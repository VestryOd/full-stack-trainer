# CI/CD & DevOps Glossary

Every acronym and term a fullstack developer is likely to encounter in CI/CD and DevOps contexts — in interviews, job descriptions, and day-to-day work. Organized alphabetically. Terms defined in earlier articles in this section are given a condensed explanation here plus a cross-reference.

---

## A

**Agent**
Another word for **runner** — the machine that executes CI/CD pipeline jobs. The term "agent" is used by Jenkins, Azure Pipelines, and some other tools; "runner" is used by GitHub Actions and GitLab CI. See: *Runner*.

**ALB** — Application Load Balancer
AWS's (Amazon Web Services') managed load balancer that operates at the HTTP/HTTPS layer (Layer 7 of the OSI network model). Unlike a classic load balancer that routes based on IP/port, an ALB can route based on URL path, hostname, headers, or query parameters. Used in blue-green and canary deployments to switch traffic between environments.

**APM** — Application Performance Monitoring
A category of tools that combine distributed traces, metrics, and sometimes logs into a unified view focused on application-level performance. APM tools automatically instrument your code to trace every request, identify slow code paths, and group errors. Examples: Datadog APM, New Relic, Sentry, Elastic APM. See: *[Monitoring and Observability]*.

**Artifact**
Any file or set of files produced by a build step and stored for use by a later step or for deployment. Examples: a compiled JavaScript bundle, a Docker image, a `.zip` of Lambda function code, a test coverage report. The key principle: build the artifact once and deploy the same artifact to every environment (staging, production) — never rebuild from source for each environment. See: *[CI/CD Fundamentals]*.

**Artifact Registry** (also: **Container Registry** when specific to Docker images)
A storage service where build artifacts are uploaded, versioned, and pulled from during deployments. For Docker images: GitHub Container Registry (ghcr.io), Docker Hub, AWS ECR (Elastic Container Registry), Google Artifact Registry. The registry is not the same as version control (git) — it stores compiled/packaged output, not source code.

---

## B

**Base Image**
The starting point for a Docker image, specified in the `FROM` instruction of a Dockerfile. Every image is built on top of a base image. Common examples: `node:20-alpine` (Node.js on Alpine Linux), `python:3.12-slim`, `ubuntu:22.04`. `FROM scratch` starts from a completely empty image — for minimal single-binary applications.

**Blast Radius**
The scope of impact when something goes wrong in a deployment. A key goal of deployment strategies (canary, feature flags) is to limit the blast radius: if a new version has a bug, only a small percentage of users are affected before the issue is detected and rolled back. "Minimizing blast radius" is a standard phrase in reliability engineering.

**Blue-Green Deployment**
A deployment strategy that maintains two identical production environments ("blue" and "green"). The new version is deployed to the idle environment, tested, and then traffic is switched instantaneously via the load balancer. The old environment remains running for fast rollback. Eliminates the mixed-version period of rolling deployments but doubles infrastructure cost. See: *[Deployment Strategies]*.

**Build Context** (Docker)
The set of files sent to the Docker daemon when `docker build` is run — typically the contents of the current directory. Files listed in `.dockerignore` are excluded from the build context. A large build context (e.g., including `node_modules/`) slows down the build because all those files are transferred to the daemon before any Dockerfile instruction runs.

---

## C

**Canary Release**
Named after "canary in a coal mine." A deployment strategy that sends a small percentage of real user traffic (e.g., 5%) to the new version while the rest goes to the stable version. The new version is observed for errors and performance regressions; traffic is increased gradually if all looks well. Differs from a feature flag: canary is an infrastructure-level traffic split between two deployed versions. See: *[Deployment Strategies]*.

**CDK** — Cloud Development Kit (AWS CDK)
AWS's infrastructure-as-code tool that lets you define AWS infrastructure in TypeScript, Python, Java, or other languages — as opposed to JSON/YAML templates. CDK code compiles to CloudFormation templates. Feels like writing application code rather than configuration. See: *IaC*, *CloudFormation*.

