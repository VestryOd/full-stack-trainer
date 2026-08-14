# Components and templates

## Theory

### The component: what the decorator describes

`@Component` describes how a class becomes an element on the page:

```ts
@Component({
  selector: 'app-ticket-card',   // how the component is called from a template
  imports: [TicketBadge],        // the template scope of THIS component
  templateUrl: './ticket-card.html',
  styleUrl: './ticket-card.css', // singular; styleUrls is the older form
  host: { class: 'ticket-card' }, // bindings on the host element
  // encapsulation defaults to Emulated, changeDetection defaults to OnPush
})
export class TicketCard {}
```

A selector is not necessarily an element name. The compiler matches markup against a CSS-like selector, so several forms are possible:

- `'app-ticket-card'` — an element selector, the usual case for components;
- `'[appHighlight]'` — an attribute selector, the usual case for directives (chapter 06);
- `'button[appPrimary]'` — a combination: "only on a `button` carrying this attribute";
- `'.ticket-card'` — by class; you meet it in libraries, rarely need it in your own code.

### A template is compiled, not executed

An Angular template is not JSX. JSX is syntactic sugar over function calls: it turns into JS and runs as ordinary code. An Angular template is a separate language that **the compiler parses at build time** and turns into two functions inside the component class.

```
┌───────────────────────────────────────────────────┐
│ ticket-card.html                                  │
│ <h3>{{ ticket().title }}</h3>                     │
│ <span [class.urgent]="isUrgent()">                │
└───────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│ the Angular compiler (AOT), at build time         │
│ parses the template, type-checks the expressions  │
│ (strictTemplates), matches tags against selectors │
│ from this component's imports                     │
└───────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│ two functions written into the component class    │
│ create: builds nodes and listeners once           │
│ update: re-reads the binding expressions          │
└───────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│ DOM                                               │
│ nodes survive between checks; only the bindings   │
│ whose values actually changed are touched         │
└───────────────────────────────────────────────────┘
```

Three practical consequences follow:

1. **Template errors are caught at build time.** A typo in a property name, a wrong type in a binding, an unregistered tag (`NG8001`) — all of it is compiler diagnostics rather than a blank spot in the browser. In v22 the compiler additionally catches invalid `@for` blocks, an element matched by two components, and two inputs sharing one alias.
2. **Expressions are a restricted subset.** No `new`, no destructuring, no bitwise operators, no comma operator. Assignments are allowed in event handlers only. On the other hand you do get `?.`, `!`, `$any(...)`, pipes (`| date`), spread in literals and calls, and — since v21.2 — arrow functions in event handlers.
3. **The create/update split *is* Angular's update model.** Nodes are not rebuilt: a check re-evaluates the binding expressions only, and the DOM is touched where a value actually changed.

One more thing: `update` runs on every check of that template. So a template expression must be cheap — this is not "once per render" as in React, it is "an unknown number of times".

### Binding syntax

```
┌──────────────────┬───────────────────────────────────────────────────┬───────────────┐
│ in a template    │ what Angular does                                 │ in React      │
├──────────────────┼───────────────────────────────────────────────────┼───────────────┤
│ {{ expr }}       │ a text node, refreshed on every check             │ {expr}        │
├──────────────────┼───────────────────────────────────────────────────┼───────────────┤
│ [prop]="expr"    │ a PROPERTY of the element or a component input    │ prop={expr}   │
├──────────────────┼───────────────────────────────────────────────────┼───────────────┤
│ [attr.x]="expr"  │ an attribute via setAttribute/removeAttribute     │ x={expr}      │
├──────────────────┼───────────────────────────────────────────────────┼───────────────┤
│ (event)="stmt"   │ an event listener; stmt receives $event           │ onEvent={fn}  │
├──────────────────┼───────────────────────────────────────────────────┼───────────────┤
│ [(x)]="expr"     │ sugar for [x]="expr" + (xChange)="expr = $event"  │ no equivalent │
├──────────────────┼───────────────────────────────────────────────────┼───────────────┤
│ [class.x]="cond" │ toggles exactly one class                         │ className=... │
├──────────────────┼───────────────────────────────────────────────────┼───────────────┤
│ [style.w.px]="n" │ one style property, with units spelled out        │ style={{...}} │
├──────────────────┼───────────────────────────────────────────────────┼───────────────┤
│ prop="text"      │ a static string — the expression is NOT evaluated │ prop="text"   │
└──────────────────┴───────────────────────────────────────────────────┴───────────────┘
```

