# Формы

## Теория

### Reactive Forms: модель формы как объект

Основной инструмент для форм в Angular — Reactive Forms: форма описывается в классе как дерево объектов, а шаблон к ней только привязывается.

```ts
private readonly fb = inject(FormBuilder);

// nonNullable убирает null из типа: без него FormControl<string | null>,
// потому что reset() возвращает контрол к null
protected readonly form = this.fb.nonNullable.group({
  title: this.fb.nonNullable.control('', {
    validators: [Validators.required, Validators.maxLength(120)],
  }),
  priority: this.fb.nonNullable.control<TicketPriority>('medium'),
  // updateOn: 'blur' — значение и валидация обновляются по потере фокуса,
  // а не на каждый символ: дешевле и спокойнее для UX
  email: this.fb.nonNullable.control('', {
    validators: [Validators.email],
    updateOn: 'blur',
  }),
  tags: this.fb.array<FormControl<string>>([]),
});
```

Типизация здесь не косметика: `form.value` выводится из структуры, поэтому опечатка в имени поля — ошибка компиляции. Важная тонкость: `form.value` для группы с отключёнными контролами имеет тип `Partial<...>` и **не содержит** disabled-поля; полное значение даёт `getRawValue()`.

Три класса, из которых собирается форма: `FormControl` (одно значение), `FormGroup` (объект с фиксированными ключами), `FormArray` (динамический список — теги, позиции заказа, участники).

### Состояния контролов и UX ошибок

```
                Состояния контрола: на чём строится UX ошибок
┌───────────┬─────────────────────────────┬─────────────────────────────────┐
│ состояние │ когда становится true       │ что с ним делать                │
├───────────┼─────────────────────────────┼─────────────────────────────────┤
│ touched   │ поле потеряло фокус         │ главный триггер показа ошибки   │
├───────────┼─────────────────────────────┼─────────────────────────────────┤
│ dirty     │ значение менял пользователь │ предупреждение об уходе         │
├───────────┼─────────────────────────────┼─────────────────────────────────┤
│ pending   │ идёт async-валидация        │ спиннер у поля, блок submit     │
├───────────┼─────────────────────────────┼─────────────────────────────────┤
│ invalid   │ валидаторы вернули ошибку   │ сам факт ошибки, но не показ    │
├───────────┼─────────────────────────────┼─────────────────────────────────┤
│ disabled  │ control.disable()           │ значение выпадает из form.value │
└───────────┴─────────────────────────────┴─────────────────────────────────┘
       ошибку показывают при invalid И (touched ИЛИ форма отправлена):
         иначе поля краснеют до того, как пользователь начал вводить
```

Главная мысль: **`invalid` — не повод показывать ошибку**. Пустое обязательное поле невалидно с самого начала, но краснеть при загрузке формы оно не должно. Стандартная формула — `invalid && (touched || submitted)`, где `submitted` — ваш собственный сигнал, выставляемый при попытке отправки (у `FormGroup` признака «submitted» нет; он есть у директивы `ngForm`, но с Reactive Forms её обычно не используют).

### Валидаторы

Синхронный валидатор — функция `(control) => ValidationErrors | null`. Асинхронный возвращает `Promise` или `Observable` и переводит контрол в `pending`. Кросс-полевая валидация вешается на **группу**, а не на поле, потому что ей нужны оба значения:

```ts
export function slaWithinPriority(group: AbstractControl): ValidationErrors | null {
  const priority = group.get('priority')?.value as TicketPriority | undefined;
  const sla = group.get('slaHours')?.value as number | null;
  if (priority !== 'urgent' || sla === null) return null;
  return sla <= 4 ? null : { slaTooLongForUrgent: { max: 4, actual: sla } };
}
```

Ошибка при этом лежит на группе, а не на поле, поэтому её нужно осознанно вывести рядом с нужным контролом — типичный источник «валидация есть, а пользователь её не видит».

### Запись значений

