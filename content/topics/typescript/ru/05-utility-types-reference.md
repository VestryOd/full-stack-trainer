<!-- verified: 2026-06-23, corrections: 0 -->
# Справочник утилитарных типов

`Partial`, `Required`, `Readonly`, `Pick`, `Omit`, `Record` разобраны в [Generics Deep Dive] — там показана их реализация с нуля. Эта статья покрывает остальное: типы для работы с функциями, множествами, Promise, а также менее известные утилиты и практику выбора правильного инструмента.

---

## Множественные операции: Exclude, Extract, NonNullable

### Exclude\<T, U\>

Убирает из union T те члены, которые совместимы с U:

```ts
type Exclude<T, U> = T extends U ? never : T;

type A = Exclude<"a" | "b" | "c", "b">;
// "a" | "c"

type B = Exclude<string | number | boolean, string | boolean>;
// number

type C = Exclude<string | null | undefined, null | undefined>;
// string — эквивалентно NonNullable<string | null | undefined>
```

**Когда использовать:** нужно взять существующий union и убрать из него конкретные варианты, не переписывая весь тип вручную.

```ts
type AllEvents = "click" | "focus" | "blur" | "keydown" | "keyup";
type KeyboardEvents = Extract<AllEvents, `key${string}`>;
// "keydown" | "keyup"

type NonKeyboardEvents = Exclude<AllEvents, KeyboardEvents>;
// "click" | "focus" | "blur"
```

### Extract\<T, U\>

Оставляет из T только те члены, которые совместимы с U — противоположность Exclude:

```ts
type Extract<T, U> = T extends U ? T : never;

type A = Extract<"a" | "b" | "c", "b" | "d">;
// "b" — только то, что есть в обоих

type B = Extract<string | number | (() => void), Function>;
// () => void — только функции
```

**Паттерн: фильтрация по структуре**

```ts
type Shape =
  | { kind: "circle"; radius: number }
  | { kind: "square"; side: number }
  | { kind: "triangle"; base: number; height: number };

// Извлечь только те Shape, у которых есть конкретный kind:
type Circle = Extract<Shape, { kind: "circle" }>;
// { kind: "circle"; radius: number }

// Это работает через структурную совместимость:
// { kind: "circle"; radius: number } extends { kind: "circle" } → true
// { kind: "square"; side: number } extends { kind: "circle" } → false
```

### NonNullable\<T\>

Убирает `null` и `undefined` из T:

```ts
type NonNullable<T> = T extends null | undefined ? never : T;

type A = NonNullable<string | null | undefined>; // string
type B = NonNullable<number | null>;             // number
type C = NonNullable<null>;                      // never
```

**Когда использовать:** когда получаете тип из внешнего источника (API, библиотека), который может быть nullable, но вы уже проверили значение:

```ts
function assertDefined<T>(value: T): NonNullable<T> {
  if (value == null) throw new Error("Expected defined value");
  return value as NonNullable<T>;
}

const config = getConfig(); // Config | null
const safeConfig = assertDefined(config); // Config ✅
```

---

## Утилиты для функций: Parameters, ReturnType, ConstructorParameters, InstanceType

### Parameters\<T\>

Извлекает параметры функции как tuple:

```ts
type Parameters<T extends (...args: any) => any> =
  T extends (...args: infer P) => any ? P : never;

type F = (a: string, b: number, c: boolean) => void;
type P = Parameters<F>; // [string, number, boolean]

// Практическое применение — обернуть функцию:
function withLogging<T extends (...args: any[]) => any>(
  fn: T,
  name: string
): (...args: Parameters<T>) => ReturnType<T> {
  return (...args) => {
    console.log(`${name} called with`, args);
    return fn(...args);
  };
}
```

**Когда использовать:** нужно переиспользовать типы параметров существующей функции без их дублирования:

```ts
// Функция из библиотеки:
declare function createUser(
  name: string,
  email: string,
  role: "admin" | "user"
): User;

// Обёртка с теми же параметрами — не дублируем типы:
function createUserWithAudit(...args: Parameters<typeof createUser>): User {
  audit("createUser", args);
  return createUser(...args);
}
```