**cgroups** — Control Groups
A Linux kernel feature that limits the amount of CPU, memory, disk I/O, and network bandwidth that a group of processes can use. Together with namespaces, cgroups are the technology that makes Docker containers possible: each container's resource usage is bounded by cgroups, preventing one container from starving others on the same host.

**CI** — Continuous Integration
The practice of merging code changes into the shared main branch frequently (multiple times per day), with each merge automatically triggering a pipeline that builds and tests the code. The goal: catch integration problems minutes after they are introduced, not days later. CI is the foundation on which CD is built. See: *[CI/CD Fundamentals]*.

**CD** — Continuous Delivery / Continuous Deployment
Two distinct concepts that share the same abbreviation. **Continuous Delivery**: every passing build is packaged into a deployable artifact and automatically deployed to staging — but production deployment requires a manual approval gate. **Continuous Deployment**: the manual gate is removed; every passing build is automatically deployed to production. The difference is one word and one human click. See: *[CI/CD Fundamentals]*.

**CloudFormation**
AWS's native infrastructure-as-code service. You define AWS resources (EC2 instances, S3 buckets, RDS databases, load balancers, etc.) in JSON or YAML templates, and CloudFormation provisions and manages them. Mature and deeply integrated with AWS but verbose; many teams prefer CDK (which compiles to CloudFormation) for a better developer experience.

**Composite Action** (GitHub Actions)
A reusable group of steps packaged into a single `uses:` call, embedded within a job. Composite actions are stored as `action.yml` files (typically in `.github/actions/`). Unlike reusable workflows (which are full jobs), a composite action runs as part of a job alongside other steps. Use when you want to abstract a sequence of setup/install/build steps. See: *[GitHub Actions]*.

**Configuration Drift**
The gradual divergence of environments (staging, production) from each other due to manual changes made to one but not the other — "just this once" modifications to production that are never reflected in staging. Configuration drift is the primary cause of "works on staging, broken in production." Infrastructure as Code (IaC) prevents drift by making the code the single source of truth for what exists. See: *IaC*.

**Container**
A running instance of a Docker image — the image plus a writable layer on top, running as an isolated process on the host OS. Containers share the host OS kernel (unlike VMs which have their own). They are started and stopped in milliseconds and are designed to be ephemeral (temporary, replaceable). See: *[Docker Essentials]*.

**Container Registry**
See: *Artifact Registry*.

**CRD** — Custom Resource Definition (Kubernetes)
An extension mechanism in Kubernetes that lets you add your own resource types to the Kubernetes API. Tools like Argo Rollouts and Cert-Manager work by installing CRDs into the cluster and then providing controllers that act on those custom resources. When you see `apiVersion: argoproj.io/v1alpha1` in a YAML file, that's a CRD-backed resource.

---

## D

**DAG** — Directed Acyclic Graph
A graph structure where edges (connections between nodes) point in one direction and there are no cycles — no path that leads back to where it started. In CI/CD, a DAG describes pipeline job dependencies: job B depends on job A (directed), and there is no circular dependency (acyclic). GitLab CI's `needs:` keyword and GitHub Actions' `needs:` key both create DAG-shaped pipelines. See: *[GitLab CI]*.

**dind** — Docker-in-Docker
A configuration where a Docker daemon runs inside a Docker container — so that Docker commands (`docker build`, `docker push`) can be executed inside a CI job that itself runs in a container. Required in GitLab CI when using the Docker executor and needing to build Docker images. Declared as a service: `services: - docker:24-dind`. Has security implications (privileged mode). See: *[GitLab CI]*.

**DNS** — Domain Name System
The internet's "phone book" — a distributed database that translates human-readable domain names (e.g., `api.myapp.com`) into IP addresses. Relevant to DevOps in the context of traffic switching: DNS-based traffic switching in blue-green deployments has a propagation delay (TTL — Time To Live) of minutes to hours, making it unsuitable for instant rollback. Load balancer-based switching is preferred.

