# MongoDB + Mongoose: Interview Questions (Middle → Senior)

## How to use this cheat sheet

Every answer below is a condensed version of what the articles in this topic cover in detail. In an interview almost none of these questions is the final one — each is a lead-in to a follow-up: "why?", "what if the data grows 100x?", "show me on our domain". That is why each group ends with a **"Typical follow-ups"** section showing where the interviewer usually goes next. If a follow-up catches you off guard, that is a signal to go back to the matching article.

A note on delivery. MongoDB questions attract slogans more than most ("Mongo is faster", "there is no schema", "populate is N+1"). A strong answer always contains mechanics and a limit of applicability, not a verdict.

## Group 1: the document model and choosing a database

**1. How does BSON differ from JSON, and what does the ObjectId layout give you?**

BSON is a binary typed format: every field carries an explicit type and length, so the engine can skip fields without fully parsing them and types survive a round-trip. JSON has no `Date`, `ObjectId`, `Decimal128` or `Int32/Int64` — hence the practical consequences: money must be stored as `Decimal128` or integer cents (otherwise you get the same rounding error as `Float` in SQL), and a date must be a BSON `Date` rather than a string, or range queries compare lexicographically. `ObjectId` is 12 bytes whose first 4 are unix time in seconds: sorting by `_id` nearly matches sorting by creation time, the date can be extracted from the value (`getTimestamp()`), and keyset pagination "newest first" comes free on the `_id` index. The flip side: an `ObjectId` is predictable and exposes the creation time, so public URLs that care about that need a separate unpredictable field. At the API boundary BSON is serialized to Extended JSON — `_id` becomes a string, and the reverse "string → ObjectId" mapping is where input validation is mandatory. See [Document Model and Use Cases].

---

**2. MongoDB is called schemaless. What does that actually mean?**

That the schema is not enforced by the database, not that there is none. A collection accepts a document of any shape, and there is no DDL or `ALTER TABLE` — but the data shape still exists; it has simply moved from the database into the application code. That is a transfer of responsibility: every read must tolerate documents in an older shape, a "migration" becomes a lazy upgrade on read or a batch script, analytics trips over heterogeneous documents, and a new developer learns the shape from code rather than from `\d posts`. In return, adding a field is a code deploy with no migration and no locks, and heterogeneous entities live in one collection without EAV and without 40 nullable columns. The discipline can be partly pushed back into the database with a `$jsonSchema` validator and `validationLevel: "moderate"` (importantly, it also catches writes made outside the application — from the shell, from a script), while Node projects usually keep the schema in Mongoose, remembering that this is an application-side check. See [Document Model and Use Cases] and [Mongoose: Schemas, Models, and Validation].

---

**3. Why did you choose MongoDB over PostgreSQL?**

The answer runs along four axes and ends with a limit of applicability. First, data shape and access pattern: "the main query is the whole order card; it is read and written as one aggregate, so it lives as one document instead of a four-table join". Second, consistency requirements: "all order invariants are inside one document, so single-document atomicity is enough; if stock decrement and order creation had to be atomic together, that would be an argument for a relational database". Third, scale and workload profile: how much we write, how we read, whether we are ready to shard. Fourth, operational context: what the team already knows how to run. And the closing part that marks a senior: "if billing with multi-entity transactions or ad-hoc analytics appears, that part moves to PostgreSQL". Separately, raise the honest caveat unprompted: `jsonb` in PostgreSQL covers a large share of "we need a flexible schema", with full transactions right next to it — so "we can store JSON in Mongo" does not by itself justify the choice. See [Document Model and Use Cases] and the PostgreSQL topic, [PostgreSQL Fundamentals].

## Typical follow-ups (group 1)

```txt
"Fine, but what if tomorrow you need a report along an arbitrary
dimension?" → they check whether you admit the weak spot:
aggregations exist but ad-hoc JOINs do not; the answer is
materialized views via $merge, or moving analytics to a separate
store

"You said the schema lives in the code. How do you roll out a shape
change across 50 million records?" → lazy upgrade on read, a
background script, a schema-version field in the document; and why
not "one migration overnight"

"Why do we need _id at all if we have a slug?" → the _id_ unique
index always exists; a custom _id (the slug) removes one index but
pays in B-tree locality on insert

"Money in a Double — what exactly breaks?" → they want a concrete
example of accumulating rounding error, not "that's not done"
```

