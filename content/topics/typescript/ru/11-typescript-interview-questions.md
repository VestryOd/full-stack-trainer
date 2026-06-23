# TypeScript — Вопросы для собеседования (Senior)

## Группа 1: Система типов — основы

**Чем структурная типизация TypeScript отличается от номинальной? Приведите пример, где это важно.**

TypeScript сравнивает совместимость типов по их форме (набору полей и методов), а не по имени. Два класса с одинаковыми полями совместимы, даже если объявлены независимо. Пример где это важно: `type UserId = number` и `type OrderId = number` — один и тот же тип; функция, принимающая `UserId`, примет `OrderId` без ошибки. Чтобы сделать их несовместимыми, нужны branded types: `type UserId = number & { readonly __brand: "UserId" }`.

---

**Что такое excess property check и почему он срабатывает только для объектных литералов?**

Excess property check — дополнительная проверка, которая запрещает лишние поля при передаче объектного литерала напрямую. Она не является частью структурной типизации — это отдельный механизм для раннего обнаружения опечаток в именах полей. При передаче через переменную проверка не срабатывает, потому что переменная может быть использована в других местах, где лишние поля допустимы. `const opts = { timeout: 3000, retries: 3 }; configure(opts);` — ✅, но `configure({ timeout: 3000, retries: 3 })` — ❌ если `retries` не в типе.

---

**В чём разница между `type` и `interface` помимо синтаксиса? Когда использовать каждый?**

Два ключевых отличия: (1) `interface` поддерживает declaration merging — несколько объявлений с одним именем автоматически сливаются. `type` объявить дважды — ошибка. (2) `type` умеет union, tuple, conditional types — `interface` нет. Практическое правило: `interface` для объектов и классов (особенно если планируется module augmentation), `type` для всего остального — union, tuple, mapped/conditional types.

---

**Почему `let x = "hello"` даёт тип `string`, а `const x = "hello"` — `"hello"`?**

TypeScript применяет widening (расширение): для `let` переменную можно переприсвоить (`x = "world"` — валидно), поэтому тип расширяется до `string`. `const` переприсвоить нельзя — значение фиксировано, тип можно оставить литеральным. Тот же принцип для полей объекта: `const obj = { x: "hello" }` даёт `{ x: string }`, а не `{ x: "hello" }`, потому что `obj.x = "world"` — легально. Исправление: `as const`.

---

**Как TypeScript выполняет control flow анализ? Что происходит после `if (x == null) return`?**

TypeScript строит граф потока управления для каждой функции. В каждой точке графа он отслеживает тип каждой переменной с учётом всех предыдущих проверок. После `if (x == null) return` TypeScript знает: в коде ниже `x` не может быть `null` или `undefined` (потому что `== null` ловит оба). Тип сужается — обе nullish-значения убираются из union. `==` (двойное равенство) в этом специфическом случае TypeScript понимает семантически.

---

## Группа 2: Дженерики

**Почему дженерики TypeScript — это не "шаблоны как в C++"?**

В C++ шаблоны раскрываются при компиляции в конкретный код для каждого типа. В TypeScript дженерик — переменная типа, которую компилятор *выводит* при вызове. Вся типизация стирается в runtime — в JavaScript нет ни `T`, ни `string`, ни `number`. Ещё важнее: TypeScript *решает уравнение* для T из аргументов функции. `identity(42)` — TypeScript видит `number → T`, выводит `T = number`. Это вывод типов, а не раскрытие шаблона.

---

**Что делает `K extends keyof T` и зачем это нужно вместо просто `string`?**

`K extends keyof T` ограничивает K до ключей конкретного объекта T. Если написать просто `K extends string` — можно передать любую строку, включая несуществующие ключи. С `K extends keyof T` TypeScript гарантирует, что ключ существует, и выводит точный тип значения `T[K]`. Функция `getProperty<T, K extends keyof T>(obj: T, key: K): T[K]` — при вызове `getProperty(user, "name")` TypeScript выводит `K = "name"` и возвращаемый тип `string`, а не `unknown`.

