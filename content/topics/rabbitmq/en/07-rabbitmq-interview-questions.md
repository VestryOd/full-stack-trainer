# RabbitMQ — Interview Questions

## Group 1: Fundamentals

**What problem does a message queue solve that direct HTTP calls cannot?**

HTTP is synchronous and couples availability: if Service B is slow or down, Service A's request fails. A message queue breaks this coupling in three ways: (1) **temporal decoupling** — producer and consumer don't need to be available simultaneously; (2) **load decoupling** — a traffic spike fills the queue rather than overwhelming the consumer; (3) **failure isolation** — a consumer crash doesn't affect the producer; it reconnects and processes from where it left off. The tradeoff: eventual consistency instead of immediate confirmation, and the added operational cost of running a broker.

---

**What is AMQP and why does it matter?**

AMQP (Advanced Message Queuing Protocol) is an open, wire-level protocol for message-oriented middleware. "Wire-level" means the exact bytes on the network are standardized — any AMQP-compliant client in any language can talk to RabbitMQ without vendor lock-in. RabbitMQ implements AMQP 0-9-1 (not the incompatible AMQP 1.0). The key design constraint of AMQP that shapes everything: producers never publish directly to queues — they publish to exchanges, which route to queues via bindings. This indirection is what enables RabbitMQ's routing flexibility.

---

**Explain the difference between a durable queue and a persistent message.**

These are independent settings that are often conflated. A **durable queue** (`{ durable: true }`) means the queue's definition (name, settings, bindings) survives a broker restart — the "pipe" isn't lost. A **persistent message** (`{ persistent: true }`, which sets delivery mode 2) means the message content itself is written to disk — it survives a broker restart even if unprocessed. In production you need both: a durable queue without persistent messages will be empty after a crash; a persistent message in a non-durable queue won't survive because the queue itself disappears on restart.

---

**What is the difference between at-most-once, at-least-once, and exactly-once delivery?**

**At-most-once**: broker delivers the message once; if the consumer crashes before processing, the message is gone (`noAck: true` in RabbitMQ). **At-least-once**: broker redelivers on failure; the consumer may process the same message more than once (RabbitMQ default with `ack`/`nack`). **Exactly-once**: each message is processed exactly once even across failures — requires coordination between broker, consumer, and storage. RabbitMQ does not provide exactly-once natively. The practical path: design for at-least-once and make consumers idempotent. This achieves the safety of exactly-once without the complexity.

---

## Group 2: Core Concepts

**What are the four exchange types in RabbitMQ and when do you use each?**

**Direct**: routes to queues whose binding key exactly matches the routing key. Use for: task routing, specific notification types, per-tenant routing. **Topic**: routes using wildcard patterns (`*` = one word, `#` = zero or more words). Use for: event-driven microservices where different services care about subsets of events (`order.*`, `*.placed`). **Fanout**: ignores the routing key, delivers to all bound queues. Use for: broadcasting events to all interested parties (Pub/Sub pattern). **Headers**: routes based on message header key-value pairs (`x-match: all/any`). Use for: attribute-based routing when the routing key isn't expressive enough — rare in practice, topic covers most cases.

---

**What is the default exchange and how is `sendToQueue` related to it?**

The default exchange is a pre-declared direct exchange with an empty string name (`""`). Its special rule: every queue is automatically bound to it with its own name as the binding key. `channel.sendToQueue('my-queue', payload)` is syntactic sugar for `channel.publish('', 'my-queue', payload)` — it publishes to the default exchange with the queue name as routing key. You can't manually add bindings to the default exchange (the auto-binding is implicit). It's fine for simple cases, but explicit named exchanges give you flexibility to route the same message to multiple queues without changing the producer.

---

**What is the difference between `nack` with `requeue: true` and `nack` with `requeue: false`?**

