# Replication, Transactions, and Consistency

## A replica set is the minimum production configuration

A standalone `mongod` is not used in production: without replicas there is neither fault tolerance nor transactions (they require a replica set). The standard configuration is three members: one primary and two secondaries.

```txt
A replica set: one write point, several copies of the data

 ┌─────────────────────────────────────────────────┐
 │ the application (the driver knows every member) │
 └─────────────────────────────────────────────────┘
                           │  every write goes to the primary only
                           ▼
  ┌───────────────────────────────────────────────┐
  │ PRIMARY                                       │
  │ applies the write and records it in the oplog │
  │ (local.oplog.rs — a capped collection)        │
  └───────────────────────────────────────────────┘
                           │  secondaries tail the oplog and apply the operations
                           ▼
┌─────────────────────┐    ┌─────────────────────────┐
│ SECONDARY           │    │ SECONDARY               │
│ a copy of the data, │    │ a candidate for primary │
│ may lag behind      │    │ during an election      │
└─────────────────────┘    └─────────────────────────┘

primary unavailable → an election (a few seconds) → a new primary from the majority
the oplog size sets the window in which a lagging member can still catch up
```

```txt
How it works:
  - ALL writes go to the primary only. A secondary accepts reads but
    never writes
  - the primary records every applied operation in the oplog — the
    capped collection local.oplog.rs
  - oplog entries are idempotent: {$inc: {views: 1}} becomes
    {$set: {views: 43}}, so re-applying is safe
  - secondaries continuously tail the oplog and apply the operations
  - the oplog size defines the recovery window: a member that falls
    behind by more than that window cannot catch up incrementally and
    needs a full initial sync
```

Elections and automatic failover are enough to understand mechanically, without the protocol:

```txt
  - members exchange heartbeats every 2 seconds
  - if the primary stops responding for ~10 seconds the secondaries
    start an election: the new primary is the member voted for by a
    MAJORITY of the set
  - "majority" is why member counts are odd: a 3-member set survives
    losing one; in a 2-member set losing either one removes the
    majority and writes stop
  - during an election (usually seconds) writes are impossible. The
    driver handles that itself: retryable writes are on by default and
    a single write is retried automatically
  - special roles: an arbiter votes but stores no data (usually a sign
    of cost-cutting that hurts later: majority writes are harder to
    acknowledge in such a set); hidden/delayed members exist for
    backups and analytics
```

## Read preference: where to read from

```js
// in the connection string
mongodb+srv://host/db?readPreference=secondaryPreferred

// or per query
db.posts.find(f).readPref("secondaryPreferred")
```

```txt
primary             — the primary only (the default)
primaryPreferred    — the primary, or a secondary if it is unavailable
secondary           — secondaries only
secondaryPreferred  — a secondary, or the primary if none are available
nearest             — the member with the lowest network latency
```

Reading from a secondary looks like a free way to "offload the database", and that is exactly why it is one of the most common mistakes:

```txt
1. Read-your-own-write breaks. A user saves their profile (a write to
   the primary) and immediately opens the page (a read from a
   secondary that has not applied the operation yet) → they see the
   OLD data and conclude the save did not work.

2. Replication lag is unpredictable. Normally it is milliseconds, but
   during a write spike, a long index build or on a slow disk a
   secondary falls behind by seconds or minutes. All you can bound is
   the member selection: maxStalenessSeconds: 90 (the driver will not
   read from members lagging more than that).

3. Writes do not scale. Every secondary applies THE SAME writes as the
   primary: adding replicas does not increase write throughput.
   Replicas scale reads only — and at the cost of stale data.

When reading from a secondary is appropriate:
  - reports and analytics (yesterday's data will not go stale)
  - heavy aggregations that should not compete with production traffic
    (see [Aggregation Pipeline])
  - geo-distributed reads via nearest/tags
  - data exports and backup jobs
```

If you need both primary offloading and the "I will see my own write" guarantee, the answer is a causally consistent session: the driver carries the operation's logical time, and the read waits until the member catches up.

```js
const session = client.startSession();   // causalConsistency: true by default
await posts.updateOne({ _id }, { $set: { title } }, { session });
const fresh = await posts.findOne({ _id }, { session });  // sees the write
```

## Write concern: what "the write was acknowledged" means

