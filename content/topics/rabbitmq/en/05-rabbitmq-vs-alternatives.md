# RabbitMQ vs Alternatives

## The framing that makes comparisons useful

Comparing message brokers by feature lists ("Kafka has log compaction, RabbitMQ has per-message TTL") misses the point. The useful frame is **what problem each system was designed to solve first**:

```txt
RabbitMQ   → designed for routing and delivery of individual messages
             Core question: "how do I get this specific message to the right consumer?"

Kafka      → designed for durable, ordered, replayable event logs at scale
             Core question: "how do I store a stream of events that any consumer can read, in order, from any point in time?"

Redis Pub/Sub → designed for in-memory real-time broadcast between connected clients
             Core question: "how do I fan out a signal to all currently-listening subscribers with the lowest possible latency?"

AWS SQS    → designed for decoupled, managed, at-least-once task queues with no operational overhead
             Core question: "how do I queue background work reliably without managing infrastructure?"
```

Understanding the original design intent tells you more about fit than any feature list.

## RabbitMQ vs Kafka

This is the most common comparison at senior interviews, and it's frequently framed as "smart broker, dumb consumer" vs "dumb broker, smart consumer."

### The architectural difference

```txt
RabbitMQ ("smart broker"):
  - Broker tracks which messages each consumer has received
  - Broker routes messages using exchange/binding rules
  - Broker deletes messages after consumer acks them
  - Consumer just processes whatever arrives — no state required
  - Delivery is push-based: broker sends to consumer

Kafka ("smart consumer"):
  - Broker stores messages in ordered, immutable logs (topics with partitions)
  - Broker does NOT track per-consumer state — it just appends and serves
  - Consumer tracks its own position (called "offset") in the log
  - Consumer can replay from any offset: yesterday, last week, beginning of time
  - Delivery is pull-based: consumer polls the broker
```

The offset ownership is the key difference. In RabbitMQ, once a message is acked, it's gone — there's no way to re-read it. In Kafka, the data is retained for a configurable period (days, weeks, forever), and any new consumer can read from the beginning.

### Throughput and use cases

```txt
RabbitMQ strengths:
  ✓ Complex routing (4 exchange types, wildcard patterns, header matching)
  ✓ Per-message TTL, priority queues, DLQ out of the box
  ✓ Push delivery → lower latency for individual messages
  ✓ Easy competing consumers (multiple workers on one queue)
  ✓ Well-understood operational model, management UI included
  ✓ ~50k–150k messages/sec per node (typical tuned setup)

Kafka strengths:
  ✓ Replayable event log — consumers can re-read history
  ✓ Exactly-once semantics with Kafka transactions
  ✓ Extremely high throughput: millions of messages/sec on a modest cluster
  ✓ Multiple independent consumer groups, each with its own offset
  ✓ Stream processing with Kafka Streams / ksqlDB
  ✓ Long-term event storage (event sourcing, audit logs, data lake ingestion)

RabbitMQ weaknesses:
  ✗ No message replay — once acked, it's gone
  ✗ No consumer groups with independent offsets
  ✗ Less suited for high fan-out with independent replay needs

Kafka weaknesses:
  ✗ No native per-message routing — routing is via topic/partition only
  ✗ No per-message TTL (only log-level retention policies)
  ✗ Higher operational complexity (ZooKeeper or KRaft, partition management)
  ✗ Pull model adds polling latency
  ✗ No built-in DLQ (must implement in application code)
  ✗ Ordering guarantee is per-partition, not per-topic
```

### Ordering guarantees

```txt
RabbitMQ:
  - Single consumer on a queue → FIFO order guaranteed
  - Multiple consumers on a queue → no global order guarantee
    (consumer A might process message 2 while consumer B is still processing message 1)
  - Competing consumers trade ordering for throughput

Kafka:
  - Within a single partition → strictly ordered
  - Across partitions → no order guarantee
  - To guarantee order for a specific entity (e.g. all events for user_id=42),
    use a partition key: messages with the same key always go to the same partition
```

```ts
// Kafka: enforce ordering for a specific user's events
producer.send({
  topic: 'user-events',
  messages: [{
    key: userId.toString(),  // same key → same partition → ordered
    value: JSON.stringify(event),
  }],
});
```

