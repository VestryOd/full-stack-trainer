# Event Loop: глубокий разбор

## Три компонента, без которых нет понимания

Прежде чем разбирать алгоритм, нужно чётко понять три вещи, которые постоянно взаимодействуют.

### Call Stack (Стек вызовов)

LIFO-стек фреймов выполнения. Каждый вызов функции добавляет фрейм наверх; возврат из функции удаляет его. **Run-to-completion**: движок не может прервать выполняющуюся JS-функцию — Event Loop получает управление только когда стек **полностью пуст**.

```js
function a() { b(); }
function b() { c(); }
function c() { console.log('c'); }

a();
// Стек в момент console.log:
// [c] ← top
// [b]
// [a]
// [global]
```

### Task Queue / Macrotask Queue (Очередь задач)

FIFO-очередь. Источники задач:
- `setTimeout` / `setInterval` (по истечении времени)
- События пользователя (клик, ввод)
- I/O callbacks (network, file — в Node.js)
- `postMessage` / `MessageChannel`
- `setImmediate` (только Node.js)

**"Macrotask" — не термин спецификации HTML** (там просто "task"), но слово устоялось в сообществе для разграничения с микрозадачами.

### Microtask Queue (Очередь микрозадач)

Отдельная очередь с более высоким приоритетом. Источники:
- `Promise.then` / `.catch` / `.finally` (всегда, даже если Promise уже resolved)
- `queueMicrotask(fn)`
- `MutationObserver` (браузер)
- `process.nextTick` (Node.js — особый случай, см. ниже)

## Полный алгоритм Event Loop

### Браузерный Event Loop (HTML spec)

```txt
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   1. Взять ОДНУ задачу из Task Queue (если есть)           │
│      ↓                                                      │
│   2. Выполнить задачу (run-to-completion)                   │
│      ↓                                                      │
│   3. Выполнить ВСЕ микрозадачи из Microtask Queue          │
│      (включая те, что добавлены во время обработки)         │
│      ↓                                                      │
│   4. [Rendering opportunity] — если нужно:                  │
│      requestAnimationFrame → style → layout → paint         │
│      ↓                                                      │
│   5. → вернуться к шагу 1                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Критический момент шага 3**: Microtask Queue дренируется **полностью** — не одна микрозадача, а все до последней. Если микрозадача добавляет новую микрозадачу, та тоже выполняется до следующей макрозадачи. Бесконечный цикл микрозадач заблокирует Event Loop навсегда.

```js
// ❌ Бесконечный цикл микрозадач — страница зависнет
function infinite() {
  Promise.resolve().then(infinite);
}
infinite();
```

### Почему `Promise.then` всегда создаёт микрозадачу

Даже если Promise уже в состоянии `fulfilled`, `.then(cb)` **не вызывает `cb` синхронно**. Спецификация требует: реакция на Promise всегда помещается в Microtask Queue, никогда не выполняется немедленно. Это гарантирует предсказуемый порядок — код после `.then()` всегда выполняется раньше callback.

```js
const p = Promise.resolve(42); // уже resolved

p.then(v => console.log('then:', v));
console.log('sync');

// Вывод:
// 'sync'      ← синхронный код
// 'then: 42'  ← микрозадача, выполнена после опустошения стека
```

## Порядок выполнения: разбор через конкретные примеры

### Пример 1: базовый

```js
console.log('1');

setTimeout(() => console.log('2'), 0);

Promise.resolve()
  .then(() => console.log('3'))
  .then(() => console.log('4'));

console.log('5');
```

<details>
<summary>Разбор пошагово</summary>

```txt
Синхронный код (одна задача: "script"):
  console.log('1')  → вывод: 1
  setTimeout(...)   → добавляет задачу в Task Queue
  Promise.resolve().then('3') → добавляет микрозадачу '3'
  console.log('5')  → вывод: 5

Стек пуст → дренируем Microtask Queue:
  Микрозадача '3':
    console.log('3') → вывод: 3
    .then('4')        → добавляет новую микрозадачу '4'
  Микрозадача '4':
    console.log('4') → вывод: 4
  Microtask Queue пуст

Следующая итерация Event Loop — берём задачу из Task Queue:
  setTimeout callback:
    console.log('2') → вывод: 2

Итог: 1, 5, 3, 4, 2
```

</details>

### Пример 2: вложенные микрозадачи

```js
// Predict the output:
Promise.resolve()
  .then(() => {
    console.log('A');
    Promise.resolve().then(() => console.log('B'));
  })
  .then(() => console.log('C'));

