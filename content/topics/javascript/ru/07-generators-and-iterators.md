# Генераторы и итераторы

## Протокол итерации — контракт на уровне спецификации

JavaScript определяет два связанных протокола. Любой объект может реализовать их и получить совместимость с `for...of`, spread, деструктуризацией и `Array.from`.

### Iterable (Итерируемый объект)

Объект является **iterable**, если у него есть метод `[Symbol.iterator]()`, возвращающий **Iterator**.

```ts
interface Iterable<T> {
  [Symbol.iterator](): Iterator<T>;
}
```

### Iterator (Итератор)

Объект является **iterator**, если у него есть метод `next()`, возвращающий `IteratorResult`.

```ts
interface Iterator<T> {
  next(value?: unknown): IteratorResult<T>;
  return?(value?: unknown): IteratorResult<T>; // опциональный: ранний выход
  throw?(error?: unknown): IteratorResult<T>;  // опциональный: бросить внутрь
}

interface IteratorResult<T> {
  value: T | undefined;
  done: boolean;
}
```

**Контракт**: `done: false` — значение доступно; `done: true` — итерация завершена, `value` обычно `undefined` (или финальное возвращаемое значение у генераторов).

### Встроенные итерируемые объекты

```js
// Все они реализуют Symbol.iterator:
[1, 2, 3][Symbol.iterator]();       // ArrayIterator
'hello'[Symbol.iterator]();         // StringIterator (по Unicode code points!)
new Map([[1,'a']])[Symbol.iterator](); // MapIterator (entries)
new Set([1,2])[Symbol.iterator]();  // SetIterator

// for...of, spread, деструктуризация, Array.from — всё через Symbol.iterator:
const [a, b] = new Set([10, 20, 30]); // a=10, b=20
const chars = [...'hello']; // ['h', 'e', 'l', 'l', 'o']
```

### Ручная реализация итератора

```js
function range(start, end, step = 1) {
  return {
    // Объект является и iterable, и iterator одновременно
    [Symbol.iterator]() { return this; },
    next() {
      if (start < end) {
        const value = start;
        start += step;
        return { value, done: false };
      }
      return { value: undefined, done: true };
    },
  };
}

for (const n of range(0, 10, 2)) {
  console.log(n); // 0, 2, 4, 6, 8
}

console.log([...range(1, 4)]); // [1, 2, 3]
```

## Генераторные функции и механика `yield`

### Что такое генератор

`function*` возвращает **объект-генератор**, который одновременно является:
- **Iterator** — имеет метод `next()`
- **Iterable** — `gen[Symbol.iterator]()` возвращает `gen` (себя)

```js
function* simple() {
  yield 1;
  yield 2;
  yield 3;
}

const gen = simple();

// Как Iterator:
gen.next(); // { value: 1, done: false }
gen.next(); // { value: 2, done: false }
gen.next(); // { value: 3, done: false }
gen.next(); // { value: undefined, done: true }

// Как Iterable:
gen[Symbol.iterator]() === gen; // true

// Но gen уже израсходован. Новый — из функции:
console.log([...simple()]); // [1, 2, 3]
```

### Модель приостановки — что реально происходит

Генератор поддерживает **четыре внутренних состояния**:

```txt
suspendedStart → executing → suspendedYield → completed
                               ↑___________↓  (цикл yield)
```

Ключевое: при `yield` движок **сохраняет весь контекст выполнения** (локальные переменные, позицию в коде, scope chain) — и возвращает управление вызывающему коду. При следующем `next()` — восстанавливает контекст и продолжает с того места.

Это принципиально отличается от closure: closure сохраняет Environment Record, но не позицию выполнения. Генератор сохраняет и то, и другое.

```js
function* stateful() {
  let x = 0;
  while (true) {
    x++;
    const reset = yield x; // yield возвращает значение, переданное в next()
    if (reset) x = 0;
  }
}

const counter = stateful();
counter.next();    // { value: 1, done: false }
counter.next();    // { value: 2, done: false }
counter.next();    // { value: 3, done: false }
counter.next(true); // { value: 1, done: false } — reset=true, x сброшен в 0, потом x++
counter.next();    // { value: 2, done: false }
```

### Двунаправленная коммуникация через `yield`

`yield` — не просто "вернуть значение". Это **точка обмена**: генератор отдаёт значение наружу, а при возобновлении получает новое значение внутрь.

```js
// Predict the output:
function* echo() {
  console.log('start');
  const a = yield 'first';    // получит значение из next(...)
  console.log('got:', a);
  const b = yield 'second';
  console.log('got:', b);
  return 'done';
}

const g = echo();

const r1 = g.next('ignored'); // первый next(): запускает генератор
                               // значение 'ignored' НИКУДА не идёт
                               // (нет yield, которому его передавать)
console.log(r1);               // ?

const r2 = g.next('hello');   // возобновляет, 'hello' → a
console.log(r2);               // ?

const r3 = g.next('world');   // возобновляет, 'world' → b
console.log(r3);               // ?

const r4 = g.next();           // генератор завершён
console.log(r4);               // ?
```

