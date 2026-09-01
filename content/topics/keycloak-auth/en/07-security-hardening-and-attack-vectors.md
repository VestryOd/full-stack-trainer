# Security Hardening — attacks and defenses specific to auth flows

## Every defense mechanism has one specific attack behind it

This article walks each auth defense back to the exact attack it closes off.

Articles 01-06 mentioned those mechanisms as needed: PKCE (Proof Key for Code Exchange), token TTL (time to live), refresh rotation. None of them got the attack behind it taken apart. The general mechanics of XSS (cross-site scripting), CSRF (cross-site request forgery) and CORS (cross-origin resource sharing) are covered in the general Security topic. Here the focus is narrow and applied:

- What exactly happens without PKCE.
- What exactly breaks with loose `redirect_uri` validation.
- How a JWT (JSON Web Token) algorithm confusion attack physically works.

This is the level that separates two answers. One is "I configured Keycloak following a guide". The other is "I can walk an attacker's scenario through every checkbox in the config that defends against it."

## PKCE — the mechanics of the defense, not just "recommended practice"

The full PKCE sequence was shown in article 01; here's exactly what happens mathematically, and why it defends against interception.

```txt
Step 1 (client, locally, never sent anywhere):
  code_verifier = a cryptographically random string,
                  43-128 characters
  Example: "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"

Step 2 (the client computes and sends a derived value):
  code_challenge = BASE64URL(SHA256(code_verifier))
  code_challenge_method = "S256"

Step 3 (the client sends code_challenge to /authorize):
  GET /authorize?...
      &code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM
      &code_challenge_method=S256
  Keycloak remembers the code_challenge next to the authorization
  code it issues

Step 4 (the client exchanges the code for tokens and sends the
        original code_verifier):
  POST /token
    grant_type=authorization_code
    &code=<authorization code>
    &code_verifier=dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk

Step 5 (Keycloak checks):
  SHA256(code_verifier from step 4) == code_challenge from step 3 ?
  Match → issue tokens
  No match → reject, 400 invalid_grant
```

Why this specifically defends against **authorization code interception**: an intercepted `code` is useless on its own. Suppose an attacker somehow gets hold of it. It can leak through proxy logs. It can come from a malicious app on the device registered on the same custom URL scheme. It can come from an analytics system that logs the full redirect URL. Without the `code_verifier`, that value buys them nothing.

The `code_verifier` **never travels over the network before step 4**. It lives only in the legitimate client's memory. In a SPA (single-page application) it usually sits in `sessionStorage` for the duration of the flow, between step 2 and step 4.

The attacker also can't compute the `code_verifier` from the `code_challenge`. SHA256 is a one-way function, and reversing it is cryptographically infeasible.

**Why PKCE matters even for confidential clients.** This is a common interview question, already raised in article 01; here is the mechanics.

A confidential client is protected by `client_secret` against **somebody else** impersonating it at the code→token exchange step. But `client_secret` does not cover a different scenario. An attacker intercepts a `code` meant for **this specific** client, then exchanges it through **that same** confidential client before the legitimate user does. It is a race on the intercepted code, run ahead of the legitimate request.

PKCE closes exactly this scenario, whatever the client type. That is why the modern OAuth 2.0 Security Best Current Practice makes PKCE mandatory for **every** client type, not just public ones.

## state vs nonce — two parameters defending against two different attacks

Both parameters are random strings. The client generates them, sends them in the `/authorize` request, and gets them back. That similarity is exactly what gets them confused. They defend against fundamentally different attacks.

```txt
state — CSRF/replay protection for the redirect itself:

  The attack without state: an attacker starts their own login
  flow against the legitimate Keycloak, logging into an account
  they control. They get a valid authorization code on their own
  redirect. Then they hand the victim a link to the app's callback
  URL carrying that code, in a phishing email for example. If the
  victim follows it, and the app never checks that state matches,
  the app can link the victim's session to the attacker's account.
  This is Login CSRF: the victim ends up logged in as the attacker,
  and may then type sensitive data into an account the attacker
  controls.

  Defense: the client generates a random state before redirecting
  to /authorize, stores it locally (sessionStorage), sends it in
  the request, and on the callback verifies that the returned
  state matches the stored one. An authorization code obtained
  outside this one local client session will not pass that check.

nonce — replay protection for the ID Token:

  The attack without nonce: an attacker obtains a legitimate user's
  previously issued, not yet expired ID Token — through logs or a
  compromised channel, say. They re-present it to the client app
  as "the result of a new login".

  Defense: the client generates a random nonce before redirecting.
  Keycloak embeds it inside the ID Token itself as a claim
  (`nonce: <value>`) when issuing it. On receiving the ID Token,
  the client checks the `nonce` claim inside the token against the
  value it generated for this one login attempt. A re-presented
  old ID Token carries the old nonce, which will not match the new
  one — so the client rejects it as invalid for this session.
```

