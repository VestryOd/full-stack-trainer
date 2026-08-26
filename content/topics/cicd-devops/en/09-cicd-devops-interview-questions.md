# CI/CD and DevOps Interview Questions

CI stands for continuous integration: every merge into the main branch triggers an automated build and test run. CD stands for continuous delivery or continuous deployment; the first question below is about that difference. DevOps is the practice of one team owning both development and operations.

## Group 1: CI/CD Fundamentals

**What is the difference between Continuous Delivery and Continuous Deployment?**

The difference is one manual approval gate in front of production.

Both start the same way: every change that passes the automated pipeline is packaged into a deployable artifact and released to staging.

- **Continuous Delivery** stops there: the production deploy waits for a human to click the button.
- **Continuous Deployment** removes that button: every passing build goes straight to production on its own.

Both need a pipeline reliable enough that a failing build really means "do not ship."

---

**What is a CI pipeline and what steps does it typically include?**

A CI pipeline is a sequence of automated steps triggered by a code change: a push or a pull request. The typical order:

1. Check out the source code.
2. Install dependencies.
3. Run the linter and the type checker.
4. Run unit and integration tests.
5. Build the application.
6. Publish an artifact: a Docker image to a registry, or a bundle to S3 (Simple Storage Service, the Amazon Web Services object store).
7. Optionally deploy to staging.

The steps run from cheapest to most expensive. A cheap failure such as a lint error catches the problem before the full test suite or the Docker build.

---

**What is an artifact and why should you build it once and promote it through environments?**

An artifact is any file produced by a build step: a compiled JS bundle, a Docker image, a Lambda ZIP, a binary.

"Build once, promote everywhere" means the same artifact goes to staging and then to production, never rebuilt per environment. Rebuilding introduces variance:

- An npm package resolves to a different version.
- Environment variables get baked in differently.
- A transient download fails.

What you tested on staging must be byte-for-byte identical to what goes to production. The artifact is pushed to a registry: Docker Hub, ECR (Elastic Container Registry) or S3. Its tag is the commit hash, so any version is reproducible.

---

**What does "pipeline as code" mean and what are its advantages?**

Pipeline as code means the CI/CD pipeline is defined in a configuration file committed next to the application code. That file is usually YAML, the configuration format where nesting is shown by indentation. Four advantages:

- Pipeline changes go through the same pull request review as code changes. No more "accidental" edits.
- The history of those changes is visible in `git log`.
- The pipeline is reproducible: any branch carries its own configuration, and it behaves the same for every developer.
- Rollback is a `git revert`.

Contrast Jenkins of the 2010s, where pipelines were configured by clicking through a web interface: invisible, hard to audit, impossible to version.

---

**What is a runner (agent) and what are the trade-offs between hosted and self-hosted runners?**

A runner is the machine where pipeline jobs actually execute. The CI scheduler assigns a triggered job to a free runner, which clones the repository, runs the steps and reports the result.

**Hosted runners**, provided by the platform (GitHub-hosted, GitLab.com shared):

- A fresh virtual machine (VM) for every job.
- Zero maintenance, billed per minute.
- No access to your private networks.

**Self-hosted runners** — machines you own and register with the CI platform:

- They can reach private databases and private network segments, such as a VPC (virtual private cloud).
- The hardware is fully yours, and the cost is fixed: your own servers.
- Operating system updates, security patches and disk cleanup are on you.

Security rule: never use self-hosted runners on a public repository. A malicious pull request can modify the workflow and run arbitrary code on your machine.

---

## Group 2: GitHub Actions & GitLab CI

**What is the difference between `on: push` and `on: pull_request` triggers in GitHub Actions?**

The `on: push` trigger fires when a commit lands in the repository: main, a feature branch, or any branch matching a pattern. The `on: pull_request` trigger fires when a pull request is opened, updated or synchronized.

The usual split:

- `on: pull_request` runs tests and linting, validating the proposed change.
- `on: push` to `main`, after the pull request is merged, runs the deployment pipeline.

One important difference: `on: pull_request` from a fork gets read-only permissions and no repository secrets at all.

---

**How do matrix builds work and when are they useful?**

A matrix build is one job definition that GitHub Actions expands into several parallel jobs by combining matrix values.

