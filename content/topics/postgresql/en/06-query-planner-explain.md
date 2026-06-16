# Query Planner and EXPLAIN ANALYZE

## The Planner — PostgreSQL's most complex component, responsible for the difference between 5 ms and 5 minutes

SQL is a declarative language: you describe **what** you want, not **how** to get it. The Planner/Optimizer's job is to transform that declarative "what" into a concrete execution plan: which indexes to use, in what order to scan tables, which JOIN algorithm to apply.

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

```txt
PostgreSQL Planner is a cost-based optimizer. It doesn't know exact
execution times, but estimates the "cost" of each plan in abstract units:

  seq_page_cost     = 1.0    (cost of reading one page via Sequential
                              Scan — the base unit)
  random_page_cost  = 4.0    (cost of random-access to one page —
                              Index Scan does random I/O)
  cpu_tuple_cost    = 0.01   (CPU cost per row)
  cpu_index_tuple_cost = 0.005
  cpu_operator_cost = 0.0025

Plan cost = sum of all I/O and CPU operations weighted by these parameters.
The Planner picks the plan with the MINIMUM estimated cost.
```

```txt
Why random_page_cost = 4.0 by default but often needs to be lowered:
  HDD: random I/O is 10-100x more expensive than sequential → 4.0 is right
  SSD: random I/O is only ~2x more expensive → lower it to 1.1-2.0

  ALTER SYSTEM SET random_page_cost = 1.1;  -- for SSD/NVMe
  SELECT pg_reload_conf();

  Without this, on an SSD server PostgreSQL will AVOID Index Scan in
  favor of Seq Scan, thinking index access is "expensive."
```

## Data access methods — what the Planner chooses

```sql
EXPLAIN SELECT * FROM users WHERE email = 'max@test.com';
```

```txt
Sequential Scan (Seq Scan):
  Reads ALL table pages in order (sequential I/O — fast).
  When used:
    - no index on the column
    - index exists but selectivity is low (many rows match)
    - table is small (index is slower due to overhead)
    - after heavy UPDATE (table bloat → many empty pages)
  Cost: O(n) = seq_page_cost × N_pages + cpu_tuple_cost × N_rows

Index Scan:
  1. Traverse B-Tree: O(log N)
  2. For each found key: random I/O to heap (ctid → row)
  When used: high selectivity (few rows match)
  Cost: O(log N + K × random_page_cost), where K = row count

Bitmap Index Scan + Bitmap Heap Scan:
  1. First: traverse index, build in-memory bitmap (page numbers)
  2. Then: read heap pages IN ORDER (sequential I/O!)
  When used: medium selectivity (many rows, but not all)
  Advantage over Index Scan: re-sorts pages → sequential I/O
  Cost: between Seq Scan and Index Scan

Index Only Scan:
  All needed data is in the index (key + INCLUDE columns).
  Heap may NOT be read (if Visibility Map says "all-visible").
  Fastest option for covering indexes.
```

## JOIN algorithms — three fundamentally different approaches

```txt
Nested Loop Join:
  FOR EACH row IN outer_table:
    FOR EACH row IN inner_table WHERE join_condition:
      output
  Cost: O(N × M) — only good for small tables
  Or: O(N × log M) if there's an index on the inner table
  When: small outer result set, index available on inner

Hash Join:
  1. Build phase: builds a hash table from the SMALLER table
  2. Probe phase: FOR EACH row IN larger_table → lookup in hash table
  Cost: O(N + M) — great for large tables without indexes
  Constraint: hash table must fit in work_mem
  When: large non-indexed joins, equality conditions (=)

Merge Join:
  Both tables sorted on the join key → one pass O(N + M)
  Cost: O(N×log N + M×log M) if sorting needed,
        O(N + M) if already sorted (sorted index)
  When: both tables are large, index exists or ORDER BY used
```

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
                     ->  Index Scan using idx_users_created
                           on users u
                           Index Cond: (created_at > '2024-01-01')
                           (actual time=0.08..5.2 rows=5000 loops=1)
                     ->  Hash  (cost=...)
                           Buckets: 32768  Batches: 1  Memory Usage: 1024kB
                           ->  Seq Scan on orders o
                               (actual time=0.02..8.3 rows=85000 loops=1)
 Planning Time: 1.2 ms
 Execution Time: 23.5 ms
