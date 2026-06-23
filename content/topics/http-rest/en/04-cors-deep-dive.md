<!-- verified: 2026-06-23, corrections: 0 -->
# CORS Deep Dive

## Where CORS Comes From and Why It Exists

CORS is a browser mechanism, not an HTTP protocol feature. To understand why it exists, you first need to understand the **Same-Origin Policy (SOP)**.

### Same-Origin Policy

Browsers enforce SOP: JavaScript on `https://app.example.com` cannot read responses from `https://api.other.com`. "Origin" is defined by three components:

```txt
https://app.example.com:443/path
│        │              │
│        │              └── Port (default if omitted: 443 for https, 80 for http)
│        └── Host (including subdomains)
└── Scheme (protocol)

Examples:
https://example.com     vs  https://example.com      — SAME origin
https://example.com     vs  http://example.com       — DIFFERENT (scheme)
https://example.com     vs  https://api.example.com  — DIFFERENT (host)
https://example.com     vs  https://example.com:8080 — DIFFERENT (port)
```

SOP protects users: without it, a malicious site could read your `mail.google.com` inbox, make requests to `bank.com` on your behalf, etc. — just by loading JavaScript on their page.

### CORS as a Relaxation of SOP

CORS (Cross-Origin Resource Sharing) is a mechanism that lets a server **explicitly permit** requests from other origins. The server tells the browser: "yes, that foreign origin is allowed to read my responses."

```txt
Without CORS:
  browser → GET https://api.other.com/data   → response arrives
  browser blocks JavaScript from reading the response

With CORS (server allows it):
  browser → GET https://api.other.com/data   → response arrives
  Access-Control-Allow-Origin: https://app.example.com
  browser lets JavaScript read the response
```

Key insight: **CORS does not protect the server** — the request physically executes. CORS protects the browser (client) from reading foreign responses. That's why curl has no concept of CORS — it's a browser policy.

---

## Simple Requests vs Preflight

The browser categorizes cross-origin requests into two types:

### Simple Requests

The browser sends the request directly, adding an `Origin` header. If the server's response doesn't allow that origin — the browser blocks JS from reading the response (but the request already ran).

Conditions for a simple request (all three must be true):

```txt
Method: GET, HEAD, or POST
Headers: only browser-added headers plus:
  Accept, Accept-Language, Content-Language,
  Content-Type (only: text/plain, application/x-www-form-urlencoded, multipart/form-data)
No custom headers (Authorization, X-Custom-Header, etc.)
```

```http
GET /api/public-data HTTP/1.1
Host: api.other.com
Origin: https://app.example.com

─────────────────────────────────────
HTTP/1.1 200 OK
Access-Control-Allow-Origin: https://app.example.com
Content-Type: application/json

{ "data": "..." }
```

### Preflight Requests

For "non-simple" requests, the browser first sends an `OPTIONS` request asking: "am I allowed to make this request?" Only after receiving permission does it send the real request.

```txt
Browser executes: fetch("https://api.other.com/users", {
  method: "DELETE",
  headers: { "Authorization": "Bearer token" }
})

Step 1: Preflight OPTIONS
────────────────────────────────────────────────────────
OPTIONS /api/users HTTP/1.1
Host: api.other.com
Origin: https://app.example.com
Access-Control-Request-Method: DELETE
Access-Control-Request-Headers: Authorization

Step 2: Server response to preflight
────────────────────────────────────────────────────────
HTTP/1.1 204 No Content
Access-Control-Allow-Origin: https://app.example.com
Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE
Access-Control-Allow-Headers: Authorization, Content-Type
Access-Control-Max-Age: 86400

Step 3: Real request (only if preflight passed)
────────────────────────────────────────────────────────
DELETE /api/users/42 HTTP/1.1
Host: api.other.com
Origin: https://app.example.com
Authorization: Bearer token

HTTP/1.1 204 No Content
Access-Control-Allow-Origin: https://app.example.com
```

What triggers a preflight:
```txt
- Method: PUT, DELETE, PATCH, or any non-standard method
- Custom headers: Authorization, X-Requested-With, etc.
- Content-Type: application/json (!)
- Request with credentials (cookies/HTTP auth) to a different origin
```

Practical implication: **most API requests with `Content-Type: application/json` or `Authorization` trigger a preflight**. That means double the HTTP requests.

---

## CORS Headers: Full Breakdown

### Response Headers (server → browser)

**`Access-Control-Allow-Origin`**

```http
Access-Control-Allow-Origin: https://app.example.com   # Specific origin
Access-Control-Allow-Origin: *                          # All origins
```

`*` is forbidden when `credentials: "include"`. The server cannot use a wildcard and require credentials at the same time.

To allow multiple specific origins — you can't list them comma-separated. You must dynamically check the request's `Origin` and reflect it in the response:

```typescript
const ALLOWED_ORIGINS = new Set([
  "https://app.example.com",
  "https://admin.example.com",
]);

app.use((req, res, next) => {
  const origin = req.headers.origin;
  if (origin && ALLOWED_ORIGINS.has(origin)) {
    res.set("Access-Control-Allow-Origin", origin);
    res.set("Vary", "Origin"); // required! caches need to know
  }
  next();
});
```

**`Access-Control-Allow-Methods`**

```http
Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
```

Lists the allowed methods in the preflight response.

**`Access-Control-Allow-Headers`**

```http
Access-Control-Allow-Headers: Authorization, Content-Type, X-Request-ID
```

Allowed request headers. If the client requests a custom header in `Access-Control-Request-Headers`, it must appear here.

**`Access-Control-Expose-Headers`**

```http
Access-Control-Expose-Headers: X-Total-Count, X-Request-ID, ETag
```

By default, JavaScript can only read a handful of safe response headers (Content-Type, Cache-Control, Content-Language, Content-Length, Expires, Last-Modified, Pragma). To make custom headers readable by JS, they must be explicitly listed. Typical example: pagination via `X-Total-Count`.

**`Access-Control-Allow-Credentials`**

```http
Access-Control-Allow-Credentials: true
```

Permits cookies, HTTP authentication, and TLS client certificates to be sent with the request. Requires a specific origin (not `*`) in `Access-Control-Allow-Origin`.

**`Access-Control-Max-Age`**

```http
Access-Control-Max-Age: 86400
```

How many seconds the browser caches the preflight result for a given URL + method + headers combination. Without this, the browser sends OPTIONS before every request. 86400 = 1 day (browsers often cap this at ~7200 seconds).

### Request Headers (browser → server)

```http
Origin: https://app.example.com                # Where the request originates
Access-Control-Request-Method: DELETE          # The method in the real request
Access-Control-Request-Headers: Authorization  # Custom headers in the real request
```

The browser adds these automatically — your JavaScript code does not.

---

## Credentials and CORS

Credentials in the CORS context means cookies, HTTP Basic/Digest authentication, and TLS client certificates.

By default, cross-origin requests do NOT send credentials. To enable:

```typescript
// Client-side (fetch):
const response = await fetch("https://api.other.com/data", {
  credentials: "include",  // send cookies
});

// Client-side (axios):
const response = await axios.get("https://api.other.com/data", {
  withCredentials: true,
});
```

And on the server:
```http
Access-Control-Allow-Origin: https://app.example.com  # NOT wildcard!
Access-Control-Allow-Credentials: true
```

If the server responds with `Access-Control-Allow-Origin: *` when `credentials: "include"` is set — the browser blocks the response with an error.

```txt
Why * + credentials is forbidden:

* means "any site can read the response."
Credentials means "the request sends the user's cookies."
Together: "any site can read the response that includes
the logged-in user's data" — an obvious vulnerability.
```

---

## Practical Example: Express with Correct CORS

```typescript
import express from "express";

const app = express();

const ALLOWED_ORIGINS = new Set([
  "https://app.example.com",
  "https://admin.example.com",
  // For development:
  "http://localhost:3000",
  "http://localhost:5173",
]);

function handleCors(
  req: express.Request,
  res: express.Response,
  next: express.NextFunction
): void {
  const origin = req.headers.origin;

  if (origin && ALLOWED_ORIGINS.has(origin)) {
    res.set("Access-Control-Allow-Origin", origin);
    res.set("Vary", "Origin"); // critical for correct cache behavior
    res.set("Access-Control-Allow-Credentials", "true");
  }

  if (req.method === "OPTIONS") {
    res.set("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS");
    res.set("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Request-ID");
    res.set("Access-Control-Max-Age", "86400");
    res.set("Access-Control-Expose-Headers", "X-Total-Count, X-Request-ID");
    return res.sendStatus(204);
  }

  res.set("Access-Control-Expose-Headers", "X-Total-Count, X-Request-ID");

  next();
}

app.use(handleCors);

// Or use the cors package:
import cors from "cors";

app.use(cors({
  origin: (origin, callback) => {
    if (!origin || ALLOWED_ORIGINS.has(origin)) {
      callback(null, true);
    } else {
      callback(new Error(`Origin ${origin} not allowed`));
    }
  },
  credentials: true,
  methods: ["GET", "POST", "PUT", PATCH", "DELETE"],
  allowedHeaders: ["Authorization", "Content-Type", "X-Request-ID"],
  exposedHeaders: ["X-Total-Count", "X-Request-ID"],
  maxAge: 86400,
}));
```

---

## When CORS Is Not the Issue — Common Misconceptions

