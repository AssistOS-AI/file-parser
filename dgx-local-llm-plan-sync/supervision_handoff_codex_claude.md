# Recovery handoff: local-llm multi-arch work on pgx-research

Written 2026-09-28 18:55 +0300 (15:55Z), last updated 2026-09-29 (owner decisions on runners and vLLM) by the Claude Code session on the owner's Mac that owns the mirror/watch ("Anthropic Messages API server support", this directory). Requested by Codex as `supervision_handoff_codex.md`; the owner's standing rule puts `_claude` on every document Claude creates, hence this name. I keep it current as state changes.

Everything below was checked in this session unless it is marked *(as logged)*, which means it was taken from the implementer's log and not re-run here.

## 0. OUTAGE in progress (2026-09-28 23:00 +0300)

pgx-research has been unreachable since about 19:55Z (`connect … port 22: Operation timed out`, 3 of 3 bounded probes at 19:57Z). **The exact recovery state is in [`recovery_manifest_20260928T1958Z_claude.md`](recovery_manifest_20260928T1958Z_claude.md).**
- **Frozen copy:** everything mirrored is frozen in `outage-freeze-20260928T1957Z/` (with a `.sha256` list).
- **Backup refs:** `refs/outage-20260928T1957Z/local-llm-multiarch` in all three local repos.
- **Repos:** all three branches are clean, and equal on pgx (last sync), the Mac and GitHub.
- **Not mirrored:** the second C12 recheck report (of `70047bd`).
- **Phase 0 tools:** the quiet-gate v7 repair exists only as mirrored `.v7tmp` work in progress; the installed v6 `quietgate.py` is `d1c59c22`.
- **Codex:** it is the failover launcher; this session launches nothing.

> **WATCH STOPPED (2026-09-29, at the owner's request: "Stop monitoring the remote machine").** The `check_remote.py` Monitor loop was stopped at 397 consecutive failed polls. No `check_remote.py` process is left running.
> - **Nothing on the Mac updates from pgx any more:** `remote-plans/`, `repos/`, `phase0/`, `transcripts/` and the local `pgx/*` refs stay as they were at the outage (last successful sync about 19:54Z on 2026-09-28).
> - **Nobody reports a pgx recovery** (SSH_RECOVERED). If pgx comes back, whoever reconciles must fetch the state themselves.
> - **Kept:** the freeze, the backup refs, the WIP generations, `check_remote.py` and `state.json`. Restarting the loop resumes the watch (the command is in §2).
> - **Codex's own SSH processes** to `pgx`/`pgx-research` (codex app-server proxy) were left untouched.

### Failover ACTIVE (recorded 2026-09-28 23:05 +0300)

- **Launched by Codex:** the sole Mac writer is **"Local LLM multiarch Mac continuation"**. The Claude CLI session is `a0db78e6-e488-4c0b-b7ce-3b0a944c27b5` (background ID `a0db78e6`, PID 61988), with Opus 5.5, high effort, bypass permissions and Remote Control. Its launch record is `/Users/danielsava/work/local-llm-recovery-20260928/session_launch_codex.json`, and its brief is `recovery_brief_codex.md` in the same folder.
- **Recovery root:** `/Users/danielsava/work/local-llm-recovery-20260928/`. It holds independent clones on `recovery/local-llm-multiarch-20260928` at the manifest tips (ploinky `338a3c56`, local-llms `70047bd`, container-image-builds `afd9415`), plus a copy of the frozen `phase0/tools` including the `.v7tmp` work.
- **Checked here (read-only) at 2026-09-28 23:05 +0300:** each clone is on that branch at that tip, clean, with committer `skutner`. PID 61988 is alive. Its environment has `CLAUDE_CODE_EFFORT_LEVEL=high`, as are the background daemon's (this machine's daemon can override `--effort`; here it matches). It does not appear in the desktop app's session list, as expected for a CLI background session.
- **Ownership rules:**
  - the Mac writer owns portable fixes on private recovery branches, and does **not** push the shared `local-llm-multiarch` while remote ownership is uncertain;
  - NVIDIA/GB10 gates stay pending; Mac tests can't satisfy them;
  - Codex owns final review, the Opus reviewer and fix orchestration;
  - this session keeps the watch, mirror and recovery records, launches no other continuation, and doesn't edit the recovery root.
