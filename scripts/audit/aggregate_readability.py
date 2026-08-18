#!/usr/bin/env python3
"""Aggregate the per-zone readability reports into audit/readability-report.md.

Reads every audit/readability/*.json written by the phase-2 zone auditors and
emits the score tables, the abbreviation roll-up and the full list of concrete
"before / after" fixes.

The hand-written synthesis (target reader, systemic patterns, top-20 priorities)
lives in audit/readability/SYNTHESIS.md and is inlined at the top, so re-running
this script after more zones land never overwrites the analysis.

Usage: python3 scripts/audit/aggregate_readability.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ZONES_DIR = ROOT / "audit" / "readability"
FLAGS_JSON = ROOT / "audit" / "readability_flags.json"
SYNTHESIS = ZONES_DIR / "SYNTHESIS.md"
OUT = ROOT / "audit" / "readability-report.md"

RUBRIC = ("A", "B", "C", "D", "E", "F", "G")
RUBRIC_NAMES = {
    "A": "термины и аббревиатуры",
    "B": "синтаксис предложений",
    "C": "первое предложение (пирамида)",
    "D": "плотность концепций",
    "E": "код-примеры",
    "F": "английская версия (B1-B2)",
    "G": "русская версия",
}
VERDICT_RU = {
    "ok": "ok",
    "targeted-fixes": "точечные правки",
    "systemic-refactor": "системный рефактор",
}


def md_table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join("" if c is None else str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def load_zones() -> list[dict]:
    zones = []
    for path in sorted(ZONES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["_file"] = path.name
        zones.append(data)
    return zones


def mean(values: list[float]) -> float | None:
    vals = [v for v in values if isinstance(v, (int, float))]
    return round(sum(vals) / len(vals), 2) if vals else None


def zone_label(z: dict) -> str:
    kinds = z.get("kinds") or []
    suffix = {
        "topic-article": "статьи",
        "course-chapter": "курс",
        "question-bank": "вопросы",
        "quiz-bank": "quiz",
    }
    tags = "+".join(suffix.get(k, k) for k in kinds)
    return f"{z['zone']} ({tags})"


def locale_split(z: dict) -> dict[str, dict[str, float | None]]:
    """Per-locale averages, so an EN-only or RU-only problem stays visible."""
    out = {}
    for loc in ("ru", "en"):
        files = [f for f in z.get("files", []) if f.get("locale") == loc]
        if not files:
            continue
        out[loc] = {
            k: mean([f.get("scores", {}).get(k) for f in files]) for k in RUBRIC
        }
    return out


def main() -> int:
    zones = load_zones()
    if not zones:
        print("no zone reports in audit/readability/")
        return 1

    flags = json.loads(FLAGS_JSON.read_text(encoding="utf-8")) if FLAGS_JSON.exists() else None
    flag_by_coll: dict[tuple[str, str], dict] = {}
    if flags:
        for r in flags["files"]:
            slot = flag_by_coll.setdefault(
                (r["kind"], r["collection"]), {"words": 0, "flags": 0, "files": 0}
            )
            slot["words"] += r["metrics"]["prose_words"]
            slot["flags"] += r["metrics"]["flags_total"]
            slot["files"] += 1

    L: list[str] = []
    if SYNTHESIS.exists():
        L.append(SYNTHESIS.read_text(encoding="utf-8").rstrip())
        L.append("")

    # ---- score table -------------------------------------------------------
    L.append("## Оценки по зонам (от худших)\n")
    L.append(
        "Шкала 1-5: **1** — мешает понимать, **3** — заметно, но читаемо, **5** — чисто для "
        "целевого читателя. `—` = критерий неприменим (F только для en, G только для ru).\n"
    )
    rows = []
    for z in zones:
        avg = z.get("averages", {})
        overall = mean([avg.get(k) for k in RUBRIC])
        fl = None
        for k in z.get("kinds") or []:
            hit = flag_by_coll.get((k, z["zone"]))
            if hit and hit["words"]:
                fl = round(1000 * hit["flags"] / hit["words"], 1)
                break
        rows.append(
            [zone_label(z), len(z.get("files", []))]
            + [avg.get(k, "—") for k in RUBRIC]
            + [overall, fl if fl is not None else "", VERDICT_RU.get(z["verdict"], z["verdict"])]
        )
    rows.sort(key=lambda r: (r[-3] if isinstance(r[-3], (int, float)) else 99))
    L.append(
        md_table(
            ["зона", "файлов"] + list(RUBRIC) + ["средняя", "флагов/1k", "вердикт"],
            rows,
        )
    )
    L.append("")

    # ---- per-rubric aggregate ---------------------------------------------
    L.append("### Средняя по критериям на всех проверенных зонах\n")
    agg_rows = []
    for k in RUBRIC:
        vals = [z.get("averages", {}).get(k) for z in zones]
        vals = [v for v in vals if isinstance(v, (int, float))]
        worst = sorted(
            [(z.get("averages", {}).get(k), zone_label(z)) for z in zones
             if isinstance(z.get("averages", {}).get(k), (int, float))]
        )[:3]
        agg_rows.append(
            [
                k,
                RUBRIC_NAMES[k],
                round(sum(vals) / len(vals), 2) if vals else "—",
                min(vals) if vals else "—",
                max(vals) if vals else "—",
                ", ".join(f"{name} ({score})" for score, name in worst),
            ]
        )
    L.append(md_table(["", "критерий", "средняя", "мин", "макс", "худшие зоны"], agg_rows))
    L.append("")

    # ---- RU vs EN ----------------------------------------------------------
    L.append("### RU против EN по зонам\n")
    rows = []
    for z in zones:
        split = locale_split(z)
        if len(split) < 2:
            continue
        ru, en = split["ru"], split["en"]
        ru_all = mean([ru[k] for k in "ABCDE"])
        en_all = mean([en[k] for k in "ABCDE"])
        rows.append(
            [
                zone_label(z),
                ru_all,
                en_all,
                round(en_all - ru_all, 2) if (ru_all and en_all) else "",
                ru.get("B"),
                en.get("B"),
                en.get("F"),
                ru.get("G"),
            ]
        )
    rows.sort(key=lambda r: r[3] if isinstance(r[3], (int, float)) else 0)
    L.append(
        md_table(
            ["зона", "RU (A-E)", "EN (A-E)", "EN − RU", "B ru", "B en", "F (en)", "G (ru)"],
            rows,
        )
    )
    L.append(
        "\nОтрицательное «EN − RU» = английская версия хуже русской по одинаково применимым "
        "критериям A-E.\n"
    )

    # ---- patterns ----------------------------------------------------------
    L.append("## Наблюдения аудиторов по зонам\n")
    for z in sorted(zones, key=lambda z: zone_label(z)):
        L.append(f"### {zone_label(z)} — {VERDICT_RU.get(z['verdict'], z['verdict'])}\n")
        for p in z.get("patterns", []):
            L.append(f"- {p}")
        if z.get("notes"):
            L.append(f"\n**Прочее:** {z['notes']}")
        L.append("")

    # ---- abbreviations -----------------------------------------------------
    L.append("## Нерасшифрованные аббревиатуры по файлам\n")
    L.append(
        "Списки проверены аудиторами вручную (ложные срабатывания препасса убраны, пропущенное "
        "добавлено). Аббревиатура попадает сюда, если её первое использование **в этом файле** "
        "не объяснено.\n"
    )
    total_files = 0
    total_tokens = 0
    for z in sorted(zones, key=lambda z: zone_label(z)):
        abbr = z.get("unexpanded_abbrevs") or {}
        if not abbr:
            continue
        L.append(f"<details>\n<summary>{zone_label(z)} — {len(abbr)} файлов</summary>\n")
        for file, tokens in sorted(abbr.items()):
            total_files += 1
            total_tokens += len(tokens)
            L.append(f"- `{file}`: {', '.join(tokens)}")
        L.append("\n</details>\n")
    L.insert(
        len(L) - 0,
        f"Итого: {total_tokens} нерасшифрованных первых упоминаний в {total_files} файлах.\n",
    )

    # ---- concrete fixes ----------------------------------------------------
    L.append("## Все конкретные места «до / после»\n")
    L.append(
        "Полный список от аудиторов, сгруппирован по зонам. Каждое «после» сохраняет все "
        "технические утверждения из «до» — правится только язык.\n"
    )
    n = 0
    for z in sorted(zones, key=lambda z: zone_label(z)):
        places = z.get("worst_places") or []
        if not places:
            continue
        L.append(f"### {zone_label(z)}\n")
        for p in places:
            n += 1
            L.append(f"**{n}. `{p.get('file', '?')}` — критерий {p.get('rubric', '?')}**\n")
            L.append(f"*Проблема:* {p.get('problem', '')}\n")
            before = (p.get("before") or p.get("quote") or "").strip()
            after = (p.get("after") or "").strip()
            L.append("До:\n")
            L.append("```")
            L.append(before)
            L.append("```")
            L.append("После:\n")
            L.append("```")
            L.append(after)
            L.append("```\n")
    OUT.write_text("\n".join(L), encoding="utf-8")

    zones_by_verdict: dict[str, int] = {}
    for z in zones:
        zones_by_verdict[z["verdict"]] = zones_by_verdict.get(z["verdict"], 0) + 1
    files = sum(len(z.get("files", [])) for z in zones)
    print(f"zones: {len(zones)} ({', '.join(f'{k}={v}' for k, v in sorted(zones_by_verdict.items()))})")
    print(f"files scored: {files}")
    print(f"before/after fixes: {n}")
    print(f"unexpanded abbrevs: {total_tokens} across {total_files} files")
    print(f"→ {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
