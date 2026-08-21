# Mongoose Queries, populate, and Pitfalls

## A Query is an object, not a promise

`Model.find()` returns not a promise but a `Query` object you can keep building. The request only reaches the server on `await` or `.exec()`.

```typescript
// The chain is built lazily — the query has not run yet
const query = PostModel.find({ status: 'published' })
  .where('stats.views').gte(100)
  .select('title slug author stats.views')
  .sort({ publishedAt: -1 })
  .limit(20)
  .lean();

const posts = await query.exec();   // this is where the database is hit
```

```typescript
// The practical benefit: a dynamic filter without merging objects
function buildPostsQuery(f: PostFilter) {
  const q = PostModel.find({ status: 'published' });
  if (f.tag)     q.where({ tags: f.tag });
  if (f.author)  q.where({ 'author._id': f.author });
  if (f.since)   q.where('publishedAt').gte(f.since);
  return q.sort({ publishedAt: -1 }).limit(f.limit ?? 20);
}
```

```txt
Two things about Query:

1. await and .exec() do the same thing, but exec() returns a real
   promise and gives a more useful stack trace on error. In code where
   diagnostics matter, prefer .exec().

2. A single Query cannot be executed twice: awaiting the same object
   again throws "Query was already executed". That catches a real bug —
   reusing a "query template" as a variable. A template must be a
   function, not an object.
```

## populate is **not** $lookup: it is extra queries

`populate` fills a reference field with the referenced document. It looks like a join, and it is not one. The join happens in your Node process, after Mongoose has fetched the related documents with a second query.

```txt
    populate is separate queries, not a server-side $lookup
┌──────────────────────────────────────────────────────────────┐
│ PostModel.find().limit(20).populate("author._id")            │
│   query 1: db.posts.find(...).limit(20)                      │
├──────────────────────────────────────────────────────────────┤
│ Mongoose collects every authorId from the 20 documents       │
│   query 2: db.users.find({ _id: { $in: [ ...20 ids... ] } }) │
├──────────────────────────────────────────────────────────────┤
│ stitching in the Node process memory:                        │
│   post.author._id = the matching user document               │
└──────────────────────────────────────────────────────────────┘
    20 posts = 2 queries, not 21 — but still two round-trips
        a nested populate adds one more query per LEVEL
```

```typescript
// A schema with a reference
const commentSchema = new Schema<Comment>({
  postId: { type: Schema.Types.ObjectId, ref: 'Post', required: true },
  author: { type: Schema.Types.ObjectId, ref: 'User', required: true },
  body:   { type: String, required: true },
});

// populate with options
const comments = await CommentModel.find({ postId })
  .populate({
    path: 'author',
    select: 'name avatar',        // fetch only the fields you need
    match: { banned: { $ne: true } },   // ← read the trap below
  })
  .limit(50)
  .lean();
```

The key fact: `populate` is not a server-side join but **extra queries** whose results Mongoose stitches together in the process memory. Four practical consequences follow.

```txt
1. One populate over a list is ONE extra query, not N. Mongoose
   collects all the ids and issues an $in. The common claim
   "populate = N+1" is wrong in the basic case — which is exactly why
   an interview answer should explain the mechanics rather than repeat
   the meme.

2. N+1-like effects appear in specific cases. N+1 means one query for
   a list of N items, plus one more query per item — N+1 round-trips
   where two would do. The cases:
   - a nested populate: populate({ path: 'comments',
     populate: { path: 'author' } }) — one query PER nesting level
   - populate inside a loop over documents (populate called per
     object) — that is a genuine N+1
   - populate with perDocumentLimit: to give "3 comments PER post"
     Mongoose must run a separate query for every parent document
   - populate in GraphQL resolvers without batching

3. options: { limit: 3 } in populate is a TOTAL limit on the whole
   $in query, not "3 per document". The classic surprise: the first
   post has three comments and the rest have none. "3 per each" is
   perDocumentLimit, and it is expensive.

4. match filters the RELATED documents but does not remove the parent:
   if the author is banned, the post is returned with author: null.
   populate cannot filter parents by a property of the related
   document at all — that needs $lookup + $match or a denormalized
   field on the parent.
```

