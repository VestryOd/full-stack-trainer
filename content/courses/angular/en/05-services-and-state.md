# Services and state

## Theory

### Why state leaves the component

A component lives exactly as long as its view stays in the tree. Navigating away and back gives you a brand-new instance. So the boundary runs like this: **the component owns screen state, the service owns data state**. The ticket list must survive a trip to the detail page and back; an expanded accordion must not.

The second motive is reuse: the same list is needed by the table, by the counter in the header and by a "my tickets" widget. The third is testability: logic inside a service can be verified without rendering anything (chapter 13).

### Anatomy of a signal store

```
A signal store in a service: what goes out, what stays in
┌─────────────────────────────────────────────────┐
│ component: reads and commands only              │
│ store.filtered()   store.setStatus("open")      │
├─────────────────────────────────────────────────┤
│ the service's public API — read-only throughout │
│ readonly tickets = this.state.asReadonly()      │
│ readonly filtered = computed(() => ...)         │
├─────────────────────────────────────────────────┤
│ commands: the only way to change state          │
│ add(ticket)  setStatus(s)  select(id)  reset()  │
├─────────────────────────────────────────────────┤
│ private state: the only thing ever written      │
│ private state = signal<readonly Ticket[]>([])   │
└─────────────────────────────────────────────────┘
a WritableSignal is never exposed: otherwise any component
  could write to the state and bypass the commands
```

The rules that turn "a service with fields" into a store:

1. **Writes are private.** What goes out are `asReadonly()` signals and `computed` values. If a component can call `set()`, the store's invariants cannot be guaranteed. The change happens outside the commands, so none of the accompanying logic runs: recomputing the selection, invalidation, logging.
2. **Changes go through commands.** A method states an intent: `assign(id, user)`, not `setTickets(newArray)`. Then the rules live in one place instead of being smeared across components.
3. **Updates are immutable.** `update((tickets) => [...])` and `readonly Ticket[]` types — so the compiler catches `push` (chapter 02).
4. **Derived values are `computed`, not a second field.** Duplicated state is where drift comes from: at that moment you have two places holding "the truth".

### Who owns which state

The most useful classification in a real project:

- **Domain data** — tickets, users. Lives in an application-level service and survives navigation.
- **Screen state** — filters, sorting, the selected row, expanded panels. Lives as long as the screen does. Technically this can be a service too, but one provided at the route or component level (chapter 04). It is then destroyed together with the screen.
- **Server cache** — whatever came from the API, along with loading flags and errors. A separate category, because the source of truth lives on the server, not with you; `httpResource` is dedicated to it (chapter 08).
- **Form state** — the draft, validity, `dirty`. Belongs to the form, not to a store (chapter 10).

Mixing them in one object is the classic "one big store" mistake. Domain and UI (user interface) state start invalidating each other, and screen filters suddenly outlive the screen.

### The ladder of solutions

Climb a step only when the current one hurts:

| level | when it is enough | what it costs |
|---|---|---|
| signals in a component | state is born and dies with the screen | nothing |
| a service with signals | several screens need the same data | encapsulation discipline |
| NgRx SignalStore | many features, shared conventions needed | a dependency with its own cycle |
| NgRx Store (actions) | tracing, time-travel and audit required | boilerplate and team ramp-up |

The honest answer to "do we need NgRx": **in most applications, no** — and that is a position you can defend in an interview. A service with signals covers what Redux was historically adopted for: a single source of truth, derived values, predictable changes. Signals add fine-grained updates without selectors and manual memoization.

What genuinely remains the domain of third-party solutions:

- **Shared conventions in a large team.** When there are dozens of stores written by fifteen people, "just a service" turns into fifteen different styles. SignalStore imposes a shape: `signalStore(withState(...), withComputed(...), withMethods(...), withHooks(...))`. Changes go through `patchState`, and collections through `withEntities` from `@ngrx/signals/entities`. The RxJS bridge is `rxMethod` from `@ngrx/signals/rxjs-interop`.
- **Tracing and tooling.** The classic NgRx Store with actions/reducers/effects gives you an action log, time-travel in DevTools and reproducibility. If the business demands an audit trail of who changed what, that is its scenario.
- **Complex async orchestration.** Chains, cancellations, dependent requests — cases where RxJS effects express more than hand-written code (chapter 09).

