<!-- verified: 2026-06-05, corrections: 0 -->
# JWT, Access Token и Refresh Token

## Структура JWT — что это физически

JWT (JSON Web Token) — это строка из трёх частей, разделённых точками: `header.payload.signature`. Каждая часть — base64url-encoded.

```txt
Header (base64url):
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9
Payload:
.eyJzdWIiOiIxMjMiLCJyb2xlIjoiYWRtaW4iLCJleHAiOjE3MTk5MzI4MDB9
Signature:
.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c
```

```json
// Header — алгоритм подписи и тип токена
{ "alg": "HS256", "typ": "JWT" }

// Payload — claims (не зашифрованы, любой может прочитать)
{
  "sub": "user-123",        // subject — идентификатор пользователя
  "role": "admin",
  "exp": 1719932800,        // expiry timestamp (UNIX)
  "iat": 1719929200,        // issued at timestamp
  "jti": "unique-token-id"  // JWT ID — для blacklist/revoke
}
```

**Критически важно**: payload только подписан, но **не** зашифрован. Подпись — это HMAC (hash-based message authentication code), посчитанный по заголовку и payload с секретом. Любой может декодировать payload, поэтому никогда не кладите в JWT пароли, секреты и полные PII (personally identifiable information) данные.

Signature верифицирует: payload не был изменён после выдачи. Подделать signature без secret невозможно.

## Access Token + Refresh Token — схема и зачем нужны оба

Наивный ответ — один долгоживущий JWT, скажем на 30 дней. Выдайте такой, и украденная копия остаётся валидной 30 дней, а отозвать её нельзя, потому что схема stateless. Решение — два токена с разными сроками жизни и разными местами хранения.

**Access Token**

- TTL (time to live): 5-15 минут.
- Содержит: `userId`, роль, разрешения.
- Хранение: memory (переменная JS) или HttpOnly Cookie.
- Использование: в заголовке `Authorization` **каждого** API-запроса.
- При краже: валиден максимум 15 минут, поэтому риск минимален.

**Refresh Token**

- TTL: 7-30 дней, или до явного logout.
- Содержит: только `jti` (token ID), либо `userId` плюс `jti`.
- Хранение: HttpOnly Secure Cookie, недоступный JavaScript.
- Использование: **только** для получения нового access token.
- Хранится в базе данных, поэтому удаление записи отзывает его мгновенно.

## Полный flow — от логина до refresh

```typescript
// 1. Логин
app.post('/auth/login', async (req, res) => {
  const { email, password } = req.body;
  const user = await db.users.findByEmail(email);

  if (!user || !await bcrypt.compare(password, user.passwordHash)) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }

  const accessToken = jwt.sign(
    { sub: user.id, role: user.role },
    process.env.JWT_ACCESS_SECRET!,
    { expiresIn: '15m' }
  );

  const refreshToken = crypto.randomUUID(); // opaque token
  const hashedRefreshToken = await bcrypt.hash(refreshToken, 10);

  // Сохраняем в БД для возможности revoke
  await db.refreshTokens.create({
    token: hashedRefreshToken,
    userId: user.id,
    expiresAt: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
  });

  res
    .cookie('refreshToken', refreshToken, {
      httpOnly: true,   // JS не может прочитать
      secure: true,     // только HTTPS
      sameSite: 'strict', // CSRF защита
      maxAge: 30 * 24 * 60 * 60 * 1000, // 30 дней в мс
      path: '/auth',    // только для /auth endpoints
    })
    .json({ accessToken }); // access token в JSON ответе
});

// 2. Refresh — получить новый access token
app.post('/auth/refresh', async (req, res) => {
  const refreshToken = req.cookies.refreshToken;
  if (!refreshToken) return res.status(401).json({ error: 'No refresh token' });

  // Найти и верифицировать refresh token
  const stored = await db.refreshTokens.findValidByUserId(/* ... */);
  const isValid = stored && await bcrypt.compare(refreshToken, stored.token);
  if (!isValid || stored.expiresAt < new Date()) {
    return res.status(401).json({ error: 'Invalid or expired refresh token' });
  }

  // Refresh Token Rotation: удалить старый, выдать новый
  await db.refreshTokens.delete(stored.id);

  const newRefreshToken = crypto.randomUUID();
  const hashedNew = await bcrypt.hash(newRefreshToken, 10);
  await db.refreshTokens.create({ token: hashedNew, userId: stored.userId, /* ... */ });

  const accessToken = jwt.sign(
    { sub: stored.userId, role: stored.user.role },
    process.env.JWT_ACCESS_SECRET!,
    { expiresIn: '15m' }
  );

  res
    .cookie('refreshToken', newRefreshToken, {
      httpOnly: true,
      secure: true,
      sameSite: 'strict',
      path: '/auth',
    })
    .json({ accessToken });
});

// 3. Logout
app.post('/auth/logout', authenticate, async (req, res) => {
  const refreshToken = req.cookies.refreshToken;
  if (refreshToken) {
    // Удалить refresh token из БД → полный revoke
    await db.refreshTokens.deleteByUserId(req.user.sub);
  }
  res.clearCookie('refreshToken', { path: '/auth' }).json({ ok: true });
});
```

## Где хранить токены — выбор с trade-offs