```typescript
// Virtual populate: a "top-down" relation without an id array on the parent
postSchema.virtual('comments', {
  ref: 'Comment',
  localField: '_id',
  foreignField: 'postId',
  justOne: false,
});

// The count only, without loading the documents
postSchema.virtual('commentCount', {
  ref: 'Comment',
  localField: '_id',
  foreignField: 'postId',
  count: true,
});

const post = await PostModel.findById(id).populate('comments');
```

Virtual populate is convenient and dangerous at once. `foreignField` must be indexed. Otherwise every such populate is a `COLLSCAN` over the child collection. `COLLSCAN` is the stage name in a query plan that means "no index was used, the whole collection was read". Indexes and query performance are the subject of their own article.

And `count: true` recounts every time. A hot screen needs a stored counter instead: the Computed pattern from the Schema Design article.

```txt
             Three ways to get related data
┌──────────────────────────────────────────────────────┐
│ populate                                             │
│                                                      │
│ where it runs       Node + N queries                 │
│ round-trips         2 or more                        │
│ filter on related   match, parent still returned     │
│ cost                network and Node memory          │
│ when it fits        admin panels, rare screens       │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│ $lookup                                              │
│                                                      │
│ where it runs       on the server                    │
│ round-trips         1                                │
│ filter on related   fully, inside the pipeline       │
│ cost                a nested loop                    │
│ when it fits        reports and aggregations         │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│ redesign the schema                                  │
│                                                      │
│ where it runs       nowhere: already in the document │
│ round-trips         1                                │
│ filter on related   a plain find                     │
│ cost                duplicates need syncing          │
│ when it fits        the hot read path                │
└──────────────────────────────────────────────────────┘
     if populate sits in your most frequent query,
        the problem is the schema, not populate
```

A separate note on integrity: `populate` returns `null` if the referenced document was deleted. MongoDB has no foreign keys and no cascades. A foreign key (FK) is the relational constraint that makes the database itself refuse a reference to a row that does not exist.

Dangling references are therefore a normal state of the database, and the code has to survive them. An `if (!post.author) ...` check is not paranoia but a required branch.

## lean(): what hydration costs

Without `lean()` Mongoose turns every document in the response into a full `Document`: setters, getters, change tracking, virtuals, methods, built-in validation. For a list of 500 objects that is noticeable work wasted if the objects only go into JSON.

```typescript
// A hydrated document: has save(), virtuals, methods
const post = await PostModel.findById(id);
post.title = 'new';
await post.save();

// lean: a plain old JavaScript object, far cheaper in memory and CPU
const posts = await PostModel.find({ status: 'published' })
  .select('title slug author')
  .lean<Pick<Post, '_id' | 'title' | 'slug' | 'author'>[]>()
  .exec();
// posts[0].save  → undefined: this is NOT a document
```

```txt
What you lose along with hydration:
  - save(), document methods, markModified
  - virtuals (if needed — lean({ virtuals: true }) in recent versions,
    or compute them in code)
  - schema getters/setters: the value arrives exactly as stored
  - application of defaults to fields missing from the document

What you do NOT lose:
  - populate works with lean()
  - projections, sorts, indexes — all unchanged

The rule: any "read and return" query gets lean(). Any "modify and
save" query does not. The cleanest way to keep them apart in a
repository is separate methods: findForRead() and findForUpdate().
```

On typing: `lean()` changes the result type, and it must not be confused with `HydratedDocument`. The generic on `lean<T>()` is the simplest way to describe the real shape, especially with `select`.

And `_id` in that shape stays a `Types.ObjectId` until you explicitly serialize it to a string at the API boundary. The article on Mongoose schemas, models and validation covers that boundary.

## findOneAndUpdate: the behaviour you have to know

```typescript
const post = await PostModel.findOneAndUpdate(
  { _id: id, status: 'draft' },                 // the precondition
  { $set: { status: 'published', publishedAt: new Date() } },
  {
    returnDocument: 'after',   // 'before' is the DEFAULT!
    runValidators: true,       // otherwise validation does NOT run
    upsert: false,
    projection: { title: 1, status: 1 },
  },
);
if (!post) throw new ConflictError('post not found or already published');
```