```
                               Запись значений в Reactive Forms
┌──────────────────────┬────────────────────────────────┬────────────────────────────────────┐
│ вызов                │ что делает                     │ подводный камень                   │
├──────────────────────┼────────────────────────────────┼────────────────────────────────────┤
│ setValue(v)          │ требует ВСЕ поля группы        │ пропустил поле — ошибка в рантайме │
├──────────────────────┼────────────────────────────────┼────────────────────────────────────┤
│ patchValue(v)        │ обновляет только переданные    │ опечатку в ключе не заметит никто  │
├──────────────────────┼────────────────────────────────┼────────────────────────────────────┤
│ reset(v)             │ значение + сброс touched/dirty │ сбрасывает и статусы валидации     │
├──────────────────────┼────────────────────────────────┼────────────────────────────────────┤
│ { emitEvent: false } │ не эмитит valueChanges         │ зависимая логика не сработает      │
├──────────────────────┼────────────────────────────────┼────────────────────────────────────┤
│ form.value           │ без disabled-полей             │ нужен getRawValue()                │
└──────────────────────┴────────────────────────────────┴────────────────────────────────────┘
              в zoneless setValue/patchValue НЕ запускают проверку шаблона сами:
               состояние формы надо отражать в сигналах или звать markForCheck
```

Последняя строка — то, о чём предупреждала глава 03, и одна из немногих вещей, которые действительно ломаются при переходе на zoneless. `setValue`/`patchValue` меняют состояние формы и эмитят свои Observable, но проверку шаблона не планируют. Пока значения читаются директивами (`formControlName`), это незаметно — их обновляет сам механизм привязки. А вот если шаблон читает `form.valid`, `control.errors` или `form.value` напрямую, то после программной записи разметка может остаться прежней. Практичное решение — не читать состояние формы в шаблоне напрямую, а отражать его в сигналы:

```ts
// events (v18+) отдаёт единый поток изменений значения, статуса и touched
private readonly formEvents = toSignal(this.form.events, { initialValue: null });

// сигналы, на которые шаблон может опираться безопасно
protected readonly isInvalid = computed(() => {
  this.formEvents();               // зависимость: пересчитать при любом событии формы
  return this.form.invalid;
});
```

### ControlValueAccessor: свой контрол

Чтобы собственный компонент работал внутри Reactive Forms (`formControlName`, валидаторы, `touched`), он должен реализовать `ControlValueAccessor` — четыре метода-контракта:

```ts
@Component({
  selector: 'app-priority-picker',
  providers: [
    // NG_VALUE_ACCESSOR — multi-токен (глава 04): так формы находят контрол.
    // forwardRef нужен, потому что класс ещё не определён на этой строке
    { provide: NG_VALUE_ACCESSOR, useExisting: forwardRef(() => PriorityPicker), multi: true },
  ],
  template: `…`,
})
export class PriorityPicker implements ControlValueAccessor {
  protected readonly value = signal<TicketPriority>('medium');
  protected readonly disabled = signal(false);

  private onChange: (value: TicketPriority) => void = () => {};
  private onTouched: () => void = () => {};

  // форма → компонент
  writeValue(value: TicketPriority | null): void {
    this.value.set(value ?? 'medium');
  }
  // компонент → форма
  registerOnChange(fn: (value: TicketPriority) => void): void { this.onChange = fn; }
  registerOnTouched(fn: () => void): void { this.onTouched = fn; }
  setDisabledState(isDisabled: boolean): void { this.disabled.set(isDisabled); }

  protected select(priority: TicketPriority): void {
    this.value.set(priority);
    this.onChange(priority);   // без этого форма не узнает о значении
    this.onTouched();          // без этого не появится touched, а значит и ошибки
  }
}
```

Забыть `onTouched()` — самая частая ошибка в кастомных контролах: значение приходит, а ошибки не показываются, потому что `touched` никогда не становится `true`.

### Signal Forms: куда идёт фреймворк

С v22 в Angular есть второй, сигнальный API форм (`@angular/forms/signals`, `@publicApi 22.0`). Идея принципиально иная: **источник правды — ваш сигнал с данными**, а форма лишь оборачивает его деревом полей.

