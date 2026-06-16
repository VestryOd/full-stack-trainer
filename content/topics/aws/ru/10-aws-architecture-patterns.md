<!-- verified: 2026-06-05, corrections: 0 -->
# AWS Architecture Patterns

## Зачем нужны паттерны архитектуры

Senior AWS вопросы редко "что такое S3?" — чаще "как бы вы спроектировали систему X?" или "почему вы выбрали этот подход?". Каждый паттерн ниже — готовая схема с обоснованием выборов.

## Pattern 1: Static SPA / Next.js static export

```txt
User → CloudFront (edge cache, HTTPS, custom domain)
          ↓ Cache MISS
          S3 (static assets: HTML, JS, CSS, images)

Когда: React/Vue SPA, Next.js с `output: 'export'`, документация, лендинги
Почему CloudFront перед S3:
  - S3 website endpoint: нет HTTPS на custom domain
  - S3: нет edge caching (запросы идут в один регион)
  - CloudFront: 250+ Edge Locations, HTTP→HTTPS redirect, Gzip/Brotli
  
SPA routing решение:
  CloudFront Custom Error Response: 403/404 → /index.html (status 200)
  React Router обрабатывает путь на клиенте
```

## Pattern 2: Fullstack SPA + REST API

```txt
User → CloudFront → S3 (Next.js static build / SPA)
                ↓ /api/*  (CACHING_DISABLED behavior)
             API Gateway HTTP API → Lambda → RDS PostgreSQL (VPC)
                                         ↓
                                    ElastiCache Redis (session, cache)
                                    S3 (файлы через Pre-Signed URL)

CDK stack:
  S3 + CloudFront для фронтенда
  API Gateway HTTP API + Lambda для backend
  RDS Aurora Serverless v2 + RDS Proxy (connection pooling)
  VPC: Lambda и RDS в private subnets

Когда: fullstack pet-project, MVP, стартап API
Trade-off: Lambda cold start для API → Provisioned Concurrency для critical routes
```

## Pattern 3: Production NestJS API — ECS Fargate + ALB

```txt
Internet → Route53 → ALB (443/HTTPS termination, health checks)
                     ↓ Round-robin
               ECS Fargate Tasks (NestJS, 2+ copies в разных AZs)
                     ↓
               RDS Aurora PostgreSQL Multi-AZ (private subnet)
                     ↓
               ElastiCache Redis (session, distributed cache)
                     ↓
               S3 (uploads) + CloudFront (media CDN)
               SQS + Worker Lambda (async tasks: email, notifications)

Почему ECS Fargate, не Lambda:
  NestJS: тяжёлая инициализация (DI, декораторы) → 2-5 сек cold start
  WebSocket поддержка (если нужна)
  Нет 29-секундного ограничения ответа
  Постоянный RAM (session, cache)

Auto Scaling: CPU 70% → scale out, CPU 30% → scale in
Circuit Breaker: если новые Tasks не поднимаются → rollback
```

## Pattern 4: File Upload — Pre-Signed URL

```txt
Плохо (прокси через backend):
  Frontend → POST /upload (10GB) → Backend → S3
  Проблемы: трафик через сервер, Lambda timeout, memory overflow

Правильно (direct upload):
  1. Frontend → GET /upload-url?filename=photo.jpg → Backend
  2. Backend → AWS SDK: getSignedUrl(PutObjectCommand, expiresIn: 300)
  3. Backend → Frontend: { url, key }
  4. Frontend → S3: PUT напрямую (signed URL)
  5. S3 trigger: PUT → SQS → Lambda (resize, validate, virus scan)
  6. Frontend → Backend: POST /confirm { key }
  7. Backend → DB: save key

Для size limits: Presigned POST (conditions: content-length-range)
Для private downloads: GET Pre-Signed URL (expiresIn: 3600)
```

## Pattern 5: Async Processing — Order Flow

```txt
Задача: POST /orders должен отвечать быстро,
        но нужно: payment processing + email + analytics + inventory update

POST /orders (sync, < 100ms):
  → Validate order → Save to DB → Publish SNS "OrderCreated"
  → Response 202 Accepted { orderId }

SNS "OrderCreated" fan-out → 4 SQS очереди:
  SQS_Payment → Lambda_Payment (charge card, retry 3x, DLQ)
  SQS_Email   → Lambda_Email (send confirmation, idempotent)
  SQS_Inventory → Lambda_Inventory (decrement stock)
  SQS_Analytics → Lambda_Analytics (metrics, Kinesis)

GET /orders/:id → polling статуса (или WebSocket для real-time)

Гарантии:
  SQS: at-least-once delivery → idempotent handlers
  DLQ: failed messages изолируются, не блокируют очередь
  Каждый сервис: независимый retry, масштабирование
```

