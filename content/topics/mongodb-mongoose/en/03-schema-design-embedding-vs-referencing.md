# Schema Design: Embedding vs Referencing

## The schema is designed from the queries, not from the entities

Relational design goes in this order: identify entities, normalize to 3NF, then optimize whatever turned out to be slow. In MongoDB that order is inverted: you first write down the queries the application will run most often, and only then decide how to lay out the data. The document model has no normal forms — it has a match between the schema and the access pattern.

```txt
What to write down BEFORE the first collection (a blog example):

  1. post page              — post + author (name, avatar) + first
                              3 comments                      ~1000/min
  2. post feed              — 20 posts: title, author, comment
                              count, tags                      ~500/min
  3. all comments of a post — paginated, 50 per page            ~50/min
  4. author profile         — author + their last 10 posts       ~20/min
  5. comment moderation     — a single comment by _id             ~5/min

The list already shows the key fact: queries 1 and 2 are 95% of the
load, and both want the author name and the comment count together
with the post. Everything else in the design follows from that.
```

The rule the whole topic reduces to fits in one phrase: **what is read together is stored together**. What follows are the constraints that stop you from taking that rule to absurdity.

## Two ways to connect data

```txt
EMBEDDING: comments inside the post                REFERENCING: two collections
┌──────────────────────────────────┐         ┌──────────────────────────────┐
│ collection posts                 │         │ collection posts             │
│                                  │         │                              │
│ { _id: 1,                        │         │ { _id: 1, title: "Indexes" } │
│   title: "Indexes",              │         └──────────────────────────────┘
│   comments: [                    │
│     { _id: 11, body: "..." },    │         ┌─────────────────────────────────────┐
│     { _id: 12, body: "..." } ] } │         │ collection comments                 │
└──────────────────────────────────┘         │                                     │
  one read returns the whole page;           │ { _id: 11, postId: 1, body: "..." } │
 one write changes post and comment          │ { _id: 12, postId: 1, body: "..." } │
atomically; but the array grows unbounded    └─────────────────────────────────────┘
                                               growth is not bound by the document,
                                                comments have their own lifecycle;
                                                 but two queries and no atomicity
```

Embedding means putting the child data inside the parent document. Referencing means storing an `_id` (or the other way round, a `parentId` in the child) and issuing a second query.

```txt
What embedding gives you:
  + one read returns everything; no joins, no second network round-trip
  + one write changes the parent and the nested data ATOMICALLY
    (see [CRUD and Query Operators])
  + the data sits physically together — one disk/cache access
  - the document grows; the 16 MB limit and a full document rewrite
    on every write
  - the nested data cannot be addressed independently: no collection
    of its own, no separate pagination, and "give me all comments by
    this user across all posts" gets harder
  - updating a single nested element rewrites the whole document

What referencing gives you:
  + growth is not bound by the parent's size
  + child entities have their own life: own indexes, sorting,
    pagination, deletion
  + the same child document can be linked from many parents
  - at least two queries (or a $lookup — see [Aggregation Pipeline])
  - no atomicity across collections without a transaction
  - integrity is on the application: MongoDB does not forbid dangling
    references — there is no FK and no ON DELETE CASCADE here
```

## Four selection criteria

### 1. Cardinality

```txt
                   Cardinality is the first filter on the decision
┌───────────────────┬──────────────────────────────┬─────────────────────────────────┐
│ relationship      │ example in a blog            │ decision                        │
├───────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ one-to-few        │ a post has 3-10 tags         │ embed as an array               │
├───────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ one-to-few        │ a user has 2 addresses       │ embed as an array               │
├───────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ one-to-many       │ a post has 50-500 comments   │ reference + Subset in post      │
├───────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ one-to-squillions │ a post has millions of views │ reference from child, Bucket    │
├───────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ many-to-many      │ posts and tags as entities   │ array of ids on the "main" side │
└───────────────────┴──────────────────────────────┴─────────────────────────────────┘
               the few/many boundary is not a number but an answer to:
                       can a user grow this without any limit?
```

The "one-to-few / one-to-many / one-to-squillions" phrasing is useful because it turns the question from "how many now" into "how many can there ever be". Three to ten tags on a post is few and stays few forever. Comments are many: 99% of posts will have 20, but one viral post will have 50,000, and the schema has to survive exactly that case.

### 2. Access pattern: read together or separately

