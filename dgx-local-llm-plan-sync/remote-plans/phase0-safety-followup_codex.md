Author: claude-code-opus-5-5 (the plan-review session), at the owner's request, relayed by the Codex coordinator
Date: 2026-09-28
Revision 2 (about 18:45): corrects errors in the first version (about 18:05), which engineering had already started working from. Every change is listed under "Corrections in revision 2" at the end and marked **[rev 2]** where it appears. The recommendations and their order are unchanged.
Revision 3 note (about 20:50): the gpt-oss-120b transient figures in section 4 are withdrawn. They are the "≈10.5 GiB non-cache transient", the single-prefill +6.3 GiB and the "≈13 GiB" np>1 margin. The Phase 0 prefill rise they rest on has the shape of an excursion that did not reproduce in the follow-up runs. See `plans/phase0-followup-data-quality_codex.md`, section 2, point 3. No margin may be derived until valid runs exist.
Scope: a read-only review of the Phase 0 memory evidence and of the unified-memory safety proposals in `plans/local-llm-multiarch-implementation-log.md` ("Phase 0 proposals"). I changed no source and did not edit the plan for this note. The recommendations went to the engineering session. Where I disagree with a proposal, I flag it here and leave the decision to the owner.

Owner decisions taken as given:
- L1 for the first arm64 image, with non-bit-identical greedy output across CUDA toolkits recorded as a changed correctness criterion.
- No Ollama on arm64; amd64 keeps it.
- Keep the measured 8192 MiB prompt-cache baseline until 4096 MiB is validated.
- Guard constants stay provisional until timing and headroom evidence exists.
- **[rev 2]** Added after the first version, by the owner via Codex:
  - Backward compatibility is not required, so no recommendation here needs a compatibility-preserving variant.
  - Approved, within the existing free-space floor: the pinned gpt-oss-120b re-download, and targeted, repeated, trace-logged measurements of the corner, the cache and stop latency.
  - Engineering is to use:
    - deterministic buffer accounting plus independently measured transient margins;
    - envelope keys that pin every memory-relevant parameter;
    - 250 ms sampling throughout in the unified profile;
    - an immediate, targeted kill on an actual floor breach;
    - measured stop and release latency before any constant is fixed.
  - The 8192 MiB admitted cache stays until smaller settings pass.
  - `oom_score_adj` is only a backstop. Userspace sampling cannot be promised to protect against arbitrary allocations by other processes on a shared host.

Evidence:
- `/home/research/phase0/results/serve/*`: 100 ms `/proc/meminfo` samples, server logs and JSON for 22 runs;
- `/home/research/phase0/tools/serve_check.py`;
- the local-llm source on the `local-llm-multiarch` branch (committed HEAD);
- llama.cpp b11159 sources at `6b790a9c`: `tools/server/server-task.cpp`, `server-context.cpp`, `server.cpp` and `common/arg.cpp`.

Analysis scripts are in `/tmp/claude-1002/-home-research-work/8bfd08cf-9225-4b6c-b766-b7917428a572/scratchpad/phase0-review/`.

## Verdict

The proposals point the right way:
- admission is the real control;
- the prompt cache gets an explicit bound that admission counts;
- PSI is never a trigger on its own;
- runners load with `dio`.

The evidence does not yet support the specific constants. Five problems need fixing before C2 and C3 are finalised:
1. The flat runtime margin is smaller than gpt-oss-120b's measured non-cache transient.
2. The guard cannot stop a load, because loads allocate in bursts of up to about 9.6 GiB per 250 ms.
3. "At ready" figures taken from MemAvailable deltas are noisy.
4. **[rev 2]** Several back-to-back Phase 0 runs were disturbed by 4–9 GiB swings in the host's baseline, and two proposal figures come from them.
5. The harness needs the measurement hygiene below.

None of these blocks Phase 1. Each needs one measurement or code change, listed below. The owner has approved them.

## 1. `serve_check.py` and failed parallel requests

