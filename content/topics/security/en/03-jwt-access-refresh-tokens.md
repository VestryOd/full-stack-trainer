# JWT, Access Token, and Refresh Token

## JWT structure — what it is physically

JWT (JSON Web Token) is a string made of three dot-separated parts: `header.payload.signature`. Each part is base64url-encoded.

```txt
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9    ← Header (base64url)
.eyJzdWIiOiIxMjMiLCJyb2xlIjoiYWRtaW4iLCJleHAiOjE3MTk5MzI4MDB9  ← Payload
.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c   ← Signature
```

```json
// Header — signing algorithm and token type
{ "alg": "HS256", "typ": "JWT" }

// Payload — claims (NOT encrypted, anyone can read them)
{
  "sub": "user-123",        // subject — user identifier
  "role": "admin",
  "exp": 1719932800,        // expiry timestamp (UNIX)
  "iat": 1719929200,        // issued at timestamp
  "jti": "unique-token-id"  // JWT ID — for blacklist/revoke
}
```

**Critical**: the payload is only signed (Signature = HMAC(header + payload, secret)), NOT encrypted. Anyone can decode the payload. Never put in JWT: passwords, secrets, full PII data.

The signature verifies: the payload was not modified after issuance. Forging the signature without the secret is impossible.

## Access Token + Refresh Token — the scheme and why you need both

```txt
Problem: if you issue one long-lived JWT (e.g. 30 days) →
if stolen, it's valid for 30 days. Can't be revoked (stateless).

Solution: two tokens with different TTLs and storage locations.

Access Token:
  TTL: 5-15 minutes
  Contains: userId, role, permissions
  Storage: memory (JS variable) or HttpOnly Cookie
  Used in: Authorization header on EVERY API request
  If stolen: valid for at most 15 minutes → minimal risk

Refresh Token:
  TTL: 7-30 days (or until explicit logout)
  Contains: only jti (token ID) or userId + jti
  Storage: HttpOnly Secure Cookie (inaccessible to JavaScript)
  Used: ONLY to obtain a new Access Token
  Stored in DB: can be instantly revoked by deleting from DB
```

## Full flow — from login to refresh

```typescript
// 1. Login
app.post('/auth/login', async (req, res) => {
  const { email, password } = req.body;
  const user = await db.users.findByEmail(email);

  if (!user || !await bcrypt.compare(password, user.passwordHash)) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }

  const accessToken = jwt.sign(
    { sub: user.id, role: user.role },
    process.env.JWT_ACCESS_SECRET!,
    { expiresIn: '15m' }
  );

  const refreshToken = crypto.randomUUID(); // opaque token
  const hashedRefreshToken = await bcrypt.hash(refreshToken, 10);

  // Save to DB to enable revocation
  await db.refreshTokens.create({
    token: hashedRefreshToken,
    userId: user.id,
    expiresAt: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
  });

  res
    .cookie('refreshToken', refreshToken, {
      httpOnly: true,     // JS can't read it
      secure: true,       // HTTPS only
      sameSite: 'strict', // CSRF protection
      maxAge: 30 * 24 * 60 * 60 * 1000, // 30 days in ms
      path: '/auth',      // only for /auth endpoints
    })
    .json({ accessToken }); // access token in JSON response
});

// 2. Refresh — get a new access token
app.post('/auth/refresh', async (req, res) => {
  const refreshToken = req.cookies.refreshToken;
  if (!refreshToken) return res.status(401).json({ error: 'No refresh token' });

  // Find and verify refresh token
  const stored = await db.refreshTokens.findValidByUserId(/* ... */);
  const isValid = stored && await bcrypt.compare(refreshToken, stored.token);
  if (!isValid || stored.expiresAt < new Date()) {
    return res.status(401).json({ error: 'Invalid or expired refresh token' });
  }

  // Refresh Token Rotation: delete old, issue new
  await db.refreshTokens.delete(stored.id);

  const newRefreshToken = crypto.randomUUID();
  const hashedNew = await bcrypt.hash(newRefreshToken, 10);
  await db.refreshTokens.create({ token: hashedNew, userId: stored.userId, /* ... */ });

  const accessToken = jwt.sign(
    { sub: stored.userId, role: stored.user.role },
    process.env.JWT_ACCESS_SECRET!,
    { expiresIn: '15m' }
  );

  res
    .cookie('refreshToken', newRefreshToken, { httpOnly: true, secure: true, sameSite: 'strict', path: '/auth' })
    .json({ accessToken });
});

// 3. Logout
app.post('/auth/logout', authenticate, async (req, res) => {
  const refreshToken = req.cookies.refreshToken;
  if (refreshToken) {
    // Delete refresh token from DB → full revoke
    await db.refreshTokens.deleteByUserId(req.user.sub);
  }
  res.clearCookie('refreshToken', { path: '/auth' }).json({ ok: true });
});
```

