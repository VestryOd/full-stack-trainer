<!-- verified: 2026-06-23, corrections: 0 -->
# Type Narrowing and Guards

## How TypeScript Tracks Types: Control Flow Analysis

TypeScript builds a control flow graph (CFG) for each function. At each node in the graph TypeScript knows the type of every variable, accounting for all branches, checks, and early returns.

```ts
function process(value: string | number | null | undefined) {
  //                      ^ TypeScript: value is string | number | null | undefined

  if (value == null) {
    return; // null and undefined eliminated
  }
  //       ^ TypeScript: value is string | number

  if (typeof value === "string") {
    value.toUpperCase(); // TypeScript: value is string ✅
  } else {
    value.toFixed(2);    // TypeScript: value is number ✅
  }
}
```

Important: narrowing is not a runtime mechanism. TypeScript applies it only during analysis. In JavaScript everything is erased; you are responsible for ensuring the checks actually run.

---

## typeof — Primitives

`typeof` narrows to JavaScript primitive types:

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
  // value: object | null — typeof null === "object" in JS!
  if (value === null) {
    return "null";
  }
  return JSON.stringify(value);      // value: object
}
```

**Trap: `typeof null === "object"`** — the classic JS bug that TypeScript doesn't hide:

```ts
function isObject(value: unknown): boolean {
  return typeof value === "object"; // null returns true too!
}

// Correct check:
function isObject(value: unknown): boolean {
  return typeof value === "object" && value !== null;
}
```

What `typeof` recognizes:

```txt
"string"    → string
"number"    → number
"boolean"   → boolean
"bigint"    → bigint
"symbol"    → symbol
"undefined" → undefined
"function"  → Function (subtype of object)
"object"    → object | null  ← trap!
```

---

## instanceof — Classes and Constructors

`instanceof` narrows to a specific class instance:

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

**Limitation of `instanceof`:** only works with classes created via `new`. Does not work with:
- Plain objects (`{}`)
- Objects from other iframes/realms (different prototype chains)
- TypeScript types (interfaces, type aliases) — they're erased at runtime

```ts
interface Point { x: number; y: number }
const p = { x: 1, y: 2 };

if (p instanceof Point) { // ❌ 'Point' only refers to a type, but is being used as a value here
}
```

---

## The `in` Operator — Key Presence Check

`in` narrows the type by checking whether a key exists in an object:

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

`in` works for discriminating by optional fields:

```ts
type Square   = { kind: "square"; side: number };
type Circle   = { kind: "circle"; radius: number };
type Triangle = { base: number; height: number }; // no kind field

type Shape = Square | Circle | Triangle;

function area(shape: Shape): number {
  if ("kind" in shape) {
    // shape: Square | Circle — Triangle has no kind field
    if (shape.kind === "square") return shape.side ** 2;
    return Math.PI * shape.radius ** 2;
  }
  // shape: Triangle
  return (shape.base * shape.height) / 2;
}
```

**Important nuance:** `in` checks the entire prototype chain, not just the object's own properties. For plain objects this usually doesn't matter, but for class instances it can produce unexpected results:

```ts
class A { foo() {} }
class B {}

const b = new B();
console.log("foo" in b);       // false — foo is not in b or B.prototype
console.log("toString" in b);  // true — toString comes from Object.prototype
```

---

## Custom Type Guards: The `is` Keyword

When built-in narrowing is insufficient, you can write a predicate function that explicitly tells TypeScript what type it checks:

```ts
// Syntax: parameter is Type
function isString(value: unknown): value is string {
  return typeof value === "string";
}

const input: unknown = "hello";

if (isString(input)) {
  input.toUpperCase(); // input: string ✅ — TypeScript trusts the predicate
}
```

Without `is`, TypeScript only sees a `boolean` return and doesn't narrow:

```ts
// Without is — TypeScript only sees boolean:
function isStringPlain(value: unknown): boolean {
  return typeof value === "string";
}

const input: unknown = "hello";
if (isStringPlain(input)) {
  input.toUpperCase(); // ❌ Object is of type 'unknown'
}
```

### Practical Type Guards

```ts
// Guard for an interface — check the keys:
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

// Guard for a union discriminant:
type Shape =
  | { kind: "circle"; radius: number }
  | { kind: "square"; side: number };

