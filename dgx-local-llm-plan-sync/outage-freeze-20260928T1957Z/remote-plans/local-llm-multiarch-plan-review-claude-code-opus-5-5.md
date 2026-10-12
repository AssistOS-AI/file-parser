Reviewer: claude-code-opus-5-5
Date: 2026-09-28
Plan: /home/research/work/plans/local-llm-multiarch-plan.md, sha256 a8f8085be85a747eac8292cd8f49a978f4028cafb7abb3b3ae7044700dac2d10, modified 2026-09-28 13:43:48.575710739 +0200

# Review: run `local-llms/local-llm` on NVIDIA DGX Spark through a multi-arch image

- **Plan version.** This is the version that builds llama.cpp from source, adds MTP and uses a three-way Phase 0. I began on an earlier version; the plan's author told me about the change, and I re-read and reviewed this one. It did not change again before I finished (same sha256 at 14:11).
- **Scope of changes.** None. The review was read-only: no repository, image, Box or agent was changed, and every repository's `git status` is clean afterwards.
- **Scratch directory.** `/tmp/claude-1002/-home-research-work/8bfd08cf-9225-4b6c-b766-b7917428a572/scratchpad/`, written `scratch/` below.
- **GPU experiments.** A few small, transient runs, listed as M1–M6 in section 2. The largest allocated 56 GiB, stayed about 50 GiB below MemAvailable, then freed everything. Nothing else was using the GPU.
- **Prompt revision.** At 13:48 the review prompt added a rule against building software and running benchmarks. I only read that revision after these runs.
  - What ran: throwaway programs of a few lines, compiled with the host's `nvcc` (M1–M6); and, by a helper, a CMake configure of a one-kernel test (row 8).
  - What did not happen: no project software was built, no model was run, and nothing was installed.
  - If you want only Phase 0 numbers, treat M3–M6 as leads; section 4, item 22, re-measures them.

## 1. Verdict

The one-agent, multi-arch decision holds, and I found no evidence against it. The registry mechanics are as the plan describes. `ploinky-node` is pinned by an index. `local-llm` is pinned by one amd64 manifest with no attestations, and the workflow's own candidate step already wraps that manifest in an index. Ploinky's dependency cache already keys everything by in-container architecture. I ran Ploinky's own `discoverNvidiaGpu` read-only on this host with only the ldconfig flag rewritten, and discovery succeeds, so A1 is the only host-side x86 assumption.

**What can start now.** Phase 1 (A1) can start now. The host-level half of Phase 0 can start today in parallel: the host has CUDA 13.0 and nvidia-container-toolkit 1.19.1, so it needs neither A1 nor the Box.

**What must change before Phase 2:**

1. **Memory safety on unified memory.** I measured that GB10 GPU memory is invisible to process RSS, to the OOM killer's score and to memory cgroups. The GPU also allocates and touches memory at about 28 GiB/s. So the planned 2-second MemAvailable guard cannot contain a bad estimate, and the kernel would kill the wrong process.
2. **The x86 regression gate.** It must move from Phase 3 to Phase 2, because the shared JavaScript reaches x86 hosts in Phase 2.
3. **How the detected profile reaches the code.** The plan must say how it reaches the static runner adapters, the catalog and the Run path. As the code stands, an arm64 image would download weights for ik_llama.cpp or TabbyAPI and then fail at launch.
4. **The Phase 0 disk budget.** 40 GB is two to four times too small for the listed experiments, on a disk the live workspace shares.

**Before Phase 3:** decide what vLLM does on arm64 until Phase 4, because the arm64 lock would ship it earlier. Also decide how FlashInfer works without run-time downloads.

**D** can start once its dependencies on the specs are handled.

**Admitting against MemAvailable is sound.** CUDA allocations on GB10 do reclaim page cache. On integrated GPUs, llama.cpp b11159, Ollama 0.34.4 and vLLM 0.30.0 all size themselves from MemAvailable.

## 2. Fact check

