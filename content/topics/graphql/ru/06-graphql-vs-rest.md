<!-- verified: 2026-06-05, corrections: 0 -->
# GraphQL vs REST

## Правильный уровень сравнения — архитектурный, а не "что лучше"

Оба подхода — HTTP-протокол, JSON, stateless-запросы. Разница не в "технологии", а в том, КТО контролирует форму ответа и КАКИЕ архитектурные инварианты встроены в протокол.

```txt
REST    — РЕСУРС-ориентированный подход:
          URL = ресурс, HTTP-метод = операция над ресурсом,
          HTTP-статус = результат операции
          Сервер определяет форму ответа каждого эндпоинта

GraphQL — ОПЕРАЦИЯ-ориентированный подход:
          Один URL, операция описана В ТЕЛЕ запроса (query/
          mutation/subscription), клиент определяет форму
          ответа через selection set
```

## Overfetching и Underfetching — где REST "ломается" для сложных клиентов

```txt
Эти проблемы разобраны в [GraphQL Fundamentals] с числовым
примером. Нюанс, который редко упоминают:

REST НЕ обязан всегда возвращать всё: многие публичные REST API
поддерживают sparse fieldsets (например, Google API:
?fields=name,email, JSON:API spec: ?fields[users]=name,email).
Это частично решает overfetching — но это КОНВЕНЦИЯ, а не
встроенный механизм спецификации REST. GraphQL делает это
стандартным поведением из коробки.

Более серьёзная проблема — underfetching для СЛОЖНЫХ UX:
экран "Дашборд" с профилем + уведомлениями + последними
заказами = 3 round-trip в REST (или 1 кастомный эндпоинт
/dashboard, нарушающий ресурс-ориентированность), vs
1 GraphQL-запрос с 3 top-level полями.
```

## Версионирование — хронический pain point REST

```http
# REST — обычно решается через URL-версию или заголовок
GET /v1/users/1
GET /v2/users/1
```

```txt
/v2 = дублирование всей логики, поддержка двух версий
параллельно, рано или поздно "/v3"...
Попытки решить через заголовки (Accept: application/vnd.api.v2+json)
или параметры (?version=2) не решают фундаментальной проблемы:
УДАЛЕНИЕ или ИЗМЕНЕНИЕ поля в существующем эндпоинте — это
BREAKING CHANGE для клиентов.
```

```graphql
# GraphQL — additive evolution без версий
type User {
  id: ID!
  name: String!
  fullName: String @deprecated(reason: "Use 'name' instead")
  email: String
  # Добавляем новые поля — старые клиенты их просто не запрашивают
  phoneNumber: String
}
```

```txt
GraphQL-подход: ДОБАВЛЕНИЕ полей — не breaking change (старые
клиенты не запрашивают их, схема обратно совместима). УДАЛЕНИЕ
поля — breaking change, поэтому поле сначала помечается
@deprecated (инструменты предупредят разработчиков фронтенда
через codegen), мониторится usage (Apollo Studio показывает, кто
ещё использует deprecated-поле), и только после 0% использования —
удаляется.

Это не значит, что GraphQL никогда не делает breaking changes —
ИЗМЕНЕНИЕ ТИПА поля (String → Int), ИЗМЕНЕНИЕ NULLABLE → NON-NULL
— это breaking changes и в GraphQL. Просто инструментарий
(schema registry, breaking-change detection в CI) развит лучше.
```

## Типизация и контракт — OpenAPI vs GraphQL Schema

```txt
REST + OpenAPI:
  - OpenAPI spec — отдельный файл/документация, которая МОЖЕТ
    дрейфовать относительно реальной реализации (если не
    подключено автоматическое тестирование соответствия)
  - Типы генерируются из OpenAPI spec → если spec не обновлена,
    сгенерированные типы не отражают реальный API
  - Нет встроенного механизма проверки совместимости

GraphQL:
  - Схема IS спецификация — сервер физически не может вернуть
    поле, которого нет в схеме (Validate-фаза до выполнения
    резолверов, см. [GraphQL Fundamentals])
  - Introspection даёт АКТУАЛЬНУЮ схему прямо с сервера
  - Codegen (graphql-codegen) генерирует типы из RUNTIME-схемы,
    а не из потенциально устаревшей документации
  - CI может проверять breaking changes (schema diffing)
    автоматически
```

## Кэширование — где REST действительно выигрывает (и как GraphQL компенсирует)

```txt
REST:
  GET /users/1 — кэшируется CDN по URL "из коробки":
    - Cache-Control: max-age=3600
    - ETag + If-None-Match (304 Not Modified)
    - Last-Modified + If-Modified-Since
    - URL = единица кэширования (точная, предсказуемая)

GraphQL:
  POST /graphql — не кэшируется CDN по умолчанию
  (подробнее — [GraphQL Fundamentals], [Performance and Security])

Компенсации в GraphQL:
  1. Persisted Queries → GET-запросы с хэшем в URL → CDN-кэш
  2. @cacheControl директива (Apollo):
     type Post @cacheControl(maxAge: 60) { ... }
     поле в resolver-е: info.cacheControl.setCacheHint()
     → сервер добавляет Cache-Control: max-age=60 к HTTP-ответу
  3. Кэш на уровне клиента (Apollo Client нормализованный кэш)
     — кэширует по id типа, а не по URL, что позволяет одному
     запросу автоматически обновить кэш другого запроса, если
     оба касались одного User { id: "1" }
```

## Семантика ошибок — HTTP-статусы vs errors[]