```txt
                     What "the write was acknowledged" actually means
┌────────────────────────┬──────────────────────────────────┬───────────────────────────┐
│ setting                │ acknowledged once                │ the risk you take         │
├────────────────────────┼──────────────────────────────────┼───────────────────────────┤
│ w: 0                   │ the driver sent the packet       │ the write may never apply │
├────────────────────────┼──────────────────────────────────┼───────────────────────────┤
│ w: 1                   │ the primary applied it           │ rollback on failover      │
├────────────────────────┼──────────────────────────────────┼───────────────────────────┤
│ w: 1, j: true          │ the primary journaled it         │ rollback on failover      │
├────────────────────────┼──────────────────────────────────┼───────────────────────────┤
│ w: "majority"          │ a majority of members applied it │ higher latency            │
├────────────────────────┼──────────────────────────────────┼───────────────────────────┤
│ w: "majority", j: true │ a majority journaled it          │ the highest latency       │
└────────────────────────┴──────────────────────────────────┴───────────────────────────┘
                      since MongoDB 5.0 the default is w: "majority"
           wtimeout bounds the wait but does NOT undo an already applied write
```

```js
await db.collection("orders").insertOne(doc, {
  writeConcern: { w: "majority", j: true, wtimeout: 5000 }
});
```

```txt
The parameters:
  w  — how many members must acknowledge the operation.
       1 — the primary only; "majority" — a majority of the set;
       0 — do not wait for acknowledgement at all (fire-and-forget)
  j  — wait until the operation reaches the journal (disk) rather than
       staying in memory only. Protects against loss if the member
       shuts down abruptly
  wtimeout — how long to wait for acknowledgement. On expiry the driver
       gets an error, but the operation MAY ALREADY BE APPLIED:
       wtimeout cancels the wait, not the write
```

The key scenario that explains the difference between `w: 1` and `w: "majority"`:

```txt
  1. a client writes with w: 1 → the primary applies it and
     acknowledges to the client
  2. the secondaries have not received the operation from the oplog yet
  3. the primary crashes
  4. an election picks a new primary from members that never saw the
     operation
  5. the old member comes back, finds an operation absent from the new
     primary's history and ROLLS IT BACK, dumping it into a file on
     disk

Result: the client got "success" and the data is not in the database.
This is exactly what w: "majority" protects against: the
acknowledgement arrives once a majority has the operation, which means
any future primary contains it.

That is why, starting with MongoDB 5.0, the default write concern is
w: "majority". On older clusters and older applications the default
was w: 1 — worth checking.
```

## Read concern: which data counts as existing

```txt
local         — return the member's most recent data even if it is not
                yet majority-acknowledged (and could therefore be
                rolled back). The default for reads from the primary
available     — like local, but on a sharded cluster it does not wait
                for consistency with the config servers (fast, but it
                can return orphaned documents)
majority      — return only data acknowledged by a majority, which
                therefore will NOT be rolled back
snapshot      — read from a consistent snapshot; used in transactions
linearizable  — the strictest for a single document: guarantees the
                read sees every successful write that completed before
                it; expensive, requires the primary and w: "majority"
```

The real guarantees come from the combination of three settings, and this is exactly the question that separates "read the docs" from "operated it in production":

```txt
w: "majority" + readConcern: "majority" + readPreference: primary
  → strict: acknowledged data will not roll back and reads see it

w: 1 + readConcern: "local"
  → fast, but an acknowledged write can disappear on failover

w: "majority" + readPreference: secondaryPreferred, no session
  → the write is durable, but you may not see your own change
    immediately

w: "majority" + a causally consistent session + a secondary
  → durable and read-your-own-write works, at the cost of waiting for
    the member to catch up
```

A phrasing for interviews: write concern answers "when does a write count as done", read concern answers "which data counts as existing", read preference answers "who do I ask". Three independent knobs — and "consistency" without naming all three is an empty word.

## Multi-document transactions

Transactions arrived in 4.0 for replica sets and 4.2 for sharded clusters. The claim "MongoDB has no transactions" is outdated.

```js
const session = client.startSession();
try {
  await session.withTransaction(async () => {
    // Inside a transaction, session MUST be passed to every operation
    const post = await posts.findOneAndUpdate(
      { _id: postId },
      { $inc: { "stats.comments": 1 } },
      { session, returnDocument: "after" }
    );
    if (!post) throw new Error("post not found");   // throw → abort

    await comments.insertOne(
      { postId, body, author, createdAt: new Date() },
      { session }
    );
  }, {
    readConcern:  { level: "snapshot" },
    writeConcern: { w: "majority" }
  });
} finally {
  await session.endSession();
}
```