- **If pgx returns:** report immediately. Keep both histories (pgx and the Mac recovery branches) and the freeze. Wait for Codex's coordination before any source reconciliation or restarting duplicate writers.
- **Mirror size:** the Phase 0 mirror (243 MB) is near its 300 MB guard. If it trips, adjust only through a concrete, scoped preservation plan.
- **Progress (2026-09-28 23:45 +0300, read-only):** pgx is still unreachable (43 consecutive failed polls). The GitHub `local-llm-multiarch` tips are unchanged (`338a3c56`, `70047bd7`, `afd94156`). The Mac continuation committed `b972b38` on the private `recovery/local-llm-multiarch-20260928` in local-llms ("Fail a Run stopped during an empty model lookup, and let a Cancel of planning succeed"); this is the minor C12 cancellation gap from Codex's second recheck. Author and committer are `skutner`, with 0 agent mentions. It is not pushed (the local recovery branch has no upstream). ploinky and container-image-builds are unchanged. PID 61988 is alive (42 min).
- **Update (2026-09-29 00:15 +0300, read-only):** pgx is still unreachable (69 consecutive failed polls); GitHub tips are unchanged.
  - **Process:** the continuation process was **resumed as PID 77404** (`--resume … a0db78e6-….jsonl`). PID 61988 has exited; the session ID is unchanged.
  - **Its last reply (20:53Z) reports:**
    - candidate set frozen: local-llms `b972b38`, ploinky `338a3c56`, container-image-builds `afd94156`, all clean on the recovery branch;
    - a harness candidate at `65ef19c` (`quietgate.py` `b4dfb4cb…`), with a status document at `7f10b64` on a local `quietgate-v7` branch with no remote, under `phase0/harness-wt`;
    - `phase0/tools` still identical to the outage freeze.
  - **Frozen for review:** per Codex's decision, it makes no source or harness changes, commits, pushes or new sessions. Review artefacts are in `full-review-20260928/`, and `continuation_status_codex.md` plus `phase0/harness-wt/continuation_status_round2_codex.md` hold the status.
  - **Still pending on GB10:** installing the gate on pgx, the measurements, and envelope acceptance.
- **Update (2026-09-29 about 01:50 +0300, read-only):** pgx is still unreachable (149 consecutive failed polls). GitHub tips are unchanged (`338a3c56`, `70047bd7`, `afd94156`). PID 77404 is alive.
  - **Review-fix work in local-llms:** the recovery clone now has the checked-out branch `recovery/local-llm-reviewed-20260928` at `b0ada3e`, plus two worktrees under `local-llms/.claude/worktrees/`:
    - `model-files-review-fixes` at `b0ada3e` (`9f1b666`, `e55645c`, `b0ada3e` on top of `b972b38`);
    - `runtime-review-fixes` at `ebd501b` (`e47b7fa`, `59b4ae8`, `9763fda`, `ebd501b` on top of `b972b38`), not yet merged into the reviewed branch.
  - Both worktrees had 2 uncommitted paths at this check.
  - **Attribution:** all 7 new commits are `skutner`/`skutner`, with 0 agent-mention lines.
  - **Not pushed:** none of this is on GitHub. `recovery/local-llm-multiarch-20260928` is still at `b972b38`. ploinky and container-image-builds are unchanged.
- **Update (2026-09-29 about 02:20 +0300, read-only):** pgx is still unreachable (173 consecutive failed polls). GitHub tips are unchanged. PID 77404 is alive.
  - `recovery/local-llm-reviewed-20260928` is now at **`32917c3`** ("Integrate runtime cancellation and model acquisition fixes"). It contains the model-files fixes (`b0ada3e`) and the runtime fixes through `f116446`.
  - `worktree-runtime-review-fixes` is at `69d7f06` (a bounded pending free-disk test), which is **not** yet in the reviewed branch. `worktree-model-files-review-fixes` is unchanged at `b0ada3e`.
  - Both worktrees still show 2 uncommitted paths.
  - **Attribution:** all new commits are `skutner`/`skutner`, with 0 agent-mention lines. Nothing is pushed.
- **Update (2026-09-29 about 03:20 +0300, read-only):** pgx is still unreachable (225 consecutive failed polls). GitHub tips are unchanged. PID 77404 is alive.
  - **local-llms:** `recovery/local-llm-reviewed-20260928` is now at **`50f3938`** ("Complete queued-run cancellation and literal request ID handling"). It contains the runtime worktree through `f1e18da` (`69d7f06`, `4a5eb8e`, `6ab2ef5`, `88e0146`, `f1e18da`).
  - **container-image-builds:** a new local branch `recovery/local-llm-image-reviewed-20260928` is at **`a319898`** on top of `afd9415` ("Pin multiarch runner install checks to the verified source candidate"). It is checked out, clean, and has no upstream.
  - **Unchanged:** ploinky `338a3c56`.
  - **Attribution:** all new commits are `skutner`/`skutner`, with 0 agent-mention lines. Nothing is pushed.

## 1. Sessions on pgx-research (host `pgx`, user `research`, cwd `/home/research/work`)

| Role | Desktop id | CLI id / transcript on pgx | Model, effort | State at 15:52Z |
|---|---|---|---|---|
| Planning (title "server : add Anthropic Messages API support") | `local_2ef99e76-6bed-4e68-bf4a-d611494a62a5` | `e95c870c-8d4a-46a7-bacf-21525480837e.jsonl` | Opus 5.5 xhigh | idle since 12:32Z |
| Review, acting as orchestrator ("Local LLM multiarch plan review"; briefly titled "Local LLM multiarch orchestrator" from 17:43:53Z, back to the original title by about 19:3xZ, apparently after the app restart) | `local_3065c935-796a-4314-8e25-f64edea9a30f` | `8bfd08cf-9225-4b6c-b766-b7917428a572.jsonl` | Opus 5.5 max, bypass | idle |
| Implementer ("Local LLM multiarch engineering plan") | `local_d1b738b8-4be8-4527-b955-b7cd5347fdbd` | `a519e4b1-8c2d-41a5-a64d-18fad9d6ce30.jsonl` | Opus 5.5 high, bypass | running |

