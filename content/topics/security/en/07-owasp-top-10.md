# OWASP Top 10 (2021)

## What is OWASP Top 10

OWASP (Open Worldwide Application Security Project) is a non-profit organization publishing the top 10 most critical web application vulnerabilities. Updated approximately every 3-4 years. Interviews don't require memorizing the whole list, but they expect deep understanding of the first 5-7 entries and the ability to cite specific examples and defenses.

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
  const order = await prisma.order.findUnique({ where: { id: req.params.id } });
  if (!order || (order.userId !== req.user.id && req.user.role !== 'admin')) {
    return res.status(403).json({ error: 'Forbidden' }); // not 404 — info leak
  }
  res.json(order);
});

// Defense principles:
// 1. Deny by default — forbid everything, explicitly allow
// 2. Check ownership at the DB query level (not in memory)
// 3. Log access denials and alert on anomalies
```

## A02: Cryptographic Failures

Formerly called "Sensitive Data Exposure". Covers incorrect use or absence of cryptography.

```txt
Typical scenarios:
  - HTTP instead of HTTPS (data in plaintext)
  - Passwords in plaintext or MD5/SHA-1 (deprecated)
  - JWT with algorithm=none (signature not verified)
  - PII data in logs (email, IP, credit card)
  - Weak encryption keys (< 128 bit)
  - ECB mode usage (deterministic → patterns visible)
  - Secrets in git history

Defenses:
  - HTTPS everywhere (HSTS header)
  - bcrypt/Argon2 for passwords
  - AES-256-GCM for data at rest
  - Explicit JWT algorithm check: jwt.verify(token, secret, { algorithms: ['HS256'] })
  - Data classification: know what's sensitive and protect accordingly
```

## A03: Injection

Includes SQL, NoSQL, LDAP, OS Command, SSTI injection.

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

```txt
Examples:
  - No rate limiting on login endpoint → brute force possible
  - Password reset without MFA and without token expiry → account takeover
  - No lockout after N attempts → enumeration attacks
  - Critical operations without a second confirmation factor
  - All data in one DB without isolation
  - Public S3 bucket for private documents

Threat Modeling (STRIDE): during design phase:
  S — Spoofing identity
  T — Tampering with data
  R — Repudiation
  I — Information disclosure
  D — Denial of service
  E — Elevation of privilege

Every feature should pass through STRIDE before any code is written.
```

## A05: Security Misconfiguration

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
  res.status(500).json({ error: 'Internal server error', requestId: req.id }); // client gets minimum
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

```txt
Supply Chain Attack: Log4Shell (2021), XZ Utils (2024)
  - Attacker compromises a popular package (npm/pip/maven)
  - All applications using the package are vulnerable

Defenses:
  - Subresource Integrity (SRI) for CDN scripts:
    <script src="..." integrity="sha384-..." crossorigin="anonymous">
  - npm lockfile (package-lock.json) with integrity hash verification
  - Signed Docker images (Docker Content Trust)
  - Package signature verification (npm provenance, PyPI sigstore)
  - CI/CD pipeline: verify artifact checksums

Deserialization vulnerabilities:
  - Never deserialize user input into objects
  - JSON.parse is safe, eval() is not
  - Opaque tokens (not JWT with complex payload) for refresh tokens
```

## A09: Security Logging and Monitoring Failures

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

SSRF — a vulnerability where the server makes an HTTP request to an arbitrary URL as directed by an attacker.

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

- **"SSRF is a rare edge case"** — SSRF has been in the Top 10 since 2021. In cloud environments (AWS/GCP), it's especially dangerous because of the Instance Metadata Service, which can expose IAM credentials.

- **"Security Misconfiguration means only wrong file permissions"** — it covers a wide range: open S3 buckets, debug mode in production, X-Powered-By header exposing the stack, default credentials, overly permissive CORS settings.

- **"A08 Software Integrity is just about dependencies"** — it also covers pipeline integrity violations (CI/CD), unsigned updates, and deserialization of untrusted data.
