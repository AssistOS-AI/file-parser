# Agent "Map model consumers and prior runtime repos" finished

> Verbatim subagent result from the pgx-research session `local_2ef99e76-6bed-4e68-bf4a-d611494a62a5` (CLI `e95c870c-8d4a-46a7-bacf-21525480837e`), transcript record uuid `5f8bc2d1-70e1-4727-ad29-fb9f53c1ae3b`, 2026-09-28T10:55:55.930Z.
> File paths are on the pgx host under `/home/research/work`, not on this Mac.

**Consumer-side integration of `dgx-local-agent`: how local models are discovered and called in AssistOS/Achilles**

Short answer: one agent can already expose several models (`/coder`, `/fast`, `/big`) with no Soul Gateway change. The gaps are reasoning output (dropped), sampling fields (partly dropped), embeddings, and native Anthropic `/v1/messages` on the agent side. Nothing was modified and no containers were touched.

Path roots used below: PL=`/home/research/work/ploinky`, SG=`…/.ploinky/repos/proxies/soul-gateway`, AAL=`…/scratchpad/ref/AchillesAgentLib`, EXP=`…/.ploinky/repos/AchillesIDE/explorer`, LL=`…/.ploinky/repos/local-llms/local-llm`, CIB=`…/.ploinky/repos/container-image-builds`.

## 1. Discovery and model ids

- **The Router lists every enabled agent, not only chat agents.** `PL/cli/server/openAiAgentDiscovery.js:119-142` walks the routes. It skips only disabled or draining routes and routes with no host port (124-125).
  - `endpoints.chatCompletions` only sets `responderKind` (70-82):
    - `command`: the agent's own handler; it streams if `supportsStream` or `stream` is set.
    - `inert`: `model:"none"` or `"off"`.
    - otherwise `llm`: the Achilles agentic default responder.
  - Each row carries repo, agent, `routerPath:/&lt;routeKey&gt;` and `/v1/chat/completions` (84-108). The endpoint requires an agent assertion (188-210).
- **Soul Gateway turns agents into models.**
  - It polls every 60 s (`SG/src/ploinky/discovery-scheduler.mjs:33`) and upserts one provider per agent with adapter `ploinky-agent-openai` (`reconcile-agents.mjs:203-231`).
  - It then GETs `/&lt;routeKey&gt;/v1/models` through the Router (`runtime/backends/builtin/ploinky-agent-openai.backend.mjs:214-257`) and syncs with `disableMissing:true` (`reconcile-agents.mjs:540-557`). An empty list never disables anything (`runtime/providers/auto-provisioner.mjs:534-544`).
  - Model key = `${repo}/${agent}/${modelId}`, where `modelId = row.modelId || row.providerModelId || row.id` (backend 405-420).
- **Where `/default` comes from.** AgentServer's `/v1/models` (`PL/Agent/server/AgentServer.mjs:843-870`) runs `endpoints.models.command` if one is declared. Otherwise it returns a fallback (810-841): a single row with `id:'default'` and `displayName` set to the agent name. The row also carries `supportsTools:true`, `supportsVision:false`, and tags from `capabilities.tags`, or `['generic-agent']` when none are declared (813).
  - If model sync fails, Soul Gateway also writes a `&lt;repo&gt;/&lt;agent&gt;/default` placeholder (`reconcile-agents.mjs:108-151`).
- **Multiple models per agent: yes, already supported.**
  - Declare `endpoints.models.command` returning `{object:'list', data:[{id:'coder',…},{id:'fast'},{id:'big'}]}`. That yields `dgx-local/dgx-local-agent/coder` and so on.
  - Soul Gateway sends `model: providerModelId` (e.g. `"coder"`) in the chat body (backend 146, 289-293), so the chat handler must dispatch on `request.model`. The existing local-llm ignores it: it overwrites `body.model` at `LL/src/chatResponder.mjs:100`.
  - Descriptor fields Soul Gateway honours (backend 416-465): displayName, contextWindow, maxOutputTokens, supportsTools/Streaming/Vision, pricing, isFree, tags.

## 2. Protocols

The chain is: client → Soul Gateway ingress → `ploinky-agent-openai` backend → Router, which only delegates the exact paths `/v1/chat/completions` and `/v1/models` (`PL/cli/server/agentOpenAiDelegation.js:44-57, 258-312`) → AgentServer (1405) → the command handler. The handler receives `{endpoint:'openai.chat.completions', request, metadata}` on stdin (693-700).