```txt
What matters:

  - returnDocument defaults to 'before': you get the state as it was
    BEFORE the change, not after it. The old alias new: true does the
    same as returnDocument: 'after' — in new code use returnDocument
  - runValidators must be requested explicitly, and even then required
    is not checked for fields absent from the update (see the article
    on Mongoose schemas, models and validation)
  - document middleware (pre/post 'save') is NOT called — this is a
    query operation
  - null means "nothing matched the filter". That is part of the API,
    not an error: it is exactly how compare-and-set is implemented
    (see the CRUD and Query Operators article)
  - upsert + setDefaultsOnInsert: schema defaults are applied on
    insert (the default behaviour in current Mongoose versions), but
    it is worth verifying on your version
```

```txt
How to choose between findOneAndUpdate and save():

  findOneAndUpdate — when ATOMICITY matters and the condition can be
  expressed as a filter: counters, status changes, claiming a job,
  checking a balance. One round-trip, no race.

  save() — when the DOCUMENT'S HOOKS AND VALIDATION matter: password
  hashing, invariants across fields, auditing via post('save'). The
  cost: a read plus a write, with someone else's write able to slip in
  between.

  The mixed option that is often what you actually want: write through
  findOneAndUpdate and keep invariants in explicit domain functions
  instead of relying on schema magic.
```

## versionKey `__v` and optimistic concurrency

`__v` is the version field Mongoose adds to every document, and it is far weaker than the name "optimistic locking" suggests. It guards array positions, not arbitrary field changes.

```txt
What __v is: a version field Mongoose adds to the document. It is NOT
incremented on every save() — only when an operation could conflict
over array positions (for example $push/$pull change element indexes).

The mechanics: on save() Mongoose adds __v to the update filter. If
the document changed in the meantime, the update matches nothing and
Mongoose throws a VersionError.

What it is NOT: a full optimistic lock over any change. A title field
can be overwritten on top of someone else's edit with no error at all.
```

```typescript
// Explicit optimistic concurrency at the schema level (Mongoose 5.10+)
const postSchema = new Schema<Post>({ ... }, {
  optimisticConcurrency: true,   // __v is checked on EVERY save()
});

// Or by hand, without Mongoose magic — the version in the filter
const res = await PostModel.updateOne(
  { _id: id, version: expectedVersion },
  { $set: { ...changes }, $inc: { version: 1 } },
);
if (res.matchedCount === 0) throw new ConflictError('document changed');
```

The second variant is the same "condition in the filter" technique as in the article on CRUD (create, read, update, delete) and query operators. It works without Mongoose, it is visible in the code, and it does not depend on the library version.

## Connections: the pool, buffering and serverless

Mongoose keeps a pool of open connections inside the process and reuses them, so `connect()` belongs at application startup and nowhere else. The settings below are the ones that actually change behaviour under load.

```typescript
await mongoose.connect(process.env.MONGO_URL!, {
  maxPoolSize: 20,                 // connection pool size
  minPoolSize: 2,
  serverSelectionTimeoutMS: 5000,  // how long to wait for a suitable member
  socketTimeoutMS: 45000,
});

mongoose.connection.on('error', (err) => logger.error({ err }, 'mongo error'));
mongoose.connection.on('disconnected', () => logger.warn('mongo disconnected'));
```

```txt
The connection pool lives in the process and is reused: connect() is
called ONCE at application startup, not inside a request handler. A
second connect() to the same URI is reused by Mongoose, but code that
"connects per request" usually means a connection leak somewhere
nearby.

Pool size: too small and queries queue up (visible as rising latency
with unchanged database load); too large across N instances and you
hit the cluster's connection limit (in Atlas that depends on the tier).
```

Command buffering is a mechanism that masks problems more often than it helps:

```txt
While the connection is not established, Mongoose does NOT throw
immediately: it BUFFERS operations (bufferCommands: true by default)
and waits up to bufferTimeoutMS (10 seconds). The production symptom
is requests that "hang" for ten seconds and then fail with

  MongooseError: Operation `posts.find()` buffering timed out
  after 10000ms

The danger is that the real cause — an unreachable cluster, a wrong
URI, an IP missing from the allowlist — turns into an obscure timeout
ten seconds after startup. What to do:

  - the application healthcheck verifies
    mongoose.connection.readyState === 1
  - do not accept traffic until the connection is established
  - in critical services: bufferCommands: false — then an operation
    without a connection fails IMMEDIATELY with a clear error
  - log connection events, not only query errors
```

