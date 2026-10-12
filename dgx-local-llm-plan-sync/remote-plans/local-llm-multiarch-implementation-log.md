# Implementation log: local-llm multi-arch plan

Implementer: Claude Code (claude-opus-5-5), session started 2026-09-28.
Plan: `/home/research/work/plans/local-llm-multiarch-plan.md`, sha256 `b5a9537626c71dce8974f30fcc31b2ff54bee61719a25bf31176a5f66393da94` (matches the reviewed version named in the implementation prompt).

Plan revision: at about 18:30 on 2026-09-28 the plan-review session updated the plan (authorised by Codex for the owner) to sha256 `48d896f0643c82f16754daef4deca3ad25883ca170b4283acf2f7dfec227fa6e`, adding §9 "Owner decisions after Phase 0 (changed contracts)". Work from then on follows that version.

## Decisions taken by the owner

| # | Decision | Date | Evidence shown |
| --- | --- | --- | --- |
| 3 | LM Studio stays amd64-only (settled before this session) | — | plan §6 |
| 4 | amd64 reuses `b6c79…` in the first index (settled before this session) | — | plan §6 |
| 6 | Phase 0 model set: gpt-oss-20b MXFP4, Qwen3.6-35B-A3B MTP UD-Q4_K_XL (`unsloth/Qwen3.6-35B-A3B-MTP-GGUF` @`5bc3e238`), gpt-oss-120b MXFP4 (`ggml-org/gpt-oss-120b-GGUF` @`238abdd2`), downloaded sequentially; peak about 81 GB; 20 GB free floor | 2026-09-28 | draft disk table in the Step 2 report |
| — | Stop (not destroy) the Explorer deployment for Phase 0 | 2026-09-28 | same report |
| — | One branch name, `local-llm-multiarch`, in every repository for this plan (relayed from the owner by the plan-review session). Renamed locally: ploinky `arm64-gpu-discovery` → `local-llm-multiarch` (head `338a3c56`), local-llms `gpu-memory-unknown` → `local-llm-multiarch` (head `ee175b9`); container-image-builds already used it. Nothing pushed; commits unchanged. Earlier rows of this log name the old branches. | 2026-09-28 | — |
| — | Reclaim disk (relayed from the owner by the plan-review session, 2026-09-28 ~16:10): that session ran `ploinky destroy --delete-cache` on the stopped Explorer deployment (Box `ploinky-box-work-287e15733c26`, `.ploinky/box/images` 13 GB, `.ploinky/box/dependencies`), and deleted `.data/roboTeamAgent` (8.3 GB) and a stale `/var/tmp/container_images_storage2654024115`. **The Explorer deployment is destroyed, not just stopped.** Kept: `plans/`, the rest of `.ploinky` (repos, config), other agents' small data, the ploinky-box image in host podman storage. This session did not run those deletions. | 2026-09-28 | — |
| — | Delete each Phase 0 model as soon as its benchmarks are done, and log it; keep only what later steps need (e.g. one small model for the Phase 1 nested check) | 2026-09-28 | — |
| 1 | **L1** (ggml-org b11159 CUDA 13.4 arm64 release) for the first arm64 image. Recorded as a **change to the original correctness criterion**, not an unchanged gate pass: greedy output is not bit-identical across CUDA toolkits (13.4 vs 13.0); accepted on the op tests (16445/16445 both), perplexity and throughput evidence. | 2026-09-28 | Phase 0 proposals; decided by Codex under the owner's delegated authority, relayed by the owner in this session |
| 2 | **Omit Ollama** from the first arm64 image; clear "not available on this platform" behaviour; amd64 Ollama support unchanged. | 2026-09-28 | same |
| — | Unified load: `dio` plus a post-checksum `posix_fadvise(DONTNEED)` where supported. | 2026-09-28 | same |
| — | Prompt cache: admission counts an explicit `--cache-ram` bound. Keep the measured 8192 MiB baseline until a 4096 MiB setting passes full long-context and parallel requests plus peak-memory checks. | 2026-09-28 | same |
| — | Fix the Phase 0 harness so any failed parallel request fails the run. | 2026-09-28 | same |
| — | The host reserve (16 GiB), guard floor (8 GiB) and PSI rule are **provisional safety candidates**, not validated: they need measured load/ready stop latency and allocation headroom, including concurrent requests and delayed samples. PSI alone never stops a healthy load with high MemAvailable. | 2026-09-28 | same |
| — | Push feature branch `local-llm-multiarch` in the three dev repos after checkpoint commits (gh 2.101.0 authenticated as skutner on pgx); no default-branch pushes, no image publication. No AI co-author or attribution lines in any commit. | 2026-09-28 | same |
| — | **No backwards compatibility** ("we don't care about backwards compatibility", the owner, relayed by Codex in this session; supersedes the byte-identical dedicated-profile requirement). Shared code, query/output formats, schemas and old behaviour may change where it simplifies the design; no v2 registry migration, alias paths or unchanged characterization tests kept only for compatibility. Specs and meaningful tests follow the new contract; deliberate breaking changes are recorded. x86/amd64 and arm64 must keep working; security, correctness and memory gates stay. | 2026-09-28 | owner via Codex |
| 9 | 32,000-token answers are **not** a first-release requirement. Keep coherent explicit completion budgets and deadlines; the long-completion expansion is later work. | 2026-09-28 | owner via Codex |
| 5 (partial) | The x86 host gate is a functional validation, not proof of byte-identical old behaviour; the host is still to be identified. | 2026-09-28 | owner via Codex |
| 5 | x86 functional gate host: **ubuntu-codex** (SSH user skutner; x86_64; RTX 3060 Laptop 6144 MiB; driver 595.91.07; ~26 GiB RAM available; 398 GiB disk; podman; existing workspace `/home/skutner/work/file-parser`). Codex coordinates the isolated run from the Mac; no credentials move, pgx does not reach it. This session prepares exact feature SHAs, the image identity and capacity-appropriate gpt-oss-20b llama.cpp/Ollama steps (partial offload on 6 GiB, or a pinned smaller model plus a truthful large-model rejection); the original large-model gate is reported passed only if it actually runs. | 2026-09-28 | owner via Codex |
| — | Safety follow-up (`plans/phase0-safety-followup_codex.md`, plan-review session): re-download the pinned gpt-oss-120b into the scratch area after checking the 20 GB floor, keep it until the review measurements are verified. Run the 128K × 4-slot corner with `--cache-ram` 8192, 4096 and 1 (MiB), clean baselines, `-lv 4` trace logs, repeated cold parallel prefills and long generations, per-request success and overlap evidence. Derive deterministic buffer accounting plus a measured per-model, per-parallelism transient margin separate from the cache. Guard: 250 ms sampling throughout unified operation and an immediate process-group SIGKILL on a proven floor breach; graceful stops otherwise. Measure signal-to-exit and memory-release latency during load and active requests before accepting any floor. Admission covers the full known allocation; the guard is not presented as protection against load bursts or other users' allocations. Keep 8192 MiB admitted until lower settings pass. Coordinate the focused safety review with the plan-review session. | 2026-09-28 | owner via Codex |
| 10 | Retire the legacy translation/reranking and CPU-only agents with D. No replacement or migration layer. Preserve stored models and user/workspace data, keep the coding-style rules, fix spec/HTML/navigation references, document exactly which services disappear. D stays separately reviewable (its own commit; this session keeps it as a separate commit on `local-llm-multiarch`, since every repo uses that one branch name); no default-branch merge. Historical tags and Docker Hub deprecation are not needed. | 2026-09-28 | owner via Codex |
| — | The x86 handoff may stay a draft until the candidate is final; give the pinned ready revision when testable. Stop-tool findings (SIGTERM hang, memory still falling after SIGKILL) are leads, not proof: establish process-group/child termination and actual GPU and system memory recovery on a stable baseline before accepting guard constants, send the evidence to the plan reviewer, and keep those gates pending; SIGKILL alone is not proof of safe reclamation. | 2026-09-28 | owner via Codex |
| — | **Keep every downloaded model file until the work is concluded**, and delete only after the owner confirms (relayed by the orchestrator session, ~19:50). Covers gpt-oss-20b, Qwen3.6-35B-A3B MTP, gpt-oss-120b and any model verified later. Replaces "delete each Phase 0 model once its benchmarks are done" (which cost two re-downloads) and extends the ~18:50 rule. Disk is not a constraint (366 GB free at 19:50; the three models ≈98 GB). Suggestion noted: later steps (e.g. Spark acceptance) reuse the verified files (hard links) instead of downloading again, where the agent can adopt a pre-placed, sha256-checked file. | 2026-09-28 | owner via orchestrator |
| — | Model retention refined (owner, via orchestrator): "If we have space we should keep these models until no longer needed for the implementation." Keep them while disk allows; ask the owner before deleting any, whether for space or because one is no longer needed. | 2026-09-28 | owner via orchestrator |
| C12 | New feature (owner: "If the model exists in the workspace we should use it instead of downloading it over and over again."), added to the plan as C12 in Phase 2 by the orchestrator. Before a download, look for the pinned artifact in the agent's store and in the workspace's shared directory `/shared/models` (host `<workspace>/.data/shared/models`); match only on the pinned identity (size and sha256; every shard; every snapshot file), regular files only; adopt by hard link (same filesystem) or copy, then verify the agent's own copy; record device/inode/size/mtime/ctime and re-verify before a load if they changed; Delete weights removes only the agent's link or copy and reports the space actually freed; gguf and hf-snapshot only; DS002 records the lookup order; tests for link, copy, wrong hash, symlink, changed ctime. | 2026-09-28 | owner via orchestrator |
| — | A2 stays in the Ploinky branch (owner answered "Yes" to the combined question; recorded as keeping A2, accepting the one-time Box replacement on R580 hosts) | 2026-09-28 | same report |

## Deviations from the plan

None yet.

## Step 1: Baseline (2026-09-28)

### Dev clones (`/home/research/dev`)

| Repo | Origin default branch head | Installed copy | Ahead of installed? | Feature branch |
| --- | --- | --- | --- | --- |
| ploinky | `master` `3f8ffa58` (2026-09-28 14:08, "refine webchat messages") | `/home/research/work/ploinky` `ed86558b` | 1 commit ahead (webchat only; no change to `gpuGrant.mjs` or its test) | `arm64-gpu-discovery` |
| local-llms | `main` `03697765` | `.ploinky/repos/local-llms` `03697765` | no | `gpu-memory-unknown` (C0) |
| container-image-builds | `main` `95ba10a2` | `.ploinky/repos/container-image-builds` `95ba10a2` | no | `local-llm-multiarch` |
| AchillesAgentLib (test dependency only, not changed) | checked out at Ploinky's lock pin `ef515b2d` | — | — | — |

Commit identity in the dev clones: `skutner <sava.dumitru.daniel@gmail.com>` (repo-local config), matching recent history. None of the three repositories' recent `git log` has AI trailers, so none are added (local-llms forbids them; ploinky and container-image-builds match their history).

### Tests

