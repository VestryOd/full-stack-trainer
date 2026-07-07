# Styling and Isolation

## Why global CSS leakage is the most common real-world MFE bug

CSS has zero encapsulation by default. A `.button { padding: 8px; }` written by the catalog team will override a visually identical `.button` in the checkout team's DOM — because all rendered DOM ends up in the same document, sharing one global CSSOM, no matter how independently each team built their code.

This is worse than the shared-dependency conflict from article 03: there, at least an error sometimes gets thrown (`Invalid hook call`) that you can trace through a stack trace. A CSS conflict just silently looks wrong — a badge is the wrong color, a margin is off — and it's much harder to trace back to whose stylesheet is at fault, especially when the teams involved never see each other's code.

## Solution 1 — CSS Modules

The mechanism: class names are hashed at build time (`.button` → `.button_a3f9d1`), scoped locally to the file — a naming collision becomes practically impossible because the hash is (nearly) globally unique.

```css
/* CheckoutApp.module.css */
.button { padding: 8px 16px; }
```

```tsx
import styles from './CheckoutApp.module.css';
<button className={styles.button}>Pay</button>
```

**Strengths:** works with ordinary CSS tooling, zero runtime cost, supported out of the box by most bundlers.

**Weaknesses:** only guarantees uniqueness of **class names** — it does nothing against a high-specificity global selector elsewhere on the page (a global tag selector like `button { ... }` from someone else's reset stylesheet still applies). And it requires **every** team to actually and consistently use CSS Modules — it does nothing, on its own, to protect against a sibling remote that decided not to.

## Solution 2 — Shadow DOM

Real, browser-native isolation of the DOM and CSS — not a build convention, an actual boundary. A custom element wraps its content in a shadow root; styles inside the shadow root don't leak out, and outside styles mostly don't leak in.

```ts
class CheckoutWidget extends HTMLElement {
  connectedCallback() {
    const shadow = this.attachShadow({ mode: 'open' });
    shadow.innerHTML = `
      <style>.button { padding: 8px 16px; }</style>
      <button class="button">Pay</button>
    `;
  }
}
customElements.define('checkout-widget', CheckoutWidget);
```

**Real trade-offs, not just upsides:**

- **Event retargeting.** Events dispatched inside a shadow DOM get their `target` retargeted to the shadow host when observed from outside — not to the actual element that fired them. This breaks naive event-delegation code and some analytics/tracking scripts that read `event.target` directly.
- **Third-party library compatibility.** Many libraries assume they can query the DOM globally (`document.querySelector`) or inject global styles/portals (React portals, modal libraries, some UI kits, tag-manager scripts). Such libraries often silently fail to find elements inside a shadow root, because it's a separate DOM subtree, unreachable by a plain global `document.querySelector` without explicitly piercing the boundary.
- **CSS custom properties (variables) cross the shadow DOM boundary by default** — inheritance through them still works. This is useful for passing shared design tokens (colors, spacing) into isolated shadow content, but it's often wrongly assumed that shadow DOM blocks absolutely everything — it doesn't; it only blocks "ordinary" style rules.

## Solution 3 — scoped CSS-in-JS

Libraries like styled-components or Emotion generate unique class names **at runtime** and inject component-scoped `<style>` tags directly into `<head>`. Same idea as CSS Modules, just resolved at runtime instead of build time.

```tsx
const Button = styled.button`
  padding: 8px 16px;
`;
```

**Strengths:** styles live next to the component, can be dynamic based on props, the same collision-avoidance guarantee as CSS Modules (hashed class names).

**Weaknesses:** a runtime cost (computing and injecting styles on every render), plus an MFE-specific gotcha: if two independently built remotes each use styled-components as **separate** bundled copies (not a shared singleton via Module Federation's `shared` config — see article 03), they can inject conflicting global resets, or — more subtly — run incompatible major versions of the library with different SSR/hydration behavior. The order of `<style>` tags injected independently by different remotes is essentially undefined — a later-injected tag can win on specificity regardless of the source order a developer expects, which looks like an intermittent, "flaky" visual bug tied to load order/timing rather than a logic error in either team's code.

## Solution 4 — naming convention discipline (BEM-style prefixing)

The pragmatic, zero-tooling default: prefix every class name with a namespace unique to each MFE.

```css
/* checkout-mfe */
.checkout__button--primary { padding: 8px 16px; }

/* catalog-mfe */
.catalog__button--primary { padding: 8px 16px; }
```

**Strengths:** works everywhere, requires no tooling, easy to reason about in devtools, works for legacy code and gradual migration.

**Weaknesses:** entirely convention-based — nothing technically enforces the prefix, and a new team member unfamiliar with the convention can trivially write an unprefixed global selector that silently collides with someone else's.

This is exactly why it's called "the pragmatic default" — it's the lowest common denominator that works when you can't force every team onto the same CSS tooling at the same time.

## A shared design system as a versioned package — and the version-skew problem

The real production practice: to avoid all of the above for the common building blocks (buttons, inputs, modals, typography), organizations extract them into a shared design-system package, e.g. `@company/design-system`, versioned and published like any npm package (or shared via Module Federation's `shared` config as a singleton — see article 03).

**The version-skew problem:** if catalog-mfe is pinned to `@company/design-system@2.1.0` and checkout-mfe to `@company/design-system@3.0.0` (a major version with breaking visual changes — a new spacing scale, different border-radius tokens), and the two are composed side by side on the same page (say, a checkout modal opening over a catalog page), the user literally sees **two visually different** button styles, both claiming to be the same design system, on the same screen.

This is the CSS-domain equivalent of the "two React copies" bug from article 03 — except no error is thrown here; it just looks visually inconsistent, which is arguably worse, since the problem is silent and only caught when an actual human looks at the page.

**Mitigation:** the same organizational discipline as shared-JS-dependency governance in article 03 — treat the design system's major version as a singleton requirement enforced across every consuming MFE (a CI check comparing versions across repos), with a defined upgrade window and rollout process, rather than letting each team upgrade a breaking version on its own schedule.

## Summary table of approaches

```txt
┌───────────────────┬───────────────────────┬───────────────┬────────────────────┬──────────────────┐
│ Approach            │ Isolation mechanism    │ Runtime cost   │ Third-party lib     │ Enforcement       │
│                    │                        │                │ compatibility       │                  │
├───────────────────┼───────────────────────┼───────────────┼────────────────────┼──────────────────┤
│ CSS Modules        │ Build-time name hash   │ None           │ Fine               │ Build convention  │
│                    │                        │                │                    │ only              │
├───────────────────┼───────────────────────┼───────────────┼────────────────────┼──────────────────┤
│ Shadow DOM         │ Real DOM boundary      │ Small          │ Poor (many libs    │ Enforced by the   │
│                    │                        │ (shadow root   │ expect a global    │ browser           │
│                    │                        │ parsing)       │ document)          │                  │
├───────────────────┼───────────────────────┼───────────────┼────────────────────┼──────────────────┤
│ CSS-in-JS          │ Runtime hash +         │ Some           │ Fine, but tag order│ Build/runtime     │
│                    │ injected <style>       │ (style compute)│ across remotes is  │ convention        │
│                    │                        │                │ undefined          │                  │
├───────────────────┼───────────────────────┼───────────────┼────────────────────┼──────────────────┤
│ BEM prefixing      │ Naming convention      │ None           │ Fine               │ None — pure       │
│                    │                        │                │                    │ discipline        │
└───────────────────┴───────────────────────┴───────────────┴────────────────────┴──────────────────┘
```

## Common interview traps

- **"One of these approaches fully solves style isolation"** — in practice, mature organizations combine them: BEM prefixing as a baseline discipline, a shared design-system package for common elements, and CSS Modules/CSS-in-JS within each MFE's own unique components.

- **"Shadow DOM is strictly superior to the other approaches because it's the only real isolation"** — real DOM isolation, yes, but paid for with event retargeting and incompatibility with libraries that expect global DOM access. It's a deliberate trade-off, not a free upgrade.

- **"CSS Modules protect against all style leakage"** — they only hash class names from your own modules; a global tag selector or a high-specificity reset stylesheet from someone else's CSS can still override your styles.

- **"A shared design system automatically solves version skew just by being shared"** — not on its own. A design system needs the same version-governance discipline as shared JS dependencies from article 03: without a CI check comparing versions across repos, major-version skew leads to silent visual inconsistency rather than a thrown error.

- **"CSS custom properties (variables) are blocked by the Shadow DOM boundary just like ordinary styles"** — no, they cross the shadow DOM boundary by default via inheritance, which is exactly what makes them a convenient mechanism for passing shared design tokens into isolated content.