**Dockerfile**
A text file containing a sequence of instructions that Docker executes to build an image. Each instruction (`FROM`, `RUN`, `COPY`, `CMD`, etc.) creates a layer in the image. The Dockerfile is committed to the repository and serves as the reproducible recipe for building the application's container image. See: *[Docker Essentials]*.

**Dotenv** (`.env` file)
A plain text file in the root of a project that stores environment variables in `KEY=VALUE` format, one per line. Loaded at application startup by the `dotenv` library (`import 'dotenv/config'`). Intended for local development only — never committed to version control. The `.env.example` file (with variable names but no real values) is committed instead, as a template for other developers. See: *[Environments and Config]*.

---

## E

**ECR** — Elastic Container Registry
AWS's managed Docker container registry. You push Docker images to ECR and pull them during deployments to ECS, Lambda, or other AWS services. Images are tagged (e.g., with a commit SHA) and versioned. Private by default; access is controlled via AWS IAM (Identity and Access Management) policies.

**ECS** — Elastic Container Service
AWS's managed container orchestration service. You define task definitions (what Docker image to run, how much CPU/memory, what environment variables) and services (how many copies to run, which load balancer to attach to). ECS manages starting, stopping, and health-checking the containers. An alternative to Kubernetes that is simpler to operate but less flexible.

**ELK Stack** — Elasticsearch + Logstash + Kibana
A popular open-source log management stack. **Elasticsearch**: a distributed search and analytics engine that stores and indexes log data. **Logstash**: a pipeline that ingests logs from multiple sources, transforms them, and forwards them to Elasticsearch. **Kibana**: a web UI for querying and visualizing data in Elasticsearch. Often extended with **Beats** (lightweight log shippers) and referred to as the **Elastic Stack**.

**Error Budget**
The allowable amount of unreliability (downtime, errors, latency violations) permitted before an SLO is breached — expressed as a duration or a count. Formula: `error budget = 1 − SLO target`. Example: SLO of 99.9% availability → 0.1% error budget → 43.2 minutes of allowed downtime per 30-day period. When the error budget is nearly exhausted, teams freeze risky changes; when it is ample, teams can move faster. See: *SLO*, *[Monitoring and Observability]*.

**Expand-Contract Migration** (also: Parallel-Change Pattern)
A safe database migration strategy for zero-downtime deployments. Instead of making breaking schema changes in a single deploy, changes are spread across multiple deploys: **Expand** (add new column as nullable, backward-compatible), **Migrate** (backfill data in the background), **Contract** (make column NOT NULL once all rows have data), **Cleanup** (drop old column once old code is gone). Ensures both old and new versions of the application can run simultaneously against the same database. See: *[Deployment Strategies]*.

---

## F

**Feature Flag** (also: Feature Toggle, Feature Switch)
A mechanism in application code that enables or disables a feature at runtime without deploying new code. The feature code is already deployed but gated behind a conditional check (e.g., `if (flagClient.variation('new-checkout', user, false))`). Allows: gradual rollout by user percentage, instant kill switch without redeploy, A/B testing, and deploying incomplete features to production (behind the flag). Not a deployment strategy — it is an application-level code technique. See: *[Deployment Strategies]*.

---

## G

**GDPR** — General Data Protection Regulation
A European Union regulation that governs how organizations collect, store, process, and share personal data of EU residents. Relevant to DevOps: logging PII (Personally Identifiable Information) such as email addresses, phone numbers, or IP addresses in application logs may violate GDPR. Logs should store user IDs (pseudonymous identifiers), not raw personal data.

**GitOps**
A practice where the desired state of infrastructure and application deployments is defined in Git, and automated systems continuously reconcile the actual state with the desired state in Git. Changes to infrastructure are made via pull requests (reviewed, tested, merged) rather than direct commands. Tools: Argo CD, Flux. "If it's not in Git, it doesn't exist" is the GitOps ethos.

**Graceful Shutdown**
The process by which an application cleanly handles a termination signal (`SIGTERM`) before exiting: stops accepting new connections, finishes processing in-flight requests, closes database connections, and exits with code 0. Without graceful shutdown, in-flight requests are dropped on every deployment. Essential for zero-downtime deployments. See: *[Deployment Strategies]*, *SIGTERM*.

