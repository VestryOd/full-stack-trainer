# Document Model and Use Cases

## A document instead of a row: the unit of storage in MongoDB

In a relational database an entity is spread across tables, and a query reassembles it with joins. In MongoDB the unit of storage is the document: a self-contained structure with nested objects and arrays that can be written and read in a single round-trip.

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

The same post in PostgreSQL is `posts` + `users` + `post_tags` + `tags` and three or four joins per read. The difference is not "better or worse" but where the entity gets assembled: in the database on every read (SQL), or once on write (a document).

A collection is a container of documents — the analogue of a table, but with no declared structure. The basic vocabulary:

```txt
database    → a set of collections (like a schema/database in PostgreSQL)
collection  → a set of documents (like a table, but with no DDL)
document    → a BSON object, 16 MB maximum (like a row)
field       → a key inside a document (like a column, except every
              document has its own set)
```

## BSON is not JSON: the types JSON does not have

On the wire and on disk MongoDB uses BSON (Binary JSON) — a binary format where every field carries an explicit type and length. Two practical properties follow: the engine can skip fields without fully parsing them, and types survive a round-trip.

```txt
BSON types that JSON does not have:
  ObjectId     — a 12-byte identifier, the default value of _id
  Date         — int64, milliseconds since epoch, ALWAYS UTC
  Decimal128   — decimal number with exact arithmetic (money)
  Int32/Int64  — fixed-width integers (JSON only has "number")
  Double       — IEEE 754, same behaviour as a JS number
  Binary       — bytes + subtype (a UUID, for example)
  Regex        — a regular expression as a field value
  Timestamp    — an INTERNAL oplog type, not for application dates
```

Three traps that grow out of the BSON/JSON gap:

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

// 3. Dates. The string "2026-07-14" is NOT a Date: range queries on it
//    compare lexicographically, not chronologically.
db.posts.insertOne({ publishedAt: "2026-07-14" })            // a string
db.posts.insertOne({ publishedAt: new Date("2026-07-14") })  // BSON Date
```

When a document leaves the process over HTTP, BSON is serialized to Extended JSON — in relaxed mode `ObjectId` becomes a string and `Date` an ISO string. That is why an API returns `"_id": "66b0f2c1..."` rather than an object, and the reverse mapping (string → ObjectId) belongs to the application layer. `new ObjectId(req.params.id)` throws on an invalid string — the first place where input validation is required.

## _id and how ObjectId is built

Every document has an `_id`: mandatory, unique within the collection, immutable after insert. A unique index `_id_` is created for it automatically and cannot be dropped. If `_id` is not set explicitly, the driver (not the server) generates an `ObjectId`.

```txt
                     ObjectId is 12 bytes, not a random UUID
┌───────┬───────────────────────────┬───────────────────────────────────────────┐
│ bytes │ what is inside            │ practical consequence                     │
├───────┼───────────────────────────┼───────────────────────────────────────────┤
│ 0-3   │ unix time in seconds, UTC │ sorting by _id ~ sorting by creation time │
├───────┼───────────────────────────┼───────────────────────────────────────────┤
│ 4-8   │ random per-process value  │ two processes never generate the same id  │
├───────┼───────────────────────────┼───────────────────────────────────────────┤
│ 9-11  │ per-process counter       │ order within the same second is preserved │
└───────┴───────────────────────────┴───────────────────────────────────────────┘
            time granularity is 1 second: within one second the order
                     across different processes is undefined
```

What that layout gives you in practice:

```js
// The creation time is inside _id itself — a separate createdAt field is
// not required (though usually still useful: it can be backfilled, _id
// cannot).
ObjectId("66b0f2c14a1e2d0012ab34cd").getTimestamp()  // ISODate(...)

// Sorting by _id ~ sorting by creation time → free keyset pagination
// for "newest first" on the index that already exists (_id_).
db.posts.find({ _id: { $lt: lastSeenId } }).sort({ _id: -1 }).limit(20)

// A time range can be expressed through _id built from a timestamp.
db.posts.find({ _id: { $gte: ObjectId.createFromTime(1750000000) } })
```

What ObjectId does not guarantee: a strict global ordering (within the same second the order across processes is arbitrary) and secrecy — the value exposes the creation time, and documents created by the same process have adjacent ids. For public URLs where that matters, use a separate unpredictable field instead of `_id`.

A custom `_id` is allowed and sometimes worth it: a natural key (`_id: "mongodb-indexes"` for a slug, `_id: userId` in a 1:1 profile collection) removes one index and makes the "one record, one key" relationship explicit. The cost is the same B-tree locality trade-off as with UUIDs (see the PostgreSQL topic): a monotonic ObjectId lands at the right edge of the tree, a random key lands anywhere.

## "Schemaless" does not mean "no schema"

A collection accepts any document: missing fields, a field with a different type, a brand-new nested object. There is no DDL, no `ALTER TABLE`; adding a field is just another `$set`.

```txt
      MongoDB: the schema lives in the code           PostgreSQL: the schema lives in the DB
