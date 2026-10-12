#!/usr/bin/env python3
"""Top-5 next-token probabilities after PROMPT + prefix, for one build. usage: probe_tie.py BIN MODEL PREFIX_FILE"""
import json, os, subprocess, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from serve_check import PROMPT, post, health
bin_, model, prefix = sys.argv[1], sys.argv[2], open(sys.argv[3]).read()
port = 18091
p = subprocess.Popen([os.path.join(os.path.dirname(__file__), 'gpurun'), os.path.join(bin_, 'llama-server'), '-m', model,
    '--host', '127.0.0.1', '--port', str(port), '--no-webui', '-ngl', '99', '-fa', 'on', '-b', '2048', '-ub', '2048',
    '-t', '10', '-c', '8192', '-np', '1', '--load-mode', 'dio'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    env={**os.environ, 'LD_LIBRARY_PATH': ''})
try:
    while not health(port): time.sleep(0.2)
    r = post(f'http://127.0.0.1:{port}/completion', {'prompt': PROMPT + prefix, 'n_predict': 1, 'temperature': 0,
        'top_k': 1, 'n_probs': 5, 'cache_prompt': False, 'post_sampling_probs': False})
    print(json.dumps(r['completion_probabilities'][0]['top_logprobs'] if 'top_logprobs' in r['completion_probabilities'][0] else r['completion_probabilities'][0])[:600])
finally:
    p.terminate(); p.wait()
