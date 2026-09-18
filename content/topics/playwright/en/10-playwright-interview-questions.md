# Playwright: interview questions

## How to use this cheat sheet

Every answer below is the short version of what the articles of this topic cover
in full. Playwright questions almost always come in two storeys: first "how does
it work", a minute later "and why is it built that way" or "what did you do when
it broke".

That is why every group ends with a section of follow-up questions: it shows
where the conversation usually goes next. A follow-up that catches you off guard
is a signal to go back to the matching article.

| group | about | article |
|---|---|---|
| 1 | the model and isolation | 01 |
| 2 | locators and waiting | 02 |
| 3 | assertions and timeouts | 03 |
| 4 | fixtures, sign-in, network | 04, 05, 06 |
| 5 | flakiness and parallelism | 08 |
| 6 | debugging and the build machine | 07, 09 |

## Group 1: the model and isolation

**1. How does a test drive the browser, and why is this not emulation?**

A test is a Node.js process that launches a real browser next to itself and keeps
one connection to it. Commands travel over an automation protocol: in Chromium it
is built into the browser and called `Chrome DevTools Protocol`, while for
Firefox and WebKit (the engine behind Safari) Playwright ships its own builds.

Two consequences follow, and those are what interviewers probe:

- **The browser version is tied to the package version.** Builds arrive with
  `@playwright/test`, so "works for me, fails on the build machine" often means
  two different package versions.
- **There is no driver in between.** The connection opens once and lives for the
  whole run.

```bash
# browser builds are installed separately and versioned by the package
npx playwright install --with-deps chromium
```

**2. What does a browser context isolate, and what does it not?**

A context is a separate profile inside the browser process, close in spirit to an
incognito window. It carries away all page state and knows nothing about the test
process.

| isolated by the context | isolated by nothing |
|---|---|
| cookies, `localStorage`, `sessionStorage` | module variables in the test file |
| cache and permissions | rows in the database |
| the tabs of that context | files on disk and queues |

The practical conclusion: a clean slate per test is free, and all server-side
state is yours to reset.

**3. Why would a test need a second context?**

So that one scenario can have two users in it. A test gets one context and one
session, so a second tab of the same context is still the same user.

```ts
test('another user cannot see the task', async ({ browser }) => {
  const maria = await browser.newContext({ storageState: '.auth/maria.json' });
  const ivan = await browser.newContext({ storageState: '.auth/ivan.json' });
  // two pages, two sessions, one browser
  await maria.close();
  await ivan.close();
});
```

## Follow-up questions (group 1)

```txt
"How many browsers start for a run of 500 tests?" → one per
worker, not one per test: a context is cheap, a browser
process is not

"A test failed. Does the browser restart?" → yes, but only
after a failure: the worker is thrown away with it

"Where does a session live, in the browser or the context?"
→ in the context, which is why two contexts share nothing
```

## Group 2: locators and waiting

**4. Is a locator a found element?**

No, it is a description of one. The search runs at the action or the assertion
and repeats until the element is ready. That is why a locator can be created
before the page is open, and why it does not go stale after a re-render.

**5. What happens between a `click()` call and a real click?**

A queue of readiness checks, known as auto-waiting. A click needs four of them:
the element is visible, stable, receives events and is enabled.

| action | what is checked |
|---|---|
| `click`, `check`, `tap` | visible, stable, receives events, enabled |
| `fill`, `clear` | visible, enabled, editable |
| `press`, `focus` | nothing: the event is sent directly |

The last row is a common source of mistakes. Swapping a click for `press` looks
like a way around flakiness while it simply turns the checks off.

**6. What is locator strictness for?**

So that ambiguity becomes a failure now instead of flakiness later. If more than
one element matches, the action fails and lists the matches.

```txt
Error: strict mode violation: locator('li') resolved to 20 elements:
    1) <li>…</li> aka getByText('May report Done').first()
    2) <li>…</li> aka getByText('Check invoices Done').first()
    ...
```

There are three exits: narrow the description with a filter, take one element by
index, or check them all with `toHaveCount`. The first is the best, because it
keeps meaning in the test instead of a position.

## Follow-up questions (group 2)

