<!-- verified: 2026-06-05, corrections: 0 -->
# CommonJS vs ES Modules

## Почему это не просто "разница в синтаксисе"

Поверхностный уровень — "CommonJS использует `require`/`module.exports`, ESM использует `import`/`export`, ESM лучше для tree shaking". Это верно, но на собеседовании senior-уровня вопрос почти всегда движется к: **что происходит с переменными при circular dependency**, **как работает разрешение модулей**, и **что РЕАЛЬНО происходит, когда смешиваются CJS и ESM в одном проекте** — а это та область, где на практике теряются часы при миграции реальных проектов.

## CommonJS: `require` — это не "просто импорт", это синхронный вызов функции

```ts
// То, что вы пишете:
const { readFile } = require('fs');
module.exports = { processFile };
```

```ts
// То, во что Node ОБОРАЧИВАЕТ каждый файл перед выполнением:
(function (exports, require, module, __filename, __dirname) {
  const { readFile } = require('fs');
  module.exports = { processFile };
});
```

```txt
Это объясняет:
  - откуда берутся __dirname/__filename/require/module/exports
    "из воздуха" — это ПАРАМЕТРЫ функции-обёртки
  - почему top-level код модуля имеет свой собственный scope
    (переменные модуля не попадают в global)
  - почему require() — СИНХРОННАЯ операция: это обычный вызов
    функции, который должен вернуть значение до того, как
    выполнение продолжится дальше
```

### Алгоритм разрешения модулей — где теряются часы при дебаге

```txt
require('./utils')          → ./utils.js, ./utils.json, ./utils.node,
                               ./utils/index.js (в этом порядке)

require('lodash')            → поиск node_modules/lodash в ТЕКУЩЕЙ
                               директории, затем в родительской,
                               и так до корня файловой системы
                               (поэтому одна версия lodash может
                               дублироваться в node_modules
                               на разных уровнях при конфликте версий)

require('lodash')            → читает package.json пакета lodash,
                               смотрит поле "main" (или "exports"
                               для современных пакетов) — точка
                               входа НЕ обязательно index.js
```

### Module Cache — кэш по АБСОЛЮТНОМУ пути, не по строке импорта

```ts
// a.js и b.js оба делают:
require('./utils');      // из директории /src
require('../src/utils');  // из директории /src/sub — РЕЗОЛВИТСЯ в тот же файл

// Node кэширует по РЕЗОЛВНУТОМУ АБСОЛЮТНОМУ ПУТИ файла —
// поэтому оба вызова возвращают ОДИН И ТОТ ЖЕ объект exports,
// даже если строки импорта разные
```

## ESM: модули загружаются в ТРИ фазы — почему это важно

```txt
CommonJS: загрузка и выполнение — ОДНА операция (require
выполняет файл синхронно, сверху вниз).

ESM (спецификация ECMAScript) — три отдельные фазы:
  1. Construction (Parsing) — парсинг ВСЕХ модулей в графе
     зависимостей, построение "module record" для каждого,
     БЕЗ выполнения кода
  2. Instantiation — выделение памяти для всех export/import
     bindings (создание связей между модулями), снова БЕЗ
     выполнения
  3. Evaluation — выполнение кода модулей, в порядке
     зависимостей (от листьев графа к корню)
```

Именно трёхфазная загрузка делает возможным **top-level await** — Node может приостановить Evaluation одного модуля на await, продолжая Instantiation/Evaluation других независимых модулей в графе, и точно знает граф зависимостей ДО начала выполнения (потому что Construction завершена для всех модулей заранее). В CommonJS такого нет — `require()` обязан вернуть готовый результат немедленно, синхронно.

## Live bindings vs value copy — классический "gotcha" с circular dependencies

### CommonJS: экспорт — это КОПИЯ значения на момент `require()`

```ts
// counter.js (CommonJS)
let count = 0;
function increment() { count++; }
module.exports = { count, increment }; // count = 0 — СНИМОК на момент экспорта
```

