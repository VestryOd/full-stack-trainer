# Продвинутые вопросы по NestJS на интервью

## Группа 1: DI-контейнер и провайдеры

**Q: Что происходит внутри NestFactory.create() при старте приложения?**

Nest проходит пять фаз по порядку. Сначала собирает граф зависимостей и только потом поднимает сервер — отсюда правило, что ошибки конфигурации видны до первого запроса. DI дальше по тексту — dependency injection, внедрение зависимостей.

```txt
Фазы NestFactory.create():
  1. Рекурсивное сканирование всех объявлений @Module()
  2. Построение графа зависимостей → топологический порядок
  3. Создание Singleton-провайдеров, от листьев графа
  4. Вызов хуков onModuleInit()
  5. Запуск HTTP-адаптера (Express или Fastify)
```

Циклическая зависимость без `forwardRef()` ломает вторую фазу. Ошибка приходит на этапе построения графа, то есть до того, как сервер начал слушать порт.

**Q: Чем `InjectionToken<T>` лучше строковых токенов?**

Строковый токен не несёт типа: компилятор не знает, что лежит за `'DATABASE_URL'`, и опечатку в имени не поймает. Типизированный токен хранит тип значения в себе, поэтому тип на инъекции проверяется.

Второй плюс — уникальность. Две строки `'DB'` из разных модулей случайно совпадут и перезапишут друг друга, а два отдельных токена — нет.

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

Когда значение нельзя получить одним вызовом конструктора: надо открыть соединение, прочитать секрет, дождаться ответа сети. Фабрика возвращает промис, и Nest ждёт его до того, как отдаст модуль остальным.

Старт приложения при этом блокируется. Для критичных зависимостей вроде базы данных это правильное поведение: лучше не подняться совсем, чем подняться без базы.

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
// Это блокирует старт приложения — нормально для критических зависимостей
```

**Q: Что такое forwardRef() и когда он нужен?**

`forwardRef(() => Class)` откладывает вычисление ссылки на класс до момента, когда оба класса уже загружены. Нужен он при циклической зависимости: `A` просит в конструкторе `B`, а `B` просит `A`.

Без отложенной ссылки один из аргументов приезжает как `undefined`. Но лечит `forwardRef` симптом, а не причину: цикл почти всегда означает, что общую логику пора вынести в третий сервис.

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

## Группа 2: декораторы, метаданные и рефлексия

**Q: Как работает @Roles('admin') под капотом?**

Декоратор ничего не проверяет — он только пишет метаданные. `SetMetadata('roles', roles)` под капотом вызывает `Reflect.defineMetadata` и привязывает массив ролей к методу или к классу контроллера.

Проверку делает Guard. Он читает те же метаданные через `Reflector` и сравнивает их с ролями пользователя. Метаданных нет — значит ограничений нет, и эндпоинт открыт.

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

Оба метода читают одни и те же метаданные с двух уровней — метода и класса. Разница в том, как они собирают результат. `getAllAndOverride` берёт значение метода, если оно есть, иначе значение класса. `getAllAndMerge` объединяет оба массива в один.

Правило выбора простое. `getAllAndOverride` — когда метод переопределяет класс, как `@Public()` внутри защищённого контроллера. `getAllAndMerge` — когда права складываются.

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

`applyDecorators(A, B, C)` применяет декораторы в порядке записи: A → B → C. Стек `@A @B @C` над тем же методом TypeScript применяет снизу вверх: C → B → A.

Отсюда практическая польза. Набор, собранный через `applyDecorators`, ведёт себя предсказуемо и переиспользуется как один декоратор.

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

## Группа 3: конвейер запроса и его механизмы

**Q: Точный порядок выполнения в конвейере — можете нарисовать вместе с ExceptionFilter?**

Порядок фиксированный, и ExceptionFilter стоит в нём дважды. Он оборачивает всё, что ниже, поэтому перехватывает исключения и из Guard, и из Pipe, и из контроллера.

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

`next.handle()` создаёт «холодный» Observable: контроллер вызывается только при подписке. Это и даёт Interceptor-у возможность вернуть `of(cachedValue)` вместо `next.handle()` — тогда контроллер не выполнится вообще.

Вторая причина — операторы. `map`, `tap`, `catchError`, `timeout` дают компактный способ обработать поток ответа. Написать `firstValueFrom(next.handle())` можно, но операторы после этого недоступны.

```typescript
// Одна строка решает, вызывать контроллер или нет:
return cached ? of(cached) : next.handle();
```

**Q: В чём разница APP_GUARD и useGlobalGuards()?**

Разница в доступе к контейнеру. `useGlobalGuards()` в `main.ts` получает готовый объект, созданный через `new`, поэтому инжектировать в него `Reflector` или `ConfigService` нельзя.

Токен `APP_GUARD` регистрирует Guard как обычный провайдер модуля. Экземпляр создаёт контейнер, и зависимости приходят сами.

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

## Группа 4: области видимости, динамические модули и производительность

**Q: Что такое scope bubble-up и почему это проблема?**

Всплытие области видимости (scope bubble-up) — это когда REQUEST-провайдер превращает в REQUEST-провайдеров всех, кто от него зависит. Дальше эффект идёт по цепочке транзитивно, и Nest об этом не предупреждает.

Проблема в объёме работы. При 1000 RPS (requests per second — запросов в секунду) и цепочке из трёх провайдеров получается 3000 новых объектов в секунду, и все они достаются сборщику мусора.

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
// Нет scope propagation, нет нагрузки на сборщик мусора
```

