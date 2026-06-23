<!-- verified: 2026-06-23, corrections: 0 -->
# Pagination and Filtering

## Why This Deserves Its Own Article

Pagination and filtering seem straightforward — until you hit a table with 50 million rows, a real-time feed, or an infinite scroll UI. Then you discover that `LIMIT 20 OFFSET 1000000` kills the database, "page 2" shows duplicates when new records are inserted concurrently, and a simple `?status=active` filter grows into `?status[]=active&status[]=pending&createdAfter=2024-01-01`.

---

## Offset-Based Pagination

The most common approach. The client specifies "skip N records, take M."

```txt
Syntax variants:
GET /users?page=2&limit=20
GET /users?offset=20&limit=20  (page=2 → offset=(2-1)*20=20)
GET /users?skip=20&take=20     (Prisma style)
```

### How It Works in SQL

```sql
-- page=2, limit=20
SELECT * FROM users
ORDER BY created_at DESC
LIMIT 20 OFFSET 20;
```

### Response Shape

```json
{
  "data": [...],
  "pagination": {
    "page": 2,
    "limit": 20,
    "total": 1547,
    "totalPages": 78,
    "hasNext": true,
    "hasPrev": true
  }
}
```

Or via headers (GitHub style):
```http
X-Total-Count: 1547
Link: <https://api.example.com/users?page=3&limit=20>; rel="next",
      <https://api.example.com/users?page=1&limit=20>; rel="prev",
      <https://api.example.com/users?page=78&limit=20>; rel="last"
```

### Problems with Offset Pagination

**1. Performance degrades at large offsets**

```sql
-- Looks harmless:
SELECT * FROM users ORDER BY created_at DESC LIMIT 20 OFFSET 1000000;

-- In practice: the DB reads and discards 1,000,000 rows,
-- then returns 20. A full index scan.
-- On a 10M-row table — seconds of wait time.
```

**2. Data drift**

```txt
Initial state: [A, B, C, D, E, F]

Client fetches page=1: [A, B, C]
Someone deletes A.
Client fetches page=2: [D, E, F] → OFFSET 3 → [E, F, ...]
                                                 ↑ D is skipped!

Or someone inserts X at the start:
Client fetches page=2: OFFSET 3 → [C, D, E]
                                    ↑ C is duplicated!
```

**3. No parallel processing**

You can't reliably say "rows from X to Y" for parallel download.

### When to Use Offset

- The user navigates to a specific page number ("go to page 42")
- Data changes infrequently (catalogs, reference data)
- The table is relatively small (up to ~100K rows)
- A `total` count is needed for a page counter UI

---

## Cursor-Based Pagination

Instead of "skip N records" — "give me records after this specific record." The cursor is an opaque pointer to a position in the dataset.

```txt
GET /users?limit=20                    ← first page
GET /users?cursor=eyJpZCI6MjB9&limit=20 ← next (cursor from previous response)
```

### How It Works

```json
// First page response:
{
  "data": [
    { "id": 1, "name": "Alice" },
    ...
    { "id": 20, "name": "Bob" }
  ],
  "pagination": {
    "nextCursor": "eyJpZCI6MjB9",
    "hasNext": true
  }
}
```

The cursor is a base64-encoded JSON with the data needed for the next query:
```typescript
// Encoding:
const cursor = Buffer.from(JSON.stringify({ id: lastItem.id })).toString("base64url");

// Decoding:
const { id } = JSON.parse(Buffer.from(cursor, "base64url").toString());
```

### The SQL Underneath

```sql
-- First page:
SELECT * FROM users
ORDER BY id DESC
LIMIT 20;

-- Next page (cursor contains id=20):
SELECT * FROM users
WHERE id < 20
ORDER BY id DESC
LIMIT 20;
```

This is keyset pagination: instead of `OFFSET`, a `WHERE` clause. The index is used efficiently regardless of position.

### Cursor on a Composite Key

If sorting by a non-unique column (e.g. `created_at`), you need a composite cursor:

```sql
-- created_at can be identical for multiple rows
SELECT * FROM posts
WHERE (created_at, id) < ('2024-01-15 10:00:00', 42)
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

The cursor encodes both fields:
```typescript
const cursor = Buffer.from(
  JSON.stringify({ createdAt: lastItem.createdAt, id: lastItem.id })
).toString("base64url");
```

### Advantages and Limitations

```txt
Advantages:
  ✅ Stable: inserts/deletes don't break pagination
  ✅ Performant: O(log n) via index instead of O(n) at large offsets
  ✅ Perfect for infinite scroll and real-time feeds
  ✅ Correct under concurrent data changes

