# RabbitMQ vs Alternatives

## The framing that makes comparisons useful

Comparing message brokers by feature lists misses the point. A line like "Kafka has log compaction, RabbitMQ has per-message TTL" is true, but it does not tell you which broker fits your problem. TTL stands for time to live: the age at which a broker drops a message it still holds. The useful frame is **what problem each system was designed to solve first**:

- **RabbitMQ** was designed for routing and delivery of individual messages. Its core question: how do I get this specific message to the right consumer?
- **Kafka** was designed for durable, ordered, replayable event logs at scale. Its core question: how do I store a stream of events that any consumer can read in order, from any point in time?
- **Redis Pub/Sub** was designed for in-memory real-time broadcast between connected clients. Its core question: how do I fan out a signal to every listening subscriber with the lowest possible latency?
- **AWS SQS** (Simple Queue Service, the managed queue of Amazon Web Services) was designed for decoupled, managed, at-least-once task queues with no operational overhead. Its core question: how do I queue background work without running infrastructure?

Understanding the original design intent tells you more about fit than any feature list.

## RabbitMQ vs Kafka

This is the most common comparison at senior interviews, and it's frequently framed as "smart broker, dumb consumer" vs "dumb broker, smart consumer."

### The architectural difference

| | RabbitMQ, the "smart broker" | Kafka, the "smart consumer" |
|---|---|---|
| Message layout | Routed by exchange and binding rules into queues | Appended to ordered, immutable logs: topics split into partitions |
| What the broker tracks | Which messages each consumer has received | Nothing per consumer. It appends and serves |
| What the consumer tracks | Nothing. It processes whatever arrives | Its own position in the log, a number called an offset |
| After processing | The broker deletes the message once the consumer acks it | Nothing is deleted. The consumer can replay from any offset: yesterday, last week, the beginning of time |
| Delivery | Push: the broker sends to the consumer | Pull: the consumer polls the broker |

The offset ownership is the key difference. In RabbitMQ, once a message is acked, it's gone: there is no way to re-read it. In Kafka the data is retained for a configurable period (days, weeks, forever), and any new consumer can read from the beginning.

Push versus pull is not about which side controls the rate. A RabbitMQ consumer sets a prefetch window with `basic.qos`, which caps how many unacknowledged messages the broker may hand it. A Kafka consumer caps its own fetches with `max.poll.records` and `fetch.max.bytes`. Both sides control the rate; they just do it from opposite ends of the connection.

### Throughput and use cases

- **RabbitMQ strengths**
  - Complex routing: four exchange types, wildcard patterns, header matching.
  - Per-message TTL, priority queues, and a dead-letter queue (DLQ) out of the box.
  - Push delivery, so lower latency for an individual message.
  - Easy competing consumers: several workers on one queue.
  - A well-understood operational model, with a management web interface included.
  - Tens of thousands of messages per second per queue, and roughly 50k per second per node when several queues share the node. You go above that only by dropping persistence or by adding queues.
- **Kafka strengths**
  - A replayable event log, so consumers can re-read history.
  - Exactly-once semantics inside Kafka, using Kafka transactions. The guarantee runs from Kafka to Kafka: the consumer offset is written in the **same transaction** as the output topics. Kafka's own documentation notes that most external systems do not support two-phase commit. A consumer that writes into a database therefore gets no exactly-once guarantee, unless it stores the offset in that same database.
  - An order of magnitude more throughput — millions of messages per second on a modest cluster — because it writes sequentially and batches records.
  - Multiple independent consumer groups, each with its own offset.
  - Stream processing with Kafka Streams and ksqlDB.
  - Long-term event storage: event sourcing, audit logs, data lake ingestion.
- **RabbitMQ weaknesses**
  - No message replay. Once a message is acked, it is gone.
  - No consumer groups with independent offsets.
  - Less suited to high fan-out where every consumer needs its own replay.
- **Kafka weaknesses**
  - No native per-message routing. Routing goes by topic and partition only.
  - No per-message TTL, only retention policies at the log level.
  - Higher operational complexity: ZooKeeper or KRaft, plus partition management.
  - The pull model adds polling latency.
  - No built-in DLQ. You implement it in application code.
  - The ordering guarantee is per partition, not per topic.

### Ordering guarantees

- **RabbitMQ**
  - A single consumer on a queue gives a guaranteed FIFO order (first in, first out).
  - Several consumers on one queue give no global order guarantee. Consumer A may process message 2 while consumer B is still working on message 1.
  - Competing consumers trade ordering for throughput.
- **Kafka**
  - Inside a single partition, messages are strictly ordered.
  - Across partitions there is no order guarantee.
  - To guarantee order for one entity, say every event for `user_id=42`, use a partition key. Messages with the same key always go to the same partition.

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

| | Redis Pub/Sub | RabbitMQ |
|---|---|---|
| Storage | In-memory only. A Redis restart loses every pending message | Persistent by default: durable queue plus persistent messages |
| Offline consumer | Misses the message permanently | The message waits in the queue, and the consumer catches up when it reconnects |
| Acknowledgements | None. Fire-and-forget at the protocol level | Full ack, nack and retry semantics |
| Queueing | No queue. Messages are broadcast and gone | Messages wait in the queue until a consumer connects and acks them |

What Redis Pub/Sub buys with all that is latency: under a millisecond for an in-process Redis.

Redis also offers **Redis Streams**, added in Redis 5.0, and that one is closer to Kafka than to Pub/Sub. It has consumer groups, persistent storage, and message identifiers for position tracking. Redis Streams is a reasonable lightweight Kafka alternative for small-to-medium event streaming.

