<!-- verified: 2026-06-05, corrections: 0 -->
# Authentication vs Authorization

## Фундаментальное различие

Два слова отвечают на разные вопросы и выполняются в жёстком порядке. Рядом они выглядят так.

| | Authentication (аутентификация) | Authorization (авторизация) |
|---|---|---|
| Вопрос | Кто вы? | Что вам можно? |
| Что делает | Проверка личности | Проверка прав |
| Порядок | Выполняется первой | Выполняется после аутентификации |
| Результат | Личность, тот самый `userId` | Разрешено или отказано |

Типичная уязвимость: система проверяет, что JWT (JSON Web Token) валиден, — это аутентификация. Но она не проверяет, что именно этот пользователь имеет право на этот ресурс, а это уже авторизация. Такая дыра называется insecure direct object reference (IDOR).

## Методы аутентификации

Шесть методов покрывают почти всё, что встречается на практике.

**1. Password-based.** Самый распространённый. Риски: brute force, phishing, повторное использование пароля. Требует хранения через bcrypt или argon2, ограничения частоты запросов и блокировки после N попыток.

**2. Token-based (JWT).** Stateless: сервер не хранит состояние сессии. Используется в REST (representational state transfer) API и в мобильных приложениях. Подробнее — [JWT, Access Token и Refresh Token](./03-jwt-access-refresh-tokens.md).

**3. OAuth 2.0 / OpenID Connect.** Делегированная аутентификация: "Войти через Google" или "Войти через GitHub". Сам OAuth 2.0 — протокол авторизации, то есть про доступ к ресурсам. OpenID Connect — слой поверх OAuth 2.0 для identity, то есть для аутентификации.

**4. Session-based (cookie + серверная сессия).** Сервер хранит сессию в Redis или в базе данных, а cookie содержит только идентификатор сессии. Преимущество: мгновенный revoke. Недостаток: stateful, масштабировать сложнее.

**5. Multi-factor authentication (MFA), многофакторная аутентификация.** Что-то, что вы знаете (пароль), плюс что-то, что у вас есть (TOTP-код, time-based one-time password), плюс что-то, чем вы являетесь (биометрия). Критически важно для админских аккаунтов.

**6. Passkeys (WebAuthn).** Криптографическая пара ключей: приватный на устройстве, публичный у сервера. Устойчив к фишингу, потому что ключ привязан к origin. Будущий стандарт.

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

Проблема RBAC: роли становятся грубыми инструментами при росте сложности. "Manager" может видеть **всех** пользователей — но должен видеть только **своих**.

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

JWT содержит claims, которые используются для авторизации без обращения к БД (базе данных):

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

Важно: роль и разрешения в JWT — снимок на момент выдачи. Если изменить роль пользователя в базе, JWT со старой ролью останется валидным до истечения срока. Решение: короткий TTL (time to live) в 15 минут плюс refresh token.

## Session-based vs Token-based — сравнение

Оба подхода держат пользователя залогиненным. Разница в том, где живёт состояние, и она тянет за собой всё остальное.

**Session-based (cookie + Redis):**

- ✓ Мгновенный revoke: удалить сессию из Redis — и пользователь вышел.
- ✓ Payload не виден клиенту.
- ✗ Stateful: все серверы должны иметь доступ к одному Redis.
- ✗ Риск CSRF (cross-site request forgery), потому что браузер отправляет cookie автоматически.
- Когда: традиционные веб-приложения, когда важен мгновенный revoke.

**Token-based (JWT):**

- ✓ Stateless: любой сервер может проверить токен без обращения к хранилищу.
- ✓ Хорошо для микросервисов и API.
- ✗ Revoke только через blacklist, что нивелирует преимущество stateless, либо ждать истечения TTL.
- ✗ Payload виден, ведь base64 — это кодирование, а не шифрование: не кладите туда чувствительные данные.
- Когда: REST API, мобильные клиенты, межсервисная коммуникация.

## OAuth 2.0 — делегированная авторизация

OAuth 2.0 — протокол авторизации (не аутентификации). Пользователь разрешает приложению доступ к своим ресурсам у другого провайдера. Authorization Code Flow ниже — тот вариант, который берут для веба, и он проходит в пять шагов.

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

- **"OAuth = Аутентификация"** — OAuth 2.0 — протокол **авторизации** (доступ к ресурсам). Для аутентификации через OAuth нужен OpenID Connect (слой поверх OAuth 2.0, добавляющий id_token и /userinfo endpoint).

- **"JWT сам по себе = авторизация"** — JWT — это формат токена, который содержит identity и claims. Авторизация — это проверка этих claims против правил доступа. JWT без последующей проверки прав = только аутентификация.

- **"RBAC всегда достаточно"** — для простых систем да. Но для "пользователь видит только свои ресурсы" нужен ownership check (resource-based authorization), а не только проверка роли.

- **"Можно не проверять авторизацию для каждого endpoint"** — каждый endpoint должен явно проверять авторизацию. Паттерн "добавляем auth позже" приводит к уязвимостям класса IDOR, то есть insecure direct object reference.

- **"Session и JWT несовместимы"** — они не конкуренты. Можно использовать JWT для API и cookie sessions для веб-интерфейса в одном приложении. Выбор зависит от требований к revoke, клиентах и архитектуре.
