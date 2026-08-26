# CI/CD and DevOps Glossary

Every acronym and term a fullstack developer is likely to meet in interviews, job descriptions, and day-to-day work. CI (Continuous Integration) means merging code into the shared branch many times a day. CD (Continuous Delivery or Continuous Deployment) means shipping every green build onward. DevOps (Development plus Operations) means running development and operations as one process.

Entries are ordered alphabetically. A term with its own article here gets a short definition plus a link.

---

## A

**Agent**

Another word for **runner** — the machine that executes CI/CD pipeline jobs. The term "agent" is used by Jenkins, Azure Pipelines, and some other tools; "runner" is used by GitHub Actions and GitLab CI.

See: *Runner*.

**ALB** — Application Load Balancer

The managed load balancer of AWS (Amazon Web Services). It works at the application layer — layer 7 of the Open Systems Interconnection (OSI) model. That means it reads HTTP and HTTPS (HTTP Secure) traffic, not just packets.

A classic load balancer routes on network address (IP) and port only. An ALB routes on URL path, hostname, headers or query parameters. Hence its use in blue-green and canary deployments, where traffic moves between environments.

**APM** — Application Performance Monitoring

A category of tools that combine distributed traces, metrics, and sometimes logs into a unified view focused on application-level performance. APM tools automatically instrument your code to trace every request, identify slow code paths, and group errors. Examples: Datadog APM, New Relic, Sentry, Elastic APM.

See: [Monitoring and Observability](./07-monitoring-and-observability.md).

**Artifact**

Any file or set of files produced by a build step and stored for use by a later step or for deployment. Examples: a compiled JavaScript bundle, a Docker image, a `.zip` of Lambda function code, a test coverage report. The key principle: build the artifact once and deploy the same artifact to every environment (staging, production) — never rebuild from source for each environment.

See: [CI/CD Fundamentals](./01-cicd-fundamentals.md).

**Artifact Registry** (also: **Container Registry** when specific to Docker images)

A storage service where build artifacts are uploaded, versioned, and pulled from during deployments. For Docker images: GitHub Container Registry (ghcr.io), Docker Hub, AWS ECR (Elastic Container Registry), Google Artifact Registry. The registry is not the same as version control (git) — it stores compiled/packaged output, not source code.

---

## B

**Base Image**

The starting point for a Docker image, specified in the `FROM` instruction of a Dockerfile. Every image is built on top of a base image. Common examples: `node:20-alpine` (Node.js on Alpine Linux), `python:3.12-slim`, `ubuntu:22.04`. `FROM scratch` starts from a completely empty image — for minimal single-binary applications.

**Blast Radius**

The scope of impact when something goes wrong in a deployment. Deployment strategies such as canary releases and feature flags exist to keep that scope small.

If a new version has a bug, only a small share of users meet it. The issue is detected and rolled back before the rest are affected. "Minimizing blast radius" is a standard phrase in reliability engineering.

**Blue-Green Deployment**

A deployment strategy that maintains two identical production environments ("blue" and "green"). The new version is deployed to the idle environment, tested, and then traffic is switched instantaneously via the load balancer. The old environment remains running for fast rollback. Eliminates the mixed-version period of rolling deployments but doubles infrastructure cost.

See: [Deployment Strategies](./05-deployment-strategies.md).

**Build Context** (Docker)

The set of files sent to the Docker daemon when `docker build` runs — typically the contents of the current directory. Files listed in `.dockerignore` are excluded from it.

A large build context slows the build down. Include `node_modules/` and every one of those files is transferred to the daemon before the first Dockerfile instruction runs.

---

## C

**Canary Release**

Named after the canary in a coal mine. A deployment strategy that sends a small share of real user traffic — 5%, say — to the new version. Everyone else stays on the stable one.

The new version is watched for errors and performance regressions. If it looks healthy, its share of traffic grows step by step. This differs from a feature flag: a canary is an infrastructure-level traffic split between two deployed versions.

See: [Deployment Strategies](./05-deployment-strategies.md).

**CDK** — Cloud Development Kit (AWS CDK)

The infrastructure as code (IaC) tool of AWS. You define AWS infrastructure in TypeScript, Python, Java, or another real language, instead of writing JSON or YAML (a whitespace-based configuration format) templates. CDK code compiles down to CloudFormation templates, so you write application code and get configuration out.

See: *IaC*, *CloudFormation*.

**cgroups** — Control Groups

A Linux kernel feature that caps what a group of processes may use: CPU (central processing unit) time, memory, disk input/output, and network bandwidth.

