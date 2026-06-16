<!-- verified: 2026-06-05, corrections: 0 -->
# Queries, Mutations и Subscriptions

## Три типа операций — но различие глубже, чем "Query = GET, Mutation = POST"

```txt
Query        — чтение данных
Mutation      — изменение данных
Subscription  — поток событий в реальном времени
```

Поверхностная аналогия с HTTP-методами помогает на старте, но скрывает САМОЕ важное различие между Query и Mutation — порядок выполнения top-level полей, который определён спецификацией и имеет прямые последствия для consistency данных.

## Query: top-level поля выполняются ПАРАЛЛЕЛЬНО

```graphql
query Dashboard {
  profile { name }
  notifications { count }
  recentOrders { id, total }
}
```

```txt
По спецификации GraphQL, top-level резолверы для Query МОГУТ
(и обычно ДОЛЖНЫ, если они async) выполняться ПАРАЛЛЕЛЬНО —
GraphQL-сервер не обязан ждать завершения profile перед
запуском notifications. Порядок полей в ОТВЕТЕ всегда
соответствует порядку в запросе (ключи объекта сохраняют
порядок), но порядок ВЫПОЛНЕНИЯ резолверов — нет.
```

```ts
// Если все три резолвера обращаются к БД — они
// выполняются параллельно, общее время ответа ≈
// max(t_profile, t_notifications, t_recentOrders),
// а НЕ сумма
const resolvers = {
  Query: {
    profile: async (_p, _a, ctx) => ctx.db.users.findById(ctx.user.id),
    notifications: async (_p, _a, ctx) => ctx.db.notifications.countUnread(ctx.user.id),
    recentOrders: async (_p, _a, ctx) => ctx.db.orders.findRecent(ctx.user.id),
  },
};
```

## Mutation: top-level поля выполняются СТРОГО ПОСЛЕДОВАТЕЛЬНО — самый недооценённый факт спецификации

```graphql
mutation BatchUpdate {
  deductBalance(amount: 100)
  addLoyaltyPoints(amount: 10)
}
```

```txt
Спецификация GraphQL ЯВНО требует: top-level поля Mutation
выполняются ПОСЛЕДОВАТЕЛЬНО, в порядке их следования в
запросе — deductBalance ПОЛНОСТЬЮ завершается ДО начала
addLoyaltyPoints. Это сделано ИМЕННО для предотвращения race
condition при множественных изменениях данных в одном запросе.

Senior-следствие: если разработчик предполагает, что
несколько mutations в одном запросе выполнятся "как-то
параллельно для скорости" — это ОШИБОЧНОЕ предположение,
и оно НЕ должно влиять на выбор архитектуры (например, "давайте
не будем splитить на отдельные запросы ради consistency" —
спецификация УЖЕ гарантирует последовательность).

При этом: ВЛОЖЕННЫЕ резолверы внутри РЕЗУЛЬТАТА одной mutation
(например, поля связанного объекта в ответе) — выполняются
по тем же правилам, что и для Query (параллельно, где возможно).
```

## Дизайн Mutation-ответов — "Payload Pattern" vs исключения

```graphql
# ❌ Наивный подход — мутация возвращает либо объект, либо
# падает с GraphQL error (теряется структура — клиенту
# сложно различить "validation error" и "server error")
type Mutation {
  createUser(input: CreateUserInput!): User!
}
```

```graphql
# ✅ Payload Pattern — мутация ВСЕГДА успешна на уровне
# транспорта, бизнес-ошибки — часть СХЕМЫ, а не errors[]
type CreateUserPayload {
  user: User
  errors: [UserError!]
}

type UserError {
  field: String!
  message: String!
  code: UserErrorCode!
}

enum UserErrorCode {
  EMAIL_TAKEN
  INVALID_EMAIL
  WEAK_PASSWORD
}

type Mutation {
  createUser(input: CreateUserInput!): CreateUserPayload!
}
```

