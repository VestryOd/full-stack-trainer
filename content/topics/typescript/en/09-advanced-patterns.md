<!-- verified: 2026-06-23, corrections: 0 -->
# Advanced TypeScript Patterns

## Branded Types — Simulating Nominal Typing

TypeScript is structurally typed: `type UserId = number` and `type OrderId = number` are the same type. A function accepting `UserId` will silently accept `OrderId`. This creates an entire class of bugs that are easy to write and hard to find.

```ts
type UserId  = number;
type OrderId = number;

function getUser(id: UserId): User { /* ... */ }
function getOrder(id: OrderId): Order { /* ... */ }

const orderId: OrderId = 42;
getUser(orderId); // ✅ TypeScript sees no problem — but this is a logical bug!
```

A branded type adds a fictitious marker field that doesn't exist at runtime but makes the types incompatible to TypeScript:

```ts
type Brand<T, TBrand extends string> = T & { readonly __brand: TBrand };

type UserId  = Brand<number, "UserId">;
type OrderId = Brand<number, "OrderId">;

// Create values via constructor functions:
function UserId(id: number): UserId {
  return id as UserId;
}

function OrderId(id: number): OrderId {
  return id as OrderId;
}

function getUser(id: UserId): User { /* ... */ }
function getOrder(id: OrderId): Order { /* ... */ }

const userId  = UserId(1);
const orderId = OrderId(42);

getUser(userId);   // ✅
getUser(orderId);  // ❌ Argument of type 'OrderId' is not assignable to 'UserId'
getOrder(userId);  // ❌ Argument of type 'UserId' is not assignable to 'OrderId'
```

The `__brand` field exists only in the type — at runtime the object is a plain `number`. Zero overhead.

### When Branded Types Are Justified

```ts
// Money values — don't mix dollars and cents:
type Dollars = Brand<number, "Dollars">;
type Cents   = Brand<number, "Cents">;

function toCents(d: Dollars): Cents {
  return (d * 100) as Cents;
}

// Strings with different semantics:
type Email      = Brand<string, "Email">;
type HashedPass = Brand<string, "HashedPass">;
type JwtToken   = Brand<string, "JwtToken">;

function sendEmail(to: Email, body: string): void { /* ... */ }
function hashPassword(plain: string): HashedPass { /* ... */ }
function verifyToken(token: JwtToken): UserId { /* ... */ }

// Can't pass a raw string as Email:
sendEmail("alice@example.com", "Hello"); // ❌ string is not Email

// With validation:
function parseEmail(raw: string): Email {
  if (!raw.includes("@")) throw new Error("Invalid email");
  return raw as Email;
}

const email = parseEmail("alice@example.com"); // Email ✅
sendEmail(email, "Hello"); // ✅
```

### Multiple Brands

```ts
type NonEmptyString = Brand<string, "NonEmpty">;
type TrimmedString  = Brand<string, "Trimmed">;
type SafeUserInput  = Brand<string, "NonEmpty"> & Brand<string, "Trimmed">;

function sanitize(input: string): SafeUserInput {
  const trimmed = input.trim();
  if (!trimmed) throw new Error("Input cannot be empty");
  return trimmed as SafeUserInput;
}

// SafeUserInput is compatible with both NonEmptyString and TrimmedString individually:
function requireNonEmpty(s: NonEmptyString): void { /* ... */ }
const safe = sanitize("  hello  ");
requireNonEmpty(safe); // ✅ SafeUserInput extends NonEmptyString
```

---

## Phantom Types — Compile-Time Validation via Type Parameter

A phantom type is a generic parameter that is **not used in the value structure**, but changes the type's compatibility. It lets you encode object state in the type system.

