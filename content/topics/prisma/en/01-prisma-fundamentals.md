# Prisma Fundamentals

## What Prisma is and why it exists

Prisma is a TypeScript-first ORM toolkit for Node.js. An ORM (object-relational mapping) is the layer that turns TypeScript calls into SQL, the query language the database speaks.

The key difference from TypeORM and Sequelize is the order of work: schema first, code second. You describe the models in `schema.prisma`, and Prisma generates a client typed for that exact schema.

What that buys you: `prisma.user.findMany()` returns `User[]` with all fields, and you write no extra Generic annotations. A typo in a field name becomes a compile-time error instead of a runtime one.

```txt
Prisma components:
  schema.prisma   — models, relations, datasource, generator
  Prisma Client   — generated TypeScript API
                    (node_modules/.prisma/client)
  Prisma Migrate  — migrations: schema.prisma → SQL → database
  Prisma Studio   — a graphical browser and editor for the data

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

// CRUD — create, read, update, delete
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
  ✓ apps that are mostly CRUD — create, read, update, delete
     (SaaS products, admin panels, APIs)
  ✓ mixed-skill teams — typing reduces mistakes
  ✓ a fast start: schema + migrate + generated client
  ✓ GraphQL backends (Prisma + Pothos/Nexus = little glue code)

Prisma does not fit, or needs a workaround:
  ✗ complex analytical queries: window functions,
     CTE (common table expressions), LATERAL JOIN
     → use prisma.$queryRaw`SELECT ... OVER (PARTITION BY ...)`
  ✗ bulk insert or update of thousands of rows
     → createMany does not support skipDuplicates with relations;
       for bulk work: $executeRaw or pg-copy-streams
  ✗ dynamic query building with conditional JOINs
     → TypeORM QueryBuilder is more flexible here
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

// Never use string interpolation:
// ✗ await prisma.$queryRaw(`SELECT * FROM users WHERE id = ${userId}`) // SQL injection!
// ✓ await prisma.$queryRaw`SELECT * FROM users WHERE id = ${userId}`   // parameterized
```

## Common interview mistakes

- **"Prisma is a database"** — no. Prisma is an ORM on top of a database that already exists. PostgreSQL, MySQL or SQLite stores the data; Prisma only builds and runs the queries. The path of one call: `prisma.user.findMany()` → Prisma Client → Rust Query Engine → SQL → PostgreSQL.

- **"Prisma generates inefficient queries"** — partly true for the N+1 problem, where a list of N rows costs N+1 queries. It has a fix: `include` and `select` make Prisma emit a `JOIN`. For complex queries there is still `$queryRaw`. To see what actually reaches the database, set `log: ['query']` in `PrismaClient`.

- **"PrismaClient can be instantiated per request"** — no. `PrismaClient` owns a connection pool, and every new instance opens its own. NestJS needs one shared instance: `PrismaService extends PrismaClient`. A new instance per request means leaked connections and slower responses.

- **"Prisma Migrate and Prisma Client are the same thing"** — no. Migrate is a developer tool you run in the terminal: `prisma migrate dev` generates SQL migrations. Client is a library that runs at runtime and queries the database. Production runs `prisma migrate deploy`, which applies migrations that are not applied yet. By then the Client is already compiled into the bundle.

- **"Changing schema.prisma immediately makes the changes available"** — no, two steps are needed:
  - `prisma migrate dev` — create the migration and apply it to the database;
  - `prisma generate` — regenerate the Client.

  Change the schema without `generate`, and both the TypeScript types and the client code stay stale.
