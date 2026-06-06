# Redis Caching Patterns

## The Most Popular Redis Use Case

In most projects Redis is used as:

```txt
Cache Layer
```

---

# Why Cache is Needed

Without cache:

```txt
Request
 ↓
PostgreSQL
 ↓
Response
```

---

Every request:

```txt
goes to the database
```

---

# With Cache

```txt
Request
 ↓
Redis
 ↓
Hit
 ↓
Response
```

---

The database is not involved.

---

# Cache Aside Pattern

The most popular pattern.

---

Also known as:

```txt
Lazy Loading
```

---

Flow:

```txt
Request
 ↓
Redis
 ↓
Miss
 ↓
Database
 ↓
Redis
 ↓
Response
```

---

# Pseudocode

```ts
let user =
 await redis.get(key);

if (!user) {

 user =
  await db.user.find();

 await redis.set(
  key,
  user,
  ttl
 );
}

return user;
```

---

# Advantages

```txt
simplicity

memory efficiency

data is cached only when needed
```

---

# Disadvantage

The first request:

```txt
is always slow
```

---

# Write Through

Another pattern.

---

On write:

```txt
Database
+
Redis
```

---

Are updated simultaneously.

---

Flow:

```txt
Update User
 ↓
Database
 ↓
Redis
```

---

# Pros

Cache is always up to date.

---

# Cons

Writes become slower.

---

# Write Behind

Rare question.

---

Write to:

```txt
Redis
```

---

And the database is updated later.

---

```txt
Redis
 ↓
Async Flush
 ↓
Database
```

---

# Pros

Very fast writes.

---

# Cons

Data can be lost.

---

# Cache Invalidation

One of the two hardest problems.

---

There's a joke:

```txt
There are only two hard things:

Cache Invalidation

Naming Things
```

---

The problem.

---

A user updated their profile.

---

Redis holds the old version.

---

# Solution #1

Delete the cache.

---

```ts
await redis.del(
 `user:${id}`
);
```

---

The next request:

```txt
Cache Miss
```

---

Will fetch fresh data from the database.

---

# Solution #2

Update the cache immediately.

---

```ts
await redis.set(...)
```

---

After updating the database.

---

# TTL Strategy

Very popular approach.

---

```txt
Cache lives for

5 minutes

10 minutes

1 hour
```

---

Then it is deleted.

---

# Cache Stampede

Very popular Senior question.

---

The problem.

---

TTL expired.

---

Simultaneously:

```txt
1000 requests
```

---

All go to the database.

---

We get:

```txt
DB Overload
```

---

# Solution #1

Mutex Lock.

---

```txt
The first request
updates the cache

the rest wait
```

---

# Solution #2

Random TTL.

---

Instead of:

```txt
60 seconds
```

---

Use:

```txt
60 ± random
```

---

Keys expire at different times.

---

# Cache Penetration

Another popular question.

---

The problem.

---

A user constantly requests:

```txt
user:99999999
```

---

Which doesn't exist.

---

Every time:

```txt
Redis Miss
 ↓
Database
```

---

# Solution

Cache:

```txt
NULL
```

---

For a short time.

---

# Cache Avalanche

Rare question.

---

Many keys expired at the same time.

---

All load goes to the database.

---

Similar to:

```txt
Cache Stampede
```

---

But affects many keys.

---

# Common Question

Which caching pattern is used most often?

Answer:

```txt
Cache Aside
```

---

# Common Question

What is Cache Stampede?

Answer:

A situation where, after a TTL expires, a large number of requests simultaneously start reading data from the database.

---

# Common Question

How to invalidate cache?

Answer:

By deleting the key after updating data, or by updating the cache immediately after writing.

---

# Interview Answer

The most popular caching pattern is Cache Aside. The application first tries to get data from Redis, and on a miss goes to the database and saves the result to cache. The main caching problems include Cache Stampede, Cache Penetration, and Cache Invalidation.
