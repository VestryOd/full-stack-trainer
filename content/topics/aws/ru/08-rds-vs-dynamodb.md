<!-- verified: 2026-06-05, corrections: 0 -->
# RDS vs DynamoDB

## RDS — управляемая реляционная БД

RDS (Relational Database Service) — управляемая база данных SQL (Structured Query Language). AWS (Amazon Web Services) берёт на себя эксплуатацию:

- Патчинг.
- Резервные копии: ежедневные, плюс восстановление на любой момент времени в пределах 35 дней.
- Репликацию Multi-AZ (Availability Zone — зона доступности) с автоматическим переключением на резерв за ~60-120 сек.
- Мониторинг.

Вы работаете с обычной PostgreSQL/MySQL — подключаетесь той же строкой подключения.

**Движки, которые запускает RDS:**

- PostgreSQL — самый популярный для fullstack.
- MySQL, MariaDB, Oracle, SQL Server.
- Aurora, разработка AWS: в 5 раз быстрее MySQL, в 3 раза быстрее PostgreSQL.
- Aurora Serverless v2 — автоматическое масштабирование вычислений.

**Как работает Multi-AZ:**

- Primary-инстанс синхронно реплицируется в Standby в другой AZ.
- При падении Primary DNS (Domain Name System) автоматически переключается на Standby за ~1-2 мин.
- Read Replica — это другое: асинхронная репликация, для масштабирования нагрузки на чтение.

**Типичный режим:**

- Production: Multi-AZ + 1-2 Read Replicas.
- Dev и staging: Single-AZ, дешевле.

## DynamoDB — управляемая NoSQL БД

DynamoDB — бессерверное хранилище NoSQL (нереляционное), типа ключ-значение и документного. Серверов для управления нет, масштабирование автоматическое, задержка — единицы миллисекунд на P99 (это самый медленный 1% запросов), SLA (Service Level Agreement — обязательство по доступности) 99.99%. Предсказуемую производительность при любом масштабе оно даёт за счёт отказа от JOIN и гибких запросов.

**Модель данных** — три уровня:

- Таблица (Table).
- Item — документ или запись, до 400KB.
- Attribute — поле.

**Обязательные ключи:**

- Partition Key (hash key) определяет партицию хранения.
- Sort Key (range key) опциональный, позволяет держать несколько item с одним ключом партиции.

**Чего в DynamoDB нет:**

- JOIN — данные денормализуются или вкладываются друг в друга.
- Ограничений по внешним ключам (foreign key constraints).
- Сложных запросов вроде `GROUP BY` и оконных функций.
- Фиксированной схемы.

## DynamoDB Data Modeling — Single Table Design

Single Table Design держит все типы сущностей в одной таблице, а паттерн доступа зашивает в ключи. Классическая ошибка — думать о DynamoDB как о таблицах SQL: таблица Users плюс таблица Orders, соединённые по `userId`.

```typescript
// Паттерн Single Table Design:
// pk (Partition Key) + sk (Sort Key) определяют тип и доступ

interface DynamoItem {
  pk: string; // PRIMARY KEY
  sk: string; // SORT KEY → тип записи
  // Дополнительные поля...
}

// Пользователь:
const user: DynamoItem = {
  pk: 'USER#user-123',
  sk: 'PROFILE',
  name: 'Alice',
  email: 'alice@example.com',
  createdAt: '2024-01-01T00:00:00Z',
};

// Заказ пользователя:
const order: DynamoItem = {
  pk: 'USER#user-123',
  sk: 'ORDER#order-456',
  total: 99.99,
  status: 'shipped',
  items: [{ productId: 'p-1', qty: 2 }],
};

// Запросы по дизайну:
// "Получить пользователя" → Query pk=USER#user-123, sk=PROFILE
// "Получить все заказы" → Query pk=USER#user-123, sk begins_with ORDER#
// "Пользователь + все заказы" → Query pk=USER#user-123 (один запрос!)
```