`channel.nack(msg, false, true)` — the message is returned to the queue and redelivered immediately. Without a delay, this creates a tight retry loop on permanent errors (malformed payload, missing dependency) that can saturate both the consumer and the broker. `channel.nack(msg, false, false)` — the message is discarded; if the queue has a configured `x-dead-letter-exchange`, it's routed there instead. The production pattern: `nack` with `requeue: false` on failure, with a dead-letter queue configured, and a separate retry topology (TTL-based delayed queue) for controlled backoff before redelivery.

---

**What is a Dead Letter Queue (DLQ) and what triggers it?**

A DLQ is a queue that receives messages which cannot be processed. A message becomes a "dead letter" in three cases: (1) rejected with `nack`/`reject` with `requeue: false`; (2) its TTL (`x-message-ttl`) expires before a consumer processes it; (3) the queue reaches its `x-max-length` limit. Configuration: set `x-dead-letter-exchange` on the source queue. RabbitMQ adds `x-death` headers to dead-lettered messages containing the original queue, reason (`rejected`, `expired`, `maxlen`), and a retry count. DLQ consumers typically alert the team, store messages to a DB for inspection, or re-publish with corrected data after a fix is deployed.

---

## Group 3: Node.js Integration

**Why must `prefetch` be called before `consume`, and how do you choose the value?**

Without `prefetch`, RabbitMQ pushes all queued messages to the consumer at once. If a queue has 50,000 messages and the consumer processes slowly, all 50,000 land in the consumer's memory — the queue has effectively moved from RabbitMQ's managed storage to your process heap. `prefetch(N)` tells the broker: "don't deliver more than N unacknowledged messages at a time." Must be called before `consume` because it configures the channel's QoS before any messages start flowing. Value selection: prefetch=1 for strict fairness and ordering (low throughput); prefetch=10–50 for typical background jobs (balanced); prefetch=100+ for fast, I/O-light consumers (high throughput, more memory used).

---

**What does `channel.publish()` returning `false` mean, and what should you do?**

`false` means the channel's internal write buffer is full — RabbitMQ's backpressure signal. If you ignore it and keep publishing, you'll exhaust memory. The correct response: stop publishing and wait for the `drain` event on the channel before resuming. In code: `const canSend = channel.publish(...); if (!canSend) { await new Promise(resolve => channel.once('drain', resolve)); }`. This is especially important in batch publishing loops. Ignoring backpressure is a common cause of "RabbitMQ consumer memory alarm" alerts in production.

---

**What is `noAck: true` and when is it appropriate?**

`noAck: true` means RabbitMQ removes the message from the queue the moment it delivers it — before the consumer does anything with it. There's no ack to send. If the consumer crashes between receiving and processing, the message is gone permanently. It's appropriate only when message loss is acceptable: fire-and-forget analytics, metrics, log shipping, live dashboard updates — use cases where throughput matters more than guaranteed delivery. Never use `noAck: true` for business-critical operations (payments, orders, user data writes).

---

**How do you implement graceful shutdown for a RabbitMQ consumer?**

The goal: stop accepting new messages while allowing in-flight processing to complete. Steps: (1) on `SIGTERM`/`SIGINT`, call `channel.cancel(consumerTag)` — tells the broker to stop delivering new messages to this consumer; (2) wait for in-flight messages to finish (a short timeout or tracking an in-flight counter); (3) `channel.close()` then `connection.close()`; (4) `process.exit(0)`. Without cancellation, `connection.close()` causes in-flight messages to be nacked and redelivered — acceptable for idempotent consumers, but may cause duplicate processing for non-idempotent ones.

---

## Group 4: Reliability

**What is the Transactional Outbox Pattern and why is it needed?**

Without it: you write to the DB and publish to RabbitMQ in two separate operations. A process crash between them leaves your system in an inconsistent state — either the DB has data with no corresponding event, or an event was published for data that wasn't committed. The Outbox pattern: write the message to an `outbox` table in the same DB transaction as the business data. A separate relay process reads `WHERE published_at IS NULL` using `SELECT FOR UPDATE SKIP LOCKED` (prevents two relay instances from grabbing the same row) and publishes to RabbitMQ with publisher confirms. Only after the broker confirms receipt does the relay mark the row as published. This guarantees atomicity without distributed transactions.

