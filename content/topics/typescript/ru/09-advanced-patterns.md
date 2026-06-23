<!-- verified: 2026-06-23, corrections: 0 -->
# Продвинутые паттерны TypeScript

## Branded Types — симуляция номинальной типизации

TypeScript структурно типизирован: `type UserId = number` и `type OrderId = number` — один и тот же тип. Функция, принимающая `UserId`, без жалоб примет `OrderId`. Это порождает целый класс ошибок, которые легко написать и тяжело найти.

```ts
type UserId = number;
type OrderId = number;

function getUser(id: UserId): User { /* ... */ }
function getOrder(id: OrderId): Order { /* ... */ }

const orderId: OrderId = 42;
getUser(orderId); // ✅ TypeScript не видит проблемы — но логически это баг!
```

Branded type (брендированный тип) — добавление фиктивного поля-маркера, которого не существует в runtime, но которое делает типы несовместимыми для TypeScript:

```ts
type Brand<T, TBrand extends string> = T & { readonly __brand: TBrand };

type UserId  = Brand<number, "UserId">;
type OrderId = Brand<number, "OrderId">;

// Создание значений — через функцию-конструктор:
function UserId(id: number): UserId {
  return id as UserId;
}

function OrderId(id: number): OrderId {
  return id as OrderId;
}

function getUser(id: UserId): User { /* ... */ }
function getOrder(id: OrderId): Order { /* ... */ }

const userId  = UserId(1);
const orderId = OrderId(42);

getUser(userId);   // ✅
getUser(orderId);  // ❌ Argument of type 'OrderId' is not assignable to 'UserId'
getOrder(userId);  // ❌ Argument of type 'UserId' is not assignable to 'OrderId'
```

Поле `__brand` существует только в типе — в runtime объект является обычным `number`. Никакого overhead.

### Когда branded types оправданы

```ts
// Денежные значения — не перепутать доллары и центы:
type Dollars = Brand<number, "Dollars">;
type Cents   = Brand<number, "Cents">;

function toCents(d: Dollars): Cents {
  return (d * 100) as Cents;
}

// Строки с разной семантикой:
type Email      = Brand<string, "Email">;
type HashedPass = Brand<string, "HashedPass">;
type JwtToken   = Brand<string, "JwtToken">;

function sendEmail(to: Email, body: string): void { /* ... */ }
function hashPassword(plain: string): HashedPass { /* ... */ }
function verifyToken(token: JwtToken): UserId { /* ... */ }

// Нельзя отправить необработанную строку как Email:
sendEmail("alice@example.com", "Hello"); // ❌ строка не Email
sendEmail("alice@example.com" as Email, "Hello"); // ✅ явное приведение

// Или — с валидацией:
function parseEmail(raw: string): Email {
  if (!raw.includes("@")) throw new Error("Invalid email");
  return raw as Email;
}

const email = parseEmail("alice@example.com"); // Email ✅
sendEmail(email, "Hello"); // ✅
```

### Несколько брендов

```ts
// Комбинирование брендов:
type NonEmptyString = Brand<string, "NonEmpty">;
type TrimmedString  = Brand<string, "Trimmed">;
type SafeUserInput  = Brand<string, "NonEmpty"> & Brand<string, "Trimmed">;

function sanitize(input: string): SafeUserInput {
  const trimmed = input.trim();
  if (!trimmed) throw new Error("Input cannot be empty");
  return trimmed as SafeUserInput;
}

// SafeUserInput совместим с NonEmptyString и TrimmedString по отдельности:
function requireNonEmpty(s: NonEmptyString): void { /* ... */ }
const safe = sanitize("  hello  ");
requireNonEmpty(safe); // ✅ SafeUserInput extends NonEmptyString
```

---

## Phantom Types — компайл-тайм валидация через параметр типа

Phantom type — generic-параметр, который **не используется в структуре типа**, но изменяет его совместимость. Позволяет кодировать состояние объекта в системе типов.

