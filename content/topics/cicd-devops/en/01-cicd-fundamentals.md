# CI/CD Fundamentals

## The problem CI/CD solves

Before CI/CD existed, teams worked in long-lived feature branches that diverged from the main codebase for days or weeks. When it was finally time to merge, the result was "integration hell": a painful, error-prone process of resolving conflicts and debugging interactions between code that had evolved independently — often under a looming release deadline.

**CI/CD** (Continuous Integration / Continuous Delivery) is a practice — backed by tooling — that makes integration and delivery of software changes frequent, automated, and low-risk. The shorter the gap between writing code and having it tested and deployed, the smaller each individual change is, and the cheaper each bug is to find and fix.

```txt
Without CI/CD:
  Code written for 2 weeks → "big bang" merge → integration hell → manual testing → risky release

With CI/CD:
  Code written for 2 hours → automatic merge + test → staged deploy → small, frequent releases
```

## The three terms: CI, CD (Delivery), CD (Deployment)

These three abbreviations are routinely conflated in job postings, interviews, and casual conversation. They are three distinct concepts that build on each other.

### Continuous Integration (CI)

**CI** — Continuous Integration — means every developer merges (integrates) their code changes into the shared main branch frequently — ideally multiple times per day — and each merge automatically triggers a pipeline that builds and tests the code.

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

**Continuous Delivery** extends CI: every code change that passes the automated pipeline is also packaged into a deployable **artifact** (a Docker image, a compiled bundle, a zip archive — see the Artifact section below) and **made ready to deploy to production** — but the actual production deployment requires a manual approval step.

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
Tests pass → staging deploy → smoke tests pass → PRODUCTION DEPLOY (fully automatic)
```

This requires a very high degree of confidence in the automated test suite and monitoring. Not all teams reach this level, and that is completely fine — Continuous Delivery is the right end-state for many products.

```txt
Summary:
  Continuous Integration  = frequent merges + automated build + automated tests
  Continuous Delivery     = CI + build artifact + automatic staging + manual prod trigger  
  Continuous Deployment   = CI + build artifact + automatic staging + automatic prod deploy
```

## What a pipeline is

A **pipeline** is a sequence of automated steps that run in a defined order when triggered by an event (usually a code push or a pull request being opened). The pipeline is defined as code — typically in a YAML file checked into the repository alongside the application code. This practice is called **pipeline as code**.

Each pipeline consists of **jobs**. A job is a logical unit of work that runs on a single machine. Each job contains individual **steps** (also called **commands** or **tasks** depending on the tool) — shell commands or pre-built actions that do the actual work.

```txt
Pipeline (triggered by: git push to main)
│
├── Job: lint                    ← runs in parallel with "test"
│   ├── Step: checkout code
│   ├── Step: npm ci             (install exact dependency versions from lockfile)
│   └── Step: npm run lint
│
├── Job: test                    ← runs in parallel with "lint"
│   ├── Step: checkout code
│   ├── Step: npm ci
│   └── Step: npm test
│
└── Job: build                   ← only starts AFTER lint + test both pass
    ├── Step: checkout code
    ├── Step: npm ci
    ├── Step: npm run build
    └── Step: docker build + push
```

Jobs within a pipeline often run in **parallel** to save time. But some jobs have dependencies — the `build` job should only run if `lint` and `test` succeeded first; the `deploy` job should only run if `build` succeeded.

## What an artifact is

An **artifact** in CI/CD is any file or set of files produced by a build step and passed to a later step or stored for later use.

Examples:
- A compiled JavaScript/TypeScript bundle (`dist/` folder, `build/` folder)
- A **Docker image** — a packaged snapshot of your application and its runtime environment
- A `.zip` of an AWS Lambda function's code
- A test coverage report (HTML/XML files)
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

An **artifact registry** (also called a **container registry** specifically for Docker images) is a storage service where artifacts are uploaded, versioned, and pulled from during deployments. Examples: GitHub Container Registry (ghcr.io), Docker Hub, AWS ECR (Elastic Container Registry — Amazon's managed container registry), Google Artifact Registry.

## What a runner (agent) is

A **runner** (GitHub Actions terminology) or **agent** (used by Jenkins and some other tools) is the machine — physical or virtual — where the pipeline's jobs actually execute.

When you push code and a pipeline triggers, something has to actually run the shell commands `npm test`, `docker build`, etc. That "something" is the runner.

```txt
CI Provider servers           Your code repository
  ┌──────────────────┐        ┌──────────────────────────┐
  │  Pipeline        │  reads │  .github/workflows/       │
  │  Scheduler       │ ──────→│  ci.yml                   │
  └────────┬─────────┘        └──────────────────────────┘
           │ assigns job to
           ↓
  ┌──────────────────┐
  │     Runner       │  ← a virtual machine that executes
  │  (ubuntu-latest) │    the steps from the YAML file:
  │                  │    npm ci, npm test, docker build...
  └──────────────────┘