```txt
The questions that produce the answer:
  - Is the child data needed EVERY time the parent is read?
    Always → embedding. Sometimes → referencing (don't pay for what
    you don't read).
  - Is access to the children needed WITHOUT the parent? "All comments
    by a user", "moderate the newest comments across the system"
    → a separate collection.
  - Is pagination/sorting over the children needed? Inside an array
    that only works in the aggregation pipeline ($slice, $unwind +
    $sort) — expensive and awkward → a separate collection.
```

### 3. Change frequency and the cost of duplicates

Embedding or duplicating creates a copy. A copy is a commitment to keep it updated. So you duplicate what rarely changes, and never duplicate what changes often.

```txt
Author name and avatar    → change once a year   → duplicating is fine
Post comment count        → changes hourly       → keep it as a counter
                                                   on the post (Computed),
                                                   but do not duplicate
                                                   it in 500 places
Email, roles, ban status  → change and critical  → reference only
```

### 4. Growth bounds

```txt
The key question: can a user (or an external system) grow this set of
elements without any limit?

  post tags        — set by the author, editor caps at 10  → bounded
  likes            — any of a million users can add one    → UNBOUNDED
  comments         — anyone can write one                  → UNBOUNDED
  shipping addrs   — the user, realistically 1-5           → bounded

An unbounded array inside a document is a deferred incident, not a
"works fine so far".
```

## The running example: a blog schema

```js
// users — an entity with its own life, referenced from many places
{
  _id: ObjectId("64a1"),
  email: "max@test.com",          // changes, critical → NOT duplicated
  name: "Maksym",                 // rarely changes → duplicated
  avatar: "/a/12.png",            // rarely changes → duplicated
  passwordHash: "...",
  createdAt: ISODate("...")
}

// posts — the central aggregate: what the page and the feed need
{
  _id: ObjectId("66b0"),
  slug: "mongodb-indexes",
  title: "Indexes in MongoDB",
  body: "...",

  // Extended Reference: id + the minimum fields needed for rendering
  author: { _id: ObjectId("64a1"), name: "Maksym", avatar: "/a/12.png" },

  // one-to-few, bounded, always read together → embedding
  tags: ["mongodb", "performance"],

  // Computed: written on write, read on every page
  stats: { comments: 128, views: 9421, likes: 42 },

  // Subset: only what the post page shows above the fold
  recentComments: [
    { _id: ObjectId("77c1"), body: "thanks!",
      author: { _id: ObjectId("64b2"), name: "Anna" },
      createdAt: ISODate("...") }
  ],

  publishedAt: ISODate("...")
}

// comments — unbounded one-to-many → own collection, reference to post
{
  _id: ObjectId("77c1"),
  postId: ObjectId("66b0"),       // the reference goes child → parent
  author: { _id: ObjectId("64b2"), name: "Anna" },
  body: "thanks!",
  score: 3,
  createdAt: ISODate("...")
}
```

What this schema buys on the main queries:

```js
// 1. Post page — ONE query instead of a three-table join: the post, the
//    author fields for rendering and the first comments are all inside
const post = await db.collection("posts").findOne({ slug });

// 2. Feed — ONE query, everything needed is in the projection
const feed = await db.collection("posts")
  .find({ status: "published" })
  .project({ title: 1, slug: 1, author: 1, tags: 1, "stats.comments": 1 })
  .sort({ publishedAt: -1 })
  .limit(20)
  .toArray();

// 3. All comments of a post — a separate query with real pagination
const comments = await db.collection("comments")
  .find({ postId: post._id })
  .sort({ createdAt: -1 })
  .limit(50)
  .toArray();
```

The key observation: 95% of the load (queries 1 and 2) is served by a single round-trip to a single collection. The remaining 5% pay for a second query — and that is the right trade-off, not an oversight.

## Practical design patterns

```txt
┌────────────────────┬────────────────────────────────────────┬───────────────────────────┐
│ pattern            │ the pain it treats                     │ the cost                  │
├────────────────────┼────────────────────────────────────────┼───────────────────────────┤
│ Extended Reference │ an extra query for the author name     │ duplicates need updating  │
├────────────────────┼────────────────────────────────────────┼───────────────────────────┤
│ Subset             │ a bloated document when 3 rows suffice │ two writes instead of one │
├────────────────────┼────────────────────────────────────────┼───────────────────────────┤
│ Bucket             │ millions of tiny documents             │ point edits get harder    │
├────────────────────┼────────────────────────────────────────┼───────────────────────────┤
│ Computed           │ an aggregate recomputed on every read  │ the value can drift       │
└────────────────────┴────────────────────────────────────────┴───────────────────────────┘
```

