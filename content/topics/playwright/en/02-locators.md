# A locator describes an element, it does not find one

A locator is a description of an element, not a reference to a found one. The
search happens at the moment of an action or an assertion, and it repeats until
the element is ready. Auto-waiting, strictness and most of this article grow out
of that one fact.

## You can create a locator before the element exists

Creating a locator searches for nothing and touches nothing.

```ts
// tests/tasks.spec.ts
import { test, expect } from '@playwright/test';

test('the filter leaves only open tasks', async ({ page }) => {
  const rows = page.getByRole('listitem');          // the page is not open yet
  const filter = page.getByLabel('Status');

  await page.goto('/tasks');
  await filter.selectOption('open');

  await expect(rows).toHaveCount(20);               // the search happens here
});
```

The `rows` variable is created before `page.goto()`, and that is fine. It holds
the description "elements with the list item role", not an element. Every use of
`rows` searches again against the current state of the page.

This is why a locator never goes stale. The list re-rendered after the filter,
and the same `rows` finds the new rows. The older style, holding a reference to
a found element, broke after a re-render. In a report that looked like a random
failure.

## A queue of checks sits between `click()` and a real click

The action does not happen straight away. First Playwright makes sure the
element is ready for it.

```txt
 What happens between click() and a real click
┌────────────────────────────────────┐
│ 1. click() is called               │
│ the locator is still a description │
└────────────────────────────────────┘
                   │  no search has happened yet
                   ▼
┌────────────────────────────────────┐
│ 2. Find by description             │
│ from scratch on every attempt      │
└────────────────────────────────────┘
                   │  the element is found
                   ▼
┌────────────────────────────────────┐
│ 3. Readiness checks                │
│ visible, stable, receives events,  │
│ enabled                            │
└────────────────────────────────────┘
                   │  every check passed
                   ▼
┌────────────────────────────────────┐
│ 4. Scroll to element               │
│ if it is off screen                │
└────────────────────────────────────┘
                   │  the element is on screen
                   ▼
┌────────────────────────────────────┐
│ 5. Mouse click in the centre       │
│ then wait for navigations          │
└────────────────────────────────────┘
while the element is missing or a check keeps failing,
steps 2 and 3 repeat until the action timeout runs out
```

Those readiness checks are called auto-waiting. They are built into actions, and
there is nothing to turn on. The set of checks depends on the action, because
readiness means different things for a click and for typing.

| action | what is checked before it |
|---|---|
| `click`, `dblclick`, `tap`, `check` | visible, stable, receives events, enabled |
| `hover`, `dragTo` | visible, stable, receives events |
| `fill`, `clear` | visible, enabled, editable |
| `selectOption` | visible, enabled |
| `screenshot` | visible, stable |
| `press`, `focus`, `dispatchEvent` | nothing: the event is sent directly |

The words in the right column are specific checks, not loose language. Stable
means the bounding box of the element stayed the same for two animation frames
in a row. Receives events means the element is the one at the click point, not a
tooltip on top of it. One conclusion follows: `press` and `focus` check nothing,
so they are not a safe stand-in for a click.

The `force: true` option skips the checks, and `trial: true` runs them and then
drops the action itself. The first one is rarely right and usually hides a
defect. The second is handy to test that a button is clickable without clicking
it.

## A failed action tells you which check it got stuck on

A timeout prints a call log instead of a bare "element not found".

```txt
TimeoutError: locator.click: Timeout 2000ms exceeded.
Call log:
  - waiting for getByRole('button', { name: 'Sign in' })
    - locator resolved to <button disabled>Sign in</button>
  - attempting click action
    2 × waiting for element to be visible, enabled and stable
      - element is not enabled
    - retrying click action
    - waiting 20ms
    2 × waiting for element to be visible, enabled and stable
      - element is not enabled
    - retrying click action
      - waiting 100ms
    4 × waiting for element to be visible, enabled and stable
      - element is not enabled
    - retrying click action
      - waiting 500ms
```

