# Структурные паттерны (Structural Patterns)

## Зачем нужны структурные паттерны

Структурные паттерны описывают **как компоновать классы и объекты в более крупные структуры**, сохраняя гибкость. Там где порождающие паттерны отвечают на "как создать объект", структурные отвечают на "как соединить объекты так, чтобы интерфейс системы оставался простым, а внутренняя сложность — инкапсулированной".

```txt
Порождающие → "кто и как создаёт"
Структурные  → "как объекты и классы связываются между собой"
Поведенческие → "как объекты взаимодействуют и распределяют ответственность"
```

---

## Adapter — "переходник между несовместимыми интерфейсами"

> Преобразует интерфейс класса в другой интерфейс, который ожидает клиент. Позволяет классам с несовместимыми интерфейсами работать вместе.

Adapter — один из самых частых паттернов в реальном коде: почти каждый раз, когда подключаешь стороннюю библиотеку к своей архитектуре, нужен адаптер.

### Пример: адаптация стороннего email-клиента

```ts
// Внутренний интерфейс приложения:
interface EmailService {
  send(to: string, subject: string, body: string): Promise<void>;
}

// Сторонняя библиотека — Sendgrid SDK с ДРУГИМ интерфейсом:
class SendgridClient {
  async sendMail(params: {
    personalizations: Array<{ to: Array<{ email: string }> }>;
    from: { email: string };
    subject: string;
    content: Array<{ type: string; value: string }>;
  }): Promise<void> {
    // ... реальный HTTP-запрос к Sendgrid API
  }
}

// ❌ Без адаптера — вся кодовая база знает о Sendgrid-специфичном формате:
async function notifyUser(userId: string, message: string) {
  await sendgridClient.sendMail({
    personalizations: [{ to: [{ email: user.email }] }],
    from: { email: 'noreply@app.com' },
    subject: 'Notification',
    content: [{ type: 'text/plain', value: message }],
  });
  // Смена Sendgrid на Mailgun → правки во всём коде
}

// ✅ Adapter: оборачиваем Sendgrid в наш EmailService-интерфейс

class SendgridAdapter implements EmailService {
  constructor(
    private readonly client: SendgridClient,
    private readonly fromEmail: string,
  ) {}

  async send(to: string, subject: string, body: string): Promise<void> {
    await this.client.sendMail({
      personalizations: [{ to: [{ email: to }] }],
      from: { email: this.fromEmail },
      subject,
      content: [{ type: 'text/plain', value: body }],
    });
  }
}

// Весь код работает с EmailService — замена Sendgrid на Mailgun:
// создать новый MailgunAdapter, поменять в DI-контейнере, остальной код не трогать
async function notifyUser(emailService: EmailService, userEmail: string, message: string) {
  await emailService.send(userEmail, 'Notification', message);
}
```

### Реальный контекст (React)

```tsx
// Adapter в React — обёртка вокруг сторонней UI-библиотеки
// под внутренний интерфейс компонентов приложения

// Внешняя библиотека react-select имеет свой API:
import ReactSelect from 'react-select';

// Внутренний интерфейс приложения:
interface SelectProps {
  options: Array<{ value: string; label: string }>;
  value: string;
  onChange: (value: string) => void;
}

// Adapter: переводит внутренний интерфейс в react-select API
function AppSelect({ options, value, onChange }: SelectProps) {
  return (
    <ReactSelect
      options={options}
      value={options.find(o => o.value === value)}
      onChange={(opt) => opt && onChange(opt.value)}
    />
  );
}

// Теперь весь код использует <AppSelect> с простым API.
// Смена react-select на другую библиотеку — только в AppSelect.
```

---

## Bridge — "разделить абстракцию и реализацию"

> Разделяет абстракцию и реализацию так, чтобы они могли изменяться независимо.

Bridge решает проблему "взрывного роста подклассов" при комбинировании двух осей изменений. Без Bridge: N абстракций × M реализаций = N×M классов. С Bridge: N + M классов.

```txt
Без Bridge (взрывной рост):
  LightThemeButton, DarkThemeButton
  LightThemeInput, DarkThemeInput
  LightThemeModal, DarkThemeModal
  ... при добавлении темы SystemTheme → ещё 3 класса

С Bridge (N + M):
  Button(theme), Input(theme), Modal(theme)
  LightTheme, DarkTheme, SystemTheme
  → добавить тему = 1 новый класс
  → добавить компонент = 1 новый класс
```

### Пример: рендерер + тема

