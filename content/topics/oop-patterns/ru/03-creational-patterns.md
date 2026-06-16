# Порождающие паттерны (Creational Patterns)

## Зачем выделять создание объектов в отдельный паттерн

Порождающие паттерны решают один вопрос: **как создавать объекты так, чтобы код, использующий объект, не зависел от деталей его создания**. Это прямое следствие DIP из SOLID: если `new ConcreteClass(arg1, arg2, arg3)` разбросан по всему коду — смена реализации требует правки во всех местах.

```txt
Без порождающего паттерна:
  const db = new PostgresDatabase(host, port, user, password, poolSize);
  // эта строка в 40 местах → смена на MongoDB требует 40 правок

С фабрикой / DI-контейнером:
  const db = DatabaseFactory.create(config);
  // смена реализации — в одном месте
```

Не каждый `new` требует паттерна. Ориентир: **паттерн нужен, когда создание сложно, вариативно, или должно быть изолировано от потребителя**.

---

## Singleton

> Гарантирует, что класс имеет только один экземпляр, и предоставляет глобальную точку доступа к нему.

### Базовая реализация на TypeScript

```ts
class DatabaseConnection {
  private static instance: DatabaseConnection | null = null;
  private connection: Connection;

  private constructor(config: DbConfig) {
    // private конструктор — нельзя вызвать new снаружи
    this.connection = createConnection(config);
  }

  static getInstance(config: DbConfig): DatabaseConnection {
    if (!DatabaseConnection.instance) {
      DatabaseConnection.instance = new DatabaseConnection(config);
    }
    return DatabaseConnection.instance;
  }

  query<T>(sql: string, params?: unknown[]): Promise<T[]> {
    return this.connection.query(sql, params);
  }
}

// Первый вызов — создаёт соединение
const db1 = DatabaseConnection.getInstance(config);
// Второй вызов — возвращает тот же экземпляр
const db2 = DatabaseConnection.getInstance(config);
console.log(db1 === db2); // true
```

### Почему Singleton — часто антипаттерн

Singleton решает реальную проблему (один экземпляр дорогого ресурса), но создаёт три системных проблемы:

```txt
1. Скрытая зависимость (нарушение DIP):
   Код, вызывающий DatabaseConnection.getInstance(), зависит
   от конкретного класса напрямую, без инжекции.
   → невозможно подменить в тестах без monkey-patching

2. Глобальное изменяемое состояние:
   Любая часть кода может изменить состояние Singleton —
   это ровно то, что делает код непредсказуемым и трудно
   тестируемым ("тест A изменил Singleton, тест B упал")

3. Нарушение SRP:
   Singleton управляет и своей бизнес-логикой, и собственным
   жизненным циклом (когда создаться, как хранить instance)
```

```ts
// ❌ Скрытая зависимость — как тестировать UserService
// без реального подключения к БД?

class UserService {
  async findUser(id: string) {
    const db = DatabaseConnection.getInstance(config); // скрытая зависимость
    return db.query(`SELECT * FROM users WHERE id = $1`, [id]);
  }
}

// В тесте нет способа подменить DatabaseConnection без мокирования модуля

// ✅ DI вместо Singleton — тот же эффект "одного экземпляра",
// но без глобального состояния и с тестируемостью

class UserService {
  constructor(private readonly db: IDatabase) {} // зависимость явна и заменяема

  async findUser(id: string) {
    return this.db.query(`SELECT * FROM users WHERE id = $1`, [id]);
  }
}

// В тесте:
const service = new UserService(new InMemoryDatabase());
// В production (через DI-контейнер или вручную):
const service = new UserService(DatabaseConnection.getInstance(config));
```

### Когда Singleton оправдан

```txt
Оправдан:
  - Logger (один процесс → один поток вывода)
  - Конфигурация, загружаемая один раз из env
  - Кеш в памяти (Map/LRU), когда нужен один разделяемый кеш
  - DI-контейнер сам по себе (IoC-контейнер — Singleton)

НЕ оправдан:
  - Соединение с БД (используй пул соединений через DI)
  - HTTP-клиент (инжектируй с нужными настройками через DI)
  - Любой класс, который хочется замокать в тестах
```

