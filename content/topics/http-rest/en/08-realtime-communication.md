<!-- verified: 2026-06-23, corrections: 0 -->
# Real-Time Communication

## Four Approaches

When the client needs to receive updates without making an explicit request, there are four mechanisms: polling, long polling, SSE, and WebSockets. They look similar on the surface but work fundamentally differently. We'll cover each individually — then compare.

---

## Polling (Short Polling)

The simplest approach: the client periodically asks "is there anything new?"

### How It Works

```txt
Time →

Client: [GET /api/updates] [GET /api/updates] [GET /api/updates] [GET /api/updates]
           ↓                   ↓                  ↓                  ↓
Server: [200: empty]       [200: empty]        [200: data!]       [200: empty]

                          ↑ 5-second interval ↑
```

### Implementation

```typescript
// Client:
function startPolling(intervalMs: number = 5000) {
  const poll = async () => {
    const response = await fetch("/api/notifications?since=" + lastSeenId);
    const { items, lastId } = await response.json();

    if (items.length > 0) {
      handleNewItems(items);
      lastSeenId = lastId;
    }
  };

  const timerId = setInterval(poll, intervalMs);
  return () => clearInterval(timerId); // cleanup
}

// Server (Express):
app.get("/api/notifications", async (req, res) => {
  const since = Number(req.query.since) || 0;
  const items = await db.notifications.findAll({
    where: { id: { [Op.gt]: since }, userId: req.user.id },
    order: [["id", "ASC"]],
    limit: 50,
  });

  res.json({
    items,
    lastId: items.at(-1)?.id ?? since,
  });
});
```

### Honest Assessment of Polling

```txt
Pros:
  ✅ Trivial to implement
  ✅ Works everywhere: any browser, any proxy, any server
  ✅ Stateless: the server has no concept of a "connection"
  ✅ Easy to debug (ordinary HTTP requests)
  ✅ Trivially scales horizontally

Cons:
  ❌ Latency = poll interval (5s interval = up to 5s delay)
  ❌ Empty requests: 95% return "nothing new"
  ❌ Load is proportional to clients × frequency:
     1000 clients × once per 5s = 200 req/s constantly
```

**When to use:**
- Infrequent updates (once a minute or less) — stats dashboards
- Progress of a long operation (file import, report generation)
- Simplicity matters more than efficiency (prototype, internal tool)
- Infrastructure can't support persistent connections (old proxies)

---

## Long Polling

An improvement on polling: the server holds the request open until data arrives or a timeout occurs.

### How It Works

```txt
Time →

Client: [GET /api/updates] ──────────── hold ──────────── [data!] [GET /api/updates] ──── hold ──
Server:                    waiting for data...              ↑       waiting for data...
                                                      data arrived
                                                      → respond → client reconnects immediately
```

### Implementation

```typescript
// Server (Express) — hold the request open:
const waitingClients = new Map<string, express.Response>();

app.get("/api/long-poll", async (req, res) => {
  const userId = req.user.id;

  // Check if there's already pending data:
  const pending = await db.notifications.findPending(userId);
  if (pending.length > 0) {
    return res.json({ items: pending });
  }

  // Nothing yet — register this client as waiting:
  res.setTimeout(30_000, () => {
    waitingClients.delete(userId);
    res.json({ items: [] }); // timeout → empty response
  });

  waitingClients.set(userId, res);

  req.on("close", () => {
    waitingClients.delete(userId);
  });
});

// When a new notification arrives:
async function notifyUser(userId: string, notification: Notification) {
  await db.notifications.save(notification);

  const waitingRes = waitingClients.get(userId);
  if (waitingRes) {
    waitingClients.delete(userId);
    waitingRes.json({ items: [notification] });
  }
}

// Client:
async function longPoll() {
  while (true) {
    try {
      const response = await fetch("/api/long-poll", {
        signal: AbortSignal.timeout(35_000), // slightly longer than server timeout
      });
      const { items } = await response.json();

      if (items.length > 0) handleNewItems(items);
    } catch (err) {
      if (err instanceof DOMException && err.name === "TimeoutError") continue;
      await sleep(2000); // pause before reconnecting on error
    }
  }
}
```

