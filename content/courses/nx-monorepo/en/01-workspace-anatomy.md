# Workspace anatomy

## Theory

### nx.json — the configuration of Nx itself

`nx.json` at the root is the only file that describes the behaviour of *Nx itself* (rather than individual projects). Three key blocks you'll run into constantly:

- **`plugins`** — the list of registered plugins with their options. This is not just "installed packages": every entry here means "this plugin scans the repo and *infers* targets from tool configs". The `@nx/vite/plugin` entry is why a project with a `vite.config.ts` has `build` and `serve`, even though its project.json is empty.
- **`targetDefaults`** — defaults for same-named targets across all projects: `"build": { "dependsOn": ["^build"], "cache": true }` means "any build first builds its dependencies and is cached". Covered in chapter 03.
- **`namedInputs`** — named file sets (`default`, `production`, `sharedGlobals`) that feed the cache hash. The central topic of chapter 04.

You'll also meet three smaller blocks. The block `generators` sets default generator options, so that every `nx g @nx/react:lib` in this repo gets the same bundler and linter. Next to it sit `defaultBase` (for affected) and `release` (versioning/publishing).

### What makes a folder a "project"

Nx doesn't scan "everything": graph nodes come from three sources. A folder becomes a project if one of these is true:

- it contains a **`project.json`**;
- it contains a **`package.json`** (the package-based classic);
- it was "adopted" by a plugin from `nx.json` whose `createNodes` matched a tool config. That's how `@nx/playwright` creates an e2e (end-to-end — tests that drive the whole running app) project from `playwright.config.ts`.

Knowing this list removes the main confusion in an unfamiliar repo: "why does `nx show projects` list a project that has no project.json?"

### project.json vs inferred targets: before and after crystal

This is the biggest behavioural change in the history of Nx, and in real work repos you'll meet both eras:

- **The old world (before Nx 17.2)**: every project has a "fat" `project.json` where each target is written by hand: executor, options, configurations, outputs. Dozens of lines per project, duplication across the repo, and a change like "update outDir for everyone" means a mass find-and-replace.
- **Project crystal (Nx 18+, mainstream since 19)**: targets are *inferred* by plugins from the tools' own configs. If there's a `vite.config.ts`, the `@nx/vite` plugin gives the project `build`, `serve`, `preview` and `test`, reading the options straight from that config. Then `project.json` slims down to a name, a type and tags — or disappears entirely.

The final target configuration is assembled from three layers — and in an unfamiliar repo it matters which layer "won":

```
            precedence: higher = stronger
┌────────────────────────────────────────────────────┐
│ 3. the project's project.json (and the "nx" key    │
│    in package.json) — targeted overrides           │
├────────────────────────────────────────────────────┤
│ 2. nx.json: targetDefaults — defaults for all      │
│    same-named targets across the workspace         │
├────────────────────────────────────────────────────┤
│ 1. targets inferred by plugins (crystal):          │
│    vite.config.ts → build / serve / preview / test │
└────────────────────────────────────────────────────┘
       the result: nx show project shell --web
```

The tool that makes these layers visible is **`nx show project shell --web`**. It opens an interactive page with **all** of the project's targets. Every option there is annotated with its source: which plugin or file contributed it. Without `--web`, the same command prints the final JSON to the terminal. It answers "what will actually run on `nx build shell`" — and we'll use it in every chapter.

> **Versions.** The names of inferred targets are not Nx constants but plugin options in `nx.json`: `"serveTargetName": "serve"`. In some repos the dev server is `nx serve app`, in others `nx dev app`. The reason is that someone — or a different generator version — named the target differently. Before complaining that "the command from the tutorial doesn't work", check the `plugins` block of your repo's nx.json.

### apps/ vs libs/ — why this split

The Nx convention: **thin apps, fat libs** (a rule of thumb: 20% of the code in apps, 80% in libs). An application is a build-and-deploy point: routing, composition, configuration. All the logic, UI (user interface) components and data access live in libs — even when there's only one app.

The reasons are pragmatic:

- only libs get boundaries (`tags` + module boundaries, chapter 06);
- only small libs give precise affected results — change `catalog/data-access` and the `checkout` tests don't run;
- only code extracted into a lib can be reused by a future second app, and this course will have four of them.

The folder names themselves are a convention: `workspaceLayout` in nx.json can change them, and newer presets use `packages/`.

## In a real-world monorepo