```ts
// "Реализация" — тема оформления (ось 1)
interface Theme {
  buttonStyle(): string;
  inputStyle(): string;
  backgroundColor(): string;
}

class LightTheme implements Theme {
  buttonStyle() { return 'bg-white text-black border border-gray-300'; }
  inputStyle() { return 'bg-white border border-gray-200'; }
  backgroundColor() { return '#ffffff'; }
}

class DarkTheme implements Theme {
  buttonStyle() { return 'bg-gray-800 text-white border border-gray-600'; }
  inputStyle() { return 'bg-gray-700 border border-gray-600 text-white'; }
  backgroundColor() { return '#1a1a1a'; }
}

// "Абстракция" — UI-компонент (ось 2)
// Bridge: абстракция держит ссылку на реализацию (theme)
abstract class UIComponent {
  constructor(protected readonly theme: Theme) {}
  abstract render(): string;
}

class Button extends UIComponent {
  constructor(theme: Theme, private readonly label: string) {
    super(theme);
  }
  render(): string {
    return `<button class="${this.theme.buttonStyle()}">${this.label}</button>`;
  }
}

class TextInput extends UIComponent {
  constructor(theme: Theme, private readonly placeholder: string) {
    super(theme);
  }
  render(): string {
    return `<input class="${this.theme.inputStyle()}" placeholder="${this.placeholder}" />`;
  }
}

// Добавить SystemTheme → 1 новый Theme-класс, Button и TextInput не трогаем
// Добавить Checkbox → 1 новый UIComponent-класс, темы не трогаем
const darkButton = new Button(new DarkTheme(), 'Submit');
const lightInput = new TextInput(new LightTheme(), 'Enter email');
```

### Bridge vs Strategy

```txt
Bridge — структурный паттерн: реализация выбирается при создании объекта
  и обычно не меняется (это архитектурное решение о том, как объект устроен)

Strategy — поведенческий паттерн: алгоритм можно подменять во время
  выполнения (это решение о том, как объект ведёт себя в конкретный момент)

Граница размытая — часто одно и то же реализуется через оба.
Ключевой вопрос: "это постоянная структура или сменяемое поведение?"
```

---

## Composite — "дерево объектов, единый интерфейс"

> Компонует объекты в древовидные структуры для представления иерархий "часть-целое". Позволяет клиенту единообразно работать с отдельными объектами и их композициями.

Composite нужен всякий раз, когда структура данных рекурсивна: файловая система, DOM-дерево, организационная иерархия, категории товаров.

### Пример: файловая система

```ts
// Единый интерфейс для файлов и директорий
interface FileSystemItem {
  name: string;
  size(): number;
  print(indent?: string): void;
}

// Лист (leaf) — файл, не может содержать дочерние элементы
class File implements FileSystemItem {
  constructor(
    public readonly name: string,
    private readonly sizeInBytes: number,
  ) {}

  size(): number { return this.sizeInBytes; }

  print(indent = ''): void {
    console.log(`${indent}📄 ${this.name} (${this.sizeInBytes}B)`);
  }
}

// Составной элемент (composite) — директория
class Directory implements FileSystemItem {
  private children: FileSystemItem[] = [];

  constructor(public readonly name: string) {}

  add(item: FileSystemItem): void { this.children.push(item); }
  remove(item: FileSystemItem): void {
    this.children = this.children.filter(c => c !== item);
  }

  // Рекурсивно суммирует размеры всех дочерних элементов
  size(): number {
    return this.children.reduce((total, child) => total + child.size(), 0);
  }

  print(indent = ''): void {
    console.log(`${indent}📁 ${this.name}/`);
    this.children.forEach(child => child.print(indent + '  '));
  }
}

// Клиентский код работает с FileSystemItem — не знает, файл это или директория:
const root = new Directory('project');
const src = new Directory('src');
src.add(new File('index.ts', 1024));
src.add(new File('app.ts', 2048));

const node_modules = new Directory('node_modules');
node_modules.add(new File('express.js', 51200));

root.add(src);
root.add(node_modules);
root.add(new File('package.json', 512));

root.print();
// 📁 project/
//   📁 src/
//     📄 index.ts (1024B)
//     📄 app.ts (2048B)
//   📁 node_modules/
//     📄 express.js (51200B)
//   📄 package.json (512B)

console.log(`Total: ${root.size()}B`); // рекурсивно считает всё дерево
```

### Реальный контекст (React)