The distinction people trip over: **`[x]` writes a property, not an attribute**. `[value]="text"` assigns `input.value`, while `[attr.value]="text"` calls `setAttribute('value', ...)`. For most HTML properties the difference is invisible, but it becomes decisive wherever no property exists: `aria-*`, `data-*`, SVG attributes, `colspan` — those need `[attr.]`. The mirror case is `disabled`: the attribute `disabled="false"` still disables a button (presence is what counts, not the value), whereas `[disabled]="false"` does not.

Two-way binding `[(x)]="expr"` is neither magic nor object watching: it is literally the pair `[x]` + `(xChange)`. Your own component joins that syntax if it has an input `x` and an output `xChange` — or, more modern, a `model()` (chapter 02).

### Control flow

Built-in control flow (`@if`, `@for`, `@switch`, `@let`) is part of the template language and needs no imports:

```html
@if (selected(); as ticket) {
  <app-ticket-card [ticket]="ticket" />
} @else if (loading()) {
  <p>Loading…</p>
} @else {
  <p>Nothing selected</p>
}

@for (ticket of tickets(); track ticket.id) {
  <app-ticket-card [ticket]="ticket" />
} @empty {
  <p>No tickets match the filter</p>
}

@switch (ticket.status) {
  @case ('new')
  @case ('open') { <span class="badge badge-active">Active</span> }
  @case ('pending') { <span class="badge">Waiting for customer</span> }
  @default { <span class="badge badge-done">Closed</span> }
}
```

What matters here:

- **`track` is mandatory** in `@for` — not an option but part of the syntax. It tells Angular how to match data items to the DOM nodes already created for them. Inside the block you get `$index`, `$count`, `$first`, `$last`, `$even`, `$odd`; in nested loops they can be aliased with `let`.
- **`@switch` does not fall through** — no `break` needed. Several consecutive `@case` markers may point at one block (as above). A trailing `@default never;` enables exhaustiveness checking: if a new variant appears in the union type, the build fails.
- **`@if (expr; as alias)`** stores the result of the expression in a block variable — handy so a signal is not called twice.
- **`@let x = expr;`** declares a local template variable: read-only, visible after its declaration and only inside its block, not redeclarable. It is a way to avoid repeating an expression, not a substitute for `computed` — heavy logic still belongs in the class.

### Host bindings

The host element is that `<app-ticket-card>` in the parent's markup. Bindings on it are described by the `host` object:

```ts
@Component({
  selector: 'app-ticket-card',
  host: {
    class: 'ticket-card',                        // a static class
    '[class.ticket-card--urgent]': 'isUrgent()', // a conditional class
    '[attr.aria-label]': '"Ticket " + ticket().id',
    '(click)': 'open()',                         // a listener on the host
  },
})
```

On collisions: a static binding of the component loses to the consumer's binding, a dynamic value beats a static one, and between two dynamic ones the component's host binding wins. The `@HostBinding`/`@HostListener` decorators do the same thing and exist purely for backwards compatibility — the documentation explicitly recommends `host`.

### Styles and view encapsulation

```
                     ViewEncapsulation: what happens to component styles
┌────────────────────┬──────────────────────────────────────────────────────┬────────────────┐
│ mode               │ mechanics                                            │ when to use    │
├────────────────────┼──────────────────────────────────────────────────────┼────────────────┤
│ Emulated (default) │ _nghost/_ngcontent attributes + rewritten selectors  │ almost always  │
├────────────────────┼──────────────────────────────────────────────────────┼────────────────┤
│ ShadowDom          │ a native shadow root: styles neither enter nor leave │ hard isolation │
├────────────────────┼──────────────────────────────────────────────────────┼────────────────┤
│ None               │ styles land in the document as global ones           │ themes, resets │
└────────────────────┴──────────────────────────────────────────────────────┴────────────────┘
           :host is the host element itself; ::ng-deep pierces isolation downwards
                         but is kept for backwards compatibility only
```

In Emulated mode the compiler appends a component-unique attribute to every selector from `styleUrl`, and the matching attribute to the elements of the template. Hence the two perennial questions:

- "Why doesn't my `.badge` from this component affect a child component?" — because the child's nodes carry a different attribute. Styling the internals of someone else's component from the outside is impossible by design; the right path is an input, a CSS variable or a class on the host — not `::ng-deep`.
- "Why does the global `styles.css` work everywhere?" — global styles are not rewritten. Isolation is one-way: styles get in from the outside, they do not get out from the inside.

