# Testing

## Theory

### The stack: Vitest instead of Karma

Since v21 the default test runner is **Vitest**: in the `unit-test` builder schema the `runner` option defaults to `vitest` and accepts `karma` for older projects. Tests run in Node with jsdom, or in a real browser if you specify `browsers`. Useful builder options: `setupFiles`, `providersFile` (a file exporting an array of providers for the whole test environment), `coverage`, `filter`, `ui`, `debug`, `isolate`.

One limitation follows from that, and it breaks half of all older tests: **`fakeAsync`/`tick` do not work with Vitest**. The Vitest runner does not patch zone.js, and the documentation says plainly that `fakeAsync` is no longer recommended. Use ordinary `async`/`await`, `await fixture.whenStable()`, and Vitest's own fake timers (`vi.useFakeTimers()`) instead.

### What to test with what

Pick the tool from what you are testing. Most rows below need no `TestBed` at all.

| what you test | the tool | is `TestBed` needed |
|---|---|---|
| a signal store, its commands | a plain unit test | no: `new Store()` or `inject` |
| a pure function, a pipe | a plain unit test | no |
| a component and its template | `TestBed` + `fixture` | yes |
| the HTTP layer and interceptors | `provideHttpClientTesting` | yes |
| a guard, a resolver | `TestBed.runInInjectionContext` | yes |
| a user journey | Playwright / Cypress | no: a real browser |

The less `TestBed`, the faster and steadier the suite. That is exactly why logic moves into services (chapter 05).

The key idea: **a signal store is tested like an ordinary class**. No `TestBed`, no rendering — create it, call a command, read a signal, compare. That follows directly from the architecture of chapter 05. It is also the main argument for moving logic out of components: the tests become fast and independent of markup.

### TestBed and swapping dependencies

`TestBed` is a configurable injector plus the ability to create a component. Swapping dependencies through dependency injection (DI) is exactly what makes Angular tests worth liking. No module mocking is needed: a different provider is enough (chapter 04).

```
           A component test: the order of steps
┌────────────────────────────────────────────────────────┐
│ TestBed.configureTestingModule({ providers: [...] })   │
│ swap dependencies here: a mock instead of the real API │
└────────────────────────────────────────────────────────┘
                             │  creation
                             ▼
┌────────────────────────────────────────────────────────┐
│ const fixture = TestBed.createComponent(TicketList)    │
│ the instance exists, the template is not checked yet   │
└────────────────────────────────────────────────────────┘
                             │  inputs
                             ▼
┌────────────────────────────────────────────────────────┐
│ fixture.componentRef.setInput('ticket', ticket)        │
│ setInput marks the component as changed (chapter 11)   │
└────────────────────────────────────────────────────────┘
                             │  sync
                             ▼
┌────────────────────────────────────────────────────────┐
│ await fixture.whenStable()                             │
│ wait for the template check and microtasks             │
│ instead of a manual detectChanges()                    │
└────────────────────────────────────────────────────────┘
                             │  assert
                             ▼
┌────────────────────────────────────────────────────────┐
│ expect(...) on the DOM, a harness or signals           │
│ httpTesting.verify() in afterEach                      │
└────────────────────────────────────────────────────────┘
fakeAsync/tick do not work with the Vitest runner: zone.js
is not patched there, and fakeAsync is no longer recommended
```

Two places where v22 tests differ from tests written three years ago:

1. **`await fixture.whenStable()` instead of `fixture.detectChanges()`.** In zoneless tests a manual `detectChanges()` is a forced synchronization, and it can hide a genuine bug. A component that forgot to notify the framework "works" in the test but not in the application. With `whenStable()` Angular schedules the check itself, so the test exercises exactly the behaviour production will have.
2. **Inputs are set through `fixture.componentRef.setInput(...)`.** A direct `component.ticket = x` does not mark the component as changed (chapter 11). With signal inputs it will not even compile, because `input()` returns a read-only signal.

Handy tools:

- `TestBed.inject(Token)` fetches a dependency.
- `TestBed.overrideProvider(...)` replaces one after configuration.
- `TestBed.runInInjectionContext(fn)` invokes a guard, a resolver or any function using `inject()`.
- `DeferBlockBehavior.Manual` steps through the states of a `@defer` block (chapter 12).

### HTTP: HttpTestingController

