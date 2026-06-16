# Паттерны на практике

## От теории к реальному коду

Паттерны редко встречаются в изоляции. В реальных проектах одна архитектурная задача решается комбинацией нескольких паттернов, и способность распознать эти комбинации — признак зрелости разработчика.

```txt
Изучить паттерн по учебнику → узнать паттерн в готовом коде →
  распознать паттерн в "незаконченном" коде (антипаттерне) →
    самостоятельно выбрать нужный паттерн для новой задачи

Этот файл — про третий и четвёртый уровень.
```

---

## Антипаттерны — что распознавать на код-ревью

Антипаттерн — это решение, которое кажется разумным, применяется часто, но систематически создаёт проблемы. Знание антипаттернов так же важно, как знание паттернов.

### God Object (Объект-бог)

Класс, который знает слишком много и делает слишком много. Нарушает SRP, High Cohesion и Low Coupling одновременно.

```ts
// ❌ UserManager — God Object: регистрация, авторизация, аватары,
// платежи, email, статистика, роли — всё в одном классе

class UserManager {
  private db: Database;
  private emailClient: EmailClient;
  private s3: S3Client;
  private stripeClient: StripeClient;
  private redisClient: RedisClient;

  async register(email: string, password: string) { ... }
  async login(email: string, password: string) { ... }
  async logout(userId: string) { ... }
  async uploadAvatar(userId: string, file: Buffer) { ... }
  async deleteAvatar(userId: string) { ... }
  async createSubscription(userId: string, planId: string) { ... }
  async cancelSubscription(userId: string) { ... }
  async sendWelcomeEmail(userId: string) { ... }
  async sendPasswordResetEmail(email: string) { ... }
  async getUserStats(userId: string) { ... }
  async assignRole(userId: string, role: string) { ... }
  async revokeRole(userId: string, role: string) { ... }
  async banUser(userId: string, reason: string) { ... }
  async unbanUser(userId: string) { ... }
  // ... ещё 20 методов
}

// ✅ Декомпозиция по ответственностям:
class AuthService { /* login, logout, tokens */ }
class UserRegistrationService { /* register, confirm email */ }
class AvatarService { /* upload, delete, resize */ }
class BillingService { /* subscriptions, payments */ }
class NotificationService { /* emails, push */ }
class UserAdminService { /* roles, bans */ }
```

**Признаки God Object:**
- Название класса заканчивается на `Manager`, `Handler`, `Controller`, `Processor` — без конкретизации предметной области
- Конструктор инжектирует 5+ зависимостей
- Файл длиннее 300-500 строк
- Метод класса не использует большинство его полей

### Spaghetti Code — скрытые зависимости и состояние

```ts
// ❌ Спагетти-код: функции зависят от глобального изменяемого состояния,
// порядок вызовов неочевиден, побочные эффекты скрыты

let currentUser: User | null = null;
let isProcessing = false;
let lastError: Error | null = null;

async function processOrder(orderId: string) {
  if (!currentUser) throw new Error('No user'); // скрытая зависимость от глобала
  if (isProcessing) return;                      // скрытое состояние
  isProcessing = true;
  try {
    await doPayment(orderId);   // модифицирует глобалы внутри себя
    await sendEmail(orderId);   // зависит от состояния doPayment
    isProcessing = false;
  } catch (e) {
    lastError = e as Error;     // сохраняет в глобал — когда это прочитать?
    isProcessing = false;
  }
}

// ✅ Явные зависимости, без глобального состояния:
class OrderProcessor {
  constructor(
    private readonly paymentService: PaymentService,
    private readonly notificationService: NotificationService,
  ) {}

  async process(orderId: string, userId: string): Promise<OrderResult> {
    const payment = await this.paymentService.charge(orderId, userId);
    await this.notificationService.sendConfirmation(userId, orderId);
    return { orderId, paymentId: payment.id };
  }
}
```

### Golden Hammer — "если у тебя есть молоток, всё выглядит как гвоздь"

```txt
Проявления Golden Hammer:
  - "Мы используем Redux для всего состояния" → даже для local UI-state
    одного компонента, который не нужен нигде больше
  - "Мы используем микросервисы" → для приложения, которое пишут 2 человека
  - "Мы используем очередь задач" → для синхронной операции в 10мс
  - "Мы используем Singleton" → для каждого сервиса

Антидот: явно формулировать проблему ДО выбора решения.
Паттерн — ответ на вопрос "почему?", а не на "что использовать следующим?"
```

### Primitive Obsession — значения без поведения

