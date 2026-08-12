# Targets, executors and the task pipeline

## Theory

### Terminology: project, target, task

Three words with a strict meaning in Nx. A **target** is a named *capability* of a project ("shell can build, serve, lint"). A **task** is a concrete run: `project:target`, optionally with a configuration: `shell:build:production`. The full run form is `nx run shell:build`; `nx build shell` is its shorthand — they are identical. **Configurations** are named option presets inside a target (`production`/`development`), selected with `--configuration=production` (the `--prod` shorthand still works but is considered legacy).

### The executor: what physically runs a task

An executor is the function Nx hands a task to. The configuration syntax is `package:name`:

- **Specialized ones**: `@nx/vite:build`, `@nx/eslint:lint` — call the tool's API programmatically and support extra options. The main form in pre-crystal repos.
- **`nx:run-commands`** — the universal one: runs an arbitrary shell command. So common that it has sugar: `"command": "tsc --noEmit"` in a target's configuration is the short form of `{"executor": "nx:run-commands", "options": {"command": "tsc --noEmit"}}`.

Crystal plugins (chapter 01) infer targets in exactly this command form: shell's inferred `build` is literally `vite build` with `cwd: apps/shell`. The philosophy: the tool runs through its own native CLI, just as you would run it by hand — Nx wraps it with the graph, the cache and the pipeline.

An executor is code in node_modules, and you can always find it. A package's executor map lives in its `executors.json`:

```bash
cat node_modules/nx/executors.json
# { "executors": { "run-commands": { "implementation": "./src/executors/run-commands/run-commands.impl", ... } } }

less node_modules/nx/src/executors/run-commands/run-commands.impl.js
# inside — plain Node code: spawning the command, handling output, the exit code
```

This skill — "open the executor's impl" — is the main debugging tool when a task behaves inexplicably: you read what *actually* runs instead of guessing.

### The task pipeline: dependsOn

Tasks depend on each other: you can't build an application before its libraries are built. This is expressed with `dependsOn`:

- **`"^build"`** — "first run the `build` target of all of the project's *dependencies*" (the `^` symbol = "of the upstream neighbours in the graph"). The canonical rule for build.
- **`"build"`** (no `^`) — "first run the `build` target of *this same* project" (e.g. `test` may require a prior `build`).
- The object form is for fine-tuning: `{ "dependsOn": [{ "target": "build", "dependencies": true, "params": "forward" }] }`.

`dependsOn` rules are declared either in `targetDefaults` in nx.json (for all same-named targets in the repo — the usual place) or in a specific project's project.json (surgically). A `targetDefaults` key can be a target name (`"build"`) or an executor (`"@nx/vite:build"`) — the latter is more precise when same-named targets do different things across the repo.

An important nuance: `"^build"` **does not fail** when a dependency has no `build` target — the task simply isn't created. That's why non-buildable libs (our shared-ui) live happily in the pipeline: there's nothing to build, and `nx build shell` skips them.

### What happens on nx build shell

```
┌────────────────────────────────────────────┐
│ nx build shell  (= nx run shell:build)     │
└────────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────┐
│ project graph + dependsOn → TASK GRAPH:    │
│ nodes are tasks of the form project:target │
└────────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────┐
│ hash every task → cache lookup:            │
│ hit → instant replay from .nx/cache        │
└────────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────┐
│ miss → run the task's executor             │
│ in parallel, in topological order          │
└────────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────┐
│ outputs + stdout are saved to the cache    │
│ (hash mechanics — chapter 04)              │
└────────────────────────────────────────────┘
```

The key point: **the task graph is a separate structure**, derived from the project graph. Project graph nodes are projects; task graph nodes are tasks. One project graph yields different task graphs depending on what was requested: `nx build shell` has one task graph, `nx run-many -t test` another. You can inspect it without running anything: `nx build shell --graph`. A cycle in the task graph (A waits for B, B waits for A) is a run-time error — one more reason the `shared-ui ⇄ shell` cycle from chapter 02 is not viable.

Parallelism: Nx runs independent tasks concurrently (`--parallel`, default 3) while respecting topological order — a task starts once everything it depends on has finished. The practical consequence for CI: `nx run-many -t lint,test,build` is one command instead of three sequential stages; lint and test across projects don't wait for each other, and each build starts as soon as its dependencies are ready.

