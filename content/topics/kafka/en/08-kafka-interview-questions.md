# Kafka — Interview Questions

## Group 1: Fundamentals (Junior)

**What is Kafka? How does it fundamentally differ from a message queue?**

Kafka is a **distributed log**, not a message queue. The difference is architectural: in a queue (RabbitMQ, SQS), a message is **deleted** after it's read and acknowledged. In Kafka, a message stays in the log regardless of whether it's been read — until a configured retention period expires (`retention.ms`). This allows multiple consumers to read the same stream independently, and new services to replay the entire event history from the beginning. Kafka doesn't route messages — the broker simply stores the log, and each consumer tracks its own read position (offset). This is called the "dumb broker, smart consumer" philosophy.

---

**Explain the trio: topic, partition, offset.**

A **topic** is a named channel — a logical category of events (e.g., `"order-events"`). It's an abstraction; data is physically stored in partitions. A **partition** is the physical subdivision of a topic: an ordered, append-only log on the disk of a single broker. Partitions are the source of scalability: N partitions = N parallel consumers in one group. An **offset** is the sequence number of a message within a specific partition, starting at 0. The critical point: offset is **per-partition**, not global. Offset 5 in partition 0 and offset 5 in partition 1 are different messages. Each consumer independently tracks and commits its own offset.

---

**What is a Consumer Group and which two patterns does it enable?**

A **Consumer Group** is a named group of consumer processes that collectively read a topic. Rule: each partition is assigned to exactly one consumer within the group. This enables two patterns: (1) **Queue-like (parallel processing)** — one group, multiple consumers. Partitions are split between them. Each message is processed by exactly one consumer. Adding consumers scales throughput (up to the partition count). (2) **Pub/Sub** — multiple groups, each receiving all topic messages. A `search-service` group and an `analytics-service` group read the same topic independently, each maintaining their own offsets.

---

**What does "dumb broker, smart consumer" mean and why is it an architectural choice, not a limitation?**

In RabbitMQ, the broker is smart: it tracks the state of every queue, actively pushes messages to consumers, deletes them after ack, and manages routing. In Kafka, the broker is "dumb": it simply stores the log on disk and serves data on request. Consumers know their own offset and call `poll()` themselves (pull model). This is a deliberate architectural choice with three advantages: (1) horizontal scalability — the broker stores no per-consumer state, only data; (2) consumers read at their own pace, never getting overwhelmed; (3) replay — a consumer can reset its offset backward and re-read history. In RabbitMQ, replay is impossible: data is deleted after consumption.

---

**Why doesn't Kafka delete a message after it's read? What does this enable in practice?**

Kafka stores the log by time (`retention.ms`, default 7 days) or volume (`retention.bytes`), regardless of whether the data was read. This enables three things: (1) **Multiple independent consumers** — Search, Analytics, and Fraud Detection all read the same topic independently; (2) **Replay after failure** — a service goes down for 2 hours, restarts, reads from its last committed offset, catches up on everything it missed without loss; (3) **New services** — a new ML service connects and reads the full 30-day event history from scratch, requiring zero changes to the producer. This is the fundamental difference from a queue, where none of this is possible.

---

## Group 2: Mechanics (Middle)

**Why does Kafka only guarantee ordering within a partition? How do you use this in practice?**

A partition is a sequential file — messages inside it are numbered and read strictly in order. With multiple partitions, each is consumed in parallel by a separate consumer — there's no mechanism to synchronize their progress. Offset 5 in partition 0 and offset 5 in partition 1 are independent counters; Kafka doesn't know which "happened first." **In practice**: if the order of events for a specific entity matters (order, user, session), use its ID as the message key. Then `hash(key) % numPartitions` always yields the same partition → all events for the entity land there → the consumer reads them in strict write order.

---

**How do you choose a good partition key? What is a hot partition and why is it dangerous?**

A good key: (1) **correctness** — groups messages whose relative order matters (orderId, userId); (2) **high cardinality** — many unique values → even distribution across partitions; (3) **stability** — if partition count increases, `hash(key) % N` yields a different partition → ordering breaks for new messages relative to old ones. A **hot partition** arises from low cardinality (e.g., key = `countryCode`): 70% of traffic goes to one partition, its consumer can't keep up, lag grows. The danger: you can't "help" it by adding consumers — one partition = one consumer per group. Fix: switch to a higher-cardinality key (userId instead of countryCode) or split the topic.

