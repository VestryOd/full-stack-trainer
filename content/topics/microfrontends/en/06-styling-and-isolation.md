# Styling and Isolation

## Why global CSS leakage is the most common real-world micro-frontend bug

CSS has zero encapsulation by default. Say the catalog team writes `.button { padding: 8px; }`. That rule will override a visually identical `.button` in the checkout team's DOM (document object model — the browser's live tree of page elements).

Everything rendered ends up in the same document, sharing one global CSSOM (CSS object model — the matching tree of style rules). How independently each team built its code makes no difference.

This is worse than the shared-dependency conflict in [Module Federation: How It Actually Works Under the Hood](./03-module-federation-deep-dive.md). There, at least, an error sometimes gets thrown (`Invalid hook call`) and you can follow a stack trace.

A CSS conflict just silently looks wrong: a badge is the wrong color, a margin is off. Tracing it back to the guilty stylesheet is much harder, especially when the teams involved never see each other's code.

## Solution 1 — CSS Modules

The mechanism: class names are hashed at build time (`.button` → `.button_a3f9d1`) and scoped to the file. A naming collision becomes practically impossible, because the hash is very nearly globally unique.

```css
/* CheckoutApp.module.css */
.button { padding: 8px 16px; }
```

```tsx
import styles from './CheckoutApp.module.css';
<button className={styles.button}>Pay</button>
```

**Strengths:** works with ordinary CSS tooling, zero runtime cost, supported out of the box by most bundlers.

**Weaknesses:** the guarantee covers **class names** only. A high-specificity global selector elsewhere on the page still applies. One example is a global tag selector such as `button { ... }` in someone else's reset stylesheet. And CSS Modules only help if **every** team uses them consistently. A sibling remote that opted out can still break your layout.

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

- **Event retargeting.** An event dispatched inside a shadow DOM is seen from outside with its `target` set to the shadow host. It is not set to the element that actually fired it. This breaks naive event-delegation code, and some analytics scripts that read `event.target` directly.
- **Third-party library compatibility.** Many libraries assume they can query the DOM globally with `document.querySelector`. Others inject global styles or portals: React portals, modal libraries, component kits, tag-manager scripts. Such libraries often fail silently inside a shadow root. It is a separate DOM subtree, and a plain global `document.querySelector` cannot reach it without explicitly piercing the boundary.
- **CSS custom properties (variables) cross the shadow DOM boundary by default** — inheritance through them still works. That is useful: shared design tokens such as colors and spacing reach isolated shadow content. People often assume shadow DOM blocks absolutely everything. It does not — it blocks only ordinary style rules.

## Solution 3 — scoped CSS-in-JS

Libraries like styled-components or Emotion generate unique class names **at runtime** and inject component-scoped `<style>` tags directly into `<head>`. Same idea as CSS Modules, just resolved at runtime instead of build time.

```tsx
const Button = styled.button`
  padding: 8px 16px;
`;
```

**Strengths:** styles live next to the component, can be dynamic based on props, the same collision-avoidance guarantee as CSS Modules (hashed class names).

**Weaknesses:** styles cost time at runtime, because they are computed and injected on every render. There is also a gotcha specific to micro-frontends, and it has several faces.

Suppose two independently built remotes each bundle their **own separate copy** of styled-components, instead of sharing one singleton through Module Federation's `shared` config. Three things can go wrong:

- The copies inject conflicting global resets.
- They run incompatible major versions of the library, with different SSR (server-side rendering) and hydration behavior.
- The order of the `<style>` tags they inject independently is undefined.

That last one bites hardest. A tag injected later can win on specificity, whatever source order the developer expected. The symptom is an intermittent, flaky visual bug tied to load order and timing, not a logic error in anyone's code.

The `shared` config is covered in [Module Federation: How It Actually Works Under the Hood](./03-module-federation-deep-dive.md).

## Solution 4 — naming convention discipline (BEM-style prefixing)

