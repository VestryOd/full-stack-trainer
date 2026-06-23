<!-- verified: 2026-06-23, corrections: 0 -->
# Основы системы типов TypeScript

## Структурная типизация — фундаментальный выбор дизайна

TypeScript использует **структурную типизацию** (structural typing / duck typing): два типа считаются совместимыми, если их *форма* (набор полей и методов) совместима. Имя типа не имеет значения.

```txt
Структурная (TypeScript, Go):
  "Если у утки есть клюв и она крякает — это утка."
  Совместимость определяется структурой, а не именем типа.

Номинальная (Java, C#, Rust):
  "Утка — это только то, что явно объявлено как Duck."
  Два класса с идентичными полями НЕ совместимы,
  если не наследуются от общего предка.
```

Практический пример, который сначала удивляет:

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
greet(dog); // ✅ OK — TypeScript не жалуется!
```

В Java этот код не скомпилируется — `Dog` не является `Cat`. TypeScript считает типы совместимыми, потому что оба имеют поле `name: string`. Это не баг — это намеренное решение команды TS, основанное на том, как JavaScript реально используется: утиная типизация и объектные литералы — основа языка.

### Что структурная типизация означает практически

```ts
interface Printable {
  print(): void;
}

// Явной реализации интерфейса нет — и не нужно
const document = {
  title: "Report",
  print() { console.log(this.title); }
};

function printAll(items: Printable[]): void {
  items.forEach(item => item.print());
}

printAll([document]); // ✅ — document структурно совместим с Printable
```

**Ключевые следствия структурной типизации:**

```txt
1. Избыточные поля допустимы при присваивании:
   { name: string; age: number } совместим с { name: string }
   (subtype отношения — больший тип совместим с меньшим)

2. Объектные литералы — исключение (excess property check):
   TypeScript ДОПОЛНИТЕЛЬНО запрещает лишние поля в объектных
   литералах, переданных напрямую — это не структурная проверка,
   это отдельная проверка для раннего обнаружения опечаток

3. Функции проверяются структурно по параметрам:
   (x: number) => void совместима с (x: number, y: string) => void
   в некоторых контекстах — это намеренно (см. [Variance])
```

Excess property check — частый источник путаницы:

```ts
interface Options {
  timeout: number;
}

// ❌ Ошибка только при передаче объектного ЛИТЕРАЛА напрямую:
// Argument of type '{ timeout: number; retries: number; }'
// is not assignable to parameter — Object literal may only
// specify known properties
configure({ timeout: 3000, retries: 3 });

// ✅ Через переменную — проверка не срабатывает:
const opts = { timeout: 3000, retries: 3 };
configure(opts); // OK — структурно совместим
```

Это не противоречие, а два слоя: структурная проверка + отдельная "fresh object literal check" только для литералов. Понять разницу важно для интервью.

---

## Вывод типов (Type Inference) — механизм изнутри

TypeScript выводит типы на основе контекста. Важно понимать *как именно* — это объясняет многие сюрпризы.

### Расширение типа (Type Widening)

Когда TypeScript видит литеральное значение, он *расширяет* тип до базового:

```ts
let x = "hello";   // x: string (не "hello")
let n = 42;        // n: number (не 42)
let b = true;      // b: boolean (не true)

const cx = "hello"; // cx: "hello" — константа, расширения нет
const cn = 42;      // cn: 42
```

Почему `let` расширяет, а `const` — нет? Потому что `let` *может быть переприсвоен* (`x = "world"` — валидно), поэтому тип должен быть достаточно широким. `const` переприсвоить нельзя, значит тип может быть точным литеральным.

Расширение внутри объектов:

```ts
const obj = { x: 10, y: "hello" };
// obj: { x: number; y: string } — поля расширяются, даже для const
// Потому что поля объекта МОЖНО переписать: obj.x = 20 — OK

const obj2 = { x: 10, y: "hello" } as const;
// obj2: { readonly x: 10; readonly y: "hello" } — без расширения
```

### Сужение типа (Type Narrowing)

Сужение — процесс, при котором TypeScript уточняет тип в конкретной ветке кода на основе control flow анализа.

```ts
function process(value: string | number | null) {
  if (value === null) {
    // value: null — TypeScript знает точно
    return;
  }

  if (typeof value === "string") {
    // value: string — сужено
    console.log(value.toUpperCase());
  } else {
    // value: number — TypeScript вычел string и null
    console.log(value.toFixed(2));
  }
}
```

TypeScript отслеживает *control flow* (if/else, return, throw, assignments) и строит граф потока данных. Каждый узел графа имеет свой тип для каждой переменной. Это объясняет, почему TS знает тип после `if (x === null) return`:

```ts
function getLength(s: string | undefined): number {
  if (!s) return 0;
  // ↑ После этой проверки TypeScript знает: s !== undefined и s !== ""
  // Тип s здесь: string
  return s.length; // ✅
}
```

---

## type vs interface — за пределами синтаксиса

Разница не только в синтаксисе. Два принципиальных отличия:

### 1. Declaration Merging (слияние объявлений)

`interface` поддерживает слияние — несколько объявлений с одним именем автоматически объединяются:

```ts
interface User {
  id: number;
  name: string;
}

