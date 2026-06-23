# Flexbox Deep Dive

## The mental model: two axes, one container

Flexbox operates on a single axis at a time. The **main axis** is the direction items flow; the **cross axis** is perpendicular to it. Every flexbox property maps to one of these two axes.

```
flex-direction: row (default)

main axis →→→→→→→→→→→→→→→→→→→→→
┌─────────────────────────────────┐
│  ┌───┐  ┌───┐  ┌───┐  ┌───┐   │ ↑ cross axis
│  │ A │  │ B │  │ C │  │ D │   │ │
│  └───┘  └───┘  └───┘  └───┘   │ ↓
└─────────────────────────────────┘

flex-direction: column

┌─────────────────────────────────┐
│  ┌───────────────────────────┐  │ ↑ main axis
│  │ A                         │  │ │
│  └───────────────────────────┘  │ │
│  ┌───────────────────────────┐  │ │
│  │ B                         │  │ ↓
│  └───────────────────────────┘
   → cross axis
```

`justify-content` always controls alignment along the **main axis**.
`align-items` / `align-self` always controls alignment along the **cross axis**.

When `flex-direction` changes, the axes rotate — `justify-content: center` centers vertically in a column layout. This trips up developers who memorize "justify = horizontal" — that's only true when `flex-direction: row`.

## The flex algorithm — how the browser distributes space

Before understanding `flex-grow`, `flex-shrink`, and `flex-basis`, you need to understand the order in which the browser resolves flex item sizes. The algorithm has four stages:

### Stage 1: Determine the hypothetical main size

Each item's **hypothetical main size** is resolved from `flex-basis`. The resolution order:

1. If `flex-basis` is `auto` → use the item's `width` (or `height` in column layout). If that's also `auto` → use the item's max-content size (shrink to content).
2. If `flex-basis` is a length (`px`, `%`, etc.) → use that value directly (ignoring `width`/`height`).
3. If `flex-basis` is `content` → use the item's max-content size.

```css
.item {
  flex-basis: auto;
  width: 200px;
  /* Hypothetical main size: 200px */
}

.item {
  flex-basis: 150px;
  width: 200px;
  /* Hypothetical main size: 150px — flex-basis wins */
}

.item {
  flex-basis: auto;
  /* No width set → hypothetical main size = content width */
}
```

### Stage 2: Determine if there is free space or overflow

Sum all hypothetical main sizes plus gaps. Compare to the container's main size.

- **Free space > 0**: container has leftover space → `flex-grow` distributes it.
- **Free space < 0**: items overflow the container → `flex-shrink` absorbs the overflow.
- **Free space = 0**: items fit exactly, no growing or shrinking needed.

### Stage 3a: Distribute free space via `flex-grow`

`flex-grow` specifies a proportion — not a pixel value or ratio of the final size. The free space is distributed proportionally among items with non-zero `flex-grow`.

```
Container: 600px
Items: A (flex-grow: 1, flex-basis: 0), B (flex-grow: 2, flex-basis: 0), C (flex-grow: 1, flex-basis: 0)

Total flex-grow: 1 + 2 + 1 = 4
Free space: 600px (flex-basis is 0 for all)

A gets: 600 × (1/4) = 150px
B gets: 600 × (2/4) = 300px
C gets: 600 × (1/4) = 150px
```

With non-zero `flex-basis` values:

```
Container: 600px
A: flex-grow: 1, flex-basis: 100px
B: flex-grow: 2, flex-basis: 100px
C: flex-grow: 1, flex-basis: 100px

Sum of flex-basis: 300px
Free space: 600 - 300 = 300px (THIS is distributed, not the total width)

A gets: 100 + 300 × (1/4) = 100 + 75 = 175px
B gets: 100 + 300 × (2/4) = 100 + 150 = 250px
C gets: 100 + 300 × (1/4) = 100 + 75 = 175px
```

Key insight: `flex-grow` distributes **free space**, not total space. This is why `flex-grow: 1` on all items does NOT mean each item gets equal width — it does only if `flex-basis` is the same for all (including `flex-basis: 0`).

### Stage 3b: Absorb overflow via `flex-shrink`

`flex-shrink` works similarly but absorbs negative free space. The calculation uses **weighted shrink factors** — each item's `flex-shrink` value is multiplied by its `flex-basis` to weight the distribution:

```
Container: 400px
A: flex-shrink: 1, flex-basis: 200px  → weighted factor: 1 × 200 = 200
B: flex-shrink: 2, flex-basis: 200px  → weighted factor: 2 × 200 = 400
C: flex-shrink: 1, flex-basis: 200px  → weighted factor: 1 × 200 = 200

Total weighted factor: 800
Overflow: (200 + 200 + 200) - 400 = 200px (to absorb)

A shrinks by: 200 × (200/800) = 50px → final: 150px
B shrinks by: 200 × (400/800) = 100px → final: 100px
C shrinks by: 200 × (200/800) = 50px → final: 150px
```

