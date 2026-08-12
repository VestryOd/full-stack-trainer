# Affected: rebuild only what was touched

## Theory

### The mechanics: from git diff to a task list

`nx affected` answers "what could *these* changes have broken" — and runs tasks only for that subset. The pipeline:

```
┌──────────────────────────────────────────────────────────┐
│ git merge-base(base, head) → git diff                    │
│ the list of changed files                                │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ each file → its owning project                           │
│ (by projectRoot; outside all projects = a global change) │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ closure UP the graph:                                    │
│ + everyone who depends on the changed (transitively)     │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ nx affected -t lint,test,build:                          │
│ a regular task graph, but only for the affected          │
└──────────────────────────────────────────────────────────┘
```

Three details worth seeing here:

- **merge-base, not a direct diff.** Nx compares head not with `--base` itself but with the *branching point* (`git merge-base`). So commits merged into main after you branched off don't inflate your affected set: only what you did is compared. The default base is `defaultBase` from nx.json (we saw it back in chapter 00).
- **The closure goes up — towards dependents.** Change `shared-ui` → affected are `shared-ui` and everyone depending on it (`shell`), transitively to the very top. It doesn't go down (to `shared-ui`'s dependencies): nobody changed them. But don't mix the levels: when a `build` task is created for the affected `shell`, the `dependsOn: ["^build"]` rule from chapter 03 will, as usual, pull in the build tasks of its dependencies — as prerequisites, most likely replayed from cache.
- **A file outside all projects = a global change.** `nx.json`, the root `package.json`, the lock file have no owning project — Nx conservatively marks **everything** as affected. This is a feature: changing dependency versions or pipeline rules can honestly break anything. The practical consequence: bulk dependency updates should travel in separate PRs, not mixed with features.

### Why affected is the main CI scaling mechanism

Recall the arithmetic from chapter 00: naive CI time = number of projects × average task time, and the first factor grows with the repo. The cache (chapter 04) removes re-execution of the *unchanged*, but the task list is still linear: a thousand cache hits is a thousand cache lookups. Affected attacks the list itself: exactly as many tasks are created as are affected. The two mechanisms work at different levels and compose: **affected narrows "what to run", the cache removes repeats within that list**. A PR changing one lib in a 300-project repo spawns a dozen tasks — and some of those are hits on top.

An important nuance at the boundary of the levels: affected operates on *projects*, the cache on *hashes*. Editing `app.spec.tsx` makes the `shell` project affected → the `shell:build` task will be created. But its hash didn't change (specs are subtracted from `production`, chapter 04) → the task instantly replays from cache. Affected is the coarse filter, the cache is the precise one; they don't duplicate each other — they back each other up.

### Useless without a correct graph

`nx affected` is no smarter than the graph it computes the closure over. Three ways to get garbage out of it:

- **Missing edges.** The classic — an e2e project without `implicitDependencies` (chapter 02): you change the app, e2e isn't in affected, CI is green, the regression ships. An edge absent from the graph is a test that will not run.
- **Oversized libs.** One `shared/utils` for the whole repo where everything gets dumped → everyone depends on it → any edit there makes affected ≈ the entire repo. The precision of affected equals the granularity of the graph; the push for small libs with clear boundaries (chapter 06) is also a push for cheap CI.
- **Relationships that bypass imports.** A script reads another project's file via `fs.readFile`, a build pulls a neighbour's artifact by a hardcoded path — the graph doesn't see such links, affected doesn't account for them. Same rule as chapter 02: a dependency must be expressed as an import or an implicit edge.

### The commands

```bash
nx affected -t build                       # affected build tasks (base = defaultBase)
nx affected -t lint,test,build             # the pipeline over the affected
nx show projects --affected                # just the LIST of projects, no execution
nx affected --graph                        # visual: who is affected and through which edges
nx affected -t test --base=origin/main --head=HEAD   # explicit comparison bounds
nx affected -t build --exclude='*-e2e'     # exclude by pattern
```

