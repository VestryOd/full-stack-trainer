<!-- verified: 2026-06-23, corrections: 0 -->
# Authentication Patterns

## Authentication vs Authorization

First, the distinction that gets confused constantly:

```txt
Authentication (AuthN):
  "Who are you?" — proving identity.
  Login/password, token, certificate.

Authorization (AuthZ):
  "What are you allowed to do?" — checking permissions.
  Roles, policies, ACLs.

Order: AuthN first, then AuthZ.
You can't check permissions without knowing who's asking.
```

HTTP responses reflect this distinction:
```txt
401 Unauthorized — not authenticated (bad name — historical accident)
403 Forbidden    — authenticated, but not authorized
```

---

## Session-Based Authentication

The classic approach: the server stores session state, the client holds an ID.

### Mechanics

```txt
1. POST /login { email, password }
   │
   ▼
2. Server checks credentials:
   - Finds user in DB
   - Verifies bcrypt password hash
   - Creates a record in the session store (Redis/DB)
   - session = { id: "abc123", userId: 42, expiresAt: ... }
   │
   ▼
3. Response:
   HTTP/1.1 200 OK
   Set-Cookie: sessionId=abc123; HttpOnly; Secure; SameSite=Lax; Path=/
   │
   ▼
4. Subsequent requests:
   GET /api/me HTTP/1.1
   Cookie: sessionId=abc123
   │
   ▼
5. Server looks up session from store by sessionId,
   gets userId → loads the user
```

### Cookie Attributes (critically important)

```http
Set-Cookie: sessionId=abc123; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=86400
```

```txt
HttpOnly        — JS cannot read this cookie (XSS protection)
Secure          — send only over HTTPS
SameSite=Strict — cookie not sent on any cross-site request
SameSite=Lax    — sent on top-level GET navigation (recommended default)
SameSite=None   — always sent (needed if API is on a different domain; + Secure required)
Path=/          — accessible for all paths
Max-Age         — TTL in seconds (preferred over Expires)
```

### Session Store

```txt
Server memory   → ❌ Doesn't scale, lost on restart
Database (Postgres) → ⚠️ Slower but durable, easy to invalidate
Redis           → ✅ Fast, built-in TTL, supports horizontal scaling
```

```typescript
import session from "express-session";
import RedisStore from "connect-redis";
import { createClient } from "redis";

const redisClient = createClient({ url: process.env.REDIS_URL });
await redisClient.connect();

app.use(session({
  store: new RedisStore({ client: redisClient }),
  secret: process.env.SESSION_SECRET!,
  resave: false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 24 * 60 * 60 * 1000, // 24 hours in ms
  },
}));
```

### Pros and Cons of Sessions

```txt
Pros:
  ✅ Instant invalidation: delete from Redis = user logged out
  ✅ Small "token" (just an ID)
  ✅ Server can see all active sessions

Cons:
  ❌ Stateful: every server needs access to the session store
  ❌ Store becomes a single point of failure (if Redis goes down)
  ❌ Extra RTT to Redis on every request
  ❌ Poor fit for mobile clients and API-to-API calls
```

---

## JWT (JSON Web Tokens)

JWT is a standard (RFC 7519) for transmitting data as signed JSON. The key difference from sessions: **the server holds no state** — all information is inside the token.

### JWT Structure

```txt
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0MiIsInJvbGUiOiJhZG1pbiIsImV4cCI6MTcxOTIwMDAwMH0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c

│──────── Header ────────│───────────── Payload ─────────────│──── Signature ────│

Header  (base64url): { "alg": "HS256", "typ": "JWT" }
Payload (base64url): { "sub": "42", "role": "admin", "exp": 1719200000 }
Signature: HMACSHA256(base64url(header) + "." + base64url(payload), secret)
```

**Important**: base64url is **encoding**, not encryption. The payload is visible to anyone. Never put sensitive data in a JWT (passwords, card numbers).

### Standard Claims