- **The bug, and its fix.** In the version the Phase 0 runs used:
  - `one(i)` ran `post()` in a thread, so an HTTP 500 raised inside that thread never reached the main thread;
  - `outs[i]` stayed `None`, and the run still reported `ok: true`.

  `results/serve/20b-c128k-np4-cram-0.json` shows exactly this: `ok: true` with 0 of 4 timings, while its server log has 36 "failed to find a memory slot" lines. **[rev 2]** Engineering fixed it at 17:59, before my first version was written: `serve_check.py:133-135` now raises when any parallel result is empty. My first version wrongly said the run still reported `ok: true`.
- **Audit of the other runs, from their server logs.** Every other parallel run did finish all 4 requests (`predicted_n` 64 and `prompt_n` 26214 each):
  - `20b-c128k-np4-cram-default`;
  - `120b-c128k-np4-dio`;
  - `qwen-c128k-np4-mtpoff` and `qwen-c128k-np4-mtpon`;
  - after the fix, `20b-c128k-np4-cram-4096-v2` and `-8192-v2`.

  No proposal number rests on a silent failure.
- **Remaining gaps**, which engineering is now addressing (`serve_check2.py`):
  - (a) record each request's HTTP status, error body, `predicted_n == n_predict`, `prompt_n == per`, slot id, and start and end times;
  - (b) give the parallel threads a join timeout;
  - (c) prove the requests overlapped: their start and end times overlap and their slot ids differ;
  - (d) run at `-lv 4`. At the default verbosity, llama-server logs neither its buffer sizes nor any prompt-cache event (the 120b, Qwen and v2 logs have none; the two `-lv 4` runs, `cram-default` and `cram-0`, have both);
  - (e) timestamp the stop signal on the sampler's clock (see 6);
  - (f) **[rev 2]** measurement hygiene, see 2.

## 2. "At ready" from MemAvailable deltas is not a reliable number

**[rev 2] Drifted baselines.** Six runs ended with MemAvailable more than 1 GiB away from their start. All six ran back to back between 17:39 and 17:45.

| Run | End − start (GiB) |
| --- | --- |
| `120b-c32k-np1-none-cold` | +1.89 |
| `120b-c32k-np1-dio-cold` | −6.24 |
| `L2-120b-greedy` | −3.62 |
| `N-120b-greedy` | +8.74 |
| `20b-c128k-np4-cram-default` | −5.72 |
| `20b-c128k-np4-cram-0` | +5.63 |

- The change is entirely in MemFree; Cached and Shmem stay flat.
- The missing memory came back gradually during the following run, not as a release step. Each llama-server exit released its own memory within about 2 s (see 6).
- That points to another process on the host, not a delayed release. The `localhost/local-llm:dev` image was being built around then (created 17:49); engineering can confirm whether the build overlapped.
- The other 16 runs are within 0.8 GiB.

**[rev 2] Figures taken from drifted runs:**
- **gpt-oss-120b at 32K:** the proposal's "120b ctx 32k: 8.1 GiB" comes from `120b-c32k-np1-dio-cold` (−6.24). The same model and settings measured 64.54 GiB in `L2-120b-greedy`. `N-120b-greedy`'s 55.48 plus the ≈8.4 GiB that came back during its load gives about 64. So the overhead is about 5.2–5.5 GiB, not 8.1. The higher figure is conservative for admission, but it shows the method's error.
- **gpt-oss-20b envelope:** its 25.4 GiB comes from `20b-c128k-np4-cram-default` (−5.72). The clean explicit-8192 run (`cram-8192-v2`, +0.80) peaked at 20.30. The log reads the gap as "the prompt cache's share varies with what gets saved"; drift is the likelier cause.

**Clean baselines disagree too.** On two runs whose end and start agree within 0.3 GiB, 120b at 128K shows 67.70 GiB with 1 slot and 65.98 GiB with 4. The 4-slot figure should not be lower, so about ±1.7 GiB of noise remains even on a clean baseline.

**Recommendation** (the owner has since approved deterministic buffer accounting):
- Take the at-ready term from llama.cpp's own logged buffers, which are deterministic. At `-lv 4` these are the CUDA0 and CUDA_Host model, KV and compute buffers.
- Add a separately measured CUDA context and runtime constant.
- Use MemAvailable only as a cross-check.

