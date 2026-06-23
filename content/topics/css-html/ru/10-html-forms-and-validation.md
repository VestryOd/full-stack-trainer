# HTML-формы и валидация

## Элемент form — что он на самом деле делает

`<form>` — больше чем контейнер. Он определяет **контекст отправки**: HTTP-метод, URL назначения, тип кодирования и набор элементов управления, отправляемых вместе. Понимание этого важно, потому что React и другие фреймворки нередко рендерят формы без учёта того, что браузер предоставляет нативно.

```html
<form
  action="/api/register"
  method="POST"
  enctype="multipart/form-data"
  novalidate
>
```

- `action`: URL, на который отправляются данные. Если не указан — текущий URL.
- `method`: `GET` (данные в строке запроса, идемпотентный, bookmarkable) или `POST` (данные в теле запроса). `dialog` — третье значение, закрывает элемент `<dialog>`.
- `enctype`: `application/x-www-form-urlencoded` (по умолчанию), `multipart/form-data` (обязательно для загрузки файлов), `text/plain` (редко используется).
- `novalidate`: отключает нативный UI браузерной валидации — полезно когда нужно использовать Constraint Validation API программно без нативных всплывающих пузырей.

`<button type="submit">` внутри формы отправляет её. `<button>` без `type` внутри формы по умолчанию `type="submit"` — частая причина случайных отправок.

## Элементы управления формой — нативная семантика

```html
<!-- Текстовые поля -->
<input type="text">        <!-- однострочный текст -->
<input type="email">       <!-- валидирует формат email, показывает email-клавиатуру на мобильном -->
<input type="tel">         <!-- показывает клавиатуру телефона, без валидации формата -->
<input type="url">         <!-- валидирует формат URL -->
<input type="password">    <!-- маскирует ввод, по умолчанию отключает автодополнение -->
<input type="search">      <!-- показывает кнопку очистки в некоторых браузерах -->
<input type="number">      <!-- цифровая клавиатура, валидация min/max/step -->
<input type="range">       <!-- слайдер -->

<!-- Дата/время -->
<input type="date">        <!-- выбор даты, формат YYYY-MM-DD -->
<input type="time">        <!-- выбор времени, формат HH:MM -->
<input type="datetime-local"> <!-- дата + время -->
<input type="month">
<input type="week">

<!-- Выбор -->
<input type="checkbox">    <!-- булев переключатель -->
<input type="radio">       <!-- исключительный выбор в группе (одинаковый name) -->
<select>                   <!-- выпадающий список -->
<input type="color">       <!-- выбор цвета -->

<!-- Файлы -->
<input type="file">        <!-- выбор файла, требует enctype multipart/form-data -->

<!-- Скрытые -->
<input type="hidden">      <!-- отправляет значение без участия пользователя (CSRF-токены и т.д.) -->

<!-- Кнопки -->
<button type="submit">     <!-- отправляет форму -->
<button type="reset">      <!-- сбрасывает все элементы к значениям по умолчанию -->
<button type="button">     <!-- ничего не делает нативно, для JavaScript -->
<input type="submit">      <!-- устарел в пользу <button type="submit"> -->
```

`<input type="email">` на мобильном показывает клавиатуру с видными `@` и `.com`. Это само по себе причина использовать правильный тип — ничего не стоит и улучшает UX для мобильных пользователей.

## Доступность форм — фундамент

### Связывание label

Каждый видимый элемент управления формой нуждается в видимой, программно связанной метке. "Placeholder как label" — нарушение доступности.

**Метод 1: Связывание через `for`/`id` (явное)**

```html
<label for="email">Электронная почта</label>
<input type="email" id="email" name="email" />

<!-- Клик по label фокусирует поле — встроенное поведение -->
```

**Метод 2: Оборачивающий label (неявное)**

```html
<label>
  Электронная почта
  <input type="email" name="email" />
</label>
```

Оба метода создают одинаковое доступное имя. Явный метод `for`/`id` гибче — label и поле не обязаны быть рядом в DOM.

