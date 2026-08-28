# Security: Interview Questions

Questions are grouped thematically. Each group includes a full senior-level answer + typical follow-up questions.

---

## Group 1: Security Fundamentals

### What is the CIA Triad and why does it matter?

CIA stands for confidentiality, integrity and availability — the three fundamental security properties of any system.

**Confidentiality**: data is accessible only to authorized parties. Threats: traffic interception, also called a MITM (man-in-the-middle) attack, SQL (Structured Query Language) Injection, and token leakage. Controls: HTTPS (Hypertext Transfer Protocol Secure), encryption, and RBAC (role-based access control).

**Integrity**: data cannot be modified without detection. Threats: CSRF (cross-site request forgery), which performs an action on the user's behalf. Also SQL Injection that modifies data, and JWT (JSON Web Token) payload tampering without a valid signature. Controls: HMAC (hash-based message authentication code), digital signatures, and the JWT signature itself.

**Availability**: the system is accessible to authorized users. Threats: DDoS (distributed denial of service), regex DoS, and resource exhaustion. Controls: Rate Limiting and Circuit Breaker.

**Typical follow-ups**

**Q: "What does a DDoS attack violate?"**

A: Availability. DDoS exhausts server resources, so legitimate users can't access the service.

**Q: "What does intercepting a JWT violate?"**

A: Confidentiality. The attacker gains access to data that was meant only for the authorized user.

**Q: "What does CSRF violate?"**

A: Integrity. An action is performed on behalf of the user without their knowledge, so data is modified without authorization.

### What is Defense in Depth?

A principle of layered protection: if one layer is breached, the next should stop the attack. You can't rely on a single defense.

Example for an API endpoint, one layer per step:

1. HTTPS for encryption.
2. Rate Limiting against brute force.
3. JWT Validation for authentication.
4. Role Check for authorization.
5. Zod or ValidationPipe for validation.
6. Parameterized Query against injection.
7. Output Encoding against XSS (cross-site scripting).
8. Security Headers against clickjacking.

**Typical follow-ups**

**Q: "What is Security Through Obscurity? Does it work?"**

A: Attempting to secure a system by hiding information, such as a secret URL or an undocumented API. It is **not** a real defense: attackers find endpoints via brute force, scanning, and source code.

Real protection is authorization on the endpoint, regardless of how "secret" it is. Kerckhoffs's principle: a system is secure when the secret is only the key, not the algorithm.

---

## Group 2: JWT, Authentication, and Tokens

### Describe the structure of a JWT and what happens if the payload is modified

JWT — three base64url-encoded parts: `header.payload.signature`.

- **Header**: algorithm (`HS256`) and type
- **Payload**: claims (sub, role, exp, iat, jti) — **not** encrypted, anyone can read it
- **Signature**: HMAC(header + payload, secret) — guarantees integrity

If the payload is modified (e.g., `role: "user" → "admin"`): the signature becomes invalid on verification. The server must reject the token. Exception: the `alg:none` attack — if the library accepts algorithm=none, the signature is not checked. Defense: `jwt.verify(token, secret, { algorithms: ['HS256'] })` — explicit algorithm specification.

**Typical follow-ups**

**Q: "Can you put a password in a JWT?"**

A: No. The payload is only signed, not encrypted. Anyone can base64-decode the payload without a key and see the contents.

**Q: "How does HS256 differ from RS256?"**

A: HS256 is symmetric: one secret for signing and verification. RS256 is asymmetric: the private key signs, the public key verifies. In microservices RS256 is preferable, because each service verifies via the public key without knowing the private key.

### Explain the Access Token + Refresh Token scheme and the logout problem

**Why two tokens**: one long-lived JWT is catastrophic if stolen, because it stays valid for 30 days. Two tokens split that risk: Access (15 min, stateless) plus Refresh (30 days, stored in the database).

**Flow**: Login → AccessToken (in JSON response) + RefreshToken (HttpOnly Cookie). After 15 min: POST /auth/refresh → new AccessToken. Logout: delete RefreshToken from the database + clearCookie.

**JWT Logout Problem**: an Access Token is stateless, so you can't "revoke" it before its TTL (time to live) expires. Three solutions:

1. A short TTL, 15 min.
2. A Redis blacklist by `jti`.
3. Refresh Token Rotation: each refresh issues a new refresh token and invalidates the old one.

**Typical follow-ups**

**Q: "Where is it safe to store an Access Token?"**

