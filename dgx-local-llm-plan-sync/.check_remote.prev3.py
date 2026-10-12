#!/usr/bin/env python3
"""Poll the pgx-research Claude Code transcript for the dgx-local-llm planning
session and print one line per event worth re-syncing the local plan doc.

Silent when nothing changed. Emits:
  TURN_ENDED  - transcript grew, stayed flat for STABLE_POLLS polls, and the
                last main-thread record ends a turn (increment saved locally)
  MEMORY_CHANGED - the remote planning memory file changed
  PLANS_CHANGED  - a file in the remote plans/ dir was added, changed or
                   removed; already rsynced into remote-plans/ (old versions
                   kept under remote-plans/.history/)
  REPO_CHANGED   - an implementer dev clone's refs moved (a branch created,
                   moved, pushed or deleted, or the checked-out head); acted
                   on once the refs hold for STABLE_POLLS polls, which
                   uncommitted edits do not reset. Every dev-clone branch is
                   already fetched as pgx/<branch>; each non-default branch
                   has a local branch of the same name, created or
                   fast-forwarded (never moved when checked out here or
                   diverged). repos/<name>/state.md has the branch table
  REPO_WIP       - uncommitted work captured into an immutable generation
                   repos/<name>/wip/gen-*/ (wip.patch + wip.meta.json with the
                   base HEAD, times, skipped files and the patch sha256),
                   switched in via one atomic repos/<name>/wip/current
                   symlink. The work hash covers tracked diffs and untracked
                   file contents; captured every poll it changed (no
                   stability wait) and at least every WIP_FORCE_EVERY s while
                   dirty; published only if HEAD held during capture and the
                   patch applies to its base in a throwaway index. Notice at
                   most every WIP_EVENT_EVERY s per repo
  REPO_WIP_FAIL / REPO_WIP_RECOVERED - WIP_FAIL_REPORT_AFTER captures in a row
                   were not promoted (last good snapshot kept) / it recovered
  REPO_SYNC_FAIL - ref sync failed; reported once per ref state
  TURN_ENDED <name> - the same for the implementer / review session
  ORIGIN_PUSHED  - an implementer branch appeared or moved on GitHub; already
                   fetched locally as origin/<branch>
  REPO_UNPUSHED  - a pgx branch tip has not reached GitHub for UNPUSHED_AFTER s
  PHASE0_SYNC_FAIL - mirroring /home/research/phase0 (minus models, builds,
                   binaries and ollama-home) into phase0/ failed or would
                   exceed PHASE0_MAX_TOTAL (the mirror itself is silent)
  SSH_FAIL / MISSING / SHRUNK - the watch itself is broken; never stay silent

`--mark-synced SIZE` records that the local doc now reflects the transcript
up to SIZE bytes (optional MEMORY_SIG 'size:mtime'). `--status` prints the
state. With no arguments it runs a single poll.
Env SYNC_TRANSCRIPT_LOCAL / SYNC_MEMORY_LOCAL replace ssh with local files,
SYNC_PLANS_LOCAL replaces the remote plans dir, SYNC_REPO_REMOTE_ROOT /
SYNC_REPO_LOCAL_ROOT replace the dev-clone and local repo roots, and
SYNC_HOST / SYNC_STATE / SYNC_INCREMENTS / SYNC_PLANS_MIRROR /
SYNC_REPO_MIRROR / SYNC_PHASE0_LOCAL / SYNC_PHASE0_MIRROR redirect the rest
(self-tests).
"""
import json
import os
import hashlib
import shutil
import subprocess
import tempfile
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.environ.get("SYNC_STATE", os.path.join(HERE, "state.json"))
INCREMENTS = os.environ.get("SYNC_INCREMENTS", os.path.join(HERE, "increments"))
HOST = os.environ.get("SYNC_HOST", "pgx-research")
TRANSCRIPT = "/home/research/.claude/projects/-home-research-work/e95c870c-8d4a-46a7-bacf-21525480837e.jsonl"
MEMORY = "/home/research/.claude/projects/-home-research-work/memory/dgx-local-agent-planning.md"
PLANS = "/home/research/work/plans"
PLANS_MIRROR = os.environ.get("SYNC_PLANS_MIRROR", os.path.join(HERE, "remote-plans"))
STABLE_POLLS = 2
SSH_FAIL_LIMIT = 5
LOCAL_T = os.environ.get("SYNC_TRANSCRIPT_LOCAL")
LOCAL_M = os.environ.get("SYNC_MEMORY_LOCAL")
LOCAL_P = os.environ.get("SYNC_PLANS_LOCAL")
# Repos the implementer changes: dev clones on pgx, fetched into the local
# workspace repo of the same name through its `pgx` remote.
REPO_NAMES = ["ploinky", "local-llms", "container-image-builds"]
LOCAL_R = os.environ.get("SYNC_REPO_REMOTE_ROOT")
REPO_REMOTE_ROOT = LOCAL_R or "/home/research/dev"
REPO_LOCAL_ROOT = os.environ.get("SYNC_REPO_LOCAL_ROOT", os.path.dirname(HERE))
REPO_MIRROR = os.environ.get("SYNC_REPO_MIRROR", os.path.join(HERE, "repos"))
EMPTY_BLOB = "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"  # git hash-object of ""
WIP_FILE_LIMIT = 2 * 1024 * 1024
WIP_EVENT_EVERY = int(os.environ.get("SYNC_WIP_EVENT_EVERY", 1800))
WIP_FAIL_REPORT_AFTER = 3
WIP_FORCE_EVERY = int(os.environ.get("SYNC_WIP_FORCE_EVERY", 600))
WIP_KEEP_GENERATIONS = 5
# The implementer's Phase 0 results, mirrored silently.
LOCAL_P0 = os.environ.get("SYNC_PHASE0_LOCAL")
PHASE0_ROOT = LOCAL_P0 or "/home/research/phase0"
PHASE0_MIRROR = os.environ.get("SYNC_PHASE0_MIRROR", os.path.join(HERE, "phase0"))
# Not mirrored: model weights, builds and binaries, and Ollama's home (it
# holds Ollama's private key). Everything else is, file by file up to
# PHASE0_MAX_SIZE, unless the whole set would exceed PHASE0_MAX_TOTAL.
PHASE0_EXCLUDES = ["models", "ollama-models", "l1", "l2", "native", "ppl", "tbo",
                   "ollama", "dl", "ollama-home"]
