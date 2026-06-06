<!-- verified: 2026-06-05, corrections: 0 -->
# Node.js Fundamentals

## Что такое Node.js

Node.js — это JavaScript Runtime Environment.

Очень важно понимать:

```txt
Node.js ≠ JavaScript
Node.js ≠ Framework
```

---

JavaScript — язык.

Node.js — среда выполнения.

---

# Что значит Runtime

Runtime — это программа,
которая позволяет выполнять JavaScript код.

---

Например:

```js
console.log('Hello');
```

---

В браузере этот код выполняет:

```txt
Chrome
Firefox
Safari
```

---

На сервере его выполняет:

```txt
Node.js
```

---

# Почему Node.js появился

До Node JavaScript существовал почти исключительно в браузере.

---

В 2009 году Ryan Dahl создал Node.js.

Главная идея:

```txt
Асинхронный сервер
без создания потока на каждый запрос
```

---

# Основные преимущества Node.js

## Один язык

Frontend:

```txt
JavaScript / TypeScript
```

Backend:

```txt
JavaScript / TypeScript
```

---

## Высокая производительность для I/O

Node отлично подходит для:

```txt
REST API
GraphQL
WebSockets
Realtime приложения
Proxy
Streaming
```

---

## Огромная экосистема

npm содержит миллионы пакетов.

---

# Где Node особенно хорош

I/O Bound задачи.

---

Например:

```txt
Запросы к БД
HTTP запросы
Redis
Файлы
Очереди сообщений
```

---

Node не ждёт завершения операций.

Он продолжает обслуживать другие запросы.

---

# Где Node работает хуже

CPU-bound задачи.

---

Например:

```txt
Видео кодирование
Image processing
Machine Learning
Сложные вычисления
```

---

Потому что основной JS поток один.

---

# Основные части Node.js

Node состоит из:

```txt
V8
Libuv
Event Loop
Thread Pool
Node APIs
```

---

Многие разработчики думают:

```txt
Node = V8
```

Это ошибка.

V8 — только часть Node.

---

# Что даёт Node поверх JavaScript

В браузере нет:

```js
fs.readFile()
```

---

В Node есть.

---

В браузере нет:

```js
process.env
```

---

В Node есть.

---

Node предоставляет:

```txt
File System
Network APIs
Streams
Processes
Buffers
Crypto
Timers
```

---

# Процесс Node.js

Когда запускается:

```bash
node app.js
```

создается:

```txt
Node Process
```

---

У процесса есть:

```txt
Heap
Stack
Event Loop
Thread Pool
```

---

# Event Driven Architecture

Node построен вокруг событий.

---

Пример:

```js
server.on('request', callback);
```

---

Событие:

```txt
request
```

---

Обработчик:

```txt
callback
```

---

Так работает большая часть Node.

---

# EventEmitter

Основа событийной модели.

---

Пример:

```js
emitter.on('userCreated', handler);
```

---

И затем:

```js
emitter.emit('userCreated');
```

---

Многие встроенные Node API используют EventEmitter.

---

# Основной вывод

Node.js — это JavaScript Runtime,
оптимизированный для асинхронного I/O.

Его сила не в вычислениях,
а в эффективной обработке большого количества параллельных операций ввода-вывода.