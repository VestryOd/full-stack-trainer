<!-- verified: 2026-06-23, corrections: 0 -->
# Паттерны аутентификации

## Аутентификация vs Авторизация

Прежде всего — разница, которую путают постоянно:

```txt
Аутентификация (Authentication, AuthN):
  "Кто ты?" — доказательство личности.
  Логин/пароль, токен, сертификат.

Авторизация (Authorization, AuthZ):
  "Что тебе можно?" — проверка прав.
  Роли, политики, ACL.

Порядок: сначала AuthN, затем AuthZ.
Нельзя проверить права, не зная кто это.
```

HTTP-ответы отражают эту разницу:
```txt
401 Unauthorized — не аутентифицирован (плохое название — исторически сложилось)
403 Forbidden    — аутентифицирован, но не авторизован
```

---

## Session-Based Authentication (Сессии)

Классический подход: сервер хранит состояние сессии, клиент получает ID.

### Механика

```txt
1. POST /login { email, password }
   │
   ▼
2. Сервер проверяет credentials:
   - Находит пользователя в БД
   - Проверяет bcrypt-хэш пароля
   - Создаёт запись в session store (Redis/БД)
   - session = { id: "abc123", userId: 42, expiresAt: ... }
   │
   ▼
3. Ответ:
   HTTP/1.1 200 OK
   Set-Cookie: sessionId=abc123; HttpOnly; Secure; SameSite=Lax; Path=/
   │
   ▼
4. Последующие запросы:
   GET /api/me HTTP/1.1
   Cookie: sessionId=abc123
   │
   ▼
5. Сервер достаёт сессию из store по sessionId,
   получает userId → загружает пользователя
```

### Cookie-атрибуты (критически важны)

```http
Set-Cookie: sessionId=abc123; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=86400
```

```txt
HttpOnly    — JS не может читать cookie (защита от XSS)
Secure      — отправлять только по HTTPS
SameSite=Strict — cookie не отправляется при cross-site запросах совсем
SameSite=Lax    — отправляется при top-level GET навигации (рекомендуемый дефолт)
SameSite=None   — всегда отправляется (нужно если API на другом домене, + Secure)
Path=/      — доступна для всех путей
Max-Age     — TTL в секундах (предпочтительнее Expires)
```

### Session Store

```txt
Память сервера → ❌ Не масштабируется, теряется при перезапуске
БД (PostgreSQL) → ⚠️ Медленнее, но надёжно, легко invalidate
Redis           → ✅ Быстро, TTL встроен, поддерживает horizontal scaling
```

```typescript
// Express + express-session + Redis:
import session from "express-session";
import RedisStore from "connect-redis";
import { createClient } from "redis";

const redisClient = createClient({ url: process.env.REDIS_URL });
await redisClient.connect();

app.use(session({
  store: new RedisStore({ client: redisClient }),
  secret: process.env.SESSION_SECRET!,
  resave: false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 24 * 60 * 60 * 1000, // 24 часа в мс
  },
}));
```

### Преимущества и недостатки сессий

```txt
Плюсы:
  ✅ Мгновенная инвалидация: удалить из Redis = пользователь вышел
  ✅ Маленький "токен" (просто ID)
  ✅ Сервер видит все активные сессии

Минусы:
  ❌ Stateful: каждый сервер должен иметь доступ к session store
  ❌ Store становится single point of failure (если Redis упал)
  ❌ Дополнительный RTT к Redis при каждом запросе
  ❌ Плохо подходит для мобильных клиентов и API-to-API
```

---

## JWT (JSON Web Tokens)

JWT — это стандарт (RFC 7519) для передачи данных в виде подписанного JSON. Главное отличие от сессий: **сервер не хранит состояние** — вся информация внутри токена.

### Структура JWT

```txt
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0MiIsInJvbGUiOiJhZG1pbiIsImV4cCI6MTcxOTIwMDAwMH0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c

│──────── Header ────────│───────────── Payload ─────────────│──── Signature ────│

Header  (base64url): { "alg": "HS256", "typ": "JWT" }
Payload (base64url): { "sub": "42", "role": "admin", "exp": 1719200000 }
Signature: HMACSHA256(base64url(header) + "." + base64url(payload), secret)
```

**Важно**: base64url — это **кодирование**, не шифрование. Payload виден всем. Никогда не кладите в JWT чувствительные данные (пароли, данные карты).

### Стандартные claims

