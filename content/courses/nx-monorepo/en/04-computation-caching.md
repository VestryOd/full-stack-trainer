# Computation caching: a cache you have to understand

## Theory

### A task as a pure function

The model the whole Nx cache stands on: **a task is a pure function**. Inputs fully determine outputs; therefore the result can be memoized: hash the inputs, and if that hash has already been executed — don't run the task, replay the saved result instead. A cache hit on a build that takes minutes completes in milliseconds.

The entire reliability of this scheme rests on one condition: **the declared inputs and outputs match the actual ones**. The Nx cache doesn't "glitch sometimes" — it strictly executes the contract you described to it. Every "the cache lied" story is a story about a wrongly described contract, and at the end of this chapter we'll reproduce one with our own hands.

### What goes into the hash

```
┌─────────────────────────────────────────────────────────┐
│ the shell:build task hash is computed from:             │
├─────────────────────────────────────────────────────────┤
│ · content of shell files matched by inputs (production) │
│ · content of every dependency's files (^production)     │
│ · the target configuration: command and options         │
│ · versions of externalDependencies (npm:vite, ...)      │
│ · sharedGlobals and declared env variables              │
└─────────────────────────────────────────────────────────┘
      key found in .nx/cache → replay, not found → run
```

Line by line:

- **Content, not dates.** Nx hashes file contents: a `touch` that changes no bytes doesn't invalidate the cache, and a `git checkout` back and forth doesn't force a rebuild.
- **Dependency files** enter via the `^` notation (familiar from dependsOn): changing `button.tsx` in shared-ui changes the `shell:build` hash, because build's inputs are `["production", "^production"]`.
- **The target configuration** — the command and options themselves: change a `vite build` flag and it's a different task; the old cache doesn't apply to it.
- **externalDependencies** — versions of the npm packages the task reaches through the graph (chapter 02): bump vite — the hash changes.
- **Env variables** enter the hash **only if declared** (`{"env": "SHOP_BANNER"}`). This is the most common source of a "lying" cache — remember this line until the exercise.
- There are also **runtime inputs** — the result of a command, e.g. `{"runtime": "node --version"}`: useful when the artifact depends on the Node version.

### namedInputs: why a spec file must not bust the build cache

Listing globs in every target doesn't scale, so file sets get names in `nx.json` → `namedInputs`. The canonical pattern is two sets:

- **`default`** — all project files + `sharedGlobals` (global files that affect everything: the root tsconfig.base.json, a CI environment lock file).
- **`production`** — `default` **minus** whatever doesn't affect the production artifact: `*.spec.tsx`, test configs, README. Exclusion syntax is a `!`-glob: `"!{projectRoot}/**/*.spec.@(ts|tsx)"`.

Then the wiring to targets: `build` takes `["production", "^production"]`, and `test` takes `["default", "^production"]`. Read those two lines carefully — they carry the whole idea:

- editing `app.spec.tsx` → the `test` hash changes (specs are in default), the `build` hash doesn't (subtracted from production). Tests rerun, the build replays from cache;
- editing `button.tsx` in shared-ui → both `shell:build` and `shell:test` invalidate (via `^production`);
- editing specs *inside shared-ui* doesn't even touch `shell:test`: someone else's tests have no reason to rerun (`^production`, not `^default`).

Without a configured `production`, every commit to tests rebuilds the whole repo — fixing that is the cheapest CI optimization in existence.

### outputs and what lives in .nx/cache

**Outputs** declare *where the task writes*: `["{projectRoot}/dist"]`, `["{workspaceRoot}/dist/apps/shell"]`, `["{options.outputPath}"]`. On execution Nx saves those paths into `.nx/cache` along with the terminal output; on a hit it restores the files into place and replays stdout, colors included. Tasks without file artifacts (lint, typecheck) need no outputs: only the output and exit code are cached — which is all they need.

The cache is an ordinary folder: inside `.nx/cache` are directories named by hash, holding the outputs and a terminal-output file. It's worth opening once with your own eyes: it stops being magic. Bypass the cache once — `--skip-nx-cache`; wipe everything derived — `nx reset`; turn caching off for a target permanently — `"cache": false` (correct for side-effect tasks like deploy).

### When the cache "lies" and how to debug it

Four typical scenarios, all contract violations:

1. **An undeclared input.** The task reads something not in inputs: an env variable, a file outside projectRoot, a global config not in sharedGlobals. Symptom: you changed something, yet Nx returns a hit with the old result. Cure: add the missing input.
2. **An undeclared output.** The task writes where Nx doesn't look. Symptom: after a hit, part of the artifacts is missing. Cure: add the path to outputs.
3. **An unstable input.** Something in inputs changes on its own: codegen writes straight into src before the build, a config contains a timestamp. The symptom is the opposite — the cache **never** hits. Debug: two runs in a row with no edits; a second miss = look for what mutates between runs.
4. **A non-deterministic task.** A flaky test passed once — and the cache will replay the "green" result until the inputs change. The cache is honest here; the test isn't.

