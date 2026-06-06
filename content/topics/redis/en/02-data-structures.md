# Redis Data Structures

## The Most Underrated Redis Topic

Many people think:

```txt
Redis = Key Value
```

---

That's not quite right.

---

Redis supports multiple data structures.

---

# String

The most popular.

---

Example:

```bash
SET user:1 "John"
```

---

Retrieval:

```bash
GET user:1
```

---

Used for:

```txt
Cache

JSON

Tokens

Sessions
```

---

# Counter

Very popular use case.

---

```bash
INCR page_views
```

---

Redis atomically increments the counter.

---

# Why This is Convenient

No need for:

```txt
SELECT

UPDATE
```

---

From the database.

---

# Hash

Very popular structure.

---

Similar to an object.

---

Example:

```bash
HSET user:1
 name John
 age 30
```

---

Retrieval:

```bash
HGET user:1 name
```

---

# When to Use

```txt
User Profile

Settings

Metadata
```

---

# List

A list of elements.

---

Example:

```bash
LPUSH queue task1
```

---

Retrieval:

```bash
RPOP queue
```

---

Very similar to a queue.

---

# Queue

Popular use case.

---

```txt
Producer
 ↓
Redis List
 ↓
Consumer
```

---

# Set

A collection of unique values.

---

Example:

```bash
SADD tags redis
SADD tags node
```

---

Duplicate:

```bash
SADD tags redis
```

---

Will not be added.

---

# When to Use

```txt
Tags

Followers

Permissions
```

---

# Sorted Set

The most loved interview question.

---

Each element has a:

```txt
Score
```

---

Example:

```bash
ZADD leaderboard
 100 user1
 200 user2
```

---

Get ranking:

```bash
ZRANGE
```

---

# Where It's Used

```txt
Leaderboards

Ratings

Top Users

Game Scores
```

---

# Bitmap

Rarely asked.

---

Used for:

```txt
Flags

Feature Tracking

Analytics
```

---

# HyperLogLog

Very rare topic.

---

Allows counting:

```txt
unique users
```

---

With minimal memory.

---

# Stream

A modern structure.

---

Similar to:

```txt
Kafka Lite
```

---

Used for:

```txt
Event Processing

Messaging
```

---

# Common Question

Which structure is used for a Leaderboard?

Answer:

Sorted Set.

---

# Common Question

How to store a user?

Answer:

Most often a Hash.

---

# Common Question

How to implement a view counter?

Answer:

String + INCR.

---

# Common Question

How to implement a queue?

Answer:

List or Streams.

---

# Common Question

What is the difference between Set and Sorted Set?

Answer:

Set stores only unique values, while Sorted Set additionally stores a score and supports sorting.

---

# Interview Answer

Although Redis is often perceived as a key-value store, it actually provides many specialized data structures: Strings, Hashes, Lists, Sets, Sorted Sets, Streams, and more. The choice of structure depends on the nature of the data and the operations that need to be performed.
