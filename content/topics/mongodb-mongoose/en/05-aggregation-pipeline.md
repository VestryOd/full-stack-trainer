# Aggregation Pipeline

## A pipeline of stages, not a query

`find` can filter, project and sort. Everything else is the job of aggregation: grouping, computed fields, joins, statistics. A pipeline is an array of stages. Each stage receives a stream of documents, does something with it and passes it on. The documents leaving a stage do not have to match the shape of the documents entering it.

Two plan names show up throughout this article, because an aggregation is planned like any other query. COLLSCAN means a full collection scan: the server reads every document. IXSCAN — an index scan — means it walks sorted index keys instead.

```txt
A pipeline: every stage takes a stream and emits a stream
┌───────────────────────────────────────────┐
│ collection comments                       │
│ 2,000,000 documents                       │
└───────────────────────────────────────────┘
                      │  180,000
                      ▼
┌───────────────────────────────────────────┐
│ $match: { createdAt: { $gte: monthAgo } } │
│ uses an index — it is the first stage     │
└───────────────────────────────────────────┘
                      │  4,200
                      ▼
┌───────────────────────────────────────────┐
│ $group: by author._id                     │
│ sum and count per author                  │
└───────────────────────────────────────────┘
                      │  4,200
                      ▼
┌───────────────────────────────────────────┐
│ $sort: { total: -1 }  +  $limit: 10       │
│ top-k: only the groups are sorted         │
└───────────────────────────────────────────┘
                      │  10
                      ▼
┌───────────────────────────────────────────┐
│ a cursor with the result                  │
│ 10 documents                              │
└───────────────────────────────────────────┘
the numbers on the arrows are documents passed to the next stage
```

```js
// Top 10 authors by comment count over the last month
db.comments.aggregate([
  { $match: { createdAt: { $gte: monthAgo } } },
  { $group: { _id: "$author._id",
              name:  { $first: "$author.name" },
              total: { $sum: 1 } } },
  { $sort:  { total: -1 } },
  { $limit: 10 }
]);
```

```txt
What matters about the mechanism itself:
  - aggregate returns a cursor, just like find: the result is read
    in batches (see article 02 on CRUD and query operators)
  - a field reference inside a stage is a string with a dollar
    sign: "$author.name". Without the dollar it is a literal
  - stages can repeat: two $match stages, three $addFields — all
    fine
  - the order of stages determines both the result and the
    performance
```

## The main stages

Roughly a dozen stages cover almost every real pipeline. Here they are with one line each:

```js
// $match — a filter. The same syntax as find
{ $match: { status: "published", "stats.views": { $gte: 100 } } }

// $project — keep/rename/compute fields (the shape changes)
{ $project: { _id: 0, title: 1, author: "$author.name",
              short: { $substrCP: ["$body", 0, 200] } } }

// $addFields / $set — add fields without dropping the rest
{ $addFields: { commentsPerView: { $divide: ["$stats.comments",
                                            "$stats.views"] } } }

// $group — grouping with accumulators
{ $group: { _id: "$author._id", posts: { $sum: 1 } } }

// $sort / $limit / $skip
{ $sort: { publishedAt: -1 } }, { $limit: 20 }

// $unwind — expand an array into separate documents
{ $unwind: "$tags" }

// $lookup — a "join" with another collection
{ $lookup: { from: "users", localField: "author._id",
             foreignField: "_id", as: "authorDoc" } }

// $facet — several independent sub-pipelines over the same input
{ $facet: { items: [ ... ], total: [ { $count: "n" } ] } }

// $count / $sortByCount — common shorthands
{ $count: "total" }
{ $sortByCount: "$tags" }        // = $group by value + $sort by count

// $replaceRoot / $replaceWith — make a nested object the root
{ $replaceWith: "$author" }

// $out / $merge — write the result into a collection
{ $merge: { into: "authorStats", on: "_id", whenMatched: "replace" } }
```

## $group and accumulators

`_id` in `$group` is the grouping key, not an identifier. It can be a field, a composite object, or `null` — which makes one group for the whole input.

```js
db.comments.aggregate([
  { $group: {
      // a composite key: author + month
      _id: { author: "$author._id",
             month: { $dateTrunc: { date: "$createdAt", unit: "month" } } },
      count:    { $sum: 1 },
      avgScore: { $avg: "$score" },
      best:     { $max: "$score" },
      // $first/$last only make sense after a $sort
      firstBody: { $first: "$body" },
      // $push collects an array — careful: this is the road to 16 MB
      ids:      { $push: "$_id" },
      unique:   { $addToSet: "$postId" }
  } }
]);

// One group for the whole collection
{ $group: { _id: null, total: { $sum: 1 }, views: { $sum: "$stats.views" } } }
```

