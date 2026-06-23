<!-- verified: 2026-06-23, corrections: 0 -->
# Кэширование и заголовки

## Зачем нужен HTTP-кэш и как он устроен

Кэширование HTTP — это сохранение ответа и его повторное использование без обращения к серверу. Выгода двойная: клиент получает ответ быстрее, сервер разгружается.

Кэш бывает нескольких уровней:

```txt
Клиент (браузер)
    │
    │  ← Private cache: хранит ответы только для этого пользователя
    │    (сессионные данные, профиль, корзина)
    │
CDN / Reverse Proxy (Cloudflare, nginx, Varnish)
    │
    │  ← Shared cache: хранит ответы для всех пользователей
    │    (статика, публичные API-ответы)
    │
Origin Server (backend)
```

Вся логика кэширования управляется заголовками. Главный из них — `Cache-Control`.

---

## Cache-Control — полный разбор директив

`Cache-Control` — это заголовок, который может стоять как в **ответе** (сервер говорит "вот правила для этого ресурса"), так и в **запросе** (клиент говорит "вот как я хочу использовать кэш").

### Директивы ответа (сервер → клиент/CDN)

```http
Cache-Control: max-age=3600
```
Кэшировать ресурс 3600 секунд (1 час) с момента получения. По истечении — стал "устаревшим" (stale).

```http
Cache-Control: s-maxage=86400
```
То же что `max-age`, но только для **shared-кэшей** (CDN, прокси). Перекрывает `max-age` для CDN. Браузер использует `max-age`.

```http
Cache-Control: no-cache
```
Кэш хранить **можно**, но перед использованием нужно **валидировать** с сервером (conditional request). Если сервер говорит "не изменилось" → 304, кэш используется. НЕ означает "не кэшировать".

```http
Cache-Control: no-store
```
Не хранить вообще. Никакого кэша — ни в браузере, ни в CDN. Для чувствительных данных (банковские операции, медицинские данные).

```http
Cache-Control: private
```
Кэшировать только в приватном кэше (браузере). CDN и прокси не должны кэшировать. Для персонализированных ответов.

```http
Cache-Control: public
```
Можно кэшировать в shared-кэше (CDN). Обычно сочетается с `max-age`. Для статики и публичного контента.

```http
Cache-Control: must-revalidate
```
Если ресурс устарел (`max-age` истёк), нельзя использовать stale-версию — только валидировать с сервером. Без этой директивы некоторые кэши могут отдавать устаревшее.

```http
Cache-Control: immutable
```
Ресурс никогда не изменится — не нужно проверять свежесть даже если `max-age` истёк. Используется для версионированных ассетов (`main.abc123.js`).

```http
Cache-Control: stale-while-revalidate=60
```
Отдавать устаревший кэш до 60 секунд пока в фоне идёт обновление. Повышает perceived performance: пользователь не ждёт, обновление происходит асинхронно.

```http
Cache-Control: stale-if-error=3600
```
Если сервер недоступен (5xx, timeout), использовать устаревший кэш до 3600 секунд. Защита от кратковременных сбоев.

### Комбинации директив

```http
# Публичная статика — кэшировать везде на год:
Cache-Control: public, max-age=31536000, immutable

# Приватные данные пользователя — только браузер, 5 минут:
Cache-Control: private, max-age=300

# Динамические данные — кэшировать в CDN на минуту, в браузере валидировать:
Cache-Control: public, s-maxage=60, no-cache

# Не кэшировать вообще (персональные/секретные данные):
Cache-Control: no-store

# Агрессивная freshness с защитой от деградации:
Cache-Control: public, max-age=3600, stale-while-revalidate=60, stale-if-error=86400
```

### Директивы запроса (клиент → сервер)

Клиент тоже может управлять кэшом через `Cache-Control` в запросе:

```http
Cache-Control: no-cache    # Игнорировать кэш, получить свежий ответ
Cache-Control: no-store    # Не сохранять ответ
Cache-Control: max-age=0   # Принять кэш только если он свежее 0 секунд (= всегда валидировать)
Cache-Control: max-stale=60 # Принять кэш даже если он устарел до 60 секунд
```

