#!/usr/bin/env python3
"""Generate audit/COVERAGE.md — what the language pass has and has not touched.

The checkbox comes from PASSED below, which is maintained by hand: a zone is
ticked only when a commit closed it. Everything else in the table is measured
live, so the document cannot drift from the content.

Usage:
  python3 scripts/audit/coverage.py > audit/COVERAGE.md
"""

from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import readability_flags as rf  # noqa: E402

# zone key -> commit that closed it. Keep in sync with the branch history.
PASSED = {
    'article:postgresql': '2ac9e6f, 6d78f51',
    'article:system-design': '5756a08, ea2075c',
    'article:prisma': 'f6e4f20, 92e2037',
    'article:mongodb-mongoose': '525f8a2, 237f2b2',
    'article:nodejs': 'c59d3f1, f094918',
    'article:react': '892d62d, a06c8ca',
    'bank:system-design': 'wave 1',
    'bank:nodejs': 'wave 1',
    'bank:react': 'wave 1',
    'bank:http-rest': '926309e',
    'bank:postgresql': 'wave 1 (written from scratch)',
    'bank:prisma': '77b4835',
    'bank:browser-runtime': '9e7f625',
    'quiz:postgresql': '6d78f51',
    'quiz:browser-runtime': 'c5a809b',
    'article:typescript': 'a569679',
    'article:nestjs': '4d92284, 219814b',
    'bank:typescript': 'ba80fea, 7b1acf3',
    'bank:nestjs': '3036c4a',
    'quiz:typescript': 'ea81281',
    'quiz:nestjs': '3036c4a',
    'article:http-rest': '28f1fb1, d4dbf18',
    'quiz:http-rest': 'eeb9fc7',
    'article:javascript': '3f2bb28, e07165c',
    'article:nextjs': '00b9614',
    'quiz:javascript': 'edcb48f',
    'quiz:nextjs': '3f2bb28',
    'bank:nextjs': 'wave B',
}

MEASURE = ('unexpanded abbreviations, over-limit sentences, '
           'over-long paragraphs, ALL-CAPS emphasis')


def md_flags(paths: list[str]) -> tuple[int, int]:
    total = words = 0
    for p in paths:
        locale = 'ru' if '/ru/' in p else 'en'
        text = Path(p).read_text(encoding='utf-8')
        prose = rf.to_prose(text)
        total += (len(rf.find_abbreviations(prose, locale))
                  + len(rf.find_long_sentences(text, locale))
                  + len(rf.find_long_paragraphs(rf.blocks_of(text)))
                  + rf.count_caps_emphasis(prose))
        words += len(rf.to_prose(text, keep_inline=True).split())
    return total, words


def json_flags(path: str, fields: tuple[str, ...]) -> tuple[dict[str, int], int]:
    per_field = {f: 0 for f in fields}
    words = 0
    for item in json.loads(Path(path).read_text(encoding='utf-8')):
        for locale in ('en', 'ru'):
            for field in fields:
                value = item.get(field)
                if not isinstance(value, dict):
                    continue
                chunk = value.get(locale)
                texts = [chunk] if isinstance(chunk, str) else list(chunk or [])
                for text in texts:
                    prose = rf.to_prose(text)
                    per_field[field] += (len(rf.find_abbreviations(prose, locale))
                                         + len(rf.find_long_sentences(text, locale))
                                         + len(rf.find_long_paragraphs(rf.blocks_of(text)))
                                         + rf.count_caps_emphasis(prose))
                    words += len(rf.to_prose(text, keep_inline=True).split())
    return per_field, words


def wide_lines(path: str) -> int:
    out = subprocess.run(
        [sys.executable, 'scripts/audit/block_width.py', path, '--quiet'],
        capture_output=True, text=True).stdout
    match = re.search(r'(\d+) lines over budget', out)
    return int(match.group(1)) if match else 0


def thousands(n: int) -> str:
    return f'{n:,}'.replace(',', ' ')


def tick(key: str) -> str:
    return '[x]' if key in PASSED else '[ ]'


