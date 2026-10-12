Reviewer: codex-gpt-6
Date: 2026-09-28
Plan: /home/research/work/plans/local-llm-multiarch-plan.md, sha256 a8f8085be85a747eac8292cd8f49a978f4028cafb7abb3b3ae7044700dac2d10, modified 2026-09-28 13:43:48.575710739 +0200

## 1. Verdict

The one-agent, multi-architecture design is sound enough to begin A1 and a bounded Phase 0, with the corrections below. There is no evidence that a second agent or a new Box image is necessary. The existing amd64 manifest is reusable, arm64 runner artifacts exist, and the host discovery failure is exactly the architecture filter described in the plan. However, the plan is not ready to serve as a release checklist: it omits runner-availability work from its phases, exposes vLLM before its stated acceptance phase, under-specifies protection of the shared memory pool, and overlooks source-archive build identity and existing publication checks. Start with the parser fix and small, controlled measurements; make successful nested GPU execution, memory-pressure characterization, and tests of the shared code on an x86 GPU explicit prerequisites for publishing the first usable index. Legacy deletion can be prepared independently but is not needed to unblock inference.

## 2. Fact check

Evidence paths below use these abbreviations, all referring to the installed sources reviewed:

- **P** = `/home/research/work/ploinky`, HEAD `ed86558bca7777913395d576feb8bc856d350096`.
- **L** = `/home/research/work/.ploinky/repos/local-llms`, HEAD `03697765a35d92adf4c7db1be9616c0b5a64cb63`.
- **I** = `/home/research/work/.ploinky/repos/container-image-builds`, HEAD `95ba10a2be4eb1aeb0d9612186c746ae9d7b9efe`.
- **E** = `/home/research/work/.ploinky/repos/AchillesIDE`, HEAD `bddb644068d504c4c8b1b4d6e42d5cb423af5e26`.
- **G** = `/home/research/work/.ploinky/repos/proxies`, HEAD `83e897a06e1b5863ce418ffda39ab3acbbf66dd5`.

I read the applicable repository CLAUDE.md/AGENTS.md files and local-llm's DS000–DS004. I found no CLAUDE.md or AGENTS.md in I. The report is the only intentionally written persistent artifact. No image, model, package, or source archive was downloaded; upstream source text, JSON and wheel METADATA were read in memory. No container lifecycle operation was performed.

### Host, current failure, and Ploinky

