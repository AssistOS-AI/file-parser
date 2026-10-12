You are reviewing an engineering plan. You did not write it. Your job is to find what is wrong, missing or risky in it, not to implement it.

## The plan

Read `/home/research/work/plans/local-llm-multiarch-plan.md` in full before anything else. It may have been revised since this prompt was written, so treat the file, not this summary, as the plan.

In short: the Ploinky agent `local-llms/local-llm` runs open-weight LLMs on a GPU, but its image is amd64-only. The plan makes it run on this NVIDIA DGX Spark (aarch64, GB10 GPU with compute capability 12.1, unified CPU/GPU memory, driver 580 / CUDA 13.0). It does so by publishing the image as a multi-arch OCI index (amd64 unchanged, a new arm64 build) and adding a run-time hardware profile (dedicated vs unified memory) to the agent's shared JavaScript. It also fixes Ploinky's GPU discovery on arm64 and deletes the legacy agents from the `local-llms` repo.

The owner has decided on one agent with a multi-arch image instead of two agents. Challenge that decision only with concrete evidence that it fails.

## Before you start

1. Record which version of the plan you review: run `sha256sum` and `stat -c %y` on the plan file and put both in your report header. If the file changes while you work, re-read it, review the new version, and note the change in the report.
2. Other agents may already have reviewed this plan (`/home/research/work/plans/local-llm-multiarch-plan-review-*.md`). Do not read their reports until your own findings are written, so that your review stays independent. Afterwards, read them and add the comparison section described under Output.
3. Read each repository's `CLAUDE.md` and `AGENTS.md` before judging work in it. The `local-llms` repo treats its DS specifications as the source of truth.

## Ground rules

- Read-only review. Do not edit, create or delete files in any repository. Do not commit, branch, `git pull`, `git checkout` or `git stash` anywhere under `/home/research/work`. The repos under `/home/research/work/.ploinky/repos/` are the installed sources of a live workspace, so changing them changes the running system. If you need another revision of a repo, clone it into a temporary directory of your own.
- Do not start, stop, restart or recreate Ploinky, the Box container or any agent container. Do not run `ploinky start`, `restart`, `enable`, `disable`, `gpu grant` or `gpu revoke`. These are fine: `ploinky gpu status` (from `/home/research/work`), `podman ps`, `podman inspect`, and `podman exec <box> <read-only command>`.
- Do not pull container images, download model weights, install packages, build software or run benchmarks. Free disk is limited (check with `df -h /`), and builds and benchmarks belong to the plan's Phase 0. If a claim can only be settled that way, mark it unverifiable and name the Phase 0 measurement that would settle it. Metadata lookups are fine: GitHub REST API and raw files, PyPI JSON API, registry manifest requests, release asset lists, vendor documentation.
- Running existing unit tests is fine. Examples: from `/home/research/work/.ploinky/repos/local-llms`, `node --test 'local-llm/tests/*.test.mjs'`; Ploinky's tests under `/home/research/work/ploinky/tests/unit/`. Report the results as they are. Small throwaway scripts in your own temporary directory are fine too.
- The only file you may write is your report (see Output).

## What to do

### 1. Verify the facts

The plan has a section listing the facts it relies on, with commands to check them. Re-check every one you can on this machine or through metadata APIs. Mark each confirmed, refuted or unverifiable, with the command output or `file:line` behind the verdict. Also check any factual claim elsewhere in the plan that a finding of yours depends on. Give extra weight to:

- **Ploinky GPU discovery.** `parseLdconfigCache` accepts only `x86-64` (`/home/research/work/ploinky/ploinky-box/gpuGrant.mjs`). Does anything else in the host-side GPU grant path (device list, library list, CDI spec, fingerprint, marker) assume x86 or a discrete GPU?
- **No new Box image.** Check the Box's mounts, whether its podman handles the CDI device on arm64, and anything architecture-specific in `container-image-builds/images/ploinky-box`.
- **Image indexes.** `ploinky-node`'s pinned digest should be a multi-arch index and `local-llm`'s a single amd64 manifest (query the registry). Does `docker buildx imagetools create` accept the existing single-platform manifest digest inside a new index, including any provenance or attestation manifests the current image carries?
- **The llama.cpp build.** Is compiling in the image on a GPU-less CI runner equivalent in performance to NVIDIA's native build on the Spark? The image build uses the DGX Spark playbook's CUDA flags (`121a-real`), but `GGML_NATIVE=OFF` with CPU variants chosen at run time. Is the builder's CUDA version the right match for the 580 driver? Is the prebuilt fallback's CUDA 13.4 safe on that driver without a forward-compatibility package? Check:
  - NVIDIA's playbook (`github.com/NVIDIA/dgx-spark-playbooks`, `nvidia/llama-cpp`);
  - llama.cpp's release CI, `ggml/src/ggml-cuda/CMakeLists.txt` and `ggml/src/ggml-cpu/CMakeLists.txt`, at the pinned build.