---

## Условные запросы (Conditional Requests)

Когда кэш устарел, клиент не обязан загружать ресурс заново — он может спросить сервер "а ресурс изменился?". Это и есть conditional request. Две механики:

### ETag (Entity Tag)

Сервер возвращает уникальный идентификатор версии ресурса. При следующем запросе клиент отправляет его обратно.

```txt
Запрос 1: клиент не имеет кэша
─────────────────────────────────────────────────────
GET /api/users/42 HTTP/1.1

HTTP/1.1 200 OK
ETag: "v3-abc123"
Cache-Control: max-age=300

{ "id": 42, "name": "Alice" }

Запрос 2: кэш устарел (через 5 минут), клиент валидирует
─────────────────────────────────────────────────────
GET /api/users/42 HTTP/1.1
If-None-Match: "v3-abc123"

HTTP/1.1 304 Not Modified
ETag: "v3-abc123"
(тело не передаётся — экономия трафика)

Запрос 3: ресурс изменился
─────────────────────────────────────────────────────
GET /api/users/42 HTTP/1.1
If-None-Match: "v3-abc123"

HTTP/1.1 200 OK
ETag: "v4-def456"
Cache-Control: max-age=300

{ "id": 42, "name": "Alice Updated" }
```

ETag бывает двух видов:
```http
ETag: "abc123"    # Strong ETag — байт-в-байт одинаковый контент
ETag: W/"abc123"  # Weak ETag — семантически эквивалентный контент
                  # (можно добавить whitespace, порядок полей JSON)
```

### Last-Modified

Альтернатива ETag на основе времени:

```http
# Ответ сервера:
Last-Modified: Mon, 23 Jun 2025 10:00:00 GMT

# Следующий запрос клиента:
If-Modified-Since: Mon, 23 Jun 2025 10:00:00 GMT

# Ответ если не изменился:
HTTP/1.1 304 Not Modified
```

**ETag лучше Last-Modified** в большинстве случаев:
- Точнее: файл может пересохраниться с тем же содержимым, но другим временем
- Нет проблем с временными зонами и точностью до секунды
- Можно хранить произвольный "fingerprint" (хэш, версия)

### If-Match для PUT/PATCH (оптимистичная блокировка)

```http
# Клиент читает ресурс, получает ETag:
GET /api/documents/5
→ ETag: "v2"

# Клиент обновляет, требуя что версия не изменилась:
PUT /api/documents/5
If-Match: "v2"
{ "content": "..." }

# Если кто-то уже изменил документ:
HTTP/1.1 412 Precondition Failed

# Если версия совпадает:
HTTP/1.1 200 OK
ETag: "v3"
```

---

## Уровни кэша: браузер vs CDN vs прокси

```txt
┌──────────────────────────────────────────────────────────────┐
│                         Браузер                              │
│  Хранит: GET-ответы для текущего пользователя               │
│  Объём: несколько сотен MB (настраивается пользователем)     │
│  Ключ: URL + Vary                                            │
│  Управление: Cache-Control: private или public              │
└──────────────────────────────────────────────────────────────┘
           ↕ запросы проходят через (при cache miss)
┌──────────────────────────────────────────────────────────────┐
│                 CDN (Cloudflare, CloudFront, Fastly)         │
│  Хранит: public ответы для всех пользователей               │
│  Объём: практически неограничен                              │
│  Ключ: URL + Vary + часто кастомные ключи                   │
│  Управление: Cache-Control: public, s-maxage=N              │
│  Плюс: близко к пользователю (edge nodes по всему миру)     │
└──────────────────────────────────────────────────────────────┘
           ↕ при cache miss идёт до origin
┌──────────────────────────────────────────────────────────────┐
│            Reverse Proxy / Load Balancer (nginx, Varnish)   │
│  Хранит: shared кэш внутри инфраструктуры                   │
│  Разгружает origin от повторяющихся запросов                │
└──────────────────────────────────────────────────────────────┘
           ↕ при cache miss
┌──────────────────────────────────────────────────────────────┐
│                      Origin Server                           │
└──────────────────────────────────────────────────────────────┘
```

