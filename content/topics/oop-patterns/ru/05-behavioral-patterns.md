# Поведенческие паттерны (Behavioral Patterns)

## Зачем нужны поведенческие паттерны

Поведенческие паттерны описывают **как объекты взаимодействуют и распределяют ответственность** во время выполнения. Там где структурные паттерны отвечают на "как соединить объекты", поведенческие отвечают на "как они общаются между собой".

```txt
Структурные  → "статические связи между классами и объектами"
Поведенческие → "динамические протоколы взаимодействия объектов"
```

Поведенческие паттерны — самая большая группа GoF. Они решают: как избежать жёсткой связности между отправителем и получателем сообщения, как инкапсулировать алгоритм, как реагировать на изменение состояния.

---

## Observer — "подписка на события"

> Определяет зависимость "один ко многим" между объектами так, что при изменении состояния одного объекта все зависящие от него оповещаются и обновляются автоматически.

Observer — один из самых фундаментальных паттернов во фронтенд и Node.js разработке. EventEmitter, DOM-события, React-стейт, RxJS — всё это реализации Observer.

### Базовая реализация

```ts
interface Observer<T> {
  update(data: T): void;
}

interface Observable<T> {
  subscribe(observer: Observer<T>): void;
  unsubscribe(observer: Observer<T>): void;
  notify(data: T): void;
}

class EventBus<T> implements Observable<T> {
  private observers = new Set<Observer<T>>();

  subscribe(observer: Observer<T>): void {
    this.observers.add(observer);
  }

  unsubscribe(observer: Observer<T>): void {
    this.observers.delete(observer);
  }

  notify(data: T): void {
    this.observers.forEach(observer => observer.update(data));
  }
}

// Использование:
interface UserCreatedEvent {
  userId: string;
  email: string;
}

const userEvents = new EventBus<UserCreatedEvent>();

// Подписчики — не зависят друг от друга и не знают о UserService
const emailObserver: Observer<UserCreatedEvent> = {
  update: ({ email }) => emailService.sendWelcome(email),
};
const analyticsObserver: Observer<UserCreatedEvent> = {
  update: ({ userId }) => analytics.track('user_created', { userId }),
};

userEvents.subscribe(emailObserver);
userEvents.subscribe(analyticsObserver);

// UserService только публикует событие, не знает о подписчиках:
class UserService {
  async register(email: string, password: string) {
    const user = await this.userRepo.create(email, password);
    userEvents.notify({ userId: user.id, email });
    return user;
  }
}
```

### Node.js EventEmitter — Observer в стандартной библиотеке

```ts
import { EventEmitter } from 'node:events';

// EventEmitter — встроенная реализация Observer в Node.js
class OrderService extends EventEmitter {
  async placeOrder(dto: CreateOrderDto): Promise<Order> {
    const order = await this.orderRepo.save(dto);
    // Паттерн Observer: emit вместо прямого вызова подписчиков
    this.emit('order:placed', order);
    return order;
  }
}

const orderService = new OrderService();

// Подписчики регистрируются снаружи — OrderService о них не знает
orderService.on('order:placed', async (order: Order) => {
  await notificationService.sendConfirmation(order);
});

orderService.on('order:placed', async (order: Order) => {
  await inventoryService.reserveStock(order.items);
});

// Senior-нюанс: всегда подписывайся на 'error', иначе необработанный
// emit('error') приведёт к падению процесса (см. [Node.js Fundamentals])
orderService.on('error', (err) => logger.error('OrderService error', err));
```

### Observer в React — useEffect и кастомные хуки

```tsx
// React state — это Observable: при изменении все компоненты-подписчики
// (использующие этот state) перерендериваются

// Кастомный хук как Observable — подписывается на внешнее событие:
function useWindowSize() {
  const [size, setSize] = useState({ width: window.innerWidth, height: window.innerHeight });

  useEffect(() => {
    const handler = () => setSize({ width: window.innerWidth, height: window.innerHeight });
    // Подписка (subscribe):
    window.addEventListener('resize', handler);
    // Отписка при размонтировании (unsubscribe) — критически важно!
    return () => window.removeEventListener('resize', handler);
  }, []);

  return size;
}
```

### Когда Observer становится проблемой