`:host` in a component's CSS is its host element (`:host(.ticket-card--urgent)` — when the class is present). `:host-context()` exists but relies on a mechanism considered deprecated in modern browsers.

## React parallels

- **JSX is JS, a template is a DSL.** JSX gives you the whole language, so the cost of a mistake is a runtime bug. An Angular template is compiled and type-checked (`strictTemplates`), so most markup mistakes become build errors. The price is a restricted expression subset: no `items.reduce(...)` with an inline callback, no `new Date()`. Logic moves into the class — not as a style preference but as a requirement of the template language.
- **`prop={expr}` versus `[prop]="expr"` and `prop="text"`.** In JSX, braces are the only way to pass a non-string, and forgetting them is hard. In Angular, `prop="t"` is valid markup that simply passes the string `"t"`; with `strictTemplates` the compiler usually catches it on a type mismatch, but with a `string` input the mistake slips through silently.
- **`key` versus `track`.** Both are about element identity, but `key` in React is an optional prop with a console warning, whereas `track` in Angular is a mandatory part of the `@for` syntax. The consequences are the same: a wrong key or `track $index` while sorting means recreated or shuffled nodes and lost DOM state (focus, scroll position, the value of an uncontrolled input).
- **Two-way binding is sugar, not observation.** In React, form state is always "controlled": `value` + `onChange`. `[(x)]` in Angular is the same pattern written as a single token: `[x]` + `(xChange)`. There is no mutation tracking of objects, unlike old AngularJS or Vue.
- **Where the habit breaks:** in React you happily write `{items.filter(f).map(m)}` right in the markup — the component function runs a bounded number of times and the cost is predictable. In Angular the same expression lands in the `update` function and runs on every check of the template; worse, `filter`/`map` return a **new array each time**, so `@for` sees a new reference and does extra matching work. Derived data in Angular is computed in `computed` (chapter 02), not in the template.

## What you will see in legacy code

- **Structural directives instead of blocks:** `*ngIf="cond"`, `*ngIf="cond; else other"` with `<ng-template #other>`, `*ngFor="let t of tickets; trackBy: trackById"` (where `trackBy` is a class method with the signature `(index, item)`), `[ngSwitch]` + `*ngSwitchCase`. They still work, but the new control flow is not an alternative style — it is the replacement: faster and needing no imports.
- **`CommonModule` in `imports`** — the mandatory companion of `*ngIf`/`*ngFor` and pipes such as `date`, `currency`. Seeing it in a standalone component means that component still runs on the old directives.
- **`[ngClass]="{active: isActive}"` and `[ngStyle]="{width: w + 'px'}"`** instead of `[class.active]`/`[style.width.px]`. The directives are still there, but targeted bindings are cheaper and type better.
- **`@HostBinding('class.active') isActive = false;` and `@HostListener('click', ['$event'])`** instead of the `host` object — the most reliable marker of code written before v17.
- **`styleUrls: ['./x.component.css']`** (an array), `encapsulation: ViewEncapsulation.None` "so the styles just work", `::ng-deep`/`/deep/`/`>>>` to pierce isolation, and template references `#input` combined with `@ViewChild('input')` instead of signal queries (chapter 02).

## What we add to the project

Support Desk gets a typed ticket model, a list of static data rendered with `@for`/`@empty`, and a card component: the status badge through `@switch`, the priority class through a host binding, and isolated styles.

## Exercise

**Input:** the project from chapter 00 with the `TicketList` placeholder.
**Output:** a list of several tickets, each rendered by its own card component.

Requirements:

1. Put the ticket model in its own file: `id` (number), `title`, `status` (`'new' | 'open' | 'pending' | 'closed'`), `priority` (`'low' | 'medium' | 'high' | 'urgent'`), `assignee` (string or `null`), `createdAt`, `slaHours` (number, optional). Status and priority must be unions, not `string`.
2. In `TicketList`, a static array of 6–8 tickets; among them at least one unassigned (`assignee: null`), one with status `closed` and one with priority `urgent`.
3. The `TicketCard` component shows the title, a human-readable status label, the priority, the assignee or "Unassigned", and the creation date. Build the status label in the template with `@switch` rather than a map in the class (the point of this chapter is the blocks; in chapter 06 the same thing becomes a pipe).
4. The card's host element: a static class, a conditional class for `urgent`, and an `aria-label` carrying the ticket number. All of it through the `host` object, no decorators.
5. In `TicketList`: `@for` with a correct `track`, `@empty` with a message, `@if` around an "N tickets / N unassigned" line, and `@let` in at least one place where you would otherwise repeat an expression.
6. Card styles live in the card's own file; the badge must not leak into other components. Define the spacing between cards so that the list owns it, not the card.
7. Constraint: no class method calls and no `filter`/`map` in templates.

