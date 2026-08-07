#!/usr/bin/env python3
"""Quality gates for cards entering the automatic publishing queue.

The publisher writes three language versions. A card that has only a headline
and two short paragraphs is technically valid JSON, but it is not a useful
Stacks reading. Keep this check independent of the renderer so the same rule
can be used by the queue merge and by local validation.
"""

import re


# Characters, not words: this keeps the gate fair across Korean, English and
# Japanese. These are deliberately below the depth of a good feature card but
# above the "headline + two paragraphs" cards that prompted the gate.
MIN_GIST_CHARS = {"ko": 700, "en": 800, "ja": 600}
MIN_PROSE_PARAGRAPHS = 5


def plain_text(text):
    """Remove data markers while keeping real prose and subheading text."""
    out = []
    for line in str(text or "").split("\n"):
        if line.startswith("## "):
            out.append(line[3:].strip())
        elif line.startswith("@@"):
            continue
        else:
            out.append(line)
    return "\n".join(out)


def prose_paragraphs(text):
    """Count meaningful prose paragraphs, excluding headings and short labels."""
    chunks = re.split(r"\n\s*\n", plain_text(text))
    count = 0
    for chunk in chunks:
        lines = [line.strip() for line in chunk.split("\n") if line.strip()]
        if not lines:
            continue
        if len(lines) == 1 and lines[0].startswith("## "):
            continue
        if len(" ".join(lines)) >= 45:
            count += 1
    return count


def depth_report(item):
    """Return human-readable depth failures; an empty list means it passes."""
    gist = item.get("gist") or {}
    failures = []
    for lang, minimum in MIN_GIST_CHARS.items():
        text = plain_text(gist.get(lang) or "")
        chars = len(re.sub(r"\s+", "", text))
        paras = prose_paragraphs(gist.get(lang) or "")
        if chars < minimum:
            failures.append("%s %d/%d chars" % (lang, chars, minimum))
        if paras < MIN_PROSE_PARAGRAPHS:
            failures.append("%s %d/%d prose paragraphs" %
                            (lang, paras, MIN_PROSE_PARAGRAPHS))
    return failures


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) != 2:
        raise SystemExit("usage: card_quality.py item.json")
    with open(sys.argv[1], encoding="utf-8") as fh:
        item = json.load(fh)
    errors = depth_report(item)
    if errors:
        print("FAIL: " + "; ".join(errors))
        raise SystemExit(1)
    print("PASS")