For example, `matrix: { node: [18, 20, 22] }` spawns three parallel jobs, each running a different Node.js version. Matrices can be multi-dimensional: `matrix: { os: [ubuntu-latest, windows-latest], node: [18, 20] }` gives 4 jobs.

Use cases:

- Testing across several Node.js, Python or Java versions.
- Testing on several operating systems.
- Testing against several database versions.

Each matrix combination is a fully isolated job with its own runner.

---

**What is the difference between a reusable workflow and a composite action in GitHub Actions?**

A **reusable workflow** is a complete workflow that runs as its own job on its own runner. You define it with `on: workflow_call` and call it with `uses: ./.github/workflows/deploy.yml`. It can hold many steps and its own `env:` and `with:` inputs, in complete isolation.

A **composite action** is a reusable sequence of steps that runs *inside an existing job* and shares that job's runner. You define it in an `action.yml` with `runs.using: composite`.

Which to pick:

- Composite action — to abstract repeated setup steps within one job: install, auth, configure.
- Reusable workflow — to share a whole job or deployment flow across repositories.

---

**What is the difference between `only/except` and `rules` in GitLab CI, and which should you use?**

Always use `rules`. The `only/except` keyword is deprecated and will be removed.

The legacy form is `only: [main, merge_requests]`: the job runs only on the listed branches or events. Its limits:

- Conditions cannot be combined.
- CI variables are not available inside a condition.
- `when: manual` cannot be set conditionally.

The modern `rules` keyword is an ordered list of `if/when/changes` conditions evaluated top to bottom; the first matching rule wins. It supports:

- `if: $CI_COMMIT_BRANCH == "main"`
- `changes: [src/**/*]` — run only if source files changed
- `when: manual`
- `allow_failure: true`, per rule

---

**What does the `needs:` keyword do in GitLab CI, and what structure does it create?**

The `needs:` keyword defines explicit job dependencies. It turns the pipeline from a stage-based sequence into a DAG. That is a directed acyclic graph: edges point one way, and no path loops back.

Without `needs:`, every job in a stage waits for the whole previous stage. With `needs:`, a job starts as soon as its own dependencies finish, whatever stage it sits in. For example, `deploy-preview` can depend only on `build` and never wait for `test-e2e` in the same stage, which cuts total pipeline time significantly.

GitHub Actions does the same with `needs:` at the job level.

---

**How do you securely handle secrets in GitHub Actions?**

Secrets live in repository or organization Settings → Secrets, and after the initial configuration they never appear in logs. Inside a workflow you read them through `${{ secrets.MY_SECRET }}`.

Five rules:

1. Never hardcode a secret in the workflow YAML file.
2. Never `echo` a secret value. GitHub masks the values it knows about, but the mask is not foolproof.
3. For production credentials, use environment-level secrets (`environment: production`). A job using them waits for human approval before it runs.
4. For third-party API keys, prefer OIDC (OpenID Connect) federated tokens over static keys that live forever. AWS (Amazon Web Services), GCP (Google Cloud Platform) and Azure all support this.
5. Audit which workflows can read which secrets.

---

**What is Docker-in-Docker (dind) and when is it required in GitLab CI?**

Docker-in-Docker (dind) is a setup where a Docker daemon runs *inside* a Docker container. That lets `docker build` and `docker push` run inside a CI job that is itself a container.

You need it in GitLab CI when the Docker executor runs jobs as containers and a job has to build Docker images. Declare it as a service — `services: - docker:24-dind` — with `DOCKER_HOST: tcp://docker:2376`.

Security implication: dind requires **privileged mode**, so the container has full access to the host kernel. That is a significant risk in a shared environment. The alternative is Kaniko: it builds Docker images without a daemon and without privileged mode.

---

## Group 3: Docker

**What is the difference between a Docker image and a container?**

An image is a read-only, layered snapshot of a filesystem. It holds everything needed to run the application: operating system base, runtime, dependencies, compiled code. An image is built from a Dockerfile and stored in a registry.

A container is a running instance of an image: the image's filesystem plus a writable top layer, running as an isolated process on the host.

The analogy: an image is a class definition, a container an instance of it. Many containers can run from one image at once. Images are built once and promoted; containers are ephemeral and replaceable.

