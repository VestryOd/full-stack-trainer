# Cheat Sheet and Technology Comparison

Reference material for articles 01-07 — no new concept explanations, just compact tables and snippets for quick lookup. If something here isn't clear, it's covered in depth in the article named in that section's heading.

## Part 1: Cheat Sheet

### CSS: animation/transition properties — cheap vs. expensive (article 01)

| Property | Pipeline stages | Cost |
|---|---|---|
| `transform`, `opacity` | Composite | Cheap — compositor, GPU (graphics processing unit) |
| `filter` (compositor-only in some engines) | Composite / Paint | Conditionally cheap — depends on the engine and filter type |
| `background-color`, `box-shadow`, `border-color` | Style → Paint → Composite | Moderate — repaint without reflow |
| `width`, `height`, `top`, `left`, `margin`, `padding` | Style → Layout → Paint → Composite | Expensive — reflow, potentially cascading |

### `transition` — syntax (article 02)

```css
.el {
  transition-property: transform, opacity;
  transition-duration: 0.3s, 0.2s;
  transition-timing-function: ease-out, linear;
  transition-delay: 0s;
  /* lets discrete properties such as `display` take part in a transition */
  transition-behavior: allow-discrete;
}
```

### `@keyframes` / `animation-*` longhands (article 02)

| Property | Values | Common mistake |
|---|---|---|
| `animation-fill-mode` | `none` \| `forwards` \| `backwards` \| `both` | Forgetting `forwards` → the element "snaps" back after the animation |
| `animation-direction` | `normal` \| `reverse` \| `alternate` \| `alternate-reverse` | Forgetting `alternate` for a pulse without a "teleport" |
| `animation-iteration-count` | a number \| `infinite` | — |
| `animation-play-state` | `running` \| `paused` | The only way to pause a CSS animation without a JS class toggle |

### Cubic-bezier presets worth memorizing (article 02)

```txt
ease        = cubic-bezier(0.25, 0.1, 0.25, 1.0)
              — transition's default
ease-in     = cubic-bezier(0.42, 0.0, 1.0, 1.0)
              — for elements leaving
ease-out    = cubic-bezier(0.0, 0.0, 0.58, 1.0)
              — for elements entering
ease-in-out = cubic-bezier(0.42, 0.0, 0.58, 1.0)
              — transitions between stable states
Material fast-out-slow-in = cubic-bezier(0.05, 0.7, 0.1, 1)
Spring-like overshoot     = cubic-bezier(0.34, 1.56, 0.64, 1)
              — y > 1 produces "bounce"
```

```css
/* steps() — not easing, frame-by-frame sprite animation */
animation: walk 0.8s steps(8, jump-end) infinite;

/* linear() — piecewise-linear curve for a multi-bounce spring effect */
transition: transform 0.8s linear(0, 0.5 15%, 0.9 30%, 1.1 45%, 1 100%);
```

### `@property` — typed custom properties (article 02)

```css
@property --angle {
  syntax: '<angle>';
  inherits: false;
  initial-value: 0deg;
}
```

### WAAPI — `Animation` methods and properties (article 03)

WAAPI is the Web Animations API. It drives the same engine CSS animation runs on, from JS.

| Method/property | Purpose |
|---|---|
| `element.animate(keyframes, options)` | Starts the animation, returns an `Animation` |
| `.play()` / `.pause()` / `.reverse()` | Playback control |
| `.finish()` | Instantly jump to the end, keeping any fill effect |
| `.cancel()` | Stop and revert to the pre-animation state |
| `.playbackRate` | Playback speed (can be negative) |
| `.currentTime` | Manual position scrubbing |
| `.playState` | `idle` \| `running` \| `paused` \| `finished` |
| `.finished` | A promise, resolves on completion, rejects on `cancel()` |
| `composite: 'add'` | Layering independent animations on the same property |
| `element.getAnimations()` / `document.getAnimations()` | Orchestrating a set of animations |

```javascript
// Scroll-driven animation via WAAPI (article 03)
const timeline = new ViewTimeline({ subject: el, axis: 'block' });
el.animate({ opacity: [0, 1] }, { fill: 'both', timeline });
```

### The canonical rAF (`requestAnimationFrame`) loop with delta time (article 04)

```javascript
let previousTimestamp;
function tick(timestamp) {
  if (previousTimestamp === undefined) previousTimestamp = timestamp;
  const deltaMs = timestamp - previousTimestamp;
  previousTimestamp = timestamp;

  update(deltaMs / 1000); // pass seconds, express speed in units/sec

  requestAnimationFrame(tick);
}
requestAnimationFrame(tick);
```

### A minimal FLIP snippet (article 04)

FLIP stands for First, Last, Invert, Play: measure, mutate, compensate, then animate.

```javascript
function flip(el, mutateFn) {
  const first = el.getBoundingClientRect();
  mutateFn();
  const last = el.getBoundingClientRect();
  const dx = first.left - last.left;
  const dy = first.top - last.top;

  el.style.transition = 'none';
  el.style.transform = `translate(${dx}px, ${dy}px)`;
  el.getBoundingClientRect(); // force layout once
  el.style.transition = 'transform 0.3s ease';
  el.style.transform = '';
}
```

### GSAP — core API (article 05)

GSAP is the GreenSock Animation Platform, a JS animation library.

