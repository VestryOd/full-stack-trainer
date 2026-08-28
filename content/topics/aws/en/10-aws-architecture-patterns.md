# AWS Architecture Patterns

## Why architecture patterns matter

Senior AWS (Amazon Web Services) questions are rarely definition questions. Instead of "what is S3 (Simple Storage Service)", you get design questions: how would you build system X, and why that way. Each pattern below is a ready-made blueprint with the reasoning behind its choices.

## Pattern 1: Static SPA / Next.js static export

A static SPA (single-page application) needs no server: S3 stores the files and CloudFront serves them from the edge. CloudFront is not an optimization here — without it there is no HTTPS (encrypted HTTP) on your own domain.

```txt
User → CloudFront (edge cache, HTTPS, custom domain)
          ↓ Cache MISS
          S3 (static assets: HTML, JS, CSS, images)
```

**Use when:** React/Vue SPA, Next.js with `output: 'export'`, docs, landing pages.

**Why CloudFront in front of S3:**

- S3 website endpoint gives no HTTPS on a custom domain.
- S3 has no edge caching: requests go to one region.
- CloudFront has 250+ Edge Locations, HTTP→HTTPS redirect, Gzip/Brotli.

**SPA routing solution:**

- CloudFront Custom Error Response maps 403/404 → `/index.html` with status 200.
- React Router then handles the path on the client.

## Pattern 2: Fullstack SPA + REST API

The same static frontend, plus one path that is not static. CloudFront sends `/api/*` to API Gateway with caching disabled, so a single domain serves both the app and its REST (representational state transfer) backend.

```txt
User → CloudFront → S3 (Next.js static build / SPA)
         ↓ /api/*  (CACHING_DISABLED behavior)
       API Gateway HTTP API → Lambda → RDS PostgreSQL (VPC)
                                ↓
                           ElastiCache Redis (session, cache)
                           S3 (files via Pre-Signed URL)
```

**CDK (Cloud Development Kit) stack:**

- S3 + CloudFront for the frontend.
- API Gateway HTTP API + Lambda for the backend.
- RDS (Relational Database Service) Aurora Serverless v2 + RDS Proxy for connection pooling.
- VPC (Virtual Private Cloud): Lambda and RDS in private subnets.

**Use when:** fullstack pet project, MVP (minimum viable product), startup API.

**Trade-off:** Lambda cold start on the API. Buy it back with Provisioned Concurrency on critical routes.

## Pattern 3: Production NestJS API — ECS Fargate + ALB

A long-running NestJS API is the case where containers beat functions. Route53 points at an ALB (Application Load Balancer), which spreads traffic across ECS (Elastic Container Service) Fargate Tasks in more than one Availability Zone.

```txt
Internet → Route53 → ALB (443/HTTPS termination, health checks)
                 ↓ Round-robin
           ECS Fargate Tasks (NestJS, 2+ copies across AZs)
                 ↓
           RDS Aurora PostgreSQL Multi-AZ (private subnet)
                 ↓
           ElastiCache Redis (session, distributed cache)
                 ↓
           S3 (uploads) + CloudFront (media CDN)
           SQS + Worker Lambda (async tasks: email, notifications)
```

**Why ECS Fargate, not Lambda:**

- NestJS has heavy initialization (dependency injection, decorators) — 2-5 sec cold start.
- WebSocket support, if needed.
- No 29-second response limit.
- Persistent memory for session and cache.

**Scaling and safety net:**

- Auto Scaling: processor load (CPU) at 70% → scale out, at 30% → scale in.
- Circuit Breaker: if new Tasks fail to start → rollback.

## Pattern 4: File Upload — Pre-Signed URL

Uploading through your own backend makes you pay for the same bytes twice. A Pre-Signed URL lets the browser PUT straight into S3, and the backend only signs the request and stores the resulting key.

```txt
Bad (proxying through backend):
  Frontend → POST /upload (10GB) → Backend → S3
  Problems: traffic through server, Lambda timeout, memory overflow

Correct (direct upload):
1. Frontend → GET /upload-url?filename=photo.jpg → Backend
2. Backend → AWS SDK: getSignedUrl(PutObjectCommand, expiresIn: 300)
3. Backend → Frontend: { url, key }
4. Frontend → S3: PUT directly (signed URL)
5. S3 trigger: PUT → SQS → Lambda (resize, validate, virus scan)
6. Frontend → Backend: POST /confirm { key }
7. Backend → DB: save key
```

Two variants of the same idea:

- For size limits: Presigned POST, with `content-length-range` in the conditions.
- For private downloads: a GET Pre-Signed URL with `expiresIn: 3600`.

## Pattern 5: Async Processing — Order Flow

`POST /orders` must respond fast, yet an order also needs payment processing, an email, analytics and an inventory update. The pattern does the minimum synchronously, publishes one SNS (Simple Notification Service) event, and lets four queues carry the rest.

```txt
POST /orders (sync, < 100ms):
  → Validate order → Save to DB → Publish SNS "OrderCreated"
  → Response 202 Accepted { orderId }

SNS "OrderCreated" fan-out → 4 SQS queues:
  SQS_Payment   → Lambda_Payment (charge card, retry 3x, DLQ)
  SQS_Email     → Lambda_Email (send confirmation, idempotent)
  SQS_Inventory → Lambda_Inventory (decrement stock)
  SQS_Analytics → Lambda_Analytics (metrics, Kinesis)

GET /orders/:id → poll for status (or WebSocket for real-time)
```