Together with namespaces, cgroups are the technology that makes Docker containers possible. Each container's resource usage is bounded by its own cgroup, so one container cannot starve the others on the same host.

**CI** — Continuous Integration

The practice of merging code changes into the shared main branch frequently — several times a day. Each merge automatically triggers a pipeline that builds and tests the code. The goal: catch integration problems minutes after they appear, not days later. CI is the foundation CD is built on.

See: [CI/CD Fundamentals](./01-cicd-fundamentals.md).

**CD** — Continuous Delivery / Continuous Deployment

Two distinct concepts share the same abbreviation.

- **Continuous Delivery** — every passing build is packaged into a deployable artifact and deployed to staging automatically. Production still needs a manual approval gate.
- **Continuous Deployment** — the manual gate is gone. Every passing build is deployed to production automatically.

The difference is one word and one human click.

See: [CI/CD Fundamentals](./01-cicd-fundamentals.md).

**CloudFormation**

The native infrastructure as code service of AWS. You describe resources in JSON or YAML templates, and CloudFormation creates them and keeps managing them:

- EC2 (Elastic Compute Cloud) — virtual machines.
- S3 (Simple Storage Service) — object storage buckets.
- RDS (Relational Database Service) — managed databases.
- Load balancers, networks, queues and the rest of AWS.

Mature and deeply integrated with AWS, but verbose. Many teams prefer CDK, which compiles to CloudFormation.

**Composite Action** (GitHub Actions)

A reusable group of steps packaged into a single `uses:` call, embedded within a job. Composite actions are stored as `action.yml` files (typically in `.github/actions/`). Unlike reusable workflows (which are full jobs), a composite action runs as part of a job alongside other steps. Use when you want to abstract a sequence of setup/install/build steps.

See: [GitHub Actions](./02-github-actions.md).

**Configuration Drift**

The gradual divergence of environments — staging against production — caused by manual changes made to one but not the other. Someone patches production "just this once" and never reflects the change in staging.

Drift is the main cause of "works on staging, broken in production". Infrastructure as Code prevents it by making the code the single source of truth for what exists.

See: *IaC*.

**Configuration Management**

The ongoing maintenance of servers that already exist: installing packages, writing config files, starting services, keeping all of it identical across machines. Tools: Ansible, Chef, Puppet, SaltStack.

Contrast with *Provisioning*, which creates the machines.

**Container**

A running instance of a Docker image. It is the image plus a writable layer on top, running as an isolated process on the host operating system (OS). Containers share the host OS kernel, unlike virtual machines, which each carry their own. They start and stop in milliseconds and are meant to be ephemeral — temporary and replaceable.

See: [Docker Essentials](./04-docker-essentials.md).

**Container Registry**

See: *Artifact Registry*.

**CRD** — Custom Resource Definition (Kubernetes)

An extension mechanism in Kubernetes that lets you add your own resource types to the Kubernetes API. Tools like Argo Rollouts and Cert-Manager work by installing CRDs into the cluster and then providing controllers that act on those custom resources. When you see `apiVersion: argoproj.io/v1alpha1` in a YAML file, that's a CRD-backed resource.

---

## D

**DAG** — Directed Acyclic Graph

A graph whose edges — the connections between nodes — all point one way, with no cycles. No path leads back to where it started.

In CI/CD a DAG describes job dependencies. Job B depends on job A, and that is the direction. No chain of dependencies loops back on itself, and that is the acyclic part. GitLab CI's `needs:` keyword and GitHub Actions' `needs:` key both build DAG-shaped pipelines.

See: [GitLab CI](./03-gitlab-ci.md).

**dind** — Docker-in-Docker

A configuration where a Docker daemon runs inside a Docker container. That lets Docker commands such as `docker build` and `docker push` run inside a CI job which itself runs in a container.

Required in GitLab CI when you use the Docker executor and need to build images. Declared as a service: `services: - docker:24-dind`. It has a security cost, because the container has to run in privileged mode.

See: [GitLab CI](./03-gitlab-ci.md).

**DNS** — Domain Name System

The internet's phone book: a distributed database that translates human-readable domain names such as `api.myapp.com` into network addresses.

This matters to DevOps when traffic has to be switched. A DNS-based switch in a blue-green deployment propagates only as fast as the TTL (Time To Live) allows, which is minutes to hours. That rules it out for instant rollback, so load balancer-based switching is preferred.

**Dockerfile**

