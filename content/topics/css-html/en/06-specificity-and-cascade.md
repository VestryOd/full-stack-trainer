# Specificity and the Cascade

## The cascade — what it actually is

The **cascade** is the algorithm browsers use to resolve conflicts when multiple CSS rules target the same element and property. It is not just "last rule wins" — that's only the tiebreaker at the very end. The cascade applies five criteria in order, stopping as soon as one criterion produces a winner:

1. **Origin and importance** — where the rule comes from and whether `!important` is set
2. **Context** — shadow DOM encapsulation boundaries
3. **Cascade layer** — `@layer` ordering
4. **Specificity** — selector weight
5. **Order of appearance** — source position (the tiebreaker)

Most developers only know criterion 4 and 5. Understanding all five is what separates "CSS doesn't make sense" from "CSS makes complete sense."

## Origin and importance — the first criterion

CSS rules come from three origins:

1. **User-agent stylesheet** — browser defaults (`<h1>` is bold, `<a>` is blue and underlined, `<button>` has padding)
2. **Author stylesheet** — your CSS (linked files, `<style>` tags, inline styles)
3. **User stylesheet** — custom styles applied by the user (accessibility tools, browser extensions)

Without `!important`, the priority order is: **author > user > user-agent**.

With `!important`, the order **reverses for that property**: **user-agent `!important` > user `!important` > author `!important` > author normal > user normal > user-agent normal**.

This reversal is intentional. A user who applies `!important` to a rule (e.g., via an accessibility extension that enforces high-contrast colors) must be able to override even an `!important` author rule — because the user's needs take precedence.

Inline styles (`style=""`) are author styles with extremely high specificity — but they are still in the "author" origin bucket and can be overridden by author `!important`.

## Specificity — the precise calculation

Specificity is represented as three numbers: **(A, B, C)** where:
- **A** — count of ID selectors (`#id`)
- **B** — count of class selectors (`.class`), attribute selectors (`[attr]`), and pseudo-classes (`:hover`, `:focus`, `:nth-child()`)
- **C** — count of type selectors (elements: `div`, `p`, `span`) and pseudo-elements (`::before`, `::after`)

The universal selector `*`, combinators (`>`, `+`, `~`, ` `), and `:where()` contribute zero specificity.

Comparison is done left-to-right: a higher A always wins over any B or C value. **It is not a decimal number** — `(0, 1, 0)` does not become `0.1.0`. A class selector `(0, 1, 0)` beats any number of type selectors `(0, 0, N)` — even `(0, 0, 1000)`.

```css
/* Specificity breakdown: */

*                          /* (0, 0, 0) — universal, contributes nothing */
div                        /* (0, 0, 1) — one type selector */
.class                     /* (0, 1, 0) — one class */
#id                        /* (1, 0, 0) — one ID */
div p                      /* (0, 0, 2) — two types */
div.class                  /* (0, 1, 1) — one class + one type */
.nav .item                 /* (0, 2, 0) — two classes */
#header .nav a             /* (1, 1, 1) — one ID + one class + one type */
a:hover                    /* (0, 1, 1) — one pseudo-class + one type */
a::before                  /* (0, 0, 2) — one pseudo-element + one type */
input[type="text"]         /* (0, 1, 1) — one attribute selector + one type */
:not(.active)              /* (0, 1, 0) — :not() contributes its argument's specificity */
:is(.nav, #header)         /* (1, 0, 0) — :is() takes the highest specificity of its arguments */
:where(.nav, #header)      /* (0, 0, 0) — :where() always contributes zero */
```

### `:is()`, `:not()`, `:has()` — specificity of list selectors

These pseudo-classes are "forgiving" — they accept selector lists. Their specificity is determined by the **most specific selector in the argument list**:

```css
/* :is() specificity = specificity of most specific argument */
:is(div, .class, #id) p    /* (1, 0, 1) — #id is most specific in the list */

/* Even if the matching element doesn't match #id: */
/* <p class="class"> matches :is(div, .class, #id) via .class */
/* but specificity is still (1, 0, 1) because #id is in the list */
```

