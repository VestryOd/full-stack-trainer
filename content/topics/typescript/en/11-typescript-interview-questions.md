# TypeScript — Interview Questions (Senior)

## Group 1: Type System Fundamentals

**How does TypeScript's structural typing differ from nominal typing? Give an example where it matters.**

TypeScript compares types by shape — the set of fields and methods — and ignores the name.

```txt
Structural (TypeScript, Go):
  Two classes with the same fields are compatible,
  even when declared independently.

Nominal (Java, C#, Rust):
  A Cat is only what was declared as Cat.
```

Where it matters: `type UserId = number` and `type OrderId = number` are the same type. A function taking `UserId` silently accepts `OrderId`. To split them you need branded types: `type UserId = number & { readonly __brand: "UserId" }`.

---

**What is an excess property check, and why does it only trigger on object literals?**

It is an extra check that disallows unknown fields when an object literal is passed directly.

```ts
interface Options { timeout: number }
declare function configure(o: Options): void;

// ❌ Object literal may only specify known properties,
//    and 'retries' does not exist in type 'Options'
configure({ timeout: 3000, retries: 3 });

// ✅ Via a variable the check does not run:
const opts = { timeout: 3000, retries: 3 };
configure(opts);
```

The check is not part of structural typing. It is a separate mechanism for catching typos in field names early. Passing a variable skips it, because that variable may be used in other places where the extra fields are wanted.

---

**What is the difference between `type` and `interface` beyond syntax? When should you use each?**

Two differences matter: `interface` merges across declarations, and `type` alone can express unions and tuples.

| | `interface` | `type` |
|---|---|---|
| Declared twice | merges into one | `Duplicate identifier` |
| Union, tuple | cannot express | can express |
| Mapped, conditional | cannot express | can express |

Practical rule: `interface` for objects and classes, especially when module augmentation is planned. Use `type` for everything else — unions, tuples, mapped and conditional types.

---

**Why does `let x = "hello"` give type `string`, while `const x = "hello"` gives `"hello"`?**

Because `let` can be reassigned, TypeScript widens its type; `const` cannot, so the literal type survives.

```ts
let x = "hello";    // x: string — x = "world" must stay legal
const c = "hello";  // c: "hello" — the value is fixed

const obj = { x: "hello" };
// obj: { x: string } — obj.x = "world" is legal, so the field widens

const fixed = { x: "hello" } as const;
// fixed: { readonly x: "hello" } — no widening
```

This is called widening. Object fields widen even under `const`, because the field itself is still assignable. The fix is `as const`.

---

**How does TypeScript perform control flow analysis? What happens after `if (x == null) return`?**

TypeScript builds a control flow graph for every function and tracks the type of each variable at every point in it.

```ts
function f(x: string | number | null | undefined) {
  if (x == null) return;
  // x: string | number — both null and undefined are gone,
  // because == null catches the two of them at once
  return typeof x === "string" ? x.toUpperCase() : x.toFixed(2);
}
```

Each point in the graph accounts for every check before it. TypeScript understands the semantics of `==` (loose equality) in this specific pattern, which is why one check removes two members from the union.

---

## Group 2: Generics

**Why are TypeScript generics not "templates like in C++"?**

A C++ template is expanded into concrete code for each type. A TypeScript generic is only a type variable, which the compiler infers at the call site.

```ts
function identity<T>(value: T): T { return value; }

identity(42);      // TypeScript solves number → T, so T = number
identity("hi");    // T = string
// Compiled JS: function identity(value) { return value; }
// No T, no string, no number — all typing is erased
```

TypeScript *solves an equation* for `T` from the arguments. That is type inference, not template expansion. Nothing about `T` survives into the JavaScript output.

---

**What does `K extends keyof T` do, and why use it instead of just `string`?**

It constrains `K` to the keys of one specific object `T`, so the key is guaranteed to exist.

