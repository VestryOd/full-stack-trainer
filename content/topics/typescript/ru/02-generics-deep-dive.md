<!-- verified: 2026-06-23, corrections: 0 -->
# Дженерики — глубокое погружение

## Зачем нужны дженерики: проблема, которую они решают

Без дженериков приходится выбирать между потерей типобезопасности и дублированием кода:

```ts
// Вариант 1: any — теряем всю типизацию
function identity(value: any): any {
  return value;
}
const result = identity("hello"); // result: any — IDE не подскажет методы

// Вариант 2: перегрузки — дублирование, не масштабируется
function identityStr(value: string): string { return value; }
function identityNum(value: number): number { return value; }

// Вариант 3: дженерик — один раз, типобезопасно
function identity<T>(value: T): T {
  return value;
}
const result = identity("hello"); // result: string ✅
const result2 = identity(42);     // result2: number ✅
```

Дженерики — это не "шаблоны как в C++". В C++ шаблоны раскрываются при компиляции в конкретный код. В TypeScript дженерик — это **переменная типа**, значение которой TypeScript *выводит* в момент вызова функции или инстанциации типа. Вся типизация стирается в runtime.

---

## Ограничения дженериков (Generic Constraints)

Без ограничений `T` — это буквально любой тип. TypeScript не позволит обращаться ни к каким свойствам:

```ts
function getLength<T>(value: T): number {
  return value.length; // ❌ Property 'length' does not exist on type 'T'
}
```

`extends` добавляет ограничение — говорит "T должен быть совместим с этим типом":

```ts
function getLength<T extends { length: number }>(value: T): number {
  return value.length; // ✅ TypeScript знает, что .length существует
}

getLength("hello");   // ✅ string имеет .length
getLength([1, 2, 3]); // ✅ array имеет .length
getLength(42);        // ❌ number не имеет .length
```

`extends` здесь — это **ограничение**, а не наследование. Читается как "T должен быть структурно совместим с `{ length: number }`", то есть быть подтипом этого типа.

### Ограничения через `keyof`

Один из самых важных паттернов — безопасный доступ к свойствам объекта:

```ts
// Без дженерика — любой string, нет гарантии существования ключа:
function getProperty(obj: object, key: string): unknown {
  return (obj as any)[key];
}

// С дженериком — полная типобезопасность:
function getProperty<T, K extends keyof T>(obj: T, key: K): T[K] {
  return obj[key];
}

const user = { id: 1, name: "Alice", role: "admin" };

const name = getProperty(user, "name");   // name: string ✅
const id = getProperty(user, "id");       // id: number ✅
getProperty(user, "email");               // ❌ "email" не является keyof typeof user
```

Разберём сигнатуру `<T, K extends keyof T>(obj: T, key: K): T[K]`:
- `T` — тип объекта, выводится из первого аргумента
- `K extends keyof T` — K должен быть одним из ключей T
- `T[K]` — тип значения по ключу K в объекте T (indexed access type)

### Ограничения с несколькими параметрами

```ts
// K ограничен keyof T — K зависит от T
function pick<T, K extends keyof T>(obj: T, keys: K[]): Pick<T, K> {
  const result = {} as Pick<T, K>;
  keys.forEach(key => {
    result[key] = obj[key];
  });
  return result;
}

const user = { id: 1, name: "Alice", email: "a@b.com", role: "admin" };
const partial = pick(user, ["name", "email"]);
// partial: { name: string; email: string } — точный тип ✅
```

---

## Параметры дженериков по умолчанию

TypeScript 2.3+ позволяет задавать дефолтные значения для параметров типа:

```ts
// Без дефолтного параметра — нужно указывать явно:
interface ApiResponse<T> {
  data: T;
  status: number;
  message: string;
}
type VoidResponse = ApiResponse<void>; // нужно писать явно

// С дефолтным параметром:
interface ApiResponse<T = unknown> {
  data: T;
  status: number;
  message: string;
}

// Теперь можно не указывать T, если он не нужен:
const response: ApiResponse = { data: null, status: 200, message: "OK" };
// data: unknown — безопаснее, чем any
```

Дефолты работают с ограничениями:

```ts
// T должен быть объектом, по умолчанию — Record<string, unknown>
function merge<T extends object = Record<string, unknown>>(
  target: T,
  source: Partial<T>
): T {
  return { ...target, ...source };
}

merge({ a: 1, b: 2 }, { b: 3 }); // T выведен как { a: number; b: number }
```

---

## Generic Functions vs Generic Classes

### Generic Functions

