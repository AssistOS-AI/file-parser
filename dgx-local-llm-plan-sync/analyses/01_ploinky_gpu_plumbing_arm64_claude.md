# Agent "Audit Ploinky GPU plumbing on arm64" finished

> Verbatim subagent result from the pgx-research session `local_2ef99e76-6bed-4e68-bf4a-d611494a62a5` (CLI `e95c870c-8d4a-46a7-bacf-21525480837e`), transcript record uuid `a6b6e835-ab07-4088-a594-13c3e43a6dca`, 2026-09-28T10:52:39.286Z.
> File paths are on the pgx host under `/home/research/work`, not on this Mac.

I found one hard blocker for a CUDA agent on this host: the ldconfig architecture filter. The rest of the GPU path is not arch-specific. The other items limit or slow a vLLM/llama.cpp agent without stopping it, apart from multi-Spark networking, which the Box design rules out. This was read-only: no files changed and no containers restarted. The only things I ran were the three GPU/runtime unit test files (70 pass), and read-only commands inside the Box through `podman exec`.

## 1. GPU grant code (`ploinky-box/gpuGrant.mjs`)

- **`:232-243` `parseLdconfigCache`**: line 239 only accepts entries flagged `x86-64`. On this host every entry is `libc6,AArch64` (zero x86-64 entries out of 1418), so discovery fails. The version parser (`:245`) already handles "Kernel Module for aarch64 580.159.03".
- **What happens once the parser is fixed:** discovery should pass on this host.
  - The 3 device nodes (`:49`) exist and are `rw-rw-rw-`.
  - The required libraries (`:53-57`) resolve to `/usr/lib/aarch64-linux-gnu/*.so.580.159.03`.
  - The optional `libnvidia-nvvm.so.4` and `libnvidia-gpucomp.so.580.159.03` (`:58`, `:337`) are in the ldconfig cache.
  - `/usr/bin/nvidia-smi` is there.
  - The `/usr/local/nvidia/{lib64,bin}` paths (`constants.mjs:41-46`) are arch-neutral.
- **CDI spec (`:397-418`)** has no hooks and no env: device nodes plus read-only binds only. So there is no `libcuda.so` symlink, no ld-cache update and no `enable-cuda-compat`.
- **Fingerprint (`:464-478`) and observation regex (`:760`, `:776`)** have no arch assumptions.
- **`gpuGrantMarker.mjs`** is arch-neutral.

**Compared with NVIDIA's `/etc/cdi/nvidia.yaml`, Ploinky leaves out:**
- **Needed for compute, and missing:**
  - `libnvidia-nvvm70.so.4`: `libcuda` loads it by name (seen in its strings), but ldconfig lists only `libcuda.so.1`, not the unversioned `libcuda.so`. Its real file is named `.so.4`, so the `versionedName` check (`:323`) would reject it as written.
  - The unversioned `libcuda.so` symlink: Triton, which vLLM uses, links against `-lcuda`.
  - The forward-compat hook: without it the agent image's CUDA must be 13.0 or lower (driver 580).
- **Useful for profiling only:** `/dev/nvidia-uvm-tools` (CUPTI/Nsight).
- **Not needed for CUDA inference:** `/dev/nvidia-modeset`, `/dev/dri/*`, `libcudadebugger`, `libnvidia-cfg`/`opencl`/`encode`/`nvcuvid`, the GL/EGL/Vulkan libraries, the GSP firmware, the persistenced socket and the MPS binaries.
- **`/dev/nvidia-caps` and IMEX:** NVIDIA's own spec omits them too. `nvidia-cap1` is root-only, and no IMEX channels exist. Not needed.
- **`nvidia-smi` memory `[N/A]`:** Ploinky core never reads it (`cli/sandbox/docker/hardwareDetection.js:89` runs only `nvidia-smi -L`). Only the local-llm agent parses it (`src/controller/hardware.mjs:29`).

