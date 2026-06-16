<!-- verified: 2026-06-05, corrections: 0 -->
# Authentication vs Authorization

## Фундаментальное различие

```txt
Authentication (Аутентификация)   Authorization (Авторизация)
────────────────────────────────  ──────────────────────────────
"КТО ТЫ?"                         "ЧТО ТЕБЕ МОЖНО?"
Проверка личности                  Проверка прав
Выполняется ПЕРВОЙ                 Выполняется ПОСЛЕ аутентификации
Результат: identity (userId)       Результат: permitted/denied
```

Типичная уязвимость: система проверяет что JWT валиден (аутентификация), но не проверяет что этот конкретный пользователь имеет право на этот ресурс (авторизация) → Insecure Direct Object Reference (IDOR).

## Методы аутентификации

```txt
1. Password-based
   Самый распространённый. Риски: brute force, phishing, password reuse.
   Требует: bcrypt/argon2 хранение, rate limiting, lockout после N попыток.

2. Token-based (JWT)
   Stateless. Сервер не хранит состояние сессии.
   Используется в REST API и mobile. Подробнее: [JWT and Refresh Tokens].

3. OAuth 2.0 / OpenID Connect
   Делегированная аутентификация: "Войти через Google/GitHub".
   OAuth 2.0 = протокол авторизации (доступ к ресурсам).
   OpenID Connect = слой поверх OAuth 2.0 для identity (аутентификации).

4. Session-based (Cookie + Server Session)
   Сервер хранит сессию (Redis/DB). Cookie содержит только session ID.
   Преимущество: мгновенный revoke. Недостаток: stateful, scaling сложнее.

5. Multi-Factor Authentication (MFA)
   Что-то что знаешь (пароль) + что-то что имеешь (TOTP-код) +
   что-то чем являешься (биометрия). Критически важно для admin accounts.

6. Passkeys (WebAuthn)
   Cryptographic keypair: приватный ключ на устройстве, публичный у сервера.
   Phishing-resistant: ключ привязан к origin. Будущий стандарт.
```

## Модели авторизации

### RBAC — Role-Based Access Control

Права определяются ролью пользователя. Самая распространённая модель.

```typescript
// Определение ролей и разрешений
const PERMISSIONS = {
  'admin': ['users:read', 'users:write', 'users:delete', 'orders:all'],
  'manager': ['orders:read', 'orders:write', 'users:read'],
  'customer': ['orders:read:own', 'profile:write:own'],
} as const;

type Role = keyof typeof PERMISSIONS;

// Middleware для проверки разрешений
function requirePermission(permission: string) {
  return (req: Request, res: Response, next: NextFunction) => {
    const userPermissions = PERMISSIONS[req.user.role as Role] ?? [];
    if (!userPermissions.includes(permission as never)) {
      return res.status(403).json({ error: 'Insufficient permissions' });
    }
    next();
  };
}

// Использование
router.delete('/users/:id', authenticate, requirePermission('users:delete'), deleteUser);
```

Проблема RBAC: роли становятся грубыми инструментами при росте сложности. "Manager" может видеть ВСЕХ пользователей — но должен видеть только СВОИХ.

### ABAC — Attribute-Based Access Control

Решение принимается на основе атрибутов пользователя, ресурса и окружения.

```typescript
// Policy-based: "пользователь может редактировать ресурс если является его владельцем"
function canEdit(user: User, resource: Order): boolean {
  if (user.role === 'admin') return true;
  if (resource.ownerId === user.id) return true;
  if (user.role === 'manager' && resource.department === user.department) return true;
  return false;
}

app.patch('/orders/:id', authenticate, async (req, res) => {
  const order = await db.orders.findById(req.params.id);
  if (!canEdit(req.user, order)) {
    return res.status(403).json({ error: 'Forbidden' });
  }
  // ...
});
```

ABAC гибче RBAC, но сложнее в аудите ("кто имеет доступ к этому ресурсу?").

### Resource-based Authorization (Ownership Check)

Самый частый паттерн в реальных приложениях: проверка принадлежности ресурса.

```typescript
// IDOR уязвимость — отсутствие ownership check
app.get('/api/orders/:id', authenticate, async (req, res) => {
  // ПЛОХО: любой аутентифицированный пользователь видит любой заказ
  const order = await db.orders.findById(req.params.id);
  res.json(order);
});

// Исправление
app.get('/api/orders/:id', authenticate, async (req, res) => {
  const order = await db.orders.findById(req.params.id);
  if (!order) return res.status(404).json({ error: 'Not found' });

  // Ownership check: либо владелец, либо admin
  if (order.userId !== req.user.id && req.user.role !== 'admin') {
    return res.status(403).json({ error: 'Forbidden' });
  }

  res.json(order);
});
```

