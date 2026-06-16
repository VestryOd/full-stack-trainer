# Паттерны GRASP

## Что такое GRASP и почему это не "ещё один список паттернов"

GRASP (General Responsibility Assignment Software Patterns) — это не паттерны реализации вроде Singleton или Observer. Это **принципы распределения ответственности**: ответы на вопрос "какой объект должен владеть этим поведением или знанием?"

```txt
Паттерны GoF (Creational/Structural/Behavioral) отвечают на:
  "Как реализовать X?"

GRASP отвечает на:
  "Кому назначить ответственность X?"

Это разные уровни абстракции. GRASP — ближе к SOLID по уровню,
чем к GoF по характеру. Они дополняют друг друга.
```

GRASP сформулировал Крэйг Ларман в книге "Applying UML and Patterns" (1997). В отличие от GoF-паттернов, GRASP менее известен на собеседованиях — но именно поэтому знание GRASP отличает кандидата, который думает об архитектуре, от кандидата, который просто выучил паттерны.

---

## 1. Information Expert — "знаешь данные? владей поведением"

> Ответственность за операцию следует назначать классу, который владеет информацией, необходимой для её выполнения.

Это самый фундаментальный принцип GRASP и одновременно самый часто нарушаемый. Нарушение выглядит как "сервис, который берёт данные объекта и считает что-то по ним снаружи" вместо того, чтобы делегировать вычисление самому объекту.

### Нарушение Information Expert

```ts
// ❌ OrderController знает о структуре Order (items, discount) и считает total снаружи.
// Если структура Order изменится — менять придётся и OrderController,
// и любое другое место, которое считает total руками.

class OrderController {
  getOrderTotal(order: Order): number {
    let subtotal = 0;
    for (const item of order.items) {
      subtotal += item.price * item.quantity;
    }
    // Знание о том, как применяется скидка, размазано по контроллеру
    if (order.discountPercent) {
      subtotal *= (1 - order.discountPercent / 100);
    }
    return subtotal;
  }
}
```

```ts
// ✅ Order сам знает свои items и discount — он и считает total.
// OrderController просто вызывает метод.

class Order {
  constructor(
    public readonly items: OrderItem[],
    public readonly discountPercent: number = 0,
  ) {}

  get total(): number {
    const subtotal = this.items.reduce(
      (sum, item) => sum + item.price * item.quantity,
      0
    );
    return subtotal * (1 - this.discountPercent / 100);
  }
}

class OrderController {
  getOrderTotal(order: Order): number {
    return order.total; // ответственность делегирована эксперту
  }
}
```

### Связь с SOLID

Information Expert — это практическая реализация SRP на уровне данных. Класс, который владеет данными, имеет одну причину изменяться в этом контексте: изменение самих данных или правил их обработки. Если логика вынесена наружу — появляется дополнительная причина изменений у внешнего класса.

### Реальный контекст (React)

```tsx
// ❌ Компонент-родитель знает о структуре CartItem и считает итог снаружи
function CartSummary({ items }: { items: CartItem[] }) {
  const total = items.reduce((s, i) => s + i.price * i.quantity, 0);
  return <div>Total: ${total}</div>;
}

// ✅ Модель Cart — Information Expert, она считает total
class Cart {
  constructor(public readonly items: CartItem[]) {}
  get total() {
    return this.items.reduce((s, i) => s + i.price * i.quantity, 0);
  }
}

function CartSummary({ cart }: { cart: Cart }) {
  return <div>Total: ${cart.total}</div>;
}
```

---

## 2. Creator — "создаёт тот, кто содержит или использует"

> Класс B должен создавать экземпляры класса A, если B содержит A, агрегирует A, является инициализирующим для A, или владеет данными для создания A.

Creator отвечает на вопрос "где написать `new`?" без необходимости всегда выносить создание в фабрику.

### Нарушение Creator

```ts
// ❌ Внешний сервис создаёт OrderItem — хотя OrderItem
// существует только в контексте Order

class OrderService {
  createOrder(data: CreateOrderDto): Order {
    // OrderService не "владеет" OrderItem — зачем ему его создавать?
    const items = data.items.map(
      itemData => new OrderItem(itemData.productId, itemData.price, itemData.quantity)
    );
    return new Order(items);
  }
}
```

