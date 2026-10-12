---
name: measurement-quiet-host
description: During Spark memory measurements, run tests/builds/hashing/pushes under flock /home/research/phase0/.memlock; host is multi-user
metadata:
  type: feedback
---
While Phase 0 / follow-up memory measurements run (harness v4 holds `/home/research/phase0/.memlock` per run), wrap any engineering command that can move memory (node --test, builds, hashing, git push) in `flock /home/research/phase0/.memlock <cmd>`.

**Why:** unit tests run beside the matrix contaminated two runs (rejected by the data-quality review, 2026-09-28). The DGX host is also shared with other users (salboaie, daniel) whose multi-GiB node processes come and go, so harness v4 attributes memory instead of assuming a quiet host.

**How to apply:** check `pgrep -af serve_check2` before heavy work, take the lock, and never judge a run by its last sample: use `tools/memory_validity.py`. Don't wait on a process with `pgrep -f <pattern>` from a shell whose own command line contains the pattern (it matches itself); wait on the PID. Related: [[dgx-host-tooling]], [[keep-models-until-conclusion]].
