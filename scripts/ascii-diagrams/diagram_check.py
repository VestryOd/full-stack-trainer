#!/usr/bin/env python3
"""Validate box-drawing diagrams inside markdown code fences.

Scans every fenced code block that contains box-drawing characters and
verifies box geometry: each ┌ must close into a rectangle (top edge of ─/┬
ending in ┐, sides of │/├/┤, bottom edge of ─/┴ between └ and ┘ on the same
rows/columns). Catches the classic hand-padding bug where ru/en text length
shifts a border by a column. Corners that no valid box claims are reported
as orphans.

Only blocks containing at least one ┌ are treated as box diagrams. File
trees (├── / └── with no ┌) are not diagrams and are skipped; don't mix a
file tree and a box diagram in one fenced block.

Usage:
  python3 scripts/ascii-diagrams/diagram_check.py <dir-or-file> [...]

Exit code 0 = every block PASS, 1 = at least one FAIL.
"""

import json
import os
import sys
from pathlib import Path

BOX_CHARS = set('┌┐└┘─│├┤┬┴┼')


def check_block(lines):
    grid = [list(l) for l in lines]

    def at(r, c):
        if r < 0 or r >= len(grid) or c < 0 or c >= len(grid[r]):
            return ' '
        return grid[r][c]

    errors = []
    claimed = set()

    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            if ch != '┌':
                continue
            # top edge → find the matching ┐
            cc = c + 1
            while at(r, cc) in '─┬':
                cc += 1
            if at(r, cc) != '┐':
                errors.append(f'line {r + 1}, col {c + 1}: top edge does not close with ┐')
                continue
            right = cc
            # left side ↓ find └
            rr = r + 1
            while at(rr, c) in '│├':
                rr += 1
            if at(rr, c) != '└':
                errors.append(f'line {r + 1}, col {c + 1}: left side does not close with └')
                continue
            bottom = rr
            # right side ↓ must close with ┘ on the same row
            rr = r + 1
            while at(rr, right) in '│┤':
                rr += 1
            if at(rr, right) != '┘' or rr != bottom:
                errors.append(
                    f'line {r + 1}, col {c + 1}: right side misaligned '
                    f'(expected ┘ at line {bottom + 1}, col {right + 1})'
                )
                continue
            # bottom edge between └ and ┘
            bad = next(
                (cc for cc in range(c + 1, right) if at(bottom, cc) not in '─┴'),
                None,
            )
            if bad is not None:
                errors.append(f'line {bottom + 1}, col {bad + 1}: bottom edge broken')
                continue
            claimed.update({(r, c), (r, right), (bottom, c), (bottom, right)})

    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            if ch in '┌┐└┘' and (r, c) not in claimed:
                errors.append(f'line {r + 1}, col {c + 1}: orphan corner {ch}')

    return errors


def _blocks_in_text(lines, label_prefix=''):
    """Yield (label, block_lines) for fenced blocks containing box chars."""
    in_fence = False
    block, start = [], 0
    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith('```'):
            if in_fence:
                if any('\u250c' in l for l in block):
                    yield f'{label_prefix}{start}', block
                in_fence = False
            else:
                in_fence = True
                block, start = [], i + 1
            continue
        if in_fence:
            block.append(line)


# Locale-mapped markdown fields of the JSON rubrics. Diagrams live in the answer /
# explanation / description bodies, never in a question stem or a quiz option.
JSON_FIELDS = ('answer', 'explanation', 'description', 'solutionExplanation')


def iter_json_diagram_blocks(json_path):
    """Same, for content/questions, content/quiz and content/tasks."""
    try:
        items = json.loads(Path(json_path).read_text(encoding='utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, dict) or 'id' not in item:
            continue
        for field in JSON_FIELDS:
            value = item.get(field)
            if not isinstance(value, dict):
                continue
            for locale in ('en', 'ru'):
                text = value.get(locale)
                if not isinstance(text, str):
                    continue
                prefix = f"{item['id']}.{field}.{locale}:"
                yield from _blocks_in_text(text.splitlines(), prefix)


def iter_diagram_blocks(md_path):
    """Yield (start_line, block_lines) for fenced blocks containing box chars."""
    with open(md_path, encoding='utf-8') as f:
        lines = f.read().splitlines()
    in_fence = False
    block, start = [], 0
    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith('```'):
            if in_fence:
                if any('┌' in l for l in block):
                    yield start, block
                in_fence = False
            else:
                in_fence = True
                block, start = [], i + 1
            continue
        if in_fence:
            block.append(line)


def main():
    targets = sys.argv[1:]
    if not targets:
        print(__doc__.strip(), file=sys.stderr)
        return 1

    md_files = []
    json_files = []
    for t in targets:
        if os.path.isdir(t):
            for root, _, files in os.walk(t):
                for f in sorted(files):
                    if f.endswith('.md'):
                        md_files.append(os.path.join(root, f))
                    elif f.endswith('.json'):
                        json_files.append(os.path.join(root, f))
        elif t.endswith('.json'):
            json_files.append(t)
        else:
            md_files.append(t)

    failed = 0
    total = 0
    for path in json_files:
        for label, block in iter_json_diagram_blocks(path):
            total += 1
            errors = check_block(block)
            if errors:
                failed += 1
                print(f'FAIL  {path} {label}')
                for e in errors:
                    print(f'      {e}')
            else:
                print(f'PASS  {path} {label}')
    for path in md_files:
        for start, block in iter_diagram_blocks(path):
            total += 1
            errors = check_block(block)
            if errors:
                failed += 1
                print(f'FAIL  {path}:{start}')
                for e in errors:
                    print(f'      {e}')
            else:
                print(f'PASS  {path}:{start}')

    print(f'\n{total - failed}/{total} diagram blocks passed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
