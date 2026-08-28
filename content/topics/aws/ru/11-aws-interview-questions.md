<!-- verified: 2026-06-05, corrections: 0 -->
# AWS — вопросы для собеседования (Fullstack / Senior)

## Группа 1: Основы — Cloud, Regions, IAM (Identity and Access Management)

**Q: Что такое AWS и что отличает её от других облаков?**

AWS (Amazon Web Services) — ведущая облачная платформа: 33 региона, 105 зон доступности (AZ), 200+ управляемых сервисов. Отличие от Google Cloud и Azure: самая широкая экосистема сервисов, наибольшая доля рынка (~32%), лучшая зрелость сервисов для продакшена.

Модель разделённой ответственности (Shared Responsibility Model) делит безопасность надвое:

- AWS отвечает за безопасность **самого облака**: датацентры, железо, управляемые сервисы.
- Вы отвечаете за безопасность **внутри облака**: IAM (Identity and Access Management), шифрование данных, безопасность на уровне приложения, настройка сети.

---

**Q: Что такое Region и Availability Zone? Зачем приложению несколько AZ?**

Region — географическая зона (eu-west-1 = Ирландия). В регионе 3-6 AZ — изолированных датацентров с независимым питанием, охлаждением, сетью. Физически разделены (10+ км), соединены оптикой с низкой задержкой.

Зачем 2+ AZ в production:

- RDS (Relational Database Service) Multi-AZ: Primary в AZ-1, синхронная репликация в Standby AZ-2 → failover ~60-120 сек
- ECS (Elastic Container Service) Fargate: Tasks распределены по AZ → если AZ недоступна, другие Tasks продолжают работу
- ALB (Application Load Balancer): маршрутизирует только на задачи в здоровых AZ
- S3 (Simple Storage Service), DynamoDB, SQS (Simple Queue Service) и SNS (Simple Notification Service) — 3+ реплики по AZ уже встроены

---

**Q: Что такое IAM Role и почему она лучше Access Keys для сервисов?**

IAM Role — набор прав с Trust Policy, которая говорит, кто может принять роль. Lambda, EC2 (Elastic Compute Cloud) и ECS принимают роль через STS (Security Token Service). Взамен они получают временные учётные данные — AccessKeyId, SecretAccessKey, SessionToken — с TTL (time to live — временем жизни) от 1 до 12 часов.

Access Keys (долгоживущие): если утекают в git/.env → полный доступ, пока не отозвать вручную. Role: учётные данные ротируются автоматически, не хранятся в коде, а область действия — только нужные права.

Principle of Least Privilege: `bucket.grantRead(fn)` → только `s3:GetObject`, не `s3:*` или `AdministratorAccess`.

