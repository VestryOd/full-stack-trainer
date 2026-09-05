# Canvas Animation and the Game Loop

## From a static drawing to a living canvas

Canvas animation means **erasing the previous frame and drawing a new one from scratch**, many times a second. That follows from the immediate-mode model of article 01: the pixels canvas draws remember nothing about themselves.

So canvas animation can't work like "change a property, the browser repaints it". CSS and the Web Animations API (WAAPI) do work that way, and the article rAF and JS-Driven Animation covers them. Canvas does not.

The loop here is a **game loop**: it owns an entire world's state, not one animated value. The canonical delta-time loop on `requestAnimationFrame` was covered in rAF and JS-Driven Animation, where it moves one value independently of the display refresh rate. Here the state is positions, velocities, score and collisions. Instead of animating a transition, you simulate a moment and render it.

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

Separating `update` from `draw` isn't a stylistic preference. `update` is pure logic — numbers, physics, game rules — and has no idea `ctx` even exists. That makes it testable with an ordinary unit test, no canvas involved; article 08 goes deeper. The `draw` function is the only place that touches `ctx`. It makes no decisions, and only renders whatever state has already been computed.

## Fixed timestep vs. variable timestep

An ordinary delta-time loop (like the one above) is a **variable timestep**: `dt` is different every frame, driven by the actual frame rate. That's fine for animating a single visual value. For **physics and game logic**, it's a source of real problems:

- A spike in `dt` (a lag stutter, a tab switch, weak hardware) lets a fast-moving object skip through an obstacle in one large step. The collision is never noticed. This is the "tunneling" effect.
- The same game level behaves **differently** across devices, even with identical code. The velocity integration step differs at different `dt` values, so numerical error accumulates differently.
- Reproducibility (replays, deterministic tests) becomes impossible. The result depends on exactly **how** frames happened to be distributed over time.

The fix is a **fixed timestep with an accumulator**. Physics always steps forward in identical, small chunks of time, regardless of the actual frame rate. Whatever leftover time accumulates between physics steps is used to interpolate the visual position between the last two physics states:

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
                                          // if a frame was abnormally long
                                          // (the tab was backgrounded), don't try
                                          // to catch up hundreds of physics steps at once

  accumulator += frameTime;

  while (accumulator >= FIXED_DT) {
    previousState = { ...currentState };
    updatePhysics(currentState, FIXED_DT); // always the same step size
    accumulator -= FIXED_DT;
  }

  const alpha = accumulator / FIXED_DT; // how much is "left over" between steps, 0..1
  const renderState = interpolate(previousState, currentState, alpha);

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  draw(ctx, renderState); // draw the intermediate, smoothed state

  requestAnimationFrame(loop);
}
```

The practical payoff: physics becomes deterministic and identical across devices. Interpolation (`alpha`) also removes the visual "stepping". Without it, stepping shows up whenever rendering lands exactly on physics steps, and `FIXED_DT` may not line up with the display's refresh rate.

For casual browser games and most demo effects, an honest variable timestep is entirely sufficient. Fixed timestep is worth its cost when you have real collision physics, competitive game logic, or a hard requirement for reproducibility.

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

This is **not** a retained-mode scene like Pixi or three.js (articles 05-06). The entity array isn't a structure canvas itself "knows about" and can selectively repaint. These are ordinary JS objects that you iterate over and redraw every single frame, entirely on top of article 01's immediate-mode model.

## Layered canvases: the cheapest big optimization

If part of a scene is static and doesn't change every frame, redrawing it alongside dynamic content wastes CPU (central processing unit) time. Static here means a background, decorative elements, or a UI (user interface) frame. The fix is stacking several `<canvas>` elements on top of each other via CSS:

```html
<div style="position: relative; width: 800px; height: 600px;">
  <canvas id="background" style="position: absolute; inset: 0;"></canvas>
  <canvas id="foreground" style="position: absolute; inset: 0;"></canvas>
</div>
```

```javascript
// The background is drawn once, outside the game loop
const bgCtx = document.getElementById('background').getContext('2d');
drawStaticBackground(bgCtx); // gradient, stars, decoration — computed once