Edge cases to think about:

- What happens with `track ticket.id` if two tickets in the array share an `id`?
- Why must `aria-label` go through `[attr.aria-label]` while a button's `disabled` goes through `[disabled]`?
- `@empty` fires on an empty array. What if `null` arrives instead of an array — what does the user see and what does the compiler say?
- If the global `styles.css` says `.badge { color: red }` and `ticket-card.css` says `.badge { color: blue }`, which colour wins and why?
- You wrote `track $index` and later added sorting by priority. What breaks visually, and why is it invisible on an unchanging list?

## Solution walkthrough

`src/app/tickets/ticket.ts` — the model. Its own file, because the service, the form and the HTTP layer will all import it later:

```ts
export type TicketStatus = 'new' | 'open' | 'pending' | 'closed';
export type TicketPriority = 'low' | 'medium' | 'high' | 'urgent';

export interface Ticket {
  readonly id: number;
  readonly title: string;
  readonly status: TicketStatus;
  readonly priority: TicketPriority;
  readonly assignee: string | null;
  readonly createdAt: string; // an ISO string: what the API will send in chapter 08
  readonly slaHours?: number;
}
```

`src/app/tickets/ticket-card.ts`:

```ts
import { Component, computed, input } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Ticket } from './ticket';

@Component({
  selector: 'app-ticket-card',
  // the date pipe is used in THIS template, so it is imported here
  imports: [DatePipe],
  templateUrl: './ticket-card.html',
  styleUrl: './ticket-card.css',
  host: {
    // a static class: we could put class="..." at the usage site instead,
    // but then every consumer would have to remember it
    class: 'ticket-card',
    // a conditional class — targeted toggling, no [ngClass]
    '[class.ticket-card--urgent]': 'isUrgent()',
    // aria-label has no DOM property, hence [attr.]
    '[attr.aria-label]': '"Ticket #" + ticket().id',
  },
})
export class TicketCard {
  // A signal input: the value is read as a function — ticket().
  // input()/output() mechanics come in chapter 02; here it is enough that
  // this is a typed, required input of the component
  readonly ticket = input.required<Ticket>();

  // Derived values are computed in the class, not in the template:
  // in the template this would be recomputed on every check
  protected readonly isUrgent = computed(() => this.ticket().priority === 'urgent');
}
```

`src/app/tickets/ticket-card.html`:

```html
<!-- @let so that ticket() isn't repeated on every line -->
@let t = ticket();

<h3 class="ticket-card__title">{{ t.title }}</h3>

<!-- @switch does not fall through: consecutive @case markers = one block -->
@switch (t.status) {
  @case ('new')
  @case ('open') {
    <span class="badge badge--active">Active</span>
  }
  @case ('pending') {
    <span class="badge badge--waiting">Waiting for customer</span>
  }
  @default {
    <span class="badge badge--done">Closed</span>
  }
}

<dl class="ticket-card__meta">
  <dt>Priority</dt>
  <dd>{{ t.priority }}</dd>

  <dt>Assignee</dt>
  <!-- ?? instead of a ternary: null and undefined are handled alike -->
  <dd>{{ t.assignee ?? 'Unassigned' }}</dd>

  <dt>Created</dt>
  <!-- the date pipe instead of a class method: a pure pipe caches by its
       input value, a method would run on every check (chapter 06) -->
  <dd>{{ t.createdAt | date: 'mediumDate' }}</dd>
</dl>
```

`src/app/tickets/ticket-card.css`:

```css
/* :host is the <app-ticket-card> element itself. The component owns how it
   looks inside, but not where it sits: outer spacing belongs to the list */
:host {
  display: block;
  padding: 0.75rem 1rem;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
}

/* :host(...) — the host under a condition; the class comes from a host binding */
:host(.ticket-card--urgent) {
  border-color: #d64545;
}

/* this .badge will not leak into other components: the compiler appends
   an attribute unique to TicketCard to the selector */
.badge {
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  background: #eee;
  font-size: 0.75rem;
}

.badge--active { background: #dcf0dc; }
.badge--waiting { background: #fdf1cc; }
.badge--done { background: #e6e6e6; }
```