- **Other arm64 runners.**
  - Ollama's `ollama-linux-arm64` asset at the pinned version, and its GB10 support.
  - vLLM's aarch64 wheel and its dependency closure on Python 3.13 aarch64 (torch, the `cuda-toolkit` wheels, `flashinfer-python`, `nvidia-cutlass-dsl`, Triton). Does any dependency lack an aarch64 cp313 wheel or need a build from source?
- **Admission on GB10.** `local-llm` admission should approve everything when `nvidia-smi` reports `[N/A]`. Read `src/controller/hardware.mjs` and `src/controller/admission.mjs`; a small in-memory reproduction in your temporary directory is fine.

### 2. Judge the plan

For each workstream (Ploinky, image, agent code, cleanup, Explorer) and for the phase order, look for:

- **Correctness:** steps that would not work as written.
- **Missing work:** things the change needs that the plan does not mention. Places to look:
  - every remaining x86 or CUDA 12 assumption in `local-llm/src`, `local-llm/tools/runner_install_check.mjs`, `runnerInstaller.mjs` and `runnerLock.mjs` (allowed hosts, uv binary, Python path);
  - the image proof and install-check jobs in `container-image-builds/.github/workflows/publish-local-llm-image.yml`, and tests in `container-image-builds/tests/`;
  - Ploinky's dependency cache and runtime-key probe (`ploinky/cli/utils/dependencies/`) for an agent whose image differs by platform;
  - Explorer's smoke tests (`AchillesIDE/tests/smoke/`);
  - documentation and specs that say "amd64 only".
- **Risk to existing x86 users:** shared code changes, when the manifest pin changes, and regressions that CI without a GPU would not catch.
- **Unified-memory design:**
  - Is detecting "unified" from `[N/A]` plus compute capability 12.x robust (future drivers, GH200, Jetson Thor, containers without `nvidia-smi`)?
  - Is admitting against MemAvailable sound when the page cache holds model files and CUDA allocations on GB10 may not reclaim it?
  - Is `--no-mmap` the right default?
  - Is an always-on memory guard enough without swap, given that nested agents have no memory limits?
- **Security:** does the arm64 build keep every rule of `local-llm`'s DS001 and DS003 (loopback runners, per-start keys, minimal runner environment, no secrets in images, the runner lock's allowed hosts and sha256 pinning, never shipping proprietary files)?
- **Cleanup:** anything that still references the legacy agents or the `assistos/local-llms` image (search beyond the repos the plan lists if you can), and anything in the legacy tree worth keeping.
- **Sequencing:** can any phase start earlier or later, and are the gates between phases right?

### 3. Answer the open decisions

For each open decision in the plan, give a recommendation with reasons.

## Output

Write your report to `/home/research/work/plans/local-llm-multiarch-plan-review-<agent-name>.md`.

- `<agent-name>` is the agent and model you are running as, in lowercase with hyphens, for example `claude-code-opus-5-5` or `codex-gpt-5`.
- Never overwrite another report: if the file exists, append `-2`, `-3` and so on.

Start the report with this header:

```
Reviewer: <agent-name>
Date: <today's date>
Plan: /home/research/work/plans/local-llm-multiarch-plan.md, sha256 <hash>, modified <time>
```

Then these sections:

1. **Verdict:** one paragraph. Is the plan sound enough to start Phase 0 and Phase 1?
2. **Fact check:** a table with claim, verdict (confirmed / refuted / unverifiable) and evidence (command output excerpt or `file:line`).
3. **Findings**, most severe first. For each: severity (blocker / major / minor), where (`file:line` or plan section), what is wrong, the evidence, and a concrete fix to the plan.
4. **Missing work:** items to add to the plan, each assigned to a workstream and phase.
5. **Open decisions:** your recommendation for each.
6. **Questions for the plan's author:** only things you could not settle yourself.
7. **Comparison with earlier reviews:** written after your findings, and only if other reports exist. Say where you agree, where you disagree and why, and which of their findings the current plan already addresses. Leave this section out if there are no other reports.

At the end of the session, print a short summary and the report's path.

Be specific and evidence-based. Say plainly when you could not verify something and why. Do not pad the report with restatements of the plan or with generic advice.