A text file containing a sequence of instructions that Docker executes to build an image. Each instruction (`FROM`, `RUN`, `COPY`, `CMD`, etc.) creates a layer in the image. The Dockerfile is committed to the repository and serves as the reproducible recipe for building the application's container image.

See: [Docker Essentials](./04-docker-essentials.md).

**Dotenv** (`.env` file)

A plain text file in the root of a project that stores environment variables in `KEY=VALUE` format, one per line. Loaded at application startup by the `dotenv` library (`import 'dotenv/config'`). Intended for local development only — never committed to version control. The `.env.example` file (with variable names but no real values) is committed instead, as a template for other developers.

See: [Environments and Configuration](./06-environments-and-config.md).

---

## E

**ECR** — Elastic Container Registry

The managed Docker container registry of AWS. You push Docker images to ECR and pull them during deployments to ECS (Elastic Container Service), Lambda, or other AWS services. Images are tagged — with the Git commit hash, for example — and versioned. Private by default: access is controlled by AWS IAM (Identity and Access Management) policies.

**ECS** — Elastic Container Service

The managed container orchestration service of AWS. You define two things:

- A **task definition** — which Docker image to run, how much processor time and memory, which environment variables.
- A **service** — how many copies to run, and which load balancer to attach them to.

ECS then starts, stops and health-checks the containers. It is an alternative to Kubernetes: simpler to operate, less flexible.

**ELK Stack** — Elasticsearch + Logstash + Kibana

A popular open-source log management stack, named after its three parts:

- **Elasticsearch** — a distributed search and analytics engine that stores and indexes log data.
- **Logstash** — a pipeline that ingests logs from many sources, transforms them, and forwards them to Elasticsearch.
- **Kibana** — a web interface for querying and visualizing the data in Elasticsearch.

Often extended with **Beats** (lightweight log shippers) and then called the **Elastic Stack**.

**Error Budget**

The allowable amount of unreliability (downtime, errors, latency violations) permitted before an SLO is breached — expressed as a duration or a count. Formula: `error budget = 1 − SLO target`. Example: SLO of 99.9% availability → 0.1% error budget → 43.2 minutes of allowed downtime per 30-day period. When the error budget is nearly exhausted, teams freeze risky changes; when it is ample, teams can move faster.

See: *SLO*, [Monitoring and Observability](./07-monitoring-and-observability.md).

**Exec Form** (Docker)

The JSON-array way of writing `CMD` and `ENTRYPOINT`: `CMD ["node", "server.js"]`. Docker runs the binary directly, so the process ID (PID) of your application is 1 and it receives `SIGTERM`.

Shell form — `CMD node server.js` — gives process ID 1 to `sh`, which swallows the signal.

See: *PID 1*, *SIGTERM*, [Docker Essentials](./04-docker-essentials.md).

**Expand-Contract Migration** (also: Parallel-Change Pattern)

A safe database migration strategy for zero-downtime deployments. Instead of one deploy carrying a breaking schema change, the change is spread over four deploys:

- **Expand** — add the new column as nullable, so old code keeps working.
- **Migrate** — backfill the data in the background.
- **Contract** — make the column `NOT NULL` once every row has a value.
- **Cleanup** — drop the old column once the old code is gone.

Old and new versions of the application can then run at the same time against the same database.

See: [Deployment Strategies](./05-deployment-strategies.md).

---

## F

**Feature Flag** (also: Feature Toggle, Feature Switch)

A mechanism in application code that turns a feature on or off at runtime, without deploying new code. The feature is already deployed, but gated behind a conditional check such as `if (flagClient.variation('new-checkout', user, false))`.

What it buys you:

- Gradual rollout by percentage of users.
- An instant kill switch that needs no redeploy.
- A/B testing.
- Shipping an unfinished feature to production behind the flag.

A feature flag is not a deployment strategy. It is a technique inside application code.

See: [Deployment Strategies](./05-deployment-strategies.md).

---

## G

**GDPR** — General Data Protection Regulation

A European Union regulation that governs how organizations collect, store, process, and share personal data of EU residents. Relevant to DevOps: logging PII (Personally Identifiable Information) such as email addresses, phone numbers, or IP addresses in application logs may violate GDPR. Logs should store user IDs (pseudonymous identifiers), not raw personal data.

**GitOps** (Git plus operations)

A practice where the desired state of infrastructure and deployments lives in Git. Automated systems continuously reconcile the actual state with what Git says it should be.

Infrastructure changes go through pull requests — reviewed, tested, merged — rather than direct commands. Tools: Argo CD, Flux. The motto is "if it's not in Git, it doesn't exist".

**Graceful Shutdown**

