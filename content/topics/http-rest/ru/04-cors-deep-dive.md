<!-- verified: 2026-06-23, corrections: 0 -->
# CORS в деталях

## Откуда взялся CORS и зачем он нужен

CORS — это механизм браузера, а не HTTP-протокола. Чтобы понять зачем он нужен, нужно сначала понять **Same-Origin Policy (SOP)**.

### Same-Origin Policy

Браузер применяет SOP: JavaScript на странице `https://app.example.com` не может читать ответы от `https://api.other.com`. "Origin" определяется тремя компонентами:

```txt
https://app.example.com:443/path
│        │              │
│        │              └── Порт (если не указан — дефолтный: 443 для https, 80 для http)
│        └── Хост (включая поддомены)
└── Схема (протокол)

Примеры:
https://example.com     vs  https://example.com      — ОДИН origin
https://example.com     vs  http://example.com       — РАЗНЫЕ (схема)
https://example.com     vs  https://api.example.com  — РАЗНЫЕ (хост)
https://example.com     vs  https://example.com:8080 — РАЗНЫЕ (порт)
```

SOP защищает пользователей: без неё вредоносный сайт мог бы читать вашу почту на `mail.google.com`, делать запросы от вашего имени на `bank.com` и т.д. — просто загрузив JavaScript на своей странице.

### CORS как исключение из SOP

CORS (Cross-Origin Resource Sharing) — механизм, позволяющий серверу **явно разрешить** запросы с других origin'ов. Сервер говорит браузеру: "да, этому чужому origin можно читать мои ответы".

```txt
Без CORS:
  браузер → GET https://api.other.com/data   → ответ приходит
  браузер блокирует JavaScript от чтения ответа

С CORS (сервер разрешает):
  браузер → GET https://api.other.com/data   → ответ приходит
  Access-Control-Allow-Origin: https://app.example.com
  браузер даёт JavaScript прочитать ответ
```

Важно: **CORS не защищает сервер** — запрос физически отправляется и выполняется. CORS защищает браузер (клиента) от чтения чужих ответов. Именно поэтому curl не знает о CORS — это браузерная политика.

---

## Simple Requests vs Preflight

Браузер делит cross-origin запросы на два типа:

### Simple Requests (простые запросы)

Браузер отправляет запрос напрямую, добавляя `Origin` заголовок. Если сервер в ответе не разрешает этот origin — браузер блокирует JS от чтения ответа (но запрос уже выполнен).

Условия для simple request (все три должны выполняться):

```txt
Метод: GET, HEAD, или POST
Заголовки: только автоматически добавляемые браузером +
  Accept, Accept-Language, Content-Language,
  Content-Type (только: text/plain, application/x-www-form-urlencoded, multipart/form-data)
Нет кастомных заголовков (Authorization, X-Custom-Header и т.д.)
```

```http
GET /api/public-data HTTP/1.1
Host: api.other.com
Origin: https://app.example.com

─────────────────────────────────────
HTTP/1.1 200 OK
Access-Control-Allow-Origin: https://app.example.com
Content-Type: application/json

{ "data": "..." }
```

### Preflight Requests (предварительные запросы)

Для "не простых" запросов браузер сначала отправляет `OPTIONS`-запрос, спрашивая: "можно ли мне сделать такой запрос?". Только получив разрешение, отправляет настоящий запрос.

```txt
Браузер делает fetch("https://api.other.com/users", {
  method: "DELETE",
  headers: { "Authorization": "Bearer token" }
})

Шаг 1: Preflight OPTIONS
────────────────────────────────────────────────────────
OPTIONS /api/users HTTP/1.1
Host: api.other.com
Origin: https://app.example.com
Access-Control-Request-Method: DELETE
Access-Control-Request-Headers: Authorization

Шаг 2: Ответ сервера на preflight
────────────────────────────────────────────────────────
HTTP/1.1 204 No Content
Access-Control-Allow-Origin: https://app.example.com
Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE
Access-Control-Allow-Headers: Authorization, Content-Type
Access-Control-Max-Age: 86400

Шаг 3: Настоящий запрос (только если preflight прошёл)
────────────────────────────────────────────────────────
DELETE /api/users/42 HTTP/1.1
Host: api.other.com
Origin: https://app.example.com
Authorization: Bearer token

HTTP/1.1 204 No Content
Access-Control-Allow-Origin: https://app.example.com
```

