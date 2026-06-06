# Prisma Interview Questions

---

# 1. What is Prisma?

Prisma is a TypeScript-first ORM toolkit that generates a typed client based on schema.prisma.

---

# 2. What is schema.prisma?

The central Prisma file.

Describes:

- datasource
- generator
- models
- relations

---

# 3. What is the source of truth?

Answer:

```txt
schema.prisma
```

---

# 4. What is Prisma Client?

The generated TypeScript API for working with the database.

---

# 5. What does Prisma Migrate do?

Generates SQL migrations from schema changes.

---

# 6. How does migrate dev differ from migrate deploy?

migrate dev:

```txt
local development
```

---

migrate deploy:

```txt
production
CI/CD
```

---

# 7. What is db push?

Updates the database structure without creating migrations.

---

# 8. Why is db push not used in production?

Because there is no history of changes.

---

# 9. What relations does Prisma support?

- One-To-One
- One-To-Many
- Many-To-Many

---

# 10. What does include do?

Loads related entities.

---

# 11. What does select do?

Limits the returned fields.

---

# 12. What is better to use for performance?

Usually:

```txt
select
```

---

rather than large includes.

---

# 13. What is connect?

Links an existing record.

---

# 14. What is connectOrCreate?

If the record exists:

```txt
connect
```

If not:

```txt
create
```

---

# 15. What are nested writes?

Creating/updating related entities in a single query.

---

# 16. How do transactions work in Prisma?

Via:

```ts
$transaction()
```

---

Database transactions are used under the hood.

---

# 17. Does Prisma protect against race conditions?

No.

---

Race conditions are resolved through:

- transactions
- locks
- constraints

at the database level.

---

# 18. What is the N+1 Problem?

One query for a list of objects
and N additional queries
for related data.

---

# 19. How to deal with N+1?

- include
- batching
- DataLoader
- proper GraphQL design

---

# 20. Why is knowledge of PostgreSQL still important?

Because Prisma generates SQL.

Performance problems
are usually at the database level.

---

# 21. When to use Raw SQL?

- complex analytical queries
- window functions
- PostgreSQL-specific features

---

# 22. How does Prisma differ from TypeORM?

Prisma:

```txt
schema-first
generated client
strong typing
```

---

TypeORM:

```txt
decorators
entities
runtime metadata
```

---

# 23. What is Shadow Database?

A temporary database
that Prisma uses
to verify migrations.

---

# 24. What is createMany?

Bulk insert of records.

Faster than a loop of create() calls.

---

# 25. What would you optimize first in a slow Prisma query?

Answer:

1. EXPLAIN ANALYZE
2. Indexes
3. include/select
4. Pagination
5. N+1
6. Raw SQL if necessary