PHASE0_MAX_SIZE = "50m"
PHASE0_MAX_FILE_KIB = 50 * 1024
PHASE0_MAX_TOTAL = 300 * 1024 * 1024
# Other pgx sessions whose turns are watched (name -> transcript). They start
# at their current size, advance on each ended turn, and are rsynced into
# transcripts/ so a takeover has them if pgx goes away.
SESSIONS_DIR = "/home/research/.claude/projects/-home-research-work"
LOCAL_S = os.environ.get("SYNC_SESSIONS_LOCAL_DIR")
EXTRA_SESSIONS = {
    "implementer": "a519e4b1-8c2d-41a5-a64d-18fad9d6ce30.jsonl",
    "review": "8bfd08cf-9225-4b6c-b766-b7917428a572.jsonl",
}
TRANSCRIPTS_MIRROR = os.environ.get("SYNC_TRANSCRIPTS_MIRROR", os.path.join(HERE, "transcripts"))
# GitHub: pushed implementer branches are fetched as origin/<branch>, and a
# pgx tip that stays unpushed longer than UNPUSHED_AFTER s is reported once.
ORIGIN_URL = os.environ.get("SYNC_ORIGIN_URL", "https://github.com/AssistOS-AI/{repo}.git")
ORIGIN_EVERY = int(os.environ.get("SYNC_ORIGIN_EVERY", 300))
UNPUSHED_AFTER = int(os.environ.get("SYNC_UNPUSHED_AFTER", 900))
# Full copies of all watched transcripts and their side dirs (subagents,
# tool results), refreshed every TRANSCRIPTS_EVERY s whatever the turn state.
TRANSCRIPTS_EVERY = int(os.environ.get("SYNC_TRANSCRIPTS_EVERY", 300))


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(s):
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(s, f, indent=1)
    os.replace(tmp, STATE)


def ssh(cmd, timeout=30):
    r = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", HOST, cmd],
        capture_output=True, timeout=timeout,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode(errors="replace").strip() or f"ssh exit {r.returncode}")
    return r.stdout


def stat_sizes():
    """Return (transcript_size or None, memory 'size:mtime' or None,
    sorted list of 'name:size:mtime' for files in the plans dir)."""
    if LOCAL_T:
        t = os.path.getsize(LOCAL_T) if os.path.exists(LOCAL_T) else None
        m = None
        if LOCAL_M and os.path.exists(LOCAL_M):
            st = os.stat(LOCAL_M)
            m = f"{st.st_size}:{int(st.st_mtime)}"
        plans = []
        if LOCAL_P and os.path.isdir(LOCAL_P):
            for n in os.listdir(LOCAL_P):
                fp = os.path.join(LOCAL_P, n)
                if os.path.isfile(fp):
                    st = os.stat(fp)
                    plans.append(f"{n}:{st.st_size}:{st.st_mtime}")
        return t, m, sorted(plans)
    out = ssh(
        f"stat -c %s {TRANSCRIPT} 2>/dev/null || echo MISSING; "
        f"stat -c %s:%Y {MEMORY} 2>/dev/null || echo MISSING; "
        f"find {PLANS} -maxdepth 1 -type f -printf '%f:%s:%T@\\n' 2>/dev/null | sort"
    ).decode().splitlines()
    t = None if out[0] == "MISSING" else int(out[0])
    m = None if out[1] == "MISSING" else out[1]
    return t, m, [l for l in out[2:] if l]


def mirror_plans(replaced):
    """rsync the plans dir into PLANS_MIRROR. Files in `replaced` (changed or
    removed remotely) are first moved to .history/<timestamp>/ by hand,
    because macOS openrsync ignores --delete together with --backup."""
    src = (LOCAL_P.rstrip("/") + "/") if LOCAL_T else f"{HOST}:{PLANS}/"
    backup = os.path.join(PLANS_MIRROR, ".history", time.strftime("%Y%m%dT%H%M%S"))
    for name in replaced:
        cur = os.path.join(PLANS_MIRROR, name)
        if os.path.isfile(cur):
            os.makedirs(backup, exist_ok=True)
            os.replace(cur, os.path.join(backup, name))
    cmd = ["rsync", "-a", "--exclude", ".history"]
    if not LOCAL_T:
        cmd += ["-e", "ssh -o BatchMode=yes -o ConnectTimeout=10"]
    os.makedirs(PLANS_MIRROR, exist_ok=True)
    r = subprocess.run(cmd + [src, PLANS_MIRROR + "/"], capture_output=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode(errors="replace").strip() or f"rsync exit {r.returncode}")


def fetch_tail(offset):
    if LOCAL_T:
        with open(LOCAL_T, "rb") as f:
            f.seek(offset)
            return f.read()
    return ssh(f"tail -c +{offset + 1} {TRANSCRIPT}", timeout=120)


def summarize(chunk):
    users, texts, last = 0, 0, None
    for line in chunk.decode(errors="replace").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("isSidechain"):
            continue
        t = r.get("type")
        if t == "user":
            c = (r.get("message") or {}).get("content")
            if isinstance(c, str) and not c.lstrip().startswith("<task-notification>"):
                users += 1
        if t == "assistant":
            for b in (r.get("message") or {}).get("content") or []:
                if b.get("type") == "text" and b.get("text", "").strip():
                    texts += 1
        if t in ("assistant", "user") or (t == "system" and r.get("subtype") == "stop_hook_summary"):
            last = r
    ended = False
    if last is not None:
        if last.get("type") == "system":
            ended = True
        elif last.get("type") == "assistant":
            ended = (last.get("message") or {}).get("stop_reason") == "end_turn"
    return users, texts, ended, (last or {}).get("uuid"), (last or {}).get("timestamp")


