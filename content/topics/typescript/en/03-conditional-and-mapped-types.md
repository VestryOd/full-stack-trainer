<!-- verified: 2026-06-23, corrections: 0 -->
# Conditional and Mapped Types

## Conditional Types

A conditional type is a type-level expression that works like a ternary operator:

```ts
T extends U ? X : Y
```

Read as: "If T is compatible with U — the result is X, otherwise — Y". `extends` here checks compatibility (subtype check), not inheritance.

```ts
type IsString<T> = T extends string ? true : false;

type A = IsString<string>;  // true
type B = IsString<number>;  // false
type C = IsString<"hello">; // true — "hello" is compatible with string
```

### Why They Exist: The Problem Conditional Types Solve

Without conditional types it's impossible to express "the return type depends on the input":

```ts
// ❌ Without conditional types — must use overloads:
function unwrap(value: string): string;
function unwrap(value: number): number;
function unwrap(value: string | number): string | number { return value; }

// ✅ With conditional types — one type expresses everything:
type Unwrap<T> = T extends Promise<infer U> ? U : T;

type A = Unwrap<Promise<string>>; // string
type B = Unwrap<number>;          // number — not a Promise, returned as-is
```

### Chained Conditional Types

Like nested ternary operators:

```ts
type TypeName<T> =
  T extends string    ? "string"    :
  T extends number    ? "number"    :
  T extends boolean   ? "boolean"   :
  T extends null      ? "null"      :
  T extends undefined ? "undefined" :
  "object";

type A = TypeName<string>;    // "string"
type B = TypeName<42>;        // "number"
type C = TypeName<boolean>;   // "boolean"
type D = TypeName<() => void>;// "object"
```

---

## The `infer` Keyword

`infer` is the most powerful part of conditional types. It lets you **extract** a type from a more complex structure inside the `extends` branch.

Core principle: `infer R` creates a type variable R that TypeScript fills in during pattern matching.

```ts
// Without infer — must know the type ahead of time:
type GetPromiseValue<T> = T extends Promise<string> ? string : never;
// Only works for Promise<string>, not generic

// With infer — TypeScript infers the type:
type GetPromiseValue<T> = T extends Promise<infer R> ? R : never;

type A = GetPromiseValue<Promise<string>>;         // string
type B = GetPromiseValue<Promise<number[]>>;       // number[]
type C = GetPromiseValue<Promise<{ id: number }>>; // { id: number }
type D = GetPromiseValue<string>;                  // never — not a Promise
```

### `infer` for Functions

```ts
// Extract the parameter types of a function:
type Parameters<T extends (...args: any) => any> =
  T extends (...args: infer P) => any ? P : never;

type F = (a: string, b: number) => boolean;
type P = Parameters<F>; // [string, number] — a tuple!

// Extract the return type:
type ReturnType<T extends (...args: any) => any> =
  T extends (...args: any) => infer R ? R : never;

type R = ReturnType<F>; // boolean
```

### `infer` in Multiple Positions Simultaneously

```ts
// First and last element of a tuple:
type Head<T extends any[]> = T extends [infer H, ...any[]] ? H : never;
type Tail<T extends any[]> = T extends [...any[], infer L] ? L : never;

type H = Head<[string, number, boolean]>; // string
type L = Tail<[string, number, boolean]>; // boolean

// Function parameter and return type simultaneously:
type FunctionParts<T> = T extends (arg: infer A) => infer R
  ? { input: A; output: R }
  : never;

type Parts = FunctionParts<(x: string) => number>;
// { input: string; output: number }
```

### `infer` for Nested Structures

```ts
// The element type of an array:
type ElementOf<T> = T extends (infer E)[] ? E : never;

type E1 = ElementOf<string[]>;        // string
type E2 = ElementOf<[number, string]>; // number | string — union from tuple

// Object value type by key (alternative to indexed access):
type ValueOf<T, K extends keyof T> = T extends Record<K, infer V> ? V : never;

type User = { id: number; name: string };
type IdType = ValueOf<User, "id">; // number
```

---

## Distributive Conditional Types

This is the most non-obvious behavior of conditional types — the source of most surprises.

**Rule:** When a conditional type is applied to a **bare** (unwrapped) type parameter `T`, it automatically distributes over the members of a union:

```ts
type IsString<T> = T extends string ? true : false;

// With a union type — TypeScript applies the condition to EACH member:
type Result = IsString<string | number | boolean>;
// Equivalent to:
// IsString<string> | IsString<number> | IsString<boolean>
// = true | false | false
// = boolean
```

