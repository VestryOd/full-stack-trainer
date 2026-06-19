# CI/CD & DevOps — Interview Questions

## Group 1: CI/CD Fundamentals

**What is the difference between Continuous Delivery and Continuous Deployment?**

Both start the same way: every code change that passes the automated pipeline is packaged into a deployable artifact and automatically released to staging. The difference is the final step. Continuous Delivery stops there and requires a human to approve the production deploy — the button exists, but a person clicks it. Continuous Deployment removes that button entirely: every passing build goes straight to production automatically. The difference is one manual approval gate. Both require the pipeline to be reliable enough that a failing build actually means "do not ship."

---

**What is a CI pipeline and what steps does it typically include?**

A CI pipeline is a sequence of automated steps triggered by a code change (push or pull request). Typical steps in order: (1) checkout the source code; (2) install dependencies; (3) lint/type-check; (4) run unit and integration tests; (5) build the application; (6) publish an artifact (Docker image to a registry, bundle to S3, etc.); (7) optionally deploy to staging. The steps are ordered from cheapest to most expensive so that a fast, cheap failure (lint error) catches the problem before a slow, expensive step (full test suite or Docker build) runs.

---

**What is an artifact and why should you build it once and promote it through environments?**

An artifact is any file produced by a build step: a compiled JS bundle, a Docker image, a Lambda ZIP, a compiled binary. "Build once, promote everywhere" means the same artifact is deployed to staging and then to production — never rebuilt from source per environment. The reason: rebuilding introduces variance (npm package resolves differently, environment variables are baked in differently, a transient download fails). What you tested on staging must be byte-for-byte identical to what goes to production. The artifact is pushed to an artifact registry (Docker Hub, ECR, S3) tagged with the commit SHA so any version is precisely reproducible.

---

**What does "pipeline as code" mean and what are its advantages?**

Pipeline as code means the CI/CD pipeline is defined in a configuration file (YAML) committed to the same repository as the application code. Advantages: (1) pipeline changes go through the same pull request review process as code changes — no "accidental" pipeline modifications; (2) the history of pipeline changes is visible in `git log`; (3) the pipeline is reproducible — any branch can have its own pipeline configuration and it will behave the same for every developer; (4) rollback is a git revert. Contrast: Jenkins of the 2010s where pipelines were configured by clicking through a web UI — invisible, hard to audit, impossible to version.

---

**What is a runner (agent) and what are the trade-offs between hosted and self-hosted runners?**

A runner is the machine where pipeline jobs actually execute. When a job is triggered, the CI scheduler assigns it to an available runner, which clones the repo, runs the steps, and reports the result. **Hosted runners** (GitHub-hosted, GitLab.com shared): pre-provisioned by the platform, fresh VM per job, zero maintenance, billed per minute, no access to private networks. **Self-hosted runners**: machines you own, registered with the CI platform, can access private databases and VPCs, hardware is fully controllable, cost is fixed (your own servers), but you maintain OS updates, security patches, and disk cleanup. Security concern: never use self-hosted runners on public repositories — a malicious PR can modify the workflow to run arbitrary code on your machine.

---

## Group 2: GitHub Actions & GitLab CI

**What is the difference between `on: push` and `on: pull_request` triggers in GitHub Actions?**

`on: push` fires when a commit is pushed directly to the repository — including to main, feature branches, or any branch matching a pattern. `on: pull_request` fires when a PR is opened, updated (new commit pushed to the source branch), or synchronized. For most projects: `on: pull_request` runs tests and linting (validating the proposed change), and `on: push` to `main` (after the PR is merged) runs the deployment pipeline. An important difference: `on: pull_request` from a fork runs with limited secrets access for security — the workflow has read-only permissions and no access to repository secrets.

---

**How do matrix builds work and when are they useful?**

A matrix build is a single job definition that GitHub Actions expands into multiple parallel jobs by combining values from a matrix. Example: `matrix: { node: [18, 20, 22] }` spawns three parallel jobs, each running with a different Node.js version. Matrices can be multi-dimensional: `matrix: { os: [ubuntu-latest, windows-latest], node: [18, 20] }` → 4 jobs. Use cases: testing across multiple Node.js/Python/Java versions, testing on multiple operating systems, testing against multiple database versions. Each matrix combination is a fully isolated job with its own runner.

