# Clean Architecture (Чистая архитектура)

> **Область применения:** Clean Architecture — это организация кода внутри одного сервиса так, чтобы основная бизнес-логика была независима от фреймворков, баз данных и механизмов доставки. Как несколько сервисов координируются между собой — это вопрос System Design.

## Проблема, которую решает Clean Architecture — точнее, чем многоуровневая архитектура

Многоуровневая архитектура (статья 01) говорит, *какие слои иметь*. Clean Architecture говорит, *в каком направлении должны указывать зависимости* между этими слоями — и делает это правило явным и обязательным.

Конкретная решаемая проблема: **бизнес-логика зависит от вещей, которые меняются по внешним причинам**.

```ts
// ❌ Этот сервис "знает", что работает на Express и использует Prisma
// При переходе на Fastify или Prisma → сырой SQL придётся трогать бизнес-логику

import { Request, Response } from 'express';     // импорт фреймворка
import { PrismaClient } from '@prisma/client';   // импорт базы данных

const prisma = new PrismaClient();

export async function createOrder(req: Request, res: Response) {
  const user = await prisma.user.findUnique({ where: { id: req.user.id } });
  if (!user || user.creditLimit < req.body.total) {
    return res.status(400).json({ error: 'Insufficient credit' });
  }
  const order = await prisma.order.create({ data: { userId: user.id, total: req.body.total } });
  res.status(201).json(order);
}
```

Бизнес-правило ("пользователь не может превысить кредитный лимит") зарыто внутри функции, импортирующей `express` и `prisma`. Нельзя протестировать это правило без поднятия HTTP и базы данных. Нельзя переиспользовать из CLI-инструмента или cron-задачи. При каждом breaking change в Prisma приходится искать бизнес-логику в файлах, связанных с фреймворком.

Ответ Clean Architecture: **основная бизнес-логика не должна импортировать из, или знать о, чём-либо из внешнего слоя**.

## Четыре кольца — и Правило зависимостей

Роберт Мартин (известный как "Дядя Боб") описал Clean Architecture как концентрические кольца. Определяющее правило — **Dependency Rule** (Правило зависимостей):

> **Зависимости в исходном коде должны указывать только вовнутрь. Ничто во внутреннем кольце не может знать о чём-либо во внешнем кольце.**

```txt
┌─────────────────────────────────────────────────────────┐
│             4. Фреймворки и драйверы                    │
│    (Express, NestJS, Prisma, HTTP, CLI,                 │
│     базы данных, внешние сервисы, UI)                   │
│  ┌──────────────────────────────────────────────────┐   │
│  │          3. Интерфейсные адаптеры                 │   │
│  │  (Контроллеры, Презентеры, Шлюзы,               │   │
│  │   реализации репозиториев, маперы DTO)           │   │
│  │  ┌───────────────────────────────────────────┐   │   │
│  │  │            2. Варианты использования       │   │   │
│  │  │   (Прикладные бизнес-правила,             │   │   │
│  │  │    логика оркестрации)                    │   │   │
│  │  │  ┌──────────────────────────────────────┐  │   │   │
│  │  │  │           1. Сущности                 │  │   │   │
│  │  │  │  (Корпоративные бизнес-правила,       │  │   │   │
│  │  │  │   доменные объекты, базовые типы)     │  │   │   │
│  │  │  └──────────────────────────────────────┘  │   │   │
│  │  └───────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘

Зависимости: всегда указывают ──► вовнутрь
             НИКОГДА наружу
```

### Кольцо 1: Сущности (Entities)

Самое внутреннее кольцо. Чистые бизнес-объекты и правила, существующие вне любого прикладного контекста. Без импортов фреймворков. Без импортов БД. Без HTTP-концепций.

```ts
// entities/order.ts — чистый TypeScript, ноль зависимостей
export interface Order {
  id: string;
  userId: string;
  total: number;
  status: 'pending' | 'confirmed' | 'cancelled';
  createdAt: Date;
}

// Бизнес-правило как чистая функция — тестируется без какой-либо настройки
export function canPlaceOrder(userCreditLimit: number, orderTotal: number): boolean {
  return userCreditLimit >= orderTotal;
}

export class InsufficientCreditError extends Error {
  constructor(available: number, required: number) {
    super(`Кредитный лимит ${available} недостаточен для суммы заказа ${required}`);
    this.name = 'InsufficientCreditError';
  }
}
```