The process by which an application handles a termination signal (`SIGTERM`) cleanly before it exits. In order, it:

- stops accepting new connections;
- finishes the requests already in flight;
- closes its database connections;
- exits with code 0.

Without graceful shutdown, in-flight requests are dropped on every deployment. It is essential for zero-downtime deployments.

See: [Deployment Strategies](./05-deployment-strategies.md), *SIGTERM*.

---

## H

**HCL** — HashiCorp Configuration Language

The domain-specific language used by Terraform and other HashiCorp tools to define infrastructure. HCL is a declarative language — you describe the desired end state, and Terraform figures out how to get there. Human-readable, supports expressions, variables, loops, and modules. Alternative to writing CloudFormation YAML or CDK TypeScript.

**Health Check**

A periodic test that decides whether a service is alive and ready to take traffic. Kubernetes has two of them:

- A **liveness probe** checks whether the process is alive. A failed probe restarts the container.
- A **readiness probe** checks whether the service is ready for traffic. A failed probe removes it from the load balancer, but does not restart it.

In Docker Compose the `healthcheck` key defines that command; `depends_on: condition: service_healthy` waits for it.

See: [Monitoring and Observability](./07-monitoring-and-observability.md).

**Hosted Runner** (also: Managed Runner)

A CI/CD runner provided and managed by the CI platform: GitHub, GitLab and the rest. Each pipeline run gets a fresh virtual machine with common tools pre-installed, and you maintain nothing.

What you give up:

- you pay per minute of compute time;
- the hardware is shared with other platform users;
- the runner cannot reach your private network.

Contrast: *Self-Hosted Runner*.

---

## I

**IaC** — Infrastructure as Code

The practice of defining and managing infrastructure in code files committed to version control, instead of clicking through a web console or running manual commands. Infrastructure here means servers, networks, databases, load balancers.

What you get: reproducibility, an audit trail, environment parity, disaster recovery, and pull-request review of infrastructure changes. Tools: Terraform, AWS CDK, CloudFormation, Pulumi, Ansible.

See: [Environments and Configuration](./06-environments-and-config.md).

**Image** (Docker Image)

A read-only, layered snapshot of a filesystem. It holds everything an application needs to run:

- the base operating system;
- the runtime — Node.js, Python and so on;
- dependencies;
- compiled code and configuration files.

An image is built from a Dockerfile. Many containers can run from the same image at once. The image is the deployment unit: built once, then promoted through environments.

See: *Container*, [Docker Essentials](./04-docker-essentials.md).

**Immutable Infrastructure**

A practice where servers and containers are never modified after deployment. Instead a new image is built and deployed, and the old one is replaced.

To update the application, you build a new Docker image and replace the running containers. You do not open a shell in a container over SSH (Secure Shell) and patch files by hand. That is what makes deployments reproducible and keeps configuration drift off the running instances.

---

## J

**Job** (CI/CD)

A unit of work in a pipeline that runs on a single runner/agent machine. A job consists of a sequence of steps (commands). Jobs in the same pipeline stage run in parallel by default (in GitLab CI) or unless they have `needs:` dependencies (in GitHub Actions). A job produces artifacts and reports a pass/fail result.

See: *Stage*, *Step*, [CI/CD Fundamentals](./01-cicd-fundamentals.md).

---

## K

**K8s** — Kubernetes

An open-source container orchestration platform, originally developed by Google. The name is a numeronym: K, then 8 letters, then s. Kubernetes automates the deployment, scaling and management of containerized applications across a cluster of machines.

Its key concepts:

- **pod** — a group of containers scheduled together;
- **deployment** — a declaration of desired state;
- **service** — a stable network endpoint;
- **ingress** — routing for traffic from outside;
- **namespace** — resource isolation inside a cluster.

The de-facto standard for running containers at scale.

---

## L

**Layer** (Docker)

A single incremental change to a Docker image's filesystem, created by one Dockerfile instruction (`FROM`, `RUN`, `COPY`, `ADD`). Layers are stacked, and each one records only the difference from the layer beneath it.

Layers are cached. If an instruction and its inputs have not changed since the last build, Docker reuses the cached layer. Ordering instructions from least-changed to most-changed maximizes cache reuse and speeds builds up.

See: [Docker Essentials](./04-docker-essentials.md).

**Liveness Probe**

A Kubernetes health check that determines whether a container process is alive and should continue running. If the liveness probe fails, Kubernetes restarts the container. A liveness probe should only check whether the process itself is responsive — not whether external dependencies (database, cache) are available. If it checks external dependencies, a database outage causes all pods to restart in a loop.