`src/app/tickets/ticket-list.ts`:

```ts
import { Component } from '@angular/core';
import { Ticket } from './ticket';
import { TicketCard } from './ticket-card';

@Component({
  selector: 'app-ticket-list',
  // TicketCard must be listed here or <app-ticket-card> is not recognized.
  // DatePipe, however, is not needed here: it is used in the card's template,
  // and every component has its own template scope
  imports: [TicketCard],
  templateUrl: './ticket-list.html',
  styleUrl: './ticket-list.css',
})
export class TicketList {
  // Static data for this chapter. In chapter 02 the array becomes a signal,
  // in chapter 05 it moves into a service, in chapter 08 it comes from HTTP
  protected readonly tickets: readonly Ticket[] = [
    { id: 101, title: 'Cannot log in after password reset', status: 'new', priority: 'urgent', assignee: null, createdAt: '2026-08-10T09:12:00Z', slaHours: 4 },
    { id: 102, title: 'Invoice PDF is empty', status: 'open', priority: 'high', assignee: 'Dana', createdAt: '2026-08-09T14:41:00Z', slaHours: 8 },
    { id: 103, title: 'Export to CSV drops the last row', status: 'open', priority: 'medium', assignee: 'Ivan', createdAt: '2026-08-08T11:05:00Z' },
    { id: 104, title: 'Feature request: dark theme', status: 'pending', priority: 'low', assignee: 'Dana', createdAt: '2026-08-05T16:20:00Z' },
    { id: 105, title: 'Webhook retries are too aggressive', status: 'pending', priority: 'high', assignee: null, createdAt: '2026-08-04T08:00:00Z', slaHours: 24 },
    { id: 106, title: 'Typo on the pricing page', status: 'closed', priority: 'low', assignee: 'Ivan', createdAt: '2026-07-29T10:30:00Z' },
  ];
}
```

`src/app/tickets/ticket-list.html`:

```html
<section class="ticket-list">
  <header class="ticket-list__header">
    <h2>Tickets</h2>

    @if (tickets.length > 0) {
      <p class="ticket-list__summary">{{ tickets.length }} tickets</p>
    }
  </header>

  <ul class="ticket-list__items">
    <!-- track by id: a stable identifier of the data, not a position.
         On sorting or prepending, the nodes are reused -->
    @for (ticket of tickets; track ticket.id) {
      <li>
        <!-- [ticket]="ticket" — a property binding to the component input.
             Without brackets this would be the string "ticket" -->
        <app-ticket-card [ticket]="ticket" />
      </li>
    } @empty {
      <li class="ticket-list__empty">No tickets match the filter</li>
    }
  </ul>
</section>
```

`src/app/tickets/ticket-list.css`:

```css
.ticket-list__items {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;      /* spacing between cards is the list's responsibility */
  padding: 0;
  margin: 0;
  list-style: none;
}

.ticket-list__summary {
  color: #666;
  font-size: 0.875rem;
}
```

Note two things in this code. First, `DatePipe` is listed in `imports` of `TicketCard`, where the template uses it, and absent from `TicketList` — template scopes are independent, "import it once at the top" does not exist here. Second, `tickets` is typed as `readonly Ticket[]`: the array does not change in this chapter, and once it does it will be a signal rather than an in-place mutation.

Answers to the edge cases:

- A duplicate `id` under `track ticket.id` is a runtime error: Angular detects that one key maps to several items and throws about duplicated keys in `@for`. That is better than a silently shuffled DOM, and it is exactly why the key must be genuinely unique rather than "usually unique".
- `aria-label` has no DOM property (unlike `id`, `value`, `disabled`), so there is nothing for `[ariaLabel]` to write to — `[attr.aria-label]` is required. A button, conversely, does have a `disabled` property, and a property binding handles `false` correctly; `[attr.disabled]="false"` would leave the attribute in the markup with the string `"false"` and the button would stay disabled.
- `null` instead of an array: `@for` over `null` is a type error under `strictTemplates`, so the build fails. If the type does allow `null`, write `@for (t of tickets ?? []; track t.id)` — and then `@empty` behaves exactly as for an empty array.
- The component's `.badge` wins, not because Angular prioritizes it but by ordinary CSS rules: the compiler appends an attribute, so the selector becomes `.badge[_ngcontent-abc]` — more specific than a global `.badge`. Do not treat that as "isolation from global styles" though: `!important` or a more specific global selector still wins.
- `track $index` ties nodes to positions. After sorting, the item at index 0 is still the same DOM node with rewritten content — so instead of moving nodes around, Angular rewrites all of them. On an unchanging list this is invisible (positions and data line up), so the bug lives in the code until the first sort, prepend or removal, and then shows up as lost focus, jumped scroll position and stuttering animations.

