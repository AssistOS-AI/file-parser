# Agent "Audit local-llm internals for reuse" finished

> Verbatim subagent result from the pgx-research session `local_2ef99e76-6bed-4e68-bf4a-d611494a62a5` (CLI `e95c870c-8d4a-46a7-bacf-21525480837e`), transcript record uuid `3e206326-c667-4317-842d-54406c15d812`, 2026-09-28T10:53:58.385Z.
> File paths are on the pgx host under `/home/research/work`, not on this Mac.

## local-llm reuse audit for a DGX Spark agent (GB10, aarch64, UMA)

**Most important finding:** local-llm on this machine doesn't just fail, it approves everything. `readGpu` (`src/controller/hardware.mjs:63-65`) turns `[N/A]` into NaN, and every comparison with NaN in `admission.mjs` is false. I ran `admit()` against a live GB10 snapshot: every seed model returned `ok`, and so did a made-up 500 GiB dense GGUF and a 300 GiB vLLM snapshot. vLLM then fails at launch, because `gpuMemoryUtilization` comes out as NaN and `vllm.mjs:116` throws `invalid_launch`. All GPU checks are silently off.

Nothing was modified. The only file I wrote was a small admission probe in the scratchpad.

### 1. Module classification

A = reuse as-is, B = reuse with changes, C = replace.

| Module | Purpose | Class and what changes |
|---|---|---|
| `main.mjs`, `controlSocket.mjs`, `errors.mjs`, `drainBudget.mjs` | Main process, private control socket with token, drain timing | A |
| `testPrompt.mjs` | Admin smoke chat over loopback | A. Only the `GATEWAY_MODEL` name changes (`:19`, `deployments.mjs:363`) |
| `chatResponder.mjs` | `/v1/chat/completions` proxy | B (see §1d) |
| `controller/commandQueue.mjs` | Serialized mutations | A |
| `controller/stateStore.mjs` | Atomic state writes and restart recovery | A for one deployment, B for several (`deployment: null` at `:21`, `reconcileAfterRestart` `:100-119`) |
| `controller/catalog.mjs` + `schema.json` | Catalog validation | B. GGUF is one file only (`:73-77`), so split GGUFs (`-0000N-of-M`, common for 60–120 GB models) can't be expressed. Snapshots are top-level files only (`:102`) |
| `controller/downloader.mjs`, `weightStores.mjs`, `ollamaStore.mjs` | Resumable, sha256-pinned downloads | A. Add a multi-file GGUF store by reusing the snapshot code |
| `controller/runnerProcess.mjs` | Process group, log buffer, report parser | A (the `CUDA0` regexes still match on GB10) |
| `controller/hardware.mjs` | Hardware snapshot | C for `readGpu`/`readSnapshot`. `physicalCoreCount` is A (returns 20 here). `defaultThreads` is B: 18 threads includes the A725 efficiency cores |
| `controller/admission.mjs` | Fit decisions | C (§1a) |
| `controller/runnerLock.mjs` | Runner lock schema | B. `ALLOWED_HOSTS` (`:42-51`) has no `pypi.nvidia.com` or `wheels.vllm.ai`. Files have no platform field (`:106-143`), so one lock = one architecture |
| `controller/runnerInstaller.mjs` | Offline `uv` venv build | B. Python is fixed to `/usr/bin/python3` 3.13 (`:28`, `:284`, `UV_PYTHON_DOWNLOADS=never`); TensorRT-LLM has historically shipped cp310/cp312 wheels only |
| `controller/deployments.mjs` | The controller | B. Nothing arch-specific, but one deployment is assumed throughout (§1c) |
| `runners/index.mjs`, `params.mjs` | Adapter registry, param validation | A |
| `runners/llamaServer.mjs`, `llamaCpp.mjs` | llama-server family | B: new sm_121 binary, and `admit` is hard-wired (`llamaServer.mjs:236`) |
| `runners/ikLlamaCpp.mjs` | ik fork | C. Its hybrid CPU/GPU MoE advantage means nothing on UMA; drop it |
| `runners/ollama.mjs` | Ollama | B: arm64 binary; `OLLAMA_MAX_LOADED_MODELS=1` (`:109`); `admitOllama` is C |
| `runners/vllm.mjs` | vLLM | B (§1b) |
| `runners/tabbyApi.mjs` | ExLlamaV3 | C: cu128 x86 wheels, sm_121 support unknown |
| `runners/lmStudio.mjs`, `lmStudioLoad.mjs` | LM Studio | C: `ENGINE_DIR` is the x86_64 CUDA 12 engine (`:37`), and it's proprietary |
| `tools/local_llm_tool.mjs`, `runner_install_check.mjs` | MCP tool dispatch, CI install check | A (B once tools take a deployment id) |
| `catalog/models.json` | Seed models | C. Its values are tuned for a 6 GB card (e.g. `nCpuMoe: 17`). It is swappable through `LOCAL_LLM_CATALOG_FILE` (`deployments.mjs:70`) |
| `mcp-config.json` | 12 admin tools | A, or B for multi-deployment |
| IDE plugins (1,599 lines of JS) | Dashboard | B. The GPU card and estimate meter read `gpu.totalBytes/usedBytes` (`local-llm-dashboard-view.js:63-71, 350-357`), which are NaN here |

