# CQRS and Event Sourcing

> **Scope note:** CQRS (Command Query Responsibility Segregation) and Event Sourcing are covered here as patterns. The Nest.js implementation is in [command and query separation in Nest.js](../../nestjs/en/08-cqrs-pattern.md). Read replicas are in [database scaling](../../system-design/en/04-database-scaling.md).

## CQRS splits models, not databases

Command Query Responsibility Segregation means that writes and reads are described by two different models. A command changes state and protects the business rules. A query changes nothing and returns data in the shape one screen needs.

The problem it grew out of shows up in any service built on a single model:

```ts
// One model serves both the write and the report — and fits neither
// src/orders/orders.service.ts
interface OrderRow {
  id: string;
  customerId: string;
  status: 'pending' | 'paid' | 'shipped';
  totalUsd: number;
  createdAt: Date;
}

interface OrderTable {
  findOne(id: string): Promise<OrderRow | null>;
  findCreatedAfter(from: Date): Promise<OrderRow[]>;
  update(id: string, patch: Partial<OrderRow>): Promise<void>;
}

export class OrdersService {
  constructor(private readonly orders: OrderTable) {}

  // Write: state transition rules are needed here
  async ship(orderId: string): Promise<void> {
    const order = await this.orders.findOne(orderId);
    if (!order) throw new Error(`Order ${orderId} not found`);
    if (order.status !== 'paid') throw new Error('Cannot ship before payment');
    await this.orders.update(orderId, { status: 'shipped' });
  }

  // Read: the report screen needs a customer name and region, absent here
  async report(from: Date): Promise<OrderRow[]> {
    return this.orders.findCreatedAfter(from); // customers fetched separately
  }
}
```

The `OrderRow` model is normalized for data integrity. The report screen wants the opposite: a flat row with the customer name and region already filled in. One structure cannot serve both jobs well.

CQRS answers this with two separate types:

```ts
// Write side: an aggregate that protects the transition rule
// src/orders/write/order.aggregate.ts
export class Order {
  constructor(
    private readonly id: string,
    private status: 'pending' | 'paid' | 'shipped',
  ) {}

  ship(): void {
    if (this.status !== 'paid') {
      throw new Error(`Order ${this.id}: cannot ship before payment`);
    }
    this.status = 'shipped';
  }
}

const order = new Order('42', 'pending');
try {
  order.ship();
} catch (e) {
  console.log((e as Error).message); // Order 42: cannot ship before payment
}

// Read side: a flat row shaped for the report screen, with no rules
// src/orders/read/order-report.row.ts
export interface OrderReportRow {
  orderId: string;
  customerName: string; // filled in ahead of time, not at query time
  region: string;
  totalUsd: number;
  status: string;
}
```

The write side cannot produce an `OrderReportRow`. The read side knows nothing about the rule "no shipping before payment". That is the split. Entry points split the same way: the `ShipOrder` command goes to its own handler, the `OrderReport` query to another one.

## What CQRS does not mean

Half of the interview mistakes are extra requirements people attach to the pattern. They are worth listing directly:

- **Not "two databases".** The split can live entirely inside one schema and one transaction.
- **Not "a message bus".** A command can run synchronously, inside the same request.
- **Not "Event Sourcing".** These are two independent patterns, and each one works without the other.
- **Not "a command must return nothing".** In practice a command returns the id of the new record, and that is fine.
- **Not about how data travels.** The response format and the protocol have nothing to do with the pattern.

The split is a ladder, not a switch. You can climb one step and stop there:

```txt
   Three levels of splitting writes from reads
┌───────────────────────────────────────────────┐
│ Level 1. Two sets of methods in one service   │
│   shared: the model, the schema, the database │
│   gives: clarity. Does not give: scaling      │
├───────────────────────────────────────────────┤
│ Level 2. Two models over one database         │
│   shared: the database and the transaction    │
│   gives: a query shaped for one screen        │
├───────────────────────────────────────────────┤
│ Level 3. Two stores joined by events          │
│   shared: only the event stream               │
│   gives: independent scaling. Cost: a lag     │
└───────────────────────────────────────────────┘
CQRS starts at level 1 — a second store is optional
```

