# requestAnimationFrame and JS-Driven Animation

## When declarative tools stop being enough

CSS transitions, keyframes, and WAAPI (articles 02-03) cover the large majority of UI animation and should stay your default choice. But there's a class of problems that simply can't be expressed declaratively, because they have no fixed "from" and "to" at the moment they start:

```txt
- Continuous simulation: physics (gravity, collisions, cursor inertia)
- A value that depends on MULTIPLE live sources at once: cursor
  position + scroll velocity + time — these can't be described as
  keyframes ahead of time, because the combination changes every frame
- An animation that needs to be interrupted MID-FLIGHT and continue
  from its CURRENT velocity in a new direction — not play out along
  a pre-defined curve to completion
- Real-time interaction: a drag that keeps momentum after release,
  where the final trajectory depends on the gesture's velocity at
  the moment of release, known only at runtime
```

These cases need full control over what happens every single frame — that's `requestAnimationFrame` (rAF). Set the frame clearly up front: rAF-driven animation is main-thread work (see [Rendering Pipeline and Frame Budget]), and unlike CSS/WAAPI on the compositor, it's never "free" — it's the first thing to suffer when the main thread gets overloaded. Choosing it is a deliberate trade for control, not an upgrade to a "more powerful" tool.

## `requestAnimationFrame` mechanics: exactly when the callback fires

```javascript
function tick(timestamp) {
  // timestamp is a DOMHighResTimeStamp — the same value
  // performance.now() would have returned at the start of this frame
  console.log(timestamp);
  requestAnimationFrame(tick); // schedule the next call
}
requestAnimationFrame(tick);
```

The rAF callback runs **before** the Style/Layout/Paint stage of the current frame, synced to the display's refresh rate (vsync) — exactly once per frame, not "as often as possible." That's a fundamental difference from `setInterval(fn, 16)`, which has no connection to the actual rendering cycle at all: `setInterval` can fire in the middle of an already-running render stage (in which case a style change only lands in the NEXT frame, not the current one — a wasted call), can accumulate drift over time, and isn't aligned with the display's refresh rate (60 Hz, 120 Hz, 144 Hz — all different).

A key practical detail: **in background tabs, `requestAnimationFrame` gets throttled or fully suspended by the browser** (typically down to ~once per second or stopped entirely) — this saves CPU and battery for animations the user physically can't see. `setInterval`, unlike rAF, keeps ticking in the background (though modern browsers throttle it too, just less aggressively and less predictably). That's another reason to use rAF specifically for animation rather than timers: the browser correctly pauses the animation on its own wherever the user wouldn't see it anyway.

```javascript
const id = requestAnimationFrame(tick);
cancelAnimationFrame(id); // stop the scheduled call — must be done when
                          // a component unmounts / an element is removed,
                          // otherwise the callback keeps running and tries
                          // to touch DOM that no longer exists
```

## The canonical rAF loop with delta time — and why leaving it out breaks on 120 Hz

The most common mistake in hand-rolled JS animation is moving a value by a fixed step **per frame** instead of **per unit of time**:

```javascript
// ❌ Speed depends on the display's refresh rate
let x = 0;
function tick() {
  x += 2; // "2 pixels per frame"
  element.style.transform = `translateX(${x}px)`;
  requestAnimationFrame(tick);
}
requestAnimationFrame(tick);
// On a 60 Hz screen: 2px × 60 frames/sec = 120px/sec
// On a 120 Hz screen: 2px × 120 frames/sec = 240px/sec
// The exact same code moves TWICE as fast on the higher-refresh
// display — a bug that's hard to catch locally if the developer
// only has a standard 60 Hz monitor
```

The fix is to track **delta time** (time elapsed since the last frame) and scale the movement step by it, expressing speed in units **per second**, not units **per frame**:

```javascript
// ✅ Speed doesn't depend on the display's refresh rate
let x = 0;
const speedPerSecond = 120; // px/sec — same speed on any display

let previousTimestamp;
function tick(timestamp) {
  if (previousTimestamp === undefined) previousTimestamp = timestamp;
  const deltaMs = timestamp - previousTimestamp;
  previousTimestamp = timestamp;

  x += speedPerSecond * (deltaMs / 1000);
  element.style.transform = `translateX(${x}px)`;

  requestAnimationFrame(tick);
}
requestAnimationFrame(tick);
// At 60 Hz: 60 frames × 2px = 120px/sec. At 120 Hz: 120 frames × 1px = 120px/sec.
// A different number of smaller steps, the SAME final speed.
```

