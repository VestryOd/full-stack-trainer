# -*- coding: utf-8 -*-
"""Кандидаты на нарушение правил доступности языка.

Правила живут в CLAUDE.md и в content/STYLE.md (2.6, 3.6, 7.7):
термин сначала объясняется по-русски и только потом называется по-английски;
заголовки разделов русские и осмысленные; абзац читается как объяснение живого
человека, а не как выжимка из справочника.

Ни одно из этих правил не ловится readability_flags.py: там меряются длина
предложения, длина абзаца, аббревиатуры и капс. Этот скрипт закрывает пробел.

Инструмент фокусирующий, а не выносящий приговор. Он показывает места, которые
стоит прочитать глазами; решение всегда за чтением. На зоне playwright, которая
писалась уже по этим правилам, он даёт ноль кандидатов.

Что считается кандидатом:
  [7.7] заголовок, где латиницы больше, чем кириллицы (имена в бэктиках не в счёт)
  [2.6] технический термин, перед которым нет объяснения обычными словами
        (глосса в скобках сразу после токена засчитывается)
  [3.6] абзац из четырёх и более предложений, где терминов больше, чем предложений
  [ст.] foo/bar, опора на удержанный контекст, канцелярит

Usage:
  python3 scripts/audit/language_accessibility.py content/topics/<zone>/ru
  python3 scripts/audit/language_accessibility.py content/questions/<zone>.json
  python3 scripts/audit/language_accessibility.py content/topics/<zone>/ru/03-*.md
"""
import re, sys
from pathlib import Path

LAT, CYR = re.compile(r'[A-Za-z]'), re.compile(r'[А-Яа-яЁё]')
FENCE = re.compile(r'^```.*?^```', re.S | re.M)
INLINE = re.compile(r'`[^`\n]*`')
# имя, которое объяснять не нужно: продукт, а не термин
# девять токенов из allowlist 2.1: их не расшифровывают и не объясняют
ALLOWED = {'HTML', 'CSS', 'API', 'JS', 'TS', 'URL', 'HTTP', 'JSON', 'ID'}
PRODUCTS = {'Playwright', 'Chromium', 'Firefox', 'Safari', 'Chrome', 'Node', 'Docker',
            'React', 'Angular', 'Vue', 'Next', 'Redis', 'Postgres', 'PostgreSQL',
            'MongoDB', 'Kafka', 'RabbitMQ', 'GitHub', 'GitLab', 'Linux', 'Windows',
            'Testing', 'Advanced', 'Error', 'Expected', 'Received', 'Running'}
# настоящий технический термин: две заглавные внутри слова или точка в имени
TERM = re.compile(r'(?<![A-Za-z0-9_./-])([A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9]+)+|[A-Z]{2,6})(?![A-Za-z0-9_])')

def strip_code(t): return INLINE.sub(' ', FENCE.sub(' ', t))

def headings(text):
    out, body = [], FENCE.sub(lambda m: '\n' * m.group(0).count('\n'), text)
    for i, line in enumerate(body.splitlines(), 1):
        m = re.match(r'^(#{1,3})\s+(.*)', line)
        if not m: continue
        bare = INLINE.sub(' ', m.group(2))      # имена API в бэктиках разрешены
        lat, cyr = len(LAT.findall(bare)), len(CYR.findall(bare))
        if lat > cyr:
            out.append((i, m.group(2)))
    return out

def unexplained_terms(text, window=200):
    prose = strip_code(text)
    footer = prose.find('## Связь с другими темами')
    if footer == -1: footer = prose.find('## Related topics')
    limit = footer if footer > 0 else len(prose)
    seen, out = set(), []
    for m in TERM.finditer(prose[:limit]):
        tok = m.group(1)
        if tok in seen or tok in PRODUCTS or tok in ALLOWED: continue
        seen.add(tok)
        after = prose[m.end():m.end() + 90]
        if re.match(r'\s*\(', after) and len(CYR.findall(after[:60])) >= 4:
            continue                            # глосса в скобках сразу после токена
        left = prose[max(0, m.start() - window):m.start()]
        sentence = re.split(r'(?<=[.!?])\s', left)[-1] if left else ''
        if len(CYR.findall(sentence)) >= 10:    # объяснение стоит перед термином
            continue
        out.append((prose[:m.start()].count('\n') + 1, tok, ' '.join(sentence.split())[-80:]))
    return out