```txt
The $push trap: it collects everything into an array inside a
single result document, and a document is capped at 16 MB
(megabytes). A $push grouping over a large collection fails with
BSONObjectTooLarge. If you need a list, bound it: $slice after
$push, or $limit before grouping. Or do not group at all.
```

## The "filter early" principle

Indexes in an aggregation only work on the stages that come before the first stage that reshapes the document stream. In practice that means `$match` and `$sort` belong at the front of the pipeline.

```txt
   BAD: filtering after unwinding
┌─────────────────────────────────┐
│ $unwind: "$tags"                │
│ $lookup: from: "users"          │
│ $match: { status: "published" } │
│ $sort:  { publishedAt: -1 }     │
└─────────────────────────────────┘
no index is used: stages that reshape
documents already ran before $match;
  $lookup also ran for the drafts

    GOOD: filter and sort first
┌─────────────────────────────────┐
│ $match: { status: "published" } │
│ $sort:  { publishedAt: -1 }     │
│ $limit: 20                      │
│ $lookup: from: "users"          │
│ $unwind: "$tags"                │
└─────────────────────────────────┘
    $match + $sort use the index
  { status: 1, publishedAt: -1 };
   $lookup runs over 20 documents
```

The optimizer does rearrange some things, and knowing its limits helps:

```txt
What the optimizer can do:
  - move $match forward through $project/$addFields/$unwind when
    the condition refers to fields those stages did not change
  - merge $sort + $limit into a top-k sort: the sorter keeps only
    the N best in memory instead of the whole input
  - coalesce consecutive $limit, $skip and $match stages
  - drop fields that are not used downstream (projection pushdown)

What the optimizer cannot do:
  - move $match through $group when the filter is on a computed
    field. In { $group: ... }, { $match: { total: { $gt: 10 } } }
    the filter runs after grouping, over all groups. That is
    normal and unavoidable — it is the equivalent of HAVING in
    SQL, the query language of relational databases. Just be
    aware that no index is involved.
  - guess that $lookup should have run after $limit — the order
    is yours to choose
```

Verify it the same way as for `find`, with explain. Article 04 on indexes covers reading a plan.

```js
db.posts.explain("executionStats").aggregate([ ... ]);
// in the output: stages[0].$cursor.queryPlanner.winningPlan — what
// happened to the first stage: IXSCAN or COLLSCAN, was it merged
// with the $sort
```

## $lookup — why it is not a free join

`$lookup` looks like a join and behaves like a loop. It runs once per document that reaches the stage.

```txt
       $lookup is a nested loop, not a hash join
┌──────────────────────────────────────────────────────┐
│ stage input: 500 posts                               │
├──────────────────────────────────────────────────────┤
│ for every post a lookup runs against users:          │
│   { _id: <the post authorId> }                       │
│   → 500 separate accesses to the users collection    │
│   → with an index on _id these are 500 fast IXSCANs  │
│   → without an index on foreignField — 500 COLLSCANs │
├──────────────────────────────────────────────────────┤
│ stage output: the same 500 posts + author: [ ... ]   │
└──────────────────────────────────────────────────────┘
the planner picks no join order and builds no hash table
an Extended Reference in the schema removes this stage entirely
```

```js
// The basic form: an equality join, the result is an array of matches
db.posts.aggregate([
  { $match: { status: "published" } },
  { $sort:  { publishedAt: -1 } },
  { $limit: 20 },                        // ← narrow the input first!
  { $lookup: { from: "users",
               localField: "author._id",
               foreignField: "_id",
               as: "authorDoc" } },
  { $unwind: "$authorDoc" }              // 1-element array → an object
]);

// The sub-pipeline form: filter and project inside the lookup
db.posts.aggregate([
  { $lookup: {
      from: "comments",
      let: { pid: "$_id" },
      pipeline: [
        { $match: { $expr: { $eq: ["$postId", "$$pid"] } } },
        { $sort: { createdAt: -1 } },
        { $limit: 3 },
        { $project: { body: 1, "author.name": 1 } }
      ],
      as: "recentComments"
  } }
]);
```

