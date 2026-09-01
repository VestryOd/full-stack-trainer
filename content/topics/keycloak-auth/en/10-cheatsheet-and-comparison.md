# Cheat Sheet and Comparison

Reference material for articles 01-09 — no new concept explanations, just compact tables and snippets. If a term is unclear, it's covered in detail in the article referenced in the section header.

## Part 1: Cheat Sheet

### Choosing a grant type (article 01)

| Client | Grant Type | Is there a user? | Can it hold a secret? | Status |
|---|---|---|---|---|
| React SPA (single-page application) / mobile app | Authorization Code + PKCE (Proof Key for Code Exchange) | Yes | No (public client) | ✅ current |
| A backend calling Keycloak on behalf of a user | Authorization Code + PKCE (not strictly required here, but always recommended) | Yes | Yes (confidential) | ✅ current |
| Service A → Service B (no user) | Client Credentials | No | Yes (confidential) | ✅ current |
| Any device with poor input: smart television, console, CLI (command-line interface) | Device Code | Yes (on a **different** device) | No | ✅ current |
| ~~A login form inside the client~~ | ~~ROPC (Resource Owner Password Credentials)~~ | Yes | Doesn't matter | ❌ deprecated |
| ~~A token in the URL fragment~~ | ~~Implicit~~ | Yes | No | ❌ deprecated |

### JWT claims in a Keycloak token (articles 01-03)

JWT stands for JSON Web Token — the signed, self-describing token format Keycloak issues.

| Claim | Meaning | Appears in |
|---|---|---|
| `iss` | Issuer — the URL of the realm that issued the token | Access, ID, Refresh |
| `sub` | Subject — the unique ID of the user (or service account) | Access, ID |
| `aud` | Audience — who the token is meant for | Access, ID |
| `azp` | Authorized party — the client_id the token was issued to | Access, ID |
| `exp` / `iat` | Expiry / issued-at (a Unix timestamp) | Access, ID, Refresh |
| `jti` | JWT ID — a unique token identifier (for revocation/blacklisting) | Access, ID |
| `sid` | Session ID — ties the token to a Keycloak server-side session | Access, ID |
| `acr` | Authentication Context Class Reference — the auth assurance level (article 08, step-up) | Access, ID |
| `realm_access.roles` | Realm roles (article 02) | Access |
| `resource_access.<client>.roles` | Client roles for a specific client (article 02) | Access |
| `scope` | The list of granted OAuth2 scopes | Access |
| `email`, `name`, `preferred_username` | Identity claims (from the `profile`/`email` scopes) | ID (and Access if configured) |
| `nonce` | The value used for ID Token replay protection (article 07) | ID |

### keycloak-js — core methods (article 05)

