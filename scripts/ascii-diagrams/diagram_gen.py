#!/usr/bin/env python3
"""Programmatic box-drawing diagram generator for course content.

Box-drawing diagrams in content/ must never be typed by hand: text width
differs between ru/en, and hand-padded borders drift. Instead, each diagram
is a small builder function here; the output is pasted into the chapter and
validated with diagram_check.py.

Usage:
  python3 scripts/ascii-diagrams/diagram_gen.py <diagram> <lang>
  python3 scripts/ascii-diagrams/diagram_gen.py --list
"""

import sys

# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------


def box(lines, min_width=0):
    """Wrap lines in a ┌─┐│└─┘ box, padded to the longest line."""
    inner = max([len(l) for l in lines] + [min_width])
    top = '┌' + '─' * (inner + 2) + '┐'
    body = ['│ ' + l.ljust(inner) + ' │' for l in lines]
    bottom = '└' + '─' * (inner + 2) + '┘'
    return [top, *body, bottom]


def layered(sections, min_width=0):
    """One box with ├───┤ separators between sections (a layer stack)."""
    inner = max([len(l) for sec in sections for l in sec] + [min_width])
    out = ['┌' + '─' * (inner + 2) + '┐']
    for i, sec in enumerate(sections):
        if i:
            out.append('├' + '─' * (inner + 2) + '┤')
        out.extend('│ ' + l.ljust(inner) + ' │' for l in sec)
    out.append('└' + '─' * (inner + 2) + '┘')
    return out


def hstack(blocks, gap=2):
    """Place blocks side by side, top-aligned."""
    height = max(len(b) for b in blocks)
    widths = [max(len(l) for l in b) for b in blocks]
    padded = [
        [(b[i] if i < len(b) else '').ljust(w) for i in range(height)]
        for b, w in zip(blocks, widths)
    ]
    sep = ' ' * gap
    return [sep.join(row).rstrip() for row in zip(*padded)]


def vstack(blocks, gap=0):
    out = []
    for i, b in enumerate(blocks):
        if i and gap:
            out.extend([''] * gap)
        out.extend(b)
    return out


def centered(text, width):
    return text.center(width).rstrip()


def h_arrow(label, height, arrow_row):
    """A horizontal ──▶ connector block to place between boxes in hstack."""
    width = max(len(label) + 2, 8)
    rows = [''] * height
    if label:
        rows[arrow_row - 1] = label.center(width).rstrip()
    rows[arrow_row] = '─' * (width - 1) + '▶'
    return rows


def vchain(boxes, labels=None):
    """Stack boxes vertically with a centered │/▼ connector between them."""
    inner = max(len(l) for b in boxes for l in b)
    labels = labels or [''] * (len(boxes) - 1)
    out = []
    for i, b in enumerate(boxes):
        if i:
            col = (inner + 4) // 2
            label = labels[i - 1]
            out.append(' ' * col + '│' + ('  ' + label if label else ''))
            out.append(' ' * col + '▼')
        out.extend(box(b, min_width=inner))
    return out


def with_title_and_notes(block, title, notes):
    """A caption above and note lines below, centered on the block width."""
    width = max(len(l) for l in block)
    return [
        centered(title, width),
        *block,
        *[centered(n, width) for n in notes],
    ]


# ---------------------------------------------------------------------------
# Diagram builders
# ---------------------------------------------------------------------------


def polyrepo_vs_monorepo(L):
    left = with_title_and_notes(
        hstack([box(L['repo1']), box(L['repo2'])], gap=1),
        L['poly_title'],
        L['poly_notes'],
    )
    right = with_title_and_notes(box(L['mono_lines']), L['mono_title'], L['mono_notes'])
    return hstack([left, right], gap=5)


def nx_stack(L):
    return layered([L['layer1'], L['layer2'], L['layer3'], L['layer4']])


def target_merge(L):
    block = layered([L['layer1'], L['layer2'], L['layer3']])
    return with_title_and_notes(block, L['title'], L['notes'])


def graph_mini(L):
    b1, b2, b3 = box([L['node1']]), box([L['node2']]), box([L['node3']])
    return hstack(
        [b1, h_arrow(L['edge1'], 3, 1), b2, h_arrow(L['edge2'], 3, 1), b3],
        gap=1,
    )


def graph_pipeline(L):
    return vchain([L['step1'], L['step2'], L['step3'], L['step4']], L['edges'])


def task_flow(L):
    return vchain([L['step1'], L['step2'], L['step3'], L['step4'], L['step5']])