> **Versions.** Long-running tasks (dev servers) historically broke the pipeline: the task "never finishes", so everything depending on it waits forever. Nx 21 introduced **continuous tasks** (`"continuous": true`): the pipeline doesn't wait for their completion — the microfrontend dev mode is built on this (chapter 10), where serving the host pulls up the serve of every remote. In older versions this was worked around with hacks like `run-many` over a manual list of serve tasks.

## In a real-world monorepo

- `npx nx build <project> --graph` — the task graph of a specific run without executing it: what will run and in which order. The first "why is the build so slow" question starts here.
- `npx nx show project <project> --web` — for each target you can see: command form or executor, its `dependsOn`, and where it was inherited from (targetDefaults / plugin / project.json).
- `cat node_modules/<package>/executors.json` → the `implementation` path → open the impl file. Works for any executor of any plugin.
- `grep -A5 targetDefaults nx.json` — the repo's pipeline is declared here; if a target has unexpected prerequisites, also check project.json (`grep -rn dependsOn --include=project.json`).
- In the repo's CI config, look at how tasks are launched: `nx run-many` / `nx affected` is the norm; a sequence of separate `npm run ...` per project is a red flag (chapter 13).

## What we're adding to the project

`vite build` doesn't check types (esbuild simply strips them) — broken typing can ship to production with a green build. We add a `typecheck` target to shell on `nx:run-commands` and include it in the repo's pipeline alongside lint/test/build.

## Practical exercise

**Input:** the workspace after chapter 02 (shell + shared-ui, an edge in the graph).

**Task:**

1. Find out what `nx build shell` physically runs: locate the target in `nx show project shell`, determine its form (command or executor) and find the `nx:run-commands` code on disk.
2. Inspect the task graph: `nx build shell --graph`. Explain why there is no `shared-ui:build` task in it, even though build has `dependsOn: ["^build"]`.
3. Add a `typecheck` target to `apps/shell/project.json`: the command is `tsc -p tsconfig.app.json --noEmit`, working directory — the project folder.
4. Make `typecheck` cacheable for the whole repo via `targetDefaults` (not in project.json).
5. Run the pipeline: `nx run-many -t lint,test,typecheck,build` — and read the output: what ran in parallel, what waited.

**Requirements:** `nx typecheck shell` fails on a deliberately broken type in app.tsx and passes after the fix; a re-run with no changes comes from the cache.

**Edge cases to think about:**

- What happens if `typecheck` declares `dependsOn: ["typecheck"]` (on itself)? And `["^typecheck"]`?
- Why does `tsc --noEmit` have no outputs — and what gets cached then?
- Why use `--parallel=1` when debugging the pipeline?

## Worked solution

Step 1 — the target's form and the executor's code:

```bash
npx nx show project shell | python3 -m json.tool | grep -A4 '"build"'
# "build": {
#   "executor": "nx:run-commands",
#   "options": { "command": "vite build", "cwd": "apps/shell" },
#   ...

cat node_modules/nx/executors.json | python3 -m json.tool | grep -A2 run-commands
# "run-commands": { "implementation": "./src/executors/run-commands/run-commands.impl", ...
```

So even the "magic" inferred build is `nx:run-commands`, whose impl (a plain Node file in `node_modules/nx/src/executors/run-commands/`) spawns `vite build` in the project folder. The whole chain is readable with your own eyes.

Step 2: the task graph for `nx build shell` has a single task — `shell:build`. The `^build` rule looked through shell's dependencies (shared-ui), found no `build` target on them (the lib is non-buildable, bundler=none) and silently created no tasks. It will appear in chapter 06 when we make a buildable lib, and in chapter 12 with the api.

Steps 3–4 — the target and its repo-wide caching:

```json
// apps/shell/project.json
{
  "name": "shell",
  "$schema": "../../node_modules/nx/schemas/project-schema.json",
  "projectType": "application",
  "sourceRoot": "apps/shell/src",
  "tags": [],
  "targets": {
    "typecheck": {
      "command": "tsc -p tsconfig.app.json --noEmit",
      "options": { "cwd": "apps/shell" }
    }
  }
}
```

```json
// nx.json
{
  "targetDefaults": {
    "typecheck": { "cache": true }
  }
}
```

Key decisions:

- `"command"` is that very sugar over `nx:run-commands`: the full form with `"executor"` + `"options"` is equivalent, just longer. To verify how it expanded — `nx show project shell`.
- `cache: true` went into `targetDefaults`, not project.json — when the libs get their own typecheck targets in chapter 06, they become cacheable automatically, with no copy-paste across projects. The rule: properties shared by all same-named targets live in nx.json; project.json keeps only project specifics.
- `tsc --noEmit` has no file outputs — what's cached is the **terminal output and the exit code**. A cache replay reproduces both; for verification tasks (lint, typecheck) that's all you need. What outputs are and how to declare them — chapter 04.

