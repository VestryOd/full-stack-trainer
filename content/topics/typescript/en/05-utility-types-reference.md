<!-- verified: 2026-06-23, corrections: 0 -->
# Utility Types Reference

`Partial`, `Required`, `Readonly`, `Pick`, `Omit`, and `Record` are covered in [Generics Deep Dive] — with from-scratch implementations. This article covers the rest: function utilities, set operations, Promise utilities, lesser-known helpers, and a guide for picking the right tool.

---

## Set Operations: Exclude, Extract, NonNullable

### Exclude\<T, U\>

Removes from union T the members that are compatible with U:

```ts
type Exclude<T, U> = T extends U ? never : T;

type A = Exclude<"a" | "b" | "c", "b">;
// "a" | "c"

type B = Exclude<string | number | boolean, string | boolean>;
// number

type C = Exclude<string | null | undefined, null | undefined>;
// string — equivalent to NonNullable<string | null | undefined>
```

**When to use:** you have an existing union and need to remove specific variants without rewriting the whole type manually.

```ts
type AllEvents = "click" | "focus" | "blur" | "keydown" | "keyup";
type KeyboardEvents = Extract<AllEvents, `key${string}`>;
// "keydown" | "keyup"

type NonKeyboardEvents = Exclude<AllEvents, KeyboardEvents>;
// "click" | "focus" | "blur"
```

### Extract\<T, U\>

Keeps from T only the members that are compatible with U — the opposite of Exclude:

```ts
type Extract<T, U> = T extends U ? T : never;

type A = Extract<"a" | "b" | "c", "b" | "d">;
// "b" — only what exists in both

type B = Extract<string | number | (() => void), Function>;
// () => void — functions only
```

**Pattern: filtering by structure**

```ts
type Shape =
  | { kind: "circle"; radius: number }
  | { kind: "square"; side: number }
  | { kind: "triangle"; base: number; height: number };

// Extract only the Shape variant with a specific kind:
type Circle = Extract<Shape, { kind: "circle" }>;
// { kind: "circle"; radius: number }

// This works through structural compatibility:
// { kind: "circle"; radius: number } extends { kind: "circle" } → true
// { kind: "square"; side: number } extends { kind: "circle" } → false
```

### NonNullable\<T\>

Removes `null` and `undefined` from T:

```ts
type NonNullable<T> = T extends null | undefined ? never : T;

type A = NonNullable<string | null | undefined>; // string
type B = NonNullable<number | null>;             // number
type C = NonNullable<null>;                      // never
```

**When to use:** when you receive a type from an external source (API, library) that may be nullable, but you've already verified the value:

```ts
function assertDefined<T>(value: T): NonNullable<T> {
  if (value == null) throw new Error("Expected defined value");
  return value as NonNullable<T>;
}

const config = getConfig(); // Config | null
const safeConfig = assertDefined(config); // Config ✅
```

---

## Function Utilities: Parameters, ReturnType, ConstructorParameters, InstanceType

### Parameters\<T\>

Extracts the parameters of a function as a tuple:

```ts
type Parameters<T extends (...args: any) => any> =
  T extends (...args: infer P) => any ? P : never;

type F = (a: string, b: number, c: boolean) => void;
type P = Parameters<F>; // [string, number, boolean]

// Practical use — wrapping a function:
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

**When to use:** you need to reuse the parameter types of an existing function without duplicating them:

```ts
// A function from a library:
declare function createUser(
  name: string,
  email: string,
  role: "admin" | "user"
): User;

// A wrapper with the same parameters — no type duplication:
function createUserWithAudit(...args: Parameters<typeof createUser>): User {
  audit("createUser", args);
  return createUser(...args);
}
```

### ReturnType\<T\>

Extracts the return type of a function:

```ts
type ReturnType<T extends (...args: any) => any> =
  T extends (...args: any) => infer R ? R : never;

function fetchUser(id: number) {
  return { id, name: "Alice", email: "a@b.com" };
}

type FetchedUser = ReturnType<typeof fetchUser>;
// { id: number; name: string; email: string }
```

**Key pattern: don't duplicate types between the function and its consumers**

```ts
// ❌ Duplication — User type must be maintained in two places:
type User = { id: number; name: string; email: string };
function getUser(): User { /* ... */ }

// ✅ Type derived from the implementation:
function getUser() {
  return { id: 0, name: "", email: "" };
}
type User = ReturnType<typeof getUser>;
// Now the type and implementation are always in sync
```

**Awaited + ReturnType for async functions:**

```ts
async function fetchUser(id: number) {
  const res = await fetch(`/api/users/${id}`);
  return res.json() as Promise<{ id: number; name: string }>;
}

