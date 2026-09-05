# requestAnimationFrame and JS-Driven Animation

## When declarative tools stop being enough

CSS transitions, keyframes, and WAAPI (Web Animations API, articles 02-03) cover the large majority of interface animation. They should stay your default choice. But some problems can't be expressed declaratively at all, because they have no fixed "from" and "to" at the moment they start:

```txt
- Continuous simulation: physics (gravity, collisions, cursor
  inertia)
- A value that depends on several live sources at once: cursor
  position + scroll velocity + time — these can't be described
  as keyframes ahead of time, because the combination changes
  every frame
- An animation that needs to be interrupted mid-flight and
  continue from its current velocity in a new direction — not
  play out along a pre-defined curve to completion
- Real-time interaction: a drag that keeps momentum after
  release, where the final trajectory depends on the gesture's
  velocity at the moment of release, known only at runtime
```

These cases need full control over what happens every single frame. That's `requestAnimationFrame` (rAF).

One limit is worth stating right away: rAF-driven animation is main-thread work, see [Rendering Pipeline and Frame Budget](./01-rendering-pipeline-and-frame-budget.md). Unlike CSS and WAAPI on the compositor, it is never "free". It is the first thing to suffer when the main thread gets overloaded. Choosing it is a deliberate trade for control, not an upgrade to a "more powerful" tool.

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

The rAF callback runs **before** the Style/Layout/Paint stage of the current frame. It is synced to the display's refresh rate (vsync): exactly once per frame, not "as often as possible."

That is a fundamental difference from `setInterval(fn, 16)`, which has no connection to the actual rendering cycle at all:

- It can fire in the middle of an already-running render stage. A style change then lands only in the **next** frame, not the current one — a wasted call.
- It can accumulate drift over time.
- It isn't aligned with the display's refresh rate, and that rate differs from screen to screen: 60 Hz, 120 Hz, 144 Hz.

A key practical detail: **in background tabs, `requestAnimationFrame` gets throttled or fully suspended by the browser.** Typically it drops to about once per second, or stops entirely. That saves processor time and battery for animations the user physically can't see.

`setInterval`, unlike rAF, keeps ticking in the background. Modern browsers throttle it too, just less aggressively and less predictably. That is another reason to use rAF for animation rather than timers. The browser correctly pauses the animation on its own wherever the user wouldn't see it anyway.

```javascript
const id = requestAnimationFrame(tick);
cancelAnimationFrame(id); // stop the scheduled call — must be done when
                          // a component unmounts / an element is removed,
                          // otherwise the callback keeps running and tries
                          // to touch DOM that no longer exists
```

## The canonical rAF loop with delta time — and why leaving it out breaks on 120 Hz

The most common mistake in JS animation written by hand is moving a value by a fixed step **per frame**, not **per unit of time**:

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
// The exact same code moves twice as fast on the higher-refresh
// display — a bug that's hard to catch locally if the developer
// only has a standard 60 Hz monitor
```

The fix is to track **delta time**, the time elapsed since the last frame. Scale the movement step by it, and express speed in units **per second**, not units **per frame**:

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
// A different number of smaller steps, the same final speed.
```

This isn't a theoretical footnote for completeness. It is a real source of bug reports: "it's smooth on my Mac. But on the tester's 144 Hz gaming laptop the animation runs 2.4x too fast and finishes way earlier than it should."

## Interpolation and normalized progress

Practically every time-based JS animation uses the same formula. Normalize elapsed time into `[0, 1]`. Apply an easing function to that normalized `t`. Then interpolate between the start and end value based on the result:

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

`from + (to - from) * t` is `lerp` (linear interpolation). It is the primitive that all time-based animation is built on. The CSS engine does conceptually the same thing internally, just on the compositor, without any JS code of yours running per frame.

## Easing as a pure function of `t`

An easing function is, mathematically, just `f(t): [0,1] → ℝ`. Usually it maps into `[0,1]`, though not necessarily: overshoot is allowed, exactly as with `cubic-bezier()` in article 02. Unlike `cubic-bezier()`, JS easing isn't limited to a cubic Bézier curve. You can implement anything: bounce, elastic, stepped effects.

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

The practical interview takeaway: `cubic-bezier()` and a JS easing function solve the exact same mathematical problem, `t → progress`. They differ only in level. The declarative level is CSS, limited to the shape of a Bézier curve, with `linear()` covering the trickier cases (article 02). The imperative level is JS: an arbitrary formula, always at the cost of main-thread work.