**[rev 2]** For gpt-oss-20b at 128K × 4:
- the logged buffers sum to 15.73 GiB;
- the four runs at those settings measured 15.61–16.92 GiB at ready;
- the two clean v2 runs differ from each other by 1.23 GiB, although nothing differs between them at that point (the cache is still empty).

So the constant lies somewhere between about 0 and 1.2 GiB and has to come from clean repeats. My first version said it "fits about 1 GiB".

**[rev 2] Measurement hygiene for the new runs:**
- before each run, wait until MemAvailable is within about 0.5 GiB of the idle reference and steady (±0.25 GiB over 10 s), with a timeout that fails the run;
- keep sampling for at least 60 s after exit, and report the time until MemAvailable is back within 0.5 GiB of the start;
- sample the runner's own GPU memory next to MemAvailable, so drift can be attributed (`nvidia-smi --query-compute-apps=pid,used_memory` reports it on GB10, as the nested check showed);
- run no builds, downloads or large copies during memory measurements;
- reject any run whose end differs from its start by more than 0.5 GiB.

## 3. Prompt cache: how it works at b11159, and what accounting follows

From the source at `6b790a9c`:
- **It is a hard bound.** `server_prompt_cache::alloc` evicts the oldest entries before it allocates, so the cache stays within `--cache-ram` (`server-task.cpp:1750-1757`). A single state larger than the whole limit is skipped with "prompt state size … exceeds cache size limit …, skipping" (`:1731-1734`).
- **Idle slots are cleared even when their save is skipped.** With `--kv-unified`, idle slots are cleared on each new task whether or not the save succeeded (`server-context.cpp:2436-2451`, `[TAG_IDLE_SLOT_CLEAR]`).
- **[rev 2] Without `--kv-unified`, idle slots are saved but not cleared.** Each save is then a RAM copy on top of the KV (`server-context.cpp:1424-1430`).
- **`--cache-ram 0` turns the clearing off.** `--cache-idle-slots` is on by default but requires a nonzero `--cache-ram`, and `0` disables it (`server-context.cpp:1420-1423`; `arg.cpp:1729-1735`). That is why `cram-0` failed: the idle slot holding 118k tokens kept its cells in the unified KV. Any nonzero size keeps the clearing, so the size is a trade-off between memory and prompt reuse, not a correctness switch.
- **gpt-oss-120b's long state does not fit in 4096 MiB.** 18 full-attention layers × 8 KV heads × 64 × 2 (K and V) × 2 B = 36,864 B per token, so the idle 117,979-token slot is at least 4,148 MiB. **[rev 2]** That figure is a lower bound: the saved state also carries the SWA cells and context checkpoints. For gpt-oss-20b the log shows 2,769.5 MiB saved against 2,765.2 MiB of full-attention KV. The same arithmetic reproduces gpt-oss-20b's logged KV buffer exactly: 12 layers give 3072 MiB at 131072.
- **The 120b run did use the cache, although its log can't show it.** In `120b-c128k-np4-dio`, MemAvailable drops by a further 4.07 GiB within 3 s of the parallel launch, which matches that state being saved.

Recommendations:
- Counting `cacheRam` in full is correct. It is a hard bound, allocated synchronously in one burst when a new task starts. Keep it.
- To validate 4096 MiB, gpt-oss-20b alone isn't enough. `20b-cram-4096-v2` passed 4/4 with a peak of 19.76 GiB, against 20.30 for the clean explicit-8192 run (**[rev 2]** my first version compared it with the drifted 25.43). But the 20b's 118k state (about 2,770 MiB) fits in 4096, so this is only the cheap case. The 120b-class case must also be shown:
  - at `-lv 4`, the "exceeds cache size limit …, skipping" line appears;
  - all 4 parallel requests still succeed;
  - the peak drops by about 4 GiB.
- The owner approved the 120b re-download, and engineering started it at 18:10.

## 4. The flat runtime margin is too small for gpt-oss-120b with parallel requests (disagreement)

**[rev 3] The figures in this section are withdrawn** (see the note at the top). The recommendation still stands: measure the margin per model and per slot class, separately from the cache. The size of that margin is open.