### Кольцо 2: Варианты использования (Use Cases)

Прикладные бизнес-правила. Use Case (также называемый "Interactor") оркестрирует Entities для выполнения одной конкретной бизнес-операции. Знает о Entities, но НЕ знает об HTTP, базах данных или фреймворках.

Ключевой момент: Use Cases определяют **интерфейсы** для данных, которые им нужны из внешнего мира — репозитории, внешние сервисы, уведомители. Эти интерфейсы живут *внутри* кольца use case (внутренний слой), но их *реализации* — во внешних кольцах.

```ts
// use-cases/place-order.use-case.ts
// В этом файле НОЛЬ импортов из Express, Prisma или любого фреймворка
import type { Order } from '../entities/order';
import { canPlaceOrder, InsufficientCreditError } from '../entities/order';

// Use Case определяет что ему НУЖНО — но не КАК это получить
// Эти интерфейсы остаются в внутреннем слое; реализации — в кольцах 3/4
export interface IUserRepository {
  findById(id: string): Promise<{ id: string; email: string; creditLimit: number } | null>;
}

export interface IOrderRepository {
  create(input: { userId: string; total: number }): Promise<Order>;
}

export interface INotificationService {
  sendOrderConfirmation(email: string, orderId: string): Promise<void>;
}

export interface PlaceOrderInput {
  userId: string;
  total: number;
}

// Класс Use Case — чистая оркестрация, без фреймворка, без БД
export class PlaceOrderUseCase {
  constructor(
    private userRepo: IUserRepository,
    private orderRepo: IOrderRepository,
    private notifier: INotificationService,
  ) {}

  async execute(input: PlaceOrderInput): Promise<Order> {
    const user = await this.userRepo.findById(input.userId);
    if (!user) throw new Error(`Пользователь ${input.userId} не найден`);

    // Использует бизнес-правило из уровня entity
    if (!canPlaceOrder(user.creditLimit, input.total)) {
      throw new InsufficientCreditError(user.creditLimit, input.total);
    }

    const order = await this.orderRepo.create({ userId: user.id, total: input.total });
    await this.notifier.sendOrderConfirmation(user.email, order.id);

    return order;
  }
}
```

Обратите внимание на отсутствующее: нет `import from 'express'`, нет `import from '@prisma/client'`. Use Case говорит с *интерфейсами*, которые сам определяет. Ему не важно — и он не знает — приходят ли данные из PostgreSQL, SQLite или in-memory-коллекции.

### Кольцо 3: Интерфейсные адаптеры (Interface Adapters)

Это кольцо содержит код, переводящий между use cases и внешним миром. Контроллеры, презентеры, реализации репозиториев, маперы DTO (Data Transfer Object — простой объект для передачи данных между слоями).

```ts
// adapters/repositories/prisma-user.repository.ts
// Реализует интерфейс, определённый в кольце 2 — используя Prisma (кольцо 4)
import type { IUserRepository } from '../../use-cases/place-order.use-case';
import { PrismaClient } from '@prisma/client';

export class PrismaUserRepository implements IUserRepository {
  constructor(private prisma: PrismaClient) {}

  async findById(id: string) {
    const user = await this.prisma.user.findUnique({ where: { id } });
    if (!user) return null;
    return { id: user.id, email: user.email, creditLimit: user.creditLimit };
  }
}
```

```ts
// adapters/repositories/prisma-order.repository.ts
import type { IOrderRepository } from '../../use-cases/place-order.use-case';
import type { Order } from '../../entities/order';
import { PrismaClient } from '@prisma/client';

export class PrismaOrderRepository implements IOrderRepository {
  constructor(private prisma: PrismaClient) {}

  async create(input: { userId: string; total: number }): Promise<Order> {
    const order = await this.prisma.order.create({
      data: { userId: input.userId, total: input.total, status: 'pending' },
    });
    return {
      id: order.id,
      userId: order.userId,
      total: order.total,
      status: order.status as Order['status'],
      createdAt: order.createdAt,
    };
  }
}
```

