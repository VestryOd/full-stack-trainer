# Многоуровневая архитектура

> **Область применения:** Эта статья о том, как организовывать код *внутри* одного приложения или сервиса. Как несколько сервисов общаются между собой — service discovery, API gateway, балансировка нагрузки — это вопросы System Design, здесь не рассматриваются.

## Проблема, которую решает многоуровневая архитектура

Представьте кодовую базу, где обработчик Express-роута напрямую делает запросы к базе данных, форматирует ответ, применяет бизнес-правила и отправляет письма — всё в одной функции. Это не выдумка: именно так выглядят неструктурированные кодовые базы после нескольких месяцев работы в режиме "лишь бы поскорее".

```ts
// ❌ Всё смешано — реальность кода в режиме "просто выкатить в прод"
app.post('/orders', async (req, res) => {
  const user = await db.query('SELECT * FROM users WHERE id = $1', [req.user.id]);
  if (user.rows[0].creditLimit < req.body.total) {
    return res.status(400).json({ error: 'Insufficient credit' });
  }
  const order = await db.query(
    'INSERT INTO orders (user_id, total, status) VALUES ($1, $2, $3) RETURNING *',
    [req.user.id, req.body.total, 'pending'],
  );
  await sendgrid.send({ to: user.rows[0].email, subject: 'Order placed', text: '...' });
  res.json(order.rows[0]);
});
```

Проблемы с таким подходом:

- **Нельзя протестировать бизнес-правило** ("недостаточно кредита") без HTTP-запроса, реальной базы данных и реального сервиса email
- **Нельзя переиспользовать бизнес-правило** из скрипта командной строки (CLI), cron-задачи или WebSocket-обработчика — логика намертво привязана к HTTP
- **Изменение схемы базы данных** (переименование колонки) требует поиска сырых запросов на SQL (Structured Query Language) по всем файлам роутов
- **Новый член команды** не понимает, где "логика" — она везде

Многоуровневая архитектура решает все четыре проблемы сразу.

## Три слоя — и что куда относится

```txt
┌─────────────────────────────────────────┐
│            Слой представления           │  HTTP, WebSocket, CLI
│     (контроллеры, обработчики, DTO)     │  Знает о req/res
└────────────────────┬────────────────────┘
                     │ вызывает
┌────────────────────▼────────────────────┐
│            Слой бизнес-логики           │  Чистая логика, нет HTTP
│ (сервисы, доменные объекты, валидаторы) │  Без импортов фреймворка
└────────────────────┬────────────────────┘
                     │ вызывает
┌────────────────────▼────────────────────┐
│       Слой доступа к данным (DAL)       │  БД, кеш, внешние API
│  (репозитории, ORM-модели, DB-клиенты)  │  Без бизнес-правил
└─────────────────────────────────────────┘
```

**Слой представления** — переводит между внешним миром (HTTP-запросы, WebSocket-сообщения, CLI-аргументы) и приложением. Знает о `req`, `res`, HTTP-кодах, заголовках. Не содержит бизнес-правил. Его задача: валидировать форму входных данных, вызвать сервис, отформатировать вывод. Типы, в которых он принимает и отдаёт данные, — это DTO (data transfer object, объект передачи данных).

**Слой бизнес-логики** — сердце приложения. Он держит правила бизнеса:

- Пользователь не может разместить заказ, если превышен кредитный лимит.
- Счёт должен содержать хотя бы одну позицию.

Этот слой ничего не знает об HTTP, базах данных или провайдерах email. Он работает с чистыми объектами и интерфейсами.

**Слой доступа к данным (DAL, Data Access Layer)** — знает, как читать и записывать данные. SQL-запросы, вызовы ORM (object-relational mapper, объектно-реляционный маппер), операции Redis, вызовы внешних API. Не содержит бизнес-правил. Переводит между тем, что запрашивает бизнес-слой ("дай мне пользователя 42"), и тем, как данные реально хранятся.

## Правило строгого разделения слоёв — и почему оно важно

Правило: **каждый слой может вызывать только слой непосредственно ниже него.** Слой представления вызывает бизнес-слой. Бизнес-слой вызывает слой доступа к данным. Никто не пропускает слой и не вызывает вышестоящий.