---

**How do you implement retry with exponential backoff in RabbitMQ?**

RabbitMQ has no native retry delay. The standard pattern uses TTL + Dead Letter Exchange: (1) the main queue has `x-dead-letter-exchange` pointing to a retry exchange; (2) on failure, `nack` with `requeue: false` — the message routes to the retry exchange; (3) the retry queue has `x-message-ttl` (e.g., 30 seconds) and `x-dead-letter-exchange` pointing back to the main exchange — after TTL expiry the message returns to the main queue for reprocessing. For exponential backoff, use multiple retry queues with increasing TTLs (5s, 30s, 5min), routing to successively slower queues based on the `x-death[0].count` header. After the maximum retry count, route to a permanent DLQ.

---

**What is an idempotent consumer and how do you implement one?**

An idempotent consumer produces the same result whether it processes a message once or ten times — necessary because RabbitMQ guarantees at-least-once delivery (messages can be redelivered after crashes). Two implementation approaches: (1) **Redis deduplication**: `SET processed:{messageId} 1 NX EX 86400` — if `NX` returns null, it's a duplicate, ack and skip; (2) **DB upsert**: `INSERT INTO table (...) ON CONFLICT (message_id) DO NOTHING` — the unique constraint makes the operation a no-op on retry. The `messageId` must be set by the producer (`{ messageId: crypto.randomUUID() }`). Without a stable `messageId`, deduplication requires business-key-based upserts (e.g., `ON CONFLICT (order_id) DO NOTHING`).

---

**What is a poison message and how do you detect and handle it?**

A poison message causes the consumer to crash or error every time it tries to process it — a malformed payload, an unexpected schema version, a bug triggered by specific data. Without a guard, the consumer enters an infinite crash-redeliver loop. Detection: `x-death` headers accumulate with each redelivery; when `x-death[0].count` exceeds `MAX_RETRIES`, the message is poisoned. Handling: don't retry — quarantine it. Ack the message (so it leaves the queue), write it to a `quarantined_messages` table with the full payload and headers, and send an alert to the team. Fix the root cause (usually a bug or schema change), then optionally re-publish corrected messages from the quarantine table.

---

## Group 5: Architecture & Comparisons

**What is the architectural difference between RabbitMQ and Kafka?**

RabbitMQ is a "smart broker" — it tracks delivery state per consumer, routes messages via exchanges, and deletes messages after ack. Consumers are stateless receivers. Kafka is a "smart consumer" — the broker stores messages in immutable ordered logs (partitions) indefinitely, consumers track their own position (offset), and can replay from any point in time. The practical consequence: in RabbitMQ, once a message is acked it's gone (no replay). In Kafka, new consumers can read the full history. Choose RabbitMQ for complex routing, task queues, per-message TTL, and moderate throughput. Choose Kafka for event replay, multiple independent consumer groups, event sourcing, and millions of messages per second.

---

**Why can't RabbitMQ guarantee ordering with multiple consumers on one queue?**

With a single consumer on a queue, delivery is FIFO — guaranteed. With multiple consumers, message 1 goes to Consumer A and message 2 goes to Consumer B. Consumer A processes slowly (or crashes and redelivers), Consumer B finishes first. From the business perspective, message 2 was "processed" before message 1. To maintain ordering with multiple consumers: use one queue per consumer (Pub/Sub pattern with fanout exchange, not competing consumers), or use Kafka with partition keys (all events for a given entity go to the same partition, processed by the same consumer).

---

**When would you choose Redis Pub/Sub over RabbitMQ?**

