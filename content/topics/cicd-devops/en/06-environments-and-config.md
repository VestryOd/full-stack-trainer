# Environments and Configuration

## What "environment" means in DevOps

DevOps is development and operations working as one team. In it, an **environment** is a self-contained deployment of your application, with its own infrastructure, configuration and data. Different environments serve different purposes in the development lifecycle.

The canonical set of environments for a web application:

- **Local** — the developer's laptop. Purpose: write and manually test code. Data: sample or fake data, local database. Used by: the developer.
- **Test** — the CI pipeline (continuous integration), fresh for every run. Purpose: automated unit and integration tests. Data: fixtures, an in-memory or throwaway database. Used by: the CI runner.
- **Development, or "dev"** — a shared server. Purpose: integration between services, and testing features before staging. Data: synthetic or anonymized. Used by: developers, sometimes QA (quality assurance).
- **Staging, also "pre-prod"** — a QA or pre-production server. Purpose: final validation, as close to production as possible. Data: an anonymized copy of production data, or realistic synthetic data. Used by: QA, product managers, client demos.
- **Production, or "prod"** — the live servers. Purpose: serve real end users. Data: real user data. Used by: end users.

Not all teams use all environments. Many startups operate with just three: local → staging → production. Larger organizations add more: a dedicated QA environment, UAT, performance testing and disaster recovery. UAT stands for user acceptance testing: the client or product owner validates a feature before go-live.

### Why "staging must mirror production"

Staging exists to catch bugs that appear only under production conditions. That means production-scale data, production-size infrastructure, real third-party API responses, production TLS (Transport Layer Security) certificates and the production CDN (content delivery network) configuration. If staging differs significantly from production, it fails its primary purpose.

Common staging-production discrepancies that cause "works on staging, broken in prod" bugs:

- Different environment variables — staging uses a mock payment provider, production the real one.
- Different server specs — staging has `1 CPU / 1 GB RAM`, production has `4 CPU / 16 GB RAM`.
- Different database version — staging on Postgres 14, production on Postgres 15.
- Different CDN and caching behaviour — staging has no CDN, production uses CloudFront.
- A single instance on staging against several on production, which is what reveals race conditions and session-affinity bugs.

## Environment variables

An **environment variable** is a key-value pair that a process can read at runtime. It is set by the operating system or by whatever starts the process, not hardcoded in source code.

```bash
# Setting an environment variable in a shell
export DATABASE_URL="postgres://user:password@localhost:5432/myapp"
export NODE_ENV="production"
export PORT="3000"

# The running application reads them
node dist/server.js
```

In Node.js:

```ts
const dbUrl = process.env.DATABASE_URL;
const port = parseInt(process.env.PORT ?? '3000', 10);
const isProd = process.env.NODE_ENV === 'production';
```

Why environment variables — not hardcoded values or config files committed to the repo:

1. **Security.** Credentials — database passwords, API keys — should not be in version control. Anyone with read access to the repo would see them; historical commits are permanent.
2. **Flexibility.** The same Docker image runs in staging with staging credentials and in production with production credentials. The image itself does not change: build once, run anywhere.
3. **The 12-factor app principle.** One of its foundational principles (12factor.net) is to store config in the environment. Config here is anything that varies between deploys: dev, staging, prod.

### `NODE_ENV` — a special convention

`NODE_ENV` is a de-facto standard in the Node.js ecosystem. Its value changes how many libraries behave:

| | `NODE_ENV=development` | `NODE_ENV=production` |
|---|---|---|
| React | Full error messages and dev warnings | Dev warnings stripped, component names minified |
| Express | Stack traces in error responses | Stack traces hidden, for security |
| Webpack / Vite | No minification, source maps included | Minified, tree-shaken, optimized bundle |
| Many libraries | Optimizations skipped, so debugging is easier | Caching and performance paths enabled |

```ts
// Common pattern: different behavior per environment
if (process.env.NODE_ENV !== 'production') {
  app.use(morgan('dev'));          // verbose HTTP logging in dev
  app.use(errorHandler());        // detailed error responses in dev
}
```

**Never set `NODE_ENV=development` on staging.** Staging should run with `NODE_ENV=production` to catch production-mode bugs (minification issues, missing error boundaries, etc.).

## The `.env` file convention

A `.env` file is a plain text file in the root of a project. It stores environment variables in `KEY=VALUE` format, one per line:

```bash
# .env  (example)
DATABASE_URL=postgres://postgres:password@localhost:5432/myapp_dev
REDIS_URL=redis://localhost:6379
JWT_SECRET=local-dev-secret-not-for-production
PORT=3000
NODE_ENV=development
STRIPE_SECRET_KEY=sk_test_...
```

Libraries like **dotenv** (Node.js) read this file at application startup and load the variables into `process.env`:

```ts
// At the very top of the entry point (before any other imports that use process.env)
import 'dotenv/config';
// or
import dotenv from 'dotenv';
dotenv.config();
```

**`.env` is for local development only. It must never be committed to version control.**

The correct `.gitignore` setup:

```gitignore
# .gitignore
.env
.env.local
.env.*.local
```

What you DO commit to the repo instead — a `.env.example` (also called `.env.template`) file with the variable names but no real values:

```bash
# .env.example  — committed to the repo, safe to share
DATABASE_URL=postgres://user:password@localhost:5432/dbname
REDIS_URL=redis://localhost:6379
JWT_SECRET=change-this-to-a-random-secret
PORT=3000
NODE_ENV=development
STRIPE_SECRET_KEY=sk_test_your_key_here
```

This file tells every developer which variables are needed, without exposing real credentials. New team members copy it (`cp .env.example .env`) and fill in the real local values.

### Multiple `.env` files

Some projects use multiple `.env` files for different environments:

| File | Role |
|---|---|
| `.env` | Defaults. Lowest priority, usually safe values. |
| `.env.local` | Local overrides. Highest priority, not committed. |
| `.env.development` | Values for the dev environment. |
| `.env.test` | Values for tests, loaded when `NODE_ENV=test`. |
| `.env.production` | Values for production — often just a placeholder; the real ones come from CI secrets. |

This convention is built into frameworks like Next.js, Vite, and Create React App. The load order and priority rules are framework-specific — know the rules for the framework you are using.

## Secrets vs environment variables vs config files

These three mechanisms are often confused. They are different both in what they store and in how they are managed:

| | Environment variables | Config files | Secrets manager |
|---|---|---|---|
| Stores | Runtime config, non-sensitive | Static app config: feature flags, timeouts | Passwords, API keys, TLS certificates, encryption keys |
| Where | Process env, CI secrets, platform vars | A file in the repo or deployment | An external service: AWS (Amazon Web Services) Secrets Manager, Vault |
| Set by | Ops or the CI pipeline | The developer | Ops or the security team |
| Versioned | No — kept in the CI secrets store | Yes, in the repo | No — rotated separately from code |
| Rotated without a deploy | By hand, editing the CI variable | No, it needs a deploy | Yes, automatically in most managers |

### When to use each

**Environment variables** for values that:
- Change between environments (dev URL ≠ prod URL)
- Are non-sensitive (port numbers, feature flags, log levels)
- Or are sensitive but will be injected by the platform at runtime (database URL from CI, not hardcoded)

**Config files** for values that:
- Are the same across all environments (request timeout defaults, pagination limits, algorithm constants)
- Are safe to be in the codebase
- Benefit from being versioned and reviewed as code

```ts
// config/defaults.ts — committed to the repo
export const config = {
  pagination: { defaultLimit: 20, maxLimit: 100 },
  cache: { ttlSeconds: 300 },
  upload: { maxFileSizeMb: 10 },
};
```

**Secrets manager** for values that:
- Are highly sensitive (production database password, private keys, payment processor credentials)
- Need audit logging (who accessed this secret and when)
- Need rotation (automatic periodic rotation without a redeploy)
- Need fine-grained access control — only this Lambda function may read this secret

## Secrets management

### Why you never commit secrets to a repository

**Reason 1 — git history is permanent.** Delete a secret from a file, commit the deletion — it is still there. It stays in `git log` and `git blame`. Anyone with repo access, current or historical, can find it. Tools like truffleHog and gitleaks scan git history for leaked credentials.

**Reason 2 — repository access is not production access.** Developers, contractors, GitHub Actions bots and Dependabot all have read access to the repo. None of them should automatically get production database passwords or payment API keys.

**Reason 3 — a secret in a public repo is compromised immediately.** Bots scan GitHub for leaked AWS keys, Stripe secrets and the like within seconds of a push. AWS runs its own scanners and notifies you, but by then it may be too late.

What to do if you accidentally commit a secret:

```bash
# Step 1: IMMEDIATELY rotate the secret (change the password/regenerate the key)
# The git history cannot be fully purged in a shared repo without force-pushing
# to all branches and everyone re-cloning — this is impractical.
# The only safe remedy is rotation.

# Step 2: Remove from git history (optional, but does not replace rotation)
git filter-repo --path .env --invert-paths
# or: BFG Repo Cleaner (external tool)
# Note: force-push required; all collaborators must re-clone
```

### What a secrets manager is

A **secrets manager** is a dedicated service for storing, accessing, and rotating sensitive credentials. It provides:

- **Encryption at rest**: secrets are stored encrypted, not as plain text
- **Audit log**: every access is logged (which service, which user, at what time)
- **Access control**: fine-grained permissions — only this EC2 (Elastic Compute Cloud) instance reads this secret
- **Automatic rotation**: rotate the secret on a schedule without any code change or redeploy
- **Versioning**: keep previous versions of a secret for rollback

Common secrets managers:

- **AWS Secrets Manager** — managed by AWS; integrates with Lambda, ECS (Elastic Container Service) and RDS (Relational Database Service). Rotation of RDS passwords is built in. About $0.40 per secret per month.
- **HashiCorp Vault** — open-source, self-hosted, or managed as HCP Vault (HashiCorp Cloud Platform). Backends: databases, PKI (public key infrastructure), SSH (secure shell), cloud. Harder to operate than a managed service.
- **Google Secret Manager**, **Azure Key Vault** — the Google Cloud and Azure equivalents.
- **Doppler / Infisical** — developer-friendly hosted secrets managers. They plug into local development and into CI/CD pipelines: continuous integration, continuous delivery.

How secrets reach a running application:

```txt
Option A: Injected as environment variables at deploy time
  CI pipeline fetches secret from AWS Secrets Manager
  → injects it as an env var into the container/function
  → app reads process.env.DATABASE_URL
  Downside: secret sits in an env var, readable from /proc on Linux

Option B: Application fetches at startup
  App calls AWS Secrets Manager SDK at startup
  → retrieves secret directly
  → stores in memory (never in an env var)
  Better for: highly sensitive secrets, rotation without restart

Option C: Sidecar / agent injection
  A sidecar container (e.g. Vault Agent) runs next to the app,
  fetches secrets and writes them to a shared in-memory volume
  App reads them from files in /vault/secrets/
  Better for: Kubernetes environments with Vault
```

Example — fetching a secret from AWS Secrets Manager in Node.js:

```ts
import {
  SecretsManagerClient,
  GetSecretValueCommand,
} from '@aws-sdk/client-secrets-manager';

const client = new SecretsManagerClient({ region: 'us-east-1' });

async function getDbPassword(): Promise<string> {
  const response = await client.send(
    new GetSecretValueCommand({ SecretId: 'prod/myapp/db-password' }),
  );
  if (!response.SecretString) throw new Error('Secret not found');
  const { password } = JSON.parse(response.SecretString);
  return password;
}
```

## Infrastructure as Code (IaC)

**Infrastructure as Code** (IaC) means describing infrastructure in code files instead of clicking through a web console or running shell commands by hand. Infrastructure here means servers, networks, databases, load balancers, DNS (Domain Name System) records. The files are usually YAML (a text format for structured data), JSON, or a domain-specific language.

```txt
Without IaC (manual, "ClickOps"):
  Engineer goes to the AWS console
  → clicks "Create EC2 instance"
  → selects instance type, AMI (machine image), security group
  → configures the load balancer by hand
  → updates DNS by hand
  Problem: not reproducible, not auditable, configuration drifts
           between environments, and there is nothing to review

With IaC:
  Engineer writes a configuration file
  → file is committed to version control
  → changes are reviewed in pull requests
  → CI pipeline applies the changes automatically
  → staging and production are defined identically in code
  Benefit: reproducible, auditable, environment parity,
           real disaster recovery
```

### Configuration drift

Without IaC, **configuration drift** is inevitable. Environments that started out identical gradually diverge: someone makes a manual change in production ("just this once") and forgets to apply it to staging. The two environments are now silently different. This is a major source of "works on staging, broken in prod".

IaC solves this by making the code the single source of truth — if it's not in the code, it doesn't exist.

### IaC tools — a brief map