**Q: Как реализовать Dynamic Module с registerAsync?**

Оба метода возвращают один и тот же объект `DynamicModule`, и отличаются они только способом получить опции. Простой `register` кладёт готовые опции через `useValue`. Асинхронная версия кладёт их через `useFactory` вместе со списком `inject`, поэтому опции можно взять из `ConfigService`.

Всё остальное в объекте совпадает: тот же `module`, те же провайдеры, тот же `exports`.

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

**Q: Когда CQRS оправдан, а когда это избыточное усложнение?**

CQRS (Command Query Responsibility Segregation — разделение ответственности за команды и запросы) окупается там, где чтение и запись действительно разошлись: своя модель, своя нагрузка, свои побочные эффекты. На простом наборе операций над записями он добавляет файлы и не добавляет пользы.

В таблице три сокращения. DDD (domain-driven design) — проектирование от предметной области. CRUD (create, read, update, delete) — четыре базовые операции над записью. MVP (minimum viable product) — минимальная версия продукта.

| Нужен CQRS | Не нужен CQRS |
|---|---|
| Сложный домен, спроектированный по DDD | Простой CRUD |
| Разные нагрузки на чтение и запись | Админка, система управления контентом |
| Побочные эффекты через события | MVP или прототип |
| Нужна полная история изменений | Команда меньше пяти человек |
| Микросервисная архитектура | |

Признаки перегруженного сервиса, которому пора разделиться:

- Больше десяти методов, и чтение с записью перемешаны.
- Методы делают и бизнес-логику, и побочные эффекты.
- Сервис трудно тестировать: слишком много зависимостей в одном классе.

**Q: Как CommandHandler.execute() может вернуть данные, если CQRS говорит, что Command ничего не возвращает?**

Строгий запрет идёт из принципа CQS (Command Query Separation — разделение команд и запросов) Бертрана Мейера, и он академический. `@nestjs/cqrs` тип возвращаемого значения не ограничивает.

На практике вернуть идентификатор созданной сущности из обработчика команды — нормально и удобно. Важно другое: не возвращать из команды данные для чтения, для этого есть запрос. Созданный `{ id }` — результат мутации, а не результат чтения.