---

**What triggers a rebalance and what happens during one?**

A rebalance is triggered by: a new consumer joining the group; a consumer leaving gracefully (shutdown); a consumer failing to send a heartbeat within `session.timeout.ms` (default 45s) — considered dead; new partitions added to the topic. During **eager rebalancing** (legacy protocol): all consumers revoke all their partitions, the coordinator broker recalculates assignments, all consumers receive new ones. The entire group **pauses processing** during this. **Cooperative rebalancing** (Kafka 2.3+): only affected partitions are redistributed; unaffected consumers continue processing. Common real-world problem: a consumer processes a heavy message for longer than `max.poll.interval.ms` (default 5 minutes) → broker considers it stuck → rebalance → another consumer starts processing the same message → duplicate.

---

**What is the difference between auto-commit and manual commit? What delivery semantics does each provide?**

**Auto-commit** (`autoCommit: true`): kafkajs periodically commits the current offset by timer (`autoCommitInterval`) or message count. If the commit fires **before** processing finishes and the consumer crashes — the message is lost. Semantics: **at-most-once**. **Manual commit** (`autoCommit: false`): the developer explicitly calls `consumer.commitOffsets()` **after** successful processing. If the consumer crashes before committing — the message is re-read on restart. Semantics: **at-least-once**. In code: `{ offset: (Number(message.offset) + 1).toString() }` — commit the next offset, not the current one (this means "the next one for me is X, so X-1 has been processed").

```ts
// At-least-once: commit AFTER processing
await consumer.run({
  autoCommit: false,
  eachMessage: async ({ topic, partition, message }) => {
    await processEvent(JSON.parse(message.value!.toString()));
    await consumer.commitOffsets([{
      topic, partition,
      offset: (Number(message.offset) + 1).toString(),
    }]);
  },
});
```

---

**Why do you commit `offset + 1` and not `offset` itself?**

In Kafka, "committing offset X" means "the next message I want to receive is X." The commit signals that everything up to X-1 has been processed. So after successfully processing a message with `offset=5`, you commit `6`: "start sending me from 6." A common bug: `commitOffsets([{ offset: message.offset }])` — this means "next = 5," so message 5 will be re-read on the next restart. In kafkajs, `message.offset` is a string: `(Number(message.offset) + 1).toString()`.

---

**What is consumer lag and how do you deal with it?**

**Consumer lag** is the difference between the latest offset in a partition (end of the log, where the producer writes) and the group's current committed offset. Lag = 0: consumer is real-time. Growing lag: consumer can't keep up. Formula: `lag = latestOffset - committedOffset`. Causes: slow processing; external service throttling; synchronous calls blocking the event loop; traffic spike. Solutions: (1) add more consumers — but no more than the partition count; (2) increase partition count (and consumers); (3) optimize processing (batch DB writes, parallelize external calls); (4) increase `maxBytesPerPartition` for larger fetches. Monitoring: kafkajs Admin API, Kafka UI, Burrow, Datadog.

---

**What is a poison message and how do you handle it in Kafka?**

A poison message is one the consumer cannot process successfully: invalid JSON, incompatible schema, a bug in business logic. In Kafka this is especially dangerous: the broker doesn't remove it from the log, and with `autoCommit: false` the consumer receives it again and again after every restart — the entire partition is frozen, lag grows. Solution: the **Dead Letter Topic (DLT)** pattern. After N retries (usually 3 with exponential backoff), the message is sent to `original-topic.DLT` with error metadata in the headers, the offset is committed, and normal processing continues. A separate DLT consumer monitors these messages and fires alerts.

---

## Group 3: Reliability and Guarantees (Senior)

**Explain the three delivery semantics in Kafka: at-most-once, at-least-once, exactly-once.**

**At-most-once**: processed zero or one time. Loss is possible. Achieved with: `acks: 0` on the producer (fire-and-forget) or auto-commit before processing completes on the consumer. Acceptable for non-critical metrics. **At-least-once**: processed one or more times. Duplicates are possible, no loss. Achieved with: `acks: -1` on the producer + manual commit after processing. The standard in most production systems. **Exactly-once**: processed exactly once. Achieved via: (1) idempotent producer (eliminates write-side duplicates from retries) + Kafka Transactions (atomic consume + produce + commitOffset for Kafka→Kafka scenarios); or (2) at-least-once + idempotent consumer (more common in practice). Important: exactly-once via Kafka Transactions only works Kafka→Kafka. If the result is written to a database, the guarantee doesn't extend there.

