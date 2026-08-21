# Notification System Design

## Why "direct calls" is an anti-pattern, and what that means in practice

```txt
❌ Order Service → Email Service → Push Service → SMS Service
   (synchronous calls)
```

The problem isn't just "Order Service goes down if Email Service is unavailable" — that's only a symptom. The root problem is that **Order Service has to know about every delivery channel** and its API. Adding a new channel means changing Order Service. An example is Slack notifications for B2B (business-to-business) customers — companies rather than consumers.

This directly violates the principle from the Message Queues article: a business service should publish a fact ("OrderCreated"), not dictate what happens with that fact.

```txt
✅ Order Service publishes the fact "OrderCreated"

┌──────────────────────────────────────────────────────────────┐
│ Event Bus, the "OrderCreated" channel                        │
└──────────────────────────────────────────────────────────────┘
            ▼                       ▼                   ▼
┌──────────────────────┐  ┌───────────────────┐  ┌─────────────┐
│ Notification Service │  │ Analytics Service │  │ CRM Service │
└──────────────────────┘  └───────────────────┘  └─────────────┘
```

This is the fan-out from the Message Queues article, applied to a specific problem. The Notification Service is just one subscriber. Adding a Slack channel means adding a new consumer, with no changes to Order Service.

## Inside the Notification Service: a Decision Layer, not just "send everything"

A naive implementation is "got the event, sent email, push and SMS (short message service, a text message) to everyone at once". A real system has an intermediate **decision layer**. It decides **what, to whom, through which channel, and when**:

```txt
Event "OrderCreated" { userId, orderId, ... }
        ↓
Decision Layer:
  1. User Preferences — did the user disable SMS? → drop SMS from the list
  2. Notification Type Rules — "OrderCreated" is critical →
     even if push is globally disabled, deliver at least in-app
  3. Channel Priority — for critical notifications: push → if
     not delivered within N minutes → SMS as a fallback
  4. Rate Limiting / Batching — has the user already had 5
     notifications in the last hour? → merge them into a digest
     instead of sending a 6th separate one
        ↓
Per-channel Queue (Email Queue, Push Queue, SMS Queue, In-App Queue)
        ↓
Channel-specific Workers
```

This decision layer is what separates "just a queue with workers" from a system that is actually discussed in senior interviews.

## User Preferences — more than just on/off

```sql
notification_preferences (
  user_id, notification_type, channel, enabled
)
-- Example: (user_42, 'order_updates', 'sms', false)
--          (user_42, 'order_updates', 'push', true)
--          (user_42, 'marketing', 'email', false)
```

Senior nuance: different **types** of notifications (transactional vs marketing) need different policy handling, not just user preferences:

```txt
Transactional (OTP codes, order confirmation, security alerts):
  - the user CANNOT fully disable them (or disabling is limited:
    can turn off email, but not security alerts)
  - legal/compliance requirements often mandate delivery

Marketing (promos, digests):
  - fully controlled by the user (opt-in/opt-out)
  - often require explicit consent (GDPR/CAN-SPAM)
```

OTP means one-time password — the short code sent for login or confirmation. GDPR is the European data-protection law, and CAN-SPAM is the United States law on commercial email.

Mixing these two categories in a single preferences table, with no separation by type, is a common design mistake. In practice it leads either to critical notifications not being delivered, or to legal problems around spam.

## Idempotency and deduplication — at-least-once in action

The Event Bus typically provides at-least-once delivery, as discussed in the Message Queues article. That means the same "OrderCreated" event can be processed **twice**.

```ts
import { db } from './db'; // an already created PrismaClient

interface OrderCreatedEvent { eventId: string; userId: string; orderId: string }

declare function sendEmail(
  userId: string,
  subject: string,
  body: string,
): Promise<void>;

// ❌ On reprocessing, the user gets 2 identical emails
async function handleOrderCreated(event: OrderCreatedEvent) {
  const body = `Order ${event.orderId} is confirmed`;
  await sendEmail(event.userId, 'Order confirmed', body);
}

// ✅ Idempotency via a notification_id tied to (eventId, channel, type)
async function handleOrderCreatedIdempotent(event: OrderCreatedEvent) {
  const notificationId = `${event.eventId}:email:order_confirmation`;

  const existing = await db.notifications.findUnique({ where: { id: notificationId } });
  if (existing) return; // already sent or in progress — no-op

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

This is the same problem, and the same solution, as in the Message Queues article. The difference is visibility: "a duplicate email" is far more obvious to the user than "a duplicate analytics record". That is exactly why interviewers like to check whether a candidate reaches this point in a notifications context.

## Retry, Backoff, and DLQ — applied to external providers

DLQ stands for dead letter queue: where a message lands after every retry has failed.

```txt
Email Worker → SES API → timeout/5xx