See: *Readiness Probe*, [Monitoring and Observability](./07-monitoring-and-observability.md).

**Loki** (Grafana Loki)

A horizontally scalable log aggregation system from Grafana Labs, modelled on Prometheus. Unlike Elasticsearch, Loki does not index the full content of logs — only their labels, the metadata attached to each stream. That makes it much cheaper to run on large volumes.

Loki is queried with LogQL, a query language close to PromQL, and displayed in Grafana dashboards. It pairs with Prometheus for metrics and Tempo for traces to make a full open-source observability stack.

---

## M

**Metrics**

Numeric measurements of system properties, sampled over time and aggregated. Logs are discrete events; metrics show *how much* and *how fast* — request rate, error rate, processor usage, latency percentiles.

The four golden signals, from Google's book on site reliability engineering (SRE): Latency, Traffic, Errors, Saturation. Standard metric types: Counter (only goes up), Gauge (up and down), Histogram (buckets). Tool: Prometheus.

See: [Monitoring and Observability](./07-monitoring-and-observability.md).

**Monitoring**

Watching a set of signals you chose in advance, and alerting when one of them crosses a threshold. Error rate above 1%, latency above 500 ms, disk above 90% full.

Monitoring answers questions you knew to ask. *Observability* is the wider property: answering the ones you did not anticipate.

See: [Monitoring and Observability](./07-monitoring-and-observability.md).

**Multi-Stage Build** (Docker)

A Dockerfile technique that uses several `FROM` instructions, each starting a new build stage. Files are copied from one stage into another with `COPY --from=stage-name`, and the final image holds only what reached the last stage.

Build tools, dev dependencies and source files stay behind. That cuts the production image size down a lot. With the full toolchain it is roughly 400 MB (megabytes); with only the runtime and the compiled output, roughly 80 MB.

See: [Docker Essentials](./04-docker-essentials.md).

---

## N

**Namespace** (Kubernetes)

A mechanism for isolating groups of resources within a single Kubernetes cluster. Resources (pods, services, deployments) in one namespace are isolated from those in another. Commonly used to separate environments (dev, staging, prod) within the same cluster, or to separate teams/applications. Default namespaces: `default`, `kube-system` (cluster components), `kube-public`.

**Non-Root User** (Docker)

A security practice: run container processes as a user other than root, whose user ID is not 0. By default Docker containers run as root, so an attacker who escapes the container holds root on the host.

Adding `USER node` — or any non-root user — to a Dockerfile reduces that risk. The `node:*` base images ship a built-in `node` user with user ID 1000 for exactly this purpose.

See: [Docker Essentials](./04-docker-essentials.md).

---

## O

**Observability**

The property of a system that lets you understand its internal state from the outputs it emits: logs, metrics and traces. A system is highly observable when you can diagnose any failure mode from that data, including failure modes nobody anticipated.

The three pillars of observability are logging, metrics and distributed tracing. *Monitoring* watches signals you defined in advance; observability is the ability to discover the failures you did not.

See: [Monitoring and Observability](./07-monitoring-and-observability.md).

**OpenTelemetry** (OTel)

A vendor-neutral, open-source standard with a software development kit (SDK) for instrumenting applications. It covers three kinds of telemetry: traces, metrics and logs.

OpenTelemetry replaces vendor-specific agents. You instrument your code once and export the data to any compatible backend — Jaeger, Datadog, Honeycomb, Grafana Tempo. It is governed by the CNCF (Cloud Native Computing Foundation) and is the current industry standard for observability instrumentation.

**Orchestration** (Container Orchestration)

The automated management of containerized applications across a cluster of machines. An orchestrator:

- schedules containers onto nodes;
- restarts unhealthy containers;
- scales the number of replicas up and down with load;
- manages network routing between services;
- rolls out new versions.

Kubernetes is the dominant orchestration platform. AWS ECS and HashiCorp Nomad are alternatives.

---

## P

**PCI DSS** — Payment Card Industry Data Security Standard

A security standard for organizations that handle credit card data. It matters to logging: card numbers, the card verification value (CVV) and full cardholder names must never appear in logs or be stored unencrypted.

Violations can bring fines and the loss of the right to process card payments. If your application takes payments, PCI DSS shapes what you may log, how you store data, and how you manage secrets.

**PII** — Personally Identifiable Information

Any data that can identify a specific individual — a name, an email address, a phone number, a home address, a national identity number. In some jurisdictions an IP address counts too.

