#!/usr/bin/env python3
"""Readability pre-pass for full-stack-trainer content.

Mechanically marks *candidates* for readability problems — it is a focusing tool
for the deep audit, not a verdict. Target reader: strong junior / middle dev,
English B1-B2, reading on a phone in short bursts.

Checks per file (topic articles and course chapters, both locales) and per
answer field (question / quiz banks, both locales):

  1. abbreviations used without an expansion near their first occurrence
  2. sentences over the word limit (28 RU / 25 EN)
  3. paragraphs over ~6 rendered lines on a narrow screen
  4. runs of more than 4 theory paragraphs with no code block or diagram
  5. (questions only) first sentence of an answer is not a direct answer

Outputs:
  audit/readability_flags.json  — per-file detail for the deep audit
  audit/readability-flags.md    — "worst files by metric" tables

Read-only: never writes inside content/.

Usage:
  python3 scripts/audit/readability_flags.py                 # whole content tree
  python3 scripts/audit/readability_flags.py content/topics/react
  python3 scripts/audit/readability_flags.py --json-out /tmp/after.json <path>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "content"
AUDIT = ROOT / "audit"

LOCALES = ("ru", "en")

# --- thresholds -------------------------------------------------------------

MAX_SENTENCE_WORDS = {"ru": 28, "en": 25}
# Chars per rendered line in the site's content column. On a phone a line holds
# roughly half that, so a paragraph flagged at 6 lines here is ~12 lines there.
PARA_LINE_CHARS = 70
MAX_PARA_LINES = 6
MAX_THEORY_RUN = 4            # prose paragraphs in a row without code/diagram
MAX_LEAD_WORDS = 30           # first sentence of an answer

# Deliberately tiny. Everything not on this list is a candidate for expansion —
# there is no "everyone knows this one" allowlist. HTTPS, REST, DOM, SQL, JWT,
# CORS and friends are candidates on purpose: the target reader may not know them.
ABBREV_ALLOWLIST = {"HTML", "CSS", "API", "JS", "TS", "URL", "HTTP", "JSON", "ID"}

# Brand and library names the CamelCase pattern picks up. Not abbreviations —
# nothing is gained by expanding "GitHub". Concepts stay candidates on purpose
# (NoSQL, WebP, IoC, GoF, DoS, PaaS all remain flagged).
PRODUCT_NAMES = {
    "GitHub", "GitLab", "YouTube", "MacBook", "PayPal", "WiFi", "NumPy", "PyPy",
    "MySQL", "RxJS", "MobX", "NgRx", "RegExp",
}

# Uppercase tokens that are language keywords or HTTP verbs, not acronyms.
KEYWORDS = {
    # SQL
    "SELECT", "INSERT", "UPDATE", "DELETE", "FROM", "WHERE", "JOIN", "LEFT",
    "RIGHT", "INNER", "OUTER", "FULL", "CROSS", "GROUP", "ORDER", "BY", "HAVING",
    "LIMIT", "OFFSET", "AS", "ON", "IN", "IS", "NOT", "AND", "OR", "NULL",
    "TRUE", "FALSE", "WITH", "SET", "VALUES", "CREATE", "DROP", "ALTER", "TABLE",
    "INDEX", "PRIMARY", "KEY", "FOREIGN", "UNIQUE", "DEFAULT", "CASCADE",
    "RETURNING", "BEGIN", "COMMIT", "ROLLBACK", "EXISTS", "DISTINCT", "UNION",
    "CASE", "WHEN", "THEN", "ELSE", "END", "LIKE", "BETWEEN", "ASC", "DESC",
    "COUNT", "SUM", "AVG", "MIN", "MAX", "OVER", "PARTITION", "ANALYZE",
    "EXPLAIN", "VACUUM", "LOCK", "SHARE", "ONLY", "READ", "WRITE", "LEVEL",
    "ISOLATION", "SERIALIZABLE", "REPEATABLE", "COMMITTED", "UNCOMMITTED",
    # SQL types and constraints (JSONB, UUID, MVCC, WAL stay candidates on purpose)
    "TEXT", "VARCHAR", "CHAR", "INT", "INTEGER", "BIGINT", "SMALLINT", "SERIAL",
    "BOOLEAN", "BOOL", "DATE", "TIME", "TIMESTAMP", "TIMESTAMPTZ", "NUMERIC",
    "DECIMAL", "REAL", "FLOAT", "BYTEA", "ARRAY", "CHECK", "CONSTRAINT",
    "REFERENCES", "GENERATED", "ALWAYS", "IDENTITY", "SEQUENCE", "NEXTVAL",
    "CONCURRENTLY", "USING", "INTO", "EXCEPT", "INTERSECT", "ROW", "ROWS",
    # HTTP verbs and header-ish words
    "GET", "POST", "PUT", "PATCH", "HEAD", "OPTIONS", "TRACE", "CONNECT",
    # misc language tokens that show up capitalised in prose
    "IF", "FOR", "DO", "OK", "NEW", "THIS", "ALL", "ANY", "NO", "YES", "VS",
    "TODO", "NOTE", "WARN", "INFO", "DEBUG", "ERROR", "FATAL",
}

# Cyrillic all-caps used for emphasis, not abbreviations.
RU_EMPHASIS = {
    "НЕ", "НИ", "ВСЕ", "ВСЁ", "ВСЕГО", "ТОЛЬКО", "ВСЕГДА", "НИКОГДА", "ОЧЕНЬ",
    "НО", "ЕСЛИ", "ДА", "НЕТ", "ЭТО", "ТАК", "КАК", "ЧТО", "ГДЕ", "КОГДА",
    "ПОСЛЕ", "ДО", "БЕЗ", "ОДИН", "ОДНА", "РАЗ", "ДВА", "ТРИ", "УЖЕ", "ЕЩЁ",
    "ЕЩЕ", "БОЛЬШЕ", "МЕНЬШЕ", "КАЖДЫЙ", "ЛЮБОЙ", "САМ", "ЖЕ", "ПРИ", "ИЗ",
    "ДЛЯ", "ПО", "НА", "ОТ", "ЗА", "ВО", "СО", "ИЛИ", "ТОТ", "ТУТ", "ТАМ",
    "НАДО", "НУЖНО", "МОЖНО", "НЕЛЬЗЯ", "ДОЛЖЕН", "ВАЖНО", "ГЛАВНОЕ",
}

# --- patterns ---------------------------------------------------------------

FENCE_SPLIT_RE = re.compile(r"(^```[^\n]*\n.*?^```[ \t]*$)", re.DOTALL | re.M)
FENCE_LANG_RE = re.compile(r"^```([^\n]*)")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
URL_RE = re.compile(r"https?://\S+")
MD_LINK_RE = re.compile(r"\[([^\]\n]*)\]\(([^)\s]+)[^)]*\)")
WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9_'’\-]+")
BOX_CHARS = set("─│┌┐└┘├┤┬┴┼═║╔╗╚╝╠╣╦╩╬▲▼◄►↑↓→←↔⟶")

# 2-6 uppercase Latin letters/digits, e.g. GC, JWT, HTTP2, OWASP
# The leading `.` guard keeps dotted product names whole: Socket.IO must not
# yield "IO", and Node.JS must not yield "JS".
ABBR_UPPER_RE = re.compile(r"(?<![A-Za-z0-9_.])([A-Z][A-Z0-9]{1,5})(?![A-Za-z0-9_])")
# mixed-case acronyms: IoC, IaC, PaaS, SaaS, GoF, TTFb-style
ABBR_MIXED_RE = re.compile(r"(?<![A-Za-z0-9_])([A-Z][a-z]{1,2}[A-Z][A-Za-z]{0,3})(?![A-Za-z0-9_])")
# numeronyms: a11y, i18n, l10n, k8s
ABBR_NUMERONYM_RE = re.compile(r"(?<![A-Za-z0-9_])([a-z]\d{1,3}[a-z]{1,2})(?![A-Za-z0-9_])")
# 2-6 uppercase Cyrillic letters, e.g. БД, СУБД, ООП
ABBR_CYRILLIC_RE = re.compile(r"(?<![А-Яа-яЁё])([А-ЯЁ]{2,6})(?![А-Яа-яЁё])")

# Introductory openings that delay the actual answer.
LEAD_INTRO_RE = {
    "ru": re.compile(
        r"^\s*(?:прежде\s+чем|перед\s+тем|чтобы\s+понять|для\s+того\s+чтобы|"
        r"начнём|начнем|давайте|рассмотрим|представьте|представим|вообразите|"
        r"важно\s+понимать|важно\s+сначала|стоит\s+начать|исторически|"
        r"когда\s+мы\s+говорим|если\s+говорить|разберём|разберем|"
        r"существует\s+(?:несколько|два|три|множество)|"
        r"есть\s+(?:несколько|два|три)\s|"
        r"в\s+(?:современных|современном|современной)|"
        r"на\s+этот\s+вопрос|этот\s+вопрос|сам\s+вопрос)",
        re.I,
    ),
    "en": re.compile(
        # note: `let['’]s`, not `let'?s` — "lets you do X" is a direct answer,
        # "Let's look at X" is a stall.
        r"^\s*(?:before\s+|in\s+order\s+to|to\s+understand|to\s+answer|let['’]s\b|"
        r"let\s+us\b|imagine\b|consider\b|picture\b|historically|"
        r"it'?s\s+important\s+to|it\s+is\s+important\s+to|"
        r"there\s+(?:are|is)\s+(?:several|two|three|many|a\s+few)|"
        r"when\s+(?:we|you)\s+(?:talk|think)|"
        r"first,?\s+(?:it|we|you|let)|this\s+question\b|"
        r"in\s+modern\b|these\s+days\b|nowadays\b)",
        re.I,
    ),
}

# Dots that must not end a sentence.
PROTECT = [
    r"т\.\s?е\.", r"т\.\s?д\.", r"т\.\s?п\.", r"т\.\s?к\.", r"и\.\s?о\.",
    r"др\.", r"см\.", r"напр\.", r"рис\.", r"стр\.", r"гл\.",
    r"e\.g\.", r"i\.e\.", r"etc\.", r"vs\.", r"Fig\.", r"No\.", r"cf\.",
    r"Mr\.", r"Ms\.", r"Dr\.", r"approx\.",
    r"\d+\.\d+",                     # 3.14, 18.2
    r"\b[A-Za-zА-Яа-яЁё]\.",         # single-letter initials
]
PROTECT_RE = re.compile("|".join(PROTECT))
SENT_SPLIT_RE = re.compile(r"(?<=[.!?…])[\s ]+(?=[«\"(\[A-ZА-ЯЁ0-9])")


# --- helpers ----------------------------------------------------------------

def count_words(text: str) -> int:
    return len(WORD_RE.findall(text))


def clip(text: str, limit: int = 220) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :]
    return text


def to_prose(text: str, keep_inline: bool = False) -> str:
    """Drop fenced code, URLs and link targets — keep readable prose.

    `keep_inline=True` unwraps inline code instead of deleting it: `useEffect`
    is a word the reader actually reads, so it must count toward sentence length
    and must not be cut out of a quoted sentence. Abbreviation detection uses
    the default (deleting), because `PORT` in backticks is an identifier, not
    jargon that needs explaining.
    """
    text = FENCE_SPLIT_RE.sub(" ", text)
    text = INLINE_CODE_RE.sub(
        (lambda m: m.group(0).strip("`")) if keep_inline else " ", text
    )
    text = URL_RE.sub(" ", text)
    text = MD_LINK_RE.sub(r"\1", text)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    return text


def split_sentences(text: str) -> list[str]:
    """Split prose into sentences, treating markdown line breaks as boundaries."""
    out: list[str] = []
    for chunk in re.split(r"\n{1,}", text):
        chunk = chunk.strip()
        if not chunk:
            continue
        # strip markdown decoration that would confuse the word count
        chunk = re.sub(r"^\s*(?:[#>]+|[-*+]|\d+[.)])\s*", "", chunk)
        chunk = chunk.replace("**", "").replace("__", "")
        if not chunk:
            continue
        holes: list[str] = []

        def hide(m: re.Match) -> str:
            holes.append(m.group(0))
            return f"\x00{len(holes) - 1}\x00"

        masked = PROTECT_RE.sub(hide, chunk)
        for part in SENT_SPLIT_RE.split(masked):
            restored = re.sub(r"\x00(\d+)\x00", lambda m: holes[int(m.group(1))], part).strip()
            if restored:
                out.append(restored)
    return out


def is_table_row(line: str) -> bool:
    return line.lstrip().startswith("|")


def is_list_item(line: str) -> bool:
    return bool(re.match(r"\s*(?:[-*+]|\d+[.)])\s", line))


def is_heading(line: str) -> bool:
    return bool(re.match(r"\s*#{1,6}\s", line))


# --- checks -----------------------------------------------------------------

def is_caps_emphasis(token: str, prose: str) -> bool:
    """True if the token is a shouted normal word, not an acronym.

    Self-referential test: if the same word also appears in lower case somewhere
    in this text ("EVERY" here, "every" there), it is emphasis. An acronym never
    shows up lower-cased — the corpus has no "jwt" or "мvcc".
    """
    lower = token.lower()
    if len(lower) < 2:
        return False
    return bool(
        re.search(rf"(?<![A-Za-zА-Яа-яЁё0-9_]){re.escape(lower)}"
                  rf"(?![A-Za-zА-Яа-яЁё0-9_])", prose)
    )


def count_caps_emphasis(prose: str) -> int:
    """All-caps words used to shout, e.g. "run ALL microtasks" / "ВСЕ микрозадачи"."""
    total = 0
    for m in list(ABBR_UPPER_RE.finditer(prose)) + list(ABBR_CYRILLIC_RE.finditer(prose)):
        tok = m.group(1)
        if tok in RU_EMPHASIS or is_caps_emphasis(tok, prose):
            total += 1
    return total


def find_abbreviations(prose: str, locale: str, stats: dict | None = None) -> list[dict]:
    """Abbreviations whose first occurrence in this text has no expansion nearby.

    `stats` accumulates {"expanded": n, "seen": n} so the report can say what
    share of first mentions are explained at all.
    """
    sentences = split_sentences(prose)
    first_seen: dict[str, tuple[int, str, str]] = {}

    def register(token: str, kind: str, idx: int, sentence: str) -> None:
        if token in first_seen:
            return
        first_seen[token] = (idx, sentence, kind)

    for idx, sentence in enumerate(sentences):
        for m in ABBR_UPPER_RE.finditer(sentence):
            tok = m.group(1)
            if tok in ABBREV_ALLOWLIST or tok in KEYWORDS:
                continue
            if is_caps_emphasis(tok, prose):   # shouted word, not an acronym
                continue
            register(tok, "upper", idx, sentence)
        for m in ABBR_MIXED_RE.finditer(sentence):
            if m.group(1) in PRODUCT_NAMES:
                continue
            register(m.group(1), "mixed", idx, sentence)
        for m in ABBR_NUMERONYM_RE.finditer(sentence):
            register(m.group(1), "numeronym", idx, sentence)
        if locale == "ru":
            for m in ABBR_CYRILLIC_RE.finditer(sentence):
                tok = m.group(1)
                if tok in RU_EMPHASIS or is_caps_emphasis(tok, prose):
                    continue
                register(tok, "cyrillic", idx, sentence)

    flags = []
    for token, (idx, sentence, kind) in sorted(first_seen.items()):
        # window: the sentence itself plus the next one (glosses often follow)
        # §2.2: an acronym may live in a heading as long as the text below expands
        # it. A heading is one short "sentence", so widen the window in that case.
        span = 5 if len(sentences[idx].split()) <= 12 else 2
        window = " ".join(sentences[idx : idx + span])
        expansion = detect_expansion(token, window)
        if stats is not None:
            stats["seen"] = stats.get("seen", 0) + 1
        if expansion:
            if stats is not None:
                stats["expanded"] = stats.get("expanded", 0) + 1
            continue
        flags.append(
            {
                "token": token,
                "kind": kind,
                "first_sentence": clip(sentence),
                "occurrences": len(re.findall(rf"(?<![A-Za-zА-Яа-яЁё0-9_]){re.escape(token)}"
                                             rf"(?![A-Za-zА-Яа-яЁё0-9_])", prose)),
            }
        )
    return flags


def initials_expansion(token: str, window: str) -> str | None:
    """Detect a spelled-out expansion by matching initials, in order.

    STYLE.md allows any gloss form, and three common ones carry no punctuation
    marker this function can key on:

        not to the ORM. That is the object-relational mapper, …
        at the CDN. A content delivery network holds copies …
        The key is a UUID, a universally unique identifier.

    So match the letters of the abbreviation against the initials of consecutive
    words instead. Hyphens count as word separators, since "object-relational
    mapper" spells ORM. Acronyms that double a letter ("UUID" for "universally
    unique identifier") are matched with the last letter dropped.
    """
    letters = [c for c in token if c.isalpha()]
    if len(letters) < 2:
        return None

    def matches(seq: list[str]) -> bool:
        pattern = r"[\w-]*\W+".join(re.escape(c) for c in seq)
        return bool(re.search(rf"\b{pattern}[\w-]*\b", window, re.I))

    if matches(letters):
        return "initials"
    if len(letters) >= 4 and matches(letters[:-1]):
        return "initials-partial"
    return None


def detect_expansion(token: str, window: str) -> str | None:
    """Return the expansion form found near `token`, or None."""
    esc = re.escape(token)
    # ABBR (expansion)
    if re.search(rf"{esc}\s*[—-]?\s*\(([^)]{{3,80}})\)", window):
        return "parenthetical-after"
    # expansion (ABBR)
    if re.search(rf"\(\s*{esc}\s*\)", window):
        return "parenthetical-before"
    # ABBR — expansion / ABBR - expansion / ABBR: expansion
    if re.search(rf"{esc}\s*(?:—|–|:|,\s+(?:a|an|the|это|то\s+есть)\b|\bэто\b|\bis\b|"
                 rf"\bstands\s+for\b|\bозначает\b|\bрасшифровывается\b)\s", window):
        return "gloss-dash"
    return initials_expansion(token, window)


def find_long_sentences(text: str, locale: str) -> list[dict]:
    """Sentences over the word limit. Inline code counts as words — it is read."""
    limit = MAX_SENTENCE_WORDS[locale]
    out = []
    for sentence in split_sentences(to_prose(text, keep_inline=True)):
        n = count_words(sentence)
        if n > limit:
            out.append({"words": n, "text": clip(sentence)})
    out.sort(key=lambda s: -s["words"])
    return out


def blocks_of(body: str) -> list[dict]:
    """Split a markdown body into typed blocks: code, diagram, table, list, para, heading."""
    out: list[dict] = []
    for part in FENCE_SPLIT_RE.split(body):
        if not part.strip():
            continue
        if part.startswith("```"):
            lang = (FENCE_LANG_RE.match(part).group(1) or "").strip().lower()
            is_diagram = lang in {"txt", "text", "ascii", "diagram", "plain"} or bool(
                BOX_CHARS & set(part)
            )
            out.append({"type": "diagram" if is_diagram else "code", "text": part})
            continue
        for chunk in re.split(r"\n\s*\n", part):
            lines = [l for l in chunk.split("\n") if l.strip()]
            if not lines:
                continue
            if all(is_heading(l) for l in lines):
                kind = "heading"
            elif any(is_table_row(l) for l in lines):
                kind = "table"
            elif is_list_item(lines[0]):
                kind = "list"
            else:
                kind = "para"
            out.append({"type": kind, "text": chunk})
    return out


def find_long_paragraphs(blocks: list[dict]) -> list[dict]:
    out = []
    for b in blocks:
        if b["type"] != "para":
            continue
        prose = to_prose(b["text"], keep_inline=True)
        chars = len(" ".join(prose.split()))
        lines = -(-chars // PARA_LINE_CHARS)  # ceil
        if lines > MAX_PARA_LINES:
            out.append(
                {"est_lines": lines, "words": count_words(prose), "text": clip(prose, 160)}
            )
    out.sort(key=lambda p: -p["est_lines"])
    return out


def find_theory_walls(blocks: list[dict]) -> list[dict]:
    """Runs of prose paragraphs with no code block, diagram or table in between.

    Headings and lists are neutral: a heading does not explain anything, and a
    bullet list is still text. Only code, a diagram or a table breaks the wall.
    """
    out = []
    run: list[dict] = []
    for b in blocks:
        if b["type"] == "para":
            run.append(b)
            continue
        if b["type"] in {"code", "diagram", "table"}:
            if len(run) > MAX_THEORY_RUN:
                out.append(
                    {
                        "paragraphs": len(run),
                        "words": sum(count_words(to_prose(p["text"], keep_inline=True)) for p in run),
                        "starts_with": clip(to_prose(run[0]["text"], keep_inline=True), 140),
                    }
                )
            run = []
    if len(run) > MAX_THEORY_RUN:
        out.append(
            {
                "paragraphs": len(run),
                "words": sum(count_words(to_prose(p["text"], keep_inline=True)) for p in run),
                "starts_with": clip(to_prose(run[0]["text"], keep_inline=True), 140),
            }
        )
    return out


def check_answer_lead(answer: str, locale: str) -> dict | None:
    """Flag an answer whose first sentence does not answer the question."""
    sentences = split_sentences(to_prose(answer, keep_inline=True))
    if not sentences:
        return None
    lead = sentences[0]
    words = count_words(lead)
    reasons = []
    if words > MAX_LEAD_WORDS:
        reasons.append(f"first sentence is {words} words (limit {MAX_LEAD_WORDS})")
    if LEAD_INTRO_RE[locale].match(lead):
        reasons.append("opens with an introductory construction")
    if not reasons:
        return None
    return {"words": words, "reasons": reasons, "lead": clip(lead)}


# --- per-target analysis ----------------------------------------------------

def analyse_markdown(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    body = strip_frontmatter(raw)
    locale = "ru" if f"/ru/" in path.as_posix() else "en"
    blocks = blocks_of(body)
    prose = to_prose(body)

    abbrev_stats: dict[str, int] = {}
    abbrevs = find_abbreviations(prose, locale, abbrev_stats)
    long_sentences = find_long_sentences(body, locale)
    long_paragraphs = find_long_paragraphs(blocks)
    walls = find_theory_walls(blocks)

    readable = to_prose(body, keep_inline=True)
    prose_words = count_words(readable)
    total_sentences = len(split_sentences(readable))
    flags = len(abbrevs) + len(long_sentences) + len(long_paragraphs) + len(walls)

    return {
        "path": path.relative_to(ROOT).as_posix(),
        "kind": "course-chapter" if "/courses/" in path.as_posix() else "topic-article",
        "collection": path.parents[1].name,
        "locale": locale,
        "metrics": {
            "prose_words": prose_words,
            "sentences": total_sentences,
            "code_blocks": sum(1 for b in blocks if b["type"] == "code"),
            "diagrams": sum(1 for b in blocks if b["type"] == "diagram"),
            "paragraphs": sum(1 for b in blocks if b["type"] == "para"),
            "abbrevs_seen": abbrev_stats.get("seen", 0),
            "abbrevs_expanded": abbrev_stats.get("expanded", 0),
            "unexpanded_abbrevs": len(abbrevs),
            "caps_emphasis": count_caps_emphasis(prose),
            "long_sentences": len(long_sentences),
            "long_sentence_pct": round(100 * len(long_sentences) / total_sentences, 1)
            if total_sentences
            else 0.0,
            "long_paragraphs": len(long_paragraphs),
            "theory_walls": len(walls),
            "flags_total": flags,
            "flags_per_1k_words": round(1000 * flags / prose_words, 1) if prose_words else 0.0,
        },
        "unexpanded_abbrevs": abbrevs[:40],
        "long_sentences": long_sentences[:15],
        "long_paragraphs": long_paragraphs[:10],
        "theory_walls": walls[:10],
    }


def analyse_json_bank(path: Path, kind: str) -> list[dict]:
    """Analyse a question / quiz bank: one record per (bank, locale)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    results = []
    for locale in LOCALES:
        abbrevs: dict[str, dict] = {}
        long_sentences: list[dict] = []
        long_paragraphs: list[dict] = []
        walls: list[dict] = []
        lead_issues: list[dict] = []
        prose_words = 0
        sentences = 0
        items = 0
        caps_emphasis = 0
        abbrev_stats: dict[str, int] = {}

        for idx, entry in enumerate(data):
            ref = entry.get("id") or f"{path.stem}#{idx}"
            field = "answer" if kind == "question-bank" else "explanation"
            text = (entry.get(field) or {}).get(locale) if isinstance(
                entry.get(field), dict
            ) else None
            if not text:
                continue
            items += 1
            prose = to_prose(text)
            readable = to_prose(text, keep_inline=True)
            prose_words += count_words(readable)
            sentences += len(split_sentences(readable))

            caps_emphasis += count_caps_emphasis(prose)
            for a in find_abbreviations(prose, locale, abbrev_stats):
                slot = abbrevs.setdefault(
                    a["token"],
                    {"token": a["token"], "kind": a["kind"], "entries": [], "count": 0},
                )
                slot["count"] += 1
                if len(slot["entries"]) < 6:
                    slot["entries"].append(ref)
            for s in find_long_sentences(text, locale):
                long_sentences.append({**s, "ref": ref})
            blocks = blocks_of(text)
            for p in find_long_paragraphs(blocks):
                long_paragraphs.append({**p, "ref": ref})
            for w in find_theory_walls(blocks):
                walls.append({**w, "ref": ref})
            if kind == "question-bank":
                lead = check_answer_lead(text, locale)
                if lead:
                    lead_issues.append({**lead, "ref": ref})

        long_sentences.sort(key=lambda s: -s["words"])
        abbrev_list = sorted(abbrevs.values(), key=lambda a: -a["count"])
        flags = len(abbrev_list) + len(long_sentences) + len(long_paragraphs) + len(walls) + len(
            lead_issues
        )
        results.append(
            {
                "path": f"{path.relative_to(ROOT).as_posix()}#{locale}",
                "kind": kind,
                "collection": path.stem,
                "locale": locale,
                "metrics": {
                    "items": items,
                    "prose_words": prose_words,
                    "sentences": sentences,
                    "abbrevs_seen": abbrev_stats.get("seen", 0),
                    "abbrevs_expanded": abbrev_stats.get("expanded", 0),
                    "unexpanded_abbrevs": len(abbrev_list),
                    "caps_emphasis": caps_emphasis,
                    "long_sentences": len(long_sentences),
                    "long_sentence_pct": round(100 * len(long_sentences) / sentences, 1)
                    if sentences
                    else 0.0,
                    "long_paragraphs": len(long_paragraphs),
                    "theory_walls": len(walls),
                    "indirect_leads": len(lead_issues),
                    "indirect_lead_pct": round(100 * len(lead_issues) / items, 1) if items else 0.0,
                    "flags_total": flags,
                    "flags_per_1k_words": round(1000 * flags / prose_words, 1)
                    if prose_words
                    else 0.0,
                },
                "unexpanded_abbrevs": abbrev_list[:40],
                "long_sentences": long_sentences[:15],
                "long_paragraphs": long_paragraphs[:10],
                "theory_walls": walls[:10],
                "indirect_leads": lead_issues[:20],
            }
        )
    return results


