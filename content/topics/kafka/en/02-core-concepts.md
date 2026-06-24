# Kafka Core Concepts

## Topic

A **topic** is a named channel into which producers write messages and from which consumers read them. Think of it as a folder containing an event journal of a specific type.

```txt
topic: "order-placed"       topic: "payment-completed"    topic: "user-registered"
┌──────────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
│ [order1][order2]...  │    │ [pay1][pay2][pay3]...│    │ [usr1][usr2]...      │
└──────────────────────┘    └──────────────────────┘    └──────────────────────┘
```

A topic is the logical unit of data organization. Physically, a topic is divided into **partitions**, which store the actual data.

Key topic properties:
- Topic name is a string (e.g., `"order-placed"`, `"user-events"`)
- Partition count is set at creation time (can be increased, never decreased)
- Retention period (`retention.ms`) is configured per topic
- Any number of consumer groups can read the same topic — data is shared

## Partition

A **partition** is a physical subdivision of a topic: an ordered, immutable log of messages stored on the disk of a single broker.

Each topic is divided into N partitions (N ≥ 1). Partitions are what enables Kafka to scale horizontally.

```txt
Topic "order-placed" with 3 partitions:

Partition 0:  [order-A] [order-B] [order-C] [order-D] ──► new messages appended here
              offset: 0    1         2         3

Partition 1:  [order-E] [order-F] [order-G] ──► ...
              offset: 0    1         2

Partition 2:  [order-H] [order-I] ──► ...
              offset: 0    1
```

**Why do partitions exist?**

A single log file means a single CPU thread for reads and writes — a bottleneck. Partitions break this constraint:

1. **Write parallelism**: a producer can write to partition 0, 1, and 2 simultaneously
2. **Read parallelism**: each partition can be consumed by a separate consumer — 3 partitions = 3 parallel consumers in one group
3. **Distribution across brokers**: each partition lives on a specific broker (with replicas on others), spreading the load across the cluster

```txt
Kafka Cluster with 3 brokers, Topic with 3 partitions:

Broker 1          Broker 2          Broker 3
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ P0 (leader) │   │ P1 (leader) │   │ P2 (leader) │
│ P1 (replica)│   │ P2 (replica)│   │ P0 (replica)│
│ P2 (replica)│   │ P0 (replica)│   │ P1 (replica)│
└─────────────┘   └─────────────┘   └─────────────┘
```

The **leader** is the partition copy that accepts writes from producers. A **replica** is a copy that stays in sync with the leader. If the broker holding the leader crashes, one of the replicas is automatically promoted to the new leader.

## Offset

An **offset** is the sequence number of a message within a specific partition. It starts at 0 and increases monotonically.

```txt
Partition 0:
  offset 0: { key: "user-1", value: "order placed" }
  offset 1: { key: "user-2", value: "order placed" }
  offset 2: { key: "user-1", value: "order shipped" }
  offset 3: { key: "user-3", value: "order placed" }
              ↑
        consumer reads from here → has read up to and including offset 2
```

**Critical property**: offset is **per-partition**, not global across the topic. Offset 5 in partition 0 and offset 5 in partition 1 are completely different messages.

Additionally, Kafka stores offsets **per-consumer-group** (more on this below). This means two different groups can read the same topic independently, each with its own set of offsets.

```txt
Topic "order-placed", Partition 0:
[msg0][msg1][msg2][msg3][msg4][msg5]

Consumer Group "search-service":   offset = 5 (fully caught up)
Consumer Group "analytics":        offset = 3 (2 messages behind)
Consumer Group "audit-log":        offset = 0 (just started, reading from the beginning)
```

A consumer **commits its offset** — saves it to Kafka's internal `__consumer_offsets` topic, signaling "I have processed up to this point." Commit strategies are covered in detail in the Kafka in Node.js article.

## Producer

A **producer** is a client that writes messages into a topic.

The producer decides:
1. **Which topic** to write to (required)
2. **Which key** to use — determines which partition the message lands in
3. **Which headers** to attach — metadata (schema version, trace ID, etc.)

```txt
Producer → [topic: "order-placed", key: "user-123", value: { orderId: 42, ... }]
                │
                ▼
         Kafka selects a partition:
         - key provided → hash(key) % numPartitions → always the same partition for the same key
         - key = null → round-robin across partitions (even distribution)
```

