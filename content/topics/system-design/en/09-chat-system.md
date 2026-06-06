# Chat System Design

## Problem Statement

Design a chat similar to:

```txt
Telegram

WhatsApp

Slack

Messenger
```

---

# Step 1. Clarify Requirements

Very important.

---

# Functional Requirements

```txt
1-on-1 chat

Group chat

Message history

Online status

Read receipts

Typing indicator
```

---

# Non Functional Requirements

```txt
Realtime delivery

High availability

Low latency

Millions of users
```

---

# Basic Architecture

```txt
Client
 ↓
WebSocket Gateway
 ↓
Chat Service
 ↓
Database
```

---

# Why HTTP Does Not Work

Interviewers love asking about this.

---

If you use HTTP:

```txt
GET messages
GET messages
GET messages
```

---

We get Polling.

---

A lot of unnecessary traffic.

---

# Solution

WebSocket.

---

```txt
Client
 ↕
 Server
```

---

Persistent connection.

---

# Sending a Message

Flow:

```txt
User A
 ↓
WebSocket
 ↓
Chat Service
 ↓
Database
 ↓
User B
```

---

# Should You Save the Message First?

Interviewers love asking about this.

---

Yes.

---

Correct order:

```txt
Save Message
 ↓
ACK Sender
 ↓
Deliver Receiver
```

---

# Why

If the server crashes:

```txt
the message is not lost
```

---

# Message Storage

The most common question.

---

Usually:

```txt
PostgreSQL

or

MongoDB
```

---

# PostgreSQL

Suitable when:

```txt
complex queries

filtering

search
```

---

# MongoDB

Suitable when:

```txt
huge volume of messages
```

---

# Messages Table

```sql
messages

id

chat_id

sender_id

text

created_at
```

---

# How to Know Who Is Online

A very popular question.

---

We do not store this in PostgreSQL.

---

We use:

```txt
Redis
```

---

For example:

```txt
online:user:123
```

---

With TTL.

---

# Typing Indicator

```txt
User typing...
```

---

Usually:

```txt
NOT saved
```

---

to DB.

---

Transmitted via:

```txt
WebSocket Event
```

---

# Read Receipts

Interviewers love asking about this.

---

```txt
Seen

Delivered

Read
```

---

Stored in the DB.

---

For example:

```sql
message_status
```

---

# Scaling

The most popular Senior question.

---

There are:

```txt
10 Chat Servers
```

---

User A is on:

```txt
Server #2
```

---

User B is on:

```txt
Server #8
```

---

How do we deliver the message?

---

# Solution

Redis Pub/Sub.

---

```txt
Server 2
 ↓
Redis
 ↓
Server 8
 ↓
User B
```

---

# Even Better

```txt
Kafka
```

---

For very large systems.

---

# Offline Users

Interviewers love asking about this.

---

If the user is not online:

```txt
save the message
```

---

To the DB.

---

When they log in:

```txt
load the history
```

---

# Push Notifications

If the app is closed:

```txt
APNS

FCM
```

---

# Group Chats

A separate table.

---

```sql
chat_members

chat_id

user_id
```

---

# Final Architecture

```txt
Users
 ↓
Load Balancer
 ↓
WebSocket Servers
 ↓
Redis Pub/Sub
 ↓
Chat Service
 ↓
PostgreSQL
```

---

For Push:

```txt
Chat Service
 ↓
Notification Queue
 ↓
Push Worker
 ↓
FCM/APNS
```

---

# Common Question

Why is Redis needed in a chat?

Answer:

For Presence, Pub/Sub, and fast storage of temporary data.

---

# Common Question

Why are messages saved before delivery?

Answer:

To avoid data loss on a failure.

---

# Common Question

Why WebSocket?

Answer:

Because the server can instantly push messages to the client.

---

# Interview Answer

A modern chat is typically built on WebSocket connections, PostgreSQL or MongoDB for message storage, Redis for Presence and Pub/Sub, and queues for sending push notifications. The core architectural goal is to ensure reliable message delivery and the ability to scale horizontally.
