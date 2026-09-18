# A test controls the network, it does not hope for it

A `route` handler intercepts a request before it leaves for the network. The test
decides what happens next: answer with prepared data, abort the request, change
it, or let it through untouched. That turns the network from a source of
surprises into part of the test setup.

## A handler sits between the page and the network

Registering a handler states a rule: "requests to these addresses are mine".

```ts
// tests/tasks.spec.ts
import { test, expect } from '@playwright/test';

test('an empty list shows the hint', async ({ page }) => {
  await page.route('**/api/tasks*', async (route) => {
    await route.fulfill({
      json: { items: [], total: 0, page: 1, pages: 1 },
    });
  });

  await page.goto('/tasks');

  await expect(page.getByText('No tasks')).toBeVisible();
  await expect(page.getByRole('listitem')).toHaveCount(0);
});
```

The app fetched its data as usual, but the answer came from the test. This is how
you check states that are hard to produce on a real server: an empty list, an
error, a slow answer, broken data.

| method | what it does | how it ends |
|---|---|---|
| `route.fulfill()` | answers with prepared data | the chain stops |
| `route.abort()` | fails the request like a network error | the chain stops |
| `route.continue()` | sends it on, optionally modified | remaining handlers are skipped |
| `route.fallback()` | hands the request to the next handler | the chain continues |

The difference between `continue()` and `fallback()` is the subtle part here. The
first sends the request to the network right away. The second passes it further
down the chain of handlers.

## Handlers run in reverse: the last one declared goes first

Handlers form a chain, and the entry point is the end of the registration list.

```txt
  How GET /api/tasks walks through the handlers
┌────────────────────────────────┐
│ The page sends a request       │
│ a fetch inside the app         │
└────────────────────────────────┘
                 │  intercepted before the network
                 ▼
┌────────────────────────────────┐
│ page.route declared second     │
│ it goes first                  │
└────────────────────────────────┘
                 │  the handler called fallback()
                 ▼
┌────────────────────────────────┐
│ page.route declared first      │
│ it goes second                 │
└────────────────────────────────┘
                 │  fallback() again
                 ▼
┌────────────────────────────────┐
│ context.route                  │
│ after every page.route         │
└────────────────────────────────┘
                 │  fallback() or continue()
                 ▼
┌────────────────────────────────┐
│ The real network               │
│ the request reached the server │
└────────────────────────────────┘
fulfill() and abort() end the chain where they are,
continue() goes to the network past the remaining handlers
```

One test with a print inside each handler shows it.

```ts
test('handler order', async ({ page, context }) => {
  await context.route('**/api/tasks*', async (route) => {
    console.log('  context.route: registered first');
    await route.fallback();
  });
  await page.route('**/api/tasks*', async (route) => {
    console.log('  page.route #1 (registered earlier)');
    await route.fallback();
  });
  await page.route('**/api/tasks*', async (route) => {
    console.log('  page.route #2 (registered later)');
    await route.fallback();
  });

  await page.goto('/tasks');
});
```

```txt
  page.route #2 (registered later)
  page.route #1 (registered earlier)
  context.route: registered first
  ✓  1 tests/route.spec.ts:3:5 › handler order (303ms)
```

Two rules follow. Put the shared stub on the context or at the top of the file,
and the specific one inside the test, where it will override the shared one. If
that specific handler calls `continue()` instead of `fallback()`, the shared one
never runs at all.

## Not everything deserves a stub

A stub makes a test fast and steady, and blind by exactly the same amount.

| what the test checks | where the data comes from |
|---|---|
| rendering of an empty list, an error, long text | a stub in the test |
| a rare server answer: `500`, a timeout, broken `JSON` | a stub in the test |
| that the filter sends the right request | a real server plus a request check |
| that signing in produces a working session | a real server |
| an end-to-end path down to the database | a real server |

The rule is short. Stub what gets in the way of checking the interface, and never
stub the thing the test is there to prove. A sign-in test with a stubbed
`POST /api/login` only checks the markup of the form.

To inspect the request itself, use `route.continue()` with no changes: the
handler sees the request and lets it through.

```ts
test('the filter reaches the server with the right parameter', async ({ page }) => {
  const urls: string[] = [];
  await page.route('**/api/tasks*', async (route) => {
    urls.push(route.request().url());
    await route.continue();                 // the data stays real
  });

  await page.goto('/tasks');
  await page.getByLabel('Status').selectOption('done');
  await expect(page.getByRole('listitem')).toHaveCount(12);

  expect(urls.at(-1)).toContain('status=done');
});
```

## Waiting for a response catches the wrong one unless you narrow it

