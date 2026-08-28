# RabbitMQ — Interview Questions

## Group 1: Fundamentals

**What problem does a message queue solve that direct HTTP calls cannot?**

HTTP is synchronous, so it couples availability. If Service B is slow or down, Service A's request fails. A message queue breaks that coupling in three ways.

| Decoupling | What it gives you |
|---|---|
| **Temporal** | Producer and consumer don't have to be available at the same time. |
| **Load** | A traffic spike fills the queue instead of overwhelming the consumer. |
| **Failure** | A consumer crash doesn't reach the producer. The consumer reconnects and continues from where it stopped. |

The trade-off is eventual consistency instead of an immediate confirmation. You also pay the operational cost of running a broker.

---

**What is AMQP and why does it matter?**

AMQP (Advanced Message Queuing Protocol) is an open, wire-level protocol for message-oriented middleware. "Wire-level" means the exact bytes on the network are standardized. Any AMQP client, in any language, can talk to RabbitMQ without vendor lock-in.

RabbitMQ implements AMQP 0-9-1, not the incompatible AMQP 1.0.

One design rule of AMQP shapes everything else. Producers never publish straight to a queue: they publish to an exchange, and the exchange routes to queues through bindings. That extra step is what gives RabbitMQ its routing flexibility.

---

**Explain the difference between a durable queue and a persistent message.**

These are two independent settings, and they are often confused.

| Setting | What survives a broker restart |
|---|---|
| **Durable queue** (`{ durable: true }`) | The queue definition: name, settings, bindings. The "pipe" is still there. |
| **Persistent message** (`{ persistent: true }`, which sets delivery mode 2) | The message content itself, written to disk, even if nobody has processed it yet. |

In production you need both. A durable queue without persistent messages comes back empty after a crash. A persistent message in a non-durable queue does not survive either, because the queue itself disappears on restart.

---

**What is the difference between at-most-once, at-least-once, and exactly-once delivery?**

Three guarantees, from the weakest to the strongest.

| Guarantee | What the broker does | What it costs you |
|---|---|---|
| **At-most-once** | Delivers once and forgets (`noAck: true` in RabbitMQ). | The message is lost if the consumer crashes before processing it. |
| **At-least-once** | Redelivers after a failure (the RabbitMQ default, with `ack`/`nack`). | The consumer may process the same message more than once. |
| **Exactly-once** | Processes each message once, even across failures. | Needs coordination between broker, consumer and storage. |

RabbitMQ does not provide exactly-once natively. The practical path is to design for at-least-once and make consumers idempotent. That gives you the safety of exactly-once without the complexity.

---

## Group 2: Core Concepts

**What are the four exchange types in RabbitMQ and when do you use each?**

There are four types, and each one treats the routing key differently.

| Type | Routing rule | Use it for |
|---|---|---|
| **Direct** | Delivers to queues whose binding key exactly matches the routing key. | Task routing, specific notification types, per-tenant routing. |
| **Topic** | Matches wildcard patterns: `*` is one word, `#` is zero or more words. | Event-driven microservices where each service wants a subset of events (`order.*`, `*.placed`). |
| **Fanout** | Ignores the routing key and delivers to every bound queue. | Broadcasting an event to all interested parties, the Pub/Sub pattern. |
| **Headers** | Matches key-value pairs in the message headers (`x-match: all/any`). | Attribute-based routing when the routing key is not expressive enough. Rare in practice: topic covers most cases. |

---

**What is the default exchange and how is `sendToQueue` related to it?**

The default exchange is a direct exchange that RabbitMQ declares for you, and its name is the empty string (`""`). Its special rule: every queue is bound to it automatically, with the queue's own name as the binding key.

That rule is the whole of `sendToQueue`:

```js
// These two lines do exactly the same thing.
channel.sendToQueue('my-queue', payload);
channel.publish('', 'my-queue', payload); // '' is the default exchange
```

You cannot add bindings to the default exchange by hand, because the auto-binding is implicit. It is fine for simple cases. Named exchanges are what let you route one message to several queues without touching the producer.

---

**What is the difference between `nack` with `requeue: true` and `nack` with `requeue: false`?**

| Call | What happens to the message |
|---|---|
| `channel.nack(msg, false, true)` | It goes back to the queue and is redelivered right away. |
| `channel.nack(msg, false, false)` | It is discarded. If the queue has an `x-dead-letter-exchange` configured, the message is routed there instead. |

Immediate requeue is the dangerous one. On a permanent error — a malformed payload, a missing dependency — nothing separates one attempt from the next. The message spins in a tight retry loop that can saturate both the consumer and the broker.

