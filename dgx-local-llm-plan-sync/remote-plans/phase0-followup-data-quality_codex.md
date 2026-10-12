Author: claude-code-opus-5-5 (the plan-review session), at the owner's request, relayed by the Codex coordinator
Date: 2026-09-28. Revision 1 about 20:50; revision 2 about 21:05, after Codex's review of revision 1 and engineering's activity log. Both were written while the follow-up matrix was still running.
Scope: an early, lightweight data-quality check of the completed runs in `/home/research/phase0/results/followup/`.
- I read the per-run JSON, the 100 ms memory CSVs, the server logs, `annotations.json`, `tools/serve_check2.py` (v3) and `tools/followup.sh`.
- I did no GPU work, hashing, copying or measurement, and changed no raw record.
- Nothing here finalises a constant.
- The greedy-smoke EOS correction (`annotations.json`) is a request-validity issue and is kept separate from memory validity.

## 1. What the harness checks today (v3)

- **Baseline:** it waits until MemAvailable varies by no more than 0.25 GiB over 10 s, for up to 300 s. The baseline is the mean of that window. It is not compared with an idle reference, and a long wait is not flagged.
- **`drift`:** set when |baseline − the last sample 60 s after exit| > 0.75 GiB. It looks only at the last sample.
- **No attribution:** the runner's own GPU memory (nvidia-smi) is sampled, but only per-phase maxima are kept. The runner's host memory (RSS) is not sampled. So in-run memory cannot be split into the runner's own and other processes'.

## 2. Evidence from the completed runs

Post-exit offset = baseline − MemAvailable at the given time after the server exited. Positive means memory is still missing.

| Run | Requests | Baseline (GiB avail, spread, wait) | At ready | Phase peaks: prefill / parallel / coldparallel / longgen | Offset at exit, +2 s, +5 s, +10 s, +60 s | Harness `drift` |
| --- | --- | --- | --- | --- | --- | --- |
| 120b cram8192 r1 | ok (derived; greedy EOS annotated) | 109.53, 0.11, 20 s | 67.10 | 67.81 / 71.80 / 75.68 / 75.86 | −0.14, +0.05, −0.08, −0.06, +0.61 (slow decline from +30 s) | false |
| 120b cram4096 r1 | ok (derived; greedy EOS annotated) | 109.86, 0.14, 30 s | 67.31 | 67.99 / 68.61 / 71.77 / 73.14 | **+1.18, +1.33, +2.19, +1.76**, +0.63 (back within 0.5 only at +26 s) | false |
| 120b cram1 r1 | ok | 109.33, 0.18, 10 s | 66.64 | **73.17** / 73.38 / 69.12 / 70.11 | **+1.17, +1.27, +1.27, +1.18, +1.65** (never back) | true |
| 20b cram8192 r1 | ok | 109.00, 0.19, **281 s** | 16.27 | 17.06 / 20.01 / 23.01 / 26.89 | +0.16, +0.01, +0.55, +0.74, +0.98 (swings ±1 GiB) | true |
| 20b cram1 r1 | running | — | — | — | — | — |

What these show:
1. **The last-sample rule gets it wrong both ways.**
   - `120b cram4096 r1` is not flagged, yet 1.2–2.2 GiB was missing for 26 s after exit. Something outside the runner overlapped the end of the run.
   - `20b cram8192 r1` is flagged, although its release was complete 2 s after exit. The later swings came after the run.
   - `120b cram8192 r1` also declines after +30 s: post-exit drift, which does not touch the run itself.
