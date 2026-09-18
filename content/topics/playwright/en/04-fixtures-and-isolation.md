# Every test starts from a clean slate

The clean slate comes from a new browser context per test, not from cleaning up
afterwards. Building that environment before a test and taking it apart after is
a separate mechanism; in Playwright it is called a fixture. The same design
explains what isolation does not cover.

## A fixture is an argument of the test, not a global setting

A test declares what it needs in the brackets and receives it ready to use.

```ts
// tests/tasks.spec.ts
import { test, expect } from '@playwright/test';

test('the filter leaves only open tasks', async ({ page }) => {
  await page.goto('/tasks');
  await page.getByLabel('Status').selectOption('open');

  await expect(page.getByRole('listitem')).toHaveCount(20);
});

test('checking the list over the API, with no interface', async ({ request }) => {
  const res = await request.get('/api/tasks?status=open&page=1');

  await expect(res).toBeOK();
  expect((await res.json()).total).toBe(33);
});
```

The first test asked for `page` and got a page inside its own context. The second
asked for `request` and got a request client with no browser at all. A fixture
nobody asked for is never built, so an unused `browser` costs the test nothing.

The table below has a "scope" column. Scope is how long a fixture lives: either
one test, or the whole process that runs tests one after another. Such a process
is called a worker, and several of them run at the same time.

| fixture | what it gives | scope |
|---|---|---|
| `page` | a page inside its own context | test |
| `context` | the whole browser context | test |
| `request` | a request client without a browser | test |
| `browser` | the browser process | worker |
| `playwright` | the entry point to the package | worker |
| `browserName` | the browser name as a string | worker |

The `page` and `context` fixtures are related: `page` is created inside that same
`context`. So asking for both does not hand you two separate pages.

## A worker lives long, a test does not

Scope decides what survives the border between two tests.

```txt
        The fixture lifecycle inside one worker
┌─────────────────────────────────────────────────────┐
│ The worker starts                                   │
│ worker fixtures are built: browser, its own account │
├─────────────────────────────────────────────────────┤
│ Test 1                                              │
│ built: context -> page -> boardPage                 │
│ the test body                                       │
│ torn down: boardPage -> page -> context             │
├─────────────────────────────────────────────────────┤
│ Test 2                                              │
│ same browser and account, new context and page      │
│ the test body                                       │
│ torn down in reverse order                          │
├─────────────────────────────────────────────────────┤
│ The worker finishes                                 │
│ worker fixtures are torn down: account -> browser   │
└─────────────────────────────────────────────────────┘
setup runs from dependencies outwards, teardown runs backwards:
  only worker-scoped things survive between two tests
```

You can check the order by printing from the fixture itself. The output below
comes from a run of two tests in one worker.

```txt
Running 2 tests using 1 worker

  setup    account (worker 0)
  setup    boardPage
  >>       test 1 body
  teardown boardPage
  ✓  1 tests/fixtures.spec.ts:21:1 › first test (117ms)
  setup    boardPage
  >>       test 2 body
  teardown boardPage
  ✓  2 tests/fixtures.spec.ts:26:1 › second test (75ms)
  teardown account

  2 passed (827ms)
```

The `account` fixture is worker-scoped, so it was built once and torn down after
the last test. The `boardPage` fixture is test-scoped, so it went round the full
circle twice. Printing this yourself is worth doing whenever the order looks
unclear: it answers faster than the docs do.

## A custom fixture takes the repetition out of tests

A fixture is declared with `test.extend`, and its body splits in two around the
call to `use`.

```ts
// tests/fixtures.ts
import { test as base, expect, type Page } from '@playwright/test';

export const test = base.extend<{ boardPage: Page }>({
  boardPage: async ({ page }, use) => {
    await page.goto('/tasks');                 // setup: before the test
    await page.getByLabel('Status').selectOption('open');

    await use(page);                           // the test runs here

    await page.evaluate(() => localStorage.clear());   // teardown: after it
  },
});

export { expect };
```

Everything before `use` runs before the test body. Everything after it runs once
the test is over, including after a failure. Whatever you pass into `use` becomes
the argument of the test. Teardown running even on failure is the main thing a
fixture has over code appended to the end of a test.

