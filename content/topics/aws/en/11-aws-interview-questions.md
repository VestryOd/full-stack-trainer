# AWS Interview Questions (Fullstack / Senior)

## Group 1: Fundamentals — Cloud, Regions, IAM (Identity and Access Management)

**Q: What is AWS and what distinguishes it from other clouds?**

AWS (Amazon Web Services) is the leading cloud platform: 33 regions, 105 Availability Zones, 200+ managed services. Difference from Google Cloud and Azure: broadest service ecosystem, largest market share (~32%), most mature production-grade services.

The Shared Responsibility Model splits security in two:

- AWS is responsible for security **of** the cloud: datacenters, hardware, managed services.
- You are responsible for security **in** the cloud: IAM (Identity and Access Management), data encryption, app-level security, network config.

---

**Q: What is a Region and an Availability Zone? Why does an application need multiple AZs?**

Region — a geographic zone (eu-west-1 = Ireland). Within a region there are 3-6 AZs — isolated datacenters with independent power, cooling, and networking. Physically separated (10+ km), connected by low-latency fiber.

Why 2+ AZs in production:

- RDS (Relational Database Service) Multi-AZ: Primary in AZ-1, synchronous replication to Standby AZ-2 → failover ~60-120 sec
- ECS (Elastic Container Service) Fargate: Tasks spread across AZs → if an AZ goes down, other Tasks keep running
- ALB (Application Load Balancer): routes only to tasks in healthy AZs
- S3 (Simple Storage Service), DynamoDB, SQS (Simple Queue Service) and SNS (Simple Notification Service) already replicate across 3+ AZs

---

**Q: What is an IAM Role and why is it better than Access Keys for services?**

An IAM Role is a set of permissions with a Trust Policy, which says who can assume the role. Lambda, EC2 (Elastic Compute Cloud) and ECS assume a role through STS (Security Token Service). In return they get temporary credentials — AccessKeyId, SecretAccessKey, SessionToken — with a TTL (time to live) of 1 to 12 hours.

Access Keys (long-lived): if they leak into git/.env → full access until manually revoked. Role: credentials are automatically rotated, never stored in code, scope = only necessary permissions.

Principle of Least Privilege: `bucket.grantRead(fn)` → only `s3:GetObject`, not `s3:*` or `AdministratorAccess`.

