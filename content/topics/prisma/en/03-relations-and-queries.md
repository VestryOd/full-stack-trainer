# Prisma Relations and Queries

## Relation types

Prisma supports three relation types: one-to-one, one-to-many and many-to-many. It turns all three into plain SQL — the language it uses to talk to PostgreSQL. In the database a relation is an FK (foreign key) column on the child table, and reading rows together with their relations is a `JOIN`.

The only difference between the three is which side holds that key. The model that carries `@relation(fields: [...])` is the one with the column.

```prisma
// One-to-one: a User has exactly one Profile
// The foreign key sits on the child model (Profile.userId)
model User {
  id      Int      @id @default(autoincrement())
  profile Profile?  // may be empty — a Profile is optional
}

model Profile {
  id     Int    @id @default(autoincrement())
  bio    String?
  userId Int    @unique  // @unique is what makes it one-to-one
  user   User   @relation(fields: [userId], references: [id], onDelete: Cascade)
}

// One-to-many: a User has many Posts
model User {
  id    Int    @id @default(autoincrement())
  posts Post[]  // virtual field — there is no such column
}

model Post {
  id       Int  @id @default(autoincrement())
  authorId Int
  author   User @relation(fields: [authorId], references: [id])
}

// Many-to-many, explicit (the recommendation for production)
// — when you need extra fields on the join table
model UserRole {
  userId     Int
  roleId     Int
  assignedAt DateTime @default(now())
  assignedBy String?

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)
  role Role @relation(fields: [roleId], references: [id], onDelete: Cascade)

  @@id([userId, roleId])
  @@index([roleId])
}

// Many-to-many, implicit: no extra fields needed,
// so Prisma creates the join table itself
model Post {
  id   Int   @id @default(autoincrement())
  tags Tag[]
}
model Tag {
  id    Int    @id @default(autoincrement())
  posts Post[]
}
// → Prisma creates the "_PostToTag" table automatically
```

## onDelete / onUpdate — referential actions

`onDelete` and `onUpdate` set the referential actions: what happens to the child rows when the parent row is deleted, or when its `id` changes.

```prisma
model Post {
  authorId Int
  author   User @relation(fields: [authorId], references: [id],
    onDelete: Cascade,  // delete a User → delete all their Posts
    onUpdate: Cascade   // change User.id → update Post.authorId
  )
}

// Options:
// Cascade  — cascade the delete and the update (most common)
// Restrict — block the delete while related rows still exist
// SetNull  — write NULL into the key (needs authorId Int?)
// NoAction — Prisma does nothing; the database checks it
// SetDefault — write the key's default value
```

## Queries — find*, create, update, delete

```typescript
// findUnique — only on @id or @unique fields, returns T | null
const user = await prisma.user.findUnique({ where: { id: 1 } });

// findFirst — first record matching a condition, returns T | null
const active = await prisma.user.findFirst({
  where: { isActive: true },
  orderBy: { createdAt: 'desc' },
});

// findMany — all records matching a condition
const users = await prisma.user.findMany({
  where: {
    AND: [
      { isActive: true },
      { createdAt: { gte: new Date('2024-01-01') } },
    ],
    OR: [
      { role: 'ADMIN' },
      { role: 'EDITOR' },
    ],
    email: { contains: '@company.com', mode: 'insensitive' }, // LIKE, ignoring case
    name: { not: null },
  },
  orderBy: [{ createdAt: 'desc' }, { name: 'asc' }],
  take: 20,    // LIMIT
  skip: 40,    // OFFSET — pagination by offset
});

// count + aggregate
const total = await prisma.user.count({ where: { isActive: true } });
const stats = await prisma.order.aggregate({
  _sum: { amount: true },
  _avg: { amount: true },
  _count: true,
  where: { status: 'COMPLETED' },
});

// upsert — create if not exists, else update
const user = await prisma.user.upsert({
  where: { email: 'alice@example.com' },
  create: { email: 'alice@example.com', name: 'Alice' },
  update: { name: 'Alice Updated' },
});

// createMany / updateMany / deleteMany — bulk operations
await prisma.post.createMany({
  data: [{ title: 'A', authorId: 1 }, { title: 'B', authorId: 1 }],
  skipDuplicates: true, // do not fail on UNIQUE conflicts
});

await prisma.post.deleteMany({ where: { authorId: 1 } });
```

## include vs select — loading relations

`include` adds the relations on top of every field of the model. The `select` option does the opposite: it returns exactly the fields you listed, and nothing else.

