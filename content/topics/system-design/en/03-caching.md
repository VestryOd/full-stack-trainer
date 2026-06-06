# Caching

## Why Cache Is Needed

The most popular System Design question.

---

Without cache:

```txt
Client
 ↓
API
 ↓
Database
```

---

Every request goes to the DB.

---

# The Problem

Imagine:

```txt
10000 requests/sec
```

---

To the homepage.

---

All going to PostgreSQL.

---

We get:

```txt
a bottleneck
```

---

# The Solution

Add a Cache Layer.

---

```txt
Client
 ↓
API
 ↓
Redis
 ↓
Database
```

---

# Cache Hit

Data found in the cache.

---

```txt
Redis
 ↓
Response
```

---

The DB is not involved.

---

# Cache Miss

No data found.

---

```txt
Redis
 ↓
Database
 ↓
Redis
 ↓
Response
```

---

# What Is Usually Cached

```txt
Profiles

Products

Catalogs

Settings

Popular Posts
```

---

# What Is Usually NOT Cached

```txt
Bank Balances

Payments

Critical Transactions
```

---

# Cache Aside

The most popular pattern.

---

Flow:

```txt
Read Redis

Miss

Read DB

Write Redis
```

---

# Write Through

On write, update both:

```txt
Database
+
Cache
```

---

# Cache Invalidation

The hardest problem in caching.

---

A user changed their data.

---

Redis still holds old data.

---

# Solution

After UPDATE:

```txt
DEL cache_key
```

---

or:

```txt
SET new value
```

---

# TTL

Time To Live.

---

For example:

```txt
5 minutes
```

---

After which the entry is deleted.

---

# Cache Stampede

A very popular question.

---

Problem:

```txt
TTL expired

10000 requests
```

---

All go to the DB.

---

# Solution

```txt
Mutex

Random TTL

Warm Cache
```

---

# Multi-Level Cache

Advanced level.

---

```txt
Browser Cache

CDN Cache

Redis Cache

Database
```

---

# Common Question

When does Redis help the most?

Answer:

When reads greatly outnumber writes.

---

# Interview Answer

Caching reduces the load on the database and lowers latency. The most popular pattern is Cache Aside using Redis with TTL.