# --- report -----------------------------------------------------------------

def md_table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def build_report(records: list[dict]) -> str:
    md = [r for r in records if r["kind"] in {"topic-article", "course-chapter"}]
    banks = [r for r in records if r["kind"] in {"question-bank", "quiz-bank"}]

    L = ["# Readability flags — mechanical pre-pass\n"]
    L.append(
        "Candidates only, not verdicts. Thresholds: sentence > "
        f"{MAX_SENTENCE_WORDS['ru']} words (RU) / {MAX_SENTENCE_WORDS['en']} (EN); "
        f"paragraph > {MAX_PARA_LINES} rendered lines at {PARA_LINE_CHARS} chars/line; "
        f"> {MAX_THEORY_RUN} prose paragraphs in a row without code/diagram/table; "
        f"answer lead > {MAX_LEAD_WORDS} words or introductory opening.\n"
    )
    L.append(
        "Abbreviation allowlist (everything else is a candidate): "
        + ", ".join(sorted(ABBREV_ALLOWLIST))
        + ". Brand names excluded from the CamelCase pattern: "
        + ", ".join(sorted(PRODUCT_NAMES))
        + ".\n"
    )
    seen = sum(r["metrics"].get("abbrevs_seen", 0) for r in records)
    expanded = sum(r["metrics"].get("abbrevs_expanded", 0) for r in records)
    L.append(
        f"First mentions of an abbreviation across all files: **{seen}**. "
        f"Explained on the spot: **{expanded}** ({round(100 * expanded / seen, 1) if seen else 0}%).\n"
    )

    # per-collection roll-up
    by_coll: dict[tuple[str, str], list[dict]] = {}
    for r in records:
        by_coll.setdefault((r["kind"], r["collection"]), []).append(r)

    L.append("## Collections ranked by flag density\n")
    rows = []
    for (kind, coll), rs in by_coll.items():
        words = sum(r["metrics"]["prose_words"] for r in rs)
        flags = sum(r["metrics"]["flags_total"] for r in rs)
        rows.append(
            [
                coll,
                kind,
                len(rs),
                words,
                sum(r["metrics"]["unexpanded_abbrevs"] for r in rs),
                sum(r["metrics"]["long_sentences"] for r in rs),
                sum(r["metrics"]["long_paragraphs"] for r in rs),
                sum(r["metrics"]["theory_walls"] for r in rs),
                sum(r["metrics"].get("indirect_leads", 0) for r in rs),
                flags,
                round(1000 * flags / words, 1) if words else 0.0,
            ]
        )
    rows.sort(key=lambda r: -r[-1])
    L.append(
        md_table(
            ["collection", "kind", "files", "prose words", "abbrev", "long sent",
             "long para", "walls", "indirect leads", "flags", "per 1k words"],
            rows,
        )
    )
    L.append("")

    for title, subset, extra in (
        ("Worst markdown files by flag density", md, []),
        ("Question / quiz banks", banks, ["indirect_leads", "indirect_lead_pct"]),
    ):
        L.append(f"## {title}\n")
        ranked = sorted(subset, key=lambda r: -r["metrics"]["flags_per_1k_words"])[:40]
        headers = ["file", "locale", "words", "abbrev", "long sent", "% long",
                   "long para", "walls"] + [e.replace("_", " ") for e in extra] + [
            "flags/1k"]
        rows = [
            [
                r["path"].replace("content/", ""),
                r["locale"],
                r["metrics"]["prose_words"],
                r["metrics"]["unexpanded_abbrevs"],
                r["metrics"]["long_sentences"],
                r["metrics"]["long_sentence_pct"],
                r["metrics"]["long_paragraphs"],
                r["metrics"]["theory_walls"],
            ]
            + [r["metrics"].get(e, "") for e in extra]
            + [r["metrics"]["flags_per_1k_words"]]
            for r in ranked
        ]
        L.append(md_table(headers, rows))
        L.append("")

    L.append("## RU vs EN — is the English version harder?\n")
    pairs: dict[str, dict[str, dict]] = {}
    for r in md:
        key = r["path"].replace("/ru/", "/*/").replace("/en/", "/*/")
        pairs.setdefault(key, {})[r["locale"]] = r
    rows = []
    for key, p in pairs.items():
        if len(p) < 2:
            continue
        ru, en = p["ru"]["metrics"], p["en"]["metrics"]
        rows.append(
            [
                key.replace("content/topics/", "").replace("content/courses/", "course:"),
                ru["long_sentence_pct"],
                en["long_sentence_pct"],
                round(en["long_sentence_pct"] - ru["long_sentence_pct"], 1),
                ru["unexpanded_abbrevs"],
                en["unexpanded_abbrevs"],
            ]
        )
    rows.sort(key=lambda r: -r[3])
    L.append(
        md_table(
            ["file", "RU % long sent", "EN % long sent", "EN − RU", "RU abbrev", "EN abbrev"],
            rows[:30],
        )
    )
    L.append("")

    L.append("## Most frequent unexpanded abbreviations across all files\n")
    freq: dict[str, dict] = {}
    for r in records:
        for a in r["unexpanded_abbrevs"]:
            slot = freq.setdefault(a["token"], {"files": 0, "kind": a["kind"]})
            slot["files"] += 1
    rows = [
        [tok, v["kind"], v["files"]]
        for tok, v in sorted(freq.items(), key=lambda kv: -kv[1]["files"])[:60]
    ]
    L.append(md_table(["abbreviation", "kind", "files where first use is unexplained"], rows))
    L.append("")
    return "\n".join(L)


