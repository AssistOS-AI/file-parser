---
name: dgx-local-agent-planning
description: "Status, owner decisions and roles for the local-llm multi-arch plan (Ploinky agent local-llms/local-llm on this DGX Spark), started 2026-09-28"
metadata:
  node_type: memory
  type: project
  originSessionId: e95c870c-8d4a-46a7-bacf-21525480837e
  modified: 2026-09-28T17:52:23.664Z
---

On 2026-09-28 the owner settled on a single agent, `local-llms/local-llm`, running on this DGX Spark (GB10, sm_121, aarch64, 119.6 GiB unified memory, CUDA 13.0, driver 580) through a multi-arch OCI image. amd64 reuses digest `b6c79…`; arm64 is a new build. The agent picks a dedicated or unified hardware profile at run time. The ten legacy shared-image agents are deleted.

**Files**, all in /home/research/work/plans/:
- the plan, `local-llm-multiarch-plan.md` (sha 3f6c1d10… since about 21:55 on 2026-09-28, which added §9 item 10 on memory evidence and acceptance; before that 21db523a…; before that 738778a0…, 714b391f…, 48d896f0… and b5a95376…). Its §9 lists the owner's post-Phase-0 decisions and every contract they change. Items 6 and 7 are C12 (reuse model files already in the workspace) and model retention. Item 8 maps Codex's C12 review (R1–R8, `plans/local-llm-workspace-reuse-review_codex.md`) to actions. The C12 trust model: /data is operator-trusted, /shared is untrusted; nothing from /shared is hard-linked, only copied privately and verified; in-place adoption at the canonical store path is the zero-copy path; stat checks detect accidents only;
- two reviews, `…-review-claude-code-opus-5-5.md` and `…-review-codex-gpt-6_codex.md`;
- `local-llm-multiarch-implementation-log.md`, owned by the engineering session. It holds the owner's decisions table and the Phase 0 data;
- `phase0-safety-followup_codex.md`, this session's targeted Phase 0 memory-safety review (revision 2 corrects the first version openly).

**Roles:**
- The engineering session ("Local LLM multiarch engineering plan") implements, using dev clones in /home/research/dev and scratch in /home/research/phase0.
- The owner's Mac session ("Anthropic Messages API server support") relays owner messages.
- The Codex coordinator supervises through the owner, and owns the later independent final review and fix cycle. It is not a Claude session and does not appear in ListAgents. Relay to it by giving the user a paste-ready block; the owner pastes Codex's messages into this session.
- This session does targeted reviews and edits the plan only when the owner allows it, after coordinating ownership with engineering. It never touches source.

**Owner decisions (2026-09-28):**
- **Decision 1:** L1 (the ggml-org b11159 CUDA 13.4 prebuilt), recorded as a changed correctness criterion because greedy output is not bit-identical across toolkits.
- **Decision 2:** no Ollama on arm64; amd64 keeps it.
- **Decision 5:** the x86 functional gate runs on ubuntu-codex (RTX 3060 Laptop 6 GiB, driver 595.91.07, about 26 GiB RAM). Codex runs it from the Mac; this host does not reach it. It uses a gpt-oss-20b procedure sized for 6 GiB, and records real constraints or rejections, never an invented pass.
- **Decision 6:** the model set is gpt-oss-20b, Qwen3.6-35B-A3B MTP and gpt-oss-120b, with a 20 GB free floor.
- **Decision 9:** 32k-token completions are not a first-release requirement.
- **No backward compatibility.** This supersedes the byte-identical and unchanged-test requirements. Both architectures must still work, and deliberate breaks are recorded in specs.
- **Memory safety:**
  - admission = logged buffers + measured constant + per-model transient margin + `--cache-ram`, with 8192 MiB admitted until smaller settings pass;
  - 250 ms sampling throughout, and an immediate process-group SIGKILL on a floor breach;
  - constants stay provisional until stop and release latency are measured;
  - oom_score_adj is only a backstop.

**Model files:** keep every downloaded model until the owner says the work is concluded ([[keep-models-until-conclusion]]; relayed to engineering on 2026-09-28 at about 20:00).

