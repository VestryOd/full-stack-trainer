# Indexes and Internals

## An index is a separate data structure that trades space and write speed for read speed

An index buys read speed, and it pays with disk space and write speed. That is the whole trade-off in one sentence.

Without an index, `WHERE email = 'max@test.com'` on a 10 million row table becomes a Sequential Scan. PostgreSQL reads **all** heap file pages, 8 KB (8192 bytes) each, and checks every row. Complexity: O(n).

An index stores a mapping from column values to physical row locations: a page number plus an offset inside that page. The cost is extra disk space, plus work on every write — `INSERT`, `UPDATE` and `DELETE` all have to update the index structure as well.

## B-Tree — the default index, and why it works for most cases

```txt
           [50]
         /      \
     [25]        [75]
    /    \      /    \
[10,20] [30,40] [60,70] [80,90]
```

B-Tree stands for balanced tree. Three properties make it the default choice:

- Each node holds sorted keys and pointers to child nodes. At the leaves, those pointers lead to heap rows.
- All leaf nodes sit at the same depth, so the tree stays balanced.
- Leaves are linked to each other in a doubly linked list. That makes range queries efficient: `BETWEEN`, `<`, `>`.

For 1,000,000 rows the height is about log₁₀₀(1,000,000) ≈ 3 levels. PostgreSQL B-Tree nodes hold hundreds of keys each, so this is not a binary tree. A real lookup costs 3-4 I/O operations, where I/O means input/output — one read or write against the disk. A Seq Scan over the same table touches 10,000+ pages.

B-Tree supports `=`, `<`, `<=`, `>`, `>=`, `BETWEEN`, `LIKE 'prefix%'`, `IS NULL` and `ORDER BY`. The last one works because the index is already sorted, so the sort step can be skipped entirely.

B-Tree does **not** support `LIKE '%suffix'`, full-text search, or the `@>` family of operators.

## Internals: how PostgreSQL stores data and indexes on disk

```txt
Heap file (table):
  ┌───────────┬───────────┬───────────┐
  │  Page 0   │  Page 1   │  Page 2   │  ← 8 KB pages
  │ (8192 B)  │ (8192 B)  │ (8192 B)  │
  └───────────┴───────────┴───────────┘
```

Each page contains four parts:

- `PageHeader` — 24 bytes.
- `ItemIdData` — an array of pointers to the rows.
- Free space, held in reserve for new rows.
- Tuple data — the rows themselves, which PostgreSQL calls tuples.

Each row contains two parts:

- `HeapTupleHeader`, 23 bytes: `xmin` and `xmax` (both used by MVCC, Multi-Version Concurrency Control), plus `natts`, `infomask` and others.
- The column data itself.

An index file is built from the same 8 KB pages, but with B-Tree nodes inside them. Leaf pages store pairs of `(key_value, ctid)`, where `ctid` is `(page_number, item_offset)` — the physical location of that row in the heap.

## Composite Index and Left Prefix Rule — the most common interview question

```sql
CREATE INDEX idx_orders_user_status ON orders(user_id, status);
```

A composite index stores keys as the pair `(user_id, status)`. They are sorted by `user_id` first, then by `status` within one `user_id`.

The index **works** for:

- `WHERE user_id = 5` — the left prefix on its own.
- `WHERE user_id = 5 AND status = 'paid'` — both fields.
- `WHERE user_id = 5 AND status > 'paid'` — a range on the right field.
- `ORDER BY user_id, status` — sorting.

The index does **not** work efficiently for `WHERE status = 'paid'`, which is the right column without the left one. PostgreSQL can still do an Index Scan with a filter, but efficiency drops to O(n), because it has to scan the whole index.

Why: data in the index is sorted by `(user_id, status)`. Without pinning `user_id` to a value you cannot jump straight to a given `status`. That status is scattered across the entire index, inside every `user_id` section.

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

Two benefits:

- The index size equals the share of rows that satisfy the `WHERE` condition. If 5% of orders are unpaid, the index is 20 times smaller than a full one.
- A smaller index fits far more easily into `shared_buffers`, the page cache PostgreSQL keeps in memory.

On top of that, queries carrying the same `WHERE` condition pick it up automatically.

One limitation: the query **must** contain that same condition, or a stricter one. Otherwise the planner cannot use a partial index at all.

## Covering Index — Index-Only Scan without touching the heap

```sql
-- Query: SELECT id, email FROM users WHERE email = 'max@test.com'
-- Without INCLUDE: Index Scan (found in index → fetch from heap)
CREATE INDEX idx_users_email ON users(email);

-- With INCLUDE: Index-Only Scan (all needed data is in the index)
CREATE INDEX idx_users_email_covering ON users(email) INCLUDE (id);
```

An Index-Only Scan works only when both conditions hold:

1. Every column the `SELECT` asks for is in the index, either as a key or inside `INCLUDE`.
2. The Visibility Map says the heap page is "all-visible". That means every row on the page is visible to every transaction, so `VACUUM` has already processed it.

