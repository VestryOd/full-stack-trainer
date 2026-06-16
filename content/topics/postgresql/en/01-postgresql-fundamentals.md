# PostgreSQL Fundamentals

## PostgreSQL — not just a "relational database," but an object-relational DBMS with a rich type system

PostgreSQL is an open-source ORDBMS (Object-Relational Database Management System). Key words:

```txt
"Object-relational" — supports table inheritance, user-defined
types (CREATE TYPE), operator overloading, custom aggregate
functions. This goes beyond the SQL:2016 standard and the
standard relational model (Codd).

"Open source" — code is fully open (PostgreSQL License, similar
to MIT), actively developed by the community since 1996, governed
by the PostgreSQL Global Development Group.
```

For interviews: "PostgreSQL is the most advanced open-source relational database" is the project's own standard description. Difference from MySQL: PostgreSQL follows the SQL standard more strictly, handles complex JOINs better, and has MVCC without read locks (details in [MVCC, Locks, and Vacuum]).

## The journey of a SQL query through PostgreSQL's internal layers

```txt
Application (psql / Prisma / pg)
        │  SQL text via TCP (PostgreSQL wire protocol)
        ▼
  ┌─────────────────────────────────────┐
  │  Parser      — builds AST from SQL │
  │  Analyzer    — resolves names       │
  │               (tables, columns,     │
  │               types) → Query Tree  │
  │  Rewriter    — applies rules        │
  │               (VIEW expansion,      │
  │               RLS policies)         │
  │  Planner/    — builds multiple      │
  │  Optimizer     plans, picks the one │
  │               with the lowest       │
  │               estimated cost        │
  │  Executor    — executes the plan,   │
  │               returns rows          │
  └─────────────────────────────────────┘
        │
        ▼
  Buffer Manager (shared_buffers — page cache in RAM)
        │  cache miss
        ▼
  Storage (heap files, index files on disk)
```

```txt
Senior nuance: the Planner is the most complex part. It estimates
cost using statistics (pg_statistic, collected by ANALYZE) and
chooses between Seq Scan, Index Scan, Bitmap Scan, Hash Join,
Merge Join, etc. Wrong statistics → wrong plan → slow query.
Details in [Query Planner and EXPLAIN].
```

## Object hierarchy: Cluster → Database → Schema → Table → Row → Column

```txt
Cluster     — the entire PostgreSQL instance (one postmaster
              process, one data directory). Contains MULTIPLE
              databases.

Database    — a logically isolated container. A transaction cannot
              touch data in a DIFFERENT database (cross-database
              queries only via dblink/postgres_fdw).

Schema      — a namespace inside a database. Default: public.
              One instance: multiple schemas (e.g., one schema
              per tenant in a multi-tenant SaaS).

Table       — a set of rows with the same "type" (same column
              structure). Physically — a heap file (pages of 8 KB).

Row (tuple) — one record. PostgreSQL calls a row a "tuple" in
              internal documentation.

Column      — an attribute of a table. Has a data type and a set
              of constraints.
```

```sql
-- Demonstrating the hierarchy
CREATE DATABASE app_db;

\c app_db

CREATE SCHEMA billing;

CREATE TABLE billing.invoices (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES public.users(id),
    amount      NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## Data types — the choice of type affects size, indexes, and behavior

```sql
-- Numbers
INTEGER        -- 4 bytes, -2.1B..+2.1B
BIGINT         -- 8 bytes, ±9.2×10^18  ← for user_id, counters
SERIAL         -- auto-increment on INTEGER (implemented via SEQUENCE)
BIGSERIAL      -- auto-increment on BIGINT (preferred for PK)
NUMERIC(p, s)  -- arbitrary precision, exact money; slower than float
REAL / FLOAT8  -- IEEE 754 float; never for money (precision loss)

-- Strings
TEXT           -- variable length, no limit (preferred)
VARCHAR(n)     -- like TEXT but with a length constraint (in PostgreSQL
               -- no performance difference vs TEXT — both are VARLENA)
CHAR(n)        -- fixed length, padded with spaces — almost never
               -- needed in modern applications

-- Date and time
DATE           -- date only (no time of day)
TIMESTAMP      -- date + time, no time zone (stores "wall clock")
TIMESTAMPTZ    -- date + time + UTC normalization (recommended for
               -- anything shown to users across different time zones)
INTERVAL       -- a period of time (INTERVAL '3 months')

-- Boolean
BOOLEAN        -- TRUE / FALSE / NULL (three states)

-- JSON
JSON           -- stores raw JSON text as-is (parsed on each access)
JSONB          -- binary JSON: parsed at insert time, supports
               -- GIN indexes, @>, ?, #> operators. Preferred.
               -- Only downside: loses key order and duplicate keys
               -- (like a dict in Python)

-- UUID
UUID           -- 128-bit UUID; stored more efficiently than TEXT(36)
               -- gen_random_uuid() (built into PostgreSQL 13+)