## Group 2: schema design

**4. Embedding or referencing — what criteria do you use?**

Four of them, and the order matters. First, cardinality in terms of "how many can there ever be", not "how many now": one-to-few (3–10 tags) gets embedded, one-to-many (comments) moves out with a reference, one-to-squillions (views) lives separately with bucketing. Second, access pattern: if the child data is always needed when the parent is read — embedding; if it needs independent access ("all comments by a user", moderation), its own pagination and sorting — a separate collection. Third, change frequency: duplicate what rarely changes and is almost always read (author name and avatar), never duplicate what changes often or is critical (email, roles). Fourth, growth bounds: can a user grow this set of elements without any limit? If yes, embedding is a deferred incident. And the starting point is not the entities but a list of the top-5 queries with their rates: without it any answer about embedding is guesswork. The rule everything reduces to: what is read together is stored together. See [Schema Design: Embedding vs Referencing].

---

**5. A concrete case: comments on a post — embed or reference?**

A reference plus a Subset — and the reasoning matters more than the answer. Comments have no upper bound: 99% of posts will have 20, but one viral post will have 50,000, and the schema has to survive exactly that. Full embedding hits the 16 MB limit, but it breaks long before that: WiredTiger does not patch a document in place, so every `$push` rewrites the whole document, the whole document is read into memory and sent over the network, and a multikey index on the array gets one entry per element. So comments live in their own collection with a `postId` reference (which needs an index), giving proper pagination, sorting and independent moderation. At the same time the post page shows the first three comments on 95% of views — those are kept in the post itself as a fixed-length array via `$push` with `$sort` and `$slice: 3`. The cost: there are now two writes and they are not atomic, so insert into `comments` first (the source of truth) and update the preview second — that way a failure loses a cache, not data. See [Schema Design: Embedding vs Referencing] and [CRUD and Query Operators].

---

**6. Which design patterns do you use and what do they cost?**

Extended Reference: the post stores not `authorId` but `author: { _id, name, avatar }` — exactly the fields that get rendered. It removes the second query on every page and every feed item; the cost is that duplicates must be updated, and you must say by which mechanism (a background job, change streams) or that it is a deliberate snapshot of "the name as of publication". Subset: the hot slice inside the document with a mandatory `$slice`, without which the pattern becomes an anti-pattern. Bucket: a document per bucket (`postId` + hour) rather than per event, with `upsert` and `$inc` — millions of tiny documents become 24 per post per day, and a weekly report reads 168 documents instead of 70 million; a unique index on the bucket key is mandatory, otherwise an upsert race creates two. Computed: the comment counter is stored ready and changed with an atomic `$inc` instead of `countDocuments()` on every feed read; the mandatory companion is a background recompute from the source of truth, because the counter will drift eventually. The general principle: for every pattern name not only the benefit but what you pay. See [Schema Design: Embedding vs Referencing].

---

**7. What is wrong with a fully normalized schema in MongoDB — and what is the danger of the opposite, massive denormalization?**

Full normalization in Mongo is the worst of both worlds. Joins nominally exist, but `$lookup` runs as a sub-query per input document, with no hash join and no join-order choice by a planner, and `populate` in Mongoose is separate queries entirely; meanwhile integrity is still absent — no FK, no `ON DELETE CASCADE`, no cross-collection checks; transactions become necessary at every step and cost more than in a relational database. So you end up with a relational schema without relational guarantees and without a relational optimizer. If the data genuinely requires normalization along every axis, the right conclusion is to use PostgreSQL. The opposite extreme: copying the full author document into every post and comment. Then an email change becomes an `updateMany` over millions of documents with no transaction around it, a mid-way failure leaves the system in two states, and a GDPR deletion becomes a hunt for copies across every collection. The question an interviewer asks: "who updates the duplicates and when, and what happens on a mid-way failure?" A good answer names a concrete mechanism, or honestly says "it is a snapshot, we never update it". See [Schema Design: Embedding vs Referencing] and [Aggregation Pipeline].