```ts
TestBed.configureTestingModule({
  providers: [TicketApi, provideHttpClient(), provideHttpClientTesting()],
});

const httpTesting = TestBed.inject(HttpTestingController);
const api = TestBed.inject(TicketApi);

const promise = firstValueFrom(api.list({ status: 'open' }));

// expectOne fails with a readable message when there are zero or several requests
const req = httpTesting.expectOne((r) => r.url.endsWith('/tickets'));
expect(req.request.method).toBe('GET');
expect(req.request.params.get('status')).toBe('open');

req.flush([{ id: 1, title: 'Test' }]);       // deliver the response
expect(await promise).toHaveLength(1);

httpTesting.verify();                         // no outstanding requests remain
```

The controller's API: `expectOne`, `expectNone`, `match` (several requests), `verify`. On a request: `flush(body, opts)` for success, `error(new ProgressEvent('error'), { status: 500 })` for a failure. Move `verify()` into `afterEach` — then every test also asserts that no unexpected requests were made.

### Harnesses: tests that survive markup changes

`cdk/testing` puts a layer between the test and the DOM (document object model). A harness describes a component through its *behaviour*: click, read text, pick an option. The test itself knows nothing about classes or nesting.

It is loaded with `TestbedHarnessEnvironment.loader(fixture)`, then `getHarness(Predicate)` / `getAllHarnesses(...)`. Your own harness is a class extending `ComponentHarness` with locators (`this.locatorFor('.selector')`) and domain methods.

The point is simple: refactoring markup must not break tests. A test looking for `.ticket-card__title > span` breaks on any markup tweak; a harness with a `getTitle()` method does not.

### e2e — an overview

Unit and component tests do not verify what the user cares about. Does the whole path work: open the list, filter, create a ticket, see it in the list? That is what an end-to-end (e2e) test checks, and it needs a real browser: **Playwright** (the de-facto standard today) or Cypress.

The rules for sane e2e:

- Keep them few — a handful of key journeys.
- Do not use them as a substitute for unit tests.
- Find elements by role, text or `data-testid`, not by CSS classes.
- Do not mock the backend without a reason, or the test loses its point.

Protractor, which Angular used to ship, was removed long ago.

## React parallels

The tasks map one to one; the tools do not.

| the task | React: Jest/Vitest + React Testing Library | Angular: `TestBed` |
|---|---|---|
| swap a dependency | `jest.mock` on the module | a provider in `TestBed` |
| render a component | `render(<Cmp prop={x} />)` | `createComponent` + `setInput` |
| wait for an update | `await waitFor(...)` | `await fixture.whenStable()` |
| find an element | `screen.getByRole(...)` | a harness or `DebugElement` |
| mock the network | `msw` / `fetch-mock` | `provideHttpClientTesting` |
| assert state | through the DOM | through the DOM or signals directly |

- **Swapping dependencies is Angular's main advantage.** With `jest.mock('./api')` you intercept an import at the bundler level: you must know the path, remember hoisting, and type the mock yourself. In Angular a dependency is requested by token, so swapping it is one ordinary entry: `{ provide: TicketApi, useValue: fake }`. It is typed and independent of file paths. That is what makes DI a tool rather than an extra layer (chapter 04).
- **The React Testing Library philosophy versus access to the instance.** React Testing Library (RTL) deliberately denies access to component state: assert what the user sees. In Angular you have `fixture.componentInstance`, and with signals you can read state directly. Convenient, but it slides easily into testing implementation. A sensible boundary: assert state in service tests, and test components through the DOM or a harness.
- **Waiting for updates.** RTL's `waitFor` polls the DOM until success; Angular's `whenStable()` waits until the framework has run its scheduled synchronization. The reliability differs: `whenStable()` knows about the scheduler rather than guessing with a timeout.
- **Speed.** Service unit tests in Angular are exactly as fast as in React. But `TestBed` is heavier than RTL's `render()`, because it boots the compiler and an injector. The conclusion is the opposite of the React habit of testing everything through a render. In Angular it pays to keep logic in services and test it without `TestBed`.
- **Where the habit breaks:** `component.input = value` instead of `setInput()`. In React props are set at render time, so the analogy suggests just assigning the field. In Angular that is a compile error with signal inputs, and a silent failure with older ones. The component is not marked as changed, the template never updates, and the test fails on a baffling `expect`.

