# SQL Injection and Input Validation

## SQL Injection — how the attack works

SQL Injection occurs when user input is concatenated into a SQL query without escaping. An attacker can change the query's logic, bypass authentication, and read or delete data.

```typescript
// VULNERABLE: concatenating user input into SQL
async function findUser(email: string) {
  const query = `SELECT * FROM users WHERE email = '${email}'`;
  return await db.query(query);
}

// Attack #1: authentication bypass
// email = "' OR '1'='1' --"
// Query becomes: SELECT * FROM users WHERE email = '' OR '1'='1' --'
// '1'='1' is always true → returns all users
// -- comments out the rest of the query

// Attack #2: reading other users' data
// email = "' UNION SELECT id, email, password_hash, null FROM users --"
// Appends a second SELECT → leaks the entire table

// Attack #3: Blind SQL Injection (when output isn't visible)
// email = "' AND (SELECT SUBSTRING(password_hash,1,1) FROM users WHERE id=1)='a' --"
// By timing or differing behavior → enumerate characters one by one

// Attack #4: DROP (if DB user has sufficient privileges)
// email = "'; DROP TABLE users; --"
```

### Parameterized Queries — the only correct defense

```typescript
// SAFE: parameterized query (pg/node-postgres)
async function findUser(email: string) {
  const result = await pool.query(
    'SELECT * FROM users WHERE email = $1',
    [email]  // parameter passed separately, never interpolated into SQL
  );
  return result.rows[0];
}

// SAFE: Prisma ORM (parameterizes automatically)
const user = await prisma.user.findUnique({
  where: { email }, // safe by default
});

// SAFE: TypeORM with parameters
const user = await userRepository.findOne({
  where: { email }, // safe
});

// DANGEROUS: raw query with interpolation (Prisma)
const users = await prisma.$queryRawUnsafe(
  `SELECT * FROM users WHERE email = '${email}'` // vulnerable!
);

// SAFE: raw query with parameters (Prisma)
const users = await prisma.$queryRaw`SELECT * FROM users WHERE email = ${email}`;
// or
const users = await prisma.$queryRaw(
  Prisma.sql`SELECT * FROM users WHERE email = ${email}`
);
```

**Principle**: data never becomes part of the SQL text. The DB receives the query template and data separately — there's no way to "escape" the string context.

## Input Validation — why server-side validation is mandatory

Frontend validation is UX, not security. Anyone can send a request directly via curl/Postman, bypassing the browser and JS entirely.

```typescript
// With Zod (Express)
import { z } from 'zod';

const createUserSchema = z.object({
  email: z.string().email().max(255),
  password: z.string().min(8).max(128),
  name: z.string().min(1).max(100).trim(),
  // role is absent → client can't set the role
});

app.post('/api/users', async (req, res) => {
  const result = createUserSchema.safeParse(req.body);
  if (!result.success) {
    return res.status(400).json({
      error: 'Validation failed',
      details: result.error.flatten(),
    });
  }
  const { email, password, name } = result.data; // typed, safe object
  // ...
});

// NestJS: DTO + ValidationPipe
import { IsEmail, IsString, MinLength, MaxLength } from 'class-validator';

export class CreateUserDto {
  @IsEmail()
  email: string;

  @IsString()
  @MinLength(8)
  @MaxLength(128)
  password: string;

  @IsString()
  @MinLength(1)
  @MaxLength(100)
  name: string;
  // role: intentionally absent
}

// main.ts
app.useGlobalPipes(new ValidationPipe({
  whitelist: true,            // strips fields not declared in the DTO
  forbidNonWhitelisted: true, // returns an error for unknown fields
  transform: true,            // converts types (string → number)
}));
```

## Mass Assignment — an insidious vulnerability

Occurs when the server blindly applies the request body to an object or model.

