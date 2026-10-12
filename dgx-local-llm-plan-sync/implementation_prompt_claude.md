> Verbatim first prompt of the pgx implementer session "Local LLM multiarch engineering plan" (`local_d1b738b8…`, CLI `a519e4b1…`), record `c34fe82d-b34e-464a-9a8e-b48d8929a4d6`, 2026-09-28T12:34:20.606Z.



<pasted_content id="55ae">
You are implementing an engineering plan on this machine: an NVIDIA DGX Spark (aarch64, GB10 GPU, 119.6 GiB of unified memory, no swap).

## 1. Read first
1. The plan: /home/research/work/plans/local-llm-multiarch-plan.md. Run sha256sum on it. The current reviewed and revised version is b5a9537626c71dce8974f30fcc31b2ff54bee61719a25bf31176a5f66393da94. If the hash differs, someone edited the plan after this prompt was written: follow the current file and record which version you used.
2. The two reviews the plan answers. Use them for evidence and file:line references:
   - plans/local-llm-multiarch-plan-review-claude-code-opus-5-5.md
   - plans/local-llm-multiarch-plan-review-codex-gpt-6_codex.md
   The plan's "Review response" section maps their findings to plan items. Where the plan and a review disagree, the plan wins.
3. Before changing a repository, read its CLAUDE.md and AGENTS.md.
   - In local-llms, the DS specs are the source of truth (local-llm/docs/specs, DS000–DS004). Update the specs, and the HTML docs where they exist, in the same change as the code.
   - In Ploinky, code and tests are the source of truth, and DS files must not have a Conclusion section.

## 2. The machine
- An existing Explorer deployment lives in /home/research/work (Box ploinky-box-work-287e15733c26, 15 agents). It is not needed.
  - You may stop it at any time, and destroy it when you need its disk, memory or ports. Use Ploinky's own commands for that (see its README), not raw podman, so its state stays consistent.
  - Keep /home/research/work/plans (the plan, the reviews and your log), /home/research/work/AdvancedLanguageAgent, and the host's Ploinky checkout /home/research/work/ploinky.
  - Ask me before deleting workspace data in /home/research/work/.data.
- Don't develop in place in the installed repos (/home/research/work/.ploinky/repos/*) or in /home/research/work/ploinky.
- The Ploinky CLI is /home/research/work/ploinky/bin/ploinky; it is not on PATH. Run test workspaces with your dev clone's CLI instead.
- There is no gh CLI and no GitHub token, so api.github.com is unauthenticated: 60 requests per hour, shared with other sessions. Prefer raw.githubusercontent.com and https://github.com/<owner>/<repo>/releases/expanded_assets/<tag>.
- Installed tools: skopeo, podman, docker, nvidia-ctk 1.19.1, and CUDA 13.0 (nvcc).
- Disk: about 132 GB free on /. The existing deployment's Box image store (/home/research/work/.ploinky/box/images) takes about 13 GB more. Keep at least 20 GB free at all times. Check `df -h /` before every download or build, and delete artifacts between steps.
- Memory: GB10 GPU memory is invisible to RSS, OOM scoring and memory cgroups, and there is no swap. Start with small models, watch MemAvailable, and run GPU test processes with oom_score_adj=1000.
- Don't use sudo. If something needs root, such as dropping caches or writing /etc/cdi, ask me.

## 3. How to work
- Clone each repository you change into /home/research/dev/<repo>, from its GitHub origin. Fetch the default branch first and note whether it is ahead of the installed copy. Work on feature branches without a codex/ prefix.
- Commits follow each repository's CLAUDE.md. local-llms, proxies and AchillesIDE forbid AI co-author trailers and AI attribution in commits and PR descriptions, so add none there. Elsewhere, match the style of the repository's recent `git log`.
- Get my explicit go-ahead before you push, open a PR, dispatch a GitHub workflow, publish or tag an image, or change anything on Docker Hub.
- Don't run Ploinky's cross-repository E2E release gate (described in its CLAUDE.md) unless I ask.
- Keep an implementation log at /home/research/work/plans/local-llm-multiarch-implementation-log.md. Record:
  - each phase and the commands you ran;
  - measurements, as tables;
  - branches and commits;
  - test results, reported as they are;
  - the decisions I made;
  - every deviation from the plan, with its reason.
- Other sessions may write in plans/. Never overwrite their files, and don't edit the plan without my OK.
- If the plan turns out to be wrong or impossible somewhere, stop and show me the evidence instead of silently diverging.
- At each stop, report what changed, test results as they are, open risks, and the next step you propose.

