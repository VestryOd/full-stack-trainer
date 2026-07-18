# Animation Libraries and the Ecosystem

## Why reach for a library when you already have CSS, WAAPI, and rAF

Articles 01-04 give you a complete set of native primitives, and for animating a single element on its own, that's enough. Libraries don't solve "how do I animate one div" — they solve three problems that are easy to hand-roll incorrectly with native tools alone:

```txt
1. ORCHESTRATION across many independent elements: a timeline with
   precise synchronization (this element starts 0.2s BEFORE the
   previous one ends), staggering across dozens of elements with a
   controllable distribution pattern
2. COMPLEX scroll choreography: pinning a section in place while the
   user scrolls, syncing animation progress to scroll velocity
   (scrub), multiple triggers on one page — things the native
   ScrollTimeline (article 03) physically can't do (it can't "stick"
   an element to the viewport during scroll)
3. Integration with a FRAMEWORK'S lifecycle: React unmounts DOM
   synchronously — an exit animation in plain React has no time to
   finish playing unless something solves that at the library level
```

The selection rule here is simple and should stay the default: **the native tool is always the first candidate**; a library earns its place when the specific task falls into one of the three buckets above — not because "it's what I'm used to" or "everyone has GSAP on their résumé."

## GSAP: the industry standard for scroll choreography

GSAP (GreenSock Animation Platform) is the longest-lived, most performance-predictable JS animation library, the de facto standard on agency/brand sites that need cinematic scroll choreography.

### Tween — the base unit

```javascript
import gsap from 'gsap';

gsap.to('.hero-title', {
  x: 100,
  opacity: 1,
  duration: 0.8,
  ease: 'power3.out', // GSAP's own library of easing curves
});

gsap.from('.card', { y: 40, opacity: 0, duration: 0.5 }); // "from" the current value to the given one
gsap.fromTo('.badge', { scale: 0 }, { scale: 1, duration: 0.4 }); // both endpoints explicit
```

### Timeline — orchestration with precise positioning

```javascript
const tl = gsap.timeline({ defaults: { duration: 0.5, ease: 'power2.out' } });

tl.to('.logo', { opacity: 1, y: 0 })
  .to('.nav-item', { opacity: 1, stagger: 0.08 }, '-=0.2') // start 0.2s BEFORE the previous tween ends
  .to('.hero-title', { opacity: 1 }, 'reveal')              // a named label at the current position
  .to('.hero-subtitle', { opacity: 1 }, 'reveal+=0.1');      // relative to the 'reveal' label
```

Position parameters (`'-=0.2'`, named labels, `'<'`/`'>'` for "together with the previous one"/"after the previous one") are what turns a pile of disconnected tweens into a single choreographed sequence, where you can restructure the whole thing's timing by changing one parameter instead of recomputing absolute delays by hand.

### Stagger — more than "uniform delay"

```javascript
gsap.to('.grid-item', {
  opacity: 1,
  y: 0,
  stagger: {
    each: 0.05,
    from: 'center',   // the wave radiates out from the center of the grid, not left to right
    grid: 'auto',      // GSAP infers the grid from the DOM layout itself
  },
});
```

GSAP's `stagger` isn't just "the i-th element starts i × delay later" — it's a full distribution system (from the center, from an edge, random, grid-aware based on distance) — something you could recreate by hand with `setTimeout` in a loop, but with an order of magnitude more code and much more fragility.

### ScrollTrigger: what the native ScrollTimeline can't do

```javascript
import { ScrollTrigger } from 'gsap/ScrollTrigger';
gsap.registerPlugin(ScrollTrigger);

gsap.to('.pinned-section .content', {
  xPercent: -100 * (sections.length - 1), // horizontal scrolling of cards
  ease: 'none',
  scrollTrigger: {
    trigger: '.pinned-section',
    pin: true,           // PINS the section in the viewport for the duration of the scroll — the native API has nothing like this
    scrub: 1,             // progress is TIED to scroll, smoothed over 1s
    end: () => `+=${sections.length * window.innerHeight}`,
    markers: process.env.NODE_ENV === 'development', // visible trigger markers while debugging
  },
});
```

The key difference from `animation-timeline: scroll()`/`view()` (article 03): the native scroll-driven timeline gives you scroll-linked progress for a single element, but it can't **pin** an element to the viewport, stretching a section's logical "scroll" across several screens' worth of real page height. Pin + scrub is exactly the mechanic behind most "storytelling sites" — the elaborate landing pages where a section stays put while a multi-step animation plays out — and as of this writing, that's still GSAP's territory, not native CSS's.

