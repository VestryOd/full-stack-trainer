<!-- verified: 2026-06-23, corrections: 0 -->
# Template Literal Types

## Syntax and Core Mechanics

Template literal types (TypeScript 4.1+) are types built like JavaScript template literals, but at the type level:

```ts
type Greeting = `Hello, ${string}`;

const a: Greeting = "Hello, Alice";  // ✅
const b: Greeting = "Hello, ";       // ✅ — string can be empty
const c: Greeting = "Hi, Alice";     // ❌ — doesn't start with "Hello, "
```

Interpolation supports: `string`, `number`, `boolean`, `bigint`, `null`, `undefined`, and their unions:

```ts
type Version = `v${number}`;

const x: Version = "v1";    // ✅
const y: Version = "v2.5";  // ❌ — 2.5 is a number, but "v2.5" doesn't match `v${number}`
                              //     because number → "2", not "2.5" in template literals
const z: Version = "v42";   // ✅
```

Important nuance: `${number}` matches the string representation of any number (including decimals — `"3.14"`), `${boolean}` matches `"true"` and `"false"`.

---

## Combining with Union Types

When a union is substituted into an interpolation slot, TypeScript cross-multiplies all combinations — this is the core power of template literal types:

```ts
type Direction = "top" | "right" | "bottom" | "left";
type Margin = `margin-${Direction}`;
// "margin-top" | "margin-right" | "margin-bottom" | "margin-left"

type Color = "red" | "green" | "blue";
type Shade = "light" | "dark";
type ThemedColor = `${Shade}-${Color}`;
// "light-red" | "light-green" | "light-blue" |
// "dark-red"  | "dark-green"  | "dark-blue"
```

Multiple unions are cross-multiplied:

```ts
type Axis = "x" | "y";
type Scale = "sm" | "md" | "lg";
type SpacingKey = `space-${Axis}-${Scale}`;
// "space-x-sm" | "space-x-md" | "space-x-lg" |
// "space-y-sm" | "space-y-md" | "space-y-lg"
```

This lets you express entire spaces of valid strings without listing each one manually.

---

## Built-in String Utilities

TypeScript provides four utilities for case manipulation:

```ts
type U = Uppercase<"hello">;     // "HELLO"
type L = Lowercase<"WORLD">;     // "world"
type C = Capitalize<"hello">;    // "Hello"
type UC = Uncapitalize<"Hello">; // "hello"
```

They work with unions too:

```ts
type EventName = "click" | "focus" | "blur";
type HandlerName = `on${Capitalize<EventName>}`;
// "onClick" | "onFocus" | "onBlur"
```

---

## Use Case 1: Typed Event Names

An event system without template literal types loses precision:

```ts
// ❌ Accepts any string — typos go uncaught:
declare function on(event: string, handler: () => void): void;
on("clik", () => {}); // typo, TypeScript is silent

// ✅ With template literal type — only valid names:
type DOMEvent = "click" | "focus" | "blur" | "change" | "submit";

declare function on(event: DOMEvent, handler: () => void): void;
on("clik", () => {}); // ❌ Argument of type '"clik"' is not assignable
on("click", () => {}); // ✅
```

### Typed EventEmitter

```ts
type EventMap = {
  userCreated: { id: number; name: string };
  userDeleted: { id: number };
  orderPlaced: { orderId: string; total: number };
};

class TypedEmitter<Events extends Record<string, unknown>> {
  on<K extends keyof Events>(
    event: K,
    handler: (data: Events[K]) => void
  ): void {
    // implementation
  }

  emit<K extends keyof Events>(event: K, data: Events[K]): void {
    // implementation
  }
}

const emitter = new TypedEmitter<EventMap>();

emitter.on("userCreated", (data) => {
  console.log(data.id, data.name); // data: { id: number; name: string } ✅
});

emitter.emit("orderPlaced", { orderId: "123", total: 99.99 }); // ✅
emitter.emit("orderPlaced", { orderId: "123" }); // ❌ missing total
```

---

## Use Case 2: Typed Route Parameters

Extracting parameters from a path string — the classic use case for `infer` + template literals:

```ts
// Extract parameter names from a path like "/users/:id/posts/:postId":
type ExtractParams<Path extends string> =
  Path extends `${string}:${infer Param}/${infer Rest}`
    ? Param | ExtractParams<`/${Rest}`>
    : Path extends `${string}:${infer Param}`
    ? Param
    : never;

type A = ExtractParams<"/users/:id">;                    // "id"
type B = ExtractParams<"/users/:id/posts/:postId">;      // "id" | "postId"
type C = ExtractParams<"/users/:id/posts/:postId/likes">; // "id" | "postId"

// Build a params object type from a path:
type RouteParams<Path extends string> = {
  [K in ExtractParams<Path>]: string;
};

type UserPostParams = RouteParams<"/users/:id/posts/:postId">;
// { id: string; postId: string }
```

### Typed Router

```ts
type Routes = {
  "/users/:id": { id: string };
  "/users/:id/posts/:postId": { id: string; postId: string };
  "/search": Record<string, never>;
};

function navigate<R extends keyof Routes>(
  route: R,
  ...params: Routes[R] extends Record<string, never>
    ? []
    : [params: Routes[R]]
): void {
  // implementation
}

navigate("/users/:id", { id: "123" });           // ✅
navigate("/users/:id");                           // ❌ missing params
navigate("/search");                              // ✅ — no params needed
navigate("/users/:id", { id: "1", extra: "x" }); // ❌ excess property
```

---

## Use Case 3: Typed Nested Object Access (Dot Notation)

"Dot notation" for nested objects — a popular interview problem:

```ts
type DotPath<T, Prefix extends string = ""> =
  T extends object
    ? {
        [K in keyof T]: K extends string
          ? Prefix extends ""
            ? DotPath<T[K], K> | K
            : DotPath<T[K], `${Prefix}.${K}`> | `${Prefix}.${K}`
          : never;
      }[keyof T]
    : Prefix;

type Config = {
  server: {
    host: string;
    port: number;
  };
  db: {
    url: string;
  };
};

type ConfigPaths = DotPath<Config>;
// "server" | "db" | "server.host" | "server.port" | "db.url"
```

Get the value type at a dot path:

```ts
type DeepGet<T, Path extends string> =
  Path extends `${infer Key}.${infer Rest}`
    ? Key extends keyof T
      ? DeepGet<T[Key], Rest>
      : never
    : Path extends keyof T
    ? T[Path]
    : never;

type HostType = DeepGet<Config, "server.host">;    // string ✅
type PortType = DeepGet<Config, "server.port">;    // number ✅
type Wrong    = DeepGet<Config, "server.missing">; // never ✅
```

---

## Use Case 4: CSS-in-JS Type Safety

```ts
type CSSProperty =
  | "margin" | "padding" | "border"
  | "background" | "color" | "font";

type CSSDirection = "top" | "right" | "bottom" | "left";

type DirectionalProperty = `${Extract<CSSProperty, "margin" | "padding" | "border">}-${CSSDirection}`;
// "margin-top" | "margin-right" | ... | "padding-top" | ... | "border-top" | ...

// Typed CSS variables:
type CSSVar<T extends string> = `--${T}`;
type ThemeVar = CSSVar<"color-primary" | "color-secondary" | "spacing-md">;
// "--color-primary" | "--color-secondary" | "--spacing-md"

// Typed BEM className builder:
type BEMBlock = "button" | "card" | "modal";
type BEMElement = "title" | "body" | "footer" | "icon";
type BEMModifier = "primary" | "disabled" | "large";

type BEMClass =
  | BEMBlock
  | `${BEMBlock}__${BEMElement}`
  | `${BEMBlock}--${BEMModifier}`
  | `${BEMBlock}__${BEMElement}--${BEMModifier}`;

const cls: BEMClass = "button__icon--disabled"; // ✅
const bad: BEMClass = "button__missing";        // ❌
```

---

## Use Case 5: Typed Query Parameters and API

```ts
// HTTP methods + paths → request and response types:
type ApiRoutes = {
  "GET /users": { response: { users: User[] } };
  "GET /users/:id": { params: { id: string }; response: User };
  "POST /users": { body: { name: string; email: string }; response: User };
  "DELETE /users/:id": { params: { id: string }; response: void };
};

type HttpMethod = "GET" | "POST" | "PUT" | "DELETE" | "PATCH";

// Typed fetch wrapper:
async function apiFetch<R extends keyof ApiRoutes>(
  route: R,
  options?: Omit<ApiRoutes[R], "response">
): Promise<ApiRoutes[R] extends { response: infer Res } ? Res : never> {
  // implementation
  throw new Error("not implemented");
}

const users = await apiFetch("GET /users");
// users: { users: User[] } ✅

const user = await apiFetch("POST /users", {
  body: { name: "Alice", email: "a@b.com" }
});
// user: User ✅
```