**Что НЕ делать:**

```html
<!-- Неправильно: placeholder — не метка -->
<input type="email" placeholder="Электронная почта" />

<!-- Неправильно: aria-label вместо видимой метки (зрячие пользователи ничего не видят) -->
<input type="email" aria-label="Электронная почта" />
<!-- Технически проходит, но нарушает WCAG 2.5.3 (Label in Name) -->

<!-- Правильно: видимая метка + placeholder для подсказки -->
<label for="email">Электронная почта</label>
<input type="email" id="email" placeholder="user@example.com" />
```

`aria-label` уместен для полей только с иконкой (поле поиска внутри формы поиска с видимой кнопкой), но не как замена видимой метки для обычного поля.

### `fieldset` и `legend` — группировка связанных элементов

`<fieldset>` группирует семантически связанные элементы управления. `<legend>` предоставляет доступное имя группы. Обязательно для групп radio и checkbox — без этого скринридеры объявляют каждый вариант без контекста.

```html
<!-- Группа radio — legend даёт контекст вопроса -->
<fieldset>
  <legend>Предпочтительный способ связи</legend>

  <label>
    <input type="radio" name="contact" value="email" />
    Электронная почта
  </label>

  <label>
    <input type="radio" name="contact" value="phone" />
    Телефон
  </label>

  <label>
    <input type="radio" name="contact" value="mail" />
    Почта
  </label>
</fieldset>

<!-- Без fieldset + legend скринридер объявит:
     "Электронная почта, переключатель, 1 из 3" — без контекста вопроса -->

<!-- С fieldset + legend:
     "Предпочтительный способ связи, группа. Электронная почта, переключатель, 1 из 3" -->
```

```html
<!-- Группа checkbox — тот же принцип -->
<fieldset>
  <legend>Выберите интересы</legend>

  <label>
    <input type="checkbox" name="interests" value="css" />
    CSS
  </label>
  <label>
    <input type="checkbox" name="interests" value="js" />
    JavaScript
  </label>
</fieldset>
```

`fieldset` также группирует элементы для нативного состояния disabled — `<fieldset disabled>` отключает все элементы управления внутри:

```html
<fieldset disabled>
  <!-- Все input, select, button внутри отключены -->
  <!-- Полезно во время отправки формы для предотвращения двойной отправки -->
  <legend>Платёжная информация</legend>
  <input type="text" name="card-number" />
  <input type="text" name="cvv" />
</fieldset>
```

### Связывание сообщений об ошибках

Сообщения об ошибках должны быть программно связаны с невалидным полем, а не просто визуально рядом:

```html
<label for="email">Электронная почта</label>
<input
  type="email"
  id="email"
  name="email"
  aria-invalid="true"
  aria-describedby="email-error"
  required
/>
<span id="email-error" role="alert">
  Введите корректный адрес электронной почты.
</span>
```

- `aria-invalid="true"` — объявляет "недопустимо" при фокусе на поле
- `aria-describedby="email-error"` — связывает сообщение об ошибке с полем; скринридеры читают ошибку после метки и типа поля
- `role="alert"` — объявляет ошибку немедленно при её появлении в DOM

Для нескольких ошибок на одном поле:

```html
<input
  type="password"
  id="pwd"
  aria-describedby="pwd-hint pwd-error"
/>
<p id="pwd-hint">Минимум 8 символов.</p>
<p id="pwd-error" role="alert">Пароль слишком короткий.</p>
```

Несколько ID в `aria-describedby` разделяются пробелами. Скринридеры читают их по порядку.

## Нативные атрибуты валидации

### Полный набор атрибутов

