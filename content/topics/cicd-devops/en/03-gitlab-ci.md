# GitLab CI

## What GitLab CI is

**GitLab CI** (GitLab Continuous Integration) is GitLab's built-in CI/CD platform. Like GitHub Actions, it requires no external service — you commit a file called `.gitlab-ci.yml` to the root of your repository, and GitLab automatically picks it up and runs pipelines based on it.

GitLab CI predates GitHub Actions by several years and is the dominant CI/CD solution in many enterprises that self-host their Git infrastructure. If you work with a company that runs its own GitLab instance (on-premises), you will almost certainly work with GitLab CI.

## `.gitlab-ci.yml` structure

The configuration file lives at the **root of the repository** (not in `.gitlab/` — it is always `.gitlab-ci.yml` at the top level).

```yaml
# .gitlab-ci.yml

stages:           # defines the order of stages; jobs in the same stage run in parallel
  - lint
  - test
  - build
  - deploy

variables:        # pipeline-level variables (non-secret config)
  NODE_VERSION: "20"
  NODE_ENV: "test"

# ── Job definition ────────────────────────────────────────────────
run-lint:                       # job name (arbitrary, must be unique in the file)
  stage: lint                   # which stage this job belongs to
  image: node:20-alpine         # Docker image to run this job inside
  before_script:                # commands that run before script, in every job
    - npm ci
  script:                       # the actual commands — required key
    - npm run lint
  cache:                        # cache configuration
    key: "$CI_COMMIT_REF_SLUG"  # cache key — here: branch name
    paths:
      - node_modules/

run-tests:
  stage: test
  image: node:20-alpine
  before_script:
    - npm ci
  script:
    - npm test -- --coverage
  artifacts:                    # files to keep after the job finishes
    when: always                # keep even if the job failed
    paths:
      - coverage/
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage/cobertura-coverage.xml
    expire_in: 7 days

build-app:
  stage: build
  image: node:20-alpine
  before_script:
    - npm ci
  script:
    - npm run build
  artifacts:
    paths:
      - dist/
    expire_in: 1 hour           # short-lived: just needs to reach the deploy job

deploy-staging:
  stage: deploy
  image: alpine:latest
  script:
    - ./scripts/deploy.sh staging
  environment:                  # tells GitLab this job deploys to an environment
    name: staging
    url: https://staging.example.com
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

### The `stages` key

`stages` defines both the **names** of stages and their **execution order**. Jobs belonging to the same stage run in parallel; the next stage only starts when all jobs in the current stage have passed.

```txt
stages: [lint, test, build, deploy]

  Stage lint  → run-lint (one job, runs alone)
       ↓ (passes)
  Stage test  → run-tests (one job, but could be many in parallel)
       ↓ (passes)
  Stage build → build-app
       ↓ (passes)
  Stage deploy → deploy-staging
```

If you omit `stages`, GitLab falls back to the default: `[.pre, build, test, deploy, .post]`. Two special stages — `.pre` always runs before everything, `.post` always runs after everything — regardless of what you list in `stages`.

### The `script` key

`script` is the **only required key** in a job. It is a list of shell commands that run sequentially inside the job's container. If any command returns a non-zero exit code, the job fails.

```yaml
script:
  - echo "Starting build"
  - npm run build
  - echo "Build complete"
```

`before_script` runs before `script` and is often used for setup (installing dependencies). `after_script` runs after `script` regardless of success or failure — useful for cleanup.

```txt
Execution order for a job:
  before_script  (setup: npm ci, apt-get install, ...)
  script         (the actual work)
  after_script   (cleanup — runs even on failure)
```

### The `image` key

Each job runs inside a **Docker container**. The `image` key specifies which Docker image to use:

```yaml
image: node:20-alpine    # Node.js 20 on Alpine Linux (small image)
```

You can set a default image for all jobs at the top level and override it per job:

```yaml
default:
  image: node:20-alpine  # used by all jobs that don't specify their own image

build-go-service:
  image: golang:1.22     # overrides the default for this specific job
  script:
    - go build ./...