### Singleton в Node.js через модули (практичнее класса)

```ts
// config.ts — модуль кешируется Node.js require/import,
// поэтому объект создаётся ровно один раз без паттерна

const config = {
  db: {
    host: process.env.DB_HOST ?? 'localhost',
    port: Number(process.env.DB_PORT ?? 5432),
  },
  jwt: {
    secret: process.env.JWT_SECRET!,
    expiresIn: '7d',
  },
} as const;

export { config };

// Везде, где нужна конфигурация — импортируем тот же объект:
import { config } from './config';
// Это идиоматичный "Singleton" в Node.js — без класса, без getInstance
```

---

## Factory Method

> Определяет интерфейс для создания объекта, но позволяет подклассам (или конкретным функциям) решать, какой класс инстанцировать.

Factory Method — это не обязательно метод в подклассе (как в GoF). В TypeScript/JavaScript он чаще встречается как **функция или статический метод**, скрывающий детали создания.

### Пример: логгер с разными транспортами

```ts
// Без Factory Method — потребитель знает о деталях конфигурации каждого транспорта
const logger = new WinstonLogger({
  transports: [
    new winston.transports.Console({ format: winston.format.colorize() }),
    new winston.transports.File({ filename: 'error.log', level: 'error' }),
  ],
});
```

```ts
// ✅ Factory Method скрывает детали конфигурации

interface Logger {
  info(message: string, meta?: object): void;
  error(message: string, error?: Error): void;
}

function createLogger(env: 'development' | 'production' | 'test'): Logger {
  if (env === 'test') {
    return new SilentLogger(); // не пишет в stdout во время тестов
  }

  if (env === 'development') {
    return new ConsoleLogger({ colors: true, prettyPrint: true });
  }

  // production
  return new StructuredLogger({
    destination: process.env.LOG_DESTINATION ?? 'stdout',
    level: 'info',
  });
}

// Потребитель не знает, какой конкретно Logger создан
const logger = createLogger(process.env.NODE_ENV as 'development');
logger.info('Server started');
```

### Реальный контекст (NestJS)

```ts
// NestJS useFactory — это Factory Method в DI-контейнере:
// модуль описывает КАК создать провайдер, не создавая его сам

@Module({
  providers: [
    {
      provide: 'DATABASE',
      useFactory: async (config: ConfigService): Promise<DataSource> => {
        const dataSource = new DataSource({
          type: 'postgres',
          host: config.get('DB_HOST'),
          // ...
        });
        await dataSource.initialize();
        return dataSource;
      },
      inject: [ConfigService],
    },
  ],
})
export class DatabaseModule {}
```

### Реальный контекст (React)

```tsx
// Factory для создания компонентов-уведомлений по типу
type NotificationType = 'success' | 'error' | 'warning' | 'info';

function createNotification(type: NotificationType, message: string): React.ReactElement {
  const components: Record<NotificationType, React.FC<{ message: string }>> = {
    success: SuccessToast,
    error: ErrorToast,
    warning: WarningToast,
    info: InfoToast,
  };
  const Component = components[type];
  return <Component message={message} />;
}
```

---

## Abstract Factory

> Предоставляет интерфейс для создания **семейств** взаимосвязанных объектов без указания их конкретных классов.

Ключевое слово — **семейство**: когда нужно создавать несколько объектов, которые должны быть согласованы между собой (одна тема UI, одна платёжная система, один облачный провайдер).

### Пример: UI-компоненты для разных тем

