# TypeScript — Вопросы для собеседования (Senior)

## Группа 1: Система типов — основы

**Чем структурная типизация TypeScript отличается от номинальной? Приведите пример, где это важно.**

TypeScript сравнивает типы по форме — набору полей и методов — и не смотрит на имя.

```txt
Структурная (TypeScript, Go):
  Два класса с одинаковыми полями совместимы,
  даже если объявлены независимо друг от друга.

Номинальная (Java, C#, Rust):
  Cat — это только то, что объявлено как Cat.
```

Где это важно: `type UserId = number` и `type OrderId = number` — один и тот же тип. Функция, принимающая `UserId`, молча примет `OrderId`. Чтобы их развести, нужны branded types: `type UserId = number & { readonly __brand: "UserId" }`.

---

**Что такое excess property check и почему он срабатывает только для объектных литералов?**

Это дополнительная проверка, которая запрещает неизвестные поля при передаче объектного литерала напрямую.

```ts
interface Options { timeout: number }
declare function configure(o: Options): void;

// ❌ Object literal may only specify known properties,
//    and 'retries' does not exist in type 'Options'
configure({ timeout: 3000, retries: 3 });

// ✅ Через переменную проверка не срабатывает:
const opts = { timeout: 3000, retries: 3 };
configure(opts);
```

Проверка не входит в структурную типизацию. Это отдельный механизм для раннего обнаружения опечаток в именах полей. При передаче через переменную она не срабатывает: переменную могут использовать и в других местах, где лишние поля как раз нужны.

---

**В чём разница между `type` и `interface` помимо синтаксиса? Когда использовать каждый?**

Отличий два: `interface` сливает повторные объявления, а `type` умеет union и tuple.

| | `interface` | `type` |
|---|---|---|
| Объявлен дважды | сливается в один | `Duplicate identifier` |
| Union, tuple | не умеет | умеет |
| Mapped, conditional | не умеет | умеет |

Практическое правило: `interface` — для объектов и классов, особенно если планируется module augmentation. `type` — для всего остального: union, tuple, mapped и conditional types.

---

**Почему `let x = "hello"` даёт тип `string`, а `const x = "hello"` — `"hello"`?**

Потому что `let` можно переприсвоить, и TypeScript расширяет тип; `const` переприсвоить нельзя, поэтому литеральный тип сохраняется.

```ts
let x = "hello";    // x: string — x = "world" должно остаться легальным
const c = "hello";  // c: "hello" — значение фиксировано

const obj = { x: "hello" };
// obj: { x: string } — obj.x = "world" легально, поле расширяется

const fixed = { x: "hello" } as const;
// fixed: { readonly x: "hello" } — расширения нет
```

Это называется widening, расширение типа. Поля объекта расширяются даже под `const`, потому что самому полю значение присвоить можно. Исправление — `as const`.

---

**Как TypeScript выполняет control flow анализ? Что происходит после `if (x == null) return`?**

TypeScript строит граф потока управления для каждой функции и в каждой его точке знает тип каждой переменной.

```ts
function f(x: string | number | null | undefined) {
  if (x == null) return;
  // x: string | number — ушли и null, и undefined,
  // потому что == null ловит оба сразу
  return typeof x === "string" ? x.toUpperCase() : x.toFixed(2);
}
```

Каждая точка графа учитывает все проверки до неё. Семантику `==` (нестрогого равенства) в этом конкретном паттерне TypeScript понимает — поэтому одна проверка убирает из union сразу два члена.

---

## Группа 2: Дженерики

**Почему дженерики TypeScript — это не "шаблоны как в C++"?**

Шаблон в C++ раскрывается при компиляции в конкретный код для каждого типа. Дженерик в TypeScript — это переменная типа, которую компилятор выводит при вызове.

```ts
function identity<T>(value: T): T { return value; }

identity(42);      // TypeScript решает number → T, значит T = number
identity("hi");    // T = string
// Скомпилированный JS: function identity(value) { return value; }
// Ни T, ни string, ни number — вся типизация стёрта
```

