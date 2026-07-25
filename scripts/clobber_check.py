"""Catch a push that silently deleted somebody else's recent work.

scripts/deploy_guard.py is the prevention: run it before uploading and it will
stop you. But it only works if the session remembers to run it, and the whole
reason this exists is that a session did not follow the process.

So this is the backstop, and it needs no cooperation at all. It runs in CI on
every push and asks one question:

    did this commit remove lines that somebody added in the last day?

That is the exact signature of a whole-file upload landing on a stale copy.
An ordinary edit removes lines that have been sitting in the file for a while.
Overwriting a file with a stale copy removes lines that appeared hours ago -
and removes them in a block, from a commit the author never saw.

False alarms are the failure mode that matters here: an alarm that fires on
normal work gets muted, and then the real one is invisible too. So:

  * whitespace, lone braces and short lines do not count
  * a line REWRITTEN IN PLACE does not count (see below)
  * fewer than MIN_LINES recovered from one commit does not count
  * bot commits (regenerated og/, data/, p/ ...) are neither victim nor culprit
  * a commit that deliberately reverts something can say so with [clobber-ok]

The rewrite exemption, added 2026-07-25 after this check cried wolf three times
in one afternoon: editing a line that arrived a few hours ago is ordinary work,
not a clobber. The original version only looked at what a commit deleted, so
`foo: "a"` -> `foo: "a", bar: "b"` read exactly like the line being erased.

The tell is whether anything took the line's place. A stale upload drops a block
and puts nothing there; an edit leaves a near-identical line at the same spot.
So a removed line is forgiven when most of it (SURVIVED) reappears among the
lines the SAME hunk added. That does mask one real case - reverting somebody's
one-line change back to the previous text - but that costs a couple of lines,
well under MIN_LINES, while the alarm this silences was firing on nearly every
honest edit. Measured on the three false alarms and one true positive from that
day, the two groups do not overlap: every honest edit scored >= 0.97, half the
lines of the real deletion scored under 0.5.

Usage:  python3 scripts/clobber_check.py [<sha>]     (default HEAD)
Exit:   0 clean   1 clobber detected   2 could not run
Writes nothing. Prints a Markdown report to stdout when it finds something.
"""

import difflib
import subprocess
import sys
from datetime import datetime, timedelta, timezone

WINDOW_HOURS = 24
MIN_LINES = 3          # lines from one victim commit before it counts
MAX_SCAN = 60          # how far back to look for victims
SURVIVED = 0.75        # share of a removed line that must reappear in its own hunk

WATCH_PREFIXES = ("index.html", "sw.js", "assets/", "worker/", "scripts/",
                  ".github/workflows/", "CLAUDE.md", "sources.json",
                  "manifest.json", "privacy.html")

BOT_AUTHORS = ("stacks-og-bot", "stacks-feed-bot", "github-actions",
               "github-actions[bot]", "dependabot")

SKIP_TOKEN = "[clobber-ok]"


def git(*args):
    p = subprocess.run(("git",) + args, capture_output=True, text=True)
    if p.returncode != 0:
        return ""
    return p.stdout.rstrip("\n")


def substantive(line):
    s = line.strip()
    if len(s) <= 3:
        return False
    if s in ("*/", "/*", "});", "})", "};", "*", "-->", "<!--"):
        return False
    return True


def watched(path):
    return any(path == p or path.startswith(p) for p in WATCH_PREFIXES)


def is_bot(author):
    return any(b in author for b in BOT_AUTHORS)


def diff_lines(sha, parent, path, sign):
    out = git("diff", "--unified=0", parent, sha, "--", path)
    marker, skip = sign, ("+++" if sign == "+" else "---")
    return [ln[1:] for ln in out.splitlines()
            if ln.startswith(marker) and not ln.startswith(skip)]


def hunks(sha, parent, path):
    """[(removed_lines, added_lines)] for each @@ hunk, in file order."""
    out = git("diff", "--unified=0", parent, sha, "--", path)
    blocks, cur = [], None
    for ln in out.splitlines():
        if ln.startswith("@@"):
            cur = ([], [])
            blocks.append(cur)
        elif cur is None:
            continue
        elif ln.startswith("-") and not ln.startswith("---"):
            cur[0].append(ln[1:])
        elif ln.startswith("+") and not ln.startswith("+++"):
            cur[1].append(ln[1:])
    return blocks


def survival(line, blob):
    """How much of `line` reappears inside `blob`, 0..1.

    Deliberately not difflib's ratio(): ratio punishes length difference, so
    splitting one line into six scores low even though every character
    survived. What matters is whether the old text is still in there."""
    sm = difflib.SequenceMatcher(None, line, blob, autojunk=False)
    return sum(b.size for b in sm.get_matching_blocks()) / max(1, len(line))