The production pattern is the second call. Use `nack` with `requeue: false`, configure a dead-letter queue, and add a separate retry topology for controlled backoff. That topology is a delayed queue built on TTL (time to live — how long a message may wait before the broker expires it).

---

**What is a Dead Letter Queue (DLQ) and what triggers it?**

A DLQ is a queue that collects the messages which cannot be processed. A message becomes a "dead letter" in three cases:

- It was rejected with `nack` or `reject` and `requeue: false`.
- Its TTL (`x-message-ttl`) ran out before any consumer processed it.
- The queue reached its `x-max-length` limit.

To configure one, set `x-dead-letter-exchange` on the source queue. RabbitMQ then adds `x-death` headers to every dead-lettered message: the original queue, the reason (`rejected`, `expired`, `maxlen`) and a retry count.

A DLQ consumer usually alerts the team and stores the message in a database for inspection. Once the fix is deployed, it can re-publish the message with corrected data.

---

## Group 3: Node.js Integration

**Why must `prefetch` be called before `consume`, and how do you choose the value?**

Without `prefetch`, RabbitMQ pushes every queued message to the consumer at once. If the queue holds 50,000 messages and the consumer is slow, all 50,000 land in your process memory. The queue has effectively moved out of RabbitMQ's managed storage and into your heap.

`prefetch(N)` tells the broker not to deliver more than N unacknowledged messages at a time. It is a direct throttle: the broker stops pushing until you acknowledge. It has to be called before `consume`. The reason: it sets the channel's QoS (quality of service) limits, and that must happen before any message starts flowing.

| Value | Good for | What it costs |
|---|---|---|
| `prefetch(1)` | Strict fairness and ordering. | Low throughput. |
| `prefetch(10)` to `prefetch(50)` | Typical background jobs. | A balance of both. |
| `prefetch(100)` and above | Fast consumers that do little I/O. | High throughput, more memory used. |

---

**What does `channel.publish()` returning `false` mean, and what should you do?**

`false` means the channel's internal write buffer is full. That is RabbitMQ's backpressure signal. If you ignore it and keep publishing, you will run out of memory.

The correct response is to stop publishing and wait for the channel's `drain` event before resuming:

```js
const canSend = channel.publish(exchangeName, routingKey, payload);
if (!canSend) {
  // The buffer is full: pause until the channel has flushed it.
  await new Promise(resolve => channel.once('drain', resolve));
}
```

This matters most inside batch publishing loops. Ignoring backpressure is a common cause of "RabbitMQ consumer memory alarm" alerts in production.

---

**What is `noAck: true` and when is it appropriate?**

`noAck: true` means RabbitMQ removes the message from the queue the moment it delivers it, before the consumer has done anything with it. There is no ack to send. If the consumer crashes between receiving and processing, the message is gone for good.

Use it only where losing a message is acceptable:

- Fire-and-forget analytics.
- Metrics.
- Log shipping.
- Live dashboard updates.

What these have in common is that throughput matters more than guaranteed delivery. Never use `noAck: true` for business-critical work: payments, orders, or writes of user data.

---

**How do you implement graceful shutdown for a RabbitMQ consumer?**

The goal is to stop accepting new messages while letting the in-flight ones finish. Four steps:

1. On `SIGTERM` or `SIGINT`, call `channel.cancel(consumerTag)`. This tells the broker to stop delivering new messages to this consumer.
2. Wait for the in-flight messages to finish, using a short timeout or a counter of messages still in flight.
3. Call `channel.close()`, then `connection.close()`.
4. Call `process.exit(0)`.

Skip step 1 and `connection.close()` nacks the in-flight messages, so the broker redelivers them. That is acceptable for idempotent consumers. For non-idempotent ones it means duplicate processing.

---

## Group 4: Reliability

**What is the Transactional Outbox Pattern and why is it needed?**

Without it, you write to the database and publish to RabbitMQ as two separate operations. A crash between them leaves the system inconsistent. Either the database holds data that no event describes, or an event was published for data that never committed.

The Outbox pattern closes that gap. The message is written to an `outbox` table inside the same database transaction as the business data. A separate relay process then does three things:

1. Reads the unpublished rows with `WHERE published_at IS NULL`, using `SELECT FOR UPDATE SKIP LOCKED` so that two relay instances never grab the same row.
2. Publishes each row to RabbitMQ with publisher confirms.
3. Marks the row as published, but only after the broker confirms receipt.

The result is atomicity without distributed transactions.

---

**How do you implement retry with exponential backoff in RabbitMQ?**

