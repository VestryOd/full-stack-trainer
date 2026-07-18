# Pixels, Images, and Effects

## A level below primitives

Articles 01-02 work with canvas through high-level primitives: "draw a rectangle," "draw a path." This article goes one level lower, where you don't draw shapes — you read and write the RGBA values of every individual pixel in the buffer directly. That unlocks three classes of work that `fillRect`/`drawImage` alone can't reach: per-pixel image filters, compositing tricks like the scratch-card effect, and, by the end of this article, moving rendering off the main thread entirely.

## `ImageData`: reading and writing the buffer directly

```javascript
const imageData = ctx.getImageData(x, y, width, height); // reads a region of the buffer
console.log(imageData.width, imageData.height);
console.log(imageData.data); // a Uint8ClampedArray — raw RGBA bytes

ctx.putImageData(imageData, x, y); // writes the buffer back
```

**`getImageData`'s cost isn't trivial.** Canvas 2D can render using GPU acceleration, and requesting raw pixels on the CPU forces a synchronization: the browser has to wait for the GPU to finish its current work and copy the buffer's contents from GPU memory into ordinary process memory — a sync point that can cost real time, especially in a hot loop (calling it every animation frame is a common cause of a sudden FPS drop). The `willReadFrequently: true` hint, passed when getting the context, tells the browser to keep the buffer in CPU-accessible memory from the start, avoiding repeated GPU→CPU copies:

```javascript
const ctx = canvas.getContext('2d', { willReadFrequently: true });
```

`putImageData`, unlike `fillRect`/`drawImage`, **ignores** the current transform, `globalCompositeOperation`, and the clip region — it's a direct, byte-for-byte write into the buffer, not "drawing" in the usual sense of the context as a state machine (article 01).

## `Uint8ClampedArray`: the RGBA layout and how it differs from `Uint8Array`

`imageData.data` is a flat byte array, 4 values per pixel, row by row:

```txt
data[0] = R of pixel (0,0)   data[4] = R of pixel (1,0)
data[1] = G of pixel (0,0)   data[5] = G of pixel (1,0)
data[2] = B of pixel (0,0)   data[6] = B of pixel (1,0)
data[3] = A of pixel (0,0)   data[7] = A of pixel (1,0)
```

`Clamped` in the type's name isn't a formality: writing a value outside `[0, 255]` gets **clamped** to the boundary (255 on overflow, 0 on going negative), rather than wrapping around modulo 256, as it would with an ordinary `Uint8Array`. This matters for filter arithmetic — `pixel + 50` producing 280 would give `280 % 256 = 24` with a plain `Uint8Array` (visually, a random dark pixel instead of the expected bright one), while `Uint8ClampedArray` correctly gives `255`.

**A worked example: a grayscale and threshold filter**

```javascript
function applyGrayscale(ctx, width, height) {
  const imageData = ctx.getImageData(0, 0, width, height);
  const data = imageData.data;

  for (let i = 0; i < data.length; i += 4) {
    // The luminance formula — the eye is more sensitive to green,
    // less to blue, so it's not just a plain (r+g+b)/3
    const luminance = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
    data[i] = data[i + 1] = data[i + 2] = luminance; // R=G=B=luminance → gray
    // data[i + 3] (alpha) is left untouched
  }

  ctx.putImageData(imageData, 0, 0);
}

function applyThreshold(ctx, width, height, cutoff = 128) {
  const imageData = ctx.getImageData(0, 0, width, height);
  const data = imageData.data;

  for (let i = 0; i < data.length; i += 4) {
    const luminance = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
    const value = luminance >= cutoff ? 255 : 0; // strictly black or white
    data[i] = data[i + 1] = data[i + 2] = value;
  }

  ctx.putImageData(imageData, 0, 0);
}
```

## Security: tainted canvas and `crossOrigin`

If an image from a DIFFERENT origin is drawn onto a canvas without correct CORS headers, the canvas gets marked **tainted** — the browser deliberately blocks any subsequent reading of its pixel data (`getImageData`, `toDataURL`, `toBlob`), throwing a `SecurityError`. This isn't a bug or overzealous strictness — it's a defense against using canvas as an "oracle" to steal private cross-origin image content (for instance, detecting whether a user is logged into another site by checking the availability of their private avatar, reading its pixels byte by byte).