## Typical follow-ups (group 2)

```txt
"A post has 40,000 embedded comments. What will you see in the
metrics before the BSONObjectTooLarge error?" → rising write
latency (document rewrites), growing read traffic, a bloated
multikey index, large oplog entries

"An author changed their name. Describe what happens in the
system" → updateMany by author._id (with an index on that field),
eventual consistency between the two writes, an idempotent
background job

"How will you know it is time to change the schema?" → slow
queries that need a $lookup on the hot path; documents in the
hundreds of kilobytes; a growing number of transactions

"Design the schema for likes: 1M users liking posts" → they check
whether you propose an array of userIds in the post (unbounded);
they expect a separate collection plus a Computed counter
```

## Group 3: queries, updates and atomicity

**8. What exactly does single-document atomicity guarantee, and when do you still need a transaction?**

Any write operation on a SINGLE document is atomic: either all its changes apply or none. That holds for several fields, nested objects and array elements at once — so a `$push` of a comment together with an `$inc` of the counter and an `updatedAt` update in one `updateOne` is never observed half-applied. State the boundaries precisely: `updateMany` over 100 documents is 100 separate atomic operations, and in between you can see half of them updated; two operations in a row in application code are not atomic either, even on the same document. A transaction is needed when the invariant spans several documents and divergence is unacceptable: a transfer between accounts, an order plus a stock reservation, deleting an aggregate with its children. Transactions exist since 4.0 (replica set) and 4.2 (sharded cluster) — the claim "MongoDB has no transactions" is outdated. But a well-designed aggregate makes them rare: if a transaction is needed for every other request, that signals a relational schema. See [CRUD and Query Operators] and [Replication, Transactions, and Consistency].

---

**9. How do you fetch "ratings of 4 or more from a specific user"? What is the array gotcha?**

The gotcha is that conditions on an array field via dot notation are evaluated INDEPENDENTLY: `{ "ratings.userId": "b", "ratings.score": { $gte: 4 } }` will match a document where `userId: "b"` belongs to one element and `score: 5` to another — returning something you did not ask for. To make both conditions hold on the SAME element you need `$elemMatch`: `{ ratings: { $elemMatch: { userId: "b", score: { $gte: 4 } } } }`. The same applies to a range on one element: without `$elemMatch`, `{ score: { $gte: 4, $lte: 5 } }` means "some element is ≥ 4 and some element is ≤ 5", possibly different ones. The practical rule: one condition — dot notation; two or more on the same element — always `$elemMatch`. For selecting the elements themselves there are the `$slice`, `comments.$` and `$elemMatch` projections, but if such selections are needed regularly with pagination and sorting, that is a sign the data belongs in its own collection. See [CRUD and Query Operators].

---

**10. `updateOne` vs `replaceOne`, and why does `upsert` not protect against duplicates?**

`updateOne` with operators updates the listed fields and leaves the rest alone. `replaceOne` replaces the whole document except `_id` — the source of a classic bug: `PUT /posts/:id` writing `req.body` through a replace (or through an update with no operators, which drivers treat as a replacement). The client sent `{ title }`, `authorId` and `createdAt` disappeared from the document, and the cause is later looked for in the read path rather than the write path. REST PUT semantics are not `replaceOne`: a `$set` over an explicit allowlist of fields is safer. On upsert: it removes the "find first, then decide" round-trip, but it is not an atomic "check and insert" — two concurrent upserts that find nothing will insert two documents. Only a unique index protects you: with one, the second upsert gets `E11000`, which is an expected outcome handled as "retry once". Another nuance: only the filter's equalities make it into the new document, comparison operators are ignored on insert, and insert-only fields are set with `$setOnInsert`. See [CRUD and Query Operators].

---

**11. How do you implement "claim a job" or "debit without going negative" without a transaction?**

