# Browser Animation — Interview Questions (Middle → Senior)

## Group 1: Rendering Pipeline and Fundamentals

**Why are `transform` and `opacity` considered "cheap" to animate, while `top`/`left`/`width` are "expensive"?**

Because they trigger different stages of the rendering pipeline. Any geometry change (`width`, `top`, `left`, `margin`) requires Layout — the browser has to recompute positions and sizes, potentially cascading to sibling and child elements — followed by Paint, to repaint the affected pixels. `transform` and `opacity` don't change document geometry and don't require repainting already-rendered content: they only change how an already-rasterized layer is positioned and blended during the Composite stage. Composite can run on a separate compositor thread, independent of the main thread, so `transform`/`opacity` animation keeps running smoothly even while the main thread is busy with heavy JS. The imprecise (but frequently heard) answer — "because it's on the GPU" — doesn't explain the mechanism: `box-shadow` can also be GPU-rendered and still requires Paint.

---

**What's the difference between the main thread and the compositor thread, and why does it matter for animation?**

The main thread is the only thread where JS, Style recalculation, Layout, Paint, and event handlers run; it's sequential, and while it's busy, it can't process either the next render frame or a user's click. The compositor thread is separate and lighter, and can animate already-rasterized layers on its own (move, scale, fade them) without going back to the main thread every frame. The practical consequence: an animation requiring Style/Layout/Paint gets blocked by heavy main-thread JS; a purely compositor-driven animation (`transform`/`opacity`) is almost immune, because it physically executes on a different thread.

---

**What is jank, physically, in terms of what the browser is doing?**

Jank is a missed frame. If the browser doesn't finish preparing a new frame by the time the display is ready to show it (within 16.7 ms at 60 Hz, or 8.3 ms at 120 Hz), the display re-shows the previous frame instead. Visually this reads as a stutter: instead of a steady sequence of small motion steps, the eye sees a single "jump" covering the distance of two steps in the time one used to take. The cause of a dropped frame is almost always that the main thread was busy longer than the frame budget allows (JS, Layout, Paint) and didn't finish preparing the frame in time.

---

**When does an element get promoted to its own composited layer, what does that cost, and why is "add `will-change` everywhere just in case" bad practice?**

The browser creates a separate layer for: 3D transforms (`translateZ(0)`, `translate3d`), `will-change: transform/opacity`, the presence of `<video>`/`<canvas>`/`<iframe>`, an animated `filter`, an active CSS animation/transition on `transform`/`opacity`. Each layer is a separate GPU texture, costing roughly `width × height × 4 bytes (RGBA)` in memory. Scattering `will-change` across many static elements "just in case" reserves that memory immediately, not at the moment of the actual animation — this is called layer explosion: dozens of extra layers cost memory and composite-stage time, which in aggregate WORSENS performance exactly where `will-change` was supposed to help, especially noticeable on mobile devices with memory shared between CPU and GPU. The correct pattern is adding `will-change` right before the animation starts and removing it right after it ends.

---

**What is layout thrashing, how do you diagnose it, and how do you fix it?**

By default, the browser batches style changes and defers Layout recomputation until the next frame. But some JS properties (`offsetHeight`, `offsetWidth`, `getBoundingClientRect()`, `scrollTop`) must return UP-TO-DATE geometry — if there are pending style changes before the read, the browser is forced to compute layout immediately and synchronously (a forced synchronous layout). The danger isn't one such read — it's interleaving writes and reads in a loop: every iteration forces a full reflow all over again.

```javascript
// ❌ Layout thrashing
items.forEach((item) => {
  const h = item.offsetHeight;              // read → forces layout
  item.style.height = `${h + 10}px`;         // write → invalidates layout
});

// ✅ Fix: split the read and write phases
const heights = items.map((item) => item.offsetHeight); // all reads first
items.forEach((item, i) => { item.style.height = `${heights[i] + 10}px`; }); // then all writes
```

Diagnosing this in real code — the DevTools Performance panel: these cases are explicitly flagged with a purple Layout block labeled "Forced reflow," with a stack trace down to the exact line of code, no need to read through the whole codebase.

## Group 2: CSS Transitions and Keyframes

**Why is `transition: all` considered a production bug source rather than a harmless shorthand?**

Because it's an open-ended contract: ANY future change to ANY CSS property on the element starts animating, including changes added by another developer months later with no idea a `transition` is even watching. The classic scenario: someone adds `position: sticky` to an element that already has `transition: all` for adaptive logic — and toggling the sticky state makes the element visibly "glide" to its new position over the transition duration, even though nobody intended to animate that. A second, less obvious argument: the browser has to track every animatable property on the element to know whether a transition needs to start, which adds a small but constant overhead that an explicit property list removes entirely.

