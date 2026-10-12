# Plan: run `local-llms/local-llm` on NVIDIA DGX Spark through a multi-arch image

Status: being implemented (log: `plans/local-llm-multiarch-implementation-log.md`). Revised 2026-09-28 after two reviews of version `a8f8085b…`:

- `plans/local-llm-multiarch-plan-review-claude-code-opus-5-5.md` (findings F1–F15);
- `plans/local-llm-multiarch-plan-review-codex-gpt-6_codex.md` (findings 1–11).

Section 8 maps each finding to the change it caused. Revised again on 2026-09-28 (evening), from `b5a95376…`, to record the owner's decisions after Phase 0, including that backward compatibility is not required. Section 9 lists each decision and every contract it changes; the changed text elsewhere points to it.

## 1. Goal

Make the existing Ploinky agent `local-llms/local-llm` run local LLMs on an NVIDIA DGX Spark, optimized for that machine, while it keeps working on the x86/amd64 hosts it serves today. Keeping working does not mean keeping today's behaviour: backward compatibility is not required (§9, item 1). Explorer (AssistOSExplorer) must keep enabling one agent, and Ploinky must not learn anything about the `local-llms` repository.

## 2. Decision

- **One agent,** `local-llms/local-llm`. No separate `dgx-local-llm` agent. Both reviews found no evidence against this.
- **A multi-arch image.** The agent's image becomes an OCI index, published like `ploinky-node` and `ploinky-box`:
  - `linux/amd64`: today's image. Its manifest digest `sha256:b6c79af2aad08b542339346f4a985c84d5cbcacc31e8c6df45f951da7ba0fbf7` is reused as-is inside the index (B1, decision 4). Reuse saves a rebuild; it is not a compatibility promise, and amd64 is rebuilt whenever the shared code needs it (§9, item 1).
  - `linux/arm64`: a new build for the GB10 GPU (compute capability 12.1). The agent reports other arm64 NVIDIA GPUs (GH200, Jetson Thor) as unsupported by this image (C4).
- **A hardware profile chosen at run time.** The agent picks dedicated or unified memory from what `nvidia-smi` reports (C1). The JavaScript source is shared by both architectures, because Ploinky mounts the agent directory at `/code`; only binaries and locks come from the image.
- **One agent left in the repository.** The twelve legacy shared-image agents (a manager and eleven model agents) are deleted (D).

### Alternatives considered and rejected

| Alternative | Why rejected |
| --- | --- |
| Two agents (`local-llm` + `dgx-local-llm`) chosen per host by a new Ploinky feature (agent-declared `hostRequirements`, an `if-supported` enable modifier and a host-facts file written into the Box) | Needs a Ploinky feature, Explorer plugin filtering (Explorer aggregates `IDE-plugins/` from every agent in installed repos, enabled or not), and duplicated code. A multi-arch index selects the right image with no new mechanism. |
| Fork `local-llm` into a new agent | About 13k lines copied to change about 1k (estimate from a module-by-module audit). |
| `profiles.<profile>.enable` | The operator chooses the profile; it does not detect the host. |
| Ploinky DS014 `llmRuntime` architecture catalog | Selects an image for one agent, depends on an external catalog, and its policies (`--gpus`, host IPC) are refused inside the Box. |
| A default manifest platform of `linux/amd64` | Would refuse every agent without the field on arm64 hosts, including the ~15 `ploinky-node` agents already running on this Spark. The default must stay today's behaviour: the host's own platform. |

## 3. Facts this plan relies on

The reviews verified these on 2026-09-28: on this host, through registry and PyPI metadata, and in upstream sources at the pinned tags. Each review's fact-check table gives the evidence. Anything marked "Phase 0" or "Phase 1" is still open and is settled by that phase.

### Host (this machine)

| Fact | How to check |
| --- | --- |
| NVIDIA DGX Spark (Lenovo OEM, `30KL0004GF`); DGX OS 7.2.3 base build with OTA 7.5.0; Ubuntu 24.04.4; kernel 6.17; aarch64 | `cat /etc/dgx-release; uname -a` |
| NVIDIA GB10, PCI device ID `0x2E1210DE`, compute capability 12.1, driver 580.159.03, CUDA 13.0 | `nvidia-smi --query-gpu=name,pci.device_id,compute_cap,driver_version --format=csv` |
| `nvidia-smi` reports `memory.total/used/free` as `[N/A]` and `addressing_mode` as `ATS`. Utilization, power, temperature and per-process `used_memory` are numeric. | `nvidia-smi --query-gpu=memory.total,addressing_mode,utilization.gpu,power.draw,temperature.gpu --format=csv`; `nvidia-smi --query-compute-apps=pid,used_memory --format=csv` |
| 119.6 GiB MemTotal, no swap | `free -h` |
| 20 cores: 10 Cortex-X925 (cpu5–9 and 15–19, sysfs `cpu_capacity` 997–1024) and 10 Cortex-A725 (cpu0–4 and 10–14, 718–731); no SME | `lscpu; cat /sys/devices/system/cpu/cpu*/cpu_capacity` |
| 1 TB NVMe with about 132 GB free (85 % used). The existing Explorer deployment's Box image store takes about 13 GB of the used space. | `df -h /`; `du -sh /home/research/work/.ploinky/box/images` |
| The existing Explorer deployment (workspace `/home/research/work`, Box `ploinky-box-work-287e15733c26`, 15 agents) is not needed during this work. The owner allows stopping or destroying it (2026-09-28). | — |
| Single Spark; all ConnectX-7 ports down | `ip -br link; ibdev2netdev` |
| Host tools: CUDA 13.0.88, cmake 3.28.3, gcc 13.3. cmake 3.28 accepts `121a-real`; only the `f` suffixes need 3.31.8+. gcc 13.3 cannot resolve `-mcpu=native` on this CPU and falls back to baseline armv8-a. | `nvcc --version; cmake --version; gcc -mcpu=native -Q --help=target` |
| nvidia-container-toolkit 1.19.1 is installed, so GPU containers run on the host without Ploinky | `nvidia-ctk --version` |

### GB10 memory behaviour

These were measured on 2026-09-28 with small CUDA test programs on the host. Phase 1 repeats the measurements inside a nested agent container.

- **Integrated device.** CUDA reports the device as integrated: `integrated=1`, `pageableMemoryAccessUsesHostPageTables=1`, and 119.63 GiB total.
- **`cudaMemGetInfo` reports MemFree, not MemAvailable.** It returned 48.2 GiB free while MemAvailable was 106.3 GiB and 53.9 GiB was page cache.
- **CUDA allocations reclaim clean page cache.** 56 GiB was allocated and touched starting from 48 GiB of MemFree, and Cached fell by 9.8 GiB.
- **The runners size from MemAvailable.** On integrated GPUs, llama.cpp b11159 (its fit logic), Ollama 0.34.4 and vLLM 0.30.0 (`psutil.virtual_memory().available`) all do.
- **Allocation is fast.** Allocating and first touching memory runs at about 28 GiB/s.
- **GPU memory is invisible to per-process accounting.**
  - A process holding 4 GiB had 98 MB of RSS and the baseline `oom_score`.
  - Inside a `MemoryMax=2G` scope, its cgroup showed 70 MiB.
  - So neither the kernel OOM killer's choice of victim nor memory cgroups see GPU allocations.

### Current failure

- Explorer's manifest enables `local-llms/local-llm no-wait` (`.ploinky/repos/AchillesIDE/explorer/manifest.json:28`, `enable` list).
- On this host the Box pulled the amd64-only `local-llm` image (4.57 GB, 620 s). The runtime-key probe then failed with `Exec format error` (`ploinky/cli/utils/dependencies/dependencyRuntimeKey.js:151`).
  - The dead 4.91 GB image stays in the Box's image store.
  - Log: `/home/research/work/.ploinky/logs/no-wait/ploinky_local-llms_local-llm_work_287e1573.*.log`.
- `ploinky gpu status` fails on this host. Run it from `/home/research/work` as `/home/research/work/ploinky/bin/ploinky gpu status`, because `ploinky` is not on PATH.
  - It reports `Host GPU: unavailable (NVIDIA driver library libcuda.so.1 is not in the ldconfig cache)`.
  - Cause: `parseLdconfigCache` accepts only entries flagged `x86-64` (`ploinky/ploinky-box/gpuGrant.mjs:239`), and on this host the flag is `AArch64`.
  - With only that filter changed, the rest of discovery succeeds here: 3 device nodes, 5 driver libraries and `nvidia-smi`.
  - The CDI spec, fingerprint and marker carry no architecture data.
- If the agent did run here, admission would pass every model on GPU memory.
  - `readGpu` (`local-llm/src/controller/hardware.mjs`) turns `[N/A]` into `NaN`, so every GPU-memory comparison in `src/controller/admission.mjs` is false.
  - A 500 GiB GGUF (llama.cpp) and a 400 GiB tag (Ollama) are admitted. RAM and disk checks still apply.
  - vLLM gets a `NaN` GPU share and fails at launch (`src/runners/vllm.mjs:115-117`), unless an admin sets the share.

### Multi-arch mechanics

- **`ploinky-node` is an index.** Explorer pins `ploinky-node` by digest `sha256:accd925f…` (`explorer/manifest.json:2`). That digest is an OCI image index with `linux/amd64` and `linux/arm64` entries, and podman on this Spark resolved it to arm64.
- **`local-llm` is a single manifest.**
  - Its manifest pins a single amd64 image manifest, `b6c79…`, with revision label `95ba10a…`.
  - It was pushed with `provenance: false`, and the OCI referrers API lists no attestations for it.
  - The publish workflow's candidate step already wraps it in an index (`candidate-36131512550-1`), so an `imagetools create` of it plus an arm64 digest is a known operation.
