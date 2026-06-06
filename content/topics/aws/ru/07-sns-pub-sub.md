<!-- verified: 2026-06-05, corrections: 0 -->
# SNS и Pub/Sub Architecture

## Что такое SNS

SNS расшифровывается как:

```txt
Simple Notification Service
```

---

Это Pub/Sub сервис AWS.

---

# Главная идея

SQS:

```txt
Одно сообщение
 ↓
Один Consumer
```

---

SNS:

```txt
Одно событие
 ↓
Много подписчиков
```

---

# Queue vs Pub/Sub

Очень популярный вопрос.

---

SQS:

```txt
Producer
 ↓
Queue
 ↓
Consumer
```

---

Сообщение обычно обрабатывается
одним получателем.

---

# SNS

```txt
Producer
 ↓
Topic
 ↓
Subscriber A

Subscriber B

Subscriber C
```

---

Одно событие получают все подписчики.

---

# Topic

Самая важная сущность SNS.

---

Topic — канал публикации событий.

---

Например:

```txt
user-created
```

---

# Publish

Отправка события.

---

```txt
User Service
 ↓
SNS Topic
```

---

# Subscribe

Подписка на Topic.

---

```txt
Email Service

Analytics Service

CRM Service
```

---

Все получают одно событие.

---

# Flow

```txt
User Created
 ↓
SNS Topic
 ↓
Email

Analytics

CRM
```

---

# Почему SNS нужен

Очень любят спрашивать.

---

Без SNS:

```txt
User Service
 ↓
Email

 ↓
Analytics

 ↓
CRM
```

---

Жесткая связанность.

---

С SNS:

```txt
User Service
```

---

Не знает вообще,
кто слушает события.

---

# Типы подписчиков

SNS может отправлять события в:

```txt
SQS

Lambda

HTTP

Email

SMS
```

---

# SNS → Lambda

Очень популярная архитектура.

---

```txt
SNS Topic
 ↓
Lambda A

Lambda B

Lambda C
```

---

# SNS → SQS

Еще популярнее.

---

```txt
SNS
 ↓
SQS A

SQS B

SQS C
```

---

Каждая система получает свою очередь.

---

# Fan-Out Pattern

Самая популярная тема SNS.

---

Одно событие:

```txt
Order Created
```

---

Рассылается:

```txt
Billing

Email

Analytics

CRM
```

---

Это называется:

```txt
Fan-Out
```

---

# SQS vs SNS

Очень любят спрашивать.

---

SQS:

```txt
Queue
```

---

SNS:

```txt
Pub/Sub
```

---

SQS:

```txt
1 Consumer
```

---

SNS:

```txt
Many Consumers
```

---

# SNS + SQS

Самая популярная AWS архитектура.

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

Преимущества:

```txt
масштабирование

ретраи

буферизация

слабая связанность
```

---

# Delivery Guarantees

SNS также использует:

```txt
At Least Once Delivery
```

---

Поэтому подписчики должны быть:

```txt
idempotent
```

---

# Когда использовать SNS

Подходит:

```txt
Domain Events

Notifications

Fan-Out

Event Driven Architecture
```

---

# Когда не использовать

Если нужен:

```txt
один получатель
```

---

Тогда лучше:

```txt
SQS
```

---

# Частый вопрос

Чем SNS отличается от SQS?

Ответ:

SQS предназначена для очередей и обработки сообщений одним consumer. SNS реализует Pub/Sub модель, при которой одно событие доставляется множеству подписчиков.

---

# Частый вопрос

Что такое Fan-Out Pattern?

Ответ:

Архитектурный паттерн, при котором одно событие публикуется в SNS и автоматически доставляется нескольким независимым системам.

---

# Interview Answer

SNS является Pub/Sub сервисом AWS и используется для публикации событий множеству подписчиков. Центральным элементом является Topic, на который публикуются события. SNS часто используется вместе с SQS для построения масштабируемых event-driven систем.