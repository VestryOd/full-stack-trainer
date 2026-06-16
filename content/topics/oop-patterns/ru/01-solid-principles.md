# Принципы SOLID

## Зачем SOLID — переформулировка через "стоимость изменений"

Принципы SOLID — не про "красивый код" и не про академическую чистоту. Они про одно: **сделать так, чтобы добавление новой функциональности не ломало уже работающую**.

```txt
Симптомы кода, нарушающего SOLID:
  - "Я поменял один класс, а тесты упали в пяти несвязанных местах"
  - "Чтобы добавить новый тип пользователя, нужно поменять 12 файлов"
  - "Я не могу написать unit-тест для этого класса без поднятия БД"
  - "Этот класс нельзя переиспользовать — он тащит за собой всё приложение"

Каждый из этих симптомов — нарушение одного или нескольких принципов SOLID.
```

Важное предупреждение с самого начала: SOLID — это **инструмент**, а не религия. В конце каждого принципа будет раздел "когда строгое соблюдение вредит" — потому что слепое следование принципам создаёт over-engineered код, который так же сложно поддерживать, как и код без принципов.

## S — Single Responsibility Principle (SRP)

> "Класс должен иметь только одну причину для изменения."

Более практичная формулировка: **класс должен отвечать только перед одним "актором"** (группой людей или процессом, который требует изменений). "Одна ответственность" — не про количество методов, а про то, **чьи требования могут заставить класс измениться**.

### Нарушение SRP

```ts
// ❌ UserService меняется по трём разным причинам:
//    1. Изменение бизнес-логики (хешируем по-другому)
//    2. Изменение формата письма (маркетинг поменял шаблон)
//    3. Изменение хранилища (мигрируем с SQL на NoSQL)
class UserService {
  async register(email: string, password: string) {
    // Логика хеширования — зона ответственности security-команды
    const hashedPassword = await bcrypt.hash(password, 10);

    // SQL-запрос — зона ответственности data-команды
    const user = await db.query(
      'INSERT INTO users (email, password) VALUES ($1, $2) RETURNING *',
      [email, hashedPassword]
    );

    // Шаблон письма — зона ответственности маркетинга
    await sendEmail({
      to: email,
      subject: 'Welcome to our platform!',
      body: `Hi! You've successfully registered. Click here to confirm...`,
    });

    return user.rows[0];
  }
}
```

```ts
// ✅ Каждый класс знает только свою зону:
// UserRepository — только хранилище
// EmailService — только отправка писем
// UserService — только оркестрация (координирует остальных)

class UserRepository {
  async create(email: string, hashedPassword: string) {
    const result = await db.query(
      'INSERT INTO users (email, password) VALUES ($1, $2) RETURNING *',
      [email, hashedPassword]
    );
    return result.rows[0];
  }
}

class EmailService {
  async sendWelcome(email: string) {
    await sendEmail({
      to: email,
      subject: 'Welcome to our platform!',
      body: `Hi! You've successfully registered. Click here to confirm...`,
    });
  }
}

class UserService {
  constructor(
    private readonly userRepository: UserRepository,
    private readonly emailService: EmailService,
  ) {}

