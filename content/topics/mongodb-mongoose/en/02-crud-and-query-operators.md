# CRUD and Query Operators

## A filter is a document, not a query string

MongoDB has no textual query language: the filter, the update and the projection are all BSON documents. One consequence often surprises people coming from SQL: a query is built like an ordinary object, so it is easy to assemble dynamically — and just as easy to assemble user input into it (`{ $ne: null }` instead of a string), which is why input must be validated.

```js
// The full set of read and write operations. Pluralization is the only
// difference in call shape: One works on the first matching document.
db.posts.insertOne({ title: "Indexes", authorId: userId })
db.posts.insertMany([{ ... }, { ... }])

db.posts.find({ authorId: userId })           // a cursor
db.posts.findOne({ slug: "mongodb-indexes" }) // a document or null

db.posts.updateOne({ _id: id }, { $set: { title: "New" } })
db.posts.updateMany({ authorId: userId }, { $set: { archived: true } })
db.posts.replaceOne({ _id: id }, { title: "New", authorId: userId })

db.posts.deleteOne({ _id: id })
db.posts.deleteMany({ archived: true })

// A separate family: atomically modify AND return the document
db.posts.findOneAndUpdate({ _id: id }, { $inc: { "stats.views": 1 } })
db.posts.findOneAndDelete({ _id: id })
db.posts.findOneAndReplace({ _id: id }, { ... })
```

```txt
What write operations return:
  insertOne   → { acknowledged, insertedId }
  updateOne   → { matchedCount, modifiedCount, upsertedId }
  deleteOne   → { acknowledged, deletedCount }

matchedCount ≠ modifiedCount: the document was found but $set wrote the
same value → matched 1, modified 0. Check exactly what you mean:
"the document did not exist" is matchedCount === 0, not
modifiedCount === 0.
```

## Query operators

```js
// Equality needs no operator: {field: value} is an implicit $eq
db.posts.find({ status: "published" })

// Comparison
db.posts.find({ "stats.views": { $gte: 100, $lt: 1000 } })  // both apply
db.posts.find({ status: { $in: ["published", "featured"] } })
db.posts.find({ status: { $nin: ["draft"] } })
db.posts.find({ status: { $ne: "draft" } })

// Field presence and type — a direct consequence of having no rigid schema
db.posts.find({ coverUrl: { $exists: false } })   // no such field at all
db.posts.find({ coverUrl: null })                 // no field OR field is null
db.posts.find({ publishedAt: { $type: "string" } })  // hunting for
                                                     // "broken" documents

// Logical operators
db.posts.find({ $or: [{ status: "published" }, { authorId: userId }] })
db.posts.find({ $and: [{ tags: "mongo" }, { tags: "perf" }] })  // see $all
db.posts.find({ tags: { $not: { $size: 0 } } })

// Regular expressions
db.posts.find({ slug: { $regex: "^mongodb-", $options: "i" } })
db.posts.find({ slug: /^mongodb-/ })   // the same thing, shorter
```

Two places where mistakes are easy:

```txt
{ coverUrl: null } ≠ { coverUrl: { $exists: false } }
  null matches BOTH documents without the field AND documents whose
  field is null. For a strict "field is missing": { $exists: false }.
  For a strict "present and null": { coverUrl: { $type: "null" } }.

$regex uses an index ONLY when anchored at the start and not
case-insensitive: /^mongodb-/ — yes, /^mongodb-/i and /indexes/ — no
(see [Indexes and Query Performance]). A "contains substring" search
over a large collection via $regex is a COLLSCAN; that needs a text
index or Atlas Search.
```

## Arrays: dot notation vs $elemMatch

An array in a filter behaves differently from what someone with SQL experience expects. A condition on an array field is satisfied if AT LEAST ONE element matches it — and each condition is evaluated independently of the others.

