# Гексагональная архитектура (Порты и Адаптеры)

> **Область применения:** Как и Clean Architecture, гексагональная архитектура описывает организацию кода внутри одного приложения — изоляцию ядра от внешних зависимостей. Она не касается взаимодействия сервисов между собой.

## Ментальная модель — шестиугольник с подключаемыми сторонами

Гексагональная архитектура (она же **Ports and Adapters** — «Порты и Адаптеры») описана Alistair Cockburn в 2005 году. «Гексагональность» не несёт смысловой нагрузки — Cockburn выбрал шестиугольник потому, что у него больше сторон, чем у прямоугольника: на рисунке удобнее разместить несколько портов. Настоящее название — *Ports and Adapters* — точнее отражает суть.

Центральная идея: у приложения есть **ядро** (бизнес-логика) и **граница**. Всё, что находится за границей, — внешняя система: база данных, HTTP-клиент, очередь сообщений, CLI, тестовый стенд. С каждой внешней системой приложение общается через одно из двух:

- **Порт (Port)** — интерфейс (контракт), определённый самим приложением
- **Адаптер (Adapter)** — конкретная реализация этого интерфейса, подключающаяся к определённой внешней системе

```txt
                     ┌────────────────────────────────┐
    HTTP Client ──── │ Адаптер (Express Controller)   │
                     │              ↓                  │
    REST API ──────  │ ──────────►  ПОРТ               │
                     │         (IOrderService)         │
                     │              ↓                  │
                     │          ЯДРО                   │
                     │       ПРИЛОЖЕНИЯ                │
                     │              ↓                  │
                     │         ПОРТ                    │
                     │   (IOrderRepository)  ◄──────── │ ── Адаптер (Prisma Repository)
                     │              ↓                  │
                     │   ПОРТ                          │
                     │   (INotificationService) ◄───── │ ── Адаптер (Sendgrid)
                     └────────────────────────────────┘
```

Ядро ничего не знает об Express, Prisma или Sendgrid. Оно знает только о своих портах. Заменить Sendgrid на Mailgun — значит написать новый адаптер. Ядро не изменится.

## Порты — два вида

Порты бывают двух направлений, и понимание направления принципиально:

### Управляющие порты (левая сторона / primary ports)

Управляющий порт — интерфейс, через который **внешний актор управляет приложением**. Актор (HTTP-клиент, CLI, тест) вызывает приложение через этот порт. Адаптер на левой стороне переводит формат внешнего актора на язык порта.

```ts
// Управляющий порт — приложение говорит «вот как меня можно использовать»
// Определён внутри ядра; реализован самим приложением
export interface IPlaceOrderUseCase {
  execute(input: PlaceOrderInput): Promise<Order>;
}

// Управляющий адаптер — переводит HTTP-запрос на язык порта
// Живёт за пределами ядра
export class HttpOrderAdapter {
  constructor(private useCase: IPlaceOrderUseCase) {}

  async handlePost(req: Request, res: Response): Promise<void> {
    const order = await this.useCase.execute({
      userId: req.user!.id,
      total: Number(req.body.total),
    });
    res.status(201).json(order);
  }
}
```

### Управляемые порты (правая сторона / secondary ports)

Управляемый порт — интерфейс, через который **приложение управляет внешней системой**. Приложение говорит «мне нужно что-то снаружи — вот контракт». Адаптер на правой стороне реализует этот контракт, используя конкретную технологию.

```ts
// Управляемый порт — приложение говорит «вот что мне нужно снаружи»
// Определён внутри ядра
export interface IOrderRepository {
  findById(id: string): Promise<Order | null>;
  save(order: Order): Promise<Order>;
}

export interface IEmailNotifier {
  sendConfirmation(email: string, orderId: string): Promise<void>;
}

// Управляемый адаптер — реализует порт на конкретной технологии
// Живёт за пределами ядра
export class PrismaOrderRepository implements IOrderRepository {
  constructor(private prisma: PrismaClient) {}

  async findById(id: string): Promise<Order | null> {
    const row = await this.prisma.order.findUnique({ where: { id } });
    return row ? mapToOrder(row) : null;
  }

  async save(order: Order): Promise<Order> {
    const row = await this.prisma.order.upsert({
      where: { id: order.id },
      create: mapToDb(order),
      update: mapToDb(order),
    });
    return mapToOrder(row);
  }
}
```

## Полная структура проекта