| # | Claim (plan section) | Verdict | Evidence |
| --- | --- | --- | --- |
| 1 | DGX Spark (Lenovo OEM), DGX OS 7.2.3, Ubuntu 24.04, kernel 6.17, aarch64 (§3) | Confirmed, one correction | `/etc/dgx-release` has `DGX_SWBUILD_VERSION="7.2.3"` but also `DGX_OTA_VERSION="7.5.0"` (2026-05-21), so the running OS is OTA 7.5.0. `DGX_PLATFORM="30KL0004GF"`; `Ubuntu 24.04.4 LTS`; `6.17.0-1018-nvidia … aarch64`. |
| 2 | GB10, compute capability 12.1, driver 580.159.03, CUDA 13.0 | Confirmed | `NVIDIA GB10, 12.1, 580.159.03`; the nvidia-smi header says `CUDA Version: 13.0`; `/proc/driver/nvidia/version` says Open Kernel Module 580.159.03. |
| 3 | nvidia-smi reports GPU memory as `[N/A]` | Confirmed | Output is `[N/A], [N/A], [N/A]`. Also: `addressing_mode` is `ATS`. Per-process `used_memory` *is* numeric (`984215, 4266` for a 4 GiB test allocation). `utilization.gpu,power.draw,temperature.gpu,compute_cap` gives `0, 10.70, 43, 12.1`. |
| 4 | 119.6 GiB MemTotal, no swap | Confirmed | `MemTotal: 125442396 kB` (119.63 GiB), `SwapTotal: 0 kB`. |
| 5 | 20 cores: 10 Cortex-X925 + 10 Cortex-A725 | Confirmed | `lscpu`. MIDR part `0xd85` (X925) on cpu5–9 and 15–19, with sysfs `cpu_capacity` 997–1024. Part `0xd87` (A725) on cpu0–4 and 10–14, capacity 718–731. The agent's `physicalCoreCount()` gives 20, so `defaultThreads` is 18. |
| 6 | 1 TB NVMe, about 132 GB free | Confirmed | `/dev/nvme0n1p2 916G 738G 132G 85% /`. |
| 7 | Single Spark; all ConnectX-7 ports down | Confirmed | `ibdev2netdev` shows four ports `(Down)`; `ip -br link` shows `enp1s0f0np0 … DOWN` and the others down. |
| 8 | Host has CUDA 13.0 and cmake 3.28; 3.28 is enough for `121a-real`; only `f` needs 3.31.8+ (updated §3) | Confirmed | nvcc `V13.0.88`; `cmake 3.28.3`. The regex at `/usr/share/cmake-3.28/Modules/Internal/CMakeCUDAArchitecturesValidate.cmake:8` accepts `a?` only. A throwaway configure and build with `121a-real` emitted `code=[sm_121a]`; `121f` fails with "is not one of the following" (`scratch/llamacpp/cmaketest/`). |
| 9 | Explorer enables `local-llms/local-llm no-wait` | Confirmed | `AchillesIDE/explorer/manifest.json:28`. |
| 10 | The Box pulled the amd64 image (4.57 GB, 620 s) and the launch failed with `Exec format error` | Confirmed | Log: `[pull] … ready — 4.57 GB unpacked in 620s`, then `WARNING: image platform (linux/amd64) does not match the expected platform (linux/arm64)`, then `exec container process /usr/local/bin/node: Exec format error`. It fails in the runtime-key probe (`ploinky/cli/utils/dependencies/dependencyRuntimeKey.js:151`), before the agent starts. The dead image is still in the Box store: `docker.io/assistos/local-llm … 4.91 GB`. |
| 11 | `ploinky gpu status` reports libcuda missing because of `gpuGrant.mjs:239` | Confirmed | `Host GPU: unavailable (NVIDIA driver library libcuda.so.1 is not in the ldconfig cache)`. `ldconfig -p` shows `libcuda.so.1 (libc6,AArch64) => /lib/aarch64-linux-gnu/libcuda.so.1`. |
| 12 | Nothing else in the host GPU grant path assumes x86 or a discrete GPU (prompt) | Confirmed | `scratch/a1-sim.mjs` calls the real `discoverNvidiaGpu` with the host's ldconfig output, changing only `AArch64` to `x86-64`. Discovery succeeds: 3 device nodes, read-write; `libcuda.so.1`, `libnvidia-ptxjitcompiler.so.1`, `libnvidia-ml.so.1`, `libnvidia-nvvm.so.4` and `libnvidia-gpucomp.so.580.159.03` all resolve to `…so.580.159.03`; `nvidia-smi` found. CDI rendering, fingerprint and marker (`gpuGrant.mjs:397-527`) carry no architecture data. `nvidia-smi` and `libcuda` need only glibc (`ldd`). `tests/unit/ploinkyBoxGpuGrant.test.mjs` passes 54/54; its fixture hard-codes `(libc6,x86-64)` at `:101`. |
| 13 | With `[N/A]`, admission approves every model (§3) | Confirmed for GPU memory, with limits | `scratch/nan-repro/repro.mjs` imports the agent's own modules and feeds them GB10's exact nvidia-smi line. `readGpu` then returns NaN for total, used and free. A 500 GiB GGUF on llama.cpp is `ok`; a 400 GiB Ollama tag is `ok` (with `ramBytes` NaN); vLLM with an admin `gpuMemoryUtilization` of 0.9 is `ok`. Not every comparison fails, though: the RAM check still refuses `nCpuMoe 60` (450.8 GiB of RAM), and the disk check still refuses a download larger than free disk. Without an admin value, vLLM gets `gpuMemoryUtilization: NaN` and fails at launch with `invalid_launch` (`src/runners/vllm.mjs:115-117`). |
| 14 | `ploinky-node` `sha256:accd925f…` is an OCI index with amd64 and arm64, resolved to arm64 here | Confirmed | `skopeo inspect --raw` shows `application/vnd.oci.image.index.v1+json` with amd64 `14c2ae03…` and arm64 `1f9f1234…`, and no attestation entries. In the Box, image `07fd7e99fa11` is `arm64` and its RepoDigests hold both digests. `podman image inspect …@sha256:accd925f…` resolves to it. Pinned at `AchillesIDE/explorer/manifest.json:2`. |
| 15 | `local-llm` pins a single amd64 manifest | Confirmed | `…@sha256:b6c79af2…` is `application/vnd.oci.image.manifest.v1+json`. Config: `architecture: amd64`, `User 1000:1000`, 11 layers (3.20 GB compressed), label revision `95ba10a…`. |
| 16 | Reusing `b6c79…` inside a new index with `imagetools create` works, including provenance and attestations (prompt) | Confirmed | No attestations exist: the image was pushed with `provenance: false` (`publish-local-llm-image.yml:73`), and the OCI referrers API for `b6c79` returns `{"manifests":[]}`. The workflow's own candidate step (`:155`) already wraps `b6c79` in an index: `candidate-36131512550-1` is OCI index `sha256:2f91e807…` with one member, `b6c79` `linux/amd64`. Combining it with an arm64 digest is the same operation as `publish-ploinky-node-image.yml:178-195`. |
| 17 | Ploinky pulls with no `--platform`; only `runtimePolicy.platform` adds one | Confirmed | `ploinky/cli/sandbox/docker/common.js:196`; `containerRuntimePolicy.js:262`. |
| 18 | The `ploinky-node` workflow builds natively per platform, pushes by digest, proves each, then assembles | Confirmed | `publish-ploinky-node-image.yml:27-38` (matrix `ubuntu-24.04` / `ubuntu-24.04-arm`), `:71` (`provenance: false`), `:178-195` (create, then member check). |
| 19 | The runtime base is the same index; the amd64 lock-in is at `Dockerfile:54` | Confirmed | `images/local-llm/Dockerfile:40` is `FROM …@sha256:accd925f…`; `:54` is `test "${TARGETARCH:-amd64}" = amd64;`. |
| 20 | Ploinky's dependency cache and runtime-key probe with an image that differs by platform (prompt) | Confirmed: no change needed | The runtime key comes from `process.arch` inside the image (`dependencyRuntimeKey.js:102-125`), so it is `container-linux-arm64-glibc-node24` vs `container-linux-x64-glibc-node24`. Cache paths are keyed by it (`dependencyCache.js:59-69`). The stamp includes the `image` string (`dependencyCache.js:281`), so the pin change causes one reinstall per host. `tests/unit/dependencyRuntimeKey.test.mjs` does not load outside a Ploinky-started environment (`PLOINKY_AGENTLIB_DIR is not set`), so this row rests on reading the code. |
| 21 | `ploinky-box:latest` is multi-arch and the arm64 variant runs here | Confirmed | The Box `ploinky-box-work-287e15733c26` runs it; inside, `uname -m` is `aarch64`, Fedora 44, podman 5.8.2. `publish-ploinky-box-image.yml:53-57` has an amd64/arm64 matrix. |
| 22 | The Box needs no new image: no NVIDIA userland, hookless CDI (§3, §4.A) | Confirmed by code; CDI not yet exercised | `images/ploinky-box/Dockerfile` has no GPU packages; its only architecture branch is cloudflared's sha256 (`:75-79`). The CDI spec is plain JSON read by podman 5.8.2, whose CDI support does not depend on architecture. There is no `/etc/cdi` in the Box today because discovery fails, so the nested CDI path on arm64 stays untested until A1. |
| 23 | The Box mounts the host checkout read-only at `/opt/ploinky` | Confirmed | `podman inspect` shows `/home/research/work/ploinky -> /opt/ploinky (bind rw=false)`, plus `.ploinky/box/images -> …/ploinky-images` (read-write). |
| 24 | Box constraints (pids, cgroups, shm) | Confirmed | `PidsLimit=2048`, with `pids.current` already at 727 for 15 agents. The Box has `Memory=0`, and its cgroup has `memory.max` = `max`. The in-Box `containers.conf` says `cgroups="disabled"`. The shm cap of 16g is at `ploinky/cli/sandbox/runtimeCapabilities.js:242-244`. |
| 25 | llama.cpp b11159's `ubuntu-cuda-13.4-arm64` asset, and how ggml-org builds it (updated §3) | Confirmed, except the binary itself | Assets: `llama-b11159-bin-ubuntu-cuda-13.4-arm64.tar.gz` (139 MB, sha256 `258c9dc7…7644b`) and `cudart-…-13.4-arm64.tar.gz` (527 MB, `34d8602d…11bfa`). `release.yml:316-453`: `ubuntu-24.04-arm`, `nvidia/cuda:13.4.1-devel-ubuntu24.04`, no `CMAKE_CUDA_ARCHITECTURES`, `GGML_NATIVE=OFF GGML_CPU_ALL_VARIANTS=ON GGML_BACKEND_DL=ON`, gcc-14. The default list for CUDA ≥ 13 is `75-virtual;80-virtual;86-real;89-real;90-virtual;120a-real;121a-real` (`ggml/src/ggml-cuda/CMakeLists.txt:30-55`). Not checked: the cubins inside the shipped `libggml-cuda.so`, which needs the 139 MB download. |
| 26 | The 13.4 build runs on the 580 / 13.0 driver without a forward-compatibility package | Confirmed from documentation; not run | The CUDA Compatibility guide says "CUDA 13.x \| >= 580". The 13.4 U1 notes say "Existing CUDA 13.x applications run on drivers >=580 under CUDA minor version compatibility"; only new 13.4 features need R615+. JIT of PTX from a newer toolkit is unsupported, but `121a-real` code needs no JIT. `cuda-compat` covers only data-center GPUs, some RTX server SKUs and Jetson, so it is not an option on GB10 anyway. |
| 27 | NVIDIA's playbook builds with the quoted cmake line, updated 06/03/2026 (updated §4.B.2) | Confirmed, with notes | `NVIDIA/dgx-spark-playbooks`, `nvidia/llama-cpp/README.md`. The playbook clones llama.cpp master with no pin and uses the host toolkit. It runs with defaults (4 slots, `n_ctx = 262144`) plus the MTP flags. `GGML_CURL` is not an option at b11159, so it is silently ignored. |
| 28 | "GPU code does not depend on the build machine" (updated §4.B.2) | Confirmed | `GGML_NATIVE` is read only inside `if (NOT DEFINED CMAKE_CUDA_ARCHITECTURES)` (`ggml-cuda/CMakeLists.txt:27`). nvcc emits `sm_121a` without using a GPU. |
| 29 | CPU variants: "gcc-14 for the armv9.2 variant … the best CPU variant, including armv9.2, is picked at run time" | Partly refuted | The armv9.2 variants require SME (`armv9.2-a+…+sme`), and the X925/A725 have no SME (`lscpu` flags). So `cpu-feats.cpp` picks `armv8.6_2` = `armv8.6-a+dotprod+fp16+sve+i8mm+sve2`, which gcc 13 already builds. gcc-14 adds nothing on this machine. |
| 30 | Phase 0 reference (1), "a native build on the host exactly as the playbook does it", is the reference | Refuted for CPU code | The host's gcc 13.3 cannot resolve `-mcpu=native` on this CPU. `gcc -mcpu=native -Q --help=target` prints empty `-mcpu=` and `-march=`. The predefined macros show `__ARM_ARCH 8` and none of `__ARM_FEATURE_SVE`, `SVE2`, `MATMUL_INT8`, `BF16` or `DOTPROD`. llama.cpp's feature probe `-mcpu=native+dotprod` is rejected. So (1) is baseline armv8-a on the CPU side, while (2) is `armv8.6_2`; the GPU code is identical. |
| 30a | The in-image CI build (`121a-real`, `GGML_NATIVE=OFF`, CPU variants chosen at run time, CUDA 13.0 builder) performs like the playbook's native build (updated §4.B.2, prompt) | Unverifiable here; expected equal or better | The GPU code is identical for the same nvcc and architecture flags (row 28). The CPU code is equal or better, because (2) gets `armv8.6_2` while the host's native build gets baseline armv8-a (rows 29, 30). Only the Phase 0 llama-bench comparison settles performance, run with identical runtime flags plus a correctness check (F8). |
| 30b | CUDA 13.0 in the builder is the right match for the 580 driver (prompt) | Confirmed, with a trade-off | 580 is the CUDA 13.0 driver branch and the host toolkit is 13.0.88, so a 13.0 build needs no minor-version compatibility. It matches the playbook's environment and torch's `cuda-toolkit==13.0.3`. The trade-off: CUDA 13.0 bundles CCCL 3.0.1, so llama.cpp's CUB top-k path (CCCL ≥ 3.2) falls back to argsort unless `GGML_CUDA_CUB_3DOT2=ON` fetches CCCL during configure. |
| 31 | MTP: `--spec-type draft-mtp --spec-draft-n-max 3` (updated C5) | Confirmed at b11159 | `common/arg.cpp:4245`, with `draft-mtp` defined at `speculative.cpp:37`; `:4136` (`--spec-draft-n-max`, default 3). |
| 32 | C5's `--no-mmap` | Refuted for b11159 | `--mmap`, `--no-mmap`, `--mlock` and `--direct-io` were removed in b10875; b11159 has only `-lm, --load-mode {auto,none,mmap,mlock,mmap+mlock,dio}` (`arg.cpp:2687`), and an unknown flag fails with "invalid argument". The adapter already maps `noMmap` to `--load-mode none` (`src/runners/llamaCpp.mjs:4-12`); its comment's "b11125" should say b10105/b10875. |
| 33 | Ollama v0.34.4 ships `ollama-linux-arm64.tar.zst` (1.5 GB) and supports GB10 (§3) | Confirmed, with a caveat | 1,549,684,612 bytes, sha256 `96f50a11…7fd7e6`; `docs/gpu.mdx` lists "12.1 \| GB10 (DGX Spark)". There is no sm_121 SASS, though. `cuda_v12` is built for `…;120`, which llama.cpp rewrites to `120a` (runs only on 12.0). `cuda_v13` is PTX-only (`…;120-virtual;121-virtual`, giving `compute_121a`). So on GB10 the driver JIT-compiles Ollama's GPU code on first load (`llama/server/CMakePresets.json`; `discover/llama_server.go` skips runners whose ARCHS lack 1210). |
| 34 | vLLM 0.30.0 aarch64 wheel; torch 2.13 on `cuda-toolkit==13.0.3`; cp313 aarch64; flashinfer; cutlass-dsl (§3) | Confirmed; closure complete | `vllm-0.30.0-cp38-abi3-manylinux_2_28_aarch64.whl` (309,984,160 B). `torch-2.13.0-cp313-cp313-manylinux_2_28_aarch64.whl` requires `cuda-toolkit[cublas,cudart,cufft,cufile,cupti,curand,cusolver,cusparse,nvjitlink,nvrtc,nvtx]==13.0.3`. All 196 distributions in the amd64 lock exist for cp313 aarch64 at the same versions (91 platform wheels to replace, 105 identical files). None is sdist-only, and all come from `files.pythonhosted.org`. Size: 3.94 GB vs 3.88 GB (`scratch/vllm-closure/vllm-0.30.0-aarch64-cp313-availability.tsv`). `nvidia-cutlass-dsl[cu13]==4.7.1` still pulls `libs-cu12`; nvcc/nvvm arrive at 13.2.86 and nvdisasm at 13.4.92 through `humming-kernels[cu13]`. |
| 35 | vLLM's sm_121 kernel coverage is "unverified" (§3) | Confirmed from build configuration; not run | The aarch64 wheel is built with CUDA 13.0.2 for `8.0 8.7 8.9 9.0 10.0 11.0 12.0`. The NVFP4, FP8, Marlin and MoE kernels use `12.0f`, which covers 12.1. FlashAttention 2 is `8.0+PTX`, so it is JIT-compiled on GB10. torch's v2.13.0 build script lists `sm_120` SASS for aarch64, with no PTX. Triton 3.7.1 maps 12.1 to `sm_121a` and bundles `ptxas-blackwell` 13.1.80. FlashInfer needs a CUDA toolkit at run time (finding 5). |
| 36 | ik_llama.cpp, TabbyAPI and LM Studio are x86-only | Confirmed | ik_llama.cpp is built in an amd64 `nvidia/cuda` stage for `86-real;89-real` (`Dockerfile:1-38`). The TabbyAPI lock pins `exllamav3 1.5.1+cu128.torch2.9.0` and `torch 2.9.0+cu128`. LM Studio's lock file is `0.0.25-1-linux-x64.full+cuda12.tar.gz`, and `src/runners/lmStudio.mjs:37` names `llama.cpp-linux-x86_64-nvidia-cuda12-avx2-2.41.0`. |
| 37 | A1: "Update README wording that says x86-64" | Refuted (minor) | `grep -n -i x86 ploinky/README.md` finds nothing. The only x86-64 wording is the code comment at `gpuGrant.mjs:232`. |
| 38 | A2: `libnvidia-nvvm70.so.4`'s real file is not named with the driver version | Confirmed | It is a regular 21 MB file. `libcuda.so.580.159.03` contains the string `libnvidia-nvvm70.so.4`. NVIDIA's own `nvidia-ctk cdi generate` (1.19.1) does not mount it. |
| 39 | C1: utilization, power and temperature report on GB10 | Confirmed | See row 3. |
| 40 | C7: 8,192 tokens and 570 s | Confirmed | `src/chatResponder.mjs:76-77`. |
| 41 | C8: the dashboard reads `gpu.totalBytes` / `usedBytes` | Confirmed | `local-llm-dashboard-view.js:69-71, 357`. NaN arrives as `null`, because the control socket speaks JSON. |
| 42 | C9: two LM Studio tests fail on this 20-core host | Confirmed | `node --test 'local-llm/tests/*.test.mjs'`: 255 tests, 253 pass, 2 fail, both with `--threads is 12, expected 18` (`tests/lmstudio.test.mjs`). `container-image-builds` `--test-name-pattern=local-llm`: 7/7 pass. |
| 43 | D: "the eleven legacy agents (the manager and ten model agents)" | Refuted | The plan lists 12 names and 12 directories exist. `local-llms/AGENTS.md:5` says "twelve Ploinky agents … One manager agent … eleven model-serving agents". |
| 44 | D: nothing depends on the legacy agents | Confirmed for what is on this machine | A grep over `.ploinky/repos/*`, `ploinky/` and `AdvancedLanguageAgent/` finds only the fixture string `planning-local` (`ploinky/tests/unit/llmArchitectureSelector.test.mjs:133`). `.ploinky/agents.json` enables none of them, and Ploinky core has no reference. AchillesAgentLib's copy in the Box image (`/opt/ploinky-agentlib`) has only a comment and a test fixture naming `agent:llm-runtime/base-local`, which is a different repository's agent (`LLMAgents/openAiAgenticResponder.mjs:82`, `.test.mjs:42`). Docker Hub still serves `assistos/local-llms:latest` (arm64-only, 2.9 GB, 205 pulls, last push 2026-05-27). |
| 45 | Soul Gateway: 120 s default deadline (§3, consumer side) | Confirmed; I did not check the reasoning-field claim | `proxies/soul-gateway/src/db/dao/models-dao.mjs:22` (`requestTimeoutMs = 120000`) and `src/runtime/execution/timeout-middleware.mjs:148`. |

