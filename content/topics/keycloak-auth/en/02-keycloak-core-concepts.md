# Keycloak — the object model

This article is the map of Keycloak's object model: Realm, Client, User, Role, Group, Client Scope. Articles 04 and 05 attach concrete NestJS and React code to that map.

Keycloak is not "a black box that spits out JSON Web Tokens (JWT)". It is an OpenID Connect (OIDC) server with a fairly strict object model. Without that model, configuring Keycloak is clicking around the admin console by trial and error. Any confusing production issue then gets debugged blind: a claim missing from the token, an LDAP (Lightweight Directory Access Protocol) user who cannot log in.

## Realm — an isolated "tenant" inside a single Keycloak

A **Realm** is a fully isolated space. It has its own users, clients, roles and themes, plus its own security settings: password policy, brute-force protection, token lifetimes (TTL). Two realms on the same Keycloak instance can't see each other's data at all. It is as if they were two separate Keycloak servers that happen to run on the same host.

```txt
┌─────────────────────────────────────────────────┐
│ Keycloak instance                               │
├─────────────────────────────────────────────────┤
│ Realm "acme-internal"                           │
│   Users: company employees                      │
│   Clients: internal-admin-panel, hr-service     │
│   Password policy: strict, MFA required         │
├─────────────────────────────────────────────────┤
│ Realm "acme-customers"                          │
│   Users: product customers                      │
│   Clients: customer-web-app, mobile-app         │
│   Password policy: looser, social login enabled │
└─────────────────────────────────────────────────┘
```

Realm is the unit at which you decide "multi-tenancy = separate realms or a shared realm with groups". A full trade-off breakdown lives in [Advanced Patterns](./08-advanced-patterns.md). Here we only fix the fact that a Realm **can** be a tenant boundary, without that being mandatory.

A separate realm always exists: `master`, created by default on install. **The `master` realm is meant for administering Keycloak itself** — creating other realms, managing server-level settings. Real application users should never log in through `master`. A common early-project mistake is inertia: continuing to configure everything in `master` instead of creating a dedicated realm for the app right away.

## Client — who talks to Keycloak, and how

A **Client** in Keycloak terms is the registration of a specific application inside a realm. It is the OAuth2 "Client" role from [OAuth2 / OIDC Fundamentals](./01-oauth2-oidc-fundamentals.md). A client's config includes allowed grant types, `redirect_uri` and per-client token lifetimes. The most important part architecturally is the **client type**:

|  | Can hold a secret? | Typical example |
|---|---|---|
| Public | No | React SPA (single-page app), mobile app — the code runs on the user's device, where a secret can't be protected |
| Confidential | Yes | NestJS backend, or a backend-for-frontend service — code runs on your team's server, so the secret can live in env or a secret manager |
| Bearer-only | Doesn't log anyone in | A pure Resource Server — an API that only **validates** tokens issued for another client, and never starts an OAuth2 flow |

`public` in Keycloak literally means "this client's `client_secret` is empty, and Keycloak won't require it on the code→token exchange". That is exactly why PKCE (Proof Key for Code Exchange) isn't optional for public clients — it's a mandatory defense. Without a secret and without PKCE, anyone who intercepts the code could complete the exchange.

`bearer-only` is a type people often confuse with "confidential, but for an API". The difference is fundamental. A bearer-only client **has no login endpoint and can't initiate an Authorization Code flow**. It exists so that the Keycloak Admin Console has somewhere to configure client roles for that API, and to validate the `aud` (audience) claim.

In practice a NestJS resource server is often not registered as a separate Keycloak client at all. A token issued to the React SPA — a public client — gets validated on the backend directly via JWKS (JSON Web Key Set). Both [Tokens, Sessions, and Validation](./03-tokens-sessions-and-validation.md) and [NestJS Resource Server](./04-nestjs-resource-server.md) cover that.

A bearer-only client is useful when you specifically need to separate `aud` between different APIs.

```bash
# Creating a confidential client via the Admin REST API
curl -X POST https://keycloak.example.com/admin/realms/myrealm/clients \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "clientId": "backend-service",
    "publicClient": false,
    "serviceAccountsEnabled": true,
    "standardFlowEnabled": false,
    "directAccessGrantsEnabled": false
  }'
```

Note `serviceAccountsEnabled: true` — the flag that turns on the Client Credentials Grant for a client. Keycloak calls this a "service account". It even gets its own technical user, `service-account-backend-service`, that roles can be assigned to.

## Users, Groups, Roles — the authorization model

### Realm roles vs Client roles

Roles in Keycloak come in two flavors, and the difference isn't syntactic — it's semantic:

```txt
Realm role:
  Exists at the level of the WHOLE realm. Example: "admin",
  "premium-user". Meaningful across all clients in the realm
  at once.
  Token claim: realm_access.roles: ["admin", "premium-user"]

Client role:
  Exists in the CONTEXT of one specific client. Example: the
  client "billing-service" can have a role "invoice:write"
  that makes no sense for any other client.
  Token claim:
    resource_access.billing-service.roles: ["invoice:write"]
```

```json
{
  "sub": "a1b2c3",
  "realm_access": {
    "roles": ["offline_access", "premium-user"]
  },
  "resource_access": {
    "billing-service": {
      "roles": ["invoice:write", "invoice:read"]
    },
    "account": {
      "roles": ["manage-account"]
    }
  }
}
```

A practical rule of thumb. If a permission makes sense for the user in general, regardless of which API they use, that's a realm role. If it's specific to one service — "can this user delete invoices in billing-service" — that's a client role of that service.

A common beginner mistake is to make everything a realm role "because it's simpler". Over time that turns `realm_access.roles` into a pile of fifty unrelated roles, with no clue which one belongs to which service.

### Composite roles

A **Composite role** is a role that, when assigned to a user, automatically "unpacks" into a set of other roles.

```txt
Composite role "app-admin" includes:
  realm role "premium-user"
  + client role billing-service:"invoice:write"
  + client role billing-service:"invoice:read"
  + client role admin-panel:"users:manage"

Assigning the SINGLE role "app-admin" to a user →
  all 4 roles from the composite appear in the token automatically
```

Composite roles model "job titles" or "pricing tiers" as a single assignment. Without them you maintain a list of a dozen separate roles per user by hand.

A senior-level nuance: composite roles make assignment easier but auditing harder. Looking at a user, you only see "app-admin". The full list of actual permissions has to be expanded separately, through the Admin API or the "Effective Roles" tab in the console.

### Groups — assigning roles to many users at once

A **Group** is a way to assign a set of roles (and attributes) to many users at once, without composite roles per user. Groups support hierarchy (`/company/engineering/backend`), and roles assigned to a parent group are inherited by child groups.

```txt
Group "/company/engineering"
  → realm role "internal-tool-access"

Group "/company/engineering/backend" (inherits /engineering)
  → client role backend-service:"deploy"

A user in /company/engineering/backend gets BOTH roles:
  "internal-tool-access" (inherited) + "deploy" (its own)
```

The difference between a Group and a Composite Role is a frequent question. A composite role is a "this role includes these roles" relationship, applied wherever that role gets assigned. A group is a "this user belongs to this organizational unit" relationship. A group can also carry attributes (`department: backend`), and it is administered along the company's org chart rather than an abstract bag of permissions.

## Client Scopes and Protocol Mappers — how token content is actually shaped

This is the mechanism that answers "how does a scope from article 01 turn into actual claims in the JWT". It is a practical skill needed in almost every real project: custom claims for business logic, such as `tenantId`, `subscriptionTier` or an internal `permissions` array.

A **Client Scope** is a named, reusable bundle of configuration that can be attached to any number of clients. Standard scopes (`profile`, `email`, `roles`) ship with Keycloak out of the box; custom ones you create yourself.

A **Protocol Mapper** is a concrete rule inside a client scope. It says: take this piece of data and put it in the token under this claim name. The data can be a user attribute, a role, a static value or a script.

```txt
Client Scope "tenant-info" (custom, created manually)
  └─ Protocol Mapper "tenant-id-mapper"
       Type: "User Attribute"
       User Attribute:  tenantId
         (a custom user attribute in Keycloak)
       Token Claim Name: tenant_id
       Add to ID token: ✓
       Add to access token: ✓
```

```bash
# Creating a protocol mapper via the Admin REST API —
# adds the custom user attribute tenantId as the tenant_id claim
KC_REALM=https://keycloak.example.com/admin/realms/myrealm
curl -X POST \
  "$KC_REALM/client-scopes/$SCOPE_ID/protocol-mappers/models" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "tenant-id-mapper",
    "protocol": "openid-connect",
    "protocolMapper": "oidc-usermodel-attribute-mapper",
    "config": {
      "user.attribute": "tenantId",
      "claim.name": "tenant_id",
      "jsonType.label": "String",
      "id.token.claim": "true",
      "access.token.claim": "true"
    }
  }'
```

Result in the token:

```json
{
  "sub": "a1b2c3",
  "tenant_id": "acme-corp",
  "realm_access": { "roles": ["premium-user"] }
}
```

A Client Scope is then attached to a client as **Default** or **Optional**. Default means the scope is added to the token automatically on any login by that client. Optional means it is added only if the client asked for it in the `scope=` parameter on the redirect to `/authorize`.

This is a direct continuation of the "scope requests, claim appears" mechanics from article 01, except now you can see **where** that link is configured.