A mnemonic that actually separates the two. The `state` parameter **protects the transport**: the redirect exchange between the client and Keycloak, at the HTTP level. The `nonce` parameter **protects the content**: the ID Token itself, so it can't be reused outside one specific login attempt.

In an OIDC (OpenID Connect) flow both parameters are used at the same time, and neither substitutes for the other. Both `keycloak-js` and `oidc-client-ts` generate and verify them automatically. Knowing the mechanism still matters. It tells you what exactly breaks when a library is misconfigured — a custom OIDC client implementation that skipped the nonce check, for instance.

## Strict redirect_uri validation — how loose matching turns into token theft

`redirect_uri` is the URL Keycloak sends the user's browser to, carrying an authorization code, after a successful login. If Keycloak (or the client itself) validates this parameter loosely, it opens a direct path to code/token theft.

```txt
Loose validation (a common configuration mistake):
  Registered redirect_uri in Keycloak: "https://app.example.com/*"
  (a wildcard pattern, allowed by some old or careless configs
  "for convenience")

  The attack: say app.example.com has an open-redirect hole
  somewhere — /some-legit-path?next=https://evil.com, which
  redirects to next with no domain check. An attacker crafts an
  authorization request with
  redirect_uri=https://app.example.com/some-legit-path?
  next=https://evil.com, and that technically matches the
  wildcard pattern. The user logs in, and Keycloak's form looks
  completely normal, because the domain really is the real one.
  Keycloak redirects to the allowed redirect_uri, which in turn
  open-redirects to evil.com — carrying the authorization code
  along in the query string.

Correct validation:
  Registered redirect_uri: an exact match,
  "https://app.example.com/callback" — no wildcard, no extra
  query parameters on top, compared character for character.
  The OAuth 2.0 Security Best Current Practice explicitly
  requires exact string matching, not prefix or pattern matching.
```

The practical consequence for Keycloak configuration: **never use wildcard patterns in a client's Valid Redirect URIs "for dev convenience"** — not even temporarily. This is one of those settings that gets forgotten before going to prod. It is also one of the most common findings in real security audits of OAuth2 integrations.

## JWT Algorithm Confusion — a classic interview trap

This is an attack on the JWT validation library itself, not on Keycloak directly. It still concerns the code you write in the NestJS Resource Server (article 04), so knowing the mechanics is mandatory.

```txt
The "alg: none" attack:

  A JWT header can technically contain { "alg": "none" } — a token
  with no signature at all. That is a valid format per the JWT
  spec, even though it is meaningless as authentication. An
  attacker takes any valid token, changes the payload however
  they like (say, "role": "admin"), changes the header to
  { "alg": "none" }, and drops the signature part.

  A vulnerable library: if the validation code trusts the `alg`
  from the token's own header — that is, asks the token which
  algorithm to verify it with — it will honestly "verify" the
  signature against "none" (an empty check) and accept the token.

  Defense: never let the validation library pick the algorithm
  from a value inside the token. The algorithms list must be
  hardcoded in the Resource Server's config:

    algorithms: ['RS256']   // fixed, not "whatever the token says"

  (see the KeycloakJwtStrategy example in articles 03/04 —
  algorithms is already passed explicitly for exactly this reason)

The RS256/HS256 key confusion attack:

  Keycloak signs with RS256 by default. That is asymmetric:
  Keycloak holds the private key, everyone else gets the public
  key via JWKS. HS256 is a symmetric algorithm, where the same
  secret both signs and verifies.

  The attack: suppose the validation library does not strictly
  check that the `alg` in the received token matches the expected
  algorithm (RS256), and instead adapts to whatever `alg` the
  token claims. The attacker changes the header to
  { "alg": "HS256" } and signs the token with HMAC, using
  Keycloak's public RSA key as the HMAC secret — a key that is
  openly available through the JWKS endpoint. The vulnerable
  library sees `alg: HS256` and grabs "the key for HS256". If the
  code carelessly hands it the same public key used for RS256
  verification, the check passes: HMAC(payload,
  public_RSA_key_as_secret) genuinely matches the signature the
  attacker computed with that same public key.

  Defense: the same as above — algorithms: ['RS256'] hardcoded,
  so the library never tries to read the token as HS256 under any
  circumstances. Modern, well-vetted libraries close this vector
  by default when configured correctly: jose, jsonwebtoken 9+,
  passport-jwt with an explicit algorithms option. But that
  correct configuration — an explicit algorithms list, not the
  library's default — is the developer's responsibility.
```