This weighting means larger items shrink more (in absolute pixels) when `flex-shrink` values are equal — intentional design so that items don't disproportionately shrink relative to their size.

### Stage 4: Apply min/max constraints

After growing/shrinking, the browser clamps each item to its `min-width`/`max-width` (or `min-height`/`max-height` in column layout). If clamping happens, the excess free space or overflow is redistributed among unclamped items. This iteration continues until no more clamping occurs.

## The `min-width: auto` trap

This is the most common flexbox bug and one of the most-asked flexbox interview questions.

By default, flex items have `min-width: auto`. For most elements, `auto` resolves to `0`. But for elements with intrinsic content (text nodes, images, elements with explicit `width` on their content), `min-width: auto` resolves to the **minimum content size** — the smallest the element can be without content overflow.

```css
.container {
  display: flex;
  width: 300px;
}

.item {
  flex-shrink: 1;
  flex-basis: 200px;
  /* min-width: auto → resolves to the minimum content width */
}
```

If the item contains a long word or a fixed-width image, `min-width: auto` might be `150px`. Even with `flex-shrink: 1`, the item cannot shrink below `150px`. If the container is too small, the item overflows — despite `flex-shrink` being set.

**The fix:**

```css
.item {
  min-width: 0; /* Override min-width: auto */
  overflow: hidden; /* or overflow: auto, to contain the content */
}
```

Once `min-width: 0` is set, `flex-shrink` can shrink the item below its content size, and `overflow: hidden` handles the clipped content.

This also affects text truncation:

```css
/* This won't work — the flex item won't shrink, text won't truncate */
.text-item {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* This works */
.text-item {
  min-width: 0; /* ← the essential fix */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
```

The same issue occurs in column layouts with `min-height: auto` on flex items that contain images or have explicit heights.

## The `flex` shorthand — what the browser actually sets

```css
/* flex: <grow> <shrink> <basis> */
flex: 1;         /* flex: 1 1 0% — NOT flex: 1 1 auto */
flex: auto;      /* flex: 1 1 auto */
flex: none;      /* flex: 0 0 auto — completely inflexible */
flex: 0;         /* flex: 0 1 0% */
flex: 1 200px;   /* flex: 1 1 200px */
```

The critical difference between `flex: 1` and `flex: 1 1 auto`:

```css
/* flex: 1 → flex-basis: 0% → items share ALL container space proportionally */
.item { flex: 1; }

/* flex: auto → flex-basis: auto → items start at their content size,
   then share only FREE space proportionally */
.item { flex: auto; }
```

`flex: 1` on all items → equal-width items (all start from 0 and grow equally).
`flex: auto` on all items → items whose content is larger get more space.

Use `flex: 1` when you want a true equal-distribution layout.
Use `flex: auto` when content width should influence final sizes.

## Alignment properties — complete map

```
Main axis (justify-*):
  justify-content   → space distribution between/around items in the container
  justify-items     → default justify-self for all items (rarely used in flex)
  justify-self      → individual item alignment (NOT supported in flex — only grid)

Cross axis (align-*):
  align-content     → space distribution between/around lines (multi-line only)
  align-items       → default cross-axis alignment for all items
  align-self        → override for an individual item
```

`justify-self` does not work in flexbox — this is a common mistake. To align a single flex item to the end of the main axis, use `margin-auto`:

```css
/* Navigation: logo left, links right */
.nav {
  display: flex;
  align-items: center;
}

.nav-logo { /* stays at start */ }

.nav-links {
  margin-left: auto; /* pushes to the end of the main axis */
}
```

`margin: auto` in flexbox absorbs all available free space in the specified direction. It's the flexbox equivalent of `float: right` — without the float side effects.

```css
/* Center a single item in the container — both axes */
.container {
  display: flex;
}
.item {
  margin: auto; /* absorbs free space in all directions */
}
```

## `align-content` vs `align-items` — the distinction that matters

`align-items` controls how items align within a single flex line.
`align-content` controls how multiple flex lines distribute space within the container — it only has effect when `flex-wrap: wrap` and there are at least two lines.

```css
.container {
  display: flex;
  flex-wrap: wrap;
  height: 400px;

  align-items: center;    /* items vertically centered within each line */
  align-content: center;  /* lines themselves centered within 400px height */
}
```

With a single-line flex container (no wrap, or only one line), `align-content` has no effect — `align-items` is what controls cross-axis alignment.

## `gap` property

