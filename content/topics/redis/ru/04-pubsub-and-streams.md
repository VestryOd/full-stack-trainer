<!-- verified: 2026-06-05, corrections: 0 -->
# Redis Pub/Sub и Streams

## Redis как Message Broker

Очень многие думают:

```txt
Redis = Cache
```

---

Но Redis также поддерживает:

```txt
Messaging
```

---

# Pub/Sub

Расшифровка:

```txt
Publish / Subscribe
```

---

Очень похож на:

```txt
SNS
```

---

# Идея

Publisher отправляет событие.

---

Subscriber получает событие.

---

# Схема

```txt
Publisher
 ↓
Channel
 ↓
Subscriber A

Subscriber B

Subscriber C
```

---

# Publish

```bash
PUBLISH orders
 "created"
```

---

# Subscribe

```bash
SUBSCRIBE orders
```

---

Теперь клиент получает сообщения.

---

# Где используют

```txt
Chat

Notifications

Live Updates

WebSockets
```

---

# Главный недостаток

Очень любят спрашивать.

---

Pub/Sub:

```txt
НЕ сохраняет сообщения
```

---

Если подписчик был отключен:

```txt
сообщение потеряно
```

---

# Пример

```txt
Message Sent
 ↓
Subscriber Offline
 ↓
Message Lost
```

---

# Поэтому Pub/Sub плох для

```txt
финансовых операций

заказов

критичных событий
```

---

# Redis Streams

Современное решение Redis.

---

Появилось в Redis 5.

---

Очень любят спрашивать.

---

# Главное отличие

Pub/Sub:

```txt
ephemeral
```

---

Streams:

```txt
persistent
```

---

Сообщения сохраняются.

---

# Пример

```bash
XADD orders *
 status created
```

---

Добавляем запись в Stream.

---

# Consumer

Читает:

```bash
XREAD
```

---

Сообщения.

---

# Stream

Похож на:

```txt
Kafka Lite
```

---

# Почему Streams лучше

Если consumer отключился:

```txt
ничего не потеряется
```

---

После восстановления:

```txt
прочитает старые сообщения
```

---

# Consumer Groups

Очень популярный вопрос.

---

Позволяют нескольким consumers:

```txt
делить нагрузку
```

---

Схема:

```txt
Orders Stream
 ↓
Consumer Group
 ↓
Worker 1

Worker 2

Worker 3
```

---

Каждое сообщение:

```txt
обрабатывается одним worker
```

---

# ACK

Очень важная тема.

---

После обработки:

```bash
XACK
```

---

Сообщение подтверждается.

---

# Если Worker умер

Очень любят спрашивать.

---

Сообщение:

```txt
остается pending
```

---

Другой worker может забрать его позже.

---

# Pub/Sub vs Streams

Самый популярный вопрос.

---

Pub/Sub:

```txt
очень быстро

просто

без хранения
```

---

Streams:

```txt
надежно

есть история

есть replay
```

---

# Streams vs Kafka

Senior вопрос.

---

Kafka:

```txt
распределенный лог

огромный throughput

кластеризация
```

---

Streams:

```txt
проще

меньше возможностей

меньше инфраструктуры
```

---

# Когда использовать Pub/Sub

Подходит:

```txt
Chat

Live Notifications

Realtime Updates
```

---

# Когда использовать Streams

Подходит:

```txt
Orders

Payments

Background Jobs

Reliable Messaging
```

---

# Частый вопрос

Почему Pub/Sub ненадежен?

Ответ:

Сообщения не сохраняются. Если подписчик был недоступен в момент публикации, сообщение теряется.

---

# Частый вопрос

Что такое Consumer Group?

Ответ:

Механизм Redis Streams, позволяющий группе consumers совместно обрабатывать сообщения и распределять нагрузку.

---

# Частый вопрос

Что выбрать для чата?

Ответ:

Pub/Sub.

---

# Частый вопрос

Что выбрать для обработки заказов?

Ответ:

Streams.

---

# Interview Answer

Redis поддерживает два основных механизма обмена сообщениями. Pub/Sub обеспечивает мгновенную доставку сообщений активным подписчикам, но не хранит историю. Redis Streams предоставляет надежную модель обмена сообщениями с хранением истории, подтверждением обработки и Consumer Groups.