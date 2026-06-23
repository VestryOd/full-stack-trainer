# Responsive and Modern CSS

## Media queries — what they actually measure

Media queries respond to the **viewport** — the browser window dimensions. This works for page-level layout decisions ("switch from one column to two columns when the screen is wide enough"), but breaks down for components.

The fundamental problem: a component doesn't know how wide it is — it only knows how wide the viewport is. A card component might be full-width on mobile, half-width in a two-column layout, and one-third-width in a three-column layout. The viewport width doesn't tell the card which of these scenarios it's in.

```css
/* Media query approach — breaks when the same component appears
   in containers of different widths at the same viewport size */
@media (min-width: 768px) {
  .card {
    display: grid;
    grid-template-columns: 120px 1fr;
  }
}
/* At 900px viewport:
   - A card in a full-width container → works, has enough room
   - A card in a 300px sidebar → also switches layout → broken, too narrow */
```

## Container queries — the paradigm shift

Container queries respond to the **container's size**, not the viewport's. A component can adapt to the space it actually has, regardless of why that space is that size.

### Setting up a containment context

A container query requires two things: (1) a **containment context** declared on the container, and (2) a `@container` rule on the component.

```css
/* Step 1: Declare the container */
.card-wrapper {
  container-type: inline-size;
  /* inline-size: responds to the container's inline dimension (width in LTR) */
  /* size: responds to both inline and block dimensions */
  container-name: card; /* optional — for named container queries */
}

/* Step 2: Write the container query */
@container (min-width: 400px) {
  .card {
    display: grid;
    grid-template-columns: 120px 1fr;
  }
}

/* Named container query — targets a specific container by name */
@container card (min-width: 400px) {
  .card-title {
    font-size: 1.25rem;
  }
}
```

Now `.card` adapts to its container's width — not the viewport. Place it in a 300px sidebar and it stays single-column. Place it in a 600px main area and it switches to grid layout. Same component, same CSS, correct behavior in both contexts.

### Container shorthand

```css
/* Equivalent to container-type + container-name */
.wrapper {
  container: card / inline-size;
  /* name / type */
}
```

### Container query units

Within a `@container` block, special units are available relative to the container size:

```css
@container (min-width: 400px) {
  .card-title {
    font-size: 5cqi;   /* 5% of container's inline size */
    padding: 3cqb;     /* 3% of container's block size */
    margin: 2cqw;      /* 2% of container's width */
    height: 10cqh;     /* 10% of container's height */
    font-size: min(5cqi, 2rem); /* responsive but capped */
  }
}
```

`cqi` (container query inline) and `cqb` (container query block) are the most useful — they're direction-aware (work correctly with logical properties).

### What container queries solve that media queries cannot

```html
<!-- A design system card used in three different layout contexts simultaneously -->
<div class="sidebar" style="width: 280px;">
  <article class="card">...</article>  <!-- should be compact layout -->
</div>

<div class="main-grid" style="width: 600px;">
  <article class="card">...</article>  <!-- should be medium layout -->
</div>

<div class="featured" style="width: 900px;">
  <article class="card">...</article>  <!-- should be expanded layout -->
</div>
```

```css
.card-container {
  container-type: inline-size;
}

/* Compact: < 300px */
.card { /* single column, small text */ }

/* Medium: 300px–600px */
@container (min-width: 300px) {
  .card {
    display: grid;
    grid-template-columns: 100px 1fr;
  }
}

/* Expanded: > 600px */
@container (min-width: 600px) {
  .card {
    grid-template-columns: 200px 1fr;
    font-size: 1.125rem;
  }
}
```

All three cards on the same page, same viewport size, different layouts — impossible with media queries, trivial with container queries.

### Style container queries

Beyond size, container queries can query **computed style values**:

```css
/* Parent sets a custom property */
.theme-dark {
  --theme: dark;
}

/* Children respond to it */
@container style(--theme: dark) {
  .card {
    background: #1a1a2e;
    color: #e0e0e0;
  }
}
```

Style queries are still experimental (partial support as of 2024) but show the direction: components that adapt to their semantic context, not just their physical dimensions.

## Logical properties — why they matter for i18n

Physical properties (`margin-left`, `padding-right`, `border-top`) are tied to physical screen directions. Logical properties are tied to **writing mode and text direction** — they adapt automatically when the layout direction changes.

