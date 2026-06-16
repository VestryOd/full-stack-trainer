# NestJS Advanced Interview Questions

## Группа 1: DI Container и Providers

**Q: Что происходит внутри NestFactory.create() при старте приложения?**

Nest выполняет несколько последовательных фаз: (1) рекурсивное сканирование всех `@Module()` деклараций, (2) построение dependency graph — топологический sort чтобы определить порядок инициализации, (3) инстанцирование всех провайдеров Singleton scope начиная с листьев графа, (4) вызов `onModuleInit()` хуков, (5) запуск HTTP адаптера (Express/Fastify). Если есть circular dependency без `forwardRef()` — ошибка на этапе построения графа.

**Q: Чем `InjectionToken<T>` лучше строковых токенов?**

```typescript
// Строковый токен — нет type safety
{ provide: 'DATABASE_URL', useValue: 'postgres://...' }
// Инжекция: @Inject('DATABASE_URL') url: string — компилятор не проверяет тип

// InjectionToken<T> — полная type safety
const DATABASE_URL = new InjectionToken<string>('DATABASE_URL');
{ provide: DATABASE_URL, useValue: 'postgres://...' }
// Инжекция: @Inject(DATABASE_URL) url: string — компилятор проверяет что url: string

// Дополнительные плюсы:
// - Нет конфликтов имён между модулями (строки 'DB' могут совпасть)
// - IDE автокомплит
// - Токен сам является документацией через generic <T>
```

**Q: Когда useFactory нужен async?**

```typescript
// Когда провайдер требует async инициализации:
{
  provide: PrismaService,
  useFactory: async (config: ConfigService) => {
    const prisma = new PrismaClient({
      datasources: { db: { url: config.get('DATABASE_URL') } },
    });
    await prisma.$connect(); // async операция
    return prisma;
  },
  inject: [ConfigService],
}
// Nest ждёт resolve Promise перед тем как модуль станет доступен
// Это блокирует старт приложения — нормально для критических зависимостей (БД)
```

**Q: Что такое forwardRef() и когда он нужен?**

```typescript
// Circular dependency: A зависит от B, B зависит от A
// Без forwardRef — ошибка при построении графа (один из них undefined)
@Injectable()
export class UserService {
  constructor(
    @Inject(forwardRef(() => AuthService))
    private authService: AuthService,
  ) {}
}

@Injectable()
export class AuthService {
  constructor(
    @Inject(forwardRef(() => UserService))
    private userService: UserService,
  ) {}
}
// Лучшее решение: рефакторинг для устранения циклической зависимости
// forwardRef — workaround, признак архитектурной проблемы
```

---

## Группа 2: Decorators, Metadata, и Reflection

**Q: Как работает @Roles('admin') под капотом?**

```typescript
// @Roles использует Reflect Metadata API:
export const Roles = (...roles: string[]) => SetMetadata('roles', roles);
// SetMetadata — это: Reflect.defineMetadata('roles', roles, target/method)

// Guard читает metadata через Reflector:
@Injectable()
export class RolesGuard implements CanActivate {
  constructor(private reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    // getAllAndOverride: сначала проверить метод, потом класс
    const roles = this.reflector.getAllAndOverride<string[]>('roles', [
      context.getHandler(), // @Roles на методе (приоритет)
      context.getClass(),   // @Roles на классе (fallback)
    ]);

    if (!roles) return true; // нет @Roles — открытый endpoint

    const user = context.switchToHttp().getRequest().user;
    return roles.some(role => user?.roles?.includes(role));
  }
}
```

**Q: В чём разница между getAllAndOverride и getAllAndMerge?**

```typescript
// getAllAndOverride: приоритет метода над классом (один массив или undefined)
@Controller('admin')
@Roles('admin')          // класс: ['admin']
class AdminController {
  @Get()
  @Roles('superadmin')   // метод: ['superadmin']
  action() {}
}
// getAllAndOverride → ['superadmin'] (метод имеет приоритет)

// getAllAndMerge: объединить метод + класс (один массив)
// getAllAndMerge → ['superadmin', 'admin'] (объединение)

// Используй getAllAndOverride когда метод должен ПЕРЕОПРЕДЕЛЯТЬ класс (@Public)
// Используй getAllAndMerge когда метод ДОПОЛНЯЕТ класс (permissions)
```

**Q: Как работает applyDecorators и чем отличается от стека декораторов?**

