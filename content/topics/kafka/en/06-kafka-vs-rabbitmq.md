# Kafka vs RabbitMQ

## The Philosophical Difference: Log vs Queue

This is not a comparison of which one is faster or which one is more reliable. Kafka and RabbitMQ solve fundamentally different problems, because they are built on different storage models.

```txt
                RabbitMQ — the queue model
┌───────────────────────────────────────────────────────┐
│ The broker keeps a message until it has been read and │
│ acknowledged (ack). After the ack it is deleted.      │
│                                                       │
│ Producer ──▶ [msg1][msg2][msg3]                       │
│ a consumer reads msg1                                 │
│          ──▶ [msg2][msg3]        msg1 is gone         │
└───────────────────────────────────────────────────────┘

                  Kafka — the log model
┌───────────────────────────────────────────────────────┐
│ The broker keeps the log (append-only) until the      │
│ retention period expires — whether the message was    │
│ read or not.                                          │
│                                                       │
│ offset:      0     1     2     3     4                │
│           [msg1][msg2][msg3][msg4][msg5]              │
│                                                       │
│ Consumer A: offset=2  (has read 0 and 1)              │
│ Consumer B: offset=0  (reading from the start)        │
│ Consumer C: offset=4  (close to real time)            │
│                                                       │
│ msg1..msg5 are all still in the log                   │
└───────────────────────────────────────────────────────┘
```

Everything else follows from this difference: failure behavior, scaling, multi-consumer support, replay capability.

## Retention: How Long Data Is Kept

```txt
RabbitMQ — event-driven retention:
  A message exists ONLY until it is consumed.
  Read + ack → deleted immediately.
  No ack within N seconds → requeue (back to the queue).
  Optionally: a dead letter queue for failed messages.

  Problem: you cannot rewind. If an analytics service was not
  reading the queue for 2 hours, those 2 hours of events are
  gone forever.

Kafka — time-based retention:
  A message is stored for N days (retention.ms) or up to
  M bytes (retention.bytes), REGARDLESS of whether it was read.

  Default: 7 days. Configurable per topic:
    retention.ms=-1 → keep forever (compact topics)
    retention.ms=3600000 → 1 hour
    retention.bytes=1073741824 → delete oldest when over 1GB

  Advantage: analytics service down for 2 hours → restarts from
  its last offset → catches up on everything it missed.
  No data loss.
```

This isn't just a technical detail — it's Kafka's core architectural value. The log is the source of truth. A new service can subscribe and receive the entire history of events from the beginning. RabbitMQ offers no such capability.

## Delivery Model: Push vs Pull

```txt
RabbitMQ — push model:
  The broker pushes messages to its subscribers.
  The consumer limits the flow with a prefetch window,
  which is how RabbitMQ does backpressure: basic.qos caps
  how many unacknowledged messages the broker may hand
  out at once.

  Pro: low latency, sub-millisecond for simple tasks
  Con: the window is chosen up front, so a wrong prefetch
       value can still bury a slow consumer

Kafka — pull model:
  The consumer polls the broker itself (poll).
  The consumer limits the flow per fetch:
  max.poll.records and fetch.max.bytes cap how much
  a single poll returns.
  The broker knows nothing about consumer state, except
  the committed offsets.

  Pro: the consumer is never overwhelmed and reads at its
       own pace
  Con: slightly higher latency for real-time tasks, though
       usually under 10 ms

Both sides can limit the flow. The difference is who starts
the transfer, not who holds the control.
```

## Routing: Where Logic Lives

