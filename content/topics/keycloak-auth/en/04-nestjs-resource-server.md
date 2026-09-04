# NestJS as a Resource Server

## From "we validate the token" to "a correctly designed API"

This article turns the mechanics of article 03 into a concrete NestJS architecture. Article 03 covered JWKS (JSON Web Key Set), `kid`, local validation against introspection, and who owns the refresh.

Four questions get answered here. Which Guard checks what? How do Keycloak roles turn into `@Roles('admin')` decisions? What do you do when a simple "has role / doesn't have role" isn't enough? And how do services talk to each other with no user involved?

## Manual approach vs adapter — a deliberate choice, not "whatever came up on Google"

There are two realistic ways to wire NestJS to Keycloak. Picking between them is an architectural decision with concrete trade-offs, not a matter of taste.

```txt
Manual approach (passport-jwt + jwks-rsa):
  You write the JwtStrategy yourself (see article 03), write the
  Guards and role decorators yourself, decide yourself what to do
  with every claim.

  ✓ Full transparency: every line that decides "let in / reject"
    is visible — critical for a security audit
  ✓ No Keycloak-specific dependency in your core code — easier to
    move to a different OIDC provider later
  ✓ Full control over error format, logging, which claims get
    extracted and how
  ✗ More code to write and maintain yourself
  ✗ Easy to forget a subtlety (audience checking, say) — nothing
    catches it for you

Adapter (nest-keycloak-connect / keycloak-connect):
  An official (or community) NestJS module wrapping
  Keycloak-specific Guards, decorators (@Roles, @Public,
  @AuthenticatedUser), and out-of-the-box integration with
  Keycloak Authorization Services.

  ✓ Less code — Guards and decorators are already written and tested
  ✓ Out-of-the-box support for resource-based authorization
    (Keycloak Authorization Services), which takes longer by hand
  ✗ Less transparency — part of the validation logic is hidden
    inside the library, you need to read its source when debugging
  ✗ Tight coupling to Keycloak specifically — if the team decides to
    migrate to Auth0/Okta a year later, you rebuild the abstraction
    layer instead of just swapping the issuer URL
  ✗ Dependent on a community package's maintenance (not always the
    official Red Hat/Keycloak module — check the repo's activity)
```

Practical recommendation: **for a product that will clearly stay on Keycloak long-term and needs Authorization Services, the adapter pays off**.

Go manual for an API where maximum transparency matters: fintech, or anything under external security audit. The same goes if the team wants to keep the option of switching providers. Both approaches sit on the same protocol foundation from articles 01-03. The only difference is who writes the Guard code: you or the library.

## Guards and decorators — mapping Keycloak roles onto NestJS authorization

Either way — writing it yourself or using an adapter — the resulting architecture is the same. **A Guard validates the token and extracts roles. A decorator on the controller declares the requirement. A Reflector connects the two.**

```typescript
// roles.decorator.ts — metadata for required roles on a handler/controller
import { SetMetadata } from '@nestjs/common';

export const ROLES_KEY = 'roles';
export const Roles = (...roles: string[]) => SetMetadata(ROLES_KEY, roles);
```

```typescript
// roles.guard.ts — reads realm_access.roles from the payload, compares against metadata
import {
  CanActivate, ExecutionContext, ForbiddenException, Injectable,
} from '@nestjs/common';
import { Reflector } from '@nestjs/core';

@Injectable()
export class RolesGuard implements CanActivate {
  constructor(private reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    const requiredRoles = this.reflector.getAllAndOverride<string[]>(ROLES_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);
    // no role required — open to any authenticated user
    if (!requiredRoles?.length) return true;

    const { user } = context.switchToHttp().getRequest();
    const realmRoles: string[] = user?.realm_access?.roles ?? [];

    const hasRole = requiredRoles.some((role) => realmRoles.includes(role));
    if (!hasRole) {
      throw new ForbiddenException({
        error: 'insufficient_role',
        required: requiredRoles,
      });
    }
    return true;
  }
}
```

```typescript
// billing.controller.ts — a declarative role requirement on a specific endpoint
@Controller('invoices')
@UseGuards(AuthGuard('jwt'), RolesGuard) // authentication first, then authorization
export class InvoicesController {
  @Post()
  @Roles('billing-service:invoice:write') // a client role from article 02
  async create(@Body() dto: CreateInvoiceDto) { /* ... */ }

  @Get()
  @Roles('billing-service:invoice:read')
  async findAll() { /* ... */ }
}
```

A key architectural point that's easy to miss: **`AuthGuard('jwt')` and `RolesGuard` are two separate Guards, running one after the other.** They are not one fused Guard. `AuthGuard('jwt')` is authentication — "who is this". `RolesGuard` is authorization — "what are they allowed to do".