```js
// Array of scalars: a filter by value matches an element, not the array
db.posts.find({ tags: "mongodb" })              // has that tag
db.posts.find({ tags: ["mongodb", "perf"] })    // the array EQUALS exactly
                                                // this, same order
db.posts.find({ tags: { $all: ["mongodb", "perf"] } })  // contains both
db.posts.find({ tags: { $size: 3 } })           // exactly 3 elements
db.posts.find({ "tags.0": "mongodb" })          // the first element
```

With an array of objects the classic interview trap begins:

```txt
       Dot notation on an array checks conditions INDEPENDENTLY
┌───────────────────────────────────────────────────────────────────┐
│ a document in the posts collection:                               │
│ { _id: 1, ratings: [ { userId: "a", score: 5 },                   │
│                      { userId: "b", score: 2 } ] }                │
├───────────────────────────────────────────────────────────────────┤
│ { "ratings.score": { $gte: 4 } }                                  │
│   → MATCH: at least one element has score >= 4                    │
├───────────────────────────────────────────────────────────────────┤
│ { "ratings.userId": "b", "ratings.score": { $gte: 4 } }           │
│   → MATCH, and this is the trap: the conditions are met by        │
│     DIFFERENT elements — userId by the second, score by the first │
├───────────────────────────────────────────────────────────────────┤
│ { ratings: { $elemMatch: { userId: "b", score: { $gte: 4 } } } }  │
│   → NO MATCH: ONE element must satisfy both conditions            │
│     (which is what people usually mean)                           │
└───────────────────────────────────────────────────────────────────┘
rule: two or more conditions on the same array element always need $elemMatch
```

The practical rule: one condition on an array — dot notation; two or more conditions that must hold for the SAME element — `$elemMatch`. The same operator is needed when there is one condition but it is compound:

```js
// A range on a single element: without $elemMatch this means "some
// element is >= 4 AND some element is <= 5", possibly different ones
db.posts.find({ ratings: { $elemMatch: { score: { $gte: 4, $lte: 5 } } } })
```

## Update operators

The second argument of `updateOne` is not a new document but a set of instructions. A field not mentioned in the instructions stays as it was.

```js
// Scalar fields
{ $set:    { title: "New", "stats.views": 0 } }  // dot notation creates
                                                 // the nesting
{ $unset:  { coverUrl: "" } }        // remove the field (value ignored)
{ $inc:    { "stats.views": 1, "stats.likes": -1 } }  // atomic increment
{ $mul:    { price: 1.2 } }
{ $min:    { lowestPrice: 42 } }     // write only if lower than current
{ $max:    { peakViews: 1200 } }
{ $rename: { body: "content" } }
{ $currentDate: { updatedAt: true } }
{ $setOnInsert: { createdAt: new Date() } }   // only on an upsert insert

// Arrays
{ $push:     { tags: "mongodb" } }
{ $push:     { comments: { $each: [c1, c2], $sort: { createdAt: -1 },
                           $slice: 20 } } }   // append, sort and keep 20
                                              // in a single step
{ $addToSet: { tags: "mongodb" } }   // append if not present
{ $pull:     { tags: "legacy" } }    // remove by condition
{ $pull:     { comments: { authorId: bannedId } } }
{ $pop:      { tags: 1 } }           // 1 — last, -1 — first
```

The `$push` + `$slice` + `$sort` combination is the working answer to unbounded array growth: the document keeps only the last N elements (see [Schema Design: Embedding vs Referencing], the Subset pattern).

There are three positional operators for updating an element inside an array:

```js
// $ — the FIRST element matched by the query filter
db.posts.updateOne(
  { _id: postId, "comments._id": commentId },
  { $set: { "comments.$.body": "edited" } }
)
// requirement: the array field must appear in the FILTER, otherwise you
// get "The positional operator did not find the match"

// $[] — ALL elements of the array
db.posts.updateMany({}, { $set: { "comments.$[].moderated": false } })

// $[ident] — every element matched by arrayFilters
db.posts.updateOne(
  { _id: postId },
  { $set: { "comments.$[c].hidden": true } },
  { arrayFilters: [{ "c.score": { $lt: -5 } }] }
)
```