### ReturnType\<T\>

Извлекает тип возвращаемого значения функции:

```ts
type ReturnType<T extends (...args: any) => any> =
  T extends (...args: any) => infer R ? R : never;

function fetchUser(id: number) {
  return { id, name: "Alice", email: "a@b.com" };
}

type FetchedUser = ReturnType<typeof fetchUser>;
// { id: number; name: string; email: string }
```

**Ключевой паттерн: не дублировать типы между функцией и использованием**

```ts
// ❌ Дублирование — тип User нужно поддерживать в двух местах:
type User = { id: number; name: string; email: string };
function getUser(): User { /* ... */ }

// ✅ Тип выводится из реализации функции:
function getUser() {
  return { id: 0, name: "", email: "" };
}
type User = ReturnType<typeof getUser>;
// Теперь тип и реализация всегда синхронизированы
```

**Await + ReturnType для async-функций:**

```ts
async function fetchUser(id: number) {
  const res = await fetch(`/api/users/${id}`);
  return res.json() as Promise<{ id: number; name: string }>;
}

// ReturnType вернёт Promise, Awaited его разворачивает:
type UserResponse = Awaited<ReturnType<typeof fetchUser>>;
// { id: number; name: string }
```

### ConstructorParameters\<T\>

Аналог `Parameters`, но для конструктора класса:

```ts
type ConstructorParameters<T extends abstract new (...args: any) => any> =
  T extends abstract new (...args: infer P) => any ? P : never;

class HttpClient {
  constructor(
    baseUrl: string,
    timeout: number,
    headers: Record<string, string>
  ) {}
}

type ClientArgs = ConstructorParameters<typeof HttpClient>;
// [string, number, Record<string, string>]

// Фабрика с теми же параметрами:
function createClient(...args: ConstructorParameters<typeof HttpClient>) {
  return new HttpClient(...args);
}
```

### InstanceType\<T\>

Извлекает тип экземпляра класса из конструктора:

```ts
type InstanceType<T extends abstract new (...args: any) => any> =
  T extends abstract new (...args: any) => infer R ? R : any;

class Service {
  process(data: string): number { return 0; }
}

type ServiceInstance = InstanceType<typeof Service>;
// Service — тот же тип, что вернул бы new Service()

// Где это реально нужно — работа с классом как значением:
function createInstance<T extends new (...args: any[]) => any>(
  Ctor: T,
  ...args: ConstructorParameters<T>
): InstanceType<T> {
  return new Ctor(...args);
}

const client = createInstance(HttpClient, "https://api.example.com", 5000, {});
// client: HttpClient ✅
```

**Типичный use-case — dependency injection:**

```ts
type Constructor<T = object> = new (...args: any[]) => T;

function injectable<T extends Constructor>(Base: T) {
  return class extends Base {
    static dependencies: Constructor[] = [];
  };
}

// Теперь можно работать с типом экземпляра обобщённо:
function resolve<T extends Constructor>(
  Ctor: T
): InstanceType<T> {
  return new Ctor() as InstanceType<T>;
}
```

---

## Promise-утилиты: Awaited

### Awaited\<T\>

Рекурсивно разворачивает Promise-подобные типы:

```ts
type A = Awaited<Promise<string>>;           // string
type B = Awaited<Promise<Promise<number>>>;  // number — рекурсия!
type C = Awaited<string>;                    // string — не Promise
type D = Awaited<Promise<string | number>>;  // string | number
```

**Реализация с нуля** (упрощённая версия того, что в stdlib):

```ts
type Awaited<T> =
  // null и undefined возвращаем как есть (не Promise)
  T extends null | undefined
    ? T
    // Проверяем: есть ли у T метод .then (thenable)?
    : T extends object & { then(onfulfilled: infer F, ...args: any[]): any }
      // Если есть — извлекаем тип первого аргумента колбека
      ? F extends (value: infer V, ...args: any[]) => any
        // Рекурсивно разворачиваем (на случай Promise<Promise<...>>):
        ? Awaited<V>
        : never
      // Не thenable — возвращаем T напрямую:
      : T;
```

