"""Refuse to let one session's upload silently erase another's work.

Deploys here go through GitHub's web "Upload files" page, because the sandbox
has no push credentials. That path replaces a file WHOLE. Git never sees a
conflict, the commit looks ordinary, and whatever somebody else committed to
that file while you were working is simply gone - with no marker in history
saying it happened.

That is not hypothetical. On 2026-07-25 a session cloned at 8399953, worked for
an hour, and was one click away from uploading index.html over three commits
another window had landed in the meantime (+103/-4, +21/-1, and an assets
change). It was caught by reading the commit log by hand, seconds before.

claude/WORK-LOCK.md is the cooperative answer, and the other window had not
taken a lock. So this is the non-cooperative one: it asks git what actually
moved, and it does not care whether anybody followed the process.

Two modes, run in this order:

  BEFORE uploading
      python3 scripts/deploy_guard.py index.html sw.js
      -> compares your merge-base against origin/main. If any file you are
         about to upload has moved under you, it prints the commits, the
         rebase command, and exits non-zero.

  AFTER rebasing, before uploading
      python3 scripts/deploy_guard.py --verify index.html sw.js
      -> checks that every non-trivial line those other commits ADDED is still
         present in your working copy. A clean rebase is not proof: the
         whole-file upload is what ships, so verify the bytes you are shipping.

A line you deliberately REWROTE is not a lost line (added 2026-07-25, after
verify flagged three honest edits in one afternoon). When a line is not found
verbatim, verify looks for a near-identical one; if the file still holds an
obvious rewrite of it, that is reported as a rewrite to eyeball, not a loss,
and does not fail the run. Only lines with nothing resembling them left - the
signature of uploading a stale copy - stop the deploy.

With no file arguments, both modes use the files you have actually changed
relative to the merge-base.

Exit codes:  0 safe   2 collision / lost lines   3 git problem
No external dependencies. Read-only: never writes to the repo or the remote.
"""

import difflib
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

REMOTE = "origin"
BRANCH = "main"

# Commits by these authors regenerate derived files on a schedule. They are not
# another human session, and their paths (og/, data/, p/, feeds/ ...) are not
# hand-edited, so a collision with them is noise.
BOT_AUTHORS = ("stacks-og-bot", "stacks-feed-bot", "github-actions",
               "github-actions[bot]")

# Somebody committing to these right now means a live session, not a cron job.
HAND_EDITED = ("index.html", "sw.js", "assets/", "worker/", "scripts/",
               ".github/workflows/", "CLAUDE.md", "sources.json")

ACTIVE_WINDOW_MIN = 45   # "someone else is probably working right now"


class GitError(Exception):
    pass


def git(*args, check=True):
    p = subprocess.run(("git",) + args, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise GitError("git %s -> %s" % (" ".join(args), p.stderr.strip()))
    return p.stdout.rstrip("\n")


def c(code, s):
    return s if not sys.stdout.isatty() else "\033[%sm%s\033[0m" % (code, s)


def bold(s):
    return c("1", s)


def red(s):
    return c("31;1", s)


def green(s):
    return c("32;1", s)


def yellow(s):
    return c("33;1", s)


def substantive(line):
    """Lines whose disappearance actually means something was lost.

    Blank lines and lone braces/brackets move around constantly during honest
    edits; counting them produces false alarms that train people to ignore the
    alarm."""
    s = line.strip()
    return len(s) > 3 and s not in ("*/", "/*", "});", "})", "};", "});;")


def base_memo_path():
    return os.path.join(git("rev-parse", "--git-dir"), "deploy_guard_base")


def remember_base(base):
    """Persist the pre-rebase base so --verify can be exact.

    Without this, verify has to guess its range. Guessing "the last 24 hours"
    flags lines from your OWN earlier commits that a later commit legitimately
    rewrote, and an alarm that cries wolf is an alarm people switch off.
    Untracked, inside .git, local to this clone."""
    try:
        with open(base_memo_path(), "w") as f:
            f.write(base + "\n")
    except OSError:
        pass


def recall_base():
    try:
        with open(base_memo_path()) as f:
            sha = f.read().strip()
        return sha if sha and git("cat-file", "-t", sha, check=False) == "commit" else None
    except OSError:
        return None


def fetch():
    try:
        git("fetch", "-q", REMOTE, BRANCH)
    except GitError as e:
        print(red("원격을 못 읽었습니다 — 검사를 건너뛰지 말고 원인을 먼저 해결하세요."))
        print("  " + str(e))
        sys.exit(3)


SURVIVED = 0.75    # share of a line that must reappear in its own spot


def survival(line, blob):
    """How much of `line` reappears inside `blob`, 0..1.

    Not difflib's ratio(): ratio punishes length difference, so splitting one
    line into six scores low even though every character survived."""
    sm = difflib.SequenceMatcher(None, line, blob, autojunk=False)
    return sum(b.size for b in sm.get_matching_blocks()) / max(1, len(line))


def rewritten_in_place(old_text, new_text):
    """Lines of old_text that new_text replaced with a rewrite of themselves.

    Position is the whole point, so this diffs the two versions rather than
    asking "does something similar exist anywhere in the file". Anywhere is
    far too generous in source code: `function mine(){ return "x"; }` looks a
    lot like `function other(){ return "y"; }`, so a real stale upload would
    find a look-alike for every line it dropped and clear itself.

    Only a `replace` block counts - lines swapped for other lines at the same
    spot. A `delete` block is the stale-upload signature: gone, nothing put
    in their place."""
    o = old_text.splitlines()
    n = new_text.splitlines()
    forgiven = set()
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
            None, o, n, autojunk=False).get_opcodes():
        if tag != "replace":
            continue
        blob = "\n".join(n[j1:j2])
        for line in o[i1:i2]:
            if survival(line, blob) >= SURVIVED:
                forgiven.add(line)
    return forgiven