```txt
src/
├── core/                          ← сам шестиугольник
│   ├── domain/                    ← сущности и бизнес-правила
│   │   └── order.ts
│   ├── ports/                     ← все интерфейсы портов
│   │   ├── driving/               ← управляющие порты (как ИСПОЛЬЗОВАТЬ приложение)
│   │   │   └── place-order.port.ts
│   │   └── driven/                ← управляемые порты (что приложению НУЖНО снаружи)
│   │       ├── order-repository.port.ts
│   │       └── email-notifier.port.ts
│   └── use-cases/                 ← логика приложения (реализует управляющие порты)
│       └── place-order.use-case.ts
│
└── adapters/                      ← всё за пределами шестиугольника
    ├── driving/                   ← управляющие адаптеры (транслируют входящие вызовы)
    │   ├── http/
    │   │   └── orders.controller.ts
    │   └── cli/
    │       └── place-order.command.ts
    └── driven/                    ← управляемые адаптеры (реализуют управляемые порты)
        ├── persistence/
        │   └── prisma-order.repository.ts
        ├── notification/
        │   └── sendgrid-email.notifier.ts
        └── in-memory/             ← тестовые адаптеры — быстрые, без I/O
            ├── in-memory-order.repository.ts
            └── fake-email.notifier.ts
```

Адаптеры в `in-memory/` — ключевая идея: в тестах вы не мокаете — вы предоставляете настоящую (но in-memory) реализацию управляемого порта. Это чище мокирования, потому что in-memory адаптер обязан соблюдать контракт интерфейса.

```ts
// adapters/driven/in-memory/in-memory-order.repository.ts
// Настоящая реализация IOrderRepository через Map — для тестов
import type { IOrderRepository } from '../../../core/ports/driven/order-repository.port';
import type { Order } from '../../../core/domain/order';

export class InMemoryOrderRepository implements IOrderRepository {
  private store = new Map<string, Order>();

  async findById(id: string): Promise<Order | null> {
    return this.store.get(id) ?? null;
  }

  async save(order: Order): Promise<Order> {
    this.store.set(order.id, order);
    return order;
  }

  // Тестовый хелпер — проверить состояние без прохода через интерфейс
  getAll(): Order[] {
    return Array.from(this.store.values());
  }
}
```

```ts
// use-cases/place-order.use-case.test.ts
// Используем in-memory адаптеры — без моков, без стабов, настоящие реализации
import { PlaceOrderUseCase } from '../core/use-cases/place-order.use-case';
import { InMemoryOrderRepository } from '../adapters/driven/in-memory/in-memory-order.repository';
import { FakeEmailNotifier } from '../adapters/driven/in-memory/fake-email.notifier';

const orderRepo = new InMemoryOrderRepository();
const emailNotifier = new FakeEmailNotifier();
const useCase = new PlaceOrderUseCase(orderRepo, emailNotifier);

test('сохраняет заказ и отправляет подтверждение', async () => {
  const order = await useCase.execute({ userId: 'u1', total: 150 });

  expect(orderRepo.getAll()).toHaveLength(1);
  expect(emailNotifier.getSentEmails()).toContainEqual(
    expect.objectContaining({ orderId: order.id })
  );
});
```

## Антикоррупционный слой (ACL)

**ACL (Anti-Corruption Layer — антикоррупционный слой)** — паттерн, который часто используется вместе с гексагональной архитектурой. По сути это управляемый адаптер с дополнительной задачей: не просто трансформировать формат данных, но и **защищать доменную модель от терминологии и концепций внешней системы**.

Проблема, которую он решает: внешние API приходят со своим словарём, своими структурами данных и концепциями, которые могут отличаться от вашей доменной модели или даже вредить ей. Без ACL этот внешний словарь просачивается в ядро.

```ts
// Внешний API платёжной системы возвращает такую форму — её словарь, не ваш
interface StripePaymentIntent {
  id: string;
  amount: number;          // в центах
  currency: string;
  status: 'requires_payment_method' | 'requires_confirmation' | 'succeeded' | 'canceled';
  metadata: Record<string, string>;
  created: number;         // Unix timestamp
}

// Ваша доменная модель — ваш словарь
export interface Payment {
  id: string;
  orderId: string;
  amountInCents: number;
  currency: string;
  status: 'pending' | 'completed' | 'failed';
  processedAt: Date;
}

// ACL-адаптер — транслирует между двумя мирами
// Защищает домен от проникновения словаря Stripe
export class StripePaymentAdapter implements IPaymentGateway {
  constructor(private stripe: Stripe) {}

  async charge(orderId: string, amountInCents: number, currency: string): Promise<Payment> {
    const intent = await this.stripe.paymentIntents.create({
      amount: amountInCents,
      currency,
      metadata: { orderId },
    });

    // Антикоррупция: переводим статусы Stripe → доменный словарь
    return {
      id: intent.id,
      orderId,
      amountInCents: intent.amount,
      currency: intent.currency,
      status: this.mapStripeStatus(intent.status),
      processedAt: new Date(intent.created * 1000),
    };
  }

  private mapStripeStatus(stripeStatus: StripePaymentIntent['status']): Payment['status'] {
    switch (stripeStatus) {
      case 'succeeded': return 'completed';
      case 'canceled': return 'failed';
      default: return 'pending';
    }
  }
}
```

