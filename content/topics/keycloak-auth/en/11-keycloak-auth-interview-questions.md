# Keycloak / OAuth2 / OIDC — Interview Questions (Middle → Senior)

## Group 1: Protocol Fundamentals

**What's the actual difference between OAuth2 and OIDC?**

OAuth2 is an **authorization** protocol; OIDC (OpenID Connect) is an **identity** layer on top of it. OAuth2 issues an access token that answers "what is the token holder allowed to do". It gives no standard way to learn **who** the user is.

OIDC reuses the same mechanics — the same endpoints, the same grant types — and adds three things:

- **ID Token** — a JWT (JSON Web Token) carrying identity claims: `sub`, `email`, `name`.
- **UserInfo endpoint** — fetch the current profile using an access token.
- **Discovery document** — `/.well-known/openid-configuration`.

Confusing the two is an architectural mistake, not a terminology slip. Using an access token as proof of identity is the "OAuth as authentication" antipattern. Closing that hole is exactly why OIDC was created in 2014.

```txt
           Two layers, two artifacts
┌─────────────┬──────────────┬─────────────────┐
│ layer       │ artifact     │ answers         │
├─────────────┼──────────────┼─────────────────┤
│ OAuth2      │ access token │ what is allowed │
├─────────────┼──────────────┼─────────────────┤
│ OIDC on top │ ID Token     │ who the user is │
└─────────────┴──────────────┴─────────────────┘
```

---

**Name the four OAuth2 roles, and explain why a backend service can be two of them at once.**

The four roles are:

- **Resource Owner** — the user.
- **Client** — the app requesting access.
- **Authorization Server** — Keycloak, which authenticates the user and issues tokens.
- **Resource Server** — the API that owns the protected data.

A NestJS backend serving a React SPA (single-page application) is a Resource Server relative to that SPA. The same backend becomes a Client the moment it calls a **different** internal service on its own behalf. There is no user in that call — it goes through the Client Credentials Grant.

```txt
            The same backend, two roles
┌─────────────────────────┬───────────────────────┐
│ the call                │ the NestJS backend is │
├─────────────────────────┼───────────────────────┤
│ React SPA to NestJS API │ Resource Server       │
├─────────────────────────┼───────────────────────┤
│ NestJS API to billing   │ Client                │
└─────────────────────────┴───────────────────────┘
```

Confusing "who is who" in a concrete architecture is behind wrong decisions about who refreshes tokens and where those tokens are stored.

---

**What are front-channel and back-channel, and why does this distinction matter?**

Front-channel means the data travels through the user's browser: redirects, query parameters, the URL fragment. That path is visible in browser history, in the `Referer` header and in proxy logs. Back-channel means a direct server connection that bypasses the browser and is invisible to the user.

```txt
                Where the data actually travels
┌───────────────┬─────────────────────┬────────────────────────┐
│ channel       │ path                │ seen in                │
├───────────────┼─────────────────────┼────────────────────────┤
│ front-channel │ through the browser │ history, Referer, logs │
├───────────────┼─────────────────────┼────────────────────────┤
│ back-channel  │ server to server    │ nothing                │
└───────────────┴─────────────────────┴────────────────────────┘
```

The rule: secrets and tokens travel over the back-channel wherever possible.

This is exactly why the Authorization Code Grant is safer than the Implicit Grant. Authorization Code sends only a one-time code over the front-channel, then exchanges it for tokens over the back-channel. Implicit puts the token itself straight into the URL fragment — front-channel.

---

## Group 2: Grant Types

**Why is the Implicit Grant considered deprecated — give a concrete technical answer, not "it's old."**

```txt
    What Implicit puts in the address bar
┌────────────────────────────────────────────┐
│ https://app.example.com/callback           │
│   #access_token=eyJhbGci...&expires_in=300 │
│   ▲ the token itself, on the front-channel │
└────────────────────────────────────────────┘
```

Three concrete reasons:

1. The token travels through the URL fragment — the front-channel. It ends up in browser history, in the `Referer` header when the user follows an external link, and in proxy logs.
2. The token is issued right on the redirect, with no extra check of the client. Authorization Code is different: the back-channel code→token exchange lets Keycloak verify a PKCE (Proof Key for Code Exchange) `code_verifier` or a client secret.
3. There is no refresh token, because that would be unsafe over the front-channel too. Extending a session therefore depended on a fragile iframe mechanism with `prompt=none`.

