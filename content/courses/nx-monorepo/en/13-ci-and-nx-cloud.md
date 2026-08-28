# CI for a monorepo and Nx Cloud

## Theory

### Assembling the kit: affected + cache + the right base

We have learned every part of the continuous integration (CI) pipeline separately. This chapter assembles them into one conveyor:

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

The only new piece is the `nrwl/nx-set-shas` action in the second block. From chapter 05 we know what the base must be: the last state CI actually verified. For a pull request (PR) that state is the merge-base with main, and Nx computes it itself. For a push to main, `HEAD~1` is a trap.

nx-set-shas asks the GitHub API for the commit hash (SHA) of the last **successful** workflow run on main. It puts that hash into `NX_BASE` and the current one into `NX_HEAD`. Both variables are read by affected automatically. If yesterday's run failed, today's run compares against the day-before-yesterday's success, so not a single commit goes unverified.

### Why the local cache isn't enough

The local `.nx/cache` (chapter 04) lives on one machine. CI agents are ephemeral: every run starts with a clean file system, and the whole cache is discarded with the container. Add the team math: twenty developers build the same unchanged lib twenty times.

The answer is a **remote cache**: a shared "hash → artifacts + stdout" store on top of the same mechanics. This is where chapter 04's content addressing pays off. The hash is computed from file contents, so the same commit yields the same key on any machine. A task executed by one agent — or by one colleague — becomes a replay for everyone.

There are two implementations. **Nx Cloud** is the official hosted service, and it connects in a minute: `npx nx connect`. If your data cannot leave the company, you run a self-hosted cache server that implements the Nx remote-cache API and point `NX_SELF_HOSTED_REMOTE_CACHE_SERVER` at it. The store behind it used to be Amazon S3 (Simple Storage Service) or a similar bucket, which is exactly what the note below is about.

> **Versions.** Older repos may contain community remote-cache plugins over Amazon S3. They worked through an undocumented task-runner API that Nx has since closed. If you see `tasksRunnerOptions` with a custom runner in nx.json, that is the same layer, and a migration will have to revisit it.

> **Security.** Bucket-backed cache packages are gone, not merely dated. Four of them were deprecated on 2026-05-21: `@nx/s3-cache`, `@nx/gcs-cache`, `@nx/azure-cache` and `@nx/shared-fs-cache`.

> The reason is CREEP (cache race-condition exploit enables poisoning). It is filed as CVE-2025-36852 with a severity of 9.4; a published vulnerability gets an identifier in the common vulnerabilities and exposures (CVE) list.

> The attack itself is short to state. Any contributor allowed to open a pull request can plant an artifact that later runs in production. Nx states the flaw sits in the design of those packages and cannot be patched, so do not add them to a repo today.

### Tokens and cache poisoning

A remote cache holds executable artifacts that get downloaded and run, so access has two levels:

- A **read-only** token: can fetch hits, cannot write. For developers' local machines and especially for CI on PRs from forks.
- **read-write**: full access. Only for trusted pipelines (main), with the token in CI secrets, not in nx.json.

The threat all this exists for is **cache poisoning**. Whoever can write to the cache can plant a malicious artifact under a hash that tomorrow's production build will match. Their code then silently "restores from cache" into the production bundle. Hence the rule with no exceptions: untrusted code from forks and local machines never gets write access.

### Distributed task execution: sharding by the graph

When even the affected list is large, tasks can be spread across machines. The manual route is a CI job matrix: "agent 1 builds apps/a…", "agent 2 tests libs/x…". Such a matrix is static and ignores dependencies.

**Distributed task execution (DTE)** in Nx Cloud does it dynamically. The main job publishes the task graph, and N agents pick tasks off it. The agents honour `dependsOn` and balance on historical timings. The cache is shared by all of them, and the logs are stitched into one stream, as if everything ran on a single machine.

One line enables it: `--distribute-on="5 linux-medium-js"`. The key distinction from a matrix is what gets sharded: the **task graph**, not a project list.

### nx migrate: upgrades as codemods

You can't upgrade Nx by hand — we've known that since chapter 00 (the core and the plugins move in lockstep, versions pinned exactly). The official mechanism has two phases:

```bash
npx nx migrate latest        # phase 1: updates versions in package.json
                             # and generates migrations.json — the codemod list
npm install
npx nx migrate --run-migrations   # phase 2: runs the codemods over the repo
```

