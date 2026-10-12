#!/usr/bin/env python3
import json, os, signal, subprocess, sys, time, urllib.request
BASE = 'http://127.0.0.1:11535'
def post(path, body, timeout=1800):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={'content-type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read())
def du(p): return int(subprocess.check_output(['du', '-sb', p]).split()[0])
PROMPT = 'The capital of France is Paris. List the first ten prime numbers, then explain in two sentences why 1 is not a prime number.'
out = {}
def gen(label):
    s = subprocess.Popen([sys.executable, 'tools/memsample.py', f'results/ollama-{label}-mem', '100']); time.sleep(0.5)
    t = time.time()
    r = post('/api/generate', {'model': 'gpt-oss:20b', 'prompt': PROMPT, 'stream': False, 'think': 'low',
                               'options': {'temperature': 0, 'seed': 1, 'num_predict': 256}})
    wall = time.time() - t
    ps = post('/api/ps', {}) if False else json.loads(urllib.request.urlopen(BASE + '/api/ps').read())
    s.send_signal(signal.SIGTERM); s.wait()
    mem = json.load(open(f'results/ollama-{label}-mem.json'))
    out[label] = {'wall_s': round(wall, 2), 'load_s': round(r['load_duration'] / 1e9, 2),
                  'eval_tps': round(r['eval_count'] / (r['eval_duration'] / 1e9), 1),
                  'prompt_tps': round(r['prompt_eval_count'] / max(r['prompt_eval_duration'], 1) * 1e9, 1),
                  'jit_cache_bytes': du('ollama-jit'), 'ps': ps.get('models'), 'max_drop_MemAvailable_GiB': mem['max_drop_MemAvailable_GiB'],
                  'min_MemAvailable_GiB': mem['min_MemAvailable_GiB'], 'response_head': r['response'][:160]}
    print(label, json.dumps({k: v for k, v in out[label].items() if k != 'ps'}))
def unload():
    post('/api/generate', {'model': 'gpt-oss:20b', 'keep_alive': 0}); time.sleep(3)
gen('first-load-empty-jit')
unload()
gen('reload-warm-jit')
# Tool call
r = post('/api/chat', {'model': 'gpt-oss:20b', 'stream': False, 'options': {'temperature': 0, 'seed': 1},
    'messages': [{'role': 'user', 'content': 'What is the weather in Bucharest right now? Use the tool.'}],
    'tools': [{'type': 'function', 'function': {'name': 'get_weather', 'description': 'Current weather for a city',
               'parameters': {'type': 'object', 'properties': {'city': {'type': 'string'}}, 'required': ['city']}}}]})
out['tool_call'] = r['message'].get('tool_calls')
print('tool_calls', json.dumps(out['tool_call']))
json.dump(out, open('results/ollama-gate.json', 'w'), indent=1)
