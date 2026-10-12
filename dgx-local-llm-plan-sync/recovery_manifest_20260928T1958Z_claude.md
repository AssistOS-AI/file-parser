# Recovery manifest: pgx-research outage, 2026-09-28

Written by the Mac mirror session at about 20:00Z, from local data only. pgx was unreachable while this was written.

## Outage evidence

| Time (UTC) | Evidence |
|---|---|
| 19:54:43 | Last successful Phase 0 sync by the watch (the watch's `phase0_synced_at`, 22:54:43 +0300) |
| 19:54:58 | Last successful access reported by Codex |
| about 19:55 | Codex's bounded probe times out; the watch records `ssh_failures: 2` at 19:57 |
| 19:57:28, 19:57:41, 19:57:55 | Three bounded probes from this Mac: `ssh: connect to host pgx port 22: Operation timed out` (8 s each). `nc -z pgx 22` is also unreachable. |
| 19:55:11 | Desktop app: implementer `lastActivityAt`, `remoteControlState: "on"`. The app's status may be stale. |

**Not taken:** no continuation launched (Codex is the failover launcher), no pushes, and no remote or unrelated workload touched.

## Frozen copy of everything mirrored

- **Frozen copy:** `dgx-local-llm-plan-sync/outage-freeze-20260928T1957Z/` (262 MB) holds `phase0/`, `transcripts/`, `remote-memory/`, `repos/` (ref states and WIP generations) and `remote-plans/` (with `.history`), as they were at about 19:57Z.
- **Checksums:** `outage-freeze-20260928T1957Z.sha256` has 505 file hashes.
- **Why:** the live mirror directories are kept current by the watch (`rsync --delete` for Phase 0). The freeze keeps this state even if pgx comes back different.

**Backup refs** at the current tips, one in each local repo:
- ploinky: `refs/outage-20260928T1957Z/local-llm-multiarch` → `338a3c56`
- local-llms: the same ref → `70047bd7`
- container-image-builds: the same ref → `afd94156`

## Repositories: branch `local-llm-multiarch`

All three agree across the pgx dev clone (last ref sync), this Mac's `pgx/*` ref, this Mac's local branch, `origin/*`, and GitHub (`git ls-remote`, checked about 19:58Z).

| Repo | Tip (full) | Last ref sync (+0300) | On GitHub |
|---|---|---|---|
| ploinky | `338a3c567391cdc3004daa88d1e0ad16436bfe8d` | 22:33:27 | yes, equal |
| local-llms | `70047bd70b1cf97688a93e29e1882215f01ac081` | 22:41:23 | yes, equal |
| container-image-builds | `afd94156f766c2ac8215a06c78d257b40506195e` | 19:43:25 | yes, equal |

- **local-llms history:** includes the approved message-only reword (`d68c70f→104ecee`, `c22c7ab→70047bd`), validated here.
- **Old tips:** reachable through `refs/supervision/pre-message-reword-20260928T1935` and Codex's bundle.

## Uncommitted work in the dev clones: verified WIP generations

| Repo | `wip/current` | State | Recorded at (+0300) | Best-effort |
|---|---|---|---|---|
| ploinky | `gen-20260928T193441-765` | clean | 19:34:41 | none |
| local-llms | `gen-20260928T222957-961` | clean | 22:29:57 | none |
| container-image-builds | `gen-20260928T194215-484` | clean | 19:42:15 | none |

- **Clean at last contact:** each dev clone's work hash was polled until about 19:54Z and did not change after these clean generations. So all three repos had **no uncommitted work in the dev clones** at last contact.
- **Earlier dirty generations** remain under `repos/local-llms/wip/gen-*`, for example `gen-20260928T211820-449`, which was restore-verified live against pgx at 21:18.
- **Not in repo WIP:** engineering's quiet-gate repair was in `/home/research/phase0/tools`; see the next section.

## Phase 0 tools: which versions are mirrored

The last Phase 0 sync was 19:54:43Z. mtimes are pgx-local times, +0200.

| File | sha256 (prefix) | mtime | Status |
|---|---|---|---|
| `quietgate.py` | `d1c59c22` | 21:46:58 | **v6, installed: the defective gate** (unbounded lock wait, late pass) |
| `quietgate.py.v7tmp` | `0a7b98a9` | 21:52:50 | **v7 repair, work in progress**, not installed. It uses a monotonic, bounded design according to the reported intent; I have not verified its content against the requirement. |
| `attribution.py` | `bf903041` | 21:47:11 | v6, installed |
| `attribution.py.v7tmp` | `5bbb833e` | 21:52:44 | v7 work in progress, not installed |
| `test_quietgate.py` | `30fa4be1` | 21:53:38 | new tests for the repair (the latest mirrored version) |
| `serve_check2.py` | `c00de363` | 21:47:11 | v6 (`HARNESS_VERSION = 6`) |
| `followup-reruns.sh` | `8015dd3a` | 21:47:44 | v6 |
| `stop_latency.py` | `7d3b7f4e` | 21:46:15 | unchanged |
| `memory_validity.py` | `d65b54f3` | 21:48:06 | rule 3 |

**At risk:** anything edited in `phase0/tools` after 19:54:43Z. Among it, possibly a later `.v7tmp` or an installed v7, which the implementer's transcript suggests was 19:52–19:53Z work with tests waiting on `.memlock`.

## Phase 0 results

- **Mirrored:** 260 files under `phase0/results` (243 MB with logs and tools).
- **In progress at last contact:** `qwen-c256k-np1-mtpoff-cram1-r1`. Its `-mem.csv`, `-attr.jsonl` and `-server.log` were last mirrored at 19:54:34–19:54:42Z, and there is **no final result JSON**, so treat it as incomplete.
- **Last completed:** `qwen-c128k-np4-mtpoff-cram1-r1` (result JSON at 19:51:59Z).
- **Also mirrored:** `memory-validity.json` and `attribution-check.json` (both 19:48:06Z), and `logs/memlock.log` and `logs/followup-resume.log` (19:51–19:52Z).
- **Size limit:** the mirror is approaching its 300 MB total guard (243 MB), because of the large `-attr.jsonl` files. On reconnect, a PHASE0_SYNC_FAIL may appear. If so, the frozen copy remains.

## Plans and reports

| File | Local mtime (+0300) | Notes |
|---|---|---|
| `local-llm-multiarch-plan.md` | 22:46:40 | sha256 `3f6c1d10…`, the current plan (§9 item 10) |
| `local-llm-multiarch-implementation-log.md` | 22:48:06 | sha256 `edb14cd9…` |
| `phase0-followup-data-quality_codex.md` | 22:52:15 | revision 5 plus 5d and 5e (the quiet-gate defect) |
| `local-llm-workspace-reuse-recheck_codex.md` | 21:51:27 | the **first** C12 recheck (of `d68c70f`) |

**Second C12 recheck report (of `70047bd`): NOT mirrored.** No such file had appeared in `plans/` by the last sync. The progress Codex describes, with F1–F4 fixed and one minor cancellation-result gap remaining, exists only in Codex's own session.

## Claude transcripts, full copies

| Session | Local copy size | Last record | Mirrored at (+0300) |
|---|---|---|---|
| implementer `a519e4b1…` | 11,009,026 B | 19:52:50.580Z | 22:53:30 |
| review/orchestrator `8bfd08cf…` | 10,286,589 B | 19:52:30.474Z | 22:53:30 |
| planning `e95c870c…` | 2,496,721 B | 12:32:35.985Z | idle since then |

**Gap:** the implementer's activity from 19:52:50Z until at least 19:55:11Z (per the app) is not mirrored.

## For the failover launcher

A continuation on this Mac can start from the verified tips above. The branches are clean and there is no repo WIP to apply. Use a worktree, so this Mac's checkouts stay as they are:

```bash
git -C /Users/danielsava/work/file-parser/local-llms worktree add ../local-llms-continuation local-llm-multiarch
```

- **NVIDIA-only gates stay pending:** the matrix, the reruns, stop latency and Spark acceptance need GB10.
- **Not needed for code work:** the v7 quiet-gate files are GB10 tooling.
