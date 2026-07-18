# Canvas 2D Fundamentals

## Immediate mode: the core mindset shift

If you're coming from DOM/SVG (or from [Browser Animation]), you already have a reflex: "create an element → it exists → I can find it later and change it." Both DOM and SVG are **retained-mode** systems: the browser keeps a structure of objects (a tree of DOM nodes, or a tree of `<circle>`/`<rect>` elements), and when you change `element.style.left`, the browser figures out what to repaint on its own.

Canvas works on a fundamentally different model — it's an **immediate-mode** system ("draw it and forget it"): calling `ctx.fillRect(10, 10, 50, 50)` colors pixels right now and remembers nothing about there having been a "rectangle" here. A moment later, as far as canvas is concerned, those are just colored pixels in a buffer — indistinguishable from any other colored pixels. There's no object you can go back to and say "move 10px to the right." The only way to change anything is to **redraw it entirely** (or whatever part changed) from scratch.

```txt
DOM/SVG (retained mode):                Canvas (immediate mode):
  el.style.left = '110px'                 ctx.clearRect(...)       // erase
  → the browser repaints only              ctx.fillRect(110, 10, 50, 50) // redraw
    what's necessary, on its own            → YOU are responsible for
                                               deciding WHAT and WHEN to redraw
```

This isn't a syntax detail — it's the reason the entire architecture of canvas applications (articles 02 and 08) is built around a "clear → update state → redraw" loop, rather than around mutating existing objects.

## `getContext('2d')` and the context as a state machine

```javascript
const canvas = document.querySelector('canvas');
const ctx = canvas.getContext('2d');
```

`ctx` isn't just a bag of drawing functions — it's a **state machine**: it holds current values (`fillStyle`, `strokeStyle`, `lineWidth`, the current transform, the clip region) that persist across calls until you explicitly change them — like a pen that has a current color and thickness, and keeps drawing with them until you dip it in something else.

```javascript
ctx.fillStyle = 'red';
ctx.fillRect(0, 0, 50, 50);   // a red square
ctx.fillRect(60, 0, 50, 50);  // ALSO red — fillStyle doesn't reset on its own
ctx.fillStyle = 'blue';
ctx.fillRect(120, 0, 50, 50); // now blue
```

`getContext('2d')` on the same `<canvas>` element always returns the same context object — calling it doesn't create a new one each time, so it's safe to cache `ctx` in a variable during component setup.

## The coordinate system

The origin is the top-left corner, X grows to the right, Y grows **downward** (unlike math, where Y grows upward — a common source of sign errors when porting formulas straight from a physics textbook without flipping them).

A subtlety almost nobody thinks about until they hit it: thin lines (`lineWidth: 1`) drawn at **whole-number** coordinates look blurry, because a 1px line is drawn "centered" on the coordinate and bleeds half a pixel to either side, landing right on the boundary between two physical pixels. The classic fix is to offset line coordinates by 0.5px:

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
ctx.beginPath();               // start a NEW path — clears any accumulated points
ctx.moveTo(50, 50);             // move the "pen" without drawing a line
ctx.lineTo(150, 50);            // a line to this point
ctx.arc(150, 100, 50, 0, Math.PI * 2); // an arc: center, radius, startAngle, endAngle, [anticlockwise]
ctx.quadraticCurveTo(200, 150, 250, 50); // a quadratic Bézier curve (one control point)
ctx.bezierCurveTo(260, 0, 300, 0, 320, 50); // a cubic Bézier curve (two control points)
ctx.closePath();               // close the path with a line back to the starting point