### Honest Assessment of Long Polling

```txt
Pros:
  ✅ Near-real-time latency when data is available (tens of ms)
  ✅ Fewer empty requests than regular polling
  ✅ Works through all proxies and firewalls (plain HTTP)
  ✅ Stateless between sessions (each request is independent)

Cons:
  ❌ Server complexity: must manage open connections
  ❌ Every response requires a new request (reconnect overhead)
  ❌ Hard to scale: each instance holds its own waitingClients in memory
     → needs shared pub/sub (Redis) to notify the right instance
  ❌ Holds a thread/worker for the entire wait period (without async)
```

**When to use:**
- Low latency needed but SSE/WebSocket unavailable (legacy clients)
- Historically: Comet, XMPP clients, old WhatsApp Web
- Today: almost always better to use SSE instead of long polling

---

## Server-Sent Events (SSE)

SSE is a **unidirectional persistent HTTP stream** from server to client. The browser opens a connection once; the server sends events for as long as needed.

### How It Works

```txt
Client: GET /api/events HTTP/1.1
        Accept: text/event-stream

Server: HTTP/1.1 200 OK
        Content-Type: text/event-stream
        Cache-Control: no-cache
        Connection: keep-alive

        data: {"type":"message","text":"Hello"}\n\n

        event: notification\n
        data: {"id":42,"text":"New order"}\n
        id: 42\n\n

        data: keep-alive\n\n

        event: notification\n
        data: {"id":43,"text":"Order shipped"}\n
        id: 43\n\n
        ↑ connection stays open; server sends events as they occur
```

### SSE Event Format

```txt
Each event is a set of lines terminated by a blank line (\n\n):

data: text or JSON                    ← required
event: event-name                     ← optional (default: "message")
id: 42                                ← optional, for Last-Event-ID
retry: 3000                           ← optional, ms before reconnect

Examples:

Simple event:
  data: Hello world\n\n

JSON data:
  data: {"userId":42,"action":"login"}\n\n

Multi-line data (multiple data: fields):
  data: first line\n
  data: second line\n\n

Named event:
  event: orderUpdate\n
  data: {"orderId":100,"status":"shipped"}\n
  id: 55\n\n
```

### EventSource API on the Client

```typescript
const eventSource = new EventSource("/api/events", {
  withCredentials: true, // send cookies
});

// Default event (event: message or no event: field):
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("message:", data);
};

// Named event:
eventSource.addEventListener("orderUpdate", (event) => {
  const order = JSON.parse(event.data);
  updateOrderUI(order);
});

// Errors and reconnection:
eventSource.onerror = (err) => {
  console.error("SSE error:", err);
  // Browser reconnects automatically!
  // If id: was set — sends Last-Event-ID header on reconnect
};

// Close:
eventSource.close();
```

**Automatic reconnection** is a built-in SSE feature. The browser reconnects on disconnect (after `retry` ms, default 3000). On reconnect it sends `Last-Event-ID`, and the server can replay missed events.

### SSE Server Implementation (Express)

```typescript
class SSEManager {
  private connections = new Map<string, express.Response[]>();

  add(userId: string, res: express.Response) {
    const existing = this.connections.get(userId) ?? [];
    this.connections.set(userId, [...existing, res]);
  }

  remove(userId: string, res: express.Response) {
    const remaining = (this.connections.get(userId) ?? []).filter(r => r !== res);
    if (remaining.length === 0) {
      this.connections.delete(userId);
    } else {
      this.connections.set(userId, remaining);
    }
  }

  send(userId: string, event: string, data: unknown, id?: number) {
    const conns = this.connections.get(userId) ?? [];
    const chunk = [
      `event: ${event}`,
      `data: ${JSON.stringify(data)}`,
      id !== undefined ? `id: ${id}` : "",
      "",
      "",
    ].filter(Boolean).join("\n") + "\n";

    for (const res of conns) {
      res.write(chunk);
    }
  }
}

const sseManager = new SSEManager();

app.get("/api/events", requireAuth, async (req, res) => {
  res.set({
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no", // disable nginx buffering
  });

  res.write("retry: 3000\n\n");

  const userId = req.user.id;
  sseManager.add(userId, res);

  // Keepalive every 30s (proxies close idle connections):
  const keepAlive = setInterval(() => {
    res.write(": keepalive\n\n"); // lines starting with : are comments, ignored by client
  }, 30_000);

  req.on("close", () => {
    clearInterval(keepAlive);
    sseManager.remove(userId, res);
  });
});

// Send events from business logic:
async function onNewNotification(notification: Notification) {
  await db.notifications.save(notification);
  sseManager.send(notification.userId, "notification", notification, notification.id);
}
```

