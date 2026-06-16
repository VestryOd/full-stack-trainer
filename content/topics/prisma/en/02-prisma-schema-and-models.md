# Prisma Schema and Models

## schema.prisma structure

`schema.prisma` is the single source of truth for the database structure in a Prisma project. It consists of three blocks: datasource (DB connection), generator (what to generate), and model (table definitions).

```prisma
// schema.prisma — full structure

generator client {
  provider = "prisma-client-js"
  // output = "../src/generated/client" // optional custom output path
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
  // shadowDatabaseUrl = env("SHADOW_DATABASE_URL") // required for migrate dev against a prod DB
}

// Enum — a type shared by multiple models
enum UserRole {
  ADMIN
  EDITOR
  VIEWER
}

model User {
  id        String   @id @default(uuid())         // UUID primary key
  email     String   @unique                        // UNIQUE constraint
  name      String?                                 // nullable (NULL in SQL)
  role      UserRole @default(VIEWER)
  isActive  Boolean  @default(true)
  score     Decimal  @default(0) @db.Decimal(10, 2) // precise decimal for money
  metadata  Json?                                   // JSON field (PostgreSQL jsonb)

  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt                     // Prisma updates automatically

  posts     Post[]   // one-to-many: a User has many Posts
  profile   Profile? // one-to-one: a User has one Profile (optional)

  @@index([email, createdAt])                      // composite index
  @@map("users")                                   // table name in DB (default = "User")
}
```

## Data types and their SQL equivalents

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

// @db modifiers — narrow the DB-level type
email  String @db.VarChar(255)    // limit length
price  Decimal @db.Decimal(10, 2) // 10 digits, 2 decimal places
bio    String @db.Text            // explicit TEXT (not VARCHAR)
```

## Field attributes

```prisma
model Product {
  // Primary Keys
  id     Int    @id @default(autoincrement())  // SERIAL / INTEGER
  uuid   String @id @default(uuid())           // UUID v4
  cuid   String @id @default(cuid())           // CUID — collision-resistant ID

  // Constraints
  sku    String @unique
  email  String @unique

  // Defaults
  status String @default("active")
  count  Int    @default(0)
  flag   Boolean @default(false)
  createdAt DateTime @default(now())           // NOW() in SQL
  updatedAt DateTime @updatedAt                // update trigger

  // Mapping
  productName String @map("product_name")      // camelCase in TS, snake_case in DB
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

  @@id([orderId, productId])       // composite Primary Key (many-to-many join table)
  @@unique([orderId, productId])   // composite UNIQUE (alternative to @@id)
  @@index([productId])             // index on foreign key (important for performance)
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
  @@index([authorId])                          // always index FK fields
  @@index([status, createdAt(sort: Desc)])     // composite with sort direction
}
```

```txt
Rule: always index:
  ✓ Foreign key fields (authorId, userId, orderId)
  ✓ Fields in frequent WHERE conditions (status, type, isActive)
  ✓ Fields in ORDER BY when other WHERE conditions are already present
  ✗ Do NOT index low-cardinality boolean fields (isActive = true/false)
     → the query planner often ignores such an index and does a seq scan
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

- **"Prisma automatically uses any table name"** — no. By default: model `User` → table `"User"` (quoted, case-sensitive in PostgreSQL). For `snake_case`: always add `@@map("users")`. Without `@@map` on PostgreSQL, errors can occur when someone creates a table without quotes.

- **"Float is fine for prices"** — no. `Float` is IEEE 754 floating point and introduces rounding errors: `0.1 + 0.2 = 0.30000000000000004`. For money: `Decimal @db.Decimal(10, 2)` in the schema + `Decimal.js`, or store amounts in cents as `Int`. Never use Float for financial calculations.

- **"@updatedAt always updates automatically"** — it updates on any Prisma `update` operation, but NOT on `$executeRaw`. If you update via raw SQL, `updatedAt` will not be updated. Also: `@updatedAt` is set on the Prisma Client side, not via a DB trigger.

- **"Indexing every field speeds up queries"** — no. Indexes slow down INSERT/UPDATE (the index structure must be updated). Excessive indexes: waste space, slow down writes, and may be ignored by the query planner. Only index fields that appear in real `WHERE`/`JOIN`/`ORDER BY` queries.

- **"UUID is always better than autoincrement"** — it depends. UUID: no predictable sequence (safer for public APIs), can be generated client-side, convenient for merging data from multiple DBs. Autoincrement: more compact (4 bytes vs 16), better locality for B-tree indexes (new rows at the end). For internal IDs + JOINs: `autoincrement`. For public resources: `uuid`.
