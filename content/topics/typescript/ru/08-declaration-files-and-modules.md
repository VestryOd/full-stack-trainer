<!-- verified: 2026-06-23, corrections: 0 -->
# Файлы деклараций и модули

## Что такое `.d.ts` файлы и зачем они нужны

`.d.ts` — файл, содержащий только объявления типов. Никакого исполняемого кода — только сигнатуры, интерфейсы, типы. TypeScript использует их для понимания API библиотек, написанных на JavaScript.

```txt
Источники типов в TypeScript-проекте:

1. .ts файлы — содержат и типы, и код
2. .d.ts файлы — только объявления типов (генерируются из .ts
   при компиляции или написаны вручную для JS-библиотек)
3. @types/* пакеты — .d.ts файлы для популярных JS-библиотек
   (например, @types/express, @types/lodash)
4. tsconfig lib — встроенные типы для DOM, ES2022 и т.д.
```

Когда TypeScript встречает `import { foo } from "some-library"`, он ищет типы в следующем порядке:
1. Поле `types` или `typings` в `package.json` библиотеки
2. `index.d.ts` в корне пакета
3. Пакет `@types/some-library` в `node_modules/@types/`
4. Если ничего не найдено — тип `any` (и предупреждение при `noImplicitAny`)

---

## Ambient declarations — объявление без реализации

`declare` — ключевое слово, которое говорит TypeScript: "это существует в runtime, но определено где-то снаружи". В `.d.ts` файле `declare` подразумевается везде, но в `.ts` файле его нужно писать явно.

```ts
// global.d.ts
declare const __VERSION__: string;           // глобальная переменная
declare function require(id: string): any;   // глобальная функция
declare class EventEmitter {                 // глобальный класс
  on(event: string, listener: Function): this;
  emit(event: string, ...args: any[]): boolean;
}

// Объявление модуля (ambient module):
declare module "*.svg" {
  const content: string;
  export default content;
}

declare module "*.png" {
  const src: string;
  export default src;
}
```

Последние два — типичный паттерн для webpack/vite проектов: TypeScript не знает, что импорт `.svg` даёт, поэтому нужно объявить ambient модуль.

### `declare global` — расширение глобального namespace

```ts
// types/global.d.ts
export {}; // делает файл модулем, а не скриптом

declare global {
  interface Window {
    analytics: {
      track(event: string, props?: Record<string, unknown>): void;
    };
  }

  // Глобальная переменная, доступная без import:
  const __DEV__: boolean;
}
```

Без `export {}` файл считается скриптом (не модулем) и его объявления глобальны автоматически. С `export {}` файл становится модулем, и для расширения глобального scope нужен `declare global {}`.

---

## Declaration Merging — слияние деклараций

TypeScript позволяет нескольким объявлениям с одним именем автоматически сливаться. Это работает для: `interface`, `namespace`, `function` (overloads), `class + interface`, `enum`.

### interface + interface

```ts
// Два объявления User сливаются в одно:
interface User {
  id: number;
  name: string;
}

interface User {
  email: string;
  createdAt: Date;
}

// Итоговый User: { id: number; name: string; email: string; createdAt: Date }
const user: User = {
  id: 1,
  name: "Alice",
  email: "alice@example.com",
  createdAt: new Date(),
}; // ✅
```

### namespace + class / namespace + function

Namespace может сливаться с классом или функцией того же имени — это паттерн для добавления статических членов или свойств функции:

```ts
function validator(value: string): boolean {
  return validator.pattern.test(value);
}

namespace validator {
  export const pattern = /^[a-z]+$/;
  export function create(pattern: RegExp): typeof validator {
    return (v: string) => pattern.test(v);
  }
}

// Использование:
validator("hello");           // ✅ вызов функции
validator.pattern;            // ✅ свойство из namespace
validator.create(/^\d+$/);    // ✅ метод из namespace
```

### enum + namespace

Добавление статических методов к enum:

```ts
enum Direction {
  Up = "UP",
  Down = "DOWN",
  Left = "LEFT",
  Right = "RIGHT",
}

namespace Direction {
  export function opposite(dir: Direction): Direction {
    const map: Record<Direction, Direction> = {
      [Direction.Up]: Direction.Down,
      [Direction.Down]: Direction.Up,
      [Direction.Left]: Direction.Right,
      [Direction.Right]: Direction.Left,
    };
    return map[dir];
  }
}

Direction.opposite(Direction.Up); // Direction.Down ✅
```

---

## Module Augmentation — расширение типов сторонних библиотек

Самый практически важный use-case для слияния деклараций — дополнение типов из `node_modules` без форка библиотеки.

### Расширение Express