```javascript
// ❌ Without crossOrigin — the canvas ends up "tainted" for a foreign
// origin, and any export attempt fails with a SecurityError in the console
const img = new Image();
img.src = 'https://other-domain.com/photo.jpg';
img.onload = () => {
  ctx.drawImage(img, 0, 0);
  canvas.toDataURL(); // 💥 SecurityError: tainted canvas
};
```

```javascript
// ✅ Explicitly requesting CORS mode — WORKS only if the image's
// server sends the Access-Control-Allow-Origin header
const img = new Image();
img.crossOrigin = 'anonymous';
img.src = 'https://other-domain.com/photo.jpg';
img.onload = () => {
  ctx.drawImage(img, 0, 0);
  canvas.toDataURL(); // ✅ works, provided the server allows CORS
};
```

A common real-world scenario: "a user uploads a photo, we apply a canvas filter, exporting to a file fails with a confusing error" — almost always this exact cause: `crossOrigin` on the client with no matching header on the server does NOT help; both conditions are required simultaneously.

## `globalCompositeOperation`: how new drawing blends with what's already there

It's important to get the scope of this property right: it's not "the final blending of the whole scene" — it's a mode applied to **every drawing call**, determining how new pixels combine with whatever's already in the buffer underneath them.

### `destination-out`: a complete scratch-card effect

New shapes ERASE existing content wherever they're drawn (it behaves like an eraser, not paint) — this is exactly what scratch-card effects ("scratch to reveal your prize") are built on:

```javascript
// 1. The base layer — what's hidden under the "foil" (prize text, an image)
ctx.fillStyle = '#222';
ctx.fillRect(0, 0, canvas.width, canvas.height);
ctx.fillStyle = 'gold';
ctx.font = 'bold 32px sans-serif';
ctx.fillText('You won 500!', 60, 150);

// 2. The "foil" layer on top — what the user will scratch away
ctx.globalCompositeOperation = 'source-over'; // ordinary drawing (the default)
ctx.fillStyle = '#999';
ctx.fillRect(0, 0, canvas.width, canvas.height);

// 3. Erasing with a brush as the cursor moves
canvas.addEventListener('pointermove', (e) => {
  if (e.buttons !== 1) return; // only erase while the button is held down

  ctx.globalCompositeOperation = 'destination-out'; // the KEY line:
  // everything drawn from here on ERASES existing pixels instead of
  // painting over them
  ctx.beginPath();
  ctx.arc(e.offsetX, e.offsetY, 20, 0, Math.PI * 2);
  ctx.fill(); // a "hole" in the foil layer — the base layer shows through
});
```

That's the COMPLETE working mechanic of a scratch-card effect — the three pieces (a base layer, a foil layer, and an eraser brush via `destination-out`) are enough for a real production component with no additional libraries.

### Other practically important modes

```txt
source-atop  — new drawing is only visible WHERE opaque content
                already exists underneath it (clipped to the shape of
                existing content) — useful for recoloring/tinting
                within an already-drawn silhouette without spilling
                past its edges

multiply     — color channels are MULTIPLIED together — the result is
                always darker than the source colors — the classic
                mode for overlaying shadow/darkening on top of an
                existing scene

screen       — visually the opposite of multiply — the result is
                always lighter — used for glow/highlight effects

lighter      — channel values are ADDED together (additive blending) —
                the classic technique for glow and particles: overlapping
                bright particles (sparks, fire, light) get BRIGHTER
                where they overlap, instead of just drawing over each other
```

```javascript
// Additive glow for particles — a signature "fire"/"sparks" technique
ctx.globalCompositeOperation = 'lighter';
particles.forEach((p) => {
  const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.radius);
  gradient.addColorStop(0, 'rgba(255, 200, 100, 0.8)');
  gradient.addColorStop(1, 'rgba(255, 200, 100, 0)');
  ctx.fillStyle = gradient;
  ctx.beginPath();
  ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
  ctx.fill();
});
// Where particles overlap, total brightness is higher, producing a
// natural clustered-light effect instead of a flat overlay
```

