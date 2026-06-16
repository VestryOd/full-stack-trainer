<!-- verified: 2026-06-05, corrections: 0 -->
# GraphQL Performance и Security

## Корень всех проблем — гибкость, за которую платит сервер

```txt
REST    — сервер полностью контролирует форму и стоимость
          КАЖДОГО эндпоинта (фиксированный набор JOIN'ов,
          фиксированная глубина)
GraphQL — клиент формирует запрос ДИНАМИЧЕСКИ, и сервер
          ДОЛЖЕН выполнить ЛЮБУЮ синтаксически валидную
          комбинацию полей схемы
```

Эта асимметрия — причина, почему GraphQL API требуют ДОПОЛНИТЕЛЬНОГО слоя защиты, которого нет у типичного REST API: depth limiting, query complexity analysis, timeout на резолверы. Без них единственный валидный (с точки зрения схемы) запрос может стать вектором DoS.

## Query Depth и Depth Limiting — простая, но грубая защита

```graphql
query {
  user {
    posts {
      comments {
        author {
          posts {
            comments { text }   # глубина 6
          }
        }
      }
    }
  }
}
```

```ts
// graphql-depth-limit — отклоняет запрос на этапе Validate
// (до вызова резолверов, см. [GraphQL Fundamentals])
import depthLimit from 'graphql-depth-limit';

const server = new ApolloServer({
  schema,
  validationRules: [depthLimit(5)],
});
```

```txt
Проблема depth limiting: он считает только ВЛОЖЕННОСТЬ, а не
СТОИМОСТЬ. Запрос глубины 3, но с 3 алиасами одного и того же
тяжёлого поля (см. ниже про Query Aliasing) пройдёт depth limit,
но по факту вызовет резолвер 3 раза. Depth limiting — это
"дешёвая первая линия защиты", а не полноценное решение.
```

## Query Complexity — назначение "стоимости" каждому полю

```ts
// graphql-query-complexity — каждому полю присваивается вес,
// сумма весов запрошенных полей должна не превышать лимит
const complexityRule = createComplexityLimitRule(1000, {
  estimators: [
    fieldExtensionsEstimator(),
    simpleEstimator({ defaultComplexity: 1 }),
  ],
});
```

```graphql
type Query {
  users(first: Int!): [User!]! @complexity(value: 1, multipliers: ["first"])
}

type User {
  posts(first: Int!): [Post!]! @complexity(value: 2, multipliers: ["first"])
}
```

```txt
Senior-нюанс: сложность УМНОЖАЕТСЯ через multipliers — поле
posts(first: 10) внутри users(first: 100) даёт сложность
ПРИМЕРНО 100 * (1 + 10 * 2) = 2100, а не просто "1 + 2".
Именно перемножение аргументов limit/first на вложенных
уровнях — то, что делает "невинный" с виду запрос
(глубина 3, но first: 100 на каждом уровне) экспоненциально
дорогим. Это и есть формализация "Query Explosion".
```

### Query Aliasing — обход naive-лимитов через дублирование полей

```graphql
query {
  a: expensiveField
  b: expensiveField
  c: expensiveField
  # ... 1000 алиасов одного и того же поля
}
```

```txt
Алиасы — легитимная фича GraphQL (запросить одно поле с разными
аргументами под разными именами). Но 1000 алиасов ОДНОГО
дорогого поля в ОДНОМ запросе → 1000 вызовов резолвера за один
HTTP-запрос — depth limiting это не остановит (глубина = 1).
Защита: либо ограничение количества полей в запросе
(graphql-validation-complexity считает и это), либо rate
limiting на уровне СЛОЖНОСТИ запроса, а не количества HTTP-
запросов.
```

## Rate Limiting — GraphQL не отменяет классику, но единицей измерения должна быть СЛОЖНОСТЬ

```txt
Наивно: "100 запросов в минуту на IP" — не работает, потому что
1 запрос может стоить как 1, а может — как 10 000 (см. Query
Complexity выше). Production-практика — комбинировать:

  1. Rate limiting по количеству HTTP-запросов (Redis,
     API Gateway, NestJS Throttler) — базовая защита от
     простого флуда
  2. Rate limiting по СУММЕ query complexity за период — для
     защиты от "малого числа дорогих запросов"
  3. Resolver-level timeout — отдельный резолвер, который висит
     дольше N секунд (например, ждёт внешний API), завершается
     с ошибкой, не блокируя весь event loop (см. [Worker Threads
     and Cluster] из раздела Node.js про event loop blocking)
```