ctx.fill();   // fill the accumulated path
ctx.stroke(); // stroke the accumulated path
```

Forgetting `beginPath()` before a new shape is a common source of "why is everything a mess" bugs: previous points are NOT reset automatically — `moveTo`/`lineTo` keep accumulating into the same path, and `fill()`/`stroke()` fill/stroke EVERYTHING accumulated since the start, including shapes from previous frames.

### The fill rule: nonzero vs. evenodd

When a path self-intersects or contains multiple sub-contours (say, a circle inside a circle — a "donut"), the browser has to decide which regions get colored. The default rule is `nonzero`: for each point, it counts how many times the contour "winds" around it, taking direction into account; if that count isn't zero, the point gets filled.

```javascript
// A "donut": the outer circle clockwise, the inner one
// COUNTERCLOCKWISE — opposite directions, so the nonzero rule
// gives a winding count of 0 inside the inner circle → a hole
ctx.beginPath();
ctx.arc(100, 100, 80, 0, Math.PI * 2, false); // outer, clockwise
ctx.arc(100, 100, 40, 0, Math.PI * 2, true);  // inner, COUNTERCLOCKWISE
ctx.fill(); // 'nonzero' — the default, gives a correct donut with a hole

ctx.fill('evenodd'); // an alternative rule — just counts the parity of
                      // ray-contour intersections, ignoring direction
```

The practical takeaway: if a "donut" suddenly renders as a solid circle with no hole, it's almost always because both contours were wound in the same direction (both clockwise), so under the default `nonzero` rule they never cancel out — flip one contour's direction via `arc()`'s `anticlockwise` parameter, or explicitly call `fill('evenodd')`.

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
ctx.lineCap = 'round';   // 'butt' | 'round' | 'square' — what a line's END looks like
ctx.lineJoin = 'round';  // 'miter' | 'round' | 'bevel' — what a CORNER between segments looks like
ctx.setLineDash([8, 4]); // a dashed line: 8px segment, 4px gap
```

## Transforms: order matters

`translate`, `rotate`, and `scale` don't set an absolute state — they **multiply** the current transformation matrix by a new one, and matrix multiplication isn't commutative: `translate → rotate` and `rotate → translate` give different results.

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
ctx.fillRect(-25, -25, 50, 50); // drawn RELATIVE to the new (0,0)
```

The order of calls reads "backward" relative to intuition: `translate` followed by `rotate` in code means "first move the coordinate system, THEN rotate the already-moved one" — which is exactly what produces rotation around the new point instead of around the original origin.

`setTransform(a, b, c, d, e, f)` sets an ABSOLUTE matrix instead of compounding onto the current one (useful when you need to know the exact resulting state without relying on the history of calls); `resetTransform()` resets to the identity matrix.

## The state stack: `save()`/`restore()` — and the classic leak

`save()` pushes a snapshot of the CURRENT styles and transform onto a stack (but NOT the current path — paths aren't part of the snapshot); `restore()` pops the top snapshot off the stack, reverting state to it.

```javascript
// ❌ A leaked transform: rotate() and fillStyle stay in effect
// for ALL subsequent shapes in this frame — the classic
// "why is the next element rotated / the wrong color" bug
function drawRotatedIcon(ctx, x, y, angle) {
  ctx.translate(x, y);
  ctx.rotate(angle);
  ctx.fillStyle = 'red';
  ctx.fillRect(-10, -10, 20, 20);
  // NO restore() — the transform and fillStyle "leak" into the rest of the code
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

The team rule: any drawing function that changes the transform or styles, and gets called in a loop over many objects, must be wrapped in `save()`/`restore()` — otherwise, by the third element, the list of "inherited" distortions becomes unpredictable and hard to debug.

## Text: drawing without automatic layout

```javascript
ctx.font = '16px system-ui'; // the same syntax as CSS's font shorthand
ctx.textAlign = 'center';    // 'left' | 'center' | 'right' — relative to X in fillText
ctx.textBaseline = 'middle'; // 'top' | 'middle' | 'alphabetic' | 'bottom' — relative to Y
ctx.fillText('Score: 100', x, y);
ctx.strokeText('Outlined', x, y);

const metrics = ctx.measureText('Score: 100');
console.log(metrics.width); // the text's width in pixels — the ONLY way
                              // to know whether a string fits, since canvas
                              // doesn't wrap text automatically
```

Unlike the DOM, canvas has no built-in line wrapping, ellipsis, or line-height — if you need multi-line, word-wrapped text, that's separate, manual logic built on top of `measureText()`, computed by you, not something the context provides.

## `devicePixelRatio`: reason #1 canvas looks blurry on retina

This is the single detail whose absence breaks roughly every other beginner canvas project. A canvas has TWO independent sizes:

```txt
canvas.width / canvas.height       — the BACKING STORE size (the actual
                                       number of pixels in the buffer you draw into)
canvas.style.width / style.height  — the element's size ON THE PAGE, in CSS
                                       pixels (like an ordinary DOM element)
```

If you don't set these separately, they end up equal to the same number of CSS pixels — and on a display with `devicePixelRatio: 2` (a typical retina screen), the browser has to stretch a buffer of, say, 400×300 real pixels to fill 800×600 physical screen pixels — that is, it **upscales** it, like a small image scaled up to a larger size. The result is visible blur, uniformly, across text, lines, and every bit of content.

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

  canvas.width = rect.width * dpr;   // the REAL buffer size — larger than the CSS size
  canvas.height = rect.height * dpr;
  canvas.style.width = `${rect.width}px`;   // the CSS size stays the same —
  canvas.style.height = `${rect.height}px`; // the element doesn't get physically bigger

  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr); // critical: from here on, draw using CSS-PIXEL
                        // coordinates — the context scales them into the
                        // buffer's real pixels for you
  return ctx;
}
```

After `ctx.scale(dpr, dpr)`, all the rest of your drawing code is written in familiar "logical" coordinates (`fillRect(10, 10, 50, 50)` — as if dpr were 1), and the context handles scaling that into the buffer's real pixels for you — this is the only way to get a crisp picture WITHOUT rewriting every piece of drawing geometry for a specific dpr.

## Clearing strategies

```javascript
ctx.clearRect(0, 0, canvas.width, canvas.height); // ✅ the standard way:
// makes the area transparent, without touching the transform,
// styles, or anything else in the context's state

