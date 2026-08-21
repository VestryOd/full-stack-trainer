# Guards, Pipes, Interceptors, Middleware

## Полный конвейер запроса в NestJS

Конвейер (pipeline) — это фиксированная последовательность шагов, через которые Nest прогоняет каждый входящий запрос. Порядок задан фреймворком, и от него зависит, какая проверка на каком шаге вообще возможна.

```txt
Incoming Request
      ↓
  Middleware        — Express/Fastify уровень, нет Nest контекста
      ↓
  ExceptionFilter   — перехват исключений (обёртка снаружи)
      ↓
  Guard             — авторизация: пропустить или отклонить
      ↓
  Interceptor (pre) — before next.handle()
      ↓
  Pipe              — трансформация и валидация входных данных
      ↓
  Controller Method — бизнес-логика
      ↓
  Interceptor (post)— после next.handle() через .pipe()
      ↓
  ExceptionFilter   — перехват исключений из Controller
      ↓
  Response
```

Дальше в статье — каждый шаг по отдельности: что он умеет и чего от него ждать не стоит.

## Middleware — уровень HTTP, до Nest

Middleware — функция, которая работает на уровне Express или Fastify, до того как Nest определил, какой контроллер обслужит запрос. У неё есть сырые `req` и `res`, но нет доступа ни к обработчику, ни к метаданным декораторов.

Отсюда правило. Middleware годится для сквозной обвязки: CORS (cross-origin resource sharing — правила доступа к API из браузера с другого домена), идентификатор запроса, разбор cookies. Для авторизации не годится: решение о доступе зависит от метаданных, а их здесь ещё нет.

```typescript
// Middleware — Express-совместимый, не знает о Nest pipeline
@Injectable()
export class RequestIdMiddleware implements NestMiddleware {
  use(req: Request, res: Response, next: NextFunction) {
    // Нет доступа к Handler, Controller, metadata
    req['requestId'] = crypto.randomUUID();
    res.setHeader('X-Request-ID', req['requestId']);

    next(); // обязательно! иначе запрос зависнет
  }
}

// Регистрация в Module:
@Module({})
export class AppModule implements NestModule {
  configure(consumer: MiddlewareConsumer) {
    consumer
      .apply(RequestIdMiddleware, CorsMiddleware)
      .forRoutes('*'); // или { path: 'users', method: RequestMethod.ALL }
  }
}

// Когда использовать Middleware:
// ✓ CORS, rate limiting (express-rate-limit), helmet
// ✓ Request logging без знания Handler
// ✓ Request ID генерация
// ✓ Парсинг cookies, сжатие (compression)
// ✗ НЕ для авторизации — нет доступа к Handler metadata (@Public, @Roles)
```

## Guard — авторизация и контроль доступа

Guard отвечает на один вопрос: пускать этот запрос дальше или нет. Метод `canActivate` вернул `true` — запрос идёт к контроллеру. Вернул `false` — Nest отвечает 403 Forbidden. Можно и выбросить своё исключение, например `UnauthorizedException`.

В отличие от middleware, Guard уже знает, какой обработчик выбран, и читает метаданные декораторов через `Reflector`. Поэтому приём с `@Public()` реализуется только на уровне Guard.

```typescript
// Guard: вернуть true = пропустить, false/throw = отклонить (403)
@Injectable()
export class JwtAuthGuard extends AuthGuard('jwt') {
  constructor(private reflector: Reflector) {
    super();
  }

  canActivate(context: ExecutionContext): boolean | Promise<boolean> | Observable<boolean> {
    // Доступ к metadata через Reflector
    const isPublic = this.reflector.getAllAndOverride<boolean>('isPublic', [
      context.getHandler(),
      context.getClass(),
    ]);

    if (isPublic) return true;

    return super.canActivate(context); // проверить JWT
  }
}

// Guard выполняется ПОСЛЕ Middleware, имеет полный Nest контекст
// Возвращает ForbiddenException (403) при false
// Можно бросить кастомный exception: throw new UnauthorizedException()

// Когда использовать Guard:
// ✓ JWT / session validation
// ✓ Role-based access control (@Roles)
// ✓ Resource ownership checks (владелец ли пользователь ресурса)
// ✓ API key validation
// ✗ НЕ для трансформации данных
```

В примере проверяется JWT (JSON Web Token) — подписанный токен, который клиент присылает в заголовке `Authorization`.

## Pipe — валидация и трансформация входных данных

Pipe стоит между запросом и аргументом метода: он проверяет значение и при необходимости преобразует его. Проверка не прошла — Pipe выбрасывает `BadRequestException` (400), и контроллер не вызывается.

Важно, что Pipe применяется к каждому параметру отдельно. Встроенные разбирают одиночное значение: `ParseIntPipe` — число, `ParseUUIDPipe` — UUID (universally unique identifier), идентификатор вида `550e8400-e29b-41d4-a716-446655440000`.

`ValidationPipe` работает крупнее: он проверяет весь объект по DTO (data transfer object) — классу, который описывает форму входящих данных и правила для каждого поля.