<details>
<summary>Разбор</summary>

```txt
g.next('ignored'):
  Запускает генератор с suspendedStart
  'start' → вывод: start
  yield 'first' → приостановка
  r1 = { value: 'first', done: false }

g.next('hello'):
  Возобновляет; 'hello' = значение выражения (yield 'first')
  a = 'hello'
  'got: hello' → вывод: got: hello
  yield 'second' → приостановка
  r2 = { value: 'second', done: false }

g.next('world'):
  Возобновляет; 'world' = значение (yield 'second')
  b = 'world'
  'got: world' → вывод: got: world
  return 'done' → завершение
  r3 = { value: 'done', done: true }

g.next():
  Генератор уже completed
  r4 = { value: undefined, done: true }

Итог:
  start
  { value: 'first', done: false }
  got: hello
  { value: 'second', done: false }
  got: world
  { value: 'done', done: true }
  { value: undefined, done: true }
```

</details>

### `yield*` — делегирование

`yield*` делегирует итерацию другому iterable и возвращает его финальное значение (`return` генератора):

```js
function* inner() {
  yield 'b';
  yield 'c';
  return 'inner_done'; // это значение yield* выражения во внешнем генераторе
}

function* outer() {
  yield 'a';
  const result = yield* inner(); // делегирует, result = 'inner_done'
  console.log('inner returned:', result);
  yield 'd';
}

console.log([...outer()]); // ['a', 'b', 'c', 'd']
// + вывод: inner returned: inner_done
```

`yield*` работает с **любым iterable**, не только с генераторами:

```js
function* flatten(arr) {
  for (const item of arr) {
    if (Array.isArray(item)) yield* flatten(item); // рекурсия
    else yield item;
  }
}

console.log([...flatten([1, [2, [3, 4]], 5])]); // [1, 2, 3, 4, 5]
```

### `return()` и `throw()` — внешнее управление генератором

```js
function* gen() {
  try {
    yield 1;
    yield 2;
  } finally {
    console.log('cleanup'); // выполнится при return() или throw()
  }
}

const g = gen();
g.next();         // { value: 1, done: false }
g.return('exit'); // 'cleanup' → { value: 'exit', done: true }
// Генератор завершён. Все последующие next() → { value: undefined, done: true }

// throw():
const g2 = gen();
g2.next();            // { value: 1, done: false }
g2.throw(new Error('boom'));
// 'cleanup' (finally)
// Error бросается в точке yield 1 — если там нет try/catch внутри генератора,
// ошибка всплывает к вызывающему коду
```

`for...of` автоматически вызывает `return()` на генераторе при досрочном выходе (`break`, `throw`, `return`):

```js
function* infinite() {
  let i = 0;
  try {
    while (true) yield i++;
  } finally {
    console.log('generator cleanup');
  }
}

for (const n of infinite()) {
  if (n > 2) break; // вызовет gen.return() → finally сработает
}
// 'generator cleanup'
```

## Асинхронные генераторы и `for-await-of`

`async function*` — асинхронный генератор. Умеет и `await`, и `yield`. Потребляется через `for await...of`.

```js
async function* paginate(url) {
  let page = 1;
  while (true) {
    const res = await fetch(`${url}?page=${page}`);
    const { data, hasMore } = await res.json();
    yield data; // отдаёт текущую страницу
    if (!hasMore) break;
    page++;
  }
}

// Потребление:
for await (const page of paginate('/api/items')) {
  processPage(page);
  // следующий fetch произойдёт только когда мы перейдём к следующей итерации
}
```

Асинхронный итерируемый объект реализует `[Symbol.asyncIterator]()`:

```js
const asyncIterable = {
  [Symbol.asyncIterator]() {
    let i = 0;
    return {
      async next() {
        await delay(100); // имитация async операции
        return i < 3
          ? { value: i++, done: false }
          : { value: undefined, done: true };
      },
    };
  },
};

for await (const val of asyncIterable) {
  console.log(val); // 0, 1, 2 — с задержками
}
```

## Практические паттерны

### Ленивые вычисления и бесконечные последовательности

