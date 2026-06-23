# Box Model and Layout Basics

## The box model — what the browser actually computes

Every element in a document is represented as a rectangular box. The browser computes four nested rectangles for each box:

```
┌──────────────────────────────────────────┐
│                  margin                  │
│   ┌──────────────────────────────────┐   │
│   │             border               │   │
│   │   ┌──────────────────────────┐   │   │
│   │   │          padding         │   │   │
│   │   │   ┌──────────────────┐   │   │   │
│   │   │   │     content      │   │   │   │
│   │   │   │   width × height │   │   │   │
│   │   │   └──────────────────┘   │   │   │
│   │   └──────────────────────────┘   │   │
│   └──────────────────────────────────┘   │
└──────────────────────────────────────────┘
```

This structure is fixed — the question is how `width` and `height` are interpreted relative to it.

## `content-box` vs `border-box` — the actual difference

### `content-box` (the default, and the unintuitive one)

`width` and `height` define the **content area only**. Padding and border are added on top:

```css
.box {
  box-sizing: content-box; /* default */
  width: 200px;
  padding: 20px;
  border: 2px solid black;
}
/* Total rendered width: 200 + 20 + 20 + 2 + 2 = 244px */
```

This means: `width: 200px` does NOT mean the element is 200px wide on screen. The 200px is consumed by content, and the element grows outward beyond that. If you're sizing an element to fit a container, you must subtract padding and border from the desired width — arithmetic that's error-prone and breaks when any of those values change.

### `border-box` (the sane default)

`width` and `height` define the **border box** — the total size including padding and border. Content area shrinks to accommodate them:

```css
.box {
  box-sizing: border-box;
  width: 200px;
  padding: 20px;
  border: 2px solid black;
}
/* Total rendered width: 200px (exactly) */
/* Content area: 200 - 20 - 20 - 2 - 2 = 156px */
```

`width: 200px` now means the element is 200px wide on screen. Period. Changing padding or border doesn't affect the external dimensions.

### Why `border-box` is universally applied as a reset

The modern CSS reset applies `border-box` to every element:

```css
*,
*::before,
*::after {
  box-sizing: border-box;
}
```

The `::before` and `::after` inclusion matters: pseudo-elements are not covered by `*` alone and default to `content-box` unless explicitly set.

The reason this reset became universal: when building column layouts (e.g., `width: 50%` for two equal columns), `content-box` makes it impossible to add any padding without breaking the layout. With `border-box`, `width: 50%; padding: 16px` works as expected — the element is exactly 50% of its container.

**The one case `content-box` is still useful:** when you want an element's dimensions to expand based on content while having fixed padding. Rare in practice.

## Margin collapsing — the actual algorithm

Margin collapsing is one of the most misunderstood CSS behaviors. Most explanations say "adjacent margins collapse." That's incomplete. The full rules:

### Rule 1: Adjacent siblings

When two block-level elements are stacked vertically, the bottom margin of the first and the top margin of the second collapse into a single margin. The result is the **maximum** of the two values, not their sum.

```html
<p style="margin-bottom: 20px">First paragraph</p>
<p style="margin-top: 30px">Second paragraph</p>
<!-- Gap between them: 30px (max of 20 and 30), NOT 50px -->
```

```css
/* Negative margins collapse differently:
   max of positives + min of negatives */
/* margin-bottom: 20px, margin-top: -10px → result: 10px */
/* margin-bottom: -20px, margin-top: -10px → result: -20px */
```

### Rule 2: Parent and first/last child

If a parent element has no border, padding, inline content, or block formatting context separating it from its first child's top margin — they collapse:

```html
<div class="parent">
  <!-- No padding-top, no border-top, no inline content before child -->
  <p style="margin-top: 30px">Child paragraph</p>
</div>

<!-- The parent's margin-top and child's margin-top collapse.
     The 30px "leaks" out of the parent to become the parent's effective top margin.
     The parent's own margin-top (if any) is compared, and the maximum wins. -->
```

This is the "margin leaking" phenomenon. Adding `padding-top: 1px` to the parent breaks the collapse — any separation (border or padding) prevents it.

**What prevents collapse between parent and child:**
- Parent has `padding-top` or `border-top` (any non-zero value)
- Parent has `overflow` other than `visible` (creates a BFC)
- Parent has `display: flow-root`
- Parent is a flex or grid container (children are flex/grid items, not in flow)

### Rule 3: Empty blocks

A block element with no height, no padding, no border, and no inline content collapses its own top and bottom margins:

```css
.empty {
  margin-top: 20px;
  margin-bottom: 30px;
  /* No height, no content, no padding, no border */
}
/* Effective margin contribution: 30px (max of 20 and 30) */
```

