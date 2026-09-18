# Web-first assertions wait, plain ones do not

A check written as `expect(locator)` repeats until it matches or until its time
runs out. A check written as `expect(value)` compares an already-collected number
or string exactly once. The first kind — the one that knows the page is still
moving and waits for it — is called a web-first assertion, and that is the name
used from here on.

## `expect(locator)` retries, `expect(value)` does not

The difference is not what you check. It is what goes inside `expect`.

```txt
         One trait, two ways to check it
┌──────────────────────┐  ┌──────────────────────┐
│ expect(locator)      │  │ expect(value)        │
│ takes a description  │  │ takes a plain number │
│                      │  │                      │
│ check                │  │ compare once         │
│ no match: again      │  │                      │
│ no match: again      │  │                      │
│ match: pass          │  │ verdict at once      │
│                      │  │                      │
│ or a 5000 ms timeout │  │ no timeout at all    │
└──────────────────────┘  └──────────────────────┘
the right column answers from a state that is already stale:
the page moved on, the number was taken before the compare
```

On the left, `expect` receives a description and decides for itself when to ask
the page again. On the right, it receives a number taken before the call, so it
can only compare that. A list that finishes rendering a hundred milliseconds
later is seen by the left form and missed by the right one.

```ts
// tests/tasks.spec.ts
import { test, expect } from '@playwright/test';

test('the filter leaves twenty tasks', async ({ page }) => {
  await page.goto('/tasks');
  await page.getByLabel('Status').selectOption('open');

  // Flaky: the number is taken before the list re-renders
  expect(await page.getByRole('listitem').count()).toBe(20);

  // Reliable: the check repeats until it matches
  await expect(page.getByRole('listitem')).toHaveCount(20);
});
```

The `await` keyword tells the two apart in code. A web-first assertion has it in
front of `expect`, because the waiting lives inside. A plain one has it inside
the brackets, because the value must arrive before the comparison.

## A failure shows what was expected, what came back, and how long it waited

A web-first assertion prints four state lines and a call log.

```txt
Error: expect(locator).toHaveCount(expected) failed

Locator:  getByRole('listitem')
Expected: 25
Received: 20
Timeout:  1500ms

Call log:
  - Expect "toHaveCount" getByRole('listitem') with timeout 1500ms
  - waiting for getByRole('listitem')
    16 × locator resolved to 20 elements
       - unexpected value "20"
```

Everything needed for the diagnosis is here. Twenty-five rows expected, twenty
received, one and a half seconds spent. The `16 ×` line says the check repeated
sixteen times and saw the same thing each time. So this is not a race: the list
rendered and then stood still, and the expectation in the test is simply wrong.

A plain `expect` prints half as much in the same situation.

```txt
Error: expect(received).toBe(expected) // Object.is equality

Expected: 25
Received: 20
```

No timeout, no log, no locator — two numbers were compared, and the rest is your
job. That is the second reason to prefer a web-first assertion. It does not only
wait, it also explains.

## Every trait has a ready-made check of its own

Checking a trait with a ready-made assertion is cheaper than collecting the value
by hand and comparing it yourself.

| what you check | with what | on the running example |
|---|---|---|
| an element is on screen | `toBeVisible` | the "Tasks" heading showed up |
| an element is gone | `toBeHidden` | the "No tasks" hint is hidden |
| how many | `toHaveCount` | twenty rows in the list |
| the whole text | `toHaveText` | the pager says "Page 2 of 5" |
| part of the text | `toContainText` | the row contains the word "report" |
| a field value | `toHaveValue` | the "Email" field kept the address |
| a selected option | `toHaveValues` | the filter has `open` selected |
| a button is usable | `toBeEnabled`, `toBeDisabled` | "Next" is off on the last page |
| the page address | `toHaveURL` | the address is `/tasks` after sign-in |
| a server answer | `toBeOK` | `GET /api/tasks` came back fine |

All of them retry on their own. The full list in the docs is longer, and it
includes an accessibility tree snapshot through `toMatchAriaSnapshot`, an image
comparison through `toHaveScreenshot`, and checks for class, attribute and style.

```ts
// a per-assertion timeout beats the shared one
await expect(page.getByRole('heading', { name: 'Tasks' })).toBeVisible();
await expect(page.getByRole('listitem')).toHaveCount(20, { timeout: 10_000 });
await expect(page.getByText('Page 2 of 5')).toBeVisible();
await expect(page.getByLabel('Email')).toHaveValue('maria@example.com');

// negation waits for the opposite: until the row disappears
await expect(page.getByText('May report')).toBeHidden();
```

Negation holds a detail that is easy to forget. The `not.toBeVisible()` form
waits until the condition turns false instead of checking it once. So a "nothing
appeared" check honestly spends its whole timeout and slows the suite down.

## Several timeouts run at once, and the strictest one cuts the rest

The assertion timeout is not the only counter in a test, and it is not the main
one.