## Check yourself

1. Explain in your own words why `[value]="text"` and `[attr.value]="text"` are different things, and give two cases where the choice genuinely matters.
2. What exactly does `track` tell Angular, and what physically happens to the DOM under `track $index` when the list is sorted?
3. `[(size)]="value"` on your own component — what does it expand into, and what must the component provide for that syntax to compile?
4. Why is `{{ formatDate(t.createdAt) }}` a bad idea in Angular while `{formatDate(t.createdAt)}` is perfectly fine in React? What should you do instead?
5. How does Emulated encapsulation achieve isolation, and why does it prevent styling a child component's internals from the outside? What is offered instead of `::ng-deep`?

<details>
<summary>Answers</summary>

1. `[value]` assigns a **property** on the DOM object (`el.value = text`); `[attr.value]` calls `setAttribute`. They diverge wherever no property exists, or where property and attribute live separate lives. First case: `aria-*`/`data-*`/SVG attributes/`colspan` — no properties at all, only `[attr.]` works. Second: `input.value` — the property reflects the current field value while the `value` attribute only carries the initial one, so binding the attribute will not update text the user has already typed. Third classic: `disabled` — the attribute acts by its mere presence, so `[attr.disabled]="false"` keeps the button disabled while `[disabled]="false"` does not.
2. `track` defines the identity rule: which value tells Angular "this is the same data item as before", so it can reuse the DOM node created for it along with that node's state. With `track $index`, identity becomes the position. After sorting, position 0 holds a different data object, but Angular treats it as "the same item" and rewrites the node's content instead of moving the node — and so on down the list. The result is a full update of every node instead of a reorder: lost focus, reset scroll, broken animations, and in lists of components, redundant work in their templates.
3. It expands into `[size]="value"` + `(sizeChange)="value = $event"`. So the component needs an input `size` and an output named exactly `sizeChange` (`<input name>Change`). The modern way to get both at once is `model<T>()`, which creates a writable signal input and the paired output automatically (chapter 02).
4. In React the component function body runs a bounded number of times, and a call inside the markup costs the same as any other render code. In Angular the expression lands in the template's `update` function and is evaluated on **every** check of that template — and you do not control how many there are. On top of that the result cannot be cached: Angular has no idea what the method depends on. The right options are a `computed` in the class (memoized by its signal dependencies), a pure pipe (cached by its input value), or data prepared in advance.
5. The compiler gives every component a unique attribute: `_ngcontent-<id>` on the nodes of its template, `_nghost-<id>` on the host element, and appends that attribute to every selector from `styleUrl`. A parent's selector therefore cannot match a child component's nodes — they carry a different component's attribute. That is the isolation, and it is one-way: global styles are not rewritten and do reach inside. Instead of `::ng-deep` (kept for backwards compatibility and discouraged), the child component should expose customization points of its own: an input that drives its classes, CSS variables it reads, or a class on its host element that the consumer sets from outside.

</details>

## Common mistake

The most common mechanical mistake is forgetting the square brackets: `<app-ticket-card ticket="ticket" />`. In JSX, omitting braces passes a string and you notice at once; in Angular the line looks like a valid HTML attribute because it *is* one — the component receives the string `"ticket"`, not an object. `strictTemplates` saves you here: the input is typed as `Ticket`, a string does not fit, and the build fails on a type mismatch. But when the input is typed `string` (a title, an id-as-string, an icon name), the mistake passes silently and turns into "why do all the cards show the same text". The rule: anything that is not a literal string from the markup goes through `[ ]`.

The second mistake is importing the React habit of computing data inside the markup: `@for (t of tickets.filter(x => x.status !== 'closed'); track t.id)`. There are two independent penalties. First, the expression runs on every check of the template rather than once. Second, and more insidious, `filter` returns a **new array** on every call, so `@for` receives a different collection reference each time and has to re-match items by `track` — precisely the extra work `track` was supposed to prevent. Filtering, sorting and aggregates belong in a `computed` in the class (chapter 02); the template only reads the finished value.
