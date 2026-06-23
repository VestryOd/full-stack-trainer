# CSS Grid Deep Dive

## The fundamental difference from Flexbox

Flexbox is **content-out**: the container adapts to its items. You define item sizes and growth rules, and the container accommodates them.

Grid is **layout-in**: the container defines a rigid two-dimensional structure of tracks (rows and columns), and items are placed into cells of that structure. The grid exists independently of its items.

This distinction drives when to choose one over the other — but more on that at the end.

## Explicit vs implicit grid

The **explicit grid** is what you define with `grid-template-columns`, `grid-template-rows`, and `grid-template-areas`. The **implicit grid** is what the browser creates automatically when items are placed outside the explicit grid boundaries.

```css
.container {
  display: grid;
  grid-template-columns: 200px 1fr 1fr; /* 3 explicit columns */
  grid-template-rows: 80px auto;        /* 2 explicit rows */
}
```

If you place items that require a 3rd row, the browser generates it automatically — that's the implicit grid. The size of implicit tracks is controlled by `grid-auto-rows` and `grid-auto-columns`:

```css
.container {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-template-rows: 200px;    /* only one explicit row */
  grid-auto-rows: 150px;        /* all subsequent implicit rows: 150px */
}
```

Without `grid-auto-rows`, implicit rows get `auto` size — they shrink to fit their content. This is the source of "why is my second row so short?" bugs.

`grid-auto-flow` controls how items flow into the implicit grid:

```css
grid-auto-flow: row;    /* default: fill rows first, add rows as needed */
grid-auto-flow: column; /* fill columns first, add columns as needed */
grid-auto-flow: dense;  /* backfill holes left by large items — changes visual order */
```

`grid-auto-flow: dense` is useful for masonry-like layouts but changes the visual order of items, which breaks keyboard/screen-reader navigation. Use with care.

## The `fr` unit — what it actually is

`fr` stands for **fraction of available free space** — not fraction of total container size. This distinction matters when the grid has fixed-size tracks alongside `fr` tracks.

```css
.container {
  display: grid;
  width: 900px;
  grid-template-columns: 200px 1fr 2fr;
}
```

Resolution:
1. Subtract fixed tracks: `900 - 200 = 700px` available
2. Total fractions: `1 + 2 = 3`
3. One `fr` = `700 / 3 ≈ 233px`
4. Column 2: `1fr = 233px`, Column 3: `2fr = 466px`

```css
/* fr with gap */
.container {
  display: grid;
  width: 900px;
  gap: 20px;
  grid-template-columns: 1fr 1fr 1fr;
}
/* Gap is subtracted first: 900 - (2 × 20) = 860px available
   Each column: 860 / 3 ≈ 286px */
```

`fr` is computed after all fixed-size tracks (px, em, %, min-content, max-content) and gaps are resolved. The remaining space is then divided into fractions.

**`fr` vs `%`:**

```css
/* % includes the space used by gap — columns overflow */
grid-template-columns: 33.33% 33.33% 33.33%;
/* With gap: 3 × 33.33% + 2 × 20px > 100% — items overflow */

/* fr excludes gap — always fits */
grid-template-columns: 1fr 1fr 1fr;
/* With gap: always divides remaining space correctly */
```

This is why `fr` is preferred over `%` for proportional columns.

**`minmax()` with `fr`:**

```css
/* Column won't shrink below 200px, but will grow to fill free space */
grid-template-columns: minmax(200px, 1fr) minmax(200px, 2fr);
```

## `grid-template-areas` — readable layouts

`grid-template-areas` names rectangular regions of the grid and lets you assign items to them by name. The result is a self-documenting layout:

```css
.layout {
  display: grid;
  grid-template-columns: 240px 1fr;
  grid-template-rows: 64px 1fr 48px;
  grid-template-areas:
    "header  header"
    "sidebar main"
    "footer  footer";
  min-height: 100vh;
}

.header  { grid-area: header; }
.sidebar { grid-area: sidebar; }
.main    { grid-area: main; }
.footer  { grid-area: footer; }
```

