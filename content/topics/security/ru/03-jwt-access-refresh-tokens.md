<!-- verified: 2026-06-05, corrections: 0 -->
# JWT, Access Token и Refresh Token

## Структура JWT — что это физически

JWT (JSON Web Token) — это строка из трёх частей, разделённых точками: `header.payload.signature`. Каждая часть — base64url-encoded.

```txt
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9    ← Header (base64url)
.eyJzdWIiOiIxMjMiLCJyb2xlIjoiYWRtaW4iLCJleHAiOjE3MTk5MzI4MDB9  ← Payload
.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c   ← Signature
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

**Критически важно**: payload только подписан (Signature = HMAC(header + payload, secret)), но НЕ зашифрован. Любой может декодировать payload. Никогда не класть в JWT: пароли, секреты, полные PII данные.

Signature верифицирует: payload не был изменён после выдачи. Подделать signature без secret невозможно.

## Access Token + Refresh Token — схема и зачем нужны оба

```txt
Проблема: если выдать один long-lived JWT (например, 30 дней) →
при краже он валиден 30 дней. Отозвать нельзя (stateless).

Решение: два токена с разными TTL и местами хранения.

Access Token:
  TTL: 5-15 минут
  Содержит: userId, role, permissions
  Хранение: memory (JS variable) или HttpOnly Cookie
  Использование: в Authorization header КАЖДОГО API запроса
  При краже: валиден максимум 15 минут → риск минимален

Refresh Token:
  TTL: 7-30 дней (или до явного logout)
  Содержит: только jti (token ID) или userId + jti
  Хранение: HttpOnly Secure Cookie (не доступен JavaScript)
  Использование: ТОЛЬКО для получения нового Access Token
  Хранится в БД: можно мгновенно отозвать удалив из БД
```

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
    .cookie('refreshToken', newRefreshToken, { httpOnly: true, secure: true, sameSite: 'strict', path: '/auth' })
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

```txt
Access Token:
  Memory (JS variable):
    ✓ Недоступен XSS (не в DOM, не в storage)
    ✗ Теряется при обновлении страницы → нужен silent refresh
    Использование: SPA с aggressive refresh strategy

  HttpOnly Cookie:
    ✓ Недоступен XSS
    ✗ CSRF риск (отправляется автоматически) → нужен sameSite=strict/lax
    Использование: традиционные web apps

  localStorage / sessionStorage:
    ✗ НЕБЕЗОПАСНО: XSS script может прочитать и отправить токен
    ✗ Никогда не используй для access token

Refresh Token:
  HttpOnly Secure Cookie + path=/auth:
    ✓ Недоступен XSS
    ✓ Отправляется только на /auth/* endpoints (path ограничение)
    ✓ sameSite=strict защищает от CSRF
    Это стандартная рекомендация
```

## JWT Logout Problem — почему logout сложен и как решить

Stateless природа JWT создаёт фундаментальную проблему: после COMMIT токена невозможно "забыть" его до истечения TTL.

```txt
Проблемы, когда нужен instant revoke:
  1. Пользователь нажал "Выйти со всех устройств"
  2. Пользователь изменил пароль (старые токены должны стать невалидными)
  3. Admin заблокировал аккаунт
  4. Обнаружена кража токена

Решения:

1. Короткий TTL (15 мин):
   Простое решение. При logout просто удаляем refresh token.
   Украденный access token валиден максимум 15 мин.
   Ограничение: 15 минут всё равно могут быть критичны.

2. Token Blacklist (Redis):
   При logout/revoke: занести jti токена в Redis с TTL = оставшееся время жизни токена.
   При каждом запросе: проверить jti не в blacklist.
   Ограничение: появляется состояние (Redis), теряем чистый stateless.
   Когда использовать: когда нужен instant revoke, есть Redis.

3. Refresh Token Rotation (рекомендуется):
   Каждый refresh выдаёт НОВЫЙ refresh token и делает старый невалидным.
   Обнаружение кражи: если refresh token уже использован → alert + revoke все токены.
   Это не решает проблему украденного access token, только refresh.
```

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

```txt
HS256 (HMAC SHA-256):
  Один симметричный ключ для подписи и верификации.
  Кто подписывает → тот же кто верифицирует → нужен доступ к ключу.
  Когда: монолит или microservices с общим secret (через secrets manager).
  Риск: если secret утёк → подделка любых токенов.

RS256 (RSA SHA-256):
  Асимметричная пара: private key (подписывает) + public key (верифицирует).
  Auth service держит private key, все остальные сервисы используют public key.
  Когда: microservices, когда нельзя раздавать secret всем сервисам.
  Риск: если private key утёк → подделка токенов.
  JWKS endpoint: Auth Server публикует public keys (/.well-known/jwks.json),
  сервисы скачивают автоматически → rotation без деплоя.
```

## Типичные ошибки на интервью

- **"JWT payload зашифрован"** — нет. Payload только подписан (integrity), но читается без ключа (просто base64decode). Не кладите чувствительные данные в JWT payload.

- **"Можно хранить access token в localStorage"** — это уязвимость. XSS-атака может прочитать localStorage и украсть токен. Используйте HttpOnly Cookie или memory.

- **"Refresh token обязательно является JWT"** — нет. Refresh token — это opaque строка (случайный UUID), хранящаяся в БД. JWT-формат для refresh token добавляет риски (payload можно прочитать) без выгод (всё равно нужна БД для revoke).

- **"Logout = удалить access token из localStorage"** — это не logout для stateful систем. Настоящий logout: удалить refresh token из БД (revoke), очистить cookie. Access token продолжит работать до истечения TTL — поэтому нужен короткий TTL или blacklist.

- **"HS256 лучше RS256 потому что быстрее"** — зависит от архитектуры. В microservices RS256 безопаснее: каждый сервис верифицирует через public key, не зная private key. HS256 требует раздавать secret всем сервисам.
