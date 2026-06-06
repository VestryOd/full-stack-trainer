<!-- verified: 2026-06-05, corrections: 0 -->
# AWS Architecture Patterns

## Самый важный файл по AWS

На Senior интервью редко спрашивают:

```txt
что такое S3
```

---

Чаще спрашивают:

```txt
как бы вы построили систему
```

---

# Pattern 1

Static Website

---

Схема:

```txt
User
 ↓
CloudFront
 ↓
S3
```

---

Используется для:

```txt
Landing Pages

Documentation

Static Sites
```

---

# Pattern 2

Next.js Production

---

Очень популярный вопрос.

---

```txt
User
 ↓
CloudFront
 ↓
Next.js
 ↓
API
 ↓
PostgreSQL
```

---

# Pattern 3

Next.js + Strapi

---

Для CMS проектов.

---

```txt
User
 ↓
CloudFront
 ↓
Next.js
 ↓
Strapi
 ↓
PostgreSQL
```

---

Страницы:

```txt
ISR
```

---

После публикации:

```txt
revalidateTag()
```

---

# Pattern 4

Serverless API

---

Самая популярная AWS схема.

---

```txt
Client
 ↓
API Gateway
 ↓
Lambda
 ↓
DynamoDB
```

---

Плюсы:

```txt
простота

масштабирование

низкая стоимость
```

---

# Pattern 5

File Upload

---

Очень любят спрашивать.

---

```txt
Frontend
 ↓
Backend
 ↓
Pre-Signed URL

Frontend
 ↓
S3
```

---

# Почему так

Backend не участвует
в передаче файла.

---

# Pattern 6

Image Processing

---

```txt
Upload
 ↓
S3
 ↓
Lambda
 ↓
Thumbnail
 ↓
S3
```

---

Очень распространенная задача.

---

# Pattern 7

Queue Based Processing

---

```txt
API
 ↓
SQS
 ↓
Workers
```

---

Преимущества:

```txt
разгрузка API

ретраи

масштабирование
```

---

# Pattern 8

SNS + SQS Fan-Out

---

Очень любят Senior интервьюеры.

---

```txt
Order Service
 ↓
SNS
 ↓
SQS Billing

SQS Email

SQS Analytics
```

---

Одно событие:

```txt
много подписчиков
```

---

# Pattern 9

Microservices

---

```txt
ALB
 ↓
ECS

 ↓
User Service

 ↓
Order Service

 ↓
Payment Service
```

---

# Pattern 10

Event Driven Architecture

---

```txt
Order Created
 ↓
SNS
 ↓
Consumers
```

---

Сервисы связаны
через события.

---

# Монолит vs Microservices

Очень популярный вопрос.

---

Монолит:

```txt
проще

дешевле

быстрее разработка
```

---

Микросервисы:

```txt
масштабирование

независимые релизы

сложнее поддержка
```

---

# Lambda vs ECS

Еще один популярный вопрос.

---

Lambda:

```txt
event driven
```

---

ECS:

```txt
always running
```

---

# PostgreSQL vs DynamoDB

Очень любят спрашивать.

---

Большинство бизнес систем:

```txt
PostgreSQL
```

---

High Throughput:

```txt
DynamoDB
```

---

# Частый вопрос

Как бы вы построили интернет-магазин?

Ответ:

```txt
Next.js
 ↓
CloudFront
 ↓
NestJS
 ↓
PostgreSQL

Uploads → S3

Notifications → SQS

Emails → Workers
```

---

# Частый вопрос

Как бы вы построили CMS?

Ответ:

```txt
Next.js
 ↓
Strapi
 ↓
PostgreSQL

Images → S3

CDN → CloudFront
```

---

# Частый вопрос

Как бы вы построили систему обработки изображений?

Ответ:

```txt
Upload
 ↓
S3
 ↓
Event
 ↓
SQS
 ↓
Lambda Workers
 ↓
Thumbnail
```

---

# Самый сильный Senior ответ

Какой сервис AWS выбрать?

Ответ:

Нет универсального сервиса. Выбор зависит от требований по производительности, стоимости, отказоустойчивости, latency и характеру нагрузки. Хороший архитектор подбирает сервисы под конкретный сценарий, а не использует один и тот же стек для всех задач.