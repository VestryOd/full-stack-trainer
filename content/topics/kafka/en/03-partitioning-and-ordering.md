# Partitioning and Message Ordering

## How a Producer Chooses a Partition

When a producer sends a message, it must decide which of the topic's N partitions to write to. This decision is made **on the client side** (not by the broker) using one of three strategies:

### Strategy 1: Key-Based Partitioning

If a message is sent with a key (key ≠ null), Kafka calculates the partition using:

```txt
partition = murmur2(key) % numPartitions
```

`murmur2` is a non-cryptographic hash function. Crucially: the same key **always** maps to the same partition (as long as partition count doesn't change).

```txt
Topic "order-events" (4 partitions):

hash("order-101") % 4 = 2   and   hash("order-202") % 4 = 0

{ key: "order-101", value: "placed"    } → Partition 2
{ key: "order-101", value: "shipped"   } → Partition 2
{ key: "order-101", value: "delivered" } → Partition 2
{ key: "order-202", value: "placed"    } → Partition 0
```

Result: every event for `order-101` lands in Partition 2. Their order is therefore guaranteed, and one consumer processes them in the correct sequence.

### Strategy 2: Round-Robin (No Key)

If no key is set (key = null), the producer distributes messages evenly across partitions in a round-robin fashion:

```txt
Topic "logs" (3 partitions), key = null:

Message 1 → Partition 0
Message 2 → Partition 1
Message 3 → Partition 2
Message 4 → Partition 0
Message 5 → Partition 1
...
```

Advantage: even load distribution. Disadvantage: no ordering guarantees — messages 1, 4, 7 (in partition 0) and 2, 5, 8 (in partition 1) are read in parallel by different consumers.

> **Note on the sticky partitioner**: since Kafka 2.4 the default for `key=null` is the sticky partitioner. The producer fills a whole batch in one partition, then switches to another. That cuts the number of broker requests, so latency drops. Ordering behaviour does not change.

### Strategy 3: Explicit Partition Assignment

A producer can specify the partition directly. Used rarely — for custom routing or testing:

```ts
await producer.send({
  topic: 'order-events',
  messages: [
    { partition: 2, key: 'order-101', value: JSON.stringify(event) }
  ]
});
```

## Why Ordering Is Only Guaranteed Within a Partition

This is the most common Kafka interview topic, and the answer needs to be understood mechanically — not just memorized.

### One Partition = One Log = One Order

A partition is a sequential, append-only file. Messages are written strictly one after another, with monotonically increasing offsets. They can only be read in the order they were written.

```txt
Partition 2:
  [off:0 "placed"]  [off:1 "payment-ok"]
  [off:2 "shipped"] [off:3 "delivered"]
  ───────────────────────────────────────────────────►
  Consumer reads strictly left to right: 0 → 1 → 2 → 3
```

The consumer assigned to Partition 2 will receive these messages in exactly this order. The guarantee is absolute.

### Multiple Partitions — No Global Ordering

When a topic has multiple partitions, different partitions are consumed in parallel by different consumers. There is no mechanism to synchronize their progress:

```txt
Topic "order-events" (3 partitions):

Partition 0: [order-A: placed] [order-D: placed] [order-A: shipped]
Partition 1: [order-B: placed] [order-B: payment-ok]
Partition 2: [order-C: placed] [order-C: shipped]
             [order-D: payment-ok]

Consumer A reads Partition 0: placed→A, placed→D, shipped→A
Consumer B reads Partition 1: placed→B, payment-ok→B
Consumer C reads Partition 2: placed→C, shipped→C, payment-ok→D

Question: which happened first — "order-A shipped" (P0, offset 2)
          or "order-D payment-ok" (P2, offset 2)?
Answer:   Kafka doesn't know. Offset 2 in P0 and offset 2 in P2
          are independent counters.
```

Kafka has no global timestamp for comparing messages across partitions. Every message does carry a timestamp, but it guarantees nothing about ordering when several producers write at the same time.

### Practical Takeaway: Use the Key to Isolate Ordering

If ordering matters for a specific entity (order, user, session), use its ID as the key:

```txt
✓ Correct — event ordering for an order is guaranteed:
  key = "order-101" → all its events land in the same partition

✗ Incorrect — one order's events may land in different partitions:
  key = null (or key = a new random UUID each time)
```

## How to Choose a Good Partition Key

Choosing a key means balancing three factors:

### 1. Ordering Guarantee (correctness)

The key should group messages whose relative order matters. Ask: "If these two events were swapped, would the logic break?"

```txt
✓ Good keys:
  - userId    (user events: registration → login → purchase)
  - orderId   (lifecycle: created → paid → shipped → delivered)
  - sessionId (session events)
  - deviceId  (device telemetry)

✗ Bad keys for ordering:
  - null             (no ordering at all)
  - timestamp        (every message gets a unique key → no grouping)
  - random UUID      (same problem)
```

### 2. Even Distribution (cardinality)

Poor distribution → one partition is overloaded while others are idle. This is called a **hot partition**:

```txt
Topic "events" (4 partitions), key = countryCode:

Russia:  ████████████████████ (70% of traffic) → P0 overloaded
Germany: ████ (15%)                             → P1 OK
France:  ███ (10%)                              → P2 OK
Other:   ██ (5%)                                → P3 idle

→ Consumer on P0 can't keep up. Lag grows.
  Consumers on P1, P2, P3 are underutilized.
  Adding more consumers doesn't help — the bottleneck is in P0.
```

```txt
✓ High cardinality (many unique values):
  - userId (millions of users → spread evenly across partitions)
  - orderId
  - sessionId

✗ Low cardinality (few unique values):
  - countryCode (10–200 values → easily creates a hot partition)
  - status ("active"/"inactive" — only 2 values)
  - isVip (boolean)
```

### 3. Stability of Partition Count

After increasing partition count, `hash(key) % numPartitions` yields a different result for the same keys. Messages with the same key start landing in a different partition → ordering is broken for new messages relative to old ones.

```txt
Before: 4 partitions
  hash("order-101") % 4 = 2  → Partition 2

After: 6 partitions
  hash("order-101") % 6 = 5  → Partition 5 (different!)

Old order-101 events are in Partition 2,
new order-101 events are in Partition 5 →
consumers read them independently → ordering is broken.
```

**Takeaway**: plan the partition count upfront, with room to grow. Increasing partitions is a painful operation when ordering matters.

Practical rule of thumb: provision 2–4x more partitions than your planned consumer count at launch.

## Rebalancing — What Happens When Group Membership Changes

**Rebalancing** is the process of redistributing partitions among consumers in a group. During a rebalance, **the entire group pauses processing** — this matters.

### What Triggers a Rebalance

```txt
1. A consumer joins the group
   (new instance started, horizontal scaling)

2. A consumer leaves the group gracefully
   (clean shutdown, deploying a new version)

3. A consumer is presumed dead
   (no heartbeat received within session.timeout.ms — default: 45s)

4. Partitions are added to a topic
   (topic configuration change)

5. A consumer changes its subscription
   (updated topic list)
```

### Rebalancing Mechanics

Prior to Kafka 2.3, Eager Rebalancing was used:

```txt
Eager Rebalancing (legacy protocol):

  Before:  P0→C1, P1→C2, P2→C3
  
  C4 joins:
  1. ALL consumers REVOKE all partitions (commit offsets, release)
  2. Group Coordinator (one of the brokers) recalculates assignments
  3. All consumers receive new assignments

  After:  P0→C1, P1→C2, P2→C3, P3→C4 (if 4 partitions exist)
          or P0→C1, P1→C2, P2→C4     (if C3 left)

  Problem: the pause covers revoking and recalculating
           every partition in the group
```

Since Kafka 2.3+: Cooperative (Incremental) Rebalancing:

```txt
Cooperative Rebalancing (new protocol):

  Before:  P0→C1, P1→C2, P2→C3

  C4 joins:
  1. Group Coordinator identifies the minimal diff
  2. Only P2 is revoked from C3 (others keep processing)
  3. P2 is assigned to C4

  After:  P0→C1, P1→C2, P2→C4

  Advantage: only affected partitions pause;
             the rest continue processing without interruption
```

In `kafkajs`, cooperative rebalancing is enabled via the `partitionAssigners` configuration option.

### session.timeout.ms vs heartbeat.interval.ms

```txt
heartbeat.interval.ms (default: 3000ms)
  — how often a consumer sends "I'm alive" to the broker
  — should be significantly smaller than session.timeout.ms

session.timeout.ms (default: 45000ms, min: 6000ms)
  — no heartbeat within this window → the consumer is dead
  — broker initiates a rebalance

max.poll.interval.ms (default: 300000ms = 5 minutes)
  — maximum time between two poll() calls
  — processing one message longer than this → consumer is stuck
  — broker rebalances even if heartbeats still arrive
```

A typical real-world problem runs like this:

1. A consumer spends 6 minutes on one heavy message.
2. That exceeds `max.poll.interval.ms`, which defaults to 5 minutes.
3. The broker drops the consumer from the group and starts a rebalance.
4. Another consumer picks up the same message and processes it a second time.

Fix: either increase `max.poll.interval.ms`, reduce `max.poll.records` (fetch fewer messages per poll), or speed up message processing.

## The Full Picture: Key → Partition → Ordering

```txt
Producer sends order events:

  { key: "ord-1", event: "placed"  }
  { key: "ord-2", event: "placed"  }
  { key: "ord-1", event: "paid"    }
  { key: "ord-3", event: "placed"  }        hash(key) % 3
  { key: "ord-1", event: "shipped" }   ────────────────────►
  { key: "ord-2", event: "paid"    }
  { key: "ord-3", event: "shipped" }

  P0: [ord-2:placed] [ord-2:paid]
  P1: [ord-1:placed] [ord-1:paid] [ord-1:shipped]
  P2: [ord-3:placed] [ord-3:shipped]

Consumer Group (3 consumers):
  Consumer A reads P0 → ord-2 events in strict order ✓
  Consumer B reads P1 → ord-1 events in strict order ✓
  Consumer C reads P2 → ord-3 events in strict order ✓

  Global ordering across ord-1, ord-2, ord-3 — not guaranteed ✗
  (but we don't need it: orders are independent)
```

## Common Interview Traps

**"Kafka guarantees message ordering"**

Incomplete. Kafka guarantees ordering **within a partition**. With multiple partitions, global ordering is not guaranteed. The correct answer: "Kafka guarantees ordering within a partition. To guarantee ordering for a specific entity's events, use its ID as the message key — all its events will land in the same partition."

**"You can increase partition count without affecting ordering"**

No. After the increase, `hash(key) % newCount` maps the same keys to different partitions. New events for an entity land in a different partition than old events → relative ordering between old and new events is broken. Partition count must be planned upfront.

**"A hot partition is fine — one consumer will just be slower"**

It's worse than it sounds. The consumer on the hot partition becomes a bottleneck for the whole group, and its lag grows. Lag is the number of messages between the offset a consumer has committed and the end of the partition.

You can't "help" it by adding another consumer to the same partition — one partition, one consumer per group. You need to either change the partition key or split the hot stream across multiple topics.

**"Rebalancing is instantaneous"**

No. During eager rebalancing, the entire group pauses: all consumers revoke their partitions, wait for the coordinator, then receive new assignments. On a large cluster with slow consumers, this can take several seconds. This is exactly why cooperative rebalancing (Kafka 2.3+) exists.

**"If a consumer crashes and restarts, unacknowledged messages are lost"**

No — with correctly configured offsets. The consumer resumes from the last committed offset. If it crashed before committing, it re-reads messages from the last commit. This is at-least-once semantics — messages are reprocessed, not lost. Covered in detail in the delivery guarantees article.
