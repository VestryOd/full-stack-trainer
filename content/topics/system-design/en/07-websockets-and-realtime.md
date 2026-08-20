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

Senior nuance: SSE is often overlooked, yet it is much simpler than WebSocket when communication is **one-way** (server → client). It runs over plain HTTP, so it passes through corporate proxies and load balancers more easily. Automatic reconnect is built into the browser's `EventSource` API. Proposing WebSocket for "show the user live notifications" works, but it is overkill. SSE solves the same task more simply.

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

- An L7 (layer 7) load balancer must explicitly support and pass through `Upgrade` headers. Layer 7 means the balancer reads HTTP itself, not just raw network packets. Not every Nginx or ALB (Application Load Balancer in Amazon) configuration does this by default. That is a common cause of "WebSocket works locally, doesn't work behind the load balancer".
- After the handshake, the connection is **long-lived** (stateful). That is fundamentally different from regular short HTTP requests. It changes how the load balancer and the infrastructure must handle it: timeouts, keep-alive, and per-instance connection limits.

## The core architectural challenge: the connection is pinned to a specific server

This is the **most important senior question** in this topic.

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
import { createClient } from 'redis'; // node-redis, the `redis` package
import type { WebSocket } from 'ws';

const redis = createClient();
await redis.connect();

const activeConnections = new Map<string, WebSocket>();

// When User B connects, Server #8 subscribes to their channel
async function subscribeForUser(userId: string): Promise<void> {
  const subscriber = redis.duplicate(); // a subscribed connection does nothing else
  await subscriber.connect();
  await subscriber.subscribe(`user:${userId}:messages`, (payload) => {
    const socket = activeConnections.get(userId);
    socket?.send(payload); // delivered into the specific open WebSocket
  });
}

// Any server that receives a message for userId publishes it
async function publishToUser(recipientId: string, message: unknown): Promise<void> {
  await redis.publish(`user:${recipientId}:messages`, JSON.stringify(message));
}
```

This is the same Pub/Sub pattern as in the Message Queues article. Redis Pub/Sub fits small and medium scale: low latency, simple to run. At large scale teams use Kafka or NATS (a lightweight open-source messaging system), which add persistence. If a consumer is briefly disconnected, a Redis Pub/Sub message is lost forever; with Kafka it is not.

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

Without this registry, a server would have to publish to **every** instance "just in case". That works at small scale, but it does not scale to thousands of rooms.

## Presence (online/offline) — TTL instead of explicit disconnect

```txt
Problem: a WebSocket connection can die "silently"
(network loss, laptop closed) without an explicit close event —
the server doesn't always learn that the client disconnected
```

Solution — a heartbeat plus a TTL in Redis. TTL means time to live: an expiry set on a key, after which Redis deletes the key itself.

```ts
// node-redis (the `redis` package) takes the options as an object:
// `{ EX: 60 }`. The other popular client, ioredis, takes the same
// thing as extra arguments instead: `'EX', 60`.
import { createClient } from 'redis';

const redis = createClient();
await redis.connect();

// Client sends a heartbeat every 30 seconds
// Server refreshes the TTL on each heartbeat
async function touchPresence(userId: string): Promise<void> {
  await redis.set(`presence:user:${userId}`, 'online', { EX: 60 }); // 60s TTL
}

// If no heartbeat arrives within 60 seconds, the key expires on its own,
// presence:user:123 stops existing → the user is "offline"
// (no need for an explicit disconnect handler)
```

The TTL approach is more reliable than "handle onDisconnect". The disconnect event may never fire when the network fails abruptly. The TTL expires anyway, whether or not the server was told about the disconnect.

## Delivery Guarantees in chat — offline delivery

WebSocket delivers a message only if the recipient is **currently online**. For offline users, you need a separate path:

```txt
1. Message Service always writes the message to the database
   first — that is the source of truth
2. Then delivery via WebSocket is attempted (if the user is online)
3. If the user is offline:
   - the message stays in the database with status "unread"
   - (optionally) a push notification via APNs/FCM
4. On the next connection, the client requests
   "all messages since last_seen_message_id" — catching up on what was missed
```

APNs and FCM in step 3 are the two mobile push services: Apple Push Notification service and Firebase Cloud Messaging.

Senior nuance: WebSocket is a **transport for real-time delivery**, not a source of truth or a delivery guarantee. Any reliable realtime system has a regular persist-then-notify model underneath. WebSocket is just the fastest of the notify paths.

## Load Balancing for WebSocket

```txt
Round Robin for new connections is fine — the server choice
happens once, at connection time.

After that, the connection lives on that server until it's dropped.
This is NOT "sticky session" in the HTTP-cookie sense — it's simply
a physical property of the TCP connection: it's held by one server
by definition, until closed.
```

TCP in that diagram is Transmission Control Protocol — the transport that carries the connection.

The main consequence for capacity planning: when a server restarts or deploys, **all** WebSocket connections on it drop at the same time. Clients need reconnect logic with backoff. Graceful shutdown should signal clients to reconnect before the server fully goes away, rather than just dropping the connection.

## Common interview mistakes

- **Not mentioning that the connection is "stuck" on a specific server.** This is the central scaling challenge for WebSocket. It is exactly what the interviewer wants to hear.

- **Proposing sticky sessions as the WebSocket scaling solution.** That does not solve cross-server delivery. It only describes how the TCP connection already works. The real problem is cross-server delivery via Pub/Sub.

- **Ignoring SSE.** For one-way updates such as notifications and live feeds, proposing WebSocket as the only option, without mentioning the much simpler SSE.

- **Treating WebSocket as a reliable transport.** Not explaining persist-then-notify and offline delivery. WebSocket by itself guarantees nothing.

- **Presence via an explicit disconnect handler without TTL.** Not accounting for connections that "die silently" with no disconnect event.

- **Not mentioning a connection registry for room-based broadcast.** Trying to "broadcast to every server just in case" instead of targeted delivery via a Redis Set used as a registry.

- **Not discussing client reconnect logic.** When a server deploys or restarts, all its connections drop at once. Without backoff-based reconnects, thousands of clients reconnect at the same moment — a thundering herd at the connection level.
