# Логин один раз, а не в каждом тесте

Состояние входа снимают один раз в отдельном проекте и раздают тестам файлом.
Снимок — это набор cookies и записей хранилища, а не «оставленный открытым
браузер». Поэтому вход перестаёт занимать место в каждом тесте и в каждом отчёте.

## Снимок состояния — это файл с cookies и хранилищем

Метод `storageState` забирает у контекста всё, что определяет сессию, и кладёт в
файл.

```ts
// tests/auth.setup.ts
import { test as setup, expect } from '@playwright/test';

setup('вход под Марией', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill('maria@example.com');
  await page.getByLabel('Пароль').fill('correct-horse');
  await page.getByRole('button', { name: 'Войти' }).click();
  await expect(page.getByRole('heading', { name: 'Задачи' })).toBeVisible();

  await page.context().storageState({ path: '.auth/maria.json' });
});
```

Получившийся файл читается глазами. Ниже настоящий снимок со стенда этой темы:
приложение кладёт токен в `localStorage`, а сервер ставит cookie сессии.

```json
{
  "cookies": [
    {
      "name": "session",
      "value": "bWFyaWFAZXhhbXBsZS5jb20=",
      "domain": "localhost",
      "path": "/",
      "expires": -1,
      "httpOnly": false,
      "secure": false,
      "sameSite": "Lax"
    }
  ],
  "origins": [
    {
      "origin": "http://localhost:3000",
      "localStorage": [
        { "name": "token", "value": "tok-bWFyaWFAZXhhbXBsZS5jb20=" }
      ]
    }
  ]
}
```

Ключей ровно два, и это готовый ответ на вопрос «что войдёт в снимок».

| что | попадает в снимок |
|---|---|
| cookies, включая `httpOnly` | да |
| `localStorage` по каждому origin | да |
| `sessionStorage` | нет |
| `IndexedDB` | только с опцией `indexedDB: true` |
| открытые вкладки, история, кэш | нет |
| ключи доступа `WebAuthn` | только с опцией `credentials: true` |

Отсутствие `sessionStorage` проверяется в одну строку: тест, запущенный со
снимком, видит `token` из `localStorage` и `null` вместо черновика. Вывод такого
прогона приведён ниже, в разделе про проект подготовки.

Приложение, которое держит сессию в `sessionStorage`, через снимок не
восстановить. Такой сессией занимается отдельная подготовка перед тестом —
фикстура, которая сама заполняет хранилище нужными значениями.

## Где живёт состояние входа

Снимок проходит три остановки: проект подготовки, файл, контекст теста.

```txt
              Где живёт состояние входа
┌──────────────────────────────────────┐
│ Проект setup                         │
│ вход через форму, один раз на прогон │
└──────────────────────────────────────┘
                    │  context.storageState({ path })
                    ▼
┌──────────────────────────────────────┐
│ Файл .auth/maria.json                │
│ cookies и localStorage по origin     │
└──────────────────────────────────────┘
                    │  use: { storageState } в проекте
                    ▼
┌──────────────────────────────────────┐
│ Контекст теста                       │
│ создаётся уже заполненным из файла   │
└──────────────────────────────────────┘
                    │  фикстура page как обычно
                    ▼
┌──────────────────────────────────────┐
│ Страница теста                       │
│ открывается сразу под пользователем  │
└──────────────────────────────────────┘
sessionStorage в файл не попадает, а срок жизни токена
   живёт внутри значения: файл стареет вместе с ним
```

Ни на одной остановке браузер не остаётся открытым. Контекст теста создаётся
обычным порядком и просто получает содержимое файла до первого перехода.

## Проект-зависимость готовит состояние до тестов

Подготовку оформляют отдельным проектом, а тесты объявляют его зависимостью.

```ts
// playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  projects: [
    { name: 'setup', testMatch: /.*\.setup\.ts/ },
    {
      name: 'chromium',
      use: { storageState: '.auth/maria.json' },
      testIgnore: /.*\.setup\.ts/,
      dependencies: ['setup'],          // сначала вход, потом всё остальное
    },
  ],
});
```

Поле `dependencies` задаёт порядок: проект `setup` проходит целиком, и только
после этого стартуют зависимые проекты. Если вход упал, зависимые тесты не
запускаются вовсе — и это правильно, потому что все они упали бы одинаково.

```txt
Running 2 tests using 1 worker

  ✓  1 [setup] › tests/auth.setup.ts:3:6 › вход под Марией (394ms)
  token из снимка:        tok-bWFyaWFAZXhhbXBsZS5jb20=
  sessionStorage.draft:   null
  cookies:                session
  ✓  2 [chromium] › tests/list.spec.ts:3:5 › список открыт (127ms)

  2 passed (1.4s)
```

Имя проекта в квадратных скобках показывает, что происходит. Полезная привычка:
каталог `.auth` добавляют в `.gitignore`, потому что там лежат живые сессии.

## Несколько ролей — несколько снимков

Роли отличаются только именем файла, поэтому подготовку пишут циклом.