---

## H

**HCL** — HashiCorp Configuration Language
The domain-specific language used by Terraform and other HashiCorp tools to define infrastructure. HCL is a declarative language — you describe the desired end state, and Terraform figures out how to get there. Human-readable, supports expressions, variables, loops, and modules. Alternative to writing CloudFormation YAML or CDK TypeScript.

**Health Check**
A periodic test to determine whether a service is alive and ready to accept traffic. In Kubernetes: **liveness probes** check whether the process is alive (failed probe → restart the container); **readiness probes** check whether the service is ready for traffic (failed probe → remove from load balancer, do not restart). In Docker Compose: the `healthcheck` key defines a command that determines whether a service is healthy, used by `depends_on: condition: service_healthy`. See: *[Monitoring and Observability]*.

**Hosted Runner** (also: Managed Runner)
A CI/CD runner provided and managed by the CI platform (GitHub, GitLab, etc.). You get a fresh virtual machine for each pipeline run, pre-installed with common tools. No maintenance required on your side. You pay per minute of compute time; hardware is shared with other platform users; runners have no access to your private network. Contrast: *Self-Hosted Runner*.

---

## I

**IaC** — Infrastructure as Code
The practice of defining and managing infrastructure (servers, networks, databases, load balancers) in code files committed to version control, rather than by clicking through a web console or running manual commands. Benefits: reproducibility, auditability, environment parity, disaster recovery, PR-based review of infrastructure changes. Tools: Terraform, AWS CDK, CloudFormation, Pulumi, Ansible. See: *[Environments and Config]*.

**Image** (Docker Image)
A read-only, layered snapshot of a filesystem with everything needed to run an application: the OS base, runtime (Node.js, Python, etc.), dependencies, compiled code, and configuration files. An image is built from a Dockerfile. Multiple containers can run from the same image simultaneously. The image is the deployment unit that is built once and promoted through environments. See: *Container*, *[Docker Essentials]*.

**Immutable Infrastructure**
A practice where servers and containers are never modified after deployment — instead, a new image is built and deployed, and the old one is replaced. If you need to update the application, you build a new Docker image and replace the running containers; you do not SSH into a container and patch files manually. Immutable infrastructure makes deployments reproducible and eliminates configuration drift on the running instances.

---

## J

**Job** (CI/CD)
A unit of work in a pipeline that runs on a single runner/agent machine. A job consists of a sequence of steps (commands). Jobs in the same pipeline stage run in parallel by default (in GitLab CI) or unless they have `needs:` dependencies (in GitHub Actions). A job produces artifacts and reports a pass/fail result. See: *Stage*, *Step*, *[CI/CD Fundamentals]*.

---

## K

**K8s** — Kubernetes
An open-source container orchestration platform originally developed by Google. "K8s" is a numeronym: K + 8 letters + s. Kubernetes automates the deployment, scaling, and management of containerized applications across a cluster of machines. Key concepts: pods (groups of containers), deployments (desired state declarations), services (network endpoints), ingress (external traffic routing), namespaces (resource isolation within a cluster). The de-facto standard for running containers at scale.

---

## L

**Layer** (Docker)
A single incremental change to a Docker image's filesystem, created by a Dockerfile instruction (`FROM`, `RUN`, `COPY`, `ADD`). Layers are stacked — each records only the diff relative to the layer beneath. Layers are cached: if a layer's instruction and its inputs haven't changed since the last build, Docker reuses the cached layer. Ordering instructions from least-changed to most-changed maximizes cache reuse and speeds up builds. See: *[Docker Essentials]*.

**Liveness Probe**
A Kubernetes health check that determines whether a container process is alive and should continue running. If the liveness probe fails, Kubernetes restarts the container. A liveness probe should only check whether the process itself is responsive — not whether external dependencies (database, cache) are available. If it checks external dependencies, a database outage causes all pods to restart in a loop. See: *Readiness Probe*, *[Monitoring and Observability]*.

