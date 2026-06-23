# CSS Architecture Patterns

## The core problem all CSS architectures solve

CSS has two properties that make it difficult at scale:

1. **Global scope** — every selector competes against every other selector in the entire document. There is no built-in module boundary.
2. **Specificity escalation** — when a style doesn't apply, the instinctive fix is to make the selector more specific. This creates a ratchet: specificity only ever goes up, making overrides increasingly difficult.

Every CSS architecture — BEM, CSS Modules, CSS-in-JS, Tailwind — is a different answer to the same question: **how do we prevent global scope and specificity escalation from making CSS unmaintainable?**

## BEM — Block Element Modifier

### The naming convention

BEM (Block, Element, Modifier) is a naming convention that encodes component hierarchy into class names:

```
block              → .card
block__element     → .card__header
block__element     → .card__body
block__element     → .card__footer
block--modifier    → .card--featured
element--modifier  → .card__header--large
```

```html
<article class="card card--featured">
  <header class="card__header card__header--large">
    <h2 class="card__title">Title</h2>
    <span class="card__tag">New</span>
  </header>
  <div class="card__body">
    <p class="card__description">...</p>
  </div>
  <footer class="card__footer">
    <button class="card__action card__action--primary">Read more</button>
  </footer>
</article>
```

```css
.card { background: white; border-radius: 8px; }
.card--featured { border: 2px solid #0066cc; }
.card__header { padding: 16px 16px 0; }
.card__header--large { padding: 24px 24px 0; }
.card__title { font-size: 1.25rem; font-weight: 700; }
.card__body { padding: 16px; }
.card__footer { padding: 0 16px 16px; }
.card__action { display: inline-flex; padding: 8px 16px; }
.card__action--primary { background: #0066cc; color: white; }
```

### Why BEM works — the reasoning, not just the convention

BEM's power isn't the double underscore — it's the constraint that **every selector is a single class with specificity `(0, 1, 0)`**.

Without BEM:
```css
.card .header { }           /* (0, 2, 0) */
.card .header .title { }    /* (0, 3, 0) */
.featured .card .title { }  /* (0, 3, 0) — same specificity, source order decides */
```

Every new style rule can create a specificity conflict. Overriding anything requires matching or beating the existing specificity.

With BEM:
```css
.card__header { }   /* (0, 1, 0) */
.card__title { }    /* (0, 1, 0) */
.card--featured { } /* (0, 1, 0) */
```

Everything is `(0, 1, 0)`. There are **no specificity conflicts** — the last rule wins (source order). Overriding is trivially: write a rule with any specificity above `(0, 1, 0)`.

The name encodes the relationship: `.card__title` tells you this is the title inside a card, without requiring nesting in the selector. You can move the HTML, change the DOM structure, and the styles still work — the coupling is in the name, not in the selector hierarchy.

### BEM gotchas

**Don't mirror DOM nesting in BEM names:**

```html
<!-- Wrong: BEM depth follows DOM depth -->
<div class="card">
  <div class="card__body">
    <div class="card__body__content">  <!-- card__body__content is wrong -->
      <p class="card__body__content__text">  <!-- even worse -->

<!-- Correct: flat BEM, regardless of DOM nesting -->
<div class="card">
  <div class="card__body">
    <div class="card__content">  <!-- element of card, not of card__body -->
      <p class="card__text">
```

Elements belong to the Block, not to other Elements. `card__body__content` means "content inside body inside card" — but BEM doesn't support element nesting. Flatten it: `card__content`.

**Modifiers modify, they don't replace:**

```html
<!-- Wrong: modifier replaces the base class -->
<button class="card__action--primary">

<!-- Correct: modifier adds to the base class -->
<button class="card__action card__action--primary">
```

Without the base class, you'd have to duplicate all the base styles in the modifier. BEM modifiers add to the base, not replace it.

**When to start a new Block vs use an Element:**

Ask: "Can this component exist independently?" If yes — new Block. If it only makes sense inside another component — Element.

```css
/* .card__action is an element — it only exists inside cards */
/* .button is a block — it can exist anywhere */
```

### BEM doesn't solve global scope

BEM still puts classes in global CSS scope. Two developers could both create `.card__title` with different intentions. In small teams, this works fine (conventions + code review). In large teams or when integrating third-party components, it's a problem.

## CSS Modules

CSS Modules solve the global scope problem by **automatically scoping class names to the file that defines them**. At build time, each class name is transformed into a unique identifier:

```css
/* card.module.css */
.card { background: white; border-radius: 8px; }
.header { padding: 16px; }
.title { font-size: 1.25rem; }
.action { padding: 8px 16px; }
.actionPrimary { background: #0066cc; color: white; }
```

