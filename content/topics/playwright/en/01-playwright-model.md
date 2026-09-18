# The Playwright model: browser, context, page

Playwright starts a real browser and drives it over a protocol from a Node.js
process. Isolation between tests does not come from the browser. It comes from a
browser context, a clean profile inside a process that is already running.

## Your test drives a real browser, not an imitation of one

A test is an ordinary Node.js process that launches a browser next to itself and
keeps one connection open to it.

```txt
             Who talks to whom while a test runs
┌─────────────────────────────────────┐
│ Your test                           │
│ a Node.js process: the test runner  │
└─────────────────────────────────────┘
                   │  commands over a protocol, one connection
                   ▼
┌─────────────────────────────────────┐
│ Browser                             │
│ a Chromium, Firefox or WebKit build │
└─────────────────────────────────────┘
                   │  real input: a click, typed text
                   ▼
┌─────────────────────────────────────┐
│ App page                            │
│ your frontend on localhost:3000     │
└─────────────────────────────────────┘
     there is no driver process between test and browser:
  Playwright installs and versions the browser build itself
```

The process that runs your tests is called the test runner. It starts a browser
build as a child process and sends it commands over an automation protocol. In
Chromium that protocol is built into the browser itself and is called
`Chrome DevTools Protocol`. For Firefox and WebKit (the engine behind Safari)
Playwright ships its own builds with the same level of access.

Browser builds do not arrive with the package. You install them with a separate
command, which also pulls the system libraries they need.

```bash
# browser builds are installed separately from the package
npx playwright install --with-deps chromium

# at the time of writing the latest package version is 1.63.0, from 4 September 2026
npx playwright --version
# Version 1.63.0
```

Check the current version in the release notes on the `playwright.dev` site.
Package 1.63.0 ships Chromium 153.0.8010.12, Firefox 155.0 and WebKit 26.6.
Those numbers live in `browsers.json` inside the `playwright-core` package, so
you can read them straight from `node_modules`.

Two consequences follow from "one package plus its own browser build". They
explain half of the surprises later on:

- **The browser version is tied to the package version.** Updating
  `@playwright/test` brings new builds. So "it passes locally but fails in CI
  (continuous integration)" often means nothing more than two different package
  versions.
- **There is no driver process in the middle.** The connection opens once and
  lives for the whole run. A command reaches the browser without an intermediate
  server.

The browser runs headless by default, which means without a window on screen.

```bash
# the same run, with a window on screen and one browser only
npx playwright test --headed --project=chromium
```

The `--headed` flag opens a window, and that is the only thing it changes. The
page, the protocol and the timeouts stay exactly the same.

Direct access to the browser buys you more than clicks. Over the same connection
a test gets things a unit test never has:

- **Interception and stubbing of network requests** — see
  [A test controls the network, it does not hope for it](./05-network.md).
- **A snapshot of the signed-in state, reused across tests** — see
  [Sign in once, not in every test](./06-auth-and-state.md).
- **A recording of everything that happened on the page**, network and screen
  frames included. Such a recording is called a trace, and it has its own
  article: [A failing test should explain itself](./07-debugging.md).
- **Environment emulation:** window size, locale, time zone, colour scheme and
  permissions.

## Isolation lives in the context, not in the browser

A browser context is a separate profile inside the browser process, close in
spirit to an incognito window. The picture below brings in one more word: tests
do not run in a single process but in several at once, and each such process is
called a worker.

```txt
 One worker: one browser, one context per test
┌─────────────────────────────────────────────┐
│ Browser: launched once per worker           │
│                                             │
│ ┌──────────────────┐ ┌────────────────────┐ │
│ │ Test 1 context   │ │ Test 2 context     │ │
│ │ own cookies      │ │ empty cookies      │ │
│ │ own localStorage │ │ empty localStorage │ │
│ │ own cache        │ │ empty cache        │ │
│ │                  │ │                    │ │
│ │ Page (a tab)     │ │ Page (a tab)       │ │
│ └──────────────────┘ └────────────────────┘ │
└─────────────────────────────────────────────┘
contexts cannot see each other data, one process or not:
so the order of tests inside a worker changes nothing
```

A context has its own cookies, its own `localStorage` and `sessionStorage`, its
own cache and its own permissions. Creating one is cheap, because the browser
process is already up. The docs describe contexts as fast to create and fully
isolated. That is why the clean slate goes to every test rather than to every
file.

| level | what it isolates | when it is created | what it costs |
|---|---|---|---|
| browser | the process, the version, launch flags | once per worker | a process start |
| context | cookies, storage, cache, permissions | per test | almost nothing |
| page | a tab: its own address and history | per test | almost nothing |