### Measurements made for this review (`scratch/cudaq/`, host CUDA 13.0)

- **M1: GB10 reports itself as integrated.** `cudaGetDeviceProperties` gives `integrated=1`, `pageableMemoryAccessUsesHostPageTables=1`, `totalGlobalMem=119.63 GiB`.
- **M2: `cudaMemGetInfo` reports MemFree, not MemAvailable.** It returned `free=48.23 GiB` while `/proc/meminfo` showed `MemFree 48.23`, `MemAvailable 106.34`, `Cached 53.92`.
- **M3: CUDA allocations reclaim clean page cache.**
  - 56 allocations of 1 GiB, each `cudaMalloc` + `cudaMemset`, starting from `MemFree 48.02`: all succeeded.
  - `Cached` fell from 53.93 to 44.10 GiB, and `MemAvailable` fell from 106.14 to 49.87 GiB.
  - `cudaMemGetInfo` tracked MemFree the whole time. Everything was freed afterwards.
- **M4: GB10 allocates fast.** 16 × 1 GiB `cudaMalloc` + `cudaMemset` took 0.58 s, about 27.8 GiB/s.
- **M5: GPU memory is not in RSS or the OOM score.** A process holding 4 GiB (4266 MiB in nvidia-smi) had `VmRSS 98844 kB` and `oom_score 666`, which is the baseline for `oom_score_adj` 0 on this kernel.
- **M6: GPU memory is not charged to memory cgroups.**
  - Under `systemd-run --user --scope -p MemoryMax=2G`, the same 4 GiB hold ran, and its scope's `memory.current` was 70 MiB.
  - Control: a Python process allocating 3 GiB of CPU memory in the same kind of scope was killed (exit 137).