This is "distributivity" — like distributive multiplication in math:
`2 × (3 + 4) = 2×3 + 2×4`
`Conditional<A | B> = Conditional<A> | Conditional<B>`

### Practical Use: Exclude and Extract

```ts
// Exclude<T, U> — remove from T the members that are compatible with U:
type Exclude<T, U> = T extends U ? never : T;

type A = Exclude<string | number | boolean, number>;
// string extends number ? never : string → string
// number extends number ? never : number → never
// boolean extends number ? never : boolean → boolean
// = string | never | boolean = string | boolean ✅

// Extract<T, U> — keep only the members of T that are compatible with U:
type Extract<T, U> = T extends U ? T : never;

type B = Extract<string | number | boolean, string | boolean>;
// string extends string | boolean ? string : never → string
// number extends string | boolean ? number : never → never
// boolean extends string | boolean ? boolean : never → boolean
// = string | boolean ✅
```

### Disabling Distributivity

Sometimes you need TypeScript to treat a union as a single type, without distributing. The trick is to wrap it in a tuple:

```ts
// Distributive (distributes over the union):
type IsNever<T> = T extends never ? true : false;
type A = IsNever<never>; // boolean (not true!) — because never is an empty union

// Non-distributive (wrap in a tuple):
type IsNever<T> = [T] extends [never] ? true : false;
type B = IsNever<never>;  // true ✅
type C = IsNever<string>; // false ✅
```

Why does `T extends never` give `boolean` instead of `true`? Because `never` is the empty union. A distributive type over the empty union = the empty union = `never`. TypeScript can't compute a result for an empty union — it returns `never`. This is counter-intuitive, which is why `[T] extends [never]` is the standard pattern for checking for `never`.

---

## Mapped Types

Mapped types let you create a new type by transforming each key of an existing one:

```ts
// Syntax:
type MappedType<T> = {
  [K in keyof T]: /* new type for the value */
};
```

`K in keyof T` — iteration over the keys of T. Read as "for each key K of T".

### Modifiers: `readonly` and `?`

```ts
// Add readonly:
type Freeze<T> = { readonly [K in keyof T]: T[K] };

// Remove readonly:
type Mutable<T> = { -readonly [K in keyof T]: T[K] };

// Add optionality:
type Partial<T> = { [K in keyof T]?: T[K] };

// Remove optionality:
type Required<T> = { [K in keyof T]-?: T[K] };

// Combining:
type ReadonlyPartial<T> = { readonly [K in keyof T]?: T[K] };
```

`-readonly` and `-?` are modifier *removal* operators. TypeScript lets you explicitly add (`+?`, `+readonly`, or without `+`) and remove (`-?`, `-readonly`).

### Transforming Value Types

```ts
// Make all values nullable:
type Nullable<T> = { [K in keyof T]: T[K] | null };

// Wrap each field in a Promise:
type Promisify<T> = { [K in keyof T]: Promise<T[K]> };

// Make all values getter functions:
type Getterize<T> = { [K in keyof T]: () => T[K] };

type User = { id: number; name: string };
type GetterUser = Getterize<User>;
// { id: () => number; name: () => string }
```

---

## Key Remapping with `as`

TypeScript 4.1+ allows renaming keys in mapped types via `as`:

```ts
// Syntax:
type RemappedType<T> = {
  [K in keyof T as /* new key name */]: T[K];
};
```

### Filtering Keys via `as ... never`

If the remapping returns `never`, the key is excluded:

```ts
// Keep only string keys:
type StringKeysOnly<T> = {
  [K in keyof T as K extends string ? K : never]: T[K];
};

// Keep only fields of a specific value type:
type PickByValue<T, V> = {
  [K in keyof T as T[K] extends V ? K : never]: T[K];
};

type User = { id: number; name: string; age: number; email: string };
type StringFields = PickByValue<User, string>;
// { name: string; email: string } — string fields only ✅
```

### Renaming Keys

```ts
// Add a prefix to each key:
type Prefixed<T, P extends string> = {
  [K in keyof T as K extends string ? `${P}${Capitalize<K>}` : never]: T[K];
};

type User = { id: number; name: string };
type PrefixedUser = Prefixed<User, "user">;
// { userId: number; userName: string } ✅

// Getters:
type Getters<T> = {
  [K in keyof T as K extends string ? `get${Capitalize<K>}` : never]: () => T[K];
};

type UserGetters = Getters<User>;
// { getId: () => number; getName: () => string }
```