-- Arrays
INTEGER[]      -- array of any type (native PostgreSQL support,
TEXT[]         -- NOT a JSON array). Query with @> or ANY().
```

```txt
Senior practice: always prefer TIMESTAMPTZ over TIMESTAMP.
TIMESTAMP without TZ stores "local" time without zone info —
when the server/client timezone setting changes, data starts being
interpreted incorrectly. TIMESTAMPTZ normalizes to UTC on storage,
returns in the session's TZ on read.
```

## Constraints — built-in data integrity enforcement

```sql
CREATE TABLE orders (
    id          BIGSERIAL PRIMARY KEY,           -- NOT NULL + UNIQUE
    user_id     BIGINT NOT NULL
                  REFERENCES users(id)
                  ON DELETE RESTRICT,            -- prevents deletion
                  -- ON DELETE SET NULL          -- or: nullifies ref
                  -- ON DELETE CASCADE,          -- or: cascades delete
    status      TEXT NOT NULL
                  CHECK (status IN ('pending','paid','cancelled')),
    total       NUMERIC(12,2) NOT NULL CHECK (total >= 0),
    email       TEXT UNIQUE,                     -- NULL doesn't violate UNIQUE
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Deferred constraints (checked at END of transaction, not per-row)
ALTER TABLE orders
  ADD CONSTRAINT fk_user
  FOREIGN KEY (user_id) REFERENCES users(id)
  DEFERRABLE INITIALLY DEFERRED;
```

```txt
Senior nuance: UNIQUE in PostgreSQL allows MULTIPLE NULLs (because
NULL ≠ NULL in the SQL standard). If you need a unique field that
allows exactly one NULL, use a partial index:
CREATE UNIQUE INDEX ON t(col) WHERE col IS NOT NULL.

ON DELETE RESTRICT vs ON DELETE NO ACTION: both prevent deletion
of a parent row when child rows exist. Difference: RESTRICT checks
immediately within the statement; NO ACTION can be made DEFERRED
(checked at end of transaction).
```

## Relationships and normalization — the practical level

```sql
-- Many-to-Many via junction table
CREATE TABLE user_roles (
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id    BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, role_id)            -- composite PK prevents dupes
);

-- JOIN — the foundation of working with normalized data
SELECT u.id, u.name, r.name AS role
FROM users u
JOIN user_roles ur ON ur.user_id = u.id
JOIN roles r       ON r.id = ur.role_id
WHERE u.id = $1;
```

```txt
Normal forms (3NF is enough for interviews):
  1NF — atomic values (no arrays/groups in a column), unique rows
  2NF — every non-key attribute depends on the WHOLE key
        (relevant for composite PKs)
  3NF — no transitive dependencies (a non-key doesn't depend on
        another non-key)

Denormalization as a conscious trade-off:
  orders.total_amount — store a pre-computed sum instead of
  recalculating SUM(items.price * items.qty) on every read.
  Cost: duplication + risk of desync if items are directly UPDATEd
  without updating orders.total_amount.
```

## JSONB — when and how to use it wisely

```sql
CREATE TABLE products (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    attributes  JSONB                       -- dynamic / variable fields
);

INSERT INTO products (name, attributes)
VALUES ('iPhone 15', '{"color": "black", "storage": 256, "tags": ["phone","apple"]}');

-- JSONB operators
SELECT * FROM products WHERE attributes @> '{"color": "black"}';    -- contains
SELECT attributes->>'color' FROM products WHERE id = 1;             -- get text
SELECT attributes->'storage' FROM products;                          -- get JSON value

-- GIN index for @>, ?, ?|, ?& operators
CREATE INDEX idx_products_attrs ON products USING GIN (attributes);

-- For path operators (jsonb_path_ops) — smaller index, only @>
CREATE INDEX idx_products_attrs_path ON products
  USING GIN (attributes jsonb_path_ops);
```

```txt
When JSONB makes sense:
  ✓ "Dynamic schema" — attributes that vary heavily between records
    (product attributes in e-commerce)
  ✓ Storing external API responses without normalization (audit log)
  ✓ Fast prototyping before the schema stabilizes

When JSONB is an anti-pattern:
  ✗ Fields that are frequently used in WHERE/JOIN — they should be
    regular columns with regular B-Tree indexes
  ✗ Relationships between entities — FOREIGN KEY inside JSONB is
    impossible
  ✗ "Because it's flexible" — without a real justification for a
    dynamic schema
```

## Connection to other topics

```txt
[ACID and Transactions]           — how PostgreSQL ensures
                                      consistency through transactions
[Isolation Levels]                — how visibility of changes between
                                      concurrent transactions is
                                      controlled
[Indexes and Internals]           — how to speed up SELECT on large
                                      tables
[MVCC, Locks, and Vacuum]         — why UPDATE in PostgreSQL doesn't
                                      overwrite the row in place
[Query Planner and EXPLAIN]       — how the execution plan is chosen
```

## Common interview mistakes

- **"TEXT vs VARCHAR — VARCHAR is faster"** — in PostgreSQL both types use the same internal representation (VARLENA); there is zero performance difference. VARCHAR(n) only adds a length check.

- **"TIMESTAMP and TIMESTAMPTZ are the same thing"** — not explaining that TIMESTAMP stores a "naive" date without a time zone, which can lead to incorrect interpretation when the server or client TZ changes.

- **"SERIAL is the best way to create auto-increment"** — not knowing that SERIAL is syntactic sugar (CREATE SEQUENCE + DEFAULT nextval()), and that modern PostgreSQL prefers `GENERATED ALWAYS AS IDENTITY` for SQL-standard compliance.

- **"UNIQUE prevents two NULLs"** — in PostgreSQL (and the SQL standard) NULL ≠ NULL, so a UNIQUE index allows multiple NULL values.

- **"JSONB gives you flexibility"** — not explaining the concrete trade-off: JSONB breaks relational normalization, makes FOREIGN KEY relationships impossible, and prevents standard B-Tree indexes on nested fields with good selectivity.