---

**В чём разница между generic-функцией и generic-классом в контексте вывода типов?**

У generic-функции тип параметра `T` выводится заново при каждом вызове: `wrap("hello")` → `T = string`, `wrap(42)` → `T = number`. У generic-класса `T` фиксируется при инстанциации — `new Stack<number>()` фиксирует `T = number` для всего экземпляра, и `stack.push("hello")` — ошибка. Разные экземпляры могут иметь разный `T`: `new Stack<string>()` и `new Stack<number>()` — независимые типы.

---

**Реализуйте `Awaited<T>` с нуля. Почему он не просто проверяет `instanceof Promise`?**

```ts
type Awaited<T> =
  T extends null | undefined ? T :
  T extends object & { then(onfulfilled: infer F, ...args: any[]): any }
    ? F extends (value: infer V, ...args: any[]) => any
      ? Awaited<V>
      : never
    : T;
```
Не `instanceof` потому что TypeScript использует duck typing: любой объект с методом `.then()` считается thenable. Это совместимо с нестандартными Promise-реализациями (Bluebird, кастомные обёртки). `instanceof Promise` — runtime-проверка, которая не работает на уровне типов. Рекурсия нужна для `Promise<Promise<T>>`.

---

**Что произойдёт при `pair(1, "hello")` если сигнатура `function pair<T>(a: T, b: T): [T, T]`?**

TypeScript выведет `T = string | number` — наименьший общий суперт­ип. Оба аргумента удовлетворяют `string | number`. Результат: `[string | number, string | number]`. Это часто не то, что нужно. Правильнее: `function pair<A, B>(a: A, b: B): [A, B]` — два независимых параметра.

---

## Группа 3: Условные и отображённые типы

**Что такое дистрибутивные условные типы? Почему `IsString<string | number>` = `boolean`, а не `false`?**

Когда условный тип применяется к голому (bare) параметру `T`, TypeScript распределяет его по членам union: `IsString<string | number>` → `IsString<string> | IsString<number>` → `true | false` → `boolean`. Это дистрибутивность. Чтобы обработать union как единое целое (недистрибутивно): обернуть в tuple `[T] extends [string]`. Частный случай: `T extends never` никогда не равен `true` — нужно `[T] extends [never]`.

---

**Объясните `infer` на примере. Как извлечь тип элемента Promise?**

`infer R` создаёт переменную типа R, которую TypeScript заполняет при сопоставлении паттерна:
```ts
type UnwrapPromise<T> = T extends Promise<infer R> ? R : T;
type A = UnwrapPromise<Promise<string>>; // string
type B = UnwrapPromise<number>;          // number
```
`infer` работает только внутри ветки `extends` условного типа — это не объявление нового generic-параметра, а извлечение при сопоставлении. Можно использовать в нескольких позициях: `T extends (arg: infer A) => infer R` извлечёт и тип аргумента, и возвращаемый тип.

---

**Реализуйте `Omit<T, K>` с нуля через `Pick` и `Exclude`.**

```ts
type Omit<T, K extends keyof T> = Pick<T, Exclude<keyof T, K>>;
// Exclude<"id" | "name" | "email", "email"> = "id" | "name"
// Pick<User, "id" | "name"> = { id: number; name: string }
```
`Exclude` убирает из union нужные ключи, `Pick` строит объект из оставшихся. Цепочка: `keyof T` → union ключей → `Exclude` убирает K → `Pick` строит объект. Понимание этой цепочки показывает знание механики mapped types.

---

**Что делает `[K in keyof T as K extends string ? K : never]`?**

Это key remapping через `as` (TypeScript 4.1+). `K in keyof T` итерирует по всем ключам T (включая `number` и `symbol`). `as K extends string ? K : never` переименовывает каждый ключ: если K является string — оставляем K, иначе возвращаем `never`. Ключи, замапленные на `never`, исключаются из результирующего типа. Это фильтрация ключей по типу, аналог `filter` для полей объекта.