Laws that govern it in logs, databases and analytics pipelines:

- GDPR — the data protection regulation of the European Union.
- HIPAA — the health privacy law of the United States.
- CCPA — the consumer privacy act of California.

In logging, store pseudonymous user identifiers instead of raw email addresses or names.

**PID 1** — Process ID 1

In Linux every process has a PID (process identifier). PID 1 is the init process: the first process the kernel starts. It is responsible for starting every other process, and for reaping zombies — child processes that have exited but have not been cleaned up.

In a Docker container, PID 1 is the main process. Write `CMD` in shell form (`CMD node server.js`) and `sh` becomes PID 1, with Node.js as its child. That `sh` does not forward `SIGTERM` to its children and does not reap zombies.

Always use exec form (`CMD ["node", "server.js"]`), so that your own application is PID 1.

See: *Exec Form*, *SIGTERM*, [Docker Essentials](./04-docker-essentials.md).

**Pipeline**

A sequence of automated steps, called jobs, that run in a defined order when an event triggers them. The trigger can be a code push, a pull request, a schedule, or a manual click.

The pipeline is defined as code — usually YAML — and committed to the repository alongside the application. It is also called a CI/CD pipeline, a build pipeline, or a workflow in GitHub Actions.

See: *Pipeline as Code*, [CI/CD Fundamentals](./01-cicd-fundamentals.md).

**Pipeline as Code**

The practice of defining CI/CD pipelines in configuration files (YAML) kept in the source repository and versioned alongside the application code.

What it gets you:

- Pipeline changes go through the same pull-request review as code changes.
- Pipeline history is visible in `git log`.
- The pipeline is reproducible across environments.

Every modern CI/CD platform works this way: GitHub Actions, GitLab CI, Jenkins Pipelines.

**Prometheus**

An open-source monitoring system and time-series database, created at SoundCloud and now part of the CNCF. Prometheus scrapes metrics: it pulls them from HTTP endpoints such as `/metrics` that instrumented applications expose, at a configurable interval — every 15 seconds, say.

Metrics are stored as time series and queried with PromQL (Prometheus Query Language). They are usually displayed in Grafana dashboards, and Alertmanager is the usual companion for alerting.

**Provisioning**

The process of setting up and configuring infrastructure resources until they are ready to use:

- creating virtual machines;
- configuring networking;
- installing operating systems and software;
- allocating storage.

Provisioning usually happens once, or on a schedule when resources are replaced. Infrastructure as Code tools such as Terraform and CloudFormation automate it. Contrast with *Configuration Management*: ongoing maintenance of already-provisioned systems, Ansible's domain.

---

## R

**Readiness Probe**

A Kubernetes health check that determines whether a container is ready to accept traffic. If the readiness probe fails, Kubernetes removes the pod from the load balancer's routing pool but does not restart the container. The readiness probe should check that all required external dependencies (database, cache, downstream services) are reachable. Contrast with *Liveness Probe* (which determines whether to restart).

See: [Monitoring and Observability](./07-monitoring-and-observability.md).

**Rolling Deployment** (Rolling Update)

A deployment strategy that replaces old instances with new ones a few at a time, while the service keeps running. Each new instance passes a health check before the matching old one is drained of traffic and stopped.

During the rollout both versions run at once, so database migrations have to stay backward-compatible. Built into Kubernetes, ECS, and most platform-as-a-service (PaaS) hosts.

See: [Deployment Strategies](./05-deployment-strategies.md).

**Runner** (also: Agent)

The machine — virtual or physical — where CI/CD pipeline jobs actually execute. When a pipeline is triggered, the CI scheduler assigns jobs to available runners. **Hosted runners** are provided by the CI platform (GitHub-hosted, GitLab.com shared). **Self-hosted runners** are machines you own and manage, registered with the CI platform.

See: [CI/CD Fundamentals](./01-cicd-fundamentals.md), [GitHub Actions](./02-github-actions.md), [GitLab CI](./03-gitlab-ci.md).

---

## S

**Secrets Manager**

A dedicated service for storing, reading, auditing and rotating sensitive credentials: passwords, API keys, TLS (Transport Layer Security) certificates, encryption keys.

It gives you encryption at rest, an audit log of who read what and when, fine-grained access control, automatic rotation, and versioning. Examples: AWS Secrets Manager, HashiCorp Vault, Google Cloud Secret Manager, Azure Key Vault, Doppler, Infisical. Not the same thing as a password manager, which is for humans.

See: [Environments and Configuration](./06-environments-and-config.md).

**Self-Hosted Runner**

