# Authentication vs Authorization

## The fundamental distinction

```txt
Authentication                     Authorization
────────────────────────────────   ──────────────────────────────
"WHO ARE YOU?"                      "WHAT ARE YOU ALLOWED TO DO?"
Verifying identity                  Checking permissions
Happens FIRST                       Happens AFTER authentication
Result: identity (userId)           Result: permitted/denied
```

A typical vulnerability: the system checks that a JWT is valid (authentication) but doesn't check that this specific user has the right to access this resource (authorization) → Insecure Direct Object Reference (IDOR).

## Authentication methods

```txt
1. Password-based
   Most common. Risks: brute force, phishing, password reuse.
   Requires: bcrypt/argon2 storage, rate limiting, lockout after N attempts.

2. Token-based (JWT)
   Stateless. Server doesn't store session state.
   Used in REST APIs and mobile apps. More detail: [JWT and Refresh Tokens].

3. OAuth 2.0 / OpenID Connect
   Delegated authentication: "Sign in with Google/GitHub".
   OAuth 2.0 = authorization protocol (resource access).
   OpenID Connect = layer on top of OAuth 2.0 for identity (authentication).

4. Session-based (Cookie + Server Session)
   Server stores the session (Redis/DB). Cookie contains only session ID.
   Advantage: instant revoke. Disadvantage: stateful, harder to scale.

5. Multi-Factor Authentication (MFA)
   Something you know (password) + something you have (TOTP code) +
   something you are (biometrics). Critical for admin accounts.

6. Passkeys (WebAuthn)
   Cryptographic keypair: private key on device, public key at server.
   Phishing-resistant: key is bound to the origin. The emerging standard.
```

## Authorization models

### RBAC — Role-Based Access Control

Permissions are determined by the user's role. The most common model.

```typescript
// Defining roles and permissions
const PERMISSIONS = {
  'admin': ['users:read', 'users:write', 'users:delete', 'orders:all'],
  'manager': ['orders:read', 'orders:write', 'users:read'],
  'customer': ['orders:read:own', 'profile:write:own'],
} as const;

type Role = keyof typeof PERMISSIONS;

// Middleware for checking permissions
function requirePermission(permission: string) {
  return (req: Request, res: Response, next: NextFunction) => {
    const userPermissions = PERMISSIONS[req.user.role as Role] ?? [];
    if (!userPermissions.includes(permission as never)) {
      return res.status(403).json({ error: 'Insufficient permissions' });
    }
    next();
  };
}

// Usage
router.delete('/users/:id', authenticate, requirePermission('users:delete'), deleteUser);
```

RBAC limitation: roles become blunt instruments as complexity grows. A "Manager" might be able to see ALL users — but should only see THEIR OWN.

### ABAC — Attribute-Based Access Control

The decision is made based on attributes of the user, resource, and environment.

```typescript
// Policy-based: "user can edit a resource if they own it"
function canEdit(user: User, resource: Order): boolean {
  if (user.role === 'admin') return true;
  if (resource.ownerId === user.id) return true;
  if (user.role === 'manager' && resource.department === user.department) return true;
  return false;
}

app.patch('/orders/:id', authenticate, async (req, res) => {
  const order = await db.orders.findById(req.params.id);
  if (!canEdit(req.user, order)) {
    return res.status(403).json({ error: 'Forbidden' });
  }
  // ...
});
```

ABAC is more flexible than RBAC but harder to audit ("who has access to this resource?").

### Resource-based Authorization (Ownership Check)

The most common pattern in real applications: checking resource ownership.

```typescript
// IDOR vulnerability — missing ownership check
app.get('/api/orders/:id', authenticate, async (req, res) => {
  // BAD: any authenticated user can see any order
  const order = await db.orders.findById(req.params.id);
  res.json(order);
});

// Fixed
app.get('/api/orders/:id', authenticate, async (req, res) => {
  const order = await db.orders.findById(req.params.id);
  if (!order) return res.status(404).json({ error: 'Not found' });

  // Ownership check: either the owner or an admin
  if (order.userId !== req.user.id && req.user.role !== 'admin') {
    return res.status(403).json({ error: 'Forbidden' });
  }

  res.json(order);
});
```

