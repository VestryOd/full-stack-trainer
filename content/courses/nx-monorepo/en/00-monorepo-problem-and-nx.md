# The monorepo problem and where Nx fits

## Theory

### What a monorepo solves — and what it creates

The "polyrepo vs monorepo" debate is often a matter of taste, but underneath it sit three very concrete engineering problems with polyrepo:

1. **Code sharing.** In a polyrepo, shared code (a ui-kit, API contract types, utilities) travels via npm publish: build → bump the version → publish → update every consumer. That is hours or days of delay per change, and at any given moment different apps sit on different versions of the same library.
2. **Atomic changes across boundaries.** You change an API contract — the backend and every frontend consumer must be updated in sync. In a polyrepo that means several PRs in different repos which cannot merge atomically: between merges the system is in an inconsistent state, and no CI catches it.
3. **Single dependency versions.** Five repos means five package.json files, five versions of React, five TypeScript configurations. Upgrading a dependency turns into a quarter-long campaign.

```
 POLYREPO: one repo per app             MONOREPO: a single repository
┌────────────┐ ┌───────────┐            ┌─────────────────────────┐
│ shop-web   │ │ shop-api  │            │ mini-shop/              │
│            │ │           │            │                         │
│ ui-kit@1.2 │ │ types@2.1 │            │ apps/  shell · catalog  │
│ types@1.8  │ │           │            │        checkout · api   │
└────────────┘ └───────────┘            │ libs/  shared/ui        │
code is shared via npm publish;         │        shared/api-types │
versions drift, one contract change     └─────────────────────────┘
means several PRs and releases          one import graph, single dep versions,
                                        atomic PRs across project boundaries
```

A monorepo solves all three at the cost of two new problems, both about scale:

- **Build and test time grows linearly with repo size.** A naive CI script of "build and test everything" across 50 projects means hours per PR, even when the PR touches one file in one library.
- **Dependency chaos.** When all the code lives in one repo and anything can import anything, a year later you have a big ball of mud where every library depends on every other one.

These two problems are exactly what Nx solves. Everything else (generators, migrations, plugins) is useful tooling around the edges, but the core value is **never rebuilding what didn't change** (computation caching + affected) and **keeping boundaries enforced** (project graph + module boundaries).

### Where Nx sits among the alternatives

Think in layers. Package manager workspaces (npm/pnpm/yarn) solve dependency installation only: one `node_modules`, local packages reachable from each other via symlinks. They know nothing about *what depends on what at the task level* or *what needs rebuilding*.

```
┌─────────────────────────────────────────────────┐
│ plugins: @nx/react, @nx/node, @nx/eslint, ...   │
│ generators · executors · inferred targets       │
├─────────────────────────────────────────────────┤
│ Nx core: project graph · task pipeline          │
│ computation cache · affected                    │
├─────────────────────────────────────────────────┤
│ package manager workspaces (npm/pnpm/yarn):     │
│ dependency install, package symlinks            │
├─────────────────────────────────────────────────┤
│ a plain git repository: apps/ · libs/ · nx.json │
└─────────────────────────────────────────────────┘
```

- **Lerna** — historically the first popular tool, focused on versioning and publishing packages. Since 2022 Lerna is maintained by the Nx team and delegates task running to Nx under the hood.
- **Turborepo** — a task runner plus cache on top of a package-based monorepo. Conceptually close to the Nx core, but its graph is built from `package.json` dependencies (not from import analysis), and there is no layer of generators, plugins, or boundary rules.
- **Nx** adds on top: a **project graph built by static import analysis** (chapter 02), **computation caching** with a precise inputs/outputs model (chapter 04), **affected** (chapter 05), **generators and migrations** (chapter 07), **module boundaries** via ESLint (chapter 06), and plugins that understand specific tools (webpack, vite, jest, playwright).

The key everyday difference between Nx and Turborepo: Nx sees the `shell → shared/ui` dependency even when it exists only as a TS import, with no package.json entry. That is more precise and doesn't rely on the discipline of "remember to declare the dependency".

### Integrated vs package-based

A classification from the Nx docs that you'll meet in articles and interviews:

- **Package-based**: every project is a full npm package with its own `package.json` and its own dependencies; projects connect through package manager workspaces. Nx is only a task runner + cache here.
- **Integrated**: a single root `package.json` (single version policy), projects wired together through aliases in `tsconfig.base.json` (`@mini-shop/shared-ui` → `libs/shared/ui/src/index.ts`), and Nx drives everything through plugins and generators.

> **Versions.** In older versions (Nx 15–16) this was a hard fork right in the `create-nx-workspace` wizard: "package-based or integrated?". Since Nx 19–20 the line has blurred: project crystal (plugins infer targets from tool configs on their own — chapter 01) made the integrated mode as lightweight as package-based, and the new TS preset (Nx 20+) defaults to package manager workspaces + TypeScript project references instead of `tsconfig.base.json` aliases. In a real work project started on Nx 15–17 you will almost certainly see the classic integrated setup with `tsconfig.base.json`; in a freshly created one — possibly the new style. Being able to recognize both matters more than arguing which one is "correct".

