---
name: runtime_invariants
description: Ploinky + Achilles runtime invariants for the file-parser workspace. Load before work on router/auth/secure-wire/guest-mode/manifests/MCP/HTTP services/WebChat/file access/logs/runtime config, before changes in ploinky/, AssistOSExplorer/, copilot-agents/, or proxies/soul-gateway/ that affect runtime boundaries, and before authoring DS-NNN specs.
when_to_use: Trigger on changes or reviews involving Ploinky routing, authentication, secure-wire invocation, guest sessions, MCP, manifest-declared HTTP services, WebChat, uploads, files, secrets, logs, runtime isolation, Achilles skills, provider relays, or cross-agent invariants.
---

# Runtime Invariants - Ploinky + Achilles + Soul Gateway

Use this skill as the compact runtime guardrail set for the workspace. It
summarizes the current contracts in:

- `ploinky/docs/specs/DS005-routing-and-web-surfaces.md`
- `ploinky/docs/specs/DS011-security-model.md`
- `AssistOSExplorer/docs/specs/DS06-ploinky-runtime-invariants.md`
- `copilot-agents/docs/specs/DS002-ploinky-runtime-invariants.md`
- `proxies/soul-gateway/docs/specs/DS001-DS003`

If a task depends on exact wording, read the relevant DS file. This skill is a
working checklist, not a replacement for the specs.

## Router and Web Surfaces

- Browser surfaces, first-party MCP calls, delegated MCP calls, uploads, blobs,
  and manifest-declared HTTP services enter through the Ploinky router. Direct
  agent ports are implementation details even when bound to localhost.
- WebChat is a generic transport. It must not hardcode optional provider agent
  ids, backend tags, MCP tool names, or domain-specific dispatch. Provider
  routing belongs to the selected chat agent or its skills.
- `@word` in WebChat is ordinary chat text unless the WebChat-owned file
  suggestion provider handles it. Do not turn arbitrary `@provider` text into
  framework dispatch.
- `forward-envelope=1` lets WebChat pass sanitized references and a short-lived
  router invocation token to the selected chat agent. References must stay
  workspace-relative and must reject absolute paths, traversal, NUL bytes, and
  reserved secret-file names.
- First-party browser surfaces rely on router auth/session handling. Surface
  token shortcuts are legacy-only where explicitly documented.

## HTTP Services

- HTTP services must be declared in the owning agent `manifest.json`; do not add
  product-specific service paths in Ploinky core.
- Declarations define the external prefix, internal prefix, and auth mode:
  `none`, `guest`, or `protected`.
- `auth: "none"` intentionally has no router identity. Use it only with an
  explicit DS decision.
- `auth: "guest"` follows guest policy and may use `forceGuest: true` to ignore
  an existing login and mint a service-scoped guest identity.
- `auth: "protected"` must establish an authenticated router identity before
  proxying. The router strips caller-supplied Ploinky identity headers and
  regenerates authoritative identity metadata for protected or guest services.
- `x-ploinky-auth-info` is not a secure grant by itself. A service may trust it
  only when it arrived through the declared router service route; guest services
  must also validate the router-issued invocation token and guest role/scope.
- Long-lived HTTP service state is ephemeral unless persisted through the
  agent's data directory, a declared volume, BacklogManager, DB skills, or
  another documented store.

## MCP and Secure Wire

- MCP servers run inside agent containers/sandboxes. Agents declare MCP in their
  manifests; the router proxies under `/mcps/<agent>/mcp` and `/mcp/<agent>/mcp`.
- Executable tool calls, resource reads, and task-status reads require
  router-minted invocation JWTs. Tool listing may be visible without a grant, so
  do not put secrets in tool metadata.
- Delegated agent calls must re-enter through the router with
  `X-Ploinky-Caller-JWT`; do not invent bearer tokens, client secrets, or custom
  caller headers around secure wire.
- Invocation JWTs are audience, tool, body-hash, scope, user, expiry, and replay
  bound. Forward exactly the canonicalized tool arguments that were signed.
- Ploinky route authentication identifies the caller, but agents still own
  domain authorization. Sensitive actions must check verified user/agent
  identity, roles, scopes, target resource, workspace path, and local policy.
- The installed-agent index is discovery, not authorization.

## Keys and Secrets

- `PLOINKY_MASTER_KEY` is the workspace root key. Treat it as high-trust host
  secret material; never inject it into agent runtimes.
- Agents receive `PLOINKY_DERIVED_MASTER_KEY`, the HKDF-derived agent runtime
  root. It signs/verifies invocation JWTs and derives Ploinky-owned or
  agent-owned generated secrets.
- Agent-owned generated secrets must use manifest `derive: "derived-master"`,
  `{{derivedMasterSecret:NAME}}`, or an equivalent documented helper with
  domain-separated labels for repo, agent, and secret name. Do not create random
  persistent generated secrets for workspace-owned agent credentials.
- External provider credentials remain explicitly configured secrets.
- `.ploinky/.secrets` and `.ploinky/passwords.enc` are encrypted stores. Use
  `ploinky var`/documented APIs; do not append plaintext secret files.
- Non-sensitive topology and runtime config such as hostnames, realms, public
  URLs, ports, and profile-specific defaults should live in profiles so a fresh
  workspace can start without manual variable setup. Secrets stay secret-owned.

## Guest Mode

- Guest access is scoped to the declaring route shape. Manifest-level
  `guest: true` exposes the agent as a guest agent; HTTP-service `auth: "guest"`
  exposes only the declared service prefix.
