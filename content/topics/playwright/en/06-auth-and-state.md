# Sign in once, not in every test

The signed-in state is captured once in a separate project and handed to tests as
a file. A snapshot is a set of cookies and storage entries, not "a browser left
open". Signing in stops taking up room in every test and in every report.

## A state snapshot is a file with cookies and storage

The `storageState` method takes everything that defines a session out of a
context and writes it to a file.

```ts
// tests/auth.setup.ts
import { test as setup, expect } from '@playwright/test';

setup('sign in as Maria', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill('maria@example.com');
  await page.getByLabel('Password').fill('correct-horse');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Tasks' })).toBeVisible();

  await page.context().storageState({ path: '.auth/maria.json' });
});
```

The resulting file reads fine by eye. Below is a real snapshot from the stand
used in this topic: the app puts a token in `localStorage`, the server sets a
session cookie.

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

There are exactly two keys, and that answers the question of what a snapshot
holds.

| what | in the snapshot |
|---|---|
| cookies, `httpOnly` ones included | yes |
| `localStorage` per origin | yes |
| `sessionStorage` | no |
| `IndexedDB` | only with the `indexedDB: true` option |
| open tabs, history, cache | no |
| `WebAuthn` passkeys | only with the `credentials: true` option |

The missing `sessionStorage` takes one line to confirm: a test started from a
snapshot sees `token` in `localStorage` and `null` instead of the draft. The
output of that run appears below, in the section about the setup project.

An app that keeps its session in `sessionStorage` cannot be restored from a
snapshot. Such a session needs its own preparation step before the test — a
fixture that fills the storage with the right values itself.

## Where the signed-in state lives

A snapshot makes three stops: the setup project, the file, the test context.

```txt
              Where the signed-in state lives
┌──────────────────────────────────────┐
│ The setup project                    │
│ signs in once per run                │
└──────────────────────────────────────┘
                    │  context.storageState({ path })
                    ▼
┌──────────────────────────────────────┐
│ The .auth/maria.json file            │
│ cookies and localStorage per origin  │
└──────────────────────────────────────┘
                    │  use: { storageState } in the project
                    ▼
┌──────────────────────────────────────┐
│ The test context                     │
│ created already filled from the file │
└──────────────────────────────────────┘
                    │  the page fixture as usual
                    ▼
┌──────────────────────────────────────┐
│ The test page                        │
│ opens as the user right away         │
└──────────────────────────────────────┘
 sessionStorage never reaches the file, and a token carries
      its own lifetime: the file ages together with it
```

At none of those stops does a browser stay open. The test context is created the
usual way and simply receives the contents of the file before the first
navigation.

## A project dependency prepares the state before the tests

The preparation becomes its own project, and tests declare it as a dependency.

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
      dependencies: ['setup'],          // sign in first, everything else after
    },
  ],
});
```

The `dependencies` field sets the order: the `setup` project runs to completion,
and only then do the dependent projects start. If signing in fails, the dependent
tests never run, which is right, because all of them would fail the same way.

```txt
Running 2 tests using 1 worker

  ✓  1 [setup] › tests/auth.setup.ts:3:6 › sign in as Maria (316ms)
  token from the snapshot: tok-bWFyaWFAZXhhbXBsZS5jb20=
  sessionStorage.draft:    null
  cookies:                 session
  ✓  2 [chromium] › tests/list.spec.ts:3:5 › list is open (167ms)

  2 passed (1.4s)
```

The project name in square brackets shows what is going on. One good habit: add
the `.auth` directory to `.gitignore`, because live sessions end up there.

## Several roles mean several snapshots

Roles differ only by file name, so the preparation is written as a loop.

```ts
// tests/auth.setup.ts
const USERS = [
  { role: 'maria', email: 'maria@example.com', password: 'correct-horse' },
  { role: 'ivan', email: 'ivan@example.com', password: 'stapler-lamp' },
];