  async register(email: string, password: string) {
    const hashedPassword = await bcrypt.hash(password, 10);
    const user = await this.userRepository.create(email, hashedPassword);
    await this.emailService.sendWelcome(email);
    return user;
  }
}
```

### Реальный контекст (NestJS)

В NestJS нарушение SRP — это сервис, который делает HTTP-запросы, пишет в БД, форматирует ответ и отправляет метрики. Каждый из этих слоёв должен быть отдельным инжектируемым провайдером. Тест `UserService` не должен требовать поднятого почтового сервера.

### Когда строгое SRP вредит

Если приложение маленькое и ответственности НИКОГДА не меняются независимо — искусственное дробление создаёт cognitive overhead без реальной пользы. "Регистрация пользователя" в MVP из 200 строк кода не требует четырёх классов.

---

## O — Open/Closed Principle (OCP)

> "Программные сущности должны быть открыты для расширения, но закрыты для модификации."

Практически: **добавление нового поведения не должно требовать изменения уже работающего кода**. Это достигается через абстракции — полиморфизм, стратегии, плагины.

### Нарушение OCP

```ts
// ❌ Каждый новый тип уведомления требует изменения NotificationService.
// Добавить SMS → открыть этот файл, добавить ветку в switch.
// Это нарушение OCP: класс не закрыт для модификации.
class NotificationService {
  send(type: 'email' | 'sms' | 'push', message: string, recipient: string) {
    switch (type) {
      case 'email':
        emailClient.send({ to: recipient, body: message });
        break;
      case 'sms':
        smsClient.send({ phone: recipient, text: message });
        break;
      case 'push':
        pushClient.notify({ userId: recipient, message });
        break;
      // Добавляем 'slack' → открываем этот файл → риск сломать email/sms/push
    }
  }
}
```

```ts
// ✅ Новый тип уведомления = новый класс, существующий код не трогаем

interface NotificationChannel {
  send(message: string, recipient: string): Promise<void>;
}

class EmailChannel implements NotificationChannel {
  async send(message: string, recipient: string) {
    await emailClient.send({ to: recipient, body: message });
  }
}

class SmsChannel implements NotificationChannel {
  async send(message: string, recipient: string) {
    await smsClient.send({ phone: recipient, text: message });
  }
}

// Добавляем Slack — новый класс, ни один существующий файл не меняем
class SlackChannel implements NotificationChannel {
  async send(message: string, recipient: string) {
    await slackClient.postMessage({ channel: recipient, text: message });
  }
}

class NotificationService {
  constructor(private readonly channels: NotificationChannel[]) {}

  async sendAll(message: string, recipient: string) {
    await Promise.all(this.channels.map(ch => ch.send(message, recipient)));
  }
}
```

### Реальный контекст (React)

В React OCP — это разница между компонентом с захардкоженным поведением и компонентом, принимающим `renderItem` / `onAction` / `children`. Компонент `<Table>`, внутрь которого нельзя передать кастомный рендер ячейки, нарушает OCP — для любого нового типа ячейки нужно модифицировать `Table`.

### Когда строгое OCP вредит

Преждевременная абстракция хуже, чем её отсутствие. Если у вас два типа каналов и третьего никогда не будет — interface + switch честнее, чем сложная система регистрации плагинов. **YAGNI до второй-третьей вариации, OCP после.**

---

## L — Liskov Substitution Principle (LSP)

> "Объекты дочернего класса должны быть заменимы объектами родительского класса без изменения корректности программы."

Практически: **код, работающий с базовым типом, должен работать с любым его подтипом без сюрпризов**. LSP нарушается, когда подкласс "ужесточает" предусловия, "ослабляет" постусловия, или бросает исключения, которых нет в базовом классе.

### Нарушение LSP

```ts
// ❌ Классический пример: Rectangle и Square
// Математически квадрат — частный случай прямоугольника.
// Но в программировании — нарушение LSP.

class Rectangle {
  constructor(protected width: number, protected height: number) {}

  setWidth(w: number)  { this.width = w; }
  setHeight(h: number) { this.height = h; }
  area() { return this.width * this.height; }
}

class Square extends Rectangle {
  setWidth(w: number)  { this.width = w; this.height = w; }  // сюрприз!
  setHeight(h: number) { this.width = h; this.height = h; }  // сюрприз!
}

function assertRectangleArea(rect: Rectangle) {
  rect.setWidth(5);
  rect.setHeight(3);
  // Ожидаем 15, но если rect — Square, получим 9
  console.assert(rect.area() === 15, `Expected 15, got ${rect.area()}`);
}

assertRectangleArea(new Rectangle(0, 0)); // ✅ 15
assertRectangleArea(new Square(0));        // ❌ 9 — LSP нарушен
```

```ts
// ✅ Не наследоваться там, где подтип не может полностью выполнить контракт базового