---

**Why doesn't ROPC (Resource Owner Password Credentials) fit modern applications?**

The client physically collects the user's password in its own form. That directly contradicts OAuth2's goal of never exposing the password to a third party.

```txt
          The ROPC request, in full
┌────────────────────────────────────────────┐
│ POST /token                                │
│   grant_type=password                      │
│   &username=user@example.com               │
│   &password=<the user's own password>      │
│   ▲ the client holds it, not only Keycloak │
└────────────────────────────────────────────┘
```

Two practical losses follow:

- **MFA and step-up become hard.** MFA is multi-factor authentication. The Authorization Server never sees or controls the login form, so you would have to reinvent MFA inside the client.
- **SSO becomes impossible.** SSO is single sign-on: one login shared by several apps. With ROPC the user logs in again, separately, in every client.

Keycloak disables Direct Access Grants by default for new clients.

---

**When should you use the Client Credentials Grant, and what fundamentally sets it apart from a user login?**

```typescript
// one back-channel call: no browser, no redirect
await fetch(`${issuer}/protocol/openid-connect/token`, {
  method: 'POST',
  body: new URLSearchParams({
    grant_type: 'client_credentials',
    client_id: 'service-a',
    client_secret: process.env.SERVICE_A_SECRET!,
  }),
});
```

When a service asks for a token on its own behalf, with no user involved. An internal RPC (remote procedure call) between microservices is the typical case.

The fundamental difference is that there is no front-channel step at all: no browser, no redirect. The whole exchange is a single back-channel `POST` to `/token` with `client_id` and `client_secret`.

The issued token has no `sub` pointing at a real user, and no ID Token is issued. There is nobody to identify.

```txt
       The /token response for client_credentials
┌──────────────────────────────────────────────────────┐
│ access_token                  yes                    │
│ id_token                      no, nobody to identify │
│ sub of a real user            no                     │
└──────────────────────────────────────────────────────┘
```

---

## Group 3: Tokens and Validation

**Explain the difference between an access token, an ID token, and a refresh token — where each one goes and who uses it.**

Each of the three has exactly one intended recipient:

- **Access token** — for the Resource Server. Sent in the `Authorization: Bearer` header on every API call. Carries scope and roles: "what is allowed".
- **ID Token** — for the client app only, to display user info. It must never be sent to another API as an access token. Carries identity claims: "who this is". OIDC requires it to be a JWT.
- **Refresh token** — for the Authorization Server **only**. Sent only to the `/token` endpoint, to get a new access token. The client never parses it and never uses it directly.

```txt
         Three artifacts, three recipients
┌─────────┬──────────────────────┬────────────────┐
│ token   │ goes to              │ sent to        │
├─────────┼──────────────────────┼────────────────┤
│ access  │ Resource Server      │ every API call │
├─────────┼──────────────────────┼────────────────┤
│ ID      │ the client app only  │ nowhere        │
├─────────┼──────────────────────┼────────────────┤
│ refresh │ Authorization Server │ /token only    │
└─────────┴──────────────────────┴────────────────┘
```

---

**How does a Resource Server verify a JWT's signature without contacting Keycloak on every request?**

Through JWKS — the JSON Web Key Set. Keycloak publishes its public keys at `/protocol/openid-connect/certs`. The Resource Server downloads them once and caches them. After that it verifies signatures locally, with plain cryptography and no network call.

Every JWT header carries a `kid` (Key ID) saying which key in the set signed that token. That is what lets Keycloak rotate keys with zero downtime. During rotation the old and the new key sit in the JWKS at the same time.

```typescript
secretOrKeyProvider: passportJwtSecret({
  jwksUri: `${issuer}/protocol/openid-connect/certs`,
  cache: true,
  rateLimit: true,
}),
```

---

**What's the trade-off between local JWT validation and Token Introspection?**

Local validation is fast — sub-millisecond, no network. Its cost: the Resource Server only learns about a revoked token once the TTL (time to live) expires, so revocation is not instant.