```html
<!-- required: значение не должно быть пустым -->
<input type="text" required />

<!-- minlength / maxlength: количество символов -->
<input type="text" minlength="2" maxlength="50" />

<!-- min / max: числовые или датовые ограничения -->
<input type="number" min="0" max="100" step="5" />
<input type="date" min="2024-01-01" max="2024-12-31" />

<!-- pattern: regex-валидация (без слешей, автоматически привязан к ^ и $) -->
<input type="text" pattern="[A-Z]{2}[0-9]{6}" title="Формат: AA123456" />

<!-- step: допустимые шаги для number/date/time -->
<input type="number" min="0" step="0.01" /> <!-- допустимо: 0, 0.01, 0.02... -->

<!-- multiple: несколько email-адресов или файлов -->
<input type="email" multiple />  <!-- email-адреса через запятую -->
<input type="file" multiple />   <!-- выбор нескольких файлов -->

<!-- accept: фильтр типов файлов (рекомендательный — браузер применяет, пользователь может обойти) -->
<input type="file" accept=".pdf,.docx,image/*" />
```

### Атрибут `pattern` подробно

Атрибут `pattern` — регулярное выражение, применяемое ко всему значению поля (неявно привязано к `^` и `$`):

```html
<!-- Индекс в формате почтового кода UK -->
<input
  type="text"
  pattern="[A-Z]{1,2}[0-9][0-9A-Z]?\s?[0-9][A-Z]{2}"
  title="Введите корректный почтовый индекс (например, SW1A 1AA)"
/>

<!-- HEX-цвет -->
<input
  type="text"
  pattern="#[0-9A-Fa-f]{6}"
  title="Введите HEX-код цвета (например, #FF0000)"
/>

<!-- Телефон: цифры, пробелы, тире, скобки, опциональный + -->
<input
  type="tel"
  pattern="\+?[\d\s\-\(\)]{7,20}"
  title="Введите корректный номер телефона"
/>
```

`title` предоставляет подсказку, показываемую в нативном пузыре браузерной валидации при несоответствии паттерну.

### Псевдоклассы валидации

```css
/* Стилизация состояний valid/invalid — осторожно с UX: не показывать invalid до взаимодействия */
input:valid { border-color: green; }
input:invalid { border-color: red; }

/* :user-valid / :user-invalid — применяется только после взаимодействия пользователя с полем */
/* Предотвращает красные рамки при загрузке страницы до ввода */
input:user-invalid { border-color: red; }
input:user-valid { border-color: green; }

/* Обязательное + пустое */
input:required:placeholder-shown { /* ещё не заполнено */ }

/* Опциональное (не required) */
input:optional { }

/* Диапазонные поля */
input[type="range"]:in-range { }
input[type="range"]:out-of-range { }
```

`:user-valid` и `:user-invalid` (теперь поддерживаются всеми основными браузерами) решают UX-проблему `:valid`/`:invalid` — которые применяются сразу при загрузке страницы, показывая пустые обязательные поля как невалидные до того, как пользователь их даже коснулся.

## Constraint Validation API

Браузер предоставляет состояние валидации формы программно через Constraint Validation API. Это мост между нативной HTML-валидацией и JavaScript-управляемым UX валидации.

### Основные методы и свойства

```javascript
// На элементах управления формой (input, select, textarea, button):
input.validity          // объект ValidityState
input.validationMessage // строка — сообщение браузера (локализованное)
input.checkValidity()   // возвращает boolean, вызывает событие 'invalid' если false
input.reportValidity()  // как checkValidity(), но показывает нативный UI браузера
input.setCustomValidity(message) // установить кастомное сообщение об ошибке ('' для сброса)
input.willValidate      // false если элемент исключён из валидации

// На форме:
form.checkValidity()    // возвращает false если любой элемент не проходит, вызывает 'invalid'
form.reportValidity()   // то же, но показывает UI браузера для первого невалидного
```

### Объект `ValidityState` — точные причины ошибок

```javascript
input.validity.valueMissing     // обязательное поле пустое
input.validity.typeMismatch     // значение не соответствует типу (например, не email)
input.validity.patternMismatch  // не соответствует атрибуту pattern
input.validity.tooLong          // превышает maxlength
input.validity.tooShort         // меньше minlength
input.validity.rangeOverflow    // превышает max
input.validity.rangeUnderflow   // ниже min
input.validity.stepMismatch     // не является допустимым шагом
input.validity.badInput         // значение нельзя преобразовать (например, буквы в числовом поле)
input.validity.customError      // setCustomValidity() вызван с непустым сообщением
input.validity.valid            // true если все выше false
```