**Loki** (Grafana Loki)
A horizontally scalable log aggregation system designed by Grafana Labs, inspired by Prometheus. Unlike Elasticsearch, Loki does not index the full content of logs — only their labels (metadata). This makes it cheaper to operate at scale. Loki is queried using LogQL (a query language similar to PromQL) and is displayed in Grafana dashboards. Pairs with Prometheus (metrics) and Tempo (traces) for a full open-source observability stack.

---

## M

**Metrics**
Numeric measurements of system properties, sampled over time and aggregated. Unlike logs (discrete events), metrics show *how much* and *how fast* — request rate, error rate, CPU usage, latency percentiles. The four golden signals (from Google's SRE book): Latency, Traffic, Errors, Saturation. Standard metric types: Counter (only goes up), Gauge (up and down), Histogram (buckets). Tool: Prometheus. See: *[Monitoring and Observability]*.

**Multi-Stage Build** (Docker)
A Dockerfile technique that uses multiple `FROM` instructions, each starting a new build stage. Files can be copied from one stage to another using `COPY --from=stage-name`. The final image contains only what was copied into the last stage — build tools, dev dependencies, and source files are left behind. Dramatically reduces production image size (e.g., from ~400 MB with all build tools to ~80 MB with only the runtime and compiled output). See: *[Docker Essentials]*.

---

## N

**Namespace** (Kubernetes)
A mechanism for isolating groups of resources within a single Kubernetes cluster. Resources (pods, services, deployments) in one namespace are isolated from those in another. Commonly used to separate environments (dev, staging, prod) within the same cluster, or to separate teams/applications. Default namespaces: `default`, `kube-system` (cluster components), `kube-public`.

**Non-Root User** (Docker)
A security practice of running container processes as a non-root user (not UID 0). By default, Docker containers run as root — if an attacker escapes the container, they have root privileges on the host. Adding `USER node` (or any non-root user) to a Dockerfile reduces this risk. The `node:*` base images include a built-in `node` user (UID 1000) for this purpose. See: *[Docker Essentials]*.

---

## O

**Observability**
The property of a system that allows understanding of its internal state by examining its external outputs (logs, metrics, traces). A system is "highly observable" if you can diagnose any failure mode — including ones you didn't anticipate — from the data the system emits. The three pillars of observability are logging, metrics, and distributed tracing. Contrast: *Monitoring* (watching predefined signals) vs observability (ability to discover unexpected failure modes). See: *[Monitoring and Observability]*.

**OpenTelemetry** (OTel)
A vendor-neutral, open-source standard and SDK for instrumenting applications to emit telemetry data: traces, metrics, and logs. OpenTelemetry replaces vendor-specific agents — you instrument your code once with the OTel SDK and export data to any compatible backend (Jaeger, Datadog, Honeycomb, Grafana Tempo). Governed by the CNCF (Cloud Native Computing Foundation). The current industry standard for observability instrumentation.

**Orchestration** (Container Orchestration)
The automated management of containerized applications across a cluster of machines: scheduling containers onto nodes, restarting unhealthy containers, scaling the number of replicas up or down in response to load, managing network routing between services, and rolling out new versions. Kubernetes is the dominant orchestration platform. AWS ECS and HashiCorp Nomad are alternatives.

---

## P

**PCI DSS** — Payment Card Industry Data Security Standard
A security standard for organizations that handle credit card data. Relevant to logging: card numbers, CVV codes, and full cardholder names must never appear in logs or be stored unencrypted. Violations can result in fines and loss of the ability to process card payments. If your application handles payments, compliance with PCI DSS affects what you can log, how you store data, and how you manage secrets.

**PII** — Personally Identifiable Information
Any data that can be used to identify a specific individual: name, email address, phone number, home address, national ID number, IP address (in some jurisdictions). PII must be handled carefully in logs, databases, and analytics pipelines under regulations like GDPR, HIPAA, and CCPA. In logging: log user IDs (pseudonymous identifiers) instead of raw email addresses or names.

**PID 1** — Process ID 1
In a Linux system, PID 1 is the init process — the first process started by the kernel, responsible for starting all other processes and for reaping zombie processes (child processes that have exited but haven't been cleaned up). In a Docker container, PID 1 is the main process. If `CMD` is specified in shell form (`CMD node server.js`), `sh` becomes PID 1 and Node.js runs as a child process — `sh` does not forward SIGTERM to its children and does not reap zombies. Always use exec form (`CMD ["node", "server.js"]`) so your application is PID 1. See: *Exec form*, *SIGTERM*, *[Docker Essentials]*.

**Pipeline**
A sequence of automated steps (jobs) that run in a defined order when triggered by an event (a code push, a PR, a schedule, a manual trigger). The pipeline is defined as code (typically YAML) and committed to the repository alongside the application. Also called a "CI/CD pipeline," "build pipeline," or "workflow" (GitHub Actions). See: *Pipeline as Code*, *[CI/CD Fundamentals]*.

**Pipeline as Code**
The practice of defining CI/CD pipelines in configuration files (YAML) stored in the source code repository, versioned alongside the application code. Benefits: pipeline changes go through the same PR review process as code changes; pipeline history is visible in git log; the pipeline is reproducible across environments. All modern CI/CD platforms (GitHub Actions, GitLab CI, Jenkins Pipelines) implement this practice.

**Prometheus**
An open-source monitoring system and time-series database created at SoundCloud and now part of the CNCF. Prometheus "scrapes" (pulls) metrics from HTTP endpoints (`/metrics`) exposed by instrumented applications at a configurable interval (e.g., every 15 seconds). Metrics are stored as time series and queried with PromQL (Prometheus Query Language). Typically displayed in Grafana dashboards. Often paired with Alertmanager for alerting.

**Provisioning**
The process of setting up and configuring infrastructure resources so they are ready to use: creating virtual machines, configuring networking, installing operating systems and software, allocating storage. Provisioning is typically done once (or on a schedule when resources are replaced). Infrastructure as Code tools (Terraform, CloudFormation) automate provisioning. Contrast with *Configuration Management* (ongoing maintenance of already-provisioned systems — Ansible's domain).

---

## R

**Readiness Probe**
A Kubernetes health check that determines whether a container is ready to accept traffic. If the readiness probe fails, Kubernetes removes the pod from the load balancer's routing pool but does not restart the container. The readiness probe should check that all required external dependencies (database, cache, downstream services) are reachable. Contrast with *Liveness Probe* (which determines whether to restart). See: *[Monitoring and Observability]*.

**Rolling Deployment** (Rolling Update)
A deployment strategy that replaces instances of the old version with the new version incrementally — a few at a time — while the service continues to run. The new instance passes a health check before the old instance is drained and stopped. During the rollout, both old and new versions run simultaneously, which requires backward-compatible database migrations. Built into Kubernetes, ECS, and most PaaS platforms. See: *[Deployment Strategies]*.

**Runner** (also: Agent)
The machine — virtual or physical — where CI/CD pipeline jobs actually execute. When a pipeline is triggered, the CI scheduler assigns jobs to available runners. **Hosted runners** are provided by the CI platform (GitHub-hosted, GitLab.com shared). **Self-hosted runners** are machines you own and manage, registered with the CI platform. See: *[CI/CD Fundamentals]*, *[GitHub Actions]*, *[GitLab CI]*.

---

## S

**Secrets Manager**
A dedicated service for storing, accessing, auditing, and rotating sensitive credentials (passwords, API keys, TLS certificates, encryption keys). Provides: encryption at rest, audit logging (who accessed what and when), fine-grained access control, automatic rotation, and versioning. Examples: AWS Secrets Manager, HashiCorp Vault, GCP Secret Manager, Azure Key Vault, Doppler, Infisical. Not the same as a *password manager* (for humans). See: *[Environments and Config]*.

**Self-Hosted Runner**
A runner machine owned and managed by you, with the runner software installed and registered with your CI/CD platform. Allows access to private networks, specific hardware (GPU, specific CPU architecture), and can be more cost-effective at high pipeline volumes. Security concern: self-hosted runners on public repositories can be exploited by malicious PRs that modify the workflow YAML to run arbitrary code on your machine. See: *[GitHub Actions]*, *[GitLab CI]*.

**Service Mesh**
A dedicated infrastructure layer that handles service-to-service communication in a microservices architecture — including load balancing, traffic routing, mTLS (mutual TLS encryption between services), retries, circuit breaking, and observability. Implemented as sidecar proxies injected into each pod. Examples: Istio, Linkerd. Relevant to canary releases: a service mesh can split traffic with fine-grained percentage control without modifying application code. See: *Sidecar*.

**SIGTERM** — Signal Terminate
A Unix/Linux signal (signal number 15) sent by the operating system or orchestrator to a process to request graceful shutdown. Unlike SIGKILL (signal 9, which immediately kills the process), SIGTERM can be caught by the process, which then has time to clean up (finish in-flight requests, close database connections) before exiting. Kubernetes sends SIGTERM before stopping a pod, then SIGKILL after the grace period (default 30 seconds). See: *Graceful Shutdown*, *PID 1*.

**SLA** — Service Level Agreement
A contractual commitment between a service provider and its customers defining the expected level of service (uptime, response time, error rate) and the financial consequences (service credits, refunds, right to terminate) if the commitment is not met. An SLA is an external, legally binding document. It is always less strict than the internal SLO to provide a safety buffer. Example: AWS S3 SLA promises 99.9% monthly uptime with service credits for breaches. See: *SLO*, *SLI*, *[Monitoring and Observability]*.

**SLI** — Service Level Indicator
A specific, quantifiable metric that represents how well the service is performing for users — the raw measurement. Examples: percentage of requests completing in < 200ms; percentage of requests returning a non-5xx status; percentage of jobs completing within their deadline. SLIs are the inputs to SLOs. See: *SLO*, *SLA*.

**SLO** — Service Level Objective
An internal target for an SLI — the threshold below which the team considers the service to be failing its users. Not a customer-facing commitment (that is the SLA); an SLO is an internal engineering goal. The gap between SLO and SLA provides a safety margin. An SLO combined with the concept of error budget makes reliability tradeable: if the error budget is ample, teams can deploy more aggressively; if it is nearly exhausted, teams freeze risky changes. See: *SLA*, *SLI*, *Error Budget*.

**SRE** — Site Reliability Engineering
A discipline and job role pioneered by Google that applies software engineering principles to infrastructure and operations problems. SREs define and maintain SLOs, manage error budgets, build automation to replace manual operations work, and respond to incidents. The concept of the "four golden signals" (Latency, Traffic, Errors, Saturation) comes from Google's SRE book. An SRE's goal is to make systems reliable while still enabling the speed of software delivery.

**Stage** (CI/CD)
A named group of jobs in a pipeline that all run in parallel (within the stage) and that must all pass before the next stage starts. The `stages:` key in GitLab CI defines both the stage names and their execution order. GitHub Actions does not have a first-class "stage" concept — ordering is achieved via the `needs:` key between jobs. See: *Job*, *[CI/CD Fundamentals]*, *[GitLab CI]*.

**State File** (Terraform)
A JSON file that Terraform uses to track the current state of all infrastructure it manages. When you run `terraform apply`, Terraform compares the desired state (in `.tf` files) with the current state (in the state file) and determines the minimal set of changes to make. In team environments, the state file must be stored remotely (e.g., in an S3 bucket with DynamoDB for locking) to prevent concurrent modifications. The state file may contain sensitive values and should never be committed to git.

**Step** (GitHub Actions)
An individual command or action within a job. A step either runs a shell command (`run: npm test`) or calls a pre-built action (`uses: actions/checkout@v4`). Steps within a job run sequentially. Compare with *Job* (multiple steps, one machine) and *Stage* (multiple jobs). See: *[GitHub Actions]*.

---

## T

**Terraform**
The most widely used Infrastructure as Code tool, created by HashiCorp. Written in HCL (HashiCorp Configuration Language). Provider-agnostic: has providers for AWS, GCP, Azure, Cloudflare, Vercel, GitHub, Kubernetes, and hundreds of others. Workflow: `terraform init` → `terraform plan` (preview changes) → `terraform apply` (make changes) → `terraform destroy` (tear down). State is tracked in a state file. See: *IaC*, *HCL*, *State File*.

**Trace** (Distributed Trace)
A record of the full journey of a single request through all the services and components of a distributed system. A trace consists of multiple **spans** (one per service/component). Each span records: the name of the operation, start and end time, any errors. A trace ID is propagated through all service-to-service calls (via the `traceparent` HTTP header per the W3C Trace Context standard). Traces answer: "Where did this specific request spend its time, and where did it fail?" See: *Span*, *OpenTelemetry*, *[Monitoring and Observability]*.

**TTL** — Time To Live
In DNS: the number of seconds that a DNS record is cached by resolvers and clients before being re-fetched from the authoritative DNS server. Relevant to blue-green deployments: if you switch traffic by updating a DNS record and the TTL is 3600 (1 hour), some users will still be routed to the old environment for up to an hour. Reduce TTL to 60 seconds before a planned traffic switch. Load balancer-based switching does not have this problem.

---

## U

**Uptime Monitoring**
The practice of periodically sending requests to your service from external locations and alerting when the service does not respond correctly. "External" monitoring — it simulates what a real user experiences. Distinct from internal monitoring (metrics emitted by the application itself). A service can appear healthy internally while being unreachable externally due to network/DNS/firewall issues. Tools: UptimeRobot, Pingdom, Checkly. See: *[Monitoring and Observability]*.

---

## V

**Vault** (HashiCorp Vault)
An open-source secrets management tool by HashiCorp. Provides centralized secret storage with encryption at rest, fine-grained access policies, audit logging, dynamic secrets (credentials generated on demand and automatically revoked), and secret rotation. Available as self-hosted or HCP Vault (cloud-managed). More complex to operate than managed cloud services (AWS Secrets Manager) but more flexible and not tied to a specific cloud provider. See: *Secrets Manager*.

**VPC** — Virtual Private Cloud
A logically isolated section of a cloud provider's network that you define and control. Your EC2 instances, RDS databases, Lambda functions, and other resources run inside your VPC and are not accessible from the public internet unless you explicitly configure routing. Relevant to CI/CD: self-hosted runners inside the VPC can reach private databases and internal services; GitHub-hosted runners (outside your VPC) cannot.

---

## W

**Workflow** (GitHub Actions)
A YAML file in `.github/workflows/` that defines a CI/CD automation: when it runs (triggers), what it does (jobs and steps), and where it runs (runner type). A repository can have multiple workflow files for different purposes (CI, deploy, release, scheduled tasks). See: *[GitHub Actions]*, *Pipeline as Code*.

---

## Y

**YAML** — YAML Ain't Markup Language
A human-readable data serialization format widely used for configuration files. The name is a recursive acronym (the definition refers to itself). YAML is the standard format for CI/CD pipeline definitions (GitHub Actions workflows, `.gitlab-ci.yml`, Kubernetes manifests, Docker Compose files). Key syntax rules: indentation is significant (use spaces, never tabs); `:` separates keys from values; `-` marks list items; `#` starts a comment. YAML's sensitivity to whitespace is a common source of hard-to-debug errors — use a YAML linter (e.g., `yamllint`) in your pipeline.

---

## Zero-Downtime Deployment

The requirement that a deployment makes the service continuously available to users — not even a second of outage. Achieved through strategies like rolling updates (replacing instances one at a time after health checks pass), blue-green switching (traffic cut over instantaneously after the new environment is validated), and graceful shutdown (application processes in-flight requests before exiting). Zero-downtime at the infrastructure level is necessary but not sufficient — the application must also handle `SIGTERM` gracefully for the guarantee to hold. See: *[Deployment Strategies]*, *Graceful Shutdown*.
