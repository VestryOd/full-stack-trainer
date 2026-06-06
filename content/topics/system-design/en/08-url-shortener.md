# URL Shortener Design

## Problem Statement

We need to build:

```txt
bit.ly

tinyurl

goo.gl
```

---

Example.

---

Input:

```txt
https://google.com/very/long/url
```

---

Output:

```txt
https://app.com/abc123
```

---

# Step 1

Functional requirements.

---

The system must:

```txt
create short links

redirect users

track statistics
```

---

# Step 2

Basic architecture.

---

```txt
Client
 ↓
API
 ↓
Database
```

---

# Table

```sql
ShortUrls

id

shortCode

longUrl

createdAt
```

---

# The Core Problem

Interviewers love asking about this.

---

How to generate:

```txt
abc123
```

---

# Option 1

Random String

---

```txt
a8fj3x
```

---

Pros:

```txt
simple
```

---

Cons:

```txt
collisions
```

---

# Option 2

Auto Increment

---

```txt
1
2
3
4
```

---

Convert to:

```txt
Base62
```

---

# Base62

Characters:

```txt
0-9
a-z
A-Z
```

---

Total:

```txt
62
```

---

Example:

```txt
125 → cb
```

---

# Why Base62

The link becomes shorter.

---

# Read Path

A very popular question.

---

User opens:

```txt
app.com/abc123
```

---

Flow:

```txt
API
 ↓
Database
 ↓
302 Redirect
```

---

# Problem

If:

```txt
1 million redirects/hour
```

---

The DB will become a bottleneck.

---

# Solution

Redis Cache.

---

```txt
Client
 ↓
Redis
 ↓
Database
```

---

# Cache Hit

Redirect immediately.

---

# Cache Miss

Read from DB.

---

# Analytics

Another popular question.

---

We want to count:

```txt
clicks
```

---

# Bad Solution

```txt
UPDATE clicks
```

---

On every redirect.

---

# Good Solution

```txt
Queue
 ↓
Worker
 ↓
Analytics DB
```

---

# Why

We do not slow down the redirect.

---

# Scaling

Interviewers love asking about this.

---

Reads:

```txt
far outnumber
```

---

Writes.

---

Therefore we use:

```txt
Read Replicas
```

---

# Final Architecture

```txt
User
 ↓
Load Balancer
 ↓
API
 ↓
Redis
 ↓
PostgreSQL
```

---

For analytics:

```txt
API
 ↓
Queue
 ↓
Worker
 ↓
Analytics
```

---

# Common Question

Why use Redis?

Answer:

Most requests are redirects for already-existing links.

---

# Common Question

Why Base62?

Answer:

It allows compactly encoding a numeric ID.

---

# Common Question

Why analytics via a queue?

Answer:

To avoid increasing the redirect latency.

---

# Interview Answer

A URL Shortener is typically built on PostgreSQL for storing links, Redis for caching popular URLs, and queues for asynchronously processing analytics. Base62 encoding of an auto-incremented ID is commonly used for generating short codes.