- **Pulls use the host platform.** Ploinky runs `podman pull <image>` with no `--platform` (`ploinky/cli/sandbox/docker/common.js:196`). It adds `--platform` only when `llmRuntime.runtimePolicy.platform` is set (`ploinky/cli/sandbox/docker/containerRuntimePolicy.js:262`).
- **The `ploinky-node` workflow is the model.** `container-image-builds/.github/workflows/publish-ploinky-node-image.yml` builds each platform on its native runner (`ubuntu-24.04`, `ubuntu-24.04-arm`), pushes by digest, proves each platform, and then assembles the index with `docker buildx imagetools create`.
- **Where the amd64 lock-in is.** The runtime base `ploinky-node:24-trixie-tools@sha256:accd925f…` is that same multi-arch index. The amd64 lock-in is the guard `test "${TARGETARCH:-amd64}" = amd64` (`container-image-builds/images/local-llm/Dockerfile:54`) and the x64 downloads that follow it.
- **The dependency cache needs no change.**
  - Ploinky keys it by the image's own `process.arch` (`container-linux-arm64-glibc-node24` vs `container-linux-x64-glibc-node24`).
  - The pin change invalidates each host's cache once, because the stamp records the image reference.

### Box

- **Image.** `ploinky-box:latest` is a multi-arch index; its arm64 variant runs on this Spark (Fedora 44, podman 5.8.2).
- **GPU wiring.**
  - The Box image contains no NVIDIA userland.
  - GPU wiring consists of device nodes, read-only binds of the host's driver libraries under `/usr/local/nvidia`, a hookless CDI spec `ploinky.local/gpu=all`, and a grant marker.
  - The wiring is fixed when the Box is created.
- **Code vs create arguments.**
  - The Box mounts the host's Ploinky checkout read-only at `/opt/ploinky`, so Ploinky code changes reach the Box without an image rebuild.
  - New GPU wiring or Box create arguments take effect only when the Box is replaced, and that restarts the workspace's agents.
- **Constraints for agents:**
  - no `--ipc host`;
  - `/dev/shm` at most `16g`;
  - one 2,048-task pid limit shared by every agent (727 in use with 15 agents);
  - nested cgroups disabled, and the Box itself has no memory limit;
  - no host networking or RDMA (multi-Spark is out of scope by design).
- **Not yet tested.** Nested CDI on arm64 is untested, because the Box has no GPU wiring today (Phase 1).

### Runner availability on arm64

**llama.cpp b11159** (tag commit `6b790a9c291b5d7af3312bbf9f0c558aa023b13e`):

- **Prebuilt assets.** `llama-b11159-bin-ubuntu-cuda-13.4-arm64.tar.gz` (sha256 `258c9dc7c6c02fd2d805ebf9511876ab7b9d7b2d3f0c2166454d682ccae7644b`) and `cudart-llama-b11159-bin-ubuntu-cuda-13.4-arm64.tar.gz` (`34d8602d0084b2498dbf0c436fe2d1d4e54ba577b8d5567eb56990e8fff11bfa`; cudart, cuBLAS and cuBLASLt `.so.13`).
- **How the prebuilt is built.** On `ubuntu-24.04-arm`, in `nvidia/cuda:13.4.1-devel-ubuntu24.04`, with gcc-14 and `GGML_NATIVE=OFF GGML_CPU_ALL_VARIANTS=ON GGML_BACKEND_DL=ON`. It sets no `CMAKE_CUDA_ARCHITECTURES`, so the default list applies: `75-virtual;80-virtual;86-real;89-real;90-virtual;120a-real;121a-real`, which includes native `sm_121a` code.
- **Driver compatibility.** CUDA 13.x applications run on driver ≥ 580 under minor-version compatibility, provided no PTX JIT is needed. The forward-compatibility package does not apply to GB10.
- **CPU code.** On this CPU (no SME), the `armv8.6_2` variant is selected.
- **CCCL.** A CUDA 13.0 build ships CCCL 3.0.1 and so loses the CUB top-k path, which needs CCCL ≥ 3.2 and which 13.4 has.
- **Still open (Phase 0).** The cubins actually inside the shipped `libggml-cuda.so`, and a run on this driver.

**llama.cpp b11159 options:**

- **Load mode.**
  - `--no-mmap`, `--mmap`, `--mlock` and `--direct-io` were removed in b10875. The option is now `--load-mode {auto,none,mmap,mlock,mmap+mlock,dio}`.
  - `auto` already avoids mmap on an integrated GPU.
  - `dio` reads with O_DIRECT; ggml-org's Spark benchmark uses `mmap 0, dio 1`.
- **Defaults.** `--jinja` is on by default. `-np` defaults to 4 slots with a unified KV cache.
- **Prompt cache.** `--cache-ram` defaults to 8192 MiB of host RAM; `0` disables it. With `--kv-unified`, idle slots are saved into it and cleared when a new task starts, and the clearing needs a nonzero `--cache-ram`. With `0`, a long idle slot keeps its cells and new requests fail, as Phase 0 measured. A state larger than the whole limit is not saved, but its slot is still cleared.
- **MTP exists.** `--spec-type draft-mtp` and `--spec-draft-n-max` (default 3).
- **Mixed KV types are slow.** Flash-attention kernels are compiled only for same-type K/V pairs; a mixed pair converts to f16.
- **Build identity.** Without git metadata a build reports build 0 and commit `unknown`, unless `LLAMA_BUILD_NUMBER` and `LLAMA_BUILD_COMMIT` are set (`cmake/build-info.cmake`).

**NVIDIA's llama.cpp playbook** (`NVIDIA/dgx-spark-playbooks`, `nvidia/llama-cpp`, updated 06/03/2026):

- It clones llama.cpp master without a pin and builds with the host toolkit: `-DGGML_NATIVE=ON -DGGML_CUDA=ON -DGGML_CURL=ON -DGGML_RPC=ON -DCMAKE_CUDA_ARCHITECTURES=121a-real`. `GGML_CURL` is not an option at b11159.
- It runs with the defaults plus the MTP flags and `--chat-template-kwargs '{"preserve_thinking": true}'`.

**Ollama v0.34.4:**

- **Asset.** `ollama-linux-arm64.tar.zst`: 1,549,684,612 bytes, sha256 `96f50a1192133028cf4e010d8c333f8af14b1505db6be7b2034c11487e7fd7e6`. GB10 is listed as supported.
- **No native sm_121 code.** `cuda_v12` has `sm_120a`, which runs only on 12.0, and `cuda_v13` is PTX-only (`compute_121a`). So the driver JIT-compiles it on first load.
- **Memory.** On integrated GPUs it sizes from MemAvailable and loads with `--load-mode dio`.
- **Install route.** NVIDIA's Ollama playbook installs the unpinned `install.sh`.
- **Still open.** Untested on this host (Phase 0).

**vLLM 0.30.0** (installed on demand):

- **Wheels.**
  - The wheel is `vllm-0.30.0-cp38-abi3-manylinux_2_28_aarch64.whl`.
  - All 196 distributions in the amd64 lock have cp313 aarch64 wheels at the same versions on `files.pythonhosted.org`: none is sdist-only, 3.94 GB in total.
  - torch 2.13 depends on `cuda-toolkit[…]==13.0.3`.
- **Kernels.**
  - vLLM's NVFP4, FP8, Marlin and MoE kernels are built for `12.0f`, which covers 12.1.
  - FlashAttention 2 is PTX only, so the driver JIT-compiles it.
  - torch ships `sm_120` machine code.
  - Triton 3.7.1 maps 12.1 to `sm_121a`, bundles ptxas 13.1.80 and links `-l:libcuda.so.1`.
- **FlashInfer.**
  - FlashInfer 0.6.18 needs a CUDA toolkit (nvcc on PATH) at run time, so offline vLLM turns it off.
  - When the network is reachable, vLLM probes NVIDIA's artifactory to decide FlashInfer paths on SM12x.
- **Known issue.** gpt-oss uses Marlin MXFP4 on SM121, and vLLM #37030 (wrong first Harmony token) is open.
- **Still open.** Untested on this host (Phase 4).

**ik_llama.cpp, TabbyAPI and LM Studio:** x86-only builds today; left out of arm64.

### Model sizes (Hugging Face, for disk planning)

| Model | Size |
| --- | --- |
| gpt-oss-20b MXFP4 GGUF | 12.1 GB |
| Qwen3.6-35B-A3B MTP GGUF, UD-Q4_K_XL / Q8_0 | 22.9 / 37.8 GB |
| Qwen3-Coder-30B-A3B Q8_0 | 32.5 GB |
| GLM-4.7-Flash Q8_0 | 31.8 GB |
| gpt-oss-120b MXFP4 GGUF | 63.4 GB, one file |
| Qwen3.5-122B-A10B MXFP4_MOE | 74.7 GB, 3 files |
| `openai/gpt-oss-120b` safetensors (for vLLM) | 65.2 GB |

### Consumer side

- **Discovery.** Soul Gateway discovers the agent through the Router's `/api/router/openai-agent-discovery` and names the model `local-llms/local-llm/default`. It already supports several models per agent through `endpoints.models.command` (later phase).
- **Deadlines.** The chat endpoint's command limit is 600 s (`manifest.json` `timeoutMs: 600000`). Soul Gateway's default request deadline is 120 s.
- **Request fields.** Soul Gateway drops `reasoning_content` and `reasoning_effort` and forwards only some sampling fields. These are later-phase gateway patches (Phase 5; decision 9 keeps them there).

## 4. Work by repository

### A. Ploinky (`github.com/AssistOS-AI/ploinky`) — prerequisite

**1. Required: `parseLdconfigCache` accepts the ldconfig flag of the host architecture.**

