# Security Interview Questions (Fullstack / Senior)

---

# 1. What is Authentication?

Verifying the identity of a user.

---

Examples:

```txt
Password

JWT

OAuth

SSO
```

---

# 2. What is Authorization?

Verifying a user's permissions.

---

Determines:

```txt
what the user can do
```

---

# 3. What is the difference between Authentication and Authorization?

Authentication:

```txt
Who are you?
```

---

Authorization:

```txt
What are you allowed to do?
```

---

# 4. What is RBAC?

Role Based Access Control.

---

Access is determined by role.

---

Example:

```txt
Admin

Manager

User
```

---

# 5. What is ABAC?

Attribute Based Access Control.

---

Access is determined by attributes.

---

For example:

```txt
department

owner

country
```

---

# 6. What is JWT?

JSON Web Token.

---

Contains:

```txt
Header

Payload

Signature
```

---

# 7. Is JWT encrypted?

No.

---

JWT is signed,
but not encrypted.

---

# 8. Can a password be stored in JWT?

No.

---

JWT can be read by anyone.

---

# 9. What is an Access Token?

A short-lived access token.

---

Usually:

```txt
5–30 minutes
```

---

# 10. What is a Refresh Token?

A long-lived token
for obtaining a new Access Token.

---

# 11. Where to store the Access Token?

Best option:

```txt
Memory
```

---

Acceptable:

```txt
HttpOnly Cookie
```

---

# 12. Where to store the Refresh Token?

Most often:

```txt
HttpOnly
Secure
SameSite Cookie
```

---

# 13. Why is localStorage dangerous?

During an XSS attack, an attacker can read the token.

---

# 14. What is XSS?

Cross Site Scripting.

---

Executing malicious JavaScript on a website.

---

# 15. What types of XSS exist?

```txt
Stored

Reflected

DOM
```

---

# 16. What is Stored XSS?

A script is saved to the database.

---

The most dangerous variant.

---

# 17. What is DOM XSS?

The vulnerability occurs on the client.

---

Often through:

```js
innerHTML
```

---

# 18. How to protect against XSS?

```txt
Escaping

React JSX

CSP

HttpOnly Cookies
```

---

# 19. What is CSP?

Content Security Policy.

---

Restricts script execution.

---

# 20. What is CSRF?

Cross Site Request Forgery.

---

Tricks the browser into sending a request
on behalf of the user.

---

# 21. Why does JWT in Authorization Header reduce CSRF risk?

The browser does not automatically add:

```txt
Authorization Header
```

---

# 22. How to protect against CSRF?

```txt
CSRF Token

SameSite Cookie

Authorization Header
```

---

# 23. What is SameSite Cookie?

A browser policy
controlling the sending of cookies
between sites.

---

# 24. What is CORS?

Cross-Origin Resource Sharing.

---

A browser policy
for cross-origin requests.

---

# 25. Does CORS protect the server?

No.

---

Only the browser.

---

# 26. What is a Preflight Request?

An OPTIONS request
that the browser sends in advance.

---

# 27. What is SQL Injection?

User influence on a SQL query.

---

# 28. Example of SQL Injection?

```sql
' OR 1=1 --
```

---

# 29. How to protect against SQL Injection?

```txt
Parameterized Queries

ORM

Validation
```

---

# 30. Does Prisma protect against SQL Injection?

In most cases yes.

---

But not:

```txt
$queryRawUnsafe()
```

---

# 31. What is NoSQL Injection?

The SQL Injection equivalent
for NoSQL databases.

---

# 32. What is Command Injection?

User influence
on system commands.

---

# 33. What is Input Validation?

Checking data correctness.

---

# 34. What is Sanitization?

Removing dangerous content.

---

# 35. What is the difference between Validation and Sanitization?

Validation:

```txt
is the data correct?
```

---

Sanitization:

```txt
is the data safe?
```

---

# 36. Why can't you trust Frontend Validation?