```typescript
// Встроенные Pipes:
// ParseIntPipe, ParseUUIDPipe, ParseBoolPipe, ParseArrayPipe
// DefaultValuePipe, ParseEnumPipe

@Get(':id')
findOne(@Param('id', ParseUUIDPipe) id: string) {
  // ParseUUIDPipe: '550e8400-...' → '550e8400-...' (валидный UUID)
  // НЕ UUID → BadRequestException (400)
  return this.usersService.findOne(id);
}

// ValidationPipe — самый мощный Pipe
// В main.ts (глобально):
app.useGlobalPipes(new ValidationPipe({
  whitelist: true,          // удалить поля НЕ из DTO
  forbidNonWhitelisted: true, // 400 если есть лишние поля (вместо тихого удаления)
  transform: true,           // автоматически трансформировать типы (string → number)
  transformOptions: {
    enableImplicitConversion: true,
  },
}));

// DTO с class-validator:
export class CreateUserDto {
  @IsEmail()
  email: string;

  @IsString()
  @MinLength(8)
  password: string;

  @IsOptional()
  @IsString()
  name?: string;
}

// Pipe выполняется ПО ОДНОМУ для каждого параметра:
@Post()
create(
  @Body() dto: CreateUserDto,        // ValidationPipe применяется к body
  @Param('id', ParseIntPipe) id: number, // ParseIntPipe к param
) {}

// Когда использовать Pipe:
// ✓ Валидация DTO (class-validator + ValidationPipe)
// ✓ Трансформация типов (string → number, string → Date)
// ✓ Парсинг сложных параметров
// ✗ НЕ для авторизации
// ✗ НЕ для трансформации ответа
```

## Exception Filters — перехват и форматирование ошибок

Exception Filter — последний рубеж: он превращает выброшенное исключение в ответ клиенту. Своего фильтра нет — работает встроенный, и клиент получает минимальный JSON без пути, времени и внутреннего кода ошибки.

`@Catch(HttpException)` ограничивает фильтр одним классом исключений, а пустой `@Catch()` ловит всё подряд. Внутри доступен `ArgumentsHost` — та же обёртка над контекстом, от которой наследует `ExecutionContext`, поэтому фильтр работает не только на HTTP.

```typescript
// ExceptionFilter: перехватить любое исключение и форматировать ответ
@Catch(HttpException) // или @Catch() для всех исключений
@Injectable()
export class HttpExceptionFilter implements ExceptionFilter {
  catch(exception: HttpException, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const response = ctx.getResponse<Response>();
    const request = ctx.getRequest<Request>();
    const status = exception.getStatus();

    response.status(status).json({
      statusCode: status,
      timestamp: new Date().toISOString(),
      path: request.url,
      message: exception.message,
    });
  }
}

// Применить глобально:
app.useGlobalFilters(new HttpExceptionFilter());
// или через модуль:
{ provide: APP_FILTER, useClass: HttpExceptionFilter }

// Когда использовать ExceptionFilter:
// ✓ Стандартизировать формат ошибок
// ✓ Перехватить Prisma ошибки → HTTP ошибки
// ✓ Логировать ошибки с контекстом
// ✓ Скрыть внутренние детали (stack trace) от клиента
```

## Что выбрать под конкретную задачу

Правило выбора короткое: посмотрите, что именно вы собираетесь трогать — доступ, вход, выход или формат ошибки.

| Задача | Механизм |
|---|---|
| Проверка JWT или сессии | Guard |
| Доступ по ролям | Guard + декоратор `@Roles` |
| Проверка, что ресурс принадлежит пользователю | Guard |
| Валидация тела запроса | `ValidationPipe` + DTO |
| Преобразование параметров пути и запроса | `ParseIntPipe`, `ParseUUIDPipe` |
| Обёртка ответа в `{ data, meta }` | Interceptor (`map`) |
| Логирование запросов и ответов | Interceptor (`tap`) |
| Кеширование ответов | Interceptor (`switchMap`) |
| Таймаут на запрос | Interceptor (`timeout`) |
| Единый формат ошибок | ExceptionFilter |
| CORS, Helmet, сжатие | Middleware |
| Проброс идентификатора запроса | Middleware |
| Разбор cookies | Middleware |

## Типичные ошибки на интервью

- **"Guard и Middleware могут делать одно и то же"** — нет. У middleware нет доступа ни к `ExecutionContext`, ни к обработчику, ни к метаданным декораторов (`@Public`, `@Roles`). У Guard доступ есть: через `context.getHandler()` и `Reflector`. Проверять токен в middleware технически можно, но приём с `@Public()` там не реализуется — метаданных ещё нет.

- **"Pipes применяются ко всему запросу сразу"** — нет, к каждому параметру отдельно: `@Body()` → `ValidationPipe`, `@Param('id')` → `ParseIntPipe`, `@Query('page')` → `ParseIntPipe`. У разных параметров могут быть разные Pipes.

- **"ExceptionFilter нужен только для кастомных ошибок"** — нет. Глобальный фильтр решает три задачи: единый формат всех ошибок API, перевод ошибок драйвера базы данных в HTTP-ошибки, логирование ошибок со стеком. Без него работает встроенный фильтр, который отдаёт минимальный JSON.

- **"Порядок такой: Pipe → Guard"** — наоборот. Правильный порядок: Guard → Interceptor (до) → Pipe → Controller. Pipe выполняется после Guard, потому что нет смысла валидировать данные того, кому доступ всё равно закрыт.

- **"Вызовы `useGlobal*` и токены `APP_*` — одно и то же"** — нет. Вызовы `useGlobal*` в `main.ts` создают объект вне контейнера внедрения зависимостей (DI), поэтому сервисы в него не инжектируются. Токены `APP_*` в модуле идут через контейнер, и зависимости приходят обычным способом. Нужен `ConfigService` или `PrismaService` внутри Guard, Pipe или Filter — берите форму с токеном.
