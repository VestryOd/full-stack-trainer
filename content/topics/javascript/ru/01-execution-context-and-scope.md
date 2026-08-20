# Контексты выполнения и область видимости

## Что такое контекст выполнения — переформулировка через спецификацию

Когда JavaScript-движок выполняет код, он создаёт **Execution Context** (контекст выполнения) — абстрактный контейнер, описанный в спецификации ECMAScript. Это не просто "окружение" в размытом смысле — у контекста есть конкретная внутренняя структура:

```txt
Execution Context
├── code evaluation state  — где "находится" выполнение
├── Function               — ссылка на Function Object или null
├── Realm                  — набор встроенных (Array, Object, …)
├── LexicalEnvironment     — где ищутся let/const и catch
├── VariableEnvironment    — где живут var и function-объявления
└── ThisBinding            — значение this
```

В стеке может быть много контекстов одновременно. Тот, что наверху стека — **Running Execution Context**.

```txt
         ┌───────────────────────────┐
         │  baz()  execution context │  ← running (текущий)
         ├───────────────────────────┤
         │  bar()  execution context │
         ├───────────────────────────┤
         │  foo()  execution context │
         ├───────────────────────────┤
         │  global execution context │  ← всегда в основании
         └───────────────────────────┘
                   Call Stack
```

## Две фазы создания контекста: creation vs execution

Каждый раз при вызове функции (или при старте скрипта) движок проходит через **две фазы**:

### Фаза создания (Creation Phase)

Движок сканирует тело функции (или глобальный код) и выполняет следующее **до запуска любой строки кода**:

1. Создаёт **Environment Record** (запись окружения)
2. Устанавливает **outer reference** — ссылку на лексически внешний Environment Record (это и есть механизм scope chain)
3. Определяет **`this`**
4. Обрабатывает объявления:
   - `var x` → создаёт привязку в VariableEnvironment, инициализирует `undefined`
   - `function foo() {}` → создаёт привязку в VariableEnvironment, инициализирует **полным function object**
   - `let y` / `const z` → создаёт привязку в LexicalEnvironment, но не инициализирует её — это Temporal Dead Zone (TDZ)

### Фаза выполнения (Execution Phase)

Движок выполняет код построчно. Присваивания происходят именно здесь.

```js
// Что видит движок в creation phase для этого кода:
console.log(a); // ?
console.log(b); // ?
console.log(c); // ?

var a = 1;
let b = 2;
function c() {}

// Creation phase result:
// a → undefined     (var: создано, инициализировано undefined)
// b → <TDZ>         (let: создано, НЕ инициализировано)
// c → function c(){} (function declaration: создано и инициализировано сразу)

// Execution phase:
// console.log(a) → undefined  ✅ (var существует, значение ещё undefined)
// console.log(b) → ReferenceError: Cannot access 'b' before initialization
// console.log(c) → function c(){} ✅ (полностью инициализирована)
```

**Хойстинг — это не "поднятие кода".** Это следствие двухфазной модели: привязки создаются в фазе создания, а код выполняется в фазе выполнения. Никакой магии — только порядок операций, предписанный спецификацией.

## Environment Records — что за ними стоит

Спецификация определяет иерархию Environment Records:

```txt
Environment Record (абстрактный)
├── Declarative ER          — let, const, function, class, import
│   ├── Function ER         — то же, + arguments object
│   └── Module ER           — import bindings (всегда live bindings)
├── Object ER               — var в глобальном коде (на globalThis)
└── Global ER               — составной: Declarative ER + Object ER
```

**Function Environment Record** — самый частый в работе. Хранит локальные переменные функции, `arguments`, `this` binding (для обычных функций).

**Global Environment Record** — составной: 
- `ObjectEnvironmentRecord` (обёртка над `globalThis`) — хранит `var`-переменные и function declarations как свойства глобального объекта
- `DeclarativeEnvironmentRecord` — хранит `let`/`const` на верхнем уровне (они **не** становятся свойствами `globalThis`)

```js
var x = 1;
let y = 2;

console.log(globalThis.x); // 1  — var стала свойством globalThis
console.log(globalThis.y); // undefined — let НЕ стала свойством globalThis
```

## LexicalEnvironment vs VariableEnvironment — зачем их два

До ES2015 — редакции стандарта 2015 года — они были одним и тем же. ES2015 ввёл `let`/`const` с блочной областью видимости, и их нужно было отделить от `var`.

```txt
function outer() {
  var a = 1;   // → VariableEnvironment (не зависит от блоков)
  let b = 2;   // → LexicalEnvironment (зависит от блоков)

  if (true) {
    var c = 3; // → VariableEnvironment функции outer(), не блока
    let d = 4; // → LexicalEnvironment блока if (только внутри)
  }

  console.log(a); // 1
  console.log(b); // 2
  console.log(c); // 3 — var "утекла" из блока
  console.log(d); // ReferenceError
}
```

Когда движок встречает `{` (блок), он создаёт новый Declarative Environment Record для `let`/`const` этого блока и делает его новым `LexicalEnvironment`. `VariableEnvironment` при этом не меняется — оно принадлежит функции или глобальному контексту.

## Scope Chain — механизм разрешения идентификаторов

Scope chain — это не отдельная структура. Это **цепочка ссылок `outer`** между Environment Records. Каждая запись имеет поле `[[OuterEnv]]`, указывающее на лексически объемлющую запись.

```js
const globalVar = 'global';

function outer() {
  const outerVar = 'outer';

  function inner() {
    const innerVar = 'inner';
    console.log(innerVar);  // найдено в inner's ER
    console.log(outerVar);  // найдено в outer's ER (через [[OuterEnv]])
    console.log(globalVar); // найдено в global ER (через [[OuterEnv]].[[OuterEnv]])
    console.log(missing);   // обходим всю цепочку → ReferenceError
  }

  inner();
}
```