```txt
Проблемы Observer в крупных приложениях:
  - "Цепочки реакций": событие A → событие B → событие C → ...
    трудно отследить, что происходит при конкретном действии пользователя
  - Memory leaks: подписчик живёт дольше Observable — не отписался → утечка
  - Порядок выполнения: подписчики вызываются в порядке регистрации,
    но явной гарантии порядка нет — если один подписчик зависит
    от результата другого, это скрытая связность
```

---

## Strategy — "инкапсулировать алгоритм"

> Определяет семейство алгоритмов, инкапсулирует каждый из них и делает их взаимозаменяемыми. Позволяет изменять алгоритм независимо от клиентов, которые его используют.

Strategy — это паттерн для "подменяемого поведения". Если у вас есть место в коде, где алгоритм нужно менять в зависимости от контекста (сортировка, валидация, ценообразование, аутентификация), Strategy — правильный выбор.

### Пример: стратегии ценообразования

```ts
interface PricingStrategy {
  calculate(basePrice: number, context: PricingContext): number;
}

interface PricingContext {
  userId: string;
  isPremium: boolean;
  couponCode?: string;
  quantity: number;
}

class StandardPricing implements PricingStrategy {
  calculate(basePrice: number, context: PricingContext): number {
    return basePrice * context.quantity;
  }
}

class PremiumPricing implements PricingStrategy {
  calculate(basePrice: number, context: PricingContext): number {
    return basePrice * context.quantity * 0.85; // 15% скидка для premium
  }
}

class BulkPricing implements PricingStrategy {
  calculate(basePrice: number, context: PricingContext): number {
    const discount = context.quantity >= 100 ? 0.30 : context.quantity >= 10 ? 0.15 : 0;
    return basePrice * context.quantity * (1 - discount);
  }
}

class CouponPricing implements PricingStrategy {
  constructor(private readonly coupons: Map<string, number>) {}

  calculate(basePrice: number, context: PricingContext): number {
    const discount = context.couponCode
      ? this.coupons.get(context.couponCode) ?? 0
      : 0;
    return basePrice * context.quantity * (1 - discount);
  }
}

class PriceCalculator {
  constructor(private strategy: PricingStrategy) {}

  // Стратегия может меняться в runtime
  setStrategy(strategy: PricingStrategy): void {
    this.strategy = strategy;
  }

  calculatePrice(basePrice: number, context: PricingContext): number {
    return this.strategy.calculate(basePrice, context);
  }
}

// Выбор стратегии — бизнес-правило, отделённое от самого расчёта:
function selectStrategy(context: PricingContext): PricingStrategy {
  if (context.couponCode) return new CouponPricing(couponsMap);
  if (context.isPremium) return new PremiumPricing();
  if (context.quantity >= 10) return new BulkPricing();
  return new StandardPricing();
}
```

### Strategy в реальных библиотеках

```ts
// Passport.js — классический Strategy паттерн для аутентификации:
passport.use(new LocalStrategy(async (username, password, done) => {
  const user = await User.findOne({ username });
  if (!user || !await bcrypt.compare(password, user.password)) {
    return done(null, false);
  }
  return done(null, user);
}));

passport.use(new JwtStrategy(opts, async (payload, done) => {
  const user = await User.findById(payload.sub);
  return user ? done(null, user) : done(null, false);
}));

// Подключить Google OAuth? Добавить ещё одну стратегию — без изменения остального кода.

// Array.prototype.sort — стратегия как функция-компаратор:
const users = [...].sort((a, b) => a.name.localeCompare(b.name)); // стратегия: по имени
const users2 = [...].sort((a, b) => b.createdAt - a.createdAt);   // стратегия: по дате
```

---

## Command — "инкапсулировать действие как объект"

> Инкапсулирует запрос как объект, позволяя параметризовать клиентов с различными запросами, ставить запросы в очередь, логировать их и поддерживать отмену операций.

Command превращает "вызов метода" в объект. Это открывает возможности: очередь команд, отмена, повтор, транзакции, логирование.

### Пример: текстовый редактор с undo/redo

