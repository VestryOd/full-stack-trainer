# Token Storage and the BFF Pattern

## The central architectural decision in SPA security

A SPA (single-page application) has to settle one question before anything else: **where the token physically lives in the browser**. This article compares the three answers honestly, and then a fourth approach that removes the question: the BFF (Backend-for-Frontend) pattern.

That single decision shapes the app's entire risk profile. It is not an implementation detail you can swap later with no consequences — the whole SPA threat model is built around it. Everything covered in article 05 (silent-check-sso, refresh, logout) sits on top of it.

There is no single "correct" answer for every case. More and more teams choose the BFF instead of living with the trade-off at all.

## Three storage options — and what each one bets on

Two attacks decide this table. XSS (cross-site scripting) is attacker JavaScript running inside your own page. CSRF (cross-site request forgery) is another site making the browser send an authenticated request on the user's behalf.

| | In-memory (a JS variable) | localStorage / sessionStorage | httpOnly cookie |
|---|---|---|---|
| **Reachable by an XSS script?** | **No** — the token lives only in a closure. No API lets one script read another script's memory. | **Yes** — any JS reads it through `localStorage.getItem`. That includes code injected by an XSS attack. | **No** — JS physically cannot read it. That is the whole point of `httpOnly`. |
| **Survives a page refresh?** | **No** — a full page reload loses it. Then silent-check-sso has to run again (article 05). | **Yes** — it survives a refresh. It also survives closing the tab. | **Yes** — the browser resends the cookie on every request. That includes requests after a refresh. |
| **Vulnerable to CSRF?** | **No** — the token is never sent automatically. Nothing goes out without explicit code. | **No** — it is not sent automatically either. Sending it takes explicit JS code. | **Yes** — the browser sends the cookie on every request to the domain. That includes a request started by a malicious site. |
| **Practical downside** | Needs silent-check-sso or a refresh on every load. This is the exact fragility from article 05. | Never use it for an access token. It is the only option here with no real justification. | Needs `SameSite`/CSRF protection plus a careful CORS (cross-origin resource sharing) config. See below. |

The key takeaway from this table is easy to miss. **This isn't a "secure vs insecure" choice. It is a choice of which attack vector you accept as a risk.**

In-memory storage and an httpOnly cookie both close off XSS-based token reading. Each opens a different secondary problem in exchange: in-memory loses state on refresh, the cookie needs CSRF protection.

localStorage is the only option in the table that beats the others on nothing. On the XSS axis it loses to both, and it gives nothing back for that loss. So the industry consensus — "never store a token in localStorage" — is not dogma. It is a direct reading of this comparison.

## "httpOnly cookie" isn't a free win

A common mistake when first learning this space is to hear "httpOnly cookies protect against XSS", stop there, and treat the question as settled.

httpOnly solves exactly one problem: JS can't read the cookie. It also creates exactly one new one. **The browser sends that cookie automatically on every request to the domain, no matter who started the request.** That includes a request started by a malicious page the user opened in another tab.

This is the CSRF attack. Its general mechanism is covered in the security topic; here the focus is narrow — what CSRF means for an auth cookie.

**The mandatory minimum protection for an auth cookie** — not an optional "for later":

- **`SameSite=Strict`** — the cookie is never sent on any cross-site navigation, not even when the user clicks a link from another site. This is the safest option. It can break the "user clicked a link in an email and should stay logged in" scenario.
- **`SameSite=Lax`** — the cookie is sent on top-level GET navigation, such as clicking a link. It is not sent on cross-site `POST`, `fetch` or `XHR` requests from other domains. A practical default for most apps.
- **`Secure`** — the cookie is only ever transmitted over HTTPS (HTTP over an encrypted connection). Without this flag it could be intercepted over an unencrypted channel.
- **A CORS config written for the auth endpoints specifically** — `Access-Control-Allow-Origin` must name one specific domain, never the wildcard `"*"` alongside `Access-Control-Allow-Credentials: true`. Browsers won't even allow that combination. But a misconfigured server that reflects the request's `Origin` header back verbatim, with no whitelist check, creates the same risk as a wildcard.

Bottom line: an httpOnly cookie removes the XSS token-theft vector. It still demands the **same** engineering discipline as any other option — `SameSite`, `Secure`, a precise CORS config. "Just use an httpOnly cookie" with none of the rest of that config is not safer by default. It is a different set of requirements, not a smaller one.

## BFF (Backend-for-Frontend) — the browser never gets a token at all

All three options above share one underlying problem. **The browser, in some form, still holds an artifact that grants API access** — a token in memory, in storage, or in a cookie.

The BFF pattern removes that problem architecturally, instead of picking the best storage location. **The browser never sees an access, refresh or ID token at all.** The only thing that reaches the browser is a plain session cookie belonging to the app itself: first-party, not Keycloak's.

```txt
The classic "public client in the browser" (articles 01-05):

  Browser ──(Auth Code + PKCE)──► Keycloak
  Browser ──(holds the access/refresh token)──► stores it directly
  Browser ──(Authorization: Bearer <token>)──► NestJS API

The BFF pattern:

  Browser ──(a plain HTTP session: one first-party
             session cookie)──► BFF
  BFF, a server and not the browser
       ──(Auth Code + PKCE; client_secret lives here,
          the BFF is a confidential client)──► Keycloak
  BFF ──(holds the access/refresh token on the server,
          in its own session store or Redis)──►
  BFF ──(proxies the request and attaches the real
          access token)──► NestJS API
```