interface Shape {
  area(): number;
}

class Rectangle implements Shape {
  constructor(private width: number, private height: number) {}
  area() { return this.width * this.height; }
}

class Square implements Shape {
  constructor(private side: number) {}
  area() { return this.side * this.side; }
}

// Общий код работает с Shape — и для Rectangle, и для Square без сюрпризов
function printArea(shape: Shape) {
  console.log(`Area: ${shape.area()}`);
}
```

### Реальный контекст (Node.js)

```ts
// ❌ ReadOnlyRepository "наследует" Repository, но не может выполнить контракт

class Repository<T> {
  async findById(id: string): Promise<T> { ... }
  async save(entity: T): Promise<void> { ... }
  async delete(id: string): Promise<void> { ... }
}

class ReadOnlyRepository<T> extends Repository<T> {
  async save(entity: T): Promise<void> {
    throw new Error('Not supported'); // ← нарушение LSP: код с Repository не ожидает этого
  }
  async delete(id: string): Promise<void> {
    throw new Error('Not supported');
  }
}

// Функция, работающая с Repository, не ожидает Error от save/delete:
async function archiveUser(repo: Repository<User>, user: User) {
  user.archivedAt = new Date();
  await repo.save(user); // ← взрывается, если repo — ReadOnlyRepository
}
```

```ts
// ✅ Разделить интерфейсы — ISP + LSP работают вместе

interface ReadableRepository<T> {
  findById(id: string): Promise<T>;
  findAll(): Promise<T[]>;
}

interface WritableRepository<T> extends ReadableRepository<T> {
  save(entity: T): Promise<void>;
  delete(id: string): Promise<void>;
}

class ReadOnlyUserRepository implements ReadableRepository<User> {
  async findById(id: string) { ... }
  async findAll() { ... }
}

// archiveUser теперь явно требует WritableRepository — типобезопасно
async function archiveUser(repo: WritableRepository<User>, user: User) {
  user.archivedAt = new Date();
  await repo.save(user);
}
```

### Когда строгое LSP вредит

LSP чаще нарушается случайно, чем намеренно, поэтому "вреда от строгого соблюдения" здесь меньше. Единственный контр-аргумент: иногда "исключение в unimplemented методе" — честное решение для переходного периода при рефакторинге. Но это технический долг, а не архитектурное решение.

---

## I — Interface Segregation Principle (ISP)

> "Клиенты не должны зависеть от методов, которые они не используют."

Практически: **"жирные" интерфейсы нужно разбивать на меньшие, специализированные**. Класс, реализующий интерфейс из 15 методов и бросающий `NotImplemented` в 10 из них, — сигнал нарушения ISP.

### Нарушение ISP

```ts
// ❌ Один "жирный" интерфейс для всех типов хранилища

interface Storage {
  upload(key: string, data: Buffer): Promise<string>;
  download(key: string): Promise<Buffer>;
  delete(key: string): Promise<void>;
  generateSignedUrl(key: string, expiresIn: number): Promise<string>;
  listObjects(prefix: string): Promise<string[]>;
  copyObject(source: string, dest: string): Promise<void>;
}

// LocalStorage не умеет генерировать signed URLs (это S3-концепт),
// но вынуждена реализовывать метод:
class LocalStorage implements Storage {
  async upload(key: string, data: Buffer) { ... }
  async download(key: string) { ... }
  async delete(key: string) { ... }
  async generateSignedUrl(): Promise<string> {
    throw new Error('Local storage does not support signed URLs'); // ❌ ISP
  }
  async listObjects(prefix: string) { ... }
  async copyObject(source: string, dest: string) { ... }
}
```

```ts
// ✅ Разделить на целевые интерфейсы — каждый класс реализует только то, что умеет

interface ObjectStore {
  upload(key: string, data: Buffer): Promise<string>;
  download(key: string): Promise<Buffer>;
  delete(key: string): Promise<void>;
}