With `findOneAndUpdate` and the condition in the FILTER — an atomic server-side read-modify-write, the equivalent of `SELECT FOR UPDATE` plus an update in one step. Claiming a job: `findOneAndUpdate({ _id, status: "pending" }, { $set: { status: "running", workerId } }, { returnDocument: "after" })` — if the status changed in the meantime no document is found, and `null` *is* the answer "already claimed", not an error. Not going negative: `findOneAndUpdate({ _id, balance: { $gte: amount } }, { $inc: { balance: -amount } })` — the check is performed by the server at write time rather than by the application against a stale copy. The alternative, "read, compute in Node, write back", is the classic lost update: two processes read `views = 100`, both write 101, one increment is lost. The same technique works as optimistic locking: the document version in the filter plus an `$inc` of the version, where `matchedCount === 0` means a conflict. The general principle: move the check out of the code and into the query filter. See [CRUD and Query Operators] and [Mongoose Queries, populate, and Pitfalls].

## Typical follow-ups (group 3)

```txt
"You wrote findOneAndUpdate for a job queue. What if the worker
dies after claiming a job?" → you need a timeout and a return to
pending (a claimedAt field plus a background job), i.e.
idempotency and recovery

"matchedCount 1, modifiedCount 0 — what happened?" → a $set of
the same value; and why "not found" is checked via matchedCount

"How do you tell 'no such document' from 'the condition failed'
when findOneAndUpdate returned null in both cases?" → a separate
findOne for diagnostics, or distinct error codes by business
meaning

"You have 200,000 documents in a result set and toArray(). What is
wrong?" → the whole set in process memory; cursor iteration,
batching, and why skip gets more expensive with the page number
```

## Group 4: indexes and performance

**12. What is the ESR rule and why is the order exactly that?**

ESR is Equality, Sort, Range: the field order in a compound index. Equality first, because exact equality pins a key prefix and narrows the scan to a contiguous stretch of the index. Sort right after the equalities, because within the pinned prefix the keys are already sorted by the next index field: if that matches the `sort`, the server returns documents in order, there is no `SORT` stage in the plan, and `limit` becomes cheap — 20 documents come off the start of the scan instead of after sorting the whole result. Range last, because a range reads a contiguous stretch of keys inside which the order by the next field is no longer a global order — which is why any sort field placed AFTER a range field does not save you from an in-memory sort. A concrete check: for `find({ status, "author._id", publishedAt: { $gte } }).sort({ views: -1 })` the correct index is `{ status: 1, "author._id": 1, views: -1, publishedAt: 1 }`, while the "intuitive" `{ status: 1, publishedAt: 1, views: -1 }` adds a `SORT` with a 100 MB memory limit. Plus, separately, the prefix rule: an index `{a, b, c}` serves `(a)`, `(a,b)`, `(a,b,c)` but not `(b)`. See [Indexes and Query Performance].

---

**13. How do you read `explain()` and which numbers do you look at?**

I run `explain("executionStats")` — unlike the default `queryPlanner` mode it actually executes the query and gives real numbers. I look at four: `nReturned`, `totalKeysExamined`, `totalDocsExamined`, `executionTimeMillis`. A healthy query looks like `nReturned ≈ totalKeysExamined ≈ totalDocsExamined`; any order-of-magnitude gap is work done for nothing. Then the stages: `COLLSCAN` means no index is used; `SORT` means an in-memory sort (so the index does not cover the `sort`); `docsExamined >> nReturned` means the index is not selective enough or the field order is wrong; `totalDocsExamined: 0` with `nReturned > 0` is a covered query, which is the goal. A reading detail: the tree in `winningPlan` is printed root-to-leaf, the reverse of the data flow, so it is easier to start from the deepest stage. And "there is an IXSCAN" is not a conclusion: an index that examines a million keys to return 20 documents is a slow query with an index. I find the slow query with the profiler (`setProfilingLevel(1, { slowms: 100 })`) rather than by guessing. See [Indexes and Query Performance].

---

**14. Name situations where an index exists but is not used.**

