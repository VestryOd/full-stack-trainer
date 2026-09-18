# A failing test should explain itself

After a failure everything needed for the diagnosis is already on disk: the call
log, a text snapshot of the page, a screenshot, a video and a recording of the
run. That recording is called a trace, and a separate viewer opens it. Set up in
advance, these artefacts answer "what happened" without running the test again.

## The report names the step, not only the test

A long test with no markup reports a line number and nothing else. Splitting it
into steps turns the report into a story of how far the test got.

```ts
// tests/pager.spec.ts
import { test, expect } from '@playwright/test';

test('the pager moves forward', async ({ page }) => {
  await test.step('open the task list', async () => {
    await page.goto('/tasks');
    await expect(page.getByRole('listitem')).toHaveCount(20);
  });

  await test.step('go to page two', async () => {
    await page.getByRole('button', { name: 'Next' }).click();
    await expect(page.getByText('Page 2 of 3')).toBeVisible();
  });

  await test.step('pager label', async () => {
    await expect(page.getByText('Page 2 of 5')).toBeVisible({ timeout: 2000 });
  });
});
```

The failure header now carries the step name, and it shows that the first two
steps went through.

```txt
1) tests/pager.spec.ts:3:5 › the pager moves forward › pager label

  Error: expect(locator).toBeVisible() failed

  Locator: getByText('Page 2 of 5')
  Expected: visible
  Timeout: 2000ms
  Error: element(s) not found
```

The same steps become collapsible groups in the trace viewer, which makes them
worth the lines even in short tests. A step takes two useful options: `box: true`
hides its internals and leaves only the name in the report, and `params` attaches
arbitrary data that the viewer then shows.

## A trace is an archive, not a picture

The `trace.zip` file is assembled during the run, and it holds several different
recordings.

```txt
     What sits inside trace.zip
┌─────────────────────────────────┐
│ Test actions and steps          │
│ test.trace, 1-trace.trace       │
├─────────────────────────────────┤
│ Screen frames for every action  │
│ screencast/*.jpeg               │
├─────────────────────────────────┤
│ Page snapshots before and after │
│ resources/*.html and *.json     │
├─────────────────────────────────┤
│ Network traffic of the run      │
│ 1-trace.network                 │
├─────────────────────────────────┤
│ Test source and call stacks     │
│ src/*.ts, *-trace.stacks        │
└─────────────────────────────────┘
all of it is captured on the browser and test side:
server logs and database state are not in the archive
```

Any unzip tool lists them. Below is the real content of an archive from our
stand, with long names shortened.

```txt
src/….ts
attachments/…
test.trace
1-trace.trace
1-trace.network
screencast/page@…-1789723067141.jpeg
screencast/page@…-1789723067176.jpeg
resources/….html
resources/….json
1-trace.stacks
```

That set is what the viewer turns into its panes: the action list on the left,
the film strip on top, and tabs for network, console, source and call stack at
the bottom. A page snapshot is stored markup rather than an image, so inside the
viewer you can hover it and pick elements.

| what the trace shows | what it does not hold |
|---|---|
| every action with its time and duration | server logs |
| page markup before, during and after an action | database state |
| requests, responses and their bodies | anything from before recording started |
| browser console messages | what happened in another context |

The command to open an archive is `npx playwright show-trace trace.zip`. The file
is self-contained: attach it to a ticket and a colleague sees the same run
without running anything.

## The error context file reads straight in the terminal

Next to the trace a failure leaves a text file called `error-context.md`. It
describes the page at the moment of failure as a tree of roles.

```yaml
- heading "Tasks" [level=1]
- text: Status
- combobox "Status":
  - option "all" [selected]
  - option "open"
  - option "done"
- list:
  - listitem:
    - text: Sprint plan
    - button "Done"
  - listitem:
    - text: May report
    - button "Done"
```

Such a snapshot answers the most common question behind a locator failure: what
was on the page at all. The heading is "Tasks", the filter is a `combobox` with
three options, every row carries a "Done" button. This is the same tree that
`getByRole` reads from, so the file tells you straight away which locator would
reach the element.

## Videos and screenshots cost disk space, so they are switched on by condition

Artefacts are not free, and the gap between "always" and "on failure" shows up on
a long run.

```ts
// playwright.config.ts
export default defineConfig({
  use: {
    trace: 'on-first-retry',        // recorded on the first retry only
    screenshot: 'only-on-failure',  // a screenshot for failed tests only
    video: 'retain-on-failure',     // recorded always, kept for failures
  },
});
```

