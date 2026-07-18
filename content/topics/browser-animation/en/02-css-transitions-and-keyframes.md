# CSS Transitions and Keyframes

## Why the declarative path is the right default, not just the "easy" one

CSS animation isn't preferable because it's "less code to write" — it's preferable because it hands the browser maximum information up front. From the start, the browser knows the starting value, the target value, the duration, and the curve, so it can plan the compositor thread's work (see [Rendering Pipeline and Frame Budget]) without a constant back-and-forth with the main thread. JS-driven animation via `requestAnimationFrame` (article 04) has to recompute a value on the main thread every single frame — a CSS transition or keyframe animation on `transform`/`opacity` can run entirely on the compositor, even while the main thread is busy.

The practical rule follows from that: **if an animation can be expressed in CSS, express it in CSS**, and reach for JS only when you need logic CSS genuinely can't express (a dynamic target, dependence on physics/velocity, interrupting mid-flight while preserving current speed). That's why CSS transitions and keyframes aren't the "beginner" layer of this topic — they're a senior engineer's working tool for the large majority of real-world UI animation.

## How `transition` actually works

`transition` isn't "fade this in smoothly" — it's a precise contract: the browser tracks a property's **computed value**, and when it changes, instead of swapping it instantly, it plays a sequence of intermediate values between old and new over the given duration.

```css
.button {
  transition-property: background-color, transform;
  transition-duration: 0.2s, 0.3s;
  transition-timing-function: ease-out, cubic-bezier(0.34, 1.56, 0.64, 1);
  transition-delay: 0s, 0.05s;
}
/* Comma-separated shorthand = a list of independent transitions,
   each with its own parameters matched by position in the list */
```

Not every CSS property can be interpolated. The browser groups them by how they interpolate:

```txt
Numeric (interpolated as a number):        width, opacity, font-size, line-height
Color (interpolated per channel):          color, background-color, border-color
Transform (interpolated by matrix
  component — NOT as a string!):           transform
Lists of matching length:                  box-shadow (if the number of shadows
                                            matches), transform with the same
                                            function list
Discrete (not interpolated — the value
  flips at 50% of the duration):           display, visibility (partially),
                                            grid-template-columns with string
                                            values, most keyword properties
```

The key detail about discrete properties: `transition: display 0.3s` isn't technically an error — the browser just has no way to smoothly interpolate `display: block` into `display: none`, so the value flips instantly **halfway through** the given duration (by default), not at the start and not at the end. In practice this looks like "nothing animated," which is exactly what produces the bug report "transition isn't working" — it is working, just on a property that can't be blended.

Another interview-level nuance: `transform` interpolates **not as a text string**, but by decomposing the transform matrix into components (translate/scale/rotate/skew) and interpolating each one separately. That's why `transform: translateX(0) rotate(0deg)` → `transform: translateX(100px) rotate(45deg)` produces smooth motion along an arc of components rather than an abrupt recompute.

## `transition: all` — not a shorthand, a source of production bugs

`transition: all 0.3s ease` looks like a harmless default: "animate whatever changes." In practice it's an open-ended contract: **any** future change to **any** CSS property on this element now animates, including ones you never planned for.

```css
/* ❌ transition: all — a time bomb */
.card {
  transition: all 0.3s ease;
}

/* Six months later, another developer adds adaptive logic: */
.card.is-pinned {
  position: sticky;
  top: 0;
}
/* Result: toggling .is-pinned makes the card visibly "glide" into
   its new position over 0.3s, because transition: all picked up
   the change to top — nobody intended to animate that at all.
   Bug report: "the card jumps around while scrolling." Finding
   the cause: 40 minutes in DevTools. */
```

```css
/* ✅ An explicit list — only what's intended actually animates,
   and it's self-documenting: a reader immediately sees what
   MIGHT change visually on this element */
.card {
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}
```

There's a second, less obvious argument against `all`: the browser has to **watch every animatable property of the element** for changes to know whether a transition needs to start — a small but constant overhead that an explicit list removes entirely. In production code, `transition: all` is defensible only in prototypes, or on elements that are guaranteed never to receive new styles in the future — which in practice is almost never actually guaranteed.

## `@keyframes` and `animation-*`: the ones interviewers catch people on

`transition` can only go "from the current value to a new one" — a single transition along one sequence of states. `@keyframes` gives you an arbitrary number of intermediate points and doesn't need a state-change trigger — the animation can start on its own, as soon as the element exists.