Level 1 is the old CQS (Command Query Separation) principle. Under it a method either changes state or answers a question, never both. Level 3 is the one interviews ask about. Writes go into normalized PostgreSQL tables, and reads come from denormalized documents or from Elasticsearch.

## The split only pays off when reads and writes diverge

The honest answer for most projects is that plain CRUD (create, read, update, delete) is right. As long as the screen shows the same fields you write, a second model only adds code.

| Signal in the requirements | What it means for the decision |
|---|---|
| Reads happen tens of times more often than writes | Move reads into a separate model |
| A report pulls data from 5–6 tables | A projection takes the joins out of query time |
| The write rules are complex and numerous | Free the aggregate from the screen's shape |
| Search is full-text while writes are relational | A second store is justified, e.g. Elasticsearch |
| The screen shape matches the table shape | Plain CRUD, no split needed |
| The team is under 5 people on a short deadline | Plain CRUD, no split needed |

A typical case from practice is a product catalog. The catalog is read thousands of times a minute. The warehouse writes stock levels rarely, but with checks. The split pays off here because load and data shape diverge while the domain stays shared.

## Event Sourcing makes the event log the source of truth

Event Sourcing stores changes instead of current state. Immutable, past-tense events are appended to a log, and that log is the source of truth. Current state is not kept in the database: it is derived from the log.

```sql
-- Classic storage: the current state is overwritten
UPDATE orders SET status = 'shipped' WHERE id = 42;
-- after this the table holds only the word 'shipped'

-- Event Sourcing: the same change is a new row in the log
INSERT INTO events (stream_id, version, type, payload)
VALUES ('42', 4, 'OrderShipped', '{"carrier":"DHL"}');
-- versions 1, 2 and 3 stay in place and stay readable
```

The difference is that `UPDATE` destroys the previous value. The log destroys nothing, so it gives three things a plain table cannot:

- **A full audit trail.** You see what happened, in what order, and with what data.
- **Queries about the past.** You can answer "what was the balance thirty days ago".
- **Rules that depend on history.** For example, a discount on the third order in a month.

Here is one order stored as events:

```ts
// The log of one order: a full history instead of a single row
// every event is immutable and named in the past tense
const stream = [
  { version: 1, type: 'OrderPlaced', total: 120, at: '2026-03-01T10:00Z' },
  { version: 2, type: 'OrderPaid', amount: 120, at: '2026-03-01T10:04Z' },
  { version: 3, type: 'OrderItemRemoved', price: 20, at: '2026-03-02T09:10Z' },
  { version: 4, type: 'OrderShipped', carrier: 'DHL', at: '2026-03-03T08:00Z' },
];

console.log(stream.length); // 4 — and no row was ever modified
```

## State is rebuilt by folding the events

Current state is produced by running the events through a transition function in order. This is an ordinary fold: an initial state plus a list of events gives a result. There is no magic here — it is `reduce`.

```ts
// Rebuilding state: folding the log from left to right
// src/orders/write/replay.ts
type OrderEvent =
  | { type: 'OrderPlaced'; total: number }
  | { type: 'OrderPaid'; amount: number }
  | { type: 'OrderItemRemoved'; price: number }
  | { type: 'OrderShipped'; carrier: string };

interface OrderState {
  total: number;
  status: 'none' | 'pending' | 'paid' | 'shipped';
}

const initial: OrderState = { total: 0, status: 'none' };

function apply(state: OrderState, event: OrderEvent): OrderState {
  switch (event.type) {
    case 'OrderPlaced':
      return { total: event.total, status: 'pending' };
    case 'OrderPaid':
      return { ...state, status: 'paid' };
    case 'OrderItemRemoved':
      return { ...state, total: state.total - event.price };
    case 'OrderShipped':
      return { ...state, status: 'shipped' };
  }
}

const events: OrderEvent[] = [
  { type: 'OrderPlaced', total: 120 },
  { type: 'OrderPaid', amount: 120 },
  { type: 'OrderItemRemoved', price: 20 },
  { type: 'OrderShipped', carrier: 'DHL' },
];

console.log(events.reduce(apply, initial));
// { total: 100, status: 'shipped' }
```