| Feature | Status on this path |
|---|---|
| Streaming (SSE) | **Yes.** Soul Gateway requests `stream:true` whenever the model row says it supports streaming, whatever the client asked (backend 169-178, 289-293). AgentServer pipes handler stdout raw (730-807) and the Router pipes the response back (`routerHandlers.js:208-228`). The default `llm` responder only fakes SSE with a single chunk (`AgentServer.mjs:427-445`). |
| `tools`, `tool_choice`, `tool_calls` | **Yes.** Forwarded at backend 157-160; parsed for streaming (601-613) and non-streaming (665-680) responses. |
| Other request fields | Only `max_tokens`, `temperature`, `top_p`, `stop`, `response_format` and the provider's `settings.extra_body` are forwarded (backend 144-167). **Dropped:** `reasoning_effort`, `chat_template_kwargs`, `seed`, penalties, `n`, `logprobs`, `parallel_tool_calls`, `stream_options`, `max_completion_tokens`. |
| `reasoning_content` | **Not supported.** It is ignored at backend 596-613, and Soul Gateway's internal stream has no reasoning event (`runtime/kernel/canonical-stream.mjs:1-45`). The agent backend also sends no keep-alive signal during reasoning, so a long think counts as silence for the timeouts (`runtime/execution/timeout-middleware.mjs:15-40, 143-157`). |
| Large contexts | Body limits are not the problem: 5 MiB in Soul Gateway (`BODY_LIMIT_BYTES`, `config/env.mjs:136`) and 10 MiB in the Router (`routerHandlers.js:22`). No context-window check exists. The real limit is time: the default request deadline is 120 s (`config/env.mjs:54-57`) and stream idle is 300 s. Token usage is read from any chunk (backend ~617-626). |

- **Anthropic `/v1/messages`:** only at the gateway. Soul Gateway accepts `/v1/messages` and `/v1/responses` (`public-api/register-routes.mjs:31-36`) and converts them into OpenAI chat calls to the agent. AgentServer serves only `/v1/chat/completions` and `/v1/models` (44-45), and the Router delegates only those two paths.
- **Other endpoint kinds:** a manifest can declare only `chatCompletions`, `models` and `agent-card` (`PL/docs/specs/DS005-agent-manifest-and-registry.md:143-152`).
  - Soul Gateway has `/v1/embeddings`, but it needs a backend with `embed()` (only `openai-api.backend.mjs` has one) and a model tagged `embeddings` (`public-api/embeddings-route.mjs:20, 204-211`).
  - There is no rerank or legacy completions path to agents.

## 3. Tiering

- **AchillesAgentLib just points at gateway tiers.** `LLMConfig.json` `defaults` maps each intent to a Soul Gateway tier: `fast→soul_gateway/fast`, `code/coding→soul_gateway/code`, `plan/thinking/vision→soul_gateway/plan`, `deep/research/long-context→soul_gateway/deep`, plus `write` and `ultra`.
  - Resolution order (`utils/LLMClient.mjs:172-217`): explicit model through the defaults map → `modelConfig[tag]` → tag scoring over discovered models (80-111) → `plan`.
  - Gateway models appear as `soul_gateway/&lt;key&gt;` (`providers/modelsConfigLoader.mjs:532-610`).
  - Per-process override: `LLM_MODELS_CONFIG_PATH` (620-623). The AdvancedLanguageAgent CLI adds `--model`, `ALA_MODEL`, `--tag` and `--model-config`.
- **The tiers themselves live in Soul Gateway.** `fast, code, plan, write, deep, ultra, web-assist` are cascades seeded once from free OpenRouter models (`bootstrap/free-model-catalog.mjs:167-240`; `LLM_DEFAULT_TIERS` at `manifest.json:84`).
- **How tags interact with tiers.**
  - Agent tags are kept as-is; the tag classifier is skipped for discovered agents (`runtime/policy/model-metadata-classifier.mjs:614-615, 643`).
  - Every predefined tag (49-78) except the public tier names (`bootstrap/reconcile-tag-tiers.mjs:10-13`) is an automatic tier. Agent models join it, and for agent providers the tier is created if missing (`reconcile-tag-tiers.mjs:261-330`; `auto-provisioner.mjs:701-709`).
  - `generic-agent` is one of these tags, so every agent without `capabilities.tags` lands in the `generic-agent` cascade.
  - `local-llm` is not a predefined tag. local-llm therefore joins no tier and is reachable only by its explicit id.