```ts
function getProperty<T, K extends keyof T>(obj: T, key: K): T[K] {
  return obj[key];
}

const user = { name: "Alice", age: 30 };
getProperty(user, "name");  // K = "name", return type string
getProperty(user, "typo");  // ❌ Argument of type '"typo"' is not
                            //    assignable to parameter of type
                            //    '"name" | "age"'
```

With `K extends string` any string is accepted, including keys that do not exist. With `K extends keyof T` TypeScript also infers the precise value type `T[K]` instead of `unknown`.

---

**What is the difference between a generic function and a generic class in terms of type inference?**

In a function `T` is inferred fresh at every call; in a class `T` is fixed once, at instantiation.

```ts
declare function wrap<T>(v: T): T[];
wrap("hello");  // T = string
wrap(42);       // T = number — inferred again, per call

const s = new Stack<number>(); // T = number for this whole instance
s.push("hello");               // ❌ Argument of type 'string' is not
                               //    assignable to parameter 'number'
```

Different instances can hold different `T`. `Stack<string>` and `Stack<number>` are independent types.

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

Not `instanceof`, because TypeScript uses duck typing: any object with a `.then()` method counts as thenable. That keeps it compatible with non-standard Promise implementations such as Bluebird and custom wrappers. Checking `instanceof Promise` is a runtime test, and it does not work at the type level. The recursion is what handles `Promise<Promise<T>>`.

---

**What happens when you call `pair(1, "hello")` if the signature is `function pair<T>(a: T, b: T): [T, T]`?**

It does not compile. Inference fixes `T` from the first argument and then rejects the second.

```ts
declare function pair<T>(a: T, b: T): [T, T];

pair(1, "hello");
// error TS2345: Argument of type 'string' is not assignable
//    to parameter of type 'number'.

pair<string | number>(1, "hello"); // [string | number, string | number] ✅

// Two independent parameters keep both types exact:
declare function pair2<A, B>(a: A, b: B): [A, B];
pair2(1, "hello"); // [number, string] ✅
```

One `T` can only be one type, and inference takes it from the first candidate instead of building a union. Name the union yourself, or use two type parameters.

---

## Group 3: Conditional and Mapped Types

**What are distributive conditional types? Why is `IsString<string | number>` = `boolean` and not `false`?**

Because a conditional type applied to a bare type parameter is distributed over each member of the union.

```ts
type IsString<T> = T extends string ? true : false;

type A = IsString<string | number>;
// IsString<string> | IsString<number> = true | false = boolean

// Wrap in a tuple to treat the union as one whole:
type IsStringNonDist<T> = [T] extends [string] ? true : false;
type B = IsStringNonDist<string | number>; // false
```

That spreading is distributivity. One special case: `T extends never` is never `true`, because there is nothing to distribute over — use `[T] extends [never]` instead.

---

**Explain `infer` with an example. How do you extract the type inside a Promise?**

`infer R` declares a type variable that TypeScript fills in while matching a pattern.

```ts
type UnwrapPromise<T> = T extends Promise<infer R> ? R : T;
type A = UnwrapPromise<Promise<string>>; // string
type B = UnwrapPromise<number>;          // number
```

`infer` only works inside the `extends` branch of a conditional type. It is not a new generic parameter, it is extraction during pattern matching. It can appear in several positions at once: `T extends (arg: infer A) => infer R` extracts the argument type and the return type together.

---

**Implement `Omit<T, K>` from scratch using `Pick` and `Exclude`.**

```ts
type Omit<T, K extends keyof T> = Pick<T, Exclude<keyof T, K>>;
// Exclude<"id" | "name" | "email", "email"> = "id" | "name"
// Pick<User, "id" | "name"> = { id: number; name: string }
```

`Exclude` removes the unwanted keys from the union and `Pick` builds an object from what remains. The chain is short: `keyof T` gives a union of keys, `Exclude` drops `K`, `Pick` rebuilds the object.

---

**What does `[K in keyof T as K extends string ? K : never]` do?**

It is key remapping (TypeScript 4.1+): the `as` clause renames each key, and keys renamed to `never` disappear.

