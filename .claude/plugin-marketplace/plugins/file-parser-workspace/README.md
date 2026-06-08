# file-parser-workspace

Workspace plugin for `~/work/file-parser`. Consolidates the 8 Achilles skill-build skills (previously duplicated across `file-parser/.claude/skills/`, `AssistOSExplorer/.claude/skills/`, and `ploinky/.claude/skills/`), three workspace subagents, and a `commit_attribution_guard` hook.

## Skills

- `achilles_specs` — AchillesAgentLib integration, dependency resolution, runtime config, coding-style additions.
- `antropic_skill_build` — Build Anthropic-style passthrough skills.
- `article_build` — Rebuild research-article outputs from plans + assets + bibliography.
- `cskill_build` — Build code skills (`cskill.md`).
- `dgskill_build` — Build dynamic code generation skills (`dcgskill.md`).
- `gamp_specs` — General Architecture Method Pattern specs.
- `oskill_build` — Build orchestrator skills (`oskill.md`).
- `review_specs` — Review existing DS specs against contract conventions.
## Subagents

- `ploinky-router-tracer` — Trace a request from router → auth → secure-wire → agent.
- `ds-spec-finder` — Locate DS-NNN spec files by topic.
- `achilles-skill-author` — Draft a new skill (cskill/oskill/mskill/tskill/dcgskill) with correct schema.

## Hooks

- `commit_attribution_guard` (PreToolUse on `git commit`) — Hard-blocks commits whose message contains AI/coding-agent attribution. Workspace policy is in `~/work/file-parser/CLAUDE.md`.

## Installation

This plugin is distributed via a local marketplace registered in `~/.claude/settings.json`:

```json
"extraKnownMarketplaces": {
    "file-parser-workspace-local": {
        "source": {
            "source": "directory",
            "path": "/Users/danielsava/work/file-parser/.claude/plugin-marketplace"
        },
        "autoUpdate": true
    }
},
"enabledPlugins": {
    "file-parser-workspace@file-parser-workspace-local": true
}
```

Once enabled, restart Claude Code. Verify with `/plugin list` and `/skills`.
