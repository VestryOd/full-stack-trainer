# Guards, Pipes, Interceptors, Middleware

## The full NestJS request pipeline

The pipeline is a fixed sequence of steps that every incoming request goes through. The order is set by the framework, and it decides which check is even possible at which step.

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

The rest of the article takes the steps one at a time: what each one can do, and what you should not expect from it.

## Middleware — the HTTP level, before Nest

Middleware is a function that runs at the Express or Fastify level, before Nest has decided which controller will serve the request. It has the raw `req` and `res`, but no access to the handler or to decorator metadata.

That sets the rule. Middleware is right for the cross-cutting basics: CORS, a request id, cookie parsing. CORS (cross-origin resource sharing) is the set of rules for calling your API from a browser on another domain.

Middleware is wrong for authorization: that decision depends on metadata, and the metadata is not available yet.

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

A Guard answers one question: does this request go further or not. `canActivate` returns `true` and the request reaches the controller. It returns `false` and Nest replies 403 Forbidden. You can also throw your own exception, such as `UnauthorizedException`.

Unlike middleware, a Guard already knows which handler was selected, and it reads decorator metadata through `Reflector`. That is why the `@Public()` pattern can only be built at the Guard level.

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

The example checks a JWT (JSON Web Token) — a signed token the client sends in the `Authorization` header.

## Pipe — validation and transformation of incoming data

A Pipe sits between the request and the method argument: it checks the value and converts it when needed. If the check fails, the Pipe throws a `BadRequestException` (400) and the controller is never called.

The important part is that a Pipe is applied to each parameter separately. The built-in ones handle a single value: `ParseIntPipe` a number, `ParseUUIDPipe` a UUID (universally unique identifier) — an id shaped like `550e8400-e29b-41d4-a716-446655440000`.

`ValidationPipe` works at a larger scale: it checks a whole object against a DTO. DTO stands for data transfer object — the class that describes the shape of the incoming data and the rules for each field.

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

An Exception Filter is the last line: it turns a thrown exception into a response for the client. With no filter of your own, the built-in one runs. The client then gets a minimal JSON: no path, no timestamp, no internal error code.

`@Catch(HttpException)` limits the filter to one exception class, while an empty `@Catch()` catches everything. Inside you get `ArgumentsHost` — the same context wrapper that `ExecutionContext` inherits from, which is why a filter works beyond HTTP too.

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

## Which one to pick for a given task

The rule is short: look at what you are about to touch — access, the input, the output, or the error format.

| Task | Mechanism |
|---|---|
| JWT or session validation | Guard |
| Role-based access | Guard + the `@Roles` decorator |
| Checking that the resource belongs to the user | Guard |
| Validating the request body | `ValidationPipe` + DTO |
| Converting path and query parameters | `ParseIntPipe`, `ParseUUIDPipe` |
| Wrapping the response in `{ data, meta }` | Interceptor (`map`) |
| Request and response logging | Interceptor (`tap`) |
| Caching responses | Interceptor (`switchMap`) |
| Putting a timeout on a request | Interceptor (`timeout`) |
| One error format everywhere | ExceptionFilter |
| CORS, Helmet, compression | Middleware |
| Passing a request id through | Middleware |
| Cookie parsing | Middleware |

## Common interview mistakes

- **"Guard and Middleware can do the same thing"** — no. Middleware has no access to `ExecutionContext`, to the handler, or to decorator metadata (`@Public`, `@Roles`). A Guard has all of it, through `context.getHandler()` and `Reflector`. Checking a token in middleware is technically possible, but the `@Public()` pattern is not: the metadata does not exist yet.

- **"Pipes are applied to the whole request at once"** — no, to each parameter separately: `@Body()` → `ValidationPipe`, `@Param('id')` → `ParseIntPipe`, `@Query('page')` → `ParseIntPipe`. Different parameters can have different Pipes.

- **"ExceptionFilter is only needed for custom errors"** — no. A global filter does three jobs. It gives one error format across the API. It translates database driver errors into HTTP errors. And it logs every error with its stack. Without it the built-in filter runs and returns a minimal JSON.

- **"The order is Pipe → Guard"** — it is the other way round. The correct order is Guard → Interceptor (pre) → Pipe → Controller. A Pipe runs after a Guard, because there is no point validating data for someone who has no access anyway.

- **"The `useGlobal*` calls and the `APP_*` tokens are the same thing"** — no. The `useGlobal*` calls in `main.ts` build the object outside the dependency injection (DI) container, so no services can be injected into it. The `APP_*` tokens in a module go through the container, and dependencies arrive the usual way. If your Guard, Pipe or Filter needs `ConfigService` or `PrismaService`, use the token form.
