<!-- verified: 2026-06-05, corrections: 0 -->
# Пароли, Хеширование и Управление Секретами

## Hashing vs Encryption — принципиальная разница

```txt
Hashing (хеширование):       Encryption (шифрование):
  Односторонняя функция        Двусторонняя функция
  Нельзя "расшифровать"        Можно расшифровать ключом
  bcrypt("password") → "..."   AES.encrypt("data", key) ↔ AES.decrypt("...", key)
  Используется для паролей     Используется для данных, которые нужно восстановить

Почему пароли НЕ шифруют, а хешируют:
  Если шифровать → сервер хранит ключ шифрования
  При утечке БД + ключа → все пароли восстановлены
  Для сравнения пароля при логине шифрование не нужно:
  достаточно хешировать введённый пароль и сравнить хеши
```

## SHA-256 и почему он плох для паролей

SHA-256 — криптографически безопасная hash-функция, разработанная для скорости (хеширование файлов, digital signatures). Эта же скорость делает её непригодной для паролей.

```txt
SHA-256 производительность:
  CPU (2024): ~1 млрд хешей/сек
  GPU (RTX 4090): ~23 млрд хешей/сек
  Специализированный hardware (ASIC): триллионы/сек

Brute force словаря 10 млн паролей:
  SHA-256: ~0.01 секунды на GPU
  bcrypt (cost=12): ~3 часа на GPU
  Argon2id (рекомендуемые параметры): дни/недели

Rainbow Tables: предвычисленная таблица {password → SHA256-hash}
  При отсутствии salt → мгновенный lookup по хешу
  Защита: Salt делает rainbow tables бесполезными
```

## bcrypt — детальный механизм

```typescript
import bcrypt from 'bcrypt';

// Хеширование при регистрации
async function hashPassword(password: string): Promise<string> {
  const COST_FACTOR = 12; // number of rounds = 2^12 = 4096 итераций
  // bcrypt автоматически: генерирует случайный salt и встраивает его в хеш
  return await bcrypt.hash(password, COST_FACTOR);
  // Результат: "$2b$12$XXXXXXXXXXXXXXXXXXXXXXXX.YYYYYYYYYYYYYYYYYYYYYYYYYYYY"
  //             ^^   ^^ ^^^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  //         algorithm cost      salt (22 chars)         hash (31 chars)
  // Salt хранится ВНУТРИ хеша → не нужна отдельная колонка
}

// Проверка при логине
async function verifyPassword(password: string, hash: string): Promise<boolean> {
  return await bcrypt.compare(password, hash);
  // bcrypt: извлекает salt из hash, вычисляет hash(password + salt), сравнивает
}

// Выбор cost factor:
// cost=10: ~100ms  — минимальный приемлемый уровень
// cost=12: ~400ms  — рекомендуется для большинства приложений (2024)
// cost=14: ~1.6s   — для высокой безопасности, если сервер позволяет задержку
// Правило: выбирай максимальный cost при котором login занимает ~100-500ms
```

```txt
Как bcrypt защищает от атак:
  1. Медленность: intentionally computationally expensive → brute force нереален
  2. Соль: уникальная per-password → одинаковые пароли → разные хеши
     → rainbow tables бесполезны
     → если БД утекла, нельзя "сравнить" два аккаунта с одним паролем
  3. Adaptive: при росте вычислительной мощности — увеличить cost factor
```

## Argon2 — современный стандарт

Argon2 — победитель Password Hashing Competition 2015. Три варианта: Argon2d, Argon2i, Argon2id (рекомендуется).

```typescript
import argon2 from 'argon2';

// Хеширование
async function hashPasswordArgon2(password: string): Promise<string> {
  return await argon2.hash(password, {
    type: argon2.argon2id,   // гибридный вариант: защита от GPU и timing attacks
    memoryCost: 65536,        // 64MB RAM — GPU атаки становятся дорогими
    timeCost: 3,              // 3 итерации
    parallelism: 4,           // 4 потока
  });
}

// Верификация
async function verifyPasswordArgon2(password: string, hash: string): Promise<boolean> {
  return await argon2.verify(hash, password);
}

// Преимущество Argon2 над bcrypt:
// Argon2 использует MEMORY в вычислениях
// Атака с GPU: GPU имеет много ядер но мало RAM на ядро
// memoryCost = 64MB означает что GPU ядро не может параллельно вычислять много хешей
// → атака с GPU практически нивелирована
```

## Управление секретами приложения

### Anti-patterns