---

**What is an idempotent producer and how does it prevent duplicates?**

Without an idempotent producer: producer sends a message, broker writes it, ACK lost in transit → producer retries → broker writes a duplicate. The idempotent producer fixes this with a **Producer ID (PID)** and **sequence number**: Kafka assigns each producer a unique PID; each message gets a monotonically increasing sequence number (per-partition). The broker tracks the last sequence from each PID and, on receiving a duplicate `(PID, seq)`, discards it and sends an ACK. In kafkajs: `kafka.producer({ idempotent: true })` — automatically sets `acks: -1` and unlimited retries. Limitation: only protects against duplicates from retries within a single write session to one partition.

---

**What are Kafka Transactions and when are they needed?**

Kafka Transactions allow you to atomically: read a message from topic A, process it, write the result to topic B, and commit the offset — all or nothing. If anything fails, the transaction is rolled back, the offset is not committed, and the consumer re-reads the original message. Needed for Kafka→Kafka scenarios: stream processing where results are written back into Kafka. Honest limitation: transactions work only within Kafka. If the result is written to PostgreSQL or an external API, the database is not part of the Kafka transaction — exactly-once doesn't apply there. This is exactly why most teams choose at-least-once + idempotent consumer over Kafka Transactions.

---

**What is an idempotent consumer? Give three implementation approaches.**

An idempotent consumer produces the same result when processing the same message a second time. Approaches: (1) **ON CONFLICT DO NOTHING** — use the entity's unique key on INSERT: `INSERT INTO orders (...) ON CONFLICT (id) DO NOTHING`. A duplicate call produces no error and no duplicate row. (2) **Optimistic locking / versioning** — `UPDATE orders SET status='paid', version=$2 WHERE id=$1 AND version=$2-1`. If the row was already updated (duplicate), `rowCount=0` and the handler simply returns. (3) **processed_events table** — before handling, `INSERT INTO processed_events (id) ON CONFLICT DO NOTHING RETURNING id`. If `rowCount=0` — already processed, skip. Key format: `${topic}-${partition}-${offset}`.

---

## Group 4: System Design (Senior+)

**Design a system where placing an order must trigger inventory reservation, email notification, and analytics — without tight coupling between services.**

