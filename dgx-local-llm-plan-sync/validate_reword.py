#!/usr/bin/env python3
"""Validate a message-only history rewrite of a feature branch, then move the
local branch to it.

Usage: validate_reword.py <repo> <old_tip> <new_tip> [--apply]

Walks old and new back in step until they meet at a shared commit. For every
rewritten pair it requires:
- an equal tree;
- the new parent being the next new commit, or the shared base;
- the same author name, email and date, and the same committer name and email;
- a new message that differs from the old one only by removed lines, or by
  one contiguous span deleted from a line where the deleted span itself
  contains the agent mention, with no agent mention left;
- the same committer date (the approved method copies it).
With --apply, and only if every check passed, it moves refs/heads/<branch>
from old_tip to new_tip with `git update-ref` (compare-and-swap), and only if
that branch is not checked out in any worktree. Nothing else is touched.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BRANCH = "local-llm-multiarch"
AGENT = re.compile(r"co-authored|claude|anthropic|generated with|codex|openai|\U0001F916", re.I)


def git(repo, *a):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, check=True).stdout.decode().rstrip("\n")


def span_deleted(old, new):
    """True if new == old with one contiguous span removed, and that span
    contains an agent mention."""
    if len(new) >= len(old):
        return False
    p = 0
    while p < len(new) and new[p] == old[p]:
        p += 1
    s = 0
    while s < len(new) - p and new[-1 - s] == old[-1 - s]:
        s += 1
    if p + s != len(new):
        return False
    return bool(AGENT.search(old[p:len(old) - s]))


def message_ok(om, nm):
    """New message = old message minus whole lines, or with one line trimmed by
    an agent-mention span. Returns (ok, list of describing strings)."""
    notes, i = [], 0
    rest = list(om)
    for line in nm:
        if line in rest:
            rest.remove(line)
            continue
        match = next((o for o in rest if span_deleted(o, line)), None)
        if match is None:
            return False, [f"new line not derived from the old message: {line!r}"]
        rest.remove(match)
        notes.append(f"trimmed: {match!r} -> {line!r}")
    notes += [f"removed line: {l!r}" for l in rest]
    return True, notes


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv
    name, old, new = args
    repo = os.path.join(os.path.dirname(HERE), name)
    old, new = git(repo, "rev-parse", old), git(repo, "rev-parse", new)
    base = git(repo, "merge-base", old, new)
    olds = git(repo, "rev-list", "--first-parent", f"{base}..{old}").split()
    news = git(repo, "rev-list", "--first-parent", f"{base}..{new}").split()
    problems = []
    if len(olds) != len(news):
        problems.append(f"rewritten ranges differ in length: old {len(olds)} vs new {len(news)}")
    fmt = "%T%n%P%n%an%n%ae%n%ad%n%cn%n%ce%n%cd"
    rows = []
    for o, n in zip(olds, news):
        ot, op, oan, oae, oad, ocn, oce, ocd = git(repo, "show", "-s", f"--format={fmt}", "--date=raw", o).split("\n")
        nt, np_, nan, nae, nad, ncn, nce, ncd = git(repo, "show", "-s", f"--format={fmt}", "--date=raw", n).split("\n")
        om = git(repo, "show", "-s", "--format=%B", o).split("\n")
        nm = git(repo, "show", "-s", "--format=%B", n).split("\n")
        msg_ok, removed = message_ok(om, nm)
        checks = {
            "tree": ot == nt,
            "author": (oan, oae, oad) == (nan, nae, nad),
            "committer": (ocn, oce, ocd) == (ncn, nce, ncd),
            "message only removes agent-mention text": msg_ok,
            "no agent mention left": not any(AGENT.search(l) for l in nm),
        }
        rows.append((o[:10], n[:10], checks, removed))
        problems += [f"{o[:10]}->{n[:10]}: {k} FAILED" for k, ok in checks.items() if not ok]
    # parent chain: each new commit's first parent is the next new commit or the base
    for i, n in enumerate(news):
        want = news[i + 1] if i + 1 < len(news) else base
        got = git(repo, "rev-parse", f"{n}^")
        if got != want:
            problems.append(f"{n[:10]}: parent {got[:10]} expected {want[:10]}")
    print(f"{name}: base {base[:10]}; old {old[:10]} -> new {new[:10]}; {len(news)} rewritten commit(s)")
    for o, n, checks, removed in rows:
        print(f"  {o} -> {n}: " + ", ".join(f"{k}={'ok' if v else 'FAIL'}" for k, v in checks.items()))
        for l in removed:
            print(f"      {l}")
    if problems:
        print("NOT VALID:\n  " + "\n  ".join(problems))
        return 1
    print("VALID: message-only rewrite; trees, parent chain and identities preserved")
    if apply:
        cur = git(repo, "rev-parse", "-q", "--verify", f"refs/heads/{BRANCH}")
        wt = git(repo, "worktree", "list", "--porcelain").split("\n")
        if f"branch refs/heads/{BRANCH}" in wt:
            print(f"not moved: {BRANCH} is checked out in a worktree here")
            return 2
        if cur != old:
            print(f"not moved: local {BRANCH} is at {cur[:10]}, not the old tip {old[:10]}")
            return 2
        git(repo, "update-ref", "-m", "validated message-only reword", f"refs/heads/{BRANCH}", new, old)
        print(f"moved local {BRANCH}: {old[:10]} -> {new[:10]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