```txt
✅ Разрешено:               ❌ Запрещено:
Presentation → Service      Presentation → Repository (пропуск слоя)
Service → Repository        Repository → Service (вызов вверх)
                            Service → req/res (утечка представления)
```

Почему строго? Потому что каждое нарушение снова вводит исходную проблему. Обработчик роута, напрямую вызывающий репозиторий, означает логику базы данных в слое представления — вы снова тестируете бизнес-правила через HTTP.

## Практическая файловая структура

```txt
src/
├── presentation/           (или: controllers/, routes/)
│   ├── orders.controller.ts
│   └── orders.dto.ts
├── services/               (слой бизнес-логики)
│   └── orders.service.ts
├── repositories/           (слой доступа к данным)
│   └── orders.repository.ts
└── domain/                 (опционально: чистые доменные типы)
    └── order.ts
```

## Рефакторинг примера

```ts
// domain/order.ts — чистые типы, без фреймворка
export interface Order {
  id: string;
  userId: string;
  total: number;
  status: 'pending' | 'confirmed' | 'cancelled';
  createdAt: Date;
}

export interface CreateOrderInput {
  userId: string;
  total: number;
}
```

```ts
// repositories/orders.repository.ts — только доступ к данным, без бизнес-правил
import { db } from '../db';
import type { Order, CreateOrderInput } from '../domain/order';

export class OrdersRepository {
  async findById(id: string): Promise<Order | null> {
    const row = await db.query('SELECT * FROM orders WHERE id = $1', [id]);
    return row.rows[0] ?? null;
  }

  async create(input: CreateOrderInput): Promise<Order> {
    const row = await db.query(
      'INSERT INTO orders (user_id, total, status) VALUES ($1, $2, $3) RETURNING *',
      [input.userId, input.total, 'pending'],
    );
    return row.rows[0];
  }
}
```

```ts
// services/orders.service.ts — только бизнес-логика
// Обратите внимание: нет импортов из express, нет req/res, нет сырого SQL
import type { OrdersRepository } from '../repositories/orders.repository';
import type { UsersRepository } from '../repositories/users.repository';
import type { EmailService } from './email.service';
import type { Order, CreateOrderInput } from '../domain/order';

export class InsufficientCreditError extends Error {
  constructor(userId: string, required: number, available: number) {
    super(`Пользователю ${userId} нужно ${required}, доступно ${available}`);
    this.name = 'InsufficientCreditError';
  }
}

export class OrdersService {
  constructor(
    private ordersRepo: OrdersRepository,
    private usersRepo: UsersRepository,
    private emailService: EmailService,
  ) {}

  async createOrder(input: CreateOrderInput): Promise<Order> {
    const user = await this.usersRepo.findById(input.userId);
    if (!user) throw new Error(`Пользователь ${input.userId} не найден`);

    // Бизнес-правило живёт здесь — не в обработчике роута, не в репозитории
    if (user.creditLimit < input.total) {
      throw new InsufficientCreditError(input.userId, input.total, user.creditLimit);
    }

    const order = await this.ordersRepo.create(input);

    // Уведомление — сервис вызывает другой сервис, по-прежнему без HTTP
    await this.emailService.sendOrderConfirmation(user.email, order);

    return order;
  }
}
```

```ts
// presentation/orders.controller.ts — только HTTP, без бизнес-правил
import { Router, type Request, type Response } from 'express';
import { OrdersService, InsufficientCreditError } from '../services/orders.service';

export function createOrdersRouter(ordersService: OrdersService): Router {
  const router = Router();

  router.post('/', async (req: Request, res: Response) => {
    try {
      const order = await ordersService.createOrder({
        userId: req.user!.id,
        total: req.body.total,
      });
      res.status(201).json(order);
    } catch (err) {
      if (err instanceof InsufficientCreditError) {
        return res.status(400).json({ error: err.message });
      }
      throw err; // error middleware обработает неожиданные ошибки
    }
  });

  return router;
}
```

Теперь бизнес-правило ("недостаточно кредита") тестируется без HTTP:

```ts
// orders.service.test.ts — нет HTTP, нет базы данных, нет реальной отправки email
import { OrdersService, InsufficientCreditError } from './orders.service';

const mockOrdersRepo = { findById: jest.fn(), create: jest.fn() };
const mockUsersRepo = { findById: jest.fn() };
const mockEmailService = { sendOrderConfirmation: jest.fn() };

const service = new OrdersService(mockOrdersRepo, mockUsersRepo, mockEmailService);

test('бросает InsufficientCreditError при превышении кредитного лимита', async () => {
  mockUsersRepo.findById.mockResolvedValue({ id: '1', email: 'a@b.com', creditLimit: 50 });

  await expect(
    service.createOrder({ userId: '1', total: 100 })
  ).rejects.toBeInstanceOf(InsufficientCreditError);
});
```

## NestJS и многоуровневая архитектура

NestJS задаёт эту структуру своими соглашениями:

- Декоратор `@Controller` маркирует слой представления.
- Сервисы, помеченные `@Injectable()`, — бизнес-слой.
- Репозитории — слой доступа к данным, часто как тонкие обёртки над TypeORM или Prisma.

```ts
// NestJS — слоистость обеспечивает контейнер внедрения зависимостей (DI)
@Controller('orders')
export class OrdersController {
  constructor(private readonly ordersService: OrdersService) {}

  @Post()
  create(@Body() dto: CreateOrderDto, @Request() req) {
    return this.ordersService.createOrder({ userId: req.user.id, total: dto.total });
  }
}

@Injectable()
export class OrdersService {
  constructor(private readonly ordersRepository: OrdersRepository) {}
  // бизнес-логика здесь
}

@Injectable()
export class OrdersRepository {
  constructor(private readonly prisma: PrismaService) {}
  // доступ к данным здесь
}
```

NestJS `Module` выступает в роли "проводки" — объявляет провайдеры и внедряет их.

## Когда многоуровневая архитектура — правильный выбор

Многоуровневая архитектура — правильный выбор по умолчанию для большинства приложений:
- Команды из 2–10 инженеров на одной кодовой базе
- Бизнес-логика, которую нужно тестировать изолированно
- Приложения, которые могут потребовать замены базы данных или механизма доставки (HTTP → CLI → cron)

Когда она начинает давать сбои:
- Очень сложные домены, где каждый "слой" превращается в жирный класс с десятками методов. Здесь [Clean Architecture](./03-clean-architecture.md) или [Hexagonal Architecture](./04-hexagonal-architecture.md) дают более дробное разделение
- Сквозные аспекты (аудит, авторизация, логирование), которые не вписываются аккуратно в один слой

## Типичные ошибки на интервью

- **"Слой сервисов — просто прокси, он не добавляет ценности"** — это признак недоизвлечённой бизнес-логики. Если сервис буквально делает `return this.repo.findById(id)` для каждого метода — бизнес-правила утекли в репозиторий или контроллер. Слой сервисов должен содержать решения, валидации и оркестрацию.

- **"Я делаю запрос к базе прямо в контроллере, чтобы было проще"** — то, что проще сейчас, потом больно тестировать и менять. Усилий на извлечение репозитория минимум. Цена обхода накапливается с каждой добавленной фичей.

- **"Репозитории нужны только если планируете менять базу данных"** — такая формулировка упускает главное преимущество. Репозитории делают слой сервисов тестируемым без реальной базы данных. Возможность поменять PostgreSQL на MySQL — побочный эффект, а не основная причина.

- **"Бизнес-логика в модели/entity лучше, чем в сервисе"** — иногда верно. Метод `User.hasPermission()`, проверяющий свойства объекта, — хороший пример. Проблема возникает, когда методы модели начинают принимать клиент базы данных или HTTP-объекты в аргументах. В этот момент граница слоя растворяется внутри самой сущности.

- **"Многоуровневая архитектура — то же самое, что Clean Architecture"** — они решают связанные, но разные задачи. Многоуровневая архитектура организует код в горизонтальные уровни. [Clean Architecture](./03-clean-architecture.md) добавляет Dependency Rule: внешние слои зависят от внутренних, но не наоборот. Ещё она определяет, в каком направлении должны указывать абстракции. Можно построить плохую многоуровневую архитектуру, где слой сервисов напрямую импортирует из Express, — Clean Architecture это явно запрещает.
