# Security Fundamentals

## Why security matters for full-stack developers

Most serious vulnerabilities aren't the result of sophisticated attacks. They're the consequence of bad architectural decisions: storing passwords in plain text, missing input validation, overly privileged services. A developer is responsible for application security across the entire stack — from SQL (structured query language) queries to HTTP headers.

## CIA Triad — the three fundamental security properties

CIA has nothing to do with an intelligence agency here. The letters stand for confidentiality, integrity and availability, and every information security system is built on those three principles.

**Confidentiality — data is accessible only to authorized parties.**

Threats: traffic interception by MITM (a man-in-the-middle sitting between client and server), token leakage, SQL Injection.

Controls: encryption in transit with TLS (transport layer security), which is what HTTPS (HTTP over TLS) gives you. Then JWT (JSON Web Token), RBAC (role-based access control) and encryption of data at rest.

**Integrity — data cannot be modified by unauthorized parties without detection.**

Threats: SQL Injection that modifies the database directly. Also CSRF (cross-site request forgery) acting on behalf of the user, and tampering with a JWT payload that carries no valid signature.

Controls: the JWT signature, HMAC (hash-based message authentication code), digital signatures, database transactions.

**Availability — the system must be accessible to authorized users.**

An attack on availability aims at denial of service (DoS) rather than at the data itself. DDoS is the same attack spread across many machines at once.

Threats: DDoS, resource exhaustion (unbounded queries, regex DoS), dependency on an external service without a fallback.

Controls: rate limiting, circuit breaker, horizontal scaling.

Common interview questions: "What does DDoS violate?" — Availability. "What does JWT interception violate?" — Confidentiality. "What does CSRF violate?" — Integrity (action on behalf of the user without their knowledge).

## Authentication vs Authorization — a fundamental distinction

The two words differ by one question each: authentication asks who you are, authorization asks what you may do. Authorization only makes sense once authentication has succeeded.

**Authentication — who are you?** The process of verifying a user's identity. Methods: login and password, OAuth 2.0, passkeys, multi-factor authentication. The question it settles: are you really Ivan Ivanov?

**Authorization — what are you allowed to do?** The process of checking permissions after identity is confirmed. Methods: RBAC (roles), ABAC (attribute-based access control), ACL (access control lists). The question it settles: is Ivan Ivanov allowed to delete users?

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

The principle applies everywhere: database users, IAM (identity and access management) roles in Amazon Web Services, Linux permissions, OAuth 2.0 scopes.

## Attack Surface — all entry points

The attack surface is the sum of all points through which an attacker may attempt to enter or extract data from a system.

The table below is the typical surface of a web application, entry point by entry point.

| Entry point | What is attacked there |
|---|---|
| HTTP API | SQL Injection, parameter tampering, auth bypass |
| HTML forms | XSS (cross-site scripting), CSRF |
| File upload | path traversal, malicious file execution |
| WebSockets | missing auth check, message spoofing |
| Admin panel | brute force, privilege escalation |
| Third-party deps | supply chain attacks through npm or pip packages |
| Environment vars | secrets exposure in logs, error messages |
| GraphQL | introspection, query complexity DoS |

Rule: every new endpoint or integration increases the attack surface. That decision must be made deliberately, with corresponding protections added.

## Defense in Depth — layered protection

Relying on a single defense is a fundamental mistake. Defense in Depth: if one layer is breached, the next should stop the attack.

Take one API endpoint as the example. Nine layers can stand in front of it, and each one stops a different class of attack.

| Layer | What it stops |
|---|---|
| 1. HTTPS | traffic interception by a man-in-the-middle |
| 2. Rate limiting | brute force, DoS |
| 3. JWT validation | authentication |
| 4. Role and permission check | authorization |
| 5. Input validation (Zod, Joi) | injection, invalid data |
| 6. Parameterized queries | SQL Injection |
| 7. Output encoding | XSS during rendering |
| 8. Security headers (Helmet.js) | clickjacking, content-type sniffing |
| 9. Audit logging | attack detection after the fact |

Each layer is independent — a vulnerability in one doesn't open the entire system.

## Security Through Obscurity — an anti-pattern

Hiding information (URLs, API structure, technology stack) is not a security control.

Compare what only looks like protection with what actually is protection.

**Bad — security through obscurity:**

- `/api/secret-admin-panel-v2`, which an attacker finds via brute force.
- Hiding the stack version in headers, because security through ignorance is an illusion.
- "Nobody knows this endpoint" — any scanner finds it in minutes.

**Good — real protection:**

- `/api/admin-panel` that requires a JWT with `role='admin'`, plus an IP (internet protocol) whitelist.
- Open-source code with good architecture is more secure than closed-source code with architectural flaws.

Kerckhoffs's principle: a system should be secure even if everything about it is known, except the key. Modern cryptography works exactly this way.

## HTTPS and TLS — the mandatory foundation

The value of HTTPS is easiest to see by putting the two sides next to each other.

**What happens without HTTPS:**

1. The user sends a password, and it is visible in plain text on the network.
2. A JWT in the `Authorization` header is intercepted.
3. A cookie with a session token is intercepted.

Any network node between client and server can see that data.

**What TLS provides, and HTTPS with it:**

1. Channel encryption: the data is encrypted, and a man-in-the-middle sees ciphertext.
2. Server authentication: the SSL (secure sockets layer) certificate confirms it's your server, not an attacker.
3. Integrity: the TLS MAC (message authentication code) guarantees the data wasn't modified in transit.

```typescript
// Express: force redirect from HTTP to HTTPS
app.use((req, res, next) => {
  const isProduction = process.env.NODE_ENV === 'production';
  if (isProduction && req.header('x-forwarded-proto') !== 'https') {
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

- **"Authentication = Authorization"** — these are different concepts. Authentication answers "who are you?", authorization — "what are you allowed to do?". Validating a JWT = authentication. Checking a role/permission for a resource = authorization. Many systems check authentication but skip authorization. That gap is called IDOR (insecure direct object reference).

- **"HTTPS encrypts data in the database"** — HTTPS only encrypts network traffic (the transmission channel). Data in the database is not encrypted by HTTPS. Protecting data at rest requires encryption at the database or application level.

- **"Security Through Obscurity is sufficient"** — hiding URLs or technology stacks is not a security control. Proper authorization on an endpoint matters more than its "secrecy". Attackers easily find endpoints via brute force, traffic interception, or source code.

- **"CIA = Central Intelligence Agency in a security context"** — in infosec, CIA Triad stands for Confidentiality, Integrity, Availability — three fundamental security properties, unrelated to intelligence agencies.

- **"Defense in Depth = many passwords"** — it's a principle of layered protection: each layer (HTTPS → Auth → Authorization → Validation → Encoding) independently defends against different attack classes.