2. **`120b cram1 r1` has an in-run excursion that does not reproduce.**
   - During the last half of the prefill, the drop climbs from 67.0 to 73.2 GiB. It passes +1 GiB at 20:19:18 and stays there into the parallel phase. At 20:20:03 it falls back by about 5.7 GiB at once, 20 s into the parallel phase.
   - The two other 120b runs process the same 117,964-token prefill on the same slot, with the same 29 context checkpoints of 4.5 MiB, and stay flat, within 0.7 GiB of at-ready.
   - The runner's GPU memory (nvidia-smi) is 65,724 MiB during that phase in all three runs, and Cached is flat. So the extra memory is not the runner's GPU allocations. The runner's RSS was not sampled, so it cannot yet be attributed.
   - It falls between engineering's two harness updates of that session (v2 at 20:17:07, v3 at 20:20:27). **[rev 2] Engineering's exact tool-call timestamps (`results/followup/engineering-activity.json`) contradict this hint.** Nothing of theirs ran at 20:19:18: there was a file edit at 20:17:55 and a `tail` at 20:19:47, and a light `grep` of library files, which only fills the page cache, ran at 20:20:29–36, after the rise began. Nothing of theirs ran during Phase 0's 17:34–17:40 run either. The excursion is **unattributed**, and a genuine but intermittent model or driver transient is a live hypothesis. Another user (`salboaie`) had short-lived `node` processes of 1.1–3.2 GiB at 20:44. That is circumstantial, not attribution.
   - ~~Until it is attributed, this run is contaminated.~~ **[rev 2]** Until it is attributed, the run is *inconclusive*: its peaks stay in the worst case (section 3).
3. **This retracts a figure in my Phase 0 follow-up.**
   - Phase 0's `120b-c128k-np4-dio` run shows the same shape: a gradual rise of about 6 GiB during the prefill, and a sudden drop of about 9 GiB during the parallel phase.
   - Section 4 of `phase0-safety-followup_codex.md` built the "≈10.5 GiB non-cache transient" and the "≈13 GiB margin for 120b np>1" on it. Both stay withdrawn as derived constants. **[rev 2]** Withdrawn does not mean dismissed: Phase 0's 80.51 GiB peak stays the preserved worst case for 120b 128K×4 at 8192 MiB until the excursion is attributed.
   - The clean-looking parts of the new runs suggest a much smaller transient without the cache. For example, `120b cram4096 r1`'s parallel phase is +1.3 GiB above at-ready, and its 118k state was skipped as predicted (`skipped_exceeds_limit: 1`). But no margin may be derived until valid runs exist.
4. **`20b cram8192 r1` began on a busy host.** Its baseline needed 281 s of the 300 s limit to settle, and the ±1 GiB swings after exit show the activity continued. Engineering reported a full test-suite run (310/310) during the matrix; `node --test` runs test files in parallel.

## 3. Validity rules

### Rule version 1 (about 20:50; superseded)

Rule v1 had four conditions:
- (a) the stress requests passed;
- (b) the baseline settled within 60 s, within 0.5 GiB of an absolute idle reference of 109.4 GiB;
- (c) memory was back within 0.5 GiB by exit + 10 s;
- (d) unattributed memory stayed within ±0.5 GiB of at-ready.

The evidence was the maximum over valid runs. Engineering implemented it (`tools/memory_validity.py`, `memory-validity.json`, rule_version 1) and also rejected runs that overlapped its own logged activity.

Codex found three flaws, and I agree with all of them:
- **An absolute idle reference.** A benign, long-lived process that changes the host's idle level would reject every later run.
- **A residual used as an acceptance test before its meaning was shown.**
- **A "maximum over valid runs" that drops rejected runs' peaks.** That selects the lower peaks, and could discard a genuine intermittent transient.

### Rule version 2 (current, prospective)

Rule v2 applies to every classification from now on. The runs already done are re-classified under it below, and each record states its rule version and raw sha256. Request, performance and correctness success stay separate from memory evidence: `annotations.json` covers the greedy criterion, and memory classes never depend on it.