// ReturnType returns Promise, Awaited unwraps it:
type UserResponse = Awaited<ReturnType<typeof fetchUser>>;
// { id: number; name: string }
```

### ConstructorParameters\<T\>

The analog of `Parameters` but for class constructors:

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

// A factory with the same parameters:
function createClient(...args: ConstructorParameters<typeof HttpClient>) {
  return new HttpClient(...args);
}
```

### InstanceType\<T\>

Extracts the instance type of a class from its constructor:

```ts
type InstanceType<T extends abstract new (...args: any) => any> =
  T extends abstract new (...args: any) => infer R ? R : any;

class Service {
  process(data: string): number { return 0; }
}

type ServiceInstance = InstanceType<typeof Service>;
// Service — the same type new Service() would return

// Where it's really needed — working with a class as a value:
function createInstance<T extends new (...args: any[]) => any>(
  Ctor: T,
  ...args: ConstructorParameters<T>
): InstanceType<T> {
  return new Ctor(...args);
}

const client = createInstance(HttpClient, "https://api.example.com", 5000, {});
// client: HttpClient ✅
```

**Typical use case — dependency injection:**

```ts
type Constructor<T = object> = new (...args: any[]) => T;

function injectable<T extends Constructor>(Base: T) {
  return class extends Base {
    static dependencies: Constructor[] = [];
  };
}

function resolve<T extends Constructor>(
  Ctor: T
): InstanceType<T> {
  return new Ctor() as InstanceType<T>;
}
```

---

## Promise Utilities: Awaited

### Awaited\<T\>

Recursively unwraps Promise-like types:

```ts
type A = Awaited<Promise<string>>;           // string
type B = Awaited<Promise<Promise<number>>>;  // number — recursive!
type C = Awaited<string>;                    // string — not a Promise
type D = Awaited<Promise<string | number>>;  // string | number
```

