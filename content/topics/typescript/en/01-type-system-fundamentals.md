<!-- verified: 2026-06-23, corrections: 0 -->
# TypeScript Type System Fundamentals

## Structural Typing — A Fundamental Design Choice

TypeScript uses **structural typing** (also called duck typing): two types are compatible if their *shape* (the set of fields and methods) is compatible. The name of the type doesn't matter.

```txt
Structural (TypeScript, Go):
  "If it has a beak and it quacks — it's a duck."
  Compatibility is determined by structure, not by name.

Nominal (Java, C#, Rust):
  "A duck is only what is explicitly declared as Duck."
  Two classes with identical fields are NOT compatible
  unless they share a common ancestor.
```

A practical example that surprises people at first:

```ts
class Cat {
  name: string;
  constructor(name: string) { this.name = name; }
}

class Dog {
  name: string;
  constructor(name: string) { this.name = name; }
}

function greet(animal: Cat): void {
  console.log(animal.name);
}

const dog = new Dog("Rex");
greet(dog); // ✅ OK — TypeScript does not complain!
```

In Java this code wouldn't compile — `Dog` is not a `Cat`. TypeScript considers the types compatible because both have a `name: string` field. This is not a bug — it's a deliberate decision by the TS team, based on how JavaScript is actually used: duck typing and object literals are the foundation of the language.

### What Structural Typing Means in Practice

```ts
interface Printable {
  print(): void;
}

// No explicit interface implementation needed
const document = {
  title: "Report",
  print() { console.log(this.title); }
};

function printAll(items: Printable[]): void {
  items.forEach(item => item.print());
}

printAll([document]); // ✅ — document is structurally compatible with Printable
```

**Key consequences of structural typing:**

```txt
1. Extra fields are allowed on assignment:
   { name: string; age: number } is compatible with { name: string }
   (subtype relationship — a larger type is compatible with a smaller one)

2. Object literals are an exception (excess property check):
   TypeScript ADDITIONALLY disallows extra fields on object literals
   passed directly — this is not a structural check, it's a separate
   check for catching typos early

3. Functions are checked structurally by parameters:
   (x: number) => void is compatible with (x: number, y: string) => void
   in some contexts — this is intentional (see [Variance])
```

The excess property check is a frequent source of confusion:

```ts
interface Options {
  timeout: number;
}

// ❌ Error only when passing an object LITERAL directly:
// Argument of type '{ timeout: number; retries: number; }'
// is not assignable to parameter — Object literal may only
// specify known properties
configure({ timeout: 3000, retries: 3 });

// ✅ Via a variable — the check doesn't trigger:
const opts = { timeout: 3000, retries: 3 };
configure(opts); // OK — structurally compatible
```

This isn't a contradiction — it's two layers: structural checking + a separate "fresh object literal check" only for literals. Understanding the difference is important for interviews.

---

## Type Inference — The Mechanics

TypeScript infers types from context. Understanding *how* explains many surprising behaviors.

### Type Widening

When TypeScript sees a literal value, it *widens* the type to the base type:

```ts
let x = "hello";   // x: string (not "hello")
let n = 42;        // n: number (not 42)
let b = true;      // b: boolean (not true)

const cx = "hello"; // cx: "hello" — constant, no widening
const cn = 42;      // cn: 42
```

Why does `let` widen but `const` doesn't? Because `let` *can be reassigned* (`x = "world"` is valid), so the type must be wide enough to accommodate that. `const` can't be reassigned, so the type can be the precise literal.

Widening inside objects:

```ts
const obj = { x: 10, y: "hello" };
// obj: { x: number; y: string } — fields widen, even for const
// Because object fields CAN be reassigned: obj.x = 20 is OK

const obj2 = { x: 10, y: "hello" } as const;
// obj2: { readonly x: 10; readonly y: "hello" } — no widening
```

### Type Narrowing

Narrowing is the process by which TypeScript refines a type in a specific code branch based on control flow analysis.

```ts
function process(value: string | number | null) {
  if (value === null) {
    // value: null — TypeScript knows exactly
    return;
  }

  if (typeof value === "string") {
    // value: string — narrowed
    console.log(value.toUpperCase());
  } else {
    // value: number — TypeScript subtracted string and null
    console.log(value.toFixed(2));
  }
}
```

TypeScript tracks *control flow* (if/else, return, throw, assignments) and builds a data flow graph. Each node in the graph has its own type for each variable. This explains why TS knows the type after `if (x === null) return`:

```ts
function getLength(s: string | undefined): number {
  if (!s) return 0;
  // ↑ After this check TypeScript knows: s !== undefined and s !== ""
  // Type of s here: string
  return s.length; // ✅
}
```

