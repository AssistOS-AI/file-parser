# Workspace Map

Multi-repo checkout for Ploinky, AssistOSExplorer, Soul Gateway, and adjacent agent work. Each top-level dir is its own repo or subproject; read its local `AGENTS.md` before editing.

The file-parser product documentation starts at `docs/index.html`. Its contracts are in `docs/specs/`, including `DS001-coding-style.md` and `DS003-main-behavior.md`. The `process_documents` entry point in `file-parser-agent/` emits Markdown; its separate LLM helper is not called by that entry point. Sibling repositories retain their own documentation and runtime contracts.

`AGENTS.md` is the single instruction file in this workspace and in every repo under it. Claude Code and Codex both load it natively. Claude Code also loads nested `AGENTS.md` files on demand; Codex reads only from its git root down to the working directory, so always read the target subrepo's `AGENTS.md` before editing there. Do not add `CLAUDE.md` files; personal Claude Code policy lives in `~/.claude/CLAUDE.md`.

## User response preference

| Preference | Instruction |
| --- | --- |
| List formatting | Avoid bullet-point lists in assistant responses. Prefer tables when structured information is useful. |

## Top-level layout

- `ploinky/` — Ploinky runtime, CLI, router, agent gateway. Agents start here as containers. Source of truth for routing, secure-wire JWTs, manifests, and the `ploinky-proxy` acceptance gate. See `ploinky/AGENTS.md`.
- `AssistOSExplorer/` — Ploinky Explorer + coupled agents (`explorer`, `dpuAgent`, `gitAgent`, `soplangAgent`, `tasksAgent`, `emailAgent`, `userPersistoAgent`, `workspaceMonitorAgent`, `multimedia`, `webmeetAgent`, `webmeetScribeAgent`, `webmeetStt`, `liveKitServerAgent`, `webAssist`). See `AssistOSExplorer/AGENTS.md`.
- `AchillesCLI/` — RoboTeam workspace robot and copilot agent. See `AchillesCLI/AGENTS.md`.
- `OnlyOfficeAgent/` — Extracted public Ploinky OnlyOffice Document Server agent (`OnlyOfficeAgent/onlyOffice`); installed by Explorer's manifest and disabled by default. See `OnlyOfficeAgent/AGENTS.md`.
- `UmamiAgent/` — Read-only Umami analytics agent (`UmamiAgent/umamiAgent`). See its `AGENTS.md`.
- `proxies/soul-gateway/` — Soul Gateway, the local LLM hub that runs as a Ploinky agent. No longer deployed at `soul.axiologic.dev`. See `proxies/AGENTS.md`.
- `local-llms/` — The `local-llm` Ploinky agent's glue and hardware limits (container memory/CPU budget, MPS GPU share). The engine (controller, runners, downloader, catalog schema) lives in `Ploinky-Worker/lib/local-llm`, at the commit pinned in `local-llms/local-llm/package.json`. See `local-llms/AGENTS.md`.
- `Ploinky-Worker/` — `AssistOS-AI/Ploinky-Worker` (GPL-3.0), the `pworker` standalone server and the local-llm engine library. See its `AGENTS.md`.
- `container-image-builds/` — Central Docker Hub image build definitions and publishing workflows. `sources/` holds pinned build-source clones; do not edit them.
- `copilot-agents/` — Local Copilot provider agents and AchillesCLI-owned consumer integrations. See `copilot-agents/AGENTS.md`.
- `DocumentationSkills/` — Portable documentation skills catalog. Selected skills are copied into the workspace `.agents/skills/`, which subrepos link to from their own `.agents/skills/` and `.claude/skills`. See `DocumentationSkills/AGENTS.md`.
- `Gatekeeper/` — Separate repository; see its `README.md`.
- `file-parser-agent/` — Standalone file-parsing MCP agent (part of this workspace repo).
- `website/` — Static site assets. See `website/AGENTS.md`.
- `evidence/` and `dgx-local-llm-plan-sync/` — Frozen evidence snapshots. Never edit them.

## Critical cross-repo invariants

