# Web Animations API

## What WAAPI actually is — and why it isn't "an alternative to CSS"

A common misconception treats the Web Animations API (WAAPI) as a third, separate way to animate elements, alongside CSS transitions and `requestAnimationFrame`. In reality, WAAPI is **the exact same engine** that runs `transition` and `@keyframes` (see [CSS Transitions and Keyframes]) — just with a programmatic JS interface on top of it. When you call `element.animate(...)`, the browser creates precisely the same internal `KeyframeEffect` it would from a `@keyframes` rule in CSS, with the same properties: interpolation based on value type, the ability to run on the compositor thread for `transform`/`opacity` (see [Rendering Pipeline and Frame Budget]), the same timing model.

The difference isn't "CSS is fast, JS is slow" — it's about **where the values come from and who controls them**. CSS works well when keyframe values are known ahead of time, while you're writing styles. WAAPI is what you need when:

- the target value is computed at runtime (dragging, physics, server-driven data)
- the animation needs programmatic control: pause, reverse, slow down, await completion via a promise
- you need to combine several independent animations on the same property without rewriting CSS classes

That's why building an animation by toggling CSS classes "for every dynamic value" is an anti-pattern that WAAPI solves directly, with no loss of the CSS engine's performance characteristics.

## `element.animate()`: syntax and keyframe formats

```javascript
const animation = element.animate(keyframes, options);
```

Keyframes can be given in two equivalent formats:

```javascript
// Format 1: an array of keyframe objects (explicit offset positions)
element.animate(
  [
    { transform: 'translateY(0)',   opacity: 1, offset: 0 },
    { transform: 'translateY(-8px)', opacity: 0.6, offset: 0.5 },
    { transform: 'translateY(0)',   opacity: 1, offset: 1 },
  ],
  { duration: 600, easing: 'ease-in-out' },
);

// Format 2: an object of per-property value arrays — the browser
// evenly distributes offsets between the values for you
element.animate(
  {
    transform: ['translateY(0)', 'translateY(-8px)', 'translateY(0)'],
    opacity: [1, 0.6, 1],
  },
  { duration: 600, easing: 'ease-in-out' },
);
```

The second format is more convenient for dynamically generated keyframes — for example, when a list of intermediate values is assembled from data in a loop — because you don't have to compute `offset` for each point by hand.

`options` mirrors the CSS `animation-*` properties, just as a camelCase object:

```javascript
element.animate(keyframes, {
  duration: 300,        // ↔ animation-duration
  easing: 'ease-out',   // ↔ animation-timing-function
  delay: 100,           // ↔ animation-delay
  endDelay: 0,           // wait after the end before the animation counts as finished
  iterations: 3,          // ↔ animation-iteration-count (Infinity for infinite)
  direction: 'alternate', // ↔ animation-direction
  fill: 'forwards',       // ↔ animation-fill-mode
  iterationStart: 0,      // which point in the cycle [0..iterations) to start from
  composite: 'replace',   // how this combines with the underlying value — see below
});
```

## The `Animation` object's lifecycle: not "fire and forget"

`element.animate()` returns an `Animation` object — a programmatic remote control for the running animation, not a one-shot call:

```javascript
const anim = element.animate(
  { transform: ['scale(1)', 'scale(1.2)'] },
  { duration: 400, easing: 'ease-out', fill: 'forwards' },
);

anim.pause();                 // pause at the current position
anim.play();                  // resume
anim.reverse();               // play backward from the current position
anim.finish();                // instantly jump to the end state
anim.cancel();                // stop and REVERT to the pre-animation state
                               // (unlike finish — cancel drops any fill effect)

anim.playbackRate = 2;        // speed up 2x on the fly, no restart
anim.playbackRate = -1;       // play backward at the same speed

console.log(anim.currentTime);  // current position on the timeline (ms)
anim.currentTime = 200;         // "seek" manually — useful for scrubbing
                                 // (e.g. syncing to a user drag gesture
                                 // without recreating the animation)

console.log(anim.playState);    // 'idle' | 'running' | 'paused' | 'finished'
```

A practical example: an animation synced to a drag-scrub slider — something that's simply impossible with a CSS `transition`, since it has no way to programmatically pin progress to an arbitrary point:

```javascript
const timeline = element.animate(
  { transform: ['translateX(0)', 'translateX(300px)'] },
  { duration: 1000, fill: 'both' },
);
timeline.pause(); // pause immediately — we're driving it manually

slider.addEventListener('input', (e) => {
  const progress = Number(e.target.value) / 100; // 0..1
  timeline.currentTime = progress * 1000;         // animation progress = slider position
});
```