The log reads top to bottom and answers three questions at once. The element was
found, so the locator is right. The button was found in the `disabled` state, so
the problem is not the search. The enabled check never passed, so the app never
unlocked the button, and the test is not the thing to fix.

The number before the multiplication sign counts how many times the same log
line repeated. The pauses between attempts grow: 20 milliseconds, then 100, then
500.

The same log goes into the report and into the recording of the run, which is
called a trace. So in CI (continuous integration) you have it without re-running
anything. There is more on that in
[A failing test should explain itself](./07-debugging.md).

## A role locator survives a redesign, a CSS selector does not

The first choice is what the user sees: the role, the label, the text.

```ts
// Fragile: the selector describes the markup, not the meaning
await page.locator('div.card > form > button.btn-primary').click();

// Sturdy: the description matches what the user sees
await page.getByRole('button', { name: 'Sign in' }).click();
await page.getByLabel('Password').fill('correct-horse');
await page.getByPlaceholder('Search tasks').fill('report');
await page.getByText('Page 2 of 5').isVisible();
```

The role comes from the accessibility tree, which the browser builds from the
markup and from ARIA (accessible rich internet applications) attributes. The
`btn-primary` class lasts until the next redesign. The button role with the
"Sign in" name outlives it.

| what you are after | how to describe it | example |
|---|---|---|
| a button, link, heading, field | `getByRole` | `getByRole('button', { name: 'Sign in' })` |
| a field with a label | `getByLabel` | `getByLabel('Password')` |
| a field with a hint inside | `getByPlaceholder` | `getByPlaceholder('Search tasks')` |
| text on the page | `getByText` | `getByText('No tasks')` |
| an image | `getByAltText` | `getByAltText('Maria avatar')` |
| an element with no visible trait | `getByTestId` | `getByTestId('task-row')` |

Note that `getByTestId` is last, and not because it is bad. It survives a
translation and a copy change, but it also checks nothing the user can see. The
attribute behind it is set by the `testIdAttribute` option, and it defaults to
`data-testid`.

## Strictness catches ambiguity before it becomes flakiness

A locator that matches more than one element fails the action with a clear
message.

```txt
Error: expect(locator).toBeVisible() failed

Locator: locator('li')
Expected: visible
Error: strict mode violation: locator('li') resolved to 20 elements:
    1) <li>…</li> aka getByText('May report Done').first()
    2) <li>…</li> aka getByText('Check invoices Done').first()
    3) <li>…</li> aka getByText('Sprint plan Done').first()
    4) <li>…</li> aka getByText('May report Done').nth(1)
    5) <li>…</li> aka getByText('Check invoices Done').nth(1)
    6) <li>…</li> aka getByText('Sprint plan Done').nth(1)
    7) <li>…</li> aka getByText('May report Done').nth(2)
    8) <li>…</li> aka getByText('Check invoices Done').nth(2)
    9) <li>…</li> aka getByText('Sprint plan Done').nth(2)
    10) <li>…</li> aka getByText('May report Done').nth(3)
    ...

Call log:
  - Expect "toBeVisible" locator('li') with timeout 1500ms
  - waiting for locator('li')
```

Another tool would take the first match and move on. The test would pass until
the row order changed, and then turn flaky for no visible reason. Strictness
turns that future flakiness into an honest failure on the very first run.

An action fails the same way, with its own header:
`locator.click: Error: strict mode violation: …`. The list of matches is printed
up to the tenth one, then a line of dots.

The output doubles as a hint. After the word `aka` there is a ready locator for
each match, and you can copy it into the test as a starting point.

```ts
// 1. Narrow the description — the right answer almost every time
await page.getByRole('listitem').filter({ hasText: 'May report' }).click();

// 2. Take one element by index — when the order is the point
await page.getByRole('listitem').first().click();

// 3. Check every match at once — when there should be many
await expect(page.getByRole('listitem')).toHaveCount(20);
```

