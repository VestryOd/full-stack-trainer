# Forms

## Theory

### Reactive Forms: the form as an object

The primary tool for forms in Angular is Reactive Forms. The form is described in the class as a tree of objects, and the template merely binds to it.

```ts
private readonly fb = inject(FormBuilder);

// nonNullable removes null from the type: without it you get
// FormControl<string | null>, because reset() returns the control to null
protected readonly form = this.fb.nonNullable.group({
  title: this.fb.nonNullable.control('', {
    validators: [Validators.required, Validators.maxLength(120)],
  }),
  priority: this.fb.nonNullable.control<TicketPriority>('medium'),
  // updateOn: 'blur' — value and validation update when focus is lost
  // rather than on every keystroke: cheaper and calmer for UX
  email: this.fb.nonNullable.control('', {
    validators: [Validators.email],
    updateOn: 'blur',
  }),
  tags: this.fb.array<FormControl<string>>([]),
});
```

Typing here is not cosmetic: `form.value` is inferred from the structure, so a typo in a field name is a compile error. One important subtlety: for a group with disabled controls, `form.value` is typed `Partial<...>` and **excludes** the disabled fields; the full value comes from `getRawValue()`.

Three classes make up a form: `FormControl` (one value), `FormGroup` (an object with fixed keys), `FormArray` (a dynamic list — tags, order lines, participants).

### Control states and error UX

Error UX (user experience — what the user actually sees and feels) rests on five control flags. Show an error when `invalid` **and** (`touched` **or** the form was submitted): otherwise fields turn red before the user has typed anything.

| state | becomes true when | what to do with it |
|---|---|---|
| `touched` | the field lost focus | the main trigger for showing errors |
| `dirty` | the user changed the value | the unsaved-changes warning |
| `pending` | async validation is running | a spinner on the field, block submit |
| `invalid` | a validator returned an error | the error exists, but do not show yet |
| `disabled` | `control.disable()` | the value drops out of `form.value` |

The main point: **`invalid` is not a reason to show an error**. An empty required field is invalid from the very start, but it must not turn red as the form loads. The standard formula is `invalid && (touched || submitted)`, where `submitted` is a signal of your own, set when submission is attempted. A `FormGroup` has no "submitted" flag: the `ngForm` directive does, but it is rarely used with Reactive Forms.

### Validators

A synchronous validator is a function `(control) => ValidationErrors | null`. An asynchronous one returns a `Promise` or an `Observable` and puts the control into `pending`. Cross-field validation goes on the **group**, not on a field, because it needs both values:

```ts
export function slaWithinPriority(group: AbstractControl): ValidationErrors | null {
  const priority = group.get('priority')?.value as TicketPriority | undefined;
  const sla = group.get('slaHours')?.value as number | null;
  if (priority !== 'urgent' || sla === null) return null;
  return sla <= 4 ? null : { slaTooLongForUrgent: { max: 4, actual: sla } };
}
```

The error then lives on the group rather than on a field. So you have to deliberately surface it next to the relevant control. This is a classic source of "the validation exists but the user never sees it".

### Writing values

A value can be written into the form in several ways, and each one has its own gotcha.

| call | what it does | the gotcha |
|---|---|---|
| `setValue(v)` | requires every field of the group | a missing field throws at runtime |
| `patchValue(v)` | updates only what you passed | a typo in a key goes unnoticed |
| `reset(v)` | value plus `touched`/`dirty` reset | it resets validation statuses too |
| `{ emitEvent: false }` | does not emit `valueChanges` | dependent logic never runs |
| `form.value` | excludes disabled fields | you need `getRawValue()` |

One thing to note about zoneless: `setValue`/`patchValue` do **not** schedule a template check themselves. Mirror form state into signals or call `markForCheck`. This is what chapter 03 warned about, and one of the few things that genuinely break when moving to zoneless.

Here is the machinery. `setValue`/`patchValue` change form state and emit their Observables, but they do not schedule a template check. As long as values are read by the directives (`formControlName`), you never notice — the binding machinery updates them.

But if the template reads `form.valid`, `control.errors` or `form.value` directly, the markup may stay stale after a programmatic write.

The practical fix is not to read form state in the template directly but to mirror it into signals:

```ts
// events (v18+) provides one stream of value, status and touched changes
private readonly formEvents = toSignal(this.form.events, { initialValue: null });

// signals the template can safely rely on
protected readonly isInvalid = computed(() => {
  this.formEvents();               // a dependency: recompute on any form event
  return this.form.invalid;
});
```

### ControlValueAccessor: your own control

For a component of yours to work inside Reactive Forms (`formControlName`, validators, `touched`), it must implement `ControlValueAccessor` — a contract of four methods:

```ts
@Component({
  selector: 'app-priority-picker',
  providers: [
    // NG_VALUE_ACCESSOR is a multi token (chapter 04): this is how forms find
    // the control. forwardRef is needed because the class is not defined yet
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => PriorityPicker),
      multi: true,
    },
  ],
  template: `…`,
})
export class PriorityPicker implements ControlValueAccessor {
  protected readonly value = signal<TicketPriority>('medium');
  protected readonly disabled = signal(false);

  private onChange: (value: TicketPriority) => void = () => {};
  private onTouched: () => void = () => {};

  // form → component
  writeValue(value: TicketPriority | null): void {
    this.value.set(value ?? 'medium');
  }
  // component → form
  registerOnChange(fn: (value: TicketPriority) => void): void { this.onChange = fn; }
  registerOnTouched(fn: () => void): void { this.onTouched = fn; }
  setDisabledState(isDisabled: boolean): void { this.disabled.set(isDisabled); }

  protected select(priority: TicketPriority): void {
    this.value.set(priority);
    this.onChange(priority);   // without this the form never learns the value
    this.onTouched();          // without this there is no touched, hence no errors
  }
}
```

Forgetting `onTouched()` is the most common bug in custom controls: the value arrives but errors never show, because `touched` never becomes `true`.

### Signal Forms: where the framework is heading

Since v22 Angular ships a second, signal-based forms API (`@angular/forms/signals`, `@publicApi 22.0`). The idea is fundamentally different: **the source of truth is your data signal**, and the form merely wraps it in a tree of fields.

```ts
import {
  form,
  schema,
  submit,
  required,
  minLength,
  min,
  validate,
} from '@angular/forms/signals';

// 1. the model is an ordinary signal
private readonly model = signal({
  title: '',
  priority: 'medium' as TicketPriority,
  slaHours: 4,
});

// 2. rules are described by a schema over the model
private readonly rules = schema<TicketDraft>((path) => {
  required(path.title, { message: 'Title is required' });
  minLength(path.title, 5);
  min(path.slaHours, 1);
  // a cross-field check: the rule sees the whole value
  validate(path, ({ value }) =>
    value().priority === 'urgent' && value().slaHours > 4
      ? { kind: 'slaTooLong', message: 'Urgent tickets need SLA ≤ 4h' }
      : null,
  );
});

// 3. the form is model plus schema
protected readonly ticketForm = form(this.model, this.rules);

// 4. submission: server errors returned from the action land on the fields
protected async save(): Promise<void> {
  await submit(this.ticketForm, {
    action: async (f) => this.api.create(f().value()),
  });
}
```

```html
<form [formRoot]="ticketForm">
  <input [formField]="ticketForm.title" />
  @for (error of ticketForm.title().errors(); track error.kind) {
    <p class="error">{{ error.message }}</p>
  }
</form>
```

What matters here:

- the data is never copied into the form: `form()` writes straight into your signal;
- rules are separated from structure and reusable through `schema()`;
- field state (`value`, `errors`, `touched`, `disabled`, `pending`) consists of signals.

There are many ready-made rules: `required`, `min`/`max`, `minLength`/`maxLength`, `email`, `pattern`, `validate`, `validateAsync`, `validateHttp`, `validateTree`. There is integration with Standard Schema (zod, valibot), plus `disabled`, `hidden`, `readonly` and `debounce`. Structural helpers are `apply`, `applyEach`, `applyWhen`, `applyWhenValue`.

A custom control implements the **interface** `FormValueControl<T>` (or `FormCheckboxControl`). So `ControlValueAccessor` with its four methods is no longer needed.

The two approaches side by side, row by row:

| the task | Reactive Forms | Signal Forms (v22) |
|---|---|---|
| source of truth | the `FormGroup` itself | your data signal |
| creation | `new FormGroup({...})` | `form(model)` |
| template binding | `[formGroup]` + `formControlName` | `[formRoot]` + `[formField]` |
| a validator | `Validators.required` on a control | `required(path)` in a schema |
| reading errors | `control.errors?.[key]` | `field().errors()` |
| a custom control | `ControlValueAccessor` | the `FormValueControl<T>` interface |
| submitting | `form.valid` + your own submit | `submit(form, { action })` |

The course's practical stance: **the project uses Reactive Forms**. The reasons are pragmatic. They are what you will meet in existing projects and what interviews ask about. Every component library is built around them, and years of use have proved them.

Signal Forms are worth knowing and trying. The API is stable, the direction is obvious, and migration one form at a time is possible thanks to the compatibility layer in the package.

### Template-driven — an overview

The third option: `[(ngModel)]` plus `name` inside a `<form>`, where the `ngForm` directive assembles the form and validators are attributes (`required`, `minlength`). The upside is minimal code for trivial forms.

The downsides, which keep it from being the main tool:

- the form's structure is implicit — it is not in the class;
- typing is weak;
- programmatic control is awkward;
- async and cross-field validation take ingenuity.

Rare in new code — but not extinct, so `#form="ngForm"` and `form.controls['title'].errors` are worth recognizing.

## React parallels

- **Who owns the state.** In React form state almost always lives in the component: `useState`, or `react-hook-form` with its `register`. In Reactive Forms the owner is the `FormGroup` object itself. It has its own tree, its own statuses and its own validation, and the component only holds a reference. Hence the feeling that "Angular forms are heavier": it is a separate model with its own API rather than a state variable.
- **react-hook-form is closer to Signal Forms.** React Hook Form keeps data outside the render and registers fields through `register`. Signal Forms does the same, except the source is a signal and the fields are a tree over it. Even validation is similar: a schema (zod) over the model instead of validators scattered across fields.
- **Showing errors.** In React you usually decide for yourself: `formState.errors` plus `isSubmitted`. Angular hands you ready flags on every control: `touched`, `dirty`, `pending`. But the display rule is still yours, because `invalid` alone does not mean "show the error".
- **A custom control.** In React it is a component with `value`/`onChange` props — that is all. In Angular it needs a contract: `ControlValueAccessor` with four methods and an `NG_VALUE_ACCESSOR` provider. More ceremony, but the control inherits the whole forms infrastructure — validation, statuses, `disabled`, integration with `formControlName`. Signal Forms cut the ceremony: implementing an interface is enough.
- **Where the habit breaks:** trying to keep form values in separate signals and "synchronize" them with the `FormGroup`. That creates two sources of truth and endless drift. The correct direction is the opposite. The `FormGroup` is the source, and what the template needs (validity, errors) is mirrored into signals via `form.events` and `toSignal`.

## What you will see in legacy code

- **Untyped forms:** before Angular 14 `new FormGroup({ title: new FormControl('') })` had no types, so `form.value.titel` compiled fine. Hence `UntypedFormGroup`/`UntypedFormControl` in migrated projects — a marker that typing was never finished.
- **`FormBuilder` without `nonNullable`:** `this.fb.group({ title: [''] })` yields `FormControl<string | null>` and `null` spreads through the code. The modern form is `fb.nonNullable.group(...)`.
- **`valueChanges.subscribe()` with manual teardown** and "field A changes field B" logic inside the subscription. Today that is `takeUntilDestroyed()` (chapter 09) or `form.events` — and better still, a validation rule instead of imperative synchronization.
- **`ngModel` together with Reactive Forms:** `[(ngModel)]` on a control that already has `formControlName`. That combination was deprecated and removed; seeing it means the form was half-rewritten.
- **`markAsTouched()` in a loop over all controls** before submitting, often through a home-made recursive `markAllAsTouched` — `AbstractControl` has had a built-in `markAllAsTouched()` for a while.
- **`Validators.compose([...])`** and validator classes (`@Directive` with `NG_VALIDATORS`) where a plain function would do.

## What we add to the project

The create/edit ticket form. SLA (service level agreement) here means the response time the team is committed to. It is the `slaHours` field of the ticket model.

Inside the form:

- a typed `FormGroup` with validators;
- the cross-field rule "urgent requires SLA ≤ 4h";
- an async uniqueness check on the title;
- a `FormArray` for tags;
- a custom priority control on `ControlValueAccessor`.