**1a. `admission.mjs` is built on a separate VRAM pool and RAM pool.**
- **llama-server estimate:** weights are split into `gpuWeights`/`cpuWeights` by `nCpuMoe`. The GPU part is checked against `gpu.totalBytes*0.97` and `gpu.freeBytes-256 MiB` (`:132, :140`); the RAM part separately against `availableBytes-1 GiB` (`:144`). On UMA those two checks double-count one pool.
- **vLLM:** `VLLM_USABLE_SHARE 0.94`, `VLLM_MAX_UTILIZATION 0.9` and the 768 MiB overhead (`:200-203`) were measured on an RTX 3060. The GPU share it passes vLLM is computed from free VRAM (`fromFree`, `:231`, NaN here).
- **vLLM `cpuOffloadGb`:** its RAM estimate is 1.81× the offload + 3 GiB, ×1.15 (`:214-218`). On UMA, offload adds no capacity and would consume the same pool twice.
- **Memory guard:** it only runs when admission sets `ramFloorBytes`, i.e. vLLM with offload (`deployments.mjs:530-560`). With no swap on this machine, it should run for every deployment.

**1b. `vllm.mjs` flags** (`:121-135`):
- Always passed: `--model`, `--served-model-name`, `--host 127.0.0.1`, `--port`, `--max-model-len` (default 4096, max 131072), `--gpu-memory-utilization`, `--max-num-seqs` (default 1), `--dtype`.
- Conditional: `--enforce-eager` (on by default), `--quantization`, `--kv-cache-dtype`, `--cpu-offload-gb`.
- Not passed at all: `--enable-auto-tool-choice`, `--tool-call-parser`, `--reasoning-parser`, `--max-num-batched-tokens`, `--trust-remote-code`. So `tools` with `tool_choice: auto` will fail on vLLM.
- Environment: FlashInfer sampler is off because the image has no CUDA toolkit. Compile caches are container-local (`:189`), so CUDA graphs and torch.compile are rebuilt on every container start.

**llama-server flags** (`llamaServer.mjs:161-201`): `-m`, `--host`, `--port`, `--api-key`, `--no-webui -lv 4`, `--alias`, `--ctx-size` (16k), `--n-gpu-layers` 99, `--n-cpu-moe` only if &gt;0, `--flash-attn` auto, `--cache-type-k/v` (f16 default; q8_0 and q4_0 also allowed), `--threads`, `-np` 1, `--kv-unified` when np&gt;1, batch 2048 / ubatch 512, `--load-mode` (mmap stays on unless `noMmap` is set), `--chat-template-kwargs`, and `--jinja` only when the model sets `requiresJinja`.

