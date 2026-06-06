# Prisma Relations and Queries

## The Main Idea of Relations

Prisma describes relationships between models.

Under the hood these are still ordinary:

```txt
Foreign Keys
JOIN
Reference Constraints
```

in PostgreSQL.

---

# One-To-One

Example:

```txt
User
 ↓
Profile
```

---

# Prisma Schema

```prisma
model User {
  id      Int      @id @default(autoincrement())
  profile Profile?
}

model Profile {
  id      Int @id @default(autoincrement())

  userId  Int @unique

  user    User @relation(
    fields: [userId],
    references: [id]
  )
}
```

---

# Why @unique

Because:

```txt
one User
=
one Profile
```

---

# SQL Equivalent

```sql
profile.user_id UNIQUE
```

---

# One-To-Many

The most popular relation.

---

Example:

```txt
User
 ↓
Posts
```

---

# Prisma Schema

```prisma
model User {
  id    Int    @id @default(autoincrement())

  posts Post[]
}

model Post {
  id     Int @id @default(autoincrement())

  userId Int

  user User @relation(
    fields: [userId],
    references: [id]
  )
}
```

---

# SQL Equivalent

```sql
posts.user_id REFERENCES users(id)
```

---

# Many-To-Many

A very common interview question.

---

Example:

```txt
Users
 ↕
Roles
```

---

# Implicit Many-To-Many

Prisma can create the join table automatically.

---

```prisma
model User {
  id    Int @id @default(autoincrement())

  roles Role[]
}

model Role {
  id    Int @id @default(autoincrement())

  users User[]
}
```

---

Prisma will create the intermediate table itself.

---

# Explicit Many-To-Many

More commonly used in production.

---

Because extra fields can be stored.

---

Example:

```prisma
model UserRole {
  userId Int
  roleId Int

  assignedAt DateTime @default(now())

  user User @relation(
    fields: [userId],
    references: [id]
  )

  role Role @relation(
    fields: [roleId],
    references: [id]
  )

  @@id([userId, roleId])
}
```

---

# SELECT Queries

Get all users.

```ts
const users = await prisma.user.findMany();
```

---

Get one.

```ts
const user = await prisma.user.findUnique({
  where: {
    id: 1,
  },
});
```

---

# findUnique

Only used for:

```txt
Primary Key
Unique Fields
```

---

# findFirst

Finds the first matching record.

---

```ts
await prisma.user.findFirst({
  where: {
    isActive: true,
  },
});
```

---

# WHERE

Filtering.

---

```ts
await prisma.user.findMany({
  where: {
    email: 'max@test.com',
  },
});
```

---

# AND

```ts
where: {
  AND: [
    { active: true },
    { age: { gt: 18 } },
  ]
}
```

---

# OR

```ts
where: {
  OR: [
    { role: 'ADMIN' },
    { role: 'MODERATOR' },
  ]
}
```

---

# LIKE Equivalent

```ts
where: {
  email: {
    contains: '@gmail.com',
  },
}
```

---

# include

A very important topic.

---

Get a user and their posts.

```ts
await prisma.user.findMany({
  include: {
    posts: true,
  },
});
```

---

Under the hood Prisma will perform a JOIN.

---

# select

Allows returning only the needed fields.

---

```ts
await prisma.user.findMany({
  select: {
    id: true,
    email: true,
  },
});
```

---

Very useful for performance.

---

# include vs select

include:

```txt
adds relations
```

---

select:

```txt
limits fields
```

---

# Nested Select

```ts
await prisma.user.findMany({
  select: {
    id: true,
    posts: {
      select: {
        title: true,
      },
    },
  },
});
```

---

# Create

```ts
await prisma.user.create({
  data: {
    email: 'max@test.com',
  },
});
```

---

# Update

```ts
await prisma.user.update({
  where: {
    id: 1,
  },
  data: {
    email: 'new@test.com',
  },
});
```

---

# Delete

```ts
await prisma.user.delete({
  where: {
    id: 1,
  },
});
```

---

# Nested Writes

A very common interview topic.

---

You can create a User and a Post in one query.

---

```ts
await prisma.user.create({
  data: {
    email: 'max@test.com',

    posts: {
      create: [
        {
          title: 'First Post',
        },
      ],
    },
  },
});
```

---

# connect

Link an existing record.

---

```ts
await prisma.post.create({
  data: {
    title: 'Post',

    user: {
      connect: {
        id: 1,
      },
    },
  },
});
```

---

# connectOrCreate

Very popular.

---

If the record does not exist:

```txt
create
```

If it does:

```txt
connect
```

---

```ts
connectOrCreate: {
  where: {
    email: 'max@test.com',
  },
  create: {
    email: 'max@test.com',
  },
}
```

---

# Pagination

offset pagination

```ts
skip: 20
take: 10
```

---

cursor pagination

```ts
cursor: {
  id: 100
}
```

---

Cursor pagination is preferable for large tables.

---

# A Common Question

What is better:

```ts
include
```

or

multiple separate queries?

---

Answer:

It depends on the data volume.

A large include can lead
to very heavy JOIN queries.

---

# Interview Answer

Relations in Prisma are an abstraction over Foreign Keys. Prisma supports One-To-One, One-To-Many, and Many-To-Many relationships and provides a convenient API through include, select, nested writes, connect, and connectOrCreate.