The separation matters: it lets you reuse `RolesGuard` for other authentication methods, an API key for internal services for example, without duplicating the role-checking logic.

For client roles (`resource_access.billing-service.roles`, see article 02) the decorator and Guard work the same way. They just read a different path in the payload. In practice it is convenient to build one general `@RequireRole(type: 'realm' | 'client', clientId?: string, role: string)`. Don't over-engineer that API if the project only ever uses realm roles, or only client roles of a single service.

```txt
   Two Guards, running one after the other
┌────────────────────────────────────────────┐
│ Request with Authorization: Bearer <token> │
└────────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────┐
│ AuthGuard('jwt')  —  authentication        │
│ answers "who is this"                      │
└────────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────┐
│ RolesGuard        —  authorization         │
│ answers "what are they allowed to do"      │
└────────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────┐
│ @Roles(...) matched: the controller runs   │
└────────────────────────────────────────────┘
  RolesGuard is reusable: swap AuthGuard for
  an API-key guard and the role logic stays
```

## When simple roles aren't enough — Keycloak Authorization Services

Role-based checks ("has the admin role — can do everything, doesn't — can do nothing") work great as long as the rules are static. They stop working for rules like "a user can only edit **their own** documents". Or "access to a resource depends on the time of day and the user's department".

That is no longer authorization by role. It is authorization by **resource attributes and context**, and Keycloak has a separate layer for it: **Authorization Services**, a UMA-like model (User-Managed Access).

```txt
The Authorization Services object model:

  Resource   — a specific protected entity or type of entity
               ("Invoice", "Document:42", "/admin/*")
  Scope      — an action on a resource ("view", "edit", "delete").
               Not the same as the OAuth2 scope from article 01:
               here it is just an action name inside
               Authorization Services
  Policy     — a decision rule: a role-based policy, a time-based
               policy, a JS-based policy (custom logic), a
               group-based policy, a client-based policy...
  Permission — ties a Resource + Scope to one or more Policies:
               "the 'edit-invoice' Permission is granted if the
               'owner-only' or the 'admin-role' Policy passes"
```

```txt
Policy Enforcement Point (PEP) — a pattern, not a Keycloak term:

  The Resource Server (NestJS) does NOT implement the authorization
  business rules itself — instead, on every protected request it
  asks Keycloak (the Policy Decision Point): "can this user perform
  the 'edit' scope on the 'Invoice:42' resource?"

  NestJS API                     Keycloak (PDP)
  ────────────                   ──────────────
  PUT /invoices/42     ──────►   UMA Permission Ticket /
  (PEP: intercepts the    RPT     Token endpoint:
   request, asks for       ◄──────  "invoice:42#edit" → RESOLVED
   permission)                     (or DENIED)
```

```bash
# A UMA-like permission check request — RPT (Requesting Party Token)
curl -X POST \
  https://keycloak.example.com/realms/myrealm/protocol/openid-connect/token \
  -H "Authorization: Bearer $USER_ACCESS_TOKEN" \
  -d "grant_type=urn:ietf:params:oauth:grant-type:uma-ticket" \
  -d "audience=billing-service" \
  -d "permission=Invoice:42#edit"
```

```json
// Response when access is granted — the RPT carries an authorization claim
{
  "access_token": "eyJhbGci...",
  "token_type": "Bearer"
}
// The RPT payload contains:
// "authorization": { "permissions": [{ "rsid": "invoice-42-id", "scopes": ["edit"] }] }
```

```typescript
// NestJS: a guard delegating the decision to Keycloak instead of a local role check
@Injectable()
export class UmaPermissionGuard implements CanActivate {
  constructor(
    private reflector: Reflector,
    private keycloakAuth: KeycloakAuthorizationService,
  ) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest();
    const resource = this.reflector.get<string>('resource', context.getHandler());
    const scope = this.reflector.get<string>('scope', context.getHandler());

    const allowed = await this.keycloakAuth.checkPermission(
      req.headers.authorization, // the user's access token
      `${resource}#${scope}`,
    );
    if (!allowed) throw new ForbiddenException('uma_permission_denied');
    return true;
  }
}
```

When to move to Authorization Services, and when not to:

```txt
Simple roles are enough when:
  - The rules are static and don't depend on a specific resource
    instance
  - "Anyone with role X can do Y to ANY resource of this type"
  - A small team that values debugging simplicity over hunting
    through the Keycloak Admin Console for a Policy's config