```tsx
// React-дерево компонентов — это Composite:
// каждый компонент может содержать другие компоненты или быть листом

// Составной компонент:
function Layout({ children }: { children: React.ReactNode }) {
  return <div className="layout">{children}</div>;
}

// Использование — единый интерфейс children для любой вложенности:
<Layout>
  <Header />           {/* лист */}
  <Layout>             {/* составной */}
    <Sidebar />        {/* лист */}
    <MainContent />    {/* лист */}
  </Layout>
  <Footer />           {/* лист */}
</Layout>
```

---

## Decorator — "добавить поведение без изменения класса"

> Динамически добавляет объекту новые обязанности. Является гибкой альтернативой наследованию для расширения функциональности.

Decorator оборачивает объект в другой объект с тем же интерфейсом, добавляя поведение до или после оригинальной операции.

### Пример: HTTP-клиент с декораторами

```ts
interface HttpClient {
  get<T>(url: string): Promise<T>;
  post<T>(url: string, body: unknown): Promise<T>;
}

// Базовая реализация
class FetchHttpClient implements HttpClient {
  async get<T>(url: string): Promise<T> {
    const res = await fetch(url);
    return res.json() as Promise<T>;
  }
  async post<T>(url: string, body: unknown): Promise<T> {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return res.json() as Promise<T>;
  }
}

// Декоратор логирования — не меняет базовый клиент
class LoggingHttpClient implements HttpClient {
  constructor(
    private readonly client: HttpClient,
    private readonly logger: Logger,
  ) {}

  async get<T>(url: string): Promise<T> {
    this.logger.info(`GET ${url}`);
    const result = await this.client.get<T>(url);
    this.logger.info(`GET ${url} → OK`);
    return result;
  }

  async post<T>(url: string, body: unknown): Promise<T> {
    this.logger.info(`POST ${url}`, { body });
    const result = await this.client.post<T>(url, body);
    this.logger.info(`POST ${url} → OK`);
    return result;
  }
}

// Декоратор retry — оборачивает другой HttpClient (в т.ч. уже декорированный)
class RetryHttpClient implements HttpClient {
  constructor(
    private readonly client: HttpClient,
    private readonly maxRetries: number = 3,
  ) {}

  async get<T>(url: string): Promise<T> {
    return this.withRetry(() => this.client.get<T>(url));
  }

  async post<T>(url: string, body: unknown): Promise<T> {
    return this.withRetry(() => this.client.post<T>(url, body));
  }

  private async withRetry<T>(operation: () => Promise<T>): Promise<T> {
    let lastError: Error;
    for (let attempt = 1; attempt <= this.maxRetries; attempt++) {
      try {
        return await operation();
      } catch (err) {
        lastError = err as Error;
        if (attempt < this.maxRetries) {
          await new Promise(r => setTimeout(r, 2 ** attempt * 100)); // exponential backoff
        }
      }
    }
    throw lastError!;
  }
}

// Стек декораторов — оборачиваем по одному:
const client: HttpClient = new RetryHttpClient(
  new LoggingHttpClient(
    new FetchHttpClient(),
    logger,
  ),
  3,
);

// Интерфейс не изменился — потребитель не знает о декораторах:
const user = await client.get<User>('/api/users/1');
```

### HOC (Higher-Order Component) как Decorator в React

```tsx
// HOC — классический пример Decorator в React:
// оборачивает компонент, добавляя поведение (аутентификацию, логирование, доступность)

function withAuth<P extends object>(Component: React.FC<P>): React.FC<P> {
  return function AuthGuard(props: P) {
    const { isAuthenticated } = useAuth();
    if (!isAuthenticated) return <Navigate to="/login" />;
    return <Component {...props} />;
  };
}

function withErrorBoundary<P extends object>(Component: React.FC<P>): React.FC<P> {
  return function WithBoundary(props: P) {
    return (
      <ErrorBoundary fallback={<ErrorPage />}>
        <Component {...props} />
      </ErrorBoundary>
    );
  };
}

// Стек декораторов — композиция HOC'ов:
const ProtectedDashboard = withAuth(withErrorBoundary(Dashboard));
```

### TypeScript-декораторы (`@Decorator`) — это тоже Decorator паттерн?

```ts
// TypeScript decorators (@Injectable, @Controller, @Get) — 
// это метаданные и трансформации класса на уровне компилятора.
// По структуре они похожи на Decorator паттерн (оборачивают/модифицируют класс),
// но реализуются через Reflect.metadata, а не через обёртку с тем же интерфейсом.

@Injectable()
class UserService {
  // @Injectable добавляет метаданные для DI-контейнера NestJS —
  // это Decorator паттерн по духу, но не по классической GoF-структуре
}
```