### When to choose RabbitMQ over Kafka

- You need complex routing rules (wildcards, headers, per-consumer filtering)
- Messages are tasks or commands, not events — they should be consumed once, then deleted
- You need per-message TTL or priority
- You need DLQ and retry behavior with minimal application code
- You're running a small-to-medium system and don't want Kafka's operational complexity

### When to choose Kafka over RabbitMQ

- You need to replay events (new service needs to catch up from day one)
- Multiple independent consumer groups with different processing speeds
- Event sourcing or audit log that must never lose data
- Extremely high throughput (millions/sec)
- You're already in the Kafka ecosystem (Kafka Connect, Kafka Streams, ksqlDB)

## RabbitMQ vs Redis Pub/Sub

Redis Pub/Sub is the fastest way to fan out a signal to connected clients — and also the most fragile.

```txt
Redis Pub/Sub:
  - In-memory only: if a subscriber is offline when a message is published, it misses it — permanently
  - No persistence: Redis restart = all pending messages lost
  - No acknowledgements: fire-and-forget at the protocol level
  - No queue: messages are not stored waiting for consumers — they're broadcast and gone
  - Extremely low latency: sub-millisecond for in-process Redis

RabbitMQ:
  - Persistent by default (durable queue + persistent messages)
  - Messages wait in queue until consumer connects and acks
  - Full ack/nack/retry semantics
  - Offline consumers catch up when they reconnect
```

Redis also offers **Redis Streams** (added in Redis 5.0) which is closer to Kafka than to Pub/Sub — it has consumer groups, persistent storage, and message IDs for position tracking. Redis Streams is a reasonable lightweight Kafka alternative for small-to-medium event streaming.

```txt
Redis Pub/Sub: choose when
  ✓ Real-time broadcast to currently-connected clients (chat, live dashboard, notifications)
  ✓ Cache invalidation signals (tell app servers "invalidate this key")
  ✓ Loss of a signal is acceptable (the next one will arrive soon)
  ✓ You already have Redis and don't want another broker

RabbitMQ: choose when
  ✓ Message delivery must be guaranteed even if consumer is offline
  ✓ You need durable queues, DLQ, retry logic
  ✓ Business-critical operations that cannot lose messages
```

## RabbitMQ vs AWS SQS

AWS SQS (Simple Queue Service) is a fully managed message queue service — no servers to provision, no brokers to maintain.

```txt
AWS SQS:
  - Fully managed: no cluster to run, automatic scaling, 99.9% SLA
  - At-least-once delivery guaranteed by AWS
  - Standard queues: extremely high throughput, messages may arrive out of order
  - FIFO queues: exactly-once processing + ordering (lower throughput: ~3k TPS)
  - Visibility timeout: message becomes "invisible" while being processed
    (not a true lock — another consumer can grab it if timeout expires)
  - DLQ support built-in (via redrive policy, no extra topology needed)
  - Pull-based: consumers call ReceiveMessage to fetch (long polling supported)
  - No exchange/routing: one queue per logical stream
  - Pay-per-message pricing (~$0.40 per million messages on Standard)

RabbitMQ:
  - Self-hosted (or CloudAMQP/Amazon MQ managed options)
  - Complex routing with exchanges
  - Push-based delivery (lower latency for individual messages)
  - More control over topology, behavior, and tuning
  - No per-message pricing (fixed infrastructure cost)
```

### The SQS visibility timeout — a concept interviews often test

In SQS, when a consumer receives a message, it becomes **invisible** to other consumers for the duration of the visibility timeout (default 30 seconds). If the consumer doesn't delete the message before the timeout expires, it becomes visible again and another consumer can receive it.

```txt
SQS visibility timeout flow:
  Consumer A receives message → message invisible for 30s
  Consumer A processes and calls DeleteMessage → message gone ✓
  
  Consumer A crashes after receiving but before delete:
  → visibility timeout expires → message visible again
  → Consumer B receives it and processes it
  (This is how SQS achieves at-least-once without acks)
```

This is different from RabbitMQ's ack model: in SQS, you "delete" rather than "ack", and the timeout mechanism is what provides redelivery on failure rather than an explicit nack.