You need Authorization Services when:
  - Rules depend on a SPECIFIC resource instance (ownership,
    attributes of a DB record) or on context (time, IP, user
    attributes beyond roles)
  - The business wants to manage access rules without involving
    developers (a non-technical security or compliance person
    configures Policies through the Keycloak Admin Console)
  - You need centralized auditing of "who could do what, when" —
    Keycloak logs permission requests in one place
```

An honest caveat: Authorization Services add a network round-trip to every check, unless you cache the RPT (Requesting Party Token). They also add cognitive overhead — the team needs to understand the Resource/Scope/Policy/Permission model instead of just reading `if (user.roles.includes(...))`.

For most CRUD apps (create, read, update, delete) the ownership model is "my records vs someone else's". Checking `resource.ownerId === user.sub` directly in service code is often enough. Not every ownership check needs to go through UMA — only rules that are complex, or that need a central policy editable without a deploy.

## Monolith vs API Gateway — where exactly to validate the token in a microservices architecture

This is an architectural choice affecting the whole stack, not a detail of one service.

```txt
Option A — every service validates the token itself:

  Client → Service A (validates the JWT via JWKS)
         → Service B (validates the JWT via JWKS)
         → Service C (validates the JWT via JWKS)

  ✓ Each service is independent: tested and deployed in isolation
  ✓ Zero-trust by default: a service never trusts the caller without
    verifying, even inside the network perimeter
  ✗ Duplicated validation logic (or a shared library — but then its
    version has to be kept in sync across every service)
  ✗ N services = N places where JWKS/aud config can be wrong

