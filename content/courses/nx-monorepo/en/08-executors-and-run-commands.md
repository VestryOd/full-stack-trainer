# Executors: from run-commands to your own

## Theory

### The decision ladder

From chapter 03 we know that an executor is the function Nx hands a task to. We also know that `nx:run-commands`, with its `"command"` sugar, is the most common one. Before writing your own, honestly walk the ladder:

```
┌───────────────────────────────┬──────────────────────────────────┐
│ nx:run-commands is enough     │ a custom executor is warranted   │
├───────────────────────────────┼──────────────────────────────────┤
│ wrap one existing CLI command │ logic: conditions, retries, API  │
├───────────────────────────────┼──────────────────────────────────┤
│ commands: serial or parallel  │ typed, schema-validated options  │
├───────────────────────────────┼──────────────────────────────────┤
│ one-off script for this repo  │ reuse across dozens of projects  │
├───────────────────────────────┼──────────────────────────────────┤
│ output and exit code suffice  │ needs context: graph/root/config │
└───────────────────────────────┴──────────────────────────────────┘
```

Between the columns sits an intermediate step people often forget: **a script launched via run-commands** (`"command": "tsx tools/scripts/deploy.ts"`). The logic already lives in a proper typed file, just without the plugin packaging. For many tasks that's the optimum; a custom executor beats it when you need per-project validated options and access to the Nx context.

### run-commands beyond "command"

The full form does noticeably more than the chapter 03 sugar:

```json
{
  "executor": "nx:run-commands",
  "options": {
    "commands": [
      "node tools/scripts/prepare.js {projectName}",
      "vite build"
    ],
    "parallel": false,
    "cwd": "{projectRoot}",
    "envFile": ".env.build",
    "forwardAllArgs": true
  }
}
```

- `commands` + `parallel: false` — a sequential chain (by default the listed commands run in parallel!);
- interpolation: `{projectRoot}`, `{projectName}`, `{args.name}` — values from the context and command-line (CLI) arguments substituted into the strings;
- `envFile` loads variables (remember chapter 04: if they affect the artifact, they belong in inputs too);
- `forwardAllArgs` passes `nx run x:y --flags` through into the command.

A non-zero exit code from any command → the task fails. For many scenarios that contract is all you need.

### The anatomy of a custom executor

Three files, mirroring generators from chapter 07. An entry in **executors.json** (the plugin registry), a **schema.json** (option types and validation), and the **impl** — an async function:

```ts
export default async function myExecutor(
  options: MyExecutorSchema,        // already validated by the schema
  context: ExecutorContext,         // who am I and where am I
): Promise<{ success: boolean }> { ... }
```

The result contract is a `{ success }` object. It is not an exception and not an exit code, because the executor runs inside the Nx process. So `success: false` is the sanctioned way to say "the task failed". A thrown exception also fails the task, but with an ugly stack trace instead of your message.

**ExecutorContext** is what a shell command doesn't have. It carries `projectName` (whom the task runs for), `root` (the workspace root) and `projectsConfigurations` (every project's configuration, effectively the project graph). It also carries `targetName`, `configurationName` and `isVerbose`.

One executor attached to ten projects behaves differently for each because it reads the context — that's its power over a hardcoded script.

For long-running tasks such as dev servers there's a second contract form: an async iterable that yields events instead of a single result. That's how serve executors are built, and how Nx knows a task is "running" rather than "hung".

> **Versions.** In older repos executors are called **builders** — an Angular devkit legacy (`"builder": "@angular-devkit/build-angular:browser"` in angular.json). Same contract, different word. And `nx:run-commands` lived as `@nrwl/workspace:run-commands` before the rebranding — you'll meet it in unmigrated configs.

### The skill: what actually runs

The complete debugging chain for any target (assembling chapters 01, 03 and this one):

1. `nx show project X` — the final configuration: executor or command, options after all layers (inferred → targetDefaults → project.json).
2. If the executor is custom: `node_modules/<package>/executors.json` (for a local plugin — `tools/workspace-plugin/executors.json`) → the impl path → read the code.
3. `nx run X:target --verbose` — the full stack trace instead of the short error.

This closes the "why does the deploy in our repo do *that*" question in minutes — no wiki archaeology, no interviewing the old-timers.

## In a real-world monorepo

- `find . -name executors.json -not -path '*/node_modules/*'` — does the repo have custom executors? Their impls are the de facto documentation of how the team does deploys, codegen and database migrations.
- `grep -rn '"executor"' --include=project.json apps libs | grep -v 'nx:run-commands' | grep -v '@nx/'`. Which projects use homegrown executors? Old `@nrwl/` aliases show up along the way.
- In `nx show project X` output, look for options with curly braces: `{projectRoot}`, `{args.*}` — interpolation explains where the "magic" values in commands come from.
- A task fails mysteriously — `nx run X:y --verbose` before reading any code: the full stack trace is often enough.
- Hunting for where deploy logic lives: first `nx show project <app>` for the deploy target, then the impl via the theory chain. Not a repo-wide search for "deploy".

