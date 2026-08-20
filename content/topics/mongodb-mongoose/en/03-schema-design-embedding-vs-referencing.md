# Schema Design: Embedding vs Referencing

## The schema is designed from the queries, not from the entities

In MongoDB you design from the queries. First write down the queries the application will run most often. Only then decide how to lay out the data.

Relational design goes the other way round: identify entities, normalize to 3NF, then optimize whatever turned out to be slow. 3NF is the third normal form — the rule set that pulls duplicated columns out into tables of their own. The document model has no normal forms at all. What it has instead is a match between the schema and the access pattern.

```txt
What to write down before the first collection (a blog example):

  1. post page      ~1000/min
     post + author (name, avatar) + first 3 comments
  2. post feed       ~500/min
     20 posts: title, author, comment count, tags
  3. all comments of a post   ~50/min
     paginated, 50 per page
  4. author profile  ~20/min
     author + their last 10 posts
  5. comment moderation   ~5/min
     a single comment by _id

The list already shows the key fact: queries 1 and 2 are 95% of the
load, and both want the author name and the comment count together
with the post. Everything else in the design follows from that.
```

The rule the whole topic reduces to fits in one phrase: **what is read together is stored together**. What follows are the constraints that keep you from pushing that rule too far.

## Two ways to connect data

There are exactly two. Embedding means putting the child data inside the parent document. Referencing means storing an `_id` — or the other way round, a `parentId` in the child — and issuing a second query.

```txt
EMBEDDING: comments inside the post
┌──────────────────────────────────┐
│ collection posts                 │
│                                  │
│ { _id: 1,                        │
│   title: "Indexes",              │
│   comments: [                    │
│     { _id: 11, body: "..." },    │
│     { _id: 12, body: "..." } ] } │
└──────────────────────────────────┘
  one read returns the whole page;
 one write changes post and comment
atomically; but the array grows unbounded

      REFERENCING: two collections
┌──────────────────────────────┐
│ collection posts             │
│                              │
│ { _id: 1, title: "Indexes" } │
└──────────────────────────────┘

┌─────────────────────────────────────┐
│ collection comments                 │
│                                     │
│ { _id: 11, postId: 1, body: "..." } │
│ { _id: 12, postId: 1, body: "..." } │
└─────────────────────────────────────┘
  growth is not bound by the document,
   comments have their own lifecycle;
    but two queries and no atomicity
```

```txt
What embedding gives you:
  + one read returns everything; no joins, no second network
    round-trip
  + one write changes the parent and the nested data atomically
    (article 02 covers single-document atomicity)
  + the data sits physically together — one disk or cache access
  - the document grows; the 16 MB limit, and a full document
    rewrite on every write
  - the nested data cannot be addressed independently: no
    collection of its own, no separate pagination, and "give me
    all comments by this user across all posts" gets harder
  - updating a single nested element rewrites the whole document

What referencing gives you:
  + growth is not bound by the parent's size
  + child entities have their own life: own indexes, sorting,
    pagination, deletion
  + the same child document can be linked from many parents
  - at least two queries, or a $lookup — see article 05 on the
    aggregation pipeline
  - no atomicity across collections without a transaction
  - integrity is on the application: MongoDB does not forbid
    dangling references. There is no foreign key here and no
    ON DELETE CASCADE.
```

## Four selection criteria

### 1. Cardinality

Cardinality is how many children one parent can have, and it is the first filter on the decision:

| relationship | example in a blog | decision |
|---|---|---|
| one-to-few | a post has 3-10 tags | embed as an array |
| one-to-few | a user has 2 addresses | embed as an array |
| one-to-many | a post has 50-500 comments | reference + Subset in the post |
| one-to-squillions | a post has millions of views | reference from the child, Bucket |
| many-to-many | posts and tags as entities | array of ids on the "main" side |

The few/many boundary is not a number. It is the answer to one question: can a user grow this without any limit?

That phrasing is useful because it turns "how many now" into "how many can there ever be". Three to ten tags on a post is few, and stays few forever. Comments are many. 99% of posts will have 20 of them, one viral post will have 50,000, and the schema has to survive exactly that case.

### 2. Access pattern: read together or separately

Three questions decide it, and each one points straight at an answer:

```txt
  - Is the child data needed every time the parent is read?
    Always → embedding. Sometimes → referencing (do not pay for
    what you do not read).
  - Is access to the children needed without the parent? "All
    comments by a user", "moderate the newest comments across
    the system" → a separate collection.
  - Is pagination or sorting over the children needed? Inside an
    array that only works in the aggregation pipeline ($slice,
    $unwind + $sort) — expensive and awkward → a separate
    collection.
```