```txt
RabbitMQ — smart routing in the broker:

  ┌────────────────────────────────────────────────┐
  │ RabbitMQ broker                                │
  │                                                │
  │ Producer ──▶ Exchange ──▶ Bindings ──▶ Queue A │
  │                                        Queue B │
  │                                        Queue C │
  │                                                │
  │ Queue A ──▶ Consumer A                         │
  │ Queue B ──▶ Consumer B                         │
  │ Queue C ──▶ Consumer C                         │
  └────────────────────────────────────────────────┘

  Exchange types:
  - direct:  exact routing key match
  - fanout:  broadcast to all queues
  - topic:   wildcards in routing key (orders.*, *.critical)
  - headers: route by message headers

  Rich routing is RabbitMQ's strength.
  Complex topologies can be wired directly in the broker.

Kafka — routing in client code:
  The broker just stores topics.
  All logic of "which consumer reads what" lives in
  application code.

  Need fanout? → multiple consumer groups read the same topic.
  Need filtering? → the consumer reads everything, filters itself.
  Need routing? → the producer picks the topic by condition.

  This is not a weakness — it is the deliberate simplicity of
  the "dumb broker" philosophy.
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

| Parameter | Kafka | RabbitMQ |
|---|---|---|
| Storage model | Log (append-only) | Queue (deleted after ack) |
| Retention | By time or size, independent of reads | Until read and acknowledged |
| Replay | Yes — rewind the offset | No |
| Multiple consumers | Yes — consumer groups, each group gets every message | Limited — each queue is consumed by one set of consumers |
| Throughput | Very high: millions of messages per second | Tens of thousands per second per queue, roughly 50 thousand per node across several queues |
| Latency | Milliseconds (pull) | Sub-millisecond (push) |
| Flow control | Consumer pulls; `max.poll.records` and `fetch.max.bytes` cap a fetch | Broker pushes; `basic.qos` prefetch caps unacknowledged messages |
| Routing | In client code (dumb broker) | In the broker (smart broker, exchanges) |
| Ordering | Guaranteed within a partition | Guaranteed within a single queue |
| Operational complexity | Higher: brokers, partitions, replication, ZooKeeper or KRaft | Lower: simpler to set up and manage |
| Dead letter handling | Dead Letter Topic pattern written in code, not broker-native | Built into the broker: a dead letter exchange (DLX) |
| Message prioritization | Not supported | Priority queues, natively |

## An Honest Note About Real-World Choices

The textbook answer to "Kafka or RabbitMQ?" is "look at your requirements: do you need replay? high throughput? complex routing?" That's the right answer. But in practice, it's a bit more nuanced.

**Many teams choose a tool not based on technical fit, but based on what their cloud provider offers:**

```txt
AWS:
  → Amazon MSK (Managed Streaming for Kafka) — Kafka
  → Amazon SQS — a simple queue (not RabbitMQ, but an
    analogue for task queues)
  → Amazon SNS — pub/sub on top of SQS

GCP:
  → Google Cloud Pub/Sub — managed messaging
    (semantics closer to Kafka, but not Kafka)

Azure:
  → Azure Event Hubs — Kafka-compatible API (managed Kafka)
  → Azure Service Bus — RabbitMQ-like messaging

Confluent Cloud:
  → Fully managed Kafka with additional tooling
    (Schema Registry, ksqlDB, Kafka Connect)
```

Choosing Kafka usually means Amazon MSK (Managed Streaming for Kafka) or Confluent Cloud, not running your own cluster. That reduces the operational burden, but it adds vendor lock-in and cost.

**Another reality**: many startups begin with RabbitMQ, which is easier to set up and carries less overhead. They move to Kafka as the load grows, or when replay and event sourcing become a requirement. Kafka is not automatically the better choice for every new project.

## Scenario: Order Service — What to Choose?

To make the choice concrete, consider a specific scenario:

**Requirements**: when an order is placed, send an email, reserve inventory, and record an analytics event.

```txt
Option A: RabbitMQ
  Order Service publishes three times:
  │── "email" exchange → Email Queue → Email Worker
  │── "inventory" exchange → Inventory Queue → Inventory Worker
  └── "analytics" exchange → Analytics Queue → Analytics Worker

  Pros: simple, tasks are independent, each worker does one thing
  Cons: Order Service knows about three downstream systems;
        a new consumer (recommendations) means changing
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

**Decision rule**: if you have **one event → multiple independent consumers** and/or **need replay** — Kafka. If **one task → one worker** with no need to re-read — RabbitMQ, or Amazon SQS (Simple Queue Service).

## Common Interview Traps

**"Kafka is faster than RabbitMQ — so you should always choose Kafka"**

Wrong selection criterion. RabbitMQ has sub-millisecond latency and handles tens of thousands of messages per second per queue. Spread over several queues that is roughly 50 thousand per node, which is more than enough for most task-queue scenarios.

Kafka is an order of magnitude higher, because it appends to a sequential log and batches the writes. But that is not an argument for sending 1000 emails a day.

**"Kafka replaces RabbitMQ"**

No. There are things RabbitMQ does that Kafka cannot:

- message prioritization;
- a built-in dead letter exchange (DLX);
- rich broker-level routing through exchanges;
- remote procedure call (RPC) patterns with reply queues.

These are different tools for different problems, not versions of the same thing.

**"RabbitMQ is legacy — everyone is moving to Kafka"**

This is industry hype, not fact. RabbitMQ is actively developed, from the 3.x line into 4.x, and runs in millions of production systems. It remains the right choice for task queues, simple messaging patterns, and moderate throughput.

**"Need pub/sub → need Kafka"**

Not necessarily. RabbitMQ fanout exchanges implement pub/sub. So does Amazon SNS (Simple Notification Service) together with SQS, without any Kafka. Kafka is one way to implement pub/sub, not the only way. Choosing Kafka is justified when you also need replay, long-term retention, or very high throughput.

**"We're on AWS — so we should use SQS instead of Kafka"**

Amazon Web Services (AWS) offers both, and they are different tools. Amazon SQS is a managed task queue, closer to RabbitMQ in model. Amazon MSK is managed Kafka. The choice between them follows the same logic: need replay? → MSK. Simple task queues? → SQS.