def hash_inputs(L):
    block = layered([L['head'], L['items']])
    width = max(len(l) for l in block)
    return block + [centered(n, width) for n in L['notes']]


def affected_flow(L):
    return vchain([L['step1'], L['step2'], L['step3'], L['step4']])


def table(rows):
    """Render rows of equal-length string tuples as a ┌┬┐ bordered table."""
    cols = len(rows[0])
    widths = [max(len(r[i]) for r in rows) for i in range(cols)]

    def hline(left, mid, right):
        return left + mid.join('─' * (w + 2) for w in widths) + right

    out = [hline('┌', '┬', '┐')]
    for i, row in enumerate(rows):
        if i:
            out.append(hline('├', '┼', '┤'))
        out.append('│ ' + ' │ '.join(c.ljust(w) for c, w in zip(row, widths)) + ' │')
    out.append(hline('└', '┴', '┘'))
    return out


def type_matrix(L):
    return table(L['rows'])


def generator_flow(L):
    return vchain([L['step1'], L['step2'], L['step3'], L['step4'], L['step5']])


def executor_choice(L):
    return table(L['rows'])


def mf_topology(L):
    top = box(L['host'])
    bottom = hstack([box(L['remote1']), box(L['remote2'])], gap=4)
    width = max(len(l) for l in bottom)
    out = [centered(l, width) for l in top]
    out.append(centered(L['edge'], width))
    out.append(centered('▼', width))
    out.extend(bottom)
    return out


def mf_load(L):
    return vchain([L[f'step{i}'] for i in range(1, 7)])


def serve_topology(L):
    top = box(L['host'])
    bottom = hstack([box(L['remote1']), box(L['remote2'])], gap=4)
    width = max(len(l) for l in bottom)
    out = [centered(L['title'], width), '']
    out += [centered(l, width) for l in top]
    out.append(centered(L['edge'], width))
    out.append(centered('▼', width))
    out.extend(bottom)
    out.append('')
    out.append(centered(L['note'], width))
    return out


def mf_errors(L):
    return table(L['rows'])


def ci_flow(L):
    return vchain([L[f'step{i}'] for i in range(1, 6)])


def audit_map(L):
    return table(L['rows'])


DIAGRAMS = {
    'polyrepo-vs-monorepo': polyrepo_vs_monorepo,
    'nx-stack': nx_stack,
    'target-merge': target_merge,
    'graph-mini': graph_mini,
    'graph-pipeline': graph_pipeline,
    'task-flow': task_flow,
    'hash-inputs': hash_inputs,
    'affected-flow': affected_flow,
    'type-matrix': type_matrix,
    'generator-flow': generator_flow,
    'executor-choice': executor_choice,
    'mf-topology': mf_topology,
    'mf-load': mf_load,
    'serve-topology': serve_topology,
    'mf-errors': mf_errors,
    'contract-hub': serve_topology,
    'ci-flow': ci_flow,
    'audit-map': audit_map,
}