**The proposal:** runtime margin = 4 GiB for np = 1 and 8 GiB for np > 1, on top of at-ready + `cacheRam`.

**What `120b-c128k-np4-dio` shows**, split by phase using its server-log timestamps. **[rev 2]** The at-ready baseline is now the harness value, 65.98, as in the log; my first version used 66.24 from my own phase split.

| Phase | MemAvailable drop from start | Above at-ready |
| --- | --- | --- |
| At ready | 65.98 GiB | — |
| Single 118k prefill | 72.25 GiB | +6.3 GiB of compute transient, with only one request running |
| Parallel phase | 80.51 GiB | +14.5 GiB, of which 4.07 is the cache save |

- That leaves about **10.5 GiB of non-cache transient**, above the 8 GiB margin.
- The one-slot run at the same context (`120b-c128k-np1-dio-cold`) rose only +0.6 GiB during the same prefill. So a 4-slot configuration costs more even for single requests.

**Why the check still passes.** The proposal's "82.0 ≥ 80.5" holds only because `cacheRam` (8) is added on top of the margin (8):
- With `cacheRam` 4096, the 118k save is skipped. The expected peak is ≈ 80.51 − 4.07 = 76.4 against a need of 59.03 + 7.0 + 4 + 8 = 78.0, which is 1.6 GiB of headroom, from one run.
- With a smaller `cacheRam`, for example 1024, the formula falls short: a need of 75.0 against a peak of about 76.4.

**Recommendation.** Make the margin a per-model, per-np-class figure, measured without the cache and kept separate from `cacheRam`, so the cache size can be tuned without breaking admission. The owner has since approved independently measured transient margins.
- Run with `--cache-ram 1`, which keeps idle-slot clearing but caches almost nothing.
- Take (peak − at-ready) × 1.25.

| Model and class | Estimate from these runs, to be confirmed |
| --- | --- |
| gpt-oss-120b np > 1 | ≈ 13 GiB (10.5 × 1.25) **[rev 2]** |
| np = 1, all three models | ≤ 1.6 GiB measured, so 4 GiB is fine |

The np = 1 figure includes the Qwen 256K prefills: 1.39 with MTP off and 1.57 with MTP on. The log's "≤ 0.7 with one request" misses these.

## 5. Rectangular context × parallelism envelopes

**The corners do dominate the rectangle**, with everything else fixed:
- the unified KV grows linearly with the context;
- the SWA cells grow with np (n_swa × np + ubatch);
- the measured transient grows with np (the 4-slot 120b prefill peak is 4 GiB above the 1-slot one at the same context);
- the prompt cache is bounded by `cacheRam`.

So measuring the maximal corner is a sound approach.

**Gaps:**
- (a) Each corner was run once, with one request pattern: a 90 % prefill, then 4 × 20 % at once.
  - At the 120b corner, add two patterns: np simultaneous cold prefills of ctx/np each, and np long generations.
  - Repeat each corner at least twice; clean baselines still differ by about 1.7 GiB.
- (b) The envelope key must pin every parameter that changes memory. The owner has approved this.
  - `-b` and `-ub` 2048, f16 K and V, `-fa on`, `--kv-unified`;
  - the load mode, the MTP flags and the `--cache-ram` value;
  - an explicit `-np`. llama-server's `-np` auto means 4 slots and `--kv-unified` (`server.cpp:156-161`).

  Anything outside the key is refused, as the plan already says.
- (c) The Qwen envelope is L-shaped: (≤ 131072 × ≤ 4) ∪ (≤ 262144 × 1). That's fine, but it needs to be encoded as two rectangles.
- (d) **[rev 2]** Re-derive the 20b envelope peak from clean runs; the current 25.4 is drifted (see 2).

## 6. Guard: sampling interval, floor and stop latency

**Load-phase bursts.** Using the 100 ms samples, I took the largest MemAvailable fall within any 250 ms window:
- 7.3–9.6 GiB in all 22 runs, on every model, including gpt-oss-20b (a 12.1 GB file). **[rev 2]** This was 7.4–9.6 and "12 GiB total" before the v2 runs.
- That is about 29–38 GiB/s: large buffers being committed as they are allocated.

