# Animation Libraries and the Ecosystem

## Why reach for a library when you already have CSS, WAAPI, and rAF

Articles 01-04 give you a complete set of native primitives: CSS, WAAPI (Web Animations API) and `requestAnimationFrame`, usually shortened to rAF. For animating a single element on its own, that is enough. Libraries don't solve "how do I animate one div". They solve three problems that are easy to get wrong when you build them by hand:

```txt
1. Orchestration across many independent elements: a timeline
   with precise synchronization (this element starts 0.2s
   before the previous one ends), staggering across dozens of
   elements with a controllable distribution pattern
2. Complex scroll choreography: pinning a section in place
   while the user scrolls, syncing animation progress to
   scroll velocity (scrub), multiple triggers on one page.
   The native ScrollTimeline (article 03) physically cannot
   do this: it cannot "stick" an element to the viewport
   during scroll
3. Integration with a framework lifecycle: React unmounts
   the DOM synchronously, so an exit animation in plain React
   has no time to finish playing unless something solves that
   at the library level
```

The selection rule here is simple, and it should stay the default. **The native tool is always the first candidate.** A library is justified when the task falls into one of the three groups above. Not because "it's what I'm used to", and not because "everyone has GSAP on their résumé."

## GSAP: the industry standard for scroll choreography

GSAP (GreenSock Animation Platform) is the longest-lived JS animation library, and the most predictable one in terms of performance. It is the de facto standard on agency and brand sites that need cinematic scroll choreography.

### Tween — the base unit

```javascript
import gsap from 'gsap';

gsap.to('.hero-title', {
  x: 100,
  opacity: 1,
  duration: 0.8,
  ease: 'power3.out', // GSAP's own library of easing curves
});

// "from" the current value to the given one
gsap.from('.card', { y: 40, opacity: 0, duration: 0.5 });

// both endpoints explicit
gsap.fromTo('.badge', { scale: 0 }, { scale: 1, duration: 0.4 });
```

### Timeline — orchestration with precise positioning

```javascript
const tl = gsap.timeline({ defaults: { duration: 0.5, ease: 'power2.out' } });

tl.to('.logo', { opacity: 1, y: 0 })
  // start 0.2s before the previous tween ends
  .to('.nav-item', { opacity: 1, stagger: 0.08 }, '-=0.2')
  // 'reveal' is a named label at the current position
  .to('.hero-title', { opacity: 1 }, 'reveal')
  // positioned relative to the 'reveal' label
  .to('.hero-subtitle', { opacity: 1 }, 'reveal+=0.1');
```

Position parameters turn a pile of disconnected tweens into a single choreographed sequence. There are three of them: `'-=0.2'`, named labels, and `'<'`/`'>'`. The last pair means "together with the previous one" and "after the previous one". With them you restructure the timing of the whole sequence by changing one parameter, instead of recomputing absolute delays by hand.

### Stagger — more than "uniform delay"

```javascript
gsap.to('.grid-item', {
  opacity: 1,
  y: 0,
  stagger: {
    each: 0.05,
    // the wave radiates out from the center of the grid,
    // not left to right
    from: 'center',
    // GSAP infers the grid from the DOM layout itself
    grid: 'auto',
  },
});
```

GSAP's `stagger` isn't just "the i-th element starts i × delay later". It is a full distribution system: from the center, from an edge, random, or grid-aware based on distance. You could recreate that by hand with `setTimeout` in a loop. But it would take an order of magnitude more code, and be much more fragile.

### ScrollTrigger: what the native ScrollTimeline can't do

```javascript
import { ScrollTrigger } from 'gsap/ScrollTrigger';
gsap.registerPlugin(ScrollTrigger);

gsap.to('.pinned-section .content', {
  xPercent: -100 * (sections.length - 1), // horizontal scrolling of cards
  ease: 'none',
  scrollTrigger: {
    trigger: '.pinned-section',
    // pins the section in the viewport for the duration of the
    // scroll — the native API has nothing like this
    pin: true,
    // progress is tied to scroll, smoothed over 1s
    scrub: 1,
    end: () => `+=${sections.length * window.innerHeight}`,
    // visible trigger markers while debugging
    markers: process.env.NODE_ENV === 'development',
  },
});
```