Проверка `validity.valueMissing` vs `validity.typeMismatch` позволяет показывать конкретные сообщения для каждой причины ошибки — без переизобретения логики валидации:

```javascript
function getErrorMessage(input) {
  const { validity } = input;

  if (validity.valueMissing) return 'Это поле обязательно для заполнения.';
  if (validity.typeMismatch) {
    if (input.type === 'email') return 'Введите корректный адрес электронной почты.';
    if (input.type === 'url') return 'Введите корректный URL.';
  }
  if (validity.patternMismatch) return input.title || 'Неверный формат.';
  if (validity.tooShort) return `Минимум ${input.minLength} символов.`;
  if (validity.tooLong) return `Максимум ${input.maxLength} символов.`;
  if (validity.rangeUnderflow) return `Минимальное значение: ${input.min}.`;
  if (validity.rangeOverflow) return `Максимальное значение: ${input.max}.`;

  return input.validationMessage; // запасной вариант — сообщение браузера
}
```

### `setCustomValidity` — интеграция серверных ошибок

```javascript
// После ответа сервера об ошибке (например, email уже существует):
async function handleSubmit(e) {
  e.preventDefault();
  const form = e.target;
  const emailInput = form.querySelector('[name="email"]');

  const response = await fetch('/api/register', {
    method: 'POST',
    body: new FormData(form),
  });

  if (!response.ok) {
    const error = await response.json();

    if (error.field === 'email') {
      emailInput.setCustomValidity(error.message);
      emailInput.reportValidity(); // показать UI браузера с нашим сообщением
      // ИЛИ: показать собственный UI:
      showErrorMessage(emailInput, error.message);
    }
  }
}

// Важно: очищать кастомную ошибку при редактировании
emailInput.addEventListener('input', () => {
  emailInput.setCustomValidity(''); // очистить — восстанавливает нативную валидацию
});
```

`setCustomValidity('')` (пустая строка) сбрасывает кастомную ошибку и восстанавливает нативную валидацию. Непустое сообщение без очистки делает поле бессрочно невалидным.

### Кастомная валидация с `novalidate` — полный контроль

```javascript
class FormValidator {
  constructor(form) {
    this.form = form;
    this.form.setAttribute('novalidate', ''); // отключаем UI браузера, оставляем API

    this.form.addEventListener('submit', this.handleSubmit.bind(this));

    // Валидация в реальном времени: при blur, затем при input после первой ошибки
    this.form.addEventListener('blur', this.handleBlur.bind(this), true);
  }

  handleSubmit(e) {
    e.preventDefault();
    const inputs = [...this.form.elements].filter(el => el.willValidate);
    let firstInvalid = null;

    inputs.forEach(input => {
      if (!input.checkValidity()) {
        this.showError(input, getErrorMessage(input));
        if (!firstInvalid) firstInvalid = input;
      } else {
        this.clearError(input);
      }
    });

    if (firstInvalid) {
      firstInvalid.focus(); // переместить фокус на первое невалидное поле
      return;
    }

    this.submitForm();
  }

  handleBlur(e) {
    const input = e.target;
    if (!input.willValidate) return;

    if (!input.checkValidity()) {
      this.showError(input, getErrorMessage(input));
      // Переключаемся на валидацию в реальном времени
      input.addEventListener('input', () => this.validateRealtime(input));
    }
  }

  validateRealtime(input) {
    if (input.checkValidity()) {
      this.clearError(input);
    } else {
      this.showError(input, getErrorMessage(input));
    }
  }

  showError(input, message) {
    input.setAttribute('aria-invalid', 'true');
    let errorEl = document.getElementById(`${input.id}-error`);
    if (!errorEl) {
      errorEl = document.createElement('span');
      errorEl.id = `${input.id}-error`;
      errorEl.setAttribute('role', 'alert');
      input.setAttribute('aria-describedby',
        `${input.getAttribute('aria-describedby') || ''} ${errorEl.id}`.trim()
      );
      input.parentNode.insertBefore(errorEl, input.nextSibling);
    }
    errorEl.textContent = message;
  }

  clearError(input) {
    input.removeAttribute('aria-invalid');
    const errorEl = document.getElementById(`${input.id}-error`);
    if (errorEl) errorEl.textContent = '';
  }
}
```