## Pagination — почему limit/offset недостаточно для масштаба

```graphql
# ⚠️ Offset pagination — простая, но деградирует на больших
# offset (БД всё равно сканирует и отбрасывает offset строк)
users(skip: 100000, take: 20): [User!]!
```

```graphql
# ✅ Cursor-based (Relay Connection spec) — курсор кодирует
# позицию (часто — закодированный id/timestamp последней
# записи), БД делает WHERE id > cursor LIMIT 20 — индекс
# используется напрямую, без сканирования пропущенных строк
type UserConnection {
  edges: [UserEdge!]!
  pageInfo: PageInfo!
}

type UserEdge {
  node: User!
  cursor: String!
}

type PageInfo {
  hasNextPage: Boolean!
  endCursor: String
}

type Query {
  users(first: Int!, after: String): UserConnection!
}
```

```txt
Дополнительный плюс cursor pagination: она УСТОЙЧИВА к
вставкам/удалениям между страницами (offset 100-120 после
вставки записи на позицию 50 "сдвинет" всю страницу и приведёт
к дублям/пропускам — курсор от этого не зависит, так как
привязан к конкретной записи, а не к позиции).

first/take в схеме — это ОБЯЗАТЕЛЬНЫЙ аргумент в production:
без него users без пагинации — самый частый источник
"внезапно дорогого" запроса, который не остановит depth limit
(глубина 1) и сложно ограничить complexity-правилами без
multipliers.
```

## Caching — почему GraphQL не кэшируется "бесплатно", и Persisted Queries как решение

```txt
Эта проблема разобрана на уровне HTTP в [GraphQL Fundamentals]
(POST /graphql не кэшируется CDN/браузером по URL). Persisted
Queries решают её так:
```

```txt
1. Клиент один раз регистрирует текст запроса на сервере
   (или вычисляет SHA-256 хэш сам — Automatic Persisted Queries)
2. На КАЖДЫЙ последующий вызов клиент отправляет ТОЛЬКО хэш:
   GET /graphql?extensions={"persistedQuery":{"sha256Hash":"abc123"}}&variables={"id":"1"}
3. Сервер: если хэш известен — выполняет запрос по сохранённому
   тексту + полученным variables; если хэш неизвестен — просит
   клиента отправить полный текст один раз (для регистрации)
```

```txt
Эффекты:
  - Трафик резко падает (хэш короче запроса)
  - Запрос отправляется через GET → можно кэшировать на CDN по
    URL (хэш + variables в query string)
  - Побочный эффект безопасности: т.к. ИЗВЕСТНЫЕ хэши можно
    занести в allowlist (см. [Queries, Mutations, and
    Subscriptions] про связь variables ↔ Persisted Queries),
    сервер может ОТКЛОНЯТЬ запросы с произвольным текстом —
    защита от Query Explosion на корню
```

## Introspection — детали из [GraphQL Fundamentals], применённые к security

```txt
Подробный trade-off (codegen/Playground vs утечка структуры API)
разобран в [GraphQL Fundamentals]. Дополнение для security-
контекста: отключение introspection — это "security through
obscurity", а НЕ замена authorization. Злоумышленник с доступом
к исходникам фронтенда (bundle.js содержит ВСЕ используемые
запросы) или к перехваченному трафику УЖЕ видит часть схемы —
отключение __schema только усложняет brute-force ОСТАЛЬНЫХ
полей, но не делает их недоступными при наличии прав.
```

## Authorization — почему "защитить endpoint" не работает в GraphQL

```txt
В REST у каждого ресурса свой URL → middleware на роуте
(`router.get('/admin/users', requireAdmin, handler)`) покрывает
весь доступ к ресурсу.

В GraphQL ОДИН endpoint обслуживает ВСЕ типы данных — авторизация
"на входе" в /graphql может проверить только "залогинен ли
пользователь вообще", но НЕ "может ли он видеть ПОЛЕ
User.email ДРУГОГО пользователя".
```

