<!-- verified: 2026-06-05, corrections: 0 -->
# OWASP Top 10 (2021)

## Что такое OWASP Top 10

OWASP (Open Worldwide Application Security Project) — некоммерческая организация, публикующая топ-10 наиболее критичных уязвимостей веб-приложений. Обновляется примерно каждые 3-4 года. На интервью не требуют наизусть всю десятку, но необходимо глубокое понимание первых 5-7 и умение привести конкретные примеры и защиты.

## A01: Broken Access Control

**#1 с 2021 года.** 94% приложений в исследовании имели эту уязвимость.

```typescript
// IDOR (Insecure Direct Object Reference) — типичный сценарий
// GET /api/orders/12345 → пользователь меняет на /api/orders/12346
// Если нет ownership check → доступ к чужому заказу

// Другие примеры:
// - Пользователь обращается к admin endpoint без проверки роли
// - URL /admin работает без аутентификации
// - Повышение привилегий через редактирование JWT payload (alg:none атака)
// - Горизонтальное движение: user A видит данные user B

// Защита:
app.get('/api/orders/:id', authenticate, async (req, res) => {
  // ownership встроен в сам запрос: чужой заказ просто не найдётся
  const order = await prisma.order.findFirst({
    where: req.user.role === 'admin'
      ? { id: req.params.id }
      : { id: req.params.id, userId: req.user.id },
  });
  // 404, а не 403: ответ 403 подтвердил бы, что заказ существует, но чужой,
  // и помог бы атакующему собрать список валидных id
  if (!order) return res.status(404).json({ error: 'Not found' });
  res.json(order);
});

// Принципы защиты:
// 1. Deny by default — запрещать всё, явно разрешать
// 2. Проверять ownership на уровне запроса к БД (не в памяти)
// 3. Логировать отказы доступа и алертить на аномалии
```

## A02: Cryptographic Failures

Ранее называлась "Sensitive Data Exposure". Охватывает неправильное использование или отсутствие криптографии.

Типичные сценарии:

- HTTP вместо HTTPS (Hypertext Transfer Protocol Secure), и данные идут в открытом виде.
- Пароли в открытом виде или под устаревшими MD5 (Message Digest 5) и SHA-1 (Secure Hash Algorithm 1).
- JWT (JSON Web Token) с `algorithm=none`, то есть подпись не проверяется.
- Персональные данные, PII (personally identifiable information), в логах: email, IP (адрес узла в сети), номер карты.
- Слабые ключи шифрования, меньше 128 бит.
- Использование режима ECB (electronic codebook): он детерминированный, поэтому паттерны видны.
- Секреты в git-истории.

Защита:

- HTTPS везде, с заголовком HSTS (HTTP Strict Transport Security).
- bcrypt или Argon2 для паролей.
- AES-256-GCM для данных at-rest, то есть Advanced Encryption Standard в режиме Galois/Counter Mode.
- Явная проверка алгоритма JWT: `jwt.verify(token, secret, { algorithms: ['HS256'] })`.
- Классификация данных: знать, какие данные чувствительные, и защищать их соответственно.

## A03: Injection

Injection — это семейство уязвимостей, а не одна ошибка. Недоверенный ввод доходит до интерпретатора, который читает его как инструкции:

- SQL (Structured Query Language) injection — против реляционной базы данных.
- NoSQL (нереляционное хранилище) injection — против баз вроде MongoDB.
- LDAP (Lightweight Directory Access Protocol) injection — против сервера каталогов.
- OS (operating system) Command injection — ввод доходит до командной оболочки.
- SSTI (server-side template injection) — ввод доходит до шаблонизатора.

```typescript
// SQL Injection (подробнее: [SQL Injection and Input Validation])
// Command Injection — не менее опасно:

// УЯЗВИМО: передача пользовательского ввода в shell
import { exec } from 'child_process';
app.post('/api/convert', (req, res) => {
  exec(`convert ${req.body.filename} output.pdf`, (err, stdout) => {
    // filename = "image.jpg; rm -rf /; echo" → катастрофа
  });
});

// БЕЗОПАСНО: избегать shell, использовать массивы аргументов
import { execFile } from 'child_process';
app.post('/api/convert', (req, res) => {
  const safeFilename = path.basename(req.body.filename); // strip path traversal
  execFile('convert', [safeFilename, 'output.pdf'], (err, stdout) => { /* ... */ });
  // execFile не интерпретирует shell metacharacters
});
```

## A04: Insecure Design

Архитектурные уязвимости — те, что нельзя исправить только патчем кода.

Примеры:

- Нет rate limiting на login endpoint, и перебор паролей становится возможен.
- Password reset без MFA (multi-factor authentication) и без истечения токена, отсюда account takeover.
- Нет lockout после N попыток, отсюда enumeration-атаки.
- Критические операции без второго фактора подтверждения.
- Хранение всех данных в одной базе данных без изоляции.
- Публичный S3 (Amazon Simple Storage Service) bucket для приватных документов.

Моделирование угроз идёт на стадии дизайна, а чеклист для него — STRIDE — по букве на класс угрозы:

- **S** — Spoofing identity.
- **T** — Tampering with data.
- **R** — Repudiation.
- **I** — Information disclosure.
- **D** — Denial of service.
- **E** — Elevation of privilege.

Каждую фичу нужно пропускать через STRIDE до написания кода.

## A05: Security Misconfiguration

Неправильная конфигурация — это дефолты, которые никто не поменял. В коде ниже четыре таких дефолта и починка к каждому, начиная с CORS (cross-origin resource sharing), где разрешены любые origin.

```typescript
// Примеры неправильной конфигурации:

// ПЛОХО: все CORS origins разрешены
app.use(cors({ origin: '*' })); // API с авторизацией + wildcard = риск

// ПЛОХО: stack trace в production response
app.use((err, req, res, next) => {
  res.status(500).json({ error: err.message, stack: err.stack }); // утечка инфо
});

// ХОРОШО:
app.use((err, req, res, next) => {
  logger.error({ err, requestId: req.id }); // логируем всё
  // клиенту — минимум
  res.status(500).json({ error: 'Internal server error', requestId: req.id });
});

// ПЛОХО: Debug режим в production
// X-Powered-By: Express → даёт info об инфраструктуре

// ХОРОШО:
app.disable('x-powered-by');
app.use(helmet()); // добавляет security headers

// ПЛОХО: дефолтные credentials не изменены
// PostgreSQL: postgres:postgres, MongoDB: без пароля
// S3 Bucket: public-read для внутренних файлов
```

## A06: Vulnerable and Outdated Components

Уязвимые компоненты находят сканеры, а не чтение кода. Команды ниже проверяют зависимости и Docker-образы на известные CVE — публичный каталог common vulnerabilities and exposures.

```bash
# Зависимости с известными CVE

# Проверка (Node.js):
npm audit
npm audit --audit-level=high  # только high/critical

# Автоматизация:
# GitHub Dependabot — автоматические PR на обновление
# Snyk — более детальный анализ с remediation

# Docker images:
docker scout cves myapp:latest
trivy image myapp:latest  # сканирование на CVE

# Принцип: dependencies нужно обновлять регулярно
# lock файл (package-lock.json) фиксирует версии → reproducible builds
# НО lock файл не защищает если сам пакет скомпрометирован (supply chain)
```

## A07: Identification and Authentication Failures

Аутентификация ломается небольшим набором повторяющихся способов. В коде ниже их пять: непроверенный алгоритм JWT, отсутствие rate limiting на логине, слабые пароли, отсутствие MFA и предсказуемые токены.

```typescript
// Типичные уязвимости:

// 1. JWT с algorithm=none (критическая уязвимость ранних библиотек)
// Attacker: изменяет header на {"alg":"none"}, удаляет signature
// Уязвимая библиотека принимает токен
// Защита: всегда явно указывать algorithms
jwt.verify(token, secret, { algorithms: ['HS256'] }); // не ['HS256', 'none']!

// 2. Отсутствие rate limiting на login
app.post('/auth/login', rateLimiter({ max: 5, windowMs: 15 * 60 * 1000 }), loginHandler);

// 3. Слабые пароли: нет проверки на минимальную сложность
// Проверка через zxcvbn (оценка надёжности пароля):
import zxcvbn from 'zxcvbn';
const { score } = zxcvbn(password); // 0-4, требуем >= 3

// 4. Отсутствие MFA для привилегированных операций
// 5. Предсказуемые session/reset tokens (не криптографически случайные)
// ПЛОХО: Math.random() → предсказуем
// ХОРОШО: crypto.randomBytes(32).toString('hex')
```

## A08: Software and Data Integrity Failures

Включает уязвимости supply chain и нарушение целостности данных.

Атака на цепочку поставок компрометирует не ваш код, а популярный пакет. Log4Shell (2021) и `XZ Utils` (2024) — самые известные случаи. Злоумышленник компрометирует пакет в npm, pip или maven, и все приложения, использующие пакет, уязвимы.

Защита:

- Subresource Integrity (SRI) для скриптов с CDN (сеть доставки контента): `<script src="..." integrity="sha384-..." crossorigin="anonymous">`.
- npm lockfile (`package-lock.json`) с проверкой integrity hash.
- Подписанные Docker images (Docker Content Trust).
- Проверка подписи пакетов: npm provenance, sigstore в Python Package Index (PyPI).
- Проверять контрольные суммы артефактов в пайплайне CI (непрерывная интеграция) и CD (непрерывная доставка).