A: Memory (a JS variable) is protected from XSS but lost on page refresh. An HttpOnly Cookie is protected from XSS but carries CSRF risk, so it needs `sameSite=strict`. localStorage is **insecure**: XSS can steal it.

**Q: "How do you detect Refresh Token theft?"**

A: Refresh Token Rotation. On each refresh a new refresh token is issued and the old one is deleted from the database. If an attacker uses the stolen token, that is a reuse attempt on an already-used token. It raises an alert and revokes **all** refresh tokens for that user.

**Q: "What is OAuth 2.0 and how is it different from authentication?"**

A: OAuth 2.0 is a delegated **authorization** protocol, meaning access to resources. For authentication you need OpenID Connect, a layer on top of OAuth 2.0 that adds an `id_token` with identity data. "Sign in with Google" is OpenID Connect, not plain OAuth 2.0.

---

## Group 3: XSS, CSRF, and CORS

Three browser-side topics that are easy to confuse: XSS, CSRF, and CORS (cross-origin resource sharing).

### Explain XSS, CSRF, and how they differ

**XSS** (Cross-Site Scripting): attacker injects JavaScript into pages; victim's browser executes it in the context of your site. Three types: Stored (in the database), Reflected (in the URL), and DOM-based, living in the client's Document Object Model. Result: steal tokens from localStorage/cookies, keylogger, actions on user's behalf.

**CSRF** (Cross-Site Request Forgery): victim's browser (already authenticated) sends a request to your site from evil.com. Browser automatically attaches your domain's cookies. Server can't distinguish it from a legitimate request.

**Key difference**: XSS — code executes from your origin. CSRF — request is sent from a foreign origin.

**Typical follow-ups**

**Q: "Why does JWT in the Authorization header protect against CSRF?"**

A: Browsers automatically send cookies for a domain, but they do **not** attach custom headers such as Authorization on cross-domain requests. A page on evil.com can't get the JWT from memory or localStorage because of the same-origin policy, so it can't set the header.

**Q: "Does HttpOnly Cookie protect against XSS?"**

A: Partially. HttpOnly makes the cookie unreadable by JS. But XSS can still send requests from your origin with fetch or XMLHttpRequest, and the cookie is attached automatically. XSS plus session authentication gives action hijacking. Full protection is HttpOnly plus CSP (Content Security Policy), which limits what an injected script can do.

**Q: "What is CORS and does it protect the server?"**

A: CORS is a browser policy controlling cross-origin fetch and XHR (XMLHttpRequest) requests. It does **not** protect the server: curl, Postman and any backend bypass CORS entirely. It protects only the browser context of the user. The server is protected by authentication and authorization.

**Q: "When does the browser send a Preflight OPTIONS request?"**

A: Before a "non-simple" request: a DELETE, PUT or PATCH method, an Authorization or `Content-Type: application/json` header, or any custom header. Preflight asks the server "is this request allowed?" before sending the actual request.

---

## Group 4: Injection and Input Validation

### What is SQL Injection and how do you defend against it?

SQL Injection: user input is concatenated into SQL → attacker changes the query's logic. Example: `email = "' OR '1'='1' --"` → auth bypass. UNION attack → entire table leaked. With DROP privileges → data deleted.

The only correct defense: **parameterized queries**, where data never becomes part of the SQL text. An ORM (object-relational mapper) such as Prisma or TypeORM parameterizes automatically for standard methods, but `$queryRawUnsafe` and `query()` with concatenation are vulnerable.

**Typical follow-ups**

**Q: "What is Command Injection?"**

A: The equivalent of SQL Injection for shell commands. If user input is passed to `exec()`, the attacker inserts `; rm -rf /`. Defense: `execFile()` instead of `exec()`, because it doesn't interpret metacharacters, or avoid the shell entirely.

**Q: "What is Mass Assignment?"**

A: The client sends fields it shouldn't be able to change, for example `role:'admin'`, and the server blindly applies `req.body` to the model. Defense: an explicit whitelist via a DTO (data transfer object) or Zod schema, accepting only declared fields.

**Q: "How does Validation differ from Sanitization?"**

A: Validation asks whether the data is correct, and rejects invalid input with 400. Sanitization asks whether the data is safe, and transforms it for a context. For SQL use only parameterized queries, not manual escaping. For HTML use DOMPurify when HTML rendering is required. Both are needed in different contexts.

---

## Group 5: Passwords and Secrets

### How do you store passwords correctly and why not encrypt them?

