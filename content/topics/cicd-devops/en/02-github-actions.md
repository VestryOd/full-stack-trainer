# GitHub Actions

## What GitHub Actions is

**GitHub Actions** is GitHub's built-in CI/CD (Continuous Integration / Continuous Delivery) platform. Instead of connecting an external service (Jenkins, CircleCI, Travis CI), you define your automation directly in the repository as YAML files. Those files — called **workflows** — live in the `.github/workflows/` directory and are version-controlled alongside your code.

The core idea: describe *what to do* (a sequence of steps) and *when to do it* (a trigger event). GitHub's infrastructure takes care of the rest.

```txt
Your repository
└── .github/
    └── workflows/
        ├── ci.yml          ← runs on every push / pull request
        ├── deploy.yml      ← runs on merge to main
        └── release.yml     ← runs on git tag push
```

## Workflow YAML structure

Every workflow file has the same top-level structure:

```yaml
name: CI                          # display name in the GitHub Actions UI

on:                               # TRIGGER — when this workflow runs
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:                              # workflow-level environment variables
  NODE_VERSION: '20'

jobs:                             # the work to do — one or more jobs
  test:                           # job ID (used for dependencies between jobs)
    name: Run tests               # display name in the UI
    runs-on: ubuntu-latest        # the runner type to use

    steps:                        # ordered list of actions/commands in this job
      - name: Checkout code
        uses: actions/checkout@v4  # a pre-built action from the marketplace

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'

      - name: Install dependencies
        run: npm ci                # shell command

      - name: Run tests
        run: npm test
```

The four top-level keys to know:

```txt
name    — display name (optional but recommended)
on      — trigger(s): what events cause this workflow to run
env     — environment variables available to all jobs in this workflow
jobs    — the actual work: a map of job IDs to job definitions
```

## Triggers (`on`)

The `on` key defines when the workflow runs. GitHub Actions supports dozens of events; these are the ones you'll use in 90% of cases:

### `push`

```yaml
on:
  push:
    branches: [main, develop]       # only on pushes to these branches
    paths:                          # optional: only if these paths changed
      - 'src/**'
      - 'package.json'
```

Runs whenever commits are pushed to the matching branches. The `paths` filter is useful for monorepos — skip the frontend CI when only backend files changed.

### `pull_request`

```yaml
on:
  pull_request:
    branches: [main]               # only for PRs targeting main
    types: [opened, synchronize]   # default: opened + synchronize (new commits on the PR)
```

Runs on pull request events. The most important types: `opened` (PR created), `synchronize` (new commit pushed to the PR branch), `closed` (PR closed or merged).

### `schedule`

```yaml
on:
  schedule:
    - cron: '0 6 * * 1'           # every Monday at 06:00 UTC
```

Runs on a cron schedule — useful for nightly builds, weekly dependency audits (`npm audit`), or scheduled end-to-end tests against production. The format is standard UNIX cron: `minute hour day-of-month month day-of-week`.

### `workflow_dispatch`

```yaml
on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Target environment'
        required: true
        default: 'staging'
        type: choice
        options: [staging, production]
```

Allows running the workflow manually from the GitHub UI or via the API. The `inputs` block adds a form with fields — useful for deploy workflows where you want a human to pick the target environment.

### `workflow_call`

```yaml
on:
  workflow_call:                   # makes this workflow reusable by other workflows
    inputs:
      node-version:
        type: string
        required: true
    secrets:
      NPM_TOKEN:
        required: true
```

Used to create **reusable workflows** — covered in detail below.

## Jobs: parallelism and dependencies

By default, all jobs in a workflow run in parallel. Use `needs` to declare dependencies:

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps: [...]

  test:
    runs-on: ubuntu-latest
    steps: [...]

  build:
    runs-on: ubuntu-latest
    needs: [lint, test]          # waits for BOTH lint and test to succeed
    steps: [...]

  deploy:
    runs-on: ubuntu-latest
    needs: build                 # waits for build
    if: github.ref == 'refs/heads/main'   # only runs on the main branch
    steps: [...]
```

```txt
Timeline:
  t=0s   lint ──────→ pass (30s)
         test ──────────────────→ pass (90s)
                                          ↓
  t=90s                              build (60s)
                                          ↓
  t=150s                           deploy (only on main)
```

The `if` condition on a job (or step) controls whether it runs. Common patterns:

```yaml
if: github.ref == 'refs/heads/main'          # only on main branch
if: github.event_name == 'pull_request'      # only on PRs
if: failure()                                # only if a previous step failed
if: always()                                 # always run, even if earlier jobs failed
```

## Matrix builds

A **matrix** lets you run the same job multiple times with different parameter combinations — without duplicating the job definition.

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        node-version: [18, 20, 22]
        os: [ubuntu-latest, windows-latest]

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node-version }}
      - run: npm ci && npm test
```

This produces 6 parallel jobs: `{node-18, ubuntu}`, `{node-18, windows}`, `{node-20, ubuntu}`, `{node-20, windows}`, `{node-22, ubuntu}`, `{node-22, windows}`.

