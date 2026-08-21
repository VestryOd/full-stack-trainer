#!/usr/bin/env python3
"""Merge per-agent patch files into a question bank.

Several agents work one bank at once. If each did read-mutate-write on the content
file, the last writer would silently drop the others' work — so each agent writes a
patch file holding only its own entries, and this merges them.

Patch shape:

    { "<id>": { "question": {"en": …, "ru": …}, "answer": {"en": …, "ru": …} } }

`question` is optional. Both locales must be present in any field that appears, so
a wholesale field replace cannot drop a locale.

Usage:
  python3 scripts/audit/merge_patch.py content/questions/nodejs.json /tmp/p2.json /tmp/p3.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 1

    target = Path(sys.argv[1])
    patches = sys.argv[2:]

    raw = target.read_text(encoding="utf-8")
    trailing = raw.endswith("\n")
    data = json.loads(raw)
    by_id = {q["id"]: q for q in data}

    applied = 0
    for patch_file in patches:
        patch = json.loads(Path(patch_file).read_text(encoding="utf-8"))
        for qid, fields in patch.items():
            assert qid in by_id, f"{patch_file}: unknown id {qid}"
            for field in ("question", "answer"):
                if field not in fields:
                    continue
                for locale in ("en", "ru"):
                    assert locale in fields[field], f"{qid}.{field}: locale {locale} missing"
                    assert fields[field][locale].strip(), f"{qid}.{field}.{locale} is empty"
                by_id[qid][field] = fields[field]
            applied += 1
        print(f"  {patch_file}: {len(patch)} entries")

    target.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + ("\n" if trailing else ""),
        encoding="utf-8",
    )
    print(f"merged {applied} entries; file holds {len(data)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