As with any context state (article 01), `globalCompositeOperation` needs to be reset to `'source-over'` explicitly (or wrapped in `save()`/`restore()`) — otherwise the next, unsuspecting piece of code starts drawing in an unexpected blend mode.

## Shadows and `filter`: the same CSS effects, but with a real cost every frame

```javascript
ctx.shadowColor = 'rgba(0,0,0,0.4)';
ctx.shadowBlur = 12;
ctx.shadowOffsetX = 4;
ctx.shadowOffsetY = 4;
ctx.fillRect(50, 50, 100, 100); // the shadow is drawn automatically on any fill/stroke/drawImage

ctx.filter = 'blur(4px) brightness(1.2)'; // the same syntax as CSS filter (covered
                                            // in the browser-animation topic as a
                                            // CSS property)
ctx.drawImage(image, 0, 0);
```

The cost is real: `shadowBlur` and `filter: blur()` are effectively a software blur pass over rasterized pixels on EVERY drawing call, and in the immediate-mode model (where everything gets redrawn every frame, article 02), that cost is paid all over again 60 times a second, for every object it touches. With many animated objects carrying shadow/blur, this is a common cause of a sharp FPS drop.

**The fix — cache an expensive effect into an offscreen canvas once**, and just `drawImage` the finished result inside the game loop:

```javascript
// ❌ The shadow gets recomputed every frame, for every particle
function draw(ctx) {
  particles.forEach((p) => {
    ctx.shadowColor = 'orange';
    ctx.shadowBlur = 15;
    ctx.beginPath();
    ctx.arc(p.x, p.y, 5, 0, Math.PI * 2);
    ctx.fill();
  });
}
```

```javascript
// ✅ The effect is computed ONCE, in an offscreen canvas — from then
// on, it's just a cheap drawImage
const glowSprite = document.createElement('canvas');
glowSprite.width = glowSprite.height = 40;
const glowCtx = glowSprite.getContext('2d');
glowCtx.shadowColor = 'orange';
glowCtx.shadowBlur = 15;
glowCtx.beginPath();
glowCtx.arc(20, 20, 5, 0, Math.PI * 2);
glowCtx.fillStyle = 'orange';
glowCtx.fill();

function draw(ctx) {
  particles.forEach((p) => {
    ctx.drawImage(glowSprite, p.x - 20, p.y - 20); // just copying already-rendered pixels
  });
}
```

This is the same principle as caching static content once with layered canvases in article 02, applied here to expensive visual effects rather than whole scenes.

## Exporting: `toDataURL` vs. `toBlob`

```javascript
const dataUrl = canvas.toDataURL('image/png'); // SYNCHRONOUS, blocks the main thread
// A base64 string inflates the data size by roughly a third compared to
// the binary representation — more expensive in memory and encoding time

canvas.toBlob((blob) => {
  // ASYNCHRONOUS — encoding happens without blocking the main thread
  const formData = new FormData();
  formData.append('image', blob);
  fetch('/upload', { method: 'POST', body: formData });
}, 'image/png');
```

The rule: `toBlob` is the preferred choice almost always, especially for large canvases and/or sending data to a server — a `Blob` goes straight into `FormData`/`fetch`, with no base64 bloat and no synchronous blocking. `toDataURL` is justified only for small images, or where you genuinely need a string (embedding directly in an `<img src>`/CSS).

`createImageBitmap(source)` is a separate tool for decoding images OFF the main thread:

```javascript
const response = await fetch('/large-photo.jpg');
const blob = await response.blob();
const bitmap = await createImageBitmap(blob); // decoding happens in the
                                                // background, main thread stays free
ctx.drawImage(bitmap, 0, 0); // drawn just like an ordinary image
```

Unlike `new Image()` + `.onload` (where the decisive work — decoding a JPEG/PNG into raster data — can cause noticeable jank on the main thread for large images), `createImageBitmap` explicitly moves that decoding off the main thread.

## `OffscreenCanvas` + Worker: rendering entirely off the main thread

