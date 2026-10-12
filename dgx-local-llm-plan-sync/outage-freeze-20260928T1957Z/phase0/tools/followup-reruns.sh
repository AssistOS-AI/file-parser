#!/bin/sh
# Reruns after the follow-up matrix (plans/phase0-followup-data-quality_codex.md, section 4).
# Each round classifies every serve run (memory_validity.py) and runs the next repetition of each
# configuration that has fewer than two CLEAN, agreeing runs (memory_validity.py rule 3). One automatic round
# (2026-09-28: no run has been CLEAN on this shared host yet, so further rounds are a decision, not a default).
# Each rerun passes the quiet-host scheduling gate (--quiet-gate, harness v6): it waits without the lock for
# non-runner memory to hold within 0.25 GiB for 60 s, re-checks under the lock, and defers after 30 min
# (<out>.DEFERRED.json, reported below). A heuristic only; a gated run is judged by the same rules.
# Run names are <stem>-r<rep>[-a<attempt>]; preserved Phase 0 entries are skipped. Stop-latency runs are
# judged separately. Every run holds the memory lock (harness v4).
set -u
cd /home/research/phase0
OUT=results/followup
for round in 1; do
  python3 tools/memory_validity.py > "$OUT/memory-validity-round$round.txt" 2>&1
  todo=$(python3 - <<'PY'
import json, glob, os, re, shlex
v = json.load(open('results/followup/memory-validity.json'))
models = {'gpt-oss-120b-MXFP4.gguf': ('models/gpt-oss-120b-MXFP4.gguf', '120b'), 'gpt-oss-20b-MXFP4.gguf': ('models/gpt-oss-20b-MXFP4.gguf', '20b'),
          'Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf': ('models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf', 'qwen')}
for c in v['configs']:
    if c['status'] == 'enough':
        continue
    runs = [name for name, _ in c['runs'] if not name.startswith('phase0/')]
    if not runs:
        continue
    parsed = [re.match(r'^(.*)-r(\d+)(?:-a\d+)?$', name) for name in runs]
    stem = parsed[0].group(1)
    rep = 1 + max(int(m.group(2)) for m in parsed)
    if glob.glob(f'results/followup/{stem}-r{rep}*'):
        continue  # never overwrite
    last = json.load(open(f'results/followup/{runs[-1]}.json'))
    model, _ = models[last['model']]
    args = ['python3', 'tools/serve_check2.py', '--bin', 'l1/llama-b11159', '--model', model, '--out', f'results/followup/{stem}-r{rep}',
            '--ctx', str(last['ctx']), '--np', str(last['np']), '--cache-ram', str(last['cache_ram']), '--cold', '--quiet-gate', f'--extra={last.get("extra", "")}']
    for p in last['patterns']:
        args += ['--pattern', p]
    print(' '.join(shlex.quote(x) for x in args))
PY
)
  [ -z "$todo" ] && { echo "== reruns: every configuration has enough valid runs (round $round) $(date +%T)"; break; }
  echo "$todo" | while IFS= read -r cmd; do
    echo "== rerun round $round $(date +%T): $cmd"
    sh -c "$cmd" 2>&1 | tail -1
  done
done
python3 tools/memory_validity.py > "$OUT/memory-validity-final.txt" 2>&1
for d in "$OUT"/*.DEFERRED.json; do [ -e "$d" ] && echo "== DEFERRED (no quiet interval within 30 min): $(basename "$d")"; done
echo "== reruns done $(date +%T)"