```

This is a key difference from GitHub Actions: in GitLab CI, every job runs in a Docker container by default (with the Docker executor). In GitHub Actions, the runner has tools pre-installed on the host VM and you use `uses: actions/setup-node@v4` to configure them.

## GitLab Runner

A **GitLab Runner** is a separate open-source application (written in Go) that registers with a GitLab instance and executes the jobs from your pipelines. The relationship:

```txt
GitLab server                     GitLab Runner (separate process/machine)
  ┌───────────────────┐             ┌───────────────────────────────────┐
  │  Reads            │             │                                    │
  │  .gitlab-ci.yml   │ ─── job ──→ │  Picks up the job                 │
  │  when a push      │             │  Runs it in a Docker container     │
  │  happens          │ ←─ result ─ │  (or shell, VM, K8s pod...)        │
  └───────────────────┘             └───────────────────────────────────┘
```

### Runner executors

The **executor** determines how the runner actually runs each job:

```txt
docker    → each job runs in a fresh Docker container (most common)
            requires Docker on the runner machine

shell     → each job runs directly in the shell of the runner machine
            no isolation — jobs share the machine's environment

kubernetes → each job runs as a pod in a Kubernetes cluster
              (K8s = Kubernetes — a container orchestration platform)
              good for large-scale, cloud-native pipelines

