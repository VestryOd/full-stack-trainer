# CSS + HTML Advanced — Interview Questions

## Group 1: Box Model and Layout

**What is the total rendered width of an element with `width: 300px`, `padding: 0 20px`, `border: 3px solid`, and the default `box-sizing`?**

`346px`. The default `box-sizing: content-box` means `width` defines only the content area. Padding and border are added on top: `300 + 20 + 20 + 3 + 3 = 346px`. With `box-sizing: border-box` the total would be `300px` — the content area shrinks to `254px` to accommodate padding and border. This is why the modern universal reset applies `box-sizing: border-box` to every element including `::before` and `::after`.

---

**Explain margin collapsing. When does it happen and when doesn't it?**

Margin collapsing merges adjacent vertical margins into a single margin equal to the larger of the two (not their sum). Three scenarios trigger it: (1) adjacent block siblings — the bottom margin of the first and top margin of the second collapse; (2) parent and first/last child — if no border, padding, or BFC separates them, the child's margin "leaks" out of the parent; (3) empty blocks — an element with no height, border, or padding collapses its own top and bottom margins. It does NOT occur in flex/grid containers, on floated elements, on `position: absolute/fixed` elements, or when a BFC separates the elements. A common gotcha: switching a layout from `display: block` to `display: flex` makes previously-collapsed margins suddenly add up, increasing spacing between elements.

---

**What is a Block Formatting Context (BFC) and what creates one?**

A BFC is an isolated layout environment where internal elements do not interact with external elements for layout purposes — margins don't collapse across BFC boundaries, floats are contained inside. Creating a BFC: `overflow` other than `visible`, `display: flow-root` (explicit, no side effects), `display: flex/grid`, `float`, `position: absolute/fixed`, `contain: layout/paint`. The practical difference between `overflow: hidden` (BFC hack) and `display: flow-root` (intentional BFC): `overflow: hidden` clips content and has that side effect; `display: flow-root` creates a BFC with zero side effects.

---

**Why does `position: fixed` sometimes not fix to the viewport?**

Because an ancestor has `transform`, `filter`, `will-change: transform`, `backdrop-filter`, or `perspective` applied. Any of these creates a new containing block that captures `position: fixed` descendants, causing them to position relative to that ancestor instead of the viewport. Even `transform: none` can trigger this in some browsers. The architectural fix: render fixed-position elements (modals, toasts, drawers) as direct children of `<body>` — the portal pattern used by React Portal and Vue Teleport.

---

## Group 2: Flexbox

**What is the difference between `flex: 1` and `flex: 1 1 auto`?**

The `flex-basis` value. `flex: 1` expands to `flex: 1 1 0%` — all items start from zero and grow proportionally, resulting in equal widths regardless of content. `flex: 1 1 auto` uses each item's content width as the starting point, then distributes only the remaining free space proportionally — a larger-content item stays larger. To get truly equal-width columns: use `flex: 1` (or equivalently, `flex-basis: 0`).

---

**A flex item has `flex-shrink: 1` but is still overflowing its container. Why?**

The `min-width: auto` default on flex items. When a flex item contains intrinsic content (text, images, elements with explicit widths), `min-width: auto` resolves to the minimum content size — the smallest the item can be without its content overflowing. `flex-shrink` cannot shrink the item below this floor. Fix: add `min-width: 0` to the flex item, which removes the floor and lets `flex-shrink` work correctly. Follow with `overflow: hidden` to contain the now-clipped content. This is also the reason text truncation with `text-overflow: ellipsis` requires `min-width: 0` on the flex ancestor.

---

**How does `flex-shrink` distribute the overflow between items — is it proportional to `flex-shrink` values?**

Not exactly. The shrink amount is weighted by both `flex-shrink` and `flex-basis`: each item's weight = `flex-shrink × flex-basis`. An item with `flex-shrink: 2, flex-basis: 200px` has weight `400`; an item with `flex-shrink: 1, flex-basis: 200px` has weight `200`. The overflow is distributed proportionally by these weighted factors. This means items with a larger `flex-basis` shrink more in absolute pixels when `flex-shrink` values are equal — the algorithm is designed to avoid disproportionate shrinking relative to item size.

---

**How do you push one flex item to the far end of the main axis while keeping others at the start?**

