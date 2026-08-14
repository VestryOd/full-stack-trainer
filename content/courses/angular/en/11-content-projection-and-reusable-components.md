# Content projection and reusable components

## Theory

### Three ways to hand markup into a component

```
                          Three ways to hand markup to someone else's component
┌──────────────────────┬──────────────────────────┬────────────────────────┬────────────────────────────┐
│ approach             │ when it is created       │ passing data in        │ when to use it             │
├──────────────────────┼──────────────────────────┼────────────────────────┼────────────────────────────┤
│ ng-content           │ ALWAYS, even when hidden │ no: the parent context │ static slots               │
├──────────────────────┼──────────────────────────┼────────────────────────┼────────────────────────────┤
│ ng-template + outlet │ when it is inserted      │ yes: template context  │ table rows, cells          │
├──────────────────────┼──────────────────────────┼────────────────────────┼────────────────────────────┤
│ createComponent()    │ when your code calls it  │ yes: setInput()        │ dialogs, toolbars, plugins │
└──────────────────────┴──────────────────────────┴────────────────────────┴────────────────────────────┘
                   the docs explicitly forbid wrapping ng-content in @if/@for/@switch:
                   the content is created regardless and the condition merely hides it
```

This is the first fork people get wrong: `ng-content` looks like the universal answer, but it has two hard limits — the content is **always created**, and it cannot receive data from the host component. As soon as you need to "render a row per ticket" or "create the content only when opened", you are looking at `ng-template` or dynamic creation.

### ng-content and slots

```
        what the consumer writes               where it lands in the panel template
┌─────────────────────────────────────┐    ┌──────────────────────────────────────────┐
│ <app-panel>                         │    │ <header>                                 │
│   <h2 panel-title>Tickets</h2>      │    │   <ng-content select="[panel-title]" />  │
│   <button panel-action>New</button> │    │   <ng-content select="[panel-action]" /> │
│   <p>Today's list</p>               │    │ </header>                                │
│ </app-panel>                        │    │ <div class="body">                       │
└─────────────────────────────────────┘    │   <ng-content>No data</ng-content>       │
 ngProjectAs lets content reach a slot     │ </div>                                   │
 without reshaping it for the selector     └──────────────────────────────────────────┘
                                           an ng-content with no select takes the rest;
                                               text inside the tag is the fallback
```

The mechanics: `<ng-content>` is not an element but a **compiler instruction** telling Angular where to place the content the consumer passed in. Consequences:

- `select` takes ordinary CSS selectors (`[panel-title]`, `h2`, `.actions`). An `ng-content` without `select` collects whatever did not match; if no such slot exists, the extra content simply never renders.
- The tag's body can hold **fallback content** — shown when the consumer passed nothing into that slot.
- `ngProjectAs="[panel-title]"` lets an element reach a slot it does not match — an `<ng-container>` or a wrapper component, for instance. The value is static; binding is not allowed.
- Projected content belongs to the **consumer**: its expressions are evaluated in the parent's context, its styles are the parent's (chapter 01), and it sees the host's `providers` but not its `viewProviders` (chapter 04).
- The documentation states the limitation outright: "Angular always instantiates and creates DOM nodes for content rendered to a `<ng-content>` placeholder, even if that `<ng-content>` placeholder is hidden", and "You should not conditionally include `<ng-content>` with `@if`, `@for`, or `@switch`". Hiding it is possible; not creating it is not.

### ng-template + ngTemplateOutlet: the render-props analogue

When the content needs data from the component (a table row knows its ticket) or must be created later, you pass a **template**:

```html
<!-- the consumer describes how to draw a cell and receives the data back -->
<app-data-table [rows]="tickets()">
  <ng-template #cell let-ticket let-column="column">
    @switch (column) {
      @case ('title') { <a [routerLink]="['/tickets', ticket.id]">{{ ticket.title }}</a> }
      @default { {{ ticket[column] }} }
    }
  </ng-template>
</app-data-table>
```

```html
<!-- inside the table: the template is inserted as many times as needed -->
@for (row of rows(); track row.id) {
  <tr>
    @for (column of columns(); track column) {
      <td>
        <ng-container
          [ngTemplateOutlet]="cellTemplate()"
          [ngTemplateOutletContext]="{ $implicit: row, column }"
        />
      </td>
    }
  </tr>
}
```

