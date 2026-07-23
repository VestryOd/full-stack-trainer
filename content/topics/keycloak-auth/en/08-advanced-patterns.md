# Advanced Patterns — beyond plain login

## When "just set up login" stops being enough

Articles 01-07 cover what's needed for a correct and secure standard flow: login, tokens, backend/frontend defense. This article covers scenarios that come up less often, but show up systematically in a senior role: not "how do you do login," but "how do you design auth for a specific, non-trivial business situation" — extra security for particular actions, merging identities from different sources, a multi-tenant SaaS, non-standard claims, migrating off a legacy system, and Keycloak's own operational maturity.

## Step-up authentication — a targeted second factor, not a global one

The problem step-up solves: requiring MFA/WebAuthn for EVERY action in the app is UX friction on every login, even where the stakes are low (viewing an order list). Requiring it ONLY for sensitive actions (a money transfer, changing a password, changing an email) is the right balance, and Keycloak supports this as a first-class scenario through **Authentication Flows** (article 02) combined with the **`acr` (Authentication Context Class Reference) parameter**.

```txt
The mechanism:
  1. A regular login goes through the standard browser flow
     (a password, maybe "remember me") → an access token is issued
     with the claim "acr": "1" (a low authentication assurance level)

  2. Before a sensitive action, the app initiates a NEW authorization
     request with the parameter:
       &acr_values=2  (requesting a higher authentication level)
     or the Keycloak-specific:
       &kc_action=CONFIGURE_TOTP  (force a specific action)

  3. Keycloak sees the current session was authenticated with acr=1,
     but acr=2 is being requested → forces an ADDITIONAL step
     (WebAuthn/OTP) ON TOP of the existing session, without a full
     re-login

  4. The new access token carries "acr": "2" — the app CHECKS THIS
     CLAIM before allowing the sensitive action, instead of just
     trusting that "the user somehow went through step-up on the
     client"
```

```typescript
// NestJS: a Guard checking the authentication level before a sensitive action
@Injectable()
export class StepUpGuard implements CanActivate {
  canActivate(context: ExecutionContext): boolean {
    const { user } = context.switchToHttp().getRequest();
    const requiredAcr = this.reflector.get<string>('acr', context.getHandler());

    if (requiredAcr && user.acr !== requiredAcr) {
      throw new ForbiddenException({
        error: 'step_up_required',
        required_acr: requiredAcr,
        // The frontend should trigger a NEW authorization request
        // with acr_values=<requiredAcr>, not just show an error
      });
    }
    return true;
  }
}

@Post('transfer-funds')
@RequireAcr('2') // requires step-up for this specific endpoint
async transferFunds(@Body() dto: TransferDto) { /* ... */ }
```

A key architectural point: **the `acr` claim check MUST happen on the Resource Server (backend), not only in the frontend UI**. A common mistake is having the frontend show a WebAuthn modal before calling a sensitive endpoint, but never checking the actual `acr` in the token on the backend — then an attacker who already holds a valid access token with `acr: 1` (a regular login, no step-up) can call the API directly, bypassing the UI check entirely.

## Account Linking — merging identities from multiple Identity Providers

The scenario: a user originally registered locally (email+password), and later wants to link a Google login for convenience — both login methods should lead to the SAME account, not create a duplicate user.

```txt
Without explicit linking (the problem):
  A user registers locally: user@example.com / password
  Later they log in via "Sign in with Google" with the same email —
  Keycloak (via Identity Brokering, article 02), by default, MAY
  create a SECOND, separate account, even with a matching email —
  the result: two disconnected "users" in the system, with different
  order history/settings/permissions.

With Account Linking:
  First login:  local login, user@example.com/password
  The user goes to "Account Settings" → "Link Accounts" →
  "Link Google" → redirect to Google → after successful
  authentication, Keycloak LINKS the google-sub to the ALREADY
  EXISTING local account (a Federated Identity Link) instead of
  creating a new one

  After linking: both the local password AND "Sign in with Google"
  lead to the SAME Keycloak user, with the same history of
  roles/groups/data
```