## `animation.finished`: promises instead of `setTimeout` guesswork

Before WAAPI, the only way to know an animation had actually finished was either listening for `transitionend`/`animationend` (with well-known pitfalls — it may not fire on `display: none`, may fire multiple times when several properties transition, may not fire at all if the element is removed from the DOM too early) or a `setTimeout` set to the presumed duration — fragile, since it ignores changes to `playbackRate` or pauses.

`Animation.finished` is a promise that resolves when the animation ends naturally, and **rejects** if it was stopped via `cancel()`:

```javascript
async function animateOutAndRemove(element) {
  const anim = element.animate(
    { opacity: [1, 0], transform: ['scale(1)', 'scale(0.9)'] },
    { duration: 250, easing: 'ease-in', fill: 'forwards' },
  );

  try {
    await anim.finished;       // wait for actual completion, no time guessing
    element.remove();          // remove the DOM node ONLY once the animation truly finished playing
  } catch {
    // the animation was cancelled (e.g. the element got reused) — do nothing
  }
}
```

This solves the classic exit-animation problem in component frameworks (see also `AnimatePresence` in article 05): React unmounts a DOM node synchronously the moment `setState` runs, and any CSS animation on it simply gets cut off along with the node. `animation.finished` gives you a reliable point at which to defer the actual removal until the animation has really finished.

## Composite modes: `replace`, `add`, `accumulate`

The composite mode determines how the animation's value **combines** with the existing (underlying) value of the property — either from a previous animation or from ordinary CSS.

```txt
replace     (default) — the animation's value FULLY replaces
              the underlying value. Behaves like an ordinary
              CSS transition/animation.
add         — the animation's value is ADDED to the underlying
              value (for transform — matrices are multiplied
              together, not swapped out)
accumulate  — similar to add, but specific to repeated iterations
              of a single animation: each next iteration keeps
              accumulating from where the previous one left off
              (inherited from SMIL/SVG animation)
```

`composite: 'add'` solves a concrete practical problem: layering **independent** animations on the same property without manually recomputing the combined transform matrix:

```javascript
// A base "alive" animation — a subtle idle bob that runs continuously
element.animate(
  { transform: ['translateY(0px)', 'translateY(-4px)', 'translateY(0px)'] },
  { duration: 2000, iterations: Infinity, easing: 'ease-in-out' },
);

// On click — ADD a short "bounce" on top of the current bob,
// without interrupting or manually recomputing the base animation
button.addEventListener('click', () => {
  element.animate(
    { transform: ['scale(1)', 'scale(1.15)', 'scale(1)'] },
    { duration: 300, composite: 'add' },
  );
});
// The resulting transform at any point in time is a COMBINATION
// of both animations (the browser multiplies the matrices itself),
// not one overriding the other
```

Without `composite: 'add'`, the second animation with `composite: 'replace'` (the default) would simply override the first one for the duration of its playback, and once it finished, the element would "snap" back to the first animation's state — a visibly jarring jump that many people try to fix by hand-computing a combined transform in JS. `add` removes that work from the developer entirely.

## `getAnimations()`: orchestrating a set of animations

`Element.prototype.getAnimations()` and `Document.prototype.getAnimations()` return the list of all active (and recently finished, until garbage-collected) `Animation` objects on an element or across the whole document:

```javascript
// Cancel ALL of an element's current animations before starting a new one —
// a common pattern for avoiding "animation buildup" when a user
// interacts rapidly and repeatedly (e.g. clicking fast)
function animateExclusive(element, keyframes, options) {
  element.getAnimations().forEach((anim) => anim.cancel());
  return element.animate(keyframes, options);
}
```

```javascript
// Wait for ALL animations on the page to finish before, say,
// taking a screenshot or moving on to the next step in a test
async function waitForAllAnimations() {
  const animations = document.getAnimations();
  await Promise.all(animations.map((a) => a.finished));
}
```

This is something a purely CSS-based model simply didn't offer: previously the only way to know "something on the page is currently animating" was to manually track state in JS, or attach `transitionend` handlers to every element up front.

## Why WAAPI beats manually toggling CSS classes for dynamic values