- **Mapping `fast` or `code` to a local model: yes, but it is manual.** Public tiers are never filled from tags. An admin edits the tier's children in the Soul Gateway dashboard (Explorer Settings → "Soul Gateway") or via the `/management/tiers` API (`management/tiers-route.mjs:1-17`; `dashboard/js/app.mjs:2636-2808`). This applies to the whole workspace; `LLMConfig.json` `defaults` is the per-client alternative.

## 4. Explorer integration

- **local-llm is enabled by default.** `EXP/manifest.json:11-29` lists `"local-llms/local-llm no-wait"` (28) and `"proxies/soul-gateway no-wait"` (24), and `repos.local-llms` clones the repo (30-35).
- **How plugins are loaded.** The `collect_ide_plugins` tool (`utils/server/tool-handlers.mjs:1212-1216`) calls `aggregateIdePlugins` (`utils/ide-plugins.mjs:364-607`).
  - It scans the workspace and `.ploinky/repos/*/&lt;agent&gt;/IDE-plugins/*/config.json` (560-577) whether or not the agent is enabled. Duplicates are dropped by agent directory name (425).
  - `config.json` fields: `pluginCategory:"application"`, `location` (e.g. `file-exp:toolbar`), `type`, `presenter`, `dependencies`, `toolbarModal`, `icon`.
  - Settings entries come from the manifest's `ideSettings` (294-360): `pluginKey` `&lt;agent&gt;/&lt;id&gt;`, then `settingsComponent` or `settingsUrl`, then `adminOnly`.
  - `locationOrder` sets the sort order (`utils/pluginUtils.core.js:125-131`).
  - `adminOnly` hides the entry from non-admins: toolbar filter at `web-components/pages/file-exp/file-exp-application-plugins.js:48`, route guards at `main.js:118, 316, 502`, and in the Settings modal (`web-components/modals/settings-modal/settings-agent-model.js:58-67`).
  - Explorer's `applicationPlugins` only works as a deny-list: an entry set to `false` hides a plugin (`pluginUtils.core.js:438-466`).
  - The plugin UI reaches its agent through `getClient('&lt;agent&gt;').callTool` (`LL/IDE-plugins/local-llm-tool-button/components/local-llm-dashboard/local-llm-dashboard.js:40-44`).
- **What a new agent needs to appear the same way:** its repo in Explorer's `repos`, an `enable` entry, `IDE-plugins/&lt;id&gt;/config.json`, manifest `ideSettings`, a unique agent name, and MCP tools for the dashboard.

## 5. The older repos

**llm-runtime** (2026-05-28 to 06-24)
- **Purpose:** role agents (`planning-local`, `relevance`, `language-detection`) sharing one in-container runtime: an MCP server and a proxy mapping port 9000 to MCP 9001, control 9002 and engine 8080.
  - It reads a Ploinky-mounted `/runtime/selected-architecture.json` plus an agent-owned `agent-models.json` (profiles → launcher candidates by priority and required accelerators).
  - Launcher scripts implement `describe`, `prepare`, `start`, `stop`, `status`.
- **Status:** dead. The only real launcher (llama.cpp CPU, in `base-local`) was removed on 06-18 "superseded by default-local-llm"; the remaining agents have only `fake-cpu` launchers, and the manifests use `profiles.ports`, which DS005 now rejects.
- **arm64 / GPU:** its schemas list `nvidia-cuda` and `linux/arm64`, but no GPU launcher was ever written.
- **Reusable:** the launcher `describe` schema (with `chat/embeddings/rerank` capabilities) and the profile/candidate priority model, which fits coder/fast/big.

**local-llm-architectures** (last commit 06-17)
- **Purpose:** a data-only catalog (9 architectures, images, JSON schemas). Ploinky core still consumes it when a manifest sets `llmRuntime.enabled` (`PL/cli/sandbox/docker/llmRuntimeIntegration.js`, `llmArchitectureCatalog.js:12, 374-412`). Hardware detection maps aarch64 to arm64 and probes `nvidia-smi` and `nvidia-ctk` (`hardwareDetection.js:10-17, 89-124`).
- **Status:** the `nvidia-cuda-arm64` entry is marked experimental. It uses `gpus:"all"`, `ipc:"host"` and 8 GB memory, and points at `ghcr.io/ploinky/llm-runtime-nvidia-cuda-arm64:dev`, whose build context does not exist. The CPU Dockerfiles are placeholders (`tail -f /dev/null`).
- **Why it can't be used for GPU:** its policies conflict with today's Box GPU model, which grants the device `ploinky.local/gpu=all` via `containerSecurity.gpu` and rejects `--gpus` and host IPC (`PL/CLAUDE.md:19`).
- **Reusable:** only the hardware probes and the architecture-id naming convention.

