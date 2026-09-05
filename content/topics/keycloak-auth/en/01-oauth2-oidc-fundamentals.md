# OAuth2 / OIDC — Protocol Fundamentals

This article fixes the vocabulary the whole topic runs on: four OAuth2 roles, three kinds of token, and the grant types that issue them. It also explains what OpenID Connect (OIDC) adds on top of OAuth2. Everything later in this topic — a Keycloak configuration, a NestJS guard, a `keycloak-js` wiring in React — is one concrete implementation of what you read here.

## Protocol roles — the vocabulary everything else depends on

OAuth2 is defined by RFC 6749, one of the numbered Request for Comments documents that define internet protocols. It does not describe how to log in to a site. It describes a general problem: how a **Client** gets limited access to a resource owned by a **Resource Owner**, without ever seeing the owner's password. The spec fixes four roles:

```txt
┌─────────────────────────────────────────────────┐
│ Resource Owner — the user who owns the data     │
└─────────────────────────────────────────────────┘
                         │  logs in and gives consent
                         ▼
┌─────────────────────────────────────────────────┐
│ Authorization Server (Keycloak) —               │
│ authenticates the user, issues and signs tokens │
└─────────────────────────────────────────────────┘
                         │  issues a token
                         ▼
┌─────────────────────────────────────────────────┐
│ Client — React SPA, mobile app, backend service │
└─────────────────────────────────────────────────┘
                         │  presents the token
                         ▼
┌─────────────────────────────────────────────────┐
│ Resource Server — NestJS API that owns          │
│ the protected data                              │
└─────────────────────────────────────────────────┘
```

- **Resource Owner** — the user who owns the data (or, in a service-to-service scenario with no human involved, the resource itself).
- **Client** — the application that **wants** access to the resource on behalf of the Resource Owner. A client does **not** have to be a server. A React SPA (single-page application), a mobile app and a backend service are all clients in OAuth2 terms. They differ only in their properties — see public vs confidential in [Keycloak Core Concepts](./02-keycloak-core-concepts.md).
- **Authorization Server** (Keycloak, in our stack) — the service that authenticates the Resource Owner, obtains consent, and issues tokens to the Client. It's the only role that ever sees the user's password and owns the token-issuing logic.
- **Resource Server** — the API that owns the protected data (the NestJS backend, in our stack) and decides "let in / reject" based on the presented token.

An important consequence that's easy to miss: **Client and Resource Server are different roles even when the same team writes both**. In a "React SPA + NestJS API" setup, the NestJS backend is the Resource Server.

But that same backend becomes a Client when it calls another internal service on its own behalf, with no user involved. That case is the Client Credentials Grant, described below. Confusing "who is who" in a specific architecture is behind half the wrong decisions about where to store a token and who should refresh it.

## "OAuth2 is authorization, not authentication" — what this actually means

OAuth2 answers one question: **what is this client allowed to do?** It issues an **access token** that tells the Resource Server which scopes the holder of that token has. OAuth2 by itself **does not guarantee** the Client anything about who the resource owner is. The spec defines no standard way to learn the user's identity. The most-quoted line in this space is a technical constraint, not a slogan.

Historically this led developers to **abuse the access token as proof of identity**. The reasoning was: if I hold a valid access token, I must know who is logged in. That is the well-known "OAuth as authentication" antipattern, which OpenID Connect fixed in 2014.

```txt
Plain OAuth2 answers:
  "Can whoever holds this token call GET /api/orders?"
                        ↓
                       YES / NO

Plain OAuth2 does not directly answer:
  "Who exactly is logged in, and what's their name?"
```

**OpenID Connect (OIDC)** is a thin, standardized identity layer built **on top of** OAuth2: the same endpoints, the same grant types, the same redirect flow. OIDC adds exactly three things that plain OAuth2 was missing:

1. **ID Token** — a token that carries claims about the user's identity: `sub` (a unique identifier), `email`, `name`, authentication time and so on. An ID Token is always a JSON Web Token (JWT) — that is an OIDC requirement, while OAuth2 never dictates the format of the access token. The ID Token is meant for the **client**. It must be verified, and it **must never be sent to other APIs** as if it were an access token.
2. **UserInfo endpoint** (`/protocol/openid-connect/userinfo` in Keycloak) — a standardized HTTP endpoint the client can call with an access token. It returns the user's current profile, which helps when the ID Token is already stale but the profile might have changed.
3. **Discovery document** (`/.well-known/openid-configuration`) — a JSON document the Authorization Server publishes. It describes **all** of the server's endpoints and capabilities, so the client never has to hardcode URLs.

