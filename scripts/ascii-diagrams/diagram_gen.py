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


def objectid_layout(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def mongo_fit_matrix(L):
    return table(L['rows'])


def populate_mechanics(L):
    return with_title_and_notes(
        layered([L['step1'], L['step2'], L['step3']]),
        L['title'],
        L['notes'],
    )


def populate_vs_lookup(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def error_mapping(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def mongoose_layers(L):
    block = layered([L['layer1'], L['layer2'], L['layer3'], L['layer4']])
    return with_title_and_notes(block, L['title'], L['notes'])


def hook_coverage(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def replica_set(L):
    top = box(L['primary'])
    bottom = hstack([box(L['secondary1']), box(L['secondary2'])], gap=4)
    width = max(len(l) for l in bottom)
    col = width // 2

    def edge(label):
        return [' ' * col + '│' + '  ' + label, ' ' * col + '▼']

    out = [centered(L['title'], width), '']
    out += [centered(l, width) for l in box(L['client'])]
    out += edge(L['write_edge'])
    out += [centered(l, width) for l in top]
    out += edge(L['oplog_edge'])
    out.extend(bottom)
    out.append('')
    out += [centered(n, width) for n in L['notes']]
    return out


def write_concern_matrix(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def shard_routing(L):
    left = with_title_and_notes(box(L['targeted']), L['targeted_title'], L['targeted_notes'])
    right = with_title_and_notes(box(L['scatter']), L['scatter_title'], L['scatter_notes'])
    return hstack([left, right], gap=4)


def pipeline_flow(L):
    return with_title_and_notes(
        vchain([L[f'stage{i}'] for i in range(1, 6)], L['edges']),
        L['title'],
        L['notes'],
    )


def stage_order(L):
    left = with_title_and_notes(box(L['bad_lines']), L['bad_title'], L['bad_notes'])
    right = with_title_and_notes(box(L['good_lines']), L['good_title'], L['good_notes'])
    return hstack([left, right], gap=4)


def lookup_cost(L):
    return with_title_and_notes(
        layered([L['input'], L['work'], L['result']]),
        L['title'],
        L['notes'],
    )


def esr_rule(L):
    block = layered([L['query'], L['split'], L['index']])
    return with_title_and_notes(block, L['title'], L['notes'])


def explain_checklist(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def plan_shapes(L):
    blocks = [
        with_title_and_notes(box(L[f'plan{i}']), L[f'title{i}'], L[f'notes{i}'])
        for i in (1, 2, 3)
    ]
    return hstack(blocks, gap=3)


def embed_vs_ref(L):
    left = with_title_and_notes(box(L['embed_lines']), L['embed_title'], L['embed_notes'])
    right = with_title_and_notes(
        vstack([box(L['ref_parent']), box(L['ref_child'])], gap=1),
        L['ref_title'],
        L['ref_notes'],
    )
    return hstack([left, right], gap=4)


def cardinality_rule(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def pattern_catalog(L):
    return table(L['rows'])


def bucket_shape(L):
    return with_title_and_notes(
        layered([L['naive'], L['bucket']]),
        L['title'],
        L['notes'],
    )


def elemmatch_matrix(L):
    block = layered([L['doc'], L['case1'], L['case2'], L['case3']])
    return with_title_and_notes(block, L['title'], L['notes'])


def lost_update_timeline(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def schema_location(L):
    left = with_title_and_notes(box(L['mongo_lines']), L['mongo_title'], L['mongo_notes'])
    right = with_title_and_notes(box(L['sql_lines']), L['sql_title'], L['sql_notes'])
    return hstack([left, right], gap=4)


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
    'objectid-layout': objectid_layout,
    'mongo-fit-matrix': mongo_fit_matrix,
    'schema-location': schema_location,
    'elemmatch-matrix': elemmatch_matrix,
    'lost-update-timeline': lost_update_timeline,
    'embed-vs-ref': embed_vs_ref,
    'cardinality-rule': cardinality_rule,
    'pattern-catalog': pattern_catalog,
    'bucket-shape': bucket_shape,
    'esr-rule': esr_rule,
    'explain-checklist': explain_checklist,
    'plan-shapes': plan_shapes,
    'pipeline-flow': pipeline_flow,
    'stage-order': stage_order,
    'lookup-cost': lookup_cost,
    'replica-set': replica_set,
    'write-concern-matrix': write_concern_matrix,
    'shard-routing': shard_routing,
    'mongoose-layers': mongoose_layers,
    'hook-coverage': hook_coverage,
    'populate-mechanics': populate_mechanics,
    'populate-vs-lookup': populate_vs_lookup,
    'error-mapping': error_mapping,
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
    'objectid-layout': {
        'ru': {
            'title': 'ObjectId — 12 байт, а не случайный UUID',
            'rows': [
                ('байты', 'что внутри', 'практическое следствие'),
                ('0-3', 'unix-время в секундах, UTC', 'сортировка по _id ≈ по времени создания'),
                ('4-8', 'случайное значение процесса', 'два процесса не сгенерируют одинаковый id'),
                ('9-11', 'счётчик внутри процесса', 'порядок внутри одной секунды сохраняется'),
            ],
            'notes': [
                'гранулярность времени — 1 секунда: внутри секунды порядок',
                'между разными процессами не определён',
            ],
        },
        'en': {
            'title': 'ObjectId is 12 bytes, not a random UUID',
            'rows': [
                ('bytes', 'what is inside', 'practical consequence'),
                ('0-3', 'unix time in seconds, UTC', 'sorting by _id ~ sorting by creation time'),
                ('4-8', 'random per-process value', 'two processes never generate the same id'),
                ('9-11', 'per-process counter', 'order within the same second is preserved'),
            ],
            'notes': [
                'time granularity is 1 second: within one second the order',
                'across different processes is undefined',
            ],
        },
    },
    'mongo-fit-matrix': {
        'ru': {
            'rows': [
                ('сигнал в требованиях', 'скорее MongoDB', 'скорее PostgreSQL'),
                ('форма данных', 'агрегат читается целиком', 'связи и запросы по любой оси'),
                ('схема', 'поля различаются от записи к записи', 'поля известны и стабильны'),
                ('запись', 'очень много вставок, шардинг впереди', 'умеренная, важнее целостность'),
                ('транзакции', 'меняется один документ', 'меняются 3-5 таблиц сразу'),
                ('аналитика', 'заранее известные отчёты', 'произвольные JOIN и BI-запросы'),
                ('целостность', 'контролирует приложение', 'нужны FK и ON DELETE'),
            ],
        },
        'en': {
            'rows': [
                ('signal in the requirements', 'leans MongoDB', 'leans PostgreSQL'),
                ('data shape', 'one aggregate read as a whole', 'relations, queries along any axis'),
                ('schema', 'fields differ across records', 'fields are known and stable'),
                ('writes', 'very high insert rate, sharding ahead', 'moderate, integrity matters more'),
                ('transactions', 'one document changes', '3-5 tables change at once'),
                ('analytics', 'reports known upfront', 'ad-hoc JOINs and BI queries'),
                ('integrity', 'enforced by the application', 'FK and ON DELETE required'),
            ],
        },
    },
    'schema-location': {
        'ru': {
            'mongo_title': 'MongoDB: схема живёт в коде',
            'mongo_lines': [
                'коллекция posts',
                '',
                '{ title, authorId, tags }',
                '{ title, authorId }          ← нет tags',
                '{ title, author: {...} }     ← другая форма',
            ],
            'mongo_notes': [
                'БД примет всё; проверять форму обязан код',
                '(Mongoose-схема или $jsonSchema-валидатор)',
            ],
            'sql_title': 'PostgreSQL: схема живёт в БД',
            'sql_lines': [
                'таблица posts',
                '',
                'title      text   NOT NULL',
                'author_id  bigint REFERENCES users',
                'tags       text[] DEFAULT ARRAY[]',
            ],
            'sql_notes': [
                'БД отвергнет неверную форму,',
                'но изменение формы = миграция',
            ],
        },
        'en': {
            'mongo_title': 'MongoDB: the schema lives in the code',
            'mongo_lines': [
                'collection posts',
                '',
                '{ title, authorId, tags }',
                '{ title, authorId }          ← no tags',
                '{ title, author: {...} }     ← different shape',
            ],
            'mongo_notes': [
                'the DB accepts anything; the code must check',
                '(a Mongoose schema or a $jsonSchema validator)',
            ],
            'sql_title': 'PostgreSQL: the schema lives in the DB',
            'sql_lines': [
                'table posts',
                '',
                'title      text   NOT NULL',
                'author_id  bigint REFERENCES users',
                'tags       text[] DEFAULT ARRAY[]',
            ],
            'sql_notes': [
                'the DB rejects a wrong shape,',
                'but changing the shape means a migration',
            ],
        },
    },
    'elemmatch-matrix': {
        'ru': {
            'title': 'Точечная нотация по массиву проверяет условия НЕЗАВИСИМО',
            'doc': [
                'документ в коллекции posts:',
                '{ _id: 1, ratings: [ { userId: "a", score: 5 },',
                '                     { userId: "b", score: 2 } ] }',
            ],
            'case1': [
                '{ "ratings.score": { $gte: 4 } }',
                '  → МАТЧ: хотя бы один элемент имеет score >= 4',
            ],
            'case2': [
                '{ "ratings.userId": "b", "ratings.score": { $gte: 4 } }',
                '  → МАТЧ, и это ловушка: условия выполнены РАЗНЫМИ',
                '    элементами — userId вторым, score первым',
            ],
            'case3': [
                '{ ratings: { $elemMatch: { userId: "b", score: { $gte: 4 } } } }',
                '  → НЕ МАТЧ: нужен ОДИН элемент, проходящий оба условия',
                '    (именно это обычно и имеют в виду)',
            ],
            'notes': [
                'правило: два и более условия на один элемент массива — всегда $elemMatch',
            ],
        },
        'en': {
            'title': 'Dot notation on an array checks conditions INDEPENDENTLY',
            'doc': [
                'a document in the posts collection:',
                '{ _id: 1, ratings: [ { userId: "a", score: 5 },',
                '                     { userId: "b", score: 2 } ] }',
            ],
            'case1': [
                '{ "ratings.score": { $gte: 4 } }',
                '  → MATCH: at least one element has score >= 4',
            ],
            'case2': [
                '{ "ratings.userId": "b", "ratings.score": { $gte: 4 } }',
                '  → MATCH, and this is the trap: the conditions are met by',
                '    DIFFERENT elements — userId by the second, score by the first',
            ],
            'case3': [
                '{ ratings: { $elemMatch: { userId: "b", score: { $gte: 4 } } } }',
                '  → NO MATCH: ONE element must satisfy both conditions',
                '    (which is what people usually mean)',
            ],
            'notes': [
                'rule: two or more conditions on the same array element always need $elemMatch',
            ],
        },
    },
    'lost-update-timeline': {
        'ru': {
            'title': 'Lost update: read-modify-write в коде приложения',
            'rows': [
                ('шаг', 'процесс A', 'процесс B'),
                ('1', 'find: views = 100', ''),
                ('2', '', 'find: views = 100'),
                ('3', 'update: views = 101', ''),
                ('4', '', 'update: views = 101'),
            ],
            'notes': [
                'два инкремента, результат 101 вместо 102 — один потерян',
                'findOneAndUpdate({ _id }, { $inc: { views: 1 } }) — один атомарный шаг: 102',
            ],
        },
        'en': {
            'title': 'Lost update: read-modify-write in application code',
            'rows': [
                ('step', 'process A', 'process B'),
                ('1', 'find: views = 100', ''),
                ('2', '', 'find: views = 100'),
                ('3', 'update: views = 101', ''),
                ('4', '', 'update: views = 101'),
            ],
            'notes': [
                'two increments, result is 101 instead of 102 — one is lost',
                'findOneAndUpdate({ _id }, { $inc: { views: 1 } }) — one atomic step: 102',
            ],
        },
    },
    'embed-vs-ref': {
        'ru': {
            'embed_title': 'EMBEDDING: комментарии внутри поста',
            'embed_lines': [
                'коллекция posts',
                '',
                '{ _id: 1,',
                '  title: "Индексы",',
                '  comments: [',
                '    { _id: 11, body: "..." },',
                '    { _id: 12, body: "..." } ] }',
            ],
            'embed_notes': [
                'одно чтение отдаёт всю страницу;',
                'одна запись меняет пост и комментарий',
                'атомарно; но массив растёт без границы',
            ],
            'ref_title': 'REFERENCING: две коллекции',
            'ref_parent': [
                'коллекция posts',
                '',
                '{ _id: 1, title: "Индексы" }',
            ],
            'ref_child': [
                'коллекция comments',
                '',
                '{ _id: 11, postId: 1, body: "..." }',
                '{ _id: 12, postId: 1, body: "..." }',
            ],
            'ref_notes': [
                'рост не ограничен документом,',
                'комментарии живут своей жизнью;',
                'но два запроса и нет атомарности',
            ],
        },
        'en': {
            'embed_title': 'EMBEDDING: comments inside the post',
            'embed_lines': [
                'collection posts',
                '',
                '{ _id: 1,',
                '  title: "Indexes",',
                '  comments: [',
                '    { _id: 11, body: "..." },',
                '    { _id: 12, body: "..." } ] }',
            ],
            'embed_notes': [
                'one read returns the whole page;',
                'one write changes post and comment',
                'atomically; but the array grows unbounded',
            ],
            'ref_title': 'REFERENCING: two collections',
            'ref_parent': [
                'collection posts',
                '',
                '{ _id: 1, title: "Indexes" }',
            ],
            'ref_child': [
                'collection comments',
                '',
                '{ _id: 11, postId: 1, body: "..." }',
                '{ _id: 12, postId: 1, body: "..." }',
            ],
            'ref_notes': [
                'growth is not bound by the document,',
                'comments have their own lifecycle;',
                'but two queries and no atomicity',
            ],
        },
    },
    'cardinality-rule': {
        'ru': {
            'title': 'Кардинальность — первый фильтр решения',
            'rows': [
                ('связь', 'пример в блоге', 'решение'),
                ('one-to-few', 'у поста 3-10 тегов', 'вкладывать массивом'),
                ('one-to-few', 'у пользователя 2 адреса', 'вкладывать массивом'),
                ('one-to-many', 'у поста 50-500 комментариев', 'ссылка + Subset в посте'),
                ('one-to-squillions', 'у поста миллионы просмотров', 'ссылка из дочернего, Bucket'),
                ('many-to-many', 'посты и теги как сущности', 'массив id на «главной» стороне'),
            ],
            'notes': [
                'граница few/many — не число, а ответ на вопрос:',
                'может ли пользователь наращивать это без предела?',
            ],
        },
        'en': {
            'title': 'Cardinality is the first filter on the decision',
            'rows': [
                ('relationship', 'example in a blog', 'decision'),
                ('one-to-few', 'a post has 3-10 tags', 'embed as an array'),
                ('one-to-few', 'a user has 2 addresses', 'embed as an array'),
                ('one-to-many', 'a post has 50-500 comments', 'reference + Subset in post'),
                ('one-to-squillions', 'a post has millions of views', 'reference from child, Bucket'),
                ('many-to-many', 'posts and tags as entities', 'array of ids on the "main" side'),
            ],
            'notes': [
                'the few/many boundary is not a number but an answer to:',
                'can a user grow this without any limit?',
            ],
        },
    },
    'pattern-catalog': {
        'ru': {
            'rows': [
                ('паттерн', 'какую боль лечит', 'цена'),
                ('Extended Reference', 'лишний запрос за именем автора', 'дубли надо обновлять'),
                ('Subset', 'документ раздут, а нужно 3 записи', 'две записи вместо одной'),
                ('Bucket', 'миллионы крошечных документов', 'сложнее точечные правки'),
                ('Computed', 'агрегат считается на каждом чтении', 'значение может разъехаться'),
            ],
        },
        'en': {
            'rows': [
                ('pattern', 'the pain it treats', 'the cost'),
                ('Extended Reference', 'an extra query for the author name', 'duplicates need updating'),
                ('Subset', 'a bloated document when 3 rows suffice', 'two writes instead of one'),
                ('Bucket', 'millions of tiny documents', 'point edits get harder'),
                ('Computed', 'an aggregate recomputed on every read', 'the value can drift'),
            ],
        },
    },
    'bucket-shape': {
        'ru': {
            'title': 'Bucket: документ на корзину, а не на событие',
            'naive': [
                'наивно — документ на каждый просмотр:',
                '{ postId: 1, at: ISODate("...T10:00:03Z") }',
                '{ postId: 1, at: ISODate("...T10:00:07Z") }',
                '  → 10M документов в сутки, 10M записей в индексе',
            ],
            'bucket': [
                'Bucket — документ на (postId, час):',
                '{ postId: 1, hour: ISODate("...T10:00Z"),',
                '  count: 8421, uniqueUsers: 3190 }',
                '  → 24 документа в сутки на пост, upsert + $inc',
            ],
            'notes': [
                'отчёт за неделю: 168 документов вместо 70 миллионов',
            ],
        },
        'en': {
            'title': 'Bucket: one document per bucket, not per event',
            'naive': [
                'naive — one document per view:',
                '{ postId: 1, at: ISODate("...T10:00:03Z") }',
                '{ postId: 1, at: ISODate("...T10:00:07Z") }',
                '  → 10M documents a day, 10M index entries',
            ],
            'bucket': [
                'Bucket — one document per (postId, hour):',
                '{ postId: 1, hour: ISODate("...T10:00Z"),',
                '  count: 8421, uniqueUsers: 3190 }',
                '  → 24 documents a day per post, upsert + $inc',
            ],
            'notes': [
                'a weekly report reads 168 documents instead of 70 million',
            ],
        },
    },
    'esr-rule': {
        'ru': {
            'title': 'ESR: как разложить запрос в порядок полей индекса',
            'query': [
                'запрос:',
                'db.posts.find({ status: "published",',
                '                "author._id": authorId,',
                '                publishedAt: { $gte: monthAgo } })',
                '        .sort({ views: -1 })',
            ],
            'split': [
                'E (equality)  status, author._id   — точные значения',
                'S (sort)      views: -1            — порядок выдачи',
                'R (range)     publishedAt: $gte    — диапазон',
            ],
            'index': [
                'индекс:',
                '{ status: 1, "author._id": 1, views: -1, publishedAt: 1 }',
                '  → IXSCAN без стадии SORT и без лишних FETCH',
            ],
            'notes': [
                'поменять S и R местами — и появится SORT в памяти на всей выборке',
            ],
        },
        'en': {
            'title': 'ESR: how to turn a query into index field order',
            'query': [
                'query:',
                'db.posts.find({ status: "published",',
                '                "author._id": authorId,',
                '                publishedAt: { $gte: monthAgo } })',
                '        .sort({ views: -1 })',
            ],
            'split': [
                'E (equality)  status, author._id   — exact values',
                'S (sort)      views: -1            — output order',
                'R (range)     publishedAt: $gte    — a range',
            ],
            'index': [
                'index:',
                '{ status: 1, "author._id": 1, views: -1, publishedAt: 1 }',
                '  → IXSCAN with no SORT stage and no extra FETCH',
            ],
            'notes': [
                'swap S and R and you get an in-memory SORT over the whole result',
            ],
        },
    },
    'explain-checklist': {
        'ru': {
            'title': 'Чтение executionStats: признак → диагноз → что делать',
            'rows': [
                ('что видно', 'что это значит', 'что делать'),
                ('stage: COLLSCAN', 'индекс не используется', 'создать индекс по ESR'),
                ('stage: SORT', 'сортировка в памяти', 'добавить sort-поле в индекс'),
                ('docsExamined >> nReturned', 'индекс плохо селективен', 'уточнить порядок полей'),
                ('keysExamined >> nReturned', 'скан широкого диапазона', 'вынести equality вперёд'),
                ('docsExamined = 0', 'covered query', 'ничего, это цель'),
                ('rejectedPlans пусто', 'план один', 'проверить, что он ожидаемый'),
            ],
            'notes': [
                'ориентир здорового запроса: nReturned ≈ docsExamined ≈ keysExamined',
            ],
        },
        'en': {
            'title': 'Reading executionStats: symptom → diagnosis → action',
            'rows': [
                ('what you see', 'what it means', 'what to do'),
                ('stage: COLLSCAN', 'no index is used', 'create an index per ESR'),
                ('stage: SORT', 'sorting in memory', 'add the sort field to the index'),
                ('docsExamined >> nReturned', 'index is not selective', 'revisit the field order'),
                ('keysExamined >> nReturned', 'a wide range is scanned', 'move equality fields first'),
                ('docsExamined = 0', 'a covered query', 'nothing — this is the goal'),
                ('rejectedPlans is empty', 'only one plan existed', 'check it is the expected one'),
            ],
            'notes': [
                'a healthy query looks like: nReturned ≈ docsExamined ≈ keysExamined',
            ],
        },
    },
    'plan-shapes': {
        'ru': {
            'title1': 'без индекса',
            'plan1': [
                'COLLSCAN',
                '  ↓',
                'SORT',
                '  ↓',
                'LIMIT',
            ],
            'notes1': [
                'читает все документы,',
                'сортирует в памяти',
            ],
            'title2': 'индекс + документы',
            'plan2': [
                'IXSCAN',
                '  ↓',
                'FETCH',
                '  ↓',
                'LIMIT',
            ],
            'notes2': [
                'по индексу находит ключи,',
                'потом читает документы',
            ],
            'title3': 'covered query',
            'plan3': [
                'IXSCAN',
                '  ↓',
                'PROJECTION_COVERED',
                '  ↓',
                'LIMIT',
            ],
            'notes3': [
                'документы не читаются',
                'вообще: docsExamined = 0',
            ],
        },
        'en': {
            'title1': 'no index',
            'plan1': [
                'COLLSCAN',
                '  ↓',
                'SORT',
                '  ↓',
                'LIMIT',
            ],
            'notes1': [
                'reads every document,',
                'sorts in memory',
            ],
            'title2': 'index + documents',
            'plan2': [
                'IXSCAN',
                '  ↓',
                'FETCH',
                '  ↓',
                'LIMIT',
            ],
            'notes2': [
                'finds keys in the index,',
                'then reads the documents',
            ],
            'title3': 'covered query',
            'plan3': [
                'IXSCAN',
                '  ↓',
                'PROJECTION_COVERED',
                '  ↓',
                'LIMIT',
            ],
            'notes3': [
                'documents are never read:',
                'docsExamined = 0',
            ],
        },
    },
    'pipeline-flow': {
        'ru': {
            'title': 'Пайплайн: каждая стадия получает поток и отдаёт поток',
            'stage1': ['коллекция comments', '2 000 000 документов'],
            'stage2': ['$match: { createdAt: { $gte: monthAgo } }', 'использует индекс — стадия первая'],
            'stage3': ['$group: по author._id', 'сумма и количество на автора'],
            'stage4': ['$sort: { total: -1 }  +  $limit: 10', 'top-k: сортируются только группы'],
            'stage5': ['курсор с результатом', '10 документов'],
            'edges': ['180 000', '4 200', '4 200', '10'],
            'notes': [
                'числа на стрелках — сколько документов уходит в следующую стадию',
            ],
        },
        'en': {
            'title': 'A pipeline: every stage takes a stream and emits a stream',
            'stage1': ['collection comments', '2,000,000 documents'],
            'stage2': ['$match: { createdAt: { $gte: monthAgo } }', 'uses an index — it is the first stage'],
            'stage3': ['$group: by author._id', 'sum and count per author'],
            'stage4': ['$sort: { total: -1 }  +  $limit: 10', 'top-k: only the groups are sorted'],
            'stage5': ['a cursor with the result', '10 documents'],
            'edges': ['180,000', '4,200', '4,200', '10'],
            'notes': [
                'the numbers on the arrows are documents passed to the next stage',
            ],
        },
    },
    'stage-order': {
        'ru': {
            'bad_title': 'ПЛОХО: фильтр после разворота',
            'bad_lines': [
                '$unwind: "$tags"',
                '$lookup: from: "users"',
                '$match: { status: "published" }',
                '$sort:  { publishedAt: -1 }',
            ],
            'bad_notes': [
                'индекс не используется: перед $match',
                'уже прошли стадии, меняющие форму;',
                '$lookup выполнен для черновиков тоже',
            ],
            'good_title': 'ХОРОШО: фильтр и сортировка первыми',
            'good_lines': [
                '$match: { status: "published" }',
                '$sort:  { publishedAt: -1 }',
                '$limit: 20',
                '$lookup: from: "users"',
                '$unwind: "$tags"',
            ],
            'good_notes': [
                '$match + $sort берут индекс',
                '{ status: 1, publishedAt: -1 };',
                '$lookup работает по 20 документам',
            ],
        },
        'en': {
            'bad_title': 'BAD: filtering after unwinding',
            'bad_lines': [
                '$unwind: "$tags"',
                '$lookup: from: "users"',
                '$match: { status: "published" }',
                '$sort:  { publishedAt: -1 }',
            ],
            'bad_notes': [
                'no index is used: stages that reshape',
                'documents already ran before $match;',
                '$lookup also ran for the drafts',
            ],
            'good_title': 'GOOD: filter and sort first',
            'good_lines': [
                '$match: { status: "published" }',
                '$sort:  { publishedAt: -1 }',
                '$limit: 20',
                '$lookup: from: "users"',
                '$unwind: "$tags"',
            ],
            'good_notes': [
                '$match + $sort use the index',
                '{ status: 1, publishedAt: -1 };',
                '$lookup runs over 20 documents',
            ],
        },
    },
    'lookup-cost': {
        'ru': {
            'title': '$lookup — вложенный цикл, а не hash join',
            'input': [
                'на входе стадии: 500 постов',
            ],
            'work': [
                'для КАЖДОГО поста выполняется поиск в users:',
                '  { _id: <authorId поста> }',
                '  → 500 отдельных обращений к коллекции users',
                '  → с индексом по _id это 500 быстрых IXSCAN',
                '  → без индекса по foreignField — 500 COLLSCAN',
            ],
            'result': [
                'на выходе: те же 500 постов + поле author: [ ... ]',
            ],
            'notes': [
                'планировщик не выбирает порядок соединения и не строит хеш-таблицу',
                'Extended Reference в схеме убирает эту стадию целиком',
            ],
        },
        'en': {
            'title': '$lookup is a nested loop, not a hash join',
            'input': [
                'stage input: 500 posts',
            ],
            'work': [
                'for EVERY post a lookup runs against users:',
                '  { _id: <the post authorId> }',
                '  → 500 separate accesses to the users collection',
                '  → with an index on _id these are 500 fast IXSCANs',
                '  → without an index on foreignField — 500 COLLSCANs',
            ],
            'result': [
                'stage output: the same 500 posts + author: [ ... ]',
            ],
            'notes': [
                'the planner picks no join order and builds no hash table',
                'an Extended Reference in the schema removes this stage entirely',
            ],
        },
    },
    'replica-set': {
        'ru': {
            'title': 'Реплика-сет: одна точка записи, несколько копий данных',
            'client': ['приложение (драйвер знает всех членов сета)'],
            'write_edge': 'все записи — только на primary',
            'primary': [
                'PRIMARY',
                'применяет запись и пишет её в oplog',
                '(local.oplog.rs — capped-коллекция)',
            ],
            'oplog_edge': 'secondaries тянут oplog и применяют операции',
            'secondary1': [
                'SECONDARY',
                'копия данных,',
                'может отставать',
            ],
            'secondary2': [
                'SECONDARY',
                'кандидат в primary',
                'при выборах',
            ],
            'notes': [
                'primary недоступен → выборы (несколько секунд) → новый primary из большинства',
                'размер oplog задаёт окно, за которое отставший узел ещё может догнать',
            ],
        },
        'en': {
            'title': 'A replica set: one write point, several copies of the data',
            'client': ['the application (the driver knows every member)'],
            'write_edge': 'every write goes to the primary only',
            'primary': [
                'PRIMARY',
                'applies the write and records it in the oplog',
                '(local.oplog.rs — a capped collection)',
            ],
            'oplog_edge': 'secondaries tail the oplog and apply the operations',
            'secondary1': [
                'SECONDARY',
                'a copy of the data,',
                'may lag behind',
            ],
            'secondary2': [
                'SECONDARY',
                'a candidate for primary',
                'during an election',
            ],
            'notes': [
                'primary unavailable → an election (a few seconds) → a new primary from the majority',
                'the oplog size sets the window in which a lagging member can still catch up',
            ],
        },
    },
    'write-concern-matrix': {
        'ru': {
            'title': 'Что на самом деле значит «запись подтверждена»',
            'rows': [
                ('настройка', 'подтверждение получено, когда', 'чем рискуете'),
                ('w: 0', 'драйвер отправил пакет', 'запись могла не примениться'),
                ('w: 1', 'применил primary', 'откат при failover'),
                ('w: 1, j: true', 'primary записал в журнал', 'откат при failover'),
                ('w: "majority"', 'применило большинство узлов', 'выше задержка'),
                ('w: "majority", j: true', 'большинство записало в журнал', 'самая высокая задержка'),
            ],
            'notes': [
                'начиная с MongoDB 5.0 значение по умолчанию — w: "majority"',
                'wtimeout ограничивает ожидание, но НЕ отменяет уже применённую запись',
            ],
        },
        'en': {
            'title': 'What "the write was acknowledged" actually means',
            'rows': [
                ('setting', 'acknowledged once', 'the risk you take'),
                ('w: 0', 'the driver sent the packet', 'the write may never apply'),
                ('w: 1', 'the primary applied it', 'rollback on failover'),
                ('w: 1, j: true', 'the primary journaled it', 'rollback on failover'),
                ('w: "majority"', 'a majority of members applied it', 'higher latency'),
                ('w: "majority", j: true', 'a majority journaled it', 'the highest latency'),
            ],
            'notes': [
                'since MongoDB 5.0 the default is w: "majority"',
                'wtimeout bounds the wait but does NOT undo an already applied write',
            ],
        },
    },
    'shard-routing': {
        'ru': {
            'targeted_title': 'TARGETED: фильтр содержит shard key',
            'targeted': [
                'find({ tenantId: "acme", _id: x })',
                '',
                'mongos → шард 2',
                '',
                'шард 1  ·  [шард 2]  ·  шард 3',
            ],
            'targeted_notes': [
                'запрос уходит на ОДИН шард;',
                'масштабируется линейно с их числом',
            ],
            'scatter_title': 'SCATTER-GATHER: shard key отсутствует',
            'scatter': [
                'find({ status: "published" })',
                '',
                'mongos → все шарды → слияние',
                '',
                '[шард 1] · [шард 2] · [шард 3]',
            ],
            'scatter_notes': [
                'каждый шард выполняет запрос,',
                'mongos сливает; сортировка — тоже на нём',
            ],
        },
        'en': {
            'targeted_title': 'TARGETED: the filter contains the shard key',
            'targeted': [
                'find({ tenantId: "acme", _id: x })',
                '',
                'mongos → shard 2',
                '',
                'shard 1  ·  [shard 2]  ·  shard 3',
            ],
            'targeted_notes': [
                'the query goes to ONE shard;',
                'scales linearly with their number',
            ],
            'scatter_title': 'SCATTER-GATHER: no shard key in the filter',
            'scatter': [
                'find({ status: "published" })',
                '',
                'mongos → every shard → merge',
                '',
                '[shard 1] · [shard 2] · [shard 3]',
            ],
            'scatter_notes': [
                'every shard runs the query and',
                'mongos merges; the sort happens there too',
            ],
        },
    },
    'mongoose-layers': {
        'ru': {
            'title': 'Что именно добавляет Mongoose между кодом и сервером',
            'layer1': [
                'код приложения: сервисы, контроллеры',
            ],
            'layer2': [
                'Mongoose: Schema · каст типов · валидация · хуки',
                'virtuals · methods/statics · populate · query builder',
                'гидрация результата в Document-обёртки',
            ],
            'layer3': [
                'официальный Node.js driver: BSON, пул соединений,',
                'мониторинг топологии, retryable writes, сессии',
            ],
            'layer4': [
                'mongod / mongos: индексы, план запроса, репликация',
            ],
            'notes': [
                'каждая строка слоя Mongoose — это удобство, у которого есть цена в поведении',
            ],
        },
        'en': {
            'title': 'What exactly Mongoose adds between your code and the server',
            'layer1': [
                'application code: services, controllers',
            ],
            'layer2': [
                'Mongoose: Schema · type casting · validation · hooks',
                'virtuals · methods/statics · populate · query builder',
                'hydration of results into Document wrappers',
            ],
            'layer3': [
                'the official Node.js driver: BSON, connection pool,',
                'topology monitoring, retryable writes, sessions',
            ],
            'layer4': [
                'mongod / mongos: indexes, query plan, replication',
            ],
            'notes': [
                'every line of the Mongoose layer is a convenience with a behavioural cost',
            ],
        },
    },
    'hook-coverage': {
        'ru': {
            'title': 'Какие операции проходят через валидацию и хуки',
            'rows': [
                ('операция', 'валидация', 'pre/post save', 'query-хуки'),
                ('doc.save()', 'да', 'да', 'нет'),
                ('Model.create()', 'да', 'да', 'нет'),
                ('Model.insertMany()', 'да', 'нет', 'нет'),
                ('findOneAndUpdate()', 'только с runValidators', 'НЕТ', 'да'),
                ('updateOne() / updateMany()', 'только с runValidators', 'НЕТ', 'да'),
                ('bulkWrite()', 'нет', 'нет', 'нет'),
            ],
            'notes': [
                'отсюда баг с хешированием пароля: pre(\'save\') не увидит findOneAndUpdate',
            ],
        },
        'en': {
            'title': 'Which operations go through validation and hooks',
            'rows': [
                ('operation', 'validation', 'pre/post save', 'query hooks'),
                ('doc.save()', 'yes', 'yes', 'no'),
                ('Model.create()', 'yes', 'yes', 'no'),
                ('Model.insertMany()', 'yes', 'no', 'no'),
                ('findOneAndUpdate()', 'only with runValidators', 'NO', 'yes'),
                ('updateOne() / updateMany()', 'only with runValidators', 'NO', 'yes'),
                ('bulkWrite()', 'no', 'no', 'no'),
            ],
            'notes': [
                'hence the password hashing bug: pre(\'save\') never sees findOneAndUpdate',
            ],
        },
    },
    'populate-mechanics': {
        'ru': {
            'title': 'populate — это отдельные запросы, а не $lookup на сервере',
            'step1': [
                'PostModel.find().limit(20).populate("author._id")',
                '  запрос 1: db.posts.find(...).limit(20)',
            ],
            'step2': [
                'Mongoose собирает все authorId из 20 документов',
                '  запрос 2: db.users.find({ _id: { $in: [ ...20 id... ] } })',
            ],
            'step3': [
                'склейка в памяти процесса Node:',
                '  post.author._id = соответствующий документ user',
            ],
            'notes': [
                '20 постов = 2 запроса, а не 21 — но это всё равно два round-trip',
                'вложенный populate добавляет ещё один запрос на КАЖДЫЙ уровень',
            ],
        },
        'en': {
            'title': 'populate is separate queries, not a server-side $lookup',
            'step1': [
                'PostModel.find().limit(20).populate("author._id")',
                '  query 1: db.posts.find(...).limit(20)',
            ],
            'step2': [
                'Mongoose collects every authorId from the 20 documents',
                '  query 2: db.users.find({ _id: { $in: [ ...20 ids... ] } })',
            ],
            'step3': [
                'stitching in the Node process memory:',
                '  post.author._id = the matching user document',
            ],
            'notes': [
                '20 posts = 2 queries, not 21 — but still two round-trips',
                'a nested populate adds one more query per LEVEL',
            ],
        },
    },
    'populate-vs-lookup': {
        'ru': {
            'title': 'Три способа получить связанные данные',
            'rows': [
                ('', 'populate', '$lookup', 'пересмотр схемы'),
                ('где выполняется', 'Node + N запросов', 'на сервере', 'нигде: данные уже в документе'),
                ('round-trips', '2 и больше', '1', '1'),
                ('фильтр по связанным', 'match, но родитель остаётся', 'полноценно в пайплайне', 'обычный find'),
                ('цена', 'сеть и память Node', 'вложенный цикл', 'дубли надо синхронизировать'),
                ('когда уместно', 'админки, редкие экраны', 'отчёты и агрегации', 'горячий путь чтения'),
            ],
            'notes': [
                'если populate стоит в самом частом запросе — вопрос не к populate, а к схеме',
            ],
        },
        'en': {
            'title': 'Three ways to get related data',
            'rows': [
                ('', 'populate', '$lookup', 'redesign the schema'),
                ('where it runs', 'Node + N queries', 'on the server', 'nowhere: already in the document'),
                ('round-trips', '2 or more', '1', '1'),
                ('filter on related', 'match, parent still returned', 'fully, inside the pipeline', 'a plain find'),
                ('cost', 'network and Node memory', 'a nested loop', 'duplicates need syncing'),
                ('when it fits', 'admin panels, rare screens', 'reports and aggregations', 'the hot read path'),
            ],
            'notes': [
                'if populate sits in your most frequent query, the problem is the schema, not populate',
            ],
        },
    },
    'error-mapping': {
        'ru': {
            'title': 'Ошибки Mongoose/драйвера → ответ API',
            'rows': [
                ('ошибка', 'причина', 'ответ'),
                ('ValidationError', 'схема отвергла значения', '400 + список полей'),
                ('CastError', 'невалидный вход: битый ObjectId', '400'),
                ('E11000 (code 11000)', 'нарушен уникальный индекс', '409 + имя поля'),
                ('VersionError', 'документ изменён параллельно', '409, предложить перечитать'),
                ('buffering timed out', 'нет соединения с базой', '503'),
                ('MongoServerSelectionError', 'кластер недоступен', '503'),
            ],
            'notes': [
                'без такого маппинга всё это превращается в 500 и в бесполезный алерт',
            ],
        },
        'en': {
            'title': 'Mongoose/driver errors → the API response',
            'rows': [
                ('error', 'cause', 'response'),
                ('ValidationError', 'the schema rejected the values', '400 + field list'),
                ('CastError', 'invalid input: a malformed ObjectId', '400'),
                ('E11000 (code 11000)', 'a unique index was violated', '409 + field name'),
                ('VersionError', 'the document changed concurrently', '409, ask for a refetch'),
                ('buffering timed out', 'no connection to the database', '503'),
                ('MongoServerSelectionError', 'the cluster is unreachable', '503'),
            ],
            'notes': [
                'without this mapping all of it becomes a 500 and a useless alert',
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
