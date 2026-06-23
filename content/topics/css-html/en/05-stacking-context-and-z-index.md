# Stacking Context and z-index

## Why z-index is misunderstood — the mental model is wrong

Most developers think of z-index as a global stack: "element with z-index: 100 always appears above element with z-index: 10." This model is wrong. z-index is local — it competes within the same **stacking context**, and different stacking contexts are ordered relative to each other as atomic units.

The correct mental model: the browser renders a tree of stacking contexts, not a flat list of z-index values. An element with `z-index: 9999` inside a stacking context that is rendered below another stacking context will appear behind every element in that other context — including elements with `z-index: 1`.

## The paint order without stacking contexts

Before introducing stacking contexts, understand the default paint order for a document without any positioned elements:

1. Background and borders of the root element
2. Block-level descendants in normal flow (in DOM order)
3. Floating elements
4. Inline-level descendants in normal flow (in DOM order)

Later in DOM order = painted on top. No z-index needed, no stacking contexts involved.

## What a stacking context is

A stacking context is an element that forms an independent layer in the rendering. Elements inside a stacking context are painted together and ordered relative to each other using z-index. The stacking context itself is then placed as a single unit relative to sibling stacking contexts.

Within a stacking context, the paint order is:

1. The element itself (background + border)
2. Descendants with negative z-index (lowest first)
3. Block-level descendants in normal flow
4. Floating descendants
5. Inline-level descendants in normal flow
6. Descendants with z-index: 0 or z-index: auto and positioned
7. Descendants with positive z-index (lowest first)

The critical constraint: **z-index values only compare elements within the same stacking context.** An element with `z-index: 1000` in stacking context A cannot be compared against an element with `z-index: 1` in stacking context B by their z-index values alone — it depends on the stacking order of contexts A and B themselves.

## The full list of stacking context triggers

This is the list most developers don't have memorized — and it's the source of almost every "why doesn't my z-index work?" bug.

**Positioning + z-index:**
- `position: absolute`, `relative`, `fixed`, or `sticky` with a `z-index` value other than `auto`

**Opacity:**
- `opacity` less than `1`

**Transforms:**
- `transform` other than `none`
- `translate`, `rotate`, `scale` (individual transform properties, not `none`)
- `perspective` other than `none`
- `transform-style: preserve-3d`

**Filters and effects:**
- `filter` other than `none`
- `backdrop-filter` other than `none`
- `clip-path` other than `none`
- `mask` / `mask-image` / `mask-border` other than `none`

**Compositing:**
- `mix-blend-mode` other than `normal`
- `isolation: isolate`

**Layout containment:**
- `contain: layout`, `contain: paint`, `contain: strict`, `contain: content`

**Will-change:**
- `will-change` set to any property that would create a stacking context on its own
  (e.g., `will-change: transform`, `will-change: opacity`)

**Other:**
- `position: fixed` or `position: sticky` (always, regardless of z-index value)

```css
/* All of these create a stacking context: */
.a { position: relative; z-index: 1; }       /* ← classic */
.b { opacity: 0.99; }                         /* ← surprise */
.c { transform: translateX(0); }              /* ← GPU optimization side effect */
.d { filter: blur(0px); }                     /* ← another surprise */
.e { will-change: transform; }                /* ← performance hint side effect */
.f { isolation: isolate; }                    /* ← explicit, intentional */
.g { position: fixed; }                       /* ← always, no z-index needed */
```

## Why `z-index: 9999` stops working — illustrated

The most common real-world scenario:

```html
<div class="card" style="position: relative; z-index: 1;">
  <div class="tooltip" style="position: absolute; z-index: 9999;">
    I should appear above everything
  </div>
</div>

<div class="modal-overlay" style="position: relative; z-index: 2;">
  <!-- This entire stacking context is above z-index: 1 -->
</div>
```

The tooltip has `z-index: 9999`, but it lives inside the `.card` stacking context which has `z-index: 1`. The `.modal-overlay` has `z-index: 2`. Since `2 > 1`, the entire `.card` context (including the tooltip with 9999) renders behind `.modal-overlay`. The 9999 value is compared only against other children of `.card`, not against the overlay.

**Another common scenario — the transform trap:**

```html
<style>
  .sidebar {
    transform: translateX(0); /* GPU compositing optimization */
    /* This creates a stacking context! */
  }

  .dropdown {
    position: absolute;
    z-index: 1000;
    /* Positioned relative to .sidebar's stacking context */
  }

  .page-header {
    position: relative;
    z-index: 10;
  }
</style>

<header class="page-header">...</header>
<aside class="sidebar">
  <div class="dropdown">Should appear above header?</div>
</aside>
```