This is a key difference between `:is()` and `:where()`: `:where()` always contributes zero specificity, making it ideal for base styles you want to be easily overridden.

```css
/* Base styles with :where() — zero specificity, easily overridden */
:where(h1, h2, h3, h4, h5, h6) {
  font-weight: 700;
  line-height: 1.2;
}

/* Override with any specificity */
.article h2 { font-weight: 600; } /* (0, 1, 1) — wins */
```

### Inline styles

Inline styles have a specificity above any selector: effectively `(1, 0, 0, 0)` — a fourth column above A. Only `!important` overrides inline styles.

```html
<p style="color: red;">text</p>
```

```css
#specific.super-specific p { color: blue; } /* (1, 1, 1) — still loses to inline */
```

## `!important` — the mechanism and when it's justified

`!important` moves a declaration out of the normal specificity competition and into a separate "important" bucket. Within the important bucket, specificity and order still apply — but the important bucket always wins over the normal bucket.

```css
p { color: blue !important; }          /* important bucket, (0, 0, 1) */
#id p { color: red; }                  /* normal bucket, (1, 0, 1) */
/* Result: blue — important beats normal regardless of specificity */

p { color: blue !important; }          /* important bucket, (0, 0, 1) */
#id p { color: red !important; }       /* important bucket, (1, 0, 1) */
/* Result: red — within important bucket, higher specificity wins */
```

### When `!important` is actually justified

`!important` has legitimate uses — the problem is it's used as a lazy fix rather than deliberately:

**1. Utility classes that must not be overridden**

```css
/* Utility classes in a design system — should always apply */
.sr-only {
  position: absolute !important;
  width: 1px !important;
  height: 1px !important;
  overflow: hidden !important;
  clip: rect(0, 0, 0, 0) !important;
  white-space: nowrap !important;
}
/* Component styles could have higher specificity — !important ensures these always apply */
```

**2. Overriding third-party inline styles**

```css
/* Third-party widget injects inline styles we can't control */
.widget-container {
  width: 100% !important; /* overrides the widget's inline style="width: 300px" */
}
```

**3. User accessibility overrides**

```css
/* User stylesheet forcing high-contrast mode */
* {
  background-color: black !important;
  color: white !important;
}
/* Must use !important to override any author styles */
```

**4. Animation endpoint states**

Rarely, but `!important` in `@keyframes` prevents the value from being overridden mid-animation by specificity.

**The anti-patterns:** using `!important` to fight specificity wars in your own codebase means your specificity architecture is broken. The fix is architecture (`@layer`, component scoping, lower-specificity selectors), not `!important`.

## Cascade layers — `@layer`

`@layer` was introduced in 2022 (all major browsers by end of 2022) to solve the core problem of CSS at scale: **specificity wars**.

### The problem `@layer` solves

In a large application, you have:
- Browser resets (e.g., normalize.css)
- Framework base styles
- Your design system tokens and components
- Page-specific styles
- Third-party widget styles

Without layers, all of these compete on specificity and order. A reset's `.btn` and your design system's `.btn` and the third-party's `.btn` all fight. You end up writing higher and higher specificity selectors, or scattering `!important` everywhere.

### How layers work

```css
/* Declare layer order first — lower in the list = lower priority */
@layer reset, base, components, utilities;

@layer reset {
  *, *::before, *::after { box-sizing: border-box; }
  body { margin: 0; }
}

@layer base {
  h1 { font-size: 2rem; }
  a { color: inherit; text-decoration: underline; }
}

@layer components {
  .btn {
    display: inline-flex;
    padding: 8px 16px;
    border-radius: 4px;
    font-weight: 600;
  }
  .btn-primary {
    background: #0066cc;
    color: white;
  }
}

@layer utilities {
  .mt-0 { margin-top: 0; }
  .text-center { text-align: center; }
}
```

**Priority order:** unlayered styles > `utilities` > `components` > `base` > `reset`.

