# CQRS Pattern

## Concept — separating reads and writes

CQRS (Command Query Responsibility Segregation) splits operations into two independent flows: Commands (mutate state, return nothing) and Queries (only read data, change nothing). Bertrand Meyer's principle: a method should either do something (command) or answer a question (query) — but not both.

```txt
Traditional Service Layer:
  UserService
  ├── createUser()   → void (mutates)
  ├── updateUser()   → void (mutates)
  ├── deleteUser()   → void (mutates)
  ├── getUser()      → User (reads)
  └── getUsers()     → User[] (reads)

CQRS:
  Commands (WriteModel)        Queries (ReadModel)
  ├── CreateUserCommand        ├── GetUserQuery
  ├── UpdateUserCommand        ├── GetUsersQuery
  └── DeleteUserCommand        └── GetUserProfileQuery

  CommandBus → CommandHandler → DB (write)
  QueryBus   → QueryHandler   → DB/Cache (read)
```

## Full implementation with @nestjs/cqrs

```typescript
// 1. Command — describes the intent to mutate state
// Commands are immutable: readonly fields
export class CreateUserCommand {
  constructor(
    public readonly email: string,
    public readonly name: string,
    public readonly role: UserRole,
  ) {}
}

// 2. Command Handler — executes business logic
@CommandHandler(CreateUserCommand)
export class CreateUserHandler implements ICommandHandler<CreateUserCommand> {
  constructor(
    private prisma: PrismaService,
    private eventBus: EventBus,
  ) {}

  async execute(command: CreateUserCommand): Promise<User> {
    const { email, name, role } = command;

    // Check business rules
    const existing = await this.prisma.user.findUnique({ where: { email } });
    if (existing) throw new ConflictException('Email already in use');

    // Mutate state
    const user = await this.prisma.user.create({
      data: { email, name, role },
    });

    // Publish event — for side effects
    this.eventBus.publish(new UserCreatedEvent(user.id, user.email));

    return user;
  }
}

// 3. Query — describes what to read
export class GetUserQuery {
  constructor(public readonly userId: string) {}
}

// 4. Query Handler — read-only, can be optimized independently
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

// 5. Event — signals that something happened (past tense)
export class UserCreatedEvent {
  constructor(
    public readonly userId: string,
    public readonly email: string,
  ) {}
}

// 6. Event Handler — reacts to the event, decoupled from the command
@EventsHandler(UserCreatedEvent)
export class UserCreatedHandler implements IEventHandler<UserCreatedEvent> {
  constructor(
    private emailService: EmailService,
    private auditService: AuditService,
  ) {}

  async handle(event: UserCreatedEvent) {
    // Parallel side effects — do not block the command
    await Promise.all([
      this.emailService.sendWelcome(event.email),
      this.auditService.log('user_created', event.userId),
    ]);
  }
}
```

## Usage in Controller

```typescript
@Controller('users')
export class UsersController {
  constructor(
    private readonly commandBus: CommandBus,
    private readonly queryBus: QueryBus,
  ) {}

  @Post()
  async create(@Body() dto: CreateUserDto) {
    // Dispatch command — CommandBus finds the right CommandHandler
    return this.commandBus.execute(
      new CreateUserCommand(dto.email, dto.name, dto.role),
    );
  }

  @Get(':id')
  async findOne(@Param('id', ParseUUIDPipe) id: string) {
    // Dispatch query — QueryBus finds the right QueryHandler
    return this.queryBus.execute(new GetUserQuery(id));
  }
}

// Registration in Module:
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

## Event Sourcing vs CQRS — a common confusion

```txt
CQRS:                           Event Sourcing:
Separates read/write models     Stores event history instead of state
Can be used without ES          Almost always uses CQRS
Doesn't change how data stored  Fundamentally changes storage strategy

CQRS without ES:
  Commands → write current state to DB
  Queries  → read from same DB or read replica

CQRS + ES:
  Commands → append Event to event store (immutable log)
  Queries  → read from materialized view (projection of events)
  Replay   → reconstruct any previous state

When to add Event Sourcing:
  ✓ Full audit trail needed (finance, medical, legal)
  ✓ Temporal queries ("what was the balance 30 days ago?")
  ✓ Complex business rules based on history
  ✗ Simple CRUD — ES adds enormous complexity
```

## Sagas — coordinating between commands

```typescript
// Saga reacts to events and can publish new Commands
// Used for complex business processes (distributed transactions)
@Injectable()
export class UserRegistrationSaga {
  // ofType filters events from EventBus
  @Saga()
  userRegistered = (events$: Observable<any>): Observable<ICommand> => {
    return events$.pipe(
      ofType(UserCreatedEvent),
      // Transform event into a command
      map(event => new SendWelcomeEmailCommand(event.email)),
    );
  };
}

// Saga: UserCreatedEvent → CommandBus.execute(SendWelcomeEmailCommand)
// Decouples: UserCreatedHandler has no knowledge of email logic
```

## When CQRS is justified

```txt
CQRS fits:                        CQRS NOT needed:
─────────────────────────────────────────────────────────
Complex domain (DDD)              Simple CRUD (≤10 endpoints)
Different read/write load         Admin Panel, Internal Tool
Microservice architecture         MVP / prototype
Event-driven side effects         Team < 5 engineers
Audit trail required              No scaling plans
Different read and write schemas  Tight deadlines

Signs it's time to add CQRS:
  Service has >10 methods
  Methods mix read and write logic
  Hard to test (too many dependencies)
  Side effects needed after commands
```

## Common interview mistakes

- **"CQRS is a microservices pattern"** — no. CQRS works inside a single monolithic application. `@nestjs/cqrs` is for monoliths. Yes, CQRS is often used in microservices, but it's not a requirement.

- **"A Command must not return anything"** — strictly speaking, the CQS (Command Query Separation) principle says a Command is void, but in practice `@nestjs/cqrs` CommandHandler.execute() can return data (e.g., the created object with a generated ID). Many commands return the ID of the created entity.

- **"CQRS and Event Sourcing are the same thing"** — no. CQRS separates read and write models. Event Sourcing is a data storage pattern where state is stored as a sequence of events. You can use CQRS without Event Sourcing (most NestJS projects do). Event Sourcing almost always requires CQRS, but not vice versa.

- **"EventHandler blocks the Command"** — no. `eventBus.publish()` publishes an event asynchronously. The CommandHandler does not wait for EventHandlers to complete. If execution guarantees are needed, the EventHandler needs its own retry logic or a message queue (BullMQ, Kafka).

- **"Sagas are needed for all events"** — no. Add a Saga when you need to coordinate multiple commands in response to an event (distributed saga pattern). A simple side effect (sending an email) is the job of an EventHandler, not a Saga. A Saga is needed when event A → command B → event C → command D (a chained business process).