---

**What are Docker image layers and why do they matter for build performance?**

Each Dockerfile instruction (`FROM`, `RUN`, `COPY`, `ADD`) creates a new read-only layer — a diff relative to the layer below it.

Layers are cached. If an instruction and its inputs have not changed since the last build, Docker reuses the cached layer instead of re-running it. A change to any layer invalidates the cache for every layer below it.

That makes layer ordering critical. Put the instructions that change rarely first:

- Installing operating system packages.
- Copying `package.json`.
- Running `npm install`.

Then come the instructions that change on almost every commit, such as copying the application source. The practical rule `COPY package*.json ./` → `RUN npm ci` → `COPY . .` keeps the `npm ci` layer cached across source changes.

---

**What is the difference between `CMD` and `ENTRYPOINT`, and between exec form and shell form?**

`ENTRYPOINT` defines the fixed executable that always runs. `CMD` supplies default arguments that you can override at `docker run` time. When both are present, the container runs `ENTRYPOINT` with the arguments from `CMD`.

The form matters more than it looks:

- **Shell form** (`CMD node server.js`) invokes `sh -c "node server.js"`. That makes `sh` the container's PID (process identifier) 1, with Node.js as its child. And `sh` does not forward `SIGTERM` to children, so graceful shutdown is broken.
- **Exec form** (`CMD ["node", "server.js"]`) runs Node.js directly as PID 1. It receives `SIGTERM` and can shut down gracefully.

Always use exec form for the main process. Shell form is fine for `RUN` build steps.

---

**What is PID 1 in a container and why does it matter?**

In Linux, PID 1 is the init process — the first process the kernel starts. It reaps zombie child processes and forwards signals. In a Docker container, PID 1 is the process defined by `CMD` or `ENTRYPOINT`.

If shell form makes `sh` the PID 1, it does not forward `SIGTERM` to its children. The chain from there is short:

1. Kubernetes stops the pod and sends `SIGTERM`.
2. The `sh` process ignores it.
3. Kubernetes waits out the grace period, 30 seconds by default.
4. Kubernetes sends `SIGKILL`. The container is killed forcefully and every in-flight request is dropped.

With exec form your application is PID 1, receives `SIGTERM` directly and can shut down gracefully. For Node.js that means `CMD ["node", "server.js"]`, not `CMD node server.js`.

---

**What is a multi-stage build and what problem does it solve?**

A multi-stage build uses several `FROM` instructions in one Dockerfile, each starting a new build stage. Files move between stages with `COPY --from=builder`.

The final image contains only what is explicitly copied into the last stage. Build tools, dev dependencies, the TypeScript compiler and test files are left behind in earlier stages. The production image ends up with the Node.js runtime and compiled JS — no TypeScript compiler, no `@types/*` packages, no test frameworks.

Typical size reduction: from about 400 megabytes with all build tools to about 80 for the runtime alone. Smaller images pull faster, expose a smaller attack surface and cost less to store.

---

**Why should containers run as a non-root user?**

By default the process inside a Docker container runs as root, the user with identifier 0. Say an attacker exploits a vulnerability and escapes the container through a kernel bug or a misconfiguration. They then hold full root access to the host.

Running as a non-root user limits the damage: an escaped process has the same restricted privileges as an ordinary user of the operating system.

In a Dockerfile that is `USER node`: the `node:*` base images already contain a `node` user with identifier 1000. Make sure the files your application writes to are owned by that user. Some container runtimes can enforce non-root as a policy — Kubernetes does it with Pod Security Admission.

---

## Group 4: Deployment Strategies

**What is zero-downtime deployment and how is it achieved?**

Zero-downtime deployment means the service stays available during a code update: no dropped requests, no user-visible errors. Two things have to work together.

- An infrastructure strategy that keeps old instances running while new ones start: rolling update, blue-green or canary.
- Graceful shutdown in the application. On `SIGTERM` the instance stops accepting new connections but finishes the requests already in flight.

Without graceful shutdown, even a perfect rolling update drops requests on every pod replacement. Database migrations must stay backward compatible too, since the old and new version run at the same time.

---

**What is the difference between rolling, blue-green, and canary deployments?**