The general diagnostic algorithm: reproduce with `--skip-nx-cache` (result differs from the hit? — the contract is broken) → figure out which input isn't accounted for (`nx show project X` shows the target's final inputs) → declare it. Turning the cache off for good is capitulation, not a fix.

## In a real-world monorepo

- `cat nx.json | python3 -m json.tool | grep -B2 -A10 namedInputs` — is there a `production` set and what's subtracted from it. If it's missing — test edits rebuild production artifacts; fixing it takes half an hour and visibly speeds up CI.
- Run any build twice: the second run prints a `[local cache]` marker and takes hundreds of milliseconds. No marker — caching for that target is off or unstable (scenario 3).
- `ls .nx/cache | head` and peek into one of the hash folders — the outputs and terminal output sit there in plain sight.
- `grep -rn "process.env" apps/*/vite.config.* webpack.config.*` (and equivalents) — every variable found must either be in the corresponding target's inputs or provably not affect the artifact. This is the highest-yield audit for cache "lies".
- `nx show project <name>` → the target's inputs block: the final list after all the layers. Compare it against what the task actually reads.
- Suspecting a stale cache on odd behaviour — `--skip-nx-cache` to verify, `nx reset` as the last resort. If `--skip-nx-cache` gives a different result — you have scenario 1; hunt down the input.

## What we're adding to the project

