---
name: keep-models-until-conclusion
description: "Keep downloaded model files while disk space allows, until the implementation no longer needs them; delete only with the owner's go-ahead (owner rule, 2026-09-28)"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 8bfd08cf-9225-4b6c-b766-b7917428a572
  modified: 2026-09-28T17:52:19.270Z
---

Keep every downloaded, verified model file (and other large artifacts that are slow to fetch again) while disk space allows, until the implementation no longer needs them. The owner's words: "If we have space we should keep these models until no longer needed for the implementation". Delete one only with the owner's go-ahead.

**Why:** on 2026-09-28 the Phase 0 models were deleted "once their benchmarks were done". That rule came from the plan I wrote, when the disk had about 132 GB free. The disk cleanup freed most of it, but nobody revisited the rule, so gpt-oss-120b was deleted with 449 GB still free. The safety follow-up then needed it again, and the re-downloads of gpt-oss-120b (63.4 GB) and Qwen3.6 (22.9 GB) cost about 2 hours. The owner asked "Why don't we keep these models…?" and then "only delete them once we have a conclusion". I relayed that rule to the engineering session.

**How to apply:**
- In plans and implementation prompts, don't prescribe deleting models between steps unless disk space actually requires it. Re-check any disk-driven rule after a cleanup changes free space.
- Before recommending a deletion, check whether later work (reviews, re-measurements, acceptance) could need the file.
- Prefer reusing verified files (hard links) over downloading again.

Related: [[dgx-local-agent-planning]]
