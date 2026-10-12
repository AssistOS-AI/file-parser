#!/usr/bin/env python3
"""Stop and release latency of llama-server on unified memory (safety follow-up item 6c).

Sends SIGKILL or SIGTERM to the runner's process group either during the load (when MemAvailable has
dropped by --fraction of the weights) or during active requests (--at seconds into np simultaneous
cold prefills), and records on one clock: signal time, exit time, and when MemAvailable is back within
0.5 GiB of the pre-run baseline. MemAvailable is sampled every 50 ms here.

usage: stop_latency.py --bin DIR --model FILE --out PREFIX --when load|active --signal KILL|TERM
                       [--ctx N] [--np N] [--fraction 0.5] [--at 5]
"""
import argparse, json, os, signal, subprocess, sys, threading, time, urllib.request

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
from serve_check2 import avail, evict, health, request, wait_flat  # noqa: E402
from attribution import memlock  # noqa: E402

G = 1024 ** 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bin', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--when', choices=['load', 'active'], required=True)
    ap.add_argument('--signal', choices=['KILL', 'TERM'], required=True)
    ap.add_argument('--ctx', type=int, default=131072)
    ap.add_argument('--np', type=int, default=4)
    ap.add_argument('--fraction', type=float, default=0.5)
    ap.add_argument('--at', type=float, default=5.0)
    ap.add_argument('--port', type=int, default=18092)
    a = ap.parse_args()
    sig = signal.SIGKILL if a.signal == 'KILL' else signal.SIGTERM
    # The memory-measurement lock, for the whole run (harness v4).
    _lock, lock_wait = memlock()
    weights = os.path.getsize(a.model)
    evict(a.model)
    baseline = wait_flat()
    base = baseline['MemAvailable']
    samples = []
    stop = threading.Event()

    def sampler():
        while not stop.is_set():
            samples.append((time.time(), avail()))
            time.sleep(0.05)
    th = threading.Thread(target=sampler, daemon=True)
    th.start()
    args = [os.path.join(TOOLS, 'gpurun'), os.path.join(a.bin, 'llama-server'), '-m', a.model, '--host', '127.0.0.1',
            '--port', str(a.port), '--no-webui', '-ngl', '99', '-fa', 'on', '-b', '2048', '-ub', '2048', '-t', '10',
            '-c', str(a.ctx), '-np', str(a.np), '--load-mode', 'dio', '--cache-ram', '8192']
    if a.np > 1:
        args.append('--kv-unified')
    log = open(a.out + '-server.log', 'w')
    t_spawn = time.time()
    server = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, env={**os.environ, 'LD_LIBRARY_PATH': ''},
                              start_new_session=True)
    result = {'when': a.when, 'signal': a.signal, 'model': os.path.basename(a.model), 'ctx': a.ctx, 'np': a.np,
              'baseline_GiB': round(base / G, 2), 'baseline_spread_GiB': baseline['spread_GiB'],
              'baseline_waited_s': baseline.get('waited_s'), 'memlock_wait_s': lock_wait, 'tool_version': 2}
    try:
        if a.when == 'load':
            target = weights * a.fraction
            while base - avail() < target:
                if server.poll() is not None or time.time() - t_spawn > 600:
                    raise RuntimeError('server exited or load too slow before the signal point')
                time.sleep(0.02)
            result['drop_at_signal_GiB'] = round((base - avail()) / G, 2)
        else:
            while not health(a.port):
                if server.poll() is not None:
                    raise RuntimeError('server exited while loading')
                time.sleep(0.05)
            status, body, err = request(a.port, '/tokenize', {'content': ' '.join(f'w{i}' for i in range(40000))})
            ids = body['tokens']
            per = int(a.ctx / a.np * 0.9)
            prompts = [(ids * (per // len(ids) + 1))[i:i + per] for i in range(a.np)]
            outcomes = []

            def one(p):
                outcomes.append(request(a.port, '/completion', {'prompt': p, 'n_predict': 64, 'cache_prompt': False}, timeout=600)[0])
            workers = [threading.Thread(target=one, args=(p,), daemon=True) for p in prompts]
            [w.start() for w in workers]
            time.sleep(a.at)
            result['drop_at_signal_GiB'] = round((base - avail()) / G, 2)
        t_signal = time.time()
        os.killpg(server.pid, sig)
        try:
            server.wait(120 if sig == signal.SIGKILL else 30)
        except subprocess.TimeoutExpired:
            # SIGTERM did not end it: record the hang, then kill the group and measure from there.
            result['term_hang_s'] = round(time.time() - t_signal, 1)
            t_signal = time.time()
            result['followed_by'] = 'SIGKILL'
            os.killpg(server.pid, signal.SIGKILL)
            server.wait(120)
        t_exit = time.time()
        # Wait for the memory to come back (up to 60 s).
        t_back = None
        while time.time() - t_exit < 60:
            if base - avail() <= 0.5 * G:
                t_back = time.time()
                break
            time.sleep(0.02)
        # Nothing of the runner's process group may remain, and its GPU memory must be gone.
        try:
            os.killpg(server.pid, 0)
            result['group_alive_after_exit'] = True
        except ProcessLookupError:
            result['group_alive_after_exit'] = False
        apps = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,used_memory', '--format=csv,noheader,nounits'],
                              capture_output=True, text=True, timeout=10).stdout.strip()
        result['gpu_apps_after_release'] = apps or None
        result['end_vs_baseline_GiB'] = round((base - avail()) / G, 2)
        result.update({
            'signal_to_exit_s': round(t_exit - t_signal, 3),
            'exit_to_released_s': round(t_back - t_exit, 3) if t_back else None,
            'signal_to_released_s': round(t_back - t_signal, 3) if t_back else None,
            'exit_code': server.returncode,
        })
        # The largest MemAvailable fall in any 250 ms window before the signal (allocation burst).
        before = [(t, v) for (t, v) in samples if t <= t_signal]
        burst = 0
        j = 0
        for i in range(len(before)):
            while before[i][0] - before[j][0] > 0.25:
                j += 1
            burst = max(burst, max(v for _, v in before[j:i + 1]) - before[i][1])
        result['max_fall_per_250ms_before_signal_GiB'] = round(burst / G, 2)
        after = [(t, v) for (t, v) in samples if t >= t_signal]
        result['further_drop_after_signal_GiB'] = round((before[-1][1] - min(v for _, v in after)) / G, 2) if after and before else None
        result['ok'] = t_back is not None
    except Exception as e:  # noqa: BLE001
        result['ok'] = False
        result['error'] = str(e)
        try:
            os.killpg(server.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    finally:
        time.sleep(2)
        stop.set()
        log.close()
    with open(a.out + '-mem.csv', 'w') as f:
        f.write('epoch,MemAvailable\n')
        for t, v in samples:
            f.write(f'{t:.3f},{v}\n')
    json.dump(result, open(a.out + '.json', 'w'), indent=1)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