```ts
// T — phantom параметр: существует только в типе, не в runtime:
type Tagged<T, TTag> = T; // TTag не используется в значении

// Или через класс-обёртку:
class TypedValue<T, TTag> {
  private readonly __tag!: TTag; // readonly, никогда не присваивается
  constructor(public readonly value: T) {}
}

// Кодирование состояния валидации:
type Unvalidated = "Unvalidated";
type Validated   = "Validated";

type FormData<TState> = {
  name: string;
  email: string;
  age: number;
} & { readonly __state: TState }; // phantom поле

function createForm(data: { name: string; email: string; age: number }): FormData<Unvalidated> {
  return data as FormData<Unvalidated>;
}

function validate(form: FormData<Unvalidated>): FormData<Validated> {
  if (!form.name) throw new Error("Name required");
  if (!form.email.includes("@")) throw new Error("Invalid email");
  if (form.age < 0) throw new Error("Invalid age");
  return form as FormData<Validated>;
}

// Только валидированные данные принимаются:
function submitForm(form: FormData<Validated>): void {
  // отправка на сервер
}

const raw = createForm({ name: "Alice", email: "a@b.com", age: 30 });
submitForm(raw);                    // ❌ FormData<Unvalidated> не совместим
const validated = validate(raw);
submitForm(validated);              // ✅
```

### Phantom types для единиц измерения

```ts
type Meters    = { readonly __unit: "m" };
type Feet      = { readonly __unit: "ft" };
type Kilograms = { readonly __unit: "kg" };

type Measurement<TUnit> = number & { readonly __unit: TUnit };

function meters(n: number): Measurement<Meters> {
  return n as Measurement<Meters>;
}
function feet(n: number): Measurement<Feet> {
  return n as Measurement<Feet>;
}

function metersToFeet(m: Measurement<Meters>): Measurement<Feet> {
  return (m * 3.281) as Measurement<Feet>;
}

const height = meters(1.8);
metersToFeet(height);       // ✅
metersToFeet(feet(5.9));    // ❌ нельзя перевести футы в футы
metersToFeet(1.8);          // ❌ обычное число не принимается
```

---

## Builder Pattern с типизированным chaining

Паттерн Builder с типами позволяет на уровне компиляции гарантировать, что обязательные поля установлены перед вызовом `build()`.

### Базовый builder

```ts
class QueryBuilder<
  TTable extends string,
  TSelected extends string = never,
  TFiltered extends boolean = false
> {
  private _table: TTable;
  private _fields: TSelected[] = [];
  private _where: string | null = null;

  constructor(table: TTable) {
    this._table = table;
  }

  select<TFields extends string>(
    ...fields: TFields[]
  ): QueryBuilder<TTable, TSelected | TFields, TFiltered> {
    this._fields = [...this._fields, ...fields] as any;
    return this as any;
  }

  where(condition: string): QueryBuilder<TTable, TSelected, true> {
    this._where = condition;
    return this as any;
  }

  // build доступен только если есть хотя бы одно поле:
  build(this: QueryBuilder<TTable, string, TFiltered>): string {
    const fields = this._fields.join(", ");
    const where = this._where ? ` WHERE ${this._where}` : "";
    return `SELECT ${fields} FROM ${this._table}${where}`;
  }
}

const query = new QueryBuilder("users")
  .select("id", "name", "email")
  .where("age > 18")
  .build(); // ✅

// Без select — build недоступен:
const bad = new QueryBuilder("users").build();
// ❌ Argument 'this' is not assignable — TSelected is never
```

### Builder с исключением уже установленных полей

```ts
type RequiredFields = "name" | "email" | "role";

class UserBuilder<TSet extends RequiredFields = never> {
  private data: Partial<Record<RequiredFields, string>> = {};

  setName(name: string): UserBuilder<TSet | "name"> {
    this.data.name = name;
    return this as any;
  }

  setEmail(email: string): UserBuilder<TSet | "email"> {
    this.data.email = email;
    return this as any;
  }

  setRole(role: string): UserBuilder<TSet | "role"> {
    this.data.role = role;
    return this as any;
  }

  // build доступен только когда все поля установлены:
  build(
    this: UserBuilder<RequiredFields>
  ): Record<RequiredFields, string> {
    return this.data as Record<RequiredFields, string>;
  }
}

const user = new UserBuilder()
  .setName("Alice")
  .setEmail("alice@example.com")
  .setRole("admin")
  .build(); // ✅

// Пропустили setRole:
const incomplete = new UserBuilder()
  .setName("Bob")
  .setEmail("bob@example.com")
  .build(); // ❌ TSet = "name" | "email", не "name" | "email" | "role"
```

---

## Рекурсивные типы

TypeScript поддерживает рекурсивные типы — типы, которые ссылаются на самих себя. Основное ограничение: рекурсия должна быть через уровень косвенности (через тип, а не напрямую к примитиву).

### Типизация JSON

