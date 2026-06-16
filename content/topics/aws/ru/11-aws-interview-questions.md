<!-- verified: 2026-06-05, corrections: 0 -->
# AWS Interview Questions (Fullstack / Senior)

## Группа 1: Основы — Cloud, Regions, IAM

**Q: Что такое AWS и что отличает её от других облаков?**

AWS (Amazon Web Services) — ведущая облачная платформа: 33 региона, 105 AZ, 200+ managed сервисов. Отличие от GCP/Azure: самая широкая экосистема сервисов, наибольшая доля рынка (~32%), лучшая зрелость сервисов для продакшена.

Shared Responsibility Model: AWS = Security OF the cloud (datacenters, hardware, managed services). You = Security IN the cloud (IAM, data encryption, app-level security, network config).

---

**Q: Что такое Region и Availability Zone? Зачем приложению несколько AZ?**

Region — географическая зона (eu-west-1 = Ирландия). В регионе 3-6 AZ — изолированных датацентров с независимым питанием, охлаждением, сетью. Физически разделены (10+ км), соединены low-latency fiber.

Зачем 2+ AZ в production:
- RDS Multi-AZ: Primary в AZ-1, синхронная репликация в Standby AZ-2 → failover ~60-120 сек
- ECS Fargate: Tasks распределены по AZ → если AZ недоступна, другие Tasks продолжают работу
- ALB: route на tasks только в здоровых AZ
- S3, DynamoDB, SQS, SNS — уже встроены 3+ AZ реплики

---

**Q: Что такое IAM Role и почему она лучше Access Keys для сервисов?**

IAM Role — набор permissions с Trust Policy (кто может принять роль). Lambda/EC2/ECS принимают роль через STS → получают временные credentials (AccessKeyId + SecretAccessKey + SessionToken, TTL 1-12ч).

Access Keys (долгоживущие): если утекают в git/.env → полный доступ пока не отозвать вручную. Role: credentials автоматически ротируются, не хранятся в коде, scope = только нужные permissions.

Principle of Least Privilege: `bucket.grantRead(fn)` → только `s3:GetObject`, не `s3:*` или `AdministratorAccess`.

