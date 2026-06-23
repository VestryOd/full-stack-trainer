<!-- verified: 2026-06-23, corrections: 0 -->
# HTTP/REST — Interview Questions

25–30 questions grouped by topic. Difficulty: 🟢 junior · 🟡 middle · 🔴 senior.

---

## HTTP Fundamentals

### 1. 🟢 What is HTTP and why is it stateless?

HTTP (HyperText Transfer Protocol) is an application-layer protocol over TCP/IP. Text request → text response. Stateless means every request is independent: the server holds no memory of previous requests. That's exactly why cookies, sessions, and JWTs exist — they carry state explicitly.

Statelessness is a deliberate design choice, not a limitation: it simplifies horizontal scaling (any instance handles any request), caching, and debugging.

---

### 2. 🟢 What HTTP methods do you know? What's the difference between GET and POST?

GET is safe and idempotent: reads a resource, doesn't modify server state. POST is unsafe and non-idempotent: creates a resource or performs an action.

Full picture by safety and idempotency:

```txt
Method  | Safe | Idempotent
--------|------|------------
GET     |  ✅  |    ✅
HEAD    |  ✅  |    ✅
OPTIONS |  ✅  |    ✅
PUT     |  ❌  |    ✅
DELETE  |  ❌  |    ✅
POST    |  ❌  |    ❌
PATCH   |  ❌  |  depends
```

Idempotency matters for retries: if a PUT request's TCP connection drops, you can safely retry. POST you can't — a duplicate order gets created.

---

### 3. 🟢 What do status codes 201, 204, 301, 304, 401, 403, 409, 429 mean?

- **201 Created** — resource created (POST). Usually includes a `Location` header.
- **204 No Content** — success, no body (DELETE, PUT without a return value).
- **301 Moved Permanently** — resource moved forever; browser caches the redirect.
- **304 Not Modified** — cache is current, no body (response to `If-None-Match`).
- **401 Unauthorized** — not authenticated (missing/expired token).
- **403 Forbidden** — authenticated, but no permission.
- **409 Conflict** — conflict (duplicate email on registration).
- **429 Too Many Requests** — rate limiting, usually + `Retry-After`.

Trap: 401 is named "Unauthorized" but means "Unauthenticated." A historical naming mistake in the HTTP spec.

---

### 4. 🟡 What is idempotency and why does it matter in practice?

A method is idempotent if applying it multiple times produces the same result as applying it once.

Practical importance: when a connection drops, the client doesn't know whether the request arrived. If the method is idempotent (PUT, DELETE) — safe to retry. If not (POST) — a retry creates a duplicate order or payment.

PATCH is idempotent only when the operation is absolute: `{ "status": "active" }` — yes; `{ "views": { "increment": 1 } }` — no.

This is why payment systems require an `Idempotency-Key` header on `POST /payments` — it turns a non-idempotent method into an idempotent one through server-side deduplication.

---

### 5. 🟡 What's the difference between PUT and PATCH?

PUT replaces the resource **entirely**: the client sends the full representation. Not sending a field means deleting it.

PATCH updates **partially**: only the changed fields.

```http
PUT /users/42    { "name": "Alice", "email": "new@example.com", "role": "admin" }
                  ↑ all fields required

PATCH /users/42  { "email": "new@example.com" }
                  ↑ only what's changing
```

PUT is idempotent by definition: `PUT /users/42` twice with the same data — same result.

---

## REST and API Design

### 6. 🟢 What is REST? Is a typical JSON API RESTful?

REST is an architectural style of 6 constraints (Fielding, 2000): Client-Server, Stateless, Cacheable, Uniform Interface, Layered System, Code on Demand. Not a protocol, not a standard.

Most "REST APIs" are Richardson Maturity Level 2: resources + HTTP methods. That's "REST-ish," not full REST. Full REST requires HATEOAS (Level 3) — the client follows links from responses without knowing URLs in advance. Almost nobody implements Level 3.

---

### 7. 🟡 What is HATEOAS? Why doesn't anyone implement it?

HATEOAS (Hypermedia As The Engine Of Application State) is a REST constraint: the client doesn't know URLs in advance and follows hyperlinks from server responses, just like a browser follows links on a page.