`gap` (previously `grid-gap`) sets spacing between flex items — row-gap and column-gap:

```css
.container {
  display: flex;
  gap: 16px;        /* row-gap: 16px; column-gap: 16px */
  gap: 8px 16px;   /* row-gap: 8px; column-gap: 16px */
  row-gap: 8px;
  column-gap: 16px;
}
```

`gap` is now universally supported. Key advantage over `margin`: gap only applies between items, never on the outer edges — no need for negative margin hacks to remove edge spacing.

```css
/* Old approach — ugly */
.container { margin: 0 -8px; }
.item { margin: 0 8px; }

/* Modern approach */
.container { display: flex; gap: 16px; }
/* No outer margin needed */
```

## Real layout examples

### Classic holy grail layout

```css
.page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.header,
.footer {
  flex: none; /* don't grow or shrink — fixed height */
}

.body {
  display: flex;
  flex: 1; /* grow to fill remaining vertical space */
}

.sidebar {
  flex: 0 0 240px; /* fixed width, no grow/shrink */
}

.main {
  flex: 1; /* takes all remaining horizontal space */
  min-width: 0; /* prevent content from breaking layout */
}
```

### Responsive card grid that doesn't use media queries

```css
.card-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.card {
  flex: 1 1 280px;
  /* flex-basis: 280px means items want to be 280px wide.
     flex-grow: 1 means they grow to fill remaining space.
     flex-shrink: 1 means they can shrink below 280px.
     Result: as many columns as fit at ~280px minimum, all equal width. */
}
```

### Navbar with logo, centered links, right-side actions

```css
.navbar {
  display: flex;
  align-items: center;
  padding: 0 24px;
}

.logo {
  flex: none;
  margin-right: auto; /* pushes everything else to the right */
}

.nav-links {
  display: flex;
  gap: 24px;
  /* Centered between logo and actions because logo has margin-right: auto
     and actions have margin-left: auto */
  margin: 0 auto;
}

.nav-actions {
  flex: none;
  margin-left: auto; /* pushes itself to the far right */
}
```

### Equal-height columns with varied content

```css
.columns {
  display: flex;
  align-items: stretch; /* default — columns match the tallest */
  gap: 24px;
}

.column {
  flex: 1;
  min-width: 0;
}
```

`align-items: stretch` (the default) makes all flex items expand to match the cross-axis size of the tallest item. This is why flexbox automatically gives equal-height columns — a layout that required table-cell hacks before flexbox.

## Common interview traps

**"Why doesn't `flex-grow: 1` on all items make them equal width?"**

It does — only if `flex-basis` is the same for all items. With `flex-basis: auto` (the default in `flex: 0 1 auto`), items start at their content size and only share the *remaining* free space equally. A wider-content item starts bigger and stays bigger. To get truly equal widths: `flex: 1` (which sets `flex-basis: 0%`), so all items start from zero and grow equally.

---

**"An item with `flex-shrink: 1` is overflowing its container — why?"**

`min-width: auto` on flex items. The browser computed the item's minimum content size (e.g., a long unbreakable word, an image) and won't shrink the item below that — regardless of `flex-shrink`. Fix: add `min-width: 0` to the item. Then add `overflow: hidden` (or `overflow: auto`) to contain the content.

---

**"What's the difference between `flex: 1` and `flex: 1 1 auto`?"**

The `flex-basis` value. `flex: 1` resolves to `flex: 1 1 0%` — items start from zero and grow proportionally, resulting in equal sizes. `flex: 1 1 auto` uses each item's content width as the starting point, so larger-content items end up larger even when `flex-grow` values are equal.

---

**"How do you align one flex item to the right while keeping others on the left?"**

`margin-left: auto` on the item you want on the right. In flexbox, `auto` margins absorb all available free space in the specified direction. `justify-self` does not work on flex items (it's a grid-only property). For pushing an item to the end: `margin-left: auto`. For pushing to the start: `margin-right: auto`.

---

**"Why is `align-content` doing nothing in my flex layout?"**

`align-content` only affects containers with `flex-wrap: wrap` that actually have more than one line of items. With a single flex line (which is the default), `align-content` is ignored — use `align-items` instead. Also: `align-content` requires the container to have a defined height larger than the sum of flex lines.

---

**"Flex item contains long text, but `text-overflow: ellipsis` isn't working."**

The flex item isn't shrinking enough to trigger truncation. Two fixes are needed: (1) `min-width: 0` on the flex item (overrides the `auto` default that prevents shrinking below content size), and (2) `white-space: nowrap; overflow: hidden; text-overflow: ellipsis` on the text element. Without `min-width: 0`, the flex item grows to fit the untruncated text before truncation is even considered.
