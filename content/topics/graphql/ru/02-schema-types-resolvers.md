<!-- verified: 2026-06-05, corrections: 0 -->
# Schema, Types и Resolvers

## Schema — это не просто "описание данных", это контракт с конкретными гарантиями

```graphql
type User {
  id: ID!
  name: String!
  email: String
}
```

SDL (Schema Definition Language) — формальный язык, описывающий КАЖДЫЙ возможный запрос к API и гарантии о форме ответа. "Гарантии" здесь ключевое слово: `String!` — это не просто "обычно не null", это ОБЯЗАТЕЛЬСТВО сервера, нарушение которого приводит к ошибке выполнения (см. ниже про null bubbling) — то есть схема влияет на runtime-поведение, а не только на статическую типизацию.

## Скалярные типы и кастомные скаляры

```graphql
scalar String
scalar Int
scalar Float
scalar Boolean
scalar ID    # сериализуется как String, но семантически — идентификатор
```

```txt
ID vs String — частый вопрос: ID семантически отличается
(используется для кэширования на клиенте, Relay Global
Object Identification), но НА УРОВНЕ ПЕРЕДАЧИ ДАННЫХ
неотличим от String. "1" и 1 оба валидны как ID.
```

### Кастомные скаляры — типичный senior-паттерн

```ts
// DateTime как кастомный скаляр — сериализация/десериализация
// происходит в ОДНОМ месте, а не в каждом resolver'е
const DateTimeScalar = new GraphQLScalarType({
  name: 'DateTime',
  serialize: (value: Date) => value.toISOString(),       // сервер → клиент
  parseValue: (value: string) => new Date(value),         // клиент → сервер (variables)
  parseLiteral: (ast) => new Date((ast as StringValueNode).value), // клиент → сервер (inline)
});
```

```graphql
scalar DateTime

type Post {
  createdAt: DateTime!
}
```

Без кастомного скаляра `createdAt: String!` ТЕХНИЧЕСКИ работает, но теряет смысловую типизацию — клиент не знает из схемы, что строка — это дата в ISO-формате, и codegen сгенерирует `string`, а не `Date`/`DateTime`.

## Non-Null и Lists — комбинации и ИХ РЕАЛЬНОЕ ВЛИЯНИЕ на поведение при ошибках

```graphql
posts: [Post]      # массив может быть null, элементы могут быть null
posts: [Post]!     # массив не null, элементы могут быть null
posts: [Post!]     # массив может быть null, элементы не null
posts: [Post!]!    # ни массив, ни элементы не null
```

### Senior-нюанс: "Null Bubbling" — что происходит, когда non-null поле возвращает ошибку

```graphql
type Query {
  user(id: ID!): User    # nullable
}

type User {
  id: ID!
  name: String!          # non-null!
  email: String
}
```

```txt
Если resolver User.name выбросит ошибку (или вернёт null
для поля типа String!):

  GraphQL НЕ МОЖЕТ вернуть { "name": null } — это нарушило
  бы контракт схемы (String! гарантирует "никогда null").

  Поэтому ошибка "пробулькивает" ВВЕРХ по дереву ответа до
  БЛИЖАЙШЕГО NULLABLE родителя — в данном случае весь объект
  user становится null:

  {
    "data": { "user": null },
    "errors": [{ "message": "...", "path": ["user", "name"] }]
  }

  Если бы Query.user тоже был User! (non-null) — пузырь
  пошёл бы ЕЩЁ ВЫШЕ, и null'ом стало бы ВСЁ поле "data".
```

```txt
Практический вывод: ЧРЕЗМЕРНОЕ использование "!" в схеме —
это не просто "строгость ради строгости". Каждый "!" создаёт
ТОЧКУ КАСКАДНОГО ОБНУЛЕНИЯ. Один нестабильный resolver
глубоко вложенного non-null поля может обнулить ВЕСЬ ответ
запроса. Распространённая практика — делать non-null ТОЛЬКО
поля, которые ДЕЙСТВИТЕЛЬНО гарантированно присутствуют
(`id`), и оставлять nullable всё, что зависит от внешних
сервисов/может временно отсутствовать.
```

## Object Types, Interfaces, Unions — когда одного Object Type недостаточно