### 3. Change frequency and the cost of duplicates

Embedding or duplicating creates a copy. A copy is a commitment to keep it updated. So you duplicate what rarely changes, and never duplicate what changes often.

- **Author name and avatar** — they change about once a year, so duplicating them is fine.
- **Post comment count** — it changes hourly. Keep it as a counter on the post (the Computed pattern below), but do not duplicate it in 500 places.
- **Email, roles, ban status** — they change, and they are critical. Reference only.

### 4. Growth bounds

The last criterion is a single question: can a user, or an external system, grow this set of elements without any limit?

```txt
  post tags       — author sets them, editor caps at 10  → bounded
  likes           — any of a million users can add one   → unbounded
  comments        — anyone can write one                 → unbounded
  shipping addrs  — the user, realistically 1-5          → bounded
```

An unbounded array inside a document is a deferred incident, not a "works fine so far".

## The running example: a blog schema

The criteria above turn the blog into three collections: `users`, `posts` and `comments`.

```js
// users — an entity with its own life, referenced from many places
{
  _id: ObjectId("64a1"),
  email: "max@test.com",          // changes, critical → not duplicated
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

  // Subset: only what the post page shows on the first screen
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
// 1. Post page — one query instead of a three-table join: the post, the
//    author fields for rendering and the first comments are all inside
const post = await db.collection("posts").findOne({ slug });

// 2. Feed — one query, everything needed is in the projection
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

The key observation: 95% of the load (queries 1 and 2) is served by a single round-trip to a single collection. The remaining 5% pay for a second query, and that is the right trade-off, not an oversight.

## Practical design patterns

Four patterns cover most of what a document schema needs, and each one has a price tag:

| pattern | the pain it treats | the cost |
|---|---|---|
| Extended Reference | an extra query for the author name | duplicates need updating |
| Subset | a bloated document when 3 rows suffice | two writes instead of one |
| Bucket | millions of tiny documents | point edits get harder |
| Computed | an aggregate recomputed on every read | the value can drift |

### Extended Reference — duplicate a few fields, not the whole document

The problem: a plain `authorId` forces a second query just for the name and avatar, on every page and for every feed item. Embedding the whole author is overkill, because a user has an email, a password hash and settings, and none of those are needed here.

```js
// the fix: put exactly the author fields that get rendered into the post
author: { _id: ObjectId("64a1"), name: "Maksym", avatar: "/a/12.png" }
```

```txt
Applicability criterion: duplicate only fields that are
  (a) needed on almost every read of the parent, and
  (b) changed substantially less often than they are read.

A synchronization plan is mandatory, and it comes in two variants:

  1. The copy must catch up with the source.
     A name change triggers a background update of every document
     where it was copied: updateMany by author._id, plus an index
     on that field. Between those two writes the system is out of
     sync. That is deliberate eventual consistency — the copies
     become correct a little later, not instantly — not a bug.

  2. The copy is a snapshot at the time of an event, and must not
     be updated: the author name "as of publication", the product
     price "as of the order", the shipping address "as recorded
     in the order". Here duplication is a domain requirement, not
     a technical optimization.

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
// is a COLLSCAN — a full scan of every document (see article 04)
```

### Subset — keep the hot slice inside the document

The problem: there can be 50,000 comments, so embedding them is out. But the post page shows the first three, and for 95% of page views a second query is issued just for those.

```js
// the fix: a fixed-length array in the post + the full collection
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
  - $slice inside $push is the mechanism that bounds the growth;
    without it Subset becomes an anti-pattern
  - there are now two writes, to posts and to comments, and they
    are not atomic: a crash in between can leave a post with an
    updated preview and no record in comments
  - whether that divergence is acceptable is a product decision.
    For a preview and a counter it usually is: the next comment,
    or a background recompute, repairs it. For money it is not,
    and then you need a transaction — see article 06.
  - the "right" order is: insert into comments first (the source
    of truth), then update the preview. That way only a cache is
    lost, not data.
```

### Bucket — group a stream into bucket documents

The problem: one document per event produces millions of tiny documents. Each one carries storage overhead and an index entry. And, most importantly, a report has to scan millions of documents.

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
// upsert race creates two buckets (see article 02 on upsert)

// A weekly report for one post: 168 documents instead of 70 million
db.postViews.find({ postId, hour: { $gte: weekAgo } }).sort({ hour: 1 })
```