---

**What's the difference between `transition` and `animation`/`@keyframes`? When do you reach for which?**

`transition` requires a trigger — a state/class/computed-value change — and describes a single move "from the current value to a new one." `animation` + `@keyframes` needs no trigger (it can start on its own, as soon as the element exists), allows an arbitrary number of intermediate points, and has built-in repetition/direction (`animation-iteration-count`, `animation-direction`). Choice: `transition` for reacting to a state change (hover, open/closed); `animation` for self-starting or cyclical effects (a spinner, a pulse, frame-by-frame sprite animation).

---

**What does `animation-fill-mode` do, and what bug shows up if you forget it?**

`animation-fill-mode` determines what styles apply to the element BEFORE the animation starts and AFTER it ends. By default (`none`), outside the animation's active time the element's normal CSS rules apply, NOT the keyframe values. The classic bug: an element animates from `opacity: 0` to `opacity: 1` via `@keyframes` with `animation-iteration-count: 1`, the animation plays correctly, but once it ends the element suddenly vanishes — because without `forwards`, the browser reverts it to its normal state, where `opacity` isn't set to the last keyframe's value. The fix: `animation-fill-mode: forwards` (or `both`, if you also need the first keyframe applied before `animation-delay`).

---

**How do you animate `height: auto` (the accordion problem)? Name at least two approaches.**

CSS has historically been unable to animate a transition to/from `auto`, because `auto` isn't a number — it's an instruction to "compute from content" — and `transition` doesn't know the target value ahead of time. Working approaches: (1) the CSS Grid trick — wrap the content in `display: grid` with `grid-template-rows: 0fr`, switch to `1fr` on open, with `overflow: hidden` on the inner container — a reliable, cross-browser option; (2) the modern `interpolate-size: allow-keywords` on `:root` combined with `calc-size()` — lets you animate `height: auto` directly, though browser support isn't yet universal at the time of writing, so it's worth checking current support and/or providing a fallback.

---

**What's the difference between `cubic-bezier()`, `steps()`, and `linear()` as timing functions?**

`cubic-bezier(x1, y1, x2, y2)` builds a smooth curve from two control points; the `y` coordinates can go outside [0, 1], producing overshoot/bounce, but the curve is limited to a single smooth shape — it can't describe multiple oscillations. `steps(n, jump-term)` is a fundamentally different mechanism: not continuous interpolation but `n` discrete value jumps, used for frame-by-frame sprite animation via `background-position`, not for "smoothness." `linear()` is a modern function defining a piecewise-linear curve through an explicit list of `(value, position%)` points, which lets you declaratively describe a multi-bounce spring-like effect in pure CSS — something previously achievable only via JS.

## Group 3: Web Animations API

**How does WAAPI relate to CSS transitions/animations under the hood?**

WAAPI isn't an alternative engine — it's a programmatic interface to the exact same engine that runs `transition` and `@keyframes`. `element.animate()` creates the same internal `KeyframeEffect`, with the same value-type-based interpolation and the same ability to run on the compositor for `transform`/`opacity`/`filter`. The difference isn't performance — it's where the values come from and who controls playback: CSS is good for keyframe values known ahead of time, WAAPI is what you reach for when a value is computed at runtime or the animation needs programmatic control (pause, reverse, a completion promise).

---

**Explain WAAPI's composite modes (`'replace'` vs `'add'`) and give a practical use case for `'add'`.**

`replace` (the default) fully replaces the property's underlying value with the animation's value. `add` sums the animation's value with the underlying value (for `transform`, matrices are multiplied together rather than swapped out). A practical use case: a base "alive" animation (a continuous, subtle bob) plus a brief bounce effect on click, both on `transform` — with `composite: 'add'`, the second animation layers on top of the first without interrupting or replacing it, and without needing to manually compute a combined transform matrix in JS. Without `add`, the second animation with the default `replace` would override the first for its duration, and once it finished, the element would visually "snap" back.

---

**Why is WAAPI usually better than toggling CSS classes for animation values that are computed dynamically?**