```

**GitHub-hosted (managed) runners** — VMs managed entirely by the CI provider. You get a fresh, clean VM for each pipeline run with common tools pre-installed. Convenient, requires zero maintenance on your side, but: you pay per minute of compute, the hardware is shared with other users, and the runners have no access to your private network.

**Self-hosted runners** — VMs or physical machines you own, with the runner software installed. They register with the CI provider and pick up jobs. Useful when:
- Your pipeline needs to reach internal resources (a private database, an on-premises registry, a VPN)
- You need specific hardware (a GPU machine for ML model tests, a macOS machine for iOS builds)
- Pipeline volume is high enough that managed runners become cost-prohibitive

## Typical pipeline stages for a fullstack project

A real-world pipeline for a Node.js + TypeScript project typically looks like this:

```txt
┌────────────────────────────────────────────────────────────────┐
│                         CI Pipeline                             │
│                                                                  │
│  [lint] ──┐                                                      │
│            ├──→ [test] ──→ [type-check] ──→ [build] ──→ [push] │
│  [format]─┘                                    ↓                │
│                                      (on merge to main only)    │
│                                     [deploy to staging]         │
│                                            ↓                    │
│                                   [smoke tests on staging]      │
│                                            ↓                    │
│                              (manual gate OR automatic)         │
│                                   [deploy to production]        │
└────────────────────────────────────────────────────────────────┘
```

**lint** — run ESLint (and/or Stylelint for CSS) to catch syntax errors, unused variables, style violations. Takes 5–30 seconds. Fails fast and cheap.

**type-check** — for TypeScript projects, run `tsc --noEmit` to verify type correctness without emitting output files. This is kept separate from the build step because modern bundlers (esbuild, swc, Vite) often skip type-checking for speed — they transpile but don't type-check. Running `tsc --noEmit` in CI ensures type errors are never silently skipped.

**test** — run the full test suite (unit tests, integration tests). Often the slowest step. Parallelized across multiple runner instances for large projects.

**build** — compile TypeScript to JavaScript, bundle frontend assets, build a Docker image. The output is the deployable artifact.

**push** (publish artifact) — push the built Docker image to the artifact registry tagged with the commit SHA and optionally a version tag.

**deploy** — pull the artifact from the registry and release it to the target environment. This step uses **secrets** — credentials, API keys, database URLs — that are stored in the CI system's secret store, not in the code.

## Why the order matters: fail fast

Pipelines are designed to **fail fast**: the cheapest checks run first. If a developer forgot a semicolon or has a TypeScript error, the pipeline fails in under a minute — without burning 10 minutes on a Docker build or 30 minutes on end-to-end tests.

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

```txt
[GitHub Actions]              — workflow YAML in detail, triggers, matrix builds,
                                secrets, caching, deploying to Vercel/Netlify
[GitLab CI]                   — .gitlab-ci.yml structure, GitLab Runner,
                                how it differs from GitHub Actions
[Docker Essentials]           — images, containers, Dockerfile, multi-stage builds
[Deployment Strategies]       — rolling, blue-green, canary, feature flags, rollback
[Environments and Config]     — dev/staging/prod, secrets management, .env, IaC
[Monitoring and Observability]— logging, metrics, tracing, APM, SLA/SLO/SLI
[CI/CD Glossary]              — every acronym and term explained
```

## Common interview traps

- **Confusing CI/CD with a specific tool** — CI/CD is a *practice*; GitHub Actions, GitLab CI, Jenkins, CircleCI are *tools* that implement that practice. "We use CI" describes a process; "we use GitHub Actions" names the tooling.

- **Conflating Continuous Delivery with Continuous Deployment** — one of the most common slips in interviews. The difference is a single word and a crucial concept: Delivery = human approval gate before production; Deployment = fully automatic. Interviewers specifically ask about this.

- **"We rebuild from source for production"** — a red flag. The artifact should be built once and the exact same artifact deployed to staging and production. Rebuilding for prod means the two environments may have run on slightly different code (e.g., a dependency bumped between builds).

- **Treating the pipeline YAML and the runner as the same thing** — the YAML is the *definition* (what to do); the runner is the *machine that executes it* (where it runs). A pipeline definition can run on GitHub-hosted runners, self-hosted runners, or a mix.

- **Not knowing why lint runs before tests** — it is not convention; it is economics. Lint costs 10× less to run than the test suite. Failing fast on a lint error saves minutes of compute time per PR and provides faster feedback to the developer.

- **"CI/CD means we deploy automatically"** — only Continuous *Deployment* deploys automatically. Many mature teams use Continuous *Delivery* with a manual gate, especially for regulated products or those with scheduled maintenance windows.