```txt
Automatic account linking by email — a tempting but dangerous
"default" configuration:

  Keycloak CAN be configured to automatically link accounts by
  matching email WITHOUT explicit user confirmation ("First Login
  Flow" with "Automatically link" enabled). Convenient, but creates a
  REAL vulnerability: if an external IdP (say, an obscure corporate
  provider added via Identity Brokering) does NOT verify email as
  strictly as your main realm does — an attacker can register with
  THAT external IdP using SOMEONE ELSE'S email (if that IdP allows
  it with no verification), log in through it to your app, and
  automatically "inherit" the victim's local account with the same
  email.

  Safe practice: an explicit user action (a "Link" button in an
  already-authenticated session) instead of automatic linking by
  email on first login through a new IdP — especially for an IdP
  whose email verification policy you don't fully know and don't
  directly control.
```

## Multi-tenancy — Realm-per-tenant vs Shared Realm

This is one of the most common architectural questions when building a B2B SaaS on Keycloak, and there's no universally correct answer here — only a deliberate trade-off.

```txt
Realm-per-tenant:
  Every company customer (SaaS tenant) gets its OWN Keycloak realm:
  acme-corp, globex-inc, initech-llc...

  ✓ Full isolation out of the box — its own password policy, its own
    login theme (important for white-label SaaS — the customer sees
    THEIR OWN branding on the login page, not a shared one), its own
    Identity Providers/User Federation (a customer can connect THEIR
    OWN Active Directory with no risk to other customers)
  ✓ Easier to satisfy a "tenant data is physically isolated"
    requirement for compliance-sensitive customers
  ✗ Operational overhead GROWS linearly with the number of tenants:
    realm-as-code (article 02) config has to be applied to N realms,
    monitoring/alerting has to aggregate across N realms, a Keycloak
    upgrade gets tested against N configurations
  ✗ A practical ceiling: thousands of realms on a single Keycloak
    instance start creating real operational load (the admin console,
    config sync, startup time)

Shared Realm with group/organization-based isolation:
  One realm for ALL tenants, isolation via Groups (article 02):
  /tenants/acme-corp, /tenants/globex-inc, with a tenantId attribute
  and a Protocol Mapper putting tenant_id into the token (article 02)

  ✓ Operational load DOESN'T grow linearly with the number of
    tenants — one realm serves thousands of organizations
  ✓ Easier to share common infrastructure (one theme for everyone,
    except white-label cases) and common Identity Providers
  ✗ Isolation happens at the APPLICATION level, not Keycloak's: the
    Resource Server MUST filter data by the tenant_id from the token
    on EVERY request — a mistake in that check means a cross-tenant
    data leak, and that's not a Keycloak problem, it's a bug in your
    code
  ✗ Per-tenant customization (its own login theme, its own Identity
    Provider) is harder — Keycloak Organizations (a relatively new
    feature, available from certain versions on) partially closes
    this gap, but doesn't give you the full isolation of
    realm-per-tenant
```

A practical, context-dependent recommendation: **realm-per-tenant is justified for B2B enterprise SaaS with a small number (tens-hundreds) of large customers, each needing customization and strict isolation (often a direct compliance requirement). A shared realm with groups is justified for B2C or self-serve B2B with thousands of small tenants**, where realm-per-tenant's operational load would become unmanageable, and isolation requirements are looser. A hybrid option (Keycloak Organizations) is worth evaluating separately against the specific Keycloak version and specific requirements — this is a relatively new area where best practices are still settling.

## Extending claims via the Protocol Mapper SPI — when the built-in mappers aren't enough

Article 02 covered the built-in Protocol Mappers (User Attribute, Role). Sometimes a claim needs to be computed with non-trivial business logic: aggregating data from an external DB, calling another service, a complex transformation — something that can't be expressed with an out-of-the-box declarative mapper.

```txt
Keycloak SPI (Service Provider Interface) — Keycloak's general
extensibility mechanism: Java interfaces you can implement yourself
and package as a JAR plugin, deployed into Keycloak's providers/
directory.

Protocol Mapper SPI — the specific SPI for custom claim logic:
  implement the ProtocolMapper interface (Java), inside which you
  can run arbitrary code (hit your own DB, call an internal service,
  apply complex business logic) to compute a claim's value when a
  token is issued.
```

