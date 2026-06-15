# Notification System Design

## Why "direct calls" is an anti-pattern, and what that means in practice

```txt
❌ Order Service → Email Service → Push Service → SMS Service
   (synchronous calls)
```

The problem isn't just "Order Service goes down if Email Service is unavailable" — that's only a symptom. The root problem is that **Order Service has to know about every delivery channel** and its API. Adding a new channel (e.g., Slack notifications for B2B customers) requires changing Order Service. This directly violates the principle from [Message Queues]: a business service should publish a fact ("OrderCreated"), not dictate what happens with that fact.

```txt
✅ Order Service → publishes "OrderCreated" → Event Bus
                                                  │
                          ┌───────────────────────┼───────────────────┐
                          ▼                       ▼                   ▼
                  Notification Service      Analytics Service    CRM Service
```

This is the fan-out from [Message Queues], applied to a specific problem. The Notification Service is just one subscriber; adding a Slack channel is a new consumer that requires no changes to Order Service.

## Inside the Notification Service: a Decision Layer, not just "send everything"

A naive implementation is "got the event, sent email+push+sms to everyone at once." A real system has an intermediate **decision layer** that decides **what, to whom, through which channel, and when**:

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
     notifications in the last hour? → merge into a digest instead of a 6th separate one
        ↓
Per-channel Queue (Email Queue, Push Queue, SMS Queue, In-App Queue)
        ↓
Channel-specific Workers
```

This decision layer is what separates "just a queue with workers" (the old version of this article) from a system that's actually discussed in senior interviews.

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

Mixing these categories in a single preferences table without separating by type is a common design mistake — in practice it leads either to critical notifications not being delivered, or to legal issues around spam.

## Idempotency and deduplication — at-least-once in action

The Event Bus (as discussed in [Message Queues]) typically provides at-least-once delivery — the same "OrderCreated" event can be processed **twice**.

```ts
// ❌ On reprocessing, the user gets 2 identical emails
async function handleOrderCreated(event: OrderCreatedEvent) {
  await sendEmail(event.userId, 'Order confirmed', ...);
}

// ✅ Idempotency via a notification_id tied to (eventId, channel, type)
async function handleOrderCreatedIdempotent(event: OrderCreatedEvent) {
  const notificationId = `${event.eventId}:email:order_confirmation`;

  const existing = await db.notifications.findUnique({ where: { id: notificationId } });
  if (existing) return; // already sent or in progress — no-op

  await db.notifications.create({
    data: { id: notificationId, userId: event.userId, status: 'pending', channel: 'email' },
  });

  await sendEmail(event.userId, 'Order confirmed', ...);
  await db.notifications.update({ where: { id: notificationId }, data: { status: 'sent' } });
}
```

This is the same problem and solution as in [Message Queues] — the difference is that "a duplicate email" is far more visible to the user than "a duplicate analytics record," which is exactly why interviewers like to probe whether candidates connect the dots in a notifications context.

## Retry, Backoff, and DLQ — applied to external providers

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

This applies the "eliminating SPOF" pattern from [System Design Fundamentals] to external dependencies: if the entire Notification Service depends on a single email provider with no abstraction, an incident on that provider's side (and major email providers do have multi-hour degradations) halts delivery of all transactional emails — critical for OTP codes.

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

Without this feedback loop, "sent" means "we handed it to the provider," not "the user received it" — a difference that matters for compliance and for alerting ("why is our bounce rate 40% on new signups — maybe a bug in the signup form").

## Realtime (In-App) vs Push vs Email/SMS — choosing a channel based on user context

```txt
User is online (an open WebSocket connection, see [WebSockets]):
  → delivery via WebSocket is instant, the In-App notification
    appears without a reload

User is offline:
  → the in-app notification is saved to the DB (unread),
    will appear on the next login
  → IF critical, also send push via FCM/APNs
  → IF very critical and push didn't land, SMS as a fallback
```

This decision is made at the decision layer level and depends both on the user's presence status (Redis, see [WebSockets]) and on how important this particular notification is — not every notification deserves an SMS, even if a push fails.

## Final architecture

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

## Common interview mistakes

- **Stopping at "event → queue → workers"** — that's the baseline; the decision layer (preferences, deduplication, priorities, rate limiting/digest) is what separates a shallow answer from a deep one.

- **Not distinguishing transactional from marketing notifications** — they have fundamentally different opt-out and compliance requirements.

- **Not mentioning idempotency under at-least-once event delivery** — "the user got the same email twice" is a concrete, easy-to-picture bug the interviewer expects you to flag as a risk.

- **Retrying without considering the error's nature** — endlessly retrying sends to an invalid email/number instead of immediately marking it as permanently failed.

- **A single provider with no abstraction/fallback** — not mentioning that an incident at an external email/SMS provider would fully halt that channel.

- **"Sent" = "delivered"** — not accounting for the fact that delivery confirmation arrives asynchronously via a provider webhook, and without it you can't distinguish "sent" from "received by the user."

- **Ignoring rate limiting/batching** — a user getting 20 push notifications in an hour due to activity in one thread will disable notifications entirely; digests are part of the architecture, not a "UI design feature."
