#!/usr/bin/env python3
"""Phase 0 safety follow-up harness (plans/phase0-safety-followup_codex.md, items 1, 2, 5).

Starts llama-server through gpurun (oom_score_adj 1000) with fixed flags and -lv 4, samples
/proc/meminfo every 100 ms with absolute timestamps, and records, per phase, the MemAvailable
drop from a flat baseline. Every request's outcome is recorded (HTTP status, error body,
prompt_n, predicted_n, slot id, start and end time); any failed or short request fails the run.
Parallel requests must be shown to overlap in time and to use different slots.

Patterns (--pattern, repeatable, run in the given order on one server):
  greedy          one 128-token greedy completion
  prefill         one request of 90 % of the context
  parallel        np requests of 20 % of the pool each, at once (after whatever ran before)
  coldparallel    np requests of ctx/np * 0.9 each, at once, on fresh slots (--cache-prompt false)
  longgen         np requests of 1,024 prompt tokens and --long-n generated tokens each, at once

usage: serve_check2.py --bin DIR --model FILE --out PREFIX --ctx N --np N [--cache-ram MiB]
                       [--load-mode dio] [--extra "ARGS"] --pattern P [--pattern P ...]
"""
import argparse, json, os, re, shlex, signal, subprocess, sys, threading, time, urllib.error, urllib.request

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import attribution  # noqa: E402
import quietgate  # noqa: E402
with open(attribution.__file__, 'rb') as _a:
    ATTRIBUTION_SHA256 = __import__('hashlib').sha256(_a.read()).hexdigest()
PROMPT = ('The capital of France is Paris. List the first ten prime numbers, then explain in two '
          'sentences why 1 is not a prime number.')
G = 1024 ** 3
# v1: greedy required exactly 128 tokens. v2 (2026-09-28 20:17:07): greedy accepted any 1+ tokens.
# v3: greedy passes on EOS within 1..128 or the 128 limit, with the stop reason and completion recorded.
# v4: passive only (attribution.py): the memory-measurement lock, runner/other-user memory attribution
#     every 500 ms, baseline flags and release judged at exit + 10 s. Requests and their checks unchanged.
# v5: validity rules rev 2 sampling: /proc/meminfo in the attribution loop (external memory for everyone),
#     timed nvidia-smi, a pre-run meminfo snapshot, and a 75 s post-exit tail for the post-run quiet window.
# v6: scheduling only (measurement unchanged): the lock is asked for after a 5 s yield and every grant is logged
#     (logs/memlock.log); --quiet-gate (the one rerun round) waits, without the lock, for non-runner memory to
#     hold within 0.25 GiB for 60 s, re-checks 20 s under the lock, and defers after 30 min (<out>.DEFERRED.json).
HARNESS_VERSION = 6
with open(os.path.abspath(__file__), 'rb') as _f:
    import hashlib
    HARNESS_SHA256 = hashlib.sha256(_f.read()).hexdigest()


def meminfo():
    d = {}
    with open('/proc/meminfo') as f:
        for line in f:
            k, v = line.split(':', 1)
            d[k] = int(v.split()[0]) * 1024
    return d


def avail():
    return meminfo()['MemAvailable']


