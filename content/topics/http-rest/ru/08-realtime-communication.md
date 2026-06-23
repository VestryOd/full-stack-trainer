<!-- verified: 2026-06-23, corrections: 0 -->
# Real-Time коммуникация

## Четыре подхода

Когда нужно, чтобы клиент получал обновления без явного запроса, есть четыре механизма: polling, long polling, SSE и WebSockets. Они выглядят похоже, но устроены принципиально по-разному. Разберём каждый по отдельности — потом сравним.

---

## Polling (короткий опрос)

Простейший подход: клиент периодически спрашивает "есть что-то новое?".

### Как это работает

```txt
Время →

Клиент: [GET /api/updates] [GET /api/updates] [GET /api/updates] [GET /api/updates]
           ↓                   ↓                  ↓                  ↓
Сервер: [200: пусто]       [200: пусто]        [200: данные!]    [200: пусто]

                            ↑ интервал 5 секунд ↑
```

### Реализация

```typescript
// Клиент:
function startPolling(intervalMs: number = 5000) {
  const poll = async () => {
    const response = await fetch("/api/notifications?since=" + lastSeenId);
    const { items, lastId } = await response.json();

    if (items.length > 0) {
      handleNewItems(items);
      lastSeenId = lastId;
    }
  };

  const timerId = setInterval(poll, intervalMs);
  return () => clearInterval(timerId); // cleanup
}

// Сервер (Express):
app.get("/api/notifications", async (req, res) => {
  const since = Number(req.query.since) || 0;
  const items = await db.notifications.findAll({
    where: { id: { [Op.gt]: since }, userId: req.user.id },
    order: [["id", "ASC"]],
    limit: 50,
  });

  res.json({
    items,
    lastId: items.at(-1)?.id ?? since,
  });
});
```

### Честная оценка polling

```txt
Плюсы:
  ✅ Тривиально реализовать
  ✅ Работает везде: любой браузер, любой прокси, любой сервер
  ✅ Stateless: сервер не знает о "соединении"
  ✅ Легко дебажить (обычные HTTP-запросы)
  ✅ Легко горизонтально масштабировать

Минусы:
  ❌ Задержка = интервал опроса (5 сек интервал = до 5 сек задержка)
  ❌ Пустые запросы: 95% запросов возвращают "ничего нового"
  ❌ Нагрузка пропорциональна числу клиентов × частоте
     1000 клиентов × раз в 5 сек = 200 req/s постоянно
```

**Когда использовать:**
- Редкие обновления (раз в минуту и реже) — dashboard статистики
- Прогресс долгой операции (файловый импорт, генерация отчёта)
- Простота важнее эффективности (прототип, внутренний инструмент)
- Инфраструктура не поддерживает persistent connections (старые прокси)

---

## Long Polling (длинный опрос)

Улучшение polling: сервер держит запрос открытым до появления данных или таймаута.

### Как это работает

```txt
Время →

Клиент: [GET /api/updates] ──────────── hold ──────────── [данные!] [GET /api/updates] ──────── hold ──
Сервер:                    ждёт данных...                 ↑          ждёт данных...
                                                     данные появились
                                                     → ответ → клиент сразу переподключается
```

### Реализация

```typescript
// Сервер (Express) — держим запрос открытым:
const waitingClients = new Map<string, express.Response>();

app.get("/api/long-poll", async (req, res) => {
  const userId = req.user.id;

  // Проверяем есть ли уже ожидающие данные:
  const pending = await db.notifications.findPending(userId);
  if (pending.length > 0) {
    return res.json({ items: pending });
  }

  // Ничего нет — регистрируем клиента как ожидающего:
  res.setTimeout(30_000, () => {
    waitingClients.delete(userId);
    res.json({ items: [] }); // таймаут → пустой ответ
  });

  waitingClients.set(userId, res);

  // Когда клиент отключился — убираем:
  req.on("close", () => {
    waitingClients.delete(userId);
  });
});

// Когда приходит новое уведомление:
async function notifyUser(userId: string, notification: Notification) {
  await db.notifications.save(notification);

  const waitingRes = waitingClients.get(userId);
  if (waitingRes) {
    waitingClients.delete(userId);
    waitingRes.json({ items: [notification] });
  }
}

// Клиент:
async function longPoll() {
  while (true) {
    try {
      const response = await fetch("/api/long-poll", {
        signal: AbortSignal.timeout(35_000), // чуть больше серверного таймаута
      });
      const { items } = await response.json();

      if (items.length > 0) handleNewItems(items);
    } catch (err) {
      if (err instanceof DOMException && err.name === "TimeoutError") continue;
      await sleep(2000); // пауза при ошибке перед переподключением
    }
  }
}
```

