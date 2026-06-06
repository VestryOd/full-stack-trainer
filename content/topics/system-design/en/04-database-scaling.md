# Database Scaling

## The Most Common Bottleneck

On most projects the first thing to break is:

```txt
Database
```

---

Not the backend.

---

Not the frontend.

---

The DB specifically.

---

# Vertical Scaling

The simplest approach.

---

```txt
16 GB RAM
 ↓
64 GB RAM
```

---

# Pros

Simple.

---

# Cons

There is a limit.

---

# Horizontal Scaling

Add new nodes.

---

# Read Replicas

The most popular approach.

---

```txt
Write
 ↓
Primary DB
 ↓
Replica 1

Replica 2

Replica 3
```

---

# The Idea

Writes go to:

```txt
Primary
```

---

Reads go to:

```txt
Replicas
```

---

# Why It Works

In most systems:

```txt
Read >> Write
```

---

# Replication

Primary sends changes.

---

Replica applies them.

---

# Replication Lag

A very popular question.

---

The Replica can fall behind.

---

For example:

```txt
100ms

500ms

1 sec
```

---

# Consequence

A user updated their profile.

---

Immediately reads it back.

---

Lands on a Replica.

---

Sees old data.

---

# Sharding

The next level.

---

We split the data.

---

For example:

```txt
Users A-M
 ↓
Shard 1

Users N-Z
 ↓
Shard 2
```

---

# Why

When a single DB can no longer keep up.

---

# Problems with Sharding

Interviewers love asking about this.

---

These appear:

```txt
Cross Shard Queries

Joins

Transactions
```

---

become complex.

---

# CQRS

Command Query Responsibility Segregation.

---

We separate:

```txt
Write Database

Read Database
```

---

# Database per Service

Popular in microservices.

---

Each service has:

```txt
its own DB
```

---

# Common Question

When to use Read Replicas?

Answer:

When the system has significantly more read operations than write operations.

---

# Common Question

When to use Sharding?

Answer:

When vertical scaling and replicas can no longer handle the load.

---

# Interview Answer

DB scaling typically starts with Read Replicas. If that is not enough, sharding, CQRS, or splitting data between services are used.
