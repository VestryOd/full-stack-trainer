# Kafka — Interview Questions

## Group 1: Fundamentals (Junior)

**What is Kafka? How does it fundamentally differ from a message queue?**

Kafka is a **distributed log**, not a message queue. The difference is what happens to a message after it is read.

- **Queue** (RabbitMQ, Amazon SQS — Simple Queue Service): the message is **deleted** once it has been read and acknowledged.
- **Log** (Kafka): the message stays until the configured retention period expires (`retention.ms`), whether anyone read it or not.

Because the message stays, many consumers can read the same stream independently, and a new service can replay the whole event history from the start.

Kafka also routes nothing. The broker stores the log, and each consumer tracks its own read position, called the offset. This is the "dumb broker, smart consumer" philosophy.

---

**Explain the trio: topic, partition, offset.**

A topic is a named channel, a partition is one physical log inside it, and an offset is a message's position in that partition.

- **Topic** — a logical category of events, for example `"order-events"`. It is an abstraction: the data physically lives in partitions.
- **Partition** — an ordered, append-only log on the disk of a single broker. Partitions are the source of scalability: N partitions allow N parallel consumers in one group.
- **Offset** — the sequence number of a message inside one partition, starting at 0.

The critical point: an offset is **per-partition**, not global. Offset 5 in partition 0 and offset 5 in partition 1 are different messages. Each consumer tracks and commits its own offset.

---

**What is a Consumer Group and which two patterns does it enable?**

A **Consumer Group** is a named group of consumer processes that read one topic together. The rule that makes it work: each partition is assigned to exactly one consumer inside the group. Two patterns follow from that rule.

```txt
 Queue-like: one group, the partitions are split
┌────────────────────────────────────────────────┐
│ topic "orders", group "sync"                   │
│                                                │
│   partition 0 ──▶ consumer A                   │
│   partition 1 ──▶ consumer B                   │
│   partition 2 ──▶ consumer C                   │
│                                                │
│ each message is handled by exactly one of them │
└────────────────────────────────────────────────┘

  Pub/sub: several groups, each reads everything
┌────────────────────────────────────────────────┐
│ topic "orders"                                 │
│                                                │
│   group "search-service"    ──▶ every message  │
│   group "analytics-service" ──▶ every message  │
│                                                │
│ the groups keep independent offsets            │
└────────────────────────────────────────────────┘
```

- **Queue-like (parallel processing)** — one group, several consumers. The partitions are split between them, and each message is processed by exactly one consumer. Adding consumers scales throughput, up to the partition count.
- **Pub/sub** — several groups, each receiving every message of the topic. A `search-service` group and an `analytics-service` group read the same topic independently, each keeping its own offsets.

---

**What does "dumb broker, smart consumer" mean and why is it an architectural choice, not a limitation?**

It means the broker keeps no per-consumer state: it stores the log on disk and serves data on request. In RabbitMQ the broker is smart instead — it tracks the state of every queue, pushes messages to consumers, deletes them after ack, and manages routing.

In Kafka the consumer knows its own offset and calls `poll()` itself. That is the pull model, and it buys three things.

- **Horizontal scalability** — the broker stores data, not one record per consumer.
- **No overload** — consumers read at their own pace, because nothing is pushed at them.
- **Replay** — a consumer can move its offset backward and re-read history.

In RabbitMQ replay is impossible: the data is deleted after consumption.

---

**Why doesn't Kafka delete a message after it's read? What does this enable in practice?**

Kafka stores the log by time (`retention.ms`, 7 days by default) or by volume (`retention.bytes`), whether the data was read or not. Three things become possible.

- **Several independent consumers** — search, analytics and fraud detection all read the same topic, each at its own pace.
- **Replay after a failure** — a service is down for 2 hours, restarts, reads from its last committed offset and catches up on everything it missed.
- **New services** — a new machine learning (ML) service connects and reads the full 30-day history from scratch. The producer does not change at all.

This is the fundamental difference from a queue, where none of it is possible.

---

## Group 2: Mechanics (Middle)

