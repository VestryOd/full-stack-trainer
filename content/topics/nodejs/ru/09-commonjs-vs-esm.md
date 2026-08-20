<!-- verified: 2026-06-05, corrections: 0 -->
# CommonJS vs ES Modules

## Почему это не просто "разница в синтаксисе"

Две системы различаются тем, **когда и как загружается модуль**, а не только ключевыми словами. CommonJS (CJS) выполняет `require()` синхронно и отдаёт копию экспортированных значений. ES Modules (ESM — ES означает ECMAScript, стандарт, по которому устроен JavaScript) сначала разбирают весь граф зависимостей, а затем связывают модули живыми связями (live bindings).

Поверхностный ответ — "CommonJS использует `require`/`module.exports`, ESM использует `import`/`export`, ESM лучше для tree shaking". Это верно, но на этом останавливаться рано. На собеседовании senior-уровня вопрос почти всегда уходит в три темы:

- Что происходит с переменными при circular dependency (циклической зависимости).
- Как на самом деле работает разрешение модулей.
- Что реально происходит, когда CJS и ESM смешаны в одном проекте.

Последняя тема — та, где на практике теряются часы при миграции реальных проектов.

## CommonJS: `require` — это не "просто импорт", это синхронный вызов функции

```ts
// То, что вы пишете:
const { readFile } = require('fs');
module.exports = { processFile };
```

```ts
// То, во что Node оборачивает каждый файл перед выполнением:
(function (exports, require, module, __filename, __dirname) {
  const { readFile } = require('fs');
  module.exports = { processFile };
});
```

```txt
Это объясняет:
  - откуда берутся __dirname/__filename/require/module/exports
    "из воздуха" — это параметры функции-обёртки
  - почему top-level код модуля имеет свой собственный scope
    (переменные модуля не попадают в global)
  - почему require() — синхронная операция: это обычный вызов
    функции, который должен вернуть значение до того, как
    выполнение продолжится дальше
```

### Алгоритм разрешения модулей — где теряются часы при отладке

```txt
require('./utils')     → ./utils.js, ./utils.json,
                          ./utils.node, ./utils/index.js
                          (именно в этом порядке)

require('lodash')       → поиск node_modules/lodash в текущей
                           директории, затем в родительской,
                           и так до корня файловой системы
                           (поэтому одна версия lodash может
                           дублироваться в node_modules
                           на разных уровнях при конфликте
                           версий)

require('lodash')       → читает package.json пакета lodash,
                           смотрит поле "main" (или "exports"
                           для современных пакетов) — точка
                           входа не обязательно index.js
```

### Module Cache — кэш по абсолютному пути, а не по строке импорта

```ts
// a.js и b.js оба делают:
require('./utils');      // из директории /src
require('../src/utils');  // из /src/sub — это тот же файл

// Node кэширует по разрешённому абсолютному пути файла —
// поэтому оба вызова возвращают один и тот же объект
// exports, даже если строки импорта разные
```

## ESM: модули загружаются в три фазы — почему это важно

```txt
CommonJS: загрузка и выполнение — одна операция (require
выполняет файл синхронно, сверху вниз).

ESM (спецификация ECMAScript) — три отдельные фазы:
  1. Construction (Parsing) — разбор всех модулей в графе
     зависимостей, построение "module record" для каждого,
     без выполнения кода
  2. Instantiation — выделение памяти для всех export/import
     bindings (создание связей между модулями), снова без
     выполнения
  3. Evaluation — выполнение кода модулей, в порядке
     зависимостей (от листьев графа к корню)
```

Именно трёхфазная загрузка делает возможным **top-level await**. Node может приостановить Evaluation одного модуля на `await` и продолжить Instantiation и Evaluation других независимых модулей графа. Плюс он точно знает граф зависимостей **до** начала выполнения, потому что Construction завершена для всех модулей заранее.

В CommonJS такого нет. `require()` обязан вернуть готовый результат немедленно, синхронно.

## Live bindings vs копия значения — классическая ловушка с circular dependencies

### CommonJS: экспорт — это копия значения на момент `require()`

```ts
// counter.js (CommonJS)
let count = 0;
function increment() { count++; }
module.exports = { count, increment }; // count = 0 — снимок на момент экспорта
```

```ts
// main.js
const { count, increment } = require('./counter');
increment();
console.log(count); // 0 — не изменился! count скопирован как примитив
```

### ESM: импорт — это live binding (ссылка на "ячейку" в модуле, а не на значение)

```ts
// counter.mjs
export let count = 0;
export function increment() { count++; }
```

```ts
// main.mjs
import { count, increment } from './counter.mjs';
increment();
console.log(count); // 1 — импорты ESM всегда читают текущее значение
```

```txt
Это не "странность ESM" — это прямое следствие трёхфазной
загрузки: на этапе Instantiation создаётся связывание со
"слотом" переменной в модуле-источнике, а не копия её
текущего значения. Каждое обращение к импортированному
имени читает актуальное состояние этого слота.
```

### Circular dependencies — где разница проявляется драматичнее всего

