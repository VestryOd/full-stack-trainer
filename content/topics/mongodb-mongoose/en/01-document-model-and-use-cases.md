# Document Model and Use Cases

## A document instead of a row: the unit of storage in MongoDB

MongoDB stores data as documents. A document is a self-contained structure with nested objects and arrays inside it. It can be written and read in a single round-trip: one request to the server, one answer back.

```js
// collection posts — one document holds everything a post page needs
{
  _id: ObjectId("66b0f2c14a1e2d0012ab34cd"),
  title: "Indexes in MongoDB",
  slug: "mongodb-indexes",
  author: { _id: ObjectId("66a1..."), name: "Maksym", avatar: "/a/12.png" },
  tags: ["mongodb", "performance"],
  stats: { views: 1204, comments: 8 },
  publishedAt: ISODate("2026-07-14T09:12:00Z")
}
```

The same post in PostgreSQL is `posts` + `users` + `post_tags` + `tags`, and three or four joins on every read. The difference is not "better or worse". It is *where* the entity gets assembled. SQL (structured query language) assembles it in the database, on every read. A document is assembled once, when it is written.

A collection is a container of documents — the analogue of a table, but with no declared structure. The basic vocabulary:

```txt
database    → a set of collections
              (a schema or a database in PostgreSQL)
collection  → a set of documents (a table with no declared shape)
document    → a BSON object (binary JSON), 16 MB max (a row)
field       → a key inside a document (a column — except that
              every document has its own set)
```

## BSON is not JSON: the types JSON does not have

On the wire and on disk MongoDB uses BSON (binary JSON). It is a binary format where every field carries an explicit type and its length. Two practical properties follow from that. The engine can skip a field without parsing it fully. And types survive a round-trip: what you wrote is what you read back.

```txt
BSON types that JSON does not have:
  ObjectId     — a 12-byte identifier, the default value of _id
  Date         — int64, milliseconds since the epoch, always in
                 UTC (coordinated universal time, zero offset)
  Decimal128   — decimal number with exact arithmetic (money)
  Int32/Int64  — fixed-width integers (JSON only has "number")
  Double       — IEEE 754, same behaviour as a JS number
  Binary       — raw bytes + subtype (a UUID, for example)
  Regex        — a regular expression as a field value
  Timestamp    — an internal type for the oplog, MongoDB's own
                 replication log; not for application dates
```

Three traps grow out of the gap between BSON and JSON:

```js
// 1. Numbers. Every JS number is a double. The driver writes Double by
//    default; an integer above 2^53 loses precision in JS, before the write.
db.posts.insertOne({ views: 9007199254740993 })  // ← not that number anymore
db.posts.insertOne({ views: Long("9007199254740993") })  // explicit Int64

// 2. Money. Double accumulates rounding error — exactly like Float in SQL
//    (see the PostgreSQL topic on numeric/decimal).
db.orders.insertOne({ total: 19.99 })                     // Double — bad
db.orders.insertOne({ total: Decimal128("19.99") })       // exact
// alternative without Decimal128: store cents as Int32/Int64

// 3. Dates. The string "2026-07-14" is not a Date: range queries on it
//    compare text letter by letter, not chronologically.
db.posts.insertOne({ publishedAt: "2026-07-14" })            // a string
db.posts.insertOne({ publishedAt: new Date("2026-07-14") })  // BSON Date
```

When a document leaves the process over HTTP, BSON is serialized to Extended JSON. In relaxed mode `ObjectId` becomes a plain string. `Date` becomes a text date in ISO 8601 form — the international standard order, `"2026-07-14T09:12:00Z"`.

That is why an API returns `"_id": "66b0f2c1..."` rather than an object. The reverse mapping, string → `ObjectId`, belongs to the application layer. On an invalid string `new ObjectId(req.params.id)` throws, so this is the first place where input validation is required.

## _id and how ObjectId is built