## Where to store tokens — choices with trade-offs

```txt
Access Token:
  Memory (JS variable):
    ✓ Inaccessible to XSS (not in DOM, not in storage)
    ✗ Lost on page refresh → need silent refresh
    Use when: SPA with an aggressive refresh strategy

  HttpOnly Cookie:
    ✓ Inaccessible to XSS
    ✗ CSRF risk (sent automatically) → need sameSite=strict/lax
    Use when: traditional web apps

  localStorage / sessionStorage:
    ✗ INSECURE: XSS script can read and exfiltrate the token
    ✗ Never use for access tokens

Refresh Token:
  HttpOnly Secure Cookie + path=/auth:
    ✓ Inaccessible to XSS
    ✓ Only sent to /auth/* endpoints (path restriction)
    ✓ sameSite=strict protects against CSRF
    This is the standard recommendation
```

## JWT Logout Problem — why logout is hard and how to solve it

The stateless nature of JWT creates a fundamental problem: once a token is issued, it can't be "forgotten" before its TTL expires.

```txt
Problems requiring instant revoke:
  1. User clicks "Sign out from all devices"
  2. User changes password (old tokens should become invalid)
  3. Admin blocks an account
  4. Token theft is detected

Solutions:

1. Short TTL (15 min):
   Simple. On logout, just delete the refresh token.
   A stolen access token is valid at most 15 minutes.
   Limitation: 15 minutes can still be critical in some cases.

2. Token Blacklist (Redis):
   On logout/revoke: store jti in Redis with TTL = remaining token lifetime.
   On every request: check jti is not in blacklist.
   Limitation: introduces state (Redis), loses clean stateless design.
   When to use: when instant revoke is required, Redis is available.

3. Refresh Token Rotation (recommended):
   Each refresh issues a NEW refresh token and invalidates the old one.
   Theft detection: if a refresh token was already used → alert + revoke all.
   Doesn't solve the problem of a stolen access token, only refresh.
```

```typescript
// Blacklist via Redis
import { createClient } from 'redis';
const redis = createClient();

async function revokeToken(jti: string, ttlSeconds: number): Promise<void> {
  await redis.setEx(`blacklist:${jti}`, ttlSeconds, '1');
}

async function isRevoked(jti: string): Promise<boolean> {
  return (await redis.exists(`blacklist:${jti}`)) === 1;
}

// In authenticate middleware:
const payload = jwt.verify(token, secret) as JwtPayload;
if (payload.jti && await isRevoked(payload.jti)) {
  return res.status(401).json({ error: 'Token revoked' });
}
```

## Signing algorithms — HS256 vs RS256

```txt
HS256 (HMAC SHA-256):
  One symmetric key for both signing and verification.
  Whoever signs → also verifies → needs access to the key.
  When: monolith or microservices with a shared secret (via secrets manager).
  Risk: if the secret leaks → any token can be forged.

RS256 (RSA SHA-256):
  Asymmetric pair: private key (signs) + public key (verifies).
  Auth service holds the private key; all other services use the public key.
  When: microservices, when you can't share the secret with every service.
  Risk: if the private key leaks → tokens can be forged.
  JWKS endpoint: Auth Server publishes public keys (/.well-known/jwks.json),
  services download automatically → key rotation without redeployment.
```

## Common interview mistakes

- **"JWT payload is encrypted"** — no. The payload is only signed (integrity), but readable without the key (just base64decode). Don't put sensitive data in the JWT payload.

- **"It's fine to store access tokens in localStorage"** — this is a vulnerability. An XSS attack can read localStorage and steal the token. Use HttpOnly Cookie or memory.

- **"Refresh tokens must be JWTs"** — no. A refresh token is an opaque string (random UUID) stored in the database. Using JWT format for refresh tokens adds risks (payload is readable) with no benefit (you need a DB for revocation anyway).

- **"Logout = delete the access token from localStorage"** — that's not a real logout for stateful systems. Proper logout: delete the refresh token from the DB (revoke), clear the cookie. The access token continues to work until TTL expiry — which is why you need a short TTL or blacklist.

- **"HS256 is better than RS256 because it's faster"** — it depends on architecture. In microservices, RS256 is safer: each service verifies via the public key without knowing the private key. HS256 requires distributing the secret to every service.