Introspection (`POST /token/introspect`) makes revocation visible immediately. Its cost: a network round-trip on every request, and Keycloak becomes a dependency of every API call, not just of login.

```txt
            The two validation modes, side by side
┌────────────┬───────────────────────┬───────────────────────┐
│            │ local                 │ introspection         │
├────────────┼───────────────────────┼───────────────────────┤
│ speed      │ sub-millisecond       │ a round-trip per call │
├────────────┼───────────────────────┼───────────────────────┤
│ revocation │ visible after the TTL │ visible at once       │
├────────────┼───────────────────────┼───────────────────────┤
│ Keycloak   │ needed at login       │ needed on every call  │
└────────────┴───────────────────────┴───────────────────────┘
```

In practice: local validation by default, with a short access token TTL of 5-15 minutes. Introspection is used selectively, for high-sensitivity operations such as money transfers and admin actions.

---

**Why shouldn't you hardcode Keycloak's public key in the app's config?**

Three reasons:

1. Any key rotation on Keycloak's side breaks validation for every client holding a hardcoded key, until someone redeploys by hand.
2. If a key is compromised, the fastest response is to generate a new one in Keycloak. A hardcoded key rules that path out.
3. Libraries such as `jwks-rsa` already solve caching and refreshing by `kid`. There is no need to reinvent it.

```typescript
// brittle: any key rotation breaks this until someone redeploys
{ publicKey: '-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkq...' }

// resilient: the library fetches and refreshes the key by kid
{ jwksUri: `${issuer}/protocol/openid-connect/certs` }
```

---

## Group 4: Keycloak Specifics

**What's the difference between a realm role and a client role, and how do you decide which to use?**

A realm role exists at the level of the whole realm and is meaningful across all clients at once (`realm_access.roles`). A client role exists in the context of one client and means nothing to the others (`resource_access.<client>.roles`).

The rule of thumb:

- The permission is meaningful "for the user in general" → a realm role.
- The permission is specific to one service, such as "can this user delete invoices in billing-service" → a client role of that service.

```txt
           Two roles, two claim paths
┌─────────────┬────────────────────────────────┐
│ role kind   │ where it lands in the token    │
├─────────────┼────────────────────────────────┤
│ realm role  │ realm_access.roles             │
├─────────────┼────────────────────────────────┤
│ client role │ resource_access.<client>.roles │
└─────────────┴────────────────────────────────┘
```

Making everything a realm role "for simplicity" turns `realm_access.roles` into a pile of entries with no clue which service each one belongs to.

---

**What fundamentally sets Identity Brokering apart from User Federation?**

**Identity Brokering** — Keycloak delegates **authentication** to an external IdP (identity provider) such as Google or another Keycloak. The user is redirected to that provider and logs in there. Keycloak gets a token or an assertion back, and creates a local "shadow" account tied to the external `sub`. Keycloak never sees the password at all.

```txt
                    Who checks the password
┌────────────────────┬───────────────────────┬─────────────────┐
│ mechanism          │ checks the password   │ the user sees   │
├────────────────────┼───────────────────────┼─────────────────┤
│ Identity Brokering │ the external provider │ one more button │
├────────────────────┼───────────────────────┼─────────────────┤
│ User Federation    │ Keycloak itself       │ the usual form  │
└────────────────────┴───────────────────────┴─────────────────┘
```

**User Federation** — Keycloak checks the password itself, but the data, and the bind request itself, go to an external store. That store is typically LDAP (Lightweight Directory Access Protocol) or Active Directory.

Mnemonic: brokering is "one more button on the login screen", a choice the user can see. Federation is "an invisible backend" behind the standard login form.

---

**What's a Protocol Mapper, and when do you need a custom SPI mapper instead of a built-in one?**

```txt
           What a mapper actually does
┌───────────────────────────────────────────────┐
│ A user attribute, a role, a static value      │
└───────────────────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│ Protocol Mapper, configured in a Client Scope │
└───────────────────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│ One specific claim in the issued token        │
└───────────────────────────────────────────────┘
```

A Protocol Mapper is a rule inside a Client Scope, and a custom one is a Java plugin built on Keycloak's SPI (Service Provider Interface). The mapper turns data — a user attribute, a role, a static value — into a specific token claim.

