# Pixels, Images, and Effects

## A level below primitives

This article works one level below drawing primitives. You don't draw shapes here: you read and write the RGBA (red, green, blue, alpha) values of every individual pixel in the buffer directly. Articles 01-02 stayed at the level of "draw a rectangle" and "draw a path".

That unlocks three classes of work `fillRect` and `drawImage` can't reach on their own. Per-pixel image filters come first. Then compositing tricks such as the scratch-card effect. And by the end of the article, moving rendering off the main thread entirely.

## `ImageData`: reading and writing the buffer directly

```javascript
const imageData = ctx.getImageData(x, y, width, height); // reads a region of the buffer
console.log(imageData.width, imageData.height);
console.log(imageData.data); // a Uint8ClampedArray — raw RGBA bytes

ctx.putImageData(imageData, x, y); // writes the buffer back
```

**`getImageData` is expensive.** Canvas 2D can render with GPU (graphics processing unit) acceleration. Requesting raw pixels for the CPU (central processing unit) then forces a synchronization. The browser has to wait for the GPU to finish its current work. Then it copies the buffer's contents from GPU memory into ordinary process memory.

That synchronization point can cost real time, especially in a loop that runs every frame. Calling `getImageData` on every animation frame is a common cause of a sudden FPS (frames per second) drop.

The `willReadFrequently: true` hint, passed when getting the context, tells the browser to keep the buffer in CPU-accessible memory from the start. That avoids repeated GPU→CPU copies:

```javascript
const ctx = canvas.getContext('2d', { willReadFrequently: true });
```

`putImageData`, unlike `fillRect` and `drawImage`, **ignores** the current transform, `globalCompositeOperation`, and the clip region. It is a direct, byte-for-byte write into the buffer. That is not "drawing" in the usual sense of the context as a state machine (article 01).

## `Uint8ClampedArray`: the RGBA layout and how it differs from `Uint8Array`

`imageData.data` is a flat byte array, 4 values per pixel, row by row:

```txt
data[0] = R of pixel (0,0)   data[4] = R of pixel (1,0)
data[1] = G of pixel (0,0)   data[5] = G of pixel (1,0)
data[2] = B of pixel (0,0)   data[6] = B of pixel (1,0)
data[3] = A of pixel (0,0)   data[7] = A of pixel (1,0)
```

`Clamped` in the type's name isn't a formality. Writing a value outside `[0, 255]` gets **clamped** to the boundary: 255 on overflow, 0 on going negative. An ordinary `Uint8Array` would wrap around modulo 256 instead.

This matters for filter arithmetic. Suppose `pixel + 50` produces 280. A plain `Uint8Array` gives `280 % 256 = 24`, which looks like a random dark pixel instead of the expected bright one. `Uint8ClampedArray` correctly gives `255`.

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

If an image from a **different** origin is drawn onto a canvas without correct CORS headers, the canvas gets marked **tainted**. CORS stands for cross-origin resource sharing. The browser then deliberately blocks any later reading of that canvas's pixel data — `getImageData`, `toDataURL`, `toBlob` — and throws a `SecurityError`.

This isn't a bug, and it isn't strictness for its own sake. It is a defense against using canvas as an "oracle" to steal private cross-origin image content. An attacker could detect whether a user is logged into another site by checking whether their private avatar loads, and then reading its pixels.

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
// ✅ Explicitly requesting CORS mode — works only if the image's
// server sends the Access-Control-Allow-Origin header
const img = new Image();
img.crossOrigin = 'anonymous';
img.src = 'https://other-domain.com/photo.jpg';
img.onload = () => {
  ctx.drawImage(img, 0, 0);
  canvas.toDataURL(); // ✅ works, provided the server allows CORS
};
```

A common real-world scenario: a user uploads a photo, we apply a canvas filter, and exporting to a file fails with a confusing error. The cause is almost always this one. Client-side `crossOrigin`, with no matching header on the server, does **not** help. Both conditions are required at the same time.

## `globalCompositeOperation`: how new drawing blends with what's already there

Get the scope of this property right. It is not a single blend applied to the whole scene at the end. It is a mode applied to **every drawing call**, determining how new pixels combine with whatever is already in the buffer underneath them.

### `destination-out`: a complete scratch-card effect

New shapes **erase** existing content wherever they're drawn: the mode behaves like an eraser, not like paint. Scratch-card effects ("scratch to reveal your prize") are built on exactly this:

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

  ctx.globalCompositeOperation = 'destination-out'; // the key line:
  // everything drawn from here on erases existing pixels instead of
  // painting over them
  ctx.beginPath();
  ctx.arc(e.offsetX, e.offsetY, 20, 0, Math.PI * 2);
  ctx.fill(); // a "hole" in the foil layer — the base layer shows through
});
```

