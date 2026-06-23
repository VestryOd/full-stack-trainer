<!-- verified: 2026-06-23, corrections: 0 -->
# Template Literal Types

## Синтаксис и базовая механика

Template literal types (TypeScript 4.1+) — это типы, которые строятся как JavaScript template literals, но на уровне типов:

```ts
type Greeting = `Hello, ${string}`;

const a: Greeting = "Hello, Alice";  // ✅
const b: Greeting = "Hello, ";       // ✅ — string может быть пустым
const c: Greeting = "Hi, Alice";     // ❌ — не начинается с "Hello, "
```

Интерполяция поддерживает: `string`, `number`, `boolean`, `bigint`, `null`, `undefined`, а также их union-ы:

```ts
type Version = `v${number}`;
type V1 = Version; // `v${number}`

const x: Version = "v1";    // ✅
const y: Version = "v2.5";  // ❌ — 2.5 это number, но "v2.5" не соответствует `v${number}`
                              //     потому что number → "2", не "2.5" в template literal
const z: Version = "v42";   // ✅
```

Важный нюанс: `${number}` соответствует строковому представлению любого числа (включая дробные — `"3.14"`), `${boolean}` соответствует `"true"` и `"false"`.

---

## Комбинирование с union types

Когда в интерполяцию подставляется union, TypeScript перемножает все комбинации — это ключевая мощь template literal types:

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

Несколько union-ов перемножаются:

```ts
type Axis = "x" | "y";
type Scale = "sm" | "md" | "lg";
type SpacingKey = `space-${Axis}-${Scale}`;
// "space-x-sm" | "space-x-md" | "space-x-lg" |
// "space-y-sm" | "space-y-md" | "space-y-lg"
```

Это позволяет выразить целые пространства допустимых строк без перечисления каждой вручную.

---

## Встроенные строковые утилиты

TypeScript предоставляет четыре утилиты для работы с регистром:

```ts
type U = Uppercase<"hello">;    // "HELLO"
type L = Lowercase<"WORLD">;    // "world"
type C = Capitalize<"hello">;   // "Hello"
type UC = Uncapitalize<"Hello">; // "hello"
```

Они работают и с union-ами:

```ts
type EventName = "click" | "focus" | "blur";
type HandlerName = `on${Capitalize<EventName>}`;
// "onClick" | "onFocus" | "onBlur"
```

---

## Практика 1: типизированные имена событий

Система событий без template literal types теряет точность:

```ts
// ❌ Принимает любую строку — опечатки не поймать:
declare function on(event: string, handler: () => void): void;
on("clik", () => {}); // опечатка, TypeScript молчит

// ✅ С template literal type — только валидные имена:
type DOMEvent = "click" | "focus" | "blur" | "change" | "submit";
type EventHandler = `on${Capitalize<DOMEvent>}`;

declare function on(event: DOMEvent, handler: () => void): void;
on("clik", () => {}); // ❌ Argument of type '"clik"' is not assignable
on("click", () => {}); // ✅
```

### Типизированный EventEmitter

```ts
type EventMap = {
  userCreated: { id: number; name: string };
  userDeleted: { id: number };
  orderPlaced: { orderId: string; total: number };
};

type EventName = keyof EventMap;

class TypedEmitter<Events extends Record<string, unknown>> {
  on<K extends keyof Events>(
    event: K,
    handler: (data: Events[K]) => void
  ): void {
    // реализация
  }

  emit<K extends keyof Events>(event: K, data: Events[K]): void {
    // реализация
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

## Практика 2: типизированные параметры маршрутов

Извлечение параметров из строки пути — классический use-case для `infer` + template literal:

```ts
// Извлечь имена параметров из пути вида "/users/:id/posts/:postId":
type ExtractParams<Path extends string> =
  Path extends `${string}:${infer Param}/${infer Rest}`
    ? Param | ExtractParams<`/${Rest}`>
    : Path extends `${string}:${infer Param}`
    ? Param
    : never;