```ts
// ❌ Примитивы везде: string как email, string как userId, number как деньги
function sendInvoice(userId: string, email: string, amount: number) {
  // userId и email — оба string, легко перепутать аргументы при вызове
  // amount — number, но 10.005 — валидная сумма?
}

sendInvoice(user.email, user.id, 99.99); // перепутали — TypeScript не поймает

// ✅ Value Objects с валидацией и поведением:
class Email {
  private constructor(private readonly value: string) {}

  static create(raw: string): Email {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(raw)) {
      throw new Error(`Invalid email: ${raw}`);
    }
    return new Email(raw.toLowerCase());
  }

  toString(): string { return this.value; }
}

class Money {
  private constructor(
    private readonly amount: number, // в центах (целое число)
    private readonly currency: string,
  ) {}

  static fromDollars(dollars: number, currency = 'USD'): Money {
    return new Money(Math.round(dollars * 100), currency);
  }

  add(other: Money): Money {
    if (this.currency !== other.currency) throw new Error('Currency mismatch');
    return new Money(this.amount + other.amount, this.currency);
  }

  toDisplay(): string { return `$${(this.amount / 100).toFixed(2)}`; }
}

// Теперь TypeScript физически не позволит перепутать Email и UserId:
function sendInvoice(userId: UserId, email: Email, amount: Money) { ... }
```

### Анemic Domain Model

```ts
// ❌ "Анемичная модель": классы-данные без поведения,
// вся логика — в сервисах-процедурах

class Order {
  id: string = '';
  items: OrderItem[] = [];
  status: string = 'pending';
  total: number = 0;
  discountPercent: number = 0;
  // Только данные, никакой логики
}

// Вся бизнес-логика разбросана по сервисам:
class OrderService {
  calculateTotal(order: Order): number { // считает то, что Order должен знать о себе
    return order.items.reduce((s, i) => s + i.price * i.quantity, 0)
      * (1 - order.discountPercent / 100);
  }

  canCancel(order: Order): boolean { // Order мог бы знать это сам
    return order.status === 'pending' || order.status === 'paid';
  }
}

// ✅ Rich Domain Model: логика живёт там, где живут данные
class Order {
  private status: OrderStatus = 'pending';
  private items: OrderItem[] = [];
  private discountPercent: number = 0;

  get total(): number {
    return this.items.reduce((s, i) => s + i.price * i.quantity, 0)
      * (1 - this.discountPercent / 100);
  }

  canCancel(): boolean {
    return this.status === 'pending' || this.status === 'paid';
  }

  cancel(): void {
    if (!this.canCancel()) throw new Error(`Cannot cancel order in status: ${this.status}`);
    this.status = 'cancelled';
  }
}
```

---

## Комбинации паттернов в реальных проектах

### Repository + Proxy (кеш) + Decorator (логирование)

```ts
// Три паттерна, одна задача: прозрачный кеш запросов к БД с логированием

interface UserRepository {
  findById(id: string): Promise<User | null>;
  save(user: User): Promise<User>;
}

// Слой 1: реальное хранилище (конкретная реализация)
class PostgresUserRepository implements UserRepository {
  async findById(id: string) { ... }
  async save(user: User) { ... }
}

// Слой 2: Proxy с кешированием
class CachedUserRepository implements UserRepository {
  private cache = new Map<string, User>();

  constructor(private readonly inner: UserRepository) {}

  async findById(id: string) {
    return this.cache.get(id) ?? this.inner.findById(id).then(u => {
      if (u) this.cache.set(id, u);
      return u;
    });
  }

  async save(user: User) {
    const saved = await this.inner.save(user);
    this.cache.set(saved.id, saved);
    return saved;
  }
}

// Слой 3: Decorator с логированием (над кешем)
class LoggedUserRepository implements UserRepository {
  constructor(
    private readonly inner: UserRepository,
    private readonly logger: Logger,
  ) {}

  async findById(id: string) {
    const start = Date.now();
    const result = await this.inner.findById(id);
    this.logger.debug('findById', { id, found: !!result, ms: Date.now() - start });
    return result;
  }

  async save(user: User) {
    const result = await this.inner.save(user);
    this.logger.info('user.saved', { id: result.id });
    return result;
  }
}

// Сборка стека в DI-контейнере (NestJS):
{
  provide: UserRepository,
  useFactory: (db: Database, logger: Logger) =>
    new LoggedUserRepository(
      new CachedUserRepository(
        new PostgresUserRepository(db),
      ),
      logger,
    ),
  inject: [DATABASE, LOGGER],
}
```

### Factory + Strategy + Observer: обработка платежей