### The mapping

| Physical | Logical | Maps to in LTR | Maps to in RTL |
|---|---|---|---|
| `margin-left` | `margin-inline-start` | left | right |
| `margin-right` | `margin-inline-end` | right | left |
| `margin-top` | `margin-block-start` | top | top |
| `margin-bottom` | `margin-block-end` | bottom | bottom |
| `padding-left` | `padding-inline-start` | left | right |
| `width` | `inline-size` | width | width |
| `height` | `block-size` | height | height |
| `top` | `inset-block-start` | top | top |
| `left` | `inset-inline-start` | left | right |

In a left-to-right (`ltr`) layout: **inline** = horizontal, **block** = vertical.
In a top-to-bottom vertical writing mode (e.g., Japanese): **inline** = vertical, **block** = horizontal.

### The practical problem logical properties solve

```css
/* Physical approach — must be manually mirrored for RTL */
.button-icon {
  margin-left: 8px; /* icon on the right of text */
}

/* RTL override needed: */
[dir="rtl"] .button-icon {
  margin-left: 0;
  margin-right: 8px;
}

/* Logical approach — works for both directions automatically */
.button-icon {
  margin-inline-start: 8px;
  /* LTR: margin-left: 8px → icon is to the right of text ✓ */
  /* RTL: margin-right: 8px → icon is to the left of text ✓ */
}
```

No `[dir="rtl"]` override needed. The browser maps the logical direction automatically based on the computed `direction` and `writing-mode` values.

### Real-world example — a chat message layout

```css
/* Physical approach requires duplicated RTL styles */
.message {
  margin-left: auto;
  text-align: left;
  border-radius: 12px 12px 12px 0; /* bottom-left corner flat */
}
[dir="rtl"] .message {
  margin-left: 0;
  margin-right: auto;
  text-align: right;
  border-radius: 12px 12px 0 12px; /* bottom-right corner flat */
}

/* Logical approach — zero RTL overrides needed */
.message {
  margin-inline-start: auto;
  text-align: start;
  border-start-start-radius: 12px;
  border-start-end-radius: 12px;
  border-end-end-radius: 12px;
  border-end-start-radius: 0; /* corner at the message origin */
}
```

### Border-radius logical properties

```css
/* Physical → Logical mapping for border-radius */
border-top-left-radius     → border-start-start-radius
border-top-right-radius    → border-start-end-radius
border-bottom-left-radius  → border-end-start-radius
border-bottom-right-radius → border-end-end-radius
```

### `inset` shorthand

```css
/* Physical positioning */
position: absolute;
top: 0;
right: 0;
bottom: 0;
left: 0;

/* Physical shorthand */
inset: 0; /* all four sides */
inset: 10px 20px; /* block / inline */

/* Logical positioning */
inset-block: 0;   /* block-start and block-end */
inset-inline: 0;  /* inline-start and inline-end */
inset-inline-start: 20px;
```

### When to use logical properties in practice

- **Always**: new projects where you control the codebase, any project that might need RTL in the future
- **Selectively**: existing projects where adopting fully logical properties would require extensive testing
- **Avoid**: when you genuinely mean a physical direction regardless of writing mode (e.g., a decorative element pinned to the physical left edge of the viewport)

## `clamp()`, `min()`, `max()` — responsive values without media queries

These three functions enable **fluid** responsive design — values that scale continuously with the viewport, not in discrete breakpoint jumps.

### `min()` and `max()`

```css
/* min(): use the smaller of the values */
width: min(500px, 100%);
/* On a 400px viewport: 100% (400px) < 500px → uses 400px */
/* On a 800px viewport: 500px < 100% (800px) → uses 500px */
/* Practical: element is at most 500px, but shrinks on smaller screens */

/* max(): use the larger of the values */
font-size: max(16px, 1.5vw);
/* On a 800px viewport: 1.5vw = 12px < 16px → uses 16px (never smaller than 16px) */
/* On a 1200px viewport: 1.5vw = 18px > 16px → uses 18px */
/* Practical: font scales with viewport but never goes below 16px */
```

### `clamp()` — the fluid scaling function

`clamp(minimum, preferred, maximum)` — the value scales with the preferred expression but is clamped between minimum and maximum:

```css
/* Font size that scales between 1rem and 2rem based on viewport width */
font-size: clamp(1rem, 2.5vw, 2rem);
/* At 400px: 2.5vw = 10px. clamp: 16px (uses minimum, 10px < 1rem) */
/* At 800px: 2.5vw = 20px. clamp: 20px (uses preferred) */
/* At 1200px: 2.5vw = 30px. clamp: 32px (uses maximum, 30px > 2rem) */
```

### Fluid typography with `clamp()`

The "preferred" value is typically a viewport-relative expression. The goal: typography that scales smoothly from minimum (mobile) to maximum (desktop) sizes without media query breakpoints.

```css
/* Formula: clamp(min-size, preferred, max-size)
   preferred = min-size + (max-size - min-size) × ((100vw - min-vw) / (max-vw - min-vw))
   Simplified to a linear expression using vw */

:root {
  /* Fluid base font: 16px at 320px viewport, 20px at 1200px */
  font-size: clamp(1rem, 0.875rem + 0.625vw, 1.25rem);

  /* Fluid heading: 2rem at 320px, 3.5rem at 1200px */
  --h1-size: clamp(2rem, 1.571rem + 2.143vw, 3.5rem);
}

h1 { font-size: var(--h1-size); }
```

### Fluid spacing with `clamp()`

```css
:root {
  /* Section padding: 24px on mobile, 80px on desktop */
  --section-padding: clamp(24px, 4vw + 16px, 80px);

  /* Gap between columns: 16px minimum, scales to 32px */
  --column-gap: clamp(16px, 3vw, 32px);
}

.section {
  padding-block: var(--section-padding);
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--column-gap);
}
```

### No-media-query responsive layout

```css
/* Card that's always readable without breakpoints */
.card {
  /* Width: at least 280px, at most 400px, scales with container */
  width: clamp(280px, 100%, 400px);

  /* Padding scales with the card's width */
  padding: clamp(16px, 5%, 32px);

  /* Font scales with viewport */
  font-size: clamp(0.875rem, 0.8rem + 0.375vw, 1.125rem);
}
```

### `min()` / `max()` in grid and flex

```css
/* Column that's at least 200px wide (prevents too-narrow columns) */
grid-template-columns: repeat(auto-fit, minmax(min(200px, 100%), 1fr));
/* min(200px, 100%): on a 150px container, 100% < 200px → uses 100% */
/* Prevents the column from overflowing when the container is narrower than minmax's minimum */

/* Sidebar with a reasonable width range */
.sidebar {
  width: min(300px, 30%);
  /* Takes 30% of the container, but never more than 300px */
}
```

## The `aspect-ratio` property

`aspect-ratio` defines the preferred aspect ratio of an element. The browser maintains this ratio automatically as the element's size changes.

```css
/* 16:9 video container */
.video-wrapper {
  aspect-ratio: 16 / 9;
  width: 100%;
  /* Height computed automatically: width × (9/16) */
}

/* Square avatar */
.avatar {
  aspect-ratio: 1;   /* equivalent to 1 / 1 */
  width: 64px;       /* height: 64px automatically */
}

/* 3:2 photo ratio */
.photo {
  aspect-ratio: 3 / 2;
  width: 100%;
  overflow: hidden; /* clip if image doesn't match ratio */
}

.photo img {
  width: 100%;
  height: 100%;
  object-fit: cover; /* fill the aspect-ratio box without distortion */
}
```

### Before `aspect-ratio` — the padding hack

The pre-`aspect-ratio` technique used a padding-top percentage trick:

```css
/* Old technique — padding-top as percentage is relative to element's WIDTH */
.video-wrapper {
  position: relative;
  padding-top: 56.25%; /* 9/16 = 56.25% */
  height: 0;
}
.video-wrapper iframe {
  position: absolute;
  top: 0; left: 0;
  width: 100%; height: 100%;
}
```

`aspect-ratio` replaces this entirely and works on any element type.

### `aspect-ratio` with content

When the element has content, `aspect-ratio` is a *preference*, not a constraint. If content is taller than the ratio allows, the element grows:

```css
.card {
  aspect-ratio: 4 / 3;
  /* If content is taller than 75% of the card's width → card grows vertically */
  /* aspect-ratio is overridden by content */
}

/* To enforce the ratio regardless of content: */
.card {
  aspect-ratio: 4 / 3;
  overflow: hidden; /* clip overflowing content */
}
```