# --- main -------------------------------------------------------------------

def collect_targets(paths: list[Path]) -> tuple[list[Path], list[tuple[Path, str]]]:
    md_files: list[Path] = []
    banks: list[tuple[Path, str]] = []
    for base in paths:
        if base.is_file():
            if base.suffix == ".md":
                md_files.append(base)
            elif base.suffix == ".json":
                kind = "question-bank" if "questions" in base.parts else "quiz-bank"
                banks.append((base, kind))
            continue
        md_files += sorted(base.rglob("*.md"))
        for json_path in sorted(base.rglob("*.json")):
            parts = json_path.parts
            if "questions" in parts:
                banks.append((json_path, "question-bank"))
            elif "quiz" in parts:
                banks.append((json_path, "quiz-bank"))
    return md_files, banks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="*", default=[], help="files or dirs (default: whole content/)")
    ap.add_argument("--json-out", default=str(AUDIT / "readability_flags.json"))
    ap.add_argument("--md-out", default=str(AUDIT / "readability-flags.md"))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    bases = [Path(p).resolve() for p in args.paths] or [
        CONTENT / "topics",
        CONTENT / "courses",
        CONTENT / "questions",
        CONTENT / "quiz",
    ]
    missing = [b for b in bases if not b.exists()]
    if missing:
        print("not found: " + ", ".join(str(m) for m in missing), file=sys.stderr)
        return 1

    md_files, banks = collect_targets(bases)
    records = [analyse_markdown(p) for p in md_files]
    for path, kind in banks:
        records += analyse_json_bank(path, kind)

    payload = {
        "config": {
            "max_sentence_words": MAX_SENTENCE_WORDS,
            "para_line_chars": PARA_LINE_CHARS,
            "max_para_lines": MAX_PARA_LINES,
            "max_theory_run": MAX_THEORY_RUN,
            "max_lead_words": MAX_LEAD_WORDS,
            "abbrev_allowlist": sorted(ABBREV_ALLOWLIST),
        },
        "scanned": [str(b.relative_to(ROOT)) if ROOT in b.parents else str(b) for b in bases],
        "files": records,
    }
    Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json_out).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if args.md_out:
        Path(args.md_out).write_text(build_report(records), encoding="utf-8")

    words = sum(r["metrics"]["prose_words"] for r in records)
    flags = sum(r["metrics"]["flags_total"] for r in records)
    print(f"scanned {len(md_files)} md files + {len(banks)} banks ({len(records)} records)")
    print(f"prose words: {words}")
    print(f"unexpanded abbrevs: {sum(r['metrics']['unexpanded_abbrevs'] for r in records)}")
    print(f"long sentences:     {sum(r['metrics']['long_sentences'] for r in records)}")
    print(f"long paragraphs:    {sum(r['metrics']['long_paragraphs'] for r in records)}")
    print(f"theory walls:       {sum(r['metrics']['theory_walls'] for r in records)}")
    print(f"indirect leads:     {sum(r['metrics'].get('indirect_leads', 0) for r in records)}")
    print(f"caps emphasis:      {sum(r['metrics'].get('caps_emphasis', 0) for r in records)}")
    print(f"flags total: {flags} ({round(1000 * flags / words, 1) if words else 0} per 1k words)")
    if not args.quiet:
        print(f"→ {args.json_out}")
        if args.md_out:
            print(f"→ {args.md_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
