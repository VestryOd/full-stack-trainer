# TypeScript — Interview Questions (Senior)

## Group 1: Type System Fundamentals

**How does TypeScript's structural typing differ from nominal typing? Give an example where it matters.**

TypeScript compares type compatibility by shape (the set of fields and methods), not by name. Two classes with the same fields are compatible even if declared independently. Where this matters: `type UserId = number` and `type OrderId = number` are the same type; a function accepting `UserId` will silently accept `OrderId`. To make them incompatible, you need branded types: `type UserId = number & { readonly __brand: "UserId" }`.

---

**What is an excess property check, and why does it only trigger on object literals?**

Excess property check is an additional check that disallows extra fields when an object literal is passed directly. It is not part of structural typing — it's a separate mechanism for catching typos in field names early. It doesn't trigger when passing a variable, because a variable may be used in other places where extra fields are permitted. `const opts = { timeout: 3000, retries: 3 }; configure(opts);` — ✅, but `configure({ timeout: 3000, retries: 3 })` — ❌ if `retries` is not in the type.

---

**What is the difference between `type` and `interface` beyond syntax? When should you use each?**

Two key differences: (1) `interface` supports declaration merging — multiple declarations with the same name are automatically combined. Declaring `type` twice is an error. (2) `type` can express unions, tuples, and conditional types — `interface` cannot. Practical rule: `interface` for objects and classes (especially when module augmentation is planned), `type` for everything else — unions, tuples, mapped/conditional types.

---

**Why does `let x = "hello"` give type `string`, while `const x = "hello"` gives `"hello"`?**

TypeScript applies widening: for `let`, the variable can be reassigned (`x = "world"` is valid), so the type is widened to `string`. `const` cannot be reassigned — the value is fixed, so the type can stay literal. Same principle for object fields: `const obj = { x: "hello" }` gives `{ x: string }`, not `{ x: "hello" }`, because `obj.x = "world"` is legal. Fix: `as const`.

---

**How does TypeScript perform control flow analysis? What happens after `if (x == null) return`?**

TypeScript builds a control flow graph for every function. At each point in the graph it tracks the type of each variable, accounting for all previous checks. After `if (x == null) return`, TypeScript knows: in the code below, `x` cannot be `null` or `undefined` (because `== null` catches both). The type is narrowed — both nullish values are removed from the union. TypeScript understands the semantics of `==` (loose equality) in this specific pattern.

---

## Group 2: Generics

**Why are TypeScript generics not "templates like in C++"?**

In C++, templates are expanded at compile time into concrete code for each type. In TypeScript, a generic is a type variable that the compiler *infers* at the call site. All typing is erased at runtime — in JavaScript there is no `T`, no `string`, no `number`. More importantly: TypeScript *solves an equation* for T from the function's arguments. `identity(42)` — TypeScript sees `number → T`, infers `T = number`. This is type inference, not template expansion.

---

**What does `K extends keyof T` do, and why use it instead of just `string`?**

`K extends keyof T` constrains K to the keys of a specific object T. Using just `K extends string` allows any string, including non-existent keys. With `K extends keyof T` TypeScript guarantees the key exists and infers the precise value type `T[K]`. The function `getProperty<T, K extends keyof T>(obj: T, key: K): T[K]` — calling `getProperty(user, "name")` infers `K = "name"` and the return type `string`, not `unknown`.

---

**What is the difference between a generic function and a generic class in terms of type inference?**

In a generic function, the type parameter `T` is inferred fresh at every call site: `wrap("hello")` → `T = string`, `wrap(42)` → `T = number`. In a generic class, `T` is fixed at instantiation — `new Stack<number>()` fixes `T = number` for the entire instance, and `stack.push("hello")` is an error. Different instances can have different `T`: `new Stack<string>()` and `new Stack<number>()` are independent types.

---

**Implement `Awaited<T>` from scratch. Why doesn't it just check `instanceof Promise`?**