---

**What is the difference between a reusable workflow and a composite action in GitHub Actions?**

A **reusable workflow** (defined with `on: workflow_call`) is a complete workflow that runs as its own job on its own runner. It is called via `uses: ./.github/workflows/deploy.yml`. It can include multiple steps, its own `env:` and `with:` inputs, and runs in complete isolation. A **composite action** (defined in an `action.yml` with `runs.using: composite`) is a reusable sequence of steps that runs *inside an existing job*, sharing the same runner environment. Use a composite action when you want to abstract repeated setup steps within a job (install, auth, configure). Use a reusable workflow when you want to share an entire job or deployment flow across repositories.

---

**What is the difference between `only/except` and `rules` in GitLab CI, and which should you use?**

`only/except` is the legacy keyword: `only: [main, merge_requests]` — the job runs only on specified branches or events. It is limited: cannot combine conditions, cannot access CI variables in conditions, cannot set `when: manual` conditionally. `rules` is the modern replacement: an ordered list of `if/when/changes` conditions evaluated top to bottom; the first matching rule wins. `rules` supports: `if: $CI_COMMIT_BRANCH == "main"`, `changes: [src/**/*]` (run only if source files changed), `when: manual`, and `allow_failure: true` per rule. Always use `rules` — `only/except` is deprecated and will be removed.

---

**What does the `needs:` keyword do in GitLab CI, and what structure does it create?**

`needs:` defines explicit job dependencies, turning the pipeline from a stage-based sequence into a DAG (Directed Acyclic Graph — a graph with directed edges and no cycles). Without `needs:`, jobs in a stage all wait for the entire previous stage to complete. With `needs:`, a job starts as soon as its specific dependencies finish — regardless of what stage it is in. Example: `deploy-preview` can depend only on `build` without waiting for `test-e2e` in the same stage. This significantly reduces total pipeline time. In GitHub Actions, the same is done with `needs:` at the job level.

---

**How do you securely handle secrets in GitHub Actions?**

Secrets are stored in repository or organization Settings → Secrets and are never visible in logs after the initial configuration. In workflows, access them via `${{ secrets.MY_SECRET }}`. Rules: (1) never hardcode secrets in workflow YAML; (2) never `echo` a secret value — GitHub automatically masks known secret values in logs but this is not foolproof; (3) use environment-level secrets (`environment: production`) for production credentials — these require approval before the job runs; (4) for third-party API keys, use OIDC (OpenID Connect) federated tokens instead of long-lived static keys when the provider supports it (AWS, GCP, Azure all do); (5) audit which workflows have access to which secrets.

---

**What is Docker-in-Docker (dind) and when is it required in GitLab CI?**

dind (Docker-in-Docker) is a configuration where a Docker daemon runs *inside* a Docker container — so that `docker build` and `docker push` can be executed inside a CI job that itself runs in a container. Required in GitLab CI when using the Docker executor (where jobs run as containers) and the job needs to build Docker images. Declared as a service: `services: - docker:24-dind`, with `DOCKER_HOST: tcp://docker:2376`. Security implication: dind requires the container to run in **privileged mode**, which means the container has full access to the host kernel — a significant security risk in shared environments. Alternative: Kaniko (builds Docker images without a daemon, no privileged mode required).

---

## Group 3: Docker

**What is the difference between a Docker image and a container?**

An image is a read-only, layered snapshot of a filesystem — everything needed to run the application: OS base, runtime, dependencies, compiled code. An image is built from a Dockerfile and stored in a registry. A container is a running instance of an image: the image's filesystem plus a writable top layer, running as an isolated process on the host OS. Multiple containers can run from the same image simultaneously. The analogy: an image is a class definition; a container is an instance of that class. Images are built once and promoted; containers are ephemeral and replaceable.

---

**What are Docker image layers and why do they matter for build performance?**

