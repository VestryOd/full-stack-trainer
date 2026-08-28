# Kafka in Real Projects — Practical Scenarios

## Scenario 1: Event Streaming — One Stream, Multiple Consumers

This is the use case Kafka was designed for, and the clearest way to show why it beats a queue here.

### Architecture: E-Commerce Orders

A user places an order. Four independent systems all care about this fact. The
Order Service publishes that fact once, into a single topic:

```txt
  [Order Service]  ──▶  topic "order-events"
     (producer)          12 partitions, key = orderId
                         30 days of retention
```

Four consumer groups then read that same topic, each at its own pace:

| Consumer group | What it does with an order event |
|---|---|
| Inventory | Reserves the goods in the warehouse |
| Notification | Sends email and push notifications |
| Analytics | Updates the sales dashboards |
| Fraud Detection | Checks the purchase against known patterns |

**Why this is better than a queue:**
- Order Service knows nothing about the systems downstream. It just publishes the fact
- Adding the Fraud Detection group requires zero changes to Order Service
- Analytics down for 3 hours → restarts → catches up on all missed events
- The full 30-day order history can be replayed for a new machine learning model

### Event Structure

```ts
// types/order-events.ts
type OrderEventType =
  | 'ORDER_PLACED'
  | 'PAYMENT_COMPLETED'
  | 'PAYMENT_FAILED'
  | 'ORDER_CONFIRMED'
  | 'ORDER_SHIPPED'
  | 'ORDER_DELIVERED'
  | 'ORDER_CANCELLED';

interface OrderEvent {
  eventId: string;          // unique event ID (for idempotency)
  eventType: OrderEventType;
  orderId: string;          // partition key
  userId: string;
  occurredAt: string;       // ISO timestamp
  payload: Record<string, unknown>;
}

// Producer in Order Service
async function publishOrderEvent(event: OrderEvent): Promise<void> {
  await producer.send({
    topic: 'order-events',
    messages: [{
      key: event.orderId,
      value: JSON.stringify(event),
      headers: { 'event-type': Buffer.from(event.eventType) },
    }],
  });
}
```

```ts
// Consumer in Inventory Service
await consumer.run({
  autoCommit: false,
  eachMessage: async ({ topic, partition, message }) => {
    const event = JSON.parse(message.value!.toString()) as OrderEvent;

    // Process only the event types this service cares about
    if (event.eventType === 'ORDER_CONFIRMED') {
      await inventoryService.reserve({
        orderId: event.orderId,
        items: event.payload.items as OrderItem[],
      });
    }

    await consumer.commitOffsets([{
      topic, partition,
      offset: (Number(message.offset) + 1).toString(),
    }]);
  },
});
```

## Scenario 2: Event Sourcing — The Log as Source of Truth

**Event Sourcing** is an architectural pattern. The state of an entity is not a current snapshot in a database table. It is the sequence of events that led to that state.

```txt
Traditional approach (state-based):
  orders table row:
    { id: "ord-1", status: "shipped", amount: 1500,
      updatedAt: "..." }
  
  Question: "Why is the status 'shipped' and not 'delivered'?"
  Answer: unknown — we only store the current state.

Event Sourcing approach:
  order-events log (every event carries orderId "ord-1"):
    [0] ORDER_PLACED    { amount: 1500, items: [...] }
    [1] PAYMENT_OK      { method: "card", txId: "tx-42" }
    [2] ORDER_CONFIRMED { warehouseId: "wh-3" }
    [3] ORDER_SHIPPED   { trackingId: "TRK-99", carrier: "FedEx" }
  
  Current state = apply all events in order.
  Full history is always available.
  Can "rewind" to any point in time.
```

Kafka is an ideal store for an event sourcing log: append-only, high throughput, long-term retention, multiple readers.

```ts
// Rebuilding order state from the event log
async function rebuildOrderState(orderId: string): Promise<Order> {
  // In real event sourcing, you read from a specialized event store.
  // This shows the concept.
  const events = await getEventsFromLog('order-events', orderId);

  return events.reduce((state, event) => {
    switch (event.eventType) {
      case 'ORDER_PLACED':
        return { ...state, status: 'pending', amount: event.payload.amount };
      case 'PAYMENT_OK':
        return { ...state, status: 'paid' };
      case 'ORDER_SHIPPED':
        return { ...state, status: 'shipped', trackingId: event.payload.trackingId };
      default:
        return state;
    }
  }, {} as Order);
}
```

## Scenario 3: Log Aggregation — Centralized Log Collection

Every microservice writes logs to stdout. How do you centralize, index, and analyze them?

The classic ELK (Elasticsearch, Logstash, Kibana) stack, with Kafka standing in
front of it:

```txt
      ┌───────────┐  ┌───────────┐  ┌───────────┐
      │ Service A │  │ Service B │  │ Service C │
      │ logs to   │  │ logs to   │  │ logs to   │
      │ stdout    │  │ stdout    │  │ stdout    │
      └───────────┘  └───────────┘  └───────────┘
            ▼              ▼              ▼
         ┌───────────────────────────────────┐
         │ Filebeat / Fluentd (log shipper)  │
         │ Reads logs from files and stdout, │
         │ then writes them to Kafka         │
         └───────────────────────────────────┘
                           ▼
           Topic: "application-logs"
           Retention: 3 days
           Partitions: 24 (key = serviceId)
          ▼                 ▼               ▼
  ┌───────────────┐  ┌────────────┐  ┌─────────────┐
  │ Logstash      │  │ Monitoring │  │ S3 Archiver │
  │ writes to     │  │ alerts on  │  │ long-term   │
  │ Elasticsearch │  │ errors     │  │ storage     │
  └───────────────┘  └────────────┘  └─────────────┘
```

**Why Kafka in this chain, rather than going directly to Elasticsearch?**

Without Kafka: Filebeat → Elasticsearch directly. Problems:
- Elasticsearch is overwhelmed during traffic spikes
- Logs are lost if Elasticsearch is unavailable
- No ability to reprocess logs (e.g., when an index schema changes)

With Kafka: Kafka acts as a buffer. When Elasticsearch is overloaded, logs accumulate in Kafka and Logstash reads them at its own pace. If Elasticsearch goes down, logs aren't lost — they're in the Kafka log.

## Scenario 4: Change Data Capture (CDC)

**Change Data Capture (CDC)** is a mechanism for capturing database changes and publishing them as an event stream. Instead of polling the database ("what changed in the last minute?"), CDC subscribes to the database's own binary replication log.

PostgreSQL has a Write-Ahead Log (WAL) — a binary journal of all changes. Standby replicas already read it. Debezium (a popular CDC connector) reads the same WAL, and to PostgreSQL it looks like one more replica.

```txt
  ┌──────────────┐        ┌──────────┐        ┌─────────────────┐
  │ PostgreSQL   │  WAL   │ Debezium │        │ Kafka topic     │
  │              │───────▶│ (Kafka   │───────▶│ "postgres.      │
  │ INSERT order │        │ Connect) │        │  public.orders" │
  │ UPDATE order │        └──────────┘        │                 │
  │ DELETE order │                            │ [insert-event]  │
  └──────────────┘                            │ [update-event]  │
                                              │ [delete-event]  │
                                              └─────────────────┘

               Three consumers read that one topic:
                ▼                   ▼               ▼
       ┌─────────────────┐  ┌──────────────┐  ┌───────────┐
       │ Search Index    │  │ Analytics    │  │ Audit Log │
       │ (Elasticsearch) │  │ (ClickHouse) │  │ (S3)      │
       └─────────────────┘  └──────────────┘  └───────────┘
```

**CDC event structure** (Debezium format):

```ts
interface DebeziumOrderEvent {
  before: OrderRecord | null;  // state BEFORE the change (null for INSERT)
  after: OrderRecord | null;   // state AFTER the change (null for DELETE)
  op: 'c' | 'u' | 'd' | 'r';  // create, update, delete, read (snapshot)
  ts_ms: number;               // timestamp of the change in the DB
  source: {
    table: string;
    db: string;
    lsn: number;               // position in WAL
  };
}
```

**Why CDC instead of publishing events from application code?**

```txt
Approach 1: events from code:
  await db.transaction(async (tx) => {
    await tx.orders.create(order);
    // problem: not atomic!
    await kafka.send('order-created', order);
  });
  
  Problem: the database transaction and the Kafka write are not
  atomic. If Kafka is unavailable, the order is created but the
  event is never sent.

Approach 2: Transactional Outbox:
  await db.transaction(async (tx) => {
    await tx.orders.create(order);
    await tx.outbox.insert({
      topic: 'order-created', payload: order,
    });
    // Everything in one database transaction → atomic
  });
  // Separate process reads outbox and writes to Kafka

Approach 3: CDC (Debezium):
  await db.orders.create(order);  // just write to the database
  // Debezium captures the change from the WAL and writes it
  // to Kafka. Guarantee: if the change is in the database, it
  // will reach Kafka, because the WAL is read like a replica.
```

CDC is especially valuable when you need to synchronize data across storage systems without changing application code.

## Scenario 5: Real-Time Analytics Pipeline

An e-commerce analytics pipeline in real time. OLAP stands for online analytical
processing: a store tuned for aggregate queries over many rows, not for reading
one row at a time.

```txt
        ┌────────────────────────────────────────────┐
        │ Data sources: Order Service, User Service, │
        │ Product Service, Web Frontend              │
        └────────────────────────────────────────────┘
                               ▼
              ┌─────────────────────────────────┐
              │ Kafka topics                    │
              │ "order-events"   "user-events"  │
              │ "product-views"  "click-stream" │
              └─────────────────────────────────┘
           ▼                    ▼                   ▼
  ┌─────────────────┐  ┌─────────────────┐  ┌───────────────┐
  │ Kafka Streams / │  │ ClickHouse /    │  │ Elasticsearch │
  │ Apache Flink    │  │ Apache Druid    │  │ (search,      │
  │ (real-time      │  │ (OLAP store     │  │ analytics)    │
  │ aggregation)    │  │ for dashboards) │  │               │
  └─────────────────┘  └─────────────────┘  └───────────────┘
```

