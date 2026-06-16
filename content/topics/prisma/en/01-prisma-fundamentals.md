# Prisma Fundamentals

## What Prisma is and why it exists

Prisma is a TypeScript-first ORM toolkit for Node.js. The key difference from TypeORM/Sequelize: a schema-first approach — the developer describes models in `schema.prisma`, and Prisma generates a fully typed client for that exact schema. This means `prisma.user.findMany()` returns `User[]` with all fields without extra Generic annotations, and a typo in a field name is a compile-time error, not a runtime one.

```txt
Prisma components:
  schema.prisma   — model definitions, relations, datasource, generator
  Prisma Client   — generated TypeScript API (node_modules/.prisma/client)
  Prisma Migrate  — migration system: schema.prisma → SQL → apply to DB
  Prisma Studio   — GUI for browsing and editing data (optional)

Request stack:
  NestJS Service
    ↓
  Prisma Client (TypeScript)
    ↓
  Prisma Query Engine (Rust, native binary)
    ↓
  PostgreSQL / MySQL / SQLite / SQL Server / MongoDB
```

## Minimal configuration

```prisma
// schema.prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id        Int      @id @default(autoincrement())
  email     String   @unique
  name      String?
  createdAt DateTime @default(now())
  posts     Post[]
}

model Post {
  id       Int    @id @default(autoincrement())
  title    String
  authorId Int
  author   User   @relation(fields: [authorId], references: [id])
}
```

```typescript
// Initialization (singleton in NestJS — via PrismaService)
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient({
  log: ['query', 'error'], // log SQL queries in dev
});

// CRUD — basic operations
const user = await prisma.user.create({
  data: { email: 'alice@example.com', name: 'Alice' },
});

const users = await prisma.user.findMany({
  where: { name: { not: null } },
  orderBy: { createdAt: 'desc' },
  take: 10,
  skip: 0,
});

const updated = await prisma.user.update({
  where: { id: user.id },
  data: { name: 'Alice Smith' },
});

await prisma.user.delete({ where: { id: user.id } });
```

## PrismaService in NestJS

```typescript
// prisma.service.ts — standard singleton in NestJS
import { Injectable, OnModuleInit, OnModuleDestroy } from '@nestjs/common';
import { PrismaClient } from '@prisma/client';

@Injectable()
export class PrismaService extends PrismaClient implements OnModuleInit, OnModuleDestroy {
  async onModuleInit() {
    await this.$connect();
  }

  async onModuleDestroy() {
    await this.$disconnect();
  }
}

// prisma.module.ts
@Global()
@Module({
  providers: [PrismaService],
  exports: [PrismaService],
})
export class PrismaModule {}

// users.service.ts — usage
@Injectable()
export class UsersService {
  constructor(private prisma: PrismaService) {}

  async findAll() {
    return this.prisma.user.findMany();
  }
}
```

## When Prisma fits and when it doesn't

```txt
Prisma is a good fit for:
  ✓ TypeScript projects (NestJS, Next.js, Express + TS)
  ✓ CRUD-heavy applications (SaaS, admin panels, APIs)
  ✓ Mixed-skill teams — typing reduces mistakes
  ✓ Rapid development — schema + migrate + generated client = fast
  ✓ GraphQL backends (Prisma + Pothos/Nexus = minimal boilerplate)

Prisma does NOT fit or requires workarounds:
  ✗ Complex analytical queries (window functions, CTE, LATERAL JOIN)
     → solution: prisma.$queryRaw`SELECT ... OVER (PARTITION BY ...)`
  ✗ Bulk insert/update of thousands of rows
     → createMany does not support skipDuplicates with relations;
       for bulk: $executeRaw or pg-copy-streams
  ✗ Dynamic query building with conditional JOINs
     → TypeORM QueryBuilder is more flexible for this scenario
```

## $queryRaw and $executeRaw — when you need raw SQL

```typescript
// $queryRaw — returns typed results
// Note: Prisma.sql template literal is required to prevent SQL injection
const result = await prisma.$queryRaw<{ id: number; rank: number }[]>`
  SELECT id, RANK() OVER (ORDER BY score DESC) as rank
  FROM users
  WHERE created_at > ${new Date('2024-01-01')}
`;

// $executeRaw — for UPDATE/DELETE without returning data
const count = await prisma.$executeRaw`
  UPDATE users SET last_seen = NOW() WHERE id = ${userId}
`;
// Returns the number of affected rows

// NEVER use string interpolation:
// ✗ await prisma.$queryRaw(`SELECT * FROM users WHERE id = ${userId}`) // SQL injection!
// ✓ await prisma.$queryRaw`SELECT * FROM users WHERE id = ${userId}`   // parameterized
```

## Common interview mistakes

- **"Prisma is a database"** — no. Prisma is an ORM on top of an existing DB. Data is stored by PostgreSQL/MySQL/SQLite; Prisma only generates and executes queries against it. `prisma.user.findMany()` → Prisma Client → Rust Query Engine → SQL → PostgreSQL.

- **"Prisma generates inefficient queries"** — partly true for the N+1 problem (without `include`), but Prisma can generate JOINs via `include`/`select`. For complex queries: `$queryRaw`. The generated SQL can be inspected via `log: ['query']` in PrismaClient.

- **"PrismaClient can be instantiated per request"** — no. PrismaClient manages a connection pool. In NestJS — one singleton `PrismaService extends PrismaClient`. Creating a new instance per request → connection leaks and performance degradation.

- **"Prisma Migrate and Prisma Client are the same thing"** — no. Migrate is a development tool (CLI): `prisma migrate dev` → generates SQL migrations. Client is a runtime library: executes queries against the DB. In production: run `prisma migrate deploy` (applies pending migrations); the Client is already compiled into the bundle.

- **"Changing schema.prisma immediately makes the changes available"** — no. You need: (1) `prisma migrate dev` — create the migration and apply it to the DB; (2) `prisma generate` — regenerate the Client. If you only change the schema without `generate` — TypeScript types are stale, and so is the runtime client.