```txt
REST:    200 OK, 201 Created, 400 Bad Request,
         401 Unauthorized, 404 Not Found, 500 Internal Error
         → Мониторинг через HTTP-статусы — стандартный
           инструмент любой APM/алертинг-системы

GraphQL: почти всегда HTTP 200, даже при ошибках
         (подробнее — [GraphQL Fundamentals])
         → Мониторинг требует парсинга тела ответа,
           GraphQL-aware инструментарий (Apollo Studio)

При этом в GraphQL ошибки СТРУКТУРИРОВАНЫ: каждая ошибка
содержит path (путь к провалившемуся полю в ответе), что
позволяет ТОЧНО определить, какое поле сломалось, а не только
"что-то 500-ит".
```

## Загрузка файлов — где REST проще

```txt
REST: multipart/form-data — нативная поддержка на уровне HTTP,
обработчики есть в любом фреймворке.

GraphQL: файлы — не часть спецификации GraphQL (которая
описывает ТОЛЬКО JSON). Для загрузки файлов нужно либо:
  - graphql-upload (реализует graphql-multipart-request-spec —
    расширение поверх GraphQL) — но с ограничениями (работает
    только с multipart-совместимым клиентом)
  - Гибридный подход: отдельный REST/presigned-S3 URL для
    загрузки файла, GraphQL-мутация только для сохранения
    метаданных — это наиболее чистый architectural pattern для
    production
```

## BFF — наиболее распространённый способ совместного использования

```txt
Frontend
    ↓
GraphQL BFF (Backend For Frontend)
    ↓
  ┌─────────────────────────────────┐
  │ Users REST Service              │
  │ Orders REST Service             │
  │ Notifications gRPC Service      │
  │ External Partner REST API       │
  └─────────────────────────────────┘
```

```txt
GraphQL-слой агрегирует данные из НЕСКОЛЬКИХ downstream-сервисов
(которые могут оставаться REST или gRPC) в ОДИН граф, оптимально
формируя ответ под нужды конкретного клиента (веб, мобайл, TV-
приложение — каждый со своими data requirements).

Downstream-сервисы при этом остаются REST — потому что:
  - они обслуживают ДРУГИЕ клиенты (другие BFF, партнёры, webhook)
  - REST проще для публичных API и стандартизации
  - HTTP-кэширование на межсервисном уровне проще с REST

GraphQL Federation (см. [Performance and Security]) — то же, но
без единого monolithic BFF: каждый сервис владеет своей частью
GraphQL-графа.
```

## Когда выбрать REST, когда GraphQL — честная оценка

```txt
REST предпочтительнее:
  ✓ Публичный API (GitHub v3 REST, Stripe, Twilio) — CDN-кэш,
    широкая поддержка клиентами (curl, HTTPie, Postman "из
    коробки"), нет зависимости от GraphQL-клиента
  ✓ Простой CRUD API без сложных связей между сущностями
  ✓ API с частой загрузкой файлов
  ✓ Когда HTTP-кэширование критично и нет ресурсов на Persisted
    Queries / Apollo Cache Control
  ✓ Webhooks, event-driven интеграции (REST endpoint как
    "приёмник" событий)
  ✓ Маленькая команда с меньшим опытом в GraphQL

GraphQL предпочтительнее:
  ✓ Сложные UI с вложенными связанными данными
  ✓ Несколько клиентов с РАЗНЫМИ data requirements (веб vs
    мобайл vs embedded — каждый запрашивает ровно то, что нужно)
  ✓ BFF-слой над несколькими downstream-сервисами
  ✓ Команды, которым важно type-safe codegen и единый договор
    схемы между frontend и backend
  ✓ Активно эволюционирующий API с частым изменением
    требований клиента (additive evolution без версий)

Наиболее реалистичный production-ответ: REST + GraphQL в одном
проекте — REST для публичного API и webhook-интеграций, GraphQL
как BFF для собственного frontend.
```

## Связь с другими темами

```txt
[GraphQL Fundamentals]            — overfetching/underfetching,
                                      HTTP-семантика GraphQL
[Performance and Security]         — кэширование через Persisted
                                      Queries, Federation как
                                      альтернатива monolithic BFF
[Queries, Mutations, and
 Subscriptions]                     — сравнение Mutation с
                                      REST-глаголами POST/PUT/
                                      PATCH/DELETE и idempotency
```

## Типичные ошибки на интервью

- **"GraphQL заменит REST"** — не понимать, что они решают разные задачи: GraphQL не имеет нативного CDN-кэширования, усложняет загрузку файлов, и большинство публичных API останутся REST — именно из-за простоты консьюминга и HTTP-кэша.

- **"REST типизирован хуже, потому что нет схемы"** — не упоминать OpenAPI/Swagger как стандарт типизации REST API, и не объяснять разницу в гарантиях (OpenAPI может дрейфовать, GraphQL-схема IS runtime-контракт).

- **"В GraphQL нет версионирования — значит всё всегда ломается"** — не знать про @deprecated + additive evolution как основную стратегию, не упоминать breaking-change detection через schema diffing в CI.

- **"GraphQL кэш — это Apollo Client"** — путать клиентский нормализованный кэш с HTTP-кэшированием; не знать про @cacheControl и Persisted Queries как способ получить CDN-кэш для GraphQL.

- **"Нужно выбрать: REST или GraphQL"** — не предлагать гибридный BFF-паттерн (GraphQL как aggregation layer над REST-микросервисами) как наиболее распространённое production-решение.