TypeScript *решает уравнение* для `T` по аргументам. Это вывод типов, а не раскрытие шаблона. Ничего от `T` не доезжает до JavaScript-вывода.

---

**Что делает `K extends keyof T` и зачем это нужно вместо просто `string`?**

Ограничивает `K` ключами одного конкретного объекта `T`, поэтому ключ гарантированно существует.

```ts
function getProperty<T, K extends keyof T>(obj: T, key: K): T[K] {
  return obj[key];
}

const user = { name: "Alice", age: 30 };
getProperty(user, "name");  // K = "name", возвращаемый тип string
getProperty(user, "typo");  // ❌ Argument of type '"typo"' is not
                            //    assignable to parameter of type
                            //    '"name" | "age"'
```

С `K extends string` пройдёт любая строка, включая несуществующие ключи. С `K extends keyof T` TypeScript ещё и выводит точный тип значения `T[K]` вместо `unknown`.

---

**В чём разница между generic-функцией и generic-классом в контексте вывода типов?**

У функции `T` выводится заново при каждом вызове, у класса — фиксируется один раз, при инстанциации.

```ts
declare function wrap<T>(v: T): T[];
wrap("hello");  // T = string
wrap(42);       // T = number — выводится снова, для каждого вызова

const s = new Stack<number>(); // T = number на весь экземпляр
s.push("hello");               // ❌ Argument of type 'string' is not
                               //    assignable to parameter 'number'
```

У разных экземпляров `T` может быть разным. `Stack<string>` и `Stack<number>` — независимые типы.

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

Не `instanceof`, потому что TypeScript использует duck typing: любой объект с методом `.then()` считается thenable. Это сохраняет совместимость с нестандартными реализациями Promise — Bluebird, собственные обёртки. Проверка `instanceof Promise` работает в runtime и на уровне типов бесполезна. Рекурсия нужна для `Promise<Promise<T>>`.

---

**Что произойдёт при `pair(1, "hello")` если сигнатура `function pair<T>(a: T, b: T): [T, T]`?**

Код не скомпилируется. Вывод типов фиксирует `T` по первому аргументу и отвергает второй.

```ts
declare function pair<T>(a: T, b: T): [T, T];

pair(1, "hello");
// error TS2345: Argument of type 'string' is not assignable
//    to parameter of type 'number'.

pair<string | number>(1, "hello"); // [string | number, string | number] ✅

// Два независимых параметра сохраняют оба типа точно:
declare function pair2<A, B>(a: A, b: B): [A, B];
pair2(1, "hello"); // [number, string] ✅
```

Один `T` может быть только одним типом, и вывод берёт его из первого кандидата, а не строит union. Назовите union сами или используйте два параметра типа.

---

## Группа 3: Условные и отображённые типы

**Что такое дистрибутивные условные типы? Почему `IsString<string | number>` = `boolean`, а не `false`?**

Потому что условный тип, применённый к голому (bare) параметру, распределяется по каждому члену union.

```ts
type IsString<T> = T extends string ? true : false;

type A = IsString<string | number>;
// IsString<string> | IsString<number> = true | false = boolean

// Обернуть в tuple, чтобы обработать union как единое целое:
type IsStringNonDist<T> = [T] extends [string] ? true : false;
type B = IsStringNonDist<string | number>; // false
```

Это раскладывание и называется дистрибутивностью. Частный случай: `T extends never` никогда не даёт `true`, потому что распределять не по чему — нужно `[T] extends [never]`.

---

**Объясните `infer` на примере. Как извлечь тип элемента Promise?**

`infer R` объявляет переменную типа, которую TypeScript заполняет при сопоставлении паттерна.

```ts
type UnwrapPromise<T> = T extends Promise<infer R> ? R : T;
type A = UnwrapPromise<Promise<string>>; // string
type B = UnwrapPromise<number>;          // number
```

