# Browser Animation — Interview Questions (Middle → Senior)

## Group 1: Rendering Pipeline and Fundamentals

**Why are `transform` and `opacity` considered "cheap" to animate, while `top`/`left`/`width` are "expensive"?**

Because they trigger different stages of the rendering pipeline.

```txt
┌────────────────────────────────────────────────────┐
│ Style      which rules apply to which element      │
├────────────────────────────────────────────────────┤
│ Layout     positions and sizes                     │
│            entered by width, top, left, margin     │
├────────────────────────────────────────────────────┤
│ Paint      fill in the pixels                      │
│            entered by background-color, box-shadow │
├────────────────────────────────────────────────────┤
│ Composite  place and blend the ready layers        │
│            entered by transform, opacity           │
└────────────────────────────────────────────────────┘
```

Any geometry change — `width`, `top`, `left`, `margin` — requires Layout. The browser has to recompute positions and sizes, potentially cascading to sibling and child elements. Then comes Paint, to repaint the affected pixels.

`transform` and `opacity` don't change document geometry and don't require repainting already-rendered content. They only change how an already-rasterized layer is positioned and blended during the Composite stage. Composite can run on a separate compositor thread, independent of the main thread. So `transform`/`opacity` animation keeps running smoothly even while the main thread is busy with heavy JS.

The imprecise but frequently heard answer is "because it's on the GPU (graphics processing unit)". That doesn't explain the mechanism: `box-shadow` can also be GPU-rendered and still requires Paint.

---

**What's the difference between the main thread and the compositor thread, and why does it matter for animation?**

The main thread is the only thread where JS, Style recalculation, Layout, Paint and event handlers run.

```txt
┌─────────────────────────┐  ┌─────────────────────────┐
│ Main thread             │  │ Compositor thread       │
│                         │  │                         │
│ JS                      │  │ Moves, scales and fades │
│ Style recalculation     │  │ layers that are already │
│ Layout, Paint           │  │ rasterized              │
│ Event handlers          │  │                         │
│                         │  │ Keeps going even while  │
│ Sequential. While busy: │  │ the main thread is busy │
│ no next frame, no click │  │ with heavy JS           │
└─────────────────────────┘  └─────────────────────────┘
```

The main thread is sequential. While it's busy, it can't process either the next render frame or a user's click. The compositor thread is separate and lighter, and it can animate already-rasterized layers on its own: move, scale and fade them. It does that without going back to the main thread every frame.

The practical consequence: an animation requiring Style, Layout or Paint gets blocked by heavy main-thread JS. A purely compositor-driven animation (`transform`/`opacity`) is almost immune, because it physically executes on a different thread.

---

**What is jank, physically, in terms of what the browser is doing?**

Jank is a missed frame.

The browser has to finish preparing a new frame by the time the display is ready to show it. That budget is 16.7 ms at 60 Hz, or 8.3 ms at 120 Hz. Miss it, and the display re-shows the previous frame instead.

Visually this looks like a stutter. Instead of a steady sequence of small motion steps, the eye sees a single "jump". That jump covers the distance of two steps in the time one used to take.

The cause of a dropped frame is almost always the same. The main thread was busy longer than the frame budget allows (JS, Layout, Paint) and didn't finish preparing the frame in time.

---

**When does an element get its own composited layer, what does it cost, and why is "`will-change` everywhere, just in case" bad practice?**

The browser creates a separate layer in these cases:

- A 3D transform (`translateZ(0)`, `translate3d`).
- `will-change: transform/opacity`.
- The presence of `<video>`, `<canvas>` or `<iframe>`.
- An animated `filter`.
- An active CSS animation or transition on `transform`/`opacity`.

Each layer is a separate GPU texture. It costs roughly `width × height × 4 bytes (RGBA)` in memory.

Scattering `will-change` across many static elements "just in case" reserves that memory immediately, not at the moment of the actual animation. This is called layer explosion.

Dozens of extra layers cost memory and composite-stage time, and in aggregate that **worsens** performance exactly where `will-change` was supposed to help. It is especially noticeable on mobile devices, where memory is shared between the CPU (central processing unit) and the GPU.

The correct pattern is adding `will-change` right before the animation starts and removing it right after it ends.

---

**What is layout thrashing, how do you diagnose it, and how do you fix it?**