```javascript
// ❌ Toggling classes for a dynamic value — requires generating
// CSS on the fly or defining a class for every possible case,
// and breaks on re-trigger without a forced-reflow hack
function highlightProgress(bar, percent) {
  bar.className = `progress progress--${percent}`; // a class like progress--73 doesn't exist
  // The alternative — inline style — then needs a forced-reflow trick
  // to RESTART the transition on the same target value:
  bar.style.transition = 'none';
  bar.style.width = '0%';
  void bar.offsetWidth; // forced synchronous layout — see article 01
  bar.style.transition = 'width 0.3s ease';
  bar.style.width = `${percent}%`;
}
```

```javascript
// ✅ WAAPI — a value straight from a variable, no CSS generation
// and no reflow hacks; each call produces a clean, independent Animation
function highlightProgress(bar, percent) {
  bar.animate(
    { width: [`${bar.getBoundingClientRect().width}px`, `${percent}%`] },
    { duration: 300, easing: 'ease', fill: 'forwards' },
  );
}
```

The second example isn't ideal performance-wise (`width` is a layout-triggering property, more expensive than `transform` — see article 01), but it illustrates the main point: WAAPI accepts an arbitrary JS value directly, with no intermediate "first turn it into CSS" step. For `transform`/`opacity` animations with runtime-computed values — dragging, sortable lists, cursor-physics-driven motion — this is the only clean way to avoid hand-rolling class or inline-style generation.

## Performance: the same engine as CSS — not an rAF loop

An important distinction that's often muddled in interviews: WAAPI is NOT the same thing as "writing a `requestAnimationFrame` loop in JS" (article 04). Both are JS-driven, but they have fundamentally different execution models:

```txt
Manual rAF loop:
  Every frame → JS callback runs on the MAIN thread →
  computes a new value → writes a style →
  the browser recomputes Style/(Layout)/Paint/Composite
  If the main thread is busy, the callback runs late and a frame can drop

WAAPI (element.animate):
  The browser gets the FULL animation description ONCE →
  subsequent playback for transform/opacity/filter
  can run ON THE COMPOSITOR, with no per-frame trip back
  to the main thread — same as with CSS transitions
```

That means a WAAPI animation on `transform` keeps running smoothly even while the main thread is busy with heavy JS — the same property CSS transitions/keyframes have, because it's literally the same engine. A hand-rolled rAF loop can't have that property by definition — it IS main-thread work.

## Scroll-driven animations: `ScrollTimeline` and `ViewTimeline`

Before this feature existed, "animation progress tied to scroll" always meant a JS `scroll` event handler manually computing progress and updating a style on every scroll event (which can fire dozens of times per second), with the constant risk of layout thrashing and always running on the main thread. Scroll-driven animations move that relationship into a declarative model that's independent of the main thread.

There's an important distinction worth stating clearly in an interview:

```txt
Scroll-LINKED (what ScrollTimeline/ViewTimeline actually do):
  Animation progress is DIRECTLY equal to scroll position.
  There's no independent clock — the animation's currentTime
  is a function of scrollTop/viewport intersection. Scroll
  back up, and the animation runs backward too, synchronously,
  with no time-based interpolation involved.

Scroll-TRIGGERED (what GSAP ScrollTrigger typically does in
  "play once" mode, or an IntersectionObserver + CSS class):
  Scroll only TRIGGERS an ordinary time-based animation
  (with its own duration and easing), which then runs
  independently of further scrolling, on its own clock.
```

The CSS form — `animation-timeline`:

```css
/* Scroll-linked: a reading-progress bar at the top of the page,
   tied directly to scrolling the whole document */
@keyframes grow-progress {
  from { transform: scaleX(0); }
  to   { transform: scaleX(1); }
}
.reading-progress-bar {
  animation: grow-progress linear;
  animation-timeline: scroll(root); /* source = scrolling the root element */
  transform-origin: left;
}
```

```css
/* Scroll-linked via ViewTimeline: an element reveals as it enters
   the viewport and un-reveals as it exits — with NO
   IntersectionObserver involved */
@keyframes reveal {
  from { opacity: 0; transform: translateY(24px); }
  to   { opacity: 1; transform: translateY(0); }
}
.reveal-card {
  animation: reveal linear both;
  animation-timeline: view();       /* timeline = the element's viewport visibility */
  animation-range: entry 0% cover 40%; /* from entering to 40% covered */
}
```

The WAAPI form — the same timelines as objects, passed to `animate()`:

```javascript
const timeline = new ViewTimeline({
  subject: document.querySelector('.reveal-card'),
  axis: 'block',
});

document.querySelector('.reveal-card').animate(
  { opacity: [0, 1], transform: ['translateY(24px)', 'translateY(0)'] },
  { fill: 'both', timeline },
);
```