```ts
import { form, schema, submit, required, minLength, min, validate } from '@angular/forms/signals';

// 1. модель — обычный сигнал
private readonly model = signal({ title: '', priority: 'medium' as TicketPriority, slaHours: 4 });

// 2. правила описываются схемой поверх модели
private readonly rules = schema<TicketDraft>((path) => {
  required(path.title, { message: 'Title is required' });
  minLength(path.title, 5);
  min(path.slaHours, 1);
  // кросс-полевая проверка: правило видит всё значение
  validate(path, ({ value }) =>
    value().priority === 'urgent' && value().slaHours > 4
      ? { kind: 'slaTooLong', message: 'Urgent tickets need SLA ≤ 4h' }
      : null,
  );
});

// 3. форма = модель + схема
protected readonly ticketForm = form(this.model, this.rules);

// 4. отправка: серверные ошибки возвращаются из action и садятся на поля
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

Что здесь принципиально: данные не копируются в форму (`form()` пишет прямо в ваш сигнал), правила отделены от структуры и переиспользуются через `schema()`, а состояние поля (`value`, `errors`, `touched`, `disabled`, `pending`) — сигналы. Есть готовые правила `required`, `min`/`max`, `minLength`/`maxLength`, `email`, `pattern`, `validate`, `validateAsync`, `validateHttp`, `validateTree`, интеграция со Standard Schema (zod, valibot), а также `disabled`, `hidden`, `readonly`, `debounce`. Структурные помощники — `apply`, `applyEach`, `applyWhen`, `applyWhenValue`. Кастомный контрол реализует **интерфейс** `FormValueControl<T>` (или `FormCheckboxControl`) — то есть `ControlValueAccessor` с его четырьмя методами больше не нужен.

```
┌────────────────────┬────────────────────────────────┬───────────────────────────────┐
│ что делаем         │ Reactive Forms                 │ Signal Forms (v22)            │
├────────────────────┼────────────────────────────────┼───────────────────────────────┤
│ источник правды    │ FormGroup внутри формы         │ ваш signal с данными          │
├────────────────────┼────────────────────────────────┼───────────────────────────────┤
│ создание           │ new FormGroup({...})           │ form(model)                   │
├────────────────────┼────────────────────────────────┼───────────────────────────────┤
│ привязка в шаблоне │ [formGroup] + formControlName  │ [formRoot] + [formField]      │
├────────────────────┼────────────────────────────────┼───────────────────────────────┤
│ валидатор          │ Validators.required в контроле │ required(path) в схеме        │
├────────────────────┼────────────────────────────────┼───────────────────────────────┤
│ чтение ошибок      │ control.errors?.[key]          │ field().errors()              │
├────────────────────┼────────────────────────────────┼───────────────────────────────┤
│ свой контрол       │ ControlValueAccessor           │ интерфейс FormValueControl<T> │
├────────────────────┼────────────────────────────────┼───────────────────────────────┤
│ отправка           │ form.valid + свой submit       │ submit(form, { action })      │
└────────────────────┴────────────────────────────────┴───────────────────────────────┘
```

Практическая позиция курса: **проект пишем на Reactive Forms**. Причины прагматичные — именно их вы встретите в существующих проектах и о них спрашивают на собеседованиях, вокруг них построены все библиотеки UI-компонентов, и они проверены годами. Signal Forms стоит знать и попробовать: API стабилен, направление очевидно, а миграция по одной форме за раз возможна благодаря слою совместимости в пакете.

### Template-driven — обзорно

Третий вариант: `[(ngModel)]` + `name` внутри `<form>`, где форму собирает директива `ngForm`, а валидаторы задаются атрибутами (`required`, `minlength`). Плюс — минимум кода для примитивных форм. Минусы, из-за которых он не является основным: структура формы неявная (её нет в классе), типизация слабая, программное управление неудобное, а асинхронная валидация и кросс-полевые правила требуют изобретательности. В новом коде встречается редко — но встречается, поэтому синтаксис `#form="ngForm"` и `form.controls['title'].errors` опознавать нужно.

## Параллели с React

- **Кто владеет состоянием.** В React состояние формы почти всегда лежит в компоненте: `useState` или `react-hook-form` с его `register`. В Reactive Forms владелец — сам объект `FormGroup`, у него своё дерево, свои статусы и своя валидация; компонент лишь держит на него ссылку. Отсюда ощущение «формы в Angular тяжелее»: это отдельная модель со своим API, а не переменная состояния.
- **react-hook-form ближе к Signal Forms.** RHF хранит данные вне рендера и подписывает поля через `register`; Signal Forms делает то же самое, только источник — сигнал, а поля — дерево над ним. Даже валидация похожа: схема (zod) поверх модели, а не валидаторы, разбросанные по полям.
- **Показ ошибок.** В React вы обычно решаете сами: `formState.errors` плюс `isSubmitted`. В Angular готовые флаги есть у каждого контрола (`touched`, `dirty`, `pending`), но правило показа всё равно ваше: `invalid` сам по себе не означает «покажи ошибку».
- **Кастомный контрол.** В React это компонент с пропсами `value`/`onChange` — и всё. В Angular нужен контракт: `ControlValueAccessor` с четырьмя методами и провайдером `NG_VALUE_ACCESSOR`. Больше церемоний, зато контрол получает всю инфраструктуру форм — валидацию, статусы, `disabled`, интеграцию с `formControlName`. В Signal Forms церемоний меньше: достаточно реализовать интерфейс.
- **Где ломается привычка:** попытка держать значения формы в отдельных сигналах и «синхронизировать» их с `FormGroup`. Получаются два источника правды и вечные расхождения. Правильно наоборот: `FormGroup` — источник, а в сигналы отражается то, что нужно шаблону (валидность, ошибки), через `form.events` и `toSignal`.