| timeout | default | where it is set |
|---|---|---|
| test | 30,000 ms | the `timeout` field, `test.setTimeout()` |
| assertion | 5,000 ms | `expect.timeout`, or an option on the assertion |
| action | none | `use.actionTimeout`, or an option on the action |
| navigation | none | `use.navigationTimeout`, or an option on `goto` |
| whole run | none | `globalTimeout` in the config |

```ts
// playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  timeout: 30_000,                    // for the whole test
  expect: { timeout: 5_000 },         // for one web-first assertion
  use: { actionTimeout: 10_000 },     // for one action
});
```

An option on a single assertion overrides `expect.timeout`. The test timeout
overrides everything: once it runs out, the test fails no matter how long an
assertion still had.

```txt
Test timeout of 2000ms exceeded.

Error: expect(locator).toBeVisible() failed

Locator: getByText('No tasks')
Expected: visible
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByText('No tasks') with timeout 30000ms
  - waiting for getByText('No tasks')
  - Test timeout of 2000ms exceeded.
```

The log states the conflict outright: the assertion was given thirty seconds and
the test lived two. A generous timeout on one check buys nothing until the test
timeout goes up as well. Flakiness that people treat with bigger timeouts is
covered in
[A flaky test is worse than no test](./08-flakiness-and-parallelism.md).

## A soft check does not stop the test

A normal check ends the test on the first mismatch. A soft one records the error
and carries on; the name comes from how it is written: `expect.soft`.

```ts
test('the task card shows every field', async ({ page }) => {
  await page.goto('/tasks');

  await expect.soft(page.getByRole('listitem')).toHaveCount(20);
  await expect.soft(page.getByRole('heading')).toHaveText('Tasks');

  // a hard assertion: without it there is nothing left to check
  await expect(page.getByRole('button', { name: 'Next' })).toBeEnabled();
});
```

A test with soft assertions still counts as failed, but every mismatch reaches
the report at once.

```txt
Error: expect(locator).toHaveCount(expected) failed
    Expected: 25
    Received: 20
      - Expect "soft toHaveCount" getByRole('listitem') …

Error: expect(locator).toHaveText(expected) failed
    Expected: "Inbox"
    Received: "Tasks"
      - Expect "soft toHaveText" getByRole('heading') …
```

Soft assertions fit where the checks are independent: several fields of one card,
several columns of one row. They hurt where the second check is pointless without
the first: with no list on screen, there is no pager to verify.

Setting the mode for a group of checks is what `expect.configure` is for.

```ts
// one configured expect instead of repeating options on every line
const softExpect = expect.configure({ soft: true, timeout: 10_000 });

await softExpect(page.getByRole('listitem')).toHaveCount(20);
await softExpect(page.getByRole('heading')).toHaveText('Tasks');
```

## With nothing to check on the page, `expect.poll` and `toPass` do the waiting

These two forms move the retry onto arbitrary code instead of a locator.

```ts
// wait until the server starts reporting the right number of tasks
await expect.poll(async () => {
  const res = await page.request.get('/api/tasks?status=open&page=1');
  return (await res.json()).total;
}, { timeout: 10_000, intervals: [200, 500, 1_000] }).toBe(20);

// repeat a whole block until all of it passes
await expect(async () => {
  const res = await page.request.get('/api/tasks?status=open&page=1');
  expect(res.status()).toBe(200);
  expect((await res.json()).items).toHaveLength(20);
}).toPass({ timeout: 10_000, intervals: [500] });
```

The `expect.poll` form repeats a function and applies a plain matcher to the
result. The `toPass` form repeats the block as a whole and counts it as passing
once no error is left inside. Both fail with the same extra line in the log.

```txt
Error: expect(received).toBe(expected) // Object.is equality

Expected: 25
Received: 20

Call Log:
- Timeout 1500ms exceeded while waiting on the predicate
```

Use them for what the page does not show: a queue state, a database row, an
answer from a neighbouring service. For anything visible on the page a plain
web-first assertion is cheaper, because it waits and prints the locator in the
report.

## Common mistakes

- **Checking `count()` with a plain `expect`.** The symptom: the test fails on a
  slow machine and passes on a fast one. Replace the check with `toHaveCount`.
- **Raising the assertion timeout without raising the test timeout.** The
  symptom: the log says "with timeout 30000ms" while the test dies at its own
  thirty-second limit.
- **Using a soft assertion where nothing can follow.** The symptom: one mismatch
  produces ten derived ones, and the real cause is hard to spot.
- **Checking absence with `not` in every test.** The symptom: the suite slows
  down, because each of those checks honestly waits out its timeout.

## Related topics

- [A locator describes an element, it does not find one](./02-locators.md) — why
  a description never goes stale, and which methods do not wait.
- [A failing test should explain itself](./07-debugging.md) — where the same log
  is shown next to the page frames.
- [A flaky test is worse than no test](./08-flakiness-and-parallelism.md) — when
  waiting cures a problem and when it hides one.
- [A pipeline run: what Playwright asks of the build machine](./09-ci-and-visual.md)
  — about `toHaveScreenshot` and image comparison across machines.
