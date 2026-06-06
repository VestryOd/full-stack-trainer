# Prisma Fundamentals

## What is Prisma

Prisma is a TypeScript-first ORM toolkit.

The main idea of Prisma:

- describe the data structure in schema.prisma
- automatically generate a typed client
- work with the database through a TypeScript API

---

# ORM

ORM = Object Relational Mapping.

---

Without ORM:

```sql
SELECT *
FROM users;
```

---

With ORM:

```ts
await prisma.user.findMany();
```

---

# Why Prisma Became Popular

Before Prisma, the most common choices were:

- TypeORM
- Sequelize
- MikroORM

---

Prisma offered:

```txt
Schema First
Strong Typing
Generated Client
Excellent DX
```

---

# The Main Idea of Prisma

The developer describes models:

```prisma
model User {
  id    Int    @id
  email String
}
```

---

After that, Prisma generates:

```ts
prisma.user.findMany()
prisma.user.create()
prisma.user.update()
prisma.user.delete()
```

---

# What Prisma Consists Of

Prisma consists of several parts.

---

# Prisma Schema

File:

```txt
schema.prisma
```

---

Describes:

- models
- relations
- datasource
- generator

---

# Prisma Client

The generated TypeScript API.

---

Example:

```ts
await prisma.user.findMany();
```

---

# Prisma Migrate

The migration system.

---

Allows:

```txt
change schema
↓
generate SQL
↓
apply changes
```

---

# Prisma Engine

The low-level layer
that communicates with the database.

---

# Architecture

Frontend
↓
NestJS
↓
Prisma Client
↓
Prisma Engine
↓
PostgreSQL

---

# Why Prisma Does Not Replace PostgreSQL

A very important question.

---

Prisma does NOT store data.

Prisma does NOT execute SQL itself.

---

It generates queries to the database.

---

That is:

```txt
Prisma
=
abstraction over SQL
```

---

# When Prisma Works Best

- TypeScript projects
- NestJS
- GraphQL
- CRUD-heavy applications
- SaaS products

---

# When Prisma Can Be Inconvenient

Very complex SQL queries.

For example:

```txt
complex analytical queries
window functions
non-standard PostgreSQL features
```

Then you use:

```ts
$queryRaw
```

---

# Prisma Client Example

```ts
const users = await prisma.user.findMany();
```

---

Creating a record:

```ts
await prisma.user.create({
  data: {
    email: 'max@test.com',
  },
});
```

---

Updating:

```ts
await prisma.user.update({
  where: {
    id: 1,
  },
  data: {
    name: 'Max',
  },
});
```

---

# Pros of Prisma

- excellent typing
- autocomplete
- simple API
- migrations
- great developer experience

---

# Cons of Prisma

- an additional abstraction layer
- not always convenient for complex SQL
- raw SQL is sometimes needed

---

# Short Interview Answer

Prisma is a TypeScript-first ORM toolkit that uses a schema-first approach. The developer describes models in schema.prisma, after which Prisma generates a typed client for working with the database.
