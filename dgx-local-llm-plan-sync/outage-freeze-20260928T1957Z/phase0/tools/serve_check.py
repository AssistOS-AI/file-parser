#!/usr/bin/env python3
"""Phase 0 server check for one llama.cpp build and one model.

Starts llama-server (through gpurun, oom_score_adj 1000) with fixed flags, samples
/proc/meminfo every 100 ms, and records: load time, page cache before/after load,
a greedy completion, optionally a full-context prefill and parallel requests.
Writes <out>.json (results) and <out>-mem.csv/.json (memory samples).

usage: serve_check.py --bin DIR --model FILE --out PREFIX [--load-mode dio|none|auto]
                      [--ctx N] [--np N] [--cold] [--prefill] [--parallel] [--extra "ARGS"]
"""
import argparse, json, os, shlex, signal, subprocess, sys, threading, time, urllib.request

TOOLS = os.path.dirname(os.path.abspath(__file__))
PROMPT = ('The capital of France is Paris. List the first ten prime numbers, then explain in two '
          'sentences why 1 is not a prime number.')
G = 1024 ** 3


def meminfo():
    d = {}
    with open('/proc/meminfo') as f:
        for line in f:
            k, v = line.split(':', 1)
            d[k] = int(v.split()[0]) * 1024
    return d


def evict(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
    finally:
        os.close(fd)


def post(url, body, timeout=3600):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={'content-type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def health(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bin', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--load-mode', default='dio')
    ap.add_argument('--ctx', type=int, default=8192)
    ap.add_argument('--np', type=int, default=1)
    ap.add_argument('--port', type=int, default=18090)
    ap.add_argument('--cold', action='store_true', help='evict the model file from the page cache first')
    ap.add_argument('--prefill', action='store_true', help='send one prompt filling most of the context')
    ap.add_argument('--parallel', action='store_true', help='send --np long requests at once')
    ap.add_argument('--extra', default='')
    a = ap.parse_args()

    result = {'bin': a.bin, 'model': os.path.basename(a.model), 'load_mode': a.load_mode, 'ctx': a.ctx,
              'np': a.np, 'cold': a.cold, 'extra': a.extra}
    if a.cold:
        evict(a.model)
    before = meminfo()
    sampler = subprocess.Popen([sys.executable, os.path.join(TOOLS, 'memsample.py'), a.out + '-mem', '100'])
    time.sleep(0.5)
    args = [os.path.join(TOOLS, 'gpurun'), os.path.join(a.bin, 'llama-server'), '-m', a.model,
            '--host', '127.0.0.1', '--port', str(a.port), '--no-webui',
            '-ngl', '99', '-fa', 'on', '-b', '2048', '-ub', '2048', '-t', '10',
            '-c', str(a.ctx), '-np', str(a.np), '--load-mode', a.load_mode] + shlex.split(a.extra)
    if a.np > 1:
        args.append('--kv-unified')
    log = open(a.out + '-server.log', 'w')
    t0 = time.time()
    server = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, env={**os.environ, 'LD_LIBRARY_PATH': ''})
    try:
        while not health(a.port):
            if server.poll() is not None:
                raise RuntimeError(f'llama-server exited with {server.returncode}')
            if time.time() - t0 > 1800:
                raise RuntimeError('load took more than 30 minutes')
            time.sleep(0.1)
        result['load_seconds'] = round(time.time() - t0, 2)
        after = meminfo()
        result['load_delta_GiB'] = {k: round((after[k] - before[k]) / G, 2) for k in ('MemFree', 'MemAvailable', 'Cached')}
        result['after_load_GiB'] = {k: round(after[k] / G, 2) for k in ('MemFree', 'MemAvailable', 'Cached')}
        size = os.path.getsize(a.model)
        result['load_rate_GBps'] = round(size / 1e9 / result['load_seconds'], 2)

        g = post(f'http://127.0.0.1:{a.port}/completion', {
            'prompt': PROMPT, 'n_predict': 128, 'temperature': 0, 'top_k': 1, 'seed': 1, 'cache_prompt': False})
        result['greedy'] = {'content': g.get('content'), 'tokens_predicted': g.get('tokens_predicted'),
                            'timings': g.get('timings')}

        def tokens(count, seed):
            # Exactly `count` token ids of varied text, counted by the server's own tokenizer.
            text = ' '.join('%s %d' % (('alpha', 'beta', 'gamma', 'delta', 'omega')[j % 5], (seed * 7919 + j) % 100003)
                            for j in range(count))
            ids = post(f'http://127.0.0.1:{a.port}/tokenize', {'content': text})['tokens']
            assert len(ids) >= count, (len(ids), count)
            return ids[:count]

        if a.prefill:
            # 90 % of the whole context in one request (one slot may use the unified pool).
            target = int(a.ctx * 0.9)
            prompt_ids = tokens(target, 1)
            t = time.time()
            p = post(f'http://127.0.0.1:{a.port}/completion', {
                'prompt': prompt_ids, 'n_predict': 16, 'temperature': 0, 'cache_prompt': False})
            result['prefill'] = {'tokens': target, 'seconds': round(time.time() - t, 2), 'timings': p.get('timings'),
                                 'mem_GiB': {k: round(meminfo()[k] / G, 2) for k in ('MemFree', 'MemAvailable', 'Cached')}}
        if a.parallel and a.np > 1:
            # Each slot gets 20 % of the pool, so all run at once within the unified KV cache.
            per = int(a.ctx * 0.2)
            prompts = [tokens(per, i + 2) for i in range(a.np)]
            outs = [None] * a.np

            def one(i):
                # A failed request leaves outs[i] None; the check below fails the run.
                outs[i] = post(f'http://127.0.0.1:{a.port}/completion', {
                    'prompt': prompts[i], 'n_predict': 64, 'temperature': 0, 'cache_prompt': False}).get('timings')
            t = time.time()
            threads = [threading.Thread(target=one, args=(i,)) for i in range(a.np)]
            [th.start() for th in threads]
            [th.join() for th in threads]
            result['parallel'] = {'seconds': round(time.time() - t, 2), 'timings': outs}
            failed = sum(1 for o in outs if not o)
            if failed:
                raise RuntimeError(f'{failed} of {a.np} parallel requests failed')
        result['ok'] = True
    except Exception as e:
        result['ok'] = False
        result['error'] = str(e)
    finally:
        server.send_signal(signal.SIGTERM)
        try:
            server.wait(60)
        except subprocess.TimeoutExpired:
            server.kill()
        time.sleep(1)
        sampler.send_signal(signal.SIGTERM)
        sampler.wait(30)
        log.close()
    result['mem'] = json.load(open(a.out + '-mem.json'))
    with open(a.out + '-server.log') as f:
        result['server_log_notes'] = [line.strip() for line in f if any(s in line for s in (
            'integrated', 'load_mode', 'CUDA0 model buffer', 'CUDA0 KV buffer', 'CUDA0 compute buffer',
            'using device', 'load_backend', 'direct I/O', 'mmap', 'error', 'failed'))][:40]
    json.dump(result, open(a.out + '.json', 'w'), indent=1)
    print(json.dumps({k: result[k] for k in result if k not in ('mem', 'server_log_notes', 'greedy')}))
    print('greedy:', json.dumps((result.get('greedy') or {}).get('content'))[:300])
    print('min MemAvailable GiB:', result['mem']['min_MemAvailable_GiB'], 'max drop:', result['mem']['max_drop_MemAvailable_GiB'])


if __name__ == '__main__':
    main()