```txt
Trade-off, который стоит явно проговорить на интервью:

GraphQL errors[] (массив ошибок верхнего уровня) —
предназначен для НЕОЖИДАННЫХ ошибок (БД недоступна, баг) —
вызывает null bubbling (см. [Schema, Types, and Resolvers]).

Typed error unions / Payload Pattern — для ОЖИДАЕМЫХ
бизнес-ошибок (email занят, недостаточно средств) —
клиент ОБЯЗАН обработать их как часть нормального потока
данных (TypeScript заставит проверить errors перед
использованием user), а не через try/catch.

Большинство production GraphQL API (Shopify, GitHub) ИМЕННО
поэтому используют Payload Pattern для бизнес-логики
и errors[] оставляют для системных сбоев.
```

## Variables — не просто "стиль", а требование для Persisted Queries и безопасности

```graphql
# ❌ Inline-аргументы — каждый уникальный набор данных создаёт
# НОВУЮ строку запроса
query {
  user(id: "42") { name }
}

# ✅ Variables — текст запроса СТАБИЛЕН независимо от данных
query GetUser($id: ID!) {
  user(id: $id) { name }
}
```

```txt
Почему это критично, а не "best practice ради красоты":

1. Persisted Queries / APQ (Automatic Persisted Queries) —
   клиент отправляет ХЭШ текста запроса вместо самого текста.
   Если каждый запрос имеет уникальный inline-аргумент —
   ХЭШ МЕНЯЕТСЯ каждый раз, и кэширование по хэшу теряет смысл
   (см. [Performance and Security]).

2. Query allowlisting в production — белый список разрешённых
   ЗАПРОСОВ (по хэшу текста) — работает только если текст
   запроса НЕ зависит от пользовательских данных.

3. Безопасность — сериализация значений в variables проходит
   через parseValue кастомных скаляров (см. [Schema, Types,
   and Resolvers]), что даёт единую точку валидации/санитизации,
   в отличие от произвольной строки запроса.
```

## Fragments — переиспользование полей И единица co-location во фронтенд-архитектуре

```graphql
fragment UserCard on User {
  id
  name
  avatar
}

query ProfilePage {
  currentUser { ...UserCard }
  suggestedFriends { ...UserCard }
}
```

```txt
На уровне СХЕМЫ fragments — просто переиспользование набора
полей. Но в современной фронтенд-архитектуре (Apollo Client,
Relay) фрагменты — это ЕДИНИЦА COLOCATION: КАЖДЫЙ компонент
React определяет СВОЙ fragment с полями, которые ему нужны,
а родительский компонент "собирает" фрагменты дочерних
компонентов в один запрос. Это позволяет компоненту менять
свои data-требования без изменения родителей — прямая
параллель с "клиент определяет форму ответа" из [GraphQL
Fundamentals], но на уровне ДЕКОМПОЗИЦИИ компонентов, а не
всего запроса.

Fragment masking (Relay, новый Apollo Client) идёт дальше:
компонент НЕ МОЖЕТ обратиться к полям, не объявленным в его
СОБСТВЕННОМ фрагменте, даже если они есть в общем результате —
это предотвращает скрытые зависимости между компонентами.
```

## Subscriptions: транспорт и архитектурные ограничения, которые редко проговаривают

```graphql
type Subscription {
  messageAdded(chatId: ID!): Message!
}
```

```ts
// NestJS / graphql-ws
@Subscription(() => Message, {
  filter: (payload, variables) => payload.messageAdded.chatId === variables.chatId,
})
messageAdded(@Args('chatId') chatId: string) {
  return pubSub.asyncIterableIterator('MESSAGE_ADDED');
}
```

### Senior-нюанс №1: In-memory PubSub НЕ РАБОТАЕТ при горизонтальном масштабировании