```typescript
// Serverless / Next.js: the connection is cached across invocations
// in globalThis, otherwise every hot reload or cold start creates a
// new pool
const globalForMongoose = globalThis as unknown as {
  mongooseConn?: Promise<typeof mongoose>;
};

export function getConnection() {
  if (!globalForMongoose.mongooseConn) {
    globalForMongoose.mongooseConn = mongoose.connect(process.env.MONGO_URL!, {
      maxPoolSize: 5,          // in serverless the pool is kept small:
                               // many instances, one cluster limit
    });
  }
  return globalForMongoose.mongooseConn;
}
```

## autoIndex: why production turns it off

`autoIndex` makes Mongoose create every index declared in every schema when the application starts. That is convenient in development and wrong in production. It moves index builds into the deploy, and it lets a schema edit change production indexes with no review.

```typescript
await mongoose.connect(url, {
  autoIndex: false,      // do not create indexes automatically
  autoCreate: false,     // and do not create collections
});
```

```txt
By default autoIndex: true — at application startup Mongoose calls
createIndex for EVERY index declared in the schemas. In development
that is convenient. In production there are three problems:

1. Building an index on a large collection is a noticeable load, and
   it will happen at deploy time — the worst possible moment (see
   the Indexes and Query Performance article).

2. With N service instances you get N concurrent attempts to create
   the same index: the server handles it, but the wasted work and the
   confusing logs are guaranteed.

3. Index changes happen implicitly: someone edited a schema and an
   index appeared in production with no review and no plan.

The right process: autoIndex disabled, indexes applied deliberately by
a migration script in the deploy pipeline.
```

```typescript
// Deliberate index synchronization — a separate deploy step
await PostModel.syncIndexes();
// WARNING: syncIndexes DROPS indexes that are not in the schema.
// An index created by hand for a report will disappear. For an audit,
// use:
const diff = await PostModel.diffIndexes();   // what would be created/dropped
```

A separate trap ties this section to the article on Mongoose schemas, models and validation: `unique: true` in a schema is an index declaration. With `autoIndex: false` and no migration the index is never created. That means **there is no uniqueness at all**, even though the code looks like there is. Unique indexes must be in the migration.

## Error handling: mapping to the API response

Mongoose and the driver throw six errors that matter, and each one has a correct HTTP status. Most of them are expected outcomes rather than failures, so returning 500 for all of them turns a normal API contract into a pager alert.

```txt
  Mongoose/driver errors → the API response
┌───────────────────────────────────────────┐
│ ValidationError                           │
│                                           │
│ cause      the schema rejected the values │
│ response   400 + field list               │
└───────────────────────────────────────────┘
┌───────────────────────────────────────────┐
│ CastError                                 │
│                                           │
│ cause      invalid input: a bad ObjectId  │
│ response   400                            │
└───────────────────────────────────────────┘
┌───────────────────────────────────────────┐
│ E11000 (code 11000)                       │
│                                           │
│ cause      a unique index was violated    │
│ response   409 + field name               │
└───────────────────────────────────────────┘
┌───────────────────────────────────────────┐
│ VersionError                              │
│                                           │
│ cause      the document changed meanwhile │
│ response   409, ask for a refetch         │
└───────────────────────────────────────────┘
┌───────────────────────────────────────────┐
│ buffering timed out                       │
│                                           │
│ cause      no connection to the database  │
│ response   503                            │
└───────────────────────────────────────────┘
┌───────────────────────────────────────────┐
│ MongoServerSelectionError                 │
│                                           │
│ cause      the cluster is unreachable     │
│ response   503                            │
└───────────────────────────────────────────┘
    without this mapping all of it becomes
          a 500 and a useless alert
```