---

**Как реализовать `PickByValue<T, V>` — выбрать только поля с определённым типом значения?**

```ts
type PickByValue<T, V> = {
  [K in keyof T as T[K] extends V ? K : never]: T[K];
};

type User = { id: number; name: string; age: number; active: boolean };
type StringFields = PickByValue<User, string>; // { name: string }
type NumberFields = PickByValue<User, number>; // { id: number; age: number }
```
Ключ: `T[K] extends V ? K : never` — проверяем тип значения, а не ключа. Возвращаем K если совпадает, `never` (исключаем) если нет.

---

## Группа 4: Template Literal Types

**Как с помощью template literal types сгенерировать все CSS-свойства `margin-top`, `margin-right` и т.д.?**

```ts
type Direction = "top" | "right" | "bottom" | "left";
type MarginProperty = `margin-${Direction}`;
// "margin-top" | "margin-right" | "margin-bottom" | "margin-left"
```
TypeScript перемножает все комбинации, когда в интерполяцию подставляется union. Два union перемножаются: `${A | B}-${C | D}` = `"A-C" | "A-D" | "B-C" | "B-D"`. При очень большом числе комбинаций TypeScript выдаёт "Expression produces a union type that is too complex to represent".

---

**Напишите тип, извлекающий параметры из пути `/users/:id/posts/:postId`.**

```ts
type ExtractParams<Path extends string> =
  Path extends `${string}:${infer Param}/${infer Rest}`
    ? Param | ExtractParams<`/${Rest}`>
    : Path extends `${string}:${infer Param}`
    ? Param
    : never;

type P = ExtractParams<"/users/:id/posts/:postId">; // "id" | "postId"
```
Паттерн рекурсивный: извлекаем первый параметр до `/`, затем применяем тип к хвосту строки. Без рекурсии нельзя обработать произвольное число параметров.

---

## Группа 5: Утилитарные типы

**В чём разница между `Exclude` и `Omit`? Частая путаница.**

`Exclude<T, U>` — работает с union types, убирает из T члены, совместимые с U: `Exclude<"a" | "b" | "c", "b">` = `"a" | "c"`. `Omit<T, K>` — работает с ключами объекта, убирает поля: `Omit<User, "email">` = объект без поля email. Фактически `Omit` реализован через `Exclude`: `Omit<T, K> = Pick<T, Exclude<keyof T, K>>`. Перепутать их — классическая ошибка: применить `Exclude` к объекту или `Omit` к union.

---

**Зачем нужен `InstanceType<T>`? Когда без него не обойтись?**

`InstanceType<T>` извлекает тип экземпляра из конструктора класса. Нужен когда класс передаётся как значение (не инстанцируется напрямую):
```ts
function createInstance<T extends new (...args: any[]) => any>(
  Ctor: T, ...args: ConstructorParameters<T>
): InstanceType<T> {
  return new Ctor(...args);
}
```
Без `InstanceType` возвращаемый тип был бы `{}` или `object` — потеря информации о конкретном классе. Используется в DI-контейнерах, фабриках, декораторах.

---

**Как получить тип результата async-функции (без Promise-обёртки)?**

```ts
async function fetchUser() {
  return { id: 1, name: "Alice" };
}

type User = Awaited<ReturnType<typeof fetchUser>>;
// { id: number; name: string }
```
`ReturnType` вернёт `Promise<{ id: number; name: string }>`. `Awaited` рекурсивно разворачивает Promise. Комбинация `Awaited<ReturnType<typeof fn>>` — стандартный паттерн для получения типа данных из async-функции.

---

## Группа 6: Сужение типов и type guards

**Почему TypeScript не может сузить тип через пользовательскую функцию без `is`?**

Без `is` TypeScript видит только то, что функция возвращает `boolean`. Он не анализирует тело функции, чтобы понять семантику проверки — это было бы слишком дорого и неточно. С `value is string` разработчик явно говорит компилятору: "если функция вернула `true` — тип `value` в вызывающем коде сужается до `string`". Это контракт, который TypeScript принимает на веру — он не верифицирует корректность тела guard-функции.