### Extended Reference — duplicate a few fields, not the whole document

The problem: a plain `authorId` forces a second query just for the name and avatar — on every page and for every feed item. Embedding the whole author is overkill: a user has an email, a password hash and settings, none of which are needed here.

```js
// the fix: put exactly the author fields that get rendered into the post
author: { _id: ObjectId("64a1"), name: "Maksym", avatar: "/a/12.png" }
```

```txt
Applicability criterion: duplicate only fields that are
  (a) needed on almost every read of the parent, and
  (b) changed substantially less often than they are read.

A synchronization plan is mandatory — and it comes in two variants:

  1. The copy must catch up with the source:
     a name change → a background update of every document where it
     was copied (updateMany by author._id, plus an index on that
     field). Between those two writes the system is out of sync —
     that is deliberate eventual consistency, not a bug.

  2. The copy is a SNAPSHOT at the time of an event, and must NOT be
     updated: the author name "as of publication", the product price
     "as of the order", the shipping address "as recorded in the
     order". Here duplication is a domain requirement, not a
     technical optimization.

Telling these two cases apart is what separates a designed schema
from accidental denormalization.
```

```js
// Variant 1 in code: a profile update also updates the copies
await users.updateOne({ _id: userId }, { $set: { name: newName } });
await posts.updateMany(
  { "author._id": userId },
  { $set: { "author.name": newName } }
);
await comments.updateMany(
  { "author._id": userId },
  { $set: { "author.name": newName } }
);
// both collections need an index on { "author._id": 1 }, otherwise this
// is a COLLSCAN (see [Indexes and Query Performance])
```

### Subset — keep the hot slice inside the document

The problem: there can be 50,000 comments, so embedding them is out. But the post page shows the first three — and for 95% of page views a second query is issued just for those.

```js
// the fix: a FIXED-length array in the post + the full collection
db.posts.updateOne(
  { _id: postId },
  {
    $push: {
      recentComments: {
        $each: [newComment],
        $sort: { createdAt: -1 },
        $slice: 3                  // ← the array's upper bound
      }
    },
    $inc: { "stats.comments": 1 }
  }
);
await db.collection("comments").insertOne(newComment);  // the full copy
```

```txt
What matters about Subset:
  - $slice inside $push is the mechanism that makes the growth
    BOUNDED; without it Subset becomes an anti-pattern
  - there are now two writes (to posts and to comments) and they are
    NOT atomic: a crash in between can leave a post with an updated
    preview and no record in comments
  - whether that divergence is acceptable is a product decision: for
    a preview and a counter it usually is (the next comment or a
    background recompute repairs it), for money it is not — and then
    you need a transaction (see [Replication, Transactions, and
    Consistency])
  - the "right" order is: insert into comments first (the source of
    truth), then update the preview — that way only a cache is lost,
    not data
```

### Bucket — group a stream into bucket documents

```txt
  Bucket: one document per bucket, not per event
┌────────────────────────────────────────────────┐
│ naive — one document per view:                 │
│ { postId: 1, at: ISODate("...T10:00:03Z") }    │
│ { postId: 1, at: ISODate("...T10:00:07Z") }    │
│   → 10M documents a day, 10M index entries     │
├────────────────────────────────────────────────┤
│ Bucket — one document per (postId, hour):      │
│ { postId: 1, hour: ISODate("...T10:00Z"),      │
│   count: 8421, uniqueUsers: 3190 }             │
│   → 24 documents a day per post, upsert + $inc │
└────────────────────────────────────────────────┘
a weekly report reads 168 documents instead of 70 million
```

The problem: one document per event produces millions of tiny documents. Each carries storage overhead and an index entry, and — most importantly — a report has to scan millions of documents.

```js
// Views: not a document per view, but a bucket per (postId, hour)
await db.collection("postViews").updateOne(
  { postId, hour: startOfHour },
  {
    $inc: { count: 1 },
    $setOnInsert: { createdAt: new Date() }
  },
  { upsert: true }
);
// a unique index { postId: 1, hour: 1 } is mandatory — otherwise an
// upsert race creates two buckets (see [CRUD and Query Operators])

// A weekly report for one post: 168 documents instead of 70 million
db.postViews.find({ postId, hour: { $gte: weekAgo } }).sort({ hour: 1 })
```