- `x64` maps to `x86-64` and `arm64` to `AArch64`; an unknown architecture is refused with a clear reason.
- `discoverNvidiaGpu` takes `arch`, defaulting to `process.arch`.
- Tests pass the architecture explicitly:
  - x64 and arm64 fixtures;
  - an arm64 cache that also lists x86-64 or 32-bit entries;
  - whitespace in the flags;
  - missing libraries, a version mismatch, and an unknown architecture;
  - a round-trip of the arm64 CDI spec, marker and fingerprint that adds no device, mount or privilege.
- **x64 changes are allowed.** x64 wiring and fingerprints may change. A2 changes them on R580 hosts, which replaces each such Box once; the owner accepted this. Tests check the intended wiring on both architectures, not that x64 output stays the same (§9, item 1).
- Fix the comment at `gpuGrant.mjs:232`; the README has no x86-64 wording.
- **Rollout.** A workspace gets GPU wiring at its next Box replacement (`ploinky start`, `restart` or `update`), which restarts its agents. The existing Explorer deployment is not needed, so there is no live workspace to protect. Test in a fresh workspace run by the development Ploinky clone (Phase 1). At the end, redeploy Explorer on this host from the released revisions if it is wanted (Phase 3).

**2. Optional, with A1: bind `libnvidia-nvvm70.so.4` when present.** Treat it as a soname-specific exception to the check that driver libraries carry the driver version in their file names: its real file is unversioned, and `libcuda` names it. It exists on every R580 host, x86 included; llama.cpp does not need it.

**3. Only if Phase 4 measures a need: raise the Box's 2,048-task pid limit.** It is a Box create argument, so every workspace's Box is replaced, and Ploinky's Box-identity and E2E rules apply. Keep it a separate change from A1.

**4. Optional: refuse an image before pulling it** when its index has no entry for the host platform, or when it is a single-platform image for another platform, instead of pulling it and failing with `Exec format error`.

- No manifest field; the default stays the host's own platform.
- Consider hosts with binfmt emulation.

**Dropped after review:**

- `/dev/nvidia-uvm-tools`: only profilers need it.
- A `stack` ulimit: local-llm declares no `llmRuntime`, `containerSecurity` has no such key, and no failure needs it.

No Box image change is needed.

### B. `container-image-builds` — the multi-arch image

**1. amd64: reuse `b6c79…` through a reuse-and-prove job, or rebuild it.**

- The job's input is the pinned digest. It must equal the current pin in `local-llm/manifest.json` and be `linux/amd64`.
- The job re-runs today's proof against that digest with today's expectations: revision label `95ba10a…` instead of `GITHUB_SHA` (`publish-local-llm-image.yml:88`), ik_llama.cpp, CUDA 12 libraries, the LM Studio SDK, and the amd64 runner lock.
- While the digest is reused, `images/local-llm/Dockerfile`, `sources.lock.json` and `runners.lock.json` stay as they are, so they still describe the published image.
- The shared JavaScript (C) must work with whichever amd64 image the index carries. It keeps no compatibility branches for an older image: if it needs something the reused image lacks, rebuild amd64, with its own build-and-prove job (§9, item 1).

**2. arm64: add `images/local-llm/Dockerfile.arm64`.**

- **Same layout as amd64.** Same base (`ploinky-node:24-trixie-tools@sha256:accd925f…`), same `/opt` paths, same `PATH`, and the same `LD_LIBRARY_PATH` (only the granted driver libraries), so the JavaScript does not branch on CPU architecture.
- **llama.cpp: one of two candidates, chosen in Phase 0 (decision 1: L1).** Both carry `121a-real` GPU code and `GGML_CPU_ALL_VARIANTS` (`armv8.6_2` is selected on this CPU).
  - **L1, prebuilt.** ggml-org's b11159 `ubuntu-cuda-13.4-arm64` pair, pinned by sha256 like the amd64 assets. It runs under CUDA minor-version compatibility.
  - **L2, source build:**
    - builder `nvidia/cuda:13.0.2-devel-ubuntu24.04`, pinned by its arm64 manifest `sha256:450d11555d20ac8ebbbc13ebf17589c2bd42869171a90179ce7098b4a5e64c6a` (index `sha256:5dc1bca23d05bd37b011be68ec470c03b403a5da07ec3a86e41af9470e9d0cc6`);
    - source fetched by the full tag commit and verified, as the ik_llama.cpp builder does (archives GitHub generates are not guaranteed to stay byte-identical);
    - `-DLLAMA_BUILD_NUMBER=11159 -DLLAMA_BUILD_COMMIT=6b790a9c2`, so `--version` reports build 11159 like the prebuilt;
    - `-DCMAKE_CUDA_ARCHITECTURES=121a-real`;
    - `GGML_NATIVE=OFF`, `GGML_CPU_ALL_VARIANTS=ON` and `GGML_BACKEND_DL=ON`, with gcc-14 as ggml-org uses (gcc 13 cannot build the SME variants);
    - `GGML_RPC=OFF`, and neither `GGML_CURL` (not an option) nor `LLAMA_CURL` (deprecated); check the configure output for options it ignored;
    - CCCL: accept the 13.0 argsort fallback, or vendor a pinned CCCL ≥ 3.2 (never a download during configure);
    - targets `llama-server` and `llama-bench`, so Phase 0 benchmarks the build that ships;
    - binaries, CPU and CUDA backends, and cudart, cuBLAS and cuBLASLt from the builder go in `/opt/llama.cpp` with RUNPATH `$ORIGIN`, proved from the final image.
  - **Still rejected: compiling on first use inside the running container.** It would need the CUDA devel toolkit in the image and take minutes. It would also repeat in every new container, because DS004 rebuilds runnable copies per container, and its output cannot be pinned by hash.
- **Ollama.** Not in the first arm64 image (decision 2). If it is added later: `ollama-linux-arm64` v0.34.4, pinned by sha256.
- **uv and build tools.** uv 0.12.18 `uv-aarch64-unknown-linux-gnu.tar.gz` (sha256 `afb6291f3f0a6b4521fc67b947822506c41dde5b60d2189dd8f3695b2ac8c9e7`); gcc, libc6-dev and libpython3.13-dev for Triton (Phase 4); `/opt/runners` owned by uid 1000.
- **Left out.** No ik_llama.cpp, no TabbyAPI, no LM Studio or its SDK.
- **`source.contract`** records the architecture, the llama.cpp candidate and its CUDA version, and `gpu_compute_capabilities=12.1`: the GPUs its CUDA runners were built for, which C4 reads.
- **Dropped: the `libcuda.so` link for Triton.** Triton 3.7.1 links `libcuda.so.1`. Also, image environment variables do not reach runners, because the controller builds their environment.

**3. Locks.**

- `sources.lock.arm64.json`, with `"architecture": "arm64"`.
- `runners.lock.arm64.json`, copied into the arm64 image at `/opt/local-llm/runners.lock.json`.
- The first arm64 lock has no runner entries; an empty lock is valid. vLLM is added in Phase 4, with its aarch64 closure and a new arm64 image.
- The lock schema is unchanged.

**4. Workflow `publish-local-llm-image.yml`.**

- **Jobs:**
  - amd64 reuse-and-prove (B1);
  - arm64 build-and-prove on `ubuntu-24.04-arm`;
  - an install check per architecture;
  - assembling the index, only after both proofs and install checks pass, followed by verification of its exact children.
- **arm64 proof.** It keeps every amd64 proof rule that applies:
  - uid 1000;
  - runner `--version` (build 11159);
  - an `ldd` closure in which only `libcuda.so.1` may be missing;
  - the weight scan and the LM Studio absence scan;
  - the lock `cmp` and `source.contract`.

  It adds `cuobjdump --list-elf /opt/llama.cpp/libggml-cuda.so`, which must show `sm_121a` code; this needs no GPU.
- **Install check.**
  - It reads the architecture's own lock and keeps proprietary entries validate-only.
  - It pins `LOCAL_LLMS_COMMIT` to a pushed candidate that contains C's changes.
  - On arm64 it runs on a runner with disk room for the lock: in Phase 4, 3.94 GB of wheels plus the venv.
- **Tests.** In `tests/image-definitions.test.mjs`, make every amd64-only assertion (`:311-312`, `:337-338`, `:351-381`, `:400-456`) per-architecture, and add tests for the arm64 Dockerfile, locks and proof.
- **Wording.** Update the "amd64 only" text in the workflow header (`:3-6`) and in the Dockerfile comment (`:43-46`).

### C. `local-llms` — agent code with two hardware profiles

**0. First, as a standalone change (Phase 1): treat non-finite GPU memory as unknown.** The GPU is then reported unavailable with a reason, and every Run is refused. Hosts that report numbers see no change.

**1. Hardware snapshot (`src/controller/hardware.mjs`).**

- **Queries.** Today's five-field `--query-gpu` call no longer has to stay byte-identical (§9, item 1). Add a second, optional call for `pci.device_id,compute_cap,addressing_mode,utilization.gpu,power.draw,temperature.gpu`; its failure (an older driver, an unknown field) never disables the GPU.
- **Memory model.**
  - Unified: `memory.total` is `[N/A]` or "Not Supported" and `addressing_mode` is `ATS` or `HMM`; or the PCI device ID is on a known-unified list. That list holds GB10, `0x2E1210DE`, which also covers a future driver that reports numbers.
  - Dedicated: `memory.total` is numeric and the device is not on that list. GH200 is dedicated: it reports ATS with numeric HBM.
  - Anything else is unknown and refused. Do not infer the model from CPU architecture.