---

**В чём разница между `asserts value is T` и `value is T`? Когда использовать каждый?**

`value is T` — возвращает `boolean`, используется в `if`-условии. Сужение действует только внутри ветки `if`. `asserts value is T` — возвращает `void`, выбрасывает исключение если условие не выполнено. После вызова тип сужён в коде ниже, без `if`. Используйте `value is T` когда нужна ветвящаяся логика. `asserts value is T` — когда значение обязано соответствовать типу, иначе выполнение не должно продолжаться (validation function, precondition check).

---

**Что такое exhaustiveness checking и как его реализовать?**

Паттерн гарантирует, что все варианты discriminated union обработаны. Реализация:
```ts
function assertNever(value: never): never {
  throw new Error(`Unhandled case: ${JSON.stringify(value)}`);
}

switch (shape.kind) {
  case "circle": return ...;
  case "square": return ...;
  default: return assertNever(shape); // ❌ если добавить новый вариант без case
}
```
Если добавить новый вариант в union без соответствующего `case` — TypeScript выдаст ошибку: "Argument of type '{ kind: "rectangle" }' is not assignable to parameter of type 'never'". Это compile-time защита от забытых веток.

---

**Почему `typeof null === "object"` — ловушка в TypeScript? Как правильно проверить объект?**

`typeof null` в JavaScript исторически возвращает `"object"` — это известная ошибка в спецификации, которую не исправляли ради обратной совместимости. TypeScript не скрывает это поведение: после `typeof value === "object"` тип сужается до `object | null`. Правильная проверка на объект: `typeof value === "object" && value !== null`. Без второй части `null` остаётся в типе.

---

**Почему discriminated unions лучше объекта с опциональными полями?**

Опциональные поля позволяют невалидные комбинации: `{ data?: User; error?: Error; loading?: boolean }` — TypeScript принимает `{ data: user, error: err }` (что это значит?). Discriminated union делает невалидные состояния невыразимыми:
```ts
type State =
  | { status: "success"; data: User }
  | { status: "error"; error: Error }
  | { status: "loading" };
```
Нельзя создать `{ status: "success"; error: err }`. TypeScript сужает тип по discriminant. Плюс exhaustiveness checking работает автоматически через switch.

---

## Группа 7: Вариантность и утверждения типов

**Почему параметры функций контравариантны? Объясните на примере.**

Функция с более широким параметром безопасна там, где ожидается функция с более узким:
```ts
type CatHandler = (cat: Cat) => void;
const handler: CatHandler = (animal: Animal) => { animal.name }; // ✅
```
Почему: мы будем вызывать `handler` с `Cat`, а функция принимает `Animal` — Cat IS-A Animal, всё что у Animal есть, есть у Cat. Наоборот — небезопасно: если обязуемся принять `Animal`, но обращаемся к `cat.meow()` — Animal может не иметь этот метод. Контравариантность переворачивает направление: `(Animal) → void` является подтипом `(Cat) → void`.

---

**Почему методы в TypeScript бивариантны даже со `strictFunctionTypes`?**

`strictFunctionTypes` применяет контравариантную проверку только к function-typed properties (`handleFn: (v: T) => void`), но не к методам (`handle(v: T): void`). Это историческое решение для совместимости: строгая контравариантность методов ломала бы слишком много реального кода (особенно паттерны вроде `Array.prototype.forEach`). Чтобы получить корректную контравариантность — используйте свойство-функцию вместо метода.

---

**В чём разница между `satisfies`, явной аннотацией и `as`?**

- Явная аннотация (`const x: Config = value`) — меняет тип `x` на `Config`, детальные типы полей теряются.
- `satisfies` (`const x = value satisfies Config`) — проверяет совместимость с `Config`, но тип остаётся выведенным: поля сохраняют точные типы (например, `"localhost"` вместо `string`).
- `as` (`const x = value as Config`) — не проверяет совместимость вообще, просто утверждает тип. `{ port: 3000 } as Config` — ошибки нет, хотя `host` отсутствует.
Для конфигов: `as const satisfies Config` — получаем и readonly literal types, и проверку соответствия.