```ts
// tests/tasks.spec.ts
import { test, expect } from './fixtures';

test('the pager moves forward', async ({ boardPage }) => {
  await boardPage.getByRole('button', { name: 'Next' }).click();

  await expect(boardPage.getByText('Page 2 of 2')).toBeVisible();
});
```

A fixture has three useful modifiers. The `auto: true` flag turns it on for every
test in the file without naming it in the brackets. The `option: true` flag turns
it into a setting you fill in from the config through `use`. The `timeout` option
limits the fixture separately from the test.

```ts
// playwright.config.ts — a project fills in the option fixture
export default defineConfig({
  projects: [
    { name: 'open tasks', use: { defaultStatus: 'open' } },
    { name: 'done tasks', use: { defaultStatus: 'done' } },
  ],
});
```

## Scope is chosen by cost, not by convenience

Test scope is safe, worker scope is fast.

| trait | test scope | worker scope |
|---|---|---|
| when it is built | before every test | once per process |
| what sees it | that one test | every test of the worker |
| cost of a mistake | one test is lost | a chain of tests breaks |
| typical resident | a page, test data | a browser, an account, a stub server |

```ts
// tests/fixtures.ts — one account per worker
export const test = base.extend<{}, { account: string }>({
  account: [async ({}, use, workerInfo) => {
    const email = `maria+${workerInfo.workerIndex}@example.com`;
    await createUser(email);                   // expensive: do it once

    await use(email);

    await deleteUser(email);
  }, { scope: 'worker' }],
});
```

The account here is keyed by the worker index, so two workers never fight over
one user. The opposite dependency is forbidden: a worker fixture cannot ask for
`page`. The run does not even start, it fails with
`worker fixture "api" cannot depend on a test fixture "page"`.

The rule makes sense: `page` lives for one test while a worker fixture outlives
dozens. A worker fixture that needs a page creates its own context from `browser`
and closes it itself.

## The browser is isolated, your module is not

A context carries away all page state, but it has nothing to do with the test
process.

```txt
Running 2 tests using 1 worker

  wrote filter=open and module variable 42
  ✓  1 tests/iso-en.spec.ts:5:5 › test 1 writes (56ms)
  localStorage.filter = null
  module variable     = 42
  ✓  2 tests/iso-en.spec.ts:12:5 › test 2 reads (59ms)

  2 passed (566ms)
```

The `localStorage` entry went away with the context. The module variable crossed
the border, because it lives in the test runner process. That leaves a short list
of things to watch yourself:

- **Module variables and singletons.** They are shared by every test of the file
  inside one worker.
- **Database rows and files on disk.** Nobody rolls them back unless your fixture
  does.
- **External services and queues.** A stub started for the whole run still
  remembers the previous test.

Each item is a ready-made source of flakiness, and the details are in
[A flaky test is worse than no test](./08-flakiness-and-parallelism.md).

## A fixture beats `beforeEach`

Both work, but a fixture has four advantages, and none of them is about taste.

- **The test reads whole.** Its brackets say what it needs; a hook says nothing.
- **Nothing extra is built.** A hook runs for every test in the file, a fixture
  only for the tests that asked.
- **Teardown is guaranteed.** Code after `use` runs even when the test fails.
- **Steps show up in the report.** A fixture appears in the trace as its own row,
  and `box: true` hides it when the noise is not worth it.

Hooks stay useful for actions that build nothing: attach a note to the report,
check a shared precondition, skip the test.

## Common mistakes

- **Keeping state in a module variable.** The symptom: tests pass one by one and
  fail together. Move the state into a fixture.
- **Declaring expensive setup per test.** The symptom: the run got three times
  slower after one new fixture. Worker scope is the answer.
- **Cleaning up at the end of the test body.** The symptom: after a failure the
  mess stays and the next test fails for a different reason. Move cleanup after
  `use`.
- **Creating a context by hand while holding `page`.** The symptom: the trace
  shows two contexts and only one is checked. A second context is for a second
  user.

## Related topics

- [The Playwright model: browser, context, page](./01-playwright-model.md) —
  what a context isolates and what it costs.
- [Sign in once, not in every test](./06-auth-and-state.md) — how a ready
  signed-in state reaches tests through fixtures and projects.
- [A flaky test is worse than no test](./08-flakiness-and-parallelism.md) — why
  shared state breaks a parallel run.
- Testing — the question bank on data setup, hooks and test doubles at unit
  level.
