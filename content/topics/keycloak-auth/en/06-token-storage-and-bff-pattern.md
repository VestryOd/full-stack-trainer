# Token Storage and the BFF Pattern

## The central architectural decision in SPA security

Everything covered in article 05 (silent-check-sso, refresh, logout) happens ON TOP OF one decision that shapes the app's entire risk profile: **where the token physically lives in the browser**. This isn't an implementation detail you can swap later with no consequences — it's the decision the whole SPA threat model is built around. This article covers the options honestly, with no single "correct" answer for every case, and then walks through an architecture that's increasingly chosen instead of the trade-off entirely — BFF (Backend-for-Frontend).

## Three storage options — and what each one bets on

```txt
┌──────────────────┬───────────────────┬───────────────────┬──────────────────┐
│                    │ In-memory (JS var) │ localStorage/       │ httpOnly Cookie    │
│                    │                    │ sessionStorage      │                    │
├──────────────────┼───────────────────┼───────────────────┼──────────────────┤
│ Reachable by an    │ No — the token         │ YES — any JS,       │ No — JS physically │
│ XSS script?        │ only exists in a       │ including code       │ cannot read it     │
│                    │ closure/memory, no     │ injected via XSS,    │ (that's the whole  │
│                    │ API lets one JS        │ reads it directly    │ point of httpOnly) │
│                    │ script access another  │ via localStorage.    │                    │
│                    │ script's memory        │ getItem              │                    │
├──────────────────┼───────────────────┼───────────────────┼──────────────────┤
│ Survives a page    │ No — lost on a full     │ Yes — survives      │ Yes — the browser  │
│ refresh?           │ page reload (needs      │ both a refresh and  │ resends the cookie │
│                    │ silent-check-sso        │ closing the tab      │ on every request,  │
│                    │ again, article 05)      │                     │ including after a  │
│                    │                         │                     │ refresh            │
├──────────────────┼───────────────────┼───────────────────┼──────────────────┤
│ Vulnerable to      │ No — the token isn't     │ No — not sent        │ YES — the browser  │
│ CSRF?              │ sent automatically       │ automatically,       │ sends the cookie    │
│                    │ anywhere                 │ sending requires     │ AUTOMATICALLY on   │
│                    │                         │ explicit JS code     │ every request to    │
│                    │                         │                     │ the domain —         │
│                    │                         │                     │ including a request  │
│                    │                         │                     │ initiated by a       │
│                    │                         │                     │ malicious site       │
├──────────────────┼───────────────────┼───────────────────┼──────────────────┤
│ Practical           │ Requires silent-check-  │ Never use this for   │ Requires explicit    │
│ downside            │ sso/refresh on every    │ an access token —     │ SameSite/CSRF        │
│                    │ load — the very          │ the only option in    │ protection + careful │
│                    │ fragility from article   │ this table WITHOUT     │ CORS config (below)  │
│                    │ 05                       │ a real justification  │                     │
└──────────────────┴───────────────────┴───────────────────┴──────────────────┘
```

The key takeaway from this table, and one that's easy to miss: **this isn't a "secure vs insecure" choice — it's a choice of WHICH attack vector you're accepting as a risk**. In-memory and httpOnly cookie both close off XSS-based token reading, but each opens a different secondary problem (losing state on refresh vs needing CSRF protection). localStorage is the only option in the table that doesn't solve any of these problems better than the others, which is why the industry consensus ("never store a token in localStorage") isn't dogma — it's that this option is strictly dominated by either of the other two on the XSS axis, with no compensating advantage.

## "httpOnly cookie" isn't a free win

