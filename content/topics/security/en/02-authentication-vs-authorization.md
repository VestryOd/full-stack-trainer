# Authentication vs Authorization

## The fundamental distinction

The two words answer different questions and run in a fixed order. Side by side they look like this.

| | Authentication | Authorization |
|---|---|---|
| The question | Who are you? | What are you allowed to do? |
| What it does | Verifying identity | Checking permissions |
| Order | Happens first | Happens after authentication |
| Result | Identity, the `userId` | Permitted or denied |

A typical vulnerability: the system checks that a JWT (JSON Web Token) is valid, which is authentication. It never checks that this specific user has the right to access this resource, which is authorization. The name of that hole is insecure direct object reference (IDOR).

## Authentication methods

Six methods cover almost everything you will meet in practice.

**1. Password-based.** Most common. Risks: brute force, phishing, password reuse. Requires bcrypt or argon2 storage, rate limiting, and lockout after N attempts.

**2. Token-based (JWT).** Stateless: the server doesn't store session state. Used in REST (representational state transfer) APIs and mobile apps. More detail in [JWT and Refresh Tokens](./03-jwt-access-refresh-tokens.md).

**3. OAuth 2.0 / OpenID Connect.** Delegated authentication: "Sign in with Google" or "Sign in with GitHub". OAuth 2.0 on its own is an authorization protocol about resource access. OpenID Connect is a layer on top of OAuth 2.0 for identity, which is authentication.

**4. Session-based (cookie + server session).** The server stores the session in Redis or a database, and the cookie contains only the session id. Advantage: instant revoke. Disadvantage: stateful, harder to scale.

**5. Multi-factor authentication (MFA).** Something you know (password) plus something you have (a TOTP code, time-based one-time password) plus something you are (biometrics). Critical for admin accounts.

**6. Passkeys (WebAuthn).** A cryptographic keypair: private key on the device, public key at the server. Phishing-resistant, because the key is bound to the origin. The emerging standard.

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

RBAC limitation: roles become blunt instruments as complexity grows. A "Manager" might be able to see **all** users — but should only see **their own**.

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

Important: the role and permissions in a JWT are a snapshot at issuance time. If a user's role changes in the database, the JWT with the old role remains valid until it expires. The fix is a short TTL (time to live) of 15 minutes plus a refresh token.

## Session-based vs Token-based — comparison

Both approaches keep a user logged in. They differ in where the state lives, and that single difference drives every line below.

**Session-based (cookie + Redis):**

- ✓ Instant revoke: delete the session from Redis and the user is logged out.
- ✓ Payload not visible to the client.
- ✗ Stateful: all servers need access to the same Redis.
- ✗ CSRF (cross-site request forgery) risk, because the browser sends the cookie automatically.
- When: traditional web apps, when instant revoke matters.

**Token-based (JWT):**

- ✓ Stateless: any server can verify the token without a storage roundtrip.
- ✓ Great for microservices and APIs.
- ✗ Revoke only via a blacklist, which negates the stateless advantage, or wait for the TTL to expire.
- ✗ Payload is visible, since base64 is encoding and not encryption — don't put sensitive data in it.
- When: REST API, mobile, inter-service communication.

## OAuth 2.0 — delegated authorization

OAuth 2.0 is an authorization protocol (not authentication). The user grants an application access to their resources at another provider. The Authorization Code Flow below is the variant to use on the web, and it runs in five steps.

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

- **"OAuth = Authentication"** — OAuth 2.0 is an **authorization** protocol (resource access). For authentication via OAuth, you need OpenID Connect (a layer on top of OAuth 2.0 that adds id_token and a /userinfo endpoint).

- **"JWT itself = authorization"** — JWT is a token format that carries identity and claims. Authorization is the act of checking those claims against access rules. JWT without subsequent permission checks = only authentication.

- **"RBAC is always sufficient"** — for simple systems, yes. But for "a user sees only their own resources," you need an ownership check (resource-based authorization), not just a role check.

- **"Authorization doesn't need to be checked on every endpoint"** — every endpoint must explicitly verify authorization. The pattern of "we'll add auth later" leads to IDOR vulnerabilities, that is insecure direct object reference.

- **"Sessions and JWT are incompatible"** — they're not competitors. You can use JWT for the API and cookie sessions for the web interface in the same application. The choice depends on revoke requirements, clients, and architecture.
