# HTML Forms and Validation

## The form element — what it actually does

`<form>` is more than a container. It defines a **submission context**: the HTTP method, action URL, encoding type, and the set of controls that are submitted together. Understanding this matters because React and other frameworks often render forms without understanding what the browser provides natively.

```html
<form
  action="/api/register"
  method="POST"
  enctype="multipart/form-data"
  novalidate
>
```

- `action`: the URL the form data is submitted to. If omitted, the current URL.
- `method`: `GET` (data in query string, idempotent, bookmarkable) or `POST` (data in request body). `dialog` is a third value — closes a `<dialog>` element.
- `enctype`: `application/x-www-form-urlencoded` (default), `multipart/form-data` (required for file uploads), `text/plain` (rarely used).
- `novalidate`: disables native browser validation UI — useful when you want to use the Constraint Validation API programmatically without triggering the browser's built-in popup bubbles.

A `<button type="submit">` inside the form submits it. `<button>` without `type` defaults to `type="submit"` inside a form — a frequent cause of accidental submissions.

## Form controls — native semantics

```html
<!-- Text inputs -->
<input type="text">        <!-- single-line text -->
<input type="email">       <!-- validates email format, shows email keyboard on mobile -->
<input type="tel">         <!-- shows phone keyboard on mobile, no format validation -->
<input type="url">         <!-- validates URL format -->
<input type="password">    <!-- masks input, disables autocomplete by default -->
<input type="search">      <!-- shows clear button in some browsers -->
<input type="number">      <!-- numeric keyboard, min/max/step validation -->
<input type="range">       <!-- slider -->

<!-- Date/time inputs -->
<input type="date">        <!-- date picker, YYYY-MM-DD format -->
<input type="time">        <!-- time picker, HH:MM format -->
<input type="datetime-local"> <!-- combined date+time -->
<input type="month">
<input type="week">

<!-- Selection -->
<input type="checkbox">    <!-- boolean toggle -->
<input type="radio">       <!-- exclusive selection within a group (same name) -->
<select>                   <!-- dropdown -->
<input type="color">       <!-- color picker -->

<!-- File -->
<input type="file">        <!-- file selector, requires multipart/form-data encoding -->

<!-- Hidden -->
<input type="hidden">      <!-- submits value without user interaction (CSRF tokens, etc.) -->

<!-- Buttons -->
<button type="submit">     <!-- submits the form -->
<button type="reset">      <!-- resets all controls to their default values -->
<button type="button">     <!-- does nothing natively, for JavaScript -->
<input type="submit">      <!-- deprecated in favour of <button type="submit"> -->
```

`<input type="email">` on mobile shows a keyboard with `@` and `.com` prominently placed. This alone is a reason to use the correct input type — it costs nothing and improves UX for mobile users.

## Form accessibility — the foundation

### Label association

Every visible form control needs a visible, programmatically associated label. "Placeholder as label" is an accessibility failure.

**Method 1: `for`/`id` association (explicit)**

```html
<label for="email">Email address</label>
<input type="email" id="email" name="email" />

<!-- Clicking the label focuses the input — built-in behavior -->
```

**Method 2: Wrapping label (implicit)**

```html
<label>
  Email address
  <input type="email" name="email" />
</label>
```

Both methods create the same accessible name. The explicit `for`/`id` method is more flexible — the label and input don't need to be adjacent in the DOM.

**What NOT to do:**

```html
<!-- Wrong: placeholder is not a label -->
<input type="email" placeholder="Email address" />

<!-- Wrong: aria-label as a substitute for a visible label (sighted users see nothing) -->
<input type="email" aria-label="Email address" />
<!-- This passes technically but fails WCAG 2.5.3 (Label in Name) -->

<!-- Correct: visible label + placeholder for hint -->
<label for="email">Email address</label>
<input type="email" id="email" placeholder="user@example.com" />
```

`aria-label` is appropriate for icon-only inputs (a search field inside a search form with a visible search button), but not as a replacement for a visible label on a standard field.

### `fieldset` and `legend` — grouping related controls

`<fieldset>` groups semantically related controls. `<legend>` provides the group's accessible name. This is mandatory for radio groups and checkbox groups — without it, screen readers announce each option without context.

```html
<!-- Radio group — legend provides the question context -->
<fieldset>
  <legend>Preferred contact method</legend>

  <label>
    <input type="radio" name="contact" value="email" />
    Email
  </label>

  <label>
    <input type="radio" name="contact" value="phone" />
    Phone
  </label>

  <label>
    <input type="radio" name="contact" value="mail" />
    Post
  </label>
</fieldset>

<!-- Without fieldset + legend, a screen reader would announce:
     "Email, radio button, 1 of 3" with no context about the question -->

<!-- With fieldset + legend:
     "Preferred contact method, group. Email, radio button, 1 of 3" -->
```