Toggling classes for an arbitrary, runtime-computed value either requires generating CSS on the fly (you can't define a class for every possible value) or using inline styles, which then need a forced-reflow hack (`void el.offsetWidth`) to RESTART the transition on the same target value — otherwise the browser won't register the value as having changed. WAAPI accepts a JS value directly in `element.animate()`, with no intermediate CSS-generation step and no reflow hacks, while still using the same compositor-friendly engine for `transform`/`opacity`.

---

**What's the difference between scroll-linked and scroll-triggered animation?**

Scroll-linked (what native `ScrollTimeline`/`ViewTimeline`, `animation-timeline: scroll()`/`view()` do) means the animation's progress is DIRECTLY equal to scroll position, with no independent clock — scroll back up, and the animation runs backward, synchronously. Scroll-triggered (what GSAP's ScrollTrigger often does in play-once mode, or an IntersectionObserver + CSS class) means scroll only TRIGGERS an ordinary time-based animation with its own duration and easing, which then runs independently of further scrolling.

## Group 4: rAF, FLIP, and JS-Driven Animation

**Why must a hand-rolled `requestAnimationFrame` loop account for delta time?**

Because moving a value by a fixed step per frame (`x += 2`) produces a speed that depends on the display's refresh rate: 120px/sec at 60 Hz, 240px/sec at 120 Hz, with identical code. The correct approach is computing the time elapsed since the previous frame (`timestamp - previousTimestamp`) and scaling the movement by it, expressing speed in units per second rather than units per frame — that way the final speed is the same regardless of refresh rate, just made up of a different number of smaller or larger steps.

---

**Walk through the FLIP technique step by step. Why does it turn an expensive layout animation into a cheap one?**

First — measure the element's current position (`getBoundingClientRect()`) BEFORE the DOM change. Last — apply the actual DOM change (a reorder, a layout shift) and measure the new position AFTER. Invert — compute the difference between First and Last, and immediately apply a compensating `transform`, with no transition — the element visually stays in its old spot, even though it's already physically in the new one. Play — enable a transition on `transform` and clear the compensation — the element smoothly "travels" from its old visual position to its true new one. The cheapness comes from the fact that the entire visible animation happens purely through `transform` (the Composite stage, article 01), not by animating real layout properties, which simply doesn't scale to large numbers of elements without jank.

---

**What's the practical difference between duration-based easing animation and spring animation? Why can a spring be interrupted mid-flight with no visible jump, while a duration-based tween can't easily do that?**

Duration-based animation is a function `t → progress`, where `t` is normalized time within a PRE-SET duration; it has no notion of "current velocity," only a position along a fixed curve. Spring animation models a physical mass-spring-damper system: its state is `(current value, current velocity)`, and it has no fixed duration at all — it stops on its own once the system physically settles. Changing the target mid-flight is trivial for a spring: the physics recomputes a new trajectory that preserves the current velocity, with no jump. For duration-based animation, the same change would require either an abrupt restart (a visible jump) or manually recomputing the remaining time and the current "velocity" along the tangent of the curve — which is non-trivial and usually isn't done.

---

**When is `requestIdleCallback` the wrong tool, and why?**

For animation itself. `requestIdleCallback` has no guarantees whatsoever about frequency or timing — the callback can be deferred indefinitely if the main thread stays busy, and it isn't synced to the display's refresh rate at all. It's a tool for background, non-urgent work (batching analytics, warming a cache, lazy initialization) — things that should happen "whenever there's a spare moment," not "exactly by the next frame."

## Group 5: Libraries and Ecosystem

**When would you reach for GSAP instead of native CSS/WAAPI? What does `ScrollTrigger` give you that native scroll-driven animations don't?**

GSAP earns its place when a task needs timeline orchestration across many independent elements with precise positioning (labels, relative offsets like `'-=0.2'`) or complex scroll choreography. The key concrete difference `ScrollTrigger` provides is the ability to PIN (`pin: true`) a section in the viewport for the duration of scroll, stretching a logical animation across several screens of real page height, plus `scrub` to tie progress to scroll velocity with smoothing. The native `animation-timeline: scroll()`/`view()` gives scroll-linked progress for a single element, but can't "stick" an element to the viewport — that's exactly why elaborate scroll-storytelling sites still need GSAP, not just native CSS.

---

**What problem does `AnimatePresence` in Framer Motion solve, and why does that problem exist in the first place?**

React unmounts a DOM node SYNCHRONOUSLY the moment a render condition stops being true (`{isOpen && <Modal />}` → `isOpen: false`) — any CSS/JS animation on that node has no physical time to finish, because the node is already gone from the tree. `AnimatePresence` intercepts the moment React "wants" to remove a child, keeps it in the DOM a little longer, plays the `exit` animation, and only then actually removes the node. Without this mechanism, you'd have to hand-roll two-phase state yourself (`isOpen` plus a delayed `isRendered`).

