# MongoDB + Mongoose: Interview Questions (Middle → Senior)

## How to use this cheat sheet

Every answer below is a condensed version of what the articles in this topic cover in detail. In an interview almost none of these questions is the final one. Each is a lead-in to a follow-up: "why?", "what if the data grows 100 times?", "show me on our domain".

That is why each group ends with a **"Typical follow-ups"** section showing where the interviewer usually goes next. If a follow-up catches you off guard, that is a signal to go back to the matching article.

A note on delivery. MongoDB questions attract slogans more than most: "Mongo is faster", "there is no schema", "populate is N+1". `N+1` means one query for a list of N items plus one more query per item — N+1 database round-trips where two would do. A strong answer always contains mechanics and a limit of applicability, not a verdict.

## Group 1: the document model and choosing a database

**1. How does BSON differ from JSON, and what does the ObjectId layout give you?**

BSON (binary JSON) is a binary typed format: every field carries an explicit type and length. Two things follow. The engine can skip a field without fully parsing it, and types survive a round-trip unchanged.

JSON has no `Date`, `ObjectId`, `Decimal128` or `Int32/Int64`. That has two practical consequences you should name:

- Money is stored as `Decimal128` or as integer cents. A `Double` accumulates the same rounding error as `Float` in SQL (structured query language).
- A date is stored as a BSON `Date`, never as a string. Otherwise range queries compare the values lexicographically, so `"2026-1-9"` sorts before `"2026-10-01"`.

```js
db.orders.insertOne({
  total: NumberDecimal("19.99"),   // not 19.99 — no binary rounding
  createdAt: new Date(),           // not "2026-08-13" — a real Date
});
```

An `ObjectId` is 12 bytes, and the first 4 hold unix time in seconds:

```txt
ObjectId("66b0f2c1a4e3f21c8d9b1234")  — 12 bytes, 24 hex chars

  66b0f2c1    4 bytes   unix time in seconds
  a4e3f21c8d  5 bytes   random, per process
  9b1234      3 bytes   counter, per process
```

That layout buys you three things for free. Sorting by `_id` nearly matches sorting by creation time. The date can be read out of the value with `getTimestamp()`. And keyset pagination "newest first" runs on the `_id` index, which always exists.

The flip side: an `ObjectId` is predictable and it exposes the creation time. For public URLs where that matters you need a separate unpredictable field.

At the API boundary BSON is serialized to Extended JSON, and `_id` becomes a string. The reverse mapping, "string → ObjectId", is where input validation is mandatory. The document model article covers this in full.

---

**2. MongoDB is called schemaless. What does that actually mean?**

It means the schema is not enforced by the database, not that there is none. A collection accepts a document of any shape, and there is no DDL (data definition language) — no `CREATE TABLE`, no `ALTER TABLE`.

But the data shape still exists. It has simply moved from the database into the application code.

That is a transfer of responsibility, and it has a price:

- Every read must tolerate documents in an older shape.
- A "migration" becomes a lazy upgrade on read, or a batch script.
- Analytics trips over heterogeneous documents.
- A new developer learns the shape from the code, not from `\d posts`.

What you get in return:

- Adding a field is a code deploy, with no migration and no locks.
- Heterogeneous entities live in one collection, without 40 nullable columns and without EAV (entity-attribute-value). EAV is the relational trick of storing "field name / field value" rows to fake a flexible schema.

Some of the discipline can be pushed back into the database with a `$jsonSchema` validator. Importantly, it also catches writes made outside the application — from the shell, from a script.

```js
db.createCollection("posts", {
  validator: { $jsonSchema: {
    bsonType: "object",
    required: ["title", "status"],
    properties: { status: { enum: ["draft", "published"] } },
  } },
  validationLevel: "moderate",   // existing bad documents are not rejected
});
```

Node projects usually keep the schema in Mongoose instead, remembering that this is an application-side check only. The document model article and the Mongoose schemas article go into both.

---

**3. Why did you choose MongoDB over PostgreSQL?**

The answer runs along four axes and ends with a limit of applicability.

1. **Data shape and access pattern.** "The main query is the whole order card. It is read and written as one aggregate, so it lives as one document instead of a four-table join."
2. **Consistency requirements.** "All order invariants are inside one document, so single-document atomicity is enough. If stock decrement and order creation had to be atomic together, that would be an argument for a relational database."
3. **Scale and workload profile.** How much we write, how we read, whether we are ready to shard.
4. **Operational context.** What the team already knows how to run.