This is a classic interview question exactly because it sounds esoteric and comes down to one practical rule. **The verification algorithm is set by the Resource Server's configuration, not by a value from the token itself.** That rule is easy to check in code review. JWT validation with no explicit list of allowed algorithms is a red flag, whichever library is in use.

## Refresh Token Rotation with Reuse Detection — the full picture

Article 03 mentioned rotation as a policy. Here is why it is specifically a **detection** mechanism, not just hygiene.

```txt
The normal scenario (no attack):

  The client holds refresh_token_1
  → exchanges it for access_token_2 + refresh_token_2 (Keycloak
    revokes refresh_token_1 the moment refresh_token_2 is issued)
  → later exchanges refresh_token_2 for refresh_token_3
  → and so on, each exchange invalidates the previous token

A theft scenario (the refresh token is compromised, say via XSS,
before the app has had a chance to use it):

  An attacker stole refresh_token_1 — from sessionStorage via XSS,
  say, before the legitimate app got to exchange it

  Case A — the attacker uses it first:
    The attacker → exchanges refresh_token_1 for refresh_token_2
    The legitimate app later tries to exchange its own, already
    revoked refresh_token_1 → Keycloak rejects it, because
    refresh_token_1 was already used and therefore revoked →
    the app sees invalid_grant where it did not expect one.
    That is a compromise signal, and it deserves to be treated
    as a possible theft rather than as "an expired session"

  Case B — the legitimate app uses it first:
    The app → exchanges refresh_token_1 for refresh_token_2 first
    The attacker later tries the already revoked refresh_token_1
    → Keycloak sees an attempt to reuse a token that was already
    "spent" in an exchange — a clear signal that someone other
    than the legitimate client holds a copy of this token
```

The correct reaction to detected reuse is not just to reject that one request. It is to **revoke the entire chain of tokens tied to that session**, which Keycloak supports as part of its refresh token rotation policy.

That forces the legitimate user through a full re-login. There is no way around it. At this point nothing tells you reliably which of the two copies of the token is the right one — the attacker's or the user's.

This is exactly what turns rotation from "just fresher tokens" into a real **breach-detection mechanism**. Without rotation, a stolen refresh token would stay quietly valid until its TTL expired, with no signal of the compromise at all.

## Brute-force detection in Keycloak — a built-in defense that needs deliberate configuration

Keycloak has a built-in password-guessing defense (Realm Settings → Security Defenses → Brute Force Detection) that's worth configuring explicitly, rather than relying on unchecked defaults:

```txt
Key parameters:
  Max Login Failures       — how many failed attempts before a
                              temporary account lockout (typically:
                              5-10)
  Wait Increment            — how much lockout time increases with
                              each subsequent burst of failures
                              (progressive delay, not fixed)
  Max Wait                  — the ceiling on lockout time
  Quick Login Check Millis  — the minimum interval between
                              attempts, below which they count as
                              "too fast" (a defense against
                              scripted attacks making hundreds of
                              attempts per second)
  Permanent Lockout         — lock the account permanently, until
                              an admin unlocks it by hand, once
                              the attempt ceiling is exceeded,
                              instead of a temporary delay
```

A practical nuance: settings that are too aggressive create a vector for **denial of service against other people's accounts**. A low `Max Login Failures` with `Permanent Lockout` enabled is enough.

An attacker who knows only the victim's email, and no password, deliberately enters a wrong password the required number of times. The legitimate user is now locked out of their own account. Balancing password-guessing defense against this secondary DoS (denial of service) vector is a deliberate decision, not "stricter is always better."

## Clickjacking protection specifically for the login page

Keycloak's login page is a particularly sensitive clickjacking target. Here is how the attack looks.

The attacker embeds the login page in an invisible `<iframe>` on their own page, laid underneath something like a "Play the game" button. On top of the login form they put their own UI (user interface) as a transparent layer.

The user types real credentials while believing they are interacting with something else. The data really does travel through a form that belongs to Keycloak — just embedded by the attacker in their own context.

```txt
Keycloak config (Realm Settings → Security Defenses → Headers):
  X-Frame-Options: SAMEORIGIN   (a legacy but still-honored header;
                                  restricts iframe embedding to the
                                  same origin only)
  Content-Security-Policy:
    frame-ancestors 'self' https://app.example.com;
    (the modern, more flexible mechanism — an explicit whitelist
     of domains allowed to embed the Keycloak page in an iframe.
     Important: not an unconditional 'none'. silent-check-sso
     from article 05 is itself a legitimate iframe embedding of
     the Keycloak page from the app's domain, and 'none' would
     break it. What you need is a precise whitelist of your own
     app's domains, not a blanket ban)
```

One subtlety is specific to this topic. **Keycloak's login page may legitimately need to be embedded in an iframe**, because of silent-check-sso. It is the only page in the system like that. For most other pages in the app, `frame-ancestors 'none'` would be the right default.