```txt
Bucket applies when:
  - the event stream is uniform and very dense (metrics, IoT, activity
    logs, impressions)
  - it is read as a RANGE, not as individual events
  - point edits of a single event are not needed

The cost: changing or deleting one event inside a bucket is awkward;
the granularity (hour/day) is fixed at design time and can only be
changed by a recompute. For pure time series, consider time series
collections — MongoDB 5.0+ does the bucketing for you.
```

### Computed — compute on write, not on read

The problem: `stats.comments` can be obtained with `countDocuments({ postId })` — but then a feed of 20 posts performs 20 counts, each scanning the index over all comments of a post.

```js
// the fix: keep the ready value and update it in the same atomic step
// as the fact itself
db.posts.updateOne({ _id: postId }, { $inc: { "stats.comments": 1 } });

// the same for an average rating — store the sum and the count so the
// average never requires walking all the ratings
db.posts.updateOne(
  { _id: postId },
  { $inc: { "rating.sum": score, "rating.count": 1 } }
);
// the average is computed on read from two numbers
```

```txt
When to apply: read an order of magnitude more often than it changes
(counters, sums, averages, "last activity at").

A mandatory companion is a repair path. A counter will drift sooner or
later: a crashed process, a manually deleted document, a bug in a new
branch. You need a background job that recomputes it from the source
of truth and can be run by hand:

  const real = await comments.countDocuments({ postId });
  await posts.updateOne({ _id: postId },
                        { $set: { "stats.comments": real } });

A schema with Computed and no such job is a schema with no way back
to the truth.
```

## Anti-patterns

### The unbounded array

```txt
{ _id: postId, comments: [ ... 40,000 elements ... ] }

Why this breaks LONG before the 16 MB limit:
  - WiredTiger does not patch a document in place: updating the array
    rewrites the whole document → the bigger it gets, the more
    expensive EVERY $push becomes
  - the whole document is read into memory and sent over the network
    even when one element is needed (a $slice projection saves traffic
    but not the disk read)
  - a multikey index on the array gets one entry PER ELEMENT of the
    document → the index bloats (see [Indexes and Query Performance])
  - updating an element near the end requires walking the array
  - in a replica set every such update is a large oplog entry

The anti-pattern signal can be stated without numbers: elements are
appended by user actions and there is no upper bound.

The fix: referencing (its own collection) or Subset with $slice.
```

### The 16 MB limit

```txt
16 MB is a hard limit on the SIZE OF ONE DOCUMENT in BSON, including
every nested object and array. The write fails with:
  BSONObjectTooLarge / "object to insert too large"

Where else the limit shows up:
  - the result of an aggregation that collects one document via
    $group/$push (see [Aggregation Pipeline]) — worked around with a
    cursor or $out/$merge
  - a query reply is limited to ~16 MB per batch (the cursor returns
    the rest via getMore)

The practical meaning: 16 MB is not "a ceiling to grow into" but a
sign the schema is wrong. Documents in a healthy schema are
kilobytes. Files and media do not belong in documents: MongoDB has
GridFS for that, but the right answer is usually S3 plus a link in
the document.
```

### Massive denormalization with no synchronization plan

```txt
Symptom: posts and comments store a FULL copy of the author — email,
roles, settings, counters.

What happens next:
  - a user changes their email → updateMany over millions of
    documents, minutes of work and a write-load spike
  - the update fails halfway → some documents have the new email, some
    the old one, and there is NO transaction around any of it
  - a GDPR deletion turns into hunting for copies across every
    collection
  - every post grew several times larger for fields that are never
    rendered

The question an interviewer asks: "who updates the duplicates and
when, and what happens if that update fails halfway?" A good answer
names a concrete mechanism:
  - a background job/queue with retries and idempotency
  - change streams: watch users and update the copies
  - a transaction — if divergence is unacceptable (and then say
    honestly that it costs more)
  - a deliberate "we never update the copies, it is a snapshot"

No answer means the denormalization was accidental.
```

### The "SQL-style" schema: full normalization in MongoDB