```ts
type Awaited<T> =
  T extends null | undefined ? T :
  T extends object & { then(onfulfilled: infer F, ...args: any[]): any }
    ? F extends (value: infer V, ...args: any[]) => any
      ? Awaited<V>
      : never
    : T;
```
Not `instanceof` because TypeScript uses duck typing: any object with a `.then()` method is considered thenable. This is compatible with non-standard Promise implementations (Bluebird, custom wrappers). `instanceof Promise` is a runtime check that doesn't work at the type level. Recursion is needed for `Promise<Promise<T>>`.

---

**What happens when you call `pair(1, "hello")` if the signature is `function pair<T>(a: T, b: T): [T, T]`?**

TypeScript will infer `T = string | number` — the least common supertype. Both arguments satisfy `string | number`. Result: `[string | number, string | number]`. This is often not what you want. The correct approach: `function pair<A, B>(a: A, b: B): [A, B]` — two independent type parameters.

---

## Group 3: Conditional and Mapped Types

**What are distributive conditional types? Why is `IsString<string | number>` = `boolean` and not `false`?**

When a conditional type is applied to a bare type parameter `T`, TypeScript distributes it over the union members: `IsString<string | number>` → `IsString<string> | IsString<number>` → `true | false` → `boolean`. This is distributivity. To treat the union as a whole (non-distributively): wrap in a tuple `[T] extends [string]`. Special case: `T extends never` never equals `true` — use `[T] extends [never]` instead.

---

**Explain `infer` with an example. How do you extract the type inside a Promise?**

`infer R` creates a type variable R that TypeScript fills in during pattern matching:
```ts
type UnwrapPromise<T> = T extends Promise<infer R> ? R : T;
type A = UnwrapPromise<Promise<string>>; // string
type B = UnwrapPromise<number>;          // number
```
`infer` only works inside the `extends` branch of a conditional type — it is not a new generic parameter declaration, it's extraction during pattern matching. It can be used in multiple positions: `T extends (arg: infer A) => infer R` extracts both the argument type and the return type.

---

**Implement `Omit<T, K>` from scratch using `Pick` and `Exclude`.**

```ts
type Omit<T, K extends keyof T> = Pick<T, Exclude<keyof T, K>>;
// Exclude<"id" | "name" | "email", "email"> = "id" | "name"
// Pick<User, "id" | "name"> = { id: number; name: string }
```
`Exclude` removes the unwanted keys from the union, `Pick` builds an object from what remains. The chain: `keyof T` → union of keys → `Exclude` removes K → `Pick` builds the object. Understanding this chain demonstrates knowledge of mapped type mechanics.

---

**What does `[K in keyof T as K extends string ? K : never]` do?**

This is key remapping via `as` (TypeScript 4.1+). `K in keyof T` iterates over all keys of T (including `number` and `symbol`). `as K extends string ? K : never` renames each key: if K is a string — keep K, otherwise return `never`. Keys mapped to `never` are excluded from the resulting type. This is key filtering by type — the equivalent of `filter` for object fields.

---

**How would you implement `PickByValue<T, V>` — select only fields with a specific value type?**

```ts
type PickByValue<T, V> = {
  [K in keyof T as T[K] extends V ? K : never]: T[K];
};

type User = { id: number; name: string; age: number; active: boolean };
type StringFields = PickByValue<User, string>; // { name: string }
type NumberFields = PickByValue<User, number>; // { id: number; age: number }
```
Key: `T[K] extends V ? K : never` — checking the value type, not the key. Return K if it matches, `never` (exclude) if it doesn't.

---

## Group 4: Template Literal Types

**How do you generate all CSS properties `margin-top`, `margin-right`, etc. with template literal types?**

```ts
type Direction = "top" | "right" | "bottom" | "left";
type MarginProperty = `margin-${Direction}`;
// "margin-top" | "margin-right" | "margin-bottom" | "margin-left"
```
TypeScript cross-multiplies all combinations when a union is substituted into an interpolation slot. Two unions are multiplied: `${A | B}-${C | D}` = `"A-C" | "A-D" | "B-C" | "B-D"`. With a very large number of combinations TypeScript throws "Expression produces a union type that is too complex to represent".

---

**Write a type that extracts parameters from the path `/users/:id/posts/:postId`.**

