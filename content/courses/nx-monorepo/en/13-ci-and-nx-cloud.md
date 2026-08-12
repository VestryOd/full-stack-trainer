# CI for a monorepo and Nx Cloud

## Theory

### Assembling the kit: affected + cache + the right base

We've learned every part of the CI pipeline separately; this chapter assembles them into a conveyor:

```
┌─────────────────────────────────────────────┐
│ event: push to main / pull_request          │
└─────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│ nrwl/nx-set-shas: NX_BASE = the SHA         │
│ of the last SUCCESSFUL CI run               │
└─────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│ nx affected -t lint,test,typecheck,build:   │
│ tasks for affected projects only            │
└─────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│ every task: hash → remote cache:            │
│ hit → replay in ms; miss → run and record   │
└─────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│ push to main only: nx affected -t deploy —  │
│ independent deploys of the affected remotes │
└─────────────────────────────────────────────┘
```

The only new piece is the `nrwl/nx-set-shas` action in the second block. From chapter 05 we know the base must be "the last state CI actually verified": for a PR that's the merge-base with main (Nx computes it itself), but for a push to main, `HEAD~1` is a trap. nx-set-shas asks the GitHub API for the SHA of the last **successful** workflow run on main and puts it into `NX_BASE` (the current one into `NX_HEAD`); affected reads these variables automatically. If yesterday's run failed, today's compares against the day-before-yesterday's success — and not a single commit goes unverified.

### Why the local cache isn't enough

The local `.nx/cache` (chapter 04) lives on a machine — and CI agents are ephemeral: every run starts with a clean file system, and the whole cache is discarded with the container. Add the team math: twenty developers build the same unchanged lib twenty times. The answer is a **remote cache**: a shared "hash → artifacts + stdout" store on top of the same mechanics. This is where chapter 04's content addressing pays off: the hash is computed from file contents, so the same commit yields the same key on any machine — a task executed by one agent (or one colleague) becomes a replay for everyone.

Implementations: **Nx Cloud** — the official SaaS (connected in a minute: `npx nx connect`); for those who can't send data out — a self-hosted cache on S3/GCS/a network share via Nx Powerpack (paid, but no third-party infrastructure).

> **Versions.** Older repos may contain community remote-cache plugins over S3 — they worked through an undocumented task-runner API that Nx has since closed in favour of Nx Cloud/Powerpack. If you see `tasksRunnerOptions` with a custom runner in nx.json — that's that layer; a migration will have to revisit it.

### Tokens and cache poisoning

A remote cache holds executable artifacts that get downloaded and run, so access has two levels:

- A **read-only** token: can fetch hits, cannot write. For developers' local machines and especially for CI on PRs from forks.
- **read-write**: full access. Only for trusted pipelines (main), with the token in CI secrets, not in nx.json.

The threat all this exists for: **cache poisoning**. Whoever can write to the cache can plant a malicious artifact under a hash that tomorrow's production build will match — and their code silently "restores from cache" into the production bundle. Hence the rule with no exceptions: untrusted code (forks, local machines) never gets write access.

### Distributed task execution: sharding by the graph

When even the affected list is large, tasks can be spread across machines. The manual route — a CI job matrix ("agent 1 builds apps/a…", "agent 2 tests libs/x…") — is static and ignores dependencies. **DTE** (Nx Cloud) does it dynamically: the main job publishes the task graph, N agents pick tasks off it honouring `dependsOn` and balancing on historical timings, the cache is shared by all, and the logs are stitched into one stream as if everything ran on a single machine. Enabled with one line (`--distribute-on="5 linux-medium-js"`); the key distinction from a matrix: what gets sharded is the **task graph**, not a project list.

### nx migrate: upgrades as codemods

You can't upgrade Nx by hand — we've known that since chapter 00 (the core and the plugins move in lockstep, versions pinned exactly). The official mechanism has two phases:

```bash
npx nx migrate latest        # phase 1: updates versions in package.json
                             # and generates migrations.json — the codemod list
npm install
npx nx migrate --run-migrations   # phase 2: runs the codemods over the repo
```

Migrations are the same generators from chapter 07, just written by the Nx team: they rewrite nx.json to the new schema, move project.json onto inferred targets, update tool configs. That's exactly how repos survived transitions like "executors → crystal" without manual refactoring. `migrations.json` is worth committing into the upgrade PR: colleagues and CI can reproduce the run, and the file is deleted after the merge. Hoarding majors means hoarding migration debt: two or three skipped majors turn an hour-long upgrade into a week-long project.