**Why does Kafka only guarantee ordering within a partition? How do you use this in practice?**

A partition is a sequential file: the messages inside it are numbered and read strictly in order. With several partitions each one is consumed in parallel by a different consumer, and there is no mechanism to synchronise their progress. Offset 5 in partition 0 and offset 5 in partition 1 are independent counters. Kafka does not know which one happened first.

**In practice**: when the order of events for one entity matters (an order, a user, a session), use that entity's id as the message key. Then `hash(key) % numPartitions` always yields the same partition. All events for the entity land there, and the consumer reads them in write order.

---

**How do you choose a good partition key? What is a hot partition and why is it dangerous?**

A good key has three properties.

- **Correctness** — it groups messages whose relative order matters (`orderId`, `userId`).
- **High cardinality** — many unique values, so the load spreads evenly across partitions.
- **Stability** — if the partition count grows, `hash(key) % N` sends the same key elsewhere, and ordering breaks between old and new messages.

A **hot partition** comes from low cardinality. With `key = countryCode`, 70% of the traffic can land in one partition: its consumer cannot keep up and lag grows.

The danger is that adding consumers does not help — one partition is read by one consumer per group. The fix is a key with higher cardinality (`userId` instead of `countryCode`), or splitting the topic.

---

**What triggers a rebalance and what happens during one?**

A rebalance is the moment when partitions are reassigned inside a consumer group. Four events trigger it:

- a new consumer joins the group;
- a consumer leaves gracefully (shutdown);
- a consumer sends no heartbeat within `session.timeout.ms` (45 seconds by default) and is considered dead;
- new partitions are added to the topic.

**Eager rebalancing** (the legacy protocol): every consumer gives up all of its partitions, the coordinator broker recalculates the assignment, and everyone gets new ones. The whole group **stops processing** while this happens.

**Cooperative rebalancing** (Kafka 2.3 and later) only redistributes the partitions that are affected. Consumers that keep their partitions carry on working.

A common production problem: a consumer handles one heavy message for longer than `max.poll.interval.ms` (5 minutes by default). The broker decides it is stuck, a rebalance starts, another consumer picks up the same message, and you get a duplicate.

---

**What is the difference between auto-commit and manual commit? What delivery semantics does each provide?**

The difference is when the offset is written, and that decides what happens to a message if the consumer dies.

- **Auto-commit** (`autoCommit: true`): kafkajs commits the current offset on a timer (`autoCommitInterval`) or after a number of messages. If the commit fires **before** processing finishes and the consumer crashes, the message is lost. Semantics: **at-most-once**.
- **Manual commit** (`autoCommit: false`): you call `consumer.commitOffsets()` yourself **after** processing succeeds. If the consumer crashes before the commit, the message is re-read on restart. Semantics: **at-least-once**.

In the code below, note `{ offset: (Number(message.offset) + 1).toString() }`. You commit the next offset, not the current one: the meaning is that everything up to X-1 has been processed.

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

In Kafka, committing offset X means that the next message you want to receive is X. The commit says everything up to X-1 has been processed. So after processing a message with `offset=5` you commit `6`, which tells the broker to start sending from 6.

A common bug is `commitOffsets([{ offset: message.offset }])`. That commits 5, so the broker starts from 5 again and message 5 is re-read after every restart. In kafkajs `message.offset` is a string, hence `(Number(message.offset) + 1).toString()`.

---

**What is consumer lag and how do you deal with it?**

**Consumer lag** is the distance between the end of a partition and the point the group has committed. The end of the log is where the producer writes. Formula: `lag = latestOffset - committedOffset`. Lag of 0 means the consumer is real-time; growing lag means it cannot keep up.

Causes: slow processing, an external service throttling you, synchronous calls blocking the event loop, or a traffic spike. What you can do about it:

- Add consumers — but never more than the partition count.
- Add partitions, and consumers to match.
- Speed the handler up: batch the database writes, run external calls in parallel.
- Raise `maxBytesPerPartition` so each fetch brings more data.

For monitoring: the kafkajs Admin API, Kafka UI (a web console for Kafka), Burrow, Datadog.