Then the closing part that marks a senior: "if billing with multi-entity transactions or ad-hoc analytics appears, that part moves to PostgreSQL."

Separately, raise the honest caveat before you are asked. In PostgreSQL, `jsonb` covers a large share of "we need a flexible schema", and it has full transactions right next to it. So "we can store JSON in Mongo" does not by itself justify the choice.

The document model article and the PostgreSQL topic both cover this comparison.

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

Four criteria, and the order matters.

1. **Cardinality, in terms of "how many can there ever be"** — not "how many now". One-to-few (3–10 tags) gets embedded. One-to-many (comments) moves out with a reference. One-to-squillions (page views) lives separately with bucketing.
2. **Access pattern.** If the child data is always needed when the parent is read, embed it. If it needs independent access ("all comments by a user", moderation), its own pagination and its own sorting, give it a collection.
3. **Change frequency.** Duplicate what rarely changes and is almost always read: an author's name and avatar. Never duplicate what changes often or is critical: email, roles.
4. **Growth bounds.** Can a user grow this set of elements without any limit? If yes, embedding is a deferred incident.

```txt
how many children      what to do
─────────────────────  ────────────────────────────────────
one-to-few  (3-10)     embed as an array
one-to-many (100s)     own collection + a reference
one-to-squillions      own collection + bucketing
unbounded by a user    own collection, no exceptions
```

And the starting point is not the entities. It is a list of the top five queries with their rates. Without that, any answer about embedding is guesswork. The rule everything reduces to: what is read together is stored together. That is the whole subject of the schema design article.

---

**5. A concrete case: comments on a post — embed or reference?**

A reference plus a Subset — and the reasoning matters more than the answer. Comments have no upper bound. 99% of posts will have 20 of them, but one viral post will have 50,000, and the schema has to survive exactly that one.

Full embedding hits the 16 MB (megabyte) document limit, but it breaks long before it, for three reasons:

1. `WiredTiger`, the MongoDB storage engine, does not patch a document in place. Every `$push` rewrites the whole document.
2. The whole document is read into memory and sent over the network, even when you need one comment.
3. An index on an array is a multikey index: one index entry per array element. The index grows together with the document.

So comments live in their own collection with a `postId` reference, which needs an index. That gives proper pagination, sorting and independent moderation.

At the same time the post page shows the first three comments on 95% of views. Those are kept in the post itself, as a fixed-length array:

```js
await posts.updateOne({ _id: postId }, {
  $push: {
    previewComments: {
      $each: [{ author, body, createdAt: new Date() }],
      $sort: { createdAt: -1 },
      $slice: 3,                 // keep only the newest three
    },
  },
});
```

The cost: there are now two writes and they are not atomic. So insert into `comments` first, because that is the source of truth, and update the preview second. That way a failure loses a cache, not data. The schema design article goes deeper, and so does the article on CRUD (create, read, update, delete).

---

**6. Which design patterns do you use and what do they cost?**

Four patterns, and for each one name the price as well as the benefit.

**Extended Reference.** The post stores not `authorId` but `author: { _id, name, avatar }` — exactly the fields that get rendered. It removes the second query on every page and every feed item. The cost: duplicates must be updated. You must say by which mechanism — a background job, change streams — or say that it is a deliberate snapshot of "the name as of publication".

**Subset.** The hot slice lives inside the document, with a mandatory `$slice`. Without the `$slice` the pattern becomes an anti-pattern, because the array grows without a bound.

**Bucket.** A document per bucket (`postId` plus the hour) rather than per event, written with `upsert` and `$inc`:

```js
await views.updateOne(
  { postId, hour: "2026-08-13T14" },
  { $inc: { count: 1 } },
  { upsert: true },              // needs a unique index on { postId, hour }
);
```

Millions of tiny documents become 24 per post per day, and a weekly report reads 168 documents instead of 70 million. A unique index on the bucket key is mandatory: otherwise an upsert race creates two buckets for the same hour.

**Computed.** The comment counter is stored ready and changed with an atomic `$inc`, instead of `countDocuments()` on every feed read. The mandatory companion is a background recompute from the source of truth, because the counter will drift eventually.

---

**7. What is wrong with a fully normalized schema in MongoDB — and what is the danger of the opposite, massive denormalization?**

