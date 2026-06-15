<!-- verified: 2026-06-05, corrections: 0 -->
# Notification System Design

## Почему "напрямую" — антипаттерн, и что это значит на практике

```txt
❌ Order Service → Email Service → Push Service → SMS Service
   (синхронные вызовы)
```

Проблема не только в "Order Service упадёт, если Email Service недоступен" — это лишь следствие. Корневая проблема — **Order Service вынужден знать про все каналы доставки** и их API. Добавление нового канала (например, Slack-уведомления для B2B-клиентов) требует изменения Order Service. Это прямое нарушение принципа из [Message Queues]: бизнес-сервис должен публиковать факт ("OrderCreated"), а не диктовать, что с этим фактом делать.

```txt
✅ Order Service → publishes "OrderCreated" → Event Bus
                                                  │
                          ┌───────────────────────┼───────────────────┐
                          ▼                       ▼                   ▼
                  Notification Service      Analytics Service    CRM Service
```

Это fan-out из [Message Queues], применённый к конкретной задаче. Notification Service — лишь один из подписчиков; добавление Slack-канала — это новый consumer, не требующий изменений в Order Service.

## Notification Service внутри: Decision Layer, а не просто "разослать"

Наивная реализация — "получили событие, отправили email+push+sms всем сразу". Реальная система имеет промежуточный **decision layer**, который решает **что, кому, через какой канал и когда**:

```txt
Event "OrderCreated" { userId, orderId, ... }
        ↓
Decision Layer:
  1. User Preferences — пользователь отключил SMS? → убрать SMS из списка
  2. Notification Type Rules — "OrderCreated" критично →
     даже если push отключён глобально, доставить хотя бы in-app
  3. Channel Priority — для критичных уведомлений: push → если
     не доставлено за N минут → SMS как fallback
  4. Rate Limiting / Batching — у пользователя уже было 5 уведомлений
     за последний час? → объединить в дайджест вместо 6-го отдельного
        ↓
Per-channel Queue (Email Queue, Push Queue, SMS Queue, In-App Queue)
        ↓
Channel-specific Workers
```

Этот decision layer — то, что отличает "просто очередь с воркерами" (старая версия статьи) от системы, которую реально обсуждают на senior-интервью.

## User Preferences — не просто on/off

```sql
notification_preferences (
  user_id, notification_type, channel, enabled
)
-- Пример: (user_42, 'order_updates', 'sms', false)
--         (user_42, 'order_updates', 'push', true)
--         (user_42, 'marketing', 'email', false)
```

Senior-нюанс: разные **типы** уведомлений (транзакционные vs маркетинговые) должны обрабатываться по-разному на уровне политики, а не только пользовательских предпочтений:

```txt
Транзакционные (OTP-коды, подтверждение заказа, алерты безопасности):
  - пользователь НЕ может полностью отключить (или отключение
    ограничено: можно выключить email, но не security-алерты)
  - юридические/compliance требования часто диктуют доставку

Маркетинговые (промо, дайджесты):
  - полностью управляются пользователем (opt-in/opt-out)
  - часто требуют explicit consent (GDPR/CAN-SPAM)
```

Путать эти категории в одной таблице preferences без разделения по типу — частая ошибка дизайна, которая на практике приводит либо к недоставке критичных уведомлений, либо к юридическим проблемам со спамом.

## Идемпотентность и дедупликация — at-least-once в действии

Event Bus (как обсуждалось в [Message Queues]) обычно даёт at-least-once доставку — то же событие "OrderCreated" может быть обработано **дважды**.

```ts
// ❌ При повторной обработке события пользователь получит 2 одинаковых email
async function handleOrderCreated(event: OrderCreatedEvent) {
  await sendEmail(event.userId, 'Order confirmed', ...);
}

// ✅ Идемпотентность через notification_id, привязанный к (eventId, channel, type)
async function handleOrderCreatedIdempotent(event: OrderCreatedEvent) {
  const notificationId = `${event.eventId}:email:order_confirmation`;

  const existing = await db.notifications.findUnique({ where: { id: notificationId } });
  if (existing) return; // уже отправлено или в процессе — no-op

  await db.notifications.create({
    data: { id: notificationId, userId: event.userId, status: 'pending', channel: 'email' },
  });

  await sendEmail(event.userId, 'Order confirmed', ...);
  await db.notifications.update({ where: { id: notificationId }, data: { status: 'sent' } });
}
```

Это та же проблема и решение, что и в [Message Queues] — отличие лишь в том, что "дубликат email" заметнее пользователю, чем "дубликат записи в аналитике", поэтому интервьюеры особенно любят проверять, додумает ли кандидат до этого в контексте уведомлений.

## Retry, Backoff и DLQ — применительно к внешним провайдерам

