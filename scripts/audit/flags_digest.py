#!/usr/bin/env python3
"""Print the readability pre-pass flags for one collection, compactly.

Used by the phase-2 audit subagents so they don't have to parse the 5 MB
audit/readability_flags.json themselves.

Usage:
  python3 scripts/audit/flags_digest.py react
  python3 scripts/audit/flags_digest.py react --kind topic-article
  python3 scripts/audit/flags_digest.py python-fullstack --kind course-chapter
  python3 scripts/audit/flags_digest.py --list
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLAGS = ROOT / "audit" / "readability_flags.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("collection", nargs="?")
    ap.add_argument("--kind", action="append", default=[],
                    help="topic-article | course-chapter | question-bank | quiz-bank")
    ap.add_argument("--flags-json", default=str(FLAGS))
    ap.add_argument("--list", action="store_true", help="list available collections")
    ap.add_argument("--max-sentences", type=int, default=8)
    ap.add_argument("--max-paragraphs", type=int, default=4)
    args = ap.parse_args()

    data = json.loads(Path(args.flags_json).read_text(encoding="utf-8"))
    records = data["files"]

    if args.list:
        pairs = sorted({(r["kind"], r["collection"]) for r in records})
        for kind, coll in pairs:
            print(f"{kind:16} {coll}")
        return 0

    if not args.collection:
        ap.error("collection is required (or use --list)")

    subset = [r for r in records if r["collection"] == args.collection]
    if args.kind:
        subset = [r for r in subset if r["kind"] in args.kind]
    if not subset:
        print(f"no records for collection={args.collection} kind={args.kind or 'any'}")
        return 1

    cfg = data["config"]
    print(f"# Readability flags: {args.collection}")
    print(
        f"thresholds: sentence > {cfg['max_sentence_words']['ru']}w RU / "
        f"{cfg['max_sentence_words']['en']}w EN; paragraph > {cfg['max_para_lines']} lines "
        f"@ {cfg['para_line_chars']} chars; theory run > {cfg['max_theory_run']} paragraphs; "
        f"answer lead > {cfg['max_lead_words']}w"
    )
    print(f"abbreviation allowlist: {', '.join(cfg['abbrev_allowlist'])}")
    print("(these are mechanical candidates, not verdicts)\n")

    for r in sorted(subset, key=lambda r: r["path"]):
        m = r["metrics"]
        print(f"## {r['path']}  [{r['kind']}, {r['locale']}]")
        summary = (
            f"words={m['prose_words']} sentences={m['sentences']} "
            f"unexpanded_abbrevs={m['unexpanded_abbrevs']} "
            f"long_sentences={m['long_sentences']} ({m['long_sentence_pct']}%) "
            f"long_paragraphs={m['long_paragraphs']} theory_walls={m['theory_walls']} "
            f"caps_emphasis={m.get('caps_emphasis', 0)}"
        )
        if "indirect_leads" in m:
            summary += f" indirect_leads={m['indirect_leads']} ({m['indirect_lead_pct']}%)"
        print(summary)

        if r["unexpanded_abbrevs"]:
            print("- abbreviations whose first use in THIS file has no explanation:")
            for a in r["unexpanded_abbrevs"]:
                extra = f", in {len(a.get('entries', []))} entries" if a.get("entries") else ""
                occ = a.get("occurrences", a.get("count", 1))
                print(f"    {a['token']} ({a['kind']}, {occ}×{extra})")
                if a.get("first_sentence"):
                    print(f"      first use: {a['first_sentence']}")

        if r["long_sentences"]:
            print(f"- longest sentences (top {args.max_sentences}):")
            for s in r["long_sentences"][: args.max_sentences]:
                ref = f"[{s['ref']}] " if s.get("ref") else ""
                print(f"    {s['words']}w {ref}{s['text']}")

        if r["long_paragraphs"]:
            print(f"- longest paragraphs (top {args.max_paragraphs}):")
            for p in r["long_paragraphs"][: args.max_paragraphs]:
                ref = f"[{p['ref']}] " if p.get("ref") else ""
                print(f"    ~{p['est_lines']} lines / {p['words']}w {ref}{p['text']}")

        if r["theory_walls"]:
            print("- theory walls (paragraph runs with no code/diagram/table):")
            for w in r["theory_walls"]:
                ref = f"[{w['ref']}] " if w.get("ref") else ""
                print(f"    {w['paragraphs']} paragraphs / {w['words']}w {ref}{w['starts_with']}")

        if r.get("indirect_leads"):
            print("- answers whose first sentence does not land the answer:")
            for l in r["indirect_leads"]:
                print(f"    [{l['ref']}] {'; '.join(l['reasons'])}")
                print(f"      lead: {l['lead']}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
