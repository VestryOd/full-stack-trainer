# OWASP Top 10

## What is OWASP

OWASP:

```txt
Open Worldwide
Application Security Project
```

---

The most well-known organization
in web application security.

---

# OWASP Top 10

A list of the most widespread
and dangerous vulnerabilities.

---

Interviewers rarely require
memorizing the entire list.

---

But you need to understand the main items.

---

# A01

Broken Access Control

---

The most dangerous category.

---

# Example

A user requests:

```http
GET /users/123
```

---

Changes it to:

```http
GET /users/124
```

---

And gets someone else's data.

---

# Cause

No access control check.

---

# Protection

```txt
RBAC

ABAC

Ownership Checks
```

---

# A02

Cryptographic Failures

---

Encryption errors.

---

Examples:

```txt
HTTP instead of HTTPS

weak algorithms

passwords without bcrypt
```

---

# A03

Injection

---

Very popular question.

---

Examples:

```txt
SQL Injection

NoSQL Injection

Command Injection
```

---

# Protection

```txt
ORM

Parameterized Queries

Validation
```

---

# A04

Insecure Design

---

Architectural vulnerability.

---

Example:

```txt
no Rate Limiting

no MFA

no account lockout
```

---

# A05

Security Misconfiguration

---

Configuration errors.

---

Examples:

```txt
public S3 Bucket

debug mode

excessive permissions
```

---

# A06

Vulnerable Components

---

Vulnerable dependencies.

---

Example:

```txt
npm package
with a known CVE
```

---

# Protection

```txt
npm audit

Dependabot

regular updates
```

---

# A07

Identification and Authentication Failures

---

Authentication errors.

---

Examples:

```txt
weak passwords

no MFA

insecure JWT
```

---

# A08

Software and Data Integrity Failures

---

Integrity violations.

---

Example:

```txt
loading unsigned packages
```

---

# A09

Security Logging and Monitoring Failures

---

No logging.

---

No monitoring.

---

An attack happened.

---

Nobody noticed.

---

# A10

Server Side Request Forgery

---

SSRF.

---

Very frequently asked.

---

# The Idea

The server is tricked into making a request.

---

Example:

```http
POST /fetch-image
```

---

The user passes:

```txt
http://localhost:5432
```

---

Or:

```txt
http://169.254.169.254
```

---

The server itself goes to that address.

---

# Why This is Dangerous

Can gain access to:

```txt
internal services

AWS metadata

private APIs
```

---

# Protection

```txt
Allow List

URL Validation

Network Restrictions
```

---

# What is Actually Asked in Interviews

Most often:

```txt
Broken Access Control

XSS

CSRF

SQL Injection

JWT Security

Password Storage

SSRF
```

---

# Common Question

Which category is currently the most dangerous?

Answer:

Broken Access Control.

---

# Common Question

What is SSRF?

Answer:

A vulnerability that allows an attacker to trick the server into making requests to internal or protected resources.

---

# Common Question

What is Security Misconfiguration?

Answer:

Errors in infrastructure or application configuration that introduce vulnerabilities.

---

# Interview Answer

OWASP Top 10 is a list of the most critical web application vulnerabilities. The most important ones for a Fullstack developer are Broken Access Control, Injection, Authentication Failures, Security Misconfiguration, and SSRF.