## What you will see in legacy code

- **Karma + Jasmine:** a `karma.conf.js`, a `test.ts` with `require.context`, and `ng test` opening a browser. It still works (`runner: karma`), but new projects use Vitest and its `expect` rather than Jasmine's.
- **`fakeAsync`/`tick`/`flushMicrotasks`** in every async test — they do not work with Vitest at all. Replacements: `async`/`await`, `await fixture.whenStable()`, `vi.useFakeTimers()`.
- **`fixture.detectChanges()` after every line** — a zone-era habit. In zoneless it is also dangerous: the test starts passing where the application would not update.
- **`component.ticket = ticket; fixture.detectChanges();`** instead of `componentRef.setInput()`.
- **`TestBed.configureTestingModule({ declarations: [...], imports: [SomeModule] })`** — the module era; standalone components are simply listed in `imports`.
- **Spies for everything:** `jasmine.createSpyObj('TicketApi', ['list'])` with hand-written typing and `spyOn(service, 'method')` where a plain stub object through a provider would do.
- **`HttpClientTestingModule` in `imports`** — replaced by the `provideHttpClientTesting()` function.

## What we add to the project

Three sets of tests, plus one e2e journey as an example:

- Unit tests for `TicketStore`, with no `TestBed`.
- An HTTP-layer test with `HttpTestingController`, including the interceptor.
- A list component test with the API swapped through a provider, plus a harness for the ticket card.

## Exercise

**Input:** the project from chapter 12.
**Output:** a suite that fails for real reasons and does not break when markup changes.

Requirements:

1. Unit tests for `TicketStore` without `TestBed`. Assert by reading the signals directly:
   - `add` prepends.
   - `update` preserves order and leaves the other objects untouched.
   - `remove` with a missing id does not throw.
   - The `computed` counters recompute.
2. HTTP-layer tests: `TicketApi.list()` builds the right URL and params; `create()` sends the body; a 500 leads to the expected behaviour. `verify()` goes in `afterEach`.
3. An interceptor test: a request with a token gets the `Authorization` header, a request with `SKIP_AUTH` does not. Think about how to verify interceptor order.
4. A `TicketList` component test. Swap `TicketApi` for a stub through a provider and wait for `whenStable()`. Then assert that the right number of cards rendered, and that an empty response shows the empty state. No `fixture.detectChanges()` and no `fakeAsync`.
5. An interaction test: clicking a card changes the selection. Set inputs through `componentRef.setInput()`.
6. A harness: write `TicketCardHarness` with `getTitle()`, `getStatus()`, `isSelected()`, `click()`. Rewrite the test from step 5 on top of it and confirm that renaming a CSS class does not break it.
7. A guard: test `adminMatchGuard` through `TestBed.runInInjectionContext()` with two different roles.
8. One Playwright e2e: open the list, filter by status, create a ticket, see it in the list. Select by role and text.

Edge cases to think about:

- A test passes with `fixture.detectChanges()` but fails with `await fixture.whenStable()`. What does that tell you about the component?
- The component uses `httpResource`. What must the test do for the request to go out and the response to arrive?
- `httpTesting.verify()` fails with "one request is outstanding". What are the three most likely causes?
- You swapped `TicketApi` for a stub but the component still sends real requests. Where do you look?
- Testing a `@defer` block: how do you assert that the `@placeholder` is shown rather than the content?

## Solution walkthrough

`src/app/tickets/ticket-store.spec.ts` — the fastest and most valuable test:

```ts
import { TestBed } from '@angular/core/testing';
import { TicketStore } from './ticket-store';

describe('TicketStore', () => {
  // TestBed is only here to obtain an instance with its dependencies;
  // there is no component, no template and no change detection
  function createStore(): TicketStore {
    TestBed.configureTestingModule({ providers: [TicketStore] });
    return TestBed.inject(TicketStore);
  }

  it('prepends a ticket to the list', () => {
    const store = createStore();
    const before = store.tickets().length;

    store.add(makeTicket({ id: 999, title: 'New' }));

    // state is read directly: a signal is just a call
    expect(store.tickets()).toHaveLength(before + 1);
    expect(store.tickets()[0].id).toBe(999);
  });

  it('update preserves order and does not recreate the other objects', () => {
    const store = createStore();
    const [first, second] = store.tickets();

    store.update(second.id, { title: 'Patched' });

    const after = store.tickets();
    expect(after[1].title).toBe('Patched');
    // the important property of an immutable update: neighbours keep their
    // references, so OnPush cards are not re-checked (chapter 03)
    expect(after[0]).toBe(first);
  });

  it('remove with a missing id breaks nothing', () => {
    const store = createStore();
    const before = store.tickets();

    expect(() => store.remove(-1)).not.toThrow();
    expect(store.tickets()).toEqual(before);
  });

  it('counters are derived from the state', () => {
    const store = createStore();
    store.add(makeTicket({ id: 1000, assignee: null }));

    // the computed recomputed itself: no "update the counter" code in the store
    expect(store.unassignedCount()).toBeGreaterThan(0);
  });
});
```

