<!-- verified: 2026-06-23, corrections: 0 -->
# TypeScript Compiler and Configuration

## How the TypeScript Compiler Works

TypeScript is not transpiled directly to JavaScript by the browser or Node. It's a separate tool (`tsc`) that goes through several phases:

```txt
TypeScript compilation phases:

1. Parsing
   Source .ts → AST (Abstract Syntax Tree)

2. Binding
   Build the symbol table: which names are declared where

3. Type checking
   Analyze AST + symbol table → list of errors
   This is where all type checks happen

4. Emit
   AST → .js and .d.ts files
   Types are completely erased

Important: phases 3 and 4 are independent.
  - tsc --noEmit — type-check only, no JS generated
  - isolatedModules — each file compiled independently (Babel/esbuild)
  - transpileOnly (ts-node) — skip type checking, emit only
```

This explains why Babel and esbuild can transpile TypeScript without understanding types: they perform only phase 4, skipping phase 3. This is also why some TypeScript constructs are incompatible with `isolatedModules` (e.g. `const enum`, `namespace`).

---

## `strict` — What It Actually Enables

`"strict": true` is not a single option — it's a group of eight flags. Knowing each one individually matters because sometimes you need only a subset, or need to understand exactly which flag caught an error.

```json
{
  "compilerOptions": {
    "strict": true
    // Equivalent to enabling all eight flags below:
  }
}
```

### `strictNullChecks`

The most important flag. Without it, `null` and `undefined` are assignable to any type:

```ts
// strictNullChecks: false (default without strict):
let name: string = null;    // ✅ — disaster at runtime
let age: number = undefined; // ✅

// strictNullChecks: true:
let name: string = null;    // ❌ Type 'null' is not assignable to type 'string'
let name2: string | null = null; // ✅ — explicit permission
```

**What it catches:** accessing properties on `null`/`undefined` without a check, using the result of functions that can return `null` (`.find()`, `.querySelector()`).

```ts
// Without strictNullChecks — silent:
const user = users.find(u => u.id === id);
user.name; // ✅ TypeScript — but runtime crash if not found

// With strictNullChecks:
user.name; // ❌ 'user' is possibly 'undefined'
if (user) user.name; // ✅
```

### `noImplicitAny`

Disallows implicit `any` where TypeScript cannot infer a type:

```ts
// noImplicitAny: false:
function process(data) { // data: any — TypeScript doesn't complain
  return data.value;
}

// noImplicitAny: true:
function process(data) { // ❌ Parameter 'data' implicitly has an 'any' type
  return data.value;
}

// Fix — explicit annotation:
function process(data: unknown) { /* ... */ }
function process(data: { value: string }) { /* ... */ }
```

**What it catches:** function parameters without types, variables that can't be inferred from context, uninitialized object fields.

### `strictFunctionTypes`

Enables contravariant checking of function parameters (instead of bivariant). Covered in detail in [Variance and Assertions]:

```ts
// strictFunctionTypes: false:
type Handler = (event: MouseEvent) => void;
const handler: Handler = (event: Event) => {}; // ✅ bivariant (UNSAFE)

// strictFunctionTypes: true:
const handler: Handler = (event: Event) => {}; // ❌ Event is wider than MouseEvent
```

**What it catches:** covariant uses of function types that should be contravariant. Especially important with callback parameters.

### `strictBindCallApply`

Enables type checking for `.bind()`, `.call()`, `.apply()`:

```ts
function greet(name: string, age: number): string {
  return `${name}, ${age}`;
}

// strictBindCallApply: false:
greet.call(null, "Alice", "30"); // ✅ — string instead of number, TypeScript silent

// strictBindCallApply: true:
greet.call(null, "Alice", "30"); // ❌ Argument of type 'string' is not assignable to 'number'
greet.call(null, "Alice", 30);   // ✅
```

### `strictPropertyInitialization`

Requires all class properties to be initialized in the constructor:

```ts
class User {
  id: number;    // ❌ Property 'id' has no initializer and is not definitely assigned
  name: string;  // ❌ same

  constructor() {
    // forgot to assign
  }
}

// Fixes:
class User {
  id: number = 0;    // ✅ initializer
  name!: string;     // ✅ definite assignment assertion (careful — disables the check)

  constructor(id: number, name: string) {
    this.id = id;    // ✅ assignment in constructor
    this.name = name;
  }
}
```

**What it catches:** class fields that may be `undefined` due to an incomplete constructor — a typical source of runtime errors in OOP code.

### `noImplicitThis`

Disallows `this` with an implicit type of `any`:

```ts
// noImplicitThis: true:
function greet() {
  return this.name; // ❌ 'this' implicitly has type 'any'
}

// Fix — explicit this type:
function greet(this: { name: string }) {
  return this.name; // ✅
}
```

### `alwaysStrict`

Adds `"use strict"` to every generated JS file. In modern ES modules `"use strict"` is already implied, so the effect is minimal — but for CJS output it matters.

### `useUnknownInCatchVariables` (TS 4.0+)

Changes the type of the `catch` variable from `any` to `unknown`:

```ts
// useUnknownInCatchVariables: false:
try { /* ... */ } catch (e) {
  e.message; // e: any — can access any property without checking
}

// useUnknownInCatchVariables: true:
try { /* ... */ } catch (e) {
  e.message; // ❌ e: unknown — a check is required
  if (e instanceof Error) {
    e.message; // ✅
  }
}
```

**Practically important:** anything can be thrown — `throw "string"`, `throw 42`, `throw { code: 500 }` — all legal in JavaScript. `unknown` is more honest than `any`.

---

## Other Important Options Outside `strict`

### `noUncheckedIndexedAccess`

One of the most useful options outside `strict`. Adds `| undefined` to the result of index access:

```ts
// noUncheckedIndexedAccess: false (default):
const arr = [1, 2, 3];
const x = arr[10]; // x: number — but this is undefined at runtime!
x.toFixed();       // runtime crash

// noUncheckedIndexedAccess: true:
const x = arr[10]; // x: number | undefined
x.toFixed();       // ❌ Object is possibly 'undefined'
if (x !== undefined) x.toFixed(); // ✅

// Same for objects with index signatures:
const map: Record<string, number> = {};
const val = map["key"]; // val: number | undefined ✅
```

**Why it's not in `strict` by default:** breaks too much existing code, requires many `if (x !== undefined)` guards. But for new projects — recommended.

### `exactOptionalPropertyTypes`

Distinguishes "field is absent" from "field is explicitly `undefined`":

```ts
// exactOptionalPropertyTypes: false:
interface Config { timeout?: number }
const c: Config = { timeout: undefined }; // ✅ — treated as absent

// exactOptionalPropertyTypes: true:
const c: Config = { timeout: undefined };
// ❌ Type '{ timeout: undefined }' is not assignable to 'Config'
//    Types of property 'timeout' are incompatible
//    Type 'undefined' is not assignable to 'number'
```

Useful when the difference between "not provided" and "provided as undefined" matters (e.g. when working with JSON or REST APIs where `null`/absent have different meanings).

### `noImplicitOverride`

Requires an explicit `override` keyword when overriding a base class method:

```ts
class Base {
  render(): string { return "base"; }
}

// noImplicitOverride: false:
class Child extends Base {
  render(): string { return "child"; } // silent, even if Base has no render
}

// noImplicitOverride: true:
class Child extends Base {
  render(): string { return "child"; } // ❌ Method 'render' will overwrite the base
  override render(): string { return "child"; } // ✅
}

// Key benefit: if the method is renamed in Base, TypeScript catches it in Child:
class Child extends Base {
  override rander(): string { return "child"; } // ❌ Method 'rander' does not exist in Base
}
```

---

## Module Resolution: node16 / bundler

Module resolution is the algorithm by which TypeScript finds the file for `import { x } from "some-path"`. A wrong setting is the source of "Cannot find module" errors or dev/prod behavior differences.

### Strategies

```txt
classic       — legacy, only for old projects
node          — Node.js CommonJS algorithm (long-standing standard)
node16 / nodenext — Node.js ESM algorithm (required for ESM)
bundler       — for projects with webpack/vite/esbuild (TS 5.0+)
```

