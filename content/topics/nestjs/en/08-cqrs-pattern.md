# CQRS Pattern

## Concept — separating reads and writes

CQRS (Command Query Responsibility Segregation) splits operations into two independent flows. Commands change state. Queries only read data and change nothing.

The strict formulation belongs to Bertrand Meyer: a method should either do something (a command) or answer a question (a query), but never both. The `@nestjs/cqrs` package bends that rule a little — more on that at the end of the article.

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

  CommandBus → CommandHandler → write to database
  QueryBus   → QueryHandler   → read from database or cache
```

## Full implementation with `@nestjs/cqrs`

The `@nestjs/cqrs` package gives you six building blocks, and they are easiest to read in pairs:

- **Command** and **CommandHandler** — the intent to change state, and the code that carries it out.
- **Query** and **QueryHandler** — a description of what to read, and the reading itself.
- **Event** and **EventHandler** — a message that something already happened, and the reaction to it.

Command and Query are plain classes with `readonly` fields and no logic. The logic lives in the handler. Finding the right handler for a given class is the bus's job: `CommandBus`, `QueryBus`, `EventBus`.

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

## Usage in a controller

No business logic is left in the controller. It builds a command or a query out of the input and hands it to the bus, and the bus finds the handler by class.

One condition: the handlers must be declared as ordinary module providers, and `CqrsModule` must be imported. Otherwise the bus never learns about them.

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

## Event Sourcing and CQRS — a common confusion

These are two different patterns. CQRS splits the read and write models. Event Sourcing (ES) changes how data is stored. Instead of the current state, the database keeps a chain of events, and the state is computed by replaying that chain.

Hence the one-sided relationship: CQRS without Event Sourcing is everywhere, while Event Sourcing without CQRS almost never happens.

| | CQRS | Event Sourcing |
|---|---|---|
| What it does | Separates read and write models | Stores event history instead of state |
| Does it need the other one | Works without Event Sourcing | Almost always used with CQRS |
| Effect on storage | Storage strategy unchanged | Changes the storage strategy completely |

```txt
CQRS without Event Sourcing:
  Commands → write the current state to the database
  Queries  → read from the same database or a replica

CQRS + Event Sourcing:
  Commands → append an event to the log (append-only)
  Queries  → read from a projection of the events
  Replay   → reconstruct any past state

When to add Event Sourcing:
  ✓ Full history of changes is required (finance, medical, legal)
  ✓ Questions about the past ("what was the balance 30 days ago?")
  ✓ Complex business rules that depend on history
  ✗ Simple CRUD — Event Sourcing adds enormous complexity
```

## Sagas — coordinating between commands

A Saga listens to the stream of events and sends commands in response. You need one when a business process runs as a chain: event A → command B → event C → command D.

A saga is written as an arrow-function field with a `@Saga()` decorator. The stream of events comes in, `ofType` keeps the type you want, and `map` turns the event into a command. The bus executes the returned commands itself.

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

CQRS costs you several extra files per operation, so the question is always the same: what are you buying with that price.

The left column lists signs that the price pays off, the right column signs that it does not. Three abbreviations in it are worth expanding right away. DDD (domain-driven design) means designing from the business domain. CRUD (create, read, update, delete) are the four basic operations on a record. MVP (minimum viable product) is the smallest version of a product you put in front of users.

| CQRS fits | CQRS not needed |
|---|---|
| Complex domain designed with DDD | Simple CRUD, up to 10 endpoints |
| Different read and write load | Admin panel, internal tool |
| Microservice architecture | MVP or prototype |
| Side effects driven by events | Team smaller than five people |
| Full history of changes required | No plans for load growth |
| Different schemas for reads and writes | Tight deadlines |

Signs that an existing service is ready to be split:

- The service has more than ten methods.
- Its methods mix reads and writes.
- It is hard to test: too many dependencies.
- Side effects are needed after commands.

## Common interview mistakes

- **"CQRS is a microservices pattern"** — no. CQRS works inside a single monolithic application, and `@nestjs/cqrs` was built for exactly that. It is indeed used in microservices often, but that is not a requirement.

- **"A Command must not return anything"** — strictly by the CQS principle (Command Query Separation) that is true. In practice `@nestjs/cqrs` does not restrict the return type, and `CommandHandler.execute()` often returns the created object or its id.

- **"CQRS and Event Sourcing are the same thing"** — no. CQRS separates the read and write models. Event Sourcing is a way of storing data as a sequence of events. CQRS without Event Sourcing works fine, and that is how most NestJS projects are built. Event Sourcing almost always requires CQRS, but not the other way round.

- **"EventHandler blocks the Command"** — no. `eventBus.publish()` publishes the event asynchronously, and the CommandHandler does not wait for the event handlers to finish. If you need a delivery guarantee, add retries inside the handler or push the work into a queue (BullMQ, Kafka).

- **"Sagas are needed for all events"** — no. A saga is for when one event has to trigger several commands in a coordinated way. A simple side effect such as sending an email is an EventHandler's job. A saga starts where the chain does: event A → command B → event C → command D.
