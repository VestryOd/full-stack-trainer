# Signals and reactivity

## Theory

### A signal as the unit of state

A signal is a value that knows who reads it. The API has three parts:

```ts
const count = signal(0);          // WritableSignal<number>
count();                          // a read — and, at the same time, a dependency registration
count.set(5);                     // a new value
count.update((n) => n + 1);       // a new value from the previous one
const readonlyCount = count.asReadonly(); // Signal<number> for a public API
```

A signal is read by calling it, and that is not cosmetic: **the call itself is the subscription**. When `count()` runs inside a `computed`, an `effect` or a template, the reactive context in which the read happened is recorded as a consumer. No dependency list is ever declared — it is assembled from the actual reads on each recomputation, so dependencies can differ between runs (a conditional read is a conditional dependency).

Values are compared with `Object.is` by default; if the new value equals the old one, consumers are not notified. For non-primitives this means: **mutating an object is not a change**. `tickets().push(t)` notifies nobody, because the reference is the same. Hence the rule: work with signals immutably (`set([...arr, t])`), or — if the structure is expensive to copy — supply your own equality: `signal(value, { equal: myEqual })`.

### computed: laziness and memoization

```ts
readonly tickets = signal<readonly Ticket[]>([]);
readonly statusFilter = signal<TicketStatus | null>(null);

readonly filtered = computed(() => {
  const status = this.statusFilter();
  const all = this.tickets();
  return status === null ? all : all.filter((t) => t.status === status);
});
```

```
   ┌─────────────────────────┐    ┌─────────────────────────────┐
   │ tickets = signal([...]) │    │ statusFilter = signal(null) │
   └─────────────────────────┘    └─────────────────────────────┘
                ▼                                ▼
┌──────────────────────────────────────────────────────────────────┐
│ filtered = computed(() => ...)                                   │
│ reads both signals → the subscription builds itself,             │
│ from the actual reads, not from a dependency list                │
└──────────────────────────────────────────────────────────────────┘
                 ▼                                   ▼
┌─────────────────────────────────┐    ┌───────────────────────────┐
│ template @for (t of filtered()) │    │ openCount = computed(...) │
└─────────────────────────────────┘    └───────────────────────────┘
```

The mechanics in one sentence: changing a signal **marks** dependent graph nodes as stale (push), and recomputation happens **on read** (pull). That gives properties manual recomputation never has:

- **Laziness.** If nobody reads `filtered()` — say the block holding that list is hidden by `@if` — the function never runs.
- **Memoization.** While dependencies are unchanged, repeat reads return the cached value. So reading `filtered()` five times in a template is fine.
- **No intermediate states.** Even if you change several signals in a row, every reader sees a consistent result rather than a chain of half-updated values.
- **`computed` is read-only.** It has no `set`; if you want "derived, but overridable", that is `linkedSignal`.

### linkedSignal: derived state you can still overwrite

The classic case is a selected item. It depends on the list (when the list changes the selection must reset), yet the user can change it. `computed` does not fit — it is read-only; an `effect` that synchronizes two signals is the common mistake. `linkedSignal` exists for this:

```ts
// shorthand: recomputed whenever the signals it reads change
readonly selectedId = linkedSignal(() => this.filtered()[0]?.id ?? null);

// extended form: the previous value is available
readonly selectedTicket = linkedSignal<readonly Ticket[], Ticket | null>({
  source: this.filtered,
  computation: (tickets, previous) =>
    tickets.find((t) => t.id === previous?.value?.id) ?? tickets[0] ?? null,
});

// and it is still a writable signal
this.selectedId.set(105);
```

The point: the value lives as ordinary state (it accepts `set`/`update`), but a change of the source recomputes it, discarding the manual choice. The extended form lets you "keep the selection if it still exists in the new list".

### effect: why this is not useEffect

`effect` registers a function that re-runs whenever the signals it read change:

```ts
effect((onCleanup) => {
  const id = this.selectedId();          // a dependency
  const timer = setTimeout(() => this.markSeen(id), 3000);
  onCleanup(() => clearTimeout(timer));  // before the next run and on destroy
});
```

What matters about the mechanics:

- **Dependencies are not declared.** There is no array like in `useEffect`; whatever is actually read is tracked. A read that must not create a dependency goes inside `untracked()`.
- **Timing.** Effects created in a component context run as part of Angular's synchronization (together with that component's change detection), while root effects run as a microtask. This changed in v19: previously effects were scheduled independently.
- **Destruction is automatic.** An effect belongs to the injection context it was created in (usually a field of a component or service) and is destroyed with it. Manual variants: `manualCleanup: true` plus `ref.destroy()`, or passing an `injector` explicitly when creating an effect outside an injection context.
- **Writing signals inside an effect is allowed.** The `allowSignalWrites` flag was removed in v19. Allowed does not mean recommended: an effect that writes a signal was usually meant to be a `computed` or a `linkedSignal`.

Where `effect` genuinely belongs: logging and analytics, syncing to `localStorage`, imperative APIs (canvas, maps, third-party widgets), `focus()`/scrolling, integration with non-reactive code. Where it does not — nearly everything else:

```
┌──────────────────────────────────────────┬──────────────┬──────────────────────────────────────────┐
│ the task                                 │ the tool     │ why this one                             │
├──────────────────────────────────────────┼──────────────┼──────────────────────────────────────────┤
│ a value derived from others              │ computed     │ lazy, memoized, read-only                │
├──────────────────────────────────────────┼──────────────┼──────────────────────────────────────────┤
│ state from a source, still overridable   │ linkedSignal │ resets with the source + set/update      │
├──────────────────────────────────────────┼──────────────┼──────────────────────────────────────────┤
│ reaching outside: logs, storage, focus() │ effect       │ returns nothing, the effect is the point │
├──────────────────────────────────────────┼──────────────┼──────────────────────────────────────────┤
│ one signal mirroring another             │ none of them │ duplication = a broken data model        │
└──────────────────────────────────────────┴──────────────┴──────────────────────────────────────────┘
```

### Signal inputs, outputs and queries

```
┌─────────────────────────┬──────────────────────────────────────────┬──────────────────────────┐
│ declaration             │ what you get                             │ in the parent's template │
├─────────────────────────┼──────────────────────────────────────────┼──────────────────────────┤
│ input<T>()              │ Signal<T | undefined>, read-only         │ [x]="expr"               │
├─────────────────────────┼──────────────────────────────────────────┼──────────────────────────┤
│ input.required<T>()     │ Signal<T>; missing binding = build error │ [x]="expr"               │
├─────────────────────────┼──────────────────────────────────────────┼──────────────────────────┤
│ input(0, { transform }) │ the value passes through transform       │ [x]="expr"               │
├─────────────────────────┼──────────────────────────────────────────┼──────────────────────────┤
│ output<T>()             │ an object with emit(value)               │ (x)="onX($event)"        │
├─────────────────────────┼──────────────────────────────────────────┼──────────────────────────┤
│ model<T>(init)          │ a writable signal + an xChange output    │ [(x)]="expr"             │
├─────────────────────────┼──────────────────────────────────────────┼──────────────────────────┤
│ viewChild.required(Cmp) │ Signal<Cmp> from its own template        │ —                        │
├─────────────────────────┼──────────────────────────────────────────┼──────────────────────────┤
│ contentChildren(Cmp)    │ Signal<readonly Cmp[]> from projection   │ —                        │
└─────────────────────────┴──────────────────────────────────────────┴──────────────────────────┘
```

Details worth keeping in mind:

- An input is a **read-only signal**: a component cannot write to its own `input`. A writable input is `model()`, and it also creates the `xChange` output that makes `[(x)]` work.
- `transform` must be a pure, statically analyzable function; the built-in `booleanAttribute` and `numberAttribute` cover attribute coercion.
- `alias` changes the name in the template only, not the field name.
- Inputs are recorded statically by the compiler: you cannot add or remove one at runtime.
- Signal queries (`viewChild` and relatives) return signals rather than a `QueryList` and need no `ngAfterViewInit`: the result becomes available when the matching element appears and updates reactively. `contentChildren` looks at direct children only by default — `descendants: true` goes deeper.