**llm-runtime-cpu image**
- **What it is:** Node 24 plus a CPU-only llama.cpp b6412 `llama-server` build and the Hugging Face CLI.
- **arm64:** yes. CI (`publish-llm-runtime-cpu-image.yml`) runs on `ubuntu-24.04-arm` and defaults to `linux/arm64` with tag `cpu-arm64-smoke`. It is still listed as optional (`CIB/README.md:26-28`).
- **Reusable:** the native-arm64 CI runner and the build-from-source recipe. For GB10 it would need a CUDA 13 base and `-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=121` (I believe GB10 is sm_121; not checked here).

**Why `local-llms/local-llm` replaced them:** it is one GPU agent that installs and runs its runners itself (llama.cpp, ik_llama.cpp, Ollama, vLLM, TabbyAPI, LM Studio), with an admin dashboard, weight download on Run, discovery through a chatCompletions command, and GPU via the CDI grant. However, its image is amd64-only (`CIB/images/local-llm/Dockerfile:43`; CI publishes `linux/amd64`; CUDA 12.8, compute capabilities 86/89). So it cannot use the GPU natively on a DGX Spark, which is the gap `dgx-local-agent` fills.

## Implications for dgx-local-agent

1. **Must declare `endpoints.chatCompletions.command`** with `supportsStream:true` and a large `timeoutMs` (local-llm uses 600000). Without a command, AgentServer runs the Achilles loop, which calls Soul Gateway itself.
2. **Multiple models need only `endpoints.models.command`; no Soul Gateway change.**
   - Use ids without `/`.
   - Return `contextWindow`, `maxOutputTokens`, `supportsTools` and `supportsVision` for each model.
   - The chat handler must dispatch on `request.model`.
   - The list can include only models that are ready: Soul Gateway disables missing ones within about 60 s and ignores an empty list.
3. **Tags need care.**
   - Set `capabilities.tags` (e.g. `["dgx-local"]`) to stay out of `generic-agent`.
   - Per-model predefined tags (`coding`, `reasoning`, `long-context`, `vision`) automatically put models into those tiers; use them on purpose.
   - Putting a model into `fast`/`code`/`plan`/`deep` needs an admin edit in the Soul Gateway Tiers UI. Alternatively, a Soul Gateway change could seed "local-first" tier children automatically.
4. **Reasoning needs a decision.** Soul Gateway strips `reasoning_effort` and `chat_template_kwargs` and drops `reasoning_content`. Either fix thinking behaviour per model inside the agent (e.g. `coder` without thinking, `big` with it), or patch `ploinky-agent-openai.backend.mjs` around line 596 to:
   - send a keep-alive during `delta.reasoning_content` / `delta.reasoning`;
   - forward more fields (or use the provider's `settings.extra_body`).
5. **Long contexts need longer timeouts.** Raise the Soul Gateway per-model `requestTimeoutMs` (default 120 s) so prefill of 100k+ tokens fits, and have the agent send `usage` in its last SSE chunk, since `stream_options` is not forwarded.
6. **Anthropic `/v1/messages` already works through the gateway**, using model `dgx-local/dgx-local-agent/coder`. A native agent endpoint would need changes in AgentServer, the Router's delegation surface and a new Soul Gateway backend. The alternative, an `httpRoutes` side door, bypasses the gateway's policies and logging.
7. **Embeddings and rerank need changes in four places:** a new manifest endpoint kind, an AgentServer route, a Router delegation surface, and `embed()` in the agent backend. The workaround is a manually configured `openai-api` provider.
8. **Explorer setup:**
   - Add the repo to Explorer's `repos` and `"&lt;repo&gt;/dgx-local-agent no-wait"` to `enable`.
   - Add IDE plugins with unique `id`s, `adminOnly:true` and a `locationOrder`, plus `ideSettings` with pluginKey `dgx-local-agent/&lt;id&gt;`.
   - Consider not enabling `local-llm` by default on arm64 hosts. I haven't checked how its amd64 image fails there.
9. **Build:** an arm64 + CUDA 13 image, reusing the arm64 CI runner pattern from `llm-runtime-cpu`. Request the GPU with `containerSecurity.gpu` plus `shmSize`, not the `llmRuntime` `gpus`/`ipc` policy.