Условия, триггерящие preflight:
```txt
- Метод: PUT, DELETE, PATCH, или любой нестандартный
- Кастомные заголовки: Authorization, X-Requested-With, и т.д.
- Content-Type: application/json (!)
- Запрос с credentials (cookies/HTTP auth) на другой origin
```

Практическое следствие: **большинство API-запросов с `Content-Type: application/json` или `Authorization` триггерят preflight**. Это значит двойное количество HTTP-запросов.

---

## CORS-заголовки: полный разбор

### Заголовки ответа (сервер → браузер)

**`Access-Control-Allow-Origin`**

```http
Access-Control-Allow-Origin: https://app.example.com   # Конкретный origin
Access-Control-Allow-Origin: *                          # Все origins
```

`*` запрещено при `credentials: "include"`. Сервер не может использовать wildcard и требовать credentials одновременно.

Если нужно разрешить несколько конкретных origins — нельзя перечислить через запятую. Нужно динамически проверять `Origin` запроса и отражать его в ответе:

```typescript
const ALLOWED_ORIGINS = new Set([
  "https://app.example.com",
  "https://admin.example.com",
]);

app.use((req, res, next) => {
  const origin = req.headers.origin;
  if (origin && ALLOWED_ORIGINS.has(origin)) {
    res.set("Access-Control-Allow-Origin", origin);
    res.set("Vary", "Origin"); // обязательно! кэши должны знать
  }
  next();
});
```

**`Access-Control-Allow-Methods`**

```http
Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
```

В preflight-ответе перечисляет разрешённые методы.

**`Access-Control-Allow-Headers`**

```http
Access-Control-Allow-Headers: Authorization, Content-Type, X-Request-ID
```

Разрешённые заголовки запроса. Если клиент запрашивает кастомный заголовок в `Access-Control-Request-Headers`, он должен быть в этом списке.

**`Access-Control-Expose-Headers`**

```http
Access-Control-Expose-Headers: X-Total-Count, X-Request-ID, ETag
```

По умолчанию JavaScript видит только базовые заголовки ответа (Content-Type, Cache-Control, Content-Language, Content-Length, Expires, Last-Modified, Pragma). Чтобы JS мог читать кастомные заголовки — их нужно явно перечислить. Типичный пример: пагинация через `X-Total-Count`.

**`Access-Control-Allow-Credentials`**

```http
Access-Control-Allow-Credentials: true
```

Разрешает отправку cookies, HTTP-аутентификации и TLS-сертификатов с запросом. Требует явного origin (не `*`) в `Access-Control-Allow-Origin`.

**`Access-Control-Max-Age`**

```http
Access-Control-Max-Age: 86400
```

Сколько секунд браузер кэширует результат preflight для данного URL + метод + заголовки. Без этого браузер делает OPTIONS перед каждым запросом. 86400 = 1 день (браузеры часто ограничивают максимум ~7200 секундами).

### Заголовки запроса (браузер → сервер)

```http
Origin: https://app.example.com                # Откуда запрос
Access-Control-Request-Method: DELETE          # Какой метод будет в настоящем запросе
Access-Control-Request-Headers: Authorization  # Какие кастомные заголовки
```

Эти заголовки добавляет браузер автоматически — не JavaScript-код.

---

## Credentials и CORS

Credentials в контексте CORS — это cookies, HTTP Basic/Digest аутентификация, и TLS client certificates.

По умолчанию cross-origin запросы НЕ отправляют credentials. Для включения нужно:

```typescript
// На клиенте (fetch):
const response = await fetch("https://api.other.com/data", {
  credentials: "include",  // отправлять cookies
});

// На клиенте (axios):
const response = await axios.get("https://api.other.com/data", {
  withCredentials: true,
});
```