def added_lines(sha, path):
    """The lines a single commit added to one file."""
    diff = git("show", "--format=", "--unified=0", sha, "--", path, check=False)
    return [ln[1:] for ln in diff.splitlines()
            if ln.startswith("+") and not ln.startswith("+++")]


def commits_touching(rng, path, since_hours=None):
    args = ["log", "--format=%H%x1f%an%x1f%aI%x1f%s"]
    if since_hours:
        args += ["--since=%d.hours" % since_hours]
    args += [rng, "--", path]
    out = git(*args, check=False)
    rows = []
    for line in out.splitlines():
        if not line.strip():
            continue
        sha, author, when, subject = line.split("\x1f", 3)
        rows.append({"sha": sha, "author": author, "when": when, "subject": subject})
    return rows


def minutes_since(iso):
    try:
        t = datetime.fromisoformat(iso)
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - t.astimezone(timezone.utc)).total_seconds() / 60


def changed_files(rng):
    out = git("diff", "--name-only", rng, check=False)
    return [f for f in out.splitlines() if f.strip()]


def resolve_targets(argv, base):
    if argv:
        return argv
    mine = changed_files("%s..HEAD" % base)
    if not mine:
        mine = [f for f in git("diff", "--name-only", "HEAD",
                               check=False).splitlines() if f.strip()]
    return mine


def header(base, head, remote_head):
    print(bold("\ndeploy_guard — 업로드가 남의 작업을 지우는지 검사합니다"))
    print("  내 HEAD      %s" % head[:7])
    print("  원격 main    %s" % remote_head[:7])
    print("  공통 조상    %s" % base[:7])


def mode_check(targets, base, remote_head):
    """Has anything I am about to upload moved under me?"""
    remember_base(base)
    rng = "%s..%s" % (base, remote_head)
    collisions, bot_only = [], []
    for path in targets:
        rows = commits_touching(rng, path)
        if not rows:
            continue
        human = [r for r in rows if not any(b in r["author"] for b in BOT_AUTHORS)]
        (collisions if human else bot_only).append((path, rows, human))

    active = []
    for path in HAND_EDITED:
        for r in commits_touching("%s..%s" % (base, remote_head), path):
            m = minutes_since(r["when"])
            if (m is not None and m <= ACTIVE_WINDOW_MIN
                    and not any(b in r["author"] for b in BOT_AUTHORS)):
                active.append((path, r, m))

    if bot_only:
        print(yellow("\n생성물 변경 (봇) — 무시해도 됩니다"))
        for path, rows, _ in bot_only:
            print("  %s  (%d개 봇 커밋)" % (path, len(rows)))

    if not collisions:
        print(green("\n✅ 안전 — 올릴 파일 %d개 전부, 클론 이후 원격에서 안 움직였습니다."
                    % len(targets)))
        for t in targets:
            print("     %s" % t)
        if active:
            print(yellow("\n⚠ 다만 다른 창이 지금 작업 중일 수 있습니다 "
                         "(최근 %d분 내 커밋):" % ACTIVE_WINDOW_MIN))
            seen = set()
            for path, r, m in active:
                if r["sha"] in seen:
                    continue
                seen.add(r["sha"])
                print("     %s  %2.0f분 전  %s" % (r["sha"][:7], m, r["subject"][:56]))
            print("     올리기 직전에 이 명령을 한 번 더 돌리세요.")
        return 0

    print(red("\n❌ 위험 — 지금 업로드하면 아래 작업이 조용히 사라집니다."))
    print(red("   웹 업로드는 파일 통째 교체라 git이 충돌로 막아주지 않습니다.\n"))
    for path, rows, human in collisions:
        print(bold("  %s" % path))
        for r in human:
            m = minutes_since(r["when"])
            when = "%.0f분 전" % m if m is not None and m < 600 else r["when"][:16]
            n = len([x for x in added_lines(r["sha"], path) if substantive(x)])
            print("     %s  %-10s  +%-4d줄  %s"
                  % (r["sha"][:7], when, n, r["subject"][:52]))
    print(bold("\n  해야 할 일"))
    print("     1) git stash -u   (작업 중이면)")
    print("     2) git fetch %s %s && git rebase %s/%s" % (REMOTE, BRANCH, REMOTE, BRANCH))
    print("     3) 충돌 해결 후 빌드/검증 다시")
    print("     4) python3 scripts/deploy_guard.py --verify %s" % " ".join(targets))
    print("     5) 그 다음에 업로드\n")
    return 2