```txt
"Why is getByRole better than a CSS selector?" → it
describes what the user sees and survives a redesign

"count() returns a number — why is that flaky?" → because it
does not wait: the number is taken before the re-render

"How do you find which check blocked the action?" → read the
call log: it says "element is not enabled"
```

## Group 3: assertions and timeouts

**7. How does `expect(locator)` differ from `expect(value)`?**

The first repeats the check until it matches or until time runs out. The second
compares an already-collected value once. The first form is called a web-first
assertion.

```ts
// waits: the check repeats until it matches
await expect(page.getByRole('listitem')).toHaveCount(20);

// does not wait: the number is taken first and compared once
expect(await page.getByRole('listitem').count()).toBe(20);
```

The `await` keyword tells them apart: the waiting form has it before `expect`,
the plain one inside the brackets.

**8. Which timeout wins when several are set?**

The strictest one. An option on a single assertion overrides the shared
`expect.timeout`, and the test timeout cuts everything else short.

| timeout | default |
|---|---|
| test | 30,000 ms |
| assertion | 5,000 ms |
| action and navigation | none |

Hence the classic mistake: an assertion is given thirty seconds while the test
still lives thirty, and the failure comes from the test.

**9. When are soft assertions appropriate?**

When the checks are independent and you want the full list of mismatches:
several fields of one card, several columns of a row. The `expect.soft` form
records the error and carries on, though the test still counts as failed.

## Follow-up questions (group 3)

```txt
"What does not.toBeVisible() do?" → waits until the
condition turns false, spending its whole timeout

"How do you check something the page does not show?" →
expect.poll or expect(...).toPass: retry arbitrary code

"Why is toPass needed when poll exists?" → poll repeats a
function, toPass repeats a whole block with several
assertions inside
```

## Group 4: fixtures, signed-in state, network

**10. Why is a fixture better than `beforeEach`?**

Because it is built only for the tests that asked for it, and it is torn down
even after a failure. The test also reads whole: its brackets list everything it
needs.

Scope is chosen by cost, and that is almost always the follow-up.

| scope | when it is built | typical resident |
|---|---|---|
| `test` | before every test | a page, test data |
| `worker` | once per process | a browser, an account, a stub server |

The opposite dependency is forbidden: a `worker` fixture cannot ask for `page`,
because a page lives for one test.

**11. What goes into a signed-in state snapshot?**

Cookies and `localStorage` per origin, and that is all.

```json
{
  "cookies": [{ "name": "session", "value": "…", "domain": "localhost" }],
  "origins": [
    { "origin": "http://localhost:3000",
      "localStorage": [{ "name": "token", "value": "…" }] }
  ]
}
```

There is no `sessionStorage` in the snapshot, and `IndexedDB` only arrives with
an explicit option. An app that keeps its session in `sessionStorage` cannot be
restored this way, and that is a ready-made follow-up.

**12. In what order do network handlers run?**

In reverse registration order: the last one declared goes first, and page
handlers run before context handlers.

```txt
page.route #2 (registered later)
page.route #1 (registered earlier)
context.route: registered first
```

Then the difference between two methods matters: `fallback()` passes the request
to the next handler, while `continue()` sends it to the network past the rest.

**13. What should be stubbed and what should not?**

Stub what stands in the way of checking the interface: an empty list, a server
error, a broken answer. Never stub the thing the test exists to prove. A sign-in
test with a stubbed `POST /api/login` checks the markup of the form and nothing
else.

## Follow-up questions (group 4)

```txt
"How do you give each worker its own user?" → a worker-scope
fixture plus the worker index inside the email address

"What is wrong with a bare waitForResponse?" → it catches
the first matching response, including one already in flight

"Why record traffic when stubbing exists?" → a recording
holds the real server answers, captured once
```

## Group 5: flakiness and parallelism

**14. How do you tell a race from an order dependency?**

By how they behave on retries. A race against time usually disappears on the
second run, while a dependency on shared data reproduces every time.

```txt
✓  1 tests/shared.spec.ts:3:5 › import adds tasks (38ms)
✘  2 tests/shared.spec.ts:9:5 › three pages (5.1s)
✘  3 tests/shared.spec.ts:9:5 › three pages (retry #1) (5.1s)
✘  4 tests/shared.spec.ts:9:5 › three pages (retry #2) (5.1s)
```