## 3. Findings (most severe first)

### F1. Major: memory safety on unified memory rests on a guard that is too slow and an OOM killer that cannot see the runner

**Where:** C2, C3; `local-llm/src/controller/deployments.mjs:100-105, 530-560`.

**What is wrong.** The plan makes the memory guard "always on" in the unified profile and treats it as the backstop. On GB10 it is the only protection there is, and as built it cannot catch an overshoot:

- It samples MemAvailable every 2 s while loading and every 10 s once ready (`deployments.mjs:104-105`). GB10 allocates and touches memory at about 28 GiB/s (M4), so up to about 55 GiB can go between two samples. A KV cache for a long context is a single allocation.
- The kernel OOM killer will not pick the runner. Its GPU memory is not in its RSS or OOM score (M5), so the victim is whichever process has the largest RSS and `oom_score_adj`: the Box's Node processes, another agent, or the desktop.
- Memory cgroups do not contain GPU memory either (M6). Neither the Box (`Memory=0`, `memory.max=max`) nor any future per-agent limit would bound a runner. Nested cgroups are disabled anyway.
- There is no swap, so nothing slows down before the OOM kill.
- Estimates can be wrong in both directions. NVIDIA's July 2026 driver notes say the driver "enhances Out-of-Memory (OOM) handling" on GB10. An unanswered forum report (t/384326, 2026-09-26) shows `CUDA_ERROR_OUT_OF_MEMORY` at context creation with 67–74 GiB MemAvailable on driver 580.173.02.

**Fix (C3, Phase 2):**

1. Start every runner with `oom_score_adj=1000`. Raising it needs no privilege: write `/proc/<pid>/oom_score_adj` right after spawn and before the model loads; children inherit it. An overshoot then kills the runner, and the driver frees its memory.
2. Sample every 250 ms while loading and every 2 s once ready; a `/proc/meminfo` read costs microseconds. Also read `/proc/pressure/memory` and stop the runner when `full avg10` rises.
3. Size the floor for the gap between samples: max(4 GiB, 5 % of MemTotal) plus a margin.
4. Treat admission as the real control, because one large allocation outruns any sampling. Record in DS003 that on unified memory, admission plus `oom_score_adj` are the containment, and that cgroup limits do not apply to GPU allocations.

### F2. Major: the x86 regression gate comes after the shared code ships

**Where:** §5 Phases 2–3; C1, C5, C7.

**What is wrong.** The agent's JavaScript is mounted from the repo at `/code`, so C reaches every x86 host as soon as `local-llms` main moves in Phase 2. The plan's only x86 hardware check ("Re-test on an x86 GPU host") is in Phase 3. C touches x86 behaviour in places GPU-less CI cannot judge:

- **Fail-closed on telemetry.** C1 says "any non-finite value is unknown, and runs are refused" and also adds utilization, power and temperature. Laptop GPUs often report `power.draw` as `[N/A]`; GB10 itself reports `Current Power Limit: N/A`. If the rule covers those fields, x86 laptops lose their GPU.
- **One nvidia-smi query.** `readGpu` sends a single `--query-gpu` (`hardware.mjs:28-31`). A field an older driver does not know fails the whole call, and the GPU is marked unavailable (`hardware.mjs:32-45`).
- **Thread default.** C1's "performance cores" default: on an Intel hybrid laptop, a P-core rule would change today's "physical cores − 2", which `tests/cpu-cores.test.mjs:57-63` and `tests/runner-characterization.test.mjs` pin.
- **Shared schema.** The context maximum, a load-mode enum, MTP parameters and the chat limits (C7) change for everyone.

**Fix.** Gate the Phase 2 merge, not Phase 3, on:

- `tests/runner-characterization.test.mjs` passing unchanged for the dedicated profile (it pins the exact argv and probes);
- a golden `readGpu` test using today's x86 nvidia-smi output;
- a manual gpt-oss-20b run on the x86 GPU host with llama.cpp and Ollama.

Also:

- Fail closed only on the memory fields admission uses.
- Put new fields in a second query whose failure never disables the GPU.
- Change the thread default only where sysfs `cpu_capacity` shows mixed cores. It is readable in containers; here X925 is 997–1024 and A725 is 718–731.

### F3. Major: the plan does not say how the detected profile reaches the adapters, the catalog and the Run path

**Where:** C4, C5, C6.

**What is wrong.**

- **The adapters are static.** They are module-level singletons with static fields:
  - All six report `supported: true` (checked by importing `src/runners/index.mjs`), so C4's "existing `supported` / `unsupportedReason` fields" are constants.
  - `LLAMA_SERVER_PARAM_SCHEMA` is deep-frozen with `ctxSize.maximum 131072` and `ubatchSize.default 512` (`src/runners/llamaServer.mjs:27-105`).
  - `admit: admitLlamaServer` is fixed (`:236`).
