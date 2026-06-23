# Паттерны Repository и Service

> **Область применения:** Это паттерны организации кода внутри одного приложения. Repository абстрагирует доступ к данным; Service Layer абстрагирует бизнес-операции. Они присутствуют практически в каждом Node.js/NestJS проекте с многоуровневой или чистой архитектурой.

## Зачем нужны эти паттерны — какую проблему они решают

Без явных паттернов бизнес-логика и доступ к данным оказываются в одном месте:

```ts
// ❌ Контроллер делает всё — никакого разделения
app.post('/orders', async (req, res) => {
  const user = await prisma.user.findUnique({ where: { id: req.user.id } });
  if (!user || user.creditLimit < req.body.total) {
    return res.status(400).json({ error: 'Insufficient credit' });
  }
  const order = await prisma.order.create({
    data: { userId: user.id, total: req.body.total, status: 'pending' },
  });
  await sendgrid.send({
    to: user.email,
    subject: 'Order confirmed',
    text: `Order ${order.id} placed for $${order.total}`,
  });
  res.status(201).json(order);
});
```

Три проблемы:
1. **Бизнес-правило нельзя протестировать** — «пользователь не может превысить кредитный лимит» можно проверить только через HTTP + реальную базу данных
2. **Разрозненный доступ к данным** — смена `prisma.order.create` на сырой SQL потребует изменений во всех контроллерах
3. **Перемешанные ответственности** — проверка лимита, создание заказа, отправка письма, HTTP-ответ — всё в одной функции

Паттерны Repository и Service дают каждой ответственности своё место.

## Паттерн Repository

**Репозиторий (Repository)** предоставляет коллекция-подобный интерфейс к доменной сущности. С точки зрения вызывающего кода это выглядит как типизированная in-memory коллекция — вы вызываете `findById`, `save`, `delete`. Репозиторий инкапсулирует все SQL-запросы, ORM-вызовы или обращения к API.

```txt
Controller / Use Case
        │
        │ вызывает (доменный язык: findById, save, findByUserId)
        ▼
  ┌─────────────┐
  │  Repository │  ← интерфейс, определён в доменном/сервисном слое
  └──────┬──────┘
         │ реализует
         ▼
  ┌────────────────────┐
  │  PrismaRepository  │  ← реализация, знает о Prisma
  └────────────────────┘
         │
         ▼
     PostgreSQL
```

### Определение интерфейса

Интерфейс живёт в бизнес-слое. Он говорит на языке домена — без типов Prisma, без SQL, без специфичных для ORM типов пагинации:

```ts
// repositories/order.repository.interface.ts
// Этот интерфейс живёт в доменном/сервисном слое
// Он говорит на языке домена, а не базы данных
export interface IOrderRepository {
  findById(id: string): Promise<Order | null>;
  findByUserId(userId: string): Promise<Order[]>;
  findPending(): Promise<Order[]>;
  save(order: Order): Promise<Order>;
  delete(id: string): Promise<void>;
}
```

### Конкретная реализация

Реализация на Prisma живёт в инфраструктурном/адаптерном слое. Она транслирует между доменной моделью и моделью ORM:

```ts
// repositories/prisma-order.repository.ts
import type { IOrderRepository } from './order.repository.interface';
import type { Order } from '../domain/order';
import { PrismaClient } from '@prisma/client';

export class PrismaOrderRepository implements IOrderRepository {
  constructor(private prisma: PrismaClient) {}

  async findById(id: string): Promise<Order | null> {
    const row = await this.prisma.order.findUnique({ where: { id } });
    return row ? this.mapToDomain(row) : null;
  }

  async findByUserId(userId: string): Promise<Order[]> {
    const rows = await this.prisma.order.findMany({ where: { userId } });
    return rows.map(this.mapToDomain);
  }

  async findPending(): Promise<Order[]> {
    const rows = await this.prisma.order.findMany({
      where: { status: 'pending' },
    });
    return rows.map(this.mapToDomain);
  }

  async save(order: Order): Promise<Order> {
    const row = await this.prisma.order.upsert({
      where: { id: order.id },
      create: this.mapToDb(order),
      update: this.mapToDb(order),
    });
    return this.mapToDomain(row);
  }

  async delete(id: string): Promise<void> {
    await this.prisma.order.delete({ where: { id } });
  }

  // Приватные маперы держат тип Prisma вне домена
  private mapToDomain(row: PrismaOrder): Order {
    return {
      id: row.id,
      userId: row.userId,
      total: row.total,
      status: row.status as Order['status'],
      createdAt: row.createdAt,
    };
  }

  private mapToDb(order: Order): Omit<PrismaOrder, 'id'> {
    return {
      userId: order.userId,
      total: order.total,
      status: order.status,
      createdAt: order.createdAt,
    };
  }
}

// Генерируемый Prisma тип — живёт только в этом файле
type PrismaOrder = {
  id: string;
  userId: string;
  total: number;
  status: string;
  createdAt: Date;
};
```

