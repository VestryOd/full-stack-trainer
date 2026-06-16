# Indexes and Internals

## An index is a separate data structure that trades space and write speed for read speed

Without an index, `WHERE email = 'max@test.com'` on a 10M-row table is a Sequential Scan: PostgreSQL reads ALL heap file pages (8 KB each) and checks every row. Complexity: O(n).

An index is a separate structure storing a mapping of column values → physical row locations (page + offset). Cost: extra disk space + overhead on every write (INSERT/UPDATE/DELETE must update the index structure).

## B-Tree — the default index, and why it works for most cases

```txt
B-Tree (Balanced Tree) — a balanced tree where:
  - each node holds sorted keys and pointers to child nodes
    (or heap rows at the leaves)
  - all leaf nodes are at the same depth (the tree stays balanced)
  - leaves are linked to each other (doubly linked list) →
    range queries are efficient (BETWEEN, <, >)

           [50]
         /      \
     [25]        [75]
    /    \      /    \
[10,20] [30,40] [60,70] [80,90]
```

```txt
B-Tree height for 1,000,000 rows ≈ log₁₀₀(1,000,000) ≈ 3 levels
(PostgreSQL B-Tree nodes hold hundreds of keys, not a binary tree).
A real lookup: 3-4 I/O operations vs 10,000+ pages for a Seq Scan.

B-Tree supports: =, <, <=, >, >=, BETWEEN, LIKE 'prefix%', IS NULL,
ORDER BY (sorted index → sort can be skipped).
Does NOT support: LIKE '%suffix', full-text search, @> operators.
```

## Internals: how PostgreSQL stores data and indexes on disk

```txt
Heap file (table):
  ┌───────────┬───────────┬───────────┐
  │  Page 0   │  Page 1   │  Page 2   │  ← 8 KB pages
  │ (8192 B)  │ (8192 B)  │ (8192 B)  │
  └───────────┴───────────┴───────────┘

Each page contains:
  - PageHeader (24 bytes)
  - ItemIdData (array of pointers to rows)
  - Free space (for new rows)
  - Tuple data (the rows themselves — tuples)

Each row (tuple) contains:
  - HeapTupleHeader (23 bytes): xmin, xmax (for MVCC),
    natts, infomask...
  - Column data

Index file (B-Tree):
  - Same 8 KB pages, but containing B-Tree nodes inside
  - Leaf pages store (key_value, ctid),
    where ctid = (page_number, item_offset) — the physical
    location of the row in the heap
```

## Composite Index and Left Prefix Rule — the most common interview question

```sql
CREATE INDEX idx_orders_user_status ON orders(user_id, status);
```

```txt
A composite index stores keys as (user_id, status) — SORTED first
by user_id, then by status within one user_id.

The index WORKS for:
  WHERE user_id = 5                        ← left prefix only
  WHERE user_id = 5 AND status = 'paid'    ← both fields
  WHERE user_id = 5 AND status > 'paid'    ← range on right field
  ORDER BY user_id, status                 ← sorting

The index does NOT work efficiently for:
  WHERE status = 'paid'                    ← right column without left
    (PostgreSQL can do an Index Scan with filter, but efficiency
    drops to O(n) — must scan the whole index)

Why: data in the index is sorted by (user_id, status). Without
fixing user_id = X, you can't "jump" to a specific status — it's
scattered across the entire index in different user_id sections.
```

```sql
-- Correct column order for a composite index:
-- 1. Columns with equality conditions (=) — first
-- 2. Columns with range conditions (<, >, BETWEEN) — last
-- 3. Columns only for ORDER BY/GROUP BY — at the end

-- Query: WHERE user_id = 5 AND created_at > '2024-01-01'
-- Correct index: (user_id, created_at), NOT (created_at, user_id)
CREATE INDEX idx ON orders(user_id, created_at);
```

## Partial Index — index only the subset you need

```sql
-- Index only for active users
CREATE INDEX idx_users_email_active ON users(email)
WHERE is_active = true;

-- Index for unpaid orders (say, 5% of all orders)
CREATE INDEX idx_orders_pending ON orders(created_at)
WHERE status = 'pending';
```

```txt
Benefits:
  - Index size = % of rows satisfying the WHERE condition
    (5% unpaid → index is 20x smaller than a full index)
  - Smaller index → fits more easily in shared_buffers (RAM cache)
  - Queries with the same WHERE condition use it automatically

Limitation: the query MUST contain the same condition in WHERE
(or a stricter one), otherwise the Planner can't use a partial index.
```

## Covering Index — Index-Only Scan without touching the heap

```sql
-- Query: SELECT id, email FROM users WHERE email = 'max@test.com'
-- Without INCLUDE: Index Scan (found in index → fetch from heap)
CREATE INDEX idx_users_email ON users(email);

-- With INCLUDE: Index-Only Scan (all needed data is in the index)
CREATE INDEX idx_users_email_covering ON users(email) INCLUDE (id);
```