The transcripts live in `/home/research/.claude/projects/-home-research-work/`, and the pgx memory in `…/memory/`.

## 2. What is mirrored locally, and how fresh it is

The root is `/Users/danielsava/work/file-parser/dgx-local-llm-plan-sync/`, driven by `check_remote.py` under a Monitor loop. It polls every 60 s, and a state must hold for 2 polls before it is acted on.

| Item | Local path | Source on pgx | Refresh |
|---|---|---|---|
| Plan, reviews, review prompt, implementation log | `remote-plans/` (+ `.history/` for every replaced version) | `/home/research/work/plans/` | within about 2 min |
| Implementer repos, **committed objects** (ref sync waits only for the refs to hold 2 polls; uncommitted edits no longer delay it) | `../ploinky`, `../local-llms`, `../container-image-builds`: remote `pgx` = `pgx-research:/home/research/dev/<repo>`, refspec `+refs/heads/*:refs/remotes/pgx/*`, prune, no tags; a local branch `local-llm-multiarch` tracks `pgx/local-llm-multiarch`; checked-out branches are never moved | `/home/research/dev/<repo>` | within about 2 min of a ref change |
| Implementer repos, **uncommitted work** | **`repos/<repo>/wip/current/`** holds the **last verified** generation: `wip.patch` (tracked diff against HEAD plus untracked files ≤ 2 MB each) and `wip.meta.json` (base HEAD, branch, capture times, content-aware work hash, patch sha256, skipped files, `verified: true`). Resolve `current` once and read both files from that directory. The last 5 verified generations are kept as `wip/gen-*`. **`wip/best-effort/`** is a separate, **UNVERIFIED** pointer to the latest capture rejected because the tree changed while it was read (it applies to its base, but may mix states); only 1 is kept, and it never displaces or prunes verified generations. `wip/rejected.patch` is the last capture that failed `git apply --check`. The pre-19:34 flat files are in `repos/<repo>/legacy-flat-wip/` (superseded). | same | Every poll the content-aware work hash changed (about 60 s, one capture per poll, no stability wait), and at least every 10 min while dirty. A REPO_WIP notice at most every 30 min; REPO_WIP_FAIL after 3 consecutive unpublished captures, then REPO_WIP_RECOVERED. |
| GitHub copies | `origin/local-llm-multiarch` in the three local repos, fetched once pushed; REPO_UNPUSHED fires if a pgx tip stays off GitHub for more than 15 min | github.com/AssistOS-AI | checked every 5 min |
| Phase 0 evidence | `phase0/`: `results/`, `logs/`, `mem/`, `tools/`, `ollama-jit/`. **Excluded:** models (`models/`, `ollama-models/`), builds and binaries (`l1/`, `l2/`, `native/`, `ppl/`, `tbo/`, `ollama/`, `dl/`), and `ollama-home/` (Ollama's private key). Files over 50 MB are skipped, and a total over 300 MB is refused. | `/home/research/phase0/` | about 1 min, silent |
| Full transcripts, including `subagents/` and `tool-results/` | `transcripts/<cli-id>.jsonl` and `transcripts/<cli-id>/` | see section 1 | every 5 min; turn increments are kept in `increments/` |
| pgx memory files | `remote-memory/` | `…/memory/` | on change |
| Implementation prompt (verbatim) | `implementation_prompt_claude.md` | implementer's first message | static |
| Status page | `../DGX_LOCAL_LLM_PLAN_2026-09-28_claude.md` | — | edited by me |

**Freshness at writing:**
- the Phase 0 mirror at 18:51:44 +0300;
- transcripts at 18:48 +0300: implementer 3,111,332 B, review 5,574,154 B, planning 2,496,721 B;
- repos at 18:51:41 +0300.

**Limit:** the watch runs only while this Mac session is open, and the Monitor is re-armed every 30 min.

## 2a. Recovery guarantees (what the tests establish, 2026-09-28 19:45 +0300)

These tests ran on throwaway local repos, with fault injection enabled only in test mode, and with `check_remote.py` as deployed at about 19:45 +0300. Codex's independent checks drove three rounds of fixes:
- **19:34:** same-name untracked edits were not detected;
- **19:34:** `wip.patch` and `wip.meta.json` were not published atomically as a pair;
- **19:45:** a tree change *during* a capture was recorded as saved; later, a proposed bounded retry would have promoted an inconsistent capture.

| Guarantee | Test that establishes it |
|---|---|
| **Verified means consistent at one point in time** | A capture is published to `wip/current` only if HEAD and the content-aware work hash (tracked diff plus each untracked file's content and mode) are **equal before and after** the read, and the patch applies to `base_head` in a throwaway index |
| An edit during a capture is never recorded as saved (Codex repro 3) | Untracked `new-module.mjs` `n=11` rewritten to `n=12` mid-read, and a tracked `a.txt` edit mid-read: `wip/current` unchanged, the saved hash **not** advanced, and the capture kept only as `wip/best-effort` (`verified: false`). The **first quiet poll** published a verified generation with the new bytes. |
| Continuous mid-capture edits never degrade the verified snapshot | 6 polls, each with an edit before and during the read: `wip/current` stayed on the last verified generation throughout; REPO_WIP_FAIL fired once; `best-effort` kept 1 directory while the verified generations were untouched; the first quiet poll published the latest bytes (`c=6`) verified, with REPO_WIP_RECOVERED |
| Continuous edits between polls don't starve capture | 4–5 consecutive polls, each with an edit before the poll: every poll's edit was in `wip/current` |
| Same-name untracked content and mode edits are detected (Codex repro 1) | `n = 1` → `n = 2` with no tracked changes, and a `chmod` alone, each published a new generation |
| Patch and meta publish as one atomic pair (Codex repro 2) | A fault injected at validate, patch write, meta write, rename and pointer switch (dirty), and at meta write, rename and pointer switch (going clean): `wip/current` stayed the identical generation, patch sha256 matched meta, no temp files remained, and the next poll recovered consistently |
| A HEAD change during capture is rejected and retried | `wip/current` unchanged; captured against the new base 2 polls later |
| A non-applying patch is never published | (19:21 suite, same validation) |
| Large untracked files are listed | A 3 MB file appeared in `skipped_untracked` |
| A snapshot restores the tree | clone → checkout `base_head` → `git apply --binary` gave a byte-identical tree, except listed skipped files |
| Real checkouts are never touched | The local repo stayed on its branch, clean, in every run |
| Ref sync runs during edits | A commit made during continuous edits was fetched within 2 polls |

**Live on pgx:**
- **19:35:** local-llms `gen-20260928T193501-173` reproduced 4 files byte-for-byte (`verify_wip_restore.py`, previous layout).
- **19:46:** all three trees were clean.
- **21:18:29 +0300, current version:** `verify_wip_restore.py` confirmed local-llms `gen-20260928T211820-449` (verified, base `d3c6a94`) reproduces the live pgx dirty tree byte-for-byte: 1 changed file, 0 deletions, 0 skipped. That is the first dirty-tree restore proof on pgx for the accepted version.

`verify_wip_restore.py` now prints VERIFIED results for `wip/current` and, separately, any UNVERIFIED `wip/best-effort` and whether it is newer.

**Honest limits:**
- The pair is **not an atomic snapshot of the remote tree.** The read is lock-free (`GIT_OPTIONAL_LOCKS=0`, so it never takes the implementer's index lock), and files are read one by one. "Verified" means the content hash was the same before and after the read. A change that is made and reverted within one read would go unnoticed.
- The lock-free behaviour is inferred from git's documentation, not tested.
- **Not covered:**
  - edits since the last verified generation: at least one poll (about 60 s), and longer while edits keep landing during reads, until a quiet poll;
  - untracked files over 2 MB;
  - files outside the three dev clones;
  - anything once this Mac session is closed.

## 3. Refs (checked 15:52Z)

| Repo | pgx `local-llm-multiarch` | Base | Commits | On GitHub? (checked 16:0xZ with `git ls-remote`) |
|---|---|---|---|---|
| ploinky | `338a3c56` | `3f8ffa58` (origin/master) | `f5d95fc0` A1 arm64 ldconfig; `338a3c56` A2 NVVM 7.0 | **yes, matches** |
| local-llms | `70047bd` (as of the reword) | `03697765` (origin/main) | `ee175b9` C0; `54f9388` C1 memory-model detection; `42bf53d` unified llama.cpp inside measured envelopes plus refusing runners the image lacks; `ec77b40` unified-memory dashboard card; `574660b` chat budget/deadline settings; `a72260e` report unreadable state | **yes, matches** |
| container-image-builds | `f10aeb5` | `95ba10a2` (origin/main) | `f10aeb5` Dockerfile.arm64 prototype (L1 prebuilt llama.cpp, no Ollama), `sources.lock.arm64.json`, empty arm64 runner lock | **yes, matches** |

- **Identity:** every commit is authored and committed by `skutner <sava.dumitru.daniel@gmail.com>`, and **no commit carries AI attribution** (scanned for co-authored, claude, anthropic, generated with, codex, openai and 🤖).
- **Other branches:** none exist on pgx beyond the defaults. The pre-rename names `arm64-gpu-discovery` and `gpu-memory-unknown` are gone.

To view the implementer's changes locally:

```bash
git -C /Users/danielsava/work/file-parser/ploinky log -p 3f8ffa58..local-llm-multiarch
```

The same form works for local-llms (`03697765..`) and container-image-builds (`95ba10a2..`).

## 4. Push and attribution setup on pgx

**Push setup (verified here):**
- GitHub CLI 2.101.0 at `/home/research/.local/bin/gh` is authenticated as `skutner` (set up by Codex); `permissions.push=true` on all three repos.
- The git credential helper for github.com is `!/home/research/.local/bin/gh auth git-credential`.
- **Pushed** by the implementer at about 18:00 pgx time (16:00Z), after the owner's go-ahead in its session (per its log): new branch `local-llm-multiarch` in all three repos, no force-push. GitHub tips match the pgx tips.
- Its prompt still requires the owner's go-ahead for PRs, workflow dispatches and publishes.
- What a push triggers: only two read-only workflows, ploinky `verify-runtime-source-absence.yml` and container-image-builds `verify-edge-routing-source-absence.yml`, with no secrets. The publish workflows are main-only or dispatch-only.

**Attribution safeguards:**
- `/home/research/.claude/settings.json` has `attribution.commit=""`, `attribution.pr=""` and `includeCoAuthoredBy=false` (Codex).
- `/home/research/.claude/rules/commit-attribution_codex.md` (Codex).
- A `commit-msg` hook in each of the three dev clones (`.git/hooks/commit-msg`, sha256 `4b69bc33cfb2…`, mine; source copy in `commit-msg-hook` here) strips whole AI signature lines: AI co-author trailers, "Generated with/by <AI tool>" lines, and 🤖 lines. The first version could drop ordinary sentences such as "generated by copilot-agents' exporter", so it was tightened and retested locally, then replaced on pgx; its dry run on pgx was of the first version. The implementer has been told.
- This Mac's `~/.claude/settings.json` parses and has the same attribution keys (checked).
- New clones do **not** get the hook automatically.

## 5. Candidate status *(as logged)*

- **Phase 1 code:** A1 + A2 and C0 are done and tested on pgx.
  - ploinky GPU grant tests 61/61; the full unit suite has the same 63 failing tests as before the change, all environmental.
  - local-llms 258/260, the 2 failures being the known LM Studio thread-count tests.
- **Phase 0:** done. The Explorer deployment on pgx is destroyed. **Model files:** new owner rule (relayed by the orchestrator session, about 19:50 pgx time): keep every downloaded model until the owner says the work is concluded. This replaces delete-after-benchmark. Qwen3.6 has been re-downloaded (22.9 GB, done), gpt-oss-120b was about 52 of 63 GB at 17:44Z, and gpt-oss-20b is kept. `/home/research/phase0/models/` is not mirrored.
- **Decisions recorded in the implementation log.** The source column there says "decided by Codex under the owner's delegation":
  - **1 = L1**, the prebuilt CUDA 13.4 llama.cpp. This is recorded as a **change to the original correctness criterion**: greedy output is not bit-identical across toolkits, so acceptance rests on 16445/16445 op tests, perplexity and throughput.
  - **2 = Ollama omitted** on arm64 (amd64 unchanged).
  - Also: `dio` plus a post-checksum `posix_fadvise(DONTNEED)`; admission counts an explicit `--cache-ram`, kept at 8192 MiB until 4096 passes long-context, parallel and peak checks; the Phase 0 harness must fail on any failed parallel request.
- **Provisional:** the host reserve of 16 GiB, the guard floor of 8 GiB and the PSI rule. The plan-review session's read-only follow-up is `remote-plans/phase0-safety-followup_codex.md`. It asks for:
  - a fixed harness, and at-ready figures from logged buffers;
  - a per-model, per-np margin, since the 120b 4-slot non-cache transient is about 10.2 GiB, above the 8 GiB margin;
  - 250 ms sampling in every phase, and SIGKILL on a floor breach;
  - a stop-latency measurement;
  - a 120b re-run at `--cache-ram` 8192, 4096 and 1, which needs a 63 GB re-download.
- **Decisions recorded since** (all relayed by Codex under the owner's delegation, per the implementation log):
  - **5:** the x86 functional gate runs on ubuntu-codex; Codex owns it, and the procedure is in `plans/local-llm-x86-gate-procedure.md`.
  - **9:** no 32k completions in the first release.
  - **10:** retire the legacy agents. Implemented as its own commit `28aa001`, pushed: translation, reranking and CPU-only source retired, stored model and user data preserved, coding style moved to DS006, change documented in DS000.
  - **Qwen3.6-35B-A3B MTP:** re-download and validation approved by Codex (about 19:55 +0300), so all three first-release models can get measured envelopes.
- **Plan amended** to sha256 `714b391f…` (the orchestrator, at the owner's request): new **C12**, reuse pinned model files already in the agent's store or in the workspace's `/shared/models/` (size and sha256 match, hard-link or copy, re-verify). Model retention refined to keep the models while disk allows, and ask the owner before deleting any.
- **C12 implemented** in local-llms `d3c6a94` (pushed). Codex's read-only review `remote-plans/local-llm-workspace-reuse-review_codex.md` finds it **not ready**: 6 major findings (R1 verification race, R2 symlink confinement, R3 new HF snapshot ENOENT, R4 disk admission before reuse, R5 partial destroyed by a wrong candidate, R6 copy fallback) and 2 minor.
- **Plan revised again** to sha256 `738778a0…`: C12 redesigned after R1–R8. `/shared` is untrusted and adopted only via a verified private copy, never hard-linked. Zero-copy in-place adoption happens only at the store's canonical path. Verification uses `O_NOFOLLOW` and fd-bound hashing with fstat before and after. Each candidate gets its own staging, and an existing `.partial` is never touched. The implementation still to follow.
- **C12 rework `d68c70f`, rechecked by Codex** (`remote-plans/local-llm-workspace-reuse-recheck_codex.md`): improved but **not acceptable**. R4, R5, R7 and R8 are resolved; R1, R2, R3 and R6 partly. New majors: F1 root swap, F2 FIFO block, F3 in-place HF state directory, F4 download stat-after-hash. F5 is minor.
- **Plan revised again** to sha256 `21db523a…`: C12 clarifications for F1–F5 (root anchoring, non-blocking opens, bound download verification, in-place snapshot `.state` creation, cancellable planning) and regression tests 15–20. The implementation is still to follow.
- **C12 F1–F5 fixes** pushed as local-llms `c22c7ab` (317/317 reported). **Commit-message deviation awaiting coordination:** `d68c70f` and `c22c7ab` each cite a `…_codex.md` filename in their body, against the workspace no-agent-mention rule. They are the only two affected commits across the three branches (checked here), with no attribution trailers. **The owner approved a message-only reword** (via the orchestrator, relayed by Codex). The implementer is the single remote writer, with `--force-with-lease=refs/heads/local-llm-multiarch:c22c7ab…`. Old history is kept at `refs/supervision/pre-message-reword-20260928T1935` and `supervision-snapshots/local-llms-pre-message-reword-20260928T1935_codex.bundle` (both Codex's; don't remove). **Done and validated (2026-09-28 22:40 +0300):** `d68c70f → 104ecee` and `c22c7ab → 70047bd`. Tip `70047bd` is on pgx and GitHub. `validate_reword.py` confirmed equal trees, the parent chain (`104ecee → d3c6a94`, `70047bd → 104ecee`), identical author and committer (name, email, dates), and that the only change is the trimmed `(plans: …_codex.md)` span. The empty `git diff c22c7ab 70047bd` and the scan of the whole branch show 0 agent mentions. `origin/main` is unchanged (`03697765`). This Mac's unchecked-out `local-llm-multiarch` was moved `c22c7ab → 70047bd` with a compare-and-swap `update-ref`. The old commits remain reachable through Codex's `refs/supervision/pre-message-reword-20260928T1935`, the Mac bundle, and pgx's `refs/backup/local-llm-multiarch-c22c7abe` plus a verified bundle. The pgx `commit-msg` hook strips attribution lines only, not other mentions.
- **Follow-up peaks** (raw `peak_drop_GiB`, r1/r2, preserved as inconclusive): 120b cache 8192 75.86/**82.93**, cache 4096 73.14/**78.27**, cache 1 73.38/**76.21**; 20b cache 8192 26.89/20.52, cache 1 23.64/17.37. The edge-step attribution check passing is not whole-method validation.
- **Follow-up matrix in progress.** Early data-quality check (`remote-plans/phase0-followup-data-quality_codex.md`): 2 runs provisional and 2 rejected (outside activity; an unattributed excursion). The previous 120b transient and margin figures are **withdrawn** (safety follow-up rev 3). Harness v4 attribution and quiet-host rules are proposed, with extra reruns. No constant is final.
- **Measurement status (about 21:45):** rule 3 marks all 11 completed runs **inconclusive**; external movement from other pgx users was above 0.5 GiB in every run. The app restart at 21:31 interrupted the matrix; it was marked and resumed as a single detached writer. **Decided (about 21:55, Codex under delegation; plan `3f6c1d10…` §9 item 10):** finish the matrix and the stop-latency checks, keeping every attempt; no abort on external movement; one rerun round with a quiet-host gate (non-runner memory steady within 0.25 GiB for 60 s, a configuration deferred after 30 min); the maximum of inconclusive or lower-bound peaks is **not** a conservative constant (masked peaks are lower bounds; **no worst-peak fallback**); no new margin or guard constant; other users are neither stopped nor contacted; no release acceptance without clean agreeing evidence or an independently justified upper bound. Harness v6 hashes checked on pgx and locally. Preserved worst peaks, all inconclusive (GiB): 120b 8192/4096/1 = 82.93/78.27/76.21 (the last a lower bound); 20b 8192/1 = 26.89/23.64; Qwen 128K×4 MTP off 35.13 (lower bound); Qwen 256K×1 MTP off 40.34 (new). The C12 recheck by Codex is active at `70047bd`.
- **Still open for the owner:** decisions 7 and 8, before Phase 4.
- **Owner decision, typed in this Mac session (2026-09-29, during the pgx outage): "Let's go with your recommendations."** It answers my summary of the Phase 0 results: llama-server from the prebuilt L1 release, `--load-mode dio`, no Ollama on arm64, `--cache-ram` kept at 8192 MiB and counted, and **MTP on for Qwen3.6**.
  - **Already in place, now confirmed by the owner directly:** decisions 1 (L1) and 2 (no Ollama on arm64), the `dio` default with the post-checksum page-cache drop, and `--cache-ram` 8192. The reviewed code agrees: `loadMode` default `'dio'` (`local-llm/src/runners/llamaServer.mjs`) and `cacheRamMiB: 8192` (`local-llm/src/controller/profiles.mjs`) on `recovery/local-llm-reviewed-20260928`.
  - **New: MTP on by default for Qwen3.6-35B-A3B** (`--spec-type draft-mtp --spec-draft-n-max 3`). Today `mtp` is a single boolean in the unified schema, `default: false`. gpt-oss has no MTP head, so this needs a per-model default. That design is engineering's, and Codex turns the decision into work.
  - **Costs to carry with it (Phase 0):** decode 66 → 95–99 tokens/s with greedy output identical to MTP off, but +1.2–3.3 GiB at ready, and 4 parallel requests took 37 % longer (55.0 → 75.5 s). How parallel use is handled is left to engineering.
  - **Interaction with the envelope rule (§9 item 10):** Qwen MTP-on configurations have Phase 0 values only (128K×4 34.86 GiB, 256K×1 34.80 GiB), and the Qwen seed entry is refused until measured (`7e7b2b5`). So a default-on MTP stays unavailable at admission until clean, agreeing evidence exists, as MTP off does.
  - **Not decisions:** vLLM (Phase 4, untested) and the x86 check (Phase 2) remain open work items, not choices.
  - **Relayed only here.** I did not message the Mac continuation or any pgx session.
- **Owner addition, typed in this Mac session right after (2026-09-29): "But let's add support for vLlm as well if someone wants to try it at runtime."**
  - **My reading:** vLLM becomes an opt-in runner on arm64/GB10 in scope now, rather than deferred to Phase 4. It is not the default; llama-server stays the default.
  - **What this pulls forward:** plan Phase 4 and B3:
    - the aarch64 lock closure (196 wheels, about 3.94 GB, installed on demand from the lock);
    - gcc and libpython for Triton;
    - vLLM leaving `incompatible` on the unified profile, with `--gpu-memory-utilization` computed from MemAvailable;
    - the gpt-oss correctness test for vLLM #37030;
    - the Box pid limit (A3) if needed;
    - acceptance on the Spark.
  - **Also brings forward** open decisions 7 (FlashInfer) and 8 (compile caches). Their answers are below, if the owner gives them.
  - **Needs GB10:** acceptance and any envelope measurement need pgx or another GB10. This Mac has no NVIDIA GPU.
  - **Owner's answers (AskUserQuestion in this Mac session), quoted:**

    | Question | Owner's answer | What it means |
    |---|---|---|
    | Decision 7, FlashInfer: keep it off, or lock the prebuilt wheels? | "In this case let's leave it alone for now" | Deferred. No FlashInfer work is part of this change. The owner chose neither option. I read that as not blocking vLLM's own artifactory probe either (not confirmed) |
    | Decision 8, compile caches: in the container, or `/data` with a manifest? | "Not relevant" | No decision needed for this change. Today's design (caches in the container) is unchanged |
    | Memory safety for vLLM on unified memory | **"Experimental opt-in"** | An admin can enable vLLM without a measured envelope. The option as presented: admission sizes it from vLLM's fixed memory fraction plus the host reserve and floor, and the 250 ms guard still kills it on a breach. This is a **deliberate owner exception** to §9 item 10's "unvalidated envelopes stay unavailable", for vLLM only. llama-server's rule is unchanged |

  - **Owner's clarification: "Similar to what we have now in local-llm."** Do it the way the current amd64 agent already does. There (local-llms `main` `0369776`, `local-llm/src/runners/vllm.mjs`), vLLM 0.30.0 is **installed on demand from the image's runner lock** (DS004: `runnerInstaller.mjs`, `runnerLock.mjs`, `scripts/runners/vllm.sh`), runs from its runnable copy, reads a Hugging Face snapshot, listens on loopback with a per-start key, and has `admitVllm` admission. For arm64 this means:
    - a vLLM entry in `runners.lock.arm64.json`, with the aarch64 closure;
    - the same on-demand install;
    - the unified-profile admission above, instead of `incompatible`.
  - **For Codex:** this is scope and policy only; the design belongs to engineering. Nothing was sent to the Mac continuation or to pgx.
- **Repair acceptance:** Codex independently verified and **accepted** the mirror repair for the tested guarantees in section 2a (about 19:55 +0300). Its live restore check saw clean trees, so it is clean-state evidence, not a new dirty-tree restore proof.
- **Now (Step 4, since about 17:45 pgx time):** the Phase 1 nested check.
  - The dev image `localhost/local-llm:dev` (`b14cdc2705ee`, 2.12 GB, built from `f10aeb5`) is proved.
  - The dev CLI sees the GB10.
  - The first test workspace was discarded. The image was not in the Box store, and UDP 7882 is taken by user `salboaie`, so it uses `--port 18088 --udp-port 17882`.
  - One logged deviation: a hand edit of the throwaway workspace's `agents.json`. It is being redone in an order that needs no hand edits.
  - **Recreated workspace** (`/home/research/gpu-test-workspace`, dev Ploinky): the Box has GPU wiring, and the nested agent container sees GB10 with only `--device ploinky.local/gpu=all`, unprivileged. C0 refuses Runs as intended. The GB10 memory findings reproduce in the nested container (23.5 GiB/s allocation). Its `local-llms` checkout has an **uncommitted, test-only** manifest edit (`container` → `localhost/local-llm:dev`), which is not in the dev clones and so not in `wip.patch`.

## 5a. New owner constraint (2026-09-28 19:06 +0300, typed by the owner in this Mac session)

> "One thing I did not mention is we don't care about backwards compatibility"

This was relayed verbatim to the engineering and review sessions, with the plan items it appears to touch. The list is my reading, for the owner or Codex to confirm:
- the implementation prompt's "existing amd64 users see no change in behaviour", and the Phase 2 byte-identical dedicated-profile gate (characterization and `cpu-cores` tests unchanged, golden `readGpu`, C1's unchanged query). x86 must still work, but need not behave identically.
- B1 reusing the amd64 digest `b6c79…`, versus rebuilding amd64 (decision 4);
- C6's catalog v3 registry migration and old-state readability;
- D's migration and retirement notes, tag and Docker Hub deprecation;
- Ploinky "x64 fingerprints unchanged".

Security, correctness and the unified-memory safety work are unaffected.

**The implementer has recorded it** (relayed by Codex; it supersedes the byte-identical dedicated-profile requirement), together with:
- decision 9: no 32k completions in the first release;
- decision 5, partly: the x86 gate is functional only, and the host is still to be named;
- the safety follow-up plan: a 120b re-download, `--cache-ram` 8192/4096/1 runs, buffer-based accounting plus a per-model margin, 250 ms sampling with SIGKILL on a proven floor breach, and stop-latency measurement.

## 6. Local continuation readiness (this Mac)

**What the Mac can and can't do:** it is Apple silicon arm64 with no NVIDIA GPU.
- **Can continue:** C1–C11, B1–B4 and D code, plus unit tests.
- **Cannot:** anything that needs GB10: the Phase 1 nested GPU check, Spark acceptance, vLLM and any new measurements. Those stay NVIDIA-only gates.

**Test baseline on this Mac** (run from `git archive` exports under the session scratchpad, so no checkout was changed):

| Repo | Result |
|---|---|
| local-llms `local-llm-multiarch` | 238/260 |
| local-llms `origin/main` | 233/255 |
| ploinky GPU grant (`local-llm-multiarch`) | 60/61 |
| ploinky GPU grant (`pgx/master`) | 53/54 |
| container-image-builds `image-definitions` | 22/22 |

- The **22 local-llms failures are identical on the branch and on main**. They come from the macOS environment (runner/helper process and signal tests, archive unpacking).
- The one ploinky failure, "bind-mount alias of the gpu-grants directory", **also fails on master**, because it tests Linux-only behaviour.
- The full ploinky unit suite has not been run on the Mac. It needs `PLOINKY_AGENTLIB_DIR` at the lock pin `ef515b2d`, quoted globs, and a symlink-free `TMPDIR`.

**Current local repo state (don't disturb):**
- `ploinky` has `fix/ploinky-cleanup-integrated-20260925` checked out and clean.
- `local-llms` has `main` checked out and clean.
- `container-image-builds` has `main` checked out, with only an untracked `.DS_Store`.

To continue without touching those checkouts, use worktrees:

```bash
git -C /Users/danielsava/work/file-parser/ploinky worktree add ../ploinky-local-llm-multiarch local-llm-multiarch
```

Then apply `repos/<repo>/wip/current/wip.patch` (verified) onto `base_head` from `wip/current/wip.meta.json` if the tree was dirty. Use `wip/best-effort/` only if it is newer and the verified one is too old, knowing it may mix states. Check it first with `python3 dgx-local-llm-plan-sync/verify_wip_restore.py <repo>` while pgx is still reachable. Read the implementation log and prompt before continuing.

**Local podman/Ploinky inventory:**
- podman machine `podman-machine-default` (applehv, 4 CPU, 6 GiB, 100 GiB disk, 6.2 GB used);
- one container, `ploinky-box-testexplorerfresh-d8f88a10b6e8` (up 8 h, the `~/work/testExplorerFresh` Explorer fixture);
- one image, `docker.io/assistos/ploinky-box:latest` (1.41 GB).

The owner allowed removing these, but **nothing is removed yet**, because nothing needs the space (180 GiB free on the Mac, 94 GB in the VM). At takeover, only if needed: `ploinky destroy` from `~/work/testExplorerFresh`, `mv` the fixture aside, then `podman rmi docker.io/assistos/ploinky-box:latest`.

## 7. Takeover trigger and who does what (agreed with Codex, 2026-09-28 about 19:10 +0300)

| Responsibility | Owner |
|---|---|
| Mirror, watch, snapshots, this handoff | **this Claude session** (single writer of `dgx-local-llm-plan-sync/`) |
| Starting any local continuation session if pgx is lost | **Codex**, under the owner's direct authorization in the Codex chat. This session does **not** launch one. |
| Engineering decision gates (delegated) | Codex |
| Final independent Codex review, the separate Opus 5.5 max review, comparison, and new Opus 5.5 high fix sessions | Codex. This session starts none. |

- **Signal for pgx loss:** SSH_FAIL from the watch (5 consecutive failed polls) and `remoteControlState` no longer `"on"` at a re-arm check.
- **On that signal**, this session records here the time of failure and the latest recoverable state: refs, `wip.patch` age, transcript sizes and times, Phase 0 mirror time. Codex's 5-minute supervisor reads it from here.
- **What survives an outage:**
  - pushed commits are on GitHub, now the normal case;
  - unpushed commits are in the local `pgx/*` refs;
  - uncommitted work survives only in the last verified generation, `repos/<repo>/wip/current/`, or as unverified evidence in `wip/best-effort/`.
