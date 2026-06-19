# Environments and Configuration

## What "environment" means in DevOps

In DevOps, an **environment** is a self-contained deployment of your application with its own infrastructure, configuration, and data. Different environments serve different purposes in the development lifecycle.

The canonical set of environments for a web application:

```txt
Developer's laptop         → local environment
                             purpose: write and manually test code
                             data: sample/fake data, local database
                             who uses it: the developer

CI pipeline                → test environment (ephemeral)
                             purpose: automated testing (unit, integration)
                             data: test fixtures, in-memory or throwaway database
                             who uses it: CI runner (automated)

Shared server              → development / dev environment
                             purpose: integration between multiple services,
                             testing features before they go to staging
                             data: synthetic/anonymized data
                             who uses it: developers, sometimes QA

QA / pre-production server → staging environment (also called "pre-prod")
                             purpose: final validation before production
                             as close to production as possible
                             data: copy of production data (anonymized) or
                             realistic synthetic data
                             who uses it: QA, product managers, client demos

Live server(s)             → production environment ("prod")
                             purpose: serves real end users
                             data: real user data
                             who uses it: end users
```

Not all teams use all environments. Many startups operate with just three: local → staging → production. Larger organizations may add dedicated QA, UAT (User Acceptance Testing — a stage where the client or product owner validates the feature before go-live), performance testing, and disaster recovery environments.

### Why "staging must mirror production"

Staging exists to catch bugs that only appear in production conditions: production-scale data, production infrastructure size, real third-party API responses, production TLS certificates, production CDN configuration. If staging differs significantly from production, it fails its primary purpose.

Common staging-production discrepancies that cause "works on staging, broken in prod" bugs:

```txt
- Different environment variables (staging uses mock payment provider, prod uses real one)
- Different server specs (staging has 1 CPU / 1 GB RAM, prod has 4 CPU / 16 GB RAM)
- Different database version (staging: Postgres 14, prod: Postgres 15)
- Different CDN/caching behavior (staging has no CDN, prod uses CloudFront)
- Single instance on staging vs multiple instances on prod
  (reveals race conditions, session affinity issues)
```

## Environment variables

An **environment variable** is a key-value pair available to a process at runtime, set by the operating system or the process launcher — not hardcoded in the application source code.

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

```txt
1. Security: credentials (DB passwords, API keys) should not be in version control.
   Anyone with read access to the repo would see them. Historical commits are permanent.

2. Flexibility: the same Docker image runs in staging with staging credentials,
   and in production with production credentials — the image itself is unchanged.
   "Build once, run anywhere."

3. 12-factor app principle: one of the foundational principles (from 12factor.net)
   of building portable, cloud-native applications is "store config in the environment."
   Config = anything that varies between deploys (dev/staging/prod).
```

### `NODE_ENV` — a special convention

`NODE_ENV` is a de-facto standard in the Node.js ecosystem. Its value changes how many libraries behave:

```txt
NODE_ENV=development  → React includes full error messages and dev warnings
                        Express shows stack traces in error responses
                        Webpack/Vite do not minify, include source maps
                        Many libraries skip optimizations for easier debugging

NODE_ENV=production   → React strips dev warnings, minifies component names
                        Express hides stack traces (security)
                        Webpack/Vite minify, tree-shake, optimize bundle
                        Many libraries enable caching and performance paths
```

```ts
// Common pattern: different behavior per environment
if (process.env.NODE_ENV !== 'production') {
  app.use(morgan('dev'));          // verbose HTTP logging in dev
  app.use(errorHandler());        // detailed error responses in dev
}
```

**Never set `NODE_ENV=development` on staging.** Staging should run with `NODE_ENV=production` to catch production-mode bugs (minification issues, missing error boundaries, etc.).

## The `.env` file convention

A `.env` file (pronounced "dot env") is a plain text file in the root of a project that stores environment variables in `KEY=VALUE` format, one per line:

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

**`.env` is for local development only. It must NEVER be committed to version control.**

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

```txt
.env              → defaults (lowest priority, usually safe defaults)
.env.local        → local overrides (highest priority, not committed)
.env.development  → dev-specific values
.env.test         → test-specific values (loaded when NODE_ENV=test)
.env.production   → production-specific values (often just a reference — real values come from CI secrets)
```

