# System Design Interview Questions

## The Most Popular Tasks for Senior Fullstack Interviews

---

# 1. Design URL Shortener

Example:

```txt
bit.ly
tinyurl
```

---

# What They Check

```txt
ID Generation

Caching

Database Design

Scalability
```

---

# Expected Architecture

```txt
Client
 ↓
API
 ↓
Redis
 ↓
PostgreSQL
```

---

# Key Topics

```txt
Base62

Read Replicas

Analytics Queue
```

---

# Common Follow-Up

How to avoid collisions?

---

Answer:

```txt
Auto Increment
+
Base62
```

---

# 2. Design Chat System

Example:

```txt
Telegram

Slack

WhatsApp
```

---

# What They Check

```txt
WebSockets

Realtime

Presence

Pub/Sub
```

---

# Expected Architecture

```txt
Client
 ↓
WebSocket
 ↓
Chat Service
 ↓
PostgreSQL
```

---

Additionally:

```txt
Redis Pub/Sub
```

---

# Common Follow-Up

How to scale WebSocket?

---

Answer:

```txt
Redis Pub/Sub

Kafka
```

---

# 3. Design Notification System

---

# What They Check

```txt
Queues

Event Driven

Fan Out
```

---

# Expected Architecture

```txt
Producer
 ↓
SNS
 ↓
SQS
 ↓
Workers
```

---

# Common Follow-Up

Why not send email directly?

---

Answer:

```txt
Latency

Fault Tolerance
```

---

# 4. Design File Upload Service

Very popular.

---

# What They Check

```txt
S3

CDN

Queues
```

---

# Good Architecture

```txt
Frontend
 ↓
Backend
 ↓
PreSigned URL

Frontend
 ↓
S3
```

---

# Follow-Up

How to generate thumbnails?

---

Answer:

```txt
S3
 ↓
Queue
 ↓
Worker
```

---

# 5. Design Instagram Feed

One of the most popular tasks.

---

# What They Check

```txt
Feed Generation

Caching

Database Scaling
```

---

# The Core Problem

How to display the feed quickly.

---

# Approach 1

Fan Out On Read.

---

When the user opens the app:

```txt
assemble the feed
```

---

On the fly.

---

# Approach 2

Fan Out On Write.

---

When a post is published:

```txt
pre-update the feed
```

---

of followers.

---

# Common Follow-Up

What would Instagram choose?

---

Answer:

A hybrid.

---

# 6. Design YouTube

Interviewers love asking about this.

---

# What They Check

```txt
Video Storage

CDN

Streaming
```

---

# Architecture

```txt
Upload
 ↓
S3
 ↓
Encoding Queue
 ↓
Workers
 ↓
CDN
```

---

# Follow-Up

Why can't you serve video directly?

---

Answer:

```txt
Bandwidth

Latency
```

---

# 7. Design Dropbox

---

# What They Check

```txt
Large Files

Synchronization

Storage
```

---

# Architecture

```txt
Client
 ↓
API
 ↓
Metadata DB
 ↓
Object Storage
```

---

# Follow-Up

How to synchronize files?

---

Answer:

```txt
Versioning

Change Events
```

---

# 8. Design Ride Sharing

Example:

```txt
Uber

Bolt
```

---

# What They Check

```txt
Geolocation

Realtime

Matching
```

---

# Architecture

```txt
Driver Service

Location Service

Matching Service
```

---

# Follow-Up

How to find nearby drivers?

---

Answer:

```txt
Geohash

Spatial Index
```

---

# 9. Design Booking System

Very popular.

---

Example:

```txt
Booking

Airbnb

Cinema Seats
```

---

# What They Check

```txt
Transactions

Locks

Consistency
```

---

# The Core Problem

Double booking.

---

# Solution

```txt
DB Transaction

Row Lock

Redis Lock
```

---

# Follow-Up

Why is Redis Lock not always needed?

---

Answer:

Often it is enough to use:

```sql
SELECT FOR UPDATE
```

---

# 10. Design News Feed

Very similar to Instagram.

---

# What They Check

```txt
Feed Generation

Ranking

Caching
```

---

# Follow-Up

What will become the bottleneck?

---

Answer:

```txt
Database
```

---

# Solution

```txt
Redis

Read Replicas
```

---

# 11. Design Rate Limiter

Interviewers love asking about this.

---

# What They Check

```txt
Redis

TTL

Counters
```

---

# Solution

```txt
Redis
 ↓
INCR
 ↓
TTL
```

---

# Follow-Up

How to make a distributed limiter?

---

Answer:

```txt
Redis
```

---

# 12. Design Search System

Example:

```txt
Google

Product Search
```

---

# What They Check

```txt
Indexing

Full Text Search
```

---

# Architecture

```txt
PostgreSQL
 ↓
Events
 ↓
Elasticsearch
```

---

# Follow-Up

Why not PostgreSQL LIKE?

---

Answer:

```txt
scales poorly
```

---

# Interviewers' Favorite Topics

If you summarize all the tasks.

---

They almost always come down to:

```txt
Load Balancer

Redis

PostgreSQL

Queue

Workers

S3

CDN

WebSocket
```

---

# Most Common Follow-Up Questions

After any task.

---

# What will become the bottleneck?

---

# How to scale?

---

# What cache to add?

---

# How to prevent data loss?

---

# What if the database goes down?

---

# How to ensure high availability?

---

# How to ensure consistency?

---

# The Strongest Senior Answer

After any architecture.

---

Do not say:

```txt
This is the correct solution.
```

---

Say:

```txt
This is one of the possible approaches.

Further choices depend on:

load

latency requirements

cost

availability

consistency
```

---

# Interview Cheat Sheet

For almost any problem:

```txt
Requirements

↓

Scale Estimation

↓

API

↓

Data Model

↓

Load Balancer

↓

API

↓

Redis

↓

PostgreSQL

↓

Queue

↓

Workers

↓

S3/CDN

↓

Scaling

↓

Trade-Offs
```

---

# Final Thought

On Senior System Design interviews there is almost never a single correct solution.

The interviewer evaluates not the choice of technologies, but the ability to understand requirements, identify system bottlenecks, and make reasoned architectural decisions.
