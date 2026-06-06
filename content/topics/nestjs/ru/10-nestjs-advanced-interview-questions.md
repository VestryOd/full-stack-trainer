<!-- verified: 2026-06-05, corrections: 0 -->
# NestJS Advanced Interview Questions

---

# 1. Что такое NestJS?

Прогрессивный Node.js framework,
построенный поверх:

```txt
Express
или
Fastify
```

---

Использует:

```txt
Dependency Injection

Modules

Decorators
```

---

# 2. Что происходит внутри NestFactory.create()?

1. Сканирование модулей.
2. Построение Dependency Graph.
3. Регистрация Providers.
4. Создание Singleton объектов.
5. Запуск HTTP Adapter.

---

# 3. Что такое Dependency Injection?

Передача зависимостей извне через контейнер.

---

# 4. Что такое DI Container?

Хранилище:

```txt
Token → Instance
```

---

# 5. Что такое Provider?

Любой объект,
который участвует в Dependency Injection.

---

# 6. Что такое Injection Token?

Ключ,
по которому Nest ищет зависимость.

---

# 7. Какие типы Provider знаете?

```txt
useClass

useValue

useFactory

useExisting
```

---

# 8. Когда использовать useFactory?

Когда объект нужно создавать динамически.

---

Например:

```txt
Prisma

JWT

External SDK
```

---

# 9. Что такое Dynamic Module?

Модуль,
создающий конфигурацию во время выполнения.

---

# 10. Что такое forRoot()?

Регистрация глобальной конфигурации.

---

# 11. Что такое forFeature()?

Локальная регистрация для конкретного модуля.

---

# 12. Что такое ExecutionContext?

Контекст текущего запроса.

---

Позволяет получить:

```txt
Request

Handler

Controller
```

---

# 13. Что такое Reflect Metadata?

Механизм хранения метаданных на классах и методах.

---

# 14. Что такое Reflector?

Сервис для чтения metadata.

---

# 15. Как работает @Roles()?

Сохраняет роли через metadata.

---

Guard читает их через Reflector.

---

# 16. Что такое Custom Decorator?

Пользовательский декоратор,
добавляющий metadata
или извлекающий данные.

---

# 17. Что такое Composite Decorator?

Комбинация нескольких декораторов через:

```ts
applyDecorators()
```

---

# 18. Что такое Middleware?

Обработка запроса до попадания в Nest pipeline.

---

# 19. Что такое Guard?

Механизм авторизации.

---

Решает:

```txt
можно выполнять запрос
или нельзя
```

---

# 20. Что такое Pipe?

Трансформация и валидация входящих данных.

---

# 21. Что такое ValidationPipe?

Проверяет DTO через:

```txt
class-validator
```

---

# 22. Что делает whitelist?

Удаляет лишние поля.

---

# 23. Что такое Interceptor?

Механизм перехвата выполнения метода.

---

До и после вызова handler.

---

# 24. Для чего используют Interceptors?

```txt
Logging

Caching

Metrics

Response Mapping
```

---

# 25. Что такое Exception Filter?

Глобальная обработка ошибок.

---

# 26. В каком порядке выполняются Middleware, Guard, Pipe и Interceptor?

```txt
Middleware
 ↓
Guard
 ↓
Interceptor(before)
 ↓
Pipe
 ↓
Controller
 ↓
Interceptor(after)
```

---

# 27. Что такое Scope?

Жизненный цикл Provider.

---

# 28. Какие Scope существуют?

```txt
Singleton

Request

Transient
```

---

# 29. Какой Scope используется по умолчанию?

```txt
Singleton
```

---

# 30. Почему Request Scope дорогой?

Создает новый dependency graph на каждый запрос.

---

# 31. Когда использовать Request Scope?

```txt
Tenant Context

Correlation ID

Tracing
```

---

# 32. Что такое CQRS?

Разделение операций чтения и записи.

---

# 33. Что такое Command?

Операция изменения состояния.

---

# 34. Что такое Query?

Операция чтения данных.

---

# 35. Что такое Event?

Факт произошедшего события.

---

# 36. Что такое CommandBus?

Шина выполнения команд.

---

# 37. Что такое QueryBus?

Шина выполнения запросов.

---

# 38. Что такое EventBus?

Шина публикации событий.

---

# 39. Когда CQRS оправдан?

Сложная бизнес логика.

---

# 40. Когда CQRS избыточен?

Обычный CRUD.

---

# 41. Что такое микросервис?

Независимый сервис,
выполняющий ограниченный набор задач.

---

# 42. Что такое ClientProxy?

Клиент отправки сообщений между сервисами.

---

# 43. Что делает send()?

Request/Response взаимодействие.

---

# 44. Что делает emit()?

Публикация события без ожидания ответа.

---

# 45. Что такое MessagePattern?

Обработчик запросов.

---

# 46. Что такое EventPattern?

Обработчик событий.

---

# 47. Какие транспорты поддерживает Nest?

```txt
TCP

Redis

RabbitMQ

Kafka

NATS

gRPC
```

---

# 48. Когда использовать RabbitMQ?

Очереди задач,
retry,
routing.

---

# 49. Когда использовать Kafka?

Высоконагруженный event streaming.

---

# 50. Самый популярный Senior вопрос

Что делает NestJS сильным framework?

Ответ:

Nest объединяет Dependency Injection, модульную архитектуру, декораторы, middleware pipeline, CQRS и поддержку микросервисов в единую платформу. Это позволяет строить как небольшие API, так и сложные распределенные системы с хорошей тестируемостью и слабой связанностью компонентов.