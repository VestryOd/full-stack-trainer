# Passwords, Hashing, and Secrets Management

## Hashing vs Encryption — a fundamental distinction

Hashing is a one-way function and encryption is a two-way function. That single difference decides which of the two a password gets.

| | Hashing | Encryption |
|---|---|---|
| Direction | One-way function | Two-way function |
| Reversal | Cannot be "decrypted" | Can be decrypted with a key |
| Call shape | `bcrypt("password") → "..."` | `AES.encrypt("data", key) ↔ AES.decrypt("...", key)` |
| Used for | Passwords | Data that needs to be recovered |

**Why passwords are hashed and not encrypted.** Encryption would force the server to store the encryption key. A database leak together with a key leak recovers all passwords at once. Comparing a password at login does not need encryption anyway: just hash the entered password and compare hashes.

## SHA-256 and why it's unsuitable for passwords

SHA-256 is a cryptographically secure hash function from the Secure Hash Algorithm family, designed for speed (file hashing, digital signatures). That same speed makes it unsuitable for passwords.

SHA-256 throughput depends only on the hardware that runs it:

- CPU (central processing unit), 2024: ~1 billion hashes/sec.
- GPU (graphics processing unit), an `RTX 4090`: ~23 billion hashes/sec.
- Specialized hardware, an ASIC (application-specific integrated circuit): trillions/sec.

Brute-forcing a 10-million-word dictionary shows what that speed buys an attacker:

- SHA-256: ~0.01 seconds on GPU.
- bcrypt (cost=12): ~3 hours on GPU.
- Argon2id (recommended params): days/weeks.

Rainbow Tables are precomputed `{password → SHA256-hash}` tables. Without salt they turn cracking into an instant lookup by hash. Salt is the defense: it makes rainbow tables useless.

## bcrypt — detailed mechanism

bcrypt does the salting for you. Hashing generates a random salt and embeds it in the returned string, and `bcrypt.compare` reads that salt back out.

```typescript
import bcrypt from 'bcrypt';

// Hashing at registration
async function hashPassword(password: string): Promise<string> {
  const COST_FACTOR = 12; // rounds = 2^12 = 4096 iterations
  // bcrypt automatically: generates a random salt and embeds it in the hash
  return await bcrypt.hash(password, COST_FACTOR);
  // Result: "$2b$12$XXXXXXXXXXXXXXXXXXXXXXXX.YYYYYYYYYYYYYYYYYYYYYYYYYYYY"
  //          ^^   ^^ ^^^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  //      algorithm cost    salt (22 chars)         hash (31 chars)
  // Salt is stored INSIDE the hash → no separate column needed
}

// Verification at login
async function verifyPassword(password: string, hash: string): Promise<boolean> {
  return await bcrypt.compare(password, hash);
  // bcrypt: extracts salt from hash, computes hash(password + salt), compares
}

// Choosing cost factor:
// cost=10: ~100ms  — minimum acceptable
// cost=12: ~400ms  — recommended for most apps (2024)
// cost=14: ~1.6s   — for high security where the server can tolerate the delay
// Rule: pick the highest cost where login takes ~100-500ms
```

**How bcrypt defends against attacks:**

1. **Slowness.** It is intentionally expensive to compute, so brute force is impractical.
2. **Salt.** The salt is unique per password, so identical passwords give different hashes. Rainbow tables are useless against it, and if the database leaks nobody can tell which accounts share a password.
3. **Adaptive cost.** As computing power grows, you increase the cost factor.

## Argon2 — the modern standard

Argon2 is the winner of the Password Hashing Competition 2015. Three variants: Argon2d, Argon2i, Argon2id (recommended).

```typescript
import argon2 from 'argon2';

// Hashing
async function hashPasswordArgon2(password: string): Promise<string> {
  return await argon2.hash(password, {
    type: argon2.argon2id,   // hybrid: protection against GPU and timing attacks
    memoryCost: 65536,        // 64MB RAM — makes GPU attacks expensive
    timeCost: 3,              // 3 iterations
    parallelism: 4,           // 4 threads
  });
}

// Verification
async function verifyPasswordArgon2(password: string, hash: string): Promise<boolean> {
  return await argon2.verify(hash, password);
}

// Why Argon2 beats bcrypt:
// Argon2 uses MEMORY in its computation
// GPU attack: GPUs have many cores but little RAM per core
// memoryCost = 64MB means a GPU core can't parallelize many hash computations
// → GPU attacks are effectively neutralized
```

## Application secrets management

### Anti-patterns

Four ways to hand a secret to an attacker, all of them common in real repositories.