Follow-up: Как Lambda получает credentials автоматически?
Lambda Runtime → Instance Metadata Service (IMDS) → STS AssumeRole → env vars: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`. SDK подхватывает автоматически — не нужно настраивать.

---

## Группа 2: S3 и CloudFront

**Q: Чем S3 отличается от файловой системы? Как организовать доступ к private файлам?**

S3 — объектное хранилище: объект = key + data + metadata. Нет настоящих папок (только key prefix `a/b/c.jpg`). Нет append/seek/lock. Нет partial update — только полная замена объекта. До 5TB на объект.

Для private файлов — Pre-Signed URL:
```typescript
const url = await getSignedUrl(s3, new GetObjectCommand({ Bucket, Key }), { expiresIn: 3600 });
```
URL подписан HMAC-SHA256, работает без AWS credentials у клиента, истекает через TTL.

Три уровня безопасности: BlockPublicAccess (блокирует всё публичное) + Bucket Policy (resource-based: разрешить CloudFront через OAC) + IAM (identity-based: `bucket.grantRead(fn)`).

---

**Q: Как деплоить SPA на AWS? Почему нужен CloudFront?**

S3 хранит статические файлы. CloudFront обязателен:
1. S3 website endpoint не поддерживает HTTPS на custom domain
2. S3 не имеет edge caching (запросы идут в один регион)
3. CloudFront: 250+ Edge Locations, HTTP→HTTPS redirect, Gzip/Brotli, custom headers

SPA routing: Custom Error Response 403/404 → /index.html (status 200) → React Router обрабатывает путь.

Cache strategy: JS/CSS с content hash → `max-age=31536000, immutable` (forever). `index.html` → `no-cache`. При деплое: инвалидировать только `/index.html`, не `/*`.

---

**Q: Как реализовать загрузку файлов без прокси через backend?**

Pre-Signed PUT URL:
1. Client → `GET /upload-url` → Backend
2. Backend → SDK: `getSignedUrl(PutObjectCommand, { expiresIn: 300 })`
3. Backend → Client: `{ url, key }`
4. Client → S3: `PUT [url]` (Backend не участвует в передаче файла!)
5. S3 trigger → SQS → Lambda (resize, virus scan, update DB)

Для ограничения размера: Presigned POST с `content-length-range` condition. Для downloads private файлов: GET Pre-Signed URL.

---

## Группа 3: Lambda и Serverless

**Q: Как работает Cold Start и как его оптимизировать?**

Cold Start: AWS создаёт новый execution environment (скачать package, запустить Node.js runtime, выполнить init code вне handler). Warm Start: уже существующий container — только вызов handler.

Оптимизация:
1. Минимизировать bundle: esbuild/tsup (tree shaking) vs webpack. Import `{ S3Client }` не весь `aws-sdk`
2. Lazy initialization: `if (!db) db = await createPool()` внутри handler (не в модульном scope)
3. Provisioned Concurrency: N environments всегда warm (платишь постоянно)
4. Избегать тяжёлых фреймворков: NestJS 2-5 сек cold start → лучше ECS Fargate

Lambda в VPC добавляет +100-600ms к cold start (ENI provisioning). Mitigation: Hyperplane ENI (улучшено в 2019), RDS Proxy вместо прямого подключения к RDS.

---

**Q: Какие типы triggers есть у Lambda? Чем synchronous отличается от asynchronous?**

Synchronous (caller ждёт ответа): API Gateway, ALB, CloudFront Functions. Errors возвращаются caller, retry — на стороне caller.

Asynchronous (fire-and-forget): S3, SNS, EventBridge. Lambda retry: 2 раза с exponential backoff, потом DLQ. Caller не получает ошибку.

Stream-based (Lambda polling): SQS (batch size 1-10000, reportBatchItemFailures), Kinesis (bisect batch on error), DynamoDB Streams. Lambda сама polling источника.

Важно для SQS: `batchItemFailures` — только упавшие items идут в retry/DLQ, остальные удаляются как успешные.

---

**Q: Когда выбрать Lambda, когда ECS Fargate?**

Lambda: event-driven (S3, SQS, SNS), sporadic трафик, simple HTTP API (<29 сек), background jobs, cron (EventBridge). Нет cold start → optimize bundle. DynamoDB лучше чем RDS (нет connection pool проблемы).

ECS Fargate: NestJS (2-5 сек cold start неприемлем), WebSocket, stateful (in-memory cache), постоянный high-throughput (>1000 RPS), процессы >15 мин.

Если CI/CD уже Docker-based: Fargate проще операционно. Если event-driven workload + pay-per-use критично: Lambda.

---

## Группа 4: API Gateway, SQS, SNS

**Q: REST API vs HTTP API в API Gateway — что выбрать?**

HTTP API (v2): $1/million (71% дешевле), ниже latency, встроенный JWT Authorizer, рекомендуется по умолчанию.

REST API (v1): $3.50/million, response caching, API Keys + Usage Plans, request/response transformation. Нужно только если требуется один из этих features.

Lambda Authorizer кэшируется (TTL 300 сек) → изменение роли пользователя: до 5 мин старый кэш действует. API Gateway timeout = 29 сек (даже если Lambda timeout больше).

---

**Q: Как работает SQS? Что такое Visibility Timeout и почему нужна идемпотентность?**

At-Least-Once Delivery: SQS гарантирует доставку минимум один раз. Одно сообщение может быть доставлено дважды (rare, но возможно).

Visibility Timeout: consumer получил сообщение → оно invisible на 30 сек (по умолч.). Если consumer не вызвал DeleteMessage (упал или timeout) → сообщение снова visible → другой consumer берёт.

→ Handlers ДОЛЖНЫ быть idempotent: сохранять messageId как ключ, проверять перед обработкой.

DLQ: после `maxReceiveCount` попыток → сообщение в DLQ. Без DLQ: poison message = бесконечный retry = блокирует очередь.

Standard Queue: неограниченный throughput, нет гарантии порядка, возможны дубликаты.
FIFO Queue: строгий порядок, exactly-once (5-мин окно дедупликации), throughput ограничен.

---

**Q: Чем SNS отличается от SQS? Когда использовать Fan-Out pattern?**

SQS: point-to-point, один consumer получает сообщение, pull model. SNS: pub/sub, все subscribers получают копию, push model.

Fan-Out: SNS Topic → N SQS очередей. Один Publish → fan-out в SQS_Billing + SQS_Email + SQS_Analytics. Каждая очередь: независимый retry, DLQ, масштабирование. Добавить новый consumer = подписать новую SQS → Order Service не меняется.

SNS fire-and-forget: сообщение не хранится. Если subscriber недоступен → потеря (для Lambda). SNS → SQS → Lambda надёжнее чем SNS → Lambda напрямую (SQS буферизует).

---

## Группа 5: RDS, DynamoDB, ECS

**Q: Как выбрать между RDS PostgreSQL и DynamoDB?**

RDS PostgreSQL: relations (FK, JOIN), гибкие SQL запросы, ACID транзакции без ограничений, schema migrations. Когда: e-commerce, CRM, финансы, стандартный fullstack. Проблема с Lambda: connection pool exhaustion → RDS Proxy.

DynamoDB: key-based access (GetItem = O(1)), single-digit ms latency, serverless, unlimited scale, no connection pool. Когда: IoT, gaming, session store, event log, Lambda backend. Требует Single Table Design: знать access patterns ДО проектирования схемы.

DynamoDB транзакции ограничены: 25 items, 5 таблиц, стоит 2x RCU/WCU. PostgreSQL: полноценные ACID, real FK constraints.

---

**Q: Как устроен Single Table Design в DynamoDB?**

Все сущности — одна таблица. `pk` + `sk` определяют тип и паттерн доступа:
- USER#123 / PROFILE → user record
- USER#123 / ORDER#456 → order
- Query pk=USER#123, sk begins_with ORDER# → все заказы за один запрос

GSI (Global Secondary Index): дополнительный паттерн доступа (например, поиск по email). Проекция: только нужные атрибуты, не весь item.

---

**Q: Как построить NestJS API на AWS в production?**

```txt
Route53 → ALB (HTTPS, health checks) → ECS Fargate Tasks (2+ AZs)
                                         ↓
                              RDS Aurora Serverless v2 + RDS Proxy
                              ElastiCache Redis (session, cache)
                              SQS + Worker Lambdas (async tasks)
                              S3 + CloudFront (uploads, media)
                              Secrets Manager (DB password, JWT)
```

Почему ECS Fargate, не Lambda: NestJS холодный старт 2-5 сек, WebSocket поддержка, нет 29 сек ограничения, persistent connection pool через RDS Proxy.

Auto Scaling: CPU 70% → +1 task, CPU 30% → -1 task (cooldown 60/30 сек). Circuit Breaker CDK: `circuitBreaker: { rollback: true }` — если Tasks не поднимаются → rollback деплоя.

---

## Группа 6: Архитектура и системный дизайн

**Q: Как бы вы построили систему обработки заказов (e-commerce)?**

```txt
POST /orders (sync, < 100ms):
  → validate → save to DB → publish SNS "OrderCreated" → 202 Accepted

SNS fan-out → SQS_Payment → Lambda_Payment (Stripe, retry 3x, DLQ)
           → SQS_Email → Lambda_Email (confirmation, idempotent)
           → SQS_Inventory → Lambda_Inventory (decrement stock)

Frontend: GET /orders/:id polling OR WebSocket для real-time status

File processing: Pre-Signed URL → S3 → SQS → Lambda (resize, scan)
Media: S3 + CloudFront с content hashing
Infra: CDK, GitHub Actions CI/CD, CloudWatch alarms, X-Ray tracing
```

Follow-up: Как обеспечить idempotency payment Lambda?
Сохранять `messageId` в ProcessedPayments таблице (DynamoDB conditional put `attribute_not_exists`). Проверять перед списанием. Stripe поддерживает `idempotencyKey` API.

---

**Q: Монолит vs Microservices: когда переходить?**

Монолит (NestJS на Fargate): один деплой, нет сетевых вызовов, простой дебаг, один DB connection pool. Правильный старт для большинства проектов.

Переходить к microservices когда:
- Разные части системы масштабируются по-разному (Payment Service vs Email Service)
- Независимые команды с разными release cycles
- Разные технологические требования (Go для CPU-intensive, Node для I/O)

Не переходить только потому что "так делают Netflix" — у Netflix другой масштаб и другие команды. Преждевременные microservices = distributed monolith = худший из миров.