Redis Pub/Sub: when you need sub-millisecond real-time broadcast to currently-connected clients, and losing a message if a subscriber is offline is acceptable. Use cases: live dashboard updates, chat presence, cache invalidation signals, collaborative editing cursors. Redis Pub/Sub has no persistence — a subscriber that's offline misses the message permanently. RabbitMQ: when the message must be delivered even if the consumer is offline, when you need durable queues, DLQ, ack semantics, or complex routing. Redis Streams (added in Redis 5.0) is a middle ground: persistent, consumer groups, offset tracking — closer to Kafka, worth considering for simple event streaming when Redis is already in the stack.

---

**When would you choose AWS SQS over RabbitMQ?**

SQS: when you're on AWS and want zero infrastructure management (no cluster to run, automatic scaling, 99.9% SLA), pay-per-message pricing is acceptable, routing needs are simple (one queue per type), and you want managed DLQ via redrive policy with zero configuration. SQS uses a pull model with visibility timeout instead of push + ack. RabbitMQ: when you need complex routing (topic wildcards, headers), push delivery for lower per-message latency, fine-grained control over retry behavior and prefetch, or want to avoid AWS vendor lock-in. CloudAMQP and Amazon MQ provide managed RabbitMQ if you want the routing power without the operational burden.

---

## Group 6: System Design

**How would you design a reliable order notification system using RabbitMQ?**

Setup: topic exchange `order-events`. Order Service uses Transactional Outbox (write event to `outbox` table atomically with the order, relay publishes with publisher confirms). Email Service binds queue `order-email` to `order.placed` with a DLQ configured. Consumer is idempotent via `ON CONFLICT (message_id) DO NOTHING` on a `sent_notifications` table. Retry: `nack` with `requeue: false` on transient errors → messages wait in a retry queue (30s TTL) → return to main queue → max 3 retries → permanent DLQ with alerting. Prefetch set to 10 — allows parallelism without overwhelming the SMTP server. Graceful shutdown: cancel consumer on SIGTERM, wait for in-flight to complete.

---

**How would you prevent a failing consumer from creating an infinite retry loop?**

Three complementary guards: (1) **Maximum retry count**: read `x-death[0].count` from message headers; if `>= MAX_RETRIES`, route to a permanent DLQ instead of retrying. (2) **Retry delay**: `nack` with `requeue: false` → dead-letter to a retry exchange → retry queue with `x-message-ttl` → returns to main queue after delay. Without delay, retries are immediate and tight-loop. (3) **Poison message detection**: if the error is structural (JSON parse failure, schema validation error), skip retries entirely — quarantine immediately. The combination: transient errors get up to N delayed retries; structural errors go directly to quarantine.

---

**How would you scale a RabbitMQ consumer to handle 10x traffic?**

Horizontal scaling: run multiple consumer instances, each connecting to the same queue. RabbitMQ round-robins deliveries across all connected consumers — no coordination code required. Tune prefetch per instance: if each instance can handle 20 concurrent messages, `prefetch(20)`. For CPU-bound work, run one consumer per CPU core with `prefetch(1)`. For I/O-bound work (HTTP calls, DB writes), higher prefetch + more instances. RabbitMQ itself: add nodes to form a cluster; use Quorum Queues (replicated across nodes) instead of Classic Queues for HA. Quorum Queues provide automatic leader failover and are the recommended default for production since RabbitMQ 3.8.

---

**What is the choreography-based saga pattern and what are its trade-offs?**

In a choreography saga, each service reacts to events and publishes its own — there's no central coordinator. Example: Order Service publishes `order.placed` → Inventory Service reserves stock and publishes `order.inventory-reserved` → Payment Service charges and publishes `payment.processed` → Order Service updates status. Trade-offs: **pros**: no single point of failure (no coordinator service), loose coupling, each service is independently deployable. **cons**: hard to trace a single business transaction across multiple services and queues without distributed tracing (correlation IDs on every message, OpenTelemetry); compensating transactions must be explicit (if payment fails, publish `order.inventory-release`). The alternative — orchestration (a saga coordinator calls each service in order) — is easier to reason about but introduces a central service that can become a bottleneck and a single point of failure.