**1c. "One deployment at a time" is built in deeply, but only in the controller, state and UI, not in the adapters.** Running 2–3 concurrent deployments would take:
- **State and controller:** the single `state.deployment` (31 references), plus the single `job`, `runner`, `runnerLogStart`, `lastCompletion` and `memoryStop` (`deployments.mjs:110-129`), become per-deployment maps. The busy/replace check (`:813-820`), `inUse` and drain handle several.
- **Ports and scratch dirs:** ports are fixed per runner (`ports[runnerId]`, `:617`, `index.mjs:33`), so two llama.cpp instances collide; ports must be allocated per deployment. vLLM and TabbyAPI use fixed `/dev/shm` directories (`vllm.mjs:29`, `tabbyApi.mjs:29`) that also collide.
- **Routing:** `chatTarget()` must take a model id. `buildRunnerRequest` must stop overwriting `model` (`chatResponder.mjs:100`). The manifest needs an `endpoints.models` command; AgentServer supports this (`resolveOpenAiModelsKind`), whereas the fallback only lists `default`. Whether Soul Gateway exposes several ids per agent still needs checking.
- **Admission:** it has to check the sum of all running deployments' estimates against the shared pool.
- **Surface:** the tools, the per-deployment log, and the dashboard's single deployment card.
- **Size:** roughly 1.5–2.5k changed lines, most of them in `deployments.mjs` and the dashboard.

**1d. `chatResponder.mjs`.**
- **Passed through** (`:12-16`): `tools`, `tool_choice`, `stream`, `stream_options`, `response_format`, `reasoning_effort`, `chat_template_kwargs`, `logprobs`, `top_logprobs`.
- **Dropped:** `parallel_tool_calls`, the `reasoning` object, `top_k`, `min_p`, `repetition_penalty`, `logit_bias`, `user`, and vLLM extras.
- **Limits:** `MAX_COMPLETION_TOKENS` 8192 and `RUNNER_TIMEOUT_MS` 570 s are hard-coded (`:76-77`). A big dense model at about 5 tok/s cannot produce 8192 tokens within 570 s.

**1e. Weight formats.**
- NVFP4 (ModelOpt) and MXFP4 Hugging Face snapshots fit the `hf` format when their files are top-level `.safetensors`/`.json`; the `quantization` pattern accepts `modelopt_fp4` and `mxfp4`.
- TensorRT-LLM checkpoints fit the same way through its PyTorch backend, which reads HF checkpoints. Prebuilt `.engine` files don't fit the snapshot file pattern, and since engines are specific to the GPU they should be built locally anyway.
- Split GGUFs need a new source type.