A runner machine you own and manage yourself, with the runner software installed on it and registered with your CI/CD platform.

It reaches private networks, carries specific hardware such as a GPU (graphics processing unit), and costs less at high pipeline volumes.

The security concern: on a public repository, a malicious pull request can edit the workflow YAML and run arbitrary code on your machine.

See: [GitHub Actions](./02-github-actions.md), [GitLab CI](./03-gitlab-ci.md).

**Service Mesh**

A dedicated infrastructure layer that handles service-to-service communication in a microservices architecture. It takes over:

- load balancing and traffic routing;
- mTLS — mutual TLS encryption between services;
- retries and circuit breaking;
- observability.

It is implemented as sidecar proxies injected into each pod. Examples: Istio, Linkerd. For canary releases this matters: a service mesh can split traffic by fine-grained percentages without touching application code.

See: *Sidecar*.

**Sidecar**

A helper container that runs next to the main application container in the same pod, sharing its network and often its storage. The application does not know it is there.

Typical jobs: a service mesh proxy, a log shipper, a metrics exporter. The pattern keeps infrastructure out of application code.

See: *Service Mesh*.

**SIGTERM** — Signal Terminate

A Unix and Linux signal, number 15, sent by the operating system or the orchestrator to ask a process to shut down gracefully.

SIGKILL (signal 9) kills the process immediately. SIGTERM can be caught, which gives the process time to clean up: finish in-flight requests, close database connections, then exit. Kubernetes sends SIGTERM before stopping a pod, and SIGKILL after the grace period, 30 seconds by default.

See: *Graceful Shutdown*, *PID 1*.

**SLA** — Service Level Agreement

A contractual commitment between a service provider and its customers. It states the expected level of service: uptime, response time, error rate. It also states the price of missing it — service credits, refunds, the right to terminate.

An SLA is external and legally binding. It is always looser than the internal SLO, which leaves a safety buffer. Example: the AWS S3 SLA promises 99.9% monthly uptime, with service credits when that is breached.

See: *SLO*, *SLI*, [Monitoring and Observability](./07-monitoring-and-observability.md).

**SLI** — Service Level Indicator

A specific, quantifiable metric that represents how well the service is performing for users — the raw measurement. Examples: percentage of requests completing in < 200ms; percentage of requests returning a non-5xx status; percentage of jobs completing within their deadline. SLIs are the inputs to SLOs.

See: *SLO*, *SLA*.

**SLO** — Service Level Objective

An internal target for an SLI: the threshold below which the team treats the service as failing its users. It is not a customer-facing commitment — that is the SLA — but an internal engineering goal, and the gap between the two is the safety margin.

An SLO plus an error budget makes reliability tradeable. Budget to spare means teams can deploy more aggressively. Budget nearly gone means risky changes are frozen.

See: *SLA*, *SLI*, *Error Budget*.

**Span**

One unit of work inside a distributed trace: a single operation in a single service. A span records its name, its start and end time, its parent span, and any errors.

A trace is a tree of spans. When a request took too long, the slow span is what you look for.

See: *Trace*, *OpenTelemetry*.

**SRE** — Site Reliability Engineering

A discipline and a job role pioneered by Google, applying software engineering principles to infrastructure and operations problems.

Site reliability engineers define and maintain SLOs, manage error budgets, build automation to replace manual operations work, and respond to incidents. The four golden signals — Latency, Traffic, Errors, Saturation — come from Google's SRE book. The goal is systems that stay reliable without slowing software delivery down.

**Stage** (CI/CD)

A named group of jobs in a pipeline. They all run in parallel, and every one of them must pass before the next stage starts. The `stages:` key in GitLab CI defines both the stage names and their execution order. GitHub Actions does not have a first-class "stage" concept — ordering is achieved via the `needs:` key between jobs.

See: *Job*, [CI/CD Fundamentals](./01-cicd-fundamentals.md), [GitLab CI](./03-gitlab-ci.md).

**State File** (Terraform)

A JSON file that Terraform uses to track the current state of all the infrastructure it manages.

When you run `terraform apply`, Terraform compares the desired state in your `.tf` files with the current state in this file. From that difference it works out the smallest set of changes to make.

In a team the state file must live remotely, so that two people cannot modify it at once. An S3 bucket with DynamoDB for locking is the usual answer. The file may hold sensitive values, so it must never be committed to git.

**Step** (GitHub Actions)

An individual command or action within a job. A step either runs a shell command (`run: npm test`) or calls a pre-built action (`uses: actions/checkout@v4`). Steps within a job run sequentially. Compare with *Job* (multiple steps, one machine) and *Stage* (multiple jobs).