The layer declared last in the `@layer` declaration wins over earlier layers. Unlayered styles (outside any `@layer`) always win over layered styles — this is intentional for gradual migration: your existing CSS without layers takes precedence over layered third-party code.

### The key insight: layers beat specificity

Within a higher-priority layer, **even a low-specificity selector beats a high-specificity selector in a lower-priority layer**:

```css
@layer base {
  #specific-id .nested-class p { color: blue; }  /* (1, 1, 1) */
}

@layer utilities {
  .text-red { color: red; }  /* (0, 1, 0) */
}
/* Result: red — utilities layer beats base layer regardless of specificity */
```

This fundamentally changes how you write CSS. Instead of escalating specificity to win, you put things in the right layer. Utility classes can be truly atomic — `(0, 1, 0)` — and still win over any component style because they're in a higher layer.

### Importing third-party CSS into a layer

```css
/* Third-party styles get contained to a layer with lower priority */
@import url('normalize.css') layer(reset);
@import url('third-party-widget.css') layer(vendor);

@layer reset, vendor, components, utilities;
/* Your components and utilities always win over vendor styles */
```

### Nested layers

```css
@layer components {
  @layer forms {
    .input { border: 1px solid #ccc; }
  }
  @layer buttons {
    .btn { padding: 8px 16px; }
  }
}
/* Accessed as: components.forms, components.buttons */
/* components.buttons > components.forms in priority */
```

### `!important` within layers — the reversal

`!important` within `@layer` reverses the layer priority — the same way origin priority reverses for `!important`:

```css
@layer base, components;

@layer base {
  .text { color: blue !important; }
}
@layer components {
  .text { color: red; }
}
/* Normal: components wins → red */
/* But with !important in base: base's !important wins → blue */
/* Because !important reverses layer order */
```

This is consistent with the origin behavior: `!important` always inverts the cascade order so that lower-priority origins/layers can protect their values.

## CSS custom properties — inheritance and cascade interaction

CSS custom properties (variables) participate in the cascade and inheritance like any other property — but with unique behaviors.

### Cascade resolution

Custom properties follow all cascade rules: specificity, layer, origin, `!important`:

```css
:root { --color: blue; }
.card { --color: green; }
#special { --color: red; }

/* .card#special → --color: red (ID specificity wins) */
```

### Inheritance

Custom properties inherit by default — they flow down the DOM like `color` or `font-size`:

```css
:root {
  --spacing: 16px;
  --brand-color: #0066cc;
}

/* All descendants can use these without redeclaring */
.button {
  padding: var(--spacing);
  background: var(--brand-color);
}

/* Override for a subtree */
.compact-section {
  --spacing: 8px;
  /* All descendants of .compact-section use 8px spacing */
}
```

### The `@property` rule — registered custom properties

Unregistered custom properties are essentially string substitution — the browser doesn't know the type. `@property` registers the type, enabling:

1. **Type checking** — invalid values are caught
2. **Animation** — custom properties can be transitioned/animated
3. **Inheritance control** — you can make a custom property non-inheriting

```css
@property --hue {
  syntax: '<number>';     /* CSS type: number */
  inherits: false;        /* does NOT inherit down the DOM */
  initial-value: 220;     /* fallback if not set */
}

@property --card-bg {
  syntax: '<color>';
  inherits: true;
  initial-value: white;
}

/* Now --hue can be animated: */
.color-wheel {
  --hue: 0;
  background: hsl(var(--hue), 70%, 60%);
  transition: --hue 0.3s ease;
}

.color-wheel:hover {
  --hue: 180;
}
```

Without `@property`, `transition: --hue 0.3s` does nothing — the browser doesn't know how to interpolate a string. With `@property` and `syntax: '<number>'`, it transitions as a number.

### The invalid-at-computed-value-time concept

Unlike regular properties, an invalid custom property value doesn't cause the declaration to be ignored — it causes the property to resolve to its **inherited value** or the **initial value**, not to the browser default:

```css
:root { --color: 16px; } /* Not a valid color, but valid as a custom property string */

p {
  color: var(--color); /* --color is 16px — invalid as a color */
  /* Result: NOT the browser default (black).
     Instead: the inherited value of 'color', or if at the root, 'initial' */
}
```