```ts
type ExtractParams<Path extends string> =
  Path extends `${string}:${infer Param}/${infer Rest}`
    ? Param | ExtractParams<`/${Rest}`>
    : Path extends `${string}:${infer Param}`
    ? Param
    : never;

type P = ExtractParams<"/users/:id/posts/:postId">; // "id" | "postId"
```
The pattern is recursive: extract the first parameter up to `/`, then apply the type to the rest of the string. Without recursion you can't handle an arbitrary number of parameters.

---

## Group 5: Utility Types

**What is the difference between `Exclude` and `Omit`? A common source of confusion.**

`Exclude<T, U>` — works with union types, removes from T the members compatible with U: `Exclude<"a" | "b" | "c", "b">` = `"a" | "c"`. `Omit<T, K>` — works with object keys, removes fields: `Omit<User, "email">` = object without the email field. `Omit` is actually implemented via `Exclude`: `Omit<T, K> = Pick<T, Exclude<keyof T, K>>`. Classic mistake: applying `Exclude` to an object or `Omit` to a union.

---

**When is `InstanceType<T>` necessary? When can't you avoid it?**

`InstanceType<T>` extracts the instance type from a class constructor. Needed when a class is passed as a value (not instantiated directly):
```ts
function createInstance<T extends new (...args: any[]) => any>(
  Ctor: T, ...args: ConstructorParameters<T>
): InstanceType<T> {
  return new Ctor(...args);
}
```
Without `InstanceType`, the return type would be `{}` or `object` — losing information about the specific class. Used in DI containers, factories, and decorators.

---

**How do you get the result type of an async function (without the Promise wrapper)?**

```ts
async function fetchUser() {
  return { id: 1, name: "Alice" };
}

type User = Awaited<ReturnType<typeof fetchUser>>;
// { id: number; name: string }
```
`ReturnType` returns `Promise<{ id: number; name: string }>`. `Awaited` recursively unwraps the Promise. The combination `Awaited<ReturnType<typeof fn>>` is the standard pattern for getting the data type from an async function.

---

## Group 6: Type Narrowing and Guards

**Why can't TypeScript narrow the type through a custom function without `is`?**

Without `is`, TypeScript only sees that the function returns `boolean`. It doesn't analyze the function body to understand the semantic of the check — that would be too expensive and imprecise. With `value is string`, the developer explicitly tells the compiler: "if this function returned `true` — narrow the type of `value` to `string` in the calling code." This is a contract TypeScript accepts on faith — it does not verify the correctness of the guard body.

---

**What is the difference between `asserts value is T` and `value is T`? When to use each?**

`value is T` — returns `boolean`, used in an `if` condition. Narrowing applies only inside the `if` branch. `asserts value is T` — returns `void`, throws an exception if the condition fails. After the call the type is already narrowed in the code below, with no `if` needed. Use `value is T` when you need branching logic. Use `asserts value is T` when the value must conform to the type, otherwise execution should not continue (validation function, precondition check).

---

**What is exhaustiveness checking and how do you implement it?**

The pattern guarantees all variants of a discriminated union are handled. Implementation:
```ts
function assertNever(value: never): never {
  throw new Error(`Unhandled case: ${JSON.stringify(value)}`);
}

switch (shape.kind) {
  case "circle": return ...;
  case "square": return ...;
  default: return assertNever(shape); // ❌ compile error if new variant added without a case
}
```
Adding a new variant to the union without a corresponding `case` — TypeScript errors: "Argument of type '{ kind: "rectangle" }' is not assignable to parameter of type 'never'". Compile-time protection against forgotten branches.

---

**Why is `typeof null === "object"` a trap in TypeScript? What's the correct check for an object?**

`typeof null` in JavaScript historically returns `"object"` — a known spec bug left unfixed for backward compatibility. TypeScript doesn't hide this: after `typeof value === "object"`, the type narrows to `object | null`. Correct check: `typeof value === "object" && value !== null`. Without the second condition `null` remains in the type.

---

**Why are discriminated unions better than an object with optional fields?**