```ts
interface Command {
  execute(): void;
  undo(): void;
}

class TextEditor {
  private content = '';

  insert(text: string, position: number): void {
    this.content = this.content.slice(0, position) + text + this.content.slice(position);
  }

  delete(start: number, length: number): void {
    this.content = this.content.slice(0, start) + this.content.slice(start + length);
  }

  getContent(): string { return this.content; }
}

class InsertCommand implements Command {
  constructor(
    private readonly editor: TextEditor,
    private readonly text: string,
    private readonly position: number,
  ) {}

  execute(): void { this.editor.insert(this.text, this.position); }
  undo(): void { this.editor.delete(this.position, this.text.length); }
}

class DeleteCommand implements Command {
  private deletedText = '';

  constructor(
    private readonly editor: TextEditor,
    private readonly start: number,
    private readonly length: number,
  ) {}

  execute(): void {
    this.deletedText = this.editor.getContent().slice(this.start, this.start + this.length);
    this.editor.delete(this.start, this.length);
  }

  undo(): void { this.editor.insert(this.deletedText, this.start); }
}

// CommandHistory — хранит историю для undo/redo
class CommandHistory {
  private readonly history: Command[] = [];
  private pointer = -1;

  execute(command: Command): void {
    // При выполнении новой команды — обрезаем "будущее" (redo-стек)
    this.history.splice(this.pointer + 1);
    command.execute();
    this.history.push(command);
    this.pointer++;
  }

  undo(): void {
    if (this.pointer < 0) return;
    this.history[this.pointer].undo();
    this.pointer--;
  }

  redo(): void {
    if (this.pointer >= this.history.length - 1) return;
    this.pointer++;
    this.history[this.pointer].execute();
  }
}
```

### Redux как Command + Observer

```ts
// Redux — это реализация Command + Observer:
//
// Action (команда): { type: 'INCREMENT', payload: 1 }
//   — объект, описывающий намерение (как Command.execute())
//
// Reducer (обработчик команды): (state, action) => newState
//   — чистая функция, применяющая команду к состоянию
//
// dispatch() — отправляет команду в store
//
// store.subscribe() — Observer: компоненты подписываются на изменения
//
// Redux DevTools: inspect и replay actions — возможно только потому,
// что каждое действие — сериализуемый объект (Command)

// Эквивалент Command в Redux:
const increment = (amount: number) => ({ type: 'INCREMENT' as const, payload: amount });

// Reducer — чистая функция-обработчик команд:
function counterReducer(state = 0, action: ReturnType<typeof increment>) {
  switch (action.type) {
    case 'INCREMENT': return state + action.payload;
    default: return state;
  }
}

// dispatch — выполнение команды:
store.dispatch(increment(1));
// Все подписчики (connect(), useSelector()) — Observer:
store.subscribe(() => console.log(store.getState()));
```

### Command в очередях задач (Node.js)

```ts
// BullMQ / pg-boss: каждая задача в очереди — это Command-объект
interface JobCommand {
  type: string;
  payload: unknown;
}

// Постановка в очередь — отложенное выполнение Command:
await queue.add('send-email', { to: user.email, template: 'welcome' });
await queue.add('resize-image', { fileId: 'abc123', sizes: [100, 200, 400] });

// Worker — "invoker" из паттерна Command, выполняет команды:
worker.process(async (job) => {
  const handlers: Record<string, (payload: unknown) => Promise<void>> = {
    'send-email': (p) => emailService.send(p as EmailPayload),
    'resize-image': (p) => imageService.resize(p as ResizePayload),
  };
  await handlers[job.name]?.(job.data);
});
```

---

## Iterator — "последовательный обход без раскрытия структуры"

> Предоставляет способ последовательно обходить элементы составного объекта, не раскрывая его внутреннего представления.

В TypeScript Iterator встроен в язык через протокол `Symbol.iterator` и генераторы.

### Пример: пагинация через кастомный Iterator

```ts
// Без Iterator — потребитель должен знать про offset/limit и делать запросы вручную

// ✅ С Iterator — потребитель просто итерирует, не зная деталей пагинации
class PaginatedUserIterator implements AsyncIterable<User[]> {
  constructor(
    private readonly repo: UserRepository,
    private readonly pageSize: number = 50,
  ) {}

  async *[Symbol.asyncIterator](): AsyncGenerator<User[]> {
    let page = 0;
    let hasMore = true;

    while (hasMore) {
      const batch = await this.repo.findAll({
        skip: page * this.pageSize,
        take: this.pageSize,
      });
      if (batch.length === 0) {
        hasMore = false;
      } else {
        yield batch;
        page++;
        hasMore = batch.length === this.pageSize;
      }
    }
  }
}

// Потребитель не знает об offset/limit:
async function exportAllUsers(repo: UserRepository) {
  const iterator = new PaginatedUserIterator(repo, 100);

  for await (const batch of iterator) {
    await csvWriter.write(batch);
  }
}
```