### Универсальный репозиторий — использовать с осторожностью

Универсальный (generic) репозиторий привлекателен для сокращения повторяющегося кода:

```ts
// Универсальная база — абстрагирует стандартные CRUD-операции
export interface IRepository<T, ID = string> {
  findById(id: ID): Promise<T | null>;
  save(entity: T): Promise<T>;
  delete(id: ID): Promise<void>;
}

// IOrderRepository расширяет универсальную и добавляет специфичные для заказов запросы
export interface IOrderRepository extends IRepository<Order> {
  findByUserId(userId: string): Promise<Order[]>;
  findPending(): Promise<Order[]>;
}
```

Риск: универсальный `IRepository<T>` нередко порождает метод `findAll()` со сложными параметрами фильтрации/сортировки, который превращается в построитель запросов — фактически повторную реализацию ORM поверх ORM. Держите универсальную базу тонкой (только `findById`, `save`, `delete`) и помещайте все доменно-специфичные запросы в конкретный интерфейс.

## Паттерн Service Layer

**Сервис (Service)** или **Сервисный слой (Service Layer)** — место, где живут бизнес-операции. Он оркестрирует репозитории и другие зависимости для выполнения use case — без знания об HTTP, WebSocket или CLI.

```txt
Controller (HTTP)  CLI Command  Background Job
       │               │              │
       └───────────────┴──────────────┘
                       │ вызывает (бизнес-язык: placeOrder, cancelOrder)
                       ▼
              ┌─────────────────┐
              │  OrdersService  │  ← содержит бизнес-логику и оркестрацию
              └────────┬────────┘
                       │ использует
              ┌────────┴────────────────┐
              │                         │
    ┌─────────────────┐      ┌─────────────────────┐
    │ IOrderRepository│      │ INotificationService │
    └─────────────────┘      └─────────────────────┘
```

```ts
// services/orders.service.ts
// Сервисный слой — оркестрирует бизнес-логику
// Знает о репозиториях и других сервисах; ничего не знает об HTTP
import type { IOrderRepository } from '../repositories/order.repository.interface';
import type { IUserRepository } from '../repositories/user.repository.interface';
import type { INotificationService } from '../services/notification.service.interface';
import type { Order } from '../domain/order';

export class InsufficientCreditError extends Error {
  constructor(available: number, required: number) {
    super(`Кредитный лимит ${available} недостаточен для суммы заказа ${required}`);
    this.name = 'InsufficientCreditError';
  }
}

export class OrderNotFoundError extends Error {
  constructor(id: string) {
    super(`Заказ ${id} не найден`);
    this.name = 'OrderNotFoundError';
  }
}

export class OrdersService {
  constructor(
    private orderRepository: IOrderRepository,
    private userRepository: IUserRepository,
    private notificationService: INotificationService,
  ) {}

  async placeOrder(userId: string, total: number): Promise<Order> {
    const user = await this.userRepository.findById(userId);
    if (!user) throw new Error(`Пользователь ${userId} не найден`);

    if (user.creditLimit < total) {
      throw new InsufficientCreditError(user.creditLimit, total);
    }

    const order = await this.orderRepository.save({
      id: crypto.randomUUID(),
      userId,
      total,
      status: 'pending',
      createdAt: new Date(),
    });

    await this.notificationService.sendOrderConfirmation(user.email, order.id);
    return order;
  }

  async cancelOrder(orderId: string, requestingUserId: string): Promise<Order> {
    const order = await this.orderRepository.findById(orderId);
    if (!order) throw new OrderNotFoundError(orderId);

    // Бизнес-правило: отменить заказ может только его владелец
    if (order.userId !== requestingUserId) {
      throw new Error('Нет прав для отмены этого заказа');
    }

    // Бизнес-правило: можно отменить только заказы в статусе pending
    if (order.status !== 'pending') {
      throw new Error(`Нельзя отменить заказ со статусом '${order.status}'`);
    }

    const cancelled = await this.orderRepository.save({ ...order, status: 'cancelled' });
    return cancelled;
  }

  async getOrdersByUser(userId: string): Promise<Order[]> {
    return this.orderRepository.findByUserId(userId);
  }
}
```

Контроллер теперь становится тонким — он обрабатывает только HTTP-уровень:

```ts
// controllers/orders.controller.ts
// Тонкий: парсит запрос, вызывает сервис, маппит ответ
export class OrdersController {
  constructor(private ordersService: OrdersService) {}

  async create(req: Request, res: Response): Promise<void> {
    try {
      const order = await this.ordersService.placeOrder(
        req.user!.id,
        Number(req.body.total),
      );
      res.status(201).json(order);
    } catch (err) {
      if (err instanceof InsufficientCreditError) {
        res.status(400).json({ error: err.message });
        return;
      }
      throw err;
    }
  }

  async cancel(req: Request, res: Response): Promise<void> {
    try {
      const order = await this.ordersService.cancelOrder(
        req.params.id,
        req.user!.id,
      );
      res.json(order);
    } catch (err) {
      if (err instanceof OrderNotFoundError) {
        res.status(404).json({ error: err.message });
        return;
      }
      throw err;
    }
  }
}
```

## Полная структура файлов

```txt
src/
├── domain/
│   └── order.ts                    ← чистые типы и бизнес-правила
│
├── repositories/
│   ├── order.repository.interface.ts     ← IOrderRepository (интерфейс)
│   ├── user.repository.interface.ts      ← IUserRepository (интерфейс)
│   ├── prisma-order.repository.ts        ← реализация
│   └── prisma-user.repository.ts         ← реализация
│
├── services/
│   ├── notification.service.interface.ts ← INotificationService (интерфейс)
│   ├── orders.service.ts                 ← бизнес-логика
│   └── sendgrid-notification.service.ts  ← реализация
│
├── controllers/
│   └── orders.controller.ts              ← HTTP-слой перевода
│
└── main.ts                               ← сборка (Composition Root)
```

## Тестирование каждого слоя независимо

Паттерн моментально окупается в тестах. Каждый слой тестируется без внешних зависимостей:

```ts
// services/orders.service.test.ts
// Без HTTP, без Prisma, без Sendgrid — чистый тест бизнес-логики
import { OrdersService, InsufficientCreditError } from './orders.service';

const mockOrderRepo = {
  findById: jest.fn(),
  findByUserId: jest.fn(),
  findPending: jest.fn(),
  save: jest.fn(),
  delete: jest.fn(),
};

const mockUserRepo = {
  findById: jest.fn(),
  save: jest.fn(),
  delete: jest.fn(),
};

const mockNotifier = {
  sendOrderConfirmation: jest.fn(),
};

const service = new OrdersService(mockOrderRepo, mockUserRepo, mockNotifier);

beforeEach(() => jest.clearAllMocks());

test('размещает заказ при достаточном кредитном лимите', async () => {
  mockUserRepo.findById.mockResolvedValue({ id: 'u1', email: 'user@test.com', creditLimit: 500 });
  mockOrderRepo.save.mockResolvedValue({ id: 'o1', userId: 'u1', total: 100, status: 'pending', createdAt: new Date() });
  mockNotifier.sendOrderConfirmation.mockResolvedValue(undefined);

  const order = await service.placeOrder('u1', 100);

  expect(order.status).toBe('pending');
  expect(mockNotifier.sendOrderConfirmation).toHaveBeenCalledWith('user@test.com', 'o1');
});

test('бросает InsufficientCreditError при превышении лимита', async () => {
  mockUserRepo.findById.mockResolvedValue({ id: 'u1', email: 'user@test.com', creditLimit: 50 });

  await expect(service.placeOrder('u1', 100)).rejects.toBeInstanceOf(InsufficientCreditError);
  expect(mockOrderRepo.save).not.toHaveBeenCalled();
});

test('бросает ошибку при отмене чужого заказа', async () => {
  mockOrderRepo.findById.mockResolvedValue({
    id: 'o1', userId: 'u2', total: 100, status: 'pending', createdAt: new Date(),
  });

  await expect(service.cancelOrder('o1', 'u1')).rejects.toThrow('Нет прав');
});
```

## NestJS — провайдеры и внедрение зависимостей

В NestJS сервисы и репозитории — это **провайдеры**, декорированные `@Injectable()`. IoC-контейнер (Inversion of Control — инверсия управления) NestJS берёт на себя создание и внедрение зависимостей:

```ts
// orders.module.ts
@Module({
  imports: [PrismaModule],
  controllers: [OrdersController],
  providers: [
    OrdersService,
    // Привязываем токен интерфейса к конкретной реализации
    { provide: 'IOrderRepository', useClass: PrismaOrderRepository },
    { provide: 'IUserRepository', useClass: PrismaUserRepository },
    { provide: 'INotificationService', useClass: SendgridNotificationService },
  ],
})
export class OrdersModule {}

// orders.service.ts — стиль NestJS
@Injectable()
export class OrdersService {
  constructor(
    @Inject('IOrderRepository') private orderRepository: IOrderRepository,
    @Inject('IUserRepository') private userRepository: IUserRepository,
    @Inject('INotificationService') private notificationService: INotificationService,
  ) {}
  // ... та же бизнес-логика
}
```