## What we're adding to the project

A custom `deploy` executor in our workspace-plugin: a deploy stub that publishes the built artifact into a local content delivery network (CDN) folder. In chapters 10–11 this is exactly how we'll simulate the independent deployment of every remote microfrontend.

## Practical exercise

**Input:** the workspace after chapter 07 (the local plugin with the feature-lib generator).

**Task:**

1. Generate a `deploy` executor stub in workspace-plugin.
2. Implement the contract:
   - **Options (schema):** `destination` (string, default `".deploy"`), `clean` (boolean, default `true`);
   - **Logic:** locate the project's artifact at `dist/<projectRoot>`, computing the path from the context rather than hardcoding it. If it is missing, return `success: false` with a clear "run nx build first" hint. If `clean` is set, wipe the target folder. Copy the artifact into `<destination>/<projectName>`. Print a pseudo-URL like `https://cdn.mini-shop.local/<projectName>/`;
   - **Result:** `{ success: true }` only if the copy actually happened.
3. Attach a `deploy` target to shell: the plugin's executor, `dependsOn: ["build"]`, no caching.
4. Verify three scenarios. Deploy without a build: no artifact, so `success: false`. Then `nx deploy shell`: build is pulled in via dependsOn, from cache if unchanged. Then repeat the deploy: build hit, deploy re-executed.
5. Add `.deploy/` to .gitignore.

**Edge cases to think about:**

- Why `dependsOn: ["build"]` (no `^`), not `["^build"]`?
- What happens on `nx run-many -t deploy` across several projects with a shared `destination` and no per-project subfolders?
- Why does the executor return `success: false` instead of `throw new Error(...)`?

## Worked solution

Steps 1–2 — the stub and the implementation:

```bash
npx nx g @nx/plugin:executor deploy \
  --path=tools/workspace-plugin/src/executors/deploy
```

`schema.json`:

```json
{
  "$schema": "https://json-schema.org/schema",
  "$id": "Deploy",
  "title": "Deploy stub: publishes a project's dist into a local CDN folder",
  "type": "object",
  "properties": {
    "destination": {
      "type": "string",
      "description": "The local 'CDN' root",
      "default": ".deploy"
    },
    "clean": {
      "type": "boolean",
      "description": "Wipe the target folder before copying",
      "default": true
    }
  },
  "required": []
}
```

`executor.ts`:

```ts
import { ExecutorContext, logger } from '@nx/devkit';
import { cpSync, existsSync, rmSync } from 'fs';
import * as path from 'path';
import { DeployExecutorSchema } from './schema';

export default async function deployExecutor(
  options: DeployExecutorSchema,
  context: ExecutorContext,
): Promise<{ success: boolean }> {
  const projectName = context.projectName!;
  // Context instead of hardcode: the executor works for ANY project in the repo
  const projectRoot = context.projectsConfigurations.projects[projectName].root;
  const distPath = path.join(context.root, 'dist', projectRoot);
  const targetPath = path.join(context.root, options.destination, projectName);

  if (!existsSync(distPath)) {
    logger.error(`Artifact not found: ${distPath}`);
    logger.error(`Build the project first: nx build ${projectName}`);
    return { success: false };
  }

  if (options.clean && existsSync(targetPath)) {
    rmSync(targetPath, { recursive: true });
  }
  cpSync(distPath, targetPath, { recursive: true });

  logger.info(`✅ ${projectName} deployed → ${targetPath}`);
  logger.info(`   https://cdn.mini-shop.local/${projectName}/`);
  return { success: true };
}
```

Step 3 — the target on shell (`apps/shell/project.json`, fragment):

```json
{
  "targets": {
    "deploy": {
      "executor": "@mini-shop/workspace-plugin:deploy",
      "dependsOn": ["build"],
      "cache": false
    }
  }
}
```

Key decisions:

- `dependsOn: ["build"]` without `^` — the deploy needs the built **project itself**, not its dependencies (those are handled by build's own `^build`). A fresh artifact is always deployed. If the sources didn't change, build closes as a cache hit in milliseconds. That is exactly the "cache the pure functions, execute the side effects" pairing we built in chapter 04.
- `cache: false` on deploy is formally redundant, because caching only turns on with an explicit `cache: true`. But a documented intent is cheaper than an hour of debugging if someone someday enables caching for this target name via targetDefaults.
- The artifact path is computed from `context.projectsConfigurations`. Attach this same target to catalog or a checkout remote (chapter 10) and it works without a single edit.

Step 4 — the scenarios:

```bash
rm -rf dist
npx nx run shell:deploy   # with dependsOn, build gets pulled in automatically;
# to see the failure branch, run the executor on a project with no dist:
# >  NX   Artifact not found: dist/apps/shell — Build the project first: nx build shell