### "A CORS error is a server-side security problem"

No. A CORS error means the **browser** refused to pass the response to JavaScript. The request itself reached the server and executed.

```txt
CSRF attack (Cross-Site Request Forgery):
  - User is logged into bank.com
  - Visits evil.com
  - evil.com submits an HTML form: POST https://bank.com/transfer
  - Browser sends bank.com cookies automatically!
  - CORS doesn't help here (HTML forms don't follow CORS)
  - Protection: CSRF tokens, SameSite cookies, Origin/Referer validation
```

CORS controls reading the response, not whether the request runs.

### "curl can test CORS"

Impossible. curl is not a browser, it has no SOP. A successful curl request proves the endpoint works, not that a browser will allow JavaScript to read the response.

### "I'll add `Access-Control-Allow-Origin: *` and everything will work"

It will — with caveats:
- Won't work with credentials (cookies)
- This means "anyone can read my API" — fine for public APIs, a problem for private ones

### "CORS isn't needed if the API and frontend are on the same domain"

True, but with nuance:
```txt
Same origin:
  https://example.com + https://example.com/api — SAME origin
  https://app.example.com + https://api.example.com — DIFFERENT (subdomain)

Subdomain ≠ same origin.
For api.example.com ↔ app.example.com — CORS headers are required.
```

---

## Private Network Access (New Chrome Restriction)

Since Chrome 94, there's an additional restriction: requests from a public origin to a private network (localhost, 192.168.x.x, 10.x.x.x) require explicit permission.

```http
# Browser adds to the preflight:
Access-Control-Request-Private-Network: true

# Server (localhost) must respond with:
Access-Control-Allow-Private-Network: true
```

Relevant for: local apps, IoT devices, dev tools running on localhost that are accessed from public websites.

---

## Diagram: Full CORS Flow for an API Request

```txt
JavaScript code:
fetch("https://api.other.com/users/42", {
  method: "DELETE",
  headers: { "Authorization": "Bearer token" }
})

Browser determines request type:
  ├─ Simple? (GET/HEAD/POST + basic headers)
  │    → Send directly with Origin header
  │
  └─ Non-simple (DELETE / Authorization header)
       → Preflight

Preflight:
OPTIONS https://api.other.com/users/42
Origin: https://app.example.com
Access-Control-Request-Method: DELETE
Access-Control-Request-Headers: Authorization
       │
       ▼
Server api.other.com:
  Check Origin → in allow-list? ──── No ──→ 403 / no ACAO header
       │ Yes                                      │
       ▼                                          │
  HTTP/1.1 204 No Content                        │
  Access-Control-Allow-Origin: https://app.example.com
  Access-Control-Allow-Methods: DELETE            │
  Access-Control-Allow-Headers: Authorization     │
  Access-Control-Max-Age: 86400                   │
       │                                          │
       ▼                                          │
Browser:                                          │
  Preflight passed? ──── No (403/no ACAO) ───────→ CORS Error
       │ Yes                                      (JS can't read response)
       ▼
Real request:
DELETE https://api.other.com/users/42
Authorization: Bearer token
Origin: https://app.example.com
       │
       ▼
Server:
  HTTP/1.1 204 No Content
  Access-Control-Allow-Origin: https://app.example.com
       │
       ▼
Browser:
  ACAO matches Origin? ──── No ──→ CORS Error
       │ Yes
       ▼
  JavaScript receives the response ✅
```

---

## Common Interview Traps

- **"CORS is a server-side security mechanism"** — no. CORS is a browser policy that lets a server **relax** the Same-Origin Policy. The server protects itself through other means (CSRF tokens, SameSite cookies, authentication). CORS only controls what the browser passes to JavaScript.

- **"curl tests CORS"** — no. curl has no SOP. A successful curl call doesn't mean a browser will let JavaScript read the response. Test CORS in an actual browser.

- **"You can use `*` and `credentials: true` together"** — no, the browser blocks with an error. With credentials, you must specify a concrete origin.

- **"A CORS error means the request never reached the server"** — usually wrong. For simple requests, the request executes and the browser blocks reading the response. For preflighted requests, the real request isn't sent, but the OPTIONS did reach the server.

- **"Adding an `Origin` header in Node.js bypasses CORS"** — CORS is enforced by browsers, not servers. Node.js server code isn't subject to SOP/CORS. Only browser JavaScript is.

- **"A subdomain is the same origin"** — no. `app.example.com` and `api.example.com` are different origins. CORS headers are required for cross-subdomain requests.

- **"Why is `Vary: Origin` needed?"** — without it, a cache (CDN, proxy) might return a response with `Access-Control-Allow-Origin: https://a.com` to a client with origin `https://b.com`. `Vary: Origin` tells the cache to store separate versions of the response for each origin.