Event order carries the whole meaning here. Put `OrderPlaced` after `OrderItemRemoved` and the fold returns 120 instead of 100. So events need a version number inside the stream, not only a timestamp. Clocks on different nodes drift. A version number does not.

Here is the full path of one command:

```txt
   The write path: a log instead of UPDATE
┌──────────────────────────────────────────┐
│ Command ShipOrder(orderId=42)            │
└──────────────────────────────────────────┘
                      │  SELECT by streamId
                      ▼
┌──────────────────────────────────────────┐
│ Read the events of order 42 from the log │
└──────────────────────────────────────────┘
                      │  fold the events
                      ▼
┌──────────────────────────────────────────┐
│ Rebuild the state and check the rules    │
└──────────────────────────────────────────┘
                      │  INSERT, never UPDATE
                      ▼
┌──────────────────────────────────────────┐
│ Append the event OrderShipped(42)        │
└──────────────────────────────────────────┘
                      │  subscribes to the log
                      ▼
┌──────────────────────────────────────────┐
│ A projector updates the read-model row   │
└──────────────────────────────────────────┘
       the log holds no current state:
   it is derived from the events every time
```

This corrects a common belief: Event Sourcing on its own does not speed up reads. Folding forty thousand events is slower than reading one row by primary key. Read speed comes from snapshots and projections, not from the log.

## A snapshot shortens the fold without changing the model

A snapshot is a stored state at a known stream version. On load you take the latest snapshot and fold only the events that came after it.

```ts
// A snapshot: a state plus the version of the last event in it
// src/orders/write/load-with-snapshot.ts
import { apply, initial, type OrderEvent, type OrderState } from './replay';

interface Snapshot {
  streamId: string;
  version: number;
  state: OrderState;
}

declare const snapshots: {
  findLatest(streamId: string): Promise<Snapshot | null>;
};
declare const eventStore: {
  readAfter(streamId: string, version: number): Promise<OrderEvent[]>;
};

async function loadOrder(streamId: string): Promise<OrderState> {
  const snap = await snapshots.findLatest(streamId);
  const tail = await eventStore.readAfter(streamId, snap?.version ?? 0);
  return tail.reduce(apply, snap?.state ?? initial);
}
// 40,000 events, a snapshot at version 39,900 → a fold over 100 events
```

A snapshot is an optimization, not a second source of truth. You can delete it and rebuild it from the log at any moment, and no data is lost. That is why a snapshot does not complicate the model: it adds nothing to the meaning of the events.

## Projections buy fast reads with a lag

A projection is a table or a document built from events for one specific query. A projector subscribes to the log, handles events one by one, and updates the read model. A projector holds no business rules — it only moves data.

A separate question is how the event reliably reaches the projector. In Event Sourcing the log is the source, so the projector reads it from a stored position. In CQRS without a log, the event is written in the same transaction as the state, into an outbox table. A separate process then publishes it.

```ts
// A projector: one event → one edit in the read model
// src/orders/read/order-report.projector.ts
import type { OrderReportRow } from './order-report.row';

interface OrderPlacedEvent {
  orderId: string;
  customerName: string; // put into the event at write time
  region: string;
  total: number;
}

interface ReportRowStore {
  insert(row: OrderReportRow): Promise<void>;
  setStatus(orderId: string, status: string): Promise<void>;
}

export class OrderReportProjector {
  constructor(private readonly rows: ReportRowStore) {}

  async onOrderPlaced(event: OrderPlacedEvent): Promise<void> {
    await this.rows.insert({
      orderId: event.orderId,
      customerName: event.customerName,
      region: event.region,
      totalUsd: event.total,
      status: 'pending',
    });
  }

  async onOrderShipped(event: { orderId: string }): Promise<void> {
    await this.rows.setStatus(event.orderId, 'shipped');
  }
}
```

