<!-- verified: 2026-06-23, corrections: 0 -->
# HTTP/2 and HTTP/3

## Why HTTP/2 Was Needed

HTTP/1.1 was designed in 1997. The web back then was text pages with a handful of images. A modern page is 100+ resources: JS bundles, CSS, fonts, images, API calls. HTTP/1.1 was never built for that.

### Problems with HTTP/1.1

**Head-of-line (HoL) blocking**

```txt
HTTP/1.1 — one connection, one request at a time:

Client: [GET /main.js] ──────────────────────── [GET /style.css]
Server:               [..response main.js..]    [..response style.css..]

If main.js is large — style.css waits, even if it's already ready.
This is head-of-line blocking.
```

Browsers worked around this by opening **6 parallel TCP connections** per domain. But each connection means a separate TCP + TLS handshake.

**Uncompressed text headers**

Every request carries full headers:
```http
Host: api.example.com
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36...
Accept: application/json
Accept-Language: en-US,en;q=0.9,ru;q=0.8
Accept-Encoding: gzip, deflate, br
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Cookie: sessionId=abc123; _ga=GA1.2.xxx; _gid=GA1.2.yyy
```

That's 500–2000 bytes per request, and 95%+ of the headers are identical across requests.

**No prioritization**

The browser had no way to tell the server "CSS is more important than images — send it first."

---

## HTTP/2: Binary, Multiplexed

HTTP/2 (2015, RFC 7540) solves these problems while preserving HTTP semantics — same methods, status codes, and headers. Only the **transport** changes.

### Binary Framing

HTTP/1.1 is a text protocol. HTTP/2 is binary:

```txt
HTTP/1.1:
  GET /users HTTP/1.1\r\n
  Host: api.example.com\r\n
  \r\n

HTTP/2 (simplified):
  [Length: 3 bytes][Type: 1 byte][Flags: 1 byte][Stream ID: 4 bytes][Payload: N bytes]
       ↑ fixed 9-byte frame header
```

Frame types:
```txt
HEADERS       — request/response headers
DATA          — request/response body
SETTINGS      — connection configuration
PING          — keepalive
GOAWAY        — close the connection
RST_STREAM    — reset a specific stream
WINDOW_UPDATE — flow control
PUSH_PROMISE  — server push announcement
```

### Multiplexing (the key feature)

Multiple requests concurrently over a **single TCP connection** via **streams**:

```txt
HTTP/1.1 (6 connections):
  TCP conn 1: [GET /main.js      ──────────────────]
  TCP conn 2: [GET /vendor.js    ──────────────────]
  TCP conn 3: [GET /style.css    ──────]
  TCP conn 4: [GET /logo.png     ───]
  TCP conn 5: [GET /api/user     ──]
  TCP conn 6: [GET /api/config   ────]

HTTP/2 (1 connection, N streams):
  TCP conn:
    Stream 1:  [GET /main.js   ] ──────[DATA]──────────────────
    Stream 3:  [GET /vendor.js ] ──────[DATA]──────────────────
    Stream 5:  [GET /style.css ] ────[DATA]──────
    Stream 7:  [GET /logo.png  ] ───[DATA]
    Stream 9:  [GET /api/user  ] ──[DATA]
    Stream 11: [GET /api/config] ────[DATA]
               ↑ all interleaved as frames inside one TCP stream
```

Streams are identified by **odd** numbers (client-initiated) or **even** numbers (server push). They're independent — one slow stream does not block the others.

### HPACK — Header Compression

HTTP/2 compresses headers using HPACK (RFC 7541):

```txt
Static table (61 entries):
  :method = GET          → index 2
  :status = 200          → index 8
  content-type = application/json → + name with literal value

Dynamic table:
  First request:  Authorization: Bearer eyJ... → added to the table
  Second request: Authorization: Bearer eyJ... → just an index (1–4 bytes instead of 500+)

Result: headers compressed 85–95% starting from the second request.
```

### Stream Prioritization

The client can specify a stream priority (0–256) and dependency between streams:

```txt
Priority tree:
  Stream 1 (CSS, weight 220)
    └── Stream 3 (JS, weight 180)
          └── Stream 5 (image, weight 60)

Server delivers: CSS → JS → image.
```

In practice, prioritization is poorly implemented across most servers and browsers, but it's conceptually important to understand.

### Server Push (and Why It Failed)

Server Push: the server sends a resource to the client before it was requested.

```txt
Client: GET /index.html

Server: [HTML response]
        [PUSH_PROMISE: /style.css]  ← server says "I'll push this"
        [DATA for /style.css]       ← sends without a request
        [PUSH_PROMISE: /main.js]
        [DATA for /main.js]

Client receives CSS and JS together with HTML — no additional requests.
```

Why it failed:
```txt
1. Browsers cache resources. The server doesn't know what's already in
   the client's cache. Pushing cached resources wastes bandwidth.

2. Hard to implement correctly: how do you decide what to push?

3. 103 Early Hints solves the same problem more simply:
   HTTP/1.1 103 Early Hints
   Link: </style.css>; rel=preload; as=style

4. Chrome removed Server Push support in 2022.
   HTTP/3 dropped it from the spec entirely.
```