```css
@keyframes pulse {
  0%   { transform: scale(1);    opacity: 1;   }
  50%  { transform: scale(1.08); opacity: 0.85; }
  100% { transform: scale(1);    opacity: 1;   }
}

.notification-dot {
  animation-name: pulse;
  animation-duration: 1.6s;
  animation-timing-function: ease-in-out;
  animation-iteration-count: infinite;
  animation-fill-mode: both;
}
```

Properties that most often get mixed up or forgotten in interviews:

**`animation-fill-mode`** — what happens to the element's styles BEFORE the animation starts and AFTER it ends:

```txt
none      (default) — before start and after end, the element's normal
            CSS rules apply, NOT the keyframe values
forwards  — after the animation ends, the LAST keyframe's (100%) values persist
backwards — BEFORE the animation starts (including animation-delay),
            the FIRST keyframe's (0%) values apply
both      — forwards + backwards combined
```

The classic bug: an element animates via `@keyframes` from `opacity: 0` to `opacity: 1`, the animation plays correctly once (`animation-iteration-count: 1`), but once it's done **the element suddenly vanishes** — because `animation-fill-mode` defaults to `none`, and once the animation ends the browser reverts the element to its normal CSS state, where `opacity` is either unset or back to its pre-animation value. The fix is `animation-fill-mode: forwards`.

**`animation-direction`** — `alternate` is the one people forget:

```css
.loader-bar {
  animation: slide 1s ease-in-out infinite alternate;
  /* alternate: even iterations run forward, odd ones run in
     reverse (100% → 0%), with no "teleport" back to the start
     on each cycle */
}
```

```txt
normal            — always 0% → 100%
reverse           — always 100% → 0%
alternate         — 0%→100%, then 100%→0%, alternating
alternate-reverse — 100%→0%, then 0%→100%, alternating
```

**`animation-play-state`** — the only way to pause a CSS animation without JS toggling classes:

```css
.spinner { animation: spin 1s linear infinite; }
.spinner:hover { animation-play-state: paused; }
```

**Multiple animations via commas** — same as with transition, the comma-separated shorthand sets up independent animations:

```css
.card {
  animation: fadeIn 0.3s ease-out forwards,
             pulse 2s ease-in-out 0.3s infinite;
  /* fadeIn plays once, immediately; pulse starts 0.3s later
     (after fadeIn) and repeats forever */
}
```

## Timing functions: not just "which curve looks nicer"

A timing function is a function `t → progress`, where `t` is normalized time from 0 to 1 (0% → 100% of the duration), and `progress` is the normalized progress of the interpolated value, also usually 0 to 1 — though not necessarily, as the overshoot section below explains.

### Keywords, and what they mean physically

```txt
linear      — constant speed, no acceleration/deceleration. Reads as
              "mechanical," good for continuous processes (a progress
              bar, a spinning loader), but poor for UI enter/exit
              transitions — it looks unnaturally abrupt at both ends.
ease        — (transition's default) smooth start, speeds up,
              smoothly decelerates toward the end.
ease-in     — slow start, sharp acceleration toward the end.
              Fits elements LEAVING the scene.
ease-out    — sharp start, smooth deceleration toward the end.
              Fits elements ENTERING the scene — the eye reads
              a fast initial response as "responsiveness."
ease-in-out — slow start and slow end, faster in the middle.
              Fits transitions between two stable states (open/closed).
```

### `cubic-bezier(x1, y1, x2, y2)` — how to actually read the curve

Every keyword above is just a preset `cubic-bezier()`. The Bézier curve is built from two control points, P1(x1, y1) and P2(x2, y2), with P0(0,0) and P3(1,1) fixed:

```txt
ease         = cubic-bezier(0.25, 0.1, 0.25, 1.0)
ease-in      = cubic-bezier(0.42, 0.0, 1.0, 1.0)
ease-out     = cubic-bezier(0.0, 0.0, 0.58, 1.0)
ease-in-out  = cubic-bezier(0.42, 0.0, 0.58, 1.0)
linear       = cubic-bezier(0.0, 0.0, 1.0, 1.0)   (equivalent to the linear keyword)
```

The practical reading: the control points' `x` values must stay within [0, 1] — that's the time axis, and time can't run backward — but `y` **can go outside [0, 1]**. That's exactly what produces overshoot: the value temporarily shoots past the target and settles back, giving a springy feel without a single line of JS:

```css
/* Material Design's "fast-out, slow-in" for entering elements */
.modal {
  transition: transform 0.3s cubic-bezier(0.05, 0.7, 0.1, 1);
}

/* A "springy" entrance from y > 1 on the second control point */
.toast {
  transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  /* y2 = 1.56 → the element overshoots the target position and
     settles back — the exact "bounce" many people reach for a
     JS spring to get, even though this is plain CSS */
}
```

