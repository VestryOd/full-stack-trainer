<!-- verified: 2026-06-23, corrections: 0 -->
# Variance and Type Assertions

## What Is Variance?

Variance describes how the subtyping relationship between simple types (e.g. `Cat extends Animal`) transfers to complex types that contain them (e.g. `Box<Cat>` vs `Box<Animal>`, or `(x: Cat) => void` vs `(x: Animal) => void`).

Four kinds:

```txt
Covariance:
  Cat extends Animal → Box<Cat> extends Box<Animal>
  "subtyping direction is preserved"

Contravariance:
  Cat extends Animal → Handler<Animal> extends Handler<Cat>
  "subtyping direction is reversed"

Invariance:
  Cat extends Animal implies NEITHER direction
  Box<Cat> and Box<Animal> are incompatible

Bivariance:
  Cat extends Animal → BOTH Box<Cat> extends Box<Animal>
                        AND Box<Animal> extends Box<Cat>
  (accepted in either direction)
```

Understanding why function types behave the way they do is a core requirement at the senior level.

---

## Covariance: Function Return Types

Function return types are **covariant**: if a function returns a subtype, it is compatible wherever a function returning the supertype is expected.

```ts
class Animal { name: string = "" }
class Cat extends Animal { meow(): void {} }

// A function returning Cat is compatible where Animal is expected:
type AnimalFactory = () => Animal;
type CatFactory = () => Cat;

const makeCat: CatFactory = () => new Cat();
const makeAnimal: AnimalFactory = makeCat; // ✅ covariance

// Why this is sound:
// If I expect () => Animal, and I get () => Cat —
// that's fine: Cat IS-A Animal, it has everything needed
```

```txt
Return types:
  Cat IS-A Animal
  → (() => Cat) IS-A (() => Animal)
  Direction preserved ✅
```

---

## Contravariance: Function Parameters

Function parameters are **contravariant**: if a function accepts a supertype, it is compatible wherever a function accepting the subtype is expected.

```ts
type AnimalHandler = (animal: Animal) => void;
type CatHandler = (cat: Cat) => void;

function feedAnimal(animal: Animal): void {
  console.log(animal.name);
}

function feedCat(cat: Cat): void {
  cat.meow(); // Uses a Cat-specific method!
}

// A function with a wider parameter is compatible where a narrower one is expected:
const handler: CatHandler = feedAnimal; // ✅ contravariance

// But not the other way around:
const handler2: AnimalHandler = feedCat; // ❌ UNSAFE!
```

**Why `AnimalHandler = feedCat` is dangerous:**

```ts
const allAnimals: Animal[] = [new Animal(), new Cat()];
allAnimals.forEach(handler2); // handler2 = feedCat
// feedCat calls cat.meow() on an Animal that has no meow() → runtime crash!
```

**Why `CatHandler = feedAnimal` is safe:**

```ts
const cats: Cat[] = [new Cat()];
cats.forEach(handler); // handler = feedAnimal
// feedAnimal calls animal.name — Cat inherits this from Animal ✅
```

```txt
Function parameters:
  Cat IS-A Animal
  → (Animal) => void IS-A (Cat) => void
  Direction REVERSED ✅
```

Mnemonic: "accepting more — you can substitute everywhere less is accepted". A function that handles any `Animal` will certainly handle a `Cat`.

---

## TypeScript's Bivariance Problem: Methods

TypeScript historically checks method parameters **bivariantly** (in both directions) rather than contravariantly. This is a type system unsoundness left for compatibility:

```ts
interface Comparer<T> {
  compare(a: T, b: T): number;        // method — bivariant (UNSAFE)
  compareArrow: (a: T, b: T) => number; // function property — contravariant (SAFE)
}

// With a method TypeScript accepts both directions:
const catComparer: Comparer<Cat> = {
  compare(a: Animal, b: Animal) { return 0; } // ✅ — contravariant, fine
};

const animalComparer: Comparer<Animal> = {
  compare(a: Cat, b: Cat) { return 0; } // ✅ — TypeScript accepts! But UNSAFE
};
```

**`strictFunctionTypes` (part of `strict`)** — fixes this for function properties, but **not for methods**:

```ts
// With strictFunctionTypes:
interface Handler<T> {
  handle(value: T): void;           // method — still BIVARIANT (even with strictFunctionTypes)
  handleFn: (value: T) => void;     // function property — CONTRAVARIANT (correctly checked)
}

type CatHandlerFn    = (cat: Cat) => void;
type AnimalHandlerFn = (animal: Animal) => void;

// For function properties (with strictFunctionTypes):
const h: CatHandlerFn    = (a: Animal) => {}; // ✅ contravariance, fine
const h2: AnimalHandlerFn = (c: Cat) => {};   // ❌ Error: strictFunctionTypes enforced
```

Key takeaway: if you want correct contravariance — use `handleFn: (v: T) => void` instead of `handle(v: T): void`.

---

## Invariance and Why It Exists

Some types are invariant — neither covariance nor contravariance applies. The classic example is mutable arrays:

```ts
// Arrays are theoretically covariant in TypeScript:
const cats: Cat[] = [new Cat()];
const animals: Animal[] = cats; // ✅ TypeScript allows this (but it's UNSAFE!)

animals.push(new Animal()); // animals and cats point to the same array in memory!
cats[1].meow(); // runtime crash: Animal has no meow() ❌
```

TypeScript permits this for practicality (Kotlin, Java have the same problem with arrays). For correct code, use `ReadonlyArray`:

```ts
const cats: ReadonlyArray<Cat> = [new Cat()];
const animals: ReadonlyArray<Animal> = cats; // ✅ — safe: push is not available
```

**True invariance** in TypeScript arises when a type parameter appears in both `in` and `out` positions:

```ts
// A class with both get and set — invariant in T:
interface Box<T> {
  get(): T;         // out-position → covariant in T
  set(v: T): void;  // in-position  → contravariant in T
  // result: invariant — neither Box<Cat> is Box<Animal>
  //                      nor Box<Animal> is Box<Cat>
}
```

---

## `as const` — Fix the Type as Narrowly as Possible

`as const` tells TypeScript: "infer the narrowest possible type for this value":

```ts
// Without as const — types are widened:
const config = {
  host: "localhost",
  port: 3000,
  env: "production"
};
// config: { host: string; port: number; env: string }
// — fields are mutable, types are wide

// With as const — everything is readonly with literal types:
const config = {
  host: "localhost",
  port: 3000,
  env: "production"
} as const;
// config: {
//   readonly host: "localhost";
//   readonly port: 3000;
//   readonly env: "production"
// }
```

**How it works at different levels:**

```ts
// Primitive:
let x = "hello" as const; // x: "hello" (not string)

// Array:
const arr = [1, 2, 3] as const;
// arr: readonly [1, 2, 3] — a tuple, not number[]

// Object (recursive):
const nested = { a: { b: "value" } } as const;
// nested: { readonly a: { readonly b: "value" } }

// Enum-like pattern via as const:
const Direction = {
  Up: "UP",
  Down: "DOWN",
  Left: "LEFT",
  Right: "RIGHT",
} as const;

type Direction = typeof Direction[keyof typeof Direction];
// "UP" | "DOWN" | "LEFT" | "RIGHT"
// This is the "const enum alternative" pattern — safer than enum
```

**When `as const` is genuinely needed:**

```ts
// 1. Union from an array:
const STATUSES = ["pending", "active", "closed"] as const;
type Status = typeof STATUSES[number]; // "pending" | "active" | "closed"

// Without as const:
const STATUSES = ["pending", "active", "closed"];
type Status = typeof STATUSES[number]; // string — useless

// 2. Passing to a function that expects a literal type:
function setDirection(dir: "UP" | "DOWN") {}
const dir = "UP";           // dir: string — too wide
setDirection(dir);          // ❌ Argument of type 'string' is not assignable to...

const dir2 = "UP" as const; // dir2: "UP"
setDirection(dir2);         // ✅
```

---

## `satisfies` — Validate Type Without Losing Precision (TypeScript 4.9+)

`satisfies` is an operator that checks a value is compatible with a type, but **does not widen** it to that type. The type stays inferred; TypeScript merely guarantees the compatibility.

```ts
type ColorMap = Record<string, string | [number, number, number]>;

// ❌ Explicit annotation — precise types lost:
const palette: ColorMap = {
  red: [255, 0, 0],
  green: "#00ff00",
  blue: [0, 0, 255],
};
// palette.red: string | [number, number, number]
// Can't call palette.red.map(...) without narrowing

// ✅ satisfies — check compatibility, keep precise types:
const palette = {
  red: [255, 0, 0],
  green: "#00ff00",
  blue: [0, 0, 255],
} satisfies ColorMap;

palette.red;   // [number, number, number] ✅ — precise type!
palette.green; // string ✅ — precise type!
palette.red.map(v => v * 2); // ✅ — we know it's an array
palette.green.toUpperCase(); // ✅ — we know it's a string

// Type-checking still applies — extra keys rejected:
const bad = {
  red: [255, 0, 0],
  unknownKey: "value", // ❌ if ColorMap is exact
} satisfies ColorMap;
```

### `satisfies` vs Explicit Annotation vs `as`

```ts
type Config = { port: number; host: string };

// 1. Explicit annotation — type becomes Config, details lost:
const c1: Config = { port: 3000, host: "localhost" };
// c1: Config — no information about the specific values

// 2. satisfies — type stays precise, compatibility verified:
const c2 = { port: 3000, host: "localhost" } satisfies Config;
// c2: { port: number; host: string } — TypeScript can track literal values

// 3. as — does NOT check compatibility, just asserts:
const c3 = { port: 3000 } as Config; // ❌ Missing host, but TypeScript is silent!
// c3: Config — TypeScript trusts us, even if we're wrong

// 4. as const + satisfies — best for configs:
const c4 = {
  port: 3000,
  host: "localhost",
} as const satisfies Config;
// c4: { readonly port: 3000; readonly host: "localhost" }
// — precise type, compatibility verified, and readonly
```