Each Dockerfile instruction (`FROM`, `RUN`, `COPY`, `ADD`) creates a new read-only layer — a diff relative to the layer below. Layers are cached: if an instruction and its inputs have not changed since the last build, Docker reuses the cached layer and skips re-executing it. This makes layer ordering critical for performance: place instructions that change rarely (installing OS packages, copying `package.json`, running `npm install`) before instructions that change often (copying application source code). A single change to any layer invalidates the cache for all layers below it. Practical rule: `COPY package*.json ./` → `RUN npm ci` → `COPY . .` keeps the `npm ci` layer cached across source code changes.

---

**What is the difference between CMD and ENTRYPOINT, and between exec form and shell form?**

`ENTRYPOINT` defines the fixed executable that always runs. `CMD` provides default arguments that can be overridden at `docker run` time. When both are present, the container runs `ENTRYPOINT CMD-arguments`. Shell form (`CMD node server.js`) invokes `sh -c "node server.js"` — `sh` becomes PID 1, Node.js is a child process, and `sh` does not forward `SIGTERM` to children → graceful shutdown is broken. Exec form (`CMD ["node", "server.js"]`) runs Node.js directly as PID 1 — it receives `SIGTERM` and can shut down gracefully. Always use exec form for the main process. Shell form is acceptable for `RUN` build steps.

---

**What is PID 1 in a container and why does it matter?**

In Linux, PID 1 is the init process — the first process started by the kernel. It is responsible for reaping zombie child processes and forwarding signals. In a Docker container, PID 1 is the process defined by `CMD`/`ENTRYPOINT`. If `sh` is PID 1 (shell form of CMD), it does not forward `SIGTERM` to its child processes — when Kubernetes stops the pod, `SIGTERM` is sent, `sh` ignores it, Kubernetes waits 30 seconds (grace period), and then sends `SIGKILL`, killing the container forcefully and dropping any in-flight requests. With exec form, your application is PID 1, receives `SIGTERM` directly, and can shut down gracefully. For Node.js: `CMD ["node", "server.js"]`, not `CMD node server.js`.

---

**What is a multi-stage build and what problem does it solve?**

A multi-stage build uses multiple `FROM` instructions in one Dockerfile, each starting a new build stage. Files can be copied between stages with `COPY --from=builder`. The final image contains only what is explicitly copied into the last stage — build tools, dev dependencies, TypeScript compiler, and test files are left behind in earlier stages. Result: a production image that contains only the Node.js runtime and compiled JS, not the TypeScript compiler, `@types/*` packages, or test frameworks. Typical size reduction: from ~400 MB (all build tools included) to ~80 MB (runtime only). Smaller images mean faster pulls, smaller attack surface, and lower storage costs.

---

**Why should containers run as a non-root user?**

By default, the process inside a Docker container runs as root (UID 0). If an attacker exploits a vulnerability in the application and escapes the container (via a kernel bug or misconfig), they have full root access to the host machine. Running as a non-root user limits the blast radius: an escaped process has the same limited privileges as a regular OS user. In a Dockerfile: `USER node` (the `node:*` base images include a pre-created `node` user with UID 1000). Make sure files your application needs to write to are owned by that user. Some container runtimes (like Kubernetes with Pod Security Admission) can enforce non-root as a policy.

---

## Group 4: Deployment Strategies

**What is zero-downtime deployment and how is it achieved?**

Zero-downtime deployment means the service remains continuously available during a code update — no requests are dropped, no users see errors. It requires two things working together: (1) an infrastructure strategy that keeps old instances running while new ones start (rolling update, blue-green, or canary); (2) graceful shutdown in the application — when the instance receives `SIGTERM`, it stops accepting new connections but finishes processing in-flight requests before exiting. Without graceful shutdown, even a perfectly orchestrated rolling update drops requests on every pod replacement. Database migrations must also be backward-compatible with both the old and new version of the application running simultaneously.

---

**What is the difference between rolling, blue-green, and canary deployments?**

