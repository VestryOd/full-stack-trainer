# Passwords, Hashing, and Secrets Management

## Hashing vs Encryption — a fundamental distinction

```txt
Hashing:                          Encryption:
  One-way function                  Two-way function
  Cannot be "decrypted"             Can be decrypted with a key
  bcrypt("password") → "..."        AES.encrypt("data", key) ↔ AES.decrypt("...", key)
  Used for passwords                Used for data that needs to be recovered

Why passwords are HASHED, not encrypted:
  If encrypted → the server stores the encryption key
  DB leak + key leak → all passwords recovered
  For login comparison, encryption isn't needed:
  just hash the entered password and compare hashes
```

## SHA-256 and why it's unsuitable for passwords

SHA-256 is a cryptographically secure hash function designed for speed (file hashing, digital signatures). That same speed makes it unsuitable for passwords.

```txt
SHA-256 throughput:
  CPU (2024): ~1 billion hashes/sec
  GPU (RTX 4090): ~23 billion hashes/sec
  Specialized hardware (ASIC): trillions/sec

Brute-forcing a 10-million-word dictionary:
  SHA-256: ~0.01 seconds on GPU
  bcrypt (cost=12): ~3 hours on GPU
  Argon2id (recommended params): days/weeks

Rainbow Tables: a precomputed {password → SHA256-hash} table
  Without salt → instant lookup by hash
  Defense: Salt makes rainbow tables useless
```

## bcrypt — detailed mechanism

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

```txt
How bcrypt defends against attacks:
  1. Slowness: intentionally computationally expensive → brute force is impractical
  2. Salt: unique per-password → identical passwords → different hashes
     → rainbow tables are useless
     → if the DB leaks, can't tell which accounts share a password
  3. Adaptive: as computing power grows — increase the cost factor
```

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

```txt
Tier 1: Development
  .env file (in .gitignore)
  process.env.JWT_SECRET
  Sufficient for local development

Tier 2: Staging/CI
  GitHub Actions Secrets / GitLab CI Variables
  Encrypted by the platform, not visible in logs
  Automatically injected into CI pipelines

Tier 3: Production
  AWS Secrets Manager
  AWS Parameter Store (SecureString)
  HashiCorp Vault
  Azure Key Vault / GCP Secret Manager
  Advantages:
    - Rotation without redeploying the application
    - Audit log (who accessed the secret and when)
    - Least-privilege access via IAM roles
    - Automatic rotation for RDS passwords (AWS)
```

```typescript
// Fetching a secret from AWS Secrets Manager (AWS SDK v3)
import { SecretsManagerClient, GetSecretValueCommand } from '@aws-sdk/client-secrets-manager';

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

```txt
Why rotate:
  1. On key compromise — minimize the window of exposure
  2. Compliance requirements (PCI DSS, SOC2): mandatory rotation
  3. Limit the damage from a compromised key

Zero-downtime rotation pattern:
  1. Issue a new secret (new_secret)
  2. Update the application to support BOTH: old_secret + new_secret
     (JWT verification: try new_secret, fall back to old_secret on failure)
  3. Wait for all tokens signed with old_secret to expire
  4. Remove old_secret from configuration

JWT Key Rotation with JWKS:
  Auth Server publishes /.well-known/jwks.json
  Multiple keys simultaneously (current + previous)
  Services download public keys automatically
  → key rotation without redeploying consumers
```

## Common interview mistakes

- **"SHA-256 is fine for passwords"** — SHA-256 was designed for speed, not passwords. A GPU computes billions of SHA-256 hashes per second. For passwords, use bcrypt (cost≥12) or Argon2id — they are intentionally slow and memory-hard.

- **"You should encrypt passwords with AES"** — encryption is reversible. If the key is stolen → all passwords are exposed. Hashing is irreversible: even if hashes are leaked, the original password can't be recovered without brute force.

- **"The salt must be stored separately in the database"** — bcrypt embeds the salt in the hash output. No separate column is needed. You store only the hash string, which contains algorithm + cost + salt + hash.

- **"It's fine to store secrets in Docker/K8s environment variables in plaintext"** — for production, secrets must be encrypted. Kubernetes Secrets are only base64-encoded (not encrypted) — use Sealed Secrets, AWS Secrets Manager, or Vault.

- **"Argon2 and bcrypt are interchangeable — doesn't matter which you pick"** — not quite. Argon2id is better protected against GPU attacks thanks to memory-hardness. bcrypt is battle-tested and widely supported. For a new project — Argon2id. For an existing bcrypt setup — no need to change.