npx nx deploy shell
# ✔ nx run shell:build          ← the prerequisite from dependsOn
# ✅ shell deployed → .deploy/shell
#    https://cdn.mini-shop.local/shell/

npx nx deploy shell
# ✔ nx run shell:build  [local cache]   ← the build replayed from cache
# ✅ shell deployed → .deploy/shell     ← the deploy executed again
```

Answers to the remaining edge cases:

- `run-many -t deploy` with a shared folder and no per-project subpaths — parallel tasks race for the same paths: artifacts overwrite each other non-deterministically. Our `<destination>/<projectName>` scheme makes deploys independent by construction — the same isolation principle as cache outputs.
- A `throw` also fails the task, but the user gets the executor's stack trace instead of a diagnosis. Returning `success: false` with `logger.error` is a managed failure: you articulate what happened and what to do. Keep exceptions for the genuinely unexpected, such as a bug in the executor itself.

## Check yourself

1. State the executor contract: the signature, what returning `{ success: false }` means, and how that differs from a non-zero exit code in run-commands.
2. What exactly does `ExecutorContext` provide that a shell command fundamentally lacks? Show it on our deploy.
3. Why does deploy use `dependsOn: ["build"]` without `^`? And why is the "deploy depends on build + build is cached" pairing correct architecture rather than a wasted run?
4. The team asks to "add retries and a Slack notification to the deploy". Today it's a run-commands with a 200-character bash string. By which signs do you know it's time for a custom executor (or at least a script)?
5. An unfamiliar repo; `nx run api:migrate-db` does something scary. Describe the file chain that tells you in five minutes what actually runs.

<details>
<summary>Answers</summary>

1. The signature is `async (options, context) => Promise<{ success: boolean }>`, or an async iterable for long-running tasks. Returning `success: false` is a sanctioned, managed failure: the executor logged the cause itself and returned a verdict. Nx marks the task failed and fails its dependents. In run-commands the same role is played by the process exit code. But the diagnostics there are limited to whatever the command printed, while an executor formulates the error programmatically and with types.
2. Task self-awareness: `projectName`, the project's root from `projectsConfigurations` (effectively the graph), the target and configuration names, the verbose flag. A shell command knows only its cwd and env. In deploy this let us compute `dist/<projectRoot>` and `<destination>/<projectName>` from context — one executor serves any project in the repo with no hardcoded parameters.
3. Without `^`: the deploy needs the project's own artifact, and the dependencies are built by that build's own `^build`. The pairing is correct because each layer does its job. The dependsOn entry guarantees artifact freshness, so the deploy never publishes a stale dist. The cache guarantees that freshness is free when sources are unchanged. And `cache: false` on deploy itself guarantees the publish always executes. No scenario breaks: code changed, code unchanged, or dist deleted.
4. There are four transition signs. Conditions and error handling appear in the string (`&&`, `||`, `if`). Options are passed positionally with no validation. The same string gets copied into a second and third project. And when it fails, nobody can tell at which step. The first step up is a typed script (`tsx tools/scripts/deploy.ts`) called via run-commands. An executor is justified once you need per-project schema-validated options and context, that is, different behaviour for different projects.
5. `nx show project api` → the `migrate-db` target: the executor and final options. If the executor is custom, open the executors.json of the corresponding package or plugin (for a local one, in tools/). From there follow the implementation field to the file and read it. When running — `--verbose` for the full stack trace. Five minutes, zero interviews with old-timers.

</details>

## Common mistake

A developer from the single-app world solves problems "the package.json way". The run-commands `commands` list grows a bash rope: `mkdir -p ... && cp -r ... && curl ... || echo 'failed' && exit 1`, ten commands with conditions. It's untyped, untestable, behaves differently in bash and zsh, and a mid-way failure leaves a half-deploy with no rollback.

The threshold is simple: **the moment a command grows `&&` with a condition or error handling, it's a program**. A program belongs in a file — a script via run-commands — or in an executor. There, failure is a meaningful `success: false` with a diagnosis, not a scrap of stdout.

The opposite extreme is executor mania: a custom executor for every trifle where `"command": "rimraf dist"` would do. Every executor is a schema, an impl, tests and maintenance across Nx upgrades. The plugin bloats, and a year later half the executors duplicate existing command-line tools, worse than the originals.

The ladder from the start of the chapter is the working filter: command → commands → script → executor. A task climbs a step only when it's genuinely cramped on the current one.