```typescript
// include: pull in related records (a JOIN inside)
const userWithPosts = await prisma.user.findUnique({
  where: { id: 1 },
  include: {
    posts: {
      where: { published: true },
      orderBy: { createdAt: 'desc' },
      take: 5,
      include: { tags: true }, // nested include
    },
    profile: true,
  },
});

// select: take only the fields you need (a projection)
const userNames = await prisma.user.findMany({
  select: {
    id: true,
    email: true,
    posts: {           // select together with a relation — allowed
      select: { title: true, createdAt: true },
      where: { published: true },
    },
  },
});
// The result type is exact:
// { id: number; email: string; posts: { title: string; ... }[] }

// include and select cannot sit together at the same level
// ✗ { include: { posts: true }, select: { id: true } } — TS error
// ✓ select: { id: true, posts: { select: { title: true } } } — correct
```

## Nested writes — related records in one request

A nested write creates or changes related records inside a single Prisma call. Prisma wraps such a call in a transaction: either everything is written, or nothing is.

```typescript
// create with a nested create: a User and their Posts in one request
const user = await prisma.user.create({
  data: {
    email: 'alice@example.com',
    profile: {
      create: { bio: 'Senior Engineer' },  // create the Profile too
    },
    posts: {
      create: [
        { title: 'First post' },
        { title: 'Second post' },
      ],
    },
  },
  include: { profile: true, posts: true }, // return it with its relations
});

// connect — link a record that already exists
await prisma.post.update({
  where: { id: 1 },
  data: {
    tags: {
      connect: [{ id: 1 }, { id: 2 }],     // add tags
      disconnect: [{ id: 3 }],              // remove a tag
      set: [{ id: 1 }],                     // keep exactly these, drop the rest
    },
  },
});

// connectOrCreate — find or create
await prisma.post.create({
  data: {
    title: 'Post',
    author: {
      connectOrCreate: {
        where: { email: 'alice@example.com' },
        create: { email: 'alice@example.com', name: 'Alice' },
      },
    },
  },
});
```

## Pagination — by offset or by cursor

Pagination comes in two shapes. By offset: "skip 20 rows, give me the next 10". By cursor: "give me 10 rows after this `id`".

```typescript
// Pagination by offset — simple but slow on large tables
const page2 = await prisma.post.findMany({
  skip: 20,   // OFFSET 20
  take: 10,   // LIMIT 10
  orderBy: { createdAt: 'desc' },
});
// Problem: with OFFSET 1000000 PostgreSQL still reads 1000010 rows

// Pagination by cursor — for large tables and infinite scrolling
const nextPage = await prisma.post.findMany({
  cursor: { id: lastSeenId },   // start after this id
  take: 10,
  skip: 1,                       // skip the cursor row itself
  orderBy: { id: 'asc' },
});
// Inside: WHERE id > lastSeenId LIMIT 10 → O(log N) through the index
```

## The N+1 problem and how to solve it

N+1 means a list of N rows costs N+1 queries: one for the list itself, plus one per row for its relations.

```typescript
// N+1: a separate query to posts runs for every user
const users = await prisma.user.findMany();
for (const user of users) {
  const posts = await prisma.post.findMany({ where: { authorId: user.id } });
  // 1 query for findMany + N queries for posts = N+1
}

// The fix: include — a single query with a JOIN
const usersWithPosts = await prisma.user.findMany({
  include: { posts: true },
  // Prisma executes: SELECT users.*, posts.* FROM users LEFT JOIN posts ON ...
});

// For complex cases: prisma.$queryRaw with explicit JOIN
const result = await prisma.$queryRaw<UserWithCount[]>`
  SELECT u.id, u.email, COUNT(p.id)::int as post_count
  FROM users u
  LEFT JOIN posts p ON p.author_id = u.id
  GROUP BY u.id
`;
```

## Common interview mistakes

- **"include always does a `JOIN`"** — not quite. In Prisma 5 and later, `include` becomes a `JOIN` in most cases, but for some query shapes Prisma issues a separate `SELECT ... WHERE id IN (...)`. Turn on `log: ['query']` and you see the real SQL instead of a guess about it.

- **"select and include can't be used together"** — they can't at the same level. `{ select, include }` in one object is a TypeScript error. Nesting them is fine: `select: { id: true, posts: { select: { title: true } } }` returns two user fields plus one field of each post.

- **"An implicit many-to-many is better for production"** — the opposite. An explicit join table is a model you own, so you can:
  - add fields to it, such as `assignedAt` or `role`;
  - query it directly with `prisma.userRole.findMany()`;
  - configure cascade deletion for each side separately.

- **"findUnique is faster than findFirst"** — yes. `findUnique` translates to `WHERE id = ?` on an indexed field. The same condition in `findFirst` returns the same row, but Prisma does not necessarily optimize it the same way. Use `findUnique` when you search by `@id` or `@unique` fields.

- **"Cursor pagination is always better than offset"** — cursor is better on large tables and for infinite scrolling. But a cursor cannot jump to an arbitrary page: reaching page 50 means walking pages 1 to 49. So use offset for a numbered-page interface, and a cursor for infinite scroll and APIs.