// The game loop only touches the foreground
const fgCanvas = document.getElementById('foreground');
const fgCtx = fgCanvas.getContext('2d');
function loop(timestamp) {
  // ...
  fgCtx.clearRect(0, 0, fgCanvas.width, fgCanvas.height);
  draw(fgCtx); // dynamic entities only
  requestAnimationFrame(loop);
}
```

The effect is especially noticeable when the static background is itself expensive to draw: a complex gradient, hundreds of decorative elements. Without layers, that cost is paid **every** frame for nothing, even though it only genuinely needs to be computed once.

## Sprite sheets and `drawImage`'s 9-argument form

A sprite sheet is a single image containing several animation frames laid out in a grid. The full form of `drawImage` crops an arbitrary rectangle from the source image. It then pastes that crop onto the canvas at an arbitrary position, and at an arbitrary size:

```javascript
ctx.drawImage(
  image,
  sx, sy, sWidth, sHeight, // where to crop from in the source image
  dx, dy, dWidth, dHeight, // where to paste it on the canvas, and at what size
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
    playerX, playerY, FRAME_WIDTH, FRAME_HEIGHT, // paste at the player's position
  );
}
```

One sprite sheet plus an `sx` computed from the frame index is the standard 2D game pattern. It avoids a separate `<img>` and a separate load for every animation frame.

## Hit detection: three approaches

**Math-based (AABB or circle)** — the cheapest and by far the most common in real code. AABB stands for axis-aligned bounding box, a rectangle whose sides stay parallel to the axes:

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
// without calling fill()/stroke() — just a hit test against the path
const isHit = ctx.isPointInPath(clickX, clickY);
```

Convenient for irregular/complex shapes that are already described as a canvas path and that you'd rather not duplicate with a separate math model.

**Color-picking on a hidden canvas** — solves hit-testing exactly for complex, overlapping, arbitrarily irregular shapes, with no math at all. Every interactive object is drawn onto an invisible offscreen canvas in a solid, unique color, with anti-aliasing switched off. A click then reads the pixel color under the cursor:

```javascript
const hitCanvas = document.createElement('canvas');
hitCanvas.width = canvas.width; hitCanvas.height = canvas.height;
const hitCtx = hitCanvas.getContext('2d', { willReadFrequently: true });
hitCtx.imageSmoothingEnabled = false; // required: anti-aliasing blends colors at edges

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

This works exactly, for any shape: stars, arbitrary polygons, objects overlapping each other. The cost is an extra offscreen render pass on every scene change. Article 03 covers the details of working with pixels, including `getImageData` and what it costs.

## Pausing when the tab is backgrounded

The browser already throttles or suspends `requestAnimationFrame` in background tabs, as rAF and JS-Driven Animation explains. That alone isn't enough for game logic. Rendering may pause while a physics accumulator keeps piling up `dt`, or reads `Date.now()` directly. Then `frameTime` is enormous when the tab comes back.

Without a clamp, the simulation will try to catch up hours or even days of skipped time in a single frame. The clamp is `Math.min(frameTime, 0.25)`, from the fixed-timestep example above.

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

This example is deliberately small, but it brings together every piece covered in the article. It separates `update` and `draw`, runs a delta-time loop, and keeps an entity-like data structure: `ball` and `paddle` as plain objects. Hit detection is math-based, an AABB check for the paddle. That is exactly what any browser game or interactive canvas feature starts from.

## Connection to other articles

- [Canvas 2D Fundamentals](./01-canvas-2d-fundamentals.md) — the immediate-mode model that makes the explicit clear → update → draw cycle mandatory.
- rAF and JS-Driven Animation — the base delta-time `requestAnimationFrame` loop, extended here into a full stateful game loop.
- [Pixels, Images, and Effects](./03-pixels-images-and-effects.md) — the pixel-level work behind the color-picking approach to hit detection.
- [Architecture and Performance for Canvas Apps](./08-architecture-and-performance-for-canvas-apps.md) — object pooling, dirty rectangles, and other optimizations built on top of this loop.

## Common interview traps

- **Not separating `update` and `draw`.** Writing a single function that both mutates state and draws. The logic becomes untestable without a canvas, and adding fixed timestep later gets harder.

- **Not knowing the difference between fixed and variable timestep.** Being unable to explain why physics under variable timestep behaves differently across devices, or what "tunneling" means when `dt` spikes.

- **Not clamping `dt` after a lag spike or a backgrounded tab.** This is the "spiral of death" scenario. Return to the tab with `frameTime` uncapped, and the simulation tries to catch up an enormous span of time in one frame. That makes the lag worse, not better.

- **Redrawing a static background every frame.** Not knowing about layered canvases as the cheapest optimization, and trying to "optimize" the static background's own drawing code instead.

- **Using only math-based hit detection where shapes are complex and overlapping.** Not knowing about color-picking on a hidden canvas as an exact alternative. The manual route is writing intersection geometry for arbitrary polygons by hand.

- **Relying only on the browser's background rAF throttling.** Pausing **game** logic (timers, physics) has to be handled explicitly, via `visibilitychange`. Assuming that slower rendering by the browser is enough on its own does not work.