```ts
// src/types/express.d.ts
import "express";

declare module "express-serve-static-core" {
  interface Request {
    user?: {
      id: number;
      email: string;
      role: "admin" | "user";
    };
    requestId: string;
  }
}
```

Почему `express-serve-static-core`, а не `express`? Потому что типы Express разбиты по нескольким внутренним модулям, и `Request` определён именно там. Найти правильный модуль для augmentation — навык, требующий чтения исходных `.d.ts` файлов:

```bash
node_modules/@types/express/index.d.ts
# → смотрим, откуда импортируется Request
# → находим: import * as e from "express-serve-static-core"
```

### Расширение Fastify

```ts
// src/types/fastify.d.ts
import "fastify";

declare module "fastify" {
  interface FastifyRequest {
    user: { id: number; role: string } | undefined;
  }

  interface FastifyInstance {
    config: {
      PORT: number;
      DATABASE_URL: string;
    };
  }
}
```

### Расширение глобальных типов (Window, process.env)

```ts
// src/types/env.d.ts
declare namespace NodeJS {
  interface ProcessEnv {
    NODE_ENV: "development" | "production" | "test";
    DATABASE_URL: string;
    JWT_SECRET: string;
    PORT?: string; // необязательная
  }
}
```

После этого `process.env.DATABASE_URL` имеет тип `string` (не `string | undefined`), а `process.env.TYPO` — ошибка компиляции.

### Расширение сторонних типов через `@types`

Если у библиотеки нет своих типов и вы хотите их дополнить:

```ts
// node_modules/@types/some-lib/index.d.ts НЕ ТРОГАЕМ
// Вместо этого — src/types/some-lib.d.ts:

import "some-lib";

declare module "some-lib" {
  // Добавляем отсутствующий метод:
  interface SomeClass {
    missingMethod(arg: string): void;
  }

  // Добавляем отсутствующий экспорт:
  export function newHelper(): void;
}
```

**Важное ограничение module augmentation:** нельзя создать новый модуль через augmentation — можно только расширить существующий. Для несуществующего модуля нужен ambient module:

```ts
// Ambient module (новый модуль):
declare module "some-untyped-lib" {
  export function doSomething(): void;
  export const VERSION: string;
}

// Module augmentation (расширение существующего):
declare module "some-typed-lib" {
  interface ExistingInterface {
    newField: string; // ✅
  }
}
```

---

## Namespace vs Module — история и современность

### Что такое namespace

`namespace` (ранее назывался `module` до TypeScript 1.5) — это способ организации кода в пространства имён до появления ES-модулей:

```ts
namespace Utils {
  export interface Logger {
    log(message: string): void;
  }

  export function formatDate(date: Date): string {
    return date.toISOString();
  }

  export namespace Strings {
    export function capitalize(s: string): string {
      return s.charAt(0).toUpperCase() + s.slice(1);
    }
  }
}

const formatted = Utils.formatDate(new Date());
Utils.Strings.capitalize("hello");
```

### Почему namespace — преимущественно legacy

```txt
Проблема namespace:

1. Нет tree-shaking — весь namespace включается в бандл
2. Нет явных зависимостей — неясно, что откуда приходит
3. Конфигурация для компилятора сложнее (outFile, concatenate)
4. Не совместим с ES-модулями нативно
5. Отладка в браузере хуже — нет source map интеграции с модулями

Современная альтернатива — ES-модули (import/export):
  - Нативно поддерживаются всеми бандлерами
  - Tree-shaking работает из коробки
  - Явные зависимости между файлами
  - Совместимо с Node.js ESM
```

### Когда namespace всё ещё оправдан

```ts
// 1. Ambient declarations для глобальных библиотек (legacy):
declare namespace jQuery {
  function ajax(url: string, settings?: AjaxSettings): JqXHR;
  interface AjaxSettings {
    method?: "GET" | "POST";
    data?: object;
  }
}

// 2. Группировка типов внутри d.ts файла:
declare namespace API {
  interface User { id: number; name: string }
  interface Post { id: number; title: string; authorId: number }
  interface Response<T> { data: T; status: number }
}

// 3. Слияние с enum или function (показано выше)
```

### Отличие `module "foo"` от `namespace`

```ts
// Ambient module (для типизации JS-библиотек):
declare module "lodash" {
  export function chunk<T>(array: T[], size: number): T[][];
}

// Это НЕ то же самое, что namespace!
// declare module создаёт описание ES-модуля
// namespace создаёт глобальное пространство имён
```

---

## Triple-slash directives — директивы с тремя косыми

Triple-slash директивы — специальные однострочные комментарии в начале файла, которые TypeScript интерпретирует как инструкции.

```ts
/// <reference types="node" />
/// <reference path="./types/custom.d.ts" />
/// <reference lib="es2022" />
```

