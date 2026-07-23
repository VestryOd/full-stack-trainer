# Keycloak / OAuth2 / OIDC — Interview Questions (Middle → Senior)

## Group 1: Protocol Fundamentals

**What's the actual difference between OAuth2 and OIDC?**

OAuth2 is an AUTHORIZATION protocol: it answers "what is the token holder allowed to do" by issuing an access token, but gives no standardized way to learn WHO the user is. OIDC is a thin IDENTITY layer built on top of OAuth2 using the same mechanics (same endpoints, same grant types), adding three specific things: an ID Token (a JWT with identity claims — `sub`, `email`, `name`), a UserInfo endpoint (fetch the current profile using an access token), and a discovery document (`/.well-known/openid-configuration`). Confusing them isn't a terminology slip, it's an architectural mistake: using an access token as proof of identity (the "OAuth as authentication" antipattern) is exactly why OIDC was created in 2014.

---

**Name the four OAuth2 roles, and explain why a backend service can be two of them at once.**

Resource Owner (the user), Client (the app requesting access), Authorization Server (Keycloak — authenticates and issues tokens), Resource Server (the API owning the protected data). A NestJS backend in a "React SPA + API" setup is a Resource Server relative to the SPA. But that same backend, when calling a DIFFERENT internal service on its own behalf (no user, via the Client Credentials Grant), is acting as a Client at that moment. Confusing "who is who" in a specific architecture is behind wrong decisions about who should refresh tokens and where they should be stored.

---

**What are front-channel and back-channel, and why does this distinction matter?**

Front-channel — data travels through the user's browser (redirects, query params, the URL fragment) — visible in browser history, the Referer header, proxy logs. Back-channel — a direct server connection, bypassing the browser, invisible to the user. Rule: secrets and tokens should travel over the back-channel wherever possible. This distinction is exactly why the Authorization Code Grant (only a one-time-use code over the front-channel, exchanged for tokens over the back-channel) is safer than the Implicit Grant (a token straight in the URL fragment — front-channel).

---

## Group 2: Grant Types

**Why is the Implicit Grant considered deprecated — give a concrete technical answer, not "it's old."**

Three concrete reasons: (1) the token travels through the URL fragment — front-channel — and ends up in browser history, the Referer header when navigating to an external link, proxy logs; (2) the token is issued right on the redirect with no additional client check, unlike Authorization Code, where the back-channel code→token exchange lets you verify a PKCE code_verifier or a client secret; (3) there's no refresh token (that would be unsafe over the front-channel too), so extending a session depended on a fragile iframe mechanism with `prompt=none`.

---

**Why doesn't ROPC (Resource Owner Password Credentials) fit modern applications?**

The client physically collects the user's password in its own form — this directly contradicts OAuth2's goal of "never exposing the password to a third party." Practical losses: MFA/step-up becomes hard without reinventing it inside the client (the Authorization Server never sees or controls the login form), and SSO becomes impossible (the user has to log in again separately in every client). Keycloak disables Direct Access Grants by default for new clients.

---

**When should you use the Client Credentials Grant, and what fundamentally sets it apart from a user login?**

When a service requests a token on its own behalf, with no user involved — an internal RPC between microservices, say. The fundamental difference: there's no front-channel step at all (no browser, no redirect), the whole exchange is a single back-channel POST to `/token` with `client_id`+`client_secret`. The issued token has no `sub` pointing at a real user, and no ID Token is issued — there's nobody to identify.

---

## Group 3: Tokens and Validation

**Explain the difference between an access token, an ID token, and a refresh token — where each one goes and who uses it.**

Access token — meant for the Resource Server, sent in the `Authorization: Bearer` header on every API call, carries scope/roles ("what's allowed"). ID Token — meant only for the client app to display user info, should never be sent to another API as an access token, carries identity claims ("who this is"), must be a JWT per OIDC. Refresh token — meant ONLY for the Authorization Server, sent only to the `/token` endpoint to get a new access token, never parsed or used directly by the client.

---

**How does a Resource Server verify a JWT's signature without contacting Keycloak on every request?**

Via JWKS (JSON Web Key Set) — Keycloak publishes its public keys at `/protocol/openid-connect/certs`, the Resource Server downloads them once, caches them, and from then on verifies signatures locally with plain cryptography, no network call. Every JWT's header carries a `kid` (Key ID) pointing to which of several keys in the JWKS signed it — this lets Keycloak rotate keys with zero downtime: during rotation, both the old and new key are simultaneously present in the JWKS.