Limitations:
  ❌ Cannot jump directly to page 42
  ❌ Cannot display "page 2 of 78"
  ❌ Usually forward-only (backward requires a reverse cursor)
  ❌ No total count without an expensive COUNT(*) query
```

### Bidirectional Cursor Pagination

```json
{
  "data": [...],
  "pagination": {
    "startCursor": "eyJpZCI6MX0",
    "endCursor": "eyJpZCI6MjB9",
    "hasNextPage": true,
    "hasPreviousPage": false
  }
}
```

GraphQL (Relay spec) uses exactly this model:
```graphql
{
  users(first: 20, after: "cursor") {
    edges { node { id name } cursor }
    pageInfo { hasNextPage endCursor }
  }
}
```

---

## Comparison

```txt
┌─────────────────────┬──────────────────┬──────────────────────┐
│                     │ Offset/Page      │ Cursor               │
├─────────────────────┼──────────────────┼──────────────────────┤
│ Jump to page N      │ ✅ Easy           │ ❌ Not possible      │
│ Total count         │ ✅ Available      │ ❌ Expensive         │
│ Infinite scroll     │ ⚠️ Drift issues   │ ✅ Ideal             │
│ Performance         │ ❌ O(n) at >100K  │ ✅ O(log n) always   │
│ Stability           │ ❌ Drift on DML   │ ✅ Stable            │
│ Implementation      │ ✅ Simple         │ ⚠️ More complex      │
│ Real-time feed      │ ❌ Not suitable   │ ✅ Ideal             │
└─────────────────────┴──────────────────┴──────────────────────┘

Decision rule:
  Classic table with page numbers → offset
  Infinite scroll / feeds / large data → cursor
```

---

## Filtering

### Simple Filters via Query Params

```txt
GET /users?status=active
GET /users?role=admin&status=active          (AND)
GET /products?categoryId=5&inStock=true
GET /orders?userId=42
```

### Multiple Values (OR on a Single Field)

```txt
Option 1 — repeated parameter (preferred):
GET /users?status=active&status=pending

Option 2 — bracket notation:
GET /users?status[]=active&status[]=pending

Option 3 — comma-separated:
GET /users?status=active,pending
```

Express parses repeated query params as an array automatically (via `req.query.status`).

### Comparison Operators

For numeric and date/time filters you need operators:

```txt
Option 1 — suffix:
GET /orders?totalGte=100&totalLte=500
GET /users?createdAfter=2024-01-01&createdBefore=2024-12-31

Option 2 — bracket notation:
GET /orders?total[gte]=100&total[lte]=500
GET /users?created[after]=2024-01-01

Option 3 — Prisma/API style:
GET /orders?filter=total:gte:100,total:lte:500
```

There's no universal standard. The important thing is to be consistent and document it.

### Search

```txt
GET /users?q=alice                   — full-text search
GET /users?search=alice              — same, different param name
GET /products?name=iphone&fuzzy=true — fuzzy search
```

At the SQL level:
```sql
-- LIKE (simple):
WHERE name ILIKE '%alice%'

-- Full-text search (PostgreSQL):
WHERE to_tsvector('english', name || ' ' || email) @@ to_tsquery('english', 'alice')

-- For serious search: Elasticsearch, Meilisearch, pg_trgm
```

---

## Sorting

```txt
Single column:
GET /users?sort=createdAt&order=desc
GET /users?sort=name&order=asc
GET /users?sort=-createdAt            (minus = desc — popular convention)
GET /users?sort=+name                 (plus = asc)

Multiple columns:
GET /users?sort=-createdAt,name       (desc by date, then asc by name)
```

### Sorting Safety

Never interpolate a sort field directly into SQL:

```typescript
// ❌ SQL Injection:
const query = `SELECT * FROM users ORDER BY ${req.query.sort}`;

// ✅ Whitelist of allowed fields:
const SORTABLE_FIELDS = new Set(["createdAt", "name", "email", "id"]);
const sortField = SORTABLE_FIELDS.has(req.query.sort as string)
  ? req.query.sort as string
  : "createdAt";