## Почему нативной валидации недостаточно для production

### 1. Нет контроля над UI валидации

Нативные пузыри браузера не стилизованы, не являются частью вашей дизайн-системы и не поддаются настройке. Позиция, внешний вид и тайминг всплывающего окна полностью под контролем браузера.

### 2. Тайминг валидации неправильный для UX

Нативная валидация срабатывает только при отправке формы. Лучшая практика:
- Валидировать при **blur** (первый раз, когда пользователь покидает поле)
- Валидировать при **input** после первой ошибки (реальное время, как только пользователь знает о проблеме)
- Валидировать всё при **submit**

Нативная валидация ничего из этого не делает — только при отправке.

### 3. Межполевая валидация невозможна

Нативная валидация проверяет каждое поле изолированно. Выразить "подтверждение пароля должно совпадать с паролем" или "дата окончания должна быть позже даты начала" с помощью HTML-атрибутов невозможно.

```javascript
// Межполевая валидация требует JavaScript
const password = document.getElementById('password');
const confirm = document.getElementById('confirm-password');

confirm.addEventListener('input', () => {
  if (confirm.value !== password.value) {
    confirm.setCustomValidity('Пароли не совпадают.');
  } else {
    confirm.setCustomValidity('');
  }
});
```

### 4. Серверные ошибки нельзя показать нативно

После отправки формы сервер может отклонить значение по причине, которую клиент не может предсказать — имя пользователя занято, карта отклонена, адрес вне зоны доставки. У нативной валидации нет механизма для этого. `setCustomValidity` заполняет пробел, но требует JavaScript.

### 5. Асинхронная валидация невозможна

Проверка доступности имени пользователя требует API-запроса. Атрибуты `pattern` не умеют делать HTTP-запросы.

```javascript
let debounceTimer;
usernameInput.addEventListener('input', () => {
  clearTimeout(debounceTimer);
  usernameInput.setCustomValidity(''); // очищаем во время проверки

  debounceTimer = setTimeout(async () => {
    const response = await fetch(`/api/check-username?value=${usernameInput.value}`);
    const { available } = await response.json();

    if (!available) {
      usernameInput.setCustomValidity('Это имя пользователя уже занято.');
    }
    updateFieldUI(usernameInput);
  }, 400);
});
```

### Подход для production

Используйте нативные атрибуты для того, что они дают (семантика типа поля, базовые ограничения, `ValidityState` без переизобретения логики), но стройте UX валидации на JavaScript:

```
HTML-атрибуты: type, required, minlength, maxlength, pattern, min, max
  → определяют правила (браузер валидирует против них)

JavaScript + Constraint Validation API:
  → управление таймингом (blur, input, submit)
  → управление UI (кастомные сообщения, кастомное отображение)
  → межполевая валидация
  → асинхронная валидация
  → интеграция серверных ошибок через setCustomValidity

novalidate на <form>:
  → отключить нативные пузыри браузера
  → оставить ValidityState API активным
```

## `FormData` — отправка и чтение значений