```typescript
secretOrKeyProvider: passportJwtSecret({
  jwksUri: `${issuer}/protocol/openid-connect/certs`,
  cache: true,
  rateLimit: true,
}),
```

---

**What's the trade-off between local JWT validation and Token Introspection?**

Local validation is fast (sub-millisecond, no network), but the Resource Server only learns about revocation once the TTL expires (revocation isn't instant). Introspection (`POST /token/introspect`) gives instant revocation awareness, but adds a network round-trip to every request and makes Keycloak a dependency of every API call, not just login. In practice: local validation by default with a short access token TTL (5-15 minutes), introspection selectively for high-sensitivity operations (money transfers, admin actions).

---

**Why shouldn't you hardcode Keycloak's public key in the app's config?**

Three reasons: (1) any key rotation on Keycloak's side breaks validation for every client with a hardcoded key, until a manual redeploy; (2) if a key is compromised, the fastest response is generating a new one in Keycloak — hardcoding rules that path out; (3) libraries like jwks-rsa already solve caching and refreshing by `kid` — no need to reinvent it.

---

## Group 4: Keycloak Specifics

**What's the difference between a realm role and a client role, and how do you decide which to use?**

A realm role exists at the level of the whole realm and is meaningful across all clients at once (`realm_access.roles`). A client role exists in the context of a specific client and makes no sense for others (`resource_access.<client>.roles`). The rule of thumb: if a permission is meaningful "for the user in general" — a realm role; if it's specific to one service ("can this user delete invoices in billing-service") — a client role of that service. Making everything a realm role "for simplicity" turns `realm_access.roles` into a pile of entries with no clue which service each one belongs to.

---

**What fundamentally sets Identity Brokering apart from User Federation?**

Identity Brokering — Keycloak delegates AUTHENTICATION to an external IdP (Google, another Keycloak): the user is redirected to the external provider, logs in there, Keycloak gets a token/assertion back and creates a local "shadow" account tied to the external `sub`. Keycloak never sees the password at all. User Federation — Keycloak checks the password itself, but the data (and the bind request itself) go to an external store — typically LDAP/AD. Mnemonic: brokering is "one more button on the login screen" (a visible UX choice), federation is "an invisible backend" for the standard login form.

---

**What's a Protocol Mapper, and when do you need a custom SPI mapper instead of a built-in one?**

A Protocol Mapper is a rule inside a Client Scope, turning data (a user attribute, a role, a static value) into a specific token claim. Built-in mappers are enough when the data already exists as a user attribute/role/group. A custom Protocol Mapper SPI (Java) is needed when a claim requires data that physically doesn't live in Keycloak (say, "current subscription tier" from an external billing service), or logic more complex than declarative mapping — with a real ongoing maintenance cost (versioning against the Keycloak version).

---

## Group 5: NestJS Resource Server

**Why should authentication and authorization in NestJS be two separate Guards, not one?**

`AuthGuard('jwt')` answers "who is this" (validating the token, extracting the payload), `RolesGuard` answers "what are they allowed to do" (comparing roles from the payload against the decorator's metadata). The separation lets you reuse `RolesGuard` for OTHER authentication methods (an API key for internal services, say) without duplicating the role-checking logic. A fused Guard would have to be copied wholesale the moment a second authentication method appears.

---

**When is simple role-based checking not enough, and what does Keycloak Authorization Services give you in that case?**

When a rule depends on a SPECIFIC resource instance (ownership: "only my documents") or on context (time, attributes beyond roles). Authorization Services introduces a Resource + Scope + Policy + Permission model: the Resource Server (the Policy Enforcement Point) asks Keycloak (the Policy Decision Point) via a UMA-ticket request, "can this user perform the 'edit' scope on the 'Invoice:42' resource?" The cost is a network round-trip and the model's cognitive overhead; for a simple "my records vs someone else's" it's often enough to check `resource.ownerId === user.sub` directly in code, without rolling out full UMA.

---

**Who should refresh the access token — the client or the Resource Server, and what should the API return on an expired token?**

Always the client — it's the one holding the refresh token (except in a BFF architecture, where that's a separate, deliberately designed role). The Resource Server physically has no user refresh token and shouldn't try to get one — that would break the API's stateless model, turning it into a hidden auth client. The correct reaction to an expired/invalid token is a 401 with a structured error body (`{"error": "token_expired"}`), and the follow-up reaction (refresh or re-login) is entirely on the client side.

---

**Which architectural choice is safer in microservices: every service validates the JWT itself, or an API Gateway validates once?**

Every service validating itself is the safer default, especially in Kubernetes environments where network isolation isn't guaranteed (a neighboring pod in the same namespace can physically reach the service directly). The Gateway option only pays off as part of a deliberate zero-trust architecture with mTLS between the Gateway and the services — not just "saving one JWKS call," especially since JWKS validation is already a cheap, local operation.

---

## Group 6: React SPA, Token Storage, BFF

**Why is Authorization Code + PKCE the only correct flow for an SPA?**

A React SPA is a public client: all the code runs in the user's browser, any "secret" in the JS bundle is reachable via DevTools. PKCE needs no client_secret at all — the `code_verifier` defends against authorization code interception without any secret, because an intercepted `code` is useless without the original `code_verifier`, which never left the legitimate client's memory.

---

**What's the silent-check-sso problem in Safari, and how would you diagnose it?**

The mechanism: an invisible iframe loads a Keycloak page with `prompt=none`, and if the user has an active session, Keycloak hands back an authorization code silently, via `postMessage`. This requires sending Keycloak's session cookie in the context of an iframe embedded on a domain that's foreign to Keycloak — a classic third-party cookie scenario. Safari ITP blocks third-party cookies by default, so silent-check-sso silently "fails to find" a genuinely active session, and the app shows a login screen to a user who's formally already logged in. Diagnosis: reproduce it specifically in Safari (not Chrome with default settings), inspect the iframe's network requests — Keycloak's session cookie physically isn't attached to the request. Mitigations: `login-required` instead of `check-sso` if there's no anonymous content, or moving to the BFF pattern, which removes the problem architecturally. Secondary hypotheses worth checking and ruling out: too short an Access Token TTL combined with a bug in the frontend's `updateToken()`/retry logic, and an SSO Session Idle timeout that genuinely expired due to inactivity.

---

**Compare the trade-offs of storing a token in memory, in localStorage, and in an httpOnly cookie.**

In-memory — unreachable by XSS, but lost on a page refresh (needs a silent refresh). localStorage — reachable by ANY JS, including code injected via XSS — the only option with no real justification for why the industry treats it as off-limits for tokens. httpOnly cookie — unreachable by XSS, but sent by the browser automatically on every request to the domain, including ones triggered by a malicious page (CSRF) — requires mandatory SameSite + Secure + precise CORS. This isn't a "secure vs insecure" choice, it's a choice of which attack vector you're accepting as a risk.

---

**Explain the BFF pattern, and when it's justified compared to a public client in the browser.**

A BFF removes the problem architecturally: the browser never sees the access/refresh/ID token, only the app's own first-party session cookie. The BFF (a confidential client) does the Authorization Code + PKCE exchange itself on the server, stores tokens in Redis/a DB keyed by session ID, and proxies API requests carrying the real token. Pros: XSS physically can't steal the token (nothing to read), the third-party cookie problem disappears architecturally. Cons: an extra network hop, an extra server-full component, the BFF itself becomes a critical attack target. Justified for fintech/healthcare/enterprise apps with high security stakes; for an MVP, the classic public client remains adequate and faster to build.

---

## Group 7: Attacks and Defenses

**Why does PKCE matter even for confidential clients, which already have a client_secret?**

`client_secret` protects against SOMEONE ELSE impersonating the client at the code→token exchange step. But it doesn't protect against a scenario where an attacker intercepted a `code` meant for this specific client and tries to exchange it through the SAME confidential client before the legitimate user does (a race condition on interception). PKCE closes exactly this scenario regardless of client type, which is why the modern OAuth 2.0 Security BCP recommends it for all clients.

---

**What's the difference between `state` and `nonce`, and why are both needed?**

`state` protects the redirect exchange itself from CSRF/replay: the client generates a random value before redirecting, stores it locally, verifies it on the callback — preventing Login CSRF (tying the victim's session to the attacker's account). `nonce` protects the ID Token's content from being replayed: Keycloak embeds it INSIDE the token itself as a claim, the client checks it on receipt — preventing a re-presented, not-yet-expired old ID Token. Mnemonic: `state` is transport, `nonce` is content; they don't substitute for each other.

---

**Describe the mechanics of a JWT algorithm confusion attack, and how you'd defend against it.**

The "alg: none" attack — an attacker changes the token's header to `{"alg": "none"}`, drops the signature; a vulnerable library that trusts the `alg` from the token itself "verifies" an empty signature and accepts the token. The RS256/HS256 confusion attack — an attacker changes the header to `{"alg": "HS256"}` and signs the token with HMAC using Keycloak's PUBLIC RSA key (openly available via JWKS) as the secret; if the library doesn't strictly check for the expected algorithm and instead "adapts" to whatever the token claims, the check passes. The defense in both cases is the same: `algorithms` is ALWAYS hardcoded in the Resource Server's config (`algorithms: ['RS256']`), never derived from the value inside the token.

---

**Why is refresh token rotation a breach-detection mechanism, not just hygiene?**

Every exchange of a refresh token for a new pair revokes the old one. If a token is stolen (say via XSS before the legitimate client uses it): if the attacker uses it first, the legitimate app's attempt to use its own (already revoked) token errors out — a compromise signal. If the legitimate client uses it first, the attacker's later attempt to use the already-revoked token signals a reuse attempt to Keycloak. The correct reaction is revoking the ENTIRE token chain for that session, not just rejecting one request, because there's no reliable way to tell which copy of the token is "the right one."

---

## Group 8: Architecture and Scenarios

**What's the trade-off between realm-per-tenant and a shared realm with groups for a multi-tenant SaaS?**

Realm-per-tenant gives full isolation out of the box (its own password policy, theme, Identity Providers) — but operational load grows linearly with the number of tenants (realm-as-code config, monitoring, upgrades all multiply by N realms). A shared realm with groups (`/tenants/acme-corp` + a `tenant_id` claim via a Protocol Mapper) doesn't grow linearly, but data isolation falls on the application — the Resource Server MUST filter by `tenant_id` on every request, and a mistake here means a cross-tenant data leak, no longer a Keycloak problem. In practice: realm-per-tenant for B2B enterprise with tens-hundreds of large customers and strict compliance requirements; shared realm for self-serve with thousands of small tenants.

---

**Scenario: users on Safari occasionally get silently logged out, with nothing resembling a logout action on their part. How would you diagnose this?**

The first hypothesis isn't logout — it's a failure of the session-CHECKING mechanism: if the app uses `onLoad: 'check-sso'` in `keycloak-js`, silent-check-sso relies on an iframe embedded from the app's domain, reading Keycloak's session cookie — a third-party cookie scenario that Safari ITP blocks by default. Verification: reproduce it specifically in Safari with an active Keycloak session in a sibling tab — check-sso won't find the session even though it's genuinely alive, and the app shows an unauthenticated state. If confirmed, three fixes: (1) accept it and make sure the UX for that case is decent (a visible "Log in" button, not a blank screen); (2) switch to `login-required` if there's no anonymous content; (3) architecturally move to the BFF pattern, where identification goes through the app's own first-party cookie and the third-party cookie problem disappears entirely. Secondary hypotheses worth checking and ruling out too: too short an Access Token TTL combined with a bug in the frontend's `updateToken()`/retry logic, and an SSO Session Idle timeout that genuinely expired due to real inactivity.

---

**Design the auth architecture for a new multi-tenant SaaS on Keycloak — what decisions would you make, and why?**

Key decisions: (1) Multi-tenancy — if you expect a small number of large enterprise customers with individual requirements (their own Identity Provider, custom login branding, strict compliance) — realm-per-tenant, despite the growing operational load; if it's a self-serve model with many small tenants — a shared realm with group-based isolation and a `tenant_id` claim that's mandatorily filtered on EVERY Resource Server request. (2) Token storage — given real security requirements (typical for B2B SaaS with corporate customers), start directly with the BFF pattern rather than a public client in the browser — it removes a whole class of problems (XSS token theft, silent-check-sso's third-party cookie fragility) architecturally. (3) Authorization — realm/client roles for static rules, Keycloak Authorization Services only where ownership-based or contextual authorization is genuinely needed, not by default. (4) Operations — deploy Keycloak from day one as an HA cluster with a real database (PostgreSQL) and realm-as-code (keycloak-config-cli/Terraform) for reproducible environments, not console clicks. (5) Logout — back-channel logout rather than front-channel, so propagating logout across the multiple clients sharing an SSO session doesn't depend on the state of the user's browser.