`$` updates only the first matched element — if three match, one is updated. That is another reason to give nested objects their own `_id`: an exact match instead of "the first similar one".

## updateOne vs replaceOne

```js
// updateOne — a partial update: other fields are untouched
db.posts.updateOne({ _id: id }, { $set: { title: "New" } })

// replaceOne — the WHOLE document is replaced by the one passed (except _id)
db.posts.replaceOne({ _id: id }, { title: "New" })
// → authorId, tags, stats, createdAt are GONE from the document
```

```txt
The classic bug: PUT /posts/:id that writes req.body through replaceOne
(or through an update with no operators — drivers treat an
operator-less document as a replace). The client sent { title }, and
authorId and createdAt disappeared from the document. Later the post
page breaks on a missing author, and the cause is looked for in the
read path, not the write path.

Rule: REST PUT semantics ≠ replaceOne. Even for PUT, a $set over an
explicit allowlist of fields is safer than replacing the document with
the request body.
```

## upsert and its race condition

`upsert: true` means: if the filter matched nothing, insert a document. The new document is assembled from the equality fields of the filter plus the update instructions.

```js
db.postStats.updateOne(
  { postId: postId, day: "2026-08-13" },        // equalities → they go
                                                // into the new document
  {
    $inc: { views: 1 },                          // 1 on insert
    $setOnInsert: { createdAt: new Date() }      // only on insert
  },
  { upsert: true }
)
// inserts { postId, day, views: 1, createdAt } or increments the existing
// one — in a single round-trip, with no "find first, then decide"
```

Note that only equalities make it into the new document: a filter like `{ views: { $gt: 5 } }` contributes nothing — comparison operators are ignored on insert.

```txt
Race condition. Upsert is NOT atomic as "check and insert" if there is
no unique index:

  A: did not find { postId, day } → decides to insert
  B: did not find { postId, day } → decides to insert
  → two documents in the collection for one (postId, day) pair

A unique index is the only real protection:
  db.postStats.createIndex({ postId: 1, day: 1 }, { unique: true })

With it the second upsert gets a duplicate key error (E11000). That is
an EXPECTED outcome, not a failure: the server itself retries a single
upsert, and application code keeps the "catch E11000 → retry once"
pattern (see [Mongoose Queries, populate, and Pitfalls] on mapping
E11000 to an API error).
```

## Projections: read only what you need

```js
// Inclusion: _id is always returned unless excluded explicitly
db.posts.find({ authorId: userId }, { title: 1, slug: 1, _id: 0 })

// Exclusion: everything except the listed fields
db.users.find({}, { passwordHash: 0, tokens: 0 })

// Inclusion and exclusion CANNOT be mixed (except for _id):
db.posts.find({}, { title: 1, body: 0 })   // → error

// Array projections
db.posts.find({}, { comments: { $slice: 5 } })        // first 5
db.posts.find({}, { comments: { $slice: -5 } })       // last 5
db.posts.find({ "comments.authorId": userId },
              { "comments.$": 1 })                     // first match
db.posts.find({}, { comments: { $elemMatch: { score: { $gt: 10 } } } })
```

A projection is not only about less traffic: if every field needed is present in the index, the query can be answered without touching the documents at all (a covered query, see [Indexes and Query Performance]). And the reverse — the habit of pulling the whole document in Mongoose also costs object hydration (see [Mongoose Queries, populate, and Pitfalls] on `lean()`).

## Cursors and batching

`find` does not return data — it returns a cursor. Documents arrive in batches: the first one with the query reply, the rest via `getMore`.

```txt
find → the server prepares a cursor and returns the first batch
       (101 documents or ~16 MB, whichever comes first)
       ↓
the driver hands documents to the application one by one
       ↓
batch exhausted → getMore → next batch (up to 16 MB by default)
       ↓
cursor exhausted → closed automatically

An idle cursor lives for 10 minutes, then the server closes it
("cursor id not found" in the logs usually means slow batch processing
in the application, or a cursor that was never closed).
```