### Generator как Iterator

```ts
// Генераторы — самый идиоматичный способ реализовать Iterator в TypeScript

function* range(start: number, end: number, step = 1): Generator<number> {
  for (let i = start; i < end; i += step) {
    yield i;
  }
}

for (const n of range(0, 10, 2)) {
  console.log(n); // 0, 2, 4, 6, 8
}

// Infinite Iterator — без генератора потребовал бы специальной обработки:
function* fibonacci(): Generator<number> {
  let [a, b] = [0, 1];
  while (true) {
    yield a;
    [a, b] = [b, a + b];
  }
}

const fib = fibonacci();
console.log(fib.next().value); // 0
console.log(fib.next().value); // 1
console.log(fib.next().value); // 1
```

### Node.js Streams как Iterator

```ts
// Readable stream в Node.js реализует AsyncIterable — это Iterator:
import { createReadStream } from 'node:fs';
import * as readline from 'node:readline';

async function processLargeFile(path: string) {
  const fileStream = createReadStream(path);
  const rl = readline.createInterface({ input: fileStream });

  // AsyncIterator: читаем построчно, не загружая весь файл в память
  for await (const line of rl) {
    await processLine(line);
  }
}
```

---

## Template Method — "скелет алгоритма с переопределяемыми шагами"

> Определяет скелет алгоритма в базовом классе, позволяя подклассам переопределять отдельные шаги, не меняя структуру алгоритма.

Template Method — один из паттернов, где наследование оправдано архитектурно. Базовый класс фиксирует порядок шагов; подклассы могут менять детали, не ломая "рецепт".

### Пример: обработчик данных

```ts
// Базовый класс фиксирует алгоритм:
abstract class DataImporter {
  // Template Method — финальный, порядок шагов нельзя менять
  async import(source: string): Promise<ImportResult> {
    const rawData = await this.readData(source);
    const parsedData = this.parseData(rawData);
    const validData = this.validateData(parsedData);
    const transformedData = this.transformData(validData);
    return this.saveData(transformedData);
  }

  // Обязательные шаги — подклассы ДОЛЖНЫ реализовать
  protected abstract readData(source: string): Promise<string>;
  protected abstract parseData(raw: string): Record<string, unknown>[];

  // Необязательные хуки — подкласс может переопределить
  protected validateData(data: Record<string, unknown>[]): Record<string, unknown>[] {
    return data.filter(row => Object.keys(row).length > 0);
  }

  protected transformData(data: Record<string, unknown>[]): Record<string, unknown>[] {
    return data; // по умолчанию — без трансформации
  }

  protected abstract saveData(data: Record<string, unknown>[]): Promise<ImportResult>;
}

class CsvImporter extends DataImporter {
  protected async readData(source: string): Promise<string> {
    return fs.readFile(source, 'utf-8');
  }

  protected parseData(raw: string): Record<string, unknown>[] {
    const [headerLine, ...rows] = raw.split('\n');
    const headers = headerLine.split(',');
    return rows.map(row => {
      const values = row.split(',');
      return Object.fromEntries(headers.map((h, i) => [h, values[i]]));
    });
  }

  protected async saveData(data: Record<string, unknown>[]): Promise<ImportResult> {
    await db.batchInsert('imports', data);
    return { count: data.length, status: 'success' };
  }
}

class JsonApiImporter extends DataImporter {
  constructor(private readonly apiUrl: string) { super(); }

  protected async readData(_source: string): Promise<string> {
    const response = await fetch(this.apiUrl);
    return response.text();
  }

  protected parseData(raw: string): Record<string, unknown>[] {
    return JSON.parse(raw).data; // специфичная структура API
  }

  protected transformData(data: Record<string, unknown>[]): Record<string, unknown>[] {
    // Дополнительная нормализация — только для JSON API
    return data.map(row => ({ ...row, importedAt: new Date().toISOString() }));
  }

  protected async saveData(data: Record<string, unknown>[]): Promise<ImportResult> {
    await db.batchInsert('imports', data);
    return { count: data.length, status: 'success' };
  }
}
```

### Template Method vs Strategy