```ts
// Интерфейсы для каждого типа компонента
interface Button {
  render(): string;
}

interface Input {
  render(): string;
}

// Абстрактная фабрика — контракт для семейства
interface UIComponentFactory {
  createButton(label: string): Button;
  createInput(placeholder: string): Input;
}

// Конкретная фабрика для Material UI
class MaterialUIFactory implements UIComponentFactory {
  createButton(label: string): Button {
    return { render: () => `<MuiButton variant="contained">${label}</MuiButton>` };
  }
  createInput(placeholder: string): Input {
    return { render: () => `<MuiTextField placeholder="${placeholder}" />` };
  }
}

// Конкретная фабрика для Ant Design
class AntDesignFactory implements UIComponentFactory {
  createButton(label: string): Button {
    return { render: () => `<AntButton type="primary">${label}</AntButton>` };
  }
  createInput(placeholder: string): Input {
    return { render: () => `<AntInput placeholder="${placeholder}" />` };
  }
}

// Потребитель работает только с абстрактной фабрикой
function renderLoginForm(factory: UIComponentFactory): string {
  const button = factory.createButton('Sign In');
  const input = factory.createInput('Enter email');
  return `<form>${input.render()}${button.render()}</form>`;
}

// Смена темы — смена фабрики в одном месте:
const form = renderLoginForm(new MaterialUIFactory());
```

### Реальный контекст: облачные провайдеры

```ts
// Abstract Factory для работы с облаком — один интерфейс, два провайдера

interface StorageService {
  upload(key: string, data: Buffer): Promise<string>;
  download(key: string): Promise<Buffer>;
}

interface QueueService {
  publish(topic: string, message: unknown): Promise<void>;
  subscribe(topic: string, handler: (msg: unknown) => void): void;
}

interface CloudFactory {
  createStorage(): StorageService;
  createQueue(): QueueService;
}

class AwsFactory implements CloudFactory {
  createStorage(): StorageService { return new S3StorageService(); }
  createQueue(): QueueService { return new SqsQueueService(); }
}

class GcpFactory implements CloudFactory {
  createStorage(): StorageService { return new GcsStorageService(); }
  createQueue(): QueueService { return new PubSubQueueService(); }
}

// Миграция с AWS на GCP — меняем одну строку:
const cloud: CloudFactory = process.env.CLOUD === 'gcp'
  ? new GcpFactory()
  : new AwsFactory();
```

### Factory Method vs Abstract Factory

```txt
Factory Method:
  - Создаёт ОДИН тип объекта
  - Часто — функция или статический метод
  - Скрывает детали конфигурации одного объекта

Abstract Factory:
  - Создаёт СЕМЕЙСТВО взаимосвязанных объектов
  - Группирует несколько Factory Methods
  - Гарантирует согласованность между объектами одного семейства
```

---

## Builder

> Разделяет конструирование сложного объекта на пошаговый процесс, позволяя создавать разные представления одного объекта.

Builder нужен, когда конструктор объекта принимает много параметров, часть из которых опциональна, и комбинации параметров вариативны.

### Проблема "telescoping constructor"

```ts
// ❌ Конструктор с 8 параметрами — вызов нечитаем,
// легко перепутать порядок аргументов

const query = new DatabaseQuery(
  'users',      // tableName
  ['id', 'email'], // columns
  { role: 'admin' }, // where
  'created_at', // orderBy
  'DESC',       // orderDirection
  10,           // limit
  0,            // offset
  true          // includeDeleted
);
// Что значит true? Зачем 'DESC' третьим аргументом?
```