`infer` работает только внутри ветки `extends` условного типа. Это не объявление нового generic-параметра, а извлечение при сопоставлении. Использовать его можно сразу в нескольких позициях: `T extends (arg: infer A) => infer R` вытащит и тип аргумента, и возвращаемый тип.

---

**Реализуйте `Omit<T, K>` с нуля через `Pick` и `Exclude`.**

```ts
type Omit<T, K extends keyof T> = Pick<T, Exclude<keyof T, K>>;
// Exclude<"id" | "name" | "email", "email"> = "id" | "name"
// Pick<User, "id" | "name"> = { id: number; name: string }
```

`Exclude` убирает из union ненужные ключи, а `Pick` строит объект из оставшихся. Цепочка короткая: `keyof T` даёт union ключей, `Exclude` выбрасывает `K`, `Pick` собирает объект заново.

---

**Что делает `[K in keyof T as K extends string ? K : never]`?**

Это key remapping (TypeScript 4.1+): секция `as` переименовывает каждый ключ, а ключи, переименованные в `never`, исчезают.

```ts
type OnlyStringKeys<T> = {
  [K in keyof T as K extends string ? K : never]: T[K];
};

const sym = Symbol("s");
type Mixed = { name: string; 42: boolean; [sym]: number };
type Result = OnlyStringKeys<Mixed>; // { name: string }
```

`K in keyof T` итерирует по всем ключам `T`, включая ключи типа `number` и `symbol`. То есть это фильтрация ключей по типу — аналог `filter` для полей объекта.

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

Главная деталь — `T[K] extends V ? K : never`: проверяется тип значения, а не ключа. Совпало — возвращаем `K`, не совпало — `never`, и поле выпадает.

---

## Группа 4: Template Literal Types

**Как с помощью template literal types сгенерировать все CSS-свойства `margin-top`, `margin-right` и т.д.?**

```ts
type Direction = "top" | "right" | "bottom" | "left";
type MarginProperty = `margin-${Direction}`;
// "margin-top" | "margin-right" | "margin-bottom" | "margin-left"
```

TypeScript перемножает все комбинации, когда в интерполяцию подставляется union. Два union перемножаются: `${A | B}-${C | D}` даёт `"A-C" | "A-D" | "B-C" | "B-D"`. С какого-то размера TypeScript отказывается: "Expression produces a union type that is too complex to represent".

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

Паттерн рекурсивный: берём первый параметр до `/`, затем применяем тип к остатку строки. Без рекурсии произвольное число параметров обработать нельзя.

---

## Группа 5: Утилитарные типы

**В чём разница между `Exclude` и `Omit`? Частая путаница.**

`Exclude` отфильтровывает члены union, а `Omit` убирает поля из типа объекта.

| | Работает с | Пример | Результат |
|---|---|---|---|
| `Exclude<T, U>` | членами union | `Exclude<"a" \| "b" \| "c", "b">` | `"a" \| "c"` |
| `Omit<T, K>` | ключами объекта | `Omit<User, "email">` | `User` без `email` |

Фактически `Omit` построен на `Exclude`: `Omit<T, K> = Pick<T, Exclude<keyof T, K>>`. Классическая ошибка — перепутать их: применить `Exclude` к объекту или `Omit` к union.

---

**Зачем нужен `InstanceType<T>`? Когда без него не обойтись?**

`InstanceType<T>` извлекает тип экземпляра из конструктора класса — это нужно всякий раз, когда класс передают как значение.

```ts
function createInstance<T extends new (...args: any[]) => any>(
  Ctor: T, ...args: ConstructorParameters<T>
): InstanceType<T> {
  return new Ctor(...args);
}
```

Без `InstanceType` возвращаемый тип свалился бы в `{}` или `object`, и информация о конкретном классе потерялась бы. Так бывает в фабриках, декораторах и DI-контейнерах. DI — это dependency injection, внедрение зависимостей, когда объекты за вас собирает контейнер.

---

**Как получить тип результата async-функции (без Promise-обёртки)?**

