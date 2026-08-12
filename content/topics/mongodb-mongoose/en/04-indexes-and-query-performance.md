# Indexes and Query Performance

## An index is a separate B-tree structure over document fields

Without an index, `find({ slug: "mongodb-indexes" })` is a COLLSCAN: the server reads every document in the collection and checks the condition. An index is a separate structure (a B-tree, as in PostgreSQL) that stores sorted key values plus a pointer to the document's location in the data files.

```js
db.posts.createIndex({ slug: 1 })                       // 1 — ascending
db.posts.createIndex({ slug: 1 }, { name: "slug_uniq", unique: true })
db.posts.getIndexes()                                   // all indexes
db.posts.dropIndex("slug_1")
db.posts.stats().indexSizes                             // size of each
```

```txt
What to remember about the structure:
  - the _id_ index is created automatically and cannot be dropped
  - EVERY document of the collection is in the index; a document
    without the field is indexed with the value null (except in
    sparse/partial indexes)
  - an index on a nested field uses dot notation:
      { "author._id": 1 }  — an index on a field inside the object
      { author: 1 }        — an index on the WHOLE object; it only
                             serves queries for full equality of the
                             object with the same key order
  - indexes live in the same WiredTiger cache as the data and compete
    with it for memory
```

## Single field: direction does not matter

```js
db.posts.createIndex({ publishedAt: 1 })
// serves both sort({ publishedAt: 1 }) and sort({ publishedAt: -1 }):
// a B-tree can be scanned in either direction
```

Direction starts to matter only in a compound index when sorting by several fields — see below.

## Compound indexes and the ESR rule

A compound index stores keys sorted by the first field, then by the second within it, and so on. Two practical rules follow from that.

The first is the **prefix rule**: an index `{a: 1, b: 1, c: 1}` serves queries on `(a)`, `(a, b)`, `(a, b, c)`, but not on `(b)` or `(b, c)`. Without pinning the left-hand fields there is no way to jump into the right part of the tree.

The second is **ESR: Equality → Sort → Range**. This is the main practical tool for designing a compound index.

```txt
       ESR: how to turn a query into index field order
┌───────────────────────────────────────────────────────────┐
│ query:                                                    │
│ db.posts.find({ status: "published",                      │
│                 "author._id": authorId,                   │
│                 publishedAt: { $gte: monthAgo } })        │
│         .sort({ views: -1 })                              │
├───────────────────────────────────────────────────────────┤
│ E (equality)  status, author._id   — exact values         │
│ S (sort)      views: -1            — output order         │
│ R (range)     publishedAt: $gte    — a range              │
├───────────────────────────────────────────────────────────┤
│ index:                                                    │
│ { status: 1, "author._id": 1, views: -1, publishedAt: 1 } │
│   → IXSCAN with no SORT stage and no extra FETCH          │
└───────────────────────────────────────────────────────────┘
swap S and R and you get an in-memory SORT over the whole result
```

Why that order:

```txt
E — Equality first.
    Exact equality pins a key prefix, which narrows the scan to a
    contiguous stretch of the index. Every equality field up front
    reduces the number of keys examined.

S — Sort right after the equality fields.
    Within the pinned prefix the keys are ALREADY sorted by the next
    index field. If that field matches the sort, the server returns
    documents in the required order — there is no SORT stage in the
    plan. That is also what makes limit cheap: 20 documents come off
    the start of the scan instead of after sorting the whole result.

R — Range last.
    A range ($gt, $lt, $in over many values, an anchored $regex) reads
    a CONTIGUOUS stretch of keys. Inside that stretch the order by the
    next field is no longer a global order — which is why any sort
    field placed AFTER a range field does not save you from an
    in-memory sort.
```

```js
// The same query with the "intuitive" index (range before sort)
db.posts.createIndex({ status: 1, publishedAt: 1, views: -1 })
db.posts.find({ status: "published", publishedAt: { $gte: monthAgo } })
        .sort({ views: -1 }).limit(20).explain("executionStats")
// → the plan contains SORT: the server collected ALL matching documents
//   for the month, sorted them in memory and only then took 20

// The ESR index
db.posts.createIndex({ status: 1, views: -1, publishedAt: 1 })
// → no SORT: the scan is already in order, and limit cuts it short
```