```typescript
// BAD #1: hardcoded secrets in code
const JWT_SECRET = 'my-super-secret-key-123';
const DB_URL = 'postgres://admin:password@prod.db.com/mydb';

// BAD #2: .env file in the git repository
// .gitignore MUST include .env, .env.local, .env.production

// BAD #3: logging secrets
console.log('Config:', { dbUrl, jwtSecret }); // SECRET IN LOGS!

// BAD #4: secrets in Docker environment variables without encryption
// docker run -e DB_PASSWORD=secret ... # visible in process list
```

### Correct approach: tiers of secrets storage

Where a secret may live depends on the environment, and there are three tiers.

**Tier 1: Development.**

- A `.env` file, listed in `.gitignore`.
- Read in code as `process.env.JWT_SECRET`.
- Sufficient for local development.

**Tier 2: Staging and continuous integration (CI).**

- GitHub Actions Secrets or GitLab CI Variables.
- Encrypted by the platform, not visible in logs.
- Automatically injected into CI pipelines.

**Tier 3: Production.** The secret lives in a managed store:

- Secrets Manager in Amazon Web Services (AWS).
- AWS Parameter Store, `SecureString` type.
- HashiCorp Vault.
- Azure Key Vault, or Secret Manager in Google Cloud Platform (GCP).

Advantages of a managed store:

- Rotation without redeploying the application.
- Audit log: who accessed the secret and when.
- Least-privilege access via identity and access management (IAM) roles.
- Automatic rotation for Relational Database Service (RDS) passwords on AWS.

```typescript
// Fetching a secret from AWS Secrets Manager (AWS SDK v3)
import {
  SecretsManagerClient,
  GetSecretValueCommand,
} from '@aws-sdk/client-secrets-manager';

const client = new SecretsManagerClient({ region: 'eu-west-1' });

async function getSecret(secretName: string): Promise<Record<string, string>> {
  const command = new GetSecretValueCommand({ SecretId: secretName });
  const response = await client.send(command);
  return JSON.parse(response.SecretString!);
}

// At app startup (not on every request):
async function loadSecrets(): Promise<AppSecrets> {
  const [dbSecrets, authSecrets] = await Promise.all([
    getSecret('myapp/production/database'),
    getSecret('myapp/production/auth'),
  ]);
  return {
    dbUrl: `postgres://${dbSecrets.username}:${dbSecrets.password}@${dbSecrets.host}/mydb`,
    jwtSecret: authSecrets.jwtSecret,
  };
}
```

### Secret Rotation — rotation without downtime

Three reasons to rotate a secret:

1. A key was compromised, and rotation minimizes the window of exposure.
2. Compliance requires it. The Payment Card Industry Data Security Standard (PCI DSS) and SOC2 (System and Organization Controls) both make rotation mandatory.
3. Rotation limits the damage from a compromised key.

The zero-downtime rotation pattern takes four steps:

1. Issue a new secret, `new_secret`.
2. Update the application to support **both** `old_secret` and `new_secret`. For JWT (JSON Web Token) verification that means trying `new_secret` first and falling back to `old_secret` on failure.
3. Wait for all tokens signed with `old_secret` to expire.
4. Remove `old_secret` from configuration.

Signing keys rotate differently, through JWKS (JSON Web Key Set). The Auth Server publishes `/.well-known/jwks.json` and holds multiple keys at once, the current one and the previous one. Services download the public keys automatically, so keys rotate without redeploying consumers.

## Common interview mistakes

- **"SHA-256 is fine for passwords"** — SHA-256 was designed for speed, not passwords. A GPU computes billions of SHA-256 hashes per second. For passwords, use bcrypt (cost≥12) or Argon2id — they are intentionally slow and memory-hard.

- **"You should encrypt passwords with AES"** — the Advanced Encryption Standard is encryption, and encryption is reversible. If the key is stolen → all passwords are exposed. Hashing is irreversible: even if hashes are leaked, the original password can't be recovered without brute force.

- **"The salt must be stored separately in the database"** — bcrypt embeds the salt in the hash output. No separate column is needed. You store only the hash string, which contains algorithm + cost + salt + hash.

- **"It's fine to store secrets in Docker or Kubernetes environment variables in plaintext"** — for production, secrets must be encrypted. Kubernetes Secrets are only base64-encoded (not encrypted) — use Sealed Secrets, AWS Secrets Manager, or Vault.

- **"Argon2 and bcrypt are interchangeable — doesn't matter which you pick"** — not quite. Argon2id is better protected against GPU attacks thanks to memory-hardness. bcrypt is battle-tested and widely supported. For a new project — Argon2id. For an existing bcrypt setup — no need to change.
