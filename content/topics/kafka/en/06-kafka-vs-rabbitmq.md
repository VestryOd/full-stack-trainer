# Kafka vs RabbitMQ

## The Philosophical Difference: Log vs Queue

This isn't a comparison of "which is faster" or "which is more reliable." Kafka and RabbitMQ solve fundamentally different problems because they're built on different data storage models.

```txt
RabbitMQ — queue model:                  Kafka — log model:
┌────────────────────────────┐           ┌────────────────────────────────────┐
│  Broker stores messages    │           │  Broker stores the log             │
│  until they are read and   │           │  (append-only) until the           │
│  acknowledged (ack).       │           │  retention period expires,         │
│  After ack — message is    │           │  regardless of whether the         │
│  deleted.                  │           │  message was read or not.          │
└────────────────────────────┘           └────────────────────────────────────┘

  Producer ──► [msg1][msg2][msg3]           offset: 0     1     2     3     4
  Consumer reads msg1 →                     [msg1][msg2][msg3][msg4][msg5]

  ──► [msg2][msg3]                          Consumer A: offset=2 (read 0,1)
  msg1 IS DELETED                           Consumer B: offset=0 (reading from start)
                                            Consumer C: offset=4 (near real-time)
                                            msg1,2,3,4,5 ALL STILL IN THE LOG
```

Everything else follows from this difference: failure behavior, scaling, multi-consumer support, replay capability.

## Retention: How Long Data Is Kept

```txt
RabbitMQ — event-driven retention:
  A message exists ONLY until it is consumed.
  Read + ack → deleted immediately.
  No ack within N seconds → requeue (returned to queue for retry).
  Optionally: Dead Letter Queue for failed messages.

  Problem: you can't "rewind." If an analytics service wasn't
  reading the queue for 2 hours — those 2 hours of events are
  gone forever.

Kafka — time-based retention:
  A message is stored for N days (retention.ms) or until volume M bytes
  (retention.bytes), REGARDLESS of whether it was read.

  Default: 7 days. Configurable per topic:
    retention.ms=-1 → keep forever (compact topics)
    retention.ms=3600000 → 1 hour
    retention.bytes=1073741824 → delete oldest when exceeding 1GB

  Advantage: analytics service down for 2 hours → restarts from
  last offset → catches up on everything it missed. No data loss.
```

This isn't just a technical detail — it's Kafka's core architectural value. The log is the source of truth. A new service can subscribe and receive the entire history of events from the beginning. RabbitMQ offers no such capability.

## Delivery Model: Push vs Pull

```txt
RabbitMQ — push model:
  Broker actively "pushes" messages to subscribers.
  Broker manages backpressure via prefetch count.
  Consumer has no direct control over receive rate.

  Pro: low latency (sub-millisecond for simple tasks)
  Con: consumer can receive more messages than it can process

Kafka — pull model:
  Consumer polls the broker itself (poll).
  Consumer has full control over its processing rate.
  Broker has no knowledge of consumer state (except offsets).

  Pro: consumer is never overwhelmed; reads at its own pace
  Con: slightly higher latency for real-time tasks (but typically <10ms)
```

## Routing: Where Logic Lives

```txt
RabbitMQ — smart routing in the broker:
  ┌─────────────────────────────────────────────┐
  │              RabbitMQ Broker                 │
  │                                              │
  │  Producer ──► Exchange ──► Bindings ──►      │
  │              (direct/fanout/               Queue A ──► Consumer A
  │               topic/headers)              Queue B ──► Consumer B
  │                                            Queue C ──► Consumer C
  └─────────────────────────────────────────────┘

  Exchange types:
  - direct:  exact routing key match
  - fanout:  broadcast to all queues
  - topic:   wildcards in routing key (orders.*, *.critical)
  - headers: route by message headers

  Rich routing is RabbitMQ's strength.
  Complex topologies can be wired directly in the broker.

Kafka — routing in client code:
  The broker just stores topics.
  All logic of "which consumer reads what" lives in application code.

  Need fanout? → multiple consumer groups read the same topic.
  Need filtering? → consumer reads everything, filters itself.
  Need routing? → producer writes to different topics conditionally.

  This is not a weakness — it's the deliberate simplicity of the
  "dumb broker" philosophy.
```