- Guest JWTs carry guest identity, role, expiry, and optional service scope.
  Agents must enforce limitations from roles/scopes and cannot self-promote a
  guest into an authenticated user.
- Product-specific public paths belong in manifests, not hardcoded router logic.

## Runtime Isolation and Volumes

- Containers, bubblewrap, and Seatbelt are defense in depth for
  operator-enabled code, not hostile multi-tenant isolation.
- Enabled agents are trusted participants in one local workspace. The current
  shared-HMAC invocation model does not provide non-repudiation between
  mutually hostile agents.
- Lifecycle hooks are trusted host/runtime code.
- Manifest volumes and runtime resources are explicit grants. Host paths for
  persistent state should stay under `.ploinky/`; durable service data belongs
  under `.ploinky/data/...`, generated runtime inputs under `.ploinky/agents/...`.
- Container-published ports should default to localhost unless a manifest/profile
  intentionally exposes a wider bind. Exposing the router port beyond the local
  machine changes the security model and needs TLS/proxy/network controls.

## Files, Uploads, and Static Content

- Workspace file access must be confined to the workspace root, agent root,
  declared data directory, or explicit runtime volume. Reject absolute caller
  paths, traversal, NUL bytes, and symlink escapes.
- WebChat uploads and file suggestions are scoped to the current session upload
  directory and must not expose sibling sessions. This is a UX scope, not a
  security boundary between hostile sessions.
- Browser responses must not leak host absolute paths.
- Do not place secrets, tokens, credentials, transcripts, screenshots, DOM
  dumps, or hidden policy text in static roots, plugin assets, docs, fixtures,
  logs, or screenshots.

## Logs and Diagnostics

- Default logs and user-facing errors must not expose secrets, cookies, bearer
  tokens, invocation JWTs, API keys, raw prompts, materialized resources,
  command stdin, base64 payloads, screenshots, DOM dumps, hidden policy text, or
  internal payloads.
- Detailed diagnostics belong behind explicit debug flags and still require
  redaction before persistence.
- Visitor-facing output should be clean text or the endpoint's documented JSON,
  not internal traces.

## LLM and Search Access

- Request-time LLM inference goes through `ploinky/node_modules/achillesAgentLib`
  (`LLMAgent` or documented helpers). Direct vendor HTTP from an agent runtime
  is a violation.
- Soul Gateway is the only sanctioned bypass, and only for lifecycle probes or
  model discovery, not direct response generation.
- Search providers exposed through Soul Gateway are reached via
  `achillesAgentLib`; browser/headless search execution is owned by the search
  backend agent, not Ploinky core.

## Achilles Skills

| Type | File | Purpose |
|---|---|---|
| Anthropic-style | `skill.md` | Pass-through skill instructions |
| Code | `cskill.md` | Callable JavaScript/MJS skills |
| Dynamic codegen | `dcgskill.md` | LLM-generated transient code |
| MCP | `mskill.md` | MCP tool wrappers |
| Orchestrator | `oskill.md` | Multi-step skill coordination |
| DB-table | `tskill.md` | Table-row skills against a DB |

Skill subsystem details live in
`ploinky/node_modules/achillesAgentLib/docs/specs/DS006-CodeSkillsSubsystem.md`
and `DS007-Subsystems.md`.

## Framework Code Rules

- Ploinky framework code must not know optional provider ids, backend tags,
  agent-owned tool names, or catalog-specific policy.
- Cross-agent behavior belongs in manifests, plugins, selected chat agents,
  launcher skills, relays, or explicit configuration.
- If a change solves one agent's workflow by hardcoding behavior in the router
  or WebChat, move it back to an agent-owned contract.

## Browser-Use Specifics

- Interactive browser viewers must be manifest-declared protected HTTP services.
- Viewer ownership is derived from verified secure-wire/auth context. Viewer
  routes can use `x-ploinky-auth-info` only as router-provided service metadata,
  not as an arbitrary caller-supplied grant.
- Browser sessions that require login/OAuth/2FA/CAPTCHA must avoid logging
  credentials, cookies, localStorage/sessionStorage, auth callback URLs,
  screenshots, and DOM dumps.
- Router-relative viewer URLs may be returned internally; user-facing launcher
  text should render a full `http://` or `https://` URL using the public
  WebChat/router origin or a local `http://localhost:<port>` fallback.

## Deploy and Remote Ops

- Use GitHub Actions for deploy/update/destroy. SSH to production is read-only
  status/debug unless the user explicitly requests a state-changing operation.
- `skills.axiologic.dev` deploys through
  `AssistOSExplorer/.github/workflows/deploy-skills-explorer.yml` and must pass
  `PLOINKY_MASTER_KEY` through stop/update/start.
- After deploy, verify router health, public surfaces, container status, Ploinky
  status, and start logs.

## Validation Checklist

1. Runtime/auth/router/MCP/HTTP/file/log/manifest changes update the relevant DS
   spec and local docs in the same change.
2. Framework changes keep agent ids, backend tags, and agent-owned tools out of
   Ploinky core.
3. Agent code preserves router-mediated entry, secure-wire invocation, scoped
   guest behavior, explicit manifest services, workspace-confined storage,
   redacted logging, and domain authorization.
4. LLM access still goes through `achillesAgentLib`.
5. Run targeted unit tests. For Ploinky/Explorer workflow changes, also run the
   available fast/smoke tests or state why they were not run.
