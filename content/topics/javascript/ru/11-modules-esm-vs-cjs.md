# Модули: ESM vs CommonJS

## CommonJS — механика изнутри

CommonJS (CJS) — система модулей Node.js, существовавшая до стандартизации ESM. Понимание её механики важно для работы с legacy-кодом и для объяснения ключевых отличий от ESM.

### Обёртка модуля

Каждый CJS-файл **оборачивается функцией** перед выполнением:

```js
(function(exports, require, module, __filename, __dirname) {
  // Ваш код модуля здесь
});
```

Вот откуда берутся `exports`, `require`, `module`, `__filename`, `__dirname` — это не глобальные переменные, а **параметры обёртки**. Node.js вызывает эту функцию при первом `require()` модуля.

### `module.exports` vs `exports`

Самая частая ловушка CJS:

```js
// exports — это локальная переменная, изначально указывающая на module.exports:
console.log(exports === module.exports); // true

// ✅ Добавление свойств — работает через оба:
exports.foo = 1;        // module.exports.foo = 1 ← одно и то же
module.exports.bar = 2; // module.exports.bar = 2

// ❌ Переприсваивание exports — разрывает связь:
exports = { foo: 1 }; // теперь exports — новый объект, module.exports не изменён

// require() возвращает module.exports, а не exports!
// Если exports переприсвоен — изменения потеряны
module.exports = { foo: 1 }; // ✅ так правильно переопределять экспорт целиком
```

```js
// ❌ Типичная ошибка:
// counter.js
exports = function() { return ++count; }; // не сработает

// ✅ Правильно:
module.exports = function() { return ++count; };
```

### Кеширование `require`

CJS кеширует каждый модуль по его **абсолютному пути** в `require.cache`. Повторный `require()` возвращает кешированный `module.exports` без повторного выполнения кода:

```js
// Получить кеш:
Object.keys(require.cache); // все загруженные модули

// Инвалидировать кеш (редко нужно, но бывает при тестировании):
delete require.cache[require.resolve('./my-module')];

// Доказательство кеширования:
// counter.js
let count = 0;
module.exports = { increment: () => ++count, get: () => count };

// main.js
const a = require('./counter');
const b = require('./counter'); // один и тот же объект
a.increment();
console.log(b.get()); // 1 — a и b ссылаются на один module.exports
```

### `require()` — синхронный, динамический

```js
// Путь вычисляется в runtime — допустимо:
const plugin = require(`./plugins/${pluginName}`);

// Условный импорт — допустимо:
if (process.env.NODE_ENV === 'test') {
  const mock = require('./mocks/db');
}

// require в середине функции — допустимо:
function loadConfig() {
  return require('./config.json'); // JSON парсится автоматически
}
```

## ESM — механика изнутри

ESM (ECMAScript Modules) — стандартная система модулей языка. Принципиально иная модель: **статический анализ, живые привязки, асинхронная загрузка**.

### Три фазы выполнения ESM

```txt
1. Parsing (Разбор)
   — движок парсит граф зависимостей (все import)
   — пути должны быть строковыми литералами (без вычислений)
   — создаются Module Records для всех модулей

2. Linking (Связывание)
   — создаются Environment Records для каждого модуля
   — экспортируемые привязки (let/const/function) создаются, но не инициализируются
   — импортируемые имена связываются с этими привязками

3. Evaluation (Вычисление)
   — модули выполняются в порядке зависимостей (post-order)
   — привязки инициализируются значениями
```

Ключевое: **импорты — это не копии**, а **живые ссылки** (live bindings) на экспортированные привязки.

### Live bindings vs CJS copies

```js
// === counter.mjs ===
export let count = 0;
export function increment() { count++; }

// === main.mjs ===
import { count, increment } from './counter.mjs';

console.log(count); // 0
increment();
console.log(count); // 1 ← живая привязка: видим обновлённое значение!

// С CJS эквивалентом:
// === counter.cjs ===
let count = 0;
module.exports = {
  count,               // ← копия значения count на момент exports
  increment() { count++; }
};

// === main.cjs ===
const { count, increment } = require('./counter.cjs');
console.log(count); // 0
increment();
console.log(count); // 0 ← CJS: скопировали примитив, не привязку
                    //         count в модуле изменился, но наша копия нет
```

Это принципиальная разница: ESM экспортирует **привязку**, CJS экспортирует **значение** (для примитивов — копию, для объектов — ссылку).

### Хойстинг импортов

`import` декларации **хоистятся** — они обрабатываются до выполнения кода модуля. Движок связывает все импорты на фазе Linking, а не в момент достижения строки `import`.

```js
// Это легально в ESM:
foo(); // работает, хотя import ниже

import { foo } from './utils.mjs';
// foo — function declaration в utils.mjs, тоже хоистится внутри него

// Но нельзя хоистить значения let/const из другого модуля:
console.log(bar); // ReferenceError (TDZ) если bar — let/const в utils.mjs
import { bar } from './utils.mjs';
```