- **Unified pool.** Read `/proc/meminfo`: MemTotal and MemAvailable for sizing, MemFree and Cached for display. Never size from `cudaMemGetInfo` or from `nvidia-smi`.
- **Fail closed only on what admission uses.** Utilization, power and temperature are optional telemetry; laptop GPUs report `power.draw` as `[N/A]`.
- **Thread default.** Unchanged, unless sysfs `cpu_capacity` shows cores of different capacity; then it is the number of highest-capacity CPUs (the 10 X925 cores here). A thread count is not affinity: pinning (`--cpu-mask`) is optional and is decided in Phase 0.

**2. Unified admission (`src/controller/admission.mjs`).** llama-server comes first. Ollama is not in the first arm64 image (decision 2), and vLLM stays `incompatible` in the unified profile until Phase 4.

- **What a run needs:** weights + KV cache + compute buffers + MTP allocations when enabled + runner overhead.
- **The KV term follows each runner's contract.** llama-server's `ctxSize` is the whole unified pool (`--kv-unified`), not a per-slot size, so it is not multiplied by the number of slots.
- **Constants and the host reserve come from Phase 0 peak measurements:** download and hash, load, full prefill, parallel slots, and MTP on and off.
- **How the need is computed** (owner, after Phase 0; §9, item 5). It is the sum of:
  - the weights;
  - llama.cpp's own buffer sizes (model, KV and compute, as logged at `-lv 4`);
  - a measured runtime constant;
  - a transient margin per model and per slot class (one slot or several), measured separately from the prompt cache;
  - the prompt cache's explicit bound. The adapter always passes `--cache-ram`, and admission counts it in full. 8192 MiB stays the admitted value until a smaller setting passes the long-context, parallel-request and peak-memory checks on the largest models.
- **The envelope's key pins every memory-relevant parameter:** context, slots (an explicit `-np`), `-b` and `-ub`, K and V types, flash attention, `--kv-unified`, load mode, the MTP flags and `--cache-ram`.
- **Verdicts.** `insufficient-now` when the need exceeds MemAvailable minus a floor; `incompatible` when it exceeds MemTotal minus a host reserve.
- **Measured envelope only.** Until the self-calibrating admission of Phase 5, the unified profile admits only configurations inside the envelope Phase 0 measured (weight size, context and slots, MTP). Outside it, Run is refused with that reason. An envelope counts as measured only when it rests on clean, agreeing evidence, or on an independently justified upper-bound method. Until then that model and configuration stay unavailable (§9, item 10).
- **No offload.** No CPU offload and no `nCpuMoe` in this profile.
- **Dedicated profile.** There is no requirement to keep today's policy or constants (§9, item 1). Any change is deliberate, recorded in DS003, and validated by the x86 functional gate (Phase 2).

**3. Memory containment in the unified profile (`src/controller/deployments.mjs`).** GB10 GPU memory is invisible to RSS, to the OOM score and to memory cgroups, so:

- **OOM priority.** Every runner gets `oom_score_adj=1000` right after spawn and before it loads. This needs no privilege, and children inherit it. A kernel OOM then kills the runner, which frees its GPU memory. This is a backstop only (§9, item 5).
- **An always-on memory guard:**
  - it samples MemAvailable every 250 ms throughout, both while the model loads and once it is ready, and also watches `/proc/pressure/memory` (`full avg10`). This changed after Phase 0 (§9, item 5): a prompt-cache save allocates up to `--cache-ram` in one step;
  - on an actual floor breach it kills the runner's process group at once (SIGKILL, no grace period); other stops stay graceful;
  - its floor covers the gap between samples: at least max(4 GiB, 5 % of MemTotal), calibrated in Phase 0. The floor and the other guard constants stay provisional until stop and release latency are measured, both during a load and during active requests;
  - if `/proc/meminfo` cannot be read, the runner is stopped.
- **Admission is the primary control,** because one large allocation, such as a KV cache, outruns any sampling. In Phase 0, loads took 7–10 GiB within 250 ms. Admission covers the full known allocation. DS003 records this, and records the residual risks:
  - cgroup limits do not bound GPU allocations here;
  - other agents can take memory between admission and load;
  - userspace sampling cannot protect against arbitrary allocations by other processes on a shared host.

**4. Runner and GPU availability (`src/runners/*`, `src/controller/deployments.mjs`), in Phase 2.**

- **`supported` / `unsupportedReason` become run-time properties.** Each adapter computes them at controller start from what the image contains: the executable exists (llama.cpp, ik_llama.cpp, Ollama), or the lock has an entry (vLLM, TabbyAPI, LM Studio). The profile also counts: vLLM is `incompatible` on unified memory until Phase 4.
- **GPU check.** The GPU's compute capability must appear in the image's `gpu_compute_capabilities` (`source.contract`). The reused amd64 image has no such line, so the check is skipped there. A rebuilt amd64 image should carry the line too, so the check needs no special case (§9, item 1).
- **Refuse before downloading.** Run refuses with `runner_unavailable` before any download, and the overview and dashboard say "not available on this platform". Today Run checks only the static `supported` flag and whether the lock can install the runner (`deployments.mjs:796-806`). On an arm64 image that would download a GGUF for ik_llama.cpp and then fail at launch.

**5. llama-server (`src/runners/llamaServer.mjs`, `llamaCpp.mjs`).**

- **Load mode.** Replace `noMmap` / `mlock` with a `loadMode` enum mapped one-to-one to b11159's `--load-mode` (`auto`, `none`, `mmap`, `mlock`, `mmap+mlock`, `dio`).
  - The dedicated default is `auto`. Keeping today's argv unchanged is no longer a requirement (§9, item 1).
  - The unified default is `dio`, loading from `/data` right after a controller download and hash. This was decided after Phase 0: cold loads were 1.9–3.2× faster than with `none`, and the page cache grew by 0.8 GiB instead of 12–37 GiB.
- **Unified defaults:** `-ngl 999`, `-fa on`, `-b 2048 -ub 2048`, the same type for K and V, an explicit `-np`, and no `nCpuMoe`. `--jinja` is already on by default at b11159.
- **Context.** Raise the `ctxSize` maximum to 262,144, capped per model at its training context.
- **MTP.** `--spec-type draft-mtp --spec-draft-n-max 3` is an opt-in parameter for models validated in Phase 0, and admission counts its memory. `chatTemplateKwargs` gains `preserve_thinking`, as in NVIDIA's MTP example.
- **Page cache.** Drop a downloaded file's page cache after its sha256 check (`posix_fadvise(DONTNEED)`, which needs no privilege), where supported. This was decided after Phase 0: a full page cache after a download disturbed the first gpt-oss-120b benchmarks.
- **Profile.** Adapters take the profile in `normalizeParams`, `admit` and a per-profile schema view (C6).

**6. Profile and catalog.**

- **Choosing the profile.** The controller determines it from the first snapshot at start, logs it, and keeps it for the container's lifetime. A later snapshot that disagrees is reported, not acted on.
- **One seed catalog.** Schema v3, with `recommended` values per profile; today's values become the dedicated ones. Existing registry entries need not be migrated (§9, item 1). State the controller no longer supports is detected, then refused or reset with a clear message; it is never misread. `LOCAL_LLM_CATALOG_FILE` remains only an explicit override.
- **Unified seed.**
  - Validated in Phase 0 for the first release: gpt-oss-20b, Qwen3.6-35B-A3B MTP (UD-Q4_K_XL) and gpt-oss-120b (MXFP4).
  - Listed, each measured before it is marked validated: Qwen3-Coder-30B-A3B Q8_0, GLM-4.7-Flash, and Qwen3.5-122B-A10B (MXFP4_MOE, 74.7 GB, with a disk warning).
  - No dense 70B models.
  - Every Hugging Face source is pinned by commit, size and sha256.
- **Split GGUF,** needed for Qwen3.5-122B-A10B (3 files; gpt-oss-120b is one file):
  - it is still the `gguf` weight format;
  - every shard is pinned by size and sha256;
  - shards keep a canonical order and their names, in one directory;
  - the set has one immutable artifact identity;
  - disk space and progress are accounted over the whole set, and deletion is shared;
  - `model_add` accepts it. Old state files need not remain readable (§9, item 1).

  DS002 changes with it.

**7. Chat endpoint (`src/chatResponder.mjs`).**