Three strategies:

- **Rolling update.** Instances are replaced one at a time, or in small batches. Both versions serve traffic during the rollout, so the API and the database schema must stay backward compatible. Cheapest of the three, built into Kubernetes and ECS (Elastic Container Service).
- **Blue-green.** Two identical environments are maintained. The new version is deployed and tested in the idle one, then the load balancer switches traffic instantly. No mixed-version period, rollback is a switch back — but you pay for double infrastructure.
- **Canary.** A small share of traffic, say 5%, goes to the new version while the rest stays on the old. You observe it and raise the share gradually. Smallest damage radius of the three, but it needs traffic-splitting infrastructure: a service mesh or a smart load balancer.

---

**What is the expand-contract migration pattern and when is it needed?**

The expand-contract pattern lets you make a breaking database schema change without downtime. During a rolling deploy the old and the new version both run against the same database, so one dangerous migration is split into three deploys:

1. **Expand.** Add the new column as nullable: no lock, backward compatible, and the old code ignores it.
2. **Backfill.** Deploy code that writes to both the old and the new column, then run a background job to populate the new column for existing rows.
3. **Contract.** Once all rows are populated and the old code is gone, make the column `NOT NULL` and drop the old column.

Common pitfall: adding a `NOT NULL` column with a `DEFAULT` in a single migration on a large table. PostgreSQL then rewrites the entire table and holds a full table lock.

---

**What is a feature flag and how is it different from a canary release?**

A feature flag (feature toggle) is an `if` statement in application code that checks a configuration value at runtime: `if (flags.isEnabled('new-checkout', user))`. The code is already deployed to production but stays inactive until the flag is turned on.

A canary release works one level lower, in the infrastructure. Two versions of the service run at once, and a load balancer or service mesh routes a share of traffic to the new one.

The practical difference:

- A flag can be toggled per user, per organization or per percentage, with no deployment at all.
- A canary release means two deployed versions are actually running.

They complement each other: use a canary release to validate the new binary, then feature flags for controlled exposure.

---

**What is graceful shutdown and how do you implement it in Node.js?**

Graceful shutdown means the process catches `SIGTERM` and then winds down in order:

1. Stop accepting new connections.
2. Wait for in-flight requests to complete.
3. Release resources: database connections, message queue consumers.
4. Exit with code 0.

In Node.js with Express:
```javascript
process.on('SIGTERM', async () => {
  server.close(async () => {        // stop accepting new HTTP connections
    await prisma.$disconnect();     // close DB connection pool
    process.exit(0);
  });
});
```
Kubernetes sends `SIGTERM` and waits `terminationGracePeriodSeconds`, 30 seconds by default, before sending `SIGKILL`. The application must finish its shutdown inside that window. For NestJS, `app.enableShutdownHooks()` wires this up through the `OnApplicationShutdown` lifecycle hook.

---

## Group 5: Environments, Config & Secrets

**What is the difference between an environment variable, a configuration file, and a secret?**

Three kinds of setting, split by sensitivity:

- **Environment variables** — non-sensitive runtime parameters: feature flags, log level, API URLs, environment name. Simple key-value pairs, easy to override per environment, visible in `process.env`.
- **Configuration files** — structured non-sensitive settings: database schema name, pagination defaults, supported locales. Committed to the repository and loaded at startup.
- **Secrets** — sensitive credentials that must never appear in source code, logs or plain-text storage. Database passwords, API keys, JWT (JSON Web Token) signing keys, TLS (Transport Layer Security) private keys.

Secrets are stored in a secrets manager (AWS Secrets Manager, HashiCorp Vault) and injected into the process at runtime via environment variables. The boundary: if leaking it would cause a security incident, it is a secret.

---

**Why should `.env` files never be committed to version control?**

Once a secret is committed it is effectively permanent. Deleting it in a later commit does not help: it stays in git history and `git log -p` recovers it. Anyone with repository access can read it — current and future team members, automated tools, GitHub's own indexing. Supply chain attacks harvest secrets from git history.

The correct pattern: `.env` goes into `.gitignore`, and `.env.example` is committed instead, with the same keys and no real values. That documents which variables are required without exposing them. Run a secret scanner in CI too — GitHub's native scanner, `trufflehog` or `gitleaks` — to catch accidental commits of real credentials.