Step 5 — the pipeline:

```bash
npx nx run-many -t lint,test,typecheck,build
#    ✔  nx run shared-ui:lint
#    ✔  nx run shell:typecheck
#    ✔  nx run shell:lint
#    ✔  nx run shared-ui:test
#    ✔  nx run shell:test
#    ✔  nx run shell:build
# Successfully ran targets lint, test, typecheck, build for 2 projects
```

The order in the output is a race between parallel tasks (3 at a time by default), not stages: lint ran alongside test, and shell's build started independently because it had nothing to wait for. Manually ordering "all lint first, then all tests" in CI is unnecessary and harmful — it imposes barriers that don't exist in the graph.

Answers to the edge cases:

- `dependsOn: ["typecheck"]` on itself — a cycle in the task graph; Nx refuses to build the plan and fails with an error. `["^typecheck"]` is legal: dependencies' typecheck first; while the libs have no such target, it's a no-op.
- `--parallel=1` serializes execution: task logs don't interleave and the order is deterministic — the standard move to figure out *which* task is breaking the pipeline.

## Check yourself

1. How does the task graph differ from the project graph, and why are they two different graphs? What is the task graph for `nx build shell` made of?
2. Decode `"dependsOn": ["^build"]` word by word. What happens for a dependency that has no `build` target?
3. `"command": "vite build"` in a target's configuration — what is it really? Describe the path from that line to a running vite process.
4. Why is `nx run-many -t lint,test,build` in CI better than three sequential stages lint → test → build?
5. What principle decides where a target property is declared — in nx.json's `targetDefaults` or in a project's project.json?

<details>
<summary>Answers</summary>

1. The project graph is the static map of "who depends on whom" (nodes are projects, edges are imports). The task graph is the plan of a specific run (nodes are `project:target` tasks), built from the project graph by expanding `dependsOn` rules from the requested tasks. Different commands produce different task graphs over the same project graph. For `nx build shell`: take `shell:build`, the `^build` rule adds the build tasks of its dependencies (those that have the target) — recursively down the graph.
2. "Before running this target, run the `build` target of every project the current one depends on in the project graph". If a dependency has no `build` target — no task is created for it, and there is no error. That's why non-buildable libs don't obstruct the pipeline.
3. Sugar: the configuration normalizes to `{"executor": "nx:run-commands", "options": {"command": "vite build", ...}}`. At run time Nx looks up the run-commands implementation path in `node_modules/nx/executors.json`, loads the impl module, and it spawns a `vite build` child process with the project's `cwd`, relaying output and the exit code back to Nx (which caches them).
4. Stages are artificial barriers: the whole test stage waits for the slowest lint, even though project X's tests don't depend on project Y's lint. `run-many` with several targets hands Nx all the tasks at once, and it executes them with maximum parallelism while honouring only the real dependencies from the task graph. The same work finishes faster, and the ordering is guaranteed by the graph, not by a rigid sequence.
5. The general rule: what holds for *all* same-named targets in the repo (cacheability, `^build`, shared inputs) goes into `targetDefaults`; what's project-specific (the command itself, special options, a targeted override) goes into project.json. New projects then get correct behaviour automatically, and project.json files stay thin.

</details>

## Common mistake

A developer from the single-app world reproduces the familiar CI in the monorepo: sequential stages `lint → test → build`, each looping over projects or calling `npm run`. It works, but throws away the main thing: Nx already knows both the order and the allowed parallelism — from the task graph. Manual stages add artificial barriers (build waits for *all* tests to finish even though its dependencies are ready) and, worse, duplicate the dependency knowledge: when a new lib appears, someone must remember to slot it into the handcrafted order — while `dependsOn` would have picked it up automatically.

The second classic misstep is putting a long-running task into a regular pipeline: making `e2e` depend on `serve` and wondering why the pipeline hangs. `serve` never finishes — and the pipeline waits precisely for *completion*. Before Nx 21 this was solved with workarounds (starting the server outside Nx, wait-on scripts); newer versions have `"continuous": true` for it, which the Module Federation dev mode is also built on (chapter 10). If your repo is older — know that a hung `dependsOn: ["serve"]` is not a bug but the wrong tool for the job.
