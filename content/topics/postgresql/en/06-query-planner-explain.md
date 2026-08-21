# Query Planner and EXPLAIN ANALYZE

## The Planner — PostgreSQL's most complex component, responsible for the difference between 5 ms and 5 minutes

SQL (Structured Query Language) is a declarative language: you describe **what** you want, not **how** to get it. The job of the Planner, also called the Optimizer, is to turn that declarative "what" into a concrete execution plan. It decides which indexes to use, in what order to scan tables, and which `JOIN` algorithm to apply.

Two stages in the pipeline below have names worth unpacking first. The Parser produces an AST (abstract syntax tree — the parsed, tree-shaped form of your query text). The Rewriter then applies rules to that tree. One of those rules is RLS (row-level security — per-row access policies attached to a table), and it silently adds conditions to your query.

```txt
SQL text
    │  Parser: AST
    ↓
Query Tree
    │  Rewriter: VIEW expansion, RLS
    ↓
Logical Plan
    │  Planner: enumerate plans, estimate cost of each
    ↓
Best Physical Plan
    │  Executor: runs it
    ↓
Result
```

## Cost model — what the Planner actually estimates

The PostgreSQL Planner is a cost-based optimizer. It does not know how long a plan will really take. Instead it estimates the "cost" of every candidate plan in abstract units, then picks the plan with the lowest estimate.

The unit itself is a setting. Reading one page sequentially costs 1.0 by definition, and every other parameter is priced relative to that.

| Parameter | Default | What it prices |
|---|---|---|
| `seq_page_cost` | 1.0 | Reading one page during a Sequential Scan — the base unit |
| `random_page_cost` | 4.0 | Reading one page by random access, as an Index Scan does |
| `cpu_tuple_cost` | 0.01 | Processing one row |
| `cpu_index_tuple_cost` | 0.005 | Processing one index entry |
| `cpu_operator_cost` | 0.0025 | Evaluating one operator or function call |

The cost of a plan is the sum of all its disk reads and all its row processing, each weighted by the parameters above.

The default `random_page_cost = 4.0` was chosen for spinning disks. On the wrong hardware it distorts every plan:

- On an HDD (hard disk drive — a spinning magnetic disk) a random read costs 10-100x more than a sequential read. There 4.0 is about right.
- On an SSD (solid-state drive — flash memory, no moving parts) a random read costs only about 2x more. There the value should come down to 1.1-2.0.

```sql
ALTER SYSTEM SET random_page_cost = 1.1;  -- for SSD/NVMe
SELECT pg_reload_conf();
```

Skip that change and PostgreSQL keeps avoiding Index Scan on your SSD server. It still believes index access is expensive, so it prefers a Seq Scan.

## Data access methods — what the Planner chooses

```sql
EXPLAIN SELECT * FROM users WHERE email = 'max@test.com';
```

One term runs through the whole section. **Selectivity** is the share of the table a condition keeps. `WHERE id = 42` is highly selective, because it keeps one row. `WHERE country = 'USA'` on a mostly-American table is not selective at all.

**Sequential Scan (Seq Scan)** reads all table pages in order. Sequential reads are fast, so this is often the right plan rather than a failure. The Planner uses it when:

- there is no index on the column;
- an index exists, but selectivity is low, so many rows match anyway;
- the table is small, and there the index only adds overhead;
- the table is bloated after heavy `UPDATE` traffic, so it holds many near-empty pages.

```txt
Cost of a Seq Scan — linear in table size:
  seq_page_cost × N_pages + cpu_tuple_cost × N_rows
```

**Index Scan** works in two steps. First it walks the B-Tree, which takes O(log N). Then, for each key it found, it makes one random read into the heap to fetch the row that `ctid` points at. The Planner uses it when selectivity is high, so few rows match.

```txt
Cost of an Index Scan:
  O(log N + K × random_page_cost), where K = number of matching rows
```

**Bitmap Index Scan + Bitmap Heap Scan** is the middle ground, and it runs in two passes:

1. Walk the index and build a bitmap in memory. The bitmap marks which heap pages hold matching rows.
2. Read those heap pages in physical order, which turns the random reads back into sequential ones.

That re-sorting is the whole advantage over a plain Index Scan. It is also why the Planner reaches for this method at medium selectivity: many rows match, but not all of them.

