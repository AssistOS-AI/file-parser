---
name: commit-message-no-agent-names
description: Commit messages must not name coding agents even indirectly, e.g. via review file names like *_codex.md
metadata:
  type: feedback
---
Commit messages, PR text and code comments must not mention Claude, Codex or other coding agents, and that includes file names such as `plans/local-llm-workspace-reuse-review_codex.md`. Refer to "the C12 review" or "the recheck" instead, and scan every message before committing (`git log -1 --format=%B | grep -iE 'claude|codex|anthropic|co-authored|generated'`).

**Why:** the user's global rule (commit-attribution) forbids any AI/agent mention; two pushed local-llms commits (d68c70f, c22c7ab, 2026-09-28) broke it by citing `_codex.md` file names, and fixing published history needs coordination.

**How to apply:** check before `git commit`, not after the push. Related: [[dgx-host-tooling]].