| Method | Purpose |
|---|---|
| `new Keycloak(config)` | Create an adapter instance (url, realm, clientId) |
| `keycloak.init(options)` | Initialize; `onLoad: 'check-sso' \| 'login-required'` |
| `keycloak.login(options?)` | Redirect to Keycloak login; `redirectUri` — where to come back to |
| `keycloak.logout(options?)` | Redirect to Keycloak logout (front-channel) |
| `keycloak.updateToken(minValidity)` | Refresh the token if fewer than minValidity seconds remain; makes no call if the token is already fresh |
| `keycloak.token` / `keycloak.tokenParsed` | The current access token (raw JWT / parsed payload) |
| `keycloak.loadUserProfile()` | Fetch the user profile (via Keycloak's Account API) |
| `keycloak.hasRealmRole(role)` / `hasResourceRole(role, client)` | Check roles on the client (doesn't replace a backend check!) |
| `keycloak.authenticated` | Boolean — whether the user is logged in after `init()` |

### PKCE — the minimal generation snippet (article 07)

```typescript
function base64UrlEncode(buffer: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(buffer)))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function generateCodeVerifier(): string {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return base64UrlEncode(array.buffer);
}

async function generateCodeChallenge(verifier: string): Promise<string> {
  const data = new TextEncoder().encode(verifier);
  const digest = await crypto.subtle.digest('SHA-256', data);
  return base64UrlEncode(digest);
}
```

### NestJS — a minimal JWT guard via JWKS (articles 03-04)

JWKS is the JSON Web Key Set: the public keys Keycloak publishes so that anyone can check a signature.

```typescript
export class KeycloakJwtStrategy extends PassportStrategy(Strategy, 'jwt') {
  constructor(config: ConfigService) {
    super({
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      algorithms: ['RS256'], // always hardcoded — see article 07, algorithm confusion
      secretOrKeyProvider: passportJwtSecret({
        jwksUri: `${config.get('KEYCLOAK_ISSUER')}/protocol/openid-connect/certs`,
        cache: true,
        rateLimit: true,
      }),
      issuer: config.get('KEYCLOAK_ISSUER'),
    });
  }
  validate(payload: KeycloakJwtPayload) {
    return payload;
  }
}
```

### BFF — the request flow in one diagram (article 06)

BFF stands for Backend-for-Frontend.

```txt
Browser  ──(first-party session cookie)──►  BFF

BFF      ──(Auth Code + PKCE, back-channel)──►  Keycloak
              the client_secret lives here

BFF      ──(stores access/refresh tokens in Redis or a
              database, keyed by sessionId)

BFF      ──(proxies the request, header
              Authorization: Bearer <real token>)──► Resource Server

The browser never sees the access, refresh or ID token.
```

## Part 2: Comparison

Five facts per option: what it is for, what it does, where it is typically used, its security posture and its operational cost.

### Auth Code + PKCE

- **For:** interactive user login.
- **Does:** sends a code over the front-channel, exchanges it for tokens over the back-channel, and verifies the `code_verifier`.
- **Typical use:** any client with a browser or UI (user interface) — SPA, mobile app, server-side web app.
- **Security:** high — protected against code interception regardless of client type.
- **Operational cost:** low — built into any decent OIDC (OpenID Connect) library.

### Client Credentials

- **For:** service-to-service calls, with no user.
- **Does:** a direct back-channel exchange of `client_id` plus secret for a token.
- **Typical use:** internal microservices, cron jobs, integrations with no human involved.
- **Security:** high, provided the `client_secret` is protected — a secret manager, not an env var in code.
- **Operational cost:** low — one HTTP call plus a cached token.

### Device Code

- **For:** devices with limited input.
- **Does:** polls for a token while the user logs in on a **different** device.
- **Typical use:** smart televisions, consoles, CLI tools.
- **Security:** high — the password is never typed on the device itself.
- **Operational cost:** medium — needs a polling mechanism, and a UX (user experience) for showing the code.

### BFF Pattern

- **For:** removing tokens from the browser architecturally.
- **Does:** keeps a server-side session and proxies to the Resource Server carrying the real token.
- **Typical use:** fintech, healthcare, enterprise apps with high security stakes.
- **Security:** the maximum available for browser-based scenarios — XSS (cross-site scripting) cannot steal the token.
- **Operational cost:** high — an extra component to run on a server, extra latency, an extra critical attack target.

### Public client in the browser

- **For:** direct SPA-to-API calls.
- **Does:** keeps the token in the browser (memory or cookie) and attaches it to requests.
- **Typical use:** MVPs (minimum viable products), internal tools, low-stakes apps.
- **Security:** medium — a trade-off between XSS, CSRF (Cross-Site Request Forgery) and UX, covered in article 06.
- **Operational cost:** low — the SPA can be pure static hosting.

### Keycloak

- **For:** a self-hosted OIDC/OAuth2 Identity Provider.
- **Does:** gives a full object model — realms, clients, roles, Authorization Services.
- **Typical use:** companies with a dedicated platform team, and strict compliance or data-residency requirements.
- **Security:** as high as the team's operating discipline makes it.
- **Operational cost:** high — HA (high availability), patching, upgrades, monitoring (article 08).

### Auth0

- **For:** managed identity-as-a-service.
- **Does:** gives a ready-made UI, Actions and Rules for customization, and broad SDK (software development kit) coverage.
- **Typical use:** startups and products where speed to market matters.
- **Security:** high, maintained by the provider.
- **Operational cost:** MAU (monthly active users) billing — low at first, can spike sharply with scale.

### Okta

- **For:** managed identity, historically strong in enterprise and workforce identity.
- **Does:** integrates deeply with corporate SSO (single sign-on) systems.
- **Typical use:** enterprise B2E (business-to-employee), companies with existing Okta infrastructure.
- **Security:** high, maintained by the provider.
- **Operational cost:** MAU or seat billing, enterprise contracts.

### AWS Cognito

- **For:** managed identity, deeply integrated with the AWS (Amazon Web Services) ecosystem.
- **Does:** User Pools plus Identity Pools, with Lambda triggers for customization.
- **Typical use:** products already fully built on AWS.
- **Security:** high, maintained by AWS.
- **Operational cost:** MAU billing, usually cheaper than Auth0 or Okta at volume.

### Supabase Auth

- **For:** a managed or self-hostable simple start.
- **Does:** GoTrue — simplified OIDC-like auth as part of the Supabase stack.
- **Typical use:** MVPs, small-to-medium Supabase-based projects.
- **Security:** medium-high for standard scenarios, without Keycloak's enterprise depth.
- **Operational cost:** low — minimal configuration.

### A home-grown auth system

- **For:** full control and zero dependencies.
- **Does:** your own users table, your own JWT-issuing code, your own bcrypt.
- **Typical use:** rarely justified for a new project in 2024 or later.
- **Security:** entirely on your team — MFA (multi-factor authentication), rate limiting and security best practices are built and maintained by hand.
- **Operational cost:** hidden and constantly growing. Every security feature Keycloak or Auth0 give you out of the box is written and maintained by hand here.