RabbitMQ has no native retry delay. The standard pattern builds one out of a TTL and a dead letter exchange:

1. The main queue has `x-dead-letter-exchange` pointing at a retry exchange.
2. On failure the consumer sends `nack` with `requeue: false`, so the message routes to that retry exchange.
3. The retry queue has an `x-message-ttl` — 30 seconds, say — and its own `x-dead-letter-exchange` pointing back at the main exchange.
4. When the TTL expires, the message returns to the main queue and is processed again.

For exponential backoff, use several retry queues with increasing TTLs:

| Attempt | Retry queue TTL |
|---|---|
| 1 | 5 seconds |
| 2 | 30 seconds |
| 3 | 5 minutes |

Pick the next, slower queue from the `x-death[0].count` header. After the maximum retry count, route the message to a permanent DLQ.

---

**What is an idempotent consumer and how do you implement one?**

An idempotent consumer produces the same result whether it processes a message once or ten times. You need one because RabbitMQ guarantees at-least-once delivery, and a message can be redelivered after a crash.

There are two common implementations.

| Approach | How it works |
|---|---|
| **Redis deduplication** | `SET processed:{messageId} 1 NX EX 86400`. If `NX` returns null, the message is a duplicate: ack it and skip. |
| **Database upsert** | `INSERT INTO table (...) ON CONFLICT (message_id) DO NOTHING`. The unique constraint turns a retry into a no-op. |

Both need a stable `messageId`, and the producer has to set it (`{ messageId: crypto.randomUUID() }`). Without one, deduplication falls back on a business key, for example `ON CONFLICT (order_id) DO NOTHING`.

---

**What is a poison message and how do you detect and handle it?**

A poison message makes the consumer crash or fail every single time it tries to process it. The usual causes are a malformed payload, an unexpected schema version, or a bug that only specific data triggers. With no guard in place, the consumer falls into an endless crash-and-redeliver loop.

**Detection.** The `x-death` headers accumulate with every redelivery. Once `x-death[0].count` exceeds `MAX_RETRIES`, treat the message as poisoned.

**Handling.** Do not retry it, quarantine it:

- Ack the message, so that it leaves the queue.
- Write it to a `quarantined_messages` table with the full payload and headers.
- Send an alert to the team.

Then fix the root cause, which is usually a bug or a schema change. After that you can optionally re-publish the corrected messages from the quarantine table.

---

## Group 5: Architecture & Comparisons

**What is the architectural difference between RabbitMQ and Kafka?**

The two brokers put the intelligence in different places. RabbitMQ is a smart broker with a simple consumer; Kafka is a simple broker with a smart consumer.

| | RabbitMQ | Kafka |
|---|---|---|
| Routing | Exchanges route by key, pattern or header. | The producer picks a partition. |
| Storage | The message is deleted after ack. | Messages stay in immutable ordered logs (partitions) indefinitely. |
| Position | The broker tracks delivery state per consumer. | Each consumer tracks its own position, the offset. |
| Replay | None: once a message is acked it is gone. | A new consumer can read the full history from any point. |

Choose RabbitMQ for complex routing, task queues, per-message TTL and moderate throughput. Choose Kafka for event replay, several independent consumer groups, event sourcing, and millions of messages per second.

---

**Why can't RabbitMQ guarantee ordering with multiple consumers on one queue?**

With a single consumer on a queue, delivery is FIFO (first in, first out) and the order is guaranteed. Add a second consumer and that guarantee is gone.

Message 1 goes to Consumer A, message 2 goes to Consumer B. If A is slow, or crashes and gets a redelivery, then B finishes first. From the business point of view, message 2 was processed before message 1.

Two ways to keep the order:

- **One queue per consumer.** The Pub/Sub pattern with a fanout exchange, not competing consumers on one queue.
- **Kafka with partition keys.** All events for a given entity land in the same partition, and one consumer processes that partition.

---

**When would you choose Redis Pub/Sub over RabbitMQ?**

Choose Redis Pub/Sub when you need a sub-millisecond broadcast to the clients that are connected right now. Losing a message for an offline subscriber has to be acceptable, because Redis Pub/Sub has no persistence at all.

Typical use cases:

- Live dashboard updates.
- Chat presence.
- Cache invalidation signals.
- Collaborative editing cursors.

Choose RabbitMQ when the message must arrive even if the consumer is offline. That is also the answer when you need durable queues, a DLQ, ack semantics, or complex routing.

Redis Streams, added in Redis 5.0, sits between the two. It is persistent and it has consumer groups and offset tracking, which puts it closer to Kafka. It is worth considering for simple event streaming when Redis is already in your stack.