## Springs and damping: the physical alternative to duration

Every example above shares one thing: a fixed **duration** set up front. That works well for "open → closed" transitions with known endpoints. It works poorly for interactive animation. There, motion starts with an already-nonzero velocity — say, the user threw an element after dragging it. Or it needs to be interrupted mid-flight with a new target.

Spring animation doesn't model "progress over time". It models a physical mass-spring-damper system. A spring pulls the current value toward the target with force proportional to the distance. A damper dissipates that force proportional to velocity. Such a system has **no fixed duration**: it stops on its own once velocity and distance from the target become negligibly small:

```javascript
function springStep(
  current, velocity, target,
  { stiffness = 170, damping = 26, mass = 1 },
  dt,
) {
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

Why this "feels more natural" isn't a matter of taste. It follows directly from the model: real-world objects don't move on a pre-scheduled timeline, they react to forces in the present moment.

And that is exactly why springs can be interrupted where duration-based animation cannot. A spring's state is `(current value, current velocity)`, not `(t within a fixed duration)`. Changing the `target` mid-flight is trivial: the physics recomputes a new trajectory that preserves the current velocity, with no visible "jump":

```javascript
// The user moves the mouse — the target changes every frame,
// and the spring keeps moving smoothly, with no animation restart
let springTarget = 0;
document.addEventListener('mousemove', (e) => { springTarget = e.clientX; });
// animateSpring(...) reads springTarget on every step instead of a fixed `to`
```

This is the core reason modern interface toolkits (iOS, Framer Motion, react-spring, Motion.dev) default to springs for interactive elements that can be interrupted. For non-clickable, "plays once" transitions they default to duration plus easing.

## Lerp smoothing for cursors and parallax — and a hidden frame-rate trap

A common pattern is "smoothly following" a target. Two examples: a custom cursor lagging behind the real mouse pointer, or a parallax layer that smooths out abrupt scroll jumps:

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

This is the same class of problem as "px += 2 per frame" above, just more hidden. The code looks time-independent already. But the decay factor `0.1` is implicitly tied to how often the callback runs. The correct formula is exponential decay, corrected for the actual `dt`:

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

This detail rarely shows up in tutorials. Its absence is exactly why the cursor blob "feels different on the 60 Hz demo monitor than on a ProMotion 120 Hz MacBook". The code, though, is nominally the same.

## FLIP: turning an expensive layout animation into a cheap transform animation

The classic problem: list items get reordered by sorting, drag-and-drop or filtering. Their position in the DOM (document object model — the browser's tree of page elements) changes instantly.

The only obvious way to animate that is animating `top`, `left`, `grid-row` and similar properties. Those trigger Layout every single frame (article 01), so the approach doesn't scale to lists of even a few dozen items without visible jank.

**FLIP** (First → Last → Invert → Play) is a technique that sidesteps the problem entirely, reducing the animation to `transform` alone:

```txt
First  — before the DOM change: measure the element's current
          position (getBoundingClientRect())
Last   — apply the DOM change (the actual reorder or layout
          shift). The browser instantly places the element in
          its new position, with no animation. Measure that
          new position
Invert — compute the delta between First and Last, then
          immediately apply a transform that compensates for
          it. Visually the element looks like it is still in
          its old spot, even though in layout it is already
          in the new one
Play   — enable a transition on transform and clear the
          compensating transform. The element smoothly
          "travels" from its old visual position to its true
          new one, and the whole animation is a pure
          compositor transform, with zero reflow per frame