- **Run downloads before it finds out the runner is missing.**
  - Before admission and download, Run checks only the static `supported` and whether the lock can install the runner (`src/controller/deployments.mjs:796-806`); detection results are not consulted for runners baked into the image.
  - On an arm64 image without ik_llama.cpp, Run on `ik_llama.cpp` downloads the GGUF (12–77 GB for the proposed models) and then fails with ENOENT at launch.
  - TabbyAPI, absent from an arm64 lock, counts as "not installable" and goes the same way.
- **The catalog seam is the wrong tool.**
  - `LOCAL_LLM_CATALOG_FILE` is a test and development seam, read once when the controller is built (`deployments.mjs:68-70`), before any hardware snapshot.
  - Setting it in the arm64 image would choose the catalog by CPU architecture, which C1 rules out.
  - Seed `recommended` values are keyed by runner only. gpt-oss-20b's (`nCpuMoe 17, batchSize 256, ubatchSize 256`) are tuned for a 6 GB GPU.

**Fix (C, Phase 2):**

- The controller derives the profile from the first snapshot at start, logs it, and keeps it for the container's lifetime.
- Pass `profile` into `normalizeParams` and `admit`, and add a `paramSchemaFor(profile)` that the overview and the dashboard use.
- Work out runner availability at start from what the image contains: the executable exists, or the lock has an entry. Run then refuses with a new `runner_unavailable` code before any download.
- Carry per-profile `recommended` either in one seed catalog (catalog v3 plus a registry migration) or in two seed files under `/code/catalog` chosen by profile. Do not use the environment seam.

### F4. Major: Phase 0 does not fit its disk budget and would disturb the live workspace

**Where:** §5 Phase 0.

**What is wrong.**

- **Weights alone exceed the budget.**
  - The disk is shared with the live workspace: 132 GB free, 85 % used.
  - Weight sizes for the listed benchmarks, from the Hugging Face API: gpt-oss-120b MXFP4 63.4 GB (one file); Qwen3.6-35B-A3B-MTP UD-Q4_K_XL 22.9 GB (37.8 GB at Q8_0); Qwen3-Coder-30B-A3B Q8_0 32.5; GLM-4.7-Flash Q8_0 31.8; gpt-oss-20b 12.1.
  - The vLLM aarch64 wheels are 3.94 GB before the venv is built, and vLLM needs separate safetensors snapshots (`openai/gpt-oss-120b` is 65.2 GB).
  - A three-way llama-bench on gpt-oss-20b, Qwen3.6-35B and gpt-oss-120b needs about 100 GB of weights by itself. "About 40 GB" covers the images and one small model.
- **Disk already wasted.** The Box already holds the dead 4.91 GB amd64 `local-llm` image (`.ploinky/box/images` is 13 GB).
- **The live workspace would be disturbed.**
  - A1 applied to the live workspace recreates its Box (a new GPU wiring label), which restarts its 15 agents.
  - Ploinky has no local build hook (`LOCAL_IMAGE_BUILD_DEFINITIONS = {}`, `ploinky/cli/sandbox/docker/common.js:140`), so `localhost/local-llm:dev` has to be loaded into the Box's image store by hand.
  - The plan does not say which workspace Phase 0 uses.

**Fix:**

- Add a disk table for each Phase 0 step, with deletions in between.
- Remove the dead amd64 image first.
- Name the models explicitly; take gpt-oss-120b only when nothing else is on disk.
- Run the build and benchmark comparisons on the host, outside Ploinky. The host has CUDA 13.0 and nvidia-container-toolkit 1.19.1 (`nvidia-ctk cdi generate` works), so this needs no A1 and can start now.
- Do the nested-container check in a separate test workspace after A1.

### F5. Major: vLLM on arm64 arrives before its unified design, and its offline behaviour on GB10 is undecided

**Where:** B3; Phase 3 → 4.

**What is wrong.**

- **Sequencing.** B3 puts vLLM in `runners.lock.arm64.json` in Phase 3, but unified vLLM sizing comes in Phase 4 (Phase 2 is "llama.cpp and Ollama only"). After Phase 3, an admin can install vLLM on the Spark and run it under rules that do not exist yet.
- **Memory share.**
  - On integrated GPUs, vLLM 0.30.0 sizes from `psutil.virtual_memory().available`: the code has `if current_platform.is_integrated_gpu(…)` then `self.free_memory = psutil.virtual_memory().available`.
  - It refuses to start when that figure is below `total × gpu_memory_utilization`, and total is 119.6 GiB. So any share above MemAvailable ÷ 119.6 GiB fails; that ratio was 0.89–0.93 during this review.
  - NVIDIA's NGC 26.08 notes suggest 0.7 on unified memory.
- **FlashInfer and run-time downloads.**
  - FlashInfer 0.6.18 compiles at run time and needs a CUDA toolkit layout with `nvcc` on PATH. The wheels include `nvcc` 13.2.86, but not on PATH, so vLLM turns FlashInfer off. It then falls back to FlashAttention 2 (PTX-only on GB10, compiled by the driver on first use) or Triton attention, CUTLASS NVFP4 and Marlin MoE.
  - When the network is reachable, vLLM also checks NVIDIA's artifactory (`has_nvidia_artifactory()` requests `https://edge.urm.nvidia.com/artifactory/…` with a 5 s timeout). The answer decides whether FlashInfer's sink and fast-decode paths are used on SM12x.
  - This is an unpinned run-time network path, against DS004's "nothing unpinned is downloaded at run time".
- **Model and driver risks.**
  - gpt-oss on SM121 uses Marlin MXFP4, and vLLM #37030 (wrong first Harmony token on SM121) was open when checked.
  - `nvidia-cutlass-dsl` documents support for the CUDA 12.9 / 13.3 drivers, not 580.
- **Compile caches in `/data`.**
  - Phase 4 wants "compile cache under `/data`".
  - Today vLLM's Triton and vLLM caches are container-local (`/opt/runners/.cache/vllm`, `src/runners/vllm.mjs:189`), which matches DS004's reason for rebuilding runnable copies: other workspace processes can write `/data`, so compiled code kept there can be swapped.

**Fix:**

- Either leave vLLM out of the arm64 lock until Phase 4, or have the unified profile report vLLM as `incompatible` until then.
- For Phase 4:
  - Pin `--attention-backend` and the MoE backend per model family.
  - Decide FlashInfer explicitly. One option is to lock `flashinfer-cubin` and `flashinfer-jit-cache` 0.6.18.post1 from flashinfer.ai; that adds a host to `ALLOWED_HOSTS` (`src/controller/runnerLock.mjs:42-51`) and to DS004. The other is to keep FlashInfer off and stop the artifactory check.
  - Compute `--gpu-memory-utilization` from MemAvailable at start.
  - Prove with a run that has no network (CI install check or Phase 0) that nothing is fetched.
  - Keep compile caches in the container, or put them in `/data` only with a hash manifest checked before use.

### F6. Minor: detect the memory model from NVIDIA's documented signal, not from compute capability 12.x

**Where:** C1.

**What is wrong.**

- NVIDIA documents nvidia-smi's "Not Supported" memory as how integrated GPUs (iGPUs) behave: "iGPUs do not have dedicated framebuffer memory" (DGX Spark Known Issues).
- The documented device attribute is `cudaDevAttrIntegrated`, and this GB10 reports `integrated=1` (M1).
- Compute capability 12.x adds nothing: RTX 50 cards are 12.0 and discrete, and Jetson Thor is an iGPU at 11.0 whose memory also shows "Not Supported", so it would fail closed under the plan's rule.
- `addressing_mode` alone is not a unified-memory signal either: GH200 reports ATS but has dedicated HBM.
- Containers without `nvidia-smi` already fail closed (`hardware.mjs:38-45`), which is correct.

**Fix:**

- Dedicated when `memory.total` is numeric; this covers GH200.
- Unified when `memory.total` is `[N/A]` or "Not Supported", corroborated by a second, optional query (`addressing_mode` is ATS or HMM).
- Otherwise unknown and refused, as the plan says.
- In Phase 0, record llama.cpp's own load log as a cross-check: it reports the device as an integrated GPU and `load_mode = none` under `auto`.

### F7. Minor: admitting against MemAvailable is right, but the llama-server flags are stale and `cudaMemGetInfo` must not be used