Optional fields allow invalid combinations: `{ data?: User; error?: Error; loading?: boolean }` — TypeScript accepts `{ data: user, error: err }` (what does this mean?). A discriminated union makes invalid states inexpressible:
```ts
type State =
  | { status: "success"; data: User }
  | { status: "error"; error: Error }
  | { status: "loading" };
```
It's impossible to create `{ status: "success"; error: err }`. TypeScript narrows the type via the discriminant. Exhaustiveness checking works automatically through switch.

---

## Group 7: Variance and Assertions

**Why are function parameters contravariant? Explain with an example.**

A function with a wider parameter is safe where a function with a narrower parameter is expected:
```ts
type CatHandler = (cat: Cat) => void;
const handler: CatHandler = (animal: Animal) => { animal.name }; // ✅
```
Why: we will call `handler` with a `Cat`, and the function accepts an `Animal` — Cat IS-A Animal, everything Animal has, Cat has. The other direction is unsafe: if we promise to accept an `Animal` but call `cat.meow()` — Animal might not have that method. Contravariance reverses the direction: `(Animal) → void` is a subtype of `(Cat) → void`.

---

**Why are methods in TypeScript bivariant even with `strictFunctionTypes`?**

`strictFunctionTypes` applies contravariant checking only to function-typed properties (`handleFn: (v: T) => void`), not to methods (`handle(v: T): void`). This is a historical decision for compatibility: strict contravariance for methods would break too much real-world code (especially patterns like `Array.prototype.forEach`). To get correct contravariance — use a function property instead of a method.

---

**What is the difference between `satisfies`, an explicit annotation, and `as`?**

- Explicit annotation (`const x: Config = value`) — changes the type of `x` to `Config`, precise field types are lost.
- `satisfies` (`const x = value satisfies Config`) — checks compatibility with `Config` but the type remains inferred: fields keep their precise types (e.g. `"localhost"` instead of `string`).
- `as` (`const x = value as Config`) — does not check compatibility at all, just asserts the type. `{ port: 3000 } as Config` — no error, even though `host` is missing.
For configs: `as const satisfies Config` — get both readonly literal types and a compatibility check.

---

**When is `as` acceptable, and when is it a sign of an architectural problem?**