**Rolling update**: instances are replaced one at a time (or in small batches). During the rollout, both old and new versions serve traffic simultaneously — requires backward-compatible API and database schema. Minimal infrastructure cost. Built into Kubernetes and ECS. **Blue-green**: two identical environments are maintained; the new version is fully deployed and tested in the idle environment, then traffic is switched instantaneously via the load balancer. No mixed-version period, instant rollback (switch back), but doubles infrastructure cost. **Canary**: a small percentage of traffic (e.g., 5%) is sent to the new version; the rest stays on the old. The new version is observed; traffic is gradually increased. Minimum blast radius, but requires traffic-splitting infrastructure (service mesh or smart load balancer).

---

**What is the expand-contract migration pattern and when is it needed?**

The expand-contract pattern solves the problem of making breaking database schema changes without downtime when both old and new versions of the application must run against the same database during a rolling deploy. It splits one dangerous migration into three separate deploys: (1) **Expand** — add the new column as nullable (no lock, backward compatible, old code ignores it); (2) **Backfill** — deploy new code that writes to both old and new columns; run a background job to populate the new column for existing rows; (3) **Contract** — once all rows are populated and old code is gone, make the column NOT NULL and drop the old column. Never add a NOT NULL column with a DEFAULT in a single migration on a large table — PostgreSQL must rewrite the entire table, causing a full table lock.

---

**What is a feature flag and how is it different from a canary release?**

A feature flag (feature toggle) is an `if` statement in application code that checks a configuration value at runtime: `if (flags.isEnabled('new-checkout', user))`. The code is already deployed to production but inactive until the flag is turned on. A canary release is an infrastructure-level strategy: two versions of the service are deployed simultaneously, and a load balancer or service mesh routes a percentage of traffic to the new version. Feature flags are application-level and can be toggled per user, per organization, or per percentage without any deployment. Canary releases involve actually running two deployed versions. They complement each other: use a canary release to validate the new binary, then use feature flags for controlled feature exposure.

---

**What is graceful shutdown and how do you implement it in Node.js?**

Graceful shutdown means the process catches `SIGTERM`, stops accepting new connections, waits for in-flight requests to complete, releases resources (database connections, message queue consumers), and exits with code 0. In Node.js with Express:
```javascript
process.on('SIGTERM', async () => {
  server.close(async () => {        // stop accepting new HTTP connections
    await prisma.$disconnect();     // close DB connection pool
    process.exit(0);
  });
});
```
Kubernetes sends `SIGTERM` and waits `terminationGracePeriodSeconds` (default: 30 s) before sending `SIGKILL`. The application must complete its shutdown within that window. For NestJS: `app.enableShutdownHooks()` handles this via lifecycle hooks (`OnApplicationShutdown`).

---

## Group 5: Environments, Config & Secrets

**What is the difference between an environment variable, a configuration file, and a secret?**

**Environment variables**: non-sensitive runtime parameters (feature flags, log level, API URLs, environment name). Simple key-value pairs, easy to override per environment, visible in `process.env`. **Configuration files**: structured non-sensitive settings (database schema name, pagination defaults, supported locales) — committed to the repository and loaded at startup. **Secrets**: sensitive credentials that must never appear in source code, logs, or plain-text storage (database passwords, API keys, JWT signing keys, TLS private keys). Secrets are stored in a secrets manager (AWS Secrets Manager, HashiCorp Vault) and injected into the process at runtime via environment variables. The boundary: if it being leaked would cause a security incident, it is a secret.

---

**Why should `.env` files never be committed to version control?**

Once a secret is committed, it is effectively permanent — even if deleted in a subsequent commit, it remains in git history and can be recovered with `git log -p`. Anyone with repository access (current or future team members, automated tools, GitHub's own indexing) can read it. Supply chain attacks harvest secrets from git history. The correct pattern: `.env` is in `.gitignore`; `.env.example` is committed instead (same keys, no real values). This documents which variables are required without exposing their values. Use secret scanning tools (GitHub's native scanner, `trufflehog`, `gitleaks`) in CI to catch accidental commits of real credentials.

---

**What is configuration drift and how does Infrastructure as Code prevent it?**

