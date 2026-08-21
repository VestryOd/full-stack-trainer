<!-- verified: 2026-06-05, corrections: 0 -->
# Система уведомлений

## Почему "напрямую" — антипаттерн, и что это значит на практике

```txt
❌ Order Service → Email Service → Push Service → SMS Service
   (синхронные вызовы)
```

Проблема не только в "Order Service упадёт, если Email Service недоступен" — это лишь следствие. Корневая проблема — **Order Service вынужден знать про все каналы доставки** и их API. Добавление нового канала требует изменения Order Service. Например, Slack-уведомления для B2B (business-to-business) клиентов — то есть для компаний, а не для частных пользователей.

Это прямое нарушение принципа из статьи про очереди сообщений: бизнес-сервис должен публиковать факт ("OrderCreated"), а не диктовать, что с этим фактом делать.

```txt
✅ Order Service публикует факт "OrderCreated"

┌──────────────────────────────────────────────────────────────┐
│ Event Bus, канал "OrderCreated"                              │
└──────────────────────────────────────────────────────────────┘
            ▼                       ▼                   ▼
┌──────────────────────┐  ┌───────────────────┐  ┌─────────────┐
│ Notification Service │  │ Analytics Service │  │ CRM Service │
└──────────────────────┘  └───────────────────┘  └─────────────┘
```

Это fan-out из статьи про очереди сообщений, применённый к конкретной задаче. Notification Service — лишь один из подписчиков. Добавить Slack-канал — значит добавить нового подписчика, без изменений в Order Service.

## Notification Service внутри: Decision Layer, а не просто "разослать"

Наивная реализация — "получили событие, отправили email, push и SMS (short message service, текстовое сообщение) всем сразу". В реальной системе есть промежуточный **decision layer** — слой решений. Он решает **что, кому, через какой канал и когда**:

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

Этот decision layer — то, что отличает "просто очередь с воркерами" от системы, которую реально обсуждают на senior-интервью.

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

OTP — это one-time password, одноразовый код для входа или подтверждения. GDPR — европейский закон о защите данных, CAN-SPAM — американский закон о коммерческой рассылке.

Путать эти две категории в одной таблице preferences, без разделения по типу, — частая ошибка дизайна. На практике она приводит либо к недоставке критичных уведомлений, либо к юридическим проблемам со спамом.

## Идемпотентность и дедупликация — at-least-once в действии

Event Bus обычно даёт доставку at-least-once, как разобрано в статье про очереди сообщений. Значит, одно и то же событие "OrderCreated" может быть обработано **дважды**.

```ts
import { db } from './db'; // уже созданный PrismaClient

interface OrderCreatedEvent { eventId: string; userId: string; orderId: string }

declare function sendEmail(
  userId: string,
  subject: string,
  body: string,
): Promise<void>;

// ❌ При повторной обработке события пользователь получит 2 одинаковых email
async function handleOrderCreated(event: OrderCreatedEvent) {
  const body = `Order ${event.orderId} is confirmed`;
  await sendEmail(event.userId, 'Order confirmed', body);
}

// ✅ Идемпотентность через notification_id, привязанный к (eventId, channel, type)
async function handleOrderCreatedIdempotent(event: OrderCreatedEvent) {
  const notificationId = `${event.eventId}:email:order_confirmation`;

  const existing = await db.notifications.findUnique({ where: { id: notificationId } });
  if (existing) return; // уже отправлено или в процессе — no-op

  await db.notifications.create({
    data: { id: notificationId, userId: event.userId, status: 'pending', channel: 'email' },
  });

  const body = `Order ${event.orderId} is confirmed`;
  await sendEmail(event.userId, 'Order confirmed', body);
  await db.notifications.update({
    where: { id: notificationId },
    data: { status: 'sent' },
  });
}
```

Это та же проблема и то же решение, что в статье про очереди сообщений. Отличие — в заметности: "дубликат email" виден пользователю гораздо лучше, чем "дубликат записи в аналитике". Именно поэтому интервьюеры любят проверять, дойдёт ли кандидат до этого в контексте уведомлений.

## Retry, Backoff и DLQ — применительно к внешним провайдерам

DLQ — это dead letter queue, очередь, куда сообщение попадает после того, как все повторные попытки провалились.

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

Это применение паттерна "устранение SPOF" к внешним зависимостям. SPOF — это single point of failure, единая точка отказа; сам паттерн разобран в статье про основы System Design. SES выше — это Amazon Simple Email Service, провайдер, взятый здесь как резервный.

