# WebSockets and Realtime Systems

## The Main Problem with HTTP

HTTP works on a request/response model:

```txt
Request
 ↓
Response
```

---

The server cannot write to the client on its own.

---

# Example

A chat.

---

User A sent a message.

---

How does user B find out?

---

Option #1

Constantly ask the server.

---

```txt
GET /messages
GET /messages
GET /messages
```

---

This is called:

```txt
Polling
```

---

# Downside

A lot of unnecessary requests.

---

# Long Polling

An improved version.

---

The client sends a request.

---

The server keeps the connection open.

---

Until data is available.

---

After the response:

```txt
a new request
```

---

# Downside

Still a lot of HTTP requests.

---

# WebSocket

The solution.

---

After the connection is established:

```txt
Client
 ↕
 Server
```

---

The communication is bidirectional.

---

# Full Duplex

A very popular question.

---

Both client and server can:

```txt
send data
```

---

At any time.

---

# WebSocket Handshake

Interviewers love asking about this.

---

It starts as HTTP.

---

```http
GET /chat

Upgrade: websocket
```

---

The server responds:

```http
101 Switching Protocols
```

---

After that:

```txt
WebSocket
```

---

# Typical Chat Architecture

```txt
Client
 ↓
WebSocket Gateway
 ↓
Message Service
 ↓
Database
```

---

# Message Storage

Very important.

---

Messages are stored in:

```txt
PostgreSQL
```

---

or

```txt
MongoDB
```

---

WebSocket is only needed
for delivery.

---

# Presence

A very popular question.

---

How do we know:

```txt
who is online?
```

---

Usually we use:

```txt
Redis
```

---

Example:

```txt
user:123
online
TTL 60 sec
```

---

# Scaling Problem

A very popular Senior question.

---

There are:

```txt
10 servers
```

---

The user is connected to:

```txt
Server #3
```

---

The message arrived on:

```txt
Server #8
```

---

How do we deliver it?

---

# Solution

Pub/Sub.

---

```txt
Redis Pub/Sub

Kafka

NATS
```

---

# Diagram

```txt
Server 8
 ↓
Redis PubSub
 ↓
Server 3
 ↓
User
```

---

# Sticky Sessions

Another option.

---

Always send the user
to the same server.

---

But scales worse.

---

# Common Question

When to use WebSocket?

Answer:

When the server needs to push data to the client in real time.

---

# Common Question

How is WebSocket better than HTTP?

Answer:

There is no need to constantly create new connections.

---

# Common Question

How to scale WebSocket?

Answer:

Via Redis Pub/Sub or a message broker.

---

# Interview Answer

WebSocket provides a persistent bidirectional connection between client and server and is used for chats, notifications, collaborative document editing, and other realtime systems.