Strictness has three legitimate exits, shown above. The first is almost always
the best: it keeps a description in the test, not a position. The second is
honest where the first row is exactly what you check. The third removes the
question, because a count assertion expects many elements by design.

## Chaining and filtering narrow the description, they do not search twice

Every link of a chain is the search area for the next link.

```txt
Chaining narrows the description, it does not re-search
┌───────────────────────────┐
│ The whole page            │
│ page                      │
└───────────────────────────┘
              │  .getByRole('list')
              ▼
┌───────────────────────────┐
│ The task list             │
│ role=list                 │
└───────────────────────────┘
              │  .getByRole('listitem')
              ▼
┌───────────────────────────┐
│ List rows                 │
│ role=listitem, 20 of them │
└───────────────────────────┘
              │  .filter({ hasText: 'report' })
              ▼
┌───────────────────────────┐
│ The report row            │
│ exactly one               │
└───────────────────────────┘
the search runs once, at the action or the assertion:
intermediate locators search for nothing and hold nothing
```

A chain does not run several searches. It builds one description, and that
description runs as a whole at the action. So intermediate variables cost
nothing, and they sit well in a page object.

```ts
// tests/tasks.spec.ts
const list = page.getByRole('list');
const rows = list.getByRole('listitem');

// the row with this text inside it
const reportRow = rows.filter({ hasText: 'May report' });
await reportRow.getByRole('button', { name: 'Done' }).click();

// rows that contain an "overdue" badge
const overdue = rows.filter({ has: page.getByTestId('overdue-badge') });
await expect(overdue).toHaveCount(3);

// rows without the "draft" label
const published = rows.filter({ hasNotText: 'draft' });
await expect(published).toHaveCount(17);
```

The `has` filter takes another locator and keeps the rows that contain it. Two
more connectors exist: `and()` requires both descriptions to match, `or()`
accepts either of them. The second one helps where the interface shows either a
"Sign in" button or the name of the user who is already in.

## Not every method auto-waits

Methods that return a value wait for nothing and answer from the current state
of the page.

```ts
// Flaky: count() answers at once, the list may not be rendered yet
const n = await page.getByRole('listitem').count();
expect(n).toBe(20);

// Flaky for the same reason: isVisible() does not wait for the text to appear
if (await page.getByText('No tasks').isVisible()) {
  await page.getByRole('button', { name: 'New task' }).click();
}

// Reliable: the assertion retries until its own timeout runs out
await expect(page.getByRole('listitem')).toHaveCount(20);
```

The methods `count()`, `isVisible()`, `textContent()`, `getAttribute()` and
`all()` return immediately. They are useful while debugging and in the rare
branch, while checks belong to the assertions that wait by themselves. Those are
called web-first assertions, and they have their own article:
[Web-first assertions wait, plain ones do not](./03-assertions.md).

## Common mistakes

- **Describing the markup instead of the meaning.** The symptom: a locator
  breaks after a markup change that changed no behaviour. The cure is
  `getByRole` and `getByLabel`.
- **Silencing strictness with a blind `first()`.** The symptom: the test passes
  while checking a random row. Narrow the description with a filter first.
- **Branching on `isVisible()`.** The symptom: the test behaves differently on a
  fast and a slow machine. Use an assertion for the check.
- **Answering a failure with `force: true`.** The symptom: the failure goes away
  and the interface defect stays. Read the call log first.

## Related topics

- [Web-first assertions wait, plain ones do not](./03-assertions.md) — why
  `expect(locator)` retries and `expect(value)` does not.
- [A failing test should explain itself](./07-debugging.md) — where the call log
  is shown next to the page frames.
- [A flaky test is worse than no test](./08-flakiness-and-parallelism.md) — the
  locator habits that make a test flaky.
- CSS + HTML Advanced — the accessibility tree, roles and names from the markup
  side.