Follow-up: How does Lambda get credentials automatically?
Lambda Runtime → Instance Metadata Service (IMDS) → STS AssumeRole → env vars: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`. The AWS SDK (software development kit) picks them up automatically — no configuration needed.

---

## Group 2: S3 and CloudFront

**Q: How does S3 differ from a filesystem? How do you control access to private files?**

S3 is object storage: object = key + data + metadata. No real folders (only key prefix `a/b/c.jpg`). No append/seek/lock. No partial update — only full object replacement. Up to 5TB per object.

For private files — Pre-Signed URL:
```typescript
const url = await getSignedUrl(
  s3, new GetObjectCommand({ Bucket, Key }), { expiresIn: 3600 },
);
```
The URL is signed using HMAC (hash-based message authentication code) over SHA256 (a 256-bit hash). No AWS credentials are needed on the client, and the link stops working once its TTL runs out.

Three security layers: BlockPublicAccess (blocks all public access) + Bucket Policy (resource-based: allow CloudFront via OAC — Origin Access Control) + IAM (identity-based: `bucket.grantRead(fn)`).

---

**Q: How do you deploy an SPA to AWS? Why is CloudFront necessary?**

S3 stores the static files of the SPA (single-page application). CloudFront is required:

1. S3 website endpoint doesn't support HTTPS (encrypted HTTP) on a custom domain
2. S3 has no edge caching (requests hit one region)
3. CloudFront: 250+ Edge Locations, HTTP→HTTPS redirect, Gzip/Brotli, custom headers

SPA routing: Custom Error Response 403/404 → /index.html (status 200) → React Router handles the path.

Cache strategy: JS/CSS with content hash → `max-age=31536000, immutable` (forever). `index.html` → `no-cache`. On deploy: invalidate only `/index.html`, not `/*`.

---

**Q: How do you implement file uploads without proxying through the backend?**

Pre-Signed PUT URL:
1. Client → `GET /upload-url` → Backend
2. Backend → SDK: `getSignedUrl(PutObjectCommand, { expiresIn: 300 })`
3. Backend → Client: `{ url, key }`
4. Client → S3: `PUT [url]` (Backend is not involved in file transfer!)
5. S3 trigger → SQS → Lambda (resize, virus scan, update the database record)

For size limits: Presigned POST with `content-length-range` condition. For private file downloads: GET Pre-Signed URL.

---

## Group 3: Lambda and Serverless

**Q: How does Cold Start work and how do you optimize it?**

Cold Start: AWS creates a new execution environment (download package, start Node.js runtime, run init code outside the handler). Warm Start: reuses an existing container — only the handler is called.

Optimization:

1. Minimize bundle: esbuild/tsup (tree shaking) vs webpack. Import `{ S3Client }` not the whole `aws-sdk`
2. Lazy initialization: `if (!db) db = await createPool()` inside handler (not at module scope)
3. Provisioned Concurrency: N environments always warm (you pay continuously)
4. Avoid heavy frameworks: NestJS 2-5 sec cold start → better on ECS Fargate

Lambda inside a VPC (Virtual Private Cloud) adds 100-600ms to cold start, because it has to provision an ENI (elastic network interface). Mitigation: Hyperplane ENI (improved 2019), RDS Proxy instead of a direct RDS connection.

---

**Q: What trigger types does Lambda have? How does synchronous differ from asynchronous?**

Synchronous (caller waits for the response): API Gateway, ALB, CloudFront Functions. Errors are returned to the caller; retry is on the caller's side.

Asynchronous (fire-and-forget): S3, SNS, EventBridge. Lambda retries 2 times with exponential backoff, then sends the event to a DLQ (dead-letter queue). The caller doesn't receive the error.

Stream-based (Lambda polling): SQS (batch size 1-10000, `reportBatchItemFailures`), Kinesis (bisect batch on error), DynamoDB Streams. Lambda polls the source itself.

Important for SQS: `batchItemFailures` — only failed items go to retry/DLQ, and the others are deleted as successful.

---

**Q: When to choose Lambda, when to choose ECS Fargate?**

Lambda: event-driven (S3, SQS, SNS), sporadic traffic, simple HTTP API (<29 sec), background jobs, cron (EventBridge). Minimize cold start → optimize bundle. DynamoDB preferred over RDS (no connection pool problem).

ECS Fargate: NestJS (2-5 sec cold start is unacceptable), WebSocket, stateful (in-memory cache), continuous high-throughput (>1000 requests per second), processes >15 min.

If the build pipeline already produces Docker images: Fargate is simpler operationally. If event-driven workload + pay-per-use is critical: Lambda.

---

## Group 4: API Gateway, SQS, SNS

**Q: REST API vs HTTP API in API Gateway — what to choose?**

REST (representational state transfer) is the older of the two API Gateway flavours.

HTTP API (v2): $1/million (71% cheaper), lower latency, built-in JWT (JSON Web Token) Authorizer — recommended by default.

REST API (v1): $3.50/million, response caching, API Keys + Usage Plans, request/response transformation. Only needed if one of these specific features is required.

Lambda Authorizer result is cached (TTL 300 sec) → user role change: old cache active for up to 5 min. API Gateway timeout = 29 sec (even if Lambda timeout is longer).

---

**Q: How does SQS work? What is Visibility Timeout and why is idempotency required?**

At-Least-Once Delivery: SQS guarantees delivery at least once. A message can be delivered twice (rare, but possible).

Visibility Timeout: consumer received message → it's invisible for 30 sec (default). If consumer didn't call DeleteMessage (crashed or timed out) → message becomes visible again → another consumer picks it up.

Handlers therefore **must** be idempotent: store `messageId` as a key, and check it before processing.

DLQ: after `maxReceiveCount` attempts → message moved to DLQ. Without DLQ: poison message = infinite retry = blocks the queue.

Standard Queue: unlimited throughput, no order guarantee, duplicates possible.
FIFO Queue (first in, first out): strict order, exactly-once (5-min dedup window), throughput limited.

---

**Q: How does SNS differ from SQS? When to use Fan-Out pattern?**

SQS: point-to-point, one consumer receives the message, pull model. SNS: pub/sub, all subscribers receive a copy, push model.

Fan-Out: SNS Topic → N SQS queues. One Publish → fan-out into SQS_Billing + SQS_Email + SQS_Analytics. Each queue: independent retry, DLQ, scaling. Add a new consumer = subscribe a new SQS → Order Service unchanged.

SNS is fire-and-forget: no storage. If subscriber is unavailable → message lost (for Lambda). SNS → SQS → Lambda is more reliable than SNS → Lambda directly (SQS buffers).

---

## Group 5: RDS, DynamoDB, ECS

**Q: How do you choose between RDS PostgreSQL and DynamoDB?**

RDS PostgreSQL: relations through foreign keys and JOIN, flexible SQL queries, unrestricted ACID transactions (atomicity, consistency, isolation, durability), schema migrations. Use when: e-commerce, CRM (customer relationship management), finance, standard fullstack. Lambda problem: connection pool exhaustion → use RDS Proxy.

DynamoDB: key-based access (`GetItem` = O(1)), single-digit ms latency, serverless, unlimited scale, no connection pool. Use when: IoT (Internet of Things), gaming, session store, event log, Lambda backend. Requires Single Table Design: know the access patterns **before** designing the schema.

DynamoDB transactions are limited: 25 items, 5 tables, and they cost double — 2x RCU (read capacity units) and 2x WCU (write capacity units). PostgreSQL: full ACID, real foreign key constraints.

---

**Q: How does Single Table Design work in DynamoDB?**

All entities — one table. `pk` + `sk` define the type and access pattern:

- `USER#123` / `PROFILE` → user record
- `USER#123` / `ORDER#456` → order
- Query `pk=USER#123, sk begins_with ORDER#` → all orders in one request

GSI (Global Secondary Index): additional access pattern (e.g., search by email). Projection: only needed attributes, not the full item.

---

**Q: How would you build a NestJS API on AWS in production?**

```txt
Route53 → ALB (HTTPS, health checks) → ECS Fargate Tasks (2+ AZs)
                                         ↓
                              RDS Aurora Serverless v2 + RDS Proxy
                              ElastiCache Redis (session, cache)
                              SQS + Worker Lambdas (async tasks)
                              S3 + CloudFront (uploads, media)
                              Secrets Manager (DB password, JWT)
```

Why ECS Fargate, not Lambda: NestJS cold start 2-5 sec, WebSocket support, no 29-sec limit, persistent connection pool via RDS Proxy.

Auto Scaling by CPU (processor) load: 70% → +1 task, 30% → -1 task (cooldown 60/30 sec). Circuit Breaker in CDK: `circuitBreaker: { rollback: true }` — if Tasks fail to start → deployment rollback.

---

## Group 6: Architecture and System Design

**Q: How would you build an order processing system (e-commerce)?**

```txt
POST /orders (sync, < 100ms):
→ validate → save to DB → publish SNS "OrderCreated" → 202 Accepted

SNS fan-out → SQS_Payment   → Lambda_Payment (Stripe, retry 3x, DLQ)
           → SQS_Email     → Lambda_Email (confirmation, idempotent)
           → SQS_Inventory → Lambda_Inventory (decrement stock)

Frontend: GET /orders/:id polling OR WebSocket for real-time status

File processing: Pre-Signed URL → S3 → SQS → Lambda (resize, scan)
Media: S3 + CloudFront with content hashing
Infra: CDK, GitHub Actions CI/CD, CloudWatch alarms, X-Ray tracing
```

Follow-up: How do you ensure idempotency for the payment Lambda?
Save `messageId` in a ProcessedPayments table (DynamoDB conditional put `attribute_not_exists`). Check before charging. Stripe also supports `idempotencyKey` API.

---

**Q: Monolith vs Microservices — when to make the switch?**

Monolith (NestJS on Fargate): one deploy, no network calls, simple debugging, one database connection pool. The right starting point for most projects.

Switch to microservices when:

- Different parts of the system scale differently (Payment Service vs Email Service)
- Independent teams with different release cycles
- Different tech requirements: Go for processor-bound work (CPU), Node for I/O

Don't switch just because "that's what Netflix does" — Netflix has different scale and different teams. Premature microservices = distributed monolith = the worst of both worlds.