**1f. Runner adapter contract.** This is what a TensorRT-LLM, SGLang or llama.cpp-sm121 adapter would implement.
- **Required fields and functions:**
  - `id`, `displayName`, `weightFormat` (one of the catalog's `WEIGHT_FORMATS` keys), `pinnedVersion`, `supported`, `executable`.
  - `port` (a unique integer), `apiKey` (boolean), `paramSchema`.
  - `normalizeParams(params, {model})` and `detect({spawnSync, installer})` returning `{installed, version, reason}`.
  - `start(ctx)`, which returns details.
  - `chatModel(deployment)`.
  - `admit({model, source, params, gpu, memory, disk, remainingDownloadBytes})`, returning `{status, reason, estimate, warnings}`.
- **Optional:** `basicParams`, `moeParams`, `describeContext`, `buildLaunch` (by convention), `parseReport`, `requestOptions`, `enabled(env)`, `watchdog {check, intervalMs}`, `afterExit`, `unsupportedReason`.
- **What `start` receives** (`deployments.mjs:615-648`):
  - Context: `runner`, `model`, `params`, `artifact`, `weights`, `runnerDir`, `admission`, `shmDir`, `port`, `apiKey`, `dataDir`, `signal`, `fetch`, `store`.
  - Callbacks: `launch({command, args, env, cwd?, outputFilter?})`, `exec`, `waitForHttp`, `setPhase`, `progress`, `record`, `recheckAdmission`, `throwIfAborted`.
- A runner is "installable" when its id is in the lock; `runPipeline` then calls `ensureRunnable` before `start`.

**1g. Lock plus `uv`, or a container image?** The lock format is architecture-neutral. vLLM 0.30.0 in the current lock is already CUDA 13 (torch 2.13, cu13 NVIDIA wheels), but all 197 of its files are x86_64. aarch64 vLLM works if PyPI or download.pytorch.org carry aarch64 cu130 wheels with sm_121 kernels, which needs checking. TensorRT-LLM and SGLang-on-Spark are practically container-distributed and don't match Python 3.13. My recommendation is to bake vLLM and llama.cpp into the arm64 image and use NGC images for TensorRT-LLM, which needs Ploinky sidecar support.

### 2. Arch and CUDA assumptions in the image (`container-image-builds`)

**`images/local-llm/Dockerfile`:**
- **ik_llama.cpp builder:** `nvidia/cuda` 12.8.2-devel on amd64 (`:1`). Built for `IK_CUDA_ARCHITECTURES=86-real;89-real` (`:14`), which is SASS only with no PTX, so it can't run on sm_121. Compiled with `-DGGML_AVX/AVX2/FMA/F16C` (`:27`), which are x86-only.
- **amd64 guard:** `test "${TARGETARCH:-amd64}" = amd64` (`:54`).
- **x64 assets:** `llama-b11159-bin-ubuntu-cuda-12.8-x64` plus `cudart` (`:62-67`), `ollama-linux-amd64` (`:68`), and `source.contract` records `cuda=12.8` (`:82`).
- **uv:** `uv-x86_64-unknown-linux-gnu` 0.12.18 (`:95-100`); `libpython3.13-dev` (`:93`).
- **Runtime paths:** assumes driver libs at `PATH`/`LD_LIBRARY_PATH` `/usr/local/nvidia` (`:150-151`). Whether the Ploinky GPU grant binds aarch64 driver libs there is unverified.
- **Base image:** multi-arch (amd64 + arm64), so it is not a blocker.

**`sources.lock.json`:** `"architecture": "amd64"`.

**`runners.lock.json`:**
- vLLM: cp313, manylinux x86_64.
- TabbyAPI: torch 2.9.0+cu128, `exllamav3 …+cu128 linux_x86_64`.
- LM Studio: `linux-x64.full+cuda12`.

**`.github/workflows/publish-local-llm-image.yml`:**
- Builds on `ubuntu-24.04` (x86, `:24`) with `platforms: linux/amd64` (`:68`) and checks `Architecture = amd64` (`:86`).
- Its `ldd` proof expects `libcudart.so.12` (`:120`) and Ollama `cuda_v12`/`cuda_v13` (`:111`).
- The install check runs on x86 with no GPU (`:170`).

`tests/image-definitions.test.mjs:298` asserts "amd64 only".

### 3. Fork vs shared core vs profile

- **Size of what would be duplicated:** about 3.9k lines of generic code (control socket, controller helpers, catalog, downloader, stores, lock, installer, process, params, tools), plus `deployments.mjs` (1,194), about 1.6k lines of dashboard JS and 6.7k lines of tests. That is roughly 13k lines, of which about 0.5k (`hardware.mjs` + `admission.mjs`) and some adapter defaults actually differ.
- **Seams that already exist:**
  - `createController` takes `runners`, `snapshot`, `readMemory`, `ports`, `installer`, `detectRunner`, `seedCatalog` and `shmDir` as parameters (`deployments.mjs:66-107`); `main.mjs:80` passes only `dataDir`.
  - Admission is policy per adapter (`runner.admit`).
  - `createLlamaServerRunner` is a factory, so an sm_121 llama.cpp is about 30 lines.
- **Where there is no seam:** module-level constants in `admission.mjs`, `NVIDIA_LIB_DIR` and executable paths per adapter, the `chatResponder` limits, the hard-wired `admit: admitLlamaServer`, and LM Studio's `threadsFor` (not injectable).

### 4. Test baseline (Node v24.21.0, aarch64)

255 tests, **253 pass, 2 fail**, 3.1 s. Both failures (`tests/lmstudio.test.mjs:335` and `:494`) say `--threads is 12, expected 18`. The test fixture hard-codes 12 threads, which assumes a 14-core development box, while `lmStudio.mjs:76-77` reads the real core count (20 here, so 18). This comes from the host's core count, not from ARM itself; LM Studio's adapter lacks the `cpuCores` injection the llama-server factory has. No other failures, so the suite is effectively arch-clean because nothing in it touches real hardware.

### Recommendation

I recommend adding a hardware profile inside a shared core rather than forking.

1. **Profile first:** add a "UMA" profile to local-llm, selected when `os.arch()==='arm64'` or when `memory.total` reads `[N/A]`. Plug it in through the existing `createController` parameters, a profile-specific runner table and a DGX seed catalog. Ship it as a separate arm64 image (`dgx-local-agent`) that points at the same source.
2. **Shared core later:** extract a package only once multi-deployment lands, because that change touches the controller, state, tools and UI either way.

A fork would copy about 13k lines to change about 1k.

**What must change for UMA:**
- **`hardware.mjs` `readGpu`/`readSnapshot`:** detect UMA (`[N/A]`, name `GB10`, `compute_cap` 12.1). Report `gpu.memoryModel:'unified'` with the pool taken from `/proc/meminfo` MemTotal/MemAvailable (119.6 GiB visible here). Never produce NaN; treat non-finite values as unknown. `defaultThreads` should prefer the X925 cores.
- **`admission.mjs`:** add a unified-pool policy where need = all weights + KV + compute + context + runner RAM, checked against the pool minus a host reserve (e.g. max(8 GiB, 10%)). Retire `GPU_MARGIN_BYTES`, `RAM_MARGIN_BYTES`, the 0.97 ceiling, `VLLM_USABLE_SHARE`, `VLLM_MAX_UTILIZATION`, the `VLLM_OFFLOAD_*` constants, `fromFree`, `llamaWeightSplit`'s capacity role, and the `ramWarning` split. The same fix is needed in `admitOllama` and `admitTabbyApi`. Also sum across running deployments.
- **`deployments.mjs` `startMemoryGuard`:** always run it on UMA, with a floor.
- **`vllm.mjs`:**
  - Remove `cpuOffloadGb`; set `--gpu-memory-utilization` from need/total.
  - Default `enforceEager` to false.
  - Add tool and reasoning parser parameters and `maxNumSeqs` &gt; 1.
  - Possibly `TRITON_PTXAS_PATH` if Triton's bundled `ptxas` rejects sm_121 (worth verifying).
- **`llamaServer.mjs`:** accept an `admit` override; default `nCpuMoe` to 0 (hide it); reconsider mmap vs `--no-mmap` (page cache and CUDA buffers share one pool); raise the 131072 `ctxSize` maximum.
- **`llamaCpp.mjs`:** executable and `pinnedVersion` for an arm64 CUDA 13 sm_121 source build. Drop `ikLlamaCpp`, `tabbyApi` and the LM Studio adapters from the profile.
- **`ollama.mjs`:** arm64 binary; make `OLLAMA_MAX_LOADED_MODELS` configurable.
- **`chatResponder.mjs`:** make `MAX_COMPLETION_TOKENS` and `RUNNER_TIMEOUT_MS` configurable; widen `FORWARDED_FIELDS`.
- **`catalog.mjs`:** add a multi-file GGUF source; ship a DGX `models.json`.
- **`runnerLock.mjs`:** add allowed hosts and a per-file platform field. **`runnerInstaller.mjs`:** optionally a pinned Python.
- **Image and CI:** an arm64 Dockerfile and workflow on a native arm64 runner, with an `ldd` proof for CUDA 13.
- **Dashboard:** show one "Unified memory" card instead of separate GPU and RAM cards.