### Intrinsic aspect ratio for images and videos

Images and videos have an intrinsic aspect ratio from their source dimensions. `aspect-ratio` can override it or be used to reserve space before the image loads (preventing layout shift):

```css
img {
  aspect-ratio: 16 / 9;
  width: 100%;
  object-fit: cover;
  /* Image loads with its intrinsic ratio, but CSS enforces 16/9 */
}

/* Reserve space before image loads — prevents CLS (Cumulative Layout Shift) */
.image-container {
  aspect-ratio: 16 / 9;
  background: #f0f0f0; /* placeholder color */
}
.image-container img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
```

## Putting it together — a modern responsive component

```css
/* A card component that uses all modern responsive techniques */

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(280px, 100%), 1fr));
  gap: clamp(16px, 3vw, 32px);
  padding: clamp(16px, 4vw, 48px);
  container-type: inline-size;
}

.card {
  display: flex;
  flex-direction: column;
}

.card-image {
  aspect-ratio: 16 / 9;
  overflow: hidden;
  border-radius: 8px;
}

.card-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.card-body {
  padding-block: clamp(12px, 2vw, 24px);
  padding-inline: clamp(12px, 2vw, 24px);
  flex: 1;
}

.card-title {
  font-size: clamp(1rem, 1.5cqi, 1.5rem);
  margin-block-end: 0.5em;
}

/* Container query: switch to horizontal layout in wider containers */
@container (min-width: 500px) {
  .card {
    flex-direction: row;
  }
  .card-image {
    aspect-ratio: 1;
    flex: 0 0 200px;
  }
}
```

## Common interview traps

**"What's the difference between container queries and media queries?"**

Media queries respond to the **viewport size** — they're useful for page-level layout decisions. Container queries respond to the **container's size** — they make components truly reusable because the component adapts to the space it actually occupies, not to a global screen measurement. A card component that appears in a 280px sidebar and a 600px main area at the same viewport width can only adapt correctly with container queries.

---

**"What is `container-type: inline-size` vs `container-type: size`?"**

`inline-size`: enables querying the container's inline dimension (width in horizontal writing modes). The container's block size (height) remains untracked — the element doesn't need an explicit height to participate. `size`: enables querying both inline and block dimensions. Requires that the container's block size not depend on its content (must be explicitly set or constrained) — otherwise circular size computation. Use `inline-size` in most cases; `size` only when you need to query the container's height.

---

**"What's the difference between `margin-left` and `margin-inline-start`?"**

`margin-left` is a physical property — always refers to the left side of the element regardless of writing direction. `margin-inline-start` is a logical property — refers to the start of the inline direction. In LTR layouts, both are identical. In RTL layouts (`dir="rtl"`), `margin-inline-start` maps to `margin-right`. In vertical writing modes, `margin-inline-start` maps to the top or bottom. Logical properties eliminate the need for `[dir="rtl"]` overrides.

---

**"Explain `clamp(1rem, 2.5vw, 2rem)`."**

The value is `2.5vw`, clamped to a minimum of `1rem` and a maximum of `2rem`. At small viewports, if `2.5vw` falls below `1rem`, the value is `1rem`. At large viewports, if `2.5vw` exceeds `2rem`, the value is `2rem`. Between those extremes, it scales linearly with the viewport width. This replaces two media query breakpoints with a single continuously-scaling value.

---

**"What problem does `aspect-ratio` solve over the padding-top hack?"**

The padding-top hack (`padding-top: 56.25%`) exploits the fact that padding percentage is relative to element width — it creates a box with a fixed aspect ratio by making the height proportional to the width via padding. Problems: requires `height: 0`, requires `position: absolute` on children, breaks content flow. `aspect-ratio` is declarative, works with content flow, applies to any element type, and is readable. It's supported in all major browsers since 2021.

---

**"When would you use `min()` in a grid column definition?"**

`repeat(auto-fit, minmax(min(280px, 100%), 1fr))` — the `min(280px, 100%)` prevents a column from having a minimum size larger than the container. Without it, if the container is 200px wide, the `minmax(280px, 1fr)` would compute a 280px minimum for a 200px container — the column overflows. With `min(280px, 100%)`, on a 200px container `100% < 280px` so the minimum becomes `100%` (200px), and the column fits.
