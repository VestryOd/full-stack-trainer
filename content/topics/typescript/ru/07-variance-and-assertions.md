<!-- verified: 2026-06-23, corrections: 0 -->
# Вариантность и утверждения типов

## Что такое вариантность

Вариантность описывает, как отношение подтипирования между простыми типами (например, `Cat extends Animal`) переносится на сложные типы, которые их содержат (например, `Box<Cat>` и `Box<Animal>`, или `(x: Cat) => void` и `(x: Animal) => void`).

Четыре вида:

```txt
Ковариантность (covariance):
  Cat extends Animal → Box<Cat> extends Box<Animal>
  "направление подтипирования сохраняется"

Контравариантность (contravariance):
  Cat extends Animal → Handler<Animal> extends Handler<Cat>
  "направление подтипирования переворачивается"

Инвариантность (invariance):
  Cat extends Animal НЕ означает ни того, ни другого
  Box<Cat> и Box<Animal> — несовместимы

Бивариантность (bivariance):
  Cat extends Animal → верно И Box<Cat> extends Box<Animal>,
                          И Box<Animal> extends Box<Cat>
  (принимается в любом направлении)
```

Понять, почему функциональные типы ведут себя именно так — ключевое требование для senior-уровня.

---

## Ковариантность: возвращаемые значения функций

Возвращаемый тип функции **ковариантен**: если функция возвращает подтип — она совместима там, где ожидается функция, возвращающая супертип.

```ts
class Animal { name: string = "" }
class Cat extends Animal { meow(): void {} }

// Функция, возвращающая Cat, совместима там, где ожидается Animal:
type AnimalFactory = () => Animal;
type CatFactory = () => Cat;

const makeCat: CatFactory = () => new Cat();
const makeAnimal: AnimalFactory = makeCat; // ✅ ковариантность

// Почему это логично:
// Если я ожидаю () => Animal, а получаю () => Cat —
// это нормально: Cat IS-A Animal, у него есть всё, что нужно
```

```txt
Возвращаемые типы:
  Cat IS-A Animal
  → (() => Cat) IS-A (() => Animal)
  Направление сохраняется ✅
```

---

## Контравариантность: параметры функций

Параметры функции **контравариантны**: если функция принимает супертип — она совместима там, где ожидается функция, принимающая подтип.

```ts
type AnimalHandler = (animal: Animal) => void;
type CatHandler = (cat: Cat) => void;

function feedAnimal(animal: Animal): void {
  console.log(animal.name);
}

function feedCat(cat: Cat): void {
  cat.meow(); // Использует Cat-специфичный метод!
}

// Функция с более широким параметром совместима там,
// где ожидается функция с более узким параметром:
const handler: CatHandler = feedAnimal; // ✅ контравариантность

// А наоборот — нет:
const handler2: AnimalHandler = feedCat; // ❌ UNSAFE!
```

**Почему `AnimalHandler = feedCat` опасно:**

```ts
const allAnimals: Animal[] = [new Animal(), new Cat()];
allAnimals.forEach(handler2); // handler2 = feedCat
// feedCat вызовет cat.meow() на Animal, у которого нет meow() → runtime crash!
```

**Почему `CatHandler = feedAnimal` безопасно:**

```ts
const cats: Cat[] = [new Cat()];
cats.forEach(handler); // handler = feedAnimal
// feedAnimal вызовет animal.name — это есть у Cat (наследует от Animal) ✅
```

```txt
Параметры функции:
  Cat IS-A Animal
  → (Animal) => void IS-A (Cat) => void
  Направление ПЕРЕВОРАЧИВАЕТСЯ ✅
```

Мнемоника: "принять больше — можешь заменить везде, где принимают меньше". Функция, которая умеет работать с любым `Animal`, точно справится с `Cat`.

---

## Проблема бивариантности в TypeScript: методы

TypeScript исторически проверяет параметры методов **бивариантно** (в обоих направлениях), а не контравариантно. Это нарушение корректной системы типов, оставленное ради совместимости:

```ts
interface Comparer<T> {
  compare(a: T, b: T): number; // метод — бивариантен (НЕБЕЗОПАСНО)
  compareArrow: (a: T, b: T) => number; // свойство-функция — контравариантно (БЕЗОПАСНО)
}

// С методом TypeScript принимает оба направления:
const catComparer: Comparer<Cat> = {
  compare(a: Animal, b: Animal) { return 0; } // ✅ — контравариантно, OK
};

const animalComparer: Comparer<Animal> = {
  compare(a: Cat, b: Cat) { return 0; } // ✅ — TypeScript принимает! Но это UNSAFE
};
```

**`strictFunctionTypes` (часть `strict`)** — исправляет это для функций-свойств, но **не для методов**:

```ts
// С strictFunctionTypes:
interface Handler<T> {
  handle(value: T): void;          // метод — БИВАРИАНТЕН (даже с strictFunctionTypes)
  handleFn: (value: T) => void;    // свойство-функция — КОНТРАВАРИАНТНА (проверяется корректно)
}

type CatHandlerFn = (cat: Cat) => void;
type AnimalHandlerFn = (animal: Animal) => void;

// Для функций-свойств (с strictFunctionTypes):
const h: CatHandlerFn = (a: Animal) => {}; // ✅ контравариантность, OK
const h2: AnimalHandlerFn = (c: Cat) => {}; // ❌ Error: strictFunctionTypes работает
```

Это важно знать: если хотите корректную контравариантность — используйте `handleFn: (v: T) => void` вместо `handle(v: T): void`.

---

## Инвариантность и её причины

Некоторые типы инвариантны — ни ковариантность, ни контравариантность не применяются. Классический пример — изменяемые массивы:

```ts
// Теоретически массивы ковариантны в TypeScript:
const cats: Cat[] = [new Cat()];
const animals: Animal[] = cats; // ✅ TypeScript разрешает (но это UNSAFE!)

animals.push(new Animal()); // animals и cats — один массив в памяти!
cats[1].meow(); // runtime crash: Animal не имеет meow() ❌
```

TypeScript разрешает это в угоду практичности (Kotlin, Java имеют ту же проблему с массивами). Для корректного кода нужен `ReadonlyArray`:

```ts
const cats: ReadonlyArray<Cat> = [new Cat()];
const animals: ReadonlyArray<Animal> = cats; // ✅ — безопасно: нельзя push
```

**Реальная инвариантность** появляется в TypeScript при использовании `in`-позиций и `out`-позиций одновременно:

```ts
// Класс с методом set и get — инвариантен по T:
interface Box<T> {
  get(): T;   // out-позиция → ковариантна по T
  set(v: T): void; // in-позиция → контравариантна по T
  // в итоге — инвариантна: ни Box<Cat> не является Box<Animal>,
  // ни Box<Animal> не является Box<Cat>
}
```

---

## `as const` — зафиксировать тип максимально точно

`as const` говорит TypeScript: "вывести самый узкий возможный тип для этого значения":

```ts
// Без as const — типы расширяются:
const config = {
  host: "localhost",
  port: 3000,
  env: "production"
};
// config: { host: string; port: number; env: string }
// — поля можно менять, типы широкие

// С as const — всё readonly и литеральные типы:
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

**Как это работает на разных уровнях:**

```ts
// Примитив:
let x = "hello" as const; // x: "hello" (не string)

// Массив:
const arr = [1, 2, 3] as const;
// arr: readonly [1, 2, 3] — tuple, не number[]

// Объект (рекурсивно):
const nested = { a: { b: "value" } } as const;
// nested: { readonly a: { readonly b: "value" } }

// Перечисление значений через as const:
const Direction = {
  Up: "UP",
  Down: "DOWN",
  Left: "LEFT",
  Right: "RIGHT",
} as const;

type Direction = typeof Direction[keyof typeof Direction];
// "UP" | "DOWN" | "LEFT" | "RIGHT"
// Это паттерн "const enum alternative" — безопаснее, чем enum
```

**Когда `as const` реально нужен:**

```ts
// 1. Discriminated union из массива:
const STATUSES = ["pending", "active", "closed"] as const;
type Status = typeof STATUSES[number]; // "pending" | "active" | "closed"

// Без as const:
const STATUSES = ["pending", "active", "closed"];
type Status = typeof STATUSES[number]; // string — бесполезно

