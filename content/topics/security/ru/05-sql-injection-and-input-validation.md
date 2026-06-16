<!-- verified: 2026-06-05, corrections: 0 -->
# SQL Injection и Input Validation

## SQL Injection — механизм атаки

SQL Injection возникает когда пользовательский ввод конкатенируется в SQL-запрос без экранирования. Злоумышленник может изменить логику запроса, обойти аутентификацию, прочитать/удалить данные.

```typescript
// УЯЗВИМО: конкатенация пользовательского ввода в SQL
async function findUser(email: string) {
  const query = `SELECT * FROM users WHERE email = '${email}'`;
  return await db.query(query);
}

// Атака #1: обход аутентификации
// email = "' OR '1'='1' --"
// Запрос становится: SELECT * FROM users WHERE email = '' OR '1'='1' --'
// Условие '1'='1' всегда истинно → возвращает всех пользователей
// -- комментирует остаток запроса

// Атака #2: чтение чужих данных
// email = "' UNION SELECT id, email, password_hash, null FROM users --"
// Добавляет результаты второго SELECT к первому → утечка всей таблицы

// Атака #3: Blind SQL Injection (когда вывод не виден)
// email = "' AND (SELECT SUBSTRING(password_hash,1,1) FROM users WHERE id=1)='a' --"
// По времени ответа или разному поведению → перебор символов по одному

// Атака #4: DROP (при достаточных правах DB user)
// email = "'; DROP TABLE users; --"
```

### Parameterized Queries — единственная правильная защита

```typescript
// БЕЗОПАСНО: параметризованный запрос (pg/node-postgres)
async function findUser(email: string) {
  const result = await pool.query(
    'SELECT * FROM users WHERE email = $1',
    [email]  // параметр передаётся отдельно, никогда не интерполируется в SQL
  );
  return result.rows[0];
}

// БЕЗОПАСНО: Prisma ORM (параметризует автоматически)
const user = await prisma.user.findUnique({
  where: { email }, // безопасно по умолчанию
});

// БЕЗОПАСНО: TypeORM с параметрами
const user = await userRepository.findOne({
  where: { email }, // безопасно
});

// ОПАСНО: raw query с интерполяцией (Prisma)
const users = await prisma.$queryRawUnsafe(
  `SELECT * FROM users WHERE email = '${email}'` // уязвимо!
);

// БЕЗОПАСНО: raw query с параметрами (Prisma)
const users = await prisma.$queryRaw`SELECT * FROM users WHERE email = ${email}`;
// или
const users = await prisma.$queryRaw(
  Prisma.sql`SELECT * FROM users WHERE email = ${email}`
);
```

**Принцип**: данные никогда не становятся частью SQL-текста. БД получает шаблон запроса и данные отдельно — нет возможности "выйти" из строкового контекста.

## Input Validation — почему серверная валидация обязательна

Frontend-валидация — UX, не безопасность. Любой может отправить запрос напрямую через curl/Postman, минуя браузер и JS.

```typescript
// Пример с Zod (Express)
import { z } from 'zod';

const createUserSchema = z.object({
  email: z.string().email().max(255),
  password: z.string().min(8).max(128),
  name: z.string().min(1).max(100).trim(),
  // role отсутствует → клиент не может установить роль
});

app.post('/api/users', async (req, res) => {
  const result = createUserSchema.safeParse(req.body);
  if (!result.success) {
    return res.status(400).json({
      error: 'Validation failed',
      details: result.error.flatten(),
    });
  }
  const { email, password, name } = result.data; // типизированный, безопасный объект
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
  // role: намеренно отсутствует
}

// main.ts
app.useGlobalPipes(new ValidationPipe({
  whitelist: true,      // удаляет поля, не объявленные в DTO
  forbidNonWhitelisted: true, // возвращает ошибку на неизвестные поля
  transform: true,      // преобразует типы (string → number)
}));
```

## Mass Assignment — коварная уязвимость

Происходит когда сервер слепо применяет тело запроса к объекту/модели.