---

**Когда `as` допустим, а когда — признак архитектурной проблемы?**

Допустим: DOM API (`document.querySelector("canvas") as HTMLCanvasElement` — TypeScript не знает конкретный тип элемента), `JSON.parse` (тип `any` по природе), `Object.keys(...) as Array<keyof typeof obj>`, сторонние библиотеки с плохими типами. Признак проблемы: `return {} as User` (обход типов вместо корректной реализации), `value as any` (потеря всех гарантий), `as` вместо type guard (скрывает, что проверка нужна). Double assertion `as unknown as T` — почти всегда архитектурная проблема.

---

## Группа 8: Файлы деклараций и модули

**Чем `.d.ts` файл отличается от `.ts` файла с только типами?**

`.d.ts` файл никогда не компилируется в JavaScript — TypeScript считает его чисто декларативным. Он используется для описания ambient-окружения: глобальных переменных, сторонних библиотек, module augmentation. `.ts` файл с только типами компилируется в пустой `.js` (или файл с импортами). Для `declare global`, `declare module` и ambient module declarations нужен именно `.d.ts` контекст (или `declare` ключевое слово в `.ts`).

---

**Как расширить тип `Request` из Express для добавления поля `user`?**

```ts
// src/types/express.d.ts
import "express";

declare module "express-serve-static-core" {
  interface Request {
    user?: { id: number; role: string };
  }
}
```
Важно: нужно расширять `"express-serve-static-core"`, а не `"express"` — именно там определён интерфейс `Request`. Найти правильный модуль можно через `node_modules/@types/express/index.d.ts`. Без `import "express"` файл может не работать как модуль, и слияние не произойдёт.

---

**Почему `export {}` важен в `.d.ts` файле с `declare global`?**

Без `export {}` TypeScript считает файл скриптом (не модулем) — все объявления автоматически глобальны без `declare global {}`. С `export {}` файл становится модулем, и для расширения глобального scope нужен явный блок `declare global {}`. Без этого различия объявления могут применяться непредсказуемо: или всё глобально (нежелательно в модульной архитектуре), или ничего (если TypeScript решит что файл — модуль, но `declare global` не написан).

---

**В каких случаях namespace ещё оправдан в современном TypeScript?**

Три случая: (1) Ambient declarations для глобальных библиотек, загружаемых через `<script>` (jQuery, старые SDK): `declare namespace jQuery { ... }`. (2) Группировка типов в `.d.ts` файле: `declare namespace API { interface User {...} }` — удобная организация без создания файловых модулей. (3) Слияние с enum или function для добавления статических методов. В обычном `.ts` коде — используйте ES-модули.

---

## Группа 9: Продвинутые паттерны

**Что такое branded types? Как они работают без runtime overhead?**

Branded type добавляет фиктивное поле-маркер, которое делает типы структурно несовместимыми:
```ts
type UserId = number & { readonly __brand: "UserId" };
```
Поле `__brand` существует только в типе TypeScript. При компиляции `type UserId = number & { __brand: "UserId" }` стирается — в JavaScript это просто `number`. Нет никакого wrapper-объекта, нет проверок в runtime. Создание значения: `const id = 42 as UserId` — `as` убирает структурную проверку для инициализации.

---

**Чем phantom type отличается от branded type?**

Branded type: поле-маркер в самом типе (`T & { __brand: ... }`). Phantom type: неиспользуемый generic-параметр (`type FormData<TState> = { name: string } & { __state: TState }`). Цель похожа — добавить compile-time различие без runtime изменений. Phantom types удобнее для кодирования состояний (Validated/Unvalidated), branded — для разграничения одноимённых примитивов (UserId vs OrderId). Оба подхода работают без runtime overhead.

