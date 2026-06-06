<!-- verified: 2026-06-05, corrections: 0 -->
# Chat System Design

## Постановка задачи

Спроектировать чат наподобие:

```txt
Telegram

WhatsApp

Slack

Messenger
```

---

# Шаг 1. Уточняем требования

Очень важно.

---

# Functional Requirements

```txt
1-on-1 chat

Group chat

Message history

Online status

Read receipts

Typing indicator
```

---

# Non Functional Requirements

```txt
Realtime delivery

High availability

Low latency

Millions of users
```

---

# Базовая архитектура

```txt
Client
 ↓
WebSocket Gateway
 ↓
Chat Service
 ↓
Database
```

---

# Почему HTTP не подходит

Очень любят спрашивать.

---

Если использовать HTTP:

```txt
GET messages
GET messages
GET messages
```

---

Получаем Polling.

---

Много лишнего трафика.

---

# Решение

WebSocket.

---

```txt
Client
 ↕
 Server
```

---

Постоянное соединение.

---

# Отправка сообщения

Flow:

```txt
User A
 ↓
WebSocket
 ↓
Chat Service
 ↓
Database
 ↓
User B
```

---

# Нужно ли сначала сохранять сообщение?

Очень любят спрашивать.

---

Да.

---

Правильный порядок:

```txt
Save Message
 ↓
ACK Sender
 ↓
Deliver Receiver
```

---

# Почему

Если сервер упадет:

```txt
сообщение не потеряется
```

---

# Хранение сообщений

Самый частый вопрос.

---

Чаще всего:

```txt
PostgreSQL

или

MongoDB
```

---

# PostgreSQL

Подходит если:

```txt
сложные запросы

фильтрация

поиск
```

---

# MongoDB

Подходит если:

```txt
огромный объем сообщений
```

---

# Таблица сообщений

```sql
messages

id

chat_id

sender_id

text

created_at
```

---

# Как узнать кто онлайн

Очень популярный вопрос.

---

Не храним это в PostgreSQL.

---

Используем:

```txt
Redis
```

---

Например:

```txt
online:user:123
```

---

С TTL.

---

# Typing Indicator

```txt
User typing...
```

---

Обычно:

```txt
НЕ сохраняется
```

---

В БД.

---

Передается через:

```txt
WebSocket Event
```

---

# Read Receipts

Очень любят спрашивать.

---

```txt
Seen

Delivered

Read
```

---

Хранятся в БД.

---

Например:

```sql
message_status
```

---

# Масштабирование

Самый популярный Senior вопрос.

---

Есть:

```txt
10 Chat Servers
```

---

Пользователь А:

```txt
Server #2
```

---

Пользователь Б:

```txt
Server #8
```

---

Как доставить сообщение?

---

# Решение

Redis Pub/Sub.

---

```txt
Server 2
 ↓
Redis
 ↓
Server 8
 ↓
User B
```

---

# Еще лучше

```txt
Kafka
```

---

Для очень больших систем.

---

# Offline Users

Очень любят спрашивать.

---

Если пользователь не онлайн:

```txt
сохраняем сообщение
```

---

В БД.

---

При входе:

```txt
загружаем историю
```

---

# Push Notifications

Если приложение закрыто:

```txt
APNS

FCM
```

---

# Групповые чаты

Отдельная таблица.

---

```sql
chat_members

chat_id

user_id
```

---

# Финальная архитектура

```txt
Users
 ↓
Load Balancer
 ↓
WebSocket Servers
 ↓
Redis Pub/Sub
 ↓
Chat Service
 ↓
PostgreSQL
```

---

Для Push:

```txt
Chat Service
 ↓
Notification Queue
 ↓
Push Worker
 ↓
FCM/APNS
```

---

# Частый вопрос

Почему Redis нужен в чате?

Ответ:

Для Presence, Pub/Sub и быстрого хранения временных данных.

---

# Частый вопрос

Почему сообщения сохраняют до доставки?

Ответ:

Чтобы не потерять данные при сбое.

---

# Частый вопрос

Почему WebSocket?

Ответ:

Потому что сервер может мгновенно отправлять сообщения клиенту.

---

# Interview Answer

Современный чат обычно строится на WebSocket соединениях, PostgreSQL или MongoDB для хранения сообщений, Redis для Presence и Pub/Sub, а также очередях для отправки push-уведомлений. Основная задача архитектуры — обеспечить надежную доставку сообщений и возможность горизонтального масштабирования.