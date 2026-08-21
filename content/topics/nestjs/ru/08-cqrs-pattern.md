# Паттерн CQRS

## Концепция — разделение чтения и записи

CQRS (Command Query Responsibility Segregation — разделение ответственности за команды и запросы) делит операции на два независимых потока. Commands меняют состояние. Queries только читают данные и ничего не меняют.

Строгая формулировка принадлежит Бертрану Мейеру: метод должен либо делать что-то (command), либо отвечать на вопрос (query), но не то и другое сразу. Пакет `@nestjs/cqrs` от этой строгости отступает — о нём в конце статьи.

```txt
Традиционный Service Layer:
  UserService
  ├── createUser()   → void (изменяет)
  ├── updateUser()   → void (изменяет)
  ├── deleteUser()   → void (изменяет)
  ├── getUser()      → User (читает)
  └── getUsers()     → User[] (читает)

CQRS:
  Commands (WriteModel)        Queries (ReadModel)
  ├── CreateUserCommand        ├── GetUserQuery
  ├── UpdateUserCommand        ├── GetUsersQuery
  └── DeleteUserCommand        └── GetUserProfileQuery

  CommandBus → CommandHandler → запись в базу
  QueryBus   → QueryHandler   → чтение из базы или кеша
```

## Полная реализация с `@nestjs/cqrs`

Пакет `@nestjs/cqrs` даёт шесть строительных блоков, и читать их удобно парами:

- **Command** и **CommandHandler** — намерение изменить состояние и код, который это выполняет.
- **Query** и **QueryHandler** — описание того, что нужно прочитать, и само чтение.
- **Event** и **EventHandler** — сообщение о том, что уже произошло, и реакция на него.

Command и Query — простые классы с полями `readonly`, без логики. Логика живёт в обработчике. А найти нужный обработчик по классу команды — работа шины: `CommandBus`, `QueryBus`, `EventBus`.

```typescript
// 1. Command — описывает намерение изменить состояние
// Команды неизменяемы: readonly поля
export class CreateUserCommand {
  constructor(
    public readonly email: string,
    public readonly name: string,
    public readonly role: UserRole,
  ) {}
}

// 2. Command Handler — выполняет бизнес-логику
@CommandHandler(CreateUserCommand)
export class CreateUserHandler implements ICommandHandler<CreateUserCommand> {
  constructor(
    private prisma: PrismaService,
    private eventBus: EventBus,
  ) {}

  async execute(command: CreateUserCommand): Promise<User> {
    const { email, name, role } = command;

    // Проверить бизнес-правила
    const existing = await this.prisma.user.findUnique({ where: { email } });
    if (existing) throw new ConflictException('Email already in use');

    // Изменить состояние
    const user = await this.prisma.user.create({
      data: { email, name, role },
    });

    // Опубликовать событие — для side effects
    this.eventBus.publish(new UserCreatedEvent(user.id, user.email));

    return user;
  }
}

// 3. Query — описывает что нужно прочитать
export class GetUserQuery {
  constructor(public readonly userId: string) {}
}

// 4. Query Handler — только чтение, можно оптимизировать отдельно
@QueryHandler(GetUserQuery)
export class GetUserHandler implements IQueryHandler<GetUserQuery> {
  constructor(private prisma: PrismaService) {}

  async execute(query: GetUserQuery): Promise<UserDto> {
    const user = await this.prisma.user.findUniqueOrThrow({
      where: { id: query.userId },
      select: { id: true, email: true, name: true, role: true, createdAt: true },
    });
    return user;
  }
}

// 5. Event — сигнал что что-то произошло (прошедшее время)
export class UserCreatedEvent {
  constructor(
    public readonly userId: string,
    public readonly email: string,
  ) {}
}

// 6. Event Handler — реагирует на событие, decoupled от команды
@EventsHandler(UserCreatedEvent)
export class UserCreatedHandler implements IEventHandler<UserCreatedEvent> {
  constructor(
    private emailService: EmailService,
    private auditService: AuditService,
  ) {}

  async handle(event: UserCreatedEvent) {
    // Параллельные side effects — не блокируют команду
    await Promise.all([
      this.emailService.sendWelcome(event.email),
      this.auditService.log('user_created', event.userId),
    ]);
  }
}
```

## Использование в контроллере

В контроллере не остаётся бизнес-логики. Он собирает команду или запрос из входных данных и отдаёт шине, а шина сама находит обработчик по классу.

Одно условие: обработчики нужно объявить обычными провайдерами модуля и импортировать `CqrsModule`. Иначе шина о них не узнает.

```typescript
@Controller('users')
export class UsersController {
  constructor(
    private readonly commandBus: CommandBus,
    private readonly queryBus: QueryBus,
  ) {}

  @Post()
  async create(@Body() dto: CreateUserDto) {
    // Dispatch команды — CommandBus находит нужный CommandHandler
    return this.commandBus.execute(
      new CreateUserCommand(dto.email, dto.name, dto.role),
    );
  }

  @Get(':id')
  async findOne(@Param('id', ParseUUIDPipe) id: string) {
    // Dispatch запроса — QueryBus находит нужный QueryHandler
    return this.queryBus.execute(new GetUserQuery(id));
  }
}

// Регистрация в Module:
@Module({
  imports: [CqrsModule],
  providers: [
    CreateUserHandler,
    UpdateUserHandler,
    DeleteUserHandler,
    GetUserHandler,
    GetUsersHandler,
    UserCreatedHandler,
  ],
})
export class UsersModule {}
```