```ts
async function fetchUser() {
  return { id: 1, name: "Alice" };
}

type User = Awaited<ReturnType<typeof fetchUser>>;
// { id: number; name: string }
```

Один `ReturnType` даст `Promise<{ id: number; name: string }>`, а `Awaited` разворачивает его рекурсивно. Комбинация `Awaited<ReturnType<typeof fn>>` — стандартный способ назвать тип данных за async-функцией.

---

## Группа 6: Сужение типов и type guards

**Почему TypeScript не может сузить тип через пользовательскую функцию без `is`?**

Без `is` компилятор видит только то, что функция возвращает `boolean`, и в тело он не заглядывает.

```ts
// ❌ Без is — возвращаемый тип просто boolean:
function isStringPlain(v: unknown): boolean {
  return typeof v === "string";
}
const a: unknown = "hi";
if (isStringPlain(a)) a.toUpperCase(); // ❌ 'a' is of type 'unknown'

// ✅ С is — разработчик объявляет контракт:
function isString(v: unknown): v is string {
  return typeof v === "string";
}
if (isString(a)) a.toUpperCase(); // ✅ a: string
```

Разбор тела был бы дорогим и неточным, поэтому TypeScript принимает предикат на веру. Корректность тела guard-функции он не проверяет никогда.

---

**В чём разница между `asserts value is T` и `value is T`? Когда использовать каждый?**

`value is T` возвращает `boolean`, по которому вы ветвитесь; `asserts value is T` возвращает `void`, выбрасывает исключение и сужает тип во всём коде после вызова.

```ts
function isString(v: unknown): v is string {
  return typeof v === "string";
}
function assertString(v: unknown): asserts v is string {
  if (typeof v !== "string") throw new Error("not a string");
}

if (isString(x)) x.toUpperCase(); // сужено только внутри ветки

assertString(y);
y.toUpperCase(); // сужено с этого места и ниже, без if
```

Используйте `value is T`, когда нужна ветвящаяся логика. Используйте `asserts value is T`, когда значение обязано соответствовать типу, иначе выполнение продолжаться не должно: функция валидации или проверка предусловия.

---

**Что такое exhaustiveness checking и как его реализовать?**

Это паттерн, который заставляет компилятор доказать, что обработаны все варианты discriminated union.

```ts
function assertNever(value: never): never {
  throw new Error(`Unhandled case: ${JSON.stringify(value)}`);
}

switch (shape.kind) {
  case "circle": return ...;
  case "square": return ...;
  // ❌ Argument of type '{ kind: "rectangle" }' is not
  //    assignable to parameter of type 'never'
  default: return assertNever(shape);
}
```

Добавьте в union новый вариант без соответствующего `case` — и ветка `default` перестанет компилироваться. Это compile-time защита от забытых веток.

---

**Почему `typeof null === "object"` — ловушка в TypeScript? Как правильно проверить объект?**

Потому что `typeof null` в JavaScript возвращает `"object"`, и проверка сужает тип до `object | null`, а не до `object`.

```ts
function bad(v: unknown) {
  if (typeof v === "object") {
    // v: object | null — null всё ещё здесь!
  }
}

function good(v: unknown) {
  if (typeof v === "object" && v !== null) {
    // v: object ✅
  }
}
```

Это известная ошибка спецификации, которую не стали исправлять ради обратной совместимости. TypeScript её не скрывает, поэтому без второго условия `null` остаётся в типе.

---

**Почему discriminated unions лучше объекта с опциональными полями?**

Потому что опциональные поля позволяют собрать бессмысленное состояние, а discriminated union делает такие состояния невыразимыми.

```ts
// ❌ TypeScript примет { data: user, error: err } — и что это значит?
type Bad = { data?: User; error?: Error; loading?: boolean };

// ✅ Невалидные комбинации записать нельзя:
type State =
  | { status: "success"; data: User }
  | { status: "error"; error: Error }
  | { status: "loading" };
```

Создать `{ status: "success"; error: err }` не получится. TypeScript сужает тип по дискриминанту, и exhaustiveness checking после этого работает в `switch` автоматически.