```bash
curl https://keycloak.example.com/realms/myrealm/.well-known/openid-configuration
```

```json
{
  "issuer":
    "https://keycloak.example.com/realms/myrealm",
  "authorization_endpoint":
    "https://keycloak.example.com/realms/myrealm/protocol/openid-connect/auth",
  "token_endpoint":
    "https://keycloak.example.com/realms/myrealm/protocol/openid-connect/token",
  "userinfo_endpoint":
    "https://keycloak.example.com/realms/myrealm/protocol/openid-connect/userinfo",
  "jwks_uri":
    "https://keycloak.example.com/realms/myrealm/protocol/openid-connect/certs",
  "end_session_endpoint":
    "https://keycloak.example.com/realms/myrealm/protocol/openid-connect/logout",
  "grant_types_supported": [
    "authorization_code",
    "client_credentials",
    "refresh_token",
    "urn:ietf:params:oauth:grant-type:device_code"
  ],
  "response_types_supported": ["code", "none"],
  "code_challenge_methods_supported": ["plain", "S256"]
}
```

Practical consequence: **a decent library should be configured with an issuer URL and pull this document itself**, rather than hardcoding a path to every endpoint. Libraries like `keycloak-js`, `oidc-client-ts` and `passport-jwt` with an OIDC strategy all support that.

It is the difference between a config that works on your dev box and one that survives a Keycloak upgrade. Under `/protocol/openid-connect/*` the paths could in theory change.

## Front-channel vs back-channel — a recurring concept in every article ahead

This distinction isn't a detail of one specific flow. It's a lens for **any** data exchange in OAuth2/OIDC:

```txt
Front-channel:
  Data travels through the user's browser — redirects, query
  params, the URL fragment (#), postMessage. Visible in the
  address bar, potentially visible to third-party code on the
  page, and able to leak through browser history, the Referer
  header or proxy logs.
  Example: a redirect to /authorize with parameters in the
  query string.

Back-channel:
  Data travels server to server, directly, bypassing the user's
  browser entirely. A TLS connection between the Client (or the
  Resource Server) and the Authorization Server. Never visible
  to the user, never stored in browser history.
  Example: exchanging an authorization code for tokens — a
  direct POST to /token from the backend, or straight from JS
  code in the browser for a public client, but never through
  a redirect.
```

Why it matters: **anything that must stay secret — a client secret, the tokens themselves — should travel over the back-channel wherever possible**.

That is why the Implicit Grant is considered insecure: it passes the access token through the URL fragment, over the front-channel (more on this below). The Authorization Code Grant became the standard instead. It sends only a one-time `code` over the front-channel and exchanges that code for tokens over the back-channel.

From here on this pair of terms is used without redefinition. If a flow passes something through a redirect, that's front-channel. If it's a direct HTTP request between servers, that's back-channel.

## Access Token, ID Token, Refresh Token — three artifacts, three purposes

This is the number one source of confusion for developers new to this space. All three are "some kind of token", issued in the same response, so it's tempting to treat them interchangeably. That's a mistake with real consequences.

|  | Access Token | ID Token | Refresh Token |
|---|---|---|---|
| Intended for | Resource Server (the API), in an `Authorization: Bearer` header | Client only — never send it to another API | Authorization Server, and only at `/token` |
| Format | Opaque per OAuth2 spec; a JWT in Keycloak | Always a JWT (an OIDC requirement) | Opaque per spec; a JWT in Keycloak, an implementation detail |
| Contains | scope, roles, permissions — "what's allowed" | Identity claims: `sub`, `email`, `name`, `auth_time` — "who this is" | The minimum the Authorization Server needs to find the session |
| Lifetime | Short (minutes) | Same as the access token | Long (hours or days), or until logout |
| Used by | Resource Server, on every API call | Client app, to show "Hi, Name" on screen | Client, only to get a new token pair |