**Index Only Scan** may never touch the heap at all. That works when the index already holds everything the query selects — the key plus any `INCLUDE` columns. The heap is skipped whenever the Visibility Map marks a page as "all-visible". This is the fastest option, and the reason to build covering indexes.

| Access method | Chosen when | Heap reads |
|---|---|---|
| Seq Scan | no index, or most rows match | every page, in order |
| Index Scan | few rows match | one random read per match |
| Bitmap Index Scan | many rows match, but not most | matching pages, in physical order |
| Index Only Scan | the index holds every selected column | often none at all |

## `JOIN` algorithms — three fundamentally different approaches

**Nested Loop Join** is the straightforward one. For every row of the outer table it scans the inner table for rows that satisfy the join condition.

```txt
FOR EACH row IN outer_table:
  FOR EACH row IN inner_table WHERE join_condition:
    output the pair
```

Its cost is O(N × M), which is only acceptable for small tables. With an index on the inner table it drops to O(N × log M). So the Planner picks it when the outer result set is small and the inner table is indexed.

**Hash Join** runs in two phases. The build phase puts the **smaller** table into a hash table. The probe phase then walks the larger table and looks up every row in that hash table. Cost is O(N + M), which is excellent for large tables with no usable index. Two limits come with it: the hash table has to fit into `work_mem`, and the join condition has to be equality (`=`).

**Merge Join** needs both inputs sorted on the join key. Then one pass over both is enough, at O(N + M). If PostgreSQL has to sort them first, add O(N×log N + M×log M). It wins when both tables are large and the sort order is free — from an index, or because the query needs an `ORDER BY` anyway.

| Algorithm | Needs | Best case |
|---|---|---|
| Nested Loop | nothing; an index on the inner table helps a lot | small outer set, indexed inner table |
| Hash Join | equality condition, `work_mem` for the hash table | two large tables, no usable index |
| Merge Join | both inputs sorted on the join key | two large tables already in sorted order |

## EXPLAIN and EXPLAIN ANALYZE — reading the output

```sql
EXPLAIN ANALYZE BUFFERS
SELECT u.id, u.email, COUNT(o.id) AS order_count
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
WHERE u.created_at > '2024-01-01'
GROUP BY u.id, u.email
ORDER BY order_count DESC
LIMIT 10;
```

```txt
Sample output (simplified):
 Limit  (cost=1245.67..1245.70 rows=10 width=40)
        (actual time=23.456..23.458 rows=10 loops=1)
   ->  Sort  (cost=1245.67..1248.17 rows=1000 width=40)
         (actual time=23.454..23.455 rows=10 loops=1)
       Sort Key: count(o.id) DESC
       Sort Method: top-N heapsort  Memory: 26kB
       ->  HashAggregate  (cost=...)
             (actual time=22.1..22.8 rows=1000 loops=1)
           ->  Hash Left Join  (cost=...)
                 Hash Cond: (o.user_id = u.id)
               ->  Index Scan using idx_users_created on users u
                     Index Cond: (created_at > '2024-01-01')
                     (actual time=0.08..5.2 rows=5000 loops=1)
               ->  Hash  (cost=...)
                     Buckets: 32768  Batches: 1  Memory: 1024kB
                   ->  Seq Scan on orders o
                         (actual time=0.02..8.3 rows=85000 loops=1)
 Planning Time: 1.2 ms
 Execution Time: 23.5 ms
```

Four things in that output carry almost all of the information:

1. **`cost=start..total`** — two numbers, not one. The start cost is the work before the first row appears, which is what a `LIMIT` cares about. The total cost is the estimate for the whole node. When `actual rows` is far from `rows`, the statistics are stale and `ANALYZE` is due.
2. **`actual time=X..Y rows=Z loops=N`** — the measured side of the node. X is the time to its first row, Y the time to its last row, both in milliseconds. Z is how many rows it really returned. And `loops=N` means the node ran N times, so on the inner side of a Nested Loop the real cost is Y × N.
3. **`Buffers`, printed only with the `BUFFERS` option** — where the pages came from. A `shared hit` is a page served from `shared_buffers`, the cache in memory, and it is fast. A `shared read` is a page fetched from disk, and it is slow. Many `shared read`s mean the data does not fit in the cache, or was never in it.
4. **The red flags** — four patterns that should stop you on sight:
   - **Seq Scan on a large table with a `WHERE`** — the column probably needs an index.
   - **estimated rows far below actual rows** (`rows=1000` against `actual=100000`) — stale statistics, so run `ANALYZE`.
   - **Nested Loop with `loops=10000`** — that is 10000 passes over the inner side, which needs an index.
   - **`Sort Method: external merge Disk`** — the sort spilled to disk, because `work_mem` is too small. For heavy analytic queries raise it: `SET work_mem = '256MB'`.