```ts
// ❌ Недостаточно — проверка на уровне всего запроса
app.use('/graphql', requireAuth, graphqlHandler);

// ✅ Авторизация на уровне РЕЗОЛВЕРА конкретного ПОЛЯ
const resolvers = {
  User: {
    email: (user, _args, ctx) => {
      if (ctx.user.id !== user.id && !ctx.user.isAdmin) {
        return null; // или throw new ForbiddenError()
      }
      return user.email;
    },
  },
};
```

```ts
// NestJS — декларативно, через Guards на уровне резолвера поля
@ResolveField('email')
@UseGuards(FieldOwnerOrAdminGuard)
email(@Parent() user: User) {
  return user.email;
}
```

```txt
Senior-нюанс: field-level authorization взаимодействует с null
bubbling (см. [Schema, Types, and Resolvers]) — если email
объявлен как String! (non-null), а резолвер из-за прав доступа
вернёт null, это вызовет null bubbling всего объекта User.
Поэтому поля, доступ к которым может быть ограничен по правам,
ДОЛЖНЫ быть nullable в схеме — это архитектурное решение схемы,
продиктованное требованиями авторизации, а не только данными.
```

## Federation — когда один монолитный GraphQL-сервер недостаточен

```txt
User Service (graph)  ──┐
Post Service (graph)  ──┼──→  Apollo Gateway / Router  →  Client
Review Service (graph) ─┘     (один объединённый граф)
```

```graphql
# User Service — владеет типом User
type User @key(fields: "id") {
  id: ID!
  name: String!
}

# Post Service — РАСШИРЯЕТ User полем, которым владеет САМ
extend type User @key(fields: "id") {
  id: ID! @external
  posts: [Post!]!
}
```

```ts
// Post Service — резолвер для "сборки" расширения сущности из
// другого сервиса. Когда Gateway собирает ответ и нужно
// разрешить User.posts, он вызывает Reference Resolver с
// { id } из User Service
const resolvers = {
  User: {
    posts: (user, _args, ctx) => ctx.db.post.findMany({ where: { authorId: user.id } }),
  },
};
```

```txt
Federation решает организационную проблему (разные команды
владеют разными частями графа независимо), но добавляет НОВЫЙ
N+1-подобный слой: Gateway делает отдельные сетевые запросы к
КАЖДОМУ сервису для "дозаполнения" сущности — то есть DataLoader
(см. [N+1 Problem and DataLoader]) теперь нужен не только на
уровне БД внутри сервиса, но и Gateway батчит запросы _entities
между сервисами.
```

## Связь с другими темами

```txt
[GraphQL Fundamentals]            — почему HTTP-кэширование не
                                      работает "из коробки",
                                      Introspection trade-off
[Schema, Types, and Resolvers]    — null bubbling и его
                                      взаимодействие с field-level
                                      authorization
[N+1 Problem and DataLoader]       — DataLoader как часть
                                      общей картины производительности
[Queries, Mutations, and
 Subscriptions]                     — variables как требование для
                                      Persisted Queries
```

## Типичные ошибки на интервью

- **"Депт-лимит решает проблему дорогих запросов"** — не упоминать Query Aliasing как способ обойти depth limiting при глубине 1, и не знать про Query Complexity с multipliers как более точный механизм.

- **"Offset pagination достаточно, просто добавим limit"** — не объяснять деградацию производительности на больших offset и нестабильность при вставках/удалениях, не знать про Relay Connection spec (cursor-based).

- **"Persisted Queries — это просто оптимизация трафика"** — не связывать их с безопасностью (allowlisting известных хэшей как защита от Query Explosion) и с кэшированием через GET.

- **"Authorization можно сделать одним middleware на /graphql"** — не понимать, что в GraphQL авторизация должна быть на уровне РЕЗОЛВЕРА конкретного поля, а не всего запроса.

- **Не видеть конфликт field-level authorization и non-null полей** — резолвер, возвращающий null из-за прав доступа для поля типа `String!`, вызывает null bubbling всего объекта.

- **"Federation — это просто микросервисы для GraphQL"** — не упоминать, что Gateway вносит СОБСТВЕННЫЙ N+1-подобный слой между сервисами при сборке сущностей (`_entities`).