Full normalization in Mongo gives you the worst of both worlds. Three things go wrong at once:

- Joins nominally exist, but `$lookup` runs as a sub-query per input document. There is no hash join and no join-order choice by a planner, and `populate` in Mongoose is separate queries entirely.
- Integrity is still absent: no FK, no `ON DELETE CASCADE`, no cross-collection checks. An FK is a foreign key — the relational constraint that blocks a reference to a row that does not exist.
- Transactions become necessary at every step, and they cost more than in a relational database.

So you end up with a relational schema without relational guarantees and without a relational optimizer. If the data genuinely requires normalization along every axis, the right conclusion is to use PostgreSQL.

The opposite extreme is copying the full author document into every post and every comment. Then an email change becomes an `updateMany` over millions of documents with no transaction around it. A mid-way failure leaves the system in two states. And a deletion request under the General Data Protection Regulation (GDPR) becomes a search for copies across every collection.

The question an interviewer asks is always the same. Who updates the duplicates, and when? And what happens on a mid-way failure? A good answer names a concrete mechanism, or honestly says "it is a snapshot, we never update it". The schema design and aggregation articles both extend this.

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

Any write operation on a **single** document is atomic: either all of its changes apply, or none of them do. That holds for several fields, nested objects and array elements at once.

```js
// No reader ever sees this half-applied
await posts.updateOne({ _id: postId }, {
  $push: { previewComments: comment },
  $inc:  { "stats.comments": 1 },
  $set:  { updatedAt: new Date() },
});
```

State the boundaries precisely, because that is what the follow-up probes:

- `updateMany` over 100 documents is 100 separate atomic operations. In between you can observe half of them updated.
- Two operations in a row in application code are not atomic either, even on the same document.

A transaction is needed when the invariant spans several documents and divergence is unacceptable. Three examples: a transfer between accounts, an order plus a stock reservation, deleting an aggregate together with its children.

Transactions exist since 4.0 for replica sets and 4.2 for sharded clusters, so the claim "MongoDB has no transactions" is outdated. But a well-designed aggregate makes them rare. If a transaction is needed for every other request, that signals a relational schema. The CRUD article and the replication article both take this further.

---

**9. How do you fetch "ratings of 4 or more from a specific user"? What is the array gotcha?**

The gotcha is that conditions on an array field written with dot notation are evaluated **independently** of each other.

```js
// WRONG: userId "b" may be in one element and score 5 in another
await reviews.find({ "ratings.userId": "b", "ratings.score": { $gte: 4 } });

// RIGHT: both conditions must hold on the SAME element
await reviews.find({
  ratings: { $elemMatch: { userId: "b", score: { $gte: 4 } } },
});
```

The same applies to a range on one element. Without `$elemMatch`, `{ score: { $gte: 4, $lte: 5 } }` means "some element is at least 4 and some element is at most 5" — possibly different elements.

The practical rule is short. One condition on an array field: dot notation is fine. Two or more conditions that must meet on the same element: always `$elemMatch`.

For selecting the elements themselves there are the `$slice`, `comments.$` and `$elemMatch` projections. But if such selections are needed regularly, with pagination and sorting, that is a sign the data belongs in its own collection. The CRUD and query operators article covers both sides.

---

**10. `updateOne` vs `replaceOne`, and why does `upsert` not protect against duplicates?**

`updateOne` with operators updates the listed fields and leaves the rest alone. `replaceOne` replaces the whole document except `_id`. That is the source of a classic bug:

```js
// The classic PUT bug: the client sent { title } only
await posts.replaceOne({ _id: id }, req.body);
// → authorId and createdAt are now GONE from the document

// Safer: $set over an explicit allowlist of fields
const allowed = pick(req.body, ["title", "body", "tags"]);
await posts.updateOne({ _id: id }, { $set: allowed });
```

An update with no operators is treated as a replacement by the drivers too, so the same bug hides there. And `REST` (representational state transfer — the usual style of HTTP APIs) `PUT` semantics are not `replaceOne`. When `authorId` and `createdAt` disappear, the cause is then looked for in the read path rather than the write path.

On `upsert`: it removes the "find first, then decide" round-trip, but it is **not** an atomic "check and insert". Two concurrent upserts that both find nothing will insert two documents. Only a unique index protects you: with one in place, the second upsert gets `E11000`, which is an expected outcome you handle as "retry once".