### What targeted updates buy you

The dependency graph is the reason Angular updates the DOM surgically. Changing `statusFilter` marks `filtered` dirty, then everyone reading `filtered`, then the templates where those reads happen — and exactly those templates get re-checked. Neither the parent component nor the neighbouring cards are involved. In React you reach comparable precision by hand: `useMemo`, `memo`, splitting contexts, store selectors. In Angular it is a property of the read mechanism itself.

## React parallels

- **`signal` versus `useState`.** Both hold state, but `useState` gives you a snapshot of the current render while a signal is a live handle on a value. Consequences: no functional updates "so we don't lose the latest state" (`count.update` is convenience, not necessity), no stale values in callbacks, and no batching-as-semantics — the value is readable right after `set`, while the DOM updates at the next synchronization.
- **`computed` versus `useMemo`.** `useMemo` needs a manual dependency list and recomputes on every render where those dependencies changed, whether the result is needed or not. `computed` collects dependencies itself and is lazy: no read, no work. The whole class of "wrong dependency array" bugs disappears.
- **`effect` versus `useEffect` — the main divergence.** In React, `useEffect` is the universal tool: subscriptions, derived data, state synchronization, data fetching. In Angular, `effect` is a narrow tool for reaching outside the reactive graph. Derived data is `computed`, derived state is `linkedSignal`, data fetching is `resource`/`httpResource` (chapter 08). Importing the "I'll write an effect that recomputes and stores it" habit buys you redundant runs, races and hard-to-find cycles.
- **`input()` versus props.** A React prop is an ordinary value in a render closure; a signal input is a signal, so it can be read inside a `computed` without "adding it to the dependencies" and passed along as a source of reactivity. The flip side: an input cannot be written, and `input.required()` cannot be read before the binding is applied — in the constructor it is still empty (`ngOnInit` and later are fine).
- **Where the habit breaks:** in React, mutating state fails obviously — the component simply does not re-render, and you notice fast. In Angular, mutating an array inside a signal looks successful: the data in memory did change, the debugger shows the new item, and the DOM stays put — because `Object.is` compared the reference and concluded nothing happened. This is the single most time-consuming beginner bug with signals.

## What you will see in legacy code

- **Decorator-based `@Input()` and `@Output()`:** `@Input() ticket!: Ticket;`, `@Output() selected = new EventEmitter<Ticket>();`. They still work; `EventEmitter` is a Subject underneath, which is why older code sometimes subscribes to outputs as if they were Observables.
- **`ngOnChanges(changes: SimpleChanges)`** — the pre-signals way to react to input changes. With signal inputs it is unnecessary: the input is reactive itself, and "compute something when the input changes" is a `computed`.
- **Plain class fields plus `ChangeDetectorRef`:** `constructor(private cdr: ChangeDetectorRef)` and `this.cdr.markForCheck()` after an async update. That is the manual version of what a signal does on its own (chapter 03).
- **`@ViewChild('input') input!: ElementRef;` with `ngAfterViewInit`** and a `QueryList` with `.changes.subscribe(...)` — before signal queries the result could not be read earlier than a specific hook, and changes had to be subscribed to by hand.
- **`BehaviorSubject` as service state** with `state$ | async` in templates: `private state = new BehaviorSubject(initial); readonly state$ = this.state.asObservable();`. That is the previous generation of the same "private write, public read" pattern (chapters 05 and 09).

## What we add to the project

The ticket list moves onto signals: the array becomes a `signal`, the status and search filters become separate signals, and the filtered list and counters become `computed`. The card gains an output for selection, and the filter panel uses `model()` for two-way binding.

## Exercise

