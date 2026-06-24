# Kafka in Real Projects — Practical Scenarios

## Scenario 1: Event Streaming — One Stream, Multiple Consumers

This is Kafka's most canonical use case and the best way to explain why it outperforms a queue in this pattern.

### Architecture: E-Commerce Orders

A user places an order. Four independent systems all care about this fact:

```txt
                        ┌─────────────────────────────────────────┐
                        │         Kafka Cluster                    │
                        │                                          │
[Order Service] ───────►│  Topic: "order-events"                  │
  (Producer)            │  Partitions: 12 (key = orderId)         │
                        │  Retention: 30 days                      │
                        └──────────────┬──────────────────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
              ▼                        ▼                        ▼                  ▼
  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
  │ Inventory Group  │  │ Notification     │  │ Analytics Group  │  │ Fraud Detection  │
  │                  │  │ Group            │  │                  │  │ Group            │
  │ Reserves         │  │ Sends email and  │  │ Updates sales    │  │ Checks purchase  │
  │ warehouse stock  │  │ push notif.      │  │ dashboards       │  │ patterns         │
  └──────────────────┘  └──────────────────┘  └──────────────────┘  └──────────────────┘
```

**Why this is better than a queue:**
- Order Service has no knowledge of downstream systems — it just publishes the fact
- Adding Fraud Detection Group requires zero changes to Order Service
- Analytics down for 3 hours → restarts → catches up on all missed events
- The full 30-day order history can be replayed for a new ML model

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

**Event Sourcing** is an architectural pattern where the state of an entity is determined not by a current snapshot in a database table, but by the sequence of events that led to it.

```txt
Traditional approach (state-based):
  orders table: { id: "ord-1", status: "shipped", amount: 1500, updatedAt: "..." }
  
  Question: "Why is the status 'shipped' and not 'delivered'?"
  Answer: unknown — we only store the current state.

Event Sourcing approach:
  order-events log:
    [0] ORDER_PLACED    { orderId: "ord-1", amount: 1500, items: [...] }
    [1] PAYMENT_OK      { orderId: "ord-1", method: "card", txId: "tx-42" }
    [2] ORDER_CONFIRMED { orderId: "ord-1", warehouseId: "wh-3" }
    [3] ORDER_SHIPPED   { orderId: "ord-1", trackingId: "TRK-99", carrier: "FedEx" }
  
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

```txt
Classic ELK stack with Kafka:

  ┌────────────┐    ┌────────────┐    ┌────────────┐
  │ Service A  │    │ Service B  │    │ Service C  │
  │ (logs →    │    │ (logs →    │    │ (logs →    │
  │  stdout)   │    │  stdout)   │    │  stdout)   │
  └─────┬──────┘    └─────┬──────┘    └─────┬──────┘
        │                 │                 │
        ▼                 ▼                 ▼
  ┌─────────────────────────────────────────────────┐
  │          Filebeat / Fluentd (log shipper)        │
  │  Reads logs from files/stdout, writes to Kafka   │
  └──────────────────────┬──────────────────────────┘
                         │
                         ▼
               Topic: "application-logs"
               Retention: 3 days
               Partitions: 24 (key = serviceId)
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
  ┌──────────┐   ┌──────────┐   ┌──────────────┐
  │Logstash  │   │Monitoring│   │ S3 Archiver  │
  │→ Elastic │   │(alerts   │   │ (long-term   │
  │  search  │   │ on errors│   │  storage)    │
  └──────────┘   └──────────┘   └──────────────┘
```

**Why Kafka in this chain, rather than going directly to Elasticsearch?**

Without Kafka: Filebeat → Elasticsearch directly. Problems:
- Elasticsearch is overwhelmed during traffic spikes
- Logs are lost if Elasticsearch is unavailable
- No ability to reprocess logs (e.g., when an index schema changes)

With Kafka: Kafka acts as a buffer. When Elasticsearch is overloaded, logs accumulate in Kafka and Logstash reads them at its own pace. If Elasticsearch goes down, logs aren't lost — they're in the Kafka log.

## Scenario 4: Change Data Capture (CDC)

**Change Data Capture (CDC)** is a mechanism for capturing database changes and publishing them as an event stream. Instead of polling the database ("what changed in the last minute?"), CDC subscribes to the database's own binary replication log.

```txt
How CDC works with PostgreSQL:

  PostgreSQL has a Write-Ahead Log (WAL) — a binary journal of all changes.
  WAL is used for standby replication.
  
  Debezium (a popular CDC connector) reads the WAL like a regular replica:
  
  ┌──────────────┐         ┌───────────┐         ┌─────────────────────────┐
  │  PostgreSQL  │──WAL───►│  Debezium │────────►│  Kafka Topic            │
  │              │         │ (Kafka    │         │  "postgres.public.orders"│
  │  INSERT order│         │  Connect) │         │                          │
  │  UPDATE order│         └───────────┘         │  [insert-event]          │
  │  DELETE order│                               │  [update-event]          │
  └──────────────┘                               │  [delete-event]          │
                                                 └─────────────────────────┘
                                                           │
                                   ┌───────────────────────┼───────────────┐
                                   │                       │               │
                                   ▼                       ▼               ▼
                             [Search Index]         [Analytics]      [Audit Log]
                             (Elasticsearch)        (ClickHouse)     (S3)
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
    await kafka.send('order-created', order);  // problem: not atomic!
  });
  
  Problem: the DB transaction and Kafka write are not atomic.
  If Kafka is unavailable — order created, event not sent.

Approach 2: Transactional Outbox:
  await db.transaction(async (tx) => {
    await tx.orders.create(order);
    await tx.outbox.insert({ topic: 'order-created', payload: order });
    // Everything in one DB transaction → atomic
  });
  // Separate process reads outbox and writes to Kafka