┌────────────────────────────────────────────────┐    ┌────────────────────────────────────┐
│ collection posts                               │    │ table posts                        │
│                                                │    │                                    │
│ { title, authorId, tags }                      │    │ title      text   NOT NULL         │
│ { title, authorId }          ← no tags         │    │ author_id  bigint REFERENCES users │
│ { title, author: {...} }     ← different shape │    │ tags       text[] DEFAULT ARRAY[]  │
└────────────────────────────────────────────────┘    └────────────────────────────────────┘
   the DB accepts anything; the code must check           the DB rejects a wrong shape,
  (a Mongoose schema or a $jsonSchema validator)      but changing the shape means a migration
```

The schema does not disappear — it moves from the database into the code. That is a transfer of responsibility, not free flexibility:

```txt
What becomes the application's job:
  - every read must tolerate documents in an older shape
    (field missing / different type / nesting changed)
  - a "migration" turns into a lazy upgrade on read or a
    separate batch script — never a single DDL statement
  - analytics and BI trip over heterogeneous documents
  - a new developer learns the data shape from code, not from \d posts

What you get in return:
  - adding a field = deploying code, with no migration and no locks
  - heterogeneous entities (products with different attribute sets)
    live in one collection without EAV and without 40 nullable columns
  - one document's version may differ from its neighbour's — sometimes
    that is exactly what you want (events, snapshots, audit records)
```

The discipline can be pushed back into the database with a schema validator. It is not a full replacement for DDL, but it stops obviously broken documents — including writes made outside the application (from the shell, from a migration script):

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

`validationLevel: "moderate"` is the practical mode for an existing collection with historical documents: new and already-valid records are checked, legacy ones can still be updated. The second and more common route in Node projects is to keep the schema in Mongoose (see [Mongoose: Schemas, Models, and Validation]), remembering that this is an application-side check: `mongosh` and any other client bypass it.

## When MongoDB is a good fit and when it is not

```txt
┌────────────────────────────┬───────────────────────────────────────┬───────────────────────────────────┐
│ signal in the requirements │ leans MongoDB                         │ leans PostgreSQL                  │
├────────────────────────────┼───────────────────────────────────────┼───────────────────────────────────┤
│ data shape                 │ one aggregate read as a whole         │ relations, queries along any axis │
├────────────────────────────┼───────────────────────────────────────┼───────────────────────────────────┤
│ schema                     │ fields differ across records          │ fields are known and stable       │
├────────────────────────────┼───────────────────────────────────────┼───────────────────────────────────┤
│ writes                     │ very high insert rate, sharding ahead │ moderate, integrity matters more  │
├────────────────────────────┼───────────────────────────────────────┼───────────────────────────────────┤
│ transactions               │ one document changes                  │ 3-5 tables change at once         │
├────────────────────────────┼───────────────────────────────────────┼───────────────────────────────────┤
│ analytics                  │ reports known upfront                 │ ad-hoc JOINs and BI queries       │
├────────────────────────────┼───────────────────────────────────────┼───────────────────────────────────┤
│ integrity                  │ enforced by the application           │ FK and ON DELETE required         │
└────────────────────────────┴───────────────────────────────────────┴───────────────────────────────────┘
```

Where MongoDB genuinely fits:

```txt
- The aggregate is read and written as a whole: an order with its line
  items, a post with an author preview and tags, a profile with its
  settings. One round-trip instead of a join — and no "assemble the
  entity from five tables" code.
- The data shape varies: a catalogue where a TV and a book have almost
  no overlapping attributes; integrations with external APIs that send
  an arbitrary payload.
- Write-heavy streams: events, logs, telemetry, IoT — plus TTL indexes
  for automatic expiry (see [Indexes and Query Performance]) and the
  Bucket pattern (see [Schema Design: Embedding vs Referencing]).
- Horizontal scaling is built into the product: sharding is a first-class
  feature, not a bolt-on (see [Replication, Transactions, and
  Consistency]).
- Early product stage: the data shape changes weekly, and the cost of
  changing it matters more than strictness.
```

Where MongoDB gets in the way:

```txt
- The operation touches several entities by definition: a money
  transfer, decrementing stock + creating an order + granting bonus
  points. Transactions exist, but they are the exception rather than
  the norm — a relational model is cheaper here.
