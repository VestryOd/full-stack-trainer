<!-- verified: 2026-06-05, corrections: 0 -->
# Паттерны архитектуры AWS

## Зачем нужны паттерны архитектуры

Senior-вопросы по AWS (Amazon Web Services) редко бывают на определения. Вместо «что такое S3 (Simple Storage Service)» вам дают задачу на проектирование: как бы вы построили систему X и почему именно так. Каждый паттерн ниже — готовая схема с обоснованием выборов.

## Паттерн 1: Static SPA / Next.js static export

Статическому SPA (single-page application — одностраничному приложению) сервер не нужен: файлы лежат в S3, а раздаёт их CloudFront с ближайшей точки присутствия. CloudFront здесь не оптимизация — без него на своём домене не будет HTTPS (зашифрованный HTTP).

```txt
User → CloudFront (edge cache, HTTPS, custom domain)
          ↓ Cache MISS
          S3 (static assets: HTML, JS, CSS, images)
```

**Когда:** React/Vue SPA, Next.js с `output: 'export'`, документация, лендинги.

**Почему CloudFront перед S3:**

- У S3 website endpoint нет HTTPS на своём домене.
- У S3 нет кеша на границе сети: запросы идут в один регион.
- У CloudFront 250+ Edge Locations, редирект HTTP→HTTPS, Gzip/Brotli.

**Как решается роутинг SPA:**

- CloudFront Custom Error Response переводит 403/404 → `/index.html` со статусом 200.
- Дальше React Router разбирает путь на клиенте.

## Паттерн 2: Fullstack SPA + REST API

Тот же статический фронтенд плюс один путь, который статикой не является. CloudFront отправляет `/api/*` в API Gateway с отключённым кешем, поэтому один домен обслуживает и приложение, и его бэкенд на REST (representational state transfer).

```txt
User → CloudFront → S3 (Next.js static build / SPA)
         ↓ /api/*  (CACHING_DISABLED behavior)
       API Gateway HTTP API → Lambda → RDS PostgreSQL (VPC)
                                ↓
                           ElastiCache Redis (session, cache)
                           S3 (файлы через Pre-Signed URL)
```

**Стек CDK (Cloud Development Kit):**

- S3 + CloudFront для фронтенда.
- API Gateway HTTP API + Lambda для бэкенда.
- RDS (Relational Database Service) Aurora Serverless v2 + RDS Proxy для пула соединений.
- VPC (Virtual Private Cloud): Lambda и RDS в приватных подсетях.

**Когда:** fullstack pet-project, MVP (minimum viable product), стартап-API.

**Компромисс:** холодный старт Lambda на API. Выкупается через Provisioned Concurrency на критичных маршрутах.

## Паттерн 3: Production NestJS API — ECS Fargate + ALB

Долгоживущий API на NestJS — это тот случай, где контейнеры выигрывают у функций. Route53 указывает на ALB (Application Load Balancer), а тот раскидывает трафик по задачам ECS (Elastic Container Service) Fargate в разных зонах доступности.

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
```

**Почему ECS Fargate, а не Lambda:**

- У NestJS тяжёлая инициализация (внедрение зависимостей, декораторы) — 2-5 сек холодного старта.
- Поддержка WebSocket, если она нужна.
- Нет 29-секундного ограничения на ответ.
- Постоянная память под сессии и кеш.

**Масштабирование и страховка:**

- Auto Scaling: загрузка процессора (CPU) 70% → scale out, 30% → scale in.
- Circuit Breaker: если новые Tasks не поднимаются → откат.

## Паттерн 4: File Upload — Pre-Signed URL

Загрузка через свой бэкенд заставляет платить за одни и те же байты дважды. Pre-Signed URL позволяет браузеру сделать PUT прямо в S3, а бэкенд только подписывает запрос и сохраняет ключ.

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
```

Два варианта той же идеи:

- Для ограничения размера: Presigned POST с условием `content-length-range`.
- Для приватных скачиваний: GET Pre-Signed URL с `expiresIn: 3600`.

## Паттерн 5: Async Processing — Order Flow

`POST /orders` должен отвечать быстро, но заказу нужны ещё оплата, письмо, аналитика и списание со склада. Паттерн делает синхронно минимум, публикует одно событие SNS (Simple Notification Service), а остальное разбирают четыре очереди.

```txt
POST /orders (sync, < 100ms):
  → Validate order → Save to DB → Publish SNS "OrderCreated"
  → Response 202 Accepted { orderId }

SNS "OrderCreated" fan-out → 4 SQS очереди:
  SQS_Payment → Lambda_Payment (charge card, retry 3x, DLQ)
  SQS_Email   → Lambda_Email (send confirmation, idempotent)
  SQS_Inventory → Lambda_Inventory (decrement stock)
  SQS_Analytics → Lambda_Analytics (metrics, Kinesis)

GET /orders/:id → polling статуса (или WebSocket для real-time)
```

**Что это даёт:**

- SQS (Simple Queue Service) доставляет минимум один раз, поэтому обработчики должны быть идемпотентными.
- DLQ (dead-letter queue) изолирует упавшие сообщения, и они не блокируют очередь.
- Каждый сервис повторяет и масштабируется независимо.

## Паттерн 6: Image Processing Pipeline