- `npx nx show projects` — a flat list of every project in the repo. Faster than `nx graph` when you just need the names and the scale.
- `npx nx show project <name> --web` — the key command of this chapter: all real targets of a project and the source of every option. Look for "inferred by @nx/..." versus "from project.json" annotations.
- `cat nx.json | python3 -m json.tool` — a non-empty `plugins` block → the repo runs on crystal, tool configs are the source of truth. No block, but fat project.json files → the old style, the truth lives in project.json.
- `find . -name project.json -not -path "*/node_modules/*" -exec wc -l {} +` — project.json weight across the whole repo in a second. Files of 10 lines mean crystal, 100+ lines mean explicit executors.
- `npx nx list @nx/react` — which generators and executors an installed plugin provides; works for any `@nx/*`.

## What we're adding to the project

We generate the first application — `shell`, the future microfrontend host (chapters 10–11). For now it's a regular React app on Vite. Along the way the workspace gains its first plugins in `nx.json` and a `tsconfig.base.json`.

## Practical exercise

**Input:** the `mini-shop` workspace from chapter 00 (empty, one commit).

**Task:**

1. Add the React plugin with `npx nx add @nx/react` and inspect the diff: what changed in `package.json` and `nx.json`?
2. Generate a `shell` application in `apps/shell`: bundler — vite, styles — css, tests — vitest, no e2e. First run the generator with `--dry-run` and read the file list, then for real.
3. Study the result and answer in writing:
   - How many targets are declared in `apps/shell/project.json` — and how many does `nx show project shell` display? Where does the difference come from?
   - What appeared under `plugins` in nx.json, and which target names are configured there?
   - Why did `tsconfig.base.json` appear at the root only now, and not in chapter 00?
4. Run `nx serve shell` (check it in the browser) and `nx build shell`. Then find the build artifact on disk and the file where its path is configured.

**Edge cases to think about:**

- What happens if you run the same generator a second time? And with `--dry-run`?
- How do you rename the `serve` target to `dev` for every vite project at once, without touching a single project.json?
- Why is `nx add @nx/react` better than a manual `npm install -D @nx/react`?

## Worked solution

Installing the plugin and generating:

```bash
npx nx add @nx/react
# installs @nx/react at EXACTLY the same version as nx and runs its init generator

npx nx g @nx/react:app shell --directory=apps/shell --dry-run
# CREATE apps/shell/project.json ... — a plan only, the disk is untouched

npx nx g @nx/react:app shell --directory=apps/shell \
  --bundler=vite --style=css --unitTestRunner=vitest \
  --e2eTestRunner=none --linter=eslint
```

> **Versions.** Since Nx 18 the project path is taken exactly as you provide it: `--directory=apps/shell` means literally that folder. Older versions behaved differently (`projectNameAndRootFormat=derived`): Nx built the path itself out of the project name and the nesting options. The same command could therefore drop the project somewhere else entirely.

> **Versions.** The command `nx add` appeared in Nx 17. Before that you installed plugins by hand, and the main risk was installing a version that didn't match the core (chapter 00).

What appeared (plus small extras like a favicon — the exact set depends on the version):

```
mini-shop/
├── apps/shell/
│   ├── index.html            # vite dev entry
│   ├── project.json          # THIN: name, type, tags — no targets
│   ├── vite.config.ts        # source of truth: build/serve/test
│   ├── tsconfig.json         # + tsconfig.app.json, .spec.json
│   └── src/
│       ├── main.tsx          # bootstrap: createRoot + <App/>
│       ├── styles.css
│       └── app/
│           ├── app.tsx
│           └── app.spec.tsx  # vitest, same vite.config.ts
├── tsconfig.base.json        # appeared with the first TS project
└── eslint.config.mjs         # flat config in newer versions
```

`apps/shell/project.json` — the whole file:

```json
{
  "name": "shell",
  "$schema": "../../node_modules/nx/schemas/project-schema.json",
  "projectType": "application",
  "sourceRoot": "apps/shell/src",
  "tags": []
}
```

**Zero** targets here. And yet:

```bash
npx nx show project shell
# {
#   "name": "shell",
#   "targets": {
#     "build":   { "command": "vite build", ... },
#     "serve":   { "command": "vite serve", ... },
#     "preview": { "command": "vite preview", ... },
#     "test":    { "command": "vitest", ... },
#     "lint":    { "command": "eslint .", ... }
#   }
# }
```

All five targets are inferred: they were contributed by the plugins that `nx add` registered in nx.json. Note that crystal targets run **the tool's own CLI (command-line interface)** — `vite build` is the same command you'd type by hand. Nx wraps it with the graph, the cache and the pipeline; how exactly is chapter 03.

```json
{
  "plugins": [
    {
      "plugin": "@nx/vite/plugin",
      "options": {
        "buildTargetName": "build",
        "serveTargetName": "serve",
        "previewTargetName": "preview",
        "testTargetName": "test"
      }
    },
    { "plugin": "@nx/eslint/plugin", "options": { "targetName": "lint" } }
  ],
  "generators": {
    "@nx/react": {
      "application": {
        "babel": true, "style": "css", "linter": "eslint", "bundler": "vite"
      }
    }
  }
}
```