### SSE over HTTP/2

SSE works excellently with HTTP/2: each SSE connection is one HTTP/2 stream. In HTTP/1.1, the browser is limited to 6 connections per domain (and SSE occupies one of them). In HTTP/2, streams are unlimited — you can open 100 SSE connections without issue.

### Honest Assessment of SSE

```txt
Pros:
  ✅ Simple: plain HTTP, works through any proxy
  ✅ Automatic reconnect with Last-Event-ID — built into the browser
  ✅ Named events — built into the protocol
  ✅ No library needed: EventSource supported in all modern browsers
  ✅ HTTP/2-friendly: many SSE streams share one connection
  ✅ Relatively easy to scale (only needs pub/sub for multi-instance)

Cons:
  ❌ Server-to-client only (unidirectional)
  ❌ Text only (no binary protocol)
  ❌ EventSource doesn't support custom headers (can't send Bearer token)
     → workarounds: token in query param or cookie
  ❌ In HTTP/1.1: each SSE occupies one of 6 allowed connections
```

---

## WebSockets

WebSockets are a **full-duplex persistent connection** over TCP (RFC 6455). The client and server can send messages to each other at any time.

### The Upgrade Handshake

A WebSocket connection starts as an HTTP request, then "upgrades":

```http
GET /ws HTTP/1.1
Host: api.example.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13
Sec-WebSocket-Protocol: chat, superchat

─────────────────────────────────────────
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
Sec-WebSocket-Protocol: chat
```

After 101, the connection switches to the WebSocket protocol. The TCP connection stays open; HTTP is no longer used.

