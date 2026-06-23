<!-- verified: 2026-06-23, corrections: 0 -->
# Условные и отображённые типы

## Условные типы (Conditional Types)

Условный тип — это выражение уровня типов, которое работает как тернарный оператор:

```ts
T extends U ? X : Y
```

Читается: "Если T совместим с U — результат X, иначе — Y". `extends` здесь проверяет совместимость (subtype check), не наследование.

```ts
type IsString<T> = T extends string ? true : false;

type A = IsString<string>;  // true
type B = IsString<number>;  // false
type C = IsString<"hello">; // true — "hello" совместим со string
```

### Зачем это нужно: проблема, которую решают conditional types

Без условных типов невозможно выразить "возвращаемый тип зависит от входного":

```ts
// ❌ Без conditional types — приходится использовать overloads:
function unwrap(value: string): string;
function unwrap(value: number): number;
function unwrap(value: string | number): string | number { return value; }

// ✅ С conditional types — один тип выражает всё:
type Unwrap<T> = T extends Promise<infer U> ? U : T;

type A = Unwrap<Promise<string>>; // string
type B = Unwrap<number>;          // number — не Promise, возвращаем как есть
```

### Цепочки условных типов

Как вложенные тернарные операторы:

```ts
type TypeName<T> =
  T extends string  ? "string"  :
  T extends number  ? "number"  :
  T extends boolean ? "boolean" :
  T extends null    ? "null"    :
  T extends undefined ? "undefined" :
  "object";

type A = TypeName<string>;    // "string"
type B = TypeName<42>;        // "number"
type C = TypeName<boolean>;   // "boolean"
type D = TypeName<() => void>;// "object"
```

---

## Ключевое слово `infer`

`infer` — самая мощная часть условных типов. Оно позволяет **извлекать** тип из более сложной структуры внутри ветки `extends`.

Базовый принцип: `infer R` создаёт переменную типа R, которую TypeScript заполняет при сопоставлении.

```ts
// Без infer — нужно знать тип заранее:
type GetPromiseValue<T> = T extends Promise<string> ? string : never;
// Работает только для Promise<string>, не универсально

// С infer — TypeScript выводит тип сам:
type GetPromiseValue<T> = T extends Promise<infer R> ? R : never;

type A = GetPromiseValue<Promise<string>>;        // string
type B = GetPromiseValue<Promise<number[]>>;      // number[]
type C = GetPromiseValue<Promise<{ id: number }>>; // { id: number }
type D = GetPromiseValue<string>;                 // never — не Promise
```

### `infer` для функций

```ts
// Извлечь тип параметров функции:
type Parameters<T extends (...args: any) => any> =
  T extends (...args: infer P) => any ? P : never;

type F = (a: string, b: number) => boolean;
type P = Parameters<F>; // [string, number] — tuple!

// Извлечь возвращаемый тип функции:
type ReturnType<T extends (...args: any) => any> =
  T extends (...args: any) => infer R ? R : never;

type R = ReturnType<F>; // boolean
```

### `infer` в нескольких позициях одновременно

```ts
// Первый и последний элемент tuple:
type Head<T extends any[]> = T extends [infer H, ...any[]] ? H : never;
type Tail<T extends any[]> = T extends [...any[], infer L] ? L : never;

type H = Head<[string, number, boolean]>; // string
type L = Tail<[string, number, boolean]>; // boolean

// Параметр и результат функции одновременно:
type FunctionParts<T> = T extends (arg: infer A) => infer R
  ? { input: A; output: R }
  : never;

type Parts = FunctionParts<(x: string) => number>;
// { input: string; output: number }
```

### `infer` для вложенных структур

```ts
// Тип элемента массива:
type ElementOf<T> = T extends (infer E)[] ? E : never;

type E1 = ElementOf<string[]>;        // string
type E2 = ElementOf<[number, string]>; // number | string — union из tuple

// Значение объекта по ключу (альтернатива indexed access):
type ValueOf<T, K extends keyof T> = T extends Record<K, infer V> ? V : never;

type User = { id: number; name: string };
type IdType = ValueOf<User, "id">; // number
```

---

## Дистрибутивные условные типы

Это самое неочевидное поведение conditional types — источник большинства сюрпризов.

**Правило:** Когда условный тип применяется к **голому** (bare) параметру типа `T`, он автоматически распределяется по членам union:

```ts
type IsString<T> = T extends string ? true : false;

// С union type — TypeScript применяет условие к КАЖДОМУ члену:
type Result = IsString<string | number | boolean>;
// Эквивалентно:
// IsString<string> | IsString<number> | IsString<boolean>
// = true | false | false
// = boolean
```

Это "дистрибутивность" — как дистрибутивность умножения в математике:
`2 × (3 + 4) = 2×3 + 2×4`
`Conditional<A | B> = Conditional<A> | Conditional<B>`