Параметр типа — часть сигнатуры функции. Выводится при каждом вызове:

```ts
// Каждый вызов — свой T:
function wrap<T>(value: T): { value: T } {
  return { value };
}

const a = wrap("hello");  // a: { value: string }
const b = wrap(42);       // b: { value: number }
// a и b имеют разные конкретные типы — T не "фиксируется" на всю программу
```

Функция может иметь несколько независимых параметров типа:

```ts
function zip<A, B>(as: A[], bs: B[]): [A, B][] {
  return as.map((a, i) => [a, bs[i]] as [A, B]);
}

const zipped = zip([1, 2, 3], ["a", "b", "c"]);
// zipped: [number, string][]
```

### Generic Classes

Параметр типа фиксируется при **инстанциации** класса:

```ts
class Stack<T> {
  private items: T[] = [];

  push(item: T): void {
    this.items.push(item);
  }

  pop(): T | undefined {
    return this.items.pop();
  }

  peek(): T | undefined {
    return this.items[this.items.length - 1];
  }
}

const numStack = new Stack<number>();
numStack.push(1);
numStack.push(2);
numStack.push("hello"); // ❌ Argument of type 'string' is not assignable to 'number'

const strStack = new Stack<string>();
strStack.push("hello"); // ✅
```

T фиксируется для всего экземпляра `numStack: Stack<number>` — все методы работают с `number`.

### Когда generic-метод, а когда generic-класс

```ts
// Generic-класс: когда тип связывает несколько методов:
class Repository<T extends { id: number }> {
  private store = new Map<number, T>();

  save(entity: T): void {
    this.store.set(entity.id, entity);
  }

  findById(id: number): T | undefined {
    return this.store.get(id);
  }
}

// Generic-метод: когда тип нужен только для одной операции:
class Utils {
  static first<T>(arr: T[]): T | undefined {
    return arr[0];
  }

  static last<T>(arr: T[]): T | undefined {
    return arr[arr.length - 1];
  }
}
```

---

## Вывод типов через generic-параметры

Это ключевое отличие дженериков TypeScript от "просто шаблонов": TypeScript **решает уравнение** для T на основе аргументов.

### Вывод из вложенных структур

```ts
function unwrapPromise<T>(promise: Promise<T>): T {
  // Тело не важно для понимания вывода
  throw new Error("not implemented");
}

// TypeScript видит Promise<string> и выводит T = string:
declare const p: Promise<string>;
const val = unwrapPromise(p); // val: string ✅
```

### Вывод при нескольких параметрах типа

TypeScript выводит каждый параметр независимо, потом проверяет согласованность:

```ts
function merge<T, U>(obj1: T, obj2: U): T & U {
  return { ...obj1, ...obj2 } as T & U;
}

const result = merge({ a: 1 }, { b: "hello" });
// T = { a: number }, U = { b: string }
// result: { a: number } & { b: string } = { a: number; b: string }
```

### Когда вывод не срабатывает — явное указание параметров

Иногда TypeScript не может вывести T, или выводит слишком широкий тип:

```ts
// TypeScript выводит T = never, потому что массив пуст:
function createArray<T>(length: number): T[] {
  return new Array(length);
}

const arr = createArray(5);        // arr: unknown[] — T выведен как unknown
const arr2 = createArray<string>(5); // arr2: string[] — явное указание ✅
```

Или TypeScript делает два несовместимых вывода:

```ts
function coerce<T>(value: unknown): T {
  return value as T; // явное приведение — нарушает типобезопасность
}

// T нельзя вывести из `unknown`, нужно указывать явно:
const num = coerce<number>("42"); // T = number, но это опасно!
```

---

## Реализация стандартных utility types с нуля

Это обязательный уровень для senior — понимание механики, а не просто использование готовых типов.

### Partial\<T\>

```ts
// Стандартная библиотека:
type Partial<T> = { [K in keyof T]?: T[K] };

// Как читать:
// keyof T — объединение всех ключей T ("id" | "name" | "email")
// K in keyof T — для каждого ключа K
// ?: — делаем поле опциональным
// T[K] — тип значения по ключу K

type User = { id: number; name: string; email: string };
type PartialUser = Partial<User>;
// { id?: number | undefined; name?: string | undefined; email?: string | undefined }
```

### Required\<T\>

```ts
type Required<T> = { [K in keyof T]-?: T[K] };
// -? — убираем опциональность (противоположность ?)
// +? добавляет, -? убирает

type PartialConfig = { host?: string; port?: number };
type Config = Required<PartialConfig>;
// { host: string; port: number }
```

### Readonly\<T\>