```ts
// Factory создаёт нужную Strategy, Observer уведомляет о результате

interface PaymentStrategy {
  pay(amount: Money, metadata: PaymentMetadata): Promise<PaymentResult>;
}

class StripeStrategy implements PaymentStrategy { ... }
class PaypalStrategy implements PaymentStrategy { ... }
class CryptoStrategy implements PaymentStrategy { ... }

// Factory выбирает стратегию
function createPaymentStrategy(method: string): PaymentStrategy {
  const strategies: Record<string, () => PaymentStrategy> = {
    stripe: () => new StripeStrategy(stripeClient),
    paypal: () => new PaypalStrategy(paypalClient),
    crypto: () => new CryptoStrategy(cryptoClient),
  };
  const factory = strategies[method];
  if (!factory) throw new Error(`Unknown payment method: ${method}`);
  return factory();
}

// Observer уведомляет подписчиков о событии
class PaymentService extends EventEmitter {
  async processPayment(method: string, amount: Money, meta: PaymentMetadata) {
    const strategy = createPaymentStrategy(method); // Factory
    const result = await strategy.pay(amount, meta); // Strategy
    this.emit('payment:completed', result);           // Observer
    return result;
  }
}

// Подписчики — независимы от PaymentService:
paymentService.on('payment:completed', (result) => analytics.track(result));
paymentService.on('payment:completed', (result) => emailService.sendReceipt(result));
paymentService.on('payment:completed', (result) => webhookService.notify(result));
```

---

## Паттерны в React

### Compound Components — "компонент как API"

Compound Components — это когда несколько компонентов работают вместе через общий контекст, давая пользователю гибкость композиции без prop drilling.

```tsx
// ❌ Монолитный компонент — всё через props, жёсткая структура:
<Select
  label="Country"
  options={countries}
  placeholder="Choose country"
  renderOption={(opt) => <Flag code={opt.value} />}
  footer={<Button>Add country</Button>}
/>

// ✅ Compound Components — гибкая композиция:
// Context (Mediator) разделяет состояние между компонентами

interface SelectContextValue {
  selected: string | null;
  onSelect: (value: string) => void;
}

const SelectContext = createContext<SelectContextValue | null>(null);

function useSelectContext() {
  const ctx = useContext(SelectContext);
  if (!ctx) throw new Error('Must be used within <Select>');
  return ctx;
}

// Корневой компонент — держит состояние и предоставляет контекст
function Select({ children, onChange }: { children: React.ReactNode; onChange?: (v: string) => void }) {
  const [selected, setSelected] = useState<string | null>(null);

  const onSelect = useCallback((value: string) => {
    setSelected(value);
    onChange?.(value);
  }, [onChange]);

  return (
    <SelectContext.Provider value={{ selected, onSelect }}>
      <div className="select">{children}</div>
    </SelectContext.Provider>
  );
}

// Sub-компоненты — используют контекст, не знают друг о друге
function SelectOption({ value, children }: { value: string; children: React.ReactNode }) {
  const { selected, onSelect } = useSelectContext();
  return (
    <div
      className={selected === value ? 'option selected' : 'option'}
      onClick={() => onSelect(value)}
    >
      {children}
    </div>
  );
}

function SelectTrigger({ children }: { children: React.ReactNode }) {
  const { selected } = useSelectContext();
  return <button>{selected ?? children}</button>;
}

// Использование — полная гибкость структуры:
<Select onChange={setCountry}>
  <SelectTrigger>Choose country</SelectTrigger>
  {countries.map(c => (
    <SelectOption key={c.code} value={c.code}>
      <Flag code={c.code} /> {c.name}
    </SelectOption>
  ))}
  <Button onClick={openAddCountryModal}>Add country</Button>
</Select>
```

**Паттерны внутри Compound Components:**
- Context → Mediator (разделяет состояние без prop drilling)
- SelectContext → Information Expert (компонент знает своё состояние)
- Composite (вложенные SelectOption внутри Select)

### Render Props