- **Choose Redis Pub/Sub when**
  - You need real-time broadcast to currently connected clients: chat, a live dashboard, notifications.
  - You send cache invalidation signals, telling app servers to drop a key.
  - Losing a signal is acceptable, because the next one arrives soon.
  - You already run Redis and don't want another broker.
- **Choose RabbitMQ when**
  - Delivery must be guaranteed even if the consumer is offline.
  - You need durable queues, a DLQ, and retry logic.
  - The operations are business-critical and cannot lose messages.

## RabbitMQ vs AWS SQS

AWS SQS is a fully managed message queue service: no servers to provision, no brokers to maintain.

- **AWS SQS**
  - Fully managed: no cluster to run, automatic scaling, a 99.9% SLA (service level agreement).
  - At-least-once delivery, guaranteed by AWS.
  - Standard queues: extremely high throughput, but messages may arrive out of order.
  - FIFO queues: exactly-once processing plus ordering, at a lower throughput of about 3k TPS (transactions per second).
  - Visibility timeout: a message becomes "invisible" while it is being processed. This is not a real lock, because another consumer can grab it once the timeout expires.
  - DLQ support is built in, through a redrive policy, with no extra topology.
  - Pull-based: consumers call `ReceiveMessage` to fetch, and long polling is supported.
  - No exchanges and no routing: one queue per logical stream.
  - Pay-per-message pricing, around $0.40 per million messages on Standard.
- **RabbitMQ**
  - Self-hosted, or run through a managed option: CloudAMQP, or Amazon MQ (managed queue).
  - Complex routing with exchanges.
  - Push-based delivery, so lower latency for an individual message.
  - More control over topology, behavior, and tuning.
  - No per-message pricing, just a fixed infrastructure cost.

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

This is different from RabbitMQ's ack model. In SQS you delete a message instead of acking it. Redelivery on failure comes from the timeout expiring, not from an explicit nack.

### SQS FIFO queues — when exactly-once matters in AWS

| | Standard SQS | FIFO SQS |
|---|---|---|
| Throughput | Nearly unlimited | 300 TPS, or 3,000 with batching |
| Ordering | Best-effort, not guaranteed | Guaranteed within a message group |
| Delivery | At-least-once, duplicates possible | Exactly-once, a deduplication identifier blocks duplicates |

FIFO queues exist for cases like financial transactions and order processing sequences, where a duplicate or a swapped pair is a real bug.

### When to choose SQS over RabbitMQ

- You're already on AWS and want zero infrastructure management
- You need automatic scaling without capacity planning
- Your routing needs are simple: point-to-point, or fan-out via SNS (Simple Notification Service)
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
┌────────────────────────────────────────────────────────────────┐
│                 MESSAGE BROKER DECISION GUIDE                  │
├────────────────────────────────────────────────────────────────┤
│ Do you need to replay messages, or let new consumers           │
│ read history?                                                  │
│   YES → Kafka (or Redis Streams for lower volume)              │
│   NO  → continue                                               │
│                                                                │
│ Do you need extremely high throughput (millions/sec)?          │
│   YES → Kafka                                                  │
│   NO  → continue                                               │
│                                                                │
│ Is real-time broadcast to connected clients the main           │
│ use case, and is message loss acceptable?                      │
│   YES → Redis Pub/Sub                                          │
│   NO  → continue                                               │
│                                                                │
│ Are you on AWS and want zero infrastructure work?              │
│   YES → SQS (Standard or FIFO), plus SNS for fan-out           │
│   NO  → continue                                               │
│                                                                │
│ Do you need complex routing, per-message TTL,                  │
│ priority queues, or fine-grained retry control?                │
│   YES → RabbitMQ                                               │
│                                                                │
│ Do you need simple background job queuing at moderate          │
│ throughput, without managing a broker?                         │
│   → SQS (on AWS) or RabbitMQ with CloudAMQP                    │
└────────────────────────────────────────────────────────────────┘
```

## Common interview traps

- **"Kafka is always better than RabbitMQ because it's faster"** — Kafka is faster for bulk throughput and for stream processing. RabbitMQ has lower per-message latency for delivering one message, because it pushes instead of being polled. For task queues with complex routing, RabbitMQ is simpler and fits better. "Better" depends entirely on the problem.

- **"Redis Pub/Sub is a good drop-in replacement for RabbitMQ"** — only if you can accept losing messages when consumers are offline. Redis Pub/Sub has no persistence, no queuing, and no delivery guarantees. It's a broadcast mechanism, not a message queue.

- **"Kafka guarantees exactly-once across the whole topic"** — ordering and exactly-once guarantees in Kafka are per partition, not per topic. A topic with 10 partitions has 10 independent ordered logs. Events for the same entity must be routed to the same partition via a partition key to keep their ordering. And exactly-once itself is Kafka-to-Kafka: it does not extend to a database you write into.

- **"SQS FIFO guarantees global ordering"** — SQS FIFO guarantees ordering within a **message group** (identified by `MessageGroupId`). Messages in different groups can be processed in parallel and out of order relative to each other. One FIFO queue with one message group is effectively single-threaded.

- **"I should always use Kafka because it's industry standard"** — Kafka's operational complexity is a real cost: partition management, consumer group rebalancing, offset management. Picture a team of three engineers running business software with moderate traffic. Standing up a Kafka cluster there, just to send background email, is overengineering. Use the simplest tool that meets the requirements.

- **"RabbitMQ can do event sourcing"** — poorly. RabbitMQ doesn't retain messages after ack, can't replay, and has no log semantics. Event sourcing requires an append-only store that you can replay from the beginning. For event sourcing, use Kafka, EventStoreDB, or a database with a CDC (change data capture) approach.