```javascript
const form = document.getElementById('my-form');

// Создать FormData из элемента формы
const formData = new FormData(form);

// Чтение значений
formData.get('email');          // одно значение
formData.getAll('interests');   // несколько значений (чекбоксы с одинаковым name)

// Изменение перед отправкой
formData.set('timestamp', Date.now());
formData.append('tag', 'web');
formData.delete('internal-field');

// Отправка вручную
fetch('/api/submit', {
  method: 'POST',
  body: formData,
  // Заголовок Content-Type не нужен — FormData сам устанавливает multipart/form-data
});

// Преобразование в обычный объект (без файловых полей)
const plain = Object.fromEntries(formData);

// Итерация
for (const [name, value] of formData) {
  console.log(name, value);
}
```

`FormData` корректно обрабатывает файловые поля, поля с несколькими значениями (чекбоксы, мультиселекты) и `<input type="hidden">` — ручное чтение формы через `querySelector` упускает многое из этого.

## Типичные ошибки на интервью

**"Почему нельзя использовать placeholder как label?"**

Placeholder исчезает, как только пользователь начинает вводить — чтобы вспомнить, что ожидается в поле, нужно очистить ввод. Placeholder имеет недостаточный контраст по умолчанию (браузеры рендерят его светлее). Не все вспомогательные технологии читают его как метку. WCAG 2.5.3 требует видимую метку. Placeholder — подсказка по формату (например, `user@example.com`), а не метка назначения поля.

---

**"Когда `fieldset` + `legend` обязательны, а когда опциональны?"**

Обязательны: группы radio (пользователям нужен контекст вопроса), группы checkbox, любой набор связанных полей, образующих логическую единицу (поля адреса доставки). Опциональны (но практика всё равно хорошая): форма с единственным полем, или когда окружающий визуальный контекст даёт достаточную подпись группы. Тест: если скринридер объявит только "Да, переключатель, 1 из 2" — понял бы пользователь, на что отвечает? Если нет — нужен `fieldset` + `legend`.

---

**"Что делает `novalidate` на элементе form?"**

Отключает нативный UI браузерной валидации (всплывающие пузыри), сохраняя Constraint Validation API активным. С `novalidate`: `input.validity.valid` по-прежнему отражает реальное состояние валидности, `input.checkValidity()` по-прежнему возвращает корректные результаты, `setCustomValidity` по-прежнему работает — вы просто берёте на себя ответственность за отображение обратной связи в собственном UI.

---

**"Что такое `setCustomValidity` и когда его использовать?"**

`setCustomValidity(message)` устанавливает кастомное сообщение об ошибке валидации на элементе управления. Установка непустой строки помечает элемент как невалидный и устанавливает `validity.customError = true`. Установка пустой строки сбрасывает ошибку. Сценарии использования: (1) серверные ошибки после отправки (email уже существует); (2) межполевая валидация (несовпадение паролей); (3) результаты асинхронной валидации (доступность имени пользователя). Всегда очищать через `setCustomValidity('')` при редактировании поля, иначе оно остаётся невалидным бессрочно.

---

**"В чём разница между `checkValidity()` и `reportValidity()`?"**

`checkValidity()`: возвращает `true`/`false`, вызывает событие `invalid` на невалидных элементах, НЕ показывает никакой UI. `reportValidity()`: то же, что `checkValidity()`, но также показывает нативный попап на первом невалидном элементе и фокусирует его. Используйте `checkValidity()` при создании кастомного UI валидации (не нужен пузырь браузера). Используйте `reportValidity()`, когда хотите чтобы браузер сам управлял обратной связью. На элементе формы оба валидируют все элементы и возвращают false если хоть один не проходит.

---

**"Почему `<input type="email">` лучше `<input type="text">` с pattern для email-полей, даже если всё равно валидировать на сервере?"**

Три причины помимо валидации: (1) мобильные клавиатуры — тип email показывает клавиатуру с `@` и `.com`, улучшая UX на мобильных; (2) автозаполнение — браузеры знают предлагать email-адреса для полей типа email; (3) доступность — скринридеры объявляют тип поля ("поле электронной почты" vs "текстовое поле"), давая пользователям контекст. Валидация атрибутами — дополнительна: используйте `type="email"` для UX-преимуществ и `pattern` или серверную валидацию для строгих правил формата.
