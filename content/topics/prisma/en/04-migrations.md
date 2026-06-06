# Prisma Migrations

## What is a Migration

A migration is a versioned record of database schema changes.

---

For example:

Before:

```prisma
model User {
  id Int @id
}
```

---

After:

```prisma
model User {
  id Int @id

  email String
}
```

---

The database structure needs to be updated.

---

# Why Migrations Are Needed

Without migrations:

```txt
local database
staging
production
```

will start to diverge.

---

Migrations allow you to guarantee an identical schema.

---

# The Main Idea

Schema

↓

Migration

↓

SQL

↓

Database

---

# migrate dev

The main development command.

---

```bash
npx prisma migrate dev
```

---

What happens:

1. Prisma reads schema.prisma
2. Compares with the current database state
3. Generates SQL
4. Creates a migration file
5. Runs the migration
6. Updates the Prisma Client

---

# Example

Added a field:

```prisma
email String
```

---

Prisma will create:

```sql
ALTER TABLE users
ADD COLUMN email TEXT;
```

---

# Migration Folder

The following will appear:

```txt
prisma/
 └─ migrations/
     └─ 20250101120000_add_email/
```

---

Inside:

```sql
migration.sql
```

---

# Why This Is Good

SQL remains under control.

---

You can inspect:

```sql
ALTER TABLE ...
```

---

And understand what will actually change.

---

# migrate deploy

The production command.

---

```bash
npx prisma migrate deploy
```

---

Used on:

```txt
CI/CD
Production
Docker
```

---

# Important

In production, you typically do NOT use:

```bash
migrate dev
```

---

Only:

```bash
migrate deploy
```

---

# db push

A very common interview question.

---

```bash
npx prisma db push
```

---

The difference:

```txt
updates the database
BUT
does not create a migration
```

---

Useful for:

```txt
prototypes
local development
PoC
```

---

Not recommended for production.

---

# migrate reset

Fully recreates the database.

---

```bash
npx prisma migrate reset
```

---

Does:

```txt
DROP DATABASE
CREATE DATABASE
apply migrations
run seed
```

---

Used only locally.

---

# Shadow Database

A very popular senior interview question.

---

Prisma uses a temporary database
to verify migrations.

---

Called:

```txt
Shadow Database
```

---

It is needed to:

```txt
verify migration history
detect conflicts
evaluate the diff
```

---

# Why the Shadow DB Matters

Without it, you could accidentally
generate an incorrect migration.

---

# What Happens in CI/CD

Typically:

```bash
npm run build

npx prisma migrate deploy

npm start
```

---

# What to Do If a Migration Fails in Production

A very common question.

---

You must NOT:

```txt
delete migrations manually
```

---

The correct approach:

1. fix the problem
2. create a new migration
3. apply the new migration

---

# Seed

Prisma supports populating the database with test data.

---

Example:

```bash
npx prisma db seed
```

---

Used for:

```txt
users
roles
permissions
demo data
```

---

# Migration Best Practices

Do not delete old migrations.

---

Each migration should be:

```txt
small
clear
atomic
```

---

Always review the generated SQL.

---

Especially if it contains:

```txt
DROP COLUMN
DROP TABLE
ALTER TYPE
```

---

# A Common Question

What is the source of truth?

---

Answer:

```txt
schema.prisma
```

---

Not the database.

Not the migrations folder.

---

schema.prisma is.

---

# Interview Answer

Prisma Migrate is a database schema version control system. Changes are described in schema.prisma, after which Prisma generates SQL migrations that can be applied locally via migrate dev and in production via migrate deploy.