**Tests:** `tests/unit/ploinkyBoxGpuGrant.test.mjs:61-62`, `:101`, `:114` and `:296` use x86-only fixtures (`/usr/lib/x86_64-linux-gnu`, `(libc6,x86-64)`). They pass here only because the parser is hard-coded. An arch-aware parser that defaults to `process.arch` would break them on arm64 unless the arch is injected. They need arm64 fixtures.

## 2. `containerSecurity` and the runtime policy

- **Supported keys** (`cli/sandbox/runtimeCapabilities.js:26`, validated at `:218-259`):
  - `gpu` (boolean)
  - `nestedPodman` (boolean)
  - `privileged` (boolean; refused inside a Box, `:500`)
  - `shmSize` (`^[1-9]\d{0,5}[mg]$`, capped at 16g, `:29-30`)
- **Resource knobs** go through `llmRuntime.runtimePolicy`. It applies to any agent and does not need `enabled` (`:415`, `agentServiceManager.js:1785`). Keys: `platform`, `resources{memory,cpus,pidsLimit,shmSize,ulimits.memlock{soft,hard}}`, `devices`, `securityOpt`, `ipc`, `gpus` (`containerRuntimePolicy.js:67-106`, `:168-204`; output at `:254-306`).

| Requirement | Possible? |
|---|---|
| GPU device without privileged | Yes. `gpu:true` gets exactly `--device ploinky.local/gpu=all` (`:434-452`). No extra `/dev/dri` is allowed alongside it (`:164`). |
| `--ipc host` | No. Refused inside a Box (`:507`). The agent always gets `--ipc private` (`containerRuntimePolicy.js:299`). |
| `--ulimit memlock=-1` | Yes, via `resources.ulimits.memlock:{soft:-1,hard:-1}`. The Box's hard memlock limit is unlimited. |
| `--ulimit stack=67108864` | No key for it. The agent can raise its own soft limit (`ulimit -s`), since the Box's hard stack limit is unlimited. |
| `/dev/shm` of 16g or more | Up to exactly 16g. |