```java
// A conceptual sketch (not a full tutorial — the goal is to show the idea)
public class SubscriptionTierMapper extends AbstractOIDCProtocolMapper
    implements OIDCAccessTokenMapper {

  @Override
  protected void setClaim(IDToken token, ProtocolMapperModel mappingModel,
                          UserSessionModel userSession, KeycloakSession session,
                          ClientSessionContext clientSessionCtx) {
    String userId = userSession.getUser().getId();
    // Custom logic: e.g., a call to a billing service
    String tier = billingServiceClient.getSubscriptionTier(userId);
    token.getOtherClaims().put("subscription_tier", tier);
  }
}
```

```txt
When it's justified:
  - The claim needs data that physically doesn't live in Keycloak
    (user attributes, roles, groups) — e.g. "current subscription
    tier," which changes in a billing system independent of Keycloak
  - Computing the claim needs logic unavailable in declarative
    mappers (aggregation, conditional logic more complex than a
    simple attribute mapping)

When it's NOT justified (stick with the built-in mappers):
  - The data already exists as a user attribute/role/group — then a
    built-in Protocol Mapper (article 02) solves it with zero Java
    code and no need to deploy, version, or maintain a custom plugin

The operational cost of a custom SPI:
  Every custom provider is additional code that needs testing,
  version-compatibility management against the Keycloak version
  (SPI contracts can change between major versions), and consideration
  during a Keycloak upgrade. This is a real engineering asset with an
  ongoing maintenance cost, not just configuration.
```

## Migrating from a home-grown auth system to Keycloak — the strangler pattern applied to auth

A realistic senior scenario: an existing app with legacy JWT authentication (its own `users` table, its own bcrypt hash, its own JWT-issuing code) that needs to move to Keycloak WITHOUT a big-bang flag day for every user at once (unacceptable business risk).

```txt
The classic strangler fig pattern, applied to auth:

Phase 1 — Keycloak alongside, but not in prod yet:
  Deploy Keycloak, configure the realm, DON'T switch real traffic
  over yet. Validate the configuration on staging.

Phase 2 — User Federation via a Custom User Storage SPI (a bridge):
  Write a Custom User Storage Provider (the same SPI mechanism as
  above) that turns Keycloak into a "transparent facade" OVER THE
  EXISTING legacy system's users table: on login, Keycloak checks
  the password by HITTING THE OLD DB AND APPLYING THE OLD HASH
  ALGORITHM (bcrypt/scrypt/whatever was used before), instead of
  migrating every password at once. Users log in THROUGH Keycloak
  without even knowing anything changed — their password still
  lives in the old table.

Phase 3 — Gradual, on-the-fly password migration:
  On a SUCCESSFUL login through the Custom User Storage Provider,
  Keycloak imports the user into ITS OWN internal DB (with a new,
  Keycloak-native password hash), and for THAT user, all further
  logins go directly through Keycloak, not through the bridge to the
  legacy table. Over time (as real users log in), the share of
  "migrated" users grows organically, with no forced flag day and no
  need to know every password in the clear ahead of time (which is
  impossible if they're hashed).

Phase 4 — Switching clients over (backend/frontend):
  Gradually, service by service, the backend moves from validating
  its own legacy JWTs to validating Keycloak tokens via JWKS
  (articles 03/04) — this can be done in stages, if the Resource
  Server temporarily supports TWO validation paths at once (a
  legacy JWT secret + Keycloak JWKS), clearly marked and removed
  once ready.

Phase 5 — Tearing down the bridge:
  Once the share of unmigrated users becomes negligible (or after an
  explicit "log in once to complete the migration" campaign for
  inactive accounts), the Custom User Storage Provider and the
  legacy table are retired.
```

The core idea of the strangler approach here is the same as in any other domain: **not a big-bang system replacement, but gradually "wrapping" the old system with a new facade, with data migration happening organically through real usage**, rather than a one-time batch script that would require access to passwords in a form that's impossible to have by definition (passwords are hashed irreversibly).