```ts
type OnlyStringKeys<T> = {
  [K in keyof T as K extends string ? K : never]: T[K];
};

const sym = Symbol("s");
type Mixed = { name: string; 42: boolean; [sym]: number };
type Result = OnlyStringKeys<Mixed>; // { name: string }
```

`K in keyof T` iterates over every key of `T`, including `number` and `symbol` keys. So this is key filtering by type — the equivalent of `filter` for object fields.

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

The key detail is `T[K] extends V ? K : never`: the test looks at the value type, not the key. A match returns `K`, a mismatch returns `never` and drops the field.

---

## Group 4: Template Literal Types

**How do you generate all CSS properties `margin-top`, `margin-right`, etc. with template literal types?**

```ts
type Direction = "top" | "right" | "bottom" | "left";
type MarginProperty = `margin-${Direction}`;
// "margin-top" | "margin-right" | "margin-bottom" | "margin-left"
```

TypeScript cross-multiplies every combination when a union lands in an interpolation slot. Two unions multiply out: `${A | B}-${C | D}` gives `"A-C" | "A-D" | "B-C" | "B-D"`. Past a certain size TypeScript refuses with "Expression produces a union type that is too complex to represent".

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

The pattern is recursive: take the first parameter up to `/`, then apply the type again to the rest of the string. Without recursion you cannot handle an arbitrary number of parameters.

---

## Group 5: Utility Types

**What is the difference between `Exclude` and `Omit`? A common source of confusion.**

`Exclude` filters members out of a union; `Omit` removes fields from an object type.

| | Operates on | Example | Result |
|---|---|---|---|
| `Exclude<T, U>` | union members | `Exclude<"a" \| "b" \| "c", "b">` | `"a" \| "c"` |
| `Omit<T, K>` | object keys | `Omit<User, "email">` | `User` without `email` |

`Omit` is actually built on `Exclude`: `Omit<T, K> = Pick<T, Exclude<keyof T, K>>`. The classic mistake is swapping them — applying `Exclude` to an object, or `Omit` to a union.

---

**When is `InstanceType<T>` necessary? When can't you avoid it?**

`InstanceType<T>` extracts the instance type from a class constructor, which you need whenever a class is passed around as a value.

```ts
function createInstance<T extends new (...args: any[]) => any>(
  Ctor: T, ...args: ConstructorParameters<T>
): InstanceType<T> {
  return new Ctor(...args);
}
```

Without `InstanceType` the return type would collapse to `{}` or `object`, losing the specific class. This shows up in factories, decorators, and DI containers. DI is dependency injection, where a container constructs your classes for you.

---

**How do you get the result type of an async function (without the Promise wrapper)?**

```ts
async function fetchUser() {
  return { id: 1, name: "Alice" };
}

type User = Awaited<ReturnType<typeof fetchUser>>;
// { id: number; name: string }
```

`ReturnType` alone gives `Promise<{ id: number; name: string }>`, and `Awaited` unwraps it recursively. The combination `Awaited<ReturnType<typeof fn>>` is the standard way to name the data type behind an async function.

---

## Group 6: Type Narrowing and Guards

**Why can't TypeScript narrow the type through a custom function without `is`?**

Without `is` the compiler only sees that the function returns `boolean`, and it never reads the body to guess what was checked.

```ts
// ❌ Without is — the return type is just boolean:
function isStringPlain(v: unknown): boolean {
  return typeof v === "string";
}
const a: unknown = "hi";
if (isStringPlain(a)) a.toUpperCase(); // ❌ 'a' is of type 'unknown'

// ✅ With is — the developer states the contract:
function isString(v: unknown): v is string {
  return typeof v === "string";
}
if (isString(a)) a.toUpperCase(); // ✅ a: string
```

Analysing the body would be expensive and imprecise, so TypeScript takes the predicate on faith. It never verifies that the guard body is correct.

---

**What is the difference between `asserts value is T` and `value is T`? When to use each?**

`value is T` returns a `boolean` you branch on; `asserts value is T` returns `void` and throws, narrowing everything after the call.