Rules for `grid-template-areas`:
- Each row is a quoted string; each word is a cell name
- A named area must be rectangular — L-shapes are invalid
- Use `.` for an unnamed cell (a hole)
- Each row must have the same number of cells

```css
/* Valid: header spans both columns, middle row has two regions, footer spans both */
grid-template-areas:
  "header header"
  "sidebar main"
  "footer  footer";

/* Invalid: non-rectangular named area */
grid-template-areas:
  "header main"
  "header footer"; /* "header" appears in rows 1 and 2 but only column 1 — L-shape */

/* Valid: hole in the grid */
grid-template-areas:
  "logo    nav    nav"
  ".       main   sidebar"
  "footer  footer footer";
```

Setting `grid-area` on an item implicitly places it, sets `grid-column` and `grid-row` under the hood to match the area's boundaries.

## Item placement — line numbers, spans, named lines

Grid lines are numbered starting at 1 (or -1 from the end). Items can be placed by specifying start and end lines:

```css
.item {
  grid-column: 1 / 3;    /* spans from line 1 to line 3 (2 columns) */
  grid-row: 2 / 4;       /* spans from line 2 to line 4 (2 rows) */
}

/* Equivalent using span */
.item {
  grid-column: 1 / span 2; /* start at line 1, span 2 columns */
  grid-row: 2 / span 2;
}

/* From the end */
.item {
  grid-column: 1 / -1; /* span from the first to the last line (full width) */
}
```

Named lines allow semantic placement:

```css
.container {
  grid-template-columns:
    [sidebar-start] 240px [sidebar-end main-start] 1fr [main-end];
}

.main-content {
  grid-column: main-start / main-end;
}
```

`grid-template-areas` automatically creates named lines: if an area is named `header`, lines `header-start` and `header-end` are implicitly created.

## `auto-fill` vs `auto-fit` — the subtle difference

Both are used with `repeat()` to create as many tracks as fit in the container. The difference only shows up when there aren't enough items to fill all tracks.

```css
/* auto-fill: creates as many tracks as fit, even if empty */
grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));

/* auto-fit: creates as many tracks as fit, then collapses empty tracks to 0 */
grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
```

**Visual difference with few items:**

```
Container: 900px, minmax(200px, 1fr), 3 items

auto-fill:
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
│  A   │ │  B   │ │  C   │ │empty │
└──────┘ └──────┘ └──────┘ └──────┘
Items A, B, C each get 225px (900/4 tracks)
The 4th track is empty but still occupies space

auto-fit:
┌────────────┐ ┌────────────┐ ┌────────────┐
│     A      │ │     B      │ │     C      │
└────────────┘ └────────────┘ └────────────┘
Empty tracks are collapsed to 0
Items A, B, C each get 300px (900/3 tracks)
```

**When to use which:**

- `auto-fill`: when you want items to maintain their minimum size even if that leaves empty columns — useful when you'll add more items dynamically and don't want the layout to reflow
- `auto-fit`: when you want items to grow and fill the entire row — the common "responsive grid without media queries" use case

```css
/* Responsive grid that needs no media queries — the most common use case */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}
/* Result: as many columns as fit at minimum 280px, always filling the full width */
```

## `minmax()` and `min-content` / `max-content`

`minmax(min, max)` defines a track size range. The browser assigns any size between `min` and `max`:

```css
/* A column that's at least 200px wide but can grow to 1 fr */
grid-template-columns: minmax(200px, 1fr);

/* A row that's at least content height but can grow to 300px */
grid-template-rows: minmax(min-content, 300px);
```

`min-content`: the smallest size where content doesn't overflow (long word width for text, image intrinsic width for images).
`max-content`: the size at which content doesn't wrap at all (a full sentence on one line).

