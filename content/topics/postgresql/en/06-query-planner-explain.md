# Query Planner and EXPLAIN ANALYZE

## The Most Underrated Component of PostgreSQL

Many people think:

```txt
SQL -> executes
```

---

In reality:

```txt
SQL
 ↓
Parser
 ↓
Planner
 ↓
Executor
```

---

Planner is the brain of PostgreSQL.

---

# What the Planner Does

Receives a query:

```sql
SELECT *
FROM users
WHERE email = 'max@test.com';
```

---

And decides:

```txt
how to get the result fastest
```

---

# Possible Options

For example:

```txt
Seq Scan
Index Scan
Bitmap Index Scan
Index Only Scan
```

---

Planner chooses the best.

---

# Why This Matters

The same query can run in:

```txt
5 ms
```

or

```txt
5 minutes
```

---

Depending on the chosen plan.

---

# Seq Scan

Sequential Scan.

---

The simplest option.

---

PostgreSQL reads the entire table.

---

Conceptually:

```txt
row1
row2
row3
...
row10M
```

---

Complexity:

```txt
O(n)
```

---

# When Seq Scan Is Fine

Small tables.

---

For example:

```txt
50 rows
```

---

An index would actually be slower.

---

# Index Scan

An index is used.

---

Algorithm:

```txt
find the value in the index
get the pointer
read the row
```

---

Usually:

```txt
O(log n)
```

---

# Bitmap Index Scan

Sometimes the Planner combines the index with page-level reads.

---

Especially useful when:

```txt
many matching rows
```

---

For example:

```sql
WHERE status='ACTIVE'
```

---

if there are:

```txt
100 000
```

such users.

---

# Index Only Scan

The fastest option.

---

The table is not read at all.

---

Data is taken only from the index.

---

Example:

```sql
SELECT email
FROM users
WHERE email='a@test.com';
```

---

If email is already in the index.

---

# How the Planner Knows What Is Faster

From statistics.

---

PostgreSQL collects:

```txt
row counts
value distribution
selectivity
```

---

# ANALYZE

Updates statistics.

---

Runs automatically via:

```txt
autovacuum
```

---

Or manually:

```sql
ANALYZE users;
```

---

# Selectivity

A very important topic.

---

Imagine:

```txt
users = 10M rows
```

---

Field:

```txt
country
```

---

95% of users:

```txt
USA
```

---

Query:

```sql
WHERE country='USA'
```

---

The index is useless.

---

Planner will choose:

```txt
Seq Scan
```

---

Because almost the entire table would need to be read anyway.

---

# Cost Based Optimizer

The Planner does not know the exact execution time.

---

It estimates cost.

---

Conceptually:

```txt
Seq Scan cost = 500
Index Scan cost = 200
```

---

The lower cost is chosen.

---

# EXPLAIN

Shows the execution plan.

---

Example:

```sql
EXPLAIN
SELECT *
FROM users
WHERE email='test@test.com';
```

---

Result:

```txt
Index Scan using idx_users_email
```

---

# EXPLAIN ANALYZE

The most important command.

---

It not only shows the plan.

---

It actually executes the query.

---

And shows:

```txt
actual time
rows
loops
buffers
```

---

Example:

```sql
EXPLAIN ANALYZE
SELECT *
FROM users
WHERE email='test@test.com';
```

---

# What to Look At

## Actual Time

The real execution time.

---

## Rows

How many rows were actually read.

---

## Cost

The Planner's estimate.

---

## Scan Type

Very important.

---

Look for:

```txt
Seq Scan
Index Scan
Bitmap Scan
Index Only Scan
```

---

# Why the Planner Makes Mistakes

Statistics are stale.

---

For example:

```txt
was 100 rows
became 10 million
```

---

Planner makes wrong decisions.

---

Helps:

```sql
ANALYZE;
```

---

# A Very Common Question

Why does PostgreSQL not use an index?

---

Answer:

Because the Planner determined that
the cost of using the index is higher
than the cost of a full table scan.

---

# Another Common Question

Why can a query suddenly become slow?

---

Causes:

```txt
stale statistics
table bloat
a bad plan
changed data distribution
missing index
```

---

# Senior Interview Answer

What does the Query Planner do?

The Planner analyzes a SQL query and, based on statistics, chooses the most efficient execution plan. PostgreSQL uses cost-based optimization and can choose between Sequential Scan, Index Scan, Bitmap Scan, and other data access strategies. EXPLAIN ANALYZE is used to inspect execution plans.