def erased(sha, parent, path):
    """Lines this commit removed and did NOT replace with a rewrite of them.

    Whatever survives here is a line that simply stopped existing - the shape a
    stale whole-file upload leaves behind. Measured against the lines added in
    the SAME hunk: position is the point. Anywhere-in-the-file matching is far
    too generous in source code, where boilerplate makes unrelated lines look
    alike and a real clobber could clear itself."""
    gone = []
    for removed, added in hunks(sha, parent, path):
        blob = "\n".join(added)
        for line in removed:
            if not substantive(line):
                continue
            if blob and survival(line, blob) >= SURVIVED:
                continue                     # edited in place, still there
            gone.append(line)
    return gone


def main():
    sha = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    sha = git("rev-parse", sha)
    if not sha:
        print("clobber_check: 커밋을 못 읽었습니다", file=sys.stderr)
        return 2

    subject = git("log", "-1", "--format=%s", sha)
    author = git("log", "-1", "--format=%an", sha)
    if SKIP_TOKEN in git("log", "-1", "--format=%B", sha):
        print("clobber_check: %s 로 명시적 되돌리기 — 검사 생략" % SKIP_TOKEN)
        return 0
    if is_bot(author):
        print("clobber_check: 봇 커밋(%s) — 검사 생략" % author)
        return 0

    parents = git("log", "-1", "--format=%P", sha).split()
    if len(parents) != 1:
        print("clobber_check: 머지/루트 커밋 — 검사 생략")
        return 0
    parent = parents[0]

    files = [f for f in git("diff", "--name-only", parent, sha).splitlines()
             if watched(f)]
    if not files:
        print("clobber_check: 감시 대상 파일 변경 없음")
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)
    recent = []
    for line in git("log", "--format=%H%x1f%an%x1f%aI%x1f%s",
                    "-n", str(MAX_SCAN), parent).splitlines():
        if not line.strip():
            continue
        h, a, when, s = line.split("\x1f", 3)
        try:
            t = datetime.fromisoformat(when).astimezone(timezone.utc)
        except ValueError:
            continue
        if t < cutoff:
            break
        if not is_bot(a):
            recent.append({"sha": h, "when": t, "subject": s})

    if not recent:
        print("clobber_check: 최근 %d시간 내 비교 대상 커밋 없음" % WINDOW_HOURS)
        return 0

    hits = []
    for path in files:
        removed = set(erased(sha, parent, path))
        if not removed:
            continue
        kept = {ln for ln in diff_lines(sha, parent, path, "+") if substantive(ln)}
        removed -= kept                      # moved, not deleted
        if not removed:
            continue
        for vic in recent:
            vp = git("log", "-1", "--format=%P", vic["sha"]).split()
            if len(vp) != 1:
                continue
            added = {ln for ln in diff_lines(vic["sha"], vp[0], path, "+")
                     if substantive(ln)}
            lost = removed & added
            if len(lost) >= MIN_LINES:
                hits.append({"path": path, "victim": vic, "lost": sorted(lost)})

    if not hits:
        print("clobber_check: 이상 없음 (감시 파일 %d개 검사)" % len(files))
        return 0

    age = lambda t: (datetime.now(timezone.utc) - t).total_seconds() / 3600
    print("## 다른 세션의 작업이 지워졌을 수 있습니다\n")
    print("커밋 **`%s`** (%s) — %s\n" % (sha[:7], author, subject))
    print("이 커밋이 지운 줄 중 일부가, 최근 %d시간 안에 다른 커밋이 **추가한** 줄입니다. "
          "GitHub 웹 업로드로 오래된 사본을 올렸을 때 나타나는 전형적인 흔적입니다.\n"
          % WINDOW_HOURS)
    for h in hits:
        v = h["victim"]
        print("### `%s` — `%s` 의 %d줄이 사라짐" % (h["path"], v["sha"][:7], len(h["lost"])))
        print("피해 커밋: %s *(%.1f시간 전)*\n" % (v["subject"], age(v["when"])))
        print("```")
        for ln in h["lost"][:8]:
            print(ln.strip()[:110])
        if len(h["lost"]) > 8:
            print("... 외 %d줄" % (len(h["lost"]) - 8))
        print("```\n")
    print("---\n")
    print("**되돌리려면**: 지워진 커밋을 다시 얹으세요.\n")
    print("```\ngit fetch origin main && git checkout main\n"
          "git show %s -- <파일> | git apply -3\n```\n" % hits[0]["victim"]["sha"][:7])
    print("의도한 되돌리기였다면 커밋 메시지에 `%s` 를 넣으면 이 검사를 건너뜁니다.\n"
          % SKIP_TOKEN)
    print("예방: 업로드 **전에** `python3 scripts/deploy_guard.py <파일들>` 을 돌리세요. "
          "이 상황을 미리 잡아줍니다.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
