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


def flow_box(steps, arrow='↓'):
    """A box of steps separated by a centered arrow (a vertical flow)."""
    width = max(len(l) for s in steps for l in s)
    lines = []
    for i, s in enumerate(steps):
        if i:
            lines.append(centered(arrow, width))
        lines.extend(s)
    return box(lines)


def two_col_box(spec):
    """A titled box whose body is a name/value table, padded programmatically."""
    pad = max(len(name) for name, _ in spec['rows'])
    lines = [spec['head'], '']
    lines += [f'{name.ljust(pad)}   {value}' for name, value in spec['rows']]
    return with_title_and_notes(box(lines), spec['title'], spec['notes'])


def stack_compare(L):
    return hstack([two_col_box(L['left']), two_col_box(L['right'])], gap=4)


def binding_syntax(L):
    return table(L['rows'])


def _centers(blocks, gap, offset=0):
    """Column of the horizontal centre of each block inside an hstack."""
    pos, out = offset, []
    for b in blocks:
        w = max(len(l) for l in b)
        out.append(pos + w // 2)
        pos += w + gap
    return out


def _marks(centers, width, ch='▼'):
    row = [' '] * width
    for c in centers:
        row[c] = ch
    return ''.join(row).rstrip()


def signal_graph(L):
    """sources → one derived signal → consumers, arrows placed programmatically."""
    gap = 4
    sources = [box([s]) for s in L['sources']]
    consumers = [box([c]) for c in L['consumers']]
    top, bottom = hstack(sources, gap=gap), hstack(consumers, gap=gap)
    natural = box(L['derived'])
    width = max(len(l) for block in (top, bottom, natural) for l in block)
    mid = box(L['derived'], min_width=width - 4)

    def pad(block):
        off = (width - max(len(l) for l in block)) // 2
        return off, [' ' * off + l for l in block]

    top_off, top_lines = pad(top)
    bottom_off, bottom_lines = pad(bottom)
    return [
        *top_lines,
        _marks(_centers(sources, gap, top_off), width),
        *mid,
        _marks(_centers(consumers, gap, bottom_off), width),
        *bottom_lines,
    ]


def annotated_tree(L):
    """A component tree with a programmatically padded annotation column."""
    pad = max(len(branch) for branch, _ in L['rows'])
    return [f'{branch.ljust(pad)}   {note}'.rstrip() for branch, note in L['rows']]


def cd_triggers(L):
    return table(L['rows'])


def injector_hierarchy(L):
    block = vchain([step['lines'] for step in L['steps']], [s.get('edge', '') for s in L['steps'][1:]])
    return with_title_and_notes(block, L['title'], L['notes'])


def provider_recipes(L):
    return table(L['rows'])


def store_anatomy(L):
    block = layered([L['layer1'], L['layer2'], L['layer3'], L['layer4']])
    return with_title_and_notes(block, L['title'], L['notes'])


def state_ladder(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def state_mapping(L):
    return table(L['rows'])


def structural_desugar(L):
    block = vchain([step['lines'] for step in L['steps']], [s.get('edge', '') for s in L['steps'][1:]])
    return with_title_and_notes(block, L['title'], L['notes'])


def tool_choice(L):
    return table(L['rows'])


def navigation_flow(L):
    block = vchain([step['lines'] for step in L['steps']], [s.get('edge', '') for s in L['steps'][1:]])
    return with_title_and_notes(block, L['title'], L['notes'])


def guard_matrix(L):
    return table(L['rows'])


def interceptor_chain(L):
    block = vchain([step['lines'] for step in L['steps']], [s.get('edge', '') for s in L['steps'][1:]])
    return with_title_and_notes(block, L['title'], L['notes'])


def error_handling_map(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def rxjs_map(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def interop_bridge(L):
    left = with_title_and_notes(box(L['to_signal']), L['to_signal_title'], L['to_signal_notes'])
    right = with_title_and_notes(box(L['to_observable']), L['to_observable_title'], L['to_observable_notes'])
    return hstack([left, right], gap=4)


def flattening_operators(L):
    return table(L['rows'])


def control_states(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def projection_options(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def defer_triggers(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def test_pyramid(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def render_modes(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def security_layers(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def senior_polish(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def feature_layout(L):
    pad = max(len(branch) for branch, _ in L['rows'])
    lines = [f'{branch.ljust(pad)}   {note}'.rstrip() for branch, note in L['rows']]
    width = max(len(l) for l in lines)
    return [centered(L['title'], width), *lines]


def shared_problems(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def reading_checklist(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def testbed_flow(L):
    block = vchain([step['lines'] for step in L['steps']], [s.get('edge', '') for s in L['steps'][1:]])
    return with_title_and_notes(block, L['title'], L['notes'])


def testing_comparison(L):
    return table(L['rows'])


def perf_checklist(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def budget_types(L):
    return table(L['rows'])


def slot_matching(L):
    left = with_title_and_notes(box(L['consumer']), L['consumer_title'], L['consumer_notes'])
    right = with_title_and_notes(box(L['component']), L['component_title'], L['component_notes'])
    return hstack([left, right], gap=4)


def cdk_primitives(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def forms_comparison(L):
    return table(L['rows'])


def value_writes(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def fetch_options(L):
    return table(L['rows'])


def route_state(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def pipe_cost(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def inject_modifiers(L):
    return table(L['rows'])


def cd_diagnosis(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def reactive_tools(L):
    return table(L['rows'])


def signal_io(L):
    return table(L['rows'])


def template_compile(L):
    return vchain([L['step1'], L['step2'], L['step3'], L['step4']])


def encapsulation_modes(L):
    return with_title_and_notes(table(L['rows']), L['title'], L['notes'])


def update_models(L):
    left = with_title_and_notes(
        flow_box(L['react_steps']), L['react_title'], L['react_notes']
    )
    right = with_title_and_notes(flow_box(L['ng_steps']), L['ng_title'], L['ng_notes'])
    return hstack([left, right], gap=4)


DIAGRAMS = {
    'stack-compare': stack_compare,
    'update-models': update_models,
    'binding-syntax': binding_syntax,
    'template-compile': template_compile,
    'encapsulation-modes': encapsulation_modes,
    'signal-graph': signal_graph,
    'reactive-tools': reactive_tools,
    'signal-io': signal_io,
    'cd-traversal': annotated_tree,
    'cd-triggers': cd_triggers,
    'cd-diagnosis': cd_diagnosis,
    'injector-hierarchy': injector_hierarchy,
    'provider-recipes': provider_recipes,
    'inject-modifiers': inject_modifiers,
    'store-anatomy': store_anatomy,
    'state-ladder': state_ladder,
    'state-mapping': state_mapping,
    'structural-desugar': structural_desugar,
    'tool-choice': tool_choice,
    'pipe-cost': pipe_cost,
    'navigation-flow': navigation_flow,
    'guard-matrix': guard_matrix,
    'route-state': route_state,
    'interceptor-chain': interceptor_chain,
    'error-handling-map': error_handling_map,
    'fetch-options': fetch_options,
    'rxjs-map': rxjs_map,
    'interop-bridge': interop_bridge,
    'flattening-operators': flattening_operators,
    'control-states': control_states,
    'forms-comparison': forms_comparison,
    'value-writes': value_writes,
    'projection-options': projection_options,
    'slot-matching': slot_matching,
    'cdk-primitives': cdk_primitives,
    'defer-triggers': defer_triggers,
    'perf-checklist': perf_checklist,
    'budget-types': budget_types,
    'test-pyramid': test_pyramid,
    'testbed-flow': testbed_flow,
    'testing-comparison': testing_comparison,
    'feature-layout': feature_layout,
    'shared-problems': shared_problems,
    'reading-checklist': reading_checklist,
    'render-modes': render_modes,
    'security-layers': security_layers,
    'senior-polish': senior_polish,
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
    'stack-compare': {
        'ru': {
            'left': {
                'title': 'REACT: библиотека + собранный стек',
                'head': 'react + react-dom',
                'rows': [
                    ('роутинг', 'react-router'),
                    ('данные', 'TanStack Query'),
                    ('формы', 'react-hook-form'),
                    ('DI', 'Context + пропсы'),
                    ('тесты', 'Vitest + RTL'),
                    ('сборка', 'Vite / Next.js'),
                ],
                'notes': [
                    'каждая строка — свой выбор, свой',
                    'мажор и свой релизный цикл',
                ],
            },
            'right': {
                'title': 'ANGULAR: одна поставка',
                'head': '@angular/core',
                'rows': [
                    ('роутинг', '@angular/router'),
                    ('данные', 'HttpClient, httpResource'),
                    ('формы', '@angular/forms'),
                    ('DI', 'инжектор в ядре'),
                    ('тесты', 'TestBed (+ Vitest)'),
                    ('сборка', 'Angular CLI, @angular/build'),
                ],
                'notes': [
                    'один мажор на всё, одна команда',
                    'ng update, меньше решений на входе',
                ],
            },
        },
        'en': {
            'left': {
                'title': 'REACT: a library plus a stack you assemble',
                'head': 'react + react-dom',
                'rows': [
                    ('routing', 'react-router'),
                    ('data', 'TanStack Query'),
                    ('forms', 'react-hook-form'),
                    ('DI', 'Context + props'),
                    ('tests', 'Vitest + RTL'),
                    ('build', 'Vite / Next.js'),
                ],
                'notes': [
                    'every line is a separate choice with',
                    'its own major and release cycle',
                ],
            },
            'right': {
                'title': 'ANGULAR: one shipped package',
                'head': '@angular/core',
                'rows': [
                    ('routing', '@angular/router'),
                    ('data', 'HttpClient, httpResource'),
                    ('forms', '@angular/forms'),
                    ('DI', 'injector in the core'),
                    ('tests', 'TestBed (+ Vitest)'),
                    ('build', 'Angular CLI, @angular/build'),
                ],
                'notes': [
                    'one major for everything, one',
                    'ng update, fewer upfront decisions',
                ],
            },
        },
    },
    'update-models': {
        'ru': {
            'react_title': 'REACT: функция от состояния',
            'react_steps': [
                ['setState(next)'],
                [
                    'функция компонента вызывается',
                    'заново — новые замыкания,',
                    'новые пропсы для детей',
                ],
                [
                    'React обходит поддерево;',
                    'дети тоже рендерятся заново,',
                    'если их не остановил memo',
                ],
            ],
            'react_notes': [
                'состояние живёт снаружи, в хуках;',
                'тело функции — это и есть "рендер"',
            ],
            'ng_title': 'ANGULAR: долгоживущий инстанс',
            'ng_steps': [
                ['count.set(next)'],
                [
                    'сигнал помечает зависимые',
                    'шаблоны грязными и планирует',
                    'проверку',
                ],
                [
                    'change detection проходит по',
                    'помеченным view; инстансы',
                    'классов те же, меняется DOM',
                ],
            ],
            'ng_notes': [
                'инстанс класса создаётся один раз',
                'на время жизни view; тело класса',
                'не перевызывается при обновлении',
            ],
        },
        'en': {
            'react_title': 'REACT: a function of state',
            'react_steps': [
                ['setState(next)'],
                [
                    'the component function runs',
                    'again — new closures, new',
                    'props for the children',
                ],
                [
                    'React walks the subtree;',
                    'children re-render too unless',
                    'memo stops them',
                ],
            ],
            'react_notes': [
                'state lives outside, in hooks;',
                'the function body *is* the render',
            ],
            'ng_title': 'ANGULAR: a long-lived instance',
            'ng_steps': [
                ['count.set(next)'],
                [
                    'the signal marks dependent',
                    'templates dirty and schedules',
                    'a check',
                ],
                [
                    'change detection walks the',
                    'marked views; class instances',
                    'stay, only the DOM changes',
                ],
            ],
            'ng_notes': [
                'the class instance is created once',
                'per view lifetime; the class body is',
                'never re-run on an update',
            ],
        },
    },
    'binding-syntax': {
        'ru': {
            'rows': [
                ('в шаблоне', 'что делает Angular', 'в React'),
                ('{{ expr }}', 'текстовый узел, обновляется при проверке', '{expr}'),
                ('[prop]="expr"', 'СВОЙСТВО элемента или вход компонента', 'prop={expr}'),
                ('[attr.x]="expr"', 'атрибут через setAttribute/removeAttribute', 'x={expr}'),
                ('(event)="stmt"', 'слушатель события, stmt получает $event', 'onEvent={fn}'),
                ('[(x)]="expr"', 'сахар над [x]="expr" + (xChange)="expr = $event"', 'нет аналога'),
                ('[class.x]="cond"', 'точечно добавляет/снимает один класс', 'className=...'),
                ('[style.w.px]="n"', 'одно свойство стиля с указанием единиц', 'style={{...}}'),
                ('prop="text"', 'статическая строка, выражение НЕ вычисляется', 'prop="text"'),
            ],
        },
        'en': {
            'rows': [
                ('in a template', 'what Angular does', 'in React'),
                ('{{ expr }}', 'a text node, refreshed on every check', '{expr}'),
                ('[prop]="expr"', 'a PROPERTY of the element or a component input', 'prop={expr}'),
                ('[attr.x]="expr"', 'an attribute via setAttribute/removeAttribute', 'x={expr}'),
                ('(event)="stmt"', 'an event listener; stmt receives $event', 'onEvent={fn}'),
                ('[(x)]="expr"', 'sugar for [x]="expr" + (xChange)="expr = $event"', 'no equivalent'),
                ('[class.x]="cond"', 'toggles exactly one class', 'className=...'),
                ('[style.w.px]="n"', 'one style property, with units spelled out', 'style={{...}}'),
                ('prop="text"', 'a static string — the expression is NOT evaluated', 'prop="text"'),
            ],
        },
    },
    'template-compile': {
        'ru': {
            'step1': [
                'ticket-card.html',
                '<h3>{{ ticket().title }}</h3>',
                '<span [class.urgent]="isUrgent()">',
            ],
            'step2': [
                'компилятор Angular (AOT), время сборки',
                'разбирает шаблон, проверяет типы выражений',
                '(strictTemplates), сопоставляет теги с селекторами',
                'из imports этого компонента',
            ],
            'step3': [
                'две функции, вписанные в класс компонента',
                'create: создаёт узлы и слушатели один раз',
                'update: перечитывает выражения биндингов',
            ],
            'step4': [
                'DOM',
                'узлы живут между проверками; меняются',
                'только значения тех биндингов, что изменились',
            ],
        },
        'en': {
            'step1': [
                'ticket-card.html',
                '<h3>{{ ticket().title }}</h3>',
                '<span [class.urgent]="isUrgent()">',
            ],
            'step2': [
                'the Angular compiler (AOT), at build time',
                'parses the template, type-checks the expressions',
                '(strictTemplates), matches tags against selectors',
                'from this component\'s imports',
            ],
            'step3': [
                'two functions written into the component class',
                'create: builds nodes and listeners once',
                'update: re-reads the binding expressions',
            ],
            'step4': [
                'DOM',
                'nodes survive between checks; only the bindings',
                'whose values actually changed are touched',
            ],
        },
    },
    'encapsulation-modes': {
        'ru': {
            'title': 'ViewEncapsulation: что происходит со стилями компонента',
            'rows': [
                ('режим', 'механика', 'когда брать'),
                (
                    'Emulated (по умолчанию)',
                    'атрибуты _nghost/_ngcontent + перезапись селекторов',
                    'почти всегда',
                ),
                (
                    'ShadowDom',
                    'нативный shadow root: стили не входят и не выходят',
                    'жёсткая изоляция',
                ),
                (
                    'None',
                    'стили уходят в документ как глобальные',
                    'тема, ресеты',
                ),
            ],
            'notes': [
                ':host — сам хост-элемент; ::ng-deep пробивает изоляцию вниз,',
                'но оставлен только для обратной совместимости',
            ],
        },
        'en': {
            'title': 'ViewEncapsulation: what happens to component styles',
            'rows': [
                ('mode', 'mechanics', 'when to use'),
                (
                    'Emulated (default)',
                    '_nghost/_ngcontent attributes + rewritten selectors',
                    'almost always',
                ),
                (
                    'ShadowDom',
                    'a native shadow root: styles neither enter nor leave',
                    'hard isolation',
                ),
                (
                    'None',
                    'styles land in the document as global ones',
                    'themes, resets',
                ),
            ],
            'notes': [
                ':host is the host element itself; ::ng-deep pierces isolation downwards',
                'but is kept for backwards compatibility only',
            ],
        },
    },
    'signal-graph': {
        'ru': {
            'sources': ['tickets = signal([...])', 'statusFilter = signal(null)'],
            'derived': [
                'filtered = computed(() => ...)',
                'читает оба сигнала → подписка строится сама,',
                'по факту чтения, а не по списку зависимостей',
            ],
            'consumers': ['шаблон @for (t of filtered())', 'openCount = computed(...)'],
        },
        'en': {
            'sources': ['tickets = signal([...])', 'statusFilter = signal(null)'],
            'derived': [
                'filtered = computed(() => ...)',
                'reads both signals → the subscription builds itself,',
                'from the actual reads, not from a dependency list',
            ],
            'consumers': ['template @for (t of filtered())', 'openCount = computed(...)'],
        },
    },
    'reactive-tools': {
        'ru': {
            'rows': [
                ('задача', 'инструмент', 'почему именно он'),
                (
                    'значение выводится из других',
                    'computed',
                    'ленив, мемоизирован, только чтение',
                ),
                (
                    'состояние из источника, но перезаписываемое',
                    'linkedSignal',
                    'сброс при смене источника + set/update',
                ),
                (
                    'выход во внешний мир: логи, storage, focus()',
                    'effect',
                    'ничего не возвращает, только эффект',
                ),
                (
                    'один сигнал повторяет другой',
                    'ни один',
                    'дублирование = ошибка модели данных',
                ),
            ],
        },
        'en': {
            'rows': [
                ('the task', 'the tool', 'why this one'),
                (
                    'a value derived from others',
                    'computed',
                    'lazy, memoized, read-only',
                ),
                (
                    'state from a source, still overridable',
                    'linkedSignal',
                    'resets with the source + set/update',
                ),
                (
                    'reaching outside: logs, storage, focus()',
                    'effect',
                    'returns nothing, the effect is the point',
                ),
                (
                    'one signal mirroring another',
                    'none of them',
                    'duplication = a broken data model',
                ),
            ],
        },
    },
    'signal-io': {
        'ru': {
            'rows': [
                ('объявление', 'что получаем', 'в шаблоне родителя'),
                ('input<T>()', 'Signal<T | undefined>, только чтение', '[x]="expr"'),
                ('input.required<T>()', 'Signal<T>; без биндинга — ошибка сборки', '[x]="expr"'),
                ('input(0, { transform })', 'значение проходит через transform', '[x]="expr"'),
                ('output<T>()', 'объект с emit(value)', '(x)="onX($event)"'),
                ('model<T>(init)', 'записываемый сигнал + выход xChange', '[(x)]="expr"'),
                ('viewChild.required(Cmp)', 'Signal<Cmp> из своего шаблона', '—'),
                ('contentChildren(Cmp)', 'Signal<readonly Cmp[]> из проекции', '—'),
            ],
        },
        'en': {
            'rows': [
                ('declaration', 'what you get', "in the parent's template"),
                ('input<T>()', 'Signal<T | undefined>, read-only', '[x]="expr"'),
                ('input.required<T>()', 'Signal<T>; missing binding = build error', '[x]="expr"'),
                ('input(0, { transform })', 'the value passes through transform', '[x]="expr"'),
                ('output<T>()', 'an object with emit(value)', '(x)="onX($event)"'),
                ('model<T>(init)', 'a writable signal + an xChange output', '[(x)]="expr"'),
                ('viewChild.required(Cmp)', 'Signal<Cmp> from its own template', '—'),
                ('contentChildren(Cmp)', 'Signal<readonly Cmp[]> from projection', '—'),
            ],
        },
    },
    'cd-traversal': {
        'ru': {
            'rows': [
                ('App', 'обходится: он на пути к грязному компоненту'),
                ('├── AppHeader', 'пропущен: OnPush, входы те же, событий не было'),
                ('├── TicketList', 'проверяется: прочитанный в шаблоне сигнал изменился'),
                ('│   ├── TicketFilters', 'пропущен: его входы не менялись'),
                ('│   ├── TicketCard #101', 'проверяется: изменился вход selected'),
                ('│   └── TicketCard #102 … #106', 'пропущены: входы те же'),
                ('└── AppFooter', 'пропущен'),
            ],
        },
        'en': {
            'rows': [
                ('App', 'traversed: it sits on the path to a dirty component'),
                ('├── AppHeader', 'skipped: OnPush, same inputs, no events'),
                ('├── TicketList', 'checked: a signal read in its template changed'),
                ('│   ├── TicketFilters', 'skipped: its inputs did not change'),
                ('│   ├── TicketCard #101', 'checked: the selected input changed'),
                ('│   └── TicketCard #102 … #106', 'skipped: same inputs'),
                ('└── AppFooter', 'skipped'),
            ],
        },
    },
    'cd-triggers': {
        'ru': {
            'rows': [
                ('что произошло', 'zone.js (как было до v21)', 'zoneless (как сейчас)'),
                (
                    'клик по кнопке в шаблоне',
                    'зона перехватила событие → tick()',
                    'слушатель уведомляет напрямую',
                ),
                (
                    'signal.set, читаемый в шаблоне',
                    'обход дерева после микротасок',
                    'помечает путь, проверяет его',
                ),
                (
                    'setTimeout меняет поле класса',
                    'зона перехватила таймер → tick()',
                    'НИЧЕГО: уведомления нет',
                ),
                (
                    'колбэк fetch/промиса',
                    'зона перехватила → tick()',
                    'нужен сигнал или markForCheck',
                ),
                (
                    'emit в AsyncPipe',
                    'зона + markForCheck из пайпа',
                    'markForCheck из пайпа',
                ),
                (
                    'колбэк сторонней библиотеки',
                    'зона, если API пропатчен',
                    'нужен сигнал или markForCheck',
                ),
            ],
        },
        'en': {
            'rows': [
                ('what happened', 'zone.js (before v21)', 'zoneless (today)'),
                (
                    'a click on a template button',
                    'the zone caught the event → tick()',
                    'the listener notifies directly',
                ),
                (
                    'signal.set read in a template',
                    'a tree walk after the microtasks',
                    'marks the path, checks that path',
                ),
                (
                    'setTimeout writes a class field',
                    'the zone caught the timer → tick()',
                    'NOTHING: there is no notification',
                ),
                (
                    'a fetch/promise callback',
                    'the zone caught it → tick()',
                    'needs a signal or markForCheck',
                ),
                (
                    'an emit picked up by AsyncPipe',
                    'the zone + markForCheck in the pipe',
                    'markForCheck in the pipe',
                ),
                (
                    'a third-party library callback',
                    'the zone, if the API was patched',
                    'needs a signal or markForCheck',
                ),
            ],
        },
    },
    'cd-diagnosis': {
        'ru': {
            'title': 'Диагностика: симптом → причина → чем смотреть',
            'rows': [
                ('симптом', 'причина', 'инструмент'),
                (
                    'данные новые, DOM старый',
                    'источник не уведомил Angular',
                    'provideCheckNoChangesConfig',
                ),
                (
                    'обновляется через клик в любом месте',
                    'то же, но клик даёт обход',
                    'то же + DevTools profiler',
                ),
                (
                    'проверок больше, чем изменений',
                    'Eager-компонент или метод в шаблоне',
                    'DevTools profiler',
                ),
                (
                    'NG0100 после первого рендера',
                    'значение меняется во время проверки',
                    'стек ошибки: чей шаблон',
                ),
                (
                    'тест видит пустой DOM',
                    'нет await fixture.whenStable()',
                    'сам тест (глава 13)',
                ),
            ],
            'notes': [
                'NG0100 существует только в dev: в проде повторной проверки нет,',
                'и рассогласование остаётся невидимым',
            ],
        },
        'en': {
            'title': 'Diagnosis: symptom → cause → what to look with',
            'rows': [
                ('symptom', 'cause', 'tool'),
                (
                    'fresh data, stale DOM',
                    'the source never notified Angular',
                    'provideCheckNoChangesConfig',
                ),
                (
                    'a click anywhere fixes the view',
                    'same cause; the click forces a walk',
                    'same + DevTools profiler',
                ),
                (
                    'more checks than changes',
                    'an Eager component, a method call',
                    'DevTools profiler',
                ),
                (
                    'NG0100 right after first render',
                    'a value changes during the check',
                    'the error stack: whose template',
                ),
                (
                    'a test sees an empty DOM',
                    'no await fixture.whenStable()',
                    'the test itself (chapter 13)',
                ),
            ],
            'notes': [
                'NG0100 exists in dev only: production runs no second check,',
                'so the inconsistency stays invisible',
            ],
        },
    },
    'injector-hierarchy': {
        'ru': {
            'title': 'inject(TOKEN) в TicketCard: порядок поиска',
            'steps': [
                {
                    'lines': [
                        'ElementInjector: сам TicketCard',
                        'providers / viewProviders в его @Component',
                    ]
                },
                {
                    'edge': 'не нашли',
                    'lines': [
                        'ElementInjector: родительские элементы',
                        'TicketList, App — их providers',
                    ],
                },
                {
                    'edge': 'не нашли',
                    'lines': [
                        'EnvironmentInjector: маршрут',
                        'providers в Route (глава 07)',
                    ],
                },
                {
                    'edge': 'не нашли',
                    'lines': [
                        'EnvironmentInjector: root',
                        '@Service(), providedIn: root, appConfig.providers',
                    ],
                },
                {
                    'edge': 'не нашли',
                    'lines': ['EnvironmentInjector: platform', 'providedIn: platform'],
                },
                {
                    'edge': 'не нашли',
                    'lines': ['NullInjector', 'NG0201: No provider for TOKEN'],
                },
            ],
            'notes': [
                'первое совпадение выигрывает: провайдер на компоненте перекрывает root',
                'и создаёт СВОЙ инстанс на каждый инстанс этого компонента',
            ],
        },
        'en': {
            'title': 'inject(TOKEN) inside TicketCard: the lookup order',
            'steps': [
                {
                    'lines': [
                        'ElementInjector: TicketCard itself',
                        'providers / viewProviders in its @Component',
                    ]
                },
                {
                    'edge': 'not found',
                    'lines': [
                        'ElementInjector: ancestor elements',
                        'TicketList, App — their providers',
                    ],
                },
                {
                    'edge': 'not found',
                    'lines': [
                        'EnvironmentInjector: the route',
                        'providers on a Route (chapter 07)',
                    ],
                },
                {
                    'edge': 'not found',
                    'lines': [
                        'EnvironmentInjector: root',
                        '@Service(), providedIn: root, appConfig.providers',
                    ],
                },
                {
                    'edge': 'not found',
                    'lines': ['EnvironmentInjector: platform', 'providedIn: platform'],
                },
                {
                    'edge': 'not found',
                    'lines': ['NullInjector', 'NG0201: No provider for TOKEN'],
                },
            ],
            'notes': [
                'the first match wins: a component provider shadows root',
                'and creates ITS OWN instance per instance of that component',
            ],
        },
    },
    'provider-recipes': {
        'ru': {
            'rows': [
                ('рецепт', 'что подставляет', 'типичный случай'),
                ('useClass: Impl', 'новый инстанс класса Impl', 'подмена реализации'),
                ('useValue: obj', 'готовое значение как есть', 'конфиг, константы, мок'),
                ('useFactory: fn', 'результат вызова fn', 'выбор реализации в рантайме'),
                ('useExisting: Other', 'тот же инстанс, что у Other', 'узкий интерфейс к сервису'),
                ('multi: true', 'массив всех значений токена', 'набор правил, интерсепторы'),
            ],
        },
        'en': {
            'rows': [
                ('recipe', 'what it supplies', 'typical use'),
                ('useClass: Impl', 'a new instance of Impl', 'swapping an implementation'),
                ('useValue: obj', 'a ready value as-is', 'config, constants, a mock'),
                ('useFactory: fn', 'the result of calling fn', 'choosing an impl at runtime'),
                ('useExisting: Other', 'the very instance of Other', 'a narrow interface to a service'),
                ('multi: true', 'an array of all values for the token', 'rule sets, interceptors'),
            ],
        },
    },
    'inject-modifiers': {
        'ru': {
            'rows': [
                ('вызов', 'что меняет в поиске', 'когда нужно'),
                ('inject(T)', 'обычный поиск снизу вверх', 'по умолчанию'),
                ('inject(T, { optional: true })', 'вернёт null вместо NG0201', 'необязательная зависимость'),
                ('inject(T, { self: true })', 'только свой ElementInjector', 'требуем локальный провайдер'),
                ('inject(T, { skipSelf: true })', 'начать с родителя', 'декоратор поверх родительского'),
                ('inject(T, { host: true })', 'не выше хост-компонента', 'директива внутри чужого хоста'),
            ],
        },
        'en': {
            'rows': [
                ('call', 'how it changes the lookup', 'when you need it'),
                ('inject(T)', 'the normal bottom-up lookup', 'the default'),
                ('inject(T, { optional: true })', 'returns null instead of NG0201', 'an optional dependency'),
                ('inject(T, { self: true })', 'this ElementInjector only', 'demanding a local provider'),
                ('inject(T, { skipSelf: true })', 'start at the parent', 'decorating the parent instance'),
                ('inject(T, { host: true })', 'no higher than the host component', 'a directive inside a foreign host'),
            ],
        },
    },
    'store-anatomy': {
        'ru': {
            'title': 'Сигнальный стор на сервисе: что наружу, что внутрь',
            'layer1': [
                'компонент: только чтение и команды',
                'store.filtered()   store.setStatus("open")',
            ],
            'layer2': [
                'публичное API сервиса — всё только для чтения',
                'readonly tickets = this.state.asReadonly()',
                'readonly filtered = computed(() => ...)',
            ],
            'layer3': [
                'команды: единственный способ изменить состояние',
                'add(ticket)  setStatus(s)  select(id)  reset()',
            ],
            'layer4': [
                'приватное состояние: только его и пишем',
                'private state = signal<readonly Ticket[]>([])',
            ],
            'notes': [
                'наружу не отдаётся WritableSignal: иначе любой компонент',
                'сможет писать в состояние в обход команд',
            ],
        },
        'en': {
            'title': 'A signal store in a service: what goes out, what stays in',
            'layer1': [
                'component: reads and commands only',
                'store.filtered()   store.setStatus("open")',
            ],
            'layer2': [
                "the service's public API — read-only throughout",
                'readonly tickets = this.state.asReadonly()',
                'readonly filtered = computed(() => ...)',
            ],
            'layer3': [
                'commands: the only way to change state',
                'add(ticket)  setStatus(s)  select(id)  reset()',
            ],
            'layer4': [
                'private state: the only thing ever written',
                'private state = signal<readonly Ticket[]>([])',
            ],
            'notes': [
                'a WritableSignal is never exposed: otherwise any component',
                'could write to the state and bypass the commands',
            ],
        },
    },
    'state-ladder': {
        'ru': {
            'title': 'Лестница решений: берём следующую ступень, когда прижало',
            'rows': [
                ('уровень', 'когда это достаточно', 'чем платите'),
                (
                    'сигналы в компоненте',
                    'состояние живёт и умирает с экраном',
                    'ничем',
                ),
                (
                    'сервис с сигналами',
                    'данные нужны нескольким экранам',
                    'дисциплина инкапсуляции',
                ),
                (
                    'NgRx SignalStore',
                    'много фич, нужны единые конвенции',
                    'зависимость + свой цикл релизов',
                ),
                (
                    'NgRx Store (actions)',
                    'нужны трассировка, time-travel, аудит',
                    'бойлерплейт и обучение команды',
                ),
            ],
            'notes': [
                'на 14.08.2026 стабильный NgRx — 21.1.1 с peer @angular/core ^21;',
                'поддержка v22 пока в 22.0.0-rc.0 под тегом next — это и есть цена',
            ],
        },
        'en': {
            'title': 'The ladder: climb a step only when the current one hurts',
            'rows': [
                ('level', 'when it is enough', 'what it costs'),
                (
                    'signals in a component',
                    'state is born and dies with the screen',
                    'nothing',
                ),
                (
                    'a service with signals',
                    'several screens need the same data',
                    'encapsulation discipline',
                ),
                (
                    'NgRx SignalStore',
                    'many features, shared conventions needed',
                    'a dependency with its own cycle',
                ),
                (
                    'NgRx Store (actions)',
                    'tracing, time-travel and audit required',
                    'boilerplate and team ramp-up',
                ),
            ],
            'notes': [
                'as of 2026-08-14 the stable NgRx is 21.1.1 with peer @angular/core ^21;',
                'v22 support sits in 22.0.0-rc.0 under the next tag — that is the cost',
            ],
        },
    },
    'state-mapping': {
        'ru': {
            'rows': [
                ('задача', 'в React', 'в Angular'),
                ('состояние одного экрана', 'useState / useReducer', 'signal в компоненте'),
                ('раздать зависимость вниз', 'Context + Provider', 'DI: сервис через inject()'),
                ('общее состояние приложения', 'Zustand / Redux', 'сервис с сигналами'),
                ('производное значение', 'useMemo / селектор', 'computed'),
                ('серверные данные и кеш', 'TanStack Query', 'httpResource (глава 08)'),
                ('строгие конвенции команды', 'Redux Toolkit', 'NgRx SignalStore / Store'),
            ],
        },
        'en': {
            'rows': [
                ('the task', 'in React', 'in Angular'),
                ('state of a single screen', 'useState / useReducer', 'a signal in the component'),
                ('hand a dependency down', 'Context + Provider', 'DI: a service via inject()'),
                ('application-wide state', 'Zustand / Redux', 'a service with signals'),
                ('a derived value', 'useMemo / a selector', 'computed'),
                ('server data and caching', 'TanStack Query', 'httpResource (chapter 08)'),
                ('strict team conventions', 'Redux Toolkit', 'NgRx SignalStore / Store'),
            ],
        },
    },
    'structural-desugar': {
        'ru': {
            'title': 'Во что превращается звёздочка',
            'steps': [
                {
                    'lines': [
                        'в шаблоне',
                        '<li *appRepeat="3">строка</li>',
                    ]
                },
                {
                    'edge': 'компилятор',
                    'lines': [
                        'разворачивается в ng-template',
                        '<ng-template appRepeat [appRepeat]="3">',
                        '  <li>строка</li>',
                        '</ng-template>',
                    ],
                },
                {
                    'edge': 'DI',
                    'lines': [
                        'директива получает две зависимости',
                        'TemplateRef  — что рендерить',
                        'ViewContainerRef — куда рендерить',
                    ],
                },
                {
                    'edge': 'рантайм',
                    'lines': [
                        'директива сама решает, сколько раз и когда',
                        'vcr.createEmbeddedView(tpl, context)',
                        'vcr.clear()',
                    ],
                },
            ],
            'notes': [
                '@if/@for — те же встроенные view, но без директивы-посредника:',
                'блоки компилируются напрямую и потому дешевле',
            ],
        },
        'en': {
            'title': 'What the asterisk turns into',
            'steps': [
                {
                    'lines': [
                        'in the template',
                        '<li *appRepeat="3">a row</li>',
                    ]
                },
                {
                    'edge': 'compiler',
                    'lines': [
                        'desugars into an ng-template',
                        '<ng-template appRepeat [appRepeat]="3">',
                        '  <li>a row</li>',
                        '</ng-template>',
                    ],
                },
                {
                    'edge': 'DI',
                    'lines': [
                        'the directive receives two dependencies',
                        'TemplateRef  — what to render',
                        'ViewContainerRef — where to render it',
                    ],
                },
                {
                    'edge': 'runtime',
                    'lines': [
                        'the directive decides how many times and when',
                        'vcr.createEmbeddedView(tpl, context)',
                        'vcr.clear()',
                    ],
                },
            ],
            'notes': [
                '@if/@for use the same embedded views but with no directive in',
                'between: the blocks compile directly and are cheaper for it',
            ],
        },
    },
    'tool-choice': {
        'ru': {
            'rows': [
                ('что нужно', 'инструмент', 'признак выбора'),
                ('своя разметка и своё состояние', 'компонент', 'есть шаблон'),
                ('поведение на чужом элементе', 'атрибутная директива', 'разметку не добавляем'),
                ('решать, рендерить ли и сколько раз', 'структурная директива', 'нужен TemplateRef'),
                ('преобразовать значение для вывода', 'пайп', 'чистая функция от входа'),
                ('производное значение компонента', 'computed', 'зависит от сигналов'),
                ('набор поведений на компоненте', 'hostDirectives', 'композиция без наследования'),
            ],
        },
        'en': {
            'rows': [
                ('what you need', 'the tool', 'the deciding sign'),
                ('own markup and own state', 'a component', 'it has a template'),
                ('behaviour on someone else\'s element', 'an attribute directive', 'no markup is added'),
                ('decide whether and how often to render', 'a structural directive', 'you need a TemplateRef'),
                ('reshape a value for display', 'a pipe', 'a pure function of its input'),
                ('a derived value of a component', 'computed', 'it depends on signals'),
                ('a bundle of behaviours on a component', 'hostDirectives', 'composition, not inheritance'),
            ],
        },
    },
    'pipe-cost': {
        'ru': {
            'title': 'Цена вычисления в шаблоне',
            'rows': [
                ('в шаблоне', 'когда выполняется', 'кеш'),
                ('чистый пайп, вход — примитив', 'при изменении значения', 'да'),
                ('чистый пайп, вход — объект', 'при смене ССЫЛКИ, не мутации', 'да'),
                ('impure-пайп (pure: false)', 'при каждой проверке шаблона', 'нет'),
                ('async, keyValue, slice, json', 'при каждой проверке (они impure)', 'нет'),
                ('метод класса {{ f(x) }}', 'при каждой проверке шаблона', 'нет'),
                ('computed в классе', 'при изменении зависимостей', 'да'),
            ],
            'notes': [
                'встроенные date, currency, decimal, uppercase — чистые;',
                'async вдобавок сам зовёт markForCheck при каждом emit',
            ],
        },
        'en': {
            'title': 'The cost of computing inside a template',
            'rows': [
                ('in the template', 'when it runs', 'cached'),
                ('a pure pipe, primitive input', 'when the value changes', 'yes'),
                ('a pure pipe, object input', 'when the REFERENCE changes, not on mutation', 'yes'),
                ('an impure pipe (pure: false)', 'on every check of the template', 'no'),
                ('async, keyValue, slice, json', 'on every check (they are impure)', 'no'),
                ('a class method {{ f(x) }}', 'on every check of the template', 'no'),
                ('a computed in the class', 'when its dependencies change', 'yes'),
            ],
            'notes': [
                'the built-in date, currency, decimal and uppercase are pure;',
                'async additionally calls markForCheck on every emit',
            ],
        },
    },
    'navigation-flow': {
        'ru': {
            'title': 'Что происходит между кликом по ссылке и появлением экрана',
            'steps': [
                {'lines': ['URL: /admin/reports?range=7d']},
                {
                    'edge': 'сопоставление',
                    'lines': [
                        'подбор маршрута сверху вниз + canMatch',
                        'false → маршрут пропускается, пробуем следующий',
                    ],
                },
                {
                    'edge': 'маршрут найден',
                    'lines': [
                        'загрузка ленивого чанка',
                        'loadComponent / loadChildren + providers маршрута',
                    ],
                },
                {
                    'edge': 'код загружен',
                    'lines': [
                        'canDeactivate текущего → canActivate нового',
                        'false → навигация отменяется, URL не меняется',
                    ],
                },
                {
                    'edge': 'доступ есть',
                    'lines': ['resolve: навигация ЖДЁТ данные', 'ошибка → навигация падает'],
                },
                {
                    'edge': 'данные готовы',
                    'lines': [
                        'создание компонентов в router-outlet',
                        'входы заполняет withComponentInputBinding',
                    ],
                },
            ],
            'notes': [
                'canMatch отсекает маршрут ДО загрузки чанка, canActivate — после:',
                'для ленивых разделов с ролями это разница в мегабайтах',
            ],
        },
        'en': {
            'title': 'What happens between the click and the screen',
            'steps': [
                {'lines': ['URL: /admin/reports?range=7d']},
                {
                    'edge': 'matching',
                    'lines': [
                        'routes are matched top-down + canMatch',
                        'false → this route is skipped, try the next one',
                    ],
                },
                {
                    'edge': 'route found',
                    'lines': [
                        'the lazy chunk is loaded',
                        'loadComponent / loadChildren + route providers',
                    ],
                },
                {
                    'edge': 'code loaded',
                    'lines': [
                        'canDeactivate of the current → canActivate of the new',
                        'false → navigation is cancelled, the URL stays',
                    ],
                },
                {
                    'edge': 'access granted',
                    'lines': ['resolve: navigation WAITS for data', 'an error fails the navigation'],
                },
                {
                    'edge': 'data ready',
                    'lines': [
                        'components are created in the router-outlet',
                        'inputs are filled by withComponentInputBinding',
                    ],
                },
            ],
            'notes': [
                'canMatch rejects a route BEFORE the chunk loads, canActivate after:',
                'for role-gated lazy sections that difference is measured in megabytes',
            ],
        },
    },
    'guard-matrix': {
        'ru': {
            'rows': [
                ('гард', 'когда выполняется', 'что значит false', 'типичный случай'),
                ('canMatch', 'при подборе маршрута', 'пробуем следующий маршрут', 'фича-флаг, роль'),
                ('canActivate', 'после подбора, до resolve', 'навигация отменяется', 'требуется вход'),
                ('canActivateChild', 'для каждого дочернего', 'навигация отменяется', 'защита раздела'),
                ('canDeactivate', 'при уходе с маршрута', 'остаёмся на месте', 'несохранённая форма'),
                ('resolve', 'после гардов, до компонента', 'ошибка навигации', 'данные до рендера'),
            ],
        },
        'en': {
            'rows': [
                ('guard', 'when it runs', 'what false means', 'typical use'),
                ('canMatch', 'while matching routes', 'try the next route', 'feature flag, role'),
                ('canActivate', 'after matching, before resolve', 'navigation is cancelled', 'login required'),
                ('canActivateChild', 'for every child route', 'navigation is cancelled', 'guarding a section'),
                ('canDeactivate', 'when leaving a route', 'you stay where you are', 'unsaved form'),
                ('resolve', 'after guards, before the component', 'navigation error', 'data before render'),
            ],
        },
    },
    'route-state': {
        'ru': {
            'title': 'Как прочитать состояние маршрута',
            'rows': [
                ('способ', 'что даёт', 'когда брать'),
                ('input() + withComponentInputBinding', 'сигнал, роутер обновляет сам', 'в компоненте — по умолчанию'),
                ('toSignal(route.params)', 'сигнал из Observable', 'в сервисе или гарде'),
                ('route.snapshot.paramMap', 'значение на момент создания', 'одноразовое чтение'),
                ('route.params.subscribe', 'поток изменений', 'старый код, глава 09'),
            ],
            'notes': [
                'снимок не обновляется при смене :id, если компонент переиспользован —',
                'это источник бага "открыл другой тикет, а данные прежние"',
            ],
        },
        'en': {
            'title': 'How to read route state',
            'rows': [
                ('approach', 'what you get', 'when to use it'),
                ('input() + withComponentInputBinding', 'a signal the router keeps updated', 'in a component — the default'),
                ('toSignal(route.params)', 'a signal from an Observable', 'in a service or a guard'),
                ('route.snapshot.paramMap', 'the value at creation time', 'a one-off read'),
                ('route.params.subscribe', 'a stream of changes', 'older code, chapter 09'),
            ],
            'notes': [
                'a snapshot does not update when :id changes and the component is reused —',
                'the source of the "opened another ticket, same data" bug',
            ],
        },
    },
    'interceptor-chain': {
        'ru': {
            'title': 'Один запрос сквозь цепочку интерсепторов',
            'steps': [
                {
                    'lines': [
                        'httpResource(() => url) или http.get<Ticket[]>(url)',
                        'запрос уходит вниз по цепочке в порядке withInterceptors',
                    ]
                },
                {
                    'edge': 'req',
                    'lines': [
                        'authInterceptor',
                        'вниз: req.clone({ headers: … Bearer token })',
                        'вверх: 401 → refresh или разлогин',
                    ],
                },
                {
                    'edge': 'req',
                    'lines': [
                        'loggingInterceptor',
                        'вниз: время старта, метод, url',
                        'вверх: код ответа и длительность',
                    ],
                },
                {
                    'edge': 'req',
                    'lines': [
                        'errorInterceptor',
                        'вниз: ничего',
                        'вверх: 5xx → retry, затем маппинг в свою ошибку',
                    ],
                },
                {
                    'edge': 'req',
                    'lines': [
                        'FetchBackend — реальный fetch()',
                        'ответ идёт обратно ВВЕРХ в обратном порядке',
                    ],
                },
            ],
            'notes': [
                'запрос иммутабелен: менять его можно только через req.clone();',
                'метаданные для интерсепторов передаются в req.context',
            ],
        },
        'en': {
            'title': 'One request through the interceptor chain',
            'steps': [
                {
                    'lines': [
                        'httpResource(() => url) or http.get<Ticket[]>(url)',
                        'the request travels down in withInterceptors order',
                    ]
                },
                {
                    'edge': 'req',
                    'lines': [
                        'authInterceptor',
                        'down: req.clone({ headers: … Bearer token })',
                        'up: 401 → refresh or sign out',
                    ],
                },
                {
                    'edge': 'req',
                    'lines': [
                        'loggingInterceptor',
                        'down: start time, method, url',
                        'up: status code and duration',
                    ],
                },
                {
                    'edge': 'req',
                    'lines': [
                        'errorInterceptor',
                        'down: nothing',
                        'up: 5xx → retry, then map to a domain error',
                    ],
                },
                {
                    'edge': 'req',
                    'lines': [
                        'FetchBackend — the actual fetch()',
                        'the response travels back UP in reverse order',
                    ],
                },
            ],
            'notes': [
                'a request is immutable: change it only through req.clone();',
                'metadata for interceptors travels in req.context',
            ],
        },
    },
    'error-handling-map': {
        'ru': {
            'title': 'Где обрабатывать какую ошибку',
            'rows': [
                ('ситуация', 'где обрабатывать', 'что видит пользователь'),
                ('401 Unauthorized', 'интерсептор', 'редирект на вход'),
                ('403 Forbidden', 'интерсептор', 'страница "нет доступа"'),
                ('404 на конкретной сущности', 'экран или резолвер', '"тикет не найден"'),
                ('422 / ошибки валидации', 'форма, отправившая запрос', 'сообщения у полей'),
                ('5xx', 'интерсептор: retry, затем баннер', '"попробуйте позже"'),
                ('сеть недоступна, timeout', 'интерсептор', 'офлайн-состояние'),
            ],
            'notes': [
                'общее правило: если реакция одинакова для всего приложения — интерсептор;',
                'если зависит от экрана — обрабатывается там, где запрос был вызван',
            ],
        },
        'en': {
            'title': 'Where to handle which error',
            'rows': [
                ('situation', 'where to handle it', 'what the user sees'),
                ('401 Unauthorized', 'an interceptor', 'redirect to sign-in'),
                ('403 Forbidden', 'an interceptor', 'a "no access" page'),
                ('404 for a specific entity', 'the screen or a resolver', '"ticket not found"'),
                ('422 / validation errors', 'the form that sent it', 'messages next to fields'),
                ('5xx', 'an interceptor: retry, then a banner', '"try again later"'),
                ('network down, timeout', 'an interceptor', 'an offline state'),
            ],
            'notes': [
                'the rule: if the reaction is the same app-wide, it belongs in an interceptor;',
                'if it depends on the screen, handle it where the request was made',
            ],
        },
    },
    'fetch-options': {
        'ru': {
            'rows': [
                ('способ загрузки', 'что даёт', 'когда брать'),
                ('httpResource(() => url)', 'value/isLoading/error как сигналы', 'данные экрана — по умолчанию'),
                ('resource({ params, loader })', 'то же, но loader любой async', 'не-HTTP источник, свой fetch'),
                ('http.get<T>() + subscribe', 'ручное управление и отписка', 'команды: POST/PUT/DELETE'),
                ('http.get<T>() + toSignal', 'сигнал из Observable', 'нужен RxJS-конвейер (глава 09)'),
                ('ResolveFn в маршруте', 'данные до рендера', 'проверки перед навигацией (глава 07)'),
            ],
        },
        'en': {
            'rows': [
                ('loading approach', 'what you get', 'when to use it'),
                ('httpResource(() => url)', 'value/isLoading/error as signals', 'screen data — the default'),
                ('resource({ params, loader })', 'the same, any async loader', 'a non-HTTP source, custom fetch'),
                ('http.get<T>() + subscribe', 'manual control and teardown', 'commands: POST/PUT/DELETE'),
                ('http.get<T>() + toSignal', 'a signal from an Observable', 'an RxJS pipeline is needed (ch. 09)'),
                ('ResolveFn on a route', 'data before render', 'pre-navigation checks (chapter 07)'),
            ],
        },
    },
    'rxjs-map': {
        'ru': {
            'title': 'Где RxJS остался, а где его вытеснили сигналы',
            'rows': [
                ('задача', 'было на RxJS', 'сейчас'),
                ('состояние компонента', 'BehaviorSubject + async', 'signal'),
                ('производное значение', 'combineLatest + map', 'computed'),
                ('загрузка данных экрана', 'switchMap + subscribe', 'httpResource'),
                ('события роутера', 'router.events', 'RxJS: другого API нет'),
                ('поиск с debounce', 'debounceTime + switchMap', 'RxJS: время — его тема'),
                ('поллинг, интервалы', 'interval + switchMap', 'RxJS или таймер + сигнал'),
                ('valueChanges формы', 'valueChanges', 'RxJS в Reactive Forms'),
                ('отписка в компоненте', 'takeUntil(destroy$)', 'takeUntilDestroyed()'),
            ],
            'notes': [
                'правило: состояние и производные значения — сигналы;',
                'всё, где важно ВРЕМЯ (задержки, окна, порядок, отмена) — RxJS',
            ],
        },
        'en': {
            'title': 'Where RxJS stayed and where signals replaced it',
            'rows': [
                ('the task', 'the RxJS way', 'today'),
                ('component state', 'BehaviorSubject + async', 'signal'),
                ('a derived value', 'combineLatest + map', 'computed'),
                ('loading screen data', 'switchMap + subscribe', 'httpResource'),
                ('router events', 'router.events', 'RxJS: there is no other API'),
                ('search with debounce', 'debounceTime + switchMap', 'RxJS: timing is its domain'),
                ('polling, intervals', 'interval + switchMap', 'RxJS or a timer plus a signal'),
                ('form valueChanges', 'valueChanges', 'RxJS inside Reactive Forms'),
                ('teardown in a component', 'takeUntil(destroy$)', 'takeUntilDestroyed()'),
            ],
            'notes': [
                'the rule: state and derived values are signals;',
                'anything where TIME matters (delays, windows, order, cancellation) is RxJS',
            ],
        },
    },
    'interop-bridge': {
        'ru': {
            'to_signal_title': 'toSignal(obs$)',
            'to_signal': [
                'Observable → Signal',
                '',
                'подписывается сразу и сам',
                'отписывается при уничтожении',
                'контекста инъекции',
                '',
                'нужно начальное значение:',
                'initialValue или requireSync',
                '',
                'ошибка потока → выброс при',
                'чтении сигнала',
            ],
            'to_signal_notes': [
                'обычный путь: RxJS-конвейер',
                'заканчивается сигналом',
            ],
            'to_observable_title': 'toObservable(sig)',
            'to_observable': [
                'Signal → Observable',
                '',
                'значения приходят через',
                'effect: не синхронно, а на',
                'следующей синхронизации',
                '',
                'промежуточные значения',
                'могут не попасть в поток',
                '',
                'нужен контекст инъекции',
                'или явный injector',
            ],
            'to_observable_notes': [
                'нужен редко: только чтобы отдать',
                'сигнал в готовый RxJS-конвейер',
            ],
        },
        'en': {
            'to_signal_title': 'toSignal(obs$)',
            'to_signal': [
                'Observable → Signal',
                '',
                'subscribes immediately and',
                'unsubscribes when the injection',
                'context is destroyed',
                '',
                'an initial value is required:',
                'initialValue or requireSync',
                '',
                'a stream error is rethrown when',
                'the signal is read',
            ],
            'to_signal_notes': [
                'the common direction: an RxJS',
                'pipeline ends in a signal',
            ],
            'to_observable_title': 'toObservable(sig)',
            'to_observable': [
                'Signal → Observable',
                '',
                'values arrive through an effect:',
                'not synchronously, but on the',
                'next synchronization',
                '',
                'intermediate values may never',
                'reach the stream',
                '',
                'needs an injection context',
                'or an explicit injector',
            ],
            'to_observable_notes': [
                'rarely needed: only to feed a signal',
                'into an existing RxJS pipeline',
            ],
        },
    },
    'flattening-operators': {
        'ru': {
            'rows': [
                ('оператор', 'что делает с предыдущим', 'типичный случай'),
                ('switchMap', 'отменяет предыдущий запрос', 'поиск, смена фильтра'),
                ('concatMap', 'ждёт завершения, сохраняет порядок', 'очередь сохранений'),
                ('mergeMap', 'выполняет параллельно', 'независимые загрузки'),
                ('exhaustMap', 'игнорирует новые, пока идёт текущий', 'защита от двойного клика'),
            ],
        },
        'en': {
            'rows': [
                ('operator', 'what it does to the previous one', 'typical use'),
                ('switchMap', 'cancels the previous request', 'search, filter change'),
                ('concatMap', 'waits for it, preserving order', 'a queue of saves'),
                ('mergeMap', 'runs them in parallel', 'independent loads'),
                ('exhaustMap', 'ignores new ones while busy', 'double-click protection'),
            ],
        },
    },
    'control-states': {
        'ru': {
            'title': 'Состояния контрола: на чём строится UX ошибок',
            'rows': [
                ('состояние', 'когда становится true', 'что с ним делать'),
                ('touched', 'поле потеряло фокус', 'главный триггер показа ошибки'),
                ('dirty', 'значение менял пользователь', 'предупреждение об уходе'),
                ('pending', 'идёт async-валидация', 'спиннер у поля, блок submit'),
                ('invalid', 'валидаторы вернули ошибку', 'сам факт ошибки, но не показ'),
                ('disabled', 'control.disable()', 'значение выпадает из form.value'),
            ],
            'notes': [
                'ошибку показывают при invalid И (touched ИЛИ форма отправлена):',
                'иначе поля краснеют до того, как пользователь начал вводить',
            ],
        },
        'en': {
            'title': 'Control states: what error UX is built on',
            'rows': [
                ('state', 'becomes true when', 'what to do with it'),
                ('touched', 'the field lost focus', 'the main trigger for showing errors'),
                ('dirty', 'the user changed the value', 'the unsaved-changes warning'),
                ('pending', 'async validation is running', 'a spinner on the field, block submit'),
                ('invalid', 'a validator returned an error', 'the error exists, but do not show yet'),
                ('disabled', 'control.disable()', 'the value drops out of form.value'),
            ],
            'notes': [
                'show an error when invalid AND (touched OR the form was submitted):',
                'otherwise fields turn red before the user has typed anything',
            ],
        },
    },
    'forms-comparison': {
        'ru': {
            'rows': [
                ('что делаем', 'Reactive Forms', 'Signal Forms (v22)'),
                ('источник правды', 'FormGroup внутри формы', 'ваш signal с данными'),
                ('создание', 'new FormGroup({...})', 'form(model)'),
                ('привязка в шаблоне', '[formGroup] + formControlName', '[formRoot] + [formField]'),
                ('валидатор', 'Validators.required в контроле', 'required(path) в схеме'),
                ('чтение ошибок', 'control.errors?.[key]', 'field().errors()'),
                ('свой контрол', 'ControlValueAccessor', 'интерфейс FormValueControl<T>'),
                ('отправка', 'form.valid + свой submit', 'submit(form, { action })'),
            ],
        },
        'en': {
            'rows': [
                ('the task', 'Reactive Forms', 'Signal Forms (v22)'),
                ('source of truth', 'the FormGroup itself', 'your data signal'),
                ('creation', 'new FormGroup({...})', 'form(model)'),
                ('template binding', '[formGroup] + formControlName', '[formRoot] + [formField]'),
                ('a validator', 'Validators.required on a control', 'required(path) in a schema'),
                ('reading errors', 'control.errors?.[key]', 'field().errors()'),
                ('a custom control', 'ControlValueAccessor', 'the FormValueControl<T> interface'),
                ('submitting', 'form.valid + your own submit', 'submit(form, { action })'),
            ],
        },
    },
    'value-writes': {
        'ru': {
            'title': 'Запись значений в Reactive Forms',
            'rows': [
                ('вызов', 'что делает', 'подводный камень'),
                ('setValue(v)', 'требует ВСЕ поля группы', 'пропустил поле — ошибка в рантайме'),
                ('patchValue(v)', 'обновляет только переданные', 'опечатку в ключе не заметит никто'),
                ('reset(v)', 'значение + сброс touched/dirty', 'сбрасывает и статусы валидации'),
                ('{ emitEvent: false }', 'не эмитит valueChanges', 'зависимая логика не сработает'),
                ('form.value', 'без disabled-полей', 'нужен getRawValue()'),
            ],
            'notes': [
                'в zoneless setValue/patchValue НЕ запускают проверку шаблона сами:',
                'состояние формы надо отражать в сигналах или звать markForCheck',
            ],
        },
        'en': {
            'title': 'Writing values in Reactive Forms',
            'rows': [
                ('call', 'what it does', 'the gotcha'),
                ('setValue(v)', 'requires EVERY field of the group', 'a missing field throws at runtime'),
                ('patchValue(v)', 'updates only what you passed', 'a typo in a key goes unnoticed'),
                ('reset(v)', 'value plus touched/dirty reset', 'it resets validation statuses too'),
                ('{ emitEvent: false }', 'does not emit valueChanges', 'dependent logic never runs'),
                ('form.value', 'excludes disabled fields', 'you need getRawValue()'),
            ],
            'notes': [
                'in zoneless, setValue/patchValue do NOT schedule a template check:',
                'mirror form state into signals or call markForCheck',
            ],
        },
    },
    'projection-options': {
        'ru': {
            'title': 'Три способа отдать разметку в чужой компонент',
            'rows': [
                ('способ', 'когда создаётся', 'данные внутрь', 'когда брать'),
                ('ng-content', 'ВСЕГДА, даже если скрыт', 'нет: контекст родителя', 'статичные слоты'),
                ('ng-template + outlet', 'когда вставили', 'да: контекст шаблона', 'строки таблицы, ячейки'),
                ('createComponent()', 'по вызову в коде', 'да: setInput()', 'модалки, тулбары, плагины'),
            ],
            'notes': [
                'документация прямо запрещает оборачивать ng-content в @if/@for/@switch:',
                'содержимое всё равно будет создано, а условие лишь спрячет его',
            ],
        },
        'en': {
            'title': 'Three ways to hand markup to someone else\'s component',
            'rows': [
                ('approach', 'when it is created', 'passing data in', 'when to use it'),
                ('ng-content', 'ALWAYS, even when hidden', 'no: the parent context', 'static slots'),
                ('ng-template + outlet', 'when it is inserted', 'yes: template context', 'table rows, cells'),
                ('createComponent()', 'when your code calls it', 'yes: setInput()', 'dialogs, toolbars, plugins'),
            ],
            'notes': [
                'the docs explicitly forbid wrapping ng-content in @if/@for/@switch:',
                'the content is created regardless and the condition merely hides it',
            ],
        },
    },
    'slot-matching': {
        'ru': {
            'consumer_title': 'что пишет потребитель',
            'consumer': [
                '<app-panel>',
                '  <h2 panel-title>Tickets</h2>',
                '  <button panel-action>New</button>',
                '  <p>Список за сегодня</p>',
                '</app-panel>',
            ],
            'consumer_notes': [
                'ngProjectAs позволяет попасть в слот,',
                'не меняя разметку под селектор',
            ],
            'component_title': 'куда это попадёт в шаблоне panel',
            'component': [
                '<header>',
                '  <ng-content select="[panel-title]" />',
                '  <ng-content select="[panel-action]" />',
                '</header>',
                '<div class="body">',
                '  <ng-content>Нет данных</ng-content>',
                '</div>',
            ],
            'component_notes': [
                'ng-content без select забирает остальное;',
                'внутри тега — контент по умолчанию',
            ],
        },
        'en': {
            'consumer_title': 'what the consumer writes',
            'consumer': [
                '<app-panel>',
                '  <h2 panel-title>Tickets</h2>',
                '  <button panel-action>New</button>',
                '  <p>Today\'s list</p>',
                '</app-panel>',
            ],
            'consumer_notes': [
                'ngProjectAs lets content reach a slot',
                'without reshaping it for the selector',
            ],
            'component_title': 'where it lands in the panel template',
            'component': [
                '<header>',
                '  <ng-content select="[panel-title]" />',
                '  <ng-content select="[panel-action]" />',
                '</header>',
                '<div class="body">',
                '  <ng-content>No data</ng-content>',
                '</div>',
            ],
            'component_notes': [
                'an ng-content with no select takes the rest;',
                'text inside the tag is the fallback',
            ],
        },
    },
    'cdk-primitives': {
        'ru': {
            'title': 'Angular CDK: что брать вместо своей реализации',
            'rows': [
                ('задача', 'примитив CDK'),
                ('всплывающий слой, позиционирование', 'overlay'),
                ('вставить шаблон/компонент в другое место', 'portal'),
                ('ловушка фокуса, live-объявления, монитор фокуса', 'a11y'),
                ('перетаскивание, сортировка списков', 'drag-drop'),
                ('виртуальный скролл больших списков', 'scrolling'),
                ('структура таблицы без стилей', 'table'),
                ('диалог с фокусом и ролями', 'dialog'),
                ('меню, listbox, дерево, аккордеон, степпер', 'menu, listbox, tree, accordion, stepper'),
                ('тесты через harness вместо разметки', 'testing (глава 13)'),
            ],
            'notes': [
                '@angular/aria (stable c v22) идёт дальше: готовые директивы поведения —',
                'accordion, combobox, grid, listbox, menu, tabs, toolbar, tree',
            ],
        },
        'en': {
            'title': 'Angular CDK: what to take instead of writing your own',
            'rows': [
                ('the task', 'the CDK primitive'),
                ('a floating layer with positioning', 'overlay'),
                ('render a template/component elsewhere', 'portal'),
                ('focus trap, live announcements, focus monitor', 'a11y'),
                ('dragging and reordering lists', 'drag-drop'),
                ('virtual scrolling for large lists', 'scrolling'),
                ('table structure without styles', 'table'),
                ('a dialog with focus and roles', 'dialog'),
                ('menu, listbox, tree, accordion, stepper', 'menu, listbox, tree, accordion, stepper'),
                ('tests through harnesses, not markup', 'testing (chapter 13)'),
            ],
            'notes': [
                '@angular/aria (stable since v22) goes further with ready behaviour directives:',
                'accordion, combobox, grid, listbox, menu, tabs, toolbar, tree',
            ],
        },
    },
    'defer-triggers': {
        'ru': {
            'title': '@defer: когда подгружать блок',
            'rows': [
                ('триггер', 'что означает', 'типичный случай'),
                ('on idle', 'браузер освободился (по умолчанию)', 'всё, что ниже первого экрана'),
                ('on viewport', 'блок попал в область видимости', 'графики, комментарии'),
                ('on interaction', 'клик или keydown по элементу', 'редактор, тяжёлая форма'),
                ('on hover', 'наведение мыши или фокус', 'превью, тултип с данными'),
                ('on timer(2s)', 'через заданное время', 'баннер, подсказка'),
                ('on immediate', 'сразу после основного рендера', 'разгрузить initial-бандл'),
                ('when expr', 'условие стало истинным', 'по роли, по фича-флагу'),
                ('prefetch on idle', 'код скачать заранее, не показывать', 'почти всегда полезно'),
            ],
            'notes': [
                'деферить можно только standalone-зависимости, и только те, на которые',
                'нет прямых ссылок вне блока (иначе они попадут в основной бандл)',
            ],
        },
        'en': {
            'title': '@defer: when to load the block',
            'rows': [
                ('trigger', 'what it means', 'typical case'),
                ('on idle', 'the browser went idle (the default)', 'anything below the fold'),
                ('on viewport', 'the block entered the viewport', 'charts, comments'),
                ('on interaction', 'a click or keydown on an element', 'an editor, a heavy form'),
                ('on hover', 'mouseover or focusin', 'a preview, a data tooltip'),
                ('on timer(2s)', 'after the given delay', 'a banner, a hint'),
                ('on immediate', 'right after the main render', 'shrink the initial bundle'),
                ('when expr', 'the condition became true', 'by role, by feature flag'),
                ('prefetch on idle', 'fetch the code early, show later', 'almost always worth it'),
            ],
            'notes': [
                'only standalone dependencies can be deferred, and only those with no',
                'direct references outside the block (otherwise they join the main bundle)',
            ],
        },
    },
    'perf-checklist': {
        'ru': {
            'title': 'Где искать причину, когда «Angular тормозит»',
            'rows': [
                ('симптом', 'частая причина', 'чем смотреть'),
                ('список дёргается при обновлении', 'track по индексу или по объекту', 'DevTools Profiler'),
                ('лаг на каждый ввод символа', 'метод или impure-пайп в шаблоне', 'Profiler: время проверки'),
                ('проверок больше, чем изменений', 'Eager-компонент в горячем пути', 'Profiler: счётчик циклов'),
                ('долгий первый рендер', 'весь код в initial-бандле', 'stats.json + esbuild analyze'),
                ('скачет вёрстка при загрузке', 'нет width/height у картинок', 'Lighthouse: CLS'),
                ('тормозит скролл длинного списка', 'нет виртуализации', 'Performance-профиль браузера'),
            ],
            'notes': [
                'сначала измерение, потом оптимизация: половина «оптимизаций» на глаз',
                'усложняет код, не меняя ни одного числа',
            ],
        },
        'en': {
            'title': 'Where to look when "Angular is slow"',
            'rows': [
                ('symptom', 'the usual cause', 'the tool'),
                ('the list jumps on refresh', 'track by index or by object', 'DevTools Profiler'),
                ('lag on every keystroke', 'a method or impure pipe in a template', 'Profiler: check duration'),
                ('more checks than changes', 'an Eager component on a hot path', 'Profiler: cycle count'),
                ('slow first render', 'all the code in the initial bundle', 'stats.json + esbuild analyze'),
                ('layout jumps while loading', 'images without width/height', 'Lighthouse: CLS'),
                ('scrolling a long list stutters', 'no virtual scrolling', "the browser's performance profile"),
            ],
            'notes': [
                'measure first, optimize second: half of all eyeballed "optimizations"',
                'complicate the code without moving a single number',
            ],
        },
    },
    'budget-types': {
        'ru': {
            'rows': [
                ('тип бюджета', 'что измеряет', 'зачем следить'),
                ('initial', 'всё, что грузится до первого рендера', 'главная метрика старта'),
                ('bundle (+ name)', 'конкретный бандл по имени', 'ленивый раздел не распух'),
                ('anyComponentStyle', 'любой один файл стилей компонента', 'ловит случайный импорт темы'),
                ('anyScript / allScript', 'любой один / все скрипты', 'общий потолок JS'),
                ('any / all', 'любой один / все файлы вывода', 'картинки, шрифты, шаблоны'),
            ],
        },
        'en': {
            'rows': [
                ('budget type', 'what it measures', 'why watch it'),
                ('initial', 'everything loaded before first render', 'the key startup metric'),
                ('bundle (+ name)', 'one named bundle', 'a lazy section staying slim'),
                ('anyComponentStyle', 'any single component stylesheet', 'catches an accidental theme import'),
                ('anyScript / allScript', 'any one / all scripts', 'an overall JS ceiling'),
                ('any / all', 'any one / all output files', 'images, fonts, templates'),
            ],
        },
    },
    'test-pyramid': {
        'ru': {
            'title': 'Что чем тестировать в Angular-приложении',
            'rows': [
                ('что тестируем', 'инструмент', 'нужен ли TestBed'),
                ('сигнальный стор, команды', 'обычный юнит-тест', 'нет: new Store() или inject'),
                ('чистая функция, пайп', 'обычный юнит-тест', 'нет'),
                ('компонент и его шаблон', 'TestBed + fixture', 'да'),
                ('HTTP-слой и интерсепторы', 'provideHttpClientTesting', 'да'),
                ('гард, резолвер', 'TestBed.runInInjectionContext', 'да'),
                ('сценарий пользователя', 'Playwright / Cypress', 'нет: настоящий браузер'),
            ],
            'notes': [
                'чем меньше TestBed, тем быстрее и стабильнее набор тестов:',
                'логику выносят в сервисы именно поэтому (глава 05)',
            ],
        },
        'en': {
            'title': 'What to test with what in an Angular app',
            'rows': [
                ('what you test', 'the tool', 'is TestBed needed'),
                ('a signal store, its commands', 'a plain unit test', 'no: new Store() or inject'),
                ('a pure function, a pipe', 'a plain unit test', 'no'),
                ('a component and its template', 'TestBed + fixture', 'yes'),
                ('the HTTP layer and interceptors', 'provideHttpClientTesting', 'yes'),
                ('a guard, a resolver', 'TestBed.runInInjectionContext', 'yes'),
                ('a user journey', 'Playwright / Cypress', 'no: a real browser'),
            ],
            'notes': [
                'the less TestBed, the faster and steadier the suite:',
                'that is exactly why logic moves into services (chapter 05)',
            ],
        },
    },
    'testbed-flow': {
        'ru': {
            'title': 'Тест компонента: порядок шагов',
            'steps': [
                {
                    'lines': [
                        'TestBed.configureTestingModule({ providers: [...] })',
                        'здесь подменяются зависимости: useValue с моком вместо API',
                    ]
                },
                {
                    'edge': 'создание',
                    'lines': [
                        'const fixture = TestBed.createComponent(TicketList)',
                        'инстанс создан, шаблон ещё не проверялся',
                    ],
                },
                {
                    'edge': 'входы',
                    'lines': [
                        "fixture.componentRef.setInput('ticket', ticket)",
                        'setInput помечает компонент изменённым (глава 11)',
                    ],
                },
                {
                    'edge': 'синхронизация',
                    'lines': [
                        'await fixture.whenStable()',
                        'ждём проверку шаблона и микротаски,',
                        'вместо ручного detectChanges()',
                    ],
                },
                {
                    'edge': 'проверка',
                    'lines': [
                        'expect(...) по DOM, harness или сигналам',
                        'httpTesting.verify() в afterEach',
                    ],
                },
            ],
            'notes': [
                'fakeAsync/tick НЕ работают с ранером Vitest: zone.js там не патчится,',
                'и документация больше не рекомендует fakeAsync',
            ],
        },
        'en': {
            'title': 'A component test: the order of steps',
            'steps': [
                {
                    'lines': [
                        'TestBed.configureTestingModule({ providers: [...] })',
                        'dependencies are swapped here: useValue with a mock instead of the API',
                    ]
                },
                {
                    'edge': 'creation',
                    'lines': [
                        'const fixture = TestBed.createComponent(TicketList)',
                        'the instance exists, the template has not been checked yet',
                    ],
                },
                {
                    'edge': 'inputs',
                    'lines': [
                        "fixture.componentRef.setInput('ticket', ticket)",
                        'setInput marks the component as changed (chapter 11)',
                    ],
                },
                {
                    'edge': 'sync',
                    'lines': [
                        'await fixture.whenStable()',
                        'wait for the template check and microtasks',
                        'instead of a manual detectChanges()',
                    ],
                },
                {
                    'edge': 'assert',
                    'lines': [
                        'expect(...) on the DOM, a harness or signals',
                        'httpTesting.verify() in afterEach',
                    ],
                },
            ],
            'notes': [
                'fakeAsync/tick do NOT work with the Vitest runner: zone.js is not patched there,',
                'and the documentation no longer recommends fakeAsync',
            ],
        },
    },
    'testing-comparison': {
        'ru': {
            'rows': [
                ('задача', 'React: Jest/Vitest + RTL', 'Angular: TestBed'),
                ('подменить зависимость', 'jest.mock модуля', 'провайдер в TestBed'),
                ('отрендерить компонент', 'render(<Cmp prop={x} />)', 'createComponent + setInput'),
                ('дождаться обновления', 'await waitFor(...)', 'await fixture.whenStable()'),
                ('найти элемент', 'screen.getByRole(...)', 'harness или DebugElement'),
                ('замокать сеть', 'msw / fetch-mock', 'provideHttpClientTesting'),
                ('проверить состояние', 'через DOM', 'через DOM или сигналы напрямую'),
            ],
        },
        'en': {
            'rows': [
                ('the task', 'React: Jest/Vitest + RTL', 'Angular: TestBed'),
                ('swap a dependency', 'jest.mock on the module', 'a provider in TestBed'),
                ('render a component', 'render(<Cmp prop={x} />)', 'createComponent + setInput'),
                ('wait for an update', 'await waitFor(...)', 'await fixture.whenStable()'),
                ('find an element', 'screen.getByRole(...)', 'a harness or DebugElement'),
                ('mock the network', 'msw / fetch-mock', 'provideHttpClientTesting'),
                ('assert state', 'through the DOM', 'through the DOM or signals directly'),
            ],
        },
    },
    'feature-layout': {
        'ru': {
            'title': 'Структура по фичам: Support Desk',
            'rows': [
                ('src/app/', ''),
                ('├── app.ts, app.config.ts, app.routes.ts', 'точка входа и корневые провайдеры'),
                ('├── core/', 'то, что нужно ВСЕМУ приложению'),
                ('│   ├── app-config.ts', 'InjectionToken конфига (глава 04)'),
                ('│   ├── interceptors.ts', 'auth, logging, errors (глава 08)'),
                ('│   └── auth-store.ts', 'текущий пользователь и роли'),
                ('├── ui/', 'переиспользуемые компоненты БЕЗ домена'),
                ('│   ├── data-table/', 'не знает про тикеты (глава 11)'),
                ('│   └── modal/', ''),
                ('└── tickets/', 'фича: всё про тикеты в одном месте'),
                ('    ├── ticket.ts', 'модель домена'),
                ('    ├── ticket-api.ts', 'HTTP-слой фичи'),
                ('    ├── ticket-store.ts', 'состояние домена (глава 05)'),
                ('    ├── ticket-list/', 'экран: компонент + шаблон + стили + тест'),
                ('    ├── ticket-detail/', ''),
                ('    └── ticket-form/', ''),
            ],
        },
        'en': {
            'title': 'Feature-based layout: Support Desk',
            'rows': [
                ('src/app/', ''),
                ('├── app.ts, app.config.ts, app.routes.ts', 'entry point and root providers'),
                ('├── core/', 'what the WHOLE application needs'),
                ('│   ├── app-config.ts', 'the config InjectionToken (chapter 04)'),
                ('│   ├── interceptors.ts', 'auth, logging, errors (chapter 08)'),
                ('│   └── auth-store.ts', 'the current user and roles'),
                ('├── ui/', 'reusable components with NO domain'),
                ('│   ├── data-table/', 'knows nothing about tickets (chapter 11)'),
                ('│   └── modal/', ''),
                ('└── tickets/', 'the feature: everything ticket-related'),
                ('    ├── ticket.ts', 'the domain model'),
                ('    ├── ticket-api.ts', "the feature's HTTP layer"),
                ('    ├── ticket-store.ts', 'domain state (chapter 05)'),
                ('    ├── ticket-list/', 'a screen: component + template + styles + test'),
                ('    ├── ticket-detail/', ''),
                ('    └── ticket-form/', ''),
            ],
        },
    },
    'shared-problems': {
        'ru': {
            'title': 'Почему core/shared превращается в свалку',
            'rows': [
                ('что складывают', 'чем это плохо', 'куда должно уехать'),
                ('shared/components', 'домен просачивается в общий слой', 'ui/ — только без домена'),
                ('shared/utils.ts', 'файл-помойка, никто не чистит', 'рядом с тем, кто использует'),
                ('shared/models', 'все фичи зависят от всех типов', 'модель — в свою фичу'),
                ('shared/services', 'сервис фичи виден всем', 'в фичу, если он про неё'),
                ('core/ всё подряд', 'core растёт быстрее фич', 'core — только общее для всех'),
            ],
            'notes': [
                'style guide прямо советует организовывать по фичам и НЕ создавать папки',
                'по типам кода (components, directives, services), а также избегать utils.ts',
            ],
        },
        'en': {
            'title': 'Why core/shared turns into a dumping ground',
            'rows': [
                ('what goes in', 'why it hurts', 'where it belongs'),
                ('shared/components', 'domain leaks into the shared layer', 'ui/ — domain-free only'),
                ('shared/utils.ts', 'a junk drawer nobody cleans', 'next to whoever uses it'),
                ('shared/models', 'every feature depends on every type', 'the model lives in its feature'),
                ('shared/services', "a feature's service becomes global", 'in the feature it belongs to'),
                ('core/ everything', 'core grows faster than features', 'core = truly app-wide only'),
            ],
            'notes': [
                'the style guide explicitly says to organize by feature and NOT to create',
                'directories by code type (components, directives, services), and to avoid utils.ts',
            ],
        },
    },
    'reading-checklist': {
        'ru': {
            'title': 'Чеклист: как читать незнакомый Angular-проект',
            'rows': [
                ('вопрос', 'где смотреть', 'что это скажет'),
                ('какая версия и что мигрировано', 'package.json, angular.json', 'поколение API'),
                ('zone.js есть?', 'package.json, polyfills', 'zoneless или нет (глава 03)'),
                ('как стартует приложение', 'main.ts', 'bootstrapApplication или модуль'),
                ('что провайдится глобально', 'app.config.ts или AppModule', 'HTTP, роутер, интерсепторы'),
                ('карта экранов', 'app.routes.ts', 'фичи, ленивые границы, гарды'),
                ('где состояние', 'сервисы с signal/BehaviorSubject', 'модель состояния (глава 05)'),
                ('как ходят в сеть', 'HttpClient, httpResource, интерсепторы', 'слой данных (глава 08)'),
                ('насколько живы тесты', 'runner в angular.json, *.spec.ts', 'можно ли рефакторить'),
            ],
            'notes': [
                'этот же порядок работает как план ответа на собеседовании,',
                'когда спрашивают "как бы вы разбирались в незнакомом проекте"',
            ],
        },
        'en': {
            'title': 'Checklist: how to read an unfamiliar Angular project',
            'rows': [
                ('the question', 'where to look', 'what it tells you'),
                ('which version, what was migrated', 'package.json, angular.json', 'the API generation'),
                ('is zone.js present?', 'package.json, polyfills', 'zoneless or not (chapter 03)'),
                ('how the app boots', 'main.ts', 'bootstrapApplication or a module'),
                ('what is provided globally', 'app.config.ts or AppModule', 'HTTP, router, interceptors'),
                ('the map of screens', 'app.routes.ts', 'features, lazy borders, guards'),
                ('where state lives', 'services with signal/BehaviorSubject', 'the state model (chapter 05)'),
                ('how it talks to the network', 'HttpClient, httpResource, interceptors', 'the data layer (chapter 08)'),
                ('how alive the tests are', 'the runner in angular.json, *.spec.ts', 'whether refactoring is safe'),
            ],
            'notes': [
                'the same order works as an interview answer when you are asked',
                'how you would find your way around an unfamiliar project',
            ],
        },
    },
    'render-modes': {
        'ru': {
            'title': 'Режимы рендеринга: что выбрать для маршрута',
            'rows': [
                ('RenderMode', 'когда HTML собирается', 'для чего подходит'),
                ('Client', 'в браузере (поведение по умолчанию)', 'админка, приватные экраны'),
                ('Server', 'на сервере на каждый запрос', 'персональные данные, SEO'),
                ('Prerender', 'на сборке, статический файл', 'лендинг, документация, блог'),
            ],
            'notes': [
                'outputMode: static — только пререндер, серверного файла нет;',
                'outputMode: server — нужен рантайм, деплой уже не на статику',
            ],
        },
        'en': {
            'title': 'Render modes: what to pick for a route',
            'rows': [
                ('RenderMode', 'when the HTML is produced', 'what it suits'),
                ('Client', 'in the browser (the default behaviour)', 'admin panels, private screens'),
                ('Server', 'on the server, per request', 'personalized data, SEO'),
                ('Prerender', 'at build time, a static file', 'landing pages, docs, a blog'),
            ],
            'notes': [
                'outputMode: static — prerender only, no server file;',
                'outputMode: server — a runtime is required, so no static hosting',
            ],
        },
    },
    'security-layers': {
        'ru': {
            'title': 'Что Angular защищает сам, а что на вас',
            'rows': [
                ('контекст', 'что делает Angular', 'что делаете вы'),
                ('интерполяция {{ }}', 'экранирует всё как текст', 'ничего'),
                ('[innerHTML]', 'санитизирует HTML', 'не звать bypassSecurityTrustHtml'),
                ('[href], [src]', 'санитизирует URL', 'валидировать схему для чужих ссылок'),
                ('resource URL (script src)', 'НЕ санитизирует: там код', 'не строить из пользовательских данных'),
                ('nativeElement.innerHTML', 'не участвует вовсе', 'не использовать (глава 06)'),
                ('CSP', 'nonce через ngCspNonce/CSP_NONCE', 'уникальный nonce на запрос'),
            ],
            'notes': [
                'security.autoCsp в angular.json генерирует hash-based strict CSP;',
                'по умолчанию выключен — пока это preview-возможность',
            ],
        },
        'en': {
            'title': 'What Angular protects and what is on you',
            'rows': [
                ('context', 'what Angular does', 'what you do'),
                ('interpolation {{ }}', 'escapes everything as text', 'nothing'),
                ('[innerHTML]', 'sanitizes the HTML', 'never call bypassSecurityTrustHtml'),
                ('[href], [src]', 'sanitizes the URL', 'validate the scheme for foreign links'),
                ('resource URL (script src)', 'does NOT sanitize: it is code', 'never build it from user data'),
                ('nativeElement.innerHTML', 'not involved at all', 'do not use it (chapter 06)'),
                ('CSP', 'nonce via ngCspNonce/CSP_NONCE', 'a unique nonce per request'),
            ],
            'notes': [
                'security.autoCsp in angular.json generates a hash-based strict CSP;',
                'off by default — it is still a preview capability',
            ],
        },
    },
    'senior-polish': {
        'ru': {
            'title': 'Чеклист senior polish: что смотрят в вашем проекте',
            'rows': [
                ('что проверяют', 'признак «сделано»'),
                ('современная модель', 'сигналы, standalone, inject, control flow'),
                ('нет утечек механизма', 'ни одного effect для производных значений'),
                ('состояние честно разделено', 'домен в сервисе, экран — в сторе экрана'),
                ('ошибки обработаны по уровням', '401/5xx в интерсепторе, 404/422 на экране'),
                ('код разбит', 'ленивые маршруты + @defer, бюджеты в CI'),
                ('тесты, которые ловят баги', 'whenStable, harness, без fakeAsync'),
                ('доступность', 'роли, фокус, клавиатура, aria у контролов'),
                ('README и ARCHITECTURE', 'что демонстрирует проект и как он устроен'),
            ],
            'notes': [
                'на собеседовании ценится не размер проекта, а способность объяснить',
                'каждое решение и назвать альтернативу, которую вы отвергли',
            ],
        },
        'en': {
            'title': 'The senior-polish checklist: what people look at',
            'rows': [
                ('what is checked', 'the "done" signal'),
                ('the modern model', 'signals, standalone, inject, control flow'),
                ('no mechanism leaks', 'not a single effect for derived values'),
                ('state split honestly', 'domain in a service, screen state in a screen store'),
                ('errors handled per level', '401/5xx in an interceptor, 404/422 on the screen'),
                ('code split', 'lazy routes + @defer, budgets in CI'),
                ('tests that catch bugs', 'whenStable, harnesses, no fakeAsync'),
                ('accessibility', 'roles, focus, keyboard, aria on controls'),
                ('README and ARCHITECTURE', 'what the project demonstrates and how it is built'),
            ],
            'notes': [
                'interviews value not the size of the project but your ability to explain',
                'every decision and name the alternative you rejected',
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
