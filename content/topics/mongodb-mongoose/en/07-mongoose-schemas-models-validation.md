# Mongoose: Schemas, Models, and Validation

## What Mongoose adds to the driver — and at what cost

Mongoose is not a standalone client but a layer on top of the official `mongodb` driver. It brings back into the code what MongoDB does not require: a declared schema, type casting, validation and hooks.

```txt
What exactly Mongoose adds between your code and the server
┌───────────────────────────────────────────────────────┐
│ application code: services, controllers               │
├───────────────────────────────────────────────────────┤
│ Mongoose: Schema · type casting · validation · hooks  │
│ virtuals · methods/statics · populate · query builder │
│ hydration of results into Document wrappers           │
├───────────────────────────────────────────────────────┤
│ the official Node.js driver: BSON, connection pool,   │
│ topology monitoring, retryable writes, sessions       │
├───────────────────────────────────────────────────────┤
│ mongod / mongos: indexes, query plan, replication     │
└───────────────────────────────────────────────────────┘
every line of the Mongoose layer is a convenience with a behavioural cost
```

```txt
What you get:
  + a schema as the single source of truth about document shape — the
    very schema that in MongoDB "lives in the code" (see [Document
    Model and Use Cases])
  + automatic type casting: "42" from a query string becomes a number,
    a date string becomes a Date, an id string becomes an ObjectId
  + validation before writes, and clear errors instead of garbage in
    the database
  + middleware: one place for password hashing, auditing, soft delete
  + virtuals, methods, statics — behaviour next to the data
  + populate and a chainable query builder

What you pay:
  - a query result is not a database document but a Document wrapper:
    getters/setters, change tracking, validation. That is memory and
    CPU per object (cured by lean() — see [Mongoose Queries, populate,
    and Pitfalls])
  - "hidden magic": some mechanisms do not run where you expect them
    to (validation and pre('save') on update operations — the main
    theme of this article)
  - one more layer while debugging: between your call and the server
    query there is a transformation you have to be able to inspect
    (mongoose.set('debug', true))
  - small divergences from the driver: collection names, return
    values, defaults

When Mongoose is not needed: migration scripts, heavy aggregations,
thin services with three or four queries. There the raw driver is
more honest and more predictable.
```

## Schema, Model, Document

```typescript
import { Schema, model, Types, HydratedDocument } from 'mongoose';

// 1. The interface — what the document is for TypeScript
export interface Post {
  _id: Types.ObjectId;
  title: string;
  slug: string;
  body: string;
  author: { _id: Types.ObjectId; name: string };
  tags: string[];
  status: 'draft' | 'published';
  stats: { views: number; comments: number };
  publishedAt?: Date;
  createdAt: Date;
  updatedAt: Date;
}

// 2. The Schema — document shape and rules
const postSchema = new Schema<Post>(
  {
    title:  { type: String, required: true, trim: true, maxlength: 200 },
    slug:   { type: String, required: true, unique: true, lowercase: true },
    body:   { type: String, required: true },
    author: {
      _id:  { type: Schema.Types.ObjectId, ref: 'User', required: true },
      name: { type: String, required: true },
    },
    tags:   { type: [String], default: [] },
    status: { type: String, enum: ['draft', 'published'], default: 'draft' },
    stats: {
      views:    { type: Number, default: 0, min: 0 },
      comments: { type: Number, default: 0, min: 0 },
    },
    publishedAt: { type: Date },
  },
  {
    timestamps: true,        // createdAt/updatedAt maintained automatically
    collection: 'posts',     // otherwise the name is derived from the model
    versionKey: '__v',       // see the __v section in article 08
  },
);

// 3. The Model — a class bound to a collection
export const PostModel = model<Post>('Post', postSchema);

// 4. The Document — the instance a query returns
export type PostDoc = HydratedDocument<Post>;
```