```txt
Bucket applies when:
  - the event stream is uniform and very dense: metrics, activity
    logs, impressions, or readings from the internet of things
    (IoT — network-connected sensors and devices)
  - it is read as a range, not as individual events
  - point edits of a single event are not needed

The cost: changing or deleting one event inside a bucket is
awkward. The granularity (hour or day) is fixed at design time
and can only be changed by a recompute. For pure time series,
consider time series collections — MongoDB 5.0+ does the
bucketing for you.
```

### Computed — compute on write, not on read

The problem: `stats.comments` can be obtained with `countDocuments({ postId })`. But then a feed of 20 posts performs 20 counts, and each one scans the index over all comments of a post.

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
When to apply: the value is read an order of magnitude more often
than it changes — counters, sums, averages, "last activity at".

A mandatory companion is a repair path. A counter will drift
sooner or later: a crashed process, a manually deleted document,
a bug in a new branch. You need a background job that recomputes
it from the source of truth and can also be run by hand:

  const real = await comments.countDocuments({ postId });
  await posts.updateOne({ _id: postId },
                        { $set: { "stats.comments": real } });

A schema with Computed and no such job is a schema with no way
back to the truth.
```

## Anti-patterns

### The unbounded array

An array that only ever grows is the most common schema defect in MongoDB. It breaks long before the 16 MB limit, for five separate reasons.

```txt
{ _id: postId, comments: [ ... 40,000 elements ... ] }

  - WiredTiger, MongoDB's storage engine, does not patch a
    document in place. Updating the array rewrites the whole
    document, so the bigger it gets, the more expensive every
    single $push becomes.
  - the whole document is read into memory and sent over the
    network even when one element is needed (a $slice projection
    saves traffic but not the disk read)
  - an index on an array is a multikey index: it stores one entry
    per element of the document, so the index bloats along with
    the array (see article 04)
  - updating an element near the end requires walking the array
  - in a replica set every such update is a large entry in the
    oplog, the log of writes that secondaries replay

The anti-pattern signal can be stated without numbers: elements
are appended by user actions and there is no upper bound.

The fix: referencing (its own collection), or Subset with $slice.
```

### The 16 MB limit

16 MB is a hard limit on the size of one document. People plan around it when they should be treating it as a warning sign.

```txt
The limit covers one document in BSON — the binary, typed form
MongoDB stores — including every nested object and array. The
write fails with:
  BSONObjectTooLarge / "object to insert too large"

Where else the limit shows up:
  - the result of an aggregation that collects one document via
    $group/$push (see article 05) — worked around with a cursor
    or with $out/$merge
  - a query reply is limited to ~16 MB per batch (the cursor
    returns the rest via getMore)

The practical meaning: 16 MB is not "a ceiling to grow into" but
a sign the schema is wrong. Documents in a healthy schema are
kilobytes. Files and media do not belong in documents: MongoDB
has GridFS for that, but the right answer is usually object
storage such as S3, plus a link in the document.
```

### Massive denormalization with no synchronization plan

The symptom is easy to spot: `posts` and `comments` store a full copy of the author — email, roles, settings, counters.

```txt
What happens next:
  - a user changes their email → updateMany over millions of
    documents, minutes of work and a write-load spike
  - the update fails halfway → some documents have the new email,
    some the old one, and no transaction around any of it
  - a deletion request under GDPR (the General Data Protection
    Regulation, the European privacy law) turns into a search for
    copies across every collection
  - every post grew several times larger for fields that are
    never rendered

The question an interviewer asks: "who updates the duplicates and
when, and what happens if that update fails halfway?" A good
answer names a concrete mechanism:
  - a background job or queue, with retries and idempotency
  - change streams: watch users and update the copies
  - a transaction, if divergence is unacceptable — and then say
    honestly that it costs more
  - a deliberate "we never update the copies, it is a snapshot"

No answer means the denormalization was accidental.
```

### The "SQL-style" schema: full normalization in MongoDB

Fully normalizing a MongoDB schema gives you the relational shape with none of the relational guarantees. SQL — the query language of relational databases — is the one place where copying the habits costs the most.

```txt
Symptom: users, posts, comments, tags, post_tags, post_stats —
all separate, documents hold only identifiers, and every page is
assembled from three or four $lookup stages, or five populate
calls.

