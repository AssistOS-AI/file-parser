# Claude Code Maintenance — file-parser workspace

The article *How Claude Code works in large codebases* (Anthropic, May 2026) recommends a configuration review every **3–6 months**, plus after major Claude model releases when performance feels plateaued.

## Cadence

- **Quarterly review:** every 90 days. Last reviewed: see `.claude/last-claude-review.txt`.
- **Triggered review:** any time a new major Claude model ships and you sense the setup isn't taking advantage of it (or is fighting it).
- **Triggered review:** any time a new top-level subrepo is added to `~/work/file-parser/`.

A SessionStart hook (`hooks/maintenance_check.mjs`) warns when the last review is >90 days old.

## DRI

Single Directly-Responsible Individual: **the workspace owner (currently `skutner`)**.

The DRI owns:

- `~/work/file-parser/CLAUDE.md` and every subrepo `CLAUDE.md`
- `~/work/file-parser/.claude/settings.json` (workspace permissions, hooks, MCP server registration)
- `~/work/file-parser/.claude/hooks/` (workspace-aware hooks)
- `~/work/file-parser/.claude/mcp-servers/ploinky-mcp/` (the workspace MCP server)
- `~/work/file-parser/.claude/plugin-marketplace/plugins/file-parser-workspace/` (the workspace plugin)

The DRI also decides:

- Which skills get added/removed from the workspace plugin
- Which subagents are exposed by the plugin
- The commit-attribution policy (currently: no AI attribution)

## Quarterly review checklist

Run this list every 90 days, or whenever the marker file is stale:

### CLAUDE.md health

- [ ] `find ~/work/file-parser -name CLAUDE.md -not -path '*/node_modules/*' -not -path '*/.ploinky/*' | xargs wc -l | sort -rn | head` — confirm no CLAUDE.md is >150 lines (excluding `achillesAgentLib/CLAUDE.md` which is intentionally larger as a subsystem map).
- [ ] Top-level `CLAUDE.md` still accurately maps subrepos (anything added/renamed?).
- [ ] Per-subrepo CLAUDE.md test commands still match the actual test entry points.
- [ ] DS-NNN spec references still resolve (try `find ... -name 'DSXX*'` for any cited spec id).

### Model compensation drift

The article warns: "instructions written for your current model can work against a future one." Look for rules that compensated for old-model limitations:

- [ ] Any "break refactors into single-file changes" or similar narrow-scope rules — these may now hurt with newer models.
- [ ] Any hooks that intercept tool calls Claude now handles natively (e.g., the original `p4 edit` example from the article).
- [ ] Any skills that wrap behavior Claude does well unaided.

### Plugin health

- [ ] `~/work/file-parser/.claude/plugin-marketplace/plugins/file-parser-workspace/skills/` — any skill stale relative to its subject matter? (e.g., `achilles_specs` if the AchillesAgentLib API shifted)
- [ ] `agents/` subagent definitions — still match current workflows?
- [ ] `hooks/commit_attribution_guard.mjs` patterns still catch the right strings?

### MCP server health

- [ ] `node /Users/danielsava/work/file-parser/.claude/mcp-servers/ploinky-mcp/index.mjs` still loads (smoke test in `~/work/file-parser/.claude/mcp-servers/ploinky-mcp/`).
- [ ] Tools still produce useful output (run `ds_spec_lookup`, `skill_by_name` manually).

### Hooks health

- [ ] All hooks fire without errors: trigger SessionStart with `cd ~/work/file-parser/ploinky && claude` and check the context block prints.
- [ ] Lint hook still emits sensible reminders for the current convention set.

### Cleanup

- [ ] Any new duplicate `.ploinky/repos/` trees? Add to `permissions.deny` and delete via `find -delete`.
- [ ] Any new `.bak` files in `~/.claude/`? Remove.

### After the review

- `date +%Y-%m-%d > ~/work/file-parser/.claude/last-claude-review.txt` to reset the marker.
- Add a one-line note to the bottom of this file documenting what changed.

## Review log

- **2026-05-15** — Initial setup. Implemented all 9 phases from the *Claude Code at scale* article plan. Marker initialized.