```txt
What you need to know about the mechanics:
  - $lookup is a nested loop: it runs for every document that
    reaches the stage. There is no hash join, no merge join and no
    join-order choice by a planner. That is a fundamental
    difference from a join in PostgreSQL — see article 06 of the
    PostgreSQL topic, on the query planner.
  - an index on foreignField is mandatory: without it each of the
    N lookups scans the target collection in full
  - the result is always an array; to get an object you need
    $unwind, and then you have to decide what to do with
    documents that had no match
  - in the sub-pipeline form the join condition is written with
    $expr and a $$variable. That is a correlated subquery, and it
    also runs per input document.
  - $lookup + $unwind on a to-many relationship multiplies the
    number of documents in the pipeline

Hence the rule: narrow the input before $lookup, with $match,
$sort and $limit. And keep $lookup out of the hot read path.
```

The main takeaway of this section is not about aggregation but about schema. If the primary query requires a `$lookup`, the schema was most likely designed relationally.

An Extended Reference — `author: { _id, name, avatar }` right inside the post — removes the stage entirely rather than optimizing it. Article 03 on schema design covers that.

`$lookup` stays a legitimate tool for reports, admin panels and rare queries. Those are the cases where a second round-trip costs more than a server-side join.

## $unwind and the cardinality explosion

`$unwind` turns one document with an N-element array into N documents. That is powerful and dangerous for exactly one reason: the number of documents in the pipeline gets multiplied.

```js
// How many posts per tag
db.posts.aggregate([
  { $match: { status: "published" } },   // 50,000 posts
  { $unwind: "$tags" },                  // → 250,000 documents (5 tags)
  { $group: { _id: "$tags", posts: { $sum: 1 } } },
  { $sort: { posts: -1 } }
]);
```

```txt
Two mandatory options people forget:

  { $unwind: { path: "$tags",
               preserveNullAndEmptyArrays: true } }

  By default a document whose array is missing or empty is
  dropped from the pipeline. This is the most common $unwind bug:
  "posts without tags disappeared from the report" — and nobody
  notices until someone reconciles the totals.

  { $unwind: { path: "$tags", includeArrayIndex: "tagIndex" } }
  — keep the element's position if you need it.
```

```txt
A sign that $unwind is unnecessary: it is immediately followed by
a $group that reassembles the document ($first on every field
plus $push on the unwound one). Often the following is enough
instead:
  - $filter / $map / $reduce — expressions over the array with no
    unwinding
  - $size — the array length
  - $reduce for a sum over the array
  - $match with $elemMatch — if all you need is a filter
Example: { $addFields: { hot: { $size: { $filter: {
  input: "$ratings", cond: { $gte: ["$$this.score", 4] } } } } } }
```

## Memory limits and allowDiskUse

Some stages cannot stream. They have to collect data before they emit a single document. Those are the stages that run into the per-stage memory limit of 100 MB (megabytes).

```txt
Blocking stages are the ones that must collect data before
emitting the first document: $group, $sort (without an index),
$bucket, $setWindowFields, $facet.

The limit for such a stage is 100 MB of memory.
On overflow: "Exceeded memory limit for $group ... pass
allowDiskUse:true".

  db.comments.aggregate(pipeline, { allowDiskUse: true })

allowDiskUse permits spilling to disk. The query stops failing
but becomes noticeably slower, so treat it as an emergency
measure rather than a normal setting. The right moves: narrow the
$match, give the $sort an index, reduce the grouping cardinality,
compute incrementally via $merge.

A separate limit: every result document, like any BSON document,
is capped at 16 MB. That is why $group with $push over a large
collection fails even with allowDiskUse.
```

## $facet — several computations in one pass

The classic filtered-list task needs the page itself, the total count and per-facet counters. That is three queries — or one `$facet`.

```js
db.posts.aggregate([
  { $match: { status: "published", tags: "mongodb" } },   // ← index here
  { $facet: {
      items: [
        { $sort: { publishedAt: -1 } },
        { $limit: 20 },
        { $project: { title: 1, slug: 1, author: 1 } }
      ],
      total: [ { $count: "count" } ],
      byTag: [
        { $unwind: "$tags" },
        { $sortByCount: "$tags" },
        { $limit: 10 }
      ]
  } }
]);
// the result is one document: { items: [...], total: [{count}], byTag: [...] }
```

```txt
What matters about $facet:
  - indexes are only used by the stages before $facet; inside the
    branches the work happens on the already-retrieved stream
  - every branch processes the entire input stream independently.
    The saving is that the collection is read once, not three
    times.
  - the result is a single document, so the 16 MB limit applies
    to it
  - $facet is blocking: the first document is emitted once all
    branches are computed
```

## Aggregate in the database or process in Node

The dividing line is the ratio between input volume and result volume.