Here is what one failed test took on our stand.

```txt
2.7K  error-context.md
54K   test-failed-1.png
48K   video.webm
167K  trace.zip
```

Two hundred kilobytes per test looks harmless while there are twenty tests. At
five hundred tests, recording everything turns into a hundred megabytes of
artefacts per run, which is felt by the disk and by the upload step alike. Hence
the default setup: `on-first-retry` for the trace, `only-on-failure` for the
screenshot and the video.

| value | when the artefact is kept |
|---|---|
| `off` | never |
| `on` | always, passing tests included |
| `only-on-failure` | for failures (`screenshot`) |
| `retain-on-failure` | recorded always, kept for failures |
| `on-first-retry` | on the first retry only (`trace`, `video`) |

## Watch mode and step-by-step pausing belong to writing, not to diagnosis

Investigating a failed run and writing a new test are different jobs with
different tools.

```bash
# interactive mode: test list, frames, re-run on file change
npx playwright test --ui

# step-by-step pausing: opens the inspector and walks the actions
npx playwright test --debug

# the same from code: stop exactly where you put it
# await page.pause();
```

The `--ui` flag opens a window where tests run one at a time, every action and
the recording are visible, and a file re-runs itself after an edit. The `--debug`
flag starts the inspector with a "step over" button and a locator picker. The
`page.pause()` call does the same, stopping exactly where you left it.

## `codegen` produces a draft, not a test

Recording actions in a browser saves time on the routine: the command opens a
browser and writes code as you click.

```bash
npx playwright codegen http://localhost:3000/login --output tests/draft.spec.ts
```

Before you do anything, the file holds only a stub — here it is in full, exactly
as the tool writes it.

```ts
import { test, expect } from '@playwright/test';

test('test', async ({ page }) => {
});
```

Every action then appends itself to the body. The useful flags are in the help
output: `--target` picks the language, `--test-id-attribute` says which attribute
counts as an element marker, `--device` turns on phone emulation, and `--browser`
changes the recording browser.

What recording gives you is a draft. It holds all your actions in a row, extra
clicks included, and not a single check.

```ts
// what the recording produced
test('test', async ({ page }) => {
  await page.goto('http://localhost:3000/login');
  await page.getByRole('textbox', { name: 'Email' }).click();
  await page.getByRole('textbox', { name: 'Email' }).fill('maria@example.com');
  await page.getByRole('textbox', { name: 'Password' }).click();
  await page.getByRole('textbox', { name: 'Password' }).fill('correct-horse');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByRole('button', { name: 'Next' }).click();
});
```

```ts
// what it becomes: a name, a relative address, checks instead of blind clicks
test('the Next button opens page two of the list', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill('maria@example.com');
  await page.getByLabel('Password').fill('correct-horse');
  await page.getByRole('button', { name: 'Sign in' }).click();

  await expect(page.getByRole('listitem')).toHaveCount(20);
  await page.getByRole('button', { name: 'Next' }).click();

  await expect(page.getByText('Page 2 of 3')).toBeVisible();
});
```

The difference between those two snippets is exactly the work recording does not
do: a test name instead of `test`, a relative address instead of a full one,
waiting on state instead of a chain of clicks, and checks where there were none.

## Common mistakes

- **Diagnosing a failure by running it again.** The symptom: the test passes the
  second time and the cause stays unknown. The trace of the first run is already
  on disk.
- **Leaving `trace: 'on'` in the config permanently.** The symptom: the run got
  slower and the artefacts take gigabytes.
- **Leaving `page.pause()` in the code.** The symptom: the run on the build
  machine hangs until the timeout, because it is waiting for a human.
- **Treating `codegen` as a test generator.** The symptom: a suite of clicks with
  no checks, green while the app is broken.

## Related topics

- [A locator describes an element, it does not find one](./02-locators.md) — how
  to read the call log and why it names the check that blocked the action.
- [Web-first assertions wait, plain ones do not](./03-assertions.md) — where the
  `Expected` and `Received` lines come from.
- [A flaky test is worse than no test](./08-flakiness-and-parallelism.md) — how a
  trace tells a race apart from an honest bug.
- [A pipeline run: what Playwright asks of the build machine](./09-ci-and-visual.md)
  — where to keep artefacts and what to upload from the pipeline.