```txt
Template Method (наследование):
  - Алгоритм зафиксирован в базовом классе
  - Подклассы переопределяют отдельные шаги
  - Выбор "вариации" — статический (определяется типом объекта)

Strategy (композиция):
  - Алгоритм целиком инкапсулирован в стратегии
  - Стратегии взаимозаменяемы в runtime
  - Выбор "вариации" — динамический (можно сменить в любой момент)

Правило: предпочитай Strategy над Template Method —
"предпочитай композицию наследованию".
Template Method оправдан, когда скелет алгоритма сам по себе
является ценной абстракцией (не детали шагов, а порядок).
```

---

## State — "поведение зависит от состояния"

> Позволяет объекту менять поведение при изменении его внутреннего состояния. Объект будет казаться изменившим свой класс.

State — альтернатива разрастающейся цепочке `if/switch` на поле `status` или `state`. Каждое состояние — отдельный класс с поведением.

### Пример: заказ с состояниями

```ts
interface OrderState {
  pay(): void;
  ship(): void;
  cancel(): void;
  getStatus(): string;
}

class Order {
  private state: OrderState;

  constructor() {
    this.state = new PendingState(this);
  }

  setState(state: OrderState): void { this.state = state; }

  pay(): void { this.state.pay(); }
  ship(): void { this.state.ship(); }
  cancel(): void { this.state.cancel(); }
  getStatus(): string { return this.state.getStatus(); }
}

class PendingState implements OrderState {
  constructor(private readonly order: Order) {}

  pay(): void {
    console.log('Payment received');
    this.order.setState(new PaidState(this.order));
  }
  ship(): void { throw new Error('Cannot ship unpaid order'); }
  cancel(): void {
    console.log('Order cancelled');
    this.order.setState(new CancelledState(this.order));
  }
  getStatus(): string { return 'pending'; }
}

class PaidState implements OrderState {
  constructor(private readonly order: Order) {}

  pay(): void { throw new Error('Order already paid'); }
  ship(): void {
    console.log('Order shipped');
    this.order.setState(new ShippedState(this.order));
  }
  cancel(): void {
    console.log('Order cancelled, refund initiated');
    this.order.setState(new CancelledState(this.order));
  }
  getStatus(): string { return 'paid'; }
}

class ShippedState implements OrderState {
  constructor(private readonly order: Order) {}

  pay(): void { throw new Error('Order already paid'); }
  ship(): void { throw new Error('Order already shipped'); }
  cancel(): void { throw new Error('Cannot cancel shipped order'); }
  getStatus(): string { return 'shipped'; }
}

class CancelledState implements OrderState {
  constructor(private readonly order: Order) {}

  pay(): void { throw new Error('Order is cancelled'); }
  ship(): void { throw new Error('Order is cancelled'); }
  cancel(): void { throw new Error('Order already cancelled'); }
  getStatus(): string { return 'cancelled'; }
}

// Клиентский код:
const order = new Order();
order.pay();    // "Payment received"
order.ship();   // "Order shipped"
order.cancel(); // throws: Cannot cancel shipped order
```

### XState — State Machine как библиотека

```ts
// XState формализует State паттерн в TypeScript-приложениях:
import { createMachine, interpret } from 'xstate';

const orderMachine = createMachine({
  id: 'order',
  initial: 'pending',
  states: {
    pending: {
      on: {
        PAY: 'paid',
        CANCEL: 'cancelled',
      },
    },
    paid: {
      on: {
        SHIP: 'shipped',
        CANCEL: 'cancelled',
      },
    },
    shipped: { type: 'final' },
    cancelled: { type: 'final' },
  },
});

const service = interpret(orderMachine).start();
service.send('PAY');   // pending → paid
service.send('SHIP');  // paid → shipped
```

---

## Mediator — "посредник вместо прямых связей"

> Определяет объект, инкапсулирующий взаимодействие между множеством объектов. Mediator снижает связность между компонентами, делая их взаимодействие явным.

Без Mediator: N объектов, каждый знает обо всех остальных → O(N²) связей. С Mediator: каждый объект знает только о Mediator → O(N) связей.

### Пример: чат-комната