```txt
Step-by-step request flow:

1. Browser → GET /login (on the BFF, not directly on Keycloak)
2. The BFF generates a code_verifier and redirects the browser to
   Keycloak's /authorize (Auth Code + PKCE; the BFF now acts as
   the client)
3. The user logs in on Keycloak as usual
4. Keycloak redirects the browser to the BFF's callback URL with
   an authorization code
5. The BFF exchanges the code for access/id/refresh tokens over
   the back-channel, server to server. These tokens never appear
   in an HTTP response to the browser
6. The BFF creates its own session (a session ID) and stores the
   Keycloak tokens in a server-side store (Redis or a DB) keyed
   by that session ID. The browser gets only an httpOnly
   first-party cookie holding the BFF's session ID, not a
   Keycloak token
7. Further requests: browser → GET /api/orders (a plain BFF
   session cookie) → the BFF looks up the session ID from the
   cookie → fetches the stored access token from Redis →
   proxies the request to the NestJS Resource Server with
   Authorization: Bearer <the real token>
8. Refresh: the BFF itself tracks the TTL of the stored access
   token and refreshes it via the refresh token. All of that
   happens on the server: the browser is never involved and
   never even knows a refresh happened
```

```typescript
// NestJS BFF — a simplified session-based proxy endpoint
@Controller()
export class BffController {
  constructor(
    private sessionStore: SessionTokenStore, // Redis-backed store keyed by sessionId
    private http: HttpService,
  ) {}

  @Get('callback')
  async handleCallback(
    @Query('code') code: string,
    @Req() req: Request,
    @Res() res: Response,
  ) {
    const tokens = await this.exchangeCodeForTokens(code); // back-channel POST /token

    const sessionId = randomUUID();
    await this.sessionStore.save(sessionId, tokens); // tokens live only on the server

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
    // getFreshTokens renews the access token itself once it has expired
    const tokens = await this.sessionStore.getFreshTokens(sessionId);

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

Note that `bff_session` is not a JWT (JSON Web Token) and not a Keycloak token. It is an opaque session ID for the BFF's own session. Semantically it is the same thing as any traditional server-side web session. A classic Express or Rails app used exactly this kind of cookie long before OAuth2 existed.

This is exactly why the BFF eliminates the third-party cookie problem from article 05 architecturally. There is no foreign Keycloak domain whose cookie you would have to read from an iframe, so silent-check-sso isn't needed at all. Authentication goes through the app's own first-party cookie, which the browser sends to its **own** domain the ordinary way, like any other web session.

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

  ✓ Tokens never physically exist in the browser — even a successful
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

A practical recommendation, not a universal verdict. **For a new project with real security requirements — fintech, healthcare, internal corporate systems — the BFF is a reasonable default starting point today.**

It removes a whole class of problems architecturally, rather than patching around them. A growing body of guidance leans toward exactly this pattern, including the OAuth 2.0 Security Best Current Practice and its recommendations for browser-based apps.

For a small MVP (minimum viable product) or a low-stakes internal tool, the classic public-client approach from articles 01-05 is still perfectly adequate. It is also much faster to build. Treat that as a deliberate trade-off: speed and simplicity now against a smaller attack surface. It should never be "we just didn't know about the BFF."

## Tying it together

```txt
[In-memory / localStorage /
 httpOnly cookie]           →  each option trades XSS risk for CSRF
                               risk, or for lost state on refresh.
                               There is no free option — except
                               localStorage, which loses on every
                               axis at once

[httpOnly ≠ secure by
 itself]                    →  needs SameSite + Secure + a precise
                               CORS config: the same engineering
                               discipline, just a different set of
                               requirements

[BFF]                       →  an architectural removal of the
                               problem — tokens never leave the
                               server, and the browser only ever
                               deals with a plain first-party web
                               session

[BFF vs public client
 trade-off]                 →  a smaller attack surface and a solved
                               third-party cookie problem, against
                               an extra server-full component and
                               latency: a real architectural choice,
                               not "progress vs the old way"
```

The next article is [Security Hardening and Attack Vectors](./07-security-hardening-and-attack-vectors.md). It gives a full, dedicated treatment to the mechanisms mentioned in passing here and earlier. Those are PKCE (Proof Key for Code Exchange), state, nonce, redirect validation, and JWT algorithm confusion. The focus there is attack and defense.

## Common interview traps

- **"localStorage is convenient and secure enough if the app is generally well protected against XSS"** — a risky answer. "Well protected against XSS" is never a guarantee: one vulnerable dependency in the npm tree is enough. For that case localStorage gives zero defense in depth, unlike an httpOnly cookie or in-memory storage. A good answer treats tokens in localStorage as a position you cannot defend, not as "a good practice under certain conditions."

- **"An httpOnly cookie fully solves the token security problem"** — incomplete. It closes off XSS reading, but opens a CSRF vector that needs its own mandatory defense: `SameSite` and a precise CORS config. An answer that doesn't mention CSRF shows a shallow grasp of the topic.

- **"A BFF is just a proxy, it gives no real security benefit, just an extra hop"** — an underestimate. A BFF removes the token from the browser **architecturally**; it does not merely relocate it. That changes the attack surface itself: XSS can no longer steal an access or refresh token, because there is physically nowhere to read it from. This is not an added network layer with no purpose.

- **"A BFF is always the right choice, a public client in the browser is outdated"** — an overreach. A BFF adds real operational complexity: a server-full component, latency, and one more critical attack target. That cost is justified for applications with high security stakes. It is not an unconditionally better choice for every project — MVPs and internal tools often pick the simpler public-client approach for good reasons.

- **"Since tokens are stored server-side in a BFF, refresh token rotation is no longer needed"** — no. Rotation (article 03) protects the refresh token **as an artifact**, whatever the source of the theft. It does not matter whether the token was taken from the browser or from a compromised BFF server-side store, such as a misconfigured Redis instance. A BFF lowers the odds of one theft vector. It does not remove the value of rotation as a separate way to detect a breach.