The context is an object; `$implicit` goes to the first unnamed `let` variable. The component receives the template through a signal query: `contentChild<TemplateRef<CellContext>>('cell')` (chapter 02).

For typing the context there is `ngTemplateContextGuard` — a static method declaring the context type (we met it in chapter 06 with structural directives). Without it `strictTemplates` cannot check `let-ticket`.

### ng-container

`<ng-container>` is a grouping element that never lands in the DOM. It is needed wherever a directive or block must be attached without adding a node: you cannot put a `<div>` inside `<tbody>`, but you can put an `ng-container`. It is also the usual carrier for `[ngTemplateOutlet]`.

### Creating components dynamically

When the component is chosen at runtime (a dialog, a settings panel per widget type, a plugin architecture), use `ViewContainerRef`:

```ts
private readonly host = viewChild.required('modalHost', { read: ViewContainerRef });

open<T>(component: Type<T>, inputs: Record<string, unknown>): ComponentRef<T> {
  const ref = this.host().createComponent(component);
  // setInput instead of ref.instance.x = ...: setInput marks the component
  // as changed, so an OnPush component sees the new value (chapter 03)
  for (const [key, value] of Object.entries(inputs)) ref.setInput(key, value);
  return ref;
}
```

Destruction is `ref.destroy()` or `viewContainerRef.clear()`. There is also the standalone `createComponent()` function from `@angular/core`, which needs an `EnvironmentInjector` — for cases with no convenient `ViewContainerRef` (rendering into an arbitrary DOM node, say).

Note two important details: a component created in a `ViewContainerRef` joins that container's **logical tree** (its change detection and DI) while physically being inserted as a sibling of the anchor element. And `setInput()` is the only correct way to pass inputs to a dynamic component.

### Angular CDK and @angular/aria

```
                   Angular CDK: what to take instead of writing your own
┌───────────────────────────────────────────────┬─────────────────────────────────────────┐
│ the task                                      │ the CDK primitive                       │
├───────────────────────────────────────────────┼─────────────────────────────────────────┤
│ a floating layer with positioning             │ overlay                                 │
├───────────────────────────────────────────────┼─────────────────────────────────────────┤
│ render a template/component elsewhere         │ portal                                  │
├───────────────────────────────────────────────┼─────────────────────────────────────────┤
│ focus trap, live announcements, focus monitor │ a11y                                    │
├───────────────────────────────────────────────┼─────────────────────────────────────────┤
│ dragging and reordering lists                 │ drag-drop                               │
├───────────────────────────────────────────────┼─────────────────────────────────────────┤
│ virtual scrolling for large lists             │ scrolling                               │
├───────────────────────────────────────────────┼─────────────────────────────────────────┤
│ table structure without styles                │ table                                   │
├───────────────────────────────────────────────┼─────────────────────────────────────────┤
│ a dialog with focus and roles                 │ dialog                                  │
├───────────────────────────────────────────────┼─────────────────────────────────────────┤
│ menu, listbox, tree, accordion, stepper       │ menu, listbox, tree, accordion, stepper │
├───────────────────────────────────────────────┼─────────────────────────────────────────┤
│ tests through harnesses, not markup           │ testing (chapter 13)                    │
└───────────────────────────────────────────────┴─────────────────────────────────────────┘
       @angular/aria (stable since v22) goes further with ready behaviour directives:
               accordion, combobox, grid, listbox, menu, tabs, toolbar, tree
```

The CDK is Angular Material without the styles: the behaviour and primitives Material itself is built on. The practical rule: **writing your own is justified for markup and styles, but not for behaviour that is easy to get wrong** — positioning floating layers within the viewport, trapping focus in a dialog, announcing changes to screen readers, virtual scrolling. Those are the classes of problem where a home-made version is almost always worse, and `@angular/aria` (stable since v22) additionally covers keyboard navigation for the common patterns.

## React parallels