We set up an honest cache for mini-shop: a `production` set in namedInputs (specs don't invalidate builds), then add a banner driven by the `SHOP_BANNER` env variable to shell — and use it to reproduce the classic false cache hit, then repair the contract.

## Practical exercise

**Input:** the workspace after chapter 03 (shell + shared-ui, the lint/test/typecheck/build pipeline).

**Task:**

1. Define namedInputs in `nx.json`: `default` (project files + sharedGlobals with the root `tsconfig.base.json`), `production` (default minus `*.spec.*`, `tsconfig.spec.json`); in `targetDefaults` bind `build` to `["production", "^production"]` and `test` to `["default", "^production"]`.
2. Verify the invalidation matrix (each item = edit a file + `nx run-many -t test,build` + read what came from cache):
   - a comment in `apps/shell/src/app/app.spec.tsx` → test miss, build hit;
   - a comment in `libs/shared/ui/src/lib/button.tsx` → both miss;
   - `touch` on any file without changing content → both hit.
3. Render a banner in the shell UI from an environment variable: pipe `process.env.SHOP_BANNER` through `define` in `vite.config.ts`, render it in app.tsx.
4. Reproduce the cache lie: build with `SHOP_BANNER="Sale -20%"`, then build with `SHOP_BANNER="Black Friday"` — and show (grep over dist) that the artifact still contains the old banner on a cache hit.
5. Repair the contract: declare the env input for build. Confirm that changing the variable's value now causes a miss, and a re-run with the same value is a hit.

**Edge cases to think about:**

- Why can't `vite.config.ts` be subtracted from production, even though it's "not application source"?
- What happens on a cache hit if you delete `dist/apps/shell` by hand?
- Why must the `deploy` task (arriving in chapter 08) have caching disabled on principle?

## Worked solution

Step 1 — the cache contract in nx.json:

```json
{
  "namedInputs": {
    "default": ["{projectRoot}/**/*", "sharedGlobals"],
    "sharedGlobals": ["{workspaceRoot}/tsconfig.base.json"],
    "production": [
      "default",
      "!{projectRoot}/**/*.spec.@(ts|tsx)",
      "!{projectRoot}/tsconfig.spec.json"
    ]
  },
  "targetDefaults": {
    "build": { "cache": true, "dependsOn": ["^build"], "inputs": ["production", "^production"] },
    "test": { "cache": true, "inputs": ["default", "^production"] },
    "typecheck": { "cache": true }
  }
}
```

Key decisions:

- `tsconfig.base.json` moved into `sharedGlobals`: paths aliases affect the compilation of every project — changing it must invalidate everything. The price: editing any alias rebuilds the repo; that's an honest price.
- `production` is defined as `default` minus exclusions, not as a separate list — new file types automatically land in both sets, impossible to forget.
- `vite.config.ts` stays in production (edge case 1): build options are a direct input of the artifact. Subtract it and you get false hits on any build-config edit.

Step 2 — the matrix behaves as in the theory; `touch` hits on both because content is what's hashed ("content, not dates").

Steps 3–4 — the banner and reproducing the lie:

```ts
// apps/shell/vite.config.ts (fragment)
export default defineConfig({
  // ...
  define: {
    __SHOP_BANNER__: JSON.stringify(process.env.SHOP_BANNER ?? ''),
  },
});
```

```tsx
// apps/shell/src/app/app.tsx (fragment)
declare const __SHOP_BANNER__: string;
// ...
{__SHOP_BANNER__ && <div className="banner">{__SHOP_BANNER__}</div>}
```

```bash
SHOP_BANNER="Sale -20%" npx nx build shell
grep -ro "Sale -20%" dist/apps/shell/assets | head -1   # the banner is in the bundle

SHOP_BANNER="Black Friday" npx nx build shell
# > nx run shell:build  [local cache]        ← a HIT, the task never ran
grep -ro "Sale -20%" dist/apps/shell/assets | head -1   # the OLD banner is in the bundle!
```

No mystery: file contents didn't change, the target configuration didn't either, and env variables don't enter the hash by default — from Nx's point of view it's the same task, and it faithfully replayed its result.

Step 5 — repairing the contract (we override build's inputs; the array is replaced wholesale, so the base sets are repeated):

```json
{
  "targetDefaults": {
    "build": {
      "cache": true,
      "dependsOn": ["^build"],
      "inputs": ["production", "^production", { "env": "SHOP_BANNER" }]
    }
  }
}
```

```bash
SHOP_BANNER="Black Friday" npx nx build shell   # miss: the env value entered the hash
SHOP_BANNER="Black Friday" npx nx build shell   # hit: same content + same value
```

Answers to the remaining edge cases:

- Delete `dist/apps/shell` and run build — Nx restores the artifact from `.nx/cache` on a hit: outputs are stored in the cache in full; the dist folder is not a source of truth but a projection of the cache.
- `deploy` is a side effect by definition: its value is in the *execution*, not in file results. A cache hit on deploy means "didn't deploy, but said OK". For such tasks `"cache": false` is mandatory.

## Check yourself

1. A developer changed the value of an environment variable used by the build — Nx returned a cache hit with the old artifact. Is this an Nx bug? Explain what happened and name the cure.
2. Why must changing `*.spec.tsx` not invalidate `build` but must invalidate `test` — and which mechanism expresses that in configuration?
3. What exactly does Nx save into `.nx/cache` when a task runs, and what happens on a hit? Why is lint cached even though it creates no files?
4. A task consistently misses the cache on two consecutive runs with no edits at all. List the likely causes and the diagnostic order.
5. Why doesn't `touch`-ing a file invalidate the cache, and why doesn't a `git checkout` to another branch and back force a full rebuild?

<details>
<summary>Answers</summary>

1. Not a bug: env variables don't enter the hash until declared. File contents and configuration didn't change — to Nx it's the same task, and the replay is correct per the contract. The cure: add `{"env": "NAME"}` to the target's inputs (remembering that the inputs array is overridden wholesale — the base sets must be repeated). The general rule: everything a task reads that affects its result must be a hash input.
2. Specs don't participate in the production artifact: editing them cannot change the build result, so the build hash must not change. The mechanism is namedInputs: `production = default minus !*.spec.*`, then `build.inputs = ["production", "^production"]`, while `test.inputs = ["default", ...]` — specs are in default, so test invalidates and build doesn't.
3. It saves the files at the paths from outputs plus the full terminal output and exit code. On a hit the files are restored into place and the output is replayed to the terminal — indistinguishable from a real run except for speed. Lint has nothing to put in outputs, but its value is the verdict: stdout and the exit code are cached and replayed, which is enough.
4. Something in the hash changes between runs: (a) code generation writes into projectRoot before the task — input content mutates; (b) a file with a timestamp/unique value got into inputs; (c) a declared env/runtime input is unstable (e.g. `{"runtime": "date"}`); (d) prosaically — the target has `cache: false`. Diagnosis: confirm caching is on (`nx show project`), then hunt the mutating input — compare projectRoot state before and after the first run (git status will show uncommitted changes produced by the build).
5. Because the hash is computed from file **content**, not metadata: touch changes mtime but no bytes — same hash. Returning to the previous branch restores the previous content — hence the previous hashes, and every result replays from cache. The same property makes the cache portable across machines (remote cache, chapter 13): identical content yields an identical key anywhere.

</details>

## Common mistake

A developer from the single-app world, bitten by a false hit for the first time, reacts the familiar way: "the cache can't be trusted" — and soon `--skip-nx-cache` is baked into CI, a local alias runs `rm -rf dist .nx`, and "problematic" targets get `cache: false`. This is clean-build cargo cult: the problem wasn't the cache but one undeclared input, fixable with one line. A disabled cache deceives no one — but it also saves no one a second, and turns the flagship Nx feature into dead weight. The correct reflex: a false hit = a hole in the inputs contract; find the input, declare it, and the cache is honest again.

The symmetric mistake is caching what must not be cached. A classic: the team adds a `deploy` or `db:migrate` target, forgets `"cache": false` — and one day the deploy "passes" in 40 milliseconds with a green checkmark, because the hash matched yesterday's. For side-effect tasks the result is neither files nor stdout but a change in the outside world; memoization is meaningless there by definition. The rule is simple: pure functions get cached (build, test, lint, typecheck); anything that touches the network, a database or production gets an explicit, permanent `cache: false`.