**Follow-up data quality (2026-09-28, rev 2 at about 21:05):** recorded in `plans/phase0-followup-data-quality_codex.md`.
- Rule v2 (after Codex's review): quiet windows are taken per run (no absolute idle reference); the lock is exclusive (flock -x); the residual is diagnostic until validated.
- Classes are clean, inconclusive and contaminated. A run is contaminated only with positive attribution evidence. The worst case is the maximum over clean and inconclusive peaks, so lower peaks are never selected and Phase 0's 80.51 GiB stays the 120b worst case.
- Engineering's activity log cleared it of the 120b excursions.
- Engineering runs harness v4 (lock plus attribution) and chained reruns.
- My Phase 0 120b transient figures stay withdrawn as derived constants, but their worst cases are preserved.
- Codex rechecked the C12 rework at `d68c70fe` (`plans/local-llm-workspace-reuse-recheck_codex.md`). R4, R5, R7 and R8 are resolved. F1–F5 remain: root anchoring, a FIFO non-blocking open, the HF in-place `.state` directory, download binding, and cancellable planning. Plan §9 item 9 covers them, with tests 15–21; engineering is fixing them.
- 120b cram8192 r2 (v3) peaked at 82.93 GiB with a large external load after exit. It is inconclusive and the preserved worst case, above the 82.0 GiB need.
- Lesson: don't attribute a spike to someone's work without their exact timestamps.

**History correction (about 21:40 on 2026-09-28):** Codex, under the owner's delegation, approved a message-only rewrite of local-llms `d68c70fe` and `c22c7abe`, removing the `_codex` report file names from their messages.
- Engineering is the single writer: backup bundle and ref first, exact `--force-with-lease=refs/heads/local-llm-multiarch:c22c7abe…`, verification recorded.
- The relay is queued to the offline engineering session, and also written to `plans/local-llms-history-correction-approval_codex.md`.
- I then forward the old→new SHAs and the evidence to Codex and to the local recovery owner (assumed to be the Mac session).
- The measurement matrix died at 21:31:42 in the session restart, during qwen c256k r1. Its partial files are kept; engineering resumes it.

**History correction done (about 21:40 on 2026-09-28).** Engineering is the single writer; I verified the result independently.
- local-llms `d68c70fe` → `104ecee7`, and `c22c7abe` → `70047bd7`. Trees are unchanged; the new remote tip is `70047bd`.
- Backups: the pgx bundle at `/home/research/dev/backups/…c22c7abe-pre-reword….bundle` and ref `refs/backup/local-llm-multiarch-c22c7abe`, plus Codex's Mac bundle.
- Mapping forwarded to the local recovery owner, "Anthropic Messages API server support", which Codex confirmed.
- Codex's next C12 recheck targets `70047bd`.
- Engineering now messages me from `bridge:session_01WCv2psgmn5Ak8pghwQj3xE`. A local session [3ace1c] also claimed its name; I held a message rather than confirm an unverified identity.
- Revision 3 of the data-quality assessment (current worst cases: 120b 8192 82.93, 4096 78.27, cache1 76.21) is in section 5a.

**Rule 3 (about 21:45 on 2026-09-28):**
- All 11 follow-up runs are inconclusive; other users moved up to 8.6 GiB during runs.
- The matrix resumed as detached single writer PID 621181, with one capped rerun round.
- I recommended quiet-host deferral and abort/requeue on external movement, or a night window, before more rounds (data-quality section 5b). The owner or Codex decides.

**Owner decision via Codex (about 21:55 on 2026-09-28):**
- Finish the matrix and the stop checks.
- One quiet-gated rerun round: non-runner memory within 0.25 GiB for 60 s; defer after 30 min; lock released while waiting.
- No abort on external-memory movement, and no attribution-based filtering.
- Max of inconclusive or lower-bound peaks is NOT a safe constant. Unvalidated envelopes stay unavailable, and there is no release acceptance without clean agreeing evidence or a justified upper-bound method. No new constants.
- "Kernel lag" is only a hypothesis.
- setsid/nohup doesn't prove survival.
- The C12 recheck is active at `70047bd`.
- Relayed to engineering via the bridge, with delivery unconfirmed; the decision is also recorded in the plan and in data-quality revision 5.

**Tracking (about 21:50 on 2026-09-28):**
- Engineering acknowledged the decision.
- Harness v6 (scheduling only) was installed at 21:47:44, and I verified it: serve_check2 c00de363, attribution bf903041, quietgate d1c59c22, followup-reruns 8015dd3a; stop_latency 7d3b7f4e unchanged. It adds a 5 s lock yield and logs/memlock.log.
- New preserved peak: Qwen 256K×1 MTP off, 8192, r1-a2 at 40.34 GiB (inconclusive).
- The decision and the lower-bound correction were relayed to the Mac local recovery owner.

**Quiet-gate defect (about 22:00 on 2026-09-28):** Codex found that v6's quietgate.py blocks in flock without a bound and gives the recheck a fresh deadline, so it can pass late.
- Relayed the fix to engineering: one monotonic deadline end to end, bounded lock, no late pass, release on errors, and tests.
- It must be fixed before the rerun round. It is not a plan change.
- Awaiting new hashes and test evidence to forward to Codex.

**Pending for this session:** review engineering's new safety measurements (gpt-oss-120b 128K×4 corner at `--cache-ram` 8192/4096/1, stop latency, the new harness `serve_check2.py`) when engineering pings.

**Why:** the phases follow from these decisions: Ploinky patch, then llama.cpp MVP, then multi-model, then vLLM.

**How to apply:**
- Check the plan sha before any plan edit, then coordinate with engineering before editing.
- Record owner decisions as changed contracts; flag disagreement rather than silently altering the plan.
- Correct your own earlier reports openly, with a corrections list, never silently.
- On this shared host, memory measurements need settled baselines: back-to-back Phase 0 runs drifted by 4–9 GiB.

Related: [[same-branch-name-across-repos]], [[dgx-host-tooling]]