```js
// Node.js driver: iterate without loading the whole result set in memory
const cursor = db.collection("posts").find({ status: "published" });
for await (const post of cursor) {
  await handle(post);         // documents arrive in batches, memory is flat
}

// toArray() materializes the ENTIRE result set into an array — on a large
// collection that is an OOM. Acceptable only after an explicit limit.
const page = await db.collection("posts").find(f).limit(20).toArray();

// batchSize controls the batch size — useful when processing a single
// document is slow (otherwise the cursor sits idle and "ages")
db.collection("posts").find(f).batchSize(50);
```

Pagination via `skip` looks convenient and degrades linearly: `skip(100000)` makes the server walk and throw away 100,000 documents. For an infinite feed the right tool is keyset pagination on `_id`, or on the (`sort` field, `_id`) pair — all the more so because sorting by `_id` nearly matches sorting by creation time (see [Document Model and Use Cases]).

```js
// instead of .skip(pageSize * n).limit(pageSize)
db.posts.find({ _id: { $lt: lastSeenId } }).sort({ _id: -1 }).limit(20)
```

## Single-document atomicity is the fundamental guarantee

Any write operation on a SINGLE document is atomic: either all of its changes apply, or none do. That holds for several fields, nested objects and array elements at once — and requires no transaction.

```js
// One atomic step: three fields and an array element change together.
// No reader will ever see the state "comment added but the counter is
// still the old one".
db.posts.updateOne(
  { _id: postId },
  {
    $push: { comments: { _id: new ObjectId(), body, authorId } },
    $inc:  { "stats.comments": 1 },
    $currentDate: { updatedAt: true }
  }
)
```

The boundaries of the guarantee must be stated precisely:

```txt
Atomic:              one operation on one document
NOT atomic:          updateMany over 100 documents — that is 100 separate
                     atomic operations; a reader in between sees half of
                     them updated
NOT atomic:          two operations in a row in application code
                     (even on the same document)
For everything else: multi-document transactions
                     (see [Replication, Transactions, and Consistency])
```

Hence the main practical consequence: read-modify-write in application code is a race, and `findOneAndUpdate` is not.

```txt
 Lost update: read-modify-write in application code
┌──────┬─────────────────────┬─────────────────────┐
│ step │ process A           │ process B           │
├──────┼─────────────────────┼─────────────────────┤
│ 1    │ find: views = 100   │                     │
├──────┼─────────────────────┼─────────────────────┤
│ 2    │                     │ find: views = 100   │
├──────┼─────────────────────┼─────────────────────┤
│ 3    │ update: views = 101 │                     │
├──────┼─────────────────────┼─────────────────────┤
│ 4    │                     │ update: views = 101 │
└──────┴─────────────────────┴─────────────────────┘
two increments, result is 101 instead of 102 — one is lost
findOneAndUpdate({ _id }, { $inc: { views: 1 } }) — one atomic step: 102
```

`findOneAndUpdate` is an atomic read-modify-write: the server finds the document, applies the update and returns its version either before or after the change. That is exactly why it so often covers cases where SQL would reach for a transaction with `SELECT FOR UPDATE`.

