# Redis Persistence

## Very Popular Question

If Redis stores data in memory:

```txt
RAM
```

---

What happens after:

```txt
a server restart?
```

---

Answer:

```txt
data will be lost
```

---

if Persistence is not configured.

---

# What is Persistence

A mechanism for saving data to disk.

---

Redis supports:

```txt
RDB

AOF

RDB + AOF
```

---

# RDB

Redis Database Snapshot.

---

The simplest mode.

---

# How It Works

Redis periodically takes a:

```txt
memory snapshot
```

---

And saves it as:

```txt
dump.rdb
```

---

To disk.

---

# Schema

```txt
Memory
 ↓
Snapshot
 ↓
dump.rdb
```

---

# Example

Every:

```txt
5 minutes
```

---

A new snapshot is created.

---

# Pros

```txt
fast

small file size

fast recovery
```

---

# Cons

Very frequently asked.

---

Data can be lost.

---

For example:

```txt
Snapshot was at 12:00

Redis crashed at 12:04
```

---

We lose:

```txt
4 minutes of data
```

---

# AOF

Append Only File.

---

A different approach.

---

# How It Works

Every write command:

```bash
SET

DEL

INCR
```

---

Is written to a log.

---

Example:

```txt
SET user:1 John

SET user:2 Alice

INCR counter
```

---

# Recovery

After a restart:

```txt
Redis replays the commands
```

---

From the log.

---

# Pros

Less data loss.

---

# Cons

```txt
more disk space

slower writes
```

---

# fsync

Very popular question.

---

Determines:

```txt
when to write to disk
```

---

# always

```txt
every operation
```

---

Most reliable mode.

---

Slowest.

---

# everysec

Default.

---

```txt
once per second
```

---

A trade-off between:

```txt
speed

reliability
```

---

# no

The OS decides.

---

Fastest.

---

Most risky.

---

# RDB + AOF

The most popular production option.

---

We get:

```txt
fast startup

+
minimal data loss
```

---

# Replication

Very popular topic.

---

Master:

```txt
primary Redis
```

---

Replica:

```txt
a copy
```

---

Schema:

```txt
Master
 ↓
Replica 1

Replica 2
```

---

# Why Replicas

```txt
Read Scaling

Failover

Backup
```

---

# Redis Sentinel

Very frequently asked.

---

Monitors:

```txt
Master
```

---

If Master goes down:

```txt
elects a new Master
```

---

Automatically.

---

# Redis Cluster

The next level.

---

Solves:

```txt
scaling
```

---

Data is distributed across nodes.

---

# Sharding

Very popular question.

---

Data partitioning.

---

For example:

```txt
Node 1
users 1-100000

Node 2
users 100001-200000
```

---

# Redis as Primary Database

Very frequently asked.

---

Technically:

```txt
possible
```

---

In practice:

```txt
rare
```

---

Usually:

```txt
PostgreSQL

+
Redis
```

---

# Common Question

Which is better, RDB or AOF?

Answer:

RDB is faster and more compact, AOF is more reliable and allows losing less data.

---

# Common Question

What is used in production?

Answer:

Most often RDB and AOF simultaneously.

---

# Common Question

What is Redis Sentinel?

Answer:

A Redis monitoring and automatic failover mechanism.

---

# Common Question

What is Redis Cluster?

Answer:

A distributed Redis cluster for horizontal data scaling.

---

# Interview Answer

Redis stores data in memory, so Persistence mechanisms are used to preserve data across restarts. The main options are RDB snapshots and AOF logs. In production systems, a combination of both approaches is often used together with replication, Sentinel, or Redis Cluster to ensure high availability.
