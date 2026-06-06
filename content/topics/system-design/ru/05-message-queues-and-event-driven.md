<!-- verified: 2026-06-05, corrections: 0 -->
# Message Queues и Event Driven Architecture

## Почему очереди так популярны

Очень любят спрашивать.

---

Без очереди:

```txt
API
 ↓
Email Service
```

---

Если Email Service упал:

```txt
API падает
```

---

# Через очередь

```txt
API
 ↓
Queue
 ↓
Worker
```

---

API завершился успешно.

---

Сообщение осталось.

---

# Основные преимущества

```txt
Асинхронность

Буферизация

Ретраи

Масштабирование
```

---

# Producer

Создает сообщение.

---

# Consumer

Обрабатывает сообщение.

---

# Queue

Промежуточное хранилище.

---

# Пример

```txt
Order Created
 ↓
SQS
 ↓
Email Worker
```

---

# Почему это лучше

Создание заказа:

```txt
быстро
```

---

Email:

```txt
асинхронно
```

---

# Event Driven Architecture

Следующий уровень.

---

Сервис публикует событие.

---

Например:

```txt
User Created
```

---

# Fan Out

```txt
User Service
 ↓
Event
 ↓
Email

Analytics

CRM
```

---

# Pub/Sub

Много подписчиков.

---

Каждый получает событие.

---

# At Least Once Delivery

Очень популярный вопрос.

---

Сообщение может прийти:

```txt
несколько раз
```

---

# Поэтому

Consumer должен быть:

```txt
idempotent
```

---

# Dead Letter Queue

Сообщения которые постоянно падают.

---

```txt
Main Queue
 ↓
DLQ
```

---

# Когда использовать очередь

Подходит:

```txt
Emails

Notifications

Reports

Video Processing
```

---

# Когда не использовать

```txt
Realtime Chat

Realtime Gaming
```

---

# Interview Answer

Очереди позволяют разделить создание и обработку задач. Они повышают надежность системы, позволяют переживать временные сбои и независимо масштабировать нагрузку.