Three identical failures in a row are the diagnosis: the data was spoiled by an
earlier test, and no retry brings it back.

**15. When does a retry cure a problem and when does it hide one?**

It cures where the cause is external and rare. It hides where the cause sits
inside the test.

| a retry helps | a retry is useless |
|---|---|
| the network blinked, a service was slow | a fixed pause inside the test |
| the build machine stalled under load | shared state and test order |

The `flaky` status in a report is not a shade of green. It is a list of things to
fix.

**16. Workers or shards?**

Workers are processes on one machine; sharding splits the suite between machines.
What they share is the unit of splitting: a file, not a test.

```txt
Running 8 tests using 4 workers
Running 4 tests using 2 workers, shard 1 of 2
```

Eight tests in one file still go to one process under four workers, until you
allow otherwise through `mode: 'parallel'` or `fullyParallel`.

## Follow-up questions (group 5)

```txt
"How do you prove a test is flaky?" → run it with
--repeat-each and show the share of failures

"Why not set retries: 5?" → the run gets longer and the
defect stays; a retry is not an investigation

"What about a test that has been flaky for months?" → fix it
or delete it: a red nobody believes is worse than nothing
```

## Group 6: debugging and the build machine

**17. What is inside a trace, and what is not?**

Inside the archive is everything the browser and the test saw.

```txt
test.trace          test actions and steps
screencast/*.jpeg   screen frames for every action
resources/*.html    page markup before and after an action
1-trace.network     network traffic of the run
src/*.ts            test source and call stacks
```

What is missing is anything that happened outside the browser: server logs and
database state. The archive opens with `npx playwright show-trace trace.zip` and
needs no second run. Next to it a failure leaves a text file with the tree of
page roles at the moment of the error.

**18. Why does a visual baseline not travel between machines?**

Because it belongs to a browser and a system, and Playwright writes both into the
file name.

```txt
tests/vis.spec.ts-snapshots/tasks-chromium-darwin.png
                                  ↑        ↑
                              browser    system
```

Pixels depend on fonts, anti-aliasing and screen density, so a shot from a laptop
will not match one from a container. The tool does fight for repeatability on its
own: it disables animations, waits for fonts and takes the picture twice until it
settles. The rest is on you: record baselines in the image that checks them.

**19. What does Playwright ask of a build machine?**

Four things, and it pays to name them separately:

- **The same environment.** Time zone, locale and window size come from the
  config; the browser version and the fonts come from a container of the same
  version as the package.
- **Workers matching the cores.** Four workers on two cores fight over the
  processor and produce timeout failures.
- **Room for artefacts.** The report, traces of failures and mismatch images are
  uploaded out of the pipeline.
- **A report merge.** Shards write the intermediate `blob` format, then
  `merge-reports` glues them together.

## Follow-up questions (group 6)

```txt
"What should the pipeline cache?" → npm dependencies;
caching browsers is discouraged, restoring is no faster than
downloading

"A test fails only in the container. Where do you start?" →
with the trace from the artefacts, not a local rerun

"How do you update baselines?" → --update-snapshots, and
only where those baselines are later checked
```

## A note on versions

Playwright ships often, and the details move: option names, the set of
assertions, the contents of a report. The numbers in this file were taken on
version 1.63.0, released on 4 September 2026. An honest phrasing in an interview
sounds like this: "on the version I worked with it behaved this way, and the
current state is in the release notes".

That is not a dodge but a working habit. Someone who names a version usually pins
it in `package.json` too, instead of installing "the latest".

## Related topics

- [The Playwright model: browser, context, page](./01-playwright-model.md) —
  group 1 in full.
- [A locator describes an element, it does not find one](./02-locators.md) —
  group 2 in full.
- [Web-first assertions wait, plain ones do not](./03-assertions.md) — group 3 in
  full.
- [A flaky test is worse than no test](./08-flakiness-and-parallelism.md) —
  group 5 in full.
- Testing — the question bank on the test pyramid, unit level and test doubles:
  the neighbouring topic starts there.