```txt
graphql-subscriptions предоставляет PubSub "из коробки" —
но РЕАЛИЗАЦИЯ ПО УМОЛЧАНИЮ (PubSub класс) хранит подписчиков
В ПАМЯТИ ОДНОГО ПРОЦЕССА.

Если у вас 4 реплики сервера (см. [Worker Threads and
Cluster] из раздела Node.js):
  - Клиент A подключается к Реплике 1, подписывается на
    messageAdded
  - Mutation от Клиента B обрабатывается Репликой 3
  - Реплика 3 публикует событие в СВОЙ локальный PubSub —
    Реплика 1 (и подписка Клиента A) НИЧЕГО НЕ ПОЛУЧАЕТ

Решение: PubSub на основе Redis (graphql-redis-subscriptions)
или Kafka — публикация события идёт через ВНЕШНЮЮ шину,
которую слушают ВСЕ реплики.
```

### Senior-нюанс №2: аутентификация WebSocket-соединения происходит ОДНАЖДЫ, не на каждое сообщение

```ts
// graphql-ws — connectionParams передаются ОДИН РАЗ при
// установке WebSocket-соединения, не на каждую subscription
const serverConfig = {
  context: async (ctx) => {
    const token = ctx.connectionParams?.authorization;
    const user = await verifyToken(token);
    return { user };
  },
};
```

```txt
В отличие от HTTP-запросов (где заголовок Authorization
передаётся на КАЖДЫЙ запрос), WebSocket-соединение
устанавливается ОДНАЖДЫ, и context для subscription
формируется на основе данных ЭТОГО МОМЕНТА подключения.

Практическое следствие: если у пользователя истекает
JWT ВО ВРЕМЯ долгоживущей подписки — стандартный механизм
не "перепроверяет" токен на каждое событие. Нужна явная
логика разрыва соединения при истечении токена (taймер на
основе exp claim, либо периодическая ре-аутентификация).
```

### Когда Subscriptions — оверинжиниринг

```txt
Subscriptions добавляют сложность: WebSocket-инфраструктуру,
distributed PubSub, управление состоянием long-lived
соединений, отдельную аутентификацию.

Альтернативы для "почти realtime":
  - Polling (рефетч каждые N секунд) — простой, кэшируемый,
    подходит для данных, где задержка в несколько секунд
    приемлема (счётчик уведомлений)
  - Long Polling / Server-Sent Events — для одностороннего
    потока без полной сложности WebSocket

Subscriptions оправданы, когда: задержка КРИТИЧНА (чат,
торговые котировки), и события ДВУНАПРАВЛЕННЫ или очень
частые (polling создаст слишком много избыточных запросов).
```

## Связь с другими темами

```txt
[Schema, Types, and Resolvers]  — null bubbling, который
                                    влияет на дизайн ответов
                                    мутаций
[Performance and Security]       — Persisted Queries, query
                                    allowlisting — зависят от
                                    variables вместо inline-
                                    аргументов
[GraphQL vs REST]                 — сравнение Mutation с
                                    POST/PUT/PATCH/DELETE и
                                    вопрос идемпотентности
```

## Типичные ошибки на интервью

- **"Query и Mutation отличаются только семантически (читать vs писать)"** — не знать про ОБЯЗАТЕЛЬНОЕ последовательное выполнение top-level полей Mutation по спецификации, в отличие от параллельного выполнения для Query.

- **"Ошибки в GraphQL — это всегда `errors[]`"** — не знать о Payload Pattern с typed error unions для ожидаемых бизнес-ошибок, и не объяснять trade-off между null bubbling и явной обработкой ошибок на клиенте.

- **"Variables — это просто синтаксический сахар для аргументов"** — не связывать variables с Persisted Queries/query allowlisting, где стабильность текста запроса критична.

- **"Subscriptions работают из коробки на любом количестве реплик"** — не знать про ограничение in-memory PubSub и необходимость Redis/Kafka-based PubSub для горизонтального масштабирования.

- **Не упоминать проблему аутентификации long-lived WebSocket-соединений** — не понимать, что context для subscription формируется один раз при подключении, а не на каждое событие.
