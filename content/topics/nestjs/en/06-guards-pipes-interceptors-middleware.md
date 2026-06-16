# Guards, Pipes, Interceptors, Middleware

## The full NestJS request pipeline

```txt
Incoming Request
      ↓
  Middleware        — Express/Fastify level, no Nest context
      ↓
  ExceptionFilter   — exception catching (outer wrapper)
      ↓
  Guard             — authorization: allow or reject
      ↓
  Interceptor (pre) — before next.handle()
      ↓
  Pipe              — transform and validate incoming data
      ↓
  Controller Method — business logic
      ↓
  Interceptor (post)— after next.handle() via .pipe()
      ↓
  ExceptionFilter   — exception catching from Controller
      ↓
  Response
```

## Middleware — HTTP level, before Nest

```typescript
// Middleware — Express-compatible, unaware of the Nest pipeline
@Injectable()
export class RequestIdMiddleware implements NestMiddleware {
  use(req: Request, res: Response, next: NextFunction) {
    // No access to Handler, Controller, or metadata
    req['requestId'] = crypto.randomUUID();
    res.setHeader('X-Request-ID', req['requestId']);

    next(); // required! otherwise the request hangs
  }
}

// Registration in Module:
@Module({})
export class AppModule implements NestModule {
  configure(consumer: MiddlewareConsumer) {
    consumer
      .apply(RequestIdMiddleware, CorsMiddleware)
      .forRoutes('*'); // or { path: 'users', method: RequestMethod.ALL }
  }
}

// When to use Middleware:
// ✓ CORS, rate limiting (express-rate-limit), helmet
// ✓ Request logging without knowing the Handler
// ✓ Request ID generation
// ✓ Cookie parsing, compression
// ✗ NOT for authorization — no access to Handler metadata (@Public, @Roles)
```

## Guard — authorization and access control

```typescript
// Guard: return true = allow, false/throw = reject (403)
@Injectable()
export class JwtAuthGuard extends AuthGuard('jwt') {
  constructor(private reflector: Reflector) {
    super();
  }

  canActivate(context: ExecutionContext): boolean | Promise<boolean> | Observable<boolean> {
    // Access metadata via Reflector
    const isPublic = this.reflector.getAllAndOverride<boolean>('isPublic', [
      context.getHandler(),
      context.getClass(),
    ]);

    if (isPublic) return true;

    return super.canActivate(context); // verify JWT
  }
}

// Guard runs AFTER Middleware and has full Nest context
// Returns ForbiddenException (403) on false
// You can throw a custom exception: throw new UnauthorizedException()

// When to use Guard:
// ✓ JWT / session validation
// ✓ Role-based access control (@Roles)
// ✓ Resource ownership checks
// ✓ API key validation
// ✗ NOT for data transformation
```

## Pipe — validation and transformation of incoming data

```typescript
// Built-in Pipes:
// ParseIntPipe, ParseUUIDPipe, ParseBoolPipe, ParseArrayPipe
// DefaultValuePipe, ParseEnumPipe

@Get(':id')
findOne(@Param('id', ParseUUIDPipe) id: string) {
  // ParseUUIDPipe: '550e8400-...' → '550e8400-...' (valid UUID)
  // NOT a UUID → BadRequestException (400)
  return this.usersService.findOne(id);
}

// ValidationPipe — the most powerful Pipe
// In main.ts (globally):
app.useGlobalPipes(new ValidationPipe({
  whitelist: true,              // strip fields NOT in the DTO
  forbidNonWhitelisted: true,   // 400 if extra fields are present
  transform: true,              // auto-transform types (string → number)
  transformOptions: {
    enableImplicitConversion: true,
  },
}));

// DTO with class-validator:
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

// Pipe is applied separately to each parameter:
@Post()
create(
  @Body() dto: CreateUserDto,            // ValidationPipe applied to body
  @Param('id', ParseIntPipe) id: number, // ParseIntPipe applied to param
) {}

// When to use Pipe:
// ✓ Validate DTO (class-validator + ValidationPipe)
// ✓ Transform types (string → number, string → Date)
// ✓ Parse complex parameters
// ✗ NOT for authorization
// ✗ NOT for response transformation
```

## Exception Filters — catching and formatting errors

```typescript
// ExceptionFilter: catch any exception and format the response
@Catch(HttpException) // or @Catch() for all exceptions
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

// Apply globally:
app.useGlobalFilters(new HttpExceptionFilter());
// or via module:
{ provide: APP_FILTER, useClass: HttpExceptionFilter }

// When to use ExceptionFilter:
// ✓ Standardize the error format across the API
// ✓ Convert database/library errors to HTTP errors
// ✓ Log errors with context
// ✓ Hide internal details (stack trace) from the client
```

## Decision table — when to use what

```txt
Task                                      Mechanism
──────────────────────────────────────────────────────────────
JWT/Session validation                    Guard
Role-based access                         Guard + @Roles decorator
Resource ownership                        Guard
Validate request body                     ValidationPipe + DTO
Transform path/query params               ParseIntPipe, ParseUUIDPipe
Response wrapping { data, meta }          Interceptor (map)
Request/Response logging                  Interceptor (tap)
Caching responses                         Interceptor (switchMap)
Timeout handling                          Interceptor (timeout)
Error format standardization              ExceptionFilter
CORS, Helmet, compression                 Middleware
Request ID injection                      Middleware
Cookie parsing                            Middleware
```

## Common interview mistakes

- **"Guard and Middleware can do the same thing"** — no. Middleware has no access to the Nest ExecutionContext, Handler, or decorator metadata (`@Public`, `@Roles`). A Guard has access via `context.getHandler()` and Reflector. JWT validation in Middleware works technically, but you can't implement the `@Public()` pattern (no metadata access).

- **"Pipes are applied to the whole request at once"** — no. Pipes are applied to each parameter individually: `@Body()` → ValidationPipe, `@Param('id')` → ParseIntPipe, `@Query('page')` → ParseIntPipe. Different parameters can have different Pipes.

- **"ExceptionFilter is only needed for custom errors"** — no. A global ExceptionFilter is needed to: (1) standardize the error format for all HTTP responses; (2) convert database/library errors to HTTP errors; (3) log all errors with a stack trace. Without it, Nest uses its built-in filter, which returns a minimal JSON.

- **"The order is Pipe → Guard"** — no. The correct order is: Guard → Interceptor(pre) → Pipe → Controller. Pipe runs AFTER Guard because there is no point validating data if the user isn't authorized.

- **"useGlobalGuards/Pipes/Filters and APP_GUARD/PIPE/FILTER are the same thing"** — no. `useGlobal*` in `main.ts` is outside DI and cannot inject services. `APP_*` in a module goes through DI and can inject services. If a Guard/Pipe/Filter needs ConfigService or PrismaService — use `APP_*`.