```html
<!-- Checkbox group — same principle -->
<fieldset>
  <legend>Select your interests</legend>

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

`fieldset` also groups controls for the browser's built-in disabled state — `<fieldset disabled>` disables every form control inside it:

```html
<fieldset disabled>
  <!-- All inputs, selects, buttons inside are disabled -->
  <!-- Useful during form submission to prevent double-submit -->
  <legend>Billing information</legend>
  <input type="text" name="card-number" />
  <input type="text" name="cvv" />
</fieldset>
```

### Error message association

Error messages must be programmatically associated with the invalid input, not just visually adjacent:

```html
<label for="email">Email address</label>
<input
  type="email"
  id="email"
  name="email"
  aria-invalid="true"
  aria-describedby="email-error"
  required
/>
<span id="email-error" role="alert">
  Please enter a valid email address.
</span>
```

- `aria-invalid="true"` — announces "invalid" when the field is focused
- `aria-describedby="email-error"` — links the error message to the input; screen readers read the error after reading the label and input type
- `role="alert"` — announces the error immediately when it appears in the DOM (for dynamically injected errors)

For multiple errors on a single field:

```html
<input
  type="password"
  id="pwd"
  aria-describedby="pwd-hint pwd-error"
/>
<p id="pwd-hint">Must be at least 8 characters.</p>
<p id="pwd-error" role="alert">Password is too short.</p>
```

Multiple IDs in `aria-describedby` are space-separated. Screen readers read them in order.

## Native validation attributes

### The full attribute set

```html
<!-- required: value must not be empty -->
<input type="text" required />

<!-- minlength / maxlength: character count -->
<input type="text" minlength="2" maxlength="50" />

<!-- min / max: numeric or date bounds -->
<input type="number" min="0" max="100" step="5" />
<input type="date" min="2024-01-01" max="2024-12-31" />

<!-- pattern: regex validation (no surrounding slashes, anchored automatically) -->
<input type="text" pattern="[A-Z]{2}[0-9]{6}" title="Format: AA123456" />

<!-- step: controls valid increments for number/date/time inputs -->
<input type="number" min="0" step="0.01" /> <!-- accepts: 0, 0.01, 0.02... -->

<!-- multiple: allows multiple email addresses or files -->
<input type="email" multiple />  <!-- comma-separated emails -->
<input type="file" multiple />   <!-- multiple file selection -->

<!-- accept: filter file types (advisory — browser enforces, user can override) -->
<input type="file" accept=".pdf,.docx,image/*" />
```

### `pattern` attribute in detail

The `pattern` attribute is a regular expression applied to the entire input value (implicitly anchored with `^` and `$`):

```html
<!-- UK postcode -->
<input
  type="text"
  pattern="[A-Z]{1,2}[0-9][0-9A-Z]?\s?[0-9][A-Z]{2}"
  title="Enter a valid UK postcode (e.g., SW1A 1AA)"
/>

<!-- Hex color -->
<input
  type="text"
  pattern="#[0-9A-Fa-f]{6}"
  title="Enter a hex color code (e.g., #FF0000)"
/>

<!-- Phone: digits, spaces, dashes, parens, optional + prefix -->
<input
  type="tel"
  pattern="\+?[\d\s\-\(\)]{7,20}"
  title="Enter a valid phone number"
/>
```

`title` provides a hint shown in the browser's native validation bubble when the pattern fails. This is the only user-visible explanation for pattern failures in native validation.

### Validation pseudo-classes

```css
/* Style valid/invalid states — careful with UX: don't show invalid before user touches */
input:valid { border-color: green; }
input:invalid { border-color: red; }

/* :user-valid / :user-invalid — only applies after the user has interacted with the field */
/* Prevents showing red borders on page load before user has typed anything */
input:user-invalid { border-color: red; }
input:user-valid { border-color: green; }

/* Required + empty */
input:required:placeholder-shown { /* not yet filled */ }

/* Optional (not required) */
input:optional { }

/* Range inputs */
input[type="range"]:in-range { }
input[type="range"]:out-of-range { }
```

`:user-valid` and `:user-invalid` (now supported in all major browsers) solve the UX problem of `:valid`/`:invalid` — which apply immediately on page load, showing empty required fields as invalid before the user has even focused them.

## The Constraint Validation API

The browser exposes form validation state programmatically through the Constraint Validation API. This is the bridge between native HTML validation and JavaScript-driven validation UX.

### Core methods and properties

```javascript
// On form controls (input, select, textarea, button):
input.validity          // ValidityState object
input.validationMessage // string — browser's validation message (localized)
input.checkValidity()   // returns boolean, fires 'invalid' event if false
input.reportValidity()  // like checkValidity() but also shows the browser's UI
input.setCustomValidity(message) // set a custom error message ('' to clear)
input.willValidate      // false if the control is excluded from validation

