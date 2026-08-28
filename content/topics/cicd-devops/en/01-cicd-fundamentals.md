# CI/CD Fundamentals

## The problem CI/CD solves

Before CI/CD existed, teams worked in long-lived feature branches that drifted away from the main codebase for days or weeks. Merging them back was "integration hell": conflicts everywhere, unpredictable interactions between independently evolved code, and a release deadline overhead.

**CI/CD** (Continuous Integration / Continuous Delivery) is a practice — backed by tooling — that makes integration and delivery of software changes frequent, automated, and low-risk. Short gaps between writing code and getting it tested and deployed keep every change small. Small changes make every bug cheap to find and fix.

```txt
Without CI/CD:
  code written for 2 weeks
    → "big bang" merge → integration hell
    → manual testing → risky release

With CI/CD:
  code written for 2 hours
    → automatic merge + test → staged deploy
    → small, frequent releases
```

## The three terms: CI, CD (Delivery), CD (Deployment)

These three abbreviations are routinely conflated in job postings, interviews, and casual conversation. They are three distinct concepts that build on each other.

### Continuous Integration (CI)

**CI** — Continuous Integration — means every developer merges (integrates) their code into the shared main branch frequently, ideally several times a day. Each merge automatically triggers a pipeline that builds and tests the code.

```txt
Developer pushes code to the repository
              ↓
Automated pipeline starts immediately:
  1. Pull the code at the commit that was pushed
  2. Install dependencies
  3. Run linting (catch style/syntax errors)
  4. Run type-checking (if TypeScript)
  5. Run unit and integration tests
  6. Build (compile, bundle)
              ↓
Pipeline PASSES → the branch is known to be in a working state
Pipeline FAILS  → developer is notified within minutes,
                  while the offending code is fresh in their mind
```

The core principle: **problems are caught within minutes, not days**. A bug found 5 minutes after it was introduced takes seconds to understand and fix. A bug found 2 weeks later — after the author has moved to a different task — can take hours to even reproduce.

### Continuous Delivery (CD — Delivery)

**Continuous Delivery** extends CI. Every change that passes the automated pipeline is packaged into a deployable **artifact**: a Docker image, a compiled bundle or a zip archive. That artifact is then **ready to deploy to production**, but the deployment itself needs a manual approval step. The Artifact section below covers artifacts in detail.

```txt
CI pipeline passes (lint + test + build)
              ↓
Build artifact (e.g. Docker image tagged with the commit SHA)
              ↓
Automatically deploy to staging environment
              ↓
Automated smoke/acceptance tests run against staging
              ↓
        ⏸ HUMAN APPROVAL GATE
          Someone reviews and clicks "Deploy to production"
              ↓
Production deployment
```