The physical format of the access token and the details of validating it are covered separately in [Tokens, Sessions, and Validation](./03-tokens-sessions-and-validation.md). That article explains JWKS (JSON Web Key Set), the `kid` header, and local validation versus introspection. The point here is the semantic boundary between the three artifacts, not the wire format.

The general structure of a JWT (header.payload.signature) is covered in the JWT, Access Token and Refresh Token topic. This article focuses on each token's protocol role, not its physical shape.

A common real-world mistake: a React app decodes the ID Token and sends it as `Authorization: Bearer <idToken>` on requests to its own NestJS API. This can technically even work, if the backend is careless enough to accept any JWT from the same issuer. But it violates the contract.

The ID Token isn't meant for a Resource Server. It has a different `aud` — the audience claim, naming the recipient the token was issued for. Nothing guarantees it even carries the claims authorization needs, such as roles and scope.

## Scopes vs Claims — the pair everyone mixes up

- **Scope** — a request for access. The client specifies scopes in the `/authorize` request (`scope=openid profile email`), effectively saying that it needs access to this category of data and actions. Scope is what the client asks **for**.
- **Claim** — a concrete fact about the user or the token, inside the issued JWT (`email`, `sub`, `realm_access.roles`). A claim is what the client actually **got**.

```txt
Requested scope:  "scope=openid profile email"
        ↓
The Authorization Server decides which claims to grant
        ↓
ID Token contains: sub, name, preferred_username, email,
                   email_verified ...
```

In Keycloak, the mapping between scopes and the actual set of claims is configured through **Client Scopes** and **Protocol Mappers**. That mechanism is Keycloak-specific and is covered in [Keycloak Core Concepts](./02-keycloak-core-concepts.md).

The protocol-level principle to take away: scope is the request, claim is the result. One scope usually bundles several claims at once. The `profile` scope isn't a single claim — it's a group of `name`, `family_name`, `given_name`, `picture` and so on.

## Grant Types — how a client actually gets a token

A grant type (sometimes called a flow) is a concrete protocol scenario. It fixes which messages travel between the Client, the Authorization Server and — sometimes — the user's browser, ending with the client holding tokens.

Picking a grant type isn't a matter of taste. It follows directly from what the client **is**:

- Is there a user in front of a screen?
- Can the client safely hold a secret?
- What kind of input interface does it have?

| Grant type | Who it's for | Status |
|---|---|---|
| Authorization Code + PKCE (Proof Key for Code Exchange) | A user with a browser; public or confidential client | The default today |
| Client Credentials | A service acting for itself, with no user | Standard for service-to-service calls |
| Device Code | A device with no keyboard or browser | Niche but standard |
| Resource Owner Password (ROPC) | Legacy clients that collect the password themselves | Deprecated |
| Implicit | Browser apps, from before PKCE existed | Deprecated |

### Authorization Code + PKCE — the modern default

This is the only correct choice for an interactive user login today. It fits confidential clients, meaning a backend with a client secret. More importantly, it fits public clients — single-page apps and mobile apps, which physically cannot hold a secret.

**PKCE** is pronounced "pixy" and is defined in RFC 7636. It was originally designed for mobile apps. Today Keycloak and most modern guidance recommend it for **all** clients, confidential ones included.

The reason is not the missing client secret. PKCE defends against a specific class of attack — authorization code interception — and that attack is relevant regardless of client type.

The full PKCE mechanism — what `code_verifier` and `code_challenge` are, and why they stop interception — is covered in [Security Hardening and Attack Vectors](./07-security-hardening-and-attack-vectors.md). Here we only fix the protocol sequence.