- **`ng-content` ≈ `children`, but with fixed slots.** In React several "slots" become props (`header={<h2/>}`) or a `children` convention; in Angular they are `select` selectors. The difference is the cost of a mistake: content that matches no slot in Angular simply never renders, with no warning.
- **`ng-template` + `ngTemplateOutlet` = render props.** A direct analogy: `renderRow={(row) => <Cell/>}` in React versus a template with a context in Angular. The implementation differs: React passes a **function**, Angular passes a **compiled template** that a `ViewContainerRef` inserts. Hence typing the context through `ngTemplateContextGuard` instead of a function type.
- **Lazy content creation.** In React `{isOpen && <Heavy/>}` does not create `Heavy` until it opens — intuitive. In Angular the same trick with `ng-content` **does not work**: the content is created regardless. Laziness requires an `ng-template` (or `@defer` — chapter 12), and this mismatch catches nearly everyone.
- **A dynamic component.** In React `const C = map[type]; return <C/>` is enough — a component is a value. In Angular you need `ViewContainerRef.createComponent()` and `setInput()`, because a component is not a function but a description with metadata, and creating it goes through DI and change detection.
- **Where the habit breaks:** expecting content passed into a component to "belong" to it. It belongs to the parent: its expressions evaluate in the parent's context, its styles are scoped by the parent, and it resolves services from the host's `providers` but not from its `viewProviders`. That is why "my content cannot see the component's service" is not a bug but the `providers`/`viewProviders` distinction.

## What you will see in legacy code

- **`*ngTemplateOutlet` with an asterisk** — `<ng-container *ngTemplateOutlet="tpl; context: { $implicit: row }">`. It works but needs `CommonModule`; the modern form is the property binding `[ngTemplateOutlet]`.
- **`@ContentChild('cell') tpl!: TemplateRef<unknown>`** with `ngAfterContentInit` instead of a signal `contentChild()` (chapter 02): the value only appeared after the hook, and changes were tracked through `QueryList.changes`.
- **`ComponentFactoryResolver`:** `resolveComponentFactory(Cmp)` + `vcr.createComponent(factory)` — the pre-Angular-13 API. Factories are gone: `createComponent(Cmp)` takes the class directly.
- **`ref.instance.title = 'x'` + `ref.changeDetectorRef.detectChanges()`** instead of `ref.setInput('title', 'x')`: writing to the instance does not mark the component as changed, hence the manual check.
- **`entryComponents`** in an NgModule — the list of dynamically created components; required before Ivy, now removed.
- **Home-made dialogs on `document.body.appendChild`** with manual focus, scroll and `z-index` management — exactly what `cdk/overlay` and `cdk/a11y` with `FocusTrap` exist for.

## What we add to the project

Two reusable components: a `DataTable` (columns described by the consumer through templates — the render-props analogue) and a `Modal` (created dynamically, with a focus trap and Escape handling). Both must work with any data, not only with tickets.

## Exercise

**Input:** the project from chapter 10 (list, detail, form).
**Output:** a table and a modal that can be reused outside tickets.

Requirements:

1. `DataTable<T>`: inputs are the row array and a column description (`{ key, header }`). The consumer may supply a cell template receiving the row and the column key. The component must not know about `Ticket`: generics only.
2. Take the templates through a signal `contentChild`, type the context (`ngTemplateContextGuard`), and provide default behaviour when no template is passed.
3. Slots: the table needs slots for a title (`[table-title]`) and for actions (`[table-actions]`), plus fallback content for the empty state.
4. `Modal`: the content is created **only when opened** — that is, through an `ng-template` or `createComponent()`, never through `ng-content`. Explain in a comment why `@if` around `ng-content` would not do.
5. The modal must close on Escape and on an outside click, return focus to the trigger element afterwards, and keep focus inside the dialog. Implement it yourself, then note in a comment which CDK primitives would cover each point.
6. Dynamic creation: write an `open(component, inputs)` method that creates an arbitrary component inside the modal through `ViewContainerRef` and passes inputs via `setInput()`. Demonstrate it with the ticket form.
7. Constraint: no `any` in the generics and no direct writes to `ref.instance` for passing inputs.

Edge cases to think about:

- A consumer passed a heavy component inside `<ng-content>` and the table hides it with `@if`. How many times is the component created?
- The projected content tries to inject a service declared in the table's `viewProviders`. What happens?
- You inserted the same `TemplateRef` into two different `ngTemplateOutlet`s. How many view instances are created, and do they share state?
- A dynamic component was created with `createComponent()` and then the route changed. What happens to it if `destroy()` is never called?
- The modal needs Escape, but it is nested inside another modal. How do you avoid closing both with one keypress?