Designing a curve by hand isn't something you do in your head — people use a visual editor (Chrome and Firefox DevTools both open one when you click a `cubic-bezier(...)` value in the styles panel, or a site like cubic-bezier.com), dragging P1/P2 visually and copying the resulting numbers.

### `linear()` — piecewise-linear curves for bounce/spring effects in pure CSS

`cubic-bezier()` physically can't describe **multiple** oscillations (several "bounces," the way a real spring would) — it's a single smooth curve with at most one overshoot. The modern `linear()` timing function solves that: you supply a list of `(value, position%)` points, and the browser linearly interpolates between them — effectively a hand-built piecewise-linear approximation of any curve, including multi-bounce effects:

```css
.bouncy-ball {
  /* Explicit points approximate a damped bounce: overshoots
     above 1, settles below, overshoots slightly again, damping
     down to the final value of 1 */
  transition: transform 0.8s linear(
    0, 0.5 15%, 0.9 30%, 1.1 45%, 0.98 60%, 1.02 75%, 1 100%
  );
}
```

This is the same result that used to require a JS spring (article 04) or a library — now achievable declaratively, without a single line of JS, at the cost of having to either generate the curve with a tool (`linear()` easing generators already exist online) or work it out by hand.

### `steps(n, jump-term)` — not easing, sprite-sheet animation

`steps()` is a fundamentally different kind of timing function: instead of continuous interpolation, the value **jumps** through `n` discrete positions. The classic use case is frame-by-frame sprite-sheet animation via `background-position`:

```css
/* An 8-frame walk-cycle sprite sheet, each frame 64px wide */
.walking-sprite {
  width: 64px;
  height: 64px;
  background-image: url('walk-sprite.png'); /* 512px = 8 × 64px */
  animation: walk-cycle 0.8s steps(8, jump-end) infinite;
}

@keyframes walk-cycle {
  from { background-position: 0 0; }
  to   { background-position: -512px 0; }
}
/* steps(8, jump-end): the range from 0 to -512px is split into
   8 EQUAL jumps — background-position instantly "teleports" to
   each next frame's position, with no smearing between sprite
   frames */
```

`jump-end` (the default) vs. `jump-start` decides whether the jump happens at the start or the end of each step interval — a detail that usually doesn't matter for sprites, but matters when you need precise sync with audio or events.

## `@starting-style` — transitioning from "the element didn't exist yet"

The classic problem: `transition` has no "state before the element appeared" — if an element is inserted into the DOM with `display: none → block`, or mounted for the first time, the browser has nothing to interpolate from, because there was no computed "previous frame" with an old value before that point. The old workaround: mount the element with initial styles, then on the next tick (`requestAnimationFrame` or `setTimeout(0)`) switch to the final class, forcing the browser to commit the first frame before starting the transition.

`@starting-style` solves this declaratively: you explicitly describe what the element's styles would have been "one frame before" its first render, or before transitioning out of `display: none`:

```css
.dialog {
  display: none;
  opacity: 0;
  transform: scale(0.9);
  transition: opacity 0.25s, transform 0.25s, display 0.25s allow-discrete;
}

.dialog[open] {
  display: block;
  opacity: 1;
  transform: scale(1);

  @starting-style {
    /* The "entry state" — where the transition starts from,
       the moment the element gets display: block */
    opacity: 0;
    transform: scale(0.9);
  }
}
```

Note the `display: 0.25s allow-discrete` in `transition-property`: `display` is a discrete property (see the table above) and can't be animated by default. `transition-behavior: allow-discrete` (used here in shorthand form) explicitly lets discrete properties participate in the transition: the browser flips `display: none → block` **at the start** of the transition (so the element is visible while the other properties animate), instead of at the midpoint as it would by default. This removes the last reason `display: none` elements used to need JS hacks for entry animation — modals, tooltips, and dropdowns can now animate on pure CSS from start to finish, including the moment they enter the DOM.

## Animating `auto` — `interpolate-size` and `calc-size()`

Another classic pain point: CSS historically couldn't animate `height: auto` (or `width: auto`) — because `auto` isn't a number, it's an instruction to "compute from content," and `transition` doesn't know the target numeric value ahead of time. For years this was worked around with hacks: a `max-height` set to some deliberately large value (breaks if the real content is taller, or makes the animation "skip past" empty space if it's shorter), or a CSS Grid trick with `grid-template-rows: 0fr → 1fr` (works, but requires wrapping in a grid container and doesn't always fit the layout).

The modern fix is the `interpolate-size` property and the `calc-size()` function:

```css
:root {
  interpolate-size: allow-keywords;
  /* Explicitly allow interpolating keyword values like auto —
     usually set once, globally */
}

.accordion-panel {
  height: 0;
  overflow: hidden;
  transition: height 0.3s ease;
}

.accordion-panel.is-open {
  height: auto;
  /* Previously this just didn't animate. With
     interpolate-size: allow-keywords, the browser computes
     the target numeric value for auto itself (via an internal
     equivalent of calc-size(auto, size)) and interpolates to
     it like an ordinary number */
}
```

Browser support for this pairing is recent as of this writing (check caniuse before relying on it in production without a fallback); for projects that need broad support right now, the grid trick with `0fr`/`1fr` remains a solid, reliable workaround:

```css
/* A proven cross-browser workaround until interpolate-size has wide support */
.accordion-wrapper {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.3s ease;
}
.accordion-wrapper.is-open {
  grid-template-rows: 1fr;
}
.accordion-content {
  overflow: hidden; /* required — otherwise content spills out during the fr-fraction animation */
}
```

## CSS variables that "don't animate," and `@property`

A plain custom property (`--angle: 0deg`) is, to the browser, an **opaque token string**, not a typed value. The browser doesn't know `--angle` is an angle rather than arbitrary text, so it can't interpolate it from `0deg` to `360deg`: the value either flips instantly (like a discrete property) or the transition doesn't even start.

```css
/* ❌ Doesn't animate smoothly — the browser doesn't know the TYPE of --angle */
.gradient-box {
  --angle: 0deg;
  background: conic-gradient(from var(--angle), red, blue, red);
  transition: --angle 1s linear;
}
```

`@property` registers a custom property with an explicit type (`syntax`), inheritance behavior, and initial value — after that, the browser knows WHAT to interpolate and HOW:

```css
@property --angle {
  syntax: '<angle>';
  inherits: false;
  initial-value: 0deg;
}

.gradient-box {
  --angle: 0deg;
  background: conic-gradient(from var(--angle), red, blue, red);
  transition: --angle 1s linear;
}

.gradient-box:hover {
  --angle: 360deg; /* now spins smoothly — the CSS variable animates as an <angle> */
}
```

This unlocks a whole class of animations that used to require JS: rotating gradients, numeric counters via `counter()` paired with an animatable `<number>`, smooth transitions between arbitrary numeric parameters that drive several derived CSS properties at once via `calc()`. `@property` can also be declared via a JS API — `CSS.registerProperty()` — with identical effect, for cases where the registration needs to happen dynamically.

## Connection to other articles

```txt
[Rendering Pipeline and Frame Budget] — why transform/opacity transitions are
                                         physically cheap, not just "because CSS"
[Web Animations API]                  — the same transition/keyframe engine,
                                         accessible from JS programmatically,
                                         with promises and precise time control
[rAF and JS-Driven Animation]         — the FLIP technique uses exactly the
                                         transform-based transitions from this
                                         article as its final step
[Motion Design Patterns and
 Accessibility]                       — how the timing functions from this
                                         article become product conventions
                                         (enter fast-out-slow-in, exit faster)
```

## Common interview traps

- **"`transition: all` is just shorthand, nothing wrong with it"** — failing to see it as a real production bug source: any future style change on the element starts animating unexpectedly, including changes added by another developer months later with no idea a transition is even watching.

- **Confusing `transition` and `animation`** — being unable to explain the substantive difference: `transition` needs a trigger (a state/class change) and describes a move between two values; `animation` + `@keyframes` needs no trigger, can start on its own, and supports an arbitrary number of intermediate points and repeats.

- **Forgetting `animation-fill-mode: forwards`** — the classic "the animation played, then the element snapped back" bug — because without `forwards`, the browser reverts the element to its normal CSS rules once the animation ends instead of keeping the last keyframe's values.

- **Assuming `cubic-bezier()` can't produce a "spring" effect** — not knowing that a control point's `y` coordinate can go outside [0, 1], which is exactly what creates overshoot/bounce in pure CSS, no JS spring required.

- **Not knowing `steps()`** — confusing it with an easing curve, when it's a fundamentally different mechanism: discrete jumps rather than continuous interpolation, built specifically for sprite/frame-based animation.

- **Not knowing CSS historically couldn't animate `height: auto`** — and having no answer for either fix (the grid `0fr`/`1fr` trick as the proven option, `interpolate-size`/`calc-size()` as the modern one) — "how do you animate an accordion with dynamic height" comes up in nearly every practical interview on this topic.

- **Not knowing about `@property`** — assuming CSS custom properties just "can't" animate at all, instead of understanding that the real issue is the value having no type, which `@property` fixes by registering one.