---

**Как реализовать рекурсивный тип для JSON-значений?**

```ts
type JSONPrimitive = string | number | boolean | null;
type JSONObject    = { [key: string]: JSONValue };
type JSONArray     = JSONValue[];
type JSONValue     = JSONPrimitive | JSONObject | JSONArray;
```
Рекурсия работает через косвенность: `JSONValue` ссылается на `JSONObject` и `JSONArray`, которые в свою очередь используют `JSONValue`. Прямая рекурсия к примитиву не работает. Ограничение: глубина рекурсии ~100 уровней. Для реально больших JSON-структур нужна runtime-валидация (Zod).

---

**Когда type-level программирование следует заменить runtime-валидацией?**

TypeScript проверяет типы только на этапе компиляции — в runtime типов нет. Если данные приходят извне (`req.body`, `JSON.parse`, `localStorage`), типы TypeScript ничего не гарантируют. `const user = req.body as User` — ложная безопасность. Когда нужна проверка значений (email формат, положительное число, не пустая строка) — типы бессильны, нужен runtime-валидатор (Zod, Yup, io-ts). Правило: type-level — для compile-time гарантий и DX; runtime-валидация — для системных границ (HTTP, файлы, env).

---

## Группа 10: Компилятор и конфигурация

**Что входит в `"strict": true`? Назовите минимум 4 флага и что каждый ловит.**

`strict` включает 8 флагов: `strictNullChecks` (null/undefined не совместимы с другими типами), `noImplicitAny` (запрет неявного any для параметров и переменных), `strictFunctionTypes` (контравариантность параметров функций), `strictBindCallApply` (типизация .bind/.call/.apply), `strictPropertyInitialization` (поля класса должны быть инициализированы в конструкторе), `noImplicitThis` (this не может быть any), `alwaysStrict` ("use strict" во всех файлах), `useUnknownInCatchVariables` (catch-переменная — unknown, не any).

---

**Чем `moduleResolution: "bundler"` отличается от `"node16"`?**

`node16` отражает реальное поведение Node.js ESM: требует явных расширений в относительных импортах (`./utils.js`), TypeScript ищет `utils.ts` по импорту `"./utils.js"`. `bundler` создан для проектов с webpack/vite/esbuild: расширения опциональны (бандлер разберётся), поддерживает `package.json` exports. `bundler` удобнее для фронтенда — не нужно писать `.js` в TypeScript-импортах. `node16` обязателен для публикации ESM-библиотек под Node.js.

---

**Что такое `isolatedModules` и почему он запрещает `const enum`?**

`isolatedModules: true` требует чтобы каждый файл компилировался независимо, без cross-file анализа. Это обязательно для Babel/esbuild/SWC — они транспилируют по одному файлу. `const enum` несовместим потому что раскрытие его значений требует доступа к другим файлам: `Direction.Up` заменяется на `0` только зная определение `Direction`. При single-file compilation — это невозможно. Замена: обычный `enum` или `as const` объект.

---

**В чём отличие `target` от `lib` в tsconfig?**

`target` управляет синтаксическими преобразованиями: `arrow functions → function`, `class → prototype`, `async/await → Promise-chain` и т.д. `lib` определяет какие API TypeScript "знает": `Array.prototype.at`, `Promise.allSettled`, `structuredClone`. Можно иметь `target: "es5"` (генерировать ES5 синтаксис) и `lib: ["es2022"]` (знать современные API, которые предоставит полифилл). Распространённая ошибка: добавить `lib: ["es2022"]` и думать, что TypeScript добавит полифилл — нет, он только добавляет типы.

---

**Почему `noUncheckedIndexedAccess` не входит в `strict`, хотя очень полезен?**

`noUncheckedIndexedAccess` добавляет `| undefined` ко всем результатам индексного доступа: `arr[0]` возвращает `T | undefined` вместо `T`. Это корректнее, но ломает огромное количество существующего кода — везде нужно добавлять проверки. Команда TypeScript приняла решение не включать его в `strict` для обратной совместимости. Для новых проектов — рекомендуется включить явно. Ловит типичный баг: `const first = arr[0]; first.toFixed()` — crash если массив пустой.