```graphql
# Interface — общий набор полей для разных типов
interface Notification {
  id: ID!
  createdAt: DateTime!
}

type LikeNotification implements Notification {
  id: ID!
  createdAt: DateTime!
  likedBy: User!
}

type CommentNotification implements Notification {
  id: ID!
  createdAt: DateTime!
  comment: Comment!
}

type Query {
  notifications: [Notification!]!
}
```

```graphql
# Запрос с inline fragments — клиент запрашивает ОБЩИЕ поля
# для всех типов + СПЕЦИФИЧНЫЕ поля для каждого конкретного
query {
  notifications {
    id
    createdAt
    ... on LikeNotification { likedBy { name } }
    ... on CommentNotification { comment { text } }
  }
}
```

```ts
// Сервер ДОЛЖЕН уметь определить, какой КОНКРЕТНЫЙ тип
// вернулся — для этого реализуется __resolveType
const resolvers = {
  Notification: {
    __resolveType(obj) {
      if ('likedBy' in obj) return 'LikeNotification';
      if ('comment' in obj) return 'CommentNotification';
      return null;
    },
  },
};
```

```txt
Union отличается от Interface: Union (`union SearchResult =
User | Post`) НЕ требует общих полей между типами вообще —
члены union могут быть полностью НЕСВЯЗАННЫМИ типами.
Interface требует, чтобы все реализации содержали поля
интерфейса. Оба нуждаются в __resolveType (или
__resolveType на уровне union).
```

## Input Types — почему GraphQL не использует Object Types для аргументов

```graphql
# ❌ Невозможно — Object Types нельзя использовать как
# тип аргумента
type Mutation {
  createUser(user: User!): User!  # ОШИБКА СХЕМЫ
}

# ✅ Input Type — отдельная иерархия типов для входных данных
input CreateUserInput {
  name: String!
  email: String!
}

type Mutation {
  createUser(input: CreateUserInput!): User!
}
```

```txt
Причина разделения: Object Type может содержать поля с
РЕЗОЛВЕРАМИ (вычисляемые поля, связи с другими типами,
интерфейсы) — концепции, которые не имеют смысла для входных
данных, которые клиент просто СЕРИАЛИЗУЕТ как JSON.
Input Types — это "плоские" структуры данных без резолверов,
интерфейсов и unions (только начиная с недавних версий
спецификации появились Input Unions через @oneOf).
```

## Resolver — сигнатура `(parent, args, context, info)` на конкретном примере

```graphql
query {
  user(id: "1") {
    name
    posts(limit: 2) { title }
  }
}
```

```ts
const resolvers = {
  Query: {
    // parent = undefined (это корневой resolver)
    // args   = { id: "1" }
    user: (_parent, args, context, info) => context.db.users.findById(args.id),
  },
  User: {
    // parent = объект User, ВОЗВРАЩЁННЫЙ резолвером Query.user
    // args   = { limit: 2 }
    posts: (parent, args, context, info) =>
      context.db.posts.findByUserId(parent.id, { limit: args.limit }),
  },
};
```

```txt
parent — это РЕЗУЛЬТАТ РОДИТЕЛЬСКОГО резолвера, а не "родительский
запрос". Цепочка: Query.user возвращает объект user → этот
объект становится parent для ВСЕХ полей внутри user (включая
posts) → User.posts получает parent.id из этого объекта.

Если для поля НЕ определён явный resolver (например, поле
"name" типа User) — используется DEFAULT RESOLVER: он просто
читает parent.name. Поэтому большинство "простых" полей в
resolvers объекте вообще не нужно прописывать — достаточно,
чтобы объект, возвращённый родительским резолвером, уже
содержал нужное свойство.
```

### `context` — создаётся ОДИН РАЗ на запрос, а не на резолвер

```ts
// NestJS / Apollo Server
const server = new ApolloServer({
  schema,
  context: async ({ req }) => ({
    user: await getUserFromToken(req.headers.authorization),
    db: dbConnection,
    // DataLoader создаётся ЗДЕСЬ — НОВЫЙ instance на КАЖДЫЙ
    // запрос, чтобы кэш DataLoader'а не "утекал" между
    // разными пользователями/запросами (см. [N+1 Problem
    // and DataLoader])
    postLoader: createPostLoader(dbConnection),
  }),
});
```