The Kafka Streams / Flink branch produces the aggregated metrics the business
actually looks at: revenue per minute, conversion rate from views to purchases,
top products in the last 5 minutes, and the number of active users right now.

**Example of a simple aggregation with kafkajs:**

```ts
// Count orders by status over a sliding window
// (in real production use Kafka Streams or Flink)
const orderCounts: Record<string, number> = {};

await consumer.run({
  autoCommit: true,
  eachMessage: async ({ message }) => {
    const event = JSON.parse(message.value!.toString()) as OrderEvent;

    if (event.eventType === 'ORDER_PLACED') {
      const minute = event.occurredAt.slice(0, 16); // "2024-01-15T14:32"
      orderCounts[minute] = (orderCounts[minute] ?? 0) + 1;

      // Publish the aggregate every minute
      await metricsProducer.send({
        topic: 'order-metrics',
        messages: [{
          key: minute,
          value: JSON.stringify({ minute, count: orderCounts[minute] }),
        }],
      });
    }
  },
});
```

## Worked Example: Complete Order Architecture

Let's bring all the scenarios together into one realistic architecture. Five
producers write into five topics of one cluster:

| Producer | Topic | Partitions | Retention |
|---|---|---|---|
| Order Service | `order-events` | 12 | 30 days |
| Payment Service | `payment-events` | 6 | 30 days |
| User Service | `user-events` | 6 | 7 days |
| CDC / Debezium | `db.public.orders` | 12 | 7 days |
| Filebeat | `app-logs` | 24 | 3 days |

Three families of consumer groups read those topics:

| Family | Consumer groups |
|---|---|
| Operational | `inventory-svc`, `notification-svc`, `fraud-detection`, `recommendation-engine` |
| Analytics | `clickhouse-sink`, which feeds an online analytical processing store for dashboards, and `real-time-metrics` on Kafka Streams |
| Infrastructure | `elasticsearch` for logs and search, `s3-archiver` for cold storage |

The two families need different delivery guarantees. The operational groups run
at-least-once with an idempotent consumer: every event is processed, sometimes
more than once, and the repeat does no harm. Losing an order is not acceptable.
The analytics groups can run at-most-once, where an event is processed once or
dropped. Losing a single metric is not critical.

**What makes this architecture scalable:**

1. **Producer/consumer decoupling**: Order Service has no knowledge of Fraud Detection or Analytics. They were added later without any changes to Order Service.

2. **Independent processing rates**: every group has its own lag — the distance between the newest message in a partition and the last one that group processed. Notification Service keeps its lag under a second. The analytics pipeline may lag by minutes, and that is acceptable. Each group reads at its own pace.

3. **Replay for new services**: Recommendation Engine was added 6 months after launch. It reads from offset=0 across the full 30-day order history and trains its model on real data from day one.

4. **Failure isolation**: Fraud Detection goes down — orders keep being created, notifications keep being sent. When Fraud Detection recovers, it processes all the orders it missed.

## Common Interview Traps

**"Event Sourcing and Event Streaming are the same thing"**

No. Event Streaming is a technical pattern: a stream of events over Kafka. Event Sourcing is an architectural pattern: system state is derived from a history of events, not from a current snapshot in the database.

Kafka works well as a store for Event Sourcing, but the two are independent. You can do Event Sourcing without Kafka, in EventStoreDB or in a plain PostgreSQL events table. You can also do Event Streaming without Event Sourcing: Kafka for logs, or CDC with no event-sourced state anywhere.

**"CDC is just scheduled database polling"**

No. CDC via WAL (Debezium) subscribes to the binary replication log, and that is not polling. Polling with `SELECT WHERE updated_at > last_check` has three problems:

- **Latency.** You never see a change sooner than the polling interval.
- **Missed events.** If a row changes twice between two polls, the first change is invisible.
- **Load.** Every poll is one more query against the production database.

WAL-based CDC has none of them: no polling, latency under a second, and every single change captured.

**"A regular kafkajs consumer is enough for real-time analytics"**

For simple metrics — yes. For complex aggregations (windowing, joins across topics, stateful processing) — no. Specialized frameworks exist for this: Kafka Streams (Java/Scala), Apache Flink, Apache Spark Streaming. In Node.js services, Kafka is typically used as a transport layer; aggregation is handled by specialized tools.

**"A new service should only read fresh data — from the moment it launched"**

This is a design decision, not a Kafka requirement. A new service can start with `fromBeginning: true` and read the whole history the topic still keeps, up to the retention limit. That is often valuable. A recommendation engine trained on historical data performs better from day one. If you choose "read only new messages", you give that option up for good.

**"Kafka Streams is something very complex — only for big companies"**

Kafka Streams is a library, not a separate cluster, and it runs inside an ordinary JVM (Java virtual machine) application. A Node.js developer cannot use it directly. Knowing that it exists still matters, because it is the standard answer to stateful stream processing.

In practice, Node.js teams write stream queries in ksqlDB. It puts SQL (structured query language) on top of Kafka. The other option is to hand the aggregation to ClickHouse or Druid.