// 2. Передача в функцию, ожидающую literal type:
function setDirection(dir: "UP" | "DOWN") {}
const dir = "UP";          // dir: string — слишком широко
setDirection(dir);         // ❌ Argument of type 'string' is not assignable to...

const dir2 = "UP" as const; // dir2: "UP"
setDirection(dir2);         // ✅
```

---

## `satisfies` — проверка типа без потери точности (TypeScript 4.9+)

`satisfies` — оператор, который проверяет, что значение совместимо с типом, но **не сужает** его до этого типа. Тип остаётся выведенным, TypeScript просто гарантирует соответствие.

```ts
type ColorMap = Record<string, string | [number, number, number]>;

// ❌ Явная аннотация — теряем точный тип:
const palette: ColorMap = {
  red: [255, 0, 0],
  green: "#00ff00",
  blue: [0, 0, 255],
};
// palette.red: string | [number, number, number]
// Нельзя вызвать palette.red.map(...) без проверки

// ✅ satisfies — проверяем соответствие, сохраняем точные типы:
const palette = {
  red: [255, 0, 0],
  green: "#00ff00",
  blue: [0, 0, 255],
} satisfies ColorMap;

palette.red;   // [number, number, number] ✅ — точный тип!
palette.green; // string ✅ — точный тип!
palette.red.map(v => v * 2); // ✅ — знаем, что это массив
palette.green.toUpperCase(); // ✅ — знаем, что это строка

// Проверка типа работает — лишние ключи запрещены:
const bad = {
  red: "not a valid color", // ❌ "not a valid color" не совместим...
  // wait, string IS совместима с string | [number, number, number]
  // satisfies проверяет структурную совместимость ✅
};
```

### `satisfies` vs явная аннотация vs `as`

```ts
type Config = { port: number; host: string };

// 1. Явная аннотация — тип становится Config, детали теряются:
const c1: Config = { port: 3000, host: "localhost" };
// c1: Config — нет информации о конкретных значениях

// 2. satisfies — тип остаётся точным, совместимость проверена:
const c2 = { port: 3000, host: "localhost" } satisfies Config;
// c2: { port: number; host: string } — тот же эффект, что и аннотация,
// но TypeScript может хранить информацию об определённых литеральных значениях

// 3. as — НЕ проверяет совместимость, просто утверждает:
const c3 = { port: 3000 } as Config; // ❌ Нет host, но TypeScript молчит!
// c3: Config — TypeScript доверяет нам, даже если мы ошиблись

// 4. as const + satisfies — лучший вариант для конфигов:
const c4 = {
  port: 3000,
  host: "localhost",
} as const satisfies Config;
// c4: { readonly port: 3000; readonly host: "localhost" }
// — и точный тип, и проверка соответствия, и readonly
```

**Таблица выбора:**

```txt
Задача                                          Инструмент
──────────────────────────────────────────────────────────────────
Ограничить тип + сохранить точность значений    satisfies
Зафиксировать все типы как readonly + literal   as const
Проверить тип + readonly + литеральные типы     as const satisfies
Сообщить TypeScript тип без проверки            as (type assertion)
Стандартная аннотация переменной/параметра      : Type
```

---

## Type Assertions (`as`) — утверждения типов

`as` говорит TypeScript: "я знаю лучше тебя, тип вот такой". TypeScript **не проверяет** это утверждение — он принимает его на веру.

```ts
const input = document.getElementById("username");
// input: HTMLElement | null

// as — мы утверждаем, что это HTMLInputElement:
const inputEl = input as HTMLInputElement;
inputEl.value; // ✅ TypeScript доверяет нам

// Но если элемента нет или он не input — runtime crash:
const missing = document.getElementById("missing") as HTMLInputElement;
missing.value; // TypeError: Cannot read properties of null
```

### Когда `as` допустим

```ts
// 1. DOM API — TypeScript не знает конкретный тип элемента:
const canvas = document.querySelector("canvas") as HTMLCanvasElement;
const ctx = canvas.getContext("2d"); // ctx: CanvasRenderingContext2D | null ✅

