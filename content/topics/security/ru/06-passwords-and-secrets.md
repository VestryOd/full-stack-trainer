<!-- verified: 2026-06-05, corrections: 0 -->
# Пароли, Хеширование и Управление Секретами

## Hashing vs Encryption — принципиальная разница

Хеширование — односторонняя функция, шифрование — двусторонняя. Одна эта разница и решает, что именно делают с паролем.

| | Hashing (хеширование) | Encryption (шифрование) |
|---|---|---|
| Направление | Односторонняя функция | Двусторонняя функция |
| Обратимость | Нельзя "расшифровать" | Можно расшифровать ключом |
| Как выглядит вызов | `bcrypt("password") → "..."` | `AES.encrypt("data", key) ↔ AES.decrypt("...", key)` |
| Для чего применяют | Для паролей | Для данных, которые нужно восстановить |

**Почему пароли не шифруют, а хешируют.** При шифровании сервер вынужден хранить ключ шифрования. Утечка базы данных вместе с ключом восстанавливает все пароли разом. А для сравнения пароля при логине шифрование и не нужно: достаточно хешировать введённый пароль и сравнить хеши.

## SHA-256 и почему он плох для паролей

SHA-256 — криптографически стойкая хеш-функция из семейства Secure Hash Algorithm, разработанная для скорости (хеширование файлов, цифровые подписи). Эта же скорость делает её непригодной для паролей.

Производительность SHA-256 зависит только от железа, на котором он считается:

- CPU (центральный процессор), 2024: ~1 млрд хешей/сек.
- GPU (графический процессор), карта `RTX 4090`: ~23 млрд хешей/сек.
- Специализированное оборудование, ASIC (микросхема под один алгоритм): триллионы/сек.

Перебор словаря на 10 млн паролей показывает, что эта скорость даёт злоумышленнику:

- SHA-256: ~0.01 секунды на GPU.
- bcrypt (cost=12): ~3 часа на GPU.
- Argon2id (рекомендуемые параметры): дни/недели.

Rainbow Tables — это предвычисленные таблицы `{password → SHA256-hash}`. При отсутствии соли поиск по такой таблице мгновенно даёт пароль по хешу. Защита — соль: она делает rainbow tables бесполезными.

## bcrypt — детальный механизм

bcrypt солит пароль за вас. Хеширование генерирует случайную соль и встраивает её в возвращаемую строку, а `bcrypt.compare` достаёт эту соль обратно.

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

**Как bcrypt защищает от атак:**

1. **Медленность.** Он намеренно дорог по вычислениям, поэтому перебор нереален.
2. **Соль.** Она уникальна для каждого пароля, поэтому одинаковые пароли дают разные хеши. Rainbow tables против неё бесполезны, а если база данных утекла, никто не сможет "сравнить" два аккаунта с одним паролем.
3. **Адаптивность.** При росте вычислительной мощности вы увеличиваете cost factor.

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

Четыре способа отдать секрет злоумышленнику, и все четыре встречаются в реальных репозиториях.

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

Где секрету можно лежать, зависит от окружения, и таких уровней три.

**Уровень 1: Development.**

- Файл `.env`, перечисленный в `.gitignore`.
- Читается в коде как `process.env.JWT_SECRET`.
- Достаточно для локальной разработки.

**Уровень 2: Staging и непрерывная интеграция (CI).**

- GitHub Actions Secrets или GitLab CI Variables.
- Зашифрованы платформой, не видны в логах.
- Автоматически подставляются в CI pipeline.

**Уровень 3: Production.** Секрет лежит в управляемом хранилище:

- Secrets Manager в Amazon Web Services (AWS).
- AWS Parameter Store, тип `SecureString`.
- HashiCorp Vault.
- Azure Key Vault или Secret Manager в Google Cloud Platform (GCP).

Преимущества управляемого хранилища:

- Ротация без деплоя приложения.
- Журнал доступа: кто и когда обращался к секрету.
- Принцип минимальных привилегий через роли IAM (identity and access management).
- Автоматическая ротация паролей RDS (Relational Database Service) в AWS.

```typescript
// Получение секрета из AWS Secrets Manager (AWS SDK v3)
import {
  SecretsManagerClient,
  GetSecretValueCommand,
} from '@aws-sdk/client-secrets-manager';

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

Ротировать секрет заставляют три причины:

1. Ключ утёк, и ротация минимизирует окно, в течение которого он полезен.
2. Этого требует комплаенс. Payment Card Industry Data Security Standard (PCI DSS) и SOC2 (System and Organization Controls) делают ротацию обязательной.
3. Ротация ограничивает ущерб от скомпрометированного ключа.

Паттерн ротации без простоя состоит из четырёх шагов:

1. Выпустить новый секрет `new_secret`.
2. Обновить приложение так, чтобы оно поддерживало **оба** секрета: `old_secret` и `new_secret`. Для проверки JWT (JSON Web Token) это значит сначала пробовать `new_secret`, а при ошибке — `old_secret`.
3. Дождаться истечения всех токенов, подписанных `old_secret`.
4. Удалить `old_secret` из конфигурации.

Ключи подписи ротируются иначе — через JWKS (JSON Web Key Set). Auth Server публикует `/.well-known/jwks.json` и держит несколько ключей одновременно, текущий и предыдущий. Сервисы скачивают публичные ключи автоматически, поэтому ключи меняются без деплоя потребителей.

## Типичные ошибки на интервью

- **"Для паролей можно использовать SHA-256"** — SHA-256 разработан для скорости, не для паролей. GPU вычисляет миллиарды SHA-256 в секунду. Для паролей используйте bcrypt (cost≥12) или Argon2id — они специально медленные и memory-hard.

- **"Пароль нужно зашифровать AES"** — AES (Advanced Encryption Standard) это шифрование, а шифрование обратимо. Если ключ украден → все пароли раскрыты. Хеширование необратимо: даже при утечке хешей — исходный пароль не восстановить без brute force.

- **"Соль хранится отдельно в базе данных"** — bcrypt встраивает соль в результат хеширования. Отдельная колонка не нужна. Вы храните только строку хеша, которая содержит algorithm + cost + salt + hash.

- **"Можно хранить секреты в переменных среды Docker или Kubernetes в открытом виде"** — для production секреты должны быть зашифрованы. Kubernetes Secrets base64-encoded (не зашифрованы) — нужно использовать Sealed Secrets, AWS Secrets Manager, или Vault.

- **"Argon2 и bcrypt взаимозаменяемы — без разницы что выбрать"** — не совсем. Argon2id лучше защищает от GPU-атак благодаря memory-hardness. bcrypt проверен временем и широко поддерживается. Для нового проекта — Argon2id. Для существующего bcrypt — менять не нужно.
