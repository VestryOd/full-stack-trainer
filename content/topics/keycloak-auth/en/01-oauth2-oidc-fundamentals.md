# OAuth2 / OIDC — Protocol Fundamentals

## Why you can't write secure auth code without this

A developer who can drop `keycloak-js` into a React app and watch the login work, but can't explain why the request includes a `code_challenge`, or why the backend shouldn't "refresh the token" itself, is working from a tutorial, not from an understanding of the protocol. That's fine as long as everything follows the happy path — it breaks unpredictably the moment something non-standard shows up: a mobile app, a service with no user behind it, a redirect that looks suspiciously like a legitimate one.

Everything in the rest of this topic — a specific Keycloak configuration, a specific NestJS guard, a specific `keycloak-js` wiring in React — is a concrete implementation of the roles and flows described here. Once you actually understand this article, most of the "weird" Keycloak behavior you'll run into in production stops being weird — you can see exactly which role is obligated to do what by spec.

## Protocol roles — the vocabulary everything else depends on

OAuth2 (RFC 6749) doesn't describe "how to log in to a site" — it describes a more general problem: how a **Client** gets limited access to a resource owned by a **Resource Owner**, without ever seeing the owner's password. The spec fixes four roles:

```txt
┌──────────────────┐                  ┌──────────────────────┐
│ Resource Owner   │ login + consent  │ Authorization Server │
│ (the user, owner │◄────────────────►│ (Keycloak: issues    │
│ of the data)     │                  │ and signs tokens)    │
└──────────────────┘                  └──────────────────────┘
                                        │ issues a token
                                        │
                                        │
┌───────────────────────┐                     ┌────────────────────┐
│ Client                │◄──────────────┘     │ Resource Server    │
│ (React SPA, mobile    │ presents the token  │ (NestJS API,       │
│ app, backend service) │────────────────────►│ owns the protected │
└───────────────────────┘                     │ resource)          │
                                              └────────────────────┘
```

- **Resource Owner** — the user who owns the data (or, in a service-to-service scenario with no human involved, the resource itself).
- **Client** — the application that WANTS access to the resource on behalf of the Resource Owner. This does NOT have to be a server: a React SPA, a mobile app, and a backend service are all "clients" in OAuth2 terms — they just differ in their properties (see public vs confidential in [Keycloak Core Concepts]).
- **Authorization Server** (Keycloak, in our stack) — the service that authenticates the Resource Owner, obtains consent, and issues tokens to the Client. It's the only role that ever sees the user's password and owns the token-issuing logic.
- **Resource Server** — the API that owns the protected data (the NestJS backend, in our stack) and decides "let in / reject" based on the presented token.

An important consequence that's easy to miss: **Client and Resource Server are different roles even when the same team writes both**. In a "React SPA + NestJS API" setup, the NestJS backend is the Resource Server. But that same NestJS backend, when it calls another internal service on its own behalf (no user involved), is now acting as a Client (see Client Credentials Grant below). Confusing "who is who" in a specific architecture is behind half the wrong decisions about where to store a token and who should refresh it.

## "OAuth2 is authorization, not authentication" — what this actually means

This is the most-quoted line in this space, and it's worth treating as a technical constraint of the spec, not a slogan.

OAuth2 answers the question **"what is this client allowed to do?"** — it issues an **access token** that tells the Resource Server "whoever holds this token has these scopes." OAuth2 by itself **does not guarantee** the Client anything about who the resource owner is: the spec doesn't define a standardized way to learn the identity of the user. Historically this led developers to **abuse the access token as proof of identity** ("if I have a valid access token, I must know who's logged in") — this is the well-known ["OAuth as authentication" antipattern], which OpenID Connect fixed in 2014.

```txt
Plain OAuth2 answers:
  "Can whoever holds this token call GET /api/orders?"
                        ↓
                       YES / NO

Plain OAuth2 does NOT directly answer:
  "Who exactly is logged in, and what's their name?"
```

**OpenID Connect (OIDC)** is a thin, standardized identity layer built ON TOP of OAuth2 (same endpoints, same grant types, same redirect flow). OIDC adds exactly three things that were missing:

