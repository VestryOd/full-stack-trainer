# Tokens, sessions, and validation in production

## From "we got a token" to "the token works correctly under load"

This article answers three production questions about tokens. How does a Resource Server decide fast whether to trust a token? What really happens when a user clicks Logout? And why is "just delete the token on the frontend" only half a logout?

Articles 01-02 covered what access, ID and refresh tokens are and how Keycloak builds them. This one goes a layer down: signature checks without calling Keycloak, revocation, token lifetimes, server-side sessions, and a logout that reaches every client.

## JWKS — how a Resource Server verifies a signature without asking Keycloak every time

An access token issued by Keycloak is a signed JWT (JSON Web Token), and by default the signature algorithm is RS256 — asymmetric signing. The Resource Server has to verify that signature **without contacting Keycloak on every single request**. Otherwise Keycloak becomes a performance bottleneck for the whole system.

The solution is **JWKS** (JSON Web Key Set). Keycloak publishes its public keys at a standard endpoint. The Resource Server downloads them once and caches them. From then on it verifies signatures **locally**, with plain cryptography and no network call per request.

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

Every JWT's header carries a `kid` (Key ID) — a pointer to **which** of the keys in the JWKS signed it:

```json
{ "alg": "RS256", "typ": "JWT", "kid": "a1b2c3d4-key-id" }
```

This isn't there just for tidiness. It is the mechanism behind **key rotation with zero downtime**. Keycloak can be configured to rotate its signing key periodically (Realm Settings → Keys → Key rotation).

During rotation the JWKS holds **both** the old and the new key. Tokens issued before the rotation are still alive if their TTL (time to live) has not expired. They keep validating against the old key by its `kid`, while new tokens are signed and verified with the new key.

Without `kid` the Resource Server could not tell which of several keys in the JWKS applies to a given token.