### TLS in HTTP/2

Technically HTTP/2 supports cleartext (h2c). In practice, all browsers require TLS for HTTP/2. So in practice, HTTP/2 = HTTPS.

---

## HTTP/2 in Practice (Node.js)

Express doesn't natively support HTTP/2 (it's tied to Node.js's `http` module). Options:

**Option 1 — Nginx/Cloudflare as a TLS terminator (recommended)**

```txt
Browser ←── HTTP/2 ──→ Nginx ←── HTTP/1.1 ──→ Node.js

Nginx handles HTTP/2 → proxies to Node.js over HTTP/1.1.
Node.js is unaware of HTTP/2; everything works.
```

```nginx
server {
    listen 443 ssl http2;
    ssl_certificate /etc/ssl/cert.pem;
    ssl_certificate_key /etc/ssl/key.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
    }
}
```

**Option 2 — Native Node.js http2 module**

```typescript
import http2 from "http2";
import fs from "fs";

const server = http2.createSecureServer({
  key: fs.readFileSync("key.pem"),
  cert: fs.readFileSync("cert.pem"),
});

server.on("stream", (stream, headers) => {
  const method = headers[":method"];
  const path = headers[":path"];

  stream.respond({
    "content-type": "application/json",
    ":status": 200,
  });

  stream.end(JSON.stringify({ method, path }));
});

server.listen(3000);
```

**Option 3 — Fastify** (native HTTP/2 support):

```typescript
import Fastify from "fastify";
import fs from "fs";

const fastify = Fastify({
  http2: true,
  https: {
    key: fs.readFileSync("key.pem"),
    cert: fs.readFileSync("cert.pem"),
  },
});

fastify.get("/api/users", async () => {
  return { users: [] };
});

await fastify.listen({ port: 3000 });
```

---

## HTTP/3: QUIC Instead of TCP

HTTP/3 (2022, RFC 9114) is the next step. The problem HTTP/2 discovered was that it fixed HoL blocking at the HTTP layer but not at the TCP layer.

### HoL Blocking in HTTP/2

```txt
HTTP/2 over TCP:

  Stream 1, 3, 5 frames are interleaved in one TCP byte stream:
  [S1][S3][S5][S1][S3][S5][S1]...

  If a TCP packet in the middle is lost — ALL streams wait for
  its retransmission. TCP knows nothing about HTTP/2 streams.
  It guarantees byte order, full stop.

  Result: losing 1 packet stalls all 50 parallel streams.
  On mobile networks with ~2% packet loss — noticeably painful.
```

### QUIC — UDP + Reliability

QUIC (Quick UDP Internet Connections) is a new transport protocol over UDP, developed by Google and standardized by IETF:

```txt
HTTP/1.1, HTTP/2:
┌──────┐
│ HTTP │
├──────┤
│ TLS  │
├──────┤
│ TCP  │  ← reliability, ordering
├──────┤
│ IP   │
└──────┘

HTTP/3:
┌──────────────┐
│ HTTP/3       │
├──────────────┤
│ QUIC         │  ← reliability + TLS + flow control
│ (UDP-based)  │
├──────────────┤
│ IP           │
└──────────────┘
```

QUIC implements reliable delivery, but **independently per stream**. A lost packet for one stream doesn't block the others.

### 0-RTT Connection Setup

HTTP/1.1 + TLS 1.2: 3 RTT before the first data byte:
```txt
TCP:  SYN → SYN-ACK → ACK              (1 RTT)
TLS:  ClientHello → ServerHello → ...  (1–2 RTT)
HTTP: GET → response                   (1 RTT)
                                 Total: 3–4 RTT
```

HTTP/3 + QUIC + TLS 1.3: 1 RTT, on reconnection — 0-RTT:
```txt
First connection:
  QUIC Initial (includes TLS ClientHello) → QUIC Handshake (TLS)
  HTTP GET → response
                                       Total: 1 RTT

Reconnection (0-RTT):
  QUIC Initial + TLS + HTTP GET → response
                                       Total: 0 RTT (!)
```

0-RTT works because QUIC remembers the connection parameters from the previous session.

### Connection Migration

```txt
HTTP/1.1 / HTTP/2 (TCP):
  IP change (WiFi → 4G) = TCP connection broken = reconnect.
  In-flight requests are lost.

HTTP/3 (QUIC):
  Connections are identified by a Connection ID, not IP:port.
  WiFi → 4G → Connection ID is preserved → connection continues.
  A file download is not interrupted when switching networks.
```

This is critical for mobile users and IoT devices.

---

## HTTP Version Comparison