## In a real-world monorepo

- Open the CI config: is it `nx affected` (and how is the base computed — nx-set-shas or a hardcode?), or `run-many`/manual lists? A 30-second maturity diagnosis of the pipeline.
- Search the CI logs for `[remote cache]` / "Nx Cloud": are there remote hits. Every run builds everything from scratch → no remote cache, the team pays for the same builds over and over.
- `grep -i "nxCloud\|accessToken" nx.json .env* 2>/dev/null` — how Nx Cloud is wired and, crucially, whether a write token is committed into the repo (it belongs in CI secrets).
- `git log --oneline -- package.json | head` + look for PRs with a `migrations.json`: does the team upgrade Nx via migrate or "by hand" (the latter explains many config oddities).
- Compare CI time on a PR changing one lib's README versus a PR into a popular lib: if both take equally long — affected or the cache isn't working, and you've found the cheapest performance win in the company.

## What we're adding to the project

CI on GitHub Actions: a PR pipeline on `nx affected` with the right base, and a deploy job on main that uses our chapter 08 executor to independently "deploy" only the affected apps of the federation.

## Practical exercise

**Input:** the workspace after chapter 12 (a GitHub repo, or the willingness to review the workflow locally).

**Task:**

1. Write `.github/workflows/ci.yml`: triggers push to main + pull_request; a full-history checkout; `nrwl/nx-set-shas`; setup-node with an npm cache; `npm ci`; `nx affected -t lint,test,typecheck,build`. Explain (in comments inside the file) why `fetch-depth: 0` and set-shas are needed.
2. Add a `deploy` job running only on push to main after a successful `main` job: `nx affected -t deploy`. Explain why this is exactly "independent microfrontend deploys", automated.
3. Verify the pipeline locally by simulating CI: `NX_BASE=<SHA> NX_HEAD=HEAD npx nx affected -t lint,test,typecheck,build` with different bases — confirm the task list changes accordingly.
4. Design, in writing, a remote-cache token scheme for a 10-person team with public PRs from contractors: who gets read, who gets write, where each token is stored, and why.
5. Study the migrate mechanics risk-free: in a throwaway branch run `npx nx migrate latest`, read the package.json diff and `migrations.json` (which codemods are planned, for which packages), then discard the branch. If you're already on the latest version — target the previous major from an older copy, or dissect the migrations.json structure using the docs.

**Edge cases to think about:**

- A flaky test passed in CI and landed in the remote cache. What do subsequent runs see, and why is this worse than a flaky test without a cache?
- The build bakes a secret from env into the bundle. What ends up in the remote cache, and who can read it?
- A PR changes a lib and nx.json at the same time. What happens to the affected list and the run time?

## Worked solution

Steps 1–2 — the entire workflow:

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  main:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          # full history: merge-base and set-shas don't work on a shallow clone
          fetch-depth: 0

      # NX_BASE = the SHA of the last successful run on main (merge-base for PRs);
      # without it, affected on push would compare with HEAD~1 and lose commits (ch. 05)
      - uses: nrwl/nx-set-shas@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm

      - run: npm ci

      - run: npx nx affected -t lint,test,typecheck,build

  deploy:
    # deploy only from main and only after a green check
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    needs: main
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: nrwl/nx-set-shas@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
      - run: npm ci
      - run: npx nx affected -t deploy