Field direction in a compound index matters when the sort spans several fields in different directions:

```txt
sort({ publishedAt: -1, title: 1 }) is served by
  { publishedAt: -1, title: 1 }   — an exact match
  { publishedAt: 1, title: -1 }   — a FULL reversal (scanned backwards)
                                    also works
  { publishedAt: -1, title: -1 }  — does NOT work: an in-memory sort
                                    is required
```

## Multikey: indexes over arrays

If the indexed field is an array, the index becomes multikey: one index entry is created per ELEMENT of the array for each document. There is no special syntax — MongoDB detects it.

```js
db.posts.createIndex({ tags: 1 })       // multikey if tags is an array
db.posts.find({ tags: "mongodb" })      // IXSCAN over one index entry

// An index on a field inside an array of objects is multikey too
db.posts.createIndex({ "recentComments.author._id": 1 })
```

```txt
Multikey limitations that come up in interviews:
  - a compound index may contain only ONE array path.
    { tags: 1, ratings: 1 } with two arrays → write error
    "cannot index parallel arrays"
  - a covered query over a multikey field is impossible: the server
    cannot reconstruct the original array from separate index entries,
    so the document is read anyway (FETCH)
  - index size scales with the total number of elements, not the
    number of documents: 1M documents with 20 tags = 20M entries
  - $elemMatch with several conditions does use the index, but the
    "both conditions on the same element" filtering happens at FETCH
    (see [CRUD and Query Operators])
```

This is another argument against the unbounded arrays discussed in [Schema Design: Embedding vs Referencing]: they hurt not only document size but index size too.

## Unique, partial, TTL

```js
// unique — uniqueness within the collection
db.users.createIndex({ email: 1 }, { unique: true })
// on an array the ELEMENTS are checked: two documents cannot share an
// element in a unique multikey field
```

```txt
The unique trap that breaks production: a missing field is indexed as
null, and null == null. So TWO documents without an email field
violate uniqueness:

  db.users.insertOne({ name: "a" })            // ok, email = null
  db.users.insertOne({ name: "b" })            // E11000 duplicate key

The correct fix is a partial index — "unique only among documents that
have the field":

  db.users.createIndex(
    { email: 1 },
    { unique: true, partialFilterExpression: { email: { $exists: true } } }
  )

sparse: true solves the same problem and still works, but
partialFilterExpression is more flexible and is the recommended way.
```

```js
// partial — index a subset of the documents
db.posts.createIndex(
  { publishedAt: -1 },
  { partialFilterExpression: { status: "published" } }
);
// the index is many times smaller (drafts are not in it) → it fits the
// cache better. The condition: a query MUST include
// { status: "published" } (or something stricter), otherwise the
// planner is not allowed to use this index

// TTL — automatic expiry by time
db.sessions.createIndex({ expiresAt: 1 }, { expireAfterSeconds: 0 });
// deletes the document once expiresAt is in the past
db.eventLog.createIndex({ createdAt: 1 }, { expireAfterSeconds: 604800 });
// deletes 7 days after createdAt
```

```txt
What matters about TTL:
  - deletion is done by a BACKGROUND task that wakes up once every 60
    seconds: it is not immediate, and a document may live an extra
    minute or much longer under load. Application logic must not treat
    TTL as a precise deadline (a session is still checked against
    expiresAt in the query)
  - the field must be a Date (or an array of dates — then the minimum
    is used)
  - TTL cannot be set on a compound index
  - only the primary deletes; secondaries receive the change through
    the oplog (see [Replication, Transactions, and Consistency])
```

## The text index and an honest note about Atlas Search

```js
db.posts.createIndex({ title: "text", body: "text" },
                     { weights: { title: 10, body: 1 },
                       default_language: "english" });

db.posts.find({ $text: { $search: "mongodb indexes" } },
              { score: { $meta: "textScore" } })
        .sort({ score: { $meta: "textScore" } });
```