This convention is built into frameworks like Next.js, Vite, and Create React App. The load order and priority rules are framework-specific — know the rules for the framework you are using.

## Secrets vs environment variables vs config files

These three mechanisms are often confused. They are different both in what they store and in how they are managed:

```txt
                 Environment    Config       Secrets
                 Variables      Files        Manager
─────────────────────────────────────────────────────────────────
What it stores   Runtime        Static app   Sensitive credentials
                 config         config       (passwords, API keys,
                 (non-sensitive)(feature     TLS certificates,
                                flags,       encryption keys)
                                timeouts...)

Where it lives   Process env,   File in      External service
                 CI secrets,    repo or      (AWS Secrets Manager,
                 platform vars  deployment   HashiCorp Vault,
                                             GCP Secret Manager)

Who sets it      Ops / CI       Developer    Ops / security team
                 pipeline

Versioned?       No (in CI      Yes          No (secrets rotated
                 secrets store) (in repo)    separately from code)

Rotatable?       Manually       Requires     Yes (automatic
without deploy?  (update CI     a deploy     rotation supported
                 variable)                   by most managers)
```

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
- Need fine-grained access control (only this Lambda function can read this secret)

## Secrets management

### Why you never commit secrets to a repository

```txt
Reason 1 — Git history is permanent
  Even if you delete a secret from a file and commit the deletion,
  the secret is still visible in git log / git blame on the old commit.
  Anyone with repo access (current or historical) can find it.
  Tools like truffleHog, gitleaks scan git history for leaked credentials.

Reason 2 — Repository access ≠ production access
  Developers, contractors, GitHub Actions bots, and Dependabot all
  have read access to the repo. They should NOT automatically have
  access to production database passwords or payment API keys.

Reason 3 — Secrets in public repos = immediate compromise
  Bots scan GitHub for leaked AWS keys, Stripe secrets, etc.
  within seconds of a commit being pushed. AWS themselves run
  automated scanners and notify you — but by then it may be too late.
```

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
- **Access control**: fine-grained permissions (only this EC2 instance can read this secret)
- **Automatic rotation**: rotate the secret on a schedule without any code change or redeploy
- **Versioning**: keep previous versions of a secret for rollback

Common secrets managers:

```txt
AWS Secrets Manager    → managed by AWS; integrates with Lambda, ECS, RDS
                         automatic rotation for RDS passwords built in
                         cost: ~$0.40/secret/month

HashiCorp Vault        → open-source, self-hosted or cloud-managed (HCP Vault)
                         supports many secret backends (database, PKI, SSH, cloud)
                         more complex to operate than managed services

GCP Secret Manager     → Google Cloud's equivalent
Azure Key Vault        → Microsoft Azure's equivalent

Doppler / Infisical    → developer-friendly SaaS secrets managers;
                         integrate with CI/CD pipelines and local dev
```

How secrets reach a running application:

```txt
Option A: Injected as environment variables at deploy time
  CI pipeline fetches secret from AWS Secrets Manager
  → injects it as an env var into the container/function
  → app reads process.env.DATABASE_URL
  Downside: secret visible as an env var (readable from /proc on Linux)

Option B: Application fetches at startup
  App calls AWS Secrets Manager SDK at startup
  → retrieves secret directly
  → stores in memory (never in an env var)
  Better for: highly sensitive secrets, rotation without restart

Option C: Sidecar / agent injection
  A sidecar container (e.g., Vault Agent) runs alongside the app container,
  fetches secrets, and writes them to a shared in-memory volume
  App reads from files in /vault/secrets/
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

**Infrastructure as Code** (IaC — pronounced "eye-ack") is the practice of defining and managing infrastructure — servers, networks, databases, load balancers, DNS records — in code files (typically YAML, JSON, or a domain-specific language) rather than by clicking through a web console or running manual shell commands.

```txt
Without IaC (manual, "ClickOps"):
  Engineer goes to AWS console
  → clicks "Create EC2 instance"
  → selects instance type, AMI, security group
  → configures load balancer manually
  → updates DNS manually
  Problem: not reproducible, not auditable, configuration drift
           between environments, impossible to review in a PR

With IaC:
  Engineer writes a configuration file
  → file is committed to version control
  → changes are reviewed in PRs
  → CI pipeline applies the changes automatically
  → staging and production are defined identically in code
  Benefit: reproducible, auditable, environment parity, disaster recovery
