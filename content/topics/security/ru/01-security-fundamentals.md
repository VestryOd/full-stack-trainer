<!-- verified: 2026-06-05, corrections: 0 -->
# Основы информационной безопасности

## Почему безопасность важна для fullstack-разработчика

Большинство серьёзных уязвимостей — не результат изощрённых атак. Это следствие плохих архитектурных решений: хранение паролей в открытом виде, отсутствие валидации ввода, избыточные привилегии сервисов. Разработчик несёт ответственность за безопасность приложения на всём стеке — от SQL-запросов до HTTP-заголовков.

## CIA Triad — три фундаментальных свойства безопасности

Любая система информационной безопасности строится на трёх принципах:

```txt
Confidentiality (Конфиденциальность)
  Данные доступны только авторизованным лицам.
  Угрозы: перехват трафика (MITM), утечка токенов, SQL Injection
  Меры: шифрование (TLS/HTTPS), JWT, RBAC, шифрование данных at-rest

Integrity (Целостность)
  Данные не могут быть изменены неавторизованным лицом незаметно.
  Угрозы: SQL Injection (прямое изменение БД), CSRF (действие от имени
  пользователя), tampering с JWT payload без подписи
  Меры: JWT Signature, HMAC, цифровые подписи, транзакции БД

Availability (Доступность)
  Система должна быть доступна авторизованным пользователям.
  Угрозы: DDoS, ресурсное истощение (unbounded queries, regex DoS),
  зависимость от внешних сервисов без fallback
  Меры: Rate Limiting, Circuit Breaker, горизонтальное масштабирование
```

Частый вопрос интервью: "Что нарушает DDoS?" — Availability. "Что нарушает перехват JWT?" — Confidentiality. "Что нарушает CSRF?" — Integrity (действие от имени пользователя без его ведома).

## Authentication vs Authorization — фундаментальное различие

```txt
Authentication (Аутентификация):  КТО ТЫ?
  Процесс проверки личности пользователя.
  Методы: login/password, OAuth 2.0, passkeys, multi-factor auth.
  Вопрос: "Ты правда Иван Иванов?"

Authorization (Авторизация):  ЧТО ТЕБЕ МОЖНО?
  Процесс проверки прав после подтверждения личности.
  Методы: RBAC (роли), ABAC (атрибуты), ACL (списки доступа).
  Вопрос: "Ивану Иванову можно удалять пользователей?"
```

Типичная ошибка: проверять только аутентификацию (валидный JWT), но не авторизацию (право на этот ресурс). Пример уязвимости:

```typescript
// НЕБЕЗОПАСНО: проверяем только что токен валиден
app.get('/api/users/:id', authenticate, async (req, res) => {
  const user = await db.users.findById(req.params.id);
  res.json(user);
});

// БЕЗОПАСНО: проверяем и аутентификацию, и право доступа к этому ресурсу
app.get('/api/users/:id', authenticate, async (req, res) => {
  if (req.user.id !== req.params.id && req.user.role !== 'admin') {
    return res.status(403).json({ error: 'Forbidden' });
  }
  const user = await db.users.findById(req.params.id);
  res.json(user);
});
```

## Principle of Least Privilege — минимальные необходимые права

Каждый компонент системы должен иметь только те права, которые строго необходимы для его работы.

```typescript
// Применение в Node.js / сервисах:

// ПЛОХО: один DB user с полными правами
// postgres://admin:password@localhost/db
// Если украдут credentials → полный доступ ко всей БД

// ХОРОШО: отдельные DB users с ограниченными правами
// postgres://app_user:password@localhost/db
// app_user имеет только: SELECT, INSERT, UPDATE, DELETE на нужных таблицах
// НЕТ: DROP, CREATE, TRUNCATE, доступа к системным таблицам

// Применение к API endpoints:
const router = express.Router();
router.post('/orders', requireRole('customer'));        // создать заказ
router.patch('/orders/:id/status', requireRole('admin')); // изменить статус
router.delete('/orders/:id', requireRole('admin'));     // удалить заказ
```

Принцип применяется везде: DB-пользователи, IAM роли в AWS, permissions в Linux, API scope в OAuth 2.0.

## Attack Surface (Поверхность атаки) — все точки входа

Поверхность атаки — совокупность всех точек, через которые злоумышленник может попытаться проникнуть в систему.