Plus the same screen sketched with Signal Forms, for comparison.

## Exercise

**Input:** the project from chapter 09 (the HTTP layer, search, polling).
**Output:** a working create/edit form with validation and a custom control.

Requirements:

1. A typed form with five fields: `title` (required, 5–120 characters), `priority` (a union type), `assignee` (string or `null`), `slaHours` (number, 1–72). Plus `tags`, a `FormArray` of strings with add and remove. No `UntypedFormGroup`, no `any`, and `null` only where it is meaningful.
2. Cross-field validation on the group: if `priority === 'urgent'` then `slaHours ≤ 4`. The error must appear next to the SLA field even though it lives on the group — work out how.
3. An async validator: the title must not duplicate an existing ticket (a request to `/api/tickets?q=`). Account for `pending` in the interface and do not fire a request on every keystroke.
4. Error UX: an error appears only when `invalid && (touched || submitted)`. The submit button is disabled while `invalid` or `pending`, but the first attempt to submit an invalid form must mark every field as `touched`.
5. A custom `PriorityPicker` control on `ControlValueAccessor`: works through `formControlName`, supports `disabled`, and marks `touched` correctly.
6. Edit mode: the same component is filled with an existing ticket's data. Decide between `setValue` and `patchValue` and justify it. Do not forget `tags` — the array has to be rebuilt.
7. Mirror form state into the template through signals (`form.events` + `toSignal`) rather than reading `form.invalid` directly — and explain why that matters specifically in zoneless.
8. Bonus: rewrite the same form with Signal Forms in a separate component and compare the amount of code and the places that required thought.

Edge cases to think about:

- You called `setValue({ title: 'x' })` on a group of five fields. What happens?
- The `assignee` control is disabled (`disable()`). What does `form.value` return, and how do you get the full value?
- The async validator is still running and the user clicks "Save". What does `form.valid` say, and how do you handle it?
- `reset()` is called after a successful save. What happens to `touched`, `dirty` and the errors — and what does the user see?
- The template reads `form.controls.title.errors`. Why might that not be enough to update the markup in zoneless?

## Solution walkthrough

`src/app/tickets/ticket-form.ts` — the main form:

```ts
import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import {
  AbstractControl,
  FormBuilder,
  FormControl,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { debounceTime, first, map, of, switchMap } from 'rxjs';
import { TicketApi } from './ticket-api';
import { PriorityPicker } from './priority-picker';
import { TicketPriority } from './ticket';

@Component({
  selector: 'app-ticket-form',
  imports: [ReactiveFormsModule, PriorityPicker],
  templateUrl: './ticket-form.html',
})
export class TicketForm {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(TicketApi);

  // nonNullable: without it every control would be FormControl<string | null>,
  // because reset() returns the value to null
  protected readonly form = this.fb.nonNullable.group(
    {
      title: this.fb.nonNullable.control('', {
        validators: [
          Validators.required,
          Validators.minLength(5),
          Validators.maxLength(120),
        ],
        asyncValidators: [this.uniqueTitle()],
        // validate on blur: otherwise the async validator fires per keystroke
        updateOn: 'blur',
      }),
      priority: this.fb.nonNullable.control<TicketPriority>('medium'),
      assignee: this.fb.control<string | null>(null),
      slaHours: this.fb.nonNullable.control(4, {
        validators: [Validators.required, Validators.min(1), Validators.max(72)],
      }),
      tags: this.fb.nonNullable.array<FormControl<string>>([]),
    },
    // the cross-field validator lives on the group: it needs two values
    { validators: [slaWithinPriority] },
  );

  // Our own "the user tried to submit" flag: a FormGroup has none
  private readonly submitted = signal(false);

  // form.events (v18+) is one stream of value, status and touched changes.
  // Through it form state reaches signals, and therefore the template
  private readonly formEvents = toSignal(this.form.events, { initialValue: null });

  protected readonly isInvalid = computed(() => {
    this.formEvents();                       // depend on any form event
    return this.form.invalid;
  });
  protected readonly isPending = computed(() => {
    this.formEvents();
    return this.form.pending;
  });
  protected readonly slaError = computed(() => {
    this.formEvents();
    // the error lives on the group but must be shown next to the SLA field
    return this.form.errors?.['slaTooLongForUrgent'] as { max: number } | undefined;
  });

  // Show an error rather than merely "being invalid"
  protected showError(controlName: keyof typeof this.form.controls): boolean {
    this.formEvents();
    const control = this.form.controls[controlName];
    return control.invalid && (control.touched || this.submitted());
  }

  protected addTag(): void {
    this.form.controls.tags.push(this.fb.nonNullable.control(''));
  }

  protected removeTag(index: number): void {
    this.form.controls.tags.removeAt(index);
  }

  protected save(): void {
    this.submitted.set(true);

    if (this.form.pending) return;           // wait for async validation
    if (this.form.invalid) {
      // without this the user cannot see what exactly is wrong
      this.form.markAllAsTouched();
      return;
    }

    // getRawValue(), not value: disabled fields must reach the request
    this.api.create(this.form.getRawValue()).subscribe(/* … */);
  }

  // The async validator as a factory method: it closes over api and debounce
  private uniqueTitle() {
    return (control: AbstractControl) =>
      of(control.value as string).pipe(
        debounceTime(300),
        switchMap((title) => this.api.list({ q: title })),
        map((tickets) => (tickets.length > 0 ? { titleTaken: true } : null)),
        // a validator must complete, or the control stays pending forever
        first(),
      );
  }
}

// The cross-field validator is a plain function over the group
function slaWithinPriority(group: AbstractControl): ValidationErrors | null {
  const priority = group.get('priority')?.value as TicketPriority | undefined;
  const sla = group.get('slaHours')?.value as number | undefined;
  if (priority !== 'urgent' || sla === undefined) return null;
  return sla <= 4 ? null : { slaTooLongForUrgent: { max: 4, actual: sla } };
}
```