```txt
Email Worker → SES API → timeout/5xx

Retry с exponential backoff: 1min, 5min, 15min, 1h
После N попыток → Dead Letter Queue → алерт on-call
```

Senior-нюанс, который часто упускают: **retry должен быть осторожен с природой ошибки**.

```txt
Временная ошибка (5xx, timeout, rate limit от провайдера):
  → retry имеет смысл

Постоянная ошибка (невалидный email-адрес, номер телефона
заблокирован, пользователь отписался у провайдера — "hard bounce"):
  → retry БЕССМЫСЛЕН и может навредить (повторные попытки
     отправки на невалидный адрес повышают spam score
     отправителя у email-провайдеров)
  → должно сразу попадать в DLQ/помечаться как permanently failed,
     желательно с автоматическим обновлением notification_preferences
     (отключить email для этого пользователя)
```

## Multi-Provider и Failover для внешних сервисов

```txt
Email Worker:
  Primary: SendGrid
  Fallback: AWS SES (если SendGrid недоступен/rate-limited)

Абстракция:
  interface EmailProvider {
    send(to: string, subject: string, body: string): Promise<SendResult>;
  }
```

Это применение паттерна "устранение SPOF" из [System Design Fundamentals] к внешним зависимостям: если весь Notification Service завязан на единственного email-провайдера без абстракции, его инцидент (а у крупных email-провайдеров случаются многочасовые деградации) останавливает доставку всех транзакционных писем — для OTP-кодов это критично.

## Delivery Tracking — webhooks от провайдеров

```txt
SES/SendGrid отправляют webhook-события обратно в систему:
  - delivered
  - bounced (адрес не существует)
  - opened / clicked (для маркетинговых писем)
  - complained (помечено как спам)

Notification Service принимает эти webhook'и → обновляет
status в таблице notifications → "complained" триггерит
автоматическое отключение этого канала для пользователя
```

Без этого цикла обратной связи статус "sent" — это "мы передали провайдеру", а не "пользователь получил" — разница, которая имеет значение для compliance и для алертинга ("почему у нас 40% bounce rate на новых регистрациях — возможно, баг в форме регистрации email").

## Realtime (In-App) vs Push vs Email/SMS — выбор канала исходя из контекста пользователя

```txt
Пользователь online (открытое WebSocket-соединение, см. [WebSockets]):
  → доставка через WebSocket мгновенно, In-App notification
    появляется без перезагрузки

Пользователь offline:
  → in-app notification сохраняется в БД (непрочитанная),
    появится при следующем входе
  → ЕСЛИ критично — дополнительно push через FCM/APNs
  → ЕСЛИ очень критично и push не сработал — SMS как fallback
```

Это решение принимается на уровне decision layer и зависит как от presence-статуса пользователя (Redis, см. [WebSockets]), так и от важности конкретного уведомления — не каждое уведомление заслуживает SMS, даже если push не доставлен.

## Финальная архитектура

```txt
Business Services (Order, Auth, ...) → Event Bus (SNS/Kafka)
                                            ↓
                                  Notification Service
                                  (Decision Layer:
                                   preferences, dedup,
                                   rate limiting, priority)
                                            ↓
                ┌──────────────┬───────────┼──────────────┐
                ▼              ▼            ▼              ▼
          Email Queue    Push Queue    SMS Queue     In-App Queue
                ↓              ↓            ↓              ↓
          Email Worker   Push Worker   SMS Worker   WebSocket/DB
          (SES/SendGrid) (FCM/APNs)    (Twilio)
                ↓              ↓            ↓
          ←──────────── Delivery webhooks ────────────→
                                ↓
                      notifications table (status tracking)
```

## Типичные ошибки на интервью

- **Останавливаться на "событие → очередь → воркеры"** — это база, но decision layer (preferences, дедупликация, приоритеты, rate limiting/digest) — то, что отличает поверхностный ответ от глубокого.

- **Не различать транзакционные и маркетинговые уведомления** — у них принципиально разные требования к возможности отключения и compliance.

- **Не упоминать идемпотентность при at-least-once доставке событий** — "пользователь получил один и тот же email дважды" — конкретный, легко представимый баг, который интервьюер ждёт услышать как риск.

- **Retry без учёта природы ошибки** — повторять отправку на невалидный email/номер бесконечно вместо немедленной маркировки как permanently failed.

- **Единственный провайдер без abstraction/fallback** — не упоминать, что инцидент у внешнего email/SMS-провайдера полностью останавливает канал.

- **"Sent" = "доставлено"** — не учитывать, что подтверждение доставки приходит асинхронно через webhook от провайдера, и без этого нельзя отличить "отправлено" от "получено пользователем".

- **Игнорировать rate limiting/batching** — пользователь, получающий 20 push-уведомлений за час из-за активности в одном треде, отключит уведомления вообще; дайджест — часть архитектуры, а не "фича для дизайна UI".