## JWT as an identity carrier for authorization

JWT contains claims used for authorization without a database roundtrip:

```typescript
// JWT payload at login
const token = jwt.sign(
  {
    sub: user.id,           // subject — user identifier
    email: user.email,
    role: user.role,        // used for RBAC
    permissions: ['orders:read', 'profile:write:own'], // for fine-grained ABAC
  },
  process.env.JWT_SECRET!,
  { expiresIn: '15m' }
);

// Middleware: decode JWT and attach user to req
function authenticate(req: Request, res: Response, next: NextFunction) {
  const token = req.headers.authorization?.replace('Bearer ', '');
  if (!token) return res.status(401).json({ error: 'Unauthorized' });

  try {
    req.user = jwt.verify(token, process.env.JWT_SECRET!) as JwtPayload;
    next();
  } catch {
    res.status(401).json({ error: 'Invalid token' });
  }
}
```

Important: the role/permissions in a JWT are a snapshot at issuance time. If a user's role changes in the DB, the JWT with the old role remains valid until expiry. Solution: short TTL (15 min) + refresh token.

## Session-based vs Token-based — comparison

```txt
Session-based (Cookie + Redis):
  ✓ Instant revoke: delete session from Redis → user is logged out
  ✓ Payload not visible to the client
  ✗ Stateful: all servers need access to the same Redis
  ✗ CSRF risk (cookie sent automatically by browser)
  When: traditional web apps, when instant revoke matters

Token-based (JWT):
  ✓ Stateless: any server can verify without a storage roundtrip
  ✓ Great for microservices and APIs
  ✗ Revoke only via blacklist (negates the stateless advantage)
     or wait for TTL expiry
  ✗ Payload is visible (base64) — don't put sensitive data in it
  When: REST API, mobile, inter-service communication
```

## OAuth 2.0 — delegated authorization

OAuth 2.0 is an authorization protocol (not authentication). The user grants an application access to their resources at another provider.

```txt
Authorization Code Flow (most secure for web):

1. Client → Authorization Server:
   GET /oauth/authorize?
     response_type=code&
     client_id=MY_APP&
     redirect_uri=https://myapp.com/callback&
     scope=read:email&
     state=RANDOM_STRING    ← CSRF protection

2. User logs in at the provider (Google/GitHub)
   and grants access

3. Authorization Server → Client:
   GET /callback?code=AUTH_CODE&state=RANDOM_STRING

4. Client → Authorization Server (server-to-server):
   POST /oauth/token
   { code, client_id, client_secret, redirect_uri }
   → { access_token, refresh_token, id_token }

5. Client → Resource Server:
   GET /api/user  Authorization: Bearer ACCESS_TOKEN
```

OpenID Connect adds an `id_token` (JWT with identity data) to the standard OAuth 2.0 flow.

## Common interview mistakes

- **"OAuth = Authentication"** — OAuth 2.0 is an AUTHORIZATION protocol (resource access). For authentication via OAuth, you need OpenID Connect (a layer on top of OAuth 2.0 that adds id_token and a /userinfo endpoint).

- **"JWT itself = authorization"** — JWT is a token format that carries identity and claims. Authorization is the act of checking those claims against access rules. JWT without subsequent permission checks = only authentication.

- **"RBAC is always sufficient"** — for simple systems, yes. But for "a user sees only their own resources," you need an ownership check (resource-based authorization), not just a role check.

- **"Authorization doesn't need to be checked on every endpoint"** — every endpoint must explicitly verify authorization. The pattern of "we'll add auth later" leads to IDOR (Insecure Direct Object Reference) vulnerabilities.

- **"Sessions and JWT are incompatible"** — they're not competitors. You can use JWT for the API and cookie sessions for the web UI in the same application. The choice depends on revoke requirements, clients, and architecture.