---

**When would you choose AWS SQS over RabbitMQ?**

Choose SQS (Simple Queue Service) from AWS (Amazon Web Services) when you want no infrastructure to manage and your routing needs are simple. Choose RabbitMQ when you need routing power and fine control over delivery.

| | Amazon SQS | RabbitMQ |
|---|---|---|
| Operations | Nothing to run: automatic scaling and a 99.9% SLA (service level agreement). | You run and tune the cluster yourself. |
| Delivery | Pull model with a visibility timeout. | Push with ack, which gives lower per-message latency. |
| Routing | Simple: one queue per message type. | Topic wildcards and header matching. |
| Dead letters | Managed, through a redrive policy, with no configuration. | You declare the exchange and the queue yourself. |
| Retries | Coarse control. | Fine control over retry behaviour and `prefetch`. |
| Lock-in | Tied to AWS. | Portable. |

CloudAMQP and Amazon MQ (managed message queuing) both offer a hosted RabbitMQ, if you want the routing power without the operational burden.

---

## Group 6: System Design

**How would you design a reliable order notification system using RabbitMQ?**

The topology is a single topic exchange, `order-events`, with one queue per consuming service.

- **Publishing.** Order Service uses the Transactional Outbox. The event is written to the `outbox` table atomically with the order, and a relay publishes it with publisher confirms.
- **Binding.** Email Service binds the queue `order-email` to `order.placed`, with a DLQ configured.
- **Idempotency.** The consumer relies on `ON CONFLICT (message_id) DO NOTHING` against a `sent_notifications` table.
- **Retries.** On a transient error, `nack` with `requeue: false`. The message waits in a retry queue with a 30-second TTL, then returns to the main queue. After three failed attempts it goes to a permanent DLQ that raises an alert.
- **Throughput.** `prefetch(10)` allows parallelism without overwhelming the SMTP (Simple Mail Transfer Protocol) server.
- **Shutdown.** Cancel the consumer on `SIGTERM` and wait for the in-flight messages to complete.

---

**How would you prevent a failing consumer from creating an infinite retry loop?**

Three guards, and they complement each other:

1. **Maximum retry count.** Read `x-death[0].count` from the message headers. Once it reaches `MAX_RETRIES`, route the message to a permanent DLQ instead of retrying it.
2. **Retry delay.** `nack` with `requeue: false` dead-letters the message to a retry exchange, whose queue has an `x-message-ttl`. The message returns to the main queue only after that delay. Without it, retries fire immediately and form a tight loop.
3. **Poison message detection.** If the error is structural — a JSON parse failure, a schema validation error — skip retries entirely and quarantine the message at once.

Together they split the failures in two. Transient errors get up to N delayed retries, and structural errors go straight to quarantine.

---

**How would you scale a RabbitMQ consumer to handle 10x traffic?**

Start with horizontal scaling: run several consumer instances, all connected to the same queue. RabbitMQ round-robins deliveries across every connected consumer, so you write no coordination code.

Then tune `prefetch` per instance to match the work:

| Workload | Setting |
|---|---|
| Each instance can handle 20 messages at once | `prefetch(20)` |
| Bound by the processor (CPU) | One consumer per core, `prefetch(1)` |
| Bound by I/O: HTTP calls, database writes | A higher prefetch, plus more instances |

Scale the broker as well. Add nodes to form a cluster. Use Quorum Queues instead of Classic Queues: a quorum queue is replicated across nodes, so the queue stays available when one node dies. Quorum queues also give automatic leader failover, and they have been the recommended default for production since RabbitMQ 3.8.

---

**What is the choreography-based saga pattern and what are its trade-offs?**

In a choreography saga each service reacts to events and publishes its own. There is no central coordinator.

The chain for an order looks like this:

1. Order Service publishes `order.placed`.
2. Inventory Service reserves the stock and publishes `order.inventory-reserved`.
3. Payment Service charges the customer and publishes `payment.processed`.
4. Order Service updates the order status.

| Pros | Cons |
|---|---|
| No single point of failure, because there is no coordinator service. | Hard to trace one business transaction across several services and queues. |
| Loose coupling between the services. | Tracing needs correlation IDs on every message, plus a tool such as OpenTelemetry. |
| Each service can be deployed independently. | Compensating transactions have to be explicit. If payment fails, something must publish `order.inventory-release`. |

The alternative is orchestration, where a saga coordinator calls each service in order. It is easier to reason about, but it adds a central service that can become both a bottleneck and a single point of failure.