### Практическое применение: Exclude и Extract

```ts
// Exclude<T, U> — убрать из T те члены, которые совместимы с U:
type Exclude<T, U> = T extends U ? never : T;

type A = Exclude<string | number | boolean, number>;
// string extends number ? never : string → string
// number extends number ? never : number → never
// boolean extends number ? never : boolean → boolean
// = string | never | boolean = string | boolean ✅

// Extract<T, U> — оставить только те члены T, которые совместимы с U:
type Extract<T, U> = T extends U ? T : never;

type B = Extract<string | number | boolean, string | boolean>;
// string extends string | boolean ? string : never → string
// number extends string | boolean ? number : never → never
// boolean extends string | boolean ? boolean : never → boolean
// = string | boolean ✅
```

### Как отключить дистрибутивность

Иногда нужно, чтобы TypeScript обрабатывал union как единый тип, без распределения. Трюк — обернуть в tuple:

```ts
// Дистрибутивный (распределяет по union):
type IsNever<T> = T extends never ? true : false;
type A = IsNever<never>; // boolean (не true!) — потому что never — пустой union

// Недистрибутивный (оборачиваем в tuple):
type IsNever<T> = [T] extends [never] ? true : false;
type B = IsNever<never>;  // true ✅
type C = IsNever<string>; // false ✅
```

Почему `T extends never` даёт `boolean` вместо `true`? Потому что `never` — это пустой union. Дистрибутивный тип по пустому union = пустой union = `never`. А `never` виден как `boolean` в большинстве контекстов... точнее, TypeScript просто не может вычислить результат для пустого union — он возвращает `never`. Это контринтуитивно, поэтому `[T] extends [never]` — стандартный паттерн для проверки на `never`.

```ts
// Ещё пример: union обрабатывается целиком:
type IsUnion<T> = [T] extends [T]
  ? T extends any ? ([T] extends [T] ? false : true) : never
  : never;
// Это уже продвинутый паттерн — важно знать, что оборачивание отключает дистрибутивность
```

---

## Отображённые типы (Mapped Types)

Mapped types позволяют создавать новый тип, преобразуя каждый ключ существующего:

```ts
// Синтаксис:
type MappedType<T> = {
  [K in keyof T]: /* новый тип для значения */
};
```

`K in keyof T` — итерация по ключам T. Читается как "для каждого ключа K из T".

### Модификаторы: `readonly` и `?`

```ts
// Добавить readonly:
type Freeze<T> = { readonly [K in keyof T]: T[K] };

// Убрать readonly:
type Mutable<T> = { -readonly [K in keyof T]: T[K] };

// Добавить опциональность:
type Partial<T> = { [K in keyof T]?: T[K] };

// Убрать опциональность:
type Required<T> = { [K in keyof T]-?: T[K] };

// Комбинирование:
type ReadonlyPartial<T> = { readonly [K in keyof T]?: T[K] };
```

`-readonly` и `-?` — операторы *удаления* модификаторов. TypeScript позволяет явно добавлять (`+?`, `+readonly`, можно без `+`) и удалять (`-?`, `-readonly`).

### Преобразование типов значений

```ts
// Сделать все значения nullable:
type Nullable<T> = { [K in keyof T]: T[K] | null };

// Обернуть каждое поле в Promise:
type Promisify<T> = { [K in keyof T]: Promise<T[K]> };

// Сделать все значения функциями-геттерами:
type Getterize<T> = { [K in keyof T]: () => T[K] };

type User = { id: number; name: string };
type GetterUser = Getterize<User>;
// { id: () => number; name: () => string }
```

---

## Remapping ключей с `as`

TypeScript 4.1+ позволяет переименовывать ключи в mapped types через `as`:

```ts
// Синтаксис:
type RemappedType<T> = {
  [K in keyof T as /* новое имя ключа */]: T[K];
};
```

### Фильтрация ключей через `as ... never`

Если переименование возвращает `never`, ключ исключается:

```ts
// Оставить только string-ключи:
type StringKeysOnly<T> = {
  [K in keyof T as K extends string ? K : never]: T[K];
};

type Mixed = { [key: string]: string } & { [key: number]: number };
// В реальности keyof объекта может включать number и symbol

// Оставить только поля определённого типа:
type PickByValue<T, V> = {
  [K in keyof T as T[K] extends V ? K : never]: T[K];
};

type User = { id: number; name: string; age: number; email: string };
type StringFields = PickByValue<User, string>;
// { name: string; email: string } — только string-поля ✅
```

### Переименование ключей