```ts
// main.js
const { count, increment } = require('./counter');
increment();
console.log(count); // 0 — НЕ изменился! count был скопирован как примитив
```

### ESM: импорт — это LIVE BINDING (ссылка на "ячейку" в модуле, не на значение)

```ts
// counter.mjs
export let count = 0;
export function increment() { count++; }
```

```ts
// main.mjs
import { count, increment } from './counter.mjs';
increment();
console.log(count); // 1 — ESM-импорты ВСЕГДА читают ТЕКУЩЕЕ значение
```

```txt
Это не "странность ESM" — это прямое следствие трёхфазной
загрузки: на этапе Instantiation создаётся связывание со
"слотом" переменной в модуле-источнике, а не копия её
текущего значения. Каждое обращение к импортированному
имени читает АКТУАЛЬНОЕ состояние этого слота.
```

### Circular dependencies — где разница проявляется драматичнее всего

```ts
// a.js (CommonJS)
console.log('a starting');
exports.done = false;
const b = require('./b'); // b.js начинает require('./a') ВНУТРИ себя —
                            // получит ЧАСТИЧНЫЙ exports объект a
                            // (только то, что было экспортировано
                            // ДО строки require('./b'))
console.log('in a, b.done =', b.done);
exports.done = true;
```

```txt
В CommonJS circular dependency приводит к получению
"частично заполненного" module.exports — порядок объявлений
ДО строки require() критичен. Это классическая причина
багов "почему этот экспорт undefined при инициализации".

В ESM circular dependency работает ЛУЧШЕ для функций
(благодаря hoisting объявлений function и live bindings),
но переменные, инициализированные через let/const с
вычислением (не просто = 0), всё ещё могут быть в состоянии
"объявлена, но не инициализирована" (TDZ — Temporal Dead
Zone) при доступе во время цикла.
```

## Tree Shaking — где Node НЕ участвует

```txt
Частое заблуждение: "ESM делает мой Node-сервер быстрее
благодаря tree shaking".

Реальность: tree shaking — это оптимизация БАНДЛЕРА
(webpack/esbuild/rollup) для КЛИЕНТСКОГО кода. Node.js САМ
НЕ делает tree shaking при выполнении — он просто загружает
и выполняет ВСЕ модули графа зависимостей, статический анализ
ESM здесь даёт только МАРГИНАЛЬНОЕ преимущество (Node может
заранее знать граф зависимостей для параллельной загрузки
файлов с диска).

Статический анализ ESM важен для tree shaking в контексте
СБОРКИ frontend-кода или серверless-функций (где размер
бандла влияет на cold start), а не для типичного Node API-сервера.
```

## Interop: смешивание CommonJS и ESM — где реально теряют время

### ESM импортирует CommonJS — `module.exports` становится `default`

```ts
// legacy-logger.js (CommonJS)
module.exports = { log: (msg) => console.log(msg) };
```

```ts
// app.mjs (ESM)
import logger from './legacy-logger.js'; // ВЕСЬ module.exports → default
logger.log('hello'); // ✅ работает

// ❌ так — НЕ сработает напрямую для произвольных CJS-пакетов:
import { log } from './legacy-logger.js';
// именованные импорты из CJS работают только если Node (через
// cjs-module-lexer) может СТАТИЧЕСКИ проанализировать
// module.exports = {...} как объектный литерал. Для динамических
// module.exports (вычисляемых в рантайме) — именованные импорты
// часто не определяются и result = undefined
```

### CommonJS импортирует ESM — `require()` НЕ МОЖЕТ загрузить ESM синхронно

```ts
// ❌ невозможно — require() синхронный, ESM-модуль требует
// асинхронной загрузки (минимум — для top-level await в графе)
const esmModule = require('./esm-only-package');
// Error: require() of ES Module not supported

// ✅ единственный путь — динамический import() (асинхронный)
const esmModule = await import('./esm-only-package.mjs');
```