`.sidebar`'s stacking context order vs `.page-header`'s stacking context order depends on DOM order and their z-index values. The dropdown's `z-index: 1000` is irrelevant to this comparison — only `.sidebar`'s z-index value (which is `auto`, since we never set it) matters. With `z-index: auto`, the sidebar doesn't form a proper stacking context and its children can compete globally... wait, actually `transform` alone without a z-index: the element participates in the stacking context of its containing block as a stacking-context-forming element with `z-index: auto` effectively — meaning it stacks as if it had `z-index: 0`.

The real fix needed: remove the `transform` from `.sidebar` (use a different GPU compositing approach) or give `.sidebar` an explicit `z-index` that is higher than `.page-header`.

## The `isolation` property — intentional stacking context

`isolation: isolate` creates a stacking context without any visual side effect. It's the explicit, intention-revealing way to contain a component's z-index stack.

**The problem it solves:**

```html
<style>
  .modal { position: fixed; z-index: 100; }

  /* Third-party component creates a stacking context with a high z-index */
  .third-party-widget { position: relative; z-index: 50; }
  .third-party-widget .internal-popup { position: absolute; z-index: 999; }
  /* The internal popup z-index: 999 is inside a z-index: 50 context.
     If our modal is z-index: 100 > 50, the popup appears behind our modal.
     But what if we want the widget's internal stack to be self-contained
     regardless of what we put around it? */
</style>
```

**Using `isolation: isolate` to contain a component:**

```css
/* Wrap your own component to prevent its z-index from leaking out */
.card-component {
  isolation: isolate;
  /* Now any z-index inside .card-component only competes
     with other elements inside .card-component.
     The card as a whole stacks in the natural DOM order
     without any z-index value. */
}

.card-component .dropdown {
  position: absolute;
  z-index: 10;
  /* This 10 doesn't compete with z-index: 5 outside the card */
}
```

This is the CSS equivalent of a module boundary: internal z-index values are implementation details, not exposed to the outside world.

**When `isolation: isolate` is essential:**

- Design system components that must work in any z-index environment
- Third-party embeds where you can't control internal z-index values
- Storybook or documentation pages where components render in isolation
- Components that use `mix-blend-mode` and shouldn't blend with sibling elements

```css
/* mix-blend-mode without isolation bleeds through to unrelated ancestors */
.text-overlay {
  mix-blend-mode: multiply;
  /* Without isolation, blends with everything behind it */
}

/* isolation: isolate on a wrapper prevents the blend mode from escaping */
.image-card {
  isolation: isolate; /* blend modes inside only blend with each other */
}
.image-card .text-overlay {
  mix-blend-mode: multiply; /* blends with .image-card's background only */
}
```

## `z-index: auto` vs `z-index: 0` — an important distinction

```css
.a { position: relative; z-index: auto; } /* does NOT create a stacking context */
.b { position: relative; z-index: 0; }   /* DOES create a stacking context */
```

With `z-index: auto`: the element is positioned but participates in the parent's stacking context. Its children can have z-index values that compete with the element's siblings.

With `z-index: 0`: a stacking context is created. Children's z-index values are contained within it.

```html
<div style="position: relative; z-index: auto;">
  <span style="position: relative; z-index: 5;">
    <!-- z-index: 5 competes with siblings of the parent div -->
  </span>
</div>

<div style="position: relative; z-index: 0;">
  <span style="position: relative; z-index: 5;">
    <!-- z-index: 5 is contained — only competes within this div -->
  </span>
</div>
```

## Negative z-index — what it actually does

Negative z-index places an element behind its stacking context's background. This is often misused:

```css
.parent {
  position: relative;
  background: white;
}

.child {
  position: relative;
  z-index: -1;
  /* Rendered behind .parent's background — effectively invisible
     if .parent has a non-transparent background */
}
```

For the child to appear between the parent's background and other content, the parent must create a stacking context (otherwise the child escapes to a grandparent stacking context):

```css
/* This creates a decorative element behind a card's content but above its background */
.card {
  position: relative;
  isolation: isolate; /* creates a stacking context, contains the negative z-index */
  background: white;
}

.card::before {
  content: '';
  position: absolute;
  z-index: -1;
  /* Now: behind .card's other children, above .card's background */
}
```

Without the stacking context on `.card`, the `::before` with `z-index: -1` would escape to the root stacking context and potentially appear behind the entire page background.

## Practical debugging approach

When z-index isn't working as expected, follow this process:

**Step 1: Find the stacking contexts in the ancestor chain**