```ts
function isString(v: unknown): v is string {
  return typeof v === "string";
}
function assertString(v: unknown): asserts v is string {
  if (typeof v !== "string") throw new Error("not a string");
}

if (isString(x)) x.toUpperCase(); // narrowed inside the branch only

assertString(y);
y.toUpperCase(); // narrowed from here on, no if needed
```

Use `value is T` when you need branching logic. Use `asserts value is T` when the value must conform and execution should stop otherwise — a validation function or a precondition check.

---

**What is exhaustiveness checking and how do you implement it?**

It is a pattern that makes the compiler prove every variant of a discriminated union is handled.

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

Add a variant to the union without a matching `case`, and the `default` branch stops compiling. That is compile-time protection against forgotten branches.

---

**Why is `typeof null === "object"` a trap in TypeScript? What's the correct check for an object?**

Because `typeof null` returns `"object"` in JavaScript, so the check narrows to `object | null` rather than `object`.

```ts
function bad(v: unknown) {
  if (typeof v === "object") {
    // v: object | null — null is still here!
  }
}

function good(v: unknown) {
  if (typeof v === "object" && v !== null) {
    // v: object ✅
  }
}
```

This is a known bug in the specification, left unfixed for backward compatibility. TypeScript does not hide it, so without the second condition `null` stays in the type.

---

**Why are discriminated unions better than an object with optional fields?**

Because optional fields let you build states that make no sense, while a discriminated union makes them unrepresentable.

```ts
// ❌ TypeScript accepts { data: user, error: err } — what does that mean?
type Bad = { data?: User; error?: Error; loading?: boolean };

// ✅ Invalid combinations cannot be written:
type State =
  | { status: "success"; data: User }
  | { status: "error"; error: Error }
  | { status: "loading" };
```

You cannot create `{ status: "success"; error: err }`. TypeScript narrows through the discriminant, and exhaustiveness checking then works automatically in a `switch`.

---

## Group 7: Variance and Assertions

**Why are function parameters contravariant? Explain with an example.**

Because a function with a wider parameter is safe wherever a function with a narrower parameter is expected.

```ts
type CatHandler = (cat: Cat) => void;
const handler: CatHandler = (animal: Animal) => { animal.name }; // ✅
```

We will only ever call `handler` with a `Cat`, and the function accepts any `Animal` — a Cat has everything an Animal has. The other direction is unsafe: promising to accept an `Animal` and then calling `cat.meow()` breaks, because an Animal may not have that method. So contravariance reverses the direction: `(Animal) => void` is a subtype of `(Cat) => void`.

---

**Why are methods in TypeScript bivariant even with `strictFunctionTypes`?**

Because `strictFunctionTypes` only applies contravariant checking to function-typed properties, never to methods.

```ts
interface Handler<T> {
  // method — still bivariant, even with strictFunctionTypes
  handle(value: T): void;
  // function property — contravariant, checked correctly
  handleFn: (value: T) => void;
}
```

This is a historical decision made for compatibility: strict contravariance on methods would break too much real-world code, especially patterns like `Array.prototype.forEach`. To get correct contravariance, declare a function property instead of a method.

---

**What is the difference between `satisfies`, an explicit annotation, and `as`?**

All three relate a value to a type, but only `satisfies` both checks the value and keeps its inferred type.

| Form | Checks compatibility | Resulting type of `x` |
|---|---|---|
| `const x: Config = value` | yes | `Config` — precise field types lost |
| `const x = value satisfies Config` | yes | inferred — `"localhost"`, not `string` |
| `const x = value as Config` | no | `Config`, asserted without any check |

`as` skips the check entirely: `{ port: 3000 } as Config` raises no error even though `host` is missing. For configs use `as const satisfies Config`, which gives readonly literal types and a compatibility check together.

---

**When is `as` acceptable, and when is it a sign of an architectural problem?**

`as` is acceptable where you genuinely know more than the compiler, and a problem where it papers over missing work.