**Implementing Awaited from scratch** (simplified version of what's in the stdlib):

```ts
type Awaited<T> =
  // null and undefined are returned as-is (not Promise)
  T extends null | undefined
    ? T
    // Check: does T have a .then method (is it thenable)?
    : T extends object & { then(onfulfilled: infer F, ...args: any[]): any }
      // If yes — extract the type of the first callback argument
      ? F extends (value: infer V, ...args: any[]) => any
        // Recursively unwrap (handles Promise<Promise<...>>):
        ? Awaited<V>
        : never
      // Not thenable — return T directly:
      : T;
```

Why such a complex implementation? TypeScript intentionally uses duck typing for "Promise-like" objects: any object with a `.then()` method is considered thenable. This is compatible with non-standard Promise implementations (Bluebird, library wrappers).

**Practical use:**

```ts
// Get the result type of an async function:
async function loadConfig(): Promise<{ host: string; port: number }> {
  return { host: "localhost", port: 3000 };
}

type Config = Awaited<ReturnType<typeof loadConfig>>;
// { host: string; port: number } ✅

// Working with arrays of Promises:
type SettledResults<T extends readonly Promise<unknown>[]> = {
  [K in keyof T]: Awaited<T[K]>;
};

type Results = SettledResults<[Promise<string>, Promise<number>]>;
// [string, number]
```

---

## Record\<K, V\> — Deeper

`Record` is built via a mapped type:

```ts
type Record<K extends keyof any, V> = { [P in K]: V };
```

`keyof any` = `string | number | symbol` — exactly what TypeScript allows as an object key.

**Usage patterns:**

```ts
// 1. Specific keys from a union:
type Status = "pending" | "active" | "closed";
type StatusConfig = Record<Status, { label: string; color: string }>;

const statusConfig: StatusConfig = {
  pending: { label: "Pending",  color: "yellow" },
  active:  { label: "Active",   color: "green"  },
  closed:  { label: "Closed",   color: "gray"   },
  // TypeScript requires all three keys and won't allow extras
};

// 2. Index signature (dynamic keys):
type Cache<V> = Record<string, V>;
// Equivalent to: { [key: string]: V }

// 3. Nested Record:
type Matrix = Record<string, Record<string, number>>;
const m: Matrix = { row1: { col1: 1, col2: 2 } };
```

**When Record is the wrong choice:**

```ts
// ❌ If keys may be absent — better use Partial<Record<...>>:
type Cache = Record<string, User>; // implies the key is ALWAYS present
const cache: Cache = {};
const user = cache["missing"]; // user: User — but actually undefined!

// ✅ Correct approach for a cache:
type Cache = Partial<Record<string, User>>;
// or:
type Cache = Record<string, User | undefined>;
const user = cache["missing"]; // user: User | undefined — honest ✅
```

---

## Lesser-Known Utilities

### ThisParameterType\<T\> and OmitThisParameter\<T\>

```ts
// Extract the type of this from a function:
function greet(this: { name: string }, greeting: string): string {
  return `${greeting}, ${this.name}`;
}

type ThisParam = ThisParameterType<typeof greet>;
// { name: string }

// Remove this from the signature:
type WithoutThis = OmitThisParameter<typeof greet>;
// (greeting: string) => string

// Application: when passing a method as a callback, bind is needed:
const alice = { name: "Alice" };
const bound = greet.bind(alice);
// bound: OmitThisParameter<typeof greet> = (greeting: string) => string
```

### ThisType\<T\>

A special marker type for `--noImplicitThis`. Used in object literals where `this` should have a specific type:

```ts
type ObjectDescriptor<D, M> = {
  data?: D;
  methods?: M & ThisType<D & M>;
  // this inside methods will be typed as D & M
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

## String Utilities (Brief Overview)

Covered in detail in [Template Literal Types]:

```ts
type U  = Uppercase<"hello">;    // "HELLO"
type L  = Lowercase<"WORLD">;    // "world"
type C  = Capitalize<"hello">;   // "Hello"
type UC = Uncapitalize<"Hello">; // "hello"

// Only work with string literals and string, not number/boolean:
type N = Uppercase<42>; // ❌ Type '42' does not satisfy the constraint 'string'
```

---

## Decision Guide: When to Reach for Each

```txt
Goal                                        Utility
──────────────────────────────────────────────────────────────────
Make all fields optional                    Partial<T>
Make all fields required                    Required<T>
Make all fields readonly                    Readonly<T>
Select a subset of fields                   Pick<T, Keys>
Exclude a subset of fields                  Omit<T, Keys>
Create an object with fixed key types       Record<Keys, V>
──────────────────────────────────────────────────────────────────
Remove types from a union                   Exclude<T, U>
Keep only matching types in a union         Extract<T, U>
Remove null and undefined                   NonNullable<T>
──────────────────────────────────────────────────────────────────
Function parameter types                    Parameters<T>
Function return type                        ReturnType<T>
Constructor parameter types                 ConstructorParameters<T>
Class instance type                         InstanceType<T>
──────────────────────────────────────────────────────────────────
Unwrap a Promise                            Awaited<T>
──────────────────────────────────────────────────────────────────
String literal case transformation          Uppercase / Lowercase /
                                            Capitalize / Uncapitalize
```

### Common Combinations

```ts
// Result type of an async function:
type Result = Awaited<ReturnType<typeof asyncFn>>;

// First parameter of a function:
type FirstArg = Parameters<typeof fn>[0];

// Make a subset of fields optional (patch/update shape):
type PatchUser = Partial<Pick<User, "name" | "email">>;

// All fields except one — readonly:
type SafeConfig = Readonly<Omit<Config, "debug">>;

// Type of Record values:
type StatusConfig = Record<Status, { label: string }>;
type StatusLabel = StatusConfig[Status]; // { label: string }
```

---

## Common Interview Traps

- **Confusing `Exclude` and `Omit`** — `Exclude` operates on union members (removes types from a union). `Omit` operates on object keys (removes fields). `Exclude<"a" | "b", "a">` = `"b"`. `Omit<User, "email">` = an object without the email field.

- **Not knowing that `Omit` is implemented via `Exclude`** — `Omit<T, K> = Pick<T, Exclude<keyof T, K>>`. Understanding this matters when you need a similar pattern.

- **Using `ReturnType` for an async function and forgetting `Awaited`** — `ReturnType<typeof asyncFn>` returns `Promise<X>`, not `X`. You need `Awaited<ReturnType<typeof asyncFn>>`.

- **Not knowing `ConstructorParameters` and `InstanceType`** — both are needed when working with classes as values (factories, DI containers, decorators). At the senior level these are required knowledge.

- **Thinking `Record<string, T>` and `{ [key: string]: T }` are fully identical** — in most contexts they're equivalent, but `Record` is a mapped type, which can produce different results with `keyof` and in conditional types.

- **Not knowing how `Awaited` is implemented** — the question "how does TypeScript know a type is a Promise?" comes up regularly. The answer: through duck typing — the presence of a `.then` method. `Awaited` doesn't check `instanceof Promise`, it checks the shape of the object.

- **Confusing `Parameters<T>[0]` with a non-existent `FirstParameter<T>`** — `FirstParameter` doesn't exist in the stdlib. The standard pattern is indexed access into the tuple: `Parameters<T>[0]`. This demonstrates understanding that `Parameters` returns a tuple, not an array.