```ts
type JSONPrimitive = string | number | boolean | null;
type JSONObject    = { [key: string]: JSONValue };
type JSONArray     = JSONValue[];
type JSONValue     = JSONPrimitive | JSONObject | JSONArray;

// Теперь можно типизировать произвольный JSON:
const data: JSONValue = {
  user: {
    id: 1,
    name: "Alice",
    tags: ["admin", "user"],
    meta: null,
  },
}; // ✅
```

### Deep Readonly (рекурсивный)

```ts
type DeepReadonly<T> =
  T extends (infer U)[]
    ? ReadonlyArray<DeepReadonly<U>>
    : T extends object
    ? { readonly [K in keyof T]: DeepReadonly<T[K]> }
    : T;

type State = {
  user: { id: number; settings: { theme: string; lang: string } };
  cart: { items: { id: number; qty: number }[] };
};

type FrozenState = DeepReadonly<State>;
// {
//   readonly user: {
//     readonly id: number;
//     readonly settings: { readonly theme: string; readonly lang: string }
//   };
//   readonly cart: {
//     readonly items: ReadonlyArray<{ readonly id: number; readonly qty: number }>
//   };
// }
```

### Рекурсивный тип для дерева

```ts
type TreeNode<T> = {
  value: T;
  children: TreeNode<T>[];
};

function mapTree<T, U>(
  node: TreeNode<T>,
  fn: (value: T) => U
): TreeNode<U> {
  return {
    value: fn(node.value),
    children: node.children.map(child => mapTree(child, fn)),
  };
}

const numTree: TreeNode<number> = {
  value: 1,
  children: [
    { value: 2, children: [] },
    { value: 3, children: [{ value: 4, children: [] }] },
  ],
};

const strTree = mapTree(numTree, n => n.toString());
// strTree: TreeNode<string> ✅
```

### Рекурсивный Split/Join типа

```ts
type Split<S extends string, Sep extends string> =
  S extends `${infer Head}${Sep}${infer Tail}`
    ? [Head, ...Split<Tail, Sep>]
    : [S];

type Parts = Split<"a.b.c.d", ".">;
// ["a", "b", "c", "d"] ✅

type Join<Parts extends string[], Sep extends string> =
  Parts extends [infer Head extends string, ...infer Tail extends string[]]
    ? Tail extends []
      ? Head
      : `${Head}${Sep}${Join<Tail, Sep>}`
    : never;

type Rejoined = Join<["a", "b", "c"], "/">;
// "a/b/c" ✅
```

---

## Type-Level Programming: когда остановиться

TypeScript позволяет делать удивительные вещи на уровне типов. Но есть жёсткие ограничения и практические соображения:

### Технические ограничения

```txt
1. Глубина рекурсии: ~100 уровней
   type Infinite<T> = { value: Infinite<T> }; — зависнет компилятор

2. Размер union: компилятор имеет лимит (~100k членов)
   Большие template literal cross-products → "too complex to represent"

3. Время компиляции: сложные типы замедляют TypeScript Language Server
   IDE начинает "тормозить" при наведении, автодополнение запаздывает

4. Читаемость: никто не понимает
   type X = { [K in keyof T as K extends string
     ? T[K] extends object ? K : never : never]: ... }
   — даже автор через неделю забудет, что это делает
```

### Граница: когда использовать runtime-валидацию (Zod и подобные)

```ts
// ❌ Попытка сделать всё через типы — хрупко и сложно:
type Positive<T extends number> = T extends infer N
  ? N extends 0 ? never
  : `${N}` extends `-${string}` ? never
  : T
  : never;
// Это не работает для runtime-значений — только для литералов!

// ✅ Runtime-валидация через Zod — проверяет И типы, И значения:
import { z } from "zod";

const UserSchema = z.object({
  id: z.number().positive(),
  name: z.string().min(1).max(100),
  email: z.string().email(),
  age: z.number().min(0).max(150),
  role: z.enum(["admin", "user", "moderator"]),
});

type User = z.infer<typeof UserSchema>;
// { id: number; name: string; email: string; age: number; role: "admin" | "user" | "moderator" }

// Использование:
function createUser(data: unknown): User {
  return UserSchema.parse(data); // ✅ и типы, и runtime-валидация
}
```

Zod решает проблему, которую TypeScript не может: **runtime-данные** (HTTP-запросы, файлы, localStorage) не имеют типов. `JSON.parse()` возвращает `any`. Только runtime-валидация может гарантировать, что пришедшие данные соответствуют ожидаемой структуре.

