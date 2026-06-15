# WebSockets and Realtime Systems

## The problem: HTTP is request/response, but the server needs to "speak first"

HTTP's model is that the client initiates and the server responds. The server can't send data to the client outside of a response to a request. But many products (chat, live notifications, price tickers, collaborative editing) need exactly that: **the server initiates a send** when an event happens.

## Comparing approaches to realtime

| Approach | How it works | Latency | Overhead | When it fits |
|---|---|---|---|---|
| **Short Polling** | The client sends `GET /messages` every N seconds | Up to N seconds | Very high — most requests return "nothing new" | Almost never optimal, but simple to implement |
| **Long Polling** | The client sends a request, the server holds it open until data arrives or it times out, then the client immediately sends a new one | Low | Medium — the connection is held but reopened | When WebSocket isn't available (old proxies/firewalls), low event frequency |
| **Server-Sent Events (SSE)** | A single HTTP connection, the server writes events into a stream (`text/event-stream`) | Low | Low, but **server → client only** | Notifications, live feeds, progress for long-running tasks — where the client doesn't need to "talk back" on the same channel |
| **WebSocket** | A full bidirectional connection after a handshake | Minimal | Low, persistent connection | Chat, games, collaborative editing — needs **mutual** low-latency transfer |

Senior nuance: SSE is often overlooked, yet it's a significantly simpler solution than WebSocket when communication is **one-way** (server → client) — it runs over plain HTTP (passes through corporate proxies/load balancers more easily, and automatic reconnect is built into the browser's `EventSource` API). Proposing WebSocket for "show the user live notifications" works but is overkill; SSE solves it more simply.

## WebSocket Handshake — why it matters architecturally

```http
Client:
GET /chat HTTP/1.1
Host: example.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==

Server:
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: ...
```

The key practical point: the connection **starts as a regular HTTP request** and "switches" to the WebSocket protocol via `101 Switching Protocols`. This means:

- an L7 load balancer must explicitly support and pass through `Upgrade` headers (not all Nginx/ALB configurations do this by default — a common cause of "WebSocket works locally, doesn't work behind the load balancer");
- after the handshake, the connection is **long-lived** (stateful) — fundamentally different from regular short HTTP requests, and it affects how the load balancer and infrastructure must handle it (timeouts, keep-alive, per-instance connection limits).

## The core architectural challenge: the connection is pinned to a specific server

This is the **most important senior question** in this topic, and the old version of this article correctly flagged it but without details on solving it.

```txt
10 servers behind a load balancer

User A is connected via WebSocket to Server #3
User B is connected via WebSocket to Server #8

User A sends a message intended for User B
  → lands on Server #3 (where A's connection is)
  → but User B's WebSocket connection lives on Server #8

Server #3 physically cannot "write" to the socket owned by Server #8
```

### Solution: Pub/Sub as a cross-instance bus

```txt
Server #3 (received the message from User A)
   ↓ publishes to Redis Pub/Sub channel "user:B:messages"
Redis Pub/Sub
   ↓ delivers to all subscribed instances
Server #8 (subscribed to "user:B:messages" because it holds User B's connection)
   ↓ writes to User B's WebSocket connection
User B receives the message
```

```ts
// When User B connects, Server #8 subscribes to their channel
const subscriber = redis.duplicate();
await subscriber.subscribe(`user:${userId}:messages`);
subscriber.on('message', (channel, payload) => {
  const socket = activeConnections.get(userId);
  socket?.send(payload); // delivered into the specific open WebSocket
});

// Any server that receives a message for userId publishes it
await redis.publish(`user:${recipientId}:messages`, JSON.stringify(message));
```

This is the same pattern as Pub/Sub from the Message Queues topic — Redis Pub/Sub fits small/medium scale (low latency, simple); at large scale, Kafka/NATS are used, which add persistence (if a consumer is briefly disconnected, a Redis Pub/Sub message is lost forever; with Kafka it isn't).

### Connection Registry — "who's on which server"

For channels/rooms (rather than individual users), you need another component — a registry answering "which servers hold connections for members of room X":

```txt
Redis: room:42:servers = {server-3, server-8, server-15}

On joining a room: SADD room:42:servers <server-id>
On disconnect:     SREM room:42:servers <server-id>

Broadcasting to a room:
  for server in room:42:servers:
    publish to "server:<id>:broadcast" channel
```

Without this registry, a server would have to publish to **every** instance "just in case" — that works at small scale but doesn't scale to thousands of rooms.

## Presence (online/offline) — TTL instead of explicit disconnect

```txt
Problem: a WebSocket connection can die "silently"
(network loss, laptop closed) without an explicit close event —
the server doesn't always learn that the client disconnected
```

Solution — heartbeat + TTL in Redis:

```ts
// Client sends a heartbeat every 30 seconds
// Server refreshes the TTL on each heartbeat
await redis.set(`presence:user:${userId}`, 'online', 'EX', 60); // 60-second TTL

// If no heartbeat arrives within 60 seconds, the key expires on its own,
// presence:user:123 stops existing → the user is "offline"
// (no need for an explicit disconnect handler)
```

The TTL approach is more reliable than "handle onDisconnect," because the disconnect event may never fire on an abrupt network failure — but the TTL is guaranteed to expire regardless of whether the server received a disconnect notification.

## Delivery Guarantees in chat — offline delivery

WebSocket delivers a message only if the recipient is **currently online**. For offline users, you need a separate path:

```txt
1. The message is always written to the DB first (source of truth) — the Message Service
2. Then delivery via WebSocket is attempted (if the user is online)
3. If the user is offline:
   - the message stays in the DB with status "unread"
   - (optionally) a push notification via APNs/FCM
4. On the next connection, the client requests
   "all messages since last_seen_message_id" — catching up on what was missed
```

Senior nuance: WebSocket is a **transport for real-time delivery**, not a source of truth or a delivery guarantee. Any reliable realtime system has a regular persist-then-notify model underneath, and WebSocket is just the fastest of the notify paths.

## Load Balancing for WebSocket

```txt
Round Robin for new connections is fine — the server choice
happens once, at connection time.

After that, the connection lives on that server until it's dropped.
This is NOT "sticky session" in the HTTP-cookie sense — it's simply
a physical property of the TCP connection: it's held by one server
by definition, until closed.
```

The main consequence for capacity planning: when a server restarts/deploys, **all** WebSocket connections on it drop simultaneously — clients need reconnect logic (with backoff), and graceful shutdown should signal clients to reconnect before the server fully goes away, rather than just dropping the TCP connection.

## Common interview mistakes

- **Not mentioning that the connection is "stuck" on a specific server** — this is the central scaling challenge for WebSocket, and it's exactly what the interviewer wants to hear.

- **Proposing sticky sessions as the WebSocket scaling solution** — that doesn't solve cross-server delivery, it just describes how the TCP connection already works; the real problem is cross-server delivery via Pub/Sub.

- **Ignoring SSE** — for one-way updates (notifications, live feeds), proposing WebSocket as the only option without mentioning the significantly simpler SSE.

- **Treating WebSocket as a reliable transport** — not explaining persist-then-notify and offline delivery; WebSocket by itself guarantees nothing.

- **Presence via an explicit disconnect handler without TTL** — not accounting for connections that "die silently" with no disconnect event.

- **Not mentioning a connection registry for room-based broadcast** — trying to "broadcast to every server just in case" instead of targeted delivery via a Redis Set/registry.

- **Not discussing client reconnect logic** — when a server deploys/restarts, all its connections drop at once, and without backoff-based reconnects, thousands of clients reconnect simultaneously (a thundering herd at the connection level).
