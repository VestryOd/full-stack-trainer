# Real-World Use Cases

## Use case 1 — Background job processing

The most common entry point into message queues for fullstack engineers: offloading slow or unreliable work from the HTTP request cycle.

**The pattern:** HTTP handler publishes a job message and immediately returns 202 Accepted. A separate worker process consumes the message and does the actual work.

```txt
HTTP Request → API Server → [Queue: jobs] → Worker Process
                ↓
         202 Accepted (instant)              (slow work happens here)
```

### Image processing pipeline

```ts
// api-server/routes/upload.ts
import { Router } from 'express';
import { getChannel } from '../rabbitmq';

const router = Router();

router.post('/images', async (req, res) => {
  // 1. Save original to S3 immediately
  const s3Key = await s3.upload(req.file);

  // 2. Publish a job — don't process synchronously
  const channel = await getChannel();
  channel.publish(
    'jobs',
    'image.resize',
    Buffer.from(JSON.stringify({
      jobId: crypto.randomUUID(),
      s3Key,
      userId: req.user.id,
      variants: ['thumbnail', 'medium', 'large'],
    })),
    { persistent: true, messageId: crypto.randomUUID() },
  );

  // 3. Return immediately — client polls or uses websocket for completion
  res.status(202).json({ status: 'processing', s3Key });
});
```

```ts
// worker/image-processor.ts
import sharp from 'sharp';

const VARIANTS = {
  thumbnail: { width: 150, height: 150 },
  medium:    { width: 800, height: 600 },
  large:     { width: 1920, height: 1080 },
};

await channel.prefetch(3); // process 3 images concurrently max

channel.consume('image-processing', async (msg) => {
  if (!msg) return;

  const job = JSON.parse(msg.content.toString()) as ImageJob;

  try {
    const original = await s3.download(job.s3Key);

    // Process all variants in parallel
    await Promise.all(
      job.variants.map(async (variant) => {
        const resized = await sharp(original)
          .resize(VARIANTS[variant])
          .webp({ quality: 85 })
          .toBuffer();

        const variantKey = job.s3Key.replace('.jpg', `-${variant}.webp`);
        await s3.upload(variantKey, resized);
      }),
    );

    // Notify the original requester via a completion event
    channel.publish(
      'jobs',
      'image.processed',
      Buffer.from(JSON.stringify({ jobId: job.jobId, variants: job.variants })),
      { persistent: true },
    );

    channel.ack(msg);
  } catch (err) {
    // Transient S3 error? Retry. Corrupt image? Dead-letter it.
    const isRetryable = err instanceof S3Error || err instanceof NetworkError;
    channel.nack(msg, false, isRetryable);
  }
});
```

**Why this beats synchronous processing:**
- HTTP request returns in milliseconds, not seconds
- Worker can run on separate infrastructure (different CPU/memory profile)
- Multiple workers can process different images in parallel
- Spikes in upload traffic don't spike processing latency — they grow the queue

---

## Use case 2 — Microservice decoupling via events

The order service scenario that comes up in nearly every senior system design interview.

**The problem:** An order gets placed. Downstream systems need to react: inventory must be reserved, an invoice must be generated, a confirmation email must be sent, analytics must record the sale. Calling each synchronously chains their availability into yours.

```txt
❌ Tight coupling:
Order Service → Inventory Service (timeout?)
             → Billing Service    (down for maintenance?)
             → Email Service      (slow SMTP?)
             → Analytics Service  (DDoS'd?)

If ANY downstream service fails → order placement fails

✅ Decoupled via events:
Order Service → [Exchange: order-events (fanout)]
                    ├──► [Queue: inventory]  → Inventory Service
                    ├──► [Queue: billing]    → Billing Service
                    ├──► [Queue: email]      → Email Service
                    └──► [Queue: analytics]  → Analytics Service

Order Service doesn't know any downstream service exists
Each service processes independently at its own pace
```