interface SignedUrlProvider {
  generateSignedUrl(key: string, expiresIn: number): Promise<string>;
}

interface ObjectLister {
  listObjects(prefix: string): Promise<string[]>;
}

class LocalStorage implements ObjectStore {
  async upload(key: string, data: Buffer) { ... }
  async download(key: string) { ... }
  async delete(key: string) { ... }
  // generateSignedUrl нет — и это нормально, LocalStorage его не поддерживает
}

class S3Storage implements ObjectStore, SignedUrlProvider, ObjectLister {
  async upload(key: string, data: Buffer) { ... }
  async download(key: string) { ... }
  async delete(key: string) { ... }
  async generateSignedUrl(key: string, expiresIn: number) { ... }
  async listObjects(prefix: string) { ... }
}

// Функция, которой нужен только upload/download, не зависит от SignedUrl
function processUserAvatar(store: ObjectStore, userId: string, data: Buffer) {
  return store.upload(`avatars/${userId}`, data);
}
```

### Реальный контекст (React)

```tsx
// ❌ Компонент принимает "жирный" объект — зависит от полей, которые не использует

interface User {
  id: string;
  email: string;
  password: string;  // зачем это UI-компоненту?
  createdAt: Date;
  role: 'admin' | 'user';
  subscriptionTier: string;
  lastLoginIp: string;
}

function UserAvatar({ user }: { user: User }) {
  // Использует только user.id и user.email, но зависит от всего User
  return <img src={`/avatars/${user.id}`} alt={user.email} />;
}

// ✅ Компонент зависит только от нужных полей
interface UserAvatarProps {
  userId: string;
  email: string;
}

function UserAvatar({ userId, email }: UserAvatarProps) {
  return <img src={`/avatars/${userId}`} alt={email} />;
}
```

### Когда строгое ISP вредит

Слишком мелкие интерфейсы создают excessive composition. Если у вас 8 интерфейсов по одному методу — это тоже проблема: код становится трудно читаем, и TypeScript intersection types (`A & B & C & D`) теряют смысл. Ориентир: **интерфейс должен соответствовать одной "роли"** (Readable, Writable, Searchable), а не одному методу.

---

## D — Dependency Inversion Principle (DIP)

> "Модули высокого уровня не должны зависеть от модулей низкого уровня. Оба должны зависеть от абстракций."
> "Абстракции не должны зависеть от деталей. Детали должны зависеть от абстракций."

Практически: **бизнес-логика не должна знать, какая БД, какой HTTP-клиент, какой email-провайдер используется**. Она работает с интерфейсами. Конкретные реализации подставляются снаружи (Dependency Injection).

```txt
❌ Зависимость "вниз" (нарушение DIP):
  UserService → PostgresRepository (конкретный класс)
  
  Проблема: чтобы заменить Postgres на MongoDB или написать тест
  без реальной БД — нужно менять UserService.

✅ Инверсия зависимостей (DIP):
  UserService → IUserRepository (интерфейс/абстракция)
       ↑                ↑
  PostgresUserRepository   InMemoryUserRepository (для тестов)
  
  UserService не знает, что стоит за IUserRepository.
  Замена реализации — без изменения бизнес-логики.
```

### Нарушение DIP

```ts
// ❌ OrderService жёстко привязан к конкретным реализациям.
// Нельзя протестировать без реального Postgres и реального Stripe.

import { PostgresOrderRepository } from './postgres-order-repository';
import { StripePaymentService } from './stripe-payment-service';

class OrderService {
  private orderRepo = new PostgresOrderRepository();  // конкретный класс
  private paymentService = new StripePaymentService(); // конкретный класс

  async placeOrder(userId: string, items: CartItem[]) {
    const total = calculateTotal(items);
    await this.paymentService.charge(userId, total);   // зависим от Stripe
    return this.orderRepo.save({ userId, items, total }); // зависим от Postgres
  }
}
```

```ts
// ✅ DIP + DI: зависимости инжектируются через конструктор, зависимость — от интерфейса