// 2. JSON.parse — возвращает any, нужно утвердить тип:
const data = JSON.parse(response) as ApiResponse;
// Лучше — через Zod или runtime guard, но as — допустимый компромисс

// 3. Object.keys/entries с известной структурой:
const keys = Object.keys(config) as Array<keyof typeof config>;

// 4. Результат внешней библиотеки с плохими типами:
const result = legacyLib.process(data) as ProcessedResult;
```

### Когда `as` недопустим

```ts
// ❌ Приведение несовместимых типов — TypeScript запрещает:
const num = "hello" as number;
// Error: Conversion of type 'string' to type 'number' may be a mistake...

// ❌ Обход проверок типов для "удобства":
function getUser(): User {
  return {} as User; // Вернёт объект без полей — runtime crash в вызывающем коде
}

// ❌ as вместо type guard — скрывает баги:
function process(value: unknown) {
  (value as User).name.toUpperCase(); // Упадёт, если value — не User
}
```

### Double assertion — "ядерный вариант"

Когда типы полностью несовместимы, можно использовать двойное приведение через `unknown`:

```ts
const x = "hello" as unknown as number; // ✅ Компилируется
// Но это практически всегда признак архитектурной проблемы

// Легитимный случай — тест с моком:
const mockUser = {} as unknown as User; // В тестах иногда допустимо
```

---

## Вариантность в дженериках: `in` и `out` (TypeScript 4.7+)

TypeScript 4.7+ позволяет явно аннотировать вариантность параметров типа:

```ts
// out T — T используется только как выходной тип (ковариантность):
interface Producer<out T> {
  produce(): T;
}

// in T — T используется только как входной тип (контравариантность):
interface Consumer<in T> {
  consume(value: T): void;
}

// Без аннотации TypeScript выводит вариантность сам,
// но явная аннотация — документация и защита от ошибок:
const catProducer: Producer<Cat> = { produce: () => new Cat() };
const animalProducer: Producer<Animal> = catProducer; // ✅ ковариантность

const animalConsumer: Consumer<Animal> = { consume: (a) => console.log(a.name) };
const catConsumer: Consumer<Cat> = animalConsumer; // ✅ контравариантность
```

**Зачем явные аннотации?** Во-первых — документация (читатель сразу видит намерение). Во-вторых — TypeScript выдаст ошибку, если тело класса/интерфейса нарушает заявленную вариантность:

```ts
interface Producer<out T> {
  produce(): T;
  consume(value: T): void; // ❌ Type 'T' is contravariant but 'out T' requires covariant
}
```

---

## Типичные ошибки на интервью

- **"Параметры функций ковариантны"** — нет, они контравариантны (при `strictFunctionTypes`). Ковариантны — возвращаемые значения. Путаница в терминах — серьёзная ошибка на senior-уровне.

- **Не знать разницу между методом и свойством-функцией с точки зрения вариантности** — `method(x: T): void` бивариантен даже с `strictFunctionTypes`. `methodFn: (x: T) => void` — контравариантен. Это практически важное различие при написании обобщённых интерфейсов.

- **"Массивы в TypeScript инвариантны"** — нет, TypeScript разрешает `Cat[] extends Animal[]` (ковариантность), что теоретически unsafe. Можно продемонстрировать runtime-баг через `push` в общий массив.

- **Путать `satisfies` и явную аннотацию** — аннотация `const x: Config = value` меняет тип `x` на `Config`. `const x = value satisfies Config` оставляет тип выведенным, только проверяет соответствие. Это ключевое различие при работе с конфигурациями.

- **Не понимать `as const` на вложенных объектах** — `as const` применяется рекурсивно: все вложенные поля становятся `readonly` и получают литеральные типы. Без `as const` — только верхний уровень `const`.

- **Считать `as` безопасной операцией** — `as` отключает проверку типов. Единственная гарантия: TypeScript не позволит `as` между полностью несовместимыми типами (нужен double assertion через `unknown`). Но и это обходится — что делает `as` принципиально небезопасным.

- **Не знать `as const satisfies` — комбинацию** — это современный идиоматичный паттерн для типизированных конфигураций: получить и `readonly` литеральные типы, и проверку совместимости с ожидаемым типом.
