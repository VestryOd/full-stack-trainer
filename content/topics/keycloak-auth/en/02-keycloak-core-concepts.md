# Keycloak — the object model

## Why the model matters before the code does

Keycloak isn't "a black box that spits out JWTs" — it's a system with a fairly strict object model: Realm, Client, User, Role, Group, Client Scope. Without understanding that model, configuring Keycloak turns into clicking around the admin console by trial and error ("I'll add the role here, seems to work") — and any confusing production issue ("why is this claim missing from the token", "why can't this LDAP user log in") gets debugged blind. This article is the map of the data model that articles 04 and 05 will attach concrete NestJS and React code to.

## Realm — an isolated "tenant" inside a single Keycloak

A **Realm** is a fully isolated space: its own users, its own clients, its own roles, its own themes, its own security settings (password policy, brute-force protection, token TTLs). Two realms on the same Keycloak instance can't see each other's data at all — as if they were two separate Keycloak servers that just happen to run on the same host.

```txt
┌─────────────────────────── Keycloak instance ───────────────────────────┐
│                                                                            │
│  ┌───────────── Realm: "acme-internal" ─────────────┐                    │
│  │  Users: company employees                          │                    │
│  │  Clients: internal-admin-panel, hr-service          │                    │
│  │  Password policy: strict, MFA required              │                    │
│  └────────────────────────────────────────────────────┘                    │
│                                                                            │
│  ┌───────────── Realm: "acme-customers" ─────────────┐                    │
│  │  Users: product customers                           │                    │
│  │  Clients: customer-web-app, mobile-app              │                    │
│  │  Password policy: looser, social login enabled       │                    │
│  └────────────────────────────────────────────────────┘                    │
└────────────────────────────────────────────────────────────────────────┘
```