### `node` (Legacy CJS)

Works like Node.js in CommonJS mode:
- `"./utils"` → looks for `./utils.ts`, `./utils.js`, `./utils/index.ts`
- `"lodash"` → looks in `node_modules/lodash`

Does not support ESM-specific features (`import.meta`, conditional exports in `package.json`).

### `node16` / `nodenext`

Required when `"module": "node16"` or `"module": "nodenext"`. Reflects the actual behavior of Node.js with ESM:

```ts
// With node16: extensions are REQUIRED for relative imports:
import { foo } from "./utils";     // ❌ ESM requires an extension
import { foo } from "./utils.js";  // ✅ — TypeScript will find utils.ts

// In a CJS file (.cts or "type": "commonjs"):
const { foo } = require("./utils"); // ✅ no extension needed in CJS
```

```json
// package.json conditional exports — node16 understands these:
{
  "exports": {
    ".": {
      "import": "./dist/index.mjs",
      "require": "./dist/index.cjs"
    }
  }
}
```

### `bundler` (TypeScript 5.0+)

Designed specifically for projects where a bundler (webpack, vite, esbuild) handles imports:

```ts
// bundler: extensions are optional (the bundler handles resolution):
import { foo } from "./utils";     // ✅ — like node
import { foo } from "./utils.js";  // ✅ — also fine

// Supports package.json exports (like node16):
import { something } from "some-lib/feature"; // ✅ via exports map
```

**Key difference from `node16`:** does not require explicit extensions in imports. Suitable for most modern frontend projects.

```json
// tsconfig for Next.js / Vite projects:
{
  "compilerOptions": {
    "module": "esnext",
    "moduleResolution": "bundler",
    "target": "es2022"
  }
}
```

---

## `isolatedModules`

Requires each file to be compilable independently, without information about other files. Mandatory when using Babel, esbuild, or SWC — they transpile one file at a time without cross-file analysis.

### What `isolatedModules` Disallows

```ts
// 1. const enum — values are resolved only via cross-file analysis:
const enum Direction { Up = 0, Down = 1 }
const d = Direction.Up; // ❌ Cannot use 'const enum' with isolatedModules

// Replacement: plain enum or as const object:
const Direction = { Up: 0, Down: 1 } as const;

// 2. Re-exporting types without the type keyword:
export { SomeType }; // ❌ — SomeType might be type-only
export type { SomeType }; // ✅ explicit type export

// 3. namespace (except ambient):
namespace Utils { // ❌ in .ts files with isolatedModules
  export function format() {}
}

// 4. Importing a type without type keyword when re-exporting:
import { MyType } from "./types";
export { MyType }; // ❌ — unclear whether it's a type or value
export type { MyType }; // ✅
```

### `verbatimModuleSyntax` (TS 5.0+) — The Modern Alternative

A stricter version: if you import something only as a type — you must write `import type`. Otherwise the compiler can't eliminate the import during emit:

```ts
// verbatimModuleSyntax: true:
import { User } from "./types";        // ❌ — if User is type-only
import type { User } from "./types";   // ✅

import { createUser, type User } from "./api"; // ✅ inline type
```

---

## `skipLibCheck`

Skips type checking of `.d.ts` files (including `node_modules/@types/**`):

```json
{
  "compilerOptions": {
    "skipLibCheck": true // very common, but understanding the trade-off matters
  }
}
```

**Why people use it:** type conflicts between different versions of `@types/*` packages, errors in third-party `.d.ts` files, faster compilation for large projects.

**Risks of `skipLibCheck: true`:**
- Hides real incompatibilities between dependencies
- A conflict between `@types/node` v18 and `@types/node` v20 — you won't see it
- An error in a library's `.d.ts` that affects your code — you won't catch it

**Best practice:**

```json
// Compromise: skip library checks but be strict about your own code:
{
  "compilerOptions": {
    "skipLibCheck": true,  // skip node_modules
    "strict": true         // but be strict about own code
  }
}
```