```txt
Capabilities and limits of the built-in text index:
  + stemming and stop words for the major languages, field weights,
    word exclusion via "-word", quoted phrases
  + works in a plain self-hosted cluster, with no external services
  - A COLLECTION CAN HAVE ONLY ONE text index
  - no typo tolerance (fuzzy), no autocomplete, no synonyms, no
    search-engine-grade relevance, no facets
  - $text cannot be combined with certain stages and sorts as freely
    as a regular index

The honest interview answer: for real search in 2026 the MongoDB
ecosystem uses Atlas Search (Lucene under the hood) — it provides
fuzzy matching, autocomplete, facets and highlighting. The built-in
text index is "search over titles so we don't have to run
Elasticsearch", and its one-per-collection limit should be stated
up front.
```

Two more types are worth knowing by name: **wildcard** `{ "attributes.$**": 1 }` — for when the set of fields is not known in advance (those heterogeneous catalogue attributes), and **hashed** — for sharding on a hash of the key (see [Replication, Transactions, and Consistency]).

## explain(): how to read a plan

```js
db.posts.find({ status: "published" }).sort({ views: -1 }).limit(20)
        .explain("executionStats")
```

```txt
Three modes:
  queryPlanner       — the chosen plan only, the query is NOT executed
                       (the default)
  executionStats     — the plan plus real numbers: the query runs
  allPlansExecution  — the same plus stats for the rejected plans
```

```txt
  no index              index + documents              covered query
┌──────────┐            ┌────────┐                 ┌────────────────────┐
│ COLLSCAN │            │ IXSCAN │                 │ IXSCAN             │
│   ↓      │            │   ↓    │                 │   ↓                │
│ SORT     │            │ FETCH  │                 │ PROJECTION_COVERED │
│   ↓      │            │   ↓    │                 │   ↓                │
│ LIMIT    │            │ LIMIT  │                 │ LIMIT              │
└──────────┘            └────────┘                 └────────────────────┘
reads every document,   finds keys in the index,   documents are never read:
sorts in memory         then reads the documents      docsExamined = 0
```

The tree in `winningPlan` is printed from the root to the leaves, i.e. in the reverse of the data flow: you see `LIMIT` first, `FETCH` inside it, and `IXSCAN` inside that. It is easier to read from the deepest stage — that is the one producing documents.

```txt
The four numbers from executionStats that decide everything:
  nReturned           — how many documents the query returned
  totalKeysExamined   — how many index keys were examined
  totalDocsExamined   — how many documents were read from the collection
  executionTimeMillis — the execution time

A healthy query: nReturned ≈ totalKeysExamined ≈ totalDocsExamined.
Any order-of-magnitude gap is work that was done for nothing.
```

```txt
                   Reading executionStats: symptom → diagnosis → action
┌───────────────────────────┬─────────────────────────┬─────────────────────────────────┐
│ what you see              │ what it means           │ what to do                      │
├───────────────────────────┼─────────────────────────┼─────────────────────────────────┤
│ stage: COLLSCAN           │ no index is used        │ create an index per ESR         │
├───────────────────────────┼─────────────────────────┼─────────────────────────────────┤
│ stage: SORT               │ sorting in memory       │ add the sort field to the index │
├───────────────────────────┼─────────────────────────┼─────────────────────────────────┤
│ docsExamined >> nReturned │ index is not selective  │ revisit the field order         │
├───────────────────────────┼─────────────────────────┼─────────────────────────────────┤
│ keysExamined >> nReturned │ a wide range is scanned │ move equality fields first      │
├───────────────────────────┼─────────────────────────┼─────────────────────────────────┤
│ docsExamined = 0          │ a covered query         │ nothing — this is the goal      │
├───────────────────────────┼─────────────────────────┼─────────────────────────────────┤
│ rejectedPlans is empty    │ only one plan existed   │ check it is the expected one    │
└───────────────────────────┴─────────────────────────┴─────────────────────────────────┘
           a healthy query looks like: nReturned ≈ docsExamined ≈ keysExamined
```

The `SORT` stage deserves a separate note: it means an in-memory sort, and it has a 100 MB limit. Exceeding it fails the query with "Sort exceeded memory limit" — you then either need `allowDiskUse` (available for `find` since 4.4) or, better, an ESR index that removes the stage entirely.

