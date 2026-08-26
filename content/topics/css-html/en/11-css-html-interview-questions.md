# CSS + HTML Advanced — Interview Questions

## Group 1: Box Model and Layout

**What is the total rendered width of an element with `width: 300px`, `padding: 0 20px`, `border: 3px solid`, and the default `box-sizing`?**

`346px`. The default `box-sizing: content-box` means `width` defines only the content area, and padding and border are added on top.

```css
.box { width: 300px; padding: 0 20px; border: 3px solid; }
/* content-box (default): 300 + 20 + 20 + 3 + 3 = 346px on screen */
/* border-box:            300px on screen, content shrinks to 254px */
```

This is why the modern universal reset applies `box-sizing: border-box` to every element, including `::before` and `::after`.

---

**Explain margin collapsing. When does it happen and when doesn't it?**

Margin collapsing merges adjacent vertical margins into one margin equal to the larger of the two, not to their sum.

```css
.first  { margin-bottom: 20px; }
.second { margin-top: 30px; }
/* Gap between them: 30px, not 50px */
```

Three scenarios trigger it:

- Adjacent block siblings: the bottom margin of the first and the top margin of the second collapse.
- Parent and first or last child: if no border, padding or BFC (block formatting context) separates them, the child's margin leaks out of the parent.
- Empty blocks: an element with no height, border or padding collapses its own top and bottom margins.

It does **not** happen in flex or grid containers, on floated elements, or when a BFC separates the elements. Absolutely and fixed positioned elements are exempt too. A common gotcha: switching a layout from `display: block` to `display: flex` makes previously collapsed margins suddenly add up.

---

**What is a Block Formatting Context (BFC) and what creates one?**

A BFC is an isolated layout environment. Elements inside it do not interact with elements outside it for layout purposes: margins don't collapse across the boundary, and floats stay contained.

```css
.a { overflow: hidden; }    /* creates a BFC, but also clips content */
.b { display: flow-root; }  /* creates a BFC with zero side effects */
```

Other things that create one: `display: flex`, `display: grid`, `float`, `position: absolute`, `position: fixed`, and `contain: layout` or `contain: paint`. The practical difference between the two lines above is the side effect. Reach for `display: flow-root` when you want the BFC and nothing else.

---

**Why does `position: fixed` sometimes not fix to the viewport?**

Because an ancestor has `transform`, `filter`, `will-change: transform`, `backdrop-filter` or `perspective` applied.

```css
.ancestor { transform: translateZ(0); } /* new containing block */
.child    { position: fixed; top: 0; }  /* now fixed to .ancestor */
```

Any of these creates a new containing block that captures `position: fixed` descendants, so they position relative to that ancestor instead of the viewport. Even `transform: none` can trigger this in some browsers.

The architectural fix: render fixed-position elements — modals, toasts, drawers — as direct children of `<body>`. That is the portal pattern used by React Portal and Vue Teleport.

---

## Group 2: Flexbox

**What is the difference between `flex: 1` and `flex: 1 1 auto`?**

The `flex-basis` value.

```css
.a { flex: 1; }        /* = flex: 1 1 0%   → equal widths */
.b { flex: 1 1 auto; } /* starts from content width → unequal */
```

With `flex: 1` all items start from zero and grow proportionally, so they end up equal whatever their content. With `flex: 1 1 auto` each item starts from its own content width, and only the remaining free space is shared out. An item with more content stays larger. For truly equal columns, use `flex: 1`, or equivalently `flex-basis: 0`.

---

**A flex item has `flex-shrink: 1` but is still overflowing its container. Why?**

The `min-width: auto` default on flex items.

```css
.item { flex-shrink: 1; min-width: 0; overflow: hidden; }
/* Without min-width: 0 the item never shrinks below its content */
```

When a flex item holds intrinsic content — text, images, elements with explicit widths — `min-width: auto` resolves to the minimum content size. That is the smallest the item can be without its content overflowing, and `flex-shrink` cannot go below that floor.

Adding `min-width: 0` removes the floor and lets `flex-shrink` work. Follow it with `overflow: hidden` to contain the now-clipped content. This is also why text truncation with `text-overflow: ellipsis` needs `min-width: 0` on the flex ancestor.