`margin-left: auto` (or `margin-inline-start: auto` for logical properties) on the item to push right. In flexbox, `auto` margins absorb all available free space in the specified direction. `justify-self` does not work on flex items — it's a grid-only property. Equivalently, `margin-right: auto` on the last "left-side" item achieves the same result by pushing everything after it to the right.

---

## Group 3: CSS Grid

**What is the precise meaning of `1fr` — is it one fraction of the container width?**

No — one fraction of the **available free space**, not the container width. Free space is what remains after all fixed-size tracks (px, em, %) and gaps are resolved. In a 900px container with a 200px fixed column, a 20px gap, and two `1fr` columns: free space = `900 - 200 - 2×20 = 660px`, so each `fr` = `330px`. This is why `fr` is preferred over `%` — percentage columns include gap space and can overflow, while `fr` always fits.

---

**What is the difference between `auto-fill` and `auto-fit` in `repeat()`?**

Both create as many tracks as fit in the container. The difference appears when there are fewer items than available track slots. `auto-fill` keeps empty tracks — items don't grow beyond their `max` in `minmax()`. `auto-fit` collapses empty tracks to zero — items expand to fill the full container width. With enough items to fill all tracks both behave identically. Use `auto-fit` for the common "responsive grid without media queries" pattern; use `auto-fill` when you want items to maintain minimum size even if that leaves empty columns.

---

**How does `grid-column: 1 / -1` work, and what is `-1`?**

Line `-1` refers to the last line of the **explicit** grid. `grid-column: 1 / -1` spans from the first to the last explicit column line — full width. With `grid-template-columns: repeat(4, 1fr)` there are 5 column lines (1 through 5), so `1 / -1` spans all 4 columns. Caveat: `-1` only works for the explicit grid. Items placed in the implicit grid (extra auto-generated rows) cannot use `-1` to span full width unless those rows are explicitly defined in `grid-template-rows`.

---

**What is subgrid and what problem does it solve?**

Subgrid (`grid-template-columns: subgrid` or `grid-template-rows: subgrid`) allows a grid item that is itself a grid container to inherit — not copy — the parent's track structure. The problem it solves: in a card grid where each card has a header, body, and footer, if cards have different content heights their footers don't align horizontally across cards. With subgrid, all cards share the parent's row tracks, so headers, bodies, and footers align automatically regardless of content height. Supported in all major browsers since Chrome 117 (August 2023).

---

## Group 4: Stacking Context and z-index

**Why doesn't `z-index: 9999` guarantee an element appears on top?**

Because z-index is local to a stacking context. Elements only compete on z-index within the same stacking context. If element A lives in stacking context X (z-index: 1) and element B lives in stacking context Y (z-index: 2), then A's z-index: 9999 doesn't matter — the entire context X (including A) renders below the entire context Y (including B). The fix is always at the stacking context level, not on the inner element.

---

**Name five things that create a stacking context beyond `position` + `z-index`.**

`opacity` less than 1 (even `opacity: 0.99`), `transform` any non-none value (including `translateZ(0)` GPU hacks), `filter` any non-none value, `will-change` pointing to compositing properties (`will-change: transform`), `isolation: isolate`, `contain: layout/paint/strict/content`, `mix-blend-mode` non-normal, `clip-path` non-none, `backdrop-filter`, `position: fixed` or `sticky` (always, regardless of z-index value). The practical implication: a seemingly innocent `transform: translateX(0)` for GPU compositing on a sidebar will trap all absolutely-positioned children, causing their z-index values to be contained within the sidebar's stacking context.

---

**What is `isolation: isolate` and when would you use it?**

It creates a stacking context with no visual side effects — no opacity change, no transform, no filter. Primary use cases: (1) containing a component's internal z-index values so they don't compete with external elements — a design system component can use z-index: 10 internally without interfering with the page's z-index: 2 modal; (2) preventing `mix-blend-mode` from blending with elements outside the component boundary. It's the CSS equivalent of a module boundary for stacking.

---

## Group 5: Specificity and Cascade

**What is the specificity of `:is(div, .class, #id) p`, and why?**

`(1, 0, 1)`. The `:is()` pseudo-class takes the specificity of its **most specific argument** — `#id` is `(1, 0, 0)`, so `:is(...)` contributes `(1, 0, 0)`. The `p` type selector adds `(0, 0, 1)`. Total: `(1, 0, 1)`. This applies even when the element matches via `.class` or `div` — the full list's maximum specificity is always used. This is the critical difference from `:where()`, which always contributes `(0, 0, 0)` regardless of its arguments.

---