```js
// Checking whether the expected index was used
const e = db.posts.find(filter).sort(s).explain("executionStats");
e.executionStats.executionStages.stage      // "LIMIT" / "FETCH" / "SORT"...
e.queryPlanner.winningPlan.inputStage.indexName
e.queryPlanner.rejectedPlans.length         // were there alternatives
```

The planner does not choose a plan from a formula but empirically: on the first run of a query shape it races the candidates over a small amount of work, picks the best one and stores it in the plan cache. Hence a practical consequence — a plan can "suddenly change": the cache is cleared on index rebuilds, restarts, and significant changes in data volume. So design the index to be the winner by ESR rather than hoping the planner makes a lucky choice.

## Covered queries

If every field the query needs — in the filter, the projection and the sort — is present in the index, the server answers without reading documents at all.

```js
db.posts.createIndex({ status: 1, publishedAt: -1, title: 1 });

db.posts.find({ status: "published" }, { _id: 0, title: 1, publishedAt: 1 })
        .sort({ publishedAt: -1 });
// → totalDocsExamined: 0, stage PROJECTION_COVERED
```

```txt
Conditions for a covered query:
  1. every filter/sort/projection field is in the index
  2. the projection excludes _id ({ _id: 0 }) unless _id is in the index
  3. the indexed field is NOT multikey (the array cannot be rebuilt)
  4. the fields are not inside subdocuments that would require a shape
     check

The signal in explain: totalDocsExamined = 0 with nReturned > 0.
The practical takeaway: a covered query is the goal for hot "list"
queries (feeds, autocomplete) where the projection is small and
predictable.
```

## When an index is NOT used

```txt
1. ESR is violated: the range field comes before the sort field
   → there is an IXSCAN, but an in-memory SORT appears over the whole
   result set.

2. $regex without a leading anchor, or with the i flag
   /^mongodb-/  → the prefix is known → IXSCAN over a range
   /^mongodb-/i → case-insensitivity breaks the order → index scan
   /indexes/    → substring in the middle → index scan or COLLSCAN

3. $ne / $nin — semantically "everything except": selectivity is close
   to 100%, so even when the index is used almost all of it is read.
   In practice this is reformulated as an $in over the allowed values.

4. A computation over the field instead of the field itself
   { $expr: { $gt: [ { $year: "$publishedAt" }, 2025 ] } } — the index
   on publishedAt does not apply; you need a range on the field itself
   ($gte/$lt on the year boundaries). $where uses no indexes at all and
   runs JS on the server (do not use it).

5. BSON type mismatch: "42" and 42 are different index values.
   The classic: an id arrives from the query string as a string while
   the database stores an ObjectId → the query honestly finds nothing.

6. Collation mismatch: an index created with one collation does not
   serve a query with another.

7. $or — every branch needs its OWN index. If one branch has none, the
   whole $or degrades to a COLLSCAN (in the plan: SUBPLAN/OR).

8. Low selectivity: { archived: false } when 99% are false — the
   planner will reasonably choose a COLLSCAN, because scattered
   document reads through the index cost more than a sequential scan.

9. The index does not fit in memory: it is used, but every access to
   its pages is a disk read, and the benefit shrinks.
```

## The write cost of indexes

```txt
Every insert/update/delete updates ALL affected indexes:
  - insert → one entry in each index (in a multikey index, one per
    array element)
  - update of a field that is in an index → the old key is removed and
    a new one inserted
  - update of a field that is in NO index → indexes are untouched
  - delete → keys are removed from every index

Practical consequences:
  - 10 indexes on a write-heavy collection means 10x the work per
    insert
  - indexes must fit in the WiredTiger cache (by default ~50% of RAM
    minus 1 GB) together with the working data set; otherwise the
    index stops being fast
  - a "just in case" index is a permanent tax on writes with no
    benefit on reads
```