## When to Choose Kafka

```txt
✓ Kafka is the right choice:

  1. Event Streaming / Event Sourcing
     Stream of events as a source of truth.
     Replay needed for new services or debugging.
     "What happened to this order over the past 30 days?"

  2. Multiple Independent Consumers of the Same Stream
     Order events → search + analytics + recommendations + audit.
     All read the same topic independently.
     Adding a new consumer requires no changes to the producer.

  3. Very High Throughput
     Millions of events per second.
     Real-time analytics, IoT telemetry, financial data streams.

  4. Log Aggregation
     Centralized log collection from microservices.
     Logstash/Filebeat → Kafka → Elasticsearch.

  5. Change Data Capture (CDC)
     Streaming database changes (Debezium → Kafka).
     Syncing across data stores.

  6. Long-Term Event Storage
     Event history needed for compliance, auditing, ML training.
```

## When to Choose RabbitMQ

```txt
✓ RabbitMQ is the right choice:

  1. Task Queues / Work Queues
     "Send an email," "resize an image," "generate a PDF."
     One task → one worker → result.
     No need to re-read the task after completion.

  2. RPC-Like Patterns
     Request → processing → response in a reply queue.
     Caller waits for the worker's result.
     Kafka is awkward for this.

  3. Complex Broker-Level Routing
     Different queues for different event types with wildcards.
     Conditional routing without logic in the consumer.

  4. Message Prioritization
     RabbitMQ supports priority queues natively.
     Kafka does not support prioritization.

  5. Short-Lived Tasks With Immediate Results
     Processing timeout makes sense.
     Retry with DLQ is built into the broker.

  6. Low Latency for Simple Tasks
     Sub-millisecond delivery at modest volumes.
```

## Honest Comparison by Parameter

```txt
┌───────────────────────┬──────────────────────────┬──────────────────────────┐
│ Parameter             │ Kafka                    │ RabbitMQ                 │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ Storage model         │ Log (append-only)        │ Queue (deleted after ack)│
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ Retention             │ Time/size-based          │ Until read + ack         │
│                       │ (independent of reads)   │                          │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ Replay                │ Yes — rewind the offset  │ No                       │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ Multiple consumers    │ Yes — consumer groups,   │ Limited — each queue     │
│                       │ each group gets all      │ consumed by one set      │
│                       │ messages                 │ of consumers             │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ Throughput            │ Very high (millions/sec) │ Medium-high              │
│                       │                          │ (thousands–hundreds of   │
│                       │                          │ thousands/sec)           │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ Latency               │ Milliseconds (pull)      │ Sub-millisecond (push)   │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ Routing               │ In client code           │ In the broker            │
│                       │ (dumb broker)            │ (smart broker, Exchange) │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ Ordering              │ Guaranteed within        │ Guaranteed within        │
│                       │ a partition              │ a single queue           │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ Operational           │ Higher: brokers,         │ Lower: simpler to set up │
│ complexity            │ partitions, replication, │ and manage               │
│                       │ ZooKeeper/KRaft          │                          │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ Dead Letter           │ DLT pattern via code     │ Built into broker (DLX)  │
│                       │ (not broker-native)      │                          │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ Message               │ Not supported            │ Priority queues          │
│ prioritization        │                          │ (native)                 │
└───────────────────────┴──────────────────────────┴──────────────────────────┘
```

## An Honest Note About Real-World Choices

The textbook answer to "Kafka or RabbitMQ?" is "look at your requirements: do you need replay? high throughput? complex routing?" That's the right answer. But in practice, it's a bit more nuanced.

**Many teams choose a tool not based on technical fit, but based on what their cloud provider offers:**