```typescript
interface JwtPayload {
  sub: string;    // Subject — ID пользователя
  iss?: string;   // Issuer — кто выдал токен
  aud?: string;   // Audience — для кого предназначен
  exp: number;    // Expiration — unix timestamp истечения
  iat: number;    // Issued At — unix timestamp выдачи
  jti?: string;   // JWT ID — уникальный ID токена (для blacklist)
  // custom claims:
  role?: string;
  email?: string;
}
```

### Access Token + Refresh Token

Одиночный JWT с долгим сроком жизни — плохая практика: при компрометации отозвать нельзя. Стандартный паттерн — два токена:

```txt
Access Token:
  - Короткий срок жизни: 15 минут — 1 час
  - Содержит данные пользователя (sub, role)
  - Передаётся в каждом запросе
  - Stateless: сервер не хранит
  - При компрометации — малый window of vulnerability

Refresh Token:
  - Долгий срок жизни: 7-90 дней
  - Хранится в HttpOnly cookie (не JS-доступен)
  - Используется ТОЛЬКО для получения нового access token
  - Сервер ХРАНИТ (в Redis/БД) — позволяет инвалидировать
```

```txt
Flow:

1. POST /auth/login
   → { accessToken: "eyJ...", expiresIn: 900 }
   + Set-Cookie: refreshToken=...; HttpOnly; Secure; SameSite=Strict

2. GET /api/me
   Authorization: Bearer eyJ...   ← access token в заголовке
   → 200 OK (пока access token валиден)

3. Access token истёк:
   GET /api/me → 401 Unauthorized

4. POST /auth/refresh
   Cookie: refreshToken=...       ← браузер отправляет автоматически
   → { accessToken: "eyJ...", expiresIn: 900 }
   + Set-Cookie: refreshToken=... (rotation — новый refresh token)

5. Logout:
   POST /auth/logout
   → Сервер удаляет refresh token из store
   + Set-Cookie: refreshToken=; Max-Age=0 (очищает cookie)
```

### Алгоритмы подписи

```txt
HS256 (HMAC SHA-256):
  - Один секретный ключ для подписи и верификации
  - Подходит если один сервис выдаёт и проверяет
  - Если ключ утёк — все токены скомпрометированы

RS256 (RSA SHA-256):
  - Приватный ключ подписывает, публичный верифицирует
  - Можно раздать публичный ключ всем сервисам
  - Никакой сервис кроме issuer не может выдавать токены
  - Стандарт для OAuth 2.0 / OpenID Connect

ES256 (ECDSA SHA-256):
  - Как RS256, но короче ключи, быстрее операции
  - Предпочтительно в современных системах
```

### TypeScript пример

```typescript
import jwt from "jsonwebtoken";
import { z } from "zod";

const ACCESS_TOKEN_SECRET = process.env.JWT_ACCESS_SECRET!;
const REFRESH_TOKEN_SECRET = process.env.JWT_REFRESH_SECRET!;

const tokenPayloadSchema = z.object({
  sub: z.string(),
  role: z.string(),
});

type TokenPayload = z.infer<typeof tokenPayloadSchema>;

function signAccessToken(payload: TokenPayload): string {
  return jwt.sign(payload, ACCESS_TOKEN_SECRET, {
    expiresIn: "15m",
    algorithm: "HS256",
  });
}

function verifyAccessToken(token: string): TokenPayload {
  const decoded = jwt.verify(token, ACCESS_TOKEN_SECRET);
  return tokenPayloadSchema.parse(decoded);
}

// Middleware
function requireAuth(
  req: express.Request,
  res: express.Response,
  next: express.NextFunction
) {
  const authHeader = req.headers.authorization;
  if (!authHeader?.startsWith("Bearer ")) {
    return res.status(401).json({ error: "Missing token" });
  }

  const token = authHeader.slice(7);
  try {
    req.user = verifyAccessToken(token);
    next();
  } catch (err) {
    if (err instanceof jwt.TokenExpiredError) {
      return res.status(401).json({ error: "Token expired" });
    }
    return res.status(401).json({ error: "Invalid token" });
  }
}
```

### Преимущества и недостатки JWT

```txt
Плюсы:
  ✅ Stateless: не нужен session store, масштабируется горизонтально
  ✅ Self-contained: данные внутри токена (меньше обращений к БД)
  ✅ Кросс-доменный: легко использовать между сервисами
  ✅ Стандарт для мобильных и SPA-приложений

Минусы:
  ❌ Невозможно инвалидировать до истечения (без blacklist)
  ❌ Растут в размере при добавлении claims (каждый запрос несёт payload)
  ❌ Сложная ротация ключей
  ❌ Много способов неправильно реализовать (alg:none, не проверять exp)
```

