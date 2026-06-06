<!-- verified: 2026-06-05, corrections: 0 -->
# Worker Threads и Cluster

## Главный вопрос

Если Node умеет Thread Pool:

```txt
Зачем нужны Worker Threads?
```

---

Потому что:

```txt
Thread Pool не выполняет JavaScript код
```

---

Он выполняет:

```txt
fs
crypto
zlib
dns
```

---

Но если у нас есть:

```js
while(true){}
```

---

Thread Pool не поможет.

---

# CPU-bound задачи

Например:

```txt
image processing
video encoding
pdf generation
machine learning
hashing
```

---

Они выполняются в основном JS потоке.

---

И блокируют Event Loop.

---

# Решение

Worker Threads.

---

# Что такое Worker Thread

Отдельный JavaScript поток.

---

Схема:

```txt
Main Thread
      │
      ├── Worker 1
      ├── Worker 2
      └── Worker 3
```

---

Каждый Worker имеет:

```txt
свой Event Loop
свой V8 Instance
свой Call Stack
```

---

# Создание Worker

```js
const { Worker } = require('worker_threads');

new Worker('./worker.js');
```

---

# Обмен сообщениями

Worker не разделяет память напрямую.

---

Используется:

```txt
postMessage()
```

---

Пример:

Main:

```js
worker.postMessage(100);
```

---

Worker:

```js
parentPort.on('message', value => {
  ...
});
```

---

# Почему это важно

Теперь тяжелая задача выполняется:

```txt
не в Main Thread
```

---

Event Loop остается свободным.

---

# Когда использовать Worker Threads

Использовать для:

```txt
CPU-bound задач
```

---

Например:

```txt
image resize
PDF rendering
video processing
AI
encryption
```

---

# Когда НЕ использовать

Обычные:

```txt
REST API
DB Queries
HTTP Requests
```

---

Для них Worker не нужен.

---

# Cluster

Очень популярный вопрос.

---

# Зачем нужен Cluster

Node процесс использует:

```txt
1 CPU Core
```

---

Представим сервер:

```txt
8 CPU cores
```

---

Получается:

```txt
используется только 1 из 8
```

---

# Решение

Cluster.

---

# Что делает Cluster

Создает несколько процессов.

---

Схема:

```txt
Master
  │
  ├── Process 1
  ├── Process 2
  ├── Process 3
  └── Process 4
```

---

Каждый процесс:

```txt
имеет свой Event Loop
имеет свой Heap
имеет свой V8
```

---

# Важно

Это НЕ потоки.

---

Это полноценные процессы.

---

# Shared Memory

Worker Threads:

```txt
можно использовать SharedArrayBuffer
```

---

Cluster:

```txt
память не разделяется
```

---

# Worker vs Cluster

Worker Threads:

```txt
многопоточность
один процесс
```

---

Cluster:

```txt
много процессов
много ядер CPU
```

---

# Что используется чаще сегодня

Очень интересный вопрос.

---

Раньше:

```txt
Cluster
```

использовался постоянно.

---

Сегодня чаще:

```txt
Docker
Kubernetes
PM2
несколько контейнеров
```

---

Поэтому Cluster стал менее популярен.

---

# Практический пример

Представим:

```txt
4 CPU cores
```

---

Вариант 1

```txt
1 Node Process
```

Использует:

```txt
1 core
```

---

Вариант 2

```txt
4 Cluster Processes
```

Использует:

```txt
4 cores
```

---

# Частый вопрос

Worker Threads или Cluster для image processing?

---

Обычно:

```txt
Worker Threads
```

---

Потому что это CPU-heavy задача.

---

# Частый вопрос

Worker Threads или Cluster для API?

---

Обычно:

```txt
Cluster
```

или несколько контейнеров.

---

# Interview Answer

Worker Threads позволяют выполнять CPU-intensive JavaScript код в отдельных потоках и используются для вычислительно сложных задач. Cluster создает несколько Node.js процессов и позволяет использовать несколько CPU ядер для масштабирования серверных приложений. Worker Threads решают проблему CPU-bound вычислений, а Cluster — проблему использования только одного CPU core.