```ts
// order-service/order.service.ts
export class OrderService {
  constructor(
    private db: Database,
    private channel: Channel,
  ) {}

  async placeOrder(input: PlaceOrderInput): Promise<Order> {
    // Business logic + DB write
    const order = await this.db.transaction(async (trx) => {
      const created = await trx.orders.create({
        userId: input.userId,
        items: input.items,
        totalAmount: input.totalAmount,
        status: 'pending',
      });

      // Outbox entry in same transaction (see article 04)
      await trx.outbox.create({
        eventType: 'order.placed',
        payload: {
          orderId: created.id,
          userId: created.userId,
          items: created.items,
          totalAmount: created.totalAmount,
          placedAt: new Date().toISOString(),
        },
      });

      return created;
    });

    return order;
    // Event publishing happens via the outbox relay — not inline here
  }
}
```

```ts
// inventory-service/consumer.ts — completely independent
channel.consume('inventory', async (msg) => {
  if (!msg) return;
  const event = JSON.parse(msg.content.toString());

  try {
    // Reserve stock for all items
    await Promise.all(
      event.items.map((item: OrderItem) =>
        db.inventory.reserve(item.sku, item.quantity, event.orderId),
      ),
    );

    // If reservation fails (out of stock), publish a compensating event
    channel.publish('order-events', 'order.inventory-reserved',
      Buffer.from(JSON.stringify({ orderId: event.orderId })),
      { persistent: true },
    );

    channel.ack(msg);
  } catch (err) {
    if (err instanceof InsufficientStockError) {
      // Compensating event: tell order service to cancel
      channel.publish('order-events', 'order.inventory-failed',
        Buffer.from(JSON.stringify({ orderId: event.orderId, reason: err.message })),
        { persistent: true },
      );
      channel.ack(msg); // ack — this is expected business logic, not a system error
    } else {
      channel.nack(msg, false, false); // unexpected error → dead-letter
    }
  }
});
```

**Key insight:** The order service doesn't import or call inventory, billing, or email services. Adding a new downstream reaction (e.g., fraud detection) requires zero changes to the order service — just add a new queue binding to the fanout exchange.

---

## Use case 3 — Rate limiting downstream services

**The problem:** An external API (payment gateway, SMS provider, email delivery) has rate limits. Your system can generate requests faster than the API allows. Without a queue, you either add complex client-side throttling or get 429s.

```txt
User requests (burst) → [Queue: sms-outbox] → SMS Worker (controlled rate)
                                                    ↓
                                           External SMS API (rate limited)
```

```ts
// sms-worker/index.ts
const SMS_RATE_LIMIT_PER_SECOND = 10;

await channel.prefetch(SMS_RATE_LIMIT_PER_SECOND);

channel.consume('sms-outbox', async (msg) => {
  if (!msg) return;

  const { phoneNumber, message, campaignId } = JSON.parse(msg.content.toString());

  try {
    await twilioClient.messages.create({
      body: message,
      from: process.env.TWILIO_FROM,
      to: phoneNumber,
    });

    await db.smsLog.create({ phoneNumber, campaignId, status: 'sent', sentAt: new Date() });
    channel.ack(msg);
  } catch (err) {
    if (err instanceof TwilioRateLimitError) {
      // Back off and let the message return to the queue
      await sleep(1000);
      channel.nack(msg, false, true); // requeue — will be picked up after a moment
    } else {
      channel.nack(msg, false, false); // dead-letter
    }
  }
});

// The queue acts as a buffer: bursts of 10,000 SMS messages are queued
// and processed at the safe rate of 10/sec — no burst hits the external API
```

**Prefetch as a rate limiter:** Setting `prefetch(N)` limits in-flight messages per worker. With N workers each at `prefetch(10)`, you have 10N concurrent requests to the external API. Tune N × prefetch to stay under the rate limit.

---

## Use case 4 — Email notification fan-out

Multiple types of events should trigger emails. Instead of each service calling an email service directly, they publish events that the email service subscribes to via a topic exchange.

```txt
Exchange: 'notifications' (topic)

order-service    ──[order.placed]────────► 
payment-service  ──[payment.failed]──────► [Queue: email-notifications] → Email Worker
auth-service     ──[user.registered]─────►
billing-service  ──[subscription.renewed]►
```