Another nuance about the inserted document. Only the filter's equalities make it in, and comparison operators are ignored on insert. Insert-only fields are set with `$setOnInsert`.

---

**11. How do you implement "claim a job" or "debit without going negative" without a transaction?**

With `findOneAndUpdate` and the condition in the **filter**. That is an atomic server-side read-modify-write: the equivalent of `SELECT FOR UPDATE` plus an update, in one step.

```js
// Claim a job. null means "already claimed" — that is the answer,
// not an error.
const job = await jobs.findOneAndUpdate(
  { _id, status: "pending" },
  { $set: { status: "running", workerId } },
  { returnDocument: "after" },
);

// Debit without going negative: the server checks at write time.
const acc = await accounts.findOneAndUpdate(
  { _id, balance: { $gte: amount } },
  { $inc: { balance: -amount } },
);
```

The alternative, "read, compute in Node, write back", is the classic lost update. Two processes read `views = 100`, both write 101, and one increment is gone.

The same technique works as optimistic locking: put the document version in the filter and `$inc` the version in the update. Then `matchedCount === 0` means a conflict.

The general principle is one sentence: move the check out of the application code and into the query filter. The CRUD article and the Mongoose queries article both build on it.

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

ESR stands for Equality, Sort, Range, and it is the rule for field order in a compound index.

- **Equality first.** Exact equality pins a key prefix and narrows the scan to a contiguous stretch of the index.
- **Sort right after the equalities.** Within the pinned prefix the keys are already sorted by the next index field. If that field matches the `sort`, the server returns documents in order and there is no `SORT` stage in the plan. And `limit` becomes cheap: 20 documents come off the start of the scan, instead of after sorting the whole result.
- **Range last.** A range reads a contiguous stretch of keys, and inside that stretch the order by the next field is no longer a global order. This is why any sort field placed **after** a range field does not save you from an in-memory sort.

```js
// The query
db.posts.find({ status, "author._id": a, publishedAt: { $gte: d } })
        .sort({ views: -1 });

// Correct — E, then S, then R
{ status: 1, "author._id": 1, views: -1, publishedAt: 1 }

// "Intuitive" and wrong — the range sits before the sort field,
// so the plan gains a SORT stage with a 100 MB memory limit
{ status: 1, publishedAt: 1, views: -1 }
```

Plus, separately, the prefix rule: an index `{a, b, c}` serves `(a)`, `(a,b)` and `(a,b,c)`, but not `(b)`. The indexes article works through both rules.

---

**13. How do you read `explain()` and which numbers do you look at?**

I run `explain("executionStats")`. Unlike the default `queryPlanner` mode it actually executes the query and gives real numbers, not estimates. Then I look at four of them:

```txt
nReturned            documents returned
totalKeysExamined    index entries read
totalDocsExamined    documents fetched from storage
executionTimeMillis  wall-clock time
```

A healthy query looks like `nReturned ≈ totalKeysExamined ≈ totalDocsExamined`. Any gap of an order of magnitude is work done for nothing.

Then the stages, and each one has a fixed meaning:

- `COLLSCAN` — collection scan: no index was used, the whole collection was read.
- `SORT` — an in-memory sort, which means the index does not cover the `sort`.
- `docsExamined` far above `nReturned` — the index is not selective enough, or the field order is wrong.
- `totalDocsExamined: 0` with `nReturned > 0` — a covered query, answered from the index alone. That is the goal.

A reading detail: the tree in `winningPlan` is printed root-to-leaf. That is the reverse of the data flow, so it is easier to start from the deepest stage.

And "there is an `IXSCAN`" is not a conclusion. `IXSCAN` is an index scan, and an index that examines a million keys to return 20 documents is still a slow query. I find the slow query with the profiler, `setProfilingLevel(1, { slowms: 100 })`, rather than by guessing.

---

**14. Name situations where an index exists but is not used.**

Eight of them, and they come up in this order in practice:

- **ESR is violated.** The range field comes before the sort field, so instead of a saving you get a `SORT` over the whole result.
- **`$regex` without a leading anchor, or with the `i` flag.** `/^mongodb-/` gives a range scan; `/^mongodb-/i` and `/indexes/` do not.
- **`$ne` and `$nin`.** They mean "everything except", so selectivity is close to 100% and almost the whole index is read anyway. Reformulate as an `$in` over the allowed values.
- **A computation over the field instead of the field itself.** `$expr` with `$year: "$publishedAt"` does not use the index on `publishedAt`. You need a range on the year boundaries instead. And `$where` uses no indexes at all.
- **A BSON type mismatch.** `"42"` and `42` are different values. The classic case is an `id` arriving as a string in the query string while the database holds an `ObjectId`.
- **A collation mismatch** between the index and the query.
- **An `$or` where at least one branch lacks an index.** The whole `$or` degrades, not just that branch.
- **Low selectivity.** With `{ archived: false }` where 99% of documents are `false`, the planner will reasonably choose a `COLLSCAN`.

---

**15. Tell me about multikey, unique and TTL — what are the traps?**

Three index kinds with three different traps.

**Multikey** happens automatically when the indexed field is an array: one index entry is created per **element**. So index size scales with the total number of elements. One million documents with 20 tags each is 20 million entries.

Two limitations follow. A compound index may contain only one array path, otherwise you get "cannot index parallel arrays". And a covered query over a multikey field is impossible, because the array cannot be reconstructed from separate entries.

**Unique** has the trap that breaks production: a missing field is indexed as `null`, and `null == null`. So **two** documents with no `email` field at all produce `E11000`.

```js
// The fix: index only the documents that have the field
db.users.createIndex(
  { email: 1 },
  { unique: true, partialFilterExpression: { email: { $exists: true } } },
);
// sparse: true also works, but partial is more flexible and recommended
```

**TTL** stands for time-to-live: the server deletes a document once its date field is older than the configured age. Four things to know.

Deletion is done by a background task that wakes up once every 60 seconds, so this is not a precise deadline. Session expiry is still checked by a condition in the query. The field must be a `Date`, and TTL cannot be set on a compound index. And only the primary deletes; secondaries get the change through the oplog, the log of applied writes.

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
a rolling build member by member, as a separate deploy step, not
via autoIndex