1. **Quiet windows, taken per run.** Each run has its own pre-run window (flat within 0.25 GiB over at least 10 s, as now) and a post-run window (flat for at least 10 s, reached within 60 s of exit).
   - The run's net change is post minus pre. It must be at most 0.5 GiB, or be matched by a recorded contributor, such as another user's anonymous memory that changed by the same amount.
   - Both windows record their contributors: per-user anonymous memory, including the `research` user's own processes other than the runner, and other GPU processes.
   - A wait of more than 60 s is recorded as "host busy before run". It is not a rejection by itself.
   - There is no absolute idle reference.
2. **Release.** Memory must be back within 0.5 GiB of the pre-run window by exit + 10 s, with no excursion above 0.75 GiB inside that window.
3. **Exclusive lock.** The harness holds an exclusive (LOCK_EX, `flock -x`, never shared) lock on `/home/research/phase0/.memlock` from before the eviction and baseline to the end of the post-run window.
   - Engineering's tests, builds, hashing and pushes, and the Codex C12 re-check, take the same exclusive lock.
   - Other users' workloads are not stopped. They are recorded, and a run they disturb is deferred or re-run.
4. **Classes.**
   - **Clean:** items 1–3 hold, and the directly measured external memory stays within 0.5 GiB of the pre-run window throughout. External memory means other processes' anonymous memory and other GPU processes. A clean run counts as a sample. A pre-v4 run can be clean only if no logged activity overlaps it.
   - **Inconclusive:** any failure of items 1–3 without positive attribution, and any unexplained in-run excursion above 0.75 GiB. It does not count as a sample, but **its phase peaks stay in the configuration's worst case**.
   - **Contaminated:** only with positive evidence. That means measured external growth matching the excursion in time and size, or a logged activity plausibly large enough to explain it. The evidence is written into the record. Only the part of the peak that the evidence explains may be excluded from the worst case.
5. **The residual is diagnostic only.** The residual is the drop minus the runner's GPU memory minus the runner's RssAnon and RssShmem. It is reported for each phase, but decides no class until the method is validated (section 5).
6. **Enough evidence per configuration.** Two clean samples whose at-ready values and every phase peak agree within 0.75 GiB. The configuration's worst case is the maximum over its clean and inconclusive samples, plus any unexplained remainder of contaminated ones. A margin derived from the clean samples must cover that worst case, unless the owner accepts a documented attribution.

## 4. Classification under rule v2

Raw sha256 values are the first 16 characters. Engineering's file has the full hashes.

| Run (raw .json / -mem.csv / -server.log) | Rule v1 class (engineering) | Rule v2 class | Why | Peaks kept in the worst case |
| --- | --- | --- | --- | --- |
| Phase 0 `serve/120b-c128k-np4-dio` (5a79310c… / 787f207e… / c949d092…) | — | Inconclusive | Unattributed prefill rise (+6 GiB) and a 9 GiB drop mid-parallel; no activity of engineering's | 80.51 (at 8192 MiB, default) |
| 120b cram8192 r1 (504e2775… / 47733ef6… / cb562ebc…) | Valid, without attribution | Inconclusive (strict reading, adopted about 21:00) | Release complete at exit; drift only after +30 s; no overlapping activity. But before v4 there is no directly measured external memory, so it cannot be clean. That is engineering's rule-v2 reading, and I accept it | 75.86 |
| 120b cram8192 r2 (harness v3, 20:41:21–20:48:37) | — | Inconclusive | Post-exit offsets grew from 2.35 GiB at exit to 7.82 GiB at +60 s (20:48:37), a large and growing external load at and after the end. The Codex recheck's tests (bounds 20:42:16–20:48:19) overlap it, but can't explain the 7.82 GiB, which came after they ended. Other users are candidates. Not attributed | **82.93** (coldparallel, 20:44:52): the preserved 120b cram8192 worst case |
| 120b cram4096 r1 (23031474… / 66c92117… / ad47a3a3…) | Rejected | Inconclusive | 1.2–2.2 GiB missing until +26 s after exit, unattributed | 73.14 |
| 120b cram1 r1 (4653ac12… / 4282b96d… / c8666a03…) | Rejected | Inconclusive | Unattributed +6.3 GiB in-run excursion; 1.2–1.7 GiB missing after exit; the later `grep` is too light to explain it | 73.38 (prefill 73.17) |
| 20b cram8192 r1 (a44cd661… / 19c22b72… / b17f6088…) | Rejected | Inconclusive | Engineering's serial `node --test` (20:30:18–20:33:00) overlapped its phases; 0.72 GiB missing at +10 s; baseline wait 281 s | 26.89 |
| 20b cram1 r1 (975e7188… / ae36882d… / 5bccaa71…) | Rejected | Inconclusive | Engineering's serial full suites and push (20:35:26–20:37:45) overlapped its baseline and load; 2.36 GiB missing at +10 s | 23.64 |

