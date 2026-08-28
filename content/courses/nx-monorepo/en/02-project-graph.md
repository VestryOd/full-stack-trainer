# The project graph: how Nx sees the repository

## Theory

### The graph is built from code, not from declarations

The project graph is the data structure everything else stands on. On it sit the task pipeline (chapter 03), the cache (chapter 04), affected (chapter 05) and boundaries (chapter 06). We covered the nodes in chapter 01 (project.json / package.json / plugin createNodes). This chapter is about the **edges**.

The key fact that separates Nx from Turborepo and Lerna: the `shell → shared-ui` edge exists because **the shell sources contain an import from shared-ui**. Not because someone wrote the dependency into a package.json. The mechanics, step by step:

```
┌───────────────────────────────────────────┐
│ source files of every project             │
│ *.ts / *.tsx / *.js                       │
└───────────────────────────────────────────┘
                      │
                      ▼
┌───────────────────────────────────────────┐
│ import parsing (syntax tree, not grep):   │
│ import / require / import()               │
└───────────────────────────────────────────┘
                      │
                      ▼
┌───────────────────────────────────────────┐
│ resolving each import to a project:       │
│ path aliases / workspaces / package names │
└───────────────────────────────────────────┘
                      │
                      ▼
┌───────────────────────────────────────────┐
│ graph edges                               │
│ + implicitDependencies from project.json  │
└───────────────────────────────────────────┘
```

Breaking down each step:

- **Parsing goes through the AST (abstract syntax tree — the parsed, tree-shaped form of the code), not through a text search.** Nx walks the file's syntax tree and collects `import ... from`, `export ... from`, `require(...)` and dynamic `import(...)`. A path mentioned in a string literal or a comment creates no edge. But `import type` does create one: to Nx it's an import like any other. That is right, because a change to a library's types must affect its consumers — otherwise affected would let broken typing through.
- **Resolving to a project.** The specifier is the string inside the import, for example `@mini-shop/shared-ui`. Nx runs it through `paths` from `tsconfig.base.json` (integrated) or through package manager workspaces (package-based), and it lands inside some project's root. If it lands nowhere, it is an npm package and becomes an external node.
- **Edge types**: `static` (a regular import), `dynamic` (`import()` — important for microfrontends, chapter 10) and `implicit` (below).

> **Versions.** In recent versions import parsing and hashing moved to native Rust code — on a repo with hundreds of projects the graph builds in seconds. For you it's a performance detail: the mechanics are the same as before.

Recomputing the graph on every run would be expensive, so Nx keeps a **daemon** — a background process that watches files and updates the graph incrementally. The serialized graph lives in `.nx/workspace-data`.

Hence the main diagnostic move. If the graph behaves strangely — an edge didn't appear, or didn't disappear — run `npx nx reset`. It kills the daemon and wipes all derived data, and the next command rebuilds the graph from scratch.

### implicitDependencies — edges that don't exist in code

Sometimes a dependency is real but not expressed by an import:

- an e2e (end-to-end — tests that drive the whole running app) project tests an application. The e2e code imports nothing from the app; it only knows the app's URL;
- a project reads another project's generated artifact;
- a deploy config depends on a built bundle.

For that, project.json supports a manual edge:

```json
{
  "name": "shell-e2e",
  "implicitDependencies": ["shell"]
}
```

Now a change to shell makes `shell-e2e` "affected", even though static analysis sees no connection. It's a surgical tool: if a repo has dozens of implicitDependencies, the team is fighting the graph instead of expressing dependencies in code.

### npm packages are nodes too

External dependencies exist in the graph as nodes like `npm:react`. The `shared-ui → npm:react` edge means "shared-ui sources import react". Nx needs this for two things:

- the external dependency's version is part of the cache hash. Bump react, and the build cache of everyone who imports it is invalidated (chapter 04);
- the command `nx graph` can show who in the repo actually uses a given package — by imports, not by package.json.

After this chapter the mini-shop graph looks like this:

```
┌────────────┐  static  ┌────────────────┐  static  ┌───────────┐
│ apps/shell │ ───────▶ │ libs/shared/ui │ ───────▶ │ npm:react │
└────────────┘          └────────────────┘          └───────────┘
```

### nx graph — the main navigation tool

`npx nx graph` starts a local web interface. The modes worth using deliberately:

- **Focus** (`nx graph --focus=shell` or a click in the interface) — only the selected project and its direct/transitive connections. On a 200-project repo "Select all" is useless — focus is mandatory.
- **Path tracing** — pick two projects in the interface and Nx shows every path between them. The answer to the classic "why did changing library X retest application Y".
- **`nx graph --file=graph.json`** — the same graph as JSON for scripting. Count incoming edges, find the most depended-upon node, or check an architectural rule in CI (continuous integration — build and test on every push).
- **`nx graph --affected`** — the subgraph touched by your changes (chapter 05).