## Solution walkthrough

`src/app/ui/data-table.ts`:

```ts
import {
  Component,
  TemplateRef,
  contentChild,
  input,
} from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';

export interface TableColumn<T> {
  readonly key: keyof T & string;
  readonly header: string;
}

// The cell template's context type: what the consumer gets in let variables
export interface CellContext<T> {
  readonly $implicit: T;
  readonly column: string;
}

@Component({
  selector: 'app-data-table',
  imports: [NgTemplateOutlet],
  templateUrl: './data-table.html',
  styleUrl: './data-table.css',
})
export class DataTable<T extends { id: number | string }> {
  readonly rows = input.required<readonly T[]>();
  readonly columns = input.required<readonly TableColumn<T>[]>();

  // A signal contentChild: no ngAfterContentInit needed, updates itself.
  // The template is optional — without it we render the value as text
  readonly cellTemplate = contentChild<TemplateRef<CellContext<T>>>('cell');

  // A hint to the compiler about the context type: without it strictTemplates
  // will not check the expressions inside let-ticket (chapter 06)
  static ngTemplateContextGuard<T>(
    _dir: DataTable<T>,
    _ctx: unknown,
  ): _ctx is CellContext<T> {
    return true;
  }
}
```

`src/app/ui/data-table.html`:

```html
<section class="table">
  <header class="table__header">
    <!-- slots: a title and actions. The selectors are ordinary CSS attributes -->
    <ng-content select="[table-title]" />
    <div class="table__actions">
      <ng-content select="[table-actions]" />
    </div>
  </header>

  <table>
    <thead>
      <tr>
        @for (column of columns(); track column.key) {
          <th>{{ column.header }}</th>
        }
      </tr>
    </thead>
    <tbody>
      @for (row of rows(); track row.id) {
        <tr>
          @for (column of columns(); track column.key) {
            <td>
              @if (cellTemplate(); as tpl) {
                <!-- ng-container adds no DOM node: important inside a <td> -->
                <ng-container
                  [ngTemplateOutlet]="tpl"
                  [ngTemplateOutletContext]="{ $implicit: row, column: column.key }"
                />
              } @else {
                {{ row[column.key] }}
              }
            </td>
          }
        </tr>
      } @empty {
        <tr>
          <td [attr.colspan]="columns().length">
            <!-- fallback content: shown when the consumer passed
                 nothing into this slot -->
            <ng-content>No rows</ng-content>
          </td>
        </tr>
      }
    </tbody>
  </table>
</section>
```

Usage — the table knows nothing about tickets:

```html
<app-data-table [rows]="board.tickets()" [columns]="columns">
  <h2 table-title>Tickets</h2>
  <button table-actions type="button" (click)="modal.open()">New ticket</button>

  <!-- the render-props analogue: the consumer decides how to draw a cell
       and receives the row through let-ticket -->
  <ng-template #cell let-ticket let-column="column">
    @switch (column) {
      @case ('title') {
        <a [routerLink]="['/tickets', ticket.id]">{{ ticket.title }}</a>
      }
      @case ('createdAt') { {{ ticket.createdAt | date: 'short' }} }
      @default { {{ ticket[column] }} }
    }
  </ng-template>
</app-data-table>
```

`src/app/ui/modal.ts` — lazy content and dynamic components:

```ts
import {
  Component,
  ComponentRef,
  DestroyRef,
  ElementRef,
  Type,
  ViewContainerRef,
  inject,
  signal,
  viewChild,
} from '@angular/core';

@Component({
  selector: 'app-modal',
  templateUrl: './modal.html',
  styleUrl: './modal.css',
  host: {
    '[class.is-open]': 'isOpen()',
    // Escape is handled on the host rather than on document: a nested modal
    // receives the event first and stops propagation — so only it closes
    '(keydown.escape)': 'onEscape($event)',
  },
})
export class Modal {
  private readonly host = inject(ElementRef<HTMLElement>);

  // The container for dynamic components
  private readonly content = viewChild.required('content', { read: ViewContainerRef });

  private readonly open = signal(false);
  readonly isOpen = this.open.asReadonly();

  private lastFocused: HTMLElement | null = null;
  private currentRef: ComponentRef<unknown> | null = null;

  constructor() {
    // a safety net: if the modal is destroyed while open, clean up after ourselves
    inject(DestroyRef).onDestroy(() => this.currentRef?.destroy());
  }

  // Opening with an arbitrary component inside
  openWith<T>(component: Type<T>, inputs: Record<string, unknown> = {}): ComponentRef<T> {
    this.lastFocused = document.activeElement as HTMLElement | null;
    this.open.set(true);

    const container = this.content();
    container.clear();
    const ref = container.createComponent(component);

    // setInput, not ref.instance.x = …: only setInput marks the component as
    // changed, otherwise an OnPush component never sees the value (chapter 03)
    for (const [key, value] of Object.entries(inputs)) {
      ref.setInput(key, value);
    }

    this.currentRef = ref;
    return ref;
  }

  close(): void {
    this.open.set(false);
    // without destroy() the component would keep living: its subscriptions,
    // timers and httpResource would carry on working
    this.currentRef?.destroy();
    this.currentRef = null;
    this.content().clear();
    // focus returns to the element that opened it: an a11y requirement
    this.lastFocused?.focus();
  }

  protected onEscape(event: Event): void {
    if (!this.open()) return;
    event.stopPropagation();   // a nested modal will not close its parent
    this.close();
  }
}
```

`src/app/ui/modal.html`:

```html
@if (isOpen()) {
  <div class="modal__backdrop" (click)="close()"></div>

  <div class="modal__dialog" role="dialog" aria-modal="true">
    <header class="modal__header">
      <!-- static slots through ng-content: a title and buttons are cheap,
           creating them up front costs nothing -->
      <ng-content select="[modal-title]" />
      <button type="button" aria-label="Close" (click)="close()">×</button>
    </header>

    <!-- The content is created HERE and only while the modal is open.
         <ng-content> cannot do this: the documentation states that projected
         content is created regardless, even when hidden — a heavy form would
         initialize together with the page -->
    <div class="modal__body">
      <ng-container #content />
    </div>
  </div>
}
```

Opening the ticket form in the modal:

```ts
protected readonly modal = viewChild.required(Modal);

protected createTicket(): void {
  const ref = this.modal().openWith(TicketForm, { mode: 'create' });
  // a dynamic component's outputs are available as usual
  ref.instance.saved.subscribe(() => this.modal().close());
}
```

What the CDK would have covered here: `cdk/overlay` — creating the layer, positioning and the backdrop; `cdk/a11y` (`FocusTrap`, `cdkTrapFocus`) — keeping focus inside the dialog, which this solution lacks; `cdk/portal` — inserting a template or component into the layer; `cdk/dialog` — all of the above plus roles and focus restoration. A home-made version makes sense as an exercise; in a project with more than one dialog, `cdk/dialog` is cheaper.

Answers to the edge cases:

- Once — and immediately, when the table is created. `@if` around `ng-content` only hides nodes that already exist: projected content is always instantiated. So a heavy component inside a slot is a cost you pay whether the slot is shown or not; laziness requires an `ng-template`.
- It will not find it: `viewProviders` are visible only to the component's own template, and projected content belongs to the parent. It will resolve the dependency from the table's `providers` (if declared there) or continue up the injector hierarchy (chapter 04). If the table's service must be available to the content, declare it in `providers`, not `viewProviders`.
- Two independent embedded views. A `TemplateRef` is a "recipe", not an instance: each insertion creates its own nodes and its own state (its own `@let` values, its own component instances inside). All they share is what arrives through the context and from the parent component.
- It keeps existing: a `ViewContainerRef` does not destroy the components it created, and a component created imperatively is not tied to the route's lifetime. Its `effect`s, subscriptions and `httpResource` keep running — a textbook leak. Hence `destroy()` in `close()` plus the `DestroyRef` safety net in the constructor.
- Handle `Escape` on the **modal's host** rather than on `document`, and stop propagation. Then the inner modal (deeper in the tree) receives the event first, closes itself, and never lets it reach the outer one. With `document` listeners you would have to maintain a stack of open dialogs — which is exactly what `cdk/overlay` does.

## Check yourself