`src/app/tickets/ticket-form.html`:

```html
<form [formGroup]="form" (ngSubmit)="save()">
  <label>
    Title
    <input type="text" formControlName="title" />
  </label>
  @if (showError('title')) {
    @let errors = form.controls.title.errors;
    <p class="error">
      @if (errors?.['required']) { Title is required }
      @else if (errors?.['minlength']) { At least 5 characters }
      @else if (errors?.['titleTaken']) { A ticket with this title already exists }
    </p>
  }
  @if (form.controls.title.pending) {
    <p class="hint">Checking for duplicates…</p>
  }

  <!-- the custom control behaves like any other: through formControlName -->
  <app-priority-picker formControlName="priority" />

  <label>
    SLA, hours
    <input type="number" formControlName="slaHours" />
  </label>
  <!-- a group-level error surfaced next to the relevant field -->
  @if (slaError(); as sla) {
    <p class="error">Urgent tickets need SLA ≤ {{ sla.max }}h</p>
  }

  <fieldset formArrayName="tags">
    <legend>Tags</legend>
    @for (tag of form.controls.tags.controls; track $index) {
      <div>
        <input type="text" [formControlName]="$index" />
        <button type="button" (click)="removeTag($index)">Remove</button>
      </div>
    }
    <button type="button" (click)="addTag()">Add tag</button>
  </fieldset>

  <button type="submit" [disabled]="isInvalid() || isPending()">Save</button>
</form>
```

Edit mode — filling in existing data:

```ts
readonly ticket = input<Ticket | null>(null);

constructor() {
  // an effect is appropriate: this is reaching out to an external
  // (non-signal) system — the form object. A derived value would not fit here
  effect(() => {
    const ticket = this.ticket();
    if (ticket === null) return;

    // patchValue, because we do not fill every field (tags are rebuilt below)
    this.form.patchValue({
      title: ticket.title,
      priority: ticket.priority,
      assignee: ticket.assignee,
      slaHours: ticket.slaHours ?? 4,
    });

    // a FormArray cannot be "patched" with a list: controls must be rebuilt
    const tags = this.form.controls.tags;
    tags.clear();
    for (const tag of ticket.tags ?? []) {
      tags.push(this.fb.nonNullable.control(tag));
    }
  });
}
```

`src/app/tickets/priority-picker.ts` — the custom control:

```ts
@Component({
  selector: 'app-priority-picker',
  providers: [
    // a multi token: this is how ReactiveFormsModule finds the implementation
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => PriorityPicker),
      multi: true,
    },
  ],
  template: `
    @for (option of options; track option) {
      <button
        type="button"
        [class.is-active]="value() === option"
        [disabled]="isDisabled()"
        (click)="select(option)"
      >
        {{ option }}
      </button>
    }
  `,
})
export class PriorityPicker implements ControlValueAccessor {
  protected readonly options: readonly TicketPriority[] = [
    'low', 'medium', 'high', 'urgent',
  ];
  protected readonly value = signal<TicketPriority>('medium');
  protected readonly isDisabled = signal(false);

  private onChange: (value: TicketPriority) => void = () => {};
  private onTouched: () => void = () => {};

  writeValue(value: TicketPriority | null): void {
    this.value.set(value ?? 'medium');
  }
  registerOnChange(fn: (value: TicketPriority) => void): void { this.onChange = fn; }
  registerOnTouched(fn: () => void): void { this.onTouched = fn; }
  setDisabledState(isDisabled: boolean): void { this.isDisabled.set(isDisabled); }

  protected select(priority: TicketPriority): void {
    this.value.set(priority);
    this.onChange(priority);
    // Without onTouched() the control never becomes touched — and errors
    // tied to touched never show. The most common bug
    // in ControlValueAccessor implementations
    this.onTouched();
  }
}
```

The same screen with Signal Forms, for comparison:

```ts
import {
  form,
  schema,
  submit,
  required,
  minLength,
  min,
  max,
  validate,
} from '@angular/forms/signals';

@Component({
  selector: 'app-ticket-form-signals',
  imports: [FormRoot, FormField],
  templateUrl: './ticket-form-signals.html',
})
export class TicketFormSignals {
  private readonly api = inject(TicketApi);

  // The model is an ordinary signal and is the source of truth.
  // form() copies nothing: writing to a field writes into this signal
  private readonly model = signal<TicketDraft>({
    title: '',
    priority: 'medium',
    assignee: null,
    slaHours: 4,
  });

  // Rules are separate from structure and reusable
  private readonly rules = schema<TicketDraft>((path) => {
    required(path.title, { message: 'Title is required' });
    minLength(path.title, 5);
    min(path.slaHours, 1);
    max(path.slaHours, 72);
    validate(path, ({ value }) =>
      value().priority === 'urgent' && value().slaHours > 4
        ? { kind: 'slaTooLong', message: 'Urgent tickets need SLA ≤ 4h' }
        : null,
    );
  });

  protected readonly ticketForm = form(this.model, this.rules);

  protected async save(): Promise<void> {
    // submit blocks re-submission itself and distributes server errors
    // across the fields when the action returns them
    await submit(this.ticketForm, { action: async (f) => this.api.create(f().value()) });
  }
}
```

The difference in volume is noticeable: no `FormBuilder`, no `getRawValue()`, no separate `submitted`. And since field state consists of signals already, the `form.events`/`toSignal` layer is unnecessary.

Answers to the edge cases:

- `setValue` requires a value for **every** control in the group: an incomplete object throws at runtime (`Must supply a value for form control with name: …`). For partial updates there is `patchValue`, but it carries the opposite danger. An unknown or misspelled key is silently ignored, so "why is this field empty" has to be found by eye.
- `form.value` excludes disabled controls and is typed `Partial`. The full value (including disabled fields) comes from `form.getRawValue()`. That is exactly why `save()` uses `getRawValue()`: otherwise a field disabled by a business rule would simply never reach the server.
- While the async validator runs, the control's status is `pending` and `form.valid` is **`false`** (validity is not known yet). So checking `if (form.invalid)` is not enough, because `pending` needs its own handling. Either disable the button, or wait for completion — `form.statusChanges` until the first non-`pending` status — and only then submit.
- `reset()` returns values to their initial (or supplied) state, clears `touched`/`dirty` and re-runs validation: the form becomes "untouched" again. The user sees a clean form without red highlights — which is correct after a successful save. But calling `reset()` on a server error would also wipe the data the user typed: there, keep the values and show a message instead.
- Because `setValue`/`patchValue` do not schedule a template check in zoneless. As long as the value is read by the `formControlName` directive, the binding machinery handles the update. But the expression `form.controls.title.errors` in a template is only evaluated when that template is checked. If nobody requested a check, the markup stays as it was. Hence the approach in the walkthrough: form state is mirrored into signals via `form.events` + `toSignal`. The template then depends on the signals rather than on the form object directly.