And the cost nobody mentions: a third-party store has its own release cycle. As this chapter is written, the stable NgRx is 21.1.1 with `peer @angular/core: ^21.0.0`. Angular 22 support lives in `22.0.0-rc.0` under the `next` tag. In other words, upgrading the framework waits on the store — a price built-in tools never charge.

### What SignalStore looks like

For comparison, the same store written with `@ngrx/signals`:

```ts
export const TicketStore = signalStore(
  { providedIn: 'root' },
  withState<{ tickets: readonly Ticket[]; status: TicketStatus | null }>({
    tickets: [],
    status: null,
  }),
  withComputed(({ tickets, status }) => ({
    filtered: computed(() =>
      status() === null ? tickets() : tickets().filter((t) => t.status === status()),
    ),
  })),
  withMethods((store) => ({
    setStatus(status: TicketStatus | null): void {
      patchState(store, { status });
    },
  })),
);
```

The difference from a hand-written service is small: the same private state, the same computed values, the same commands — just pinned down by a library. Hence the practical conclusion: start with a service and move when one of the reasons above appears; the move is mechanical.

## React parallels

The mapping, task by task:

| the task | in React | in Angular |
|---|---|---|
| state of a single screen | `useState` / `useReducer` | a signal in the component |
| hand a dependency down | Context + Provider | DI (dependency injection): a service via `inject()` |
| application-wide state | Zustand / Redux | a service with signals |
| a derived value | `useMemo` / a selector | `computed` |
| server data and caching | TanStack Query | `httpResource` (chapter 08) |
| strict team conventions | Redux Toolkit | NgRx SignalStore / Store |

- **The closest analogue of a signal service is Zustand, not Redux.** There too the store lives outside the component tree, is read through a selector and mutated through methods. The difference is the subscription. In Zustand it is defined by the selector, as in `useStore(s => s.tickets)`. In Angular it arises from the very act of reading a signal, so forgetting to narrow it is impossible.
- **Context is DI, not state.** React developers often keep state *in* a context: a `<StateProvider>` whose value comes from `useState`. In Angular the two are separate: DI delivers the service, signals provide reactivity. So there is no provider wrapper, no memoizing of the value, and no splitting contexts for performance.
- **Immutability without immer.** Redux Toolkit hides immutability behind immer so you can write "mutating" code. Angular's protection is different: `readonly` types forbid mutation, and `Object.is` inside the signal will not let a mutation "accidentally" update anything. There is no immer-like helper — but also no proxy magic.
- **The server cache is a separate category in both worlds.** In React that is TanStack Query, not Redux; in Angular it is `httpResource`, not a store. Keeping API responses in a general-purpose store with hand-written `loading`/`error` flags is equally outdated in both (chapter 08).
- **Where the habit breaks:** in React a global store is a visible architectural decision (add a Provider, wire up devtools). In Angular a service is reachable everywhere **by default**, so state becomes global by accident. You write `@Service()`, put the screen's filters in it, and they outlive the screen. The opposite mistake is just as common: putting domain data in a component provider and getting one copy per component (chapter 04).

## What you will see in legacy code

- **A `BehaviorSubject` store:** `private state$ = new BehaviorSubject(initial); readonly vm$ = this.state$.asObservable();` plus `state$ | async` in the template. Exactly the same "private write, public read" pattern, only on RxJS; porting it to signals is mechanical (chapter 09).
- **Classic NgRx:** `createAction`/`createReducer`/`createEffect`/`createSelector`, `StoreModule.forRoot(reducers)` and `forFeature`, `EntityAdapter` from `@ngrx/entity`, `this.store.select(selectTickets)` and `this.store.dispatch(loadTickets())`.
- **Facade services on top of NgRx** — a layer hiding `dispatch`/`select` behind methods; usually introduced precisely so components would not know about the store. With a signal service the facade *is* the store.
- **`@ngrx/component-store`** — the previous generation of a local store (per component/route), with `setState`/`patchState`/`select`/`effect` on RxJS. Today's equivalent is a signal service provided at the component level.
- **Manual subscriptions in components:** `ngOnInit` with `subscribe`, a `private destroy$ = new Subject()` field and `takeUntil(this.destroy$)` on every stream. Easy to get wrong. That is why the `async` pipe came first, then `takeUntilDestroyed` (chapter 09), and now signals, where there are no subscriptions at all.

