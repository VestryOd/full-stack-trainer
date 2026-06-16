# Функциональное программирование vs ООП в TypeScript

## Ложная дихотомия и реальный выбор

Первое, что нужно понять: в JavaScript/TypeScript вопрос "FP или ООП?" — это не выбор между двумя взаимоисключающими парадигмами. Это выбор **инструментов для конкретных задач** в языке, который поддерживает обе парадигмы одновременно.

```txt
JavaScript — мультипарадигменный язык:
  - Классы (class, extends) → ООП-инструменты
  - Функции первого класса, замыкания, map/filter/reduce → FP-инструменты
  - Промисы, async/await, генераторы → функциональные абстракции
  - Прототипное наследование → гибрид

React: компоненты — функции, хуки — FP-идиомы,
  но состояние и жизненный цикл — концепции из ООП

NestJS: классы, декораторы, DI — явный ООП-стиль,
  но middleware, guards — функциональные концепции
```

Цель этой статьи — не объявить победителя, а дать критерии выбора.

---

## Ключевые концепции FP и их TypeScript-реализации

### Чистые функции (Pure Functions)

```ts
// Чистая функция: один и тот же вход всегда даёт один и тот же выход,
// нет побочных эффектов (не меняет внешнее состояние, не читает глобалы)

// ✅ Чистая функция:
function calculateTax(price: number, taxRate: number): number {
  return price * (1 + taxRate);
}
// calculateTax(100, 0.2) === 120 — всегда, без исключений

// ❌ Нечистая функция (impure):
let taxRate = 0.2; // глобальное состояние

function calculateTaxImpure(price: number): number {
  return price * (1 + taxRate); // зависит от внешнего состояния
}
// Если taxRate изменится снаружи — результат изменится.
// Функция не изолирована: её нельзя тестировать без настройки глобала.

// ❌ Нечистая функция (побочный эффект):
function addUser(users: User[], newUser: User): User[] {
  users.push(newUser); // мутирует входной массив — побочный эффект!
  return users;
}

// ✅ Чистая версия — возвращает новый массив:
function addUser(users: readonly User[], newUser: User): User[] {
  return [...users, newUser]; // оригинал не тронут
}
```

**Почему чистые функции важны:**
```txt
- Детерминированность: легко тестировать (нет setup/teardown)
- Мемоизация: результат можно кешировать по аргументам
- Параллелизм: нет гонок данных (нет разделяемого изменяемого состояния)
- Отладка: поведение предсказуемо без понимания истории вызовов
```

### Иммутабельность (Immutability)

```ts
// Иммутабельность: объекты не меняются после создания — создаётся новый объект

// ❌ Мутация:
function applyDiscount(order: Order, discountPercent: number): void {
  order.total = order.total * (1 - discountPercent / 100); // мутируем входной объект
}
// Вызывающий код не знает, что его объект изменён

// ✅ Иммутабельное обновление:
function applyDiscount(order: Order, discountPercent: number): Order {
  return {
    ...order,
    total: order.total * (1 - discountPercent / 100),
  };
}

// TypeScript: readonly для принудительной иммутабельности
interface OrderItem {
  readonly productId: string;
  readonly price: number;
  readonly quantity: number;
}

type ReadonlyOrder = Readonly<Order>;
type DeepReadonly<T> = { readonly [K in keyof T]: DeepReadonly<T[K]> };

// Immer: иммутабельные обновления с мутирующим синтаксисом (copy-on-write)
import { produce } from 'immer';

const nextState = produce(state, draft => {
  draft.orders[orderId].status = 'shipped'; // выглядит как мутация, но это не так
});
// state не изменён; nextState — новый объект с изменённым вложенным полем
```

### Функции высшего порядка (Higher-Order Functions)