type A = ExtractParams<"/users/:id">;                    // "id"
type B = ExtractParams<"/users/:id/posts/:postId">;      // "id" | "postId"
type C = ExtractParams<"/users/:id/posts/:postId/likes">; // "id" | "postId"

// Построить объект параметров из пути:
type RouteParams<Path extends string> = {
  [K in ExtractParams<Path>]: string;
};

type UserPostParams = RouteParams<"/users/:id/posts/:postId">;
// { id: string; postId: string }
```

### Типизированный router

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
  // реализация
}

navigate("/users/:id", { id: "123" });          // ✅
navigate("/users/:id");                          // ❌ missing params
navigate("/search");                             // ✅ — без params
navigate("/users/:id", { id: "1", extra: "x" }); // ❌ лишнее поле
```

---

## Практика 3: типизированные ключи доступа к вложенным объектам

"Dot notation" для вложенных объектов — популярная задача на интервью:

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

Получить тип значения по dot-path:

```ts
type DeepGet<T, Path extends string> =
  Path extends `${infer Key}.${infer Rest}`
    ? Key extends keyof T
      ? DeepGet<T[Key], Rest>
      : never
    : Path extends keyof T
    ? T[Path]
    : never;

type HostType = DeepGet<Config, "server.host">; // string ✅
type PortType = DeepGet<Config, "server.port">; // number ✅
type Wrong   = DeepGet<Config, "server.missing">; // never ✅
```

---

## Практика 4: CSS-in-JS типобезопасность

```ts
type CSSProperty =
  | "margin" | "padding" | "border"
  | "background" | "color" | "font";

type CSSDirection = "top" | "right" | "bottom" | "left";

type DirectionalProperty = `${Extract<CSSProperty, "margin" | "padding" | "border">}-${CSSDirection}`;
// "margin-top" | "margin-right" | ... | "padding-top" | ... | "border-top" | ...

// Типизированные CSS переменные:
type CSSVar<T extends string> = `--${T}`;
type ThemeVar = CSSVar<"color-primary" | "color-secondary" | "spacing-md">;
// "--color-primary" | "--color-secondary" | "--spacing-md"

// Typed className builder:
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

## Практика 5: типизированные query-параметры и API

```ts
// HTTP методы + пути → типы запроса и ответа:
type ApiRoutes = {
  "GET /users": { response: { users: User[] } };
  "GET /users/:id": { params: { id: string }; response: User };
  "POST /users": { body: { name: string; email: string }; response: User };
  "DELETE /users/:id": { params: { id: string }; response: void };
};

type HttpMethod = "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
type RoutePath<R extends string> = R extends `${HttpMethod} ${infer P}` ? P : never;

type RouteMethod<R extends string> = R extends `${infer M} ${string}`
  ? M extends HttpMethod ? M : never
  : never;