```ts
// ✅ Acceptable — TypeScript cannot know the element type:
const c = document.querySelector("canvas") as HTMLCanvasElement;
const data = JSON.parse(raw) as Config;  // JSON.parse returns any
const keys = Object.keys(obj) as Array<keyof typeof obj>;

// ❌ A sign of a problem:
return {} as User;      // bypassing types instead of implementing
const v = value as any; // every guarantee is gone
const u = raw as unknown as User; // double assertion
```

The acceptable cases are the DOM API, `JSON.parse`, `Object.keys`, and third-party libraries with poor types. DOM is the document object model, the browser's object tree for a page. Using `as` in place of a type guard hides the fact that a real check is needed. A double assertion `as unknown as T` is almost always an architectural problem.

---

## Group 8: Declaration Files and Modules

**How does a `.d.ts` file differ from a `.ts` file that contains only types?**

A `.d.ts` file is never compiled to JavaScript; TypeScript treats it as purely declarative.

```txt
.d.ts   →  no output at all; describes an ambient environment:
           global variables, third-party libraries, augmentation

.ts     →  always produces output; a types-only .ts compiles
           to an empty .js, or to a file with just imports
```

`declare global`, `declare module`, and ambient module declarations need the `.d.ts` context — or the explicit `declare` keyword inside a `.ts` file.

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

You must augment `"express-serve-static-core"`, not `"express"`, because that is where the `Request` interface is defined. Find the right module by reading `node_modules/@types/express/index.d.ts`. Without `import "express"` the file may not count as a module, and the merging will not take effect.

---

**Why is `export {}` important in a `.d.ts` file that uses `declare global`?**

Because `export {}` is what turns the file into a module, and only inside a module does `declare global` mean anything.

```ts
// Without export {} — the file is a script, everything is
// already global, and declare global is unnecessary:
declare const __DEV__: boolean;

// With export {} — the file is a module, so extending the
// global scope needs an explicit block:
export {};
declare global {
  const __DEV__: boolean;
}
```

Without that distinction the declarations behave unpredictably. Either everything becomes global, which is undesirable in a modular codebase. Or nothing does, because TypeScript decided the file was a module and `declare global` was never written.

---

**In which cases is `namespace` still justified in modern TypeScript?**

Three cases, all of them inside declaration files rather than ordinary code.

```ts
// 1. Ambient declarations for a global library loaded with
//    <script> — jQuery, or a legacy SDK (software development
//    kit, a vendor's prepackaged client library):
declare namespace jQuery { function ajax(url: string): void; }

// 2. Grouping types inside a .d.ts file, without creating
//    file-level modules:
declare namespace API { interface User { id: number } }

// 3. Merging with an enum or a function to attach static methods:
namespace Direction { export function opposite(): void {} }
```

In regular `.ts` code, use ES modules instead. ES is ECMAScript, the standard that defines JavaScript.

---

## Group 9: Advanced Patterns

**What are branded types? How do they work without runtime overhead?**

A branded type adds a fictitious marker field that makes two structurally identical types incompatible:

```ts
type UserId = number & { readonly __brand: "UserId" };
```

The `__brand` field exists only in the TypeScript type, and the whole intersection is erased on compile — in JavaScript this is just a `number`. There is no wrapper object and no runtime check. To create a value you write `const id = 42 as UserId`, where `as` bypasses the structural check for the initialisation.

---

**How does a phantom type differ from a branded type?**

A branded type puts the marker in a field; a phantom type puts it in an unused generic parameter.

| | Shape | Best for |
|---|---|---|
| Branded | `T & { __brand: "UserId" }` | telling apart primitives of one type |
| Phantom | `{ name: string } & { __state: TState }` | encoding a stage, Validated vs Unvalidated |

The goal is the same in both: add a compile-time distinction with no runtime change. Neither costs anything at runtime, because both markers are erased.

---

**How do you implement a recursive type for JSON values?**

```ts
type JSONPrimitive = string | number | boolean | null;
type JSONObject    = { [key: string]: JSONValue };
type JSONArray     = JSONValue[];
type JSONValue     = JSONPrimitive | JSONObject | JSONArray;
```