**Ключевое**: `[[OuterEnv]]` определяется **лексически** (где функция написана в коде), а не **динамически** (откуда она вызвана). Это называется **лексической областью видимости (lexical scoping)**.

```js
// Predict the output:
const x = 'global';

function makeGetter() {
  const x = 'closure';
  return function get() {
    return x;
  };
}

const get = makeGetter();

function runner() {
  const x = 'runner';
  return get(); // откуда 'get' "видит" x?
}

console.log(runner()); // ?
```

<details>
<summary>Ответ</summary>

**`'closure'`**

`get` замыкается на Environment Record функции `makeGetter` (в момент создания). Когда `get()` вызывается внутри `runner()`, область видимости `runner` для `get` недоступна — она не является лексически объемлющей. Поиск идёт по цепочке `[[OuterEnv]]` от `get` → к `makeGetter` → к global. `x = 'runner'` в `runner()` — совсем другой scope, невидимый для `get`.

</details>

## Глобальный контекст выполнения

Глобальный контекст создаётся один раз при старте скрипта. Особенности:

```txt
Global Execution Context:
  ThisBinding    → globalThis (window в браузере, global в Node.js)
  LexicalEnv    → Global Environment Record
    ObjectEnvRec → глобальный объект (window/global)
    DeclaEnvRec  → let/const/class верхнего уровня
  VariableEnv   → тот же Global Environment Record
  OuterEnv      → null (нет ничего "снаружи")
```

```js
// В браузере:
var a = 1;
let b = 2;
function foo() {}

window.a;    // 1
window.b;    // undefined (let не попадает в Object ER)
window.foo;  // function foo() {} (function declaration попадает)

// globalThis работает в обоих окружениях:
globalThis.a; // 1 (браузер и Node.js)
```

## Temporal Dead Zone — что реально происходит

TDZ — это не "защита" и не особая зона памяти. Это состояние привязки в Environment Record: **created but not yet initialized**.

Спецификация запрещает читать или записывать привязку в этом состоянии. Попытка доступа бросает `ReferenceError`.

```js
// Predict the output:
let x = 'outer';

{
  console.log(x); // ?
  let x = 'inner';
}
```

<details>
<summary>Ответ</summary>

**`ReferenceError: Cannot access 'x' before initialization`**

Это ловушка. Интуиция подсказывает: "блок начался, `let x` ещё не встречена — значит, увидим `x = 'outer'` из внешнего scope". Но это неверно.

В фазе создания блока движок сканирует весь блок и создаёт привязку для внутреннего `let x` в TDZ состоянии. Эта привязка "затеняет" внешний `x` **с самого начала блока**. Поэтому `console.log(x)` обращается к внутреннему (TDZ) `x`, а не к внешнему — и получает ReferenceError.

</details>

## Function scope vs block scope — когда что использовать

```js
// var — function scope, не block scope
function example() {
  if (true) {
    var result = 'found'; // создаётся в VariableEnvironment функции
  }
  console.log(result); // 'found' — var "утекла" из if-блока
}

// let/const — block scope
function example2() {
  if (true) {
    let result = 'found'; // создаётся в LexicalEnvironment блока if
  }
  console.log(result); // ReferenceError — result не видна здесь
}

// for-цикл: var vs let
for (var i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 0); // 3, 3, 3
  // var i — одна переменная, к моменту вызова callbacks цикл уже закончился
}

for (let i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 0); // 0, 1, 2
  // let i — на каждой итерации создаётся новый binding, каждый callback
  // замыкается на свой отдельный i
}
```

Почему `let i` в `for` создаёт новый binding на каждой итерации? Это явно предписано спецификацией: в начале каждой итерации цикл создаёт новую копию LexicalEnvironment с новым значением счётчика.

## Связь с другими темами

```txt
[Замыкания]           — замыкание = функция + ссылка на
                        Environment Record: живая ссылка, не копия
                        переменных
[this и привязка]     — ThisBinding — отдельная часть Execution
                        Context, со Scope Chain не связана
[Генераторы]          — генератор хранит состояние выполнения в
                        поле code evaluation state
[Модули ESM vs CJS]   — Module Environment Record: import — это
                        live bindings в LexicalEnvironment
```

## Типичные ошибки на интервью

- **"Хойстинг поднимает код наверх"** — код не перемещается. Привязки создаются в фазе создания контекста, а код выполняется в фазе выполнения. Это разные шаги, не "перемещение".

- **"let и const не хоистятся"** — хоистятся, но попадают в TDZ. Движок знает о них с начала блока — иначе внутри блока внешняя переменная с тем же именем была бы доступна до `let`-объявления (см. пример с TDZ выше).

- **"Scope chain — это динамический поиск по стеку вызовов"** — нет. `[[OuterEnv]]` фиксируется в момент создания функции (лексически), а не в момент вызова. Именно поэтому замыкания работают.

- **"var в блоке if/for/while — это block-scoped"** — нет. `var` всегда function-scoped (или global-scoped). Блоки для неё прозрачны.

- **"let/const на верхнем уровне доступны через window"** — нет. `var` на верхнем уровне → свойство `globalThis`; `let`/`const` на верхнем уровне → только в DeclarativeEnvironmentRecord глобального контекста, через `window` недоступны.

- **Не знать разницу между `LexicalEnvironment` и `VariableEnvironment`** — для senior-интервью это важно. Один контекст держит две ссылки на два разных Environment Record. Объявления `var` и `function` уходят в `VariableEnvironment`; `let`, `const` и `catch` — в `LexicalEnvironment`. Именно это позволяет `let` быть block-scoped, пока `var` остаётся function-scoped, в одной и той же функции.