**Don't encrypt**: encryption is reversible. If the key leaks → all passwords exposed. Checking a password at login doesn't require encryption — just compare hashes.

**Don't use SHA-256**: the Secure Hash Algorithm family is designed for speed. A GPU (graphics processing unit) computes 23 billion SHA-256/sec, so brute-forcing a 10M-word dictionary takes ~0.01 sec.

**bcrypt**: intentionally slow (cost=12 → ~400ms), automatically embeds salt in the hash, adaptive (as CPU power grows, you increase the cost). CPU here is the central processing unit.

**Argon2id**: Password Hashing Competition winner. Memory-hard, needing 64MB of RAM (random access memory), so GPU attacks are neutralized. Recommended for new projects.

**Typical follow-ups**

**Q: "What is a Rainbow Table and how does bcrypt defend against it?"**

A: A Rainbow Table is a precomputed `{password → hash}` lookup table. Because bcrypt gives every password a unique salt, identical passwords produce different hashes and the table is useless. An attacker would need a separate table per salt value, which is impractical.

**Q: "Where should application secrets be stored in production?"**

A: AWS (Amazon Web Services) Secrets Manager or Parameter Store, HashiCorp Vault, or GCP (Google Cloud Platform) Secret Manager. Benefits: audit log, rotation without redeployment, access control based on IAM (identity and access management), and automatic RDS (Relational Database Service) password rotation on AWS. Development: `.env` in `.gitignore`.

**Q: "What is Secret Rotation and how do you do it without downtime?"**

A: Periodically changing secrets to minimize exposure after compromise. Without downtime it takes four steps:

1. Issue `new_secret`.
2. Support both keys: try the new one, fall back to the old one for JWT.
3. Wait for tokens signed with the old key to expire.
4. Remove `old_secret`.

A JWKS (JSON Web Key Set) endpoint publishes public keys automatically, so rotation needs no redeploy of consumers.

---

## Group 6: OWASP and Secure Architecture

OWASP (Open Worldwide Application Security Project) publishes the Top 10 list of the most critical web application vulnerabilities.

### Name the top 3 vulnerabilities from OWASP Top 10 and explain them

**A01 — Broken Access Control** (#1 since 2021): missing permission check on the resource. IDOR (insecure direct object reference): the user changes `/orders/123` to `/orders/124` and sees another user's order. Defense: ownership check at every request level, deny by default.

**A03 — Injection**: SQL, Command, and NoSQL (non-relational database) injection. Defense: parameterized queries, execFile instead of exec, Zod validation.

**A10 — Server-Side Request Forgery (SSRF)**: the server makes an HTTP request to a URL specified by the attacker. On AWS: `http://169.254.169.254/latest/meta-data/` → IAM credentials. Defense: a hostname allowlist plus DNS (domain name system) rebinding protection. That check verifies the resolved IP (internet protocol) address is not in a private range.

**Typical follow-ups**

**Q: "How would you secure a fullstack application (Next.js + NestJS)?"**

A: In layers.

1. HTTPS + HSTS (HTTP Strict Transport Security) for transport.
2. Helmet.js security headers: CSP, X-Frame-Options and the rest.
3. Rate Limiting against brute force and DoS.
4. Access Token (15min JWT) + Refresh Token (HttpOnly Cookie, rotation).
5. ValidationPipe with `whitelist=true` against Mass Assignment and invalid input.
6. Parameterized queries or Prisma against SQL Injection.
7. Zod or class-validator on every endpoint for input validation.
8. Role + ownership check against Broken Access Control.
9. Argon2 or bcrypt for passwords.
10. AWS Secrets Manager for secrets.
11. SSRF protection for any URL-fetch operations.
12. Audit logging for auth events + 403 patterns.

**Q: "What is SSRF in the context of AWS and why is it critical?"**

A: The Instance Metadata Service answers `GET 169.254.169.254/latest/meta-data/iam/security-credentials/role-name` with temporary AWS credentials. With those credentials an attacker reaches S3 (Amazon Simple Storage Service), RDS and other services via IAM. Defense: IMDSv2, which requires a request token, a URL allowlist, and blocking `169.254.169.254` at security group level.

**Q: "What is Rate Limiting and how do you implement it with Redis?"**

A: Limiting requests per period to protect against brute force and DoS. Redis: `INCR key`, set a TTL on the first `INCR`, and if the count exceeds the limit reject with 429. The `express-rate-limit` library supports a Redis store. Advanced: rate limit by (userId + endpoint) separately from (IP), and a sliding window instead of a fixed window.