docker+machine → auto-provisions new cloud VMs for each job
                  (GitLab's equivalent of GitHub-hosted runners)
```

### Types of runners

```txt
Shared runners     → provided by GitLab.com for all projects; limited
                     free minutes per month on free plans

Group runners      → registered to a GitLab group; available to all
                     projects in that group

Project runners    → registered to a specific project; available only to it

Self-hosted (any)  → a runner you install and manage yourself, anywhere
```

For GitLab.com (the SaaS version), shared runners come pre-configured. For a self-hosted GitLab instance (common in enterprises), you must install and register your own runners.

**Registering a self-hosted runner:**

```bash
# Install the runner binary (Linux example)
curl -L https://packages.gitlab.com/install/repositories/runner/gitlab-runner/script.deb.sh | sudo bash
sudo apt-get install gitlab-runner

# Register it with your GitLab instance
sudo gitlab-runner register \
  --url https://gitlab.example.com \
  --token <your-registration-token> \
  --executor docker \
  --docker-image node:20-alpine \
  --description "my-docker-runner"
```

## Pipeline variables

Variables in GitLab CI come from multiple sources, with a defined priority:

```txt
Priority (highest → lowest):
  1. Trigger variables (passed when triggering via API)
  2. Scheduled pipeline variables
  3. Manual pipeline variables (set when clicking "Run pipeline" in the UI)
  4. Project-level CI/CD variables (Settings → CI/CD → Variables)
  5. Group-level CI/CD variables
  6. Instance-level variables (admin only, for self-hosted instances)
  7. .gitlab-ci.yml variables (the `variables:` key in the file)
```

**Defining variables in `.gitlab-ci.yml`:**

```yaml
variables:
  NODE_ENV: "production"          # available to all jobs
  DOCKER_REGISTRY: "registry.example.com"

deploy:
  variables:
    DEPLOY_TARGET: "us-east-1"   # available only in this job
  script:
    - echo "Deploying to $DEPLOY_TARGET"
```

**Predefined CI/CD variables** — GitLab automatically injects many useful variables into every pipeline:

```txt
$CI_COMMIT_SHA        — full SHA of the commit that triggered the pipeline
$CI_COMMIT_SHORT_SHA  — first 8 characters of the commit SHA
$CI_COMMIT_BRANCH     — branch name (empty for tag pipelines)
$CI_COMMIT_TAG        — tag name (empty for branch pipelines)
$CI_COMMIT_REF_SLUG   — branch/tag name with special chars replaced by -
                         (safe to use as a Docker image tag or cache key)
$CI_PIPELINE_ID       — unique numeric ID of the pipeline
$CI_JOB_ID            — unique numeric ID of the job
$CI_PROJECT_PATH      — namespace/project-name (e.g. "myorg/myapp")
$CI_REGISTRY          — address of the GitLab Container Registry
$CI_REGISTRY_IMAGE    — full image path for this project in the registry
$CI_REGISTRY_USER     — username to log into the registry
$CI_REGISTRY_PASSWORD — password to log into the registry (job token)
```

Real example — tagging and pushing a Docker image with the commit SHA:

```yaml
build-docker:
  stage: build
  image: docker:24
  services:
    - docker:24-dind               # dind = Docker-in-Docker: a Docker daemon
                                   # running inside the job's container, needed
                                   # to run docker commands inside a container
  script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA
```

## `rules` vs `only`/`except`

These control **when a job runs**. `only`/`except` is the older syntax; `rules` is the modern replacement and should be used for new pipelines.

### `only` / `except` (legacy — avoid in new pipelines)

```yaml
deploy:
  script: ./deploy.sh
  only:
    - main                  # only run when the branch is "main"
    - tags                  # or when a git tag is pushed
  except:
    - schedules             # but not for scheduled pipelines
```

Limitations: `only`/`except` evaluates as a flat list of conditions (branch names, pipeline sources) and does not support complex logic or variable expressions well.

### `rules` (modern — prefer this)

`rules` evaluates conditions sequentially and stops at the first match:

```yaml
deploy-production:
  script: ./deploy.sh production
  rules:
    - if: $CI_COMMIT_TAG                          # if a git tag was pushed → run
      when: on_success
    - if: $CI_COMMIT_BRANCH == "main"             # else if on main branch → run manually
      when: manual
    - when: never                                  # otherwise → never run
```

Available `when` values:

```txt
on_success   → run if all previous jobs in earlier stages passed (default)
on_failure   → run only if a previous job failed (useful for cleanup/notification jobs)
always       → always run, regardless of previous job outcomes
manual       → add the job to the pipeline but require a human to click "Run" in the UI
never        → do not add this job to the pipeline at all
delayed      → run after a delay (start_in: '10 minutes')
```

`rules` also supports `changes` (run only if specific files changed) and `exists` (run only if a file exists):

```yaml
run-frontend-tests:
  script: npm test
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      changes:
        - frontend/**/*
        - package.json
```

## Caching and artifacts

The concepts are the same as in GitHub Actions but the syntax differs:

**Cache** — persist files between pipeline runs:

```yaml
run-tests:
  cache:
    key:
      files:
        - package-lock.json      # cache is invalidated when this file changes
    paths:
      - node_modules/
    policy: pull-push            # pull from cache at start, push updated cache at end
                                 # also: pull (read-only), push (write-only)
```

**Artifacts** — pass files between jobs in the same pipeline:

```yaml
build-app:
  artifacts:
    paths:
      - dist/
    expire_in: 1 hour

deploy:
  needs:
    - job: build-app
      artifacts: true            # explicitly download the artifacts from build-app
  script:
    - ls dist/                   # files are available here
```

By default, a job automatically downloads the artifacts from all jobs in **earlier stages**. Using `needs:` with `artifacts: true` makes the dependency explicit and also allows downloading from a specific job without waiting for its entire stage.

## `needs` — DAG pipelines

GitLab CI supports a **DAG** (Directed Acyclic Graph — a graph structure where dependencies flow in one direction with no cycles) for pipeline execution. With `needs:`, you can make a job start as soon as its specific dependencies are done — without waiting for the entire preceding stage to finish.

```txt
Without needs (stage-based — all of "test" must finish before any "build" starts):
  lint ─────────────────────────────────┐
  unit-tests ────────────────────────── stage "test" ─→ build (starts here)
  integration-tests (slowest, 10 min) ─┘

With needs (DAG — build starts as soon as lint passes):
  lint ──────────────────────────────────────────→ build (starts immediately after lint)
  unit-tests ─────────────────────────────────────→
  integration-tests (10 min, doesn't block build) →
```

```yaml
build-fast:
  stage: build
  needs:
    - lint          # start as soon as lint passes, don't wait for tests
  script:
    - npm run build
```

## GitLab CI vs GitHub Actions — switching between them

This is the most practically useful comparison for a fullstack developer who works with both platforms:

```txt
Topic                    GitHub Actions                GitLab CI
─────────────────────────────────────────────────────────────────────────────
Config file location     .github/workflows/*.yml       .gitlab-ci.yml (root)
                         (multiple files allowed)      (single file by default)

Config file name         Any name, any number          Always .gitlab-ci.yml

Stages concept           No explicit stages;           Explicit stages: key
                         use `needs:` for ordering     defines both names + order

Parallel jobs            Default (no needs = parallel) Default within a stage

Job runner image         Set per step via              Set per job via `image:`
                         `actions/setup-*`             (Docker-first approach)
                         (host VM with tools)

Trigger keyword          `on:`                         `rules:` / `only:`

PR/MR keyword            pull_request                  merge_request_event

Secrets access           ${{ secrets.NAME }}           $VARIABLE_NAME
                                                       (same as env vars)

Manual trigger           `workflow_dispatch`           `when: manual` on a job

Caching syntax           actions/cache@v4              `cache:` key in job

Passing files between    upload-artifact /             `artifacts:` in job
jobs                     download-artifact actions

Reusable pipelines       Reusable workflows +          `include:` to pull in
                         composite actions             other YAML files;
                                                       `extends:` to inherit
                                                       from job templates

Built-in container       GitHub Container Registry     GitLab Container Registry
registry                 (ghcr.io)                     ($CI_REGISTRY)

Self-hosted runners      GitHub Actions runner         GitLab Runner (separate
                         (same binary, different       binary, multiple executors)
                         config)
```

### Key differences to internalize

**1. Stages vs graph ordering**

GitHub Actions has no `stages` concept. You achieve ordering purely through `needs:`. In GitLab CI, `stages:` defines the execution order at the stage level; within a stage, jobs are parallel.

```yaml
# GitHub Actions — ordering via needs
jobs:
  lint:
    ...
  test:
    needs: [lint]
  build:
    needs: [test]

# GitLab CI — ordering via stages
stages: [lint, test, build]
lint-job:
  stage: lint
test-job:
  stage: test      # automatically runs after lint stage
build-job:
  stage: build     # automatically runs after test stage
```

**2. The `include:` keyword for splitting large pipelines**

GitLab CI supports splitting your pipeline across multiple files via `include:`:

```yaml
# .gitlab-ci.yml
include:
  - local: '.gitlab/ci/test.yml'
  - local: '.gitlab/ci/build.yml'
  - project: 'my-org/shared-pipelines'   # include from another GitLab project
    ref: main
    file: '/templates/deploy.yml'
```

GitHub Actions achieves this differently — through reusable workflows called from the `jobs:` section.

**3. `extends:` for job templates**

GitLab CI has a native template/inheritance system:

```yaml
.node-defaults:          # jobs starting with . are hidden (templates, not run directly)
  image: node:20-alpine
  before_script:
    - npm ci
  cache:
    key: "$CI_COMMIT_REF_SLUG"
    paths: [node_modules/]

lint:
  extends: .node-defaults    # inherits image, before_script, cache
  stage: lint
  script:
    - npm run lint

test:
  extends: .node-defaults    # same inheritance
  stage: test
  script:
    - npm test
```

GitHub Actions achieves this through composite actions and reusable workflows — there is no direct equivalent of `extends:`.

**4. Merge Request pipelines**

GitLab has a first-class concept of **Merge Request (MR) pipelines** — pipelines that run in the context of an MR, with access to MR-specific variables (`$CI_MERGE_REQUEST_ID`, `$CI_MERGE_REQUEST_SOURCE_BRANCH_NAME`, etc.):

```yaml
test:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"   # runs only on MRs
```

GitHub Actions uses `pull_request` as the event trigger, which is conceptually identical but uses different variable names (`github.event.pull_request.number`, etc.).

## Common interview traps

- **"GitLab CI uses YAML the same way as GitHub Actions"** — the structure is similar but the semantics differ. The biggest conceptual difference: GitLab CI has `stages:` as a first-class ordering mechanism; GitHub Actions uses only `needs:`.

- **Forgetting that jobs in the same stage run in parallel** — a common source of bugs. If two jobs in the same stage both write to the same artifact path or the same cache key, they will race. Separate conflicting jobs into different stages or use `needs:` to sequence them explicitly.

- **Using `only`/`except` in new pipelines** — this syntax is deprecated in favor of `rules:`. In an interview, showing awareness of this evolution signals that you've worked with GitLab CI recently, not just years ago.

- **Confusing `artifacts` and `cache`** — artifacts pass files between jobs within a single pipeline run; cache persists files across multiple runs. Artifacts are stored by GitLab and can be downloaded from the UI; cache is stored on the runner.

- **Not knowing what `dind` means** — "Docker-in-Docker" (the `docker:dind` service) is needed to run `docker build` inside a GitLab CI job that itself runs in a Docker container. Without it, the `docker` CLI has no daemon to talk to. Interviewers who work with GitLab CI ask about this because it's a real operational pain point.

- **Assuming `${{ secrets.NAME }}` syntax works in GitLab CI** — in GitLab CI, all variables (including secrets added in Settings → CI/CD → Variables) are accessed as plain shell variables `$VARIABLE_NAME`, not with the `${{ }}` expression syntax. The `${{ }}` syntax is specific to GitHub Actions.

- **Not knowing about `.pre` and `.post`** — these are special GitLab CI stage names that always run before and after all other stages, respectively, regardless of the `stages:` list. Useful for global setup and cleanup, and a common interview question for testing deep GitLab CI knowledge.
