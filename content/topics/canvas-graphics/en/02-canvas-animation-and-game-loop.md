# Canvas Animation and the Game Loop

## From a static drawing to a living canvas

Article 01 covered why canvas is immediate-mode: the pixels it draws remember nothing about themselves. The direct consequence is that canvas animation can't work like "change a property, the browser repaints it" (the way CSS/WAAPI does — see [rAF and JS-Driven Animation]). The only way to show motion is to **erase the previous frame and draw a new one from scratch**, many times a second.

The canonical delta-time loop built on `requestAnimationFrame` was already covered in [rAF and JS-Driven Animation] — there, it exists to move a SINGLE value independent of display refresh rate. Here, the same loop becomes a **game loop**: instead of a single value, you have an entire world's state (positions, velocities, score, collisions), and instead of "animate a transition," you're "simulate and render the current moment of that simulation."

```javascript
let previousTimestamp;
function loop(timestamp) {
  if (previousTimestamp === undefined) previousTimestamp = timestamp;
  const dt = (timestamp - previousTimestamp) / 1000; // seconds, same as the rAF article
  previousTimestamp = timestamp;

  update(dt);                                  // change the world's state
  ctx.clearRect(0, 0, canvas.width, canvas.height); // erase the previous frame
  draw(ctx);                                    // redraw the world's state

  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
```

Separating `update` from `draw` isn't a stylistic preference: `update` is pure logic (numbers, physics, game rules) that has no idea `ctx` even exists, and can be tested with an ordinary unit test with no canvas involved at all (article 08 covers this in more depth); `draw` is the only place that touches `ctx`, and it contains no decision-making logic — just rendering whatever state has already been computed.

## Fixed timestep vs. variable timestep

An ordinary delta-time loop (like the one above) is a **variable timestep**: `dt` is different every frame, driven by the actual frame rate. That's fine for animating a single visual value. For **physics and game logic**, it's a source of real problems:

```txt
The problem with variable timestep for physics:
  - On a spike in dt (a lag stutter, a tab switch, weak hardware), a
    fast-moving object can "skip through" an obstacle in one large
    step — the collision simply never gets noticed (the "tunneling"
    effect)
  - The exact same game level physically behaves DIFFERENTLY across
    devices, even with identical code — because the velocity
    integration step is different at different dt values (numerical
    integration error accumulates differently depending on step size)
  - Reproducibility (replays, deterministic tests) becomes impossible
    — the simulation's result depends on exactly HOW frames happened
    to be distributed over time
```

The fix is **fixed timestep with an accumulator**: physics always steps forward in identical, small chunks of time, regardless of the actual frame rate; whatever leftover time accumulates between physics steps is used to interpolate the visual position between the last two physics states:

```javascript
const FIXED_DT = 1 / 60; // physics always steps by 1/60 of a second
let accumulator = 0;
let previousState = {};
let currentState = {};

function loop(timestamp) {
  if (previousTimestamp === undefined) previousTimestamp = timestamp;
  let frameTime = (timestamp - previousTimestamp) / 1000;
  previousTimestamp = timestamp;

  frameTime = Math.min(frameTime, 0.25); // guard against the "spiral of death" —
                                          // if a frame was ABNORMALLY long
                                          // (the tab was backgrounded), don't try
                                          // to catch up hundreds of physics steps at once

  accumulator += frameTime;

  while (accumulator >= FIXED_DT) {
    previousState = { ...currentState };
    updatePhysics(currentState, FIXED_DT); // ALWAYS the same step size
    accumulator -= FIXED_DT;
  }

  const alpha = accumulator / FIXED_DT; // how much is "left over" between steps, 0..1
  const renderState = interpolate(previousState, currentState, alpha);

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  draw(ctx, renderState); // draw the INTERMEDIATE, smoothed state

  requestAnimationFrame(loop);
}
```

