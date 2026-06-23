# Semantic HTML and Accessibility

## Why semantic HTML matters — beyond SEO

The common explanation is "Google ranks semantic pages higher." That's true, but it's a side effect, not the reason semantics exist. The real reason is **the accessibility tree**.

Every browser maintains two representations of a page: the DOM tree (structural) and the **accessibility tree** (semantic). Screen readers, braille displays, voice control software, and other assistive technologies read the accessibility tree — not the DOM, not the visual layout. The accessibility tree is built from semantic meaning: element roles, names, states, and properties.

```html
<!-- Both render visually identical — but the accessibility trees differ radically -->

<!-- This: -->
<div class="btn" onclick="submit()">Submit</div>

<!-- vs this: -->
<button type="submit">Submit</button>
```

For the `<div>`: the accessibility tree sees a generic container with text. Screen readers announce "Submit" with no role. The element is not in the natural tab order. It has no keyboard activation. It has no implicit `disabled` state that assistive tech can detect.

For `<button>`: the accessibility tree sees role=`button`, name="Submit", focusable=true, pressable via Space/Enter. A screen reader announces "Submit, button." The browser handles keyboard interaction automatically. Disabled via `disabled` attribute and assistive tech understands it.

This gap — **native HTML semantics vs a visually styled div** — is exactly what accessibility is about. Every `<div>` you use where a semantic element exists is a manual re-implementation of behaviors the browser provides for free.

### What native semantics give you (automatically, without JavaScript)

| Element | Role | Tab stop | Keyboard activation | State |
|---|---|---|---|---|
| `<button>` | button | yes | Space, Enter | disabled, pressed |
| `<a href>` | link | yes | Enter | visited |
| `<input type="checkbox">` | checkbox | yes | Space | checked, indeterminate |
| `<select>` | listbox | yes | Arrow keys | disabled |
| `<h1>`–`<h6>` | heading (level 1–6) | no | – | – |
| `<nav>` | navigation | no | – | – |
| `<main>` | main | no | – | – |

Landmarks (`<nav>`, `<main>`, `<header>`, `<footer>`, `<aside>`, `<section>`) allow screen reader users to jump between page regions — the equivalent of a sighted user scanning a page visually. Without landmarks, screen reader users must listen to the entire page sequentially.

## Heading hierarchy — the navigation skeleton

Screen reader users frequently navigate by jumping between headings. The heading hierarchy is the primary document outline. Skipping from `<h1>` to `<h3>` is like having a table of contents with a missing chapter — the document model breaks.

```html
<!-- Wrong — visual styling drives heading choice -->
<h1>Company Name</h1>
<h3>Products</h3>  <!-- skipped h2 -->
<h5>Product A</h5> <!-- skipped h4 -->

<!-- Correct — hierarchy reflects document structure -->
<h1>Company Name</h1>
<h2>Products</h2>
<h3>Product A</h3>
```

Each page should have exactly **one `<h1>`** (the page title / primary topic). Heading levels reflect nesting, not font size. Use CSS for visual size.

## ARIA: when native semantics fall short

ARIA (Accessible Rich Internet Applications) is a set of HTML attributes that **modify the accessibility tree**. ARIA does not change behavior, styling, or DOM structure — it only changes what assistive technologies see.

The most important ARIA principle: **No ARIA is better than bad ARIA.**

An incorrect `role` or `aria-*` attribute actively misleads assistive technologies. A screen reader encountering `role="button"` on a `<div>` will announce "button" — but if Enter/Space aren't handled in JavaScript, the announced affordance is a lie. Bad ARIA creates a broken experience worse than no ARIA at all.

### The ARIA use cases that are actually justified

**1. Roles for custom interactive widgets with no HTML equivalent**

```html
<!-- A custom tab widget — no native HTML equivalent -->
<div role="tablist" aria-label="Settings sections">
  <button role="tab" aria-selected="true" aria-controls="panel-general" id="tab-general">
    General
  </button>
  <button role="tab" aria-selected="false" aria-controls="panel-privacy" id="tab-privacy">
    Privacy
  </button>
</div>
<div role="tabpanel" id="panel-general" aria-labelledby="tab-general" tabindex="0">
  <!-- general settings content -->
</div>
<div role="tabpanel" id="panel-privacy" aria-labelledby="tab-privacy" tabindex="0" hidden>
  <!-- privacy settings content -->
</div>
```

Note: using `<button role="tab">` instead of `<div role="tab">` keeps native button keyboard behavior (tab/focus) while overriding the announced role.

**2. States that change dynamically**