```txt
Participants: the user's browser, React SPA (Client), Keycloak
  (Authorization Server), NestJS API (Resource Server)

1. [Client, locally]
   Generate a random code_verifier, then compute
   code_challenge = SHA256(code_verifier)

2. [front-channel]
   The browser is redirected to:
     GET /authorize?
       response_type=code
       &client_id=spa-client
       &redirect_uri=https://app.example.com/callback
       &scope=openid profile email
       &state=<random value — CSRF protection>
       &code_challenge=<computed in step 1>
       &code_challenge_method=S256

3. [on Keycloak's side]
   The user sees Keycloak's login form — not the client's own
   form — and enters their credentials. Keycloak authenticates
   them and stores the code_challenge alongside the
   authorization code.

4. [front-channel]
   Keycloak redirects the browser back:
     GET https://app.example.com/callback?
       code=<one-time-use authorization code>
       &state=<the same value sent in step 2>

5. [Client]
   Verify that state matches what was sent
   (protects against CSRF/replay on the redirect)

6. [back-channel]
   The Client makes a direct POST to /token, not through
   a browser redirect:
     grant_type=authorization_code
     &code=<code from step 4>
     &redirect_uri=<same one as in step 2>
     &code_verifier=<original from step 1>
     &client_id=spa-client

7. [Keycloak, back-channel]
   Checks that SHA256(code_verifier) equals the code_challenge
   stored in step 3. If it matches, Keycloak issues
   access_token, id_token and refresh_token in the JSON
   response.
```

A detail worth stating explicitly: the `code` from step 4 is **useless by itself without the `code_verifier`**. Even if an attacker intercepts the code, they cannot exchange it for tokens, because they don't know the `code_verifier`. That value never left the legitimate client's memory.

Interception is realistic: a leak in proxy logs, or a malicious app registered on the same custom URL scheme in a mobile operating system.

### Client Credentials Grant — service-to-service, no user at all

Used when a service requests a token for itself, not for a user. For example, NestJS service A calls NestJS service B over an internal API. There is no logged-in human anywhere in that interaction.

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

A niche but real scenario: an app runs on a device with no keyboard or browser. Think of a smart TV, a game console, a command-line tool. Typing a username and password there is awkward.

```txt
1. [Device → Authorization Server, back-channel]
   POST /auth/device — the device requests a "device code".
   ← gets back: device_code (for the device itself),
                user_code (short, for a human — "ABCD-1234"),
                verification_uri
                  ("https://keycloak.example.com/device")

2. [Device]
   Shows on screen: "Go to keycloak.example.com/device
   and enter code ABCD-1234"

3. [User, on a different device — phone or laptop]
   Opens verification_uri, logs in normally (an Authorization
   Code-like flow happens internally), enters the user_code,
   confirms.

4. [Device, meanwhile]
   Polls /token with the device_code every N seconds:
   grant_type=urn:ietf:params:oauth:grant-type:device_code
   Until the user confirms, Keycloak replies
   "authorization_pending". Once confirmed, tokens are
   returned.
```

The core idea: the device with the poor input interface never sees the username or password. Authentication happens on a separate, convenient device. The original device only receives the result, by polling.

### Why Resource Owner Password Credentials (ROPC) is deprecated

ROPC, the `password` grant, looks tempting. The client collects the username and password in its own form, then exchanges them for a token in one request, with no redirects.

```txt
POST /token
  grant_type=password
  &username=user@example.com
  &password=<the user's password>
  &client_id=legacy-client
```

The problem isn't that "it's old" — it's specific architectural losses:

- **The client physically holds the user's password in memory.** That directly contradicts OAuth2's founding goal: grant access without exposing the password to a third party. If the client, or a library it uses, has a vulnerability, the password itself is compromised — not just a token.
- **Multi-factor authentication (MFA) and step-up become hard to add.** The Authorization Server never sees or controls the login form. So it cannot insert a text-message code, a WebAuthn prompt, or a redirect to an external identity provider (IdP). All of that second-factor logic would have to be reinvented inside every client. Identity Brokering, described in [Keycloak Core Concepts](./02-keycloak-core-concepts.md), is the mechanism for that.
- **Single sign-on (SSO) becomes impossible.** The user logs in again separately in **every** client, because authentication happens inside each app's own form rather than on a shared Authorization Server.

