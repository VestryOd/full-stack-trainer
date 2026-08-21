# NestJS Microservices

## Transports and communication patterns

NestJS hides the transport behind one and the same API: the handler code does not change whether you run over TCP, RabbitMQ, Kafka or gRPC. TCP (transmission control protocol) is a direct network connection between two services, and gRPC is Google's remote call framework running on top of HTTP/2.

A transport here is the channel services exchange messages over. There are two communication patterns:

- `@MessagePattern` — request and response: the client sends a message and waits for the result.
- `@EventPattern` — an event with no reply (fire-and-forget): the client sends it and moves on.

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

`ClientProxy` is the client side of the same scheme. The module registers the connection through `ClientsModule.register`, and a service receives the ready proxy by token and calls one of its two methods.

The `send()` method is for `@MessagePattern`. It returns an Observable with the reply, so in async/await code you wrap it in `firstValueFrom`. The `emit()` method is for `@EventPattern`: there is no reply, so there is nothing to wait for.

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

## Transports: TCP, RabbitMQ, Kafka and gRPC

Picking a transport is picking delivery guarantees, not only speed. Below are four configurations, and each comment says what that option gives you and what it does not.

Two names from the example. RabbitMQ appears in NestJS options as `Transport.RMQ`. The gRPC contract is described in a `.proto` file written in Protocol Buffers (protobuf) — a binary message format used instead of JSON.

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

## Hybrid app — HTTP and a microservice in one process

One Nest process can listen on two entry points at once: HTTP for external clients, and a queue or TCP for other services. The app is created as an ordinary HTTP app, and the second entry point is added by calling `connectMicroservice`.

After that a single controller serves both kinds of request: a method with `@Get` answers HTTP, a method with `@MessagePattern` answers messages.

```typescript
// One NestJS process listens on both HTTP (for external clients)
// and TCP or RabbitMQ (for other services)
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

## Distributed transactions — the Saga pattern

There is no `BEGIN`/`COMMIT` transaction across services: each service has its own database. So the business process is split into steps, and every step gets a compensating action — the thing that undoes what was already done.

The example below is a choreography saga: services exchange events directly, with no coordinator. The other option, orchestration, is mentioned at the end of the example.

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

Observability is being able to tell what happened to a request after it is already done. In a monolith a call stack is enough. In microservices one request travels through several processes, so it has to be tagged.

The tag is called a correlation ID: the first service generates it once and passes it along in every message. Later you use it to collect the whole story of that request from the logs of different services.

The second part of the example is about failures. A circuit breaker stops calling a service that keeps answering with errors, which keeps one failure from spreading down the chain.

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

- **"Microservices are better than a monolith"** — no, they have their own price. The price is network latency, eventual consistency instead of immediate, hard debugging across several services, and infrastructure costs. For most startups, and for apps that mostly create, read, update and delete records, a monolith is faster to build and cheaper to run. "Monolith first" is Martin Fowler's recommendation.

- **"send() returns a Promise"** — no, `clientProxy.send()` returns an Observable. To get the value in async/await code, write `await firstValueFrom(this.client.send(...))`. Do not call `.subscribe()` by hand: that is how memory leaks appear.

- **"EventPattern and MessagePattern do the same thing"** — no. A `@MessagePattern` handler returns a reply, which makes it request-response communication. An `@EventPattern` handler returns nothing, because it carries an event. On the client side the two map to `send()` and `emit()`.

- **"TCP transport is fine for production"** — no. TCP in NestJS is a direct connection with no queues, no buffering, no retries and no store for undelivered messages. Restart the service and the messages are gone. For production people pick RabbitMQ (reliable delivery), Kafka (high throughput plus stored history) or gRPC (a strict contract).

- **"A distributed transaction is BEGIN/COMMIT across services"** — there is no such thing, because every service has its own database. What you use instead is a saga with compensating actions. The result is eventual consistency, not strict consistency. This is a deliberate price you pay for a microservice architecture, and in an interview it is worth naming out loud.