**Input:** the project from chapter 01 (a static array, `TicketCard` with `input.required`).
**Output:** a list with working filters, counters and selection — all on signals, with not a single `effect`.

Requirements:

1. `TicketList`: the ticket array becomes a `signal`. Two filter signals: status (`TicketStatus | null`) and a search string.
2. Derived values must be `computed` only: the filtered list (status AND a case-insensitive title search), the total count, the unassigned count, and the number of `urgent` tickets in the current selection. Check whether the counters count from the filtered list or the original one — and decide which behaviour is right for "Total".
3. A new `TicketFilters` component: an input with the available statuses; two-way binding for the selected status via `model()`; the search string also as a `model()`. No `@Input`/`@Output` decorators.
4. `TicketCard`: add an output via `output<Ticket>()` and a host click that emits it (the output name must not clash with a native DOM event — think about why).
5. Keep the selected ticket in a `linkedSignal` bound to the filtered list: changing the filter resets the selection, unless the selected ticket is still in the selection.
6. Adding a ticket: an "Add sample ticket" button that prepends an entry to the list. Make sure both the list and the counters see the update (hint: what matters is *how* you change the array).
7. Forbidden: not a single `effect` in this chapter. If it feels necessary, you are probably duplicating state.

Edge cases to think about:

- What happens if you use `this.tickets().push(newTicket)` instead of `set`? Why does the console look "correct" while the screen does not?
- `input.required<Ticket>()` inside the constructor — what does it return? And in `ngOnInit`?
- If a `computed` reads a signal inside an `if` and the condition was `false` at first, what are its dependencies, and what happens when the condition turns `true`?
- `statusFilter.set('open')` twice in a row — how many times does `filtered` recompute?
- Your `linkedSignal` stores the ticket object. What happens when a ticket is added to the list — does the selection survive if you compare by reference?

## Solution walkthrough

`src/app/tickets/ticket-filters.ts` — the filter panel on `model()`:

```ts
import { Component, input, model } from '@angular/core';
import { TicketStatus } from './ticket';

@Component({
  selector: 'app-ticket-filters',
  templateUrl: './ticket-filters.html',
  styleUrl: './ticket-filters.css',
})
export class TicketFilters {
  // a plain input: the status list is only read
  readonly statuses = input.required<readonly TicketStatus[]>();

  // model() = a writable signal input + an automatic statusChange output.
  // The parent writes [(status)]="statusFilter" and gets two-way binding
  readonly status = model<TicketStatus | null>(null);
  readonly search = model('');
}
```

`src/app/tickets/ticket-filters.html`:

```html
<div class="filters">
  <!-- no [(ngModel)] needed here: value plus an event does the same explicitly.
       Forms arrive in chapter 10; the bindings from chapter 01 suffice for now -->
  <input
    class="filters__search"
    type="search"
    placeholder="Search by title"
    [value]="search()"
    (input)="search.set($any($event.target).value)"
  />

  <div class="filters__statuses">
    <button
      type="button"
      [class.is-active]="status() === null"
      (click)="status.set(null)"
    >
      All
    </button>

    @for (s of statuses(); track s) {
      <button
        type="button"
        [class.is-active]="status() === s"
        (click)="status.set(s)"
      >
        {{ s }}
      </button>
    }
  </div>
</div>
```

`src/app/tickets/ticket-card.ts` — an output has been added:

```ts
import { Component, computed, input, output } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Ticket } from './ticket';

@Component({
  selector: 'app-ticket-card',
  imports: [DatePipe],
  templateUrl: './ticket-card.html',
  styleUrl: './ticket-card.css',
  host: {
    class: 'ticket-card',
    '[class.ticket-card--urgent]': 'isUrgent()',
    '[class.ticket-card--selected]': 'selected()',
    '[attr.aria-label]': '"Ticket #" + ticket().id',
    '(click)': 'selectTicket.emit(ticket())',
  },
})
export class TicketCard {
  readonly ticket = input.required<Ticket>();
  // a plain boolean input: the card doesn't decide whether it is selected — it is told
  readonly selected = input(false);

  // output() instead of @Output() + EventEmitter: it has no Subject API
  // that older code used to subscribe to directly.
  // Not named select, to avoid clashing with the native select event
  readonly selectTicket = output<Ticket>();

  protected readonly isUrgent = computed(() => this.ticket().priority === 'urgent');
}
```