---

**What is a poison message and how do you handle it in Kafka?**

A poison message is one the consumer cannot process successfully: invalid JSON, an incompatible schema, or a bug in the business logic. In Kafka it is especially dangerous. The broker does not remove it from the log, so with `autoCommit: false` the consumer receives it again after every restart. The whole partition is frozen and lag grows.

The fix is the **Dead Letter Topic (DLT)** pattern. After N retries — usually 3, with exponential backoff — the message is sent to `original-topic.DLT`, with the error details in the headers. The offset is then committed and normal processing continues. A separate DLT consumer watches that topic and raises alerts.

---

## Group 3: Reliability and Guarantees (Senior)

**Explain the three delivery semantics in Kafka: at-most-once, at-least-once, exactly-once.**

The three differ in what can go wrong: loss, duplicates, or neither.

- **At-most-once** — processed zero or one time, so loss is possible. You get it with `acks: 0` on the producer (fire-and-forget), or with auto-commit that fires before processing ends. Acceptable for non-critical metrics.
- **At-least-once** — processed one or more times: duplicates are possible, loss is not. You get it with `acks: -1` on the producer plus a manual commit after processing. This is the standard in most production systems.
- **Exactly-once** — processed exactly once. Two routes lead there.

The first route is an idempotent producer plus Kafka transactions. The idempotent producer removes duplicates caused by retries, and the transaction makes consume, produce and offset commit atomic. The second route, more common in practice, is at-least-once plus an idempotent consumer.

Important: exactly-once through Kafka transactions works **inside Kafka, not when writing to an external system**. If the result goes to a database, the guarantee does not extend to it.

---

**What is an idempotent producer and how does it prevent duplicates?**

An idempotent producer stops the broker from writing the same message twice when the producer retries. Without it the failure is simple. The producer sends a message and the broker writes it, but the ack is lost on the way back. The producer retries, and the broker writes a duplicate.

The mechanism is a **Producer ID (PID)** plus a **sequence number**. Kafka gives every producer a unique PID, and every message gets a sequence number that only increases, per partition. The broker remembers the last sequence from each PID. If the same `(PID, seq)` arrives again, the broker drops it and answers with an ack.

In kafkajs, `kafka.producer({ idempotent: true })` also sets `acks: -1` and unlimited retries. The limitation: it protects only against retry duplicates within a single write session to one partition.

---

**What are Kafka Transactions and when are they needed?**

Kafka transactions make one consume-process-produce cycle atomic. Read a message from topic A, process it, write the result to topic B, and commit the offset. All of that happens, or none of it does. If a step fails, the transaction rolls back, the offset stays uncommitted, and the consumer re-reads the original message.

They are needed for Kafka→Kafka scenarios: stream processing whose results go back into Kafka. The honest limitation is that a transaction covers only Kafka itself. The consumer offset is written into the same transaction as the output topics, and an external system cannot join that transaction.

So if the result is written to PostgreSQL or pushed to an external API, exactly-once does not apply to that write. This is why most teams pick at-least-once plus an idempotent consumer instead.

---

**What is an idempotent consumer? Give three implementation approaches.**

An idempotent consumer produces the same result when it processes the same message a second time. Three ways to build one:

- **`ON CONFLICT DO NOTHING`** — rely on the entity's unique key on insert: `INSERT INTO orders (...) ON CONFLICT (id) DO NOTHING`. A repeated call raises no error and adds no duplicate row.
- **Optimistic locking through a version column** — `UPDATE orders SET status='paid', version=$2 WHERE id=$1 AND version=$2-1`. If the row was already updated by the duplicate, `rowCount=0` and the handler simply returns.
- **A `processed_events` table** — before handling, run `INSERT INTO processed_events (id) ON CONFLICT DO NOTHING RETURNING id`. If `rowCount=0`, this message was processed already, so skip it. Key format: `${topic}-${partition}-${offset}`.

---

**Compare Kafka and RabbitMQ: when would you choose each?**

The base difference: RabbitMQ is a **queue** (a message broker), Kafka is a **log** (an event streaming platform). RabbitMQ deletes a message after ack; Kafka keeps it for the retention period.