def mode_verify(targets, base, remote_head, hours):
    """After a rebase: are the other side's lines actually still in my files?

    A rebase that reports success is not the same as a file that still contains
    the other session's work, and the file is what gets uploaded.

    Deliberately NOT scoped to base..origin/main. After a successful rebase
    that range is empty, so scoping it that way makes verify pass without
    reading a single line - which is exactly the moment you needed it to look.
    Instead it re-checks every recent commit on origin/main that touched these
    files. Your own earlier commits get checked too; if one of those is
    reported, confirm you meant to rewrite those lines."""
    memo = recall_base()
    if memo:
        rng = "%s..%s/%s" % (memo, REMOTE, BRANCH)
        since = None
        print("  기준: 검사 때 기록해 둔 베이스 %s 이후 원격 커밋" % memo[:7])
    else:
        rng = "%s/%s" % (REMOTE, BRANCH)
        since = hours
        print(yellow("  기록된 베이스가 없어 최근 %d시간으로 대신합니다 "
                     "(먼저 --verify 없이 한 번 돌리면 정확해집니다)." % hours))

    total_checked = 0
    lost_any = False
    for path in targets:
        rows = [r for r in commits_touching(rng, path, since_hours=since)
                if not any(b in r["author"] for b in BOT_AUTHORS)]
        if not rows:
            continue
        if not os.path.exists(path):
            print(red("  %s 가 작업 폴더에 없습니다" % path))
            lost_any = True
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            current = f.read()
        for r in rows:
            wanted = [ln for ln in added_lines(r["sha"], path) if substantive(ln)]
            absent = [ln for ln in wanted if ln not in current]
            total_checked += len(wanted)
            if absent:
                theirs = git("show", "%s:%s" % (r["sha"], path), check=False)
                forgiven = rewritten_in_place(theirs, current) if theirs else set()
            else:
                forgiven = set()
            rewritten = [ln for ln in absent if ln in forgiven]
            missing = [ln for ln in absent if ln not in forgiven]
            tag = "%s %s" % (r["sha"][:7], r["subject"][:44])
            if missing:
                lost_any = True
                print(red("  ❌ %s" % tag))
                print(red("     %s 에서 %d/%d줄이 사라졌습니다:"
                          % (path, len(missing), len(wanted))))
                for ln in missing[:5]:
                    print("        %s" % ln.strip()[:88])
                if len(missing) > 5:
                    print("        ... 외 %d줄" % (len(missing) - 5))
            elif rewritten:
                print(yellow("  ✎ %s  (%s, %d줄 중 %d줄은 제자리에서 고쳐 씀 — "
                             "사라진 줄은 없습니다. 의도한 수정인지만 확인하세요)"
                             % (tag, path, len(wanted), len(rewritten))))
                for ln in rewritten[:3]:
                    print("        %s" % ln.strip()[:88])
                if len(rewritten) > 3:
                    print("        ... 외 %d줄" % (len(rewritten) - 3))
            else:
                print(green("  ✅ %s  (%s, %d줄 보존)" % (tag, path, len(wanted))))

    if not total_checked:
        print(green("\n✅ 대조할 상대 커밋이 없습니다 — 그대로 올려도 됩니다."))
        return 0
    if lost_any:
        print(red("\n❌ 남의 줄이 사라진 채입니다. 이대로 올리면 그 작업이 없어집니다."))
        return 2
    print(green("\n✅ 상대 커밋이 추가한 %d줄 전부 살아 있습니다. 업로드해도 됩니다."
                % total_checked))
    return 0


def main():
    argv = sys.argv[1:]
    verify = "--verify" in argv
    hours = 24
    for a in argv:
        if a.startswith("--hours="):
            hours = int(a.split("=", 1)[1])
    targets_in = [a for a in argv if not a.startswith("-")]

    root = git("rev-parse", "--show-toplevel", check=False)
    if not root:
        print(red("git 저장소 안에서 실행하세요."))
        return 3
    os.chdir(root)

    fetch()
    head = git("rev-parse", "HEAD")
    remote_head = git("rev-parse", "%s/%s" % (REMOTE, BRANCH))
    base = git("merge-base", "HEAD", "%s/%s" % (REMOTE, BRANCH))

    targets = resolve_targets(targets_in, base)
    if not targets:
        print(yellow("올릴 파일을 못 찾았습니다. 파일명을 인자로 주세요."))
        return 3

    header(base, head, remote_head)

    if verify:
        # Never short-circuit verify. The whole point is the post-rebase state,
        # where base == remote_head and an early "nothing moved" return would
        # look like a pass while having checked nothing.
        return mode_verify(targets, base, remote_head, hours)

    if base == remote_head:
        print(green("\n✅ 원격이 내 베이스와 같습니다 — 그 사이 아무도 안 올렸습니다."))
        return 0

    print("  그 사이 원격에 커밋 %d개가 올라왔습니다."
          % len(git("rev-list", "%s..%s" % (base, remote_head)).splitlines()))
    return mode_check(targets, base, remote_head)


if __name__ == "__main__":
    sys.exit(main())