```ts
// ✅ Order агрегирует OrderItem — он и знает, как их создавать

class Order {
  private items: OrderItem[] = [];

  addItem(productId: string, price: number, quantity: number): void {
    // Order — создатель OrderItem, потому что он их содержит
    this.items.push(new OrderItem(productId, price, quantity));
  }

  static fromDto(dto: CreateOrderDto): Order {
    const order = new Order();
    for (const item of dto.items) {
      order.addItem(item.productId, item.price, item.quantity);
    }
    return order;
  }
}

class OrderService {
  createOrder(data: CreateOrderDto): Order {
    return Order.fromDto(data); // создание инкапсулировано внутри Order
  }
}
```

### Связь с SOLID

Creator связан с SRP: если класс создаёт объекты, которые ему "не принадлежат", это добавляет лишнюю ответственность. Creator также перекликается с паттерном Factory (см. [Creational Patterns]) — Factory нужна тогда, когда условие "содержит или использует" не выполняется и нужна выделенная точка создания.

---

## 3. Controller — "один входной фасад для системного события"

> Ответственность за обработку системного события следует делегировать классу-контроллеру, который представляет либо систему в целом, либо use case сценарий.

Controller — это посредник между UI/API-слоем и бизнес-логикой. Он не содержит логики сам — он делегирует её доменным объектам или сервисам.

### Нарушение Controller

```ts
// ❌ Контроллер содержит бизнес-логику —
// он одновременно парсит запрос, валидирует, считает скидку,
// формирует чек и отправляет email

@Post('/orders')
async createOrder(@Body() dto: CreateOrderDto, @Req() req: Request) {
  // Логика скидки — в контроллере!
  const discount = req.user.isPremium ? 0.15 : 0;

  let total = 0;
  for (const item of dto.items) {
    total += item.price * item.quantity;
  }
  total *= (1 - discount);

  const order = await this.db.orders.insert({ ...dto, total, userId: req.user.id });

  // Email — тоже в контроллере!
  await this.emailClient.send({
    to: req.user.email,
    subject: 'Order confirmed',
    body: `Your order #${order.id} total is $${total}`,
  });

  return order;
}
```

```ts
// ✅ Контроллер — тонкий: принять запрос, делегировать, вернуть ответ

@Post('/orders')
async createOrder(
  @Body() dto: CreateOrderDto,
  @CurrentUser() user: User,
): Promise<OrderResponseDto> {
  // Вся логика в OrderService — контроллер только оркестрирует
  const order = await this.orderService.createOrder(user, dto);
  return OrderResponseDto.fromDomain(order);
}
```

### Связь с SOLID

"Тонкий контроллер" — прямое следствие SRP (контроллер меняется только при изменении HTTP-интерфейса) и DIP (контроллер зависит от абстракции сервиса, не от конкретной логики). В NestJS это выражается в том, что контроллер инжектирует сервис, а не создаёт его.

---

## 4. Low Coupling — "минимум зависимостей, максимум независимости"

> Стремитесь к низкой степени связанности между классами, чтобы изменение одного класса не требовало изменения других.

Low Coupling — это не цель "вообще не зависеть", а цель **зависеть только от того, что стабильно**. Зависеть от интерфейса — low coupling. Зависеть от конкретного класса, который часто меняется — high coupling.

```txt
Виды связанности (от менее к более проблемной):
  Data coupling    — классы обмениваются только простыми данными (хорошо)
  Stamp coupling   — передают объект целиком, хотя нужно одно поле (нейтрально)
  Control coupling — один класс управляет поведением другого через флаг (плохо)
  Content coupling — один класс читает/пишет внутренние данные другого (очень плохо)
```

### Нарушение Low Coupling

```ts
// ❌ UserService напрямую импортирует конкретные классы —
// любое изменение EmailClient или AvatarService потенциально ломает UserService