---

## Facade — "простой фасад для сложной подсистемы"

> Предоставляет унифицированный интерфейс к набору интерфейсов подсистемы. Упрощает использование сложной подсистемы.

Facade — самый "человечный" структурный паттерн: он не добавляет новое поведение, он просто скрывает сложность.

### Пример: оформление заказа

```ts
// Подсистемы с собственными сложными интерфейсами:
class InventoryService {
  async checkStock(productId: string, qty: number): Promise<boolean> { ... }
  async reserveStock(productId: string, qty: number): Promise<string> { ... }
  async releaseReservation(reservationId: string): Promise<void> { ... }
}

class PaymentService {
  async createPaymentIntent(amount: number, currency: string): Promise<string> { ... }
  async confirmPayment(intentId: string, methodId: string): Promise<Receipt> { ... }
  async refund(intentId: string): Promise<void> { ... }
}

class ShippingService {
  async calculateRate(address: Address, weight: number): Promise<number> { ... }
  async createShipment(orderId: string, address: Address): Promise<TrackingNumber> { ... }
  async cancelShipment(trackingNumber: string): Promise<void> { ... }
}

class NotificationService {
  async sendOrderConfirmation(email: string, orderId: string): Promise<void> { ... }
  async sendShippingUpdate(email: string, trackingNumber: string): Promise<void> { ... }
}

// ❌ Без фасада — контроллер координирует все подсистемы вручную,
// знает об их деталях и их порядке:

@Post('/orders')
async checkout(dto: CheckoutDto) {
  const inStock = await this.inventoryService.checkStock(dto.productId, dto.qty);
  if (!inStock) throw new BadRequestException('Out of stock');
  const reservationId = await this.inventoryService.reserveStock(dto.productId, dto.qty);
  const intentId = await this.paymentService.createPaymentIntent(dto.amount, 'usd');
  let receipt: Receipt;
  try {
    receipt = await this.paymentService.confirmPayment(intentId, dto.paymentMethodId);
  } catch (e) {
    await this.inventoryService.releaseReservation(reservationId);
    throw e;
  }
  const tracking = await this.shippingService.createShipment(dto.orderId, dto.address);
  await this.notificationService.sendOrderConfirmation(dto.email, dto.orderId);
  return { receipt, tracking };
}

// ✅ Facade: OrderFacade скрывает оркестрацию — контроллер делает один вызов

class OrderFacade {
  constructor(
    private readonly inventory: InventoryService,
    private readonly payment: PaymentService,
    private readonly shipping: ShippingService,
    private readonly notification: NotificationService,
  ) {}

  async placeOrder(dto: CheckoutDto): Promise<OrderResult> {
    const inStock = await this.inventory.checkStock(dto.productId, dto.qty);
    if (!inStock) throw new Error('Out of stock');

    const reservationId = await this.inventory.reserveStock(dto.productId, dto.qty);
    const intentId = await this.payment.createPaymentIntent(dto.amount, 'usd');

    let receipt: Receipt;
    try {
      receipt = await this.payment.confirmPayment(intentId, dto.paymentMethodId);
    } catch (e) {
      await this.inventory.releaseReservation(reservationId);
      throw e;
    }

    const tracking = await this.shipping.createShipment(dto.orderId, dto.address);
    await this.notification.sendOrderConfirmation(dto.email, dto.orderId);

    return { receipt, tracking };
  }
}

// Контроллер — один вызов, не знает о деталях подсистем:
@Post('/orders')
async checkout(dto: CheckoutDto) {
  return this.orderFacade.placeOrder(dto);
}
```

### Facade vs Controller (GRASP)

```txt
Controller (GRASP) — тонкий слой между HTTP и бизнес-логикой, не содержит логики сам.
Facade — содержит оркестрационную логику между подсистемами, скрывает их от клиента.

Часто в NestJS: Controller → Facade → отдельные Services.
Facade — это не Controller, это слой между контроллером и доменом.
```

---

## Flyweight — "разделить общее состояние между множеством объектов"

> Использует разделение для эффективной поддержки большого числа мелких объектов.

Flyweight нужен, когда создаётся огромное количество объектов с общим неизменяемым состоянием. Вместо того чтобы хранить это состояние в каждом объекте — хранить его один раз и разделять.