## In a real-world monorepo

- `npx nx graph` → focus on the project you're working on: its real dependencies and dependents in 10 seconds, without reading code.
- Path tracing between "my lib" and "the production app" shows which layers a change travels through to reach a deploy. It also answers "why did my PR (pull request) trigger 40 test jobs".
- `npx nx graph --file=graph.json` — the whole graph as JSON. The script below prints the top 10 nodes by incoming edges. Those are the projects at the center of the repo, and the most dangerous to touch.
- `grep -rn "implicitDependencies" --include=project.json .` — every manual edge in the repo. Each one should have a clear reason; a pile of implicitDependencies is a symptom that the graph doesn't reflect reality.
- The graph "lies" — you removed an import but the edge is still there? Run `npx nx reset`, then `nx graph` again. Nine times out of ten it's a stale daemon.

```bash
npx nx graph --file=graph.json
python3 - <<'PY'
import json, collections
deps = json.load(open('graph.json'))['graph']['dependencies']
print(collections.Counter(t['target'] for v in deps.values() for t in v).most_common(10))
PY
```

## What we're adding to the project

The first library — `shared/ui` with a `Button` component. Shell stops being the only node, the graph gets its first edge, and `tsconfig.base.json` gets its first alias. This is the foundation for the layered refactoring in chapter 06.

## Practical exercise

**Input:** the workspace after chapter 01 (the shell app, @nx/react + vite plugins).

**Task:**

1. Generate a React library `shared-ui` in `libs/shared/ui`: bundler — none (why none is a chapter 06 topic), tests — vitest, import path — `@mini-shop/shared-ui`.
2. Add a `Button` component to the lib (a plain button with `variant: 'primary' | 'ghost'`) and export it through the public entry `src/index.ts`.
3. Use `Button` in the shell's `app.tsx`. Make sure `nx serve shell` renders the button.
4. Verify the edge three ways. In the `nx graph` interface. In `nx graph --file=graph.json`, where you find the shell entry. And with your own eyes, in the `tsconfig.base.json` diff.
5. Break the connection: comment out the import in app.tsx — and confirm the edge is gone. Bring the import back.
6. Add `implicitDependencies: ["shared-ui"]` to `shell`, check the edge type in graph.json, then remove it.

**Edge cases to think about:**

- If you replace the import with `import type { ButtonProps } ...` — does the edge stay? Should it?
- What happens to the graph if you import Button by a relative path `../../../libs/shared/ui/src/lib/button`, bypassing the alias? Why is that bad if "it works"?
- Can shared-ui import something from shell? What would the graph say, and what should code review say?

## Worked solution

Generating the lib:

```bash
npx nx g @nx/react:lib shared-ui --directory=libs/shared/ui \
  --bundler=none --unitTestRunner=vitest --linter=eslint \
  --importPath=@mini-shop/shared-ui
```

The `tsconfig.base.json` diff — the first alias (this is the wiring the import resolves through):

```json
{
  "compilerOptions": {
    "paths": {
      "@mini-shop/shared-ui": ["libs/shared/ui/src/index.ts"]
    }
  }
}
```

The component and the public entry:

```tsx
// libs/shared/ui/src/lib/button.tsx
import type { ReactNode } from 'react';

export interface ButtonProps {
  variant?: 'primary' | 'ghost';
  onClick?: () => void;
  children: ReactNode;
}

export function Button({ variant = 'primary', onClick, children }: ButtonProps) {
  return (
    <button className={`btn btn-${variant}`} onClick={onClick}>
      {children}
    </button>
  );
}
```

```ts
// libs/shared/ui/src/index.ts — the lib's PUBLIC API:
// only what is exported from here is available to other projects
export { Button } from './lib/button';
export type { ButtonProps } from './lib/button';
```

Using it in shell:

```tsx
// apps/shell/src/app/app.tsx
import { Button } from '@mini-shop/shared-ui';

export function App() {
  return (
    <div>
      <h1>mini-shop</h1>
      <Button onClick={() => console.log('go to catalog')}>Catalog</Button>
    </div>
  );
}

export default App;
```

Checking the edge in JSON:

```bash
npx nx graph --file=graph.json
python3 - <<'PY'
import json
g = json.load(open('graph.json'))['graph']
print(g['dependencies']['shell'])
PY
# [{'source': 'shell', 'target': 'shared-ui', 'type': 'static'},
#  {'source': 'shell', 'target': 'npm:react', 'type': 'static'}, ...]
```

Key decisions:

- The `shell → shared-ui` edge appeared the moment the import line appeared in app.tsx. We didn't edit a single dependency config — that's the point of the chapter.
- `src/index.ts` is the single entry point — a barrel file, meaning one file that re-exports everything the lib offers. The alias in tsconfig.base.json points at this file, not at the folder. Anything not re-exported from index.ts stays private to the lib. For now this is only an agreement between people; in chapter 06 we turn it into a lint rule.
- After commenting out the import, the edge disappears on the next graph computation, because the daemon picks up the file change. If an open `nx graph` still shows the old picture, refresh the page — worst case, run `nx reset`.
- With `implicitDependencies: ["shared-ui"]`, graph.json gains an edge with `{'type': 'implicit'}` — it survives even when there's no import. The real use case is e2e → app; for an ordinary "code imports code" relationship an implicit edge is redundant, so we remove it.

Answers to the edge cases:

- `import type` keeps the edge — and must: change `ButtonProps` → shell has to land in affected, otherwise CI misses broken typing.
- A relative import bypassing the alias also creates the edge, because the resolver understands relative paths. But it punches through the public API: you've attached yourself to the lib's internal file, past index.ts. Now refactoring the lib's internals breaks someone else's code. In chapter 06, `@nx/enforce-module-boundaries` will forbid such imports.
- Technically `shared-ui → shell` is possible, and the graph will dutifully draw the `shell ⇄ shared-ui` cycle. But the task pipeline (chapter 03) breaks on a cycle, and rightly so. A library that knows about an application is inverted architecture. Code review should reject that import before Nx ever gets involved.

## Check yourself

1. Describe the full path from the line `import { Button } from '@mini-shop/shared-ui'` in app.tsx to the `shell → shared-ui` edge in the graph. Which files participate in the resolution?
2. Why does `import type` create an edge even though such an import vanishes from the bundle without a trace? Tie the answer to affected.
3. An e2e project has no imports from the application it tests. How do you express the dependency, and why would affected skip e2e on app changes without it?
4. Why does a repeated `nx graph` open instantly even though the repo is big? Who keeps the graph up to date, where does it live on disk, and which command resets it?
5. Why are npm packages present in the graph as separate nodes? Name two Nx mechanisms that need edges to `npm:*`.

<details>
<summary>Answers</summary>

1. Nx (via the daemon) parses the AST of app.tsx and finds the import specifier `@mini-shop/shared-ui`. The resolver runs it through `paths` in `tsconfig.base.json` and gets `libs/shared/ui/src/index.ts`. That path lies inside the root of the `shared-ui` project, whose node is known from the lib's project.json. So a file of project `shell` depends on project `shared-ui`, and a `static` edge `shell → shared-ui` is added to the graph. Participants: the app.tsx source, tsconfig.base.json (paths), and both project.json files (project boundaries).
2. A graph edge answers not "what ends up in the bundle" but "whose change affects me". A change to `ButtonProps` in shared-ui can break the shell compilation without changing a single runtime byte — affected must recheck shell (typecheck, tests). If type imports were ignored, CI would stay green on a repo that doesn't compile.
3. Write `implicitDependencies: ["shell"]` in the e2e project's project.json. It is a manual edge for relationships not expressed by imports: the e2e code reaches the app by its URL and imports nothing. Without it the graph sees e2e as an isolated node. A change to shell doesn't make e2e affected, and the affected-based CI pipeline silently skips the regression e2e was supposed to catch.
4. The graph isn't recomputed from scratch. The daemon watches the file system and updates the graph incrementally on changes, and the serialized state lives in `.nx/workspace-data`. So any command starts from a ready-made graph. The reset is `nx reset`: it kills the daemon and wipes derived data. The next command rebuilds everything — the first move when "the graph lies".
5. First, the cache: an npm package's version is a hash input (chapter 04). Bumping react must invalidate the builds of everyone who imports it, and that requires `project → npm:react` edges. Second, usage analysis: `nx graph` shows a package's actual consumers by imports rather than declarations. That is the precise answer to "can we drop dependency X".

</details>

## Common mistake

A developer from the single-app world arrives with the belief that "a dependency exists only if it's declared". They look for where shared-ui is "connected" to shell and find no entry in any package.json. From there they go one of two ways.

The first way is to add a declaration by hand: a redundant implicitDependencies, or a package.json entry duplicating what the graph already knows. The second is to decide the opposite. Since nothing needs declaring, there is no order at all. They start importing anything from anyone's libs, like this: `import { helper } from '../../../libs/checkout/feature/src/lib/internal/utils'`.

The graph will digest that, and the edge appears. But this is a **deep import** — an import that reaches inside a lib, past its public entry. It is attached to an internal file. The lib's owner reshuffles files and breaks half the repo, without changing a single export from index.ts.

The correct mental model is the inverse: **the import is the declaration**. Edges are created by code. The file index.ts is the contract, and inside that contract the lib is free. An implicitDependencies entry is an exception justified in review, not an everyday tool. Do you find yourself wanting an edge without an import, or an import past index.ts? That is almost always a sign the code lives in the wrong lib.
