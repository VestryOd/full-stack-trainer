<!-- verified: 2026-06-23, corrections: 0 -->
# TypeScript Compiler и конфигурация

## Как работает компилятор TypeScript

TypeScript не транспилируется напрямую в JavaScript браузером или Node. Это отдельный инструмент (`tsc`), который проходит несколько фаз:

```txt
Фазы компиляции TypeScript:

1. Parsing (разбор)
   Исходный .ts → AST (Abstract Syntax Tree)

2. Binding (привязка)
   Построение таблицы символов: какие имена где объявлены

3. Type checking (проверка типов)
   Анализ AST + таблица символов → список ошибок
   Именно здесь работают все проверки типов

4. Emit (генерация)
   AST → .js и .d.ts файлы
   Типы полностью стираются

Важно: шаги 3 и 4 независимы.
  - tsc --noEmit — только проверка типов, без генерации JS
  - isolatedModules — каждый файл компилируется независимо (Babel/esbuild)
  - transpileOnly (ts-node) — пропуск проверки типов, только emit
```

Это объясняет, почему Babel и esbuild могут транспилировать TypeScript без понимания типов: они выполняют только фазу 4, опуская фазу 3. Из-за этого некоторые конструкции TypeScript несовместимы с `isolatedModules` (например, `const enum`, `namespace`).

---

## `strict` — что именно включается

`"strict": true` — это не одна опция, а группа из восьми флагов. Знать каждый по отдельности важно, потому что иногда нужно включить только часть или понять, что именно поймала ошибка.

```json
{
  "compilerOptions": {
    "strict": true
    // Эквивалентно включению всех восьми флагов ниже:
  }
}
```

### `strictNullChecks`

Самый важный флаг. Без него `null` и `undefined` совместимы с любым типом:

```ts
// strictNullChecks: false (по умолчанию до strict):
let name: string = null;   // ✅ — катастрофа в runtime
let age: number = undefined; // ✅

// strictNullChecks: true:
let name: string = null;   // ❌ Type 'null' is not assignable to type 'string'
let name2: string | null = null; // ✅ — явное разрешение
```

**Что ловит:** доступ к свойствам `null`/`undefined` без проверки, обращение к результату функций, которые могут вернуть `null` (`.find()`, `.querySelector()`).

```ts
// Без strictNullChecks — молчит:
const user = users.find(u => u.id === id);
user.name; // ✅ TypeScript — но runtime crash если не найден

// Со strictNullChecks:
user.name; // ❌ 'user' is possibly 'undefined'
if (user) user.name; // ✅
```

### `noImplicitAny`

Запрещает неявный `any` там, где TypeScript не может вывести тип:

```ts
// noImplicitAny: false:
function process(data) { // data: any — TypeScript не жалуется
  return data.value;
}

// noImplicitAny: true:
function process(data) { // ❌ Parameter 'data' implicitly has an 'any' type
  return data.value;
}

// Исправление — явная аннотация:
function process(data: unknown) { /* ... */ }
function process(data: { value: string }) { /* ... */ }
```

**Что ловит:** параметры функций без типов, переменные, которые нельзя вывести по контексту, поля объектов без инициализации.

### `strictFunctionTypes`

Включает контравариантную проверку параметров функций (вместо бивариантной). Рассмотрено подробно в [Variance and Assertions]:

```ts
// strictFunctionTypes: false:
type Handler = (event: MouseEvent) => void;
const handler: Handler = (event: Event) => {}; // ✅ бивариантно (UNSAFE)

// strictFunctionTypes: true:
const handler: Handler = (event: Event) => {}; // ❌ Event шире MouseEvent
```

**Что ловит:** ковариантные использования типов функций, которые должны быть контравариантны. Особенно важно при работе с callback-параметрами.

### `strictBindCallApply`

Включает типизацию `.bind()`, `.call()`, `.apply()`:

```ts
function greet(name: string, age: number): string {
  return `${name}, ${age}`;
}

// strictBindCallApply: false:
greet.call(null, "Alice", "30"); // ✅ — строка вместо числа, TypeScript молчит

// strictBindCallApply: true:
greet.call(null, "Alice", "30"); // ❌ Argument of type 'string' is not assignable to 'number'
greet.call(null, "Alice", 30);   // ✅
```

### `strictPropertyInitialization`

Требует инициализации всех свойств класса в конструкторе:

```ts
class User {
  id: number;    // ❌ Property 'id' has no initializer and is not definitely assigned
  name: string;  // ❌ то же

  constructor() {
    // забыли присвоить
  }
}

// Исправления:
class User {
  id: number = 0;         // ✅ инициализатор
  name!: string;          // ✅ definite assignment assertion (осторожно — отключает проверку)

  constructor(id: number, name: string) {
    this.id = id;         // ✅ присвоение в конструкторе
    this.name = name;
  }
}
```

**Что ловит:** поля класса, которые могут быть `undefined` из-за незаполненного конструктора — типичный источник runtime ошибок в OOP-коде.

### `noImplicitThis`

Запрещает `this` с неявным типом `any`:

```ts
// noImplicitThis: true:
function greet() {
  return this.name; // ❌ 'this' implicitly has type 'any'
}

// Исправление — явный тип this:
function greet(this: { name: string }) {
  return this.name; // ✅
}
```

### `alwaysStrict`

Добавляет `"use strict"` в каждый сгенерированный JS-файл. В современных ES-модулях `"use strict"` уже подразумевается, поэтому эффект минимален — но для CJS-вывода важно.

### `useUnknownInCatchVariables` (TS 4.0+)

Меняет тип переменной в `catch` с `any` на `unknown`:

```ts
// useUnknownInCatchVariables: false:
try { /* ... */ } catch (e) {
  e.message; // e: any — можно обратиться к любому свойству без проверки
}

// useUnknownInCatchVariables: true:
try { /* ... */ } catch (e) {
  e.message; // ❌ e: unknown — нужна проверка
  if (e instanceof Error) {
    e.message; // ✅
  }
}
```

**Практически важно:** Error может быть `throw`нут кем угодно — `throw "string"`, `throw 42`, `throw { code: 500 }` — всё легально в JavaScript. Тип `unknown` честнее, чем `any`.

---

## Дополнительные важные опции вне `strict`

### `noUncheckedIndexedAccess`

Одна из самых полезных опций вне `strict`. Добавляет `| undefined` к результату индексного доступа:

```ts
// noUncheckedIndexedAccess: false (по умолчанию):
const arr = [1, 2, 3];
const x = arr[10]; // x: number — но в runtime это undefined!
x.toFixed();       // runtime crash

// noUncheckedIndexedAccess: true:
const x = arr[10]; // x: number | undefined
x.toFixed();       // ❌ Object is possibly 'undefined'
if (x !== undefined) x.toFixed(); // ✅

// Аналогично для объектов с индексной сигнатурой:
const map: Record<string, number> = {};
const val = map["key"]; // val: number | undefined ✅
```

**Почему не в `strict` по умолчанию:** ломает слишком много существующего кода, требует много `if (x !== undefined)` проверок. Но для новых проектов — рекомендуется.

### `exactOptionalPropertyTypes`

Различает "поле отсутствует" и "поле явно `undefined`":

```ts
// exactOptionalPropertyTypes: false:
interface Config { timeout?: number }
const c: Config = { timeout: undefined }; // ✅ — считается как отсутствующее

// exactOptionalPropertyTypes: true:
const c: Config = { timeout: undefined };
// ❌ Type '{ timeout: undefined }' is not assignable to 'Config'
//    Types of property 'timeout' are incompatible
//    Type 'undefined' is not assignable to 'number'
```

Полезно, когда важна разница между "не передали" и "передали undefined" (например, при работе с JSON или REST API, где `null`/отсутствие поля имеют разное значение).

### `noPropertyAccessFromIndexSignature`

```ts
interface Config {
  [key: string]: string;
  host: string; // конкретное поле
}

// noPropertyAccessFromIndexSignature: false:
const c: Config = { host: "localhost" };
c.host;    // ✅ конкретное поле
c.unknown; // ✅ индексная сигнатура — но опечатки не поймаешь

// noPropertyAccessFromIndexSignature: true:
c.unknown; // ❌ — нужно использовать скобочную нотацию: c["unknown"]
```

### `noImplicitOverride`

Требует явного `override` при переопределении метода базового класса:

```ts
class Base {
  render(): string { return "base"; }
}

// noImplicitOverride: false:
class Child extends Base {
  render(): string { return "child"; } // молчит, даже если в Base нет render
}

// noImplicitOverride: true:
class Child extends Base {
  render(): string { return "child"; } // ❌ Method 'render' will overwrite the base
  override render(): string { return "child"; } // ✅
}

// Ключевое: если rename метода в Base — TypeScript ловит в Child:
class Child extends Base {
  override rander(): string { return "child"; } // ❌ Method 'rander' does not exist in Base
}
```

---

## Module Resolution: node16 / bundler

