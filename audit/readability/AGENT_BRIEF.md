# Shared brief — readability pass on a question bank

Read this fully, then the short task you were given. Repo:
`/Users/maksymkaspriv/WebstormProjects/full-stack-trainer`.

## The contract

`content/STYLE.md` is binding. Read it in full before touching anything. Sections 2, 3, 4, 6, 7 and
8 apply to question banks; section 9 is quiz-specific and does not.

Target reader, from section 0: a strong junior / middle developer, English B1-B2, reading on a phone
in short bursts, not required to know jargon or acronyms in advance.

**Simplify the language, never the content.** No technical claim, number, version, flag name, edge
case or caveat may disappear. If a sentence was long because it carried four facts, the result has
four short sentences — not three facts.

## What to fix

1. **Sentences over the limit** — 28 words in Russian, 25 in English. The house shape on this site is
   `<framing clause>: <fact A>, so <fact B> — <fact C>, <fact D>`. The punctuation already marks the
   seams: split at the existing colon and em-dashes. Where a dash joins two independent statements,
   use a full stop.
2. **Enumerations written as one sentence** — a colon followed by three or four items separated by
   semicolons. Make them a bulleted list. This is the single most common defect in the project.
3. **Paragraphs over ~420 characters** — split them. On a phone that is already twelve lines.
4. **The lead sentence of every answer must answer the question that was asked**, in plain words, with
   detail and caveats after it. No warm-up, no history, no "the naive model is", no description of the
   world before the feature existed. The real answer usually already exists further down — move it up.
5. **The closing `**Common pitfall:**` / `**Частая ловушка:**` block must be the shortest prose in the
   answer**, two or three short sentences naming a concrete mistake. Across this site it is usually
   the longest sentence in the answer, which is backwards.
6. **Abbreviations** — expand at first use *inside that answer*, because a bank is read one card at a
   time. Only `HTML CSS API JS TS URL HTTP JSON id` are exempt. Prefer a gloss in its own short
   sentence when a parenthetical would push the sentence past the word limit. Never put the gloss
   inside a heading, inside code, or inside a compound word such as `TCP-соединение`.
7. **ALL-CAPS emphasis** — replace with `**bold**`.
8. **Russian**: living Russian, not a calque. Remove English nouns inflected with an apostrophe
   (`callback'а`, `remote'у`), bare English noun phrases sitting in Russian sentences, and invented
   transliterations where a normal Russian word exists. Keep the English term in parentheses on first
   use where it is the accepted name. Fix dropped subjects and missing commas before subordinate
   clauses — several banks read as machine translation.
9. **English**: it is the harder locale across this site, at +13% words. Mirror the Russian sentence
   boundaries first, then check English against its own 25-word limit. Replace idiom a B1-B2 reader
   will not know. Real examples found in audit: `the nuclear option`, `blast radius`, `table stakes`,
   `wait out its timeout`, `ties up a connection`, `sawtooth`, `strictly worse`, `post-hoc`.
10. **Code**: do not change what it does. You may translate or clarify comments. Keep lines under 92
    characters, tag each fence with the language it really contains, and make sure both fences exist.

## What not to touch

- `id`, `topicId`, `difficulty`, `tags`, and the order of entries.
- The wording of the pitfall marker itself — both «Частая ловушка» and «Типичная ошибка на интервью»
  are in use across the site, and renaming them is out of scope.
- Anything outside the entries you were assigned.
- Facts. If you find one that is wrong — a stale version, a wrong default, code that cannot run —
  **do not silently fix it**. Leave it and report it. Several such reports have already turned out to
  be more valuable than the language pass itself.

## How to deliver

You do **not** edit the content file. Several agents work on the same file at once, and a
read-mutate-write cycle would overwrite the others.

Instead write a patch file at the path given in your task, containing only your entries:

```json
{
  "nodejs-q-29": {
    "question": { "en": "...", "ru": "..." },
    "answer":   { "en": "...", "ru": "..." }
  },
  "nodejs-q-30": { "...": "..." }
}
```

Include `question` only if you changed it. Write it with
`json.dumps(patch, ensure_ascii=False, indent=2)`. The orchestrator merges the patches and re-measures.

## Verifying your own work

`python3 scripts/audit/readability_flags.py` is the measuring tool, but it reads the content file,
not your patch. So check your own text by importing the module directly:

```python
import sys, json; sys.path.insert(0, 'scripts/audit')
import readability_flags as rf
text = patch['nodejs-q-29']['answer']['en']
print(len(rf.find_abbreviations(rf.to_prose(text), 'en')),
      len(rf.find_long_sentences(text, 'en')),
      len(rf.find_long_paragraphs(rf.blocks_of(text))),
      rf.count_caps_emphasis(rf.to_prose(text)))
```

Aim for zero on all four, in both locales, for every entry you touch. Do not run the script with a
path argument — it overwrites `audit/readability_flags.json`, which is a committed baseline.

## Report

One line per entry listing what you changed, with the rubric letter (A terms, B sentences, C lead,
D density, E code, F English, G Russian). Then the two or three most substantial rewrites in full
before/after, your judgement calls, and the list of non-language defects you found and left alone.