```txt
Three things that surprise you the first time:

1. The collection name is derived from the model name: model('Post')
   → collection posts (lowercased + pluralized). model('Person') →
   people. If the collection already exists under a different name,
   set collection explicitly — otherwise Mongoose silently creates a
   new one and "the data disappears".

2. A model is registered globally on the mongoose instance. Calling
   model('Post', schema) again in another file throws
   OverwriteModelError — typical with hot reload in Next.js (the fix
   is mongoose.models.Post ?? model(...)).

3. A schema creates nothing in the database except indexes. There is
   no DDL: the collection appears on the first write.
```

## SchemaTypes and casting

```txt
Types: String · Number · Date · Boolean · ObjectId · Buffer
       Decimal128 · Map · Array · Mixed (Schema.Types.Mixed) ·
       nested schemas and subdocuments

Casting happens BEFORE validation:
  { views: "42" }               → 42
  { publishedAt: "2026-08-13" } → Date
  { authorId: "66b0f2c1..." }   → ObjectId
  { active: "true" }            → true ('true'/'1'/'yes' and the number 1)

If casting is impossible you get a CastError, and that is an INPUT
error (400), not a server failure (500):
  { views: "many" } → CastError: Cast to Number failed
Which is exactly why mapping Mongoose errors to HTTP codes has to be
deliberate (see [Mongoose Queries, populate, and Pitfalls]).
```

```typescript
// Field options that get used constantly
{
  email: {
    type: String,
    required: [true, 'email is required'],   // a message instead of the default
    unique: true,          // ← THIS IS AN INDEX, NOT A VALIDATOR (see below)
    lowercase: true,       // a setter: lowercases the value
    trim: true,
    match: [/^\S+@\S+$/, 'invalid email'],
  },
  passwordHash: { type: String, required: true, select: false }, // not
                          // returned by default — handy for secrets
  role: { type: String, enum: ['user', 'admin'], default: 'user' },
  createdBy: { type: Schema.Types.ObjectId, ref: 'User', immutable: true },
  meta: { type: Schema.Types.Mixed },     // an arbitrary structure
  score: { type: Number, default: () => 0 },  // a function default
}
```

```txt
Three SchemaTypes traps:

1. unique is NOT a validator. Mongoose merely creates a unique index;
   the check is done by the server, and a violation arrives as an
   E11000 duplicate key error AFTER the request is sent, not as a
   ValidationError. Consequences: (a) the error handler must know
   about E11000; (b) if the index was never created (autoIndex
   disabled in production) there is NO uniqueness at all, even though
   the schema says unique: true (see [Mongoose Queries, populate, and
   Pitfalls]).

2. Mixed does not track changes. doc.meta.x = 1 will not be saved
   until you call doc.markModified('meta').

3. An array defaults to an empty array, not undefined. A field
   tags: [String] with no value yields [] in the document. Something
   similar holds for a nested object: it may be created even if you
   never set it (controlled by the minimize option).
```

## Validators and the key nuance: when they actually run

```typescript
const userSchema = new Schema<User>({
  email: {
    type: String,
    required: true,
    // a synchronous custom validator
    validate: {
      validator: (v: string) => /^\S+@\S+\.\S+$/.test(v),
      message: (props) => `${props.value} is not a valid email`,
    },
  },
  username: {
    type: String,
    required: true,
    // an async validator: a database call inside validation
    validate: {
      validator: async function (v: string) {
        const exists = await UserModel.exists({ username: v });
        return !exists;
      },
      message: 'username is taken',
    },
  },
});
```

The async "is this username taken" validator is useful for a clear error message, but it is **not a uniqueness guarantee**: time passes between the check and the write (see the race condition in [CRUD and Query Operators]). Only a unique index guarantees it.

Next comes the thing that breaks the most code in real projects:

```txt
                   Which operations go through validation and hooks
┌────────────────────────────┬─────────────────────────┬───────────────┬─────────────┐
│ operation                  │ validation              │ pre/post save │ query hooks │
├────────────────────────────┼─────────────────────────┼───────────────┼─────────────┤
│ doc.save()                 │ yes                     │ yes           │ no          │
├────────────────────────────┼─────────────────────────┼───────────────┼─────────────┤
│ Model.create()             │ yes                     │ yes           │ no          │
├────────────────────────────┼─────────────────────────┼───────────────┼─────────────┤
│ Model.insertMany()         │ yes                     │ no            │ no          │
├────────────────────────────┼─────────────────────────┼───────────────┼─────────────┤
│ findOneAndUpdate()         │ only with runValidators │ NO            │ yes         │
├────────────────────────────┼─────────────────────────┼───────────────┼─────────────┤
│ updateOne() / updateMany() │ only with runValidators │ NO            │ yes         │
├────────────────────────────┼─────────────────────────┼───────────────┼─────────────┤
│ bulkWrite()                │ no                      │ no            │ no          │
└────────────────────────────┴─────────────────────────┴───────────────┴─────────────┘
       hence the password hashing bug: pre('save') never sees findOneAndUpdate
```

```typescript
// Validation does NOT run on update operations by default
await PostModel.updateOne(
  { _id: id },
  { $set: { status: 'nonsense', title: '' } },
);
// → written with no error: enum and required were never checked

// It has to be enabled explicitly
await PostModel.updateOne(
  { _id: id },
  { $set: { status: 'nonsense' } },
  { runValidators: true },       // → ValidationError
);
```

```txt
And even with runValidators there are limitations worth knowing:

  - required is not checked for fields that are NOT in the update.
    That is logical (the update is partial), but it means "the
    document is guaranteed valid" only holds through save()
  - a custom validator receives the field value, but `this` is the
    Query, not the document. A validator that needs other document
    fields does not behave on update the way it does on save
  - context: 'query' switches `this` inside the validator to the query
    object — that is how you reach the update itself via
    this.getUpdate()
  - validators for $push/$addToSet check the element being added, not
    the whole array

The practical conclusion: if the invariants matter, there are two
honest approaches:
  (1) the whole domain writes through doc.save() — then validation and
      hooks always run, at the cost of an extra read;
  (2) update operations are allowed, but validation is duplicated at
      the boundary (zod/class-validator in the DTO), and the schema is
      treated as the last line of defence, not the only one.
```

```typescript
// Manual checks when you need to control the moment
const post = new PostModel(input);
await post.validate();               // throws ValidationError
const err = post.validateSync();     // returns the error instead of throwing

// The ValidationError shape → mapping to a 400 with field details
try {
  await post.save();
} catch (e) {
  if (e instanceof mongoose.Error.ValidationError) {
    const fields = Object.entries(e.errors).map(([path, err]) => ({
      path,
      message: err.message,
    }));
    throw new BadRequestError(fields);
  }
  throw e;
}
```

## Middleware: document hooks vs query hooks

Mongoose hooks come in two families with a different `this`, and confusing them is the source of those "mysterious" bugs.

```typescript
// DOCUMENT middleware: this is the document itself
userSchema.pre('save', async function () {
  // without isModified the password gets re-hashed on every save
  if (!this.isModified('passwordHash')) return;
  this.passwordHash = await bcrypt.hash(this.passwordHash, 12);
});

userSchema.post('save', function (doc) {
  logger.info({ userId: doc._id }, 'user saved');
});

// QUERY middleware: this is the Query, there is no document yet
postSchema.pre(/^find/, function () {
  // soft delete: hide deleted documents from every find query
  this.where({ deletedAt: { $exists: false } });
});

postSchema.pre('findOneAndUpdate', function () {
  this.set({ updatedAt: new Date() });          // amend the update itself
  const update = this.getUpdate();              // what exactly is changing
});

// AGGREGATE middleware: this is the Aggregate
postSchema.pre('aggregate', function () {
  this.pipeline().unshift({ $match: { deletedAt: { $exists: false } } });
});

// ERROR handling middleware: 4 arguments → an error handler
userSchema.post('save', function (err: any, doc: unknown, next: Function) {
  if (err?.code === 11000) next(new ConflictError('email already exists'));
  else next(err);
});
```

Now the bug interviewers ask about almost every time:

```typescript
// The schema hashes the password in pre('save')
userSchema.pre('save', async function () { /* bcrypt.hash */ });

// The password-change code is written with findOneAndUpdate
await UserModel.findOneAndUpdate(
  { _id: userId },
  { $set: { passwordHash: newPassword } },   // ← this is a PLAINTEXT password
);
// pre('save') is NOT called: findOneAndUpdate is a query-level
// operation, the document is never loaded into the application and no
// save() happens. The database ends up with a plaintext password and
// login stops working (bcrypt.compare compares against a non-hash).
```

```txt
Why: pre('save') is document middleware. It is tied to the DOCUMENT
lifecycle (load → modify → save). findOneAndUpdate/updateOne/
updateMany/bulkWrite never load the document: they send the server a
description of the changes. There is no document whose save() could be
intercepted.

Three ways to fix it:

1. The domain only writes through a document:
     const user = await UserModel.findById(id);
     user.passwordHash = newPassword;
     await user.save();               // the hook runs
   Upside: invariants live in one place. Downside: an extra read and
   the loss of atomic read-modify-write (see [CRUD and Query
   Operators]).

2. Duplicate the hook on query operations — remembering that `this` is
   the Query:
     userSchema.pre('findOneAndUpdate', async function () {
       const update = this.getUpdate() as any;
       const raw = update?.$set?.passwordHash ?? update?.passwordHash;
       if (!raw) return;
       const hash = await bcrypt.hash(raw, 12);
       this.set({ passwordHash: hash });
     });
   Upside: works for both paths. Downside: the logic is duplicated,
   and you still have to remember the third path (bulkWrite).

3. Take hashing out of the schema entirely: do it in the service (the
   single place where a password changes) and keep the schema free of
   magic. Often the most honest option for "interview-ready" code.
```

```txt
A few more places where hooks do not behave as expected:
  - insertMany() validates documents but does NOT run pre('save')
  - bulkWrite() goes through neither validation nor hooks
  - deleteOne() on the MODEL is query middleware; deleteOne() on a
    DOCUMENT is document middleware. Same name, different this
  - post hooks for find receive an array of documents, for findOne a
    single document
  - hooks must be registered BEFORE the model is compiled (model(...)),
    otherwise they simply never apply
```

## Virtuals, methods, statics, query helpers

```typescript
// A virtual — a computed field that is not stored in the database
postSchema.virtual('url').get(function () {
  return `/posts/${this.slug}`;
});

// A virtual with a setter
userSchema.virtual('fullName')
  .get(function () { return `${this.firstName} ${this.lastName}`; })
  .set(function (v: string) {
    const [first, ...rest] = v.split(' ');
    this.firstName = first;
    this.lastName = rest.join(' ');
  });

// Virtuals do NOT appear in JSON unless enabled explicitly
postSchema.set('toJSON', { virtuals: true });
postSchema.set('toObject', { virtuals: true });

// A method — instance behaviour
userSchema.methods.checkPassword = function (plain: string) {
  return bcrypt.compare(plain, this.passwordHash);
};

// A static — model behaviour
postSchema.statics.findPublishedBySlug = function (slug: string) {
  return this.findOne({ slug, status: 'published' });
};

// A query helper — a reusable link in the chain
postSchema.query.published = function () {
  return this.where({ status: 'published' });
};
// await PostModel.find().published().sort({ publishedAt: -1 });
```

An important point about virtuals: they do not exist for the database. You cannot filter, sort or index by a virtual — and `find({ url: ... })` simply finds nothing. If you need to search by a value, it has to be a real field.

## strict mode: why extra fields vanish silently

```typescript
const schema = new Schema({ title: String }, { strict: true }); // default

await Model.create({ title: 'A', hackerField: 'x' });
// → only title lands in the database. hackerField is silently
//   DISCARDED, with no error
```

```txt
strict: true    (the default) — fields outside the schema are dropped
strict: false   — they are saved as-is (back to "schemaless")
strict: 'throw' — writing an unknown field throws

strictQuery — the same for filters: an unknown field in a find
              condition... the behaviour changed between Mongoose
              versions, so set it explicitly:
              mongoose.set('strictQuery', true)

In practice: strict: true protects against garbage, but silent
dropping masks typos — you saved createdAtt, there is no error and no
field. For services where mismatches must be caught early, 'throw' is
more useful. And separately: strict does not remove fields that are
ALREADY in documents written by older code — a schema migrates
nothing.
```

