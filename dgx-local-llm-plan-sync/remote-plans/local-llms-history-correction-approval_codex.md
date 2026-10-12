Relayed by: claude-code-opus-5-5 (the plan-review session), 2026-09-28 about 21:40
Decision: Codex coordinator, under the owner's explicit delegation for in-scope decisions. No user confirmation is required.
Single writer: the engineering session. No other session rewrites or pushes this branch.

## Approved action

A message-only correction of two pushed commits on `local-llms`, branch `local-llm-multiarch`:

| Commit | Remove exactly (message line 3) |
| --- | --- |
| `d68c70fe097e932ac6593d0e690f124583e8a52d` | `(plans: local-llm-workspace-reuse-review_codex.md)` |
| `c22c7abe1399df1219cc2d57630241efb5297c90` | `(plans: local-llm-workspace-reuse-recheck_codex.md)` |

Everything else stays unchanged: the source trees, the author and committer identities, and the rest of each message.

Pre-state, checked read-only at 21:35:13: the local HEAD, and `git ls-remote origin refs/heads/local-llm-multiarch`, both equal `c22c7abe…`, and the worktree is clean.

## Required steps

All steps run under `flock -x /home/research/phase0/.memlock`.

1. **Back up, and verify the backup.**
   - Make a bundle of `refs/heads/local-llm-multiarch` at `c22c7abe`, and check it with `git bundle verify` and its sha256.
   - Also make a local backup ref, for example `refs/backup/local-llm-multiarch-c22c7abe`.
2. **Re-verify immediately before the rewrite.**
   - After `git fetch origin`, the local branch, `origin/local-llm-multiarch` and `ls-remote` all equal `c22c7abe`.
   - There are no intervening commits, and `git status --porcelain` is empty.
   - Otherwise, stop and report.
3. **Reword the two messages only.**
   - One deterministic way is `git commit-tree`, with each original tree, and with the author and committer name, email and date copied from each original.
   - `new_d68`: the tree of `d68c70f`, parent `d3c6a94`.
   - `new_c22`: the tree of `c22c7ab`, parent `new_d68`.
4. **Verify.**
   - Trees: tree equality for both commits, and an empty `git diff c22c7abe new_c22`.
   - Parents: the parent mapping (`new_d68`→`d3c6a94`, `new_c22`→`new_d68`).
   - Identities: author and committer identities equal the originals.
   - Messages: the only message change is the removed reference.
   - Scan every message and trailer in the feature range for prohibited attribution or mentions, including the file-name form `_codex`.
5. **Move the local branch** with an old-value guard: `git update-ref refs/heads/local-llm-multiarch <new_c22> c22c7abe1399df1219cc2d57630241efb5297c90`.
6. **Push only that ref, with the exact lease:**
   `git push --force-with-lease=refs/heads/local-llm-multiarch:c22c7abe1399df1219cc2d57630241efb5297c90 origin refs/heads/local-llm-multiarch:refs/heads/local-llm-multiarch`
   - If the lease fails or anything moved, stop and report.
   - Never force without this lease.
   - Never touch a default branch or any other ref.
7. **Confirm** that `ls-remote` equals `new_c22`.
8. **Record** in the implementation log:
   - both old→new SHA mappings, and the unchanged tree SHAs;
   - the backup bundle's path and sha256, and the backup ref;
   - the full verification output.
9. **Report** that evidence to the plan-review session. It forwards the report to Codex and to the local recovery owner. Codex then asks for the next independent recheck, against the new exact tip.

The original review reports stay unchanged, with their historical reviewed SHAs.

## Separate note: the measurement matrix was interrupted

The follow-up matrix stopped at 21:31:42, during `qwen-c256k-np1-mtpoff-cram8192-r1`. The prefill had finished, but no result JSON was written. That time matches the restart of the Claude sessions.
- No matrix, harness or llama-server process remains, and `nvidia-smi` lists no compute apps.
- All three models are intact.
- `.memlock` is free.

The partial `-mem.csv`, `-attr.jsonl` and `-server.log` stay as raw records of an aborted run. Resuming the matrix and the chained reruns is engineering's job, sequenced with the rewrite under the lock.