### What Nx is, technically

No magic: `nx` is an ordinary npm package with a CLI, installed into devDependencies. `npx nx build shell` runs the local binary `node_modules/.bin/nx`, which reads `nx.json` plus the project configs, builds the graph, computes hashes and runs tasks. The cache is a plain folder `.nx/cache` on disk (before Nx 17 — `node_modules/.cache/nx`), the graph data lives in `.nx/workspace-data`. All of it can be inspected by hand — which we will do regularly.

## In a real-world monorepo

How to recognize all of the above in an existing workspace you've just been added to:

- `npx nx report` — the first command in an unfamiliar repo: the Nx version, the versions of all `@nx/*` plugins, the package manager. If the plugin versions don't match the nx version, the repo hasn't been migrated in a while (chapter 13).
- `ls` at the root: `nx.json` present — the repo runs on Nx. `apps/` + `libs/` + a `tsconfig.base.json` with a `paths` block — classic integrated. `packages/` + a `workspaces` field in package.json (or `pnpm-workspace.yaml`) with no path aliases — package-based or the new TS preset.
- `cat package.json | head -30` — a single root package.json with all the dependencies = single version policy; if every project has its own package.json with dependencies — package-based.
- `npx nx graph` — opens the interactive graph in a browser: how many projects there are, whether there are islands, what sits in the middle. The first thing worth doing in a new repo right after `nx report`.
- `git log --oneline --follow nx.json | tail -5` — when the repo moved to Nx and what it started from.

## What we're adding to the project

We're starting the course's end-to-end project: an empty `mini-shop` workspace that will grow over 15 chapters into a host + two remote microfrontends + a Node API. In this chapter — only `create-nx-workspace` and a walkthrough of every generated file.

## Practical exercise

**Input:** a machine with Node 20+, an empty directory.