```typescript
// Стек декораторов применяется снизу вверх (right-to-left в TypeScript):
@A
@B
@C
method() {}
// Порядок: C → B → A

// applyDecorators применяется сверху вниз (left-to-right):
const Combined = applyDecorators(A, B, C);
// Порядок: A → B → C

// Пример: API endpoint с auth + swagger
export const ApiEndpoint = (summary: string) =>
  applyDecorators(
    UseGuards(JwtAuthGuard),          // 1-й применяется к методу
    ApiOperation({ summary }),         // 2-й
    ApiBearerAuth(),                   // 3-й
    ApiUnauthorizedResponse({ description: 'Unauthorized' }),
  );

@Get()
@ApiEndpoint('Get all users')
findAll() {}
```

---

## Группа 3: Request Pipeline и его механизмы

**Q: Точный порядок выполнения в pipeline — можете нарисовать с ExceptionFilter?**

```txt
Incoming Request
      ↓
  Middleware           — Express-уровень, до Nest
      ↓
  ExceptionFilter      — обёртка вокруг всего что ниже
      ↓
  Guard                — авторизация (canActivate)
      ↓
  Interceptor (pre)    — код до next.handle()
      ↓
  Pipe                 — валидация/трансформация параметров
      ↓
  Controller/Handler   — бизнес-логика
      ↓
  Interceptor (post)   — операторы в .pipe() после next.handle()
      ↓
  ExceptionFilter      — перехват ошибок из Controller
      ↓
  Response
```

**Q: Почему next.handle() возвращает Observable, а не Promise?**

`next.handle()` создаёт "холодный" Observable — контроллер вызывается только при subscribe. Это позволяет Interceptor-у вернуть `of(cachedValue)` вместо `next.handle()` и контроллер вообще не вызывается. RxJS операторы (`map`, `tap`, `catchError`, `timeout`) дают компактный способ трансформировать поток ответа. Вернуть `firstValueFrom(next.handle())` тоже работает, но теряешь возможность применять операторы.

**Q: В чём разница APP_GUARD vs useGlobalGuards()?**

```typescript
// useGlobalGuards() в main.ts — ВНЕ DI контейнера
app.useGlobalGuards(new JwtAuthGuard()); // нельзя инжектировать Reflector!

// APP_GUARD в модуле — ЧЕРЕЗ DI, получает все инжекции
@Module({
  providers: [
    {
      provide: APP_GUARD,
      useClass: JwtAuthGuard, // Reflector инжектируется автоматически
    },
  ],
})
// Правило: если Guard/Pipe/Filter требует инжекции — использовать APP_*
```

---

## Группа 4: Scopes, Dynamic Modules, и Performance

**Q: Что такое scope bubble-up и почему это проблема?**

```typescript
// Если провайдер REQUEST-scoped — все его потребители тоже становятся REQUEST-scoped
@Injectable({ scope: Scope.REQUEST })
class RequestContextService {} // REQUEST

@Injectable()
class UserService {
  constructor(private ctx: RequestContextService) {}
  // ⚠️ Теперь тоже REQUEST (транзитивно)
}

@Injectable()
class OrderService {
  constructor(private users: UserService) {}
  // ⚠️ Тоже REQUEST (транзитивно)
}

// При 1000 RPS: 3 провайдера × 1000 = 3000 новых объектов/сек
// Решение: AsyncLocalStorage — Singleton сервис, данные в async контексте
// Нет scope propagation, нет GC overhead
```

**Q: Как реализовать Dynamic Module с registerAsync?**

```typescript
@Module({})
export class CacheModule {
  static register(options: CacheOptions): DynamicModule {
    return {
      module: CacheModule,
      providers: [
        { provide: CACHE_OPTIONS, useValue: options },
        CacheService,
      ],
      exports: [CacheService],
    };
  }

  static registerAsync(options: {
    imports?: any[];
    useFactory: (...args: any[]) => CacheOptions | Promise<CacheOptions>;
    inject?: any[];
  }): DynamicModule {
    return {
      module: CacheModule,
      imports: options.imports ?? [],
      providers: [
        {
          provide: CACHE_OPTIONS,
          useFactory: options.useFactory,
          inject: options.inject ?? [],
        },
        CacheService,
      ],
      exports: [CacheService],
    };
  }
}

// Использование: конфиг из ConfigService
CacheModule.registerAsync({
  imports: [ConfigModule],
  useFactory: (config: ConfigService) => ({
    ttl: config.get<number>('CACHE_TTL'),
    host: config.get('REDIS_HOST'),
  }),
  inject: [ConfigService],
})
```

---

## Группа 5: CQRS и микросервисы

**Q: Когда CQRS оправдан, а когда это over-engineering?**

