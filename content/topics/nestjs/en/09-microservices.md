# NestJS Microservices

## Transports and communication patterns

NestJS abstracts communication behind a unified API — the same code works with TCP, RabbitMQ, Kafka, and gRPC. Key patterns: `@MessagePattern` (request/response, waits for a reply) and `@EventPattern` (fire-and-forget, no reply).

```typescript
// Server (User Service) — handles incoming messages
import { Controller } from '@nestjs/common';
import { MessagePattern, EventPattern, Payload } from '@nestjs/microservices';

@Controller()
export class UsersController {
  constructor(private usersService: UsersService) {}

  // Request/Response — client waits for a reply
  @MessagePattern('user.find')
  async findUser(@Payload() data: { id: string }) {
    return this.usersService.findById(data.id);
  }

  // Fire-and-forget — client does not wait for a reply
  @EventPattern('user.created')
  async handleUserCreated(@Payload() data: { userId: string; email: string }) {
    await this.usersService.processNewUser(data);
  }
}

// Start as a microservice (instead of an HTTP server):
// main.ts
async function bootstrap() {
  const app = await NestFactory.createMicroservice<MicroserviceOptions>(AppModule, {
    transport: Transport.TCP,
    options: { host: '0.0.0.0', port: 3001 },
  });
  await app.listen();
}
```

## ClientProxy — sending messages to another service

```typescript
// Client (Order Service) — sends messages to User Service
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
    // send() — Request/Response, returns Observable
    // firstValueFrom() converts to Promise
    const user = await firstValueFrom(
      this.userClient.send<UserDto>('user.find', { id: userId }),
    );

    if (!user) throw new NotFoundException('User not found');

    const order = await this.ordersRepo.create({ userId, items });

    // emit() — Fire-and-forget, no waiting for reply
    this.userClient.emit('order.created', {
      orderId: order.id,
      userId,
      total: order.total,
    });

    return order;
  }
}

// send vs emit:
// send('pattern', data) → Request/Response → Observable<T> (use firstValueFrom)
// emit('pattern', data) → Fire-and-forget → Observable<void> (no subscribing needed)
```

## Transports: TCP vs RabbitMQ vs Kafka vs gRPC

```typescript
// TCP — simplest, for development and demos
// Direct connection, no buffering, no retry
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
    queueOptions: { durable: true }, // persist queue across restarts
    noAck: false, // require acknowledgement
  },
}

// Kafka — high-throughput event streaming
// Partitions, consumer groups, retention (storing event history)
{
  transport: Transport.KAFKA,
  options: {
    client: { brokers: ['kafka:9092'] },
    consumer: { groupId: 'order-service' }, // consumer group — for scaling
  },
}

// gRPC — Protocol Buffers, binary protocol, typed contract
// Faster than REST, strict contract via .proto file
{
  transport: Transport.GRPC,
  options: {
    package: 'user',
    protoPath: join(__dirname, 'user.proto'),
    url: '0.0.0.0:5000',
  },
}
```

## Hybrid app — HTTP + Microservice in one process

```typescript
// One NestJS process listens on both HTTP (for external clients) and TCP/RMQ (for other services)
async function bootstrap() {
  // HTTP server (primary)
  const app = await NestFactory.create(AppModule);

  // Add microservice transport
  app.connectMicroservice<MicroserviceOptions>({
    transport: Transport.RMQ,
    options: {
      urls: ['amqp://rabbitmq:5672'],
      queue: 'user_queue',
    },
  });

  // Start both
  await app.startAllMicroservices();
  await app.listen(3000);
}

// Controller now handles BOTH request types:
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
// Problem: transaction spanning multiple services
// No cross-service DB transactions — each service has its own DB
// Solution: Saga with compensating actions

// Choreography-based Saga (event-driven):
// Order Service:
@EventsHandler(OrderCreatedEvent)
export class OrderCreatedHandler {
  constructor(@Inject('PAYMENT_SERVICE') private paymentClient: ClientProxy) {}

  async handle(event: OrderCreatedEvent) {
    // Step 2: ask Payment Service to charge
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
    // Compensating action — cancel the order
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

// Orchestration-based Saga — central orchestrator coordinates steps
// More complex, but easier to debug — all steps in one place
```

## Observability in microservices

```typescript
// Correlation ID — trace a request across all services
@Injectable()
export class CorrelationIdInterceptor implements NestInterceptor {
  intercept(context: ExecutionContext, next: CallHandler) {
    const rpcContext = context.switchToRpc();
    const data = rpcContext.getData();

    // Pass correlationId in every message
    const correlationId = data?.correlationId ?? crypto.randomUUID();

    Logger.log(`Processing message`, { correlationId });

    return next.handle();
  }
}

// Pattern: always include in the payload:
interface BaseMessage {
  correlationId: string;  // trace across services
  timestamp: string;      // when the event occurred
  version: string;        // payload format version
}

// Circuit Breaker — protect against cascading failures
// Library: @nestjs/terminus + opossum or resilience4ts
// At 50% errors over 30s — "open" the circuit (fast-fail)
// After timeout — "half-open" (attempt one request)
```

## Common interview mistakes

- **"Microservices are better than a monolith"** — no. Microservices add: network latency, eventual consistency, distributed tracing complexity, infrastructure overhead. For most startups and CRUD apps, a monolith is faster to develop and cheaper to run. "Monolith first" is Martin Fowler's recommendation.

- **"send() returns a Promise"** — no. `clientProxy.send()` returns an `Observable`. To get the value in async/await code: `await firstValueFrom(this.client.send(...))`. Do not call `.subscribe()` manually — it leads to memory leaks.

- **"EventPattern and MessagePattern do the same thing"** — no. `@MessagePattern` expects a reply from the handler — for request/response interaction. `@EventPattern` returns no reply — fire-and-forget, for events. On the client side: `send()` for MessagePattern, `emit()` for EventPattern.

- **"TCP transport is fine for production"** — no. TCP in NestJS is a direct connection without queues, buffering, retry, or dead-letters. Messages are lost when the service restarts. Production: RabbitMQ (reliable delivery), Kafka (high throughput + retention), gRPC (strict contract).

- **"Distributed transaction = BEGIN/COMMIT across services"** — impossible. Each service has its own DB. Solution: Saga pattern with compensating actions. Result: eventual consistency, not strict consistency. This is a fundamental trade-off of microservice architecture — it's important to understand and explain it clearly in an interview.
