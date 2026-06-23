<!-- verified: 2026-06-23, corrections: 0 -->
# Сужение типов и type guards

## Как TypeScript отслеживает типы: control flow анализ

TypeScript строит граф потока управления (control flow graph) для каждой функции. В каждой точке графа TypeScript знает, какой тип у каждой переменной с учётом всех ветвей, проверок и досрочных возвратов.

```ts
function process(value: string | number | null | undefined) {
  //                      ^ TypeScript: value — string | number | null | undefined

  if (value == null) {
    return; // null и undefined выброшены
  }
  //       ^ TypeScript: value — string | number

  if (typeof value === "string") {
    value.toUpperCase(); // TypeScript: value — string ✅
  } else {
    value.toFixed(2);    // TypeScript: value — number ✅
  }
}
```

Важно: сужение — это не runtime-механизм. TypeScript применяет его только при анализе кода. В JavaScript всё стирается; вы несёте ответственность за то, что проверки реально выполняются.

---

## typeof — примитивы

`typeof` сужает до примитивных типов JavaScript:

```ts
function formatValue(value: string | number | boolean | object | null) {
  if (typeof value === "string") {
    return value.toUpperCase();      // value: string
  }
  if (typeof value === "number") {
    return value.toFixed(2);         // value: number
  }
  if (typeof value === "boolean") {
    return value ? "yes" : "no";     // value: boolean
  }
  // value: object | null — typeof null === "object" в JS!
  if (value === null) {
    return "null";
  }
  return JSON.stringify(value);      // value: object
}
```

**Ловушка: `typeof null === "object"`** — классическая JS-ошибка, TypeScript её не скрывает:

```ts
function isObject(value: unknown): boolean {
  return typeof value === "object"; // null тоже вернёт true!
}

// Правильная проверка:
function isObject(value: unknown): boolean {
  return typeof value === "object" && value !== null;
}
```

Что распознаёт `typeof`:

```txt
"string"    → string
"number"    → number
"boolean"   → boolean
"bigint"    → bigint
"symbol"    → symbol
"undefined" → undefined
"function"  → Function (подтип object)
"object"    → object | null  ← ловушка!
```

---

## instanceof — классы и конструкторы

`instanceof` сужает до экземпляра конкретного класса:

```ts
class NetworkError extends Error {
  constructor(public statusCode: number, message: string) {
    super(message);
    this.name = "NetworkError";
  }
}

class ValidationError extends Error {
  constructor(public fields: string[], message: string) {
    super(message);
    this.name = "ValidationError";
  }
}

function handleError(err: Error) {
  if (err instanceof NetworkError) {
    console.log(`HTTP ${err.statusCode}`); // err: NetworkError ✅
  } else if (err instanceof ValidationError) {
    console.log(`Fields: ${err.fields.join(", ")}`); // err: ValidationError ✅
  } else {
    console.log(err.message); // err: Error
  }
}
```

**Ограничение `instanceof`:** работает только с классами, созданными через `new`. Не работает с:
- Обычными объектами (`{}`)
- Объектами из других iframe/realm (разные прототипные цепочки)
- Типами TypeScript (интерфейсами, type aliases) — они стираются в runtime

```ts
interface Point { x: number; y: number }
const p = { x: 1, y: 2 };

if (p instanceof Point) { // ❌ 'Point' only refers to a type, but is being used as a value here
}
```

---

## Оператор `in` — проверка ключей

`in` сужает тип по наличию ключа в объекте:

```ts
type Cat = { name: string; meow(): void };
type Dog = { name: string; bark(): void };

function makeSound(animal: Cat | Dog) {
  if ("meow" in animal) {
    animal.meow(); // animal: Cat ✅
  } else {
    animal.bark(); // animal: Dog ✅
  }
}
```

`in` работает для дискриминации по необязательным полям:

```ts
type Square   = { kind: "square"; side: number };
type Circle   = { kind: "circle"; radius: number };
type Triangle = { base: number; height: number }; // нет поля kind

type Shape = Square | Circle | Triangle;

function area(shape: Shape): number {
  if ("kind" in shape) {
    // shape: Square | Circle — у Triangle нет поля kind
    if (shape.kind === "square") return shape.side ** 2;
    return Math.PI * shape.radius ** 2;
  }
  // shape: Triangle
  return (shape.base * shape.height) / 2;
}
```