## Что увидишь в legacy-коде

- **Нетипизированные формы:** `new FormGroup({ title: new FormControl('') })` до Angular 14 не имели типов, поэтому `form.value.titel` компилировалось. Отсюда `UntypedFormGroup`/`UntypedFormControl` в мигрированных проектах — маркер того, что форму не довели до типизации.
- **`FormBuilder` без `nonNullable`:** `this.fb.group({ title: [''] })` даёт `FormControl<string | null>`, и `null` расходится по коду. Современный вариант — `fb.nonNullable.group(...)`.
- **`valueChanges.subscribe()` с ручной отпиской** и логикой «поле A меняет поле B» внутри подписки. Сейчас — `takeUntilDestroyed()` (глава 09) или `form.events`, а лучше — правило валидации вместо императивной синхронизации.
- **`ngModel` вместе с Reactive Forms:** `[(ngModel)]` на контроле, у которого уже есть `formControlName`. Такая комбинация была deprecated и убрана; если видите — это форма, переписанная наполовину.
- **`markAsTouched()` в цикле по всем контролам** перед отправкой, часто рекурсивной функцией `markAllAsTouched` собственного изготовления — сейчас у `AbstractControl` есть готовый `markAllAsTouched()`.
- **`Validators.compose([...])`** и валидаторы-классы (`@Directive` с `NG_VALIDATORS`) там, где хватило бы обычной функции.

## Что добавляем в проект

Форма создания и редактирования тикета: типизированная `FormGroup` с валидаторами, кросс-полевым правилом «urgent требует SLA ≤ 4ч», асинхронной проверкой уникальности заголовка, `FormArray` для тегов и кастомным контролом выбора приоритета на `ControlValueAccessor`. Плюс тот же экран, набросанный на Signal Forms, — для сравнения.

## Практическое задание

**Вход:** проект из главы 09 (HTTP-слой, поиск, поллинг).
**Выход:** рабочая форма создания/редактирования с валидацией и своим контролом.

Требования:

1. Типизированная форма: `title` (обязательный, 5–120 символов), `priority` (union-тип), `assignee` (строка или `null`), `slaHours` (число, 1–72), `tags` (`FormArray` строк, добавление/удаление). Никаких `UntypedFormGroup`, никаких `any`, `null` только там, где он осмыслен.
2. Кросс-полевая валидация на группе: если `priority === 'urgent'`, то `slaHours ≤ 4`. Ошибку нужно показать рядом с полем SLA, хотя она лежит на группе — продумайте, как.
3. Асинхронный валидатор: заголовок не должен дублировать существующий тикет (запрос к `/api/tickets?q=`). Учтите `pending` в UI и не отправляйте запрос на каждый символ.
4. UX ошибок: ошибка появляется только при `invalid && (touched || submitted)`. Кнопка отправки заблокирована при `invalid` или `pending`, но при первой попытке отправки невалидной формы все поля должны получить `touched`.
5. Кастомный контрол `PriorityPicker` на `ControlValueAccessor`: работает через `formControlName`, поддерживает `disabled`, корректно отмечает `touched`.
6. Режим редактирования: тот же компонент заполняется данными существующего тикета. Решите, `setValue` или `patchValue`, и объясните выбор. Не забудьте про `tags` — массив нужно пересобрать.
7. Отражение состояния формы в шаблон сделайте через сигналы (`form.events` + `toSignal`), а не чтением `form.invalid` напрямую — и объясните, почему это важно именно в zoneless.
8. Дополнительно: перепишите ту же форму на Signal Forms в отдельном компоненте и сравните объём кода и места, где пришлось думать.

Edge cases на подумать:

- Вы вызвали `setValue({ title: 'x' })` на группе из пяти полей. Что произойдёт?
- Контрол `assignee` отключён (`disable()`). Что вернёт `form.value` и как получить полное значение?
- Асинхронный валидатор ещё выполняется, а пользователь нажал «Сохранить». Что покажет `form.valid` и как это обработать?
- `reset()` вызван после успешного сохранения. Что произойдёт с `touched`, `dirty` и ошибками — и что увидит пользователь?
- В шаблоне читается `form.controls.title.errors`. Почему в zoneless этого может быть недостаточно для обновления разметки?

## Разбор решения

`src/app/tickets/ticket-form.ts` — основная форма:

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

  // nonNullable: без него каждый контрол был бы FormControl<string | null>,
  // потому что reset() возвращает значение к null
  protected readonly form = this.fb.nonNullable.group(
    {
      title: this.fb.nonNullable.control('', {
        validators: [Validators.required, Validators.minLength(5), Validators.maxLength(120)],
        asyncValidators: [this.uniqueTitle()],
        // валидация по blur: иначе async-валидатор стреляет на каждый символ
        updateOn: 'blur',
      }),
      priority: this.fb.nonNullable.control<TicketPriority>('medium'),
      assignee: this.fb.control<string | null>(null),
      slaHours: this.fb.nonNullable.control(4, {
        validators: [Validators.required, Validators.min(1), Validators.max(72)],
      }),
      tags: this.fb.nonNullable.array<FormControl<string>>([]),
    },
    // кросс-полевой валидатор живёт на ГРУППЕ: ему нужны два значения
    { validators: [slaWithinPriority] },
  );

  // Своя пометка «пользователь пытался отправить»: у FormGroup такого нет
  private readonly submitted = signal(false);

  // form.events (v18+) — единый поток изменений значения, статуса и touched.
  // Через него состояние формы попадает в сигналы, а значит и в шаблон
  private readonly formEvents = toSignal(this.form.events, { initialValue: null });

  protected readonly isInvalid = computed(() => {
    this.formEvents();                       // зависимость от любого события формы
    return this.form.invalid;
  });
  protected readonly isPending = computed(() => {
    this.formEvents();
    return this.form.pending;
  });
  protected readonly slaError = computed(() => {
    this.formEvents();
    // ошибка лежит на группе, но показать её нужно рядом с полем SLA
    return this.form.errors?.['slaTooLongForUrgent'] as { max: number } | undefined;
  });

  // Показывать ошибку, а не просто «быть невалидным»
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

    if (this.form.pending) return;           // ждём async-валидацию
    if (this.form.invalid) {
      // без этого пользователь не увидит, ЧТО именно не так
      this.form.markAllAsTouched();
      return;
    }

    // getRawValue(), а не value: disabled-поля должны попасть в запрос
    this.api.create(this.form.getRawValue()).subscribe(/* … */);
  }

  // Асинхронный валидатор как метод-фабрика: замыкает api и debounce
  private uniqueTitle() {
    return (control: AbstractControl) =>
      of(control.value as string).pipe(
        debounceTime(300),
        switchMap((title) => this.api.list({ q: title })),
        map((tickets) => (tickets.length > 0 ? { titleTaken: true } : null)),
        // валидатор ОБЯЗАН завершиться, иначе контрол навсегда останется pending
        first(),
      );
  }
}

// Кросс-полевой валидатор — обычная функция над группой
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

  <!-- кастомный контрол работает как обычный: через formControlName -->
  <app-priority-picker formControlName="priority" />

  <label>
    SLA, hours
    <input type="number" formControlName="slaHours" />
  </label>
  <!-- ошибка группы, показанная у нужного поля -->
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

Режим редактирования — заполнение существующими данными:

```ts
readonly ticket = input<Ticket | null>(null);

constructor() {
  // effect уместен: это выход во внешнюю (не сигнальную) систему —
  // объект формы. Производное значение здесь не подошло бы (глава 02)
  effect(() => {
    const ticket = this.ticket();
    if (ticket === null) return;

    // patchValue, потому что заполняем не все поля (tags собираем отдельно)
    this.form.patchValue({
      title: ticket.title,
      priority: ticket.priority,
      assignee: ticket.assignee,
      slaHours: ticket.slaHours ?? 4,
    });

    // FormArray нельзя «пропатчить» списком: контролы надо пересобрать
    const tags = this.form.controls.tags;
    tags.clear();
    for (const tag of ticket.tags ?? []) {
      tags.push(this.fb.nonNullable.control(tag));
    }
  });
}
```