### Прагматичное правило

```txt
Используй type-level программирование когда:
  - Типы выводятся из кода (ReturnType, Parameters, infer)
  - Нужна compile-time гарантия (branded types, exhaustiveness)
  - Библиотечный код для разработчиков (утилитарные типы)
  - Улучшение DX: автодополнение, точные ошибки

Переключайся на runtime-валидацию когда:
  - Данные приходят извне (HTTP, файлы, env, localStorage)
  - Нужна проверка значений, а не только структуры
    (email формат, число > 0, строка не пустая)
  - Тип слишком сложный для поддержки
  - "Умный" тип работает только с литералами, а не с runtime-данными
```

---

## Дополнительные продвинутые паттерны

### Opaque Type через class trick

Альтернатива branded types без `& { __brand }` — приватный класс:

```ts
class UserId {
  private constructor(public readonly value: number) {}

  static create(n: number): UserId {
    if (n <= 0) throw new Error("UserId must be positive");
    return new UserId(n);
  }
}

function getUser(id: UserId): User { /* ... */ }

getUser(new UserId(1));            // ❌ constructor is private
getUser(UserId.create(1));         // ✅
getUser(42 as unknown as UserId);  // только через двойное приведение
```

Недостаток: накладные расходы на класс в runtime. Преимущество: конструктор может валидировать значение.

### Higher-Kinded Types симуляция

TypeScript не поддерживает HKT нативно (нет `type F<T>` как аргумента), но можно симулировать через interface merging:

```ts
// Интерфейс для HKT-реестра:
interface HKT {
  Array: unknown;
  Promise: unknown;
  Maybe: unknown;
}

type Apply<F extends keyof HKT, A> = (HKT & { Array: A[]; Promise: Promise<A>; Maybe: A | null })[F];

// Обобщённая функция над любым контейнером:
type Functor<F extends keyof HKT> = {
  map<A, B>(fa: Apply<F, A>, f: (a: A) => B): Apply<F, B>;
};

// Этот паттерн используется в fp-ts
```

### Currying с типами

```ts
type Curry<Params extends unknown[], Return> =
  Params extends [infer First, ...infer Rest]
    ? (arg: First) => Curry<Rest, Return>
    : Return;

function curry<Params extends unknown[], Return>(
  fn: (...args: Params) => Return
): Curry<Params, Return> {
  // реализация...
  return ((...args: unknown[]) => {
    if (args.length >= fn.length) return (fn as any)(...args);
    return (...more: unknown[]) => (fn as any)(...args, ...more);
  }) as any;
}

const add = curry((a: number, b: number, c: number) => a + b + c);
// add: (arg: number) => (arg: number) => (arg: number) => number

const add5 = add(5);       // (arg: number) => (arg: number) => number
const add5and3 = add5(3);  // (arg: number) => number
add5and3(2);               // 10 ✅
```

---

## Типичные ошибки на интервью

- **"Branded types имеют runtime overhead"** — нет. `__brand` поле существует только в типе TypeScript. Скомпилированный JavaScript — обычное `number` или `string`, никакого wrapper-объекта.

- **"Phantom types нельзя реализовать без runtime-поля"** — можно. Поле `__tag!: TTag` с `!` (definite assignment assertion) никогда не инициализируется — оно `undefined` в runtime. TypeScript использует его только для проверки совместимости.

- **"Рекурсивные типы можно углублять сколько угодно"** — нет, есть ограничение ~100 уровней. TypeScript выдаёт "Type instantiation is excessively deep". Это реальное ограничение, которое нужно знать при проектировании DeepReadonly, DeepPartial и т.п.

- **Не знать, когда остановиться и использовать Zod** — типы TypeScript стираются в runtime. Если данные приходят снаружи (`req.body`, `JSON.parse`), TypeScript ничего не проверяет. Строчка `const data = req.body as User` — это ложная безопасность. Нужна runtime-валидация.

- **"Builder pattern с дженериками — это overengineering"** — зависит от контекста. Для публичной библиотеки или внутреннего DSL с большим количеством обязательных шагов — оправдано. Для обычного CRUD — чрезмерно. Умение аргументировать выбор важнее самого паттерна.

- **Не понимать, что `& { readonly __brand: T }` делает типы несовместимыми** — именно дополнительное поле с уникальным literal-типом является "печатью". Два разных бренда имеют разные literal-типы в поле `__brand`, поэтому структурно несовместимы.