---

## Группа 7: Вариантность и утверждения типов

**Почему параметры функций контравариантны? Объясните на примере.**

Потому что функция с более широким параметром безопасна там, где ожидается функция с более узким.

```ts
type CatHandler = (cat: Cat) => void;
const handler: CatHandler = (animal: Animal) => { animal.name }; // ✅
```

Вызывать `handler` мы будем только с `Cat`, а функция принимает любого `Animal` — у Cat есть всё, что есть у Animal. Обратное направление небезопасно: если обязались принять `Animal`, а обращаемся к `cat.meow()`, у Animal этого метода может не быть. Поэтому контравариантность переворачивает направление: `(Animal) => void` является подтипом `(Cat) => void`.

---

**Почему методы в TypeScript бивариантны даже со `strictFunctionTypes`?**

Потому что `strictFunctionTypes` применяет контравариантную проверку только к свойствам-функциям, но не к методам.

```ts
interface Handler<T> {
  // метод — по-прежнему бивариантен, даже с strictFunctionTypes
  handle(value: T): void;
  // свойство-функция — контравариантно, проверяется корректно
  handleFn: (value: T) => void;
}
```

Это историческое решение ради совместимости: строгая контравариантность методов сломала бы слишком много реального кода, особенно паттерны вроде `Array.prototype.forEach`. Чтобы получить корректную контравариантность, объявляйте свойство-функцию вместо метода.

---

**В чём разница между `satisfies`, явной аннотацией и `as`?**

Все три связывают значение с типом, но только `satisfies` и проверяет значение, и сохраняет выведенный тип.

| Форма | Проверяет совместимость | Итоговый тип `x` |
|---|---|---|
| `const x: Config = value` | да | `Config` — точные типы полей теряются |
| `const x = value satisfies Config` | да | выведенный — `"localhost"`, а не `string` |
| `const x = value as Config` | нет | `Config`, утверждён без проверки |

`as` пропускает проверку целиком: `{ port: 3000 } as Config` не даст ошибки, хотя `host` отсутствует. Для конфигов используйте `as const satisfies Config` — это сразу и readonly literal types, и проверка соответствия.

---

**Когда `as` допустим, а когда — признак архитектурной проблемы?**

`as` допустим там, где вы действительно знаете больше компилятора, и проблемен там, где он прикрывает недоделанную работу.

```ts
// ✅ Допустимо — TypeScript не знает тип элемента:
const c = document.querySelector("canvas") as HTMLCanvasElement;
const data = JSON.parse(raw) as Config;  // JSON.parse возвращает any
const keys = Object.keys(obj) as Array<keyof typeof obj>;

// ❌ Признак проблемы:
return {} as User;      // обход типов вместо реализации
const v = value as any; // все гарантии потеряны
const u = raw as unknown as User; // double assertion
```

Допустимые случаи — DOM API, `JSON.parse`, `Object.keys` и сторонние библиотеки с плохими типами. DOM — это document object model, объектное дерево страницы в браузере. `as` вместо type guard скрывает, что проверка на самом деле нужна. Double assertion `as unknown as T` — почти всегда архитектурная проблема.

---

## Группа 8: Файлы деклараций и модули

**Чем `.d.ts` файл отличается от `.ts` файла с только типами?**

`.d.ts` файл никогда не компилируется в JavaScript — TypeScript считает его чисто декларативным.

```txt
.d.ts   →  вывода нет вообще; описывает ambient-окружение:
           глобальные переменные, сторонние библиотеки,
           module augmentation

.ts     →  вывод есть всегда; файл с одними типами даст
           пустой .js или файл с одними импортами
```

Для `declare global`, `declare module` и ambient module declarations нужен именно контекст `.d.ts` — либо явное ключевое слово `declare` внутри `.ts`.

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

Расширять нужно `"express-serve-static-core"`, а не `"express"`: интерфейс `Request` определён именно там. Найти правильный модуль можно, прочитав `node_modules/@types/express/index.d.ts`. Без `import "express"` файл может не считаться модулем, и слияние не произойдёт.