**Важный нюанс:** `in` проверяет наличие ключа в prototype chain, а не только в самом объекте. Для plain objects это обычно не проблема, но для классов может давать неожиданные результаты:

```ts
class A { foo() {} }
class B {}

const b = new B();
console.log("foo" in b); // false — foo нет ни в b, ни в B.prototype
console.log("toString" in b); // true — toString из Object.prototype
```

---

## Кастомные type guards: ключевое слово `is`

Когда встроенных способов сужения недостаточно, можно написать функцию-предикат, которая явно сообщает TypeScript, какой тип она проверяет:

```ts
// Синтаксис: параметр is Тип
function isString(value: unknown): value is string {
  return typeof value === "string";
}

const input: unknown = "hello";

if (isString(input)) {
  input.toUpperCase(); // input: string ✅ — TypeScript доверяет предикату
}
```

Без `is` TypeScript не поймёт, что проверка что-то сужает:

```ts
// Без is — TypeScript видит только boolean:
function isStringPlain(value: unknown): boolean {
  return typeof value === "string";
}

const input: unknown = "hello";
if (isStringPlain(input)) {
  input.toUpperCase(); // ❌ Object is of type 'unknown'
}
```

### Практические type guards

```ts
// Guard для интерфейса — проверяем ключи:
interface User {
  id: number;
  name: string;
  email: string;
}

function isUser(value: unknown): value is User {
  return (
    typeof value === "object" &&
    value !== null &&
    "id" in value && typeof (value as any).id === "number" &&
    "name" in value && typeof (value as any).name === "string" &&
    "email" in value && typeof (value as any).email === "string"
  );
}

// Guard для union discriminant:
type Shape =
  | { kind: "circle"; radius: number }
  | { kind: "square"; side: number };

function isCircle(shape: Shape): shape is { kind: "circle"; radius: number } {
  return shape.kind === "circle";
}

// Guard для массива:
function isStringArray(arr: unknown[]): arr is string[] {
  return arr.every(item => typeof item === "string");
}

// Guard с дженериком:
function isArrayOf<T>(
  arr: unknown[],
  guard: (item: unknown) => item is T
): arr is T[] {
  return arr.every(guard);
}

const items: unknown[] = ["a", "b", "c"];
if (isArrayOf(items, isString)) {
  items.forEach(item => item.toUpperCase()); // item: string ✅
}
```

### Риски кастомных type guards

**Критически важно:** TypeScript *слепо доверяет* возвращаемому значению `is`-функции. Если вы напишете неверную проверку — TypeScript не скажет об ошибке:

```ts
// TypeScript не проверяет, что тело функции корректно:
function isString(value: unknown): value is string {
  return typeof value === "number"; // ❌ Логически неверно, но компилируется!
}

const x: unknown = 42;
if (isString(x)) {
  x.toUpperCase(); // ✅ TypeScript думает, что x — string, но в runtime — crash
}
```

Это принципиальное ограничение: type guards — это контракт между разработчиком и компилятором, а не автоматически верифицированная проверка. Именно поэтому в production-коде часто применяют runtime-валидацию через Zod или подобные библиотеки (см. [Advanced Patterns]).

---

## Discriminated Unions — основа надёжного кода

Discriminated union — это union, где каждый вариант имеет общее поле-дискриминант с уникальным литеральным значением:

```ts
type Result<T> =
  | { status: "success"; data: T }
  | { status: "error"; error: Error; code: number }
  | { status: "loading" };

function render<T>(result: Result<T>) {
  switch (result.status) {
    case "success":
      return result.data;   // result: { status: "success"; data: T } ✅
    case "error":
      return result.error;  // result: { status: "error"; error: Error; code: number } ✅
    case "loading":
      return null;          // result: { status: "loading" } ✅
  }
}
```

**Почему discriminated unions лучше опциональных полей:**

```ts
// ❌ Опциональные поля — можно создать невалидные комбинации:
type Result = {
  data?: User;
  error?: Error;
  isLoading?: boolean;
};
// Ничто не мешает: { data: user, error: someError } — что это значит?

// ✅ Discriminated union — невалидные состояния невыразимы:
type Result =
  | { status: "success"; data: User }
  | { status: "error"; error: Error }
  | { status: "loading" };
// Невозможно создать { status: "success"; error: Error } ✅
```

