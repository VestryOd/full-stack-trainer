# NestJS Microservices

## Что такое микросервис

Очень популярный вопрос.

---

Микросервис — независимое приложение,
выполняющее ограниченный набор задач.

---

Пример.

---

Монолит:

```txt
Users
Orders
Payments
Notifications
```

---

В одном приложении.

---

# Microservices

Разделяем.

---

```txt
User Service

Order Service

Payment Service

Notification Service
```

---

Каждый сервис:

```txt
отдельный deploy

отдельный runtime

отдельная БД (часто)
```

---

# Почему появились микросервисы

Очень популярный вопрос.

---

Причины:

```txt
масштабирование

независимые релизы

разделение команд

отказоустойчивость
```

---

# Недостатки

Еще популярнее.

---

Появляются:

```txt
сетевая задержка

distributed transactions

eventual consistency

мониторинг

сложность разработки
```

---

# NestJS Microservices

Nest предоставляет отдельный слой.

---

Поддерживаются:

```txt
TCP

Redis

RabbitMQ

Kafka

NATS

gRPC
```

---

# Основная идея

Вместо:

```http
GET /users/1
```

---

Получаем:

```txt
Message
```

---

между сервисами.

---

# Message Pattern

Самая важная концепция.

---

Аналог:

```txt
Route
```

---

В HTTP.

---

Пример.

---

```ts
@MessagePattern(
 'get-user'
)
```

---

Сервис подписывается.

---

```ts
@MessagePattern(
 'get-user'
)

getUser(id: string) {

 ...
}
```

---

# Запрос

Клиент отправляет:

```txt
get-user
```

---

Nest вызывает:

```txt
handler
```

---

# Event Pattern

Следующая тема.

---

```ts
@EventPattern(
 'user-created'
)
```

---

Используется для событий.

---

# Главное отличие

Message Pattern:

```txt
Request / Response
```

---

Есть ответ.

---

# Event Pattern

```txt
Fire And Forget
```

---

Ответа нет.

---

# Пример

Message Pattern:

```txt
дай пользователя
```

---

Ждем ответ.

---

# Пример Event

```txt
пользователь создан
```

---

Никто ничего не возвращает.

---

Просто уведомляем систему.

---

# ClientProxy

Очень любят спрашивать.

---

Через него сервис
отправляет сообщения.

---

Пример:

```ts
constructor(
 @Inject('USER_SERVICE')
 private client:
 ClientProxy
) {}
```

---

# Request / Response

```ts
this.client.send(
 'get-user',
 userId
);
```

---

Получаем:

```txt
Observable
```

---

Очень важно.

---

Потому что под капотом:

```txt
сетевая операция
```

---

# Event

```ts
this.client.emit(
 'user-created',
 payload
);
```

---

Никто не отвечает.

---

# send vs emit

Очень популярный вопрос.

---

send:

```txt
Request/Response
```

---

emit:

```txt
Event
```

---

# Transport Layer

Nest скрывает детали транспорта.

---

Код одинаковый.

---

Можно использовать:

```txt
TCP
Kafka
RabbitMQ
```

---

Меняется только конфиг.

---

# TCP Transport

Самый простой.

---

Обычно используют:

```txt
локальная разработка

демо проекты
```

---

# RabbitMQ

Очень популярный брокер.

---

Плюсы:

```txt
очереди

acknowledgement

retry

routing
```

---

# Kafka

Очень популярный Senior вопрос.

---

Подходит для:

```txt
high throughput

event streaming

analytics
```

---

# gRPC

Очень часто используется.

---

Плюсы:

```txt
быстрее HTTP

protobuf

типизация
```

---

# Event Driven Architecture

Очень важная тема.

---

Пример.

---

```txt
Order Created
 ↓
Payment Service
 ↓
Notification Service
 ↓
Analytics Service
```

---

Все получают событие.

---

Никто не зависит напрямую.

---

# Saga Pattern

Очень любят спрашивать.

---

Проблема:

```txt
distributed transaction
```

---

Например:

```txt
Order

Payment

Delivery
```

---

Если Payment упал?

---

Нельзя сделать:

```sql
ROLLBACK
```

между сервисами.

---

Используют:

```txt
Compensating Actions
```

---

Это уже Saga.

---

# Когда микросервисы оправданы

Подходит:

```txt
большие команды

сложный домен

разные нагрузки
```

---

# Когда не нужны

Очень популярный вопрос.

---

Плохо:

```txt
небольшой CRUD проект
```

---

Монолит проще.

---

# Interview Answer

NestJS поддерживает микросервисную архитектуру через различные транспортные слои, включая TCP, RabbitMQ, Kafka и gRPC. Для Request/Response взаимодействия используется MessagePattern и ClientProxy.send(), а для событийной архитектуры — EventPattern и ClientProxy.emit(). Основное преимущество — слабая связанность сервисов и независимое масштабирование.