`src/app/tickets/ticket-list.ts` — the core of the chapter:

```ts
import { Component, computed, linkedSignal, signal } from '@angular/core';
import { Ticket, TicketStatus } from './ticket';
import { TicketCard } from './ticket-card';
import { TicketFilters } from './ticket-filters';

const SAMPLE_TICKETS: readonly Ticket[] = [
  { id: 101, title: 'Cannot log in after password reset', status: 'new', priority: 'urgent', assignee: null, createdAt: '2026-08-10T09:12:00Z', slaHours: 4 },
  { id: 102, title: 'Invoice PDF is empty', status: 'open', priority: 'high', assignee: 'Dana', createdAt: '2026-08-09T14:41:00Z', slaHours: 8 },
  { id: 103, title: 'Export to CSV drops the last row', status: 'open', priority: 'medium', assignee: 'Ivan', createdAt: '2026-08-08T11:05:00Z' },
  { id: 104, title: 'Feature request: dark theme', status: 'pending', priority: 'low', assignee: 'Dana', createdAt: '2026-08-05T16:20:00Z' },
  { id: 105, title: 'Webhook retries are too aggressive', status: 'pending', priority: 'high', assignee: null, createdAt: '2026-08-04T08:00:00Z', slaHours: 24 },
  { id: 106, title: 'Typo on the pricing page', status: 'closed', priority: 'low', assignee: 'Ivan', createdAt: '2026-07-29T10:30:00Z' },
];

const STATUSES: readonly TicketStatus[] = ['new', 'open', 'pending', 'closed'];

@Component({
  selector: 'app-ticket-list',
  imports: [TicketCard, TicketFilters],
  templateUrl: './ticket-list.html',
  styleUrl: './ticket-list.css',
})
export class TicketList {
  protected readonly statuses = STATUSES;

  // State: three independent signals. Everything else is derived from them
  private readonly tickets = signal<readonly Ticket[]>(SAMPLE_TICKETS);
  protected readonly statusFilter = signal<TicketStatus | null>(null);
  protected readonly search = signal('');

  // Derived values. computed is lazy: if the block is hidden behind @if,
  // the body never even runs
  protected readonly filtered = computed(() => {
    const status = this.statusFilter();
    const query = this.search().trim().toLowerCase();

    return this.tickets().filter((ticket) => {
      const statusMatches = status === null || ticket.status === status;
      const titleMatches = query === '' || ticket.title.toLowerCase().includes(query);
      return statusMatches && titleMatches;
    });
  });

  // Total comes from the full list: it is a property of the data, not of the view.
  // The other counters come from the selection: they describe what the user sees
  protected readonly totalCount = computed(() => this.tickets().length);
  protected readonly visibleCount = computed(() => this.filtered().length);
  protected readonly unassignedCount = computed(
    () => this.filtered().filter((t) => t.assignee === null).length,
  );
  protected readonly urgentCount = computed(
    () => this.filtered().filter((t) => t.priority === 'urgent').length,
  );

  // Selection: derived state that can still be set by hand.
  // source is the filtered list; computation receives the new source value
  // and the previous value of the linkedSignal itself
  protected readonly selectedId = linkedSignal<readonly Ticket[], number | null>({
    source: this.filtered,
    computation: (tickets, previous) => {
      const previousId = previous?.value ?? null;
      // the selection survives if the ticket is still in view; otherwise it resets
      return tickets.some((t) => t.id === previousId) ? previousId : null;
    },
  });

  protected select(ticket: Ticket): void {
    // clicking again clears the selection — ordinary state, ordinary set
    this.selectedId.update((id) => (id === ticket.id ? null : ticket.id));
  }

  protected addSampleTicket(): void {
    const nextId = Math.max(...this.tickets().map((t) => t.id)) + 1;

    // A NEW array rather than push: the signal compares values with Object.is,
    // and mutating the same reference would notify nobody
    this.tickets.update((tickets) => [
      {
        id: nextId,
        title: `Sample ticket #${nextId}`,
        status: 'new',
        priority: 'medium',
        assignee: null,
        createdAt: new Date().toISOString(),
      },
      ...tickets,
    ]);
  }
}
```

`src/app/tickets/ticket-list.html`:

```html
<section class="ticket-list">
  <header class="ticket-list__header">
    <h2>Tickets</h2>

    <!-- two-way binding: [(status)] expands into
         [status]="statusFilter()" + (statusChange)="statusFilter.set($event)" -->
    <app-ticket-filters
      [statuses]="statuses"
      [(status)]="statusFilter"
      [(search)]="search"
    />

    <p class="ticket-list__summary">
      {{ visibleCount() }} of {{ totalCount() }} ·
      {{ unassignedCount() }} unassigned ·
      {{ urgentCount() }} urgent
    </p>
  </header>

  <button type="button" (click)="addSampleTicket()">Add sample ticket</button>

  <ul class="ticket-list__items">
    @for (ticket of filtered(); track ticket.id) {
      <li>
        <app-ticket-card
          [ticket]="ticket"
          [selected]="ticket.id === selectedId()"
          (selectTicket)="select($event)"
        />
      </li>
    } @empty {
      <li class="ticket-list__empty">No tickets match the filter</li>
    }
  </ul>