Approach 3: CDC (Debezium):
  await db.orders.create(order);  // just write to the DB
  // Debezium automatically captures the change from WAL and writes to Kafka
  // Guarantee: if the change is in the DB — it will be in Kafka (WAL read as replica)
```

CDC is especially valuable when you need to synchronize data across storage systems without changing application code.

## Scenario 5: Real-Time Analytics Pipeline

```txt
E-commerce real-time analytics:

  Data sources:
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │ Order Service│  │ User Service │  │ Product Svc  │  │ Web Frontend │
  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
         │                 │                 │                 │
         ▼                 ▼                 ▼                 ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │                     Kafka Topics                                      │
  │  "order-events"  "user-events"  "product-views"  "click-stream"      │
  └──────────────────────────────────────────────────────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
  ┌────────────────────┐  ┌───────────────────┐  ┌────────────────────┐
  │   Kafka Streams /  │  │   ClickHouse /     │  │    Elasticsearch   │
  │   Apache Flink     │  │   Apache Druid     │  │    (search,        │
  │   (real-time       │  │   (OLAP store      │  │     analytics)     │
  │    aggregation)    │  │    for dashboards) │  │                    │
  └────────────────────┘  └───────────────────┘  └────────────────────┘
         │
         │ Real-time aggregated metrics:
         ├── revenue per minute
         ├── conversion rate (views → purchases)
         ├── top products in the last 5 minutes
         └── active users right now
```

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

Let's bring all the scenarios together into one realistic architecture.

```txt
                                     KAFKA CLUSTER
                    ┌─────────────────────────────────────────────────────┐
                    │                                                       │
[Order Service] ──►│  "order-events"     (12 partitions, 30d retention)  │
[Payment Svc]   ──►│  "payment-events"   (6 partitions, 30d retention)   │
[User Service]  ──►│  "user-events"      (6 partitions, 7d retention)    │
[CDC/Debezium]  ──►│  "db.public.orders" (12 partitions, 7d retention)   │
[Filebeat]      ──►│  "app-logs"         (24 partitions, 3d retention)   │
                    │                                                       │
                    └──────────────────────┬──────────────────────────────┘
                                           │
        ┌──────────────────────────────────┼──────────────────────────────────┐
        │                                  │                                  │
        ▼                                  ▼                                  ▼
┌─────────────────┐            ┌─────────────────────┐            ┌─────────────────┐
│   Operational   │            │      Analytics       │            │ Infrastructure  │
│ Consumer Groups │            │   Consumer Groups    │            │                 │
│                 │            │                      │            │                 │
│ inventory-svc   │            │ clickhouse-sink      │            │ elasticsearch   │
│ notification-svc│            │ (OLAP for dashboards)│            │ (logs + search) │
│ fraud-detection │            │                      │            │                 │
│ recommendation  │            │ real-time-metrics    │            │ s3-archiver     │
│   -engine       │            │ (kafka streams)      │            │ (cold storage)  │
└─────────────────┘            └─────────────────────┘            └─────────────────┘
        │                                  │
        │ at-least-once +                  │ at-most-once OK
        │ idempotent consumer              │ (losing a metric is not critical)
        │ (losing an order is not OK)      │
```

**What makes this architecture scalable:**

1. **Producer/consumer decoupling**: Order Service has no knowledge of Fraud Detection or Analytics. They were added later without any changes to Order Service.

2. **Independent processing rates**: Notification Service runs in near real-time (lag < 1s). The analytics pipeline can lag by minutes — that's acceptable. Each group reads at its own pace.

3. **Replay for new services**: Recommendation Engine was added 6 months after launch. It reads from offset=0 across the full 30-day order history and trains its model on real data from day one.

4. **Failure isolation**: Fraud Detection goes down — orders keep being created, notifications keep being sent. When Fraud Detection recovers, it processes all the orders it missed.

## Common Interview Traps

**"Event Sourcing and Event Streaming are the same thing"**

No. Event Streaming is a technical pattern: a stream of events over Kafka. Event Sourcing is an architectural pattern: system state is derived from a history of events (not a current DB snapshot). Kafka works well as a store for Event Sourcing, but you can do Event Sourcing without Kafka (EventStore DB, PostgreSQL events table) and Event Streaming without Event Sourcing (Kafka for logs or CDC without the ES pattern).

**"CDC is just scheduled database polling"**

No. CDC via WAL (Debezium) subscribes to the binary replication log — it's not polling. Polling ("SELECT WHERE updated_at > last_check") has problems: latency (at minimum the polling interval), missed events (if a row changes twice between polls, the first change is invisible), and DB load. WAL-based CDC: no polling, sub-second latency, captures every single change.

**"A regular kafkajs consumer is enough for real-time analytics"**

For simple metrics — yes. For complex aggregations (windowing, joins across topics, stateful processing) — no. Specialized frameworks exist for this: Kafka Streams (Java/Scala), Apache Flink, Apache Spark Streaming. In Node.js services, Kafka is typically used as a transport layer; aggregation is handled by specialized tools.

**"A new service should only read fresh data — from the moment it launched"**

This is a design decision, not a Kafka requirement. A new service can start with `fromBeginning: true` and read the full history (within retention), which is often valuable: a recommendation engine trained on historical data performs better from day one. The "read only new messages" choice permanently forfeits this option.

**"Kafka Streams is something very complex — only for big companies"**

Kafka Streams is a library (not a separate cluster) that runs inside a normal JVM application. For a Node.js developer: Kafka Streams isn't directly usable, but knowing it exists conceptually is important — it solves stateful stream processing. In practice, Node.js teams often use ksqlDB (SQL over Kafka) or offload aggregation to ClickHouse/Druid.