The recursion works through indirection: `JSONValue` refers to `JSONObject` and `JSONArray`, and those refer back to `JSONValue`. Direct recursion down to a primitive does not work. The depth limit is around 100 levels, so truly large JSON structures need runtime validation with a library like Zod.

---

**When should type-level programming be replaced with runtime validation?**

At every system boundary, because TypeScript checks types only at compile time and nothing checks them at runtime.

```ts
// ❌ False security — req.body is whatever arrived over the wire:
const user = req.body as User;

// ✅ A validator checks the actual value:
const user = UserSchema.parse(req.body);
```

Data from `req.body`, `JSON.parse` or `localStorage` carries no guarantee from the type system. Types are also powerless over value constraints such as email format, a positive number, or a non-empty string. Those need Zod, Yup or io-ts.

- Type-level work: compile-time guarantees and DX, the developer experience of writing the code.
- Runtime validation: every system boundary — HTTP, files, environment variables.

---

## Group 10: Compiler and Configuration

**What is included in `"strict": true`? Name at least 4 flags and what each catches.**

`strict` enables eight flags at once:

| Flag | What it catches |
|---|---|
| `strictNullChecks` | `null`/`undefined` are not assignable to other types |
| `noImplicitAny` | implicit `any` on parameters and variables |
| `strictFunctionTypes` | contravariant checking of function parameters |
| `strictBindCallApply` | untyped `.bind` / `.call` / `.apply` |
| `strictPropertyInitialization` | class fields never initialized in the constructor |
| `noImplicitThis` | `this` typed as `any` |
| `alwaysStrict` | missing `"use strict"` in generated files |
| `useUnknownInCatchVariables` | a `catch` variable used as `any` instead of `unknown` |

In an interview it is enough to name the first four and say what each one catches.

---

**How does `moduleResolution: "bundler"` differ from `"node16"`?**

`node16` copies what Node.js really does with ES modules (ESM); `bundler` assumes a bundler resolves imports for you.

```ts
// With node16 — a relative import must carry the extension,
// and the extension must be ".js":
import { foo } from "./utils";    // ❌ ESM needs the extension
import { foo } from "./utils.js"; // ✅ TypeScript still reads utils.ts

// With bundler — the extension is optional, webpack, vite
// or esbuild finds the file:
import { foo } from "./utils";    // ✅
```

Both strategies read the `exports` map in `package.json`. Pick `bundler` for frontend work, where you never want to write `.js` in a TypeScript import. Pick `node16` when you publish an ESM library for Node.js.

---

**What is `isolatedModules` and why does it disallow `const enum`?**

It requires every file to be compilable on its own, with no cross-file analysis — and resolving a `const enum` needs exactly that.

```ts
// file: direction.ts
export const enum Direction { Up = 0, Down = 1 }

// file: use.ts
import { Direction } from "./direction";
Direction.Up; // must be inlined as 0 — needs the other file
```

The flag is mandatory for Babel, esbuild and SWC — the Speedy Web Compiler — because each of them transpiles one file at a time. Replace a `const enum` with a plain `enum` or an `as const` object.

---

**What is the difference between `target` and `lib` in tsconfig?**

`target` decides which syntax is generated; `lib` decides which APIs TypeScript believes exist.

| | Controls | Examples |
|---|---|---|
| `target` | syntactic transforms | `arrow → function`, `class → prototype`, `async/await → Promise chain` |
| `lib` | available API types | `Array.prototype.at`, `Promise.allSettled`, `structuredClone` |

The two are independent. That is why `target: "es5"` with `lib: ["es2022"]` is valid: emit ES5 syntax, but know about modern APIs that a polyfill will supply. ES5 is the 2009 version of the JavaScript standard. Common mistake: adding `lib: ["es2022"]` and expecting a polyfill — `lib` only adds the types.

---

**Why isn't `noUncheckedIndexedAccess` included in `strict` even though it's very useful?**