```ts
// Encoding validation state:
type Unvalidated = "Unvalidated";
type Validated   = "Validated";

type FormData<TState> = {
  name: string;
  email: string;
  age: number;
} & { readonly __state: TState }; // phantom field

function createForm(data: { name: string; email: string; age: number }): FormData<Unvalidated> {
  return data as FormData<Unvalidated>;
}

function validate(form: FormData<Unvalidated>): FormData<Validated> {
  if (!form.name) throw new Error("Name required");
  if (!form.email.includes("@")) throw new Error("Invalid email");
  if (form.age < 0) throw new Error("Invalid age");
  return form as FormData<Validated>;
}

// Only validated data is accepted:
function submitForm(form: FormData<Validated>): void {
  // send to server
}

const raw = createForm({ name: "Alice", email: "a@b.com", age: 30 });
submitForm(raw);                   // ❌ FormData<Unvalidated> not compatible
const validated = validate(raw);
submitForm(validated);             // ✅
```

### Phantom Types for Units of Measure

```ts
type Meters    = { readonly __unit: "m" };
type Feet      = { readonly __unit: "ft" };
type Kilograms = { readonly __unit: "kg" };

type Measurement<TUnit> = number & { readonly __unit: TUnit };

function meters(n: number): Measurement<Meters> {
  return n as Measurement<Meters>;
}
function feet(n: number): Measurement<Feet> {
  return n as Measurement<Feet>;
}

function metersToFeet(m: Measurement<Meters>): Measurement<Feet> {
  return (m * 3.281) as Measurement<Feet>;
}

const height = meters(1.8);
metersToFeet(height);      // ✅
metersToFeet(feet(5.9));   // ❌ can't convert feet to feet
metersToFeet(1.8);         // ❌ plain number not accepted
```

---

## Builder Pattern with Typed Chaining

A typed Builder pattern guarantees at compile time that required fields are set before `build()` can be called.

### Basic Builder

```ts
class QueryBuilder<
  TTable extends string,
  TSelected extends string = never,
  TFiltered extends boolean = false
> {
  private _table: TTable;
  private _fields: TSelected[] = [];
  private _where: string | null = null;

  constructor(table: TTable) {
    this._table = table;
  }

  select<TFields extends string>(
    ...fields: TFields[]
  ): QueryBuilder<TTable, TSelected | TFields, TFiltered> {
    this._fields = [...this._fields, ...fields] as any;
    return this as any;
  }

  where(condition: string): QueryBuilder<TTable, TSelected, true> {
    this._where = condition;
    return this as any;
  }

  // build is only available when at least one field is selected:
  build(this: QueryBuilder<TTable, string, TFiltered>): string {
    const fields = this._fields.join(", ");
    const where = this._where ? ` WHERE ${this._where}` : "";
    return `SELECT ${fields} FROM ${this._table}${where}`;
  }
}

const query = new QueryBuilder("users")
  .select("id", "name", "email")
  .where("age > 18")
  .build(); // ✅

// Without select — build is unavailable:
const bad = new QueryBuilder("users").build();
// ❌ Argument 'this' is not assignable — TSelected is never
```

### Builder That Tracks Which Fields Have Been Set

```ts
type RequiredFields = "name" | "email" | "role";

class UserBuilder<TSet extends RequiredFields = never> {
  private data: Partial<Record<RequiredFields, string>> = {};

  setName(name: string): UserBuilder<TSet | "name"> {
    this.data.name = name;
    return this as any;
  }

  setEmail(email: string): UserBuilder<TSet | "email"> {
    this.data.email = email;
    return this as any;
  }

  setRole(role: string): UserBuilder<TSet | "role"> {
    this.data.role = role;
    return this as any;
  }

  // build is only available when all required fields are set:
  build(
    this: UserBuilder<RequiredFields>
  ): Record<RequiredFields, string> {
    return this.data as Record<RequiredFields, string>;
  }
}

const user = new UserBuilder()
  .setName("Alice")
  .setEmail("alice@example.com")
  .setRole("admin")
  .build(); // ✅

// Forgot setRole:
const incomplete = new UserBuilder()
  .setName("Bob")
  .setEmail("bob@example.com")
  .build(); // ❌ TSet = "name" | "email", not "name" | "email" | "role"
```