def run_script(script, timeout=60):
    """Run a bash script on pgx (or locally in repo self-tests); return stdout."""
    cmd = ["bash", "-s"] if LOCAL_R else [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", HOST, "bash -s"]
    r = subprocess.run(cmd, input=script.encode(), capture_output=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode(errors="replace").strip() or f"exit {r.returncode}")
    return r.stdout


def repo_signatures():
    """name -> six-line signature of each dev clone: its branches, default
    branch, which branches origin (GitHub) has and at what commit, the
    checked-out branch and commit, and a hash of uncommitted work. Reads are
    lock-free (GIT_OPTIONAL_LOCKS=0) so they never race the implementer's
    index writes."""
    lines = ["export GIT_OPTIONAL_LOCKS=0\n"]
    for n in REPO_NAMES:
        d = f"{REPO_REMOTE_ROOT}/{n}"
        lines.append(
            f"d={d}; printf '@@%s\\n' {n}\n"
            "git -C $d for-each-ref --format='%(refname:short)=%(objectname)' refs/heads | sort | tr '\\n' ' '; echo\n"
            "def=$(git -C $d symbolic-ref -q --short refs/remotes/origin/HEAD 2>/dev/null); echo \"${def#origin/}\"\n"
            "for b in $(git -C $d for-each-ref --format='%(refname:short)' refs/heads); do "
            "printf '%s=%s ' \"$b\" \"$(git -C $d rev-parse -q --verify refs/remotes/origin/$b || echo -)\"; done; echo\n"
            "git -C $d symbolic-ref -q --short HEAD || echo detached\n"
            "git -C $d rev-parse HEAD\n" + WIP_HASH_SNIPPET)
    out = run_script("".join(lines)).decode().split("@@")[1:]
    sigs = {}
    for block in out:
        name, *vals = block.rstrip("\n").split("\n")
        sigs[name] = "\n".join(v.strip() for v in vals)
    return sigs


def parse_sig(sig):
    heads_l, default, pushed_l, head_ref, head_sha, wip = (sig.split("\n") + [""] * 6)[:6]
    heads = dict(kv.split("=", 1) for kv in heads_l.split())
    pushed = dict(kv.split("=", 1) for kv in pushed_l.split())
    defaults = {default} if default else {"main", "master"}
    work = sorted(b for b in heads if b not in defaults)
    return heads, defaults, pushed, work, head_ref, head_sha, wip


def core_of(sig):
    """The ref part of a signature (everything but the uncommitted-work hash)."""
    return "\n".join(sig.split("\n")[:5])


def git(local, *args, check=True, timeout=300, env=None):
    r = subprocess.run(["git", "-C", local, *args], capture_output=True, timeout=timeout,
                       env={**os.environ, "GIT_SSH_COMMAND": "ssh -o BatchMode=yes -o ConnectTimeout=10",
                            **(env or {})})
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} in {local}: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout.decode().strip()


def update_local_branch(local, b, new):
    """Create or fast-forward local branch b to pgx/b. Never moves a branch
    that is checked out in a worktree here or that has diverged from pgx."""
    cur = git(local, "rev-parse", "-q", "--verify", f"refs/heads/{b}", check=False)
    if not cur:
        git(local, "branch", "--track", b, f"pgx/{b}")
        return "created"
    if cur == new:
        return "up to date"
    wt = git(local, "worktree", "list", "--porcelain", check=False).splitlines()
    if f"branch refs/heads/{b}" in wt:
        return f"checked out here at {cur[:10]}, not moved (pgx is {new[:10]})"
    anc = subprocess.run(["git", "-C", local, "merge-base", "--is-ancestor", cur, new]).returncode == 0
    if anc:
        git(local, "update-ref", f"refs/heads/{b}", new, cur)
        return f"fast-forwarded {cur[:10]}->{new[:10]}"
    return f"DIVERGED: local {cur[:10]} vs pgx {new[:10]}, not moved"


def sync_repo(name, sig, old_core):
    """Ref sync only: fetch every dev-clone branch into the local repo as
    pgx/*, create or fast-forward a local branch for each non-default one,
    and write repos/<name>/state.md (previous copy kept in .history/).
    Uncommitted work is handled separately by snapshot_wip()."""
    heads, defaults, pushed, work, head_ref, head_sha, _ = parse_sig(sig)
    old_heads = parse_sig(old_core)[0] if old_core else {}
    local = os.path.join(REPO_LOCAL_ROOT, name)
    d = f"{REPO_REMOTE_ROOT}/{name}"
    git(local, "config", "--replace-all", "remote.pgx.fetch", "+refs/heads/*:refs/remotes/pgx/*")
    git(local, "fetch", "-q", "--prune", "--no-tags", "pgx")
    for b, sha in heads.items():
        got = git(local, "rev-parse", "-q", "--verify", f"refs/remotes/pgx/{b}", check=False)
        if got != sha:
            raise RuntimeError(f"after fetch pgx/{b} is {got or 'missing'}, dev clone has {sha}")
    actions = {b: update_local_branch(local, b, heads[b]) for b in work}
    for b in sorted(set(old_heads) - set(heads)):
        actions[b] = "deleted on pgx; local branch kept" if git(
            local, "rev-parse", "-q", "--verify", f"refs/heads/{b}", check=False) else "deleted on pgx"
    script = f"export GIT_OPTIONAL_LOCKS=0\nd={d}\n"
    for b in work:
        script += (f"echo '@@B {b}'\ngit -C $d log --format='%h %ad %s' --date=format:'%Y-%m-%d %H:%M' "
                   f"refs/heads/{b} --not --remotes=origin 2>/dev/null || true\n")
    script += "echo @@STATUS\ngit -C $d status --short --branch\n"
    out = run_script(script, timeout=120).decode(errors="replace")
    logs_part, status = out.split("@@STATUS\n", 1)
    commits = {}
    for chunk in logs_part.split("@@B ")[1:]:
        b, *ls = chunk.split("\n")
        commits[b.strip()] = [l for l in ls if l.strip()]
    mdir = os.path.join(REPO_MIRROR, name)
    os.makedirs(mdir, exist_ok=True)
    cur = os.path.join(mdir, "state.md")
    if os.path.isfile(cur):
        hist = os.path.join(mdir, ".history", time.strftime("%Y%m%dT%H%M%S"))
        os.makedirs(hist, exist_ok=True)
        os.replace(cur, os.path.join(hist, "state.md"))
    rows = "".join(
        f"| `{b}` | `{heads.get(b, '-')[:12]}` | "
        f"{'no' if pushed.get(b, '-') == '-' else 'yes, origin at `' + pushed[b][:12] + '`'} | "
        f"{'default branch' if b in defaults else actions.get(b, '')} |\n" for b in sorted(heads))
    rows += "".join(f"| `{b}` | (gone) | | {a} |\n" for b, a in actions.items() if b not in heads)
    body = "".join(f"\n### `{b}`\n\n" + ("\n".join(f"- {c}" for c in cs) or "(none)") + "\n"
                   for b, cs in commits.items())
    tmp = cur + ".tmp"
    with open(tmp, "w") as f:
        f.write(f"# {name} on pgx ({d})\n\nRefs synced {time.strftime('%Y-%m-%d %H:%M:%S %z')}. "
                f"Every dev-clone branch is fetched into `{local}` as `pgx/<branch>`; each non-default "
                "branch also has a local branch of the same name tracking it.\n\n"
                f"Checked out on pgx at that time: `{head_ref}` at `{head_sha[:12]}`. Uncommitted work: see "
                "`wip/current/wip.meta.json` and `wip/current/wip.patch` (one consistent generation; captured independently).\n\n"
                "| Branch | pgx tip | Pushed to GitHub | Local branch |\n|---|---|---|---|\n" + rows +
                "\n## Commits not on any origin branch (as the dev clone sees origin)\n" + body +
                "\n## git status on pgx (at ref sync)\n\n```\n" + status + "```\n")
    os.replace(tmp, cur)
    return actions, commits, mdir