```ts
// a.js (CommonJS)
console.log('a starting');
exports.done = false;
const b = require('./b'); // b.js начинает require('./a') внутри себя —
                            // получит частичный объект exports для a
                            // (только то, что было экспортировано
                            // до строки require('./b'))
console.log('in a, b.done =', b.done);
exports.done = true;
```

```txt
В CommonJS circular dependency приводит к получению
"частично заполненного" module.exports — порядок объявлений
до строки require() критичен. Это классическая причина
багов "почему этот экспорт undefined при инициализации".

В ESM circular dependency работает лучше для функций
(благодаря hoisting объявлений function и live bindings).
Но переменные, инициализированные через let/const с
вычислением (не просто = 0), всё ещё могут быть в состоянии
"объявлена, но не инициализирована" (TDZ — Temporal Dead
Zone) при доступе во время цикла.
```

## Tree Shaking — где Node не участвует

```txt
Частое заблуждение: "ESM делает мой Node-сервер быстрее
благодаря tree shaking".

Реальность: tree shaking — это оптимизация сборщика
(webpack/esbuild/rollup) для клиентского кода. Сам Node.js
не делает tree shaking при выполнении — он просто загружает
и выполняет все модули графа зависимостей. Статический
анализ ESM даёт здесь лишь незначительное преимущество:
Node может заранее знать граф зависимостей и грузить файлы
с диска параллельно.

Статический анализ ESM важен для tree shaking, когда вы
собираете frontend-код или бессерверные функции
(serverless), где размер бандла влияет на cold start. Для
типичного Node API-сервера он не важен.
```

## Interop: смешивание CommonJS и ESM — где реально теряют время

### ESM импортирует CommonJS — `module.exports` становится `default`

```ts
// legacy-logger.js (CommonJS)
module.exports = { log: (msg) => console.log(msg) };
```

```ts
// app.mjs (ESM)
import logger from './legacy-logger.js'; // весь module.exports → default
logger.log('hello'); // ✅ работает

// ❌ так не сработает напрямую для произвольных CJS-пакетов:
import { log } from './legacy-logger.js';
// именованные импорты из CJS работают только если Node (через
// cjs-module-lexer) может статически проанализировать
// module.exports = {...} как объектный литерал. Для динамических
// module.exports (вычисляемых в рантайме) именованные импорты
// часто не определяются, и результат — undefined
```

### CommonJS импортирует ESM — `require()` не может загрузить ESM синхронно

```ts
// ❌ невозможно — require() синхронный, ESM-модуль требует
// асинхронной загрузки (минимум — для top-level await в графе)
const esmModule = require('./esm-only-package');
// Error: require() of ES Module not supported

// ✅ единственный путь — динамический import() (асинхронный)
const esmModule = await import('./esm-only-package.mjs');
```

```txt
Это одностороннее ограничение. ESM может импортировать CJS —
с оговорками выше, — но CJS не может импортировать ESM
синхронно.

На практике: если ваш CommonJS-проект зависит от пакета,
который перешёл на "pure ESM" (например, новые версии chalk,
node-fetch, inquirer), есть два варианта. Либо переходить на
ESM целиком, либо использовать динамический import() — что
ломает синхронные top-level вызовы.
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
Проблема: одна часть вашего приложения импортирует библиотеку
через require() и получает CJS-сборку, другая часть — через
import и получает ESM-сборку. Node загружает два отдельных
модуля с двумя отдельными экземплярами внутреннего состояния.

Классический симптом: библиотека использует Singleton
(например, "глобальный" реестр конфигурации). Из-за dual
package hazard в приложении оказывается два таких Singleton,
которые не видят изменений друг друга. Баг проявляется как
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
"type": "module"  → файлы .js трактуются как ESM
"type": "commonjs" (или отсутствует) → файлы .js — CommonJS

Расширения переопределяют "type" для конкретного файла:
  .mjs — всегда ESM, независимо от "type"
  .cjs — всегда CommonJS, независимо от "type"

Практическое применение: библиотека с "type": "module" в
package.json может включить отдельный .cjs-файл для обратной
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
require() для ESM     ❌ не работает         —
import для CJS        —                     module.exports → default
Динамический импорт   require() (sync)      import() (async,
                                             доступен везде)
Top-level await       ❌                     ✅
```

## Связь с другими темами

```txt
[Node.js Fundamentals]  — общий контекст npm-экосистемы и
                           структуры package.json
```

## Типичные ошибки на интервью

- **"Главное отличие — синтаксис import/export vs require"** — так теряется разница между live bindings и копией значения. А именно она — источник реальных багов при circular dependencies.

- **"ESM делает Node быстрее за счёт tree shaking"** — путать оптимизацию сборщика для клиентского кода с поведением Node.js при выполнении, который tree shaking не делает.

- **Не знать про одностороннее ограничение `require()` для ESM-модулей** — legacy-проект на CJS не может просто обновиться до новых версий "pure ESM" зависимостей. Нужен либо полный переход на ESM, либо динамический `import()`.

- **Не знать про dual package hazard** — смешанное использование require и import в одном приложении может "сломать" библиотеку с паттерном Singleton. Без этого понятия объяснить причину не получится.

- **Считать `__dirname` доступным в ESM "так же, как в CJS"** — не знать про `import.meta.url` + `fileURLToPath` как стандартную замену.