```typescript
// VULNERABLE: Mass Assignment
app.patch('/api/users/:id', authenticate, async (req, res) => {
  // User sends: { "name": "Max", "role": "admin" }
  await db.query(
    'UPDATE users SET name = $1, role = $2 WHERE id = $3',
    [req.body.name, req.body.role, req.params.id] // privilege escalation!
  );
});

// Same pattern with ORM:
app.patch('/api/users/:id', authenticate, async (req, res) => {
  // INSECURE: req.body includes a role the client shouldn't be able to change
  await prisma.user.update({
    where: { id: req.params.id },
    data: req.body, // accepts anything the client sends
  });
});

// SAFE: explicit field whitelist
app.patch('/api/users/:id', authenticate, async (req, res) => {
  const schema = z.object({
    name: z.string().min(1).max(100).optional(),
    bio: z.string().max(500).optional(),
    // role intentionally absent
  });
  const data = schema.parse(req.body);

  await prisma.user.update({
    where: { id: req.params.id },
    data, // only whitelisted fields
  });
});
```

## Sanitization vs Validation — the difference

```txt
Validation:    Is the data correct?
  Checks structure, type, format.
  On failure → reject the request (400 Bad Request).
  Example: is the email valid? is the password long enough?

Sanitization:  Is the data safe?
  Transforms/cleans data for safe use.
  Doesn't reject — transforms.
  Example: HTML escaping for display, whitespace normalization
```

```typescript
import DOMPurify from 'isomorphic-dompurify';

// Sanitization for HTML content (blog, CMS)
function sanitizeHTML(rawHTML: string): string {
  return DOMPurify.sanitize(rawHTML, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'p', 'ul', 'ol', 'li'],
    ALLOWED_ATTR: ['href', 'title'],
  });
}

// Sanitization of names and string fields
function sanitizeString(input: string): string {
  return input.trim().replace(/\s+/g, ' ');
}

// For SQL: sanitization is NOT protection
// Use only parameterized queries, not manual escaping
```

## File Upload Validation — common attacks and defenses

```typescript
import path from 'path';
import { fileTypeFromBuffer } from 'file-type';

// File upload attacks:
// 1. Path Traversal: filename = "../../etc/passwd"
// 2. Executable files: upload .php/.js file to the server
// 3. Masquerading: rename malware.exe to image.jpg
// 4. Bombs: zip bomb (1KB archive → 1GB after extraction)
// 5. XXE: malicious SVG/XML

// Defenses:
const ALLOWED_MIME_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp', 'image/gif']);
const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB

async function validateFileUpload(file: Express.Multer.File): Promise<void> {
  // 1. Check size (before reading content)
  if (file.size > MAX_FILE_SIZE) {
    throw new Error('File too large');
  }

  // 2. Check magic bytes (real type), not just extension/content-type
  const fileType = await fileTypeFromBuffer(file.buffer);
  if (!fileType || !ALLOWED_MIME_TYPES.has(fileType.mime)) {
    throw new Error('Invalid file type');
  }

  // 3. Never trust the original filename
  // path.basename protects against "../" but isn't sufficient
  const safeFilename = `${crypto.randomUUID()}${path.extname(fileType.ext)}`;

  // 4. Store outside the web root or in object storage (S3)
  // Never execute uploaded files as code
}
```

## Common interview mistakes

- **"ORM fully protects against SQL Injection"** — ORM protects when using standard methods (`findBy`, `where: {}`). But `$queryRawUnsafe` (Prisma), `query()` with concatenation (TypeORM), `createQueryBuilder` with unsafe interpolation — are all vulnerable. Always audit raw queries.

- **"Frontend validation is sufficient"** — the client is entirely under the user's control. Server-side validation is mandatory and is the only real validation.

- **"Sanitization = Validation"** — these are different processes. Validation checks correctness (reject or accept). Sanitization transforms data for safe use (transform). Both are needed in different contexts.

- **"Escaping strings is enough to protect against SQL Injection"** — manual escaping depends on encoding, locale, DB version, and is easy to get wrong. The only reliable protection is parameterized queries / prepared statements.

- **"Checking the Content-Type header is sufficient for file uploads"** — Content-Type is set by the client; an attacker can put anything there. Always check the file's magic bytes (actual content), not the request header.