**Where:** C2, C5, C8.

**What is right.** MemAvailable is the right input:

- CUDA allocations reclaim clean page cache (M3).
- llama.cpp b11159 uses MemAvailable when `prop.integrated` is set (`ggml/src/ggml-cuda/ggml-cuda.cu:5062-5065`).
- Ollama 0.34.4 takes llama.cpp's figure and caps it at MemAvailable.
- vLLM 0.30.0 uses psutil.

**What is wrong.**

- **`cudaMemGetInfo`.** Anything built on it reports only MemFree: 48.23 GiB free while 106.34 GiB was available (M2). The agent and the new "Unified memory" dashboard card must never use it.
- **`--no-mmap`.** It does not exist at b11159 (row 32).
- **Load mode.**
  - `--load-mode auto` already avoids mmap on an integrated GPU (`ggml-cuda.cu:5089, 5115`; `llama-model.cpp:1444-1452`).
  - A better default on GB10 is `--load-mode dio`: it reads with O_DIRECT (`llama-mmap.cpp:200`, falling back to buffered reads), so loading does not put a second copy of the weights into the page cache.
  - ggml-org's Spark benchmark runs `mmap 0, dio 1`, and Ollama already loads with `dio` on integrated GPUs.
  - The adapter's `noMmap` / `mlock` booleans cannot express `dio`.
- **Other defaults.** `--jinja` is on by default in llama-server at b11159. `-np` defaults to auto (4 slots with unified KV); the adapter passes `-np` explicitly, so keep that.
- **Mixed KV types.** Flash-attention vector kernels are compiled only for same-type K/V pairs (the `GGML_CUDA_FA_QUANTS` default). A mixed pair such as K `q8_0` with V `f16` is converted to f16 with a warning and runs slower.
- **Chat template arguments.** The playbook's MTP example also passes `--chat-template-kwargs '{"preserve_thinking": true}'`, but the schema's `chatTemplateKwargs` allows only `reasoning_effort`, with `additionalProperties: false` (`llamaServer.mjs:91-103`).

**Fix:**

- Replace `noMmap` / `mlock` with a `loadMode` enum (`auto`, `none`, `mmap`, `mlock`, `mmap+mlock`, `dio`). The unified default is `dio`; the dedicated default stays `auto`, i.e. no flag.
- Keep K and V the same type in the unified defaults.
- Allow `preserve_thinking` if MTP Qwen models are seeded.
- Optionally, after a download's sha256 check, drop that file's page cache with `posix_fadvise(DONTNEED)`. It needs no privilege; for example `dd if=<file> iflag=nocache count=0`.

### F8. Minor: the evidence favours ggml-org's prebuilt arm64 release over the in-image source build

**Where:** B2; §6.1.

**What is wrong.**

- **Same GPU code.** Both ship the same `121a-real` SASS (rows 25, 28).
- **Same CPU code.** Both end up at `armv8.6_2` on this CPU (row 29). The source build's `GGML_NATIVE=OFF` + `GGML_CPU_ALL_VARIANTS=ON` equals ggml-org's own flags.
- **The CUDA 13.0 build has an older CCCL and cuBLAS.**
  - The CUDA 13.0 toolkit bundles CCCL 3.0.1, below the 3.2 that llama.cpp's CUB top-k path needs. A 13.0 build therefore falls back to argsort, unless `-DGGML_CUDA_CUB_3DOT2=ON` fetches CCCL at configure time. That fetch is an unpinned network download in the builder unless vendored and pinned.
  - The 13.4 prebuilt has the newer CCCL and cuBLAS 13.4.
- **Driver match.**
  - CUDA 13.0 matches the 580 driver exactly and does not rely on minor-version compatibility, so it is a sound choice.
  - 13.4 runs through documented minor-version compatibility, because no PTX is needed (row 26).
  - DGX OS ships the 580 branch (580.159.03 here), so a 13.4 build would run under minor-version compatibility for as long as that holds.
- **Weak benchmark bar.** Phase 0's reference (1) is weaker than (2) on the CPU side (row 30), so "(2) within noise of (1)" is a weak test. None of the three builds is checked for correctness, only for speed.

**Fix:**

- In Phase 0, run all three builds with identical runtime flags: `-ngl 99 -ub 2048 -fa on --load-mode dio`, with fixed `-c` and `-np`.
- Add a correctness check across builds: the same greedy output, or the same perplexity, on a fixed text.
- Choose the prebuilt unless it fails on 580 or is measurably slower.
- Whichever build wins, add a CI check that needs no GPU: `cuobjdump --list-elf` on the shipped `libggml-cuda.so` must show `sm_121a`.
- If the source build is kept, pin the builder image by digest.

### F9. Minor: Triton does not need the `libcuda.so` link

**Where:** B2, the `libcuda.so` / `TRITON_LIBCUDA_PATH` bullet.

**What is wrong.**

- Triton 3.7.1 links its launcher with `libraries = ['libcuda.so.1']` (`-l:libcuda.so.1`).
- `TRITON_LIBCUDA_PATH` names a directory, which Triton uses as `-L`.
- The agent already sets `TRITON_LIBCUDA_PATH: /usr/local/nvidia/lib64` (`src/runners/vllm.mjs:146`), and vLLM with this same Triton runs on amd64 without an unversioned `libcuda.so`.
- Only FlashInfer's JIT links `-lcuda` against a toolkit layout (`$cuda_home/lib64/stubs`), and that belongs to the FlashInfer decision in F5.

**Fix:** drop the bullet or move it into F5's FlashInfer decision.

### F10. Minor: the image workflow and its tests need more than one assertion changed

**Where:** B4.

**What is wrong.**

- **Tests.** Several tests in `tests/image-definitions.test.mjs` are amd64-specific:
  - `:311-312`: the sources lock `architecture` is `amd64`, and the TARGETARCH guard.
  - `:337-338`: `platforms: linux/amd64$`, and `doesNotMatch(workflow, /arm64|setup-qemu|:latest\b|promote/)`.
  - `:351-381`: ik_llama.cpp and `lib(cudart|cublas|cublasLt)\.so\.12`.
  - `:400-456`: one `runners.lock.json`, and the `cmp` against it.
- **Proof step.**
  - It asserts `Architecture = amd64` (`publish-local-llm-image.yml:86`), Ollama's `cuda_v12 cuda_v13` directories (`:111-113`) and ik_llama.cpp (`:114-124`).
  - The arm64 proof must keep the uid check, the weight scan, the LM Studio absence scan, the lock `cmp` and `source.contract`. B4 names only `ldd` and `--version`.
- **Install check.**
  - It pins `LOCAL_LLMS_COMMIT` (`:177`); the arm64 run needs a pushed local-llms commit that already contains the arm64 changes.
  - It needs an `ubuntu-24.04-arm` runner with room for the 3.94 GB of wheels plus the venv. The amd64 job already has to free disk (`:184-190`).
- **Reused digest.** Reusing `b6c79` means the assemble job takes a pinned amd64 digest instead of building one. It should check that the digest is exactly the one in `local-llm/manifest.json` and that it is `linux/amd64`.
- **Missing GPU code.** CI without a GPU cannot notice missing sm_121 code; add the `cuobjdump` check from F8.

### F11. Minor: of A2's items, one is justified, one never reaches local-llm, and one changes every Box

**Where:** A2.

**What is wrong.**

- **Pid limit: justified, but it changes every Box.**
  - The Box already runs 727 of its 2,048 tasks with 15 agents (`pids.current`), and vLLM with Triton and Inductor compile workers adds hundreds more.
  - The limit is Podman's default, applied by the Box's create command, so raising it changes every workspace's Box (each one is replaced on its next start). The Box identity and E2E rules in `ploinky/CLAUDE.md` then apply.
- **`stack` ulimit: never applies to local-llm.**
  - local-llm declares no `llmRuntime` (DS001: "no `llmRuntime` block").
  - `containerSecurity` accepts only `gpu`, `nestedPodman`, `privileged` and `shmSize` (`ploinky/cli/sandbox/runtimeCapabilities.js:26`), so a `runtimePolicy.resources.ulimits.stack` key would never apply to this agent.
  - There is no evidence a larger stack is needed.