interface OrderRepository {
  save(order: Order): Promise<Order>;
  findByUserId(userId: string): Promise<Order[]>;
}

interface PaymentGateway {
  charge(userId: string, amount: number): Promise<PaymentResult>;
}

class OrderService {
  constructor(
    private readonly orderRepo: OrderRepository,
    private readonly paymentGateway: PaymentGateway,
  ) {}

  async placeOrder(userId: string, items: CartItem[]) {
    const total = calculateTotal(items);
    const payment = await this.paymentGateway.charge(userId, total);
    return this.orderRepo.save({ userId, items, total, paymentId: payment.id });
  }
}

// Для production:
const service = new OrderService(
  new PostgresOrderRepository(db),
  new StripePaymentGateway(stripeClient),
);

// Для тестов — никаких реальных зависимостей:
const service = new OrderService(
  new InMemoryOrderRepository(),
  new MockPaymentGateway(),
);
```

### Реальный контекст (NestJS)

NestJS строит всю систему вокруг DIP: `@Injectable()` провайдеры регистрируются в модуле, а классы получают зависимости через конструктор. Токен `IUserRepository` в `provide` и `useClass: PostgresUserRepository` — это DIP в действии. Именно поэтому тестирование NestJS-сервисов через `Test.createTestingModule` настолько удобно: конкретные реализации заменяются моками без изменения тестируемого кода.

### Когда строгое DIP вредит

Для небольших утилит (helper-функции, formatters, validators) — внедрение абстракций ради абстракций создаёт bloat. Если функция `formatPrice(amount: number): string` никогда не поменяет реализацию и не требует мокирования в тестах — ей не нужен интерфейс. DIP критичен для **зависимостей с побочными эффектами** (IO, сеть, время) и для **вариативного поведения** (несколько email-провайдеров).

---

## SOLID как система: принципы усиливают друг друга

```txt
SRP → один "актор" изменяет класс → легче соблюсти OCP
OCP → расширение через новые классы → требует ISP (не "жирные" интерфейсы)
ISP → маленькие интерфейсы → упрощает DIP (инжектировать только нужное)
DIP → зависимость от абстракций → упрощает тестирование (подмена реализаций)
LSP → правильная иерархия → полиморфизм работает предсказуемо (нет сюрпризов)
```

Нарушение одного принципа часто нарушает и другие: класс с тремя ответственностями (SRP) обычно также жёстко привязан к конкретным зависимостям (DIP), и добавление нового поведения требует его модификации (OCP).

## Типичные ошибки на интервью

- **"SOLID — это пять правил, которые всегда нужно соблюдать"** — без понимания trade-offs. Правильный ответ: это принципы, которые снижают стоимость изменений, а не самоцель. Преждевременная абстракция по SOLID — такая же проблема, как её отсутствие.

- **SRP как "один метод = один класс"** — SRP про причину изменения ("одного актора"), а не про количество методов. Класс с 10 методами, обслуживающий одну бизнес-область, соблюдает SRP.

- **OCP через наследование вместо композиции** — часто кандидаты объясняют OCP через `extends`, хотя современный идиоматичный подход — интерфейсы + стратегии. Наследование — один из способов, не единственный.

- **LSP только как "прямоугольник и квадрат"** — это каноничный пример, но на практике LSP чаще нарушается через `throw new Error('Not implemented')` в методах интерфейса. Умение распознать эту форму нарушения важнее знания канонического примера.

- **ISP и DIP путают** — ISP про интерфейсы со стороны клиента ("не давать лишних методов"), DIP про направление зависимости ("зависеть от абстракции, не от конкретики"). Это разные оси.

- **DIP = Dependency Injection** — DIP — принцип (направление зависимости), DI — паттерн (механизм передачи зависимости). DI реализует DIP, но DIP шире: можно инвертировать зависимости через Service Locator или через фабрики — это тоже DIP, хотя и не DI в классическом смысле.
