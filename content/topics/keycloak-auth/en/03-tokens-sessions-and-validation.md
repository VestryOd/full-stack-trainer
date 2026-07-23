# Tokens, sessions, and validation in production

## From "we got a token" to "the token works correctly under load"

Articles 01-02 explained WHAT access/ID/refresh tokens are and HOW Keycloak builds them. This article covers the next, less obvious layer: how a Resource Server (a NestJS API) quickly and correctly decides "should I trust this token right now," what happens when a user clicks Logout, and why "just delete the token on the frontend" is only half a solution. This is exactly the level of detail that separates "I wired up a library from a tutorial" from "I can explain what happens when Keycloak rotates its signing keys at 3am."

## JWKS — how a Resource Server verifies a signature without asking Keycloak every time

An access token issued by Keycloak is a signed JWT (RS256 by default — asymmetric signing). The Resource Server's job is to verify the signature **without contacting Keycloak on every single request** — otherwise Keycloak becomes a performance bottleneck for the entire system.

The solution is **JWKS** (JSON Web Key Set): Keycloak publishes its public keys at a standard endpoint, and the Resource Server downloads them once, caches them, and from then on verifies signatures **locally**, with plain cryptography, no network call on every request.

```bash
curl https://keycloak.example.com/realms/myrealm/protocol/openid-connect/certs
```

```json
{
  "keys": [
    {
      "kid": "a1b2c3d4-key-id",
      "kty": "RSA",
      "alg": "RS256",
      "use": "sig",
      "n": "xGOr-H7A-PWG...", 
      "e": "AQAB"
    }
  ]
}
```

Every JWT's header carries a `kid` (Key ID) — a pointer to WHICH of the keys in the JWKS signed it:

```json
{ "alg": "RS256", "typ": "JWT", "kid": "a1b2c3d4-key-id" }
```

This isn't there just for tidiness — it's the mechanism that enables **key rotation with zero downtime**. Keycloak can be configured to periodically rotate its signing key (Realm Settings → Keys → Key rotation). During rotation, the JWKS temporarily contains BOTH the OLD and the NEW key: tokens issued before the rotation and still alive (TTL not expired) keep validating against the old key by its `kid`, while new tokens are signed and verified with the new one. Without `kid`, the Resource Server would have no way to know which of several keys in the JWKS applies to a given token.

```txt
Why you should NEVER hardcode the public key in your app's config:
  1. Any key rotation on the Keycloak side breaks validation for
     EVERY client using the hardcoded key, until a manual redeploy
  2. If a key is compromised, the only fast response is generating
     a new key in Keycloak; hardcoding rules that path out
  3. Libraries like jwks-rsa/jose already cache the JWKS with a TTL
     and know how to refetch when they see an unfamiliar kid — this
     is a solved problem, no need to reinvent it
```

```typescript
// NestJS: a passport-jwt strategy that validates tokens via JWKS
// jwks-rsa caches keys itself and refreshes on an unfamiliar kid
import { Strategy } from 'passport-jwt';
import { passportJwtSecret } from 'jwks-rsa';

export class KeycloakJwtStrategy extends PassportStrategy(Strategy, 'jwt') {
  constructor(config: ConfigService) {
    super({
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      algorithms: ['RS256'],
      secretOrKeyProvider: passportJwtSecret({
        jwksUri: `${config.get('KEYCLOAK_ISSUER')}/protocol/openid-connect/certs`,
        cache: true,          // cache the fetched key by kid
        rateLimit: true,      // protect against excessive JWKS requests
        jwksRequestsPerMinute: 5,
      }),
      issuer: config.get('KEYCLOAK_ISSUER'),
    });
  }

  validate(payload: KeycloakJwtPayload) {
    return payload; // available downstream as req.user
  }
}
```

The full breakdown of Guards/decorators built on top of this strategy is in [NestJS Resource Server]; the point here is the JWKS + `kid` mechanics as the way to verify signatures fast and survive key rotation without manual intervention.

## Local validation vs Token Introspection — a real trade-off

Verifying the signature via JWKS is only half of "is this token valid." There's a second, subtler question: **was this token revoked BEFORE its TTL expired** (the user logged out, an admin blocked the account, a compromise was detected)? There are two fundamentally different approaches here.