**RabbitMQ is the right choice for:**

- task queues — "send an email", "resize an image";
- request-and-reply patterns, where the caller waits for a result;
- routing by message content (fanout, direct and topic exchanges);
- message prioritisation.

**Kafka is the right choice for:**

- one event read by several independent consumers;
- replay — for new services, for debugging, for machine learning;
- very high throughput, in the millions of messages per second;
- capturing database changes, log aggregation, event sourcing.

An honest caveat: in practice the choice is often decided by the cloud provider rather than by technical fit. The pairs are Amazon MSK (Managed Streaming for Kafka) against Amazon SQS, and Azure Event Hubs against Azure Service Bus.

---

**Explain the difference in the retention model between Kafka and RabbitMQ. Give a scenario where it solves a real problem.**

RabbitMQ retention is event-driven: a message lives exactly until it is read and acknowledged. If the analytics service did not read the queue for 2 hours, those 2 hours of events are gone for good.

Kafka retention is time-based: `retention.ms=604800000` keeps messages for 7 days, whether they were read or not. The analytics service goes down, comes back, reads from its last committed offset, and processes everything it missed.

A second scenario: three months later a Fraud Detection service is added. With Kafka it starts with `fromBeginning: true` and checks the whole 30-day order history. With RabbitMQ that data no longer exists.

---

## Group 4: System Design (Senior+)

**Design a system where placing an order must trigger inventory reservation, email notification, and analytics — without tight coupling between services.**

Use Kafka as an event bus. The Order Service publishes to the topic `order-events` with key `orderId`, and knows nothing about who reads it. Three independent consumer groups subscribe:

- `inventory-service` reads `ORDER_CONFIRMED` and reserves stock, using `ON CONFLICT DO NOTHING` for idempotency;
- `notification-service` reads `ORDER_PLACED` and sends the email, while a `processed_events` check stops a duplicate from sending it twice;
- `analytics-service` runs at-most-once, because losing one metric is not critical.

The advantages: adding Fraud Detection later is just a new consumer group, and the Order Service does not change. If analytics goes down, it resumes from its last offset with no data loss. Configuration: 12 partitions, key `orderId`, retention 30 days.

---

**A consumer in your group has been stuck on the same message for 10 minutes. What happened and how do you fix it?**

Three causes are likely, and each has a different fix.

- **Poison message** — invalid JSON or a logic bug. Every attempt throws, the consumer never commits the offset, and it receives the same message again. Fix: a Dead Letter Topic pattern with N retries, then send the message to the dead letter topic.
- **A hung external call** — the database or a third-party API is not answering and the consumer is blocked with no timeout. Fix: put a timeout on every external call.
- **`max.poll.interval.ms` exceeded** — processing takes longer than 5 minutes, so the broker drops the consumer from the group. A rebalance follows, another consumer gets the same partition and the same message, and the cycle repeats. Fix: raise `max.poll.interval.ms` or lower `max.poll.records`.

For diagnosis: the kafkajs logs, the rebalance metrics, and consumer lag through the Admin API.

---

**Your analytics consumer is 500,000 messages behind. What are your options?**

Diagnose first: the right action depends entirely on the cause.

- **The consumer is slow** (each message takes too long) — optimise the handler: batch the database writes, remove synchronous calls from the loop.
- **One consumer, many partitions** — add consumers to the group, up to the partition count.
- **Not enough partitions** — raise the partition count, then add consumers. Be careful: this remaps keys for data written later.
- **A traffic spike** — the lag is temporary, so wait and the consumer catches up on its own.
- **Analytics is at-most-once and loss is acceptable** — reset the offset to the current end of the log (`seekToEnd`), skipping what was missed.

Measure lag before and after every change.

---

**What is CDC and how does Debezium use Kafka? Why is CDC better than publishing events directly from application code?**

**CDC (Change Data Capture)** means capturing database changes from the replication log instead of from application code. In PostgreSQL that log is the write-ahead log (WAL): the database appends a change there before it applies the change to the data.