The key idea: the code is *always in a deployable state* (that's the "delivery" part), but a human decides *when* to actually deploy. This suits teams that need release coordination, compliance sign-offs, or scheduled maintenance windows.

### Continuous Deployment (CD — Deployment)

**Continuous Deployment** removes the manual approval gate entirely. Every change that passes all automated tests is deployed to production automatically, with no human intervention.

```txt
Tests pass → staging deploy → smoke tests pass
           → production deploy (fully automatic)
```

This requires a very high degree of confidence in the automated test suite and monitoring. Not all teams reach this level, and that is completely fine — Continuous Delivery is the right end-state for many products.

```txt
Summary:
  Continuous Integration
    = frequent merges + automated build + automated tests
  Continuous Delivery
    = CI + artifact + automatic staging + manual prod trigger
  Continuous Deployment
    = CI + artifact + automatic staging + automatic prod deploy
```

## What a pipeline is

A **pipeline** is a sequence of automated steps that run in a defined order. The trigger is an event: usually a code push, or a pull request being opened. The pipeline is defined as code. It usually lives in a file written in YAML (a plain-text format for configuration) and committed to the repository next to the application code. This practice is called **pipeline as code**.

Each pipeline consists of **jobs**. A job is a logical unit of work that runs on a single machine. Each job contains individual **steps** (also called **commands** or **tasks** depending on the tool) — shell commands or pre-built actions that do the actual work.

```txt
Pipeline (triggered by: git push to main)
│
├── Job: lint                 ← parallel with "test"
│   ├── Step: checkout code
│   ├── Step: npm ci          (exact versions from the lockfile)
│   └── Step: npm run lint
│
├── Job: test                 ← parallel with "lint"
│   ├── Step: checkout code
│   ├── Step: npm ci
│   └── Step: npm test
│
└── Job: build                ← starts after lint + test pass
    ├── Step: checkout code
    ├── Step: npm ci
    ├── Step: npm run build
    └── Step: docker build + push
```

Jobs within a pipeline often run in **parallel** to save time. But some jobs have dependencies. The `build` job should only run if `lint` and `test` succeeded first. The `deploy` job should only run after `build`.

## What an artifact is

An **artifact** in CI/CD is any file or set of files produced by a build step. It is either passed to a later step or stored for later use.

Examples:
- A compiled JavaScript/TypeScript bundle (`dist/` folder, `build/` folder)
- A **Docker image** — a packaged snapshot of your application and its runtime environment
- A `.zip` of the code of an AWS (Amazon Web Services) Lambda function
- A test coverage report: an HTML page for people, or a file in XML (a text format that other tools parse)
- A binary executable

The critical property: **build once, deploy everywhere**. The same artifact should be deployed to staging and then to production — you never rebuild from source at each stage. Rebuilding introduces the risk that production gets a slightly different version if a dependency was updated between the two builds.

```txt
Build job → produces Docker image tagged with commit SHA "abc1234"
                              ↓
               Pushed to artifact registry
                              ↓
  Deploy to staging ←── pull image "abc1234" ──→ Deploy to prod
       ↓                                                ↓
  Same bits                                       Same bits
  (guaranteed)                                    (guaranteed)
```

An **artifact registry** is a storage service. Artifacts are uploaded there, versioned, and pulled from it during deployments. For Docker images the same thing is called a **container registry**. Examples: GitHub Container Registry (ghcr.io), Docker Hub, AWS ECR (Elastic Container Registry — Amazon's managed container registry), Google Artifact Registry.

## What a runner (agent) is

A **runner** is the machine, physical or virtual, where the pipeline's jobs actually execute. GitHub Actions calls it a runner. Jenkins and some other tools call it an **agent**.

When you push code, something has to actually run the shell commands `npm test` and `docker build`. That "something" is the runner.

```txt
  CI provider servers       Your code repository
  ┌───────────┐             ┌────────────────────┐
  │ Pipeline  │──── reads ─→│ .github/workflows/ │
  │ scheduler │             │ ci.yml             │
  └───────────┘             └────────────────────┘
        │
        │ assigns the job to
        ↓
  ┌─────────────────┐
  │ Runner          │ ← virtual machine that runs
  │ (ubuntu-latest) │   the steps from the YAML file:
  │                 │   npm ci, npm test, docker build
  └─────────────────┘
```

**GitHub-hosted (managed) runners** — the CI provider owns and manages them. Each pipeline run gets a fresh, clean VM (virtual machine) with common tools pre-installed. Maintenance on your side is zero. The trade-offs:

- You pay per minute of compute.
- The hardware is shared with other users.
- The runners have no access to your private network.

**Self-hosted runners** — machines you own, physical or virtual, with the runner software installed. They register with the CI provider and pick up jobs. Useful when:

- Your pipeline needs to reach internal resources: a database in a private network, an on-premises registry, or a service behind a VPN (virtual private network).
- You need specific hardware: a GPU (graphics processing unit) for machine learning tests, or a macOS machine for iOS builds.
- Pipeline volume is high enough that managed runners become cost-prohibitive.

## Typical pipeline stages for a fullstack project

A real-world pipeline for a Node.js + TypeScript project typically looks like this:

```txt
┌──────────────────────────────────────────────────────────────┐
│                         CI Pipeline                          │
│                                                              │
│   lint ───╮                                                  │
│           ├──→ test ─→ type-check ─→ build ─→ push           │
│   format ─╯                                   │              │
│                         (on merge to main only)              │
│                                      deploy to staging       │
│                                               │              │
│                                      smoke tests on staging  │
│                                               │              │
│                         (manual gate or automatic)           │
│                                      deploy to production    │
└──────────────────────────────────────────────────────────────┘
```

**lint** — run ESLint (and/or Stylelint for CSS) to catch syntax errors, unused variables, style violations. Takes 5–30 seconds. Fails fast and cheap.

**type-check** — for TypeScript projects, run `tsc --noEmit` to verify type correctness without emitting output files. This is kept separate from the build step because modern bundlers (esbuild, swc, Vite) often skip type-checking for speed — they transpile but don't type-check. Running `tsc --noEmit` in CI ensures type errors are never silently skipped.

**test** — run the full test suite (unit tests, integration tests). Often the slowest step. Parallelized across multiple runner instances for large projects.

**build** — compile TypeScript to JavaScript, bundle frontend assets, build a Docker image. The output is the deployable artifact.

**push** (publish artifact) — push the built Docker image to the artifact registry. The tag is the commit SHA (the hash that uniquely identifies that commit), plus optionally a version tag.

**deploy** — pull the artifact from the registry and release it to the target environment. This step uses **secrets** — credentials, API keys, database URLs — that are stored in the CI system's secret store, not in the code.

## Why the order matters: fail fast

Pipelines are designed to **fail fast**: the cheapest checks run first. If a developer forgot a semicolon or has a TypeScript error, the pipeline fails in under a minute. It does not burn 10 minutes on a Docker build or 30 minutes on end-to-end tests.

```txt
Cost ladder (cheapest to most expensive):
  ESLint / format check    →   5–30 seconds
  TypeScript type-check    →  15–60 seconds
  Unit tests               →  30 sec – 3 minutes
  Integration tests        →   2–10 minutes
  Docker build             →   3–15 minutes
  End-to-end (E2E) tests   →  10–60 minutes
  
Run the cheap ones first. The first failure stops the pipeline.
```

## What's next in this section

- [GitHub Actions](./02-github-actions.md) — workflow YAML in detail, triggers,
  matrix builds, secrets, caching, deploying to Vercel and Netlify.
- [GitLab CI](./03-gitlab-ci.md) — `.gitlab-ci.yml` structure, GitLab Runner,
  and how it differs from GitHub Actions.
- [Docker Essentials](./04-docker-essentials.md) — images, containers,
  Dockerfile, multi-stage builds.
- [Deployment Strategies](./05-deployment-strategies.md) — rolling, blue-green,
  canary, feature flags, rollback.
- [Environments and Configuration](./06-environments-and-config.md) — dev,
  staging and prod, secrets management, `.env` files, infrastructure as code.
- [Monitoring and Observability](./07-monitoring-and-observability.md) —
  logging, metrics, tracing, application monitoring, service level targets.
- [CI/CD and DevOps Glossary](./08-glossary-and-acronyms.md) — every DevOps
  (development and operations) term and acronym of this section.

## Common interview traps

- **Confusing CI/CD with a specific tool** — CI/CD is a *practice*; GitHub Actions, GitLab CI, Jenkins, CircleCI are *tools* that implement that practice. "We use CI" describes a process; "we use GitHub Actions" names the tooling.

- **Conflating Continuous Delivery with Continuous Deployment** — one of the most common slips in interviews. The difference is a single word and a crucial concept: Delivery = human approval gate before production; Deployment = fully automatic. Interviewers specifically ask about this.

- **"We rebuild from source for production"** — a red flag. The artifact should be built once and the exact same artifact deployed to staging and production. Rebuilding for prod means the two environments may have run on slightly different code (e.g., a dependency bumped between builds).

- **Treating the pipeline YAML and the runner as the same thing** — the YAML is the *definition*, that is, what to do. The runner is the *machine that executes it*, that is, where it runs. A pipeline definition can run on GitHub-hosted runners, self-hosted runners, or a mix.

- **Not knowing why lint runs before tests** — it is not convention; it is economics. Lint costs 10× less to run than the test suite. Failing fast on a lint error saves minutes of compute time per pull request and gives the developer faster feedback.

- **"CI/CD means we deploy automatically"** — only Continuous *Deployment* deploys automatically. Many mature teams use Continuous *Delivery* with a manual gate, especially for regulated products or those with scheduled maintenance windows.