That is the **complete** working mechanic of a scratch-card effect. Three pieces are enough for a real production component with no extra libraries: a base layer, a foil layer, and an eraser brush via `destination-out`.

### Other practically important modes

- `source-atop` — new drawing is visible only **where** opaque content already exists underneath it. It is clipped to the shape of the existing content. That is useful for recoloring or tinting inside an already-drawn silhouette, without spilling past its edges.
- `multiply` — color channels are multiplied together, so the result is always darker than the source colors. This is the classic mode for laying shadow or darkening over an existing scene.
- `screen` — visually the opposite of `multiply`: the result is always lighter. Used for glow and highlight effects.
- `lighter` — channel values are added together, which is additive blending. This is the classic technique for glow and particles. Overlapping bright particles (sparks, fire, light) get brighter where they overlap, instead of just drawing over each other.

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

Like any context state (article 01), `globalCompositeOperation` has to be reset to `'source-over'` explicitly, or wrapped in `save()`/`restore()`. Otherwise the next piece of code, which knows nothing about the change, starts drawing in an unexpected blend mode.

## Shadows and `filter`: the same CSS effects, but with a real cost every frame

```javascript
ctx.shadowColor = 'rgba(0,0,0,0.4)';
ctx.shadowBlur = 12;
ctx.shadowOffsetX = 4;
ctx.shadowOffsetY = 4;
// the shadow is drawn automatically on any fill, stroke or drawImage
ctx.fillRect(50, 50, 100, 100);

ctx.filter = 'blur(4px) brightness(1.2)'; // the same syntax as CSS filter (covered
                                            // in the browser-animation topic as a
                                            // CSS property)
ctx.drawImage(image, 0, 0);
```

The cost is real. `shadowBlur` and `filter: blur()` are effectively a software blur pass over rasterized pixels, on **every** drawing call. In the immediate-mode model everything gets redrawn every frame (article 02). That cost is therefore paid all over again 60 times a second, for every object it touches. With many animated objects carrying shadow or blur, this is a common cause of a sharp FPS drop.

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
// ✅ The effect is computed once, in an offscreen canvas — from then
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

This is the same principle as caching static content once with layered canvases in article 02. Here it is applied to expensive visual effects instead of whole scenes.

## Exporting: `toDataURL` vs. `toBlob`

```javascript
const dataUrl = canvas.toDataURL('image/png'); // synchronous, blocks the main thread
// A base64 string inflates the data size by roughly a third compared to
// the binary representation — more expensive in memory and encoding time

canvas.toBlob((blob) => {
  // asynchronous — encoding happens without blocking the main thread
  const formData = new FormData();
  formData.append('image', blob);
  fetch('/upload', { method: 'POST', body: formData });
}, 'image/png');
```

The rule: `toBlob` is the preferred choice almost always, especially for large canvases and for sending data to a server. A `Blob` goes straight into `FormData` and `fetch`, with no base64 bloat and no synchronous blocking. Use `toDataURL` only for small images, or where you genuinely need a string: embedding directly in an `<img src>` or in CSS.

`createImageBitmap(source)` is a separate tool for decoding images off the main thread:

```javascript
const response = await fetch('/large-photo.jpg');
const blob = await response.blob();
const bitmap = await createImageBitmap(blob); // decoding happens in the
                                                // background, main thread stays free
ctx.drawImage(bitmap, 0, 0); // drawn just like an ordinary image
```