Retry with exponential backoff: 1min, 5min, 15min, 1h
After N attempts → Dead Letter Queue → on-call alert
```

A senior nuance that's often missed: **retries need to be aware of the error's nature**.

```txt
Transient error (5xx, timeout, rate limit from the provider):
  → retry makes sense

Permanent error (invalid email address, phone number blocked,
the user unsubscribed at the provider level — a "hard bounce"):
  → retrying is POINTLESS and can be harmful (repeated sends
     to an invalid address raise the sender's spam score
     with email providers)
  → should go straight to DLQ/be marked permanently failed,
     ideally with an automatic update to notification_preferences
     (disable email for this user)
```

## Multi-Provider and Failover for external services

```txt
Email Worker:
  Primary: SendGrid
  Fallback: AWS SES (if SendGrid is down/rate-limited)

Abstraction:
  interface EmailProvider {
    send(to: string, subject: string, body: string): Promise<SendResult>;
  }
```

This applies the "eliminating SPOF" pattern to external dependencies. SPOF means single point of failure, and the System Design Fundamentals article covers the pattern. Amazon SES above is Simple Email Service, the provider used here as the fallback.

Suppose the whole Notification Service depends on one email provider, with no abstraction over it. An incident on that provider's side then halts delivery of every transactional email, which is critical for OTP codes. And major email providers do have degradations lasting hours.

## Delivery Tracking — webhooks from providers

```txt
SES/SendGrid send webhook events back to the system:
  - delivered
  - bounced (address doesn't exist)
  - opened / clicked (for marketing emails)
  - complained (marked as spam)

The Notification Service receives these webhooks → updates
the status in the notifications table → "complained" triggers
automatic disabling of that channel for the user
```

Without this feedback loop, "sent" only means "we handed it to the provider". It does not mean "the user received it". That difference matters for compliance and for alerting: "why is our bounce rate 40% on new signups — maybe a bug in the signup form".

## Realtime (In-App) vs Push vs Email/SMS — choosing a channel based on user context

```txt
User is online (an open WebSocket connection):
  → delivery via WebSocket is instant, the In-App notification
    appears without a reload

User is offline:
  → the in-app notification is saved to the DB (unread),
    will appear on the next login
  → IF critical, also send push via FCM/APNs
  → IF very critical and push didn't land, SMS as a fallback
```

This decision is made in the decision layer. It depends on two things: the user's presence status, kept in Redis, and how important this particular notification is. Not every notification deserves an SMS, even if a push fails. The WebSockets and Realtime Systems article covers presence in Redis.

## Final architecture

The path from a business event to a delivered notification has five steps:

1. Business services (Order, Auth, and so on) publish an event to the Event Bus. That bus is Kafka, or Amazon SNS — Simple Notification Service.
2. The Notification Service runs the decision layer: preferences, deduplication, rate limiting, priority.
3. The result goes into a per-channel queue.
4. A worker for that channel sends it through the channel's provider. For push that provider is FCM (Firebase Cloud Messaging, from Google) or APNs (Apple Push Notification service).
5. Providers send delivery webhooks back, and the `notifications` table keeps the status.

One row per channel, steps 3 and 4 side by side:

| Channel | Queue | Worker | Sends through |
|---|---|---|---|
| Email | Email Queue | Email Worker | Amazon SES or SendGrid |
| Push | Push Queue | Push Worker | FCM or APNs |
| SMS | SMS Queue | SMS Worker | Twilio |
| In-App | In-App Queue | WebSocket/database writer | WebSocket if online, a database row if offline |

Delivery webhooks come back from the three external channels — email, push and SMS. The In-App channel needs none, because the system delivers that one itself.

## Common interview mistakes

- **Stopping at "event → queue → workers".** That is the baseline. The decision layer — preferences, deduplication, priorities, rate limiting and digests — is what separates a shallow answer from a deep one.

- **Not distinguishing transactional from marketing notifications** — they have fundamentally different opt-out and compliance requirements.

- **Not mentioning idempotency under at-least-once event delivery.** "The user got the same email twice" is a concrete, easy-to-picture bug. The interviewer expects you to name it as a risk.

- **Retrying without considering the error's nature** — endlessly retrying sends to an invalid email or number, instead of marking it permanently failed right away.

- **A single provider with no abstraction or fallback** — not mentioning that an incident at an external email or SMS provider would fully halt that channel.

- **"Sent" = "delivered".** Delivery confirmation arrives asynchronously, via a provider webhook. Without it you cannot tell "sent" from "received by the user".

- **Ignoring rate limiting and batching.** A user who gets 20 push notifications in an hour from one thread will switch notifications off entirely. Digests are part of the architecture, not a design detail in the interface.