The browser row explains why twice as many tests do not make the run twice as
slow. The process starts once per worker and stays up. It is restarted only
after a test fails.

## A project is the same test in a different environment

A project describes the settings a test runs with, not which tests run.

```ts
// playwright.config.ts — three browsers and one phone-sized screen
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox',  use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit',   use: { ...devices['Desktop Safari'] } },
    { name: 'mobile',   use: { ...devices['Pixel 7'] } },
  ],
});
```

The same `tests/login.spec.ts` file now runs four times. The `--project=chromium`
flag runs one of them, which is what people do locally almost always. The
`devices` registry brings ready-made screen sizes, pixel ratios and a
`User-Agent` string; the list ships inside the package.

Projects can do one more thing, and articles 06 and 09 are built on it. A project
can depend on another project through the `dependencies` field. The dependency
runs first, and its result is handed to the rest.

## The `page` fixture already hands you a clean context

The arguments a test lists in its brackets are a prepared environment. Each of
them is called a fixture, and `page` arrives already wrapped in its own context.

```ts
// playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  use: {
    baseURL: 'http://localhost:3000',   // lets you write page.goto('/login')
    trace: 'on-first-retry',            // a trace only on the first retry
  },
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
  },
});
```

The `webServer` block starts the app before the run and waits until the address
answers. The `reuseExistingServer` option leaves an already running local server
alone, and starts its own one on the build machine.

**The running example for this topic is a task board.** All nine articles work
on the same interface:

- `/login` — the sign-in form: an "Email" field, a "Password" field, a "Sign in"
  button.
- `/tasks` — the task list, with a status filter and pages of twenty items.
- `POST /api/login` — takes the credentials, answers with a session token.
- `GET /api/tasks?status=open&page=2` — returns one page of the list and the total.

The first test on this setup checks the most common path: sign in, then reach the
list.

```ts
// tests/login.spec.ts
import { test, expect } from '@playwright/test';

test('signing in opens the task list', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill('maria@example.com');
  await page.getByLabel('Password').fill('correct-horse');
  await page.getByRole('button', { name: 'Sign in' }).click();

  await expect(page.getByRole('heading', { name: 'Tasks' })).toBeVisible();
  await expect(page).toHaveURL('/tasks');   // baseURL is filled in for you
});
```

Notice what the test does not contain. There is no "wait two seconds" anywhere:
the locator does the waiting, which is the subject of
[A locator describes an element, it does not find one](./02-locators.md). There
is no cleanup at the end either, because the next test gets a new context.

## One test can hold two contexts at once

A second context is what you need when a scenario has two users in it.

```ts
// tests/visibility.spec.ts
import { test, expect } from '@playwright/test';

test('Maria task is not visible to Ivan', async ({ browser }) => {
  const mariaContext = await browser.newContext({ storageState: 'auth/maria.json' });
  const ivanContext = await browser.newContext({ storageState: 'auth/ivan.json' });
  const maria = await mariaContext.newPage();
  const ivan = await ivanContext.newPage();

  await maria.goto('/tasks');
  await expect(maria.getByText('May report')).toBeVisible();

  await ivan.goto('/tasks');
  await expect(ivan.getByText('May report')).toHaveCount(0);  // 0 matches

  await mariaContext.close();
  await ivanContext.close();
});
```

Two contexts inside one browser cannot see each other's data, so Maria signing in
does not sign Ivan in. A second tab of the same context does not work that way:
it shares cookies and storage with the first one. Where the `auth/maria.json`
files come from is covered by
[Sign in once, not in every test](./06-auth-and-state.md).

## Common mistakes

- **Signing in through the form in every test.** The symptom: run time grows
  linearly with the suite, and half the steps in the report are the same sign-in.
  Save the signed-in state once instead.
- **Expecting the browser to restart between tests.** The symptom: a test counts
  on a fresh process or different launch flags and gets the previous ones. Only a
  failure restarts the browser, and not always.
- **Opening a second tab instead of a second context.** The symptom: the second
  user turns out to be the first one, because the cookies are shared.
- **Leaving a hand-made context open.** The symptom: the run holds memory and
  takes a long time to finish. The `page` fixture closes itself;
  `browser.newContext()` does not.

## Related topics

- [A locator describes an element, it does not find one](./02-locators.md) — why
  a locator waits by itself, and what it checks.
- [Every test starts from a clean slate](./04-fixtures-and-isolation.md) — the
  order fixtures are created in, and their scopes.
- [Sign in once, not in every test](./06-auth-and-state.md) — how to store the
  signed-in state and skip the form.
- Testing — the question bank on the test pyramid, unit tests and test doubles.
  This topic starts where a test drives a real browser.
