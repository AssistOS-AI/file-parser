---
name: dgx-host-tooling
description: "Tooling on the DGX Spark research host: gh at ~/.local/bin (authenticated), git push via gh's credential helper, ploinky path, registry and CUDA tools"
metadata:
  node_type: memory
  type: reference
  originSessionId: 8bfd08cf-9225-4b6c-b766-b7917428a572
  modified: 2026-09-28T15:55:24.254Z
---

Observed 2026-09-28 on the DGX Spark host (`/home/research/work`):
- GitHub CLI: `gh` 2.101.0 at `/home/research/.local/bin/gh` (it may not be on PATH), logged in as `skutner` (set up 2026-09-28 evening). Git uses it as the github.com credential helper (`gh auth git-credential`), so HTTPS pushes to AssistOS-AI repos work. The `local-llm-multiarch` branches are pushed with upstreams. Never print or read the token (`gh auth status` without its token lines is fine).
- Before that setup, api.github.com was used unauthenticated (60 requests/hour, shared across sessions). Authenticated `gh api` raises that limit. raw.githubusercontent.com and `https://github.com/<owner>/<repo>/releases/expanded_assets/<tag>` (lists assets with sha256) still work without auth.
- No AI attribution in commits or PRs (owner's rule): `~/.claude/settings.json` sets `includeCoAuthoredBy: false` with empty attribution, `~/.claude/rules/commit-attribution_codex.md` records the rule, and the dev clones have commit-msg hooks.
- `ploinky` is not on PATH; use `/home/research/work/ploinky/bin/ploinky` (e.g. `gpu status`, read-only).
- `skopeo` is installed (manifest/config inspection without pulling layers); `nvidia-ctk` 1.19.1 and CUDA 13.0 `nvcc` are on the host.
- Ploinky's `tests/unit/dependencyRuntimeKey.test.mjs` fails to load outside a Ploinky-started env (`PLOINKY_AGENTLIB_DIR` unset).

Related: [[dgx-local-agent-planning]]