## 4. Order of work (follow the plan's phases and gates)
1. **Baseline.** Clone, branch, and run the existing tests:
   - local-llms: from the repo root, `node --test 'local-llm/tests/*.test.mjs'`. Two LM Studio tests are known to fail on this 20-core host; the plan fixes them.
   - Ploinky: `node --test tests/unit/ploinkyBoxGpuGrant.test.mjs`, plus the unit tests for anything you touch. Some test files need PLOINKY_AGENTLIB_DIR and only load when run the way Ploinky's own test scripts run them.
   - container-image-builds: `node --test tests/image-definitions.test.mjs`.
2. **Phase 1 code** (no hardware risk):
   - A1 (+ A2) in the Ploinky clone, with the explicit-architecture tests.
   - C0 in the local-llms clone, with tests.
   - Stop and show me the diffs and the test results.
3. **Phase 0**, host-level and without Ploinky, in a scratch directory outside /home/research/work.
   - First stop the existing Explorer deployment. That frees memory and removes processes the OOM killer could hit. Destroy it if you need its disk. As the plan notes, deleting only its dead amd64 image does not last.
   - Before downloading anything, show me a disk table (each artifact, its size, the peak, and when it gets deleted), and get plan decision 6 from me.
   - Then run the Phase 0 items as the plan describes them:
     - the three llama.cpp builds: L1, the prebuilt release pinned by sha256; L2, the source build exactly as B2 describes, in a podman build with the pinned builder image; and the playbook-native reference, built with the host toolkit;
     - llama-bench with identical flags and repeated samples, the correctness check, and cuobjdump;
     - the memory measurements;
     - the Ollama gate, running Ollama on 127.0.0.1 on a non-default port.
   - Run the binaries directly on the host.
   - Report the results as tables. Propose the admission constants, the guard floor and the measured envelope, and ask me to take decisions 1 and 2 using the plan's rule.
4. **Phase 1 nested check.** Use a fresh test workspace run by your dev Ploinky clone, for example /home/research/gpu-test-workspace. Alternatively, reuse /home/research/work after destroying the Explorer deployment (keep plans/).
   - Enable only local-llm there. Each workspace's Box has its own image store, and Explorer's whole graph would pull about 13 GB.
   - Point its local-llms dev checkout at a local arm64 image, localhost/local-llm:dev. Build that image from your Dockerfile.arm64 prototype and load it into the test Box's own image store.
   - Verify that the test Box mounts your dev Ploinky clone and has GPU wiring.
   - Then run the CUDA probe and a small model from the nested agent container, and repeat the GB10 memory measurements there.
5. **Phase 2:** C1–C11 (C4 included), with specs and tests.
   - The dedicated profile must stay byte-identical: tests/runner-characterization.test.mjs and tests/cpu-cores.test.mjs unchanged, plus a golden readGpu test on today's x86 output.
   - Then stop. The x86 GPU gate needs my x86 host (decision 5); give me the exact steps to run there.
6. **Phase 3:** B1–B4 in the container-image-builds clone.
   - This covers the amd64 reuse-and-prove job, Dockerfile.arm64 with the chosen llama.cpp candidate, per-architecture locks (the first arm64 runner lock is empty), and the workflow and its tests.
   - Build and prove the arm64 image locally with podman, then stop before pushing or dispatching.
   - After I publish, run the Spark acceptance in the test workspace, prepare the manifest pin change, and wait for my go-ahead for the x86 re-check.
   - Then, if I want Explorer back on this host, redeploy it from the released revisions.
7. **D** can be prepared on its own branch once its spec dependencies are handled: the coding-style spec kept, and references to the deleted specs rewritten. Get decision 10 from me first, and don't merge D without me.
8. **Phase 4 (vLLM) and Phase 5** only when I say so, and only after decisions 7 and 8.

## 5. Must hold throughout
- Existing amd64 users see no change in behaviour.
- local-llm's DS001, DS003 and DS004 rules hold:
  - runners listen only on loopback, with per-start keys;
  - runners get a minimal environment;
  - no secrets in images;
  - the runner lock uses only its allowed hosts, with every file pinned by sha256;
  - nothing unpinned is downloaded at run time;
  - no proprietary file (LM Studio) in any image.
- Ploinky's invariants in its CLAUDE.md hold: it stays rootless and unprivileged, and GPU wiring adds only device nodes, read-only driver binds, the hookless CDI spec, the grant marker and one label.

## 6. Decisions to get from me
These are in the plan's "Open decisions" section. Ask for each one when you reach it, with your recommendation and the evidence:
- decision 6, before the Phase 0 downloads;
- decisions 1 and 2, after Phase 0's results;
- decision 5, before the Phase 2 gate;
- decision 9, before C7;
- decision 10, before D;
- decisions 7 and 8, before Phase 4.
Decisions 3 and 4 are already settled.
</pasted_content id="55ae">
