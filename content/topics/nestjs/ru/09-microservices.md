# NestJS Microservices

## Транспорты и паттерны взаимодействия

NestJS abstracts communication за унифицированным API — один и тот же код работает с TCP, RabbitMQ, Kafka и gRPC. Ключевые паттерны: `@MessagePattern` (request/response, ждём ответа) и `@EventPattern` (fire-and-forget, ответа нет).

```typescript
// Сервер (User Service) — обрабатывает входящие сообщения
import { Controller } from '@nestjs/common';
import { MessagePattern, EventPattern, Payload } from '@nestjs/microservices';

@Controller()
export class UsersController {
  constructor(private usersService: UsersService) {}

  // Request/Response — клиент ждёт ответа
  @MessagePattern('user.find')
  async findUser(@Payload() data: { id: string }) {
    return this.usersService.findById(data.id);
  }

  // Fire-and-forget — клиент не ждёт ответа
  @EventPattern('user.created')
  async handleUserCreated(@Payload() data: { userId: string; email: string }) {
    await this.usersService.processNewUser(data);
  }
}

// Запуск как microservice (вместо HTTP сервера):
// main.ts
async function bootstrap() {
  const app = await NestFactory.createMicroservice<MicroserviceOptions>(AppModule, {
    transport: Transport.TCP,
    options: { host: '0.0.0.0', port: 3001 },
  });
  await app.listen();
}
```

## ClientProxy — отправка сообщений другому сервису

```typescript
// Клиент (Order Service) — отправляет сообщения в User Service
@Module({
  imports: [
    ClientsModule.register([
      {
        name: 'USER_SERVICE',
        transport: Transport.TCP,
        options: { host: 'user-service', port: 3001 },
      },
    ]),
  ],
})
export class OrdersModule {}

@Injectable()
export class OrdersService {
  constructor(
    @Inject('USER_SERVICE') private readonly userClient: ClientProxy,
  ) {}

  async createOrder(userId: string, items: OrderItem[]) {
    // send() — Request/Response, возвращает Observable
    // firstValueFrom() конвертирует в Promise
    const user = await firstValueFrom(
      this.userClient.send<UserDto>('user.find', { id: userId }),
    );

    if (!user) throw new NotFoundException('User not found');

    const order = await this.ordersRepo.create({ userId, items });

    // emit() — Fire-and-forget, не ждём ответа
    this.userClient.emit('order.created', {
      orderId: order.id,
      userId,
      total: order.total,
    });

    return order;
  }
}

// send vs emit:
// send('pattern', data) → Request/Response → Observable<T> (нужен firstValueFrom)
// emit('pattern', data) → Fire-and-forget → Observable<void> (не нужно subscribing)
```

## Транспорты: TCP vs RabbitMQ vs Kafka vs gRPC

```typescript
// TCP — самый простой, для разработки и демо
// Прямое соединение, нет буферизации, нет retry
{
  transport: Transport.TCP,
  options: { host: 'localhost', port: 3001 },
}

// RabbitMQ — production message queue
// Queues, acknowledgement, retry, dead-letter exchange
{
  transport: Transport.RMQ,
  options: {
    urls: ['amqp://user:pass@rabbitmq:5672'],
    queue: 'user_queue',
    queueOptions: { durable: true }, // сохранять очередь при рестарте
    noAck: false, // требовать acknowledgement
  },
}

// Kafka — high-throughput event streaming
// Партиции, consumer groups, retention (хранение истории событий)
{
  transport: Transport.KAFKA,
  options: {
    client: { brokers: ['kafka:9092'] },
    consumer: { groupId: 'order-service' }, // consumer group — для масштабирования
  },
}

// gRPC — Protocol Buffers, бинарный протокол, типизированный контракт
// Быстрее REST, строгий контракт через .proto файл
{
  transport: Transport.GRPC,
  options: {
    package: 'user',
    protoPath: join(__dirname, 'user.proto'),
    url: '0.0.0.0:5000',
  },
}
```

## Гибридное приложение — HTTP + Microservice в одном процессе

```typescript
// Один NestJS процесс слушает и HTTP (для внешних клиентов) и TCP/RMQ (для других сервисов)
async function bootstrap() {
  // HTTP сервер (основной)
  const app = await NestFactory.create(AppModule);

  // Добавить microservice transport
  app.connectMicroservice<MicroserviceOptions>({
    transport: Transport.RMQ,
    options: {
      urls: ['amqp://rabbitmq:5672'],
      queue: 'user_queue',
    },
  });

  // Запустить оба
  await app.startAllMicroservices();
  await app.listen(3000);
}

// Контроллер теперь обрабатывает ОБА типа запросов:
@Controller('users')
export class UsersController {
  @Get(':id')                              // HTTP GET /users/:id
  findOne(@Param('id') id: string) { ... }

  @MessagePattern('user.find')            // Microservice message
  findByMessage(@Payload() data: { id: string }) { ... }
}
```