```ts
// email-service/setup.ts
async function setupEmailConsumer(channel: Channel): Promise<void> {
  await channel.assertExchange('notifications', 'topic', { durable: true });
  await channel.assertQueue('email-notifications', {
    durable: true,
    arguments: { 'x-dead-letter-exchange': 'notifications.dlx' },
  });

  // Subscribe to ALL notification events from any service
  await channel.bindQueue('email-notifications', 'notifications', '#');

  await channel.prefetch(20);

  channel.consume('email-notifications', async (msg) => {
    if (!msg) return;

    const routingKey = msg.fields.routingKey; // 'order.placed', 'user.registered', etc.
    const event = JSON.parse(msg.content.toString());

    // Dispatch to the right email template based on event type
    const template = getEmailTemplate(routingKey);
    if (!template) {
      // Unknown event type — ack and ignore (don't dead-letter unrecognized events)
      channel.ack(msg);
      return;
    }

    try {
      await sendEmail({
        to: event.userEmail ?? event.customerEmail,
        subject: template.subject(event),
        html: template.render(event),
      });

      channel.ack(msg);
    } catch (err) {
      channel.nack(msg, false, false);
    }
  });
}

function getEmailTemplate(routingKey: string): EmailTemplate | null {
  const templates: Record<string, EmailTemplate> = {
    'order.placed':          { subject: (e) => `Order #${e.orderId} confirmed`, render: renderOrderConfirmed },
    'payment.failed':        { subject: () => 'Payment failed — action required', render: renderPaymentFailed },
    'user.registered':       { subject: () => 'Welcome!', render: renderWelcome },
    'subscription.renewed':  { subject: (e) => `Subscription renewed — $${e.amount}`, render: renderRenewal },
  };
  return templates[routingKey] ?? null;
}
```

**Why topic exchange instead of direct API calls:** Adding a new notification type (e.g., `shipment.dispatched`) requires zero changes to the email service — just add a template. The topic exchange binding `#` catches everything automatically.

---

## Use case 5 — Full order pipeline (system design example)

This is the architecture you'd sketch in a system design interview for an e-commerce platform. It ties together all the patterns from the previous articles.

```txt
┌─────────────────── ORDER PIPELINE ───────────────────────────────────────────┐
│                                                                               │
│  [POST /orders]                                                               │
│       │                                                                       │
│       ▼                                                                       │
│  [Order Service]  ──(outbox relay)──► Exchange: 'order-events' (topic)       │
│       │                                    │                                  │
│       ▼                               ┌────┴────────────────────┐             │
│  [DB: orders]                         ▼                         ▼             │
│  [DB: outbox]            ┌──[Queue: inventory]──►   ┌──[Queue: email]──►     │
│                          │   Inventory Service  │   │   Email Service  │     │
│                          └──────────────────────┘   └─────────────────-┘     │
│                                    │                          │               │
│                          ┌─────────┴──────┐       ┌──────────┴──────┐        │
│                          ▼                ▼       ▼                  ▼        │
│                   order.inventory  order.inven  order.confirmed    order.     │
│                   -reserved        tory-failed                     failed     │
│                          │                │                                   │
│                          ▼                ▼                                   │
│               [Queue: payment]    [Queue: order-updates]                      │
│               Payment Service     Order Service (saga compensation)           │
│                          │                                                    │
│                          ▼                                                    │
│                   payment.processed / payment.failed                          │
│                          │                                                    │
│                          ▼                                                    │
│               [Queue: order-updates]                                          │
│               Order Service updates status                                    │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
```

This is a **choreography-based saga** — each service reacts to events and publishes its own. There's no central coordinator; services talk through the message bus.

```ts
// order-service/saga-handler.ts
// Listens for events from downstream services and updates order status

channel.consume('order-updates', async (msg) => {
  if (!msg) return;

  const routingKey = msg.fields.routingKey;
  const event = JSON.parse(msg.content.toString());

  switch (routingKey) {
    case 'order.inventory-reserved':
      await db.orders.updateStatus(event.orderId, 'inventory_reserved');
      break;

    case 'order.inventory-failed':
      // Compensating transaction: cancel the order
      await db.orders.updateStatus(event.orderId, 'cancelled');
      // Notify the customer
      channel.publish('notifications', 'order.cancelled',
        Buffer.from(JSON.stringify(event)), { persistent: true });
      break;

    case 'payment.processed':
      await db.orders.updateStatus(event.orderId, 'confirmed');
      channel.publish('notifications', 'order.confirmed',
        Buffer.from(JSON.stringify(event)), { persistent: true });
      break;

    case 'payment.failed':
      await db.orders.updateStatus(event.orderId, 'payment_failed');
      // Release inventory reservation
      channel.publish('order-events', 'order.inventory-release',
        Buffer.from(JSON.stringify(event)), { persistent: true });
      break;
  }

  channel.ack(msg);
});
```