Почему такая сложная реализация? TypeScript намеренно использует duck typing для "Promise-подобных" объектов: любой объект с методом `.then()` считается thenable. Это совместимо с нестандартными Promise-реализациями (Bluebird, библиотечные обёртки).

**Практическое применение:**

```ts
// Получить тип результата async-функции:
async function loadConfig(): Promise<{ host: string; port: number }> {
  return { host: "localhost", port: 3000 };
}

type Config = Awaited<ReturnType<typeof loadConfig>>;
// { host: string; port: number } ✅

// Работа с массивами Promise:
type SettledResults<T extends readonly Promise<unknown>[]> = {
  [K in keyof T]: Awaited<T[K]>;
};

type Results = SettledResults<[Promise<string>, Promise<number>]>;
// [string, number]
```

---

## Record\<K, V\> — глубже

`Record` построен через mapped type:

```ts
type Record<K extends keyof any, V> = { [P in K]: V };
```

`keyof any` = `string | number | symbol` — именно то, что TypeScript допускает как ключ объекта.

**Варианты использования:**

```ts
// 1. Конкретные ключи из union:
type Status = "pending" | "active" | "closed";
type StatusConfig = Record<Status, { label: string; color: string }>;

const statusConfig: StatusConfig = {
  pending: { label: "Ожидает", color: "yellow" },
  active:  { label: "Активно", color: "green" },
  closed:  { label: "Закрыто", color: "gray" },
  // TypeScript требует все три ключа и не примет лишних
};

// 2. Индексная сигнатура (динамические ключи):
type Cache<V> = Record<string, V>;
// Эквивалентно: { [key: string]: V }

// 3. Вложенный Record:
type Matrix = Record<string, Record<string, number>>;
const m: Matrix = { row1: { col1: 1, col2: 2 } };

// 4. Record vs index signature — принципиальная разница:
// Record<string, number> — все ключи присутствуют и типизированы
// { [key: string]: number } — тоже, но с разным поведением
//   при typeof/keyof операциях
```

**Когда Record — не лучший выбор:**

```ts
// ❌ Если ключи могут отсутствовать — лучше Partial<Record<...>>:
type Cache = Record<string, User>; // подразумевает, что ключ ВСЕГДА есть
const cache: Cache = {};
const user = cache["missing"]; // user: User — но на самом деле undefined!

// ✅ Правильный вариант для кэша:
type Cache = Partial<Record<string, User>>;
// или:
type Cache = Record<string, User | undefined>;
const user = cache["missing"]; // user: User | undefined — честно ✅
```

---

## Менее известные утилиты

### ThisParameterType\<T\> и OmitThisParameter\<T\>

```ts
// Извлечь тип this из функции:
function greet(this: { name: string }, greeting: string): string {
  return `${greeting}, ${this.name}`;
}

type ThisParam = ThisParameterType<typeof greet>;
// { name: string }

// Убрать this из сигнатуры:
type WithoutThis = OmitThisParameter<typeof greet>;
// (greeting: string) => string

// Применение: при передаче метода как callback нужен bind:
const alice = { name: "Alice" };
const bound = greet.bind(alice);
// bound: OmitThisParameter<typeof greet> = (greeting: string) => string
```

### ThisType\<T\>

Специальный маркерный тип для `--noImplicitThis`. Используется в object literals, где `this` должен иметь конкретный тип:

```ts
type ObjectDescriptor<D, M> = {
  data?: D;
  methods?: M & ThisType<D & M>;
  // this внутри методов будет типизирован как D & M
};

function makeObject<D, M>(desc: ObjectDescriptor<D, M>): D & M {
  const data = Object.assign({}, desc.data);
  const methods = Object.assign({}, desc.methods);
  return Object.assign(data, methods) as D & M;
}

const obj = makeObject({
  data: { x: 0, y: 0 },
  methods: {
    move(dx: number, dy: number) {
      this.x += dx; // this: { x: number; y: number } & { move(...): void } ✅
      this.y += dy;
    },
  },
});
```

---

## Строковые утилиты (краткий обзор)

