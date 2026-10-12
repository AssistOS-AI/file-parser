#!/usr/bin/env python3
"""Check that the current uncommitted-work snapshot restores the pgx tree.

Snapshots live in repos/<repo>/wip/gen-*/ (wip.patch + wip.meta.json) and
repos/<repo>/wip/current points at the last complete one. This resolves
`current` once and reads both files from that one generation. It then checks
the patch's sha256 against the metadata, clones the local repo into a
throwaway directory, checks out the recorded base, applies the patch, and
compares the sha256 of every changed file with the same file on pgx. It only
compares when the pgx tree still has the work hash the snapshot was captured
at (the same content-aware hash check_remote.py uses); otherwise it reports
that the tree has moved on. Nothing is written to the real checkouts or to pgx.

Usage: verify_wip_restore.py [<repo> ...]
"""
import hashlib
import importlib.util
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("check_remote", os.path.join(HERE, "check_remote.py"))
cr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cr)


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, check=True).stdout


def quote(p):
    return "'" + p.replace("'", "'\\''") + "'"


def check(repo):
    g, meta = cr.current_generation(repo)
    if not g:
        return f"{repo}: no published generation yet"
    gen = os.path.basename(g)
    if meta.get("clean"):
        return f"{repo}: {gen} records a clean tree; nothing to restore"
    patch_path = os.path.join(g, "wip.patch")
    data = open(patch_path, "rb").read()
    if hashlib.sha256(data).hexdigest() != meta.get("patch_sha256"):
        return f"{repo}: {gen} INCONSISTENT: wip.patch sha256 does not match wip.meta.json"
    d = f"{cr.REPO_REMOTE_ROOT}/{repo}"
    live = cr.run_script(f"export GIT_OPTIONAL_LOCKS=0\nd={d}\ngit -C $d rev-parse HEAD\n" + cr.WIP_HASH_SNIPPET
                         ).decode().split()
    if live[0] != meta["base_head"] or live[1] != meta["wip_hash"]:
        return f"{repo}: {gen} pgx tree moved on since this capture; can't compare (rerun after the next capture)"
    skipped = {x["path"] for x in meta.get("skipped_untracked", [])}
    local = os.path.join(cr.REPO_LOCAL_ROOT, repo)
    with tempfile.TemporaryDirectory() as td:
        w = os.path.join(td, repo)
        sh(["git", "clone", "-q", "--no-checkout", local, w])
        sh(["git", "-C", w, "fetch", "-q", local, "+refs/remotes/pgx/*:refs/remotes/pgx/*"])
        sh(["git", "-C", w, "checkout", "-q", meta["base_head"]])
        sh(["git", "-C", w, "apply", "--binary", patch_path])
        entries = sh(["git", "-C", w, "status", "--porcelain", "-z", "--untracked-files=all"]).decode().split("\0")
        paths = sorted({e[3:] for e in entries if e and e[:2] != " D" and e[3:] not in skipped})
        deleted = sorted({e[3:] for e in entries if e[:2] == " D"})
        remote = {}
        if paths:
            for line in cr.run_script(f"cd {d} && sha256sum -- " + " ".join(quote(p) for p in paths) + "\n"
                                      ).decode().splitlines():
                h, p = line.split("  ", 1)
                remote[p] = h
        bad = [p for p in paths if remote.get(p) != hashlib.sha256(open(os.path.join(w, p), "rb").read()).hexdigest()]
        gone = cr.run_script(f"cd {d} && for f in " + " ".join(quote(p) for p in deleted)
                             + "; do [ -e \"$f\" ] && echo \"$f\"; done; true\n").decode().split() if deleted else []
    if bad or gone:
        return f"{repo}: {gen} MISMATCH: {len(bad)} changed file(s) differ {bad[:5]}; {len(gone)} deletion(s) still on pgx {gone[:5]}"
    return (f"{repo}: {gen} restore OK: base {meta['base_head'][:10]} + wip.patch reproduces {len(paths)} changed/new "
            f"file(s) and {len(deleted)} deletion(s) byte-for-byte; {len(skipped)} skipped untracked file(s) listed")


def best_effort_note(repo):
    """Report wip/best-effort separately: it is UNVERIFIED evidence (the tree
    changed while it was read) and only interesting if newer than current."""
    link = os.path.join(cr.wip_dir(repo), "best-effort")
    if not os.path.islink(link):
        return None
    b = os.path.realpath(link)
    try:
        bm = __import__("json").load(open(os.path.join(b, "wip.meta.json")))
    except (OSError, ValueError):
        return f"{repo}: best-effort pointer unreadable"
    g, _ = cr.current_generation(repo)
    newer = not g or os.path.basename(b)[3:] > os.path.basename(g)[4:]
    return (f"{repo}: UNVERIFIED best-effort {os.path.basename(b)} (captured {bm.get('captured_at_remote_utc')}, "
            f"tree changed while read; applies to {str(bm.get('base_head'))[:10]}) is "
            + ("NEWER than the verified current generation; use only if the verified one is too old"
               if newer else "older than the verified current generation; ignore it"))


if __name__ == "__main__":
    for r in sys.argv[1:] or cr.REPO_NAMES:
        try:
            print("VERIFIED  " + check(r))
        except Exception as e:  # noqa: BLE001
            print(f"VERIFIED  {r}: error: {e}")
        note = best_effort_note(r)
        if note:
            print("UNVERIFIED " + note)