interface User {
  email: string;
}

// Итоговый тип: { id: number; name: string; email: string }
const user: User = { id: 1, name: "Alice", email: "a@b.com" };
```

`type` объявить дважды — ошибка:

```ts
type Point = { x: number };
type Point = { y: number }; // ❌ Error: Duplicate identifier 'Point'
```

**Когда слияние нужно:** расширение сторонних библиотек (module augmentation):

```ts
// Расширяем типы Express без форка библиотеки
declare module "express-serve-static-core" {
  interface Request {
    user?: { id: number; role: string };
  }
}
```

### 2. Что умеет только `type`

```ts
// Объединения (unions) — только type:
type StringOrNumber = string | number;
type Status = "pending" | "active" | "closed";

// Пересечения произвольных типов:
type AdminUser = User & { permissions: string[] };

// Tuple types:
type Pair<T, U> = [T, U];

// Условные типы:
type NonNullable<T> = T extends null | undefined ? never : T;

// Mapped types:
type Readonly<T> = { readonly [K in keyof T]: T[K] };
```

`interface` не может выразить union. Попытка — ошибка компиляции.

### Практическое правило: когда что использовать

```txt
Используй interface когда:
  - Описываешь форму объекта или класса
  - Планируешь declaration merging (библиотечный код, augmentation)
  - Хочешь более понятные сообщения об ошибках
    (interface показывает имя, type — раскрывает структуру)

Используй type когда:
  - Нужен union (string | number, "a" | "b" | "c")
  - Нужен tuple
  - Пишешь conditional или mapped types
  - Алиасируешь примитив или функцию

В большинстве команд: interface для объектов/классов, type для всего остального.
Несоблюдение одного из правил — не катастрофа, но важно знать ПОЧЕМУ есть разница.
```

Почему сообщения об ошибках отличаются:

```ts
type UserType = { id: number; name: string };
interface UserInterface { id: number; name: string }

function process(u: UserType) {}
function processI(u: UserInterface) {}

process({ id: "1", name: "Alice" });
// ❌ Argument of type '{ id: string; name: string; }' is not assignable to
//    parameter of type '{ id: number; name: string; }'. (встроенная структура)

processI({ id: "1", name: "Alice" });
// ❌ Argument of type '{ id: string; name: string; }' is not assignable to
//    parameter of type 'UserInterface'. (именованный тип — лаконичнее)
```

---

## Как TypeScript выводит типы через сложные выражения

Понимание вывода важно, когда тип "расползается" до `unknown` или `any`:

```ts
// TypeScript выводит тип возвращаемого значения из тела функции:
function add(a: number, b: number) {
  return a + b; // return type: number — выведен
}

// Но в рекурсии требует явной аннотации:
function fibonacci(n: number): number { // ← аннотация обязательна
  if (n <= 1) return n;
  return fibonacci(n - 1) + fibonacci(n - 2);
}

// Контекстуальный вывод (contextual typing):
const numbers = [1, 2, 3];
numbers.forEach(n => n.toFixed()); // n: number — выведен из типа массива
```

### Вывод через обобщения (generic inference)

TypeScript выводит параметры дженериков из аргументов функции:

```ts
function identity<T>(value: T): T {
  return value;
}

const result = identity("hello"); // T выведен как string, result: string
const result2 = identity(42);    // T выведен как number

// Вывод из нескольких аргументов — TypeScript ищет наименьший общий тип:
function pair<T>(a: T, b: T): [T, T] {
  return [a, b];
}

pair(1, 2);          // T: number ✅
pair("a", "b");      // T: string ✅
pair(1, "hello");    // T: string | number — расширяется до union
```

---

## Типичные ошибки на интервью

- **"TypeScript — номинальная типизация"** — нет, TypeScript структурно-типизированный. Два класса с одинаковой структурой совместимы, даже если у них разные имена. (Исключение: можно *симулировать* номинальную типизацию через брендирование — см. [Advanced Patterns].)

- **"type и interface — одно и то же, только синтаксис разный"** — ключевые различия: declaration merging (только interface), union types (только type). Незнание этого сигнализирует о поверхностном понимании.

- **Путать excess property check и structural compatibility** — "если я передаю объект с лишним полем, это всегда ошибка" — нет, только при передаче литерала напрямую. Через переменную — OK.

- **Не знать разницу widening для `let` vs `const`** — почему `let x = "hello"` даёт `string`, а `const x = "hello"` даёт `"hello"`. Это базовая механика, которую спрашивают на middle/senior уровне.

- **Считать, что TypeScript проверяет типы в runtime** — TypeScript — это только compile-time инструмент. В скомпилированном JavaScript нет ни одной TS-аннотации. Все гарантии — только на этапе компиляции.

- **"interface не может быть extends другого interface"** — может, это одно из главных преимуществ: `interface Admin extends User { permissions: string[] }`.