### Честная оценка long polling

```txt
Плюсы:
  ✅ Почти real-time задержка при наличии данных (десятки мс)
  ✅ Меньше пустых запросов чем обычный polling
  ✅ Работает через все прокси и файрволы (обычный HTTP)
  ✅ Stateless между сессиями (каждый запрос независим)

Минусы:
  ❌ Сложнее сервера: нужно управлять открытыми соединениями
  ❌ Каждый ответ требует нового запроса (задержка переподключения)
  ❌ Сложно масштабировать: в памяти каждого инстанса свои waitingClients
     → нужен общий pub/sub (Redis) чтобы уведомить правильный инстанс
  ❌ Занимает thread/worker на весь период ожидания (без async)
```

**Когда использовать:**
- Нужна низкая задержка, но SSE/WebSocket недоступны (устаревшие клиенты)
- Исторически: Comet, XMPP-клиенты, старые версии WhatsApp Web
- Сегодня: почти всегда лучше использовать SSE вместо long polling

---

## Server-Sent Events (SSE)

SSE — это **однонаправленный постоянный HTTP-поток** от сервера к клиенту. Браузер открывает соединение один раз, сервер шлёт события сколько угодно долго.

### Как это работает

```txt
Клиент: GET /api/events HTTP/1.1
        Accept: text/event-stream

Сервер: HTTP/1.1 200 OK
        Content-Type: text/event-stream
        Cache-Control: no-cache
        Connection: keep-alive

        data: {"type":"message","text":"Hello"}\n\n

        event: notification\n
        data: {"id":42,"text":"New order"}\n
        id: 42\n\n

        data: keep-alive\n\n

        event: notification\n
        data: {"id":43,"text":"Order shipped"}\n
        id: 43\n\n
        ↑ соединение остаётся открытым, сервер шлёт события по мере появления
```

### Формат SSE-события

```txt
Каждое событие — набор строк, завершается пустой строкой (\n\n):

data: текст или JSON                  ← обязательное поле
event: имя-события                    ← опционально (default: "message")
id: 42                                ← опционально, для Last-Event-ID
retry: 3000                           ← опционально, мс до переподключения

Примеры:

Простое событие:
  data: Hello world\n\n

JSON-данные:
  data: {"userId":42,"action":"login"}\n\n

Многострочные данные (несколько data:):
  data: first line\n
  data: second line\n\n

Именованное событие:
  event: orderUpdate\n
  data: {"orderId":100,"status":"shipped"}\n
  id: 55\n\n
```

### EventSource API на клиенте

```typescript
const eventSource = new EventSource("/api/events", {
  withCredentials: true, // отправлять cookies
});

// Событие по умолчанию (event: message или без event:):
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("message:", data);
};

// Именованное событие:
eventSource.addEventListener("orderUpdate", (event) => {
  const order = JSON.parse(event.data);
  updateOrderUI(order);
});

// Ошибки и переподключение:
eventSource.onerror = (err) => {
  console.error("SSE error:", err);
  // Браузер автоматически переподключится!
  // Если установлен id: — отправит Last-Event-ID заголовок
};

// Закрытие:
eventSource.close();
```