```javascript
// Card.tsx
import styles from './card.module.css';

function Card() {
  return (
    <article className={styles.card}>
      <header className={styles.header}>
        <h2 className={styles.title}>Title</h2>
      </header>
      <footer>
        <button className={`${styles.action} ${styles.actionPrimary}`}>
          Read more
        </button>
      </footer>
    </article>
  );
}
```

Output HTML:
```html
<article class="card_card__3xK9p">
  <header class="card_header__7mP2a">
    <h2 class="card_title__1vRq8">Title</h2>
  </header>
  <footer>
    <button class="card_action__2nJ4k card_actionPrimary__8cD3m">
      Read more
    </button>
  </footer>
</article>
```

The generated class names are unique — no collisions possible across files.

### CSS Modules features

**`:global` — escaping the scope:**

```css
/* This class applies globally, not scoped */
:global(.third-party-class) { color: red; }

/* Mix of global and local */
:global(.theme-dark) .card { background: #1a1a2e; }
```

**`composes` — style inheritance:**

```css
/* base.module.css */
.button {
  display: inline-flex;
  padding: 8px 16px;
  border-radius: 4px;
  font-weight: 600;
}

/* card.module.css */
.action {
  composes: button from './base.module.css';
  /* Adds the 'button' class to the element — no style duplication */
  background: #0066cc;
  color: white;
}
```

`composes` adds the composed class to the element at runtime — the element gets both class names in the HTML, no style copying.

### What CSS Modules don't solve

