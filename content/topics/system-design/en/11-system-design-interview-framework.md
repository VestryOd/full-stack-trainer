# Universal System Design Interview Framework

## The Most Important Idea

In an interview you are not evaluated on the architecture.

---

You are evaluated on:

```txt
the thought process
```

---

The interviewer wants to see:

```txt
structured thinking

understanding of trade-offs

ability to scale a system
```

---

# The Main Mistake

The candidate immediately starts drawing:

```txt
Redis

Kafka

PostgreSQL

Load Balancer
```

---

Without understanding the problem.

---

# The Right Order

Always:

```txt
1 Requirements

2 Scale

3 API

4 Data Model

5 High Level Design

6 Bottlenecks

7 Scaling
```

---

# Step 1

Clarify requirements.

---

Interviewers love watching this.

---

# Functional Requirements

What the system must do.

---

Example for a chat:

```txt
Send Messages

Receive Messages

Group Chats
```

---

# Functional Requirements

For URL Shortener:

```txt
Create Short URL

Redirect

Analytics
```

---

# Non Functional Requirements

Very important.

---

For example:

```txt
Latency

Availability

Consistency

Durability
```

---

# Example

Chat:

```txt
Latency is critical
```

---

Bank:

```txt
Consistency is critical
```

---

# Step 2

Scale estimation.

---

Interviewers love asking about this.

---

# Example

```txt
10M users

1M DAU
```

---

# Calculate

For example:

```txt
100 req/sec

1000 req/sec

10000 req/sec
```

---

# Why

To understand:

```txt
is one server enough?

or is a cluster needed?
```

---

# A Rough Estimate Is Often Enough

The interviewer does not expect exact math.

---

# Step 3

Define the API.

---

Example:

```http
POST /messages

GET /messages
```

---

Or:

```http
POST /short-url

GET /{code}
```

---

# Step 4

Design the data.

---

A very important step.

---

# Tables

For example:

```sql
users

messages

chats
```

---

Or:

```sql
urls

analytics
```

---

# The Interviewer Wants to See

That you can model data.

---

# Step 5

High Level Design

---

Now draw the architecture.

---

The most common template.

---

```txt
Client
 ↓
Load Balancer
 ↓
API
 ↓
Cache
 ↓
Database
```

---

# Or

```txt
Client
 ↓
API
 ↓
Queue
 ↓
Workers
```

---

# Or

```txt
Client
 ↓
WebSocket
 ↓
Redis
 ↓
Database
```

---

# Do Not Over-Engineer

A very important rule.

---

Start:

```txt
with a simple solution
```

---

Then scale.

---

# Step 6

Find Bottlenecks

---

The favorite question.

---

The interviewer will almost always ask:

```txt
What will break first?
```

---

Typical answers:

```txt
Database

Network

File Storage

WebSocket Connections
```

---

# Database

The most common bottleneck.

---

Solution:

```txt
Cache

Read Replicas

Sharding
```

---

# API

The next bottleneck.

---

Solution:

```txt
Horizontal Scaling
```

---

# File Storage

Solution:

```txt
S3

CDN
```

---

# Step 7

Scaling

---

Interviewers love asking about this.

---

# Stateless Services

Almost always the first answer.

---

```txt
JWT

Redis

Database
```

---

Instead of Session Memory.

---

# Read Scaling

Use:

```txt
Read Replicas
```

---

# Heavy Computation

Use:

```txt
Queue
 ↓
Workers
```

---

# Static Content

Use:

```txt
CDN
```

---

# Realtime

Use:

```txt
WebSockets
```

---

# Frequently Encountered Components

## Redis

When is it needed?

---

```txt
Cache

Sessions

Presence

Rate Limiting
```

---

## Queue

When is it needed?

---

```txt
Emails

Notifications

Reports

Background Jobs
```

---

## S3

When is it needed?

---

```txt
Images

Videos

Documents
```

---

## CDN

When is it needed?

---

```txt
Static Content
```

---

## WebSocket

When is it needed?

---

```txt
Realtime
```

---

# A Very Important Section

Trade-Offs

---

A Senior question.

---

Do not say:

```txt
this is better
```

---

Say:

```txt
this is a trade-off
```

---

# Example

Redis.

---

Pros:

```txt
fast
```

---

Cons:

```txt
cache invalidation

complexity
```

---

# Example

Microservices.

---

Pros:

```txt
scaling
```

---

Cons:

```txt
complexity
```

---

# Example

Event Driven Architecture.

---

Pros:

```txt
loose coupling
```

---

Cons:

```txt
harder to debug
```

---

# The Most Common Answer Structure

```txt
Requirements

↓

Scale Estimation

↓

API Design

↓

Data Model

↓

High Level Design

↓

Bottlenecks

↓

Scaling

↓

Trade-Offs
```

---

# Universal Architecture

For most problems.

---

```txt
Users
 ↓
Load Balancer
 ↓
API Servers
 ↓
Redis
 ↓
PostgreSQL

Queue
 ↓
Workers

S3
 ↓
CDN
```

---

# Common Question

What to do if PostgreSQL can no longer keep up?

Answer:

```txt
Redis

Read Replicas

Sharding
```

---

# Common Question

What to do if the API responds slowly?

Answer:

Find the bottleneck.

---

Usually:

```txt
DB

External API

Heavy Computation
```

---

# Common Question

How to demonstrate Senior level?

Answer:

Discuss:

```txt
Trade-Offs

Consistency

Availability

Scalability
```

---

# The Strongest Interview Answer

When the interviewer asks:

"Which architecture would you choose?"

---

Answer:

```txt
It depends on the requirements.

I would first clarify the load,
the latency requirements,
availability and consistency needs,
and then choose an architecture
based on those constraints.
```

---

# Interview Answer

Any System Design problem should be approached with the same algorithm: first clarify requirements, then estimate scale, design the API and data model, build a basic architecture, identify potential bottlenecks, and only then discuss scaling and trade-offs.
