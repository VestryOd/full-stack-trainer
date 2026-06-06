<!-- verified: 2026-06-05, corrections: 0 -->
# V8 and Node.js Runtime

## Что такое V8

V8 — это JavaScript Engine,
разработанный Google.

---

Используется:

```txt
Chrome
Node.js
Deno
```

---

# Что делает V8

Берёт JavaScript код:

```js
const x = 5 + 10;
```

---

И выполняет его.

---

# Основные задачи V8

- Parsing
- Compilation
- Optimization
- Execution
- Garbage Collection

---

# Parsing

Сначала V8 читает исходный код.

---

Из:

```js
const x = 5;
```

строится:

```txt
AST
(Abstract Syntax Tree)
```

---

Упрощённо:

```txt
VariableDeclaration
 ├── Identifier(x)
 └── Literal(5)
```

---

# Compilation

Старые движки:

```txt
код
↓
интерпретация
```

---

Современный V8:

```txt
код
↓
компиляция
↓
машинный код
```

---

# JIT

Just-In-Time Compilation.

---

Код компилируется во время выполнения.

---

# Ignition

Первый уровень исполнения.

---

Упрощённо:

```txt
JS
↓
Bytecode
```

---

# TurboFan

Оптимизирующий компилятор.

---

Когда V8 видит,
что функция вызывается много раз:

```js
function add(a,b) {
  return a+b;
}
```

---

Он оптимизирует её.

---

Получаем:

```txt
Очень быстрый машинный код
```

---

# Hidden Classes

Очень популярный Senior вопрос.

---

V8 пытается оптимизировать объекты.

---

Например:

```js
const user = {
  name: 'Max',
  age: 30
};
```

---

Создается внутренняя структура:

```txt
Hidden Class
```

---

Если объекты имеют одинаковую форму:

```js
{name, age}
{name, age}
{name, age}
```

---

V8 работает быстрее.

---

# Почему плохо динамически менять объекты

Плохо:

```js
user.address = 'London';
```

---

Теперь Hidden Class меняется.

---

Оптимизация может сломаться.

---

# Inline Cache

Следующий уровень оптимизации.

---

V8 запоминает:

```txt
где лежит поле объекта
```

---

И получает его быстрее.

---

# Что такое Runtime

Очень важный вопрос.

---

V8 умеет:

```txt
выполнять JavaScript
```

---

Но V8 НЕ умеет:

```txt
читать файлы
открывать сокеты
работать с сетью
работать с ОС
```

---

# Что добавляет Node

Node добавляет:

```txt
libuv
fs
http
crypto
timers
streams
process
```

---

Поэтому:

```txt
V8
+
Node APIs
+
Libuv
=
Node Runtime
```

---

# Heap и Stack

V8 хранит данные в памяти.

---

Stack:

```txt
Function Calls
Primitive Values
References
```

---

Heap:

```txt
Objects
Arrays
Closures
Functions
```

---

# Garbage Collection

V8 автоматически очищает память.

---

Главная идея:

```txt
Недостижимые объекты удаляются
```

---

Пример:

```js
let user = {
  name: 'Max'
};

user = null;
```

---

Старый объект становится недостижимым.

GC сможет его удалить.

---

# Частая проблема

Memory Leak.

---

Например:

```js
const cache = [];

setInterval(() => {
  cache.push(largeObject);
}, 1000);
```

---

Объекты никогда не освобождаются.

Память постоянно растет.

---

# Почему V8 такой быстрый

Причины:

- JIT Compilation
- TurboFan
- Hidden Classes
- Inline Cache
- Оптимизированный GC

---

# Interview Answer

V8 — это JavaScript Engine, который отвечает за парсинг, компиляцию и выполнение JavaScript кода. Он использует JIT-компиляцию, оптимизации TurboFan, Hidden Classes и Inline Cache для достижения высокой производительности. Node.js использует V8 как движок выполнения, а поверх него добавляет libuv и системные API для работы с файлами, сетью и операционной системой.