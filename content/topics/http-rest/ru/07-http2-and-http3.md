<!-- verified: 2026-06-23, corrections: 0 -->
# HTTP/2 и HTTP/3

## Почему понадобился HTTP/2

HTTP/1.1 появился в 1997 году. Веб тогда был набором текстовых страниц с несколькими изображениями. Современная страница — это 100+ ресурсов: JS-бандлы, CSS, шрифты, изображения, API-запросы. HTTP/1.1 под такую нагрузку не проектировался.

### Проблемы HTTP/1.1

**Head-of-line blocking (HoL блокировка)**

```txt
HTTP/1.1 — одно соединение, один запрос за раз:

Клиент: [GET /main.js] ──────────────────────── [GET /style.css]
Сервер:               [..response main.js..]    [..response style.css..]

Если main.js большой — style.css ждёт, даже если он уже готов.
Это и есть head-of-line blocking.
```

Браузеры обходили это открывая **6 параллельных TCP-соединений** на домен. Но каждое соединение — отдельный TCP + TLS handshake.

**Текстовые заголовки без сжатия**

Каждый запрос несёт полные заголовки:
```http
Host: api.example.com
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36...
Accept: application/json
Accept-Language: en-US,en;q=0.9,ru;q=0.8
Accept-Encoding: gzip, deflate, br
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Cookie: sessionId=abc123; _ga=GA1.2.xxx; _gid=GA1.2.yyy
```

Это 500–2000 байт на каждый запрос, и 95%+ заголовков одинаковы между запросами.

**Нет возможности приоритизации**

Браузер не мог сказать серверу "CSS важнее изображений, выдай сначала его".

---

## HTTP/2: бинарный, мультиплексный

HTTP/2 (2015, RFC 7540) решает эти проблемы сохраняя семантику HTTP — те же методы, статусы, заголовки. Меняется только **транспорт**.

### Бинарный фрейминг

HTTP/1.1 — текстовый протокол. HTTP/2 — бинарный:

```txt
HTTP/1.1:
  GET /users HTTP/1.1\r\n
  Host: api.example.com\r\n
  \r\n

HTTP/2 (упрощённо):
  [Length: 3 байта][Type: 1 байт][Flags: 1 байт][Stream ID: 4 байта][Payload: N байт]
       ↑ фиксированный 9-байтовый заголовок фрейма
```

Типы фреймов:
```txt
HEADERS    — заголовки запроса/ответа
DATA       — тело запроса/ответа
SETTINGS   — настройки соединения
PING       — keepalive
GOAWAY     — закрытие соединения
RST_STREAM — сброс конкретного стрима
WINDOW_UPDATE — управление потоком
PUSH_PROMISE  — server push
```

### Мультиплексирование (ключевая фича)

Несколько запросов одновременно по **одному TCP-соединению** через **streams (стримы)**:

```txt
HTTP/1.1 (6 соединений):
  TCP conn 1: [GET /main.js      ──────────────────]
  TCP conn 2: [GET /vendor.js    ──────────────────]
  TCP conn 3: [GET /style.css    ──────]
  TCP conn 4: [GET /logo.png     ───]
  TCP conn 5: [GET /api/user     ──]
  TCP conn 6: [GET /api/config   ────]

HTTP/2 (1 соединение, N стримов):
  TCP conn:
    Stream 1: [GET /main.js   ] ──────[DATA]──────────────────
    Stream 3: [GET /vendor.js ] ──────[DATA]──────────────────
    Stream 5: [GET /style.css ] ────[DATA]──────
    Stream 7: [GET /logo.png  ] ───[DATA]
    Stream 9: [GET /api/user  ] ──[DATA]
    Stream 11:[GET /api/config] ────[DATA]
              ↑ все перемежаются по фреймам в одном TCP-потоке
```

Стримы идентифицируются **нечётными** номерами (клиентские) или **чётными** (серверные push). Независимы друг от друга — один медленный стрим не блокирует остальные.

### HPACK — сжатие заголовков

HTTP/2 сжимает заголовки с помощью HPACK (RFC 7541):

```txt
Статическая таблица (61 запись):
  :method = GET          → index 2
  :status = 200          → index 8
  content-type = application/json → + имя с литеральным значением

Динамическая таблица:
  Первый запрос: Authorization: Bearer eyJ... → добавляется в таблицу
  Второй запрос: Authorization: Bearer eyJ... → просто индекс (1-4 байта вместо 500+)

Результат: заголовки сжимаются на 85–95% начиная со второго запроса.
```