---

## Recursive Types

TypeScript supports recursive types — types that reference themselves. The main constraint: recursion must go through a level of indirection (via a type alias, not directly to a primitive).

### Typing JSON

```ts
type JSONPrimitive = string | number | boolean | null;
type JSONObject    = { [key: string]: JSONValue };
type JSONArray     = JSONValue[];
type JSONValue     = JSONPrimitive | JSONObject | JSONArray;

// Now we can type arbitrary JSON:
const data: JSONValue = {
  user: {
    id: 1,
    name: "Alice",
    tags: ["admin", "user"],
    meta: null,
  },
}; // ✅
```

### Deep Readonly (Recursive)

```ts
type DeepReadonly<T> =
  T extends (infer U)[]
    ? ReadonlyArray<DeepReadonly<U>>
    : T extends object
    ? { readonly [K in keyof T]: DeepReadonly<T[K]> }
    : T;

type State = {
  user: { id: number; settings: { theme: string; lang: string } };
  cart: { items: { id: number; qty: number }[] };
};

type FrozenState = DeepReadonly<State>;
// {
//   readonly user: {
//     readonly id: number;
//     readonly settings: { readonly theme: string; readonly lang: string }
//   };
//   readonly cart: {
//     readonly items: ReadonlyArray<{ readonly id: number; readonly qty: number }>
//   };
// }
```

### Recursive Tree Type

```ts
type TreeNode<T> = {
  value: T;
  children: TreeNode<T>[];
};

function mapTree<T, U>(
  node: TreeNode<T>,
  fn: (value: T) => U
): TreeNode<U> {
  return {
    value: fn(node.value),
    children: node.children.map(child => mapTree(child, fn)),
  };
}

const numTree: TreeNode<number> = {
  value: 1,
  children: [
    { value: 2, children: [] },
    { value: 3, children: [{ value: 4, children: [] }] },
  ],
};

const strTree = mapTree(numTree, n => n.toString());
// strTree: TreeNode<string> ✅
```

### Recursive Split/Join

```ts
type Split<S extends string, Sep extends string> =
  S extends `${infer Head}${Sep}${infer Tail}`
    ? [Head, ...Split<Tail, Sep>]
    : [S];

type Parts = Split<"a.b.c.d", ".">;
// ["a", "b", "c", "d"] ✅

type Join<Parts extends string[], Sep extends string> =
  Parts extends [infer Head extends string, ...infer Tail extends string[]]
    ? Tail extends []
      ? Head
      : `${Head}${Sep}${Join<Tail, Sep>}`
    : never;

type Rejoined = Join<["a", "b", "c"], "/">;
// "a/b/c" ✅
```

---

## Type-Level Programming: When to Stop

TypeScript allows remarkable things at the type level. But there are hard limits and practical considerations:

### Technical Limits

```txt
1. Recursion depth: ~100 levels
   type Infinite<T> = { value: Infinite<T> }; — hangs the compiler

2. Union size: compiler has a limit (~100k members)
   Large template literal cross-products → "too complex to represent"

3. Compile time: complex types slow the TypeScript Language Server
   IDE starts lagging on hover, autocomplete delays increase

4. Readability: nobody understands it
   type X = { [K in keyof T as K extends string
     ? T[K] extends object ? K : never : never]: ... }
   — even the author won't remember what this does in a week
```

### The Boundary: When to Use Runtime Validation (Zod and Similar)

```ts
// ❌ Trying to do everything via types — brittle and complex:
type Positive<T extends number> = T extends infer N
  ? N extends 0 ? never
  : `${N}` extends `-${string}` ? never
  : T
  : never;
// This only works for literal numbers — useless for runtime values!

// ✅ Runtime validation with Zod — checks both types AND values:
import { z } from "zod";

const UserSchema = z.object({
  id: z.number().positive(),
  name: z.string().min(1).max(100),
  email: z.string().email(),
  age: z.number().min(0).max(150),
  role: z.enum(["admin", "user", "moderator"]),
});

type User = z.infer<typeof UserSchema>;
// { id: number; name: string; email: string; age: number; role: "admin" | "user" | "moderator" }

function createUser(data: unknown): User {
  return UserSchema.parse(data); // ✅ both types and runtime validation
}
```