### `reference types`

Явно подключает пакет из `@types/*`. Нужен редко — обычно TypeScript находит типы автоматически через `node_modules/@types/`:

```ts
/// <reference types="node" />

// Теперь доступны типы Node.js:
process.env.NODE_ENV; // ✅
Buffer.from("hello"); // ✅
```

**Когда реально нужен:** в `.d.ts` файлах для библиотек, которые зависят от других типов:

```ts
// my-library/index.d.ts
/// <reference types="node" />

export function readFile(path: string): Buffer;
```

### `reference path`

Явно включает другой `.d.ts` файл:

```ts
/// <reference path="./vendor/legacy-lib.d.ts" />

// Это устаревший паттерн — раньше использовался вместо import
// Сейчас лучше: import type { LegacyType } from "./vendor/legacy-lib"
```

### `reference lib`

Подключает встроенную библиотеку TypeScript:

```ts
/// <reference lib="es2022.array" />

// Теперь доступен Array.prototype.at():
[1, 2, 3].at(-1); // ✅
```

### Современная практика

```txt
Используй triple-slash директивы когда:
  - Пишешь .d.ts файл для библиотеки (reference types)
  - Работаешь с legacy-кодом без модульной системы (reference path)

НЕ используй когда:
  - Пишешь обычный .ts файл — используй import
  - Подключаешь типы в проекте — используй tsconfig.json compilerOptions.types
```

```json
// tsconfig.json — вместо triple-slash в каждом файле:
{
  "compilerOptions": {
    "types": ["node", "jest"],
    "lib": ["es2022", "dom"]
  }
}
```

---

## Структура реального проекта с .d.ts файлами

```txt
src/
  types/
    global.d.ts        — declare global { Window, ProcessEnv }
    express.d.ts       — module augmentation для express
    assets.d.ts        — declare module "*.svg", "*.png"
    api.d.ts           — общие типы API (может быть .ts, не .d.ts)

Когда создавать .d.ts, а не .ts:
  - Файл содержит ТОЛЬКО типы, ни одной строки кода
  - Описываете ambient-среду (глобальные переменные)
  - Делаете module augmentation
  - Поставляете типы к JavaScript-библиотеке

Когда использовать .ts с только типами (type-only .ts):
  - Хотите использовать import/export между файлами типов
  - Не нужна ambient-семантика
```

### Генерация .d.ts при компиляции

```json
// tsconfig.json
{
  "compilerOptions": {
    "declaration": true,       // генерировать .d.ts
    "declarationDir": "./dist/types", // куда складывать
    "declarationMap": true,    // source maps для .d.ts (для go-to-definition)
    "emitDeclarationOnly": true // только .d.ts, без .js (если бандлер сам транспилирует)
  }
}
```

```ts
// src/utils.ts
export function formatDate(date: Date): string {
  return date.toISOString().split("T")[0];
}

// Генерируется dist/types/utils.d.ts:
export declare function formatDate(date: Date): string;
```

---

## Типичные ошибки на интервью

- **"namespace — это то же самое, что ES-модуль"** — нет. Namespace компилируется в объект (IIFE-паттерн в JS), не в ES-модуль. У namespace нет tree-shaking, явных зависимостей, нативной поддержки в бандлерах. Для нового кода используйте `import`/`export`.

- **Не знать разницу между `.d.ts` и `.ts` с только типами** — `.d.ts` файл никогда не компилируется в JavaScript. Он существует только для TypeScript. `.ts` файл с только типами компилируется в пустой `.js`. Для ambient деклараций и module augmentation нужен именно `.d.ts`.

- **"Module augmentation работает для любого модуля"** — можно расширить только существующий модуль. Если пытаетесь расширить несуществующий или неправильно указываете имя модуля — augmentation молча не работает (TypeScript не выдаёт ошибку!).

- **Не знать, почему `declare global` нужен `export {}`** — без `export {}` файл — скрипт (не модуль), все объявления глобальны без `declare global`. С `export {}` файл — модуль, и чтобы расширить глобальный scope нужен `declare global {}`. Путаница между script и module — частая причина "почему мои типы не подхватываются".

- **Не читать чужие `.d.ts` файлы** — умение открыть `node_modules/@types/express/index.d.ts` и найти нужный интерфейс для augmentation — базовый senior-навык. "Я просто добавил в `declare module 'express'"` вместо `'express-serve-static-core'"` — классическая ошибка.

- **Использовать triple-slash в обычных `.ts` файлах** — в современных проектах triple-slash в `.ts` файлах — архаизм. Исключение: `.d.ts` файлы библиотек, где `/// <reference types="..." />` — легитимный способ объявить зависимость от другого пакета типов.