**What are cascade layers (`@layer`) and why were they introduced?**

`@layer` declares explicitly ordered buckets of CSS. Rules in a higher-priority layer beat rules in a lower-priority layer regardless of specificity. The declaration order sets priority: `@layer reset, base, components, utilities` — utilities have the highest priority. Unlayered styles always beat layered styles. Introduced to solve specificity wars at scale: without layers, all CSS competes on specificity and source order, leading to ever-escalating selectors and scattered `!important`. With layers, you put code in the right bucket and stop fighting specificity — a utility class with `(0, 1, 0)` in the `utilities` layer beats a component rule with `(1, 2, 3)` in the `components` layer.

---

**What happens when a CSS custom property has an invalid value for its usage context?**

Invalid-at-computed-value-time behavior: the property resolves to its **inherited value** (if it inherits) or its **initial value** (if it doesn't) — NOT the browser default. For example, `:root { --color: 16px }` then `p { color: var(--color) }` — the `color` property receives an invalid value. The result is not `black` (browser default) but the inherited value of `color` from the parent, or `initial` if at the root. This is why CSS custom property bugs are hard to debug — there's no console error, and the fallback behavior is non-obvious.

---

## Group 6: Responsive and Modern CSS

**What problem do container queries solve that media queries cannot?**

Components adapting to their container's actual size rather than the global viewport size. A card component in a 280px sidebar and the same card in a 600px main area need different layouts at the same viewport width. Media queries only know the viewport width — they can't distinguish these two placements. Container queries let the card respond to the space it actually occupies: `@container (min-width: 400px) { .card { display: grid; } }`. This makes components truly reusable — the same component, the same CSS, correct layout in any container width.

---

**Explain `clamp(1rem, 2.5vw, 2rem)` precisely.**

The value is `2.5vw` (the preferred, viewport-relative expression), clamped to a minimum of `1rem` and a maximum of `2rem`. At a 400px viewport: `2.5vw = 10px < 16px (1rem)` → clamps to `1rem`. At an 800px viewport: `2.5vw = 20px`, between min and max → uses `20px`. At a 1400px viewport: `2.5vw = 35px > 32px (2rem)` → clamps to `2rem`. The value transitions continuously between the extremes — no breakpoint jumps. This replaces two media query breakpoints with a single fluid expression.

---

**What is the difference between `margin-left` and `margin-inline-start`?**

`margin-left` is a physical property — always the left side regardless of writing direction. `margin-inline-start` is a logical property — maps to the start of the inline direction based on `direction` and `writing-mode`. In LTR they're identical. In RTL, `margin-inline-start` maps to `margin-right`. In a vertical writing mode (Japanese), it maps to the top or bottom. The benefit: RTL and vertical-script layouts require zero `[dir="rtl"]` overrides — the browser maps logical properties automatically. For international applications, logical properties should be the default.

---

## Group 7: Rendering Pipeline and Performance

**Name the five stages of the browser rendering pipeline and what each does.**

(1) **Parse**: HTML → DOM, CSS → CSSOM, merged into Render Tree. CSS is render-blocking; `<script>` without `async`/`defer` is parser-blocking. (2) **Style (Recalculate Style)**: computes the final computed style for every element — resolves cascade, inheritance, custom properties, relative units to absolute pixels. (3) **Layout (Reflow)**: calculates geometry — position and size of every element. Most expensive — cascades through the document. (4) **Paint**: records drawing instructions (commands, not pixels) for each layer — backgrounds, borders, text, shadows. (5) **Composite**: GPU combines layers into the final frame, applying transforms and opacity. Only two CSS properties trigger exclusively this last stage: `transform` and `opacity`.

---

**Which CSS properties trigger only Composite and why? Why not `left`/`top`?**

Only `transform` and `opacity`. They don't affect geometry (no Layout needed) and don't change the pixel appearance of the element itself (no Paint needed). The browser promotes the element to a GPU compositing layer, uploads its texture once, and subsequent changes are handled entirely by the GPU — applying a matrix transformation or alpha blend each frame. `left`/`top` are layout properties — changing them moves the element in the document flow, which requires recalculating positions of surrounding elements (Layout), then re-recording drawing commands (Paint), then compositing. On every frame this is CPU-bound work, which is why `transform: translateX()` animations are smooth and `left:` animations are jank-prone.

---

**What is layout thrashing and how do you fix it?**

Layout thrashing occurs when JavaScript alternates between reading layout-affecting DOM properties and writing to them in a loop. Each read (e.g., `offsetWidth`, `getBoundingClientRect()`) forces the browser to flush any pending style/layout changes and compute an up-to-date value — a synchronous reflow. Each write then invalidates layout. Interleaving them causes N synchronous reflows per loop iteration. Fix: batch all reads first, then batch all writes. The browser performs one reflow for the reads and one layout update for the writes. `requestAnimationFrame` helps schedule writes to happen at the correct point in the rendering pipeline.

---

**What does `will-change: transform` actually do, and what are the risks?**

It signals to the browser that the element's `transform` will change soon. The browser typically responds by promoting the element to a GPU compositing layer early — before the animation starts — so the first frame of animation doesn't cause a jank from layer creation. Risks: each promoted layer consumes GPU memory (VRAM), and when a promoted element overlaps many non-promoted elements the browser may promote all of them to avoid rendering artifacts ("layer explosion"). Rules for responsible use: apply immediately before the animation begins, remove (`will-change: auto`) immediately after it ends. Never apply to all elements globally.

---

## Group 8: CSS Architecture and Forms

**Why does BEM use single classes instead of descendant selectors?**

Single classes have uniform specificity `(0, 1, 0)` — no specificity conflicts are possible within a BEM codebase. Descendant selectors (`.card .title`) have higher specificity `(0, 2, 0)` and couple the selector to the DOM structure — if `.title` moves outside `.card`, the style breaks. BEM encodes the relationship in the name (`.card__title`), not in selector nesting. This means overriding any BEM style is trivial: one class above `(0, 1, 0)` wins. The tradeoff: BEM doesn't solve global scope — two developers can still create `.card__title` with conflicting intentions.

---

**What is the main performance concern with runtime CSS-in-JS (Styled Components, Emotion)?**

Style injection happens in JavaScript on the main thread during rendering. Every render with new prop values generates new CSS rules and injects/updates `<style>` tags, adding to Time to Interactive. On SSR, styles must be serialized into the HTML payload and re-reconciled on the client during hydration. The additional bundle size from style definitions further increases JavaScript parse time. These costs became a blocking concern with React Server Components — runtime CSS-in-JS requires a browser JavaScript environment that RSC doesn't have. Zero-runtime alternatives (vanilla-extract, StyleX) generate CSS at build time, eliminating runtime cost.

---

**What does `novalidate` on a `<form>` do, and why would you want it?**

`novalidate` disables the browser's native validation UI (the platform-styled popup bubbles and field focusing behavior on submit) while keeping the Constraint Validation API fully active. `input.validity`, `input.checkValidity()`, and `input.setCustomValidity()` all continue to work. You want it when building custom validation UX: controlling when errors appear (on blur, not just on submit), the visual design of error messages, focus management on invalid fields, cross-field validation, and server-side error integration — none of which the native UI supports.

---

**What is `setCustomValidity` and what is the critical rule about clearing it?**

`setCustomValidity(message)` sets a custom validation error message on a form control. A non-empty string marks the field as invalid (`validity.customError = true`) and the message appears in `validationMessage`. Critical rule: you must call `setCustomValidity('')` (empty string) when the user modifies the field — otherwise the custom error persists permanently regardless of what the user types. The field stays invalid even if the user enters a perfectly valid value. Standard pattern: set the error after server response, clear it on the field's `input` event.

---

**Why is native HTML form validation insufficient for production, even if the server validates everything?**

Five reasons: (1) **Validation UI is uncontrollable** — browser popup bubbles can't be styled or positioned to match a design system. (2) **Timing is wrong** — native validation only fires on submit; best practice requires validating on blur (first exit) then on input (after first error). (3) **Cross-field validation is impossible** — password confirmation matching, date range constraints, and conditional required fields can't be expressed in HTML attributes. (4) **Server errors can't be shown** — after submission, server rejections (duplicate email, invalid coupon code) have no native display mechanism; `setCustomValidity` + JavaScript is required. (5) **Async validation is impossible** — checking username availability requires an API call that `pattern` attributes can't make.

---

## Group 9: Accessibility and Semantics

**What is the accessibility tree and why does it matter?**

The accessibility tree is a parallel representation of the page that browsers build from semantic HTML and ARIA attributes. Screen readers, braille displays, voice control software, and other assistive technologies read the accessibility tree — not the DOM, not the visual layout. A `<div onclick>` appears in the DOM but has no role, no keyboard affordance, and no state in the accessibility tree. A `<button>` has role=button, is in the tab order, is activatable by Space and Enter, and has a disabled state. Every `<div>` used where a semantic element exists is a manual re-implementation of behavior the browser provides for free.

---

**When is ARIA helpful and when is it harmful?**

Helpful: (1) custom interactive widgets with no HTML equivalent (tab lists, tree views, comboboxes); (2) dynamic state changes announced to screen readers (`aria-expanded`, `aria-live`); (3) labelling elements that can't use `<label>` (icon buttons, landmark regions). Harmful: when it overrides correct native semantics (`role="button"` on a `<div>` that doesn't handle keyboard events), when `aria-hidden="true"` is placed on a container with focusable children (black-hole focus), when incorrect roles mislead assistive technologies. The guiding principle: **no ARIA is better than bad ARIA**. Always prefer native HTML semantics; add ARIA only when native semantics are insufficient.