```tsx
// Render Prop — компонент делегирует рендеринг через функцию-пропс.
// По структуре близко к Strategy (стратегия рендеринга — снаружи).

interface DataFetcherProps<T> {
  url: string;
  render: (data: T | null, loading: boolean, error: Error | null) => React.ReactNode;
}

function DataFetcher<T>({ url, render }: DataFetcherProps<T>) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    setLoading(true);
    fetch(url)
      .then(r => r.json())
      .then(setData)
      .catch(setError)
      .finally(() => setLoading(false));
  }, [url]);

  return <>{render(data, loading, error)}</>;
}

// Использование — рендеринг определяет потребитель (Strategy):
<DataFetcher<User[]>
  url="/api/users"
  render={(users, loading, error) => {
    if (loading) return <Spinner />;
    if (error) return <ErrorMessage error={error} />;
    return <UserList users={users ?? []} />;
  }}
/>

// Современная альтернатива Render Props — custom hooks:
// (в 2024+ предпочтительнее, чем Render Props)
function useData<T>(url: string) {
  const [state, setState] = useState<{ data: T | null; loading: boolean; error: Error | null }>({
    data: null, loading: true, error: null,
  });

  useEffect(() => {
    fetch(url).then(r => r.json())
      .then(data => setState({ data, loading: false, error: null }))
      .catch(error => setState({ data: null, loading: false, error }));
  }, [url]);

  return state;
}
```

### HOC (Higher-Order Component) — Decorator в React

```tsx
// HOC — функция, принимающая компонент и возвращающая новый компонент.
// Decorator паттерн: добавляет поведение без изменения оригинала.

// HOC для логирования рендеров (debugging):
function withRenderLogger<P extends object>(
  Component: React.FC<P>,
  componentName: string,
): React.FC<P> {
  return function LoggedComponent(props: P) {
    useEffect(() => {
      console.log(`[${componentName}] rendered`, props);
    });
    return <Component {...props} />;
  };
}

// HOC для retry при ошибке загрузки данных:
function withRetry<P extends { onRetry?: () => void }>(
  Component: React.FC<P>,
  maxRetries = 3,
): React.FC<P> {
  return function WithRetry(props: P) {
    const [retryCount, setRetryCount] = useState(0);

    const handleRetry = useCallback(() => {
      if (retryCount < maxRetries) {
        setRetryCount(c => c + 1);
        props.onRetry?.();
      }
    }, [retryCount, props]);

    return <Component {...props} onRetry={handleRetry} />;
  };
}

// HOC vs custom hooks — когда что использовать:
// HOC: нужно обернуть JSX (ErrorBoundary, Theme Provider)
// Custom hook: нужно переиспользовать логику (fetch, timer, event listener)
```

---

## Паттерны в Node.js/NestJS

### Repository Pattern — абстракция над хранилищем

```ts
// Repository — Pure Fabrication (GRASP): не существует в доменной модели,
// но изолирует бизнес-логику от деталей хранилища

interface UserRepository {
  findById(id: string): Promise<User | null>;
  findByEmail(email: string): Promise<User | null>;
  findAll(filters: UserFilters): Promise<User[]>;
  save(user: User): Promise<User>;
  delete(id: string): Promise<void>;
}

// Для production: реальная реализация через TypeORM/Prisma
@Injectable()
class TypeOrmUserRepository implements UserRepository {
  constructor(
    @InjectRepository(UserEntity)
    private readonly repo: Repository<UserEntity>,
  ) {}

  async findById(id: string): Promise<User | null> {
    const entity = await this.repo.findOne({ where: { id } });
    return entity ? UserMapper.toDomain(entity) : null;
  }

  async save(user: User): Promise<User> {
    const entity = UserMapper.toEntity(user);
    const saved = await this.repo.save(entity);
    return UserMapper.toDomain(saved);
  }
  // ...
}

// Для тестов: in-memory реализация без БД
class InMemoryUserRepository implements UserRepository {
  private store = new Map<string, User>();

  async findById(id: string) { return this.store.get(id) ?? null; }
  async findByEmail(email: string) {
    return [...this.store.values()].find(u => u.email === email) ?? null;
  }
  async findAll(filters: UserFilters) { return [...this.store.values()]; }
  async save(user: User) { this.store.set(user.id, user); return user; }
  async delete(id: string) { this.store.delete(id); }
}
```

### Middleware Pipeline (Chain of Responsibility) в NestJS

```ts
// NestJS Guards, Interceptors, Pipes, Filters — это Chain of Responsibility,
// реализованный через декораторы (метаданные).
// Порядок выполнения фиксирован фреймворком:

// Guards → Interceptors (before) → Pipes → Handler → Interceptors (after) → Filters

@Injectable()
class AuthGuard implements CanActivate {
  // Chain of Responsibility: может прервать цепочку (вернуть false)
  canActivate(context: ExecutionContext): boolean {
    const request = context.switchToHttp().getRequest();
    return this.validateToken(request.headers.authorization);
  }
}

@Injectable()
class LoggingInterceptor implements NestInterceptor {
  // Decorator: оборачивает handler, добавляет логирование
  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    const start = Date.now();
    return next.handle().pipe(
      tap(() => console.log(`Request took ${Date.now() - start}ms`)),
    );
  }
}

@Injectable()
class ParseBodyPipe implements PipeTransform {
  // Chain of Responsibility + Strategy: трансформирует и валидирует входные данные
  transform(value: unknown, metadata: ArgumentMetadata) {
    return plainToInstance(metadata.metatype as Type, value);
  }
}
```