---

**How does `flex-shrink` distribute the overflow between items — is it proportional to `flex-shrink` values?**

Not exactly. The shrink amount is weighted by both values: an item's weight is `flex-shrink × flex-basis`.

```
A: flex-shrink: 2, flex-basis: 200px → weight 400
B: flex-shrink: 1, flex-basis: 200px → weight 200
Overflow is shared out in the ratio 400 : 200
```

Items with a larger `flex-basis` therefore shrink more in absolute pixels when `flex-shrink` values are equal. The algorithm is designed that way, to avoid shrinking small items disproportionately.

---

**How do you push one flex item to the far end of the main axis while keeping others at the start?**

Use `margin-left: auto` on the item you want pushed right, or `margin-inline-start: auto` if you prefer logical properties.

```css
.nav { display: flex; }
.nav .login { margin-left: auto; } /* absorbs all free space */
```

In flexbox, an `auto` margin absorbs all available free space in that direction. Note that `justify-self` does not work on flex items at all; it is a grid-only property. Putting `margin-right: auto` on the last left-side item gives the same result from the other end.

---

## Group 3: CSS Grid

**What is the precise meaning of `1fr` — is it one fraction of the container width?**

No — one fraction of the **available free space**, not of the container width. Free space is what remains after every fixed-size track (px, em, %) and every gap is resolved.

```
Container 900px, one 200px column, two 1fr columns, 20px gaps
Free space: 900 - 200 - 2×20 = 660px
Each fr:    660 / 2 = 330px
```

This is why `fr` is preferred over `%`. Percentage columns are measured against the full width, gaps included, so they can overflow. An `fr` column always fits.

---

**What is the difference between `auto-fill` and `auto-fit` in `repeat()`?**

Both create as many tracks as fit in the container. The difference appears when there are fewer items than track slots.

```css
grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
/* empty tracks stay; items never exceed their minmax max */
grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
/* empty tracks collapse to 0; items stretch to the full width */
```

With enough items to fill every track, the two behave identically. Use `auto-fit` for the common responsive grid without media queries. Use `auto-fill` when items should keep their minimum size even if that leaves empty columns.

---

**How does `grid-column: 1 / -1` work, and what is `-1`?**

Line `-1` refers to the last line of the **explicit** grid, so `grid-column: 1 / -1` spans from the first to the last explicit column line.

```css
.grid { grid-template-columns: repeat(4, 1fr); } /* 5 column lines */
.banner { grid-column: 1 / -1; }                 /* spans all four */
```

The caveat: `-1` only works for the explicit grid. Items placed in the implicit grid, in extra auto-generated rows, cannot use `-1` to span the full width unless those rows are declared in `grid-template-rows`.

---

**What is subgrid and what problem does it solve?**

Subgrid lets a grid item that is itself a grid container inherit the parent's track structure instead of copying it.

```css
.card { display: grid; grid-row: span 3; grid-template-rows: subgrid; }
/* header, body and footer now sit on the parent's row tracks */
```

The problem it solves shows up in a card grid. Every card has a header, a body and a footer, and cards with different content heights push their footers to different levels. With subgrid all cards share the parent's row tracks, so the three parts line up whatever the content. All major browsers support it since Chrome 117 (August 2023).

---

## Group 4: Stacking Context and z-index

**Why doesn't `z-index: 9999` guarantee an element appears on top?**

Because z-index is local to a stacking context. Elements only compete on z-index inside the same stacking context.

```css
.ctx-x { position: relative; z-index: 1; }  /* contains element A */
.ctx-y { position: relative; z-index: 2; }  /* contains element B */
.a     { z-index: 9999; }  /* still painted under everything in .ctx-y */
```

Context X renders below context Y as a whole, element A included. The fix is always at the stacking context level, never on the inner element.

---

**Name five things that create a stacking context beyond `position` + `z-index`.**

Any one of these is enough:

- `opacity` below 1, even `opacity: 0.99`
- `transform` with any value other than `none`, including `translateZ(0)` hacks that force a layer onto the GPU (graphics processing unit)
- `filter` with any value other than `none`
- `will-change` naming a compositing property, such as `will-change: transform`
- `isolation: isolate`
- `contain: layout`, `paint`, `strict` or `content`
- `mix-blend-mode` other than `normal`, and `clip-path` other than `none`
- `backdrop-filter`
- `position: fixed` and `position: sticky`, always, whatever the z-index

The practical implication is worth remembering. A seemingly innocent `transform: translateX(0)` on a sidebar traps every absolutely positioned child, so their z-index values now compete only inside the sidebar.

---

**What is `isolation: isolate` and when would you use it?**

It creates a stacking context with no visual side effects: no opacity change, no transform, no filter.

```css
.widget { isolation: isolate; } /* z-index inside stays inside */
```

Two main use cases. The first is containing a component's internal z-index values so they don't compete with the outside world. A design system component can use `z-index: 10` internally without disturbing a page modal at `z-index: 2`. The second is stopping `mix-blend-mode` from blending with elements beyond the component boundary. It is the CSS equivalent of a module boundary for stacking.

---

## Group 5: Specificity and Cascade

**What is the specificity of `:is(div, .class, #id) p`, and why?**

`(1, 0, 1)`. The `:is()` pseudo-class takes the specificity of its **most specific argument**.

```css
:is(div, .class, #id) p  /* (1, 0, 0) from #id + (0, 0, 1) from p */
:where(div, .class, #id) p  /* (0, 0, 0) + (0, 0, 1) = (0, 0, 1) */
```

The maximum of the list is used even when the element actually matched through `div` or `.class`. That is the critical difference from `:where()`, which always contributes `(0, 0, 0)` whatever its arguments.

---

**What are cascade layers (`@layer`) and why were they introduced?**

`@layer` declares explicitly ordered buckets of CSS. Rules in a higher-priority layer beat rules in a lower-priority layer, whatever the specificity.

```css
@layer reset, base, components, utilities;
/* declaration order sets priority: utilities is the strongest layer */
/* .p-4 (0,1,0) in utilities beats .card .title:hover (0,3,0) in components */
```

Styles that are in no layer at all always beat layered styles. Layers were introduced to end specificity wars at scale. Without them all CSS competes on specificity and source order, which produces ever-escalating selectors and `!important` scattered through the codebase.

---

**What happens when a CSS custom property has an invalid value for its usage context?**

This is the invalid-at-computed-value-time behavior. The property resolves to its **inherited value** if it inherits, or to its **initial value** if it does not — and **not** to the browser default.

```css
:root { --color: 16px; }
p { color: var(--color); } /* invalid for color */
/* Result: the inherited color, not black */
```

That is why bugs in custom properties are hard to debug. There is no console error, and the fallback behavior is not the one you would guess.

---

## Group 6: Responsive and Modern CSS

**What problem do container queries solve that media queries cannot?**

Components adapting to their container's actual size rather than to the global viewport size.

```css
.sidebar, .main { container-type: inline-size; }
@container (min-width: 400px) { .card { display: grid; } }
```

The same card in a 280px sidebar and in a 600px main area needs different layouts at one and the same viewport width. Media queries only know the viewport, so they cannot tell the two placements apart. Container queries make the component truly reusable: same component, same CSS, correct layout at any container width.

---

**Explain `clamp(1rem, 2.5vw, 2rem)` precisely.**

The value is `2.5vw`, the preferred viewport-relative expression, clamped to a minimum of `1rem` and a maximum of `2rem`.

```
400px  viewport: 2.5vw = 10px < 16px (1rem)  → clamps to 1rem
800px  viewport: 2.5vw = 20px, between bounds → uses 20px
1400px viewport: 2.5vw = 35px > 32px (2rem)  → clamps to 2rem
```

Between the two extremes the value moves continuously, with no jumps at breakpoints. One declaration replaces two media query breakpoints.

---

**What is the difference between `margin-left` and `margin-inline-start`?**

`margin-left` is a physical property: it always means the left side, whatever the writing direction. The logical property `margin-inline-start` maps to the start of the inline direction, following `direction` and `writing-mode`.