Keycloak disables Direct Access Grants (Keycloak's internal name for ROPC) by default for new clients — that's a deliberate decision, not a forgotten checkbox.

### Why Implicit Grant is deprecated

The Implicit Grant (`response_type=token`) was designed for SPAs before CORS (cross-origin resource sharing) and PKCE were widely available. The idea was to hand the access token back directly in the redirect, with no separate back-channel exchange. Browsers back then couldn't reliably make a cross-origin POST to swap a code for a token.

```txt
GET /authorize?response_type=token&client_id=spa&redirect_uri=...
        ↓
Redirect to:
  https://app.example.com/callback
    #access_token=eyJhbGci...&expires_in=300
     ▲
     the token sits in the URL fragment
```

Concrete, not abstract, reasons this is considered insecure today (the OAuth 2.0 Security Best Current Practice explicitly recommends against Implicit):

- **The token travels over the front-channel in the clear.** The whole point of splitting "code over front-channel, token over back-channel" in the Authorization Code Grant disappears. The access token itself ends up in the address bar and in browser history. It also reaches the `Referer` header on the next external link, and the logs of any proxy that records full URLs.
- **No client verification at token issuance.** In the Authorization Code Grant, the code→token exchange in step 6 runs over the back-channel. That gives the Authorization Server one more chance to confirm the request comes from a legitimate client, through PKCE's `code_verifier` or a client secret. In Implicit, the token is handed out right on the redirect, with no such check.
- **The token can't be silently refreshed.** Implicit doesn't provide a refresh token, and a refresh token over the front-channel would be unsafe too. The only way to extend a session was an invisible iframe redirect with `prompt=none`, which is inherently fragile. See the `silent-check-sso` problem in [React SPA Integration](./05-react-spa-integration.md).

Today both Keycloak and every modern library — `keycloak-js`, `oidc-client-ts` — default to Authorization Code + PKCE, even for a browser-only SPA. Implicit survives only as historical context, useful for understanding **why** the modern flow is shaped the way it is.

## Tying it together

```txt
[OAuth2 roles]            →  Client / Resource Owner /
                             Authorization Server / Resource
                             Server — the vocabulary for every
                             reasoning that follows

[OIDC on top of OAuth2]   →  ID Token + UserInfo + Discovery
                             Document add standardized identity

[Front-channel /          →  the recurring lens: what is safe
 back-channel]               to hand to a browser redirect, and
                             what only ever travels over a
                             direct server connection

[Access / ID / Refresh]   →  three artifacts with different
                             recipients and different purposes
                             — mixing them up is an
                             architectural mistake, not a minor
                             imprecision

[Grant types]             →  the choice follows from the kind
                             of client you have: a user with a
                             browser (Auth Code + PKCE), a
                             service with no user (Client
                             Credentials), a device with poor
                             input (Device Code)
```

The next article, [Keycloak Core Concepts](./02-keycloak-core-concepts.md), moves from protocol theory to the Keycloak object model. It shows how Keycloak models Realms, Clients, roles and claims, so everything described here becomes something you can configure.

## Common interview traps

- **"OAuth2 and OIDC are the same thing, just different names"** — wrong. OIDC is an identity layer built **on top of** OAuth2, reusing the same endpoints and the same grant types. It adds what plain OAuth2 cannot have by spec: an ID Token, a UserInfo endpoint, and a standard way to learn who the user is.

- **"The access token tells you who's logged in"** — no, that's the ID Token's job. The access token says **what** the token holder is allowed to do (scope and roles), not **who** they are. Confusing the two means using the wrong artifact for the job, not a minor terminology slip.

- **"PKCE only matters because SPAs don't have a client secret"** — an incomplete answer. PKCE defends against authorization code interception regardless of whether a secret exists, which is why modern guidance and Keycloak recommend PKCE even for confidential clients. A good answer explains the **mechanism** — `code_verifier` and `code_challenge` — not just that public clients need it.

- **"Implicit Grant is deprecated because it's an old spec version"** — that doesn't explain **why**. The real answer: the token travels over the front-channel, in the URL fragment. It is exposed in the clear — in browser history, in the `Referer` header, in proxy logs. There is also no extra client verification at issuance, unlike Authorization Code, where the code→token exchange happens over the back-channel with a PKCE check.

- **"The refresh token has to be a JWT too, just like the access token"** — no. The spec dictates nothing about the format of the access token or the refresh token. Only the ID Token must be a JWT, per OIDC. Keycloak makes the access token a JWT by default for convenient local validation, but that's an implementation detail, not a protocol requirement.

- **"Client Credentials Grant is basically logging in as a service account"** — not quite. Client Credentials has no user, no ID Token, and no notion of identity at all. The client itself is authorized as a subject; it is not impersonating a human. Blurring this leads to bad service-to-service authorization designs. A typical one: trying to read a specific user's roles out of a client-credentials token, where those roles cannot exist.