Configuration drift is when infrastructure environments (staging, production) diverge from each other and from their intended state due to manual changes made directly to servers or cloud resources — "I'll just change this one setting in the console real quick." Over time, staging and production differ in subtle ways that are never documented, leading to "works on staging, fails in production." Infrastructure as Code (IaC) tools (Terraform, AWS CDK) define infrastructure declaratively in code files committed to git. The IaC tool computes the diff between the declared state and the actual cloud state and applies only the necessary changes. Manual console changes are overwritten on the next `terraform apply` — the code is always the authoritative source.

---

**What does a secrets manager provide that plain environment variables do not?**

Storing secrets as plain environment variables (e.g., in a `.env` file on a server, or hardcoded in a Kubernetes manifest) has no auditability, no rotation, no fine-grained access control, and no versioning. A secrets manager (AWS Secrets Manager, HashiCorp Vault) provides: (1) **encryption at rest** — secrets are never stored in plaintext; (2) **audit log** — every access event (who read which secret, when) is recorded; (3) **fine-grained IAM policies** — the payment service can read `STRIPE_SECRET_KEY` but not `SENDGRID_API_KEY`; (4) **automatic rotation** — database passwords are rotated on a schedule; (5) **versioning** — rollback to a previous secret value; (6) **dynamic secrets** — credentials generated on demand and automatically revoked after use.

---

## Group 6: Monitoring & Observability

**What is the difference between monitoring and observability?**

Monitoring means watching a set of predefined signals — dashboards, alerts, uptime checks. It answers questions you already know to ask: "Is the error rate above 1%?" "Is CPU above 80%?" Observability is the property of a system that allows you to understand its internal state by examining its external outputs (logs, metrics, traces). It answers questions you could not have anticipated in advance: "Why did this one user's request fail differently from everyone else's?" A well-monitored system tells you that something is wrong. A highly observable system tells you *why* and *where*. Observability is built on the three pillars: logs, metrics, and distributed traces.

---

**What are the three pillars of observability and what does each answer?**

**Logs**: timestamped records of discrete events ("user 42 created order 891"). Answer: *what happened*. Best practice: structured (JSON) logs with consistent fields (`traceId`, `userId`, `level`, `message`). **Metrics**: numeric measurements aggregated over time (requests per second, p99 latency, error rate, CPU usage). Answer: *how much and how fast*. Tools: Prometheus + Grafana. **Traces**: records of a single request's journey through all services in a distributed system, broken into spans. Answer: *where specifically did this request spend its time and where did it fail*. Tools: Jaeger, Zipkin, OpenTelemetry + any compatible backend. In practice: you start with a metric alert → drill into logs for context → use the trace ID in logs to pull the full distributed trace.

---

**What are the four golden signals and what does each measure?**

From Google's SRE book — four metrics sufficient to understand any service's health from the user's perspective: (1) **Latency**: how long requests take to complete — always track percentiles (p50, p95, p99), not averages. p99 = 200 ms means 1% of users wait ≥ 200 ms. (2) **Traffic**: how much demand the system is handling — requests per second, messages per second, active users. Establishes a baseline for "normal." (3) **Errors**: rate of failed requests — distinguish 5xx (server errors), 4xx (client errors), and silent errors (wrong data returned with status 200). (4) **Saturation**: how "full" the system is — CPU, memory, connection pool utilization, queue depth. Saturation predicts failures before they happen.

---

**What is the difference between a liveness probe and a readiness probe in Kubernetes?**

**Liveness probe**: "Is this container alive or should it be restarted?" Failure → Kubernetes restarts the container. Should only check the process's own health — a simple HTTP endpoint that returns 200 if the server is running. Must NOT check external dependencies: if the probe checks the database and the database is down, all pods restart in a thundering-herd loop, making the outage worse. **Readiness probe**: "Is this container ready to receive traffic?" Failure → Kubernetes removes the pod from the load balancer's endpoint list (no restart). Should check whether all required dependencies are reachable. The readiness probe is what prevents traffic from being routed to a pod that has started but not yet connected to the database.

---

**What is distributed tracing and what problem does it solve?**