---

**What is configuration drift and how does Infrastructure as Code prevent it?**

Configuration drift is when environments diverge from each other and from their intended state because of manual changes. Someone opens the cloud console and thinks: I'll just change this one setting real quick. Over time staging and production differ in subtle, undocumented ways, and you get "works on staging, fails in production."

Infrastructure as Code prevents it. Terraform and AWS CDK (Cloud Development Kit) define infrastructure declaratively in code files committed to git.

The tool computes the diff between the declared state and the actual cloud state, then applies only the necessary changes. A manual console change is overwritten on the next `terraform apply`: the code is always the authoritative source.

---

**What does a secrets manager provide that plain environment variables do not?**

Plain environment variables give you no auditability, no rotation, no fine-grained access control and no versioning. That holds for a `.env` file on a server and for a hardcoded Kubernetes manifest value alike. A secrets manager (AWS Secrets Manager, HashiCorp Vault) adds six things:

- **Encryption at rest.** Secrets are never stored in plaintext.
- **Audit log.** Every access event is recorded: who read which secret, and when.
- **Fine-grained access policies.** With IAM (Identity and Access Management) the payment service can read `STRIPE_SECRET_KEY` but not `SENDGRID_API_KEY`.
- **Automatic rotation.** Database passwords are rotated on a schedule.
- **Versioning.** You can roll back to a previous secret value.
- **Dynamic secrets.** Credentials are generated on demand and revoked automatically after use.

---

## Group 6: Monitoring & Observability

**What is the difference between monitoring and observability?**

Monitoring means watching a set of predefined signals: dashboards, alerts, uptime checks. It answers questions you already know to ask. Is the error rate above 1%? Is the CPU (central processing unit) above 80%?

Observability is the property of a system that lets you understand its internal state from external outputs: logs, metrics, traces. It answers questions you could not have anticipated. Why did this one user's request fail differently from everyone else's?

A well-monitored system tells you that something is wrong. A highly observable system tells you *why* and *where*. Observability rests on three pillars: logs, metrics and distributed traces.

---

**What are the three pillars of observability and what does each answer?**

- **Logs** — timestamped records of discrete events, such as "user 42 created order 891". They answer *what happened*. Best practice: structured JSON logs with consistent fields — `traceId`, `userId`, `level`, `message`.
- **Metrics** — numeric measurements aggregated over time: requests per second, p99 latency, error rate, processor usage. They answer *how much and how fast*. Tools: Prometheus and Grafana.
- **Traces** — records of one request's journey through all services of a distributed system, broken into spans. They answer *where exactly this request spent its time and where it failed*. Tools: Jaeger, Zipkin, OpenTelemetry with any compatible backend.

In practice you walk them in that order. A metric alert fires, and you drill into logs for context. Then the trace ID from a log line pulls the full distributed trace.

---

**What are the four golden signals and what does each measure?**

Google's SRE (site reliability engineering) book names four metrics that are enough to judge any service's health from the user's side.

1. **Latency** — how long requests take. Always track percentiles (p50, p95, p99), not averages. A p99 of 200 ms means 1% of users wait 200 ms or longer.
2. **Traffic** — how much demand the system handles: requests per second, messages per second, active users. It establishes the baseline for "normal".
3. **Errors** — the rate of failed requests. Distinguish 5xx server errors, 4xx client errors and silent errors, where wrong data comes back with status 200.
4. **Saturation** — how "full" the system is: processor, memory, connection pool utilization, queue depth. Saturation predicts failures before they happen.

---

**What is the difference between a liveness probe and a readiness probe in Kubernetes?**

| | Liveness probe | Readiness probe |
|---|---|---|
| Asks | Is this container alive, or should it be restarted? | Is this container ready to receive traffic? |
| On failure | Kubernetes restarts the container | Kubernetes drops the pod from the load balancer, no restart |
| Should check | Only the process's own health | Whether all required dependencies are reachable |

The liveness probe should be a simple HTTP endpoint that returns 200 while the server is running. It must **never** check external dependencies. If it checks the database and the database goes down, all pods restart in a thundering-herd loop and the outage gets worse.