Every document has an `_id`: mandatory, unique within the collection, immutable after the insert. A unique index named `_id_` is created for it automatically and cannot be dropped. If `_id` is not set explicitly, the driver generates an `ObjectId` — the driver, not the server.

An `ObjectId` is not a UUID (universally unique identifier), the 128-bit random key many databases use for this job. Its 12 bytes have a fixed structure, and the first four of them are a timestamp in UTC (coordinated universal time):

| bytes | what is inside | what that gives you |
|---|---|---|
| 0-3 | unix time in seconds, UTC | sorting by `_id` ≈ sorting by creation time |
| 4-8 | random value per process | two processes never generate the same id |
| 9-11 | counter inside the process | order within one second is preserved |

Time granularity is one second. Inside a single second, the order across different processes is undefined.

What that layout gives you in practice:

```js
// The creation time is inside _id itself, so a separate createdAt field
// is not required. It is usually still useful: createdAt can be
// backfilled for old documents, _id cannot.
ObjectId("66b0f2c14a1e2d0012ab34cd").getTimestamp()  // ISODate(...)

// Sorting by _id ≈ sorting by creation time → free keyset pagination
// for "newest first" on the index that already exists (_id_).
db.posts.find({ _id: { $lt: lastSeenId } }).sort({ _id: -1 }).limit(20)

// A time range can be expressed through _id built from a timestamp.
db.posts.find({ _id: { $gte: ObjectId.createFromTime(1750000000) } })
```

Two things `ObjectId` does not guarantee. The first is a strict global order: inside one second, the order across processes is arbitrary. The second is secrecy: the value exposes the creation time, and documents created by the same process get adjacent ids. Where unpredictability matters — a public URL, for example — use a separate random field instead of `_id`.

A custom `_id` is allowed, and sometimes worth it. A natural key removes one index and makes the "one record, one key" relationship explicit. Two examples: `_id: "mongodb-indexes"` for a slug, and `_id: userId` in a 1:1 profile collection.

The cost is index locality — the same trade-off as a random primary key in PostgreSQL. A monotonic `ObjectId` always lands at the right edge of the B-tree, so only that edge stays in cache. A random key lands anywhere, so the whole tree has to stay hot. The PostgreSQL topic covers this in article 04, on indexes and internals.

## "Schemaless" does not mean "no schema"

A collection accepts any document: fields missing, a field with a different type, a brand-new nested object. There is no DDL — data definition language, the `CREATE TABLE` / `ALTER TABLE` half of SQL. Adding a field is just another `$set`.

```txt
      MongoDB: the schema lives in the code
┌────────────────────────────────────────────────┐
│ collection posts                               │
│                                                │
│ { title, authorId, tags }                      │
│ { title, authorId }          ← no tags         │
│ { title, author: {...} }     ← different shape │
└────────────────────────────────────────────────┘
   the DB accepts anything; the code must check
  (a Mongoose schema or a $jsonSchema validator)

PostgreSQL: the schema lives in the DB
┌────────────────────────────────────┐
│ table posts                        │
│                                    │
│ title      text   NOT NULL         │
│ author_id  bigint REFERENCES users │
│ tags       text[] DEFAULT ARRAY[]  │
└────────────────────────────────────┘
    the DB rejects a wrong shape,
but changing the shape means a migration
```

The schema does not disappear. It moves from the database into the code. That is a transfer of responsibility, not free flexibility:

```txt
What becomes the application's job:
  - every read must tolerate documents in an older shape
    (field missing / different type / nesting changed)
  - a "migration" turns into a lazy upgrade on read, or a
    separate batch script — never a single DDL statement
  - analytics and business-intelligence tools cannot handle
    documents of different shapes
  - a new developer learns the data shape from the code, not
    from \d posts

What you get in return:
  - adding a field = deploying code, with no migration and no
    locks
  - heterogeneous entities (products with different attribute
    sets) live in one collection — no entity-attribute-value
    (EAV) table, no 40 nullable columns
  - one document's version may differ from its neighbour's, and
    sometimes that is exactly what you want (events, snapshots,
    audit records)
```