By default, the browser batches style changes and defers Layout recomputation until the next frame.

But some JS properties must return **up-to-date** geometry: `offsetHeight`, `offsetWidth`, `getBoundingClientRect()`, `scrollTop`. If there are pending style changes before the read, the browser is forced to compute layout immediately and synchronously — a forced synchronous layout.

The danger isn't one such read. It's interleaving writes and reads in a loop: every iteration forces a full reflow all over again.

```javascript
// ❌ Layout thrashing
items.forEach((item) => {
  const h = item.offsetHeight;              // read → forces layout
  item.style.height = `${h + 10}px`;         // write → invalidates layout
});

// ✅ Fix: split the read and write phases
const heights = items.map((item) => item.offsetHeight); // all reads first
// then all writes
items.forEach((item, i) => { item.style.height = `${heights[i] + 10}px`; });
```

Diagnosing this in real code means the DevTools Performance panel. These cases are explicitly flagged with a purple Layout block labeled "Forced reflow", with a stack trace down to the exact line of code. There's no need to read through the whole codebase.

## Group 2: CSS Transitions and Keyframes

**Why is `transition: all` considered a production bug source rather than a harmless shorthand?**

Because it's an open-ended contract: **any** future change to **any** CSS property on the element starts animating. That includes changes added by another developer months later, with no idea a `transition` is even watching.

The classic scenario: someone adds `position: sticky` to an element that already has `transition: all` for adaptive logic. Toggling the sticky state then makes the element visibly "glide" to its new position over the transition duration, even though nobody intended to animate that.

A second, less obvious argument. The browser has to track every animatable property on the element to know whether a transition needs to start. That adds a small but constant overhead, and an explicit property list removes it entirely.

---

**What's the difference between `transition` and `animation`/`@keyframes`? When do you reach for which?**

`transition` requires a trigger and describes a single move. `animation` with `@keyframes` needs no trigger and can describe many steps.

| | `transition` | `animation` + `@keyframes` |
|---|---|---|
| Needs a trigger | Yes: a state, class or computed-value change | No: it can start on its own, as soon as the element exists |
| Intermediate points | One move, from the current value to a new one | Any number of them |
| Repetition, direction | Not built in | `animation-iteration-count`, `animation-direction` |

Choice: `transition` for reacting to a state change, such as hover or open/closed. Use `animation` for self-starting or cyclical effects — a spinner, a pulse, frame-by-frame sprite animation.

---

**What does `animation-fill-mode` do, and what bug shows up if you forget it?**

`animation-fill-mode` determines what styles apply to the element **before** the animation starts and **after** it ends. By default (`none`), outside the animation's active time the element's normal CSS rules apply — **not** the keyframe values.

The classic bug: an element animates from `opacity: 0` to `opacity: 1` via `@keyframes` with `animation-iteration-count: 1`. The animation plays correctly, but once it ends the element suddenly vanishes. Without `forwards`, the browser reverts it to its normal state, where `opacity` isn't set to the last keyframe's value.

The fix: `animation-fill-mode: forwards`. Use `both` if you also need the first keyframe applied before `animation-delay`.

---

**How do you animate `height: auto` (the accordion problem)? Name at least two approaches.**

CSS has historically been unable to animate a transition to or from `auto`. The reason: `auto` isn't a number, it's an instruction to "compute from content". And `transition` doesn't know the target value ahead of time.

Two working approaches:

- **The CSS Grid trick.** Wrap the content in `display: grid` with `grid-template-rows: 0fr`, switch to `1fr` on open, and put `overflow: hidden` on the inner container. A reliable, cross-browser option.
- **`interpolate-size: allow-keywords` on `:root`, combined with `calc-size()`.** This modern pair lets you animate `height: auto` directly. Browser support isn't yet universal at the time of writing, so check current support and provide a fallback.

---

**What's the difference between `cubic-bezier()`, `steps()`, and `linear()` as timing functions?**

Three different mechanisms, not three variants of one.