Two notes on these classes:
- Engineering's serial tests do explain why the 20b runs can't be clean samples. They do not attribute a specific excess: a serial test process takes about 0.1–0.3 GiB, less than the offsets seen.
- No run above is contaminated, because none has positive attribution.
- The 120b cram8192 worst case (82.93 GiB from r2) is above the proposal's 82.0 GiB need. Unless v5 runs with attribution show the runner's own peak, and the owner accepts a documented attribution, the margin must cover it.

**Reruns.** The minimum stays the same, and matches engineering's chained `tools/followup-reruns.sh`:
- 120b cram4096 r3 and cram1 r3;
- 20b cram8192 r3 and cram1 r3;
- 120b cram8192 r3 only if r2 is not clean or disagrees with r1.

The worst-case rule adds no runs. It does keep the inconclusive peaks open until they are attributed or the owner decides.

## 5. Attribution: method and validation before any use as a criterion

Harness v4 was installed at 20:46:41, between runs. It samples every 500 ms:
- the runner group's VmRSS, RssAnon and RssShmem;
- per-PID GPU memory;
- other users' total RssAnon.

These are the checks I recommend before the residual may decide anything:
1. **Coverage without overlap.** At ready, compare the runner's GPU memory with the logged CUDA0 buffers plus a context constant (for 120b, about 65.4 GiB of buffers against 65.6–65.7 GiB observed). Compare the runner's RssAnon with the logged CUDA_Host buffers plus its heap.
   - If the GPU figure also counts the pinned CUDA_Host memory, the at-ready residual turns negative by about that size (1.1 GiB for 120b), which shows double counting.
   - File-backed RSS stays out, because it is reclaimable and inside MemAvailable. RssShmem stays in.
2. **A stable at-ready residual.** The at-ready residual should agree within 0.3 GiB across repeats of one configuration, and scale sensibly between models. It stands for driver and kernel overhead.
3. **External memory measured directly, for everyone.** Record `AnonPages`, `Shmem` and `Unevictable` from `/proc/meminfo` in the same loop iteration. External anonymous memory is then AnonPages minus the runner's RssAnon. This also covers the `research` user's own other processes (Claude and Codex sessions, test runs), which a per-other-user total misses.
4. **Time alignment.** Read `/proc/meminfo` inside the same attribution loop and timestamp both reads. Record each `nvidia-smi` call's start and end, and use the midpoint. Measure the lag at the big load step.
5. **A controlled check.** Under the lock, between measurement runs, a small helper allocates and touches about 2 GiB of anonymous memory for 20 s with no runner loaded. External memory must show +2 GiB at the right time, and the runner fields and residual must not move. This uses no GPU.

Until checks 1–5 pass, the residual and "unattributed" are diagnostic only.

A worst case may be removed from the envelope only in two ways. Either the measured external memory accounts for it, with the evidence recorded. Or the owner decides, on a documented argument.

## 5a. Revision 3 (about 21:45): assessment against the current raw data