- **HashiCorp Terraform** — the most widely used, and provider-agnostic: AWS, Google Cloud, Azure, Cloudflare, Vercel. Written in HCL (HashiCorp Configuration Language). A state file tracks what is deployed.
- **AWS CDK (Cloud Development Kit)** — defines AWS infrastructure in TypeScript, Python or Java and compiles it to CloudFormation. Feels like writing application code.
- **AWS CloudFormation** — the AWS-native option: JSON and YAML templates, mature and deeply integrated with AWS. Verbose but reliable.
- **Pulumi** — like CDK, but provider-agnostic. Infrastructure is written in TypeScript, Python, Go and so on.
- **Ansible** — configuration management: installing packages, managing files, running commands on servers. A different focus from Terraform: Terraform provisions infrastructure, Ansible configures what runs on it.

### What a fullstack developer actually needs to know about IaC

You are unlikely to write Terraform or CDK from scratch as a fullstack engineer — that is typically a DevOps/platform engineer's job. But you should understand:

1. **Why IaC exists.** The alternative — manual console clicks — does not scale, is not reproducible and cannot be audited.
2. **The "plan before apply" workflow.** `terraform plan` shows what will change, like a diff for infrastructure. `terraform apply` actually makes the change. Same habit as a git diff before a merge.
3. **State files.** Terraform keeps a state file recording what is deployed. In a team it must live remotely, in an S3 (Simple Storage Service) bucket with locking. Never commit it to git: it may contain sensitive outputs.
4. **Modules.** Reusable infrastructure components, analogous to functions or npm packages.
5. **Environment separation.** Staging and production are usually separate Terraform workspaces or state files, even when they share the same module code.

Basic Terraform example — it creates an S3 bucket for object storage:

```hcl
# main.tf

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

resource "aws_s3_bucket" "app_assets" {
  bucket = "my-app-assets-${var.environment}"   # e.g. "my-app-assets-staging"

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

variable "environment" {
  type    = string
  default = "staging"
}

output "bucket_name" {
  value = aws_s3_bucket.app_assets.bucket
}
```

```bash
terraform init       # download providers
terraform plan       # preview changes
terraform apply      # create the bucket
terraform destroy    # tear it down (careful with prod!)
```

## Putting it all together: configuration flow in a real project

```txt
Local development:
  .env file (not committed) → process.env → app reads config

CI pipeline (GitHub Actions / GitLab CI):
  GitHub/GitLab secrets UI → injected as env vars to the runner
  → app tests run with test database URL, mock API keys

Staging deployment:
  CI fetches secrets from AWS Secrets Manager
  → injected as container env vars (an ECS task definition)
    or as Kubernetes secrets
  → app reads DATABASE_URL, REDIS_URL from process.env

Production deployment:
  Same mechanism, different secret values
  → app running on prod reads prod database URL, real payment keys

Infrastructure (servers, databases, networking):
  Terraform / CDK → defines what exists in AWS/GCP/Azure
  → reviewed in PRs, applied by CI on merge to main
```

## Common interview traps

- **"We store config in a config.json file in the repo"** — a red flag, if that file holds anything that differs between environments. Credentials most of all. Config that is identical everywhere and non-sensitive can live in the repo. Anything that varies, or is sensitive, belongs in an environment variable or a secret.

- **"We put secrets in `.env` and they're fine because we added `.env` to `.gitignore`"** — `.gitignore` only prevents future commits. If `.env` was ever committed before being added to `.gitignore`, the secret is already in the git history. And `.gitignore` does not protect against someone accidentally committing a file with a different name that contains the same secrets.

- **Confusing "secrets manager" with "password manager"** — a password manager (1Password, Bitwarden) is for humans storing personal credentials. A secrets manager (AWS Secrets Manager, Vault) is a programmatic service for applications and CI systems. They store and retrieve credentials at runtime over an API, with audit logs and automatic rotation.

- **Setting `NODE_ENV=development` on staging** — staging should run exactly as production does. `NODE_ENV=development` activates development-mode behavior in many libraries (verbose errors, unminified code, disabled caches) that can mask production bugs.

- **Not knowing what IaC is** — in a senior fullstack interview, saying "the DevOps team sets up the servers" is a weak answer. You should know what IaC is, why it exists, and be able to name at least one tool (Terraform, CDK, CloudFormation).

- **"We use environment variables for everything including secrets"** — plain environment variables are readable from the process environment on the host (`/proc/<pid>/environ` on Linux). For highly sensitive secrets in production, fetch them from a secrets manager inside the application. At minimum, inject them so the value stays out of the environment listing.

- **Not knowing the `.env.example` pattern** — `.env` stays out of the repo, `.env.example` goes in. Knowing that is a strong signal that a developer has worked on mature projects. Interviewers look for it.
