# PostgreSQL Indexes Internals

## What is an Index

An index is an additional data structure
that speeds up row lookups.

---

Without an index:

```sql
SELECT *
FROM users
WHERE email = 'max@test.com';
```

PostgreSQL performs:

```txt
Full Table Scan
```

---

That means:

```txt
row 1
row 2
row 3
...
row 10 000 000
```

---

Complexity:

```txt
O(n)
```

---

# What an Index Does

Creates a separate data structure.

Simplified:

```txt
email
 ↓
row location
```

---

Then searching becomes:

```txt
O(log n)
```

instead of

```txt
O(n)
```

---

# Why an Index Speeds Up Search

Think of a book.

---

Without an index:

```txt
search word by word through every page
```

---

With an index:

```txt
open the table of contents
```

---

The principle is exactly the same.

---

# The Most Important PostgreSQL Index

B-Tree

Used by default.

---

# How B-Tree Looks

Simplified:

```txt
            [50]
          /      \
      [20]       [80]
     /   \      /    \
 [10] [30] [70] [90]
```

---

Each node contains a range of values.

---

Search:

```txt
50?
 ↓
less
 ↓
20?
 ↓
greater
 ↓
30
```

---

The number of steps grows logarithmically.

---

# Why O(log n)

Assume:

```txt
1 000 000 rows
```

---

Full Scan:

```txt
up to one million checks
```

---

B-Tree:

```txt
approximately 20 steps
```

---

Because:

```txt
log₂(1 000 000)
≈ 20
```

---

# Where B-Tree Works Well

Great for:

```sql
=
<
>
<=
>=
BETWEEN
ORDER BY
```

---

Example:

```sql
WHERE created_at > now()
```

---

or

```sql
ORDER BY created_at
```

---

# Composite Index

Multiple fields can be indexed together.

---

Example:

```sql
CREATE INDEX idx_users_name_age
ON users(name, age);
```

---

The index stores:

```txt
(name, age)
```

---

Very important rule:

Left Prefix Rule

---

Index:

```txt
(name, age)
```

works for:

```sql
WHERE name = ...
```

works for:

```sql
WHERE name = ... AND age = ...
```

---

But does NOT work efficiently for:

```sql
WHERE age = ...
```

---

This is one of interviewers' favorite questions.

---

# Why an Index Might Not Be Used

Because the Planner evaluates cost.

---

Example

Table:

```txt
100 rows
```

---

Query:

```sql
WHERE is_active = true
```

---

If:

```txt
95% of rows have true
```

then the index is useless.

---

Faster to do:

```txt
Sequential Scan
```

---

# EXPLAIN ANALYZE

Used for verification.

---

Example:

```sql
EXPLAIN ANALYZE
SELECT *
FROM users
WHERE email = 'test@test.com';
```

---

You can see:

```txt
Index Scan
```

or

```txt
Seq Scan
```

---

# Downsides of Indexes

Indexes are not free.

---

Every INSERT:

```sql
INSERT ...
```

updates the index.

---

Every UPDATE:

```sql
UPDATE ...
```

may update the index.

---

Every DELETE:

```sql
DELETE ...
```

also updates the index.

---

Therefore:

```txt
many indexes
=
slower writes
```

---

# Covering Index

PostgreSQL can return data
without reading the table at all.

---

Called:

```txt
Index Only Scan
```

---

Example:

Index contains:

```txt
email
id
```

---

Query:

```sql
SELECT id
FROM users
WHERE email = ...
```

---

The table may not be read at all.

---

# Partial Indexes

A very powerful PostgreSQL feature.

---

Example:

```sql
CREATE INDEX idx_active_users
ON users(email)
WHERE is_active = true;
```

---

The index contains only active users.

---

Smaller size.

Works faster.

---

# GIN Index

Used for:

```txt
JSONB
Arrays
Full Text Search
```

---

Example:

```sql
CREATE INDEX idx_settings
ON users
USING GIN(settings);
```

---

# Why GIN is Needed for JSONB

Suppose:

```json
{
  "theme": "dark"
}
```

---

GIN indexes the JSON content.

---

And allows fast execution of:

```sql
WHERE settings @> '{"theme":"dark"}'
```

---

# Hash Index

Optimized for:

```sql
=
```

---

Rarely used.

B-Tree is usually better.

---

# GiST

Used for:

```txt
geodata
ranges
PostGIS
```

---

# BRIN

Very useful for very large tables.

---

For example:

```txt
logging
metrics
telemetry
```

---

Stores information about ranges of pages.

---

Index size is very small.

---

# Interview Question

Why does an index speed up search?

Answer:

Because PostgreSQL uses data structures
(usually B-Tree),
which allow searching in O(log n)
instead of a full table scan O(n).

---

# Interview Question

Why can an index hurt performance?

Answer:

Because the index must be maintained.

Every INSERT, UPDATE, and DELETE
requires updating the index structures.
So the read speedup always comes at the cost
of slower writes.