```ts
type Readonly<T> = { readonly [K in keyof T]: T[K] };

type MutablePoint = { x: number; y: number };
type ImmutablePoint = Readonly<MutablePoint>;
// { readonly x: number; readonly y: number }
```

### Pick\<T, K\>

```ts
type Pick<T, K extends keyof T> = { [P in K]: T[P] };

type User = { id: number; name: string; email: string; role: string };
type UserPreview = Pick<User, "id" | "name">;
// { id: number; name: string }
```

### Omit\<T, K\>

```ts
// Omit реализован через Exclude и Pick:
type Omit<T, K extends keyof T> = Pick<T, Exclude<keyof T, K>>;

// Exclude<"id" | "name" | "email", "email"> = "id" | "name"
// Pick<User, "id" | "name"> = { id: number; name: string }

type UserWithoutEmail = Omit<User, "email">;
// { id: number; name: string; role: string }
```

### Record\<K, V\>

```ts
type Record<K extends keyof any, V> = { [P in K]: V };

type Status = "pending" | "active" | "closed";
type StatusLabels = Record<Status, string>;
// { pending: string; active: string; closed: string }

const labels: StatusLabels = {
  pending: "Ожидает",
  active: "Активно",
  closed: "Закрыто",
  // TypeScript потребует все три ключа ✅
};
```

### Awaited\<T\> — рекурсивное разворачивание Promise

```ts
// Упрощённая реализация (настоящая в stdlib сложнее):
type Awaited<T> =
  T extends null | undefined ? T :
  T extends object & { then(onfulfilled: infer F, ...args: any): any }
    ? F extends (value: infer V, ...args: any) => any
      ? Awaited<V>  // рекурсивно разворачиваем вложенные Promise
      : never
    : T;

// Практически:
type A = Awaited<Promise<string>>;           // string
type B = Awaited<Promise<Promise<number>>>;  // number — рекурсия!
type C = Awaited<string>;                    // string — не Promise, возвращаем как есть
```

---

## Продвинутые паттерны с дженериками

### Generic constraints для "builder" API

```ts
type Validator<T> = {
  validate(value: unknown): value is T;
};

function createValidator<T>(check: (v: unknown) => v is T): Validator<T> {
  return { validate: check };
}

const stringValidator = createValidator(
  (v): v is string => typeof v === "string"
);

// stringValidator.validate возвращает value is string — TypeScript понимает это
const input: unknown = "hello";
if (stringValidator.validate(input)) {
  input.toUpperCase(); // ✅ input: string после проверки
}
```

### Inferring из generic-параметра для сужения

```ts
// Тип результата зависит от входного параметра:
function parseValue<T extends string | number | boolean>(
  value: string,
  type: T extends string ? "string" : T extends number ? "number" : "boolean"
): T {
  // ...
  return value as unknown as T;
}
```

### Conditional return type через overloads

Иногда вместо сложного conditional type проще использовать overloads:

```ts
function process(value: string): string;
function process(value: number): number;
function process(value: string | number): string | number {
  return value;
}

const a = process("hello"); // a: string ✅
const b = process(42);      // b: number ✅
```

---

## Типичные ошибки на интервью

- **"Дженерики стираются до `any` в runtime"** — частично верно, но неточно: TypeScript стирает типы полностью, `any` в runtime нет. Дженерики существуют только на этапе компиляции. В runtime нет ни `T`, ни `any`, ни `string` — только JavaScript-значения.

- **Путать ограничение `extends` с наследованием** — `<T extends User>` не означает "T наследует User". Это означает "T должен быть структурно совместим с User", то есть быть подтипом User. Сам User тоже подходит.

- **Не понимать, почему TypeScript выводит `never` из пустого массива** — `[]` типизируется как `never[]` без контекста, потому что нет ни одного элемента для вывода. Решение: аннотация `const arr: string[] = []` или явный параметр `createArray<string>()`.

- **Не знать, что `keyof any` = `string | number | symbol`** — поэтому в `Record<K, V>` ограничение `K extends keyof any` означает "K может быть string, number или symbol". Без ограничения TypeScript не знает, что K можно использовать как ключ объекта.

- **Считать, что класс с дженериком и функция с дженериком работают одинаково** — у класса T фиксируется при `new Stack<number>()` и не меняется для экземпляра. У функции T выводится заново при каждом вызове.

- **Писать `<T extends any>` вместо просто `<T>`** — `extends any` ничего не ограничивает, это эквивалентно отсутствию ограничения, но выглядит запутанно. Иногда пишут ошибочно вместо `<T extends object>`.
