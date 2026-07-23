# Cheat Sheet and Comparison

Reference material for articles 01-09 — no new concept explanations, just compact tables and snippets. If a term is unclear, it's covered in detail in the article referenced in the section header.

## Part 1: Cheat Sheet

### Choosing a grant type (article 01)

| Client | Grant Type | Is there a user? | Can it hold a secret? |
|---|---|---|---|
| React SPA / mobile app | Authorization Code + PKCE | Yes | No (public client) |
| A backend calling Keycloak on behalf of a user | Authorization Code + PKCE (PKCE not strictly required, but always recommended) | Yes | Yes (confidential) |
| Service A → Service B (no user) | Client Credentials | No | Yes (confidential) |
| A smart TV / CLI / device with poor input | Device Code | Yes (on a DIFFERENT device) | No |
| ~~A login form inside the client~~ | ~~ROPC (password)~~ | Yes | Doesn't matter | ❌ deprecated |
| ~~A token in the URL fragment~~ | ~~Implicit~~ | Yes | No | ❌ deprecated |

### JWT claims in a Keycloak token (articles 01-03)

| Claim | Meaning | Appears in |
|---|---|---|
| `iss` | Issuer — the URL of the realm that issued the token | Access, ID, Refresh |
| `sub` | Subject — the unique ID of the user (or service account) | Access, ID |
| `aud` | Audience — who the token is meant for | Access, ID |
| `azp` | Authorized party — the client_id the token was issued to | Access, ID |
| `exp` / `iat` | Expiry / issued-at (a UNIX timestamp) | Access, ID, Refresh |
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
| `keycloak.loadUserProfile()` | Fetch the user profile (via Keycloak's Account REST API) |
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

```typescript
export class KeycloakJwtStrategy extends PassportStrategy(Strategy, 'jwt') {
  constructor(config: ConfigService) {
    super({
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      algorithms: ['RS256'], // ALWAYS hardcoded — see article 07, algorithm confusion
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

```txt
Browser ──(first-party session cookie)──► BFF
BFF ──(Auth Code+PKCE, back-channel, client_secret lives HERE)──► Keycloak
BFF ──(access/refresh tokens stored in Redis/a DB, keyed by sessionId)
BFF ──(proxies the request, Authorization: Bearer <the real token>)──► Resource Server

The browser NEVER sees the access/refresh/ID token.
```

## Part 2: Comparison

| | What it's for | What it does | Typical real-world use | Security posture | Operational cost |
|---|---|---|---|---|---|
| **Auth Code + PKCE** | Interactive user login | A code over the front-channel, exchanged for tokens over the back-channel + code_verifier verification | Any client with a browser/UI: SPA, mobile app, server-side web app | High — protected against code interception regardless of client type | Low — built into any decent OIDC library |
| **Client Credentials** | Service-to-service, no user | A direct back-channel exchange of client_id+secret for a token | Internal microservices, cron jobs, integrations with no human involved | High, provided the client_secret is protected (a secret manager, not an env var in code) | Low — one HTTP call + a cached token |
| **Device Code** | Limited-input devices | Polling for a token while the user logs in on a DIFFERENT device | Smart TVs, consoles, CLI tools | High — the password is never typed on the device itself | Medium — needs a polling mechanism and UX for showing the code |
| **BFF Pattern** | Architecturally removing tokens from the browser | A server-side session + a proxy to the Resource Server carrying the real token | Fintech, healthcare, enterprise apps with high security stakes | Maximum for browser-based scenarios — XSS can't steal the token | High — an extra server-full component, latency, an extra critical attack target |
| **Public client in the browser** | Direct SPA-to-API calls | The token lives in the browser (memory/cookie), attached to requests | MVPs, internal tools, low-stakes apps | Medium — a trade-off between XSS/CSRF/UX, covered in article 06 | Low — the SPA can be pure static hosting |
| **Keycloak** | Self-hosted OIDC/OAuth2 Identity Provider | A full object model (realms, clients, roles, Authorization Services) | Companies with a dedicated platform team, strict compliance/data-residency requirements | As high as the team's operating discipline makes it | High — HA, patching, upgrades, monitoring (article 08) |
| **Auth0** | Managed identity-as-a-service | A ready-made UI, Actions/Rules for customization, broad SDK coverage | Startups and products where speed to market matters | High, maintained by the provider | MAU billing — low at first, can spike sharply with scale |
| **Okta** | Managed, historically strong in enterprise/workforce identity | Deep integration with corporate SSO systems | Enterprise B2E, companies with existing Okta infrastructure | High, maintained by the provider | MAU/seat billing, enterprise contracts |
| **AWS Cognito** | Managed, deep integration with the AWS ecosystem | User Pools + Identity Pools, Lambda triggers for customization | Products already fully built on AWS | High, maintained by AWS | MAU billing, usually cheaper than Auth0/Okta at volume |
| **Supabase Auth** | Managed/self-hostable, a simple start | GoTrue — simplified OIDC-like auth as part of the Supabase stack | MVPs, small-to-medium Supabase-based projects | Medium-high for standard scenarios, without Keycloak's enterprise depth | Low — minimal configuration |
| **A home-grown auth system** | Full control, zero dependencies | Your own users table, your own JWT-issuing code, your own bcrypt | Rarely justified for a new project in 2024+ | Entirely on your team — MFA/rate-limiting/security best practices have to be built and maintained yourself | Hidden and constantly growing — every security feature Keycloak/Auth0 give you out of the box is written and maintained by hand here |