import { SendgridEmailClient } from '../infrastructure/sendgrid-email-client';
import { CloudinaryAvatarService } from '../infrastructure/cloudinary-avatar-service';
import { PostgresUserRepository } from '../infrastructure/postgres-user-repository';

class UserService {
  private emailClient = new SendgridEmailClient(process.env.SENDGRID_KEY!);
  private avatarService = new CloudinaryAvatarService(process.env.CLOUDINARY_URL!);
  private userRepo = new PostgresUserRepository(process.env.DATABASE_URL!);

  // Тест этого класса требует реальных Sendgrid, Cloudinary, Postgres
}
```

```ts
// ✅ UserService зависит от интерфейсов — конкретные реализации снаружи

interface IEmailClient {
  sendWelcome(email: string): Promise<void>;
}

interface IAvatarService {
  upload(userId: string, file: Buffer): Promise<string>;
}

interface IUserRepository {
  save(user: User): Promise<User>;
}

class UserService {
  constructor(
    private readonly emailClient: IEmailClient,
    private readonly avatarService: IAvatarService,
    private readonly userRepo: IUserRepository,
  ) {}
}
```

### Low Coupling в React

```tsx
// ❌ Компонент напрямую вызывает fetch — coupling к конкретному API
function UserProfile({ userId }: { userId: string }) {
  const [user, setUser] = useState<User | null>(null);
  useEffect(() => {
    fetch(`/api/users/${userId}`).then(r => r.json()).then(setUser);
  }, [userId]);
  return <div>{user?.name}</div>;
}

// ✅ Компонент зависит от хука-абстракции — реализацию можно заменить
function UserProfile({ userId }: { userId: string }) {
  const { user } = useUser(userId); // хук скрывает источник данных
  return <div>{user?.name}</div>;
}
```

---

## 5. High Cohesion — "делай одно, но делай хорошо"

> Ответственности класса должны быть тесно связаны и фокусироваться на одной области. Низкая связность — классы-"помойки", которые сложно понять и поменять.

High Cohesion — функциональная сестра Low Coupling: Low Coupling говорит "не завись от лишнего снаружи", High Cohesion говорит "не делай лишнего внутри".

```txt
Признаки низкой связности (low cohesion):
  - Класс называется XxxManager, XxxHelper, XxxUtil — универсальные имена
    часто сигнализируют об отсутствии чёткой ответственности
  - Методы класса почти не используют поля друг друга — они просто
    живут в одном файле без внутренней связи
  - Изменение одной функции требует понимания всего класса
```

### Нарушение High Cohesion

```ts
// ❌ UserManager делает всё: авторизацию, аватары, платежи, статистику.
// Это класс с низкой связностью — его методы не связаны между собой.

class UserManager {
  async loginUser(email: string, password: string) { ... }
  async logoutUser(userId: string) { ... }
  async uploadAvatar(userId: string, file: Buffer) { ... }
  async processPayment(userId: string, amount: number) { ... }
  async getUserStats(userId: string) { ... }
  async sendNewsletterToAll() { ... }
  async generateUserReport(from: Date, to: Date) { ... }
}
```

```ts
// ✅ Каждый класс — высокосвязный: его методы используют одни и те же данные

class AuthService {
  async login(email: string, password: string): Promise<AuthToken> { ... }
  async logout(userId: string): Promise<void> { ... }
  async refreshToken(token: string): Promise<AuthToken> { ... }
}

class AvatarService {
  async upload(userId: string, file: Buffer): Promise<string> { ... }
  async delete(userId: string): Promise<void> { ... }
  async resize(userId: string, size: number): Promise<string> { ... }
}

class BillingService {
  async charge(userId: string, amount: number): Promise<Receipt> { ... }
  async refund(paymentId: string): Promise<void> { ... }
}
```

### High Cohesion vs SRP

На практике их часто путают. Разница:

```txt
SRP — про причину изменения (один актор):
  "Этот класс меняется только по требованию команды безопасности"

High Cohesion — про внутреннюю связность методов:
  "Все методы этого класса работают с одними и теми же данными
   и относятся к одной области знаний"