1. Why does `@if` around `<ng-content>` not give you lazy content creation, and what should you use instead?
2. How does `ng-template` + `ngTemplateOutlet` differ from `ng-content` in terms of passing data, and which React technique does it mirror?
3. Who "owns" projected content — the parent or the host component? Give two consequences of that fact.
4. Why is `setInput()` needed when creating a component dynamically, and what happens if you write to `ref.instance` directly?
5. What would you delegate to the CDK and what would you write yourself when building a custom dropdown? Justify the boundary.

<details>
<summary>Answers</summary>

1. Because `<ng-content>` is not an element you can create or skip but a compiler instruction about where to place content that already exists. The documentation says it plainly: nodes for projected content are always created, even when the placeholder is hidden, and `ng-content` should not be wrapped in `@if`/`@for`/`@switch`. The condition merely hides the result, while constructors, `effect`s and requests have already run. For genuine laziness the content is passed as an `ng-template` and inserted through `ngTemplateOutlet` (or a `ViewContainerRef`) at the right moment — or `@defer` is used (chapter 12) when the goal is deferring the code itself.
2. `ng-content` relocates ready-made markup with no way to pass anything into it: its expressions evaluate in the parent's context. `ng-template` passes a **description** of markup that the component inserts itself, together with a context — an object whose fields land in `let` variables (`$implicit` in the first unnamed one). This is the direct analogue of render props (`renderRow={(row) => …}`): the consumer describes "how to draw", the component decides "how many times and with what data". The difference from React is that what is passed is a compiled template rather than a function, so the context is typed through `ngTemplateContextGuard`.
3. The parent. The content is declared in the parent's template, therefore: (a) expressions inside evaluate in the parent's context and are checked when **its** template is checked — the host cannot inject its own values there except through an `ng-template` with a context; (b) styles are scoped by the parent (the parent component's `_ngcontent` attribute), so the host's CSS does not apply; (c) in DI the content sees the host's `providers` but **not** its `viewProviders`. It also follows that the content's lifecycle is tied to the parent, and the host's `ngAfterContentInit` fires after it has been created.
4. `setInput()` not only writes the value but also marks the component as changed and schedules a check — that is, it does what a `[x]="…"` binding in a template would. A direct `ref.instance.title = 'x'` changes the field, but the framework never learns about it: with an `OnPush` component (the default since v22) the template is not re-checked and the old value stays on screen. Writing to the instance also bypasses input `transform`s and, in older code, `ngOnChanges`. Practically: `setInput()` is the only correct way; a manual write requires `markForCheck`/`detectChanges` and still breaks the input contract.
5. Delegate the behaviour that is easy to get wrong: `overlay` — creating the layer, positioning relative to the trigger while respecting viewport edges and scrolling, the backdrop; `a11y` — focus trap, `FocusMonitor`, screen-reader announcements; `listbox`/`menu` — keyboard navigation, `aria-activedescendant`, typed selection; and if you like, `@angular/aria` provides ready `combobox`/`listbox` directives. Write yourself the markup, styles, animations and domain logic: what an option looks like, how the list is filtered, where the data comes from, what counts as selected. The boundary is simple: anything describable as "correct behaviour per the standard" comes from a library; anything describable as "how this looks and what it means in our product" you write.

</details>

## Common mistake

The first is trying to get lazy content through `@if` around `<ng-content>`. The React model suggests `{isOpen && children}` does not create the children while the condition is false; in Angular the content is created regardless and the condition only hides the DOM. The symptom is distinctive: the modal is closed, yet the form inside has already requested its reference data, its `effect`s are running, and the Network tab shows calls the user never triggered. Sometimes it is caught even earlier — by a console error from a component that "should not exist yet". The right path: content that must appear on demand is passed as an `ng-template` and inserted with `ngTemplateOutlet`/`ViewContainerRef` at open time, while deferring the *code* is `@defer`'s job (chapter 12).

The second is a dynamic component without `destroy()`. You created it with `createComponent()`, showed it, closed the modal by "hiding" it — and left the instance alive. It remains part of change detection, its subscriptions and `httpResource` keep working, its polling keeps hitting the network, and reopening puts a second copy next to it. The leak accumulates quietly: the application simply grows heavier. The rule: every `createComponent()` has a matching `destroy()` (or a `clear()` on the container), and it is worth adding a `DestroyRef.onDestroy()` safety net — as in the walkthrough. The same principle explains why `@if` beats "hiding with CSS": removing a view destroys the components inside it along with all their state.