### Несколько дискриминантов

TypeScript может использовать несколько полей одновременно:

```ts
type Action =
  | { type: "user"; subtype: "create"; payload: { name: string } }
  | { type: "user"; subtype: "delete"; payload: { id: number } }
  | { type: "order"; subtype: "create"; payload: { items: string[] } };

function handleAction(action: Action) {
  if (action.type === "user") {
    // action: двa варианта с type === "user"
    if (action.subtype === "create") {
      action.payload.name; // ✅
    } else {
      action.payload.id; // ✅
    }
  }
}
```

---

## Exhaustiveness checking с `never`

Проверка на исчерпанность — один из самых важных паттернов TypeScript. Идея: если все варианты обработаны, тип в последней ветке должен быть `never`. Если мы добавим новый вариант и не обновим switch — компиляция сломается.

```ts
type Shape =
  | { kind: "circle"; radius: number }
  | { kind: "square"; side: number }
  | { kind: "triangle"; base: number; height: number };

function area(shape: Shape): number {
  switch (shape.kind) {
    case "circle":
      return Math.PI * shape.radius ** 2;
    case "square":
      return shape.side ** 2;
    case "triangle":
      return (shape.base * shape.height) / 2;
    default:
      // Если все варианты обработаны — shape здесь never
      // Если нет — TypeScript выдаст ошибку ниже:
      const exhaustiveCheck: never = shape;
      throw new Error(`Unhandled shape: ${JSON.stringify(exhaustiveCheck)}`);
  }
}
```

Добавляем новый вид фигуры:

```ts
type Shape =
  | { kind: "circle"; radius: number }
  | { kind: "square"; side: number }
  | { kind: "triangle"; base: number; height: number }
  | { kind: "rectangle"; width: number; height: number }; // новый!

// ❌ Теперь компилятор сломает сборку:
// Type '{ kind: "rectangle"; width: number; height: number; }'
// is not assignable to type 'never'
// — нужно добавить case "rectangle" ✅
```

**Вспомогательная функция для exhaustiveness check:**

```ts
function assertNever(value: never, message?: string): never {
  throw new Error(message ?? `Unexpected value: ${JSON.stringify(value)}`);
}

function area(shape: Shape): number {
  switch (shape.kind) {
    case "circle":   return Math.PI * shape.radius ** 2;
    case "square":   return shape.side ** 2;
    case "triangle": return (shape.base * shape.height) / 2;
    default:         return assertNever(shape); // ❌ compile error при незакрытых вариантах
  }
}
```

**Exhaustiveness в if-else:**

```ts
type Direction = "north" | "south" | "east" | "west";

function move(dir: Direction): [number, number] {
  if (dir === "north") return [0, 1];
  if (dir === "south") return [0, -1];
  if (dir === "east")  return [1, 0];
  if (dir === "west")  return [-1, 0];

  // dir: never здесь — все варианты исчерпаны
  assertNever(dir);
}
```

---

## Assertion Functions: ключевое слово `asserts`

TypeScript 3.7+ вводит assertion functions — функции, которые не возвращают значение, но сообщают TypeScript, что если функция вернулась нормально (без throw), то определённый тип гарантирован.

### `asserts condition`

```ts
function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

function processUser(user: User | null) {
  assert(user !== null, "user must not be null");
  // TypeScript: user — User (не null) после вызова assert ✅
  user.name.toUpperCase();
}
```

`asserts condition` означает: "если функция вернулась — `condition` истинно". TypeScript использует это для сужения в вызывающем коде.

### `asserts value is Type`

```ts
function assertIsString(value: unknown): asserts value is string {
  if (typeof value !== "string") {
    throw new TypeError(`Expected string, got ${typeof value}`);
  }
}

function processInput(input: unknown) {
  assertIsString(input);
  // TypeScript: input — string ✅
  input.toUpperCase();
}
```

Разница между `asserts value is T` и `value is T`:
- `value is T` — возвращает `boolean`, используется в `if`-условии
- `asserts value is T` — возвращает `void`, при возврате тип уже сужен в вызывающем коде

```ts
// Type guard — нужен if:
if (isString(input)) {
  input.toUpperCase(); // ✅ только внутри if
}
// За пределами if — input: unknown снова

// Assertion function — не нужен if:
assertIsString(input);
input.toUpperCase(); // ✅ сразу после вызова, без if
```