### Unit of Work + Repository — транзакции в доменном слое

```ts
// Unit of Work отслеживает все изменения в рамках одной операции
// и применяет их атомарно (один коммит)

interface UnitOfWork {
  users: UserRepository;
  orders: OrderRepository;
  commit(): Promise<void>;
  rollback(): Promise<void>;
}

class PostgresUnitOfWork implements UnitOfWork {
  private readonly client: PoolClient;

  constructor(pool: Pool) {
    // Конструктор приватный — используется UnitOfWorkFactory
  }

  static async create(pool: Pool): Promise<PostgresUnitOfWork> {
    const client = await pool.connect();
    await client.query('BEGIN');
    const uow = new PostgresUnitOfWork(client);
    return uow;
  }

  // Все репозитории работают в рамках одной транзакции:
  get users(): UserRepository { return new PostgresUserRepository(this.client); }
  get orders(): OrderRepository { return new PostgresOrderRepository(this.client); }

  async commit(): Promise<void> {
    await this.client.query('COMMIT');
    this.client.release();
  }

  async rollback(): Promise<void> {
    await this.client.query('ROLLBACK');
    this.client.release();
  }
}

// Использование:
async function transferOrder(pool: Pool, orderId: string, newUserId: string) {
  const uow = await PostgresUnitOfWork.create(pool);
  try {
    const order = await uow.orders.findById(orderId);
    const newUser = await uow.users.findById(newUserId);
    order.transferTo(newUser);
    await uow.orders.save(order);
    await uow.commit(); // один коммит для всех изменений
  } catch (err) {
    await uow.rollback();
    throw err;
  }
}
```

---

## Когда NOT применять паттерн

Это самый важный навык: знать, когда паттерн нужен, почти так же важно, как знать, как его реализовать.

```txt
Ситуация                          Паттерн?    Решение
──────────────────────────────────────────────────────────────
Один тип уведомления              Observer    Нет — просто вызов функции
Два типа, никогда не будет        Strategy    Нет — if/else честнее
больше
Простой CRUD без бизнес-          Repository  Возможно нет — ORM-запросы
логики                                        напрямую в сервисе достаточно
Один шаг "алгоритма"              Template    Нет — просто метод
                                  Method
Простой конфиг из 2-3 полей       Builder     Нет — object literal понятнее
```

**Правило трёх:** паттерн оправдан, когда есть (или почти наверняка будет) три или более различных случая применения. До этого момента — YAGNI.

---

## Типичные ошибки на интервью

- **"Я использую паттерны везде"** — красный флаг. Правильный ответ включает понимание trade-offs и YAGNI. Паттерн — инструмент под конкретную задачу, а не стиль кода по умолчанию.

- **Не видеть паттерны в знакомых инструментах** — Redux — это Command+Observer. Express middleware — Chain of Responsibility. React Context — Mediator. Passport.js — Strategy. Неумение назвать паттерн за готовой библиотекой сигнализирует о том, что знание паттернов — книжное, а не практическое.

- **"Anemic Domain Model — это нормально"** — смотря для чего. Для CRUD-сервиса без бизнес-логики — приемлемо. Для доменно-насыщенных систем (финансы, e-commerce, логистика) — техдолг, который нарастает с каждой итерацией.

- **Compound Components только для сложных компонентов** — Compound Components стоит применять, когда компонент имеет несколько взаимосвязанных sub-компонентов. Для простых случаев — обычные props. Критерий: "нужна ли пользователю компонента контроль над структурой?"

- **Repository как "просто обёртка над ORM"** — Repository решает другую задачу: изоляция бизнес-логики от деталей хранилища. Если методы Repository повторяют API ORM один-в-один без добавления доменной семантики — это действительно просто обёртка и паттерн использован неосмысленно.

- **God Object → немедленный рефакторинг** — в legacy-коде God Object — норма жизни. Правильный подход: не переписывать всё сразу (это несёт риск), а вытеснять его постепенно — выделять новые сервисы по принципу "открытого-закрытого", оставляя God Object фасадом на переходный период.

- **Не различать паттерны и принципы** — SOLID и GRASP — принципы (рекомендации о том, как думать об архитектуре). GoF-паттерны — конкретные решения для конкретных задач. Паттерн может реализовывать несколько принципов. Принцип может реализовываться через несколько паттернов.