---

## `target` and `lib` — What They Control

A common source of confusion: `target` and `lib` are different things.

```txt
target — determines which JS TypeScript generates
         (syntactic transforms: arrow → function, class → prototype)

lib    — determines which APIs TypeScript knows about
         (types for Array.prototype.at, Promise.allSettled, etc.)
```

```json
{
  "compilerOptions": {
    "target": "es2017",      // generate ES2017 syntax
    "lib": ["es2022", "dom"] // but KNOW about APIs up to ES2022 + DOM
  }
}
```

This lets you use modern APIs in your code (provided by a polyfill or the runtime) while generating more compatible syntax.

```ts
// target: es2017, lib: es2022:
const result = arr.at(-1); // ✅ — TypeScript knows .at(), lib: es2022
// Generates: const result = arr.at(-1); (not transformed)
// Your polyfill ensures arr.at exists in the old browser

// target: es5 + downlevelIteration:
for (const x of set) {} // Transformed into an ES5 for loop
```

---

## Reference tsconfig.json for Different Project Types

### Node.js Backend (ESM)

```json
{
  "compilerOptions": {
    "target": "es2022",
    "module": "node16",
    "moduleResolution": "node16",
    "lib": ["es2022"],
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "skipLibCheck": true
  }
}
```

### Frontend (Vite / Next.js)

```json
{
  "compilerOptions": {
    "target": "es2022",
    "module": "esnext",
    "moduleResolution": "bundler",
    "lib": ["es2022", "dom", "dom.iterable"],
    "jsx": "react-jsx",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "verbatimModuleSyntax": true,
    "isolatedModules": true,
    "noEmit": true,
    "skipLibCheck": true
  }
}
```

### npm Library

```json
{
  "compilerOptions": {
    "target": "es2020",
    "module": "node16",
    "moduleResolution": "node16",
    "declaration": true,
    "declarationDir": "./dist/types",
    "declarationMap": true,
    "emitDeclarationOnly": true,
    "strict": true,
    "stripInternal": true  // remove @internal comments from .d.ts
  }
}
```

---

## `paths` and `baseUrl` — Import Aliases

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"],
      "@components/*": ["./src/components/*"],
      "@utils/*": ["./src/utils/*"]
    }
  }
}
```

```ts
// Instead of:
import { Button } from "../../../components/Button";
// You can write:
import { Button } from "@components/Button"; // ✅
```

**Important:** `paths` is TypeScript-only. The bundler (webpack, vite) needs to be configured separately. For Vite — `resolve.alias`; for webpack — `resolve.alias` or `tsconfig-paths-webpack-plugin`.

---

## Common Interview Traps

- **"strict is a single option"** — no, it's a group of 8 flags. Naming `strictNullChecks` and `noImplicitAny` individually and explaining what each catches is a sign of deep understanding.

- **"skipLibCheck is safe"** — it's a trade-off. It hides errors in dependency `.d.ts` files. In large projects it's sometimes necessary, but understanding the risks matters.

- **Not knowing the difference between `target` and `lib`** — `target` transforms syntax, `lib` adds knowledge of APIs. You can have `target: "es5"` and `lib: ["es2022"]` — syntax will be transpiled, but TypeScript will know about modern APIs.

- **"moduleResolution: node is always correct"** — outdated for ESM projects. Node.js ESM requires `node16`/`nodenext` with mandatory file extensions. For frontend with a bundler — `bundler` (TS 5.0+).

- **Not understanding `isolatedModules`** — "why can't I use `const enum`?" Because `isolatedModules` forbids anything requiring cross-file analysis. Babel/esbuild compile per-file and can't resolve `const enum` values.

- **Not knowing about `noUncheckedIndexedAccess`** — one of the most useful options outside `strict`, catching `undefined` when accessing array elements or object keys by index. Many even senior developers are unaware of it.

- **Confusing `declaration` and `emitDeclarationOnly`** — `declaration: true` generates `.d.ts` alongside `.js`. `emitDeclarationOnly: true` generates **only** `.d.ts`, no `.js` — used when the bundler handles transpilation.