---

**Почему `export {}` важен в `.d.ts` файле с `declare global`?**

Потому что именно `export {}` превращает файл в модуль, и только внутри модуля `declare global` вообще что-то означает.

```ts
// Без export {} — файл это скрипт, всё и так глобально,
// declare global не нужен:
declare const __DEV__: boolean;

// С export {} — файл это модуль, поэтому расширение
// глобального scope требует явного блока:
export {};
declare global {
  const __DEV__: boolean;
}
```

Без этого различия объявления ведут себя непредсказуемо. Либо всё становится глобальным, что нежелательно в модульной кодовой базе. Либо не становится ничего — TypeScript решил, что файл это модуль, а `declare global` никто не написал.

---

**В каких случаях namespace ещё оправдан в современном TypeScript?**

Три случая, и все они внутри файлов деклараций, а не в обычном коде.

```ts
// 1. Ambient declarations для глобальной библиотеки, подключённой
//    через <script> — jQuery или старый SDK (software development
//    kit, готовая клиентская библиотека от вендора):
declare namespace jQuery { function ajax(url: string): void; }

// 2. Группировка типов в .d.ts файле, без создания файловых
//    модулей:
declare namespace API { interface User { id: number } }

// 3. Слияние с enum или function, чтобы добавить статические методы:
namespace Direction { export function opposite(): void {} }
```

В обычном `.ts` коде используйте ES-модули. ES — это ECMAScript, стандарт, которым описан JavaScript.

---

## Группа 9: Продвинутые паттерны

**Что такое branded types? Как они работают без runtime overhead?**

Branded type добавляет фиктивное поле-маркер, которое делает два структурно одинаковых типа несовместимыми:

```ts
type UserId = number & { readonly __brand: "UserId" };
```

Поле `__brand` существует только в типе TypeScript, и весь intersection стирается при компиляции — в JavaScript это просто `number`. Никакого wrapper-объекта и никаких проверок в runtime. Значение создают так: `const id = 42 as UserId`, где `as` убирает структурную проверку для инициализации.

---

**Чем phantom type отличается от branded type?**

Branded type держит маркер в поле, phantom type — в неиспользуемом generic-параметре.

| | Форма | Для чего лучше |
|---|---|---|
| Branded | `T & { __brand: "UserId" }` | различать примитивы одного типа |
| Phantom | `{ name: string } & { __state: TState }` | кодировать стадию: Validated или Unvalidated |

Цель у обоих одна — добавить compile-time различие без изменений в runtime. Ни один из них ничего не стоит в runtime, потому что оба маркера стираются.

---

**Как реализовать рекурсивный тип для JSON-значений?**

```ts
type JSONPrimitive = string | number | boolean | null;
type JSONObject    = { [key: string]: JSONValue };
type JSONArray     = JSONValue[];
type JSONValue     = JSONPrimitive | JSONObject | JSONArray;
```

Рекурсия работает через косвенность: `JSONValue` ссылается на `JSONObject` и `JSONArray`, а те ссылаются обратно на `JSONValue`. Прямая рекурсия к примитиву не работает. Предел глубины — около 100 уровней, поэтому для реально больших JSON-структур нужна runtime-валидация, например через Zod.

---

**Когда type-level программирование следует заменить runtime-валидацией?**

На каждой системной границе: TypeScript проверяет типы только при компиляции, а в runtime их не проверяет никто.

```ts
// ❌ Ложная безопасность — в req.body лежит то, что пришло по сети:
const user = req.body as User;

// ✅ Валидатор проверяет само значение:
const user = UserSchema.parse(req.body);
```

Данные из `req.body`, `JSON.parse` или `localStorage` никаких гарантий от системы типов не несут. Типы бессильны и над ограничениями на значения: формат email, положительное число, непустая строка. Здесь нужны Zod, Yup или io-ts.