### Приоритизация стримов

Клиент может указать приоритет стрима (0–256) и зависимость между стримами:

```txt
Дерево приоритетов:
  Стрим 1 (CSS, приоритет 220)
    └── Стрим 3 (JS, приоритет 180)
          └── Стрим 5 (изображение, приоритет 60)

Сервер отдаёт ресурсы CSS → JS → изображение.
```

На практике приоритизация в HTTP/2 реализована плохо в большинстве серверов и браузеров, но концептуально важна.

### Server Push (и почему он не взлетел)

Server Push: сервер отправляет ресурс клиенту до того, как тот его запросил.

```txt
Клиент: GET /index.html

Сервер: [HTML response]
        [PUSH_PROMISE: /style.css]  ← сервер говорит "я пушну это"
        [DATA для /style.css]       ← отправляет без запроса
        [PUSH_PROMISE: /main.js]
        [DATA для /main.js]

Клиент получает CSS и JS вместе с HTML, без дополнительных запросов.
```

Почему не взлетел:
```txt
1. Браузеры кэшируют ресурсы. Сервер не знает что уже в кэше клиента.
   Push некэшированных ресурсов → трата bandwidth.

2. Сложно правильно реализовать: как решить что пушить?

3. 103 Early Hints решает ту же задачу проще:
   HTTP/1.1 103 Early Hints
   Link: </style.css>; rel=preload; as=style

4. Chrome удалил поддержку Server Push в 2022 году.
   HTTP/3 исключил его из спецификации.
```

### TLS в HTTP/2

Формально HTTP/2 поддерживает работу без TLS (h2c — cleartext). На практике все браузеры требуют TLS для HTTP/2. Поэтому HTTP/2 = HTTPS.

---

## HTTP/2 на практике (Node.js)

Express не поддерживает HTTP/2 нативно (он завязан на Node.js `http` module). Варианты:

**Вариант 1 — Nginx/Cloudflare как TLS-терминатор (рекомендуется)**

```txt
Браузер ←── HTTP/2 ──→ Nginx ←── HTTP/1.1 ──→ Node.js

Nginx обрабатывает HTTP/2 → проксирует на Node.js по HTTP/1.1.
Node.js не знает о HTTP/2, всё работает.
```

```nginx
server {
    listen 443 ssl http2;
    ssl_certificate /etc/ssl/cert.pem;
    ssl_certificate_key /etc/ssl/key.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
    }
}
```

**Вариант 2 — Нативный Node.js http2 модуль**

```typescript
import http2 from "http2";
import fs from "fs";

const server = http2.createSecureServer({
  key: fs.readFileSync("key.pem"),
  cert: fs.readFileSync("cert.pem"),
});

server.on("stream", (stream, headers) => {
  const method = headers[":method"];
  const path = headers[":path"];

  stream.respond({
    "content-type": "application/json",
    ":status": 200,
  });

  stream.end(JSON.stringify({ method, path }));
});

server.listen(3000);
```

**Вариант 3 — Fastify** (нативная поддержка HTTP/2):

```typescript
import Fastify from "fastify";
import fs from "fs";

const fastify = Fastify({
  http2: true,
  https: {
    key: fs.readFileSync("key.pem"),
    cert: fs.readFileSync("cert.pem"),
  },
});

fastify.get("/api/users", async () => {
  return { users: [] };
});

await fastify.listen({ port: 3000 });
```

---

## HTTP/3: QUIC вместо TCP

HTTP/3 (2022, RFC 9114) — следующий шаг. Проблема HTTP/2 оказалась в том, что он решил HoL-блокировку на уровне HTTP, но не устранил её на уровне TCP.

### HoL-блокировка в HTTP/2

```txt
HTTP/2 поверх TCP:

  Фреймы стримов 1, 3, 5 перемежаются в одном TCP-потоке:
  [S1][S3][S5][S1][S3][S5][S1]...

  Если TCP-пакет из середины потерян — ВСЕ стримы ждут его повторной передачи.
  TCP не знает о стримах HTTP/2. Он гарантирует порядок байт.

  Результат: потеря 1 пакета блокирует все 50 параллельных стримов.
  На мобильных сетях с ~2% потерей пакетов — ощутимо.
```

### QUIC — UDP + надёжность