В небольших NestJS-проектах без строгого следования Clean Architecture часто инжектируют `PrismaOrderRepository` напрямую (без интерфейсной абстракции). Это проще и оправдано, когда нет нужды менять реализацию или тестировать без базы данных.

## Unit of Work — когда несколько репозиториев должны действовать вместе

Типичная проблема: размещение заказа требует записи в `orders` и уменьшения `users.creditLimit` атомарно. Если `orderRepository.save` прошёл успешно, а `userRepository.save` упал — база данных в несогласованном состоянии.

Паттерн **Unit of Work (UoW — единица работы)** оборачивает операции нескольких репозиториев в одну транзакцию:

```ts
// unit-of-work.interface.ts
export interface IUnitOfWork {
  orderRepository: IOrderRepository;
  userRepository: IUserRepository;
  // Выполняет всё внутри одной транзакции базы данных
  executeInTransaction<T>(work: (uow: IUnitOfWork) => Promise<T>): Promise<T>;
}

// prisma-unit-of-work.ts
export class PrismaUnitOfWork implements IUnitOfWork {
  constructor(private prisma: PrismaClient) {
    this.orderRepository = new PrismaOrderRepository(prisma);
    this.userRepository = new PrismaUserRepository(prisma);
  }

  orderRepository: IOrderRepository;
  userRepository: IUserRepository;

  async executeInTransaction<T>(work: (uow: IUnitOfWork) => Promise<T>): Promise<T> {
    return this.prisma.$transaction(async (tx) => {
      const txUow = new PrismaUnitOfWork(tx as PrismaClient);
      return work(txUow);
    });
  }
}

// Использование в сервисе
async placeOrder(userId: string, total: number): Promise<Order> {
  return this.uow.executeInTransaction(async (uow) => {
    const user = await uow.userRepository.findById(userId);
    if (!user || user.creditLimit < total) throw new InsufficientCreditError(...);

    const order = await uow.orderRepository.save({ ... });
    await uow.userRepository.save({ ...user, creditLimit: user.creditLimit - total });

    return order;
  });
}
```

Unit of Work полезен, когда нужна транзакционная согласованность между несколькими агрегатами. Для простых случаев, где операции одного репозитория самодостаточны, это избыточно.

## Типичные ошибки на интервью

- **«Репозиторий — это просто обёртка над Prisma»** — репозиторий, который делает `return prisma.order.findMany(filter)` и пропускает типы Prisma `WhereInput` наверх в сервисный слой, — не настоящий репозиторий, а тонкий прокси. Ценность репозитория в абстракции: сервис спрашивает «дай мне все ожидающие заказы» на доменном языке; репозиторий переводит это в то, как данные хранятся. Если типы Prisma появляются в сервисе — репозиторий не существует в каком-либо значимом смысле.

- **«Сервисы должны быть stateless, значит никаких полей»** — дело не в полях vs не-полях; дело в изменяемом состоянии экземпляра, которое меняется между вызовами. Внедрённые через конструктор зависимости (репозитории, другие сервисы) — это поля, и они в порядке, они консистентны между вызовами. Мутируемое состояние, отслеживающее частичные вычисления между вызовами (вроде `this.currentTransaction`), было бы проблемой в singleton-сервисе.

- **«Один сервис на сущность»** — это приводит к `UserService`, `OrderService`, `ProductService`, каждый из которых пытается владеть всеми операциями над своей сущностью. Тогда сквозные операции (разместить заказ, который затрагивает пользователей, заказы и инвентарь) не имеют очевидного места. Лучше: один сервис на бизнес-возможность или группу use cases. `OrdersService` обрабатывает размещение, отмену, возврат заказов — и может вызывать `userRepository` напрямую. Граница сущности не обязана совпадать с границей сервиса.

- **«В репозитории должен быть метод `findAll()`»** — `findAll()` на большой таблице — это источник проблем с производительностью. Если сервису нужно фильтровать данные, добавьте в репозиторий метод с доменным смыслом: `findPendingOlderThan(date: Date)` лучше, чем вернуть всё и фильтровать в памяти. Если универсальная фильтрация действительно нужна, передавайте типизированный объект-фильтр, а не позволяйте типу `WhereInput` Prisma просачиваться в интерфейс.

- **«Сервисный слой — это место для всего, что не является роутингом»** — так описывают то, чем сервисный слой часто становится, а не то, чем должен быть. Управление транзакциями, кэширование, логика повторных попыток, ограничение частоты запросов — всё это имеет тенденцию просачиваться в сервисы. Когда сервис занимается бизнес-логикой И инвалидацией кэша И управлением повторными попытками — следующий шаг: выделить это в отдельные concerns (декоратор кэширования, middleware повторных попыток). Задача сервиса — чистая бизнес-оркестрация.
