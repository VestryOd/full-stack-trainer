# Semantic HTML and Accessibility

Four terms run through this article:

- **Screen reader** — software that speaks the page aloud for a blind or low-vision user.
- **Accessibility tree** — the semantic model of the page that assistive software reads instead of the visual layout.
- **Landmark** — an element such as `<nav>` or `<main>` that marks a page region, so a screen reader can jump straight to it.
- **WCAG** (Web Content Accessibility Guidelines) — the standard accessibility requirements are quoted from.

## Why semantic HTML matters — beyond search ranking

The common explanation is that Google ranks semantic pages higher, so semantics look like an SEO (search engine optimization) trick. True, but that is a side effect, not the reason semantics exist. The real reason is **the accessibility tree**.

Every browser maintains two representations of a page. One is the DOM (Document Object Model) tree, which is structural. The other is the **accessibility tree**, which is semantic.

Screen readers, braille displays, voice control software, and other assistive technologies read the accessibility tree — not the DOM, not the visual layout. The accessibility tree is built from semantic meaning: element roles, names, states, and properties.

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

Landmarks are the region elements: `<nav>`, `<main>`, `<header>`, `<footer>`, `<aside>` and `<section>`. A screen reader user jumps straight from one to the next, the way a sighted user scans a page visually. Without landmarks, they must listen to the whole page from the top.

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

An incorrect `role` or `aria-*` attribute actively misleads assistive technologies. A screen reader that meets `role="button"` on a `<div>` announces it as a button. If Enter and Space are not handled in JavaScript, that announcement is a lie. Bad ARIA creates a broken experience worse than no ARIA at all.

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

The value `polite` waits for the user to finish their current action before announcing. The value `assertive` (and `role="alert"`) interrupts immediately. Use it only for errors and urgent messages.

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

Here `aria-hidden="true"` on the SVG (scalable vector graphics) icon stops screen readers from reading raw title and path data. The `focusable="false"` attribute is needed in legacy Edge and Internet Explorer, where an SVG can otherwise steal tab focus.

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

A `tabindex` above zero is almost never justified, because it overrides the natural DOM order globally. Give one element `tabindex="1"` and it receives focus before every `tabindex="0"` element on the page. Its position in the DOM stops mattering.

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

The `inert` attribute is a cleaner alternative, and it is now broadly supported. Set `inert` on the background content. Every focusable element inside it drops out of the tab order and stops receiving pointer events.

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

The outline needs a contrast ratio of at least 3:1 against the adjacent background. That is a WCAG 2.2 requirement. The `outline-offset` property separates the ring from the element boundary, which makes it easier to see.

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

The attribute `aria-invalid="true"` makes screen readers announce the field as invalid when it receives focus. Putting `role="alert"` on the error message makes that message announced the moment it is inserted.

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

`aria-label` provides an inline string as the accessible name. `aria-labelledby` references another element's content. When both are present, `aria-labelledby` wins.

Which one to reach for:

- `aria-labelledby` — when the label text is already visible on screen, so you do not duplicate content.
- `aria-label` — when there is no visible label text: icon buttons, or a landmark region that needs a name nobody sees.

---

**"When would you use `role="presentation"` or `role="none"`?"**

They are synonyms. Both strip semantic meaning from an element that must exist in the DOM for layout reasons but should not appear in the accessibility tree.

Two classic uses:

- `<table role="presentation">` for layout tables, from the era before CSS Grid.
- Wrapper `<div>` elements inside composite ARIA widgets, where the extra container only confuses assistive technology.

Never use it on an interactive element: you would remove the role and still leave the element focusable.

---

**"Why doesn't `display: none` vs `visibility: hidden` vs `opacity: 0` behave the same way for accessibility?"**

Each of the three hides the element in a different layer.

- `display: none` — removes the element from layout and from the accessibility tree. Screen readers ignore it entirely.
- `visibility: hidden` — removes it from the visual layout and also hides it from the accessibility tree. The element exists in the DOM but is unreachable.
- `opacity: 0` — makes the element invisible, but it stays in the accessibility tree and in the tab order.

The third one is the trap. A screen reader reads an `opacity: 0` button and Tab focuses it, even though the user cannot see it. That is a common cause of "ghost" focusable elements.

---

**"What does `aria-hidden="true"` do, and what's the danger?"**

`aria-hidden="true"` removes the element from the accessibility tree, and assistive technologies skip it entirely. The danger is applying it to an element that contains focusable children.

The element disappears from the accessibility tree, but Tab still lands on the interactive children inside it. The screen reader announces nothing when they receive focus — a confusing black hole.

The rule: never put `aria-hidden="true"` on an element that has, or might later have, focusable descendants. The exception is when you also give them `tabindex="-1"` or `disabled`.

---

**"What is the `:focus-visible` pseudo-class and why was it introduced?"**

`:focus-visible` applies when the browser decides that the focus ring should be visible, based on how the user reached the element.

- A mouse user clicking a button gets focus on it, so keyboard events work, but needs no ring. The pseudo-class does not apply.
- A keyboard user tabbing to a button does need the ring. The pseudo-class applies.

Before it existed, developers wrote `outline: none` to kill the ring for mouse clicks. That killed it for keyboard navigation too — an accessibility violation. The pseudo-class fixes that, and needs no JavaScript to track how the user is navigating.