```typescript
// УЯЗВИМО: Mass Assignment
app.patch('/api/users/:id', authenticate, async (req, res) => {
  // Пользователь отправляет: { "name": "Max", "role": "admin" }
  await db.query(
    'UPDATE users SET name = $1, role = $2 WHERE id = $3',
    [req.body.name, req.body.role, req.params.id] // эскалация привилегий!
  );
});

// Тот же паттерн с ORM:
app.patch('/api/users/:id', authenticate, async (req, res) => {
  // НЕБЕЗОПАСНО: req.body содержит роль которую клиент не должен менять
  await prisma.user.update({
    where: { id: req.params.id },
    data: req.body, // принимает всё что прислал клиент
  });
});

// БЕЗОПАСНО: явное whitelist полей
app.patch('/api/users/:id', authenticate, async (req, res) => {
  const schema = z.object({
    name: z.string().min(1).max(100).optional(),
    bio: z.string().max(500).optional(),
    // role намеренно отсутствует
  });
  const data = schema.parse(req.body);

  await prisma.user.update({
    where: { id: req.params.id },
    data, // только whitelisted поля
  });
});
```

## Sanitization vs Validation — разница

```txt
Validation (Валидация):    Данные корректны?
  Проверяет структуру, тип, формат.
  Ошибка → отклоняем запрос (400 Bad Request).
  Пример: email валиден? длина пароля достаточна?

Sanitization (Санитизация): Данные безопасны?
  Преобразует/очищает данные для безопасного использования.
  Не отклоняет — трансформирует.
  Пример: экранирование HTML для отображения, нормализация whitespace
```

```typescript
import DOMPurify from 'isomorphic-dompurify';

// Sanitization для HTML контента (блог, CMS)
function sanitizeHTML(rawHTML: string): string {
  return DOMPurify.sanitize(rawHTML, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'p', 'ul', 'ol', 'li'],
    ALLOWED_ATTR: ['href', 'title'],
  });
}

// Sanitization имён и строковых полей
function sanitizeString(input: string): string {
  return input.trim().replace(/\s+/g, ' ');
}

// Для SQL: sanitization НЕ является защитой
// Используйте только parameterized queries, не экранирование вручную
```

## File Upload Validation — типичные атаки и защита

```typescript
import path from 'path';
import { fileTypeFromBuffer } from 'file-type';

// Атаки на загрузку файлов:
// 1. Path Traversal: filename = "../../etc/passwd"
// 2. Исполняемые файлы: загрузить .php/.js файл на сервер
// 3. Маскировка: переименовать malware.exe в image.jpg
// 4. Бомбы: zip bomb (1KB архив → 1GB после распаковки)
// 5. XXE: вредоносный SVG/XML

// Защита:
const ALLOWED_MIME_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp', 'image/gif']);
const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB

async function validateFileUpload(file: Express.Multer.File): Promise<void> {
  // 1. Проверить размер (до чтения контента)
  if (file.size > MAX_FILE_SIZE) {
    throw new Error('File too large');
  }

  // 2. Проверить magic bytes (реальный тип), не только расширение/content-type
  const fileType = await fileTypeFromBuffer(file.buffer);
  if (!fileType || !ALLOWED_MIME_TYPES.has(fileType.mime)) {
    throw new Error('Invalid file type');
  }

  // 3. Никогда не доверять оригинальному имени файла
  // path.basename защищает от "../" но не достаточно
  const safeFilename = `${crypto.randomUUID()}${path.extname(fileType.ext)}`;

  // 4. Хранить за пределами web root или в объектном хранилище (S3)
  // Никогда не исполнять загруженные файлы как код
}
```

## Типичные ошибки на интервью

- **"ORM полностью защищает от SQL Injection"** — ORM защищает при использовании стандартных методов (`findBy`, `where: {}`). Но `$queryRawUnsafe` (Prisma), `query()` с конкатенацией (TypeORM), `createQueryBuilder` с `getMany()` при небезопасной интерполяции — уязвимы. Всегда проверяй raw queries.

- **"Достаточно валидации на фронтенде"** — клиент полностью под контролем пользователя. Серверная валидация обязательна и является единственной настоящей валидацией.

- **"Sanitization = Validation"** — разные процессы. Validation проверяет корректность (reject or accept). Sanitization преобразует данные для безопасного использования (transform). Оба нужны в разных контекстах.

- **"Экранирование строк достаточно для защиты от SQL Injection"** — ручное экранирование зависит от кодировки, локали, версии БД и легко нарушить. Единственная надёжная защита — parameterized queries/prepared statements.

- **"Проверка MIME-type из Content-Type заголовка достаточна для file upload"** — Content-Type устанавливает клиент, злоумышленник ставит что угодно. Всегда проверяй magic bytes файла (реальное содержимое), не заголовок запроса.