`Sec-WebSocket-Accept` = base64(SHA1(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11")) — protects against accidental HTTP servers accepting WS requests.

### WebSocket Frames

```txt
WebSocket frame (simplified):
  [FIN][RSV][Opcode 4 bits][Mask 1 bit][Payload Length][Masking Key][Payload]

Opcodes:
  0x0 — continuation frame
  0x1 — text frame (UTF-8)
  0x2 — binary frame
  0x8 — close
  0x9 — ping
  0xA — pong

Masking: all client frames are masked (protection against proxy cache poisoning)
         server frames are not masked
```

### WebSocket API on the Client

```typescript
const ws = new WebSocket("wss://api.example.com/ws");

ws.onopen = () => {
  console.log("Connected");
  // Authenticate after opening:
  ws.send(JSON.stringify({ type: "auth", token: getAccessToken() }));
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data as string);
  handleMessage(message);
};

ws.onerror = (err) => {
  console.error("WebSocket error:", err);
};

ws.onclose = (event) => {
  console.log("Closed:", event.code, event.reason);
  // Reconnection is NOT automatic! Must implement yourself:
  setTimeout(reconnect, 3000);
};

// Client sending:
ws.send(JSON.stringify({ type: "chat", text: "Hello!" }));

// Binary data:
ws.send(new Uint8Array([1, 2, 3, 4]));
ws.binaryType = "arraybuffer"; // or "blob"

// Closing:
ws.close(1000, "Normal closure");
```

### WebSocket Server Implementation

```typescript
import { WebSocketServer, WebSocket } from "ws";
import http from "http";

const server = http.createServer(app);
const wss = new WebSocketServer({ server });

interface AuthenticatedWebSocket extends WebSocket {
  userId?: string;
  isAlive: boolean;
}

const connections = new Map<string, Set<AuthenticatedWebSocket>>();

wss.on("connection", (ws: AuthenticatedWebSocket) => {
  ws.isAlive = true;

  ws.on("pong", () => { ws.isAlive = true; });

  ws.on("message", (data) => {
    try {
      const message = JSON.parse(data.toString());
      handleMessage(ws, message);
    } catch {
      ws.send(JSON.stringify({ type: "error", message: "Invalid JSON" }));
    }
  });

  ws.on("close", () => {
    if (ws.userId) connections.get(ws.userId)?.delete(ws);
  });

  ws.on("error", (err) => {
    console.error("WebSocket error:", err);
  });
});

function handleMessage(ws: AuthenticatedWebSocket, message: Record<string, unknown>) {
  if (message.type === "auth") {
    const userId = verifyToken(message.token as string);
    if (!userId) {
      ws.close(1008, "Unauthorized");
      return;
    }
    ws.userId = userId;

    const userConns = connections.get(userId) ?? new Set();
    userConns.add(ws);
    connections.set(userId, userConns);

    ws.send(JSON.stringify({ type: "auth_ok" }));
    return;
  }

  if (!ws.userId) {
    ws.close(1008, "Not authenticated");
    return;
  }

  if (message.type === "chat") {
    broadcastToRoom(message.roomId as string, {
      type: "chat",
      from: ws.userId,
      text: message.text,
    });
  }
}

function sendToUser(userId: string, data: unknown) {
  const userConns = connections.get(userId);
  if (!userConns) return;

  const payload = JSON.stringify(data);
  for (const conn of userConns) {
    if (conn.readyState === WebSocket.OPEN) conn.send(payload);
  }
}

// Keepalive: ping every 30s, terminate dead connections:
const pingInterval = setInterval(() => {
  wss.clients.forEach((ws) => {
    const aws = ws as AuthenticatedWebSocket;
    if (!aws.isAlive) { aws.terminate(); return; }
    aws.isAlive = false;
    aws.ping();
  });
}, 30_000);

wss.on("close", () => clearInterval(pingInterval));
```

### Scaling WebSockets

Problem: a client on instance A wants to send a message to a user connected to instance B.

```txt
Solution: Redis Pub/Sub (or another pub/sub)

Client A → WS Instance 1 → publish("user:42", message) → Redis
                                                            ↓
                                                   subscribe("user:42")
                                                            ↓
                                                   WS Instance 2 → Client B
```

```typescript
import { createClient } from "redis";

const publisher = createClient({ url: process.env.REDIS_URL });
const subscriber = publisher.duplicate();

await Promise.all([publisher.connect(), subscriber.connect()]);

async function broadcastToUser(targetUserId: string, data: unknown) {
  sendToUser(targetUserId, data); // local first
  await publisher.publish(`user:${targetUserId}`, JSON.stringify(data));
}

await subscriber.subscribe("user:*", (message, channel) => {
  const userId = channel.replace("user:", "");
  sendToUser(userId, JSON.parse(message));
});
```

### Honest Assessment of WebSockets

```txt
Pros:
  ✅ Full duplex: client and server send messages independently
  ✅ Low per-message overhead after handshake (no HTTP headers)
  ✅ Binary data support (ArrayBuffer, Blob)
  ✅ No restrictions on message count or direction
  ✅ Built-in ping/pong for keepalive

Cons:
  ❌ Stateful: each instance tracks its own clients → harder to scale
  ❌ No automatic reconnection (unlike SSE) — must implement yourself
  ❌ Proxies and firewalls sometimes close idle WS connections
  ❌ Authentication is harder: no HTTP headers after the handshake
  ❌ Harder to debug: not visible as regular requests in DevTools Network tab
  ❌ ws:// is unencrypted; wss:// is mandatory in production
```

---

## Comparison and Decision Guide

```txt
┌──────────────────────┬───────────┬────────────┬───────────┬─────────────┐
│                      │ Polling   │ Long Poll  │ SSE       │ WebSocket   │
├──────────────────────┼───────────┼────────────┼───────────┼─────────────┤
│ Direction            │ pull      │ pull       │ push S→C  │ push S↔C    │
│ Latency              │ = interval│ ~ms        │ ~ms       │ ~ms         │
│ Empty requests       │ many      │ few        │ none      │ none        │
│ Auto-reconnect       │ client    │ client     │ browser ✅│ ❌ manual   │
│ Proxy / firewall     │ ✅ always  │ ✅ always  │ ✅ always │ ⚠️ sometimes│
│ Binary data          │ ❌        │ ❌         │ ❌        │ ✅          │
│ Scaling              │ ✅ easy   │ ⚠️ Redis   │ ⚠️ Redis  │ ❌ complex  │
│ Implementation cost  │ ⭐        │ ⭐⭐        │ ⭐⭐       │ ⭐⭐⭐⭐     │
│ HTTP/2 compatible    │ ✅        │ ✅         │ ✅✅       │ ❌ (own protocol)│
└──────────────────────┴───────────┴────────────┴───────────┴─────────────┘
```

### Practical Decision Guide

```txt
Start with the question: does the client need to push to the server in real time?

NO (server → client only):
  Use SSE.
  Examples: notifications, news feed, task progress, live dashboard,
            LLM response streaming, order status updates.

YES (client ↔ server, full duplex):
  Use WebSockets.
  Examples: chat, collaborative editing, online games,
            trading terminals, collaborative whiteboards.

No persistent connection at all:
  Infrequent updates (once a minute): polling.
  Low latency needed but SSE unavailable: long polling.

Not sure? Start with SSE or polling.
WebSockets are justified only when you genuinely need
bidirectional real-time push from the client.
The scaling and implementation complexity of WebSockets
is significantly higher than SSE.
```

### Common Real-World Cases

```txt
Notifications (GitHub, Jira, Slack unread count):
  → SSE (server pushes, client doesn't respond in real time)

ChatGPT / Claude response streaming:
  → SSE (server streams tokens, client only reads)
  Implementation: stream.write(`data: ${token}\n\n`)

File upload / import progress:
  → SSE or polling (depending on update frequency)

Live dashboard (metrics, analytics):
  → SSE (server-pushed updates every N seconds)

Chat application (Slack, WhatsApp):
  → WebSockets (client sends messages + receives them)

Collaborative editor (Google Docs, Figma):
  → WebSockets (OT/CRDT + continuous bidirectional change stream)

Real-time online game:
  → WebSockets or UDP (for browsers: WebRTC DataChannel)

Trading terminal (quotes + orders):
  → WebSockets (receive quotes + send orders)
```

---

## WebTransport (the future)

A new W3C/IETF standard over HTTP/3 (QUIC), combining WebSocket benefits with QUIC's transport improvements:

```txt
WebTransport advantages over WebSockets:
  - Multiple independent streams in one connection
  - Unreliable datagrams (like UDP — for games, video, where speed > reliability)
  - 0-RTT connection setup (QUIC)
  - Packet loss on one stream doesn't block others

Status (2024): Chrome supports it, Firefox in development.
Too early to use in production.
```

---

## Common Interview Traps

- **"WebSockets are better than SSE for real-time"** — depends on the use case. If you only need server-to-client push (notifications, feeds, streaming), SSE is simpler and sufficient. WebSockets add significant scaling complexity in exchange for a feature that's often not needed.

- **"SSE is an outdated approach"** — no. SSE is actively used. OpenAI streams ChatGPT responses over SSE. GitHub streams live updates over SSE. It's a modern, well-supported standard.

- **"WebSockets don't work over HTTPS"** — they do. `ws://` is unencrypted (like `http://`), `wss://` is encrypted (like `https://`). Always use `wss://` in production.

- **"Polling is an antipattern — never use it"** — polling is a perfectly valid choice for infrequent updates and simple scenarios. A stats dashboard that updates once a minute needs no WebSocket complexity.

- **"SSE reconnects automatically — so it's completely reliable"** — auto-reconnect exists, but you must correctly replay missed events on reconnect. This requires `id:` on events and handling `Last-Event-ID` on the server. Without it, events are lost during brief disconnects.

- **"WebSocket connection is persistent — why do we need ping/pong?"** — proxies and firewalls close idle TCP connections (typically after 60–120s). Without keepalive (ping/pong), the connection silently dies. The client only discovers this when it tries to send the next message.

- **"Long polling = SSE = WebSocket in terms of server load"** — fundamentally different. Long polling: N open HTTP requests + reconnect after each event. SSE: N persistent HTTP streams (less overhead). WebSocket: N persistent TCP connections with minimal framing. With 10,000 clients the difference is substantial.