```ts
interface ChatMediator {
  sendMessage(message: string, sender: ChatUser): void;
  addUser(user: ChatUser): void;
}

class ChatRoom implements ChatMediator {
  private users: ChatUser[] = [];

  addUser(user: ChatUser): void {
    this.users.push(user);
  }

  sendMessage(message: string, sender: ChatUser): void {
    // Медиатор знает обо всех пользователях; пользователи — только о медиаторе
    this.users
      .filter(user => user !== sender)
      .forEach(user => user.receive(message, sender.name));
  }
}

class ChatUser {
  constructor(
    public readonly name: string,
    private readonly mediator: ChatMediator,
  ) {
    mediator.addUser(this);
  }

  send(message: string): void {
    console.log(`${this.name} sends: "${message}"`);
    this.mediator.sendMessage(message, this);
  }

  receive(message: string, from: string): void {
    console.log(`${this.name} receives from ${from}: "${message}"`);
  }
}

const room = new ChatRoom();
const alice = new ChatUser('Alice', room);
const bob = new ChatUser('Bob', room);
const charlie = new ChatUser('Charlie', room);

alice.send('Hello everyone!');
// Bob receives from Alice: "Hello everyone!"
// Charlie receives from Alice: "Hello everyone!"
```

### Mediator в React — Redux Store, Context

```tsx
// Redux Store — Mediator для компонентов:
// компоненты не знают друг о друге, они общаются через store

// Без Mediator: UserProfile → напрямую уведомляет Header, Sidebar, CartCount
// С Redux (Mediator):
dispatch(updateUser(userData));    // публикует в store
// Header, Sidebar, CartCount — подписчики через useSelector, не знают друг о друге

// React Context — более лёгкий Mediator:
const ThemeContext = createContext<Theme>(defaultTheme);

// Провайдер — Mediator: компоненты читают тему напрямую из контекста
// и не передают пропсы через несколько уровней
function App() {
  return (
    <ThemeContext.Provider value={currentTheme}>
      <Layout />
    </ThemeContext.Provider>
  );
}
```

---

## Chain of Responsibility — "цепочка обработчиков"

> Позволяет передавать запросы по цепочке обработчиков. Каждый обработчик решает, обработать запрос самому или передать следующему.

Chain of Responsibility — паттерн, который буквально реализован в Express/Koa middleware. Каждый обработчик в цепочке независим и не знает о других.

### Пример: валидация и авторизация запроса

```ts
interface RequestContext {
  method: string;
  path: string;
  headers: Record<string, string>;
  userId?: string;
  body?: unknown;
}

interface Handler {
  setNext(handler: Handler): Handler;
  handle(ctx: RequestContext): Promise<void>;
}

abstract class BaseHandler implements Handler {
  private nextHandler: Handler | null = null;

  setNext(handler: Handler): Handler {
    this.nextHandler = handler;
    return handler; // возвращаем handler для chaining: a.setNext(b).setNext(c)
  }

  protected async passToNext(ctx: RequestContext): Promise<void> {
    if (this.nextHandler) {
      await this.nextHandler.handle(ctx);
    }
  }

  abstract handle(ctx: RequestContext): Promise<void>;
}

class RateLimitHandler extends BaseHandler {
  private readonly requestCounts = new Map<string, number>();

  async handle(ctx: RequestContext): Promise<void> {
    const ip = ctx.headers['x-forwarded-for'] ?? 'unknown';
    const count = (this.requestCounts.get(ip) ?? 0) + 1;
    this.requestCounts.set(ip, count);

    if (count > 100) {
      throw new Error('Rate limit exceeded');
    }
    await this.passToNext(ctx);
  }
}

class AuthHandler extends BaseHandler {
  async handle(ctx: RequestContext): Promise<void> {
    const token = ctx.headers['authorization']?.replace('Bearer ', '');
    if (!token) throw new Error('Unauthorized');

    const payload = jwtService.verify(token);
    ctx.userId = payload.sub; // обогащаем контекст
    await this.passToNext(ctx);
  }
}

class ValidationHandler extends BaseHandler {
  async handle(ctx: RequestContext): Promise<void> {
    if (ctx.method === 'POST' && !ctx.body) {
      throw new Error('Request body is required');
    }
    await this.passToNext(ctx);
  }
}

class BusinessLogicHandler extends BaseHandler {
  async handle(ctx: RequestContext): Promise<void> {
    // Настоящая бизнес-логика — только если прошли все предыдущие обработчики
    console.log(`Processing request for user ${ctx.userId}`);
  }
}

// Сборка цепочки:
const rateLimiter = new RateLimitHandler();
const auth = new AuthHandler();
const validation = new ValidationHandler();
const business = new BusinessLogicHandler();

rateLimiter.setNext(auth).setNext(validation).setNext(business);

// Запрос проходит через всю цепочку:
await rateLimiter.handle(requestContext);
```

