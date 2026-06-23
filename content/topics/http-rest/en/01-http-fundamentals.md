<!-- verified: 2026-06-23, corrections: 0 -->
# HTTP Fundamentals

## What HTTP Is and Why It Works the Way It Does

HTTP (HyperText Transfer Protocol) is an application-layer protocol built on top of TCP/IP. Every HTTP request is a text message sent over a TCP connection; the response is the same kind of text message back.

```txt
Protocol stack:

┌──────────────────────────────┐
│        Application           │
│  (browser, fetch, axios...)  │
├──────────────────────────────┤
│           HTTP               │  ← application layer
├──────────────────────────────┤
│           TLS                │  ← encryption (HTTPS)
├──────────────────────────────┤
│           TCP                │  ← reliable delivery
├──────────────────────────────┤
│           IP                 │  ← routing
└──────────────────────────────┘
```

HTTP is a **stateless** protocol: each request is independent. The server has no memory of previous requests. This is exactly why cookies, sessions, and JWTs exist — they carry state between requests explicitly.

## Anatomy of an HTTP Request and Response

```http
GET /api/users/42 HTTP/1.1
Host: api.example.com
Accept: application/json
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...
User-Agent: Mozilla/5.0
```

```txt
Request structure:
┌─────────────────────────────────────────┐
│  Method  Path           Protocol version │  ← request line
│  GET     /api/users/42  HTTP/1.1         │
├─────────────────────────────────────────┤
│  Host: api.example.com                  │
│  Accept: application/json               │  ← headers
│  Authorization: Bearer ...              │
├─────────────────────────────────────────┤
│  (empty line)                           │  ← separator
├─────────────────────────────────────────┤
│  { "name": "Alice" }                    │  ← body (for POST/PUT/PATCH)
└─────────────────────────────────────────┘
```

```http
HTTP/1.1 200 OK
Content-Type: application/json
Content-Length: 87
Cache-Control: no-cache

{
  "id": 42,
  "name": "Alice",
  "email": "alice@example.com"
}
```

---

## HTTP Methods: The Real Semantics

Most developers know methods superficially: "GET reads, POST creates." But the spec defines precise properties: **safety** and **idempotency**.

### Safety

A method is **safe** if it does not modify server state. A client may call a safe method any number of times without side effects.

```txt
Safe methods:   GET, HEAD, OPTIONS
Unsafe methods: POST, PUT, PATCH, DELETE
```

Important: "safe" is a semantic promise, not a technical restriction. `GET /delete-account` is technically possible but violates the spec. Browsers and intermediaries (caches, proxies) make decisions based on these promises.

### Idempotency

A method is **idempotent** if applying the same request multiple times produces the same result as applying it once.

```txt
Idempotent methods:     GET, HEAD, PUT, DELETE, OPTIONS
NOT idempotent:         POST, PATCH*

*PATCH can be idempotent if the operation is absolute, not relative.
 "Set status = active" — idempotent.
 "Increment counter by 1" — not idempotent.
```

Why idempotency matters in practice:

```txt
Scenario: client sends a PUT request, the TCP connection drops.
The client doesn't know — did the request arrive or not?

PUT (idempotent): safe to retry — result is the same.
POST (not idempotent): a retry may create a duplicate order or payment.

This is why payment systems often require an idempotency-key header on POST /payments.
```

### Methods One by One

**GET** — retrieve a resource. Safe, idempotent. No request body (technically allowed by the spec, but not supported by most servers and caches).

**POST** — create a resource or perform an action. Unsafe, not idempotent. The only method with a guarantee against automatic retry (unless an idempotency-key is used).

**PUT** — replace a resource entirely. Idempotent. The full resource representation is sent:
```http
PUT /api/users/42 HTTP/1.1
Content-Type: application/json

{ "id": 42, "name": "Alice", "email": "new@example.com", "role": "admin" }
```
Not sending a field = deleting it on the server. This is what distinguishes PUT from PATCH.

