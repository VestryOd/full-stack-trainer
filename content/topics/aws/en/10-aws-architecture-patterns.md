# AWS Architecture Patterns

## Why architecture patterns matter

Senior AWS questions rarely ask "what is S3?" — they more often ask "how would you design system X?" or "why did you choose this approach?" Each pattern below is a ready-made blueprint with reasoning behind the choices.

## Pattern 1: Static SPA / Next.js static export

```txt
User → CloudFront (edge cache, HTTPS, custom domain)
          ↓ Cache MISS
          S3 (static assets: HTML, JS, CSS, images)

Use when: React/Vue SPA, Next.js with `output: 'export'`, docs, landing pages
Why CloudFront in front of S3:
  - S3 website endpoint: no HTTPS on a custom domain
  - S3: no edge caching (requests go to one region)
  - CloudFront: 250+ Edge Locations, HTTP→HTTPS redirect, Gzip/Brotli

SPA routing solution:
  CloudFront Custom Error Response: 403/404 → /index.html (status 200)
  React Router handles the path on the client
```

## Pattern 2: Fullstack SPA + REST API

```txt
User → CloudFront → S3 (Next.js static build / SPA)
                ↓ /api/*  (CACHING_DISABLED behavior)
             API Gateway HTTP API → Lambda → RDS PostgreSQL (VPC)
                                         ↓
                                    ElastiCache Redis (session, cache)
                                    S3 (files via Pre-Signed URL)

CDK stack:
  S3 + CloudFront for the frontend
  API Gateway HTTP API + Lambda for the backend
  RDS Aurora Serverless v2 + RDS Proxy (connection pooling)
  VPC: Lambda and RDS in private subnets

Use when: fullstack pet project, MVP, startup API
Trade-off: Lambda cold start for the API → Provisioned Concurrency for critical routes
```

## Pattern 3: Production NestJS API — ECS Fargate + ALB

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

Why ECS Fargate, not Lambda:
  NestJS: heavy initialization (DI, decorators) → 2-5 sec cold start
  WebSocket support (if needed)
  No 29-second response limit
  Persistent RAM (session, cache)

Auto Scaling: CPU 70% → scale out, CPU 30% → scale in
Circuit Breaker: if new Tasks fail to start → rollback
```

## Pattern 4: File Upload — Pre-Signed URL

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

For size limits: Presigned POST (conditions: content-length-range)
For private downloads: GET Pre-Signed URL (expiresIn: 3600)
```

## Pattern 5: Async Processing — Order Flow

```txt
Goal: POST /orders must respond fast,
      but we need: payment processing + email + analytics + inventory update

POST /orders (sync, < 100ms):
  → Validate order → Save to DB → Publish SNS "OrderCreated"
  → Response 202 Accepted { orderId }

SNS "OrderCreated" fan-out → 4 SQS queues:
  SQS_Payment   → Lambda_Payment (charge card, retry 3x, DLQ)
  SQS_Email     → Lambda_Email (send confirmation, idempotent)
  SQS_Inventory → Lambda_Inventory (decrement stock)
  SQS_Analytics → Lambda_Analytics (metrics, Kinesis)

GET /orders/:id → poll for status (or WebSocket for real-time)

Guarantees:
  SQS: at-least-once delivery → idempotent handlers
  DLQ: failed messages are isolated, don't block the queue
  Each service: independent retry and scaling
```

## Pattern 6: Image Processing Pipeline

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

Why SQS between S3 and Lambda:
  S3 → Lambda directly: if Lambda fails → retry is limited, no DLQ
  S3 → SQS → Lambda: DLQ + configurable retry + batch processing
  Batch: one Lambda processes 10 images at once (cheaper)
```

## Pattern 7: Scheduled Jobs — Serverless Cron

```txt
EventBridge Scheduled Rule (cron expression)
  → Lambda (daily / hourly / every 5 min)

Examples:
  "Every day at 02:00 UTC" → Lambda → generate reports → S3 → email
  "Every 5 minutes" → Lambda → health check external APIs → CloudWatch alarm
  "First of the month" → Lambda → billing cycle → SQS → invoices

Alternative for long jobs (> 15 min):
  EventBridge → ECS Fargate Task (run-to-completion, then stops)
```

## Monolith vs Microservices vs Serverless Functions

```txt
Monolith (NestJS on ECS Fargate):
  Pros: simple to develop and deploy, no network calls between services,
        single DB connection pool, easy to debug
  Cons: scales as a whole, single deployment for everything, risk of coupling
  Use when: team < 5, product not defined yet, MVP

Microservices (each NestJS service on ECS Fargate):
  Pros: independent scaling, independent releases, isolation
  Cons: network latency between services, distributed transactions are complex,
        lots of infrastructure, distributed tracing required
  Use when: large systems with > 5-10 teams, different scale requirements

Serverless Functions (Lambda):
  Pros: no servers, auto-scale, pay-per-request, naturally event-driven
  Cons: cold start, stateless, 15 min limit, cold start with heavy frameworks
  Use when: event-driven workloads, sporadic traffic, background jobs
```

## Typical fullstack pet-project architecture (interview demo)

```txt
GitHub Actions CI/CD:
  Push → Build → Test → Docker Build → Push to ECR
                      → CDK deploy

Infrastructure (CDK):
  VPC (2 AZs, public + private subnets, NAT Gateway)
  S3 + CloudFront (frontend static)
  RDS Aurora PostgreSQL Serverless v2 + RDS Proxy
  ECS Fargate (or API Gateway + Lambda for a simple API)
  SQS + Lambda (async tasks)
  Secrets Manager (DB password, JWT secret)
  CloudWatch (logs, metrics, alarms)
  Route53 + ACM (custom domain + SSL)

Simplified stack for a pet project:
  Vercel / Netlify → Next.js (frontend)
  Lambda + API Gateway → compiled NestJS (simple deploy)
  RDS PostgreSQL t3.micro or PlanetScale
  S3 + CloudFront (uploads, media)
  Budget: < $10/month at low traffic
```

## Common interview mistakes

- **"Lambda for every project"** — Lambda is the right choice for event-driven and sporadic traffic. For production APIs with continuous traffic and NestJS: ECS Fargate is cheaper and avoids cold starts. Architectural choices depend on the traffic pattern, not on trends.

- **"Start with microservices because big companies do it"** — big companies moved to microservices from a monolith as they grew. Starting with microservices: distributed systems complexity without the benefit. The right path: monolith → extract a service when scale demands it.

- **"CloudFront is only for video and high traffic"** — CloudFront is necessary for any SPA: HTTPS on a custom domain is impossible without a CDN or ALB; S3 website endpoint doesn't support HTTPS for custom domains. For a pet project on S3 — CloudFront is required.

- **"Pre-Signed URL is insecure, better to proxy through backend"** — Pre-Signed URL is secure: HMAC-signed, `expiresIn`, content-type and size constraints possible via Presigned POST conditions. Proxying through backend: server load, Lambda memory overflow, higher cost.

- **"RDS is cheaper than DynamoDB"** — it depends on the pattern. RDS t3.micro = $25/month (always on). DynamoDB On-Demand at 100k requests/day ≈ $0.10/day = $3/month. But at millions of RPS, DynamoDB Provisioned is cheaper than Per-Request. Choose by access patterns, not by gut feeling.