"explain showed an IXSCAN and 2 seconds. What next?" →
keysExamined against nReturned, the presence of a SORT stage,
whether the index fits in cache
```

## Group 5: aggregation

**16. Why is `$lookup` not a free join, and what do you do about it?**

`$lookup` runs as a nested loop: for **every** document arriving at the stage, a lookup is performed against the target collection. There is no hash join, no merge join and no join-order choice by a planner. That is a fundamental difference from a `JOIN` in PostgreSQL.

Three consequences follow directly:

- An index on `foreignField` is mandatory. Without it, each of the N lookups scans the target collection in full.
- The result is always an array, so getting an object needs `$unwind` — plus a decision about documents with no match.
- The `let` plus `pipeline` form is a correlated sub-query, also executed once per input document.

```js
db.posts.aggregate([
  { $match: { status: "published" } },   // narrow the input FIRST
  { $sort:  { publishedAt: -1 } },
  { $limit: 20 },
  { $lookup: { from: "users", localField: "author._id",
               foreignField: "_id", as: "author" } },
  { $unwind: "$author" },
]);
```

But the main conclusion is about the schema, not the aggregation. If `$lookup` sits in the main read path, the schema was designed relationally. An Extended Reference removes the stage entirely rather than optimizing it: `author: { _id, name, avatar }` right inside the post. The stage stays a legitimate tool for reports, admin panels and rare queries. The aggregation and schema design articles cover both halves.

---

**17. How do you optimize a pipeline, and where should the computation happen — in the database or in Node?**

The main rule is "filter early". Indexes in an aggregation only work on the stages **before** the first one that reshapes the stream, so `$match` and `$sort` belong at the front.

The optimizer does some of this itself:

- It moves `$match` through `$project` and `$addFields`.
- It merges `$sort` plus `$limit` into a top-k sort.
- It coalesces consecutive `$limit` and `$skip` stages.

But there are two things it will not do. It will not push `$match` through `$group`, because that is a filter on a computed field — the equivalent of `HAVING`, with no index involved. And it will not guess that a `$lookup` should have run after the `$limit`.

Then remember the limits:

- Blocking stages (`$group`, `$sort` without an index, `$facet`) are capped at 100 MB. `allowDiskUse` removes the failure but not the slowness. Use it to survive a spike, not as a normal operating mode.
- A result document is capped at 16 MB. So `$group` with `$push` over a large collection fails regardless of `allowDiskUse`.

Where to compute — in the database when:

- the input volume greatly exceeds the result (2M comments produce 10 report rows);
- the work reduces to indexes and grouping;
- the result is materialized via `$merge`.

In Node when:

- the data is already small;
- the logic involves calls to external services, and rules that change with the product;
- it needs test coverage.

The guideline: aggregation is good at computing data, the application is good at expressing business rules. A 12-stage pipeline full of `$cond` and `$switch` is a program written in an awkward language with no debugger.

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

Write concern answers one question: when does a write count as done. There are four settings worth naming.

```txt
w: 1            the primary applied it
w: "majority"   a majority of the set applied it
j: true         the operation reached the journal on disk
w: 0            we do not wait for anything at all
```

The difference between `w: 1` and `majority` is concrete. Walk the failure through:

1. A client writes with `w: 1`. The primary applies it and acknowledges.
2. The secondaries have not yet copied the operation from the oplog — the log of applied writes that secondaries replay.
3. The primary crashes.
4. An election picks a new primary from the members that never saw the operation.
5. The old member comes back, finds an operation the new primary has no record of, and rolls it back.

Result: the client got "success" and the data is not in the database. That is why since MongoDB 5.0 the default is `w: "majority"`. On older clusters and in older code it was `w: 1`, which is worth checking.

Read concern answers a different question — which data counts as existing:

- `local` returns the member's fresh data, which could theoretically be rolled back.
- `majority` returns only majority-acknowledged data.
- `snapshot` is used inside transactions.

And the third independent setting is read preference: who do I ask. The real guarantees come from the combination of all three, and "consistency" without naming all three is an empty word.

Separately: `wtimeout` cancels the wait, not the write. So a blind retry after a `wtimeout` produces duplicates unless the operation is idempotent. The replication article has the full matrix.

---

**19. What is dangerous about reading from a secondary, and how do you get read-your-own-write?**

Reading from a secondary gives you eventual consistency, which means the copy catches up a moment later. There are three separate problems.

1. **Read-your-own-write breaks.** A user saves their profile, which is a write to the primary. They immediately open the page, which reads from a secondary that has not applied the operation yet. They see stale data and conclude the save did not work.
2. **Replication lag is unpredictable.** Milliseconds normally, but seconds or minutes during a write spike, a long index build or on a slow disk. All you can bound is member selection, with `maxStalenessSeconds`.
3. **Replicas do not scale writes.** Every secondary applies the same operations as the primary, so adding replicas increases read throughput only, and at the cost of stale data. Writes are scaled by sharding.

Appropriate uses for secondaries: reports, heavy aggregations that should not compete with production traffic, geo-local reads via `nearest`, and backups.

And if you need both primary offloading and the "I will see my own write" guarantee, that is a causally consistent session. The driver carries the logical time of the operation, and the read waits for the member to catch up. So it is solved by a session, not by member selection.

---

**20. What does a transaction look like in MongoDB, what does it cost, and where do people get it wrong most often?**

The API is `session.withTransaction(async () => { ... })`. It retries `TransientTransactionError` (a write conflict, a primary change) and `UnknownTransactionCommitResult` on its own, and a `throw` inside the callback means abort.

```js
await session.withTransaction(async () => {
  // Every operation MUST receive { session }
  await posts.updateOne({ _id }, { $inc: { "stats.comments": 1 } },
                        { session });
  await comments.insertOne({ postId: _id, body }, { session });
});
```

Two mistakes account for most of the damage:

1. **Forgetting `{ session }`** on an operation inside the block. Such an operation runs **outside** the transaction, so half the changes roll back and half stay.
2. **A non-idempotent callback.** It may be invoked more than once, so "send an email" or "charge an external API" must not live inside it.

The cost has four parts. Snapshot isolation means `WriteConflict` and retries under contention. There is a 60-second default time limit. Pending changes occupy the WiredTiger cache until commit. And on a sharded cluster it becomes a distributed transaction with a two-phase commit, an order of magnitude more expensive.

And most importantly: a transaction does not replace schema design. Incrementing a counter is `$inc`. "Read, check, write" is `findOneAndUpdate` with the condition in the filter. Updating denormalized copies usually tolerates eventual consistency.

---

**21. How do you choose a shard key and what does a bad choice lead to?**

The key must satisfy three requirements: high cardinality, even write distribution, and presence in most read queries. A compound key like `{ tenantId: 1, _id: 1 }` often covers all three — tenant isolation gives targeted queries, and `_id` inside provides cardinality.

A bad choice produces four recognizable symptoms:

- **Hot shard.** A monotonic key (`ObjectId`, a timestamp) with ranged distribution sends the entire insert stream to one shard while the rest idle. Cured by `hashed` or by a compound key.
- **Jumbo chunks.** Low cardinality (`country`, `status`) means every document with the same value must live together, so the chunk grows beyond the split limit and balancing breaks.
- **Scatter-gather.** A filter without the shard key makes `mongos` broadcast to every shard and merge the results. Latency is set by the slowest shard, and adding shards makes such queries worse rather than better.
- **Restrictions.** A unique index is only possible on the shard key or its prefix, and a sort without the shard key is performed on `mongos`.

The key can be changed — `reshardCollection` arrived in 5.0 — but it is a heavy operation.

And the honest caveat: sharding answers a volume problem, not a slow-query problem. A slow query on a sharded cluster becomes slow on N shards. The replication article and the indexes article are the two to reread here.

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

Mongoose is a layer over the official driver. It brings back into the code what MongoDB does not require:

- a schema as the single source of truth about document shape;
- type casting and validation;
- middleware, virtuals, methods and statics;
- `populate` and a chainable query builder.

The cost has three parts:

1. **Hydration.** A query result is not a database document but a `Document` wrapper with getters, change tracking and validation. That costs memory and processor time per object, and `lean()` is the cure.
2. **Hidden magic.** Some mechanisms do not run where you expect. That is not a detail but a source of real bugs — validation and `pre('save')` on update operations, which is the next question.
3. **One more layer while debugging.** Between your call and the server query there is a transformation you must be able to inspect, with `mongoose.set('debug', true)`.

Where Mongoose is not needed: migration scripts, heavy aggregations, thin services with a handful of queries. There the raw driver is more honest.

And the key thing to say out loud: Mongoose does not remove the need to understand the document model, indexes and atomicity. A bad schema stays bad. It is often called an ORM (object-relational mapper), and the label fits only loosely, because MongoDB is not relational.

---

**23. A `pre('save')` hook hashes the password, but the database ended up with a plaintext password. What happened?**

The password was changed through `findOneAndUpdate` or `updateOne`, and `pre('save')` is document middleware. It is tied to the **document** lifecycle: load, modify, save.

```js
// The schema hashes in pre('save')
userSchema.pre('save', async function () { /* bcrypt.hash */ });