The discipline can be pushed back into the database with a schema validator. It is not a full replacement for DDL, but it stops obviously broken documents. That includes writes made outside the application — from `mongosh`, or from a migration script:

```js
db.createCollection("posts", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["title", "authorId", "createdAt"],
      properties: {
        title:     { bsonType: "string", minLength: 1, maxLength: 200 },
        authorId:  { bsonType: "objectId" },
        createdAt: { bsonType: "date" },
        tags:      { bsonType: "array", items: { bsonType: "string" } }
      }
    }
  },
  validationLevel: "moderate",   // strict — all writes; moderate — only
                                 // documents that were already valid
  validationAction: "error"      // error — reject; warn — log only
})
```

`validationLevel: "moderate"` is the practical mode for a collection that already holds historical documents. New records and already-valid records are checked; legacy ones can still be updated.

The second route, and the more common one in Node projects, is to keep the schema in Mongoose. Article 07 covers that. Remember that a Mongoose schema is an application-side check: `mongosh` and any other client bypass it.

## When MongoDB is a good fit and when it is not

Six signals in the requirements decide it, and none of them is "which database do we like":

| signal in the requirements | leans MongoDB | leans PostgreSQL |
|---|---|---|
| data shape | one aggregate read as a whole | relations, queries along any axis |
| schema | fields differ across records | fields are known and stable |
| writes | very high insert rate, sharding ahead | moderate, integrity matters more |
| transactions | one document changes | 3-5 tables change at once |
| analytics | reports known upfront | ad-hoc reports and joins |
| integrity | enforced by the application | foreign keys and `ON DELETE` |

Where MongoDB genuinely fits:

```txt
- The aggregate is read and written as a whole: an order with its
  line items, a post with an author preview and tags, a profile
  with its settings. One round-trip instead of a join — and no
  "assemble the entity from five tables" code.
- The data shape varies: a catalogue where a TV and a book share
  almost no attributes; integrations with external APIs that send
  an arbitrary payload.
- Write-heavy streams: events, logs, telemetry, sensor data from
  the internet of things (IoT). TTL indexes (time to live) expire
  documents automatically — see article 04 on indexes — and the
  Bucket pattern keeps them cheap, see article 03 on schema
  design.
- Horizontal scaling is built into the product: sharding is a
  first-class feature, not something added later. Article 06
  covers replication and sharding.
- Early product stage: the data shape changes weekly, and the
  cost of changing it matters more than strictness.
```

Where MongoDB gets in the way:

```txt
- The operation touches several entities by definition: a money
  transfer, or decrementing stock + creating an order + granting
  bonus points. Transactions exist, but they are the exception
  rather than the norm — a relational model is cheaper here.
- Referential integrity is mandatory: foreign keys, ON DELETE
  CASCADE, "a comment cannot exist without its post" enforced by
  the database. MongoDB has none of that — only application code.
- Ad-hoc analytics: reports "along any dimension", ad-hoc joins,
  business-intelligence tools. $lookup can join, but it is not a
  join chosen by a planner. See article 05 on the aggregation
  pipeline.
- Uniqueness or invariants spanning collections: a unique index
  only works inside one collection.
- A solid relational model already exists and works. Migrating
  for the sake of migrating gives you denormalization, duplicate
  data and synchronisation code, and nothing else.
```

And the caveat a senior is expected to raise without being asked: `jsonb` in PostgreSQL covers a large part of "we need a flexible schema". PostgreSQL indexes inside a `jsonb` document with GIN — a generalized inverted index — and full transactions sit right next to it. See article 01 of the PostgreSQL topic. So "we can store JSON in Mongo" is not, by itself, a justification for the choice.

## A framework for answering "why Mongo and not Postgres"

