# CQRS Pattern

## Концепция — разделение чтения и записи

CQRS (Command Query Responsibility Segregation) разделяет операции на два независимых потока: Commands (изменяют состояние, ничего не возвращают) и Queries (только читают данные, ничего не меняют). Принцип Bertrand Meyer: метод должен либо делать что-то (command), либо отвечать на вопрос (query) — но не оба сразу.

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

  CommandBus → CommandHandler → DB (write)
  QueryBus   → QueryHandler   → DB/Cache (read)
```

## Полная реализация с @nestjs/cqrs

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

## Использование в Controller

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

## Event Sourcing vs CQRS — частая путаница

```txt
CQRS:                           Event Sourcing:
Разделяет read/write модели     Хранит историю событий вместо состояния
Может быть без Event Sourcing   Почти всегда использует CQRS
Не меняет как данные хранятся   Фундаментально меняет storage strategy

CQRS без ES:
  Commands → записать в БД current state
  Queries  → читать из той же БД или read replica

CQRS + ES:
  Commands → добавить Event в event store (immutable log)
  Queries  → читать из materialized view (проекция событий)
  Replay   → восстановить любое предыдущее состояние

Когда добавлять Event Sourcing:
  ✓ Нужен полный audit trail (финансы, медицина, юридика)
  ✓ Temporal queries ("каким был баланс 30 дней назад?")
  ✓ Сложные бизнес-правила основанные на истории
  ✗ Простой CRUD — ES добавляет огромную сложность
```

## Саги (Sagas) — координация между командами

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

```txt
Подходит CQRS:                    НЕ нужен CQRS:
─────────────────────────────────────────────────────────
Сложный domain (DDD)              Simple CRUD (≤10 endpoints)
Разная нагрузка read/write        Admin Panel, Internal Tool
Микросервисная архитектура        MVP / прототип
Event-driven side effects         Команда < 5 человек
Нужен audit trail                 Нет планов масштабирования
Разные схемы read и write models  Сжатые сроки

Признак что пора добавить CQRS:
  Service имеет >10 методов
  Методы смешивают read и write логику
  Сложно тестировать (много зависимостей)
  Нужны side effects после команд
```

## Типичные ошибки на интервью

- **"CQRS — это микросервисный паттерн"** — нет. CQRS работает внутри одного монолитного приложения. `@nestjs/cqrs` — для монолита. Да, CQRS часто используется в микросервисах, но это не обязательное условие.

- **"Command не должен ничего возвращать"** — строго говоря, принцип CQS (Command Query Separation) говорит что Command void, но на практике в @nestjs/cqrs CommandHandler.execute() может возвращать данные (например, созданный объект с сгенерированным ID). Многие команды возвращают ID созданной сущности.

- **"CQRS и Event Sourcing — одно и то же"** — нет. CQRS разделяет модели чтения и записи. Event Sourcing — паттерн хранения данных как последовательности событий. Можно использовать CQRS без Event Sourcing (большинство NestJS проектов). Event Sourcing почти всегда требует CQRS, но не наоборот.

- **"EventHandler блокирует Command"** — нет. `eventBus.publish()` публикует событие асинхронно. CommandHandler не ждёт завершения EventHandlers. Если нужна гарантия выполнения — EventHandler должен иметь собственную retry-логику или использовать message queue (BullMQ, Kafka).

- **"Саги нужны для всех событий"** — нет. Сагу добавляют когда нужно координировать несколько команд в ответ на событие (distributed saga pattern). Простой side effect (отправить email) — это задача EventHandler, не Saga. Saga нужна когда событие A → команда B → событие C → команда D (цепочка бизнес-процесса).