```typescript
interface JwtPayload {
  sub: string;    // Subject — user ID
  iss?: string;   // Issuer — who issued the token
  aud?: string;   // Audience — intended recipient
  exp: number;    // Expiration — unix timestamp
  iat: number;    // Issued At — unix timestamp
  jti?: string;   // JWT ID — unique ID (for blacklisting)
  // custom claims:
  role?: string;
  email?: string;
}
```

### Access Token + Refresh Token

A single JWT with a long lifetime is bad practice: it can't be revoked if compromised. The standard pattern is two tokens:

```txt
Access Token:
  - Short lifetime: 15 minutes to 1 hour
  - Contains user data (sub, role)
  - Sent with every request
  - Stateless: server does not store it
  - If compromised — small window of vulnerability

Refresh Token:
  - Long lifetime: 7–90 days
  - Stored in an HttpOnly cookie (not JS-accessible)
  - Used ONLY to obtain a new access token
  - Server STORES it (Redis/DB) — enables invalidation
```

```txt
Flow:

1. POST /auth/login
   → { accessToken: "eyJ...", expiresIn: 900 }
   + Set-Cookie: refreshToken=...; HttpOnly; Secure; SameSite=Strict

2. GET /api/me
   Authorization: Bearer eyJ...   ← access token in header
   → 200 OK (while access token is valid)

3. Access token expires:
   GET /api/me → 401 Unauthorized

4. POST /auth/refresh
   Cookie: refreshToken=...       ← browser sends automatically
   → { accessToken: "eyJ...", expiresIn: 900 }
   + Set-Cookie: refreshToken=... (rotation — new refresh token issued)

5. Logout:
   POST /auth/logout
   → Server deletes refresh token from store
   + Set-Cookie: refreshToken=; Max-Age=0 (clears the cookie)
```

### Signing Algorithms

```txt
HS256 (HMAC SHA-256):
  - Single secret key for both signing and verification
  - Fine when one service issues and verifies
  - If the key leaks — all tokens are compromised

RS256 (RSA SHA-256):
  - Private key signs, public key verifies
  - Distribute the public key to all services
  - No service except the issuer can issue tokens
  - Standard for OAuth 2.0 / OpenID Connect

ES256 (ECDSA SHA-256):
  - Like RS256, but shorter keys and faster operations
  - Preferred in modern systems
```

### TypeScript Example

```typescript
import jwt from "jsonwebtoken";
import { z } from "zod";

const ACCESS_TOKEN_SECRET = process.env.JWT_ACCESS_SECRET!;

const tokenPayloadSchema = z.object({
  sub: z.string(),
  role: z.string(),
});

type TokenPayload = z.infer<typeof tokenPayloadSchema>;

function signAccessToken(payload: TokenPayload): string {
  return jwt.sign(payload, ACCESS_TOKEN_SECRET, {
    expiresIn: "15m",
    algorithm: "HS256",
  });
}

function verifyAccessToken(token: string): TokenPayload {
  const decoded = jwt.verify(token, ACCESS_TOKEN_SECRET);
  return tokenPayloadSchema.parse(decoded);
}

function requireAuth(
  req: express.Request,
  res: express.Response,
  next: express.NextFunction
) {
  const authHeader = req.headers.authorization;
  if (!authHeader?.startsWith("Bearer ")) {
    return res.status(401).json({ error: "Missing token" });
  }

  const token = authHeader.slice(7);
  try {
    req.user = verifyAccessToken(token);
    next();
  } catch (err) {
    if (err instanceof jwt.TokenExpiredError) {
      return res.status(401).json({ error: "Token expired" });
    }
    return res.status(401).json({ error: "Invalid token" });
  }
}
```

### Pros and Cons of JWT

```txt
Pros:
  ✅ Stateless: no session store needed, scales horizontally
  ✅ Self-contained: data inside the token (fewer DB lookups)
  ✅ Cross-domain: easy to use across services
  ✅ Standard for mobile and SPA apps

Cons:
  ❌ Cannot be invalidated before expiry (without a blacklist)
  ❌ Grows in size as claims are added (every request carries the payload)
  ❌ Complex key rotation
  ❌ Many ways to implement incorrectly (alg:none, not checking exp)
```

---

## OAuth 2.0