def evict(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
    finally:
        os.close(fd)


def request(port, path, body, timeout=3600):
    """POST and return (status, json-or-None, error-text)."""
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=json.dumps(body).encode(),
                                 headers={'content-type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read()), None
    except urllib.error.HTTPError as e:
        return e.code, None, e.read().decode(errors='replace')[:500]
    except Exception as e:  # noqa: BLE001 - recorded as a failed request
        return None, None, repr(e)[:500]


def health(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=2) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def wait_flat(seconds=10.0, tolerance=0.25 * G, limit=300):
    """Wait until MemAvailable is flat (range within tolerance over `seconds`); return the baseline."""
    started = time.time()
    while True:
        values = []
        t = time.time()
        while time.time() - t < seconds:
            values.append(avail())
            time.sleep(0.1)
        spread = max(values) - min(values)
        if spread <= tolerance:
            return {'MemAvailable': sum(values) / len(values), 'spread_GiB': round(spread / G, 3),
                    'waited_s': round(time.time() - started, 1)}
        if time.time() - started > limit:
            return {'MemAvailable': sum(values) / len(values), 'spread_GiB': round(spread / G, 3),
                    'waited_s': round(time.time() - started, 1), 'drift': True}


BUFFER_RE = re.compile(r'(\w[\w ]*?)\s+(model|KV|RS|compute|output)\s+buffer size\s*=\s*([0-9.]+) MiB')


def buffers(log_text):
    """Sum llama.cpp's logged buffers by device and kind (MiB); only the last load's lines count."""
    out = {}
    for line in log_text.splitlines():
        m = BUFFER_RE.search(line)
        if not m:
            continue
        device = m.group(1).split()[-1]
        key = f'{device} {m.group(2)}'
        out[key] = round(out.get(key, 0) + float(m.group(3)), 2)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bin', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--ctx', type=int, required=True)
    ap.add_argument('--np', type=int, required=True)
    ap.add_argument('--cache-ram', type=int, default=None)
    ap.add_argument('--load-mode', default='dio')
    ap.add_argument('--port', type=int, default=18090)
    ap.add_argument('--cold', action='store_true')
    ap.add_argument('--long-n', type=int, default=2048)
    ap.add_argument('--pattern', action='append', required=True)
    ap.add_argument('--extra', default='')
    ap.add_argument('--after', type=float, default=75, help='seconds to keep sampling after the server exits')
    ap.add_argument('--quiet-gate', action='store_true', help='rerun round: wait for a quiet host first; defer after 30 min')
    a = ap.parse_args()

    result = {'harness_version': HARNESS_VERSION, 'harness_sha256': HARNESS_SHA256, 'bin': a.bin, 'model': os.path.basename(a.model), 'ctx': a.ctx, 'np': a.np, 'cache_ram': a.cache_ram,
              'load_mode': a.load_mode, 'patterns': a.pattern, 'extra': a.extra, 'phases': [], 'requests': []}
    # Nothing else that engineering runs may overlap this run (tests, builds, hashing, pushes take the lock too).
    if a.quiet_gate:
        _lock, result['quiet_gate'] = quietgate.gate(os.path.basename(a.out))
        if _lock is None:
            # Deferred: nothing is measured and no raw file is written besides this record.
            record = {'harness_version': HARNESS_VERSION, 'harness_sha256': HARNESS_SHA256, 'status': 'DEFERRED',
                      'reason': 'no quiet interval within the gate budget', 'argv': sys.argv[1:], **result['quiet_gate']}
            with open(a.out + '.DEFERRED.json', 'x') as f:
                json.dump(record, f, indent=1)
            print(json.dumps({'deferred': True, 'waited_s': record['waited_s']}))
            return
        result['memlock_wait_s'] = result['quiet_gate']['attempts'][-1]['lock_wait_s']
    else:
        _lock, result['memlock_wait_s'] = attribution.memlock(os.path.basename(a.out))
    if a.cold:
        evict(a.model)
    result['baseline'] = wait_flat()
    result['baseline_meminfo'] = attribution.meminfo_snapshot()
    result['attribution_sha256'] = ATTRIBUTION_SHA256
    base = result['baseline']['MemAvailable']
    sampler = subprocess.Popen([sys.executable, os.path.join(TOOLS, 'memsample.py'), a.out + '-mem', '100'])
    gpu_rows = []
    gpu_stop = threading.Event()

    def gpu_sampler():
        # The runner's own GPU memory (nvidia-smi per-process used_memory is numeric on GB10), every 500 ms.
        while not gpu_stop.is_set():
            try:
                out = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,used_memory', '--format=csv,noheader,nounits'],
                                     capture_output=True, text=True, timeout=5).stdout
                used = sum(int(line.split(',')[1]) for line in out.strip().splitlines() if line.strip())
                gpu_rows.append((time.time(), used))
            except Exception:  # noqa: BLE001
                pass
            gpu_stop.wait(0.5)
    gpu_thread = threading.Thread(target=gpu_sampler, daemon=True)
    gpu_thread.start()
    time.sleep(0.5)
    args = [os.path.join(TOOLS, 'gpurun'), os.path.join(a.bin, 'llama-server'), '-m', a.model,
            '--host', '127.0.0.1', '--port', str(a.port), '--no-webui', '-lv', '4',
            '-ngl', '99', '-fa', 'on', '-b', '2048', '-ub', '2048', '-t', '10',
            '-c', str(a.ctx), '-np', str(a.np), '--load-mode', a.load_mode] + shlex.split(a.extra)
    if a.np > 1:
        args.append('--kv-unified')
    if a.cache_ram is not None:
        args += ['--cache-ram', str(a.cache_ram)]
    result['argv'] = args[1:]
    log = open(a.out + '-server.log', 'w')
    ok = True
    t_spawn = time.time()
    server = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, env={**os.environ, 'LD_LIBRARY_PATH': ''},
                              start_new_session=True)
    attr = None
    try:
        attr = attribution.AttributionSampler(a.out, server.pid)
        attr.start()
    except Exception as e:  # noqa: BLE001 - passive; never affects the run
        result.setdefault('v4_errors', []).append(repr(e)[:200])
    phase_start = t_spawn

    def phase(name, extra=None):
        nonlocal phase_start
        now = time.time()
        result['phases'].append({'name': name, 'start': round(phase_start, 3), 'end': round(now, 3), **(extra or {})})
        phase_start = now

    def tokens(count, seed):
        text = ' '.join('%s %d' % (('alpha', 'beta', 'gamma', 'delta', 'omega')[j % 5], (seed * 7919 + j) % 100003)
                        for j in range(count))
        status, body, err = request(a.port, '/tokenize', {'content': text})
        assert status == 200, (status, err)
        ids = body['tokens']
        assert len(ids) >= count, (len(ids), count)
        return ids[:count]

    def run_requests(label, bodies, expect_prompt, expect_predicted, keep_content=False):
        outs = [None] * len(bodies)

        def one(i):
            t0 = time.time()
            status, body, err = request(a.port, '/completion', bodies[i])
            t1 = time.time()
            timings = (body or {}).get('timings') or {}
            rec = {'pattern': label, 'i': i, 'status': status, 'error': err, 'start': round(t0, 3), 'end': round(t1, 3),
                   'slot': (body or {}).get('id_slot'), 'prompt_n': timings.get('prompt_n'),
                   'predicted_n': timings.get('predicted_n'), 'prompt_tps': timings.get('prompt_per_second'),
                   'predicted_tps': timings.get('predicted_per_second')}
            # The stop reason, where the server reports it (eos, limit, word).
            for key in ('stop_type', 'stopped_eos', 'stopped_limit', 'stopped_word', 'stopping_word'):
                if isinstance(body, dict) and key in body:
                    rec[key] = body[key]
            if keep_content and isinstance(body, dict):
                rec['content'] = str(body.get('content', ''))[:4000]
            # Memory-stress requests must run their exact prompt and generation lengths; nothing waives a short one.
            rec['ok'] = (status == 200 and rec['prompt_n'] == expect_prompt[i] and rec['predicted_n'] == expect_predicted)
            outs[i] = rec
        threads = [threading.Thread(target=one, args=(i,), daemon=True) for i in range(len(bodies))]
        [th.start() for th in threads]
        for th in threads:
            th.join(timeout=3600)
        recs = [o or {'pattern': label, 'ok': False, 'error': 'no result (thread timed out)'} for o in outs]
        result['requests'].extend(recs)
        good = all(r['ok'] for r in recs)
        overlap = None
        if len(recs) > 1 and good:
            latest_start = max(r['start'] for r in recs)
            earliest_end = min(r['end'] for r in recs)
            slots = {r['slot'] for r in recs}
            overlap = {'all_overlap_s': round(earliest_end - latest_start, 3), 'distinct_slots': len(slots)}
            good = good and earliest_end > latest_start and len(slots) == len(recs)
        return good, overlap

    try:
        while not health(a.port):
            if server.poll() is not None:
                raise RuntimeError(f'llama-server exited with {server.returncode}')
            if time.time() - t_spawn > 1800:
                raise RuntimeError('load took more than 30 minutes')
            time.sleep(0.05)
        result['load_seconds'] = round(time.time() - t_spawn, 2)
        phase('load')
        time.sleep(2)
        result['at_ready_drop_GiB'] = round((base - avail()) / G, 2)
        phase('settle')
        for pattern in a.pattern:
            if pattern == 'greedy':
                good, ov = run_requests(pattern, [{'prompt': PROMPT, 'n_predict': 128, 'temperature': 0, 'top_k': 1,
                                                   'seed': 1, 'cache_prompt': False}], [None], 128, keep_content=True)
                # Greedy is a smoke check only: a bounded completion that ends at EOS (1..128 tokens) or at the
                # 128-token limit passes; the stop reason is recorded. It never waives a stress pattern.
                g = result['requests'][-1]
                n = g.get('predicted_n') or 0
                stop = g.get('stop_type') or ('eos' if g.get('stopped_eos') else 'limit' if g.get('stopped_limit') else None)
                good = g['status'] == 200 and ((stop == 'eos' and 1 <= n <= 128) or (stop == 'limit' and n == 128))
                g['stop_reason'] = stop
                g['ok'] = good
            elif pattern == 'prefill':
                n = int(a.ctx * 0.9)
                good, ov = run_requests(pattern, [{'prompt': tokens(n, 1), 'n_predict': 16, 'temperature': 0,
                                                   'cache_prompt': False}], [n], 16)
            elif pattern == 'parallel':
                n = int(a.ctx * 0.2)
                bodies = [{'prompt': tokens(n, i + 2), 'n_predict': 64, 'temperature': 0, 'cache_prompt': False}
                          for i in range(a.np)]
                good, ov = run_requests(pattern, bodies, [n] * a.np, 64)
            elif pattern == 'coldparallel':
                n = int(a.ctx / a.np * 0.9)
                bodies = [{'prompt': tokens(n, i + 20), 'n_predict': 16, 'temperature': 0, 'cache_prompt': False}
                          for i in range(a.np)]
                good, ov = run_requests(pattern, bodies, [n] * a.np, 16)
            elif pattern == 'longgen':
                bodies = [{'prompt': tokens(1024, i + 40), 'n_predict': a.long_n, 'temperature': 0.8, 'seed': i,
                           'ignore_eos': True, 'cache_prompt': False} for i in range(a.np)]
                good, ov = run_requests(pattern, bodies, [1024] * a.np, a.long_n)
            else:
                raise ValueError(pattern)
            phase(pattern, {'ok': good, 'overlap': ov})
            ok = ok and good
    except Exception as e:  # noqa: BLE001
        ok = False
        result['error'] = str(e)
    finally:
        result['stop_signal_epoch'] = round(time.time(), 3)
        try:
            os.killpg(server.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            server.wait(60)
        except subprocess.TimeoutExpired:
            os.killpg(server.pid, signal.SIGKILL)
            server.wait()
        result['exit_epoch'] = round(time.time(), 3)
        time.sleep(a.after)
        if attr:
            attr.stop()
        gpu_stop.set()
        sampler.send_signal(signal.SIGTERM)
        sampler.wait(30)
        log.close()
    result['ok'] = ok
    # Per-phase peaks from the absolute-time samples.
    rows = []
    with open(a.out + '-mem.csv') as f:
        next(f)
        for line in f:
            parts = line.strip().split(',')
            rows.append((float(parts[0]), int(parts[3])))  # epoch, MemAvailable
    for ph in result['phases']:
        inside = [v for (t, v) in rows if ph['start'] <= t <= ph['end']]
        if inside:
            ph['peak_drop_GiB'] = round((base - min(inside)) / G, 2)
    after = [(t, v) for (t, v) in rows if t >= result['exit_epoch']]
    if after:
        back = next((t for (t, v) in after if base - v <= 0.5 * G), None)
        result['release'] = {'end_drop_GiB': round((base - after[-1][1]) / G, 2),
                             'seconds_to_within_0.5GiB': round(back - result['exit_epoch'], 2) if back else None}
        # A run whose MemAvailable does not come back to its baseline was disturbed by something else.
        result['drift'] = abs(base - after[-1][1]) > 0.75 * G
    if gpu_rows:
        result['gpu_used_MiB_max'] = max(u for _, u in gpu_rows)
        for ph in result['phases']:
            inside = [u for (t, u) in gpu_rows if ph['start'] <= t <= ph['end']]
            if inside:
                ph['gpu_used_MiB_max'] = max(inside)
    result['peak_drop_GiB'] = round((base - min(v for _, v in rows)) / G, 2) if rows else None
    log_text = open(a.out + '-server.log').read()
    result['buffers_MiB'] = buffers(log_text)
    result['buffers_total_GiB'] = round(sum(result['buffers_MiB'].values()) / 1024, 2)
    result['cache_events'] = {
        'saved': len(re.findall(r'saving idle slot to prompt cache|prompt cache.*(save|store)', log_text)),
        'skipped_exceeds_limit': len(re.findall(r'exceeds cache size limit', log_text)),
        'cleared_idle': len(re.findall(r'TAG_IDLE_SLOT_CLEAR|clearing idle slot|clear idle', log_text)),
        'no_memory_slot': len(re.findall(r'failed to find a memory slot', log_text)),
    }
    result['baseline_spread_GiB'] = result['baseline']['spread_GiB']
    try:
        result['v4'] = attribution.analyse(result, rows, attr.rows if attr else [], base)
        if attr and attr.errors:
            result.setdefault('v4_errors', []).extend(attr.errors)
    except Exception as e:  # noqa: BLE001
        result.setdefault('v4_errors', []).append(repr(e)[:200])
    json.dump(result, open(a.out + '.json', 'w'), indent=1)
    brief = {k: result.get(k) for k in ('ok', 'error', 'drift', 'load_seconds', 'at_ready_drop_GiB', 'peak_drop_GiB',
                                        'buffers_total_GiB', 'gpu_used_MiB_max', 'cache_events', 'baseline_spread_GiB', 'release')}
    v4 = result.get('v4', {})
    brief['v4'] = {'release_10s_ok': v4.get('release_10s', {}).get('ok'), 'baseline': v4.get('baseline'),
                   'unattributed_ok': v4.get('attribution', {}).get('within_0.5GiB_of_ready'), 'errors': result.get('v4_errors')}
    brief['phases'] = [(p['name'], p.get('ok'), p.get('peak_drop_GiB'), p.get('overlap')) for p in result['phases']]
    print(json.dumps(brief))


if __name__ == '__main__':
    main()