## What we add to the project

All ticket state moves into `TicketStore`: data, commands and derived values. Filters and selection are extracted into a screen store provided at the component level — so the difference in lifetime becomes visible. After this the components hold nothing.

## Exercise

**Input:** the project from chapter 04 (`TicketService`, config and rules through DI).
**Output:** two stores with clear boundaries and components with no state of their own.

Requirements:

1. `TicketStore` (application level): a private signal holding the list, plus public `readonly` signals and `computed` values (total count, unassigned count). Commands: `add`, `update(id, patch)`, `remove(id)`, `reset()`. No `WritableSignal` goes out — verify that a component physically cannot call `set()`.
2. `TicketBoardState` (screen level): the status filter, the search string, the selected `id`; a derived `filtered` that reads the list from `TicketStore`. Provide it at the list component level and explain what changes when the user leaves the screen and comes back.
3. `TicketList` and `TicketFilters` hold no state at all: they only read signals and call commands. `TicketFilters` either receives values via `input()` and reports changes via `output()`, or reads the screen store directly; pick one and justify it.
4. The `update(id, patch)` command must update the ticket immutably, preserve list order, and leave the selection alone if the ticket is still there. Decide what should happen when the `id` is not found.
5. Add a `computed` that depends on both stores — for example, the selected ticket in full. Explain why this creates no cycle and needs no synchronization.
6. Constraint: not a single `effect`. If you feel the urge, you are probably duplicating state.

Edge cases to think about:

- `asReadonly()` protects against `set()`. What does it **not** protect when the state is an array of objects?
- Two instances of the list component on one screen, say two tabs, with a component-level screen store. How many filter sets exist, and is that right?
- The screen store reads `TicketStore`. What happens when the component is destroyed — does a subscription to the signal leak?
- When does a `computed` degenerate into a pointless wrapper you should remove?
- How would you test the `update` command without creating a single component?

## Solution walkthrough

`src/app/tickets/ticket-store.ts` — the domain data:

```ts
import { Service, computed, signal } from '@angular/core';
import { Ticket } from './ticket';

@Service()
export class TicketStore {
  // The only writable place in the entire store.
  // readonly Ticket[] so the compiler forbids in-place push/sort
  private readonly state = signal<readonly Ticket[]>(SAMPLE_TICKETS);

  // Read-only on the way out. The type is Signal<T>, not WritableSignal<T>,
  // so a component cannot call set() even by accident
  readonly tickets = this.state.asReadonly();

  readonly totalCount = computed(() => this.state().length);
  readonly unassignedCount = computed(
    () => this.state().filter((t) => t.assignee === null).length,
  );

  add(ticket: Ticket): void {
    this.state.update((tickets) => [ticket, ...tickets]);
  }

  // A command states an intent and keeps the invariant in one place:
  // order is preserved and the other tickets stay the same objects
  update(id: number, patch: Partial<Omit<Ticket, 'id'>>): void {
    this.state.update((tickets) =>
      tickets.map((ticket) => (ticket.id === id ? { ...ticket, ...patch } : ticket)),
    );
  }

  // A missing id is not an error: map simply changes nobody.
  // Throwing here would force every caller to check existence up front,
  // which is unnecessary coupling in the UI
  remove(id: number): void {
    this.state.update((tickets) => tickets.filter((ticket) => ticket.id !== id));
  }

  reset(): void {
    this.state.set(SAMPLE_TICKETS);
  }
}
```

`src/app/tickets/ticket-board-state.ts` — the screen state:

```ts
import { Service, computed, inject, linkedSignal, signal } from '@angular/core';
import { TicketStatus } from './ticket';
import { TicketStore } from './ticket-store';

// autoProvided: false — this store must NOT be global: it describes the
// state of one screen and has to die together with it
@Service({ autoProvided: false })
export class TicketBoardState {
  private readonly tickets = inject(TicketStore);

  private readonly statusFilter = signal<TicketStatus | null>(null);
  private readonly searchQuery = signal('');

  readonly status = this.statusFilter.asReadonly();
  readonly search = this.searchQuery.asReadonly();

  // a computed across the store boundary: it reads both domain data and
  // filters. There is no cycle because the dependency is one-way:
  // the screen knows about the data, the data knows nothing about the screen
  readonly filtered = computed(() => {
    const status = this.statusFilter();
    const query = this.searchQuery().trim().toLowerCase();

    return this.tickets.tickets().filter((ticket) => {
      const statusMatches = status === null || ticket.status === status;
      const titleMatches = query === '' || ticket.title.toLowerCase().includes(query);
      return statusMatches && titleMatches;
    });
  });

  readonly visibleCount = computed(() => this.filtered().length);

  // the selection resets when the ticket falls out of the view (chapter 02)
  private readonly selection = linkedSignal<readonly Ticket[], number | null>({
    source: this.filtered,
    computation: (tickets, previous) => {
      const id = previous?.value ?? null;
      return tickets.some((t) => t.id === id) ? id : null;
    },
  });

  readonly selectedId = this.selection.asReadonly();
  readonly selectedTicket = computed(
    () => this.filtered().find((t) => t.id === this.selection()) ?? null,
  );

  setStatus(status: TicketStatus | null): void {
    this.statusFilter.set(status);
  }

  setSearch(query: string): void {
    this.searchQuery.set(query);
  }

  toggleSelection(id: number): void {
    this.selection.update((current) => (current === id ? null : id));
  }
}
```

`src/app/tickets/ticket-list.ts` — a component with no state:

```ts
@Component({
  selector: 'app-ticket-list',
  imports: [TicketCard, TicketFilters],
  // The screen store is provided here: it is created with the component and
  // destroyed with it. Coming back to the screen gives the user clean
  // filters — a deliberate decision rather than a side effect
  providers: [TicketBoardState],
  templateUrl: './ticket-list.html',
  styleUrl: './ticket-list.css',
})
export class TicketList {
  // both stores are injected; the component holds nothing of its own
  protected readonly board = inject(TicketBoardState);
  protected readonly tickets = inject(TicketStore);
}
```

`src/app/tickets/ticket-list.html`:

```html
<section class="ticket-list">
  <header class="ticket-list__header">
    <h2>Tickets</h2>

    <!-- The filters read and write the screen store through input/output, so
         the filter component stays reusable and does not know where the data
         comes from. The alternative is injecting TicketBoardState into it:
         shorter, but ties the component to this particular screen -->
    <app-ticket-filters
      [status]="board.status()"
      [search]="board.search()"
      (statusChange)="board.setStatus($event)"
      (searchChange)="board.setSearch($event)"
    />

    <p class="ticket-list__summary">
      {{ board.visibleCount() }} of {{ tickets.totalCount() }} ·
      {{ tickets.unassignedCount() }} unassigned
    </p>
  </header>

  <ul class="ticket-list__items">
    @for (ticket of board.filtered(); track ticket.id) {
      <li>
        <app-ticket-card
          [ticket]="ticket"
          [selected]="ticket.id === board.selectedId()"
          (selectTicket)="board.toggleSelection($event.id)"
        />
      </li>
    } @empty {
      <li class="ticket-list__empty">No tickets match the filter</li>
    }
  </ul>
</section>
```

Note how the roles are split. `TicketStore` knows nothing about filters or about being read from some screen, and `TicketBoardState` knows about the data but does not own it. The dependency is one-way, so nothing needs "synchronizing" — `filtered` recomputes by itself both when a filter changes and when a ticket is added.

Answers to the edge cases:

- `asReadonly()` forbids `set`/`update` on **the signal itself**, but it does not make the data inside immutable. Even `store.tickets()[0].title = 'x'` is technically possible unless the object is protected by its type. The protection lives in the types: `readonly` fields in the `Ticket` interface and `readonly Ticket[]` for the array. The compiler then catches both field mutation and `push`.
- Two component instances mean two `TicketBoardState` instances, i.e. two independent filter sets. For two tabs that is exactly right: each filters its own way. If the filters had to be shared, the store would need to move up to the route or application level. That is a change of provider configuration, not a rewrite.
- Nothing leaks. A `computed`'s dependency on a signal is a graph edge, not a manually managed subscription. When `TicketBoardState` is destroyed with its component, its `computed` values become unreachable and are garbage collected. That is exactly why signal code has no `takeUntilDestroyed` and no `destroy$`.
- A `computed` that merely returns another signal, as in `readonly x = computed(() => this.y())`, is a useless layer. It derives nothing and adds a node to the graph. If all you want is to expose a read, hand out `this.y.asReadonly()`. A `computed` earns its place where there is an actual computation: filtering, an aggregate, a combination of several sources.
- The command test looks like an ordinary unit test: get the instance from `TestBed.inject(TicketStore)`, call `update(...)`, read `tickets()` and compare. No component, no template, no `detectChanges` — which is the main practical argument for moving logic into a service (chapter 13).

