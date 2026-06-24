# Замыкания: механика

## Что такое замыкание — определение на уровне движка

Популярное объяснение: "замыкание — это функция, которая помнит переменные из своего лексического окружения". Это верно, но неточно. Точнее:

**Замыкание = функция + ссылка на Environment Record, в котором она была создана.**

Не копия переменных, не снимок значений — **живая ссылка** на сам объект Environment Record. Это принципиально: если переменная в том Environment Record изменится после создания функции, функция увидит новое значение.

В спецификации каждый Function Object имеет внутренний слот `[[Environment]]`:

```txt
Function Object {
  [[Call]]          — алгоритм вызова функции
  [[Environment]]   → ссылка на Environment Record, в котором функция была создана
  [[FormalParameters]], [[ECMAScriptCode]], ...
}
```

Когда функция вызывается, движок создаёт новый Function Environment Record и устанавливает его `[[OuterEnv]]` = `[[Environment]]` функции. Так формируется scope chain.

**Каждая функция в JS — это замыкание.** Даже функция верхнего уровня замыкается на Global Environment Record. Термин "замыкание" обычно применяется к случаю, когда функция имеет нетривиальный `[[Environment]]` — то есть замыкается на что-то помимо глобального scope.

```js
function makeCounter() {
  let count = 0; // в Environment Record makeCounter

  return {
    increment() { count++; },  // [[Environment]] → ER makeCounter
    decrement() { count--; },  // [[Environment]] → ER makeCounter
    getValue()  { return count; }, // [[Environment]] → ER makeCounter
  };
}

const counter = makeCounter();
counter.increment();
counter.increment();
counter.decrement();
console.log(counter.getValue()); // 1

// Все три метода замыкаются на ОДИН И ТОТ ЖЕ ER makeCounter.
// Изменение count через increment видно через getValue — потому что
// это одна переменная в одном ER, не три копии.
```

## Классическая ловушка `var` в цикле — механическое объяснение

```js
// Predict the output:
for (var i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 0);
}
// ?
```

<details>
<summary>Ответ</summary>

**`3, 3, 3`**

Вот что происходит пошагово:

1. `var i` объявлена в VariableEnvironment **функции (или глобального контекста)**. Блок `for` не создаёт нового scope для `var`.
2. Создаются три callback-а стрелочных функции. У каждой `[[Environment]]` = тот же ER (с переменной `i`). Это одна ссылка на один `i`, не три копии.
3. Цикл завершается. `i` становится `3`.
4. setTimeout callback-и помещаются в очередь задач и выполняются после завершения синхронного кода.
5. Каждый callback читает `i` из своего `[[Environment]]` — и все три видят **текущее** значение `i = 3`.

```txt
Environment Record (функции/глобальный):
  i → 3  ← все три callback-а читают отсюда
```

</details>

**Три способа исправить — с разной механикой:**

```js
// Способ 1: IIFE — создаём новый ER на каждой итерации (ES5-стиль)
for (var i = 0; i < 3; i++) {
  (function(captured) {
    setTimeout(() => console.log(captured), 0);
  })(i);
  // IIFE создаёт новый ER с отдельным `captured`,
  // инициализированным текущим значением i
}
// 0, 1, 2 ✅

// Способ 2: let — спецификация предписывает создавать новый binding на каждой итерации
for (let i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 0);
}
// 0, 1, 2 ✅
// Механика: на каждой итерации создаётся новый LexicalEnvironment
// с копией i, проинициализированной текущим значением

// Способ 3: замкнуть значение через параметр функции
for (var i = 0; i < 3; i++) {
  setTimeout(console.log.bind(null, i), 0);
}
// 0, 1, 2 ✅ — bind фиксирует аргумент в момент вызова
```

## Замыкания и память — что V8 реально удерживает

Замыкания — один из основных источников утечек памяти в JS. Чтобы понять почему, нужно знать, что именно движок удерживает в памяти.

### Что GC считает "живым"

Сборщик мусора V8 (поколенческий mark-and-sweep) удерживает объект, если на него есть **reachable ссылка** — то есть путь от GC roots (стек, глобальные переменные, живые замыкания).

Замыкание удерживает весь Environment Record, на который ссылается его `[[Environment]]`. Это означает: если хотя бы одна функция жива и замыкается на ER, весь ER остаётся в памяти, даже если живая функция не использует все переменные из этого ER.

```js
function createLeak() {
  const hugeData = new Array(1_000_000).fill('leak'); // 1M элементов
  const smallData = 'tiny';

  // Эта функция использует только smallData,
  // но замыкается на ER createLeak, который содержит hugeData
  return function() {
    return smallData;
  };
}

const fn = createLeak();
// fn жива → ER createLeak жив → hugeData жив
// hugeData НЕ будет собран GC, даже если fn никогда не обращается к нему
```