**Decision table:**

```txt
Goal                                            Tool
──────────────────────────────────────────────────────────────────
Validate type + keep precise values             satisfies
Fix all types as readonly + literal             as const
Validate type + readonly + literal types        as const satisfies
Tell TypeScript the type without checking       as (type assertion)
Standard variable / parameter annotation        : Type
```

---

## Type Assertions (`as`) — When and When Not To

`as` tells TypeScript: "I know better than you, the type is this". TypeScript does **not verify** this assertion — it takes it on faith.

```ts
const input = document.getElementById("username");
// input: HTMLElement | null

// as — we assert this is an HTMLInputElement:
const inputEl = input as HTMLInputElement;
inputEl.value; // ✅ TypeScript trusts us

// But if the element is missing or not an input — runtime crash:
const missing = document.getElementById("missing") as HTMLInputElement;
missing.value; // TypeError: Cannot read properties of null
```

### When `as` Is Acceptable

```ts
// 1. DOM API — TypeScript doesn't know the specific element type:
const canvas = document.querySelector("canvas") as HTMLCanvasElement;
const ctx = canvas.getContext("2d"); // ctx: CanvasRenderingContext2D | null ✅

// 2. JSON.parse — returns any, type must be asserted:
const data = JSON.parse(response) as ApiResponse;
// Zod or a runtime guard is better, but as is an acceptable compromise

// 3. Object.keys/entries with a known structure:
const keys = Object.keys(config) as Array<keyof typeof config>;

// 4. A legacy library with poor types:
const result = legacyLib.process(data) as ProcessedResult;
```

### When `as` Is Unacceptable

```ts
// ❌ Casting incompatible types — TypeScript blocks it:
const num = "hello" as number;
// Error: Conversion of type 'string' to type 'number' may be a mistake...

// ❌ Bypassing type checks for "convenience":
function getUser(): User {
  return {} as User; // Returns an object with no fields — runtime crash for callers
}

// ❌ as instead of a type guard — hides bugs:
function process(value: unknown) {
  (value as User).name.toUpperCase(); // Crashes if value is not User
}
```

### Double Assertion — The Nuclear Option

When types are completely incompatible, you can bridge through `unknown`:

```ts
const x = "hello" as unknown as number; // ✅ Compiles
// But this is almost always a sign of an architectural problem

// Legitimate case — mocking in tests:
const mockUser = {} as unknown as User; // Sometimes acceptable in tests
```

---

## Explicit Variance Annotations: `in` and `out` (TypeScript 4.7+)

TypeScript 4.7+ allows explicitly annotating the variance of type parameters:

```ts
// out T — T is only used as an output type (covariant):
interface Producer<out T> {
  produce(): T;
}

// in T — T is only used as an input type (contravariant):
interface Consumer<in T> {
  consume(value: T): void;
}

// Without annotations TypeScript infers variance automatically,
// but explicit annotations serve as documentation and a safety net:
const catProducer: Producer<Cat> = { produce: () => new Cat() };
const animalProducer: Producer<Animal> = catProducer; // ✅ covariance

const animalConsumer: Consumer<Animal> = { consume: (a) => console.log(a.name) };
const catConsumer: Consumer<Cat> = animalConsumer; // ✅ contravariance
```

**Why explicit annotations?** First — documentation (the reader immediately sees the intent). Second — TypeScript will error if the class/interface body violates the declared variance:

```ts
interface Producer<out T> {
  produce(): T;
  consume(value: T): void; // ❌ Type 'T' is contravariant but 'out T' requires covariant
}
```

---

## Common Interview Traps

- **"Function parameters are covariant"** — no, they are contravariant (with `strictFunctionTypes`). Return types are covariant. Mixing up the terms is a serious mistake at the senior level.

- **Not knowing the method vs function-property variance difference** — `method(x: T): void` is bivariant even with `strictFunctionTypes`. `methodFn: (x: T) => void` is contravariant. This is practically important when writing generic interfaces.

- **"Arrays in TypeScript are invariant"** — no, TypeScript allows `Cat[] extends Animal[]` (covariant), which is theoretically unsound. A runtime bug can be demonstrated by `push`ing into a shared array.

- **Confusing `satisfies` and an explicit annotation** — `const x: Config = value` changes the type of `x` to `Config`. `const x = value satisfies Config` keeps the inferred type, only verifies compatibility. This is the key distinction when working with configs.

- **Not understanding that `as const` is recursive** — `as const` applies recursively: all nested fields become `readonly` with literal types. Without `as const` — only the top-level `const` applies.

- **Thinking `as` is a safe operation** — `as` disables type checking. The only guarantee: TypeScript won't allow `as` between fully incompatible types (you need a double assertion through `unknown`). But even that can be worked around — making `as` fundamentally unsafe.

- **Not knowing the `as const satisfies` combination** — this is the modern idiomatic pattern for typed configs: get both `readonly` literal types and compatibility with the expected type.