```txt
Compute in the database when:
  - the input volume is much larger than the result (2M comments
    → 10 report rows): the result travels over the network, not
    the data
  - the work comes down to $match/$sort over indexes plus
    grouping
  - you need a sort with a limit over the whole collection (top-k)
  - the result is materialized into a collection via $merge/$out
  - the result set would not fit in the Node process memory

Compute in Node when:
  - the volume is already small: you fetched 20 documents, so
    there is no need to build a pipeline just to shape the
    response
  - the logic involves calls to external services, cache lookups,
    or rules that change with the product
  - the logic needs unit tests and has to be readable a year from
    now
  - aggregation expressions start looking like a program:
    $cond/$switch/$reduce nested ten levels deep
```

A practical rule of thumb: aggregation is good at computing **data**, the application is good at expressing **business rules**. A 12-stage pipeline with branching is a program written in an awkward language with no debugger. Split it: leave the heavy filtering and grouping in the database, keep formatting and rules in code.

And the opposite mistake, which is more common: pulling 200,000 documents into Node and summing them in a loop. That means network traffic, process memory, and pressure on the garbage collector (GC) — instead of one `$group` stage.

## Materialized views with $merge

When a report is heavy and hour-old freshness is acceptable, the aggregation is run on a schedule and stored in a separate collection.

```js
// hourly: recompute author statistics
db.comments.aggregate([
  { $match: { createdAt: { $gte: hourAgo } } },
  { $group: { _id: "$author._id", newComments: { $sum: 1 } } },
  { $merge: {
      into: "authorStats",
      on: "_id",
      whenMatched: [ { $set: { comments: { $add: ["$comments",
                                                 "$$new.newComments"] } } } ],
      whenNotMatched: "insert"
  } }
]);
// after that the API reads authorStats with a plain find — fast and
// predictable
```

```txt
$merge vs $out:
  $out    — replaces the target collection entirely with the
            result
  $merge  — inserts/updates/merges by key; supports incremental
            recomputation and works with the target collection's
            existing data and indexes
```

## Connection to other topics

- **02 — CRUD and Query Operators.** CRUD is create, read, update, delete. `$match` uses the same filter language; cursors and result batching.
- **03 — Schema Design: Embedding vs Referencing.** Why a good schema removes `$lookup`; Computed fields instead of aggregating on every read.
- **04 — Indexes and Query Performance.** Indexes only work on the leading stages; explain for a pipeline; the `foreignField` index for `$lookup`.
- **06 — Replication, Transactions, and Consistency.** Running heavy aggregations on a secondary, and why that is risky.
- **08 — Mongoose Queries, populate, and Pitfalls.** `populate` against `$lookup`: N+1 queries against one stage.
- **The PostgreSQL topic, article 06 — Query Planner and EXPLAIN.** What a real join planner looks like, the one `$lookup` gets compared to.

## Common interview traps

- **"$lookup is a join, just in MongoDB"** — it is a nested loop executed per input document, with no hash join and no join-order choice. It requires an index on `foreignField` and does not belong in the hot read path.

- **"Stage order doesn't matter, the optimizer will sort it out"** — the optimizer will move `$match` through `$project`/`$addFields`. It will not push it through `$group`, and it will not guess that `$lookup` should have come after `$limit`. Indexes only work on the stages before the first reshaping one.

- **"$unwind just expands an array"** — it also multiplies the document count in the pipeline. And by default it **drops** documents with no array. `preserveNullAndEmptyArrays: true` is needed when the empty ones matter.

- **"Aggregation doesn't use indexes"** — it does, but only on the leading stages: `$match` and `$sort` before anything that reshapes documents. That is exactly why "filter early" is a requirement, not a style preference.

- **"allowDiskUse fixes the memory problem"** — it removes the failure, not the slowness. The real fix is an index for the `$sort`, a narrower `$match`, or incremental recomputation via `$merge`.

- **"I'll collect everything with $group + $push"** — the result document is capped at 16 MB. `$push` over a large collection will hit that regardless of `allowDiskUse`.

- **"$facet runs its branches in parallel, so it's fast"** — the benefit is not parallelism but that the input stream is read once. Inside the branches there are no indexes, and the stage is blocking.

- **"Since we have aggregation, counters can be computed on the fly"** — on a hot read path that is extra work on every request. A feed is the usual example. Keep the counter ready (`$inc` on write, the Computed pattern) and leave aggregation for recomputation and reports.

- **"Better to keep all logic in the pipeline — less code in the app"** — a 12-stage pipeline with `$cond`/`$switch` cannot be unit-tested. It also cannot be read a year later. The database gets bulk filtering and grouping; the application gets business rules.
