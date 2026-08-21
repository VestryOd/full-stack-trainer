#!/usr/bin/env python3
"""Measure how guessable the quiz banks are without knowing the subject.

Two biases introduced by the generation template:
  1. position — where `correctIndex` sits (random would be ~25% per slot)
  2. length   — whether the correct option is simply the longest one

Both matter to the reader: `shuffleOptions` (src/lib/quiz-utils.ts) is applied
only on the random-quiz route, so on a topic quiz the options render in file
order and the position bias is directly exploitable.

Usage: python3 scripts/audit/quiz_bias.py
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUIZ_DIR = ROOT / "content" / "quiz"


def is_longest(options: list[str], index: int) -> bool:
    """True if the option at `index` is among the longest.

    Ties count: if the correct option shares the maximum length with another, the
    "pick the longest" strategy still lands on it part of the time. Taking only
    the first maximal index (what an earlier version of this script did) hid 13%
    of the corpus behind ties and understated the bias.
    """
    if not options:
        return False
    return len(options[index]) == max(len(o) for o in options)


def is_shortest(options: list[str], index: int) -> bool:
    """True if the option at `index` is among the shortest — the inverse tell."""
    if not options:
        return False
    return len(options[index]) == min(len(o) for o in options)


def main() -> int:
    header = (
        f"{'bank':18} {'n':>3} {'idx0':>5} {'idx1':>5} {'idx2':>5} {'idx3':>5} "
        f"{'longest':>8} {'shortest':>9} {'first+long':>11}"
    )
    print(header)
    print("-" * len(header))

    totals = Counter()
    total_items = total_longest = total_shortest = total_both = 0

    for path in sorted(QUIZ_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        positions = Counter(q.get("correctIndex") for q in data)
        longest = shortest = both = 0
        for q in data:
            options = (q.get("options") or {}).get("en") or []
            index = q.get("correctIndex")
            if not isinstance(index, int) or index >= len(options):
                continue
            if is_longest(options, index):
                longest += 1
                if index == 0:
                    both += 1
            if is_shortest(options, index):
                shortest += 1
        totals += positions
        total_items += len(data)
        total_longest += longest
        total_shortest += shortest
        total_both += both
        print(
            f"{path.stem:18} {len(data):3} {positions[0]:5} {positions[1]:5} "
            f"{positions[2]:5} {positions[3]:5} {longest:8} {shortest:9} {both:11}"
        )

    print("-" * len(header))
    print(
        f"{'TOTAL':18} {total_items:3} {totals[0]:5} {totals[1]:5} {totals[2]:5} "
        f"{totals[3]:5} {total_longest:8} {total_shortest:9} {total_both:11}"
    )
    print()
    print("Blind strategies — each should sit near the 25% random baseline:")
    print(f"  pick index 0:              {100 * totals[0] / total_items:5.1f}%")
    print(f"  pick the longest option:   {100 * total_longest / total_items:5.1f}%")
    print(f"  pick the shortest option:  {100 * total_shortest / total_items:5.1f}%")
    print(f"  pick index 0 AND longest:  {100 * total_both / total_items:5.1f}%")
    skip_longest = (1 - total_longest / total_items) / 3
    print(f"  drop the longest, guess:   {100 * skip_longest:5.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