`src/app/tickets/ticket-api.spec.ts` — the HTTP layer:

```ts
import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';
import { provideAppConfig } from '../core/app-config';
import { TicketApi } from './ticket-api';

describe('TicketApi', () => {
  let httpTesting: HttpTestingController;
  let api: TicketApi;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        TicketApi,
        provideHttpClient(),
        provideHttpClientTesting(),   // swaps the backend, no real network
        ...provideAppConfig({ apiUrl: '/api' }),
      ],
    });
    httpTesting = TestBed.inject(HttpTestingController);
    api = TestBed.inject(TicketApi);
  });

  // one place that asserts "no outstanding requests" for every test
  afterEach(() => httpTesting.verify());

  it('passes filters as query parameters', async () => {
    const promise = firstValueFrom(api.list({ status: 'open', q: 'pdf' }));

    const req = httpTesting.expectOne((r) => r.url === '/api/tickets');
    expect(req.request.method).toBe('GET');
    // params rather than a URL substring: the test ignores parameter order
    expect(req.request.params.get('status')).toBe('open');
    expect(req.request.params.get('q')).toBe('pdf');

    req.flush([]);
    await promise;
  });

  it('propagates a 500 to the caller', async () => {
    const promise = firstValueFrom(api.list({}));
    httpTesting
      .expectOne('/api/tickets?page=1')
      .error(new ProgressEvent('error'), { status: 500, statusText: 'Server Error' });

    await expect(promise).rejects.toMatchObject({ status: 500 });
  });
});
```

The interceptor test — the same `HttpTestingController`, but with the real chain:

```ts
describe('authInterceptor', () => {
  it('adds the token and respects SKIP_AUTH', async () => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        { provide: AuthStore, useValue: { token: signal('t0ken') } },
      ],
    });
    const http = TestBed.inject(HttpClient);
    const httpTesting = TestBed.inject(HttpTestingController);

    void firstValueFrom(http.get('/api/tickets'));
    expect(httpTesting.expectOne('/api/tickets').request.headers.get('Authorization'))
      .toBe('Bearer t0ken');

    void firstValueFrom(
      http.get('/api/public/status', { context: new HttpContext().set(SKIP_AUTH, true) }),
    );
    expect(httpTesting.expectOne('/api/public/status').request.headers.has('Authorization'))
      .toBe(false);

    httpTesting.verify();
  });
});
```

`src/app/tickets/ticket-list.spec.ts` — a component with a swapped API:

```ts
describe('TicketList', () => {
  const fakeApi = {
    list: (params: TicketListParams) =>
      of(TICKETS.filter((t) => !params.status || t.status === params.status)),
  };

  async function setup() {
    TestBed.configureTestingModule({
      imports: [TicketList],                    // a standalone component: just imports
      providers: [
        // Swapping through DI: no module mocking, no file paths to know.
        // The stub is structurally typed, so the compiler checks compatibility
        { provide: TicketApi, useValue: fakeApi },
      ],
    });

    const fixture = TestBed.createComponent(TicketList);
    // whenStable instead of detectChanges: let Angular schedule the check
    // itself — so the test exercises the same behaviour as production
    await fixture.whenStable();
    return fixture;
  }

  it('renders a card per ticket', async () => {
    const fixture = await setup();
    const cards = fixture.nativeElement.querySelectorAll('app-ticket-card');
    expect(cards).toHaveLength(TICKETS.length);
  });

  it('shows the empty state for an empty response', async () => {
    TestBed.configureTestingModule({
      imports: [TicketList],
      providers: [{ provide: TicketApi, useValue: { list: () => of([]) } }],
    });
    const fixture = TestBed.createComponent(TicketList);
    await fixture.whenStable();

    expect(fixture.nativeElement.textContent).toContain('No tickets match the filter');
  });
});
```

