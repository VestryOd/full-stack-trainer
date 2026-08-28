# OWASP Top 10 (2021)

## What is OWASP Top 10

OWASP (Open Worldwide Application Security Project) is a non-profit organization publishing the top 10 most critical web application vulnerabilities. Updated approximately every 3-4 years. Interviews don't require memorizing the whole list. They do expect deep understanding of the first 5-7 entries, plus specific examples and defenses you can cite.

## A01: Broken Access Control

**#1 since 2021.** 94% of tested applications had this vulnerability.

```typescript
// IDOR (Insecure Direct Object Reference) — typical scenario
// GET /api/orders/12345 → user changes to /api/orders/12346
// Without ownership check → access to another user's order

// Other examples:
// - User accesses admin endpoint without role check
// - /admin URL works without authentication
// - Privilege escalation by editing JWT payload (alg:none attack)
// - Horizontal movement: user A sees user B's data

// Defense:
app.get('/api/orders/:id', authenticate, async (req, res) => {
  // ownership is baked into the query: someone else's order simply won't be found
  const order = await prisma.order.findFirst({
    where: req.user.role === 'admin'
      ? { id: req.params.id }
      : { id: req.params.id, userId: req.user.id },
  });
  // 404, not 403: a 403 would confirm the order exists but isn't theirs,
  // which helps an attacker map out valid ids
  if (!order) return res.status(404).json({ error: 'Not found' });
  res.json(order);
});

// Defense principles:
// 1. Deny by default — forbid everything, explicitly allow
// 2. Check ownership at the DB query level (not in memory)
// 3. Log access denials and alert on anomalies
```

## A02: Cryptographic Failures

Formerly called "Sensitive Data Exposure". Covers incorrect use or absence of cryptography.

Typical scenarios:

- HTTP instead of HTTPS (Hypertext Transfer Protocol Secure), so data travels in plaintext.
- Passwords in plaintext, or hashed with the deprecated MD5 (Message Digest 5) and SHA-1 (Secure Hash Algorithm 1).
- JWT (JSON Web Token) with `algorithm=none`, so the signature is not verified.
- Personally identifiable information (PII) in logs: email, IP (internet protocol) address, credit card.
- Weak encryption keys, under 128 bit.
- ECB (electronic codebook) mode usage, which is deterministic, so patterns stay visible.
- Secrets in git history.

Defenses:

- HTTPS everywhere, with the HSTS (HTTP Strict Transport Security) header.
- bcrypt or Argon2 for passwords.
- AES-256-GCM for data at rest, the Advanced Encryption Standard in Galois/Counter Mode.
- Explicit JWT algorithm check: `jwt.verify(token, secret, { algorithms: ['HS256'] })`.
- Data classification: know what's sensitive and protect accordingly.

## A03: Injection

Injection is a family of vulnerabilities, not a single bug. Untrusted input reaches an interpreter that reads it as instructions:

- SQL (Structured Query Language) injection, against a relational database.
- NoSQL (non-relational database) injection, against stores such as MongoDB.
- LDAP (Lightweight Directory Access Protocol) injection, against a directory server.
- OS Command injection, where the input reaches the operating system shell.
- SSTI (server-side template injection), where the input reaches a template engine.

```typescript
// SQL Injection (see: [SQL Injection and Input Validation])
// Command Injection — equally dangerous:

// VULNERABLE: passing user input to the shell
import { exec } from 'child_process';
app.post('/api/convert', (req, res) => {
  exec(`convert ${req.body.filename} output.pdf`, (err, stdout) => {
    // filename = "image.jpg; rm -rf /; echo" → catastrophe
  });
});

// SAFE: avoid the shell, use argument arrays
import { execFile } from 'child_process';
app.post('/api/convert', (req, res) => {
  const safeFilename = path.basename(req.body.filename); // strip path traversal
  execFile('convert', [safeFilename, 'output.pdf'], (err, stdout) => { /* ... */ });
  // execFile doesn't interpret shell metacharacters
});
```

## A04: Insecure Design

Architectural vulnerabilities — ones that can't be fixed with just a code patch.

Examples:

- No rate limiting on the login endpoint, so brute force is possible.
- Password reset without MFA (multi-factor authentication) and without token expiry, which gives account takeover.
- No lockout after N attempts, which opens the door to enumeration attacks.
- Critical operations without a second confirmation factor.
- All data in one database without isolation.
- A public S3 (Amazon Simple Storage Service) bucket for private documents.

Threat modeling belongs in the design phase, and its checklist is STRIDE — one letter per class of threat:

- **S** — Spoofing identity.
- **T** — Tampering with data.
- **R** — Repudiation.
- **I** — Information disclosure.
- **D** — Denial of service.
- **E** — Elevation of privilege.

Every feature should pass through STRIDE before any code is written.

## A05: Security Misconfiguration

Misconfiguration is about defaults that nobody changed. The code below shows four such defaults next to the fix for each, starting with a wildcard CORS (cross-origin resource sharing) origin.

```typescript
// Examples of misconfiguration:

// BAD: all CORS origins allowed
app.use(cors({ origin: '*' })); // API with auth + wildcard = risk

// BAD: stack trace in production response
app.use((err, req, res, next) => {
  res.status(500).json({ error: err.message, stack: err.stack }); // info leak
});

// GOOD:
app.use((err, req, res, next) => {
  logger.error({ err, requestId: req.id }); // log everything
  // the client gets the minimum
  res.status(500).json({ error: 'Internal server error', requestId: req.id });
});

// BAD: debug mode in production
// X-Powered-By: Express → exposes infrastructure info

// GOOD:
app.disable('x-powered-by');
app.use(helmet()); // adds security headers

// BAD: default credentials not changed
// PostgreSQL: postgres:postgres, MongoDB: no password
// S3 Bucket: public-read for internal files
```

## A06: Vulnerable and Outdated Components

Vulnerable components are found by scanners, not by reading code. The commands below check dependencies and Docker images for known CVEs, the publicly catalogued common vulnerabilities and exposures.

```bash
# Dependencies with known CVEs

# Checking (Node.js):
npm audit
npm audit --audit-level=high  # only high/critical

# Automation:
# GitHub Dependabot — automatic update PRs
# Snyk — more detailed analysis with remediation

# Docker images:
docker scout cves myapp:latest
trivy image myapp:latest  # CVE scanning

# Principle: update dependencies regularly
# Lock file (package-lock.json) pins versions → reproducible builds
# BUT the lock file doesn't protect if the package itself is compromised (supply chain)
```

## A07: Identification and Authentication Failures

Authentication fails in a handful of repeatable ways. The code below lists five: an unchecked JWT algorithm, no rate limiting on login, weak passwords, missing MFA, and predictable tokens.

```typescript
// Typical vulnerabilities:

// 1. JWT with algorithm=none (critical vulnerability in early libraries)
// Attacker: changes header to {"alg":"none"}, removes signature
// Vulnerable library accepts the token
// Defense: always specify algorithms explicitly
jwt.verify(token, secret, { algorithms: ['HS256'] }); // not ['HS256', 'none']!

// 2. No rate limiting on login
app.post('/auth/login', rateLimiter({ max: 5, windowMs: 15 * 60 * 1000 }), loginHandler);

// 3. Weak passwords: no minimum complexity check
// Check via zxcvbn (password strength estimation):
import zxcvbn from 'zxcvbn';
const { score } = zxcvbn(password); // 0-4, require >= 3

// 4. No MFA for privileged operations
// 5. Predictable session/reset tokens (not cryptographically random)
// BAD: Math.random() → predictable
// GOOD: crypto.randomBytes(32).toString('hex')
```

## A08: Software and Data Integrity Failures

Covers supply chain vulnerabilities and data integrity violations.

A supply chain attack compromises a popular package instead of your code. Log4Shell (2021) and `XZ Utils` (2024) are the best-known cases. An attacker compromises a package on npm, pip, or maven, and every application using that package is vulnerable.

Defenses:

- Subresource Integrity (SRI) for scripts served from a CDN (content delivery network): `<script src="..." integrity="sha384-..." crossorigin="anonymous">`.
- npm lockfile (`package-lock.json`) with integrity hash verification.
- Signed Docker images (Docker Content Trust).
- Package signature verification: npm provenance, sigstore on the Python Package Index (PyPI).
- Verify artifact checksums in the pipeline for continuous integration and continuous delivery (CI/CD).