Without the second condition PostgreSQL still visits the heap, because visibility is decided by the MVCC row versions stored there. So a freshly written table under heavy writes often gets no benefit from an Index-Only Scan.

## Specialized index types

Four names, three of which are acronyms worth unpacking:

- **GIN** — generalized inverted index. For multi-valued types: JSONB (JSON kept in a parsed binary form), arrays, full-text search.
- **GiST** — generalized search tree. For geometry, ranges and PostGIS, the geospatial extension.
- **BRIN** — block range index. For very large tables whose rows are already physically ordered by the column value.
- **Hash** — a plain hash table. O(1) for `=`, and nothing beyond that.

```sql
-- GIN (Generalized Inverted Index) — for multi-valued types
-- JSONB, arrays, full-text search (tsvector)
CREATE INDEX idx_products_attrs ON products USING GIN (attributes);
CREATE INDEX idx_articles_search ON articles
  USING GIN (to_tsvector('english', body));
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
```

```sql
-- Hash — O(1) for =, no range support, no WAL before pg 10
CREATE INDEX idx_users_email_hash ON users USING HASH (email);
-- In most cases B-Tree is faster and more functional
```

## When the planner skips the index — and that's correct

```sql
-- Index on is_active (boolean), 99% of rows = true
EXPLAIN SELECT * FROM users WHERE is_active = true;
-- → Seq Scan! (Planner estimates: index returns 99% of rows,
--   Seq Scan is cheaper than 990,000 random I/Os via the index)

-- The index IS used for:
EXPLAIN SELECT * FROM users WHERE is_active = false;
-- → Index Scan (1% of rows — few enough for random I/O to be cheaper)
```

The planner decides from the statistics in `pg_statistic`:

- `n_distinct` — how many unique values the column holds.
- `correlation` — how closely the physical row order matches the index value order. High correlation makes a Seq Scan more attractive.
- `most_common_vals` and `most_common_freqs` — the frequencies of the most common values.

`ANALYZE` is what updates these statistics, and stale statistics produce wrong plans. In PostgreSQL 14+, autovacuum runs `ANALYZE` automatically.

## The cost of indexes on writes — how to evaluate the trade-off

Every index adds work to `INSERT`, `UPDATE` and `DELETE`:

- `INSERT` — a new entry goes into the B-Tree, O(log n), possibly splitting a page.
- `UPDATE` on an indexed column — logically a `DELETE` plus an `INSERT` in the B-Tree. In PostgreSQL an `UPDATE` creates a new row version through MVCC, so the old version's index entry becomes dead.
- `DELETE` — the index entry is marked dead. Physical removal happens later, at `VACUUM`.

Dead entries in an index are bloat, and `VACUUM` is what clears them out.

```sql
-- How much space each index takes, and how often it is actually used
SELECT indexrelname,
       pg_size_pretty(pg_relation_size(indexrelid)) AS size,
       idx_scan AS times_used
FROM pg_stat_user_indexes
WHERE relname = 'orders'
ORDER BY pg_relation_size(indexrelid) DESC;
```

```txt
     indexrelname        |  size  | times_used
-------------------------+--------+------------
 idx_orders_user_status  | 214 MB |    1840512
 idx_orders_created_at   | 198 MB |          0   ← pays only costs
 idx_orders_pending      |  11 MB |      92310
```

In practice: do not create indexes "just in case". Every index should solve one specific problem that `EXPLAIN ANALYZE` has confirmed.

## Connection to other topics

- [MVCC, Locks, and Vacuum](./05-mvcc-locks-vacuum.md) — why `UPDATE` creates dead index entries and how `VACUUM` removes them. Also HOT (heap-only tuple) updates, the optimization for index-free updates.
- [Query Planner and EXPLAIN](./06-query-planner-explain.md) — using `EXPLAIN ANALYZE` to verify that an index is really used, and the planner's cost model.
- [PostgreSQL Fundamentals](./01-postgresql-fundamentals.md) — JSONB together with GIN indexes.

## Common interview mistakes

- **"An index always speeds up `SELECT`"** — the planner picks a Seq Scan when selectivity is low. On a table that is 99% `is_active = true`, random I/O through the index costs more than reading the heap sequentially.

- **"A composite index (a, b) works for `WHERE b = ?`"** — no, and the reason has a name: the Left Prefix Rule. Without the left column `a` in the condition, the index is used inefficiently or not at all.

- **"More indexes = faster"** — every index slows down `INSERT`, `UPDATE` and `DELETE`. Every index also adds bloat that `VACUUM` then has to clean up.

- **"`INCLUDE` in an index is the same as adding a column to the key"** — it is not. `INCLUDE` columns do not affect the B-Tree sort order, so they take no part in tree traversal. They are stored in the leaf nodes, and that is what makes an Index-Only Scan possible.

- **"BRIN indexes work for all tables"** — not in general. BRIN is effective only when the physical row order correlates with the column value, for example `created_at` in an append-only table. For randomly inserted data BRIN is useless.