1. **ID Token** — a new kind of token (always a JWT — that's an OIDC requirement, unlike the access token, whose format OAuth2 never dictates) that carries claims about the user's identity: `sub` (a unique identifier), `email`, `name`, authentication time, etc. The ID Token is meant for the **client** — it must be verified and **must never be sent to other APIs** as if it were an access token.
2. **UserInfo endpoint** (`/protocol/openid-connect/userinfo` in Keycloak) — a standardized REST endpoint the client can call with an access token to get the user's current profile (useful when the ID Token is already stale but the profile might have changed).
3. **Discovery document** (`/.well-known/openid-configuration`) — a JSON document the Authorization Server publishes, describing ALL of its endpoints and capabilities, so the client never has to hardcode URLs.

```bash
curl https://keycloak.example.com/realms/myrealm/.well-known/openid-configuration
```

```json
{
  "issuer": "https://keycloak.example.com/realms/myrealm",
  "authorization_endpoint": "https://keycloak.example.com/realms/myrealm/protocol/openid-connect/auth",
  "token_endpoint": "https://keycloak.example.com/realms/myrealm/protocol/openid-connect/token",
  "userinfo_endpoint": "https://keycloak.example.com/realms/myrealm/protocol/openid-connect/userinfo",
  "jwks_uri": "https://keycloak.example.com/realms/myrealm/protocol/openid-connect/certs",
  "end_session_endpoint": "https://keycloak.example.com/realms/myrealm/protocol/openid-connect/logout",
  "grant_types_supported": ["authorization_code", "client_credentials", "refresh_token", "urn:ietf:params:oauth:grant-type:device_code"],
  "response_types_supported": ["code", "none"],
  "code_challenge_methods_supported": ["plain", "S256"]
}
```

Practical consequence for real engineering work: **any decent library (keycloak-js, oidc-client-ts, passport-jwt with an OIDC strategy) should be configured with an issuer URL and pull this document itself**, rather than hardcoding paths to every endpoint. That's the difference between a config that "works on my dev box" and one that survives a Keycloak upgrade, where paths under `/protocol/openid-connect/*` could in theory change.

## Front-channel vs back-channel — a recurring concept in every article ahead

This distinction isn't a detail of one specific flow — it's a lens you should use to analyze ANY data exchange in OAuth2/OIDC:

```txt
Front-channel:
  Data travels through the user's BROWSER — redirects, query params,
  the URL fragment (#), postMessage. Visible in the address bar,
  potentially visible to third-party code on the page, can leak
  through browser history, the Referer header, proxy logs.
  Example: a redirect to /authorize with parameters in the query string.

Back-channel:
  Data travels SERVER-TO-SERVER, directly, bypassing the user's
  browser entirely. A TLS connection between the Client (or Resource
  Server) and the Authorization Server. Never visible to the user,
  never touches browser history.
  Example: exchanging an authorization code for tokens — a direct
  POST to /token from the backend (or, for a public client, straight
  from JS code in the browser, but NOT through a redirect).
```

Why it matters: **anything that needs to stay secret (a client secret, the tokens themselves) should travel over the back-channel wherever possible**. This is exactly why the Implicit Grant (passing the access token through the URL fragment — front-channel) is considered insecure (more below), while the Authorization Code Grant (only a one-time-use `code` over the front-channel, with the actual token exchange over the back-channel) became the standard. This pair of terms will keep showing up without redefinition from here on — if a flow passes something through a redirect, that's front-channel; if it's a direct HTTP request between servers, that's back-channel.

## Access Token, ID Token, Refresh Token — three artifacts, three purposes

This is the #1 source of confusion for developers new to this space: all three are "some kind of token" issued in the same response, and it's tempting to start treating them interchangeably. That's a mistake with real consequences.

```txt
┌──────────────┬──────────────────────┬────────────────────┬──────────────────────────┐
│              │ Access Token         │ ID Token           │ Refresh Token            │
├──────────────┼──────────────────────┼────────────────────┼──────────────────────────┤
│ Intended for │ Resource Server      │ Client (only!)     │ Authorization Server     │
│              │ (the API)            │ never send it to   │ (only it accepts it —    │
│              │                      │ another API        │ only at /token)          │
├──────────────┼──────────────────────┼────────────────────┼──────────────────────────┤
│ Format       │ Opaque by OAuth2     │ Always a JWT       │ Opaque by spec (in       │
│              │ spec; Keycloak makes │ (an OIDC           │ practice Keycloak also   │
│              │ it a JWT in practice │ requirement)       │ makes it a JWT, but      │
│              │                      │                    │ that's an implementation │
│              │                      │                    │ detail)                  │
├──────────────┼──────────────────────┼────────────────────┼──────────────────────────┤
│ Contains     │ scope, roles,        │ Identity claims:   │ Usually the minimum      │
│              │ permissions —        │ sub, email, name,  │ data the Authorization   │
│              │ "what's allowed"     │ auth_time —        │ Server needs to find     │
│              │                      │ "who this is"      │ the session              │
├──────────────┼──────────────────────┼────────────────────┼──────────────────────────┤
│ TTL          │ Short (minutes)      │ Same as access     │ Long (hours/days) or     │
│              │                      │ token              │ until logout             │
├──────────────┼──────────────────────┼────────────────────┼──────────────────────────┤
│ Used by      │ Resource server, on  │ Client app — to    │ Client — ONLY to get a   │
│              │ every API call       │ show "Hi, Name" in │ new token pair from the  │
│              │ (Authorization:      │ the UI             │ /token endpoint          │
│              │ Bearer <token>)      │                    │                          │
└──────────────┴──────────────────────┴────────────────────┴──────────────────────────┘
```

The physical format of the access token and validation details (JWKS, `kid`, local validation vs introspection) are covered separately in [Tokens, Sessions, and Validation] — the point here is the semantic boundary between the three artifacts, not the wire format. JWT's general structure (header.payload.signature) is already covered in [JWT, Access Token and Refresh Token] — we don't repeat that here; the focus of this article is each token's protocol role, not its physical shape.

A common real-world mistake: a React app decodes the ID Token and sends it as `Authorization: Bearer <idToken>` on requests to its own NestJS API. This can technically even work, if the backend is careless enough to accept any JWT from the same issuer — but it violates the contract: the ID Token isn't meant for a Resource Server, it has a different `aud` (audience — the recipient the token declares itself for), and nothing guarantees it even carries the claims authorization needs (roles, scope).

## Scopes vs Claims — the pair everyone mixes up

- **Scope** — a request for access. The client specifies scopes in the `/authorize` request (`scope=openid profile email`), effectively saying "I need access to this category of data/actions." Scope is what the client asks FOR.
- **Claim** — a concrete fact about the user or the token, inside the issued JWT (`email`, `sub`, `realm_access.roles`). A claim is what the client actually GOT.

```txt
Requested scope       →  Authorization Server decides which claims to grant
"scope=openid profile email"
                       →  ID Token contains: sub, name, preferred_username,
                          email, email_verified ...
```

The mapping between scopes and the actual set of claims in Keycloak is configured through **Client Scopes** and **Protocol Mappers** — a Keycloak-specific mechanism covered in [Keycloak Core Concepts]. The protocol-level principle to take away here: scope is the request, claim is the result, and one scope usually "bundles" several claims at once (the `profile` scope isn't a single claim — it's a group: `name`, `family_name`, `given_name`, `picture`, and so on).

## Grant Types — how a client actually gets a token

A grant type (sometimes called a "flow") is a concrete protocol scenario: which messages travel between the Client, the Authorization Server, and (sometimes) the user's browser, ending with the client holding tokens. Picking a grant type isn't a matter of taste — it's a direct consequence of what the client actually IS: does it have a user in front of a screen, can it safely hold a secret, what kind of input interface does it have.

### Authorization Code + PKCE — the modern default

This is the only correct choice for an interactive user login today — for both confidential clients (a backend with a client secret) and, more importantly, public clients (SPAs, mobile apps), which physically cannot hold a secret.

**PKCE** (Proof Key for Code Exchange, pronounced "pixy," RFC 7636) was originally designed for mobile apps, but today Keycloak and most modern guidance recommend it for ALL clients, confidential ones included — because it defends against a specific class of attack (authorization code interception) that's relevant regardless of client type, not "the absence of a secret." The full PKCE mechanism (what `code_verifier`/`code_challenge` actually are, why they defend against interception) is covered in detail in [Security Hardening and Attack Vectors] — here we're fixing the protocol sequence.

```txt
Participants: User's browser, React SPA (Client), Keycloak (AS), NestJS API (RS)

1. [Client, locally]      Generate a random code_verifier,
                            compute code_challenge = SHA256(code_verifier)

2. [front-channel]        The browser is redirected to:
                            GET /authorize?
                              response_type=code
                              &client_id=spa-client
                              &redirect_uri=https://app.example.com/callback
                              &scope=openid profile email
                              &state=<random value — CSRF protection>
                              &code_challenge=<computed in step 1>
                              &code_challenge_method=S256

3. [on Keycloak's side]   The user sees Keycloak's login form (NOT the
                            client's own form!), enters their credentials,
                            Keycloak authenticates them and stores the
                            code_challenge alongside the authorization code

4. [front-channel]        Keycloak redirects the browser back:
                            GET https://app.example.com/callback?
                              code=<one-time-use authorization code>
                              &state=<the same value sent in step 2>

5. [Client]                Verify state matches what was sent
                            (protects against CSRF/replay on the redirect)

6. [back-channel]          Client makes a direct POST (not through
                            a browser redirect) to /token:
                              grant_type=authorization_code
                              &code=<code from step 4>
                              &redirect_uri=<same one as in step 2>
                              &code_verifier=<original from step 1>
                              &client_id=spa-client

7. [Keycloak, back-channel] Checks: SHA256(code_verifier) ==
                            code_challenge stored in step 3.
                            If it matches → issues access_token,
                            id_token, refresh_token in the JSON response
```

A detail worth stating explicitly: the `code` from step 4 is **useless by itself without the `code_verifier`** — even if an attacker intercepts it (say, through a proxy log leak, or a malicious app registered on the same custom URL scheme on a mobile OS), they can't exchange it for tokens, because they don't know the `code_verifier`, which never left the legitimate client's memory.

### Client Credentials Grant — service-to-service, no user at all

Used when it's not a user requesting a token, but a service itself — for example, NestJS service A calls NestJS service B over an internal API, and there's no "logged-in human" anywhere in this interaction.

```txt
Participants: Service A (Client, confidential), Keycloak (AS)

1. [back-channel, direct, no browser involved]
   POST /realms/myrealm/protocol/openid-connect/token
     grant_type=client_credentials
     &client_id=service-a
     &client_secret=<secret known only to Service A and Keycloak>

2. [Keycloak]
   Verifies client_id + client_secret → issues an access_token
   (no id_token — there's no one to identify here; an ID Token
   is never issued in this grant type)
```

```bash
curl -X POST https://keycloak.example.com/realms/myrealm/protocol/openid-connect/token \
  -d "grant_type=client_credentials" \
  -d "client_id=service-a" \
  -d "client_secret=$SERVICE_A_SECRET"
```

The key difference from Authorization Code: there's no front-channel step at all — no browser, no user, the whole exchange is a single back-channel HTTP call. Only a confidential client (one able to safely store a `client_secret` — a server, not a browser) can do this.

### Device Code Grant — limited-input devices

A niche but real scenario: an app running on a device with no convenient keyboard/browser (a smart TV, a console, a CLI tool) where typing a username/password directly is awkward.

```txt
1. [Device → AS, back-channel]
   POST /auth/device — the device requests a "device code"
   ← gets back: device_code (for the device itself),
                user_code (short, for a human — "ABCD-1234"),
                verification_uri ("https://keycloak.example.com/device")

2. [Device]  Shows the user on screen:
   "Go to keycloak.example.com/device and enter code ABCD-1234"

3. [User, on a DIFFERENT device — phone/laptop]
   Opens verification_uri, logs in normally (an Authorization
   Code-like flow happens internally), enters the user_code, confirms

4. [Device, meanwhile]  Polls /token with the device_code every N seconds:
   grant_type=urn:ietf:params:oauth:grant-type:device_code
   Until the user confirms — Keycloak replies "authorization_pending".
   Once confirmed — tokens are returned.
```

The core idea worth calling out: the device with the poor input interface never sees the username/password at all — all authentication happens on a separate, convenient device, and the original device just gets the result via polling.

### Why Resource Owner Password Credentials (ROPC) is deprecated

ROPC (the `password` grant) looks tempting: the client collects the username/password in its own form and exchanges them for a token in one request, no redirects involved.

```txt
POST /token
  grant_type=password
  &username=user@example.com
  &password=<the user's password>
  &client_id=legacy-client
```

The problem isn't that "it's old" — it's specific architectural losses:

- **The client physically holds the user's password in memory.** This directly contradicts OAuth2's founding goal — "grant access without exposing the password to a third party." If the client (or a library it uses) has a vulnerability, the password itself is compromised, not just a token.
- **MFA/step-up becomes hard to bolt on.** The Authorization Server never sees or controls the login form — so it can't insert an SMS code, a WebAuthn prompt, a redirect to an external IdP (see Identity Brokering in [Keycloak Core Concepts]) — all of that second-factor logic would have to be reinvented inside every client.
- **SSO becomes impossible.** The user logs in again separately in EVERY client — because authentication happens inside each app's own form, not on a shared Authorization Server.

Keycloak disables Direct Access Grants (Keycloak's internal name for ROPC) by default for new clients — that's a deliberate decision, not a forgotten checkbox.

### Why Implicit Grant is deprecated

The Implicit Grant (`response_type=token`) was designed for SPAs before CORS and PKCE were widely available — the idea was to hand back the access token directly in the redirect, skipping a separate back-channel exchange, because browsers back then couldn't reliably make a cross-origin POST to swap a code for a token.

```txt
GET /authorize?response_type=token&client_id=spa&redirect_uri=...
                        ↓
Redirect: https://app.example.com/callback#access_token=eyJhbGci...&expires_in=300
                                            ▲
                                    token in the URL FRAGMENT
```

Concrete, not abstract, reasons this is considered insecure today (the OAuth 2.0 Security Best Current Practice explicitly recommends against Implicit):

- **The token travels over the front-channel in the clear** — the whole point of splitting "code over front-channel, token over back-channel" in the Authorization Code Grant disappears: the access token itself ends up in the address bar, in browser history, in the Referer header when navigating away to an external link from that page, in the logs of any intermediate proxy that logs full URLs.
- **No client verification at token issuance** — in the Authorization Code Grant, the code→token exchange in step 6 (back-channel) gives the Authorization Server one more chance to confirm the request comes from a legitimate client (via PKCE's `code_verifier`, or a client secret for confidential clients). In Implicit, the token is handed out right on the redirect — with no such extra check.
- **The token can't be silently refreshed** — Implicit doesn't provide a refresh token (that would be unsafe too — a refresh token over the front-channel), so the only way to extend a session was an invisible iframe redirect with `prompt=none`, which is inherently fragile (see the silent-check-sso problem in [React SPA Integration]).

Today both Keycloak and every modern library (`keycloak-js`, `oidc-client-ts`) default to Authorization Code + PKCE even for a pure browser-only SPA — Implicit survives only as historical context, useful for understanding WHY the modern flow is shaped the way it is.

## Tying it together

```txt
[OAuth2 Roles]                →  Client / Resource Owner / Authorization
                                  Server / Resource Server — the vocabulary
                                  for every reasoning that follows

[OIDC on top of OAuth2]        →  ID Token + UserInfo + Discovery Document
                                  add standardized identity

[Front-channel/back-channel]   →  the recurring lens: what's safe to hand
                                  to a browser redirect vs what only ever
                                  travels over a direct server connection

[Access / ID / Refresh]        →  three artifacts with different
                                  recipients and different purposes —
                                  mixing them up is an architectural
                                  mistake, not a minor imprecision

[Grant Types]                  →  the choice follows from what kind of
                                  client you have: a user with a browser
                                  (Auth Code + PKCE), a service with no
                                  user (Client Credentials), a device
                                  with poor input (Device Code)
```

The next article — [Keycloak Core Concepts] — moves from protocol theory to how Keycloak physically models Realms, Clients, roles, and claims, so everything described here becomes something you can actually configure.

## Common interview traps

- **"OAuth2 and OIDC are the same thing, just different names"** — wrong. OIDC is an identity layer built ON TOP of OAuth2, reusing the same mechanics (same endpoints, same grant types), but adding something plain OAuth2 doesn't and can't have by spec: an ID Token, a UserInfo endpoint, a standardized way to find out who the user is.

- **"The access token tells you who's logged in"** — no, that's the ID Token's job. The access token says WHAT the token holder is allowed to do (scope/roles), not WHO they are. Confusing the two means using the wrong artifact for the job, not a minor terminology slip.

- **"PKCE only matters because SPAs don't have a client secret"** — an incomplete answer. PKCE defends against authorization code interception regardless of whether a secret exists, which is why modern guidance (and Keycloak) recommends PKCE even for confidential clients. A good answer explains the MECHANISM (code_verifier/code_challenge), not just "for public clients."

- **"Implicit Grant is deprecated because it's an old spec version"** — doesn't explain WHY. The real answer: the token travels over the front-channel (the URL fragment) — in the clear, in browser history, in the Referer header, in proxy logs — with no additional client verification at issuance, unlike Authorization Code, where the code→token exchange happens over the back-channel with a PKCE check.

- **"The refresh token has to be a JWT too, just like the access token"** — no, the spec dictates nothing about the format of either the access or the refresh token (except the ID Token, which must be a JWT per OIDC). Keycloak makes the access token a JWT by default for convenient local validation, but that's an implementation detail, not a protocol requirement.

- **"Client Credentials Grant is basically logging in as a service account"** — not quite: Client Credentials has no user, no ID Token, no notion of identity at all — it's the client itself being authorized as a subject, not impersonating a human. Blurring this leads to bad service-to-service authorization designs (e.g., trying to pull a specific user's roles out of a client-credentials token, where there's nowhere for them to come from).