**Автоматическое переподключение** — встроенная функция SSE. Браузер сам переподключается при разрыве (через `retry` мс, по умолчанию 3000). При переподключении отправляет `Last-Event-ID`, и сервер может выдать пропущенные события.

### Реализация SSE-сервера (Express)

```typescript
// Менеджер подключений:
class SSEManager {
  private connections = new Map<string, express.Response[]>();

  add(userId: string, res: express.Response) {
    const existing = this.connections.get(userId) ?? [];
    this.connections.set(userId, [...existing, res]);
  }

  remove(userId: string, res: express.Response) {
    const remaining = (this.connections.get(userId) ?? []).filter(r => r !== res);
    if (remaining.length === 0) {
      this.connections.delete(userId);
    } else {
      this.connections.set(userId, remaining);
    }
  }

  send(userId: string, event: string, data: unknown, id?: number) {
    const conns = this.connections.get(userId) ?? [];
    const chunk = [
      `event: ${event}`,
      `data: ${JSON.stringify(data)}`,
      id !== undefined ? `id: ${id}` : "",
      "",  // пустая строка = конец события
      "",
    ].filter(Boolean).join("\n") + "\n";

    for (const res of conns) {
      res.write(chunk);
    }
  }
}

const sseManager = new SSEManager();

// SSE endpoint:
app.get("/api/events", requireAuth, async (req, res) => {
  // Обязательные заголовки:
  res.set({
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no", // отключить буфер nginx
  });

  // Начальное рукопожатие:
  res.write("retry: 3000\n\n");

  const userId = req.user.id;
  sseManager.add(userId, res);

  // Keepalive каждые 30 сек (прокси закрывают idle-соединения):
  const keepAlive = setInterval(() => {
    res.write(": keepalive\n\n"); // строка с : — комментарий, игнорируется клиентом
  }, 30_000);

  // Клиент отключился:
  req.on("close", () => {
    clearInterval(keepAlive);
    sseManager.remove(userId, res);
  });
});

// Отправка событий из бизнес-логики:
async function onNewNotification(notification: Notification) {
  await db.notifications.save(notification);
  sseManager.send(notification.userId, "notification", notification, notification.id);
}
```

### SSE через HTTP/2

SSE прекрасно работает с HTTP/2: каждое SSE-соединение — это один HTTP/2 стрим. Браузер в HTTP/1.1 ограничен 6 соединениями на домен (и SSE занимает одно из них!). В HTTP/2 стримов неограниченно — можно открыть 100 SSE-соединений без проблем.

### Честная оценка SSE

```txt
Плюсы:
  ✅ Простота: обычный HTTP, работает через любой прокси
  ✅ Автоматическое переподключение с Last-Event-ID — встроено в браузер
  ✅ Именованные события — встроено в протокол
  ✅ Не нужна библиотека: EventSource поддерживается всеми браузерами
  ✅ HTTP/2-совместим: множество SSE-стримов на одном соединении
  ✅ Простое серверное масштабирование (нужен только pub/sub для нескольких инстансов)

Минусы:
  ❌ Только сервер → клиент (однонаправленный)
  ❌ Только текст (нет бинарного протокола)
  ❌ EventSource не поддерживает custom заголовки (токен нельзя передать как Bearer)
     → обходы: токен в query param или cookie
  ❌ В HTTP/1.1: один SSE занимает одно из 6 соединений
```

---

## WebSockets

WebSockets — это **полнодуплексное постоянное соединение** поверх TCP (RFC 6455). Клиент и сервер могут отправлять сообщения друг другу в любой момент.

### Upgrade Handshake

WebSocket соединение начинается как HTTP-запрос, затем "апгрейдится":

```http
GET /ws HTTP/1.1
Host: api.example.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13
Sec-WebSocket-Protocol: chat, superchat

─────────────────────────────────────────
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
Sec-WebSocket-Protocol: chat
```

После 101 — соединение переключается в WebSocket-протокол. TCP-соединение остаётся открытым, HTTP больше не используется.

