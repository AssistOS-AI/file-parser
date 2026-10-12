# x86 functional gate for the local-llm multi-arch work (decision 5)

Author: the implementation session (claude-code-opus-5-5), 2026-09-28. Status: **draft**. The local-llms revision below is the current head of the feature branch; the final candidate SHA will be given when Phase 2 is complete. Codex runs this from the owner's Mac on **ubuntu-codex**. Nothing here needs pgx.

Purpose: show that the shared JavaScript works on an x86 host with a GPU of its own (the dedicated profile). This is a functional check, not a check of unchanged behaviour: the owner does not require backwards compatibility. Record what actually happens: a working run, a real constraint, or the expected rejection.

## Candidate

| Part | Identity |
| --- | --- |
| Ploinky | `https://github.com/AssistOS-AI/ploinky`, branch `local-llm-multiarch`, commit `338a3c567391cdc3004daa88d1e0ad16436bfe8d`: A1 (ldconfig flag of the host architecture) and A2 (NVVM 7.0 bound when present) |
| local-llms | `https://github.com/AssistOS-AI/local-llms`, branch `local-llm-multiarch`, **head at candidate time** (today `50308c5`; the final SHA follows) |
| Image | `docker.io/assistos/local-llm@sha256:b6c79af2aad08b542339346f4a985c84d5cbcacc31e8c6df45f951da7ba0fbf7`: today's amd64 image, unchanged, as pinned in the branch's `local-llm/manifest.json` |

## Host facts (from Codex)

ubuntu-codex: x86_64, NVIDIA RTX 3060 Laptop GPU 6144 MiB, driver 595.91.07, about 26 GiB of RAM available, 398 GiB disk free, podman. Its existing workspace `/home/skutner/work/file-parser` must not be touched.

## Capacity

- gpt-oss-20b MXFP4 is 12.1 GB and does **not** fit 6 GiB of VRAM. The seed catalog's dedicated recommendation is the validated partial-offload path, measured on this GPU model: llama.cpp with `nCpuMoe 17` (17 of 24 layers' expert weights in RAM), `ctxSize 16384`, batch and micro-batch 256, about 4.8 GiB of VRAM (catalog: 4,798 MiB, 38.4 tok/s generation, 246.7 tok/s prompt, at b11159 with 12 threads).
- Ollama places layers itself; its seed recommendation is `numCtx 4096`, and it offloads what does not fit.
- The expected rejection: llama.cpp with every expert on the GPU (`nCpuMoe 0`) must be refused as `incompatible` before anything downloads.

## Steps

Use one new directory and ports that are free on the host. The example uses `/home/skutner/work/local-llm-x86-gate` and ports 18188/tcp and 17982/udp.

```sh
# 0. Isolation and preconditions
ss -ltn | grep -E ':18188 ' ; ss -lun | grep -E ':17982 '           # both must print nothing
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv   # no compute process
df -h ~ ; free -g

# 1. Sources at the candidate
mkdir -p ~/work/local-llm-x86-gate-src && cd ~/work/local-llm-x86-gate-src
git clone -b local-llm-multiarch https://github.com/AssistOS-AI/ploinky.git
git -C ploinky checkout 338a3c567391cdc3004daa88d1e0ad16436bfe8d
(cd ploinky && node --test tests/unit/ploinkyBoxGpuGrant.test.mjs)   # expect 61/61
mkdir -p ~/work/local-llm-x86-gate && cd ~/work/local-llm-x86-gate
git clone -b local-llm-multiarch https://github.com/AssistOS-AI/local-llms.git local-llms
git -C local-llms checkout <local-llms candidate SHA>
(cd local-llms && node --test 'local-llm/tests/*.test.mjs')           # expect all pass
P=~/work/local-llm-x86-gate-src/ploinky/bin/ploinky

# 2. Start the workspace with only local-llm (pulls the 4.57 GB amd64 image once)
$P --port 18188 --udp-port 17982 start local-llms/local-llm
$P gpu status
#    expect: Host GPU: nvidia driver 595.91.07; libraries resolve under /usr/lib/x86_64-linux-gnu
#    (libnvidia-nvvm70.so.4 included if the driver has it); Box: running; GPU wiring active

# 3. Overview: profile and admission (read-only)
$P client tool local_llm_overview --agent local-llm
#    expect: "profile":"dedicated"; every runner supported (the amd64 image has them all);
#    gpt-oss-20b x llama.cpp: params nCpuMoe 17, ctxSize 16384, loadMode "auto"; admission "ok",
#    estimate gpuBytes about 5.1e9; hardware.gpu.memoryModel "dedicated", device.computeCapability "8.6"

# 4. Truthful rejection (no download)
$P client tool local_llm_overview --agent local-llm \
   --parameters '{"preview":{"modelId":"gpt-oss-20b","runnerId":"llama.cpp","params":{"nCpuMoe":0,"ctxSize":131072}}}'
#    expect: preview.admission.status "incompatible", reason naming GPU memory and nCpuMoe/ctxSize

# 5. llama.cpp, partial offload (downloads 12.1 GB)
$P client tool local_llm_run --agent local-llm -requestId gate-llama-0001 -modelId gpt-oss-20b -runnerId llama.cpp
#    poll until "phase":"ready" (or "error"):
$P client tool local_llm_status --agent local-llm
$P client tool local_llm_test_prompt --agent local-llm -prompt "Say PONG." -maxTokens 64
#    record: the answer, status.runnerReport (offloaded layers, CUDA buffers), lastCompletion speed
#    in-container checks (runner env and OOM priority):
$P shell local-llm
#      then, in that shell:
#      for p in /proc/[0-9]*; do c=$(tr '\0' ' ' < $p/cmdline); case "$c" in /opt/llama.cpp/llama-server*) echo ${p#/proc/} $(cat $p/oom_score_adj); tr '\0' '\n' < $p/environ | grep -E 'CUDA_CACHE_PATH|LD_LIBRARY_PATH';; esac; done
#      expect: oom_score_adj 1000; CUDA_CACHE_PATH=/opt/runners/.cuda-cache
$P client tool local_llm_stop --agent local-llm

# 6. Ollama (pulls 13.8 GB)
$P client tool local_llm_run --agent local-llm -requestId gate-ollama-0001 -modelId gpt-oss-20b -runnerId ollama
$P client tool local_llm_status --agent local-llm        # until ready
$P client tool local_llm_test_prompt --agent local-llm -prompt "Say PONG." -maxTokens 64
$P client tool local_llm_stop --agent local-llm

# 7. Clean up (this workspace only)
$P client tool local_llm_weights_delete --agent local-llm -modelId gpt-oss-20b -runnerId llama.cpp
$P client tool local_llm_weights_delete --agent local-llm -modelId gpt-oss-20b -runnerId ollama
$P destroy
```

## What to record

| Step | Record |
| --- | --- |
| 1 | both test results as printed |
| 2 | `ploinky gpu status` output; the Box's GPU label |
| 3 | `profile`, runner list, the gpt-oss-20b llama.cpp and Ollama admissions |
| 4 | the preview's status and reason |
| 5 | phase sequence, download time, ready time, test-prompt answer and speed, runnerReport, the in-container check |
| 6 | same for Ollama |
| any | every error verbatim; if a step cannot run, say why, not "passed" |

The original large-model gate (gpt-oss-20b on llama.cpp and Ollama) passes only if steps 5 and 6 answer the test prompt.