WIP_HASH_SNIPPET = (
    # Uncommitted-work hash: tracked diff against HEAD, plus each untracked
    # file's name, content hash and mode (size, mtime and mode above the
    # capture limit), so same-name edits of untracked files change it.
    "{ git -C $d diff HEAD --binary\n"
    "  git -C $d ls-files --others --exclude-standard -z | while IFS= read -r -d '' f; do\n"
    "    p=\"$d/$f\"; sz=$(stat -c %s \"$p\" 2>/dev/null || stat -f %z \"$p\"); "
    "md=$(stat -c %a \"$p\" 2>/dev/null || stat -f %Lp \"$p\")\n"
    "    if [ \"$sz\" -gt " + str(WIP_FILE_LIMIT) + " ]; then "
    "mt=$(stat -c %Y \"$p\" 2>/dev/null || stat -f %m \"$p\"); printf 'U %s big %s %s %s\\n' \"$f\" \"$sz\" \"$mt\" \"$md\"\n"
    "    else printf 'U %s %s %s\\n' \"$f\" \"$(git -C $d hash-object -- \"$f\")\" \"$md\"; fi\n"
    "  done\n"
    "} | git hash-object --stdin\n")


def test_fail(point):
    """Self-test fault injection (only with SYNC_REPO_REMOTE_ROOT set)."""
    if LOCAL_R and os.environ.get("SYNC_TEST_FAIL_AT") == point:
        raise OSError(f"injected failure at {point}")


def wip_dir(name):
    return os.path.join(REPO_MIRROR, name, "wip")


def current_generation(name):
    """Resolve wip/current once; return (dir, meta) of that generation or
    (None, None). Readers must read both files from the returned dir."""
    cur = os.path.join(wip_dir(name), "current")
    if not os.path.islink(cur):
        return None, None
    g = os.path.realpath(cur)
    try:
        with open(os.path.join(g, "wip.meta.json")) as f:
            return g, json.load(f)
    except (OSError, ValueError):
        return None, None


def publish_generation(name, meta, patch):
    """Write a complete generation (wip.patch if dirty, wip.meta.json with
    the patch's sha256) into a temp dir, rename it into place, then switch
    wip/current with one atomic symlink replace. Any failure before the
    switch leaves wip/current on the previous complete generation."""
    wd = wip_dir(name)
    os.makedirs(wd, exist_ok=True)
    gid = time.strftime("gen-%Y%m%dT%H%M%S-") + f"{int(time.time() * 1000) % 1000:03d}"
    tmp = os.path.join(wd, "." + gid + ".tmp")
    final = os.path.join(wd, gid)
    try:
        os.makedirs(tmp)
        if patch is not None:
            test_fail("patch")
            with open(os.path.join(tmp, "wip.patch"), "wb") as f:
                f.write(patch)
            meta["patch_sha256"] = hashlib.sha256(patch).hexdigest()
        meta["generation"] = gid
        test_fail("meta")
        with open(os.path.join(tmp, "wip.meta.json"), "w") as f:
            json.dump(meta, f, indent=1)
        test_fail("rename")
        os.rename(tmp, final)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    link_tmp = os.path.join(wd, ".current.tmp")
    try:
        if os.path.lexists(link_tmp):
            os.remove(link_tmp)
        os.symlink(gid, link_tmp)
        test_fail("pointer")
        os.replace(link_tmp, os.path.join(wd, "current"))
    except BaseException:
        if os.path.lexists(link_tmp):
            os.remove(link_tmp)
        shutil.rmtree(final, ignore_errors=True)
        raise
    try:  # pruning is best effort; current is already consistent
        test_fail("prune")
        gens = sorted(d for d in os.listdir(wd) if d.startswith("gen-"))
        for old in gens[:-WIP_KEEP_GENERATIONS]:
            if old != gid:
                shutil.rmtree(os.path.join(wd, old), ignore_errors=True)
    except OSError:
        pass
    return gid