ESR is violated — the range field comes before the sort field, and instead of a saving you get a `SORT` over the whole result. `$regex` without a leading anchor or with the `i` flag: `/^mongodb-/` gives a range scan, while `/^mongodb-/i` and `/indexes/` give an index scan or a `COLLSCAN`. `$ne`/`$nin` mean "everything except", selectivity is close to 100%, so even with an index almost all of it is read — reformulate as an `$in` over the allowed values. A computation over the field instead of the field itself: `$expr` with `$year: "$publishedAt"` does not use the index on `publishedAt`, you need a range on the year boundaries; `$where` uses no indexes at all. A BSON type mismatch: `"42"` and `42` are different values, and the classic here is an `id` from the query string versus an `ObjectId` in the database. A collation mismatch. An `$or` where at least one branch lacks an index — the whole `$or` degrades. And low selectivity: `{ archived: false }` when 99% are `false` — the planner will reasonably choose a `COLLSCAN`. See [Indexes and Query Performance].

---

**15. Tell me about multikey, unique and TTL — what are the traps?**

Multikey happens automatically when the indexed field is an array: one index entry is created per ELEMENT, so index size scales with the total number of elements (1M documents with 20 tags is 20M entries). The limitations: a compound index may contain only one array path (otherwise "cannot index parallel arrays"), and a covered query over a multikey field is impossible because the array cannot be reconstructed from separate entries. The `unique` trap that breaks production: a missing field is indexed as `null`, and `null == null`, so TWO documents without an `email` field produce `E11000`. The fix is a partial index with `partialFilterExpression: { email: { $exists: true } }` (`sparse: true` also works, but `partial` is more flexible and is recommended). TTL: deletion is done by a background task waking up once every 60 seconds, so it is not a precise deadline — session expiry is still checked by a condition in the query; the field must be a `Date`, TTL cannot be set on a compound index, and only the primary deletes (secondaries get the change through the oplog). See [Indexes and Query Performance].

## Typical follow-ups (group 4)

```txt
"You now have 12 indexes and writes got slower. How do you decide
what to drop?" → $indexStats and accesses.ops over a long period,
hideIndex before dropIndex, checking prefix duplicates ({a} is
redundant given {a,b})

"We need a substring search on titles. What do you suggest?" → an
unanchored $regex is a scan; a text index (with the immediate
caveat: one per collection, no fuzzy) or Atlas Search

"createIndex on a 300 GB collection in production — how?" → the
hybrid build since 4.2 does not lock for long but does add load;
a rolling build per member, as a separate deploy step, not via
autoIndex

"explain showed an IXSCAN and 2 seconds. What next?" →
keysExamined against nReturned, the presence of a SORT stage,
whether the index fits in cache
```

## Group 5: aggregation

**16. Why is `$lookup` not a free JOIN, and what do you do about it?**

`$lookup` runs as a nested loop: for EVERY document arriving at the stage a lookup is performed against the target collection. There is no hash join, no merge join and no join-order choice by a planner — a fundamental difference from a JOIN in PostgreSQL. Hence: an index on `foreignField` is mandatory, otherwise each of the N lookups scans the target collection in full; the result is always an array, so getting an object needs `$unwind` (and a decision about documents with no match); the `let` + `pipeline` form is a correlated subquery, also executed per input document. In practice: narrow the input BEFORE `$lookup` with `$match`, `$sort`, `$limit`. But the main conclusion is about the schema rather than the aggregation: if `$lookup` sits in the main read path, the schema was designed relationally, and an Extended Reference (`author: { _id, name, avatar }` right inside the post) removes the stage entirely rather than optimizing it. `$lookup` remains a legitimate tool for reports, admin panels and rare queries. See [Aggregation Pipeline] and [Schema Design: Embedding vs Referencing].

---

**17. How do you optimize a pipeline, and where should the computation happen — in the database or in Node?**

The main rule is "filter early": indexes in an aggregation only work on the stages BEFORE the first one that reshapes the stream, so `$match` and `$sort` belong at the front. The optimizer does some of this itself: it moves `$match` through `$project`/`$addFields`, merges `$sort` + `$limit` into a top-k sort, coalesces consecutive `$limit`/`$skip`. But it will not push `$match` through `$group` (a filter on a computed field — the equivalent of `HAVING`, with no index involved) and will not guess that `$lookup` should have run after `$limit`. Remember the limits: blocking stages (`$group`, `$sort` without an index, `$facet`) are capped at 100 MB, and `allowDiskUse` removes the failure but not the slowness — it is a lifeline, not an operating mode; separately, a result document is capped at 16 MB, so `$group` with `$push` over a large collection fails regardless of `allowDiskUse`. Where to compute: in the database when the input volume greatly exceeds the result (2M comments → 10 report rows), when the work reduces to indexes and grouping, when the result is materialized via `$merge`. In Node when the data is already small, when the logic involves external service calls and rules that change with the product, and when it needs test coverage. The guideline: aggregation is good at computing data, the application is good at expressing business rules; a 12-stage pipeline with `$cond`/`$switch` is a program in an awkward language with no debugger. See [Aggregation Pipeline].