Без ACL в бизнес-логике может оказаться `if (payment.status === 'requires_payment_method')` — строка из словаря Stripe внутри вашей бизнес-логики. При смене платёжного провайдера эту строку придётся искать по всей кодовой базе.

ACL гарантирует, что концепции Stripe существуют **только** внутри адаптера. Всё остальное приложение работает с `'pending' | 'completed' | 'failed'` — своим, стабильным словарём.

## Гексагональная архитектура vs Clean Architecture — одна задача, разный словарь

Эти две архитектуры часто смешивают — и не зря: они решают одну и ту же проблему одним и тем же механизмом (инверсия зависимостей). Словарь разный, но структура отображается один в один:

```txt
Clean Architecture          Гексагональная архитектура
──────────────────────────────────────────────────────
Entities               ↔  Domain / Core
Use Cases              ↔  Ядро приложения + управляющие порты
Interface Adapters     ↔  Адаптеры (и управляющие, и управляемые)
Frameworks & Drivers   ↔  Внешние системы, к которым подключаются адаптеры

Dependency Rule        ↔  Ядро знает только о портах, которые оно определило;
                          адаптеры знают о ядре и о внешних системах
```

Главное практическое отличие — в акцентах:

- **Clean Architecture** акцентирует **кольца и их направление** — правило «не нарушай эту границу» касается того, в каком кольце находится код
- **Гексагональная архитектура** акцентирует **симметрию портов** — обе стороны приложения (входящая и исходящая) обрабатываются одинаково: через интерфейсы, определённые ядром

На практике TypeScript-проект, применяющий одну из них, выглядит идентично проекту, применяющему другую. Если на интервью спросят «что вы используете?» — честный ответ: «Я применяю Dependency Rule из Clean Architecture, организованную через словарь Ports and Adapters из гексагональной архитектуры — они взаимно усиливают друг друга».

## Когда "порты и адаптеры" особенно полезны

Фрейминг «портов и адаптеров» особенно ценен, когда:

1. **Несколько управляющих адаптеров** — одно и то же ядро вызывается HTTP-сервером, CLI-инструментом, тестовым стендом и воркером фоновых задач. Каждый — отдельный управляющий адаптер на левой стороне шестиугольника.

2. **Несколько управляемых адаптеров** — приложению нужен и production Postgres репозиторий, и быстрый in-memory репозиторий для тестов (а возможно, и CSV-репозиторий для скрипта импорта данных).

3. **Внешние API нужно изолировать** — вы вызываете сторонний API, модель данных которого вы не контролируете. ACL-адаптер не даёт их словарю расползтись по домену.

4. **Нужно менять инфраструктуру** — миграция с Sendgrid на AWS SES или с PostgreSQL на DynamoDB — это написание нового управляемого адаптера. Ядро не меняется.

## Типичные ошибки на интервью

- **«Порты — это то же самое, что интерфейсы»** — порт это специфический *вид* интерфейса: тот, который маркирует границу между ядром приложения и внешним миром и определён самим ядром (не внешней системой). Интерфейс `UserRepository`, используемый внутри сервисного слоя, — просто интерфейс. Интерфейс `IOrderRepository`, который use case определяет в ожидании, что внешний адаптер его реализует, — это порт.

- **«ACL — это просто data mapper»** — mapper транслирует названия полей и типы. ACL транслирует *концепции*: `'requires_payment_method'` → `'pending'` — это не переименование поля, это семантический перевод между двумя предметными словарями. Цель ACL — не дать концептуальной модели внешней системы «заразить» вашу.

- **«Гексагональная и Clean Architecture — разные подходы, нужно выбрать один»** — они скорее два описания одного и того же открытия. Большинство production-кодовых баз, применяющих один подход, выглядят идентично применяющим другой: оба подхода обеспечивают Dependency Rule через интерфейсные абстракции.

- **«Управляющие и управляемые порты работают одинаково»** — нет. Управляющий порт — интерфейс, который *реализует само ядро* (класс use case реализует управляющий порт). Управляемый порт — интерфейс, который ядро *определяет*, но *реализует внешний адаптер*. Направление обратное. Путаница здесь на интервью сигнализирует о поверхностном понимании паттерна.

- **«Добавлю гексагональную структуру позже, когда проект вырастет»** — стоимость добавления её позже высока: каждое место, нарушившее границу, придётся распутывать. Структуру дешевле добавить с самого начала, пока кодовая база мала. При этом применять её к 5-файловому CRUD — объективно избыточно. Правильный ответ — пропорциональное применение, а не «всегда» или «никогда».
