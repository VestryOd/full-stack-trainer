#!/usr/bin/env python3
"""Report fenced blocks that are too wide for a phone.

`diagram_check.py` only inspects blocks containing a `┌`, so it never sees a
two-column `txt` layout built out of spaces and pipes — and those are exactly
what slides off the screen, because the site renders every fence in a
horizontally scrolling `<pre>`. Nine such blocks survived a whole language wave
in one zone because no committed script measured them.

Budgets, from content/STYLE.md:
  txt / text / no tag   68 columns   (prose or diagrams a reader must read)
  everything else       92 columns   (code, §6)

Usage:
  python3 scripts/audit/block_width.py content/topics
  python3 scripts/audit/block_width.py content/topics/react --quiet
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

PROSE_TAGS = {"", "txt", "text"}
PROSE_BUDGET = 68
CODE_BUDGET = 92

FENCE_RE = re.compile(r"^```([A-Za-z0-9+#-]*)\s*$")


def walk(path: Path):
    if path.is_file():
        yield path
        return
    yield from sorted(path.rglob("*.md"))
    yield from sorted(path.rglob("*.json"))


def lines_of(path: Path):
    """(label, text) per fenced-block host: one per markdown file, one per
    locale-field of a JSON bank or quiz.

    Banks were invisible to this tool until now — it only walked *.md, so the
    code fences inside `answer` and `explanation` were never measured. They are
    rendered by the same component as an article body, in the same scrolling
    <pre>, so they get the same budget.
    """
    if path.suffix == ".md":
        yield "", path.read_text(encoding="utf-8")
        return
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, dict) or "id" not in item:
            continue
        for field in ("question", "answer", "explanation"):
            value = item.get(field)
            if not isinstance(value, dict):
                continue
            for locale in ("en", "ru"):
                text = value.get(locale)
                if isinstance(text, str):
                    yield f"{item['id']}.{field}.{locale}", text


def check_text(text: str) -> list[tuple[int, int, str, str]]:
    """[(line_no, width, tag, line), ...] for every line over its budget."""
    out: list[tuple[int, int, str, str]] = []
    tag: str | None = None
    for n, line in enumerate(text.splitlines(), 1):
        fence = FENCE_RE.match(line)
        if fence:
            tag = fence.group(1).lower() if tag is None else None
            continue
        if tag is None:
            continue
        budget = PROSE_BUDGET if tag in PROSE_TAGS else CODE_BUDGET
        if len(line) > budget:
            out.append((n, len(line), tag or "txt", line))
    return out


def check(path: Path) -> list[tuple[str, int, int, str, str]]:
    out = []
    for label, text in lines_of(path):
        out += [(label, *row) for row in check_text(text)]
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    target = Path(sys.argv[1])
    quiet = "--quiet" in sys.argv

    per_zone: Counter[str] = Counter()
    total = files = 0
    for md in walk(target):
        wide = check(md)
        if not wide:
            continue
        files += 1
        total += len(wide)
        parts = md.parts
        if "topics" in parts:
            zone = parts[parts.index("topics") + 1]
        elif md.suffix == ".json":
            zone = f"{md.parent.name}/{md.stem}"
        else:
            zone = md.parent.name
        per_zone[zone] += len(wide)
        if not quiet:
            print(f"{md}")
            for label, n, width, tag, line in wide:
                where = f"{label}:{n}" if label else f":{n}"
                print(f"  {where} {width} cols ({tag}) {line[:60]}")

    if per_zone:
        print("\nwide lines by zone:")
        for zone, n in per_zone.most_common():
            print(f"  {zone:24} {n}")
    print(f"\n{total} lines over budget in {files} files")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