```json
{
  "id": 42,
  "_links": {
    "self":    { "href": "/users/42" },
    "orders":  { "href": "/users/42/orders" },
    "suspend": { "href": "/users/42/suspend", "method": "POST" }
  }
}
```

Nobody implements it fully because: clients still hard-code navigation logic; documentation (OpenAPI) provides the same discoverability more simply; no dominant standard (HAL, JSON:API, Siren are incompatible); building a dynamic UI from links is extremely complex.

---

### 8. 🟡 API versioning strategies. Which to choose and why?

Three approaches:

- **URL** (`/v1/users`) — most common. Easy to cache, test, and route at nginx. Downside: violates REST (URI should identify a resource, not an API version).
- **Header** (`Accept: application/vnd.api.v2+json`) — REST-correct, but tricky to cache (needs `Vary: Accept`) and less obvious to consumers.
- **Query param** (`?version=2`) — convenient as optional, but pollutes filter params.

Recommendation for most projects: `/v1` in the URL. Simpler, caches reliably, clearer to the team.

---

## Caching

### 9. 🟡 What does `Cache-Control: no-cache` mean? How does it differ from `no-store`?

A classic interview trap:

- `no-cache` — the cache **may** store the response, but must **revalidate** with the server before using it. If the server responds with 304 — the cached copy is used. Saves bandwidth, not RTT.
- `no-store` — **don't store** anything. Full request every time. For sensitive data (banking, medical records).

The distinction is critical: `no-cache` is about freshness; `no-store` is about privacy/security.

---

### 10. 🟡 What is an ETag and how do conditional requests work?

An ETag is a unique version identifier for a resource. The server includes it in the response: `ETag: "v3-abc123"`.

On the next request, the client sends `If-None-Match: "v3-abc123"`. If unchanged — the server returns `304 Not Modified` with no body. Saves bandwidth on repeated requests.

`Last-Modified` / `If-Modified-Since` is the time-based equivalent. ETag is more precise: a file can be re-saved with the same content but a new timestamp.

`If-Match` is used on PUT/PATCH for optimistic locking: "update only if version matches." On mismatch → `412 Precondition Failed`.

---

### 11. 🔴 What is `stale-while-revalidate`? When is it appropriate?

```http
Cache-Control: public, max-age=60, stale-while-revalidate=30
```

The resource is fresh for 60 seconds. For the next 30 seconds the cache serves the stale version while updating in the background. Maximum data staleness: 90 seconds.

Appropriate when perceived speed matters more than absolute freshness: news feeds, public APIs, CDN with dynamic content.

Not appropriate: banking transactions, inventory (staleness causes oversell), personalized data.

---

## CORS

### 12. 🟢 What is CORS and why does it exist?

CORS is a browser mechanism that lets a server explicitly permit cross-origin requests. Without it, the Same-Origin Policy blocks JavaScript from reading responses from other sites.

Key insight: CORS doesn't protect the server — the request physically executes. CORS controls what the browser passes to JavaScript. That's why curl has no concept of CORS — it's a browser policy, not a server one.

---

### 13. 🟡 When does the browser send a preflight OPTIONS request?

A preflight is triggered by:
- Methods: PUT, DELETE, PATCH
- Custom headers (`Authorization`, `X-Custom-Header`)
- `Content-Type: application/json` (!)
- Credentialed requests to a different origin

Implication: most API requests with JSON or an auth token trigger a preflight = double the HTTP requests. `Access-Control-Max-Age: 86400` caches the preflight response in the browser for a day.

---

### 14. 🟡 Why can't you use `Access-Control-Allow-Origin: *` with cookies?

A wildcard allows any site to read the response. Credentials (cookies) carry the logged-in user's data. Together: any site reads personal data — an obvious vulnerability.

The browser forcibly blocks the combination of `*` + `credentials: "include"`. With credentials, you must specify a concrete origin.

---

### 15. 🔴 Why is `Vary: Origin` needed? What happens without it?

When the server dynamically reflects `Access-Control-Allow-Origin` (one origin from a list), the cache must know: the same URL can return different ACAO values for different clients.

Without `Vary: Origin`: a CDN caches the response with `ACAO: https://a.com` and returns it to a client with `Origin: https://b.com`. The browser blocks it — CORS error for b.com.

With `Vary: Origin`: the cache stores separate copies per unique origin.

