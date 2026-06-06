# PostgreSQL Interview Questions (Middle → Senior)

---

# 1. What is PostgreSQL?

### Answer

PostgreSQL is an object-relational DBMS (RDBMS) that supports ACID transactions, MVCC, extended data types, indexes, JSONB, and complex SQL queries.

PostgreSQL is suitable for both classic relational data and semi-structured data via JSONB.

---

# 2. What is a Primary Key?

### Answer

A Primary Key is a unique identifier for a row.

Guarantees:

- uniqueness
- NOT NULL

Example:

```sql
id UUID PRIMARY KEY
```

---

# 3. What is a Foreign Key?

### Answer

A Foreign Key links tables together.

Example:

```sql
user_id REFERENCES users(id)
```

Guarantees referential integrity.

That is, you cannot create a record
referencing a non-existent user.

---

# 4. What types of relationships exist?

### Answer

One-To-One

```txt
User → Profile
```

One-To-Many

```txt
User → Posts
```

Many-To-Many

```txt
Users ↔ Roles
```

Usually through a join table.

---

# 5. What is normalization?

### Answer

Normalization is the process of eliminating data duplication.

For example, instead of:

```txt
post_author_name
post_author_email
```

we use:

```txt
posts.user_id
```

and a separate users table.

---

# 6. What is denormalization?

### Answer

Intentional data duplication for performance.

For example:

```txt
order.total_price
```

can be stored in the table,
instead of recalculating via JOIN.

---

# 7. What is a transaction?

### Answer

A transaction is a group of operations
that executes as a single unit.

Either all operations complete:

```sql
COMMIT;
```

Or none:

```sql
ROLLBACK;
```

---

# 8. What does ACID stand for?

### Answer

Atomicity

Either all or nothing.

Consistency

Data remains correct.

Isolation

Transactions do not interfere with each other.

Durability

After COMMIT, data will not be lost.

---

# 9. What is MVCC?

### Answer

MVCC (Multi-Version Concurrency Control) —
PostgreSQL's concurrency mechanism.

Instead of modifying a row, a new version of the row is created.

This allows:

```txt
readers don't block writers
writers don't block readers
```

---

# 10. Why does PostgreSQL perform well under load?

### Answer

The main reason is MVCC.

Reads typically do not block writes,
and writes do not block reads.

Also helps:

- indexes
- planner
- vacuum
- connection pooling

---

# 11. What is a Dirty Read?

### Answer

Reading data from an uncommitted transaction.

PostgreSQL does not allow Dirty Reads.

Even Read Uncommitted behaves as Read Committed.

---

# 12. What is a Non-Repeatable Read?

### Answer

The same SELECT within a transaction
returns different values.

---

# 13. What is a Phantom Read?

### Answer

A repeated query returns new rows
that appeared after the first SELECT.

---

# 14. What isolation levels does PostgreSQL have?

### Answer

Read Committed

The default.

Repeatable Read

All SELECTs work with one snapshot.

Serializable

Maximum isolation.

---

# 15. What isolation level is used by default?

### Answer

Read Committed.

---

# 16. How does Repeatable Read differ from Read Committed?

### Answer

Read Committed:

each SELECT can see new commits.

Repeatable Read:

the entire transaction works with one data snapshot.

---

# 17. What is Serializable?

### Answer

The strictest isolation level.

PostgreSQL behaves as if
transactions executed sequentially.

On conflict, one transaction is terminated with an error:

```txt
could not serialize access
```

---

# 18. What is an index?

### Answer

An index is an additional data structure
that speeds up row lookups.

Allows searching in:

```txt
O(log n)
```

instead of:

```txt
O(n)
```

---

# 19. What index does PostgreSQL use by default?

### Answer

B-Tree.

---

# 20. Why is searching by index faster?

### Answer

Because B-Tree allows searching logarithmically.

For:

```txt
1 000 000 rows
```

it takes approximately:

```txt
20 steps
```

instead of a full table scan.

---

# 21. What indexes do you know in PostgreSQL?

### Answer

B-Tree

The primary index.

GIN

JSONB, Full Text Search.

GiST

Geodata.

Hash

Equality search.

BRIN

Very large tables.

---

# 22. What is a Composite Index?

### Answer

An index on multiple columns.

Example:

```sql
(name, age)
```

---

# 23. What is the Left Prefix Rule?

### Answer

For an index:

```sql
(name, age)
```

the index works for:

```sql
WHERE name = ...
```

and

```sql
WHERE name = ... AND age = ...
```

But is usually inefficient for:

```sql
WHERE age = ...
```

---

# 24. Why might PostgreSQL not use an index?

### Answer

The Planner estimates cost.

If the selectivity is too low,
an index may be slower
than a full table scan.

---

# 25. What is EXPLAIN?

### Answer

Shows the query execution plan.

---

# 26. How does EXPLAIN differ from EXPLAIN ANALYZE?

### Answer

EXPLAIN shows the estimated plan.

EXPLAIN ANALYZE actually executes the query
and shows actual values.

---

# 27. What is Seq Scan?

### Answer

Sequential Scan.

Full pass through the table.

---

# 28. What is Index Scan?

### Answer

Search via index.

Usually used for point queries.

---

# 29. What is Index Only Scan?

### Answer

PostgreSQL retrieves data only from the index,
without reading the table itself.

This is one of the fastest execution options.

---

# 30. What is Bitmap Scan?

### Answer

A hybrid option.

Used when a large number of rows match.

---

# 31. What is VACUUM?

### Answer

Cleans up dead tuples
left behind by MVCC.

---

# 32. What is Autovacuum?

### Answer

A background PostgreSQL process
that automatically runs VACUUM and ANALYZE.

---

# 33. Why should you not disable Autovacuum?

### Answer

The following appear:

- dead tuples
- table bloat
- index bloat

Over time, performance degrades significantly.

---

# 34. What is a dead tuple?

### Answer

An old row version
that is no longer needed by any transaction.

---

# 35. What is table bloat?

### Answer

Table growth caused by accumulation of dead tuples.

---

# 36. What is FOR UPDATE?

### Answer

Takes a row-level lock.

Example:

```sql
SELECT *
FROM accounts
WHERE id = 1
FOR UPDATE;
```

Used to prevent race conditions.

---

# 37. What is a deadlock?

### Answer

Two transactions are waiting for each other.

Example:

```txt
A holds row1
waits for row2

B holds row2
waits for row1
```

PostgreSQL automatically terminates one of them.

---

# 38. What is JSONB?

### Answer

PostgreSQL's binary JSON format.

Supports:

- indexing
- fast search
- JSON operations

Usually preferred over JSON.

---

# 39. What is a Connection Pool?

### Answer

A mechanism for reusing database connections.

Creating a connection is expensive,
so applications use a connection pool.

---

# 40. The Most Common Senior Question

Why is PostgreSQL able to handle large numbers of concurrent transactions without total locks?

### Answer

Thanks to MVCC.

UPDATE creates a new version of a row,
rather than modifying the existing one.

Therefore reads and writes typically do not block each other,
and old row versions are cleaned up via VACUUM.