Deserialization is the other half of this category:

- Never deserialize user input into objects.
- `JSON.parse` is safe, `eval()` is not.
- Opaque tokens for refresh tokens, not a JWT with a complex payload.

## A09: Security Logging and Monitoring Failures

Logging here has two jobs: record enough to notice an attack, and never write a secret into the log. The code below does both.

```typescript
// What to log (and how to do it safely):

const sensitiveFields = ['password', 'token', 'secret', 'creditCard', 'ssn'];

function sanitizeForLog(obj: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(obj).map(([key, value]) =>
      sensitiveFields.some(f => key.toLowerCase().includes(f))
        ? [key, '[REDACTED]']
        : [key, value]
    )
  );
}

// Must log:
// - Successful and failed login attempts (with userId/IP)
// - Authorization denials (403) — brute force/scanning pattern
// - Privilege changes (user role)
// - Admin actions
// - SQL errors (possible injection attempt)
// - Anomalous patterns: N requests/sec from one IP

// Alerting (median time to detect an attack without monitoring: 200+ days):
// AWS CloudWatch Alerts, Datadog, PagerDuty
// Alert on: 5+ 403s in 1 min from one IP → block/investigate
```

## A10: Server-Side Request Forgery (SSRF)

Server-Side Request Forgery, or SSRF, is a vulnerability where the server makes an HTTP request to an arbitrary URL as directed by an attacker.

```typescript
// Vulnerable scenario: "download image by URL"
app.post('/api/fetch-image', authenticate, async (req, res) => {
  const { url } = req.body;
  // VULNERABLE: attacker provides:
  // - "http://localhost:5432" → connects to internal PostgreSQL
  // - "http://169.254.169.254/latest/meta-data/iam/security-credentials/"
  //   → AWS Instance Metadata Service → obtains IAM credentials
  // - "http://internal.company.service/admin" → internal APIs
  const response = await fetch(url);
  res.send(await response.buffer());
});

// Defense: allowlist + DNS rebinding protection
import { Resolver } from 'dns/promises';

const ALLOWED_HOSTS = new Set(['images.example.com', 'cdn.example.com']);
const PRIVATE_RANGES = [
  /^127\./,
  /^10\./,
  /^192\.168\./,
  /^172\.(1[6-9]|2\d|3[01])\./,
  /^169\.254\./,  // link-local (AWS metadata)
  /^::1$/,
  /^fc00:/,
];

async function safeRequest(url: string): Promise<Response> {
  const parsed = new URL(url);

  // Allowlist by hostname
  if (!ALLOWED_HOSTS.has(parsed.hostname)) {
    throw new Error('Host not allowed');
  }

  // DNS lookup → verify IP is not private (DNS rebinding protection)
  const resolver = new Resolver();
  const [ip] = await resolver.resolve4(parsed.hostname);
  if (PRIVATE_RANGES.some(r => r.test(ip))) {
    throw new Error('Private IP ranges not allowed');
  }

  // Use the resolved IP to connect (not the hostname again)
  return fetch(url); // in production: use a library with IP binding
}
```

## Common interview mistakes

- **"I know the OWASP Top 10 by heart"** — this alone has no value. What matters is explaining the mechanism of each vulnerability, giving a concrete code example, and describing the defense. "A01 — Broken Access Control — missing ownership check" is worth more than reciting the list.

- **"A03 Injection = SQL Injection only"** — Injection covers SQL, NoSQL, OS Command, LDAP, SSTI (Server-Side Template Injection). Command Injection is often more critical because it gives RCE (Remote Code Execution).

- **"SSRF is a rare edge case"** — SSRF has been in the Top 10 since 2021. In cloud environments it is especially dangerous. The Instance Metadata Service on AWS (Amazon Web Services) and GCP (Google Cloud Platform) can expose IAM (identity and access management) credentials.

- **"Security Misconfiguration means only wrong file permissions"** — it covers a wide range. Open S3 buckets, debug mode in production, an X-Powered-By header exposing the stack, default credentials, and overly permissive CORS settings all belong here.

- **"A08 Software Integrity is just about dependencies"** — it also covers pipeline integrity violations (CI/CD), unsigned updates, and deserialization of untrusted data.