**Ключевое различие:**
- `Cache-Control: private` → кэшируется только в браузере, CDN пропускает
- `Cache-Control: public` → кэшируется и в браузере, и в CDN
- `Cache-Control: s-maxage=3600` → CDN кэширует 1 час, браузер — по `max-age`

---

## Заголовок Vary

`Vary` говорит кэшу: "один и тот же URL может возвращать разный контент в зависимости от этих заголовков запроса". Кэш должен хранить отдельные копии для каждой комбинации.

```http
# Сервер поддерживает JSON и XML:
Vary: Accept

# Запрос JSON — кэшируется отдельно:
GET /api/users
Accept: application/json
→ сохраняется копия "JSON"

# Запрос XML — кэшируется отдельно:
GET /api/users
Accept: application/xml
→ сохраняется копия "XML"
```

Другие применения:
```http
Vary: Accept-Encoding    # gzip vs br vs identity — почти всегда нужен
Vary: Accept-Language    # локализованные ответы
Vary: Authorization      # разный контент для разных пользователей
                         # (если Authorization в Vary — CDN не кэширует,
                         #  т.к. каждый пользователь уникален)
```

**Осторожно с `Vary: Authorization`**: если поставить его на ответы с `Cache-Control: public`, CDN будет хранить отдельную копию для каждого уникального токена — фактически ломая кэш.

---

## Инвалидация кэша

"There are only two hard things in Computer Science: cache invalidation and naming things." — Phil Karlton

Когда ресурс изменился на сервере, кэш об этом не знает. Стратегии:

### 1. Версионирование URL (cache busting)

Самый надёжный способ — менять URL при изменении контента:

```txt
Первая версия:   /static/main.js?v=1   или   /static/main.abc123.js
После изменения: /static/main.js?v=2   или   /static/main.def456.js
```

Браузер видит другой URL → делает новый запрос. Старый URL с максимальным `max-age=31536000` отдаётся без запросов к серверу.

Это стандартный подход для ассетов (JS, CSS, изображения).

### 2. Программная инвалидация CDN

CDN предоставляют API для purge:

```typescript
// Cloudflare: очистить кэш по тегу
await fetch("https://api.cloudflare.com/client/v4/zones/{id}/purge_cache", {
  method: "POST",
  headers: { "Authorization": `Bearer ${CF_TOKEN}` },
  body: JSON.stringify({ tags: ["user-42"] }),
});

// AWS CloudFront: создать invalidation
await cloudfrontClient.send(new CreateInvalidationCommand({
  DistributionId: DISTRIBUTION_ID,
  InvalidationBatch: {
    Paths: { Quantity: 1, Items: ["/api/users/42"] },
    CallerReference: Date.now().toString(),
  },
}));
```

### 3. Short TTL + stale-while-revalidate

Вместо явной инвалидации — короткий TTL:

```http
Cache-Control: public, max-age=60, stale-while-revalidate=30
```

Ресурс считается свежим 60 секунд. Следующие 30 секунд CDN отдаёт stale-версию и параллельно обновляет кэш. Максимальная несвежесть — 90 секунд. Подходит для контента, где допустима небольшая задержка обновления.

---

## Практический пример: Express + кэш-стратегии