```txt
What matters about the API:
  - withTransaction retries TransientTransactionError (write conflict,
    primary change) and UnknownTransactionCommitResult by itself. You
    do not need to write a retry loop
  - an operation WITHOUT { session } inside the block runs OUTSIDE the
    transaction. This is the most common mistake: half the operations
    roll back, half stay
  - the callback may run more than once, so it must be idempotent: no
    "send an email" or "charge an external API" inside
  - a throw inside the callback aborts the whole transaction
```

```txt
The cost of transactions:
  - snapshot isolation: a concurrent write to the same documents
    produces a WriteConflict and the transaction retries — under
    contention that is a noticeable throughput loss
  - a time limit: 60 seconds by default
    (transactionLifetimeLimitSeconds). A long transaction is aborted
    by the server
  - pending changes occupy the WiredTiger cache until commit
  - on a sharded cluster the transaction becomes distributed (a
    two-phase commit across shards) — an order of magnitude more
    expensive
  - a long transaction holds a snapshot and blocks cleanup of old
    versions
```

When a transaction is genuinely needed:

```txt
  - the invariant spans several DOCUMENTS and divergence is
    unacceptable: debit account A and credit account B
  - create an entity plus a related record in another collection where
    "half done" means corrupted data: an order plus a stock reservation
  - delete an aggregate together with its child documents so that no
    dangling references remain, when that is critical

When a transaction is not needed but gets written anyway:
  - changing one document — it is already atomic, even when ten fields
    and an array change (see [CRUD and Query Operators])
  - incrementing a counter — that is $inc
  - "read, check, write" — that is findOneAndUpdate with the condition
    in the filter
  - updating denormalized copies where eventual consistency is fine
    (Extended Reference, Subset — see [Schema Design: Embedding vs
    Referencing])
```

Hence the main point of this section: transactions in MongoDB are not a substitute for schema design. If the aggregate is designed so that the invariant lives inside a single document, no transaction is needed at all. If transactions are required for every other request, that signals a relational schema — and it is time to reconsider either the schema or the database choice (see [Document Model and Use Cases]).

## Sharding — an overview

A replica set solves availability but not volume: every member holds all the data, and all writes go through one primary. When the data or the write throughput stops fitting on one machine, the collection is sharded — distributed across several replica sets.

```txt
The components of a sharded cluster:
  shard          — a replica set holding a subset of the data
  config servers — a replica set with the metadata: which key range
                   lives on which shard
  mongos         — the router the application connects to; it knows
                   the distribution and directs queries
```

The key decision is the **shard key**: the field (or combination of fields) the data is distributed by. It determines cluster performance and is expensive to change (`reshardCollection` arrived in 5.0, but it is a heavy operation).

```txt
TARGETED: the filter contains the shard key    SCATTER-GATHER: no shard key in the filter
┌────────────────────────────────────┐         ┌───────────────────────────────────┐
│ find({ tenantId: "acme", _id: x }) │         │ find({ status: "published" })     │
│                                    │         │                                   │
│ mongos → shard 2                   │         │ mongos → every shard → merge      │
│                                    │         │                                   │
│ shard 1  ·  [shard 2]  ·  shard 3  │         │ [shard 1] · [shard 2] · [shard 3] │
└────────────────────────────────────┘         └───────────────────────────────────┘
     the query goes to ONE shard;                  every shard runs the query and
  scales linearly with their number            mongos merges; the sort happens there too
```

```js
sh.shardCollection("blog.posts", { tenantId: 1, _id: 1 })   // ranged
sh.shardCollection("blog.events", { _id: "hashed" })        // hashed
```

```txt
ranged (by value ranges)
  + range queries on the key hit one or two shards
  + data for one tenant/user lives together
  - a monotonically increasing key (ObjectId, timestamp) sends EVERY
    insert to one shard — the hot shard, the classic mistake

hashed (by hash of the value)
  + inserts spread evenly even for a monotonic field
  - range queries become scatter-gather: adjacent values live on
    different shards
```

The consequences of a bad shard key are what senior interviews ask about:

```txt
hot shard          — a monotonic key with ranged distribution: the
                     entire write stream goes to one shard while the
                     rest sit idle

jumbo chunks       — low key cardinality (country, status): every
                     document with the same value must live together,
                     so the chunk grows beyond the split limit and
                     balancing breaks

scatter-gather     — a filter without the shard key: mongos broadcasts
                     the query to EVERY shard and merges the results.
                     Latency is set by the slowest shard, and adding
                     shards makes such queries worse, not better

restrictions       — a unique index is only possible on the shard key
                     (or its prefix); the shard key value cannot be
                     changed freely in a document; a sort without the
                     shard key is performed on mongos
```

The practical selection criteria: the key should (1) have high cardinality, (2) distribute writes evenly, (3) be present in most read queries. A compound key like `{ tenantId: 1, _id: 1 }` often satisfies all three: tenant isolation gives targeted queries, and `_id` inside provides cardinality.

And an honest caveat: sharding answers a volume problem, not a slow-query problem. A slow query on a sharded cluster becomes slow on N shards. Indexes and schema first (see [Indexes and Query Performance]), sharding after.

## How to answer a question about guarantees

```txt
"What consistency guarantees does MongoDB give" has no single answer —
and that is the correct answer. The framework:

1. A single document is always atomic — the base guarantee everything
   else is built on.

2. Write durability is set by write concern. The default (5.0+) is
   w: "majority": an acknowledged write will not be rolled back.

3. Data visibility is set by read concern and read preference. Reading
   from the primary with local is fresh but theoretically rollback-able;
   majority returns only acknowledged data; reading from a secondary is
   eventual consistency.

4. There is no atomicity across documents or collections without a
   transaction. Transactions exist and give snapshot isolation, but
   their cost is conflicts and retries — which is why a good schema
   avoids them.

5. Causal consistency ("I will see my own write") comes from sessions,
   not from the member selection.
```

## Connection to other topics

```txt
[CRUD and Query Operators]        — single-document atomicity,
                                    findOneAndUpdate as a substitute
                                    for a transaction
[Schema Design: Embedding vs      — why a good schema makes
 Referencing]                       transactions rare; eventual
                                    consistency for duplicates
[Indexes and Query Performance]   — the hashed index for a shard key,
                                    TTL and the oplog, indexes before
                                    sharding
[Aggregation Pipeline]            — heavy aggregations on a secondary,
                                    $merge for materialized reports
[Mongoose Queries, populate,      — connection pooling and retryable
 and Pitfalls]                      writes at the driver level,
                                    transactions in Mongoose sessions
the PostgreSQL topic,             — the comparison baseline: ACID,
[ACID and Transactions],            isolation levels and MVCC in a
[Transaction Isolation Levels]      relational database
```

## Common interview traps

- **"MongoDB has no transactions"** — it has them since 4.0 (replica set) and 4.2 (sharded cluster). The correct phrasing: transactions exist and provide snapshot isolation, but they are expensive, and a good schema makes them rare.

- **"Reading from a secondary offloads the database for free"** — that is eventual consistency: a user may not see their own write. And the lag is unpredictable. Bound it with `maxStalenessSeconds`, fix it with a causally consistent session.

- **"Replicas scale writes"** — every secondary applies the same operations as the primary. Replicas provide availability and read scaling; only sharding scales writes.

- **"The write succeeded, so it is in the database"** — with `w: 1` an acknowledged write can be rolled back on failover. The guarantee comes from `w: "majority"`, which is the default since 5.0 (but not on older clusters).

- **"`wtimeout` cancels the write"** — it only cancels the wait for acknowledgement. The operation may already be applied, so getting a `wtimeout` error and retrying is a path to duplicates unless the operation is idempotent.

- **"A transaction is needed to update two fields of one document"** — a single operation on a single document is atomic by itself, arrays and nested objects included.

- **"Everything inside `withTransaction` is automatically transactional"** — only the operations that were given the `session`. A forgotten `session` quietly runs outside the transaction.

- **"A transaction can be held as long as needed"** — 60 seconds by default, after which the server aborts it; and all that time the changes occupy cache and hold a snapshot.

- **"ObjectId is a good shard key"** — it is monotonic: with ranged distribution the entire insert stream goes to one shard (hot shard). Use `hashed` or a compound key with a tenant field in front.

- **"Sharding will speed up slow queries"** — a query without the shard key turns into a scatter-gather across all shards, and adding shards makes it worse. Indexes and schema first, sharding after.