- Type-level — для compile-time гарантий и DX (удобство разработки).
- Runtime-валидация — для системных границ: HTTP, файлы, переменные окружения.

---

## Группа 10: Компилятор и конфигурация

**Что входит в `"strict": true`? Назовите минимум 4 флага и что каждый ловит.**

`strict` включает сразу восемь флагов:

| Флаг | Что ловит |
|---|---|
| `strictNullChecks` | `null`/`undefined` несовместимы с другими типами |
| `noImplicitAny` | неявный `any` у параметров и переменных |
| `strictFunctionTypes` | контравариантность параметров функций |
| `strictBindCallApply` | нетипизированные `.bind` / `.call` / `.apply` |
| `strictPropertyInitialization` | поля класса, не инициализированные в конструкторе |
| `noImplicitThis` | `this` с типом `any` |
| `alwaysStrict` | отсутствие `"use strict"` в сгенерированных файлах |
| `useUnknownInCatchVariables` | переменная в `catch` как `any` вместо `unknown` |

На интервью достаточно назвать первые четыре и объяснить, что ловит каждый.

---

**Чем `moduleResolution: "bundler"` отличается от `"node16"`?**

`node16` копирует то, что Node.js реально делает с ES-модулями (ESM); `bundler` исходит из того, что импорты за вас разрешает бандлер.

```ts
// С node16 — относительный импорт обязан нести расширение,
// и это расширение — ".js":
import { foo } from "./utils";    // ❌ ESM требует расширение
import { foo } from "./utils.js"; // ✅ TypeScript всё равно читает utils.ts

// С bundler — расширение опционально, файл найдёт webpack,
// vite или esbuild:
import { foo } from "./utils";    // ✅
```

Обе стратегии читают карту `exports` в `package.json`. Берите `bundler` для фронтенда, где писать `.js` в TypeScript-импорте не хочется. Берите `node16`, когда публикуете ESM-библиотеку под Node.js.

---

**Что такое `isolatedModules` и почему он запрещает `const enum`?**

Он требует, чтобы каждый файл компилировался сам по себе, без cross-file анализа — а раскрытие `const enum` требует именно его.

```ts
// файл: direction.ts
export const enum Direction { Up = 0, Down = 1 }

// файл: use.ts
import { Direction } from "./direction";
Direction.Up; // нужно подставить 0 — а для этого нужен другой файл
```

Флаг обязателен для Babel, esbuild и SWC (Speedy Web Compiler), потому что каждый из них транспилирует по одному файлу. Замените `const enum` обычным `enum` или объектом с `as const`.

---

**В чём отличие `target` от `lib` в tsconfig?**

`target` решает, какой синтаксис генерировать; `lib` решает, какие API TypeScript считает существующими.

| | Управляет | Примеры |
|---|---|---|
| `target` | синтаксическими преобразованиями | `arrow → function`, `class → prototype`, `async/await → Promise-цепочка` |
| `lib` | типами доступных API | `Array.prototype.at`, `Promise.allSettled`, `structuredClone` |

Эти две настройки независимы. Поэтому `target: "es5"` вместе с `lib: ["es2022"]` — законная комбинация: генерируем синтаксис ES5, но знаем про современные API, которые подложит полифилл. ES5 — это версия стандарта JavaScript 2009 года. Частая ошибка: добавить `lib: ["es2022"]` и ждать полифилла — `lib` добавляет только типы.

---

**Почему `noUncheckedIndexedAccess` не входит в `strict`, хотя очень полезен?**

Потому что он ломает огромное количество существующего кода, и команда TypeScript оставила его снаружи ради обратной совместимости.

```ts
// С noUncheckedIndexedAccess:
const arr: number[] = [];
const first = arr[0];  // number | undefined, а не number
first.toFixed();       // ❌ Object is possibly 'undefined'
```

Флаг добавляет `| undefined` ко всем результатам индексного доступа. Это корректнее, но проверки после него приходится расставлять повсюду. В новых проектах включайте его явно: он ловит очень частое падение на пустом массиве.

---