- No dynamic styles based on JavaScript state — you have to toggle classes, not change property values inline
- No co-location of styles and logic (they're separate files)
- Verbose syntax for conditional classes
- The scoping is a build-step convention — the generated CSS is still global in production, just with unique names

## CSS-in-JS

CSS-in-JS writes styles as JavaScript, co-located with the component. Two dominant approaches: **runtime** (Styled Components, Emotion) and **zero-runtime** (Linaria, vanilla-extract, StyleX).

### Runtime CSS-in-JS (Styled Components, Emotion)

```typescript
// Styled Components
import styled from 'styled-components';

const Card = styled.article<{ featured?: boolean }>`
  background: white;
  border-radius: 8px;
  border: ${({ featured }) => featured ? '2px solid #0066cc' : 'none'};
`;

const CardTitle = styled.h2`
  font-size: 1.25rem;
  font-weight: 700;
`;

const ActionButton = styled.button<{ variant?: 'primary' | 'secondary' }>`
  display: inline-flex;
  padding: 8px 16px;
  background: ${({ variant }) => variant === 'primary' ? '#0066cc' : 'transparent'};
  color: ${({ variant }) => variant === 'primary' ? 'white' : '#0066cc'};
`;

// Usage:
<Card featured>
  <CardTitle>Title</CardTitle>
  <ActionButton variant="primary">Read more</ActionButton>
</Card>
```

**How runtime CSS-in-JS works under the hood:**

1. At render time, JavaScript evaluates the template literal with current props
2. A unique class name is generated (typically a hash of the style content)
3. A `<style>` tag is injected into `<head>` with the CSS for that class name
4. The generated class name is applied to the element

Dynamic styles (based on props) generate new class names — each unique combination of prop values can create a new CSS rule.

**Runtime CSS-in-JS advantages:**
- Full JavaScript power in styles — conditions, loops, theme variables
- Co-location: styles and component in one file
- Automatic scoping — no class name collisions
- Type-safe props on styled components
- Dead code elimination: unused components = unused styles

**Runtime CSS-in-JS disadvantages:**
- **Runtime cost**: style injection happens in JavaScript on the main thread — adds to TTI (Time to Interactive)
- **React Server Components incompatibility**: runtime style injection requires the browser JS environment — RSC doesn't have it
- **Hydration cost**: on SSR, styles must be serialized and re-injected on the client
- Larger JavaScript bundle

### Zero-runtime CSS-in-JS (vanilla-extract, StyleX, Linaria)

Zero-runtime approaches move style generation to build time:

```typescript
// vanilla-extract — styles.css.ts
import { style, styleVariants } from '@vanilla-extract/css';

export const card = style({
  background: 'white',
  borderRadius: '8px',
});

export const cardVariants = styleVariants({
  default: { border: 'none' },
  featured: { border: '2px solid #0066cc' },
});

export const title = style({
  fontSize: '1.25rem',
  fontWeight: 700,
});

// Component.tsx
import { card, cardVariants, title } from './styles.css';

function Card({ featured }: { featured?: boolean }) {
  return (
    <article className={`${card} ${featured ? cardVariants.featured : cardVariants.default}`}>
      <h2 className={title}>Title</h2>
    </article>
  );
}
```

At build time, vanilla-extract generates actual `.css` files with hashed class names. Zero JavaScript runtime cost — just static CSS files.

**Trade-off**: no truly dynamic styles at runtime. Variants must be enumerated at build time. For genuinely dynamic values (user-inputted colors, arbitrary pixel values), inline styles or CSS custom properties are needed.

### CSS custom properties as the zero-runtime dynamic style bridge

```typescript
// Zero-runtime CSS-in-JS + runtime dynamic values via custom properties
// styles.css.ts (vanilla-extract)
import { style, createVar } from '@vanilla-extract/css';

export const accentColor = createVar();

export const card = style({
  vars: { [accentColor]: '#0066cc' }, // default
  borderColor: accentColor,
});

// Component.tsx — dynamic value via inline style on the var
function Card({ color }: { color: string }) {
  return (
    <article
      className={card}
      style={{ [accentColor]: color }} // override the custom property
    >
```

The custom property is set inline (dynamic, no class generation), the rest of the styles are in static CSS.

## Utility-first CSS (Tailwind)

Tailwind provides a large set of single-purpose utility classes that map directly to CSS properties:

```html
<!-- BEM equivalent: -->
<article class="card card--featured">
  <header class="card__header">
    <h2 class="card__title">Title</h2>
  </header>
</article>

<!-- Tailwind equivalent: -->
<article class="bg-white rounded-lg border-2 border-blue-600 shadow-md">
  <header class="px-4 pt-4">
    <h2 class="text-xl font-bold text-gray-900">Title</h2>
  </header>
</article>
```

### How Tailwind actually works

Tailwind scans your source files for class names and generates only the CSS for classes that are actually used (tree-shaking). The generated CSS is a static file with single-property classes:

```css
/* Generated by Tailwind — only classes used in your files */
.bg-white { background-color: rgb(255 255 255); }
.rounded-lg { border-radius: 0.5rem; }
.border-2 { border-width: 2px; }
.border-blue-600 { border-color: rgb(37 99 235); }
.text-xl { font-size: 1.25rem; line-height: 1.75rem; }
.font-bold { font-weight: 700; }
.px-4 { padding-left: 1rem; padding-right: 1rem; }
.pt-4 { padding-top: 1rem; }
```

Every class has specificity `(0, 1, 0)` and declares a single property. Conflicts between utilities are resolved by source order — the class that appears later in the generated CSS wins.

### Tailwind advantages

**No naming decisions**: the hardest part of CSS at scale is naming. Tailwind eliminates it — you never name a component or choose a class hierarchy.

**Co-location**: styles are in the HTML (or JSX). You don't switch files to change a style.

**Predictable specificity**: every class is `(0, 1, 0)`. No specificity wars possible.

**Consistent design system**: Tailwind's scale (`text-sm`, `text-base`, `text-lg`) enforces a design system. Arbitrary values (`text-[17px]`) exist but are discouraged.

**Performance**: generated CSS is tiny (5–20KB typical for a large app, gzipped) because unused utilities are purged.

### Tailwind disadvantages

**HTML verbosity**: long class lists on complex components are hard to scan. A card with 15 utility classes on the wrapping element is noisy.

**Component abstraction pressure**: without naming, you rely on component abstraction (React/Vue components) to avoid repeating class lists. Raw HTML + Tailwind becomes unwieldy.

**Customization friction**: non-standard values require either extending the config or using arbitrary values (`text-[17px]`, `bg-[#1a1a2e]`). Extending the config is YAML, not CSS.

**Cognitive load for newcomers**: requires learning the Tailwind API (class names aren't obvious — `py-4` vs `padding-block: 1rem`).

**Dynamic styles**: Tailwind class names must be complete strings in the source — string concatenation breaks the scanner:

```javascript
// Wrong — Tailwind's scanner won't find 'bg-blue-600'
const color = 'blue';
<div className={`bg-${color}-600`}>  // won't work

// Correct — full class names in source
const classMap = { blue: 'bg-blue-600', red: 'bg-red-600' };
<div className={classMap[color]}>
```

### The `@apply` escape hatch

For repetitive utility combinations that need a name, Tailwind provides `@apply`:

```css
/* In your CSS — extract repeated patterns into a class */
@layer components {
  .btn {
    @apply inline-flex items-center justify-center px-4 py-2 font-semibold rounded-md;
  }
  .btn-primary {
    @apply btn bg-blue-600 text-white hover:bg-blue-700;
  }
}
```

`@apply` is controversial — it re-introduces the naming problem Tailwind was meant to avoid. Use sparingly, only for shared patterns that appear in many places.

## Comparison — when each approach fits

### Scale and team size

| Approach | Small team / prototype | Medium team / product | Large team / design system |
|---|---|---|---|
| Plain CSS + BEM | ✓ Excellent | ✓ Good | ⚠ Needs strict discipline |
| CSS Modules | ✓ Good | ✓ Excellent | ✓ Good |
| CSS-in-JS (runtime) | ✓ Good | ✓ Good | ⚠ Performance concerns at scale |
| CSS-in-JS (zero-runtime) | ⚠ Setup overhead | ✓ Good | ✓ Excellent |
| Tailwind | ✓ Excellent | ✓ Excellent | ⚠ Needs component system |

### Technical constraints

**Use BEM when:**
- The project is framework-agnostic or uses multiple frameworks
- You need styles to work in environments without build tools
- The team is comfortable with CSS but not deep JavaScript

**Use CSS Modules when:**
- You're using a component framework (React, Vue, Svelte)
- You want the benefits of scoping without giving up "normal" CSS syntax
- You need to share styles across components without complex tooling

**Use runtime CSS-in-JS when:**
- Your styles depend heavily on runtime JavaScript state (theme switching, user customization)
- You need deep TypeScript integration (prop-typed styled components)
- **Not** when: using React Server Components, performance is critical (TTI), or SSR is a core requirement

**Use zero-runtime CSS-in-JS (vanilla-extract, StyleX) when:**
- You want type-safe styles without runtime cost
- Building a design system that needs to work across frameworks
- React Server Components or SSR performance matter

**Use Tailwind when:**
- Rapid prototyping or startup environments where iteration speed matters
- Component-framework projects where components abstract the class lists
- The team values convention over configuration
- You need a built-in design system without designing one

### The "right" answer in 2025

There is no single right answer — but a reasonable default for a React/Next.js production app is:

1. **Tailwind** for utility styling (spacing, colors, typography) — convention-driven, no naming overhead
2. **CSS custom properties** for dynamic/theme values
3. **CSS Modules** for complex component styles that are hard to express in utilities
4. **`@layer`** to organize the cascade between layers

This hybrid approach uses each tool where it excels. Pure Tailwind for everything creates HTML noise; pure CSS Modules for everything creates naming overhead; pure CSS-in-JS creates runtime costs.

## Common interview traps

**"Why does BEM use single classes instead of descendant selectors?"**

Single classes have uniform specificity `(0, 1, 0)`. Descendant selectors (`.card .title`) have higher specificity `(0, 2, 0)` and create coupling between the parent and child in the selector — if you move `.title` outside `.card` in the DOM, the style breaks. With BEM's `.card__title`, the relationship is in the name, not the selector. Overriding is trivial — any selector above `(0, 1, 0)` wins.

---

**"What's the difference between CSS Modules and CSS-in-JS?"**

CSS Modules: a build-time transformation that generates unique class names from CSS files. The CSS itself is standard CSS — no JavaScript at runtime. CSS-in-JS (runtime): JavaScript generates CSS at runtime, injecting `<style>` tags into the document. Allows dynamic styles based on props/state. Runtime cost, incompatible with RSC. CSS-in-JS (zero-runtime): like CSS Modules but with JavaScript/TypeScript syntax for authoring — styles are generated at build time, no runtime cost.

---

**"What's the main performance concern with runtime CSS-in-JS like Styled Components?"**

Two issues: (1) **JavaScript bundle size** — style definitions are JavaScript, adding to the bundle. (2) **Runtime style injection** — on every render, JavaScript computes the styles and injects/updates `<style>` tags on the main thread. This adds to Time to Interactive. On SSR, styles must be serialized (typically as a `<style>` tag in the HTML) and then the client must reconcile its generated styles with the server's, adding to hydration cost. These concerns become significant on large pages with many components.

---

**"What problem does Tailwind solve that BEM doesn't?"**

The naming problem. With BEM, you still must decide what to call your block, what its elements are, and what modifiers apply. This naming is a significant cognitive load at scale. Tailwind eliminates naming entirely — you apply utility classes directly. Additionally, Tailwind enforces design system constraints (using the scale's predefined values rather than arbitrary pixels) and avoids stylesheet growth — unused utilities are purged, so the CSS file stays small regardless of project size.

---

**"When would you choose CSS Modules over Tailwind?"**

For complex component styles that are difficult to express as utility combinations — intricate pseudo-element designs, complex animation keyframes, deeply conditional style logic, or styles that make more sense as a cohesive block than as 20 individual utilities. Also: when the team has strong CSS expertise and values explicit style authorship over convention; or when integrating with a design system that expresses styles as CSS variables rather than utility class mappings.