The readiness probe keeps traffic away from a pod that has started but not yet connected to the database.

---

**What is distributed tracing and what problem does it solve?**

In a monolith a slow request is easy to locate: add timing logs, profile the code. In a microservices system a single user action triggers calls across 5-10 services. When the response is slow, it is unclear which service is responsible.

Distributed tracing records the full journey. When service A calls B which calls C, each service adds a span to a shared trace: start time, end time, service name, errors. A `traceId` is generated at the entry point and propagated through every call in the `traceparent` HTTP header.

The result is a Gantt-chart-like view of the whole request, showing which span was slow and why. OpenTelemetry is the standard toolkit for trace instrumentation.

---

**What is the difference between SLA, SLO, and SLI?**

Three layers of the same promise: the Service Level Indicator (SLI), the Service Level Objective (SLO) and the Service Level Agreement (SLA).

- **SLI** — the raw measurement, the specific metric you track. Example: the share of requests completing in under 300 ms over a 5-minute window.
- **SLO** — the internal target for an SLI, the threshold below which you consider the service to be failing users. Example: 99.5% of requests must complete in under 300 ms. It is not a customer-facing commitment.
- **SLA** — the external, contractual commitment to customers, with financial consequences for a breach. Example: we guarantee 99.9% monthly uptime, and if we miss it customers receive service credits.

The SLA is always less strict than the SLO, which leaves a buffer. Breaking the SLO is an internal alarm; breaking the SLA has financial and legal consequences.

---

**What is an error budget and how does it change team behavior?**

An error budget is the complement of an SLO target: how much unreliability is acceptable per period. The formula is `error budget = 1 − SLO`. A 99.9% uptime SLO leaves a 0.1% budget, which is 43.2 minutes of allowed downtime per 30 days.

The budget is a shared resource between two teams pulling in opposite directions. The dev team wants to ship features, and every deploy risks spending budget. The reliability team wants it intact.

- While the budget is ample, teams deploy more aggressively and take more risk.
- When the budget is nearly exhausted, teams freeze risky deploys and focus on reliability work.

That makes reliability a quantifiable, tradeable resource rather than a vague goal. It replaces the old standoff between "dev wants to ship" and "ops wants stability."

---

**What is structured logging and why is it better than plain text logs?**

An unstructured log line — `"User 42 placed order 891 at 14:30"` — is human-readable but machine-hostile. Parsing it with a regex to query by user ID across millions of log lines is slow and fragile.

A structured log is one JSON object per event: `{ "level": "info", "msg": "order placed", "userId": 42, "orderId": 891, "traceId": "abc123", "timestamp": "2026-01-15T14:30:00Z" }`.

Four advantages:

- Log aggregation systems (Loki, Elasticsearch) index the fields, so `userId=42 AND level=error` is an instant query.
- The `traceId` field links log lines to distributed traces.
- Fields are typed. A duration is a number, not a string like "took 120ms".
- Dashboards and alerts can be built on field values.

Use `pino` or `winston` in JSON mode for Node.js applications.

---

## Group 7: Acronyms & Concepts

**Explain CI, CD, IaC, SLA, SLO, and SLI in one sentence each.**

- **CI (Continuous Integration)** — merging code into the main branch frequently, with every merge triggering an automated build-and-test pipeline that catches integration problems immediately.
- **CD (Continuous Delivery / Deployment)** — Continuous Delivery makes every passing build deployable at any moment, behind a manual approval gate. Continuous Deployment automates that gate away.
- **IaC (Infrastructure as Code)** — defining infrastructure (servers, networks, databases) in version-controlled code files, so environments stay reproducible, auditable and free from drift.
- **SLA (Service Level Agreement)** — an external contractual commitment to customers that defines minimum service quality and financial penalties for a breach.
- **SLO (Service Level Objective)** — an internal reliability target, stricter than the SLA, below which the team treats the service as failing users.
- **SLI (Service Level Indicator)** — the raw metric feeding the SLO, for example the share of requests under 300 ms.

---

**What does APM stand for and what problem does it solve?**

APM stands for Application Performance Monitoring. It fills the gap between infrastructure monitoring — processor, memory, disk — and a business-level view of what the application does.

APM tools auto-instrument the application and capture:

- Duration and status code of every request.
- Slow database queries, with the SQL (Structured Query Language) text.
- External HTTP calls.
- Errors with full stack traces.
- Distributed traces.

The data is aggregated per endpoint, per service and per user segment.

The problem it solves: the server looks healthy at 30% processor and 60% memory, yet users complain that checkout is slow. APM shows that `POST /checkout` has a p99 of 4 s, and that 80% of that time is one unindexed database query. Examples: Datadog APM, New Relic, Sentry Performance, Elastic APM.

---

**What is Kubernetes (K8s) and what problem does it solve for deployments?**

Kubernetes is a container orchestration platform. The "8" in K8s stands for the 8 letters between K and s.

Running containers on a single server is simple with Docker. Running hundreds of them across dozens of servers is a hard distributed systems problem:

- Scheduling which container runs on which server.
- Restarting crashed containers.
- Scaling from 2 to 20 replicas under load.
- Routing network traffic.
- Rolling out new versions without downtime.
- Distributing secrets.

Kubernetes solves this with a declarative model. You describe the desired state: 5 replicas of this image, reachable at port 8080, 512 megabytes of memory each. Kubernetes then reconciles the actual state to match, handling scheduling, health checks, scaling and rolling updates.

---

**What is GitOps?**

GitOps is a practice that keeps the desired state of both application deployments and infrastructure entirely in Git. Automated systems (Argo CD, Flux) continuously reconcile the live state to match what Git declares. Every change, infrastructure included, is made through a pull request.

Benefits:

- Every change is reviewed, audited and versioned.
- The git history is the deployment log.
- Rollback is a `git revert`.
- Drift between declared and actual state is detected and corrected automatically.

GitOps is where Infrastructure as Code, CI/CD and "Git is the single source of truth" converge. It is strongest in Kubernetes, where manifests can be fully declarative.

---

**What is a DAG in the context of CI/CD pipelines?**

DAG stands for Directed Acyclic Graph. It is a structure where edges have a direction and no path returns to its starting node.

In CI/CD a DAG describes job dependencies: job B must run after job A. "Directed" means A → B and not B → A. "Acyclic" means there is no circular dependency such as A → B → A.

A traditional stage-based pipeline is a simple DAG: every job in stage 2 waits for every job in stage 1.

Modern pipelines allow arbitrary DAG shapes through the `needs:` keyword, in GitLab CI and GitHub Actions. Then `deploy-preview` can depend only on `build` and run in parallel with `test-e2e`, which cuts total pipeline time dramatically.

---

**What is OpenTelemetry (OTel) and why has it become the standard?**

OpenTelemetry is a vendor-neutral, open-source observability framework. It provides the APIs, libraries and tools for generating, collecting and exporting telemetry data: traces, metrics and logs.

Before it, instrumenting an application meant choosing a vendor — Datadog, New Relic, Jaeger — and installing its proprietary agent. Switching vendors required re-instrumenting the entire codebase.

OpenTelemetry breaks that lock-in. You instrument once against its standard APIs, export to an OpenTelemetry Collector, then route from the collector to any backend: Jaeger, Datadog, Honeycomb, Grafana Tempo. Changing backend means editing the collector's exporter config, not the application code.

It is backed by the CNCF (Cloud Native Computing Foundation) and by every major observability vendor. For new projects it is the only reasonable choice for tracing.

---

**What is the difference between uptime monitoring and application performance monitoring (APM)?**

Uptime monitoring is external and synthetic. A probe outside your infrastructure sends HTTP requests to your public URLs on a schedule and alerts if no successful response arrives in time. It simulates the most basic user experience: can a user reach the site? Tools: UptimeRobot, Pingdom, Checkly.

It catches:

- DNS (Domain Name System) failures.
- Outages of the CDN (content delivery network).
- Load balancer misconfigurations.
- Full service unavailability.

APM is internal instrumentation. Agents inside your application capture detailed data on every request: SQL queries, external API calls, error traces, per-endpoint latency. It catches slow code paths, unindexed queries, memory leaks and error spikes on specific endpoints.

You need both. Uptime monitoring catches "the site is down"; APM explains "this endpoint is slow for users in Europe because of a missing database index."