## Event Sourcing и CQRS — частая путаница

Это два разных паттерна. CQRS делит модели чтения и записи. Event Sourcing (ES) меняет способ хранения. Вместо текущего состояния база держит цепочку событий, а состояние вычисляется проигрыванием этой цепочки.

Отсюда несимметричная связь: CQRS без Event Sourcing встречается постоянно, а Event Sourcing без CQRS — почти никогда.

| | CQRS | Event Sourcing |
|---|---|---|
| Что делает | Разделяет модели чтения и записи | Хранит историю событий вместо состояния |
| Нужен ли второй паттерн | Работает и без Event Sourcing | Почти всегда используется с CQRS |
| Влияние на хранилище | Способ хранения не меняется | Меняет способ хранения принципиально |

```txt
CQRS без Event Sourcing:
  Commands → записать текущее состояние в базу
  Queries  → читать из той же базы или из реплики

CQRS + Event Sourcing:
  Commands → добавить событие в журнал (только дописывание)
  Queries  → читать из проекции событий
  Replay   → восстановить любое прошлое состояние

Когда добавлять Event Sourcing:
  ✓ Нужна полная история изменений (финансы, медицина, право)
  ✓ Запросы про прошлое ("каким был баланс 30 дней назад?")
  ✓ Сложные бизнес-правила, зависящие от истории
  ✗ Простой CRUD — Event Sourcing добавляет огромную сложность
```

## Саги — координация между командами

Сага (Saga) слушает поток событий и в ответ отправляет команды. Она нужна, когда бизнес-процесс идёт цепочкой: событие A → команда B → событие C → команда D.

Записывают сагу как поле-стрелку с декоратором `@Saga()`. На входе поток событий, `ofType` оставляет нужный тип, `map` превращает событие в команду. Возвращённые команды шина выполняет сама.

```typescript
// Saga реагирует на события и может publish новые Commands
// Используется для сложных бизнес-процессов (распределённые транзакции)
@Injectable()
export class UserRegistrationSaga {
  // ofType фильтрует события из EventBus
  @Saga()
  userRegistered = (events$: Observable<any>): Observable<ICommand> => {
    return events$.pipe(
      ofType(UserCreatedEvent),
      // Трансформировать событие в команду
      map(event => new SendWelcomeEmailCommand(event.email)),
    );
  };
}

// Saga: UserCreatedEvent → CommandBus.execute(SendWelcomeEmailCommand)
// Decouples: UserCreatedHandler не знает об email логике
```

## Когда CQRS оправдан

CQRS стоит несколько дополнительных файлов на каждую операцию, поэтому вопрос всегда один: за что вы платите эту цену.

В таблице слева — признаки, при которых цена окупается, справа — при которых нет. Три сокращения в ней стоит расшифровать сразу. DDD (domain-driven design) — проектирование от предметной области. CRUD (create, read, update, delete) — четыре базовые операции над записью. MVP (minimum viable product) — минимальная версия продукта, которую показывают первым пользователям.

| Подходит CQRS | Не нужен CQRS |
|---|---|
| Сложный домен, спроектированный по DDD | Простой CRUD, до 10 эндпоинтов |
| Разная нагрузка на чтение и запись | Админка, внутренний инструмент |
| Микросервисная архитектура | MVP или прототип |
| Побочные эффекты через события | Команда меньше пяти человек |
| Нужна полная история изменений | Нет планов роста нагрузки |
| Разные схемы для чтения и для записи | Сжатые сроки |

Признаки, что действующий сервис пора разделить:

- В сервисе больше десяти методов.
- Методы смешивают чтение и запись.
- Сервис трудно тестировать: слишком много зависимостей.
- После команд нужны побочные эффекты.

## Типичные ошибки на интервью

- **"CQRS — это микросервисный паттерн"** — нет. CQRS работает внутри одного монолитного приложения, и `@nestjs/cqrs` сделан именно для монолита. В микросервисах его действительно применяют часто, но это не обязательное условие.

- **"Command не должен ничего возвращать"** — строго по принципу CQS (Command Query Separation — разделение команд и запросов) действительно так. На практике `@nestjs/cqrs` не ограничивает тип возвращаемого значения, и `CommandHandler.execute()` часто возвращает созданный объект или его идентификатор.

- **"CQRS и Event Sourcing — одно и то же"** — нет. CQRS разделяет модели чтения и записи. Event Sourcing — способ хранения данных как последовательности событий. CQRS без Event Sourcing работает, и так сделано большинство проектов на NestJS. Event Sourcing почти всегда требует CQRS, но не наоборот.

- **"EventHandler блокирует Command"** — нет. `eventBus.publish()` публикует событие асинхронно, и CommandHandler не ждёт, пока обработчики события закончат. Нужна гарантия выполнения — заведите в обработчике свои повторные попытки или отправляйте задачу в очередь (BullMQ, Kafka).

- **"Саги нужны для всех событий"** — нет. Сага нужна, когда в ответ на событие надо согласованно выполнить несколько команд. Простой побочный эффект вроде отправки письма — работа EventHandler. Сага начинается там, где цепочка: событие A → команда B → событие C → команда D.
