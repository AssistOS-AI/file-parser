---
name: same-branch-name-across-repos
description: "For work spanning several repos, use one identical branch name in every repo (user rule, 2026-09-28)"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 8bfd08cf-9225-4b6c-b766-b7917428a572
  modified: 2026-09-28T15:43:43.694Z
---

When a change spans several repositories, create its work branch under the same name in every repo. For the local-llm multi-arch plan that name is `local-llm-multiarch`, in ploinky, local-llms, container-image-builds and any other repo the plan touches.

**Why:** on 2026-09-28 the implementation session had created three differently named branches (`arm64-gpu-discovery`, `gpu-memory-unknown`, `local-llm-multiarch`), and the user asked for one name in all repos and for this to be remembered.

**How to apply:**
- Choose the name before creating the first branch.
- Use it in every repo; rename unpushed branches with `git branch -m`.
- Put the name in every implementation prompt or message to another session working on the change.
- Each repo's own branch rules still apply (for example, no `codex/` prefix in local-llms).
- Commit at each logical step, and push the shared branch (with upstream) to origin after every commit, so the work survives if pgx becomes unreachable. The owner asked for this on 2026-09-28; it was relayed by the owner's Mac session ("Anthropic Messages API server support"). This overrides the earlier "ask before pushing" wording for branch pushes. Merges, PRs, workflow dispatches and image publishing still need the owner. Put this rule in every prompt or relay written for sessions working on the change.

Related: [[dgx-local-agent-planning]]