| Call | Purpose |
|---|---|
| `gsap.to(target, vars)` | From the current value to the given one |
| `gsap.from(target, vars)` | From the given value to the current one |
| `gsap.fromTo(target, fromVars, toVars)` | Both endpoints explicit |
| `gsap.timeline()` | Orchestration, chained `.to()`/`.from()` calls with position parameters (`'-=0.2'`, labels) |
| `stagger: { each, from, grid }` | Wave-based delay distribution |
| `ScrollTrigger: { trigger, pin, scrub, start, end }` | Scroll choreography with section pinning |

```javascript
gsap.timeline()
  .to('.a', { opacity: 1, duration: 0.4 })
  .to('.b', { opacity: 1, duration: 0.4 }, '-=0.2'); // 0.2s before the previous tween ends
```

### Motion (Framer Motion) — core props (article 05)

| Prop | Purpose |
|---|---|
| `initial` / `animate` | The starting and target state (declarative, as a function of state) |
| `exit` (inside `AnimatePresence`) | The unmount animation — without this, React removes the node instantly |
| `whileHover` / `whileTap` | Interaction states |
| `layout` | Automatic FLIP whenever geometry changes between renders |
| `variants` + `staggerChildren` | Named states, orchestrated through the component tree |
| `transition={{ type: 'spring', stiffness, damping }}` | Physical, interruptible animation (article 04) |

```tsx
<AnimatePresence>
  {isOpen && (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    />
  )}
</AnimatePresence>
```

### `prefers-reduced-motion` — mandatory boilerplate (article 07)

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

```javascript
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
window.matchMedia('(prefers-reduced-motion: reduce)')
  .addEventListener('change', (e) => applyMotionPreference(e.matches));
```

## Part 2: Technology Comparison

**How to use these tables in practice:** start from the top rows (CSS transitions, `@keyframes`, WAAPI) and move down. Go one level lower only once the specific task hits a real limitation of the level above. Don't pick a tool "because it's more powerful" if nothing in the task needs that power.

Three tables follow, with the same nine technologies in the same order. WebGL (Web Graphics Library) is the browser's low-level API for 2D and 3D drawing, and the Canvas & Graphics topic covers it in full. The DOM is the document object model — the tree of page elements that CSS and JS work with.

### What each technology is best at

| Technology | Best for | What it can do |
|---|---|---|
| **CSS transitions** | A simple transition between two states, on a trigger | Interpolating a single property change |
| **CSS `@keyframes`** | Self-starting, repeating animation | Arbitrary intermediate points, repetition, direction |
| **WAAPI** | Programmatic animation on the same engine as CSS | play/pause/reverse/scrub, promises, composite modes, scroll-driven timelines |
| **rAF + plain JS** | Full control: physics, springs, interruptibility | Anything expressible in code |
| **GSAP** | Complex timeline orchestration and scroll choreography | Precisely positioned timelines, stagger patterns, `ScrollTrigger` pin/scrub |
| **Motion (Framer Motion)** | React integration: layout animations, exit animations, declarative orchestration | `layout` (auto-FLIP), `AnimatePresence`, variants, spring physics by default |
| **Lottie** | Playing back complex vector animation from After Effects | Exact 1:1 playback of an animator's design, programmatic segment control |
| **Scroll-driven animations (native)** | Simple scroll-linked progress with zero JS in the scroll path | `animation-timeline: scroll()`/`view()`, tying progress to scroll/visibility |
| **Canvas/WebGL** | Thousands of independently animated objects, custom rendering | Full control of rasterization, arbitrary graphics outside the DOM |

### Where you actually see it, and what it costs

| Technology | Typical real-world use | Performance profile |
|---|---|---|
| **CSS transitions** | Hover/focus states, opening/closing a panel | Compositor (for transform/opacity) |
| **CSS `@keyframes`** | Spinners, pulse indicators, frame-by-frame sprites (`steps()`) | Compositor (for transform/opacity) |
| **WAAPI** | Data-driven dynamic values, exit animations via `finished`, scrubbing | Compositor (for transform/opacity/filter) |
| **rAF + plain JS** | Drag inertia, custom springs, cursor followers, canvas animation | Main thread — always main-thread work |
| **GSAP** | Brand landing pages, "storytelling" sites, elaborate onboarding sequences | Mostly compositor-friendly properties, but the library itself is main-thread JS |
| **Motion (Framer Motion)** | Interface animation in React apps, reordering lists, modals with exit transitions | Compositor where possible, plus JS orchestration |
| **Lottie** | Onboarding illustrations, branded loaders, character animation | Depends on the renderer (`svg`/`canvas`/`html`), can be heavy for complex scenes |
| **Scroll-driven animations (native)** | Reading progress bars, reveal-on-scroll cards, simple parallax | Compositor, entirely off the main thread |
| **Canvas/WebGL** | Particles, games, complex data visualizations, generative graphics | A separate render context, can move to a Worker via `OffscreenCanvas` |

### What each one can't do

| Technology | Limitations |
|---|---|
| **CSS transitions** | No arbitrary intermediate points, no programmatic progress control |
| **CSS `@keyframes`** | No dynamic values from JS without regenerating CSS |
| **WAAPI** | More verbose syntax than CSS for simple cases |
| **rAF + plain JS** | Requires manual delta time, prone to jank under heavy JS |
| **GSAP** | Extra bundle weight, overhead for simple tasks |
| **Motion (Framer Motion)** | Only makes sense in a React context; the full package is heavier than the "mini" core |
| **Lottie** | Requires a bodymovin export pipeline; any change means editing in After Effects and re-exporting |
| **Scroll-driven animations (native)** | Can't pin an element — complex choreography still needs GSAP |
| **Canvas/WebGL** | No DOM accessibility out of the box, no CSS cascade, more low-level code |