### V8 context-оптимизация (и её предел)

V8 выполняет **closure analysis**: при компиляции функции анализирует, какие переменные из внешних scope реально используются. Переменные, которые не используются ни одной живой inner function, могут быть исключены из "захваченного" Environment Record.

Однако: если несколько функций замыкаются на **один и тот же** ER, V8 использует **общий Context object** для всех них. Если хотя бы одна из этих функций использует "большую" переменную, Context удерживает её для всех — даже для тех функций, которые её не используют.

```js
function problem() {
  const huge = new Array(1_000_000).fill(0);
  const small = 'ok';

  const useSmall = () => small;   // не использует huge
  const useHuge  = () => huge;    // использует huge

  return useSmall; // возвращаем только useSmall
  // Но! useHuge и useSmall создавались в одном scope →
  // V8 создаёт один общий Context object с И huge, И small.
  // Даже после возврата useSmall, huge остаётся в памяти,
  // потому что Context жив из-за useSmall.
}
```

Это известная проблема, документированная в статье Vyacheslav Egorov (разработчик V8) и подтверждённая в Chrome DevTools через heap snapshots.

### Основные сценарии утечек через замыкания

**1. Забытые таймеры:**
```js
class Widget {
  constructor() {
    this.data = new Array(100_000).fill('data');
    // setInterval удерживает callback, callback замыкается на this,
    // this удерживает data — весь граф живёт, пока таймер жив
    this.timer = setInterval(() => {
      console.log('tick', this.data.length);
    }, 1000);
  }

  destroy() {
    clearInterval(this.timer); // ✅ без этого — утечка
  }
}
```

**2. Отсоединённые DOM-узлы:**
```js
function setup() {
  const button = document.getElementById('btn');
  const cache = new Array(100_000).fill('cached'); // большие данные

  button.addEventListener('click', () => {
    console.log(cache.length); // замыкается на cache
  });

  // Если button удалится из DOM, но listener не удалён —
  // button (detached node) и cache живут в памяти
  document.body.removeChild(button);
  // ❌ нужно: button.removeEventListener('click', handler)
  // или AbortController
}
```

**3. Глобальные коллекции, накапливающие замыкания:**
```js
const handlers = []; // глобальный массив

function register(id) {
  const data = fetchLargeData(id); // тяжёлые данные
  handlers.push(() => process(data)); // замыкание живёт пока handlers жив
}

// Если handlers никогда не очищается → утечка пропорциональна числу вызовов register
```

**WeakRef и FinalizationRegistry** (ES2021) — инструменты для работы с GC-чувствительными ссылками, подробно разобраны в [Управление памятью].

## Практические паттерны на замыканиях

### Паттерн модуля (Module Pattern)

До ESM единственным способом создать "приватные" переменные было замыкание через IIFE:

```js
const userStore = (() => {
  // Приватное состояние — недоступно снаружи
  const users = new Map();
  let nextId = 1;

  // Приватная функция
  function generateId() {
    return nextId++;
  }

  // Публичный API
  return {
    add(name) {
      const id = generateId();
      users.set(id, { id, name });
      return id;
    },
    get(id) {
      return users.get(id);
    },
    count() {
      return users.size;
    },
  };
})();

userStore.add('Alice'); // 1
userStore.add('Bob');   // 2
userStore.count();      // 2
userStore.users;        // undefined — приватно
```

### Фабричные функции и приватное состояние

Более гибкий вариант модульного паттерна — без синглтона:

```js
function createStack() {
  const items = []; // приватно

  return {
    push(item) { items.push(item); },
    pop() {
      if (items.length === 0) throw new Error('Stack is empty');
      return items.pop();
    },
    peek() { return items[items.length - 1]; },
    get size() { return items.length; },
    [Symbol.iterator]() { return [...items].reverse().values(); },
  };
}

const stack = createStack();
stack.push(1);
stack.push(2);
stack.pop(); // 2
stack.items; // undefined — массив недоступен напрямую
```

### Мемоизация

```js
function memoize(fn) {
  const cache = new Map(); // замыкается внутри возвращаемой функции

  return function(...args) {
    const key = JSON.stringify(args);
    if (cache.has(key)) {
      return cache.get(key);
    }
    const result = fn.apply(this, args);
    cache.set(key, result);
    return result;
  };
}

const expensiveCalc = memoize((n) => {
  console.log(`Computing for ${n}...`);
  return n * n;
});

expensiveCalc(5); // "Computing for 5..." → 25
expensiveCalc(5); // → 25 (из cache, без лога)
expensiveCalc(6); // "Computing for 6..." → 36
```

