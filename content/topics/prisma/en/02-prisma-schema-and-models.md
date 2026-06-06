# Prisma Schema and Models

## The Main Prisma File

The entire project revolves around:

```txt
schema.prisma
```

---

# Structure of schema.prisma

Usually consists of:

```prisma
datasource db {}

generator client {}

model User {}
```

---

# Datasource

Describes the database connection.

Example:

```prisma
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}
```

---

# Generator

Generates the Prisma Client.

```prisma
generator client {
  provider = "prisma-client-js"
}
```

---

# Model

Describes a table.

Example:

```prisma
model User {
  id    Int
  email String
}
```

---

# How Prisma Converts a Model into a Table

Model:

```prisma
model User {
  id    Int    @id
  email String
}
```

---

Becomes approximately:

```sql
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  email TEXT NOT NULL
);
```

---

# Core Types

## String

```prisma
name String
```

---

## Int

```prisma
age Int
```

---

## Boolean

```prisma
active Boolean
```

---

## DateTime

```prisma
createdAt DateTime
```

---

## Float

```prisma
price Float
```

---

## Json

```prisma
settings Json
```

---

# Nullable Fields

Denoted with:

```prisma
String?
```

---

Example:

```prisma
middleName String?
```

---

SQL equivalent:

```sql
NULL
```

---

# Primary Key

```prisma
id Int @id
```

---

# Auto Increment

```prisma
id Int @id @default(autoincrement())
```

---

SQL:

```sql
SERIAL
```

---

# UUID

Very popular.

```prisma
id String @id @default(uuid())
```

---

# Unique

```prisma
email String @unique
```

---

SQL:

```sql
UNIQUE(email)
```

---

# Default

```prisma
createdAt DateTime @default(now())
```

---

# UpdatedAt

A very popular feature.

```prisma
updatedAt DateTime @updatedAt
```

---

Prisma updates this field automatically.

---

# Enum

Example:

```prisma
enum UserRole {
  ADMIN
  USER
}
```

---

Usage:

```prisma
role UserRole
```

---

# Indexes

Simple index:

```prisma
@@index([email])
```

---

Composite index:

```prisma
@@index([email, createdAt])
```

---

Unique composite index:

```prisma
@@unique([userId, roleId])
```

---

# Mapping

Sometimes the model name differs from the table name.

---

For example:

```prisma
model User {
  id Int @id
  @@map("users")
}
```

---

# Fields Can Be Renamed Too

```prisma
email String @map("email_address")
```

---

# Complete Model

```prisma
model User {
  id        String   @id @default(uuid())
  email     String   @unique
  name      String?
  isActive  Boolean  @default(true)

  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  @@index([email])
}
```

---

# What Happens After Changing the Schema

We change:

```prisma
name String?
```

---

Run:

```bash
npx prisma migrate dev
```

---

Prisma:

1. Compares the schema
2. Generates SQL
3. Creates a migration
4. Applies changes
5. Generates a new Prisma Client

---

# A Common Question

What is the source of truth?

Answer:

schema.prisma.

The schema is considered the primary description of the data structure.

---

# Short Interview Answer

schema.prisma is the central Prisma file. It describes models, relations, datasource, and client generation settings. Based on schema.prisma, Prisma creates migrations and generates a fully typed Prisma Client.