Option B — the API Gateway validates once, then a trusted network:

  Client → API Gateway (validates the JWT, extracts claims, forwards
                         them as internal headers/an internal
                         short-TTL JWT)
         → Service A (trusts headers FROM THE GATEWAY, doesn't
                       re-verify the signature)
         → Service B (same)

  ✓ Validation in one place — easier to maintain, easier to roll out
    a policy change (a new check, say) everywhere at once
  ✓ Internal services are simpler — no auth dependencies to carry
  ✗ The gateway becomes a critical trust point: if it's compromised
    or misconfigured, every downstream service "trusts blindly"
  ✗ Requires strict network isolation ("this service only accepts
    traffic FROM THE GATEWAY") — otherwise Service A can be reached
    directly, bypassing the check entirely
```

Practical recommendation: **Option A (every service validates itself) is the safer default**. That is especially true in cloud or Kubernetes environments, where network isolation itself isn't guaranteed. A neighbouring pod in the same namespace can physically reach Service A.

Option B pays off when the gateway is part of a deliberate zero-trust architecture with mTLS (mutual TLS) between the gateway and the services. It does not pay off just to save one JWKS call. JWKS validation is cheap, local and network-free (see article 03), so "performance" is rarely a strong argument for Option B.

## Client Credentials between internal services — authorization with no user

Sometimes Service A calls Service B on its own behalf, not on behalf of a user. Think of a background job, a cron task, or an internal call between services. That is exactly the Client Credentials grant type from article 01, implemented as concrete NestJS code.

```typescript
// service-a: obtaining a service-to-service token before calling Service B
@Injectable()
export class ServiceTokenProvider {
  private cachedToken?: { token: string; expiresAt: number };

  constructor(private http: HttpService, private config: ConfigService) {}

  async getToken(): Promise<string> {
    if (this.cachedToken && this.cachedToken.expiresAt > Date.now()) {
      return this.cachedToken.token; // reuse until it's about to expire
    }

    const response = await firstValueFrom(
      this.http.post(
        `${this.config.get('KEYCLOAK_ISSUER')}/protocol/openid-connect/token`,
        new URLSearchParams({
          grant_type: 'client_credentials',
          client_id: 'service-a',
          client_secret: this.config.get('SERVICE_A_SECRET')!,
        }),
      ),
    );

    this.cachedToken = {
      token: response.data.access_token,
      expiresAt: Date.now() + (response.data.expires_in - 30) * 1000, // 30s safety margin
    };
    return this.cachedToken.token;
  }
}
```

```typescript
// Using it when calling Service B
async callServiceB() {
  const token = await this.serviceTokenProvider.getToken();
  return this.http.get('https://service-b.internal/api/data', {
    headers: { Authorization: `Bearer ${token}` },
  });
}
```

An important detail: **Service B validates this token with the same Guard used for user tokens.** From the Resource Server's point of view the only difference is what's in the payload. A Client Credentials token has no `sub` pointing at a real user. Any roles it carries belong to the `service-account-service-a` service account, not to a human.

Does the business logic need to tell "a request from a human" from "a request from a service"? Then check that explicitly. Look at the presence or absence of the user-specific claims you expect, rather than building a separate Guard that duplicates JWKS validation.

## "The backend should refresh the token" — busting the myth with actual code

The misconception already mentioned in article 03 deserves a concrete implementation. What exactly should the Resource Server return when a token has expired, and why is trying to refresh it itself an architectural mistake?

```typescript
// Correct: a NestJS Exception Filter returning a structured 401 error
@Catch(UnauthorizedException)
export class TokenExpiredFilter implements ExceptionFilter {
  catch(exception: UnauthorizedException, host: ArgumentsHost) {
    const response = host.switchToHttp().getResponse();
    response.status(401).json({
      error: 'token_expired',
      message: 'Access token is invalid or expired. Obtain a new one via refresh.',
      // We do NOT try to go to Keycloak and refresh the token on the
      // client's behalf — the Resource Server has no refresh token
      // and shouldn't have one
    });
  }
}
```

```txt
Why the backend should NOT refresh the token:

  1. The Resource Server physically doesn't have a refresh token —
     it lives with the CLIENT (in memory/an httpOnly cookie in an
     SPA, see article 06). The Resource Server only ever sees the
     access token in the Authorization header.

  2. Even if the backend somehow could get hold of a refresh token
     (say, in a BFF architecture, article 06, the one legitimate
     exception — but that's architecturally a DIFFERENT role, not
     "just an API"), the decision of "when and how to retry the
     original request after refreshing" belongs to the client,
     because only the client knows the context of the original
     request (what to retry, with what data).

  3. Blending the roles breaks the stateless model of the API:
     if the API starts managing tokens and deciding when to refresh
     them, it stops being a pure token consumer and becomes a
     hidden, undocumented auth client.
```

The correct full cycle lives on the client side, in the SPA (single-page application). See [React SPA Integration](./05-react-spa-integration.md) for the React details.

The client gets a 401. It tries `updateToken()`, or the equivalent, through the refresh token. If that succeeds, it retries the original request with the new access token. If the refresh also fails — the refresh token expired or was revoked — the client triggers a full re-login, a redirect to Keycloak.

The Resource Server takes part only in the first step of this chain: saying the token is no good. It knows nothing about what happens next.

## Tying it together

```txt
[Manual vs adapter]            →  transparency and control vs
                                 development speed — the decision
                                 hinges on audit requirements and
                                 on how likely a provider switch is

[Guards + decorators]           →  authentication and authorization
                                 are two separate Guards in a row,
                                 not one fused Guard

[Authorization Services / UMA]  →  when roles aren't granular enough
                                 — ownership, context, a policy
                                 editable without a deploy

[Monolith validation vs
 Gateway]                       →  where trust actually lives in a
                                 microservices architecture, and why
                                 "every service validates itself"
                                 is the safer default

[Client Credentials
 service-to-service]            →  the same Guard used for users —
                                 the only difference is what's in
                                 the payload

[Who refreshes the token]       →  always the client; the Resource
                                 Server only reports invalidity via
                                 401 + a clear error body
```

The next article, [React SPA Integration](./05-react-spa-integration.md), moves to the client side. It shows how a React app walks through Authorization Code + PKCE (Proof Key for Code Exchange). Then it covers refreshing tokens via `updateToken()`, and what happens when the refresh fails.

## Common interview traps

- **"nest-keycloak-connect is the only correct way to wire Keycloak into NestJS"** — not necessarily. It's a deliberate trade-off of development speed against transparency and vendor independence. For projects with strict security-audit requirements, or a real possibility of switching identity providers (IdP), the manual `passport-jwt` approach is often preferable.

- **"You can merge the authentication Guard and the role-check Guard into one, it's simpler"** — you can, but it hurts reusability. Suppose you later need a different authentication method, an API key for services for example, with the same authorization rules. The fused Guard has to be duplicated wholesale instead of reusing `RolesGuard`.

- **"Authorization Services are always needed, simple roles are never enough"** — an overreach. Simple roles are enough for rules that don't depend on a specific resource instance. Authorization Services pay off when a rule depends on ownership or context, or when non-technical staff need to manage policy without involving developers. That is an architectural decision with a real cost — a round-trip, cognitive overhead — not a "best practice by default".

- **"An API Gateway that validates the token once is always better for performance"** — performance is a weak argument here. JWKS validation is local and cheap, on the order of microseconds. "Every service validates itself" is usually the safer default, especially without strict mTLS isolation between the gateway and the services.

- **"The backend should refresh the access token when it notices it's expired"** — no, the Resource Server has no access to the client's refresh token. The one exception is a BFF (backend for frontend) architecture, where that is a separate, deliberately designed role, not "any backend". The correct API reaction to an expired token is a 401 with a clear error body; refreshing the token is the client's job.