---

## Pagination

### 16. 🟡 Offset vs cursor pagination. When to use which?

Offset (`LIMIT N OFFSET M`): simple to implement, supports jumping to a page, has a total count. Problems: at large offsets the DB reads and discards M rows (O(n) index scan); under concurrent DML, data "drifts" (duplicates or skipped rows).

Cursor (`WHERE id < lastId LIMIT N`): stable, always O(log n), ideal for infinite scroll. Can't jump to page 42, no total count.

Rule: classic table with page navigation → offset. Infinite scroll / real-time feed / >100K rows → cursor.

---

### 17. 🔴 Why is `OFFSET 5000000` slow even with an index?

`ORDER BY created_at DESC LIMIT 20 OFFSET 5000000` — the DB walks the index and **skips** 5,000,000 rows before taking 20. That's O(n) relative to the offset, not O(log n).

Cursor-based (`WHERE created_at < lastValue ORDER BY created_at DESC LIMIT 20`) hits the index directly — O(log n) regardless of position.

On a 10M-row table, offset=5M can take seconds; cursor takes milliseconds.

---

## Authentication

### 18. 🟡 How does JWT work? What does it contain and how is it verified?

JWT = `base64url(header).base64url(payload).signature`. The header contains the algorithm (`alg: HS256`), the payload contains claims (`sub`, `exp`, `role`), the signature is an HMAC or RSA signature.

Important: the payload is **not encrypted** — anyone can read it. The signature guarantees **integrity** (nobody tampered), not **confidentiality**.

Verification: the server recomputes the signature from header + payload + secret and compares. Then checks `exp`. Without signature verification — anyone can forge a token.

---

### 19. 🟡 Access token + refresh token — why two tokens?

Access token: short TTL (15 min – 1 hour), stateless, carries user data. If compromised — small window of vulnerability.

Refresh token: long TTL (7–90 days), stored **on the server** (Redis/DB), sent only to `/auth/refresh` via an HttpOnly cookie. Server-side storage enables invalidation (logout = delete from Redis).

On logout: refresh token deleted from the server. The access token remains valid until `exp` — which is why its TTL is short.

---

### 20. 🟡 What's the difference between sessions and JWT?

Sessions: server stores state in Redis/DB. Client holds only an ID (small cookie). Instant invalidation. Requires a session store — extra RTT on every request.

JWT: state inside the token, server stores nothing (stateless). Scales horizontally without Redis. Invalidation before expiry requires a blacklist (= back to stateful).

Choose: traditional web on one domain → sessions. SPA/mobile/microservices → JWT + refresh token.

---

### 21. 🔴 What is PKCE and why is it needed in OAuth 2.0?

PKCE (Proof Key for Code Exchange) is an extension for protecting the Authorization Code Flow in public clients (SPA, mobile) where a `client_secret` cannot be stored safely.

The client generates a random `code_verifier`, sends its SHA256 hash (`code_challenge`) in the authorization request. When exchanging code → token, it sends the original `code_verifier`. The Authorization Server verifies: `SHA256(verifier) == challenge`.

If the authorization code is intercepted — without the `code_verifier` it's useless. In an SPA without PKCE, an intercepted code is directly exchangeable for tokens.

---

### 22. 🔴 Why shouldn't JWT be stored in localStorage?

localStorage is accessible to any JavaScript on the page. An XSS attack on any dependency or CDN resource → token stolen → full session compromise.

Correct approach: access token in JS memory (a variable) — lost on page reload. Refresh token in an HttpOnly cookie (JS-inaccessible; browser sends it automatically). On reload — silently get a new access token via the refresh flow.

---

## Real-Time Communication

### 23. 🟡 What's the difference between SSE and WebSockets? When to use which?

SSE is a unidirectional HTTP stream (server → client). Built-in auto-reconnect with `Last-Event-ID`. Works through any proxy. Text only.

WebSocket is a full-duplex TCP connection. Client and server send independently. Supports binary data. No auto-reconnect — must implement. Harder to scale.

Choose: if you only need server push (notifications, progress, LLM streaming) → SSE. If you need client-to-server real-time push (chat, games, collaborative editing) → WebSockets.

---

### 24. 🟡 How does SSE work? What is `Last-Event-ID`?