```txt
Symptom: users, posts, comments, tags, post_tags, post_stats — all
separate, documents hold only identifiers, and every page is
assembled from three or four $lookup stages or five populate calls.

Why this is the worst of both worlds:
  - joins exist but are worse than relational ones: $lookup runs as a
    sub-query per input document, with no hash join and no join-order
    choice by a planner (see [Aggregation Pipeline]); populate in
    Mongoose is literally N+1 separate queries (see [Mongoose
    Queries, populate, and Pitfalls])
  - integrity is still absent: there is no FK, no ON DELETE CASCADE
    and no cross-collection CHECK
  - transactions become necessary at every step, and here they cost
    more than in a relational database
  - the document model's flexibility is unused: you end up with a
    relational schema without relational guarantees and without a
    relational optimizer

What to do: either rebuild the schema around aggregates (and then
$lookup is no longer needed), or admit the data is relational and
take PostgreSQL — see [Document Model and Use Cases]. The
in-between state is the most expensive one.
```

## The design procedure: how to answer at the whiteboard

```txt
1. Write down the application's top-5 queries and their rates.
   Without this step any answer about embedding is guesswork.

2. For each relationship, determine cardinality in terms of
   few / many / squillions — and separately: is there an upper bound?

3. Decide embed or reference by the criteria: read together? needed
   independently? how often does it change?

4. Check the bounds: how large will the document be for the worst
   realistic case (a viral post, the biggest tenant)?

5. For every duplicate, name a synchronization plan OR state
   explicitly that it is a snapshot.

6. Check which indexes the resulting queries need (see [Indexes and
   Query Performance]) — a schema without indexes for its own
   queries is unfinished.

7. Name what changes if a requirement changes: "if independent
   comment pagination is needed, they are already in a separate
   collection; if the history of author names is needed, the Extended
   Reference becomes a snapshot".
```

And the main thing worth saying out loud: there is no correct answer to "embed or reference" in a vacuum. There is an answer for a specific set of queries, volumes and consistency requirements. A candidate who says "comments are always embedded" or "always a reference" answers worse than one who names the criterion and applies it to the case at hand.

## Connection to other topics

```txt
[Document Model and Use Cases]    — 16 MB, single-document atomicity as
                                    the reason to design around aggregates
[CRUD and Query Operators]        — $push/$slice for Subset, upsert +
                                    $inc for Bucket, atomic $inc for
                                    Computed
[Indexes and Query Performance]   — indexes for the resulting queries,
                                    multikey over nested arrays, an index
                                    on "author._id" for syncing duplicates
[Aggregation Pipeline]            — $lookup as the price of referencing
                                    and why embedding removes it
[Replication, Transactions, and   — when divergence between duplicates is
 Consistency]                       unacceptable: a transaction and its cost
[Mongoose Queries, populate,      — populate as the most common way to
 and Pitfalls]                      get an accidental N+1 on a normalized
                                    schema
```

## Common interview traps

- **"Comments always go inside the post — it's a document database"** — comments have no upper bound: one viral post hits the 16 MB limit, and long before that it hits a full document rewrite on every `$push`. The correct answer is a reference plus a Subset for the preview.

- **"Embedding is always faster"** — faster when reading the whole parent. Slower when updating one nested element of a large document, because the whole document is rewritten; and more expensive on queries that don't need the nested data.

- **"Referencing is how SQL does it, so it must be right"** — a normalized schema in MongoDB gives you the relational shape without relational guarantees: `$lookup` instead of a planner, populate instead of a JOIN, no FK. That is the worst of both worlds.

- **"Duplicating data is bad"** — in the document model duplication is a tool. What is bad is duplication with no answer to "who updates the copies and when, and what happens on a mid-way failure".

- **"16 MB is a lot, we'll never hit it"** — the limit is found not on the average document but on the worst real one: the most popular post, the largest customer. And performance problems start at hundreds of kilobytes, not at 16 MB.

- **"Extended Reference is the same as embedding the whole document"** — the point is precisely to copy 2-3 fields for rendering, not the whole profile. You copy what rarely changes and is almost always read.

- **"The comment count can be computed with `countDocuments()` on read"** — on a feed of 20 posts that is 20 counts. The counter is stored and updated with an atomic `$inc`; separately, you need a way to recompute it from the source of truth.

- **"$lookup solves relationships, so normalizing is fine"** — `$lookup` runs per input document and is not a planned JOIN. It is acceptable for rare queries and reports, not for the main read path.

- **"I'd look at how a similar project did it"** — this question tests the ability to derive a schema from requirements. The answer has to start with the list of queries, not with a template.
