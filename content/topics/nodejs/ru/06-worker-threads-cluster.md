<!-- verified: 2026-06-05, corrections: 0 -->
# Worker Threads и Cluster

## Три способа использовать больше одного ядра — и это разные задачи

```txt
Thread Pool (libuv)  — НЕ выполняет ваш JS. Решает проблему
                        "операция X не имеет async API ОС"
                        (см. [libuv and the Thread Pool])

Worker Threads        — выполняет ВАШ JS-код в отдельном потоке,
                        с собственным V8 instance и Event Loop.
                        Решает проблему "тяжёлое вычисление
                        блокирует главный поток"

Cluster / несколько
процессов              — несколько ПОЛНОСТЬЮ независимых
                        Node-процессов, делящих один порт.
                        Решает проблему "один процесс
                        использует одно ядро CPU"
```

Частая ошибка — воспринимать их как взаимозаменяемые "способы параллелизма". На практике это решения для РАЗНЫХ проблем, и зрелая архитектура обычно использует комбинацию: Cluster/несколько контейнеров — чтобы утилизировать все ядра под HTTP-трафик, и Worker Threads — внутри КАЖДОГО из этих процессов, чтобы конкретные тяжёлые операции не блокировали именно этот процесс.

## Worker Threads: не просто "новый поток", а новый V8 instance

```txt
Каждый Worker имеет:
  - свой V8 instance (свой heap, свой GC — независимый
    от main thread, см. [Memory and Garbage Collection])
  - свой Event Loop (свою очередь microtasks/macrotasks)
  - свой global scope

НЕ делится с main thread:
  - обычные переменные / объекты (передаются через
    структурное клонирование — это КОПИРОВАНИЕ, не ссылка)

МОЖЕТ делиться (явно):
  - SharedArrayBuffer + Atomics — единственный способ
    реальной общей памяти между потоками
```

```ts
// main.ts
import { Worker } from 'node:worker_threads';

const worker = new Worker('./hash-worker.js', {
  workerData: { password: 'user-input', cost: 100_000 },
});

worker.on('message', (hash) => console.log('Hash:', hash));
worker.on('error', (err) => console.error('Worker crashed:', err));
```

```ts
// hash-worker.js
import { parentPort, workerData } from 'node:worker_threads';
import crypto from 'node:crypto';

const hash = crypto.pbkdf2Sync(workerData.password, 'salt', workerData.cost, 64, 'sha512');
parentPort.postMessage(hash.toString('hex'));
```

### Senior-нюанс №1: создание Worker'а — это НЕ бесплатно

```txt
Создание Worker'а требует:
  - инициализации НОВОГО V8 instance (десятки миллисекунд)
  - выделения памяти под отдельный heap

❌ Создавать Worker НА КАЖДЫЙ запрос — overhead инициализации
   может превысить выигрыш от параллелизма для коротких задач:

  app.post('/hash', (req, res) => {
    const worker = new Worker('./hash-worker.js', { workerData: req.body });
    worker.on('message', (h) => res.json({ hash: h }));
  });

✅ Worker Pool — фиксированный набор воркеров, переиспользуемых
   между запросами (паттерн, который реализуют библиотеки
   piscina/workerpool — типичный выбор в реальных проектах
   вместо ручной реализации):

  const pool = new Piscina({ filename: './hash-worker.js' });
  app.post('/hash', async (req, res) => {
    const hash = await pool.run(req.body); // переиспользует воркер из пула
    res.json({ hash });
  });
```

### Senior-нюанс №2: передача данных — копирование, если не Transferable/SharedArrayBuffer

```ts
// ❌ Передача большого Buffer/массива через postMessage —
// структурное клонирование КОПИРУЕТ данные (память x2 на
// время передачи, и время на сериализацию для больших объёмов)
worker.postMessage({ buffer: largeBuffer }); // largeBuffer КОПИРУЕТСЯ

// ✅ Transferable objects — передача "владения" ArrayBuffer
// без копирования (после передачи исходный буфер становится
// недоступен в отправляющем потоке)
worker.postMessage({ buffer: largeArrayBuffer }, [largeArrayBuffer]);

// ✅ SharedArrayBuffer + Atomics — оба потока видят ОДНУ
// и ту же память; нужна явная синхронизация (Atomics.wait/
// notify), как в "настоящем" многопоточном программировании
// со всеми соответствующими рисками гонок
const shared = new SharedArrayBuffer(1024);
worker.postMessage({ shared });
```

`SharedArrayBuffer` — это редкий случай в Node, где появляются настоящие data race'ы, привычные для языков с разделяемой памятью (C++/Java). Для большинства задач (передать входные данные, получить результат) Transferable ArrayBuffer достаточен и проще в обосновании на интервью.

## Cluster: несколько процессов, общий порт

```ts
import cluster from 'node:cluster';
import os from 'node:os';

if (cluster.isPrimary) {
  const numCPUs = os.availableParallelism(); // современный API, см. ниже
  for (let i = 0; i < numCPUs; i++) cluster.fork();

  cluster.on('exit', (worker) => {
    console.log(`Worker ${worker.process.pid} died, restarting`);
    cluster.fork(); // graceful restart упавшего воркера
  });
} else {
  startHttpServer(); // каждый worker-процесс — отдельный HTTP-сервер
}
```