```txt
Intrinsic state (внутреннее, разделяемое):
  Неизменяемые данные, общие для многих объектов.
  Хранится в Flyweight-объекте.

Extrinsic state (внешнее, контекстное):
  Уникальные данные для каждого использования.
  Передаётся при вызове метода, не хранится в Flyweight.
```

### Пример: рендеринг символов в текстовом редакторе

```ts
// Flyweight — неизменяемые данные символа (шрифт, размер, стиль)
class CharacterGlyph {
  constructor(
    public readonly font: string,
    public readonly size: number,
    public readonly bold: boolean,
    public readonly italic: boolean,
  ) {}

  render(char: string, x: number, y: number): void {
    // Дорогая операция рендеринга — но glyph один на все символы с этим стилем
    console.log(`Render '${char}' at (${x},${y}) in ${this.font} ${this.size}px`);
  }
}

// Flyweight Factory — возвращает существующий glyph или создаёт новый
class GlyphFactory {
  private readonly glyphs = new Map<string, CharacterGlyph>();

  getGlyph(font: string, size: number, bold: boolean, italic: boolean): CharacterGlyph {
    const key = `${font}-${size}-${bold}-${italic}`;
    if (!this.glyphs.has(key)) {
      this.glyphs.set(key, new CharacterGlyph(font, size, bold, italic));
    }
    return this.glyphs.get(key)!;
  }

  get glyphCount(): number { return this.glyphs.size; }
}

// Символ в документе — только экстринсик (позиция, сам символ) + ссылка на flyweight
class Character {
  constructor(
    private readonly char: string,
    private readonly x: number,
    private readonly y: number,
    private readonly glyph: CharacterGlyph, // разделяемый flyweight
  ) {}

  render(): void { this.glyph.render(this.char, this.x, this.y); }
}

// 100 000 символов документа — но только несколько уникальных glyphs:
const factory = new GlyphFactory();
const document: Character[] = [];

for (let i = 0; i < 100_000; i++) {
  const glyph = factory.getGlyph('Arial', 14, false, false); // один и тот же объект
  document.push(new Character('A', i * 10, 0, glyph));
}

console.log(factory.glyphCount); // 1, не 100 000
```

### Flyweight в реальных системах

```txt
Реальные примеры Flyweight:
  - Пул строк (String interning): одинаковые строки хранятся
    как один объект в памяти
  - Пул соединений с БД: соединения разделяются между запросами
  - Иконки и спрайты в UI: один объект изображения используется
    в тысячах мест DOM
  - Virtual DOM в React: React переиспользует DOM-узлы
    при рендеринге списков (key-пропс)
```

---

## Proxy — "суррогат с дополнительным контролем"

> Предоставляет суррогатный объект, контролирующий доступ к другому объекту.

Proxy имеет тот же интерфейс, что и целевой объект, но перехватывает вызовы, добавляя: ленивую инициализацию, кеширование, контроль доступа, логирование.

```txt
Виды Proxy:
  Virtual Proxy    — ленивая инициализация (объект создаётся при первом обращении)
  Protection Proxy — контроль доступа (проверка прав перед делегированием)
  Caching Proxy    — кеширует результаты дорогих операций
  Remote Proxy     — представляет удалённый объект (RPC, микросервисы)
  Logging Proxy    — логирует обращения (как Decorator, но через Proxy)
```

### Пример: Caching Proxy для репозитория

```ts
interface UserRepository {
  findById(id: string): Promise<User | null>;
  findByEmail(email: string): Promise<User | null>;
  save(user: User): Promise<User>;
}

class PostgresUserRepository implements UserRepository {
  async findById(id: string): Promise<User | null> {
    return db.query('SELECT * FROM users WHERE id = $1', [id]);
  }
  async findByEmail(email: string): Promise<User | null> {
    return db.query('SELECT * FROM users WHERE email = $1', [email]);
  }
  async save(user: User): Promise<User> {
    // INSERT или UPDATE
    return db.query('...');
  }
}

// Caching Proxy — тот же интерфейс, добавляет кеш
class CachedUserRepository implements UserRepository {
  private readonly cache = new Map<string, User>();

  constructor(private readonly repository: UserRepository) {}

  async findById(id: string): Promise<User | null> {
    if (this.cache.has(id)) {
      return this.cache.get(id)!; // cache hit — не идём в БД
    }
    const user = await this.repository.findById(id);
    if (user) this.cache.set(id, user);
    return user;
  }

  async findByEmail(email: string): Promise<User | null> {
    return this.repository.findByEmail(email); // не кешируем по email
  }

  async save(user: User): Promise<User> {
    const saved = await this.repository.save(user);
    this.cache.set(saved.id, saved); // инвалидируем и обновляем кеш
    return saved;
  }
}

// Потребитель не знает о кеше — просто получает UserRepository:
const userRepo: UserRepository = new CachedUserRepository(
  new PostgresUserRepository(),
);
```