Built-in mappers are enough when the data already exists as a user attribute, a role or a group.

A custom Protocol Mapper SPI is needed in two cases:

- The claim requires data that physically does not live in Keycloak, say "current subscription tier" from an external billing service.
- The logic is more complex than declarative mapping.

Either way it carries a real ongoing maintenance cost: the extension has to be versioned against the Keycloak version it runs on.

```txt
                Where the line runs
┌─────────────────────────────────────────────────┐
│ Built-in mapper is enough when                  │
│   the data is already an attribute, a role      │
│   or a group                                    │
├─────────────────────────────────────────────────┤
│ A custom SPI mapper is needed when              │
│   the claim needs data that is not in Keycloak, │
│   or the logic is more than declarative mapping │
└─────────────────────────────────────────────────┘
```

Built-in mappers are enough when the data already exists as a user attribute, a role or a group.

A custom Protocol Mapper SPI (Service Provider Interface, written in Java) is needed in two cases:

- The claim requires data that physically does not live in Keycloak, say "current subscription tier" from an external billing service.
- The logic is more complex than declarative mapping.

Either way it carries a real ongoing maintenance cost: the extension has to be versioned against the Keycloak version it runs on.

```txt
                 What you sign up for
┌───────────────────────────────────────────────────┐
│ A custom mapper is a .jar running inside Keycloak │
│ Every Keycloak upgrade: rebuild it, re-verify it  │
│ That cost is permanent, not one-off               │
└───────────────────────────────────────────────────┘
```

---

## Group 5: NestJS Resource Server

**Why should authentication and authorization in NestJS be two separate Guards, not one?**

`AuthGuard('jwt')` answers "who is this": it validates the token and extracts the payload. `RolesGuard` answers "what are they allowed to do": it compares roles from the payload against the decorator's metadata.

The separation lets you reuse `RolesGuard` for **other** authentication methods — an API key for internal services, for example — without duplicating the role-checking logic. A fused Guard would have to be copied wholesale the moment a second authentication method appears.

```typescript
// authentication first, authorization second: two Guards, not one
@UseGuards(AuthGuard('jwt'), RolesGuard)
@Roles('invoice:write')
async create() { /* ... */ }
```

---

**When is simple role-based checking not enough, and what does Keycloak Authorization Services give you in that case?**

Simple role checks stop being enough when the rule depends on a **specific** resource instance. Ownership is the usual case: "only my documents". Context is the other one: time, or attributes beyond roles.

Authorization Services introduces a Resource + Scope + Policy + Permission model. The Resource Server acts as the Policy Enforcement Point. It asks Keycloak — the Policy Decision Point — over a UMA (User-Managed Access) ticket: "can this user use the `edit` scope on `Invoice:42`?"

```txt
            Who asks and who decides
┌──────────────────────────────────────────────┐
│ Resource Server = Policy Enforcement Point   │
└──────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────┐
│ UMA ticket: may this user use the scope edit │
│ on Invoice:42?                               │
└──────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────┐
│ Keycloak = Policy Decision Point             │
│ answers permit or deny                       │
└──────────────────────────────────────────────┘
```

The cost is a network round-trip plus the cognitive overhead of the model. For a plain "my records versus someone else's", checking `resource.ownerId === user.sub` directly in code is often enough, with no full UMA rollout.

---

**Who should refresh the access token — the client or the Resource Server, and what should the API return on an expired token?**

Always the client, because the client is the one holding the refresh token. The exception is a BFF (Backend-for-Frontend) architecture, where refreshing is a separate, deliberately designed role.

```txt
     Refreshing follows the refresh token
┌─────────────────────┬─────────────────────┐
│ party               │ holds               │
├─────────────────────┼─────────────────────┤
│ the client          │ the refresh token   │
├─────────────────────┼─────────────────────┤
│ the Resource Server │ nothing refreshable │
└─────────────────────┴─────────────────────┘
```

The Resource Server physically has no user refresh token, and should not try to get one. That would break the API's stateless model and turn it into a hidden auth client.

The correct reaction to an expired or invalid token is a 401 with a structured error body, such as `{"error": "token_expired"}`. What happens next — refresh or re-login — is entirely on the client side.