```typescript
import mongoose from 'mongoose';

interface ApiError { status: number; code: string; details?: unknown }

export function mapMongoError(e: unknown): ApiError {
  // Unique index violation: take the field from the driver error
  if (typeof e === 'object' && e !== null && (e as any).code === 11000) {
    const key = Object.keys((e as any).keyPattern ?? {})[0] ?? 'field';
    return { status: 409, code: 'DUPLICATE', details: { field: key } };
  }

  if (e instanceof mongoose.Error.ValidationError) {
    return {
      status: 400,
      code: 'VALIDATION',
      details: Object.entries(e.errors).map(([path, err]) => ({
        path,
        message: err.message,
      })),
    };
  }

  if (e instanceof mongoose.Error.CastError) {
    return { status: 400, code: 'BAD_INPUT', details: { path: e.path } };
  }

  if (e instanceof mongoose.Error.VersionError) {
    return { status: 409, code: 'CONFLICT' };
  }

  if (e instanceof mongoose.Error.MongooseServerSelectionError) {
    return { status: 503, code: 'DB_UNAVAILABLE' };
  }

  return { status: 500, code: 'INTERNAL' };
}
```

```txt
Why this is worth doing explicitly:

  - E11000 is an EXPECTED path, not a failure: two users register with
    the same email, an upsert race (see the CRUD and Query Operators
    article). A 409 with the field name is a normal API contract;
    a 500 is a lost alert and an incomprehensible client error
  - a CastError comes from a malformed URL parameter: that is a 400,
    and it should not be logged as an incident
  - code 11000 comes from the DRIVER, not from Mongoose: it is not an
    instanceof mongoose.Error, so it has to be checked via e.code.
    People forget that, and E11000 falls through to a 500
  - do not expose the driver's e.message: it can contain the key value
    (an email), which leaks data through the API response
```

## Connection to other topics

```txt
CRUD and Query Operators        — what findOneAndUpdate does at the
                                  server level; upsert and E11000;
                                  a condition in the filter instead
                                  of a lock
Schema Design: Embedding vs     — why populate on the hot path is a
Referencing                       question about the schema;
                                  Computed instead of count: true
Indexes and Query Performance   — the foreignField index for virtual
                                  populate; building indexes in
                                  production; covered queries
                                  and lean()
Aggregation Pipeline            — $lookup as the alternative to
                                  populate, and its cost
Replication, Transactions, and  — sessions and transactions in
Consistency                       Mongoose, retryable writes at the
                                  driver level
Mongoose: Schemas, Models, and  — where validation and hooks run
Validation                        and where they do not; unique
                                  as an index
```

## Common interview traps

- **"`populate` is `$lookup` in Mongoose"** — it is separate queries plus stitching in Node memory. One populate over a list = one extra query via `$in`; `$lookup` runs on the server.

- **"`populate` always causes N+1"** — not in the basic case. N+1 means one query for a list of N items plus one more query per item, so N+1 database round-trips instead of two. It appears with nested populate, populate inside a loop over documents, and with `perDocumentLimit`. In an interview it is valuable to explain exactly where the extra query comes from.

- **"`options: { limit: 3 }` in populate gives 3 related documents per parent"** — it is a total limit on the whole `$in` query. The first parent gets three, the rest get none. "3 per each" is `perDocumentLimit`, and it runs a query per document.

- **"`match` in populate filters the parents"** — it does not: the parent comes back with `null` in the related field. Filtering a parent by a related document's property means `$lookup` + `$match` or a denormalized field.

- **"`lean()` is a micro-optimization"** — on lists it is a several-fold difference in processor time and memory, because hydration of every document is skipped. Any read-only path should be `lean()`.

- **"`findOneAndUpdate` returns the updated document"** — by default `returnDocument: 'before'`, which is the state as it was **before** the change. `'after'` has to be requested explicitly.

- **"`__v` is optimistic locking"** — `__v` is not incremented on every `save()`, and a plain field overwrite raises no conflict. Real locking is `optimisticConcurrency: true` or your own version field in the filter.

- **"The query is just slow"** (when it fails after 10 seconds with `buffering timed out`) — it is not a slow query but a missing connection. The command sat in Mongoose's buffer. Diagnose with `readyState`, connection events and a healthcheck.

- **"`autoIndex` can stay on, it is convenient"** — in production that means building indexes at deploy time, races between instances and implicit changes. Indexes are applied by a migration; note that `syncIndexes()` **drops** anything not in the schema.

- **"`unique: true` in the schema guarantees uniqueness"** — only if the index was actually created. With `autoIndex: false` and no migration there is no guarantee at all.

- **"Mongo errors are 500s"** — `E11000` is a 409, `ValidationError` and `CastError` are 400s, an unreachable cluster is a 503. And `E11000` comes from the driver, so it is not caught by `instanceof mongoose.Error`.