See: [GitHub Actions](./02-github-actions.md).

---

## T

**Terraform**

The most widely used Infrastructure as Code tool, created by HashiCorp. Written in HCL (HashiCorp Configuration Language). Provider-agnostic: it has providers for AWS, Google Cloud, Azure, Cloudflare, Vercel, GitHub, Kubernetes and hundreds of others. Workflow: `terraform init` → `terraform plan` (preview changes) → `terraform apply` (make changes) → `terraform destroy` (tear down). State is tracked in a state file.

See: *IaC*, *HCL*, *State File*.

**Trace** (Distributed Trace)

A record of the full journey of a single request through every service and component of a distributed system. A trace is made of **spans**, one per service or component. Each span records the name of the operation, its start and end time, and any errors.

A trace ID travels with every service-to-service call, in the `traceparent` HTTP header. That header comes from the Trace Context standard of the World Wide Web Consortium (W3C). Traces answer one question: where did this particular request spend its time, and where did it fail? See: *Span*, *OpenTelemetry*, [Monitoring and Observability](./07-monitoring-and-observability.md).

**TTL** — Time To Live

In DNS, the number of seconds a record stays cached by resolvers and clients before it is fetched again from the authoritative server.

This matters in blue-green deployments. Switch traffic by updating a DNS record whose TTL is 3600, one hour. Some users then keep reaching the old environment for up to an hour. Drop the TTL to 60 seconds before a planned switch. Load balancer-based switching does not have the problem at all.

---

## U

**Uptime Monitoring**

The practice of sending requests to your service from outside, on a schedule, and alerting when it does not answer correctly. It simulates what a real user experiences.

Different from internal monitoring, which uses metrics the application emits about itself. A service can look healthy from the inside while being unreachable from the outside, because of a network, DNS or firewall problem. Tools: UptimeRobot, Pingdom, Checkly.

See: [Monitoring and Observability](./07-monitoring-and-observability.md).

---

## V

**Vault** (HashiCorp Vault)

An open-source secrets management tool by HashiCorp. It offers centralized secret storage with encryption at rest, fine-grained access policies, an audit log and secret rotation. It can also issue dynamic secrets: credentials generated on demand and revoked automatically.

You can self-host it, or use HashiCorp Cloud Platform (HCP) Vault, the managed version. It is harder to operate than a managed cloud service such as AWS Secrets Manager, but more flexible and not tied to one cloud provider.

See: *Secrets Manager*.

**VPC** — Virtual Private Cloud

A logically isolated section of a cloud provider's network that you define and control.

Your EC2 instances, RDS databases, Lambda functions and other resources live inside your VPC. They are not reachable from the public internet unless you configure routing for that explicitly.

This matters to CI/CD: a self-hosted runner inside the VPC can reach private databases and internal services, while a GitHub-hosted runner outside it cannot.

---

## W

**Workflow** (GitHub Actions)

A YAML file in `.github/workflows/` that defines one piece of CI/CD automation. It names the triggers that start it, the jobs and steps it runs, and the runner type.

A repository can hold several workflow files for different purposes: CI, deploy, release, scheduled tasks.

See: [GitHub Actions](./02-github-actions.md), *Pipeline as Code*.

---

## Y

**YAML** — YAML Ain't Markup Language

A human-readable data serialization format, used widely for configuration files. The name is a recursive acronym: the definition refers to itself. YAML is the standard format for CI/CD pipeline definitions — GitHub Actions workflows, `.gitlab-ci.yml`, Kubernetes manifests, Docker Compose files.

Its key syntax rules:

- indentation is significant, and it must be spaces, never tabs;
- `:` separates a key from its value;
- `-` marks a list item;
- `#` starts a comment.

That sensitivity to whitespace is a common source of hard-to-debug errors. Run a YAML linter such as `yamllint` in your pipeline.

---

## Zero-Downtime Deployment

The requirement that a deployment keeps the service continuously available — not a single second of outage. Three habits get you there, and they work together:

- **Rolling updates** — instances are replaced one at a time, each new one only after its health check passes.
- **Blue-green switching** — traffic is cut over instantly, once the new environment has been validated.
- **Graceful shutdown** — the application finishes in-flight requests before it exits.

Zero downtime at the infrastructure level is necessary but not sufficient. The application must also handle `SIGTERM` properly for the guarantee to hold.

See: [Deployment Strategies](./05-deployment-strategies.md), *Graceful Shutdown*.