Because requests can be sent directly.

---

# 37. What is Mass Assignment?

Passing fields
that the user should not be able to change.

---

# 38. How to protect against Mass Assignment?

```txt
DTO

Whitelist

Field Mapping
```

---

# 39. What is HTTPS?

HTTP over TLS.

---

# 40. What does HTTPS provide?

```txt
encryption

integrity

server authenticity
```

---

# 41. What is MITM?

Man In The Middle.

---

Interception of traffic between parties.

---

# 42. What is Password Hashing?

Storing a hash instead of the password.

---

# 43. What is the difference between Hashing and Encryption?

Hash:

```txt
irreversible
```

---

Encryption:

```txt
reversible
```

---

# 44. Why can't passwords be stored in plain text?

A database leak will expose all passwords.

---

# 45. Why is SHA256 bad for passwords?

Too fast.

---

Easy to brute-force.

---

# 46. What is bcrypt?

A password hashing algorithm.

---

Intentionally slow.

---

# 47. What is Argon2?

A modern password hashing algorithm.

---

Considered best practice.

---

# 48. What is Salt?

A random string
added before hashing.

---

# 49. Why is Salt needed?

Protects against:

```txt
Rainbow Tables
```

---

# 50. What is a Rainbow Table?

A precomputed table:

```txt
password → hash
```

---

# 51. What is a Secret?

Sensitive application data.

---

For example:

```txt
JWT Secret

DB Password

API Keys
```

---

# 52. Where to store secrets?

Production:

```txt
AWS Secrets Manager

Vault

Parameter Store
```

---

# 53. What is Secret Rotation?

Periodic rotation of secrets.

---

# 54. What is OWASP?

Open Worldwide Application Security Project.

---

# 55. What is OWASP Top 10?

A list of the most dangerous web vulnerabilities.

---

# 56. What is Broken Access Control?

Improper access rights checking.

---

# 57. Why is Broken Access Control dangerous?

Allows gaining access
to other people's data.

---

# 58. What is Security Misconfiguration?

System configuration errors.

---

Example:

```txt
public S3 Bucket
```

---

# 59. What is SSRF?

Server Side Request Forgery.

---

Tricks the server into making requests
to internal resources.

---

# 60. Why is SSRF dangerous in AWS?

Can gain access to:

```txt
Metadata Service

Internal APIs
```

---

# 61. What is Rate Limiting?

Limiting the number of requests.

---

# 62. Why is Rate Limiting needed?

Protection against:

```txt
Brute Force

DDoS

Abuse
```

---

# 63. How to implement Rate Limiting?

Often via:

```txt
Redis

INCR

TTL
```

---

# 64. What is the Principle of Least Privilege?

Minimum necessary permissions.

---

# 65. What is Defense in Depth?

Multiple layers of protection.

---

For example:

```txt
HTTPS

JWT

RBAC

Validation

Rate Limiting
```

---

# 66. What are Security Headers?

Additional HTTP protection headers.

---

Examples:

```txt
CSP

HSTS

X-Frame-Options
```

---

# 67. What is HSTS?

HTTP Strict Transport Security.

---

Forces the browser to use HTTPS.

---

# 68. What is X-Frame-Options?

Protection against Clickjacking.

---

# 69. What is Clickjacking?

Tricking users through hidden iframes.

---

# 70. Most Popular Senior Question

How would you secure a modern Next.js + NestJS application?

Answer:

```txt
HTTPS

Access Token + Refresh Token

HttpOnly Cookies

RBAC

DTO Validation

Sanitization

Parameterized Queries

CSP

Rate Limiting

Secrets Manager

Password Hashing (Argon2/Bcrypt)
```

---

# 71. Strongest Senior Answer

What are the 3 most dangerous web vulnerabilities today?

Answer:

```txt
Broken Access Control

XSS

Injection
```

Because these are the ones that most often lead to data breaches and user account takeovers.