---

**Which architectural choice is safer in microservices: every service validates the JWT itself, or an API Gateway validates once?**

```txt
   A neighbouring pod can reach the service directly
┌───────────────────────────┬─────────────────────────┐
│ option                    │ what it requires        │
├───────────────────────────┼─────────────────────────┤
│ every service verifies    │ nothing extra           │
├───────────────────────────┼─────────────────────────┤
│ the Gateway verifies once │ mTLS Gateway to service │
└───────────────────────────┴─────────────────────────┘
```

Every service validating the token itself is the safer default. It matters most in Kubernetes environments, where network isolation is not guaranteed: a neighbouring pod in the same namespace can reach the service directly.

The Gateway option only pays off inside a deliberate zero-trust architecture. That means mTLS — mutual Transport Layer Security, where both sides present a certificate — between the Gateway and the services. "Saving one JWKS call" is not a reason on its own, since JWKS validation is already a cheap local operation.

---

## Group 6: React SPA, Token Storage, BFF

**Why is Authorization Code + PKCE the only correct flow for an SPA?**

```txt
        Why the flow has no client_secret
┌────────────────────────────────────────────────┐
│ A public client has nowhere to keep a secret   │
│ Every line of the bundle reaches the browser   │
├────────────────────────────────────────────────┤
│ PKCE instead of a secret                       │
│   the code_verifier stays in the client memory │
│   an intercepted code is useless without it    │
└────────────────────────────────────────────────┘
```

A React SPA is a public client. All the code runs in the user's browser, and any "secret" in the JS bundle is reachable through DevTools.

PKCE needs no `client_secret` at all. The `code_verifier` defends against authorization code interception without any secret. An intercepted `code` is useless without the original `code_verifier`, which never left the legitimate client's memory.

---

**What's the `silent-check-sso` problem in Safari, and how would you diagnose it?**

```txt
           The chain that breaks in Safari
┌────────────────────────────────────────────────────┐
│ The app page, on the app domain                    │
└────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────┐
│ An invisible iframe loads Keycloak                 │
│ with prompt=none                                   │
└────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────┐
│ The Keycloak session cookie is third-party here,   │
│ and Safari ITP drops it                            │
└────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────┐
│ Keycloak answers "no session", the app shows login │
└────────────────────────────────────────────────────┘
```

The mechanism first. An invisible iframe loads a Keycloak page with `prompt=none`. If the user has an active session, Keycloak hands back an authorization code silently, via `postMessage`.

That requires sending Keycloak's session cookie inside an iframe embedded on a domain that is foreign to Keycloak — a classic third-party cookie scenario. Safari ITP (Intelligent Tracking Prevention) blocks third-party cookies by default. So `silent-check-sso` quietly "fails to find" a genuinely active session. The app then shows a login screen to a user who is formally already logged in.

**How to diagnose it:**

- Reproduce it in Safari specifically, not in Chrome with default settings.
- Inspect the iframe's network requests: Keycloak's session cookie is physically not attached.

```txt
         What the diagnosis looks like
┌──────────────────────────────────────────────┐
│ Open the iframe request in the Network panel │
│   the Keycloak session cookie: not attached  │
│ Reproduce in Safari, not in a default Chrome │
└──────────────────────────────────────────────┘
```

**How to mitigate it:**

- Use `login-required` instead of `check-sso` if the app has no anonymous content.
- Move to the BFF pattern, which removes the problem architecturally.

**Secondary hypotheses worth checking and ruling out:**

- An access token TTL that is too short, combined with a bug in the frontend's `updateToken()` and retry logic.
- An SSO Session Idle timeout that genuinely expired through inactivity.

---

**Compare the trade-offs of storing a token in memory, in localStorage, and in an httpOnly cookie.**

```txt
     Three surfaces, not three grades of safety
┌─────────────────┬─────────────┬─────────────────┐
│ storage         │ read by XSS │ sent by itself  │
├─────────────────┼─────────────┼─────────────────┤
│ in memory       │ no          │ no              │
├─────────────────┼─────────────┼─────────────────┤
│ localStorage    │ yes         │ no              │
├─────────────────┼─────────────┼─────────────────┤
│ httpOnly cookie │ no          │ yes, hence CSRF │
└─────────────────┴─────────────┴─────────────────┘
```