`src/app/tickets/ticket-card.harness.ts` — a harness detached from the markup:

```ts
import { ComponentHarness, HarnessPredicate } from '@angular/cdk/testing';

export class TicketCardHarness extends ComponentHarness {
  // the only place in the tests that mentions the component's selector
  static hostSelector = 'app-ticket-card';

  static with(options: { title?: string } = {}): HarnessPredicate<TicketCardHarness> {
    return new HarnessPredicate(TicketCardHarness, options).addOption(
      'title',
      options.title,
      async (harness, title) => (await harness.getTitle()) === title,
    );
  }

  // locators stay inside: a markup change is fixed here, not in the tests
  private readonly title = this.locatorFor('.ticket-card__title');
  private readonly badge = this.locatorFor('.badge');

  async getTitle(): Promise<string> {
    return (await this.title()).text();
  }

  async getStatus(): Promise<string> {
    return (await this.badge()).text();
  }

  async isSelected(): Promise<boolean> {
    return (await this.host()).hasClass('ticket-card--selected');
  }

  async click(): Promise<void> {
    return (await this.host()).click();
  }
}
```

```ts
it('selects a ticket on click', async () => {
  const fixture = await setup();
  const loader = TestbedHarnessEnvironment.loader(fixture);

  const card = await loader.getHarness(
    TicketCardHarness.with({ title: 'Invoice PDF is empty' }),
  );
  expect(await card.isSelected()).toBe(false);

  await card.click();
  await fixture.whenStable();

  // the test names no CSS class: renaming the markup will not break it
  expect(await card.isSelected()).toBe(true);
});
```

The guard test — through an injection context:

```ts
it('only lets admins into the admin section', () => {
  TestBed.configureTestingModule({
    providers: [{ provide: CurrentUser, useValue: { roles: signal(['agent']) } }],
  });

  // the guard is a function using inject(), so it must run inside a context
  const result = TestBed.runInInjectionContext(() =>
    adminMatchGuard({} as Route, [] as UrlSegment[], {} as RouterStateSnapshot),
  );

  expect(result).toBe(false);
});
```

One Playwright journey:

```ts
test('an agent creates a ticket and sees it in the list', async ({ page }) => {
  await page.goto('/tickets');

  // role- and text-based selectors: resilient to markup edits
  await page.getByRole('button', { name: 'open' }).click();
  await page.getByRole('button', { name: 'New ticket' }).click();

  await page.getByLabel('Title').fill('Printer does not respond');
  await page.getByRole('button', { name: 'Save' }).click();

  await expect(page.getByText('Printer does not respond')).toBeVisible();
});
```

Answers to the edge cases:

- The component **does not notify** Angular of the change. A manual `detectChanges()` forces synchronization and hides that, while `whenStable()` waits for a scheduled check that nobody scheduled. The cause is usually a mutation instead of `set`, or a write to a plain field from an async callback (chapter 03). Such a component would not update in production either, so the test found a real bug rather than an API inconvenience.
- Nothing special is needed, because `httpResource` subscribes itself. Add `provideHttpClientTesting()`, then an `expectOne` plus `flush()`, then `await fixture.whenStable()` so the template sees the new value. Keep in mind that the resource fires its request when the component is created, so `expectOne` comes **after** `createComponent`.
- Three causes are the common ones:

  - Polling or an `interval` in the component sent another request the test does not know about.
  - The `httpResource` refetched, because a signal it reads changed.
  - You awaited `whenStable()` after `flush()`, and the next request in the chain went out in the meantime — a `reload()` after a mutation, say.

  To diagnose, call `httpTesting.match(() => true)` before `verify()` and inspect what is left.
- Most likely the provider is not where the dependency is looked up. Three places to check:

  - The component, or a child of it, declared `providers: [TicketApi]` of its own, and that local provider shadowed the test one (chapter 04).
  - The service injects `HttpClient` directly rather than `TicketApi`, so the backend is what needed swapping (`provideHttpClientTesting`).
  - You configured `TestBed` twice, and the second call had no effect because the component already existed.