- **`libnvidia-nvvm70.so.4`: reasonable** (row 38), but not arm64-specific: every R580 host has it. Keep it optional.
- **`/dev/nvidia-uvm-tools`: profilers only.** Leave it out unless needed, to keep the device set minimal.

**Fix:**

- Split the pid-limit change from A1, and size it from a Phase 0 measurement.
- Drop the `stack` item, or name the manifest path and the failure it fixes.

### F12. Minor: D deletes the repo's coding-style authority and breaks local-llm's spec references

**Where:** D.

**What is wrong.**

- **Agent count.** There are twelve legacy agents, not eleven (row 43).
- **Coding-style authority.** `docs/specs/DS001-coding-style.md` is the repository's coding-style authority and item 2 of `AGENTS.md`'s mandatory reading order. D deletes it along with DS000–DS011.
- **local-llm's specs cite the legacy set:**
  - `local-llm/docs/specs/DS000-vision-and-scope.md:19` (repository DS001, DS002);
  - `DS002-model-lifecycle.md:13, 60` (DS008);
  - `DS003-gpu-and-resources.md:13, 65` (DS010);
  - `matrix.md:9-10`.
- **HTML docs.** `docs/index.html` (with `specsLoader.html`, `partials-loader.js` and `styles.css`) describes the twelve legacy agents. AGENTS.md's rule that code changes update the HTML docs would have no local-llm HTML left to update.
- **Services with no replacement.** The legacy tree holds the only translation service (transformers seq2seq) and the only reranker (`scripts/services/translation_service.py`, `reranker_service.py`). local-llm serves chat completions only.

**Fix:**

- Move the coding-style rules into local-llm's spec set, or keep the repository DS001.
- Rewrite the "Reuse from repository DS008/DS010" sections with commit links.
- Decide what happens to the HTML docs.
- Record the dropped capabilities in local-llm DS000.
- Tag the last commit before the deletion.
- Mark `assistos/local-llms` deprecated on Docker Hub.

### F13. Minor (security): compiled GPU code from the driver's JIT lands in `/data`

**Where:** C, run-time environment; DS004.

**What is wrong.**

- Runners run with `HOME=/data/home` (`deployments.mjs:452`), so the CUDA driver's JIT cache (`~/.nv/ComputeCache`) is in `/data`.
- On GB10, JIT is the normal path: Ollama's `cuda_v13` runner is PTX-only, and vLLM's FlashAttention 2 is `8.0+PTX`.
- DS004's stated reason for rebuilding runnable copies is that other workspace processes can write `/data`.

**Fix:** set `CUDA_CACHE_PATH` to a directory inside the container. That costs one JIT pass per container. Otherwise, record the accepted risk in DS003/DS004.

### F14. Minor: Explorer (E) needs one operational change

**Where:** E.

**What is wrong.** After A1, this host's Box carries a GPU grant label, and `AchillesIDE/tests/smoke/lib/box-evidence.mjs:130-141` then requires `SMOKE_BOX_GPU_GRANT` to be set.

**Fix:** pass `SMOKE_BOX_GPU_GRANT` in E2E and smoke runs on a Spark. `MINIMUM_REVISIONS` and the enable line stay valid.

### F15. Minor: catalog and housekeeping

**Where:** C6, C10, B.

- **Split GGUF.** gpt-oss-120b is a single 63.4 GB file in ggml-org's repo. The split-GGUF source type is still needed for Qwen3.5-122B-A10B (MXFP4_MOE, 74.7 GB in 3 parts).
- **Seed size vs disk.** The proposed unified seed set totals about 250 GB against 132 GB free. The existing disk admission (`admission.mjs:113-115`) handles that per Run, so this is a documentation point.
- **Dead image.** The 4.91 GB amd64 image stays in the Box's image store after the switch, and Ploinky does not prune it. Remove it on arm64 hosts.
- **"amd64 only" wording.** Update it in `publish-local-llm-image.yml:3-6`, `images/local-llm/Dockerfile:43-46`, DS001's container row ("linux/amd64 only", run 36131512550) and DS000's runner table ("CUDA 12.8 build").

## 4. Missing work