## Distributed Transactions — Saga Pattern

```typescript
// Проблема: транзакция между несколькими сервисами
// БД транзакций нет — каждый сервис имеет свою БД
// Решение: Saga с compensating actions

// Choreography-based Saga (event-driven):
// Order Service:
@EventsHandler(OrderCreatedEvent)
export class OrderCreatedHandler {
  constructor(@Inject('PAYMENT_SERVICE') private paymentClient: ClientProxy) {}

  async handle(event: OrderCreatedEvent) {
    // Step 2: попросить Payment Service списать деньги
    this.paymentClient.emit('payment.process', {
      orderId: event.orderId,
      amount: event.total,
      userId: event.userId,
    });
  }
}

// Payment Service:
@EventPattern('payment.process')
async processPayment(@Payload() data: PaymentDto) {
  try {
    await this.paymentsService.charge(data);
    this.orderClient.emit('payment.succeeded', { orderId: data.orderId });
  } catch (error) {
    // Compensating action — отменить заказ
    this.orderClient.emit('payment.failed', {
      orderId: data.orderId,
      reason: error.message,
    });
  }
}

// Order Service — compensating action:
@EventPattern('payment.failed')
async handlePaymentFailed(@Payload() data: { orderId: string; reason: string }) {
  await this.ordersService.cancel(data.orderId, data.reason);
}

// Orchestration-based Saga — центральный orchestrator координирует шаги
// Сложнее, но проще для дебаггинга — все шаги в одном месте
```

## Observability в микросервисах

```typescript
// Correlation ID — отслеживать запрос через все сервисы
@Injectable()
export class CorrelationIdInterceptor implements NestInterceptor {
  intercept(context: ExecutionContext, next: CallHandler) {
    const rpcContext = context.switchToRpc();
    const data = rpcContext.getData();

    // Передавать correlationId в каждом сообщении
    const correlationId = data?.correlationId ?? crypto.randomUUID();

    // Логировать с correlationId
    Logger.log(`Processing message`, { correlationId });

    return next.handle();
  }
}

// Паттерн: всегда включать в payload:
interface BaseMessage {
  correlationId: string;  // трассировка через сервисы
  timestamp: string;      // когда событие произошло
  version: string;        // версия формата сообщения
}

// Circuit Breaker — защита от каскадных отказов
// Библиотека: @nestjs/terminus + opossum или resilience4ts
// При 50% ошибок за 30 сек — "открыть" circuit (быстро возвращать ошибку)
// После timeout — "полуоткрыть" (попробовать один запрос)
```

## Типичные ошибки на интервью

- **"Микросервисы лучше монолита"** — нет. Микросервисы добавляют: сетевые задержки, eventual consistency, сложность distributed tracing, overhead на инфраструктуру. Для большинства стартапов и CRUD приложений монолит быстрее в разработке и дешевле в эксплуатации. "Monolith first" — рекомендация Мартина Фаулера.

- **"send() возвращает Promise"** — нет. `clientProxy.send()` возвращает `Observable`. Чтобы получить значение в async/await коде: `await firstValueFrom(this.client.send(...))`. Не вызывать `.subscribe()` вручную — это приведёт к утечкам памяти.

- **"EventPattern и MessagePattern делают одно и то же"** — нет. `@MessagePattern` ожидает ответ от handler — для request/response взаимодействия. `@EventPattern` не возвращает ответ — fire-and-forget, для событий. На стороне клиента: `send()` для MessagePattern, `emit()` для EventPattern.

- **"TCP transport подходит для production"** — нет. TCP в NestJS — прямое соединение без очередей, буферизации, retry, dead-letter. При рестарте сервиса сообщения теряются. Production: RabbitMQ (надёжная доставка), Kafka (высокий throughput + retention), gRPC (строгий контракт).

- **"Distributed transaction = BEGIN/COMMIT между сервисами"** — невозможно. Каждый сервис имеет свою БД. Решение: Saga pattern с compensating actions. Результат: eventual consistency, а не strict consistency. Это trade-off микросервисной архитектуры — важно явно это понимать и объяснить интервьюеру.