</section>
```

Three decisions in this code are worth pointing out. First, `tickets` is a private signal and only `computed` values are exposed; that is the seed of what becomes a store service in chapter 05. Second, the selection stores an `id` rather than an object — when the list is refreshed, an object may be replaced by a new one carrying the same data, and reference comparison would lose the selection. Third, there is not a single class method call in the templates — only signal reads and `computed` values.

Answers to the edge cases:

- `this.tickets().push(newTicket)` does change the array, but the signal never learns about it: `set` was not called, and `Object.is(oldArray, oldArray)` is `true`. The console shows the new data (you are looking at the same live object), the screen shows the old. On top of that, the `readonly Ticket[]` type will not let you call `push` — the type is insurance against exactly this bug.
- In the constructor, `input.required()` throws: bindings have not been applied yet, and "a required input with no value" is an invalid state. Inputs can be read from `ngOnInit` onwards — better still, do not read them imperatively at all, but wrap them in a `computed` that reads them at first use.
- A `computed`'s dependencies come from the reads of the current run. If the condition was `false` and the second branch was never read, its signals are not among the dependencies. When the condition turns `true` (that change arrives from a signal that *was* read), the `computed` recomputes, reads the new signals, and they join the graph. Nothing is required from the developer, and this is the fundamental difference from a static dependency array.
- Zero times. The second `set('open')` does not change the value (`Object.is` says equal), so consumers are not marked. Had the values differed, `filtered` would recompute once — on the next read, not on each `set`.
- Adding a ticket makes `filtered` return a new array in which the other objects are the same references, so reference comparison happens to work in this particular case. But once the list comes from HTTP (chapter 08), every reload produces new objects with the same `id`s, and the selection would be lost on every refresh. That is why the solution stores an `id`.

## Check yourself

1. Explain in your own words why `computed` needs no dependency list, and what physically happens at `signal.set(...)` — before anybody reads the dependent value.
2. Why does mutating an object inside a signal fail to update the DOM, and what are the two ways to live with that?
3. Name three situations where `effect` is the right tool, and explain why "recompute one piece of state from another" is not among them.
4. How does `linkedSignal` differ from `computed` and from the pair "a signal plus an effect that overwrites it"?
5. `model<T>()` — what exactly does it create, and why does that make `[(x)]` work? How does it differ from `input()` in terms of who owns the state?

<details>
<summary>Answers</summary>

1. Dependencies are not declared because reading a signal *is* the registration: while a `computed` runs its body, a reactive context is active, and every signal called inside records that context as a consumer. The resulting list is exact by construction (it contains precisely what was read) and dynamic (a conditional read is a conditional dependency). At `signal.set(...)` no recomputation happens: the signal compares the new value to the old with `Object.is`, and if it differs, marks consumers stale (dirty) down the graph. The computation happens later, at the first read. Splitting the push notification from the pull computation is what makes laziness possible.
2. A signal compares **values**, and for objects and arrays the default comparison is by reference (`Object.is`). Mutation leaves the reference intact, so "nothing changed": consumers are not marked, the DOM is untouched. Two ways out: (a) stay immutable — `set`/`update` returning a new object or array, and type the state as `readonly` so the compiler catches mutations; (b) pass your own equality function, `signal(value, { equal })` — justified when copying the structure costs more than comparing it, but then you must call `set` deliberately.
3. `effect` fits where the result is an impact on something outside the reactive graph: (a) writing to external storage, a log or analytics; (b) imperative APIs — canvas, a map, a third-party widget, `focus()`, scrolling; (c) integration with non-reactive code that has to be *told* about a change. "Recompute state from state" does not qualify, because it has a return value and that value belongs in the graph: `computed` (read-only) or `linkedSignal` (when manual `set` is also needed). An effect in that role creates a second source of truth, extra runs and a risk of cycles — and since signal writes inside effects have been allowed since v19, the runtime will not stop you.
4. `computed` is read-only: you cannot overwrite it, it always equals its formula. `linkedSignal` is a writable signal whose value is recomputed when its source changes — "state with a reset rule". A "signal plus effect" pair does the same thing but worse: the state is updated in a separate run (so there is a moment where signal and source disagree), effect ordering is not guaranteed, and the extended `linkedSignal` form gives access to the previous value, which with an effect you would have to store by hand.
5. `model<T>(init)` creates a **writable** signal input plus a paired output named `<name>Change`. That is exactly why `[(x)]="expr"` works — it is sugar for `[x]` + `(xChange)`, and `model` provides both halves. The difference from `input()` is ownership: an `input` is read-only and the parent is the sole owner of the value; a `model` is shared ownership, the child may write and the parent finds out. Practical test: if the component's nature is to *edit* the value it was given (a control, a filter, an accordion), that is a `model`; if it only displays it, use `input` plus, if needed, an `output` for the event.

</details>

## Common mistake

Mistake number one is `effect` instead of `computed`. It looks like this:

```ts
// DO NOT DO THIS
readonly filtered = signal<readonly Ticket[]>([]);

