# JWT, Access Token, and Refresh Token

## The Most Popular Fullstack Interview Topic

Almost guaranteed to be asked.

---

# What is JWT

JSON Web Token.

---

Contains:

```txt
Header

Payload

Signature
```

---

# Header

For example:

```json
{
 "alg":"HS256",
 "typ":"JWT"
}
```

---

# Payload

Contains data.

---

For example:

```json
{
 "userId":"123",
 "role":"admin"
}
```

---

# Very Important

Payload:

```txt
is NOT encrypted
```

---

Only signed.

---

Anyone can read it.

---

# Signature

Allows verifying:

```txt
the token was not tampered with
```

---

# Why JWT is Popular

Stateless.

---

The server does not store sessions.

---

# Access Token

Short-lived token.

---

For example:

```txt
15 minutes
```

---

Used in API requests.

---

# Refresh Token

Long-lived token.

---

For example:

```txt
30 days
```

---

Used to obtain a new Access Token.

---

# Flow

```txt
Login
 ↓
Access Token
Refresh Token
```

---

After 15 minutes:

```txt
Access Token Expired
```

---

Use:

```txt
Refresh Token
```

---

Get a new Access Token.

---

# Where to Store Access Token

Very frequently asked.

---

Most secure:

```txt
Memory
```

---

Acceptable:

```txt
HttpOnly Cookie
```

---

Bad:

```txt
localStorage
```

---

Because of XSS.

---

# Where to Store Refresh Token

Most often:

```txt
HttpOnly Cookie
```

---

# Why HttpOnly

JavaScript cannot read the cookie.

---

This reduces the impact of XSS.

---

# JWT Logout Problem

Very popular Senior question.

---

JWT is stateless.

---

If a token was issued:

```txt
it is valid
until it expires
```

---

Even if the user clicked Logout.

---

# Solutions

```txt
Short Access Token

Refresh Rotation

Blacklist
```

---

# Refresh Rotation

After refresh:

```txt
the old Refresh Token
is invalidated
```

---

# Common Question

Can a password be stored in JWT?

Answer:

No.

---

# Common Question

Is JWT encrypted?

Answer:

No.

---

Signed, but not encrypted.

---

# Common Question

Why is localStorage dangerous?

Answer:

During an XSS attack, an attacker can read the token.

---

# Interview Answer

JWT consists of a Header, Payload, and Signature. The typical scheme uses Access Token + Refresh Token. The Access Token has a short lifetime and is used for API access, while the Refresh Token allows obtaining new Access Tokens without re-login.
