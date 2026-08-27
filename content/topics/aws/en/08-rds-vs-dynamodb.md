# RDS vs DynamoDB

## RDS — managed relational database

RDS (Relational Database Service) is a managed SQL (Structured Query Language) database. AWS (Amazon Web Services) handles the operations work:

- Patching.
- Backups: daily, plus point-in-time restore up to 35 days.
- Multi-AZ (Availability Zone) replication, with automatic failover in ~60-120 sec.
- Monitoring.

You connect with a standard connection string as if it were a regular PostgreSQL/MySQL instance.

**Engines RDS runs:**

- PostgreSQL — most popular for fullstack.
- MySQL, MariaDB, Oracle, SQL Server.
- Aurora, AWS-developed: 5x faster than MySQL, 3x faster than PostgreSQL.
- Aurora Serverless v2 — automatic compute scaling.

**How Multi-AZ works:**

- The primary instance replicates synchronously to a standby in another AZ.
- If the primary fails, DNS (Domain Name System) auto-switches to the standby in ~1-2 min.
- A Read Replica is a different thing: async replication, for scaling read load.

**Typical setup:**

- Production: Multi-AZ + 1-2 Read Replicas.
- Dev/staging: Single-AZ, cheaper.

## DynamoDB — managed NoSQL database

DynamoDB is a serverless NoSQL (non-relational) key-value and document store. There are no servers to manage and scaling is automatic. Latency is single-digit milliseconds at P99 (the slowest 1% of requests), and the SLA (Service Level Agreement) is 99.99%. It achieves predictable performance at any scale by dropping JOINs and flexible queries.

**Data model** — three levels:

- Table.
- Item: a document or record, up to 400KB.
- Attribute: a field.

**Required keys:**

- Partition Key (hash key) determines the storage partition.
- Sort Key (range key) is optional and allows multiple items with the same partition key.

**What DynamoDB does not have:**

- JOIN — data is denormalized or nested instead.
- Foreign key constraints.
- Complex queries such as `GROUP BY` and window functions.
- A fixed schema.

## DynamoDB Data Modeling — Single Table Design

Single Table Design keeps every entity type in one table and encodes the access pattern in the keys. The classic mistake is thinking about DynamoDB like SQL tables: a Users table plus an Orders table, joined by `userId`.

```typescript
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
import {
  DynamoDBDocumentClient, GetCommand, QueryCommand, PutCommand, UpdateCommand,
} from '@aws-sdk/lib-dynamodb';

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

Capacity mode decides how you pay for throughput. Both modes are priced in capacity units: RCU (Read Capacity Units) for reads, WCU (Write Capacity Units) for writes.

**On-Demand Mode (serverless)**

- Auto-scales to match load.
- Cost: $1.25/million Write RCU, $0.25/million Read RCU.
- Use when: unpredictable traffic, dev/staging, new projects.

**Provisioned Mode**

- You set RCU and WCU yourself.
- With Auto Scaling it scales within the bounds you set.
- Cheaper for stable, predictable load.
- Use when: production with predictable traffic.

**Size of one unit:**

- 1 RCU = 1 strongly consistent read, or 2 eventually consistent reads, up to 4KB.
- 1 WCU = 1 write, up to 1KB.

## Global Secondary Index (GSI) — additional access patterns

A GSI is a second pair of keys over the same table, so you can query by an attribute that is not the partition key. The index below makes `email` a queryable key, which the base table's `pk`/`sk` pair does not allow.

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

Ten rows decide almost every case:

| | RDS (PostgreSQL) | DynamoDB |
|---|---|---|
| Schema | Strict, migrations | Flexible, schema-less |
| Query | Full SQL, JOIN included | Key-based: `Query`, `GetItem` |
| Write scale | Vertical, by instance | Horizontal, automatic |
| Max scale | ~100k TPS (transactions per second) with Aurora | Unlimited, millions of TPS |
| Latency | 1-10ms, variable | Single-digit ms, predictable |
| Transactions | Full ACID (atomicity, consistency, isolation, durability) | Limited: 25 items, 5 tables |
| Relations | Native foreign keys and JOIN | Denormalization required |
| Cold start with Lambda | Connection overhead | Only an SDK (software development kit) call, no connections |
| Operational | Instance management | Fully serverless |
| Cost model | Per instance-hour | Per request (On-Demand) |

**Choose RDS when:**

- Entity relationships are complex: e-commerce, CRM (customer relationship management), ERP (enterprise resource planning).
- Flexible SQL queries are needed for analytics and reports.
- ACID transactions are critical, as in finance or inventory.
- The team knows SQL and access patterns are not known upfront.
- It is a standard fullstack project (Next.js + NestJS + PostgreSQL).

**Choose DynamoDB when:**

- Scale is required: millions of RPS (requests per second), IoT (Internet of Things), gaming, social feed.
- Access patterns are known upfront and simple.
- The backend is Lambda, so there is no connection pool problem.
- The architecture is serverless, with no persistent instances.
- You need a session store, an event log or a real-time leaderboard.
- Predictable low latency is mandatory.

## Common interview mistakes

- **"DynamoDB is just a fast NoSQL — you can use it everywhere instead of PostgreSQL"** — there's a fundamental difference. DynamoDB requires knowing the access patterns **before** you design the schema. If patterns change, restructuring data is painful. PostgreSQL: add an index and a new query without restructuring data.

- **"DynamoDB supports transactions, so it's like PostgreSQL"** — DynamoDB transactions are limited: maximum 25 items and 5 tables per transaction, costs 2x RCU/WCU. PostgreSQL: full ACID transactions with no row-count limits, real FOREIGN KEY constraints.

- **"Lambda should use DynamoDB because it's faster"** — the truth about connections: Lambda + RDS has a connection pool exhaustion problem (1000 Lambdas = 1000 connections). Solution: RDS Proxy. DynamoDB: stateless HTTP requests, no connection problem. But "faster" depends on the query: a complex JOIN in PostgreSQL can be faster than several `GetItem` calls in DynamoDB.

- **"Single Table Design is mandatory in DynamoDB"** — it's a best practice, not a requirement. For small projects or early stages, Multi-Table Design works. Single Table is optimal for high-traffic workloads or when you need transactions between different entity types.

- **"RDS Aurora is just expensive PostgreSQL"** — Aurora has a different storage architecture. Storage is shared and distributed, grows automatically and reaches 128TB. It allows up to 15 Read Replicas, against 5 for RDS, and failover takes under 30 seconds, against 60-120 for RDS. Aurora Serverless v2 automatically scales compute without pre-provisioning.
