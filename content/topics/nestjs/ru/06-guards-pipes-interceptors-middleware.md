# Guards, Pipes, Interceptors, Middleware

## Полный pipeline запроса в NestJS

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

## Middleware — HTTP-уровень, до Nest

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

## Pipe — валидация и трансформация входных данных

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

## Сравнительная таблица — когда что использовать

```txt
Задача                            Механизм
─────────────────────────────────────────────────────────────
JWT/Session validation            Guard
Role-based access                 Guard + @Roles decorator
Resource ownership                Guard
Validate request body             ValidationPipe + DTO
Transform path/query params       ParseIntPipe, ParseUUIDPipe
Response wrapping { data, meta }  Interceptor (map)
Request/Response logging          Interceptor (tap)
Caching responses                 Interceptor (switchMap)
Timeout handling                  Interceptor (timeout)
Error format standardization      ExceptionFilter
CORS, Helmet, compression         Middleware
Request ID injection              Middleware
Cookie parsing                    Middleware
```

## Типичные ошибки на интервью

- **"Guard и Middleware могут делать одно и то же"** — нет. Middleware не имеет доступа к Nest ExecutionContext, Handler, metadata декораторов (`@Public`, `@Roles`). Guard имеет доступ через `context.getHandler()` и Reflector. JWT проверка в Middleware работает технически, но нельзя реализовать `@Public()` паттерн (нет metadata).

- **"Pipes применяются ко всему запросу сразу"** — нет. Pipes применяются к каждому параметру отдельно: `@Body()` → ValidationPipe, `@Param('id')` → ParseIntPipe, `@Query('page')` → ParseIntPipe. Разные параметры могут иметь разные Pipes.

- **"ExceptionFilter нужен только для кастомных ошибок"** — нет. Global ExceptionFilter нужен чтобы: (1) стандартизировать формат всех HTTP ошибок; (2) конвертировать database/library ошибки в HTTP ошибки; (3) логировать все ошибки с трейсом. Без ExceptionFilter Nest использует встроенный, который возвращает минимальный JSON.

- **"Порядок Pipe → Guard"** — нет. Правильно: Guard → Interceptor(pre) → Pipe → Controller. Pipe выполняется ПОСЛЕ Guard потому что нет смысла валидировать данные если пользователь не авторизован.

- **"useGlobalGuards/Pipes/Filters и APP_GUARD/PIPE/FILTER — одно и то же"** — нет. `useGlobal*` в `main.ts` — вне DI, нельзя инжектировать сервисы. `APP_*` в модуле — через DI, можно инжектировать. Если Guard/Pipe/Filter нужен ConfigService или PrismaService — используй `APP_*`.