def dense_paragraphs(text, min_sent=4):
    body, line, out = FENCE.sub('\n\n', text), 1, []
    for block in body.split('\n\n'):
        n_lines = block.count('\n') + 1
        if block.strip() and not block.lstrip().startswith(('#', '-', '*', '|', '>', '1.')):
            prose = INLINE.sub('X', block)
            sents = [s for s in re.split(r'(?<=[.!?])\s+', prose) if s.strip()]
            terms = len(INLINE.findall(block)) + len(TERM.findall(prose))
            if len(sents) >= min_sent and terms > len(sents):
                out.append((line, len(sents), terms, ' '.join(block.split())[:85]))
        line += n_lines + 1
    return out

MARKERS = [(r'\bfoo\b|\bbar\b|\bbaz\b|doSomething', 'абстрактный пример вместо жизненного'),
           (r'как (?:мы )?уже (?:говорил|выяснил|знаем)|как известно|как отмечалось|очевидно,', 'опора на удержанный контекст'),
           (r'\bявляется\b|осуществляется|\bданн(?:ый|ая|ое) \w+|в случае если', 'канцелярит')]

def markers(text):
    prose, out = strip_code(text), []
    for rx, label in MARKERS:
        for m in re.finditer(rx, prose, re.I):
            out.append((prose[:m.start()].count('\n') + 1, label,
                        ' '.join(prose[max(0, m.start() - 45):m.start() + 55].split())))
    return out

def expand(paths):
    """Каталог -> все .md внутри; JSON-банк -> по одному куску на запись и локаль."""
    out = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            out += [(str(f), f.read_text(encoding='utf-8')) for f in sorted(p.rglob('*.md'))]
        elif p.suffix == '.json':
            import json
            try:
                items = json.loads(p.read_text(encoding='utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict) or 'id' not in item:
                    continue
                for field in ('answer', 'explanation', 'description', 'solutionExplanation'):
                    value = item.get(field)
                    if isinstance(value, dict) and isinstance(value.get('ru'), str):
                        out.append((f"{p}#{item['id']}.{field}", value['ru']))
        else:
            out.append((str(p), p.read_text(encoding='utf-8')))
    return out


def main(paths):
    total = 0
    skipped = 0
    for p, text in expand(paths):
        # проверка построена на соотношении латиницы и кириллицы, поэтому
        # английская локаль ей не по зубам: её читают глазами по тому же
        # правилу "объяснение раньше термина" и сверяют паритет с русской
        if '/en/' in p.replace('\\', '/') or p.endswith('.en'):
            skipped += 1
            continue
        h, t, d, mk = headings(text), unexplained_terms(text), dense_paragraphs(text), markers(text)
        n = len(h) + len(t) + len(d) + len(mk)
        total += n
        if not n:
            print(f'{p}: чисто'); continue
        print(f'\n=== {p}  ({n} кандидатов)')
        for line, title in h:            print(f'  [7.7] {line:4} заголовок латиницей: {title}')
        for line, tok, ctx in t[:10]:    print(f'  [2.6] {line:4} {tok} — объяснения перед ним нет | …{ctx}')
        for line, ns, nt, s in d[:6]:    print(f'  [3.6] {line:4} плотный абзац: {ns} предл. / {nt} терминов | {s}…')
        for line, label, ctx in mk[:6]:  print(f'  [ст.] {line:4} {label} | …{ctx}…')
    print(f'\nвсего кандидатов: {total}')
    if skipped:
        print(f'пропущено английских файлов: {skipped} — их проверяют чтением')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        raise SystemExit(1)
    main(sys.argv[1:])