```

```txt
Key metrics to analyze:

1. cost=start..total:
   - start cost: time to first row (important for LIMIT)
   - total cost: estimated full cost
   If actual rows differs greatly from estimated rows → stale
   statistics → need ANALYZE

2. actual time=X..Y rows=Z loops=N:
   - X: time to first row
   - Y: time to last row
   - Z: rows actually returned
   - loops=N: node was executed N times (key for Nested Loop inner)
   Real time = Y × N

3. Buffers (with BUFFERS):
   - shared hit=X: pages read from shared_buffers (RAM) — fast
   - shared read=Y: pages read from disk — slow
   High shared read → doesn't fit in cache or no cache

4. RED FLAGS in EXPLAIN ANALYZE:
   - Seq Scan on a large table with WHERE → need an index
   - estimated rows << actual rows (rows=1000 vs actual=100000)
     → stale statistics → run ANALYZE
   - Nested Loop with loops=10000 → 10000 hits on inner → need index
   - Sort Method: external merge Disk → work_mem too small
     (SET work_mem = '256MB' for heavy analytic queries)
```

## Common causes of slow queries and how to diagnose them

```sql
-- 1. Missing or wrong index
EXPLAIN ANALYZE SELECT * FROM orders WHERE status = 'pending' AND user_id = 42;
-- If Seq Scan: add index on (user_id, status) or (status, user_id)

-- 2. Stale statistics
ANALYZE orders;  -- update stats
-- Or check: SELECT * FROM pg_stat_user_tables WHERE relname = 'orders';
-- large n_dead_tup → need VACUUM

-- 3. Wrong join order / hash join out of memory
SET work_mem = '256MB';  -- for this session only (not globally!)
EXPLAIN ANALYZE ...;     -- repeat and compare plan

-- 4. Function in WHERE breaks index usage
-- BAD:  WHERE LOWER(email) = 'max@test.com' — doesn't use idx_users_email
-- GOOD: create a functional index
CREATE INDEX idx_users_email_lower ON users (LOWER(email));

-- 5. Implicit cast breaks index
-- If user_id is BIGINT but a VARCHAR is passed:
WHERE user_id = '42'  -- implicit cast VARCHAR→BIGINT → index often skipped
-- Fix: pass the correct type
WHERE user_id = 42
```

## pg_stat_statements — monitoring slow queries in production

```sql
-- Enable the extension (in postgresql.conf):
-- shared_preload_libraries = 'pg_stat_statements'

CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Top 10 most expensive queries
SELECT
  round(total_exec_time::numeric, 2) AS total_ms,
  calls,
  round(mean_exec_time::numeric, 2)  AS avg_ms,
  round((100 * total_exec_time / sum(total_exec_time) OVER ())::numeric, 1) AS pct,
  left(query, 100) AS query_snippet
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;
```

## Connection to other topics

```txt
[Indexes and Internals]       — index types and when the Planner
                                 chooses them; selectivity and Left
                                 Prefix Rule
[MVCC, Locks, and Vacuum]     — autovacuum/ANALYZE updates statistics
                                 for the Planner; HOT Update and its
                                 impact on plans
[Isolation Levels]            — isolation level affects the snapshot
                                 used during planning (rare, but
                                 important for edge cases)
```

## Common interview mistakes

- **"EXPLAIN shows real execution time"** — EXPLAIN without ANALYZE shows only the ESTIMATED cost without actually running the query. Only EXPLAIN ANALYZE executes the query and shows real time and row counts.

- **"The Planner always picks the right plan"** — the Planner gets it wrong with stale statistics (actual rows >> estimated rows in EXPLAIN ANALYZE), with non-uniform data distributions, and when correlation ≈ 0 (random row order).

- **"Index Scan is always faster than Seq Scan"** — Seq Scan can be faster with low selectivity (many rows match), on SSDs where random vs sequential I/O gap is small, and always for small tables.

- **"random_page_cost should always stay at 4.0"** — this value is optimal for HDDs. On SSDs it should be lowered to 1.1-2.0, otherwise the Planner avoids Index Scan.

- **"work_mem is a global setting for the whole server"** — work_mem is allocated PER OPERATION (sort, hash) and PER CONNECTION. SET work_mem = '1GB' with 100 concurrent connections = potentially 100 GB of RAM. Correct: SET work_mem locally in a session for heavy analytic queries.
