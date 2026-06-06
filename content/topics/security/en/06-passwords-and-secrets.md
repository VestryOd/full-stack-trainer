# Passwords, Hashing, and Secrets

## The Most Common Junior Developer Mistake

Very frequently asked:

```txt
How to store a password?
```

---

Wrong answer:

```txt
Encrypt the password
```

---

Right answer:

```txt
Hash the password
```

---

# Encryption vs Hashing

Very popular question.

---

Encryption:

```txt
reversible
```

---

Can be decrypted back.

---

Example:

```txt
AES
RSA
```

---

# Hashing

Irreversible.

---

Example:

```txt
SHA256
bcrypt
argon2
```

---

A password cannot be recovered from its hash.

---

# Why You Can't Store a Password Encrypted

Very frequently asked.

---

If the server knows the key:

```txt
it can decrypt the password
```

---

If the key is stolen:

```txt
all passwords are exposed
```

---

That's why passwords:

```txt
are not encrypted

but hashed
```

---

# How Hashing Works

```txt
password123
 ↓
hash function
 ↓
8f5e....
```

---

At login:

```txt
password123
 ↓
hash
 ↓
compare
```

---

# SHA256

Very popular question.

---

Technically:

```txt
possible
```

---

In practice:

```txt
not recommended
```

---

# Why SHA256 is Bad for Passwords

It is:

```txt
too fast
```

---

Modern GPUs can compute:

```txt
billions of hashes
```

---

Per second.

---

# Brute Force

Password guessing.

---

If the algorithm is fast:

```txt
guessing becomes feasible
```

---

# bcrypt

Specifically designed for passwords.

---

Very frequently asked.

---

bcrypt is intentionally:

```txt
slow
```

---

For example:

```txt
100ms
```

---

Per password.

---

Imperceptible for the user.

---

A catastrophe for an attacker.

---

# Salt

The most popular question.

---

What is Salt?

---

A random string.

---

Example:

```txt
password123
+
randomSalt
```

---

Before hashing.

---

# Why Salt is Needed

Imagine:

```txt
100 users
```

---

With the password:

```txt
123456
```

---

Without Salt:

```txt
all hashes are the same
```

---

With Salt:

```txt
all hashes are different
```

---

# Rainbow Table

Very frequently asked.

---

A precomputed table:

```txt
password -> hash
```

---

Salt makes it useless.

---

# bcrypt Cost Factor

Very popular Senior question.

---

Parameter:

```txt
cost
```

---

Determines:

```txt
how computationally expensive the hash is
```

---

For example:

```txt
10

12

14
```

---

The higher it is:

```txt
the slower
```

---

# Argon2

The modern leader.

---

Very frequently asked.

---

Winner of:

```txt
Password Hashing Competition
```

---

Uses:

```txt
CPU

Memory
```

---

Simultaneously.

---

Considered better than bcrypt.

---

# What to Use Today

Good answer:

```txt
Argon2

or

bcrypt
```

---

# Secrets

The next important topic.

---

Secrets:

```txt
JWT Secret

DB Password

API Keys

OAuth Secrets
```

---

# The Worst Practice

```ts
const password =
 "123456";
```

---

In code.

---

# Better

```env
DB_PASSWORD=...
```

---

But even this is not enough
for production.

---

# Production

Very frequently asked.

---

Use:

```txt
AWS Secrets Manager

AWS Parameter Store

Hashicorp Vault
```

---

# Why

Secrets can be:

```txt
rotated

logged

access-restricted
```

---

# Secret Rotation

Very popular question.

---

Regular rotation of:

```txt
passwords

keys

tokens
```

---

Without stopping the system.

---

# Common Question

Why is bcrypt better than SHA256?

Answer:

bcrypt is intentionally slow and uses salt, making brute-force attacks significantly harder.

---

# Common Question

Can a bcrypt hash be decrypted?

Answer:

No.

A password is verified by re-computing the hash and comparing the result.

---

# Common Question

What is Salt?

Answer:

A random value added to the password before hashing to protect against rainbow table attacks.

---

# Common Question

What to use for storing secrets in AWS?

Answer:

Secrets Manager.

---

# Interview Answer

Passwords must be stored as a hash, not encrypted. Today it is recommended to use bcrypt or Argon2 together with a unique salt. Application secrets must not be stored in code, and in production they are typically placed in specialized vaults like AWS Secrets Manager.