```txt
AWS:
  → Amazon MSK (Managed Streaming for Kafka) — Kafka
  → Amazon SQS — simple queue (not RabbitMQ, but analogous for task queues)
  → Amazon SNS — pub/sub on top of SQS

GCP:
  → Google Cloud Pub/Sub — managed messaging (semantics closer to Kafka,
    but not Kafka)

Azure:
  → Azure Event Hubs — Kafka-compatible API (managed Kafka)
  → Azure Service Bus — RabbitMQ-like messaging

Confluent Cloud:
  → Fully managed Kafka with additional tooling
    (Schema Registry, ksqlDB, Kafka Connect)
```

Choosing "Kafka" often means "MSK" or "Confluent Cloud," not running your own cluster. This reduces operational burden but adds vendor lock-in and cost.

**Another reality**: many startups begin with RabbitMQ (easier to spin up, less overhead) and migrate to Kafka as load grows or when replay/event sourcing becomes a requirement. Kafka is not automatically the better choice for every new project.

## Scenario: Order Service — What to Choose?

To make the choice concrete, consider a specific scenario:

**Requirements**: when an order is placed, send an email, reserve inventory, and record an analytics event.

```txt
Option A: RabbitMQ
  Order Service
    │── publish → "email" exchange → Email Queue → Email Worker
    │── publish → "inventory" exchange → Inventory Queue → Inventory Worker
    └── publish → "analytics" exchange → Analytics Queue → Analytics Worker

  Pros: simple, tasks are independent, each worker does one thing
  Cons: Order Service knows about three downstream systems;
        a new consumer (e.g., recommendations) requires changes to
        Order Service; no replay if analytics is down for 2 hours

Option B: Kafka
  Order Service
    └── publish → topic "order-placed" (key: orderId)

  Email Consumer Group     ← reads "order-placed"
  Inventory Consumer Group ← reads "order-placed"
  Analytics Consumer Group ← reads "order-placed"

  Pros: Order Service has no knowledge of downstream systems;
        a new consumer (recommendations) is just a new group,
        Order Service doesn't change; analytics down 2 hours →
        restarts → processes everything from last offset
  Cons: more infrastructure; overkill if you only need simple
        fire-and-forget tasks with no replay
```

**Decision rule**: if you have **one event → multiple independent consumers** and/or **need replay** — Kafka. If **one task → one worker** with no need to re-read — RabbitMQ (or SQS).

## Common Interview Traps

**"Kafka is faster than RabbitMQ — so you should always choose Kafka"**

Wrong selection criterion. RabbitMQ has sub-millisecond latency and handles hundreds of thousands of messages per second — more than sufficient for most task-queue scenarios. Kafka is indeed faster at very high throughput (millions of messages/sec), but that's not an argument for "send 1000 emails per day."

**"Kafka replaces RabbitMQ"**

No. Kafka can't do what RabbitMQ does: message prioritization, built-in DLX, rich broker-level routing via Exchanges, RPC patterns with reply queues. These are different tools for different problems — not versions of the same thing.

**"RabbitMQ is legacy — everyone is moving to Kafka"**

This is industry hype, not fact. RabbitMQ is actively developed (3.x → 4.x), runs in millions of production systems, and remains the right choice for task queues, simple messaging patterns, and environments with moderate throughput requirements.

**"Need pub/sub → need Kafka"**

Not necessarily. RabbitMQ fanout exchanges implement pub/sub. Amazon SNS + SQS implements pub/sub without Kafka. Kafka is one way to implement pub/sub, not the only way. Choosing Kafka is justified when you also need replay, long-term retention, or very high throughput.

**"We're on AWS — so we should use SQS instead of Kafka"**

SQS and Kafka are different tools. SQS is a managed task queue (closer to RabbitMQ in model). Amazon MSK is managed Kafka. The choice between them follows the same logic: need replay? → MSK. Simple task queues? → SQS.