// Автоматическое типизирование fetch-обёртки:
async function apiFetch<R extends keyof ApiRoutes>(
  route: R,
  options?: Omit<ApiRoutes[R], "response">
): Promise<ApiRoutes[R] extends { response: infer Res } ? Res : never> {
  // реализация
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

## Практика 6: типизированные переводы (i18n)

```ts
type Translations = {
  "user.greeting": "Hello, {name}!";
  "user.farewell": "Goodbye, {name}!";
  "error.notFound": "Resource {resource} not found.";
  "items.count": "You have {count} items.";
};

// Извлечь имена placeholder-ов из строки перевода:
type ExtractPlaceholders<S extends string> =
  S extends `${string}{${infer P}}${infer Rest}`
    ? P | ExtractPlaceholders<Rest>
    : never;

type GreetingParams = ExtractPlaceholders<"Hello, {name}!">; // "name"
type ErrorParams = ExtractPlaceholders<"Resource {resource} not found.">; // "resource"

// Типизированная функция перевода:
function t<K extends keyof Translations>(
  key: K,
  params: Record<ExtractPlaceholders<Translations[K]>, string>
): string {
  // реализация
  return key;
}

t("user.greeting", { name: "Alice" });          // ✅
t("user.greeting", { name: "Alice", extra: "x" }); // ❌ лишнее поле
t("error.notFound", {});                         // ❌ missing resource
```

---

## Взаимодействие с `infer` внутри template literal

`infer` можно использовать прямо внутри шаблонного паттерна для разбора строки:

```ts
// Разобрать "key=value" строку:
type ParseKV<S extends string> =
  S extends `${infer K}=${infer V}` ? { key: K; value: V } : never;

type P = ParseKV<"host=localhost">; // { key: "host"; value: "localhost" }

// Извлечь расширение файла:
type FileExt<S extends string> =
  S extends `${string}.${infer Ext}` ? Ext : never;

type E = FileExt<"report.pdf">;    // "pdf"
type E2 = FileExt<"style.min.css">; // "css" — последнее расширение

// Убрать префикс:
type StripPrefix<S extends string, P extends string> =
  S extends `${P}${infer Rest}` ? Rest : S;

type Stripped = StripPrefix<"on_click", "on_">; // "click"
```

---

## Ограничения template literal types

Важно знать, где механизм ломается:

```ts
// 1. Типы слишком широкого string — не дают паттерна:
type Dynamic = `prefix_${string}`;
// Любая строка с prefix_ — нет дискриминации значений

// 2. Комбинаторный взрыв — TypeScript может не справиться:
type BigUnion = "a" | "b" | "c" | "d" | "e" | "f" | "g" | "h";
type Combo = `${BigUnion}-${BigUnion}-${BigUnion}`;
// 8 × 8 × 8 = 512 членов — TypeScript справится
// Но при очень больших union-ах получим ошибку:
// "Expression produces a union type that is too complex to represent"

// 3. Рекурсия имеет предел глубины:
// TypeScript ограничивает глубину рекурсивных типов (~100 уровней)
// DeepGet и ExtractParams работают для реальных путей, но не для произвольной глубины

// 4. infer извлекает "минимальный" тип:
type Split<S extends string> = S extends `${infer Head},${infer Tail}`
  ? [Head, ...Split<Tail>]
  : [S];

type Parts = Split<"a,b,c">; // ["a", "b", "c"] ✅ — работает в рекурсии
```

---

## Типичные ошибки на интервью

- **"Template literal types работают как регулярные выражения"** — не совсем: они работают с фиксированными паттернами и union-ами, но не поддерживают квантификаторы (`*`, `+`, `?`). `${string}` соответствует любой строке (включая пустую), но нет аналогов "один или более символов".

- **Не знать про комбинаторный взрыв** — если два union по 10 элементов перемножаются в шаблоне, получается 100 членов. TypeScript имеет лимит и выдаёт ошибку "too complex to represent". Это реальное ограничение, которое нужно знать.

- **Путать template literal TYPE и template literal STRING** — `` `Hello, ${name}` `` в JS — строка. `` `Hello, ${string}` `` в TS — тип. Контекст использования разный, синтаксис похожий.

- **Не использовать `Capitalize`/`Uppercase` при генерации имён** — типичная задача "сгенерировать `onClick` из `click`" решается за одну строку: `` `on${Capitalize<EventName>}` ``. Незнание встроенных утилит — потеря баллов.

- **Забыть про рекурсию для вложенных паттернов** — разобрать `"/users/:id/posts/:postId"` за один `infer` нельзя. Нужна рекурсия: извлечь первый параметр, потом применить тип к хвосту строки.

- **Не знать, что TypeScript 4.1 — это важная версия** — template literal types появились именно тогда. До 4.1 все паттерны на строках были невозможны. Знание версии показывает понимание истории языка.