**PATCH** — partial update. Only the changed fields are sent:
```http
PATCH /api/users/42 HTTP/1.1
Content-Type: application/json

{ "email": "new@example.com" }
```
Idempotent only if the operation is absolute (not `"increment": 1`).

**DELETE** — remove a resource. Idempotent: `DELETE /users/42` twice — first call deletes, second returns 404 or 204. The end state is the same — the resource is gone.

**HEAD** — same as GET but without a response body. Used to check a resource's existence or fetch metadata (Content-Length, Last-Modified) without downloading the content.

**OPTIONS** — discover which methods and headers the server supports for a given resource. Used by browsers for CORS preflight requests (see [CORS Deep Dive]).

---

## Status Codes: What Each Range Means

```txt
1xx — Informational (rarely seen in APIs)
2xx — Success
3xx — Redirection
4xx — Client error
5xx — Server error
```

### 2xx — Success

| Code | Name | When to use |
|------|------|-------------|
| 200 | OK | Standard success for GET, PUT, PATCH |
| 201 | Created | Resource created (POST). Usually includes a `Location` header |
| 204 | No Content | Success, no body needed (DELETE, or PUT without returning a body) |
| 206 | Partial Content | Response to a Range request (partial file download) |

```http
HTTP/1.1 201 Created
Location: /api/users/43
Content-Type: application/json

{ "id": 43, "name": "Bob" }
```

### 3xx — Redirection

| Code | Name | Semantics |
|------|------|-----------|
| 301 | Moved Permanently | Resource moved forever. Browsers and SEO cache this |
| 302 | Found | Temporary redirect. Method may change to GET |
| 303 | See Other | After POST — redirect to GET (Post/Redirect/Get pattern) |
| 304 | Not Modified | Cache is fresh, no body (response to If-None-Match) |
| 307 | Temporary Redirect | Temporary, method is preserved (unlike 302) |
| 308 | Permanent Redirect | Permanent, method is preserved (unlike 301) |

The 301/302 nuance: historically browsers changed POST to GET on redirect, which didn't match the original intent. 307/308 were added to preserve the method.

### 4xx — Client Errors

| Code | When to use |
|------|-------------|
| 400 | Malformed request (invalid JSON, missing required fields) |
| 401 | Not authenticated (no/expired token) |
| 403 | Authenticated, but not authorized |
| 404 | Resource not found |
| 405 | Method not allowed (POST on /users/42) |
| 409 | Conflict (duplicate email during registration) |
| 410 | Gone — resource permanently deleted (unlike 404) |
| 422 | Unprocessable Entity — syntax OK, but business logic failed |
| 429 | Too Many Requests — rate limiting |

**401 vs 403** — a frequent source of confusion:
```txt
401 Unauthorized: "I don't know who you are. Show some ID."
403 Forbidden:    "I know who you are. You're not allowed here."
```

**404 vs 403 when hiding a resource's existence:**
```txt
If a resource exists but the user shouldn't know it does
(e.g. someone else's private profile) — return 404, not 403.
403 reveals that the resource exists.
```

### 5xx — Server Errors

| Code | When to use |
|------|-------------|
| 500 | Unexpected server error |
| 502 | Bad Gateway — upstream returned an invalid response |
| 503 | Service Unavailable — server overloaded or in maintenance |
| 504 | Gateway Timeout — upstream didn't respond in time |

---

## Headers That Matter for a Fullstack Engineer

### Content-Type and Accept

`Content-Type` — the type of the request or response body. `Accept` — what the client is willing to receive.

```http
POST /api/users HTTP/1.1
Content-Type: application/json
Accept: application/json

{ "name": "Alice" }
```

Common MIME types:
```txt
application/json          — JSON (primary for REST APIs)
application/x-www-form-urlencoded — HTML forms
multipart/form-data       — file uploads
text/plain, text/html     — text
application/octet-stream  — binary data
```

Content negotiation: if `Accept: application/xml` and the server doesn't support XML — the correct response is `406 Not Acceptable`.