### Реальный пример: валидация входных данных

```ts
type UserInput = {
  name: string;
  age: number;
  email: string;
};

function validateUserInput(
  data: Record<string, unknown>
): asserts data is UserInput {
  if (typeof data.name !== "string" || data.name.length === 0) {
    throw new ValidationError(["name"], "Name is required");
  }
  if (typeof data.age !== "number" || data.age < 0 || data.age > 150) {
    throw new ValidationError(["age"], "Age must be between 0 and 150");
  }
  if (typeof data.email !== "string" || !data.email.includes("@")) {
    throw new ValidationError(["email"], "Invalid email");
  }
}

function createUser(rawData: Record<string, unknown>): User {
  validateUserInput(rawData);
  // rawData: UserInput ✅ — после assertion function тип сужен
  return { id: generateId(), ...rawData };
}
```

### Ограничения assertion functions

```ts
// 1. Должны возвращать void или never — не boolean:
function assertIsString(v: unknown): asserts v is string {
  return typeof v === "string"; // ❌ Type 'boolean' is not assignable to type 'void'
}

// 2. Не могут быть стрелочными функциями (до TS 4.4):
// TS 3.7–4.3: только function declaration/expression
const assertIsString = (v: unknown): asserts v is string => {
  // В ранних версиях TS это не работало
  if (typeof v !== "string") throw new Error();
};
// С TS 4.4+ — работает ✅

// 3. TypeScript НЕ проверяет корректность тела — то же, что и с is:
function assertIsString(v: unknown): asserts v is string {
  // Пустое тело — TypeScript не выдаст ошибку,
  // но в runtime могут быть катастрофические последствия
}
```

---

## Сужение через равенство и присваивание

TypeScript понимает сужение через прямое сравнение:

```ts
function compare(a: string | number, b: string | boolean) {
  if (a === b) {
    // a и b должны быть одного типа — единственный вариант: string
    a; // string ✅
    b; // string ✅
  }
}
```

Сужение через присваивание:

```ts
let value: string | number = Math.random() > 0.5 ? "hello" : 42;
// value: string | number

value = "definitely a string";
// value: string — TypeScript знает, что мы только что присвоили string

value.toUpperCase(); // ✅
```

Truthy/falsy сужение:

```ts
function process(value: string | null | undefined | 0 | false) {
  if (value) {
    // value: string — null, undefined, 0, false, "" отфильтрованы
    // ОСТОРОЖНО: "" (пустая строка) тоже falsy!
    value.toUpperCase();
  }
}

// Безопаснее — явная проверка на null/undefined:
function process(value: string | null | undefined) {
  if (value != null) { // != проверяет и null, и undefined
    value.toUpperCase(); // value: string ✅
  }
}
```

---

## Типичные ошибки на интервью

- **"Type guards проверяются TypeScript в runtime"** — нет. TypeScript полностью стирается при компиляции. Type guard — это подсказка компилятору. Если тело guard-функции написано неверно, TypeScript не обнаружит ошибку, а runtime может упасть.

- **Не знать разницу между `value is T` и `asserts value is T`** — первый возвращает `boolean` и используется в `if`. Второй возвращает `void` и сужает тип в коде после вызова, без `if`. Это принципиально разный контракт с компилятором.

- **Забыть про `exhaustiveCheck: never` при добавлении нового варианта union** — discriminated union без exhaustiveness check — это тихая бомба. Новый вариант добавлен, switch без default не сломается, функция вернёт `undefined` вместо числа. Всегда добавлять `assertNever` или `const _: never = x`.

- **`typeof null === "object"` — всегда** — не проверить `&& value !== null` после `typeof value === "object"` — классическая ошибка новичка, которую иногда допускают даже опытные разработчики в спешке.

- **Считать, что `in` проверяет только собственные свойства** — `in` проходит по всей prototype chain. `"toString" in {}` — `true`. Для проверки только собственных свойств нужен `Object.prototype.hasOwnProperty.call(obj, key)` или `Object.hasOwn(obj, key)` (ES2022).

- **Не знать, что TypeScript сужает тип после `if (x == null) return`** — `== null` (двойное равно) проверяет и `null`, и `undefined` одновременно. После такой проверки TypeScript убирает оба из типа. Многие не знают, что TypeScript понимает семантику `==` в этом специфическом случае.
