# RDS vs DynamoDB

## RDS — managed relational database

RDS (Relational Database Service) is a managed SQL database. AWS handles: patching, backups (daily + point-in-time restore up to 35 days), Multi-AZ replication (automatic failover ~60-120 sec), monitoring. You connect with a standard connection string as if it were a regular PostgreSQL/MySQL instance.

```txt
RDS engines:
  PostgreSQL (most popular for fullstack)
  MySQL
  MariaDB
  Oracle
  SQL Server
  Aurora (AWS-developed, 5x faster than MySQL, 3x faster than PostgreSQL)
  Aurora Serverless v2 — automatic compute scaling

RDS Multi-AZ:
  Primary instance (synchronous replication) → Standby in another AZ
  If Primary fails: DNS auto-switches to Standby (~1-2 min)
  Read Replica: async replication, for scaling read load

Typical setup:
  Production: Multi-AZ + 1-2 Read Replicas
  Dev/Staging: Single-AZ (cheaper)
```

## DynamoDB — managed NoSQL database

DynamoDB is a serverless key-value/document store: no servers to manage, automatic scaling, single-digit millisecond latency (P99), 99.99% SLA. It achieves predictable performance at any scale by dropping JOINs and flexible queries.

```txt
Data model:
  Table
  Item (document/record, up to 400KB)
  Attribute (field)

Required keys:
  Partition Key (hash key): determines the storage partition
  Sort Key (range key): optional, allows multiple items with the same PK

No:
  JOIN — data is denormalized or nested
  Foreign Key Constraints
  Complex queries (GROUP BY, WINDOW FUNCTIONS)
  Fixed schema
```

## DynamoDB Data Modeling — Single Table Design

```typescript
// Classic mistake: thinking about DynamoDB like SQL tables
// In SQL: Users table + Orders table → JOIN by userId
// In DynamoDB: Single Table — everything in one table, keys define access patterns

// Single Table Design pattern:
// pk (Partition Key) + sk (Sort Key) define the type and access

interface DynamoItem {
  pk: string; // PRIMARY KEY
  sk: string; // SORT KEY → record type
  // Additional fields...
}

// User:
const user: DynamoItem = {
  pk: 'USER#user-123',
  sk: 'PROFILE',
  name: 'Alice',
  email: 'alice@example.com',
  createdAt: '2024-01-01T00:00:00Z',
};

// User's order:
const order: DynamoItem = {
  pk: 'USER#user-123',
  sk: 'ORDER#order-456',
  total: 99.99,
  status: 'shipped',
  items: [{ productId: 'p-1', qty: 2 }],
};

// Access patterns by design:
// "Get user" → Query pk=USER#user-123, sk=PROFILE
// "Get all orders" → Query pk=USER#user-123, sk begins_with ORDER#
// "User + all orders" → Query pk=USER#user-123 (single request!)
```

```typescript
// DynamoDB SDK v3: core operations
import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { DynamoDBDocumentClient, GetCommand, QueryCommand, PutCommand, UpdateCommand } from '@aws-sdk/lib-dynamodb';

const client = DynamoDBDocumentClient.from(new DynamoDBClient({}));

// GetItem — retrieval by exact key (O(1), fastest operation)
const user = await client.send(new GetCommand({
  TableName: 'AppTable',
  Key: { pk: 'USER#user-123', sk: 'PROFILE' },
}));

// Query — all records for one Partition Key
const orders = await client.send(new QueryCommand({
  TableName: 'AppTable',
  KeyConditionExpression: 'pk = :pk AND begins_with(sk, :skPrefix)',
  ExpressionAttributeValues: {
    ':pk': 'USER#user-123',
    ':skPrefix': 'ORDER#',
  },
  ScanIndexForward: false, // most recent first
}));

// PutItem — create/replace
await client.send(new PutCommand({
  TableName: 'AppTable',
  Item: { pk: 'USER#user-123', sk: 'PROFILE', name: 'Alice' },
  ConditionExpression: 'attribute_not_exists(pk)', // don't overwrite if exists
}));

// UpdateItem — partial update (no need to read the whole item)
await client.send(new UpdateCommand({
  TableName: 'AppTable',
  Key: { pk: 'USER#user-123', sk: 'PROFILE' },
  UpdateExpression: 'SET #name = :name, updatedAt = :now',
  ExpressionAttributeNames: { '#name': 'name' }, // name is a reserved word
  ExpressionAttributeValues: { ':name': 'Alicia', ':now': new Date().toISOString() },
}));
```

## Capacity Modes — On-Demand vs Provisioned

