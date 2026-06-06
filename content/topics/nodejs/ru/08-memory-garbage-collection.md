<!-- verified: 2026-06-05, corrections: 0 -->
# Memory, Heap, Stack и Garbage Collection

## Самая опасная проблема продакшена

Большинство Node приложений падают не из-за Event Loop.

---

Обычно проблема:

```txt
Memory Leak
```

---

# Как устроена память

Упрощенно:

```txt
Stack
Heap
```

---

# Stack

Хранит:

```txt
Function Calls
Primitive Values
References
```

---

Пример:

```js
function sum(a, b) {
  return a + b;
}
```

---

Во время вызова создается:

```txt
Stack Frame
```

---

После завершения функции:

```txt
удаляется
```

---

# Heap

Здесь живут:

```txt
Objects
Arrays
Functions
Closures
```

---

Пример:

```js
const user = {
  name: 'Max'
};
```

---

Объект будет храниться в Heap.

---

# Почему Heap важен

Практически все memory leaks происходят именно здесь.

---

# Garbage Collector

GC автоматически очищает память.

---

Главная идея:

```txt
Удаляем недостижимые объекты
```

---

# Reachability

Объект считается живым,
если до него можно добраться.

---

Например:

```js
const user = {
  name: 'Max'
};
```

---

Объект достижим.

---

# Недостижимый объект

```js
let user = {
  name: 'Max'
};

user = null;
```

---

Старый объект больше никому не нужен.

---

GC сможет удалить его.

---

# Mark and Sweep

Основной алгоритм GC.

---

Шаг 1

Mark.

---

GC начинает обход от Root Objects.

---

Например:

```txt
global
closures
stack
```

---

Помечает достижимые объекты.

---

Шаг 2

Sweep.

---

Все непомеченные объекты:

```txt
удаляются
```

---

# Generational GC

Очень популярный вопрос.

---

Наблюдение:

Большинство объектов живут недолго.

---

Например:

```js
req
res
temporary arrays
```

---

Поэтому V8 делит память:

```txt
Young Generation
Old Generation
```

---

# Young Generation

Новые объекты.

---

Обычно очищается часто.

---

Очень быстро.

---

# Old Generation

Долгоживущие объекты.

---

Например:

```txt
Cache
Singletons
Global Objects
```

---

Очищается значительно дороже.

---

# Почему GC вызывает лаги

Во время некоторых фаз:

```txt
JavaScript приостанавливается
```

---

Это называется:

```txt
Stop The World
```

---

Современный V8 уменьшает такие паузы,
но полностью не устраняет.

---

# Memory Leak

Очень популярный вопрос.

---

# Пример №1

Глобальный массив.

---

```js
const cache = [];

setInterval(() => {
  cache.push(hugeObject);
}, 1000);
```

---

Память растет бесконечно.

---

# Пример №2

Неудаленные listeners.

---

```js
emitter.on('event', handler);
```

---

Но:

```js
removeListener()
```

никогда не вызывается.

---

Получаем утечку.

---

# Пример №3

Замыкания.

---

```js
function create() {

  const hugeArray = [];

  return () => {
    console.log(hugeArray.length);
  };
}
```

---

Closure удерживает hugeArray.

---

GC не сможет удалить массив.

---

# Симптомы Memory Leak

Постепенно растет:

```txt
Heap Usage
RSS
GC Time
```

---

Со временем:

```txt
OOM
```

---

Out Of Memory.

---

# Как искать утечки

Самые популярные инструменты.

---

```txt
Chrome DevTools
Heap Snapshot
Node Inspector
clinic.js
```

---

# Heap Snapshot

Позволяет увидеть:

```txt
что занимает память
```

---

Очень часто используется в production расследованиях.

---

# Process Memory

```js
console.log(
  process.memoryUsage()
);
```

---

Показывает:

```txt
rss
heapUsed
heapTotal
external
```

---

# RSS

Resident Set Size.

---

Вся память процесса.

---

# heapUsed

Наиболее интересный показатель.

---

Сколько Heap реально используется.

---

# Очень популярный вопрос

Почему память не уменьшается после GC?

---

Потому что:

```txt
V8 может сохранить выделенную память
для будущего использования
```

---

И не возвращать её ОС сразу.

---

# Частый вопрос

Почему приложение может тормозить при большом количестве объектов?

---

Ответ:

GC приходится обходить больше объектов.

---

Увеличивается:

```txt
GC pressure
Pause time
CPU usage
```

---

# Senior Interview Answer

V8 использует автоматическую сборку мусора на основе алгоритмов Mark-and-Sweep и Generational GC. Объекты размещаются в Heap и удаляются, когда становятся недостижимыми. Наиболее распространенные причины memory leaks в Node.js — глобальные коллекции, неочищенные Event Listeners и замыкания, удерживающие большие объекты в памяти.