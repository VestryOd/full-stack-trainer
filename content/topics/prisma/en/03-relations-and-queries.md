# Prisma Relations and Queries

## Relation types

Prisma supports three relation types — all of them map to standard Foreign Keys and JOINs in PostgreSQL. The only difference is which side holds the FK.

```prisma
// One-to-One: User has exactly one Profile
// FK is on the "child" model (Profile.userId)
model User {
  id      Int      @id @default(autoincrement())
  profile Profile?  // nullable — Profile may not exist
}

model Profile {
  id     Int    @id @default(autoincrement())
  bio    String?
  userId Int    @unique  // @unique enforces one-to-one (not one-to-many)
  user   User   @relation(fields: [userId], references: [id], onDelete: Cascade)
}

// One-to-Many: User has many Posts
model User {
  id    Int    @id @default(autoincrement())
  posts Post[]  // virtual field — no column in the DB
}

model Post {
  id       Int  @id @default(autoincrement())
  authorId Int
  author   User @relation(fields: [authorId], references: [id])
}

// Many-to-Many explicit (production recommendation)
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

// Many-to-Many implicit (when no extra fields are needed — Prisma creates the join table)
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

## onDelete / onUpdate — Referential Actions

```prisma
model Post {
  authorId Int
  author   User @relation(fields: [authorId], references: [id],
    onDelete: Cascade,  // delete User → delete all their Posts
    onUpdate: Cascade   // change User.id → update Post.authorId
  )
}

// Options:
// Cascade  — cascade delete/update (most common)
// Restrict — prevent deletion if related records exist (data protection)
// SetNull  — set FK = NULL (field must be nullable: authorId Int?)
// NoAction — no action at Prisma level (enforced at DB level)
// SetDefault — set FK to its default value
```

## Queries — find*, create, update, delete

```typescript
// findUnique — only for @id or @unique fields, returns T | null
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
    email: { contains: '@company.com', mode: 'insensitive' }, // case-insensitive LIKE
    name: { not: null },
  },
  orderBy: [{ createdAt: 'desc' }, { name: 'asc' }],
  take: 20,    // LIMIT
  skip: 40,    // OFFSET — offset pagination
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
  skipDuplicates: true, // ignore unique constraint conflicts
});

await prisma.post.deleteMany({ where: { authorId: 1 } });
```

## include vs select — loading relations

```typescript
// include: load related records (JOIN under the hood)
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

// select: choose only the needed fields (projection)
const userNames = await prisma.user.findMany({
  select: {
    id: true,
    email: true,
    posts: {           // select + relation — works
      select: { title: true, createdAt: true },
      where: { published: true },
    },
  },
});
// Result is strongly typed: { id: number; email: string; posts: { title: string; ... }[] }

// include and select cannot be used together at the same level
// ✗ { include: { posts: true }, select: { id: true } } — TS error
// ✓ select: { id: true, posts: { select: { title: true } } } — correct
```

## Nested Writes — related records in one request

```typescript
// create with nested create (User + Posts in one request = one transaction)
const user = await prisma.user.create({
  data: {
    email: 'alice@example.com',
    profile: {
      create: { bio: 'Senior Engineer' },  // create Profile
    },
    posts: {
      create: [
        { title: 'First post' },
        { title: 'Second post' },
      ],
    },
  },
  include: { profile: true, posts: true }, // return with relations
});

// connect — link an existing record
await prisma.post.update({
  where: { id: 1 },
  data: {
    tags: {
      connect: [{ id: 1 }, { id: 2 }],     // add tags
      disconnect: [{ id: 3 }],              // remove a tag
      set: [{ id: 1 }],                     // set exactly these tags (disconnect old ones)
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

## Pagination — offset vs cursor

```typescript
// Offset pagination — simple but slow on large tables
const page2 = await prisma.post.findMany({
  skip: 20,   // OFFSET 20
  take: 10,   // LIMIT 10
  orderBy: { createdAt: 'desc' },
});
// Problem: OFFSET 1000000 — PostgreSQL still reads 1000010 rows

// Cursor pagination — for large tables and infinite scrolling
const nextPage = await prisma.post.findMany({
  cursor: { id: lastSeenId },   // start after this id
  take: 10,
  skip: 1,                       // skip the cursor itself
  orderBy: { id: 'asc' },
});
// Under the hood: WHERE id > lastSeenId LIMIT 10 → O(log N) via index
```

## The N+1 problem and how to solve it

```typescript
// N+1: a separate query to posts is executed for each user
const users = await prisma.user.findMany();
for (const user of users) {
  const posts = await prisma.post.findMany({ where: { authorId: user.id } });
  // 1 query for findMany + N queries for posts = N+1
}

// Solution: include — a single query with JOIN
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

- **"include always does a JOIN"** — not quite. Prisma 5+ uses `JOIN` for include in most cases, but for some patterns it may issue a separate `SELECT ... WHERE id IN (...)`. Enable `log: ['query']` to see the actual SQL.

- **"select and include can't be used together"** — they can't at the same level (`{ select, include }` → TS error), but you can do: `select: { id: true, posts: { select: { title: true } } }` — a select with a nested select for the relation.

- **"Implicit Many-to-Many is better for production"** — no. Explicit Many-to-Many (explicit join table) is recommended for production: you can add fields (`assignedAt`, `role`), directly query the join table (`prisma.userRole.findMany()`), and cascade deletion is easier to manage.

- **"findUnique is faster than findFirst"** — yes, because `findUnique` translates to `WHERE id = ?` on an indexed field. `findFirst` with the same condition is equivalent but may not be optimized by the Prisma compiler. Use `findUnique` when searching by `@id` or `@unique` fields.

- **"Cursor pagination is always better than offset"** — cursor is better for large tables and infinite scrolling. But cursor-based pagination does not support jumping to an arbitrary page (you can't go to page 50 without traversing pages 1–49). For numbered page UIs: offset. For infinite scroll/APIs: cursor.