---

**When is Lottie the right call, and when is it overkill?**

The right call is when complex vector motion graphics were designed by an animator in After Effects (character animation, detailed onboarding illustrations) and the result needs to ship to the browser 1:1, without hand-rewriting it in CSS/JS, which would take weeks and still drift from the original. It's overkill for ordinary UI transitions (a button, a card, a modal) expressible in a couple of lines of CSS via `transform`/`opacity`: there, Lottie adds the weight of a JSON payload, renderer overhead (SVG/Canvas), and a hard dependency on the bodymovin export pipeline for any design change.

## Group 6: Performance Debugging

**Debugging scenario: a marketing page stutters while scrolling on a budget Android phone, but is smooth in your desktop Chrome. Walk through your diagnosis process.**

Sequence: (1) reproduce the problem in DevTools with CPU/network throttling enabled (emulating weaker hardware) instead of trying to eyeball it on a powerful desktop; (2) record a session in the Performance panel and look at the main-thread flame chart — look for Long Tasks (>50 ms) and a repeating Layout→Paint→Composite pattern on every animation frame (a signal that a layout property is being animated instead of `transform`/`opacity`); (3) check for "Forced reflow" — if present, click the warning to get a stack trace down to the exact line where reads and writes of geometry are interleaved; (4) open the Layers panel — check whether the number of composited layers is bloated (layer explosion from `will-change` on static elements, or multiple `filter`s), and check the memory estimate for full-screen layers, which create heavier load on mobile with shared CPU/GPU memory than on desktop; (5) enable paint flashing — check whether more of the screen is repainting during scroll than it should, due to missing layer isolation; (6) if the problem is in the scroll handler itself — check whether `{ passive: true }` is set and whether geometry is being read synchronously inside the handler. It's this sequence of specific tools — not "guessing from reading the code" — that separates systematic diagnosis from guesswork.

---

**How do you diagnose layout thrashing in DevTools?**

Record a session in the Performance panel while reproducing the interaction, then look for Layout blocks explicitly flagged "Forced reflow" (a purple block with a warning icon) — clicking the warning expands a stack trace pointing to the exact line of code responsible. In the flame chart, a tight repeating pattern of small Layout blocks packed close together, correlated with a loop in your code, is the visual signature of the read/write interleaving that causes layout thrashing (article 01) — as opposed to a single, larger Layout block, which is normal and expected for one legitimate style change.

---

**What is INP, and how can animation-heavy code hurt it?**

INP (Interaction to Next Paint) is a Core Web Vitals metric measuring the delay between a user's action (a click, a tap, a keypress) and the moment the browser physically shows the next updated frame in response. If an rAF callback or JS-driven animation holds the main thread longer than the frame budget right at the moment of a user interaction, the response frame — say, a button's visual "pressed" state — gets delayed, and that directly hurts INP. The practical consequence: poorly budgeted animation isn't just an "aesthetic" issue — it's a measurable factor in the same Web Vitals report as LCP/CLS, with real SEO consequences.

## Group 7: Accessibility and Product Decisions

**How do you correctly implement `prefers-reduced-motion` support? Does it mean disabling animation entirely?**

`prefers-reduced-motion` is an OS-level setting users turn on for a medical reason (vestibular disorders, where large-amplitude motion causes dizziness and nausea), not an aesthetic preference. A baseline implementation is a global CSS `@media (prefers-reduced-motion: reduce)` block zeroing out animation/transition durations — a workable safety net, but not the best solution everywhere: the right pattern is replacing MOVEMENT with an opacity cross-fade, preserving the fact that a transition happens between states (via CSS custom properties toggled inside the media query, e.g. `--enter-transform: translateY(20px)` → `none`), rather than removing the animation entirely. In JS, the same logic is implemented via `window.matchMedia('(prefers-reduced-motion: reduce)')`, with a mandatory subscription to `change` (the user can flip the setting mid-session), and at the library level — for instance, `MotionConfig reducedMotion="user"` in Framer Motion applies this automatically to every child component.

---

**Why shouldn't focus management be gated on an animation finishing?**

Because for a user working via keyboard or screen reader, waiting out a decorative animation before focus physically lands on the right element (say, `await animation.finished` before `element.focus()`) creates a real accessibility barrier, even though a 200-300 ms delay is invisible to a sighted user with no vestibular issues. The application's state changes the moment the user acts (opening a modal, moving between steps) — focus should move synchronously with that state change, while the animation plays in parallel, visually illustrating the transition without blocking accessibility for users who don't experience that animation the same way.
