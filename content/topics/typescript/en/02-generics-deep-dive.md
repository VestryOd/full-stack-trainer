<!-- verified: 2026-06-23, corrections: 0 -->
# Generics — Deep Dive

## Why Generics Exist: The Problem They Solve

Without generics, you have to choose between losing type safety and duplicating code:

```ts
// Option 1: any — all type information lost
function identity(value: any): any {
  return value;
}
const result = identity("hello"); // result: any — IDE won't suggest methods

// Option 2: overloads — duplication, doesn't scale
function identityStr(value: string): string { return value; }
function identityNum(value: number): number { return value; }

// Option 3: generic — once, type-safe
function identity<T>(value: T): T {
  return value;
}
const result = identity("hello"); // result: string ✅
const result2 = identity(42);     // result2: number ✅
```

Generics are **not** "templates like in C++". In C++, templates are expanded at compile time into concrete code. In TypeScript, a generic is a **type variable** whose value TypeScript *infers* at the call site or type instantiation. All typing is erased at runtime.

---

## Generic Constraints

Without constraints, `T` is literally any type. TypeScript won't let you access any properties:

```ts
function getLength<T>(value: T): number {
  return value.length; // ❌ Property 'length' does not exist on type 'T'
}
```

`extends` adds a constraint — it says "T must be compatible with this type":

```ts
function getLength<T extends { length: number }>(value: T): number {
  return value.length; // ✅ TypeScript knows .length exists
}

getLength("hello");   // ✅ string has .length
getLength([1, 2, 3]); // ✅ array has .length
getLength(42);        // ❌ number doesn't have .length
```

`extends` here is a **constraint**, not inheritance. Read it as "T must be structurally compatible with `{ length: number }`", meaning T must be a subtype of that type.

### Constraints with `keyof`

One of the most important patterns — type-safe property access:

```ts
// Without generic — any string, no guarantee the key exists:
function getProperty(obj: object, key: string): unknown {
  return (obj as any)[key];
}

// With generic — full type safety:
function getProperty<T, K extends keyof T>(obj: T, key: K): T[K] {
  return obj[key];
}

const user = { id: 1, name: "Alice", role: "admin" };

const name = getProperty(user, "name");   // name: string ✅
const id = getProperty(user, "id");       // id: number ✅
getProperty(user, "email");               // ❌ "email" is not a keyof typeof user
```

Breaking down the signature `<T, K extends keyof T>(obj: T, key: K): T[K]`:
- `T` — the object type, inferred from the first argument
- `K extends keyof T` — K must be one of T's keys
- `T[K]` — the type of the value at key K in object T (indexed access type)

### Constraints with Multiple Type Parameters

```ts
// K is constrained by keyof T — K depends on T
function pick<T, K extends keyof T>(obj: T, keys: K[]): Pick<T, K> {
  const result = {} as Pick<T, K>;
  keys.forEach(key => {
    result[key] = obj[key];
  });
  return result;
}

const user = { id: 1, name: "Alice", email: "a@b.com", role: "admin" };
const partial = pick(user, ["name", "email"]);
// partial: { name: string; email: string } — precise type ✅
```

---

## Default Generic Parameters

TypeScript 2.3+ allows setting default values for type parameters:

```ts
// Without default — must specify explicitly:
interface ApiResponse<T> {
  data: T;
  status: number;
  message: string;
}
type VoidResponse = ApiResponse<void>; // must write explicitly

// With default:
interface ApiResponse<T = unknown> {
  data: T;
  status: number;
  message: string;
}

// Now T can be omitted when not needed:
const response: ApiResponse = { data: null, status: 200, message: "OK" };
// data: unknown — safer than any
```

Defaults work with constraints:

```ts
// T must be an object, default is Record<string, unknown>
function merge<T extends object = Record<string, unknown>>(
  target: T,
  source: Partial<T>
): T {
  return { ...target, ...source };
}

merge({ a: 1, b: 2 }, { b: 3 }); // T inferred as { a: number; b: number }
```

---

## Generic Functions vs Generic Classes

### Generic Functions

The type parameter is part of the function signature. It's inferred at each call site:

```ts
// Each call has its own T:
function wrap<T>(value: T): { value: T } {
  return { value };
}

const a = wrap("hello");  // a: { value: string }
const b = wrap(42);       // b: { value: number }
// a and b have different concrete types — T isn't "fixed" for the program
```

A function can have multiple independent type parameters:

```ts
function zip<A, B>(as: A[], bs: B[]): [A, B][] {
  return as.map((a, i) => [a, bs[i]] as [A, B]);
}

const zipped = zip([1, 2, 3], ["a", "b", "c"]);
// zipped: [number, string][]
```

### Generic Classes

The type parameter is fixed at **instantiation** of the class:

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

T is fixed for the entire `numStack: Stack<number>` instance — all methods work with `number`.

### When to Use a Generic Method vs a Generic Class