```

Key decisions:

- **One command instead of stages** — `affected -t lint,test,typecheck,build`: ordering and parallelism are delegated to the task graph (chapter 03); no "all lint first".
- **Deploy through affected**: catalog-feature changed → only catalog deploys; shared-ui changed → all of its consumers (chapter 11's "coordinated deploys" strategy, automated); a README-only PR deploys nothing. Our chapter 08 deploy executor didn't change by a line — context made it portable.
- Without a remote cache this pipeline is already correct, just colder: each agent recomputes its own misses. Connecting Nx Cloud (`npx nx connect`) adds cross-run hits with no YAML changes.

Step 4 — the token scheme: read-only in `nx.json` (it's not a secret: hits only) for local machines; read-write exclusively in GitHub Secrets, available only to the workflow on `main` (fork PR jobs don't receive secrets — GitHub's default, and it works in our favour). Contractors and forks automatically stay read-only. The one-question test of any scheme: "can code from an untrusted PR write something that will later execute for someone else?" — the answer must be "no".

Step 5 — a typical migrations.json:

```json
{
  "migrations": [
    {
      "package": "@nx/react",
      "version": "21.0.0-beta.3",
      "name": "update-module-federation-config",
      "description": "Migrate MF config to the new @nx/module-federation format"
    }
  ]
}
```

Every entry is a generator (chapter 07) from a specific package: phase 1 only *plans* the list from your current version to the target, phase 2 executes it. That makes upgrades reproducible: commit migrations.json and any colleague runs the same codemods.

Answers to the edge cases:

- Flaky test + cache: the green result lands in the remote cache, and **all** runs with the same hash replay it without executing — the flake is "frozen in" until the inputs change. It's chapter 04 (the cache is honest, the test isn't) at team scale: cured by fixing/quarantining flaky tests, not by disabling the cache.
- A secret baked into the bundle ends up in the remote cache as part of the artifact — readable by anyone with a read token, i.e. under our scheme the whole team and every fork. Secrets don't belong in build artifacts, period; the cache merely makes the leak wider and longer-lived.
- nx.json is a global file (chapter 05): affected = the whole repo, the longest possible run (softened by the cache). That's why config edits and bulk dependency updates should travel in dedicated PRs — otherwise every feature that grazes nx.json pays for a full run.

## Check yourself

1. Why is the Nx cache portable across machines without any state synchronization? Which property of the hash provides that, and which chapter 04 condition must hold?
2. Describe the cache poisoning attack and list which decisions in the token scheme counter it.
3. A push to main failed; the next one passed. Which SHA did the second run compare against under nx-set-shas, and what would happen with `--base=HEAD~1`?
4. How is DTE fundamentally different from a job matrix with projects manually split across agents?
5. A colleague suggests upgrading Nx by editing the versions in package.json by hand: "npm install and done". Which two classes of problems will they hit, and what does the correct process look like?

<details>
<summary>Answers</summary>

1. The hash is computed from content (files per inputs, the configuration, dependency versions), not from paths, timestamps or machine state — the same commit yields the same key anywhere. The condition is the same as for the local cache: declared inputs/outputs match reality; an undeclared input that differs between machines (env, a global config) turns portability into a source of "foreign" artifacts.
2. An attacker with write access plants a malicious artifact under a key that will match the hash of a future trusted build — and the production pipeline "restores" their code from the cache without executing anything. Countered by: the write token belonging only to trusted pipelines and living only in CI secrets; fork PRs and local machines strictly read-only; secrets being unavailable to fork jobs (GitHub's default).
3. Against the SHA of the last **successful** run — i.e. the commit before the failed one: the range covered both the failed and the new commit, nothing was lost. With `HEAD~1` the second run would compare only against the failed commit — its changes would count as "verified" by a red run nobody fixed, and some regressions would ship unchecked.
4. A matrix shards a static list with no knowledge of dependencies: an agent may draw an app's build before another agent has built its lib, and balancing is guesswork. DTE hands out tasks from the task graph dynamically: it honours dependsOn across agents, shares one cache, balances on real timings and stitches the logs into a single output. The graph is sharded, not a list.
5. First class — version drift: the nx core and the @nx/* plugins must match (chapter 00), and a manual bump easily leaves some packages behind, with errors from deep inside node_modules. Second — skipped codemods: the new version expects the new config formats (nx.json, MF configs, inferred targets) while the repo stays on the old ones; things appear to work via undocumented backward compatibility, and the next upgrade becomes even heavier. Correct: `nx migrate latest` → npm install → `nx migrate --run-migrations` → run the affected checks → commit together with migrations.json.

</details>

## Common mistake

A developer from the single-app world transplants the familiar CI template into the monorepo: a lint job, a test job, a build job, each running `npm run <script>` over the whole repo, with artifacts and waiting in between. The pipeline works, but uses neither the graph, nor the cache, nor affected — and run time grows linearly with the number of projects. The diagnosis takes one glance at the config (is there `nx affected`? how is the base set?), and the cure is almost always a *simplification*: three jobs collapse into one command that knows more about dependencies than any YAML ever will. The success criterion is counterintuitive: the less orchestration in the CI config, the more of it Nx is doing.

The second mistake is upgrading Nx like a regular dependency: bump the numbers in package.json and trust semver. Nx isn't a library but a platform with a config schema: between majors the formats of nx.json, project.json and MF configs change, and all of that refactoring is encoded in migration codemods — which a manual upgrade simply never runs. After such an "upgrade" the repo runs on old formats through a backward-compatibility layer, oddities accumulate, and the team concludes "upgrading is dangerous" — freezing the version and growing the migration debt. The correct cycle is cheap if you run it regularly: migrate on every major, run the migrations, run the affected checks — and the repo stays one step away from current.