```html
<button aria-expanded="false" aria-controls="menu" id="menu-btn">
  Menu
</button>
<ul id="menu" hidden>
  <li><a href="/about">About</a></li>
</ul>

<script>
  const btn = document.getElementById('menu-btn');
  const menu = document.getElementById('menu');

  btn.addEventListener('click', () => {
    const expanded = btn.getAttribute('aria-expanded') === 'true';
    btn.setAttribute('aria-expanded', String(!expanded));
    menu.hidden = expanded;
  });
</script>
```

`aria-expanded` tells screen readers "this button controls a region that is currently collapsed/expanded" — critical for menus, accordions, and disclosure widgets.

**3. Live regions — announcing dynamic content**

```html
<!-- Status updates that screen readers should announce automatically -->
<div aria-live="polite" aria-atomic="true" id="form-status">
  <!-- JavaScript updates this: "Form submitted successfully" -->
</div>

<!-- For urgent, interruptive announcements (errors, alerts) -->
<div role="alert">
  <!-- Content injected here is announced immediately -->
</div>
```

`aria-live="polite"` waits for the user to finish their current action before announcing. `aria-live="assertive"` (or `role="alert"`) interrupts immediately — use only for errors or urgent messages.

**4. Labelling elements that can't use `<label>`**

```html
<!-- Icon button with no visible text -->
<button aria-label="Close dialog">
  <svg aria-hidden="true" focusable="false"><!-- × icon --></svg>
</button>

<!-- A region described by content elsewhere -->
<section aria-labelledby="section-heading">
  <h2 id="section-heading">Recent Orders</h2>
  <!-- ... -->
</section>

<!-- Additional description beyond the label -->
<input
  type="password"
  id="pwd"
  aria-describedby="pwd-requirements"
/>
<div id="pwd-requirements">
  Must be at least 8 characters, include a number and a symbol.
</div>
```

`aria-hidden="true"` on the SVG prevents screen readers from reading raw SVG titles/paths. `focusable="false"` is required in IE/Edge legacy to prevent SVG from stealing tab focus.

### ARIA roles, states, and properties — the distinction

| Category | Examples | What it does |
|---|---|---|
| Roles | `role="dialog"`, `role="tab"`, `role="alert"` | Overrides the element's semantic type in the accessibility tree |
| States | `aria-expanded`, `aria-checked`, `aria-disabled`, `aria-selected` | Current condition of an element (changes dynamically) |
| Properties | `aria-label`, `aria-labelledby`, `aria-describedby`, `aria-controls`, `aria-owns` | Relationships and names (relatively static) |

States are meant to change via JavaScript (`setAttribute`). Properties are typically set in HTML and rarely change.

## Focus management

Keyboard and screen reader users navigate by focus. Mismanaged focus is the most common accessibility failure in interactive applications.

### The natural tab order

Tab order follows DOM order, not visual order. If CSS positions an element visually before its DOM position, keyboard users encounter elements in a confusing sequence.

```html
<!-- DOM order matches visual order — correct -->
<nav>...</nav>
<main>
  <h1>Dashboard</h1>
  <button>Primary action</button>
</main>

<!-- CSS `order` in flexbox changes visual order but NOT tab order -->
<!-- This creates a mismatch — avoid it for interactive elements -->
<div style="display: flex; flex-direction: row-reverse;">
  <button>First visually</button>  <!-- Last in DOM → last in tab order -->
  <button>Second visually</button> <!-- First in DOM → first in tab order -->
</div>
```

### `tabindex` — when and how

```html
<!-- tabindex="0": adds non-interactive element to tab order (at its DOM position) -->
<div role="tabpanel" tabindex="0">...</div>

<!-- tabindex="-1": removes from tab order but keeps programmatically focusable -->
<div id="modal" tabindex="-1">...</div>
<!-- document.getElementById('modal').focus() works, Tab won't land here naturally -->

<!-- tabindex > 0: AVOID. Creates a parallel tab order that is impossible to maintain -->
<button tabindex="3">Don't do this</button>
```

`tabindex > 0` is almost never justified. It overrides the natural DOM order globally — one element with `tabindex="1"` makes it receive focus before every `tabindex="0"` element on the page, regardless of where it is in the DOM.

### Focus trapping in dialogs

When a modal dialog opens, focus must be trapped inside it. If a user can Tab out of a modal into background content, they lose context.