Three options, three different attack surfaces:

- **In memory** — unreachable by XSS (cross-site scripting), but lost on a page refresh, so it needs a silent refresh.
- **localStorage** — reachable by **any** JS, including code injected via XSS. It is the only option that buys nothing in return, which is exactly why the industry treats it as off-limits for tokens.
- **httpOnly cookie** — unreachable by XSS, but the browser sends it automatically on every request to the domain, including requests triggered by a malicious page. That is CSRF (Cross-Site Request Forgery), so `SameSite`, `Secure` and precise CORS (Cross-Origin Resource Sharing) become mandatory.

This is not a "secure versus insecure" choice. It is a choice of which attack vector you accept as a risk.

---

**Explain the BFF pattern, and when it's justified compared to a public client in the browser.**

```txt
     Where each token lives under a BFF
┌─────────────────────────────────────────┐
│ Browser                                 │
│ holds only the app's own session cookie │
└─────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│ BFF, a confidential client              │
│ holds the access, refresh and ID token  │
└─────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│ Keycloak and the API                    │
│ see the real token, never the browser   │
└─────────────────────────────────────────┘
```

A BFF removes the problem architecturally: the browser never sees the access, refresh or ID token — only the app's own first-party session cookie.

The BFF is a confidential client. It runs the Authorization Code + PKCE exchange itself, on the server. It stores the tokens in Redis or a database, keyed by session id, and proxies API requests carrying the real token.

**Pros:**

- XSS physically cannot steal the token, because there is nothing to read.
- The third-party cookie problem disappears architecturally.

**Cons:**

- An extra network hop.
- An extra component that has to run on a server.
- The BFF itself becomes a critical attack target.

```txt
       The ledger of the pattern
┌──────┬───────────────────────────────┐
│ BFF  │ what changes                  │
├──────┼───────────────────────────────┤
│ gain │ XSS has nothing to read       │
├──────┼───────────────────────────────┤
│ gain │ no third-party cookie left    │
├──────┼───────────────────────────────┤
│ cost │ one more hop, one more server │
└──────┴───────────────────────────────┘
```

It is justified for fintech, healthcare and enterprise apps with high security stakes. For an MVP (minimum viable product) the classic public client is still adequate, and faster to build.

---

## Group 7: Attacks and Defenses

**Why does PKCE matter even for confidential clients, which already have a client_secret?**

`client_secret` protects against **someone else** impersonating the client at the code→token exchange step. It does not protect against a different scenario.

```txt
            Two different questions
┌───────────────┬──────────────────────────────┐
│ the check     │ what it proves               │
├───────────────┼──────────────────────────────┤
│ client_secret │ the caller is this client    │
├───────────────┼──────────────────────────────┤
│ code_verifier │ the caller started this flow │
└───────────────┴──────────────────────────────┘
```

An attacker who intercepted a `code` meant for this client can try to exchange it first. They use that **same** confidential client, racing the legitimate user.

PKCE closes exactly this scenario, whatever the client type. That is why the modern OAuth 2.0 Security BCP (Best Current Practice) recommends it for all clients.

---

**What's the difference between `state` and `nonce`, and why are both needed?**

```txt
                  Transport versus content
┌───────────┬─────────────────────────┬───────────────────┐
│ parameter │ lives in                │ stops             │
├───────────┼─────────────────────────┼───────────────────┤
│ state     │ the redirect URL        │ Login CSRF        │
├───────────┼─────────────────────────┼───────────────────┤
│ nonce     │ a claim in the ID Token │ replay of a token │
└───────────┴─────────────────────────┴───────────────────┘
```

`state` protects the redirect exchange itself from CSRF and replay. The client generates a random value before redirecting, stores it locally, and verifies it on the callback. This prevents Login CSRF, which ties the victim's session to the attacker's account.

`nonce` protects the content of the ID Token from replay. Keycloak embeds it **inside** the token itself, as a claim, and the client checks it on receipt. This prevents an old, not-yet-expired ID Token from being presented a second time.

