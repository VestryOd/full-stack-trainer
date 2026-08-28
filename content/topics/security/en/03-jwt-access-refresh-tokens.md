# JWT, Access Token, and Refresh Token

## JWT structure — what it is physically

JWT (JSON Web Token) is a string made of three dot-separated parts: `header.payload.signature`. Each part is base64url-encoded.

```txt
Header (base64url):
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9
Payload:
.eyJzdWIiOiIxMjMiLCJyb2xlIjoiYWRtaW4iLCJleHAiOjE3MTk5MzI4MDB9
Signature:
.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c
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

**Critical**: the payload is only signed, **not** encrypted. The signature is an HMAC (hash-based message authentication code) computed over the header plus the payload with the secret. Anyone can decode the payload, so never put passwords, secrets or full PII (personally identifiable information) data into a JWT.

The signature verifies: the payload was not modified after issuance. Forging the signature without the secret is impossible.

## Access Token + Refresh Token — the scheme and why you need both

The naive answer is one long-lived JWT, say 30 days. Issue that and a stolen copy stays valid for 30 days, with no way to revoke it because the scheme is stateless. The fix is two tokens with different lifetimes and different storage locations.

**Access Token**

- TTL (time to live): 5-15 minutes.
- Contains: `userId`, role, permissions.
- Storage: memory (a JS variable) or an HttpOnly cookie.
- Used in: the `Authorization` header on **every** API request.
- If stolen: valid for at most 15 minutes, so the risk is minimal.

**Refresh Token**

- TTL: 7-30 days, or until an explicit logout.
- Contains: only `jti` (token ID), or `userId` plus `jti`.
- Storage: HttpOnly Secure cookie, inaccessible to JavaScript.
- Used: **only** to obtain a new access token.
- Stored in the database, so deleting the row revokes it instantly.

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
    .cookie('refreshToken', newRefreshToken, {
      httpOnly: true,
      secure: true,
      sameSite: 'strict',
      path: '/auth',
    })
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

Every option trades one threat against another. XSS (cross-site scripting) can read whatever JavaScript can read, and CSRF (cross-site request forgery) rides on whatever the browser sends automatically.

**Access Token in memory, as a JS variable:**

- ✓ Inaccessible to XSS: it is not in the DOM (document object model) and not in storage.
- ✗ Lost on page refresh, so you need a silent refresh.
- Use when: an SPA (single-page application) with an aggressive refresh strategy.

**Access Token in an HttpOnly Cookie:**

- ✓ Inaccessible to XSS.
- ✗ CSRF risk, because it is sent automatically, so you need `sameSite=strict` or `sameSite=lax`.
- Use when: traditional web apps.

**Access Token in localStorage or sessionStorage:**

- ✗ **Insecure**: an XSS script can read the token and send it to the attacker.
- ✗ Never use this for access tokens.

**Refresh Token in an HttpOnly Secure Cookie with `path=/auth`:**

- ✓ Inaccessible to XSS.
- ✓ Only sent to `/auth/*` endpoints, thanks to the path restriction.
- ✓ `sameSite=strict` protects against CSRF.
- This is the standard recommendation.

## JWT Logout Problem — why logout is hard and how to solve it

The stateless nature of JWT creates a fundamental problem: once a token is issued, it can't be "forgotten" before its TTL expires.

**Problems that require an instant revoke:**

1. The user clicks "Sign out from all devices".
2. The user changes password, and old tokens should become invalid.
3. An admin blocks an account.
4. Token theft is detected.

**Solution 1 — short TTL of 15 minutes.** Simple: on logout you just delete the refresh token. A stolen access token is then valid for at most 15 minutes. Limitation: 15 minutes can still be critical in some cases.

**Solution 2 — token blacklist in Redis.** On logout or revoke, store the `jti` in Redis with a TTL equal to the token's remaining lifetime. On every request, check that the `jti` is not in the blacklist. Limitation: this introduces state (Redis) and loses the clean stateless design. Use it when instant revoke is required and Redis is available.

**Solution 3 — refresh token rotation, the recommended option.** Each refresh issues a **new** refresh token and invalidates the old one. Theft detection: if a refresh token was already used, raise an alert and revoke everything. It doesn't solve the problem of a stolen access token, only of a stolen refresh token.

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

Both names say how the signature is produced. HS256 is HMAC over SHA-256, the secure hash algorithm, with one shared key. RS256 is RSA (Rivest-Shamir-Adleman) over SHA-256, with a key pair.

**HS256 — one symmetric key for both signing and verification.**

- Whoever signs also verifies, so every party needs access to the key.
- When: a monolith, or microservices with a shared secret from a secrets manager.
- Risk: if the secret leaks, any token can be forged.

**RS256 — an asymmetric pair: the private key signs, the public key verifies.**

- The auth service holds the private key; all other services use the public key.
- When: microservices, where you can't share the secret with every service.
- Risk: if the private key leaks, tokens can be forged.
- JWKS (JSON Web Key Set) endpoint: the auth server publishes public keys at `/.well-known/jwks.json`. Services download them automatically, so keys rotate without a redeployment.

## Common interview mistakes

- **"JWT payload is encrypted"** — no. The payload is only signed (integrity), but readable without the key (just base64decode). Don't put sensitive data in the JWT payload.

- **"It's fine to store access tokens in localStorage"** — this is a vulnerability. An XSS attack can read localStorage and steal the token. Use HttpOnly Cookie or memory.

- **"Refresh tokens must be JWTs"** — no. A refresh token is an opaque string, a random UUID (universally unique identifier), stored in the database. Using JWT format for refresh tokens adds risks (payload is readable) with no benefit, because you need a database for revocation anyway.

- **"Logout = delete the access token from localStorage"** — that's not a real logout for stateful systems. Proper logout: delete the refresh token from the database, which revokes it, and clear the cookie. The access token continues to work until TTL expiry — which is why you need a short TTL or blacklist.

- **"HS256 is better than RS256 because it's faster"** — it depends on architecture. In microservices, RS256 is safer: each service verifies via the public key without knowing the private key. HS256 requires distributing the secret to every service.