Because it breaks an enormous amount of existing code, so the TypeScript team left it out for backward compatibility.

```ts
// With noUncheckedIndexedAccess:
const arr: number[] = [];
const first = arr[0];  // number | undefined, not number
first.toFixed();       // ❌ Object is possibly 'undefined'
```

The flag adds `| undefined` to every index access result. That is more correct, but guards then have to be added everywhere. For new projects, enable it explicitly: it catches the very common crash where the array turned out to be empty.

---

**What does `skipLibCheck: true` do and what are its risks?**

It skips type checking inside every `.d.ts` file, including all of `node_modules/@types/**`.

```txt
Benefit:  removes type conflicts between incompatible
          @types/* versions, and speeds up compilation

Risk:     hides real incompatibilities between dependencies;
          an error in a library's .d.ts that affects your
          own code goes undetected
```

In practice `skipLibCheck: true` is near-universal. What separates a senior is knowing exactly what is being skipped, and treating it as a trade-off rather than a free optimisation.

---

## Group 11: Type Safety in Architecture

**How do TypeScript types help follow the principle "make invalid states unrepresentable"?**

Discriminated unions encode state so that invalid combinations cannot be written down at all:

```ts
// ❌ Can create { loading: true, data: user, error: err }:
type State = { loading: boolean; data?: User; error?: Error };

// ✅ Invalid states are inexpressible:
type State =
  | { status: "loading" }
  | { status: "success"; data: User }
  | { status: "error"; error: Error };
```

Branded types turn a mix-up of semantically similar values into a compile error, and phantom types encode processing stages such as Unvalidated to Validated. The goal in every case is to move checks from runtime to compile time.

---

**How do you type a function whose return type depends on the input parameter?**

Three approaches, from simple to complex: overloads, a conditional return type, or a plain generic constraint.

```ts
// 1. Overloads — duplication, but readable error messages:
function process(v: string): string;
function process(v: number): number;
function process(v: any): any { return v; }

// 2. Conditional return type:
declare function process2<T extends string | number>(
  v: T
): T extends string ? string : number;

// 3. Generic with an extends constraint — often enough:
declare function process3<T extends string | number>(v: T): T;
```

Conditional types are preferred for library code, overloads when the readability of error messages matters. One caveat: TypeScript often cannot infer a conditional return type inside the function body, so a cast with `as` is frequently needed there.

---

**What is `Readonly<T>` and why doesn't `const` on an object make it readonly?**

`const` freezes the binding, not the contents, so the fields of the object stay writable.

```ts
const obj = { x: 1 };
obj.x = 2;      // ✅ allowed — const protects the variable only
obj = { x: 3 }; // ❌ Cannot assign to 'obj' because it is a constant

const ro: Readonly<{ x: number }> = { x: 1 };
ro.x = 2; // ❌ Cannot assign to 'x' because it is a read-only property
```

`Readonly<T>` marks every field `readonly` at the type level, and `as const` does the same recursively and with literal types. Note the layer: `Readonly` is a compile-time constraint while `Object.freeze()` acts at runtime. For deep immutability you need a `DeepReadonly`.

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

Four advantages: it works with `isolatedModules`, it is tree-shakeable, there is no `const enum` resolution to worry about, and the type comes from the values. The expression `typeof Status[keyof typeof Status]` is the standard pattern for building a union out of the values of an `as const` object.

---

**How does TypeScript handle `process.env.NODE_ENV` — why is the type `string | undefined` instead of a specific union?**

Because `process.env` is typed as `NodeJS.ProcessEnv`, which is `{ [key: string]: string | undefined }`, and TypeScript cannot know which variables a given environment sets.

```ts
declare namespace NodeJS {
  interface ProcessEnv {
    NODE_ENV: "development" | "production" | "test";
    DATABASE_URL: string;
  }
}
```

After extending the interface, `process.env.NODE_ENV` is `"development" | "production" | "test"` and `process.env.TYPO` is a compile error. This is module augmentation through declaration merging.