---

## type vs interface — Beyond the Syntax

The difference goes beyond syntax. Two fundamental distinctions:

### 1. Declaration Merging

`interface` supports merging — multiple declarations with the same name are automatically combined:

```ts
interface User {
  id: number;
  name: string;
}

interface User {
  email: string;
}

// Resulting type: { id: number; name: string; email: string }
const user: User = { id: 1, name: "Alice", email: "a@b.com" };
```

Declaring `type` twice is an error:

```ts
type Point = { x: number };
type Point = { y: number }; // ❌ Error: Duplicate identifier 'Point'
```

**When merging is needed:** extending third-party libraries (module augmentation):

```ts
// Extending Express types without forking the library
declare module "express-serve-static-core" {
  interface Request {
    user?: { id: number; role: string };
  }
}
```

### 2. What Only `type` Can Do

```ts
// Unions — only type:
type StringOrNumber = string | number;
type Status = "pending" | "active" | "closed";

// Intersections of arbitrary types:
type AdminUser = User & { permissions: string[] };

// Tuple types:
type Pair<T, U> = [T, U];

// Conditional types:
type NonNullable<T> = T extends null | undefined ? never : T;

// Mapped types:
type Readonly<T> = { readonly [K in keyof T]: T[K] };
```

`interface` cannot express a union. Attempting to do so is a compilation error.

### Practical Rule: When to Use Which

```txt
Use interface when:
  - Describing the shape of an object or class
  - Planning declaration merging (library code, augmentation)
  - You want clearer error messages
    (interface shows the name, type — expands the structure)

Use type when:
  - You need a union (string | number, "a" | "b" | "c")
  - You need a tuple
  - Writing conditional or mapped types
  - Aliasing a primitive or function type

Most teams: interface for objects/classes, type for everything else.
Breaking one of these rules isn't catastrophic, but it's important
to know WHY the difference exists.
```

Why error messages differ:

```ts
type UserType = { id: number; name: string };
interface UserInterface { id: number; name: string }

function process(u: UserType) {}
function processI(u: UserInterface) {}

process({ id: "1", name: "Alice" });
// ❌ Argument of type '{ id: string; name: string; }' is not assignable to
//    parameter of type '{ id: number; name: string; }'. (inlined structure)

processI({ id: "1", name: "Alice" });
// ❌ Argument of type '{ id: string; name: string; }' is not assignable to
//    parameter of type 'UserInterface'. (named type — more concise)
```

---

## How TypeScript Infers Through Complex Expressions

Understanding inference is important when types unexpectedly widen to `unknown` or `any`:

```ts
// TypeScript infers the return type from the function body:
function add(a: number, b: number) {
  return a + b; // return type: number — inferred
}

// But recursion requires an explicit annotation:
function fibonacci(n: number): number { // ← annotation required
  if (n <= 1) return n;
  return fibonacci(n - 1) + fibonacci(n - 2);
}

// Contextual typing:
const numbers = [1, 2, 3];
numbers.forEach(n => n.toFixed()); // n: number — inferred from array type
```

### Inference Through Generics

TypeScript infers generic type parameters from function arguments:

```ts
function identity<T>(value: T): T {
  return value;
}

const result = identity("hello"); // T inferred as string, result: string
const result2 = identity(42);    // T inferred as number

// Inference from multiple arguments — TypeScript finds the least common type:
function pair<T>(a: T, b: T): [T, T] {
  return [a, b];
}

pair(1, 2);          // T: number ✅
pair("a", "b");      // T: string ✅
pair(1, "hello");    // T: string | number — widens to union
```

---

## Common Interview Traps

- **"TypeScript is nominally typed"** — no, TypeScript is structurally typed. Two classes with the same structure are compatible even if they have different names. (Exception: you can *simulate* nominal typing via branding — see [Advanced Patterns].)

- **"type and interface are the same, just different syntax"** — the key differences are: declaration merging (interface only), union types (type only). Not knowing this signals a surface-level understanding.

- **Confusing excess property check with structural compatibility** — "if I pass an object with an extra field, it's always an error" — no, only when passing a literal directly. Via a variable — it's OK.

- **Not knowing the widening difference between `let` and `const`** — why `let x = "hello"` gives `string`, but `const x = "hello"` gives `"hello"`. This is fundamental mechanics asked at middle/senior level.

- **Assuming TypeScript checks types at runtime** — TypeScript is a compile-time-only tool. In compiled JavaScript there are zero TS annotations. All guarantees exist only at compile time.

- **"interface cannot extend another interface"** — it can, and this is one of its main strengths: `interface Admin extends User { permissions: string[] }`.