```ts
// adapters/controllers/orders.controller.ts
// Переводит HTTP → входные данные use case, выходные данные use case → HTTP-ответ
import type { Request, Response } from 'express';
import type { PlaceOrderUseCase } from '../../use-cases/place-order.use-case';
import { InsufficientCreditError } from '../../entities/order';

export class OrdersController {
  constructor(private placeOrderUseCase: PlaceOrderUseCase) {}

  async create(req: Request, res: Response): Promise<void> {
    try {
      const order = await this.placeOrderUseCase.execute({
        userId: req.user!.id,
        total: Number(req.body.total),
      });
      res.status(201).json(order);
    } catch (err) {
      if (err instanceof InsufficientCreditError) {
        res.status(400).json({ error: err.message });
        return;
      }
      throw err;
    }
  }
}
```

### Кольцо 4: Фреймворки и драйверы

Самое внешнее кольцо. Express, NestJS, Prisma, Redis-клиенты, внешние API, провайдеры email. Это кольцо меняется чаще всего (обновления фреймворков, миграции БД, изменения сторонних API). Правило зависимостей гарантирует, что эти изменения никогда не достигают внутренних колец.

```ts
// main.ts — сборка всего вместе (Composition Root)
import express from 'express';
import { PrismaClient } from '@prisma/client';
import { PrismaUserRepository } from './adapters/repositories/prisma-user.repository';
import { PrismaOrderRepository } from './adapters/repositories/prisma-order.repository';
import { SendgridNotificationService } from './adapters/services/sendgrid-notification.service';
import { PlaceOrderUseCase } from './use-cases/place-order.use-case';
import { OrdersController } from './adapters/controllers/orders.controller';

const prisma = new PrismaClient();
const app = express();
app.use(express.json());

// Dependency injection — вручную собирается здесь в Composition Root
const userRepo = new PrismaUserRepository(prisma);
const orderRepo = new PrismaOrderRepository(prisma);
const notifier = new SendgridNotificationService(process.env.SENDGRID_KEY!);
const placeOrderUseCase = new PlaceOrderUseCase(userRepo, orderRepo, notifier);
const ordersController = new OrdersController(placeOrderUseCase);

app.post('/orders', (req, res) => ordersController.create(req, res));

app.listen(3000);
```

## Результирующая файловая структура

```txt
src/
├── entities/                      ← кольцо 1: чистые бизнес-объекты
│   └── order.ts
├── use-cases/                     ← кольцо 2: use cases + их интерфейсы
│   └── place-order.use-case.ts
├── adapters/                      ← кольцо 3: переводчики
│   ├── controllers/
│   │   └── orders.controller.ts
│   ├── repositories/
│   │   ├── prisma-user.repository.ts
│   │   └── prisma-order.repository.ts
│   └── services/
│       └── sendgrid-notification.service.ts
└── main.ts                        ← кольцо 4: проводка фреймворка
```

## Тестирование без базы данных и HTTP-сервера

Правило зависимостей окупается сразу в тестах:

```ts
// use-cases/place-order.use-case.test.ts
// Нет Prisma. Нет Express. Нет сети. Выполняется за миллисекунды.
import { PlaceOrderUseCase, InsufficientCreditError } from './place-order.use-case';

const mockUserRepo = { findById: jest.fn() };
const mockOrderRepo = { create: jest.fn() };
const mockNotifier = { sendOrderConfirmation: jest.fn() };

const useCase = new PlaceOrderUseCase(mockUserRepo, mockOrderRepo, mockNotifier);

beforeEach(() => jest.clearAllMocks());

test('размещает заказ при достаточном кредите', async () => {
  mockUserRepo.findById.mockResolvedValue({ id: '1', email: 'a@b.com', creditLimit: 500 });
  mockOrderRepo.create.mockResolvedValue({ id: 'o1', userId: '1', total: 100, status: 'pending', createdAt: new Date() });
  mockNotifier.sendOrderConfirmation.mockResolvedValue(undefined);

  const order = await useCase.execute({ userId: '1', total: 100 });

  expect(order.status).toBe('pending');
  expect(mockNotifier.sendOrderConfirmation).toHaveBeenCalledWith('a@b.com', 'o1');
});

test('бросает InsufficientCreditError при превышении кредита', async () => {
  mockUserRepo.findById.mockResolvedValue({ id: '1', email: 'a@b.com', creditLimit: 50 });

  await expect(useCase.execute({ userId: '1', total: 100 }))
    .rejects.toBeInstanceOf(InsufficientCreditError);

  expect(mockOrderRepo.create).not.toHaveBeenCalled();
  expect(mockNotifier.sendOrderConfirmation).not.toHaveBeenCalled();
});
```