```ts
// Добавить префикс к каждому ключу:
type Prefixed<T, P extends string> = {
  [K in keyof T as K extends string ? `${P}${Capitalize<K>}` : never]: T[K];
};

type User = { id: number; name: string };
type PrefixedUser = Prefixed<User, "user">;
// { userId: number; userName: string } ✅

// Геттеры и сеттеры:
type Getters<T> = {
  [K in keyof T as K extends string ? `get${Capitalize<K>}` : never]: () => T[K];
};

type UserGetters = Getters<User>;
// { getId: () => number; getName: () => string }
```

---

## Реализация utility types с нуля через mapped + conditional

Демонстрация комбинированного использования:

### NonNullable\<T\>

```ts
// Убрать null и undefined из T:
type NonNullable<T> = T extends null | undefined ? never : T;

type A = NonNullable<string | null | undefined>; // string
type B = NonNullable<number | null>;             // number
```

Работает через дистрибутивность: каждый член union проверяется отдельно.

### DeepPartial\<T\> — рекурсивный Partial

```ts
type DeepPartial<T> = T extends object
  ? { [K in keyof T]?: DeepPartial<T[K]> }
  : T;

type Config = {
  server: { host: string; port: number };
  db: { url: string; name: string };
};

type PartialConfig = DeepPartial<Config>;
// {
//   server?: { host?: string; port?: number };
//   db?: { url?: string; name?: string };
// }
```

### DeepReadonly\<T\>

```ts
type DeepReadonly<T> = T extends (infer U)[]
  ? ReadonlyArray<DeepReadonly<U>>
  : T extends object
  ? { readonly [K in keyof T]: DeepReadonly<T[K]> }
  : T;
```

### Flatten\<T\> — извлечь тип элемента из массива рекурсивно

```ts
type Flatten<T> = T extends (infer U)[] ? Flatten<U> : T;

type A = Flatten<number[][][]>; // number
type B = Flatten<string[]>;     // string
type C = Flatten<number>;       // number — не массив
```

### UnionToIntersection\<T\> — продвинутый паттерн

Преобразование union в intersection — трюк, основанный на контравариантности функций:

```ts
type UnionToIntersection<U> =
  (U extends any ? (x: U) => void : never) extends (x: infer I) => void
    ? I
    : never;

type A = UnionToIntersection<{ a: string } | { b: number }>;
// { a: string } & { b: number }
```

Почему это работает: когда TypeScript видит `(x: U) => void` с дистрибутивным U, он создаёт union функций. Чтобы присвоить union функций одной функции, параметр должен удовлетворять ВСЕМ вариантам — то есть быть intersection.

---

## Комбинирование mapped + conditional + infer

На практике все три механизма используются вместе:

```ts
// Тип объекта, где каждое значение "разворачивает" Promise:
type AwaitedValues<T> = {
  [K in keyof T]: T[K] extends Promise<infer U> ? U : T[K];
};

type AsyncUser = {
  id: Promise<number>;
  name: Promise<string>;
  role: string; // не Promise — оставить как есть
};

type SyncUser = AwaitedValues<AsyncUser>;
// { id: number; name: string; role: string } ✅

// Разделить объект на обязательные и опциональные:
type RequiredKeys<T> = {
  [K in keyof T]-?: {} extends Pick<T, K> ? never : K;
}[keyof T];

type OptionalKeys<T> = {
  [K in keyof T]-?: {} extends Pick<T, K> ? K : never;
}[keyof T];

type Config = { host: string; port?: number; debug?: boolean };
type RK = RequiredKeys<Config>; // "host"
type OK = OptionalKeys<Config>; // "port" | "debug"
```

---

## Типичные ошибки на интервью

- **Не знать про дистрибутивность** — "почему `type T = IsString<string | number>` = `boolean`?" Ответ: дистрибутивность применяет conditional к каждому члену union. Это неочевидно и часто ловит врасплох.

- **Не понимать, почему `T extends never` не работает как ожидается** — `never` — пустой union, дистрибутивный тип по пустому union = `never`. Стандартный паттерн для проверки: `[T] extends [never]`.

- **Путать `infer` с generic-параметром** — `infer R` можно использовать ТОЛЬКО внутри условного типа в ветке `extends`. Это не объявление нового параметра — это извлечение типа при сопоставлении.

- **Не знать `as` remapping в mapped types** — до TypeScript 4.1 фильтрация ключей делалась через Omit внутри, что менее элегантно. `[K in keyof T as K extends string ? K : never]` — стандартный паттерн для фильтрации.

- **Считать, что `keyof T` возвращает массив** — нет, `keyof T` возвращает union: `keyof { a: 1; b: 2 }` = `"a" | "b"`. В mapped type `K in keyof T` итерирует по этому union.

- **Не реализовывать utility types с нуля** — умение "использовать `Partial<T>`" не демонстрирует понимания. Умение написать `{ [K in keyof T]?: T[K] }` и объяснить каждую часть — демонстрирует.

- **Написать `as const` вместо `as const satisfies`** — это разные инструменты с разными гарантиями (см. [Variance and Assertions]).
