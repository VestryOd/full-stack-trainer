# Canvas 2D Fundamentals

## Immediate mode: the core mindset shift

Canvas forgets every shape the moment it is drawn. Maybe you're coming from the DOM (document object model, the tree of page objects in the browser), or from SVG (scalable vector graphics). Then you have a reflex: create an element, and it exists, so you can find it later and change it. That reflex does not work here.

Both DOM and SVG are **retained-mode** systems. The browser keeps a structure of objects: a tree of DOM nodes, or a tree of `<circle>`/`<rect>` elements. When you change `element.style.left`, the browser figures out what to repaint on its own. The topic Browser Animation covers that side in detail.

Canvas works on a fundamentally different model. It is an **immediate-mode** system: draw it and forget it. Calling `ctx.fillRect(10, 10, 50, 50)` colors pixels right now, and remembers nothing about there having been a "rectangle" here.

A moment later, as far as canvas is concerned, those are just colored pixels in a buffer. They are indistinguishable from any other colored pixels. There is no object you can tell to move 10px to the right. The only way to change anything is to **redraw it entirely**, or at least the part that changed.

| DOM/SVG (retained mode) | Canvas (immediate mode) |
|---|---|
| `el.style.left = '110px'` | `ctx.clearRect(...)`, then `ctx.fillRect(110, 10, 50, 50)` |
| The browser repaints only what's necessary, on its own. | You decide what to redraw, and when. |

This isn't a syntax detail. It explains why the whole architecture of canvas applications is built around a "clear → update state → redraw" loop. Mutating existing objects is not on the menu. Articles 02 and 08 build on that loop.

## `getContext('2d')` and the context as a state machine

```javascript
const canvas = document.querySelector('canvas');
const ctx = canvas.getContext('2d');
```

`ctx` isn't just a bag of drawing functions. It's a **state machine**. It holds current values that persist across calls until you explicitly change them: `fillStyle`, `strokeStyle`, `lineWidth`, the current transform, the clip region. Think of a pen that has a current color and thickness, and keeps drawing with them until you dip it in something else.

```javascript
ctx.fillStyle = 'red';
ctx.fillRect(0, 0, 50, 50);   // a red square
ctx.fillRect(60, 0, 50, 50);  // also red — fillStyle doesn't reset on its own
ctx.fillStyle = 'blue';
ctx.fillRect(120, 0, 50, 50); // now blue
```

`getContext('2d')` on the same `<canvas>` element always returns the same context object. Calling it doesn't create a new one each time. That makes it safe to cache `ctx` in a variable during component setup.

## The coordinate system

The origin is the top-left corner. X grows to the right, and Y grows **downward**. In math Y grows upward, so formulas copied straight from a physics textbook need their sign flipped. Skipping that flip is a common source of errors.

A subtlety almost nobody thinks about until they hit it: thin lines (`lineWidth: 1`) drawn at **whole-number** coordinates look blurry. A 1px line is drawn "centered" on the coordinate, so it bleeds half a pixel to either side. That lands it right on the boundary between two physical pixels. The classic fix is to offset line coordinates by 0.5px:

```javascript
// ❌ A blurry line — straddles the boundary between pixels 100 and 101
ctx.moveTo(100, 0);
ctx.lineTo(100, 200);

// ✅ A crisp, one-physical-pixel-wide line
ctx.moveTo(100.5, 0);
ctx.lineTo(100.5, 200);
```

## Drawing primitives

### Rectangles — no path needed

```javascript
ctx.fillRect(x, y, width, height);   // a filled rectangle, immediately
ctx.strokeRect(x, y, width, height); // an outlined rectangle
ctx.clearRect(x, y, width, height);  // makes the area transparent
```

These are the only primitives that don't need a path — calling them draws right away.

### Paths — the universal mechanism for everything else

```javascript
ctx.beginPath();               // start a new path — clears any accumulated points
ctx.moveTo(50, 50);             // move the "pen" without drawing a line
ctx.lineTo(150, 50);            // a line to this point
// an arc: center, radius, startAngle, endAngle, [anticlockwise]
ctx.arc(150, 100, 50, 0, Math.PI * 2);
// a quadratic Bézier curve (one control point)
ctx.quadraticCurveTo(200, 150, 250, 50);
// a cubic Bézier curve (two control points)
ctx.bezierCurveTo(260, 0, 300, 0, 320, 50);
ctx.closePath();               // close the path with a line back to the starting point

ctx.fill();   // fill the accumulated path
ctx.stroke(); // stroke the accumulated path
```

Forgetting `beginPath()` before a new shape is a common source of "why is everything a mess" bugs. Previous points are **not** reset automatically: `moveTo`/`lineTo` keep accumulating into the same path. Then `fill()`/`stroke()` cover **everything** accumulated since the start, including shapes from previous frames.

### The fill rule: nonzero vs. evenodd