For each element involved, walk up the DOM and identify every ancestor that creates a stacking context. Check for: `position` + `z-index`, `opacity < 1`, `transform`, `filter`, `will-change`, `isolation`, `contain`.

```javascript
// DevTools console: find what creates a stacking context for an element
function findStackingContexts(el) {
  const contexts = [];
  let node = el.parentElement;
  while (node && node !== document.documentElement) {
    const style = getComputedStyle(node);
    const isContext =
      (style.position !== 'static' && style.zIndex !== 'auto') ||
      parseFloat(style.opacity) < 1 ||
      style.transform !== 'none' ||
      style.filter !== 'none' ||
      style.isolation === 'isolate' ||
      style.willChange !== 'auto';
    if (isContext) contexts.push({ node, style });
    node = node.parentElement;
  }
  return contexts;
}
```

**Step 2: Compare the stacking contexts, not the z-index values**

Once you've found the containing stacking contexts for both elements, compare those contexts' z-index values (or DOM order if z-index is equal).

**Step 3: Fix at the right level**

Fix the z-index at the stacking context level, not on the inner element. If element A's stacking context is behind element B's context, no amount of z-index on A's children will fix it.

**Step 4: Use DevTools layers panel**

Chrome DevTools → Layers panel shows all compositing layers (which often correspond to stacking contexts). You can see the layer tree and identify which element is causing unexpected containment.

**Common fixes:**

```css
/* Fix 1: Give the stacking context a higher z-index */
.sidebar {
  transform: translateX(0);
  z-index: 20; /* now .sidebar's context is above .header's context */
}

/* Fix 2: Remove the unintended stacking context trigger */
.sidebar {
  /* Remove: transform: translateX(0); */
  /* Use instead: */
  will-change: transform; /* still hints GPU, but... wait, this ALSO creates a context */
  /* Actually for GPU compositing without stacking context side effects,
     use translateZ(0) or translate3d(0,0,0) is not the answer — they all create contexts.
     The real answer: accept the context and manage z-index properly. */
}

/* Fix 3: Isolate intentionally */
.component {
  isolation: isolate;
  position: relative;
  z-index: 5; /* compete at this level */
}

/* Fix 4: Move the element outside the problematic stacking context */
/* Portal pattern: render modals, dropdowns, tooltips as children of <body>
   to avoid being trapped inside a component's stacking context */
```

The **portal pattern** is the correct architectural solution for UI overlays (modals, dropdowns, tooltips): render them as direct children of `<body>` (or a dedicated portal container at the root), not inside the component tree. This is why React Portal, Vue Teleport, and Angular CDK Overlay exist.

## Common interview traps

**"Why doesn't `z-index: 9999` work?"**

Almost always a stacking context issue. The element is inside a stacking context whose own z-index (relative to sibling contexts) is lower than the element it needs to appear above. z-index values only compete within the same stacking context. The fix is at the stacking context level, not on the inner element.

---

**"What creates a stacking context?"**

The answer interviewers want is more than just "position + z-index." The full list includes: `opacity < 1`, `transform` (any non-none value), `filter` (any non-none value), `will-change` pointing to compositing properties, `isolation: isolate`, `contain: layout/paint/strict/content`, `mix-blend-mode` (non-normal), `clip-path` (non-none), `mask`, `backdrop-filter`, and `position: fixed/sticky` (always, regardless of z-index).

---

**"What's the difference between `z-index: 0` and `z-index: auto` on a positioned element?"**

`z-index: auto`: positioned element participates in the parent stacking context without creating its own. Its children's z-index values compete with the element's siblings. `z-index: 0`: creates a new stacking context. Children's z-index values are contained within it and cannot compete with outside elements.

---

**"What does `isolation: isolate` do and when would you use it?"**

Creates a stacking context with no visual side effects — the element itself is not transformed, filtered, or made partially transparent. Useful for: (1) containing z-index values within a component so they don't leak into the surrounding context; (2) preventing `mix-blend-mode` from blending with elements outside the component; (3) creating predictable z-index behavior for design system components that must work in any environment.

---

**"You have a dropdown that appears behind a sticky header — how do you debug and fix it?"**

1. Check the stacking context of the sticky header (it always creates one — `position: sticky` is enough). Find its z-index or DOM position.
2. Check what stacking context the dropdown's parent is in. If the dropdown's parent stacking context has a lower z-index than the sticky header's context, the dropdown will always appear behind.
3. Fix: give the dropdown's parent stacking context a z-index higher than the header's context, or render the dropdown in a portal outside the parent's stacking context.
