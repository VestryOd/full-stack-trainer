# System Design Fundamentals

## What is System Design

System Design is the process of architecting a system.

---

In interviews you are evaluated on:

```txt
decision-making ability

understanding trade-offs

scalability

reliability
```

---

# The Most Important Idea

There is no:

```txt
perfect architecture
```

---

There are only:

```txt
trade-offs
```

---

# Typical Question

Design:

```txt
a chat

Instagram

YouTube

URL Shortener
```

---

The interviewer does not expect a perfect answer.

---

They want to understand:

```txt
how you think
```

---

# First Rule

Never start drawing the architecture right away.

---

First clarify the requirements.

---

# Functional Requirements

What the system must do.

---

For example, a chat:

```txt
send messages

receive messages

group chats
```

---

# Non Functional Requirements

How the system must perform.

---

For example:

```txt
100ms latency

1 million users

99.99 uptime
```

---

A very important topic.

---

# Scale Estimation

Interviewers love asking about this.

---

For example:

```txt
1 million users
```

---

Of those:

```txt
100k daily active
```

---

# Why This Is Needed

To understand:

```txt
database size

load

traffic
```

---

# Core Building Blocks

Almost any system consists of:

```txt
Client

API

Database

Cache

Queue

Storage
```

---

# Basic Architecture

```txt
Client
 ↓
API
 ↓
Database
```

---

Almost everything starts exactly like this.

---

# Single Point Of Failure

Interviewers love asking about this.

---

A component:

```txt
without redundancy
```

---

If it goes down:

```txt
the entire system goes down
```

---

# Example

```txt
1 Database
```

---

With no replicas.

---

# Availability

Uptime.

---

For example:

```txt
99.9%

99.99%

99.999%
```

---

# What 99.9% Means

Approximately:

```txt
8.7 hours of downtime per year
```

---

# Latency

Response time.

---

For example:

```txt
50ms
100ms
300ms
```

---

# Throughput

Number of operations.

---

For example:

```txt
1000 RPS
```

---

Requests Per Second.

---

# Vertical Scaling

A very popular question.

---

We increase the server.

---

```txt
8 GB RAM
 ↓
32 GB RAM
```

---

# Pros

Simple.

---

# Cons

There is a limit.

---

# Horizontal Scaling

We add servers.

---

```txt
Server 1

Server 2

Server 3
```

---

# Pros

Nearly unlimited growth.

---

# Cons

Complexity is introduced.

---

# Stateless Services

Interviewers love asking about this.

---

The server holds no state.

---

Any request can land:

```txt
on any server
```

---

# State

For example:

```txt
Session Memory
```

---

hinders scaling.

---

# Stateless

Therefore people often use:

```txt
JWT

Redis

Database
```

---

to store state.

---

# Read Heavy Systems

The majority of web applications.

---

For example:

```txt
Instagram

YouTube

News Sites
```

---

Reads far outnumber writes.

---

# Write Heavy Systems

For example:

```txt
Analytics

IoT

Logs
```

---

# Why This Matters

The choice of these depends on it:

```txt
Database

Cache

Queues
```

---

# Common Question

What is more important: Availability or Consistency?

Answer:

It depends on the business.

---

Bank:

```txt
Consistency
```

---

Social network:

```txt
Availability
```

---

# Interview Answer

System Design is the process of building scalable, reliable, and maintainable systems. In interviews the most important thing is to first clarify requirements, estimate the load, and only then choose architectural solutions.
