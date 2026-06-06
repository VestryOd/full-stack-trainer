<!-- verified: 2026-06-05, corrections: 0 -->
# Notification System Design

## Постановка задачи

Спроектировать систему уведомлений.

---

Примеры:

```txt
Email

Push Notifications

SMS

In-App Notifications
```

---

# Требования

Пользователь создал заказ.

---

Нужно отправить:

```txt
Email

Push

Internal Notification
```

---

# Ошибка новичков

Делать так:

```txt
Order Service
 ↓
Email Service
 ↓
Push Service
 ↓
SMS Service
```

---

# Почему плохо

Если Email Service упал:

```txt
Order Service падает
```

---

# Правильный подход

Через события.

---

```txt
Order Service
 ↓
Event
 ↓
Notification System
```

---

# Event Driven Architecture

После заказа публикуем:

```txt
Order Created
```

---

# Fan Out

Очень популярный вопрос.

---

Одно событие.

---

Много обработчиков.

---

```txt
Order Created
 ↓
Email

Push

Analytics

CRM
```

---

# Notification Service

```txt
API
 ↓
Queue
 ↓
Workers
```

---

# Почему очередь обязательна

Очень любят спрашивать.

---

Пользователь создал:

```txt
10000 заказов
```

---

Email сервис медленный.

---

Очередь сглаживает нагрузку.

---

# Типичная схема

```txt
Producer
 ↓
SQS
 ↓
Notification Workers
```

---

# Notification Table

```sql
notifications

id

user_id

type

status

created_at
```

---

# Статусы

```txt
Pending

Sent

Failed
```

---

# Retry

Очень важная тема.

---

Email сервис недоступен.

---

Повторяем:

```txt
1 min

5 min

15 min
```

---

# Dead Letter Queue

После нескольких ошибок.

---

```txt
Main Queue
 ↓
DLQ
```

---

# Иначе

Сообщение будет ломаться вечно.

---

# User Preferences

Очень любят спрашивать.

---

Пользователь может отключить:

```txt
Emails

SMS

Push
```

---

Таблица:

```sql
notification_preferences
```

---

# Push Notifications

Обычно:

```txt
Firebase Cloud Messaging

Apple Push Notification Service
```

---

# Email

Обычно:

```txt
SES

SendGrid

Mailgun
```

---

# SMS

Обычно:

```txt
Twilio
```

---

# In-App Notifications

Хранятся в БД.

---

Например:

```txt
Ваш заказ отправлен
```

---

# Realtime Notifications

Если пользователь онлайн.

---

```txt
Notification Service
 ↓
WebSocket
 ↓
Client
```

---

# Если пользователь оффлайн

Очень любят спрашивать.

---

Пишем:

```txt
Database
```

---

Потом показываем:

```txt
Unread Notifications
```

---

# Масштабирование

Очень просто.

---

Добавляем:

```txt
Workers
```

---

Количество воркеров растет независимо.

---

# Финальная архитектура

```txt
Order Service
 ↓
SNS
 ↓
SQS
 ↓
Notification Workers
```

---

Дальше:

```txt
Email

Push

SMS
```

---

Храним:

```txt
PostgreSQL
```

---

Кешируем:

```txt
Redis
```

---

# Частый вопрос

Почему уведомления через очередь?

Ответ:

Чтобы не блокировать основной бизнес-процесс.

---

# Частый вопрос

Зачем DLQ?

Ответ:

Чтобы изолировать сообщения, которые постоянно падают.

---

# Частый вопрос

Почему Event Driven Architecture хорошо подходит?

Ответ:

Потому что сервис создания заказа ничего не знает о способах доставки уведомлений.

---

# Частый вопрос

Как добавить новый канал уведомлений?

Ответ:

Добавить нового consumer'а события без изменения существующих сервисов.

---

# Interview Answer

Современная система уведомлений строится на Event Driven Architecture. Бизнес-сервис публикует события, которые попадают в очередь, а отдельные воркеры отвечают за доставку Email, Push, SMS и внутренних уведомлений. Такой подход обеспечивает слабую связанность, надежность и независимое масштабирование компонентов.