## Typical follow-ups (group 5)

```txt
"$unwind over a tags array — what happens to the document count,
and what about posts with no tags?" → cardinality multiplication
and the silent loss of documents without the array
(preserveNullAndEmptyArrays)

"You need the list, the total count and facet counters. How many
queries?" → one $facet, with caveats: indexes only work before
$facet, the stage is blocking, the result is one document (16 MB)

"The report takes 40 seconds every time the dashboard opens" →
$merge into a separate collection on a schedule and read it with
a plain find; and the difference between $merge and $out

"Can this run on a secondary?" → yes, and then the question
becomes read preference and whether stale data is acceptable
```

## Group 6: replication, consistency, transactions, sharding

**18. What does "the write was acknowledged" mean? Walk through write concern and read concern.**

Write concern answers "when does a write count as done". `w: 1` — the primary applied it; `w: "majority"` — a majority of the set applied it; `j: true` — the operation reached the journal on disk; `w: 0` — we do not wait at all. The difference between `w: 1` and `majority` is concrete: a client writes with `w: 1`, the primary acknowledges, the secondaries have not yet received the operation from the oplog, the primary crashes, a member that never saw the operation becomes the new primary, and the returning old member rolls the operation back — so the client got "success" and the data is not in the database. That is why since MongoDB 5.0 the default is `w: "majority"` (on older clusters and in older code it was `w: 1`, which is worth checking). Read concern answers a different question — which data counts as existing: `local` returns the member's fresh data that could theoretically be rolled back, `majority` returns only majority-acknowledged data, `snapshot` is used in transactions. And the third independent knob is read preference, "who do I ask". The real guarantees come from the combination of all three; "consistency" without naming all three is an empty word. Separately: `wtimeout` cancels the wait, not the write, so a blind retry after a `wtimeout` produces duplicates unless the operation is idempotent. See [Replication, Transactions, and Consistency].

---

**19. What is dangerous about reading from a secondary, and how do you get read-your-own-write?**

Reading from a secondary gives eventual consistency: a user saves their profile (a write to the primary) and immediately opens the page (a read from a secondary that has not applied the operation yet) — they see stale data and conclude the save did not work. Replication lag is unpredictable: milliseconds normally, but seconds or minutes during a write spike, a long index build or on a slow disk; all you can bound is member selection via `maxStalenessSeconds`. The third point worth saying out loud: replicas do NOT scale writes — every secondary applies the same operations as the primary, so adding replicas increases only read throughput, and at the cost of stale data; writes are scaled by sharding. Appropriate uses for secondaries are reports, heavy aggregations that should not compete with production traffic, geo-local reads via `nearest`, and backups. And if you need both primary offloading and the "I will see my own write" guarantee, that is a causally consistent session: the driver carries the operation's logical time and the read waits for the member to catch up. So it is solved by a session, not by member selection. See [Replication, Transactions, and Consistency].

---

**20. What does a transaction look like in MongoDB, what does it cost, and where do people get it wrong most often?**

The API is `session.withTransaction(async () => { ... })`, which retries `TransientTransactionError` (write conflict, primary change) and `UnknownTransactionCommitResult` on its own; a `throw` inside the callback means abort. The main mistake is forgetting to pass `{ session }` to an operation inside the block: such an operation runs OUTSIDE the transaction, so half the changes roll back and half stay. The second mistake is a non-idempotent callback: it may be invoked more than once, so "send an email" or "charge an external API" must not live inside it. The cost: snapshot isolation means `WriteConflict` and retries under contention; a 60-second default limit; pending changes occupy the WiredTiger cache until commit; on a sharded cluster it becomes a distributed transaction with a two-phase commit, an order of magnitude more expensive. And most importantly — a transaction does not replace schema design: incrementing a counter is `$inc`, "read-check-write" is `findOneAndUpdate` with the condition in the filter, and updating denormalized copies usually tolerates eventual consistency. See [Replication, Transactions, and Consistency] and [CRUD and Query Operators].