**Consequence.** With an 8 GiB floor, a sample just above the floor can be followed by exhaustion before the next sample, so the guard cannot protect a load. Admission has to, using the load's known size (weights plus logged buffers, see 2). The kernel OOM killer, with the runner at `oom_score_adj` 1000, is only the backstop, as the owner put it.

**Ready-phase rates**, which can include prompt-cache saves:
- at most 1.08 GiB per 250 ms: 120b np4 and `20b-cram-4096-v2`; Qwen np4 reached 1.07;
- at most 4.16 GiB per 2 s: 120b np4. Qwen np4 reached 3.37–3.54, and 20b np4 2.07–2.99.

**[rev 2] Release on exit**, recomputed for every run: the time from the last low sample to within 0.3 GiB of the final value.

| Runs | Released | In |
| --- | --- | --- |
| gpt-oss-120b, 1 slot (5 runs) | 61.6–66.8 GiB | 1.0–1.4 s |
| gpt-oss-120b, 128K × 4 | 71.2 GiB | 2.1 s |
| gpt-oss-20b, 8K × 1 (6 runs) | 12.5–13.2 GiB | 0.5–0.6 s |
| gpt-oss-20b, 128K × 4 (4 runs) | 16.9–20.2 GiB | 0.9–1.9 s; one run took 4.9 s to get within 0.3 GiB |
| Qwen3.6 (6 runs) | 23.8–34.2 GiB | 0.6–1.0 s; one 128K × 4 run 2.1 s |

Not measured: the time from the signal to the start of exit, during a load and during active requests. The harness does not timestamp the signal.

**Recommendations** (the owner has since approved a, b and c):
- **(a) Sample every 250 ms in every phase, not 2 s when ready (disagreement with the proposal).** A prompt-cache save allocates up to `cacheRam` in one burst when a new task starts; the 120b step was 4.07 GiB. Reading `/proc/meminfo` costs microseconds.
- **(b) On a floor breach in the unified profile, SIGKILL the runner's process group immediately.**
  - Today's guard (`startMemoryGuard` and `stopForMemory` in `local-llm/src/controller/deployments.mjs`, committed HEAD) samples every 2 s while loading and every 10 s when ready. On a breach it sends SIGTERM, then SIGKILL only after the drain's 3 s grace (`DRAIN_RUNNER_GRACE_MS`). A starved runner has nothing to save.
  - **[rev 2] Overshoot, restated.** After a breach, the runner can allocate only until the kill lands:
    - the sampling delay (up to 0.25 s) plus the kill latency, at up to 4.3 GiB/s (1.08 GiB per 250 ms), comes to about 1.1–1.5 GiB;
    - on top of that, at most the rest of one prompt-cache allocation already under way;
    - the release that follows (0.5–2.1 s) does not add to the shortfall; it only sets how long other processes see it;
    - with SIGTERM and a 3 s grace, the runner can keep allocating for 3 s more: ≈ 6 GiB at the 2 s-window rate, or up to 13 GiB at the burst rate. The 8 GiB floor does not cover that.

    My first version put the bound at 1.1 + 4.3 × 1.4 ≈ 7.1 GiB, which wrongly counted the release time as allocation time. The conclusion is unchanged.
- **(c) Measure stop latency before fixing the constants.**
  - With 120b, send SIGKILL and SIGTERM (i) at about 50 % of the load and (ii) during a 4-way parallel prefill.
  - Record signal → exit → MemAvailable back, with timestamps on the sampler's clock.
- **(d) Keep the proposed 8 GiB floor for the ready phase, provisionally, once (a) and (b) are in.** Do not rely on any floor during a load.

## 7. Host reserve, other processes and PSI

