# file-parser-workspace

Workspace plugin for `~/work/file-parser`. Provides 4 Achilles skill-build skills, three workspace subagents, and a `commit_attribution_guard` hook.

## Skills

- `antropic_skill_build` — Build Anthropic-style passthrough skills.
- `cskill_build` — Build code skills (`cskill.md`).
- `dgskill_build` — Build dynamic code generation skills (`dcgskill.md`).
- `oskill_build` — Build orchestrator skills (`oskill.md`).

`achilles_specs`, `article_build`, `gamp_specs` and `review_specs` were removed on 2026-09-30. Their current versions come from [DocumentationSkills](https://github.com/AssistOS-AI/DocumentationSkills) as `achilles-specs`, `article-build`, `gamp-specs` and `review-specs`, installed once in the workspace hub `~/work/file-parser/.agents/skills/` and linked into every repository's `.agents/skills/` (and `.claude`).

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