Migrations are the same generators from chapter 07, only written by the Nx team. They rewrite nx.json to the new schema, move project.json onto inferred targets, and update tool configs. That is exactly how repos survived transitions like "executors → crystal" without manual refactoring.

Commit `migrations.json` into the upgrade PR. Colleagues and CI can then reproduce the run, and the file is deleted after the merge. Hoarding majors means hoarding migration debt: two or three skipped majors turn an hour-long upgrade into a week-long project.

## In a real-world monorepo

- Open the CI config: is it `nx affected` (and how is the base computed — nx-set-shas or a hardcode?), or `run-many`/manual lists? A 30-second maturity diagnosis of the pipeline.
- Search the CI logs for `[remote cache]` / "Nx Cloud": are there remote hits. Every run builds everything from scratch → no remote cache, the team pays for the same builds over and over.
- `grep -i "nxCloud\|accessToken" nx.json .env* 2>/dev/null` shows how Nx Cloud is wired. Crucially, it also shows whether a write token is committed into the repo, and that token belongs in CI secrets.
- Run `git log --oneline -- package.json | head` and look for pull requests carrying a `migrations.json`. Does the team upgrade Nx via migrate, or by hand? Upgrading by hand explains many config oddities.
- Compare two runs: a PR that changes one lib's `README`, and a PR into a popular lib. If both take equally long, affected or the cache is not working. You have just found the cheapest performance win in the company.

## What we're adding to the project

CI on GitHub Actions. The PR pipeline runs `nx affected` with the right base. A deploy job on main uses our chapter 08 executor to "deploy" only the affected apps of the federation, each one independently.

## Practical exercise

**Input:** the workspace after chapter 12 (a GitHub repo, or the willingness to review the workflow locally).

**Task:**

1. Write `.github/workflows/ci.yml`. It triggers on push to main and pull_request, and starts with a full-history checkout. The steps are: `nrwl/nx-set-shas`; setup-node with an npm cache; `npm ci`; `nx affected -t lint,test,typecheck,build`. Explain, in comments inside the file, why `fetch-depth: 0` and set-shas are needed.
2. Add a `deploy` job running only on push to main after a successful `main` job: `nx affected -t deploy`. Explain why this is exactly "independent microfrontend deploys", automated.
3. Verify the pipeline locally by simulating CI. Run `NX_BASE=<SHA> NX_HEAD=HEAD npx nx affected -t lint,test,typecheck,build` with different bases. Confirm that the task list changes accordingly.
4. Design, in writing, a remote-cache token scheme for a 10-person team with public pull requests from contractors. Answer four questions: who gets read, who gets write, where each token is stored, and why.
5. Study the migrate mechanics risk-free. In a throwaway branch run `npx nx migrate latest`, then read the package.json diff and `migrations.json`. Note which codemods are planned and for which packages, then discard the branch. If you are already on the latest version, target the previous major instead: `nx migrate 20.0.0` from an older copy. You can also dissect the migrations.json structure using the docs.

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

- **One command instead of stages** — `affected -t lint,test,typecheck,build`. Ordering and parallelism are delegated to the task graph (chapter 03), so there is no stage that runs all lint first.
- **Deploy through affected**: catalog-feature changed → only catalog deploys. Changed shared-ui deploys all of its consumers, which is chapter 11's "coordinated deploys" strategy, automated. A `README`-only PR deploys nothing. Our chapter 08 deploy executor didn't change by a line — context made it portable.
- Without a remote cache this pipeline is already correct, just colder: each agent recomputes its own misses. Connecting Nx Cloud (`npx nx connect`) adds cross-run hits without touching the workflow file.

Step 4 — the token scheme. The read-only token lives in `nx.json`, because it is not a secret: it only fetches hits. That token is for local machines.

The read-write token lives exclusively in GitHub Secrets and is available only to the workflow on `main`. Jobs for fork pull requests do not receive secrets at all, which is GitHub's default and works in our favour. Contractors and forks therefore stay read-only automatically.

Test any scheme with one question. Can code from an untrusted PR write something that will later execute for someone else? The answer must always be no.

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

Every entry is a generator (chapter 07) from a specific package. Phase 1 only *plans* the list, from your current version to the target; phase 2 executes it. That makes upgrades reproducible: commit migrations.json, and any colleague runs the same codemods.

Answers to the edge cases:

- Flaky test plus cache: the green result lands in the remote cache. **All** runs with the same hash then replay it without executing, so the flake is frozen in until the inputs change. This is chapter 04 at team scale: the cache is honest, the test is not. The cure is to fix or quarantine flaky tests, not to disable the cache.
- A secret baked into the bundle ends up in the remote cache as part of the artifact. Anyone with a read token can read it, which under our scheme means the whole team and every fork. Secrets do not belong in build artifacts at all, and the cache merely makes the leak wider and longer-lived.
- nx.json is a global file (chapter 05): affected = the whole repo, the longest possible run (softened by the cache). That's why config edits and bulk dependency updates should travel in dedicated PRs — otherwise every feature that grazes nx.json pays for a full run.

## Check yourself

1. Why is the Nx cache portable across machines without any state synchronization? Which property of the hash provides that, and which chapter 04 condition must hold?
2. Describe the cache poisoning attack and list which decisions in the token scheme counter it.
3. A push to main failed; the next one passed. Which SHA did the second run compare against under nx-set-shas, and what would happen with `--base=HEAD~1`?
4. How is DTE fundamentally different from a job matrix with projects manually split across agents?
5. A colleague suggests upgrading Nx by editing the versions in package.json by hand: "npm install and done". Which two classes of problems will they hit, and what does the correct process look like?

<details>
<summary>Answers</summary>

1. The hash is computed from content: the files listed in inputs, the configuration, and dependency versions. It is not computed from paths, timestamps or machine state, so the same commit yields the same key anywhere. The condition is the same as for the local cache: declared inputs and outputs match reality. An undeclared input that differs between machines — an env variable, a global config — turns portability into a source of foreign artifacts.
2. An attacker with write access plants a malicious artifact under a key that will match the hash of a future trusted build. The production pipeline then "restores" their code from the cache without executing anything. Three decisions counter that. The write token belongs only to trusted pipelines and lives only in CI secrets. Fork pull requests and local machines are strictly read-only. Secrets are unavailable to fork jobs, which is GitHub's default.
3. Against the SHA of the last **successful** run, which is the commit before the failed one. The range covered both the failed commit and the new one, so nothing was lost. With `HEAD~1` the second run would compare only against the failed commit. Its changes would then count as verified by a red run that nobody fixed, and some regressions would ship unchecked.
4. A matrix shards a static list with no knowledge of dependencies. An agent may draw an app's build before another agent has built its lib, and balancing is guesswork. DTE hands out tasks from the task graph dynamically. It honours dependsOn across agents, shares one cache, balances on real timings and stitches the logs into a single output. The graph is sharded, not a list.
5. First class — version drift. The nx core and the @nx/* plugins must match (chapter 00), and a manual bump easily leaves some packages behind. The errors then come from deep inside node_modules. Second class — skipped codemods. The new version expects the new config formats: nx.json, module federation (MF) configs, inferred targets. Meanwhile the repo stays on the old ones. Things appear to work through undocumented backward compatibility, and the next upgrade becomes even heavier. Correct order: `nx migrate latest` → npm install → `nx migrate --run-migrations` → run the affected checks → commit together with migrations.json.

</details>

## Common mistake

A developer from the single-app world transplants the familiar CI template into the monorepo. There is a lint job, a test job and a build job. Each of them runs `npm run <script>` over the whole repo, with artifacts and waiting in between. The pipeline works, but it uses neither the graph, nor the cache, nor affected. Run time therefore grows linearly with the number of projects.

The diagnosis takes one glance at the config: is there `nx affected`, and how is the base set? The cure is almost always a *simplification*. Three jobs collapse into one command that knows more about dependencies than any hand-written config ever will. The success criterion is counterintuitive: the less orchestration in the CI config, the more of it Nx is doing.

The second mistake is upgrading Nx like a regular dependency: bump the numbers in package.json and trust semver. Nx is not a library but a platform with a config schema. Between majors the formats of nx.json, project.json and MF configs change. All of that refactoring is encoded in migration codemods, and a manual upgrade simply never runs them.

After such an "upgrade" the repo runs on old formats through a backward-compatibility layer. Oddities accumulate, the team concludes that upgrading is dangerous, and the version gets frozen while the migration debt grows. The correct cycle is cheap if you run it regularly: migrate on every major, run the migrations, and run the affected checks. The repo then stays one step away from current.