**What this buys you:**

- SQS (Simple Queue Service) gives at-least-once delivery, so handlers must be idempotent.
- A DLQ (dead-letter queue) isolates failed messages so they don't block the queue.
- Each service retries and scales independently.

## Pattern 6: Image Processing Pipeline

Image processing is the upload pattern with one extra hop: a queue between the S3 event and the worker. That hop is what buys the pipeline retry and a dead-letter queue.

```txt
Frontend → Pre-Signed PUT URL → S3 (original-images/)
                                  ↓ S3 Event Notification
                               SQS (buffer for S3 events)
                                  ↓
                               Lambda Worker:
                                 - Download from S3 (original)
                                 - Resize to multiple sizes (sharp)
                                 - Upload to S3 (thumbnails/)
                                 - Update DB record
                                 ↓
                               CloudFront → S3 (thumbnails) → Users
```

**Why SQS between S3 and Lambda:**

- S3 → Lambda directly: if Lambda fails, retry is limited and there is no DLQ.
- S3 → SQS → Lambda: DLQ, configurable retry, batch processing.
- Batching: one Lambda processes 10 images at once, which is cheaper.

## Pattern 7: Scheduled Jobs — Serverless Cron

Cron on AWS is an EventBridge rule that invokes a Lambda on a schedule, with no server waiting in between. The only real constraint is the 15-minute Lambda limit.

```txt
EventBridge Scheduled Rule (cron expression)
  → Lambda (daily / hourly / every 5 min)
```

**Examples:**

- Every day at 02:00 UTC (Coordinated Universal Time) → Lambda → generate reports → S3 → email.
- Every 5 minutes → Lambda → health check external APIs → CloudWatch alarm.
- First of the month → Lambda → billing cycle → SQS → invoices.

**Alternative for long jobs, over 15 min:** EventBridge → ECS Fargate Task, which runs to completion and then stops.

## Monolith vs Microservices vs Serverless Functions

Three shapes for the same backend. The choice follows team size and traffic pattern, not fashion.

**Monolith (NestJS on ECS Fargate)**

- Pros: simple to develop and deploy, no network calls between services, one database connection pool, easy to debug.
- Cons: scales as a whole, one deployment for everything, risk of coupling.
- Use when: team under 5, product not defined yet, MVP.

**Microservices (each NestJS service on ECS Fargate)**

- Pros: independent scaling, independent releases, isolation.
- Cons: network latency between services, complex distributed transactions, lots of infrastructure, distributed tracing required.
- Use when: large systems with more than 5-10 teams, different scale requirements.

**Serverless Functions (Lambda)**

- Pros: no servers, auto-scale, pay-per-request, naturally event-driven.
- Cons: cold start, stateless, 15 min limit, and cold start again with heavy frameworks.
- Use when: event-driven workloads, sporadic traffic, background jobs.

## Typical fullstack pet-project architecture (interview demo)

This is the stack to describe when the interviewer asks what you would build. There are two versions of it: the full one, and the one that costs under $10 a month.

**Pipeline in GitHub Actions** — continuous integration and delivery:

- Push → build → test → Docker build → push to ECR (Elastic Container Registry).
- Then `cdk deploy`.

**Infrastructure (CDK):**

- VPC: 2 Availability Zones, public and private subnets, a NAT (network address translation) Gateway.
- S3 + CloudFront for the static frontend.
- RDS Aurora PostgreSQL Serverless v2 + RDS Proxy.
- ECS Fargate, or API Gateway + Lambda for a simple API.
- SQS + Lambda for async tasks.
- Secrets Manager for the database password and the JWT (JSON Web Token) secret.
- CloudWatch for logs, metrics and alarms.
- Route53 + ACM (AWS Certificate Manager) for the custom domain and its SSL (Secure Sockets Layer) certificate.

**Simplified stack for a pet project:**

- Vercel or Netlify → Next.js frontend.
- Lambda + API Gateway → compiled NestJS, a simple deploy.
- RDS PostgreSQL t3.micro, or PlanetScale.
- S3 + CloudFront for uploads and media.
- Budget: under $10/month at low traffic.

## Common interview mistakes

- **"Lambda for every project"** — Lambda is the right choice for event-driven and sporadic traffic. For production APIs with continuous traffic and NestJS: ECS Fargate is cheaper and avoids cold starts. Architectural choices depend on the traffic pattern, not on trends.

- **"Start with microservices because big companies do it"** — big companies moved to microservices from a monolith as they grew. Starting with microservices: distributed systems complexity without the benefit. The right path: monolith → extract a service when scale demands it.

- **"CloudFront is only for video and high traffic"** — CloudFront is necessary for any SPA. Without a CDN (content delivery network) or an ALB, HTTPS on a custom domain is impossible. The S3 website endpoint does not support HTTPS for custom domains, so for a pet project on S3 CloudFront is required.

- **"Pre-Signed URL is insecure, better to proxy through backend"** — Pre-Signed URL is secure. It is signed with a keyed hash (HMAC), it expires via `expiresIn`, and content-type and size can be constrained through Presigned POST conditions. Proxying through backend: server load, Lambda memory overflow, higher cost.

- **"RDS is cheaper than DynamoDB"** — it depends on the pattern. RDS t3.micro = $25/month (always on). DynamoDB On-Demand at 100k requests/day ≈ $0.10/day = $3/month. But at millions of RPS (requests per second), DynamoDB Provisioned is cheaper than Per-Request. Choose by access patterns, not by gut feeling.