## HA and clustering — operational maturity, not a deep DevOps deep-dive

Keycloak in production is a stateful service with real availability requirements, and underestimating this is a common cause of "Keycloak went down, all of prod stopped" incidents, because authentication is a single point of failure for the whole system by definition.

```txt
Why a real database is needed (not embedded H2):
  Realm configuration, users, sessions (depending on cache
  configuration) are persistent data that need a real production-
  grade DB (PostgreSQL is the most common choice) with backups,
  replication, monitoring — just like any other critical service,
  not like "just another microservice that can be recreated from
  scratch."

Why clustering is needed (multiple Keycloak instances):
  A single Keycloak instance is a single point of failure for
  authentication across the WHOLE system: if it goes down, nobody
  can log in, and, more critically, if token introspection is in
  use (article 03), nobody can make any API calls at all until
  Keycloak comes back. A production deployment is at minimum 2+
  Keycloak replicas behind a load balancer, sharing a DB, and
  (depending on the version) a distributed session cache
  (Infinispan in cluster mode) to keep server-side sessions
  consistent across instances.

The practical takeaway for an engineer, not necessarily a DevOps
specialist:
  When planning architecture, treat Keycloak as a component that
  demands the SAME operational seriousness as the product's main
  database — HA deployment, monitoring latency and error rate on
  auth endpoints, alerting on rising p99 login-request times — not
  as "we dropped one pod in k8s and forgot about it."
```

## Tying it together

```txt
[Step-up + acr]                   →  a targeted second-factor
                                    requirement, checked ON THE
                                    BACKEND via a claim, not just in
                                    the UI

[Account Linking]                  →  an explicit user action is
                                    safer than automatic linking by
                                    email — especially for external
                                    IdPs with an unknown verification
                                    policy

[Realm-per-tenant vs Shared
 Realm]                             →  isolation and customization vs
                                    operational overhead that grows
                                    with the number of tenants — the
                                    decision depends on scale and
                                    compliance requirements

[Protocol Mapper SPI]              →  justified when a claim needs
                                    data/logic outside Keycloak —
                                    with a real ongoing maintenance
                                    cost

[Strangler pattern for
 migration]                        →  a Custom User Storage Provider
                                    as a bridge to legacy passwords,
                                    organic migration through real
                                    logins, not a batch script

[HA/clustering]                    →  Keycloak is a critical, stateful
                                    component demanding the same
                                    operational seriousness as the
                                    product's main database
```

The next article — [Keycloak vs Alternatives] — moves from "how to use Keycloak to the fullest" to a higher-level question: when it even makes sense to choose Keycloak (self-hosted) over managed alternatives (Auth0, Okta, Cognito), or even over a home-grown solution.

## Common interview traps

- **"Step-up authentication is just showing an OTP modal before a sensitive action on the frontend"** — not enough: without checking the `acr` claim on the backend, an attacker holding a regular (non-step-up) token can call the protected endpoint directly, bypassing the UI check entirely.

- **"Account linking by email should be automatic — it's more convenient for the user"** — a risk: automatic linking by email with no explicit user confirmation creates a vulnerability if an external Identity Provider doesn't verify email as strictly as your main realm does — an attacker can "inherit" someone else's local account through a weakly-verified external IdP.

- **"Realm-per-tenant is always the best choice for a multi-tenant SaaS, because it gives full isolation"** — not universally true: operational load grows linearly with the number of tenants, and for self-serve B2C/B2B with thousands of small customers, a shared realm with group-based isolation is the more realistic choice, even though data isolation then falls on the application, not on Keycloak.

- **"Migrating from a legacy auth system to Keycloak has to happen all at once, otherwise you'd have two sources of truth"** — misses the practical impossibility (and unnecessity) of a flag day: the strangler approach via a Custom User Storage Provider lets passwords migrate organically, as real logins happen, with no risk to the whole user base at once and no need to have access to plaintext passwords.

- **"Keycloak is just another stateless microservice you can scale like any other"** — wrong: Keycloak is a stateful service with real requirements around a database, backups, and a distributed session cache when clustered; underestimating this is a common cause of production incidents where the auth layer going down stops the entire system.