LABELS = {
    'polyrepo-vs-monorepo': {
        'ru': {
            'poly_title': 'POLYREPO: репозиторий на приложение',
            'repo1': ['shop-web', '', 'ui-kit@1.2', 'types@1.8'],
            'repo2': ['shop-api', '', 'types@2.1', ''],
            'poly_notes': [
                'шаринг кода — через npm publish;',
                'версии расходятся, изменение',
                'контракта = несколько PR и релизов',
            ],
            'mono_title': 'MONOREPO: один репозиторий',
            'mono_lines': [
                'mini-shop/',
                '',
                'apps/  shell · catalog',
                '       checkout · api',
                'libs/  shared/ui',
                '       shared/api-types',
            ],
            'mono_notes': [
                'один граф импортов, единые версии,',
                'атомарный PR через границы проектов',
            ],
        },
        'en': {
            'poly_title': 'POLYREPO: one repo per app',
            'repo1': ['shop-web', '', 'ui-kit@1.2', 'types@1.8'],
            'repo2': ['shop-api', '', 'types@2.1', ''],
            'poly_notes': [
                'code is shared via npm publish;',
                'versions drift, one contract change',
                'means several PRs and releases',
            ],
            'mono_title': 'MONOREPO: a single repository',
            'mono_lines': [
                'mini-shop/',
                '',
                'apps/  shell · catalog',
                '       checkout · api',
                'libs/  shared/ui',
                '       shared/api-types',
            ],
            'mono_notes': [
                'one import graph, single dep versions,',
                'atomic PRs across project boundaries',
            ],
        },
    },
    'nx-stack': {
        'ru': {
            'layer1': [
                'плагины: @nx/react, @nx/node, @nx/eslint, ...',
                'генераторы · executors · inferred targets',
            ],
            'layer2': [
                'ядро Nx: project graph · task pipeline',
                'computation cache · affected',
            ],
            'layer3': [
                'workspaces пакетного менеджера (npm/pnpm/yarn):',
                'установка зависимостей, симлинки пакетов',
            ],
            'layer4': ['обычный git-репозиторий: apps/ · libs/ · nx.json'],
        },
        'en': {
            'layer1': [
                'plugins: @nx/react, @nx/node, @nx/eslint, ...',
                'generators · executors · inferred targets',
            ],
            'layer2': [
                'Nx core: project graph · task pipeline',
                'computation cache · affected',
            ],
            'layer3': [
                'package manager workspaces (npm/pnpm/yarn):',
                'dependency install, package symlinks',
            ],
            'layer4': ['a plain git repository: apps/ · libs/ · nx.json'],
        },
    },
    'target-merge': {
        'ru': {
            'title': 'приоритет: выше = сильнее',
            'layer1': [
                '3. project.json проекта (и ключ "nx"',
                '   в package.json) — точечные переопределения',
            ],
            'layer2': [
                '2. nx.json: targetDefaults — дефолты для всех',
                '   одноимённых target-ов workspace',
            ],
            'layer3': [
                '1. inferred targets от плагинов (crystal):',
                '   vite.config.ts → build / serve / preview / test',
            ],
            'notes': ['итог: nx show project shell --web'],
        },
        'en': {
            'title': 'precedence: higher = stronger',
            'layer1': [
                '3. the project\'s project.json (and the "nx" key',
                '   in package.json) — targeted overrides',
            ],
            'layer2': [
                '2. nx.json: targetDefaults — defaults for all',
                '   same-named targets across the workspace',
            ],
            'layer3': [
                '1. targets inferred by plugins (crystal):',
                '   vite.config.ts → build / serve / preview / test',
            ],
            'notes': ['the result: nx show project shell --web'],
        },
    },
    'graph-mini': {
        'ru': {
            'node1': 'apps/shell',
            'edge1': 'static',
            'node2': 'libs/shared/ui',
            'edge2': 'static',
            'node3': 'npm:react',
        },
        'en': {
            'node1': 'apps/shell',
            'edge1': 'static',
            'node2': 'libs/shared/ui',
            'edge2': 'static',
            'node3': 'npm:react',
        },
    },
    'graph-pipeline': {
        'ru': {
            'step1': ['исходники всех проектов', '*.ts / *.tsx / *.js'],
            'step2': ['парсинг импортов (AST, не grep):', 'import / require / import()'],
            'step3': ['резолв каждого импорта в проект:', 'paths-алиасы / workspaces / имена пакетов'],
            'step4': ['рёбра графа', '+ implicitDependencies из project.json'],
            'edges': ['', '', ''],
        },
        'en': {
            'step1': ['source files of every project', '*.ts / *.tsx / *.js'],
            'step2': ['import parsing (AST, not grep):', 'import / require / import()'],
            'step3': ['resolving each import to a project:', 'path aliases / workspaces / package names'],
            'step4': ['graph edges', '+ implicitDependencies from project.json'],
            'edges': ['', '', ''],
        },
    },
    'task-flow': {
        'ru': {
            'step1': ['nx build shell  (= nx run shell:build)'],
            'step2': ['project graph + dependsOn → TASK GRAPH:', 'узлы — задачи вида проект:target'],
            'step3': ['хеш каждой задачи → проверка кеша:', 'hit → мгновенный replay из .nx/cache'],
            'step4': ['miss → запуск executor-а задачи', 'параллельно, в топологическом порядке'],
            'step5': ['outputs + stdout сохраняются в кеш', '(механика хеша — глава 04)'],
        },
        'en': {
            'step1': ['nx build shell  (= nx run shell:build)'],
            'step2': ['project graph + dependsOn → TASK GRAPH:', 'nodes are tasks of the form project:target'],
            'step3': ['hash every task → cache lookup:', 'hit → instant replay from .nx/cache'],
            'step4': ['miss → run the task\'s executor', 'in parallel, in topological order'],
            'step5': ['outputs + stdout are saved to the cache', '(hash mechanics — chapter 04)'],
        },
    },
    'hash-inputs': {
        'ru': {
            'head': ['хеш задачи shell:build считается от:'],
            'items': [
                '· контент файлов shell, попавших в inputs (production)',
                '· контент файлов всех зависимостей (^production)',
                '· конфигурация target-а: команда и опции',
                '· версии externalDependencies (npm:vite, ...)',
                '· sharedGlobals и задекларированные env-переменные',
            ],
            'notes': ['ключ найден в .nx/cache → replay, не найден → запуск'],
        },
        'en': {
            'head': ['the shell:build task hash is computed from:'],
            'items': [
                '· content of shell files matched by inputs (production)',
                '· content of every dependency\'s files (^production)',
                '· the target configuration: command and options',
                '· versions of externalDependencies (npm:vite, ...)',
                '· sharedGlobals and declared env variables',
            ],
            'notes': ['key found in .nx/cache → replay, not found → run'],
        },
    },
    'affected-flow': {
        'ru': {
            'step1': ['git merge-base(base, head) → git diff', 'список изменённых файлов'],
            'step2': ['каждый файл → проект-владелец', '(по projectRoot; вне всех проектов = глобальное изменение)'],
            'step3': ['замыкание ВВЕРХ по графу:', '+ все, кто зависит от изменённых (транзитивно)'],
            'step4': ['nx affected -t lint,test,build:', 'обычный task graph, но только для затронутых'],
        },
        'en': {
            'step1': ['git merge-base(base, head) → git diff', 'the list of changed files'],
            'step2': ['each file → its owning project', '(by projectRoot; outside all projects = a global change)'],
            'step3': ['closure UP the graph:', '+ everyone who depends on the changed (transitively)'],
            'step4': ['nx affected -t lint,test,build:', 'a regular task graph, but only for the affected'],
        },
    },
    'type-matrix': {
        'ru': {
            'rows': [
                ('тип либы', 'может зависеть от', 'что внутри'),
                ('type:feature', 'feature · ui · data-access · util', 'страницы, smart-компоненты, флоу'),
                ('type:ui', 'ui · util', 'глупые компоненты, без данных'),
                ('type:data-access', 'data-access · util', 'API-клиенты, стейт, сервисы'),
                ('type:util', 'util', 'чистые функции, типы, хелперы'),
            ],
        },
        'en': {
            'rows': [
                ('lib type', 'may depend on', 'what lives inside'),
                ('type:feature', 'feature · ui · data-access · util', 'pages, smart components, flows'),
                ('type:ui', 'ui · util', 'dumb components, no data'),
                ('type:data-access', 'data-access · util', 'API clients, state, services'),
                ('type:util', 'util', 'pure functions, types, helpers'),
            ],
        },
    },
    'generator-flow': {
        'ru': {
            'step1': ['nx g @mini-shop/workspace-plugin:feature-lib cart'],
            'step2': ['schema.json: валидация опций,', 'x-prompt дособирает недостающие'],
            'step3': ['implementation(tree, options):', 'все изменения — в ВИРТУАЛЬНОЙ ФС (Tree)'],
            'step4': ['--dry-run: напечатать diff Tree и выйти,', 'диск не тронут'],
            'step5': ['без dry-run: flush Tree на диск,', 'форматирование, установка пакетов'],
        },
        'en': {
            'step1': ['nx g @mini-shop/workspace-plugin:feature-lib cart'],
            'step2': ['schema.json: option validation,', 'x-prompt collects what is missing'],
            'step3': ['implementation(tree, options):', 'every change goes to a VIRTUAL FS (Tree)'],
            'step4': ['--dry-run: print the Tree diff and exit,', 'the disk is untouched'],
            'step5': ['without dry-run: flush the Tree to disk,', 'formatting, package installs'],
        },
    },
    'executor-choice': {
        'ru': {
            'rows': [
                ('хватит nx:run-commands', 'нужен кастомный executor'),
                ('обернуть готовый CLI одной командой', 'логика: условия, ретраи, вызовы API'),
                ('несколько команд подряд/параллельно', 'типизированные опции со schema-валидацией'),
                ('разовый скрипт конкретной репы', 'переиспользование в десятках проектов'),
                ('вывод и exit code — достаточно', 'нужен context: граф, root, configuration'),
            ],
        },
        'en': {
            'rows': [
                ('nx:run-commands is enough', 'a custom executor is warranted'),
                ('wrapping an existing CLI in one command', 'logic: conditions, retries, API calls'),
                ('a few commands, serial or parallel', 'typed options with schema validation'),
                ('a one-off script for this repo', 'reuse across dozens of projects'),
                ('output and exit code suffice', 'context needed: graph, root, configuration'),
            ],
        },
    },
    'mf-topology': {
        'ru': {
            'host': ['shell (host)', 'роутер, layout, auth,', 'адреса remoteEntry remote-ов'],
            'edge': 'загружает В РАНТАЙМЕ, в браузере пользователя',
            'remote1': ['catalog (remote)', 'exposes:', './CatalogPage'],
            'remote2': ['checkout (remote)', 'exposes:', './CheckoutPage'],
        },
        'en': {
            'host': ['shell (host)', 'router, layout, auth,', "the remotes' remoteEntry URLs"],
            'edge': "loads AT RUNTIME, in the user's browser",
            'remote1': ['catalog (remote)', 'exposes:', './CatalogPage'],
            'remote2': ['checkout (remote)', 'exposes:', './CheckoutPage'],
        },
    },
    'mf-load': {
        'ru': {
            'step1': ['браузер грузит shell (host):', 'свой бандл + список адресов remoteEntry'],
            'step2': ['host скачивает remoteEntry.js каталога —', 'маленький манифест контейнера, не весь бандл'],
            'step3': ['container.init(sharedScope):', 'host и remote объявляют версии react, react-dom, ...'],
            'step4': ['shared negotiation: на каждую зависимость', 'выбирается ОДИН совместимый экземпляр'],
            'step5': ['container.get("./CatalogPage") →', 'догружаются чанки модуля каталога'],
            'step6': ['CatalogPage рендерится в дереве host-а', 'тем самым, согласованным, react-ом'],
        },
        'en': {
            'step1': ['the browser loads shell (host):', 'its own bundle + the list of remoteEntry URLs'],
            'step2': ["host fetches the catalog's remoteEntry.js —", 'a small container manifest, not the whole bundle'],
            'step3': ['container.init(sharedScope):', 'host and remote declare their react, react-dom, ... versions'],
            'step4': ['shared negotiation: for every dependency', 'ONE compatible instance is chosen'],
            'step5': ['container.get("./CatalogPage") →', "the catalog module's chunks are fetched"],
            'step6': ["CatalogPage renders inside the host's tree", 'using that one negotiated react'],
        },
    },
    'serve-topology': {
        'ru': {
            'title': 'nx serve shell',
            'host': ['shell — полноценный dev-server', ':4200 · watch · HMR'],
            'edge': 'ждёт remotes на портах из конфига',
            'remote1': ['catalog :4201', 'СТАТИКА: собран', 'один раз, без watch'],
            'remote2': ['checkout :4202', 'СТАТИКА: собран', 'один раз, без watch'],
            'note': 'nx serve shell --devRemotes=catalog → catalog тоже dev-server с HMR',
        },
        'en': {
            'title': 'nx serve shell',
            'host': ['shell — a full dev server', ':4200 · watch · HMR'],
            'edge': 'expects remotes on the configured ports',
            'remote1': ['catalog :4201', 'STATIC: built once,', 'no watch'],
            'remote2': ['checkout :4202', 'STATIC: built once,', 'no watch'],
            'note': 'nx serve shell --devRemotes=catalog → catalog becomes a dev server with HMR too',
        },
    },
    'mf-errors': {
        'ru': {
            'rows': [
                ('симптом', 'типичная причина', 'первая проверка'),
                ('eager consumption error', 'нет async boundary', 'main.ts = import("./bootstrap")?'),
                ('Invalid hook call', 'два экземпляра react', 'devtools: renderers.size > 1?'),
                ('warning: unsatisfied version', 'разъехались версии shared', 'что декларирует каждый remoteEntry'),
                ('404 / CORS на remoteEntry.js', 'адрес или деплой remote', 'curl адреса из конфига/манифеста'),
                ('у remote чужой/старый UI', 'workspace-либа: first wins', 'когда деплоился каждый remote'),
            ],
        },
        'en': {
            'rows': [
                ('symptom', 'typical cause', 'first check'),
                ('eager consumption error', 'missing async boundary', 'main.ts = import("./bootstrap")?'),
                ('Invalid hook call', 'two react instances', 'devtools: renderers.size > 1?'),
                ('warning: unsatisfied version', 'shared versions drifted', 'what each remoteEntry declares'),
                ('404 / CORS on remoteEntry.js', "remote's address or deploy", 'curl the config/manifest URL'),
                ("remote shows stale/foreign UI", 'workspace lib: first wins', 'when each remote was deployed'),
            ],
        },
    },
    'contract-hub': {
        'ru': {
            'title': 'контракт как код',
            'host': ['libs/shared/api-types', 'Product · ProductsResponse', '(type:util, чистые типы)'],
            'edge': 'import type: обе стороны компилируются против ОДНОГО контракта',
            'remote1': ['apps/api (Express)', 'GET /api/products', 'GET /api/products/:id'],
            'remote2': ['catalog-data-access', 'fetch + типизация', 'запросов и ответов'],
            'note': 'в рантайме между ними обычный HTTP: типы проверил компилятор, данные — никто',
        },
        'en': {
            'title': 'the contract as code',
            'host': ['libs/shared/api-types', 'Product · ProductsResponse', '(type:util, pure types)'],
            'edge': 'import type: both sides compile against ONE contract',
            'remote1': ['apps/api (Express)', 'GET /api/products', 'GET /api/products/:id'],
            'remote2': ['catalog-data-access', 'fetch + typed', 'requests and responses'],
            'note': 'at runtime it is plain HTTP: the compiler checked the types, nobody checked the data',
        },
    },
    'ci-flow': {
        'ru': {
            'step1': ['событие: push в main / pull_request'],
            'step2': ['nrwl/nx-set-shas: NX_BASE = SHA', 'последнего УСПЕШНОГО прогона CI'],
            'step3': ['nx affected -t lint,test,typecheck,build:', 'задачи только затронутых проектов'],
            'step4': ['каждая задача: хеш → remote cache:', 'hit → replay за мс; miss → выполнить и записать'],
            'step5': ['только push в main: nx affected -t deploy —', 'независимый деплой затронутых remote-ов'],
        },
        'en': {
            'step1': ['event: push to main / pull_request'],
            'step2': ['nrwl/nx-set-shas: NX_BASE = the SHA', 'of the last SUCCESSFUL CI run'],
            'step3': ['nx affected -t lint,test,typecheck,build:', 'tasks for affected projects only'],
            'step4': ['every task: hash → remote cache:', 'hit → replay in ms; miss → run and record'],
            'step5': ['push to main only: nx affected -t deploy —', 'independent deploys of the affected remotes'],
        },
    },
    'audit-map': {
        'ru': {
            'rows': [
                ('слой', 'источник правды', 'что ищем (глава)'),
                ('версии', 'nx report', 'разъезд ядра и плагинов, возраст (00, 13)'),
                ('nx.json', 'cat nx.json', 'plugins, targetDefaults, namedInputs (01, 03, 04)'),
                ('граф', 'nx graph + graph.json', 'домены, мосты, либы-помойки (02, 05)'),
                ('targets', 'nx show project X --web', 'источник каждого target-а (01, 03, 08)'),
                ('границы', 'корневой eslint-конфиг', 'реальные depConstraints или заглушка (06)'),
                ('федерация', 'module-federation.config.*', 'host/remotes, shared, типы (09–11)'),
                ('CI', '.github/workflows и т.п.', 'affected? base? remote cache? (05, 13)'),
            ],
        },
        'en': {
            'rows': [
                ('layer', 'source of truth', 'what to look for (chapter)'),
                ('versions', 'nx report', 'core/plugin drift, age (00, 13)'),
                ('nx.json', 'cat nx.json', 'plugins, targetDefaults, namedInputs (01, 03, 04)'),
                ('graph', 'nx graph + graph.json', 'domains, bridges, dumping-ground libs (02, 05)'),
                ('targets', 'nx show project X --web', "each target's origin (01, 03, 08)"),
                ('boundaries', 'the root eslint config', 'real depConstraints or a placeholder (06)'),
                ('federation', 'module-federation.config.*', 'host/remotes, shared, types (09–11)'),
                ('CI', '.github/workflows etc.', 'affected? base? remote cache? (05, 13)'),
            ],
        },
    },
}


def main():
    args = sys.argv[1:]
    if args == ['--list'] or not args:
        for name, langs in LABELS.items():
            print(f"{name}  ({', '.join(sorted(langs))})")
        return 0
    if len(args) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 1
    name, lang = args
    if name not in DIAGRAMS or lang not in LABELS.get(name, {}):
        print(f'unknown diagram/lang: {name} {lang} (see --list)', file=sys.stderr)
        return 1
    print('\n'.join(DIAGRAMS[name](LABELS[name][lang])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