```typescript
// DynamoDB SDK v3: основные операции
import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import {
  DynamoDBDocumentClient, GetCommand, QueryCommand, PutCommand, UpdateCommand,
} from '@aws-sdk/lib-dynamodb';

const client = DynamoDBDocumentClient.from(new DynamoDBClient({}));

// GetItem — получение по точному ключу (O(1), самый быстрый)
const user = await client.send(new GetCommand({
  TableName: 'AppTable',
  Key: { pk: 'USER#user-123', sk: 'PROFILE' },
}));

// Query — все записи для одного Partition Key
const orders = await client.send(new QueryCommand({
  TableName: 'AppTable',
  KeyConditionExpression: 'pk = :pk AND begins_with(sk, :skPrefix)',
  ExpressionAttributeValues: {
    ':pk': 'USER#user-123',
    ':skPrefix': 'ORDER#',
  },
  ScanIndexForward: false, // последние сначала
}));

// PutItem — создание/замена
await client.send(new PutCommand({
  TableName: 'AppTable',
  Item: { pk: 'USER#user-123', sk: 'PROFILE', name: 'Alice' },
  ConditionExpression: 'attribute_not_exists(pk)', // не перезаписать если есть
}));

// UpdateItem — частичное обновление (не нужно читать весь item)
await client.send(new UpdateCommand({
  TableName: 'AppTable',
  Key: { pk: 'USER#user-123', sk: 'PROFILE' },
  UpdateExpression: 'SET #name = :name, updatedAt = :now',
  ExpressionAttributeNames: { '#name': 'name' }, // name — зарезервированное слово
  ExpressionAttributeValues: { ':name': 'Alicia', ':now': new Date().toISOString() },
}));
```

## Capacity Modes — On-Demand vs Provisioned

Режим ёмкости решает, как вы платите за пропускную способность. Считается всё в единицах ёмкости: RCU (Read Capacity Units) на чтение и WCU (Write Capacity Units) на запись.

**On-Demand Mode (serverless)**

- Авто-масштабирование под нагрузку.
- Оплата: $1.25/million Write RCU, $0.25/million Read RCU.
- Когда: непредсказуемый трафик, dev/staging, новые проекты.

**Provisioned Mode**

- Вы сами задаёте RCU и WCU.
- С Auto Scaling увеличивает и уменьшает их в заданных пределах.
- Дешевле при стабильной нагрузке.
- Когда: production с предсказуемым трафиком.

**Размер одной единицы:**

- 1 RCU = одно строго согласованное чтение или два согласованных в конечном счёте, до 4KB.
- 1 WCU = одна запись, до 1KB.

## Global Secondary Index (GSI) — дополнительные паттерны доступа

GSI — это вторая пара ключей поверх той же таблицы, чтобы искать по атрибуту, который не является ключом партиции. Индекс ниже делает `email` ключом для запроса, чего пара `pk`/`sk` базовой таблицы не позволяет.

```typescript
// CDK: таблица с GSI
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';

const table = new dynamodb.Table(this, 'AppTable', {
  partitionKey: { name: 'pk', type: dynamodb.AttributeType.STRING },
  sortKey: { name: 'sk', type: dynamodb.AttributeType.STRING },
  billingMode: dynamodb.BillingMode.PAY_PER_REQUEST, // On-Demand
  removalPolicy: RemovalPolicy.DESTROY, // только для dev!
});

// GSI: поиск заказов по статусу (email → все записи этого email)
table.addGlobalSecondaryIndex({
  indexName: 'email-index',
  partitionKey: { name: 'email', type: dynamodb.AttributeType.STRING },
  sortKey: { name: 'sk', type: dynamodb.AttributeType.STRING },
  projectionType: dynamodb.ProjectionType.INCLUDE,
  nonKeyAttributes: ['name', 'createdAt'],
});

// Запрос через GSI:
const result = await client.send(new QueryCommand({
  TableName: 'AppTable',
  IndexName: 'email-index', // указываем GSI
  KeyConditionExpression: 'email = :email',
  ExpressionAttributeValues: { ':email': 'alice@example.com' },
}));
```