The practical payoff for production work: parallax effects, reading-progress bars, reveal-on-scroll cards — all things that used to require a `scroll` listener wrapped in throttling/rAF (article 06 covers why a naive scroll handler is a jank source) — now run declaratively on the compositor, with zero JS in the scroll path at all.

## View Transitions API: an "old vs. new" snapshot without hand-rolled cross-fading

A classic problem: when a state changes — a modal opens, a tab switches, a list's layout changes — you often want a nice transition where "the old state smoothly turns into the new one." But the old and new DOM states never physically coexist, so this used to be done by hand: clone the old node, overlay it on top of the new one, cross-fade via `opacity`, and manually clean up the clone afterward.

`document.startViewTransition()` handles this natively:

```javascript
function switchToGridLayout() {
  if (!document.startViewTransition) {
    applyGridLayout(); // fallback for browsers without support — just apply, no animation
    return;
  }

  document.startViewTransition(() => {
    applyGridLayout(); // any synchronous DOM/class mutation inside the callback
  });
}
```

The mechanics, step by step:

```txt
1. The browser takes a "screenshot" of the current DOM state
2. The provided callback runs — this is where the actual
   DOM/class/state change happens (it can be synchronous,
   or return a promise for async updates)
3. The browser takes a screenshot of the NEW DOM state
4. Between the two screenshots, the browser plays a smooth
   cross-fade by default — controllable via the
   ::view-transition-old(root) and ::view-transition-new(root)
   pseudo-elements
```

Customizing the transition is just CSS on those pseudo-elements:

```css
::view-transition-old(root) {
  animation: fade-out 0.25s ease-out;
}
::view-transition-new(root) {
  animation: fade-in 0.25s ease-in;
}
```

For individual elements that need a "shared element" effect — a card in a list smoothly morphing into a hero image on a detail page, the "magic" transition that used to require the FLIP technique by hand (see article 04) — you just assign a named `view-transition-name`:

```css
.product-card__image {
  view-transition-name: product-hero; /* the browser animates the
    transition between this named element's old and new geometry itself */
}
```

An important scope note for this topic: what's covered here is the same-document form (transitions within an SPA/single-document state change). Cross-document View Transitions (transitions between full navigations — between separate HTML pages, with a real page load) extend the same idea to MPA navigation, with their own configuration nuances via `@view-transition` in CSS; for this topic, it's worth knowing it exists, but the details fall outside single-document DOM/CSS/JS animation.

## Connection to other articles

```txt
[CSS Transitions and Keyframes]         — the same keyframe/timing engine
                                           that WAAPI uses under the hood
[rAF and JS-Driven Animation]           — the FLIP technique, which View
                                           Transitions largely replace for
                                           shared-element transitions
[Performance Debugging and Jank
 Hunting]                                — why a naive scroll listener was
                                           a problem that scroll-driven
                                           animations solve
[Animation Libraries and Ecosystem]     — Motion (Framer Motion) uses
                                           WAAPI under the hood wherever
                                           it can
```

## Common interview traps

- **"WAAPI is like rAF, just different syntax"** — fundamentally wrong. WAAPI uses the same engine as CSS transitions/keyframes and can run on the compositor; an rAF loop is always main-thread JS, re-run every single frame.

- **Confusing `cancel()` and `finish()`** — `finish()` instantly plays the animation to its end and keeps any fill effect (if set); `cancel()` stops the animation and FULLY reverts the element to its pre-animation state, ignoring `fill`.

- **Not knowing `animation.finished` rejects on `cancel()`** — code doing `await anim.finished` without a `try/catch` can produce an unhandled promise rejection if the animation gets cancelled (e.g. a user double-clicking quickly).

- **Not understanding composite modes** — trying to manually compute a "combined" transform in JS for two simultaneous animations on the same element, unaware that `composite: 'add'` solves this natively.

- **Confusing scroll-linked and scroll-triggered** — being unable to explain the difference between ScrollTimeline/ViewTimeline (progress is a function of scroll, no independent clock) and, say, GSAP ScrollTrigger in play-once mode (scroll only kicks off an independent time-based animation).

- **Not knowing about the View Transitions API** — proposing to manually clone DOM nodes and cross-fade via `opacity` in a situation where `document.startViewTransition()` solves the exact same problem declaratively with far less code.

- **Not feature-checking `startViewTransition` before calling it** — calling the API without a fallback, breaking the app in unsupported browsers instead of simply applying the change without animation.