---

## Implementing Utility Types from Scratch via Mapped + Conditional

Demonstrating the combined use of all three mechanisms:

### NonNullable\<T\>

```ts
// Remove null and undefined from T:
type NonNullable<T> = T extends null | undefined ? never : T;

type A = NonNullable<string | null | undefined>; // string
type B = NonNullable<number | null>;             // number
```

Works via distributivity: each member of the union is checked separately.

### DeepPartial\<T\> — Recursive Partial

```ts
type DeepPartial<T> = T extends object
  ? { [K in keyof T]?: DeepPartial<T[K]> }
  : T;

type Config = {
  server: { host: string; port: number };
  db: { url: string; name: string };
};

type PartialConfig = DeepPartial<Config>;
// {
//   server?: { host?: string; port?: number };
//   db?: { url?: string; name?: string };
// }
```

### DeepReadonly\<T\>

```ts
type DeepReadonly<T> = T extends (infer U)[]
  ? ReadonlyArray<DeepReadonly<U>>
  : T extends object
  ? { readonly [K in keyof T]: DeepReadonly<T[K]> }
  : T;
```

### Flatten\<T\> — Recursively Unwrap an Array Type

```ts
type Flatten<T> = T extends (infer U)[] ? Flatten<U> : T;

type A = Flatten<number[][][]>; // number
type B = Flatten<string[]>;     // string
type C = Flatten<number>;       // number — not an array
```

### UnionToIntersection\<T\> — Advanced Pattern

Converting a union to an intersection — a trick based on function contravariance:

```ts
type UnionToIntersection<U> =
  (U extends any ? (x: U) => void : never) extends (x: infer I) => void
    ? I
    : never;

type A = UnionToIntersection<{ a: string } | { b: number }>;
// { a: string } & { b: number }
```

Why this works: when TypeScript sees `(x: U) => void` with a distributive U, it creates a union of functions. To assign a union of functions to a single function, the parameter must satisfy ALL variants — which means it must be an intersection.

---

## Combining Mapped + Conditional + Infer

In practice all three mechanisms are used together:

```ts
// An object type where each value "unwraps" its Promise:
type AwaitedValues<T> = {
  [K in keyof T]: T[K] extends Promise<infer U> ? U : T[K];
};

type AsyncUser = {
  id: Promise<number>;
  name: Promise<string>;
  role: string; // not a Promise — leave as-is
};

type SyncUser = AwaitedValues<AsyncUser>;
// { id: number; name: string; role: string } ✅

// Split an object into required and optional keys:
type RequiredKeys<T> = {
  [K in keyof T]-?: {} extends Pick<T, K> ? never : K;
}[keyof T];

type OptionalKeys<T> = {
  [K in keyof T]-?: {} extends Pick<T, K> ? K : never;
}[keyof T];

type Config = { host: string; port?: number; debug?: boolean };
type RK = RequiredKeys<Config>; // "host"
type OK = OptionalKeys<Config>; // "port" | "debug"
```

---

## Common Interview Traps

- **Not knowing about distributivity** — "Why does `type T = IsString<string | number>` equal `boolean`?" Answer: distributivity applies the conditional to each union member. This is non-obvious and frequently catches people off guard.

- **Not understanding why `T extends never` doesn't work as expected** — `never` is the empty union; a distributive type over the empty union = `never`. The standard pattern for checking: `[T] extends [never]`.

- **Confusing `infer` with a generic parameter** — `infer R` can only be used inside a conditional type in the `extends` branch. It's not a new parameter declaration — it's type extraction during pattern matching.

- **Not knowing `as` key remapping in mapped types** — before TypeScript 4.1, filtering keys required nested Omit, which is less elegant. `[K in keyof T as K extends string ? K : never]` is the standard filtering pattern.

- **Thinking `keyof T` returns an array** — no, `keyof T` returns a union: `keyof { a: 1; b: 2 }` = `"a" | "b"`. In a mapped type, `K in keyof T` iterates over this union.

- **Only knowing how to use utility types, not how to implement them** — knowing how to use `Partial<T>` doesn't demonstrate understanding. Being able to write `{ [K in keyof T]?: T[K] }` and explain each part does.

- **Writing `as const` instead of `satisfies`** — these are different tools with different guarantees (see [Variance and Assertions]).