---

**21. How do you choose a shard key and what does a bad choice lead to?**

The key must satisfy three requirements: high cardinality, even write distribution, and presence in most read queries. A compound key like `{ tenantId: 1, _id: 1 }` often covers all three: tenant isolation gives targeted queries and `_id` inside provides cardinality. A bad choice produces four recognizable symptoms. Hot shard: a monotonic key (`ObjectId`, timestamp) with ranged distribution sends the entire insert stream to one shard while the rest idle — cured by `hashed` or a compound key. Jumbo chunks: low cardinality (`country`, `status`) means every document with the same value must live together, the chunk grows beyond the split limit and balancing breaks. Scatter-gather: a filter without the shard key makes `mongos` broadcast to every shard and merge, latency is set by the slowest shard, and adding shards makes such queries worse rather than better. Restrictions: a unique index is only possible on the shard key or its prefix, and a sort without the shard key is performed on `mongos`. The key can be changed (`reshardCollection` since 5.0), but it is a heavy operation. And the honest caveat: sharding answers a volume problem, not a slow-query problem — a slow query on a sharded cluster becomes slow on N shards. See [Replication, Transactions, and Consistency] and [Indexes and Query Performance].

## Typical follow-ups (group 6)

```txt
"How many members in a replica set and why an odd number?" →
majority for elections; in a 2-member set losing either one stops
writes; what an arbiter is for and why it hurts majority writes

"What does the driver do during an election?" → retryable writes
are on by default and a single write is retried; hence the
idempotency requirement on application operations

"A transaction has been running for 3 minutes. What happens?" →
the server aborts it (transactionLifetimeLimitSeconds), and until
then it holds a snapshot and cache

"You have a multi-tenant SaaS. How do you shard?" → tenantId in
front of a compound key; what to do about a very large tenant
(a jumbo chunk) and how to detect it
```

## Group 7: Mongoose

**22. What does Mongoose add to the driver and at what cost?**

Mongoose is a layer over the official driver that brings back into the code what MongoDB does not require: a schema as the single source of truth about document shape, type casting, validation, middleware, virtuals/methods/statics, populate and a chainable query builder. The cost has three parts. First, hydration: a query result is not a database document but a `Document` wrapper with getters, change tracking and validation, which costs memory and CPU per object (cured by `lean()`). Second, hidden magic: some mechanisms do not run where you expect, and that is not a detail but a source of real bugs (validation and `pre('save')` on update operations). Third, one more layer while debugging: between your call and the server query there is a transformation you must be able to inspect (`mongoose.set('debug', true)`). Where Mongoose is not needed: migration scripts, heavy aggregations, thin services with a handful of queries — there the raw driver is more honest. And the key thing to say: Mongoose does not remove the need to understand the document model, indexes and atomicity — a bad schema stays bad. See [Mongoose: Schemas, Models, and Validation].

---

**23. A `pre('save')` hook hashes the password, but the database ended up with a plaintext password. What happened?**

The password was changed through `findOneAndUpdate` (or `updateOne`), and `pre('save')` is document middleware. It is tied to the DOCUMENT lifecycle: load → modify → save. `findOneAndUpdate`, `updateOne`, `updateMany` and `bulkWrite` never load the document — they send the server a description of the changes, so there is no document whose `save()` could be intercepted. The second half of the problem has exactly the same nature: schema validation does not run on update operations by default, it needs `runValidators: true`, and even then `required` is not checked for fields absent from the update, while `this` inside a custom validator is the `Query`, not the document. Three fixes: (1) the whole domain writes through `doc.save()` — then hooks and validation always run, at the cost of an extra read and the loss of atomic read-modify-write; (2) duplicate the hook on `pre('findOneAndUpdate')`, working with `this.getUpdate()` and `this.set()` — works for both paths, but the logic is duplicated and `bulkWrite` remains a third path; (3) take hashing out of the schema and do it in the service — the single place where a password changes. The third option is often the most honest: less magic, and the behaviour is visible in the code. See [Mongoose: Schemas, Models, and Validation] and [CRUD and Query Operators].