### Express middleware как Chain of Responsibility

```ts
// Express middleware — это именно Chain of Responsibility.
// next() — это passToNext() из примера выше.

app.use(async (req, res, next) => {
  // RateLimitHandler
  if (await isRateLimited(req.ip)) return res.status(429).send('Too many requests');
  next();
});

app.use(async (req, res, next) => {
  // AuthHandler
  try {
    req.user = await verifyToken(req.headers.authorization);
    next();
  } catch {
    res.status(401).send('Unauthorized');
  }
});

app.post('/orders', async (req, res) => {
  // BusinessLogicHandler — конец цепочки
  const order = await orderService.create(req.user.id, req.body);
  res.json(order);
});
```

### Chain of Responsibility vs Decorator

```txt
Decorator:
  - ВСЕГДА оборачивает (добавляет поведение к каждому вызову)
  - Декорируемый объект ВСЕГДА вызывается
  - Цель: расширение функциональности

Chain of Responsibility:
  - Может ПРЕРВАТЬ цепочку (обработчик решает: продолжить или нет)
  - Следующий обработчик вызывается только если текущий решил передать
  - Цель: найти обработчик среди кандидатов

Express middleware — оба паттерна одновременно:
  - cors(), helmet() → Decorator (добавляют поведение, всегда вызывают next)
  - authenticate() → Chain of Responsibility (может вернуть 401 и не вызвать next)
```

---

## Сравнительная таблица поведенческих паттернов

```txt
Паттерн                 Суть                                   Реальный пример
──────────────────────────────────────────────────────────────────────────────
Observer                Подписка и уведомление                 EventEmitter, Redux store
Strategy                Взаимозаменяемый алгоритм              Passport.js strategies, Array.sort
Command                 Действие как объект                    Redux actions, BullMQ jobs
Iterator                Обход без раскрытия структуры          Generators, Streams, for-await-of
Template Method         Скелет алгоритма с хуками              DataImporter, React lifecycle
State                   Поведение зависит от состояния         XState, Order states
Mediator                Посредник вместо прямых связей         Redux Store, EventBus, Socket.IO room
Chain of Responsibility Цепочка обработчиков с возможностью   Express middleware, NestJS Guards
                        прервать цепочку
```

## Типичные ошибки на интервью

- **"Observer = EventEmitter"** — EventEmitter — реализация Observer в Node.js, но паттерн шире. Pub/Sub системы (Redis pub/sub, Kafka, WebSocket broadcast) — тоже Observer. Важно понимать паттерн, а не только конкретную реализацию.

- **Путать Strategy и State** — оба меняют поведение объекта. Strategy — внешний клиент выбирает алгоритм (сортировка, ценообразование). State — объект сам меняет своё поведение при переходе в другое состояние (заказ: pending → paid → shipped). Ключевое: **кто инициирует смену** — клиент (Strategy) или сам объект (State).

- **"Redux — это просто Flux"** — Redux реализует Command (action-объекты), Observer (store.subscribe), и Singleton (один store). Называние паттернов в контексте Redux показывает глубину понимания.

- **Template Method всегда лучше Strategy** — наоборот: GoF сам рекомендует предпочитать композицию (Strategy) наследованию (Template Method). Template Method оправдан, когда "скелет алгоритма" сам по себе важная архитектурная концепция.

- **Chain of Responsibility == Decorator** — распространённая путаница. Decorator ВСЕГДА оборачивает; Chain of Responsibility может прервать цепочку. Express middleware — оба одновременно, в зависимости от конкретного обработчика.

- **Iterator только как паттерн "класс с hasNext/next"** — в TypeScript/JavaScript Iterator встроен в язык: `Symbol.iterator`, генераторы, `for-of`, `for-await-of`. Незнание встроенного протокола итерации при обсуждении паттерна Iterator — слабое место.

- **Mediator = "God Object"** — риск реальный. Mediator становится антипаттерном, когда он знает слишком много о каждом из участников. Хороший Mediator координирует взаимодействие, не содержит бизнес-логику участников. Redux — хороший пример: store не знает, зачем компонент подписывается на данные.