```txt
Senior-нюанс: context — это ОБЪЕКТ, СОЗДАВАЕМЫЙ ОДИН РАЗ
для всего запроса (со всеми его вложенными резолверами), и
ПЕРЕДАВАЕМЫЙ ПО ССЫЛКЕ во КАЖДЫЙ resolver. Это идеальное
место для:
  - данных аутентификации (избегать повторного декодирования
    JWT в каждом резолвере)
  - DataLoader instance'ов (общий batching-кэш на запрос)
  - request-scoped соединений с БД/транзакций

Антипаттерн: создавать DataLoader как GLOBAL singleton —
тогда кэш одного пользователя может "утечь" в ответ другому
пользователю (data leak между запросами).
```

### `info` — редко используется, но решает конкретную проблему overfetching НА УРОВНЕ БД

```ts
// info.fieldNodes / graphql-parse-resolve-info позволяет
// узнать, КАКИЕ ПОДПОЛЯ запросил клиент — и запросить у БД
// ТОЛЬКО эти колонки
const resolvers = {
  Query: {
    user: (_parent, args, context, info) => {
      const requestedFields = getRequestedFields(info); // ['id', 'name']
      // SELECT id, name FROM users WHERE id = ?
      // вместо SELECT * — экономия на больших таблицах
      return context.db.users.findById(args.id, { select: requestedFields });
    },
  },
};
```

```txt
Это решает проблему, симметричную "overfetching от клиента
к серверу" (которую решает GraphQL по умолчанию) —
"overfetching от резолвера к БД". Без анализа info, резолвер
обычно делает SELECT * независимо от того, что запросил
клиент. graphql-tools/graphql-parse-resolve-info — типичные
библиотеки для этого паттерна, чаще применяемого в
высоконагруженных API с широкими таблицами.
```

## Порядок выполнения вложенных резолверов — не строго "сверху вниз последовательно"

```graphql
query {
  user(id: 1) {
    name        # User.name — default resolver, читает parent.name
    posts {     # User.posts — отдельный resolver
      title
      author {  # Post.author — отдельный resolver для КАЖДОГО поста
        name
      }
    }
  }
}
```

```txt
1. Query.user выполняется ПЕРВЫМ (его результат нужен как
   parent для всех полей внутри user)
2. User.name и User.posts — резолверы для ПОЛЕЙ ОДНОГО
   уровня — могут выполняться ПАРАЛЛЕЛЬНО (если оба async)
3. Post.author вызывается ОТДЕЛЬНО для КАЖДОГО элемента
   массива posts — параллельно для каждого

Шаг 3 — это ИСТОЧНИК N+1 problem: если posts вернул 10
постов, Post.author вызовется 10 РАЗ, каждый раз с своим
запросом к БД (если не используется DataLoader). Подробно —
[N+1 Problem and DataLoader].
```

## Связь с другими темами

```txt
[GraphQL Fundamentals]         — конвейер Parse/Validate/Execute,
                                   в котором выполняются резолверы
[N+1 Problem and DataLoader]    — почему резолверы для полей
                                   массива вызываются N раз и
                                   как это решается batching'ом
[Queries, Mutations, and
 Subscriptions]                  — Mutation резолверы и их
                                   отличия (порядок выполнения,
                                   побочные эффекты)
```

## Типичные ошибки на интервью

- **"`!` в схеме — это просто как TypeScript non-null, чисто статическая проверка"** — не знать про null bubbling: ошибка в non-null поле каскадно обнуляет ближайшего nullable-родителя, вплоть до всего `data`.

- **Путать Interface и Union** — не знать, что Union не требует общих полей между членами, а Interface требует, и что оба нуждаются в `__resolveType`.

- **"Зачем нужны Input Types, если есть Object Types?"** — не объяснять, что Object Types могут содержать резолверы/интерфейсы/unions — концепции, бессмысленные для входных данных.

- **"`parent` — это родительский GraphQL-запрос"** — не понимать, что `parent` — это РЕЗУЛЬТАТ родительского резолвера (обычный JS-объект), и default resolver просто читает свойство из него.

- **Создавать DataLoader/кэш как singleton вне `context`** — не видеть риск утечки данных одного пользователя другому через общий кэш между запросами.