### When margin collapsing does NOT happen

- Elements in flex containers (flex items don't collapse margins)
- Elements in grid containers
- Elements with `float`
- Elements with `position: absolute` or `position: fixed`
- The root element's margins
- Between a parent and child when a BFC, border, or padding intervenes

The practical implication: if you switch a layout from `display: block` to `display: flex`, previously collapsed margins suddenly add up — elements that were 20px apart are now 50px apart. This is a common source of layout shifts during refactors.

### Block Formatting Context (BFC) — why it matters for collapsing

A BFC is an isolated layout environment where the normal-flow rules apply independently. Elements inside a BFC do not collapse margins with elements outside it.

What creates a BFC:
- `overflow: hidden`, `overflow: auto`, `overflow: scroll` (any value other than `visible`)
- `display: flow-root` (explicit BFC creation, no side effects)
- `display: flex`, `display: grid`, `display: inline-flex`, `display: inline-grid`
- `float: left` or `float: right`
- `position: absolute` or `position: fixed`
- `contain: layout`, `contain: content`, `contain: paint`

`display: flow-root` is the modern, side-effect-free way to create a BFC. Before it existed, developers used `overflow: hidden` as a hack — it creates a BFC, but the side effect is that it clips content.

## Positioning — the containing block rules

The `position` property determines two things: (1) whether the element participates in normal flow, and (2) what its **containing block** is.

The containing block is the reference rectangle for percentage-based dimensions and for `top`/`right`/`bottom`/`left` offsets. Getting this wrong is the source of most "why isn't my absolute element in the right place?" bugs.

### `position: static` (default)

Element participates in normal flow. `top`, `right`, `bottom`, `left`, and `z-index` have no effect. Containing block is the nearest block container ancestor (standard flow rules).

```css
.box {
  position: static; /* the default */
  top: 10px; /* ignored */
  z-index: 5; /* ignored */
}
```

### `position: relative`

Element participates in normal flow (occupies space as normal). Offset properties (`top`, `left`, etc.) move the **visual rendering** without affecting layout — the element's original space in the flow is preserved and other elements don't reflow around it.

```css
.box {
  position: relative;
  top: 20px;
  left: 10px;
  /* Visually shifted 20px down and 10px right,
     but its original space still exists in the flow */
}
```

**Containing block for children:** `position: relative` makes the element a containing block for any absolutely positioned descendants.

```html
<div style="position: relative; width: 400px; height: 200px;">
  <!-- This is the containing block for the child below -->
  <div style="position: absolute; right: 0; bottom: 0;">
    <!-- Positioned at bottom-right of the parent, not the viewport -->
  </div>
</div>
```

### `position: absolute`

Element is **removed from normal flow** — it takes up no space in the document. Positioned relative to its **nearest positioned ancestor** (an ancestor with `position` other than `static`). If no positioned ancestor exists, it's positioned relative to the **initial containing block** (the viewport in most cases, or the `<html>` element to be precise).

```html
<div class="container"> <!-- position: static — NOT the containing block -->
  <div class="wrapper" style="position: relative;"> <!-- IS the containing block -->
    <div style="position: absolute; top: 0; right: 0;">
      <!-- top-right corner of .wrapper -->
    </div>
  </div>
</div>
```

**Common gotcha:** the containing block is determined by `position` being non-static, NOT by visual nesting. An absolutely positioned element inside visually-nested divs will "escape" all of them until it finds one with `position: relative/absolute/fixed/sticky`.

**What also creates a containing block for absolute children** (beyond `position`):**
- `transform` (any value other than `none`)
- `filter` (any value other than `none`)
- `will-change: transform` or `will-change: filter`
- `contain: layout`, `contain: paint`, `contain: strict`
- `perspective`

This list trips up even experienced developers. A `transform: translateZ(0)` or `filter: blur(0)` on a parent will silently capture absolutely positioned descendants, causing them to position relative to that parent instead of a further ancestor.

```css
/* This will capture absolutely-positioned children — often unexpected */
.sidebar {
  transform: translateX(0); /* GPU layer optimization */
}

/* Now any position: absolute child inside .sidebar positions
   relative to .sidebar, not to the nearest position: relative ancestor */
```

### `position: fixed`

Like `absolute`, removed from normal flow. But the containing block is always the **viewport** — regardless of any ancestor's `position`.

**Exception:** `transform`, `filter`, `will-change`, `backdrop-filter`, or `perspective` on an ancestor breaks fixed positioning. The element is captured by the transformed ancestor instead of the viewport. This is one of the most surprising CSS behaviors.

```css
/* This breaks position: fixed on any descendant */
.parent {
  transform: none; /* Even this! */
  /* The spec says: if transform is anything other than the initial value,
     it creates a containing block for fixed children. transform: none IS
     the initial value — but some browsers had bugs with this. */
}

/* Safe approach: move fixed elements to be direct children of <body>
   to avoid accidental containment */
```

### `position: sticky`

Hybrid: acts as `relative` within its containing block (the **nearest scrolling ancestor** with overflow not `visible`/`clip`), and becomes `fixed`-like when the threshold is reached. Returns to `relative` when the container scrolls out of view.

```css
.sticky-header {
  position: sticky;
  top: 0; /* Distance from the scrolling container's edge where sticking begins */
}
```

**Why sticky often "doesn't work":**

1. **The containing block has no height.** Sticky only travels within its containing block. If the parent is only as tall as the sticky element itself, there's no room to stick.

```html
<!-- Broken: parent has no height beyond the sticky element -->
<div class="section"> <!-- height = height of h2 only -->
  <h2 style="position: sticky; top: 0;">Title</h2>
  <!-- no other content in this section -->
</div>

<!-- Working: parent is taller than the sticky element -->
<div class="section"> <!-- height = h2 + many paragraphs -->
  <h2 style="position: sticky; top: 0;">Title</h2>
  <p>...</p>
  <p>...</p>
  <!-- sticky sticks while scrolling through these -->
</div>
```

2. **An ancestor has `overflow: hidden` or `overflow: auto`.** The scrolling ancestor for sticky is not the viewport but the nearest ancestor with `overflow` other than `visible`. If that ancestor clips content, the sticky element is contained inside it and the viewport scroll doesn't trigger sticking.

3. **Missing `top`/`bottom`/`left`/`right`.** `position: sticky` without a threshold value does nothing — it doesn't know when to start sticking.

## Inline vs block — the display context that controls collapsing

Block-level elements (default for `<div>`, `<p>`, `<h1>`, etc.) generate block boxes and participate in block formatting context — this is where margin collapsing happens.

Inline-level elements (`<span>`, `<a>`, `<strong>`) generate inline boxes. They have horizontal padding/margin but vertical margin doesn't collapse and doesn't push block-level siblings.

`display: inline-block` is the hybrid: the element is treated as inline by the parent (sits in a line of text), but internally generates a block formatting context. Vertical margin and padding work as expected, and it creates a BFC (so no margin collapsing with children).

```css
/* inline-block: takes up only as much width as needed,
   sits in the text flow, but respects vertical dimensions */
.badge {
  display: inline-block;
  padding: 4px 8px;
  vertical-align: middle;
}
```

## Common interview traps

**"What's the total rendered width of this element?"**

```css
.box {
  width: 300px;
  padding: 0 20px;
  border: 3px solid;
  box-sizing: content-box; /* default */
}
```

Answer: `300 + 20 + 20 + 3 + 3 = 346px`. With `border-box`: `300px`. This is asked to test whether you know the `box-sizing` default.

---

**"Why is my margin leaking out of its parent?"**

Classic margin collapsing between parent and first child. The child's `margin-top` has nothing to stop it at the parent's boundary (no border-top, no padding-top, no inline content, no BFC). Fix options: add any `padding-top` to the parent, add `border-top: 1px solid transparent`, or make the parent `display: flow-root` / `overflow: hidden`.

---

**"My `position: fixed` element scrolls with the page — what happened?"**

An ancestor has a CSS `transform`, `filter`, or `will-change: transform` property applied. This creates a new containing block for fixed descendants, making them position relative to that ancestor instead of the viewport. Move the fixed element to be a direct child of `<body>` or remove the transform from the ancestor.

---

**"Why does switching from `display: block` to `display: flex` on a container change the spacing between elements?"**

Flex items are not in block formatting context — margin collapsing only happens in BFC. The adjacent sibling margin collapse that was occurring between block children no longer applies. Previously collapsed margins (e.g., 20px + 30px = 30px gap) now add up (50px gap). Same effect happens with grid containers.

---

**"What's the difference between `display: flow-root` and `overflow: hidden` for clearing floats / preventing margin collapse?"**

Both create a Block Formatting Context (BFC). The difference: `overflow: hidden` clips content that extends beyond the element's bounds — a side effect that is sometimes unwanted (dropdown menus, tooltips, box shadows). `display: flow-root` creates a BFC with no side effects — it was introduced precisely because `overflow: hidden` was being misused as a BFC hack.

---

**"An absolutely positioned element is in the wrong place — how do you debug it?"**

Find the containing block: walk up the DOM and find the nearest ancestor with `position` other than `static`. Also check for `transform`, `filter`, or `will-change` on ancestors — those also capture `position: absolute` children. In DevTools, select the positioned element and look at the "Computed" panel for the offset values, then identify what it's being positioned relative to.