Here is the key difference from `animation-timeline: scroll()`/`view()` (article 03). The native scroll-driven timeline gives you scroll-linked progress for a single element. But it can't **pin** an element to the viewport, stretching a section's logical "scroll" across several screens' worth of real page height.

Pin plus scrub is exactly the mechanic behind most "storytelling sites". Those are the elaborate landing pages where a section stays put while a multi-step animation plays out. As of this writing, that is still GSAP's territory, not native CSS's.

### Licensing

| Period | ScrollTrigger, SplitText, MorphSVG |
|---|---|
| Before the Webflow acquisition | Paid: a Club GreenSock subscription for commercial use |
| After the acquisition | Free, along with the rest of the platform |

Historically, some GSAP plugins required a paid Club GreenSock subscription for commercial use. ScrollTrigger, SplitText and MorphSVG were among them. Then Webflow acquired GreenSock, and the entire GSAP platform became free, including every previously paid plugin. The new terms are close to MIT (a short, permissive open-source licence that allows commercial use).

Before using it on a commercial project, check the current terms on the official site. Licensing situations for libraries change, so this is exactly the kind of fact to verify rather than recall.

## Motion (Framer Motion): the declarative layer for React

Motion (formerly known as Framer Motion) isn't a wrapper around GSAP. It is its own engine, built on WAAPI and spring physics (article 04), and integrated directly into React's component model.

### Declarative props instead of imperative calls

```tsx
import { motion } from 'motion/react';

function Card() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ scale: 1.03 }}
      whileTap={{ scale: 0.97 }}
      transition={{ type: 'spring', stiffness: 300, damping: 24 }}
    >
      Content
    </motion.div>
  );
}
```

`initial`/`animate` aren't events — they're **states**: React re-renders the component, `animate` changes to a new object, and Motion diffs it and animates whatever values changed. This fits React's model naturally: the animation is described as a function of state, not as a sequence of imperative calls.

### The `layout` prop: FLIP from article 04, fully automatic

```tsx
<motion.div layout className="list-item">
  {item.label}
</motion.div>
```

A single `layout` attribute makes Motion run the FLIP sequence (First → Last → Invert → Play, article 04) automatically. It does so around **any** geometry change an element undergoes between renders: a list reorder, a parent resizing, a CSS class switch that affects layout.

The library measures `getBoundingClientRect()` before and after React commits, then animates the difference via `transform`. That holds even when the CSS property that caused the shift is layout-triggering, say `flex-direction` or `grid-template-columns`.

### `AnimatePresence`: solves exactly the problem React itself creates