### Proxy через JavaScript `Proxy`

```ts
// ES6 Proxy — встроенный механизм перехвата операций над объектом

function createValidationProxy<T extends object>(target: T, schema: Schema<T>): T {
  return new Proxy(target, {
    set(obj, prop, value) {
      const fieldSchema = schema[prop as keyof T];
      if (fieldSchema && !fieldSchema.validate(value)) {
        throw new Error(`Invalid value for ${String(prop)}: ${value}`);
      }
      obj[prop as keyof T] = value;
      return true;
    },
  });
}

const user = createValidationProxy({ name: '', age: 0 }, {
  name: { validate: (v: string) => v.length > 0 },
  age: { validate: (v: number) => v >= 0 && v <= 150 },
});

user.name = 'Alice';  // OK
user.age = -1;        // throws: Invalid value for age: -1
```

### Express middleware как цепочка Proxy/Decorator

```ts
// Express middleware — это функциональный аналог цепочки Decorator/Proxy:
// каждый middleware обёртывает обработку запроса, добавляя поведение

app.use(cors());             // Decorator: добавляет CORS-заголовки
app.use(helmet());           // Decorator: добавляет security-заголовки
app.use(rateLimiter());      // Proxy: контролирует доступ (rate limiting)
app.use(authenticate());     // Protection Proxy: проверяет токен
app.use(requestLogger());    // Logging Proxy: логирует запросы
app.use('/api', router);     // наконец — настоящий обработчик
```

---

## Сравнительная таблица структурных паттернов

```txt
Паттерн    Суть                                      Реальный пример
────────────────────────────────────────────────────────────────────────
Adapter    Переводит чужой интерфейс в свой          Sendgrid SDK → EmailService
Bridge     Разделяет абстракцию и реализацию         Компонент × Тема
Composite  Дерево объектов с единым интерфейсом      React-дерево, файловая система
Decorator  Оборачивает объект, добавляя поведение    HOC, HTTP-клиент с retry+logging
Facade     Упрощённый интерфейс к подсистеме         OrderFacade, BFF-слой
Flyweight  Разделяет общее состояние                 Пул строк, пул соединений
Proxy      Суррогат с дополнительным контролем       Кеш, auth-guard, ES6 Proxy
```

## Типичные ошибки на интервью

- **Путать Adapter и Facade** — Adapter меняет интерфейс одного объекта. Facade создаёт упрощённый интерфейс над несколькими объектами/подсистемами. Ключевая разница: Adapter работает с одним объектом, Facade — с группой.

- **Путать Decorator и Proxy** — оба оборачивают объект. Decorator **добавляет** новое поведение/функциональность. Proxy **контролирует доступ** к существующему поведению. На практике граница размытая, но на интервью уточни: "Decorator = расширение, Proxy = контроль доступа".

- **"HOC — это не паттерн, это просто React-фича"** — HOC — это прямая реализация Decorator паттерна в функциональном стиле. Умение назвать паттерн за конкретной техникой — признак системного мышления.

- **Flyweight без разделения intrinsic/extrinsic state** — без чёткого определения, что общее (неизменяемое) и что контекстное (уникальное), Flyweight превращается в обычный кеш. Разделение состояния — суть паттерна.

- **Composite только для файловых систем** — это самый известный пример, но Composite встречается везде, где есть рекурсивная структура: DOM, AST, организационные иерархии, menu/submenu, категории с подкатегориями.

- **Proxy и ES6 `new Proxy()`** — ES6 Proxy реализует паттерн Proxy, но это не одно и то же. Паттерн Proxy — архитектурная идея о суррогатном объекте. ES6 Proxy — языковой механизм, который удобно использовать для реализации паттерна, но не исчерпывает его.

- **Не знать, что Express middleware — это структурный паттерн** — цепочку middleware через `app.use()` можно и нужно описывать через паттерны: Decorator (добавляет поведение) и Chain of Responsibility (передаёт управление через `next()`). Это показывает понимание паттернов в реальном коде, а не только в учебниках.
