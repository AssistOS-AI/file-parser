#!/usr/bin/env python3
"""Summarize llama-bench jsonl files: mean, sd, CV per (test, depth, load mode)."""
import json, statistics, sys
for path in sys.argv[1:]:
    for line in open(path):
        r = json.loads(line)
        test = f"pp{r['n_prompt']}" if r['n_prompt'] else f"tg{r['n_gen']}"
        s = r['samples_ts']; m = statistics.mean(s); sd = statistics.pstdev(s)
        print(f"{path.split('/')[-1]:55s} {test:7s} d{r['n_depth']:<6d} {r.get('load_mode', r.get('use_mmap')):>5} "
              f"{m:9.2f} ±{sd:6.2f} cv {100*sd/m:4.1f}% n={len(s)}")