OAuth 2.0 is a framework for **delegated authorization** (RFC 6749). The goal: allow an application to act on behalf of a user without receiving their password.

```txt
Without OAuth:
  "Allow the app to read your Google Calendar"
  Old way: give the app your Google password ← terrible

With OAuth 2.0:
  User logs in with Google (not with the app)
  Google asks: "Allow app.example.com to read Calendar?"
  User: "Yes"
  Google gives the app a token scoped to Calendar only
  The app uses the token without ever knowing the user's password
```

### OAuth 2.0 Roles

```txt
Resource Owner      — the user (owner of the data)
Client              — the application requesting access
Authorization Server — issues tokens (Google, GitHub, your auth server)
Resource Server     — the API holding protected data
```

### Authorization Code Flow (the main flow)

For web and mobile apps with a backend.

```txt
1. User clicks "Sign in with Google"

2. Client redirects the user:
   GET https://accounts.google.com/o/oauth2/auth
     ?response_type=code
     &client_id=CLIENT_ID
     &redirect_uri=https://app.example.com/callback
     &scope=openid email calendar.readonly
     &state=random_csrf_token
     &code_challenge=S256_PKCE_CHALLENGE
     &code_challenge_method=S256

3. User logs in with Google and grants consent

4. Google redirects back:
   GET https://app.example.com/callback
     ?code=AUTH_CODE
     &state=random_csrf_token

5. Backend exchanges code for tokens (server-to-server):
   POST https://oauth2.googleapis.com/token
   Content-Type: application/x-www-form-urlencoded

   grant_type=authorization_code
   &code=AUTH_CODE
   &redirect_uri=https://app.example.com/callback
   &client_id=CLIENT_ID
   &client_secret=CLIENT_SECRET
   &code_verifier=PKCE_VERIFIER

6. Authorization server returns:
   {
     "access_token": "ya29.xxx",
     "refresh_token": "1//xxx",
     "expires_in": 3600,
     "token_type": "Bearer",
     "id_token": "eyJ..."   ← OpenID Connect
   }

7. Client uses access_token:
   GET https://www.googleapis.com/calendar/v3/events
   Authorization: Bearer ya29.xxx
```

### PKCE (Proof Key for Code Exchange)

PKCE protects against authorization code interception. Required for mobile and SPA apps (which have no client_secret):

```txt
Client generates:
  code_verifier = random(43–128 chars)
  code_challenge = base64url(SHA256(code_verifier))

Sends code_challenge in the authorization request (step 2).
Sends code_verifier when exchanging code → token (step 5).
Authorization server verifies: SHA256(code_verifier) == code_challenge
```

Without PKCE: if someone intercepts the authorization code, they get tokens. With PKCE: a code without the verifier is useless.

### Client Credentials Flow

For API-to-API (no user involved):

```http
POST https://auth.example.com/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
&client_id=SERVICE_CLIENT_ID
&client_secret=SERVICE_CLIENT_SECRET
&scope=orders:read invoices:write

→ { "access_token": "...", "expires_in": 3600 }
```

Used for: microservices, background jobs, server-to-server integrations.

### OpenID Connect (OIDC)

OAuth 2.0 is about authorization (resource access). OpenID Connect adds an authentication layer on top of OAuth 2.0: it adds an `id_token` (JWT with user data) and a `/userinfo` endpoint.

```txt
OAuth 2.0:  "Allow reading Calendar" → access token
OIDC:       "Who is this user?"      → id_token (sub, email, name, picture)
```

---

## API Keys

The simplest mechanism for server-to-server and developer APIs:

```http
# In a header (preferred):
Authorization: Bearer sk-proj-abc123
X-API-Key: sk-proj-abc123

# In a query param (only for simple cases, not sensitive data):
GET /api/data?api_key=sk-proj-abc123
```

### Storing API Keys on the Server

Never store a key in plain text — only its hash:

```typescript
import crypto from "crypto";

// When creating a key:
const rawKey = `sk-proj-${crypto.randomBytes(32).toString("base64url")}`;
const keyHash = crypto.createHash("sha256").update(rawKey).digest("hex");

// Store keyHash in DB, return rawKey to the user once

// When verifying:
const incomingKey = req.headers["x-api-key"] as string;
const incomingHash = crypto.createHash("sha256").update(incomingKey).digest("hex");

const apiKey = await db.apiKeys.findOne({ where: { keyHash: incomingHash } });
if (!apiKey || apiKey.revokedAt) {
  return res.status(401).json({ error: "Invalid API key" });
}
```

### HMAC Request Signing

For high-security APIs (payment systems, AWS SDK): the entire request is signed, not just the key.

```typescript
// Client signs the request:
const timestamp = Date.now().toString();
const body = JSON.stringify(payload);
const message = `${req.method}\n${req.path}\n${timestamp}\n${body}`;
const signature = crypto
  .createHmac("sha256", API_SECRET)
  .update(message)
  .digest("hex");

// Adds to request:
headers["X-Timestamp"] = timestamp;
headers["X-Signature"] = signature;

// Server verifies:
// 1. Checks timestamp (not older than 5 minutes — replay attack protection)
// 2. Recomputes signature and compares
```

---

## Comparison

```txt
┌──────────────────┬──────────────┬────────────┬─────────────┬──────────┐
│                  │ Session      │ JWT        │ OAuth 2.0   │ API Key  │
├──────────────────┼──────────────┼────────────┼─────────────┼──────────┤
│ Invalidation     │ ✅ Instant   │ ❌ At exp  │ ✅ Refresh  │ ✅ Instant│
│ Stateless        │ ❌ No        │ ✅ Yes     │ ✅ Yes      │ ❌ No    │
│ Scaling          │ ⚠️ Needs Redis│ ✅ Easy   │ ✅ Easy     │ ⚠️ Redis │
│ Cross-domain     │ ❌ Complex   │ ✅ Easy    │ ✅ Native   │ ✅ Easy  │
│ 3rd-party auth   │ ❌ No        │ ❌ No      │ ✅ Built for│ ❌ No    │
│ Mobile           │ ⚠️ Awkward   │ ✅ Easy   │ ✅ Easy     │ ✅ Easy  │
│ Complexity       │ Low          │ Medium     │ High        │ Low      │
└──────────────────┴──────────────┴────────────┴─────────────┴──────────┘

When to use what:
  Session    — traditional web where frontend and API share a domain
  JWT        — SPA/mobile with your own auth, microservices
  OAuth 2.0  — "Sign in with Google/GitHub", accessing third-party data
  API Key    — developer APIs, server-to-server without a user
```

---

## Common Interview Traps

- **"Storing JWT in localStorage is convenient"** — it's dangerous. localStorage is accessible to any JS on the page (XSS → token theft). Access tokens belong in JS memory (lost on page reload), refresh tokens in an HttpOnly cookie (XSS-proof).

- **"JWT can't be invalidated"** — it can, at a cost. Options: blacklist `jti` in Redis, refresh token rotation (each use issues a new one), short-lived access tokens (15 min). Fully stateless JWT is not the right choice when you need instant revocation.

- **"401 and 403 are basically the same"** — no. 401: no token or invalid token. 403: valid token, but insufficient permissions. Mixing them up breaks client-side logic (401 = go to login; 403 = show "access denied").

- **"JWT signature means the data is encrypted"** — no. The signature guarantees integrity (nobody tampered with it). The data is in plain text (base64). For encryption use JWE (JSON Web Encryption) — rarely needed in practice.

- **"OAuth 2.0 = authentication"** — OAuth 2.0 is about authorization (delegated access). Authentication is added by OpenID Connect on top of OAuth 2.0 via the `id_token`. "Sign in with Google" is OIDC, not plain OAuth.

- **"client_secret can live in a SPA or mobile app"** — no. Public clients (SPA, mobile) have no safe place to store a secret. Use PKCE without a client_secret instead.

- **"Use bcrypt for API keys"** — no. bcrypt is intentionally slow (designed for passwords). API keys are long random strings; SHA-256 is sufficient. bcrypt for passwords, SHA-256 for API key hashes.