- Referential integrity is mandatory: FK, ON DELETE CASCADE, "a comment
  cannot exist without its post" enforced by the database. MongoDB has
  none of that — only application code.
- Ad-hoc analytics: reports "along any dimension", ad-hoc JOINs, BI
  tools. $lookup can join, but it is not a planner-level JOIN
  (see [Aggregation Pipeline]).
- Uniqueness or invariants spanning collections: a unique index only
  works inside one collection.
- A solid relational model already exists and works: migrating for the
  sake of migrating buys denormalization, duplicates and sync code.
```

And the honest caveat a senior is expected to raise unprompted: `jsonb` in PostgreSQL covers a large part of "we need a flexible schema" — with GIN indexes over the document and full transactions next to it (see the PostgreSQL topic, [PostgreSQL Fundamentals]). So "we can store JSON in Mongo" is not, by itself, a justification for the choice.

## A framework for answering "why Mongo and not Postgres"

The weak answers interviewers hear most often: "Mongo is faster", "Mongo has no schema, it is easier to develop", "Mongo scales better". The first is meaningless without a workload, the second describes a drawback as a benefit, the third is only true for a specific query profile.

A grown-up answer is built along four axes — and ends by naming the limit of applicability:

```txt
1. Data shape and access pattern
   "The main query is the whole order card: line items, address,
   status. That is one aggregate read and written as a unit, so it
   lives as one document — instead of a four-table join on every
   request."

2. Consistency requirements
   "All order invariants live inside one document, so single-document
   atomicity is enough; distributed transactions are not needed. If
   stock decrement and order creation had to be atomic together, that
   would be an argument for a relational database."

3. Scale and workload profile
   "We write ~5k events/s and read by key and by time range. We are
   ready to shard on tenantId. Analytics is a fixed set of reports
   computed by aggregations on a secondary."

4. Operational context
   "The team already runs Atlas with backups and monitoring; adding a
   second datastore for one service costs more than it saves."

5. The limit of applicability (what actually marks a senior)
   "If billing with multi-entity transactions appears, or ad-hoc
   analytics becomes a requirement, that part moves to PostgreSQL and
   MongoDB stays for events and the catalogue."
```

The same framework runs in reverse. For "why Postgres and not Mongo" the bad answer is "Mongo is not a serious database"; the good one is "the data is highly relational, queries arrive along every axis, we need FK and transactions; the flexible attributes went into a `jsonb` column".

## Connection to other topics

```txt
[CRUD and Query Operators]        — the query language for documents
                                    and single-document atomicity
[Schema Design: Embedding vs      — the main consequence of the document
 Referencing]                       model: what to embed and what to
                                    keep as a reference
[Indexes and Query Performance]   — the _id_ index, TTL indexes,
                                    indexes on nested fields
[Replication, Transactions, and   — when single-document atomicity is
 Consistency]                       not enough and a transaction is needed
[Mongoose: Schemas, Models, and   — turning the "schema lives in code"
 Validation]                        situation into an explicit contract
the PostgreSQL topic,             — the relational alternative: jsonb,
[PostgreSQL Fundamentals]           types, referential integrity
```

## Common interview traps

- **"BSON is just JSON in binary"** — BSON is typed: `Date`, `ObjectId`, `Decimal128`, `Int32/Int64` cannot be expressed in JSON. That is exactly why a document leaves the process as Extended JSON, where `_id` becomes a string.

- **"ObjectId is a random identifier like a UUID"** — the first 4 bytes are unix time, so sorting by `_id` almost matches sorting by creation time and the date can be extracted from the value. The flip side: `_id` is a poor choice where unpredictability is required.

- **"MongoDB is schemaless, there is no schema"** — a schema always exists; the only question is where it is checked: in the database (`$jsonSchema`), in the application (Mongoose), or nowhere — in which case it is checked at runtime, in the form of bugs on heterogeneous documents.

- **"Mongo is faster because it is NoSQL"** — speed comes from matching the schema to the access pattern, plus indexes. A badly designed schema with a `$lookup` on every request will lose to an indexed normalized table.

- **"Mongo has no transactions"** — an outdated claim: multi-document transactions exist since 4.0 (replica set) and 4.2 (sharded cluster). The correct statement is: transactions exist, but a good schema makes them rarely necessary, and they are not free.

- **"Money is stored as a normal number"** — `Double` produces the same rounding error as `Float` in SQL. Use `Decimal128` or integer cents.

- **"Mongo fits because the data will change"** — a changing data shape does not remove the need to analyse access patterns and consistency requirements; and PostgreSQL has `jsonb`. Without that analysis the answer sounds like a choice made out of habit.
