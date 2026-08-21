# Rubric — phase 2 readability audit

Shared brief for every zone auditor. Read this fully before opening any content file.

## Target reader — measure everything against this person

> A **strong junior / middle developer**. English at **B1-B2**. Reads **on a phone, in short
> bursts**. Can program, but is **not required to already know professional jargon or
> abbreviations**. If they have to stop, re-read a sentence twice, or go google an acronym,
> **that is a defect in the text, not in the reader.**

## The core principle — simplify the LANGUAGE, never the CONCEPTS

Senior-level depth is the value of this site and must stay. The problem is never "it explains
V8 deoptimisation". The problem is "it explains it in a 40-word sentence with three subordinate
clauses and the abbreviation IC never spelled out".

Do **not** recommend:

- cutting technical detail, edge cases, or caveats;
- lowering the level ("this is too advanced for a middle dev");
- removing or simplifying code examples' behaviour;
- restructuring files, renaming files, or merging articles.

Do recommend: shorter sentences, plain words, expanded abbreviations, an example moved earlier,
a wall of theory broken by an existing-style diagram, a lead sentence rewritten to answer first.

## What you are auditing

You will be told your **zone** (a topic's articles, a course's chapters, and/or a question/quiz
bank) and where to write your report. Read **every file in your zone, in both `ru` and `en`**.

Your mechanical flags come from `python3 scripts/audit/flags_digest.py <collection> [--kind …]`
(command given in your task). Those flags are **candidates for attention, not verdicts** — a
32-word sentence can be perfectly clear, and a 15-word one can be impenetrable. Use the flags to
decide where to look first, then judge with your own eyes. Conversely: report problems the script
could not see (dead metaphors, calques from English, an example that depends on a previous
example, a term used before it is introduced).

## Scoring — A through G, 1 to 5, per file

**1** = pervasive, blocks comprehension · **2** = frequent, slows reading badly ·
**3** = noticeable but readable · **4** = minor slips only · **5** = clean for the target reader.

**A. Terms and abbreviations.** Every acronym and jargon word is expanded or explained at its
first use **in this file**. Files are read out of order — "it's explained in another article"
does not count. `HTML CSS API JS TS URL HTTP JSON id` need no expansion; everything else does,
including DOM, REST, SQL, JWT, CORS, MVCC, GC, SSR, CI, DI, CDN, TTL, БД, ОС.

**B. Sentence syntax.** Length, nested subordinate clauses, bureaucratic register, passive voice
where active is natural, chains of nouns in the genitive (RU), stacked modifiers (EN).

**C. First sentence of a section or answer.** Does it give the essence in plain words, with
details and caveats **after** it (the pyramid)? Or does it warm up, define terms, or give
history before answering? For question banks this is the highest-weight criterion.

**D. Concept density.** Is each new idea backed by an example, analogy, or diagram **before** the
next one arrives? Or are there walls of theory where three or four unfamiliar concepts stack up
with nothing to hold on to?

**E. Code examples.** Self-contained; commented at the non-obvious lines; readable on a narrow
screen; do not require remembering a previous example's variables or state.

**F. English version (score only `en` files).** Is it B1-B2? Flag rare words, idioms, phrasal
verbs, long constructions. Explicitly check: **is `en` harder than `ru`?** (It usually needs
~19% more words for the same content, so a borderline RU sentence becomes an over-limit EN one.)

**G. Russian version (score only `ru` files).** Living language, not a word-for-word calque from
English, not bureaucratic. Flag: «является», «осуществляется», «данный», «в случае если»,
noun-stacking, untranslated headings, English word order.

Use `null` for F on `ru` files and for G on `en` files.

## Report format

Write exactly one JSON file at the path given in your task, with this shape:

```json
{
  "zone": "react",
  "kinds": ["topic-article", "question-bank"],
  "verdict": "ok | targeted-fixes | systemic-refactor",
  "files": [
    { "file": "content/topics/react/ru/02-hooks-fundamentals.md",
      "locale": "ru",
      "scores": { "A": 3, "B": 2, "C": 4, "D": 3, "E": 4, "F": null, "G": 3 } }
  ],
  "averages": { "A": 3.1, "B": 2.4, "C": 4.0, "D": 3.2, "E": 4.1, "F": 3.0, "G": 3.3 },
  "worst_places": [
    { "file": "content/topics/react/ru/02-hooks-fundamentals.md",
      "rubric": "B",
      "quote": "1-2 sentences copied verbatim from the file",
      "problem": "what exactly makes this hard for the target reader",
      "before": "the text as it is now",
      "after": "your rewrite — same technical content, same depth, easier language" }
  ],
  "unexpanded_abbrevs": {
    "content/topics/react/ru/02-hooks-fundamentals.md": ["SSR", "HOC"]
  },
  "patterns": [
    "1-2 observations about problems that repeat across this zone's files"
  ],
  "notes": "anything the schema above does not capture, max 5 lines"
}
```

Rules for the report:

- `worst_places`: **5 to 10 entries**, the genuinely worst ones, ranked worst first. Quotes must
  be verbatim — they get cited in a style guide, so a paraphrase is useless.
- `after` must preserve every technical claim in `before`. If a sentence is long because it
  carries three facts, the rewrite has three sentences, not two facts.
- `unexpanded_abbrevs`: your own verified list per file (the script's list is a starting point;
  drop its false positives, add what it missed).
- `verdict`: `ok` = ship as is; `targeted-fixes` = a handful of specific places; 
  `systemic-refactor` = the whole zone needs a language pass.
- `patterns` is the most valuable field for the final style guide. Prefer a repeating structural
  habit ("every article opens with a definition paragraph before saying what the thing is for")
  over a one-off.

## Hard constraints

- **Never edit anything in `content/`.** This is an audit. Read only.
- Write only the one JSON file you were assigned, under `audit/readability/`.
- Report in English inside the JSON (the aggregated report is Russian-facing, but quotes stay in
  their original language and are never translated).