Realm is the unit at which you decide "multi-tenancy = separate realms or a shared realm with groups" (a full trade-off breakdown lives in [Advanced Patterns]; here we're just fixing the fact that a Realm CAN be a tenant boundary, without that being mandatory).

A separate realm always exists — `master`, created by default on install. **`master` is meant for administering Keycloak itself** (creating other realms, managing server-level settings) — real application users should never log in through `master`. A common early-project mistake is inertia: continuing to configure everything in `master` instead of creating a dedicated realm for the app right away.

## Client — who talks to Keycloak, and how

A **Client** in Keycloak terms is the registration of a specific application (the OAuth2 "Client" role from [OAuth2/OIDC Fundamentals]) inside a realm. A client's config includes: allowed grant types, `redirect_uri`, per-client token TTLs, and, most important architecturally — the **client type**:

```txt
┌──────────────┬─────────────────────┬─────────────────────────────────┐
│              │ Can hold a secret?  │ Typical example                 │
├──────────────┼─────────────────────┼─────────────────────────────────┤
│ Public       │ No                  │ React SPA, mobile app —         │
│              │                     │ all the code runs on the        │
│              │                     │ user's device, a secret can't   │
│              │                     │ be protected there              │
├──────────────┼─────────────────────┼─────────────────────────────────┤
│ Confidential │ Yes                 │ NestJS backend, a BFF service — │
│              │                     │ code runs on a server your      │
│              │                     │ team controls, the secret can   │
│              │                     │ be safely kept in env/a secret  │
│              │                     │ manager                         │
├──────────────┼─────────────────────┼─────────────────────────────────┤
│ Bearer-only  │ Doesn't do login at │ A pure Resource Server — an API │
│              │ all                 │ that only VALIDATES tokens      │
│              │                     │ issued for another client, and  │
│              │                     │ never initiates an OAuth2 flow  │
│              │                     │ itself                          │
└──────────────┴─────────────────────┴─────────────────────────────────┘
```

`public` in Keycloak literally means "this client's `client_secret` is empty, and Keycloak won't require it on the code→token exchange" — which is exactly why PKCE isn't optional for public clients, it's a mandatory defense (without a secret and without PKCE, anyone who intercepts the code could complete the exchange).

`bearer-only` is a type people often confuse with "confidential, but for an API." The difference is fundamental: a bearer-only client **has no login endpoint and can't initiate an Authorization Code flow** — it exists purely so the Keycloak Admin Console has somewhere to configure client roles for that API and validate the `aud` (audience) claim in a token. In practice, a NestJS resource server is often not registered as a separate Keycloak client at all — a token issued to the React SPA (a public client) gets validated on the backend directly via JWKS (see [Tokens, Sessions, and Validation] and [NestJS Resource Server]); a bearer-only client is useful when you specifically need to separate `aud` between different APIs.

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

Note `serviceAccountsEnabled: true` — the flag that turns on the Client Credentials Grant for a client (Keycloak calls this a "service account," and it even gets its own technical user, `service-account-backend-service`, that roles can be assigned to).

## Users, Groups, Roles — the authorization model

### Realm roles vs Client roles

Roles in Keycloak come in two flavors, and the difference isn't syntactic — it's semantic:

```txt
Realm role:
  Exists at the level of the WHOLE realm. Example: "admin", "premium-user".
  Meaningful across ALL clients in the realm at once.
  Token claim: realm_access.roles: ["admin", "premium-user"]

Client role:
  Exists IN THE CONTEXT of a specific client. Example: the client
  "billing-service" might have a role "invoice:write" that makes
  no sense for any other client.
  Token claim: resource_access.billing-service.roles: ["invoice:write"]
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

A practical rule of thumb: if a permission makes sense "for the user in general, regardless of which API they happen to be using" — that's a realm role. If it's specific to one service ("can this user delete invoices in billing-service") — that's a client role of that service. A common beginner mistake is to make everything a realm role "because it's simpler," which over time turns `realm_access.roles` into a pile of fifty unrelated roles with no clue which one belongs to which service.

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

Composite roles are a mechanism for modeling "job titles"/"pricing tiers" as a single assignment, instead of manually maintaining a list of a dozen separate roles per user. A senior-level nuance: composite roles make assignment easier but make auditing harder — looking at a user, you only see "app-admin," and you have to expand the full list of actual permissions separately (via the Admin REST API or the "Effective Roles" tab in the console).

### Groups — assigning roles to many users at once

A **Group** is a way to assign a set of roles (and attributes) to many users at once, without composite roles per user. Groups support hierarchy (`/company/engineering/backend`), and roles assigned to a parent group are inherited by child groups.

```txt
Group "/company/engineering" → realm role "internal-tool-access"
Group "/company/engineering/backend" (inherits /engineering)
                                       → client role backend-service:"deploy"

A user in /company/engineering/backend gets BOTH roles:
  "internal-tool-access" (inherited) + "deploy" (own)
```

The difference between a Group and a Composite Role is a frequent question: a composite role is a "this role includes these roles" relationship, applied wherever that role gets assigned; a group is a "this user belongs to this organizational unit" relationship, which can additionally carry attributes (`department: backend`) and is convenient to administer along the lines of the company's org chart rather than an abstract bag of permissions.

## Client Scopes and Protocol Mappers — how token content is actually shaped

This is the mechanism that answers "how does a scope from article 01 turn into actual claims in the JWT" — a practical skill needed in almost every real project (custom claims for business logic: `tenantId`, `subscriptionTier`, an internal `permissions` array).

A **Client Scope** is a named, reusable bundle of configuration that can be attached to any number of clients. Standard scopes (`profile`, `email`, `roles`) ship with Keycloak out of the box; custom ones you create yourself.

A **Protocol Mapper** is a concrete rule inside a client scope: "take this piece of data (a user attribute, a role, a static value, a script) and put it in the token under this claim name."

```txt
Client Scope "tenant-info" (custom, created manually)
  └─ Protocol Mapper "tenant-id-mapper"
       Type: "User Attribute"
       User Attribute:  tenantId  (a custom user attribute in Keycloak)
       Token Claim Name: tenant_id
       Add to ID token: ✓
       Add to access token: ✓
```

```bash
# Creating a protocol mapper via the Admin REST API —
# adds the custom user attribute tenantId as the tenant_id claim
curl -X POST \
  https://keycloak.example.com/admin/realms/myrealm/client-scopes/$SCOPE_ID/protocol-mappers/models \
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

A Client Scope is then attached to a client as **Default** (added to the token automatically on any login by that client) or **Optional** (added only if the client explicitly requested it in the `scope=` parameter on the redirect to `/authorize`) — a direct continuation of the "scope requests, claim appears" mechanics from article 01, except now you can see exactly WHERE that link is configured.

A practical scenario worth mentioning: if the frontend suddenly stops seeing an expected claim in the token after someone "tidied up" Keycloak and detached a client scope from a client — that's not a frontend bug and not a library bug, it's a pure Keycloak configuration issue, diagnosed via the client's "Client Scopes" tab → check whether the needed scope is either in Default or explicitly requested.

## Identity Brokering vs User Federation — the pair developers systematically mix up

Both mechanisms are "about an external source of users," and both look like "logging in through something else," but they solve fundamentally different problems.

```txt
Identity Brokering:
  Keycloak delegates AUTHENTICATION to an external Identity Provider
  (Google, GitHub, another Keycloak, any OIDC/SAML provider).
  The user clicks "Log in with Google" → gets redirected to Google →
  logs in THERE → Google returns a token/assertion to Keycloak →
  Keycloak CREATES A LOCAL "shadow" account (a linked account) in
  ITS OWN realm, tied to the external sub.

  Keycloak never sees the user's password at all.
  Who it's for:  "Login with Google/GitHub/corporate Azure AD"
  Key point:     Keycloak = an OAuth2 Client WITH RESPECT TO the
                 external IdP

User Federation:
  Keycloak authenticates the user ITSELF (checks the password), but
  the user's data (and the password check itself) live in an EXISTING
  external store — typically LDAP or Active Directory — accessed
  through a federation provider (the built-in LDAP provider, or a
  Custom User Storage SPI for an arbitrary source).

  Keycloak makes an LDAP bind request with the entered password on login.
  Who it's for:  "The company already has an Active Directory with
                 5,000 employees, Keycloak should use THEIR ACCOUNTS
                 rather than duplicate the database"
  Key point:     Keycloak = an OIDC/SAML "facade" ON TOP OF an
                 existing user directory
```

```txt
Identity Brokering:                     User Federation:

  User → Keycloak → [redirect] →          User → Keycloak → [LDAP bind] →
         external IdP (Google)                   Active Directory
         (Keycloak = OAuth2 Client                (Keycloak = a facade,
          relative to Google)                       the password is checked
                                                     in AD)
```

A mnemonic that actually helps: **Identity Brokering is "one more button on the login screen"** (the user chooses how to authenticate, and it's a visible UX decision); **User Federation is "an invisible backend"** for Keycloak's standard login form (the user types a username/password as usual, it's just that this data is actually verified against LDAP, not Keycloak's internal DB, behind the scenes). You can combine them: local users + LDAP federation + Google brokering all at once in one realm.

## Authentication Flows — a step-builder for login

An **Authentication Flow** is a configurable sequence of steps a user goes through during login (or other actions: password reset, registration). The default `browser` flow already includes: checking a cookie for an existing SSO session → a login form → (optionally) an OTP check. Each step has a requirement: **Required** (mandatory), **Alternative** (one of several equally valid options — password OR WebAuthn, say), **Conditional** (only runs if a condition holds — e.g. "if the user has the admin role, require OTP").

```txt
Example custom flow "Login with conditional OTP":

  Cookie (checks the SSO session)      [ALTERNATIVE]
  Username Password Form                [REQUIRED]
  └─ Condition: user has role "admin"  [CONDITIONAL]
      └─ OTP Form                       [REQUIRED inside the condition]
```

This is the direct mechanism for step-up authentication (detailed scenarios in [Advanced Patterns]): not global MFA for everyone, but a targeted second-factor requirement for specific roles/groups/clients, configured declaratively in the flow builder, with zero code in the application itself.

## Themes — customizing the login screen

A **Theme** is a bundle of FreeMarker templates + CSS/JS defining how the pages Keycloak itself renders look (login, registration, email templates, error pages). An important architectural fact: the login page is **a Keycloak page**, not your React app's page (the user physically leaves the SPA's domain for the duration of authentication — that's part of the Authorization Code flow's security model, the frontend code should never get the password into its hands). A theme is how you make that page — foreign, but mandatory — look branded instead of like the default Keycloak admin skin.

## Admin REST API and Keycloak-as-Code — operational maturity

Everything shown above via `curl` is also available through a full **Admin REST API** — Keycloak itself is managed through the same OAuth2/OIDC mechanics (calling the admin API needs an access token from a service client with the right admin roles). Clicking through realm configuration by hand works fine for a single dev environment, but doesn't scale to "dev + staging + prod + temporary environments for feature branches" — the configuration inevitably drifts, and six months later nobody can answer "why is prod's password policy different from staging's."

The senior practice is **realm-as-code**: keeping all of a realm's configuration (clients, roles, client scopes, flows) as declarative files in git, applied automatically:

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

This isn't "bureaucracy for its own sake" — it's a direct consequence of the fact that the Realm is the source of truth for authorization across the whole system: if it's configured by clicking around with no version history, rolling back a bad change ("someone accidentally removed the service account from a prod client") turns into an investigation-by-memory instead of a `git revert`.

## Tying it together

```txt
[Realm]                    →  an isolated configuration boundary;
                              "realm-per-tenant vs shared" is an
                              architectural decision ([Advanced Patterns])

[Client type]               →  public/confidential/bearer-only,
                              determined by whether the client CAN
                              safely hold a secret

[Realm role / Client role /
 Composite / Group]         →  four ways to model "what's allowed,"
                              each at its own granularity

[Client Scope + Protocol
 Mapper]                    →  the mechanism that turns a scope into
                              actual token claims — what you need to
                              configure for any custom field in a JWT

[Identity Brokering vs
 User Federation]           →  "an external IdP does the
                              authenticating" vs "an external
                              directory holds the passwords, and
                              Keycloak checks them itself"

[Authentication Flows]      →  a step-builder for login — declarative
                              step-up with zero application code

[Realm-as-code]             →  operational maturity: Keycloak
                              configuration as part of a git repo,
                              not console clicks
```

The next article — [Tokens, Sessions, and Validation] — moves from "how Keycloak is configured" to what happens to an already-issued token on the API side: how it's validated, what JWKS and `kid` are, and how logout works in a system where a session exists both on Keycloak and (in effect) on the client.

## Common interview traps

- **"A Realm is just a folder for organizing clients"** — an underestimate: a Realm is full isolation (users, password policies, brute-force protection, themes), not just a namespace for grouping. Two clients in different realms can't directly reuse each other's roles or users without explicit Identity Brokering between the realms.

- **"A bearer-only client is the same as a confidential client, just for an API"** — no: a confidential client CAN initiate a flow (Client Credentials for service-to-service, say), a bearer-only client can't initiate an OAuth2 flow at all — it only validates other clients' tokens and exists to explicitly separate roles/audience for a specific API.

- **"Identity Brokering and User Federation are the same thing, just different names for 'logging in via LDAP/Google'"** — a fundamental confusion. Brokering means Keycloak doesn't check anything itself — it redirects to an external OIDC/SAML IdP. Federation means Keycloak checks the password itself (e.g. an LDAP bind), it's just that the data source is an external directory rather than the built-in DB.

- **"Composite role and Group are interchangeable ways to group permissions"** — no: a composite role is a property of the role itself (unpacks wherever it's assigned, anywhere), a group is an org unit with its own hierarchy and attributes that users and roles get attached to. They have different administrative semantics, even if the resulting set of user permissions can look the same.

- **"Claims in a token can only be changed via backend code"** — no, this is a common mistake among people unfamiliar with Protocol Mappers: adding a custom claim (say, `tenant_id`) is Keycloak configuration (a Client Scope + a Protocol Mapper), not API-side code. Writing code for this would mean solving the problem at the wrong layer of the architecture.