```css
/* Column sized to its longest word, not allowing wrapping */
grid-template-columns: min-content 1fr;

/* Column sized to its longest content line */
grid-template-columns: max-content 1fr;
```

`fit-content(value)` caps the track at `value` but allows it to shrink to `min-content`:

```css
/* Track grows up to 300px, shrinks to content minimum */
grid-template-columns: fit-content(300px) 1fr;
```

## Subgrid — aligning across component boundaries

Standard grid items create their own formatting context — a child grid's columns are independent of the parent grid's columns. Subgrid allows a child grid item to inherit the parent's track structure:

```css
.parent {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  grid-template-rows: auto auto auto;
  gap: 16px;
}

.card {
  grid-column: span 2;
  display: grid;
  /* Instead of defining new columns, inherit parent's column tracks */
  grid-template-columns: subgrid;
  /* Inherit parent's row tracks too */
  grid-template-rows: subgrid;
}

.card-header { grid-row: 1; }
.card-body   { grid-row: 2; }
.card-footer { grid-row: 3; }
```

With subgrid, all cards' headers align on the same row, all bodies align, all footers align — even when content heights vary. Without subgrid, each card is an independent grid and there's no way to align rows across cards without JavaScript-based height synchronization.

Browser support: subgrid is now supported in all major browsers (Chrome 117+, Firefox 71+, Safari 16+). It was the most-requested missing CSS feature for years.

## Named lines and named areas for responsive layouts

A powerful pattern: define multiple grid layouts in a single `grid-template-areas` redefinition via media query:

```css
.layout {
  display: grid;
  gap: 16px;
  grid-template-columns: 1fr;
  grid-template-areas:
    "header"
    "main"
    "sidebar"
    "footer";
}

@media (min-width: 768px) {
  .layout {
    grid-template-columns: 240px 1fr;
    grid-template-areas:
      "header  header"
      "sidebar main"
      "footer  footer";
  }
}

/* Item placement never changes — only the area definitions change */
.header  { grid-area: header; }
.sidebar { grid-area: sidebar; }
.main    { grid-area: main; }
.footer  { grid-area: footer; }
```

All items stay assigned to their named areas. The media query only changes where those areas are positioned. No item-level media queries needed.

## Real layout examples

### Dashboard with a fixed sidebar and dynamic main area

```css
.dashboard {
  display: grid;
  grid-template-columns: 260px 1fr;
  grid-template-rows: 60px 1fr;
  grid-template-areas:
    "sidebar topbar"
    "sidebar content";
  height: 100vh;
}

.sidebar  { grid-area: sidebar; overflow-y: auto; }
.topbar   { grid-area: topbar; }
.content  { grid-area: content; overflow-y: auto; }
```

### Masonry-approximation with dense packing

```css
.masonry {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  grid-auto-rows: 10px; /* small unit for fine-grained row control */
  gap: 16px 16px;
  grid-auto-flow: dense;
}

/* Items control their own height by spanning multiple rows */
.item-small  { grid-row: span 20; } /* 20 × 10px = 200px */
.item-medium { grid-row: span 30; }
.item-large  { grid-row: span 40; }
```

### Calendar grid

```css
.calendar {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 1px;
  background: var(--border-color);
}

.day-header {
  background: white;
  text-align: center;
  padding: 8px;
}

.day {
  background: white;
  min-height: 100px;
  padding: 8px;
}

.day[data-weekday="1"] { grid-column: 2; } /* First day of month on Tuesday */
```

### Magazine layout with named areas

```css
.magazine {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  grid-template-rows: auto;
  gap: 16px;
}

.lead-story {
  grid-column: 1 / 4;
  grid-row: 1 / 3;
}

.secondary-story {
  grid-column: 4 / 7;
  grid-row: 1;
}

.tertiary-story {
  grid-column: 4 / 7;
  grid-row: 2;
}
```