- `MAX_COMPLETION_TOKENS` and `RUNNER_TIMEOUT_MS` become configurable, but the effective limits stay inside the outer budgets: the endpoint's 600 s command limit and Soul Gateway's 120 s default deadline.
- 32,000-token completions (what Claude Code sends) are not a first-release requirement (decision 9). The first release keeps coherent, explicit completion budgets and deadlines inside the outer budgets. Raising them is Phase 5 work.
- Forward more request fields (updating DS001's allowlist), and include `usage` in the final streamed chunk.

**8. Dashboard (`IDE-plugins/local-llm-tool-button/...`).**

- A "Unified memory" card built from MemTotal and MemAvailable.
- The per-model admission meters (`local-llm-dashboard-view.js:356-357`) use the profile's pool.
- The GPU and RAM cards stay for dedicated memory.
- No NaN or null reaches a card.

**9. Tests.**

- **Profile fixtures:**
  - GB10, with the exact `nvidia-smi` lines of both queries;
  - a GB10 that reports numeric memory;
  - GH200-like (ATS with numeric memory);
  - Jetson Thor-like (`[N/A]`, compute capability 11.0);
  - missing `nvidia-smi`;
  - partial telemetry (`power.draw` `[N/A]`);
  - an unknown device.
- **Behaviour:** unified admission (pool semantics, MTP, floors, the measured envelope); runner and GPU availability; guard timing and `oom_score_adj`; `loadMode` mapping; finite values in serialized snapshots.
- **Dedicated tests** check the intended behaviour, not unchanged behaviour (§9, item 1). `tests/runner-characterization.test.mjs` and `tests/cpu-cores.test.mjs` change with any deliberate behaviour change, and each commit names the change. `readGpu` keeps a fixture of real x86 output (the RTX 3060 Laptop line).
- **Fix** the two LM Studio tests that use the test machine's core count; they fail on this 20-core host.

**10. Specs and manifest.**

- **Specs:**
  - DS000: runners per platform; the arm64 image is for GB10;
  - DS001: the container row now names the index digest; chat limits;
  - DS002: split GGUF;
  - DS003: profiles, admission, containment, and the JIT cache;
  - DS004: per-architecture locks; allowed hosts unchanged unless decision 7 adds one;
  - a new DS005, "Hardware profiles".
- **Changed contracts.** Each deliberate break of old behaviour, formats or state is recorded in the spec it changes (§9, item 1).
- **Manifest.** Point `manifest.json` `container` at the index digest, and update `about` and `description`.
- **Comment.** Fix `llamaCpp.mjs`'s comment: load modes arrived in b10105, and the old flags were removed in b10875 (not b11125).

**11. JIT cache.** Runners get `CUDA_CACHE_PATH` in the container's own filesystem (next to `/opt/runners`), not under `HOME=/data/home`.

- Other workspace processes can write to `/data`, which is DS004's reason for rebuilding runnable copies.
- The cost is one JIT pass per new container (Ollama's PTX-only runner; vLLM's FlashAttention 2), measured in Phase 0.

**12. Reuse weights that already exist in the workspace** (owner, 2026-09-28; §9, item 6). Phase 2. Revised after the Codex review of `d3c6a94` (`plans/local-llm-workspace-reuse-review_codex.md`, findings R1–R8; §9, item 8).

- **Trust model.**
  - **The agent's store.** The store (`/data`, `<workspace>/.data/local-llm` on the host) is written only by the agent and by the operator (the host user). Its files and records are trusted at that level. The records are a cache, not authentication.
  - **`/shared`.** `/shared` is mounted read-write into every agent in the workspace, so everything in it is untrusted input. Nothing read from it is used until a private copy has been verified.
  - **What checks prove.** Hashing proves the bytes that were actually read. Stat checks afterwards (device, inode, size, mtime, ctime) only detect accidental change. Timestamps are not a guarantee of immutability. A writer with operator access can still change a file after the last check, as it can a downloaded file today. That is outside what the agent protects.
- **Where to look, in order:**
  1. **The agent's own store**, as today.
  2. **In-place adoption.** A regular file already at the artifact's canonical store path, of the pinned size and with no valid record, is hashed and adopted where it is. This is the zero-copy path for retained or separately downloaded files: the operator hard-links the file into `<workspace>/.data/local-llm/models/...` on the host. DS002 documents the canonical paths.
     - The operator must not link a file that also stays under `.data/shared`; that would give every agent write access to it.
     - The log warns when an adopted file has other links.
  3. **`/shared/models/`** (`<workspace>/.data/shared/models` on the host). A candidate is adopted only by a private copy into the store, hashed while it is copied. It is never hard-linked. A link would share the inode with a path every agent can write. Inside the container, `/shared` and `/data` are separate mounts, where `link()` fails with EXDEV anyway.
  4. **Otherwise download**, or resume, as today.
- **Matching.** Only the pinned identity decides a match: the exact size and the pinned digest of every file. The digest is the sha256, or the pinned git blob id for small files kept in git (as in DS002). This applies to every shard of a split GGUF and every file of a snapshot. Names only order the candidates.
- **Binding verification to the bytes that were hashed** (R1, R2; clarified after the recheck, F1, F2 and F4):
  - **Anchor each lookup root once per operation** (F1). Resolve its real path and its directory identity (device and inode) before the walk. Reject a root that is a symlink, or whose identity changes. Never re-resolve it during the operation. The untrusted `/shared/models` root and the operator-trusted store root are separate policies.
  - **Open without blocking** (F2). Open the candidate with `O_NOFOLLOW | O_NONBLOCK`, so that a FIFO or device node cannot block the open. Reject any descriptor that `fstat` shows is not a regular file, before any read. Check for cancellation around every open. A pre-open `lstat` alone is not enough.
  - Confirm through the opened descriptor (`/proc/self/fd`) that the file lies under the anchored root. This also defeats swapped ancestor directories. If this cannot be established, fail closed.
  - Hash through that descriptor, and require an identical `fstat` before and after. A copy is hashed as it is written, so the digest is the private copy's own.
  - Record the identity of the object that was hashed, accounting for the ctime change caused by the agent's own rename.
  - **Downloads and resumed prefixes are bound the same way** (F4). A streamed digest plus a stat taken later is not enough. Before publication, verify the final partial through a descriptor with identical `fstat` before and after. The alternative is an invariant shown to detect any change between the agent's own writes, for example an `fstat` after each own write. A resumed prefix is bound likewise. A change during transfer or verification must be detected and never recorded as verified. Changes by an operator after the last check remain outside the guarantee (trust model).
  - Never take identity from a symlink. A symlink anywhere in the store is treated as absent and logged.
- **Staging and resume** (R5):
  - Each candidate gets its own unique staging file.
  - An existing `.partial` and its identity record stay untouched until a verified replacement is published.
  - After a mismatch, an error or a cancellation, only that staging file is removed. A later download resumes from the earlier offset.
- **Copies follow the download's rules** (R6):
  - Check free space for the copy plus the reserve before starting.
  - Copy in abortable chunks, so Stop, Cancel and drain settle within one chunk.
  - Report copying and verifying progress.
  - Report ENOSPC and other I/O errors as errors, never as "no candidate found".
- **Disk admission uses the bytes actually needed** (R4). The acquisition plan decides the disk term of admission and its previews:
  - 0 for files already owned or adoptable in place;
  - the full size plus the reserve for a copy;
  - the remaining bytes for a download.

  Run, preview and overview agree. Memory and GPU refusal still come before any hashing or copying.
- **Snapshots** (R3, F3). Create the final, staging and record (`.state`) directories under the store root, rejecting symlinked ancestors, before adopting. This includes in-place adoption of an unrecorded canonical snapshot. A fresh snapshot can then be adopted file by file, mixed with copies and downloads.
- **Last check before loading.** Just before the runner starts, stat-check every file of the artifact, and re-hash any whose identity changed. This is detection of accidental change, not a lock.
- **Provenance** (R7). Every file and shard carries one shape: file, source, method (`in-place`, `copy`, `download`) and bytes. The deployment log and results show it for single files, split GGUFs and snapshots. Hashing shows as the `verifying` phase.
- **Delete weights** (R8). It removes the agent's own files. `freedBytes` counts the logical size of each distinct inode (device and inode) whose last link the deletion removed. An inode that still has a link outside the deletion set counts 0.
- **Bounded, cancellable lookup.**
  - One streaming walk per artifact, collecting every needed size at once.
  - The depth and entry limits apply, and the walk checks for cancellation.
  - Acquisition planning during admission is cancellable too (F5). Stop, Cancel and drain signal it before waiting behind the Run, and the traversal stops once the pending read returns.
  - At most 3 same-size candidates are hashed per file, those whose names match first.
- **Scope.** `gguf` (including split GGUF) and `hf-snapshot`. Ollama's store stays as it is. Nothing outside the workspace is searched.
- **Specs.** DS002 covers the lookup order, trust model, canonical paths, provenance and freed bytes. DS003 covers the disk term of admission.
- **Regression tests (desired behaviour).** Each Codex reproduction becomes a test of the fixed behaviour. All use small disposable fixtures, with no GPU and no network.
  1. A fresh HF snapshot adopted from `/shared/models`, with git-blob-id and sha256 files and no final directory beforehand, completes with 0 network bytes. The same holds for a partly present snapshot and a mix of adopted and downloaded files.
  2. A write to the source during hashing, including after the last chunk, makes the adoption fail or retry. No record ever pairs a digest with bytes that were not hashed, and the next Run does not trust the changed bytes.
  3. A symlink at the store's canonical path, or in any ancestor, is never adopted or trusted. Later edits to its target are never accepted.
  4. A wrong same-size candidate in `/shared/models` beside a valid 131,072-byte partial: the download resumes with `Range: bytes=131072-`. The same holds after a copy error or a cancellation.
  5. A copy with too little free space is refused before copying, with a space error that admission and previews also show.
  6. A real controller Run whose file can be adopted in place, with less free disk than the model's size, is admitted and adopts it with 0 network bytes.
  7. A correct file at the canonical path, with no record, is adopted in place with 0 downloads.
  8. The log and results name every file's source and method, for a single GGUF, each shard of a split GGUF and each snapshot file. No `undefined` appears.
  9. A `/shared` subdirectory swapped for a symlink during the walk leads to no adoption from outside `/shared/models`.
  10. An abort during a copy and during hashing, directly and through controller Stop, Cancel and drain, settles within one chunk. Only the staging file is removed, and the earlier partial is intact.
  11. Deleting a snapshot whose two files are links to one inode reports that inode's size once. With an extra link outside the snapshot, it reports 0.
  12. A split GGUF with mixed sources (one shard in place, one copied, one downloaded) and one corrupt candidate is complete only when every shard verifies.
  13. Many same-size decoys under `/shared/models`: at most 3 are hashed per file, and the walk stops promptly on abort.
  14. A file whose stat identity changed at the last check before the runner starts is re-hashed before the load.
  15. The `/shared/models` root itself is swapped for a symlink to a sibling directory holding a correct file during lookup. Nothing is adopted from outside the anchored root (F1).
  16. A regular candidate is replaced by a FIFO just before it is opened. The open does not block; the candidate is rejected, and an abort settles promptly (F2).
  17. A canonical, unrecorded HF snapshot, with no `.state` directory, is adopted in place with 0 network bytes. A mixed snapshot with one file in place, one copied and one downloaded also completes (F3).
  18. A byte changed in the partial during or after the transfer, before publication, is detected and never recorded as verified. The same holds for a resumed prefix changed between attempts (F4).
  19. Equal-size split shards from mixed sources, with a same-name, wrong-digest decoy and a bad downloaded shard, are complete only when every shard's own digest matches.
  20. In the real controller, an artifact changed after the fetch and before launch leads to an error, with zero runner launches. This covers where the last check runs, not only `verifyArtifact`.
  21. A real controller Stop during acquisition planning stops the traversal after the current pending read, with no further directory opens. Stop settles promptly (F5).
  - Every test and reproduction on this host runs under the exclusive measurement lock (`flock -x /home/research/phase0/.memlock`).
- **Acceptance on the Spark** (nested, in the test workspace, after the hardware measurements):
  - The operator hard-links a retained pinned model (gpt-oss-20b) into the canonical store path. Run adopts it in place with 0 network bytes, and the sha256 matches.
  - A small pinned model placed under `.data/shared/models` is copied and verified. Record the time and peak disk use.
  - Correct bytes and zero network transfer are shown separately from runner performance.
  - The retained real models are only linked and read. They are never modified or deleted (§9, item 7).

### D. `local-llms` cleanup (independent)

**Delete:**

- the twelve legacy agents: `local-llms-manager` and eleven model agents (`language-translation`, `relevance`, `function-selection`, `function-invocation`, `tool-composition-local`, `base-local`, `local`, `planning-local`, `validated-planning-local`, `adaptive-local`, `coding-local`);
- the repo-root `Dockerfile` (`assistos/local-llms`), `scripts/`, `catalog/` and `tests/validate.mjs`;
- `docs/specs` DS000–DS011 with their HTML docs.

**Before the deletion, or in the same change:**

- **Coding style.** Keep the coding-style rules: move the repository's `DS001-coding-style.md` into local-llm's spec set. It is item 2 of `AGENTS.md`'s mandatory reading order.
- **Spec references.** Rewrite the references to the deleted specs, with commit links:
  - local-llm DS000 ("Relation to the legacy agents");
  - DS002 and DS003 ("Reuse from repository DS008/DS010");
  - local-llm `matrix.md`.
- **HTML docs.** Either replace `docs/index.html` (with `specsLoader.html`, `partials-loader.js` and `styles.css`) with local-llm documentation, or remove them and change AGENTS.md's rule that code changes update the HTML docs.
- **Dropped services.** Record in local-llm DS000 what is dropped: the translation (seq2seq) and reranking services, and CPU-only serving. local-llm replaces none of them (decision 10).
- **Record the removal** in local-llm DS000 as a changed contract: a legacy agent that a workspace enables disappears on update, and no model data is deleted. No migration path or compatibility shim is required (§9, item 1).
- **Optional:** tag the last commit before the deletion, and mark `assistos/local-llms` deprecated on Docker Hub (arm64-only, last pushed 2026-05-27).

**Also:**

- Rewrite `README.md`, `AGENTS.md` (scope, test command) and `docs/handoff-local-llms.md` around the one agent.
- Searches found no dependency on the legacy agents in:
  - the installed repos;
  - Ploinky;
  - AdvancedLanguageAgent;
  - AchillesAgentLib (the Box image's copy).

  They found only unrelated fixture strings: `planning-local`, and `llm-runtime/base-local`, which is another repository's agent.
- Follow the repo's `CLAUDE.md`: no AI co-author trailers, no `codex/` branch prefix.

### E. Explorer (AssistOSExplorer)

- **No code change.** The enable line `local-llms/local-llm no-wait`, the plugins and the smoke test's `MINIMUM_REVISIONS` entry stay as they are. That table guards against missing manifests in old sibling checkouts; it says nothing about runtime capability.
- **Smoke runs on a Spark.** After A1, a Spark's Box carries a GPU grant label, so Spark smoke and E2E runs must set `SMOKE_BOX_GPU_GRANT` (`tests/smoke/lib/box-evidence.mjs`).
- **Phase 3 acceptance on the Spark.** Designate an existing smoke check or add one. It must show three things:
  - the no-wait agent starts;
  - its dashboard shows the unified profile and the unavailable runners;
  - a small model answers through Soul Gateway.

## 5. Phases

**Phase 0: host-level measurements, without Ploinky.** It can start now and runs alongside Phase 1.

1. **llama.cpp builds.**
   - Build three candidates:
     - L1, the prebuilt release;
     - L2, the source build, exactly as in B2, including `llama-bench`;
     - a playbook-native build as a reference. On this CPU it gets baseline armv8-a CPU code, so it is not a ceiling.
   - Run `llama-bench` for prefill and decode, at 0 and 32K depth, on gpt-oss-20b, Qwen3.6-35B-A3B MTP and gpt-oss-120b.
     - Use identical runtime flags: `-ngl 99 -ub 2048 -fa on`, fixed context and slots, and loading without mmap both with and without direct I/O.
     - Take repeated samples and apply a tolerance declared in advance.
   - Check correctness: identical greedy output, or the same perplexity on a fixed text.
   - Run `cuobjdump` on L1's `libggml-cuda.so`.
2. **Memory.**
   - Record the peaks of MemFree, MemAvailable and Cached through download and hash, load, full prefill, parallel slots and MTP.
   - Measure the load rate.
   - Check whether direct I/O keeps the page cache from growing.
3. **Ollama gate (decision 2).** Which backend Ollama selects, first-load JIT time and cache size, memory use, tool calls, and the final layer size.
4. **Optional.** vLLM feasibility in a host container.
5. **Disk.**
   - Keep a table per step with a 20 GB free floor. Changed on 2026-09-28 (§9, item 7): model files are kept while disk space allows, until the implementation no longer needs them. None is deleted without the owner's go-ahead. The original rule, deleting between steps, cost two re-downloads.
   - First stop the existing Explorer deployment, and destroy it when its disk is needed. That frees the memory its 15 agents use and its Box image store (about 13 GB, including the dead 4.91 GB amd64 image).
   - Deleting only the dead image does not last. While Explorer's graph enables local-llm with the amd64 pin, the next `ploinky start`, `restart` or `update` of that workspace pulls the image again (4.57 GB, about 620 s; `ensureImagePresent`, `ploinky/cli/sandbox/docker/common.js:269`) and fails again.

*Gate:* decisions 1 and 2 are taken, and the admission constants, guard floor and measured envelope are calibrated.

Status on the evening of 2026-09-28: decisions 1 and 2 are taken. The constants stay provisional until the measurements listed in `plans/phase0-safety-followup_codex.md` are done and reviewed (§9, item 5).

**Phase 1: A1 (+A2) and C0, then a nested check in a fresh test workspace run by the development Ploinky clone. D runs in parallel, once its spec dependencies are handled; it is not on the critical path.**

- Give the test workspace's Box GPU wiring.
- Enable only local-llm there.
  - Each workspace's Box has its own image store at `<workspace>/.ploinky/box/images`; the Box's `storage.conf` sets `imagestore` to that bind mount.
  - Running Explorer's whole graph there would pull about 13 GB again. The disk table counts the test store instead: the arm64 dev image plus the `ploinky-node` base.
  - Alternatively, reuse `/home/research/work` after stopping the deployment and deleting its image store.
- Load the dev image into its image store by hand; Ploinky has no hook for building local images.
- A nested agent container runs a CUDA probe and a small model, and repeats the GB10 memory measurements inside the container.

*Gate:* A1 and C0 unit tests pass, and the GPU works from a nested container on arm64.

**Phase 2: C1–C12, including C4.** llama.cpp; no Ollama on arm64 (decision 2); vLLM refused on unified memory. C12 lets later steps, such as the Spark acceptance, use model files already in the workspace.

*Gate, before merging, because the shared JavaScript reaches x86 hosts at this point (changed; §9, items 1 and 2):*

- the dedicated-profile tests pass against the intended behaviour. Deliberate changes are listed, not treated as failures;
- the x86 functional gate on ubuntu-codex (decision 5) runs gpt-oss-20b with llama.cpp and with Ollama:
  - engineering supplies the exact candidate revisions and a procedure sized for the host's 6 GiB GPU, using supported partial offload if that is the validated dedicated-profile path. The 12 GB model is never treated as fully offloaded on 6 GiB;
  - Codex coordinates the run from the owner's Mac at candidate readiness. It stays isolated from the host's existing workspace (`/home/skutner/work/file-parser`) and services;
  - the result records what actually happens: a working run, the real constraint, or the expected rejection. A pass is never assumed.

**Phase 3: B1–B4.** amd64 reuse-and-prove (or rebuild-and-prove, B1), arm64 build-and-prove, the install checks and the index. Then, in order:

1. Spark acceptance in the test workspace (E). The test workspace runs a local-llms candidate that already carries the new pin.
2. Change the manifest pin to the index.
3. Re-run the x86 functional gate (decision 5) with the new pin.
4. If Explorer is wanted on this host again, redeploy it from the released revisions, and check that local-llm starts with the GPU and serves a model.

*Gate:* acceptance passes on both architectures.

**Phase 4: vLLM on arm64.**

- A new arm64 image with the vLLM lock entry: the aarch64 closure of 196 wheels.
- The install check validates every installed distribution against the lock, not only the few listed under `check.distributions`.
- A FlashInfer policy (decision 7), with no unpinned run-time downloads; a run without network access proves it.
- Attention and MoE backends pinned per model family.
- `--gpu-memory-utilization` computed from MemAvailable at start.
- A gpt-oss correctness test (vLLM #37030).
- A policy for compile caches (decision 8).
- A check on the real GPU that the imports and a chat work. The CI install check labels any failed GPU-only import as "needs a GPU", so it cannot tell a missing GPU from a broken import.
- The Box pid limit (A3), if vLLM's task count requires it.

*Gate:* vLLM acceptance on the Spark.

**Phase 5: later work that benefits both architectures.**

- Several resident models: named deployments, per-deployment ports, `endpoints.models.command`, and dispatch on `request.model`.
- Self-calibrating admission from measured memory.
- A benchmark tool.
- Soul Gateway patches: reasoning passthrough, keep-alive and per-model timeouts, together with the long-completion budgets (decision 9).

## 6. Decisions

Decided: 1–6 and 9. Dates and sources are in the implementation log's decisions table. Still open: 7, 8 and 10.

1. **llama.cpp on arm64: L1 (prebuilt) or L2 (source build).**
   - **Decided 2026-09-28: L1.** The correctness criterion changed. Greedy output is not bit-identical across CUDA toolkits (13.4 vs 13.0). So the op tests (16445/16445 on both), perplexity and throughput replace token-identical greedy output as the check.
   - The rule it was decided under follows.
   - Both candidates must pass the correctness check on driver 580.
   - If L1 is within the predeclared tolerance of L2, ship L1. It keeps the amd64 supply chain (sha256-pinned release assets, no builder stage) and brings CUDA 13.4's newer CCCL and cuBLAS.
   - Otherwise, ship L2 with its B2 fixes. It matches the CUDA 13.0 driver exactly.
   - codex-gpt-6 starts from L2 as the prototype; claude-code-opus-5-5 expects L1. Both accept this rule.
2. **Ollama on arm64: left out of the first arm64 image unless its Phase 0 gate passes.**
   - **Decided 2026-09-28: left out** of the first arm64 image; amd64 keeps Ollama. It worked in the gate. But it decoded at 58 tokens/s against 80–82 for llama-server, it needed 22 s of JIT in each new container and 3 GiB more memory, and it adds 2.1 GB unpacked.
   - It has no native sm_121 code, so it JIT-compiles on first load. With a container-local cache (C11), that happens once per container.
   - It is the same ggml engine as llama.cpp.
   - It adds a 1.5 GB archive to every arm64 install.
   - codex-gpt-6: include it if the gate passes. claude-code-opus-5-5: drop it for now.
   - If it is left out, the adapter reports "not available on this platform".
3. **LM Studio: stays amd64-only.** Both reviews agree.
4. **amd64: reuse `b6c79…` in the first index** through the reuse-and-prove job; both reviews agree. Rebuild when the amd64 contents change, or when the shared code needs something the reused image lacks. Reuse is a cost choice, not a compatibility requirement (§9, item 1).
5. **Which x86 GPU host gates Phase 2.**
   - **Decided 2026-09-28: ubuntu-codex.** It has an x86_64 CPU, an NVIDIA GeForce RTX 3060 Laptop GPU with 6144 MiB, driver 595.91.07, about 26 GiB of available RAM, 398 GiB of free disk and podman. No compute workload was running when it was inspected.
   - It is reached over SSH (user `skutner`) from the owner's Mac, and Codex coordinates the run.
   - The test is gpt-oss-20b with llama.cpp and Ollama, sized for 6 GiB (see the Phase 2 gate).
6. **The first release's model set and Phase 0 disk budget.** **Decided 2026-09-28:** gpt-oss-20b, Qwen3.6-35B-A3B MTP (UD-Q4_K_XL) and gpt-oss-120b (MXFP4), downloaded one after another, with a 20 GB free floor.
7. **FlashInfer on arm64 (Phase 4).** Either lock `flashinfer-cubin` and `flashinfer-jit-cache` 0.6.18.post1 from flashinfer.ai (which adds a host to `ALLOWED_HOSTS` and to DS004), or keep FlashInfer off and block vLLM's artifactory probe.
8. **vLLM compile caches (Phase 4).** Either keep them in the container (a warm-up per container; today's design), or put them under `/data` with a hash manifest checked before use.
9. **Long completions.** Are 32,000-token responses a first-release requirement? **Decided 2026-09-28: no.** The first release keeps coherent, explicit completion budgets and deadlines (C7). 32,000-token responses, and the endpoint and Soul Gateway deadlines they need, stay in Phase 5.
10. **Legacy translation and reranking.** Retire them with D (proposed), or keep them somewhere.

## 7. Key locations (on the DGX Spark host)

| What | Path |
| --- | --- |
| Ploinky workspace root | `/home/research/work` |
| Ploinky checkout (mounted into the Box at `/opt/ploinky`) and its CLI (not on PATH) | `/home/research/work/ploinky`, `/home/research/work/ploinky/bin/ploinky` |
| Installed repos of the existing Explorer deployment (develop in separate clones, not in place) | `/home/research/work/.ploinky/repos/{local-llms,container-image-builds,AchillesIDE,proxies,...}` |
| local-llm agent | `/home/research/work/.ploinky/repos/local-llms/local-llm` (specs in `docs/specs/`) |
| local-llm image definition | `/home/research/work/.ploinky/repos/container-image-builds/images/local-llm` |
| Explorer manifest | `/home/research/work/.ploinky/repos/AchillesIDE/explorer/manifest.json` |
| Soul Gateway | `/home/research/work/.ploinky/repos/proxies/soul-gateway` |
| Box container and its image store | `podman ps` on the host (name `ploinky-box-work-*`); `/home/research/work/.ploinky/box/images` |
| Reviews of this plan | `/home/research/work/plans/local-llm-multiarch-plan-review-*.md` |
| Implementation log; Phase 0 safety follow-up | `/home/research/work/plans/local-llm-multiarch-implementation-log.md`; `/home/research/work/plans/phase0-safety-followup_codex.md` |
| x86 functional-gate host (decision 5) | ubuntu-codex, reached over SSH from the owner's Mac (user `skutner`), not from this host |

## 8. Review response

Two reviews covered version `a8f8085b…`: claude-code-opus-5-5 (F1–F15) and codex-gpt-6 (findings 1–11).

| Finding | Change |
| --- | --- |
| Memory safety: GPU memory is invisible to RSS, the OOM score and cgroups, and a 2 s guard is too slow (opus F1); peaks are not measured (codex 1) | C3; C2 constants and the measured envelope from Phase 0; Phase 0 item 2 |
| The x86 gate comes after the shared code ships (opus F2) | Phase 2 gate; C1's second query, fail-closed limited to admission values, and the thread rule |
| Profile plumbing, static `supported`, and downloads before failing (opus F3); C4 missing from the phases (codex 2) | C4 and C6, both in Phase 2 |
| Phase 0 disk and the live workspace (opus F4; codex 10) | Phase 0 disk table and floor; model sizes in §3; the nested check in a fresh test workspace. Since then, the owner has allowed stopping or destroying the Explorer deployment. |
| vLLM before its design, FlashInfer, the artifactory probe, and caches (opus F5; codex 2) | B3's empty first arm64 lock; C4; Phase 4; decisions 7–8 |
| The detection rule (opus F6); memory topology and kernel support (codex 7) | C1's rule with the device ID; C4's GPU check; `gpu_compute_capabilities` in `source.contract` |
| Stale flags, `dio`, `preserve_thinking`, same-type K/V (opus F7; codex 6) | C5 |
| Prebuilt vs source, the correctness check, `cuobjdump` (opus F8) | B2's L1 and L2; B4; Phase 0 item 1; decision 1 |
| Build identity of a source build (codex 3) | B2's L2: fetch by commit, plus `LLAMA_BUILD_NUMBER` and `LLAMA_BUILD_COMMIT` |
| The Triton `libcuda.so` link; image ENV does not reach runners (opus F9; codex 9) | Removed from B2 |
| Workflow and tests, the reuse proof, the revision label, RUNPATH (opus F10; codex 4) | B1; B2's L2 RUNPATH; B4 |
| A2's items (opus F11) | A2–A3; `uvm-tools` and `stack` dropped |
| Cleanup: the count, coding style, cross-references, dropped services (opus F12; codex 11) | D; decision 10 |
| The JIT cache in `/data` (opus F13) | C11 |
| Explorer smoke (opus F14); a start-and-answer acceptance (codex, missing work) | E |
| Catalog sizes, split GGUF, DS002, the dead image, "amd64 only" wording (opus F15; codex 11) | C6, C10, B4, Phase 0 |
| Chat limits vs the outer deadlines (codex 5) | C7; decision 9 |
| The KV "context × slots" double count (codex 8) | C2 |

## 9. Owner decisions after Phase 0 (changed contracts)

Recorded on the evening of 2026-09-28, from `b5a95376…`. Each item gives the owner's decision, then every place in this plan it changed. The implementation log's decisions table has the dates and sources; Codex, the owner's coordinator, relayed them. The targeted Phase 0 safety review is `plans/phase0-safety-followup_codex.md`. Codex runs the later independent final review separately.

1. **No backward compatibility.** The owner: "we don't care about backwards compatibility". This supersedes the byte-identical dedicated-profile requirements, and every requirement that existed only to migrate old state or keep old output.
   - What stays:
     - x86/amd64 and arm64 must both work;
     - the security, correctness and memory gates stay;
     - reviews judge the intended current behaviour and security on both architectures. Deliberate compatibility breaks are not defects, and no test must stay unchanged only to prove old behaviour;
     - every deliberate break is recorded in the spec it changes (C10).
   - What changed:
     - §1: the goal is working on x86 hosts, not unchanged behaviour there.
     - §2, B1 and decision 4: reusing the amd64 digest is a cost choice. amd64 is rebuilt when the shared code needs it, rather than adding compatibility branches.
     - A1: x64 wiring and fingerprints may change.
     - C1: the first `nvidia-smi` query need not stay byte-identical.
     - C2: the dedicated policy and constants may change, validated by the x86 gate.
     - C4: a rebuilt amd64 image carries `gpu_compute_capabilities`.
     - C5: the dedicated argv need not stay unchanged.
     - C6: there is no registry migration, and old state need not stay readable. Unsupported state is refused or reset with a clear message, never misread.
     - C9: tests check the intended behaviour, and characterization tests change with deliberate changes.
     - D: the removal is recorded; tags and deprecation notices are optional.
     - Phase 2 gate: it validates function, not unchanged behaviour.
2. **Decision 5: the x86 functional gate runs on ubuntu-codex** (§6, item 5).
   - Engineering supplies the exact candidate revisions and a gpt-oss-20b procedure for llama.cpp and Ollama, sized for 6 GiB. That means supported partial offload, if that is the validated dedicated-profile path; the 12 GB model is never treated as fully offloaded on 6 GiB.
   - Codex runs the gate from the owner's Mac, isolated from that host's existing workspace and services.
   - The result records what actually happened: a working run, a real constraint, or the expected rejection.
   - Changed: the Phase 2 gate and Phase 3 step 3.
3. **Decision 9: no 32,000-token requirement for the first release.** Changed: C7, §3 (consumer side) and Phase 5.
4. **Decisions 1, 2 and 6** (§6), plus the unified load defaults in C5:
   - `dio`;
   - `posix_fadvise(DONTNEED)` after the checksum.

   Changed:
   - B2: L1, and no Ollama on arm64;
   - C2 and Phase 2: no Ollama on arm64;
   - C5.

   Decision 1 is recorded as a changed correctness criterion, not as a pass of the original one.
5. **Unified memory safety after Phase 0.** The owner approved the safety follow-up.
   - Admission is computed from:
     - llama.cpp's logged buffer sizes and a measured runtime constant;
     - an independently measured transient margin per model and per slot class;
     - the prompt cache's explicit bound, which stays at 8192 MiB until smaller settings pass.
   - The envelope's key pins every memory-relevant parameter.
   - The guard samples every 250 ms throughout, and kills the runner's process group at once on an actual floor breach.
   - Stop and release latency are measured, during a load and during active requests, before the guard constants are fixed. Until then, the host reserve (16 GiB), the floor (8 GiB) and the PSI rule are provisional.
   - `oom_score_adj` is only a backstop. Userspace sampling cannot promise protection against arbitrary allocations by other processes on a shared host.
   - Approved measurements: re-download the pinned gpt-oss-120b, then take repeated, trace-logged measurements of the corner, the cache and stop latency, within the 20 GB free-space floor.
   - Changed: §3 (the prompt-cache fact), C2, C3 and the Phase 0 status.
6. **Reuse model files that already exist in the workspace.** The owner: "If the model exists in the workspace we should use it instead of downloading it over and over again."
   - Before downloading, the controller looks in its own store and adopts a correctly placed file in place. Otherwise it copies a verified candidate from the workspace's `/shared/models/`.
   - It adopts a file only if its exact size and pinned digest match.
   - The requirement, design limits and security rules are my draft, revised under item 8 and relayed to engineering, who own the design details.
   - Changed: the new C12, the Phase 2 list, DS002 and DS003.
7. **Model files are kept while disk space allows, until the implementation no longer needs them.** The owner: "If we have space we should keep these models until no longer needed for the implementation."
   - No model file is deleted without the owner's go-ahead.
   - This replaces the Phase 0 rule of deleting between steps, which had forced re-downloads of gpt-oss-120b and Qwen3.6.
   - Changed: Phase 0, item 5.

8. **Codex review of C12 at `d3c6a94`** (`plans/local-llm-workspace-reuse-review_codex.md`, 2026-09-28). The six major findings (R1–R6) and the two minor ones (R7, R8) must be fixed before C12 is accepted. The review's design notes are resolved in C12. In the table, *implementation fix* means the plan already required the behaviour; *changed contract* means the plan now requires something new or different. The test numbers are C12's regression tests.

   | Finding | Class | Plan action (C12) | Tests |
   | --- | --- | --- | --- |
   | R1: bytes changed during hashing were recorded as trusted | Implementation fix. Contract clarified: verification is bound to the hashed object | Binding verification to the bytes that were hashed; trust model | 2, 14 |
   | R2: symlinks and swapped ancestors escaped confinement and defeated re-checks | Implementation fix (regular files only was already required). Contract extended to the own store, to ancestors, and to identity taken from the opened descriptor | Binding verification to the bytes that were hashed | 3, 9 |
   | R3: the first file of a fresh snapshot failed with ENOENT | Implementation fix | Snapshots | 1 |
   | R4: disk admission demanded the full download size before reuse was tried | Changed contract: disk admission uses the bytes the acquisition plan needs, and previews agree | Disk admission uses the bytes actually needed; DS003 | 5, 6 |
   | R5: a wrong candidate destroyed a valid resumable partial | Implementation fix (resuming was already required). Staging made explicit | Staging and resume | 4, 10 |
   | R6: the copy fallback skipped the space check, cancellation and error reporting | Implementation fix (the download's rules already applied). Made explicit for copies | Copies follow the download's rules | 5, 10 |
   | R7: provenance missing or `undefined`; misleading progress | Implementation fix (DS002 already required provenance in the log). One provenance shape | Provenance | 8 |
   | R8: snapshot deletion under-reported freed bytes | Implementation fix. Definition made explicit | Delete weights | 11 |
   | Note: `link()` returns EXDEV across the `/data` and `/shared` mounts | Changed contract: no hard links from `/shared`; copy only | Where to look, step 3 | Acceptance |
   | Note: shared writers and immutability | Changed contract: an explicit trust model, where stat checks detect accidents only | Trust model; last check before loading | 2, 14 |
   | Note: an unrecorded file at the canonical path was downloaded again | Changed contract: in-place adoption, the zero-copy path | Where to look, step 2 | 6, 7 |
   | Note: the plan said sha256 where DS002 pins git blob ids | Plan wording now matches DS002: the pinned digest | Matching | 1 |
   | Note: repeated, uncancellable walks | Changed contract: one cancellable walk per artifact, at most 3 candidates hashed per file | Bounded, cancellable lookup | 13 |
   | Note: model retention | Unchanged. Tests use disposable fixtures, and real models are only linked and read | Acceptance on the Spark | — |

9. **Codex recheck of C12 at `d68c70fe`** (`plans/local-llm-workspace-reuse-recheck_codex.md`, 2026-09-28; 310/310 tests confirmed). R4, R5, R7 and R8 are resolved under the revised contract. R1, R2, R3 and R6 are partly resolved, leaving five reproduced findings (F1–F5) before acceptance. No hard links from `/shared` and no backward compatibility are to be restored. The limitation for operator writes after the last check stays explicit. *Plan clarification* means C12 now states the requirement explicitly; *implementation fix* means the existing text already required it.

   | Finding | Class | Plan action (C12) | Tests |
   | --- | --- | --- | --- |
   | F1 (major): swapping the `/shared/models` root re-defines the allowed boundary | Implementation fix; plan clarification: roots are anchored by path and identity for the whole operation | Binding verification: anchor each lookup root | 15 |
   | F2 (major): a candidate replaced by a FIFO blocks the open before validation, ignoring abort | Implementation fix; plan clarification: non-blocking, no-follow open, and rejection of non-regular files before any read | Binding verification: open without blocking | 16 |
   | F3 (major): in-place adoption of a canonical HF snapshot fails, because `.state` is missing | Implementation fix (in-place snapshot adoption was already required); small clarification | Snapshots | 17 |
   | F4 (major): download finalization pairs a streamed digest with a later stat | Plan clarification: binding covers downloads and resumed prefixes explicitly; implementation fix | Binding verification: downloads and resumed prefixes | 18 |
   | F5 (minor): Stop cannot cancel acquisition planning | Implementation fix; small clarification | Bounded, cancellable lookup | 21 |
   | Observation (not one of the five): the final pre-launch re-hash displays as `starting` | Implementation fix only: C12 already requires hashing to show as `verifying` | Provenance (unchanged) | — |
   | Coverage gaps named by the recheck | New regression tests | Regression tests | 15–21 |

   Every test and reproduction on this host runs under the exclusive lock. The recheck's own earlier test runs (local time, conservative bounds): the full suite, 15.6 s, ran between 20:42:16 and 20:44:20; fixture iterations ran from about 20:44:20 to 20:48:02; no test process remained at 20:48:19. These are kept only as possible correlation evidence for memory runs in that window.

10. **Memory evidence and release acceptance** (the owner, via Codex, 2026-09-28).
    - Finish the functional matrix and the stop-latency checks, keeping every attempt.
    - One automatic re-run round follows, behind a quiet-host scheduling gate:
      - non-runner memory must be steady within 0.25 GiB for 60 s before a run starts;
      - the lock is released while waiting;
      - after 30 min without a quiet interval, the configuration is deferred and reported.

      No further rounds are run without a new decision.
    - A functional run is never aborted because an external-memory proxy moved, and unvalidated attribution never filters out peaks.
    - The maximum of inconclusive or lower-bound peaks is not a safe constant. Envelopes for unvalidated models and configurations stay unavailable. No release acceptance is claimed until there is clean agreeing evidence, or an independently justified upper-bound method. No new margin or guard constant is approved.
    - Changed: C2 (a measured envelope needs validated evidence), C3 (the guard constants stay provisional) and the Phase 3 acceptance.
    - Evidence and classifications: `plans/phase0-followup-data-quality_codex.md` (revision 5).