### What makes this architecture resilient

```txt
Failure scenario 1: Email Service is down
  → order.placed event sits in 'email' queue
  → Inventory and Payment proceed normally
  → When Email Service recovers, it processes the queued event
  → Customer gets the email late, but the order is processed correctly

Failure scenario 2: Payment Service crashes mid-processing
  → payment.processed never published
  → Order stays in 'inventory_reserved' state
  → Timeout job (or admin action) can trigger compensation
  → Alternatively: Payment Service reconnects, reprocesses in-flight message

Failure scenario 3: Order Service crashes after publishing, before outbox ack
  → Outbox relay re-publishes (at-least-once)
  → Downstream services receive duplicate event
  → Idempotent consumers handle it (ON CONFLICT DO NOTHING on order ID)
```

---

## Use case 6 — Worker pool for CPU-intensive tasks

When you have CPU-bound work (PDF generation, report compilation, data export), you want multiple workers to process tasks in parallel, with the queue as the buffer and load balancer.

```ts
// report-service/worker-pool.ts — run N instances of this

await channel.prefetch(1); // one heavy job per worker at a time

channel.consume('report-generation', async (msg) => {
  if (!msg) return;

  const job = JSON.parse(msg.content.toString()) as ReportJob;

  console.log(`Worker ${process.pid} processing report ${job.reportId}`);

  try {
    // CPU-intensive work — runs in this worker's process
    const pdfBuffer = await generatePDFReport(job.params);
    const s3Url = await s3.upload(`reports/${job.reportId}.pdf`, pdfBuffer);

    // Notify requester that the report is ready
    await db.reports.update(job.reportId, { status: 'ready', url: s3Url });
    await notifyUser(job.userId, s3Url);

    channel.ack(msg);
  } catch (err) {
    channel.nack(msg, false, false);
  }
});

// Scaling: run `docker-compose scale report-worker=5`
// RabbitMQ round-robins across all 5 workers, each with prefetch=1
// → 5 reports generated simultaneously, queue drains 5x faster
```

**The scaling story:** With N worker processes each consuming from the same queue, RabbitMQ naturally distributes work. Scale up by running more instances — no coordination code required.

## Common interview traps

- **"I should use a queue for everything to be safe"** — queues add complexity: you need to handle message serialization, consumer lifecycle, idempotency, dead-letters, monitoring. For a simple CRUD API calling one other service, synchronous HTTP is simpler and easier to reason about. Use queues when you genuinely need the decoupling or resilience benefits.

- **"The order pipeline above is a microservices anti-pattern because services are coupled through events"** — event coupling is loose coupling. Services share an event schema (a contract), not code or direct network calls. Adding, removing, or restarting a service doesn't require changes to others. The anti-pattern is sharing a database, not sharing an event bus.

- **"Choreography-based sagas are hard to debug"** — true, it's harder to trace a request across multiple services and queues compared to a single monolithic transaction. The answer isn't to avoid choreography — it's to invest in distributed tracing (correlation IDs on every message, OpenTelemetry) so you can follow a specific order through the entire pipeline.

- **"Using a queue for rate limiting is a workaround — I should fix the API client instead"** — the queue IS the fix. A rate-limited external API is a constraint you can't change. The queue decouples your system's traffic from the external API's capacity, which is exactly what it's designed for.

- **"Background jobs don't need dead-letter queues because failures are rare"** — failures happen in production, especially for jobs interacting with external services. Without a DLQ, a failed job is silently dropped. With a DLQ, failed jobs are visible, alertable, and can be replayed after fixing the root cause.

- **"Choreography vs orchestration — I need to know which is better"** — both are valid. Orchestration (a central saga coordinator calls each service in order) is easier to reason about and debug. Choreography (services react to events) scales better and has no single point of failure. The real answer on an interview: "it depends on team size, service count, and how often the process changes — and I've used both."