```ts
// Функция высшего порядка: принимает функцию как аргумент или возвращает функцию

// Функциональная композиция — HOF:
const compose = <T>(...fns: Array<(x: T) => T>) => (x: T): T =>
  fns.reduceRight((acc, fn) => fn(acc), x);

const pipe = <T>(...fns: Array<(x: T) => T>) => (x: T): T =>
  fns.reduce((acc, fn) => fn(acc), x);

// Использование:
const processPrice = pipe(
  (price: number) => price * 1.2,   // добавить НДС
  (price: number) => Math.round(price * 100) / 100, // округлить
  (price: number) => Math.max(price, 0),             // не меньше нуля
);

processPrice(99.99); // 119.99

// Каррирование (Currying):
const multiply = (a: number) => (b: number): number => a * b;
const double = multiply(2);
const triple = multiply(3);

double(5); // 10
triple(5); // 15

// Реальный пример: HOF для валидации
type Validator<T> = (value: T) => string | null;

function required<T>(message = 'Required'): Validator<T> {
  return (value) => (value === null || value === undefined || value === '') ? message : null;
}

function minLength(min: number): Validator<string> {
  return (value) => value.length < min ? `Minimum ${min} characters` : null;
}

function compose_validators<T>(...validators: Validator<T>[]): Validator<T> {
  return (value) => validators.reduce<string | null>(
    (error, validator) => error ?? validator(value),
    null
  );
}

const validatePassword = compose_validators(
  required<string>('Password is required'),
  minLength(8),
);
```

### Монады и функциональные контейнеры

```ts
// Option/Maybe — обработка отсутствующих значений без null-проверок:

class Option<T> {
  private constructor(private readonly value: T | null) {}

  static some<T>(value: T): Option<T> { return new Option(value); }
  static none<T>(): Option<T> { return new Option<T>(null); }

  map<U>(fn: (value: T) => U): Option<U> {
    return this.value !== null ? Option.some(fn(this.value)) : Option.none();
  }

  flatMap<U>(fn: (value: T) => Option<U>): Option<U> {
    return this.value !== null ? fn(this.value) : Option.none();
  }

  getOrElse(defaultValue: T): T {
    return this.value !== null ? this.value : defaultValue;
  }
}

// Без Option:
function findUserEmail(userId: string): string | null {
  const user = users.get(userId);
  if (!user) return null;
  if (!user.contacts) return null;
  return user.contacts.email ?? null;
}

// С Option — цепочка без null-проверок:
function findUserEmail(userId: string): Option<string> {
  return Option.some(userId)
    .flatMap(id => users.has(id) ? Option.some(users.get(id)!) : Option.none())
    .flatMap(user => user.contacts ? Option.some(user.contacts) : Option.none())
    .flatMap(contacts => contacts.email ? Option.some(contacts.email) : Option.none());
}

findUserEmail('123').getOrElse('unknown@example.com');

// Result<T, E> — функциональная обработка ошибок (альтернатива try/catch):
type Result<T, E> = { ok: true; value: T } | { ok: false; error: E };

function parsePositiveInt(raw: string): Result<number, string> {
  const n = parseInt(raw, 10);
  if (isNaN(n)) return { ok: false, error: `Not a number: ${raw}` };
  if (n <= 0) return { ok: false, error: `Must be positive: ${n}` };
  return { ok: true, value: n };
}

const result = parsePositiveInt('-5');
if (!result.ok) console.error(result.error); // "Must be positive: -5"
```

---

## Когда класс, а когда функция

Это практический вопрос, который часто задают на собеседованиях. Ответ не "всегда классы" и не "никогда классы".

### Используй классы когда:

```ts
// 1. Нужно инкапсулировать СОСТОЯНИЕ + ПОВЕДЕНИЕ вместе
class RateLimiter {
  private readonly timestamps: number[] = [];

  constructor(
    private readonly maxRequests: number,
    private readonly windowMs: number,
  ) {}

  isAllowed(): boolean {
    const now = Date.now();
    const windowStart = now - this.windowMs;
    // Удаляем устаревшие записи
    while (this.timestamps.length > 0 && this.timestamps[0] < windowStart) {
      this.timestamps.shift();
    }
    if (this.timestamps.length >= this.maxRequests) return false;
    this.timestamps.push(now);
    return true;
  }
}
// Без класса: мутирующее состояние (timestamps) нельзя выразить
// через чистую функцию без замыкания или внешнего хранилища

// 2. Нужен полиморфизм (разные реализации одного интерфейса)
interface Cache<T> {
  get(key: string): T | undefined;
  set(key: string, value: T, ttlMs?: number): void;
}
class InMemoryCache<T> implements Cache<T> { ... }
class RedisCache<T> implements Cache<T> { ... }

// 3. DI-контейнер требует классов (NestJS, InversifyJS)
@Injectable()
class UserService {
  constructor(private readonly repo: UserRepository) {}
}

// 4. Объект имеет сложный жизненный цикл (connect, disconnect, dispose)
class DatabasePool {
  async connect() { ... }
  async disconnect() { ... }
  async [Symbol.asyncDispose]() { await this.disconnect(); }
}
```

