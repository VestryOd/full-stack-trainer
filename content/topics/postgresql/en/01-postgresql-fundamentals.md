# PostgreSQL Fundamentals

## PostgreSQL — not just a "relational database," but an object-relational DBMS with a rich type system

PostgreSQL is an open-source ORDBMS (object-relational database management system). Both halves of that name carry meaning.

**"Object-relational"** means PostgreSQL goes past plain tables. It supports table inheritance, user-defined types (`CREATE TYPE`), operator overloading and custom aggregate functions. All four go beyond the SQL:2016 standard and beyond Codd's classic relational model. SQL stands for Structured Query Language, the standard language for querying relational data.

```sql
-- "Object-relational" in one example: your own type used as a column type
CREATE TYPE address AS (city TEXT, street TEXT, zip TEXT);

CREATE TABLE customers (
    id      BIGSERIAL PRIMARY KEY,
    name    TEXT NOT NULL,
    billing address       -- one composite value, not three separate columns
);

INSERT INTO customers (name, billing)
VALUES ('Ada', ROW('Kyiv', 'Khreshchatyk 1', '01001'));

SELECT name, (billing).city FROM customers;  -- → Ada | Kyiv
```

**"Open source"** means the code is fully open, under the PostgreSQL License. That license is close to MIT: you may ship PostgreSQL inside a commercial product for free. The community has developed it since 1996. The PostgreSQL Global Development Group governs the project.

For interviews: "PostgreSQL is the most advanced open-source relational database" is the project's own standard description. Three concrete differences from MySQL:

- PostgreSQL follows the SQL standard more strictly.
- It handles complex `JOIN`s better.
- Readers never take locks, thanks to MVCC (Multi-Version Concurrency Control — the database keeps several versions of one row). Details in [MVCC, Locks, and Vacuum](./05-mvcc-locks-vacuum.md).

## The journey of a SQL query through PostgreSQL's internal layers

Your query does not go straight to the disk. It passes five stages inside the server, and each stage rewrites it into a lower-level form.

```txt
Application (psql / Prisma / pg)
│  SQL text via TCP (PostgreSQL wire protocol)
▼
  ┌────────────────────────────────────────────┐
  │ Parser            — builds AST from SQL    │
  │ Analyzer          — resolves names         │
  │                     (tables, columns,      │
  │                     types) → Query Tree    │
  │ Rewriter          — applies rules          │
  │                     (VIEW expansion,       │
  │                     RLS policies)          │
  │ Planner/Optimizer — builds multiple plans, │
  │                     picks the one with the │
  │                     lowest estimated cost  │
  │ Executor          — executes the plan,     │
  │                     returns rows           │
  └────────────────────────────────────────────┘
│
▼
Buffer Manager (shared_buffers — page cache in RAM)
│  cache miss
▼
Storage (heap files, index files on disk)
```

Three abbreviations in that picture need unpacking:

- **AST** — abstract syntax tree, the parsed tree-shaped form of your query text.
- **RLS** — row-level security, per-row access rules that PostgreSQL bolts onto the query as extra `WHERE` conditions.
- **RAM** — random-access memory, the server's memory, as opposed to its disk.

**Senior nuance:** the Planner is the most complex part. It estimates cost from statistics (`pg_statistic`, collected by `ANALYZE`) and picks between Seq Scan, Index Scan, Bitmap Scan, Hash Join, Merge Join and others. Wrong statistics give a wrong plan, and a wrong plan means a slow query. Details in [Query Planner and EXPLAIN](./06-query-planner-explain.md).

## Object hierarchy: Cluster → Database → Schema → Table → Row → Column

Six levels, from the whole server down to a single value:

- **Cluster** — the entire PostgreSQL instance: one `postmaster` process, one data directory. It contains **multiple** databases.
- **Database** — a logically isolated container. A transaction cannot touch data in a **different** database. Cross-database queries go only through `dblink` or `postgres_fdw`.
- **Schema** — a namespace inside a database. The default one is `public`. One instance can hold many schemas, for example one schema per tenant in a multi-tenant SaaS (software as a service).
- **Table** — a set of rows with the same "type", meaning the same column structure. Physically it is a heap file: a pile of pages, 8 KB (8192 bytes) each.
- **Row (tuple)** — one record. PostgreSQL's internal documentation calls a row a "tuple".
- **Column** — an attribute of a table. It has a data type and a set of constraints.

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

Picking a type decides three things at once. It fixes how many bytes a row takes, which index types you can build on it, and how comparisons behave.

The list below is the working set for application code, with the preferred choice marked in each group. One index name appears in it — **GIN**, a generalized inverted index. It is the type that can index the inside of a JSONB value, and JSONB is JSON stored in a parsed binary form.

