# Security: Interview Questions

Questions are grouped thematically. Each group includes a full senior-level answer + typical follow-up questions.

---

## Group 1: Security Fundamentals

### What is the CIA Triad and why does it matter?

CIA Triad — three fundamental security properties of any system:

**Confidentiality**: data is accessible only to authorized parties. Threats: traffic interception (MITM), SQL Injection, token leakage. Controls: HTTPS, encryption, RBAC.

**Integrity**: data cannot be modified without detection. Threats: CSRF (action on user's behalf), SQL Injection (data modification), JWT payload tampering without valid signature. Controls: HMAC, digital signatures, JWT Signature.

**Availability**: the system is accessible to authorized users. Threats: DDoS, regex DoS, resource exhaustion. Controls: Rate Limiting, Circuit Breaker.

```txt
Typical follow-ups:

Q: "What does a DDoS attack violate?"
A: Availability. DDoS exhausts server resources → legitimate users
   can't access the service.

Q: "What does intercepting a JWT violate?"
A: Confidentiality. The attacker gains access to data that was meant
   only for the authorized user.

Q: "What does CSRF violate?"
A: Integrity. An action is performed on behalf of the user without
   their knowledge → data is modified without authorization.
```

### What is Defense in Depth?

A principle of layered protection: if one layer is breached, the next should stop the attack. You can't rely on a single defense.

Example for an API endpoint: HTTPS (encryption) → Rate Limiting (brute force) → JWT Validation (authentication) → Role Check (authorization) → Zod/ValidationPipe (validation) → Parameterized Query (injection) → Output Encoding (XSS) → Security Headers (clickjacking).

```txt
Typical follow-ups:

Q: "What is Security Through Obscurity? Does it work?"
A: Attempting to secure a system by hiding information (secret URL,
   undocumented API). NOT a real defense: attackers find endpoints via
   brute force, scanning, source code. Real protection: authorization
   on the endpoint, regardless of how "secret" it is. Kerckhoffs's
   principle: a system is secure when the secret is only the key,
   not the algorithm.
```

---

## Group 2: JWT, Authentication, and Tokens

### Describe the structure of a JWT and what happens if the payload is modified

JWT — three base64url-encoded parts: `header.payload.signature`.

- **Header**: algorithm (`HS256`) and type
- **Payload**: claims (sub, role, exp, iat, jti) — NOT encrypted, anyone can read it
- **Signature**: HMAC(header + payload, secret) — guarantees integrity

If the payload is modified (e.g., `role: "user" → "admin"`): the signature becomes invalid on verification. The server must reject the token. Exception: the `alg:none` attack — if the library accepts algorithm=none, the signature is not checked. Defense: `jwt.verify(token, secret, { algorithms: ['HS256'] })` — explicit algorithm specification.

```txt
Typical follow-ups:

Q: "Can you put a password in a JWT?"
A: No. The payload is only signed, not encrypted. base64decode the
   payload without a key → anyone can see the contents.

Q: "How does HS256 differ from RS256?"
A: HS256 — symmetric (one secret for signing and verification).
   RS256 — asymmetric (private key signs, public key verifies).
   In microservices RS256 is preferable: each service verifies
   via the public key without knowing the private key.
```

### Explain the Access Token + Refresh Token scheme and the logout problem

**Why two tokens**: one long-lived JWT if stolen — catastrophic (30 days). Two tokens: Access (15 min, stateless) + Refresh (30 days, stored in DB).

**Flow**: Login → AccessToken (in JSON response) + RefreshToken (HttpOnly Cookie). After 15 min: POST /auth/refresh → new AccessToken. Logout: delete RefreshToken from DB + clearCookie.

**JWT Logout Problem**: Access Token is stateless — can't "revoke" it before TTL expires. Solutions: (1) short TTL (15 min), (2) Redis blacklist by jti, (3) Refresh Token Rotation (each refresh → new refresh token, old one invalidated).

```txt
Typical follow-ups:

Q: "Where is it safe to store an Access Token?"
A: Memory (JS variable) — protected from XSS, lost on page refresh.
   HttpOnly Cookie — protected from XSS, CSRF risk (need sameSite=strict).
   localStorage — INSECURE: XSS can steal it.

Q: "How do you detect Refresh Token theft?"
A: Refresh Token Rotation: on each refresh a new refresh token is issued,
   the old one is deleted from DB. If an attacker uses the stolen token →
   reuse attempt on an already-used token → alert + revoke ALL refresh
   tokens for that user.

Q: "What is OAuth 2.0 and how is it different from authentication?"
A: OAuth 2.0 is a delegated AUTHORIZATION protocol (resource access).
   For authentication you need OpenID Connect (a layer on top of OAuth 2.0
   that adds an id_token with identity data). "Sign in with Google" =
   OpenID Connect, not plain OAuth 2.0.
```

---

## Group 3: XSS, CSRF, and CORS

### Explain XSS, CSRF, and how they differ

**XSS** (Cross-Site Scripting): attacker injects JavaScript into pages; victim's browser executes it in the context of your site. Three types: Stored (in DB), Reflected (in URL), DOM-based (in client JS). Result: steal tokens from localStorage/cookies, keylogger, actions on user's behalf.

**CSRF** (Cross-Site Request Forgery): victim's browser (already authenticated) sends a request to your site from evil.com. Browser automatically attaches your domain's cookies. Server can't distinguish it from a legitimate request.

**Key difference**: XSS — code executes from your origin. CSRF — request is sent from a foreign origin.

```txt
Typical follow-ups:

Q: "Why does JWT in the Authorization header protect against CSRF?"
A: Browsers automatically send cookies for a domain, but do NOT
   attach custom headers (Authorization) on cross-domain requests.
   evil.com can't get the JWT from memory/localStorage (same-origin
   policy) → can't set the header.

Q: "Does HttpOnly Cookie protect against XSS?"
A: Partially. HttpOnly makes the cookie unreadable by JS.
   But XSS can still send requests from your origin (fetch,
   XMLHttpRequest) → cookie is attached automatically.
   XSS + session authentication → action hijacking.
   Full protection: HttpOnly + CSP (prevents XSS).

Q: "What is CORS and does it protect the server?"
A: CORS is a browser policy controlling cross-origin fetch/XHR requests.
   Does NOT protect the server: curl/Postman/backend bypass CORS entirely.
   Protects only the browser context of the user.
   The server is protected by authentication and authorization.

Q: "When does the browser send a Preflight OPTIONS request?"
A: Before a "non-simple" request: DELETE/PUT/PATCH method, or
   Authorization/Content-Type: application/json header, or any
   custom header. Preflight asks the server "is this request allowed?"
   before sending the actual request.
```

---

## Group 4: Injection and Input Validation

### What is SQL Injection and how do you defend against it?

SQL Injection: user input is concatenated into SQL → attacker changes the query's logic. Example: `email = "' OR '1'='1' --"` → auth bypass. UNION attack → entire table leaked. With DROP privileges → data deleted.

The only correct defense: **parameterized queries** (data never becomes part of the SQL text). ORM (Prisma, TypeORM) parameterizes automatically for standard methods, but `$queryRawUnsafe` / `query()` with concatenation — are vulnerable.

```txt
Typical follow-ups:

Q: "What is Command Injection?"
A: The equivalent of SQL Injection for shell commands. If user input
   is passed to exec() → attacker inserts ; rm -rf /
   Defense: execFile() instead of exec() (doesn't interpret metacharacters),
   or avoid the shell entirely.

Q: "What is Mass Assignment?"
A: Client sends fields it shouldn't be able to change (e.g. role:'admin')
   and the server blindly applies req.body to the model. Defense: explicit
   whitelist via DTO/Zod schema — accept only declared fields.

Q: "How does Validation differ from Sanitization?"
A: Validation: is the data correct? (reject invalid — 400).
   Sanitization: is the data safe? (transform for a context).
   For SQL — only parameterized queries, not manual escaping.
   For HTML — DOMPurify when HTML rendering is required.
   Both are needed in different contexts.
```

---

## Group 5: Passwords and Secrets

### How do you store passwords correctly and why not encrypt them?

**Don't encrypt**: encryption is reversible. If the key leaks → all passwords exposed. Checking a password at login doesn't require encryption — just compare hashes.

**Don't use SHA-256**: designed for speed. A GPU computes 23 billion SHA-256/sec → brute-forcing a 10M-word dictionary in ~0.01 sec.

**bcrypt**: intentionally slow (cost=12 → ~400ms), automatically embeds salt in the hash, adaptive (as CPU power grows — increase cost).

**Argon2id**: Password Hashing Competition winner. Memory-hard (64MB RAM) → GPU attacks neutralized. Recommended for new projects.

```txt
Typical follow-ups:

Q: "What is a Rainbow Table and how does bcrypt defend against it?"
A: Rainbow Table — a precomputed {password → hash} lookup table.
   bcrypt: unique salt per-password → identical passwords produce
   different hashes → the table is useless (would need a separate
   table per salt value — impractical).

Q: "Where should application secrets be stored in production?"
A: AWS Secrets Manager / Parameter Store, HashiCorp Vault,
   GCP Secret Manager. Benefits: audit log, rotation without redeployment,
   IAM-based access control, automatic RDS password rotation (AWS).
   Development: .env in .gitignore.

Q: "What is Secret Rotation and how do you do it without downtime?"
A: Periodically changing secrets to minimize exposure after compromise.
   Without downtime: (1) issue new_secret, (2) support both keys
   (try new → fallback old for JWT), (3) wait for tokens signed with
   old key to expire, (4) remove old_secret.
   JWKS endpoint: automatic public key publication → rotation without
   redeploying consumers.
```

---

## Group 6: OWASP and Secure Architecture

### Name the top 3 vulnerabilities from OWASP Top 10 and explain them

**A01 Broken Access Control** (#1 since 2021): missing permission check on the resource. IDOR: user changes `/orders/123` to `/orders/124` → sees another user's order. Defense: ownership check at every request level, deny by default.

**A03 Injection**: SQL, Command, NoSQL injection. Defense: parameterized queries, execFile instead of exec, Zod validation.

**A10 SSRF**: server makes an HTTP request to a URL specified by the attacker. On AWS: `http://169.254.169.254/latest/meta-data/` → IAM credentials. Defense: hostname allowlist + DNS rebinding protection (verify resolved IP is not in a private range).

```txt
Typical follow-ups:

Q: "How would you secure a fullstack application (Next.js + NestJS)?"
A: In layers:
   1. HTTPS + HSTS (transport)
   2. Helmet.js security headers (CSP, X-Frame-Options, ...)
   3. Rate Limiting (brute force / DoS)
   4. Access Token (15min JWT) + Refresh Token (HttpOnly Cookie, rotation)
   5. ValidationPipe whitelist=true (Mass Assignment, invalid input)
   6. Parameterized queries / Prisma (SQL Injection)
   7. Zod/class-validator on every endpoint (input validation)
   8. Role + ownership check (Broken Access Control)
   9. Argon2/bcrypt for passwords
   10. AWS Secrets Manager for secrets
   11. SSRF protection for any URL-fetch operations
   12. Audit logging for auth events + 403 patterns

Q: "What is SSRF in the context of AWS and why is it critical?"
A: Instance Metadata Service: GET 169.254.169.254/latest/meta-data/
   iam/security-credentials/role-name → temporary AWS credentials.
   With those credentials → access to S3, RDS, other services via IAM.
   Defense: IMDSv2 (requires request token), URL allowlist,
   block 169.254.169.254 at security group level.

Q: "What is Rate Limiting and how do you implement it with Redis?"
A: Limiting requests per period to protect against brute force/DoS.
   Redis: INCR key → set TTL on first INCR → if count > limit →
   reject with 429. express-rate-limit library supports a Redis store.
   Advanced: rate limit by (userId + endpoint) separately from (IP),
   sliding window instead of fixed window.
```