```txt
Local (offline) JWT validation:
  The Resource Server checks the signature and exp/iss/aud LOCALLY,
  using the JWKS key, with zero network calls to Keycloak per request.

  ✓ Latency:     sub-millisecond, no network dependency
  ✓ Load:        Keycloak isn't involved in the request hot path at all
  ✗ Revocation:  the Resource Server only learns about a revoked
                 token when its TTL expires — if a user is blocked
                 "right now," they still have a valid access token
                 for up to N more minutes (the access token's TTL)

Token Introspection (RFC 7662):
  The Resource Server makes a back-channel call to Keycloak on
  EVERY request: "is this token still active?"

  ✓ Revocation:  instant awareness of revocation — Keycloak answers
                 "active: false" right after logout/blocking
  ✗ Latency:     an extra network round-trip on EVERY request
  ✗ Load:        Keycloak becomes a dependency EVERY API request
                 relies on, not just login
```

```bash
# Introspection endpoint — a confidential client asks Keycloak
# about the status of a specific token
curl -X POST \
  https://keycloak.example.com/realms/myrealm/protocol/openid-connect/token/introspect \
  -u "backend-service:$CLIENT_SECRET" \
  -d "token=$ACCESS_TOKEN"
```

```json
{
  "active": true,
  "sub": "a1b2c3",
  "exp": 1719936000,
  "scope": "openid profile email",
  "client_id": "spa-client"
}
```

The practical rule: **start with local validation by default** and keep the access token TTL short (5-15 minutes) — that covers 95% of real-world cases with acceptable risk ("a stolen token lives for at most 15 minutes"). Reach for introspection selectively — not for the whole API, but for specific high-sensitivity operations (money transfers, permission changes, admin actions) where even a few minutes of delay in propagating a revocation is unacceptable. Introspecting EVERY request across the whole API is a common design mistake — it turns Keycloak into a single point of failure for a system that was supposed to be stateless.

## Opaque vs JWT-encoded refresh token