Why this is the worst of both worlds:
  - joins exist but are worse than relational ones. $lookup runs
    as a sub-query per input document, with no hash join and no
    join-order choice by a planner (see article 05). populate in
    Mongoose is literally N+1 separate queries: one for the list
    of N parents, then one more per parent (see article 08).
  - integrity is still absent: there is no foreign key, no
    ON DELETE CASCADE and no cross-collection CHECK
  - transactions become necessary at every step, and here they
    cost more than in a relational database
  - the document model's flexibility is unused: you end up with a
    relational schema without relational guarantees and without a
    relational optimizer

What to do: either rebuild the schema around aggregates, and then
$lookup is no longer needed, or admit the data is relational and
take PostgreSQL — see article 01. The in-between state is the
most expensive one.
```

## The design procedure: how to answer at the whiteboard

Seven steps, in this order. Skipping the first one turns every later step into guesswork.

```txt
1. Write down the application's top-5 queries and their rates.
   Without this step any answer about embedding is guesswork.

2. For each relationship, determine cardinality in terms of
   few / many / squillions — and separately: is there an upper
   bound?

3. Decide embed or reference by the criteria: read together?
   needed independently? how often does it change?

4. Check the bounds: how large will the document be for the
   worst realistic case (a viral post, the biggest tenant)?

5. For every duplicate, name a synchronization plan, or state
   explicitly that it is a snapshot.

6. Check which indexes the resulting queries need (see article
   04) — a schema without indexes for its own queries is
   unfinished.

7. Name what changes if a requirement changes: "if independent
   comment pagination is needed, they are already in a separate
   collection; if the history of author names is needed, the
   Extended Reference becomes a snapshot".
```

And the main thing worth saying out loud: there is no correct answer to "embed or reference" in a vacuum. There is an answer for a specific set of queries, volumes and consistency requirements. "Comments are always embedded" and "always a reference" are both worse than naming the criterion and applying it to the case at hand.

## Connection to other topics

- **01 — Document Model and Use Cases.** The 16 MB limit, and single-document atomicity as the reason to design around aggregates.
- **02 — CRUD and Query Operators.** CRUD is create, read, update, delete. `$push`/`$slice` for Subset, `upsert` + `$inc` for Bucket, atomic `$inc` for Computed.
- **04 — Indexes and Query Performance.** Indexes for the resulting queries, multikey indexes over nested arrays, an index on `"author._id"` for syncing duplicates.
- **05 — Aggregation Pipeline.** `$lookup` as the price of referencing, and why embedding removes it.
- **06 — Replication, Transactions, and Consistency.** When divergence between duplicates is unacceptable: a transaction, and its cost.
- **08 — Mongoose Queries, populate, and Pitfalls.** `populate` as the most common way to get an accidental N+1 on a normalized schema.

## Common interview traps

- **"Comments always go inside the post — it's a document database"** — comments have no upper bound. One viral post hits the 16 MB limit, and long before that it hits a full document rewrite on every `$push`. The correct answer is a reference plus a Subset for the preview.

- **"Embedding is always faster"** — faster when reading the whole parent. Slower when updating one nested element of a large document, because the whole document is rewritten. And more expensive on queries that do not need the nested data at all.

- **"Referencing is how SQL does it, so it must be right"** — a normalized schema in MongoDB gives you the relational shape without the relational guarantees. You get `$lookup` instead of a planner, `populate` instead of a join, and no foreign keys. That is the worst of both worlds.

- **"Duplicating data is bad"** — in the document model duplication is a tool. What is bad is duplication with no answer to "who updates the copies and when, and what happens on a mid-way failure".

- **"16 MB is a lot, we'll never hit it"** — the limit is found on the worst real document, not the average one. Think of the most popular post, or the largest customer. And performance problems start at hundreds of kilobytes.

- **"Extended Reference is the same as embedding the whole document"** — the point is precisely to copy 2-3 fields for rendering, not the whole profile. You copy what rarely changes and is almost always read.

- **"The comment count can be computed with `countDocuments()` on read"** — on a feed of 20 posts that is 20 counts. The counter is stored and updated with an atomic `$inc`. Separately, you need a way to recompute it from the source of truth.

- **"$lookup solves relationships, so normalizing is fine"** — `$lookup` runs per input document and is not a planned join. It is acceptable for rare queries and reports, not for the main read path.

- **"I'd look at how a similar project did it"** — this question tests the ability to derive a schema from requirements. The answer has to start with the list of queries, not with a template.