`memory-validity.json` was generated at 20:55:23. It predates five of the eleven completed runs: 120b cram4096 r2, 120b cram1 r2, 20b cram8192 r2, 20b cram1 r2, and Qwen 128K×4 MTP off, cache 8192, r1. Its worst cases for the smaller caches (≈73 GiB) are **stale**. It must be regenerated from all raw runs.

**Worst case per configuration** (maximum over every sample, including inconclusive ones and matching Phase 0 peaks; peak drop in GiB):

| Configuration | Samples | Worst case | Clean samples |
| --- | --- | --- | --- |
| 120b 128K×4, cache 8192 | r1 75.86 (pre-v4), r2 82.93 (v3, growing external load after exit), Phase 0 80.51 | **82.93** (r2, coldparallel) | 0 |
| 120b 128K×4, cache 4096 | r1 73.14, r2 78.27 (v4) | **78.27** (r2, longgen) | pending |
| 120b 128K×4, cache 1 | r1 73.38, r2 76.21 (v5; post-run +2.72 GiB above baseline) | **76.21** (r2, coldparallel), a lower bound: see below | 0 |
| 20b 128K×4, cache 8192 | r1 26.89, r2 20.52 (v5; parallel phase dips 1.05 GiB below at-ready), Phase 0 25.43 | **26.89** (r1, longgen) | pending |
| 20b 128K×4, cache 1 | r1 23.64, r2 17.37 (v5) | **23.64** (r1, longgen) | pending |
| Qwen 128K×4, MTP off, cache 8192 | r1 35.13 (v5; post-run +0.55), Phase 0 33.38 | **35.13** | pending |
| Other Qwen configurations | Phase 0 only: 128K×4 MTP on 34.86; 256K×1 MTP off 31.30, MTP on 34.80 | Phase 0 values | 0 |

"Pending" means that engineering's rule-v2 tool must classify the v4 and v5 samples against the full criteria.

Four further points:
- **External releases can hide a peak.** A run whose MemAvailable ends above its baseline, or where a phase dips below at-ready, had memory released by someone else during the run. Its drops, and its peak, may be **understated**. Examples: 120b cram1 r2 (−2.72 GiB) and 20b cram8192 r2. Such a peak is a lower bound. It must never be used to argue that a configuration needs less, and such runs are not clean.
- **Attribution is not validated.** In check 4e, the edge steps pass. But the whole-window identity fails: the residual ranges over 0.76 GiB (0.69 during the hold) against the 0.3 GiB criterion. The method is therefore **not validated**, so under rule v2 as of now:
  - residuals, and any "matched contributor" derived from the attribution data, cannot make a run clean or contaminated;
  - no peak may be excluded as external on that basis;
  - measured external movement may still deny clean status, which is conservative, since the peaks are kept;
  - the edge-step pass is evidence for step detection only, not for the method as a whole.
- **Consequence for the constants, flagged without deciding them.** Every preserved 120b worst case exceeds the Phase 0 proposal's need formula with an 8 GiB runtime margin for np>1 (weights 59.03 + at-ready 7.0 + cache + 8):
  - 82.93 against 82.0 at cache 8192;
  - 78.27 against 78.0 at cache 4096;
  - 76.21 against about 74.0 at cache 1.

  The at-ready values seen are 7.6–10.2 GiB above the weights, not 7.0. Either clean samples will explain these worst cases, or the margins and at-ready terms must grow.