Useful options:

```yaml
strategy:
  fail-fast: false    # don't cancel other matrix jobs if one fails (default: true)
  max-parallel: 3     # limit concurrent jobs (useful to avoid rate limits)

  matrix:
    include:          # add specific combinations that aren't in the cross-product
      - node-version: 20
        os: macos-latest
    exclude:          # remove specific combinations from the cross-product
      - node-version: 18
        os: windows-latest
```

## Secrets and environment variables

There are three levels of configuration values, and choosing the wrong one is a security risk:

```txt
Environment variables  → non-sensitive config (NODE_ENV, PORT, API_URL)
Secrets                → sensitive values (passwords, tokens, private keys)
GitHub Environments    → secrets scoped to a specific deploy target (staging, production)
```

**Defining and using secrets:**

```yaml
# In the GitHub UI: Settings → Secrets and variables → Actions → New repository secret
# Then in the workflow:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Vercel
        env:
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}     # injected from GitHub Secrets
          VERCEL_ORG_ID: ${{ secrets.VERCEL_ORG_ID }}
        run: npx vercel --prod --token $VERCEL_TOKEN
```

**GitHub Environments** add a protection layer — you can require manual approval before a job that targets the `production` environment runs:

```yaml
jobs:
  deploy-prod:
    runs-on: ubuntu-latest
    environment: production        # refers to a GitHub Environment defined in Settings
    steps:
      - run: ./deploy.sh
        env:
          DB_URL: ${{ secrets.DB_URL }}   # this secret is scoped to "production" env
```

### Senior nuance #1: secrets are masked but not encrypted in logs

GitHub Actions masks secret values in logs (replaces them with `***`). However:
- If you `echo` a secret split into parts (e.g., `echo ${SECRET:0:3}`) the mask won't catch it
- If a dependency prints the secret to stdout during installation (supply chain attack), GitHub's mask catches it *after* the fact only if the secret appears verbatim
- **Never pass secrets as command arguments** (`run: ./deploy.sh --token $SECRET`) — they appear in process listings on the runner. Pass them as environment variables instead.

## Artifacts and caching

These are two different concepts that are often confused:

```txt
Cache     → speeds up the pipeline by persisting files between RUNS of the same workflow
            (node_modules, pip packages, Maven .m2 — things that don't change often)

Artifact  → stores the OUTPUT of a job so it can be downloaded or used by a LATER JOB
            in the same run (compiled bundle, test report, Docker image layer)
```

**Caching `node_modules`:**

```yaml
- uses: actions/setup-node@v4
  with:
    node-version: '20'
    cache: 'npm'          # built-in cache — caches ~/.npm keyed on package-lock.json hash
```

Or more explicitly:

```yaml
- uses: actions/cache@v4
  with:
    path: ~/.npm
    key: ${{ runner.os }}-npm-${{ hashFiles('**/package-lock.json') }}
    restore-keys: |
      ${{ runner.os }}-npm-
```

The `key` is the cache hit condition: if the `package-lock.json` hash changes (new/updated dependency), the old cache is a miss and `npm ci` runs fully, creating a new cache entry. On cache hit, `npm ci` still runs but is much faster (it validates rather than downloads).

**Passing build output between jobs:**

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci && npm run build
      - uses: actions/upload-artifact@v4
        with:
          name: dist-bundle             # artifact name
          path: dist/                   # which files to upload
          retention-days: 7             # how long to keep it

  deploy:
    runs-on: ubuntu-latest
    needs: build
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist-bundle
          path: dist/
      - run: ./scripts/deploy.sh
```

## Reusable workflows

When multiple repositories (or multiple workflows in the same repo) need to run the same logic, **reusable workflows** eliminate duplication. A reusable workflow is a regular workflow file with `on: workflow_call`.

```yaml
# .github/workflows/shared-test.yml
name: Shared Test Suite

on:
  workflow_call:
    inputs:
      node-version:
        type: string
        default: '20'
    secrets:
      NPM_TOKEN:
        required: false

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ inputs.node-version }}
      - run: npm ci && npm test
```

```yaml
# .github/workflows/ci.yml — calls the shared workflow
name: CI

on:
  push:
    branches: [main]

jobs:
  run-tests:
    uses: ./.github/workflows/shared-test.yml     # path within the same repo
    with:
      node-version: '20'
    secrets:
      NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
```

For cross-repository reuse, the path becomes `owner/repo/.github/workflows/file.yml@ref`.

## Composite actions

A **composite action** is a reusable *piece of a job* — a group of steps packaged into a single `uses:` call. Unlike a reusable workflow (which is a full job), a composite action is embedded into a job alongside other steps.

```yaml
# .github/actions/setup-and-install/action.yml
name: Setup Node and install dependencies
description: Checks out code, sets up Node.js, and runs npm ci with caching

inputs:
  node-version:
    description: Node.js version
    default: '20'

