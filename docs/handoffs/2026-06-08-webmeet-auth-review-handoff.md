# WebMeet Auth Regression Review Handoff

Date: 2026-06-08

This handoff is for reviewing the WebMeet authentication bugs fixed across Ploinky and AssistOSExplorer. It is written for a fresh Claude Code session with access to the same multi-repo workspace.

## Workspace Context

The workspace root is:

```text
/Users/danielsava/work/file-parser
```

Relevant repos:

```text
/Users/danielsava/work/file-parser/ploinky
/Users/danielsava/work/file-parser/AssistOSExplorer
```

Fresh local deployment used for validation:

```text
/Users/danielsava/work/testExplorerFresh
```

Workspace instructions:

```text
/Users/danielsava/work/file-parser/CLAUDE.md
/Users/danielsava/work/file-parser/ploinky/CLAUDE.md
/Users/danielsava/work/file-parser/AssistOSExplorer/CLAUDE.md
```

Important policy from the workspace instructions: do not add AI/tool attribution to commits, comments, release notes, or metadata.

## Commits To Review

Ploinky:

```text
cd4488d Derive user auth info from router request actor
```

AssistOSExplorer:

```text
eaa8825 Align shared invocation auth identity derivation
```

Both commits were pushed to their respective remotes on 2026-06-08.

## User-Visible Bug

After a fresh redeploy in:

```text
/Users/danielsava/work/testExplorerFresh
```

clicking WebMeet in Explorer showed this browser toast:

```text
MCP error -32603: Access denied: authentication is required.
```

This was different from the earlier fixed error:

```text
MCP error -32600: Invocation rejected: PLOINKY_DERIVED_MASTER_KEY not configured
```

The newer error meant the Router was successfully invoking the WebMeet MCP tool, but WebMeet's own domain authorization could not find an authenticated principal.

## Root Cause

The Router now mints DS013-style Router Request JWTs with identity in `sub` and `actor`:

```json
{
  "typ": "router-request",
  "iss": "ploinky-router",
  "aud": "agent:AchillesIDE/webmeetAgent",
  "sub": "user:local:admin",
  "actor": {
    "kind": "user",
    "id": "user:local:admin",
    "roles": ["admin"]
  },
  "tool": "webmeet_room_list"
}
```

The generic `authInfoFromInvocation()` helper only populated `authInfo.user` from legacy `usr` or `user` claims. When the Router Request token only had `actor` and `sub`, WebMeet received an `authInfo` object with no top-level user or principal.

WebMeet then hit:

```text
AssistOSExplorer/webmeetAgent/lib/store/accessPolicy.mjs
assertAuthenticatedAuthInfo()
```

and threw:

```text
Access denied: authentication is required.
```

Fresh container logs confirmed the tool being invoked was `webmeet_room_list`, with Router identity represented as `sub: user:local:admin` and no legacy user claims.

## Files Changed

Ploinky runtime helper:

```text
ploinky/Agent/lib/invocation-auth.mjs
```

New regression tests:

```text
ploinky/tests/unit/invocationAuthInfo.test.mjs
```

AssistOSExplorer mirrored fallback helper:

```text
AssistOSExplorer/shared/invocation-auth.mjs
```

## Behavior Added

`authInfoFromInvocation()` now:

1. Keeps legacy `usr` and `user` claim support.
2. Detects Router Request user identity from `actor.kind === "user"` and `actor.id`.
3. Falls back to `sub` when it starts with `user:`.
4. Emits `authInfo.principalId`, for example `user:local:admin`.
5. Emits `authInfo.user.id` without the `user:` prefix, for example `local:admin`.
6. Emits a friendly local username for `user:local:admin`, for example `admin`.
7. Preserves `authInfo.invocation.actor` for downstream scope/audit logic.
8. Leaves agent callers on the existing `authInfo.agent` path.

The concrete target shape for the WebMeet failing case is:

```json
{
  "principalId": "user:local:admin",
  "user": {
    "id": "local:admin",
    "username": "admin",
    "email": "",
    "roles": ["admin"]
  },
  "invocation": {
    "subject": "user:local:admin",
    "actor": {
      "kind": "user",
      "id": "user:local:admin",
      "roles": ["admin"]
    },
    "tool": "webmeet_room_list"
  }
}
```

## Verification Already Run

Ploinky focused tests:

```bash
cd /Users/danielsava/work/file-parser/ploinky
node --test tests/unit/invocationAuthInfo.test.mjs tests/unit/invocationAuth.test.mjs tests/unit/routerRequestJwt.test.mjs tests/unit/agentServerSessionLifecycle.test.mjs tests/unit/httpServiceInvocation.test.mjs
```

Result:

```text
37 pass
```

WebMeet focused tests:

```bash
cd /Users/danielsava/work/file-parser/AssistOSExplorer
node --test webmeetAgent/tests/unit/tagged-research-chat.test.mjs webmeetAgent/tests/unit/profile-avatar-events.test.mjs webmeetAgent/tests/unit/webmeet-room.test.mjs
```

Result:

```text
73 pass
```

Fresh deployment validation:

```bash
cd /Users/danielsava/work/testExplorerFresh
git -C .ploinky/repos/AchillesIDE pull --ff-only
ploinky reinstall webmeetAgent
```

Important deployment detail: `ploinky restart webmeetAgent` reused the existing staged `/Agent` runtime directory and did not pick up the changed Ploinky helper. `ploinky reinstall webmeetAgent` was needed to restage `/Agent/lib/invocation-auth.mjs`.

Direct MCP smoke against the reinstalled WebMeet container returned:

```json
{
  "ok": true,
  "rooms": 0,
  "canManageRooms": true
}
```

That smoke exercised AgentServer secure-wire verification plus WebMeet's `webmeet_room_list` domain authorization path.

## Review Focus

Please review for correctness and security, especially:

1. Whether deriving `authInfo.user` from `actor.kind === "user"` and `sub: user:*` is the right compatibility boundary.
2. Whether `authInfo.principalId = user:<id>` plus `authInfo.user.id = <id>` is compatible with WebMeet, DPU, GitAgent, and future agents.
3. Whether role propagation from `actor.roles` should be accepted as-is because the Router Request JWT is router-signed and audience-bound.
4. Whether legacy `usr/user` claims should override, merge with, or be constrained by `actor/sub`.
5. Whether `user:local:admin` mapping to username `admin` is sufficiently narrow and does not accidentally grant admin for unrelated identities.
6. Whether guest actors should remain unauthenticated in this helper, or need a distinct `authInfo.guest` shape in a follow-up.
7. Whether the fallback copy in `AssistOSExplorer/shared/invocation-auth.mjs` should remain duplicated or be replaced by a single canonical imported helper.
8. Whether additional tests are needed for agent actors, guest actors, malformed actors, and conflicting legacy claims.

## Known Non-Issues From This Fix

This fix does not change Router token minting, AgentServer secure-wire verification, MCP policy filtering, or WebMeet room ACL rules. It only normalizes the verified Router Request identity into the auth shape that agents already expect.

This fix does not require `PLOINKY_DERIVED_MASTER_KEY`. The current per-agent secure-wire model uses `PLOINKY_AGENT_SECRET` for Router Request JWT verification.

This fix does not edit `.agents` or any Ploinky-managed `.ploinky/repos` source as canonical code.