```typescript
import express from "express";
import crypto from "crypto";

const app = express();

// Статика — кэшировать навсегда (URL меняется при изменении файла)
app.use("/static", express.static("public", {
  maxAge: "1y",
  immutable: true,
}));

// Публичные данные — CDN кэширует 1 минуту, браузер валидирует
app.get("/api/articles", async (_req, res) => {
  const articles = await db.articles.findAll({ where: { published: true } });
  const etag = crypto
    .createHash("md5")
    .update(JSON.stringify(articles))
    .digest("hex");

  res.set({
    "Cache-Control": "public, s-maxage=60, no-cache",
    "ETag": `"${etag}"`,
  });

  // Conditional request: если клиент прислал тот же ETag — 304
  if (req.headers["if-none-match"] === `"${etag}"`) {
    return res.sendStatus(304);
  }

  res.json(articles);
});

// Приватные данные пользователя — только браузер, 5 минут
app.get("/api/users/me", requireAuth, async (req, res) => {
  const user = await db.users.findById(req.user.id);

  res.set("Cache-Control", "private, max-age=300");
  res.json(user);
});

// Чувствительные данные — не кэшировать
app.get("/api/payments/:id", requireAuth, async (req, res) => {
  const payment = await db.payments.findById(req.params.id);

  res.set("Cache-Control", "no-store");
  res.json(payment);
});

// Условный PUT с оптимистичной блокировкой
app.put("/api/documents/:id", requireAuth, async (req, res) => {
  const ifMatch = req.headers["if-match"];
  const doc = await db.documents.findById(req.params.id);

  if (!doc) return res.sendStatus(404);

  if (ifMatch && ifMatch !== `"${doc.version}"`) {
    return res.sendStatus(412); // Precondition Failed
  }

  const updated = await db.documents.update(req.params.id, req.body);
  const newEtag = `"${updated.version}"`;

  res.set("ETag", newEtag);
  res.json(updated);
});
```

---

## Pragma: no-cache — легаси

`Pragma` — устаревший HTTP/1.0 заголовок:

```http
Pragma: no-cache
```

Эквивалентен `Cache-Control: no-cache`, но только для HTTP/1.0-кэшей. Современные серверы должны возвращать `Cache-Control`, но для совместимости с очень старыми прокси иногда добавляют оба. На практике `Pragma` можно игнорировать.

---

## Flows кэширования — полная картина

```txt
Клиент делает GET /api/articles

           ┌─────────────────────┐
           │  Есть в кэше?       │
           └─────────────────────┘
                    │
          ┌─────────┴─────────┐
          │ Нет               │ Да
          ▼                   ▼
   Запрос к серверу    ┌──────────────┐
          │            │  Свежий?     │
          │            └──────────────┘
          │                   │
          │           ┌───────┴───────┐
          │           │ Да            │ Нет
          │           ▼               ▼
          │     Вернуть кэш   Conditional Request
          │                   If-None-Match / If-Modified-Since
          │                           │
          │                   ┌───────┴───────┐
          │                   │ 304           │ 200
          │                   │ Not Modified  │ OK
          │                   ▼               ▼
          │             Обновить TTL,   Сохранить новый
          │             вернуть кэш     ответ в кэш
          │
          ▼
    Сохранить в кэш
    (если Cache-Control разрешает)
```

---

## Типичные ошибки на интервью

- **"`no-cache` = не кэшировать"** — самая частая ошибка. `no-cache` означает: кэшировать можно, но всегда валидировать перед использованием. `no-store` означает не кэшировать совсем. Это разные вещи с разными performance-характеристиками.

- **"ETag — это хэш файла"** — не обязательно. ETag может быть хэшем, версией из БД, timestamp или любым строковым идентификатором, уникально представляющим версию ресурса. Сервер сам определяет формат.

- **"Cache-Control: public делает кэш доступным всем пользователям, включая их данные"** — да, именно поэтому на персонализированные ответы нужно ставить `private`. `public` — только для данных, одинаковых для всех пользователей.

- **"304 означает ошибку"** — нет. 304 Not Modified — это успешный ответ, означающий "кэш актуален, используй его". Экономит трафик и уменьшает нагрузку на сервер.

- **"`Vary: *` — проблема?"** — да. `Vary: *` говорит кэшу "каждый запрос уникален" — фактически отключает кэш. Никогда не используйте, если не понимаете последствия.

- **"Инвалидировать кэш CDN мгновенно"** — почти невозможно без purge API. Именно поэтому для критически важных обновлений (hotfix, security) нужно либо использовать purge CDN API, либо менять URL (cache busting), либо иметь очень короткий TTL с `stale-while-revalidate`.

- **"stale-while-revalidate нарушает консистентность"** — осознанный компромисс. Если пользователь может получить данные 90-секундной давности — это нормально для большинства случаев. Для банковских операций или инвентаря — нет.