### Используй функции когда:

```ts
// 1. Нет состояния — трансформация данных
function formatCurrency(amount: number, currency = 'USD'): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount);
}
// Никакого состояния — функция идеальна

// 2. Одна конкретная операция, не нужен полиморфизм
async function sendWelcomeEmail(email: string, name: string): Promise<void> {
  await emailClient.send({ to: email, subject: `Welcome, ${name}!`, ... });
}

// 3. Pipeline / трансформационная цепочка
const processOrders = pipe(
  filterActiveOrders,
  sortByCreatedAt,
  groupByUser,
  calculateTotals,
);

// 4. React-компоненты (функциональные)
function UserCard({ user }: { user: User }) {
  return <div>{user.name}</div>;
}

// 5. Утилиты без побочных эффектов
const isEmpty = (arr: unknown[]): boolean => arr.length === 0;
const clamp = (value: number, min: number, max: number): number =>
  Math.min(Math.max(value, min), max);
```

### Паттерн: функции для логики + классы для состояния

```ts
// Лучшая практика в TypeScript: бизнес-логику писать как чистые функции,
// состояние и инфраструктуру инкапсулировать в классах

// Чистые функции — бизнес-правила, легко тестировать:
function calculateOrderTotal(items: readonly OrderItem[], discountPercent: number): number {
  const subtotal = items.reduce((s, i) => s + i.price * i.quantity, 0);
  return subtotal * (1 - discountPercent / 100);
}

function canApplyDiscount(user: User, order: Order): boolean {
  return user.isPremium && order.total > 100;
}

// Класс-сервис — оркестрация с состоянием (зависимости через DI):
class OrderService {
  constructor(
    private readonly orderRepo: OrderRepository,
    private readonly userRepo: UserRepository,
  ) {}

  async createOrder(userId: string, items: OrderItem[]): Promise<Order> {
    const user = await this.userRepo.findById(userId);
    if (!user) throw new Error('User not found');

    const discountPercent = user.isPremium ? 15 : 0;
    // Чистая функция — не знает о БД, легко тестировать отдельно:
    const total = calculateOrderTotal(items, discountPercent);

    return this.orderRepo.save({ userId, items, total, discountPercent });
  }
}
```

---

## Композиция vs Наследование

"Предпочитай композицию наследованию" — одна из старейших рекомендаций в ООП, но её часто понимают как "никогда не используй наследование". Это не так.

### Проблемы наследования

```ts
// ❌ Глубокая иерархия наследования — хрупкая и сложная

class Animal {
  eat() { console.log('eating'); }
  sleep() { console.log('sleeping'); }
}

class Bird extends Animal {
  fly() { console.log('flying'); }
}

class Duck extends Bird {
  quack() { console.log('quacking'); }
}

class RubberDuck extends Duck {
  // Резиновая утка не должна летать, но fly() унаследован
  fly() { throw new Error('Rubber ducks cannot fly'); } // LSP нарушен
}

// Проблемы:
// 1. Хрупкий базовый класс: изменение Animal ломает всю иерархию
// 2. Проблема "бананово-гориллы": хочешь банан (Quack),
//    получаешь гориллу со всем лесом (весь Animal + Bird + Duck)
// 3. Один базовый класс = одна ось вариации, но утки бывают
//    разные по НЕСКОЛЬКИМ осям (летающие/нелетающие, живые/игрушечные)
```

```ts
// ✅ Композиция через интерфейсы + миксины:

interface Eater { eat(): void; }
interface Sleeper { sleep(): void; }
interface Flyer { fly(): void; }
interface Quacker { quack(): void; }

// Реализации — маленькие, независимые:
const eatingBehavior: Eater = { eat: () => console.log('eating') };
const flyingBehavior: Flyer = { fly: () => console.log('flying') };

// Duck — компонует нужные поведения:
class Duck implements Eater, Sleeper, Flyer, Quacker {
  private readonly eater = eatingBehavior;
  private readonly flyer = flyingBehavior;

  eat() { this.eater.eat(); }
  sleep() { console.log('sleeping'); }
  fly() { this.flyer.fly(); }
  quack() { console.log('quacking'); }
}

// RubberDuck — компонует только то, что умеет:
class RubberDuck implements Quacker {
  quack() { console.log('squeaking'); }
  // Нет fly() — и это правильно: RubberDuck просто не реализует Flyer
}
```