In a monolith, a slow request is easy to locate: add timing logs, profile the code. In a microservices system, a single user action triggers calls across 5-10 services. If the response is slow, it's unclear which service is responsible. Distributed tracing records the full journey: when service A calls B which calls C, each service adds a span (start time, end time, service name, errors) to a shared trace. A `traceId` is generated at the entry point and propagated via the `traceparent` HTTP header through all service calls. The result: a Gantt-chart-like visualization of the entire request, showing exactly which span was slow and why. OpenTelemetry is the standard SDK for trace instrumentation.

---

**What is the difference between SLA, SLO, and SLI?**

**SLI (Service Level Indicator)**: the raw measurement — the specific metric you track. Example: "percentage of requests completing in under 300 ms over a 5-minute window." **SLO (Service Level Objective)**: the internal target for an SLI — the threshold below which you consider the service to be failing users. Example: "99.5% of requests must complete in under 300 ms." Not a customer-facing commitment. **SLA (Service Level Agreement)**: the external, contractual commitment to customers, with financial consequences for breach. Example: "We guarantee 99.9% monthly uptime; if we miss it, customers receive service credits." The SLA is always less strict than the SLO to provide a buffer. Breaking the SLO is an internal alarm; breaking the SLA has financial and legal consequences.

---

**What is an error budget and how does it change team behavior?**

An error budget is the complement of an SLO target: how much unreliability is acceptable per period. Formula: `error budget = 1 − SLO`. Example: 99.9% uptime SLO → 0.1% error budget → 43.2 minutes of allowed downtime per 30 days. The budget is a shared resource between the dev team (which wants to ship features → each deploy risks consuming budget) and the SRE/ops team (which wants reliability). When the error budget is ample, teams deploy more aggressively and take more risk. When the budget is nearly exhausted, teams freeze risky deploys and focus on reliability work. This makes reliability a quantifiable, tradeable resource rather than a vague goal. Error budgets replace the adversarial dynamic between "dev wants to ship" and "ops wants stability."

---

**What is structured logging and why is it better than plain text logs?**

Unstructured log: `"User 42 placed order 891 at 14:30"` — human-readable but machine-hostile. Parsing this with a regex to query by user ID across millions of log lines is slow and fragile. Structured log: a JSON object per event — `{ "level": "info", "msg": "order placed", "userId": 42, "orderId": 891, "traceId": "abc123", "timestamp": "2026-01-15T14:30:00Z" }`. Advantages: (1) log aggregation systems (Loki, Elasticsearch) index fields and allow instant queries like `userId=42 AND level=error`; (2) `traceId` field links log lines to distributed traces; (3) fields are typed — durations are numbers, not strings like "took 120ms"; (4) dashboards and alerts can be built on field values. Use `pino` or `winston` in JSON mode for Node.js applications.

---

## Group 7: Acronyms & Concepts

**Explain CI, CD, IaC, SLA, SLO, and SLI in one sentence each.**

**CI (Continuous Integration)**: the practice of merging code to the main branch frequently, with each merge triggering an automated build-and-test pipeline to catch integration problems immediately. **CD (Continuous Delivery/Deployment)**: Continuous Delivery means every passing build is deployable to production at any moment with a manual approval gate; Continuous Deployment means that gate is automated away and every passing build ships to production automatically. **IaC (Infrastructure as Code)**: defining and managing infrastructure (servers, networks, databases) in version-controlled code files so environments are reproducible, auditable, and free from configuration drift. **SLA (Service Level Agreement)**: an external contractual commitment to customers defining minimum service quality and financial penalties for breach. **SLO (Service Level Objective)**: an internal reliability target (stricter than the SLA) that defines the threshold below which the team considers the service to be failing users. **SLI (Service Level Indicator)**: the raw measurable metric (e.g., percentage of requests under 300 ms) used as input to evaluate whether an SLO is being met.

---

**What does APM stand for and what problem does it solve?**