| Function | Mechanism | Note |
|---|---|---|
| `cubic-bezier(x1, y1, x2, y2)` | A smooth curve from two control points. The `y` coordinates may go outside [0, 1], producing overshoot or bounce. | One smooth shape only: it can't describe several oscillations. |
| `steps(n, jump-term)` | Not continuous interpolation, but `n` discrete value jumps. | For frame-by-frame sprite animation via `background-position`, not for smoothness. |
| `linear()` | A piecewise-linear curve through an explicit list of `(value, position%)` points. | Describes a multi-bounce spring effect in pure CSS. Previously that needed JS. |

## Group 3: Web Animations API

**How does WAAPI relate to CSS transitions/animations under the hood?**

WAAPI is the Web Animations API, and it isn't an alternative engine. It's a programmatic interface to the exact same engine that runs `transition` and `@keyframes`.

`element.animate()` creates the same internal `KeyframeEffect`, with the same value-type-based interpolation. It has the same ability to run on the compositor for `transform`/`opacity`/`filter`.

The difference isn't performance. It's where the values come from and who controls playback. CSS is good for keyframe values known ahead of time. WAAPI is what you reach for when a value is computed at runtime, or when the animation needs programmatic control: pause, reverse, a completion promise.

---

**Explain WAAPI's composite modes (`'replace'` vs `'add'`) and give a practical use case for `'add'`.**

`replace` is the default and swaps the underlying value out; `add` sums with it.

| `composite` | The property's underlying value | On `transform` |
|---|---|---|
| `'replace'` (default) | Fully replaced by the animation's value | The matrix is swapped out |
| `'add'` | The animation's value is added to it | Matrices are multiplied together |

A practical use case for `'add'`: a base "alive" animation, a continuous subtle bob, plus a brief bounce effect on click — both on `transform`.

With `composite: 'add'`, the second animation layers on top of the first. It doesn't interrupt or replace the first one, and it doesn't need a combined transform matrix computed by hand in JS.

Without `add`, the second animation would use the default `replace` and override the first for its duration. Once it finished, the element would visually "snap" back.

---

**Why is WAAPI usually better than toggling CSS classes for animation values that are computed dynamically?**

Toggling classes for an arbitrary, runtime-computed value leaves you two bad options. Either generate CSS on the fly, since you can't define a class for every possible value. Or use inline styles.

Inline styles then need a forced-reflow hack (`void el.offsetWidth`) to **restart** the transition on the same target value. Otherwise the browser won't register the value as having changed.

WAAPI accepts a JS value directly in `element.animate()`, with no intermediate CSS-generation step and no reflow hacks. It still uses the same compositor-friendly engine for `transform`/`opacity`.

---

**What's the difference between scroll-linked and scroll-triggered animation?**

Scroll-linked progress is the scroll position itself. Scroll-triggered animation only starts on scroll and then runs on its own clock.

| | Scroll-linked | Scroll-triggered |
|---|---|---|
| Progress | Equal to the scroll position | Its own duration and easing |
| Own clock | None | Yes |
| Scrolling back up | The animation runs backward, synchronously | Nothing changes; it keeps playing |
| How you get it | `animation-timeline: scroll()`/`view()`, `ScrollTimeline`, `ViewTimeline` | `ScrollTrigger` in play-once mode, or `IntersectionObserver` plus a CSS class |

## Group 4: requestAnimationFrame and JS-Driven Animation

**Why must a `requestAnimationFrame` loop you write yourself account for delta time?**

Because moving a value by a fixed step per frame (`x += 2`) produces a speed that depends on the display's refresh rate. The same code gives 120px/sec at 60 Hz and 240px/sec at 120 Hz.

The correct approach is computing the time elapsed since the previous frame (`timestamp - previousTimestamp`) and scaling the movement by it. Speed is then expressed in units per second rather than units per frame.

That way the final speed is the same regardless of refresh rate. It's just made up of a different number of smaller or larger steps.

---

**Walk through the FLIP technique step by step. Why does it turn an expensive layout animation into a cheap one?**

FLIP stands for First, Last, Invert, Play. Each step is one measurement or one write.

```txt
┌───────────────────────────────────────────────┐
│ First — measure the old position              │
│ getBoundingClientRect() before the DOM change │
└───────────────────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│ Last — apply the DOM change                   │
│ measure the new position                      │
└───────────────────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│ Invert — apply a compensating transform       │
│ no transition: the element looks unmoved      │
└───────────────────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│ Play — turn the transition on                 │
│ clear the compensation; the element travels   │
└───────────────────────────────────────────────┘
```

