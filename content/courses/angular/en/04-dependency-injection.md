# Dependency injection

## Theory

### Injector, token, provider

DI in Angular is not a pattern from a book but a working container inside the framework. Three concepts:

- **Token** — the key a dependency is requested by. Usually a class (`TicketService`), but it can be an `InjectionToken<T>` for anything that is not a class.
- **Provider** — the recipe for producing a value for a token.
- **Injector** — the container that holds providers, creates values on first request and caches them.

It is worth exactly as much as it costs: DI gives you **substitutability** (a mock replaces the HTTP service in tests — no module mocking), **lifetime** (one instance per application, per route or per component — decided by configuration, not by the service's code) and **configurability** (environment values are handed out through tokens rather than imported directly).

### Declaring a service

The modern way is the `@Service()` decorator (stable since v22, marked `@publicApi`):

```ts
@Service()
export class TicketService { /* … */ }
```

It is an ergonomic shorthand for `@Injectable({ providedIn: 'root' })`: the class becomes an application-wide singleton and stays tree-shakable — if nobody injects it, the bundler drops it. The decorator takes two useful options:

```ts
@Service({ autoProvided: false })         // don't register it automatically:
export class DraftStore {}                // provide it by hand where needed

@Service({ factory: () => inject(FLAG)()  // the value comes from a factory:
  ? new RealAnalytics() : new NoopAnalytics() })
export class Analytics {}
```

`@Injectable` has not gone anywhere and is required wherever **constructor injection** is used: `@Service` only works with `inject()`. `@Injectable` also supports `providedIn: 'platform'` (one instance across all applications on the page) and `'any'` (a separate instance in every lazy environment injector) — both rarely needed and always deliberately.

The key point about tree-shaking: `@Service`/`providedIn` describes the relationship **from the service's side**, so an unused service is removed from the bundle. Listing it in a `providers` array points the other way (the application references the service), and such a service always stays in the bundle.

### inject() and the injection context

```ts
export class TicketList {
  private readonly tickets = inject(TicketService);
  private readonly config = inject(APP_CONFIG);
}
```

`inject()` only works **inside an injection context**: class field initializers, the constructor, a provider or `InjectionToken` factory, and inside `runInInjectionContext(injector, fn)`. Calling it from an event handler, a timer callback or a `.then()` produces `NG0203`. When a dependency is genuinely needed later, keep the `Injector` around:

```ts
private readonly injector = inject(Injector);

async load(): Promise<void> {
  const { Heavy } = await import('./heavy');
  runInInjectionContext(this.injector, () => new Heavy());
}
```

For that same scenario v22 added `injectAsync()` — lazy injection with code splitting.

### The injector hierarchy

```
  inject(TOKEN) inside TicketCard: the lookup order
┌───────────────────────────────────────────────────┐
│ ElementInjector: TicketCard itself                │
│ providers / viewProviders in its @Component       │
└───────────────────────────────────────────────────┘
                          │  not found
                          ▼
┌───────────────────────────────────────────────────┐
│ ElementInjector: ancestor elements                │
│ TicketList, App — their providers                 │
└───────────────────────────────────────────────────┘
                          │  not found
                          ▼
┌───────────────────────────────────────────────────┐
│ EnvironmentInjector: the route                    │
│ providers on a Route (chapter 07)                 │
└───────────────────────────────────────────────────┘
                          │  not found
                          ▼
┌───────────────────────────────────────────────────┐
│ EnvironmentInjector: root                         │
│ @Service(), providedIn: root, appConfig.providers │
└───────────────────────────────────────────────────┘
                          │  not found
                          ▼
┌───────────────────────────────────────────────────┐
│ EnvironmentInjector: platform                     │
│ providedIn: platform                              │
└───────────────────────────────────────────────────┘
                          │  not found
                          ▼
┌───────────────────────────────────────────────────┐
│ NullInjector                                      │
│ NG0201: No provider for TOKEN                     │
└───────────────────────────────────────────────────┘
the first match wins: a component provider shadows root
and creates ITS OWN instance per instance of that component
```

There are in fact two hierarchies, searched in exactly this order: first the **ElementInjector** chain — up the DOM elements from the requesting component — then the **EnvironmentInjector** chain: route, root, platform, `NullInjector`.

A component has two arrays:

- `providers` — the service is visible in the component's template **and** in content projected into it via `<ng-content>`;
- `viewProviders` — visible in its own template only; projected content will not see that provider (chapter 11).

Lookup modifiers are options of `inject()`:

```
┌───────────────────────────────┬───────────────────────────────────┬───────────────────────────────────┐
│ call                          │ how it changes the lookup         │ when you need it                  │
├───────────────────────────────┼───────────────────────────────────┼───────────────────────────────────┤
│ inject(T)                     │ the normal bottom-up lookup       │ the default                       │
├───────────────────────────────┼───────────────────────────────────┼───────────────────────────────────┤
│ inject(T, { optional: true }) │ returns null instead of NG0201    │ an optional dependency            │
├───────────────────────────────┼───────────────────────────────────┼───────────────────────────────────┤
│ inject(T, { self: true })     │ this ElementInjector only         │ demanding a local provider        │
├───────────────────────────────┼───────────────────────────────────┼───────────────────────────────────┤
│ inject(T, { skipSelf: true }) │ start at the parent               │ decorating the parent instance    │
├───────────────────────────────┼───────────────────────────────────┼───────────────────────────────────┤
│ inject(T, { host: true })     │ no higher than the host component │ a directive inside a foreign host │
└───────────────────────────────┴───────────────────────────────────┴───────────────────────────────────┘
```

### Provider recipes and InjectionToken

```
┌────────────────────┬──────────────────────────────────────┬─────────────────────────────────┐
│ recipe             │ what it supplies                     │ typical use                     │
├────────────────────┼──────────────────────────────────────┼─────────────────────────────────┤
│ useClass: Impl     │ a new instance of Impl               │ swapping an implementation      │
├────────────────────┼──────────────────────────────────────┼─────────────────────────────────┤
│ useValue: obj      │ a ready value as-is                  │ config, constants, a mock       │
├────────────────────┼──────────────────────────────────────┼─────────────────────────────────┤
│ useFactory: fn     │ the result of calling fn             │ choosing an impl at runtime     │
├────────────────────┼──────────────────────────────────────┼─────────────────────────────────┤
│ useExisting: Other │ the very instance of Other           │ a narrow interface to a service │
├────────────────────┼──────────────────────────────────────┼─────────────────────────────────┤
│ multi: true        │ an array of all values for the token │ rule sets, interceptors         │
└────────────────────┴──────────────────────────────────────┴─────────────────────────────────┘
```

An interface, a configuration object, a URL string — none of them are classes, so none can serve as a token: nothing of an interface survives into runtime. `InjectionToken` exists for those:

```ts
export interface AppConfig {
  readonly apiUrl: string;
  readonly pageSize: number;
}

// a factory makes the token tree-shakable and supplies a default value
export const APP_CONFIG = new InjectionToken<AppConfig>('APP_CONFIG', {
  providedIn: 'root',
  factory: () => ({ apiUrl: '/api', pageSize: 20 }),
});
```

`multi: true` turns a token into a collection: each provider contributes one element and `inject()` returns an array. That is how extensible lists are built — validation rules, handlers, and in older code the interceptors.

### NullInjectorError as a diagnostic skill

`NG0201: No provider for X` means literally: the lookup reached the `NullInjector`, no injector in the chain knew this token. A practical checklist of causes:

1. The service has no `@Service()`/`providedIn` and is not listed in any `providers`.
2. A `provide*` call is missing from `appConfig.providers` — the most common cause for `HttpClient` (`provideHttpClient()`) and the router.
3. The provider is declared on a component while the dependency is requested from outside or higher up the tree.
4. The token is duplicated: two `InjectionToken`s with the same description are two different tokens — the description does not affect identity.
5. A circular import: the module holding the token is not initialized yet, and the provider receives `undefined` (symptom: "No provider for undefined").

Its neighbour is `NG0203: inject() must be called from an injection context` — not about a missing provider, but about where the call happened.

## React parallels

- **DI versus context.** `useContext` follows the render tree and requires a `<Provider>` wrapper around a subtree; the Angular injector follows the component tree, but a dependency can be obtained from **any** class — a service, a guard, an interceptor — not just from a component. No wrappers are needed: `@Service()` already makes the service reachable everywhere.
- **Passing dependencies down.** In React, an object needed three levels down is either drilled through props or put in a context. In Angular, `inject()` solves both, and depth is not a factor: all that matters is which injector holds the provider.
- **Substitution in tests — the main difference.** In React a dependency is usually imported directly, so replacing it requires `jest.mock` or a manual provider wrapper. In Angular substitution is a first-class operation: `TestBed.configureTestingModule({ providers: [{ provide: TicketApi, useValue: fake }] })`, with no bundler involvement (chapter 13). This is what makes DI worth its weight rather than "an extra layer".
- **Singletons.** A module singleton in React (`export const store = createStore()`) is just a module value: hard to substitute in a test, and on the server it is shared by all requests. `providedIn: 'root'` gives a singleton **per injector**, so under SSR each request gets its own.
- **Where the habit breaks:** in React you add a provider deliberately, around a specific subtree. In Angular a component provider looks like the harmless line `providers: [TicketService]` — while in fact it creates one instance per component instance, and "shared" state quietly splits into N independent copies. It is the most common architectural mistake newcomers make.

## What you will see in legacy code

- **`@Injectable()` without `providedIn`** plus registration in an NgModule's `providers`; for configurable libraries, the `SomeModule.forRoot(config)` / `forChild()` pattern, now replaced by `provideSomething(config)` functions.
- **Constructor injection:** `constructor(private http: HttpClient, @Inject(APP_CONFIG) private config: AppConfig) {}` with the decorator modifiers `@Optional()`, `@Self()`, `@SkipSelf()`, `@Host()` instead of `inject()` options.
- **`HTTP_INTERCEPTORS` with `multi: true` and interceptor classes** — the previous generation of what functional interceptors do today (chapter 08). A good example of `multi` in the wild.
- **`APP_INITIALIZER`** (a multi token for async startup work) — in new code that is `provideAppInitializer(...)`.
- **`InjectionToken` without a factory** — `new InjectionToken<AppConfig>('app.config')` plus a mandatory `useValue` somewhere in a module; forget it and you get `NG0201`.
- **`ReflectiveInjector`, `Injector.create(...)`, hand-built `EnvironmentInjector`s** in library code and in dynamic component creation (chapter 11).

## What we add to the project

Ticket state moves out of the component and into `TicketService` (the groundwork for chapter 05), application configuration is handed out through `APP_CONFIG` and a `provideAppConfig()` function, and ticket warnings are collected through a multi token — a set that can be extended without touching the service.

## Exercise

**Input:** the project from chapter 03 (signals, a counter fed by an external source).
**Output:** state in a service, config and rules delivered through DI, and `NG0201`/`NG0203` diagnosed on purpose.

Requirements:

1. Create `TicketService` with `@Service()`: a private signal holding the list, public `readonly` signals, and `add()`/`reset()` methods. `TicketList` no longer holds the array, it only reads the service. Filters stay in the component for now (they belong to the screen, not to the data) — argue why that is a sensible boundary.
2. Introduce `APP_CONFIG: InjectionToken<AppConfig>` with a default factory (`apiUrl`, `pageSize`, `slaWarningHours`) and a `provideAppConfig(overrides)` function returning providers. Wire it into `app.config.ts` and read the config inside the service.
3. Build a multi token `TICKET_RULES`, where a rule is a function `(ticket: Ticket) => string | null`. Register at least two rules (SLA at risk; `urgent` with no assignee) and collect them in the service via `inject(TICKET_RULES)`. The component shows the warnings on the card.
4. Component provider: write a small `DraftStore` (a note draft for a ticket) and declare it in the card component's `providers`. Verify that two cards have independent drafts. Explain in a comment why `TicketService` must not be declared this way.
5. Diagnostics: deliberately produce `NG0201` (drop the token's factory and provide nothing) and `NG0203` (call `inject()` inside a click handler). Read the messages and fix them — the second one in two ways: by moving the call, and via a stored `Injector`.
6. Constraint: no `@Injectable` unless genuinely required, and no constructor injection — `inject()` only.

Edge cases to think about:

- Why does `@Service()` not work with constructor injection, and when will that push you back to `@Injectable`?
- How do a component's `providers` differ from `viewProviders` when the component has an `<ng-content>`?
- What does `inject(APP_CONFIG, { optional: true })` return when no provider exists — and why is that better than try/catch?
- How many instances of a service exist with `providedIn: 'root'` versus `providedIn: 'any'` in an application with lazy routes?
- Why does `useFactory` need `deps` if the factory can simply call `inject()` inside?

## Solution walkthrough

`src/app/core/app-config.ts` — configuration as a dependency:

```ts
import { InjectionToken, Provider } from '@angular/core';

export interface AppConfig {
  readonly apiUrl: string;
  readonly pageSize: number;
  readonly slaWarningHours: number;
}

// The factory buys two things at once: a default value (the app boots with
// no explicit setup) and tree-shaking of the token itself
export const APP_CONFIG = new InjectionToken<AppConfig>('APP_CONFIG', {
  providedIn: 'root',
  factory: () => ({ apiUrl: '/api', pageSize: 20, slaWarningHours: 4 }),
});

// provideXxx() instead of SomeModule.forRoot(config): a plain function
// returning providers. Every provide* in Angular itself is built this way
export function provideAppConfig(overrides: Partial<AppConfig> = {}): Provider[] {
  return [
    {
      provide: APP_CONFIG,
      useFactory: (): AppConfig => ({
        apiUrl: '/api',
        pageSize: 20,
        slaWarningHours: 4,
        ...overrides,
      }),
    },
  ];
}
```

`src/app/tickets/ticket-rules.ts` — the multi token:

```ts
import { InjectionToken, Provider, inject } from '@angular/core';
import { APP_CONFIG } from '../core/app-config';
import { Ticket } from './ticket';

// A rule: a pure function returning a warning or null
export type TicketRule = (ticket: Ticket) => string | null;

export const TICKET_RULES = new InjectionToken<readonly TicketRule[]>('TICKET_RULES');

export function provideTicketRules(): Provider[] {
  return [
    {
      provide: TICKET_RULES,
      multi: true, // each provider contributes ONE ELEMENT to the array
      // the factory itself runs in an injection context — inject() is fine here
      useFactory: (): TicketRule => {
        const { slaWarningHours } = inject(APP_CONFIG);
        return (ticket) => {
          if (ticket.slaHours === undefined) return null;
          return ticket.slaHours <= slaWarningHours ? 'SLA at risk' : null;
        };
      },
    },
    {
      provide: TICKET_RULES,
      multi: true,
      useValue: ((ticket) =>
        ticket.priority === 'urgent' && ticket.assignee === null
          ? 'Urgent and unassigned'
          : null) satisfies TicketRule,
    },
  ];
}
```

`src/app/tickets/ticket-service.ts`:

```ts
import { Service, computed, inject, signal } from '@angular/core';
import { APP_CONFIG } from '../core/app-config';
import { Ticket } from './ticket';
import { TICKET_RULES } from './ticket-rules';

// @Service() = @Injectable({ providedIn: 'root' }), but shorter and without
// the temptation of constructor injection: it does not support it
@Service()
export class TicketService {
  private readonly config = inject(APP_CONFIG);
  // a multi token arrives as an array; the order is the registration order
  private readonly rules = inject(TICKET_RULES);

  // writes stay private, only reads are exposed (chapter 05 goes deeper)
  private readonly state = signal<readonly Ticket[]>(SAMPLE_TICKETS);
  readonly tickets = this.state.asReadonly();
  readonly pageSize = computed(() => this.config.pageSize);

  warningsFor(ticket: Ticket): readonly string[] {
    // the service does not know how many rules there are or where they came
    // from: a new rule is added by a provider, without touching this file
    return this.rules.map((rule) => rule(ticket)).filter((w) => w !== null);
  }

  add(ticket: Ticket): void {
    this.state.update((tickets) => [ticket, ...tickets]);
  }

  reset(): void {
    this.state.set(SAMPLE_TICKETS);
  }
}
```

`src/app/app.config.ts`:

```ts
export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    // environment config arrives here instead of being imported from
    // environment.ts: this way it can be swapped in tests and per stand
    ...provideAppConfig({ apiUrl: '/api/v1', slaWarningHours: 6 }),
    ...provideTicketRules(),
  ],
};
```

A component provider is the case where "one instance per component" is the goal:

```ts
@Service({ autoProvided: false }) // don't register it in root: pointless here
export class DraftStore {
  private readonly text = signal('');
  readonly draft = this.text.asReadonly();
  write(value: string): void { this.text.set(value); }
}

@Component({
  selector: 'app-ticket-card',
  // A component provider: EVERY card gets its own DraftStore,
  // which is exactly what a draft needs.
  // TicketService must never be declared this way: the ticket list is one
  // per application, and here we would get one copy of state per card
  providers: [DraftStore],
  // ...
})
export class TicketCard {
  protected readonly draft = inject(DraftStore);
  private readonly tickets = inject(TicketService); // the shared root instance
}
```

The `NG0203` walkthrough from step 5 — a call in the wrong place and two fixes:

```ts
export class TicketList {
  private readonly injector = inject(Injector); // capture the context up front

  // WRONG: an event handler is not an injection context
  onClickBad(): void {
    const service = inject(TicketService); // NG0203
  }

  // Fix 1: inject where you are supposed to — in a class field
  private readonly service = inject(TicketService);
  onClickGood(): void {
    this.service.reset();
  }

  // Fix 2: when the dependency appears later (a lazy import),
  // run the code inside the captured context
  async onLoadHeavy(): Promise<void> {
    const { HeavyExporter } = await import('./heavy-exporter');
    const exporter = runInInjectionContext(this.injector, () => new HeavyExporter());
    exporter.run();
  }
}
```

Answers to the edge cases:

- `@Service()` does not record metadata about constructor parameter types, so constructor injection is impossible with it — `inject()` only. You will go back to `@Injectable` in three cases: you need `providedIn: 'platform'`/`'any'`, the class is extended by existing code that uses constructor injection, or you are writing a library consumed by projects on the older style.
- `providers` are visible both in the component's template and in content projected through `<ng-content>`; `viewProviders` only in its own template. The difference shows when content comes from the parent: that content "belongs" to the parent, and if you do not want foreign content latching onto your internal service, declare it in `viewProviders`.
- It returns `null` instead of throwing. That beats try/catch because optionality becomes part of the dependency's signature rather than error-handling behaviour: the type is `AppConfig | null`, and the compiler forces you to handle the absence. A try/catch around `inject()` would also swallow genuine factory errors.
- With `providedIn: 'root'` there is one instance per application, no matter how many lazy routes ask for it. With `'any'` there is one per environment injector: one in root plus one in each lazy one. That is exactly why `'any'` is almost never what you want: "shared" state falls apart along lazy boundaries.
- `deps` is needed when the factory is a plain function called outside an injection context, receiving its dependencies positionally. If the factory calls `inject()` inside itself, `deps` is unnecessary: Angular runs provider factories inside an injection context. The modern style is the latter — it is type-safe, whereas `deps` is an array whose order the compiler never checks.

## Check yourself

1. Explain in your own words why `@Service()`/`providedIn: 'root'` enables tree-shaking while listing the service in `providers` does not.
2. A component declares `providers: [TicketService]`. How many instances of the service will exist, and what happens to the state it holds?
3. In what order does Angular look for a provider for `inject(TOKEN)` called in a child component, and at which point do you get `NG0201`?
4. Why does `InjectionToken` exist if a class can be a token? Why can't you use an interface?
5. What is `NG0203` about, and what are the two ways to fix it?

<details>
<summary>Answers</summary>

1. The direction of the reference. With `@Service()`/`providedIn`, the service itself declares which injector it lives in: the application does not reference it, the reference only appears where it is injected. If no such place exists, the bundler sees an unreachable class and removes it. A `providers` array is the reverse reference: the application (or module) configuration statically mentions the class, so it is reachable from the entry point and ships in the bundle even if no component ever asks for it.
2. One instance per instance of that component: the provider lives in the ElementInjector created for the element. Whatever state the service holds stops being shared — each copy of the component gets its own. If it is a form draft or a local store, that is the desired behaviour; if it is the ticket list or authentication, you get N unsynchronized copies with no error at all — just "the data doesn't match between screens".
3. First the component's own ElementInjector (its `providers`/`viewProviders`), then the ElementInjectors of ancestor elements up the tree, then the EnvironmentInjectors: the route one (if the component was opened through a route with `providers`), root, platform. The first match wins. If none of them knows the token, the search reaches the `NullInjector`, which always throws — that is `NG0201: No provider for TOKEN`.
4. A token must exist at runtime and be a unique object. A class qualifies: it exists at runtime and is unique. An interface is a type-system construct only: nothing of it survives compilation, so it cannot be referenced at runtime. `InjectionToken` is a runtime object created specifically to be a key, with a type parameter for typing the injected value. A string is a poor token too: two identical strings from different places would collide by accident, while the description in `new InjectionToken('...')` does not affect identity — two tokens with the same text remain different tokens.
5. `NG0203` means `inject()` was called outside an injection context: the context exists during class field initialization, in the constructor, and in provider/token factories, but not in event handlers, timer callbacks, `.then()` or arbitrary methods. Two fixes: move the call where a context exists (usually into a class field, which is the normal style anyway), or capture an `Injector` via `inject(Injector)` up front and run the code inside `runInInjectionContext(injector, fn)`; for lazy imports, v22 offers `injectAsync()`.

</details>

## Common mistake

Classic number one: a component-level provider where root was needed. It goes like this — a developer writes a state service, sees the line `providers: [TicketService]` in a component decorator in some article, copies it, and ends up with one instance of the service per component instance. The mistake produces neither an exception nor a warning: the application runs, it is just that a ticket added on one screen is invisible on another, and the header counter does not move after an action in the table. It is quick to diagnose if you remember the rule: **`providers` on a component is a statement that "I want my own instance"**. Shared state belongs in `@Service()` (that is, root); local state (a draft, a store for one specific form, accordion state) belongs in a component provider — and then it is a deliberate decision rather than copy-paste.

The second mistake is calling `inject()` in the wrong place. React experience says "a hook can be called anywhere inside a component", so the hand types `inject(TicketService)` inside a click handler or in a `.then()` after an `await`. The result is `NG0203: inject() must be called from an injection context`. The `await` case is particularly nasty: code before the `await` is still in the context and code after it is not, so the error appears intermittently and reads like a race condition. The cure is simple and also happens to be the right style: declare all dependencies as class fields at instance creation time, and when a dependency really is needed later (a lazily loaded module), capture the `Injector` in advance and use `runInInjectionContext`.