The weak answers interviewers hear most often are three: "Mongo is faster", "Mongo has no schema, it is easier to develop", "Mongo scales better". The first is meaningless without a workload. The second describes a drawback as a benefit. The third is only true for a specific query profile.

A strong answer is built along four axes, and it ends by naming the limit of applicability:

```txt
1. Data shape and access pattern
   "The main query is the whole order card: line items, address,
   status. That is one aggregate, read and written as a unit, so
   it lives as one document — instead of a four-table join on
   every request."

2. Consistency requirements
   "All order invariants live inside one document, so
   single-document atomicity is enough. Distributed transactions
   are not needed. If a stock decrement and an order insert had
   to be atomic together, that would argue for a relational
   database."

3. Scale and workload profile
   "We write about 5k events per second and read by key and by
   time range. We are ready to shard on tenantId. Analytics is a
   fixed set of reports, computed by aggregations on a
   secondary."

4. Operational context
   "The team already runs Atlas with backups and monitoring.
   Adding a second datastore for one service costs more than it
   saves."

5. The limit of applicability — what actually marks a senior
   "If billing with multi-entity transactions appears, or ad-hoc
   analytics becomes a requirement, that part moves to
   PostgreSQL. MongoDB stays for events and the catalogue."
```

The same framework runs in reverse. For "why Postgres and not Mongo" the bad answer is "Mongo is not a serious database". The good one names the data: "highly relational, queries arrive along every axis, so we need foreign keys (FK) and transactions. The flexible attributes went into a `jsonb` column".

## Connection to other topics

- **02 — CRUD and Query Operators.** CRUD is create, read, update, delete. The query language for documents, and single-document atomicity.
- **03 — Schema Design: Embedding vs Referencing.** The main consequence of the document model: what to embed and what to keep as a reference.
- **04 — Indexes and Query Performance.** The `_id_` index, TTL (time-to-live) indexes, indexes on nested fields.
- **06 — Replication, Transactions, and Consistency.** When single-document atomicity is not enough and a transaction is needed.
- **07 — Mongoose: Schemas, Models, and Validation.** How "the schema lives in code" becomes an explicit contract.
- **The PostgreSQL topic, article 01 — PostgreSQL Fundamentals.** The relational alternative: `jsonb`, types, referential integrity.

## Common interview traps

- **"BSON is just JSON in binary"** — BSON is typed. `Date`, `ObjectId`, `Decimal128` and `Int32/Int64` cannot be expressed in JSON. That is exactly why a document leaves the process as Extended JSON, where `_id` becomes a string.

- **"ObjectId is a random identifier like a UUID"** — the first 4 bytes are unix time. So sorting by `_id` almost matches sorting by creation time, and the date can be read out of the value. The cost: `_id` is a poor choice where unpredictability is required.

- **"MongoDB is schemaless, there is no schema"** — a schema always exists. The only question is where it is checked: in the database with `$jsonSchema`, in the application with Mongoose, or nowhere. "Nowhere" means it is checked at runtime, as bugs on documents of a different shape.

- **"Mongo is faster because it is NoSQL"** — NoSQL is only a label for "not relational", and a label is not a performance property. Speed comes from matching the schema to the access pattern, plus indexes. A badly designed schema with a `$lookup` on every request loses to an indexed normalized table.

- **"Mongo has no transactions"** — an outdated claim. Multi-document transactions exist since version 4.0 for a replica set and 4.2 for a sharded cluster. The correct statement: transactions exist, a good schema makes them rarely necessary, and they are not free.

- **"Money is stored as a normal number"** — `Double` produces the same rounding error as `Float` in SQL. Use `Decimal128`, or integer cents.

- **"Mongo fits because the data will change"** — a changing data shape does not remove the need to analyse access patterns and consistency requirements. And PostgreSQL has `jsonb`. Without that analysis the answer sounds like a choice made out of habit.