- **Host reserve** of 16 GiB (`incompatible` above MemTotal − 16 = 103.6 GiB): consistent with the evidence. **[rev 2]** The idle host held 8.5–11.2 GiB that was not available, taken from the 16 clean run starts. The log says 9–12; my first version said 8–13.
- **[rev 2] Other processes on a shared host.** They draw from the same pool, and only the dynamic `insufficient-now` check and the guard can see them; the static reserve cannot. Section 2 shows such swings of 4–9 GiB within a minute on this host. As the owner stated, the guard and `oom_score_adj` are best effort: userspace sampling cannot promise protection against arbitrary allocations by other processes. `oom_score_adj` 1000 only makes the kernel pick the runner first.
- **PSI rule** (stop only if `full avg10` ≥ 50 and MemAvailable < 2 × floor): acceptable as a secondary condition.
  - `avg10` is a 10-second average and lags a fast exhaustion by seconds, so MemAvailable stays the working trigger.
  - Phase 0 saw avg10 at 14.2 and 28.5 with 45 GiB or more available, from page-cache reclaim alone.
  - If PSI must react faster, use deltas of its `total` counter per 250 ms sample.

## 8. Items for the engineering session, in order

1. Fix the harness as in 1, including the hygiene items in 2, and run all envelope and memory checks at `-lv 4`. (In progress.)
2. Re-run the gpt-oss-120b 128K × 4 corner at `--cache-ram 8192`, `4096` and `1`, plus the extra request patterns in 5(a), each twice. This validates 4096, separates cache from non-cache transient, and gives the per-model margin in 4. (Approved; the download started at 18:10.)
3. Measure stop latency as in 6(c). (Approved.)
4. Carry the approved changes into C2 and C3:
   - the at-ready term from logged buffers (2);
   - a per-model, per-np margin independent of `cacheRam` (4);
   - 250 ms sampling in every phase, and SIGKILL of the process group on a floor breach (6);
   - an envelope key that pins every memory-relevant parameter (5b).

   Fix the constants only after items 2 and 3.
5. Keep 8192 MiB as the admitted cache size until item 2 passes, as the owner decided.
6. **[rev 2]** Re-derive the figures that came from drifted runs from clean ones: the 20b envelope peak and the 120b 32K overhead (2).

## Agreements (no change requested)

- L1 as decided.
- No Ollama on arm64.
- Loading with `dio`, plus `posix_fadvise(DONTNEED)` after the checksum.
- Counting an explicit `--cache-ram` in admission.
- PSI never the sole trigger.
- The 16 GiB host reserve.
- Refusing everything outside the measured envelope until Phase 5.

## Corrections in revision 2

1. **Section 1.** The harness fix (17:59) predates my first version, which wrongly said the run still reported `ok: true`. The remaining gaps are unchanged, and a hygiene item is added.
2. **Section 2, new.** Six back-to-back runs had 4–9 GiB baseline drift. Two proposal figures come from them: the 120b 32K overhead of 8.1 (about 5.2–5.5 from the other runs) and the 20b envelope peak of 25.4 (the clean run gives 20.30). Measurement hygiene is added.
3. **Section 2.** For the at-ready constant, "fits about 1 GiB" becomes "between about 0 and 1.2 GiB": the four 20b runs measured 15.61–16.92 against 15.73 GiB of logged buffers.
4. **Section 3.**
   - 4,148 MiB is a lower bound for the 120b state.
   - The cited ranges become `server-context.cpp:1420-1423` and `2436-2451`, and the non-unified case (`1424-1430`) is added.
   - The 4096 run is compared with the clean explicit-8192 run (20.30), not the drifted 25.43.
5. **Section 4.** The at-ready baseline is now 65.98 (the harness value), not 66.24 (my phase split). So the non-cache transient is 10.5 GiB (was 10.2), the single-prefill rise is 6.3 GiB (was 6.0), and the 120b np > 1 margin is ≈ 13 GiB (was 10–13).
6. **Section 6.**
   - The load-burst range is 7.3–9.6 (the v2 runs added).
   - The 20b size is a 12.1 GB file, not "12 GiB total".
   - The ready-phase rates include the v2 runs.
   - The release table is recomputed for every run; the first version had only N-120b, 20b 0.5–0.6 s and Qwen 0.5–1.1 s.
   - The overshoot reasoning is corrected (release time is not allocation time).
   - The current guard's actual timings are cited from the source.
7. **Section 7.** The idle-host figure is 8.5–11.2 GiB (was 8–13). The wording on other processes follows the owner's statement.