### Как несколько процессов слушают ОДИН порт

```txt
Primary-процесс создаёт серверный сокет и передаёт файловый
дескриптор каждому worker-процессу (либо использует
SO_REUSEPORT на современных ОС, где ядро само распределяет
входящие соединения между процессами).

Distribution стратегия по умолчанию (Linux, "round-robin"
в cluster module):
  Primary принимает соединение → передаёт его одному из
  worker-процессов по round-robin

  (на Windows и при SO_REUSEPORT — ОС сама балансирует,
  без участия Primary)
```

### Senior-нюанс: Cluster и stateful-соединения (WebSocket)

```txt
Проблема: round-robin распределяет НОВЫЕ соединения между
процессами, но каждый WebSocket-клиент "застревает" на
ТОМ процессе, который принял соединение. Если этот процесс
хранит presence/состояние в памяти — другие процессы об
этом не знают.

Это ТОТ ЖЕ "connection pinning" / "sticky session" вопрос,
что разобран для load balancer'ов в [WebSockets and Realtime
Systems] и [Scalability and Load Balancing] — Cluster просто
переносит ту же проблему с уровня "несколько серверов" на
уровень "несколько процессов на одном сервере". Решение
тоже то же самое — Redis Pub/Sub для cross-process
коммуникации, presence в Redis, а не in-memory.
```

## Cluster vs контейнеры — действительно ли Cluster "устарел"

```txt
Старая модель (один bare-metal сервер):
  1 сервер, 8 ядер → 1 Node-процесс использует 1 ядро →
  Cluster с 8 worker-процессами утилизирует все 8

Современная модель (Kubernetes/ECS):
  Деплой настроен на N "реплик" (подов/контейнеров),
  каждый — отдельный Node-процесс. Оркестратор сам
  распределяет реплики между ядрами/нодами кластера,
  Load Balancer/Service распределяет трафик между репликами.
```

Из этого МОЖНО сделать неверный вывод "Cluster больше не нужен никогда" — но это не совсем так:

```txt
Нюанс: если КОНТЕЙНЕРУ выделено, например, 4 vCPU, а внутри
него запущен ОДИН Node-процесс — этот процесс всё равно
использует только 1 ядро для JS-выполнения (event loop
single-threaded), остальные 3 vCPU контейнера простаивают
для CPU-bound части нагрузки (хотя Thread Pool/Worker Threads
их частично используют).

Вариант А: 1 контейнер = 1 Node-процесс, реплик больше
  (4 реплики по 1 vCPU вместо 1 реплики на 4 vCPU) —
  чаще предпочтительно в k8s: проще health checks,
  проще rolling updates, метрики на уровне реплики

Вариант Б: 1 контейнер = Cluster с несколькими
  worker-процессами (например, через PM2 в cluster mode) —
  иногда используется, когда оркестрация на уровне реплик
  ограничена или дорога (sidecar-нагрузка на каждую реплику)
```

Сильный ответ — не "Cluster устарел" и не "Cluster всегда нужен", а явное обозначение trade-off: Cluster внутри контейнера даёт более тонкую утилизацию CPU той же реплики, но усложняет наблюдаемость (логи/метрики нескольких процессов в одном контейнере) и graceful shutdown (нужно корректно остановить ВСЕ worker-процессы при `SIGTERM`, см. [Node.js Fundamentals]).

## Итоговая таблица решений

```txt
Задача                          → Решение
─────────────────────────────────────────────────────
fs/crypto/zlib операция,        → Thread Pool (встроено,
для которой нет async API ОС       просто await/.promises)

Тяжёлое вычисление (image        → Worker Threads (через
processing, custom hashing,        worker pool — piscina)
парсинг больших документов)

Утилизация всех ядер CPU         → несколько процессов:
сервера/контейнера для               Cluster ИЛИ несколько
HTTP-трафика                          реплик контейнера
                                       (предпочтительно в k8s)

Координация состояния между      → Redis (Pub/Sub, presence) —
процессами/репликами                 НЕ in-memory, см.
                                       [WebSockets and Realtime Systems]
```

## Типичные ошибки на интервью

- **"Worker Threads решают ту же проблему, что Thread Pool"** — не различать "выполнение ВАШЕГО JS в отдельном потоке" и "делегирование операций без async API ОС в фоновые потоки libuv".

- **Создавать Worker на каждый запрос** — не упоминать overhead инициализации V8 instance и паттерн worker pool (piscina/workerpool) как стандартное решение.

- **Не знать, что передача данных в Worker по умолчанию — копирование** — путать обычный `postMessage` с Transferable objects и SharedArrayBuffer, и не понимать стоимость структурного клонирования для больших объёмов данных.

- **"Cluster полностью устарел из-за Docker"** — без нюанса о том, что один Node-процесс внутри многоядерного контейнера всё равно использует одно ядро для event loop, и Cluster/несколько реплик решают эту проблему на разных уровнях с разными trade-offs.

- **Не связывать Cluster со sticky session проблемой** — для WebSocket/stateful-соединений Cluster создаёт ту же проблему connection pinning, что несколько серверов за load balancer'ом, и решается тем же способом (Redis).