There is a window between the write and the projection update. Inside it the command is already accepted, but a screen reading the projection still shows old data. This is what eventual consistency means:

```txt
t = 0 ms    the command is accepted, OrderPlaced goes to the log
t = 0 ms    the client gets a 201 Created response
t = 15 ms   the projector reads the event from the log
t = 40 ms   the row in the read model is updated

window 0..40 ms: the order exists, but the list does not show it
```

Users notice this very fast: they place an order and immediately refresh the history page. There are three working ways to close the window, and the choice is a product decision:

- **Read your own write from the write side.** The confirmation page is built from the command data, skipping the projection.
- **Show a "processing" state.** The projection models the intermediate status honestly, and the screen displays it.
- **Poll the projection.** The screen shows a loading indicator for a few hundred milliseconds and retries.

The same lag appears without events, on plain read replicas. Its mechanics and its consequences are covered in [database scaling](../../system-design/en/04-database-scaling.md).

## Versioning: old events are lifted to the new shape on read

The log is immutable, so it has no ordinary schema migration. An event written two years ago stays in its old shape forever. The reading code has to understand every shape that was ever written.

```ts
// Version 1 stays in the log forever — it cannot be rewritten
interface UserRegisteredV1 {
  type: 'UserRegistered';
  v: 1;
  name: string;
}

// Version 2 split the name into two parts
interface UserRegisteredV2 {
  type: 'UserRegistered';
  v: 2;
  firstName: string;
  lastName: string;
}

// An upcaster lifts the old shape up to the new one
function upcast(event: UserRegisteredV1 | UserRegisteredV2): UserRegisteredV2 {
  if (event.v === 2) return event;
  const [firstName, ...rest] = event.name.split(' ');
  return { type: 'UserRegistered', v: 2, firstName, lastName: rest.join(' ') };
}

console.log(upcast({ type: 'UserRegistered', v: 1, name: 'Ada Lovelace' }));
// { type: 'UserRegistered', v: 2, firstName: 'Ada', lastName: 'Lovelace' }
```

Two practical rules follow from this. Put a version number in the event from day one, or you will later guess the shape from the field set. Keep the upcasters in one place at the read boundary, so the rest of the code only knows the latest version.

Three versioning mistakes are more common than the rest:

- **Renaming a field and quietly rewriting the log.** That destroys the history the log was created for.
- **Deleting the handler of an event that is no longer written.** The old records remain, and the fold breaks on them.
- **Making a field required after the fact.** Earlier events do not have it, and the upcaster has nothing to fill it with.

## CQRS alone and Event Sourcing alone are different things

These are two independent patterns, and interviews confuse them more than anything else. CQRS is about models. Event Sourcing is about how data is stored.

```txt
              What each pattern gives you on its own
┌─────────────────┬───────────────────┬─────────────────────────┐
│ trait           │ CQRS alone        │ Event Sourcing alone    │
├─────────────────┼───────────────────┼─────────────────────────┤
│ source of truth │ the current state │ the event log           │
├─────────────────┼───────────────────┼─────────────────────────┤
│ reads           │ a separate model  │ a fold or a projection  │
├─────────────────┼───────────────────┼─────────────────────────┤
│ delete a record │ a normal DELETE   │ a reversing event       │
├─────────────────┼───────────────────┼─────────────────────────┤
│ schema change   │ ALTER TABLE       │ an event upcaster       │
├─────────────────┼───────────────────┼─────────────────────────┤
│ needs the other │ works on its own  │ almost always with CQRS │
└─────────────────┴───────────────────┴─────────────────────────┘
 the columns are independent: CQRS is not a synonym for the other
```

The asymmetry matters, and it is worth saying out loud:

- **CQRS without Event Sourcing** is the ordinary and most common case. You write current state and read from a separate model or a replica.
- **Event Sourcing without CQRS** is possible but awkward. Every read has to be assembled by folding, and that is slow.
- **Both together** — commands append events, projections serve the reads. This is the pairing people usually mean.