Module resolution — алгоритм, по которому TypeScript находит файл для `import { x } from "some-path"`. Неправильная настройка — источник ошибок "Cannot find module" или различий между dev/prod поведением.

### Стратегии

```txt
classic       — устаревшая, только для старых проектов
node          — Node.js CommonJS алгоритм (стандарт долгое время)
node16 / nodenext — Node.js ESM алгоритм (обязателен для ESM)
bundler       — для проектов с webpack/vite/esbuild (TS 5.0+)
```

### `node` (legacy CJS)

Работает как Node.js в режиме CommonJS:
- `"./utils"` → ищет `./utils.ts`, `./utils.js`, `./utils/index.ts`
- `"lodash"` → ищет в `node_modules/lodash`

Не поддерживает ESM-специфику (`import.meta`, условные exports в `package.json`).

### `node16` / `nodenext`

Обязателен, если `"module": "node16"` или `"module": "nodenext"`. Отражает реальное поведение Node.js с ESM:

```ts
// С node16: расширения ОБЯЗАТЕЛЬНЫ для относительных импортов:
import { foo } from "./utils";     // ❌ в ESM нужно расширение
import { foo } from "./utils.js";  // ✅ — TypeScript найдёт utils.ts

// В CJS-файле (.cts или "type": "commonjs"):
const { foo } = require("./utils"); // ✅ без расширения OK
```

```json
// package.json условный экспорт — node16 понимает:
{
  "exports": {
    ".": {
      "import": "./dist/index.mjs",
      "require": "./dist/index.cjs"
    }
  }
}
```

### `bundler` (TypeScript 5.0+)

Создан специально для проектов, где бандлер (webpack, vite, esbuild) обрабатывает импорты:

```ts
// bundler: расширения опциональны (бандлер разберётся):
import { foo } from "./utils";     // ✅ — как в node
import { foo } from "./utils.js";  // ✅ — тоже OK

// Поддерживает package.json exports (как node16):
import { something } from "some-lib/feature"; // ✅ через exports map
```

**Ключевое отличие от `node16`:** не требует явных расширений в импортах. Подходит для большинства современных фронтенд-проектов.

```json
// tsconfig для Next.js/Vite проекта:
{
  "compilerOptions": {
    "module": "esnext",
    "moduleResolution": "bundler",
    "target": "es2022"
  }
}
```

---

## `isolatedModules`

Требует, чтобы каждый файл мог быть скомпилирован независимо, без информации о других файлах. Это обязательно при использовании Babel, esbuild или SWC — они транспилируют по одному файлу без межфайлового анализа.

### Что запрещает `isolatedModules`

```ts
// 1. const enum — значения раскрываются только при cross-file анализе:
const enum Direction { Up = 0, Down = 1 }
const d = Direction.Up; // ❌ Cannot use 'const enum' with isolatedModules

// Замена: обычный enum или as const object:
const Direction = { Up: 0, Down: 1 } as const;

// 2. Re-export типов без type keyword:
export { SomeType }; // ❌ — SomeType может быть только типом
export type { SomeType }; // ✅ явный type export

// 3. namespace (кроме ambient):
namespace Utils { // ❌ в .ts файлах с isolatedModules
  export function format() {}
}

// 4. Импорт типа без type keyword при re-export:
import { MyType } from "./types";
export { MyType }; // ❌ — не ясно, тип или значение
export type { MyType }; // ✅
```

### `verbatimModuleSyntax` (TS 5.0+) — современная альтернатива

Более строгая версия: если вы импортируете что-то только как тип — обязан писать `import type`. Иначе компилятор не может выбросить импорт при emit:

```ts
// verbatimModuleSyntax: true:
import { User } from "./types";   // ❌ — если User — только тип
import type { User } from "./types"; // ✅

import { createUser, type User } from "./api"; // ✅ inline type
```

---

## `skipLibCheck`

Пропускает проверку типов в `.d.ts` файлах (включая `node_modules/@types/**`):

```json
{
  "compilerOptions": {
    "skipLibCheck": true // очень распространено, но понимать trade-off важно
  }
}
```

**Почему используют:** конфликты типов между разными версиями `@types/*`, ошибки в чужих `.d.ts` файлах, ускорение компиляции больших проектов.

**Риски `skipLibCheck: true`:**
- Скрывает реальные несовместимости между зависимостями
- Конфликт между `@types/node` v18 и `@types/node` v20 — не увидите
- Ошибка в `.d.ts` библиотеки, которая влияет на ваш код — не поймаете

**Лучшая практика:**