## When Grid beats Flexbox — and when it doesn't

**Use Grid when:**

1. **Two-dimensional layout** — you need to control both rows and columns simultaneously. Page layouts, dashboards, card grids where row heights should align across columns.

2. **Layout-first thinking** — the structure is defined independently of content. The grid exists and items fill it.

3. **Alignment across independent components** — subgrid allows headers, bodies, and footers of sibling cards to align on the same row tracks.

4. **Named areas** — when `grid-template-areas` communicates the intent of a layout better than nested divs.

5. **Precise placement** — items that need to overlap or be placed at specific grid coordinates.

**Use Flexbox when:**

1. **One-dimensional layout** — items in a row OR a column, where cross-axis alignment is secondary.

2. **Content-driven sizing** — item sizes are determined by content, and the container should accommodate them.

3. **Dynamic item counts** — navigation bars, tag lists, toolbars where the number of items varies and you want them to wrap naturally.

4. **Space distribution along one axis** — `justify-content: space-between` for a header with logo and actions.

5. **Single component internals** — a card's internal layout (icon + text + button) is almost always Flexbox.

**The practical rule:**

Page-level layout, grid systems, anything where rows and columns interact → Grid.
Component internals, linear lists, single-axis distributions → Flexbox.

They compose naturally:

```css
/* Grid for the page layout */
.page { display: grid; grid-template-areas: "sidebar main"; }

/* Flexbox inside each grid area for component internals */
.main-header { display: flex; align-items: center; justify-content: space-between; }
```

## Common interview traps

**"What's the difference between `auto-fill` and `auto-fit`?"**

Both create as many tracks as fit in the container. The difference appears when there are fewer items than tracks. `auto-fill` keeps empty tracks — items don't grow beyond their `max` in `minmax()`. `auto-fit` collapses empty tracks to zero — items grow to fill the full container width. With enough items to fill all columns, both behave identically.

---

**"What does `1fr` mean exactly?"**

One fraction unit of the available free space — not one fraction of the container width. Free space is what remains after all fixed-size tracks (px, em, %) and gaps are resolved. If a 900px container has a 200px fixed column and two `1fr` columns with a 20px gap, free space = `900 - 200 - 2×20 = 660px`, and each `fr` = `330px`.

---

**"Why is `fr` better than `%` for grid columns?"**

Percentages are calculated from the container's full width, before gaps are subtracted. Three `33.33%` columns with a `20px` gap sum to more than 100% and overflow. `fr` distributes only the remaining space after gaps — columns never overflow.

---

**"How do you make a full-width item in a grid?"**

`grid-column: 1 / -1`. Line `-1` always refers to the last grid line of the explicit grid. If you have `grid-template-columns: repeat(4, 1fr)`, there are 5 column lines (1 through 5). `1 / -1` spans from line 1 to line 5 — the full width. Note: `-1` only works on the explicit grid. Items in the implicit grid (extra rows) cannot use `-1` to span full width unless you explicitly define those rows in `grid-template-rows`.

---

**"Why doesn't `grid-auto-flow: dense` preserve the visual order of items?"**

Dense packing backfills gaps in the grid left by larger items. To do this, the browser may place a smaller later item before a larger earlier item. The DOM order (and therefore tab order) remains unchanged — only visual position changes. This creates a mismatch between visual and keyboard order, which is an accessibility issue. `dense` should only be used for purely decorative grids (image galleries) where keyboard navigation order doesn't need to match visual order.

---

**"What is subgrid and when would you use it?"**

Subgrid allows a grid item that is itself a grid container to inherit (not copy) the parent's row or column tracks. Without subgrid: a card grid where each card has a header, body, and footer — if card bodies have different content heights, footers don't align across cards. With `grid-template-rows: subgrid`, all cards share the parent's row tracks, and footers align automatically. Supported in all major browsers since Chrome 117 (August 2023).