```ts
// ✅ Builder — читаемый цепочечный API, каждый шаг именован

class DatabaseQueryBuilder {
  private tableName = '';
  private columns: string[] = ['*'];
  private conditions: Record<string, unknown> = {};
  private orderByColumn = 'id';
  private orderDirection: 'ASC' | 'DESC' = 'ASC';
  private limitValue = 100;
  private offsetValue = 0;
  private withDeleted = false;

  from(table: string): this {
    this.tableName = table;
    return this;
  }

  select(...columns: string[]): this {
    this.columns = columns;
    return this;
  }

  where(conditions: Record<string, unknown>): this {
    this.conditions = conditions;
    return this;
  }

  orderBy(column: string, direction: 'ASC' | 'DESC' = 'ASC'): this {
    this.orderByColumn = column;
    this.orderDirection = direction;
    return this;
  }

  limit(n: number): this {
    this.limitValue = n;
    return this;
  }

  offset(n: number): this {
    this.offsetValue = n;
    return this;
  }

  includeSoftDeleted(): this {
    this.withDeleted = true;
    return this;
  }

  build(): CompiledQuery {
    if (!this.tableName) throw new Error('Table name is required');
    return {
      sql: this.compile(),
      params: Object.values(this.conditions),
    };
  }

  private compile(): string {
    const cols = this.columns.join(', ');
    let sql = `SELECT ${cols} FROM ${this.tableName}`;
    if (!this.withDeleted) sql += ` WHERE deleted_at IS NULL`;
    const keys = Object.keys(this.conditions);
    if (keys.length) {
      const whereClauses = keys.map((k, i) => `${k} = $${i + 1}`).join(' AND ');
      sql += ` AND ${whereClauses}`;
    }
    sql += ` ORDER BY ${this.orderByColumn} ${this.orderDirection}`;
    sql += ` LIMIT ${this.limitValue} OFFSET ${this.offsetValue}`;
    return sql;
  }
}

// Читаемо, каждый шаг самодокументируется:
const query = new DatabaseQueryBuilder()
  .from('users')
  .select('id', 'email')
  .where({ role: 'admin' })
  .orderBy('created_at', 'DESC')
  .limit(10)
  .offset(0)
  .build();
```

### Builder в реальных библиотеках

```ts
// Knex.js — типичный Builder для SQL-запросов:
const users = await knex('users')
  .select('id', 'email')
  .where({ role: 'admin' })
  .orderBy('created_at', 'desc')
  .limit(10);

// Zod — Builder для схем валидации:
const UserSchema = z.object({
  email: z.string().email().toLowerCase(),
  age: z.number().int().min(18).max(120),
  role: z.enum(['admin', 'user']).default('user'),
});

// TypeORM QueryBuilder:
const users = await userRepository
  .createQueryBuilder('user')
  .where('user.role = :role', { role: 'admin' })
  .orderBy('user.createdAt', 'DESC')
  .take(10)
  .getMany();
```

### Director — необязательная часть Builder

```ts
// Director инкапсулирует типовые сценарии построения объекта.
// Полезен, когда один и тот же набор шагов повторяется в нескольких местах.

class QueryDirector {
  constructor(private readonly builder: DatabaseQueryBuilder) {}

  buildAdminListQuery(page: number, pageSize: number): CompiledQuery {
    return this.builder
      .from('users')
      .select('id', 'email', 'role', 'created_at')
      .where({ role: 'admin' })
      .orderBy('created_at', 'DESC')
      .limit(pageSize)
      .offset(page * pageSize)
      .build();
  }
}
```

---

## Prototype

> Создаёт новые объекты путём копирования (клонирования) существующего объекта-прототипа.

Prototype нужен, когда создание объекта дорого (требует сложной инициализации), а нужные объекты различаются лишь незначительно.

### Базовая реализация

```ts
interface Cloneable<T> {
  clone(): T;
}

class EmailTemplate implements Cloneable<EmailTemplate> {
  constructor(
    public subject: string,
    public body: string,
    public from: string,
    private readonly compiledRegex: RegExp, // дорого создавать каждый раз
  ) {}

  clone(): EmailTemplate {
    // shallow copy достаточно — compiledRegex неизменяем
    return new EmailTemplate(
      this.subject,
      this.body,
      this.from,
      this.compiledRegex,
    );
  }

  withSubject(subject: string): EmailTemplate {
    const copy = this.clone();
    copy.subject = subject;
    return copy;
  }

  withBody(body: string): EmailTemplate {
    const copy = this.clone();
    copy.body = body;
    return copy;
  }
}

// Базовый шаблон создан один раз (дорогая инициализация):
const baseTemplate = new EmailTemplate(
  'Notification',
  'Hello {{name}}',
  'noreply@example.com',
  /\{\{(\w+)\}\}/g,
);

// Вариации — дёшево, через клонирование:
const welcomeTemplate = baseTemplate.withSubject('Welcome!').withBody('Hi {{name}}, welcome!');
const resetTemplate = baseTemplate.withSubject('Password Reset').withBody('Reset link: {{link}}');
```