Promise.resolve().then(() => console.log('D'));
```

<details>
<summary>Разбор пошагово</summary>

```txt
Синхронный код:
  .then('A + inner B')   → Microtask Queue: [mA]
  .then('D')             → Microtask Queue: [mA, mD]
  (второй .then('C') зарегистрирован на первом Promise, но ждёт разрешения mA)

Дренируем Microtask Queue:

Итерация 1 — mA:
  console.log('A')       → вывод: A
  Promise.resolve().then('B') → добавляет mB в очередь
  mA завершилась → первый Promise теперь resolved → добавляет mC
  Microtask Queue: [mD, mB, mC]

Итерация 2 — mD:
  console.log('D')       → вывод: D
  Microtask Queue: [mB, mC]

Итерация 3 — mB:
  console.log('B')       → вывод: B
  Microtask Queue: [mC]

Итерация 4 — mC:
  console.log('C')       → вывод: C

Итог: A, D, B, C
```

Ключевая ловушка: `mC` ставится в очередь только **после** завершения `mA` (так как `mC` — это `.then` на промисе, который разрешается завершением `mA`). К тому моменту `mD` и `mB` уже в очереди.

</details>

### Пример 3: смешанный — setTimeout + Promise + async/await

```js
// Predict the output:
async function asyncFn() {
  console.log('async start');
  await Promise.resolve();
  console.log('after await');
}

console.log('1');
setTimeout(() => console.log('timeout'), 0);
asyncFn();
console.log('2');
```

<details>
<summary>Разбор пошагово</summary>

```txt
Синхронный код:
  console.log('1')      → вывод: 1
  setTimeout(...)       → Task Queue: [timeout]
  asyncFn():
    console.log('async start') → вывод: async start
    await Promise.resolve()
    → await "разворачивается" как .then()
    → всё, что после await, помещается как микрозадача
    → asyncFn приостанавливается, управление возвращается
  console.log('2')      → вывод: 2

Стек пуст → Microtask Queue: ['after await']

  'after await':
    console.log('after await') → вывод: after await

Следующая итерация Event Loop:
  Task Queue: [timeout]
  console.log('timeout')  → вывод: timeout

Итог: 1, async start, 2, after await, timeout
```

`async/await` — синтаксический сахар над Promise, поэтому "продолжение после await" всегда попадает в Microtask Queue, а не в Task Queue.

</details>

### Пример 4: составной — для senior-интервью

```js
// Predict the output:
console.log('start');

setTimeout(() => {
  console.log('timeout 1');
  Promise.resolve().then(() => console.log('promise inside timeout'));
}, 0);

setTimeout(() => console.log('timeout 2'), 0);

new Promise((resolve) => {
  console.log('promise executor');
  resolve();
}).then(() => {
  console.log('then 1');
  return Promise.resolve();
}).then(() => console.log('then 2'));

Promise.resolve().then(() => console.log('then 3'));

console.log('end');
```

<details>
<summary>Разбор пошагово</summary>

```txt
Синхронный код:
  'start'                → вывод: start
  setTimeout 1           → Task Queue: [t1]
  setTimeout 2           → Task Queue: [t1, t2]
  new Promise(executor):
    'promise executor'   → вывод: promise executor (executor синхронный!)
    resolve()            → Promise resolved
  .then('then 1')        → Microtask: [m1]
  .then('then 3')        → Microtask: [m1, m3]
  'end'                  → вывод: end

Дренируем Microtask Queue:
  m1 ('then 1'):
    'then 1'             → вывод: then 1
    return Promise.resolve() → второй .then('then 2') ждёт этого промиса
                          → добавляет m2 в очередь
    Microtask: [m3, m2]

  m3 ('then 3'):
    'then 3'             → вывод: then 3
    Microtask: [m2]

  m2 ('then 2'):
    'then 2'             → вывод: then 2
    Microtask: []

Task Queue: [t1, t2]
  t1 ('timeout 1'):
    'timeout 1'          → вывод: timeout 1
    Promise.resolve().then(...) → Microtask: [mp]
  Дренируем Microtask Queue:
    mp: 'promise inside timeout' → вывод: promise inside timeout
  t2 ('timeout 2'):
    'timeout 2'          → вывод: timeout 2

Итог: start, promise executor, end, then 1, then 3, then 2,
      timeout 1, promise inside timeout, timeout 2
```

</details>

## Node.js: `process.nextTick` vs `queueMicrotask` vs `Promise.then`

В Node.js Microtask Queue устроена иначе — в ней два уровня приоритета:

```txt
Node.js порядок после каждой задачи (и между фазами event loop):

  1. nextTick Queue    ← process.nextTick()
     (дренируется полностью)
  2. Microtask Queue  ← Promise.then(), queueMicrotask()
     (дренируется полностью)
  3. Следующая фаза event loop / следующая задача
