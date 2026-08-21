#!/usr/bin/env python3
"""Spread quiz answer keys evenly across the option positions.

The generated banks put the correct answer at index 0 in 78% of all 550 items
and at index 2 or 3 in 2.5% (measured by scripts/audit/quiz_bias.py). The
per-topic quiz route renders options in file order — `shuffleOptions` in
src/lib/quiz-utils.ts only runs on the random-quiz route — so "always pick the
first option" is a working strategy for a reader who knows nothing.

This script rotates each item's correct answer to a target position assigned
round-robin, keeping the other options in their relative order and permuting the
`ru` list identically to `en`.

Two kinds of item are left untouched, because their options depend on order:
  * an option like "All of the above" / "Все вышеперечисленное", which has to
    stay last;
  * options that label themselves ("Option A — it directly instantiates …"),
    where the letters refer to labelled code in the question.

Usage:
  python3 scripts/audit/rebalance_quiz_keys.py            # dry run
  python3 scripts/audit/rebalance_quiz_keys.py --apply
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUIZ_DIR = ROOT / "content" / "quiz"

# Only options that literally point at other positions. "Both use O(d) space" and
# "Both requests share the same instance" are ordinary distractors, not this.
ORDER_DEPENDENT = re.compile(
    r"all of the above|none of the above|both of the above|all of these|any of the above|"
    r"\bboth a and b\b|\boptions? [A-D] and [A-D]\b|"
    r"вс[её] (?:вышеперечисленн|перечисленн|указанн|из перечисленн)|"
    r"ни один из (?:перечисленн|вышеперечисленн|указанн)|"
    r"вс[её] варианты (?:выше|верны)|оба варианта выше",
    re.I,
)
SELF_LABELLED = re.compile(r"^\s*(?:Option|Вариант)\s+[A-D0-9]\b", re.I)


def is_locked(q: dict) -> str | None:
    """Return a reason if this item's option order must not change."""
    options = list(q["options"].get("en") or []) + list(q["options"].get("ru") or [])
    if any(ORDER_DEPENDENT.search(o) for o in options):
        return "order-dependent option"
    if any(SELF_LABELLED.match(o) for o in options):
        return "self-labelled options"
    return None


def rotate(options: list[str], src: int, dst: int) -> list[str]:
    """Move options[src] to position dst, keeping the rest in relative order."""
    rest = options[:src] + options[src + 1 :]
    return rest[:dst] + [options[src]] + rest[dst:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    moved = locked = 0
    before, after = Counter(), Counter()

    for path in sorted(QUIZ_DIR.glob("*.json")):
        raw = path.read_text(encoding="utf-8")
        trailing_nl = raw.endswith("\n")
        data = json.loads(raw)
        target = 0

        for q in data:
            en = q["options"]["en"]
            src = q["correctIndex"]
            before[src] += 1

            reason = is_locked(q)
            if reason:
                locked += 1
                after[src] += 1
                print(f"  skip {q['id']}: {reason}")
                continue

            dst = target % len(en)
            target += 1
            after[dst] += 1
            if dst == src:
                continue

            for locale in ("en", "ru"):
                opts = q["options"].get(locale)
                if not opts:
                    continue
                assert len(opts) == len(en), f"{q['id']}: {locale} has a different option count"
                q["options"][locale] = rotate(opts, src, dst)
            q["correctIndex"] = dst
            moved += 1

        if args.apply:
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + ("\n" if trailing_nl else ""),
                encoding="utf-8",
            )

    total = sum(before.values())
    print(f"\n{'APPLIED' if args.apply else 'DRY RUN'}: moved {moved} keys, left {locked} untouched")
    print("position of the correct answer:")
    for i in range(4):
        b = 100 * before[i] / total
        a = 100 * after[i] / total
        print(f"  index {i}: {before[i]:4} ({b:4.1f}%)  ->  {after[i]:4} ({a:4.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