### Когда наследование оправдано

```ts
// Наследование оправдано для трёх случаев:

// 1. Подтип ДЕЙСТВИТЕЛЬНО является частным случаем базового типа (IS-A)
//    — и LSP соблюдается
class HttpError extends Error {
  constructor(
    public readonly statusCode: number,
    message: string,
  ) {
    super(message);
    this.name = 'HttpError';
  }
}

class NotFoundError extends HttpError {
  constructor(resource: string) {
    super(404, `${resource} not found`);
    this.name = 'NotFoundError';
  }
}
// NotFoundError IS-A HttpError IS-A Error — LSP соблюдён на каждом уровне

// 2. Template Method: базовый класс фиксирует алгоритм, подкласс — детали
abstract class BaseExporter {
  async export(data: unknown[]): Promise<void> { ... } // шаблон
  protected abstract serialize(data: unknown[]): string; // переопределяется
}

// 3. Фреймворковые базовые классы (EventEmitter, React.Component)
class OrderService extends EventEmitter {
  // Наследование от EventEmitter — это разумно: OrderService IS-AN EventEmitter
}
```

### Mixin-паттерн как альтернатива множественному наследованию

```ts
// TypeScript не поддерживает множественное наследование классов,
// но поддерживает mixins через типизированные функции:

type Constructor<T = object> = new (...args: unknown[]) => T;

function Timestamped<TBase extends Constructor>(Base: TBase) {
  return class extends Base {
    createdAt = new Date();
    updatedAt = new Date();

    touch() { this.updatedAt = new Date(); }
  };
}

function Activatable<TBase extends Constructor>(Base: TBase) {
  return class extends Base {
    isActive = true;

    activate() { this.isActive = true; }
    deactivate() { this.isActive = false; }
  };
}

class User {
  constructor(public name: string) {}
}

// Композиция поведений через mixins:
const TimestampedUser = Timestamped(User);
const ActivatableTimestampedUser = Activatable(Timestamped(User));

const user = new ActivatableTimestampedUser('Alice');
user.touch();       // Timestamped
user.deactivate();  // Activatable
```

---

## FP-паттерны в React-экосистеме

### Хуки как FP-абстракции

```tsx
// Хуки — это функциональные абстракции над состоянием и эффектами.
// Они позволяют компоновать поведение без наследования компонентов.

// Кастомный хук = замыкание со встроенным состоянием:
function useDebounce<T>(value: T, delayMs: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delayMs);
    return () => clearTimeout(timer); // cleanup — функциональный паттерн
  }, [value, delayMs]);

  return debouncedValue;
}

// Хуки компонуются как функции:
function useUserSearch(initialQuery = '') {
  const [query, setQuery] = useState(initialQuery);
  const debouncedQuery = useDebounce(query, 300); // компонуем хуки
  const { data: users, loading } = useData<User[]>(`/api/users?q=${debouncedQuery}`);

  return { query, setQuery, users, loading };
}

// Использование:
function UserSearch() {
  const { query, setQuery, users, loading } = useUserSearch();
  return (
    <>
      <input value={query} onChange={e => setQuery(e.target.value)} />
      {loading ? <Spinner /> : <UserList users={users ?? []} />}
    </>
  );
}
```

### Функциональные обновления состояния

```tsx
// Функциональный updater в useState — чистая функция от предыдущего состояния:

// ❌ Небезопасно при батчинге React:
setCount(count + 1); // закрывается над устаревшим count

// ✅ Функциональный updater — всегда работает с актуальным состоянием:
setCount(prev => prev + 1);

// Применение — аккумулирование:
function CartProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<CartItem[]>([]);

  const addItem = useCallback((item: CartItem) => {
    setItems(prev => {
      const existing = prev.find(i => i.productId === item.productId);
      if (existing) {
        // Иммутабельное обновление:
        return prev.map(i =>
          i.productId === item.productId
            ? { ...i, quantity: i.quantity + item.quantity }
            : i
        );
      }
      return [...prev, item];
    });
  }, []);

  // ...
}
```

---

## Иммутабельность в Node.js

### Object.freeze и as const

