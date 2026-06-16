<!-- verified: 2026-06-05, corrections: 0 -->
# RDS vs DynamoDB

## RDS — управляемая реляционная БД

RDS (Relational Database Service) — managed SQL база данных. AWS управляет: patching, backup (daily + point-in-time restore до 35 дней), Multi-AZ replication (автоматический failover ~60-120 сек), monitoring. Вы работаете с обычной PostgreSQL/MySQL — подключаетесь той же строкой подключения.

```txt
Движки RDS:
  PostgreSQL (самый популярный для fullstack)
  MySQL
  MariaDB
  Oracle
  SQL Server
  Aurora (AWS-разработка, 5x быстрее MySQL, 3x быстрее PostgreSQL)
  Aurora Serverless v2 — автоматическое масштабирование вычислений

RDS Multi-AZ:
  Primary instance (синхронная репликация) → Standby в другой AZ
  При падении Primary: DNS автоматически переключается на Standby (~1-2 мин)
  Read Replica: асинхронная репликация, для scale read-нагрузки

Типичный режим:
  Production: Multi-AZ + 1-2 Read Replicas
  Dev/Staging: Single-AZ (дешевле)
```

## DynamoDB — managed NoSQL БД

DynamoDB — serverless key-value/document store: нет серверов для управления, автоматическое масштабирование, single-digit millisecond latency (P99), 99.99% SLA. Гарантирует предсказуемую производительность при любом масштабе за счёт отказа от JOIN и гибких запросов.

```txt
Модель данных:
  Таблица (Table)
  Item (документ/запись, до 400KB)
  Attribute (поле)

Обязательные ключи:
  Partition Key (hash key): определяет партицию хранения
  Sort Key (range key): опциональный, позволяет несколько item с одним PK

Нет:
  JOIN — данные денормализуются или вложены
  Foreign Key Constraints
  Сложных запросов (GROUP BY, WINDOW FUNCTIONS)
  Фиксированной схемы
```

## DynamoDB Data Modeling — Single Table Design

```typescript
// Классическая ошибка: думать о DynamoDB как о SQL таблицах
// В SQL: Users таблица + Orders таблица → JOIN по userId
// В DynamoDB: Single Table — всё в одной таблице, ключи — паттерны доступа

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
import { DynamoDBDocumentClient, GetCommand, QueryCommand, PutCommand, UpdateCommand } from '@aws-sdk/lib-dynamodb';

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

```txt
On-Demand Mode (Serverless):
  Авто-масштабирование под нагрузку
  Оплата: $1.25/million Write RCU, $0.25/million Read RCU
  Когда: непредсказуемый трафик, dev/staging, новые проекты

Provisioned Mode:
  Задаёшь RCU (Read Capacity Units) + WCU (Write Capacity Units)
  С Auto Scaling: увеличивает/уменьшает в заданных пределах
  Дешевле при стабильной нагрузке
  Когда: production с предсказуемым трафиком

Read/Write Capacity Units:
  1 RCU = 1 strongly consistent read или 2 eventually consistent read (до 4KB)
  1 WCU = 1 write (до 1KB)
```

## Global Secondary Index (GSI) — дополнительные паттерны доступа

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

```txt
                    RDS (PostgreSQL)      DynamoDB
Schema:             Strict, migrations    Flexible, schema-less
Query:              Full SQL (JOIN etc)   Key-based (Query/GetItem)
Scale Write:        Vertical (instance)   Horizontal (auto)
Max Scale:          ~100k TPS (Aurora)    Unlimited (millions TPS)
Latency:            1-10ms (variable)     Single-digit ms (predictable)
Transactions:       Full ACID             Limited (25 items/5 tables)
Relations:          Native (FK, JOIN)     Denormalization required
Cold Start (Lambda):Connection overhead   SDK only (no connections!)
Operational:        Instance management   Fully serverless
Cost Model:         Per instance/hour     Per request (On-Demand)

Выбирай RDS когда:
  ✓ Сложные связи между сущностями (e-commerce, CRM, ERP)
  ✓ Нужны гибкие SQL-запросы (аналитика, отчёты)
  ✓ ACID транзакции критичны (финансы, инвентарь)
  ✓ Команда знает SQL, паттерны доступа не определены заранее
  ✓ Стандартный fullstack проект (Next.js + NestJS + PostgreSQL)

Выбирай DynamoDB когда:
  ✓ Требуется масштаб (миллионы RPS, IoT, gaming, social feed)
  ✓ Паттерны доступа известны заранее и простые
  ✓ Lambda backend (нет connection pool проблемы)
  ✓ Serverless архитектура (нет постоянных инстансов)
  ✓ Session store, event log, real-time leaderboard
  ✓ Предсказуемая low-latency latency обязательна
```

## Типичные ошибки на интервью

- **"DynamoDB — это просто быстрая NoSQL, можно использовать везде вместо PostgreSQL"** — принципиальная разница: DynamoDB требует знания паттернов доступа ДО проектирования схемы. Если паттерны изменятся — схема меняется тяжело. PostgreSQL: можно добавить индекс и новый запрос без реструктуризации данных.

- **"DynamoDB поддерживает транзакции, значит как PostgreSQL"** — транзакции DynamoDB ограничены: максимум 25 items и 5 таблиц за раз, платишь 2x RCU/WCU. PostgreSQL: ACID транзакции без ограничений по количеству строк, реальные FOREIGN KEY constraints.

- **"Для Lambda лучше DynamoDB потому что быстрее"** — правда о соединениях: Lambda + RDS имеет проблему connection pool exhaustion (1000 Lambda = 1000 соединений). Решение: RDS Proxy. DynamoDB: stateless HTTP-запросы, нет проблемы соединений. Но "быстрее" — зависит от запроса: сложный JOIN в PostgreSQL может быть быстрее, чем несколько GetItem в DynamoDB.

- **"Single Table Design обязателен в DynamoDB"** — это лучшая практика, не требование. Для небольших проектов или начала — можно использовать несколько таблиц (Multi-Table Design). Single Table оптимально для high-traffic или когда нужны транзакции между разными типами сущностей.

- **"RDS Aurora — это просто дорогой PostgreSQL"** — Aurora имеет другую архитектуру storage: shared distributed storage до 128TB, автоматически растущий, до 15 Read Replicas (vs 5 у RDS), failover <30 секунд (vs 60-120 у RDS). Aurora Serverless v2 — автоматическое масштабирование вычислений без предварительного provisioning.