This is why custom property bugs can be hard to diagnose — invalid values don't generate DevTools warnings.

### The `var()` fallback

```css
/* Second argument is the fallback */
color: var(--primary, #0066cc);

/* Fallbacks can be nested */
color: var(--primary, var(--brand, #0066cc));

/* Fallback can be another custom property */
color: var(--button-color, var(--primary-color, blue));
```

The fallback is only used if the variable is **not defined** (or is defined as a guaranteed-invalid value). An empty string is defined — `color: var(--color, blue)` uses empty string if `--color: ;` is set.

## Practical patterns

### Escaping specificity hell with low-specificity selectors

```css
/* The single-class methodology — every selector is (0, 1, 0) */
.card { }
.card-header { }
.card-body { }
.card-footer { }

/* No nesting, no ID selectors, no element selectors for components */
/* Easy to override: add one more class */
.promotional.card { }  /* (0, 2, 0) — beats (0, 1, 0) */
```

### Design token architecture with custom properties

```css
/* Tier 1: Raw values (never used directly in components) */
:root {
  --color-blue-500: #0066cc;
  --color-blue-600: #0052a3;
  --space-4: 16px;
  --space-8: 32px;
}

/* Tier 2: Semantic tokens (component-ready) */
:root {
  --color-action: var(--color-blue-500);
  --color-action-hover: var(--color-blue-600);
  --component-spacing: var(--space-4);
}

/* Tier 3: Component tokens */
.button {
  --button-bg: var(--color-action);
  --button-bg-hover: var(--color-action-hover);
  --button-padding: var(--component-spacing);

  background: var(--button-bg);
  padding: var(--button-padding);
}

/* Theme override — change only tier 1 or tier 2 */
[data-theme="dark"] {
  --color-blue-500: #4da6ff;
  --color-blue-600: #3399ff;
}
```

## Common interview traps

**"What's the specificity of `:is(div, .class, #id)`?"**

`(1, 0, 0)` — the specificity of `:is()` equals the specificity of its most specific argument. `#id` is `(1, 0, 0)`, so the entire `:is()` selector carries that specificity even when matching via `div` or `.class`. This is different from `:where()`, which always contributes `(0, 0, 0)`.

---

**"Does an ID selector always beat any number of class selectors?"**

Yes — specificity comparison is not additive across columns. `(1, 0, 0)` beats `(0, 999, 999)`. An ID selector always beats any combination of classes, attributes, and pseudo-classes — no matter how many. The columns don't overflow into each other.

---

**"What does `@layer` do and why was it introduced?"**

`@layer` declares cascade layers — explicitly ordered buckets of CSS. Styles in a higher-priority layer win over styles in a lower-priority layer, regardless of specificity. Introduced because specificity-based conflict resolution at large scale leads to escalating selector arms races, scattered `!important` usage, and unmaintainable CSS. With layers, you put things in the right bucket and stop fighting specificity.

---

**"Does unlayered CSS win over layered CSS?"**

Yes — unlayered styles always beat layered styles in the same origin. This allows gradual migration: wrap third-party CSS in a layer, your existing unlayered CSS takes precedence without changes. This also means utility-first frameworks like Tailwind should be imported inside a layer if you want any authored styles to be able to override them without `!important`.

---

**"Can CSS custom properties be animated?"**

Only if registered via `@property` with a typed `syntax`. Unregistered custom properties are treated as strings — the browser has no interpolation algorithm for them. With `@property` and `syntax: '<color>'`, you can transition a custom property color value. Without it, `transition: --color 0.3s` is silently ignored.

---

**"What happens when you use `var(--color)` and `--color` has an invalid value for that context?"**

The invalid-at-computed-value-time behavior: the property uses its **inherited value** (if the property inherits) or its **initial value** (if it doesn't) — NOT the browser's default value. For `color`, the initial value is technically specified as `CanvasText` (browser's default for text). This is a subtle distinction that matters for debugging: you won't see the expected browser-default fallback.