**Task:** create a `mini-shop` workspace with `npx create-nx-workspace@latest` using the empty preset (`apps`), npm as the package manager, without connecting Nx Cloud or CI (that's chapter 13).

**Output:** a git repository with the initial commit made by Nx itself, plus written answers to:

1. Which files were generated at the root, and what is each one for?
2. What is inside `nx.json` right after generation?
3. Where does Nx keep its cache and graph data, and why are those paths in `.gitignore`?
4. How is the `nx` version pinned in package.json — with a range or exactly — and why does it matter?
5. What do `npx nx list` and `npx nx report` show on an empty workspace?

**Edge cases to think about:**

- What happens if you run `create-nx-workspace` inside an already existing git repository?
- How does `nx init` (adding Nx to an existing project) differ from `create-nx-workspace`?
- Why is `nx` installed as a devDependency of the project rather than globally via `npm i -g nx`?

## Worked solution

Creating the workspace (the wizard asks questions; the same answers can be passed as flags to make the result reproducible):

```bash
npx create-nx-workspace@latest mini-shop --preset=apps --pm=npm --nxCloud=skip

cd mini-shop
git log --oneline
# abc1234 Initial commit  ← the commit was made by create-nx-workspace itself
```

> **Versions.** The exact list of wizard questions has changed noticeably between majors: older versions asked "integrated vs package-based", newer ones ask for a stack (None/React/Vue/Node), a bundler, a CI provider. `--preset=apps` is the stable way to get an empty workspace; if your version doesn't support it, the closest equivalent is `--preset=ts`.

What was generated (preset `apps`; the exact set may differ slightly between versions — compare with your own output):

```
mini-shop/
├── apps/            # applications will be generated here (empty for now)
├── nx.json          # configuration of Nx itself
├── package.json     # a SINGLE package.json — single version policy
├── .gitignore       # node_modules, dist, .nx/cache, .nx/workspace-data
├── .prettierrc      # in some versions — prettier out of the box
└── README.md
```

`package.json` — note the exact version pinning:

```json
{
  "name": "@mini-shop/source",
  "version": "0.0.0",
  "license": "MIT",
  "scripts": {},
  "private": true,
  "devDependencies": {
    "@nx/workspace": "21.3.1",
    "nx": "21.3.1"
  }
}
```

Key decisions:

- The `nx` and `@nx/*` versions are pinned **exactly, without `^`** — the generator writes them that way on purpose. The Nx core and its plugins must stay on strictly the same version: a minor-version drift between `nx` and `@nx/react` is a source of hard-to-trace breakage. Upgrades go only through `nx migrate` (chapter 13), which bumps everything in sync.
- `scripts` is empty — and that's fine. In an Nx repo tasks run through `nx <target> <project>`, not npm scripts: an npm script would bypass the graph, the cache and the task pipeline.

`nx.json` right after generation is minimal:

```json
{
  "$schema": "./node_modules/nx/schemas/nx-schema.json",
  "defaultBase": "main"
}
```

- `$schema` gives you IDE autocomplete — useful once we start adding `namedInputs` and `targetDefaults` (chapters 03–04).
- `defaultBase` — the base branch for `nx affected` (chapter 05). In older versions the same setting lived deeper, in `affected.defaultBase`.

Checking the tooling on the empty workspace:

```bash
npx nx report
# NX   Report complete - copy this into the issue template
# Node    : 20.x
# npm     : 10.x
# nx      : 21.3.1
# @nx/workspace : 21.3.1

npx nx list
# only @nx/workspace is installed;
# below it — the list of plugins you COULD add (@nx/react, @nx/node, ...)

npx nx graph
# opens the browser with an empty graph — no projects yet
```

Answers to the edge cases:

- Inside an existing git repo, `create-nx-workspace` creates a **nested** directory with its own `.git` — almost never what you want. For an existing project there is `nx init`: it adds `nx` to devDependencies and generates `nx.json` without touching your structure.
- A global `nx` install is acceptable as a convenience launcher (the global `nx` finds and invokes the **local** version from node_modules), but the source of truth is always the local one: the behaviour of `nx build` must depend on the repo, not on what happens to be installed on a particular developer's machine.

## Check yourself

1. Why does the CI of a naive monorepo ("build and test everything on every PR") degrade linearly as the repo grows, and which two Nx mechanisms break that dependency?
2. How is the Nx project graph fundamentally different from what npm/pnpm workspaces know about dependencies? Why aren't symlinks enough to answer "what needs rebuilding?"
3. Which files at the root of an unfamiliar repo let you tell a classic integrated workspace from a package-based one? Why has this dichotomy blurred in recent Nx versions?
4. Why does the generator pin `nx` and `@nx/*` versions exactly, without `^`? What can break if `nx` gets a minor bump while the plugins don't?
5. The build command in an Nx repo is `nx build shell`, not an npm script like `"build": "webpack ..."`. What exactly is lost when you run the tool directly, bypassing Nx?

<details>
<summary>Answers</summary>

1. CI time = (number of projects) × (average build/test time), and the first factor grows with the repo while the size of a single PR's change does not. Nx breaks the dependency with two mechanisms: **affected** shrinks the task list to the projects touched by the change (via the graph), and **computation caching** turns re-runs of untouched work into instant cache hits. Together they make the cost of a PR proportional to the size of the *change*, not the size of the *repository*.
2. Workspaces only know the declarations from `package.json` — "package A is installed and reachable". Nx builds its graph by **static analysis of source imports**: the real `shell → shared/ui` edge exists because the code contains `import ... from '@mini-shop/shared-ui'`, even without a package.json entry. Answering "what needs rebuilding" requires the actual code relationships, not installation declarations — a declared-but-unused dependency causes unnecessary rebuilds, while an undeclared-but-real one (in package-based tools) causes missed ones.
3. Integrated: a single root `package.json` with all the dependencies + a `tsconfig.base.json` with a `paths` alias block + `apps/`/`libs/`. Package-based: `packages/`, each package with its own `package.json` and dependencies, a `workspaces` field (or `pnpm-workspace.yaml`) at the root. It blurred because project crystal removed the main "weight" of integrated (hand-written project.json files with executors), and the new TS preset of Nx 20+ itself uses workspaces + project references — so a modern integrated workspace half-resembles a package-based one.
4. The core (`nx`) and the plugins (`@nx/*`) are one product released in lockstep: plugins call internal core APIs that carry no semver guarantees. With `^`, a routine `npm install` could bump `nx` by a minor while leaving the plugins behind — and `nx build` would start failing with errors deep inside node_modules that have nothing to do with your code. Exact versions + `nx migrate` guarantee the whole set upgrades consistently.
5. Three things: the **cache** (the result won't be saved or reused — locally or in CI), the **task pipeline** (`dependsOn: ["^build"]` won't run — dependencies won't be built before the project), and the **graph/affected** (the run doesn't participate in the "what was touched" model). The tool itself will work, but the repo stops getting the main benefit of Nx; which executor Nx invokes under the hood of the same command is chapter 03.

</details>

## Common mistake

A developer coming from the single-app world brings the reflex "package.json is the project's control center": they add npm scripts like `"build:shell": "nx build shell"`, or worse, `"build": "cd apps/shell && vite build"`, and run everything through `npm run`. The first is a harmless but redundant layer (Nx commands are self-sufficient and parameterizable: `nx build shell --configuration=production`); the second is outright sabotage: calling the tool directly bypasses the cache, the task pipeline and affected, and in CI such a command honestly rebuilds everything from scratch every time, reducing the value of Nx to zero.

The second reflex from the same place is `npm install <pkg>` inside an app's folder "to add a dependency just for it". In an integrated repo this creates a nested package.json and a second node_modules, breaking the single version policy and confusing both Nx and TypeScript. Dependencies in an integrated monorepo are installed at the root — a dependency's "ownership" by a project exists at the graph level (Nx itself sees who imports it), not at the level of a separate node_modules.