This isn't a theoretical footnote for completeness — it's a real source of "it's smooth on my Mac, but on the QA engineer's 144 Hz gaming laptop the animation runs 2.4x too fast and finishes way earlier than it should."

## Interpolation and normalized progress

Practically every time-based JS animation boils down to the same formula: normalize elapsed time into `[0, 1]`, apply an easing function to that normalized `t`, and interpolate between the start and end value based on the result:

```javascript
function animateValue(from, to, duration, easingFn, onUpdate, onComplete) {
  const startTime = performance.now();

  function tick(now) {
    const elapsed = now - startTime;
    const t = Math.min(elapsed / duration, 1); // normalized progress [0, 1]
    const easedT = easingFn(t);                 // apply the curve
    const value = from + (to - from) * easedT;   // linear interpolation (lerp)

    onUpdate(value);

    if (t < 1) requestAnimationFrame(tick);
    else onComplete?.();
  }

  requestAnimationFrame(tick);
}

animateValue(0, 300, 400, easeOutCubic, (v) => {
  element.style.transform = `translateX(${v}px)`;
});
```

`from + (to - from) * t` is `lerp` (linear interpolation), the primitive that all time-based animation is built on — the CSS engine does conceptually the same thing internally, just on the compositor, without any JS code of yours running per frame.

## Easing as a pure function of `t`

An easing function is, mathematically, just `f(t): [0,1] → ℝ` (usually, though not necessarily, mapping into `[0,1]` — overshoot is allowed, exactly as with `cubic-bezier()`, see article 02). Unlike `cubic-bezier()`, JS easing isn't limited to a cubic Bézier curve — you can implement anything: bounce, elastic, stepped effects.

```javascript
const easeOutCubic  = (t) => 1 - Math.pow(1 - t, 3);
const easeInOutQuad = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);

const easeOutBounce = (t) => {
  const n1 = 7.5625, d1 = 2.75;
  if (t < 1 / d1) return n1 * t * t;
  if (t < 2 / d1) return n1 * (t -= 1.5 / d1) * t + 0.75;
  if (t < 2.5 / d1) return n1 * (t -= 2.25 / d1) * t + 0.9375;
  return n1 * (t -= 2.625 / d1) * t + 0.984375;
};
```

The practical interview takeaway: `cubic-bezier()` and a JS easing function solve the exact same mathematical problem (`t → progress`), just at different levels — declarative (CSS, limited to the shape of a Bézier curve, with `linear()` covering the trickier cases — see article 02) and imperative (JS, arbitrary formula, always at the cost of main-thread work).

## Springs and damping: the physical alternative to duration

Every example above shares one thing: a fixed **duration** set up front. That works well for "open → closed" transitions with known endpoints. It works poorly for interactive animation, where motion starts with an already-nonzero velocity (say, the user flung an element after dragging it) or needs to be interrupted mid-flight with a new target.

Spring animation doesn't model "progress over time" — it models a physical mass-spring-damper system: a spring pulls the current value toward the target with force proportional to the distance, and a damper dissipates that force proportional to velocity. It has **no fixed duration** — it stops on its own once velocity and distance from the target become negligibly small:

```javascript
function springStep(current, velocity, target, { stiffness = 170, damping = 26, mass = 1 }, dt) {
  const springForce = -stiffness * (current - target); // pulls toward the target
  const dampingForce = -damping * velocity;             // dissipates oscillation
  const acceleration = (springForce + dampingForce) / mass;

  velocity += acceleration * dt;
  current += velocity * dt;

  return { current, velocity };
}

function animateSpring(from, to, onUpdate, config = {}) {
  let current = from;
  let velocity = 0;
  let previousTime;

  function tick(now) {
    if (previousTime === undefined) previousTime = now;
    const dt = Math.min((now - previousTime) / 1000, 1 / 30); // clamp dt against lag spikes
    previousTime = now;

    ({ current, velocity } = springStep(current, velocity, to, config, dt));
    onUpdate(current);

    // Stop once the system has effectively settled
    if (Math.abs(to - current) > 0.01 || Math.abs(velocity) > 0.01) {
      requestAnimationFrame(tick);
    }
  }
  requestAnimationFrame(tick);
}
```