Допустим, весь Notification Service завязан на единственного email-провайдера, без абстракции над ним. Тогда инцидент у этого провайдера останавливает доставку всех транзакционных писем, а для OTP-кодов это критично. А у крупных email-провайдеров случаются деградации на несколько часов.

## Delivery Tracking — webhooks от провайдеров

```txt
SES/SendGrid отправляют webhook-события обратно в систему:
  - delivered
  - bounced (адрес не существует)
  - opened / clicked (для маркетинговых писем)
  - complained (помечено как спам)

Notification Service принимает эти webhook-события → обновляет
status в таблице notifications → "complained" триггерит
автоматическое отключение этого канала для пользователя
```

Без этого цикла обратной связи статус "sent" означает только "мы передали провайдеру". Он не означает "пользователь получил". Разница важна и для compliance, и для алертинга: "почему у нас 40% отказов доставки на новых регистрациях — возможно, баг в форме регистрации".

## Realtime (In-App) vs Push vs Email/SMS — выбор канала исходя из контекста пользователя

```txt
Пользователь online (открытое WebSocket-соединение):
  → доставка через WebSocket мгновенно, In-App notification
    появляется без перезагрузки

Пользователь offline:
  → in-app notification сохраняется в БД (непрочитанная),
    появится при следующем входе
  → ЕСЛИ критично — дополнительно push через FCM/APNs
  → ЕСЛИ очень критично и push не сработал — SMS как fallback
```

Это решение принимается в decision layer. Оно зависит от двух вещей: от presence-статуса пользователя, который лежит в Redis, и от важности конкретного уведомления. Не каждое уведомление заслуживает SMS, даже если push не доставлен. Presence в Redis разобран в статье про системы реального времени.

## Финальная архитектура

Путь от бизнес-события до доставленного уведомления состоит из пяти шагов:

1. Бизнес-сервисы (Order, Auth и другие) публикуют событие в Event Bus. Эта шина — Kafka или Amazon SNS (Simple Notification Service).
2. Notification Service выполняет decision layer: preferences, дедупликация, rate limiting, приоритеты.
3. Результат попадает в очередь своего канала.
4. Воркер этого канала отправляет уведомление через провайдера канала. Для push это FCM (Firebase Cloud Messaging, сервис Google) или APNs (Apple Push Notification service).
5. Провайдеры присылают webhook о доставке, а таблица `notifications` хранит статус.

По одной строке на канал — шаги 3 и 4 рядом:

| Канал | Очередь | Воркер | Через что уходит |
|---|---|---|---|
| Email | Email Queue | Email Worker | Amazon SES или SendGrid |
| Push | Push Queue | Push Worker | FCM или APNs |
| SMS | SMS Queue | SMS Worker | Twilio |
| In-App | In-App Queue | WebSocket/запись в базу | WebSocket, если online; запись в базе, если offline |

Webhook о доставке приходят от трёх внешних каналов: email, push и SMS. In-App в них не нуждается, потому что этот канал система доставляет сама.

## Типичные ошибки на интервью

- **Останавливаться на "событие → очередь → воркеры".** Это база. А отличает поверхностный ответ от глубокого именно decision layer: preferences, дедупликация, приоритеты, rate limiting и дайджесты.

- **Не различать транзакционные и маркетинговые уведомления** — у них принципиально разные требования к возможности отключения и compliance.

- **Не упоминать идемпотентность при доставке at-least-once.** "Пользователь получил один и тот же email дважды" — конкретный, легко представимый баг. Интервьюер ждёт, что вы назовёте его как риск.

- **Retry без учёта природы ошибки** — бесконечно повторять отправку на невалидный email или номер вместо того, чтобы сразу помечать её permanently failed.

- **Единственный провайдер без абстракции и резервного варианта** — не упоминать, что инцидент у внешнего email- или SMS-провайдера полностью останавливает канал.

- **"Sent" = "доставлено".** Подтверждение доставки приходит асинхронно, через webhook от провайдера. Без него нельзя отличить "отправлено" от "получено пользователем".

- **Игнорировать rate limiting и объединение в дайджест.** Пользователь, который получил 20 push-уведомлений за час из-за активности в одном треде, отключит уведомления совсем. Дайджест — часть архитектуры, а не деталь оформления интерфейса.