A key is not a unique message identifier. It's a tool for **controlling partitioning**: all messages with the same key are guaranteed to land in the same partition → their ordering is guaranteed.

## Consumer

A **consumer** is a client that reads messages from a topic. A consumer subscribes to a topic and Kafka assigns it partitions.

Consumers operate in a **pull model**: the consumer polls the broker (`poll()`), rather than the broker pushing messages to the consumer. This differs from some other systems and from HTTP webhooks. The pull model lets consumers read at their own pace without being overwhelmed.

```ts
// Simplified consumer loop (pseudocode)
while (true) {
  const messages = consumer.poll(timeout: 1000ms); // pull from broker
  for (const message of messages) {
    await processMessage(message);
  }
  consumer.commitOffset(); // save progress
}
```

## Consumer Group — How Kafka Combines Pub/Sub and Queue in One

A **consumer group** is a named group of consumer processes that collectively read a topic.

The partition assignment rule: **each partition is assigned to exactly one consumer within the group**.

This rule is the key to understanding how Kafka implements two fundamentally different patterns depending on configuration:

### Pattern 1: Parallel Processing (queue-like)

One group, multiple consumers — each reads its own partition:

```txt
Topic "orders" (3 partitions), Consumer Group "order-processor":

Partition 0 ──► Consumer A  (processes one third of all orders)
Partition 1 ──► Consumer B  (processes one third of all orders)
Partition 2 ──► Consumer C  (processes one third of all orders)

→ Horizontal scaling: add a consumer → add a partition → load is split
→ Each message is processed by EXACTLY ONE consumer in the group
```

This is the analogue of a classic queue with multiple workers. But with a key difference: if Consumer A crashes, its partitions are automatically redistributed to B and C (rebalance).

### Pattern 2: Pub/Sub (every group gets a full copy)

Multiple groups, each receiving all messages:

```txt
Topic "order-placed" (3 partitions):

Consumer Group "search-service":
  Partition 0 ──► Search Consumer 1
  Partition 1 ──► Search Consumer 2
  Partition 2 ──► Search Consumer 3

Consumer Group "analytics-service":
  Partition 0 ──► Analytics Consumer 1
  Partition 1 ──► Analytics Consumer 2
  Partition 2 ──► Analytics Consumer 3

→ Each group receives ALL messages in the topic
→ Groups are completely independent: their offsets are unrelated
```

This is pub/sub: one "order placed" event → both search and analytics receive it in full.

### The Parallelism Ceiling

The maximum number of "useful" consumers in a group equals the number of partitions. Extra consumers beyond that sit idle:

```txt
3 partitions, 5 consumers in one group:

Partition 0 ──► Consumer A  ✓ active
Partition 1 ──► Consumer B  ✓ active
Partition 2 ──► Consumer C  ✓ active
(no partition)  Consumer D  ✗ idle (receives no messages)
(no partition)  Consumer E  ✗ idle (receives no messages)
```

Consumers D and E are ready to take over a partition if A, B, or C fails — they act as standby. But you can't get more active consumers than partitions without increasing the partition count.

## Broker

A **broker** is a single Kafka node (server/process). It accepts writes from producers, stores partitions on disk, and serves data to consumers.

A single broker can store hundreds of partitions from different topics. Brokers communicate with each other for data replication.

```txt
A broker is:
  - A Kafka process (JVM)
  - A partition store (file segments on disk)
  - A server for producers and consumers
  - A replication participant

A broker is NOT:
  - A separate database
  - Aware of consumer state (beyond offsets in __consumer_offsets)
  - A "smart" router (the client library handles that)
```

## Cluster

A **cluster** is a group of brokers working together. Historically (with ZooKeeper), one broker took on the role of Controller — coordinating partition leader elections and tracking cluster state.

```txt
Minimal production cluster (3 brokers):

  ┌──────────┐    ┌──────────┐    ┌──────────┐
  │ Broker 1 │◄──►│ Broker 2 │◄──►│ Broker 3 │
  │          │    │(Controller│    │          │
  └──────────┘    └──────────┘    └──────────┘
        │              │               │
        └──────────────┴───────────────┘
                    Replication

  3 brokers → cluster survives the failure of 1 broker (with replication factor = 3)
```

Why at least 3? The quorum principle: a majority (2 of 3) is needed for agreement. With 2 brokers, the cluster can't survive the loss of one — there's no quorum.

## ZooKeeper vs KRaft — What Changed and Why