Класс может нарушать SRP (его могут требовать изменить два актора),
но иметь высокую связность. И наоборот. Но чаще нарушение одного
сопровождается нарушением другого.
```

---

## 6. Polymorphism — "тип объекта определяет поведение, а не ветвление if/switch"

> Когда поведение зависит от типа, используй полиморфизм вместо условных конструкций.

Это один из фундаментальных принципов ООП, но GRASP формулирует его как рекомендацию по распределению ответственности: **ответственность за вариативное поведение должна лежать на самом объекте**, а не на внешнем коде, который его проверяет.

### Нарушение — "type-checking antipattern"

```ts
// ❌ Бизнес-логика размазана по условным конструкциям.
// Добавить новый тип уведомления → найти и поменять ВСЕ такие switch-блоки.

function renderNotification(notification: Notification) {
  switch (notification.type) {
    case 'info':
      return `ℹ️ ${notification.message}`;
    case 'warning':
      return `⚠️ ${notification.message}`;
    case 'error':
      return `❌ ${notification.message} (code: ${notification.errorCode})`;
    case 'success':
      return `✅ ${notification.message}`;
  }
}
```

```ts
// ✅ Каждый тип сам знает, как себя рендерить

interface Notification {
  render(): string;
}

class InfoNotification implements Notification {
  constructor(private message: string) {}
  render() { return `ℹ️ ${this.message}`; }
}

class WarningNotification implements Notification {
  constructor(private message: string) {}
  render() { return `⚠️ ${this.message}`; }
}

class ErrorNotification implements Notification {
  constructor(private message: string, private errorCode: string) {}
  render() { return `❌ ${this.message} (code: ${this.errorCode})`; }
}

// Вызывающий код не знает о типах — просто вызывает render()
function displayNotification(notification: Notification) {
  console.log(notification.render());
}
```

### Реальный контекст (Node.js + NestJS)

```ts
// ❌ ExportService с if-блоками на тип формата
class ExportService {
  async export(data: ReportData, format: string): Promise<Buffer> {
    if (format === 'pdf') {
      return generatePdf(data);
    } else if (format === 'csv') {
      return generateCsv(data);
    } else if (format === 'xlsx') {
      return generateXlsx(data);
    }
    throw new Error(`Unknown format: ${format}`);
  }
}

// ✅ Полиморфизм: каждый форматтер — отдельный класс
interface ReportFormatter {
  format(data: ReportData): Promise<Buffer>;
  readonly contentType: string;
}

class PdfFormatter implements ReportFormatter {
  readonly contentType = 'application/pdf';
  async format(data: ReportData) { return generatePdf(data); }
}

class CsvFormatter implements ReportFormatter {
  readonly contentType = 'text/csv';
  async format(data: ReportData) { return generateCsv(data); }
}

class ExportService {
  constructor(private readonly formatters: Map<string, ReportFormatter>) {}

  async export(data: ReportData, format: string): Promise<Buffer> {
    const formatter = this.formatters.get(format);
    if (!formatter) throw new Error(`Unknown format: ${format}`);
    return formatter.format(data);
  }
}
```

### Связь с OCP

Polymorphism — это механизм реализации OCP на практике. "Открыт для расширения, закрыт для модификации" достигается именно через полиморфизм: новое поведение = новый класс, реализующий интерфейс.

---

## 7. Pure Fabrication — "иногда нужен класс без аналога в реальном мире"

> Если ни один доменный класс не является подходящим кандидатом для ответственности (и назначение нарушало бы High Cohesion или Low Coupling), создай искусственный класс-сервис.

Pure Fabrication — это "разрешение создать класс без доменного смысла". Большинство сервисов в слоистой архитектуре (Repository, Mapper, Formatter, Gateway) — это Pure Fabrications: в реальном мире не существует "UserRepository", это техническая абстракция.

### Пример: когда нужна Pure Fabrication

```ts
// Ситуация: нужно логировать каждое изменение заказа.
// Куда положить эту ответственность?