---

## OAuth 2.0

OAuth 2.0 — это фреймворк **делегированной авторизации** (RFC 6749). Цель: позволить приложению действовать от имени пользователя без получения его пароля.

```txt
Пример без OAuth:
  "Разреши приложению читать твой Google Calendar"
  Раньше: дай приложению свой Google пароль ← ужасно

С OAuth 2.0:
  Пользователь логинится у Google (не у приложения)
  Google спрашивает: "Разрешить app.example.com читать Calendar?"
  Пользователь: "Да"
  Google выдаёт приложению токен с доступом только к Calendar
  Приложение использует токен, не зная пароль пользователя
```

### Участники OAuth 2.0

```txt
Resource Owner  — пользователь (владелец данных)
Client          — приложение, которое хочет доступ
Authorization Server — сервер выдающий токены (Google, GitHub, ваш Auth сервер)
Resource Server — API с защищёнными данными
```

### Authorization Code Flow (основной флоу)

Для web и мобильных приложений с backend.

```txt
1. Пользователь нажимает "Войти через Google"

2. Клиент перенаправляет пользователя:
   GET https://accounts.google.com/o/oauth2/auth
     ?response_type=code
     &client_id=CLIENT_ID
     &redirect_uri=https://app.example.com/callback
     &scope=openid email calendar.readonly
     &state=random_csrf_token
     &code_challenge=S256_PKCE_CHALLENGE
     &code_challenge_method=S256

3. Пользователь логинится у Google, даёт согласие

4. Google перенаправляет обратно:
   GET https://app.example.com/callback
     ?code=AUTH_CODE
     &state=random_csrf_token

5. Backend обменивает code на токены (server-to-server):
   POST https://oauth2.googleapis.com/token
   Content-Type: application/x-www-form-urlencoded

   grant_type=authorization_code
   &code=AUTH_CODE
   &redirect_uri=https://app.example.com/callback
   &client_id=CLIENT_ID
   &client_secret=CLIENT_SECRET
   &code_verifier=PKCE_VERIFIER

6. Authorization server возвращает:
   {
     "access_token": "ya29.xxx",
     "refresh_token": "1//xxx",
     "expires_in": 3600,
     "token_type": "Bearer",
     "id_token": "eyJ..."   ← OpenID Connect
   }

7. Клиент использует access_token:
   GET https://www.googleapis.com/calendar/v3/events
   Authorization: Bearer ya29.xxx
```

### PKCE (Proof Key for Code Exchange)

PKCE — расширение для защиты от перехвата authorization code. Обязательно для мобильных и SPA (где нет client_secret):

```txt
Клиент генерирует:
  code_verifier = random(43-128 символов)
  code_challenge = base64url(SHA256(code_verifier))

Отправляет code_challenge в authorization request (шаг 2).
Отправляет code_verifier при обмене code → token (шаг 5).
Authorization server проверяет: SHA256(code_verifier) == code_challenge
```

Без PKCE: если кто-то перехватил authorization code — он получит токены. С PKCE — без code_verifier code бесполезен.

### Client Credentials Flow

Для API-to-API (без участия пользователя):

```http
POST https://auth.example.com/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
&client_id=SERVICE_CLIENT_ID
&client_secret=SERVICE_CLIENT_SECRET
&scope=orders:read invoices:write

→ { "access_token": "...", "expires_in": 3600 }
```

Используется для: микросервисов, фоновых задач, server-to-server интеграций.

### OpenID Connect (OIDC)

OAuth 2.0 — про авторизацию (доступ к ресурсам). OpenID Connect — слой аутентификации поверх OAuth 2.0: добавляет `id_token` (JWT с данными пользователя) и `/userinfo` endpoint.

```txt
OAuth 2.0:  "Разреши читать Calendar" → access token
OIDC:       "Кто этот пользователь?" → id_token (sub, email, name, picture)
```

---

## API Keys

Простейший механизм для server-to-server и developer API:

```http
# В заголовке (предпочтительно):
Authorization: Bearer sk-proj-abc123
X-API-Key: sk-proj-abc123

# В query param (только для простых случаев, не для чувствительных данных):
GET /api/data?api_key=sk-proj-abc123
```

### Хранение API-ключей на сервере

Никогда не храните ключ в открытом виде — только хэш:

```typescript
import crypto from "crypto";

// При создании ключа:
const rawKey = `sk-proj-${crypto.randomBytes(32).toString("base64url")}`;
const keyHash = crypto.createHash("sha256").update(rawKey).digest("hex");

// Храним keyHash в БД, возвращаем rawKey пользователю однократно

// При проверке:
const incomingKey = req.headers["x-api-key"] as string;
const incomingHash = crypto.createHash("sha256").update(incomingKey).digest("hex");

const apiKey = await db.apiKeys.findOne({ where: { keyHash: incomingHash } });
if (!apiKey || apiKey.revokedAt) {
  return res.status(401).json({ error: "Invalid API key" });
}
```

### HMAC Request Signing

Для высокозащищённых API (платёжные системы, AWS SDK): подписывается весь запрос, а не только ключ.

```typescript
// Клиент подписывает запрос:
const timestamp = Date.now().toString();
const body = JSON.stringify(payload);
const message = `${req.method}\n${req.path}\n${timestamp}\n${body}`;
const signature = crypto
  .createHmac("sha256", API_SECRET)
  .update(message)
  .digest("hex");

// Добавляет в запрос:
headers["X-Timestamp"] = timestamp;
headers["X-Signature"] = signature;

// Сервер верифицирует:
// 1. Проверяет timestamp (не старше 5 минут — защита от replay attacks)
// 2. Пересчитывает подпись и сравнивает
```

---

## Сравнение паттернов

```txt
┌──────────────────┬──────────────┬────────────┬─────────────┬──────────┐
│                  │ Session      │ JWT        │ OAuth 2.0   │ API Key  │
├──────────────────┼──────────────┼────────────┼─────────────┼──────────┤
│ Инвалидация      │ ✅ Мгновенно │ ❌ До exp   │ ✅ Refresh  │ ✅ Сразу │
│ Stateless        │ ❌ Нет       │ ✅ Да       │ ✅ Да       │ ❌ Нет  │
│ Масштабирование  │ ⚠️ Redis нужен│ ✅ Просто  │ ✅ Просто  │ ⚠️ Redis │
│ Cross-domain     │ ❌ Сложно    │ ✅ Просто   │ ✅ Нативно │ ✅ Просто│
│ 3rd-party auth   │ ❌ Нет       │ ❌ Нет      │ ✅ Для этого│ ❌ Нет  │
│ Мобильные        │ ⚠️ Сложнее   │ ✅ Просто  │ ✅ Просто  │ ✅ Просто│
│ Сложность        │ Низкая       │ Средняя    │ Высокая     │ Низкая  │
└──────────────────┴──────────────┴────────────┴─────────────┴──────────┘

Когда что использовать:
  Session    — традиционный web, где фронтенд и API на одном домене
  JWT        — SPA/мобильные с собственным auth, микросервисы
  OAuth 2.0  — "Войти через Google/GitHub", доступ к чужим данным
  API Key    — developer API, server-to-server без пользователя
```

---

## Типичные ошибки на интервью

- **"JWT хранить в localStorage — удобно"** — опасно. localStorage доступен любому JS на странице (XSS → кража токена). Access token — в памяти JS (теряется при перезагрузке), refresh token — в HttpOnly cookie (недоступен XSS).

- **"JWT нельзя инвалидировать"** — можно, с ценой. Варианты: blacklist jti в Redis, rotation refresh token (каждое использование выдаёт новый), short-lived access tokens (15 мин). Абсолютный stateless JWT — не для сценариев где нужна мгновенная инвалидация.

- **"401 и 403 — одно и то же"** — нет. 401: токена нет или он невалиден. 403: токен валиден, но прав нет. Путаница ломает клиентскую логику (401 = иди на страницу логина; 403 = покажи "нет доступа").

- **"JWT signature гарантирует что данные зашифрованы"** — нет. Signature гарантирует целостность (никто не изменил). Данные в открытом виде (base64). Для шифрования — JWE (JSON Web Encryption), но на практике редко нужно.

- **"OAuth 2.0 = аутентификация"** — OAuth 2.0 про авторизацию (делегированный доступ). Аутентификацию добавляет OpenID Connect поверх OAuth 2.0 через id_token. "Войти через Google" — это OIDC, не просто OAuth.

- **"client_secret можно хранить в SPA/мобильном приложении"** — нет. В публичных клиентах (SPA, mobile) нет безопасного способа хранить секрет. Используется PKCE без client_secret.

- **"bcrypt для API-ключей"** — нет. bcrypt медленный намеренно (для паролей). API-ключи — это длинные случайные строки, для них достаточно SHA-256. bcrypt для хранения паролей, SHA-256 для хранения API-ключей.