### Prototype в JavaScript/TypeScript — встроенные инструменты

```ts
// В JS/TS Prototype часто реализуется через Object.assign / spread,
// без явного метода clone():

// Shallow clone через spread:
const original = { user: { id: 1, name: 'Alice' }, role: 'admin' };
const copy = { ...original }; // shallow — original.user === copy.user

// Deep clone (Node.js 17+, современные браузеры):
const deepCopy = structuredClone(original); // полная копия, без общих ссылок

// Паттерн "immutable update" в Redux/Zustand — это Prototype:
const nextState = { ...state, count: state.count + 1 };

// Immer реализует Prototype под капотом (copy-on-write):
const nextState = produce(state, draft => {
  draft.user.name = 'Bob'; // immer клонирует только изменённые ветки
});
```

### Реальный контекст (тестирование)

```ts
// Prototype как "test fixture" — базовый объект + точечные изменения для каждого теста

const baseUser: User = {
  id: '1',
  email: 'test@example.com',
  role: 'user',
  isActive: true,
  createdAt: new Date('2024-01-01'),
};

// Каждый тест — клон с минимальными изменениями:
const adminUser = { ...baseUser, role: 'admin' as const };
const inactiveUser = { ...baseUser, isActive: false };
const newUser = { ...baseUser, createdAt: new Date() };
```

### Когда Prototype нужен, а когда нет

```txt
Нужен:
  - Создание объекта требует сложной инициализации (компиляция regex,
    парсинг схемы, установка соединения)
  - Нужно много похожих объектов с небольшими различиями
  - Иммутабельные обновления (Redux, Immer)

Не нужен (используй просто new):
  - Объекты лёгкие, инициализация дешёвая
  - Нет вариативности — все объекты одинаковые
```

---

## Сравнительная таблица порождающих паттернов

```txt
Паттерн          Решаемая проблема              Когда применять
────────────────────────────────────────────────────────────────────
Singleton        Один экземпляр на всё          Logger, конфиг, кеш
                 приложение                     (но предпочитай DI)

Factory Method   Создание одного объекта        Логгер по env,
                 с вариативной реализацией       компонент по типу

Abstract Factory Создание семейства             UI-тема, облачный
                 согласованных объектов          провайдер

Builder          Пошаговое построение           SQL-запрос, HTTP-запрос,
                 сложного объекта                конфигурация с >4 параметрами

Prototype        Клонирование объекта           Дорогая инициализация,
                 как основа для вариаций         тест-фикстуры, иммутабельность
```

## Типичные ошибки на интервью

- **"Singleton — хороший паттерн для shared-ресурсов"** — без упоминания проблем: скрытые зависимости, глобальное состояние, проблемы с тестируемостью. Правильный ответ включает "но предпочтительнее DI + один экземпляр в контейнере".

- **Путать Factory Method и Abstract Factory** — Factory Method создаёт один объект, Abstract Factory — семейство взаимосвязанных. Ключевое слово Abstract Factory — "согласованность семейства".

- **Builder всегда == "паттерн Builder из GoF"** — в TypeScript Builder чаще встречается как цепочечный API (Knex, Zod, TypeORM), а не классический GoF с отдельным Director. Оба варианта корректны, важно понимать цель.

- **"Prototype — это прототипная цепочка JavaScript"** — это разные вещи. Паттерн Prototype — про клонирование объектов. Прототипная цепочка JS — про делегирование поиска свойств по цепочке `__proto__`. На собеседовании разграничь эти понятия явно.

- **Не упомянуть DI как альтернативу Singleton** — Singleton решает "один экземпляр", но DI-контейнер решает ту же задачу без глобального состояния. Знание этой альтернативы сигнализирует о понимании практики, а не только теории.

- **Builder без валидации в `build()`** — полноценный Builder должен проверять обязательные параметры и инварианты в методе `build()`, а не при каждом setter'е. Это часто упускают при реализации на интервью.