---

## Use Case 6: Typed i18n Translations

```ts
type Translations = {
  "user.greeting": "Hello, {name}!";
  "user.farewell": "Goodbye, {name}!";
  "error.notFound": "Resource {resource} not found.";
  "items.count": "You have {count} items.";
};

// Extract placeholder names from a translation string:
type ExtractPlaceholders<S extends string> =
  S extends `${string}{${infer P}}${infer Rest}`
    ? P | ExtractPlaceholders<Rest>
    : never;

type GreetingParams = ExtractPlaceholders<"Hello, {name}!">; // "name"
type ErrorParams = ExtractPlaceholders<"Resource {resource} not found.">; // "resource"

// Typed translation function:
function t<K extends keyof Translations>(
  key: K,
  params: Record<ExtractPlaceholders<Translations[K]>, string>
): string {
  // implementation
  return key;
}

t("user.greeting", { name: "Alice" });               // ✅
t("user.greeting", { name: "Alice", extra: "x" });   // ❌ excess property
t("error.notFound", {});                              // ❌ missing resource
```

---

## Using `infer` Inside Template Literal Patterns

`infer` can be used directly inside a template pattern to parse a string:

```ts
// Parse a "key=value" string:
type ParseKV<S extends string> =
  S extends `${infer K}=${infer V}` ? { key: K; value: V } : never;

type P = ParseKV<"host=localhost">; // { key: "host"; value: "localhost" }

// Extract a file extension:
type FileExt<S extends string> =
  S extends `${string}.${infer Ext}` ? Ext : never;

type E  = FileExt<"report.pdf">;     // "pdf"
type E2 = FileExt<"style.min.css">;  // "css" — the last extension

// Strip a prefix:
type StripPrefix<S extends string, P extends string> =
  S extends `${P}${infer Rest}` ? Rest : S;

type Stripped = StripPrefix<"on_click", "on_">; // "click"
```

---

## Limitations of Template Literal Types

Important to know where the mechanism breaks down:

```ts
// 1. Overly wide string types — no pattern discrimination:
type Dynamic = `prefix_${string}`;
// Any string starting with "prefix_" — no discrimination between values

// 2. Combinatorial explosion — TypeScript may give up:
type BigUnion = "a" | "b" | "c" | "d" | "e" | "f" | "g" | "h";
type Combo = `${BigUnion}-${BigUnion}-${BigUnion}`;
// 8 × 8 × 8 = 512 members — TypeScript handles this
// But with very large unions you get:
// "Expression produces a union type that is too complex to represent"

// 3. Recursion has a depth limit:
// TypeScript limits recursive type depth (~100 levels)
// DeepGet and ExtractParams work for real paths, but not arbitrary depth

// 4. infer extracts the "minimum" matching type:
type Split<S extends string> = S extends `${infer Head},${infer Tail}`
  ? [Head, ...Split<Tail>]
  : [S];

type Parts = Split<"a,b,c">; // ["a", "b", "c"] ✅ — works recursively
```

---

## Common Interview Traps

- **"Template literal types work like regular expressions"** — not quite: they work with fixed patterns and unions, but don't support quantifiers (`*`, `+`, `?`). `${string}` matches any string (including empty), but there's no equivalent for "one or more characters".

- **Not knowing about combinatorial explosion** — if two unions of 10 elements each are cross-multiplied in a template, you get 100 members. TypeScript has a limit and throws "too complex to represent". This is a real limitation worth knowing.

- **Confusing a template literal TYPE with a template literal STRING** — `` `Hello, ${name}` `` in JS is a string. `` `Hello, ${string}` `` in TS is a type. Different usage context, similar syntax.

- **Not using `Capitalize`/`Uppercase` when generating names** — the classic "generate `onClick` from `click`" problem is one line: `` `on${Capitalize<EventName>}` ``. Not knowing the built-in utilities is a missed point.

- **Forgetting recursion for nested patterns** — parsing `"/users/:id/posts/:postId"` with a single `infer` is impossible. You need recursion: extract the first parameter, then apply the type to the rest of the string.

- **Not knowing that TypeScript 4.1 is a significant version** — template literal types were introduced then. Before 4.1, all string patterns were impossible. Knowing the version shows understanding of the language's history.