Mnemonic: `state` is transport, `nonce` is content. They do not substitute for each other.

```txt
      Sent together, returned apart
┌────────────────────────────────────────┐
│ GET /authorize?...&state=xyz&nonce=abc │
│   state comes back in the callback URL │
│   nonce comes back inside the ID Token │
└────────────────────────────────────────┘
```

---

**Describe the mechanics of a JWT algorithm confusion attack, and how you'd defend against it.**

There are two variants of the attack.

**The "alg: none" attack.** The attacker rewrites the token header to `{"alg": "none"}` and drops the signature. A vulnerable library that trusts the `alg` value from the token itself "verifies" an empty signature and accepts the token.

```txt
              Variant one, in three lines
┌──────────────────────────────────────────────────────┐
│ header rewritten to {"alg": "none"}                  │
│ signature dropped entirely                           │
│ a library that trusts the token's own alg accepts it │
└──────────────────────────────────────────────────────┘
```

**The RS256/HS256 confusion attack.** RS256 is a signature made with RSA (an asymmetric algorithm — sign with a private key, verify with the public one). HS256 is a signature made with one shared secret, using HMAC — a hash-based message authentication code.

The attacker rewrites the header to `{"alg": "HS256"}` and signs the token with HMAC, using Keycloak's **public** RSA key as the secret. That key is openly available through the JWKS. If the library does not strictly require the expected algorithm, and instead adapts to whatever the token claims, the check passes.

The defence is the same in both cases. The list of accepted algorithms is **always** hardcoded in the Resource Server's config (`algorithms: ['RS256']`). It is never derived from a value inside the token.

```typescript
// the accepted algorithm is config, never the token's own alg header
new JwtStrategy({ algorithms: ['RS256'], secretOrKeyProvider });
```

---

**Why is refresh token rotation a breach-detection mechanism, not just hygiene?**

Every exchange of a refresh token for a new pair revokes the old one. That turns a stolen token into a detectable event.

Say a token was stolen through XSS, before the legitimate client used it. Two orders are possible:

- **The attacker uses it first.** The legitimate app then tries to use its own, already revoked, token and gets an error. That error is the compromise signal.
- **The legitimate client uses it first.** The attacker's later attempt presents an already revoked token, and Keycloak sees the reuse.

```txt
Every exchange invalidates the previous token
┌────────────────────────────────────────────┐
│ refresh #1 spent   →  new pair, #1 revoked │
│ refresh #2 spent   →  new pair, #2 revoked │
│ a revoked one used again  →  a reuse event │
└────────────────────────────────────────────┘
```

The correct reaction is to revoke the **entire** token chain for that session, not just to reject one request. There is no reliable way to tell which copy of the token is the right one.

---

## Group 8: Architecture and Scenarios

**What's the trade-off between realm-per-tenant and a shared realm with groups for a multi-tenant SaaS?**

For a multi-tenant SaaS — software as a service — the trade-off is isolation against operational load.

```txt
              Isolation against operational load
┌──────────────────┬──────────────────────┬──────────────────┐
│ model            │ isolation            │ operational load │
├──────────────────┼──────────────────────┼──────────────────┤
│ realm per tenant │ full, out of the box │ grows per tenant │
├──────────────────┼──────────────────────┼──────────────────┤
│ shared realm     │ on the application   │ flat             │
└──────────────────┴──────────────────────┴──────────────────┘
```

**Realm-per-tenant** gives full isolation out of the box: its own password policy, its own theme, its own Identity Providers. The price is operational load that grows linearly with the number of tenants. Realm-as-code config, monitoring and upgrades all multiply by the number of realms.

**A shared realm with groups** (`/tenants/acme-corp` plus a `tenant_id` claim via a Protocol Mapper) does not grow that way. In exchange, data isolation falls on the application: the Resource Server **must** filter by `tenant_id` on every request. A mistake here is a cross-tenant data leak, and that is no longer a Keycloak problem.

In practice: realm-per-tenant for B2B (business-to-business) enterprise with tens to hundreds of large customers and strict compliance requirements. A shared realm for self-serve with thousands of small tenants.

```typescript
// shared realm: the Resource Server filters on every request
const rows = await repo.find({
  where: { tenantId: user.tenant_id },
});
```