---

**What is the roving tabindex pattern and when is it used?**

Roving tabindex is used for composite widgets where Tab moves between widgets and Arrow keys move within the widget — tab lists, toolbars, radio groups, tree views. The pattern: at any time, exactly one item has `tabindex="0"` (the currently active item); all other items have `tabindex="-1"`. Arrow key handlers move focus by setting the new item to `tabindex="0"` and the previous item back to `tabindex="-1"`. This ensures the widget is a single Tab stop for keyboard users navigating the page — they don't have to Tab through every tab in a tab list to exit the component.

---

## Group 10: Advanced and Cross-cutting

**How would you debug a z-index issue where an element appears behind another despite having a higher z-index?**

Step 1: Identify the stacking context chain for both elements. Walk up the DOM from each element and find every ancestor that creates a stacking context — check `position` + `z-index`, `opacity < 1`, `transform`, `filter`, `will-change`, `isolation`, `contain`. Step 2: Find the common ancestor stacking context — the comparison that matters is between the two elements' stacking contexts at that level, not between the elements' own z-index values. Step 3: Fix at the right level — adjust the z-index of the containing stacking context, not the inner element. Step 4: If the element is inside a component (a sidebar, a card), consider the portal pattern — render overlays (modals, tooltips, dropdowns) as children of `<body>` to avoid stacking context containment entirely.