```js
// Find unused indexes: access statistics since the last restart
db.posts.aggregate([{ $indexStats: {} }])
// → { name, accesses: { ops: 0, since } } — ops: 0 under live traffic
//   over a long period makes it a deletion candidate

// Safe removal: hide it from the planner first, confirm nothing got
// slower, and only then drop it
db.posts.hideIndex("status_1_views_-1")
db.posts.unhideIndex("status_1_views_-1")   // if things got worse
db.posts.dropIndex("status_1_views_-1")
```

About building indexes in production: since 4.2 `createIndex` uses a hybrid build and does not hold the collection locked for the whole build, but it does create noticeable disk and CPU load. On large production clusters indexes are traditionally built rolling-style — one replica set member at a time. In Mongoose applications, automatic index creation must be turned off separately (`autoIndex: false`) and managed deliberately — see [Mongoose Queries, populate, and Pitfalls].

## A procedure for a slow query

```txt
1. Find the slow query instead of guessing it: the profiler
   db.setProfilingLevel(1, { slowms: 100 })
   db.system.profile.find().sort({ ts: -1 })
   (in Atlas — Performance Advisor and the Profiler tab)

2. explain("executionStats") and the four numbers: nReturned against
   keysExamined and docsExamined.

3. Split the query by ESR and design the index — including the sort
   field.

4. Check whether the query can be made covered: a small projection
   plus { _id: 0 }.

5. Re-run explain on the same data: did the SORT stage disappear, do
   the numbers line up?

6. Make sure you did not create a duplicate: an index { a: 1 } is
   unnecessary if { a: 1, b: 1 } exists — the prefix already serves
   queries on a.
```

## Connection to other topics

```txt
[CRUD and Query Operators]        — which filters are indexable at all:
                                    $elemMatch, $regex, $ne, projections
[Schema Design: Embedding vs      — indexes on nested fields, multikey as
 Referencing]                       another cost of large arrays, the
                                    index on "author._id" for syncing
                                    duplicates
[Aggregation Pipeline]            — $match/$sort at the front of the
                                    pipeline as the only way to let an
                                    aggregation use an index
[Replication, Transactions, and   — the hashed index and the shard key,
 Consistency]                       TTL on secondaries via the oplog
[Mongoose Queries, populate,      — autoIndex in production, syncIndexes,
 and Pitfalls]                      lean() and covered queries
the PostgreSQL topic,             — the same B-tree, prefix rule and
[Indexes and Internals]             covering index in relational form
```

## Common interview traps

- **"Field order in a compound index does not matter"** — it matters fundamentally: the prefix rule and ESR. `{status, views, publishedAt}` and `{status, publishedAt, views}` behave differently on the same query; the second adds a SORT stage.

- **"The ESR rule is Equality, Sort, Range… but what does sort have to do with it?"** — the sort field must be in the index, otherwise sorting happens in memory with a 100 MB limit, and `limit` stops being cheap: the whole result set has to be sorted first.

- **"`{ tags: 1 }` is a regular index"** — if `tags` is an array it is multikey: one entry per element, no covered queries, and no second array allowed in the same compound index.

- **"`unique: true` and duplicates are gone"** — documents without the field are indexed as `null`, so the second such document fails with E11000. You need `partialFilterExpression: { field: { $exists: true } }`.

- **"A TTL index deletes the document exactly on time"** — the background task wakes up once a minute, and under load the delay is larger. Session expiry is checked in the query, not delegated to TTL.

- **"An index always speeds up a query"** — with low selectivity the planner will choose a COLLSCAN, and that is the right decision. And on the write path every index is a permanent overhead.

- **"explain shows an index is used, so we're fine"** — look at the numbers: `keysExamined` and `docsExamined` against `nReturned`, and the absence of a SORT stage. An IXSCAN that examines a million keys to return 20 documents is a slow query with an index.

- **"A covered query is when an index exists"** — it is when no documents are read at all: `totalDocsExamined: 0`. It requires all fields in the index, `_id` excluded from the projection, and a non-multikey field.

- **"`$regex` uses the index"** — only with a `^` anchor and without the `i` flag. A substring search is a scan; real search needs a text index (one per collection) or Atlas Search.

- **"More indexes means faster"** — faster until the indexes stop fitting in the cache and writes start costing several times more. Unused indexes are found via `$indexStats` and dropped (after `hideIndex` first).