## Check yourself

1. Explain in your own words why a store exposes `Signal<T>` rather than `WritableSignal<T>`, and what exactly breaks if you expose a writable one.
2. What tells you whether state belongs in an application-level service or in a screen-level store? Give two examples of each.
3. Why is a signal service closer to Zustand than to Redux, and how do the two differ in how a subscription is established?
4. Name three situations where NgRx (in any form) is genuinely justified, and one cost you pay regardless of project size.
5. Why does a signal store need no `takeUntilDestroyed`, no `destroy$` and no unsubscribing, even though one service reads another's data?

<details>
<summary>Answers</summary>

1. A public `Signal<T>` allows reads but not `set`/`update` — only the store itself writes. Expose a `WritableSignal<T>` and any component can change the state directly, bypassing the commands. Three things break.

   - **Invariants.** The accompanying logic — recomputing the selection, validation, logging — never runs.
   - **Locality of rules.** Changes spread across components, and "why did the list end up like this" has to be searched project-wide.
   - **Testability.** Having verified the store's commands, you can no longer be sure the state changes only through them.
2. The criterion is lifetime and the number of owners. If the data must survive leaving the screen and is needed in several places, it is an application-level service: the ticket list, the current user. If the state only makes sense on this screen and should disappear with it, it is a screen store. Examples: table filters and sorting, the selected row, an expanded detail panel. A practical test: "if the user leaves and comes back, do they expect to see this unchanged?" — yes means application level.
3. Redux is about the "action → reducer → new state" flow with an action log; a signal service has no such layer. Zustand, on the other hand, is a store outside the component tree. It is read directly and mutated through methods — structurally the same as a service. The difference is the subscription. In Zustand a component subscribes with a selector, and too broad a selector means extra re-renders. In Angular the subscription arises from reading a signal inside a template or `computed`. It cannot be too broad: you depend on exactly what you read.
4. Justified in three cases:

   - **A large team with many features**, where the value lies in shared conventions and a predictable code shape.
   - **Traceability is required** — an action log, time-travel, replaying a scenario from logs, audit.
   - **Complex async orchestration** — chains, cancellations, dependent requests, where RxJS effects express more than hand-written code.

   The cost independent of project size is an external dependency with its own release cycle. Upgrading Angular becomes possible only after the store ships a compatible version. As of writing, the stable NgRx requires `@angular/core ^21`, and v22 support exists only in an rc under the `next` tag.

5. Because the link between signals is an edge in the dependency graph, not a subscription to a stream. A `computed` in the screen store reads a signal from the domain store. The domain store does **not** keep a reference to the consumer in a way that would hold it in memory after destruction. When the component is destroyed, its store and all of its `computed` values become unreachable and are garbage collected. There is nothing to unsubscribe from: nothing resembling `subscribe` ever happened. That is why an entire class of leaks familiar from RxJS code simply does not exist in signal code.

</details>

## Common mistake

The first mistake is "one big store for everything". The logic is familiar from Redux. State should live in one place, so let us put the tickets, the filters, the open modals and the form draft in there. In Angular this is especially easy, because a service is reachable everywhere without wrappers.

The consequences do not show up right away. Screen filters outlive the screen, and the user comes back to yesterday's settings. Form state lingers in memory after the form closes. And any change in the UI part forces recomputation of things that depend on the domain part.

The cure is to split by lifetime. Domain data goes into an application-level `@Service()`. Screen state goes into a separate store declared in a component's or route's `providers`, so destruction happens automatically.

The second mistake is a copy of the state inside a component. It looks innocent. The component takes `tickets()` from the store and puts it into its own signal, to sort it locally or to avoid hitting the store.

From that moment there are two truths, and they diverge at the first change. A ticket added through a command updates the store but not the local copy. React has this bug too (`useState(props.items)`), but there it surfaces faster, because props change on every re-render.

The rule is simple. Anything derivable is derived with `computed`. Local storage is introduced only for what the store does not hold at all — an unsaved draft, for example.