function isCircle(shape: Shape): shape is { kind: "circle"; radius: number } {
  return shape.kind === "circle";
}

// Guard for an array:
function isStringArray(arr: unknown[]): arr is string[] {
  return arr.every(item => typeof item === "string");
}

// Generic guard:
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

### The Risk of Custom Type Guards

**Critically important:** TypeScript *blindly trusts* the return value of an `is` function. If you write an incorrect check, TypeScript won't complain:

```ts
// TypeScript does not verify that the body is correct:
function isString(value: unknown): value is string {
  return typeof value === "number"; // ❌ Logically wrong, but compiles!
}

const x: unknown = 42;
if (isString(x)) {
  x.toUpperCase(); // ✅ TypeScript thinks x is string, but runtime crashes
}
```

This is a fundamental limitation: type guards are a contract between the developer and the compiler, not an automatically verified check. This is exactly why production code often uses runtime validation with Zod or similar libraries (see [Advanced Patterns]).

---

## Discriminated Unions — The Foundation of Reliable Code

A discriminated union is a union where each variant has a common discriminant field with a unique literal value:

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

**Why discriminated unions beat optional fields:**

```ts
// ❌ Optional fields — invalid combinations are expressible:
type Result = {
  data?: User;
  error?: Error;
  isLoading?: boolean;
};
// Nothing prevents: { data: user, error: someError } — what does this even mean?

// ✅ Discriminated union — invalid states are inexpressible:
type Result =
  | { status: "success"; data: User }
  | { status: "error"; error: Error }
  | { status: "loading" };
// Impossible to create { status: "success"; error: Error } ✅
```

### Multiple Discriminants

TypeScript can use multiple fields simultaneously:

```ts
type Action =
  | { type: "user"; subtype: "create"; payload: { name: string } }
  | { type: "user"; subtype: "delete"; payload: { id: number } }
  | { type: "order"; subtype: "create"; payload: { items: string[] } };

function handleAction(action: Action) {
  if (action.type === "user") {
    // action: two variants with type === "user"
    if (action.subtype === "create") {
      action.payload.name; // ✅
    } else {
      action.payload.id; // ✅
    }
  }
}
```

---

## Exhaustiveness Checking with `never`

Exhaustiveness checking is one of the most important TypeScript patterns. The idea: if all variants are handled, the type in the final branch must be `never`. If you add a new variant and don't update the switch — the build breaks.

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
      // If all variants are handled — shape is never here
      // If not — TypeScript errors on the line below:
      const exhaustiveCheck: never = shape;
      throw new Error(`Unhandled shape: ${JSON.stringify(exhaustiveCheck)}`);
  }
}
```

Adding a new shape:

```ts
type Shape =
  | { kind: "circle"; radius: number }
  | { kind: "square"; side: number }
  | { kind: "triangle"; base: number; height: number }
  | { kind: "rectangle"; width: number; height: number }; // new!

// ❌ The compiler now breaks the build:
// Type '{ kind: "rectangle"; width: number; height: number; }'
// is not assignable to type 'never'
// — add case "rectangle" ✅
```

**Helper function for exhaustiveness checking:**

```ts
function assertNever(value: never, message?: string): never {
  throw new Error(message ?? `Unexpected value: ${JSON.stringify(value)}`);
}

function area(shape: Shape): number {
  switch (shape.kind) {
    case "circle":   return Math.PI * shape.radius ** 2;
    case "square":   return shape.side ** 2;
    case "triangle": return (shape.base * shape.height) / 2;
    default:         return assertNever(shape); // ❌ compile error if cases are missing
  }
}
```

**Exhaustiveness in if-else:**

```ts
type Direction = "north" | "south" | "east" | "west";

function move(dir: Direction): [number, number] {
  if (dir === "north") return [0, 1];
  if (dir === "south") return [0, -1];
  if (dir === "east")  return [1, 0];
  if (dir === "west")  return [-1, 0];

  // dir: never here — all variants exhausted
  assertNever(dir);
}
```

---

## Assertion Functions: The `asserts` Keyword

TypeScript 3.7+ introduces assertion functions — functions that return void but tell TypeScript that if the function returns normally (without throwing), a certain type is guaranteed.

### `asserts condition`

```ts
function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