Zod solves a problem TypeScript cannot: **runtime data** (HTTP requests, files, localStorage) has no types. `JSON.parse()` returns `any`. Only runtime validation can guarantee that incoming data matches the expected structure.

### Pragmatic Rule

```txt
Use type-level programming when:
  - Types are derived from code (ReturnType, Parameters, infer)
  - A compile-time guarantee is needed (branded types, exhaustiveness)
  - Library/framework code for other developers (utility types)
  - Better DX: autocomplete, precise error messages

Switch to runtime validation when:
  - Data comes from outside (HTTP, files, env, localStorage)
  - Value constraints need checking, not just structure
    (email format, number > 0, non-empty string)
  - The type is too complex to maintain
  - The "smart" type only works with literals, not with runtime data
```

---

## Additional Advanced Patterns

### Opaque Type via Private Class

An alternative to branded types without `& { __brand }` — a class with a private constructor:

```ts
class UserId {
  private constructor(public readonly value: number) {}

  static create(n: number): UserId {
    if (n <= 0) throw new Error("UserId must be positive");
    return new UserId(n);
  }
}

function getUser(id: UserId): User { /* ... */ }

getUser(new UserId(1));            // ❌ constructor is private
getUser(UserId.create(1));         // ✅
getUser(42 as unknown as UserId);  // only via double assertion
```

Downside: runtime overhead from the class wrapper. Upside: the constructor can validate the value.

### Currying with Types

```ts
type Curry<Params extends unknown[], Return> =
  Params extends [infer First, ...infer Rest]
    ? (arg: First) => Curry<Rest, Return>
    : Return;

function curry<Params extends unknown[], Return>(
  fn: (...args: Params) => Return
): Curry<Params, Return> {
  return ((...args: unknown[]) => {
    if (args.length >= fn.length) return (fn as any)(...args);
    return (...more: unknown[]) => (fn as any)(...args, ...more);
  }) as any;
}

const add = curry((a: number, b: number, c: number) => a + b + c);
// add: (arg: number) => (arg: number) => (arg: number) => number

const add5    = add(5);      // (arg: number) => (arg: number) => number
const add5and3 = add5(3);   // (arg: number) => number
add5and3(2);                 // 10 ✅
```

---

## Common Interview Traps

- **"Branded types have runtime overhead"** — no. The `__brand` field exists only in the TypeScript type. The compiled JavaScript is a plain `number` or `string` — no wrapper object.

- **"Phantom types can't be implemented without a runtime field"** — they can. A field declared as `__tag!: TTag` with the `!` (definite assignment assertion) is never initialized — it's `undefined` at runtime. TypeScript uses it only for compatibility checking.

- **"Recursive types can be nested as deeply as needed"** — no, there's a limit of ~100 levels. TypeScript throws "Type instantiation is excessively deep". This is a real constraint to know when designing `DeepReadonly`, `DeepPartial`, etc.

- **Not knowing when to stop and use Zod** — TypeScript types are erased at runtime. If data comes from outside (`req.body`, `JSON.parse`), TypeScript checks nothing. Writing `const data = req.body as User` is false security. Runtime validation is required.

- **"The typed Builder pattern is overengineering"** — depends on context. For a public library or an internal DSL with many required steps — justified. For ordinary CRUD code — excessive. Being able to argue the trade-off matters more than the pattern itself.

- **Not understanding why `& { readonly __brand: T }` makes types incompatible** — it's the extra field with a unique literal type that acts as the "seal". Two different brands have different literal types in the `__brand` field, making them structurally incompatible.