A practical scenario worth mentioning. The frontend suddenly stops seeing an expected claim in the token, right after someone "tidied up" Keycloak and detached a client scope from a client. That is not a frontend bug and not a library bug — it is a pure Keycloak configuration issue. Diagnose it on the client's "Client Scopes" tab: check whether the needed scope is in Default, or requested explicitly.

## Identity Brokering vs User Federation — the pair developers systematically mix up

Both mechanisms are about an external source of users, and both look like "logging in through something else". They solve fundamentally different problems. An external identity provider (IdP) can speak either OIDC or SAML (Security Assertion Markup Language). SAML predates OIDC and carries its assertions as XML (extensible markup language) documents.

```txt
Identity Brokering:
  Keycloak delegates AUTHENTICATION to an external Identity
  Provider (Google, GitHub, another Keycloak, any OIDC or
  SAML provider). The user clicks "Log in with Google" →
  gets redirected to Google → logs in there → Google returns
  a token or assertion to Keycloak → Keycloak creates a local
  "shadow" account (a linked account) in its own realm, tied
  to the external sub.

  Keycloak never sees the user's password at all.
  Who it's for:  "Log in with Google / GitHub / corporate
                 Azure AD"
  Key point:     Keycloak is an OAuth2 Client with respect to
                 the external IdP

User Federation:
  Keycloak authenticates the user ITSELF (checks the
  password), but the user's data — and the password check —
  live in an existing external store. Typically that is LDAP
  or Active Directory, reached through a federation provider:
  the built-in LDAP provider, or a Custom User Storage SPI
  for an arbitrary source.

  Keycloak makes an LDAP bind request with the entered
  password on login.
  Who it's for:  "The company already has an Active Directory
                 with 5,000 employees; Keycloak should use
                 THEIR accounts rather than duplicate the
                 database"
  Key point:     Keycloak is an OIDC/SAML facade on top of an
                 existing user directory
```

```txt
Identity Brokering:              User Federation:

  User → Keycloak                  User → Keycloak
    → [redirect]                     → [LDAP bind]
    → external IdP (Google)          → Active Directory
    (Keycloak = OAuth2 Client        (Keycloak = a facade,
     relative to Google)              the password is
                                      checked in AD)
```

A mnemonic that actually helps: **Identity Brokering is "one more button on the login screen"**. The user chooses how to authenticate, and that choice is visible to them.

**User Federation is "an invisible backend"** for Keycloak's standard login form. The user types a username and password as usual; behind the scenes that data is verified against LDAP, not Keycloak's own database. You can combine them: local users, LDAP federation and Google brokering all at once in one realm.

## Authentication Flows — a step-builder for login

An **Authentication Flow** is a configurable sequence of steps a user goes through during login, or during other actions such as password reset and registration. The default `browser` flow already includes three steps. First a check for a cookie from an existing single sign-on (SSO) session, then a login form, then — optionally — a one-time password (OTP) check.

Each step has a requirement:

- **Required** — mandatory.
- **Alternative** — one of several equally valid options, password or WebAuthn for example.
- **Conditional** — runs only if a condition holds, such as "if the user has the admin role, require OTP".

```txt
Example custom flow "Login with conditional OTP":

  Cookie (checks the SSO session)     [ALTERNATIVE]
  Username Password Form              [REQUIRED]
  └─ Condition: user has role "admin" [CONDITIONAL]
      └─ OTP Form                     [REQUIRED in the condition]
```

This is the direct mechanism for step-up authentication. Not global multi-factor authentication (MFA) for everyone, but a targeted second-factor requirement for specific roles, groups or clients. It is configured declaratively in the flow builder, with zero code in the application itself. Detailed scenarios are in [Advanced Patterns](./08-advanced-patterns.md).

## Themes — customizing the login screen

A **Theme** is a bundle of FreeMarker templates plus CSS and JS. It defines how the pages Keycloak itself renders look: login, registration, email templates, error pages.

An important architectural fact: the login page is **a Keycloak page**, not a page of your React app. The user physically leaves the SPA's domain for the duration of authentication. That is part of the Authorization Code flow's security model — the frontend code should never get the password into its hands.

```txt
┌───────────────────────────────────────────────────┐
│ app.example.com — your React SPA                  │
└───────────────────────────────────────────────────┘
                          │  redirect to /authorize
                          ▼
┌───────────────────────────────────────────────────┐
│ keycloak.example.com — Keycloak renders the login │
│ page itself, from a Theme                         │
└───────────────────────────────────────────────────┘
                          │  redirect back with the code
                          ▼
┌───────────────────────────────────────────────────┐
│ app.example.com — the SPA continues               │
└───────────────────────────────────────────────────┘
```