```ts
// Generic class: when the type connects multiple methods:
class Repository<T extends { id: number }> {
  private store = new Map<number, T>();

  save(entity: T): void {
    this.store.set(entity.id, entity);
  }

  findById(id: number): T | undefined {
    return this.store.get(id);
  }
}

// Generic method: when the type is needed for just one operation:
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

## Type Inference Flows Through Generic Parameters

This is the key difference between TypeScript generics and "just templates": TypeScript **solves an equation** for T based on the arguments.

### Inference from Nested Structures

```ts
function unwrapPromise<T>(promise: Promise<T>): T {
  // The body doesn't matter for understanding inference
  throw new Error("not implemented");
}

// TypeScript sees Promise<string> and infers T = string:
declare const p: Promise<string>;
const val = unwrapPromise(p); // val: string ✅
```

### Inference with Multiple Type Parameters

TypeScript infers each parameter independently, then checks consistency:

```ts
function merge<T, U>(obj1: T, obj2: U): T & U {
  return { ...obj1, ...obj2 } as T & U;
}

const result = merge({ a: 1 }, { b: "hello" });
// T = { a: number }, U = { b: string }
// result: { a: number } & { b: string } = { a: number; b: string }
```

### When Inference Fails — Explicit Type Parameters

Sometimes TypeScript can't infer T, or infers a type that's too wide:

```ts
// TypeScript infers T = unknown because the array is empty:
function createArray<T>(length: number): T[] {
  return new Array(length);
}

const arr = createArray(5);          // arr: unknown[] — T inferred as unknown
const arr2 = createArray<string>(5); // arr2: string[] — explicit ✅
```

Or TypeScript makes two incompatible inferences:

```ts
function coerce<T>(value: unknown): T {
  return value as T; // explicit cast — breaks type safety
}

// T can't be inferred from `unknown`, must be specified explicitly:
const num = coerce<number>("42"); // T = number, but this is dangerous!
```

---

## Implementing Standard Utility Types from Scratch

This is the required senior level — understanding the mechanics, not just using ready-made types.

### Partial\<T\>

```ts
// Standard library:
type Partial<T> = { [K in keyof T]?: T[K] };

// How to read it:
// keyof T — union of all keys of T ("id" | "name" | "email")
// K in keyof T — for each key K
// ?: — make the field optional
// T[K] — the type of the value at key K

type User = { id: number; name: string; email: string };
type PartialUser = Partial<User>;
// { id?: number | undefined; name?: string | undefined; email?: string | undefined }
```

### Required\<T\>

```ts
type Required<T> = { [K in keyof T]-?: T[K] };
// -? removes optionality (opposite of ?)
// +? adds, -? removes

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
// Omit is implemented via Exclude and Pick:
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
  pending: "Pending",
  active: "Active",
  closed: "Closed",
  // TypeScript requires all three keys ✅
};
```

### Awaited\<T\> — Recursively Unwrapping Promises

```ts
// Simplified implementation (the real stdlib version is more complex):
type Awaited<T> =
  T extends null | undefined ? T :
  T extends object & { then(onfulfilled: infer F, ...args: any): any }
    ? F extends (value: infer V, ...args: any) => any
      ? Awaited<V>  // recursively unwrap nested Promises
      : never
    : T;

// In practice:
type A = Awaited<Promise<string>>;           // string
type B = Awaited<Promise<Promise<number>>>;  // number — recursion!
type C = Awaited<string>;                    // string — not a Promise, returned as-is
```

---

## Advanced Generic Patterns

### Generic Constraints for a Builder API

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

// stringValidator.validate returns value is string — TypeScript understands this
const input: unknown = "hello";
if (stringValidator.validate(input)) {
  input.toUpperCase(); // ✅ input: string after the check
}
```

### Conditional Return Type via Overloads

Sometimes it's simpler to use overloads instead of complex conditional types:

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

## Common Interview Traps

- **"Generics are erased to `any` at runtime"** — partially true but imprecise: TypeScript erases types completely; there's no `any` at runtime. Generics exist only at compile time. At runtime there's no `T`, no `any`, no `string` — just JavaScript values.

- **Confusing the `extends` constraint with inheritance** — `<T extends User>` does not mean "T inherits from User". It means "T must be structurally compatible with User", i.e., be a subtype of User. User itself also qualifies.

- **Not understanding why TypeScript infers `never` from an empty array** — `[]` is typed as `never[]` without context, because there are no elements to infer from. Fix: annotate as `const arr: string[] = []` or use an explicit parameter `createArray<string>()`.

- **Not knowing that `keyof any` = `string | number | symbol`** — so in `Record<K, V>`, the constraint `K extends keyof any` means "K can be string, number, or symbol". Without the constraint TypeScript doesn't know K can be used as an object key.

- **Assuming a generic class and a generic function work the same way** — in a class, T is fixed at `new Stack<number>()` and doesn't change for the instance. In a function, T is inferred fresh at every call site.

- **Writing `<T extends any>` instead of just `<T>`** — `extends any` constrains nothing, it's equivalent to having no constraint at all, but looks confusing. Sometimes written by mistake instead of `<T extends object>`.
