# Node.js Interview Questions (Middle → Senior)

---

# 1. Что такое Node.js?

Node.js — это JavaScript Runtime Environment,
построенный на движке V8 и библиотеке libuv.

---

# 2. Чем Node.js отличается от браузера?

Node предоставляет:

- File System
- Process API
- Network API
- Streams
- Crypto

которые недоступны в браузере.

---

# 3. Что такое V8?

JavaScript Engine,
который выполняет JS код.

Отвечает за:

- Parsing
- Compilation
- Optimization
- Garbage Collection

---

# 4. Что такое Event Loop?

Механизм обработки асинхронных операций.

Event Loop выполняет callbacks,
когда Call Stack становится пустым.

---

# 5. Какие основные фазы Event Loop?

```txt
Timers
Pending Callbacks
Poll
Check
Close Callbacks
```

---

# 6. Что такое Microtask Queue?

Очередь для:

```txt
Promise.then
catch
finally
queueMicrotask
```

---

# 7. Что такое Macrotask Queue?

Очередь для:

```txt
setTimeout
setInterval
setImmediate
I/O callbacks
```

---

# 8. Почему Promise.then выполняется раньше setTimeout?

Потому что Microtasks имеют более высокий приоритет,
чем Macrotasks.

---

# 9. Что такое process.nextTick?

Специальная очередь Node.js,
которая выполняется раньше Microtasks.

---

# 10. Почему process.nextTick опасен?

Можно создать starvation
и заблокировать Event Loop.

---

# 11. Что такое libuv?

Библиотека,
которая реализует Event Loop,
Thread Pool и асинхронный I/O.

---

# 12. Node.js однопоточный или многопоточный?

JavaScript код выполняется в одном потоке.

Но Node использует:

- Thread Pool
- Worker Threads
- Cluster

---

# 13. Что такое Thread Pool?

Пул worker потоков libuv.

По умолчанию:

```txt
4 threads
```

---

# 14. Какие операции используют Thread Pool?

- fs
- crypto
- zlib
- dns.lookup

---

# 15. Почему fs.readFile не блокирует приложение?

Потому что операция выполняется в libuv Thread Pool.

---

# 16. Что такое Worker Threads?

Отдельные JavaScript потоки
для CPU-bound задач.

---

# 17. Когда использовать Worker Threads?

- Image Processing
- PDF Generation
- Encryption
- Machine Learning

---

# 18. Что такое Cluster?

Механизм запуска нескольких Node процессов
для использования нескольких CPU ядер.

---

# 19. Чем Worker отличается от Cluster?

Worker:

```txt
Threads
```

---

Cluster:

```txt
Processes
```

---

# 20. Что такое Streams?

Механизм обработки данных по частям,
без загрузки всего содержимого в память.

---

# 21. Какие типы Streams существуют?

- Readable
- Writable
- Duplex
- Transform

---

# 22. Что такое Backpressure?

Механизм регулирования скорости передачи данных,
предотвращающий переполнение памяти.

---

# 23. Почему Stream лучше readFile для больших файлов?

Потому что данные обрабатываются chunk-by-chunk.

---

# 24. Что такое Buffer?

Специальный объект Node
для работы с бинарными данными.

---

# 25. Что такое Heap?

Область памяти,
где хранятся объекты и массивы.

---

# 26. Что такое Stack?

Стек вызовов функций.

---

# 27. Что такое Garbage Collector?

Механизм автоматического освобождения памяти.

---

# 28. Как работает Mark-and-Sweep?

GC помечает достижимые объекты,
затем удаляет остальные.

---

# 29. Что такое Generational GC?

Разделение объектов на:

```txt
Young Generation
Old Generation
```

---

# 30. Что такое Memory Leak?

Ситуация,
когда объекты больше не нужны,
но всё ещё достижимы для GC.

---

# 31. Самые частые причины Memory Leak?

- Глобальные массивы
- Замыкания
- Event Listeners
- Кэш без очистки

---

# 32. Что показывает process.memoryUsage()?

Статистику памяти процесса:

- rss
- heapUsed
- heapTotal

---

# 33. Что такое CommonJS?

Система модулей Node.js:

```js
require()
module.exports
```

---

# 34. Что такое ES Modules?

Современный стандарт:

```js
import
export
```

---

# 35. В чем преимущество ESM?

- Tree Shaking
- Static Analysis
- Dynamic Import
- Top-Level Await

---

# 36. Что такое EventEmitter?

Базовый механизм событий Node.js.

---

# 37. Что такое CPU-bound задача?

Задача,
нагружающая процессор.

---

# 38. Что такое I/O-bound задача?

Задача,
ожидающая внешние ресурсы.

---

# 39. Почему Node хорош для I/O-bound задач?

Потому что Event Loop не блокируется ожиданием.

---

# 40. Почему Node плохо подходит для CPU-heavy задач?

Потому что основной JS поток один.

---

# 41. Что такое Unhandled Promise Rejection?

Ошибка Promise,
которая не была обработана через catch.

---

# 42. Что такое Dynamic Import?

```js
await import('./module.js');
```

Позволяет загружать модуль лениво.

---

# 43. Что такое Top-Level Await?

Использование await вне функции
в ES Modules.

---

# 44. Как диагностировать производительность Node приложения?

- Profiling
- Heap Snapshot
- EXPLAIN ANALYZE (если проблема в БД)
- Clinic.js
- Chrome DevTools

---

# 45. Самый популярный Senior вопрос

Почему Node.js способен обрабатывать тысячи соединений одновременно?

Ответ:

Потому что Node использует Event Loop и неблокирующий I/O. Вместо создания потока на каждый запрос он передает асинхронные операции операционной системе или libuv и продолжает обслуживать другие соединения.