```javascript
function trapFocus(container) {
  const focusableSelectors = [
    'button:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[href]',
    '[tabindex="0"]',
  ].join(', ');

  const focusable = [...container.querySelectorAll(focusableSelectors)];
  const first = focusable[0];
  const last = focusable[focusable.length - 1];

  container.addEventListener('keydown', (e) => {
    if (e.key !== 'Tab') return;

    if (e.shiftKey) {
      if (document.activeElement === first) {
        e.preventDefault();
        last.focus();
      }
    } else {
      if (document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  });
}

// When dialog opens:
dialog.removeAttribute('hidden');
dialog.focus(); // move focus into dialog
trapFocus(dialog);

// When dialog closes:
dialog.setAttribute('hidden', '');
triggerButton.focus(); // return focus to the element that opened the dialog
```

The `inert` attribute (now broadly supported) is a cleaner alternative: set `inert` on background content and all focusable elements inside it are removed from the tab order and pointer interaction automatically.

```html
<div id="page-content" inert>...</div>
<dialog open>...</dialog>
```

## Keyboard navigation patterns

The correct keyboard pattern depends on the widget type. Mixing up these patterns breaks screen reader conventions.

### Tab vs Arrow keys — the fundamental split

- **Tab/Shift+Tab**: move between **widgets** (form fields, buttons, links, custom controls)
- **Arrow keys**: move within a **widget** (between tabs in a tab list, options in a listbox, items in a menu)

This is the distinction that trips up most implementations. A tab list should have **one tab stop** for the entire `role="tablist"`, and Arrow keys move between individual tabs. If Tab moves between tabs, screen reader users who use Tab to navigate the page have to tab through every tab to exit the widget.

```javascript
// Roving tabindex pattern — standard for tab lists, toolbars, radio groups
function initRovingTabindex(container, itemSelector) {
  const items = [...container.querySelectorAll(itemSelector)];
  let currentIndex = 0;

  // Only the active item is in the tab order
  items.forEach((item, i) => {
    item.setAttribute('tabindex', i === 0 ? '0' : '-1');
  });

  container.addEventListener('keydown', (e) => {
    const lastIndex = items.length - 1;
    let nextIndex = currentIndex;

    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      nextIndex = currentIndex === lastIndex ? 0 : currentIndex + 1;
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      nextIndex = currentIndex === 0 ? lastIndex : currentIndex - 1;
    } else if (e.key === 'Home') {
      nextIndex = 0;
    } else if (e.key === 'End') {
      nextIndex = lastIndex;
    } else {
      return;
    }

    e.preventDefault();
    items[currentIndex].setAttribute('tabindex', '-1');
    items[nextIndex].setAttribute('tabindex', '0');
    items[nextIndex].focus();
    currentIndex = nextIndex;
  });
}
```

## Visible focus indicators

Browsers apply a default focus ring (`:focus` styles). Historically, many designers removed them with `outline: none` / `outline: 0` — this makes the site unusable for keyboard users.

The modern solution: `:focus-visible`. It applies only when the browser determines focus is from keyboard navigation, not mouse click.

```css
/* Remove the default ring for mouse users (who don't need it) */
:focus:not(:focus-visible) {
  outline: none;
}

/* Show a visible, well-designed ring for keyboard users */
:focus-visible {
  outline: 3px solid #005fcc;
  outline-offset: 2px;
  border-radius: 2px;
}
```

The outline should have at least 3:1 contrast ratio against the adjacent background (WCAG 2.2 requirement). `outline-offset` separates the ring from the element boundary, improving visibility.

## Common accessibility mistakes

### 1. Placeholder as label

```html
<!-- Wrong: placeholder disappears on input, no label persists -->
<input type="email" placeholder="Email address" />

<!-- Correct: always use <label> -->
<label for="email">Email address</label>
<input type="email" id="email" placeholder="user@example.com" />
```

Placeholder text has ~4.5:1 required contrast, but browser defaults barely pass 3:1. More importantly: placeholder disappears the moment the user starts typing. If they need to check what the field expects, they must clear the input.

### 2. Images without alt text (or with wrong alt text)

```html
<!-- Missing alt: screen reader reads filename or "image" -->
<img src="chart-q3-revenue.png" />

<!-- Decorative: empty alt suppresses announcement entirely -->
<img src="decorative-divider.svg" alt="" />

<!-- Informative: describes what the image communicates -->
<img src="chart-q3-revenue.png" alt="Q3 revenue chart showing 23% growth vs Q2" />

<!-- When the image is the only content of a link -->
<a href="/dashboard">
  <img src="logo.svg" alt="Dashboard home" />
  <!-- alt describes the link destination, not the image appearance -->
</a>
```