```txt
On-Demand Mode (Serverless):
  Auto-scales to match load
  Cost: $1.25/million Write RCU, $0.25/million Read RCU
  Use when: unpredictable traffic, dev/staging, new projects

Provisioned Mode:
  You set RCU (Read Capacity Units) + WCU (Write Capacity Units)
  With Auto Scaling: scales within set bounds
  Cheaper for stable, predictable load
  Use when: production with predictable traffic

Read/Write Capacity Units:
  1 RCU = 1 strongly consistent read or 2 eventually consistent reads (up to 4KB)
  1 WCU = 1 write (up to 1KB)
```

## Global Secondary Index (GSI) — additional access patterns

```typescript
// CDK: table with GSI
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';

const table = new dynamodb.Table(this, 'AppTable', {
  partitionKey: { name: 'pk', type: dynamodb.AttributeType.STRING },
  sortKey: { name: 'sk', type: dynamodb.AttributeType.STRING },
  billingMode: dynamodb.BillingMode.PAY_PER_REQUEST, // On-Demand
  removalPolicy: RemovalPolicy.DESTROY, // dev only!
});

// GSI: find by email (email → all records for that email)
table.addGlobalSecondaryIndex({
  indexName: 'email-index',
  partitionKey: { name: 'email', type: dynamodb.AttributeType.STRING },
  sortKey: { name: 'sk', type: dynamodb.AttributeType.STRING },
  projectionType: dynamodb.ProjectionType.INCLUDE,
  nonKeyAttributes: ['name', 'createdAt'],
});

// Query via GSI:
const result = await client.send(new QueryCommand({
  TableName: 'AppTable',
  IndexName: 'email-index', // specify the GSI
  KeyConditionExpression: 'email = :email',
  ExpressionAttributeValues: { ':email': 'alice@example.com' },
}));
```

## RDS vs DynamoDB — decision matrix

```txt
                      RDS (PostgreSQL)       DynamoDB
Schema:               Strict, migrations     Flexible, schema-less
Query:                Full SQL (JOIN etc.)   Key-based (Query/GetItem)
Write Scale:          Vertical (instance)    Horizontal (auto)
Max Scale:            ~100k TPS (Aurora)     Unlimited (millions TPS)
Latency:              1-10ms (variable)      Single-digit ms (predictable)
Transactions:         Full ACID              Limited (25 items/5 tables)
Relations:            Native (FK, JOIN)      Denormalization required
Cold Start (Lambda):  Connection overhead    SDK only (no connections!)
Operational:          Instance management    Fully serverless
Cost Model:           Per instance/hour      Per request (On-Demand)

Choose RDS when:
  ✓ Complex entity relationships (e-commerce, CRM, ERP)
  ✓ Flexible SQL queries needed (analytics, reports)
  ✓ ACID transactions are critical (finance, inventory)
  ✓ Team knows SQL, access patterns not known upfront
  ✓ Standard fullstack project (Next.js + NestJS + PostgreSQL)

Choose DynamoDB when:
  ✓ Scale is required (millions RPS, IoT, gaming, social feed)
  ✓ Access patterns are known upfront and simple
  ✓ Lambda backend (no connection pool problem)
  ✓ Serverless architecture (no persistent instances)
  ✓ Session store, event log, real-time leaderboard
  ✓ Predictable low latency is mandatory
```

## Common interview mistakes

- **"DynamoDB is just a fast NoSQL — you can use it everywhere instead of PostgreSQL"** — there's a fundamental difference: DynamoDB requires knowing the access patterns BEFORE designing the schema. If patterns change, restructuring data is painful. PostgreSQL: add an index and a new query without restructuring data.

- **"DynamoDB supports transactions, so it's like PostgreSQL"** — DynamoDB transactions are limited: maximum 25 items and 5 tables per transaction, costs 2x RCU/WCU. PostgreSQL: full ACID transactions with no row-count limits, real FOREIGN KEY constraints.

- **"Lambda should use DynamoDB because it's faster"** — the truth about connections: Lambda + RDS has a connection pool exhaustion problem (1000 Lambdas = 1000 connections). Solution: RDS Proxy. DynamoDB: stateless HTTP requests, no connection problem. But "faster" depends on the query: a complex JOIN in PostgreSQL can be faster than several GetItem calls in DynamoDB.

- **"Single Table Design is mandatory in DynamoDB"** — it's a best practice, not a requirement. For small projects or early stages, Multi-Table Design works. Single Table is optimal for high-traffic workloads or when you need transactions between different entity types.

- **"RDS Aurora is just expensive PostgreSQL"** — Aurora has a different storage architecture: shared distributed storage up to 128TB, automatically growing, up to 15 Read Replicas (vs 5 for RDS), failover <30 seconds (vs 60-120 for RDS). Aurora Serverless v2 automatically scales compute without pre-provisioning.