EventSource opens one persistent HTTP GET with `Accept: text/event-stream`. The server holds the connection open and sends events in the format:
```
event: orderUpdate\n
data: {"id":42}\n
id: 55\n\n
```

On disconnect, the browser automatically reconnects (after `retry` ms) and sends `Last-Event-ID: 55`. The server sees this and can replay events with ID > 55. Without handling `Last-Event-ID`, events are lost during brief disconnects.

---

### 25. 🔴 How do you scale a WebSocket server horizontally?

Problem: a client on instance A wants to send a message to a user connected to instance B. Instance A has no WebSocket connection for that user in memory.

Solution: Redis Pub/Sub. When a message arrives from a client → save + `publish("user:42", data)` to Redis. All instances subscribe to `user:*`. Instance B receives from Redis and sends over WebSocket.

Alternatives: Kafka (high throughput), Socket.IO with Redis adapter (batteries included), sticky sessions (breaks horizontal scaling but simpler).

---

### 26. 🔴 Compare polling, long polling, SSE, and WebSockets under 10,000 clients.

Polling (5s interval): 2,000 req/sec constantly, 95% empty. Load is predictable and independent of event frequency.

Long polling: idle → 10,000 open HTTP connections waiting. On an event → 10,000 responses + 10,000 reconnects simultaneously. Thundering herd on events.

SSE: 10,000 persistent HTTP streams. Events sent only when data exists. Minimal overhead (keepalive comment lines every 30s).

WebSocket: 10,000 persistent TCP connections. Minimal per-message overhead (no HTTP headers). Ping/pong every 30s. Most efficient per-byte at high event frequency.

---

## HTTP/2 and HTTP/3

### 27. 🔴 What is head-of-line blocking? Did HTTP/2 solve it?

HoL blocking in HTTP/1.1: one TCP connection = one request at a time. A slow response blocks subsequent ones. Browsers opened 6 connections — a partial workaround.

HTTP/2 solved HoL **at the HTTP layer**: stream multiplexing in a single TCP connection. Streams are independent at the HTTP level.

**But**: TCP-level HoL remained. A single lost TCP packet blocks all HTTP/2 streams (TCP guarantees byte ordering without knowing about streams).

HTTP/3 (QUIC over UDP) solved the TCP-level HoL too: streams are independent at the transport layer. A lost packet on one stream doesn't block others.

---

### 28. 🔴 What is the 0-RTT vulnerability in HTTP/3?

0-RTT lets the client send data together with the first connection packet — no handshake wait. This works because QUIC remembers parameters from the previous session.

Vulnerability: **replay attack**. An intercepted 0-RTT packet can be sent again. The server can't distinguish the original from a replay within the same 0-RTT window.

Protection: 0-RTT only for **idempotent** requests (GET). For POST/PUT in 0-RTT, the server needs deduplication (nonce, timestamp check). QUIC servers can respond with `RETRY` to force a 1-RTT handshake for sensitive operations.

---

### 29. 🟡 What optimization approaches change when moving from HTTP/1.1 to HTTP/2?

HTTP/1.1 optimizations that **hurt** in HTTP/2:
- Domain sharding (multiple subdomains for 6×N connections) → HTTP/2 multiplexing over one connection is better
- CSS/JS sprites (merging assets to reduce request count) → many small files ≈ one large file
- Inlined CSS/JS → gives up caching

HTTP/2 optimizations:
- Granular caching: small files cache independently
- 103 Early Hints instead of Server Push
- HTTP/2 stream prioritization for critical resources

---

### 30. 🔴 How does HMAC request signing work for APIs? Why use it?

HMAC (Hash-based Message Authentication Code) signs the entire request (method + path + timestamp + body) with a shared secret key. The server recomputes the signature and compares.

Advantages over a plain API key:
- Protection against man-in-the-middle: changing any byte of the request invalidates the signature
- Replay protection: timestamp in the signature + server checks "not older than 5 minutes"
- A captured request can't be replayed against a different endpoint

Used by: AWS SDK (`AWS4-HMAC-SHA256`), Stripe webhook verification, payment systems.

```typescript
const message = `${method}\n${path}\n${timestamp}\n${body}`;
const signature = crypto.createHmac("sha256", secret).update(message).digest("hex");
// Server: checks timestamp, recomputes signature, compares
```