A common mistake when first learning this space is hearing "httpOnly cookies protect against XSS" and stopping there, treating the question as settled. httpOnly solves exactly one problem (JS can't read the cookie) and creates exactly one new one: **the browser sends that cookie AUTOMATICALLY on every request to the domain, regardless of who initiated the request** — including a request triggered by a malicious page the user opened in a sibling tab (CSRF, Cross-Site Request Forgery — the detailed mechanism is covered in the general security topic; the focus here is how it specifically applies to an auth cookie).

```txt
The mandatory minimum protection for an auth cookie, not an optional
"for later":

  SameSite=Strict or Lax:
    Strict — the cookie is never sent on ANY cross-site navigation,
             even clicking a link from another site. The safest
             option, but can break the "user clicked a link from an
             email — should stay logged in" scenario.
    Lax    — the cookie is sent on top-level GET navigation (clicking
             a link), but not on cross-site POST/fetch/XHR requests
             from other domains. A practical default for most apps.

  Secure:
    The cookie is only ever transmitted over HTTPS — without this
    flag it could be intercepted over an unencrypted channel.

  CORS configuration specifically for auth endpoints:
    Access-Control-Allow-Origin must be a SPECIFIC domain, never "*"
    (a wildcard) alongside Access-Control-Allow-Credentials: true —
    browsers won't even allow that combination, but a misconfigured
    server that reflects the request's Origin back verbatim with no
    whitelist check effectively creates the same risk as a wildcard.
```

Bottom line: an httpOnly cookie removes the XSS token-theft vector, but it requires the SAME engineering discipline (SameSite, Secure, precise CORS) as any other option — "just use an httpOnly cookie" with none of the rest of the config isn't safer by default, it's just a shifted set of requirements.

## BFF (Backend-for-Frontend) — the browser never gets a token at all

All three options above share one underlying problem: **the browser, in some form, still holds an artifact that grants API access** — a token in memory, in storage, or in a cookie. The BFF pattern removes that problem architecturally, rather than by picking the best storage location: **the browser never sees an access/refresh/ID token at all**. The only thing that reaches the browser is a plain session cookie belonging to the app itself (first-party, not Keycloak's).

```txt
The classic "public client in the browser" (articles 01-05):

  Browser ──(Auth Code + PKCE)──► Keycloak
  Browser ──(holds the access/refresh token)──► stores it directly
  Browser ──(Authorization: Bearer <token>)──► NestJS API

The BFF pattern:

  Browser ──(a plain HTTP session, just a first-party session cookie)──► BFF
  BFF (a server, NOT the browser) ──(Auth Code + PKCE, THIS is where
       client_secret lives — the BFF is a confidential client)──► Keycloak
  BFF ──(holds the access/refresh token ON THE SERVER, in its own
       session store/Redis)──►
  BFF ──(proxies the request, attaching the real access token)──► NestJS API
```

```txt
Step-by-step request flow:

1. Browser → GET /login (on the BFF, not directly on Keycloak)
2. The BFF generates a code_verifier, redirects the browser to
   Keycloak's /authorize (Auth Code + PKCE — the BFF now acts as
   the client)
3. The user logs in on Keycloak as usual
4. Keycloak redirects the browser to the BFF's callback URL with
   an authorization code
5. The BFF (back-channel, SERVER-TO-SERVER) exchanges the code for
   access/id/refresh tokens — these tokens NEVER appear in an HTTP
   response to the browser
6. The BFF creates its OWN session (a session ID), stores the
   Keycloak tokens in a server-side store (Redis/a DB) keyed by
   that session ID, and hands the browser ONLY an httpOnly
   first-party cookie holding the BFF's session ID (NOT a Keycloak
   token)
7. Further requests: browser → GET /api/orders (a plain BFF session
   cookie) → the BFF looks up the session ID from the cookie →
   fetches the STORED access token from Redis → proxies the request
   to the NestJS Resource Server with Authorization: Bearer <the
   real token>
8. Refresh: the BFF itself tracks the TTL of the stored access
   token and refreshes it via the refresh token — ENTIRELY on the
   server, the browser is never involved and never even knows a
   refresh happened
```

```typescript
// NestJS BFF — a simplified session-based proxy endpoint
@Controller()
export class BffController {
  constructor(
    private sessionStore: SessionTokenStore, // a Redis-backed token store keyed by sessionId
    private http: HttpService,
  ) {}

  @Get('callback')
  async handleCallback(@Query('code') code: string, @Req() req: Request, @Res() res: Response) {
    const tokens = await this.exchangeCodeForTokens(code); // back-channel POST /token

    const sessionId = randomUUID();
    await this.sessionStore.save(sessionId, tokens); // tokens live ONLY on the server

    res.cookie('bff_session', sessionId, {
      httpOnly: true,
      secure: true,
      sameSite: 'lax',
    });
    res.redirect('/dashboard');
  }

  @All('api/*')
  async proxyToResourceServer(@Req() req: Request, @Res() res: Response) {
    const sessionId = req.cookies.bff_session;
    const tokens = await this.sessionStore.getFreshTokens(sessionId); // refreshes itself on expiry

    const upstream = await firstValueFrom(
      this.http.request({
        method: req.method,
        url: `https://api.internal${req.path.replace('/api', '')}`,
        headers: { Authorization: `Bearer ${tokens.accessToken}` },
        data: req.body,
      }),
    );
    res.status(upstream.status).json(upstream.data);
  }
}
```

Note that `bff_session` isn't a JWT and isn't a Keycloak token — it's an opaque session ID for the BFF's own session, semantically identical to any traditional server-side web session (the same kind of cookie a classic Express/Rails app would have used before any OAuth2 was involved). This is exactly why the BFF architecturally eliminates the third-party cookie problem from article 05 — silent-check-sso isn't needed at all, because there's no foreign Keycloak domain whose cookie you'd need to read from an iframe: authentication now goes through the app's own first-party cookie, sent by the browser to its OWN domain the ordinary way, like any other web session.

## An honest comparison — the BFF isn't free

```txt
A public client in the browser (the classic SPA):

  ✓ Simpler infrastructure — no separate server component for auth,
    the SPA can be pure static hosting (a CDN)
  ✓ Less latency — the browser talks to the API directly, no extra
    hop through a proxy layer
  ✗ The token physically exists in the browser in some form —
    residual XSS risk even with in-memory storage (a renderer
    process's memory is reachable by a debugger/a sufficiently
    privileged browser extension, though that's already outside
    the typical threat model)
  ✗ silent-check-sso fragility (article 05) — an architectural flaw,
    not a bug in one specific implementation