- **Interrupted run.** `qwen-c256k-np1-mtpoff-cram8192-r1` was aborted at 21:31:42 by the session restart, after its prefill. It has no result. Its partial raw files are kept, and it is not evidence. Engineering resumes only the missing and interrupted runs, under new attempt file names (Codex's instruction).

## 5b. Revision 4 (about 21:45): rule 3 applied, and a decision needed

- **Rule 3 is applied** (`memory-validity.json` rule_version 3, 21:42:07, from all 11 runs). It adopts section 5a:
  - there is no contaminated class;
  - no peak is reduced or excluded;
  - external movement can only deny clean status;
  - a peak is marked as a lower bound when memory ends at least 0.5 GiB above the baseline, or when a phase drops at least 0.5 GiB below at-ready.
- **The result: all 11 runs are inconclusive.** Every v5 run saw external movement above 0.5 GiB from other users, up to 8.6 GiB during 120b cram1 r2. The worst cases match section 5a. The lower bounds are 120b cram1 r2, 20b cram8192 r2 and Qwen 128K×4, MTP off, cache 8192, r1.
- **Why the whole-window identity fails (check 4e, evaluation 3).** When another user released about 5 GiB, AnonPages fell at once, but MemAvailable came back 0.5–0.6 GiB short and closed the gap over about 15 s. A kernel accounting lag is one possible cause; that stays a hypothesis (section 5c, item 6). Either way, the identity has not held within 0.3 GiB across large external swings, which supports keeping the residual diagnostic only.
- **The run itself:** the resumed matrix runs as one detached writer (PID/SID 621181) with byte-identical tools. The interrupted attempt is marked, and its retry is `-r1-a2`. One automatic rerun round follows, capped by engineering.
- **Decision for the owner or Codex.** On this shared host, clean pairs may not come without help. Before more rerun rounds are spent, I recommend:
  1. **Quiet-host deferral.** Start a run only after the external memory (every user's AnonPages plus Shmem, excluding the runner) has been steady within 0.25 GiB for at least 60 s.
  2. **Abort and re-queue.** If external movement exceeds 0.5 GiB during a run, stop it, keep the raw files as an attempt, and queue it again. This uses the attribution data only to decide whether to repeat a run, never to accept or exclude evidence.
  3. **Quieter hours.** Run the reruns at night.

  If clean pairs still do not appear, the constants must be derived from the preserved worst cases (conservative), and the owner decides that explicitly.

## 5c. Revision 5 (about 21:55): the owner's decision (Codex, under the owner's delegation)

1. **Finish the running and missing functional matrix and the stop-latency checks, keeping every attempt.**
2. **No abort on external movement.** A functional run is not aborted because an external-memory proxy moves by 0.5 GiB. Full stress coverage and every high peak are kept. Such an attempt is marked inconclusive and re-queued only within the bounded round. Unvalidated attribution must never become a selection filter that hides model peaks. (This declines my section 5b item 2.)
3. **One automatic re-run round, with a prospective quiet-host scheduling gate.**
   - Before a run starts, the observed non-runner memory must be steady within 0.25 GiB for 60 s. After that, the functional and validity requirements are unchanged.
   - The gate is a scheduling heuristic. It validates no residual, and it does not make a run clean.
   - Prefer a measured quiet interval; night is not assumed to be quiet.
   - If no quiet interval appears within 30 min, defer that configuration and report it.
   - Release the lock while waiting, and check the quiet baseline again after taking the lock.
   - Every measurement and test holds the exclusive `.memlock` for its whole required window.
   - No further automatic rounds are approved. The owner reassesses after the remaining functional and stop evidence and this gated round.
4. **Other users' workloads are neither stopped nor contacted.**
5. **Constants and acceptance.**
   - **[correction]** The maximum of inconclusive or lower-bound peaks is **not** a conservative constant, because a masked lower bound is not an upper bound. My section 5b sentence "the constants must be derived from the preserved worst cases (conservative)" is withdrawn.
   - The worst observed peaks are kept, with their unresolved uncertainty.
   - Envelopes for unvalidated models and configurations stay unavailable.
   - No release acceptance is claimed until there is clean agreeing evidence, or an independently justified upper-bound method.
   - No new margin or guard constant is approved.
6. **[correction]** The delayed recovery of MemAvailable after a large external release is established. That it comes from a kernel accounting lag (sections 5b and 5c) is a **hypothesis**, until evidence separates it from other contributions that were not sampled.
7. **[qualification]** `setsid`/`nohup` reduces the runner's exposure to an ordinary exit of its parent. It does not prove that the run survives termination of the host, a logout or its cgroup.
8. The independent C12 recheck is active, at exactly `70047bd`. It reports 317/317 under the lock and is waiting for the lock to run its fixtures. There is one reviewer.

Relayed to engineering, the only owner of the queue and the harness, at about 21:55, with a request for acknowledgement and for versioned scheduling changes.

## 5d. Tracking (about 21:50)

- **Engineering acknowledged the decision in section 5c at 21:46:33.** Codex confirmed this independently from engineering's transcript.
- **Harness v6** was installed at 21:47:44, between runs, as a scheduling change only. I verified the hashes:
  - `serve_check2.py` `c00de363…`, with `HARNESS_VERSION = 6`;
  - `attribution.py` `bf903041…` (only the lock helpers changed);
  - `quietgate.py` `d1c59c22…` (new);
  - `followup-reruns.sh` `8015dd3a…`;
  - `stop_latency.py` unchanged at `7d3b7f4e…`.

  Every run now waits 5 s before asking for the lock, so a queued waiter such as the C12 recheck fixtures gets it between runs. Grants are logged in `logs/memlock.log`. The quiet gate applies only to the single rerun round.
- **A new preserved peak.** `qwen-c256k-np1-mtpoff-cram8192-r1-a2` finished with every request passing. At ready it was 29.81 GiB (Phase 0: 29.91), and its **prefill peak was 40.34 GiB**, 10.5 GiB above at-ready, where Phase 0 saw 31.30. After exit, memory was still 2.12 GiB short, and it came back within 0.5 GiB only at +50 s. The run is inconclusive, and 40.34 GiB is kept as the worst observed peak for that configuration.
- **Relayed** the decision and the lower-bound correction to the local recovery owner ("Anthropic Messages API server support") at about 21:50.

## 5e. Quiet-gate timeout defect (Codex, about 22:00; relayed to engineering)

This is an implementation correction to the approved bounded scheduling decision. It changes neither the plan nor C12, and it authorises no extra rounds. I confirmed it by reading the code:

- **Unbounded wait for the lock.** `quietgate.py` (`d1c59c22…`) line 49 calls `attribution.memlock()`. When the lock is taken, that path (`attribution.py` `bf903041…`, lines 45–54) sleeps for the yield and then blocks in `flock(LOCK_EX)` with no deadline.
- **Late passes.** Line 50 gives the under-lock recheck a fresh deadline (`time.time() + recheck_s + 5`), so the gate can return `passed` after `budget_s`. Codex's deterministic stub reproduction: budget 5 s and a 10 s lock wait returned passed at t=12, with no unlock.
- **Other gaps.** The deadlines use wall-clock time, and there is no `try/finally` to release the lock on errors.

**Required fix,** before the re-run round:
- one monotonic end-to-end deadline, covering the quiet wait, the yield and lock contention, and the recheck under the lock;
- lock acquisition bounded by the remaining budget;
- no `passed` after the deadline;
- the lock released on deferral and on errors;
- unchanged blocking-lock behaviour for measurement callers that have no deadline.

**Tests:**
- pass;
- contention past the deadline;
- a quiet interval that arrives near the deadline;
- release and reacquisition by another process;
- Codex's stub case, now as a desired-behaviour assertion.

The tests use scratch locks and fake time, and run under `flock -x .memlock` on the host. The active matrix processes and the scripts they run are not to be touched. Changed files are installed by atomic rename, the v6 copies are archived, and the new hashes and test evidence are reported.

## 6. Status of constants

Nothing is finalised. The admission constants, transient margins, envelope peaks and guard constants all wait on three things:
- every configuration has two clean, agreeing samples;
- the preserved worst cases are covered or attributed;
- the stop-latency runs have been reviewed.
