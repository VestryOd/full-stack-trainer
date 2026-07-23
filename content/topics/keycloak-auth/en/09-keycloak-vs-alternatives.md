# Keycloak vs Alternatives — an honest choice, not marketing

## Why a dedicated article, when everything else was about Keycloak

The previous eight articles taught you to use Keycloak deeply and correctly — but that doesn't mean Keycloak is always the right choice. What sets a senior engineer apart from someone who just knows a tool well is the ability to honestly say "in this case, we shouldn't have picked Keycloak" — including cases where you personally picked it, but the context has since changed. This article isn't "Keycloak beats everything" — it's a framework for making this decision fresh, for each specific project.

## The players on the field — what they actually are

```txt
Keycloak:
  Open-source (Apache 2.0 license), self-hosted (or available
  through third-party managed offerings — Red Hat build of
  Keycloak, various managed-Keycloak SaaS providers). Full control
  over the code, infrastructure, and user data — and full
  responsibility for operating it.

Auth0 (now part of Okta):
  Managed identity-as-a-service. A rich configuration UI, a large
  "Actions"/"Rules" ecosystem (custom logic without deploying your
  own instance), strong docs and DX. Priced by MAU (monthly active
  users) — can grow non-linearly as the product grows.

Okta (as a product distinct from Auth0 — Okta Identity Cloud):
  Managed, historically leaning more toward enterprise/workforce
  identity (a company's employees, B2E) and deep integration with
  corporate systems (SSO into internal enterprise apps), though
  modern Okta CIC (Customer Identity Cloud, formerly Auth0) also
  covers B2C/CIAM scenarios.

AWS Cognito:
  Managed, deeply integrated with the rest of AWS (IAM, Lambda
  triggers for flow customization, API Gateway authorizers). Priced
  by MAU, usually noticeably cheaper than Auth0/Okta at comparable
  volumes. Known for a sparser UI/DX and less flexible flow
  customization compared to Auth0.

Supabase Auth (GoTrue):
  Open-source, usually used as part of Supabase (managed Postgres +
  auth + realtime + storage out of the box). Significantly simpler
  conceptually than Keycloak/Auth0 — less configuration, fewer
  capabilities (no full Authorization Services, more limited
  Identity Brokering) — built for a fast start, not enterprise
  depth.

A home-grown solution:
  Your own users table, your own JWT-issuing code, your own bcrypt.
  Full control, zero external dependencies — and FULL responsibility
  for EVERY aspect: password reset flow, MFA, login rate limiting,
  brute-force defense, matching the security best practices that
  Keycloak/Auth0 have already implemented and battle-tested across
  millions of installs.
```

## When self-hosted Keycloak is the right call

```txt
Cost at scale:
  Managed providers (Auth0, Okta, Cognito) charge by MAU — cheap or
  free at small scale (a free tier), but at a scale of hundreds of
  thousands to millions of active users, the bill can become one of
  the company's largest infrastructure line items. Self-hosted
  Keycloak's cost is infrastructure (servers, a DB, engineering time
  for upkeep), which grows SUB-LINEARLY relative to the number of
  users (unlike MAU billing) — at sufficient scale, self-hosting
  becomes economically favorable despite the engineering overhead.

Data residency and control:
  Regulatory requirements (GDPR-sensitive jurisdictions, financial/
  medical compliance, the public sector) sometimes literally require
  that user personal data NEVER leave a specific jurisdiction/
  infrastructure. Self-hosted Keycloak in your own data center/cloud
  region gives direct control over THIS specific requirement, rather
  than relying on a managed provider's regional guarantees (which do
  exist, but add an extra layer of third-party trust).

Depth of customization:
  Custom Authentication Flows, the Protocol Mapper SPI, the User
  Storage SPI (article 08) — Keycloak gives you access to the source
  and full extensibility through Java SPIs. Managed providers offer
  customization through THEIR OWN APIs/hooks (Auth0 Actions, Cognito
  Lambda triggers) — powerful, but bounded by whatever the provider
  DECIDED to make extensible, not arbitrarily.

No vendor lock-in on billing:
  MAU-based pricing from managed providers creates a direct financial
  dependency on the user base's growth, scaling non-linearly relative
  to the actual engineering load on the authentication system.
```

## When a managed provider is the better choice