runs:
  using: composite
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: ${{ inputs.node-version }}
        cache: npm
    - run: npm ci
      shell: bash
```

```yaml
# Any workflow can now do:
steps:
  - uses: ./.github/actions/setup-and-install
    with:
      node-version: '20'
  - run: npm test
  - run: npm run build
```

```txt
Composite action vs Reusable workflow — when to use which:

  Composite action    → reuse a GROUP OF STEPS within a job
                        (setup, install, build — then the caller adds more steps)

  Reusable workflow   → reuse an ENTIRE JOB (or set of jobs)
                        (a complete test suite, a complete deploy sequence)
```

## Complete real-world example: test → build → deploy to Vercel

```yaml
# .github/workflows/ci-deploy.yml
name: CI + Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  # ── 1. Lint + Type-check ──────────────────────────────────────
  lint:
    name: Lint & Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: npm
      - run: npm ci
      - run: npm run lint
      - run: npm run type-check

  # ── 2. Tests ──────────────────────────────────────────────────
  test:
    name: Unit & Integration Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: npm
      - run: npm ci
      - run: npm test -- --coverage
      - uses: actions/upload-artifact@v4
        if: always()                      # upload coverage even if tests fail
        with:
          name: coverage-report
          path: coverage/
          retention-days: 7

  # ── 3. Build ──────────────────────────────────────────────────
  build:
    name: Build
    runs-on: ubuntu-latest
    needs: [lint, test]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: npm
      - run: npm ci
      - run: npm run build
      - uses: actions/upload-artifact@v4
        with:
          name: next-build
          path: .next/

  # ── 4. Deploy (main branch only) ──────────────────────────────
  deploy:
    name: Deploy to Vercel
    runs-on: ubuntu-latest
    needs: build
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    environment: production
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          name: next-build
          path: .next/
      - name: Deploy
        run: npx vercel --prod --token ${{ secrets.VERCEL_TOKEN }}
        env:
          VERCEL_ORG_ID: ${{ secrets.VERCEL_ORG_ID }}
          VERCEL_PROJECT_ID: ${{ secrets.VERCEL_PROJECT_ID }}
```

## GitHub-hosted vs self-hosted runners

```txt
                    GitHub-hosted         Self-hosted
─────────────────────────────────────────────────────────────
Setup               Zero                  Install runner software,
                                          register with GitHub
Maintenance         None (GitHub's job)   Your responsibility
                                          (OS updates, security patches)
Network access      Public internet only  Can reach private VPCs, DBs
Hardware            Standard VMs          Any — GPU, specific CPU, ARM
Cost model          Per-minute billing    Your own infrastructure cost
Isolation           Fresh VM each run     Can be persistent (shared state risk)
OS options          ubuntu, windows,      Anything you can run the
                    macos                 runner software on
```

### Senior nuance #2: self-hosted runner security

Self-hosted runners on **public repositories** are a serious security risk: a malicious PR could modify a workflow to run arbitrary code on your runner — accessing private keys, internal databases, or other secrets on the machine.

Mitigations:
- **Require approval for first-time contributors** (GitHub setting: "Require approval for all outside collaborators")
- **Run self-hosted runners in isolated environments** (ephemeral VMs, containers) — not on machines with persistent access to sensitive systems
- **Keep self-hosted runners for private repos only** if they have access to internal resources

## Common interview traps

- **Confusing `env` at workflow level vs job level vs step level** — environment variables cascade: workflow-level `env` is available everywhere; job-level `env` is available to all steps in that job; step-level `env` is available only to that step. A secret set at the wrong level may simply not be visible where you need it.

- **Using `npm install` instead of `npm ci` in pipelines** — `npm install` can modify `package-lock.json` if it finds inconsistencies; `npm ci` always installs the exact versions from the lockfile and fails if the lockfile is out of sync. In CI, always use `npm ci`.

- **Not caching properly** — running `npm ci` without a cache in a pipeline adds 1–3 minutes per job just for dependency installation. The `actions/setup-node@v4` with `cache: npm` makes this a one-liner.

- **Putting secrets in `env` at the workflow level** — workflow-level `env` values are visible in the GitHub UI and logs; secrets accessed via `${{ secrets.NAME }}` are masked. Never store sensitive values in plain `env`.

- **Not understanding `needs` creates a hard dependency, not just ordering** — if a job in `needs` fails, the dependent job does not run at all (unless `if: always()` is set). This means a failed test job *will block* the deploy job — which is exactly what you want, but you need to understand it's not just "run after."

- **Reusable workflow vs composite action mix-up** — a reusable workflow is called with `uses:` in the `jobs:` section and is a complete job; a composite action is called with `uses:` in the `steps:` section and is a group of steps. They are not interchangeable.

- **Forgetting `if: github.event_name == 'push'` on the deploy job** — a workflow triggered by both `push` and `pull_request` will attempt to deploy on PR creation too unless guarded. A PR from a fork also won't have access to secrets — that deploy job will fail or run with empty values.
