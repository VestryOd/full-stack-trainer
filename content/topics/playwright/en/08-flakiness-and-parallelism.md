# A flaky test is worse than no test

A flaky test is one that fails sometimes and passes other times while the code
stays the same. The harm is not the failure itself. It is that people stop
trusting a red run: the team learns to press "rerun" instead of reading the
message. A missing test at least never lies to anyone.

## Flakiness only shows up on repeats

One green run proves nothing, so a suspicious test is run several times in a row.

```ts
// tests/flaky.spec.ts
import { test, expect } from '@playwright/test';

test('a fixed pause', async ({ page }) => {
  await page.goto('/tasks');
  await page.getByLabel('Status').selectOption('open');

  await page.waitForTimeout(200);            // a bet on 200 ms

  expect(await page.getByRole('listitem').count()).toBe(20);
});
```

The `--repeat-each` flag runs the same test a given number of times. On our
stand, where the server answers after a random delay, eight runs look like this.

```txt
Running 8 tests using 1 worker

✓  1 tests/flaky.spec.ts:3:5 › a fixed pause (462ms)
✓  2 tests/flaky.spec.ts:3:5 › a fixed pause (280ms)
✓  3 tests/flaky.spec.ts:3:5 › a fixed pause (276ms)
✘  4 tests/flaky.spec.ts:3:5 › a fixed pause (295ms)
✓  5 tests/flaky.spec.ts:3:5 › a fixed pause (retry #1) (277ms)
✓  6 tests/flaky.spec.ts:3:5 › a fixed pause (280ms)
✘  7 tests/flaky.spec.ts:3:5 › a fixed pause (286ms)
✓  8 tests/flaky.spec.ts:3:5 › a fixed pause (retry #1) (277ms)

2 flaky
6 passed (6.4s)
```

The word `flaky` in the summary means exactly "failed, then passed on a retry".
The message says what happened: the test checked the list before it rendered.

```txt
Error: expect(received).toBe(expected) // Object.is equality

Expected: 20
Received: 0
```

## A fixed pause is a bet on how fast the answer arrives

The `waitForTimeout` call asks to wait exactly as long as you said. No such
"exactly" exists: the server, the network and the rendering take different
amounts of time on different machines and under different load.

The pause is either shorter than the real wait, and then the test fails at
random, or longer, and then every test donates spare seconds to the suite. A
check that waits for a trait removes both problems at once.

```ts
// tests/stable.spec.ts
test('an assertion instead', async ({ page }) => {
  await page.goto('/tasks');
  await page.getByLabel('Status').selectOption('open');

  await expect(page.getByRole('listitem')).toHaveCount(20);
});
```

The same six repeats against the same unsteady server.

```txt
✓  2 tests/stable.spec.ts:3:5 › an assertion instead (72ms)
✓  3 tests/stable.spec.ts:3:5 › an assertion instead (363ms)
✓  4 tests/stable.spec.ts:3:5 › an assertion instead (249ms)
✓  5 tests/stable.spec.ts:3:5 › an assertion instead (256ms)
✓  6 tests/stable.spec.ts:3:5 › an assertion instead (362ms)

6 passed (3.5s)
```

Look at the timings. Where the pause honestly sat out its 200 milliseconds, the
assertion moved on after 72. Waiting for a trait is not only steadier, it is also
faster.

## Shared state makes tests depend on order

The second source of flakiness has nothing to do with time. Tests that write to
one database or one list start getting in each other's way, and the result
depends on who got there first.

```ts
// tests/shared.spec.ts
test('import adds tasks', async ({ request }) => {
  for (let i = 0; i < 20; i++) {
    await request.post('/api/tasks', { data: { title: `Import ${i}` } });
  }
});

test('three pages', async ({ page }) => {           // counts on the first 45
  await page.goto('/tasks');
  await expect(page.getByText('Page 1 of 3')).toBeVisible();
});
```

On its own, the second test passes.

```txt
Running 1 test using 1 worker

✓  1 tests/shared.spec.ts:9:5 › three pages (364ms)

1 passed (848ms)
```

After the first one it fails, and both retries fail the same way.

```txt
Running 2 tests using 1 worker

✓  1 tests/shared.spec.ts:3:5 › import adds tasks (38ms)
✘  2 tests/shared.spec.ts:9:5 › three pages (5.1s)
✘  3 tests/shared.spec.ts:9:5 › three pages (retry #1) (5.1s)
✘  4 tests/shared.spec.ts:9:5 › three pages (retry #2) (5.1s)
```