Acceptable: DOM API (`document.querySelector("canvas") as HTMLCanvasElement` — TypeScript doesn't know the specific element type), `JSON.parse` (returns `any` by nature), `Object.keys(...) as Array<keyof typeof obj>`, third-party libraries with poor types. Sign of a problem: `return {} as User` (bypassing types instead of a correct implementation), `value as any` (losing all guarantees), `as` instead of a type guard (hiding that a check is needed). Double assertion `as unknown as T` is almost always an architectural problem.

---

## Group 8: Declaration Files and Modules

**How does a `.d.ts` file differ from a `.ts` file that contains only types?**

A `.d.ts` file is never compiled to JavaScript — TypeScript treats it as purely declarative. It describes ambient environments: global variables, third-party libraries, module augmentation. A `.ts` file with only types compiles to an empty `.js` (or a file with imports). `declare global`, `declare module`, and ambient module declarations require the `.d.ts` context (or the `declare` keyword in `.ts`).

---

**How do you extend the `Request` type from Express to add a `user` field?**

```ts
// src/types/express.d.ts
import "express";

declare module "express-serve-static-core" {
  interface Request {
    user?: { id: number; role: string };
  }
}
```
Important: you must augment `"express-serve-static-core"`, not `"express"` — that's where the `Request` interface is defined. Find the right module by reading `node_modules/@types/express/index.d.ts`. Without `import "express"` the file may not function as a module, and the merging won't take effect.

---

**Why is `export {}` important in a `.d.ts` file that uses `declare global`?**

Without `export {}` TypeScript treats the file as a script (not a module) — all declarations are automatically global without `declare global {}`. With `export {}` the file becomes a module, and an explicit `declare global {}` block is needed to extend the global scope. Without this distinction, declarations behave unpredictably: either everything is global (undesirable in a modular architecture), or nothing (if TypeScript decides the file is a module but `declare global` wasn't written).

---

**In which cases is `namespace` still justified in modern TypeScript?**

Three cases: (1) Ambient declarations for global libraries loaded via `<script>` (jQuery, legacy SDKs): `declare namespace jQuery { ... }`. (2) Grouping types inside a `.d.ts` file: `declare namespace API { interface User {...} }` — convenient organization without creating file-level modules. (3) Merging with enum or function to add static methods. In regular `.ts` code — use ES modules.

---

## Group 9: Advanced Patterns

**What are branded types? How do they work without runtime overhead?**

A branded type adds a fictitious marker field that makes types structurally incompatible:
```ts
type UserId = number & { readonly __brand: "UserId" };
```
The `__brand` field exists only in the TypeScript type. When compiled, `type UserId = number & { __brand: "UserId" }` is erased — in JavaScript this is just a `number`. No wrapper object, no runtime checks. Creating a value: `const id = 42 as UserId` — `as` bypasses the structural check for initialization.

---

**How does a phantom type differ from a branded type?**

Branded type: a marker field in the type itself (`T & { __brand: ... }`). Phantom type: an unused generic parameter (`type FormData<TState> = { name: string } & { __state: TState }`). The goal is similar — add a compile-time distinction without runtime changes. Phantom types are more convenient for encoding state (Validated/Unvalidated); branded types — for distinguishing identically-typed primitives (UserId vs OrderId). Both approaches work without runtime overhead.

---

**How do you implement a recursive type for JSON values?**

```ts
type JSONPrimitive = string | number | boolean | null;
type JSONObject    = { [key: string]: JSONValue };
type JSONArray     = JSONValue[];
type JSONValue     = JSONPrimitive | JSONObject | JSONArray;
```
Recursion works through indirection: `JSONValue` references `JSONObject` and `JSONArray`, which in turn use `JSONValue`. Direct recursion to a primitive doesn't work. Limit: recursion depth ~100 levels. For truly large JSON structures, runtime validation (Zod) is needed.

---

**When should type-level programming be replaced with runtime validation?**

TypeScript checks types only at compile time — at runtime there are no types. If data comes from outside (`req.body`, `JSON.parse`, `localStorage`), TypeScript types guarantee nothing. `const user = req.body as User` is false security. When you need value constraints (email format, positive number, non-empty string) — types are powerless, a runtime validator is needed (Zod, Yup, io-ts). Rule: type-level for compile-time guarantees and DX; runtime validation for system boundaries (HTTP, files, env).

---

## Group 10: Compiler and Configuration

**What is included in `"strict": true`? Name at least 4 flags and what each catches.**

`strict` enables 8 flags: `strictNullChecks` (null/undefined not assignable to other types), `noImplicitAny` (disallow implicit any for parameters and variables), `strictFunctionTypes` (contravariant function parameter checking), `strictBindCallApply` (type-safe .bind/.call/.apply), `strictPropertyInitialization` (class fields must be initialized in constructor), `noImplicitThis` (this cannot be any), `alwaysStrict` ("use strict" in all files), `useUnknownInCatchVariables` (catch variable is unknown, not any).

---

**How does `moduleResolution: "bundler"` differ from `"node16"`?**

`node16` reflects real Node.js ESM behavior: requires explicit extensions in relative imports (`./utils.js`); TypeScript finds `utils.ts` when it sees the import `"./utils.js"`. `bundler` is designed for projects with webpack/vite/esbuild: extensions are optional (the bundler handles resolution), supports `package.json` exports. `bundler` is more convenient for frontend — no need to write `.js` extensions in TypeScript imports. `node16` is required for publishing ESM libraries under Node.js.

---

**What is `isolatedModules` and why does it disallow `const enum`?**

`isolatedModules: true` requires each file to be compilable independently, without cross-file analysis. Mandatory for Babel/esbuild/SWC — they transpile one file at a time. `const enum` is incompatible because resolving its values requires access to other files: `Direction.Up` is replaced with `0` only by knowing the `Direction` definition. In single-file compilation — this is impossible. Replacement: a plain `enum` or an `as const` object.

---

**What is the difference between `target` and `lib` in tsconfig?**

`target` controls syntactic transforms: `arrow functions → function`, `class → prototype`, `async/await → Promise-chain`, etc. `lib` defines which APIs TypeScript "knows about": `Array.prototype.at`, `Promise.allSettled`, `structuredClone`. You can have `target: "es5"` (generate ES5 syntax) and `lib: ["es2022"]` (know modern APIs, provided by a polyfill). Common mistake: adding `lib: ["es2022"]` and thinking TypeScript will add the polyfill — no, it only adds the types.

---

**Why isn't `noUncheckedIndexedAccess` included in `strict` even though it's very useful?**

`noUncheckedIndexedAccess` adds `| undefined` to all index access results: `arr[0]` returns `T | undefined` instead of `T`. This is more correct, but breaks enormous amounts of existing code — guards need to be added everywhere. The TypeScript team decided not to include it in `strict` for backward compatibility reasons. For new projects — recommended to enable explicitly. Catches a typical bug: `const first = arr[0]; first.toFixed()` — crash if the array is empty.

---

**What does `skipLibCheck: true` do and what are its risks?**

`skipLibCheck: true` skips type checking on all `.d.ts` files, including `node_modules/@types/**`. Benefits: eliminates type conflicts between incompatible versions of `@types/*` packages, speeds up compilation. Risks: hides real incompatibilities between dependencies; errors in a library's `.d.ts` that affect your code go undetected. Practice: `skipLibCheck: true` is near-universal — but understanding what is "being skipped" and that it's a trade-off, not a free optimization, is what separates seniors from others.

---

## Group 11: Type Safety in Architecture

**How do TypeScript types help follow the principle "make invalid states unrepresentable"?**

Discriminated unions encode state so invalid combinations cannot be expressed in types:
```ts
// ❌ Can create { loading: true, data: user, error: err }:
type State = { loading: boolean; data?: User; error?: Error };

// ✅ Invalid states are inexpressible:
type State =
  | { status: "loading" }
  | { status: "success"; data: User }
  | { status: "error"; error: Error };
```
Branded types make mixing up semantically similar values a compile error. Phantom types encode processing stages (Unvalidated → Validated). The goal: move checks from runtime to compile time.

---

**How do you type a function whose return type depends on the input parameter?**

Three approaches from simple to complex: (1) Overloads — duplication, but readable error messages. (2) Conditional return type: `function process<T extends string | number>(v: T): T extends string ? string : number`. (3) Generic with `extends` constraint — often sufficient. Conditional types are preferred for library code; overloads — when error message readability matters. TypeScript often can't infer a conditional return type inside the function body — a cast with `as` is frequently needed.

---

**What is `Readonly<T>` and why doesn't `const` on an object make it readonly?**

`const` prevents reassigning the variable, but not mutating its fields: `const obj = { x: 1 }; obj.x = 2; // ✅`. `Readonly<T>` makes all object fields `readonly` at the type level — any attempt to assign to a field is caught by TypeScript. `as const` does the same recursively, with literal types. Important: `Readonly` is a compile-time constraint. `Object.freeze()` is runtime. For deep immutability you need `DeepReadonly`.

---

**Explain the "const enum alternative" pattern with `as const`.**

```ts
// Problem with enum: compiles to an object in JS, doesn't work with isolatedModules:
enum Status { Pending = "PENDING", Active = "ACTIVE" }

// Alternative:
const Status = {
  Pending: "PENDING",
  Active: "ACTIVE",
} as const;

type Status = typeof Status[keyof typeof Status];
// "PENDING" | "ACTIVE"
```
Advantages: works with `isolatedModules`, tree-shakeable, no `const enum` resolution issues, type is derived from the values. `typeof Status[keyof typeof Status]` — the standard pattern for a union from the values of an `as const` object.

---

**How does TypeScript handle `process.env.NODE_ENV` — why is the type `string | undefined` instead of a specific union?**

By default, `process.env` is typed as `NodeJS.ProcessEnv`: `{ [key: string]: string | undefined }`. TypeScript doesn't know which variables are set in a specific environment. To get a precise type — extend the interface:
```ts
declare namespace NodeJS {
  interface ProcessEnv {
    NODE_ENV: "development" | "production" | "test";
    DATABASE_URL: string;
  }
}
```
After this, `process.env.NODE_ENV` is `"development" | "production" | "test"`, and `process.env.TYPO` is a compile error. This is module augmentation via declaration merging.