Follow-up: Как Lambda получает credentials автоматически?
Lambda Runtime → Instance Metadata Service (IMDS) → STS AssumeRole → env vars: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`. AWS SDK (software development kit — комплект разработки) подхватывает их автоматически, настраивать ничего не нужно.

---

## Группа 2: S3 и CloudFront

**Q: Чем S3 отличается от файловой системы? Как организовать доступ к private файлам?**

S3 — объектное хранилище: объект = key + data + metadata. Нет настоящих папок (только key prefix `a/b/c.jpg`). Нет append/seek/lock. Нет partial update — только полная замена объекта. До 5TB на объект.

Для private файлов — Pre-Signed URL:
```typescript
const url = await getSignedUrl(
  s3, new GetObjectCommand({ Bucket, Key }), { expiresIn: 3600 },
);
```
Ссылка подписана через HMAC (hash-based message authentication code) поверх SHA256 (256-битный хеш). Учётные данные AWS на клиенте не нужны, а ссылка перестаёт работать, когда истекает её TTL.

Три уровня безопасности: BlockPublicAccess (блокирует всё публичное) + Bucket Policy (resource-based: разрешить CloudFront через OAC — Origin Access Control) + IAM (identity-based: `bucket.grantRead(fn)`).

---

**Q: Как деплоить SPA на AWS? Почему нужен CloudFront?**

S3 хранит статические файлы SPA (single-page application — одностраничного приложения). CloudFront обязателен:

1. S3 website endpoint не поддерживает HTTPS (зашифрованный HTTP) на своём домене
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
5. S3 trigger → SQS → Lambda (resize, virus scan, обновить запись в базе)

Для ограничения размера: Presigned POST с условием `content-length-range`. Для скачивания приватных файлов: GET Pre-Signed URL.

---

## Группа 3: Lambda и Serverless

**Q: Как работает Cold Start и как его оптимизировать?**

Cold Start: AWS создаёт новый execution environment (скачать package, запустить Node.js runtime, выполнить init code вне handler). Warm Start: уже существующий container — только вызов handler.

Оптимизация:

1. Минимизировать bundle: esbuild/tsup (tree shaking) vs webpack. Import `{ S3Client }` не весь `aws-sdk`
2. Lazy initialization: `if (!db) db = await createPool()` внутри handler (не в модульном scope)
3. Provisioned Concurrency: N environments всегда warm (платите постоянно)
4. Избегать тяжёлых фреймворков: NestJS 2-5 сек cold start → лучше ECS Fargate

Lambda внутри VPC (Virtual Private Cloud) добавляет 100-600ms к холодному старту, потому что ей нужно поднять ENI (elastic network interface — сетевой интерфейс). Что помогает: Hyperplane ENI (улучшено в 2019), RDS Proxy вместо прямого подключения к RDS.

---

**Q: Какие типы triggers есть у Lambda? Чем synchronous отличается от asynchronous?**

Synchronous (вызывающая сторона ждёт ответа): API Gateway, ALB, CloudFront Functions. Ошибки возвращаются вызывающей стороне, повторы — на её стороне.

Asynchronous (fire-and-forget): S3, SNS, EventBridge. Lambda повторяет 2 раза с экспоненциальной задержкой, потом отправляет событие в DLQ (dead-letter queue — очередь недоставленных). Вызывающая сторона ошибку не получает.

Stream-based (Lambda polling): SQS (batch size 1-10000, `reportBatchItemFailures`), Kinesis (bisect batch on error), DynamoDB Streams. Здесь Lambda сама опрашивает источник.

Важно для SQS: `batchItemFailures` — только упавшие items идут в retry/DLQ, остальные удаляются как успешные.

---

**Q: Когда выбрать Lambda, когда ECS Fargate?**

Lambda: событийная работа (S3, SQS, SNS), нерегулярный трафик, простой HTTP API (<29 сек), фоновые задачи, cron (EventBridge). Минимизировать холодный старт → оптимизировать бандл. DynamoDB лучше, чем RDS: нет проблемы с пулом соединений.

ECS Fargate: NestJS (2-5 сек холодного старта неприемлемы), WebSocket, состояние в памяти, постоянная высокая нагрузка (>1000 запросов в секунду), процессы >15 мин.

Если сборка уже собирает образы Docker: Fargate проще в эксплуатации. Если важны событийная нагрузка и оплата по факту: Lambda.

---

## Группа 4: API Gateway, SQS, SNS

**Q: REST API vs HTTP API в API Gateway — что выбрать?**

HTTP API (v2): $1/million (71% дешевле), ниже задержка, встроенный авторизатор JWT (JSON Web Token) — рекомендуется по умолчанию.

REST (representational state transfer) API (v1): $3.50/million, кеширование ответов, API Keys + Usage Plans, преобразование запроса и ответа. Нужен, только если требуется одна из этих возможностей.

Lambda Authorizer кэшируется (TTL 300 сек) → изменение роли пользователя: до 5 мин старый кэш действует. API Gateway timeout = 29 сек (даже если Lambda timeout больше).

---

**Q: Как работает SQS? Что такое Visibility Timeout и почему нужна идемпотентность?**

At-Least-Once Delivery: SQS гарантирует доставку минимум один раз. Одно сообщение может быть доставлено дважды — редко, но может.

Visibility Timeout: потребитель получил сообщение → оно невидимо 30 сек (по умолчанию). Если потребитель не вызвал DeleteMessage (упал или вышел за таймаут) → сообщение снова видимо → его берёт другой потребитель.

Поэтому обработчики **должны** быть идемпотентными: сохранять `messageId` как ключ и проверять его перед обработкой.

DLQ: после `maxReceiveCount` попыток → сообщение в DLQ. Без DLQ: poison message = бесконечный retry = блокирует очередь.

Standard Queue: неограниченный throughput, нет гарантии порядка, возможны дубликаты.
FIFO Queue (first in, first out): строгий порядок, exactly-once (5-мин окно дедупликации), пропускная способность ограничена.

---

**Q: Чем SNS отличается от SQS? Когда использовать Fan-Out pattern?**

SQS: point-to-point, один consumer получает сообщение, pull model. SNS: pub/sub, все subscribers получают копию, push model.

Fan-Out: SNS Topic → N SQS очередей. Один Publish → fan-out в SQS_Billing + SQS_Email + SQS_Analytics. Каждая очередь: независимый retry, DLQ, масштабирование. Добавить новый consumer = подписать новую SQS → Order Service не меняется.

SNS fire-and-forget: сообщение не хранится. Если subscriber недоступен → потеря (для Lambda). SNS → SQS → Lambda надёжнее чем SNS → Lambda напрямую (SQS буферизует).

---

## Группа 5: RDS, DynamoDB, ECS

**Q: Как выбрать между RDS PostgreSQL и DynamoDB?**

RDS PostgreSQL: связи через внешние ключи и JOIN, гибкие SQL-запросы, транзакции ACID (атомарность, согласованность, изоляция, устойчивость) без ограничений, миграции схемы. Когда: e-commerce, CRM (управление отношениями с клиентами), финансы, стандартный fullstack. Проблема с Lambda: исчерпание пула соединений → RDS Proxy.

DynamoDB: доступ по ключу (`GetItem` = O(1)), задержка в единицы миллисекунд, serverless, неограниченный масштаб, пула соединений нет. Когда: IoT (Internet of Things), gaming, session store, event log, бэкенд на Lambda. Требует Single Table Design: знать паттерны доступа **до** проектирования схемы.

Транзакции DynamoDB ограничены: 25 items, 5 таблиц, и стоят вдвое дороже — 2x RCU (read capacity units) и 2x WCU (write capacity units). PostgreSQL: полноценный ACID и настоящие ограничения по внешним ключам.

---

**Q: Как устроен Single Table Design в DynamoDB?**

Все сущности — одна таблица. `pk` + `sk` определяют тип и паттерн доступа:

- `USER#123` / `PROFILE` → user record
- `USER#123` / `ORDER#456` → order
- Query `pk=USER#123, sk begins_with ORDER#` → все заказы за один запрос

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

Auto Scaling по загрузке CPU (процессора): 70% → +1 task, 30% → -1 task (cooldown 60/30 сек). Circuit Breaker CDK: `circuitBreaker: { rollback: true }` — если Tasks не поднимаются → rollback деплоя.

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

Монолит (NestJS на Fargate): один деплой, нет сетевых вызовов, простая отладка, один пул соединений с базой. Правильный старт для большинства проектов.

Переходить к microservices, когда:

- Разные части системы масштабируются по-разному (Payment Service vs Email Service)
- Независимые команды с разными циклами релизов
- Разные технологические требования: Go для задач, упирающихся в процессор, Node для ввода-вывода

Не переходить только потому что "так делают Netflix" — у Netflix другой масштаб и другие команды. Преждевременные microservices = distributed monolith = худший из миров.