```typescript
// ПЛОХО #1: захардкоженные секреты в коде
const JWT_SECRET = 'my-super-secret-key-123';
const DB_URL = 'postgres://admin:password@prod.db.com/mydb';

// ПЛОХО #2: .env файл в git репозитории
// .gitignore ОБЯЗАТЕЛЬНО должен содержать .env, .env.local, .env.production

// ПЛОХО #3: логирование секретов
console.log('Config:', { dbUrl, jwtSecret }); // SECRET IN LOGS!

// ПЛОХО #4: секреты в переменных окружения Docker без encryption
// docker run -e DB_PASSWORD=secret ... # виден в process list
```

### Правильный подход: уровни хранения секретов

```txt
Уровень 1: Development
  .env файл (в .gitignore)
  process.env.JWT_SECRET
  Достаточно для локальной разработки

Уровень 2: Staging/CI
  GitHub Actions Secrets / GitLab CI Variables
  Зашифрованы платформой, не видны в логах
  Автоматически инжектируются в CI pipeline

Уровень 3: Production
  AWS Secrets Manager
  AWS Parameter Store (SecureString)
  HashiCorp Vault
  Azure Key Vault / GCP Secret Manager
  Преимущества:
    - Rotation без деплоя приложения
    - Audit log (кто и когда обращался к секрету)
    - Принцип least privilege (IAM роль)
    - Автоматическая ротация для RDS паролей (AWS)
```

```typescript
// Получение секрета из AWS Secrets Manager (AWS SDK v3)
import { SecretsManagerClient, GetSecretValueCommand } from '@aws-sdk/client-secrets-manager';

const client = new SecretsManagerClient({ region: 'eu-west-1' });

async function getSecret(secretName: string): Promise<Record<string, string>> {
  const command = new GetSecretValueCommand({ SecretId: secretName });
  const response = await client.send(command);
  return JSON.parse(response.SecretString!);
}

// При старте приложения (не на каждый запрос):
async function loadSecrets(): Promise<AppSecrets> {
  const [dbSecrets, authSecrets] = await Promise.all([
    getSecret('myapp/production/database'),
    getSecret('myapp/production/auth'),
  ]);
  return {
    dbUrl: `postgres://${dbSecrets.username}:${dbSecrets.password}@${dbSecrets.host}/mydb`,
    jwtSecret: authSecrets.jwtSecret,
  };
}
```

### Secret Rotation — ротация без downtime

```txt
Зачем ротировать:
  1. При утечке ключа — minimize window of exposure
  2. Compliance требования (PCI DSS, SOC2): обязательная ротация
  3. Ограничить ущерб от скомпрометированного ключа

Паттерн rotation без downtime:
  1. Выпустить новый секрет (new_secret)
  2. Обновить приложение для поддержки ОБОИХ: old_secret + new_secret
     (JWT верификация: попробовать new_secret, при ошибке — old_secret)
  3. Дождаться истечения всех токенов подписанных old_secret
  4. Удалить old_secret из конфигурации

JWT Key Rotation с JWKS:
  Auth Server публикует /.well-known/jwks.json
  Несколько ключей одновременно (текущий + предыдущий)
  Сервисы скачивают публичные ключи автоматически
  → смена ключей без деплоя потребителей
```

## Типичные ошибки на интервью

- **"Для паролей можно использовать SHA-256"** — SHA-256 разработан для скорости, не для паролей. GPU вычисляет миллиарды SHA-256 в секунду. Для паролей используйте bcrypt (cost≥12) или Argon2id — они специально медленные и memory-hard.

- **"Пароль нужно зашифровать AES"** — шифрование обратимо. Если ключ украден → все пароли раскрыты. Хеширование необратимо: даже при утечке хешей — исходный пароль не восстановить без brute force.

- **"Соль хранится отдельно в БД"** — bcrypt встраивает соль в результат хеширования. Отдельная колонка не нужна. Хранишь только hash-строку, которая содержит algorithm + cost + salt + hash.

- **"Можно хранить секреты в переменных среды Docker/K8s в plaintext"** — для production секреты должны быть зашифрованы. Kubernetes Secrets base64-encoded (не зашифрованы) — нужно использовать Sealed Secrets, AWS Secrets Manager, или Vault.

- **"Argon2 и bcrypt взаимозаменяемы — без разницы что выбрать"** — не совсем. Argon2id лучше защищает от GPU-атак благодаря memory-hardness. bcrypt проверен временем и широко поддерживается. Для нового проекта — Argon2id. Для существующего bcrypt — менять не нужно.