## Check yourself

1. Why is `invalid` a poor criterion for showing an error, and what formula replaces it?
2. What is the difference between `setValue` and `patchValue`, and what is the danger of each?
3. Why is a cross-field validator attached to the group rather than to a field, and what problem does that create in the markup?
4. What does `ControlValueAccessor` do, and why does a forgotten `onTouched()` call lead to "the form shows no errors"?
5. How does the Signal Forms model differ fundamentally from Reactive Forms — and why is `ControlValueAccessor` unnecessary there?

<details>
<summary>Answers</summary>

1. `invalid` is true from the moment the form is created: an empty required field is invalid before the user has even seen it. Showing errors then is bad UX (the form greets the user in red). What you need is a sign that "the user has already dealt with this field or tried to submit". The formula is `invalid && (touched || submitted)`. The `touched` flag comes from the control itself on blur, and `submitted` is your own signal, because a `FormGroup` has no such flag. When submitting an invalid form you additionally call `markAllAsTouched()` so every error appears at once.
2. `setValue` replaces the value wholesale and requires **all** controls of the group: a missing field throws at runtime. `patchValue` updates only the fields you passed. The dangers mirror each other. `setValue` breaks when the form's structure changes: add a field and every call breaks. And `patchValue` **silently ignores** unknown keys, so a typo in a field name produces neither an error nor a warning. The field simply stays empty. In practice: `patchValue` for partial updates and filling from an API, `setValue` when you deliberately set the entire form state.
3. A cross-field rule depends on several controls by definition, while a validator receives only the control it is attached to. So it goes on the common parent — the group — where both values are reachable. The markup problem: the result lands in `group.errors` rather than in a specific field's `errors`. The usual "show this control's errors" template never sees it. There are two fixes. Surface the group error deliberately next to the field the user must correct, as `slaError()` does in the walkthrough. Or mirror it onto the field with a separate validator.
4. `ControlValueAccessor` is the contract between your component and the forms machinery, and it has four methods. The method `writeValue` goes form → component. Then `registerOnChange` lets the component report a new value to the form. Next, `registerOnTouched` reports interaction. And the fourth is `setDisabledState`. If `onTouched()` is never called, the control never becomes `touched`. Error display is usually tied to `touched`, so the user sees no errors for that field even though `invalid` is true. The symptom is recognizable: "errors show up in every field except my custom one".
5. In Reactive Forms the source of truth is the `FormGroup` object itself. The data lives inside the form, and the component reaches it through the controls' API. In Signal Forms the source of truth is **your model signal**, and `form(model)` only builds a tree of fields and rules over it. Writing to a field writes straight into the signal, and no copy of the data exists. That is also why a custom control needs no `ControlValueAccessor`-style intermediary with `onChange`/`onTouched` callbacks. The control implements the `FormValueControl<T>` interface, where value and state are signals and the connection is two-way by construction.

</details>

## Common mistake

The first is duplicating form state in signals. The reasoning is tempting: "chapter 05 said state belongs in signals, so form fields should too". Out come `title = signal('')` and `priority = signal('medium')` next to a `FormGroup`, with two-way synchronization through `valueChanges` and `patchValue`.

The result is predictable: two sources of truth, cyclic updates, "the field resets while I type fast".

Here is the correct boundary. While you use Reactive Forms, **the form is the state**. Only what the template needs for display — validity, errors, `pending` — is mirrored into signals via `form.events` + `toSignal`. And if you want a signal to be the source of truth, that is Signal Forms. There should then be no `FormGroup` in the component at all.

The second is an async validator that never completes. You wrote a `switchMap` over `HttpClient` and forgot that a validator must **complete** its stream. The consequences: the control stays `pending` forever, `form.valid` is `false`, the submit button is disabled, and nothing appears in the console.

The same trap applies to a validator built over `valueChanges`: it subscribes to an infinite stream. The cure is `first()`/`take(1)` at the end of the pipeline (as in the walkthrough) plus a `form.pending` check in the submit handler.

A neighbouring bug of the same family is an async validator without `updateOn: 'blur'` or `debounceTime`. It fires a request on every keystroke, so the server receives a dozen uniqueness checks for one word.