In [Performance Debugging and Jank Hunting] (the browser-animation topic), `OffscreenCanvas` was mentioned as a "bridge" to this topic — a signal that DOM animation had physically hit its ceiling. Here's the full mechanics.

`canvas.transferControlToOffscreen()` hands control of the element's rendering to a Worker thread — ALL further work with the context (`getContext`, drawing calls) happens there, not on the main thread:

```javascript
// main.js — the main thread
const canvas = document.querySelector('canvas');
const offscreen = canvas.transferControlToOffscreen();
const worker = new Worker('render-worker.js');
worker.postMessage({ canvas: offscreen }, [offscreen]); // transferred, not copied —
                                                          // ownership moves to the
                                                          // worker; the main thread
                                                          // can no longer draw to this canvas

worker.postMessage({ type: 'input', x: mouseX, y: mouseY }); // input is the only
                                                               // thing that flows
                                                               // through postMessage
```

```javascript
// render-worker.js — the worker thread
let ctx;
self.onmessage = (e) => {
  if (e.data.canvas) {
    ctx = e.data.canvas.getContext('2d'); // getContext is available in a
                                            // Worker for an OffscreenCanvas too
    startLoop();
  }
  if (e.data.type === 'input') { /* update state based on the input */ }
};

function startLoop() {
  function loop(timestamp) {
    update();
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    draw(ctx); // article 02's entire game loop, running entirely inside the worker
    requestAnimationFrame(loop); // rAF is available in an OffscreenCanvas Worker context too
  }
  requestAnimationFrame(loop);
}
```

**When this earns its complexity:** heavy, genuinely CPU-bound per-pixel work every frame — large particle counts, a complex simulation, real-time image processing — where rendering genuinely competes with the main thread against user input handling, React re-renders, and other UI work, and that measurably hurts responsiveness (INP, browser-animation article 06). **When it doesn't:** for light drawing, the architectural overhead (passing state through `postMessage`, syncing UI state with the worker, duplicating some logic) outweighs the benefit — most canvas features work perfectly well on the main thread without this level of engineering.

## Connection to other articles

```txt
[Canvas 2D Fundamentals]              — the drawing primitives this
                                         article's pixel-level work
                                         builds on top of
[Canvas Animation and Game Loop]      — the update/draw cycle where
                                         caching expensive effects and
                                         offloading to a Worker get built in
[Performance Debugging and Jank
 Hunting] (browser-animation)          — where OffscreenCanvas was first
                                         mentioned as a signal of DOM
                                         animation's architectural ceiling
[Architecture and Performance for
 Canvas Apps]                          — systematizing effect caching,
                                         pooling, and memory budgets at
                                         the level of a whole application
```

## Common interview traps

- **Not knowing `getImageData`'s cost** — calling it every animation frame with no awareness that it's a GPU→CPU sync point, and not knowing about `willReadFrequently` as a way to reduce that cost for frequent reads.

- **Confusing `Uint8ClampedArray` with an ordinary `Uint8Array`** — not knowing values outside `[0, 255]` are clamped rather than wrapped modulo, and getting unexplained artifacts in a hand-written pixel filter on overflow.

- **Being unable to explain tainted canvas** — not knowing that drawing a cross-origin image without correct CORS headers blocks ANY subsequent pixel read (`getImageData`/`toDataURL`/`toBlob`) with a `SecurityError`, and that client-side `crossOrigin` alone, without matching server headers, doesn't help.

- **Treating `globalCompositeOperation` as "the final overlay effect"** — not understanding it's a blend mode applied to EVERY drawing call, and being unable to explain the mechanics of a scratch-card effect via `destination-out`.

- **Not knowing about `lighter` for additive glow** — trying to achieve "bright particles get brighter where they overlap" with transparency and `source-over`, which produces a visually different (duller, "flatter") result.

- **Not distinguishing `toDataURL` from `toBlob` by performance** — using the synchronous `toDataURL` to send large images to a server, unaware that `toBlob` is asynchronous and avoids the base64 size bloat.

- **Not knowing about `OffscreenCanvas` + Worker** — proposing to "just optimize the drawing code" when the real problem is rendering competing with UI work for the main thread — something an architectural move to a Worker solves, not a targeted micro-optimization.