```css
.icon { margin-inline-start: 8px; }
/* left-to-right (LTR): margin-left  */
/* right-to-left (RTL): margin-right */
/* vertical writing mode: top or bottom */
```

The benefit: right-to-left and vertical-script layouts need zero `[dir="rtl"]` overrides, because the browser does the mapping. For international applications, logical properties should be the default.

---

## Group 7: Rendering Pipeline and Performance

**Name the five stages of the browser rendering pipeline and what each does.**

```
Parse → Style → Layout → Paint → Composite → Screen
```

1. **Parse** — HTML becomes the DOM (Document Object Model), CSS becomes the CSSOM (CSS Object Model), and the two merge into the Render Tree. CSS is render-blocking, and a `<script>` without `async` or `defer` is parser-blocking.
2. **Style (Recalculate Style)** — computes the final style of every element: cascade, inheritance, custom properties, and relative units resolved to absolute pixels.
3. **Layout (Reflow)** — calculates geometry, the position and size of every element. The most expensive stage, because it cascades through the document.
4. **Paint** — records drawing instructions, commands rather than pixels, for each layer: backgrounds, borders, text, shadows.
5. **Composite** — the GPU combines layers into the final frame, applying transforms and opacity.

Only two CSS properties trigger this last stage alone: `transform` and `opacity`.

---

**Which CSS properties trigger only Composite and why? Why not `left`/`top`?**

Only `transform` and `opacity`. They don't affect geometry, so no Layout is needed, and they don't change the pixel appearance of the element itself, so no Paint is needed.

```css
.smooth { transition: transform 200ms; } /* Composite only */
.janky  { transition: left 200ms; }      /* Layout + Paint + Composite */
```

The browser promotes the element to a GPU compositing layer and uploads its texture once. Every later change is handled by the GPU alone: a matrix transformation or an alpha blend per frame.

`left` and `top` are layout properties. Changing them moves the element in the document flow, which means recalculating the positions of surrounding elements, re-recording drawing commands, and only then compositing. That is work for the CPU (central processing unit) on every single frame. It is why `left` animations are prone to **jank**: the visible stutter you get when the browser misses frames.

---

**What is layout thrashing and how do you fix it?**

Layout thrashing happens when JavaScript alternates reads and writes of layout-affecting DOM properties inside a loop.

```javascript
// Thrashing: every offsetWidth read forces a synchronous reflow
boxes.forEach(b => { b.style.width = b.offsetWidth * 2 + 'px'; });

// Fixed: read everything, then write everything
const w = boxes.map(b => b.offsetWidth);
boxes.forEach((b, i) => { b.style.width = w[i] * 2 + 'px'; });
```

Each read, such as `offsetWidth` or `getBoundingClientRect()`, forces the browser to flush pending style and layout changes to return an up-to-date value. Each write then invalidates layout again.

Batching turns that into one reflow for all the reads and one layout update for all the writes. Scheduling the writes inside `requestAnimationFrame` puts them at the right point in the pipeline.

---

**What does `will-change: transform` actually do, and what are the risks?**

It signals to the browser that the element's `transform` will change soon. The browser usually responds by promoting the element to a GPU compositing layer early, before the animation starts. Creating the layer then does not stutter the first frame.

```css
.card:hover { will-change: transform; } /* prepare on hover */
* { will-change: transform; }           /* never do this */
```

Two risks. Each promoted layer occupies video memory on the graphics card. And when a promoted element overlaps many non-promoted ones, the browser may promote all of them to avoid rendering artifacts. That is a layer explosion.

Rules for responsible use: apply it immediately before the animation begins, and remove it with `will-change: auto` immediately after it ends. Never apply it to every element.

---

## Group 8: CSS Architecture and Forms

**Why does BEM use single classes instead of descendant selectors?**

Single classes have uniform specificity `(0, 1, 0)`, so no specificity conflict is possible inside a BEM (Block, Element, Modifier) codebase.

```css
.card .title  { }  /* (0, 2, 0) — breaks if .title moves out of .card */
.card__title  { }  /* (0, 1, 0) — relationship lives in the name */
```

