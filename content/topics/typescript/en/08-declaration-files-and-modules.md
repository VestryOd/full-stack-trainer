<!-- verified: 2026-06-23, corrections: 0 -->
# Declaration Files and Modules

## What Are `.d.ts` Files and Why They Exist

A `.d.ts` file contains only type declarations — no executable code, only signatures, interfaces, and types. TypeScript uses them to understand the APIs of libraries written in JavaScript.

```txt
Sources of types in a TypeScript project:

1. .ts files — contain both types and code
2. .d.ts files — type declarations only (generated from .ts
   during compilation, or written manually for JS libraries)
3. @types/* packages — .d.ts files for popular JS libraries
   (e.g. @types/express, @types/lodash)
4. tsconfig lib — built-in types for DOM, ES2022, etc.
```

When TypeScript encounters `import { foo } from "some-library"`, it looks for types in this order:
1. The `types` or `typings` field in the library's `package.json`
2. `index.d.ts` in the package root
3. The `@types/some-library` package in `node_modules/@types/`
4. If nothing is found — type `any` (with a warning under `noImplicitAny`)

---

## Ambient Declarations — Declaring Without Implementation

`declare` is a keyword telling TypeScript: "this exists at runtime, but is defined somewhere external". In a `.d.ts` file `declare` is implied everywhere, but in a `.ts` file you must write it explicitly.

```ts
// global.d.ts
declare const __VERSION__: string;           // global variable
declare function require(id: string): any;   // global function
declare class EventEmitter {                 // global class
  on(event: string, listener: Function): this;
  emit(event: string, ...args: any[]): boolean;
}

// Ambient module declarations:
declare module "*.svg" {
  const content: string;
  export default content;
}

declare module "*.png" {
  const src: string;
  export default src;
}
```

The last two are the standard pattern for webpack/vite projects: TypeScript doesn't know what importing `.svg` gives you, so you declare an ambient module.

### `declare global` — Extending the Global Namespace

```ts
// types/global.d.ts
export {}; // makes this a module, not a script

declare global {
  interface Window {
    analytics: {
      track(event: string, props?: Record<string, unknown>): void;
    };
  }

  // A global variable accessible without import:
  const __DEV__: boolean;
}
```

Without `export {}` the file is treated as a script (not a module) and its declarations are automatically global. With `export {}` the file becomes a module, and `declare global {}` is needed to extend the global scope.

---

## Declaration Merging

TypeScript allows multiple declarations with the same name to be automatically merged. This works for: `interface`, `namespace`, `function` (overloads), `class + interface`, `enum`.

### interface + interface

```ts
// Two User declarations merge into one:
interface User {
  id: number;
  name: string;
}

interface User {
  email: string;
  createdAt: Date;
}

// Resulting User: { id: number; name: string; email: string; createdAt: Date }
const user: User = {
  id: 1,
  name: "Alice",
  email: "alice@example.com",
  createdAt: new Date(),
}; // ✅
```

### namespace + class / namespace + function

A namespace can merge with a class or function of the same name — the pattern for adding static members or function properties:

```ts
function validator(value: string): boolean {
  return validator.pattern.test(value);
}

namespace validator {
  export const pattern = /^[a-z]+$/;
  export function create(pattern: RegExp): typeof validator {
    return (v: string) => pattern.test(v);
  }
}

// Usage:
validator("hello");         // ✅ function call
validator.pattern;          // ✅ property from namespace
validator.create(/^\d+$/);  // ✅ method from namespace
```

### enum + namespace

Adding static methods to an enum:

```ts
enum Direction {
  Up = "UP",
  Down = "DOWN",
  Left = "LEFT",
  Right = "RIGHT",
}

namespace Direction {
  export function opposite(dir: Direction): Direction {
    const map: Record<Direction, Direction> = {
      [Direction.Up]: Direction.Down,
      [Direction.Down]: Direction.Up,
      [Direction.Left]: Direction.Right,
      [Direction.Right]: Direction.Left,
    };
    return map[dir];
  }
}

Direction.opposite(Direction.Up); // Direction.Down ✅
```

---

## Module Augmentation — Extending Third-Party Types

The most practically important use case for declaration merging — extending types from `node_modules` without forking the library.

### Extending Express