BFF:

  ✓ Tokens NEVER physically exist in the browser — even a successful
    XSS can't steal the access/refresh token, because there's
    physically nothing for the script to read (just a session
    cookie, which is useless without the rest of the BFF server
    behind it)
  ✓ The third-party cookie problem disappears architecturally
  ✓ Refresh logic, token rotation, revocation handling — all in one
    place on the server, not scattered across client code
  ✗ An extra network hop on every API request (browser → BFF →
    Resource Server) — a real, measurable latency cost
  ✗ An extra server-full component — the SPA can no longer be purely
    static, the BFF has to be deployed, scaled, and monitored as a
    full stateful service (server-side sessions)
  ✗ The BFF itself becomes a confidential client holding a
    client_secret and users' tokens — a new, data-critical attack
    target that needs to be protected as seriously as the Resource
    Server itself
```

A practical recommendation rather than a universal verdict: **for a new project with real security requirements (fintech, healthcare, internal corporate systems), the BFF is a reasonable default starting point today**, because it removes a whole class of problems architecturally rather than patching around them, and a growing body of guidance (including the OAuth 2.0 Security Best Current Practice's recommendations for browser-based apps) leans toward exactly this pattern. For a small MVP or a low-stakes internal tool, the classic public-client approach from articles 01-05 remains perfectly adequate and significantly faster to build — it's worth treating this as a deliberate "speed/simplicity now vs a smaller attack surface" trade-off, not as "we just didn't know about the BFF."

## Tying it together

```txt
[In-memory / localStorage /
 httpOnly cookie]              →  each option trades XSS risk for
                                 CSRF risk or for lost state on
                                 refresh — there's no free option,
                                 except localStorage, which loses on
                                 every axis at once

[httpOnly ≠ secure by itself]  →  needs SameSite + Secure + precise
                                 CORS — the same engineering
                                 discipline, just a different set of
                                 requirements

[BFF]                           →  an architectural elimination of the
                                 problem: tokens never leave the
                                 server, the browser only ever deals
                                 with a plain first-party web session

[BFF vs public client
 trade-off]                     →  a smaller attack surface and a
                                 solved third-party cookie problem vs
                                 an extra server-full component and
                                 latency — a real architectural
                                 choice, not "progress vs the old way"
```

The next article — [Security Hardening and Attack Vectors] — takes the mechanisms mentioned in passing in this and earlier articles (PKCE, state, nonce, redirect validation, JWT algorithm confusion) and gives them a full, dedicated treatment focused on attack and defense.

## Common interview traps

- **"localStorage is convenient and secure enough if the app is generally well protected against XSS"** — a risky answer: "well protected against XSS" is never a guarantee (one vulnerable dependency in the npm tree is enough), and localStorage provides zero defense-in-depth for that case, unlike an httpOnly cookie or in-memory storage. A good answer recognizes that storing tokens in localStorage is an indefensible position, not "a good practice under certain conditions."

- **"An httpOnly cookie fully solves the token security problem"** — incomplete: it closes off XSS reading but opens up a CSRF vector that needs its own, mandatory defense (SameSite, precise CORS). An answer that doesn't mention CSRF shows a shallow grasp of the topic.

- **"A BFF is just a proxy, it gives no real security benefit, just an extra hop"** — an underestimate: a BFF removes the token from the browser ARCHITECTURALLY, not just relocates it — that changes the attack surface itself (XSS can no longer steal an access/refresh token, because there's physically nowhere to read it from), not just an added network layer with no purpose.

- **"A BFF is always the right choice, a public client in the browser is outdated"** — an overreach: a BFF adds real operational complexity (a server-full component, latency, an additional critical attack target) and is justified for applications with high security stakes, but it isn't an unconditionally superior choice for every project — MVPs and internal tools often reasonably choose the simpler public-client approach.

- **"Since tokens are stored server-side in a BFF, refresh token rotation is no longer needed"** — no, rotation (article 03) protects against theft of the refresh token AS AN ARTIFACT — regardless of whether the theft happened from the browser or from a compromised BFF server-side store (a misconfigured Redis instance, say) — a BFF reduces the likelihood of one theft vector, but doesn't remove the value of rotation as a separate breach-detection mechanism.
