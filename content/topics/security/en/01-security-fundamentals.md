# Security Fundamentals

## Why security matters for full-stack developers

Most serious vulnerabilities aren't the result of sophisticated attacks. They're the consequence of bad architectural decisions: storing passwords in plain text, missing input validation, overly privileged services. A developer is responsible for application security across the entire stack — from SQL queries to HTTP headers.

## CIA Triad — the three fundamental security properties

Every information security system is built on three principles:

```txt
Confidentiality
  Data is accessible only to authorized parties.
  Threats: traffic interception (MITM), token leakage, SQL Injection
  Controls: encryption (TLS/HTTPS), JWT, RBAC, encryption at rest

Integrity
  Data cannot be modified by unauthorized parties without detection.
  Threats: SQL Injection (direct DB modification), CSRF (action on
  behalf of the user), JWT payload tampering without valid signature
  Controls: JWT Signature, HMAC, digital signatures, DB transactions

Availability
  The system must be accessible to authorized users.
  Threats: DDoS, resource exhaustion (unbounded queries, regex DoS),
  external service dependency without fallback
  Controls: Rate Limiting, Circuit Breaker, horizontal scaling
```

Common interview questions: "What does DDoS violate?" — Availability. "What does JWT interception violate?" — Confidentiality. "What does CSRF violate?" — Integrity (action on behalf of the user without their knowledge).

## Authentication vs Authorization — a fundamental distinction

```txt
Authentication: WHO ARE YOU?
  The process of verifying a user's identity.
  Methods: login/password, OAuth 2.0, passkeys, multi-factor auth.
  Question: "Are you really Ivan Ivanov?"

Authorization: WHAT ARE YOU ALLOWED TO DO?
  The process of checking permissions after identity is confirmed.
  Methods: RBAC (roles), ABAC (attributes), ACL (access control lists).
  Question: "Is Ivan Ivanov allowed to delete users?"
```

A typical mistake: checking only authentication (valid JWT) but not authorization (right to access this resource). Example vulnerability:

```typescript
// INSECURE: only checks that the token is valid
app.get('/api/users/:id', authenticate, async (req, res) => {
  const user = await db.users.findById(req.params.id);
  res.json(user);
});

// SECURE: checks both authentication and the right to access this resource
app.get('/api/users/:id', authenticate, async (req, res) => {
  if (req.user.id !== req.params.id && req.user.role !== 'admin') {
    return res.status(403).json({ error: 'Forbidden' });
  }
  const user = await db.users.findById(req.params.id);
  res.json(user);
});
```

## Principle of Least Privilege — minimal necessary permissions

Every component of a system should have only the permissions strictly required for its function.

```typescript
// In Node.js / services:

// BAD: one DB user with full privileges
// postgres://admin:password@localhost/db
// If credentials are stolen → full DB access

// GOOD: separate DB users with restricted permissions
// postgres://app_user:password@localhost/db
// app_user has only: SELECT, INSERT, UPDATE, DELETE on required tables
// NO: DROP, CREATE, TRUNCATE, access to system tables

// Applied to API endpoints:
const router = express.Router();
router.post('/orders', requireRole('customer'));          // create order
router.patch('/orders/:id/status', requireRole('admin')); // change status
router.delete('/orders/:id', requireRole('admin'));       // delete order
```

The principle applies everywhere: DB users, AWS IAM roles, Linux permissions, OAuth 2.0 scopes.

## Attack Surface — all entry points

The attack surface is the sum of all points through which an attacker may attempt to enter or extract data from a system.

```txt
Typical web application attack surface:
  HTTP API         → SQL Injection, parameter tampering, auth bypass
  HTML Forms       → XSS, CSRF
  File Upload      → path traversal, malicious file execution
  WebSockets       → missing auth, message spoofing
  Admin Panel      → brute force, privilege escalation
  Third-party deps → supply chain attacks (npm/pip packages)
  Environment vars → secrets exposure in logs, error messages
  GraphQL          → introspection, query complexity DoS
```

Rule: every new endpoint or integration increases the attack surface. That decision must be made deliberately, with corresponding protections added.

## Defense in Depth — layered protection

Relying on a single defense is a fundamental mistake. Defense in Depth: if one layer is breached, the next should stop the attack.

```txt
Example: protecting an API endpoint

Layer 1: HTTPS                         → encrypts traffic (MITM)
Layer 2: Rate Limiting                 → brute force, DoS
Layer 3: JWT Validation                → authentication
Layer 4: Role/Permission Check         → authorization
Layer 5: Input Validation (Zod/Joi)   → injection, invalid data
Layer 6: Parameterized Queries         → SQL Injection
Layer 7: Output Encoding               → XSS during rendering
Layer 8: Security Headers (Helmet.js)  → clickjacking, MIME sniffing
Layer 9: Audit Logging                 → attack detection after the fact
```

Each layer is independent — a vulnerability in one doesn't open the entire system.

## Security Through Obscurity — an anti-pattern

Hiding information (URLs, API structure, technology stack) is not a security control.

```txt
BAD (Security Through Obscurity):
  /api/secret-admin-panel-v2          → attacker finds it via brute force
  Hiding stack version in headers     → security through ignorance = illusion
  "Nobody knows this endpoint"        → any scanner finds it in minutes

GOOD (real protection):
  /api/admin-panel + requires JWT with role='admin' + IP whitelist
  Open-source code with good architecture is more secure than
  closed-source code with architectural flaws
```

Kerckhoffs's principle: a system should be secure even if everything about it is known, except the key. Modern cryptography works exactly this way.

## HTTPS and TLS — the mandatory foundation

```txt
What happens without HTTPS:
  1. User sends password → visible in plain text on the network
  2. JWT in Authorization header → intercepted
  3. Cookie with session token → intercepted
  → Any network node between client and server can see the data

What TLS (HTTPS) provides:
  1. Channel encryption: data is encrypted, MITM sees ciphertext
  2. Server authentication: SSL certificate confirms it's your server,
     not an attacker
  3. Integrity: TLS MAC guarantees data wasn't modified in transit
```

```typescript
// Express: force redirect from HTTP to HTTPS
app.use((req, res, next) => {
  if (req.header('x-forwarded-proto') !== 'https' && process.env.NODE_ENV === 'production') {
    return res.redirect(301, `https://${req.headers.host}${req.url}`);
  }
  next();
});

// HSTS header: browser remembers "always HTTPS" for this domain
app.use(helmet.hsts({
  maxAge: 31536000,        // 1 year
  includeSubDomains: true,
  preload: true,
}));
```

## Common interview mistakes

- **"Authentication = Authorization"** — these are different concepts. Authentication answers "who are you?", authorization — "what are you allowed to do?". Validating a JWT = authentication. Checking a role/permission for a resource = authorization. Many systems check authentication but skip authorization (IDOR vulnerability).

- **"HTTPS encrypts data in the database"** — HTTPS only encrypts network traffic (the transmission channel). Data in the database is not encrypted by HTTPS. Protecting data at rest requires encryption at the database or application level.

- **"Security Through Obscurity is sufficient"** — hiding URLs or technology stacks is not a security control. Proper authorization on an endpoint matters more than its "secrecy". Attackers easily find endpoints via brute force, traffic interception, or source code.

- **"CIA = Central Intelligence Agency in a security context"** — in infosec, CIA Triad stands for Confidentiality, Integrity, Availability — three fundamental security properties, unrelated to intelligence agencies.

- **"Defense in Depth = many passwords"** — it's a principle of layered protection: each layer (HTTPS → Auth → Authorization → Validation → Encoding) independently defends against different attack classes.