```

---

## Sparse Fieldsets (Field Selection)

```txt
GET /users?fields=id,name,email
GET /users?select=id,name,email
GET /users?include=profile,orders     (include related entities)
GET /users?exclude=password,internalNotes
```

Useful for:
- Reducing response size (especially for mobile clients)
- Excluding sensitive fields
- Performance (SELECT only needed columns)

Also needs a whitelist:
```typescript
const ALLOWED_FIELDS = new Set(["id", "name", "email", "createdAt", "role"]);
const requestedFields = (req.query.fields as string)?.split(",") ?? [];
const fields = requestedFields.filter(f => ALLOWED_FIELDS.has(f));
```

---

## Full Example: Express + Prisma

```typescript
import { Request, Response } from "express";
import { prisma } from "../lib/prisma";
import { z } from "zod";

const listUsersSchema = z.object({
  // Pagination
  cursor: z.string().optional(),
  limit: z.coerce.number().int().min(1).max(100).default(20),
  // Filtering
  status: z.union([z.string(), z.array(z.string())]).optional(),
  role: z.string().optional(),
  q: z.string().optional(),
  // Sorting
  sort: z.enum(["createdAt", "name", "email"]).default("createdAt"),
  order: z.enum(["asc", "desc"]).default("desc"),
});

export async function listUsers(req: Request, res: Response) {
  const parsed = listUsersSchema.safeParse(req.query);
  if (!parsed.success) {
    return res.status(400).json({ error: parsed.error.flatten() });
  }

  const { cursor, limit, status, role, q, sort, order } = parsed.data;

  // Decode cursor
  let cursorId: number | undefined;
  if (cursor) {
    try {
      const decoded = JSON.parse(Buffer.from(cursor, "base64url").toString());
      cursorId = decoded.id;
    } catch {
      return res.status(400).json({ error: "Invalid cursor" });
    }
  }

  // Build filter
  const where: Record<string, unknown> = {};

  if (status) {
    const statuses = Array.isArray(status) ? status : [status];
    where.status = { in: statuses };
  }

  if (role) where.role = role;

  if (q) {
    where.OR = [
      { name: { contains: q, mode: "insensitive" } },
      { email: { contains: q, mode: "insensitive" } },
    ];
  }

  // Fetch limit+1 to determine hasNext
  const users = await prisma.user.findMany({
    where,
    orderBy: { [sort]: order },
    take: limit + 1,
    ...(cursorId ? { cursor: { id: cursorId }, skip: 1 } : {}),
    select: { id: true, name: true, email: true, status: true, createdAt: true },
  });

  const hasNext = users.length > limit;
  const data = hasNext ? users.slice(0, limit) : users;

  const lastItem = data.at(-1);
  const nextCursor = hasNext && lastItem
    ? Buffer.from(JSON.stringify({ id: lastItem.id })).toString("base64url")
    : null;

  res.set("X-Total-Count", String(await prisma.user.count({ where })));

  res.json({
    data,
    pagination: { nextCursor, hasNext, limit },
  });
}
```

---

## Rate Limiting as a Pagination Guard

Large `limit` values or aggressive scraping through pages can overload the server:

```typescript
// Cap the maximum limit:
limit: z.coerce.number().int().min(1).max(100).default(20)

// Rate limiting middleware:
import rateLimit from "express-rate-limit";

const apiLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: 100,            // 100 requests per minute
  standardHeaders: true,
  legacyHeaders: false,
});

app.use("/api/", apiLimiter);
```

Response on limit exceeded:
```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1719187260
```

---

## Common Interview Traps

- **"Offset pagination is always fine"** — no. On tables >100K rows, `OFFSET 50000` can take seconds. For infinite scroll or real-time feeds, offset is the wrong choice due to data drift.

- **"A cursor is just the ID of the last item"** — not necessarily. A cursor is an opaque token the client must not interpret. Internally it might be a composite key, timestamp + id, or any data needed to reproduce the position. Opacity is intentional: the server can change the format without breaking the API contract.

- **"OFFSET 0 is always fast"** — `OFFSET 0` is fast. `OFFSET 5000000` is not. That's exactly why cursor pagination exists.

- **"Filtering with WHERE field = value is enough"** — no index on the filter column means a full table scan. Classic production problem: the query ran fast on test data, then collapsed in production at 10M rows.

- **"Sorting with `ORDER BY req.query.sort` is fine"** — SQL injection. Sort fields must always be validated against a whitelist.

- **"total count is always needed"** — `COUNT(*)` on a large filtered table can be expensive. Sometimes the right answer is: don't return an exact total, just return `hasNext`. Instagram, Twitter/X don't show "page 2 of 847."

- **"Cursor-based pagination doesn't support going backward"** — technically it does, but requires a reverse cursor (sorting in the opposite direction). Most implementations only support forward, which is enough for infinite scroll.