First — measure the element's current position (`getBoundingClientRect()`) **before** the change to the DOM (document object model, the tree of page elements). Last — apply the actual DOM change, a reorder or a layout shift, and measure the new position **after**.

Invert — compute the difference between First and Last, and immediately apply a compensating `transform` with no transition. The element visually stays in its old spot, even though it's already physically in the new one.

Play — enable a transition on `transform` and clear the compensation. The element smoothly "travels" from its old visual position to its true new one.

The cheapness comes from one fact: the entire visible animation happens purely through `transform`, at the Composite stage (article 01). It doesn't animate real layout properties, which simply don't scale to large numbers of elements without jank.

---

**What's the practical difference between duration-based easing animation and spring animation? Why can a spring be interrupted mid-flight with no visible jump, while a duration-based tween can't easily do that?**

A duration-based tween walks a fixed curve; a spring simulates physics and always knows its current velocity.

| | Duration-based tween | Spring |
|---|---|---|
| State | A position along a fixed curve | Current value and current velocity |
| Duration | Set in advance | None: it stops when the system settles |
| New target mid-flight | Abrupt restart, or a manual recompute | Physics keeps the velocity, so no jump |

Duration-based animation is a function `t → progress`, where `t` is normalized time within a duration **set in advance**. It has no notion of "current velocity", only a position along a fixed curve.

Spring animation models a physical mass-spring-damper system. Its state is `(current value, current velocity)`, and it has no fixed duration at all: it stops on its own once the system physically settles.

Changing the target mid-flight is trivial for a spring. The physics recomputes a new trajectory that preserves the current velocity, with no jump.

For duration-based animation, the same change would require an abrupt restart with a visible jump. The alternative is manually recomputing the remaining time and the current "velocity" along the tangent of the curve, which is non-trivial and usually isn't done.

---

**When is `requestIdleCallback` the wrong tool, and why?**

For animation itself.

`requestIdleCallback` has no guarantees whatsoever about frequency or timing. The callback can be deferred indefinitely if the main thread stays busy, and it isn't synced to the display's refresh rate at all.

It's a tool for background, non-urgent work: batching analytics, warming a cache, lazy initialization. Those are things that should happen "whenever there's a spare moment", not "exactly by the next frame".

## Group 5: Libraries and Ecosystem

**When would you reach for GSAP instead of native CSS/WAAPI? What does `ScrollTrigger` give you that native scroll-driven animations don't?**

GSAP (the GreenSock Animation Platform) is worth reaching for when a task needs timeline orchestration across many independent elements. That means precise positioning — labels, relative offsets like `'-=0.2'` — or complex scroll choreography.

The key concrete difference `ScrollTrigger` provides is the ability to **pin** (`pin: true`) a section in the viewport for the duration of scroll. That stretches a logical animation across several screens of real page height. `scrub` then ties progress to scroll velocity, with smoothing.

The native `animation-timeline: scroll()`/`view()` gives scroll-linked progress for a single element, but it can't "stick" an element to the viewport. That's exactly why elaborate scroll-storytelling sites still need GSAP, not just native CSS.

---

**What problem does `AnimatePresence` in Framer Motion solve, and why does that problem exist in the first place?**

React unmounts a DOM node **synchronously** the moment a render condition stops being true (`{isOpen && <Modal />}` → `isOpen: false`). Any CSS or JS animation on that node has no physical time to finish, because the node is already gone from the tree.

`AnimatePresence` intercepts the moment React "wants" to remove a child. It keeps the child in the DOM a little longer, plays the `exit` animation, and only then actually removes the node.

Without this mechanism, you'd have to build two-phase state yourself: `isOpen` plus a delayed `isRendered`.

---

**When is Lottie the right call, and when is it overkill?**

The right call is when complex vector motion graphics were designed by an animator in After Effects. That covers character animation and detailed onboarding illustrations, where the result needs to ship to the browser 1:1. Rewriting it by hand in CSS or JS would take weeks and still drift from the original.

It's overkill for ordinary interface transitions — a button, a card, a modal — expressible in a couple of lines of CSS via `transform`/`opacity`. There, Lottie adds the weight of a JSON payload and renderer overhead (`svg` or `canvas`). It also adds a hard dependency on the bodymovin export pipeline for any design change.