def capture_wip(name):
    """Read the dev clone's uncommitted work: the tracked diff against HEAD
    plus untracked files up to WIP_FILE_LIMIT each, with HEAD read before and
    after. Lock-free and read-only on pgx. Returns (meta, patch)."""
    d = f"{REPO_REMOTE_ROOT}/{name}"
    mid = os.environ.get("SYNC_TEST_MID_CAPTURE", "") if LOCAL_R else ""
    script = (
        "export GIT_OPTIONAL_LOCKS=0\nset -e\n"
        f"d={d}\nt=$(mktemp -d)\ntrap 'rm -rf $t' EXIT\n"
        "b=$(git -C $d rev-parse HEAD)\n"
        "r=$(git -C $d symbolic-ref -q --short HEAD || echo detached)\n"
        "ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)\n"
        "git -C $d diff HEAD --binary > $t/p\n"
        "git -C $d ls-files --others --exclude-standard -z > $t/u\n"
        "while IFS= read -r -d '' f; do\n"
        "  sz=$(stat -c %s \"$d/$f\" 2>/dev/null || stat -f %z \"$d/$f\")\n"
        f"  if [ \"$sz\" -gt {WIP_FILE_LIMIT} ]; then printf '%s\\t%s\\n' \"$f\" \"$sz\" >> $t/s; "
        "else git -C $d diff --no-index --binary -- /dev/null \"$f\" >> $t/p || true; fi\n"
        "done < $t/u\n"
        + (mid + "\n" if mid else "") +
        "a=$(git -C $d rev-parse HEAD)\n"
        + WIP_HASH_SNIPPET.replace("} | git hash-object --stdin\n", "} | git hash-object --stdin > $t/h\n") +
        "printf '@@BASE %s\\n@@AFTER %s\\n@@REF %s\\n@@TIME %s\\n@@HASH %s\\n@@SKIPPED\\n' \"$b\" \"$a\" \"$r\" \"$ts\" \"$(cat $t/h)\"\n"
        "cat $t/s 2>/dev/null || true\n"
        "printf '@@PATCH\\n'\ncat $t/p\n")
    out = run_script(script, timeout=180)
    head, patch = out.split(b"@@PATCH\n", 1)
    meta, skipped, part = {}, [], "hdr"
    for line in head.decode(errors="replace").splitlines():
        if line == "@@SKIPPED":
            part = "skipped"
        elif part == "hdr" and line.startswith("@@"):
            k, v = line[2:].split(" ", 1)
            meta[k.lower()] = v
        elif part == "skipped" and line.strip():
            f, sz = line.rsplit("\t", 1)
            skipped.append({"path": f, "bytes": int(sz)})
    for k in ("base", "after", "ref", "time", "hash"):
        if k not in meta:
            raise RuntimeError(f"capture output lacks {k}")
    meta["skipped_untracked"] = skipped
    return meta, patch


def validate_patch(local, base, patch_path):
    """Prove the patch applies to its base commit, in a throwaway index
    (GIT_INDEX_FILE) so the real checkout and index are never touched.
    Returns None when it applies, else the reason."""
    if not git(local, "cat-file", "-t", f"{base}^{{commit}}", check=False):
        git(local, "fetch", "-q", "--no-tags", "pgx", check=False)
        if not git(local, "cat-file", "-t", f"{base}^{{commit}}", check=False):
            return f"base {base[:12]} not present locally yet"
    if os.path.getsize(patch_path) == 0:
        return None
    with tempfile.TemporaryDirectory() as td:
        env = {"GIT_INDEX_FILE": os.path.join(td, "index")}
        git(local, "read-tree", base, env=env)
        r = subprocess.run(["git", "-C", local, "apply", "--cached", "--check", "--binary", patch_path],
                           capture_output=True, env={**os.environ, **env})
        if r.returncode != 0:
            return "git apply --check failed: " + r.stderr.decode(errors="replace").strip()[:300]
    return None