```txt
Reduced operational load:
  Self-hosted Keycloak requires: HA deployment (article 08),
  monitoring, patching security vulnerabilities, testing upgrades
  across major versions (breaking changes do happen), database
  backups, on-call for auth-layer incidents. A managed provider
  takes ALL OF THIS on itself — the team gets auth "as a service"
  with no need to hire/dedicate engineers to maintaining the IdP
  itself.

Faster time-to-market:
  Managed providers are optimized for "set up in an hour, not
  weeks" — ready-made SDKs for every platform, ready login UI
  components, ready docs for common integrations. For a startup
  where speed to market is critical, the difference between "we
  wired up Auth0 in a day" and "we deployed and configured a
  Keycloak cluster over two weeks" can be decisive.

SLA and support:
  An enterprise contract with Auth0/Okta gives you a formal uptime
  SLA, dedicated support, and provider accountability for security
  incidents on their platform. Self-hosted Keycloak — the
  responsibility is ENTIRELY on your team, including 3am on a
  weekend.

A smaller team, less specialized expertise:
  If the team has no dedicated engineer/group specializing in
  identity infrastructure, and isn't planning to hire one — a
  managed solution removes the need to become an expert at
  operating Keycloak just to have working login.
```

## The questions a senior engineer actually asks — not a feature checklist

Choosing an IdP off a table of "feature X exists / feature Y doesn't" is a shallow approach, because almost every needed feature EXISTS at every major player in some form. The real decision is built on other questions:

```txt
1. "How big is the team, and is there expertise in operating
    identity infrastructure?"
   → No dedicated platform team → managed wins strongly. A
     dedicated platform/infra team exists → self-hosted becomes a
     realistic option.

2. "What compliance/regulatory requirements does THIS specific
    business actually have, not abstractly?"
   → A concrete legal data-residency requirement → a strong
     argument for self-hosted OR a managed provider with a
     guaranteed regional deployment (verify this contractually,
     don't assume it).

3. "What's the expected auth traffic, and how will it grow?"
   → MAU billing against a projected hundreds-of-thousands+ active
     users — calculate the ACTUAL cost 12-24 months out, not just
     at today's volume — managed billing often becomes an unpleasant
     surprise exactly during fast growth.

4. "How deep is the flow customization the business actually
    needs, versus 'just in case'?"
   → Complex corporate SSO integrations, custom multi-step
     verification flows, specific business logic at token-issuance
     time (article 08, the Protocol Mapper SPI) → self-hosted gives
     you full access to this. Standard email+password+social login
     → almost any provider handles this equally well, the difference
     isn't in capability, it's in price/operational load.

5. "What happens if the provider raises prices/changes terms/drops
    support for a feature we depend on?"
   → A managed provider is also a business relationship with the
     risk of terms changing outside your control; self-hosted
     removes this specific risk at the cost of taking on the
     operational one.
```

## Tying it together

```txt
[Self-hosted Keycloak is justified] →  scale makes MAU billing more
                                     expensive than infrastructure
                                     + engineering time; strict data
                                     residency requirements;
                                     customization needs beyond the
                                     provider's hooks

[A managed IdP is justified]         →  a team without dedicated
                                     identity expertise; speed to
                                     launch is critical; a formal
                                     SLA is needed; standard auth
                                     scenarios with no deep
                                     customization

[The senior engineer's questions]     →  team size, real (not
                                     abstract) compliance
                                     requirements, a 12-24 month
                                     traffic forecast, a real (not
                                     hypothetical) customization
                                     need, the risk of vendor
                                     lock-in on billing/terms
```

The next article — [Cheatsheet and Comparison] — condenses everything from this topic (grant types, JWT claims, the keycloak-js API, the BFF flow) into a compact reference format, including a final comparison table of every provider and pattern covered here.

## Common interview traps

- **"Keycloak is always better than managed solutions, because it's free and open-source"** — an oversimplification: "free" refers only to the license, not the total cost of ownership (TCO) — infrastructure and engineering time for HA/patching/upgrades often outweighs a managed provider's MAU billing at small-to-medium scale. Self-hosting pays off specifically AT SCALE, not by default.

- **"Choosing an IdP is comparing a feature table, whoever has more wins"** — a shallow approach: almost every major player covers the same basic feature set. The real decision is built on team/compliance/traffic/vendor-lock-in risk, not on counting rows in a marketing comparison chart.

- **"AWS Cognito is universally the worst choice because of its sparse UI"** — contextually wrong: if the infrastructure is already on AWS, deep integration with IAM/Lambda/API Gateway and a noticeably lower cost at volume can outweigh the UI/DX shortcomings — it's a trade-off, not a clear-cut verdict.

- **"A managed provider takes on all security responsibility"** — no: a managed provider removes the operational responsibility for the IdP's own infrastructure (patching, uptime), but responsibility for the CORRECT USE of the protocol (redirect_uri validation, PKCE, correct client-side token storage — articles 05-07) stays entirely with the team building the application, regardless of which provider is chosen.

- **"Supabase Auth and Keycloak are interchangeable options for any project"** — no: they have fundamentally different levels of maturity and feature coverage (Supabase Auth doesn't offer full Authorization Services, deep Identity Brokering, or Keycloak's SPI extensibility) — the choice between them comes down not to personal preference, but to whether the project needs Keycloak's enterprise depth or whether the fast start Supabase offers is enough.