## In a real-world monorepo

- Before pushing: `nx affected -t lint,test --base=origin/main` — run locally exactly what your PR touches, not the whole repo.
- `nx show projects --affected --base=origin/main` — a one-second answer to "who did I touch"; useful before review to understand the blast radius.
- `nx affected --graph --base=origin/main` — when the list surprises you: it shows the chain of edges from your edit to the unexpected project (the same job as path tracing from chapter 02, but for the current diff).
- In the repo's CI config, find how the base is computed: a hardcoded `--base=HEAD~1` is a red flag (squash merges and skipped runs lose changes); the correct pattern is the SHA of the last successful run (in GitHub Actions that's `nrwl/nx-set-shas`, chapter 13).
- A graph health metric: edit the most popular lib → `nx show projects --affected | wc -l`. If almost any edit affects almost everything, the repo has a granularity problem — cured by chapter 06, not by disabling affected.

## What we're adding to the project

The mini-shop code doesn't change — we simulate CI locally: a branch with a one-lib edit, a walkthrough of the affected list at every level (projects → tasks → cache), and a check of the global boundary via an nx.json edit.

## Practical exercise

**Input:** the workspace after chapter 04 (namedInputs configured, everything committed to `main`).

**Task:**

1. Branch off `feat/ghost-button` and edit `libs/shared/ui/src/lib/button.tsx` (e.g. a new button variant). Commit.
2. Without running any tasks, get the list of affected projects relative to `main` and explain every item on it.
3. Run `nx affected -t lint,test,typecheck,build --base=main` and analyze: which tasks were created, for which projects, why `build` was created only for shell.
4. In a second commit change **only** `apps/shell/src/app/app.spec.tsx` and run affected with build again: explain why the `shell:build` task was created yet executed from cache.
5. In a third commit edit `nx.json` — and show that every project became affected. Explain the mechanism.
6. Verify merge-base: commit to `main` (a README edit) after branching — confirm the branch's affected set didn't change.

**Edge cases to think about:**

- Is deleting a file a change? What about renaming a lib's folder?
- What does affected show on a branch with no commits yet?
- Why does `--base=HEAD~1` in CI on push events lose changes?

## Worked solution

Steps 1–3 — the lib edit:

```bash
git switch -c feat/ghost-button
# ... edit button.tsx ...
git commit -am "feat: ghost button variant"

npx nx show projects --affected --base=main
# shared-ui
# shell

npx nx affected -t lint,test,typecheck,build --base=main
#    ✔  nx run shared-ui:lint
#    ✔  nx run shared-ui:test
#    ✔  nx run shell:lint
#    ✔  nx run shell:typecheck
#    ✔  nx run shell:test
#    ✔  nx run shell:build
```

Reading the list: `shared-ui` owns the changed file; `shell` comes from the upward closure (it depends on shared-ui through the edge from chapter 02). The `build` task exists only for shell: shared-ui has no `build` target (non-buildable), and the `^build` rule added no tasks for it — nothing to add. shared-ui's `lint` next to shell's `typecheck`+`test` is the usual parallelism from chapter 03.

Step 4 — a spec-only edit:

```bash
npx nx affected -t build --base=main
#    ✔  nx run shell:build  [local cache]
```

