#!/usr/bin/env python3
"""Content inventory for full-stack-trainer.

Walks content/topics, content/courses, content/questions, content/quiz,
content/tasks and produces:
  audit/inventory.json  — raw data for later audit phases
  audit/inventory.md    — human-readable tables

Read-only: never writes inside content/.

Usage: python3 scripts/audit/inventory.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "content"
TOPICS_DIR = CONTENT / "topics"
COURSES_DIR = CONTENT / "courses"
QUESTIONS_DIR = CONTENT / "questions"
QUIZ_DIR = CONTENT / "quiz"
TASKS_DIR = CONTENT / "tasks"
AUDIT = ROOT / "audit"

LOCALES = ("ru", "en")

# topicId -> folder name under content/topics, mirrored from src/lib/content.ts
FOLDER_OVERRIDES = {"bundlers": "build-tools", "ci-cd": "ci-cd"}

# Two generations of template are in use: the newer "Common pitfall / Частая ловушка"
# and the older "Common interview trap / Типичная ошибка на интервью". Searching for
# only the first produced false "missing pitfall" reports for whole banks (prisma,
# react senior tier, nodejs q-21..58).
PITFALL_MARKERS = {
    "en": ("Common pitfall", "Common interview trap", "Gotcha", "Common mistake"),
    "ru": ("Частая ловушка", "Типичная ошибка", "Ловушка", "Распространённая ошибка"),
}

FENCE_RE = re.compile(r"```.*?(?:```|\Z)", re.DOTALL)
MD_LINK_RE = re.compile(r"\[([^\]\n]{1,120})\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
# bare bracket reference: [Some Title] not followed by ( or [ or :
BARE_REF_RE = re.compile(r"(?<![\]\)`])\[([A-ZА-ЯЁ][^\]\n]{3,80})\](?![\(\[:])")
WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9_'\-]+")


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def strip_code(text: str) -> str:
    """Remove fenced code blocks (and inline code) — leaves prose."""
    text = FENCE_RE.sub(" ", text)
    return re.sub(r"`[^`\n]*`", " ", text)


def count_words(text: str) -> int:
    return len(WORD_RE.findall(text))


def strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :]
    return text


def topic_folder(topic_id: str) -> str:
    return FOLDER_OVERRIDES.get(topic_id, topic_id)


def load_registry(rel: str, kind: str) -> list[dict]:
    """Parse src/constants/{topics,courses}.ts entries without running TS."""
    src = read(ROOT / rel)
    entries = []
    for m in re.finditer(
        r"\{\s*id:\s*'([^']+)',\s*label:\s*'([^']+)',\s*level:\s*'([^']+)'\s*\}", src
    ):
        entries.append({"id": m.group(1), "label": m.group(2), "level": m.group(3), "kind": kind})
    return entries


def load_json(path: Path):
    try:
        return json.loads(read(path)), None
    except Exception as exc:  # malformed JSON is itself a finding
        return None, f"{type(exc).__name__}: {exc}"


def both_locales(field) -> tuple[bool, bool]:
    """Return (has_en, has_ru) for a {en, ru} field."""
    if not isinstance(field, dict):
        return False, False
    return bool(str(field.get("en", "")).strip()), bool(str(field.get("ru", "")).strip())


# ----------------------------------------------------------------------------
# topics / courses (markdown)
# ----------------------------------------------------------------------------

def scan_md_collection(base: Path, registry: list[dict], kind: str) -> list[dict]:
    """Scan a folder of `<id>/<locale>/*.md` collections."""
    reg_by_id = {e["id"]: e for e in registry}
    ids_on_disk = sorted(p.name for p in base.iterdir() if p.is_dir()) if base.exists() else []

    # folder name -> registry id (registry ids may be remapped)
    folder_to_id = {topic_folder(e["id"]): e["id"] for e in registry}

    items = []
    for folder in ids_on_disk:
        item_id = folder_to_id.get(folder, folder)
        reg = reg_by_id.get(item_id)
        files: dict[str, dict] = {}
        for locale in LOCALES:
            ldir = base / folder / locale
            if not ldir.exists():
                continue
            for f in sorted(ldir.glob("*.md")):
                slug = f.stem
                raw = read(f)
                body = strip_frontmatter(raw)
                prose = strip_code(body)
                h1_match = re.search(r"^#\s+(.+)$", body, re.M)
                h1 = h1_match.group(1).strip() if h1_match else None
                entry = files.setdefault(slug, {"slug": slug, "locales": {}})
                entry["locales"][locale] = {
                    "path": str(f.relative_to(ROOT)),
                    "h1": h1,
                    # RU file whose title has no Cyrillic at all → untranslated heading
                    "h1_untranslated": bool(
                        locale == "ru" and h1 and not re.search(r"[А-Яа-яЁё]", h1)
                    ),
                    "verified_marker": bool(re.search(r"<!--\s*verified:", raw)),
                    "words_total": count_words(body),
                    "words_prose": count_words(prose),
                    "code_blocks": len(re.findall(r"^```", body, re.M)) // 2,
                    "headings": len(re.findall(r"^#{1,6} ", body, re.M)),
                    "bytes": f.stat().st_size,
                }
        file_list = [files[s] for s in sorted(files)]
        desync = [
            {
                "slug": e["slug"],
                "present": sorted(e["locales"]),
                "missing": [l for l in LOCALES if l not in e["locales"]],
            }
            for e in file_list
            if len(e["locales"]) < 2
        ]
        words = {
            l: sum(e["locales"][l]["words_total"] for e in file_list if l in e["locales"])
            for l in LOCALES
        }
        prose_words = {
            l: sum(e["locales"][l]["words_prose"] for e in file_list if l in e["locales"])
            for l in LOCALES
        }
        items.append(
            {
                "id": item_id,
                "folder": folder,
                "kind": kind,
                "label": reg["label"] if reg else None,
                "level": reg["level"] if reg else None,
                "in_registry": reg is not None,
                "articles": len(file_list),
                "files": file_list,
                "desync": desync,
                "has_interview_questions": any("interview-question" in e["slug"] for e in file_list),
                "words": words,
                "prose_words": prose_words,
                "ru_untranslated_h1": [
                    e["slug"]
                    for e in file_list
                    if e["locales"].get("ru", {}).get("h1_untranslated")
                ],
                "verified_files": sum(
                    1
                    for e in file_list
                    for loc in e["locales"].values()
                    if loc["verified_marker"]
                ),
                "total_locale_files": sum(len(e["locales"]) for e in file_list),
            }
        )

    for e in registry:
        if topic_folder(e["id"]) not in ids_on_disk:
            items.append(
                {
                    "id": e["id"],
                    "folder": topic_folder(e["id"]),
                    "kind": kind,
                    "label": e["label"],
                    "level": e["level"],
                    "in_registry": True,
                    "articles": 0,
                    "files": [],
                    "desync": [],
                    "has_interview_questions": False,
                    "words": {l: 0 for l in LOCALES},
                    "prose_words": {l: 0 for l in LOCALES},
                    "ru_untranslated_h1": [],
                    "verified_files": 0,
                    "total_locale_files": 0,
                }
            )
    return sorted(items, key=lambda i: i["id"])


# ----------------------------------------------------------------------------
# questions / quiz / tasks (json)
# ----------------------------------------------------------------------------

def scan_questions() -> list[dict]:
    banks = []
    for path in sorted(QUESTIONS_DIR.glob("*.json")):
        data, err = load_json(path)
        bank = {
            "id": path.stem,
            "path": str(path.relative_to(ROOT)),
            "parse_error": err,
            "count": 0,
            "by_difficulty": {},
            "missing_locale": [],
            "missing_pitfall": [],
            "missing_id": 0,
            "topic_id_mismatch": [],
            "words": {l: 0 for l in LOCALES},
            "answer_words": {l: [] for l in LOCALES},
        }
        if data is None:
            banks.append(bank)
            continue
        diffs = Counter()
        for idx, q in enumerate(data):
            qid = q.get("id") or f"{path.stem}#{idx}"
            if not q.get("id"):
                bank["missing_id"] += 1
            diffs[q.get("difficulty", "<none>")] += 1
            if q.get("topicId") and q["topicId"] != path.stem:
                bank["topic_id_mismatch"].append({"ref": qid, "topicId": q["topicId"]})
            gaps = []
            for field in ("question", "answer"):
                has_en, has_ru = both_locales(q.get(field))
                if not has_en:
                    gaps.append(f"{field}.en")
                if not has_ru:
                    gaps.append(f"{field}.ru")
            if gaps:
                bank["missing_locale"].append({"ref": qid, "gaps": gaps})
            ans = q.get("answer") if isinstance(q.get("answer"), dict) else {}
            no_pitfall = []
            for locale in LOCALES:
                text = str(ans.get(locale, ""))
                bank["words"][locale] += count_words(strip_code(text))
                bank["answer_words"][locale].append(count_words(strip_code(text)))
                if not any(m in text for m in PITFALL_MARKERS[locale]):
                    no_pitfall.append(locale)
            if no_pitfall:
                bank["missing_pitfall"].append({"ref": qid, "locales": no_pitfall})
        bank["count"] = len(data)
        bank["by_difficulty"] = dict(diffs)
        for locale in LOCALES:
            lens = bank["answer_words"][locale]
            bank[f"avg_answer_words_{locale}"] = round(sum(lens) / len(lens)) if lens else 0
        del bank["answer_words"]
        banks.append(bank)
    return banks


def scan_quiz() -> list[dict]:
    banks = []
    for path in sorted(QUIZ_DIR.glob("*.json")):
        data, err = load_json(path)
        bank = {
            "id": path.stem,
            "path": str(path.relative_to(ROOT)),
            "parse_error": err,
            "count": 0,
            "missing_locale": [],
            "option_count_mismatch": [],
            "bad_correct_index": [],
            "words": {l: 0 for l in LOCALES},
        }
        if data is None:
            banks.append(bank)
            continue
        for idx, q in enumerate(data):
            qid = q.get("id") or f"{path.stem}#{idx}"
            gaps = []
            for field in ("question", "explanation"):
                has_en, has_ru = both_locales(q.get(field))
                if not has_en:
                    gaps.append(f"{field}.en")
                if not has_ru:
                    gaps.append(f"{field}.ru")
            opts = q.get("options") if isinstance(q.get("options"), dict) else {}
            en_opts, ru_opts = opts.get("en") or [], opts.get("ru") or []
            for locale, arr in (("en", en_opts), ("ru", ru_opts)):
                if not arr:
                    gaps.append(f"options.{locale}")
            if gaps:
                bank["missing_locale"].append({"ref": qid, "gaps": gaps})
            if en_opts and ru_opts and len(en_opts) != len(ru_opts):
                bank["option_count_mismatch"].append(
                    {"ref": qid, "en": len(en_opts), "ru": len(ru_opts)}
                )
            ci = q.get("correctIndex")
            if not isinstance(ci, int) or not (0 <= ci < max(len(en_opts), len(ru_opts) or 0)):
                bank["bad_correct_index"].append({"ref": qid, "correctIndex": ci})
            for locale in LOCALES:
                text = " ".join(
                    [
                        str((q.get("question") or {}).get(locale, "")),
                        str((q.get("explanation") or {}).get(locale, "")),
                        " ".join(str(o) for o in (opts.get(locale) or [])),
                    ]
                )
                bank["words"][locale] += count_words(strip_code(text))
        bank["count"] = len(data)
        banks.append(bank)
    return banks


def scan_tasks() -> list[dict]:
    banks = []
    for path in sorted(TASKS_DIR.glob("*.json")):
        data, err = load_json(path)
        bank = {
            "id": path.stem,
            "path": str(path.relative_to(ROOT)),
            "parse_error": err,
            "count": 0,
            "by_difficulty": {},
            "missing_locale": [],
            "missing_solution": [],
            "words": {l: 0 for l in LOCALES},
        }
        if data is None:
            banks.append(bank)
            continue
        diffs = Counter()
        for idx, t in enumerate(data):
            tid = t.get("id") or f"{path.stem}#{idx}"
            diffs[t.get("difficulty", "<none>")] += 1
            gaps = []
            for field in ("title", "description", "solutionExplanation"):
                has_en, has_ru = both_locales(t.get(field))
                if not has_en:
                    gaps.append(f"{field}.en")
                if not has_ru:
                    gaps.append(f"{field}.ru")
            if gaps:
                bank["missing_locale"].append({"ref": tid, "gaps": gaps})
            if not str(t.get("solution", "")).strip():
                bank["missing_solution"].append(tid)
            for locale in LOCALES:
                text = " ".join(
                    str((t.get(f) or {}).get(locale, ""))
                    for f in ("title", "description", "solutionExplanation")
                    if isinstance(t.get(f), dict)
                )
                bank["words"][locale] += count_words(strip_code(text))
        bank["count"] = len(data)
        bank["by_difficulty"] = dict(diffs)
        banks.append(bank)
    return banks


# ----------------------------------------------------------------------------
# cross references
# ----------------------------------------------------------------------------

def norm_label(text: str) -> str:
    """Loose key for matching a prose reference against a slug or H1 title."""
    text = text.lower()
    text = re.sub(r"[^a-zа-яё0-9]+", " ", text)
    return " ".join(w for w in text.split() if w not in {"and", "the", "и", "в"})


def scan_cross_refs(md_items: list[dict]) -> dict:
    """Find relative links that don't resolve, and bare [Title] references.

    Bare references are plain text like `(см. [Message Queues])` — they are not
    clickable at all. Split them into two buckets: the target article exists
    (a missed-link opportunity) vs. nothing matches (a dangling reference).
    """
    known_slugs: set[str] = set()
    known_keys: dict[str, str] = {}
    for item in md_items:
        for f in item["files"]:
            known_slugs.add(f["slug"])
            # slug without the numeric prefix: 07-message-queues -> message queues
            known_keys[norm_label(re.sub(r"^\d+[-_]", "", f["slug"]))] = f["slug"]
            for loc in f["locales"].values():
                p = ROOT / loc["path"]
                m = re.search(r"^#\s+(.+)$", read(p), re.M)
                if m:
                    known_keys[norm_label(m.group(1))] = f["slug"]

    broken_links, bare_refs, plain_text_refs = [], [], []
    for item in md_items:
        for f in item["files"]:
            for locale, loc in f["locales"].items():
                p = ROOT / loc["path"]
                prose = strip_code(strip_frontmatter(read(p)))
                for m in MD_LINK_RE.finditer(prose):
                    text, target = m.group(1), m.group(2)
                    if target.startswith(("http://", "https://", "mailto:", "#")):
                        continue
                    resolved = (p.parent / target).resolve()
                    if not resolved.exists():
                        broken_links.append(
                            {
                                "file": loc["path"],
                                "text": text,
                                "target": target,
                                "expected": str(resolved.relative_to(ROOT))
                                if ROOT in resolved.parents
                                else str(resolved),
                            }
                        )
                for m in BARE_REF_RE.finditer(prose):
                    label = m.group(1).strip()
                    key = norm_label(label)
                    target = known_keys.get(key)
                    if target is None:
                        target = next(
                            (
                                slug
                                for k, slug in known_keys.items()
                                if key and (key in k or k in key)
                            ),
                            None,
                        )
                    record = {"file": loc["path"], "label": label, "resolves_to": target}
                    (plain_text_refs if target else bare_refs).append(record)
    return {
        "broken_relative_links": broken_links,
        "unresolved_bare_references": bare_refs,
        "plain_text_references": plain_text_refs,
        "known_slugs": len(known_slugs),
        "known_keys": len(known_keys),
    }


# ----------------------------------------------------------------------------
# report
# ----------------------------------------------------------------------------

def md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def write_report(inv: dict) -> str:
    L: list[str] = []
    L.append("# Content inventory\n")
    L.append(f"Generated by `scripts/audit/inventory.py` — read-only scan of `content/`.\n")

    s = inv["summary"]
    L.append("## Summary\n")
    L.append(
        md_table(
            ["Section", "Items", "Units", "Words RU", "Words EN"],
            [
                ["topics", s["topics"]["items"], f"{s['topics']['articles']} articles",
                 s["topics"]["words"]["ru"], s["topics"]["words"]["en"]],
                ["courses", s["courses"]["items"], f"{s['courses']['articles']} chapters",
                 s["courses"]["words"]["ru"], s["courses"]["words"]["en"]],
                ["questions", s["questions"]["items"], f"{s['questions']['count']} questions",
                 s["questions"]["words"]["ru"], s["questions"]["words"]["en"]],
                ["quiz", s["quiz"]["items"], f"{s['quiz']['count']} quiz items",
                 s["quiz"]["words"]["ru"], s["quiz"]["words"]["en"]],
                ["tasks", s["tasks"]["items"], f"{s['tasks']['count']} tasks",
                 s["tasks"]["words"]["ru"], s["tasks"]["words"]["en"]],
            ],
        )
    )
    L.append("")

    for kind, title in (("topic", "Topics"), ("course", "Courses")):
        items = [i for i in inv["md_collections"] if i["kind"] == kind]
        L.append(f"## {title}\n")
        rows = []
        for i in items:
            rows.append(
                [
                    i["id"],
                    i["label"] or "—",
                    i["level"] or "—",
                    "yes" if i["in_registry"] else "**NOT IN REGISTRY**",
                    i["articles"],
                    "yes" if i["has_interview_questions"] else "no",
                    i["words"]["ru"],
                    i["words"]["en"],
                    len(i["desync"]) or "",
                ]
            )
        L.append(
            md_table(
                ["id", "label", "level", "registry", "articles", "interview-q",
                 "words RU", "words EN", "ru/en desync"],
                rows,
            )
        )
        L.append("")

    desync_rows = [
        [i["id"], d["slug"], ", ".join(d["present"]), ", ".join(d["missing"])]
        for i in inv["md_collections"]
        for d in i["desync"]
    ]
    L.append("## RU/EN desync (per file)\n")
    L.append(
        md_table(["collection", "slug", "present", "missing"], desync_rows)
        if desync_rows
        else "No desync — every markdown file exists in both `ru` and `en`.\n"
    )
    L.append("")

    L.append("## RU files with an untranslated (Latin-only) H1\n")
    h1_rows = [
        [i["id"], slug, "→ " + (
            next(
                (
                    f["locales"]["ru"]["h1"]
                    for f in i["files"]
                    if f["slug"] == slug and "ru" in f["locales"]
                ),
                "",
            )
        )]
        for i in inv["md_collections"]
        for slug in i["ru_untranslated_h1"]
    ]
    L.append(
        md_table(["collection", "slug", "ru H1"], h1_rows)
        if h1_rows
        else "None — every RU article has a Cyrillic H1.\n"
    )
    L.append("")

    L.append("## `<!-- verified: -->` marker coverage\n")
    ver_rows = [
        [i["id"], i["kind"], f"{i['verified_files']}/{i['total_locale_files']}"]
        for i in inv["md_collections"]
        if i["total_locale_files"]
    ]
    L.append(md_table(["collection", "kind", "verified files"], ver_rows))
    L.append("")

    L.append("## Question banks\n")
    diff_keys = sorted({d for b in inv["questions"] for d in b["by_difficulty"]})
    rows = []
    for b in inv["questions"]:
        rows.append(
            [b["id"], b["count"]]
            + [b["by_difficulty"].get(d, 0) for d in diff_keys]
            + [
                len(b["missing_locale"]) or "",
                len(b["missing_pitfall"]) or "",
                b["missing_id"] or "",
                b["avg_answer_words_ru"],
                b["avg_answer_words_en"],
            ]
        )
    L.append(
        md_table(
            ["bank", "total"] + diff_keys
            + ["locale gaps", "no pitfall", "no id", "avg ans RU", "avg ans EN"],
            rows,
        )
    )
    L.append("")

    L.append("## Quiz banks\n")
    L.append(
        md_table(
            ["bank", "items", "locale gaps", "option count mismatch", "bad correctIndex",
             "words RU", "words EN"],
            [
                [b["id"], b["count"], len(b["missing_locale"]) or "",
                 len(b["option_count_mismatch"]) or "", len(b["bad_correct_index"]) or "",
                 b["words"]["ru"], b["words"]["en"]]
                for b in inv["quiz"]
            ],
        )
    )
    L.append("")

    L.append("## Task banks\n")
    L.append(
        md_table(
            ["bank", "items", "by difficulty", "locale gaps", "missing solution",
             "words RU", "words EN"],
            [
                [b["id"], b["count"],
                 ", ".join(f"{k}:{v}" for k, v in sorted(b["by_difficulty"].items())),
                 len(b["missing_locale"]) or "", len(b["missing_solution"]) or "",
                 b["words"]["ru"], b["words"]["en"]]
                for b in inv["tasks"]
            ],
        )
    )
    L.append("")

    L.append("## Section alignment (topic vs questions vs quiz vs tasks)\n")
    L.append(
        md_table(
            ["id", "articles", "questions", "quiz", "tasks", "note"],
            [
                [a["id"], a["articles"] or "—", a["questions"] or "—", a["quiz"] or "—",
                 a["tasks"] or "—", a["note"]]
                for a in inv["alignment"]
            ],
        )
    )
    L.append("")

    xr = inv["cross_refs"]
    L.append("## Cross references\n")
    L.append(
        f"Resolvable article slugs: {xr['known_slugs']}, match keys indexed: {xr['known_keys']}.\n"
    )
    L.append(
        f"Plain-text `[Title]` references that DO point at an existing article "
        f"(not clickable — missed link): **{len(xr['plain_text_references'])}**. "
        f"References with no matching article: **{len(xr['unresolved_bare_references'])}**.\n"
    )
    L.append("### Broken relative links\n")
    L.append(
        md_table(
            ["file", "link text", "target"],
            [[b["file"], b["text"], b["target"]] for b in xr["broken_relative_links"]],
        )
        if xr["broken_relative_links"]
        else "None.\n"
    )
    L.append("")
    L.append("### Dangling `[Title]` references (no matching article)\n")
    L.append(
        md_table(
            ["file", "label"],
            [[b["file"], b["label"]] for b in xr["unresolved_bare_references"][:100]],
        )
        if xr["unresolved_bare_references"]
        else "None.\n"
    )
    L.append("")
    L.append("### Plain-text references that could be links (top 40)\n")
    L.append(
        md_table(
            ["file", "label", "existing article"],
            [
                [b["file"], b["label"], b["resolves_to"]]
                for b in xr["plain_text_references"][:40]
            ],
        )
        if xr["plain_text_references"]
        else "None.\n"
    )
    L.append("")
    return "\n".join(L)


def main() -> int:
    topics_reg = load_registry("src/constants/topics.ts", "topic")
    courses_reg = load_registry("src/constants/courses.ts", "course")

    md_items = scan_md_collection(TOPICS_DIR, topics_reg, "topic")
    md_items += scan_md_collection(COURSES_DIR, courses_reg, "course")

    questions = scan_questions()
    quiz = scan_quiz()
    tasks = scan_tasks()
    cross_refs = scan_cross_refs(md_items)

    q_by_id = {b["id"]: b for b in questions}
    z_by_id = {b["id"]: b for b in quiz}
    t_by_id = {b["id"]: b for b in tasks}
    topic_by_id = {i["id"]: i for i in md_items if i["kind"] == "topic"}

    alignment = []
    for id_ in sorted(set(topic_by_id) | set(q_by_id) | set(z_by_id) | set(t_by_id)):
        arts = topic_by_id.get(id_, {}).get("articles", 0)
        qn = q_by_id.get(id_, {}).get("count", 0)
        zn = z_by_id.get(id_, {}).get("count", 0)
        tn = t_by_id.get(id_, {}).get("count", 0)
        notes = []
        if arts and not qn:
            notes.append("articles without question bank")
        if qn and not arts:
            notes.append("question bank without articles")
        if arts and not zn:
            notes.append("no quiz")
        if id_ not in topic_by_id and id_ not in {t["id"] for t in topics_reg}:
            notes.append("id not in TOPICS registry")
        alignment.append(
            {"id": id_, "articles": arts, "questions": qn, "quiz": zn, "tasks": tn,
             "note": "; ".join(notes) or "ok"}
        )

    def wsum(items, key="words"):
        return {l: sum(i[key][l] for i in items) for l in LOCALES}

    topics_only = [i for i in md_items if i["kind"] == "topic"]
    courses_only = [i for i in md_items if i["kind"] == "course"]

    inv = {
        "root": str(ROOT),
        "registry": {"topics": topics_reg, "courses": courses_reg},
        "md_collections": md_items,
        "questions": questions,
        "quiz": quiz,
        "tasks": tasks,
        "cross_refs": cross_refs,
        "alignment": alignment,
        "summary": {
            "topics": {
                "items": len(topics_only),
                "with_content": sum(1 for i in topics_only if i["articles"]),
                "articles": sum(i["articles"] for i in topics_only),
                "words": wsum(topics_only),
                "prose_words": wsum(topics_only, "prose_words"),
            },
            "courses": {
                "items": len(courses_only),
                "with_content": sum(1 for i in courses_only if i["articles"]),
                "articles": sum(i["articles"] for i in courses_only),
                "words": wsum(courses_only),
                "prose_words": wsum(courses_only, "prose_words"),
            },
            "questions": {
                "items": len(questions),
                "count": sum(b["count"] for b in questions),
                "words": wsum(questions),
            },
            "quiz": {"items": len(quiz), "count": sum(b["count"] for b in quiz),
                     "words": wsum(quiz)},
            "tasks": {"items": len(tasks), "count": sum(b["count"] for b in tasks),
                      "words": wsum(tasks)},
        },
    }

    AUDIT.mkdir(exist_ok=True)
    (AUDIT / "inventory.json").write_text(
        json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (AUDIT / "inventory.md").write_text(write_report(inv), encoding="utf-8")

    s = inv["summary"]
    print(f"topics:    {s['topics']['with_content']}/{s['topics']['items']} with content, "
          f"{s['topics']['articles']} articles")
    print(f"courses:   {s['courses']['with_content']}/{s['courses']['items']} with content, "
          f"{s['courses']['articles']} chapters")
    print(f"questions: {s['questions']['items']} banks, {s['questions']['count']} questions")
    print(f"quiz:      {s['quiz']['items']} banks, {s['quiz']['count']} items")
    print(f"tasks:     {s['tasks']['items']} banks, {s['tasks']['count']} items")
    print(f"desync files: {sum(len(i['desync']) for i in md_items)}")
    print(f"broken links: {len(cross_refs['broken_relative_links'])}, plain-text refs: {len(cross_refs['plain_text_references'])}, "
          f"dangling refs: {len(cross_refs['unresolved_bare_references'])}")
    print(f"→ audit/inventory.md, audit/inventory.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