---

**What is the difference between `contain: layout`, `contain: paint`, and `contain: strict`?**

`contain: layout`: internal layout changes don't affect external elements and vice versa. The browser can reflow the subtree independently. Side effects: creates stacking context, BFC, containing block for positioned descendants. `contain: paint`: acts as a viewport for the subtree — descendants can't overflow visually. Also creates stacking context, BFC, containing block. Similar to `overflow: hidden` but with additional performance signals. `contain: strict`: `layout + paint + size + style` — the strongest form. Requires explicit `width` and `height` (size containment means the browser ignores descendants when sizing the element). Used for fixed-size components that update frequently (thumbnails, grid items) where isolated reflows are critical for performance.

---

**Compare three approaches to responsive typography: media query breakpoints, `vw` units, and `clamp()`.**

Media query breakpoints: explicit steps — font is 16px below 768px, 18px above. Simple but creates jarring jumps at breakpoints. Multiple breakpoints multiply the maintenance surface. `vw` units (`font-size: 2vw`): continuous scaling but no minimum or maximum — text becomes unreadably small on phones and unreadably large on wide monitors. Requires clamping via JavaScript or additional breakpoints. `clamp()` (`font-size: clamp(1rem, 2.5vw, 1.5rem)`): combines continuous scaling with enforced bounds. Scales smoothly between the minimum (mobile floor) and maximum (desktop ceiling) with no media queries. The preferred modern approach — one declaration handles all viewport sizes.

---

**When would you choose CSS Modules over Tailwind, and vice versa?**

CSS Modules over Tailwind: when component styles involve complex pseudo-element designs, intricate animations, deeply conditional logic, or simply make more sense as a cohesive block than as 15 utility classes. Also when the team has strong CSS expertise and prefers explicit authorship, or when integrating with a design system built on CSS custom properties rather than utility class mappings. Tailwind over CSS Modules: when iteration speed matters (no file-switching, co-located in JSX), when you want a built-in design system enforced by constraints (the `spacing-4` scale), when the project uses a component framework that abstracts class list repetition, and when CSS bundle size is a concern (Tailwind purges unused utilities, shipped CSS is minimal).
