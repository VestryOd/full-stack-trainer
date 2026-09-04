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
    'bank:nextjs': '238a295',
    'bank:javascript': '3811745',
    'article:redis': 'c24b702',
    'article:graphql': '79f88bb',
    'bank:graphql': '79f88bb',
    'quiz:graphql': '79f88bb',
    'article:oop-patterns': 'f9dc1ca',
    'bank:oop-patterns': 'f9dc1ca',
    'quiz:oop-patterns': 'f9dc1ca',
    'article:architecture': '61ad2a3',
    'bank:architecture': '61ad2a3',
    'quiz:architecture': '61ad2a3',
    'article:cicd-devops': '7e15fb8',
    'bank:cicd-devops': '7e15fb8',
    'article:microfrontends': '8ee72de',
    'article:css-html': '8ee72de',
    'bank:css-html': '8ee72de',
    'quiz:css-html': '8ee72de',
    'quiz:react': '8ee72de',
    'quiz:nodejs': '8ee72de',
    'article:build-tools': '6484f91',
    'bank:bundlers': '6484f91',
    'bank:algorithms': '6484f91',
    'quiz:algorithms': '6484f91',
    'article:aws': 'f13f14e',
    'article:security': '41ef61b',
    'bank:security': '41ef61b',
    'quiz:security': '41ef61b',
    'article:strapi': 'b74d2cc',
    'bank:solid-grasp': 'ee46a79',
    'quiz:solid-grasp': 'ee46a79',
    'article:web-performance': '00cad51',
    'bank:web-performance': '00cad51',
    'quiz:web-performance': '00cad51',
    'bank:git': '52c22a5',
    'quiz:git': '52c22a5',
    'article:rabbitmq': '4dc6e04',
    'article:kafka': '4dc6e04',
    'course:nx-monorepo': '8858a81',
    'bank:nx': '8858a81',
    'article:state-management': 'e9da501',
    'bank:docker': 'e9da501',
    'quiz:docker': 'e9da501',
    'course:python-fullstack': 'c8002fc',
    'bank:python': '574ba8c',
    'bank:testing': '574ba8c',
    'quiz:testing': '574ba8c',
    'bank:angular': '78bda0a',
    'article:keycloak-auth': '3be5fee',
    'bank:ddd': 'ed7942b',
    'bank:tdd': 'ed7942b',
    'bank:event-driven': 'ed7942b',
    'article:agile-scrum': '3200ef7',
    'course:angular': '4300b36',
    'article:rxjs': '4300b36',
    'article:browser-animation': 'b3273ba',
    'article:canvas-graphics': '6e35341',
    'tasks:graphql': 'wave 25',
    'tasks:javascript': 'wave 25',
    'tasks:algorithms': 'wave 25',
    'tasks:react': 'wave 25',
    'tasks:typescript': 'wave 25',
    'tasks:nodejs': 'wave 25',
    'tasks:testing': 'wave 25',
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


def task_code_wide_lines(path: str) -> int:
    """Over-budget lines in `starterCode`/`solution` alone.

    Split out from the prose count so the tick stays honest: those two fields are
    code, the language pass does not touch them, and their 220 over-budget lines
    across the rubric are a separate debt from the text ones.
    """
    total = 0
    for item in json.loads(Path(path).read_text(encoding='utf-8')):
        for field in ('starterCode', 'solution'):
            value = item.get(field)
            if not isinstance(value, str):
                continue
            total += sum(1 for line in value.split('\n') if len(line) > 92)
    return total


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

    print('\n## Курсы\n')
    print('Курсы лежат в `content/courses` и до волны 15 не входили в учёт вовсе — сто файлов')
    print('и 292 тысячи слов были невидимы для этой таблицы, хотя аудит их смотрел (шесть')
    print('отчётов в `audit/readability/course-*.json`). Мерятся тем же способом, что статьи.\n')
    print('| | Курс | Файлов | Слов | Флаги | Широкие | Закрыто |')
    print('|---|---|---|---|---|---|---|')
    courses = []
    for course in sorted(os.listdir('content/courses')):
        files = sorted(glob.glob(f'content/courses/{course}/*/*.md'))
        if not files:
            continue
        flags, words = md_flags(files)
        courses.append((f'course:{course}', course, len(files), words, flags,
                        wide_lines(f'content/courses/{course}')))
    for key, name, n, words, flags, wide in sorted(courses, key=lambda r: (r[0] not in PASSED, -r[4])):
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

    print('\n## Задачи\n')
    print('Задачи лежат в `content/tasks` и до сентября 2026 не входили в учёт вовсе —')
    print('восемь файлов и 243 задачи были невидимы для этой таблицы, и отчётов аудита')
    print('по ним не существует: рубрика в аудит не входила. Флаги считаются по полям')
    print('`title`, `description` и `solutionExplanation`; `starterCode` и `solution` —')
    print('код, и это единая строка на обе локали, а не пара локалей.\n')
    print('`title` рендерится **обычным текстом** (`TaskView.tsx` кладёт `{t(task.title)}`')
    print('в `h1`), поэтому бэктики и `**` там печатаются буквально. Флаги в нём')
    print('вынесены отдельной колонкой: их мало, но каждый виден читателю дословно.\n')
    print('«Широкие» — строки сверх бюджета в фенсах `description` и')
    print('`solutionExplanation`, то есть в тексте. «В коде» — то же самое в')
    print('`starterCode` и `solution`. Колонки разведены, потому что галочка')
    print('означает языковой проход, а он этих двух полей не касается: они код,')
    print('единый на обе локали. 220 длинных строк в них — **отдельный записанный')
    print('долг**, найденный волной 25 после того, как `block_width.py` научили')
    print('видеть сначала поля задач, а потом и эти два.\n')
    print('| | Задачи | Задач | Слов | Флаги в объяснениях | В описаниях | В названиях | Широкие | В коде | Закрыто |')
    print('|---|---|---|---|---|---|---|---|---|---|')
    tasks = []
    for path in sorted(glob.glob('content/tasks/*.json')):
        name = os.path.basename(path)[:-5]
        per_field, words = json_flags(path, ('title', 'description', 'solutionExplanation'))
        n = len(json.loads(Path(path).read_text(encoding='utf-8')))
        code_wide = task_code_wide_lines(path)
        tasks.append((f'tasks:{name}', name, n, words, per_field['solutionExplanation'],
                      per_field['description'], per_field['title'],
                      wide_lines(path) - code_wide, code_wide))
    for key, name, n, words, expl, desc, ttl, wide, code_wide in sorted(
            tasks, key=lambda r: (r[0] not in PASSED, -(r[4] + r[5] + r[6]))):
        print(f'| {tick(key)} | `{name}` | {n} | {thousands(words)} | {expl} | {desc} | '
              f'{ttl} | {wide} | {code_wide} | {PASSED.get(key, "—")} |')

    done = sum(1 for r in rows if r[0] in PASSED) + \
        sum(1 for c in courses if c[0] in PASSED) + \
        sum(1 for b in banks if b[0] in PASSED) + sum(1 for q in quizzes if q[0] in PASSED) + \
        sum(1 for t in tasks if t[0] in PASSED)
    total = len(rows) + len(courses) + len(banks) + len(quizzes) + len(tasks)
    print(f'\n**Итого закрыто {done} зон из {total}.**')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