When a path self-intersects or contains multiple sub-contours (say, a circle inside a circle — a "donut"), the browser has to decide which regions get colored. The default rule is `nonzero`. For each point it counts how many times the contour "winds" around it, taking direction into account. If that count isn't zero, the point gets filled.

```javascript
// A "donut": the outer circle clockwise, the inner one
// counterclockwise — opposite directions, so the nonzero rule
// gives a winding count of 0 inside the inner circle → a hole
ctx.beginPath();
ctx.arc(100, 100, 80, 0, Math.PI * 2, false); // outer, clockwise
ctx.arc(100, 100, 40, 0, Math.PI * 2, true);  // inner, counterclockwise
ctx.fill(); // 'nonzero' — the default, gives a correct donut with a hole

ctx.fill('evenodd'); // an alternative rule — just counts the parity of
                      // ray-contour intersections, ignoring direction
```

The practical takeaway: if a "donut" suddenly renders as a solid circle with no hole, both contours were almost certainly wound in the same direction. Both clockwise means they never cancel out under the default `nonzero` rule. Flip one contour's direction via `arc()`'s `anticlockwise` parameter, or call `fill('evenodd')` explicitly.

## Styles: `fillStyle` is more than a color

```javascript
// A color
ctx.fillStyle = '#3366ff';

// A linear gradient
const gradient = ctx.createLinearGradient(0, 0, 200, 0); // x0,y0 → x1,y1
gradient.addColorStop(0, 'red');
gradient.addColorStop(1, 'blue');
ctx.fillStyle = gradient;

// A radial gradient — two circles (inner → outer)
const radial = ctx.createRadialGradient(100, 100, 0, 100, 100, 80);
radial.addColorStop(0, 'white');
radial.addColorStop(1, 'transparent');

// A pattern from an image
const pattern = ctx.createPattern(imageElement, 'repeat');
ctx.fillStyle = pattern;
```

Line styles:

```javascript
ctx.lineWidth = 4;
ctx.lineCap = 'round';   // 'butt' | 'round' | 'square' — the end of a line
ctx.lineJoin = 'round';  // 'miter' | 'round' | 'bevel' — the corner between segments
ctx.setLineDash([8, 4]); // a dashed line: 8px segment, 4px gap
```

## Transforms: order matters

`translate`, `rotate`, and `scale` don't set an absolute state. They **multiply** the current transformation matrix by a new one. Matrix multiplication isn't commutative, so `translate → rotate` and `rotate → translate` give different results.

```javascript
// ❌ Rotates around the origin (0,0), not around the shape's own
// center — the shape "flies" around in a circle instead of
// spinning in place
ctx.rotate(angle);
ctx.fillRect(centerX - 25, centerY - 25, 50, 50);
```

```javascript
// ✅ The classic "rotate around a point" pattern: shift the
// coordinate system to the pivot point → rotate → draw in local
// coordinates relative to (0,0)
ctx.translate(centerX, centerY);
ctx.rotate(angle);
ctx.fillRect(-25, -25, 50, 50); // drawn relative to the new (0,0)
```

The order of calls reads "backward" relative to intuition. Writing `translate` and then `rotate` means: first move the coordinate system, then rotate the already-moved one. That is exactly what produces rotation around the new point instead of around the original origin.

`setTransform(a, b, c, d, e, f)` sets an **absolute** matrix instead of compounding onto the current one. Use it when you need to know the exact resulting state without relying on the history of calls. `resetTransform()` resets to the identity matrix.

## The state stack: `save()`/`restore()` — and the classic leak

`save()` pushes a snapshot of the **current** styles and transform onto a stack. The current path is **not** part of that snapshot. `restore()` pops the top snapshot off the stack and reverts state to it.

```javascript
// ❌ A leaked transform: rotate() and fillStyle stay in effect
// for all subsequent shapes in this frame — the classic
// "why is the next element rotated / the wrong color" bug
function drawRotatedIcon(ctx, x, y, angle) {
  ctx.translate(x, y);
  ctx.rotate(angle);
  ctx.fillStyle = 'red';
  ctx.fillRect(-10, -10, 20, 20);
  // No restore() — the transform and fillStyle "leak" into the rest of the code
}
```

```javascript
// ✅ save()/restore() strictly isolate state changes to the scope
// of a single shape
function drawRotatedIcon(ctx, x, y, angle) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(angle);
  ctx.fillStyle = 'red';
  ctx.fillRect(-10, -10, 20, 20);
  ctx.restore(); // reverts the transform and fillStyle to their state before this function
}
```

The team rule: wrap any drawing function in `save()`/`restore()` if it changes the transform or styles and gets called in a loop. Otherwise, by the third element, the list of "inherited" distortions becomes unpredictable and hard to debug.

## Text: drawing without automatic layout

```javascript
ctx.font = '16px system-ui'; // the same syntax as CSS's font shorthand
ctx.textAlign = 'center';    // 'left' | 'center' | 'right' — relative to X in fillText
ctx.textBaseline = 'middle'; // 'top' | 'middle' | 'alphabetic' | 'bottom' — relative to Y
ctx.fillText('Score: 100', x, y);
ctx.strokeText('Outlined', x, y);

const metrics = ctx.measureText('Score: 100');
console.log(metrics.width); // the text's width in pixels — the only way
                              // to know whether a string fits, since canvas
                              // doesn't wrap text automatically
```