```txt
Index-Only Scan works only if:
  1. All columns requested in SELECT are in the index (key + INCLUDE)
  2. The Visibility Map shows that the heap page is "all-visible"
     (all rows on the page are visible to all transactions, i.e.,
     VACUUM has already processed the page)

Without (2), PostgreSQL still visits the heap to check visibility
(MVCC). A freshly-written table with heavy writes often won't
benefit from Index-Only Scan.
```

## Specialized index types

```sql
-- GIN (Generalized Inverted Index) — for multi-valued types
-- JSONB, arrays, full-text search (tsvector)
CREATE INDEX idx_products_attrs ON products USING GIN (attributes);
CREATE INDEX idx_articles_search ON articles USING GIN (to_tsvector('english', body));
-- GIN builds an inverted index: value → set of rows
-- Fast for @>, ?, ?|, @@; slower on writes (rebuilds posting lists)

-- GiST (Generalized Search Tree) — for geometry, ranges, PostGIS
CREATE INDEX idx_geom ON places USING GIST (location);
CREATE INDEX idx_range ON events USING GIST (during);  -- tstzrange
-- GiST supports: &&, @>, <->, <<, >>...

-- BRIN (Block Range INdex) — for very large tables with correlation
-- Stores min/max per range of pages (blocks)
CREATE INDEX idx_logs_ts ON logs USING BRIN (created_at);
-- Effective when: the physical order of rows CORRELATES with the
-- column value (time series, append-only log tables)
-- Index size: a few tens of KB vs tens of GB for a B-Tree

-- Hash — O(1) for =, no range support, no WAL before pg 10
CREATE INDEX idx_users_email_hash ON users USING HASH (email);
-- In most cases B-Tree is faster and more functional
```

## When the planner does NOT use an index — and that's correct

```sql
-- Index on is_active (boolean), 99% of rows = true
EXPLAIN SELECT * FROM users WHERE is_active = true;
-- → Seq Scan! (Planner estimates: index returns 99% of rows,
--   Seq Scan is cheaper than 990,000 random I/Os via the index)

-- The index IS used for:
EXPLAIN SELECT * FROM users WHERE is_active = false;
-- → Index Scan (1% of rows — few enough for random I/O to be cheaper)
```

```txt
The planner decides based on statistics (pg_statistic):
  - n_distinct: number of unique values
  - correlation: how well physical row order matches index value order
    (high correlation → Seq Scan may be better)
  - most_common_vals / most_common_freqs: value frequencies

ANALYZE updates statistics. Stale statistics → wrong plans.
In PostgreSQL 14+, autovacuum runs ANALYZE automatically.
```

## The cost of indexes on writes — how to evaluate the trade-off

```txt
Each index adds overhead to INSERT/UPDATE/DELETE:
  - INSERT → insert a new entry into the B-Tree (O(log n) with
    possible page split)
  - UPDATE on indexed column → logically DELETE + INSERT in B-Tree
    (in PostgreSQL, UPDATE creates a new row version via MVCC,
    so the old version's index entry becomes "dead")
  - DELETE → marks the index entry as dead (physical removal at VACUUM)

Dead entries in the index → bloat. VACUUM removes dead index entries.

Practice: don't create indexes "just in case." Every index should
solve a specific problem confirmed by EXPLAIN ANALYZE.
```

## Connection to other topics

```txt
[MVCC, Locks, and Vacuum]       — why UPDATE creates dead index
                                   entries and how VACUUM removes
                                   them; HOT-update as an optimization
                                   for index-free updates
[Query Planner and EXPLAIN]     — using EXPLAIN ANALYZE to verify
                                   index usage; the planner cost model
[PostgreSQL Fundamentals]       — JSONB + GIN indexes
```

## Common interview mistakes

- **"An index always speeds up SELECT"** — the planner chooses Seq Scan when selectivity is low (WHERE is_active = true when 99% are true), because random I/O through an index is more expensive than sequential heap reads.

- **"Composite index (a, b) works for WHERE b = ?"** — Left Prefix Rule: without the left column (`a`) in the condition, the index is used inefficiently or not at all.

- **"More indexes = faster"** — every index slows down INSERT/UPDATE/DELETE and increases bloat that VACUUM must clean.

- **"INCLUDE in an index is the same as adding a column to the key"** — INCLUDE columns don't affect the B-Tree sort order (they don't participate in tree traversal), but are stored in leaf nodes for Index-Only Scan.

- **"BRIN indexes work for all tables"** — BRIN is effective only when the physical row order CORRELATES with the column value (e.g., created_at in an append-only table). For randomly inserted data, BRIN is useless.
