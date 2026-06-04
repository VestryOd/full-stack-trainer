# Universal System Design Interview Framework

## Самая важная мысль

На интервью оценивают не архитектуру.

---

Оценивают:

```txt
ход мыслей
```

---

Интервьюер хочет увидеть:

```txt
структурированное мышление

понимание компромиссов

умение масштабировать систему
```

---

# Главная ошибка

Кандидат сразу начинает рисовать:

```txt
Redis

Kafka

PostgreSQL

Load Balancer
```

---

Не разобравшись в задаче.

---

# Правильный порядок

Всегда:

```txt
1 Requirements

2 Scale

3 API

4 Data Model

5 High Level Design

6 Bottlenecks

7 Scaling
```

---

# Шаг 1

Уточняем требования.

---

Очень любят смотреть на это.

---

# Functional Requirements

Что система должна делать.

---

Пример чата:

```txt
Send Messages

Receive Messages

Group Chats
```

---

# Functional Requirements

Для URL Shortener:

```txt
Create Short URL

Redirect

Analytics
```

---

# Non Functional Requirements

Очень важно.

---

Например:

```txt
Latency

Availability

Consistency

Durability
```

---

# Пример

Чат:

```txt
Latency критична
```

---

Банк:

```txt
Consistency критична
```

---

# Шаг 2

Оценка масштаба.

---

Очень любят спрашивать.

---

# Пример

```txt
10M users

1M DAU
```

---

# Считаем

Например:

```txt
100 req/sec

1000 req/sec

10000 req/sec
```

---

# Зачем

Понять:

```txt
одного сервера хватит?

или нужен кластер?
```

---

# Часто достаточно грубой оценки

Интервьюер не ждет точной математики.

---

# Шаг 3

Определяем API.

---

Пример:

```http
POST /messages

GET /messages
```

---

Или:

```http
POST /short-url

GET /{code}
```

---

# Шаг 4

Проектируем данные.

---

Очень важный этап.

---

# Таблицы

Например:

```sql
users

messages

chats
```

---

Или:

```sql
urls

analytics
```

---

# Интервьюер хочет увидеть

Что ты умеешь моделировать данные.

---

# Шаг 5

High Level Design

---

Теперь рисуем архитектуру.

---

Самый частый шаблон.

---

```txt
Client
 ↓
Load Balancer
 ↓
API
 ↓
Cache
 ↓
Database
```

---

# Или

```txt
Client
 ↓
API
 ↓
Queue
 ↓
Workers
```

---

# Или

```txt
Client
 ↓
WebSocket
 ↓
Redis
 ↓
Database
```

---

# Не усложняй

Очень важное правило.

---

Начинай:

```txt
с простого решения
```

---

Потом масштабируй.

---

# Шаг 6

Находим Bottlenecks

---

Самый любимый вопрос.

---

Интервьюер почти всегда спросит:

```txt
Что сломается первым?
```

---

Типичные ответы:

```txt
Database

Network

File Storage

WebSocket Connections
```

---

# Database

Самый частый bottleneck.

---

Решение:

```txt
Cache

Read Replicas

Sharding
```

---

# API

Следующий bottleneck.

---

Решение:

```txt
Horizontal Scaling
```

---

# File Storage

Решение:

```txt
S3

CDN
```

---

# Шаг 7

Масштабирование

---

Очень любят спрашивать.

---

# Stateless Services

Первый ответ почти всегда.

---

```txt
JWT

Redis

Database
```

---

Вместо Session Memory.

---

# Read Scaling

Используем:

```txt
Read Replicas
```

---

# Heavy Computation

Используем:

```txt
Queue
 ↓
Workers
```

---

# Static Content

Используем:

```txt
CDN
```

---

# Realtime

Используем:

```txt
WebSockets
```

---

# Часто встречающиеся компоненты

## Redis

Когда нужен?

---

```txt
Cache

Sessions

Presence

Rate Limiting
```

---

## Queue

Когда нужна?

---

```txt
Emails

Notifications

Reports

Background Jobs
```

---

## S3

Когда нужен?

---

```txt
Images

Videos

Documents
```

---

## CDN

Когда нужен?

---

```txt
Static Content
```

---

## WebSocket

Когда нужен?

---

```txt
Realtime
```

---

# Очень важный раздел

Trade-Offs

---

Senior вопрос.

---

Нельзя говорить:

```txt
это лучше
```

---

Нужно говорить:

```txt
это компромисс
```

---

# Пример

Redis.

---

Плюсы:

```txt
быстро
```

---

Минусы:

```txt
инвалидация кеша

сложность
```

---

# Пример

Microservices.

---

Плюсы:

```txt
масштабирование
```

---

Минусы:

```txt
сложность
```

---

# Пример

Event Driven Architecture.

---

Плюсы:

```txt
слабая связанность
```

---

Минусы:

```txt
сложнее дебаг
```

---

# Самая частая структура ответа

```txt
Requirements

↓

Scale Estimation

↓

API Design

↓

Data Model

↓

High Level Design

↓

Bottlenecks

↓

Scaling

↓

Trade-Offs
```

---

# Универсальная архитектура

Для большинства задач.

---

```txt
Users
 ↓
Load Balancer
 ↓
API Servers
 ↓
Redis
 ↓
PostgreSQL

Queue
 ↓
Workers

S3
 ↓
CDN
```

---

# Частый вопрос

Что делать если PostgreSQL перестал справляться?

Ответ:

```txt
Redis

Read Replicas

Sharding
```

---

# Частый вопрос

Что делать если API долго отвечает?

Ответ:

Найти bottleneck.

---

Обычно:

```txt
DB

External API

Heavy Computation
```

---

# Частый вопрос

Как показать Senior уровень?

Ответ:

Обсуждать:

```txt
Trade-Offs

Consistency

Availability

Scalability
```

---

# Самый сильный ответ на интервью

Когда интервьюер спрашивает:

"Какую архитектуру выберешь?"

---

Ответ:

```txt
Это зависит от требований.

Я бы сначала уточнил нагрузку,
требования к latency,
availability и consistency,
а затем выбрал архитектуру,
исходя из этих ограничений.
```

---

# Interview Answer

Любую задачу по System Design стоит решать по одинаковому алгоритму: сначала уточнить требования, затем оценить масштаб, спроектировать API и модель данных, построить базовую архитектуру, найти потенциальные узкие места и только после этого обсуждать масштабирование и компромиссы решений.