BEM encodes the relationship in the name, not in selector nesting. Overriding any BEM style is therefore trivial: one class above `(0, 1, 0)` wins. The trade-off is that BEM does not solve global scope. Two developers can still create `.card__title` with conflicting intentions.

---

**What is the main performance concern with runtime CSS-in-JS (Styled Components, Emotion)?**

Style injection happens in JavaScript on the main thread during rendering. Every render with new prop values generates new CSS rules and injects or updates `<style>` tags, which adds to Time to Interactive.

With SSR (server-side rendering) the styles must also be serialized into the HTML payload and reconciled again on the client during hydration. The extra bundle size from the style definitions increases JavaScript parse time on top of that.

These costs became a blocking concern with React Server Components: runtime CSS-in-JS needs a browser JavaScript environment, and RSC does not have one. Zero-runtime alternatives such as vanilla-extract and StyleX generate CSS at build time, so the runtime cost disappears.

---

**What does `novalidate` on a `<form>` do, and why would you want it?**

`novalidate` disables the browser's native validation interface — the platform-styled popup bubbles and the focusing behavior on submit — while keeping the Constraint Validation API fully active.

```html
<form novalidate>
  <!-- input.validity, checkValidity(), setCustomValidity() all still work -->
</form>
```

You want it when you build your own validation experience. That means controlling when errors appear — on blur, not only on submit. It also means the visual design of error messages, focus management on invalid fields, cross-field validation and server-side error integration. The native interface supports none of those.

---

**What is `setCustomValidity` and what is the critical rule about clearing it?**

`setCustomValidity(message)` sets a custom validation error message on a form control. A non-empty string marks the field invalid, sets `validity.customError = true`, and puts the message in `validationMessage`.

```javascript
input.setCustomValidity('This email is already registered');
input.addEventListener('input', () => input.setCustomValidity(''));
```

The critical rule is the second line. You must clear the error with an empty string when the user modifies the field. Otherwise it persists forever, and the field stays invalid even when the user types a perfectly valid value.

---

**Why is native HTML form validation insufficient for production, even if the server validates everything?**

Five reasons:

1. **The validation interface is uncontrollable.** Browser popup bubbles cannot be styled or positioned to match a design system.
2. **The timing is wrong.** Native validation only fires on submit. Best practice is to validate on blur, when the user first leaves the field, and then on every input after the first error.
3. **Cross-field validation is impossible.** Password confirmation, date range constraints and conditionally required fields cannot be expressed in HTML attributes.
4. **Server errors cannot be shown.** A duplicate email or an invalid coupon code has no native display mechanism, so `setCustomValidity` and JavaScript are required.
5. **Async validation is impossible.** Checking whether a username is free needs an API call, and a `pattern` attribute cannot make one.

---

## Group 9: Accessibility and Semantics

**What is the accessibility tree and why does it matter?**

The accessibility tree is a parallel representation of the page that browsers build from semantic HTML and ARIA (Accessible Rich Internet Applications) attributes. Screen readers, braille displays, voice control software and other assistive technologies read that tree, not the DOM and not the visual layout.

```html
<div class="btn" onclick="submit()">Submit</div> <!-- no role, no tab stop -->
<button type="submit">Submit</button>            <!-- role, tab stop, keys -->
```

The `<div>` appears in the DOM, but in the accessibility tree it has no role, no keyboard affordance and no state. The `<button>` has `role=button`, sits in the tab order, activates on Space and Enter, and carries a disabled state. Every `<div>` used where a semantic element exists re-implements by hand what the browser gives for free.

---

**When is ARIA helpful and when is it harmful?**

Helpful in three cases:

- Custom interactive widgets with no HTML equivalent: tab lists, tree views, comboboxes.
- Dynamic state changes that must be announced to screen readers, through `aria-expanded` or `aria-live`.
- Labelling elements that cannot use `<label>`, such as icon buttons and landmark regions.

Harmful in three others:

- When it overrides correct native semantics, such as `role="button"` on a `<div>` that never handles keyboard events.
- When `aria-hidden="true"` sits on a container that has focusable children, which creates a black hole for focus.
- When an incorrect role misleads assistive technologies.

The guiding principle: **no ARIA is better than bad ARIA**. Always prefer native HTML semantics, and add ARIA only where they fall short.

---

**What is the roving tabindex pattern and when is it used?**

Roving tabindex is for composite widgets, where Tab moves between widgets and Arrow keys move inside one. Tab lists, toolbars, radio groups and tree views all use it.

```html
<div role="tablist">
  <button role="tab" tabindex="0">General</button>   <!-- active item -->
  <button role="tab" tabindex="-1">Privacy</button>  <!-- reachable by Arrow -->
</div>
```

Exactly one item carries `tabindex="0"` at any time, and every other item carries `tabindex="-1"`. Arrow key handlers move focus by swapping those two values.

The widget is then a single Tab stop for the page. A keyboard user does not have to Tab through every tab in a tab list just to leave the component.

---

## Group 10: Advanced and Cross-cutting

**How would you debug a z-index issue where an element appears behind another despite having a higher z-index?**

Four steps:

1. **Identify the stacking context chain for both elements.** Walk up the DOM from each one and note every ancestor that creates a stacking context. Check `position` with `z-index`, `opacity` below 1, `transform`, `filter`, `will-change`, `isolation` and `contain`.
2. **Find the common ancestor stacking context.** The comparison that matters happens at that level, between the two contexts, not between the elements' own z-index values.
3. **Fix at the right level.** Adjust the z-index of the containing stacking context, not of the inner element.
4. **Consider the portal pattern.** If the element lives inside a component such as a sidebar or a card, render overlays as children of `<body>` and sidestep containment entirely.

---

**What is the difference between `contain: layout`, `contain: paint`, and `contain: strict`?**

Three levels of containment:

- `contain: layout` — internal layout changes don't affect the outside and vice versa, so the browser can reflow the subtree on its own. Side effects: the element becomes a stacking context, a BFC, and a containing block for positioned descendants.
- `contain: paint` — the element acts as a viewport for its subtree, and descendants cannot overflow it visually. It creates the same three things, and behaves like `overflow: hidden` with extra performance signals.
- `contain: strict` — `layout + paint + size + style`, the strongest form. It requires explicit `width` and `height`, because size containment means the browser ignores descendants when sizing the element.

Use `contain: strict` for fixed-size components that update often, such as thumbnails and grid items, where isolated reflows matter for performance.

---

**Compare three approaches to responsive typography: media query breakpoints, `vw` units, and `clamp()`.**

```css
@media (min-width: 768px) { html { font-size: 18px; } } /* steps */
html { font-size: 2vw; }                                /* unbounded */
html { font-size: clamp(1rem, 2.5vw, 1.5rem); }         /* bounded */
```

- **Media query breakpoints** give explicit steps: 16px below 768px, 18px above. Simple, but the jumps at each breakpoint are jarring, and every extra breakpoint adds maintenance surface.
- **`vw` units** scale continuously, but have no floor and no ceiling. Text goes unreadably small on phones and unreadably large on wide monitors, so it needs clamping through JavaScript or extra breakpoints.
- **`clamp()`** combines continuous scaling with enforced bounds. It moves smoothly between a mobile floor and a desktop ceiling without a single media query.

The last one is the preferred modern approach: one declaration handles every viewport size.

---

**When would you choose CSS Modules over Tailwind, and vice versa?**

**CSS Modules over Tailwind** when component styles involve complex pseudo-element designs, intricate animations or deeply conditional logic. Also when the styles simply read better as one cohesive block than as fifteen utility classes.

The same choice fits a team with strong CSS expertise that prefers writing styles explicitly. It also fits a design system built on CSS custom properties rather than on utility class mappings.

**Tailwind over CSS Modules** when iteration speed matters, because there is no file switching and the styles sit next to the markup. It also wins when you want a design system enforced by constraints such as the `spacing-4` scale. A component framework that hides class list repetition helps too. Bundle size is a third argument: Tailwind purges unused utilities, so the shipped CSS stays minimal.