function processUser(user: User | null) {
  assert(user !== null, "user must not be null");
  // TypeScript: user is User (not null) after the assert call ✅
  user.name.toUpperCase();
}
```

`asserts condition` means: "if this function returned — `condition` is truthy". TypeScript uses this to narrow in the calling code.

### `asserts value is Type`

```ts
function assertIsString(value: unknown): asserts value is string {
  if (typeof value !== "string") {
    throw new TypeError(`Expected string, got ${typeof value}`);
  }
}

function processInput(input: unknown) {
  assertIsString(input);
  // TypeScript: input is string ✅
  input.toUpperCase();
}
```

Difference between `asserts value is T` and `value is T`:
- `value is T` — returns `boolean`, used in an `if` condition
- `asserts value is T` — returns `void`, type is already narrowed in the calling code after the call

```ts
// Type guard — requires if:
if (isString(input)) {
  input.toUpperCase(); // ✅ only inside the if
}
// Outside the if — input: unknown again

// Assertion function — no if needed:
assertIsString(input);
input.toUpperCase(); // ✅ immediately after the call, no if required
```

### Real-World Example: Input Validation

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
  // rawData: UserInput ✅ — type narrowed after the assertion function
  return { id: generateId(), ...rawData };
}
```

### Limitations of Assertion Functions

```ts
// 1. Must return void or never — not boolean:
function assertIsString(v: unknown): asserts v is string {
  return typeof v === "string"; // ❌ Type 'boolean' is not assignable to type 'void'
}

// 2. Could not be arrow functions before TS 4.4:
// TS 3.7–4.3: only function declarations/expressions worked
const assertIsString = (v: unknown): asserts v is string => {
  if (typeof v !== "string") throw new Error();
};
// TS 4.4+ — works ✅

// 3. TypeScript does NOT verify the body is correct — same as with is:
function assertIsString(v: unknown): asserts v is string {
  // Empty body — TypeScript won't error,
  // but the runtime consequences can be catastrophic
}
```

---

## Narrowing via Equality and Assignment

TypeScript understands narrowing through direct comparison:

```ts
function compare(a: string | number, b: string | boolean) {
  if (a === b) {
    // a and b must be the same type — the only overlap is string
    a; // string ✅
    b; // string ✅
  }
}
```

Narrowing via assignment:

```ts
let value: string | number = Math.random() > 0.5 ? "hello" : 42;
// value: string | number

value = "definitely a string";
// value: string — TypeScript knows we just assigned a string

value.toUpperCase(); // ✅
```

Truthy/falsy narrowing:

```ts
function process(value: string | null | undefined | 0 | false) {
  if (value) {
    // value: string — null, undefined, 0, false filtered out
    // CAUTION: "" (empty string) is also falsy!
    value.toUpperCase();
  }
}

// Safer — explicit null/undefined check:
function process(value: string | null | undefined) {
  if (value != null) { // != checks both null and undefined
    value.toUpperCase(); // value: string ✅
  }
}
```

---

## Common Interview Traps

- **"Type guards are verified by TypeScript at runtime"** — no. TypeScript is completely erased at compile time. A type guard is a hint to the compiler. If the guard body is wrong, TypeScript won't detect the error, and the runtime may crash.

- **Not knowing the difference between `value is T` and `asserts value is T`** — the first returns `boolean` and is used in `if`. The second returns `void` and narrows the type in code after the call, without `if`. These are fundamentally different contracts with the compiler.

- **Forgetting the `exhaustiveCheck: never` pattern when adding a new union variant** — a discriminated union without exhaustiveness checking is a silent time bomb. New variant added, switch without default won't break, the function silently returns `undefined` instead of a number. Always add `assertNever` or `const _: never = x`.

- **`typeof null === "object"` — always** — forgetting `&& value !== null` after `typeof value === "object"` is a classic beginner mistake that experienced developers sometimes make in a hurry.

- **Thinking `in` checks only own properties** — `in` walks the entire prototype chain. `"toString" in {}` is `true`. For own-property checks only, use `Object.prototype.hasOwnProperty.call(obj, key)` or `Object.hasOwn(obj, key)` (ES2022).

- **Not knowing that TypeScript narrows after `if (x == null) return`** — `== null` (loose equality) checks both `null` and `undefined` simultaneously. After this check TypeScript removes both from the type. Many developers don't know that TypeScript understands the semantics of `==` in this specific case.
