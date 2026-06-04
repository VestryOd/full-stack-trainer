# libuv и Thread Pool

## Самое популярное заблуждение

Очень часто говорят:

```txt
Node.js однопоточный
```

---

Это не совсем правда.

---

Правильнее говорить:

```txt
JavaScript execution thread один
```

---

Но внутри Node есть дополнительные потоки.

---

# Что такое libuv

libuv — это C библиотека,
которая лежит в основе Node.js.

---

Она отвечает за:

```txt
Event Loop
Thread Pool
Timers
Networking
Async I/O
```

---

Фактически:

```txt
Node.js
 ├── V8
 └── libuv
```

---

# Зачем нужен libuv

V8 умеет:

```txt
выполнять JavaScript
```

---

Но V8 не умеет:

```txt
читать файлы
работать с сетью
общаться с ОС
```

---

Этим занимается libuv.

---

# Что происходит при fs.readFile()

Код:

```js
fs.readFile('file.txt', callback);
```

---

Упрощенная схема:

```txt
JavaScript
     ↓
Node API
     ↓
libuv
     ↓
Thread Pool
     ↓
OS
```

---

# Пошагово

Шаг 1

JS вызывает:

```js
fs.readFile(...)
```

---

Шаг 2

Node передает задачу libuv.

---

Шаг 3

libuv отправляет задачу
в Thread Pool.

---

Шаг 4

JavaScript поток продолжает работу.

---

Шаг 5

Когда чтение завершилось:

```txt
callback попадает в очередь Event Loop
```

---

Шаг 6

Event Loop выполняет callback.

---

# Главное

Во время чтения файла:

```txt
JavaScript поток свободен
```

---

Поэтому приложение не блокируется.

---

# Thread Pool

libuv содержит пул потоков.

---

По умолчанию:

```txt
4 worker threads
```

---

Можно изменить:

```bash
UV_THREADPOOL_SIZE=8
```

---

Например:

```bash
UV_THREADPOOL_SIZE=16
```

---

# Какие операции используют Thread Pool

Очень важный вопрос.

---

Используют:

```txt
fs
crypto
zlib
dns.lookup
```

---

Например:

```js
fs.readFile()
```

---

```js
crypto.pbkdf2()
```

---

```js
zlib.gzip()
```

---

# Что НЕ использует Thread Pool

Очень любят спрашивать.

---

Сетевые операции обычно используют:

```txt
OS Event Notification APIs
```

---

Например:

```js
http.get(...)
```

---

не занимает worker thread.

---

# Почему это важно

Представим:

```js
Promise.all([
  fs.readFile(...),
  fs.readFile(...),
  fs.readFile(...),
  fs.readFile(...),
  fs.readFile(...),
]);
```

---

Thread Pool:

```txt
4 threads
```

---

Первые 4 задачи стартуют сразу.

---

Пятая будет ждать.

---

# CPU Heavy Problem

Представим:

```js
crypto.pbkdf2(...)
```

---

Очень тяжелая операция.

---

Если одновременно запустить:

```txt
100 crypto задач
```

---

Thread Pool забьется.

---

Новые fs операции будут ждать.

---

# Как увидеть проблему

Очень часто:

```txt
CPU нормальный
```

---

Но:

```txt
Latency растет
```

---

Потому что задачи ждут свободный worker thread.

---

# Можно ли бесконечно увеличивать Thread Pool?

Нет.

---

Почему?

---

Каждый поток:

```txt
использует память
создает контекстные переключения
нагружает CPU
```

---

Обычно:

```txt
4-16
```

достаточно.

---

# Частый вопрос

Node.js многопоточный или однопоточный?

---

Правильный ответ:

JavaScript код выполняется в одном потоке.

Но Node использует libuv,
который имеет Thread Pool и может выполнять часть операций параллельно.

---

# Interview Answer

libuv — это библиотека, лежащая в основе Node.js. Она отвечает за Event Loop, асинхронный I/O и Thread Pool. Такие операции как fs, crypto и zlib выполняются в worker threads, что позволяет не блокировать основной JavaScript поток.