```txt
┌───────────────────┬──────────────┬──────────────┬──────────────┐
│                   │ HTTP/1.1     │ HTTP/2       │ HTTP/3       │
├───────────────────┼──────────────┼──────────────┼──────────────┤
│ Transport         │ TCP          │ TCP          │ UDP (QUIC)   │
│ TLS               │ Optional     │ De facto req │ Required     │
│ Multiplexing      │ ❌ 6 conn.   │ ✅ 1 conn.   │ ✅ 1 conn.   │
│ HoL (HTTP layer)  │ ❌ Yes       │ ✅ No        │ ✅ No        │
│ HoL (TCP layer)   │ ❌ Yes       │ ❌ Yes       │ ✅ No (QUIC) │
│ Header compression│ ❌ No        │ ✅ HPACK     │ ✅ QPACK     │
│ 0-RTT             │ ❌ 3+ RTT    │ ❌ 2+ RTT    │ ✅ 0–1 RTT   │
│ Connection migr.  │ ❌ No        │ ❌ No        │ ✅ Yes       │
│ Server Push       │ ❌ No        │ ✅ Yes*      │ ❌ Removed   │
│ Browser support   │ 100%         │ ~98%         │ ~85%         │
└───────────────────┴──────────────┴──────────────┴──────────────┘
* Server Push removed from Chrome; poorly implemented almost everywhere
```

---

## What Changes for the Developer

### What Doesn't Change

- HTTP methods (GET, POST, PUT, DELETE…)
- Status codes (200, 404, 500…)
- Headers (Cache-Control, Authorization, Content-Type…)
- REST API architecture

Fetch API, axios, node-fetch all work with HTTP/2 and HTTP/3 transparently. Your code doesn't change.

### What Changes: Optimization Approach

```txt
HTTP/1.1 optimizations that are HARMFUL in HTTP/2:
  ❌ Domain sharding (multiple CDN domains to bypass 6-connection limit)
  ❌ CSS/JS sprites (combining assets into one file to reduce requests)
  ❌ Inline CSS (embedding styles to save a request)

HTTP/2 optimizations:
  ✅ Many small files ≈ one large file (multiplexing makes them equally efficient)
  ✅ Granular caching (small files cache independently — changing one
     doesn't invalidate the whole bundle)
  ✅ 103 Early Hints instead of Server Push
```

### Detecting HTTP Version

```typescript
// In the browser: via Performance API
const entries = performance.getEntriesByType("resource");
entries.forEach(entry => {
  console.log(entry.name, (entry as PerformanceResourceTiming).nextHopProtocol);
  // "h2" = HTTP/2, "h3" = HTTP/3, "http/1.1" = HTTP/1.1
});
```

### Nginx Configuration for HTTP/3

```nginx
server {
    listen 443 ssl;
    listen 443 quic reuseport;       # HTTP/3
    http2 on;                         # HTTP/2

    ssl_certificate cert.pem;
    ssl_certificate_key key.pem;
    ssl_protocols TLSv1.3;            # QUIC requires TLS 1.3

    add_header Alt-Svc 'h3=":443"; ma=86400';  # Advertise HTTP/3 to browsers

    location / {
        proxy_pass http://localhost:3000;
    }
}
```

The `Alt-Svc` header tells the browser "I support HTTP/3 on port 443." On the next connection attempt, the browser will try QUIC.

---

## Diagram: Why HTTP/3 Is Faster on Poor Networks

```txt
HTTP/2 with 2% packet loss:

Time →
[S1 frame][S3 frame][S5 frame][S1 frame][X LOST ][S1 frame]
                                                    ↑
                              ALL streams WAIT until TCP retransmits X.
                              S3 and S5 are ready but blocked.

HTTP/3 with 2% packet loss:

Time →
[S1 frame][S3 frame][S5 frame][S1 frame][X LOST ][S1 frame]
                                          ↑
                              Only the stream that lost X waits.
                              S1 and S3 continue without delay.
```

---

## Common Interview Traps

- **"HTTP/2 is always faster"** — not always. On fast, low-loss networks, HTTP/1.1 with multiple connections can be comparable. HTTP/2 shows the most benefit on high-latency or unstable connections (mobile, CDN with >100ms RTT).

- **"HTTP/3 is on UDP — so it's unreliable"** — QUIC implements reliable delivery over UDP at the application layer (acknowledgements, retransmissions, ordering). UDP was chosen because TCP can't be changed without updating the OS on every node in the internet.

- **"HTTP/2 multiplexing fixed all HoL problems"** — no. TCP-level HoL remained. HTTP/3 fixed it through QUIC.

- **"Server Push is a great HTTP/2 feature"** — it failed in practice. Chrome removed support in 2022. Use 103 Early Hints or Resource Hints (`<link rel="preload">`) instead.

- **"Domain sharding is good for HTTP/2"** — the opposite. Domain sharding requires multiple DNS lookups and TLS handshakes. In HTTP/2 everything multiplexes over one connection — sharding only hurts.

- **"HTTPS is only needed for security"** — in the context of HTTP/2+, HTTPS is also needed for the protocol itself. Browsers don't support HTTP/2 without TLS. QUIC embeds TLS 1.3 as a mandatory part.

- **"0-RTT is completely safe"** — 0-RTT is vulnerable to replay attacks: an intercepted 0-RTT packet can be sent again. Therefore 0-RTT is only appropriate for idempotent requests (GET). Servers must protect against replay on 0-RTT POST/PUT requests.