- **Request-time LLM inference must route through `ploinky/node_modules/achillesAgentLib`.** Direct vendor HTTP is only permitted for Soul Gateway lifecycle probes and model discovery. See `proxies/AGENTS.md` and `AssistOSExplorer/AGENTS.md`.
- **AchillesAgentLib lives under `ploinky/node_modules/`** but is the canonical shared runtime for every agent. Treat its tree as load-bearing source, not a transient dependency. See `ploinky/node_modules/achillesAgentLib/AGENTS.md`.
- **Skill families:** code skills (`cskill.md`), dynamic-code skills (`dcgskill.md`), orchestration skills (`oskill.md`, which can expose Ploinky agents through `Allowed Agents`), and DBTable skills (`tskill.md`). They are specified together in `ploinky/node_modules/achillesAgentLib/docs/specs/DS009-subsystems.md`; built-in skills are in `DS013-built-in-skills.md`.

## Mandatory `ploinky-proxy` acceptance gate

Any new change on the `ploinky-proxy` branch of any repository in this workspace is incomplete until the exact candidate revisions have passed the fresh local Explorer deployment and three headless E2E gates defined in `ploinky/AGENTS.md`. This is a cross-repository release invariant, not a Ploinky-only convention. Do not merge, release, deploy onward, or report such a change complete without that evidence.

## Commit policy (applies to every repo here)

User-authorized commits may use the current branch, including `main` or `master`. Default-branch status alone does not require a separate approval.

- Never add `Co-Authored-By`, `Generated by`, tool-signature footers, or AI/coding-agent attribution to commits. Do not mention Claude Code, Codex, or any other agent in commit messages, PR descriptions, release notes, changelogs, code comments, or metadata.
- Commit authorship and attribution must identify only the human user. An agent may invoke commits, amends, merges, squashes, and reverts when explicitly authorized, provided it preserves the repository's configured human author and committer identity and adds no agent, tool, or AI attribution or metadata.

## Deploy and remote ops

- Codex sessions are authorized deployment operators for the environment and operation selected by the user. They may trigger tracked GitHub Actions workflows with `gh` and may use state-changing SSH, Ploinky CLI, container, Cloudflare, DNS, registry, and other remote operations needed to complete an explicitly user-authorized deploy, redeploy, destroy, recovery, or E2E task.
- This standing operator authority removes Codex-specific workflow and remote-shell prohibitions; it does not expand the selected target or operation. Before a destructive or externally visible change, positively identify the host, workspace, environment, branch, revisions, image identities, and rollback state. Never touch production or an unrelated workspace when the task selects QA or local deployment.
- The tracked Explorer deployment workflows, including `deploy-explorer-qa.yml` and `deploy-skills-explorer.yml`, are supported execution channels and may be invoked. Inspect the workflow at the dispatched revision, its inputs, target guards, secret prerequisites, and branch/fallback semantics first. If it conflicts with an explicit user invariant, use another authorized channel or update and verify the workflow through the normal reviewed change process.
- Do not deploy to `skills.axiologic.dev` unless explicitly asked. State-changing operations against any production host still require the user to have selected that production target; QA/local authorization does not imply production authorization.
- Soul Gateway is no longer deployed at `soul.axiologic.dev` and has no remote production deployment. Do not target that hostname or run the proxies Soul Gateway deploy/destroy/admin workflows unless the user selects a new target.
- Ploinky Box v5 may operate only an explicitly selected existing Cloudflare tunnel and zone through separate encrypted connector/API secret handles. Never create quick/new tunnels, source the retired plaintext tunnel environment, or mutate Cloudflare/DNS without explicit authorization and dedicated test resources; never expose secret values in docs, logs, fixtures, or artifacts.

## Working scope

- Keep edits scoped to one subrepo unless explicitly asked otherwise. Don't stage sibling repos, `node_modules/`, or unrelated workspace files.
- `.ploinky/repos/` inside any Ploinky workspace (created by Ploinky when it adds repositories) holds Ploinky-managed checkouts. Do not read or edit them; edit the originals.

## Quick navigation

- Ploinky internals or the `ploinky-proxy` acceptance contract → `ploinky/AGENTS.md`.
- An agent's specs → `AssistOSExplorer/<agent>/docs/specs/matrix.md` (Explorer itself: `AssistOSExplorer/docs/specs/matrix.md`).
- Shared agent primitives → `ploinky/node_modules/achillesAgentLib/docs/specs/`.
- Writing a new skill → the `cskill_build`/`oskill_build`/etc. skills (workspace plugin).

## Tooling

- **LSP:** Use the configured TypeScript/JavaScript `typescript-language-server` and Python `pyright` integrations when their plugin/tool availability is verified. Prefer LSP `find_references` / `goto_definition` over text search for symbol precision. Installed executables alone do not prove runtime activation.