И на сервере:
```http
Access-Control-Allow-Origin: https://app.example.com  # НЕ wildcard!
Access-Control-Allow-Credentials: true
```

Если сервер отвечает `Access-Control-Allow-Origin: *` при `credentials: "include"` — браузер заблокирует ответ с ошибкой.

```txt
Почему нельзя * + credentials:

* означает "любой сайт может читать ответ".
Credentials означает "запрос отправляет cookies пользователя".
Вместе это: "любой сайт может читать ответ, который включает
данные залогиненного пользователя" — очевидная уязвимость.
```

---

## Практический пример: Express с корректным CORS

```typescript
import express from "express";

const app = express();

const ALLOWED_ORIGINS = new Set([
  "https://app.example.com",
  "https://admin.example.com",
  // Для разработки:
  "http://localhost:3000",
  "http://localhost:5173",
]);

function handleCors(
  req: express.Request,
  res: express.Response,
  next: express.NextFunction
): void {
  const origin = req.headers.origin;

  if (origin && ALLOWED_ORIGINS.has(origin)) {
    res.set("Access-Control-Allow-Origin", origin);
    res.set("Vary", "Origin"); // критически важно для корректного кэширования
    res.set("Access-Control-Allow-Credentials", "true");
  }

  // Preflight
  if (req.method === "OPTIONS") {
    res.set("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS");
    res.set("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Request-ID");
    res.set("Access-Control-Max-Age", "86400");
    res.set("Access-Control-Expose-Headers", "X-Total-Count, X-Request-ID");
    return res.sendStatus(204);
  }

  // Для не-preflight ответов тоже нужны expose-заголовки
  res.set("Access-Control-Expose-Headers", "X-Total-Count, X-Request-ID");

  next();
}

app.use(handleCors);

// Или использовать пакет cors:
import cors from "cors";

app.use(cors({
  origin: (origin, callback) => {
    if (!origin || ALLOWED_ORIGINS.has(origin)) {
      callback(null, true);
    } else {
      callback(new Error(`Origin ${origin} not allowed`));
    }
  },
  credentials: true,
  methods: ["GET", "POST", "PUT", "PATCH", "DELETE"],
  allowedHeaders: ["Authorization", "Content-Type", "X-Request-ID"],
  exposedHeaders: ["X-Total-Count", "X-Request-ID"],
  maxAge: 86400,
}));
```

---

## Когда CORS не при чём — частые заблуждения

### "CORS-ошибка — это серверная проблема безопасности"

Нет. CORS-ошибка означает: **браузер** отказался передать ответ JavaScript-коду. Сам запрос дошёл до сервера и был выполнен.

```txt
Атака CSRF (Cross-Site Request Forgery):
  - Пользователь залогинен на bank.com
  - Заходит на evil.com
  - evil.com через HTML-форму делает POST https://bank.com/transfer
  - Браузер отправляет cookies bank.com автоматически!
  - CORS здесь не помогает (HTML-формы не подчиняются CORS)
  - Защита: CSRF-токены, SameSite cookies, проверка Origin/Referer
```

CORS защищает от чтения ответа, но не от выполнения запроса.

### "curl показывает ошибку CORS"

Невозможно. curl — не браузер, у него нет SOP. CORS — исключительно браузерный механизм. Если curl получает ответ — запрос работает; вопрос только в том, разрешит ли браузер JavaScript читать этот ответ.

### "Поставлю `Access-Control-Allow-Origin: *` — всё заработает"

Заработает, но:
- С credentials (cookies) — не заработает
- Это "разрешаю всем читать мой API" — нормально для публичных API, проблема для приватных

### "CORS не нужен если API и фронтенд на одном домене"

Верно, но с оговорками:
```txt
Один origin:
  https://example.com + https://example.com/api — ОДИН origin
  https://app.example.com + https://api.example.com — РАЗНЫЕ (поддомен)

Поддомен ≠ тот же origin.
Для api.example.com ↔ app.example.com — нужен CORS.
```