---

**Что делает `skipLibCheck: true` и какие у него риски?**

`skipLibCheck: true` пропускает проверку типов во всех `.d.ts` файлах, включая `node_modules/@types/**`. Выгоды: устраняет конфликты типов между несовместимыми версиями `@types/*`, ускоряет компиляцию. Риски: скрывает реальные несовместимости между зависимостями, ошибки в `.d.ts` библиотеки которые влияют на ваш код не обнаруживаются. Практика: `skipLibCheck: true` почти везде — но понимать что именно "пропускается" и что это компромисс, а не бесплатная оптимизация.

---

## Группа 11: Типобезопасность в архитектуре

**Как типы TypeScript помогают следовать принципу "make invalid states unrepresentable"?**

Discriminated unions кодируют состояние так, что невалидные комбинации невозможно выразить в типах:
```ts
// ❌ Можно создать { loading: true, data: user, error: err }:
type State = { loading: boolean; data?: User; error?: Error };

// ✅ Невалидные состояния невыразимы:
type State =
  | { status: "loading" }
  | { status: "success"; data: User }
  | { status: "error"; error: Error };
```
Branded types делают перепутывание семантически схожих значений ошибкой компиляции. Phantom types кодируют стадии обработки (Unvalidated → Validated). Цель — перенести проверки с runtime на compile-time.

---

**Как типизировать функцию, возвращаемый тип которой зависит от входного параметра?**

Три подхода от простого к сложному: (1) Overloads — дублирование, но читаемо. (2) Conditional return type: `function process<T extends string | number>(v: T): T extends string ? string : number`. (3) Generic с `extends` ограничением — часто достаточно. Conditional types предпочтительны для библиотечного кода, overloads — когда нужна читаемость сообщений об ошибках. TypeScript не всегда может вывести conditional return type внутри тела функции — часто нужен `as`.

---

**Что такое `Readonly<T>` и почему `const` объекта не делает его readonly?**

`const` запрещает переприсвоение переменной, но не мутацию полей объекта: `const obj = { x: 1 }; obj.x = 2; // ✅`. `Readonly<T>` делает все поля объекта `readonly` на уровне типов — попытка присвоить значение полю ловится TypeScript. `as const` делает то же рекурсивно и с literal типами. Важно: `Readonly` — compile-time ограничение. `Object.freeze()` — runtime. Для глубокой immutability нужен `DeepReadonly`.

---

**Объясните паттерн "const enum alternative" через `as const`.**

```ts
// Проблема с enum: компилируется в объект в JS, не работает с isolatedModules:
enum Status { Pending = "PENDING", Active = "ACTIVE" }

// Альтернатива:
const Status = {
  Pending: "PENDING",
  Active: "ACTIVE",
} as const;

type Status = typeof Status[keyof typeof Status];
// "PENDING" | "ACTIVE"
```
Преимущества: работает с `isolatedModules`, tree-shakeable, нет проблем с `const enum` раскрытием, тип выводится из значений. `typeof Status[keyof typeof Status]` — стандартный паттерн для union из значений `as const` объекта.

---

**Как TypeScript обрабатывает `process.env.NODE_ENV` — почему тип `string | undefined`, а не конкретный union?**

По умолчанию `process.env` типизирован как `NodeJS.ProcessEnv`: `{ [key: string]: string | undefined }`. TypeScript не знает, какие переменные установлены в конкретном окружении. Чтобы получить точный тип — расширяем интерфейс:
```ts
declare namespace NodeJS {
  interface ProcessEnv {
    NODE_ENV: "development" | "production" | "test";
    DATABASE_URL: string;
  }
}
```
После этого `process.env.NODE_ENV` — `"development" | "production" | "test"`, а `process.env.TYPO` — ошибка компиляции. Это module augmentation через declaration merging.