`Sec-WebSocket-Accept` = base64(SHA1(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11")) — защита от случайных HTTP-серверов, принявших WS-запрос.

### WebSocket фреймы

```txt
Фрейм WebSocket (упрощённо):
  [FIN][RSV][Opcode 4 bits][Mask 1 bit][Payload Length][Masking Key][Payload]

Opcodes:
  0x0 — continuation frame
  0x1 — text frame (UTF-8)
  0x2 — binary frame
  0x8 — close
  0x9 — ping
  0xA — pong

Masking: все фреймы от клиента маскируются (защита от proxy cache poisoning)
         серверные фреймы не маскируются
```

### WebSocket API на клиенте

```typescript
const ws = new WebSocket("wss://api.example.com/ws");

ws.onopen = () => {
  console.log("Connected");
  // Аутентификация после открытия:
  ws.send(JSON.stringify({ type: "auth", token: getAccessToken() }));
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data as string);
  handleMessage(message);
};

ws.onerror = (err) => {
  console.error("WebSocket error:", err);
};

ws.onclose = (event) => {
  console.log("Closed:", event.code, event.reason);
  // Переподключение — НЕ автоматическое! нужно реализовать самому:
  setTimeout(reconnect, 3000);
};

// Отправка клиентом:
ws.send(JSON.stringify({ type: "chat", text: "Hello!" }));

// Бинарные данные:
ws.send(new Uint8Array([1, 2, 3, 4]));
ws.binaryType = "arraybuffer"; // или "blob"

// Закрытие:
ws.close(1000, "Normal closure");
```

### Реализация WebSocket-сервера

```typescript
import { WebSocketServer, WebSocket } from "ws";
import http from "http";

const server = http.createServer(app);
const wss = new WebSocketServer({ server });

interface AuthenticatedWebSocket extends WebSocket {
  userId?: string;
  isAlive: boolean;
}

// Менеджер соединений:
const connections = new Map<string, Set<AuthenticatedWebSocket>>();

wss.on("connection", (ws: AuthenticatedWebSocket, req) => {
  ws.isAlive = true;

  ws.on("pong", () => { ws.isAlive = true; }); // ответ на наш ping

  ws.on("message", (data) => {
    try {
      const message = JSON.parse(data.toString());
      handleMessage(ws, message);
    } catch {
      ws.send(JSON.stringify({ type: "error", message: "Invalid JSON" }));
    }
  });

  ws.on("close", (code, reason) => {
    if (ws.userId) {
      connections.get(ws.userId)?.delete(ws);
    }
  });

  ws.on("error", (err) => {
    console.error("WebSocket error:", err);
  });
});

function handleMessage(ws: AuthenticatedWebSocket, message: Record<string, unknown>) {
  if (message.type === "auth") {
    // Верифицируем токен:
    const userId = verifyToken(message.token as string);
    if (!userId) {
      ws.close(1008, "Unauthorized"); // 1008 = Policy Violation
      return;
    }
    ws.userId = userId;

    const userConns = connections.get(userId) ?? new Set();
    userConns.add(ws);
    connections.set(userId, userConns);

    ws.send(JSON.stringify({ type: "auth_ok" }));
    return;
  }

  if (!ws.userId) {
    ws.close(1008, "Not authenticated");
    return;
  }

  // Обрабатываем остальные сообщения...
  if (message.type === "chat") {
    broadcastToRoom(message.roomId as string, {
      type: "chat",
      from: ws.userId,
      text: message.text,
    });
  }
}

// Отправка пользователю на все его устройства:
function sendToUser(userId: string, data: unknown) {
  const userConns = connections.get(userId);
  if (!userConns) return;

  const payload = JSON.stringify(data);
  for (const conn of userConns) {
    if (conn.readyState === WebSocket.OPEN) {
      conn.send(payload);
    }
  }
}

// Keepalive: ping каждые 30 сек, убиваем мёртвые соединения:
const pingInterval = setInterval(() => {
  wss.clients.forEach((ws) => {
    const aws = ws as AuthenticatedWebSocket;
    if (!aws.isAlive) {
      aws.terminate();
      return;
    }
    aws.isAlive = false;
    aws.ping();
  });
}, 30_000);

wss.on("close", () => clearInterval(pingInterval));
```

### Масштабирование WebSockets

Проблема: клиент на инстансе A хочет отправить сообщение пользователю, который подключён к инстансу B.

```txt
Решение: Redis Pub/Sub (или другой pub/sub)

Client A → WS Instance 1 → publish("user:42", message) → Redis
                                                            ↓
                                                   subscribe("user:42")
                                                            ↓
                                                   WS Instance 2 → Client B
```

```typescript
import { createClient } from "redis";

const publisher = createClient({ url: process.env.REDIS_URL });
const subscriber = publisher.duplicate();

await Promise.all([publisher.connect(), subscriber.connect()]);

// При получении сообщения от клиента:
async function broadcastToUser(targetUserId: string, data: unknown) {
  // Сначала локально:
  sendToUser(targetUserId, data);
  // Затем на другие инстансы:
  await publisher.publish(`user:${targetUserId}`, JSON.stringify(data));
}

// Подписка на сообщения от других инстансов:
await subscriber.subscribe("user:*", (message, channel) => {
  const userId = channel.replace("user:", "");
  sendToUser(userId, JSON.parse(message));
});
```

### Честная оценка WebSockets

```txt
Плюсы:
  ✅ Полный дуплекс: клиент и сервер шлют сообщения независимо
  ✅ Низкий overhead после handshake: минимальные фреймы без HTTP-заголовков
  ✅ Поддержка бинарных данных (ArrayBuffer, Blob)
  ✅ Нет ограничений на число сообщений и направление
  ✅ Встроен ping/pong для keepalive

Минусы:
  ❌ Stateful: каждый инстанс помнит своих клиентов → сложнее масштабировать
  ❌ Нет автоматического переподключения (в отличие от SSE) — нужно реализовать
  ❌ Прокси и файрволы иногда закрывают idle WS-соединения
  ❌ Аутентификация сложнее: нет HTTP-заголовков после handshake
  ❌ Отладка сложнее: не видно в Network tab как обычные HTTP-запросы
  ❌ ws:// не зашифрован, wss:// обязателен в production
```

---

## Сравнение и выбор

```txt
┌──────────────────────┬───────────┬────────────┬───────────┬─────────────┐
│                      │ Polling   │ Long Poll  │ SSE       │ WebSocket   │
├──────────────────────┼───────────┼────────────┼───────────┼─────────────┤
│ Направление          │ pull      │ pull       │ push S→C  │ push S↔C    │
│ Задержка             │ = интервал│ ~мс        │ ~мс       │ ~мс         │
│ Пустые запросы       │ много     │ мало       │ нет       │ нет         │
│ Авт. переподключение │ клиент    │ клиент     │ браузер ✅ │ ❌ нет     │
│ Прокси/файрвол       │ ✅ всегда  │ ✅ всегда  │ ✅ всегда │ ⚠️ иногда  │
│ Бинарные данные      │ ❌        │ ❌         │ ❌        │ ✅          │
│ Масштабирование      │ ✅ просто  │ ⚠️ Redis   │ ⚠️ Redis  │ ❌ сложно  │
│ Сложность реализации │ ⭐        │ ⭐⭐        │ ⭐⭐       │ ⭐⭐⭐⭐     │
│ HTTP/2 совместим     │ ✅        │ ✅         │ ✅✅       │ ❌ (отд. прот)│
└──────────────────────┴───────────┴────────────┴───────────┴─────────────┘
```

### Практическое руководство по выбору

```txt
Начните с вопроса: нужен ли push от клиента к серверу в реальном времени?

НЕ нужен (только сервер → клиент):
  Используйте SSE.
  Примеры: уведомления, лента новостей, прогресс задачи, live dashboard,
           стриминг LLM-ответов, обновления заказа.

НУЖЕН (клиент ↔ сервер, полный дуплекс):
  Используйте WebSockets.
  Примеры: чат, совместное редактирование, онлайн-игры,
           торговые терминалы, коллаборативные whiteboard.

Нет persistent connection вообще:
  Редкие обновления (раз в минуту): polling.
  Нужна низкая задержка, но SSE недоступен: long polling.

Не уверены? Начните с SSE или polling.
WebSockets оправданы только когда реально нужен двунаправленный real-time push.
Сложность масштабирования и реализации WebSockets значительно выше SSE.
```

### Частые реальные случаи

```txt
Уведомления (GitHub, Jira, Slack unread count):
  → SSE (сервер пушит, клиент не отвечает в реальном времени)

Стриминг ответа ChatGPT/Claude:
  → SSE (сервер стримит токены, клиент только читает)
  Реализация: stream.write(`data: ${token}\n\n`)

Прогресс загрузки/импорта файла:
  → SSE или polling (зависит от частоты обновлений)

Live dashboard (метрики, аналитика):
  → SSE (обновление каждые N секунд с сервера)

Чат-приложение (Slack, WhatsApp):
  → WebSockets (клиент отправляет сообщения + получает)

Совместный редактор (Google Docs, Figma):
  → WebSockets (OT/CRDT + постоянный двунаправленный поток изменений)

Онлайн-игра с реальным временем:
  → WebSockets или UDP (для браузера — WebRTC DataChannel)

Торговый терминал (котировки + ордера):
  → WebSockets (получение котировок + отправка ордеров)
```

---

## WebTransport (будущее)

Новый стандарт W3C/IETF поверх HTTP/3 (QUIC), сочетающий преимущества WebSockets и QUIC:

```txt
WebTransport преимущества над WebSockets:
  - Несколько независимых стримов в одном соединении
  - Unreliable datagrams (как UDP — для игр, видео, где важна скорость, а не надёжность)
  - 0-RTT подключение (QUIC)
  - Не блокирует другие стримы при потере пакетов

Состояние (2024): Chrome поддерживает, Firefox в разработке.
Использовать в production пока рано.
```

---

## Типичные ошибки на интервью

- **"WebSockets лучше SSE для real-time"** — зависит от задачи. Если нужен только push от сервера к клиенту (уведомления, лента, стриминг), SSE проще и достаточно. WebSockets добавляют значительную сложность при масштабировании ради функции, которая часто не нужна.

- **"SSE — это устаревший подход"** — нет. SSE активно используется. OpenAI стримит ответы ChatGPT через SSE. GitHub стримит live-обновления через SSE. Это современный и поддерживаемый стандарт.

- **"WebSockets не работают через HTTPS"** — работают. `ws://` — незашифрованный (как http://), `wss://` — зашифрованный (как https://). В production обязательно `wss://`.

- **"Polling — устаревший антипаттерн, нельзя использовать"** — polling отлично подходит для редких обновлений и простых сценариев. Dashboard статистики, который обновляется раз в минуту — polling прекрасно справляется без лишней сложности.

- **"SSE автоматически переподключается — значит надёжен полностью"** — автоматическое переподключение есть, но при переподключении нужно корректно выдать пропущенные события. Для этого `id:` в событиях + обработка `Last-Event-ID` на сервере. Без этого события потеряются при кратком разрыве.

- **"WebSocket соединение постоянно активно — зачем ping/pong?"** — прокси и файрволы закрывают idle TCP-соединения (обычно через 60–120 сек). Без keepalive (ping/pong) соединение тихо умрёт. Клиент узнает об этом только при попытке отправить следующее сообщение.

- **"Long polling = SSE = WebSocket по нагрузке на сервер"** — принципиально разные. Long polling: N открытых HTTP-запросов + переподключение после каждого события. SSE: N постоянных HTTP-потоков (меньше overhead). WebSocket: N постоянных TCP-соединений с минимальным фреймингом. При 10 000 клиентах разница ощутима.