## Clean Architecture vs Многоуровневая архитектура — ключевое различие

Обе организуют код в слои. Критическое различие — что добавляет Правило зависимостей:

```txt
Многоуровневая архитектура:
  Presentation → Service → Repository
  Направление зависимостей: обычно сверху вниз
  Но: сервис МОЖЕТ импортировать из Express, если разработчик невнимателен
      ("только на этот раз")

Clean Architecture:
  Внешние кольца (фреймворки) → Внутренние кольца (use cases, entities)
  Направление зависимостей: всегда вовнутрь, обеспечивается абстракцией интерфейса
  Use Case определяет интерфейс IRepository — импортирует интерфейс, не класс
  Реализация репозитория (которая импортирует Prisma) живёт во внешнем кольце
  Use Case не может случайно импортировать Prisma — Prisma не в его кольце
```

Правило зависимостей обеспечивается через **Dependency Inversion** (Инверсию зависимостей): внутренний слой определяет интерфейс ("порт"), внешний слой предоставляет реализацию ("адаптер"). Это та же идея, что и в Hexagonal Architecture (статья 04) — разная лексика, один принцип.

## Когда Clean Architecture оправдывает накладные расходы

У Clean Architecture есть реальные издержки: больше файлов, больше интерфейсов, больше индирекции. Избыточен для:
- Простого CRUD API с минимальной бизнес-логикой
- Прототипных или MVP-проектов, где требования меняются ежедневно
- Команды из одного-двух человек, где лишняя структура добавляет трение без отдачи

Оправдывает себя, когда:
- Бизнес-логика сложна и должна тестироваться изолированно
- Команде нужно менять инфраструктуру (например, мигрировать с PostgreSQL на MongoDB или с REST на GraphQL) без касания бизнес-логики
- Существует несколько механизмов доставки (HTTP API + CLI + фоновые задачи, использующие одни те же use cases)
- Ожидается, что кодовая база будет жить годами и разрабатываться несколькими командами

## Типичные ошибки на интервью

- **"Clean Architecture и многоуровневая архитектура — одно и то же"** — многоуровневая архитектура даёт слои; Clean Architecture даёт Правило зависимостей: внутренние слои никогда не должны импортировать из внешних. Можно иметь трёхслойное приложение, где сервис импортирует из Express (нарушение Правила зависимостей) — это многоуровневая архитектура без "чистого" в ней.

- **"Слой use cases — то же самое, что слой сервисов"** — на практике они часто перекрываются, но "сервис" в многоуровневой архитектуре обычно допускает импорты из фреймворка; Use Case в Clean Architecture явно их запрещает. Строгое соблюдение — это и есть разница.

- **"Clean Architecture означает, что нужно писать интерфейс для каждого класса"** — вы пишете интерфейсы там, где без них Правило зависимостей было бы нарушено: везде, где внутренний слой должен говорить с чем-то из внешнего слоя (БД, email, внешний API). Два класса в одном кольце, которые тесно связаны, не обязательно требуют интерфейса между собой.

- **"Dependency Inversion означает внедрение зависимостей через конструктор"** — это Dependency Injection (внедрение зависимостей), техника. Dependency Inversion (буква "D" в SOLID) — принцип: модули высокого уровня не должны зависеть от модулей низкого уровня; оба должны зависеть от абстракций. Инъекция через конструктор — один из способов реализации, но принцип касается направления абстракции, а не механизма инъекции.

- **"Entities — это модели базы данных"** — в Clean Architecture entity (сущности) — чистые бизнес-объекты без ORM-декораторов, без `@Column`, без `@Entity`. ORM-модель живёт в самом внешнем кольце (кольцо 4) или в кольце адаптеров. Entity — то, о чём заботится бизнес; ORM-модель — то, как данные хранятся.

- **"Clean Architecture всегда оправдана"** — Дядя Боб сам говорит, что применять её нужно там, где она приносит ценность. 200-строчный скрипт не нуждается в четырёх кольцах. Паттерн решает боль больших кодовых баз, где бизнес-логика со временем переплетается с деталями фреймворка. Применяйте пропорционально.