## RDS vs DynamoDB — матрица выбора

Десять строк решают почти любой случай:

| | RDS (PostgreSQL) | DynamoDB |
|---|---|---|
| Схема | Строгая, миграции | Гибкая, без схемы |
| Запросы | Полный SQL, включая JOIN | По ключу: `Query`, `GetItem` |
| Масштабирование записи | Вертикальное, по инстансу | Горизонтальное, автоматическое |
| Потолок масштаба | ~100k TPS (транзакций в секунду) на Aurora | Не ограничен, миллионы TPS |
| Задержка | 1-10ms, плавает | Единицы миллисекунд, предсказуемо |
| Транзакции | Полный ACID (атомарность, согласованность, изоляция, устойчивость) | Ограниченные: 25 items, 5 таблиц |
| Связи | Внешние ключи и JOIN из коробки | Нужна денормализация |
| Холодный старт с Lambda | Накладные расходы на соединение | Только вызов SDK (software development kit), соединений нет |
| Эксплуатация | Управление инстансом | Полностью serverless |
| Модель оплаты | За час инстанса | За запрос (On-Demand) |

**Выбирайте RDS, когда:**

- Связи между сущностями сложные: e-commerce, CRM (управление отношениями с клиентами), ERP (планирование ресурсов предприятия).
- Нужны гибкие SQL-запросы для аналитики и отчётов.
- ACID-транзакции критичны — финансы, инвентарь.
- Команда знает SQL, а паттерны доступа не определены заранее.
- Это стандартный fullstack-проект (Next.js + NestJS + PostgreSQL).

**Выбирайте DynamoDB, когда:**

- Требуется масштаб: миллионы RPS (запросов в секунду), IoT (Internet of Things — интернет вещей), gaming, social feed.
- Паттерны доступа известны заранее и просты.
- Бэкенд на Lambda, и проблемы пула соединений просто нет.
- Архитектура serverless, постоянных инстансов нет.
- Нужен session store, event log или real-time leaderboard.
- Предсказуемо низкая задержка обязательна.

## Типичные ошибки на интервью

- **"DynamoDB — это просто быстрая NoSQL, можно использовать везде вместо PostgreSQL"** — принципиальная разница: DynamoDB требует знания паттернов доступа **до** проектирования схемы. Если паттерны изменятся — схема меняется тяжело. PostgreSQL: можно добавить индекс и новый запрос без реструктуризации данных.

- **"DynamoDB поддерживает транзакции, значит как PostgreSQL"** — транзакции DynamoDB ограничены: максимум 25 items и 5 таблиц за раз, и вы платите 2x RCU/WCU. PostgreSQL: ACID транзакции без ограничений по количеству строк, реальные FOREIGN KEY constraints.

- **"Для Lambda лучше DynamoDB потому что быстрее"** — правда о соединениях: Lambda + RDS имеет проблему connection pool exhaustion (1000 Lambda = 1000 соединений). Решение: RDS Proxy. DynamoDB: stateless HTTP-запросы, нет проблемы соединений. Но "быстрее" — зависит от запроса: сложный JOIN в PostgreSQL может быть быстрее, чем несколько вызовов `GetItem` в DynamoDB.

- **"Single Table Design обязателен в DynamoDB"** — это лучшая практика, не требование. Для небольших проектов или начала — можно использовать несколько таблиц (Multi-Table Design). Single Table оптимально для high-traffic или когда нужны транзакции между разными типами сущностей.

- **"RDS Aurora — это просто дорогой PostgreSQL"** — у Aurora другая архитектура хранилища. Хранилище общее и распределённое, растёт автоматически и доходит до 128TB. Read Replicas до 15 против 5 у RDS, переключение на резерв <30 секунд против 60-120 у RDS. Aurora Serverless v2 — автоматическое масштабирование вычислений без предварительного выделения ресурсов.