- Through `DeferBlockBehavior.Manual`: the block then does not load automatically and you drive its state explicitly after obtaining `fixture.getDeferBlocks()`. Without that mode the behaviour depends on the trigger and "the placeholder is shown" becomes a race.

## Check yourself

1. Why is `await fixture.whenStable()` preferable to `fixture.detectChanges()`, and what class of bug does the latter hide?
2. Why did `fakeAsync`/`tick` stop being a working tool, and what replaces them?
3. What is the advantage of swapping dependencies through DI over `jest.mock`? Give two concrete consequences.
4. Why can a signal store be tested without `TestBed`, and what does that buy the suite?
5. Why use a harness when you could find an element with `querySelector`?

<details>
<summary>Answers</summary>

1. `detectChanges()` is an order to check the template now, and it runs whether or not anybody notified the framework of a change. Then `whenStable()` waits for a **scheduled** synchronization, so it exercises the same chain that will happen in the application. The hidden class of bugs is state that changed with no notification sent. Typical causes: an array mutated instead of `set`, or a write to a plain field from a `setTimeout` or a third-party callback. Another is a form's `setValue` with no mirror into signals (chapters 03 and 10). With `detectChanges()` such a component passes and then breaks in production. With `whenStable()` the test fails where a real defect exists.
2. `fakeAsync`/`tick` are built on zone.js patches, and the Vitest runner does not patch zone.js. Vitest is the default runner since v21, so those helpers simply do not work, and the documentation no longer recommends `fakeAsync` at all. The replacements are direct: plain `async`/`await` for promises, and `await fixture.whenStable()` for Angular's synchronization. For timers use `vi.useFakeTimers()`/`vi.advanceTimersByTime()`, and for streams control the source directly (`Subject.next()`) instead of virtual time.
3. `jest.mock('./api')` works at the module-system level. You must name the path, which breaks when files move, and remember hoisting. The mock is typed by hand, so it drifts from the real API. A provider in `TestBed` works at the token level: `{ provide: TicketApi, useValue: fake }`. That has three consequences. The test does not depend on file locations, so it survives structural refactoring. The stub is checked by the compiler against the token, so changing the service's signature breaks the test's compilation instead of a falsely green run. And the same mechanism swaps anything else: config behind an `InjectionToken`, the `Router`, the HTTP backend.
4. Because a signal store is an ordinary class with no template. State is read by calling a signal, commands are method calls, and `computed` values recompute themselves on read. Neither the template compiler nor change detection is involved; `TestBed` is only handy for assembling dependencies, and otherwise you pass them in. The suite gains speed, because no component is created. It also gains stability: such tests do not break when markup changes, and they assert behaviour rather than DOM. That is the practical reason for moving logic out of components into services (chapter 05).
5. Because `querySelector('.ticket-card__title > span')` binds the test to the markup structure. Renaming a class or adding a wrapper then breaks tests unrelated to the change. A harness is the component's API for tests: `getTitle()`, `isSelected()`, `click()`. Selectors live in one place, inside the harness, so a markup change is fixed once. A harness also hides asynchronicity: all its methods return promises and wait for stabilization themselves. And it is reusable across unit and integration tests. Library components often ship harnesses of their own, so you never need to know their internal markup at all.

</details>

## Common mistake

The first is sprinkling `fixture.detectChanges()` after every line, copying tests from older articles. In the zone era it was a necessity. Today it is actively harmful: a forced check hides exactly the defects the test should catch. A component that forgot to move state into a signal passes with `detectChanges()` and breaks in the browser.

Worse, the habit produces suites that are green precisely because synchronization was invoked by hand in the right places. The correct shape is `await fixture.whenStable()` where an update must be awaited, and nothing between actions. If a test fails without `detectChanges()`, that is a diagnosis of the code, not of the test.

The second is assigning an input directly: `fixture.componentInstance.ticket = ticket`. With signal inputs that will not compile, because `input()` returns a read-only signal. With the remaining `@Input()` fields it passes silently and leaves the component unmarked. The template never updates, and `expect` fails on an empty DOM for no visible reason.

React experience suggests that props are just values. But in Angular an input is part of a contract backed by a notification to the framework. The correct way is `fixture.componentRef.setInput('ticket', ticket)` followed by `await fixture.whenStable()`. The same principle as with dynamic components in chapter 11.