So the configuration should allow iframe embedding **only** from your own clients' trusted domains. A broad whitelist here is just as dangerous as having none at all.

## CORS — the specifics for auth endpoints

The general mechanics of CORS are covered in the Security topic. Here are the concrete gotchas specific to Keycloak endpoints.

```txt
Web Origins in a Keycloak client's settings:
  This is NOT the same thing as Valid Redirect URIs. Web Origins
  defines which origins are allowed to make CORS requests
  (fetch/XHR) DIRECTLY to Keycloak endpoints (e.g. /userinfo, /token
  from the browser) — not where the browser is allowed to be
  redirected to.

  A common configuration mistake: setting up Valid Redirect URIs
  correctly but forgetting Web Origins — then a browser fetch call
  to /userinfo or /token gets blocked by Keycloak's CORS policy,
  even though the redirect-based login flow works fine (a redirect
  isn't subject to CORS, but fetch/XHR is). These are two different
  defense mechanisms for the same client, and confusing them is a
  Keycloak-specific source of "login works but the frontend's
  userinfo call doesn't" bugs.

CORS on your Resource Server (NestJS):
  Access-Control-Allow-Origin should explicitly list the React
  app's origins, and the BFF's too if one is used (article 06).
  Never a wildcard '*' alongside an Authorization header:
  browsers won't even allow credentials with a wildcard origin,
  and trying to configure it that way signals a misunderstanding
  of the model. Pay special attention if the API serves several
  SPA clients on different domains (a multi-tenant frontend).
  The Origin should be checked against a list of allowed domains,
  never reflected blindly. `Access-Control-Allow-Origin:
  <req.headers.origin>` with no whitelist check is functionally
  the same as a wildcard — it just doesn't look like one on a
  shallow code review.
```

## Tying it together

```txt
[PKCE]                      →  code_verifier never leaves the
                               client before the exchange. An
                               intercepted code is useless without
                               it, for any client type

[state vs nonce]            →  transport-level CSRF protection for
                               the redirect vs replay protection
                               for the ID Token's content —
                               different attacks, both mandatory
                               in OIDC

[Strict redirect_uri]       →  exact match, not a wildcard.
                               Otherwise an open redirect anywhere
                               in the app becomes a channel for
                               stealing the authorization code

[JWT algorithm confusion]   →  algorithms is always hardcoded in
                               the Resource Server's config, never
                               derived from a value inside the
                               token

[Refresh rotation + reuse
 detection]                 →  not just hygiene — a way to detect
                               theft through the fact that an
                               already-spent token got reused

[Brute-force detection]     →  password-guessing defense vs the
                               risk of denial of service against
                               other people's accounts: a balance,
                               not "as strict as possible"

[frame-ancestors for login] →  the one page that may need
                               legitimate iframe embedding — a
                               precise whitelist, not a blanket
                               ban and not a blanket allow

[CORS: Web Origins vs
 Redirect URIs]             →  two different defense mechanisms
                               for the same Keycloak client.
                               Confusing them is a common source
                               of "login works, but userinfo
                               doesn't"
```

The next article is [Advanced Patterns](./08-advanced-patterns.md). It moves from defending the standard flow to patterns beyond "plain login": step-up authentication, account linking, multi-tenancy.

## Common interview traps

- **"PKCE is only needed for public clients that don't have a client secret"** — an incomplete answer. Article 01 already covered this, and here you should be able to explain the mechanism. PKCE defends against authorization code interception whether or not a secret exists: a race on an intercepted code is possible for a confidential client too.

- **"state and nonce are the same thing, OAuth2 and OIDC just came up with different names for the same protection"** — no. The `state` parameter protects the redirect exchange itself from CSRF and replay. The `nonce` parameter protects the ID Token's content from being reused. Both are needed at the same time, and they aren't interchangeable.

- **"Once redirect_uri is registered in Keycloak, you don't need to think about its security anymore"** — no. Suppose the registered pattern is a wildcard, or too broad a prefix, and the app's own domain has an open-redirect hole somewhere. That combination becomes a channel for stealing the authorization code, however "formally registered" the redirect_uri is.

- **"A JWT validation library figures out on its own which algorithm to verify the signature with, based on the token"** — no. That is exactly the vulnerable configuration for an algorithm confusion attack. The correct answer: the algorithm is always hardcoded in the Resource Server's config (`algorithms: ['RS256']`). It is never derived from the `alg` value inside the token itself.

- **"Refresh token rotation is just swapping tokens more often for hygiene"** — incomplete. Rotation's main value is **detecting** token theft through the fact that a token was reused. That detection is what lets you react and revoke the whole chain, instead of only "keeping tokens fresh."