**Box container (read-only inspect):**
- Memory: unlimited. PidsLimit: **2048** (podman's default; the create command at `lifecycle/container.mjs:155-200` passes no `--pids-limit`). Currently 716 used, peak 877.
- ShmSize 64 MB (the Box's own; agents get their own `/dev/shm`). No devices (no grant yet). SecurityOpt: `label=disable`, `unmask=all`, nested seccomp. Not privileged.
- The Box's `/etc/containers/containers.conf` sets `cgroups="disabled"`. So `memory`, `pidsLimit` and `cpus` are not enforced on nested agents (running agents show Pids=0, Mem=0), and all agents share the Box's 2048-pid cap.

## 3. Multi-arch images

- **ploinky-box** (`.github/workflows/publish-ploinky-box-image.yml:45-58`, `:158`, `:288`) and **ploinky-node** (`publish-ploinky-node-image.yml`) both work the same way:
  - a matrix builds amd64 on `ubuntu-24.04` and arm64 on `ubuntu-24.04-arm`, natively (no QEMU);
  - each job runs `docker/build-push-action` with `platforms: ${{ matrix.platform }}` and `push-by-digest=true`;
  - a proof job runs per arch;
  - an `assemble` job runs `docker buildx imagetools create` from the two proven digests.
- The live `ploinky-box:latest` is an OCI index with amd64 and arm64 entries.
- **local-llm is amd64-only** (`publish-local-llm-image.yml:3-5`, `:68`; pinned x86 CUDA builds). It cannot run on this host.
- For a new arm64 CUDA image, copy the ploinky-node pattern, using a single arm64 matrix entry or both. The hosted arm runners have no GPU, so the proof step can only use `ldd` with `libcuda` excluded, as local-llm does (`:109-120`).

## 4. Design intent (D14)

- D14 is documented in `README.md:652-753`, `CLAUDE.md` invariant 4, `docs/specs/DS005…:116-119` and `DS014…:57,69`. `proposals/` has nothing on GPU.
- **Several agents can hold the GPU at the same time.** The wiring is a set of up to 64 agents (`gpuGrant.mjs:146`, `:80`), and each one gets the same `ploinky.local/gpu=all` device. There is no exclusivity or memory accounting, so `local-llms/local-llm` and `dgx-local/dgx-local-agent` can both be named. They will compete for the 128 GB unified pool and have to coordinate between themselves.

## 5. Networking

- `network.mode:"host"` (`agentServiceManager.js:837`) gives the agent the **Box's** network namespace, not the physical host's.
- The Box uses `pasta:--ipv4-only` and sees only a copy of `wlP9s9`: no ConnectX-7 interfaces and no `/dev/infiniband`.
- Outbound TCP follows the host's routing through pasta. Inbound connections from other Sparks are impossible by invariant 3 (only two publications allowed).
- So NCCL/RoCE across several Sparks is blocked by design, not by a bug.

## Blockers

| # | Item | Severity |
|---|---|---|
| B1 | ldconfig parser accepts only `x86-64` (`gpuGrant.mjs:239`) | hard-blocker |
| B2 | local-llm image is amd64-only | hard-blocker (for reusing it) |
| B3 | Multi-Spark: no host network, RDMA or inbound access (invariant 3) | hard-blocker (future, by design) |
| B4 | Box pid cap of 2048 shared by all agents; nested cgroups disabled | degrades |
| B5 | No unversioned `libcuda.so` in the hookless spec (Triton `-lcuda`) | degrades |
| B6 | `libnvidia-nvvm70.so.4` not bound | degrades |
| B7 | No forward-compat hook: image CUDA must be 13.0 or lower | degrades |
| B8 | No `stack` ulimit key; shm capped at 16g | degrades / cosmetic |
| B9 | `/dev/nvidia-uvm-tools` not passed (profiling) | cosmetic |
| B10 | Test fixtures are x86-only | degrades (CI) |

## Proposed minimal patches

1. **`gpuGrant.mjs:232-243`:** change the signature to `parseLdconfigCache(output, { arch = process.arch } = {})` with a map `{x64:'x86-64', arm64:'AArch64'}`. Accept only that exact flag; throw `discoveryError` for an unmapped arch. Add `arch` to `discoverNvidiaGpu` (`:281`) and pass it through at `:322`. Update the `:232` comment and the README's "x86-64" wording.
2. **Tests (`ploinkyBoxGpuGrant.test.mjs`):** add `fakeHost({ arch })` with `LIB` and the flag chosen per arch, and an aarch64 `/proc` version string. Add arm64 cases:
   - AArch64 lines are accepted;
   - x86-64 lines are ignored on arm64, and the reverse on x86;
   - flagless 32-bit lines are still ignored.

   Always pass `arch` explicitly so the tests don't depend on the host.
3. **`gpuGrant.mjs:58`, `:337-348`:** add an "unversioned optional" list containing `libnvidia-nvvm70.so.4` (`libcudadebugger.so.1` is optional and cosmetic). Skip the `versionedName` check only for entries whose real file does not end in a driver version.
4. **`gpuGrant.mjs:49`:** add an optional-device list `['/dev/nvidia-uvm-tools']` that is bound when present and skipped when absent. The regex at `:760` already matches it.
5. **`lifecycle/container.mjs`, near `:157`:** add `'--pids-limit', '32768'` (or `-1`). This changes the create command, so existing Boxes are expected to be replaced once.
6. **`containerRuntimePolicy.js:92`:** allow `ulimits.stack` with the same `{soft,hard}` validation, and output `--ulimit stack=S:H` at `:277-280`. Optionally raise `MAX_SHM` (`:17` and `runtimeCapabilities.js:30`).
7. **No core change needed:** the agent image adds a `/usr/local/nvidia/lib64/libcuda.so → libcuda.so.1` symlink and sets `LD_LIBRARY_PATH`/`PATH` to include `/usr/local/nvidia`, uses CUDA 13.0 or lower, and is built with the ploinky-node workflow pattern.

Patches 1 and 2 alone should give a working grant. Patches 3-6 make vLLM/Triton run robustly.