Unlike the DOM, canvas has no built-in line wrapping, ellipsis, or line-height. Multi-line, word-wrapped text is separate manual logic built on top of `measureText()`. You compute it yourself; the context does not provide it.

## `devicePixelRatio`: reason #1 canvas looks blurry on retina

This is the single detail whose absence breaks about half of all beginner canvas projects. A canvas has **two** independent sizes:

- `canvas.width` / `canvas.height` — the **backing store** size: the actual number of pixels in the buffer you draw into.
- `canvas.style.width` / `canvas.style.height` — the element's size **on the page**, in CSS pixels, like an ordinary DOM element.

If you don't set these separately, they end up equal to the same number of CSS pixels. On a display with `devicePixelRatio: 2` (a typical retina screen), that buffer is too small. The browser stretches, say, 400×300 real pixels to fill 800×600 physical screen pixels. That is an **upscale**, like a small image blown up to a larger size. The result is visible blur, uniformly, across text, lines, and every bit of content.

```javascript
// ❌ A naive setup — blurry on any retina display
canvas.width = 400;
canvas.height = 300;
```

```javascript
// ✅ The canonical, retina-correct setup
function setupCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect(); // the CSS size on the page

  canvas.width = rect.width * dpr;   // the real buffer size — larger than the CSS size
  canvas.height = rect.height * dpr;
  canvas.style.width = `${rect.width}px`;   // the CSS size stays the same —
  canvas.style.height = `${rect.height}px`; // the element doesn't get physically bigger

  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr); // critical: from here on, draw using CSS-pixel
                        // coordinates — the context scales them into the
                        // buffer's real pixels for you
  return ctx;
}
```

After `ctx.scale(dpr, dpr)`, all the rest of your drawing code is written in familiar "logical" coordinates. You call `fillRect(10, 10, 50, 50)` as if `dpr` were 1, and the context scales that into the buffer's real pixels for you. This is the only way to get a crisp picture without rewriting every piece of drawing geometry for a specific `dpr`.

## Clearing strategies

```javascript
ctx.clearRect(0, 0, canvas.width, canvas.height); // ✅ the standard way:
// makes the area transparent, without touching the transform,
// styles, or anything else in the context's state

canvas.width = canvas.width; // ⚠️ an old-code "hack": assigning
// width resets the buffer entirely — not just clearing pixels, but
// also zeroing out the whole transform, styles, and clip region —
// so it's not just clearing, it's a full context reset as a side effect
```

The second variant is sometimes used deliberately, as a way to reset everything at once, including a transform accumulated by accident. More often it is an implicit side effect that catches people out.

If code changes `canvas.width` to handle a resize, as the function above does, that also clears the content and resets the context's state. Remember it explicitly, rather than discovering it as an "inexplicable" bug after a window resize.

## Connection to other articles

- [Canvas Animation and the Game Loop](./02-canvas-animation-and-game-loop.md) — the clear → update → draw cycle that the immediate-mode model makes mandatory, not optional.
- [Pixels, Images, and Effects](./03-pixels-images-and-effects.md) — `ImageData`, compositing, and working with pixels on top of this article's primitives.
- [Architecture and Performance for Canvas Apps](./08-architecture-and-performance-for-canvas-apps.md) — the `save()`/`restore()` discipline and retina-correct setup, scaled into production patterns.

## Common interview traps

- **Being unable to explain immediate vs. retained mode.** Conflating "canvas doesn't store objects" with "canvas is slower than the DOM" mixes up two different claims. Immediate mode can be faster or slower depending on the scenario. The key difference is the state-ownership model, not performance as such.

- **Not knowing why canvas is blurry on retina.** The blur comes from a mismatch between `canvas.width`/`canvas.height` (the buffer) and `canvas.style.width`/`style.height` (the CSS size). Trying to "fix" it with `image-rendering: crisp-edges` in CSS leaves the backing store wrong.

- **Forgetting `beginPath()`.** A path keeps accumulating across calls to `fill()`/`stroke()` unless it is explicitly restarted. The result is a "mess" of shapes from previous frames layered on top of the current one.

- **Not knowing the difference between nonzero and evenodd.** Being unable to explain why a "donut" (a circle with a hole) sometimes renders as a solid circle. The cause is both contours winding in the same direction under the default `nonzero` rule.

- **Not wrapping transforms in `save()`/`restore()`.** Writing a drawing function that changes `rotate`/`translate`/`fillStyle` and gets called in a loop, with no state isolation. It "leaks" into later iterations unpredictably.

- **Confusing `clearRect()` with assigning `canvas.width`.** The latter fully resets the context, transform and styles included, not just the pixels. The surprise is a "disappeared" transform after resizing the canvas.