## Pattern 6: Image Processing Pipeline

```txt
Frontend → Pre-Signed PUT URL → S3 (original-images/)
                                  ↓ S3 Event Notification
                               SQS (буфер для S3 events)
                                  ↓
                               Lambda Worker:
                                 - Download from S3 (original)
                                 - Resize to multiple sizes (sharp)
                                 - Upload to S3 (thumbnails/)
                                 - Update DB record
                                 ↓
                               CloudFront → S3 (thumbnails) → Users

Почему SQS между S3 и Lambda:
  S3 → Lambda напрямую: если Lambda упала → retry ограничен, нет DLQ
  S3 → SQS → Lambda: DLQ + configurable retry + batch processing
  Batch: одна Lambda обрабатывает 10 изображений за раз (дешевле)
```

## Pattern 7: Scheduled Jobs — Serverless Cron

```txt
EventBridge Scheduled Rule (cron expression)
  → Lambda (daily/hourly/every 5 min)

Примеры:
  "Каждый день в 02:00 UTC" → Lambda → генерация отчётов → S3 → email
  "Каждые 5 минут" → Lambda → health check external APIs → CloudWatch alarm
  "Первое число месяца" → Lambda → billing cycle → SQS → invoices

Альтернатива для долгих jobs (> 15 мин):
  EventBridge → ECS Fargate Task (run-to-completion, потом останавливается)
```

## Монолит vs Microservices vs Serverless Functions

```txt
Монолит (NestJS на ECS Fargate):
  Pros: простота разработки и деплоя, нет сетевых вызовов между сервисами,
        один DB connection pool, легко дебажить
  Cons: масштабируется целиком, один deployment для всего, risk of coupling
  Когда: команда < 5 человек, product не определён, MVP

Microservices (каждый NestJS сервис на ECS Fargate):
  Pros: независимое масштабирование, независимые релизы, изоляция
  Cons: network latency между сервисами, распределённые транзакции сложны,
        много инфраструктуры, distributed tracing нужен
  Когда: крупные системы с > 5-10 команд, разные требования к scale

Serverless Functions (Lambda):
  Pros: нет servers, auto-scale, pay-per-request, event-driven естественно
  Cons: cold start, stateless, 15 мин limit, cold start для heavy frameworks
  Когда: event-driven workloads, sporadic traffic, background jobs
```

## Типичная архитектура fullstack pet-project (interview demo)

```txt
GitHub Actions CI/CD:
  Push → Build → Test → Docker Build → Push to ECR
                       → CDK deploy (или cdk deploy)

Infrastructure (CDK):
  VPC (2 AZ, public + private subnets, NAT Gateway)
  S3 + CloudFront (frontend static)
  RDS Aurora PostgreSQL Serverless v2 + RDS Proxy
  ECS Fargate (или API Gateway + Lambda для simple API)
  SQS + Lambda (async tasks)
  Secrets Manager (DB password, JWT secret)
  CloudWatch (logs, metrics, alarms)
  Route53 + ACM (custom domain + SSL)

Stack для pet-project (упрощённый):
  Vercel / Netlify → Next.js (frontend)
  Lambda + API Gateway → NestJS compiled (простой деплой)
  RDS PostgreSQL t3.micro или PlanetScale
  S3 + CloudFront (uploads, media)
  Бюджет: < $10/мес при малом трафике
```

## Типичные ошибки на интервью

- **"Для любого проекта — Lambda"** — Lambda — правильный выбор для event-driven и sporadic трафика. Для production API с постоянным трафиком и NestJS: ECS Fargate дешевле и без cold start. Архитектурный выбор зависит от traffic pattern, не от моды.

- **"Микросервисы сразу, потому что так делают большие компании"** — большие компании пришли к microservices из монолита, когда росли. Начинать с microservices: distributed systems сложность без пользы. Правильный путь: monolith → extract service когда scale это требует.

- **"CloudFront нужен только для видео и большого трафика"** — CloudFront необходим для любого SPA: HTTPS на кастомный домен невозможен без CDN или ALB, S3 website endpoint не поддерживает HTTPS для custom domains. Для pet-project на S3 — CloudFront обязателен.

- **"Pre-Signed URL небезопасен, лучше прокси через backend"** — Pre-Signed URL безопасен: signed HMAC, expiresIn, можно ограничить content-type и размер через Presigned POST conditions. Прокси через backend: нагрузка на сервер, Lambda memory overflow, выше стоимость.

- **"RDS дешевле DynamoDB"** — зависит от паттерна. RDS t3.micro = $25/мес (always on). DynamoDB On-Demand при 100k requests/day ≈ $0.10/день = $3/мес. Но при миллионах RPS DynamoDB Provisioned дешевле Per-Request. Выбор по access patterns, не по "кажется дешевле".