// On the form:
form.checkValidity()    // returns false if any control fails, fires 'invalid' on each
form.reportValidity()   // same but shows browser UI for first failing control
```

### The `ValidityState` object — precise failure reasons

```javascript
input.validity.valueMissing     // required field is empty
input.validity.typeMismatch     // value doesn't match input type (e.g., not an email)
input.validity.patternMismatch  // doesn't match pattern attribute
input.validity.tooLong          // exceeds maxlength
input.validity.tooShort         // below minlength
input.validity.rangeOverflow    // above max
input.validity.rangeUnderflow   // below min
input.validity.stepMismatch     // not a valid step increment
input.validity.badInput         // value can't be converted (e.g., letters in number field)
input.validity.customError      // setCustomValidity() was called with non-empty message
input.validity.valid            // true if all above are false
```

Checking `validity.valueMissing` vs `validity.typeMismatch` lets you show specific error messages for each failure reason — without re-implementing the validation logic yourself:

```javascript
function getErrorMessage(input) {
  const { validity } = input;

  if (validity.valueMissing) return 'This field is required.';
  if (validity.typeMismatch) {
    if (input.type === 'email') return 'Please enter a valid email address.';
    if (input.type === 'url') return 'Please enter a valid URL.';
  }
  if (validity.patternMismatch) return input.title || 'Invalid format.';
  if (validity.tooShort) return `Minimum ${input.minLength} characters required.`;
  if (validity.tooLong) return `Maximum ${input.maxLength} characters allowed.`;
  if (validity.rangeUnderflow) return `Minimum value is ${input.min}.`;
  if (validity.rangeOverflow) return `Maximum value is ${input.max}.`;

  return input.validationMessage; // fallback to browser's message
}
```

### `setCustomValidity` — server-side error integration

```javascript
// After a server response indicates a conflict (e.g., email already exists):
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
      emailInput.reportValidity(); // show the browser's validation UI with our message
      // OR: show your own custom UI:
      showErrorMessage(emailInput, error.message);
    }
  }
}

// Important: clear the custom validity when the user starts typing again
emailInput.addEventListener('input', () => {
  emailInput.setCustomValidity(''); // clear — re-enables native validation
});
```

`setCustomValidity('')` (empty string) clears the custom error and re-enables native validation. If you set a non-empty message and don't clear it, the field stays invalid permanently — even if the user fixes the value.

### Custom validation with `novalidate` — full control pattern

```javascript
class FormValidator {
  constructor(form) {
    this.form = form;
    this.form.setAttribute('novalidate', ''); // disable browser UI, keep API

    this.form.addEventListener('submit', this.handleSubmit.bind(this));

    // Real-time validation: validate on blur, then on each input after first error
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
      firstInvalid.focus(); // move focus to first invalid field
      return;
    }

