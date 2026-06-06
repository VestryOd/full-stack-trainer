# Security Fundamentals

## The Most Important Topic

Most attacks do not come from sophisticated hackers.

---

But from:

```txt
poor architecture
```

---

# What is Security

Protection of:

```txt
data

users

the system
```

---

# CIA Triad

Very frequently asked.

---

Three core security properties.

---

# Confidentiality

Confidentiality.

---

Access only to those
who are permitted.

---

Examples:

```txt
JWT

Passwords

Encryption

Roles
```

---

# Integrity

Integrity.

---

Data must not be altered
by an unauthorized user.

---

Example:

```txt
digital signature

JWT Signature
```

---

# Availability

Availability.

---

The system must be running.

---

Example threats:

```txt
DDoS

Server Crash

Resource Exhaustion
```

---

# Authentication

Who are you?

---

Example:

```txt
Login + Password

JWT

OAuth
```

---

# Authorization

What are you allowed to do?

---

Example:

```txt
Admin

User

Manager
```

---

# Example

A user logged in.

---

Authentication:

```txt
identity confirmed
```

---

Authorization:

```txt
allowed to delete users
```

---

# Principle of Least Privilege

Very popular question.

---

A user should have:

```txt
minimum necessary permissions
```

---

Bad:

```txt
admin for everyone
```

---

Good:

```txt
only the needed permissions
```

---

# Attack Surface

The attack surface.

---

All entry points:

```txt
API

Forms

Upload

Admin Panel

WebSockets
```

---

The larger the surface:

```txt
the more risks
```

---

# Defense in Depth

Very popular concept.

---

Don't rely on:

```txt
a single protection
```

---

Example:

```txt
JWT
+
Role Check
+
Validation
+
Rate Limiting
```

---

# Security Through Obscurity

An anti-pattern.

---

Bad:

```txt
nobody will find the URL
```

---

Good:

```txt
real authorization
```

---

# HTTPS

Very frequently asked.

---

HTTP:

```txt
traffic is open
```

---

HTTPS:

```txt
TLS encryption
```

---

# What HTTPS Protects

```txt
Cookies

JWT

Passwords

Personal Data
```

---

# Common Question

What is CIA?

Answer:

Confidentiality, Integrity, Availability.

---

# Common Question

Why is HTTPS required?

Answer:

Without HTTPS, any traffic can be intercepted and read.

---

# Interview Answer

The foundation of information security is the CIA Triad: Confidentiality, Integrity, and Availability. Any system must ensure data confidentiality, protection against unauthorized modification, and service availability for users.