canvas.width = canvas.width; // ⚠️ an old-code "hack": assigning
// width RESETS the buffer entirely — not just clearing pixels, but
// also zeroing out the ENTIRE transform, styles, and clip region —
// so it's not just clearing, it's a full context reset as a side effect
```

The second variant is sometimes used deliberately as a way to "reset everything at once" (including an accidentally accumulated transform), but it's usually an implicit side effect that surprises people: if code changes `canvas.width` to handle a resize (as in the function above), that INCIDENTALLY clears the content and resets the context's state — worth remembering explicitly, rather than discovering it as an "inexplicable" bug after a window resize.

## Connection to other articles

```txt
[Canvas Animation and Game Loop]        — the clear→update→draw cycle that
                                           the immediate-mode model makes
                                           mandatory, not optional
[Pixels, Images, and Effects]           — ImageData, compositing, and
                                           working with pixels on top of
                                           this article's primitives
[Architecture and Performance for
 Canvas Apps]                            — the save()/restore() discipline
                                           and retina-correct canvas setup
                                           from this article scale into
                                           production patterns
```

## Common interview traps

- **Being unable to explain immediate vs. retained mode** — conflating "canvas doesn't store objects" with "canvas is slower than the DOM" — these are different claims; immediate mode can be faster or slower depending on the scenario, and the key difference is in the state-ownership model, not in performance per se.

- **Not knowing why canvas is blurry on retina** — not connecting the blur to the mismatch between `canvas.width`/`canvas.height` (the buffer) and `canvas.style.width`/`style.height` (the CSS size), and trying to "fix" it with `image-rendering: crisp-edges` in CSS instead of correcting the backing store.

- **Forgetting `beginPath()`** — not understanding that a path keeps accumulating across calls to `fill()`/`stroke()` unless explicitly restarted, and ending up with a "mess" of shapes from previous frames layered on top of the current one.

- **Not knowing the difference between nonzero and evenodd** — being unable to explain why a "donut" (a circle with a hole) sometimes renders as a solid circle with no hole — caused by both contours winding in the same direction under the default `nonzero` rule.

- **Not wrapping transforms in `save()`/`restore()`** — writing a drawing function that changes `rotate`/`translate`/`fillStyle` and gets called in a loop, with no state isolation, so it "leaks" into later iterations unpredictably.

- **Confusing `clearRect()` with assigning `canvas.width`** — not knowing the latter fully resets the context (transform, styles), not just clears pixels, and being surprised by a "disappeared" transform after resizing the canvas.