What this looks like in Nest.js code — with `CommandBus`, `QueryBus`, event handlers and sagas — is covered in [command and query separation in Nest.js](../../nestjs/en/08-cqrs-pattern.md).

## The cost: no easy delete, harder debugging, migrations become code

A log instead of current state costs five things, and each one shows up in the first month.

| What gets expensive | Why | What teams do about it |
|---|---|---|
| Deleting data | events are immutable, `DELETE` does not apply | a compensating event |
| Storage volume | you keep every change, not one row | archiving old streams |
| Debugging | the status is derived, not read from a row | a stream viewer tool |
| Changing event shape | the log has no schema migration | an upcaster on read |
| Concurrent writes | the log alone does not stop two commands | uniqueness of stream plus version |

One item deserves a separate note: deleting personal data. A compensating event does not satisfy the requirement, because the old data stays in the log. The working approach for GDPR (General Data Protection Regulation) is to store such fields encrypted and delete the key.

Event order and concurrent writes are also on you. The log does not stop two commands from writing version five of the same stream. The guard lives in the schema, in the uniqueness of stream plus version:

```sql
-- Ordering and the guard against concurrent writes, in the schema itself
CREATE TABLE events (
  stream_id   text        NOT NULL,
  version     integer     NOT NULL,
  type        text        NOT NULL,
  payload     jsonb       NOT NULL,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (stream_id, version)
);

-- Two commands read version 4 and both try to write the fifth:
INSERT INTO events (stream_id, version, type, payload)
VALUES ('42', 5, 'OrderShipped', '{"carrier":"DHL"}');
-- ERROR:  duplicate key value violates unique constraint "events_pkey"
```

The losing command gets an error, re-reads the stream, and tries again. This is optimistic locking. Without it an "immutable log" still does not protect you from races.

## When this pairing is justified

The classic fitting domain is payments, and anything where change history is required by regulation. You need the full trail, the ability to replay, and separate load for report reads. It comes together like this:

- **Write side — Event Sourcing.** A log of payment events gives an undeniable trail and lets you replay a day.
- **Read side — projections.** Report screens read denormalized tables, not the log.
- **External payment gateways — ports and adapters.** Every provider becomes a replaceable adapter, see [hexagonal architecture](./04-hexagonal-architecture.md).
- **Domain core — independent of infrastructure.** The rules know nothing about the log or the gateway, see [clean architecture](./03-clean-architecture.md).

The opposite example matters just as much. An admin panel, reference data, settings and internal tools take plain CRUD and the repository layer from [repository and service patterns](./05-repository-and-service-patterns.md). Event Sourcing there would add a log, upcasters and projectors while solving nothing real.

One more note about distributed systems. CQRS and Event Sourcing work inside a single application and do not require microservices. Service boundaries and data ownership are the topic of [monolith vs microservices](./06-monolith-vs-microservices.md).

## Common interview traps

- **"CQRS means two databases."** No. It means two models, and both can live in one schema. A second store is a separate decision, made later.

- **"CQRS and Event Sourcing are the same thing."** No. CQRS splits the read and write models. Event Sourcing stores history instead of current state. CQRS is used without an event log all the time.

- **"Event Sourcing speeds up reads."** The opposite is true: folding a stream is slower than reading one row. Snapshots and projections speed reads up, not the log itself.

- **"An event log guarantees consistency."** It does not. You enforce order inside the stream yourself, and you close concurrent writes with uniqueness of stream plus version.

- **"Events can be fixed with a migration."** The log is immutable. Changing an event shape means a new version and an upcaster on read, not `ALTER TABLE`.

- **"Snapshots complicate the model."** A snapshot is a cached fold. You can delete it and rebuild it from the log, and nothing is lost.

- **"If you have CQRS you need a message bus."** You do not. A command can run synchronously, in the same HTTP request. The bus arrives when a second read store does.

- **Staying silent about eventual consistency.** It is the central cost of the split. An answer with no sync window and no way to close it sounds memorized.