### 3. Click handlers on non-interactive elements

```html
<!-- Wrong: div is not keyboard-accessible, not announced as interactive -->
<div onclick="handleClick()">Click me</div>

<!-- Wrong even with tabindex and role — requires manual keyboard handling -->
<div onclick="handleClick()" tabindex="0" role="button">Click me</div>
<!-- Now you ALSO need keydown for Enter/Space, or it still breaks -->

<!-- Correct: use the right native element -->
<button type="button" onclick="handleClick()">Click me</button>
```

### 4. Dynamic content not announced

```javascript
// Wrong: updates DOM but screen reader users don't know
document.getElementById('result').textContent = 'Search returned 12 results';

// Correct: wrap in an aria-live region
// HTML: <div id="result" aria-live="polite" aria-atomic="true"></div>
document.getElementById('result').textContent = 'Search returned 12 results';
// Now the screen reader announces the new content
```

### 5. Color as the only error indicator

```html
<!-- Wrong: relies entirely on red color to indicate error -->
<input type="email" class="input-error" />
<!-- Input has red border — invisible to color-blind users -->

<!-- Correct: text + aria + color -->
<label for="email">Email</label>
<input
  type="email"
  id="email"
  aria-invalid="true"
  aria-describedby="email-error"
  class="input-error"
/>
<span id="email-error" role="alert">
  Invalid email format. Example: user@domain.com
</span>
```

`aria-invalid="true"` causes screen readers to announce "invalid" when the field is focused. `role="alert"` on the error message causes it to be announced immediately when injected.

### 6. Missing `lang` attribute

```html
<!-- Wrong: browser guesses the language; screen readers may use wrong pronunciation -->
<html>

<!-- Correct: explicit language declaration -->
<html lang="en">

<!-- Inline language switches -->
<p>The French phrase <span lang="fr">raison d'être</span> means reason for being.</p>
```

Screen readers use `lang` to select the correct voice/pronunciation engine. Without it, English text read by a Russian-language screen reader sounds unintelligible.

## Common interview traps

**"What's the difference between `aria-label` and `aria-labelledby`?"**

`aria-label` provides an inline string as the accessible name. `aria-labelledby` references another element's content. `aria-labelledby` takes precedence over `aria-label` when both are present. Use `aria-labelledby` when the label text is already visible on screen (don't duplicate content). Use `aria-label` when there is no visible label text (icon buttons, landmark regions needing a name that isn't visually displayed).

---

**"When would you use `role="presentation"` or `role="none"`?"**

They are synonyms. Used to strip semantic meaning from an element that must exist in the DOM for layout reasons but should not appear in the accessibility tree. Classic use: `<table role="presentation">` for layout tables (pre-CSS-grid era). Also for wrapper `<div>` elements inside ARIA composite widgets where the extra container confuses AT. Never use on interactive elements — you would remove the role but keep the element focusable, which is incoherent.

---

**"Why doesn't `display: none` vs `visibility: hidden` vs `opacity: 0` behave the same way for accessibility?"**

`display: none`: removes element from DOM layout AND from the accessibility tree. Screen readers ignore it entirely. `visibility: hidden`: removes from visual layout, also hides from accessibility tree (element exists in DOM but is inaccessible). `opacity: 0`: makes visually invisible but element remains in accessibility tree AND tab order. A screen reader will read an `opacity: 0` button, and Tab will focus it — even though the user cannot see it. This is a common cause of "ghost" focusable elements.

---

**"What does `aria-hidden="true"` do, and what's the danger?"**

`aria-hidden="true"` removes the element from the accessibility tree. Assistive technologies skip it entirely. The danger: applying it to an element that contains focusable children. The element is hidden from the accessibility tree, but Tab still lands on the interactive children. Screen reader announces nothing when those elements are focused — a confusing black hole. Rule: never put `aria-hidden="true"` on an element that has or might have focusable descendants unless you also make them `tabindex="-1"` or `disabled`.

---

**"What is the `:focus-visible` pseudo-class and why was it introduced?"**

`:focus-visible` applies when the browser determines that the focus indicator should be visible based on input modality. Mouse users clicking a button get focus on it (for keyboard events to work) but don't visually need a focus ring — `:focus-visible` doesn't apply. Keyboard users tabbing to a button do need the ring — `:focus-visible` applies. Before `:focus-visible`, developers used `outline: none` to suppress the ring for mouse clicks, which also suppressed it for keyboard navigation — an accessibility violation. `:focus-visible` solves this correctly without requiring JavaScript input-mode tracking.