---

**Scenario: users on Safari occasionally get silently logged out, with nothing resembling a logout action on their part. How would you diagnose this?**

The first hypothesis is not logout at all. It is a failure of the session **check**.

If the app uses `onLoad: 'check-sso'` in `keycloak-js`, `silent-check-sso` relies on an iframe embedded from the app's domain that reads Keycloak's session cookie. That is a third-party cookie scenario, and Safari ITP blocks it by default.

```txt
         Read the symptom as a failed check
┌─────────────────────────────────────────────────┐
│ A complaint: "logged out on its own", on Safari │
└─────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────┐
│ First hypothesis: not a logout at all           │
└─────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────┐
│ check-sso runs in an iframe that needs          │
│ the Keycloak cookie as a third-party cookie     │
└─────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────┐
│ Safari ITP blocks it, the app looks logged out  │
└─────────────────────────────────────────────────┘
```

**How to verify.** Reproduce it in Safari with an active Keycloak session in a sibling tab. The `check-sso` call will not find the session even though it is genuinely alive, and the app shows an unauthenticated state.

If that is confirmed, there are three fixes:

1. Accept it, and make sure the UX (user experience) for that case is decent — a visible "Log in" button, not a blank screen.
2. Switch to `login-required` if the app has no anonymous content.
3. Move to the BFF pattern, where identification goes through the app's own first-party cookie. The third-party cookie problem then disappears entirely.

**Secondary hypotheses worth checking and ruling out:**

- An access token TTL that is too short, combined with a bug in the frontend's `updateToken()` and retry logic.
- An SSO Session Idle timeout that genuinely expired after a real period of inactivity.

```txt
            Three fixes, three prices
┌────────────────┬──────────────────────────────┐
│ fix            │ what it asks for             │
├────────────────┼──────────────────────────────┤
│ accept it      │ a visible Log in button      │
├────────────────┼──────────────────────────────┤
│ login-required │ no anonymous content         │
├────────────────┼──────────────────────────────┤
│ BFF            │ a first-party cookie instead │
└────────────────┴──────────────────────────────┘
```

---

**Design the auth architecture for a new multi-tenant SaaS on Keycloak — what decisions would you make, and why?**

Five decisions carry this design: multi-tenancy, token storage, authorization, operations and logout.

**1. Multi-tenancy.** A few large enterprise customers → realm-per-tenant. Each of them wants its own Identity Provider, its own login branding and its own compliance story, and that is worth the growing operational load.

```txt
          The fork the first decision takes
┌─────────────────────────┬──────────────────────────┐
│ customer shape          │ the choice               │
├─────────────────────────┼──────────────────────────┤
│ a few large enterprises │ realm per tenant         │
├─────────────────────────┼──────────────────────────┤
│ many small self-serve   │ shared realm + tenant_id │
└─────────────────────────┴──────────────────────────┘
```

A self-serve model with many small tenants → one shared realm, isolation by group, and a `tenant_id` claim in the token. The Resource Server then filters by `tenant_id` on **every** request.

**2. Token storage.** Start with the BFF pattern, not with a public client in the browser. B2B SaaS with corporate customers has real security requirements. The BFF removes a whole class of problems architecturally. An XSS attack has no token to steal, and the third-party cookie fragility of `silent-check-sso` never arises.

**3. Authorization.** Realm and client roles for the static rules. Keycloak Authorization Services only where ownership-based or contextual authorization is genuinely needed — not by default.

**4. Operations.** Deploy Keycloak from day one as an HA (high availability) cluster with a real database, PostgreSQL. Keep the realm as code — `keycloak-config-cli` or Terraform — so environments are reproducible, instead of clicking through the console.

```txt
   Why the last decision is back-channel
┌───────────────┬──────────────────────────┐
│ logout        │ depends on               │
├───────────────┼──────────────────────────┤
│ front-channel │ the browser staying open │
├───────────────┼──────────────────────────┤
│ back-channel  │ a server-to-server call  │
└───────────────┴──────────────────────────┘
```

**5. Logout.** Back-channel logout rather than front-channel. Logout then propagates across the several clients sharing an SSO session without depending on the state of the user's browser.