The practical payoff: physics becomes deterministic and identical across devices, and interpolation (`alpha`) removes the visual "stepping" that would otherwise show up if rendering happened exactly on physics steps (`FIXED_DT` may not line up with the display's refresh rate). For casual browser games and most demo effects, an honest variable timestep is entirely sufficient — fixed timestep earns its place when there's real collision physics, competitive game logic, or reproducibility is a hard requirement.

## The entity pattern: minimal architecture

The simplest architecture that actually works for canvas animation with many objects is a flat array of entities, each with its own `update`/`draw`:

```javascript
class Ball {
  constructor(x, y, vx, vy, radius) {
    Object.assign(this, { x, y, vx, vy, radius });
  }

  update(dt) {
    this.x += this.vx * dt;
    this.y += this.vy * dt;
    if (this.x - this.radius < 0 || this.x + this.radius > canvas.width) this.vx *= -1;
    if (this.y - this.radius < 0 || this.y + this.radius > canvas.height) this.vy *= -1;
  }

  draw(ctx) {
    ctx.beginPath();
    ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
    ctx.fill();
  }
}

const entities = [new Ball(100, 100, 150, 200, 12), new Ball(300, 200, -100, 180, 8)];

function update(dt) { entities.forEach((e) => e.update(dt)); }
function draw(ctx) { entities.forEach((e) => e.draw(ctx)); }
```

This is NOT a retained-mode scene like Pixi or three.js (articles 05-06) — the entity array isn't a structure canvas itself "knows about" and can selectively repaint; these are just ordinary JS objects that you iterate over and redraw every single frame, entirely relying on article 01's immediate-mode model.

## Layered canvases: the cheapest big optimization

If part of a scene is static (a background, decorative elements, a UI frame) and doesn't change every frame, redrawing it alongside dynamic content is pure wasted CPU. The fix is stacking several `<canvas>` elements on top of each other via CSS:

```html
<div style="position: relative; width: 800px; height: 600px;">
  <canvas id="background" style="position: absolute; inset: 0;"></canvas>
  <canvas id="foreground" style="position: absolute; inset: 0;"></canvas>
</div>
```

```javascript
// The background is drawn ONCE, outside the game loop
const bgCtx = document.getElementById('background').getContext('2d');
drawStaticBackground(bgCtx); // gradient, stars, decoration — computed once

// The game loop only touches the foreground
const fgCtx = document.getElementById('foreground').getContext('2d');
function loop(timestamp) {
  // ...
  fgCtx.clearRect(0, 0, canvas.width, canvas.height);
  draw(fgCtx); // dynamic entities only
  requestAnimationFrame(loop);
}
```

The effect is especially noticeable when the static background is itself expensive to draw (a complex gradient, hundreds of decorative elements) — without splitting into layers, that cost gets paid EVERY frame for nothing, even though it only genuinely needs to be computed once.

## Sprite sheets and `drawImage`'s 9-argument form

A sprite sheet is a single image containing several animation frames laid out in a grid. `drawImage`'s full form lets you crop an arbitrary rectangle FROM the source image and paste it at an arbitrary position AND size on the canvas:

```javascript
ctx.drawImage(
  image,
  sx, sy, sWidth, sHeight, // where to crop FROM the source image
  dx, dy, dWidth, dHeight, // where to paste it, and at what size, ON THE CANVAS
);
```

```javascript
// Frame-by-frame character animation from an 8-frame sprite sheet, 64×64px each, in a row
const FRAME_WIDTH = 64;
const FRAME_HEIGHT = 64;
let currentFrame = 0;
let frameTimer = 0;
const FRAME_DURATION = 0.1; // seconds per frame

function update(dt) {
  frameTimer += dt;
  if (frameTimer >= FRAME_DURATION) {
    frameTimer -= FRAME_DURATION;
    currentFrame = (currentFrame + 1) % 8;
  }
}

function draw(ctx) {
  ctx.drawImage(
    spriteSheet,
    currentFrame * FRAME_WIDTH, 0, FRAME_WIDTH, FRAME_HEIGHT, // crop the i-th frame
    playerX, playerY, FRAME_WIDTH, FRAME_HEIGHT,               // paste at the player's position
  );
}
```

One sprite sheet plus a computed `sx` from a frame index is the standard 2D game pattern, avoiding a separate `<img>`/load for every animation frame.

## Hit detection: three approaches

**Math-based (AABB/circle)** — the cheapest and by far the most common in real code:

```javascript
function pointInRect(px, py, rect) {
  return px >= rect.x && px <= rect.x + rect.width &&
         py >= rect.y && py <= rect.y + rect.height;
}

function pointInCircle(px, py, circle) {
  const dx = px - circle.x, dy = py - circle.y;
  return dx * dx + dy * dy <= circle.radius * circle.radius; // no sqrt — cheaper
}
```

**`isPointInPath()`/`isPointInStroke()`** — ask the context itself whether a point falls inside an accumulated path, with no manual geometry:

```javascript
ctx.beginPath();
ctx.arc(150, 100, 50, 0, Math.PI * 2);
// WITHOUT calling fill()/stroke() — just a hit test against the path
const isHit = ctx.isPointInPath(clickX, clickY);
```

Convenient for irregular/complex shapes that are already described as a canvas path and that you'd rather not duplicate with a separate math model.

**Color-picking on a hidden canvas** — solves hit-testing for COMPLEX, overlapping, arbitrarily irregular shapes exactly, with no math at all: every interactive object is drawn onto an invisible offscreen canvas in a solid, unique color (no anti-aliasing!), and clicking reads the pixel color under the cursor:

```javascript
const hitCanvas = document.createElement('canvas');
hitCanvas.width = canvas.width; hitCanvas.height = canvas.height;
const hitCtx = hitCanvas.getContext('2d', { willReadFrequently: true });
hitCtx.imageSmoothingEnabled = false; // REQUIRED: anti-aliasing would blend colors at edges

const colorToEntity = new Map();
entities.forEach((entity, i) => {
  const color = `rgb(${(i + 1) & 255}, 0, 0)`; // a unique "id color" per object
  colorToEntity.set(color, entity);
  hitCtx.fillStyle = color;
  entity.drawHitShape(hitCtx); // the same geometry as drawing, but in one flat color
});

canvas.addEventListener('click', (e) => {
  const pixel = hitCtx.getImageData(e.offsetX, e.offsetY, 1, 1).data;
  const color = `rgb(${pixel[0]}, ${pixel[1]}, ${pixel[2]})`;
  const clickedEntity = colorToEntity.get(color);
});
```

This works exactly, for any shape (stars, arbitrary polygons, objects overlapping each other), at the cost of an extra offscreen render pass on every scene change — the details of working with pixels (`getImageData`, its cost) are covered in article 03.

## Pausing when the tab is backgrounded

The browser already throttles/suspends `requestAnimationFrame` in background tabs (see [rAF and JS-Driven Animation]), but that alone isn't enough for game logic: if only rendering is paused while a physics accumulator keeps piling up `dt` (or reads `Date.now()` directly), `frameTime` will be enormous when the tab comes back — without a clamp (`Math.min(frameTime, 0.25)` from the fixed-timestep example above), the simulation will try to catch up hours or even days of skipped time in a single frame.

```javascript
let isPaused = false;
document.addEventListener('visibilitychange', () => {
  isPaused = document.hidden;
  if (!isPaused) previousTimestamp = undefined; // reset the dt reference point
                                                  // so we don't get a huge
                                                  // first dt after returning
});

function loop(timestamp) {
  if (isPaused) { requestAnimationFrame(loop); return; }
  // ...normal update/draw logic
  requestAnimationFrame(loop);
}
```

## Putting it all together: a minimal Pong

```javascript
const canvas = document.querySelector('canvas');
const ctx = canvas.getContext('2d');

const ball = { x: 400, y: 300, vx: 240, vy: 180, radius: 8 };
const paddle = { x: 20, y: 250, width: 12, height: 100, vy: 0 };
let score = 0;

function update(dt) {
  ball.x += ball.vx * dt;
  ball.y += ball.vy * dt;

  if (ball.y - ball.radius < 0 || ball.y + ball.radius > canvas.height) ball.vy *= -1;
  if (ball.x + ball.radius > canvas.width) ball.vx *= -1; // bounce off the right wall

  paddle.y += paddle.vy * dt;

  // AABB collision check between the ball and the paddle (math-based hit detection)
  const hitsPaddle =
    ball.x - ball.radius < paddle.x + paddle.width &&
    ball.x + ball.radius > paddle.x &&
    ball.y > paddle.y && ball.y < paddle.y + paddle.height;

  if (hitsPaddle && ball.vx < 0) {
    ball.vx *= -1;
    score += 1;
  } else if (ball.x - ball.radius < 0) {
    ball.x = 400; ball.y = 300; score = 0; // missed the paddle — reset
  }
}

function draw(ctx) {
  ctx.fillStyle = '#111';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.fillStyle = 'white';
  ctx.fillRect(paddle.x, paddle.y, paddle.width, paddle.height);

  ctx.beginPath();
  ctx.arc(ball.x, ball.y, ball.radius, 0, Math.PI * 2);
  ctx.fill();

  ctx.font = '20px monospace';
  ctx.fillText(`Score: ${score}`, canvas.width - 140, 30);
}

let previousTimestamp;
function loop(timestamp) {
  if (previousTimestamp === undefined) previousTimestamp = timestamp;
  const dt = (timestamp - previousTimestamp) / 1000;
  previousTimestamp = timestamp;

  update(dt);
  draw(ctx); // the background fillRect doubles as both the background and the clear
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
```

This example is deliberately small, but it brings together every piece covered in this article: separating `update`/`draw`, the delta-time loop, an entity-like data structure (`ball`, `paddle` as plain objects), math-based hit detection (AABB for the paddle) — exactly what any browser game or interactive canvas feature actually starts from.

## Connection to other articles

```txt
[Canvas 2D Fundamentals]                — the immediate-mode model that
                                           makes the explicit clear→
                                           update→draw cycle mandatory
[rAF and JS-Driven Animation]           — the base delta-time rAF loop,
                                           extended here into a full
                                           stateful game loop
[Pixels, Images, and Effects]           — the pixel-level work behind
                                           the color-picking hit
                                           detection approach
[Architecture and Performance for
 Canvas Apps]                            — object pooling, dirty
                                           rectangles, and other
                                           optimizations built on top of
                                           this loop in a real production app
```

## Common interview traps

- **Not separating `update` and `draw`** — writing a single function that both mutates state and draws, making the logic untestable without a canvas and making it harder to add fixed timestep later.

- **Not knowing the difference between fixed and variable timestep** — being unable to explain why physics under variable timestep can behave differently across devices, or what "tunneling" means when `dt` spikes.

- **Not clamping `dt` after a lag spike or a backgrounded tab** — failing to anticipate the "spiral of death": if the real `frameTime` isn't capped, the simulation tries to catch up an enormous span of time in a single frame after returning to the tab, making the lag worse instead of better.

- **Redrawing a static background every frame** — not knowing about layered canvases as the cheapest optimization, and instead trying to "optimize" the static background's own drawing code.

- **Using only math-based hit detection where shapes are complex and overlapping** — not knowing about color-picking on a hidden canvas as an exact alternative to hand-writing intersection geometry for arbitrary polygons.

- **Relying only on the browser's background rAF throttling** — not realizing that pausing GAME logic (timers, physics) needs to be handled explicitly via `visibilitychange`, rather than assuming the browser slowing down rendering is enough on its own.