```js
// Бесконечная последовательность Фибоначчи — не вычисляет всё сразу:
function* fibonacci() {
  let [a, b] = [0, 1];
  while (true) {
    yield a;
    [a, b] = [b, a + b];
  }
}

// Взять первые N элементов из любого infinite iterable:
function take(iterable, n) {
  const result = [];
  for (const item of iterable) {
    result.push(item);
    if (result.length >= n) break;
  }
  return result;
}

take(fibonacci(), 8); // [0, 1, 1, 2, 3, 5, 8, 13]

// Пайплайн ленивых трансформаций (без промежуточных массивов):
function* map(iterable, fn) {
  for (const item of iterable) yield fn(item);
}

function* filter(iterable, predicate) {
  for (const item of iterable) {
    if (predicate(item)) yield item;
  }
}

const result = take(
  filter(
    map(fibonacci(), x => x * 2), // удвоить
    x => x % 3 === 0              // только делимые на 3
  ),
  5
);
// [0, 6, 12, 18, 24, ...] — ленивый пайплайн, не вычисляет лишнего
```

### Обход дерева

```js
function* dfsTree(node) {
  yield node.value;
  for (const child of node.children ?? []) {
    yield* dfsTree(child); // рекурсивное делегирование
  }
}

const tree = {
  value: 1,
  children: [
    { value: 2, children: [{ value: 4 }, { value: 5 }] },
    { value: 3, children: [{ value: 6 }] },
  ],
};

console.log([...dfsTree(tree)]); // [1, 2, 4, 5, 3, 6]
```

### Async pagination с обработкой ошибок

```js
async function* fetchAllUsers(baseUrl) {
  let cursor = null;

  do {
    const url = cursor ? `${baseUrl}?cursor=${cursor}` : baseUrl;
    const res = await fetch(url);

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const { users, nextCursor } = await res.json();
    yield users; // отдаём текущую пачку
    cursor = nextCursor;
  } while (cursor);
}

// Использование — единый интерфейс для любого объёма данных:
try {
  for await (const batch of fetchAllUsers('/api/users')) {
    await processBatch(batch);
  }
} catch (err) {
  console.error('Failed to fetch users:', err);
}
```

### Мемоизированный генератор (кеширование результатов итерации)

```js
function memoizeGenerator(generatorFn) {
  const cache = [];
  let gen = null;
  let done = false;

  return {
    [Symbol.iterator]() {
      let index = 0;
      return {
        next() {
          if (index < cache.length) {
            return { value: cache[index++], done: false };
          }
          if (done) {
            return { value: undefined, done: true };
          }
          gen ??= generatorFn();
          const result = gen.next();
          if (result.done) {
            done = true;
            return { value: undefined, done: true };
          }
          cache.push(result.value);
          index++;
          return result;
        },
      };
    },
  };
}

const expensiveSeq = memoizeGenerator(function* () {
  for (let i = 0; i < 5; i++) {
    console.log(`computing ${i}`);
    yield i * i;
  }
});

console.log([...expensiveSeq]); // computing 0-4, [0,1,4,9,16]
console.log([...expensiveSeq]); // нет логов — всё из кеша, [0,1,4,9,16]
```

## Связь с другими темами

```txt
[Замыкания]             — генератор сохраняет и Environment Record (замыкание),
                           и позицию выполнения (этого closure не умеет)
[Асинхронные паттерны]  — async/await внутри — это генератор + автоматический
                           Promise runner; for-await-of = async iterator protocol
[Proxy и Symbol]        — Symbol.iterator, Symbol.asyncIterator — well-known symbols,
                           позволяют любому объекту стать iterable
[Современный JS]        — Array.from(), spread, деструктуризация — все потребляют
                           Symbol.iterator; Array.fromAsync — Symbol.asyncIterator
```

## Типичные ошибки на интервью

- **"Генераторная функция выполняется при вызове"** — нет. `gen()` создаёт объект-генератор в состоянии `suspendedStart` и возвращает его. Код внутри не выполняется до первого `next()`.

- **"Первый `next(value)` передаёт значение в генератор"** — нет. Значение, переданное в первый `next()`, игнорируется — ему некуда идти (нет предшествующего `yield`). Первый `next()` только запускает генератор до первого `yield`.

- **"Генератор можно перезапустить"** — нет. После `done: true` генератор завершён навсегда. Для нового прохода нужно создать новый объект через повторный вызов генераторной функции.

- **"yield* работает только с другими генераторами"** — нет. `yield*` работает с любым iterable: массив, строка, Set, Map, другой генератор.

- **"Значение return в генераторе теряется"** — при `for...of` или spread — да, теряется. Но при ручном `next()` — `{ value: returnValue, done: true }`. А при `yield*` — значение return становится значением выражения `yield*` во внешнем генераторе. Три разных поведения.

- **"for-await-of работает с обычными итераторами"** — да, `for-await-of` работает и с синхронными iterables (оборачивает в Promise.resolve). Но `for...of` **не** работает с async iterables (Symbol.asyncIterator).

- **Не знать про `return()` и очистку ресурсов** — `for...of` с `break` вызывает `gen.return()`, что запускает `finally` блоки внутри генератора. Это важно для генераторов, удерживающих ресурсы (соединения, файлы).