Нюанс: `JSON.stringify` как ключ не работает для объектов с циклическими ссылками и функций. Для сложных случаев — используют `Map` с первым аргументом как ключом + рекурсивный подход (см. библиотеки типа `fast-memoize`).

### Once — функция, которая выполняется только раз

```js
function once(fn) {
  let called = false;
  let result;

  return function(...args) {
    if (!called) {
      called = true;
      result = fn.apply(this, args);
    }
    return result;
  };
}

const initialize = once(() => {
  console.log('Init!');
  return { ready: true };
});

initialize(); // "Init!" → { ready: true }
initialize(); // → { ready: true } (без лога)
initialize(); // → { ready: true }
```

## Predict the output — цепочка замыканий

```js
function makeAdder(x) {
  return function(y) {
    return x + y;
  };
}

const add5 = makeAdder(5);
const add10 = makeAdder(10);

console.log(add5(3));   // ?
console.log(add10(3));  // ?
console.log(add5(add10(1))); // ?

// Модифицируем: что если x — объект?
function makeObjectAdder(obj) {
  return function(val) {
    obj.value += val; // мутируем объект!
    return obj.value;
  };
}

const counter = { value: 0 };
const inc = makeObjectAdder(counter);

inc(1); // ?
inc(2); // ?
console.log(counter.value); // ?
```

<details>
<summary>Ответ</summary>

```
8   // add5(3) = 5 + 3
13  // add10(3) = 10 + 3
16  // add10(1) = 11, add5(11) = 5 + 11

// makeObjectAdder:
1   // inc(1): counter.value = 0 + 1 = 1
3   // inc(2): counter.value = 1 + 2 = 3
3   // counter.value: мутация объекта видна снаружи
```

Последний пример демонстрирует, что замыкание держит **ссылку** на объект, а не копию его значения. Мутация объекта через замыкание видна всем, кто держит ссылку на тот же объект.

</details>

## Замыкания vs Классы — когда что выбирать

```js
// Фабричная функция (замыкание)
function createUser(name) {
  let _name = name; // приватно

  return {
    getName() { return _name; },
    setName(n) { _name = n; },
  };
}

// Класс (через # private fields или конвенцию)
class User {
  #name; // действительно приватно (ES2022)

  constructor(name) { this.#name = name; }
  getName() { return this.#name; }
  setName(n) { this.#name = n; }
}
```

**Фабричная функция:** каждый метод — отдельный объект-функция в памяти, нет prototype-цепочки. При создании 10 000 объектов — 10 000 копий каждого метода. Приватность — через closure.

**Класс:** методы живут в `User.prototype`, все экземпляры делят один набор методов. Приватность через `#` — на уровне движка. Более эффективно по памяти при множестве экземпляров.

## Связь с другими темами

```txt
[Контексты выполнения] — замыкание = [[Environment]] функции → ER,
                          созданный во время execution context
[this-binding]         — стрелочная функция захватывает this через тот
                          же механизм: отсутствие собственного ThisBinding
                          + разрешение через Scope Chain (через ER)
[Управление памятью]   — замыкания как основная причина утечек; WeakMap/WeakRef
                          как инструменты для GC-безопасных ссылок
[Генераторы]           — генераторная функция хранит состояние в своём ER,
                          приостанавливая выполнение — это замыкание + control flow
```

## Типичные ошибки на интервью

- **"Замыкание — это копия переменных"** — нет. Это живая ссылка на Environment Record. Изменение переменной видно всем замыканиям, ссылающимся на тот же ER. Var-в-цикле работает именно так: все callbacks видят одну переменную, потому что замкнуты на один ER.

- **"Замыкание удерживает только те переменные, которые использует"** — частично верно для V8 при отсутствии других замыканий на тот же ER. Но если несколько функций замыкаются на один ER, V8 создаёт общий Context object, удерживающий всё, что используется хотя бы одной из них. Это реальная причина "неожиданных" утечек.

- **"Паттерн модуля устарел — теперь есть классы"** — это разные инструменты. Классы с `#`-полями дают true privacy, но module pattern всё ещё применяется для синглтонов и конфигурации без необходимости `new`.

- **"Исправить var-в-цикле можно только через let"** — let — самый чистый способ, но исторически IIFE и `bind` тоже работают и иногда встречаются в legacy-коде.

- **Не видеть утечку в паттернах с таймерами и событиями** — самая частая практическая ошибка. Замыкание в callback таймера/listener удерживает весь scope функции-родителя. `clearInterval`/`removeEventListener` — обязательны при teardown.

- **"Замыкание — это сложная концепция, специфичная для JS"** — нет. Замыкания есть в большинстве современных языков (Python, Go, Rust, Swift). В JS они особенно заметны из-за широкого использования callback-паттернов и асинхронного кода.