## Group 6: Performance Debugging

**Debugging scenario: a marketing page stutters while scrolling on a budget Android phone, but is smooth in your desktop Chrome. Walk through your diagnosis process.**

The sequence is six steps, each with a specific tool:

1. **Reproduce it in DevTools with CPU/network throttling on**, emulating weaker hardware. Don't try to judge it by eye on a powerful desktop.
2. **Record a session in the Performance panel and read the main-thread flame chart.** Look for Long Tasks (over 50 ms) and for a repeating Layout→Paint→Composite pattern on every animation frame. That pattern signals a layout property being animated instead of `transform`/`opacity`.
3. **Check for "Forced reflow".** If it's there, click the warning to get a stack trace down to the exact line where reads and writes of geometry are interleaved.
4. **Open the Layers panel.** Check whether the number of composited layers is bloated — layer explosion from `will-change` on static elements, or from multiple `filter`s. Check the memory estimate for full-screen layers too: on mobile, with memory shared between CPU and GPU, they load the device harder than on desktop.
5. **Enable paint flashing.** Check whether more of the screen is repainting during scroll than it should, because of missing layer isolation.
6. **If the problem is in the scroll handler itself**, check whether `{ passive: true }` is set, and whether geometry is being read synchronously inside the handler.

It's this sequence of specific tools that separates systematic diagnosis from guesswork, not "guessing from reading the code".

---

**How do you diagnose layout thrashing in DevTools?**

Record a session in the Performance panel while reproducing the interaction. Then look for Layout blocks explicitly flagged "Forced reflow" — a purple block with a warning icon. Clicking the warning expands a stack trace pointing to the exact line of code responsible.

In the flame chart, look for a tight repeating pattern of small Layout blocks packed close together, correlated with a loop in your code. That's the visual signature of the read/write interleaving that causes layout thrashing (article 01). A single, larger Layout block is different: it's normal and expected for one legitimate style change.

---

**What is INP, and how can animation-heavy code hurt it?**

INP (Interaction to Next Paint) is a Core Web Vitals metric. It measures the delay between a user's action and the moment the browser physically shows the next updated frame in response. The action is a click, a tap, a keypress.

Suppose an rAF callback or JS-driven animation holds the main thread longer than the frame budget. If that happens right at the moment of a user interaction, the response frame gets delayed. That frame might be a button's visual "pressed" state, and the delay directly hurts INP.

The practical consequence: poorly budgeted animation isn't just an "aesthetic" issue. It's a measurable factor in the same Web Vitals report as LCP (Largest Contentful Paint) and CLS (Cumulative Layout Shift). That has real consequences for SEO (search engine optimization).

## Group 7: Accessibility and Product Decisions

**How do you correctly implement `prefers-reduced-motion` support? Does it mean disabling animation entirely?**

`prefers-reduced-motion` is a setting in the operating system, and users turn it on for a medical reason. Vestibular disorders make large-amplitude motion cause dizziness and nausea. It isn't an aesthetic preference.

A baseline implementation is a global CSS `@media (prefers-reduced-motion: reduce)` block that zeroes out animation and transition durations. That's a workable safety net, but not the best solution everywhere.

The right pattern is replacing **movement** with an opacity cross-fade, which preserves the fact that a transition happens between states. In CSS that means custom properties toggled inside the media query, for example `--enter-transform: translateY(20px)` → `none`. The animation isn't removed entirely.

In JS the same logic goes through `window.matchMedia('(prefers-reduced-motion: reduce)')`. A subscription to `change` is mandatory, because the user can switch the setting mid-session. At the library level there's `MotionConfig reducedMotion="user"` in Framer Motion, which applies this automatically to every child component.

---

**Why shouldn't focus management be gated on an animation finishing?**

Because it creates a real accessibility barrier. A user working via keyboard or screen reader has to wait for a decorative animation to finish before focus lands on the right element. Say, `await animation.finished` before `element.focus()`. A 200-300 ms delay is invisible to a sighted user with no vestibular issues, and it's still a barrier.

The application's state changes the moment the user acts — opening a modal, moving between steps. Focus should move synchronously with that state change. The animation plays in parallel, visually illustrating the transition, without blocking accessibility for users who don't experience that animation the same way.