constructor() {
  effect(() => {
    this.filtered.set(this.tickets().filter((t) => t.status === this.statusFilter()));
  });
}
```

The code works, which is why it survives in real projects. But now the same data has two sources of truth — `tickets` and its filtered copy — and they disagree for the duration of a synchronization pass. Downstream that shows up as "the filter is right after the first click but one step behind after a fast second one", "the old selection flashes on screen", and, once a second such effect appears, update cycles. `computed` solves the same task without a copy of the state: it derives rather than stores, and it is lazy on top. The practical rule: if there is a `set`/`update` inside an `effect`, it is almost certainly a `computed` or a `linkedSignal`.

The second common mistake is mutation inside a signal: `this.tickets().push(t)`, `this.filters().status = 'open'`, `arr().sort()`. A React developer knows state must be updated immutably, but there the violation is immediately visible — the component does not re-render. In Angular the mutation "almost works": if a template check happens for some other reason (a click, another signal, a timer), the new data suddenly appears on screen, and the bug becomes intermittent — "sometimes it updates, sometimes it doesn't". The defence is cheap: type the state as `readonly Ticket[]`/`Readonly<T>` and the compiler will forbid `push`/`sort`/field assignment for you. Watch out for `sort()` and `reverse()` in particular — they mutate in place, so a `computed` over a signal needs `toSorted()` or a copy via spread.