`src/app/tickets/priority-picker.ts` — кастомный контрол:

```ts
@Component({
  selector: 'app-priority-picker',
  providers: [
    // multi-токен: так ReactiveFormsModule находит реализацию контрола
    { provide: NG_VALUE_ACCESSOR, useExisting: forwardRef(() => PriorityPicker), multi: true },
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
  protected readonly options: readonly TicketPriority[] = ['low', 'medium', 'high', 'urgent'];
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
    // Без onTouched() контрол никогда не станет touched — и ошибки,
    // привязанные к touched, не покажутся. Самая частая ошибка в CVA
    this.onTouched();
  }
}
```

Тот же экран на Signal Forms — для сравнения:

```ts
import { form, schema, submit, required, minLength, min, max, validate } from '@angular/forms/signals';

@Component({
  selector: 'app-ticket-form-signals',
  imports: [FormRoot, FormField],
  templateUrl: './ticket-form-signals.html',
})
export class TicketFormSignals {
  private readonly api = inject(TicketApi);

  // Модель — обычный сигнал и есть источник правды.
  // form() не копирует данные: запись в поле пишет в этот сигнал
  private readonly model = signal<TicketDraft>({
    title: '',
    priority: 'medium',
    assignee: null,
    slaHours: 4,
  });

  // Правила отделены от структуры и переиспользуемы
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
    // submit сам блокирует повторную отправку и раскладывает
    // серверные ошибки по полям, если action их вернёт
    await submit(this.ticketForm, { action: async (f) => this.api.create(f().value()) });
  }
}
```

Разница в объёме заметна: нет `FormBuilder`, нет `getRawValue()`, нет отдельного `submitted`, а состояние поля и так сигналы — прослойка с `form.events`/`toSignal` не нужна.

Ответы на edge cases:

- `setValue` требует значение **для всех** контролов группы: при неполном объекте вы получите ошибку в рантайме (`Must supply a value for form control with name: …`). Для частичного обновления существует `patchValue` — но у него обратная опасность: неизвестный или опечатанный ключ молча игнорируется, и «почему поле не заполнилось» приходится искать глазами.
- `form.value` не включает отключённые контролы, и её тип — `Partial`. Полное значение (включая `disabled`) даёт `form.getRawValue()`. Именно поэтому в `save()` используется `getRawValue()`: иначе поле, отключённое по бизнес-правилу, просто не уйдёт на сервер.
- Пока async-валидатор выполняется, статус контрола — `pending`, а `form.valid` — **`false`** (валидность ещё неизвестна). Поэтому проверять `if (form.invalid)` недостаточно: нужно отдельно обработать `pending` — либо заблокировать кнопку, либо дождаться завершения (`form.statusChanges` до первого не-`pending` статуса) и лишь затем отправлять.
- `reset()` возвращает значения к исходным (или к переданным), сбрасывает `touched`/`dirty` и пересчитывает валидацию: форма снова становится «нетронутой». Пользователь увидит чистую форму без красных подсветок — что после успешного сохранения корректно. Но если вы вызвали `reset()` при ошибке сервера, вы заодно стёрли введённые данные: тогда правильнее оставить значения и показать сообщение.
- Потому что `setValue`/`patchValue` в zoneless не планируют проверку шаблона. Пока значение читает директива `formControlName`, обновление проходит по механизму привязки. Но выражение `form.controls.title.errors` в шаблоне вычисляется только при проверке этого шаблона — и если проверку никто не запросил, разметка останется прежней. Отсюда решение из разбора: состояние формы отражается в сигналы через `form.events` + `toSignal`, и шаблон зависит от сигналов, а не от объекта формы напрямую.

## Проверь себя

1. Почему `invalid` — плохой критерий для показа ошибки, и какая формула используется вместо него?
2. В чём разница между `setValue` и `patchValue`, и какая опасность у каждого?
3. Зачем кросс-полевой валидатор вешают на группу, а не на поле, и какую проблему это создаёт в разметке?
4. Что делает `ControlValueAccessor` и почему забытый вызов `onTouched()` приводит к «форма не показывает ошибки»?
5. Чем принципиально отличается модель Signal Forms от Reactive Forms — и почему в Signal Forms не нужен `ControlValueAccessor`?

<details>
<summary>Ответы</summary>

