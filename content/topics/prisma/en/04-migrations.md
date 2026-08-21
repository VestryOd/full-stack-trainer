# Prisma Migrations

## Why migrations exist

A migration is a versioned change to the database schema. Without migrations, three environments (local, staging, production) gradually diverge, and deploying new code breaks because of schema mismatches.

Prisma Migrate stores the change history in the `prisma/migrations/` folder under git control. Each change is a separate file of SQL (Structured Query Language — the language of database queries) with a timestamp in its name.

```txt
How it works:
  1. Edit schema.prisma
  2. npx prisma migrate dev
     → create migration.sql, apply it, regenerate the client
  3. git add prisma/migrations/
     → commit the migration to the repository
  4. In CI/CD: npx prisma migrate deploy
     → apply to production whatever is not applied yet
```

## Prisma Migrate commands

```bash
# Development — create and apply a migration, regenerate the client
npx prisma migrate dev --name add_user_email
# → creates: prisma/migrations/20240101120000_add_user_email/migration.sql
# → applies the SQL to the local database
# → runs prisma generate

# Production and CI — apply migrations that are not applied yet
# (creates nothing new, asks no questions in the terminal)
npx prisma migrate deploy
# → reads prisma/migrations/ → finds unapplied ones → applies in order
# → does not create new migrations and does not touch schema.prisma

# Migration status
npx prisma migrate status
# → shows applied and pending migrations

# Prototyping — match the database to schema.prisma with no migration file
npx prisma db push
# Local drafts only (PoC, proof of concept):
# the change history is not kept!

# Reset the database (local only!)
npx prisma migrate reset
# → drop all tables → apply every migration from scratch → run seed
# Never run this on production

# Regenerate the client without a migration
npx prisma generate
# Needed after any schema.prisma change without migrate dev
```

## Migrations folder structure

```txt
prisma/
└─ migrations/
   ├─ 20240101120000_init/
   │   └─ migration.sql          ← CREATE TABLE statements
   ├─ 20240115083000_add_email/
   │   └─ migration.sql          ← ALTER TABLE users ADD COLUMN
   ├─ 20240201140000_add_posts/
   │   └─ migration.sql          ← CREATE TABLE posts + foreign key
   └─ migration_lock.toml        ← which database (never edit)
```

```sql
-- Example migration.sql
-- 20240115083000_add_email/migration.sql

-- AlterTable
ALTER TABLE "users" ADD COLUMN "email" TEXT;

-- CreateIndex
CREATE UNIQUE INDEX "users_email_key" ON "users"("email");
```

## Shadow Database — why it exists

The shadow database is a temporary database that Prisma creates while `migrate dev` runs and drops afterwards. Its job is to produce an exact diff between your schema and your migration history.

```txt
What migrate dev does:

1. Prisma applies every existing migration to the shadow database
2. Applies the current state of schema.prisma to the same database
3. Diffs the two results → writes a new migration.sql
4. Drops the shadow database

Without it, Prisma cannot know the real state of the schema:
what if someone changed the database by hand?

Configuration (required for hosted databases such as Supabase
and PlanetScale):
datasource db {
  provider          = "postgresql"
  url               = env("DATABASE_URL")
  shadowDatabaseUrl = env("SHADOW_DATABASE_URL") // a separate one
}
```

## Migrations in CI/CD

CI/CD stands for continuous integration and continuous delivery: automated build and release. In such a pipeline, migrations run as their own step, before the new code starts.

```yaml
# .github/workflows/deploy.yml
jobs:
  deploy:
    steps:
      - name: Build
        run: npm run build

      - name: Run migrations
        run: npx prisma migrate deploy
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}

      - name: Start server
        run: npm start
```

```txt
Important: the order is mandatory
  1. migrate deploy — before the new code starts, not after
  2. The new code must also work with the old schema:
     during rollout two instances live at once, old and new

How to add a column safely:
  Migration 1: ALTER TABLE ADD COLUMN name TEXT
              (allows NULL — the old code keeps working)
  Deploy the new code, which populates name
  Migration 2: ALTER TABLE ALTER COLUMN name SET NOT NULL
              (once every row is populated)
```

## Dangerous migrations — what to check before deploy

```sql
-- Dangerous: the table stays locked for the whole operation
ALTER TABLE users ADD COLUMN age INT NOT NULL DEFAULT 0;
-- On a 10-million-row table that lock lasts minutes

-- Safe: allow NULL first, then populate, then enforce NOT NULL
ALTER TABLE users ADD COLUMN age INT;  -- migration 1: instant
-- (background job: UPDATE users SET age = 0 WHERE age IS NULL)
ALTER TABLE users ALTER COLUMN age SET NOT NULL;  -- migration 2

-- Dangerous: renaming a field breaks running code
ALTER TABLE users RENAME COLUMN email TO email_address;
-- Correct: new column → copy the data → drop the old one,
-- that is, three separate migrations

-- Dangerous: DROP COLUMN with data
ALTER TABLE users DROP COLUMN metadata;
-- First make sure no code needs the column, then write the migration
```

## Seeding — test data

```typescript
// prisma/seed.ts
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
  // upsert instead of create — the seed can run many times over
  await prisma.user.upsert({
    where: { email: 'admin@example.com' },
    update: {},
    create: {
      email: 'admin@example.com',
      name: 'Admin',
      role: 'ADMIN',
    },
  });

  await prisma.user.createMany({
    data: Array.from({ length: 10 }, (_, i) => ({
      email: `user${i}@example.com`,
      name: `User ${i}`,
    })),
    skipDuplicates: true,
  });
}

main().finally(() => prisma.$disconnect());
```

```json
// package.json
{
  "prisma": {
    "seed": "ts-node prisma/seed.ts"
  }
}
```

```bash
npx prisma db seed          # load the test data by hand
npx prisma migrate reset    # reset the database, seed runs by itself
```

## Common interview mistakes

- **"migrate dev can be used in production"** — no. `migrate dev` creates a shadow database, generates new migrations, and asks questions in the terminal. Production has `migrate deploy`: it only applies migrations that are not applied yet, and creates none. In CI/CD, always `migrate deploy`.

- **"A migration file can be deleted if you change your mind"** — not once the migration is applied on staging or production. Deleting the file breaks the history. The correct path is a new migration that undoes the change (a reverse migration). If the migration has never been applied anywhere, you can delete the file and `prisma migrate dev` will recreate it.

- **"db push does the same thing as migrate dev"** — no. `db push` changes the database directly and writes no migration file. So there is no history, no way to reproduce it on another environment, and nothing to see in git. Use it only for a quick prototype on your own machine.

- **"A `NOT NULL` column can be added in one step"** — on large tables that is dangerous. `ADD COLUMN name TEXT NOT NULL DEFAULT 'value'` makes PostgreSQL lock the table and rewrite every row. The rule: add the column allowing `NULL` → populate it → then enforce `NOT NULL`. That is three separate migrations with deploys in between.

- **"schema.prisma isn't the real source of truth — the database is"** — no. In Prisma the source of truth is `schema.prisma`. Migrations are the history of its changes, and the database is the result of applying them. If the two diverge because of manual edits, `prisma migrate dev` detects it and asks you to resolve the conflict.