```

### Configuration drift

Without IaC, **configuration drift** is inevitable: environments that started identical gradually diverge because someone made a manual change in production ("just this once"), forgot to apply it to staging, and now the two environments are silently different. This is a major source of "works on staging, broken in prod."

IaC solves this by making the code the single source of truth — if it's not in the code, it doesn't exist.

### IaC tools — a brief map

```txt
HashiCorp Terraform  → most widely used; provider-agnostic (AWS, GCP, Azure,
                        Cloudflare, Vercel...); HCL (HashiCorp Configuration
                        Language) syntax; state file tracks what's deployed

AWS CDK              → AWS Cloud Development Kit; define AWS infrastructure
(Cloud Development     in TypeScript/Python/Java; compiles to CloudFormation;
Kit)                   feels like writing application code

AWS CloudFormation   → AWS-native IaC; JSON/YAML templates; mature and deeply
                        integrated with AWS; verbose but reliable

Pulumi               → like CDK but provider-agnostic; write infrastructure
                        in TypeScript/Python/Go/etc.

Ansible              → configuration management (installing packages, managing
                        files, running commands on servers); different focus
                        from Terraform — Terraform provisions infrastructure,
                        Ansible configures what runs on it
```

### What a fullstack developer actually needs to know about IaC

You are unlikely to write Terraform or CDK from scratch as a fullstack engineer — that is typically a DevOps/platform engineer's job. But you should understand:

```txt
1. Why IaC exists — the alternative (manual console clicks) is not scalable,
   not reproducible, and not auditable

2. The "plan before apply" workflow:
   terraform plan   → shows what will change (like a "diff" for infrastructure)
   terraform apply  → actually makes the changes
   This is analogous to a git diff before a merge

3. State files — Terraform keeps a state file that records what is currently deployed.
   This file must be stored remotely (S3 bucket with locking) in team environments —
   not committed to git (it may contain sensitive outputs)

4. Modules — reusable infrastructure components, analogous to functions or npm packages

5. Environment separation — staging and production are typically separate Terraform
   workspaces or separate state files, even if they share the same module code
```

Basic Terraform example (creating an S3 bucket — AWS's Simple Storage Service, for object storage):

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
  → injected as container env vars (ECS task definition) or K8s secrets
  → app reads DATABASE_URL, REDIS_URL from process.env

Production deployment:
  Same mechanism, different secret values
  → app running on prod reads prod database URL, real payment keys

Infrastructure (servers, databases, networking):
  Terraform / CDK → defines what exists in AWS/GCP/Azure
  → reviewed in PRs, applied by CI on merge to main
```

## Common interview traps

- **"We store config in a config.json file in the repo"** — if that file contains anything that differs between environments (especially credentials), this is a red flag. Non-sensitive config that is identical across all environments can live in the repo; anything that varies or is sensitive must be an environment variable or a secret.

- **"We put secrets in `.env` and they're fine because we added `.env` to `.gitignore`"** — `.gitignore` only prevents future commits. If `.env` was ever committed before being added to `.gitignore`, the secret is already in the git history. And `.gitignore` does not protect against someone accidentally committing a file with a different name that contains the same secrets.

- **Confusing "secrets manager" with "password manager"** — a password manager (1Password, Bitwarden) is for humans to store personal credentials. A secrets manager (AWS Secrets Manager, Vault) is a programmatic service for applications and CI systems to store and retrieve credentials at runtime, with API access, audit logs, and automatic rotation.

- **Setting `NODE_ENV=development` on staging** — staging should run exactly as production does. `NODE_ENV=development` activates development-mode behavior in many libraries (verbose errors, unminified code, disabled caches) that can mask production bugs.

- **Not knowing what IaC is** — in a senior fullstack interview, saying "the DevOps team sets up the servers" is a weak answer. You should know what IaC is, why it exists, and be able to name at least one tool (Terraform, CDK, CloudFormation).

- **"We use environment variables for everything including secrets"** — plain environment variables are readable from the process environment on the host (`/proc/<pid>/environ` on Linux). For highly sensitive secrets in production, the better approach is application-level fetching from a secrets manager, or at minimum, injecting via a mechanism that does not expose the value in the environment listing.

- **Not knowing the `.env.example` pattern** — a strong signal that a developer has worked on mature projects is knowing that `.env` is not committed but `.env.example` is. Interviewers look for this.