1. `invalid` истинен с момента создания формы: пустое обязательное поле невалидно ещё до того, как пользователь его увидел. Показывать ошибки в этот момент — плохой UX (форма встречает пользователя красным). Нужен признак «пользователь уже имел дело с этим полем или пытался отправить форму»: `invalid && (touched || submitted)`, где `touched` даёт сам контрол при потере фокуса, а `submitted` — ваш сигнал, потому что у `FormGroup` такого флага нет. При отправке невалидной формы дополнительно вызывают `markAllAsTouched()`, чтобы показать все ошибки сразу.
2. `setValue` заменяет значение целиком и требует передать **все** контролы группы: пропущенное поле — ошибка в рантайме. `patchValue` обновляет только переданные поля. Опасности зеркальные: `setValue` роняет код при изменении структуры формы (добавили поле — сломались все вызовы), а `patchValue` **молча игнорирует** неизвестные ключи, поэтому опечатка в имени поля не вызовет ни ошибки, ни предупреждения — поле просто не заполнится. Практика: `patchValue` для частичных обновлений и заполнения из API, `setValue` — когда вы сознательно задаёте состояние формы целиком.
3. Кросс-полевое правило по определению зависит от нескольких контролов, а валидатор получает только тот контрол, на который повешен. Поэтому его вешают на общего родителя — группу, — откуда доступны оба значения. Проблема в разметке: результат оказывается в `group.errors`, а не в `errors` конкретного поля, и стандартный шаблон «показать ошибки контрола» её не увидит. Решение — сознательно вывести ошибку группы рядом с тем полем, которое пользователь должен исправить (как `slaError()` в разборе), либо продублировать её на поле через отдельный валидатор.
4. `ControlValueAccessor` — контракт между собственным компонентом и механизмом форм, четыре метода: `writeValue` (форма → компонент), `registerOnChange` (компонент сообщает форме новое значение), `registerOnTouched` (компонент сообщает о взаимодействии), `setDisabledState`. Если не вызвать `onTouched()`, контрол никогда не станет `touched` — а поскольку показ ошибок обычно завязан на `touched`, пользователь не увидит ни одной ошибки для этого поля, хотя `invalid` истинен. Симптом узнаваемый: «во всех полях ошибки показываются, а в моём кастомном — нет».
5. В Reactive Forms источник правды — сам объект `FormGroup`: данные живут внутри формы, а компонент обращается к ним через API контролов. В Signal Forms источник правды — **ваш сигнал с моделью**, а `form(model)` только надстраивает над ним дерево полей и правила; запись в поле пишет прямо в сигнал, копии данных не существует. Поэтому и кастомному контролу не нужен посредник вида `ControlValueAccessor` с колбэками `onChange`/`onTouched`: контрол реализует интерфейс `FormValueControl<T>`, где значение и состояние — сигналы, а связь двусторонняя по построению.

</details>

## Частая ошибка

Первая — дублирование состояния формы в сигналах. Логика соблазнительная: «в главе 05 мы договорились держать состояние в сигналах, значит и поля формы тоже». Появляются `title = signal('')`, `priority = signal('medium')`, а рядом `FormGroup`, и между ними — синхронизация в обе стороны через `valueChanges` и `patchValue`. Результат предсказуем: два источника правды, циклические обновления, «поле сбрасывается, когда я быстро печатаю». Правильная граница: пока вы работаете с Reactive Forms, **форма и есть состояние**; в сигналы отражают только то, что нужно шаблону для отображения (валидность, ошибки, `pending`) — через `form.events` + `toSignal`. Если хочется, чтобы источником правды был сигнал, это уже Signal Forms, и тогда `FormGroup` в компоненте быть не должно вовсе.

Вторая — асинхронный валидатор, который никогда не завершается. Написали `switchMap` на `HttpClient` и забыли, что валидатор обязан **завершить** поток: контрол остаётся в `pending` навсегда, `form.valid` — `false`, кнопка отправки заблокирована, и никаких ошибок в консоли. Ровно та же беда с валидатором на `valueChanges` внутри: он подпишется на бесконечный поток. Лечение — `first()`/`take(1)` в конце конвейера (как в разборе) и проверка `form.pending` в обработчике отправки. Соседняя ошибка того же класса — async-валидатор без `updateOn: 'blur'` или `debounceTime`: запрос уходит на каждый введённый символ, и сервер получает десяток проверок уникальности на одно слово.
