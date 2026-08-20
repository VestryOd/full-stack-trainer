# Микросервисы в NestJS

## Транспорты и паттерны взаимодействия

NestJS скрывает транспорт за одним и тем же API: код обработчика не меняется, работаете вы через TCP, RabbitMQ, Kafka или gRPC. TCP (transmission control protocol) — это прямое сетевое соединение между двумя сервисами, а gRPC — фреймворк удалённых вызовов от Google поверх HTTP/2.

Транспорт здесь — канал, по которому сервисы обмениваются сообщениями. Паттернов взаимодействия два:

- `@MessagePattern` — запрос-ответ: клиент отправил сообщение и ждёт результат.
- `@EventPattern` — событие без ответа (fire-and-forget): клиент отправил и пошёл дальше.

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

`ClientProxy` — клиентская сторона той же схемы. Модуль регистрирует соединение через `ClientsModule.register`, а сервис получает готовый прокси по токену и вызывает у него один из двух методов.

`send()` — для `@MessagePattern`. Он возвращает Observable с ответом, поэтому в коде на async/await его оборачивают в `firstValueFrom`. `emit()` — для `@EventPattern`: ответа нет, ждать нечего.

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

## Транспорты: TCP, RabbitMQ, Kafka и gRPC

Выбор транспорта — это выбор гарантий доставки, а не только скорости. Ниже четыре конфигурации, и в комментариях к каждой сказано, что она даёт и чего не даёт.

Два названия из примера. RabbitMQ в опциях NestJS обозначается как `Transport.RMQ`. Контракт gRPC описывают в файле `.proto` на языке Protocol Buffers (protobuf) — это бинарный формат сообщений вместо JSON.

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

## Гибридное приложение — HTTP и микросервис в одном процессе

Один процесс Nest может слушать два входа сразу: HTTP для внешних клиентов и очередь или TCP для других сервисов. Приложение создаётся как обычное HTTP-приложение, а второй вход добавляется вызовом `connectMicroservice`.

Дальше один и тот же контроллер обслуживает оба типа запросов: метод с `@Get` отвечает на HTTP, метод с `@MessagePattern` — на сообщения.

```typescript
// Один процесс NestJS слушает и HTTP (для внешних клиентов),
// и TCP или RabbitMQ (для других сервисов)
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

## Распределённые транзакции — паттерн Saga

Транзакции `BEGIN`/`COMMIT` между сервисами не бывает: у каждого сервиса своя база данных. Поэтому бизнес-процесс разбивают на шаги, и у каждого шага есть компенсирующее действие — то, что отменяет уже сделанное.

В примере ниже — хореографическая сага: сервисы обмениваются событиями напрямую, без координатора. Второй вариант, оркестрация, упомянут в конце примера.

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

## Наблюдаемость в микросервисах

Наблюдаемость (observability) — это возможность понять, что происходило с запросом, уже после того как он прошёл. В монолите для этого хватает стека вызовов. В микросервисах один запрос идёт через несколько процессов, поэтому его надо помечать.

Метка называется correlation ID: первый сервис генерирует её один раз и передаёт дальше в каждом сообщении. По ней потом собирают всю историю запроса из логов разных сервисов.

Вторая часть примера — про отказы. Circuit Breaker («предохранитель») перестаёт дёргать сервис, который стабильно отвечает ошибкой, и тем самым не даёт отказу распространиться по цепочке.

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

- **"Микросервисы лучше монолита"** — нет, у них своя цена: сетевые задержки, согласованность «в конечном счёте» вместо мгновенной, сложная отладка запроса через несколько сервисов и расходы на инфраструктуру. Для большинства стартапов и приложений вокруг простых операций над данными монолит быстрее в разработке и дешевле в эксплуатации. «Сначала монолит» — рекомендация Мартина Фаулера.

- **"send() возвращает Promise"** — нет, `clientProxy.send()` возвращает Observable. Чтобы получить значение в коде на async/await, напишите `await firstValueFrom(this.client.send(...))`. Вызывать `.subscribe()` вручную не надо: так появляются утечки памяти.

- **"EventPattern и MessagePattern делают одно и то же"** — нет. `@MessagePattern` ждёт ответ от обработчика, это взаимодействие запрос-ответ. `@EventPattern` ответа не возвращает, это событие. На стороне клиента им соответствуют `send()` и `emit()`.

- **"TCP transport подходит для production"** — нет. TCP в NestJS — прямое соединение без очередей, буферизации, повторов и хранилища недоставленных сообщений. Перезапустили сервис — сообщения потеряны. Для продакшена берут RabbitMQ (надёжная доставка), Kafka (высокая пропускная способность и хранение истории) или gRPC (строгий контракт).

- **"Распределённая транзакция — это BEGIN/COMMIT между сервисами"** — так не бывает, у каждого сервиса своя база. Вместо этого используют сагу с компенсирующими действиями. Результат — согласованность в конечном счёте, а не строгая. Это осознанная плата за микросервисную архитектуру, и на интервью важно назвать её прямо.