```txt
CQRS нужен:                        CQRS НЕ нужен:
─────────────────────────────────────────────────────
Сложный domain (DDD)               Simple CRUD
Разные read/write нагрузки         Admin Panel, CMS
Event-driven side effects          MVP/прототип
Нужен audit trail                  Команда < 5 человек
Микросервисная архитектура

Признаки перегруженного Service (пора CQRS):
  >10 методов, читающих и пишущих вперемешку
  Методы делают и бизнес-логику и side effects
  Сложно тестировать (много зависимостей в одном сервисе)
```

**Q: Как CommandHandler.execute() может вернуть данные, если CQRS говорит что Command void?**

Принцип CQS Бертрана Мейера — академический. На практике возвращать ID созданной сущности из CommandHandler — нормально и удобно. `@nestjs/cqrs` не ограничивает тип возвращаемого значения. Важно не возвращать данные для чтения (для этого Query) — но созданный `{ id }` — это результат мутации, не query результат.

**Q: В чём разница TCP, RabbitMQ и Kafka как транспортов в NestJS?**

```txt
TCP:       Прямое соединение, нет очередей, нет retry.
           Подходит для: разработка, демо, синхронные вызовы.

RabbitMQ:  Очереди с acknowledgement, dead-letter, retry, routing.
           Подходит для: task queues, надёжная доставка.
           Сообщения хранятся до acknowledgement.

Kafka:     Партиционированный log, consumer groups, retention.
           Подходит для: event streaming, analytics, высокий throughput.
           Сообщения хранятся определённый период (retention policy).

gRPC:      Бинарный протокол (protobuf), строгий контракт через .proto.
           Подходит для: внутренние inter-service вызовы, низкая latency.
```

---

## Группа 6: Архитектурные решения и best practices

**Q: Как правильно реализовать multi-tenancy в NestJS без REQUEST scope?**

```typescript
// Плохо: REQUEST scope для каждого запроса создаёт новый PrismaClient
@Injectable({ scope: Scope.REQUEST })
class TenantDatabaseService {
  // Новый PrismaClient на каждый запрос — GC nightmare
}

// Хорошо: connection pool per tenant + AsyncLocalStorage
@Injectable()
class TenantService {
  private pools = new Map<string, PrismaClient>();

  async getClient(tenantId: string): Promise<PrismaClient> {
    if (!this.pools.has(tenantId)) {
      const client = new PrismaClient({
        datasources: { db: { url: await this.getTenantUrl(tenantId) } },
      });
      await client.$connect();
      this.pools.set(tenantId, client);
    }
    return this.pools.get(tenantId)!;
  }
}

// Middleware устанавливает tenantId в ALS
// Singleton сервисы читают tenantId из ALS, получают нужный pool
```

**Q: Что выбрать для глобального error handling — ExceptionFilter или Interceptor?**

```typescript
// ExceptionFilter — правильный выбор для error handling:
// - Перехватывает исключения брошенные на любом уровне pipeline
// - Имеет доступ к ArgumentsHost для HTTP/WS/RPC контекста
// - Стандартный Nest механизм, понятен другим разработчикам

// Interceptor с catchError — дополнение:
// - Трансформировать конкретные ошибки (Prisma → HTTP) в middleware слое
// - НЕ заменяет ExceptionFilter

// Правило: ExceptionFilter для форматирования ошибок,
//          Interceptor.catchError для трансформации внутренних ошибок в HTTP ошибки
@Catch()
export class AllExceptionsFilter implements ExceptionFilter {
  catch(exception: unknown, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const status = exception instanceof HttpException
      ? exception.getStatus()
      : HttpStatus.INTERNAL_SERVER_ERROR;

    ctx.getResponse().status(status).json({
      statusCode: status,
      timestamp: new Date().toISOString(),
      path: ctx.getRequest().url,
      message: exception instanceof Error ? exception.message : 'Internal error',
    });
  }
}
```

**Q: Как тестировать NestJS сервисы с DI?**

```typescript
// Unit test — моки через Jest
describe('UserService', () => {
  let service: UserService;
  let prisma: DeepMockProxy<PrismaService>;

  beforeEach(async () => {
    const module = await Test.createTestingModule({
      providers: [
        UserService,
        {
          provide: PrismaService,
          useValue: mockDeep<PrismaService>(), // jest-mock-extended
        },
      ],
    }).compile();

    service = module.get(UserService);
    prisma = module.get(PrismaService);
  });

  it('should find user by id', async () => {
    prisma.user.findUnique.mockResolvedValue({ id: '1', email: 'test@test.com' });
    const result = await service.findById('1');
    expect(result.email).toBe('test@test.com');
  });
});

// Integration test — реальная БД (PostgreSQL в Docker)
// @nestjs/testing + реальный PrismaService
// beforeEach: transaction → rollback для изоляции тестов
```