```ts
// Object.freeze — runtime иммутабельность:
const DEFAULT_CONFIG = Object.freeze({
  timeout: 5000,
  retries: 3,
  baseUrl: 'https://api.example.com',
});
// DEFAULT_CONFIG.timeout = 1000; → TypeError в runtime

// as const — compile-time иммутабельность (TypeScript):
const HTTP_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'] as const;
type HttpMethod = typeof HTTP_METHODS[number]; // 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
// HTTP_METHODS[0] — тип 'GET', а не string

const STATUS_CODES = {
  OK: 200,
  NOT_FOUND: 404,
  INTERNAL_ERROR: 500,
} as const;
type StatusCode = typeof STATUS_CODES[keyof typeof STATUS_CODES]; // 200 | 404 | 500
```

### Иммутабельные структуры данных в производительном коде

```ts
// Проблема наивной иммутабельности: spread создаёт копию — O(n) на каждую операцию
// Для больших объектов или частых обновлений это проблема

// ❌ Для большого массива (10 000+ элементов) каждое обновление — O(n):
const nextItems = [...items, newItem]; // копируем весь массив

// ✅ Immer: структурное разделение — копируются только изменённые ветки дерева
import { produce, enableMapSet } from 'immer';

enableMapSet(); // включить поддержку Map/Set

const nextState = produce(state, draft => {
  draft.users.set(newUser.id, newUser); // Map обновляется эффективно
  draft.orderIds.push(orderId);         // Array: только push — immer знает, что делать
});

// Immer использует Proxy под капотом: отслеживает изменения и клонирует
// только изменённые части дерева (structural sharing)
```

---

## Практическое руководство: что выбрать

```txt
Задача                            Рекомендуемый подход
──────────────────────────────────────────────────────────────────────
Трансформация данных              Чистые функции
  (форматирование, вычисления)

Компоненты с переиспользуемой     Кастомные хуки (функции)
  логикой без состояния

Сервисы с зависимостями           Классы + DI
  (репозитории, клиенты API)

Объекты с инвариантами            Классы с private полями
  (Entity, Value Object)            и методами-мутаторами

Один из набора алгоритмов         Strategy (класс или функция)

Реакция на события                Observer/EventEmitter (классы)
  между слоями

Вариативный UI без prop drilling  Compound Components + Context

Сложные конечные автоматы         XState (FP + State Machine)

Иммутабельные обновления          Immer / spread / structuredClone
  вложенного состояния
```

---

## Типичные ошибки на интервью

- **"FP лучше ООП" или "ООП лучше FP"** — в JavaScript/TypeScript это ложная дихотомия. Правильный ответ: это разные инструменты. FP хорошо для трансформаций данных и тестируемой логики. ООП хорошо для инкапсуляции состояния и полиморфизма. React использует оба подхода.

- **"Классы — это ООП, функции — это FP"** — упрощение. FP — это парадигма с чистыми функциями, иммутабельностью и композицией. Класс может содержать чистые методы (FP-стиль). Функция может иметь побочные эффекты (не FP).

- **"Иммутабельность — это медленно"** — для большинства случаев spread и structuredClone достаточно быстры. Для performance-critical кода — Immer со structural sharing. Преждевременная оптимизация vs читаемость кода: сначала правильно, потом быстро.

- **"Наследование — плохо, всегда используй композицию"** — слишком категорично. Наследование оправдано для иерархий ошибок (`Error → HttpError → NotFoundError`), шаблонного метода, фреймворковых базовых классов. Проблема не в наследовании как таком, а в глубоких иерархиях и нарушении LSP.

- **"Хуки заменили классовые компоненты — значит FP лучше ООП"** — хуки решают конкретную проблему React (переиспользование stateful-логики без HOC-обёрток). Это не манифест FP. За хуками — State, Observer, Mediator из ООП-паттернов.

- **Не знать Result/Option** — в TypeScript-интервью всё чаще спрашивают про функциональную обработку ошибок. Знание `Result<T, E>` как альтернативы исключениям и понимание, когда что использовать (исключения — для действительно исключительных ситуаций, Result — для ожидаемых ошибок бизнес-логики) — это senior-level знание.

- **Путать иммутабельность и константность** — `const` в JavaScript запрещает переприсваивание переменной, но не мутацию объекта. Иммутабельность — про невозможность мутации самого объекта. `const arr = []` + `arr.push(1)` — константная переменная, мутируемый объект.