### ESM всегда strict mode

```js
// В ESM-модуле — автоматически strict mode, без 'use strict':
function sloppy() {
  x = 1; // ReferenceError: x is not defined
          // В CJS без 'use strict' — создало бы глобальную переменную
}
```

## Циклические зависимости — главная ловушка senior-уровня

### CJS: частично построенный `module.exports`

В CJS, когда A требует B, а B требует A (цикл), B получает **текущее состояние `module.exports` A** — то, что уже было присвоено до момента кругового `require`.

```js
// === a.cjs ===
const b = require('./b.cjs');
console.log('a: b.done =', b.done);

exports.done = true;
console.log('a: finished');

// === b.cjs ===
const a = require('./a.cjs'); // ← циклический require
console.log('b: a.done =', a.done);

exports.done = true;
console.log('b: finished');

// Запуск: node a.cjs
// b: a.done = undefined  ← a ещё не выполнила exports.done = true
// a: b.done = true       ← b уже выполнила свой exports.done
// b: finished
// a: finished
```

Порядок выполнения:
1. `a.cjs` начинает загружаться, `require('./b.cjs')` вызван
2. `b.cjs` начинает загружаться, `require('./a.cjs')` вызван
3. Node видит `a.cjs` в кеше (уже загружается), возвращает **текущий** `module.exports` — пустой объект `{}`
4. `b.cjs` продолжает с `a = {}`, присваивает `b.done = true`, завершается
5. `a.cjs` получает завершённый `b`, присваивает `a.done = true`, завершается

### ESM: живые привязки решают... но не всегда

В ESM на фазе Linking все привязки создаются (но не инициализируются). Это означает, что при цикле привязка **существует**, но может находиться в TDZ:

```js
// === a.mjs ===
import { b } from './b.mjs';
export const a = 'a_value';
console.log('a: b =', b);

// === b.mjs ===
import { a } from './a.mjs';
export const b = 'b_value';
console.log('b: a =', a);
```

```txt
Порядок выполнения ESM (post-order: сначала зависимости):
  1. Разбор: a.mjs импортирует b.mjs, b.mjs импортирует a.mjs
  2. Linking: создаём привязки для a и b (обе в TDZ)
  3. Evaluation: b.mjs выполняется первым (зависимость a.mjs):
       b инициализируется в 'b_value'
       console.log('b: a =', a) → ReferenceError! a в TDZ

  Если в b.mjs вместо const используется function:
  export function getA() { return a; } // ← функция захватит a позже
  // Тогда при вызове getA() после инициализации a — всё работает
```

**Ключевое правило для ESM-циклов**: если нужны данные из кругового импорта — используйте функции (они захватывают привязку, а не значение в момент создания) или убедитесь, что нужный модуль инициализирован к моменту обращения.

```js
// ✅ Работает с ESM-циклами:
// b.mjs
import { a } from './a.mjs';
export function getA() { return a; } // функция — обратится к a позже

// a.mjs
import { getA } from './b.mjs';
export const a = 'hello';
console.log(getA()); // 'hello' — к этому моменту a инициализирована
```

## Predict the output — порядок загрузки

```js
// === lib.mjs ===
export let value = 1;
export function increment() { value++; }
export function getValue() { return value; }

// === main.mjs ===
import { value, increment, getValue } from './lib.mjs';

console.log(value);      // ?
increment();
console.log(value);      // ?
console.log(getValue()); // ?

const snapshot = value;
increment();
console.log(snapshot === value); // ?
```

<details>
<summary>Ответ</summary>

```
1     // живая привязка, начальное значение
2     // живая привязка — видим изменение внутри модуля
2     // getValue() читает ту же привязку
false // snapshot = 2 (примитив скопирован), затем value стал 3
      // snapshot (2) !== value (3)
```

Нюанс: `const snapshot = value` копирует **текущее значение** примитива (2) в локальную переменную. `value` — live binding на привязку в lib.mjs, но при присваивании `snapshot = value` значение примитива копируется, а не сама привязка. Поэтому `snapshot` не обновляется при последующих `increment()`.

</details>

## `import()` — динамический импорт

`import()` — функция-оператор, возвращающая `Promise<namespace>`. Работает в ESM и CJS:

```js
// Lazy loading:
async function loadChart() {
  const { Chart } = await import('./chart.mjs');
  return new Chart(data);
}

// Условный импорт (невозможный со статическим import):
const module = await import(
  process.env.NODE_ENV === 'test' ? './mock-db.mjs' : './db.mjs'
);

// import() в CJS может импортировать ESM (require() — не может):
// main.cjs
async function main() {
  const { foo } = await import('./esm-module.mjs'); // ✅
}

// Отличие от require():
// require('./module') → возвращает module.exports
// import('./module')  → возвращает Promise<namespace object>
//   namespace object: { default, ...namedExports }
```

```js
// namespace object:
// === utils.mjs ===
export const PI = 3.14;
export default function add(a, b) { return a + b; }

// === main.mjs ===
const ns = await import('./utils.mjs');
ns.PI;       // 3.14
ns.default;  // function add
ns.default(1, 2); // 3
```

