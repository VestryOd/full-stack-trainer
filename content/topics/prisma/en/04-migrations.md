# Prisma Migrations

## Why migrations exist

A migration is a versioned change to the database schema. Without migrations, three environments (local, staging, production) gradually diverge, and deploying new code breaks because of schema mismatches. Prisma Migrate stores the change history in the `prisma/migrations/` folder under git control: each change is a separate SQL file with a timestamp.

```txt
Workflow:
  1. Edit schema.prisma
  2. npx prisma migrate dev   → generate migration.sql + apply + regenerate Client
  3. git add prisma/migrations/  → commit the migration to the repository
  4. CI/CD: npx prisma migrate deploy  → apply pending migrations to production
```

## Prisma Migrate commands

```bash
# Development — create and apply a migration (+ regenerate Client)
npx prisma migrate dev --name add_user_email
# → creates: prisma/migrations/20240101120000_add_user_email/migration.sql
# → applies SQL to the dev DB
# → runs prisma generate

# Production / CI — apply pending migrations (no generation, no interactive prompt)
npx prisma migrate deploy
# → reads prisma/migrations/ → finds unapplied ones → applies in order
# → does NOT create new migrations, does NOT modify schema.prisma

# View migration status
npx prisma migrate status
# → shows applied / pending migrations

# Prototyping — sync the DB with schema.prisma WITHOUT creating a migration file
npx prisma db push
# Use only locally for PoC — loses change history!

# Reset the DB (local only!)
npx prisma migrate reset
# → DROP all tables → apply all migrations from scratch → run seed
# NEVER run on production

# Regenerate Client without a migration
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
   │   └─ migration.sql          ← ALTER TABLE users ADD COLUMN email TEXT
   ├─ 20240201140000_add_posts/
   │   └─ migration.sql          ← CREATE TABLE posts + FK
   └─ migration_lock.toml        ← DB provider (do not edit manually)
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

```txt
Shadow Database — a temporary DB that Prisma creates during migrate dev:

1. Prisma applies ALL existing migrations to the Shadow DB
2. Applies the current schema.prisma state to the Shadow DB
3. Diffs the two → generates a new migration.sql
4. Drops the Shadow DB

Why: to generate a precise SQL diff.
Without Shadow DB: Prisma doesn't know the true current state of the DB
(there may be manual changes not reflected in the migration history).

Configuration (required for managed DBs like Supabase/PlanetScale):
datasource db {
  provider          = "postgresql"
  url               = env("DATABASE_URL")
  shadowDatabaseUrl = env("SHADOW_DATABASE_URL") // separate dev DB
}
```

## CI/CD pipeline with Prisma

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
  1. migrate deploy — BEFORE starting the new code
  2. New code must be backward-compatible with the OLD schema
     (during rollout, two instances run simultaneously: old and new code)

Safe column addition:
  Migration 1: ALTER TABLE ADD COLUMN name TEXT  (nullable — doesn't break old code)
  Deploy new code (populates name)
  Migration 2: ALTER TABLE ALTER COLUMN name SET NOT NULL  (once all rows are populated)
```

## Dangerous migrations — what to check before deploy

```sql
-- DANGEROUS: locks the table for the entire duration
ALTER TABLE users ADD COLUMN age INT NOT NULL DEFAULT 0;
-- On a 10M-row table — lock lasts minutes

-- SAFE: add nullable first, then populate, then enforce NOT NULL
ALTER TABLE users ADD COLUMN age INT;  -- migration 1: nullable, instant
-- (background job: UPDATE users SET age = 0 WHERE age IS NULL)
ALTER TABLE users ALTER COLUMN age SET NOT NULL;  -- migration 2: after population

-- DANGEROUS: renaming a field breaks running code
ALTER TABLE users RENAME COLUMN email TO email_address;
-- Correct: add new column → copy data → drop old one (3 migrations)

-- DANGEROUS: DROP COLUMN with data
ALTER TABLE users DROP COLUMN metadata;
-- Always verify the column is unused in code BEFORE the migration
```

## Seeding — test data

```typescript
// prisma/seed.ts
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
  // upsert instead of create — safe to run multiple times
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
npx prisma db seed          # run seed manually
npx prisma migrate reset    # reset + seed automatically
```

## Common interview mistakes

- **"migrate dev can be used in production"** — no. `migrate dev` creates a Shadow DB, generates new migrations, and runs interactively. For production: `migrate deploy` — only applies pending migrations without creating new ones. Always use `migrate deploy` in CI/CD.

- **"A migration file can be deleted if you change your mind"** — not if the migration has already been applied to staging/production. Deleting it breaks the history. The correct path: create a new migration that reverses the changes (a reverse migration). If the migration hasn't been applied anywhere yet — you can delete the file and `prisma migrate dev` will recreate it.

- **"db push does the same thing as migrate dev"** — no. `db push` directly modifies the DB without creating a migration file. No history, can't reproduce on another environment, not tracked in git. Use only for rapid local prototyping.

- **"A NOT NULL column can be added in one step"** — dangerous on large tables. `ADD COLUMN name TEXT NOT NULL DEFAULT 'value'` → PostgreSQL locks the table to rewrite every row. The rule: add nullable → populate with data → enforce NOT NULL. Three separate migrations with deploys in between.

- **"schema.prisma isn't the real source of truth — the DB is"** — no. In Prisma: schema.prisma is the source of truth. Migrations are the change history of the schema. The DB is the result of applying those migrations. If the DB and schema diverge (manual DB changes), `prisma migrate dev` will detect this and ask you to resolve the conflict.