```

```js
// Только Node.js:
Promise.resolve().then(() => console.log('promise'));
process.nextTick(() => console.log('nextTick'));
queueMicrotask(() => console.log('queueMicrotask'));
console.log('sync');

// Вывод:
// sync
// nextTick        ← nextTick Queue первым
// promise         ← Promise microtask
// queueMicrotask  ← queueMicrotask (та же очередь, что Promise, FIFO)
```

**Почему `process.nextTick` имеет высший приоритет?** Исторически он был добавлен до Promise и имел семантику "выполнить перед следующей итерацией event loop". Его приоритет над Promise — наследие API, не дизайнерское решение. В современном коде `process.nextTick` следует использовать только тогда, когда нужна именно эта семантика "раньше всех промисов".

**Рекурсивный `process.nextTick` — опасная ловушка:**

```js
// ❌ Заблокирует event loop в Node.js: nextTick Queue дренируется до пуста
// перед Promise — если nextTick добавляет новый nextTick, цикл не завершится
function blockNode() {
  process.nextTick(blockNode);
}
blockNode();
```

## Rendering и Event Loop в браузере

Рендеринг (layout, paint) происходит **между задачами**, не между микрозадачами. Микрозадачи — часть той же "задачи" с точки зрения рендеринга.

```js
// Это НЕ создаст промежуточный визуальный эффект:
button.addEventListener('click', () => {
  element.style.color = 'red';
  Promise.resolve().then(() => {
    element.style.color = 'blue';
  });
  // Пользователь увидит только 'blue' — рендер произойдёт
  // после дренирования всех микрозадач
});
```

`requestAnimationFrame` выполняется **в конце той задачи, перед рендером** — он идеален для анимаций, но не гарантирует точный тайминг в мс.

```txt
Задача → Microtask Queue (полностью) → rAF → Рендер → следующая задача
```

## `queueMicrotask` vs `Promise.resolve().then`

Функционально — одинаковы (оба добавляют в Microtask Queue). Разница:
- `Promise.resolve().then(fn)` — создаёт Promise объект (дополнительная аллокация)
- `queueMicrotask(fn)` — напрямую в очередь, без Promise, без возможности передать значение или обработать ошибку

```js
// Предпочтительнее там, где нужна только микрозадача без Promise-семантики:
queueMicrotask(() => {
  // выполнится как микрозадача, без создания лишнего Promise объекта
});
```

## Связь с другими темами

```txt
[Асинхронные паттерны]   — Promise internals, async/await как сахар над
                            микрозадачами разбираются в следующей статье
[Node.js Event Loop]     — фазы libuv (timers, poll, check, close) детально
                            в теме Node.js; здесь — только JS-уровень
[Генераторы]             — async generator + for-await-of работает через
                            тот же Microtask Queue под капотом
[Производительность]     — долгие синхронные задачи блокируют Event Loop;
                            мониторинг через PerformanceObserver / monitorEventLoopDelay
```

## Типичные ошибки на интервью

- **"Микрозадачи выполняются между макрозадачами"** — упрощение, которое не объясняет главного: Microtask Queue дренируется **полностью** после каждой задачи (и вообще в любой checkpoint). Новые микрозадачи, добавленные во время обработки, тоже выполняются до следующей задачи.

- **"Promise.then выполняется, когда Promise resolved"** — Promise может быть resolved, но callback выполнится только когда стек опустеет и Event Loop достигнет Microtask Queue. Синхронный код после `.then()` всегда выполнится первым.

- **"setTimeout(fn, 0) — это сразу"** — нет. Во-первых, минимальная задержка в браузерах обычно 1–4 мс (4 мс после нескольких вложенных setTimeout). Во-вторых, задача попадёт в очередь и выполнится только после всех текущих задач и всех накопившихся микрозадач.

- **"queueMicrotask и Promise.resolve().then — одно и то же"** — функционально близко, но `queueMicrotask` не создаёт Promise объект и не имеет `.catch` семантики. Ошибка в `queueMicrotask` не перехватывается через `.catch`.

- **Не знать порядок `process.nextTick` vs Promise в Node.js** — nextTick Queue обрабатывается раньше Microtask Queue. Это не "деталь реализации" — это задокументированное поведение, важное для понимания порядка в Node.js приложениях.

- **"Рендер происходит между микрозадачами"** — нет. С точки зрения рендеринга, вся задача + все её микрозадачи — это один атомарный блок. Рендер (если нужен) происходит только после дренирования Microtask Queue.