---

**24. `populate` vs `$lookup` vs redesigning the schema. And what is `lean()` for?**

`populate` is not `$lookup` but EXTRA queries whose results Mongoose stitches together in Node process memory. An important correction to the common meme: a basic populate over a list of 20 documents is ONE extra query via `$in`, not 21. Genuine N+1 effects appear in specific cases: a nested populate (one query per level), populate inside a loop over documents, `perDocumentLimit` (a query per parent document), and GraphQL resolvers without batching. Two traps that catch almost everyone: `options: { limit: 3 }` is a total limit on the whole `$in` query, not "3 per document" (the first parent gets three, the rest get none); and `match` filters the related documents but does not remove the parent — it comes back with `null`. The choice: populate fits admin panels and rare screens, `$lookup` fits reports and aggregations, and if the related data is needed in your MOST frequent query, the right answer is to redesign the schema (Extended Reference), because then there are no extra round-trips at all. `lean()` is about something else: it returns a plain object instead of a `Document`, skipping hydration — on lists that is a multiple-fold difference in CPU and memory. The rule: any read-only path uses `lean()`, "modify and save" does not. See [Mongoose Queries, populate, and Pitfalls] and [Aggregation Pipeline].

---

**25. What has to be done to a Mongoose application before production?**

Four things. First, disable `autoIndex`: by default Mongoose creates every schema index at startup, which means building indexes at deploy time, N concurrent attempts across N instances and implicit changes without review; indexes should be applied by a migration step in the pipeline, and `syncIndexes()` used deliberately, remembering that it DROPS indexes that are not in the schema (`diffIndexes()` for an audit). From that follows the second, less obvious point: `unique: true` in a schema is an index declaration, not a validator, so with `autoIndex: false` and no migration there is no uniqueness at all even though the code looks like there is. Third, understand command buffering: before the connection is established Mongoose does not throw but buffers operations up to `bufferTimeoutMS` (10 seconds), which in production looks like "the request hangs for 10 seconds" while the real cause is an unreachable cluster or an IP missing from the allowlist; cure it with a healthcheck on `readyState`, refusing traffic until connected and, in critical services, `bufferCommands: false`. Fourth, error mapping: `E11000` is a 409 (and it comes from the driver, so check `e.code` rather than `instanceof mongoose.Error`), `ValidationError` and `CastError` are 400s, an unreachable cluster is a 503; without this everything becomes a 500 and a useless alert, and the driver's `e.message` additionally leaks the key value into the API response. See [Mongoose Queries, populate, and Pitfalls].

## Typical follow-ups (group 7)

```txt
"Why use Mongoose at all if the driver exists?" → the schema in
code and validation as the value; plus an honest answer about
where it gets in the way (aggregations, migrations, needless
hydration)

"How do you type lean() results and hydrated documents?" → they
are TWO different types; HydratedDocument vs a POJO, _id as
Types.ObjectId vs a string in the DTO

"We use Next.js; hot reload throws OverwriteModelError and the
connection count keeps growing" → mongoose.models.X ?? model(...)
plus a cached connection in globalThis with a small maxPoolSize

"Doesn't __v give you optimistic locking?" → no: __v is not
incremented on every save(), and a plain field overwrite raises no
conflict; you need optimisticConcurrency: true or your own version
field in the filter
```

## What to say when the question is unfamiliar

```txt
Three moves that work better than silence:

1. Reduce it to the base guarantees. Almost any MongoDB
   consistency question decomposes into: single-document
   atomicity + write concern + read concern/preference. Name
   those three knobs and reason from them.

2. Reduce it to the access pattern. Any schema question is
   "which queries, at what rate, with what growth bounds".
   Start with the list of queries, not the entities.

3. Name the cost. "We can do it this way, and it will cost this
   much" is a stronger answer than "this is how it's done". The
   willingness to state a trade-off is what separates a senior
   from someone who memorized recipes.
```