Why this "feels more natural" isn't a matter of taste — it follows directly from the model: real-world objects don't move on a pre-scheduled timeline, they react to forces in the present moment. And that's exactly why springs are interruptible in a way duration-based animation isn't: a spring's state is `(current value, current velocity)`, not `(t within a fixed duration)`. Changing the `target` mid-flight is trivial — the physics simply recomputes a new trajectory that preserves the current velocity, with no visible "jump":

```javascript
// The user moves the mouse — the target changes every frame,
// and the spring keeps moving smoothly, with no animation restart
let springTarget = 0;
document.addEventListener('mousemove', (e) => { springTarget = e.clientX; });
// animateSpring(...) reads springTarget on every step instead of a fixed `to`
```

This is the core reason modern UI toolkits (iOS, Framer Motion, react-spring, Motion.dev) default to springs for interactive, interruptible elements — and to duration+easing for non-clickable, "plays once" transitions.

## Lerp smoothing for cursors and parallax — and a hidden frame-rate trap

A common pattern is "smoothly following" a target: a custom cursor lagging behind the real mouse pointer, or a parallax layer that smooths out abrupt scroll jumps:

```javascript
// ❌ Naive lerp — the "0.1" factor gives a DIFFERENT convergence
// speed at different display refresh rates
let current = 0;
function tick() {
  current += (target - current) * 0.1; // "pull" 10% of the distance closer, every frame
  cursor.style.transform = `translateX(${current}px)`;
  requestAnimationFrame(tick);
}
// At 120 Hz, current gets "pulled" twice as often per second as
// at 60 Hz → the cursor physically catches up to the target
// noticeably faster
```

The same class of problem as "px += 2 per frame" above, just more hidden — the code looks time-independent already, but the decay factor `0.1` is implicitly tied to how often the callback runs. The correct formula is exponential decay, corrected for the actual `dt`:

```javascript
// ✅ Convergence doesn't depend on frame rate
let current = 0;
let previousTime;
const smoothingHalfLife = 0.08; // seconds it takes to halve the distance to the target

function tick(now) {
  if (previousTime === undefined) previousTime = now;
  const dt = (now - previousTime) / 1000;
  previousTime = now;

  const decay = 1 - Math.pow(2, -dt / smoothingHalfLife);
  current += (target - current) * decay;

  cursor.style.transform = `translateX(${current}px)`;
  requestAnimationFrame(tick);
}
```

This detail rarely shows up in tutorials, but its absence is exactly why "our cursor blob feels different on the 60 Hz demo monitor versus a ProMotion 120 Hz MacBook," even though the code is nominally "the same."

## FLIP: turning an expensive layout animation into a cheap transform animation

The classic problem: list items get reordered (sorting, drag-and-drop, filtering), their position in the DOM flow changes instantly, and the only obvious way to animate that is animating `top`/`left`/`grid-row` and similar properties, which triggers Layout every single frame (article 01) and simply doesn't scale to lists of even a few dozen items without visible jank.

**FLIP** (First → Last → Invert → Play) is a technique that sidesteps the problem entirely, reducing the animation to `transform` alone:

```txt
First  — BEFORE the DOM change: measure the element's current
          position (getBoundingClientRect())
Last   — apply the DOM change (the actual reorder/layout shift) —
          the browser instantly places the element in its NEW
          position, with NO animation, and measure that new position
Invert — compute the delta between First and Last, and IMMEDIATELY
          apply a transform to the element that compensates for it —
          visually the element looks like it's still in its old spot,
          even though it's physically (in layout) already in the new one
Play   — enable a transition on transform and clear the compensating
          transform → the element smoothly "travels" from its old
          visual position to its true new one, and the entire animation
          is a pure compositor transform, with zero reflow per frame
```

A step-by-step implementation for a reorderable list:

```javascript
function flipReorder(container, reorderFn) {
  const items = [...container.children];

  // FIRST — capture positions BEFORE the DOM change
  const firstRects = new Map(items.map((el) => [el, el.getBoundingClientRect()]));

  // (the actual DOM change — e.g. re-sorting based on data)
  reorderFn();

  // LAST — capture positions AFTER the DOM change
  items.forEach((el) => {
    const first = firstRects.get(el);
    const last = el.getBoundingClientRect();

    const deltaX = first.left - last.left;
    const deltaY = first.top - last.top;

    if (deltaX === 0 && deltaY === 0) return; // element didn't move — skip it

    // INVERT — compensate for the difference via transform, with NO transition
    el.style.transition = 'none';
    el.style.transform = `translate(${deltaX}px, ${deltaY}px)`;

    // Force layout ONCE so the browser commits the inverted state
    // before we turn the transition on
    el.getBoundingClientRect();

    // PLAY — enable the transition and clear the compensation
    el.style.transition = 'transform 0.3s ease';
    el.style.transform = '';
  });
}
```