```ts
// src/types/express.d.ts
import "express";

declare module "express-serve-static-core" {
  interface Request {
    user?: {
      id: number;
      email: string;
      role: "admin" | "user";
    };
    requestId: string;
  }
}
```

Why `express-serve-static-core` rather than `express`? Because Express types are split across several internal modules, and `Request` is defined there. Finding the right module for augmentation requires reading the source `.d.ts` files:

```bash
node_modules/@types/express/index.d.ts
# → look at where Request is imported from
# → find: import * as e from "express-serve-static-core"
```

### Extending Fastify

```ts
// src/types/fastify.d.ts
import "fastify";

declare module "fastify" {
  interface FastifyRequest {
    user: { id: number; role: string } | undefined;
  }

  interface FastifyInstance {
    config: {
      PORT: number;
      DATABASE_URL: string;
    };
  }
}
```

### Extending Global Types (Window, process.env)

```ts
// src/types/env.d.ts
declare namespace NodeJS {
  interface ProcessEnv {
    NODE_ENV: "development" | "production" | "test";
    DATABASE_URL: string;
    JWT_SECRET: string;
    PORT?: string; // optional
  }
}
```

After this, `process.env.DATABASE_URL` has type `string` (not `string | undefined`), and `process.env.TYPO` is a compile error.

### Augmenting Third-Party Types

If a library has no types and you want to add them:

```ts
// Do NOT touch node_modules/@types/some-lib/index.d.ts
// Instead — src/types/some-lib.d.ts:

import "some-lib";

declare module "some-lib" {
  // Add a missing method:
  interface SomeClass {
    missingMethod(arg: string): void;
  }

  // Add a missing export:
  export function newHelper(): void;
}
```

**Important limitation of module augmentation:** you cannot create a new module via augmentation — you can only extend an existing one. For a non-existent module you need an ambient module declaration:

```ts
// Ambient module (new module):
declare module "some-untyped-lib" {
  export function doSomething(): void;
  export const VERSION: string;
}

// Module augmentation (extending existing):
declare module "some-typed-lib" {
  interface ExistingInterface {
    newField: string; // ✅
  }
}
```

---

## Namespace vs Module — History and Current Practice

### What Is a Namespace

`namespace` (formerly called `module` before TypeScript 1.5) was a way to organize code into name spaces before ES modules existed:

```ts
namespace Utils {
  export interface Logger {
    log(message: string): void;
  }

  export function formatDate(date: Date): string {
    return date.toISOString();
  }

  export namespace Strings {
    export function capitalize(s: string): string {
      return s.charAt(0).toUpperCase() + s.slice(1);
    }
  }
}

const formatted = Utils.formatDate(new Date());
Utils.Strings.capitalize("hello");
```

### Why Namespaces Are Mostly Legacy

```txt
Problems with namespaces:

1. No tree-shaking — the entire namespace ends up in the bundle
2. No explicit dependencies — unclear where things come from
3. More complex compiler configuration (outFile, concatenate)
4. Not natively compatible with ES modules
5. Worse debugging in browsers — no source map integration with modules

Modern alternative — ES modules (import/export):
  - Natively supported by all bundlers
  - Tree-shaking works out of the box
  - Explicit dependencies between files
  - Compatible with Node.js ESM
```

### When Namespaces Are Still Justified

```ts
// 1. Ambient declarations for global libraries (legacy):
declare namespace jQuery {
  function ajax(url: string, settings?: AjaxSettings): JqXHR;
  interface AjaxSettings {
    method?: "GET" | "POST";
    data?: object;
  }
}

// 2. Grouping types inside a .d.ts file:
declare namespace API {
  interface User { id: number; name: string }
  interface Post { id: number; title: string; authorId: number }
  interface Response<T> { data: T; status: number }
}

// 3. Merging with enum or function (shown above)
```

### The Difference Between `module "foo"` and `namespace`

```ts
// Ambient module (for typing JS libraries):
declare module "lodash" {
  export function chunk<T>(array: T[], size: number): T[][];
}

// This is NOT the same as namespace!
// declare module creates a description of an ES module
// namespace creates a global name space
```

---

## Triple-slash Directives

Triple-slash directives are special single-line comments at the top of a file that TypeScript interprets as instructions.

```ts
/// <reference types="node" />
/// <reference path="./types/custom.d.ts" />
/// <reference lib="es2022" />
```