### Authorization

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI0MiJ9.xyz
Authorization: Basic dXNlcjpwYXNzd29yZA==   (user:password in base64)
Authorization: API-Key sk-proj-abc123
```

`Bearer` — the standard scheme for JWT and OAuth 2.0 tokens (RFC 6750). `Basic` — for simple auth (HTTPS only!). Non-standard schemes (`API-Key`, `Token`) — for API keys.

### Cache-Control (overview; details in [Caching and Headers])

```http
Cache-Control: no-cache        — always revalidate with server
Cache-Control: no-store        — don't cache at all
Cache-Control: max-age=3600    — cache for 1 hour
Cache-Control: private         — browser only, not CDN
Cache-Control: public          — shareable in CDN
```

Critical: `no-cache` does not mean "don't cache" — it means "always check freshness before using the cache." `no-store` means "don't cache at all." This is one of the most common HTTP misconceptions.

### Other Important Headers

```http
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000  — request tracing
X-Forwarded-For: 203.0.113.195, 70.41.3.18          — real IP behind proxy
Retry-After: 120                                     — when to retry (429/503)
Location: /api/users/43                              — URL of created resource
ETag: "33a64df551425fcc55e4d42a148795d9f25f89d"      — resource version
```

---

## The Request Lifecycle

```txt
Browser / Client
    │
    │  1. DNS resolution: api.example.com → 93.184.216.34
    │
    │  2. TCP handshake (SYN → SYN-ACK → ACK)
    │
    │  3. TLS handshake (ClientHello → ServerHello → Certificate
    │                    → Key Exchange → Finished)
    │
    │  4. HTTP request sent over TCP
    │
    ▼
Load Balancer / Reverse Proxy (nginx, CDN)
    │
    │  5. Cache check (if GET and Cache-Control allows)
    │  6. Route to a backend instance
    │
    ▼
Backend Server
    │
    │  7. Middleware: logging, rate limiting
    │  8. Auth middleware: JWT/session validation
    │  9. Route handler: business logic
    │  10. DB query
    │  11. Build the response
    │
    ▼
Response travels the reverse path
    │
    │  12. nginx/CDN may cache the response
    │  13. Browser caches according to Cache-Control
    │
    ▼
Client receives the response
```

In code (TypeScript/fetch + Express):

```typescript
// Client side (fetch API):
const response = await fetch("https://api.example.com/users/42", {
  method: "GET",
  headers: {
    "Authorization": `Bearer ${token}`,
    "Accept": "application/json",
  },
});

if (!response.ok) {
  // 4xx or 5xx
  const error = await response.json();
  throw new Error(`HTTP ${response.status}: ${error.message}`);
}

const user = await response.json();

// Server side (Express):
app.get("/api/users/:id", async (req, res) => {
  const user = await db.users.findById(req.params.id);

  if (!user) {
    return res.status(404).json({ error: "User not found" });
  }

  res.status(200).json(user);
});
```

---

## Common Interview Traps

- **"POST is for creating, PUT is for updating"** — incomplete. The correct definition is through safety and idempotency. PUT replaces a resource entirely and can create it if it doesn't exist. PATCH is a partial update. POST is the only non-idempotent method.

- **"401 and 403 are basically the same — both are about permissions"** — fundamentally different: 401 = not authenticated, 403 = authenticated but not authorized. Confusing them is an architectural mistake with security implications.

- **"`no-cache` means don't cache"** — no. `no-cache` means "always revalidate the cache with the server before using it." `no-store` means don't cache at all. This is one of the most common mistakes even among experienced developers.

- **"HTTP being stateless is a limitation"** — no, it's a deliberate design choice. Stateless enables horizontal scaling without sticky sessions, simplifies caching, and makes every request self-contained. State is carried explicitly (tokens, cookies) — which is more predictable.

- **"DELETE is idempotent, so it must return 200"** — not necessarily. First DELETE → 200 or 204. Second → 404 (resource already gone). This doesn't break idempotency: idempotency is about the same *server state*, not the same *response code*.

- **"HEAD is just GET without a body — what's the point?"** — HEAD is important for checking resource existence, getting Content-Length before downloading, and validating cache freshness without transferring data. Used by CDNs and download managers.