---

## Private Network Access (новое ограничение Chrome)

С Chrome 94+ появилось ещё одно ограничение: запросы с публичного origin на приватную сеть (localhost, 192.168.x.x, 10.x.x.x) требуют дополнительного разрешения.

```http
# Браузер добавляет в preflight:
Access-Control-Request-Private-Network: true

# Сервер (localhost) должен ответить:
Access-Control-Allow-Private-Network: true
```

Актуально для: локальных приложений, IoT-устройств, инструментов разработки, которые работают по localhost но к ним обращаются с публичных сайтов.

---

## Диаграмма: полный CORS-flow для API-запроса

```txt
JavaScript код:
fetch("https://api.other.com/users/42", {
  method: "DELETE",
  headers: { "Authorization": "Bearer token" }
})

Браузер определяет тип запроса:
  ├─ Simple? (GET/HEAD/POST + базовые заголовки)
  │    → Отправить напрямую с Origin
  │
  └─ Non-simple (DELETE / Authorization заголовок)
       → Preflight

Preflight:
OPTIONS https://api.other.com/users/42
Origin: https://app.example.com
Access-Control-Request-Method: DELETE
Access-Control-Request-Headers: Authorization
       │
       ▼
Сервер api.other.com:
  Проверяет Origin → в белом списке? ──── Нет ──→ 403/пустой ответ
       │ Да                                        │
       ▼                                           │
  HTTP/1.1 204 No Content                         │
  Access-Control-Allow-Origin: https://app.example.com
  Access-Control-Allow-Methods: DELETE             │
  Access-Control-Allow-Headers: Authorization      │
  Access-Control-Max-Age: 86400                    │
       │                                           │
       ▼                                           │
Браузер:                                           │
  Preflight прошёл? ──── Нет (403/нет ACAO) ─────→ CORS Error
       │ Да                                        (JS не видит ответ)
       ▼
Настоящий запрос:
DELETE https://api.other.com/users/42
Authorization: Bearer token
Origin: https://app.example.com
       │
       ▼
Сервер:
  HTTP/1.1 204 No Content
  Access-Control-Allow-Origin: https://app.example.com
       │
       ▼
Браузер:
  ACAO совпадает с Origin? ──── Нет ──→ CORS Error
       │ Да
       ▼
  JavaScript получает ответ ✅
```

---

## Типичные ошибки на интервью

- **"CORS — это серверная защита от атак"** — нет. CORS — это браузерная политика, позволяющая серверу **ослабить** Same-Origin Policy. Сервер защищается другими механизмами (CSRF-токены, SameSite cookies, аутентификация). CORS только контролирует, что браузер передаёт JavaScript.

- **"curl тестирует CORS"** — нет. curl не браузер, у него нет SOP. Успешный curl-запрос не означает, что браузер разрешит читать ответ. Для тестирования CORS — только браузер.

- **"Можно использовать `*` и `credentials: true` одновременно"** — нет, браузер заблокирует с ошибкой. При credentials нужен конкретный origin.

- **"CORS-ошибка — запрос не дошёл до сервера"** — обычно неверно. При simple request — запрос выполняется, браузер блокирует чтение ответа. При preflight — настоящий запрос не отправляется, но OPTIONS дошёл до сервера.

- **"Добавлю заголовок `Origin` в запрос из Node.js — обойду CORS"** — CORS проверяется браузером, не сервером. Node.js (серверный код) не подчиняется CORS. Только браузерный JavaScript подчиняется SOP/CORS.

- **"Поддомен — тот же origin"** — нет. `app.example.com` и `api.example.com` — разные origins. Для cross-subdomain CORS нужны заголовки на сервере.

- **"`Vary: Origin` зачем?"** — без этого заголовка кэш (CDN, прокси) может вернуть ответ с `Access-Control-Allow-Origin: https://a.com` клиенту с origin `https://b.com`. `Vary: Origin` говорит кэшу хранить разные версии ответа для разных origins.
