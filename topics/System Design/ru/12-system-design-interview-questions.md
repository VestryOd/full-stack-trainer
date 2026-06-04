# System Design Interview Questions

## Самые популярные задачи Senior Fullstack интервью

---

# 1. Design URL Shortener

Пример:

```txt
bit.ly
tinyurl
```

---

# Проверяют

```txt
ID Generation

Caching

Database Design

Scalability
```

---

# Ожидаемая архитектура

```txt
Client
 ↓
API
 ↓
Redis
 ↓
PostgreSQL
```

---

# Ключевые темы

```txt
Base62

Read Replicas

Analytics Queue
```

---

# Частый Follow-Up

Как избежать коллизий?

---

Ответ:

```txt
Auto Increment
+
Base62
```

---

# 2. Design Chat System

Пример:

```txt
Telegram

Slack

WhatsApp
```

---

# Проверяют

```txt
WebSockets

Realtime

Presence

Pub/Sub
```

---

# Ожидаемая архитектура

```txt
Client
 ↓
WebSocket
 ↓
Chat Service
 ↓
PostgreSQL
```

---

Дополнительно:

```txt
Redis Pub/Sub
```

---

# Частый Follow-Up

Как масштабировать WebSocket?

---

Ответ:

```txt
Redis Pub/Sub

Kafka
```

---

# 3. Design Notification System

---

# Проверяют

```txt
Queues

Event Driven

Fan Out
```

---

# Ожидаемая архитектура

```txt
Producer
 ↓
SNS
 ↓
SQS
 ↓
Workers
```

---

# Частый Follow-Up

Почему не отправлять email напрямую?

---

Ответ:

```txt
Latency

Fault Tolerance
```

---

# 4. Design File Upload Service

Очень популярно.

---

# Проверяют

```txt
S3

CDN

Queues
```

---

# Хорошая архитектура

```txt
Frontend
 ↓
Backend
 ↓
PreSigned URL

Frontend
 ↓
S3
```

---

# Follow-Up

Как генерировать thumbnail?

---

Ответ:

```txt
S3
 ↓
Queue
 ↓
Worker
```

---

# 5. Design Instagram Feed

Одна из самых популярных задач.

---

# Проверяют

```txt
Feed Generation

Caching

Database Scaling
```

---

# Основная проблема

Как быстро показывать ленту.

---

# Подход 1

Fan Out On Read.

---

При открытии:

```txt
собираем feed
```

---

На лету.

---

# Подход 2

Fan Out On Write.

---

При публикации поста:

```txt
заранее обновляем feed
```

---

Подписчиков.

---

# Частый Follow-Up

Что выберет Instagram?

---

Ответ:

Гибрид.

---

# 6. Design YouTube

Очень любят спрашивать.

---

# Проверяют

```txt
Video Storage

CDN

Streaming
```

---

# Архитектура

```txt
Upload
 ↓
S3
 ↓
Encoding Queue
 ↓
Workers
 ↓
CDN
```

---

# Follow-Up

Почему нельзя отдавать видео напрямую?

---

Ответ:

```txt
Bandwidth

Latency
```

---

# 7. Design Dropbox

---

# Проверяют

```txt
Large Files

Synchronization

Storage
```

---

# Архитектура

```txt
Client
 ↓
API
 ↓
Metadata DB
 ↓
Object Storage
```

---

# Follow-Up

Как синхронизировать файлы?

---

Ответ:

```txt
Versioning

Change Events
```

---

# 8. Design Ride Sharing

Пример:

```txt
Uber

Bolt
```

---

# Проверяют

```txt
Geolocation

Realtime

Matching
```

---

# Архитектура

```txt
Driver Service

Location Service

Matching Service
```

---

# Follow-Up

Как искать ближайших водителей?

---

Ответ:

```txt
Geohash

Spatial Index
```

---

# 9. Design Booking System

Очень популярно.

---

Пример:

```txt
Booking

Airbnb

Cinema Seats
```

---

# Проверяют

```txt
Transactions

Locks

Consistency
```

---

# Главная проблема

Двойное бронирование.

---

# Решение

```txt
DB Transaction

Row Lock

Redis Lock
```

---

# Follow-Up

Почему Redis Lock не всегда нужен?

---

Ответ:

Часто достаточно:

```sql
SELECT FOR UPDATE
```

---

# 10. Design News Feed

Очень похож на Instagram.

---

# Проверяют

```txt
Feed Generation

Ranking

Caching
```

---

# Follow-Up

Что станет bottleneck?

---

Ответ:

```txt
Database
```

---

# Решение

```txt
Redis

Read Replicas
```

---

# 11. Design Rate Limiter

Очень любят спрашивать.

---

# Проверяют

```txt
Redis

TTL

Counters
```

---

# Решение

```txt
Redis
 ↓
INCR
 ↓
TTL
```

---

# Follow-Up

Как сделать распределенный limiter?

---

Ответ:

```txt
Redis
```

---

# 12. Design Search System

Пример:

```txt
Google

Product Search
```

---

# Проверяют

```txt
Indexing

Full Text Search
```

---

# Архитектура

```txt
PostgreSQL
 ↓
Events
 ↓
Elasticsearch
```

---

# Follow-Up

Почему не PostgreSQL LIKE?

---

Ответ:

```txt
плохо масштабируется
```

---

# Самые любимые темы интервьюеров

Если обобщить все задачи.

---

Они почти всегда сводятся к:

```txt
Load Balancer

Redis

PostgreSQL

Queue

Workers

S3

CDN

WebSocket
```

---

# Самые частые Follow-Up вопросы

После любой задачи.

---

# Что станет bottleneck?

---

# Как масштабировать?

---

# Какой cache добавить?

---

# Как избежать потери данных?

---

# Что будет если база упадет?

---

# Как обеспечить high availability?

---

# Как обеспечить consistency?

---

# Самый сильный Senior ответ

После любой архитектуры.

---

Не говорить:

```txt
Вот правильное решение.
```

---

Говорить:

```txt
Это один из возможных вариантов.

Дальнейший выбор зависит от:

нагрузки

требований к latency

стоимости

availability

consistency
```

---

# Interview Cheat Sheet

Практически для любой задачи:

```txt
Requirements

↓

Scale Estimation

↓

API

↓

Data Model

↓

Load Balancer

↓

API

↓

Redis

↓

PostgreSQL

↓

Queue

↓

Workers

↓

S3/CDN

↓

Scaling

↓

Trade-Offs
```

---

# Финальная мысль

На Senior System Design интервью почти никогда не существует единственного правильного решения.

Интервьюер оценивает не набор технологий, а способность понимать требования, находить узкие места системы и принимать обоснованные архитектурные решения.