### Licensing

Historically, some GSAP plugins (including ScrollTrigger, SplitText, MorphSVG) required a paid Club GreenSock subscription for commercial use. After Webflow acquired GreenSock, the entire GSAP platform — including every previously paid plugin — became free, under an MIT-like license. Before using it on a commercial project, it's worth checking the current terms on the official site — licensing situations for libraries change, and this is exactly the kind of fact you should verify rather than rely on memory for.

## Motion (Framer Motion): the declarative layer for React

Motion (formerly known as Framer Motion) isn't a wrapper around GSAP — it's its own engine, built on WAAPI and spring physics (article 04), integrated directly into React's component model.

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

A single `layout` attribute makes Motion automatically run the FLIP sequence (First → Last → Invert → Play, article 04) around ANY geometry change an element undergoes between renders — a list reorder, a parent resizing, a CSS class switch that affects layout. The library measures `getBoundingClientRect()` before and after React commits, and animates the difference via `transform`, even when the actual CSS property that caused the shift is layout-triggering (say, `flex-direction` or `grid-template-columns`).

### `AnimatePresence`: solves exactly the problem React itself creates

React unmounts a DOM node **synchronously**, the instant a condition in JSX stops being true — a CSS/JS animation on that node has no physical time to finish, because the node is already gone from the tree:

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

The mechanics: `AnimatePresence` intercepts the moment React "wants" to remove a child, keeps it in the DOM for one more frame, plays the `exit` animation (using an `Animation.finished`-like mechanism from article 03 under the hood), and only actually removes the node from the DOM once that's done. This is the whole reason a reliable way to animate an element leaving even exists in the React ecosystem — without the library, you'd have to hand-roll two-phase state yourself (`isOpen` plus a delayed `isRendered`).

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

The parent propagates a named state (`"visible"`) down to every child with `variants`, and `staggerChildren` on the parent automatically distributes delays across them — the same thing GSAP's stagger does, just expressed through the React component tree instead of a DOM selector.

## Motion One / the "mini" engine: when every kilobyte counts

Motion as a project today combines two layers: the full React-integrated API described above, and a lightweight vanilla core (historically known as Motion One), built directly on top of WAAPI with none of the React-specific overhead:

```javascript
import { animate, stagger } from 'motion';

animate('.card', { opacity: [0, 1], y: [20, 0] }, { delay: stagger(0.05) });

animate(
  '.progress-bar',
  { transform: ['scaleX(0)', 'scaleX(1)'] },
  { duration: 0.6, easing: 'ease-out' },
);
```

The syntax closely mirrors WAAPI's `element.animate()` (article 03), with some convenience added on top (string selectors instead of manual `querySelectorAll` + a loop, a built-in `stagger()`). This is a deliberate choice for non-React projects (or React projects where the full-size Motion is overkill): a minimal bundle, maximum reliance on the browser's own engine, compositor execution wherever it's available.

## Lottie + bodymovin: when an animator works in After Effects

Lottie solves a problem that CSS/JS animation just isn't the right tool for at all: complex vector motion graphics designed by an animator in Adobe After Effects (character animation, detailed onboarding illustrations, branded loaders) — hand-rewriting that in CSS keyframes would take weeks, and the result would still drift from the designer's original.

The mechanics: the **bodymovin** plugin exports an After Effects timeline to JSON describing vector layers, keyframes, masks, shapes — not raster video, not a GIF, but full vector data. **lottie-web** (and ports for React Native, iOS, Android, Flutter) plays back that JSON natively in the browser:

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
    developer's approximation," a direct export of the original
  - Programmatic control (setSpeed, playSegments, direction) —
    something video/GIF simply doesn't offer

Pitfalls:
  - The JSON payload can be heavy for complex scenes (hundreds
    of KB into low single-digit MB) — needs lazy-loading and
    must NOT sit in the critical render path
  - The renderer matters: 'svg' scales better but gets expensive
    for complex scenes with many layers; 'canvas' performs better
    for complex graphics but is rasterized (loses some vector
    benefits when scaled)
  - ANY change to the animation requires reworking it in After
    Effects and re-exporting — frontend can't "just nudge a pixel"
  - Needs deliberate attention to prefers-reduced-motion (article
    07) — Lottie doesn't give you this for free out of the box;
    you have to explicitly check it and either skip autoplay or
    show a static frame