Two filters at two levels: affected sees "the shell project changed" (the spec is the project's file) and creates the task; the cache sees "the hash didn't change" (specs are subtracted from production inputs) and replays. Neither level made a mistake — they answer different questions.

Step 5 — the global boundary:

```bash
# edit targetDefaults in nx.json
npx nx show projects --affected --base=main
# shared-ui
# shell          ← every project in the repo
```

nx.json has no owning project → Nx treats the change as global → everything is affected. Same for package.json and the lock file: a "bumped 40 dependencies + a small feature" PR runs full CI — which is why bulk updates travel separately.

Step 6 — merge-base: a commit to main after branching doesn't enter the diff, because the comparison starts from the branching point (`git merge-base main HEAD`), not from main's tip. The branch's affected set is unchanged.

Answers to the edge cases:

- Deleting a file is a full-fledged change to the project's files (the diff sees it), the project is affected. Renaming a lib's folder means changing all of its files + editing tsconfig.base.json (a global file!) → effectively the whole repo is affected; lib moves are best done as a dedicated PR (and with the `@nx/workspace:move` generator, chapter 07).
- A branch with no commits: the diff is empty — affected is empty; but Nx also accounts for uncommitted and untracked files — so affected works locally even before you commit.
- `--base=HEAD~1` compares only with the previous commit: a squash merge of five commits, a skipped CI run, a force-push — each scenario leaves changes that never appear in any diff. The base must be "the last state CI actually verified" — which is exactly what nx-set-shas maintains.

## Check yourself

1. Describe the full pipeline of `nx affected -t test --base=main`: the four stages from git to tasks.
2. Why does the graph closure go only upward (to dependents), and how do dependency build tasks still end up executing?
3. A teammate merged a big refactoring into main; your branch was cut a week ago. Does that inflate your affected set, and why?
4. A spec-file edit: why does `nx affected -t build` create the build task, yet it doesn't execute? Which two mechanisms fired, and at which levels?
5. The repo has one giant `shared/common` lib that all 50 apps depend on. What happens to affected on any edit inside it, and what's the cure?

<details>
<summary>Answers</summary>

1. (1) `git merge-base main HEAD` finds the branching point; `git diff` from it to head yields the changed files (plus uncommitted ones). (2) Each file maps to a project by projectRoot; files outside any project mark a global change. (3) The affected set = changed projects + the transitive "who depends on them" closure up the project graph. (4) For the affected projects a regular task graph for the `test` target is built (with dependsOn, parallelism, cache) and executed.
2. A change can only break those who *use* what changed — they are the ones to recheck; nobody touched the changed project's dependencies, so rerunning their tests is pointless. Still, if an affected project's `build` needs built dependencies, `dependsOn: ["^build"]` creates those tasks as prerequisites in the task graph — they aren't "affected", they simply execute (and are almost always closed by the cache).
3. No. Nx compares not with main's tip but with the merge-base — the common ancestor of the branch and main. The refactoring was merged after branching and is absent from your history; only your changes enter the diff. (A separate matter: after rebasing onto fresh main, affected will honestly grow if the refactoring touched your dependencies.)
4. Affected works at the project level: the spec belongs to shell → shell is affected → `shell:build` enters the plan. The cache works at the hash level: build's inputs are `production`, specs are subtracted from it → the hash matches the previous one → a replay from `.nx/cache` instead of execution. The coarse filter decided "check it", the precise one decided "nothing to execute".
5. Any edit in `shared/common` affects it + all 50 consumers — affected degenerates into "everything", CI is linear again. The cure is granularity: split the lib by purpose (ui / util / data-access, chapter 06) so each part has its own narrow circle of consumers. Disabling affected or splitting the repo back into polyrepo fights the symptom.

</details>

## Common mistake

A developer from the single-app world distrusts "partial" CI: how can a PR pass when not the whole repo was built? So `nx run-many -t build` appears in CI "just in case" — the entire point of scaling is thrown away, the pipeline grows linearly with the repo again, and six months later the team complains about forty-minute pipelines. Trusting affected means trusting the graph: if the graph is complete (edges + implicit ones for e2e), then "not affected" mathematically means "could not have been broken by this diff". Fix the incomplete graph, don't widen the run list.

The opposite extreme is a homemade affected: `--base=HEAD~1`, "let's just compare with the previous commit". On a push after a squash merge of five commits, CI compares against a state where four of them were already included... and silently skips checking the first. A skipped run, a manual re-run, a force-push — every scenario leaves unverified changes behind. The base for affected is not "the previous commit" but "the last state CI verified successfully"; the ecosystem solves this with a ready-made action (`nrwl/nx-set-shas`), which we'll wire up in chapter 13.