```

A step-by-step implementation for a reorderable list:

```javascript
function flipReorder(container, reorderFn) {
  const items = [...container.children];

  // FIRST — capture positions before the DOM change
  const firstRects = new Map(items.map((el) => [el, el.getBoundingClientRect()]));

  // (the actual DOM change — e.g. re-sorting based on data)
  reorderFn();

  // LAST — capture positions after the DOM change
  items.forEach((el) => {
    const first = firstRects.get(el);
    const last = el.getBoundingClientRect();

    const deltaX = first.left - last.left;
    const deltaY = first.top - last.top;

    if (deltaX === 0 && deltaY === 0) return; // element didn't move — skip it

    // INVERT — compensate for the difference via transform, no transition
    el.style.transition = 'none';
    el.style.transform = `translate(${deltaX}px, ${deltaY}px)`;

    // Force layout once so the browser commits the inverted state
    // before we turn the transition on
    el.getBoundingClientRect();

    // PLAY — enable the transition and clear the compensation
    el.style.transition = 'transform 0.3s ease';
    el.style.transform = '';
  });
}
```

This is exactly the mechanism behind `react-flip-toolkit` and Framer Motion's layout animations (the `layout` prop, article 05). They automate precisely these four steps. The developer no longer keeps the before/after `getBoundingClientRect()` bookkeeping or the re-render synchronization by hand.

Understanding FLIP step by step is what separates two answers. One is "I use a library with layout animations". The other is "I understand **why** they work at all, and why this isn't literally animating layout.

## `requestIdleCallback`: not for animation — for the work that shouldn't compete with it

`requestIdleCallback` (rIC) schedules a callback to run during the browser's spare time between frames. That means: there is slack before the next frame is due, and the main thread isn't busy with anything urgent:

```javascript
function drainQueue(deadline) {
  while (deadline.timeRemaining() > 0 && tasksQueue.length > 0) {
    processTask(tasksQueue.shift());
  }
  // a named function, because an arrow has no `arguments` and
  // `arguments.callee` throws in strict mode and in modules
  if (tasksQueue.length > 0) requestIdleCallback(drainQueue);
}

requestIdleCallback(drainQueue);
```

The key mistake is trying to use `rIC` for animation. It has **no guarantee about frequency or timing**: the callback can be deferred indefinitely if the main thread stays busy. It also has no connection to the display's refresh rate at all.

`rIC` is a tool for background, non-urgent work: batching analytics, warming a cache, prefetching data, lazy initialization. Those are things that should happen "whenever there's a spare moment," not "exactly on the next frame."

### When it's better not to animate at all

Part of doing JS animation professionally is not running it where it isn't needed:

```javascript
// Pause the rAF loop when the element is outside the viewport —
// there's no point spending processor time or battery on an
// animation nobody can see
const observer = new IntersectionObserver(([entry]) => {
  if (entry.isIntersecting) startAnimationLoop();
  else stopAnimationLoop();
});
observer.observe(element);
```

This is the same principle behind the browser pausing rAF in background tabs, just applied by hand to individual elements within the page itself. The `prefers-reduced-motion` query is another reason to skip or tone down an animation, and article 07 covers it in detail.

## Connection to other articles

- [Rendering Pipeline and Frame Budget](./01-rendering-pipeline-and-frame-budget.md) — why rAF-driven animation is main-thread work, and how the frame budget limits what fits in a single tick.
- [Web Animations API](./03-web-animations-api.md) — WAAPI handles most of what used to need an rAF loop written by hand. And it does so without costing the main thread every frame.
- [Animation Libraries and the Ecosystem](./05-animation-libraries-and-ecosystem.md) — GSAP (GreenSock Animation Platform) and Framer Motion implement exactly the springs and FLIP from this article. They do it behind a ready-made API, with react-spring under the hood.
- [Performance Debugging and Jank Hunting](./06-performance-debugging-and-jank-hunting.md) — how to see in DevTools that an rAF callback isn't fitting inside the frame budget.

## Common interview traps

- **Moving a value by a fixed step per frame instead of per unit of time.** Not realizing such code runs at different speeds on 60 Hz versus 120/144 Hz displays. Not knowing delta time as the standard fix.

- **Confusing `requestAnimationFrame` with `setInterval`/`setTimeout`.** Not knowing rAF is synced to the display's refresh rate and automatically pauses in background tabs, while timers do neither.

- **Treating spring animation as "just another easing curve".** Not understanding it has no fixed duration at all. That is precisely why a spring can be interrupted mid-flight with no visible jump, unlike duration-based animation.

- **Not knowing about the naive lerp frame-rate bug.** Using `current += (target - current) * 0.1` with no `dt` correction, and not realizing the convergence speed is implicitly tied to frame rate.

- **Being unable to walk through FLIP step by step.** Knowing the technique's name, or a library that uses it, but not being able to unpack First/Last/Invert/Play. And not being able to explain why the actual animation ends up on `transform`, not on a layout property.

- **Suggesting `requestIdleCallback` for animation.** Not knowing it has no timing guarantees and isn't synced to the render frame. That makes it fundamentally unsuitable for visual animation: it is for background, non-urgent work only.

- **Not pausing off-screen rAF loops.** Never considering that an infinite `requestAnimationFrame` loop on an invisible element keeps burning processor time and battery for nothing. Something has to stop it — an `IntersectionObserver`, or a similar mechanism.