```txt
Типичная поверхность атаки веб-приложения:
  HTTP API         → SQL Injection, parameter tampering, auth bypass
  HTML Forms       → XSS, CSRF
  File Upload      → path traversal, malicious file execution
  WebSockets       → missing auth, message spoofing
  Admin Panel      → brute force, privilege escalation
  Third-party deps → supply chain attacks (npm/pip packages)
  Environment vars → secrets exposure в логах, error messages
  GraphQL          → introspection, query complexity DoS
```

Правило: каждый новый endpoint или интеграция — увеличение attack surface. Нужно явно принять это решение и добавить соответствующую защиту.

## Defense in Depth — многоуровневая защита

Полагаться на одну защиту — принципиальная ошибка. Defense in Depth: если один слой пробит, следующий должен остановить атаку.

```txt
Пример: защита API endpoint

Layer 1: HTTPS                         → шифрование трафика (MITM)
Layer 2: Rate Limiting                 → brute force, DoS
Layer 3: JWT Validation                → authentication
Layer 4: Role/Permission Check         → authorization
Layer 5: Input Validation (Zod/Joi)   → injection, invalid data
Layer 6: Parameterized Queries         → SQL Injection
Layer 7: Output Encoding               → XSS при рендеринге
Layer 8: Security Headers (Helmet.js)  → clickjacking, MIME sniffing
Layer 9: Audit Logging                 → обнаружение атак после факта
```

Каждый слой независим — уязвимость в одном не открывает всю систему.

## Security Through Obscurity — антипаттерн

Сокрытие информации (URL, структуры API, используемых технологий) не является защитой.

```txt
ПЛОХО (Security Through Obscurity):
  /api/secret-admin-panel-v2          → злоумышленник найдёт через brute force
  Скрытие версии stack'а в заголовках → security через незнание = иллюзия
  "Никто не знает этот endpoint"      → любой сканер найдёт за минуты

ХОРОШО (реальная защита):
  /api/admin-panel  + требует JWT с role='admin' + IP whitelist
  Открытый код (open source) с хорошей архитектурой безопаснее
  закрытого кода с архитектурными дырами
```

Стандарт Kerckhoffs: система должна быть безопасна даже если всё о ней известно, кроме ключа. Современная криптография работает именно так.

## HTTPS и TLS — обязательная основа

```txt
Что происходит без HTTPS:
  1. Пользователь отправляет пароль → виден в открытом виде в сети
  2. JWT в Authorization header → перехвачен
  3. Cookies с session token → перехвачены
  → Любой узел сети между клиентом и сервером видит данные

Что даёт TLS (HTTPS):
  1. Шифрование канала: данные зашифрованы, MITM видит шифротекст
  2. Аутентификация сервера: SSL-сертификат подтверждает что это именно
     ваш сервер, а не attacker
  3. Integrity: TLS MAC гарантирует что данные не изменены в пути
```

```typescript
// Express: принудительный редирект с HTTP на HTTPS
app.use((req, res, next) => {
  if (req.header('x-forwarded-proto') !== 'https' && process.env.NODE_ENV === 'production') {
    return res.redirect(301, `https://${req.headers.host}${req.url}`);
  }
  next();
});

// HSTS header: браузер запоминает "всегда HTTPS" для этого домена
app.use(helmet.hsts({
  maxAge: 31536000,        // 1 год
  includeSubDomains: true,
  preload: true,
}));
```

## Типичные ошибки на интервью

- **"Authentication = Authorization"** — это разные концепции. Аутентификация отвечает на "кто ты?", авторизация — "что тебе можно?". Проверка JWT = аутентификация. Проверка роли/права на ресурс = авторизация. Многие системы проверяют аутентификацию, но забывают авторизацию (IDOR уязвимость).

- **"HTTPS шифрует данные в БД"** — HTTPS шифрует только трафик в сети (канал передачи). Данные в БД — не шифруются HTTPS. Для защиты данных at-rest нужно шифрование на уровне БД или приложения.

- **"Security Through Obscurity достаточна"** — скрытие URL или технологий не является защитой. Правильная авторизация на endpoint важнее его "секретности". Злоумышленник легко находит endpoints через brute force, перехват трафика или исходный код.

- **"CIA = Confidentiality, Integrity, Availability в контексте ЦРУ"** — в контексте security это CIA Triad: три фундаментальных свойства безопасности системы, не связанных с разведкой.

- **"Defense in Depth = много паролей"** — это принцип многоуровневой защиты: каждый слой (HTTPS → Auth → Authorization → Validation → Encoding) независимо защищает от разных классов атак.