// But the password-change code went around it
await UserModel.findOneAndUpdate(
  { _id: userId },
  { $set: { passwordHash: newPassword } },   // ← a plaintext password
);
// pre('save') is never called: no document was ever loaded
```

`findOneAndUpdate`, `updateOne`, `updateMany` and `bulkWrite` never load the document. They send the server a description of the changes, so there is no document whose `save()` could be intercepted.

The second half of the problem has exactly the same nature. Schema validation does not run on update operations by default: it needs `runValidators: true`. Even then `required` is not checked for fields absent from the update, and `this` inside a custom validator is the `Query`, not the document.

Three fixes, in order of increasing honesty:

1. **The whole domain writes through `doc.save()`.** Hooks and validation then always run. The cost is an extra read and the loss of atomic read-modify-write.
2. **Duplicate the hook on `pre('findOneAndUpdate')`,** working with `this.getUpdate()` and `this.set()`. Works for both paths, but the logic is duplicated and `bulkWrite` remains a third path.
3. **Take hashing out of the schema** and do it in the service — the single place where a password changes. Often the most honest option: less magic, and the behaviour is visible in the code.

---

**24. `populate` vs `$lookup` vs redesigning the schema. And what is `lean()` for?**

`populate` is not `$lookup` but **extra queries**, whose results Mongoose stitches together in the Node process memory. An important correction to the common meme: a basic populate over a list of 20 documents is **one** extra query via `$in`, not 21.

Genuine N+1 effects appear in four specific cases:

- a nested populate — one query per nesting level;
- populate inside a loop over documents;
- `perDocumentLimit` — one query per parent document;
- GraphQL resolvers without batching.

Two traps catch almost everyone. The first: `options: { limit: 3 }` is a total limit on the whole `$in` query, not "3 per document". The first parent gets three, the rest get none. The second: `match` filters the related documents but does not remove the parent. The parent comes back with `null` in that field.

```txt
             Three ways to get related data