QUIC (Quick UDP Internet Connections) — новый транспортный протокол поверх UDP, разработанный Google, стандартизированный IETF:

```txt
HTTP/1.1, HTTP/2:
┌──────┐
│ HTTP │
├──────┤
│ TLS  │
├──────┤
│ TCP  │  ← надёжность, порядок
├──────┤
│ IP   │
└──────┘

HTTP/3:
┌──────────────┐
│ HTTP/3       │
├──────────────┤
│ QUIC         │  ← надёжность + TLS + управление потоком
│ (UDP-based)  │
├──────────────┤
│ IP           │
└──────────────┘
```

QUIC реализует надёжную доставку, но на **уровне стримов независимо**. Потеря пакета одного стрима не блокирует другие.

### 0-RTT соединение

HTTP/1.1 + TLS 1.2: 3 RTT до первого байта данных:
```txt
TCP: SYN → SYN-ACK → ACK              (1 RTT)
TLS: ClientHello → ServerHello → ...  (1-2 RTT)
HTTP: GET → response                   (1 RTT)
                                 Итого: 3-4 RTT
```

HTTP/3 + QUIC + TLS 1.3: 1 RTT, при повторном подключении — 0-RTT:
```txt
Первое подключение:
  QUIC Initial (содержит TLS ClientHello) → QUIC Handshake (TLS)
  HTTP GET → response
                                       Итого: 1 RTT

Повторное подключение (0-RTT):
  QUIC Initial + TLS + HTTP GET → response
                                       Итого: 0 RTT (!)
```

0-RTT работает потому что QUIC запоминает параметры соединения с предыдущей сессии.

### Connection Migration

```txt
HTTP/1.1 / HTTP/2 (TCP):
  Смена IP (WiFi → 4G) = разрыв TCP-соединения = переподключение.
  Активные запросы теряются.

HTTP/3 (QUIC):
  Соединение идентифицируется Connection ID, не IP:портом.
  WiFi → 4G → Connection ID сохраняется → соединение продолжается.
  Загрузка файла не прерывается при смене сети.
```

Это критично для мобильных пользователей и для IoT.

---

## Сравнение версий HTTP

```txt
┌───────────────────┬──────────────┬──────────────┬──────────────┐
│                   │ HTTP/1.1     │ HTTP/2       │ HTTP/3       │
├───────────────────┼──────────────┼──────────────┼──────────────┤
│ Транспорт         │ TCP          │ TCP          │ UDP (QUIC)   │
│ TLS               │ Опционально  │ Де-факто обяз│ Обязательно  │
│ Мультиплексинг    │ ❌ 6 соед.   │ ✅ 1 соед.   │ ✅ 1 соед.   │
│ HoL (HTTP уровень)│ ❌ Есть      │ ✅ Нет       │ ✅ Нет       │
│ HoL (TCP уровень) │ ❌ Есть      │ ❌ Есть      │ ✅ Нет (QUIC)│
│ Сжатие заголовков │ ❌ Нет       │ ✅ HPACK     │ ✅ QPACK     │
│ 0-RTT             │ ❌ 3+ RTT    │ ❌ 2+ RTT    │ ✅ 0-1 RTT   │
│ Connection migr.  │ ❌ Нет       │ ❌ Нет       │ ✅ Есть      │
│ Server Push       │ ❌ Нет       │ ✅ Есть*     │ ❌ Удалён    │
│ Поддержка (2024)  │ 100%         │ ~98%         │ ~85%         │
└───────────────────┴──────────────┴──────────────┴──────────────┘
* Server Push удалён из Chrome, мало где реализован корректно
```

---

## Что меняется для разработчика

### Не меняется

- HTTP-методы (GET, POST, PUT, DELETE…)
- Статус-коды (200, 404, 500…)
- Заголовки (Cache-Control, Authorization, Content-Type…)
- REST-архитектура API

Fetch API, axios, node-fetch — работают с HTTP/2 и HTTP/3 прозрачно. Код не меняется.

### Меняется подход к оптимизации

```txt
HTTP/1.1 оптимизации, которые во HTTP/2 НЕ нужны:
  ❌ Domain sharding (несколько CDN-доменов для обхода лимита 6 соединений)
  ❌ CSS/JS спрайты (объединение ресурсов в один файл ради меньшего числа запросов)
  ❌ Inline CSS (встраивание стилей чтобы сэкономить запрос)

HTTP/2 оптимизации:
  ✅ Много маленьких файлов ≈ один большой (мультиплексинг делает их одинаково эффективными)
  ✅ Granular caching (маленькие файлы кэшируются независимо — изменение одного не инвалидирует всё)
  ✅ 103 Early Hints вместо Server Push
```