for (const user of USERS) {
  setup(`sign in: ${user.role}`, async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(user.email);
    await page.getByLabel('Password').fill(user.password);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('heading', { name: 'Tasks' })).toBeVisible();

    await page.context().storageState({ path: `.auth/${user.role}.json` });
  });
}
```

Each project then picks up its own file, and one suite runs as several different
users.

```txt
Running 4 tests using 1 worker

  ✓  1 [setup] › tests/auth.setup.ts:9:8 › sign in: maria (292ms)
  ✓  2 [setup] › tests/auth.setup.ts:9:8 › sign in: ivan (149ms)
  maria: session=bWFyaWFAZXhh…
  ✓  3 [maria] › tests/roles.spec.ts:3:5 › session (134ms)
  ivan: session=aXZhbkBleGFt…
  ✓  4 [ivan] › tests/roles.spec.ts:3:5 › session (115ms)

  4 passed (1.8s)
```

When a role is needed by a few tests rather than a whole project, the snapshot is
attached inside the file.

```ts
// tests/admin.spec.ts
test.use({ storageState: '.auth/ivan.json' });

test('other people tasks stay hidden', async ({ page }) => {
  await page.goto('/tasks');
  await expect(page.getByText('May report')).toHaveCount(0);
});
```

## Two users in one test live in two contexts

One test gets one session, because it has one context.

```ts
test('the author sees the task, the other user does not', async ({ browser }) => {
  const mariaContext = await browser.newContext({ storageState: '.auth/maria.json' });
  const ivanContext = await browser.newContext({ storageState: '.auth/ivan.json' });

  const maria = await mariaContext.newPage();
  const ivan = await ivanContext.newPage();

  await maria.goto('/tasks');
  await ivan.goto('/tasks');

  await expect(maria.getByText('May report')).toBeVisible();
  await expect(ivan.getByText('May report')).toHaveCount(0);

  await mariaContext.close();
  await ivanContext.close();
});
```

Both contexts live in the same browser and cannot see each other's cookies. How
that isolation works is covered in
[The Playwright model: browser, context, page](./01-playwright-model.md).

## The token inside a snapshot gets old

A snapshot is data with a shelf life, and the run knows nothing about that life.

- **A short run.** The `setup` project runs at the start, and an hour-long token
  covers the whole suite.
- **A long run, or a live server.** Keep the snapshot in a directory that is
  wiped before the run, so signing in happens again.
- **A parallel run that writes data.** Tests go in several processes at once,
  and each such process — a worker — gets its own user. Otherwise tests edit the
  same tasks.

```ts
// tests/fixtures.ts — one sign-in per worker
export const test = base.extend<{}, { workerStorageState: string }>({
  workerStorageState: [async ({ browser }, use, workerInfo) => {
    const file = `.auth/worker-${workerInfo.parallelIndex}.json`;
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto('/login');
    await page.getByLabel('Email').fill(`maria+${workerInfo.parallelIndex}@example.com`);
    await page.getByLabel('Password').fill('correct-horse');
    await page.getByRole('button', { name: 'Sign in' }).click();

    await context.storageState({ path: file });
    await context.close();

    await use(file);
  }, { scope: 'worker' }],
});
```

A stale snapshot has a recognisable symptom: the first test of the project opens
`/tasks` and sees the sign-in form. The error comes from an assertion rather than
from the sign-in, so the report reads "heading not found".

## Common mistakes

- **Signing in from `beforeEach`.** The symptom: half the trace steps are the
  same sign-in, and the run grows linearly.
- **Keeping `.auth` in the repository.** The symptom: live cookies sit in the
  history. Add the directory to `.gitignore` and capture it per machine.
- **Expecting `sessionStorage` to come back.** The symptom: the snapshot exists,
  and the app still asks you to sign in.
- **Giving every worker the same user.** The symptom: tests edit the same tasks
  and only fail in a parallel run.

## Related topics

- [The Playwright model: browser, context, page](./01-playwright-model.md) — why
  a session belongs to a context rather than to a browser.
- [Every test starts from a clean slate](./04-fixtures-and-isolation.md) — how to
  hand prepared state to tests through a fixture.
- [A test controls the network, it does not hope for it](./05-network.md) — what
  to do when sign-in goes through a stubbed network.
- Keycloak / OAuth2 Auth — token anatomy, lifetimes and session refresh from the
  server side.
