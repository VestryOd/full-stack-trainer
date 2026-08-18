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


def longest_index(options: list[str]) -> int | None:
    if not options:
        return None
    return max(range(len(options)), key=lambda i: len(options[i]))


def main() -> int:
    header = (
        f"{'bank':18} {'n':>3} {'idx0':>5} {'idx1':>5} {'idx2':>5} {'idx3':>5} "
        f"{'longest':>8} {'first+longest':>14}"
    )
    print(header)
    print("-" * len(header))

    totals = Counter()
    total_items = total_longest = total_both = 0

    for path in sorted(QUIZ_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        positions = Counter(q.get("correctIndex") for q in data)
        longest = both = 0
        for q in data:
            options = (q.get("options") or {}).get("en") or []
            li = longest_index(options)
            if li is not None and li == q.get("correctIndex"):
                longest += 1
                if q.get("correctIndex") == 0:
                    both += 1
        totals += positions
        total_items += len(data)
        total_longest += longest
        total_both += both
        print(
            f"{path.stem:18} {len(data):3} {positions[0]:5} {positions[1]:5} "
            f"{positions[2]:5} {positions[3]:5} {longest:8} {both:14}"
        )

    print("-" * len(header))
    print(
        f"{'TOTAL':18} {total_items:3} {totals[0]:5} {totals[1]:5} {totals[2]:5} "
        f"{totals[3]:5} {total_longest:8} {total_both:14}"
    )
    print()
    print(f"correctIndex == 0:            {100 * totals[0] / total_items:.1f}% (random ≈ 25%)")
    print(f"correct option is longest:    {100 * total_longest / total_items:.1f}%")
    print(f"both (pick first, it's longest): {100 * total_both / total_items:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