## Common causes of slow queries and how to diagnose them

Five causes cover most slow queries in practice, and each has a check you can run in one statement.

```sql
-- 1. Missing or wrong index
EXPLAIN ANALYZE SELECT * FROM orders
WHERE status = 'pending' AND user_id = 42;
-- If Seq Scan: add index on (user_id, status) or (status, user_id)

-- 2. Stale statistics
ANALYZE orders;  -- update stats
-- Or check: SELECT * FROM pg_stat_user_tables WHERE relname = 'orders';
-- large n_dead_tup → need VACUUM

-- 3. Wrong join order / hash join out of memory
SET work_mem = '256MB';  -- for this session only (not globally!)
EXPLAIN ANALYZE ...;     -- repeat and compare plan

-- 4. Function in WHERE breaks index usage
-- BAD:  WHERE LOWER(email) = 'max@test.com' — skips idx_users_email
-- GOOD: create a functional index
CREATE INDEX idx_users_email_lower ON users (LOWER(email));

-- 5. Implicit cast breaks index
-- If user_id is BIGINT but a VARCHAR is passed:
WHERE user_id = '42'  -- cast VARCHAR→BIGINT → index often skipped
-- Fix: pass the correct type
WHERE user_id = 42
```

## pg_stat_statements — monitoring slow queries in production

`pg_stat_statements` is an extension that keeps running totals for every query the server executes. It is how you find the expensive queries in production, without running `EXPLAIN ANALYZE` on each one by hand.

```sql
-- Enable the extension (in postgresql.conf):
-- shared_preload_libraries = 'pg_stat_statements'

CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Top 10 most expensive queries
SELECT
  round(total_exec_time::numeric, 2) AS total_ms,  -- all calls together
  calls,                                        -- how many times it ran
  round(mean_exec_time::numeric, 2)  AS avg_ms, -- one average call
  -- This query's share of the total time of all queries.
  -- sum(...) OVER () is a window function: it sums the column over ALL
  -- rows of the result, yet keeps every row in place (unlike GROUP BY).
  round((100 * total_exec_time / sum(total_exec_time) OVER ())::numeric, 1)
    AS pct,
  left(query, 100) AS query_snippet             -- first 100 characters
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;
```

## Connection to other topics

- [Indexes and Internals](./04-indexes-internals.md) — the index types, when the Planner chooses each of them, and the Left Prefix Rule behind composite indexes.
- [MVCC, Locks, and Vacuum](./05-mvcc-locks-vacuum.md) — MVCC is Multi-Version Concurrency Control. That article shows how autovacuum and `ANALYZE` keep the Planner's statistics fresh, and what a HOT Update (Heap-Only Tuple) does to plans.
- [Isolation Levels](./03-isolation-levels.md) — the isolation level decides which snapshot planning sees. This rarely matters, but it does matter in edge cases.

## Common interview mistakes

- **"`EXPLAIN` shows real execution time"** — plain `EXPLAIN` shows only the estimated cost, and never runs the query. Only `EXPLAIN ANALYZE` executes it and reports real time and real row counts.

- **"The Planner always picks the right plan"** — it gets plans wrong in three situations. Statistics are stale, which you see as `actual rows` far above the estimate. The data is distributed unevenly, with a few very frequent values. Or correlation is near 0: rows sit on disk in no relation to the column order.

- **"Index Scan is always faster than Seq Scan"** — Seq Scan wins at low selectivity, when many rows match. It also competes well on an SSD, where random and sequential reads cost almost the same. And it always wins on small tables.

- **"`random_page_cost` should always stay at 4.0"** — that value is tuned for a spinning disk. On an SSD lower it to 1.1-2.0, otherwise the Planner keeps avoiding Index Scan.

- **"`work_mem` is a global setting for the whole server"** — it is allocated **per operation** (each sort, each hash) and **per connection**. `SET work_mem = '1GB'` with 100 concurrent connections is potentially a hundred gigabytes of memory. Set it inside the session that needs it, for heavy analytic queries only.