**Что делает `skipLibCheck: true` и какие у него риски?**

Он пропускает проверку типов внутри всех `.d.ts` файлов, включая весь `node_modules/@types/**`.

```txt
Выгода:  снимает конфликты типов между несовместимыми
         версиями @types/* и ускоряет компиляцию

Риск:    скрывает реальные несовместимости зависимостей;
         ошибка в .d.ts библиотеки, которая влияет на ваш
         код, остаётся незамеченной
```

На практике `skipLibCheck: true` стоит почти везде. Senior отличается тем, что понимает, что именно пропускается, и считает это компромиссом, а не бесплатной оптимизацией.

---

## Группа 11: Типобезопасность в архитектуре

**Как типы TypeScript помогают следовать принципу "make invalid states unrepresentable"?**

Discriminated unions кодируют состояние так, что невалидную комбинацию просто нельзя записать:

```ts
// ❌ Можно создать { loading: true, data: user, error: err }:
type State = { loading: boolean; data?: User; error?: Error };

// ✅ Невалидные состояния невыразимы:
type State =
  | { status: "loading" }
  | { status: "success"; data: User }
  | { status: "error"; error: Error };
```

Branded types превращают путаницу семантически схожих значений в ошибку компиляции, а phantom types кодируют стадии обработки: Unvalidated → Validated. Цель во всех случаях одна — перенести проверки с runtime на compile-time.

---

**Как типизировать функцию, возвращаемый тип которой зависит от входного параметра?**

Три подхода от простого к сложному: overloads, conditional return type или обычное generic-ограничение.

```ts
// 1. Overloads — дублирование, зато читаемые сообщения об ошибках:
function process(v: string): string;
function process(v: number): number;
function process(v: any): any { return v; }

// 2. Conditional return type:
declare function process2<T extends string | number>(
  v: T
): T extends string ? string : number;

// 3. Generic с ограничением extends — часто этого достаточно:
declare function process3<T extends string | number>(v: T): T;
```

Conditional types предпочтительны для библиотечного кода, overloads — когда важна читаемость сообщений об ошибках. Одна оговорка: внутри тела функции TypeScript часто не может вывести conditional return type, поэтому там нередко нужен `as`.

---

**Что такое `Readonly<T>` и почему `const` объекта не делает его readonly?**

`const` фиксирует привязку, а не содержимое, поэтому поля объекта остаются записываемыми.

```ts
const obj = { x: 1 };
obj.x = 2;      // ✅ можно — const защищает только переменную
obj = { x: 3 }; // ❌ Cannot assign to 'obj' because it is a constant

const ro: Readonly<{ x: number }> = { x: 1 };
ro.x = 2; // ❌ Cannot assign to 'x' because it is a read-only property
```

`Readonly<T>` помечает `readonly` каждое поле на уровне типов, а `as const` делает то же рекурсивно и с литеральными типами. Обратите внимание на слои: `Readonly` — ограничение времени компиляции, а `Object.freeze()` работает в runtime. Для глубокой неизменяемости нужен `DeepReadonly`.

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

Четыре преимущества: работает с `isolatedModules`, поддаётся tree-shaking, нет проблем с раскрытием `const enum`, а тип берётся из значений. Выражение `typeof Status[keyof typeof Status]` — стандартный паттерн для union из значений объекта с `as const`.

---

**Как TypeScript обрабатывает `process.env.NODE_ENV` — почему тип `string | undefined`, а не конкретный union?**

Потому что `process.env` типизирован как `NodeJS.ProcessEnv`, то есть `{ [key: string]: string | undefined }`, и TypeScript не знает, какие переменные выставлены в конкретном окружении.

```ts
declare namespace NodeJS {
  interface ProcessEnv {
    NODE_ENV: "development" | "production" | "test";
    DATABASE_URL: string;
  }
}
```

После расширения интерфейса `process.env.NODE_ENV` — это `"development" | "production" | "test"`, а `process.env.TYPO` — ошибка компиляции. Это module augmentation через declaration merging.