Three identical failures in a row are a diagnosis in themselves. A race against
time usually disappears on a retry, while a dependency on shared data reproduces
every time until the data is put back.

## Symptom, cause, what to do

Most flaky tests land in one of these five rows.

| symptom | cause | what to do |
|---|---|---|
| fails on a slow machine, passes on a fast one | a fixed pause, or a check that never waits | a web-first assertion, not `waitForTimeout` |
| fails in the full run, passes alone | shared data on the server | own data per test or per worker |
| fails when the file order changes | state in a module variable | move the state into a fixture |
| a click misses, the element "jumps" | an animation or a layout shift | wait for stability or switch animations off |
| fails at midnight, at month end, on another machine | time, time zone, locale | pin them in the project config |

The first row is cured by what article
[Web-first assertions wait, plain ones do not](./03-assertions.md) already
covers. The last one belongs to
[A pipeline run: what Playwright asks of the build machine](./09-ci-and-visual.md).

## Workers split one machine, shards split the machines

There are two ways to speed a run up, and they solve different problems.

```txt
     Eight test files: two ways to speed the run up
┌───────────────────────┐  ┌───────────────────────────┐
│ Workers: one machine  │  │ Shards: four machines     │
│                       │  │                           │
│ --workers=4           │  │ --shard=1/4 … 4/4         │
│                       │  │                           │
│ process 1: files 1, 5 │  │ machine 1: files 1, 2     │
│ process 2: files 2, 6 │  │ machine 2: files 3, 4     │
│ process 3: files 3, 7 │  │ machine 3: files 5, 6     │
│ process 4: files 4, 8 │  │ machine 4: files 7, 8     │
│                       │  │                           │
│ one report right away │  │ reports merged afterwards │
└───────────────────────┘  └───────────────────────────┘
both split the work by file rather than by single test:
  tests of one file move apart only when you allow it
```

Workers are processes on the same machine. Each keeps its own browser, so four
workers take four times the memory and processor.

```txt
Running 8 tests using 4 workers
```

Sharding splits the suite between machines: each takes its part and knows nothing
about the others. The `--shard=1/2` flag means "the first half out of two".

```txt
Running 2 tests using 1 worker, shard 1 of 2

✓  1 tests/part1.spec.ts:3:5 › part 1, scenario A (276ms)
✓  2 tests/part1.spec.ts:8:5 › part 1, scenario B (270ms)

2 passed (1.1s)
```

Both share one trait: the unit of splitting is a file, not a test. Eight tests in
one file still go to one process under `--workers=4`. Letting the tests of one
file spread across workers takes an explicit permission.

```ts
// at the top of the file: these tests are independent, spread them out
test.describe.configure({ mode: 'parallel' });

// or in the config, for every file at once
export default defineConfig({ fullyParallel: true });
```

```txt
Running 4 tests using 4 workers
```

The opposite setting exists too: `mode: 'serial'` keeps the file strictly in
order and skips the rest once one test fails. It states honestly that the tests
are dependent, but that is an admission, not a fix.

## A retry cures a race and hides a defect

Retries are switched on with one line, and the temptation to set a big number is
real.

```ts
// playwright.config.ts
export default defineConfig({
  retries: process.env.CI ? 2 : 0,   // none locally: let it show immediately
});
```

A retry is right where the cause is external and rare: the network blinked, the
build machine stalled, a neighbouring service answered slower than usual. It is
useless where the cause sits inside the test: a dependency on order reproduces on
the second run and on the third, as we saw above.

The main thing is not to read `flaky` as a shade of green. It is a separate
status precisely so that such tests stay visible in the report and can be fixed.
A sound habit: once a sprint, look at the list of flaky tests and take the top
one into work.

## Common mistakes

- **Answering a failure with `waitForTimeout`.** The symptom: the test fails
  again a week later, when the machine got slower.
- **Raising the retry count instead of investigating.** The symptom: the run got
  three times longer and the report is full of `flaky`.
- **Curing flakiness with bigger timeouts.** The symptom: the suite takes forty
  minutes, because every failure waits out its maximum.
- **Turning `fullyParallel` on without preparing data.** The symptom: tests that
  ran in sequence for years start fighting over the same rows.

## Related topics

- [Web-first assertions wait, plain ones do not](./03-assertions.md) — what
  replaces a fixed pause.
- [Every test starts from a clean slate](./04-fixtures-and-isolation.md) — how to
  give tests their own data instead of sharing it.
- [A failing test should explain itself](./07-debugging.md) — how a trace tells a
  race apart from an honest bug.
- Testing — the question bank on test strategy and on which checks are worth
  keeping in a suite at all.