Уязвимости десериализации — вторая половина этой категории:

- Никогда не десериализовывать пользовательский ввод в объекты.
- `JSON.parse` безопасен, а `eval()` — нет.
- Opaque-токены для refresh tokens, а не JWT со сложным payload.

## A09: Security Logging and Monitoring Failures

У логирования здесь две задачи: записать достаточно, чтобы заметить атаку, и не записать в лог ни одного секрета. Код ниже решает обе.

```typescript
// Что нужно логировать (и как безопасно):

const sensitiveFields = ['password', 'token', 'secret', 'creditCard', 'ssn'];

function sanitizeForLog(obj: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(obj).map(([key, value]) =>
      sensitiveFields.some(f => key.toLowerCase().includes(f))
        ? [key, '[REDACTED]']
        : [key, value]
    )
  );
}

// Обязательно логировать:
// - Успешные и неуспешные попытки логина (с userId/IP)
// - Отказы авторизации (403) — паттерн bruteforce/scanning
// - Изменения привилегий (роль пользователя)
// - Административные действия
// - SQL ошибки (возможная injection попытка)
// - Аномальные паттерны: N запросов/сек с одного IP

// Алертинг (среднее время обнаружения атаки без мониторинга: 200+ дней):
// AWS CloudWatch Alerts, Datadog, PagerDuty
// Alert на: 5+ 403 за 1 мин с одного IP → блокировка/расследование
```

## A10: Server-Side Request Forgery (SSRF)

Server-Side Request Forgery, или SSRF, — это уязвимость, при которой сервер выполняет HTTP-запрос к произвольному URL по указанию злоумышленника.

```typescript
// Уязвимый сценарий: "загрузи изображение по URL"
app.post('/api/fetch-image', authenticate, async (req, res) => {
  const { url } = req.body;
  // УЯЗВИМО: злоумышленник передаёт:
  // - "http://localhost:5432" → подключение к внутренней PostgreSQL
  // - "http://169.254.169.254/latest/meta-data/iam/security-credentials/"
  //   → AWS Instance Metadata Service → получение IAM credentials
  // - "http://internal.company.service/admin" → внутренние API
  const response = await fetch(url);
  res.send(await response.buffer());
});

// Защита: allowlist + DNS rebinding protection
import { Resolver } from 'dns/promises';

const ALLOWED_HOSTS = new Set(['images.example.com', 'cdn.example.com']);
const PRIVATE_RANGES = [
  /^127\./,
  /^10\./,
  /^192\.168\./,
  /^172\.(1[6-9]|2\d|3[01])\./,
  /^169\.254\./,  // link-local (AWS metadata)
  /^::1$/,
  /^fc00:/,
];

async function safeRequest(url: string): Promise<Response> {
  const parsed = new URL(url);

  // Allowlist по hostname
  if (!ALLOWED_HOSTS.has(parsed.hostname)) {
    throw new Error('Host not allowed');
  }

  // DNS lookup → проверка что IP не private (DNS rebinding)
  const resolver = new Resolver();
  const [ip] = await resolver.resolve4(parsed.hostname);
  if (PRIVATE_RANGES.some(r => r.test(ip))) {
    throw new Error('Private IP ranges not allowed');
  }

  // Использовать resolved IP для подключения (не hostname повторно)
  return fetch(url); // в production: использовать библиотеку с ip-binding
}
```

## Типичные ошибки на интервью

- **"Знаю OWASP Top 10 наизусть"** — само по себе не ценность. Важно объяснить механизм каждой уязвимости, привести конкретный пример кода и описать защиту. "A01 — Broken Access Control — когда нет ownership check" ценнее перечисления списка.

- **"A03 Injection = только SQL Injection"** — Injection включает SQL, NoSQL, OS Command, LDAP, SSTI (Server-Side Template Injection). Command Injection часто более критична т.к. даёт RCE (Remote Code Execution).

- **"SSRF — это редкая экзотика"** — SSRF входит в Top 10 с 2021 года. В облачных окружениях особенно опасна. Instance Metadata Service в AWS (Amazon Web Services) и GCP (Google Cloud Platform) отдаёт IAM (identity and access management) credentials.

- **"Security Misconfiguration — это только не те права на файлах"** — охватывает широкий спектр: открытые S3 buckets, debug режим в production, X-Powered-By header раскрывает stack, дефолтные credentials, избыточные CORS настройки.

- **"A08 Software Integrity — это только зависимости"** — включает также нарушение целостности пайплайна (CI/CD), unsigned updates, десериализацию ненадёжных данных.