```js
// 1. An atomic counter that returns the new value
const post = await db.collection("posts").findOneAndUpdate(
  { _id: postId },
  { $inc: { "stats.views": 1 } },
  { returnDocument: "after" }        // "before" — the old version (default)
);

// 2. Compare-and-set: the condition lives in the FILTER, not in the code.
//    If the status changed in the meantime, no document is found — and
//    that is the answer.
const claimed = await db.collection("jobs").findOneAndUpdate(
  { _id: jobId, status: "pending" },              // the precondition
  { $set: { status: "running", startedAt: new Date() } },
  { returnDocument: "after" }
);
if (!claimed) throw new ConflictError("job already claimed");

// 3. A job queue without an external broker: workers compete, but exactly
//    one gets the job — the server serializes writes per document
const job = await db.collection("jobs").findOneAndUpdate(
  { status: "pending", runAt: { $lte: new Date() } },
  { $set: { status: "running", workerId } },
  { sort: { runAt: 1 }, returnDocument: "after" }
);

// 4. The "never go negative" invariant — also in the filter
const ok = await db.collection("accounts").findOneAndUpdate(
  { _id: accountId, balance: { $gte: amount } },
  { $inc: { balance: -amount } }
);
if (!ok) throw new InsufficientFundsError();
```

The general technique: move the check out of the code and into the query filter. Then the "apply or not" decision is made by the server at write time, not by the application from a stale copy of the document. Optimistic locking is the same technique with a version field; in Mongoose that is `__v` (see [Mongoose Queries, populate, and Pitfalls]).

Bulk operations of mixed shape are covered by `bulkWrite`, and its `ordered` flag is worth understanding:

```js
await db.collection("posts").bulkWrite([
  { insertOne: { document: { title: "A" } } },
  { updateOne: { filter: { _id: id }, update: { $set: { views: 0 } } } },
  { deleteOne: { filter: { archived: true } } }
], { ordered: false });
// ordered: true (default) — in order, stops at the first error
// ordered: false — executed in parallel on the server, errors are
//                  collected and returned together; faster, but the order
//                  is not guaranteed. Neither mode makes the batch atomic
//                  — each individual element is atomic.
```

## Connection to other topics

```txt
[Document Model and Use Cases]    — why a filter is a document, BSON
                                    types in queries, _id
[Schema Design: Embedding vs      — $push/$slice against unbounded array
 Referencing]                       growth, _id on nested objects
[Indexes and Query Performance]   — which filters can use an index,
                                    covered queries, $regex and $ne
[Aggregation Pipeline]            — when find filters are not enough:
                                    grouping, computed fields, $lookup
[Replication, Transactions, and   — what to do when single-document
 Consistency]                       atomicity is not enough; write concern
[Mongoose Queries, populate,      — findOneAndUpdate in Mongoose,
 and Pitfalls]                      returnDocument, __v, E11000
```

## Common interview traps

- **"MongoDB has no atomicity"** — atomicity exists and it is fundamental: any operation on a SINGLE document is atomic, including changes to several fields and arrays. The false claim is a different one: that `updateMany` or two consecutive operations are atomic.

- **"`{ "ratings.userId": "b", "ratings.score": { $gte: 4 } }` finds an element matching both conditions"** — the conditions are checked independently and may be satisfied by different array elements. That needs `$elemMatch`.

- **"`updateOne` without operators updates the fields passed"** — a document with no operators is treated as a replacement; missing fields disappear. A deliberate replacement is `replaceOne`.

- **"`upsert` protects against duplicates"** — without a unique index, two concurrent upserts insert two documents. The index protects; upsert only removes the "find first, then insert" round-trip.

- **"`matchedCount === 0` and `modifiedCount === 0` are the same"** — a `$set` of the same value gives `matched: 1, modified: 0`. "Not found" is checked via `matchedCount`.

- **"`{ field: null }` finds documents without the field"** — it finds both those without the field and those with `null`. A strict "field is missing" is `$exists: false`.

- **"I'll read the document first, compute the new value and write it back"** — the classic lost update. The correct way: `$inc`/`$push` in a single operation, or `findOneAndUpdate` with the condition in the filter.

- **"`toArray()` is the normal way to get results"** — on a large result set that loads the whole collection into process memory. The standard way is iterating the cursor; `toArray()` comes after a `limit`.

- **"`skip`/`limit` is fine for pagination"** — `skip` gets linearly more expensive with the page number. Feeds need keyset pagination on `_id` or on the (`sort` field, `_id`) pair.