```txt
Это ОДНОНАПРАВЛЕННОЕ ограничение — ESM может импортировать
CJS (с оговорками выше), но CJS НЕ МОЖЕТ синхронно
импортировать ESM. На практике это означает: если ваш
CommonJS-проект зависит от пакета, который перешёл на
"pure ESM" (например, новые версии chalk, node-fetch,
inquirer) — придётся либо переходить на ESM целиком, либо
использовать динамический import() (что ломает синхронные
top-level вызовы).
```

### "Dual package hazard" — две версии одного модуля одновременно

```json
// package.json библиотеки, поддерживающей оба формата
{
  "exports": {
    "require": "./dist/index.cjs",
    "import": "./dist/index.mjs"
  }
}
```

```txt
Проблема: если ОДНА ЧАСТЬ вашего приложения импортирует
библиотеку через require() (получает CJS-сборку), а ДРУГАЯ —
через import (получает ESM-сборку) — Node загружает ДВА
ОТДЕЛЬНЫХ модуля с ДВУМЯ ОТДЕЛЬНЫМИ instance'ами внутреннего
состояния.

Классический симптом: библиотека использует Singleton
(например, "глобальный" registry конфигурации) — но из-за
dual package hazard в приложении оказывается ДВА Singleton'а,
которые не видят изменения друг друга. Баг проявляется как
"настройки не применяются" без явной ошибки.
```

## `__dirname`/`__filename` в ESM и `createRequire`

```ts
// CommonJS — доступны автоматически (параметры обёртки)
console.log(__dirname, __filename);

// ESM — нет обёртки, поэтому нет __dirname/__filename.
// Эквивалент через import.meta.url:
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
```

```ts
// Если внутри ESM-модуля нужен require() (например, для
// загрузки JSON или CJS-зависимости без top-level await):
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const pkg = require('./package.json');
```

## `package.json "type"` и расширения файлов

```txt
"type": "module"  → .js файлы ТРАКТУЮТСЯ КАК ESM
"type": "commonjs" (или отсутствует) → .js файлы — CommonJS

Расширения ПЕРЕОПРЕДЕЛЯЮТ "type" для конкретного файла:
  .mjs — ВСЕГДА ESM, независимо от "type"
  .cjs — ВСЕГДА CommonJS, независимо от "type"

Практическое применение: библиотека с "type": "module" в
package.json может включить ОТДЕЛЬНЫЙ .cjs-файл для обратной
совместимости без переключения всего пакета.
```

## Итоговая сравнительная таблица

```txt
                       CommonJS              ESM
─────────────────────────────────────────────────────────────
Загрузка              синхронная            3 фазы (async для
                                             top-level await)
Импорт                копия значения        live binding
Circular deps         частичный exports     лучше для функций,
                                             но TDZ для let/const
__dirname             встроено              через import.meta.url
require() of ESM      ❌ не работает         —
import of CJS         —                     module.exports → default
Динамический импорт   require() (sync)      import() (async, везде)
Top-level await       ❌                     ✅
```

## Связь с другими темами

```txt
[Node.js Fundamentals]  — общий контекст npm-экосистемы и
                           структуры package.json
```

## Типичные ошибки на интервью

- **"Главное отличие — синтаксис import/export vs require"** — без упоминания live bindings vs value copy, что является ИСТОЧНИКОМ реальных багов при circular dependencies.

- **"ESM делает Node быстрее за счёт tree shaking"** — путать оптимизацию БАНДЛЕРА для клиентского кода с поведением Node.js при выполнении, который tree shaking не делает.

- **Не знать про одностороннее ограничение `require()` ESM-модулей** — не понимать, почему миграция legacy CJS-проекта на новые версии "pure ESM" зависимостей требует либо полного перехода на ESM, либо динамического `import()`.

- **Не знать про dual package hazard** — не объяснять, почему библиотека с Singleton-паттерном может "сломаться" при смешанном использовании require/import в одном приложении.

- **Считать `__dirname` доступным в ESM "так же, как в CJS"** — не знать про `import.meta.url` + `fileURLToPath` как стандартную замену.
