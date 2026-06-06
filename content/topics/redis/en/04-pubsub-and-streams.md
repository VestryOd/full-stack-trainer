# Redis Pub/Sub and Streams

## Redis as a Message Broker

Many people think:

```txt
Redis = Cache
```

---

But Redis also supports:

```txt
Messaging
```

---

# Pub/Sub

Stands for:

```txt
Publish / Subscribe
```

---

Very similar to:

```txt
SNS
```

---

# The Idea

Publisher sends an event.

---

Subscriber receives the event.

---

# Schema

```txt
Publisher
 ↓
Channel
 ↓
Subscriber A

Subscriber B

Subscriber C
```

---

# Publish

```bash
PUBLISH orders
 "created"
```

---

# Subscribe

```bash
SUBSCRIBE orders
```

---

The client now receives messages.

---

# Where It's Used

```txt
Chat

Notifications

Live Updates

WebSockets
```

---

# Main Disadvantage

Very frequently asked.

---

Pub/Sub:

```txt
does NOT store messages
```

---

If a subscriber was disconnected:

```txt
the message is lost
```

---

# Example

```txt
Message Sent
 ↓
Subscriber Offline
 ↓
Message Lost
```

---

# Therefore Pub/Sub is Bad For

```txt
financial operations

orders

critical events
```

---

# Redis Streams

A modern Redis solution.

---

Introduced in Redis 5.

---

Very frequently asked.

---

# Key Difference

Pub/Sub:

```txt
ephemeral
```

---

Streams:

```txt
persistent
```

---

Messages are stored.

---

# Example

```bash
XADD orders *
 status created
```

---

Adds a record to the Stream.

---

# Consumer

Reads:

```bash
XREAD
```

---

Messages.

---

# Stream

Similar to:

```txt
Kafka Lite
```

---

# Why Streams are Better

If a consumer disconnects:

```txt
nothing is lost
```

---

After recovery:

```txt
it reads old messages
```

---

# Consumer Groups

Very popular question.

---

Allow multiple consumers to:

```txt
share the load
```

---

Schema:

```txt
Orders Stream
 ↓
Consumer Group
 ↓
Worker 1

Worker 2

Worker 3
```

---

Each message:

```txt
is processed by one worker
```

---

# ACK

Very important topic.

---

After processing:

```bash
XACK
```

---

The message is acknowledged.

---

# If a Worker Dies

Very frequently asked.

---

The message:

```txt
remains pending
```

---

Another worker can pick it up later.

---

# Pub/Sub vs Streams

The most popular question.

---

Pub/Sub:

```txt
very fast

simple

no storage
```

---

Streams:

```txt
reliable

has history

has replay
```

---

# Streams vs Kafka

Senior question.

---

Kafka:

```txt
distributed log

huge throughput

clustering
```

---

Streams:

```txt
simpler

fewer features

less infrastructure
```

---

# When to Use Pub/Sub

Good for:

```txt
Chat

Live Notifications

Realtime Updates
```

---

# When to Use Streams

Good for:

```txt
Orders

Payments

Background Jobs

Reliable Messaging
```

---

# Common Question

Why is Pub/Sub unreliable?

Answer:

Messages are not stored. If a subscriber was unavailable at the time of publishing, the message is lost.

---

# Common Question

What is a Consumer Group?

Answer:

A Redis Streams mechanism that allows a group of consumers to jointly process messages and distribute the load.

---

# Common Question

What to choose for chat?

Answer:

Pub/Sub.

---

# Common Question

What to choose for order processing?

Answer:

Streams.

---

# Interview Answer

Redis supports two main messaging mechanisms. Pub/Sub provides instant delivery of messages to active subscribers but does not store history. Redis Streams provides a reliable messaging model with message persistence, processing acknowledgment, and Consumer Groups.
