# Prisma Schema and Models

## schema.prisma structure

`schema.prisma` is the single source of truth for the database structure in a Prisma project. What is not in this file does not exist for Prisma.

The file is made of three kinds of block:

- `datasource` — which database to connect to;
- `generator` — what to generate from the schema;
- `model` — the definition of one table.

```prisma
// schema.prisma — full structure

generator client {
  provider = "prisma-client-js"
  // output = "../src/generated/client" // optional custom output path
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
  // shadowDatabaseUrl = env("SHADOW_DATABASE_URL") // for migrate dev on a prod database
}

// Enum — a type shared by multiple models
enum UserRole {
  ADMIN
  EDITOR
  VIEWER
}

model User {
  id        String   @id @default(uuid())         // primary key: UUID v4
  email     String   @unique                        // UNIQUE constraint
  name      String?                                 // may be NULL
  role      UserRole @default(VIEWER)
  isActive  Boolean  @default(true)
  score     Decimal  @default(0) @db.Decimal(10, 2) // exact decimals for money
  metadata  Json?                                   // JSON field (jsonb in PostgreSQL)

  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt                     // Prisma sets this itself

  posts     Post[]   // one-to-many: a User has many Posts
  profile   Profile? // one-to-one: a User has one Profile, or none

  @@index([email, createdAt])                      // composite index
  @@map("users")                                   // table name (else it is "User")
}
```

## Data types and their equivalents in SQL

Every Prisma type becomes a concrete column type in SQL — the language Prisma uses to talk to the database. The mapping below is for PostgreSQL.

```prisma
// Prisma types → PostgreSQL types
String    → TEXT (or VARCHAR with @db.VarChar(255))
Int       → INTEGER
BigInt    → BIGINT
Float     → DOUBLE PRECISION
Decimal   → DECIMAL / NUMERIC — use for money, not Float!
Boolean   → BOOLEAN
DateTime  → TIMESTAMP WITH TIME ZONE
Json      → JSONB (PostgreSQL) / JSON (MySQL)
Bytes     → BYTEA — for binary data
String[]  → TEXT[] — arrays (PostgreSQL only)

// @db modifiers — narrow the type at the database level
email  String @db.VarChar(255)    // limit length
price  Decimal @db.Decimal(10, 2) // 10 digits, 2 decimal places
bio    String @db.Text            // explicit TEXT (not VARCHAR)
```

## Field attributes

```prisma
model Product {
  // Primary keys
  id     Int    @id @default(autoincrement())  // SERIAL / INTEGER
  uuid   String @id @default(uuid())           // UUID v4: 128 random bits
  cuid   String @id @default(cuid())           // CUID: short, collision-free id

  // Constraints
  sku    String @unique
  email  String @unique

  // Defaults
  status String @default("active")
  count  Int    @default(0)
  flag   Boolean @default(false)
  createdAt DateTime @default(now())           // NOW() in SQL
  updatedAt DateTime @updatedAt                // set on every update

  // Renaming
  productName String @map("product_name")      // camelCase in TS, snake_case in the DB
}
```

## Composite constraints at the model level

```prisma
model OrderItem {
  orderId   Int
  productId Int
  quantity  Int

  order   Order   @relation(fields: [orderId], references: [id])
  product Product @relation(fields: [productId], references: [id])

  @@id([orderId, productId])       // composite primary key (a join table)
  @@unique([orderId, productId])   // composite UNIQUE (alternative to @@id)
  @@index([productId])             // index on the foreign key — matters for speed
  @@map("order_items")
}
```

## Indexes — when and why

```prisma
model Post {
  id        Int      @id @default(autoincrement())
  title     String
  slug      String   @unique             // automatically creates an index
  authorId  Int
  status    String   @default("draft")
  createdAt DateTime @default(now())

  // Explicit indexes — for fields used in WHERE/ORDER BY
  @@index([authorId])                          // always index foreign keys
  @@index([status, createdAt(sort: Desc)])     // composite with sort direction
}
```

```txt
Rule: always index
  ✓ foreign key fields (authorId, userId, orderId)
  ✓ fields in frequent WHERE conditions (status, type, isActive)
  ✓ fields in ORDER BY, when WHERE already has other conditions
  ✗ but not low-cardinality boolean fields, that is, fields with
     only two values (isActive = true/false)
     → the planner usually ignores such an index and reads the
       whole table instead (a sequential scan, or seq scan)
```

## Enum — when to prefer String

```prisma
enum OrderStatus {
  PENDING
  CONFIRMED
  SHIPPED
  DELIVERED
  CANCELLED
}

model Order {
  id     Int         @id @default(autoincrement())
  status OrderStatus @default(PENDING)
}
```

```typescript
// TypeScript: Prisma exports the enum as an object
import { OrderStatus } from '@prisma/client';

const orders = await prisma.order.findMany({
  where: { status: OrderStatus.PENDING },
});

// But: PostgreSQL Enum is hard to change in migrations (can't remove a value)
// Alternative: String + @db.VarChar(50) — more flexible when values change frequently
```

## Common interview mistakes

- **"Prisma automatically uses any table name"** — no. By default the model `User` becomes the table `"User"`: quoted, and case-sensitive on PostgreSQL. If you want `snake_case`, add `@@map("users")`. Without `@@map` on PostgreSQL you can hit errors as soon as someone creates the same table without quotes.

- **"Float is fine for prices"** — no. `Float` is a binary floating-point number (the IEEE 754 standard), and `0.1` has no exact binary form. That is where `0.1 + 0.2 = 0.30000000000000004` comes from. For money use `Decimal @db.Decimal(10, 2)` in the schema plus `Decimal.js`, or store cents in an `Int`. `Float` is never right for financial maths.

- **"@updatedAt always updates automatically"** — it updates on any `update` through Prisma, but not on `$executeRaw`. Change a row with raw SQL and `updatedAt` keeps its old value. Note too that Prisma Client sets the value, not a trigger inside the database.

- **"Indexing every field speeds up queries"** — no. Indexes slow down `INSERT` and `UPDATE`, because every write must update the index as well. Extra indexes waste space, slow writes, and may still be ignored by the planner. Index only the fields that really appear in `WHERE`, `JOIN` or `ORDER BY`.

- **"UUID is always better than autoincrement"** — it depends. A UUID (universally unique identifier) is a 128-bit random value. Nobody can guess the next one from the previous one, which makes it safer for public APIs. It can also be generated on the client, and it makes merging data from several databases easy.

  `autoincrement` has different strengths. It is more compact: 4 bytes against 16. It also gives better locality in B-tree indexes — new rows land at the end of the index instead of in random places. Use `autoincrement` for internal ids and `JOIN`s, and `uuid` for public resources.