The `page.waitForResponse` method returns the first matching response, not the
one your action caused.

```ts
test('stale response', async ({ page }) => {
  await page.goto('/tasks');
  const [res] = await Promise.all([
    page.waitForResponse((r) => r.url().includes('/api/tasks')),
    page.getByLabel('Status').selectOption('done'),
  ]);
  console.log(`  status=${new URL(res.url()).searchParams.get('status')}`);
});
```

```txt
  without waiting for the list: status=all
  ✓  1 tests/wait-en.spec.ts:3:5 › stale response (194ms)
```

The test wanted the answer for "done" and caught the answer of the first page
load. That first request was still in flight when the test started waiting, and
the predicate accepted it. There are three ways out, and they cost differently.

- **Narrow the predicate.** A condition like `r.url().includes('status=done')`
  rejects the stray response.
- **Wait for the starting state.** An assertion on the row count says the first
  load has finished.
- **Do not wait for a response at all.** An assertion on an element waits for the
  result instead of the transport.

```ts
// the same check with no response waiting at all
await page.goto('/tasks');
await page.getByLabel('Status').selectOption('done');
await expect(page.getByRole('listitem')).toHaveCount(12);
```

The third one is the default choice. Wait for a response only when the response
itself is under test: its status code, its body, its headers.

## A recording of the traffic replaces the server on later runs

One run can be recorded whole: which requests went out and what answered them.
That recording lives in a file of the HAR (HTTP Archive) format, and from then on
it stands in for the server.

```ts
// recording: go to the real server and store the answers in a file
await page.routeFromHAR('har/tasks.har', { url: '**/api/**', update: true });

// replay: the server is no longer needed
await page.routeFromHAR('har/tasks.har', { url: '**/api/**', update: false });
```

The recorded file is plain `JSON` and reads fine by eye. Below is a fragment of a
real recording of one request.

```json
{
  "log": {
    "creator": {
      "name": "Playwright",
      "version": "1.63.0"
    },
    "entries": [
      {
        "request": {
          "method": "GET",
          "url": "http://localhost:3000/api/tasks?status=all&page=1"
        },
        "response": {
          "status": 200,
          "content": {
            "mimeType": "application/json"
          }
        }
      }
    ]
  }
}
```

Matching is strict on the address and the method, and for `POST` on the request
body as well. A request that is not in the recording is therefore aborted by
default: the `notFound` option is `abort`. Setting it to `fallback` lets such a
request reach the network, which helps while the recording is still incomplete.

A recording ages together with the server, and that is its real price. You refresh
it with the same `update: true` flag and keep it in the repository next to the
test.

## A handler lives until the end of the test unless you remove it

Registration covers the whole test, and sometimes that is one time too many.

```ts
test('first load empty, real data afterwards', async ({ page }) => {
  let calls = 0;
  await page.route('**/api/tasks*', async (route) => {
    calls++;
    await route.fulfill({ json: { items: [], total: 0, page: 1, pages: 1 } });
  }, { times: 1 });                          // fires exactly once

  await page.goto('/tasks');
  await expect(page.getByRole('listitem')).toHaveCount(0);

  await page.getByLabel('Status').selectOption('open');
  await expect(page.getByRole('listitem')).toHaveCount(20);
  console.log(`  the handler fired ${calls} time`);
});
```

```txt
  the handler fired 1 time, later requests went to the network
  ✓  3 tests/route.spec.ts:34:5 › times: 1 (70ms)
```

To remove a handler by hand there is `page.unroute()` for one rule and
`page.unrouteAll()` for all of them. The second takes a `behavior` option: `wait`
lets running handlers finish, `ignoreErrors` swallows their errors.

## Common mistakes

- **Stubbing the very thing under test.** The symptom: a test "checks sign-in"
  and stays green while authentication is broken.
- **Registering the shared handler after the specific one.** The symptom: the
  specific rule stopped working, because the shared one now runs first.
- **Waiting for a response with no narrowing condition.** The symptom: the test
  is green while checking the answer to the previous action.
- **Forgetting `POST` bodies during replay.** The symptom: the list comes from
  the recording, but sign-in fails, because the request body did not match.

## Related topics

- [Web-first assertions wait, plain ones do not](./03-assertions.md) — why an
  element check beats waiting for a response.
- [Sign in once, not in every test](./06-auth-and-state.md) — what happens to the
  session when the network is stubbed.
- [A failing test should explain itself](./07-debugging.md) — where to see every
  request of a run, stubs included.
- HTTP / REST — status codes, headers and request anatomy from the protocol side.