```json
// Компромисс: проверять только свои файлы:
{
  "compilerOptions": {
    "skipLibCheck": true,   // пропустить node_modules
    "strict": true          // но свой код — строго
  }
}
```

---

## `target` и `lib` — что они контролируют

Частая путаница: `target` и `lib` — разные вещи.

```txt
target — определяет, в какой JS TypeScript генерирует код
         (синтаксические преобразования: arrow → function, class → prototype)

lib — определяет, какие API TypeScript считает доступными
      (типы для Array.prototype.at, Promise.allSettled и т.д.)
```

```json
{
  "compilerOptions": {
    "target": "es2017",  // генерировать ES2017 синтаксис
    "lib": ["es2022", "dom"] // но ЗНАТЬ API до ES2022 + DOM
  }
}
```

Это позволяет использовать современные API в коде (которые предоставит полифилл или runtime), но генерировать более совместимый синтаксис.

```ts
// target: es2017, lib: es2022:
const result = arr.at(-1); // ✅ — TypeScript знает .at(), lib: es2022
// Генерирует: const result = arr.at(-1); (не трансформируется)
// Ваш полифилл обеспечивает наличие arr.at в старом браузере

// target: es5 + downlevelIteration:
for (const x of set) {} // Трансформируется в ES5 for loop
```

---

## Типичный `tsconfig.json` для разных проектов

### Node.js backend (ESM)

```json
{
  "compilerOptions": {
    "target": "es2022",
    "module": "node16",
    "moduleResolution": "node16",
    "lib": ["es2022"],
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "skipLibCheck": true
  }
}
```

### Frontend (Vite / Next.js)

```json
{
  "compilerOptions": {
    "target": "es2022",
    "module": "esnext",
    "moduleResolution": "bundler",
    "lib": ["es2022", "dom", "dom.iterable"],
    "jsx": "react-jsx",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "verbatimModuleSyntax": true,
    "isolatedModules": true,
    "noEmit": true,
    "skipLibCheck": true
  }
}
```

### Библиотека (публикация в npm)

```json
{
  "compilerOptions": {
    "target": "es2020",
    "module": "node16",
    "moduleResolution": "node16",
    "declaration": true,
    "declarationDir": "./dist/types",
    "declarationMap": true,
    "emitDeclarationOnly": true,
    "strict": true,
    "stripInternal": true  // убрать @internal комментарии из .d.ts
  }
}
```

---

## `paths` и `baseUrl` — алиасы импортов

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"],
      "@components/*": ["./src/components/*"],
      "@utils/*": ["./src/utils/*"]
    }
  }
}
```

```ts
// Теперь вместо:
import { Button } from "../../../components/Button";
// Можно:
import { Button } from "@components/Button"; // ✅
```

**Важно:** `paths` — только для TypeScript. Бандлер (webpack, vite) нужно настроить отдельно. Для Vite — `resolve.alias`, для webpack — `resolve.alias` или `tsconfig-paths-webpack-plugin`.

---

## Типичные ошибки на интервью

- **"strict — это одна опция"** — нет, это группа из 8 флагов. Называть `strictNullChecks` и `noImplicitAny` по отдельности и объяснять, что каждый ловит — признак глубокого понимания.

- **"skipLibCheck безопасен"** — он компромисс. Скрывает ошибки в `.d.ts` зависимостей. В крупных проектах иногда необходим, но нужно знать риски.

- **Не знать разницу между `target` и `lib`** — `target` преобразует синтаксис, `lib` добавляет знание об API. Можно иметь `target: "es5"` и `lib: ["es2022"]` — будет транспилироваться синтаксис, но TypeScript будет знать современные API.

- **"moduleResolution: node — всегда правильно"** — устарело для ESM-проектов. Node.js ESM требует `node16`/`nodenext` с обязательными расширениями. Для фронтенда с бандлером — `bundler` (TS 5.0+).

- **Не понимать `isolatedModules`** — "почему нельзя использовать `const enum`?" Потому что `isolatedModules` запрещает всё, что требует cross-file анализа. Babel/esbuild компилируют по файлу и не могут раскрыть `const enum` значения.

- **Не знать про `noUncheckedIndexedAccess`** — это одна из самых полезных опций вне `strict`, которая ловит `undefined` при обращении к элементам массива/ключам объекта. Многие даже senior-разработчики о ней не знают.

- **Путать `declaration` и `emitDeclarationOnly`** — `declaration: true` генерирует `.d.ts` вместе с `.js`. `emitDeclarationOnly: true` генерирует **только** `.d.ts`, без `.js` — используется когда транспиляцией занимается бандлер.