### `reference types`

Explicitly includes a package from `@types/*`. Rarely needed — TypeScript usually finds types automatically via `node_modules/@types/`:

```ts
/// <reference types="node" />

// Node.js types now available:
process.env.NODE_ENV; // ✅
Buffer.from("hello"); // ✅
```

**When it's genuinely needed:** in `.d.ts` files for libraries that depend on other types:

```ts
// my-library/index.d.ts
/// <reference types="node" />

export function readFile(path: string): Buffer;
```

### `reference path`

Explicitly includes another `.d.ts` file:

```ts
/// <reference path="./vendor/legacy-lib.d.ts" />

// This is a legacy pattern — used before import/export existed
// Now prefer: import type { LegacyType } from "./vendor/legacy-lib"
```

### `reference lib`

Includes a built-in TypeScript library:

```ts
/// <reference lib="es2022.array" />

// Array.prototype.at() now available:
[1, 2, 3].at(-1); // ✅
```

### Modern Practice

```txt
Use triple-slash directives when:
  - Writing a .d.ts file for a library (reference types)
  - Working with legacy code without a module system (reference path)

Do NOT use when:
  - Writing a regular .ts file — use import instead
  - Including types across a project — use tsconfig.json compilerOptions.types
```

```json
// tsconfig.json — instead of triple-slash in every file:
{
  "compilerOptions": {
    "types": ["node", "jest"],
    "lib": ["es2022", "dom"]
  }
}
```

---

## Real-World Project Structure with .d.ts Files

```txt
src/
  types/
    global.d.ts        — declare global { Window, ProcessEnv }
    express.d.ts       — module augmentation for express
    assets.d.ts        — declare module "*.svg", "*.png"
    api.d.ts           — shared API types (can be .ts, not .d.ts)

When to create .d.ts vs .ts:
  - File contains ONLY types, zero lines of runtime code → .d.ts
  - Describing an ambient environment (global variables) → .d.ts
  - Doing module augmentation → .d.ts
  - Shipping types alongside a JavaScript library → .d.ts

When to use a type-only .ts file:
  - Need import/export between type files
  - No ambient semantics required
```

### Generating .d.ts at Compile Time

```json
// tsconfig.json
{
  "compilerOptions": {
    "declaration": true,            // generate .d.ts
    "declarationDir": "./dist/types", // where to put them
    "declarationMap": true,          // source maps for .d.ts (go-to-definition)
    "emitDeclarationOnly": true      // .d.ts only, no .js (when bundler handles transpilation)
  }
}
```

```ts
// src/utils.ts
export function formatDate(date: Date): string {
  return date.toISOString().split("T")[0];
}

// Generated dist/types/utils.d.ts:
export declare function formatDate(date: Date): string;
```

---

## Common Interview Traps

- **"Namespace is the same as an ES module"** — no. A namespace compiles to an object (IIFE pattern in JS), not an ES module. Namespaces have no tree-shaking, no explicit dependencies, no native bundler support. For new code, use `import`/`export`.

- **Not knowing the difference between `.d.ts` and a type-only `.ts`** — a `.d.ts` file is never compiled to JavaScript. It exists only for TypeScript. A `.ts` file with only types compiles to an empty `.js`. Ambient declarations and module augmentation require `.d.ts`.

- **"Module augmentation works for any module"** — you can only extend an existing module. If you try to extend a non-existent one, or specify the wrong module name, the augmentation silently does nothing (TypeScript does not error!).

- **Not knowing why `declare global` needs `export {}`** — without `export {}` the file is a script (not a module), so all declarations are automatically global without `declare global`. With `export {}` the file is a module, and `declare global {}` is needed to extend the global scope. Confusion between script and module context is a frequent cause of "why aren't my types being picked up".

- **Not reading third-party `.d.ts` files** — being able to open `node_modules/@types/express/index.d.ts` and find the right interface for augmentation is a baseline senior skill. Augmenting `declare module "express"` instead of `"express-serve-static-core"` is the classic mistake.

- **Using triple-slash in regular `.ts` files** — in modern projects, triple-slash in `.ts` files is an anachronism. The exception: `.d.ts` files for libraries, where `/// <reference types="..." />` is the legitimate way to declare a dependency on another type package.