Debezium reads the WAL like an ordinary replica and publishes every INSERT, UPDATE and DELETE as an event in a Kafka topic.

Publishing events directly from code has an atomicity problem. `db.orders.create()` and `kafka.send()` are two separate operations, not one atomic step. If Kafka is unavailable after the database insert succeeded, the event is lost. The Transactional Outbox pattern fixes that with an intermediate table written in the same database transaction, but it needs an extra polling process.

CDC through Debezium removes the problem: you write only to the database, and Debezium guarantees the capture from the WAL. If the change is in the database, it will appear in Kafka. A bonus is that this needs no change in application code, so stores can be kept in sync declaratively (PostgreSQL → Elasticsearch, → ClickHouse).

---

**What is KRaft and why did Kafka replace ZooKeeper?**

ZooKeeper was a separate coordination service that Kafka used for two jobs. It stored the cluster metadata — which brokers exist, where the partitions are, what the topic configs say — and it elected the Controller leader. That arrangement had three problems.

- Two separate clusters to run and maintain instead of one.
- ZooKeeper became a bottleneck at very large partition counts, in the hundreds of thousands.
- Controller failover was slow, measured in seconds.

**KRaft** (Kafka Raft) is a built-in consensus protocol that replaces it. It came from Kafka Improvement Proposal 500 (`KIP-500`). Metadata is stored in an internal Kafka topic, and one of the brokers takes the Controller role through a Raft election.

The gains: one cluster instead of two, failover in milliseconds, and support for millions of partitions. KRaft is production-ready since Kafka 3.3 and the default since 3.x, and ZooKeeper mode was removed entirely in Kafka 4.0.

---

## Group 5: Kafka vs RabbitMQ (Dedicated Block)

**What is the difference between a Kafka topic and a RabbitMQ queue from the consumption perspective?**

In RabbitMQ a queue is a competitive resource: several consumers compete for messages, and each message goes to exactly one of them. After processing and ack, the message is gone.

In Kafka a topic is a shared log: several consumer groups read it independently, and each group receives every message. Two consumers in the same group do not compete — each reads its own partition. Consumers in different groups receive the same messages, independently of each other.

The fundamental difference: in RabbitMQ "processed by one" means "unavailable to the others", while in Kafka the others can still read the same message.

---

**Can I implement pub/sub with RabbitMQ? When should I choose Kafka instead?**

Yes — RabbitMQ implements pub/sub with a fanout exchange: one message goes to several queues, and each queue is read by its own consumer. Three limits come with it:

- no replay, because the message is deleted once it is read;
- adding a subscriber after the fact is awkward, since it needs a new queue and a new binding in the broker;
- no long-term retention.

Choose Kafka instead when one of these is true:

- new subscribers need to replay history;
- a subscriber can crash and recover without losing data;
- the event history has to be stored, for compliance, auditing, or machine learning;
- throughput is measured in millions of events per second.

If the pub/sub is simple and short-lived, and replay is never needed, RabbitMQ is simpler and enough.

---

**Simple task: send an email after a user registers. Kafka or RabbitMQ?**

RabbitMQ, or Amazon SQS. The arguments: one task goes to one worker, replay is not needed, there is no remote procedure call (RPC) pattern, and throughput is low. Kafka would be overkill — a broker cluster to run, plus partitions, retention and a consumer group to configure, all for one email worker.

A future need for replay might change that — for example, resending the welcome email to everyone who registered in the last 7 days. Designing for a hypothetical need is premature, though. The rule: start with RabbitMQ or SQS, and move to Kafka when a concrete need for its capabilities appears.

---

**Does Kafka guarantee global message ordering within a topic?**

No. Kafka guarantees ordering **within a single partition** only. With several partitions, different consumers read them in parallel, so there is no global order.

That is the trade-off: global ordering would mean one partition, and one partition means no parallelism. Most use cases do not need it — ordering within one entity is enough. The right key gives you that: `key = orderId` puts all events of an order in one partition, in strict order.

For comparison: RabbitMQ guarantees ordering within a single queue read by a single consumer.