`new Image()` with `.onload` decodes the file on the main thread. Decoding a JPEG (joint photographic experts group) or PNG (portable network graphics) image into raster data is the decisive work here. For large images it can cause noticeable jank. `createImageBitmap` moves that decoding off the main thread explicitly.

## `OffscreenCanvas` + Worker: rendering entirely off the main thread

`OffscreenCanvas` moves rendering into a Worker thread, and this section gives the full mechanics. The browser-animation topic already mentioned it, in the article Performance Debugging and Jank Hunting, as a "bridge" to this topic. It appeared there as a signal that DOM (document object model) animation had physically hit its ceiling.

`canvas.transferControlToOffscreen()` hands control of the element's rendering to a Worker thread. **All** further work with the context happens there, not on the main thread: `getContext`, drawing calls, everything.

```javascript
// main.js — the main thread
const canvas = document.querySelector('canvas');
const offscreen = canvas.transferControlToOffscreen();
const worker = new Worker('render-worker.js');
worker.postMessage({ canvas: offscreen }, [offscreen]); // transferred, not copied —
                                                          // ownership moves to the
                                                          // worker; the main thread
                                                          // can no longer draw here

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
    requestAnimationFrame(loop); // rAF works inside a worker too
  }
  requestAnimationFrame(loop);
}
```

**When a worker is worth the complexity:** heavy, genuinely CPU-bound per-pixel work on every frame. Large particle counts, a complex simulation, real-time image processing.

There, rendering really competes with the main thread against user input handling, React re-renders, and other UI (user interface) work. That measurably hurts responsiveness, measured as INP (Interaction to Next Paint); see browser-animation article 06.

**When it isn't worth it:** for light drawing the architectural overhead outweighs the benefit. That overhead is passing state through `postMessage`, syncing UI state with the worker, and duplicating some logic. Most canvas features work perfectly well on the main thread without this level of engineering.

## Connection to other articles

- [Canvas 2D Fundamentals](./01-canvas-2d-fundamentals.md) — the drawing primitives this article's pixel-level work builds on.
- [Canvas Animation and the Game Loop](./02-canvas-animation-and-game-loop.md) — the update/draw cycle where effect caching and offloading to a Worker get built in.
- Performance Debugging and Jank Hunting (browser-animation) — where `OffscreenCanvas` was first mentioned, as a signal of the architectural ceiling of DOM animation.
- [Architecture and Performance for Canvas Apps](./08-architecture-and-performance-for-canvas-apps.md) — effect caching, pooling, and memory budgets systematized at the level of a whole application.

## Common interview traps

- **Not knowing what `getImageData` costs.** Calling it on every animation frame, with no awareness that it is a GPU→CPU sync point. And not knowing about `willReadFrequently` as a way to reduce that cost for frequent reads.

- **Confusing `Uint8ClampedArray` with an ordinary `Uint8Array`.** Not knowing that values outside `[0, 255]` are clamped rather than wrapped modulo. The symptom is unexplained artifacts in a hand-written pixel filter on overflow.

- **Being unable to explain tainted canvas.** Drawing a cross-origin image without correct CORS headers blocks **any** later pixel read (`getImageData`, `toDataURL`, `toBlob`) with a `SecurityError`. Client-side `crossOrigin` alone, without matching server headers, doesn't help.

- **Treating `globalCompositeOperation` as a final overlay effect.** It is a blend mode applied to **every** drawing call. The follow-up is usually being unable to explain the scratch-card mechanic via `destination-out`.

- **Not knowing about `lighter` for additive glow.** Trying to make bright particles get brighter where they overlap using transparency and `source-over`. That produces a visually different result: duller and flatter.

- **Not distinguishing `toDataURL` from `toBlob` by performance.** Using the synchronous `toDataURL` to send large images to a server. `toBlob` is asynchronous and avoids the base64 size bloat.

- **Not knowing about `OffscreenCanvas` with a Worker.** Proposing to "just optimize the drawing code" when the real problem is rendering competing with UI work for the main thread. That calls for an architectural move to a Worker, not a targeted micro-optimization.