def main() -> int:
    print('# Покрытие языковым проходом\n')
    print('Сгенерировано `python3 scripts/audit/coverage.py > audit/COVERAGE.md`. Галочка ставится')
    print('вручную в `PASSED` внутри скрипта — только когда зону закрыл коммит. Все числа')
    print('измеряются на текущем контенте, поэтому таблица не может разойтись с деревом.\n')
    print(f'«Флаги» — это {MEASURE}.')
    print('«Широкие» — строки в фенсах сверх 68 колонок для `txt` и 92 для кода,')
    print('по `scripts/audit/block_width.py`.\n')
    print('Ноль флагов — не цель сам по себе: у нескольких закрытых зон остаток это')
    print('артефакты измерения, и они описаны в `audit/PROGRESS.md`.\n')

    print('## Статьи\n')
    print('| | Тема | Файлов | Слов | Флаги | Широкие | Закрыто |')
    print('|---|---|---|---|---|---|---|')
    rows = []
    for topic in sorted(os.listdir('content/topics')):
        files = sorted(glob.glob(f'content/topics/{topic}/*/*.md'))
        if not files:
            continue
        flags, words = md_flags(files)
        rows.append((f'article:{topic}', topic, len(files), words, flags,
                     wide_lines(f'content/topics/{topic}')))
    for key, name, n, words, flags, wide in sorted(rows, key=lambda r: (r[0] not in PASSED, -r[4])):
        print(f'| {tick(key)} | `{name}` | {n} | {thousands(words)} | {flags} | {wide} | '
              f'{PASSED.get(key, "—")} |')

    print('\n## Банки вопросов\n')
    print('Флаги разделены по полям: проход правил **ответы**, текст вопросов не мерил никто.')
    print('Это записанный долг — 246 предложений сверх лимита в полях `question` по всем банкам.\n')
    print('| | Банк | Записей | Слов | Флаги в ответах | Флаги в вопросах | Закрыто |')
    print('|---|---|---|---|---|---|---|')
    banks = []
    for path in sorted(glob.glob('content/questions/*.json')):
        name = os.path.basename(path)[:-5]
        per_field, words = json_flags(path, ('question', 'answer'))
        n = len(json.loads(Path(path).read_text(encoding='utf-8')))
        banks.append((f'bank:{name}', name, n, words, per_field['answer'], per_field['question']))
    for key, name, n, words, ans, quest in sorted(banks, key=lambda r: (r[0] not in PASSED, -r[4])):
        print(f'| {tick(key)} | `{name}` | {n} | {thousands(words)} | {ans} | {quest} | '
              f'{PASSED.get(key, "—")} |')

    print('\n## Квизы\n')
    print('Ключи и длины вариантов выровнены во **всех** квизах ещё в очереди 1 — слепые')
    print('стратегии по сайту держатся у случайных 25%. Галочка ниже только про язык.\n')
    print('Флаги здесь считаются по полю, а не по заданию, поэтому у закрытой зоны')
    print('остаётся остаток: аббревиатура стоит в варианте ответа, а расшифрована в')
    print('вопросе или объяснении того же задания. По §2.2 это норма — читатель видит')
    print('задание целиком. У `http-rest` весь остаток такой: SSE, CORS и URI в')
    print('вариантах при глоссе в вопросе.\n')
    print('| | Квиз | Заданий | Слов | Флаги | Закрыто |')
    print('|---|---|---|---|---|---|')
    quizzes = []
    for path in sorted(glob.glob('content/quiz/*.json')):
        name = os.path.basename(path)[:-5]
        per_field, words = json_flags(path, ('question', 'explanation', 'options'))
        n = len(json.loads(Path(path).read_text(encoding='utf-8')))
        quizzes.append((f'quiz:{name}', name, n, words, sum(per_field.values())))
    for key, name, n, words, flags in sorted(quizzes, key=lambda r: (r[0] not in PASSED, -r[4])):
        print(f'| {tick(key)} | `{name}` | {n} | {thousands(words)} | {flags} | '
              f'{PASSED.get(key, "—")} |')

    done = sum(1 for r in rows if r[0] in PASSED) + \
        sum(1 for b in banks if b[0] in PASSED) + sum(1 for q in quizzes if q[0] in PASSED)
    total = len(rows) + len(banks) + len(quizzes)
    print(f'\n**Итого закрыто {done} зон из {total}.**')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