Solution: Kafka as an event bus. Order Service publishes to topic `order-events` with key `orderId` — and knows nothing about downstream systems. Three independent consumer groups: `inventory-service` (reads `ORDER_CONFIRMED`, reserves stock with `ON CONFLICT DO NOTHING` for idempotency), `notification-service` (reads `ORDER_PLACED`, sends email — duplicate check via processed_events prevents double-send), `analytics-service` (at-most-once is fine — losing one metric isn't critical). Advantages: adding a new consumer (Fraud Detection) is just a new consumer group, Order Service unchanged. Analytics goes down → recovers from last offset, no data loss. Config: 12 partitions, key = orderId, retention 30 days.

---

**A consumer in your group has been stuck on the same message for 10 minutes. What happened and how do you fix it?**

Likely causes: (1) **Poison message** — invalid JSON or a logic bug; every attempt throws, consumer doesn't commit offset → receives the same message again. Fix: add DLT pattern with N retries and send to dead letter topic after exhaustion. (2) **Hung external call** — DB or third-party API not responding, consumer blocked without a timeout. Fix: add timeout to all external calls. (3) **max.poll.interval.ms exceeded** — processing takes longer than 5 minutes → broker removes consumer from group → rebalance → another consumer gets the same partition and message → cycle. Fix: increase `max.poll.interval.ms` or reduce `max.poll.records`. Diagnostics: kafkajs logs, rebalance metrics, consumer lag via Admin API.

---

**Your analytics consumer is 500,000 messages behind. What are your options?**

Diagnose first — understand the root cause. Option A — slow consumer (each message takes too long): optimize the handler (batch DB writes, remove sync calls in the loop). Option B — single consumer, many partitions: add consumers to the group (up to the partition count). Option C — not enough partitions: increase partition count (careful — remaps keys for existing data) + add consumers. Option D — traffic spike, temporary lag: wait, consumer will catch up on its own. Option E — if analytics is at-most-once and data loss is acceptable: reset offset to the current end of the log (`seekToEnd`) — skip what was missed, start from current events. Monitor lag before and after each change.

---

**What is CDC and how does Debezium use Kafka? Why is CDC better than publishing events directly from application code?**

**CDC (Change Data Capture)** captures database changes through the binary replication log (WAL in PostgreSQL). Debezium reads the WAL as a regular replica and publishes each INSERT/UPDATE/DELETE as an event to a Kafka topic. **Direct event publishing from code** has an atomicity problem: `db.orders.create()` and `kafka.send()` are two separate, non-atomic operations. If Kafka is unavailable after a successful DB INSERT — the event is lost. The Transactional Outbox pattern solves this via an intermediate table in the same DB transaction, but requires an additional polling process. **CDC via Debezium**: write only to the DB; Debezium guarantees capture from the WAL (if the change is in the DB, it will appear in Kafka). Bonus: works without any changes to application code, enabling declarative sync across stores (PostgreSQL → Elasticsearch, → ClickHouse).

---

**What is KRaft and why did Kafka replace ZooKeeper?**

ZooKeeper was a separate coordination service used by Kafka for: storing cluster metadata (which brokers exist, which partitions are where, topic configs) and Controller leader election. Problems: two separate clusters to run and maintain; ZooKeeper became a bottleneck at very large partition counts (hundreds of thousands); slow Controller failover (seconds). **KRaft** (Kafka Raft, KIP-500) is a built-in consensus protocol: metadata is stored in an internal Kafka topic; one of the brokers takes the Controller role via Raft election. Benefits: one cluster instead of two; fast failover (milliseconds); support for millions of partitions. KRaft is production-ready since Kafka 3.3, the default since 3.x, and ZooKeeper mode was fully removed in Kafka 4.0.

---

## Group 5: Kafka vs RabbitMQ (Dedicated Block)

**What is the difference between a Kafka topic and a RabbitMQ queue from the consumption perspective?**

In RabbitMQ a queue is a competitive resource: multiple consumers compete for messages; each message goes to exactly one consumer. After processing + ack — message is gone. In Kafka a topic is a shared log: multiple consumer groups read it independently; each group receives all messages. Two consumers in the same group don't compete — each reads its own partition. Consumers from different groups receive the same messages independently. The fundamental difference: in RabbitMQ "processed by one" = "unavailable to others"; in Kafka "processed by one" = "others can still read it."

---

**Can I implement pub/sub with RabbitMQ? When should I choose Kafka instead?**

Yes, RabbitMQ implements pub/sub via fanout exchange: one message → multiple queues → each queue consumed by its own consumer. But there are limits: no replay (message deleted after reading), hard to add a new subscriber retroactively (requires creating a new queue and binding in the broker), no long-term retention. Choose Kafka when: new subscribers need to replay history; a subscriber can crash and recover without data loss; the event history must be stored (compliance, audit, ML); throughput is in the millions of events per second. If pub/sub is simple, short-lived, and replay is never needed — RabbitMQ is simpler and sufficient.

---

**Simple task: send an email after a user registers. Kafka or RabbitMQ?**

RabbitMQ (or SQS). Arguments: one task → one worker, replay not needed, no RPC pattern needed, low throughput. Kafka is overkill: you'd need to run a broker cluster, configure partitions, retention, consumer group — for one email-sending worker. If a future need emerges for replay (e.g., "resend the welcome email to everyone who registered in the last 7 days") — Kafka would make sense then. But designing for a hypothetical future need is premature. Rule: start with RabbitMQ/SQS; migrate to Kafka when a concrete need for its capabilities appears.

---

**Does Kafka guarantee global message ordering within a topic?**

No. Kafka guarantees ordering **within a single partition**. With multiple partitions, different consumers read them in parallel — there is no global ordering. This is the trade-off: global ordering → one partition → no parallelism → no scalability. For most use cases global ordering isn't needed — ordering within a single entity is sufficient (all events for one order in sequence). This is achieved with the right key: `key = orderId` → all order events in one partition → strict ordering within that order. For comparison: RabbitMQ guarantees ordering within a single queue with a single consumer.