| Claim | Verdict | Evidence |
| --- | --- | --- |
| DGX Spark, Lenovo OEM, Ubuntu 24.04, kernel 6.17, aarch64 | confirmed | `/etc/dgx-release`: `DGX_NAME="DGX Spark"`; `/sys/class/dmi/id/sys_vendor` and `product_name`: `LENOVO`, `30KL0004GF`; `/etc/os-release`: Ubuntu 24.04.4 LTS; `uname -a`: `6.17.0-1018-nvidia … aarch64`. |
| Current DGX OS version is simply 7.2.3 | refuted | `/etc/dgx-release` contains both `DGX_SWBUILD_VERSION="7.2.3"` and `DGX_OTA_VERSION="7.5.0"`, OTA date May 21, 2026. Report the base build and OTA version separately. |
| GB10, compute capability 12.1, driver 580.159.03, driver supports CUDA 13.0 | confirmed | `nvidia-smi --query-gpu=name,compute_cap,driver_version --format=csv`: `NVIDIA GB10, 12.1, 580.159.03`; full `nvidia-smi` header: `CUDA Version: 13.0`. |
| GPU memory fields are `[N/A]` | confirmed | Query of `memory.total,memory.used,memory.free` returned `[N/A], [N/A], [N/A]`. |
| Approximately 119.6 GiB RAM, no swap | confirmed | `/proc/meminfo`: `MemTotal: 125442396 kB`, or 119.63 GiB; `free -h`: `106Gi` available at inspection, Swap `0B`. |
| 20 cores, ten X925 and ten A725 | confirmed | `lscpu`: CPUs `0-19`, Cortex-X925 and Cortex-A725, ten cores in each reported group, one thread/core. |
| 1 TB NVMe, approximately 132 GB free | confirmed | `df -h /`: `/dev/nvme0n1p2 916G 738G 131G 85% /`. Distinguish the drive's decimal capacity from `df`'s units. |
| Single-host setup; all ConnectX-7 links down | confirmed | `ibdev2netdev`: four RoCE ports, all `Down`; `ip -br link`: corresponding Ethernet interfaces down. This verifies the local links, not the absence of every possible remote Spark. |
| Host CUDA toolkit 13.0, CMake 3.28 | confirmed | `nvcc --version`: `V13.0.88`; `cmake --version`: `3.28.3`. |
| CMake 3.28 can handle the chosen `121a-real`; the newer requirement concerns `120f` | confirmed | Pinned [ggml CUDA CMake file](https://github.com/ggml-org/llama.cpp/blob/b11159/ggml/src/ggml-cuda/CMakeLists.txt#L41), lines 41–54, distinguishes the family suffix and appends `121a-real` for CUDA ≥12.9. Actual build remains Phase 0. |
| Explorer enables the single agent with `no-wait` | confirmed | `E/explorer/manifest.json:28`: `local-llms/local-llm no-wait`. |
| The current image pulled 4.57 GB in 620 seconds and failed with Exec format error | confirmed | Matching workspace no-wait log, lines 21 and 23: `4.57 GB unpacked in 620s`; execution of `/usr/local/bin/node` failed with `Exec format error`. |
| GPU status fails because ldconfig accepts only x86-64 | confirmed | From workspace root, `/home/research/work/ploinky/bin/ploinky gpu status`: `Host GPU: unavailable (NVIDIA driver library libcuda.so.1 is not in the ldconfig cache)`. `P/ploinky-box/gpuGrant.mjs:239`; actual `ldconfig -p` uses `libc6,AArch64`. `ploinky` was absent from this shell's PATH, so I used the checkout's executable. |
| The rest of discovery can describe this host's devices and normal driver libraries | confirmed | Read-only in-memory reproduction passed the real ldconfig output through `replaceAll('AArch64','x86-64')` and called the unchanged `discoverNvidiaGpu`. It successfully returned all three required device nodes, five libraries, and nvidia-smi. No files or grants changed. Device numbers, CDI rendering, fingerprint and marker code (`gpuGrant.mjs:250`, `397`, `464`, `481`) contain no further x86/discrete-memory branch. This is not a runtime CUDA proof. |
| Optional nvvm70 requires a narrowly scoped version-name exception | confirmed | `readlink -f /lib/aarch64-linux-gnu/libnvidia-nvvm70.so.4` returns `/usr/lib/aarch64-linux-gnu/libnvidia-nvvm70.so.4`; ordinary libraries resolve to `.so.580.159.03`. `gpuGrant.mjs:337–347` currently checks that suffix for every optional library. `/dev/nvidia-uvm-tools` exists. |
| Admission approves oversized models with the GB10 snapshot | confirmed | Imported the actual `readGpu` with `/usr/bin/nvidia-smi`, then called the existing admission functions in memory: 500 GiB llama.cpp → `ok`; 300 GiB vLLM → `ok`, utilization `NaN`; 500 GiB Ollama → `ok`, RAM estimate `NaN`. Download bytes were zero and disk ample to isolate memory admission. `L/local-llm/src/controller/hardware.mjs:49–65`; `admission.mjs:126–193,223–295`. This does not mean unrelated source, disk or runner checks always pass. |
| GB10 utilization, power and temperature are available | confirmed | Query returned `0 %, 4.34 W, 43`; PCI device ID `0x2E1210DE`. These readings should remain optional telemetry, separate from required admission inputs. |

### Image mechanics and Box

Registry checks used the Docker Hub token endpoint with anonymous pull scope, followed by registry manifest GETs and, for the single image, its small config blob. No layers were fetched.

| Claim | Verdict | Evidence |
| --- | --- | --- |
| `ploinky-node@accd925f…` is an OCI index for both architectures | confirmed | Registry returned `application/vnd.oci.image.index.v1+json`, with amd64 child `sha256:14c2ae031b3e2f89128cd29314208e515703dae2cc66e31b5b0588acfaf43edc` and arm64 child `sha256:1f9f1234890381d7652d1a5f9873bddb312868442fc8de5f9d9fefc0dfaf8b48`. Read-only in-Box image inspection reports `arm64` for the pinned reference. |
| `local-llm@b6c79af2…` is a single amd64 manifest | confirmed | Registry media type `application/vnd.oci.image.manifest.v1+json`; config `architecture=amd64`, `os=linux`, revision `95ba10a2be4eb1aeb0d9612186c746ae9d7b9efe`. Compressed layers sum to 3,198,909,373 bytes, distinct from the logged unpacked size. |
| The existing manifest can be a member of a new index | confirmed | Docker's [imagetools create reference](https://docs.docker.com/reference/cli/docker/buildx/imagetools/create/) accepts existing single-platform manifests and indexes. Use the fully qualified immutable reference in the same repository. The current manifest has no index-level attestation members; `I/.github/workflows/publish-local-llm-image.yml:73` disables provenance. If arm64 enables attestations, verify runtime-platform members separately from attestation descriptors or preserve the current no-attestation policy. No publish or dry-run command was needed. |
| Ploinky pulls without a platform override and emits one only for an explicit runtime policy | confirmed | `P/cli/sandbox/docker/common.js:196`; `containerRuntimePolicy.js:261–263`. The existing agent declares no llmRuntime policy. |
| Native per-platform builds and index assembly already exist in ploinky-node CI | confirmed | `I/.github/workflows/publish-ploinky-node-image.yml:33–38,66–71,178–195`. Separate jobs permit different Dockerfiles. |
| The runtime base is multi-arch; the local image's guard/downloads lock it to amd64 | confirmed | `I/images/local-llm/Dockerfile:40,54,62–70,95–100`. Its ik builder is also pinned to an amd64 CUDA manifest; using a separate arm64 Dockerfile correctly avoids it. |
| Current ploinky-box is multi-arch and runs arm64 | confirmed | `latest` resolves to OCI index `sha256:ee99cd5e0dcd3d37b262bffe3a87865d4fdcce3cd31a62468dac1bb9e3a35140`, with amd64 and arm64 members. Running Box inspection reports that digest; in-Box `uname -m` returns `aarch64`, Podman version `5.8.2`. |
| No Box image rebuild is needed for A1 | confirmed | Running mount: `/home/research/work/ploinky -> /opt/ploinky RW=false`; source-generated GPU mounts/spec/marker are creation arguments (`P/ploinky-box/lifecycle/container.mjs:163,171,176`). `I/images/ploinky-box/Dockerfile` already handles arm64 and contains no NVIDIA installation step. **Applying wiring still requires a Box replacement through the normal lifecycle**; the read-only source mount does not update an existing container's devices/mounts. |
| Nested arm64 Podman actually consumes the GPU CDI device correctly | unverifiable | Running Box has `GPU wiring none` and no mounted CDI file. Static hookless CDI schema is architecture-independent; Podman is present. An authorized A1 rollout and nested CUDA test in Phase 0 must settle runtime behavior. This review did not recreate containers. |
| IPC, shared memory, PID and memory restrictions match the plan | confirmed | Runtime policy limits shm to 16g; current manifest requests 8g. Outer inspection: PidsLimit `2048`, Memory `0`; nested Explorer inspection: Cgroups `disabled`, Memory `0`, PidsLimit `0`. Outer creation currently has no explicit PID override (`P/ploinky-box/lifecycle/container.mjs:155–194`). Box admission rejects host IPC and arbitrary device/security flags. |
| Dependency cache needs no new architecture-selection feature | confirmed | Probe reads the selected image's actual `process.arch`, libc and Node version (`P/cli/utils/dependencies/dependencyRuntimeKey.js:102–123,175–189`). Cache metadata includes architecture and image (`dependencyCache.js:839–848`). The pin change can invalidate the cache even on x86 because image-reference equality is checked at `275–288`; unchanged layers do not imply no restart/install work. |

### Runners and consumers

| Claim | Verdict | Evidence |
| --- | --- | --- |
| b11159 publishes CUDA 13.4 arm64 binaries and runtime libraries | confirmed | [Release metadata](https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/b11159): server archive 145,505,332 bytes, SHA256 `258c9dc7c6c02fd2d805ebf9511876ab7b9d7b2d3f0c2166454d682ccae7644b`; cudart archive 552,521,395 bytes, SHA256 `34d8602d0084b2498dbf0c436fe2d1d4e54ba577b8d5567eb56990e8fff11bfa`. Tag resolves to commit `6b790a9c291b5d7af3312bbf9f0c558aa023b13e`. |
| Release CI uses CUDA 13.4.1, no explicit CUDA architecture, GCC 14 and dynamic CPU variants | confirmed | Pinned [release workflow](https://github.com/ggml-org/llama.cpp/blob/b11159/.github/workflows/release.yml#L336), lines 336–411; CUDA defaults include `121a-real`. Pinned CPU CMake selects feature-specific variants. |
| Native Spark and GPU-less CI builds will perform equivalently | unverifiable | Explicit `121a-real` removes the need for a physical GPU during compilation; it does not prove end-to-end performance equality across compiler/toolkit patches, CPU variants and library sets. The plan's same-model A/B test is the right gate. Record exact commits, compiler versions, selected CPU backend, load mode and runtime libraries. |
| A CUDA 13.0 arm64 Ubuntu 24.04 builder exists | confirmed | Registry `nvidia/cuda:13.0.2-devel-ubuntu24.04`: index `sha256:5dc1bca23d05bd37b011be68ec470c03b403a5da07ec3a86e41af9470e9d0cc6`; arm64 member `sha256:450d11555d20ac8ebbbc13ebf17589c2bd42869171a90179ce7098b4a5e64c6a`. Pin the chosen builder, not `13.0.x` as a moving placeholder. |
| CUDA 13.4 categorically needs a newer driver or forward-compatibility package | refuted | NVIDIA's [minor-version compatibility documentation](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html) explicitly lists CUDA 13.x with driver ≥580, subject to feature/PTX restrictions. A forward-compatibility package is not categorically required. |
| The exact CUDA 13.4 llama.cpp release is safe and equivalent on this 580 driver | unverifiable | Native GB10 code makes the fallback plausible, but new driver-dependent features and dependency behavior remain runtime questions. Require successful loading, prefill, decode and representative quantizations on this driver, not merely `--version`. |
| NVIDIA's playbook uses native CPU tuning, CUDA and `121a-real`, and demonstrates MTP | confirmed | [Playbook](https://github.com/NVIDIA/dgx-spark-playbooks/blob/31895571899a5213735fe1a76c08ce9159f6bf1a/nvidia/llama-cpp/README.md#L83), build at 88 and MTP example at 111–120. The plan must adapt its commands to the pinned source instead of copying obsolete options; see findings. |
| Ollama v0.34.4 supplies the approximately 1.5 GB arm64 archive | confirmed | [Release metadata](https://api.github.com/repos/ollama/ollama/releases/tags/v0.34.4): `ollama-linux-arm64.tar.zst`, 1,549,684,612 bytes, SHA256 `96f50a1192133028cf4e010d8c333f8af14b1505db6be7b2034c11487e7fd7e6`. Pinned [Dockerfile](https://github.com/ollama/ollama/blob/v0.34.4/Dockerfile#L285) includes CUDA 12/13 payloads; [CUDA 13 Linux preset](https://github.com/ollama/ollama/blob/v0.34.4/llama/server/CMakePresets.json#L99) includes `121-virtual`. |
| Ollama works in this Box on GB10 | unverifiable | NVIDIA has an [Ollama playbook](https://github.com/NVIDIA/dgx-spark-playbooks/blob/main/nvidia/ollama/README.md), and the pinned release contains relevant support. Its actual backend selection, GPU use, tool calls and memory behavior here need Phase 0. |
| vLLM 0.30.0 and its Python 3.13 arm64 dependency closure have wheels | confirmed | Queried PyPI JSON and PEP 658 METADATA for arm64-compatible replacements for **all 196 wheel versions** in the existing vLLM lock. All 196 have compatible wheels; traversing vLLM requirements and extras under Linux/aarch64/Python 3.13 found 196 reachable packages, no absent requirement and no pinned-version conflict. Selected compressed wheels total about **3.67 GiB**. No wheel payload was downloaded. |
| Important vLLM dependencies work as binary packages on cp313 arm64 | confirmed | Metadata includes `torch-2.13.0-cp313-cp313-manylinux_2_28_aarch64`, vLLM's cp38-abi3 arm64 wheel, Triton 3.7.1 cp313 arm64, FlashInfer 0.6.18.post1 universal wheel, CUTLASS DSL 4.7.1 universal package and its base/cu12/cu13 cp313 arm64 libraries. CUDA toolkit 13.0.3.0 is universal; selected CUDA component wheels support arm64. PyNvVideoCodec 2.0.4 requires manylinux_2_34, compatible with trixie. Recheck actual installation/imports in CI. |
| A complete wheel closure means no runtime compilation or sm_121 risk | refuted | Binary availability removes a demonstrated installation-source-build obstacle; it does not validate CUDA JIT, FlashInfer kernels, NVFP4 or Triton's assembler. The adapter already disables the FlashInfer sampler because of runtime compilation (`L/local-llm/src/runners/vllm.mjs:158–159`). Exact workload/kernel support remains a Phase 0/4 gate. |
| Pinned Triton requires a `libcuda.so` alias because it links `-lcuda` | refuted | Triton 3.7.1 [driver.py:16](https://github.com/triton-lang/triton/blob/v3.7.1/third_party/nvidia/backend/driver.py#L16) uses `libraries = ['libcuda.so.1']`; [build.py:52–56](https://github.com/triton-lang/triton/blob/v3.7.1/python/triton/runtime/build.py#L52) emits `-l:libcuda.so.1`. A different dependency may need an unversioned alias, but that is not established by this claim. |
| ik_llama.cpp, TabbyAPI and LM Studio are absent from the proposed arm64 image | confirmed | This is consistent with the current **local integration**: ik's builder targets x86 sm_86/sm_89; the Tabby lock contains x86 artifacts; `lmStudio.mjs:37` hardcodes an x86 CUDA12 engine. I did not establish the broader claim that every upstream project has no arm64 possibility. Excluding them is reasonable scope. |
| Gateway discovery and the default model name need no architecture change | confirmed | `G/soul-gateway/src/ploinky/discovery-client.mjs:49`; `reconcile-agents.mjs:113`; `L/local-llm/docs/specs/DS001-agent-contract.md`, Chat endpoint. Existing gateway tests cover multiple discovered models. |
| Gateway limits reasoning/sampling passthrough and defaults to 120 seconds | confirmed | `G/soul-gateway/src/runtime/backends/builtin/ploinky-agent-openai.backend.mjs:144–166` has the request allowlist; stream handling at `597–602` processes content and tools, not reasoning_content. `runtime/execution/timeout-middleware.mjs:147–148` supplies 120,000 ms by default. This matters to C7; see finding 7. |
| Eleven legacy agents will be removed | refuted | The plan itself lists twelve directories: manager plus eleven model agents. L/AGENTS.md and the legacy HTML agent table agree on twelve. The explicit deletion list is complete despite the wrong count. |
| No other checked repository depends on the legacy agents/image | confirmed | Read-only `rg --hidden` searches across installed repositories, P and AdvancedLanguageAgent found legacy image/qualified-agent references confined to L; remaining external local-llm references concern the retained agent or generic fixtures. This does not establish that external users have no persisted enable/profile references. |

### Tests run

| Command | Result |
| --- | --- |
| In L: `node --test 'local-llm/tests/*.test.mjs'` | **255 tests: 253 passed, 2 failed.** Both failures are the expected LM Studio fixtures at `lmstudio.test.mjs:335` and `:494`: `--threads is 12, expected 18`. No tests skipped. |
| In P: `node --test tests/unit/ploinkyBoxGpuGrant.test.mjs tests/unit/dependencyRuntimeKey.test.mjs tests/unit/dependencyCache.test.mjs tests/unit/containerRuntimePolicy.test.mjs` | **69 passed; 2 test-file failures.** GPU-grant and runtime-policy cases passed. Both dependency files failed during module initialization because `PLOINKY_AGENTLIB_DIR` was unset (`PLOINKY_AGENTLIB_CONTRACT_MISSING`). A focused rerun confirmed that cause. No dependency package installation or environment fabrication was attempted. |
| In I: `node --test --test-name-pattern=local-llm tests/image-definitions.test.mjs` | **7 passed, 0 failed.** These verify the present amd64 contract; they do not prove the proposed arm64 image. |

## 3. Findings

### 1. Major — The memory-safety gate measures too little to validate the proposed admission policy

**Where:** C1–C3, C5; Phase 0; `L/local-llm/src/controller/deployments.mjs:530–559`; DS003:50.

The proposal compares estimated resident demand with MemAvailable and asks Phase 0 to measure memory before/after loading. That leaves the most dangerous interval insufficiently specified: downloading and hashing weights can populate the page cache, and loading, prefill, graph construction and MTP can have temporary peaks much larger than the final resident allocation. NVIDIA's playbook explicitly acknowledges UMA/page-cache pressure. A successful steady-state sample does not establish that CUDA can reclaim the memory Linux counts as available.

The existing guard waits for its first scheduled sample, samples every two seconds during loading and ten seconds when ready, ignores missing/non-finite observations, and allows up to three more seconds before SIGKILL. The Box and its nested agents have no memory limit and this host has no swap. Simply enabling that guard for all unified runs is a useful backstop, not a demonstrated host-protection guarantee.

**Fix:** Make the release gate measure peak memory through first download/hash/load, warm-cache reload, full configured prefill, concurrent slots, and MTP on/off. Record MemFree, MemAvailable, cache and runner/CUDA allocation observations with adequate sampling. Calibrate a conservative reserve and guard interval from those peaks, explicitly bound behavior when telemetry fails, and begin with small models. Do not make privileged global `drop_caches` an agent feature or a prerequisite for normal use. Keep large/unmeasured configurations refused until the gate supports them. No new cgroup feature is required to start this work, but the plan must state the residual limitation when other agents can consume the shared pool.

### 2. Major — C4 is missing from the phase table, and vLLM becomes installable before its acceptance phase

**Where:** B3, C4, Phase 2–4; `L/local-llm/src/runners/vllm.mjs:97–103,233`; `llamaServer.mjs:221`; DS004:66–68.

Phase 2 explicitly lists C1–C3 and C5–C10, omitting C4. Yet B3 puts a vLLM entry into the arm64 lock in Phase 3, while Phase 4 still owns unified vLLM utilization, eager/graph behavior and model parsers. An entry with an adapter is installable under the present contract, and all existing adapters statically say `supported: true`. Missing binaries/lock entries currently mean “not installed,” not a platform support policy. The phase ordering can therefore expose unvalidated vLLM and misleading availability for omitted runners at first rollout.

**Fix:** Include C4 in Phase 2 and make it a Phase 3 gate. Either omit vLLM from the first arm64 lock until Phase 4 or explicitly disable its Install/Run paths pending that gate. Keep unsupported reasons visible in overview and reject direct admin requests before downloads. Test omitted ik/Tabby/LM Studio, LM Studio's operator switch on an unsupported platform, and supported-but-not-yet-installed vLLM separately. The amd64 lock and behavior remain unchanged.

### 3. Major — The source-archive build loses the version identity the publication proof requires

**Where:** B2 source archive and B4 version proof; `L/local-llm/src/runners/llamaCpp.mjs:14–25`; upstream build-info files.

The source archive proposal does not carry `.git`. At b11159, [cmake/build-info.cmake:1–39](https://github.com/ggml-org/llama.cpp/blob/b11159/cmake/build-info.cmake#L1) defaults to build `0`, commit `unknown`, and derives replacements from Git. [CMakeLists.txt:153–158](https://github.com/ggml-org/llama.cpp/blob/b11159/CMakeLists.txt#L153) only preserves explicitly supplied `LLAMA_BUILD_NUMBER`/`LLAMA_BUILD_COMMIT`. The adapter expects b11159 and would report a mismatch (it still returns `installed: true`, `src/runners/params.mjs:212–213`); the existing image proof would fail its `build 11159,` check. A hash-verified archive alone does not preserve that identity.

**Fix:** Pin both the archive hash and full commit `6b790a9c291b5d7af3312bbf9f0c558aa023b13e`, and configure `-DLLAMA_BUILD_NUMBER=11159 -DLLAMA_BUILD_COMMIT=6b790a9c` (or the verified full commit). Prove the binary's reported identity as well as `source.contract`; do not merely silence the mismatch warning or remove the publication assertion. Record builder digest, compiler and CUDA patch versions. This is a concrete addition to the source-build recipe, not a reason to abandon it.

### 4. Major — Reused amd64 publication needs an explicit proof path

**Where:** B1/B4; `I/.github/workflows/publish-local-llm-image.yml:88,107–142,177,215–227`; image-definition tests around 298–438.

A platform matrix alone cannot satisfy the existing workflow. It requires each image's revision label to equal the new workflow's `GITHUB_SHA`; the reused amd64 digest is permanently labeled `95ba10a…`. Its proof also unconditionally expects ik, CUDA12 library paths and the LM Studio SDK, while the arm64 design omits them. Install-check selects entries and proprietary status from the amd64 lock and fetches the old agent commit `171b2eba…`. These details need changes beyond removing the “amd64 only” assertion.

**Fix:** Describe an amd64 **reuse-and-prove** job with the known immutable digest and original source revision, and an arm64 build-and-prove job with the new source revision. Parameterize lock selection and expected payloads; keep the common uid, no-weights, no-proprietary-files and exact-lock-byte checks. Pin the install-check code to a pushed candidate containing the required shared-code changes. Make index assembly depend on both image proofs and the applicable install checks, then assert exact child digests. Preserve proprietary validate-only behavior on amd64.

Also prove the copied source build's dynamic CPU/CUDA backends and their runtime library resolution from the final image. B2 keeps LD_LIBRARY_PATH restricted to granted driver libraries; merely copying cuBLAS/cudart beside binaries is insufficient unless RUNPATH/backend discovery reaches them. Add deliberate final-image `$ORIGIN`/backend placement and closure checks rather than relying on the builder's absolute paths.

### 5. Major — Longer chat deadlines do not pass the existing outer deadline

**Where:** C7, Phase 5; `L/local-llm/manifest.json:37`; `G/soul-gateway/src/runtime/execution/timeout-middleware.mjs:147–148`.

C7 makes `RUNNER_TIMEOUT_MS` configurable and raises completion limits, but the responder command still has a 600,000 ms manifest timeout and the supported consumer route defaults to 120,000 ms. Increasing the inner timeout alone cannot make long requests usable through Soul Gateway. At the published roughly 43 tokens/s for gpt-oss-120b at 32K depth, 32,000 generated tokens would take about 744 seconds before other overhead; those historical numbers are illustrative, not this host's performance measurement.

**Fix:** Either keep C7's effective limits inside the current outer budgets and defer the feature, or move the minimal gateway/endpoint deadline configuration and a through-Gateway acceptance test into the phase that introduces long completions. Validate deadline ordering, cancellation/disconnect propagation and streamed terminal usage. Broad reasoning-passthrough work can remain later if the initial product limitation is explicit.

### 6. Minor — `--no-mmap` is obsolete at the pinned build, and does not mean DirectIO

**Where:** C5 and Phase 0; `L/local-llm/src/runners/llamaCpp.mjs:3–11`.

b11159 accepts `--load-mode` with `none`, `mmap`, `mlock`, `mmap+mlock` and `dio` ([arg.cpp:2686–2702](https://github.com/ggml-org/llama.cpp/blob/b11159/common/arg.cpp#L2686)). The current adapter already translates `noMmap: true` to `--load-mode none`. Literal `--no-mmap` in the proposed command is wrong. Moreover, `none` is buffered loading; it does not ensure that model data avoids the page cache. Most of the cited [Spark benchmark table](https://github.com/ggml-org/llama.cpp/blob/b11159/benches/dgx-spark/dgx-spark.md#L106) explicitly records `mmap=0, dio=1`.

**Fix:** Specify the adapter parameter and emitted b11159 flag separately. Compare `none` and `dio` using the actual `/data` filesystem and after a controller download/hash. Use the measured winner as the unified default, with explicit fallback handling if DirectIO is unavailable. Do not infer load-mode safety from disabling mmap alone.

### 7. Minor — Memory topology and kernel compatibility need separate, explicit handling

**Where:** C1/C4; B2 `121a-real` specialization.

`[N/A] + compute capability 12.x` recognizes this particular driver/device combination, not the definition of unified memory. A driver that begins returning numeric GB10 memory would select the dedicated path; another device returning unavailable memory is not necessarily a Spark. Conversely, an arm64 GH200 with numeric HBM would select dedicated policy but still receive the proposed llama.cpp binary containing only `121a-real` kernels. That does not make a second agent necessary, but it requires a truthful unsupported result.

**Fix:** Identify the tested GB10 profile using stable GPU identity/capabilities, treating `[N/A]` as a supporting observation. Keep an explicit unknown state and refuse unknown required memory/capability inputs. Describe which GPUs each image's runner supports and reject unsupported kernels before downloading weights. Add numeric-GB10, missing-nvidia-smi, partial telemetry, dedicated-arm64 and unknown-UMA fixtures. Do not automatically refuse inference just because optional temperature or per-process utilization is unavailable.

### 8. Minor — “context × slots” disagrees with the existing llama.cpp context contract

**Where:** C2; `L/local-llm/src/runners/llamaServer.mjs:142–147`; `admission.mjs:70–72`.

The current adapter exposes `ctxSize` as total KV capacity and adds `--kv-unified` for multiple slots. Its current KV estimate multiplies bytes/token by ctxSize once. Applying the plan's generic context × slots expression to these same parameters double-counts that pool. vLLM also has a shared paged KV pool, while Ollama's context semantics differ.

**Fix:** Specify the meaning of context and total KV capacity per runner, and calculate memory from the actual pool allocation. Include fixed/recurrent buffers, model-specific cache precision and MTP allocations as separate terms. Test parallel 1 versus multiple slots without silently redefining existing x86 parameters. Change the displayed per-request/total limits only with an explicit contract update.

### 9. Minor — The Triton alias premise is wrong, and image ENV is not the runner ENV

**Where:** B2 libcuda link; `L/local-llm/src/controller/deployments.mjs:448–455`; `src/runners/vllm.mjs:143–146`.

The pinned Triton already links the granted versioned soname. Additionally, the controller intentionally drops inherited environment variables and vLLM explicitly points `TRITON_LIBCUDA_PATH` to `/usr/local/nvidia/lib64`. Adding only image ENV would not select a new alias directory. The Python version/path, installer uv path and allowed-host list have no inherent arm64 obstacle: `/usr/bin/python3`, `/usr/local/bin/uv`, and files.pythonhosted.org already cover this closure.

**Fix:** Remove the assertion that Triton 3.7.1 requires this alias. If a Phase 0 failure identifies another exact dependency that links `-lcuda`, add a narrow adapter environment change and image-owned alias for that dependency, verified by an actual JIT call. Preserve the minimal environment; do not solve this by forwarding `process.env`. Treat FlashInfer/CUTLASS/compiler search paths as measured runtime requirements, not inferred from an install succeeding.

### 10. Minor — Full Phase 0 has no credible peak disk budget or bounded model set

**Where:** Phase 0 “about 40 GB”; C6 catalog.

The cited benchmark's gpt-oss-120b GGUF is 59.02 GiB by itself. The vLLM arm64 wheels add about 3.67 GiB compressed, and DS004 temporarily holds cache, verified staging and the expanded runnable environment. Builds, image layers and Ollama's separate weight store add more. A 40 GB total cannot cover the full catalog/per-model validation as written; 131 GiB currently free is not the same as a safe experiment budget.

**Fix:** Split Phase 0 into a small-model feasibility gate and sequential large-model validation. List exact artifacts, existing reusable weights, peak disk requirements and a free-space floor before each stage. Do not imply that all seed models or formats can be held simultaneously. Carry the disk constraint into first-install and split-GGUF tests.

### 11. Minor — Split-GGUF and cleanup omit the lifecycle specification and migration detail

**Where:** C6/C10 and D; `L/local-llm/docs/specs/DS002-model-lifecycle.md:24–38,52–58`.

C10 lists DS000, DS001, DS003 and DS004 but omits DS002, which explicitly specifies a single GGUF file, artifact identity, resume/verification and deletion. A split source changes that contract. It also must remain a GGUF **weight format** shared across applicable runners: adding an unrelated format key would not match the adapters' fixed `weightFormat: 'gguf'`. Deleting repository DS008/DS010 leaves references in retained agent specs unless they are migrated. Legacy translation and relevance provide seq2seq/reranking APIs that the retained chat runner does not replace.

**Fix:** Include DS002, its HTML documentation and both specification indexes in the work list. Specify all-shards-pinned completeness, canonical shard paths/order, immutable download identity, aggregate disk/progress accounting, shared-artifact deletion, user-model input and old-state compatibility. Correct the count to twelve legacy agents. Document removed capabilities and a retirement/migration path for persisted enables/profiles without deleting existing model data; keep the old implementation recoverable by commit. No checked in-tree consumer requires those APIs, but “no dependency found here” is not a migration policy for external users.

## 4. Missing work

| Workstream / phase | Add to the plan |
| --- | --- |
| **A / Phase 1, before nested Phase 0** | Test arch mapping with explicit x64/arm64 fixtures, whitespace in ldconfig flags, mixed architectures, missing libraries, version mismatches and unknown architectures. Exercise CDI/spec/marker/fingerprint round-trips for arm64 without widening devices, mounts or privileges. The optional nvvm70 exception must be soname-specific. |
| **A / Phase 1** | Specify rollout: source updates are immediately visible, but new GPU wiring and a raised PID limit require normal Box replacement. Record expected interruption and verify unchanged network/security boundaries in the implementation's authorized fixture. This review did not perform that rollout. |
| **A / Phase 1, only if needed** | Measure PID/stack requirements before selecting values. A `stack` ulimit needs validation and argument emission, and the separate `cli/sandbox/docker/llmArchitectureCatalog.js:133–145` validator must agree if that surface supports it. State how local-llm requests it: its current manifest has no llmRuntime block. No effect follows from adding an unused key. |
| **B / early Phase 0, Phase 3 release** | Implement the exact source-build prototype early enough for Phase 0 to test what will ship. Pin builder/source identities, preserve build number/commit, establish RUNPATH/backend layout, and explicitly build `llama-bench` as well as `llama-server`; the playbook's literal build target builds only the server. Audit configure output for ignored options: `GGML_CURL` is not a defined option in the pinned root/ggml/common CMake files, and `LLAMA_CURL` is deprecated. |
| **B / Phase 3** | Reuse-proof job, architecture-specific lock/proof expectations, candidate agent-code pin, exact-index verification and install-check dependencies from finding 4. Add tests for new arm64 contracts and preserve the existing amd64 proprietary/no-weights checks. Verify both CPU backends and CUDA library closure in the final image without granting extra privileges. |
| **B+C / Phase 4** | Resolve and hash the actual arm64 lock, including all CUDA components/extras and tokenizer data. Validate the full installed distribution closure, not only the current five selected `check.distributions` entries. Current `runner_install_check.mjs:163–165` labels any failure of a GPU-only import as “needs a GPU”; collect a real-GPU import/JIT/chat result to distinguish an architecture/import failure from a missing driver. |
| **C / Phase 2** | Include C4. Select the catalog from the detected profile at initialization while preserving an explicit LOCAL_LLM_CATALOG_FILE override. The present seam only loads a file; it does not select a profile. Check existing registry/recommended parameters: the seed gpt-oss entry currently recommends `nCpuMoe:17` and 256-token batches (`catalog/models.json:58–67`). A unified default must not accidentally retain those settings or rewrite x86 recommendations. |
| **C / Phase 2** | Inject the hardware profile into adapter schema/defaults, normalization, launch, admission and UI. Update the dashboard's per-model admission meters as well as its summary card (`local-llm-dashboard-view.js:356–357`). Add finite-value serialization tests so no `NaN` is silently emitted as JSON null. |
| **C / Phase 2 and 0 validation** | Define initial peak-memory budgets and the guard failure policy; test pre-spawn checks, loading, ready, failed telemetry, stop/drain, replacement and rapid allocation. Keep MTP opt-in per validated model until its memory and throughput are measured. “Ten threads” is not CPU affinity: if X925-only execution is intended, account for allowed CPUs and validate actual affinity separately. |
| **C / Phase 2** | DS002 and split-source work from finding 11, plus a documented bound for context/completion limits and a decision on the outer timeout work from finding 5. |
| **D / independent, release when migration is documented** | Update all retained references to deleted specs and legacy docs; correct the agent count. Preserve any needed translation/reranking contracts or document their retirement. Search persisted workspace configuration by names without modifying it during review; external deployments remain an author/operator question. |
| **E / Phase 3 acceptance** | Keep the enable line, plugins and MINIMUM_REVISIONS value. That table handles **missing manifests in old sibling checkouts**, not runtime capability (`tests/smoke/lib/explorer-graph.mjs:175–201`), so bumping it would not validate multi-arch behavior. Add or designate a smoke test that proves this no-wait agent actually starts, its dashboard reports unified memory/unsupported runners correctly, and a small model answers through Soul Gateway. Graph presence alone cannot catch the observed Exec format error. Run the same shared-source candidate on an x86 GPU and check the old defaults/admission. |

The phase order should be: A1 unit-tested change → authorized Box rollout and small nested CUDA probe; in parallel, develop the B2 prototype and profile fixtures → bounded build comparison/memory characterization → C1–C10 **including C4**, revised docs and tests → architecture-specific image/install proofs and x86 GPU regression → assemble index and update manifest → arm64 vLLM enablement only after its Phase 4 gate. Cleanup need not be on this critical path. MTP, larger contexts and the broad catalog may be staged after the first validated llama.cpp/Ollama release if they delay the basic port.

## 5. Open decisions

1. **llama.cpp: retain the CUDA 13.0 source-build proposal as the initial candidate.** It permits an exact driver/toolkit baseline and explicit GB10 kernels. Fix build identity and runtime library discovery first. Prefer the prebuilt release if the same workload/peak-memory/correctness tests demonstrate equivalent behavior on driver 580; CUDA 13.4 is not inherently disqualified. Use a predeclared performance tolerance and repeated samples, rather than an undefined “within noise.” Match model hashes, source version, load mode, context, cache types, thread policy and batch sizes; historical published numbers are a sanity check, not the A/B baseline.
2. **Ollama: include if its Phase 0 gate passes.** It preserves the existing choice and model source type, and its release has relevant arm64 CUDA support. The 1.55 GB archive is compressed payload, not a measured image-size saving. Measure final layers and account for duplicated model storage. If dropping it, make unsupported status explicit and reconsider claims of parity.
3. **LM Studio: keep the current amd64-only integration.** Its engine path and locked artifact are x86-specific; arm64 support is unnecessary to meet this goal. Preserve the default-off operator switch, acceptance gate and validate-only CI for amd64, and ship neither proprietary files nor its unused SDK in arm64.
4. **amd64: reuse the existing digest in the first index.** The registry and imagetools contract support this. Keep its original provenance label and exact child digest, then prove the new shared JS against it. Promise no new amd64 image layers, not zero metadata fetches, cache invalidations or restarts.

## 6. Questions for the plan's author

1. Which exact model/quantization/context/parallel combinations must be supported in the **first** arm64 release, and what maximum temporary disk allocation is available for Phase 0? The full proposed catalog cannot be validated within a 40 GB peak budget.
2. Which x86 GPU host will run the shared-code regression gate, and which pinned models/settings represent the existing users? Unit tests and reuse of image bytes cannot prove CUDA execution or unchanged runtime behavior.
3. Does “Claude Code sends 32,000” define an initial consumer acceptance requirement, or is it later work? That determines whether the minimal gateway/outer-timeout change must move forward from Phase 5.
4. Are there external users or persisted profiles enabling any of the twelve legacy agents, particularly translation/reranking? No checked source consumer uses them, but I cannot establish the external migration impact from this workspace.

After writing the independent findings, I checked for earlier reports again: only the prompt and this report matched the review filename pattern. No comparison section is therefore included. Final plan verification returned the same SHA256 and modification time recorded in the header.