Рассмотрены подробно в [Template Literal Types]:

```ts
type U = Uppercase<"hello">;     // "HELLO"
type L = Lowercase<"WORLD">;     // "world"
type C = Capitalize<"hello">;    // "Hello"
type UC = Uncapitalize<"Hello">; // "hello"

// Работают только со строковыми литералами и string, не с number/boolean:
type N = Uppercase<42>; // ❌ Type '42' does not satisfy the constraint 'string'
```

---

## Руководство по выбору: когда что использовать

```txt
Задача                                  Утилита
─────────────────────────────────────────────────────────────────
Сделать все поля опциональными          Partial<T>
Сделать все поля обязательными          Required<T>
Сделать все поля readonly               Readonly<T>
Выбрать подмножество полей              Pick<T, Keys>
Исключить подмножество полей            Omit<T, Keys>
Создать объект с фиксированными ключами Record<Keys, V>
─────────────────────────────────────────────────────────────────
Убрать типы из union                    Exclude<T, U>
Оставить только совпадающие типы        Extract<T, U>
Убрать null и undefined                 NonNullable<T>
─────────────────────────────────────────────────────────────────
Параметры функции                       Parameters<T>
Возвращаемый тип функции                ReturnType<T>
Параметры конструктора                  ConstructorParameters<T>
Тип экземпляра класса                   InstanceType<T>
─────────────────────────────────────────────────────────────────
Развернуть Promise                      Awaited<T>
─────────────────────────────────────────────────────────────────
Регистр строковых литералов             Uppercase / Lowercase /
                                        Capitalize / Uncapitalize
```

### Частые комбинации

```ts
// Тип результата async-функции:
type Result = Awaited<ReturnType<typeof asyncFn>>;

// Первый параметр функции:
type FirstArg = Parameters<typeof fn>[0];

// Сделать часть полей опциональной (частичное обновление):
type PatchUser = Partial<Pick<User, "name" | "email">>;

// Все поля кроме одного — readonly:
type SafeConfig = Readonly<Omit<Config, "debug">>;

// Только обязательные поля объекта:
type RequiredOnly<T> = Required<Pick<T, RequiredKeys<T>>>;
// (где RequiredKeys — из статьи [Conditional and Mapped Types])

// Тип значений Record:
type StatusConfig = Record<Status, { label: string }>;
type StatusLabel = StatusConfig[Status]; // { label: string }
```

---

## Типичные ошибки на интервью

- **Путать `Exclude` и `Omit`** — `Exclude` работает с union members (убирает типы из union). `Omit` работает с ключами объекта (убирает поля). `Exclude<"a" | "b", "a">` = `"b"`. `Omit<User, "email">` = объект без поля email.

- **Не знать, что `Omit` реализован через `Exclude`** — `Omit<T, K> = Pick<T, Exclude<keyof T, K>>`. Понимание этого важно, когда нужен похожий паттерн.

- **Использовать `ReturnType` для async-функции и забыть `Awaited`** — `ReturnType<typeof asyncFn>` вернёт `Promise<X>`, не `X`. Нужно `Awaited<ReturnType<typeof asyncFn>>`.

- **Не знать `ConstructorParameters` и `InstanceType`** — оба нужны при работе с классами как значениями (фабрики, DI-контейнеры, декораторы). На senior-уровне это обязательное знание.

- **Считать `Record<string, T>` и `{ [key: string]: T }` полностью идентичными** — в большинстве контекстов они эквивалентны, но `Record` — это mapped type, что иногда даёт разные результаты при `keyof` и в conditional types.

- **Не знать реализацию `Awaited`** — спрашивают "как TypeScript понимает, что тип является Promise?" Ответ: через duck typing — наличие метода `.then`. `Awaited` не проверяет `instanceof Promise`, он проверяет форму объекта.

- **Путать `Parameters<T>[0]` и `FirstParameter<T>`** — `FirstParameter` не существует в stdlib. Стандартный паттерн — indexed access к tuple: `Parameters<T>[0]`. Это показывает понимание того, что `Parameters` возвращает tuple, а не массив.