Обработка картинок — это паттерн загрузки с одним лишним звеном: очередью между событием S3 и воркером. Это звено и покупает конвейеру повторы и очередь недоставленных.

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
```

**Почему SQS между S3 и Lambda:**

- S3 → Lambda напрямую: если Lambda упала, повторы ограничены и DLQ нет.
- S3 → SQS → Lambda: DLQ, настраиваемые повторы, пакетная обработка.
- Пакет: одна Lambda обрабатывает 10 изображений за раз, и это дешевле.

## Паттерн 7: Scheduled Jobs — Serverless Cron

Cron в AWS — это правило EventBridge, которое по расписанию вызывает Lambda, и никакой сервер между вызовами не ждёт. Единственное реальное ограничение — 15 минут на выполнение Lambda.

```txt
EventBridge Scheduled Rule (cron expression)
  → Lambda (daily/hourly/every 5 min)
```

**Примеры:**

- Каждый день в 02:00 UTC (всемирное координированное время) → Lambda → генерация отчётов → S3 → email.
- Каждые 5 минут → Lambda → health check внешних API → CloudWatch alarm.
- Первое число месяца → Lambda → биллинговый цикл → SQS → счета.

**Альтернатива для долгих задач, дольше 15 минут:** EventBridge → ECS Fargate Task, который отрабатывает до конца и останавливается.

## Монолит vs Microservices vs Serverless Functions

Три формы одного и того же бэкенда. Выбор идёт от размера команды и характера трафика, а не от моды.

**Монолит (NestJS на ECS Fargate)**

- Плюсы: простота разработки и деплоя, нет сетевых вызовов между сервисами, один пул соединений с базой, легко отлаживать.
- Минусы: масштабируется целиком, один деплой на всё, риск связанности.
- Когда: команда меньше 5 человек, продукт ещё не определён, MVP.

**Microservices (каждый сервис NestJS на ECS Fargate)**

- Плюсы: независимое масштабирование, независимые релизы, изоляция.
- Минусы: сетевые задержки между сервисами, сложные распределённые транзакции, много инфраструктуры, нужна распределённая трассировка.
- Когда: крупные системы с более чем 5-10 командами, разные требования к масштабу.

**Serverless Functions (Lambda)**

- Плюсы: нет серверов, авто-масштабирование, оплата за запрос, событийность из коробки.
- Минусы: холодный старт, отсутствие состояния, лимит 15 минут, и снова холодный старт на тяжёлых фреймворках.
- Когда: событийные нагрузки, нерегулярный трафик, фоновые задачи.

## Типичная архитектура fullstack pet-project (interview demo)

Это тот стек, который стоит описывать, когда интервьюер спрашивает, что бы вы построили. Версии две: полная и та, что стоит меньше $10 в месяц.

**Конвейер в GitHub Actions** — непрерывная интеграция и доставка:

- Push → сборка → тесты → Docker build → отправка в ECR (Elastic Container Registry).
- Дальше `cdk deploy`.

**Инфраструктура (CDK):**

- VPC: 2 зоны доступности, публичные и приватные подсети, NAT Gateway (network address translation).
- S3 + CloudFront для статики фронтенда.
- RDS Aurora PostgreSQL Serverless v2 + RDS Proxy.
- ECS Fargate, либо API Gateway + Lambda для простого API.
- SQS + Lambda для асинхронных задач.
- Secrets Manager для пароля базы и секрета JWT (JSON Web Token).
- CloudWatch для логов, метрик и алармов.
- Route53 + ACM (AWS Certificate Manager) для своего домена и его сертификата SSL (Secure Sockets Layer).

**Упрощённый стек для pet-project:**

- Vercel или Netlify → фронтенд на Next.js.
- Lambda + API Gateway → скомпилированный NestJS, простой деплой.
- RDS PostgreSQL t3.micro или PlanetScale.
- S3 + CloudFront для загрузок и медиа.
- Бюджет: меньше $10/мес при малом трафике.

## Типичные ошибки на интервью

- **"Для любого проекта — Lambda"** — Lambda — правильный выбор для event-driven и sporadic трафика. Для production API с постоянным трафиком и NestJS: ECS Fargate дешевле и без cold start. Архитектурный выбор зависит от traffic pattern, не от моды.

- **"Микросервисы сразу, потому что так делают большие компании"** — большие компании пришли к microservices из монолита, когда росли. Начинать с microservices: distributed systems сложность без пользы. Правильный путь: monolith → extract service когда scale это требует.

- **"CloudFront нужен только для видео и большого трафика"** — CloudFront необходим для любого SPA. Без CDN (content delivery network — сети доставки контента) или ALB своего домена с HTTPS не получится. S3 website endpoint не поддерживает HTTPS для своих доменов, так что для pet-project на S3 CloudFront обязателен.

- **"Pre-Signed URL небезопасен, лучше прокси через backend"** — Pre-Signed URL безопасен. Он подписан хешем с ключом (HMAC), живёт ограниченное время через `expiresIn`, а content-type и размер ограничиваются условиями Presigned POST. Прокси через backend: нагрузка на сервер, Lambda memory overflow, выше стоимость.

- **"RDS дешевле DynamoDB"** — зависит от паттерна. RDS t3.micro = $25/мес (always on). DynamoDB On-Demand при 100k requests/day ≈ $0.10/день = $3/мес. Но при миллионах RPS (запросов в секунду) DynamoDB Provisioned дешевле Per-Request. Выбор по access patterns, не по "кажется дешевле".