APM stands for Application Performance Monitoring. It addresses the gap between infrastructure monitoring (CPU, memory, disk) and business-level understanding of application behavior. APM tools auto-instrument the application to capture: every request's duration and status code, slow database queries (with the SQL), external HTTP calls, errors with full stack traces, and distributed traces. They aggregate this data per endpoint, per service, and per user segment. The problem they solve: you know the server is "healthy" (CPU 30%, memory 60%) but users are complaining that checkout is slow. APM shows you that `POST /checkout` has p99 = 4 s and that 80% of that time is a single unindexed database query. Examples: Datadog APM, New Relic, Sentry Performance, Elastic APM.

---

**What is Kubernetes (K8s) and what problem does it solve for deployments?**

Kubernetes (the "8" in K8s stands for the 8 letters between K and s) is a container orchestration platform. The problem: running containers on a single server is simple with Docker. Running hundreds of containers across dozens of servers — scheduling which container runs on which server, restarting crashed containers, scaling from 2 to 20 replicas under load, routing network traffic, rolling out new versions without downtime, distributing secrets — is a complex distributed systems problem. Kubernetes solves this with a declarative model: you describe the desired state (`I want 5 replicas of this image, reachable at port 8080, with 512 MB memory each`) and Kubernetes continuously reconciles actual state to match. It handles scheduling, health-checking, scaling, and rolling updates automatically.

---

**What is GitOps?**

GitOps is a practice where the desired state of both application deployments and infrastructure is stored entirely in Git, and automated systems (Argo CD, Flux) continuously reconcile the live state to match the state declared in Git. All changes — including infrastructure changes — are made via pull requests. Benefits: every change is reviewed, audited, and versioned; the git history is the deployment log; rollback is a git revert; drift between declared and actual state is detected and corrected automatically. GitOps is the convergence of IaC, CI/CD, and the principle that Git is the single source of truth. It is particularly powerful in Kubernetes environments where manifests can be fully declarative.

---

**What is a DAG in the context of CI/CD pipelines?**

DAG stands for Directed Acyclic Graph — a mathematical structure where edges (connections) are directional and there are no cycles (no path returns to its starting node). In CI/CD, a DAG describes job dependencies: "job B must run after job A." The "directed" part means A → B (not B → A). The "acyclic" part means there is no circular dependency (A → B → A). Traditional stage-based pipelines are a simple DAG where all jobs in stage 2 wait for all jobs in stage 1. Modern pipelines (GitLab CI's `needs:`, GitHub Actions' `needs:`) allow arbitrary DAG shapes: `deploy-preview` can depend only on `build`, running in parallel with `test-e2e`, dramatically reducing total pipeline time compared to waiting for the full stage.

---

**What is OpenTelemetry (OTel) and why has it become the standard?**

OpenTelemetry is a vendor-neutral, open-source observability framework providing APIs, SDKs, and tools for generating, collecting, and exporting telemetry data — traces, metrics, and logs. Before OTel, instrumenting your application for observability meant choosing a vendor (Datadog, New Relic, Jaeger) and installing their proprietary agent. Switching vendors required re-instrumenting the entire codebase. OTel solves this: you instrument once with the OTel SDK (using standard APIs), export to an OTel Collector, and then route from the collector to any backend — Jaeger, Datadog, Honeycomb, Grafana Tempo — by changing the collector's exporter config, not the application code. Backed by the CNCF and supported by every major observability vendor. For new projects, OTel is the only reasonable choice for trace instrumentation.

---

**What is the difference between uptime monitoring and application performance monitoring (APM)?**

Uptime monitoring (external synthetic monitoring): a probe outside your infrastructure periodically sends HTTP requests to your public URLs and alerts if they do not return a successful response within a timeout. It simulates the most basic user experience: "Can a user reach the site at all?" Tools: UptimeRobot, Pingdom, Checkly. Catches: DNS failures, CDN outages, load balancer misconfigurations, full service unavailability. APM (internal instrumentation): agents running inside your application capture detailed data about every request — SQL queries, external API calls, error traces, per-endpoint latency. Catches: slow code paths, unindexed queries, memory leaks, error rate spikes for specific endpoints. You need both: uptime monitoring catches "the site is down," APM explains "this specific endpoint is slow for users in Europe due to a missing database index."