Historically, Kafka used **ZooKeeper** (Apache ZooKeeper) — a separate coordination service — for:
- Storing cluster metadata (which brokers exist, which partition is on which broker)
- Electing the Controller leader
- Storing topic configurations

```txt
Kafka with ZooKeeper (pre-Kafka 3.x):

  ┌─────────────────────┐    ┌──────────┐
  │    ZooKeeper        │    │ Broker 1 │
  │   (separate         │◄──►│ Broker 2 │
  │    cluster!)        │    │ Broker 3 │
  └─────────────────────┘    └──────────┘
  
  → Must run and maintain 2 separate clusters
  → ZooKeeper became a bottleneck at large scale
  → Complex operations: config changes required ZooKeeper coordination
```

**KRaft** (Kafka Raft, KIP-500) is Kafka's built-in consensus protocol, replacing ZooKeeper:

```txt
Kafka with KRaft (Kafka 3.3+, default since Kafka 4.0):

  ┌──────────────────────────────────────────────┐
  │           Kafka Cluster                       │
  │                                               │
  │  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
  │  │ Broker 1 │  │ Broker 2 │  │ Broker 3 │   │
  │  │(Controller│  │          │  │          │   │
  │  │  mode)   │  │          │  │          │   │
  │  └──────────┘  └──────────┘  └──────────┘   │
  │                                               │
  │  Metadata stored inside the cluster           │
  │  in a dedicated internal topic                │
  └──────────────────────────────────────────────┘
  
  → One cluster instead of two
  → Faster controller failover (milliseconds vs. seconds)
  → Support for millions of partitions (ZooKeeper scaled poorly)
```

**In practice**: for any new project today, use KRaft. ZooKeeper mode is deprecated and removed in Kafka 4.x. Most managed services (Confluent Cloud, AWS MSK) have already migrated to KRaft transparently.

## All Concepts Together

```txt
                         KAFKA CLUSTER
┌──────────────────────────────────────────────────────────────────┐
│                                                                    │
│   Topic "order-placed"                                             │
│   ┌──────────────────────────────────────────────────────────┐    │
│   │  Partition 0 (Broker 1):  [off:0][off:1][off:2][off:3]  │    │
│   │  Partition 1 (Broker 2):  [off:0][off:1][off:2]         │    │
│   │  Partition 2 (Broker 3):  [off:0][off:1][off:2][off:3]  │    │
│   └──────────────────────────────────────────────────────────┘    │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
         ▲                              │
         │ write                        │ read (poll)
         │                              ▼
   ┌──────────┐         Consumer Group "analytics" (separate offset)
   │ Producer │         ┌──────────────────────────────────────────┐
   │          │         │ Consumer A ◄── Partition 0 (offset: 2)  │
   └──────────┘         │ Consumer B ◄── Partition 1 (offset: 1)  │
                        │ Consumer C ◄── Partition 2 (offset: 3)  │
                        └──────────────────────────────────────────┘

                        Consumer Group "search" (separate offset)
                        ┌──────────────────────────────────────────┐
                        │ Consumer X ◄── Partition 0 (offset: 3)  │
                        │ Consumer Y ◄── Partition 1 (offset: 2)  │
                        │ Consumer Z ◄── Partition 2 (offset: 3)  │
                        └──────────────────────────────────────────┘
```

## Common Interview Traps

**"A consumer group is multiple consumers that duplicate each other's work"**

No. Within a group, each partition is assigned to exactly one consumer — there's no duplication. Duplication occurs between groups: group A and group B both receive all topic messages, but that's the pub/sub pattern by design, not a bug.

**"Offset is a global counter across the whole topic"**

No. Offset is unique within a partition. A topic with 3 partitions has three independent offset sequences: 0..N in partition 0, 0..M in partition 1, 0..K in partition 2. There is no such thing as "offset 42 in the topic."

**"Adding more consumers to a group gives linear throughput gains"**

Only up to the partition count. Beyond that, extra consumers just sit idle. The real lever for throughput is increasing partition count (plus matching consumers).

**"Multiple consumers from the same group can read one partition in parallel"**

No. One partition → one consumer per group. This is a deliberate design constraint: it's what guarantees ordered processing within a partition.

**"ZooKeeper is always required to run Kafka"**

Outdated. Since Kafka 3.3+, KRaft is production-ready and the recommended default. Since Kafka 4.0, ZooKeeper mode has been removed entirely.
