# Prompt For Claude Code

Use this prompt in a fresh Claude Code session from:

```text
/Users/danielsava/work/file-parser
```

Related handoff:

```text
/Users/danielsava/work/file-parser/docs/handoffs/2026-06-08-webmeet-auth-review-handoff.md
```

```text
Please review two pushed commits that fixed WebMeet failing to load after a fresh Explorer deployment.

Workspace root:
/Users/danielsava/work/file-parser

Detailed handoff document:
/Users/danielsava/work/file-parser/docs/handoffs/2026-06-08-webmeet-auth-review-handoff.md

First read the workspace instructions:
/Users/danielsava/work/file-parser/CLAUDE.md
/Users/danielsava/work/file-parser/ploinky/CLAUDE.md
/Users/danielsava/work/file-parser/AssistOSExplorer/CLAUDE.md

Important policy: do not add AI/tool attribution to commits, comments, release notes, changelogs, or metadata.

Commits to review:

Ploinky repo:
/Users/danielsava/work/file-parser/ploinky
commit cd4488d Derive user auth info from router request actor

AssistOSExplorer repo:
/Users/danielsava/work/file-parser/AssistOSExplorer
commit eaa8825 Align shared invocation auth identity derivation

Bug:
After a fresh redeploy in ~/work/testExplorerFresh, clicking WebMeet in Explorer showed:
MCP error -32603: Access denied: authentication is required.

Root cause found:
The Router now mints DS013-style Router Request JWTs with user identity in `sub` and `actor`, for example `sub: user:local:admin` and `actor: { kind: "user", id: "user:local:admin", roles: ["admin"] }`. The generic `authInfoFromInvocation()` helper only populated `authInfo.user` from legacy `usr` or `user` claims, so WebMeet received no top-level authenticated user/principal. WebMeet then rejected `webmeet_room_list` in `webmeetAgent/lib/store/accessPolicy.mjs` with `Access denied: authentication is required.`

Files changed:
ploinky/Agent/lib/invocation-auth.mjs
ploinky/tests/unit/invocationAuthInfo.test.mjs
AssistOSExplorer/shared/invocation-auth.mjs

Please review these changes as a code reviewer, not as an implementer unless you find a clear bug. Prioritize correctness, auth/security regressions, missing tests, and compatibility with WebMeet, DPU, GitAgent, and AgentServer secure-wire.

Specific questions to answer:

1. Is it correct to derive `authInfo.user` from `actor.kind === "user"` and `actor.id`, with fallback to `sub` when it starts with `user:`?
2. Is the resulting shape correct: `authInfo.principalId = "user:local:admin"`, `authInfo.user.id = "local:admin"`, and `authInfo.user.username = "admin"`?
3. Does accepting `actor.roles` from the router-signed Router Request JWT create any privilege escalation risk?
4. Should legacy `usr/user` claims override, merge with, or be validated against `actor/sub`?
5. Are agent callers still unaffected on `authInfo.agent`?
6. Should guest actors remain unauthenticated here, or should a separate guest shape be added?
7. Is duplicating the helper in `AssistOSExplorer/shared/invocation-auth.mjs` acceptable for now, or should this be centralized?
8. What extra tests, if any, are needed?

Commands already run successfully:

cd /Users/danielsava/work/file-parser/ploinky
node --test tests/unit/invocationAuthInfo.test.mjs tests/unit/invocationAuth.test.mjs tests/unit/routerRequestJwt.test.mjs tests/unit/agentServerSessionLifecycle.test.mjs tests/unit/httpServiceInvocation.test.mjs

Result: 37 pass.

cd /Users/danielsava/work/file-parser/AssistOSExplorer
node --test webmeetAgent/tests/unit/tagged-research-chat.test.mjs webmeetAgent/tests/unit/profile-avatar-events.test.mjs webmeetAgent/tests/unit/webmeet-room.test.mjs

Result: 73 pass.

Fresh deployment validation:
cd /Users/danielsava/work/testExplorerFresh
git -C .ploinky/repos/AchillesIDE pull --ff-only
ploinky reinstall webmeetAgent

Important: `ploinky restart webmeetAgent` reused the old staged `/Agent` runtime directory, so reinstall was needed to pick up the updated `ploinky/Agent/lib/invocation-auth.mjs`.

Direct MCP smoke against the reinstalled WebMeet container returned:
{"ok":true,"rooms":0,"canManageRooms":true}

Please provide review findings first, ordered by severity with file/line references. If there are no blocking issues, say that clearly and list residual risks or useful follow-up tests.
```
