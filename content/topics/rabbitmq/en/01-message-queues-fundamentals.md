# Message Queues — Fundamentals

## The problem that message queues solve

Imagine two microservices talking directly over HTTP:

```txt
[Order Service] ──── POST /api/notify ────► [Email Service]
```

This works fine while both services are healthy. Here is what can go wrong in production:

- **Email Service is down** → Order Service gets a 503 → the order fails, even though the order itself was saved correctly
- **Email Service is slow** (a flash sale filled its inbox) → Order Service times out → the customer sees an error for a healthy order
- **Traffic spike** → 10,000 orders per minute → Email Service receives 10,000 concurrent HTTP requests → it stops responding altogether
- **Deployment** → you deploy a new version of Email Service → for 5-10 seconds it's unavailable → Order Service requests fail

In all four cases, **the availability and latency of one service directly impacts another**. This tight coupling is the core problem.

A message queue breaks that direct dependency:

```txt
[Order Service] ──► [Queue] ──► [Email Service]
      ↑                               ↑
 "I published               "I'll process these
  a message,                 when I'm ready"
  my job is done"
```

Order Service publishes a message and moves on. It doesn't wait for Email Service to finish, and it doesn't care if Email Service is temporarily down. Email Service picks up messages from the queue at its own pace. After downtime it simply resumes from where it left off.

## Synchronous vs asynchronous communication

This is the fundamental distinction to internalize before anything else:

```txt
Synchronous (HTTP/REST, gRPC):
  Caller ──► Callee
  Caller WAITS for response
  If callee is slow/unavailable → caller is affected

Asynchronous (message queues):
  Publisher ──► Queue ◄── Consumer
  Publisher does NOT wait
  Consumer processes when it can
  Decoupled in time AND in failure
```

Synchronous isn't "bad". It is the right choice for:

- Queries where you need the result immediately ("get this user's profile")
- Operations that must be atomic ("check payment + reserve seat + confirm booking" in a single transaction)
- Simple request/response where two services are naturally coupled (e.g., an API Gateway calling its own backend)

Asynchronous (message queues) is the right choice for:

- Work that can happen in the background ("send a welcome email after signup")
- Work that could overwhelm a downstream service if done synchronously at peak load ("resize 10,000 uploaded images")
- Decoupling services that don't need to know about each other ("when an order is placed, notify inventory, billing, and analytics — independently")
- Guaranteed delivery even if a consumer is temporarily down

## Core vocabulary: producer, consumer, broker

These three terms show up in every message queue system — RabbitMQ, Kafka, AWS SQS (Simple Queue Service, from Amazon Web Services), Redis Streams:

```txt
Producer — the service that creates and sends a message
Consumer — the service that receives and processes a message
Broker   — the intermediary that stores messages and routes them
           between producers and consumers
```

In code terms for a Node.js app:

```ts
// Producer — Order Service creates a message when an order is placed
async function placeOrder(orderData: OrderData): Promise<void> {
  await db.orders.create(orderData);

  // After saving to DB, publish an event — don't call Email Service directly
  await messageQueue.publish('order.placed', {
    orderId: orderData.id,
    customerEmail: orderData.email,
    items: orderData.items,
  });
}

// Consumer — Email Service listens for that event
messageQueue.subscribe('order.placed', async (message: OrderPlacedMessage) => {
  await emailService.sendOrderConfirmation(message.customerEmail, message.orderId);
});
```

The broker (RabbitMQ, in our case) sits in the middle. It receives the message from the producer, stores it durably, and delivers it to the consumer when the consumer is ready. Neither service knows the other's network address. They only know the name of the queue or topic.

## Queue vs topic — two fundamental models

Most message queuing systems support two delivery patterns:

```txt
Queue (Point-to-Point):
  Producer ──► [Queue] ──► Consumer A
                            (one consumer gets each message)
  
  Use case: background jobs, task queues
  Example: "process this image upload" — one worker, not three

Topic (Publish/Subscribe or Pub/Sub):
  Producer ──► [Topic] ──► Consumer A (gets a copy)
                       ──► Consumer B (gets a copy)
                       ──► Consumer C (gets a copy)
  
  Use case: event broadcasting, fan-out
  Example: "order placed" → notify email, inventory and analytics
```

In RabbitMQ specifically, both patterns are implemented through its **exchange** system — but that's covered in detail in the next article. The mental model above is what matters for now.

## Push vs pull — how messages reach consumers

This distinction confuses a lot of engineers, and it comes up on senior interviews:

| | Push model | Pull model |
|---|---|---|
| Who moves it | The broker delivers as soon as a message arrives | The consumer fetches when it is ready |
| Readiness | The consumer must be ready to receive | The consumer controls the rate |
| Upside | Lower latency: the message arrives immediately | Natural backpressure: the consumer takes only what it can handle |
| Downside | The broker does not know whether the consumer can handle the load | Extra polling latency: the consumer may be idle when new messages arrive |

**RabbitMQ uses a push model** — it pushes messages to consumers over the AMQP (Advanced Message Queuing Protocol) channel. The consumer still controls the flow, through a **prefetch count** that article 03 covers in detail. The consumer tells the broker not to give it more than N unacknowledged messages at a time. That is backpressure, built inside the push model.

**Kafka uses a pull model** — consumers explicitly poll for new messages. This is one of the key architectural differences between the two systems (covered in article 05).

AWS SQS also uses a pull model (consumers call `ReceiveMessage` to fetch).

## What "durable" and "persistent" mean in this context

Two terms that are often conflated but mean different things:

| | Durable queue | Persistent message |
|---|---|---|
| What is written to disk | The queue definition: its name, bindings and settings | The message body itself |
| What survives a broker restart | The queue, but **not** the messages inside it | The message, even if no consumer has processed it yet |

For production systems you typically want **both** — a durable queue that holds persistent messages. Losing a queue definition on restart means you've lost the "pipe" entirely; losing the messages means the queue exists but is empty after a crash.

In amqplib (the standard Node.js AMQP client), this looks like:

```ts
import amqplib from 'amqplib';

const connection = await amqplib.connect('amqp://localhost');
const channel = await connection.createChannel();

// Declare a durable queue — survives broker restart
await channel.assertQueue('order-confirmations', { durable: true });

// Publish a persistent message — survives broker restart
channel.sendToQueue(
  'order-confirmations',
  Buffer.from(JSON.stringify({ orderId: '123', email: 'user@example.com' })),
  { persistent: true }, // delivery mode 2 — written to disk
);
```

Without `persistent: true`, messages are held in memory only. If RabbitMQ restarts before a consumer processes them, they're gone.

## Why not just use a database as a queue?

A common "why not" question in interviews. The short answer: you *can*, and teams do — but it comes with real tradeoffs:

```txt
Database-as-queue (polling pattern):
  ✓ No new infrastructure to manage
  ✓ Messages are transactional: one database transaction can save
    data and enqueue the job together
  ✓ Easy to inspect queue state with SQL
  
  ✗ Polling is inefficient: you're constantly querying for new rows
  ✗ At scale the "dequeue" query adds contention
    (SELECT ... FOR UPDATE SKIP LOCKED)
  ✗ No built-in fan-out (sending to multiple consumers)
  ✗ Message routing, dead-letter handling and retry policies —
    you build all of this yourself
  ✗ The table grows without bound unless you delete processed rows
```

PostgreSQL's `SKIP LOCKED` with a jobs table is a perfectly valid pattern for low-to-medium volume background jobs. Libraries like pgBoss and Que are built on exactly that. But once you need fan-out, multiple consumer groups, complex routing, or high throughput (100k+ messages/second), a dedicated broker is worth its cost.

The **Transactional Outbox Pattern** combines both approaches. You save messages to a database table atomically with the business data, and a separate process relays them into the real queue. So you get transactional safety **and** the routing and fan-out of a real broker. It is a senior-level pattern worth knowing, and article 04 returns to it.

## Common interview traps

- **"Message queues are just for email and notifications"** — that misses the broader role. Queues decouple services, rate-limit downstream systems, carry event sourcing, distribute task processing and choreograph microservices. Emails and notifications are the entry-level use case; the real value is reliability and decoupling.

- **"Async communication is always better than sync"** — wrong. If you need the result immediately (checking if a username is available), async adds complexity with no benefit. Use sync (HTTP) when you need the answer now; use async when you can fire-and-forget or tolerate eventual consistency.

- **Confusing "durable queue" with "persistent messages"** — these are independent settings. A durable queue definition without `persistent: true` messages will empty itself after a broker restart. You need both in production.

- **"If the message queue goes down, everything stops"** — in theory yes. But that misses the architectural response. The broker is one piece of infrastructure, and you run it clustered with replication. RabbitMQ clustering plus quorum queues give the same high-availability guarantees as a clustered database. You trade N direct dependencies for one hardened component, and that is a good trade.

- **"The producer should wait for confirmation that the consumer processed the message"** — this re-introduces the synchronous coupling you were trying to eliminate. Producers should only wait for the broker to confirm it received the message (publisher confirms), not for consumer processing to complete.
