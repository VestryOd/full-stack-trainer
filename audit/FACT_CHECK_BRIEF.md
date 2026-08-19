# Shared brief — correctness pass on a question bank

Read this fully, then the short task you were given. Repo:
`/Users/maksymkaspriv/WebstormProjects/full-stack-trainer`.

This is **not** the readability pass. The language pass over these banks is already done and they
measure at zero flags — your job is the debt it deliberately left behind: claims that are wrong.

## The contract

The site is interview preparation. A wrong claim here is worse than an awkward sentence: the reader
repeats it in an interview. So the bar is different from the language pass — you must **verify before
you edit**, and a claim you cannot verify stays as it is with a note in your report.

1. **Check every claim against the current official documentation**, not against your recollection.
   Load `WebSearch` and `WebFetch` with `ToolSearch` (`select:WebSearch,WebFetch`) and read the real
   source: nodejs.org/api, react.dev, the package's own README or changelog, the relevant TC39 or RFC
   page. Prefer the primary source over a blog post.
2. **A reported defect can itself be wrong.** In the first correctness pass on this site, 3 of 14
   audit findings turned out to be false and were correctly left alone. If the text is right and the
   report is wrong, do not edit — say so in your report and cite what you read.
3. **Version-dependent behaviour needs the version named in the text.** The banks target Node.js 22+
   and React 19. "The default is X" without a version is a defect when the default has changed; the
   fix is to name the version, not to pick one number.
4. **Fix minimally.** Correct the claim and whatever sentence around it becomes false. Do not
   restructure the answer, do not add sections, do not improve wording you merely dislike.
5. **Both locales, one meaning.** Every fix lands in `en` and `ru`. A claim corrected in one locale
   and left standing in the other is the worst possible outcome — the reader picks whichever tab.
6. **Do not regress the language pass.** These entries currently sit at zero readability flags.
   `content/STYLE.md` is binding for anything you write: 25 words per sentence in English, 28 in
   Russian, paragraphs under ~420 characters, abbreviations expanded at first use inside the answer,
   no ALL-CAPS emphasis. Check your own text before delivering (see below).
7. **Code must run.** Where you touch a snippet, every identifier it uses must be defined in that
   snippet or be a real import. Fences stay tagged with the language they actually contain.

## What not to touch

- `id`, `topicId`, `difficulty`, `tags`, and the order of entries.
- The pitfall marker wording — both «Частая ловушка» and «Типичная ошибка на интервью» are in use.
- Anything outside the entries you were assigned.
- Language-only problems. If you spot an awkward sentence that is not wrong, leave it.

## How to deliver

Write a patch file at the path given in your task, holding only your entries:

```json
{
  "nodejs-q-59": {
    "question": { "en": "...", "ru": "..." },
    "answer":   { "en": "...", "ru": "..." }
  }
}
```

Include `question` only if the question text itself was wrong. Write with
`json.dumps(patch, ensure_ascii=False, indent=2)`. Several agents work the same bank at once, so
**never edit the content file** — a read-mutate-write cycle would drop another agent's work. The
orchestrator merges the patches.

## Verifying your own work

```python
import sys, json; sys.path.insert(0, 'scripts/audit')
import readability_flags as rf
text = patch['nodejs-q-59']['answer']['en']
print(len(rf.find_abbreviations(rf.to_prose(text), 'en')),
      len(rf.find_long_sentences(text, 'en')),
      len(rf.find_long_paragraphs(rf.blocks_of(text))),
      rf.count_caps_emphasis(rf.to_prose(text)))
```

Zero on all four, both locales, every entry you touch. Do not run the script with a path argument —
it overwrites `audit/readability_flags.json`, a committed baseline.

## Report

For each reported defect, one block:

- **verdict** — confirmed / false report / could not verify
- **source** — the URL you read, and the sentence in it that settles the question
- **before → after** — the exact claim, old and new, in both locales
- anything you found while looking that is also wrong, and whether you fixed it

Then the defects you left alone and why. Be blunt about what you could not confirm; an honest "could
not verify" is more useful than a confident guess that ships to a reader preparing for an interview.