### Выявление версии HTTP

```typescript
// Node.js: определить версию в middleware
app.use((req, res, next) => {
  // В Express + Nginx прокси — не доступно
  // В нативном http2:
  const httpVersion = req.httpVersion; // "2.0" или "1.1"
  next();
});

// В браузере: через Performance API
const entries = performance.getEntriesByType("resource");
entries.forEach(entry => {
  console.log(entry.name, (entry as PerformanceResourceTiming).nextHopProtocol);
  // "h2" = HTTP/2, "h3" = HTTP/3, "http/1.1" = HTTP/1.1
});
```

### HTTPS обязателен

HTTP/2 де-факто требует TLS (все браузеры). HTTP/3 требует TLS обязательно (QUIC встраивает TLS 1.3).

Для разработки — mkcert для локальных сертификатов:
```bash
mkcert -install
mkcert localhost 127.0.0.1
# Создаёт localhost.pem и localhost-key.pem — доверенные локально
```

### Настройка Nginx для HTTP/3

```nginx
server {
    listen 443 ssl;
    listen 443 quic reuseport;      # HTTP/3
    http2 on;                        # HTTP/2

    ssl_certificate cert.pem;
    ssl_certificate_key key.pem;
    ssl_protocols TLSv1.3;           # QUIC требует TLS 1.3

    add_header Alt-Svc 'h3=":443"; ma=86400';  # Сообщаем браузеру о HTTP/3

    location / {
        proxy_pass http://localhost:3000;
    }
}
```

`Alt-Svc` заголовок: сервер сообщает браузеру "я поддерживаю HTTP/3 на порту 443". Браузер при следующем подключении попробует QUIC.

---

## Диаграмма: почему HTTP/3 быстрее на плохих сетях

```txt
HTTP/2 при 2% потере пакетов:

Время →
[S1 frame][S3 frame][S5 frame][S1 frame][X LOST ][S1 frame]
                                                    ↑
                              Все стримы ЖДУТ пока TCP ретранслирует X
                              S3 и S5 готовы, но заблокированы

HTTP/3 при 2% потере пакетов:

Время →
[S1 frame][S3 frame][S5 frame][S1 frame][X LOST ][S1 frame]
                                          ↑
                              Только Stream X ждёт ретрансмиссии.
                              S1 и S3 продолжают без задержки.
```

---

## Типичные ошибки на интервью

- **"HTTP/2 = быстрее всегда"** — не всегда. На быстрых сетях без потерь HTTP/1.1 с несколькими соединениями может быть сопоставим. HTTP/2 показывает большой выигрыш на высоколатентных или нестабильных соединениях (мобильные, CDN с >100ms RTT).

- **"HTTP/3 на UDP — значит ненадёжный"** — QUIC реализует надёжную доставку поверх UDP на уровне приложения (подтверждения, повторные передачи, порядок). UDP выбран как транспорт потому что TCP нельзя изменить без обновления ОС всех узлов в интернете.

- **"HTTP/2 мультиплексинг решил все проблемы HoL"** — нет. HoL на уровне TCP остался. HTTP/3 решил его через QUIC.

- **"Server Push — крутая фича HTTP/2"** — на практике провалилась. Chrome удалил поддержку в 2022. Используйте 103 Early Hints или Resource Hints (`<link rel="preload">`).

- **"Domain sharding хорошо для HTTP/2"** — наоборот. Domain sharding требует нескольких DNS-резолюций и TLS handshake. В HTTP/2 всё мультиплексируется в одном соединении — domain sharding только мешает.

- **"HTTPS нужен только для безопасности"** — в контексте HTTP/2+ HTTPS также нужен для протокола. Браузеры не поддерживают HTTP/2 без TLS. QUIC встраивает TLS 1.3 как обязательную часть.

- **"0-RTT абсолютно безопасен"** — 0-RTT уязвим к replay attacks: перехваченный 0-RTT пакет можно отправить снова. Поэтому 0-RTT подходит только для идемпотентных запросов (GET). Серверы должны защищаться от replay на 0-RTT POST/PUT запросах.