```sql
-- Numbers
INTEGER        -- 4 bytes, -2.1B..+2.1B
BIGINT         -- 8 bytes, ±9.2×10^18  ← for user_id, counters
SERIAL         -- auto-increment on INTEGER (implemented via SEQUENCE)
BIGSERIAL      -- auto-increment on BIGINT (preferred for primary keys)
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

**Senior practice: always prefer `TIMESTAMPTZ` over `TIMESTAMP`.** A plain `TIMESTAMP` stores "local" time with no zone information attached. So when the server or client timezone setting changes, existing data starts being read incorrectly.

`TIMESTAMPTZ` avoids that. On write it normalizes the value to UTC (Coordinated Universal Time, the zero time zone). On read it returns the value in the session's own time zone.

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

**Senior nuance: `UNIQUE` in PostgreSQL allows several NULLs**, because `NULL` is never equal to `NULL` in the SQL standard. If you need a unique field that allows exactly one NULL, use a partial index:

```sql
CREATE UNIQUE INDEX ON t(col) WHERE col IS NOT NULL;
```

`ON DELETE RESTRICT` and `ON DELETE NO ACTION` both stop you from deleting a parent row while child rows still exist. The difference is when the check runs:

- `RESTRICT` checks immediately, inside the statement itself.
- `NO ACTION` can be declared `DEFERRABLE`, so the check runs at the end of the transaction.

## Relationships and normalization — the practical level

```sql
-- Many-to-Many via junction table
CREATE TABLE user_roles (
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id    BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, role_id)            -- composite key prevents dupes
);

-- JOIN — the foundation of working with normalized data
SELECT u.id, u.name, r.name AS role
FROM users u
JOIN user_roles ur ON ur.user_id = u.id
JOIN roles r       ON r.id = ur.role_id
WHERE u.id = $1;
```

Three normal forms are enough for interviews:

- **1NF** — atomic values (no arrays and no repeating groups inside one column), and no duplicate rows.
- **2NF** — every non-key attribute depends on the **whole** key. This only matters for composite primary keys, written PK for short.
- **3NF** — no transitive dependencies: a non-key column must not depend on another non-key column.

Denormalization is the conscious trade-off in the other direction. A column like `orders.total_amount` holds a pre-computed sum, so you never recalculate `SUM(items.price * items.qty)` on read. The price is duplication plus the risk of drift. A direct `UPDATE` on `items` that forgets `orders.total_amount` leaves the two out of sync.

## JSONB — when and how to use it wisely

```sql
CREATE TABLE products (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    attributes  JSONB                       -- dynamic / variable fields
);

INSERT INTO products (name, attributes)
VALUES ('iPhone 15', '{"color": "black", "storage": 256, "tags": ["phone"]}');

-- JSONB operators
SELECT * FROM products WHERE attributes @> '{"color": "black"}';  -- contains
SELECT attributes->>'color' FROM products WHERE id = 1;           -- get text
SELECT attributes->'storage' FROM products;                       -- get JSON value

-- GIN index for @>, ?, ?|, ?& operators
CREATE INDEX idx_products_attrs ON products USING GIN (attributes);

-- For path operators (jsonb_path_ops) — smaller index, only @>
CREATE INDEX idx_products_attrs_path ON products
  USING GIN (attributes jsonb_path_ops);
```

When JSONB makes sense:

- ✓ A "dynamic schema" — attributes that vary heavily between records, such as product attributes in e-commerce.
- ✓ Storing external API responses without normalizing them, such as an audit log.
- ✓ Fast prototyping, before the schema stabilizes.

When JSONB is an anti-pattern:

- ✗ Fields you often use in `WHERE` or `JOIN`. Those should be regular columns with regular B-Tree indexes.
- ✗ Relationships between entities. A `FOREIGN KEY` inside JSONB is impossible.
- ✗ "Because it's flexible" — without a real reason for a dynamic schema.

## Connection to other topics

- [ACID and Transactions](./02-acid-transactions.md) — how PostgreSQL keeps data consistent through transactions. ACID stands for atomicity, consistency, isolation, durability.
- [Isolation Levels](./03-isolation-levels.md) — how visibility of changes between concurrent transactions is controlled.
- [Indexes and Internals](./04-indexes-internals.md) — how to speed up `SELECT` on large tables.
- [MVCC, Locks, and Vacuum](./05-mvcc-locks-vacuum.md) — why `UPDATE` in PostgreSQL does not overwrite the row in place.
- [Query Planner and EXPLAIN](./06-query-planner-explain.md) — how the execution plan is chosen.

## Common interview mistakes

- **"`TEXT` vs `VARCHAR` — `VARCHAR` is faster"** — in PostgreSQL both types use the same internal representation, VARLENA (variable-length array). The performance difference is zero. `VARCHAR(n)` only adds a length check.

- **"TIMESTAMP and TIMESTAMPTZ are the same thing"** — not explaining that `TIMESTAMP` stores a "naive" date with no time zone. Change the server or client time zone and that date is suddenly read wrong.

- **"SERIAL is the best way to create auto-increment"** — not knowing that `SERIAL` is syntactic sugar for `CREATE SEQUENCE` plus `DEFAULT nextval()`. Modern PostgreSQL prefers `GENERATED ALWAYS AS IDENTITY`, which is what the SQL standard defines.

- **"`UNIQUE` prevents two NULLs"** — in PostgreSQL, as in the SQL standard, `NULL` is not equal to `NULL`. So a `UNIQUE` index accepts many NULL values.

- **"JSONB gives you flexibility"** — not naming the concrete trade-off. JSONB breaks relational normalization, makes `FOREIGN KEY` relationships impossible, and blocks plain B-Tree indexes on nested fields with good selectivity.
