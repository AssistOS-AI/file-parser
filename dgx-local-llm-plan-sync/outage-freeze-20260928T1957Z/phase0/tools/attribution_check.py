#!/usr/bin/env python3
"""Controlled check of the attribution (validity rules rev 2, check 4e). No GPU.

Under the memory lock, between matrix runs: a dummy runner (sleep, own session) is sampled by the v5
AttributionSampler while a helper allocates and touches ~2 GiB of anonymous memory for 20 s. Pass when
external memory rises by 2 GiB (+-0.3) while the helper holds it, at the right time (the rise within 1.5 s
of the helper's "touched" timestamp), the runner fields stay flat, and the residual (drop - runner -
external) stays within 0.3 GiB of its start. Writes results/followup/attribution-check.json.
"""
import json, os, subprocess, sys, time

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import attribution  # noqa: E402

G = 1024 ** 3
HELPER = r'''
import mmap, sys, time
size = 2 * 1024 ** 3
buf = mmap.mmap(-1, size, flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS)
t0 = time.time()
for off in range(0, size, 4096):
    buf[off] = 1
print(f"{t0:.3f} {time.time():.3f}", flush=True)
time.sleep(20)
print(f"{time.time():.3f}", flush=True)
'''


def main():
    out_path = os.path.join(TOOLS, '..', 'results', 'followup', 'attribution-check.json')
    lock, waited = attribution.memlock()
    dummy = subprocess.Popen(['sleep', '120'], start_new_session=True)
    pre = attribution.meminfo_snapshot()
    sampler = attribution.AttributionSampler(os.path.join(TOOLS, '..', 'results', 'followup', 'attribution-check'), dummy.pid)
    sampler.start()
    time.sleep(8)
    helper = subprocess.Popen([sys.executable, '-c', HELPER], stdout=subprocess.PIPE, text=True)
    first = helper.stdout.readline().split()
    t_alloc_start, t_touched = float(first[0]), float(first[1])
    t_released = float(helper.stdout.readline())
    helper.wait()
    time.sleep(8)
    sampler.stop()
    dummy.kill()
    rows = sampler.rows
    ext0 = pre['AnonPages'] + pre['Shmem']
    series = [(r['epoch'], (r['meminfo']['AnonPages'] + r['meminfo']['Shmem'] - r['runner_anon'] - r['runner_shmem']) - ext0,
               pre['MemAvailable'] - r['meminfo']['MemAvailable'], r['runner_gpu'] + r['runner_anon'] + r['runner_shmem'])
              for r in rows]
    before = [s for s in series if s[0] < t_alloc_start]
    held = [s for s in series if t_touched + 1 <= s[0] <= t_released - 1]
    after = [s for s in series if s[0] > t_released + 1.5]
    ext_before = sum(s[1] for s in before) / len(before)
    ext_held = sum(s[1] for s in held) / len(held)
    ext_after = sum(s[1] for s in after) / len(after) if after else None
    rise = next((s[0] for s in series if s[1] - ext_before >= 1.8 * G), None)
    residual = [s[2] - s[3] - s[1] for s in series]
    runner = [s[3] for s in series]
    result = {
        'check': 'rev 2, 4e: controlled 2 GiB anonymous allocation, no GPU, under the memory lock',
        'attribution_sha256': __import__('hashlib').sha256(open(attribution.__file__, 'rb').read()).hexdigest(),
        'lock_wait_s': waited, 'samples': len(rows), 'errors': sampler.errors,
        'helper': {'alloc_start': t_alloc_start, 'touched': t_touched, 'released': t_released},
        'external_before_GiB': round(ext_before / G, 2), 'external_while_held_GiB': round(ext_held / G, 2),
        'external_after_GiB': round(ext_after / G, 2) if ext_after is not None else None,
        'external_step_GiB': round((ext_held - ext_before) / G, 2),
        'rise_seen_s_after_touched': round(rise - t_touched, 2) if rise else None,
        'runner_range_GiB': round((max(runner) - min(runner)) / G, 3),
        'residual_range_GiB': round((max(residual) - min(residual)) / G, 2),
        'drop_step_GiB': round((sum(s[2] for s in held) / len(held) - sum(s[2] for s in before) / len(before)) / G, 2),
    }
    # Evaluation 2: steps across each edge (last sample before, first after). Window averages are kept for
    # the record but cannot isolate a 2 GiB step while other users move several GiB (2026-09-28 check).
    def ext_of(r):
        return r['meminfo']['AnonPages'] + r['meminfo']['Shmem'] - r['runner_anon'] - r['runner_shmem']

    def edge(t0, t1):
        a = [r for r in rows if r['epoch'] < t0][-1]
        b = [r for r in rows if r['epoch'] > t1][0]
        d_ext = ext_of(b) - ext_of(a)
        d_drop = a['meminfo']['MemAvailable'] - b['meminfo']['MemAvailable']
        d_run = (b['runner_gpu'] + b['runner_anon'] + b['runner_shmem']) - (a['runner_gpu'] + a['runner_anon'] + a['runner_shmem'])
        return {'external_step_GiB': round(d_ext / G, 2), 'drop_step_GiB': round(d_drop / G, 2),
                'runner_step_GiB': round(d_run / G, 3), 'residual_step_GiB': round((d_drop - d_ext - d_run) / G, 2)}
    result['evaluation_version'] = 2
    result['alloc_edge'] = edge(t_alloc_start, t_touched)
    result['release_edge'] = edge(t_released, t_released)
    ae, re_ = result['alloc_edge'], result['release_edge']
    result['pass'] = (abs(ae['external_step_GiB'] - 2.0) <= 0.3 and abs(re_['external_step_GiB'] + 2.0) <= 0.3
                      and abs(ae['residual_step_GiB']) <= 0.3 and abs(re_['residual_step_GiB']) <= 0.3
                      and abs(ae['runner_step_GiB']) <= 0.05 and abs(re_['runner_step_GiB']) <= 0.05)
    result['pass_window_average'] = (abs(result['external_step_GiB'] - 2.0) <= 0.3 and result['rise_seen_s_after_touched'] is not None
                      and -1.5 <= result['rise_seen_s_after_touched'] <= 1.5 and result['runner_range_GiB'] <= 0.05
                      and result['residual_range_GiB'] <= 0.3)
    json.dump(result, open(out_path, 'w'), indent=1)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