| # | Item | Workstream | Phase |
| --- | --- | --- | --- |
| 1 | Fail closed on non-finite GPU memory as a standalone change, ahead of the unified profile. It fixes the NaN bug everywhere; the arm64 image does not exist yet, so nothing on the Spark regresses. | C | 1 |
| 2 | Start runners with `oom_score_adj=1000`; guard every 250 ms while loading; PSI trigger; floor sized for the gap between samples (F1) | C | 2 |
| 3 | Decide the profile once at controller start and pass it to `normalizeParams`, `admit` and a per-profile schema view (F3) | C | 2 |
| 4 | Work out runner availability from the image at start; Run refuses `runner_unavailable` before any download (F3) | C | 2 |
| 5 | Per-profile `recommended` values (catalog v3 plus registry migration), or two seed files chosen by profile (F3) | C | 2 |
| 6 | A second, optional nvidia-smi query for `compute_cap,addressing_mode,utilization.gpu,power.draw,temperature.gpu`; fail closed only on memory fields (F2, F6) | C | 2 |
| 7 | Golden dedicated-profile tests (`readGpu` with today's x86 output; characterization tests unchanged) and a manual x86 GPU run before merge (F2) | C | 2 |
| 8 | `loadMode` enum with unified default `dio`; same-type K/V in unified defaults; `preserve_thinking` in `chatTemplateKwargs` (F7) | C | 2 |
| 9 | `CUDA_CACHE_PATH` inside the container, or document the risk (F13) | C | 2 |
| 10 | Unified profile reports vLLM `incompatible` until Phase 4, or the arm64 lock ships without vLLM (F5) | B, C | 3 |
| 11 | FlashInfer policy, pinned attention and MoE backends, a run with no network proving nothing is fetched, `--gpu-memory-utilization` from MemAvailable (F5) | B, C | 4 |
| 12 | arm64 proof parity (uid, weight scan, LM Studio scan, lock `cmp`, `source.contract`) plus a `cuobjdump` `sm_121a` check (F8, F10) | B | 3 |
| 13 | Assemble job that takes the reused amd64 digest as a pinned input and checks it against the manifest pin (F10) | B | 3 |
| 14 | Update every amd64 assertion in `tests/image-definitions.test.mjs` (F10) | B | 3 |
| 15 | arm64 install check: runner disk space, and a pushed `LOCAL_LLMS_COMMIT` that contains the arm64 changes (F10) | B | 3 |
| 16 | Phase 0 disk table; delete the dead amd64 image; host-level runs; a separate test workspace for the nested check (F4) | Phase 0 | 0 |
| 17 | Correctness check across the three llama.cpp builds (F8) | Phase 0 | 0 |
| 18 | Measure vLLM's task count, then decide the Box pid limit separately from A1 (F11) | A | After 0 |
| 19 | D: keep or move the coding-style spec, rewrite cross-references, decide the HTML docs, tag, Docker Hub deprecation, DS000 note on dropped services (F12) | D | 1 |
| 20 | Pass `SMOKE_BOX_GPU_GRANT` in Spark smoke and E2E runs (F14) | E | After 1 |
| 21 | Specs: DS001 container row, DS000 runner table, DS003 unified-memory containment, DS004 arm64 lock and allowed hosts, workflow and Dockerfile headers (F15) | B, C | 2–3 |
| 22 | Inside a nested agent container on the Spark, re-measure: `cudaMemGetInfo` vs MemAvailable, page-cache reclaim by CUDA allocations, allocation rate, and whether GPU memory appears in RSS, the OOM score or the memory cgroup (M2–M6) | Phase 0 | 0 (after A1) |

## 5. Open decisions

**1. llama.cpp on arm64: prefer ggml-org's prebuilt CUDA 13.4 release, with the CUDA 13.0 source build as the fallback.** This reverses the plan's proposal.

- The prebuilt already contains `121a-real` SASS for GB10.
- Its CPU code is the same `armv8.6_2` variant the source build would get.
- It carries CCCL ≥ 3.2 and cuBLAS 13.4, which a 13.0 build lacks unless it fetches CCCL at configure time.
- It keeps the same supply chain as the amd64 image: sha256-pinned GitHub release assets and no builder stage.
- Choose the source build only if the prebuilt fails on driver 580 or is measurably slower in Phase 0.
- Either way, add the `cuobjdump` check and the correctness check (F8).

**2. Ollama on arm64: drop it from the first arm64 image.**

- v0.34.4 has no sm_121 SASS, so GB10 runs it only by JIT-compiling PTX on first load, and the JIT output lands in `/data/home` (F13).
- It is the same ggml engine as llama.cpp.
- Its archive is 1.55 GB compressed, and every arm64 Explorer install pulls the image, because Explorer enables local-llm on arm64 hosts whether or not they have a GPU. I did not measure the size of the final image layer.
- NVIDIA's own playbook installs it with an unpinned `install.sh`.
- The adapter must then report "not available on this platform" (F3).
- If it is kept:
  - Pin `OLLAMA_LLM_LIBRARY=cuda_v13`.
  - Measure the first-load JIT time and the cache size in Phase 0.
  - Keep the adapter's `OLLAMA_CONTEXT_LENGTH` (`src/runners/ollama.mjs:114`); it already avoids Ollama's 262,144-token default for devices with 47 GiB or more.

**3. LM Studio: keep it amd64-only (agree).**

- Its lock entry is an x64 CUDA 12 tarball, and the engine directory is x86_64 (`lmStudio.mjs:37`).
- Leave it out of the arm64 lock.
- With F3's run-time availability, it reports "not available on this platform" rather than "not installed".
- Keep the absence scan in the arm64 proof.

**4. amd64: reuse today's digest in the first index (agree), with conditions.**

- The assemble job takes `b6c79` as a pinned input and checks it.
- `images/local-llm/Dockerfile` and `runners.lock.json` stay byte-identical until an amd64 rebuild, because the tests and the proof's `cmp` tie them to the published image.
- C must keep working with the amd64 image as published: its runner lock, and its `source.contract`, which has no architecture field.

## 6. Questions for the plan's author

1. Which x86 GPU host will gate Phase 2? Is the RTX 3060 laptop behind today's measurements still available?
2. Where does Phase 0's nested-container check run? Is it acceptable that A1 recreates the live workspace's Box?
3. Should the first arm64 image carry vLLM at all before Phase 4?
4. For FlashInfer: is adding flashinfer.ai (or NVIDIA's artifactory) to the runner lock's allowed hosts acceptable, or should FlashInfer stay off on arm64?
5. Are the legacy translation and relevance-scoring services needed anywhere? local-llm has no replacement for them.
6. Can Phase 4 keep compile caches inside the container (a warm-up per container), or do you accept compiled code in `/data` with a hash check?

## 7. Comparison with earlier reviews

One other report exists: `local-llm-multiarch-plan-review-codex-gpt-6_codex.md` (codex-gpt-6). It reviews the same plan version (same sha256), and I read it only after sections 1–6 were written. The plan has not changed since, so no later revision addresses any of its findings.

### Where we agree

The fact checks agree:

- the OTA 7.5.0 correction;
- `[N/A]` memory;
- the registry facts, and reusing `b6c79` with no attestations;
- A1 as the only discovery obstacle (both of us ran `discoverNvidiaGpu` with the ldconfig flag rewritten);
- the Box constraints and the dependency cache;
- the vLLM aarch64 closure being complete;
- Triton not needing the `libcuda.so` alias;
- twelve legacy agents, not eleven;
- `--no-mmap` being obsolete and `dio` existing;
- the same test results: 253 of 255 pass in local-llm, 7 of 7 in container-image-builds, and the `PLOINKY_AGENTLIB_DIR` load failure.

Its findings 1 (memory safety), 2 (C4 and vLLM before Phase 4), 6 (`--no-mmap`), 9 (Triton), 10 (disk) and 11 (the cleanup part) match my F1, F3/F5, F7, F9, F4 and F12.

### Its findings I missed, which I accept

- **Finding 3: build identity.** This is correct, and I checked it. At b11159, `cmake/build-info.cmake` sets `BUILD_NUMBER 0` and `BUILD_COMMIT "unknown"` unless git metadata is present. A shallow clone would report build 1. `CMakeLists.txt:153-158` keeps only an explicit `LLAMA_BUILD_NUMBER` / `LLAMA_BUILD_COMMIT`. A source-archive build therefore fails the proof's `grep "build 11159,"` and the adapter's version pin (`llamaCpp.mjs:14-17`, `params.mjs:212`) unless both are passed. This adds weight to my open decision 1, preferring the prebuilt.
- **Finding 4: the revision-label check.** `publish-local-llm-image.yml:88` requires the image's revision label to equal the new run's `GITHUB_SHA`. The reused digest carries `95ba10a…`, so a reuse fails as written. That makes my F10 a major issue, not a minor one.
- **RUNPATH and backend discovery for copied libraries.** If the source build copies cudart and cuBLAS next to the binaries, those libraries must be reachable through `$ORIGIN` or backend discovery.
- **Finding 5: timeouts.** C7's longer runner timeout cannot exceed the endpoint's 600 s command limit (`local-llm/manifest.json`, `timeoutMs: 600000`) or Soul Gateway's 120 s default. The phase that raises completion limits must also move those budgets.
- **Finding 7: other arm64 GPUs.** A `121a-real`-only arm64 image has no kernels for other arm64 NVIDIA GPUs (GH200 is sm_90). The agent must report those GPUs unsupported before downloading, beyond my F6 rule for the memory model.
- **Finding 8: KV double counting.** C2's "context × slots" formula double-counts the KV cache. The adapter's `ctxSize` is already the total unified pool (`llamaServer.mjs:142-147`, `admission.mjs:70-72`).
- **Finding 9: image ENV does not reach runners.** The controller builds a minimal environment for runners (`deployments.mjs:448-455`), so an image-level `TRITON_LIBCUDA_PATH` would not reach them.
- **Finding 11: DS002.** DS002 must also change for split-GGUF sources; C10 lists only DS000, DS001, DS003 and DS004.
- **C4 is missing from the Phase 2 list.** The plan's Phase 2 row reads "C1–C3, C5–C10". I covered the substance in F3 but did not name the omission.

### Where we disagree

- **Open decision 1: llama.cpp build.** codex-gpt-6 keeps the CUDA 13.0 source build as the first candidate. I prefer the prebuilt:
  - Both carry the same `121a-real` SASS and pick the same CPU variant (`armv8.6_2`), so the source build buys only the exact toolkit match.
  - It costs the CCCL ≥ 3.2 top-k path, the build-identity and RUNPATH fixes from its own findings 3 and 4, and a pinned CUDA devel builder.
  - We agree that Phase 0 decides, and that the comparison needs fixed runtime flags, repeated samples and a correctness check.
- **Open decision 2: Ollama.** codex-gpt-6 would include it if Phase 0 passes. I would drop it from the first image:
  - Its report does not mention that v0.34.4's arm64 runners have no sm_121 SASS, so GB10 only JIT-compiles PTX on first load, into `/data/home` (my F13).
  - Its point that the 1.55 GB archive size is not a measured layer size is fair, and I have reworded open decision 2 accordingly.
- **Evidence behind the memory-safety finding.** Its finding 1 asks Phase 0 to characterise peaks, and it also says the plan must state the remaining limitation when other agents can use the shared memory pool. My F1 adds measured reasons why that limitation matters: GPU memory is invisible to RSS, the OOM score and memory cgroups (M5, M6), and allocation runs at about 28 GiB/s (M4). Its fix (a conservative reserve and a calibrated guard) and mine (`oom_score_adj=1000` on runners, faster sampling, PSI) are complementary; the plan should adopt both.