| Repo | Command | Result |
| --- | --- | --- |
| local-llms | `node --test 'local-llm/tests/*.test.mjs'` (repo root) | 255 tests: 253 pass, 2 fail. Both failures are the known LM Studio ones (`lmstudio.test.mjs:335`, `:494`: `--threads is 12, expected 18`). |
| ploinky | `node --test tests/unit/ploinkyBoxGpuGrant.test.mjs` | 54/54 pass |
| ploinky | `PLOINKY_TEST_AGENTLIB_DIR=/home/research/dev/AchillesAgentLib node --test --import ./tests/helpers/agentlibTestContract.mjs tests/unit/*.test.*` (as `tests/test_all.sh` runs them) | 4058 tests: 3976 pass, 63 fail, 19 skipped. Failures are pre-existing and environmental (mostly `mcp-sdk` not installed: no `npm install` was run in the clone). The list of failing test names is kept at `/home/research/dev/ploinky-unit-baseline-failures.txt` to compare after changes. |
| container-image-builds | `node --test tests/image-definitions.test.mjs` | 22/22 pass |

### Host at start

| Item | Value |
| --- | --- |
| `df -h /` | 916G size, 738G used, 132G avail (85 %) |
| `free -g` | 119 total, 11 used, 58 free, 51 buff/cache, 108 available |

## Step 2: Phase 1 code (2026-09-28)

### A1 + A2, Ploinky (`/home/research/dev/ploinky`, branch `arm64-gpu-discovery`, based on `origin/master` `3f8ffa58`)

| Commit | Item | Summary |
| --- | --- | --- |
| `f5d95fc0` | A1 | `parseLdconfigCache(output, arch)` keeps entries whose ldconfig flags (trimmed, compared per flag) include `x86-64` for x64 or `AArch64` for arm64; `ldconfigArchFlag` refuses any other architecture as `PLOINKY_BOX_GPU_DISCOVERY_FAILED` (so a grant leaves a stale marker). `discoverNvidiaGpu({ arch = process.arch })`. Comment at the old `:232` fixed. |
| `338a3c56` | A2 (optional, separate commit) | `libnvidia-nvvm70.so.4` is an optional library; its real file may be named exactly by its soname (soname-specific exception to the version-name check). |

Tests (`tests/unit/ploinkyBoxGpuGrant.test.mjs`): the fixture host now names its architecture (`fakeHost({ arch })`, default x64) and passes it to discovery; before this, the x64 fixtures silently depended on the test machine (with A1 alone and no fixture change, 38 of 54 failed on this arm64 host). New tests: arm64 discovery and wiring round-trip (same devices, same in-Box mounts, byte-identical CDI spec, marker equal except fingerprint, create args add only devices/ro binds/label, observed back as the same wiring); mixed caches (x86-64, hard-float, soft-float, plain libc6 entries listed first); whitespace and extra flags (`OS ABI`, `hwcap`); arm64 missing libraries and driver mismatch; unsupported architectures (`ia32`, `ppc64`, `riscv64`, `s390x`, empty, undefined, null, prototype names) including the stale-marker outcome; default = host architecture; NVVM 7.0 (bound, spec mount, exact-name exception, other names refused, exception limited to that soname).

| Command | Result |
| --- | --- |
| `node --test tests/unit/ploinkyBoxGpuGrant.test.mjs` | 61/61 pass (54 before + 7 new) |
| Full unit suite, as in the baseline | 4065 tests: 3983 pass, 63 fail, 19 skipped. The failing set is identical to the baseline (diffed by name). |
| Real host, read-only: `discoverNvidiaGpu()` from the dev clone | 3 device nodes (`/dev/nvidia-uvm` is 497:0 here), 6 libraries from `/usr/lib/aarch64-linux-gnu` incl. `libnvidia-nvvm70.so.4`, `/usr/bin/nvidia-smi`. `discoverNvidiaGpu({ arch: 'x64' })` refuses: `libcuda.so.1 is not in the ldconfig cache`. |

Risk recorded for the owner: A2 changes the discovered set on every host that has `libnvidia-nvvm70.so.4` (all R580 drivers, x86 included), so the wiring fingerprint changes and an existing GPU-wired Box is replaced once at its next `start`/`restart`/`update`. A1 alone leaves x64 fingerprints unchanged.

### C0, local-llms (`/home/research/dev/local-llms`, branch `gpu-memory-unknown`, based on `origin/main` `03697765`)

| Commit | Summary |
| --- | --- |
| `ee175b9` | `readGpu` requires `memory.total/used/free` to match `^\d+(\.\d+)?$`; otherwise returns `{ available: false, name, driverVersion, reason }`, reason naming the GPU and the values. Numeric hosts: same query, same snapshot. DS003 "Hardware snapshot" records the rule. |