### SQS FIFO queues — when exactly-once matters in AWS

```txt
Standard SQS:
  - Throughput: nearly unlimited
  - Ordering: best-effort (not guaranteed)
  - Delivery: at-least-once (duplicates possible)

FIFO SQS:
  - Throughput: 300 TPS (or 3,000 with batching)
  - Ordering: guaranteed within a message group
  - Delivery: exactly-once (deduplication ID prevents duplicates)
  - Use case: financial transactions, order processing sequences
```

### When to choose SQS over RabbitMQ

- You're already on AWS and want zero infrastructure management
- You need automatic scaling without capacity planning
- Your routing needs are simple (point-to-point or fan-out via SNS)
- Cost predictability per message matters more than latency
- You want managed DLQ with zero configuration (redrive policy)

### When to choose RabbitMQ over SQS

- You need complex exchange-based routing (topic wildcards, per-message attributes)
- You're not on AWS or need to avoid vendor lock-in
- You need push delivery for lower per-message latency
- You have high volume and per-message costs would be prohibitive
- You need fine-grained control over retry behavior, prefetch, priority

## Decision guide

```txt
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MESSAGE BROKER DECISION GUIDE                       │
├─────────────────────────────────────────────────────────────────────────────┤
│ Do you need to replay messages or let new consumers read history?           │
│   YES → Kafka (or Redis Streams for lower volume)                           │
│   NO  → continue                                                            │
│                                                                             │
│ Do you need extremely high throughput (millions/sec)?                       │
│   YES → Kafka                                                               │
│   NO  → continue                                                            │
│                                                                             │
│ Is real-time broadcast to connected clients the primary use case,           │
│ and is message loss acceptable?                                             │
│   YES → Redis Pub/Sub                                                       │
│   NO  → continue                                                            │
│                                                                             │
│ Are you on AWS and want zero infrastructure management?                     │
│   YES → SQS (Standard or FIFO), optionally with SNS for fan-out            │
│   NO  → continue                                                            │
│                                                                             │
│ Do you need complex routing, per-message TTL, priority queues,              │
│ or fine-grained retry control?                                              │
│   YES → RabbitMQ                                                            │
│                                                                             │
│ Do you need simple background job queuing with moderate throughput          │
│ and don't want to manage a broker?                                          │
│   → SQS (if AWS) or RabbitMQ with CloudAMQP (if multi-cloud)               │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Common interview traps

- **"Kafka is always better than RabbitMQ because it's faster"** — Kafka is faster for bulk throughput and stream processing, but RabbitMQ has lower per-message latency for individual message delivery (push vs pull). For task queues with complex routing, RabbitMQ is simpler and fits better. "Better" depends entirely on the problem.

- **"Redis Pub/Sub is a good drop-in replacement for RabbitMQ"** — only if you can accept losing messages when consumers are offline. Redis Pub/Sub has no persistence, no queuing, and no delivery guarantees. It's a broadcast mechanism, not a message queue.

- **"Kafka guarantees exactly-once across the whole topic"** — ordering and exactly-once guarantees in Kafka are per-partition, not per-topic. A topic with 10 partitions has 10 independent ordered logs. Events for the same entity must be routed to the same partition via a partition key to maintain ordering.

- **"SQS FIFO guarantees global ordering"** — SQS FIFO guarantees ordering within a **message group** (identified by `MessageGroupId`). Messages in different groups can be processed in parallel and out of order relative to each other. One FIFO queue with one message group is effectively single-threaded.

- **"I should always use Kafka because it's industry standard"** — Kafka's operational complexity (partition management, consumer group rebalancing, offset management) is a real cost. For a team of 3 engineers building a B2B SaaS with moderate traffic, spinning up a Kafka cluster for background email sending is overengineering. Use the simplest tool that meets the requirements.

- **"RabbitMQ can do event sourcing"** — poorly. RabbitMQ doesn't retain messages after ack, can't replay, and has no log semantics. Event sourcing requires an append-only store that you can replay from the beginning. Use Kafka, EventStoreDB, or a database with a CDC (change data capture) approach for event sourcing.