// ❌ В Order? — Order начнёт зависеть от инфраструктуры логирования → Low Coupling нарушен
class Order {
  async updateStatus(status: OrderStatus) {
    this.status = status;
    await logger.log(`Order ${this.id} status changed to ${status}`); // ← плохо
  }
}

// ❌ В OrderService? — у OrderService своя ответственность (бизнес-операции)
// Логирование — другая ответственность → SRP нарушен

// ✅ Pure Fabrication: OrderAuditLogger — искусственный класс без доменного аналога,
// чья единственная ответственность — аудит изменений

class OrderAuditLogger {
  constructor(private readonly logger: Logger) {}

  async logStatusChange(orderId: string, oldStatus: OrderStatus, newStatus: OrderStatus) {
    await this.logger.info('order.status_changed', {
      orderId,
      from: oldStatus,
      to: newStatus,
      timestamp: new Date().toISOString(),
    });
  }
}

// Order и OrderService остаются чистыми — Pure Fabrication берёт на себя
// инфраструктурную ответственность
```

### Реальный контекст

В слоистой архитектуре Pure Fabrications — это весь слой infrastructure: `UserRepository`, `EmailGateway`, `S3FileStorage`, `JwtTokenService`. Ни один из них не соответствует реальному объекту предметной области, но каждый берёт на себя конкретную инфраструктурную ответственность, освобождая доменные классы от неё.

### Когда Pure Fabrication становится антипаттерном

Если **все** классы в проекте — Pure Fabrications (сервисы, менеджеры, хелперы без доменных объектов) — это называется "Anemic Domain Model": у вас процедурный код, замаскированный под ООП. Доменные классы — `Order`, `User`, `Product` — должны содержать логику, специфичную для предметной области (расчёт скидок, валидация инвариантов). Pure Fabrication дополняет их, а не заменяет.

---

## GRASP и SOLID — таблица соответствий

```txt
GRASP принцип        Соответствующий SOLID принцип
───────────────────────────────────────────────────
Information Expert → SRP (данные и их обработка в одном месте)
Creator            → SRP (создание — ответственность агрегата)
Controller         → SRP (тонкий слой без бизнес-логики)
Low Coupling       → DIP (зависеть от абстракций, не конкретики)
High Cohesion      → SRP (фокус на одной области знаний)
Polymorphism       → OCP (расширение без модификации)
Pure Fabrication   → SRP + ISP (выделить инфраструктурную ответственность)
```

GRASP не противоречит SOLID — это две линзы на один и тот же вопрос: как структурировать код так, чтобы его можно было менять без страха.

## Типичные ошибки на интервью

- **"GRASP — это GoF паттерны"** — путать уровни. GoF — конкретные паттерны реализации (Singleton, Observer). GRASP — принципы распределения ответственности. Это разные инструменты разного уровня абстракции.

- **Не знать GRASP вообще** — SOLID знают многие, GRASP — единицы. Упоминание GRASP с правильным объяснением немедленно выделяет кандидата в разговоре об архитектуре.

- **Information Expert == "поместить всю логику в модель"** — это перекос в "толстую модель". Information Expert говорит: логику расчёта, напрямую зависящую от данных объекта, помещай в объект. Но бизнес-операции с побочными эффектами (сохранение, отправка) остаются в сервисах.

- **Creator как "всегда использовать new внутри класса"** — Creator описывает, КОМУ логично создавать объект (тому, кто его содержит или использует). Но это не запрет на фабрики — Factory нужна там, где создание сложное или вариативное.

- **Low Coupling как "никаких зависимостей"** — zero coupling невозможен и не нужен. Цель — зависеть только от стабильных абстракций, а не полностью избегать зависимостей.

- **Не различать High Cohesion и SRP** — оба принципа про "делай одно", но с разного угла: SRP про причину изменений (внешний актор), High Cohesion про внутреннюю связность методов (используют ли они общие данные и знания). Можно нарушить один, не нарушая другой.

- **Pure Fabrication как оправдание для "сервис на всё"** — Pure Fabrication легитимна, когда доменный объект не подходит. Но если всё приложение состоит из сервисов-менеджеров без доменных объектов с логикой — это Anemic Domain Model, и это проблема.