```ts
// tests/auth.setup.ts
const USERS = [
  { role: 'maria', email: 'maria@example.com', password: 'correct-horse' },
  { role: 'ivan', email: 'ivan@example.com', password: 'stapler-lamp' },
];

for (const user of USERS) {
  setup(`вход: ${user.role}`, async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(user.email);
    await page.getByLabel('Пароль').fill(user.password);
    await page.getByRole('button', { name: 'Войти' }).click();
    await expect(page.getByRole('heading', { name: 'Задачи' })).toBeVisible();

    await page.context().storageState({ path: `.auth/${user.role}.json` });
  });
}
```

Дальше каждый проект берёт свой файл, и один и тот же набор тестов проходит от
имени разных пользователей.

```txt
Running 4 tests using 1 worker

  ✓  1 [setup] › tests/auth.setup.ts:9:8 › вход: maria (193ms)
  ✓  2 [setup] › tests/auth.setup.ts:9:8 › вход: ivan (145ms)
  maria: session=bWFyaWFAZXhh…
  ✓  3 [maria] › tests/roles.spec.ts:3:5 › сессия из снимка (108ms)
  ivan: session=aXZhbkBleGFt…
  ✓  4 [ivan] › tests/roles.spec.ts:3:5 › сессия из снимка (113ms)

  4 passed (1.6s)
```

Когда роль нужна не всему проекту, а нескольким тестам, снимок подключают прямо
в файле.

```ts
// tests/admin.spec.ts
test.use({ storageState: '.auth/ivan.json' });

test('чужие задачи не видны', async ({ page }) => {
  await page.goto('/tasks');
  await expect(page.getByText('Отчёт за май')).toHaveCount(0);
});
```

## Два пользователя в одном тесте живут в двух контекстах

Один тест получает одну сессию, потому что у него один контекст.

```ts
test('задача видна автору и не видна другому', async ({ browser }) => {
  const mariaContext = await browser.newContext({ storageState: '.auth/maria.json' });
  const ivanContext = await browser.newContext({ storageState: '.auth/ivan.json' });

  const maria = await mariaContext.newPage();
  const ivan = await ivanContext.newPage();

  await maria.goto('/tasks');
  await ivan.goto('/tasks');

  await expect(maria.getByText('Отчёт за май')).toBeVisible();
  await expect(ivan.getByText('Отчёт за май')).toHaveCount(0);

  await mariaContext.close();
  await ivanContext.close();
});
```

Оба контекста живут в том же браузере и не видят cookies друг друга. Устройство
этой изоляции разобрано в статье
[Модель Playwright: браузер, контекст, страница](./01-playwright-model.md).

## Токен в снимке стареет

Снимок — это данные с собственным сроком годности, и прогон про этот срок ничего
не знает.

- **Короткий прогон.** Проект `setup` выполняется в начале, и часового токена
  хватает на весь набор тестов.
- **Длинный прогон или живой сервер.** Снимок кладут в каталог, который чистится
  перед прогоном, чтобы вход выполнялся заново.
- **Параллельный прогон с записью данных.** Тесты идут в нескольких процессах
  сразу, и каждому такому процессу — воркеру — дают своего пользователя. Иначе
  тесты правят одни и те же задачи.

```ts
// tests/fixtures.ts — свой вход на каждый воркер
export const test = base.extend<{}, { workerStorageState: string }>({
  workerStorageState: [async ({ browser }, use, workerInfo) => {
    const file = `.auth/worker-${workerInfo.parallelIndex}.json`;
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto('/login');
    await page.getByLabel('Email').fill(`maria+${workerInfo.parallelIndex}@example.com`);
    await page.getByLabel('Пароль').fill('correct-horse');
    await page.getByRole('button', { name: 'Войти' }).click();

    await context.storageState({ path: file });
    await context.close();

    await use(file);
  }, { scope: 'worker' }],
});
```

Симптом протухшего снимка узнаваем: первый же тест проекта открывает `/tasks` и
видит форму входа. Ошибка при этом приходит от ассершена, а не от входа, поэтому
в отчёте она выглядит как «не нашёл заголовок».

## Типичные ошибки

- **Логиниться в `beforeEach`.** Симптом: половина шагов трассировки — один и тот
  же вход, а прогон растёт линейно.
- **Держать `.auth` в репозитории.** Симптом: в истории лежат живые cookies. Файл
  добавляют в `.gitignore` и снимают заново на каждой машине.
- **Ждать восстановления `sessionStorage`.** Симптом: снимок сделан, а
  приложение всё равно просит войти.
- **Давать всем воркерам одного пользователя.** Симптом: тесты правят одни и те
  же задачи и падают только при параллельном прогоне.

## Связь с другими темами

- [Модель Playwright: браузер, контекст, страница](./01-playwright-model.md) —
  почему сессия принадлежит контексту, а не браузеру.
- [Каждый тест начинается с чистого листа](./04-fixtures-and-isolation.md) — как
  раздать подготовленное состояние через фикстуру.
- [Тест управляет сетью, а не надеется на неё](./05-network.md) — что делать,
  когда вход идёт в подменённую сеть.
- Keycloak / OAuth2 Auth — про устройство токенов, сроки жизни и обновление
  сессии со стороны сервера.
