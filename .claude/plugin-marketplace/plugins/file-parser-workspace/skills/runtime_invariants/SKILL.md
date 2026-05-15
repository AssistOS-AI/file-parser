---
name: runtime_invariants
description: Ploinky + Achilles runtime invariants for the file-parser workspace. Load when working on router/auth/secure-wire/guest-mode/manifests/MCP/HTTP services/file access/logs, or when changes touch ploinky/, AssistOSExplorer/, or proxies/soul-gateway/.
when_to_use: Trigger on any change inside ploinky/, AssistOSExplorer/, or proxies/soul-gateway/ that touches routing, auth, guest sessions, MCP, HTTP services, manifests, file access, logs, runtime configuration, or cross-agent invariants. Also load before authoring DS-NNN specs in any subrepo.
---

# Runtime Invariants — Ploinky + Achilles + Soul Gateway

This skill consolidates the load-bearing runtime invariants spread across `DS06-ploinky-runtime-invariants.md` (per-agent), `DS005-routing-and-web-surfaces.md`, `DS011-security-model.md` (Ploinky), and `proxies/soul-gateway/docs/specs/DS001-DS003`. Load it on-demand instead of duplicating these rules into every CLAUDE.md.

## Router and entry

- Every request enters through the Ploinky router. Direct agent invocation from outside the router is not a supported deployment.
- Auth context flows in via secure-wire invocation JWTs. Agents do not parse cookies/headers directly; they read `ctx.identity` from the runtime.
- Public service routes are declared in `manifest.json`. Adding a route via code instead of manifest is a violation.

## Guest mode

- Guests have a **scoped** session: read-only access to public surfaces, no FS write, no DPU access, no secret read.
- Promoting a guest session to authenticated is a Ploinky-owned operation. Agents do not self-promote.

## MCP boundaries

- MCP servers run inside the agent container, never on the router host.
- Each agent declares its MCP server in `manifest.json`; the router proxies it under `/mcps/<agent>/mcp`.
- Tool names exposed via MCP must be agent-owned. The framework does not know about specific tool names — code in `ploinky/cli/` that references an agent-owned tool name is a smell.

## HTTP services

- Agents declare HTTP services in `manifest.json`. The router maps each to a path under `/<agent>/<service>`.
- Long-lived state inside an HTTP service handler is ephemeral; Ploinky can restart the agent at any time. Persist via `BacklogManager`, DB skills, or the agent's data directory.

## File access

- Workspace files are reached via `ASSISTOS_FS_ROOT` (Explorer) or the agent's `agentRoot`. **Never** hardcode absolute host paths.
- DPU `/Confidential` is encrypted at rest. Plaintext writes there are a violation.
- `.ploinky/.secrets` is encrypted. Use `ploinky var` with `PLOINKY_MASTER_KEY` set; never append/edit as a plaintext env file.

## Logs

- Tool calls, internal traces, raw payloads → debug-only. Toggle with `ACHILLES_DEBUG=true`.
- Visitor-facing output: clean conversational text (or strict JSON for endpoints that expect it).
- Never leak secrets, tokens, system prompts, or hidden decision traces to end users.

## LLM access (cross-repo invariant)

- **All request-time LLM inference goes through `achillesAgentLib`** (`/Users/danielsava/work/file-parser/ploinky/node_modules/achillesAgentLib`).
- Soul Gateway is the **only** sanctioned bypass, and only for lifecycle probes and model discovery, not for response generation.
- Direct vendor HTTP calls inside an agent runtime are a violation. Use `LLMAgent` from achillesAgentLib.

## Skill subsystems (memorize)

| Type | File | Purpose |
|---|---|---|
| Anthropic-style | `skill.md` | Pass-through skills, single prompt + tool list |
| Code | `cskill.md` | Code skills: callable JS/MJS with schema |
| Dynamic codegen | `dcgskill.md` | LLM-generated code at runtime |
| MCP | `mskill.md` | MCP tool wrappers |
| Orchestrator | `oskill.md` | Multi-step orchestration over other skills |
| DB-table | `tskill.md` | Table-row skills against a DB |

Each subsystem's contract is in `achillesAgentLib/docs/specs/DS006-CodeSkillsSubsystem.md` and `DS007-Subsystems.md`. Read those before writing a new skill subsystem.

## Framework code rules (ploinky/)

- The router and WebChat handlers don't know about specific agents. **Do not hardcode** agent ids, backend tags, or agent-owned MCP tool names in framework code.
- Cross-agent behavior lives in manifests/plugins/selected agents/explicit configuration.
- SOLID + DRY: framework responsibilities are narrow. If a feature solves an agent-specific problem, it doesn't belong in the router.

## Soul Gateway specifics (proxies/soul-gateway/)

- Production: `https://soul.axiologic.dev` (SSH `admin@45.136.70.141`, key `~/proxies_server_private_key.pem`).
- Expected production DB: `soul_gateway_v2`.
- Search providers are OpenAI-compatible models exposed by Soul Gateway. External callers reach them through `achillesAgentLib` the same way they reach LLM models. Search backends own provider-specific execution for both API search and headless-browser search.

## Deploy + remote

- Use GitHub Actions for deploy/update/destroy. SSH to production is read-only status/debug unless the user explicitly requests a state-changing op.
- `skills.axiologic.dev`: canonical deploy is `.github/workflows/deploy-skills-explorer.yml` (passes `PLOINKY_MASTER_KEY` through stop→update→start).
- After any deploy: verify local router health, public `/dashboard`, container status, Ploinky status, start logs.

## Validation checklist before claiming a runtime change is done

1. Does the change touch router/auth/MCP/HTTP services/file access/logs/manifests? If yes, the relevant DS spec must be updated in the same change.
2. Does the change keep agent ids/tags out of framework code? If no, refactor.
3. Does the change preserve the LLM-via-achillesAgentLib invariant? If no, justify in the PR.
4. For Explorer/Ploinky workflow changes: smoke via `tests/smoke/test_all.sh` and `tests/fast/test_all.sh`.
5. For agent code: the agent's `npm test` (or local test) passes.