## Typing schemas in TypeScript (an overview)

```typescript
// Option 1: the interface is the source of truth (shown above)
const postSchema = new Schema<Post>({ ... });
export const PostModel = model<Post>('Post', postSchema);

// Option 2: the schema is the source of truth, the type is inferred
import { InferSchemaType, model, Schema } from 'mongoose';
const schema = new Schema({
  title: { type: String, required: true },
  tags:  [String],
});
type PostFromSchema = InferSchemaType<typeof schema>;
// { title: string; tags: string[] }

// Typing methods/statics: the model's extra generics
interface PostMethods { isFresh(): boolean }
interface PostStatics extends Model<Post, {}, PostMethods> {
  findPublishedBySlug(slug: string): Promise<PostDoc | null>;
}
const PostModel = model<Post, PostStatics>('Post', postSchema);

// An ObjectId in types is Types.ObjectId, not string. At the API
// boundary it turns into a string (Extended JSON — see [Document
// Model and Use Cases]), and those are TWO different types that must
// not be mixed up in DTOs
```

```txt
A practical tip: keep separate types for the "raw" document
(lean/DTO) and for the hydrated one (HydratedDocument). Otherwise the
code grows a type that has both save() and whatever already went out
as JSON — and the first lean() breaks the typing (see [Mongoose
Queries, populate, and Pitfalls]).
```

## Connection to other topics

```txt
[Document Model and Use Cases]    — the schema that "lives in the
                                    code"; ObjectId and Extended JSON
                                    at the API boundary
[CRUD and Query Operators]        — what updateOne and findOneAndUpdate
                                    actually do — the operations that
                                    document hooks never see
[Schema Design: Embedding vs      — what to describe as a nested schema
 Referencing]                       and what as a ref
[Indexes and Query Performance]   — unique as an index rather than a
                                    validator; indexes declared in the
                                    schema
[Mongoose Queries, populate,      — lean(), populate, autoIndex, __v,
 and Pitfalls]                      mapping E11000 to an API error
```

## Common interview traps

- **"Mongoose validation always runs"** — it runs on `save()`/`create()`, and on `updateOne`/`findOneAndUpdate` only with `runValidators: true` — and even then `required` is not checked for fields absent from the update. `bulkWrite` is not validated at all.

- **"`pre('save')` fires on any document change"** — it does not fire on `findOneAndUpdate`, `updateOne`, `updateMany` or `bulkWrite`: those are query operations and the document is never loaded. The classic consequence is a password stored in plaintext.

- **"`unique: true` in the schema is validation"** — it is a unique index declaration. A violation arrives as the database error `E11000`, not a `ValidationError`; and if the index was never created (`autoIndex: false` in production) there is no uniqueness at all.

- **"An async validator guarantees uniqueness"** — there is a race window between the check and the write. Only a unique index guarantees it; the validator exists for a readable message.

- **"Mongoose is an ORM, it abstracts MongoDB away"** — it does not remove the need to understand the document model, indexes and atomicity: `populate` is still extra queries, and a bad schema stays bad (see [Schema Design: Embedding vs Referencing]).

- **"An unknown field in create() causes an error"** — with `strict: true` it is silently dropped. You only get an error with `strict: 'throw'`.

- **"A virtual can be used in a query"** — a virtual does not exist for the database: you cannot filter, sort or index by it, and it only reaches JSON with `toJSON: { virtuals: true }`.

- **"`Mixed` is a convenient way to store arbitrary data"** — convenient, but Mongoose does not track its changes: without `markModified()` an edit to a nested field is not saved.

- **"The collection name is the model name"** — Mongoose lowercases and pluralizes it (`Post` → `posts`, `Person` → `people`). For an existing collection the name is set with the `collection` option.

- **"A CastError is a server bug"** — it is invalid input (`"many"` in a numeric field, a malformed `ObjectId` in a URL parameter). That is returned as a 400, not a 500.