```

The practical rule: Lottie is a tool for a specific situation ("we have an animator who works in After Effects, and the result needs to ship 1:1") — not a universal replacement for CSS/WAAPI on ordinary UI transitions. Where an ordinary button can be animated via `transform`/`opacity` in a couple of lines of CSS, Lottie is overkill both in weight and integration complexity.

## `@formkit/auto-animate`: a cheap win with no animation design at all

There's a separate category of libraries that need zero configuration and give you "reasonably good-looking" animation for free:

```javascript
import autoAnimate from '@formkit/auto-animate';

const list = document.querySelector('.todo-list');
autoAnimate(list);
// From this point on, ANY addition/removal/reordering of children
// inside .todo-list animates automatically — no per-case
// configuration required at all
```

Under the hood is a FLIP-based heuristic (article 04) combined with a `MutationObserver` watching the container's children for changes. This isn't a replacement for GSAP/Motion when you need deliberate, branded animation — it's a tool for places that wouldn't get animation at all otherwise ("never got prioritized," "not our focus this sprint"), where a bit of smoothness is still clearly better than abrupt layout jumps. The library weighs about 2 KB and requires no API changes on top of existing list rendering.

## An honest decision framework

```txt
1. CAN this be done with CSS/WAAPI?
   → Yes: use CSS/WAAPI (articles 01-03). This covers 90% of
     real-world UI animation and costs nothing extra in bundle
     size or performance (compositor execution).

2. Do you need COMPLEX scroll choreography (pinning, scrub,
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
  auto-animate         ~2 KB
  Motion "mini" core    ~5-18 KB (depends on which features are used)
  Framer Motion (full)  ~30-50 KB (a good portion is tree-shakable)
  GSAP core             ~20-25 KB (+ plugins as needed, e.g. ScrollTrigger)
  lottie-web             ~50-100+ KB (plus the weight of the animation's own JSON file)
```

On a landing page with one hero animation, 40 KB doesn't matter. In a mobile PWA with a JS budget of a few hundred kilobytes total, it does — and that's exactly the case where "we default to GSAP on every project" stops being an engineering decision and becomes an unexamined habit.

## Connection to other articles

```txt
[Web Animations API]                — the engine Motion's "mini"
                                       layer is built directly on top of
[rAF and JS-Driven Animation]        — the FLIP technique and springs
                                       that Motion and auto-animate
                                       implement automatically under
                                       the hood
[Performance Debugging and Jank
 Hunting]                             — how to diagnose jank REGARDLESS
                                       of whether it's caused by a
                                       native tool or a library
[Motion Design Patterns and
 Accessibility]                       — the stagger/orchestration
                                       patterns from this article,
                                       framed as product conventions
```

## Common interview traps

- **"GSAP is always better than native CSS because it's a professional tool"** — being unable to explain WHAT exactly GSAP provides beyond native tools (timeline orchestration, ScrollTrigger's pin/scrub) — not that it's inherently "faster" or "smoother"; for a single transform animation, GSAP has no performance advantage over CSS/WAAPI.

- **Not knowing the difference between native `animation-timeline: scroll()`/`view()` and GSAP ScrollTrigger** — not understanding that the native scroll-driven timeline can't pin an element to the viewport to stretch scrolling across several screens, while ScrollTrigger can — that's exactly why complex scroll choreography still requires a library.

- **Not understanding WHY `AnimatePresence` exists** — being unable to explain that React unmounts DOM synchronously, and without a mechanism that delays removal, an exit animation has no physical time to finish playing.

- **Treating Lottie as a replacement for SVG/CSS animation "for everything"** — not recognizing that Lottie earns its place specifically for complex, designer-driven, frame-by-frame motion graphics from After Effects, and that for ordinary button/card UI transitions it's a heavier, more roundabout path.

- **Not weighing bundle size as a selection criterion** — proposing GSAP or the full Framer Motion for one simple fade-in on a landing page without accounting for the weight that adds to the critical loading path.

- **Not knowing GSAP's license changed** — relying on outdated "ScrollTrigger is paid" information without checking current terms — a good signal that a candidate tracks the ecosystem rather than reciting a years-old memorized fact.
