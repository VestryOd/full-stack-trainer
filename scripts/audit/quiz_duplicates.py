#!/usr/bin/env python3
"""Find quiz items that ask the same thing twice.

Two thresholds matter here, and getting them wrong gives wildly different answers:

  * Comparing question text alone, with code fences stripped, reports 334 "duplicate"
    pairs — almost all of them false. Code-based items share the same stem ("What
    will be logged?") and differ only in the snippet, so stripping the code makes
    them look identical.
  * Requiring both the question AND the keyed answer to be similar, with the code
    left in, reports 37 pairs. Those are the real ones.

So: code is kept, and both halves must match.

Usage:
  python3 scripts/audit/quiz_duplicates.py
  python3 scripts/audit/quiz_duplicates.py --question 0.6 --answer 0.5   # looser
"""

from __future__ import annotations

import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUIZ_DIR = ROOT / "content" / "quiz"


def normalise(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace. Code is deliberately kept."""
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split())


def keyed_option(item: dict) -> str:
    options = (item.get("options") or {}).get("en") or []
    index = item.get("correctIndex")
    if not isinstance(index, int) or index >= len(options):
        return ""
    return options[index]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--question", type=float, default=0.7, help="question similarity floor")
    ap.add_argument("--answer", type=float, default=0.6, help="keyed answer similarity floor")
    args = ap.parse_args()

    total_pairs = 0
    total_items = 0
    for path in sorted(QUIZ_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        total_items += len(data)
        pairs = []
        for i in range(len(data)):
            for j in range(i + 1, len(data)):
                q_ratio = SequenceMatcher(
                    None,
                    normalise(data[i]["question"]["en"]),
                    normalise(data[j]["question"]["en"]),
                ).ratio()
                if q_ratio < args.question:
                    continue
                a_ratio = SequenceMatcher(
                    None, normalise(keyed_option(data[i])), normalise(keyed_option(data[j]))
                ).ratio()
                if a_ratio < args.answer:
                    continue
                pairs.append((round(q_ratio, 2), round(a_ratio, 2), data[i]["id"], data[j]["id"]))

        if pairs:
            total_pairs += len(pairs)
            print(f"{path.stem} — {len(pairs)} pair(s):")
            for q_ratio, a_ratio, left, right in sorted(pairs, reverse=True):
                print(f"    question={q_ratio}  answer={a_ratio}   {left} ~ {right}")

    print()
    print(f"{total_pairs} duplicate pairs across {total_items} items "
          f"(thresholds: question ≥ {args.question}, answer ≥ {args.answer})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