By default Keycloak makes the refresh token a JWT too (unlike plain OAuth2, which doesn't dictate a refresh token format at all — see article 01). That's a deliberate trade-off, not a spec requirement:

```txt
Opaque refresh token (a random string, requires a DB lookup):
  ✓ Reveals nothing when decoded (it's just random bytes)
  ✓ Naturally checked against a DB/Keycloak — revocation state is
    always current, because the check itself hits the store
  ✗ Requires a centralized store on the Authorization Server side

JWT refresh token (what Keycloak uses by default):
  ✓ Keycloak can encode a session ID and metadata into it, speeding
    up the internal lookup when exchanging it for a new access token
  ✗ The payload is technically readable (though the client should
    never parse it or rely on its content — a refresh token should
    stay a "black box" for the client, meant only to be sent to
    /token)
```

For client code (React/NestJS) this distinction **shouldn't affect the implementation** — either way the contract is identical: the refresh token is sent to `/token` with `grant_type=refresh_token` and never parsed or used directly by the client. The format is a Keycloak implementation detail; the refresh token should be treated as an opaque secret regardless.

## Tuning TTLs — short access token, long refresh, and why the numbers aren't arbitrary

```txt
Access Token TTL (Keycloak: Realm Settings → Tokens → Access Token Lifespan):
  Typical value: 5-15 minutes
  Logic: this is the upper bound of the "risk window" if a token
  is stolen. Shorter is safer, but triggers silent refresh more
  often (more network traffic + more UX failure points).
  15 minutes is a practical balance for most web apps.

Refresh Token TTL (Keycloak: SSO Session Idle / SSO Session Max):
  SSO Session Idle: how long a session stays alive WITHOUT activity
    (typically: a few hours — "went to lunch, didn't get logged out")
  SSO Session Max: an absolute ceiling on session lifetime, even
    with continuous activity (typically: days — forced re-login)
  Logic: this is a UX trade-off about "how often does the user see
  a login form again," not a defense against theft — that's handled
  by rotation (below) and revocation.
```

**Refresh Token Rotation** is a policy where EVERY exchange of a refresh token for a new token pair issues a NEW refresh token and invalidates the old one (Keycloak: client → Advanced Settings → "Revoke Refresh Token" / OAuth 2.0 settings, plus a built-in mechanism for public clients). This isn't just hygiene — it's a **breach-detection mechanism**: if a refresh token was compromised (say, stolen via XSS before the app used it) and the attacker tries to exchange it AFTER the legitimate client already did — Keycloak sees an attempt to reuse an already-revoked token and can react (revoke the whole chain, raise an alert). The full "reuse detection" scenario is covered in [Security Hardening and Attack Vectors].

## Keycloak's server-side sessions vs the Resource Server's stateless model — how the two coexist

This is a common source of confusion: "if the JWT is validated locally, with no call to the server — what do sessions on Keycloak even have to do with anything?" The answer: because these are **two different entities**, responsible for two different things.

```txt
┌─────────────────────────────────────────────────────────────────┐
│                     Keycloak (Authorization Server)                │
│                                                                      │
│  Server-side SSO Session:                                          │
│    Stored IN Keycloak's DB/memory. Lives until the user logs out    │
│    or SSO Session Max/Idle expires.                                 │
│    This session is exactly what gives you SSO: if the user is       │
│    already authenticated in this session, redirecting to            │
│    /authorize from ANOTHER client won't show the login form again.  │
│    THIS session is the source of truth for who's actually logged in.│
└──────────────────────────────┬──────────────────────────────────┘
                                 │ issues access/id/refresh tokens
                                 │ based on the Keycloak session
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                  NestJS Resource Server (API)                      │
│                                                                      │
│  Stores nothing about the session at all. Every request is          │
│  checked independently: is the signature valid? has exp expired?    │
│  is the aud correct? This is the classic stateless model — the      │
│  Resource Server has NO WAY of knowing whether the Keycloak          │
│  session this token came from is still alive, until the token's     │
│  exp passes (see the local-validation trade-off above).             │
└─────────────────────────────────────────────────────────────────┘
```

Practical consequence: **revoking a Keycloak session (logout, an admin block) doesn't instantly revoke already-issued access tokens** — they keep passing local validation on the Resource Server until exp, because the Resource Server has no way of knowing the state of the server-side session. This isn't a bug, it's a direct consequence of choosing a stateless model for the API — and that's exactly why a short access token TTL isn't an overcautious extra, it's the only practical way to bound the window where "the token is valid but the session is already dead."

## Logout — why "delete the token on the frontend" isn't a logout

A naive implementation ("we removed `accessToken` from memory/localStorage, done, logged out") only solves the UX of that ONE tab of that ONE client. A real logout in a system with SSO and multiple clients needs deliberately designed propagation.

```txt
Front-channel logout:
  The client that initiated logout redirects the user's browser to
  Keycloak's /protocol/openid-connect/logout endpoint. Keycloak kills
  the server-side session and, using the browser as transport, in turn
  redirects (or renders invisible iframes) to the logout endpoints of
  ALL OTHER clients that shared this same SSO session.

  ✗ Fragility: depends on the user's browser actually REACHING all
    those redirects/iframes — if the user closes the tab mid-process,
    some clients never learn about the logout
  ✗ The same third-party cookie restriction problem as
    silent-check-sso (see [React SPA Integration])

Back-channel logout (OIDC Back-Channel Logout, recommended):
  After killing the server-side session, Keycloak makes a DIRECT
  server-to-server HTTP POST to the pre-registered backchannel_logout_uri
  of EVERY client that shared this session — with no involvement of
  the user's browser at all.

  ✓ Reliability: doesn't depend on whether the user's browser or tab
    is still alive
  ✓ Works even for clients with no open UI (a mobile app in the
    background, a server-side BFF)
```

```txt
Single Logout — propagating across multiple clients:

  React SPA         NestJS BFF        Mobile App
      │                  │                 │
      │   all three got tokens               │
      │   within ONE SSO session              │
      └────────┬─────────┴────────┬────────┘
                │                  │
                ▼                  ▼
         ┌──────────────────────────────┐
         │   Keycloak SSO Session ID     │
         └──────────────┬───────────────┘
                          │ logout initiated by ANY of the clients
                          ▼
         Keycloak kills the session → dispatches back-channel logout
         POST requests to all three clients' backchannel_logout_uri
                          │
        ┌─────────────────┼─────────────────┐
        ▼                  ▼                  ▼
  React SPA clears     NestJS BFF tears     Mobile App learns
  its local copy of     down its server-      via push/on the
  the token             side session/cookie   next API call
```

```typescript
// NestJS: a minimal back-channel logout handler
// Keycloak POSTs a JWT ("logout token") here when a session ends
@Post('backchannel-logout')
async handleBackchannelLogout(@Body('logout_token') logoutToken: string) {
  const payload = await this.verifyLogoutToken(logoutToken); // verified via the same JWKS
  const sessionId = payload.sid;

  // Revoke everything the backend holds for this session:
  // BFF server-side cookies/sessions, cached refresh tokens, etc.
  await this.sessionStore.revokeBySessionId(sessionId);

  return { status: 'ok' }; // Keycloak expects a 200 OK
}
```

The key takeaway: **a correct logout isn't one client's action — it's an event that needs to be designed to reach every participant in the SSO session**, and in 2024+ architectures back-channel logout is the preferred mechanism exactly because it doesn't depend on the state of the user's browser at logout time.

## Tying it together

```txt
[JWKS + kid]                  →  how a Resource Server verifies
                                 signatures locally and survives key
                                 rotation with no manual intervention

[Local validation vs
 Introspection]                →  latency/load vs instant revocation
                                 awareness — chosen per operation
                                 sensitivity, not globally

[Opaque vs JWT refresh]        →  an Authorization Server
                                 implementation detail; the client
                                 always treats a refresh token as
                                 opaque

[Access/refresh TTL + rotation] →  a short access TTL means a small
                                 risk window; refresh token rotation
                                 is breach detection, not just hygiene

[Keycloak's server-side session
 vs the stateless Resource
 Server]                        →  two different sources of truth;
                                 the mismatch between them is exactly
                                 why a short access token TTL is
                                 mandatory, not optional

[Front-channel vs back-channel
 logout]                        →  how reliably logout propagates
                                 across the multiple clients sharing
                                 one SSO session
```

The next article — [NestJS Resource Server] — takes the mechanics from this article (JWKS validation, dealing with `exp`/revocation) and builds a concrete Guard/decorator authorization layer in NestJS on top of it.

## Common interview traps

- **"The app should hardcode Keycloak's public key to verify JWTs"** — wrong and unsafe: the correct approach is a JWKS endpoint with caching keyed by `kid`, which survives key rotation without redeploying the app. A hardcoded key is exactly what breaks the moment Keycloak goes through its next planned security maintenance.

- **"Token Introspection is always better than local validation because it gives instant revocation"** — misses half the picture: introspection makes Keycloak a dependency of EVERY API request, not just login, which undermines the whole point of a stateless resource server and adds latency to every call. The right answer is selective use for high-sensitivity operations, not a wholesale replacement of local validation.

- **"Since the access token is a JWT, you can revoke it by just deleting it from the DB"** — no, if the Resource Server validates it locally (typical), deleting the row from Keycloak's DB does nothing to an already-issued, not-yet-expired JWT — it keeps passing local signature checks until `exp`. Revocation is instant only where there's an explicit state check (introspection, a blacklist).

- **"Logout just means clearing the token from localStorage/memory on the frontend"** — incomplete: that only logs out the current tab of the current client, without ending the server-side SSO session in Keycloak or notifying other clients that shared that session. A complete logout needs either a front-channel redirect to Keycloak's logout endpoint, or (more reliably) back-channel logout propagating to every registered client.

- **"The backend should refresh the access token itself when it expires"** — a responsibility mix-up: refreshing is the CLIENT's job (whoever holds the refresh token and calls `/token`), not the Resource Server's. On receiving an expired token, the Resource Server should just respond with 401 and a clear error body — reacting to that (going and getting a new token) is entirely on the client side (see [NestJS Resource Server] and [React SPA Integration]).