Каждый вариант меняет одну угрозу на другую. XSS (cross-site scripting) читает всё, что доступно JavaScript, а CSRF (cross-site request forgery) едет на всём, что браузер отправляет автоматически.

**Access Token в памяти, переменной JS:**

- ✓ Недоступен XSS: его нет ни в DOM (document object model), ни в хранилищах.
- ✗ Теряется при обновлении страницы, поэтому нужен silent refresh.
- Использование: SPA (single-page application) с агрессивной стратегией обновления.

**Access Token в HttpOnly Cookie:**

- ✓ Недоступен XSS.
- ✗ Риск CSRF, потому что cookie отправляется автоматически: нужен `sameSite=strict` или `sameSite=lax`.
- Использование: традиционные веб-приложения.

**Access Token в localStorage или sessionStorage:**

- ✗ **Небезопасно**: XSS-скрипт прочитает токен и отправит его атакующему.
- ✗ Никогда не используйте это для access token.

**Refresh Token в HttpOnly Secure Cookie с `path=/auth`:**

- ✓ Недоступен XSS.
- ✓ Отправляется только на эндпоинты `/auth/*` благодаря ограничению по пути.
- ✓ `sameSite=strict` защищает от CSRF.
- Это стандартная рекомендация.

## JWT Logout Problem — почему logout сложен и как решить

Stateless-природа JWT создаёт фундаментальную проблему: после выдачи токена невозможно "забыть" его до истечения TTL (time to live).

**Когда нужен мгновенный revoke:**

1. Пользователь нажал "Выйти со всех устройств".
2. Пользователь изменил пароль, и старые токены должны стать невалидными.
3. Администратор заблокировал аккаунт.
4. Обнаружена кража токена.

**Решение 1 — короткий TTL в 15 минут.** Просто: при logout удаляем refresh token. Украденный access token тогда валиден максимум 15 минут. Ограничение: 15 минут всё равно могут быть критичны.

**Решение 2 — token blacklist в Redis.** При logout или revoke заносим `jti` токена в Redis с TTL, равным оставшемуся времени жизни токена. На каждом запросе проверяем, что `jti` не в чёрном списке. Ограничение: появляется состояние (Redis), и чистый stateless теряется. Берите этот вариант, когда нужен мгновенный revoke и Redis уже есть.

**Решение 3 — refresh token rotation, рекомендуемый вариант.** Каждый refresh выдаёт **новый** refresh token и делает старый невалидным. Обнаружение кражи: если refresh token уже использован, поднимаем алерт и отзываем все токены. Это не решает проблему украденного access token, только украденного refresh token.

```typescript
// Blacklist через Redis
import { createClient } from 'redis';
const redis = createClient();

async function revokeToken(jti: string, ttlSeconds: number): Promise<void> {
  await redis.setEx(`blacklist:${jti}`, ttlSeconds, '1');
}

async function isRevoked(jti: string): Promise<boolean> {
  return (await redis.exists(`blacklist:${jti}`)) === 1;
}

// В authenticate middleware:
const payload = jwt.verify(token, secret) as JwtPayload;
if (payload.jti && await isRevoked(payload.jti)) {
  return res.status(401).json({ error: 'Token revoked' });
}
```

## Алгоритмы подписи — HS256 vs RS256

Оба имени говорят, как считается подпись. HS256 — это HMAC поверх SHA-256, то есть secure hash algorithm, с одним общим ключом. RS256 — это RSA (Rivest-Shamir-Adleman) поверх SHA-256, с парой ключей.

**HS256 — один симметричный ключ и для подписи, и для верификации.**

- Кто подписывает, тот же и верифицирует, поэтому доступ к ключу нужен всем сторонам.
- Когда: монолит или микросервисы с общим secret через secrets manager.
- Риск: если secret утёк, подделать можно любой токен.

**RS256 — асимметричная пара: private key подписывает, public key верифицирует.**

- Auth service держит private key, все остальные сервисы используют public key.
- Когда: микросервисы, когда нельзя раздавать secret всем сервисам.
- Риск: если private key утёк, токены можно подделать.
- JWKS (JSON Web Key Set) endpoint: Auth Server публикует public keys по адресу `/.well-known/jwks.json`. Сервисы скачивают их автоматически, поэтому ключи ротируются без деплоя.

## Типичные ошибки на интервью

- **"JWT payload зашифрован"** — нет. Payload только подписан (integrity), но читается без ключа (просто base64decode). Не кладите чувствительные данные в JWT payload.

- **"Можно хранить access token в localStorage"** — это уязвимость. XSS-атака может прочитать localStorage и украсть токен. Используйте HttpOnly Cookie или memory.

- **"Refresh token обязательно является JWT"** — нет. Refresh token — это непрозрачная строка, случайный UUID (universally unique identifier), хранящаяся в БД (базе данных). JWT-формат для refresh token добавляет риски (payload можно прочитать) без выгод (всё равно нужна БД для revoke).

- **"Logout = удалить access token из localStorage"** — это не logout для stateful систем. Настоящий logout: удалить refresh token из БД (revoke), очистить cookie. Access token продолжит работать до истечения TTL — поэтому нужен короткий TTL или blacklist.

- **"HS256 лучше RS256 потому что быстрее"** — зависит от архитектуры. В microservices RS256 безопаснее: каждый сервис верифицирует через public key, не зная private key. HS256 требует раздавать secret всем сервисам.