Key decisions:

- The answer to the renaming edge case: change `"serveTargetName": "serve"` to `"dev"` in this block. Then **every** vite project in the repo gets an `nx dev <project>` target. Not a single project file is touched — that's what "targets belong to the plugin, not the project" means.
- `generators."@nx/react"` — the wizard's answers written down: the next `nx g @nx/react:lib` in this repo silently picks up the same options. That's how a team gets uniform projects without "Pete's lib uses styled-components, Mary's uses css".
- `tsconfig.base.json` appeared only now because it's created by the init generator of the first JS/TS plugin, not by `create-nx-workspace`. An empty workspace doesn't need it. There's no `paths` block in it yet — the first alias arrives with the first lib in chapter 02.

Running and building:

```bash
npx nx serve shell     # vite dev server, http://localhost:4200 by default
npx nx build shell     # artifact: dist/apps/shell/
```

The artifact path is configured not "somewhere in Nx" but in `apps/shell/vite.config.ts` → `build.outDir`. The plugin read it from there and reported it to Nx as the target's output, which matters for caching (chapter 04).

Re-running the generator over an existing project fails on a name conflict. Generators don't promise idempotency — the property of producing the same result on every run. Checking "what would change" is exactly what `--dry-run` is for.

## Check yourself

1. A project's project.json has no targets at all, yet `nx build` works for it. Explain the mechanics: who created that target, and from what?
2. In what order do the three layers of target configuration merge, and which one wins? Where can you see the result for a specific project?
3. Why is "thin apps, fat libs" a requirement of Nx mechanics rather than aesthetics? Name at least two features that degrade when all the logic lives in the application.
4. Which three things make a folder a "project" in the eyes of Nx? Why can `nx show projects` list more projects than there are project.json files?
5. In one repo the dev server starts with `nx serve app`, in another with `nx dev app`. Where does the difference physically live, and what does that say about the nature of target names?

<details>
<summary>Answers</summary>

1. While the graph is being built, a plugin from `nx.json` (e.g. `@nx/vite/plugin`) scans the repo with its `createNodes`. It finds `vite.config.ts`, reads it and *infers* the targets (`build`, `serve`, ...) with the options already filled in. The target exists only in the in-memory graph — it's in none of the project's files. The tool config is the source of truth. That's why editing `vite.config.ts` changes the behaviour of `nx build` without a single change to project.json.
2. Bottom to top: plugin-inferred targets, then `targetDefaults` from nx.json on top of them, then targeted overrides from project.json. The `"nx"` key of the project's package.json works the same way as project.json, and project.json wins. The merged result is shown by `nx show project <name>` (with `--web` — including the source of every option).
3. First, affected: with all the logic in one app, any change touches "the whole app" — everything rebuilds and retests, granularity is lost. Second, module boundaries: tags and boundary rules (chapter 06) attach to libraries — a monolithic app has nothing to constrain. Third, reuse: code inside an app can't be imported by another application (and this course will have four of them), code in a lib can.
4. Three things. A `project.json` in the folder. A `package.json` in the folder. Or a plugin from nx.json whose `createNodes` matched a tool config there. The third source explains the "extra" projects. An e2e project created by `@nx/playwright` from a single `playwright.config.ts` may have no project.json at all.
5. In nx.json, in the plugin options: `"serveTargetName": "serve"` or `"dev"`. Target names are not constants baked into Nx — they are configurable options of a specific repo. So the first reflex in someone else's workspace is not to google the "right" command. Check `plugins` in nx.json instead, or run `nx show project <name>`.

</details>

## Common mistake

A developer from the single-app world opens `apps/shell/project.json` and sees five lines with no targets. The conclusion: "the configuration is hidden somewhere, Nx is magic". Two bad scenarios follow.

First: they find a 2022 article (the pre-crystal world) and write a full `build` target with executor and options into project.json. Now the repo has **two sources of truth**. Their manual target silently shadows the inferred one, and edits to vite.config.ts partially stop affecting the build.

Second: they edit `vite.config.ts` without knowing that the specific option is overridden in `targetDefaults`, and can't understand why nothing changes. The cure is the same for both: `nx show project shell --web`. See the final configuration and the *source* of every option before touching anything.

A related reflex is creating a new application by copying an existing one's folder: "I'll copy shell and rename it — faster than figuring out generators". Three things go wrong. The copied project.json keeps the old name, which is a conflict when the graph is built. Tags and aliases go stale. Half the files the generator would have adapted stay as they were in the donor.

A generator run with `--dry-run` prints the full list of what should be created and modified. That's the honest answer to "what makes up a new project".