def snapshot_wip(s, name, wip_hash, events):
    """Copy the dev clone's uncommitted work into a new immutable generation
    under repos/<name>/wip/, switched in by one atomic wip/current symlink.
    Runs every poll the work hash changed (no stability wait), and at least
    every WIP_FORCE_EVERY s while dirty. A capture is published only if HEAD
    held during it and its patch applies to its recorded base; any failure
    leaves wip/current on the last complete generation."""
    st = s.setdefault("wip", {}).setdefault(name, {})
    local = os.path.join(REPO_LOCAL_ROOT, name)
    now = time.time()
    g, cur_meta = current_generation(name)
    dirty = wip_hash != EMPTY_BLOB
    if cur_meta and wip_hash == st.get("hash") and (not dirty or now - st.get("at", 0) < WIP_FORCE_EVERY):
        return
    reason = None
    try:
        if not dirty:
            if cur_meta and cur_meta.get("clean"):
                st.update(hash=wip_hash, at=now, fails=0)
                return
            publish_generation(name, {"repo": name, "clean": True, "wip_hash": wip_hash,
                                      "captured_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                      "note": "working tree clean at this time"}, None)
            st.update(hash=wip_hash, at=now, fails=0)
            return
        meta, patch = capture_wip(name)
        if meta["base"] != meta["after"]:
            reason = f"HEAD moved during capture ({meta['base'][:12]} -> {meta['after'][:12]})"
        else:
            if (cur_meta and not cur_meta.get("clean") and cur_meta.get("base_head") == meta["base"]
                    and cur_meta.get("patch_sha256") == hashlib.sha256(patch).hexdigest()):
                st.update(hash=meta["hash"], at=now, fails=0)  # same content: nothing to publish
                return
            wd = wip_dir(name)
            os.makedirs(wd, exist_ok=True)
            check_path = os.path.join(wd, ".validate.patch")
            try:
                with open(check_path, "wb") as f:
                    f.write(patch)
                test_fail("validate")
                reason = validate_patch(local, meta["base"], check_path)
                if reason:
                    os.replace(check_path, os.path.join(wd, "rejected.patch"))
            finally:
                if os.path.exists(check_path):
                    os.remove(check_path)
            if not reason:
                files = patch.count(b"\ndiff --git ") + (1 if patch.startswith(b"diff --git ") else 0)
                gid = publish_generation(name, {
                    "repo": name, "clean": False, "remote_dir": f"{REPO_REMOTE_ROOT}/{name}",
                    "base_head": meta["base"], "head_ref": meta["ref"],
                    "captured_at_remote_utc": meta["time"],
                    "captured_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "wip_hash": meta["hash"], "files_in_patch": files, "patch_bytes": len(patch),
                    "skipped_untracked": meta["skipped_untracked"],
                    "validated": "applies to base_head (git apply --cached --check --binary in a throwaway index)",
                    "restore": "git worktree add <dir> <base_head> && git -C <dir> apply --binary wip.patch"}, patch)
                st.update(hash=meta["hash"], base=meta["base"], at=now, fails=0)
                if st.get("fail_reported"):
                    events.append(f"REPO_WIP_RECOVERED {name} snapshot {gid} published, base {meta['base'][:10]}")
                    st["fail_reported"] = False
                elif now - s.setdefault("repo_wip_event_at", {}).get(name, 0) >= WIP_EVENT_EVERY:
                    events.append(f"REPO_WIP {name} uncommitted work captured: {files} file(s), base {meta['base'][:10]}, "
                                  f"validated, {gid} (further captures are silent for {WIP_EVENT_EVERY // 60} min) "
                                  f"files={wip_dir(name)}/current")
                    s["repo_wip_event_at"][name] = now
                return
    except Exception as e:  # noqa: BLE001 - kept as a failure; wip/current stays on the last good generation
        reason = f"capture/publish failed: {str(e)[:300]}"
    st["fails"] = st.get("fails", 0) + 1
    st["last_fail"] = reason
    if st["fails"] == WIP_FAIL_REPORT_AFTER and not st.get("fail_reported"):
        events.append(f"REPO_WIP_FAIL {name}: {st['fails']} captures in a row not published ({reason}); "
                      f"wip/current kept on the last good generation (base {str(st.get('base', 'none'))[:10]})")
        st["fail_reported"] = True


def poll_repos(s, events):
    """Ref sync waits for the refs part of the signature to hold for
    STABLE_POLLS polls (uncommitted edits don't reset it); uncommitted work
    is snapshotted every poll it changed, independently."""
    try:
        sigs = repo_signatures()
    except Exception as e:  # noqa: BLE001 - reported once per error text
        msg = str(e)[:300]
        if s.get("repo_probe_failed") != msg:
            events.append(f"REPO_SYNC_FAIL probe: {msg}")
            s["repo_probe_failed"] = msg
        return
    s.pop("repo_probe_failed", None)
    known = s.setdefault("repo_sigs", {})
    failed = s.setdefault("repo_failed", {})
    seen = s.setdefault("repo_seen", {})
    for name, sig in sigs.items():
        core = core_of(sig)
        old_core = core_of(known[name]) if "\n" in known.get(name, "") else ""
        stable = core_of(seen.get(name, "")) == core
        seen[name] = core
        if stable and old_core != core and failed.get(name) != core:
            try:
                actions, commits, mdir = sync_repo(name, sig, old_core)
                heads, _, pushed, work, head_ref, head_sha, _ = parse_sig(sig)
                br = ", ".join(
                    f"{b}@{heads[b][:10]} ({len(commits.get(b, []))} commits; local: {actions.get(b)}; "
                    f"github: {'no' if pushed.get(b, '-') == '-' else pushed[b][:10]})" for b in work)
                gone = ", ".join(f"{b}: {a}" for b, a in actions.items() if b not in heads)
                events.append(f"REPO_CHANGED {name} branches=[{br}]" + (f" gone=[{gone}]" if gone else "")
                              + f" head={head_ref}@{head_sha[:10]} files={mdir}")
                known[name] = core
                failed.pop(name, None)
            except Exception as e:  # noqa: BLE001 - once per ref state, retried when it moves
                events.append(f"REPO_SYNC_FAIL {name}: {str(e)[:300]}")
                failed[name] = core
        snapshot_wip(s, name, sig.split("\n")[5] if sig.count("\n") >= 5 else EMPTY_BLOB, events)


def poll_phase0(s, events):
    """Mirror the implementer's Phase 0 dir minus PHASE0_EXCLUDES, silently.
    Reports only failures and an over-size set, once per listing."""
    prune = " -o ".join(f"-path ./{x}" for x in PHASE0_EXCLUDES)
    script = (f"cd {PHASE0_ROOT} 2>/dev/null || {{ echo MISSING; exit 0; }}\n"
              f"L=$(find . \\( {prune} \\) -prune -o -type f -size -{PHASE0_MAX_FILE_KIB}k "
              "-printf '%s %P %T@\\n' | sort -k2)\n"
              "printf '%s\\n' \"$L\" | git hash-object --stdin\n"
              "printf '%s\\n' \"$L\" | awk '{s+=$1} END {print s+0}'\n")
    if LOCAL_P0:  # self-tests on macOS: BSD find has no -printf
        script = script.replace("-printf '%s %P %T@\\n'", "-exec stat -f '%z %N %m' {} +")
    try:
        out = (subprocess.run(["bash", "-s"], input=script.encode(), capture_output=True).stdout
               if LOCAL_P0 else run_script(script)).decode().split()
    except Exception:  # noqa: BLE001 - the transcript probe reports ssh outages
        return
    if not out or out[0] == "MISSING":
        return
    sig, total = out[0], int(out[1])
    if sig == s.get("phase0_sig") or sig == s.get("phase0_failed"):
        return
    if total > PHASE0_MAX_TOTAL:
        events.append(f"PHASE0_SYNC_FAIL {total} bytes to mirror exceeds {PHASE0_MAX_TOTAL}; "
                      "a new large folder in phase0? add it to PHASE0_EXCLUDES")
        s["phase0_failed"] = sig
        return
    src = (PHASE0_ROOT.rstrip("/") + "/") if LOCAL_P0 else f"{HOST}:{PHASE0_ROOT}/"
    cmd = ["rsync", "-a", "--delete", f"--max-size={PHASE0_MAX_SIZE}"]
    cmd += [f"--exclude=/{x}/" for x in PHASE0_EXCLUDES]
    if not LOCAL_P0:
        cmd += ["-e", "ssh -o BatchMode=yes -o ConnectTimeout=10"]
    os.makedirs(PHASE0_MIRROR, exist_ok=True)
    r = subprocess.run(cmd + [src, PHASE0_MIRROR + "/"], capture_output=True, timeout=600)
    if r.returncode != 0:
        events.append(f"PHASE0_SYNC_FAIL {r.stderr.decode(errors='replace').strip()[:300]}")
        s["phase0_failed"] = sig
        return
    s["phase0_sig"] = sig
    s.pop("phase0_failed", None)
    s["phase0_synced_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")


def poll_sessions(s, events):
    """Turn-end detection for EXTRA_SESSIONS, like the main transcript."""
    names = list(EXTRA_SESSIONS)
    if LOCAL_S:
        sizes = [os.path.getsize(os.path.join(LOCAL_S, EXTRA_SESSIONS[n]))
                 if os.path.exists(os.path.join(LOCAL_S, EXTRA_SESSIONS[n])) else None for n in names]
    else:
        try:
            out = ssh("; ".join(f"stat -c %s {SESSIONS_DIR}/{EXTRA_SESSIONS[n]} 2>/dev/null || echo MISSING"
                                for n in names)).decode().split()
        except Exception:  # noqa: BLE001 - the main probe reports ssh outages
            return
        sizes = [None if v == "MISSING" else int(v) for v in out]
    allst = s.setdefault("sessions", {})
    for n, size in zip(names, sizes):
        st = allst.setdefault(n, {})
        if size is None:
            if not st.get("missing_reported"):
                events.append(f"MISSING {n} transcript {EXTRA_SESSIONS[n]} is gone (session moved or deleted?)")
                st["missing_reported"] = True
            continue
        st["missing_reported"] = False
        if "synced" not in st:
            st.update(synced=size, last_seen=size, stable=0)
            continue
        if size < st["synced"]:
            events.append(f"SHRUNK {n} transcript is {size} bytes, below synced {st['synced']}; restarting at it")
            st.update(synced=size, last_seen=size, stable=0)
            continue
        if size == st["synced"]:
            continue
        st["stable"] = st.get("stable", 0) + 1 if st.get("last_seen") == size else 0
        st["last_seen"] = size
        if st["stable"] < STABLE_POLLS - 1:
            continue
        path = os.path.join(LOCAL_S, EXTRA_SESSIONS[n]) if LOCAL_S else None
        try:
            if path:
                with open(path, "rb") as f:
                    f.seek(st["synced"])
                    chunk = f.read()
            else:
                chunk = ssh(f"tail -c +{st['synced'] + 1} {SESSIONS_DIR}/{EXTRA_SESSIONS[n]}", timeout=120)
        except Exception:  # noqa: BLE001 - retried next poll
            continue
        users, texts, ended, uuid, ts = summarize(chunk)
        if not ended:
            continue
        d = os.path.join(INCREMENTS, n)
        os.makedirs(d, exist_ok=True)
        inc = os.path.join(d, f"{st['synced']:010d}-{size:010d}.jsonl")
        with open(inc, "wb") as f:
            f.write(chunk)
        src = path if path else f"{HOST}:{SESSIONS_DIR}/{EXTRA_SESSIONS[n]}"
        cmd = ["rsync", "-a"] + ([] if path else ["-e", "ssh -o BatchMode=yes -o ConnectTimeout=10"])
        os.makedirs(TRANSCRIPTS_MIRROR, exist_ok=True)
        subprocess.run(cmd + [src, TRANSCRIPTS_MIRROR + "/"], capture_output=True, timeout=300)
        events.append(f"TURN_ENDED {n} bytes {st['synced']}->{size} new_user_prompts={users} "
                      f"new_assistant_texts={texts} last_uuid={uuid} last_ts={ts} increment={inc}")
        st["synced"] = size


def poll_origin(s, events):
    """Every ORIGIN_EVERY s: fetch implementer branches GitHub has, and
    report a pgx tip that stays unpushed longer than UNPUSHED_AFTER s."""
    now = time.time()
    if now - s.get("origin_checked_at", 0) < ORIGIN_EVERY:
        return
    s["origin_checked_at"] = now
    unp = s.setdefault("unpushed_since", {})
    reported = s.setdefault("unpushed_reported", {})
    seen = s.setdefault("origin_tips", {})
    for name, sig in s.get("repo_sigs", {}).items():
        if "\n" not in sig:
            continue
        heads, _, _, work, _, _, _ = parse_sig(sig)
        if not work:
            continue
        local = os.path.join(REPO_LOCAL_ROOT, name)
        url = ORIGIN_URL.format(repo=name)
        r = subprocess.run(["git", "ls-remote", "--heads", url] + [f"refs/heads/{b}" for b in work],
                           capture_output=True, timeout=60)
        if r.returncode != 0:
            continue  # GitHub unreachable; try again next round
        gh = {}
        for line in r.stdout.decode().splitlines():
            sha, ref = line.split("\t")
            gh[ref.replace("refs/heads/", "")] = sha
        for b in work:
            key = f"{name}:{b}"
            if b in gh and seen.get(key) != gh[b]:
                f = subprocess.run(["git", "-C", local, "fetch", "-q", "--no-tags", url,
                                    f"+refs/heads/{b}:refs/remotes/origin/{b}"], capture_output=True, timeout=300)
                if f.returncode == 0:
                    events.append(f"ORIGIN_PUSHED {name} {b} now {gh[b][:10]} on GitHub "
                                  f"(pgx tip {heads[b][:10]}); fetched as origin/{b}")
                    seen[key] = gh[b]
                else:
                    events.append(f"REPO_SYNC_FAIL {name} fetching origin/{b}: "
                                  f"{f.stderr.decode(errors='replace').strip()[:200]}")
            if gh.get(b) == heads[b]:
                unp.pop(key, None)
                reported.pop(key, None)
                continue
            since = unp.setdefault(key, [heads[b], now])
            if since[0] != heads[b]:
                unp[key] = since = [heads[b], now]
            if now - since[1] >= UNPUSHED_AFTER and reported.get(key) != heads[b]:
                events.append(f"REPO_UNPUSHED {name} {b}: pgx tip {heads[b][:10]} not on GitHub "
                              f"(GitHub has {gh[b][:10] if b in gh else 'no such branch'}) for {int((now - since[1]) // 60)} min")
                reported[key] = heads[b]


def poll_transcripts(s, events):
    """rsync every watched transcript (.jsonl plus its side dir) into
    TRANSCRIPTS_MIRROR every TRANSCRIPTS_EVERY s; silent unless it fails
    twice in a row while ssh itself works."""
    now = time.time()
    if now - s.get("transcripts_synced_at", 0) < TRANSCRIPTS_EVERY:
        return
    ids = [os.path.basename(TRANSCRIPT)[:-6]] + [f[:-6] for f in EXTRA_SESSIONS.values()]
    os.makedirs(TRANSCRIPTS_MIRROR, exist_ok=True)
    errs = []
    for i in ids:
        for src, dst in ((f"{SESSIONS_DIR}/{i}.jsonl", TRANSCRIPTS_MIRROR + "/"),
                         (f"{SESSIONS_DIR}/{i}/", f"{TRANSCRIPTS_MIRROR}/{i}/")):
            r = subprocess.run(["rsync", "-a", "-e", "ssh -o BatchMode=yes -o ConnectTimeout=10",
                                f"{HOST}:{src}", dst], capture_output=True, timeout=300)
            if r.returncode != 0 and not src.endswith("/"):
                errs.append(f"{i}: {r.stderr.decode(errors='replace').strip()[:120]}")
    if errs:
        s["transcripts_fail"] = s.get("transcripts_fail", 0) + 1
        if s["transcripts_fail"] == 2:
            events.append("TRANSCRIPTS_SYNC_FAIL " + "; ".join(errs))
        return
    s["transcripts_fail"] = 0
    s["transcripts_synced_at"] = now


def poll(s):
    events = []
    try:
        size, mem, plans = stat_sizes()
        if s.get("ssh_failures", 0) >= SSH_FAIL_LIMIT:
            events.append("SSH_RECOVERED ssh to pgx-research works again")
        s["ssh_failures"] = 0
    except Exception as e:  # noqa: BLE001 - any failure counts toward the limit
        s["ssh_failures"] = s.get("ssh_failures", 0) + 1
        if s["ssh_failures"] == SSH_FAIL_LIMIT:
            events.append(f"SSH_FAIL {SSH_FAIL_LIMIT} consecutive failures (pgx-research down or unreachable? "
                          f"check remoteControlState before any takeover): {e}")
        if not LOCAL_T or LOCAL_R:
            poll_origin(s, events)  # GitHub needs no pgx; keep fetching pushes
        return events

    old = {e.rsplit(":", 2)[0]: e for e in s.get("plans_sig", [])}
    new = {e.rsplit(":", 2)[0]: e for e in plans}
    if old != new and s.get("plans_failed") != plans:
        added = sorted(set(new) - set(old))
        removed = sorted(set(old) - set(new))
        changed = sorted(n for n in set(new) & set(old) if new[n] != old[n])
        try:
            mirror_plans(changed + removed)
            events.append(f"PLANS_CHANGED added={added} changed={changed} removed={removed} mirrored_to={PLANS_MIRROR}")
            s["plans_sig"] = plans
            s.pop("plans_failed", None)
        except Exception as e:  # noqa: BLE001 - report once per listing, retry when it changes
            events.append(f"PLANS_MIRROR_FAIL {e}")
            s["plans_failed"] = plans

    if not LOCAL_T or LOCAL_R:
        poll_repos(s, events)
    if not LOCAL_T or LOCAL_P0:
        poll_phase0(s, events)
    if not LOCAL_T or LOCAL_S:
        poll_sessions(s, events)
    if not LOCAL_T:
        poll_transcripts(s, events)
    if not LOCAL_T or LOCAL_R:
        poll_origin(s, events)

    synced = s.get("synced_size", 0)
    if size is None:
        if not s.get("missing_reported"):
            events.append(f"MISSING remote transcript {TRANSCRIPT} is gone (session moved or deleted?)")
            s["missing_reported"] = True
        return events
    s["missing_reported"] = False

    if size < synced:
        if s.get("shrunk_reported") != size:
            events.append(f"SHRUNK transcript is {size} bytes, below synced {synced}; re-sync from scratch")
            s["shrunk_reported"] = size
        return events

    if mem is not None and s.get("memory_sig") and mem != s["memory_sig"] and s.get("memory_notified") != mem:
        events.append(f"MEMORY_CHANGED remote planning memory now {mem} (was {s['memory_sig']})")
        s["memory_notified"] = mem

    if size > synced:
        if s.get("last_seen_size") == size:
            s["stable_polls"] = s.get("stable_polls", 0) + 1
        else:
            s["stable_polls"] = 0
        s["last_seen_size"] = size
        if s["stable_polls"] >= STABLE_POLLS - 1 and s.get("notified_size") != size:
            chunk = fetch_tail(synced)
            users, texts, ended, uuid, ts = summarize(chunk)
            if ended:
                os.makedirs(INCREMENTS, exist_ok=True)
                path = os.path.join(INCREMENTS, f"{synced:010d}-{size:010d}.jsonl")
                with open(path, "wb") as f:
                    f.write(chunk)
                events.append(
                    f"TURN_ENDED bytes {synced}->{size} new_user_prompts={users} "
                    f"new_assistant_texts={texts} last_uuid={uuid} last_ts={ts} increment={path}"
                )
                s["notified_size"] = size
    return events


def main():
    s = load_state()
    args = sys.argv[1:]
    if args[:1] == ["--mark-synced"]:
        size = int(args[1])
        s.update(synced_size=size, notified_size=size, last_seen_size=size, stable_polls=0)
        if len(args) > 2:
            s["memory_sig"] = args[2]
            s["memory_notified"] = args[2]
        s["synced_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        save_state(s)
        print(json.dumps(s))
        return
    if args[:1] == ["--status"]:
        print(json.dumps(s, indent=1))
        return
    events = poll(s)
    save_state(s)
    for e in events:
        print(e, flush=True)


if __name__ == "__main__":
    main()