```txt
Why you should never hardcode the public key in your app's config:
  1. Any key rotation on the Keycloak side breaks validation for
     every client using the hardcoded key, until a manual redeploy
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

Guards and decorators built on top of this strategy are covered in [NestJS Resource Server](./04-nestjs-resource-server.md). What matters here is the JWKS + `kid` mechanics: it verifies signatures fast and survives key rotation with no manual work.

## Local validation vs Token Introspection — a real trade-off

Verifying the signature via JWKS answers only half of "is this token valid". The second, subtler question: **was the token revoked before its TTL expired?** That happens when the user logs out, an admin blocks the account, or a compromise is detected. There are two fundamentally different approaches.

```txt
Local (offline) JWT validation:
  The Resource Server checks the signature and exp/iss/aud
  locally, with the JWKS key and zero network calls to Keycloak.

  ✓ Latency:     sub-millisecond, no network dependency
  ✓ Load:        Keycloak is not in the request hot path at all
  ✗ Revocation:  the Resource Server only learns about a revoked
                 token when its TTL expires — if a user is blocked
                 "right now," they still have a valid access token
                 for up to N more minutes (the access token's TTL)

Token Introspection (RFC 7662):
  The Resource Server makes a back-channel call to Keycloak on
  every request: "is this token still active?"

  ✓ Revocation:  instant awareness of revocation — Keycloak answers
                 "active: false" right after logout/blocking
  ✗ Latency:     an extra network round-trip on every request
  ✗ Load:        Keycloak becomes a dependency of every API
                 request, not just of login
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

The practical rule: **start with local validation by default** and keep the access token TTL short, 5-15 minutes. That covers 95% of real cases at an acceptable risk — a stolen token lives for at most 15 minutes.

Reach for introspection selectively, not for the whole API. Use it on specific high-sensitivity operations: money transfers, permission changes, admin actions. Those are the places where even a few minutes of delay in propagating a revocation is unacceptable.

Introspecting **every** request across the whole API is a common design mistake. It turns Keycloak into a single point of failure for a system that was supposed to be stateless.

## Opaque vs JWT-encoded refresh token

By default Keycloak makes the refresh token a JWT too. Plain OAuth2 doesn't dictate a refresh token format at all (see article 01), so this is a deliberate trade-off, not a spec requirement:

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

For client code (React or NestJS) this distinction **shouldn't affect the implementation**. Either way the contract is identical. The refresh token is sent to `/token` with `grant_type=refresh_token`, and the client never parses it or uses it directly. The format is a Keycloak implementation detail: treat a refresh token as an opaque secret in both cases.

## Tuning TTLs — short access token, long refresh, and why the numbers aren't arbitrary

```txt
Access Token TTL
  (Keycloak: Realm Settings → Tokens → Access Token Lifespan)
  Typical value: 5-15 minutes
  Logic: this is the upper bound of the "risk window" if a token
  is stolen. Shorter is safer, but triggers silent refresh more
  often (more network traffic + more UX failure points).
  15 minutes is a practical balance for most web apps.

Refresh Token TTL (Keycloak: SSO Session Idle / SSO Session Max):
  SSO Session Idle: how long a session stays alive WITHOUT activity
    (typically a few hours — "went to lunch, still logged in")
  SSO Session Max: an absolute ceiling on session lifetime, even
    with continuous activity (typically: days — forced re-login)
  Logic: this is a UX trade-off about "how often does the user see
  a login form again," not a defense against theft — that's handled
  by rotation (below) and revocation.
```

**Refresh Token Rotation** is a policy. **Every** exchange of a refresh token for a new pair issues a **new** refresh token and invalidates the old one. In Keycloak it lives under client → Advanced Settings → "Revoke Refresh Token", and public clients get it through a built-in mechanism.

This isn't just hygiene, it's a **breach-detection mechanism**. Suppose a refresh token was stolen through XSS (cross-site scripting) before the app used it. The attacker then tries to exchange it after the legitimate client already did.

Keycloak sees a reuse of an already-revoked token and can react: revoke the whole chain, raise an alert. The full "reuse detection" scenario is in [Security Hardening and Attack Vectors](./07-security-hardening-and-attack-vectors.md).

## Keycloak's server-side sessions vs the Resource Server's stateless model — how the two coexist

A common source of confusion sounds like this. If the JWT is validated locally, with no call to the server, what do Keycloak sessions have to do with anything? The answer: these are **two different entities**, responsible for two different things.

```txt
┌─────────────────────────────────────────────────────────────┐
│ Keycloak (Authorization Server)                             │
│                                                             │
│ Server-side SSO session:                                    │
│   Stored in Keycloak's DB or memory. Lives until the user   │
│   logs out, or until SSO Session Max/Idle expires.          │
│   This session is what gives you SSO: if the user is        │
│   already authenticated in it, a redirect to /authorize     │
│   from another client shows no login form again.            │
│   This session is the source of truth for who is logged in. │
└─────────────────────────────────────────────────────────────┘
                               │  issues access/id/refresh tokens
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ NestJS Resource Server (API)                                │
│                                                             │
│ Stores nothing about the session. Every request is checked  │
│ on its own: is the signature valid? has exp expired? is the │
│ aud correct? This is the classic stateless model, so the    │
│ Resource Server cannot know whether the Keycloak session    │
│ behind this token is still alive until exp passes.          │
└─────────────────────────────────────────────────────────────┘
```

Practical consequence: **revoking a Keycloak session — a logout, an admin block — does not instantly revoke access tokens that were already issued.** They keep passing local validation on the Resource Server until `exp`, because that server cannot see the state of the server-side session.

This isn't a bug. It is a direct consequence of choosing a stateless model for the API. It is also why a short access token TTL is not an overcautious extra. It is the only practical way to bound the window where the token is valid but the session is already dead.

## Logout — why "delete the token on the frontend" isn't a logout

A naive implementation — "we removed `accessToken` from memory or localStorage, done" — only fixes the user experience of **one tab of one client**. A real logout in a system with SSO (single sign-on) and several clients needs propagation that was designed on purpose.

```txt
Front-channel logout:
  The client that started the logout redirects the user's browser
  to Keycloak's /protocol/openid-connect/logout endpoint. Keycloak
  kills the server-side session and, using the browser as
  transport, redirects in turn (or renders invisible iframes) to
  the logout endpoints of all other clients that shared this same
  SSO session.

  ✗ Fragility: depends on the user's browser actually reaching
    all those redirects/iframes — if the user closes the tab
    mid-process, some clients never learn about the logout
  ✗ The same third-party cookie restriction problem as
    silent-check-sso (see article 05)

Back-channel logout (OIDC Back-Channel Logout, recommended):
  After killing the server-side session, Keycloak makes a direct
  server-to-server HTTP POST to the pre-registered
  backchannel_logout_uri of every client that shared this session,
  with no involvement of the user's browser at all.

  ✓ Reliability: doesn't depend on whether the user's browser or tab
    is still alive
  ✓ Works even for clients with no open UI (a mobile app in the
    background, a server-side BFF)
```

```txt
Single Logout — propagating across multiple clients:

React SPA, NestJS BFF and Mobile App all got their tokens
within a single SSO session.
                 │
                 ▼
    ┌─────────────────────────┐
    │ Keycloak SSO Session ID │
    └─────────────────────────┘
                 │  logout started by any client
                 ▼
Keycloak kills the session, then sends a back-channel logout
POST to the backchannel_logout_uri of all three clients:

  React SPA   — clears its local copy of the token
  NestJS BFF  — tears down its server-side session/cookie
  Mobile App  — learns via push, or on the next API call
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

The key takeaway: **a correct logout is not one client's action. It is an event that has to be designed to reach every participant in the SSO session.** In 2024+ architectures back-channel logout is the preferred mechanism, precisely because it doesn't depend on the state of the user's browser at logout time.

## Tying it together

```txt
[JWKS + kid]                  →  how a Resource Server verifies
                                 signatures locally and survives
                                 key rotation with no manual work

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
                                 is breach detection, not hygiene

[Keycloak's server-side session
 vs the stateless Resource
 Server]                        →  two different sources of truth;
                                 the mismatch between them is why a
                                 short access token TTL is
                                 mandatory, not optional

[Front-channel vs back-channel
 logout]                        →  how reliably logout propagates
                                 across the multiple clients sharing
                                 one SSO session
```

The next article, [NestJS Resource Server](./04-nestjs-resource-server.md), takes the mechanics from here — JWKS validation and dealing with `exp` and revocation. It builds a concrete Guard and decorator authorization layer in NestJS on top of them.

## Common interview traps

- **"The app should hardcode Keycloak's public key to verify JWTs"** — wrong and unsafe. The correct approach is a JWKS endpoint with caching keyed by `kid`. It survives key rotation without redeploying the app, while a hardcoded key breaks at Keycloak's next planned security maintenance.

- **"Token Introspection is always better than local validation because it gives instant revocation"** — this misses half the picture. Introspection makes Keycloak a dependency of **every** API request, not just of login. That undermines the point of a stateless resource server and adds latency to every call. The right answer is selective use for high-sensitivity operations, not a wholesale replacement of local validation.

- **"Since the access token is a JWT, you can revoke it by just deleting it from the database"** — no. If the Resource Server validates the token locally, which is the typical case, deleting the row on Keycloak's side changes nothing. The already-issued JWT has not expired yet, so it keeps passing local signature checks until `exp`. Revocation is instant only where there is an explicit state check: introspection, or a blacklist.

- **"Logout just means clearing the token from localStorage or memory on the frontend"** — incomplete. That logs out the current tab of the current client only. It does not end the server-side SSO session in Keycloak, and it does not notify the other clients that shared that session. A complete logout needs either a front-channel redirect to Keycloak's logout endpoint, or — more reliably — back-channel logout propagating to every registered client.

- **"The backend should refresh the access token itself when it expires"** — a responsibility mix-up. Refreshing is the **client's** job: whoever holds the refresh token and calls `/token`. On receiving an expired token the Resource Server should respond with 401 and a clear error body. Reacting to that, and going to get a new token, is entirely the client's job. See [NestJS Resource Server](./04-nestjs-resource-server.md) for the API side and [React SPA Integration](./05-react-spa-integration.md) for the SPA (single-page application) side.