The pragmatic, zero-tooling default: prefix every class name with a namespace unique to each micro-frontend. BEM (block, element, modifier) is the naming scheme this borrows from.

```css
/* checkout-mfe */
.checkout__button--primary { padding: 8px 16px; }

/* catalog-mfe */
.catalog__button--primary { padding: 8px 16px; }
```

**Strengths:** works everywhere, requires no tooling, easy to reason about in devtools, works for legacy code and gradual migration.

**Weaknesses:** the whole thing rests on convention. Nothing technically enforces the prefix. A new team member who does not know the convention can write an unprefixed global selector that silently collides with someone else's.

That is exactly why it earns the label of pragmatic default. It is the lowest common denominator, and it works when you cannot move every team onto the same CSS tooling at once.

## A shared design system as a versioned package — and the version-skew problem

In real production the common building blocks — buttons, inputs, modals, typography — are not left to each team. Organizations extract them into a shared design-system package such as `@company/design-system`. That package is versioned and published like any npm package. It can also be shared as a singleton through Module Federation's `shared` config.

**The version-skew problem.** Suppose catalog-mfe is pinned to `@company/design-system@2.1.0` and checkout-mfe to `@company/design-system@3.0.0`. That major bump carries breaking visual changes: a new spacing scale, different `border-radius` tokens.

Now compose the two side by side on one page — a checkout modal opening over a catalog page, say. The user literally sees **two visually different** button styles on the same screen, both claiming to be the same design system.

This is the CSS-domain twin of the two-React-copies bug from [Module Federation: How It Actually Works Under the Hood](./03-module-federation-deep-dive.md). Here, though, no error is thrown at all. The page just looks inconsistent, which is arguably worse: the problem stays silent until an actual human looks at the screen.

**Mitigation:** the same organizational discipline that governs shared JS dependencies in [Module Federation: How It Actually Works Under the Hood](./03-module-federation-deep-dive.md). Treat the design system's major version as a singleton requirement across every consuming micro-frontend.

Enforcement is a CI (continuous integration) check that compares versions across repositories. Add a defined upgrade window and a rollout process, rather than letting each team ship a breaking upgrade on its own schedule.

## Summary table of approaches

| Approach | Isolation mechanism | Runtime cost | Third-party library compatibility | Enforcement |
|---|---|---|---|---|
| CSS Modules | Build-time name hash | None | Fine | Build convention only |
| Shadow DOM | Real DOM boundary | Small (shadow root parsing) | Poor — many libraries expect a global `document` | Enforced by the browser |
| CSS-in-JS | Runtime hash plus injected `<style>` | Some (style computation) | Fine, but tag order across remotes is undefined | Build and runtime convention |
| BEM prefixing | Naming convention | None | Fine | None — pure discipline |

## Common interview traps

- **"One of these approaches fully solves style isolation"** — none of them does. Mature organizations combine all of them. BEM prefixing is the baseline discipline, a shared design-system package covers common elements, and CSS Modules or CSS-in-JS handle each micro-frontend's own components.

- **"Shadow DOM is strictly superior to the other approaches because it's the only real isolation"** — the isolation is real, yes. You pay for it with event retargeting, and with libraries that expect global DOM access and no longer find it. That is a deliberate trade-off, not a free upgrade.

- **"CSS Modules protect against all style leakage"** — they hash class names from your own modules, and nothing more. A global tag selector from someone else's CSS still overrides your styles, and so does a high-specificity reset stylesheet.

- **"A shared design system automatically solves version skew just by being shared"** — not on its own. It needs the same version-governance discipline as shared JS dependencies in [Module Federation: How It Actually Works Under the Hood](./03-module-federation-deep-dive.md). Without a CI check comparing versions across repositories, major-version skew produces silent visual inconsistency instead of a thrown error.

- **"CSS custom properties (variables) are blocked by the Shadow DOM boundary just like ordinary styles"** — no. They cross that boundary by default, through inheritance. That is exactly what makes them a convenient way to pass shared design tokens into isolated content.