A theme is how you make that page, foreign but mandatory, look branded instead of like the default Keycloak admin skin.

## Admin REST API and Keycloak-as-Code — operational maturity

Everything shown above via `curl` also works through Keycloak's full **Admin REST API**. It is a REST (representational state transfer) interface — a plain HTTP API. Keycloak is managed through the same OAuth2/OIDC mechanics: calling the admin API needs an access token from a service client with admin roles.

Clicking through realm configuration by hand works fine for a single dev environment. It doesn't scale to "dev + staging + prod + temporary environments for feature branches". The configuration inevitably drifts, and six months later nobody can answer why prod's password policy differs from staging's.

The senior practice is **realm-as-code**: keep all of a realm's configuration — clients, roles, client scopes, flows — as declarative files in git, applied automatically:

```txt
keycloak-config-cli:
  A tool (Java, by adorsys) that takes a YAML/JSON description of
  a realm and idempotently brings the real Keycloak instance to that
  state via the Admin REST API — can run in CI/CD on every deploy.

Keycloak Terraform Provider (mrparkers/keycloak or
                              the current keycloak/keycloak):
  Same principle, expressed as Terraform resources
  (keycloak_realm, keycloak_openid_client, keycloak_role) —
  convenient if the rest of your infrastructure is already described
  in Terraform, gives you a plan/apply cycle and an explicit diff
  before changes are applied.
```

```yaml
# A fragment of a keycloak-config-cli configuration
realm: myrealm
clients:
  - clientId: backend-service
    publicClient: false
    serviceAccountsEnabled: true
    standardFlowEnabled: false
roles:
  realm:
    - name: premium-user
      description: "Access to premium features"
```

This isn't bureaucracy for its own sake. The Realm is the source of truth for authorization across the whole system. If it's configured by clicking around with no version history, rolling back a bad change becomes an investigation by memory, not a `git revert`. A typical bad change: someone accidentally removed the service account from a prod client.

## Tying it together

```txt
[Realm]                  →  an isolated configuration
                            boundary; "realm-per-tenant vs
                            shared" is an architectural
                            decision (Advanced Patterns)

[Client type]            →  public / confidential /
                            bearer-only, determined by
                            whether the client can safely
                            hold a secret

[Realm role / Client
 role / Composite /
 Group]                  →  four ways to model "what's
                            allowed", each at its own
                            granularity

[Client Scope +
 Protocol Mapper]        →  the mechanism that turns a scope
                            into actual token claims — what
                            you configure for any custom
                            field in a JWT

[Identity Brokering vs
 User Federation]        →  "an external IdP does the
                            authenticating" vs "an external
                            directory holds the passwords,
                            and Keycloak checks them itself"

[Authentication Flows]   →  a step-builder for login —
                            declarative step-up with zero
                            application code

[Realm-as-code]          →  operational maturity: Keycloak
                            configuration as part of a git
                            repo, not console clicks
```

The next article, [Tokens, Sessions, and Validation](./03-tokens-sessions-and-validation.md), moves from "how Keycloak is configured" to what happens to an already-issued token on the API side. It covers how the token is validated, and what JWKS and `kid` are. It also covers logout in a system where a session exists both on Keycloak and, in effect, on the client.

## Common interview traps

- **"A Realm is just a folder for organizing clients"** — an underestimate. A Realm is full isolation: users, password policies, brute-force protection, themes. It is not just a namespace for grouping. Two clients in different realms can't directly reuse each other's roles or users without explicit Identity Brokering between the realms.

- **"A bearer-only client is the same as a confidential client, just for an API"** — no. A confidential client **can** initiate a flow, for example Client Credentials for service-to-service. A bearer-only client can't initiate an OAuth2 flow at all. It only validates other clients' tokens and exists to separate roles and audience for a specific API.

- **"Identity Brokering and User Federation are the same thing, just different names for 'logging in via LDAP/Google'"** — a fundamental confusion. Brokering means Keycloak doesn't check anything itself: it redirects to an external OIDC or SAML identity provider. Federation means Keycloak checks the password itself, for example with an LDAP bind. The data source is just an external directory, not the built-in database.

- **"Composite role and Group are interchangeable ways to group permissions"** — no. A composite role is a property of the role itself: it unpacks wherever it's assigned, anywhere. A group is an org unit with its own hierarchy and attributes, to which users and roles get attached. They have different administrative semantics, even if the resulting set of user permissions can look the same.

- **"Claims in a token can only be changed via backend code"** — no. This is a common mistake among people unfamiliar with Protocol Mappers. Adding a custom claim, say `tenant_id`, is Keycloak configuration: a Client Scope plus a Protocol Mapper, not code on the API side. Writing code for this would mean solving the problem at the wrong layer of the architecture.