This is exactly the mechanism behind `react-flip-toolkit` and Framer Motion's layout animations (the `layout` prop, article 05) — they automate precisely these four steps, taking the manual before/after `getBoundingClientRect()` bookkeeping and re-render synchronization off the developer's plate. Understanding FLIP by hand is what separates "I use a library with layout animations" from "I understand WHY they work at all, and why this isn't literally animating layout."

## `requestIdleCallback`: not for animation — for the work that shouldn't compete with it

`requestIdleCallback` (rIC) schedules a callback to run during the browser's spare time between frames — when there's slack before the next frame is due and the main thread isn't busy with anything urgent:

```javascript
requestIdleCallback((deadline) => {
  while (deadline.timeRemaining() > 0 && tasksQueue.length > 0) {
    processTask(tasksQueue.shift());
  }
  if (tasksQueue.length > 0) requestIdleCallback(arguments.callee);
});
```

The key mistake is trying to use `rIC` FOR animation: it has **no guarantee about frequency or timing** — the callback can be deferred indefinitely if the main thread stays busy, and it has no connection to the display's refresh rate at all. `rIC` is a tool for background, non-urgent work: batching analytics, warming a cache, prefetching data, lazy initialization — things that should happen "whenever there's a spare moment," not "exactly on the next frame."

### When it's better not to animate at all

Part of doing JS animation professionally is not running it where it isn't needed:

```javascript
// Pause the rAF loop when the element is outside the viewport —
// there's no point spending CPU/battery on an animation nobody can see
const observer = new IntersectionObserver(([entry]) => {
  if (entry.isIntersecting) startAnimationLoop();
  else stopAnimationLoop();
});
observer.observe(element);
```

This is the same principle behind the browser pausing rAF in background tabs — just applied manually to individual elements within the page itself. `prefers-reduced-motion` as another reason to skip or tone down an animation is covered in detail in article 07.

## Connection to other articles

```txt
[Rendering Pipeline and Frame Budget] — why rAF-driven animation is
                                         main-thread work, and how the
                                         frame budget limits what fits
                                         in a single tick
[Web Animations API]                  — WAAPI handles most of what used
                                         to need a hand-rolled rAF loop,
                                         WITHOUT costing the main thread
                                         every frame
[Animation Libraries and Ecosystem]   — GSAP and Framer Motion (with
                                         react-spring under the hood)
                                         implement exactly the springs
                                         and FLIP from this article,
                                         behind a ready-made API
[Performance Debugging and Jank
 Hunting]                              — how to see in DevTools that an
                                         rAF callback isn't fitting
                                         inside the frame budget
```

## Common interview traps

- **Moving a value by a fixed step per frame instead of per unit of time** — not realizing such code runs at different speeds on 60 Hz versus 120/144 Hz displays, and not knowing delta time as the standard fix.

- **Confusing `requestAnimationFrame` with `setInterval`/`setTimeout`** — not knowing rAF is synced to the display's refresh rate and automatically pauses in background tabs, while timers aren't.

- **Treating spring animation as "just another easing curve"** — not understanding it has no fixed duration at all, and that this is precisely why it's interruptible mid-flight with no visible jump, unlike duration-based animation.

- **Not knowing about the naive lerp frame-rate bug** — using `current += (target - current) * 0.1` with no `dt` correction, not realizing the convergence speed is implicitly tied to frame rate.

- **Being unable to walk through FLIP step by step** — knowing the technique's name (or a library that uses it) but not being able to unpack First/Last/Invert/Play and explain why the actual animation ends up being on `transform`, not a layout property.

- **Suggesting `requestIdleCallback` for animation** — not knowing it has no timing guarantees and isn't synced to the render frame, which makes it fundamentally unsuitable for visual animation — it's for background, non-urgent work only.

- **Not pausing off-screen rAF loops** — never considering that an infinite `requestAnimationFrame` loop on an invisible element keeps burning CPU/battery for nothing, unless it's stopped manually via an `IntersectionObserver` or a similar mechanism.