Tests: new `local-llm/tests/gpu-memory-unknown.test.mjs` (golden dedicated snapshot on an RTX 3060 Laptop line, exact argv of both queries, compared as JSON; GB10's exact line; eight non-numeric variants; admission for llama.cpp, ik_llama.cpp, Ollama and vLLM, for the seed model and 500/400/300 GiB sources: all `incompatible` with the reason) and one controller test (Run refused as `admission_incompatible` for llama.cpp, Ollama, vLLM, with no download and no runner start). Without the `hardware.mjs` change, 3 of the 4 new tests fail and the golden one passes.

| Command | Result |
| --- | --- |
| `node --test 'local-llm/tests/*.test.mjs'` | 260 tests: 258 pass, 2 fail (the two known LM Studio thread-count tests, fixed later by C9) |

## Step 3: Phase 0, host-level (started 2026-09-28)

Scratch directory: `/home/research/phase0` (outside `/home/research/work`).

### Explorer stopped

`/home/research/work/ploinky/bin/ploinky stop` from `/home/research/work` (12.6 s). Box `ploinky-box-work-287e15733c26` exited; not destroyed (disk not needed per the table). `free -g` available 108 → 110 GiB.

### Link speed

Downloads run at about 6–7 MB/s (gpt-oss-20b measured 6 MB/s while the L2 builder was pulling; the earlier Explorer pull was 4.57 GB in 620 s). gpt-oss-120b (63.4 GB) therefore takes about 2.5–3 h.

### Benchmark protocol, declared before any benchmark ran

- Builds: L1 (ggml-org b11159 `ubuntu-cuda-13.4-arm64` + its cudart archive), L2 (B2 source build in the pinned CUDA 13.0.2 builder), N (playbook-native reference: host CUDA 13.0.88, gcc 13.3, `-DGGML_NATIVE=ON -DGGML_CUDA=ON -DGGML_CURL=ON -DGGML_RPC=ON -DCMAKE_CUDA_ARCHITECTURES=121a-real`). Deviation from the playbook: N is built from the b11159 commit `6b790a9c`, not unpinned master, so all three compare the same source; `LLAMA_BUILD_NUMBER/COMMIT` are also set on N so its `--version` matches.
- Command, identical for every build: `llama-bench -m <model> -ngl 99 -b 2048 -ub 2048 -fa on -t 10 -p 2048 -n 32 -d 0,32768 -lm none,dio -r 5 -o jsonl`, run through `gpurun` (oom_score_adj 1000), one build at a time, nothing else on the GPU.
- Metrics: prefill (pp2048) and decode (tg32) tokens/s at depth 0 and 32768.
- Tolerance: L1 is "within tolerance" of L2 when, for every model × test × depth, mean(L1) ≥ 0.97 × mean(L2). A cell whose 5 samples have a coefficient of variation above 3 % is re-run once before judging. N is a reference only (baseline armv8-a CPU code), not a ceiling.
- Correctness: every build must answer the same fixed prompt identically with greedy decoding (llama-server `/completion`, `temperature 0`, `top_k 1`, `seed 1`, `n_predict 128`, same ctx and slots). If texts diverge, the first divergence position and the top-token agreement are recorded, and a divergence confined to near-tied logits is not a failure only if all three builds diverge from each other similarly; any build that emits garbage or fails fails.

### Builds

| Build | How | Result |
| --- | --- | --- |
| L1 | `llama-b11159-bin-ubuntu-cuda-13.4-arm64.tar.gz` (145,505,332 B) and `cudart-…-arm64.tar.gz` (552,521,395 B) from `github.com/ggml-org/llama.cpp/releases/download/b11159/`; both sha256 match the plan (`258c9dc7…`, `34d8602d…`). cudart/cuBLAS/cuBLASLt `.so.13` copied next to the binaries. | 864 MB extracted (both archives). `llama-server --version`: build 11159, commit 6b790a9c2, GNU 14.2.0. RUNPATH `$ORIGIN`; `ldd libggml-cuda.so` resolves everything from `$ORIGIN` except `libcuda.so.1` (host). `cuobjdump --list-elf libggml-cuda.so`: 144 cubins each for sm_75, sm_80, sm_86, sm_89, sm_90, sm_120a, **sm_121a**. CPU variants shipped: armv8.2_1/2/3, armv8.6_1/2, armv9.2_1/2; `llama-bench --help` loads `libggml-cpu-armv8.6_2.so` on this CPU. CUDA initialises on driver 580 (13.4 build under minor-version compatibility): `found 1 CUDA devices (Total VRAM: 122502 MiB) … NVIDIA GB10, compute capability 12.1, VMM: yes`. |
| N (playbook-native reference) | host CUDA 13.0.88, gcc 13.3.0, cmake 3.28.3; b11159 commit; `cmake -DGGML_NATIVE=ON -DGGML_CUDA=ON -DGGML_CURL=ON -DGGML_RPC=ON -DCMAKE_CUDA_ARCHITECTURES=121a-real -DLLAMA_BUILD_NUMBER=11159 -DLLAMA_BUILD_COMMIT=6b790a9c2`; `--target llama-server llama-bench -j 12` | 2 m 33 s. Configure: "ARM -march/-mcpu not found, -mcpu=native will be used" (confirms the review: baseline CPU code); one CPU backend `libggml-cpu.so`. build 11159, GNU 13.3.0. 144 sm_121a cubins. |
| L2, first attempt | `podman build` of `/home/research/phase0/l2/Containerfile` exactly as B2 (builder `nvidia/cuda@sha256:450d1155…`, fetch by full commit and check, `rm -rf .git`, gcc-14, `121a-real`, `GGML_NATIVE=OFF GGML_CPU_ALL_VARIANTS=ON GGML_BACKEND_DL=ON GGML_RPC=OFF`, `LLAMA_BUILD_NUMBER=11159 LLAMA_BUILD_COMMIT=6b790a9c2`, RUNPATH `$ORIGIN`, targets llama-server and llama-bench) | Built in 12 m 43 s (incl. the 3.93 GB builder pull). build 11159, GNU 14.2.0, 144 sm_121a cubins, 8 CPU variants (incl. armv8.0_1). **But** configure found NCCL in the CUDA devel image (`Found NCCL: /usr/lib/aarch64-linux-gnu/libnccl.so`) and `libggml-cuda.so` NEEDS `libnccl.so.2`, which is not copied and not on the host: the CUDA backend would not load. Other configure notes: OpenSSL not found (HTTPS disabled; fine, the agent downloads, not llama-server), "Git repository not found" (expected; identity comes from the -D values), `ggml commit: unknown` (ggml's own label, not what `--version` reports). No "manually-specified variables were not used" warning. |
| L2 | same plus `-DGGML_NCCL=OFF` | (in progress) |

**Deviation / addition to B2 (recorded, not a contradiction of the plan):** the L2 recipe needs `-DGGML_NCCL=OFF`, as the existing ik_llama.cpp builder already has. The ggml-org prebuilt (L1) does not link NCCL. B4's `ldd` closure proof ("only `libcuda.so.1` may be missing") would have caught it.
| L2, second attempt | `-DGGML_NCCL=OFF` | No effect: b11159's option is `GGML_CUDA_NCCL` (`ggml/CMakeLists.txt:210`, default ON); `GGML_NCCL` is ik_llama.cpp's name. Still linked NCCL. CMake printed no unused-variable warning for it. |
| L2 (final) | `-DGGML_CUDA_NCCL=OFF` added; Containerfile `/home/research/phase0/l2/Containerfile` | `libggml-cuda.so` NEEDS only libggml-base, cudart/cuBLAS `.so.13`, `libcuda.so.1`, libstdc++/libm/libgcc_s/libc; `ldd` of every binary and library: nothing missing but `libcuda.so.1`... (resolved on the host). build 11159, commit 6b790a9c2, GNU 14.2.0, 144 sm_121a cubins, RUNPATH `$ORIGIN`. Output 732 MB. Builder image and build layers deleted afterwards. |

**Correction to the B2 addition above:** the flag is `-DGGML_CUDA_NCCL=OFF`.

### llama-bench, gpt-oss-20b MXFP4 (tokens/s, mean ± sd of 5; protocol above)

| Test | depth | load | L1 | L2 | N | L1/L2 |
| --- | --- | --- | --- | --- | --- | --- |
| pp2048 | 0 | none | 4938 ± 86 | 4901 ± 31 | 4890 ± 35 | 1.008 |
| tg32 | 0 | none | 84.13 ± 1.06 | 83.58 ± 0.61 | 82.31 ± 0.62 | 1.007 |
| pp2048 | 32768 | none | 3036 ± 12 | 3031 ± 7 | 2992 ± 24 | 1.002 |
| tg32 | 32768 | none | 63.14 ± 1.54 | 64.25 ± 0.54 | 64.02 ± 0.57 | 0.983 |
| pp2048 | 0 | dio | 4861 ± 59 | 4920 ± 56 | 4848 ± 20 | 0.988 |
| tg32 | 0 | dio | 80.32 ± 1.01 | 82.31 ± 0.48 | 80.91 ± 0.46 | 0.976 |
| pp2048 | 32768 | dio | 2984 ± 40 | 2990 ± 14 | 2940 ± 19 | 0.998 |
| tg32 | 32768 | dio | 64.11 ± 0.77 | 63.81 ± 0.21 | 63.01 ± 0.65 | 1.005 |

All CVs ≤ 2.4 %. Every L1/L2 ratio ≥ 0.97: within the declared tolerance for this model. (The Qwen download ran on the network during these runs.) Each whole bench run took about 40 s; MemAvailable fell by at most 20.6 GiB during it.

### Correctness, gpt-oss-20b

Greedy (`/completion`, temperature 0, top_k 1, seed 1, 128 tokens, ctx 8192, np 1): all three builds produce coherent text. **L2 and N are identical.** L1 diverges at character 118: after `…with the list of prime numbers`, L1 picks `,` (logprob −1.291) over ` as` (−1.416); L2 picks ` as` (−1.288) over `,` (−1.326). A near-tie; L1's greedy output is the same across load modes and cold/warm loads.

Perplexity on a fixed text (`docs/build.md`, `README.md`, `tools/server/README.md` of the b11159 checkout concatenated, 155,962 bytes), `-c 2048 -b 2048 -ub 2048 -t 10 --load-mode dio`, run with L1's `llama-perplexity` front end over each build's own libraries (L2 and N were built with only server and bench):

| Run | chunk 1–4 running PPL | final (4 chunks) | full text |
| --- | --- | --- | --- |
| CPU only (`-ngl 0 --device none`), L1 or L2 CPU backend (identical) | 18.07, 9.49, 6.77, 6.18 | 6.1800 | (running) |
| L1 GPU, FA on | 12.98, 8.23, 6.22, 5.88 | 5.8765 | 6.1768 ± 0.1057 |
| L2 GPU, FA on | 17.37, 9.48, 6.84, 6.28 | 6.2756 | 6.2655 ± 0.1078 |
| N GPU, FA on | = L2 | = L2 | 6.2655 ± 0.1078 |
| L1 kernels with CUDA 13.0 cuBLAS/cudart | = L1 | 5.8765 | — |
| L2 kernels with CUDA 13.4 cuBLAS/cudart | = L2 | 6.2756 | — |
| L1 GPU, FA off | 15.86, 9.14, 6.66, 6.15 | 6.1483 | — |
| L2 GPU, FA off | 15.52, 9.06, 6.63, 6.13 | 6.1332 | — |

So the L1/L2 difference is not cuBLAS; it comes from the ggml-cuda kernels as compiled by nvcc 13.4 vs 13.0, and shows with flash attention on. `test-backend-ops -b CUDA0 -o FLASH_ATTN_EXT` (built from the same commit with `GGML_BACKEND_DL=ON`, binary copied next to each build's `libggml-cuda.so` so the loader picks it; a first attempt with a symlinked binary loaded the wrong backend and was discarded): **L1 3982/3982 pass, L2 3982/3982 pass** against the CPU backend. Full op suite: (running).

### Load and page cache, gpt-oss-20b (llama-server, ctx 8192, np 1)

| Build | load mode | page cache | load s | GB/s | Cached Δ GiB | MemAvailable Δ GiB | min MemAvailable GiB |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L1 | dio | cold (evicted with `posix_fadvise(DONTNEED)`) | 4.51 | 2.69 | +0.78 | −12.74 | 96.42 |
| L2 | dio | cold | 4.15 | 2.92 | +0.76 | −13.03 | 96.50 |
| N | dio | cold | 4.09 | 2.96 | +0.74 | −12.57 | 96.84 |
| L1 | none | cold | 8.70 | 1.39 | **+12.10** | −12.55 | 96.93 |
| L1 | none | warm | 3.06 | 3.96 | +0.74 | −12.65 | 97.03 |
| L1 | dio | warm | 4.50 | 2.69 | +0.77 | −12.71 | 96.74 |

`dio` keeps the page cache from growing by the model size (+0.8 GiB vs +12.1 GiB for a cold `none` load) and loads a cold file about twice as fast; `none` wins only when the file is already cached. MemAvailable drops by the same ~12.7 GiB either way (the page cache is reclaimable). Download of gpt-oss-20b (curl, 12.1 GB, 17 m 7 s): Cached rose by up to 18.3 GiB (51.8 → 70.1), MemFree fell to 32.3 GiB, MemAvailable never below 101.7 GiB, PSI full 0.

CPU-only full-text perplexity (L2's CPU backend, `-ngl 0 --device none`): **6.5314 ± 0.1128**. Both GPU builds are below it (L2 −4.1 %, L1 −5.4 %), so on this model and text the GPU-vs-CPU gap is larger than the L1-vs-L2 gap (1.4 %); the CPU run is not a clean reference beyond "both GPU builds are close to it".

**Deviation (disk order):** the gpt-oss-120b download (≈2.5 h at this link speed) was started at 15:58 while Qwen3.6 is still on disk, instead of after deleting Qwen. Peak Phase 0 use becomes ≈101 GB (all three models plus builds) instead of ≈81 GB; free space stays ≥ ≈38 GB, above the 20 GB floor. The Ollama gate's files come only after Qwen is deleted. Reason: saves ~1.5 h of wall time on a slow link. Qwen3.6-35B-A3B MTP UD-Q4_K_XL downloaded in 30 m 34 s, sha256 `55983c5a…` OK.

Full `test-backend-ops -b CUDA0` (all ops vs the CPU backend): **L1 16445/16445 pass, L2 16445/16445 pass.**

### llama-bench, Qwen3.6-35B-A3B MTP UD-Q4_K_XL (tokens/s, mean ± sd of 5)

| Test | depth | load | L1 | L2 | N | L1/L2 |
| --- | --- | --- | --- | --- | --- | --- |
| pp2048 | 0 | none | 2957 ± 21 | 2957 ± 25 | 2964 ± 24 | 1.000 |
| tg32 | 0 | none | 68.60 ± 0.48 | 67.68 ± 0.49 | 68.24 ± 0.65 | 1.014 |
| pp2048 | 32768 | none | 2375 ± 7 | 2407 ± 10 | 2413 ± 14 | 0.987 |
| tg32 | 32768 | none | 57.08 ± 0.46 | 57.40 ± 0.42 | 57.24 ± 0.45 | 0.994 |
| pp2048 | 0 | dio | 2961 ± 9 | 2967 ± 16 | 2957 ± 5 | 0.998 |
| tg32 | 0 | dio | 67.61 ± 0.46 | 68.38 ± 0.49 | 67.47 ± 0.27 | 0.989 |
| pp2048 | 32768 | dio | 2418 ± 10 | 2412 ± 12 | 2346 ± 139 (cv 5.9 %) | 1.003 |
| tg32 | 32768 | dio | 56.05 ± 0.39 | 56.53 ± 0.39 | 55.28 ± 1.06 | 0.992 |

Within tolerance. The one N cell above 3 % CV is a reference cell and was not re-run. Perplexity (same text and flags): L1 **3.0602 ± 0.0441**, L2 **3.0468 ± 0.0438**, N = L2 exactly (0.4 % apart).

### Memory, Qwen3.6-35B-A3B MTP UD-Q4_K_XL (L1, llama-server, `--load-mode dio`, `-ngl 99 -fa on -b 2048 -ub 2048 -t 10`, `--kv-unified` when np > 1; weights 22.85 GB = 21.28 GiB)

Prefill = one request of exactly 90 % of the context (token ids counted by the server's `/tokenize`); parallel = np requests of 20 % of the pool each, at once. The first attempt of this matrix used a words-per-token guess that overshot the context (HTTP 400) and was discarded.

| ctx | np | MTP | load s | MemAvail Δ at ready (GiB) | peak MemAvail drop (GiB) | min MemFree (GiB) | greedy decode tok/s | MTP accepted | prefill | parallel |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 32768 | 1 | off (cold) | 6.31 | −23.36 | 24.03 | 33.39 | 66.7 | — | 29,491 t in 11.1 s (2741 t/s) | — |
| 32768 | 1 | on | 6.18 | −24.59 | 25.37 | 31.55 | 99.4 | 90/109 | 29,491 t in 11.5 s (2610 t/s) | — |
| 131072 | 4 | off | 6.73 | −26.38 | 33.38 | 22.38 | 66.3 | — | 117,964 t in 57.0 s (2087 t/s) | 4 × 26,214 t in 55.0 s |
| 131072 | 4 | on | 7.66 | −29.02 | 34.86 | 19.12 | 95.3 | 90/109 | 117,964 t in 58.9 s (2013 t/s) | 4 × 26,214 t in 75.5 s |
| 262144 | 1 | off | 6.63 | −29.91 | 31.30 | 21.50 | 66.2 | — | 235,929 t in 142.1 s (1668 t/s) | — |
| 262144 | 1 | on | 8.25 | −33.23 | 34.80 | 14.32 | 97.5 | 90/109 | 235,929 t in 151.3 s (1563 t/s) | — |

- MTP greedy output is identical to non-MTP greedy output (checked on the 32k pair), with a 1.43–1.49× decode speedup. It costs 1.2–3.3 GiB more at ready, and the parallel run took 37 % longer with MTP.
- Peak drop exceeds the at-ready drop by 0.7–7.0 GiB (prefill and parallel compute). PSI `full avg10` stayed 0 throughout. The kernel reclaimed page cache (MemFree fell to 14.3 GiB while MemAvailable never fell below 76 GiB).
- Qwen3.6's hybrid attention keeps KV small: 256K context adds ≈6.5 GiB over 32K.

**Deleted** `models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` (22.85 GB) after these runs (owner's instruction). `df -h /` afterwards: see next entry.

### Ollama gate (decision 2)

`ollama-linux-arm64.tar.zst` v0.34.4 from `github.com/ollama/ollama/releases/download/v0.34.4/`: 1,549,684,612 B, sha256 `96f50a11…` OK. Extracted: **2.1 GB** (`lib/ollama/cuda_v12` 1.2 GB, `cuda_v13` 898 MB). `cuobjdump`: `cuda_v13/libggml-cuda.so` has **no ELF (SASS) at all, only PTX** (incl. `sm_121a`); `cuda_v12` has ELF and PTX up to sm_120a, none for 12.1. Confirms the plan.

Run on the host: `tools/ollama-serve.sh`: `env -i` with the adapter's variables (`OLLAMA_HOST=127.0.0.1:11535`, `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_KV_CACHE_TYPE=f16`, `OLLAMA_CONTEXT_LENGTH=8192`, `OLLAMA_NO_CLOUD=1`), plus `OLLAMA_DEBUG=1`, `CUDA_CACHE_PATH=/home/research/phase0/ollama-jit` (C11), through `gpurun`. Listened on 127.0.0.1:11535 only.

| Item | Result |
| --- | --- |
| Backend selection | `cuda_v12` skipped: "compute capability not in compiled architectures" (cc 1210). `cuda_v13` selected: `library=CUDA compute=12.1 … type=iGPU total="119.6 GiB" available="109.4 GiB"` (MemAvailable). |
| Pull `gpt-oss:20b` | 29 m 32 s (link shared with the 120b download). Manifest sha256 `17052f91…` = catalog `manifestDigest`; size 13,793,441,244 = catalog. Store 13 GB. |
| Engine | Ollama runs its bundled llama-server (`lib/ollama/llama-server`, ggml 0.24.0) with `load_mode = dio`, `-c 8192 -np 1`; all 25/25 layers on CUDA0 (12,037 MiB model buffer + 1,105 MiB CUDA_Host). |
| First load, empty JIT cache | load 29.06 s; first request's prompt 7.4 t/s (more JIT); JIT cache afterwards **212 MB** (203M on disk). |
| Reload, warm JIT cache | load 6.83 s; prompt 258 t/s. |
| Decode | 58.4 t/s (warm; `think: low`, 256 tokens, temperature 0). llama-server greedy decode on the same model: 81.6 (L1) / 80.0 (L2) t/s. |
| Memory | MemAvailable drop 15.56 GiB at load (llama-server at the same 8192 ctx: ≈12.7 GiB); Shmem +1.17 GiB. |
| Tool call | `/api/chat` with a `get_weather` tool → `tool_calls: [{name: get_weather, arguments: {city: Bucharest}}]`. |
| Pressure | During the first load the page cache was full from the concurrent 120b download (MemFree 2.3 GiB, Cached 104 GiB, MemAvailable 111 GiB): PSI memory `full avg10` peaked at **14.23** while MemAvailable never fell below 95.4 GiB. |

Deleted afterwards: Ollama's model store (13 GB). The extracted Ollama (2.1 GB) and the JIT cache stay until decision 2.

### Findings not in the plan (for the owner)

1. **llama-server's prompt cache.** At b11159, `--cache-ram` defaults to 8192 MiB ("set the maximum cache size in MiB (default: 8192, -1 - no limit, 0 - disable)"); Ollama's bundled server logs "prompt cache is enabled, size limit: 8192 MiB". On unified memory this is up to 8 GiB more from the same pool, which C2's admission does not count and the adapter does not set. The runs above did not fill it (one request each). Proposed: the adapter passes `--cache-ram` explicitly (0 or a small value in the unified profile) and admission counts it.
2. **PSI as a stop signal.** C3 says the guard also watches `/proc/pressure/memory` `full avg10`. The Ollama first load above hit 14.23 purely from page-cache reclaim with ≥ 95 GiB available, so a PSI threshold would stop healthy loads whenever the page cache is full (after any large download). PSI needs a high threshold combined with low MemAvailable, or should only be logged.

### gpt-oss-120b MXFP4 (63,387,346,208 B = 59.03 GiB; `ggml-org/gpt-oss-120b-GGUF` @`238abdd2`, sha256 `582bd40f…` OK; download 82 m 13 s)

First L1 and L2 runs were disturbed: they ran right after the download with ≈93 GiB of page cache; PSI `full avg10` reached 28.5 (L1) / 7.6 (L2) and several cells had CV 5–21 %. Per the protocol they were re-run once (first runs kept in `results/first-120b/`); N ran later and was clean (PSI ≤ 1.0).

| Test | depth | load | L1 (re-run) | L2 (re-run) | N | L1/L2 |
| --- | --- | --- | --- | --- | --- | --- |
| pp2048 | 0 | none | 2491 ± 24 | 2527 ± 26 | 2450 ± 30 | 0.986 |
| tg32 | 0 | none | 57.07 ± 0.50 | 58.47 ± 0.25 | 57.92 ± 0.32 | 0.976 |
| pp2048 | 32768 | none | 1693 ± 6 | 1623 ± 152 (cv 9.4 %, after its one re-run) | 1693 ± 7 | 1.043 |
| tg32 | 32768 | none | 43.15 ± 0.92 | 43.19 ± 1.15 | 44.28 ± 0.31 | 0.999 |
| pp2048 | 0 | dio | 2558 ± 16 | 2508 ± 11 | 2538 ± 7 | 1.020 |
| tg32 | 0 | dio | 57.19 ± 0.33 | 57.09 ± 0.23 | 57.37 ± 0.25 | 1.002 |
| pp2048 | 32768 | dio | 1728 ± 6 | 1708 ± 5 | 1728 ± 8 | 1.012 |
| tg32 | 32768 | dio | 44.31 ± 0.15 | 43.41 ± 0.33 | 44.31 ± 0.19 | 1.021 |

Within tolerance. Perplexity (same text/flags): **L1 = L2 = N = 3.4554 ± 0.0520**, identical to four decimals. Greedy: L2 = N; L1 diverges at character 120 (`…because a prime number is de…` vs `…because it only has one posi…`), again a wording fork.

Memory (L1, llama-server, dio unless noted):

| run | load s (GB/s) | MemAvail Δ at ready (GiB) | peak drop (GiB) | min MemAvailable (GiB) | min MemFree (GiB) | decode t/s | notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ctx 32768, np 1, cold | 15.86 (4.00) | −67.14 | 67.87 | 42.72 | 33.55 | 55.6 | Cached +0.85 GiB |
| ctx 32768, np 1, cold, **`none`** | 51.12 (1.24) | −60.30 | 60.63 | 48.03 | **2.96** | 56.2 | Cached +37 GiB (max 45.4) |
| ctx 131072, np 1, cold, prefill 117,964 t | 16.07 (3.94) | −67.70 | 68.29 | 40.75 | 32.48 | 55.6 | prefill 90.6 s |
| ctx 131072, np 4, prefill + 4 × 26,214 t at once | 16.47 (3.85) | −65.98 | **80.51** | **28.41** | 19.99 | 55.5 | parallel 74.7 s |

**Deleted** `models/gpt-oss-120b-MXFP4.gguf` after these runs (owner's instruction). `df -h /`: 449 GB free.

### Prompt cache, measured (gpt-oss-20b, L1, ctx 131072, np 4, `--kv-unified`, prefill of 117,964 t then 4 × 26,214 t at once)

| `--cache-ram` | at-ready Δ (GiB) | peak drop (GiB) | parallel requests |
| --- | --- | --- | --- |
| default (8192 MiB) | −16.55 | **25.43** | 4/4 ok; log: "saving idle slot to prompt cache" ×5 |
| 0 | −16.92 | 20.85 | **0/4: HTTP 500**, "decode: failed to find a memory slot for batch of size …" ×36 |

With the default, the idle slot's 118k-token KV is moved to the host-RAM prompt cache (up to 8 GiB of the same unified pool) and the unified KV has room again; with the cache off, the idle slot keeps its cells and every new request fails. So `--cache-ram 0` is not a fix; the adapter should pass an explicit size and admission should count it. (Buffer breakdown at `-lv 4`: CUDA0 model 10,949 MiB + CUDA_Host model 587 MiB, CUDA0 KV 3,072 + 60 MiB, CUDA0 compute 869 MiB + CUDA_Host compute 567 MiB.)

A tool note: `serve_check.py` marks a run `ok` even when its parallel worker threads fail; the table above was checked per slot, and every other np-4 run in this log completed 4/4.

### Disk, actual

| Step | Planned peak (Phase 0) | Actual | Free on `/` afterwards |
| --- | --- | --- | --- |
| Builds (L1, L2 with 3.93 GB builder, N) | ≈15 GB | builder + layers ≈15 GB, deleted after L2; kept: L1 1.6 GB, L2 0.73 GB, N 0.6 GB | 117 GB (before the review session's cleanup) |
| gpt-oss-20b | 12.1 GB | 12.1 GB, **kept** for the Phase 1 nested check | — |
| Qwen3.6 MTP | 22.9 GB | 22.9 GB, deleted after its runs | 422 GB |
| Ollama gate | ≈19 GB | archive 1.5 GB + extracted 2.1 GB + store 13 GB; store deleted, archive/extract kept until decision 2 | — |
| gpt-oss-120b | 63.4 GB | 63.4 GB, deleted after its runs | 449 GB |

Peak Phase 0 use was ≈112 GB (20b + Qwen + 120b + Ollama store + builds) at about 17:15; free space never fell below ≈38 GB before the review session's cleanup (which freed ≈270 GB at ~16:10). Now in `/home/research/phase0`: ≈19 GB.

## Phase 0 proposals (for the owner)

### Decision 1: plan rule applied

| Criterion | L1 (prebuilt 13.4) | L2 (source 13.0) |
| --- | --- | --- |
| Runs on driver 580.159.03 | yes (minor-version compatibility) | yes |
| `sm_121a` cubins; CPU variant on this CPU | yes; armv8.6_2 | yes; armv8.6_2 |
| `test-backend-ops` vs CPU, all ops | 16445/16445 | 16445/16445 |
| Perplexity 20b / Qwen3.6 / 120b | 6.1768 / 3.0602 / 3.4554 | 6.2655 / 3.0468 / 3.4554 |
| Greedy text | coherent; differs from L2 at a near-tie on 20b and 120b | identical to N |
| Throughput vs L2 (all 24 cells) | 0.976–1.043 (≥ 0.97 everywhere) | — |
| Supply chain | two sha256-pinned release archives, no builder | pinned 3.93 GB builder, commit fetch, NCCL flag, RUNPATH fix |

The declared greedy-identity check is not met between toolkits (13.4 vs 13.0), only within one (L2 = N). The divergences are near-ties (`,` 27.5 % vs ` as` 24.3 % on L1; ` as` 27.6 % vs `,` 26.6 % on L2), both builds pass every op test, and the perplexity comparison is mixed and small (120b identical; Qwen 0.4 %; 20b 1.4 %, L1 lower, while the CPU backend is 4–5 % above both). Under the plan's rule ("if L1 is within the predeclared tolerance of L2, ship L1") the recommendation is **L1**, provided the owner accepts perplexity plus op tests as the correctness check in place of token-identical greedy output across toolkits.

### Decision 2: Ollama

It works (cuda_v13 by PTX JIT, tool calls OK), but: decode 58.4 t/s vs 80–82 t/s for llama-server on the same model; first load in each new container +22 s of JIT (212 MB cache, container-local under C11); +3 GiB memory vs llama-server; +2.1 GB unpacked in every arm64 image. Recommendation: **leave it out of the first arm64 image**; the adapter reports "not available on this platform".

### Admission constants, guard floor and envelope (unified profile, llama-server, `--load-mode dio`)

Measured "at ready" need beyond the weights file (GiB): 20b ctx 8k np 1: 1.3–1.8; 20b ctx 128k np 4: 5.3–5.6; Qwen3.6 ctx 32k: 2.1 (+1.2 MTP); ctx 128k np 4: 5.1 (+2.6 MTP); ctx 256k: 8.6 (+3.3 MTP); 120b ctx 32k: 8.1; ctx 128k np 1: 8.7; ctx 128k np 4: 7.0. Peak beyond "at ready": ≤ 0.7 with one request; up to 3.9 with the prompt cache off; up to 7.0 / 8.9 / 14.5 (Qwen / 20b / 120b, np 4) with the default 8 GiB prompt cache in use.

Proposed:
1. **Need** = weights + the model's measured at-ready overhead for its (ctx, np, MTP) + `cacheRam` + runtime margin (4 GiB for np = 1, 8 GiB for np > 1). The adapter passes `--cache-ram` explicitly in the unified profile (proposed 4096 MiB) and admission counts it. Check against the 120b worst case: 59.03 + 7.0 + 8 (default cache in that run) + 8 = 82.0 ≥ 80.5 measured.
2. **Host reserve** for `incompatible`: 16 GiB (idle host with nothing else running uses 9–12 GiB; room for the workspace's other agents): need > MemTotal − 16 GiB = 103.6 GiB is incompatible.
3. **Guard floor** for `insufficient-now` and the stop: **8 GiB** (above one 250 ms sample at the ≈28 GiB/s allocation rate measured in the review, M4; the plan's max(4 GiB, 5 %) is 6 GiB here). Sampling 250 ms while loading, 2 s when ready.
4. **PSI**: record, and stop only when `full avg10` ≥ 50 **and** MemAvailable < 2 × floor. Page-cache reclaim alone produced 14.2 and 28.5 with ≥ 45 GiB available.
5. **Load mode**: unified default `dio` (cold load 1.9–3.2× faster than `none`, page cache +0.8 GiB instead of +12 to +37 GiB). **Page-cache drop** after the sha256 check (`posix_fadvise(DONTNEED)`): yes. A full page cache after a download caused PSI 7.6–28.5 and 5–21 % CV in the first 120b benchmarks.
6. **Measured envelope** (first release; anything else is refused until Phase 5):

| Model | ctx × np | MTP | measured peak drop (GiB) |
| --- | --- | --- | --- |
| gpt-oss-20b MXFP4 | ≤ 131072 × ≤ 4 | n/a | 25.4 |
| Qwen3.6-35B-A3B MTP UD-Q4_K_XL | ≤ 131072 × ≤ 4, or ≤ 262144 × 1 | on/off | 34.9 |
| gpt-oss-120b MXFP4 | ≤ 131072 × ≤ 4 | n/a | 80.5 |

Not measured in Phase 0: thread count (all runs used `-t 10`), CPU pinning, K/V types other than f16, and the listed-but-unvalidated models (Qwen3-Coder, GLM-4.7-Flash, Qwen3.5-122B).

## Pushes

| When | Repo | Branch | Head pushed | Check |
| --- | --- | --- | --- | --- |
| 2026-09-28 ~18:00 | ploinky | local-llm-multiarch (new) | `338a3c567391cdc3004daa88d1e0ad16436bfe8d` | `git ls-remote` matches; outgoing commits authored skutner, no AI trailer lines |
| 2026-09-28 ~18:00 | local-llms | local-llm-multiarch (new) | `ee175b9080b34f9538d8f6869e00ee8c91ac3b14` | same |
| 2026-09-28 ~18:00 | container-image-builds | local-llm-multiarch (new) | `f10aeb51119be6063a0c12f9e5d537c95ba5386f` | same |

No force-push. Pushing touches only the feature branch; per the coordinator, the only CI a branch push triggers is read-only (ploinky `verify-runtime-source-absence.yml`, container-image-builds `verify-edge-routing-source-absence.yml`).

## Step 4: Phase 1 nested check (started 2026-09-28 ~17:45)

### Dev image

`container-image-builds` `f10aeb5`: `images/local-llm/Dockerfile.arm64` (L1), `runners.lock.arm64.json` (empty), `sources.lock.arm64.json`. Built locally: `podman build --platform linux/arm64 --build-arg RELEASE_MIRROR=http://127.0.0.1:18765 -f Dockerfile.arm64 -t localhost/local-llm:dev .` (mirror = a loopback `python3 -m http.server` over `/home/research/phase0/dl`, which holds the already-verified release files; the Dockerfile's sha256 checks still apply). Image `b14cdc2705ee`, 2.12 GB. Proof: uid 1000; aarch64; build 11159; `ldd` of `/opt/llama.cpp/*` resolves everything but `libcuda.so.1`; no `*.gguf|*.safetensors|*.exl3`; no LM Studio/llmster files; lock `cmp` with `runners.lock.arm64.json` OK; `source.contract` = `architecture=arm64, llama_cpp=b11159, llama_cpp_cuda=13.4, llama_cpp_build=release, gpu_compute_capabilities=12.1, uv=0.12.18`; `/opt/runners` owned by uid 1000; 144 `sm_121a` cubins in `libggml-cuda.so`. `node --test tests/image-definitions.test.mjs`: 22/22.

### Test workspace, first attempt (`/home/research/gpu-test-workspace`, discarded)

- UDP 7882 on this host is held by another user's rootless containers (`salboaie`, `rootlessport`), so the workspace uses `ploinky --port 18088 --udp-port 17882 start …` (flags accepted only before `start`, `diagnose`, `repair`).
- `start local-llms/local-llm`: the Box came up with self-checks passed, then the agent failed because `localhost/local-llm:dev` is not in the Box's own store (`podman pull localhost/local-llm:dev` → registry `https://localhost/v2/` refused); the failed start removed the new Box (rollback).
- `ploinky gpu status` from the dev CLI (A1+A2) on the Box-less workspace: `Host GPU: nvidia driver 580.159.03; devices /dev/nvidia0, /dev/nvidiactl, /dev/nvidia-uvm; libraries libcuda.so.1, libnvidia-ptxjitcompiler.so.1, libnvidia-ml.so.1, libnvidia-nvvm.so.4, libnvidia-nvvm70.so.4, libnvidia-gpucomp.so.580.159.03`, `GPU agents: local-llms/local-llm (manifest)`, `Desired GPU wiring: active a50d41a07461` (the installed Ploinky reports "unavailable" on this host).
- `disable agent` could not run (no Box; it tried to create one on UDP 7882). A start with `AchillesIDE/gitAgent` as the static agent also tried the registered local-llm and rolled back. **Deviation:** I then removed local-llm's record from this throwaway workspace's `agents.json` by hand (backup in `/home/research/phase0/logs/testws-agents.json.bak`); the next start refused with "agent 'local-llms/local-llm' has no unambiguous enabled instance identity" (other state still referenced it). The workspace is discarded and redone in an order that needs no hand edits: Box first (gitAgent), load the image, then `enable agent local-llms/local-llm`.

### Test workspace (`/home/research/gpu-test-workspace`, recreated) — run by the dev Ploinky clone

Order used (no hand edits): workspace checkout `local-llms` (a clone of the dev branch at `ee175b9`, origin set to GitHub; its `local-llm/manifest.json` `container` changed to `localhost/local-llm:dev` as an **uncommitted, test-only** edit) → `/home/research/dev/ploinky/bin/ploinky --port 18088 --udp-port 17882 start AchillesIDE/gitAgent` (exit 0; bootstrap cloned AchillesIDE, AchillesCLI, copilot-agents into `.ploinky/repos`) → `podman save` the dev image into the workspace, `podman exec -u podman <box> podman load -i …` into the Box's own store (`/home/podman/.local/share/ploinky-images` = `<ws>/.ploinky/box/images`), tar deleted → `ploinky enable agent local-llms/local-llm` → `ploinky --port 18088 --udp-port 17882 start` (exit 0, `local-llm: ready`).

Box `ploinky-box-gpu-test-workspace-90b386b1f08a`:

| Check | Result |
| --- | --- |
| Ploinky source | `/home/research/dev/ploinky -> /opt/ploinky` read-only (dev clone, A1+A2) |
| GPU wiring | label `io.assistos.ploinky-box.gpu-grant=a50d41a0…`; devices `/dev/nvidia0`, `/dev/nvidiactl`, `/dev/nvidia-uvm` (plus the base `/dev/fuse`, `/dev/net/tun`); read-only binds of the six AArch64 driver libraries under `/usr/local/nvidia/lib64` (incl. `libnvidia-nvvm70.so.4`), `nvidia-smi`, CDI spec `/etc/cdi/ploinky-gpu.json` (`ploinky.local/gpu=all`, no hooks), marker; `Privileged=false`, `CapAdd=[]`. `ploinky gpu status`: `Box: running; GPU wiring active a50d41a07461`. |
| Publications | `127.0.0.1:18088->8080/tcp`, `0.0.0.0:17882->7882/udp` only |
| Nested local-llm container | image `localhost/local-llm:dev`; create command adds only `--device ploinky.local/gpu=all` and `PLOINKY_GPU_STATUS=attached`; `Privileged=false`, `CapAdd=[]`, `IPC=private`, shm 8 GiB; uid 1000; `/dev/nvidia*` present; `nvidia-smi` → `NVIDIA GB10, 580.159.03, [N/A], ATS, 12.1` |
| Agent snapshot (C0) in the nested container | `{"available":false,"name":"NVIDIA GB10","driverVersion":"580.159.03","reason":"nvidia-smi reports no memory figures for NVIDIA GB10 (total [N/A], used [N/A], free [N/A]), so this agent cannot size models …"}` |

### GB10 memory measurements inside the nested container (`/data/phase1/probe`, static-cudart CUDA probe built with host nvcc for sm_121a)

| # | Measurement | Nested result | Review (host) |
| --- | --- | --- | --- |
| M1 | device properties | `integrated=1`, `pageableMemoryAccessUsesHostPageTables=1`, 119.63 GiB; driver API 13000 | same |
| M2 | `cudaMemGetInfo` vs meminfo | free = MemFree exactly (93.23 vs MemAvailable 108.21; later 1.74 vs 53.01) | same |
| M3 | allocations reclaim page cache | page cache pre-filled with a 50 GB scratch file (Cached 63.1, MemFree 41.4); 56 GiB allocated + touched: all succeeded, Cached 63.1 → 48.1 (−15.0), MemAvailable 108.2 → 53.0; freed afterwards | same behaviour |
| M4 | allocation rate | 16 GiB in 0.68 s = **23.5 GiB/s**; 56 GiB while reclaiming: 13.1 GiB/s | ≈28 GiB/s |
| M5 | RSS / OOM score | holding 16 GiB: VmRSS 100 MB; with `oom_score_adj` 1000 written by the process itself (uid 1000, no privilege): oom_score 1333 | RSS 98 MB, baseline oom_score |
| M6 | cgroup | `/sys/fs/cgroup/memory.current` 3172 → 3204 MiB while holding 16 GiB (+32 MiB); `memory.max` = `max` | 70 MiB in a 2G scope |

### gpt-oss-20b inside the nested container

`/opt/llama.cpp/llama-server` from the dev image (L1), run by hand in the nested container (the agent itself refuses Runs on GB10 until Phase 2, as C0 intends): `-m /data/phase1/gpt-oss-20b-MXFP4.gguf` (hard link, no copy) `--host 127.0.0.1 --port 18090 -ngl 99 -fa on -b 2048 -ub 2048 -t 10 -c 8192 -np 1 --load-mode dio`, after `echo 1000 > /proc/self/oom_score_adj; exec …`.

| Item | Result |
| --- | --- |
| ready | 5.35 s |
| greedy completion | **identical** to the host L1 run; decode 79.9 t/s, prompt 163.4 t/s (host: 81.6 / 170.7) |
| GPU use | `nvidia-smi --query-compute-apps`: `/opt/llama.cpp/llama-server, 11875 MiB` |
| process | oom_score_adj 1000 (inherited through exec), oom_score 1340, VmRSS 1.37 GB |
| memory | MemAvailable drop 13.14 GiB (host: ≈12.7); PSI full ≤ 1.32 |
| stop | SIGTERM → process gone, GPU memory released (MemAvailable back to 108 GiB) |

**Phase 1 gate: met.** A1 and C0 unit tests pass; the GPU works from a nested container on arm64 with the hookless CDI device.

Harness fix (decision above): `serve_check.py` now raises (run `ok: false`) when any parallel request fails.

### Prompt-cache candidate (host, L1, gpt-oss-20b, ctx 131072, np 4, prefill 117,964 t then 4 × 26,214 t, fixed harness)

| `--cache-ram` | ok | at-ready Δ (GiB) | peak drop (GiB) | parallel |
| --- | --- | --- | --- | --- |
| 4096 | yes | −15.61 | 19.76 | 4/4 in 46.7 s |
| 8192 (explicit) | yes | −16.84 | 20.30 | 4/4 in 46.9 s |

The earlier default-8192 run peaked at 25.43 GiB, so the prompt cache's share varies with what gets saved. 4096 MiB passed on gpt-oss-20b only; Qwen3.6 and gpt-oss-120b were already deleted, so per the decision the implementation keeps the 8192 MiB baseline (counted in admission) and 4096 stays a candidate until checked on the larger models.

## Safety follow-up (plans/phase0-safety-followup_codex.md), in progress

Tools (in `/home/research/phase0/tools`):
- `serve_check2.py`:
  - a settled baseline before a run (MemAvailable within ±0.25 GiB over 10 s, up to 300 s);
  - `-lv 4` logs, with every buffer summed by device and kind, and prompt-cache events counted (saved, skipped over the limit, "failed to find a memory slot");
  - every request's HTTP status, error body, `prompt_n`, `predicted_n`, slot and start/end time; a run fails on any failed or short request;
  - parallel phases must overlap in time and use distinct slots;
  - patterns `greedy`, `prefill`, `parallel`, `coldparallel`, `longgen`;
  - the process's GPU memory from `nvidia-smi --query-compute-apps` every 500 ms;
  - 60 s of sampling after exit, time back to within 0.5 GiB, and a `drift` flag when the end differs from the baseline by more than 0.75 GiB.
- `stop_latency.py`: SIGKILL or SIGTERM to the process group at a fraction of the load or N seconds into np simultaneous cold prefills. It records signal → exit → MemAvailable back within 0.5 GiB (50 ms samples), the largest 250 ms fall before the signal, and any further fall after it.
- `memsample.py` now writes absolute timestamps.

Validation run of `serve_check2.py` (gpt-oss-20b, ctx 32768, np 4, `--cache-ram 1`, all five patterns): all 14 requests ok; parallel phases overlapped 7.4–7.9 s on 4 distinct slots; logged buffers CUDA0 model 10,949 + CUDA_Host model 587 + output 3 + CUDA0 KV 828 + CUDA0 compute 485 + CUDA_Host compute 183 MiB = 12.73 GiB; "exceeds cache size limit 1.000 MiB, skipping" ×8. Its MemAvailable figures are not usable: the baseline moved by about 8 GiB during the run (the 120b re-download and other users' sessions on this shared host were active), which is why runs now require a settled baseline and are flagged for drift, and memory runs wait for the download to finish.

Tool test of `stop_latency.py` on gpt-oss-20b (ctx 32768, np 4; download still running, so leads only):

| When | Signal | Result |
| --- | --- | --- |
| load, at a 6.45 GiB drop | SIGKILL | exit 0.415 s after the signal, MemAvailable back at exit; largest fall per 250 ms before the signal 4.24 GiB; **MemAvailable still fell a further 6.57 GiB after the signal before release** |
| 3 s into 4 × 7,372-token cold prefills | SIGTERM | **did not exit within 120 s**: the log shows `cleaning up before exit...` at the signal and nothing after; killed by the tool |

Both are to be confirmed on gpt-oss-120b. The controller already follows SIGTERM with SIGKILL after 10 s on a Stop, and the unified guard uses SIGKILL.

## Step 5: Phase 2 (local-llms, branch `local-llm-multiarch`), commits so far

All pushed to origin; each commit's tests: `node --test 'local-llm/tests/*.test.mjs'` from the repo root, all passing at each commit (count after the commit).

| Commit | Items | Tests |
| --- | --- | --- |
| `54f9388` | C1: second optional nvidia-smi query; memory model dedicated/unified/unknown (known-unified GB10 id, ATS/HMM); unified pool from /proc/meminfo; performance cores; PSI reader; DS005 created | 269 |
| `42bf53d` | C2–C6 core, C3, C4, C9, C11: profile from the first snapshot; catalog v3 (profiles, per-profile recommended/validated, unified envelope; no migration); unified llama-server schema and fixed flags (`--cache-ram 8192`, MTP opt-in); unified admission (buffers + transient + 1.5 GiB runtime + cache bound; reserve 16 GiB, floor 8 GiB, provisional); runner availability from `source.contract` and `runner_unavailable` before download; GPU compute-capability check; unified guard 250 ms in every phase with process-group SIGKILL; `oom_score_adj` 1000 for every runner; `CUDA_CACHE_PATH` in the container; page-cache drop after verified downloads; loadMode replaces noMmap/mlock; LM Studio tests fixed | 283 |
| `ec77b40` | C8: unified-memory card and shared-memory estimate | 284 |
| `574660b` | C7: completion budget and runner deadline from the environment within the 600 s limit; more forwarded fields; usage in the last stream chunk | 285 |
| `a72260e` | C6 (§9): unsupported registry entries and saved params reported, not misread; removable | 286 |
| `50308c5` | C10: manifest about/description for both platforms | 286 |
| `0843870` | C6: split GGUF as one artifact | 291 |
| `28aa001` | **D** (separate commit): the twelve legacy agents, their image, scripts, catalog, tests, repository specs and HTML docs removed; coding style moved to local-llm DS006; references rewritten with links to `03697765`; dropped services documented in DS000; README, AGENTS.md, handoff rewritten | 291 |

Deliberate breaking changes (no backwards compatibility, owner): listed in the `42bf53d` and `28aa001` messages and in DS002, DS003, DS005.

Still open in Phase 2: the unified seed entries (gpt-oss-20b envelope, gpt-oss-120b, Qwen3.6-35B-A3B MTP, listed models) need the safety follow-up's buffer/transient measurements; the manifest pin moves in Phase 3. `plans/local-llm-x86-gate-procedure.md` is the draft procedure for the x86 gate on ubuntu-codex.

### Later Phase 2 and Phase 3 commits

| Repo | Commit | What |
| --- | --- | --- |
| local-llms | `88a3873` | availability before the operator switch (found on Spark: LM Studio showed its switch reason instead of "not available on this platform") |
| local-llms | `7e7b2b5` | unified seed entries, pinned, without envelopes: gpt-oss-120b, Qwen3.6-35B-A3B MTP, Qwen3-Coder-30B-A3B Q8_0, GLM-4.7-Flash Q8_0, Qwen3.5-122B-A10B (split, 3 shards); refused until measured |
| container-image-builds | `afd9415` | B1–B4: workflow with amd64 reuse-and-prove (`AMD64_DIGEST` b6c79…, label `95ba10a…`), arm64 build-and-prove on `ubuntu-24.04-arm` (uid, build 11159, closure, weight/LM Studio scans, arm64 lock `cmp`, contract, `cuobjdump` sm_121a via the pinned CUDA image), per-arch install checks (`LOCAL_LLMS_COMMIT` 28aa001…, to be re-pinned to the final candidate), and the index job after all of them, verifying exactly two children. `tests/image-definitions.test.mjs` 24/24. README row updated; the amd64 Dockerfile stays byte-identical. Not dispatched. |

### Phase 2 functional check on DGX Spark (nested, test workspace, local-llms `28aa001`)

`ploinky restart local-llm` in `/home/research/gpu-test-workspace` (dev image `localhost/local-llm:dev`), then `ploinky client tool local_llm_overview --agent local-llm`: `profile: unified`; GPU `NVIDIA GB10`, `memoryModel: unified`, device `0x2E1210DE / 12.1 / ATS`; memory 119.6 GiB total; runners: llama.cpp supported, the five others `supported: false` with "not available on this platform: this image does not include it"; gpt-oss-20b × llama.cpp `incompatible`: "has not been measured on unified memory with llama.cpp, so it cannot run here yet" (no envelope yet); `unsupportedModels: []`; status log `hardware profile: unified (NVIDIA GB10)`.

### Measurement run queued

`tools/followup.sh` starts automatically once the gpt-oss-120b re-download is complete and its sha256 verified (no downloads or builds during it): 120b 128K × 4 with `--cache-ram` 8192/4096/1 and 20b 128K × 4 with 8192/1, each twice, all five request patterns, `-lv 4`; then stop latency on 120b (load/active × SIGKILL/SIGTERM, twice). `stop_latency.py` now records a SIGTERM hang (30 s) and follows it with SIGKILL, checks that the process group is gone and that no GPU process remains, and compares the end MemAvailable with the settled baseline.

A read-only review of the Phase 2 diff by a subagent is running in parallel (reading only, to keep memory runs clean).

### Qwen3.6 re-download (approved) and queue change, ~18:50

- Owner (via Codex): re-download the same pinned Qwen3.6-35B-A3B MTP UD-Q4_K_XL (22.9 GB), verify its sha256, and measure its first-release envelopes (both corners of the L-shaped envelope, MTP on and off). Keep all three model files until envelope measurements, candidate acceptance and the review follow-ups are finished.
- The queued waiter (which would have started measuring when the 120b download ended) was stopped; the 120b transfer itself was not touched. The Qwen download was started beside it (`curl … unsloth/Qwen3.6-35B-A3B-MTP-GGUF/resolve/5bc3e238…/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`), 415 GB free.
- New chain: wait until both downloads have ended, verify both sha256, wait 60 s, then run `tools/followup.sh`. Each run also waits for a flat baseline (±0.25 GiB over 10 s). Added to the matrix: Qwen 128K × 4 (all five patterns) and 256K × 1 (greedy, prefill, longgen), MTP off/on, `--cache-ram` 8192 and 1, twice each; MTP flags passed as `--extra=…`.

### Review of the Phase 2 diff (read-only subagent) and fixes

No major finding; six minor ones, all verified in the code and fixed in local-llms `8af8ae8` (295 tests pass):
1. a transient nvidia-smi failure in the first snapshot locked the profile to dedicated until restart → the profile is fixed only by a snapshot with a usable GPU;
2. the unified guard stopped sampling during a graceful Stop/Replace → it now samples until the process exits;
3. a user model could take the id of a seed offered only in the other profile, or of an unreadable stored entry → checked against all seeds and stored entries;
4. Delete weights could not find a model not offered in the current profile, and did not decide the profile → fixed;
5. a split GGUF name with up to 99,999 shards was accepted before pinning (one Hugging Face request per shard) → limit 64 checked first;
6. the unified thread default ignored the cgroup CPU quota → capped.
Noted for the x86 gate: `oom_score_adj` 1000 now applies on x86 too, and a runner whose score cannot be written is killed; the procedure checks the value.

### C12 (plan sha `714b391f…`, added by the orchestrator for the owner)

local-llms `d3c6a94`, pushed. The controller adopts a pinned file from `/shared/models` (host `<workspace>/.data/shared/models`) before downloading:
- **Lookup:** regular files of the exact pinned size, found by a walk that follows no symlinks and is bounded (8 levels, 20,000 entries). Names never decide.
- **Adoption:** hard link, or a copy when a link is impossible. The agent's own link or copy is hashed; only a match is kept, and anything else falls through to the next candidate or the download.
- **Re-verification:** the verification record keeps dev/ino/size/mtime/ctime; a changed stat re-hashes the file before a Run, and a file verified before this change is re-hashed once.
- **Delete weights:** counts space as freed only for a last link (GGUF and snapshots).
- **Scope:** GGUF, every shard of a split GGUF, every snapshot file. Ollama is unchanged. DS002 has the lookup order.

Tests `tests/shared-models.test.mjs` (link, copy on EXDEV, wrong hash, symlinks to a file and to a directory, changed ctime with the same bytes → re-verified and kept, rewrite through the shared link → discarded and downloaded, old record without stat → hashed once). Full suite: 301/301.

### Safety follow-up matrix: greedy criterion correction (owner, 2026-09-28 ~20:20)

- Runs `120b-c128k-np4-cram8192-r1` and `-cram4096-r1` (harness v1) failed only on the greedy smoke check: HTTP 200, 101 tokens, cap 128. Every stress request (prefill, parallel, coldparallel, longgen; 13 requests) had its exact prompt and generation lengths, full overlap and distinct slots. v1 did not capture a stop reason. EOS is inferred: the request set no stop strings, and 28 + 101 tokens is far below the context.
- The raw `<run>.json` files are unchanged and keep `ok: false`. The corrected interpretation is a separate derived file, `results/followup/annotations.json`: original_ok, derived_ok, raw sha256, harness version, reason.
- **Harness versions:**
  - **v1:** greedy had to produce exactly 128 tokens.
  - **v2** (20:17:07–20:20:27; archived as `serve_check2.v2.py.txt`): greedy accepted any 1+ tokens. The in-flight run `120b … cram 1 r1` uses v2.
  - **v3** (sha256 `0733bf3d…`): greedy passes on `stop_type` eos with 1–128 tokens, or limit with exactly 128. It records the stop reason and the completion (at most 4,000 characters) and puts `harness_version` and `harness_sha256` in every result.
- **Unchanged:** memory-stress patterns keep exact `prompt_n` and `predicted_n` per request, plus the overlap and distinct-slot checks. A natural EOS in the smoke completion never waives a short stress request.
- This correction goes into the measurement report to the orchestrator.

### C12 rework after the Codex review (plan sha `738778a0…`, §9 item 8)

local-llms `d68c70f`, pushed to `local-llm-multiarch`. Fixes R1–R8 against the revised C12.
- **Trust model:** `/shared` is untrusted; no links from it. A candidate is used only through a private copy, hashed as it is written.
- **Order:** own store; in-place adoption at the canonical store path; copy from `/shared/models`; download or resume.

Implementation:
- New `src/controller/workspaceReuse.mjs`:
  - **Bound open:** `O_NOFOLLOW`, then `/proc/self/fd` must equal the expected path; fails closed.
  - **Hashing:** fstat before and after.
  - **Copies:** chunked (8 MiB), abortable, into a unique staging file.
  - **Publish:** record, rename, then compare dev/ino/size/mtime with the hashed object; only ctime may differ.
  - **Walk:** streaming and cancellable.
  - **Deletion:** freed bytes are inode-aware.
- New `src/controller/downloadError.mjs`.
- **Stores:**
  - `plan()`: the acquisition plan (0 owned or in place, the size for a copy, the remainder for a download);
  - `recheck()`: the last check before loading;
  - aggregated provenance and notes.
- **Controller:**
  - Run, preview and overview admit on the plan's bytes (overview uses one walk);
  - new `copying` phase;
  - provenance per file in the log and in the deployment's `provenance`;
  - Run's `acquisition` recorded;
  - recheck after runner preparation, before start.
- An injected downloader brings its own last-check verifier (tests).
- **Specs:**
  - DS002: trust model, canonical paths, binding, staging, copy rules, walk bounds, last check, provenance, freed bytes;
  - DS003: disk term of admission.
- **Tests:** `tests/shared-models.test.mjs` covers regression tests 1–14, plus the copy happy path and the old-record case; 15 tests. Full suite 310/310 (`node --test --test-concurrency=1 'local-llm/tests/*.test.mjs'`, run single-process beside the matrix).
- **Mutation checks:**
  - removing the before/after stability check fails test 2;
  - removing the partial before a candidate fails tests 4 and 10.
- Awaiting Codex's independent verification. Spark acceptance (in-place gpt-oss-20b link, small-model copy) comes after the matrix.

### Follow-up data quality: attribution, harness v4, validity, reruns (~20:45)

Reviewer's data-quality check: `plans/phase0-followup-data-quality_codex.md`.

**What ran on the host** (from this session's timestamped tool calls; `results/followup/engineering-activity.json`):
- **17:34–17:40 (Phase 0 120b np4 run):** engineering ran nothing but that run.
- **20:19:18 (start of the 120b cache-1 prefill excursion):** nothing. The calls at 20:17:55 and 20:19:47 were a file edit and a `tail`.
- **20:20:29–36:** `grep -a` over the 864 MB llama.cpp directory. Light, and it came after the excursion began.
- **20:25–20:30 (20b cache-8192 r1's 281 s baseline):** only file edits and greps.
- **20:30:18–20:33 and 20:35:26–20:37:45:** node tests and commit/push. These overlapped 20b cache-8192 r1 (in its phases) and 20b cache-1 r1 (baseline and load). Both runs are rejected.
- **The host is multi-user.** At 20:44, user `salboaie` had short-lived `node` processes of 3.2, 1.3 and 1.1 GiB RSS (40–326 s old) and user `daniel` was logged in. Other users' activity is the likely source of the unexplained excursions. A lock cannot serialise it, so v4 measures it.

**Harness v4** (`serve_check2.py` sha `d9956a26…`, `attribution.py` sha `2afa2774…`), installed 20:46:41 between runs; v3 is archived. Passive only:
- **Lock:** an exclusive flock on `/home/research/phase0/.memlock` from before the baseline to the end of the post-exit window.
- **Attribution, every 500 ms (28 ms per scan):** the runner group's VmRSS, RssAnon and RssShmem; per-PID GPU memory (runner versus others); every other user's RssAnon total. Unattributed = drop − runner GPU − runner (RssAnon + RssShmem), per phase against at-ready.
- **Flags:** baseline wait over 60 s and distance from the idle reference.
- **Release:** judged at exit+10 s.
- **Also:** `stop_latency.py` v2 takes the same lock.

**Engineering commands that could disturb memory** (tests, builds, hashing, pushes) now run under `flock /home/research/phase0/.memlock`.

**Validity:** `tools/memory_validity.py` (rule version 1) writes `results/followup/memory-validity.json` and leaves raw files and `annotations.json` untouched. Its release offsets reproduce the reviewer's numbers exactly. Classes now:

| Run | Class |
| --- | --- |
| 120b cache 8192 r1 | valid-without-attribution |
| 120b cache 4096 r1 | rejected (c) |
| 120b cache 1 r1 | rejected (c) |
| 20b cache 8192 r1 | rejected (b), (c), overlap |
| 20b cache 1 r1 | rejected (b), (c), overlap |

**Reruns:** `tools/followup-reruns.sh` is chained after the matrix (waiting on its PID). For up to 3 rounds it runs the next repetition of every configuration without two valid, agreeing runs. Stop-latency runs are judged separately.

### Validity rules rev 2, harness v5, attribution check (~20:53–21:00)

- **Harness v5** (`serve_check2.py` sha `babbc54e…`, `attribution.py` sha `54ec1f0c…`), installed 20:53:48 between runs:
  - `/proc/meminfo` is read inside the attribution loop;
  - nvidia-smi is timed and the midpoint used;
  - a pre-run meminfo snapshot is kept;
  - external memory for everyone = (AnonPages + Shmem) − runner (RssAnon + RssShmem);
  - 75 s post-exit tail;
  - post-run quiet window, load-step lag and coverage against the logged buffers.

  The residual is diagnostic only.
- **Controlled check 4e** (`tools/attribution_check.py`: 2 GiB anonymous helper, no GPU, under the lock; `results/followup/attribution-check.json`):
  - **Window averages (evaluation 1):** failed. `salboaie` released about 5 GiB during the 20 s hold.
  - **Edge steps (evaluation 2, same raw samples):** pass. Allocation +2.13 GiB external and +2.22 GiB drop, residual +0.09; release −1.99 external and −1.93 drop, residual +0.06; runner flat; each step in the first sample after its edge.
- **`tools/memory_validity.py` rule version 2** (rule-1 output kept as `memory-validity.rule1.json`):
  - classes CLEAN, INCONCLUSIVE and CONTAMINATED;
  - per-run post-run quiet window (tolerance 0.25 GiB, the same as the baseline);
  - preserved Phase 0 peaks;
  - worst case = max over CLEAN and INCONCLUSIVE, plus contaminated peaks less what external memory explains.
- **Classes now:** all six follow-up runs so far are INCONCLUSIVE.
  - 120b cache-8192 r1 has no 10 s window flat within 0.25 GiB after exit (spread 0.46–0.87 GiB); the orchestrator accepts the stricter reading.
  - 120b cache-8192 r2 (v3) peaked at 82.93 GiB (coldparallel) with −3.9 GiB post−pre. It is the preserved 120b cache-8192 worst case.
- **Worst cases now:**

  | Configuration | Worst case (GiB) |
  | --- | --- |
  | 120b cache 8192 | 82.93 |
  | 120b cache 4096 | 73.14 |
  | 120b cache 1 | 73.38 |
  | 20b cache 8192 | 26.89 |
  | 20b cache 1 | 23.64 |

### C12 recheck fixes F1–F5 (plan sha `21db523a…`, §9 item 9)

local-llms `c22c7ab`, pushed.
- **F1:** anchored roots (path plus dev/ino, never re-resolved; an untrusted root must be a real directory with a stable identity).
- **F2:** `O_NOFOLLOW | O_NONBLOCK` opens, fstat before any read, cancellation around opens.
- **F3:** `.state` directory created for in-place records.
- **F4:** the finished partial, including a resumed prefix, is re-hashed through its descriptor with stable fstat before publication.
- **F5:** planning abort signal, tripped by Stop, Cancel and drain before they queue.
- **Also:** the pre-launch re-hash shows as `verifying`.
- **Tests:** 15–21 in `tests/shared-models-recheck.test.mjs`. Each fix was mutation-checked; each mutation fails its own test. Full suite 317/317. All tests were run under `flock -x /home/research/phase0/.memlock`.
- **Deviation:** the messages of d68c70f and c22c7ab cite review file names ending in `_codex.md`, which breaks the no-agent-mention rule. Both are pushed to the feature branch. Rewording them needs a force-push of published history, so it is waiting for coordination.

### Commit-message correction on local-llms `local-llm-multiarch` (approved under the owner's delegation; 2026-09-28 21:38–21:40, all under `flock -x .memlock`)

Only the messages of two commits changed: each lost its reference to a review file whose name contains an agent name. Trees, parents' content, author and committer names, emails and dates, and every other message byte are unchanged. The original review reports and their SHAs stay as they were.

| Old commit | New commit | Tree (unchanged) | Parent |
| --- | --- | --- | --- |
| d68c70fe097e932ac6593d0e690f124583e8a52d | 104ecee7109af702ff3b85e10d5b1280b66e00fa | 0334f11543b24754daa20dfa61e2edc30f0952b5 | d3c6a94aa12ea100ac936248f40f9c6fe3a51b95 (unchanged) |
| c22c7abe1399df1219cc2d57630241efb5297c90 | 70047bd70b1cf97688a93e29e1882215f01ac081 | 8a26229a58d88fd14b2cc66b0c7fef54fe950ed5 | 104ecee7… (new d68) |

- **Removed text:**
  - d68c70f line 3: " (plans: local-llm-workspace-reuse-review_codex.md)";
  - c22c7ab line 3: " (plans: local-llm-workspace-reuse-recheck_codex.md)".
- **Before:** the worktree was clean, and local, origin/local-llm-multiarch and ls-remote all equalled c22c7abe; the parent chain was c22c7ab → d68c70f → d3c6a94.
- **Backup:**
  - bundle `/home/research/dev/backups/local-llms-local-llm-multiarch-c22c7abe-pre-reword-20260928T193835Z.bundle`, sha256 `d568e8667de9fe0dbee9b1e4afe894de01da48beca30ae232e95c175293a175a`;
  - `git bundle verify` reported "records a complete history", with head c22c7abe… refs/heads/local-llm-multiarch;
  - local ref `refs/backup/local-llm-multiarch-c22c7abe` → c22c7abe…;
  - the owner's delegate also holds a verified Mac bundle (`local-llms-pre-message-reword-20260928T1935_codex.bundle`).
- **Method:**
  - `git commit-tree <original tree> -p <parent>`, with GIT_AUTHOR_* and GIT_COMMITTER_* (name, email, raw date) copied from each original raw commit object;
  - messages taken from `git cat-file commit` with only the reference removed;
  - the repository's commit-msg hook passes both.
- **Checks (all OK):**
  - tree(new) == tree(old) for both;
  - parent(104ecee) == d3c6a94 and parent(70047bd) == 104ecee;
  - author and committer identical;
  - `git diff c22c7abe 70047bd` and `git diff d68c70f 104ecee` are empty;
  - the message diff is exactly the removed reference;
  - scanning all 15 feature commits (merge-base 03697765..70047bd) for codex, claude, anthropic, openai, gpt-N, model names, Co-Authored-By, "Generated with/by" and _codex found no hits.
- **Push:**
  - `git update-ref refs/heads/local-llm-multiarch 70047bd c22c7abe` (old-value guard);
  - `git push --force-with-lease=refs/heads/local-llm-multiarch:c22c7abe… origin refs/heads/local-llm-multiarch:refs/heads/local-llm-multiarch` → "+ c22c7ab...70047bd (forced update)";
  - ls-remote is now 70047bd70b1cf97688a93e29e1882215f01ac081;
  - origin/main is unchanged (03697765).
- **Other repositories:** the audit of the Ploinky (2 commits) and container-image-builds (2 commits) feature branches found no mentions; they were not touched.
- The owner's delegate also holds a verified Mac bundle: `dgx-local-llm-plan-sync/supervision-snapshots/local-llms-pre-message-reword-20260928T1935_codex.bundle` (ref `refs/supervision/pre-message-reword-20260928T1935`). The plan-review session re-checked the rewrite independently: ls-remote, trees, parents, identities, the empty diffs, the backup ref and bundle sha256, and the scan.

### Session restart: interrupted matrix, recovery and resume (21:31–21:42)

- **What stopped:** the remote process restart ended every process this session had started. That covers `tools/followup.sh`, harness v5 on `qwen-c256k-np1-mtpoff-cram8192-r1` (started 21:28:30), its sampler and `llama-server`. The last mem.csv sample was at 21:31:40.92 and the last attribution sample at 21:31:42.21. The server had loaded, finished greedy, and was prefilling 235,929 tokens (context checkpoint 2 of 32). There is no result JSON.
- **After the restart (checked 21:38):** no research-owned harness or llama process remained, nvidia-smi listed no compute apps, and `.memlock` was free.
- **Completed before the stop:** all 10 gpt-oss runs (rep 1 and rep 2) and `qwen-c128k-np4-mtpoff-cram8192-r1`.
- **Interrupted attempt:** marked in `results/followup/qwen-c256k-np1-mtpoff-cram8192-r1.INTERRUPTED.json`, with the sha256, size and mtime of its three raw files. The raw files are unchanged. It is not a sample, and the retry is `-r1-a2`.
- **Model identities, before any use:**
  - **gpt-oss-120b and Qwen3.6:** `sha256sum -c` passed after their downloads ended (19:59:53; the matrix started 20:01:38). Their ctimes (19:59:36 and 19:25:18) predate that hash and are unchanged, so the bytes cannot have changed since they were hashed. They were not re-hashed.
  - **gpt-oss-20b:** it has 2 links (the other is `gpu-test-workspace/.data/local-llm/phase1/…`) and a ctime of 17:57:11, after its original hash, so stat evidence was not enough. It was re-hashed under `flock -x` at 21:40:24 (7.6 s): OK against the catalog-pinned sha256.
- **Resume:**
  - `tools/followup-resume.sh` runs only the missing work in followup.sh's order: Qwen rep 1 (the interrupted configuration as `-a2`, then the six remaining), Qwen rep 2 (8), then stop-latency 120b load/active × KILL/TERM × r1/r2 (8).
  - It refuses any run whose output prefix already has files.
  - `tools/followup-reruns.sh` is then capped at **one** automatic round and parses attempt names; further rounds are a decision.
  - Both are launched as one detached writer, `tools/followup-continue.sh` (`setsid nohup`, PID in `logs/followup-continue.pid`, session 621181). This reduces the ordinary exposure to its parent session exiting; it does not prove the run survives host, logout or cgroup termination.
  - Before launch, no python/sh/llama writer was present. Launched 21:41:36.
  - Tools are unchanged: serve_check2 v5 `babbc54e…`, attribution `54ec1f0c…`, stop_latency v2 `7d3b7f4e…`, memsample `1beeda04…`, gpurun `ab441c05…`. Every run takes `.memlock` exclusively itself.
- **Check 4e, evaluation 3 (whole-window identity):** FAIL.
  - The residual (drop − external − runner) ranged −0.12 to +0.64 GiB (0.76 GiB) against a 0.3 limit.
  - After another user's ~5 GiB release, AnonPages fell at once, but MemAvailable came back about 0.5–0.6 GiB short, closing over about 15 s. Only this delayed recovery is established. Why it happens (for example, kernel accounting of freed memory) is a hypothesis until evidence separates it from unsampled contributions such as page cache, slab or other non-anonymous memory.
  - The edge-step pass therefore shows step detection only. The residual is not an acceptance filter.
- **Validity rule 3** (`tools/memory_validity.py`; rule-1 and rule-2 outputs kept):
  - no CONTAMINATED class and no reduced or excluded peak while attribution is unvalidated;
  - measured external movement can still deny CLEAN;
  - peaks are LOWER BOUNDS when memory ends ≥ 0.5 GiB above the baseline or a phase peak falls ≥ 0.5 GiB below at-ready;
  - `memory-validity.json` is regenerated from all 11 completed runs. None is CLEAN.

  Worst cases now (maximum of inconclusive and preserved Phase 0 peaks):

  | Configuration | Worst case (GiB) | Source |
  | --- | --- | --- |
  | 120b 8192 | 82.93 | r2 |
  | 120b 4096 | 78.27 | r2 |
  | 120b 1 | 76.21 | r2, lower bound |
  | 20b 8192 | 26.89 | |
  | 20b 1 | 23.64 | |
  | Qwen 128K×4 MTP off 8192 | 35.13 | lower bound |

  The earlier 73.14 and 73.38 for 120b 4096 and 1 were stale; they predated the r2 runs.

### Decision of 2026-09-28 ~21:45 (Codex, under the owner's delegation, relayed by the plan review) and scheduling changes

- **Finish:** the running and missing functional matrix and the stop-latency runs, keeping every attempt.
- **No aborts:** a functional run is never aborted because an external-memory proxy moved. Such a run is INCONCLUSIVE, keeps full stress coverage and its peaks, and is requeued only within the one bounded round. Unvalidated attribution never becomes a filter that hides peaks.
- **One automatic rerun round, with a quiet-host scheduling gate.** No further automatic rounds are approved.
- **Other users' workloads:** not stopped and not contacted.
- **Constants:** the maximum of inconclusive or lower-bound peaks is **not** an established safe constant, because a masked lower bound is not a conservative upper bound. The worst observed peaks are kept with their unresolved uncertainty. Unvalidated model and configuration envelopes stay UNAVAILABLE. There is no release acceptance without clean, agreeing evidence or an independently justified upper-bound method, and no new margin or guard constant.
- **Wording corrected above:** the MemAvailable recovery lag is a hypothesis about its cause; `setsid nohup` only reduces exposure to the parent exiting.

**Scheduling changes (harness v6, installed 21:47:44 between runs; measurement unchanged):**

| File | sha256 |
| --- | --- |
| `serve_check2.py` | c00de363197845ad9d2524e03e3c2d1bf7d83b4fce43e239bd7675d278b348de |
| `attribution.py` | bf903041b0287b0b169c535612b3745742687627d298cb04cfbc88bc104db111 |
| `quietgate.py` (new) | d1c59c22e1067c7816fe1c9e561c693c24f7c6a3f0a857a0d49f1c0239590d0e |
| `followup-reruns.sh` | 8015dd3a574c318f4b3121d25041f2b965e7be246c4d1142d17148145d1645d3 |
| `stop_latency.py` (unchanged; takes the lock through `memlock()`) | 7d3b7f4e… |

Archived: `serve_check2.v5.py.txt`, `attribution.v5.py.txt`, `followup-reruns.v2.sh.txt`.

1. **Lock yield and log.** `memlock()` sleeps 5 s before asking for the exclusive lock, so a waiter blocked in `flock` (the C12 recheck's fixtures) gets it between matrix runs; flock is not FIFO. It logs every grant to `logs/memlock.log`, noting when another process held the lock.
2. **Quiet gate** (`--quiet-gate`, used only by the one rerun round):
   - without the lock, wait until non-runner memory ((AnonPages + Shmem), with no runner running) holds within 0.25 GiB for 60 s;
   - take the lock and re-check for 20 s under it; if the host moved, release the lock and wait again;
   - after 30 min, defer: write `<out>.DEFERRED.json` and nothing else, and report it at the end of the round.

   The lock is never held while waiting. The gate is a heuristic: it validates nothing and does not make a run clean.
3. **`memory_validity.py`** lists deferrals. `attribution-check.json` evaluation 3 carries the hypothesis wording.