React unmounts a DOM (document object model — the browser's tree of page elements) node **synchronously**. It happens the instant a condition in JSX (the HTML-like markup syntax inside React components) stops being true. A CSS or JS animation on that node has no physical time to finish, because the node is already gone from the tree:

```tsx
// ❌ Without AnimatePresence — when isOpen: false, the node is
// removed INSTANTLY, the exit animation never even gets to start
{isOpen && <div className="modal">...</div>}
```

```tsx
// ✅ AnimatePresence delays actually unmounting until the
// exit animation is done
import { AnimatePresence, motion } from 'motion/react';

<AnimatePresence>
  {isOpen && (
    <motion.div
      className="modal"
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
    >
      ...
    </motion.div>
  )}
</AnimatePresence>
```

The mechanics are straightforward. `AnimatePresence` intercepts the moment React "wants" to remove a child and keeps it in the DOM for one more frame. It plays the `exit` animation, using an `Animation.finished`-like mechanism from article 03 under the hood. Only once that is done does it actually remove the node.

This is the whole reason the React ecosystem has a reliable way to animate an element leaving at all. Without the library you would build two-phase state by hand: `isOpen` plus a delayed `isRendered`.

### Variants and orchestration without manual delays

```tsx
const container = {
  hidden: { opacity: 1 },
  visible: { opacity: 1, transition: { staggerChildren: 0.08 } },
};
const item = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0 },
};

<motion.ul variants={container} initial="hidden" animate="visible">
  {items.map((it) => (
    <motion.li key={it.id} variants={item}>{it.label}</motion.li>
  ))}
</motion.ul>
```

The parent propagates a named state (`"visible"`) down to every child with `variants`. Then `staggerChildren` on the parent distributes delays across them automatically. GSAP's stagger does the same thing, just expressed through a DOM selector instead of the React component tree.

## Motion One / the "mini" engine: when every kilobyte counts

Motion as a project today combines two layers. One is the full React-integrated API described above. The other is a lightweight vanilla core, historically known as Motion One, built directly on top of WAAPI with none of the React-specific overhead:

```javascript
import { animate, stagger } from 'motion';

animate('.card', { opacity: [0, 1], y: [20, 0] }, { delay: stagger(0.05) });

animate(
  '.progress-bar',
  { transform: ['scaleX(0)', 'scaleX(1)'] },
  { duration: 0.6, easing: 'ease-out' },
);
```

The syntax closely mirrors WAAPI's `element.animate()` (article 03), with some convenience added on top. You get string selectors instead of `querySelectorAll` plus a loop, and a built-in `stagger()`.

This is a deliberate choice for non-React projects, and for React projects where the full-size Motion is overkill. You get a minimal bundle, maximum reliance on the browser's own engine, and compositor execution wherever it is available.

## Lottie + bodymovin: when an animator works in After Effects

Lottie solves a problem that CSS and JS animation just aren't the right tools for. That problem is complex vector motion graphics designed by an animator in Adobe After Effects: character animation, detailed onboarding illustrations, branded loaders. Rewriting that by hand in CSS keyframes would take weeks, and the result would still drift from the designer's original.

The mechanics: the **bodymovin** plugin exports an After Effects timeline to JSON describing vector layers, keyframes, masks and shapes. That is full vector data, not raster video and not a GIF (graphics interchange format). The **lottie-web** library, plus ports for React Native, iOS, Android and Flutter, plays back that JSON natively in the browser:

```javascript
import lottie from 'lottie-web';

const animation = lottie.loadAnimation({
  container: document.querySelector('.onboarding-illustration'),
  renderer: 'svg', // 'svg' | 'canvas' | 'html' — the renderer choice affects performance
  loop: true,
  autoplay: true,
  path: '/animations/onboarding-hero.json',
});

animation.setSpeed(1.5);
animation.playSegments([30, 90], true); // play back just a specific frame range
```

### Performance profile and pitfalls

```txt
Upsides:
  - Vector graphics — scales without quality loss, the file is
    dramatically smaller than comparable video/GIF
  - Exact fidelity to the animator's design — not "a frontend
    developer's approximation", but a direct export of the
    original
  - Programmatic control (setSpeed, playSegments, direction) —
    something video/GIF simply doesn't offer

Pitfalls:
  - The JSON payload can be heavy for complex scenes (hundreds
    of KB into low single-digit MB) — needs lazy-loading and
    must not sit in the critical render path
  - The renderer matters: 'svg' scales better but gets expensive
    for complex scenes with many layers; 'canvas' performs better
    for complex graphics but is rasterized (loses some vector
    benefits when scaled)
  - Any change to the animation requires reworking it in After
    Effects and re-exporting — the frontend cannot "just adjust
    one pixel"
  - Needs deliberate attention to prefers-reduced-motion (article
    07) — Lottie doesn't give you this for free out of the box;
    you have to explicitly check it and either skip autoplay or
    show a static frame
```

The practical rule: Lottie is a tool for one specific situation. That situation is "we have an animator who works in After Effects, and the result needs to ship 1:1". It is not a universal replacement for CSS or WAAPI on ordinary interface transitions. An ordinary button can be animated via `transform`/`opacity` in a couple of lines of CSS. For that, Lottie is overkill in weight and in integration complexity.

## `@formkit/auto-animate`: a cheap win with no animation design at all

There's a separate category of libraries that need zero configuration and give you "reasonably good-looking" animation for free:

```javascript
import autoAnimate from '@formkit/auto-animate';

const list = document.querySelector('.todo-list');
autoAnimate(list);
// From this point on, any addition, removal or reordering of children
// inside .todo-list animates automatically — no per-case
// configuration required at all
```

Under the hood is a FLIP-based heuristic (article 04) combined with a `MutationObserver` watching the container's children for changes.

This isn't a replacement for GSAP or Motion when you need deliberate, branded animation. It is a tool for places that wouldn't get animation at all otherwise: "never got prioritized", "not our focus this sprint". There a bit of smoothness is still clearly better than abrupt layout jumps. The library weighs about 2 KB (kilobytes) and requires no API changes on top of existing list rendering.

## An honest decision framework

```txt
1. Can this be done with CSS or WAAPI?
   → Yes: use CSS/WAAPI (articles 01-03). This covers 90% of
     real-world interface animation and costs nothing extra in
     bundle size or performance (compositor execution).

2. Do you need complex scroll choreography (pinning, scrub,
   multiple sections, a "storytelling" site)?
   → GSAP + ScrollTrigger — the industry standard for exactly
     this class of problem, with no comparably mature alternative.

3. React app, and you need layout animations / exit animations /
   declarative orchestration tied to component state?
   → Motion (Framer Motion) — the only option that solves the
     AnimatePresence problem at the framework level rather than
     by hand.

4. Need lightweight programmatic animation with no React and no
   scroll choreography, and bundle size actually matters?
   → Motion's "mini" core (Motion One) — a thin wrapper over WAAPI.

5. A motion designer supplies animation from After Effects?
   → Lottie — the only practical way to ship it 1:1, without
     redrawing it by hand in CSS/JS.

6. Lists/toggles where animation wouldn't happen at all otherwise?
   → auto-animate — minimal cost of entry, zero configuration.
```

Bundle size and licensing aren't footnotes here — they're real selection criteria on a production project:

```txt
Rough sizes (min+gzip, order of magnitude, not exact figures —
check current numbers on bundlephobia before deciding):

  auto-animate          ~2 KB
  Motion "mini" core    ~5-18 KB
                        depends on which features are used
  Framer Motion (full)  ~30-50 KB
                        a good portion is tree-shakable
  GSAP core             ~20-25 KB
                        plus plugins as needed, e.g. ScrollTrigger
  lottie-web            ~50-100+ KB
                        plus the animation's own JSON file
```

On a landing page with one hero animation, 40 KB doesn't matter. In a mobile PWA (progressive web app) with a JS budget of a few hundred kilobytes total, it does. That is exactly the case where "we default to GSAP on every project" stops being an engineering decision and becomes an unexamined habit.

## Connection to other articles

- [Web Animations API](./03-web-animations-api.md) — the engine that Motion's "mini" layer is built directly on top of.
- [requestAnimationFrame and JS-Driven Animation](./04-raf-and-js-driven-animation.md) — the FLIP technique and the springs that Motion and auto-animate implement automatically under the hood.
- [Performance Debugging and Jank Hunting](./06-performance-debugging-and-jank-hunting.md) — how to diagnose jank, whether a native tool or a library caused it.
- [Motion Design Patterns and Accessibility](./07-motion-design-patterns-and-accessibility.md) — the stagger and orchestration patterns from this article, framed as product conventions.

## Common interview traps

- **"GSAP is always better than native CSS because it's a professional tool".** Being unable to explain **what** exactly GSAP provides beyond native tools: timeline orchestration, and ScrollTrigger's pin and scrub. It is not inherently "faster" or "smoother". For a single transform animation, GSAP has no performance advantage over CSS or WAAPI.

- **Not knowing the difference between native `animation-timeline: scroll()`/`view()` and GSAP ScrollTrigger.** The native scroll-driven timeline can't pin an element to the viewport to stretch scrolling across several screens. ScrollTrigger can. That is exactly why complex scroll choreography still requires a library.

- **Not understanding **why** `AnimatePresence` exists.** Being unable to explain that React unmounts the DOM synchronously. Without a mechanism that delays removal, an exit animation has no physical time to finish playing.

- **Treating Lottie as a replacement for SVG (scalable vector graphics) and CSS animation "for everything".** Lottie is the right choice specifically for complex, designer-driven, frame-by-frame motion graphics from After Effects. For ordinary button and card transitions it is a heavier, more roundabout path.

- **Not weighing bundle size as a selection criterion.** Proposing GSAP or the full Framer Motion for one simple fade-in on a landing page. That ignores the weight it adds to the critical loading path.

- **Not knowing GSAP's license changed.** Relying on outdated "ScrollTrigger is paid" information without checking current terms. Whether a candidate tracks the ecosystem, or recites a years-old memorized fact, shows up here.