┌──────────────────────────────────────────────────────┐
│ populate                                             │
│                                                      │
│ where it runs       Node + N queries                 │
│ round-trips         2 or more                        │
│ filter on related   match, parent still returned     │
│ when it fits        admin panels, rare screens       │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│ $lookup                                              │
│                                                      │
│ where it runs       on the server                    │
│ round-trips         1                                │
│ filter on related   fully, inside the pipeline       │
│ when it fits        reports and aggregations         │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│ redesign the schema                                  │
│                                                      │
│ where it runs       nowhere: already in the document │
│ round-trips         1                                │
│ filter on related   a plain find                     │
│ when it fits        the hot read path                │
└──────────────────────────────────────────────────────┘
```

So if the related data is needed in your **most** frequent query, the right answer is to redesign the schema with an Extended Reference. Then there are no extra round-trips at all.

`lean()` is about something else. It returns a plain object instead of a `Document`, skipping hydration, and on lists that is a several-fold difference in processor time and memory. The rule: any read-only path uses `lean()`, "modify and save" does not.

---

**25. What has to be done to a Mongoose application before production?**

Four things.

**1. Turn `autoIndex` off.** By default Mongoose calls `createIndex` for every index in every schema at startup. That has three costs:

- indexes get built at deploy time, the worst possible moment;
- N service instances make N concurrent attempts at the same index;
- an index reaches production whenever someone edits a schema, with no review.

Apply indexes from a migration step in the deploy pipeline instead.

```js
mongoose.connect(url, { autoIndex: false });

// A deploy step, run deliberately:
await PostModel.diffIndexes();   // audit first: what would change
await PostModel.syncIndexes();   // WARNING: drops indexes not in the schema
```

**2. Put unique indexes in the migration.** This follows from the first point, and it is the less obvious half of it. The `unique: true` option in a schema is an index declaration, not a validator. So with `autoIndex: false` and no migration there is no uniqueness at all — even though the code looks like there is.

**3. Understand command buffering.** Before the connection is established Mongoose does not throw. It buffers operations up to `bufferTimeoutMS`, which is 10 seconds. In production that looks like "the request hangs for 10 seconds". Meanwhile the real cause is an unreachable cluster, or an address missing from the allowlist. Three cures:

- a healthcheck on `mongoose.connection.readyState`;
- refusing traffic until the connection is up;
- `bufferCommands: false` in critical services, so an operation without a connection fails immediately.

**4. Map errors to responses.** `E11000` is a 409, and it comes from the driver, so check `e.code` rather than `instanceof mongoose.Error`. `ValidationError` and `CastError` are 400s. An unreachable cluster is a 503. Without this mapping everything becomes a 500 and a useless alert — and the driver's `e.message` additionally leaks the key value into the API response. The Mongoose queries article has the full table.

## Typical follow-ups (group 7)

```txt
"Why use Mongoose at all if the driver exists?" → the schema in
code and validation as the value; plus an honest answer about
where it gets in the way (aggregations, migrations, needless
hydration)

"How do you type lean() results and hydrated documents?" → they
are TWO different types; HydratedDocument vs a plain object, _id
as Types.ObjectId vs a string in the DTO

"We use Next.js; hot reload throws OverwriteModelError and the
connection count keeps growing" → mongoose.models.X ?? model(...)
plus a cached connection in globalThis with a small maxPoolSize

"Doesn't __v give you optimistic locking?" → no: __v is not
incremented on every save(), and a plain field overwrite raises no
conflict; you need optimisticConcurrency: true or your own version
field in the filter
```

Two terms used in that block. A DTO is a data transfer object: the plain shape your API accepts and returns, kept apart from the database document. A plain object means a plain old JavaScript object, with no `save()` on it.

## What to say when the question is unfamiliar

```txt
Three moves that work better than silence:

1. Reduce it to the base guarantees. Almost any MongoDB
   consistency question decomposes into: single-document
   atomicity + write concern + read concern/preference. Name
   those three settings and reason from them.

2. Reduce it to the access pattern. Any schema question is
   "which queries, at what rate, with what growth bounds".
   Start with the list of queries, not the entities.

3. Name the cost. "We can do it this way, and it will cost this
   much" is a stronger answer than "this is how it's done". The
   willingness to state a trade-off is what separates a senior
   from someone who memorized recipes.
```