```typescript
// Так делать можно: возвращается результат мутации, а не выборка
async execute(cmd: CreateUserCommand): Promise<{ id: string }> {
  const user = await this.prisma.user.create({ data: { ...cmd } });
  return { id: user.id };
}
```

**Q: В чём разница TCP, RabbitMQ и Kafka как транспортов в NestJS?**

TCP (transmission control protocol) — это прямое соединение: ни очередей, ни повторов. RabbitMQ и Kafka ставят между сервисами посредника, и он сообщение не потеряет. То есть разница между тремя транспортами — в гарантии доставки.

Хранят сообщения посредники по-разному. RabbitMQ держит сообщение в очереди до подтверждения от потребителя. Kafka хранит его заданный срок (retention policy) независимо от того, прочитал его кто-нибудь или нет.

| Транспорт | Что это | Для чего подходит |
|---|---|---|
| TCP | Прямое соединение, нет очередей и повторов | Разработка, демо, синхронные вызовы |
| RabbitMQ | Очереди с подтверждением, повторы, маршрутизация, недоставленные сообщения | Очереди задач, надёжная доставка |
| Kafka | Партиционированный журнал, группы потребителей, хранение истории | Поток событий, аналитика, высокая пропускная способность |
| gRPC | Бинарный протокол (Protocol Buffers), строгий контракт в файле `.proto` | Внутренние вызовы между сервисами, низкие задержки |

---

## Группа 6: архитектурные решения и практики

**Q: Как правильно реализовать мультитенантность в NestJS без REQUEST scope?**

Держите пул соединений на каждого клиента (tenant) в обычном Singleton-сервисе и берите оттуда готовый клиент по идентификатору. Идентификатор при этом кладут в `AsyncLocalStorage`, а не тащат через параметры каждого метода.

Плохой вариант — REQUEST-провайдер с новым `PrismaClient`: на каждый запрос создаётся новое соединение, и это постоянная нагрузка на сборщик мусора.

```typescript
// Плохо: REQUEST scope для каждого запроса создаёт новый PrismaClient
@Injectable({ scope: Scope.REQUEST })
class TenantDatabaseService {
  // Новый PrismaClient на каждый запрос — кошмар для сборщика мусора
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

// Middleware устанавливает tenantId в AsyncLocalStorage
// Singleton сервисы читают tenantId оттуда и получают нужный pool
```

**Q: Что выбрать для глобальной обработки ошибок — ExceptionFilter или Interceptor?**

ExceptionFilter. Он перехватывает исключения с любого уровня конвейера, получает `ArgumentsHost` и поэтому работает и для HTTP, и для WebSocket, и для сообщений микросервисов. Это стандартный механизм Nest, и он понятен любому, кто читает ваш код.

Interceptor с `catchError` — дополнение, а не замена. Его задача узкая: перевести конкретные внутренние ошибки в HTTP-исключения, например коды Prisma.

```typescript
// ExceptionFilter — правильный выбор для error handling:
// - Перехватывает исключения брошенные на любом уровне pipeline
// - Имеет доступ к ArgumentsHost для HTTP/WS/RPC контекста
// - Стандартный Nest механизм, понятен другим разработчикам

// Interceptor с catchError — дополнение:
// - Трансформировать конкретные ошибки (Prisma → HTTP)
// - НЕ заменяет ExceptionFilter

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

**Q: Как тестировать NestJS сервисы с внедрением зависимостей?**

Через `Test.createTestingModule` из `@nestjs/testing`: вы объявляете тот же список провайдеров, но настоящие зависимости подменяете моками через `useValue`. Дальше `module.get(UserService)` отдаёт экземпляр, собранный контейнером.

Интеграционные тесты идут с настоящей базой в Docker и настоящим `PrismaService`. Изоляцию между тестами держат транзакцией: открыть в `beforeEach`, откатить после теста.

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

// Integration test — реальная база данных (PostgreSQL в Docker)
// @nestjs/testing + реальный PrismaService
// beforeEach: transaction → rollback для изоляции тестов
```