    this.submitForm();
  }

  handleBlur(e) {
    const input = e.target;
    if (!input.willValidate) return;

    if (!input.checkValidity()) {
      this.showError(input, getErrorMessage(input));
      // Switch to real-time validation
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

## Why native validation alone isn't enough for production

### 1. No control over the validation UI

The browser's native validation bubbles are unstyled, not part of your design system, and cannot be customized. The position, appearance, and timing of the popup are entirely browser-controlled.

### 2. Validation timing is wrong for UX

Native validation only fires on form submit. Best practice is:
- Validate on **blur** (first time the user leaves a field)
- Validate on **input** after the first error (real-time feedback once the user knows there's an issue)
- Validate everything on **submit**

Native validation does none of this — it's submit-only.

### 3. Cross-field validation is impossible

Native validation validates each field in isolation. You cannot express "password confirmation must match password" or "end date must be after start date" with HTML attributes alone.

```javascript
// Cross-field validation requires JavaScript
const password = document.getElementById('password');
const confirm = document.getElementById('confirm-password');

confirm.addEventListener('input', () => {
  if (confirm.value !== password.value) {
    confirm.setCustomValidity('Passwords do not match.');
  } else {
    confirm.setCustomValidity('');
  }
});
```

### 4. Server-side errors can't be shown natively

After a form submission, the server might reject a value for a reason the client can't predict — username already taken, credit card declined, address not in delivery zone. Native validation has no mechanism for this. `setCustomValidity` bridges the gap, but requires JavaScript.

### 5. Async validation is impossible

Checking if a username is available requires an API call. `pattern` attributes can't do HTTP requests.

```javascript
let debounceTimer;
usernameInput.addEventListener('input', () => {
  clearTimeout(debounceTimer);
  usernameInput.setCustomValidity(''); // clear while checking

  debounceTimer = setTimeout(async () => {
    const response = await fetch(`/api/check-username?value=${usernameInput.value}`);
    const { available } = await response.json();

    if (!available) {
      usernameInput.setCustomValidity('This username is already taken.');
    }
    // Re-validate the form to update UI
    updateFieldUI(usernameInput);
  }, 400);
});
```

### The production approach

Use native attributes for what they provide (input type semantics, basic constraints, `ValidityState` without re-implementing logic), but build the validation UX in JavaScript:

```
HTML attributes: type, required, minlength, maxlength, pattern, min, max
  → define the rules (browser validates against these)

JavaScript + Constraint Validation API:
  → control timing (blur, input, submit)
  → control UI (custom error messages, custom display)
  → cross-field validation
  → async validation
  → server error integration via setCustomValidity

novalidate on <form>:
  → disable browser's native popup UI
  → keep ValidityState API active
```

## `FormData` — submitting and reading form values

```javascript
const form = document.getElementById('my-form');

// Create FormData from a form element
const formData = new FormData(form);

// Read values
formData.get('email');          // single value
formData.getAll('interests');   // multiple values (checkboxes with same name)

// Modify before submission
formData.set('timestamp', Date.now());
formData.append('tag', 'web');
formData.delete('internal-field');

// Submit manually
fetch('/api/submit', {
  method: 'POST',
  body: formData,
  // No Content-Type header needed — FormData sets multipart/form-data automatically
});

// Convert to plain object (no file inputs)
const plain = Object.fromEntries(formData);

// Iterate
for (const [name, value] of formData) {
  console.log(name, value);
}
```

`FormData` correctly handles file inputs, multiple-value fields (checkboxes, multi-selects), and `<input type="hidden">` — reading the form manually via `querySelector` misses many of these.

## Common interview traps

**"Why can't you use placeholder as a label?"**

Placeholder disappears as soon as the user starts typing — if they need to recall what the field expects, they must clear their input. It has insufficient contrast by design (browsers render it lighter). It's not read as a label by all assistive technologies — some screen readers skip it. WCAG 2.5.3 requires a visible label that matches or contains the accessible name. Placeholder is a hint for format (e.g., `user@example.com`), not a label for the field's purpose.

---

**"When is `fieldset` + `legend` required vs optional?"**

Required: radio groups (users need context to understand what they're choosing), checkbox groups (same reasoning), any set of related inputs that form a logical unit (shipping address fields). Optional (but still good practice): a single-field form, or when the surrounding visual context provides sufficient group labeling. The test: if a screen reader announced just "Yes, radio button, 1 of 2" — would the user know what they're answering? If no, `fieldset` + `legend` is needed.

---

**"What does `novalidate` on a form element do?"**

Disables the browser's built-in validation UI (the popup bubbles) while keeping the Constraint Validation API active. With `novalidate`, `input.validity.valid` still reflects the actual validity state, `input.checkValidity()` still returns correct results, and `setCustomValidity` still works — you just take over responsibility for showing validation feedback in your own UI.

---

**"What is `setCustomValidity` and when would you use it?"**

`setCustomValidity(message)` sets a custom validation error message on a form control. Setting a non-empty string marks the control as invalid and sets `validity.customError = true`. Setting an empty string clears the custom error. Use cases: (1) server-side errors after form submission (email already exists); (2) cross-field validation (password confirmation mismatch); (3) async validation results (username availability). Always clear it with `setCustomValidity('')` when the user modifies the field, otherwise the field stays invalid indefinitely.

---

**"What's the difference between `checkValidity()` and `reportValidity()`?"**

`checkValidity()`: returns `true`/`false`, fires the `invalid` event on invalid controls, does NOT show any browser UI. `reportValidity()`: same as `checkValidity()` but also shows the browser's native validation popup on the first invalid control and focuses it. Use `checkValidity()` when building custom validation UI (you don't want the browser popup). Use `reportValidity()` when you want the browser to handle feedback. On the form element, both validate all controls and return false if any fails.

---

**"Why is `<input type="email">` better than `<input type="text">` with a pattern for email fields, even if you validate on the server anyway?"**

Three reasons beyond validation: (1) mobile keyboards — email type shows a keyboard with `@` and `.com` prominently, improving mobile UX; (2) autofill — browsers know to suggest email addresses for email-type inputs; (3) accessibility — screen readers announce the input type ("email field" vs "text field"), giving users context. Pattern validation is additive — use both `type="email"` for these UX benefits and `pattern` or server validation for stricter format rules.