## JWT как носитель identity для авторизации

JWT содержит claims, которые используются для авторизации без обращения к БД:

```typescript
// Payload JWT при логине
const token = jwt.sign(
  {
    sub: user.id,           // subject — идентификатор пользователя
    email: user.email,
    role: user.role,        // используется для RBAC
    permissions: ['orders:read', 'profile:write:own'], // для fine-grained ABAC
  },
  process.env.JWT_SECRET!,
  { expiresIn: '15m' }
);

// Middleware: декодируем JWT и кладём user в req
function authenticate(req: Request, res: Response, next: NextFunction) {
  const token = req.headers.authorization?.replace('Bearer ', '');
  if (!token) return res.status(401).json({ error: 'Unauthorized' });

  try {
    req.user = jwt.verify(token, process.env.JWT_SECRET!) as JwtPayload;
    next();
  } catch {
    res.status(401).json({ error: 'Invalid token' });
  }
}
```

Важно: роль/permissions в JWT — снапшот на момент выдачи. Если изменить роль пользователя в БД — JWT с старой ролью остаётся валидным до истечения. Решение: короткий TTL (15 мин) + refresh token.

## Session-based vs Token-based — сравнение

```txt
Session-based (Cookie + Redis):
  ✓ Мгновенный revoke: удалить session из Redis → пользователь выходит
  ✓ Payload не виден клиенту
  ✗ Stateful: все серверы должны иметь доступ к одному Redis
  ✗ CSRF риск (cookie отправляется автоматически браузером)
  Когда: традиционные web apps, когда важен instant revoke

Token-based (JWT):
  ✓ Stateless: любой сервер может проверить без обращения к хранилищу
  ✓ Хорошо для микросервисов и API
  ✗ Revoke только через blacklist (нивелирует stateless преимущество)
     или ждать истечения TTL
  ✗ Payload виден (base64) — не класть sensitive данные
  Когда: REST API, mobile, межсервисная коммуникация
```

## OAuth 2.0 — делегированная авторизация

OAuth 2.0 — протокол авторизации (не аутентификации). Пользователь разрешает приложению доступ к своим ресурсам у другого провайдера.

```txt
Authorization Code Flow (самый безопасный для web):

1. Client → Authorization Server:
   GET /oauth/authorize?
     response_type=code&
     client_id=MY_APP&
     redirect_uri=https://myapp.com/callback&
     scope=read:email&
     state=RANDOM_STRING    ← CSRF защита

2. Пользователь логинится у провайдера (Google/GitHub)
   и подтверждает доступ

3. Authorization Server → Client:
   GET /callback?code=AUTH_CODE&state=RANDOM_STRING

4. Client → Authorization Server (server-to-server):
   POST /oauth/token
   { code, client_id, client_secret, redirect_uri }
   → { access_token, refresh_token, id_token }

5. Client → Resource Server:
   GET /api/user  Authorization: Bearer ACCESS_TOKEN
```

OpenID Connect добавляет `id_token` (JWT с identity данными) к стандартному OAuth 2.0 flow.

## Типичные ошибки на интервью

- **"OAuth = Аутентификация"** — OAuth 2.0 — протокол АВТОРИЗАЦИИ (доступ к ресурсам). Для аутентификации через OAuth нужен OpenID Connect (слой поверх OAuth 2.0, добавляющий id_token и /userinfo endpoint).

- **"JWT сам по себе = авторизация"** — JWT — это формат токена, который содержит identity и claims. Авторизация — это проверка этих claims против правил доступа. JWT без последующей проверки прав = только аутентификация.

- **"RBAC всегда достаточно"** — для простых систем да. Но для "пользователь видит только свои ресурсы" нужен ownership check (resource-based authorization), а не только проверка роли.

- **"Можно не проверять авторизацию для каждого endpoint"** — каждый endpoint должен явно проверять авторизацию. Паттерн "добавляем auth позже" приводит к IDOR (Insecure Direct Object Reference) уязвимостям.

- **"Session и JWT несовместимы"** — они не конкуренты. Можно использовать JWT для API и cookie sessions для web UI в одном приложении. Выбор зависит от требований к revoke, клиентах и архитектуре.