## Top-level `await`

ESM-модули могут использовать `await` на верхнем уровне. Импортирующий модуль **ждёт** завершения:

```js
// === config.mjs ===
const response = await fetch('/api/config');
export const config = await response.json();
// Этот модуль "готов" только когда fetch завершён

// === app.mjs ===
import { config } from './config.mjs';
// app.mjs не начнёт выполняться пока config.mjs не завершит свой await
console.log(config.apiUrl); // гарантированно инициализировано
```

**Влияние на параллельность**: если несколько независимых модулей используют top-level await, движок может загружать их параллельно.

```js
// ❌ Последовательно (медленно):
// a.mjs
export const a = await fetchA(); // 500ms

// b.mjs
export const b = await fetchB(); // 500ms

// main.mjs: загружает a.mjs, потом b.mjs → ~1000ms

// ✅ Параллельно:
// main.mjs
const [a, b] = await Promise.all([fetchA(), fetchB()]); // ~500ms
export { a, b };
```

Top-level await **не работает** в CJS-модулях — там нет механизма ожидания.

## Совместимость CJS ↔ ESM

```txt
CJS → ESM: require() из CJS не может импортировать ESM (в Node.js)
           Почему: require() синхронный, ESM загружается асинхронно
           Решение: import() (динамический, возвращает Promise)

ESM → CJS: import 'something.cjs' — работает
           module.exports CJS становится default экспортом ESM:
           import cjsModule from './module.cjs';
           cjsModule.someMethod(); // через default

Смешанные проекты: package.json:
  "type": "module"    → .js файлы = ESM, .cjs = CJS
  "type": "commonjs"  → .js файлы = CJS, .mjs = ESM (по умолчанию)

Двойные пакеты (CJS + ESM):
  package.json exports:
    { "import": "./dist/esm/index.mjs",
      "require": "./dist/cjs/index.cjs" }
```

## Ключевые отличия: сводная таблица

```txt
Характеристика       CJS                      ESM
────────────────────────────────────────────────────────────
Синтаксис            require/module.exports   import/export
Загрузка             Синхронная (blocking)    Асинхронная
Анализ зависимостей  Runtime (динамически)   Parse time (статически)
Пути импорта         Вычисляемые             Только литералы (статично)
Экспортируемые       Копия (для примитивов)  Живая привязка
  значения
Strict mode          Опционально             Всегда
Top-level await      ❌                       ✅
Tree-shaking         ❌ (сложно)             ✅ (статический анализ)
Circular deps        Частично выполненный    Живые привязки (TDZ риск)
                     module.exports
```

## Связь с другими темами

```txt
[Контексты выполнения] — Module Environment Record: import-привязки
                          являются live bindings в LexicalEnvironment
[Event Loop]           — ESM загрузка асинхронна; top-level await
                          блокирует dependent modules через Promise
[Генераторы]           — for-await-of, async generators работают
                          только в ESM (или async функциях)
[Современный JS]       — import() динамический, AbortSignal для отмены
                          fetch внутри top-level await
```

## Типичные ошибки на интервью

- **"`exports = {...}` — это то же самое что `module.exports = {...}`"** — нет. `exports` — локальная переменная-ссылка. Переприсваивание `exports` разрывает связь с `module.exports`. `require()` всегда возвращает `module.exports`.

- **"ESM import — это то же самое что CJS require, но с другим синтаксисом"** — нет. Три принципиальных отличия: статический анализ (ESM) vs runtime (CJS), живые привязки (ESM) vs копии (CJS), async (ESM) vs sync (CJS).

- **"Tree-shaking работает с CJS"** — не в полной мере. Tree-shaking требует статического анализа экспортов/импортов. CJS динамический, экспорты могут быть вычисляемыми. Бандлеры (webpack, rollup) могут пробовать, но с ограничениями.

- **"Циклические зависимости — это всегда ошибка"** — нет, оба модуля поддерживают циклы. Но нужно понимать, что получишь: CJS — частично выполненный `module.exports`, ESM — live binding (потенциально в TDZ). Решение: функции-акцессоры вместо прямого экспорта значений.

- **"`import()` и `require()` — одинаковые"** — нет. `import()` возвращает `Promise<namespace object>` с `default` и именованными экспортами. `require()` возвращает `module.exports` синхронно. `import()` может загружать ESM-модули из CJS-контекста, `require()` — не может.

- **"Top-level await доступен в любом JS-файле"** — только в ESM-модулях. В CJS (`require`/`module.exports`) нет механизма ожидания верхнего уровня.

- **"Live bindings ESM — это то же что ссылка на объект"** — нет. Ссылка на объект позволяет мутировать объект через неё. Live binding ESM — это ссылка на **привязку** (переменную в другом модуле), которая обновляется при каждом чтении. Мутировать `count` из другого модуля через import нельзя — только через экспортированную функцию.
