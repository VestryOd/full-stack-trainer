# Pixi.js in Depth

## Pixi: a retained-mode scene on top of WebGL

Pixi keeps your scene as a tree of long-lived objects on top of WebGL (Web Graphics Library), and redraws it for you. You create scene objects **once**, and from then on you just **mutate their properties**: `sprite.x = 150`, `sprite.rotation += 0.02`. Pixi figures out what and how to redraw. It assembles those changes into the smallest possible number of draw calls, through its built-in batch renderer (article 04).

That is the opposite of the immediate-mode Canvas 2D model of articles 01-03. There you draw pixels, nothing about them is remembered, and next frame you redraw from scratch (article 01).

```txt
Canvas 2D (immediate mode, articles 01-03)
  every frame:
    ctx.clearRect(...)
    ctx.drawImage(sprite, x, y)
    // you are responsible for every frame

Pixi (retained mode)
  once:
    const sprite = new Sprite(texture);
    stage.addChild(sprite);
  every frame:
    sprite.x += 1;   // just a mutation
    // Pixi knows what to redraw
```

This isn't "Pixi eliminates immediate mode as a concept". Under the hood Pixi still draws through WebGL draw calls every frame. Rendering stays fully immediate-mode at the GPU (graphics processing unit) level (article 04).

From the perspective of **your** code, though, the model becomes retained. You work with a tree of long-lived objects instead of one-shot drawing commands.

## `Application`, `stage`, and the `Container` hierarchy

```javascript
const app = new Application();
await app.init({ width: 800, height: 600, backgroundColor: 0x1a1a2e });
document.body.appendChild(app.canvas);

const group = new Container(); // Container — a scene-graph node:
app.stage.addChild(group);       // holds children AND its own transform

const sprite = new Sprite(texture);
group.addChild(sprite);

group.rotation = 0.1; // a Container's transform automatically applies
                       // to all its children — plain canvas has no
                       // equivalent to this without manual
                       // save()/translate()/rotate() around every
                       // child draw call (article 01)
```

`app.stage` is the scene's root `Container`. Any `Container` is a tree node holding both a list of children and its own transform: position, rotation, scale, alpha.

A parent's transform automatically composes with its descendants' transforms at render time. Plain Canvas 2D would require you to manage that by hand, with `save()`/`translate()`/`rotate()` around every single draw (article 01). Here it is built directly into the scene structure.

## `Sprite`, `Texture`, and `BaseTexture`

| Concept | What it is |
|---|---|
| `BaseTexture` | The actual pixels **uploaded to GPU memory**, one GPU texture. The heaviest unit: this is what actually costs graphics memory. |
| `Texture` | A "window" into a region of a `BaseTexture`: an x, y, width, height rectangle inside it. Many `Texture` objects can point to **one** `BaseTexture` without re-uploading it. |
| `Sprite` | A display object that draws a specific `Texture` at a given position, rotation and scale. |

```javascript
const sprite = new Sprite(texture);
sprite.anchor.set(0.5); // anchor point (0.5, 0.5) = center —
                          // rotation/scale happen around the center
                          // instead of the default (0,0) corner
```

The `Texture`/`BaseTexture` split is exactly what makes sprite atlases possible. One large PNG (portable network graphics) file is one `BaseTexture` and one GPU upload. It gets sliced into dozens of `Texture` objects, each pointing to its own rectangle inside the shared image, with no extra GPU upload per sprite.

## Sprite atlases: why they enable batching

Pixi's batch renderer can combine drawing many sprites into a single draw call. The condition is that all the sprites involved share a common `BaseTexture`.

The reason: the GPU doesn't need to swap "texture units" between neighboring sprites if they read pixels from the same uploaded image. A draw call's cost is mostly state-change overhead, and texture swaps are part of it (article 04).

```txt
❌ 200 separate PNG files, each its own BaseTexture:
   drawing 200 sprites ≈ up to 200 draw calls (or groups by adjacent
   matching textures) — driver overhead grows linearly

✅ One 2048×2048px atlas, 200 sprites — 200 Textures, each pointing
   into a different rectangle of the same BaseTexture:
   the same 200 sprites render in just a few (ideally one) draw
   calls, regardless of the count
```

The practical takeaway concerns scenes with hundreds or thousands of similar sprites: particles, interface icons, map tiles. There, packing images into an atlas isn't a micro-optimization.

It is an architectural decision, and it determines whether the scene hits a performance ceiling at real-world object counts.

## The batch renderer: what breaks it

```txt
What breaks a batch (forces a separate draw call):
  - A BaseTexture change between sprites adjacent in draw order
    (if they aren't from the same atlas)
  - A filter on any object in the middle of the draw order. A
    filter renders into a temporary render texture and back, which
    interrupts batching before and after it
  - A blend mode change between adjacent objects
  - A custom shader on a single object, different from the rest of
    the batch
```

Three practical architectural consequences follow:

- Group sprites that share a texture next to each other in draw order, wherever visual z-order allows it.
- Limit the number of **distinct** filters in a scene. Not "a filter on every tenth sprite, mixed with plain ones", but either applied to a whole visual layer or not at all.
- For truly massive counts of uniform, simple sprites — thousands of particles — use `ParticleContainer`. It is a specialized container tuned for maximum batching throughput in exactly this scenario. What it trades away: a simplified transform model and limited per-child filter support.

## `Graphics`: vector shapes — but not free every frame

`Graphics` is the API for drawing vector shapes, the analog of `fillRect`/`arc`/paths from article 01. The result is WebGL geometry, not canvas pixels:

```javascript
const graphics = new Graphics();
graphics.rect(0, 0, 100, 100).fill(0xff3366);
graphics.circle(150, 50, 40).fill(0x33ccff);
stage.addChild(graphics);
```

The key difference from `Sprite` is cost. Moving, rotating or scaling a `Sprite` every frame is cheap: it only changes the transform matrix over geometry and a texture that already exist.

`Graphics` behaves differently. When you call `clear()` and draw again, it **rebuilds its geometry**, regenerating the vertex buffer. That is noticeably more expensive than a plain transform change.

```javascript
// ❌ Expensive: Graphics geometry is rebuilt 60 times a second
app.ticker.add(() => {
  graphics.clear();
  graphics.circle(mouseX, mouseY, 20).fill(0xffffff);
});
```

```javascript
// ✅ Cheap: the Sprite just moves, its geometry/texture never change
const cursorSprite = new Sprite(circleTexture); // the texture is computed once
app.ticker.add(() => {
  cursorSprite.x = mouseX;
  cursorSprite.y = mouseY; // just a transform, no geometry rebuild
});
```

The rule: use `Graphics` for static or infrequently-changing vector shapes. For shapes that genuinely need to redraw every frame in large numbers, use a `Sprite` with a pre-baked texture. The other option is caching the `Graphics` result once into a `RenderTexture` or via `cacheAsTexture`, instead of rebuilding geometry every tick.

## `Text` vs. `BitmapText`

```javascript
const text = new Text({ text: 'Score: 0', style: { fontSize: 24, fill: 0xffffff } });
// Internally, Text renders the string via canvas 2D (measuring,
// rasterizing glyphs) and uploads the result as an ordinary
// texture — expensive on every text/style change, fine as a static label

const bitmapText = new BitmapText({ text: 'Score: 0', style: { fontFamily: 'game-font' } });
// BitmapText assembles a string from pre-built glyph sprites of a
// pre-generated bitmap font (a character sprite atlas) — updating
// the text does not require re-rasterizing via canvas, cheap every frame
```

The practical choice depends on how often the string changes. A score counter that updates once a second or less: `Text` is fine. A frames-per-second counter or a timer that updates every frame: `BitmapText`.

The reason is that canvas rasterization on every frame for `Text` creates real, noticeable overhead. `BitmapText` avoids it entirely, at the cost of needing a pre-built bitmap font.

## Interaction: pointer events on scene objects

```javascript
sprite.eventMode = 'static'; // enable event handling for this object
sprite.cursor = 'pointer';
sprite.on('pointerdown', () => console.log('clicked!'));
sprite.on('pointerover', () => { sprite.tint = 0xffcc00; });

sprite.hitArea = new Rectangle(0, 0, 200, 50); // an explicit hit region,
// different from the sprite's visual bounds — useful for enlarging a
// small icon's clickable area, or shrinking it to fit an irregular shape
```

Conceptually this is the same problem as hit detection on plain canvas: math checks, `isPointInPath`, or color-picking (article 02). Pixi handles it for you through the scene graph. Hit testing runs automatically across the `Container` hierarchy, accounts for parent transforms, and needs no manual coordinate math.

## Filters: built-in, and a custom fragment shader

```javascript
import { BlurFilter, ColorMatrixFilter } from 'pixi.js';

sprite.filters = [new BlurFilter({ strength: 8 })];

const colorMatrix = new ColorMatrixFilter();
colorMatrix.grayscale(0.8);
sprite.filters = [colorMatrix];
```

A filter is applied in three steps. The object, and sometimes some area around it, is rendered into a temporary render texture. A fragment shader (article 04) runs over that texture. The result is inserted back into the scene.

That is exactly why filters "break batching", as described above. It's an extra, isolated render pass, not part of the ordinary drawing flow.

```javascript
// A minimal custom filter — grayscale via a custom fragment shader
import { Filter, GlProgram } from 'pixi.js';

const grayscaleFragment = `
  precision mediump float;
  varying vec2 vTextureCoord;
  uniform sampler2D uTexture;

  void main() {
    vec4 color = texture2D(uTexture, vTextureCoord);
    float gray = dot(color.rgb, vec3(0.299, 0.587, 0.114)); // the same
                                                              // luminance
                                                              // formula as article 03
    gl_FragColor = vec4(vec3(gray), color.a);
  }
`;

const customGrayscale = new Filter({
  glProgram: new GlProgram({ fragment: grayscaleFragment, vertex: defaultVertexShader }),
});
sprite.filters = [customGrayscale];
```

This is a direct application of the GLSL (OpenGL Shading Language) model from article 04. Pixi supplies `vTextureCoord`, a rasterization-interpolated varying, and `uTexture`, a uniform sampler. That spares you from setting up buffers and attributes by hand for a full-screen pass.

## `Ticker`: the built-in update loop

```javascript
app.ticker.add((ticker) => {
  sprite.rotation += 0.02 * ticker.deltaTime; // deltaTime: 1.0 = "one frame
                                                // at 60fps," scaled to the
                                                // actual refresh rate — the
                                                // same idea as delta time in
                                                // browser-animation article 04
                                                // and canvas article 02, just
                                                // already built into the renderer
});
```

Pixi already runs its own rAF (`requestAnimationFrame`) render loop inside `Application`. You don't need a separate `requestAnimationFrame` alongside it, and you shouldn't add one.

Your own game logic hooks in via `app.ticker.add()`. It receives `deltaTime`, counted in frames at a target 60fps, or `deltaMS`, counted in milliseconds.

## Asset loading: `Assets`

```javascript
await Assets.load('sprites/hero.png');
const heroTexture = Assets.get('sprites/hero.png'); // calling load() again with
                                                       // the same key doesn't re-fetch —
                                                       // Assets caches and dedupes

await Assets.load([
  { alias: 'atlas', src: 'sprites/atlas.json' }, // a sprite atlas with metadata
  { alias: 'font', src: 'fonts/game-font.fnt' },
]);
```

## Memory management: `destroy()` and the "new texture every frame" leak

GPU resources such as textures and buffers aren't released by JS garbage collection the way ordinary objects are. The JS wrapper object can be collected, but the GPU memory allocated for it stays occupied until `destroy()` is called explicitly.

```javascript
sprite.destroy();                       // destroys the display object
texture.destroy(true);                   // true — destroy the BaseTexture too
container.destroy({ children: true });   // recursively destroy all children
```

```javascript
// ❌ The classic leak: a new RenderTexture every frame, the old ones
// never destroy()'d — GPU memory grows without bound
app.ticker.add(() => {
  const snapshot = RenderTexture.create({ width: 200, height: 200 });
  app.renderer.render({ container: someObject, target: snapshot });
  updatePreview(snapshot); // last frame's snapshot is NEVER destroyed
});
```

```javascript
// ✅ One RenderTexture, created once and reused
const snapshot = RenderTexture.create({ width: 200, height: 200 });
app.ticker.add(() => {
  app.renderer.render({ container: someObject, target: snapshot }); // the
                                                                       // same GPU
                                                                       // resource,
                                                                       // just
                                                                       // overwritten
  updatePreview(snapshot);
});
```

This leak pattern is especially dangerous on mobile devices with limited GPU memory. The app runs fine for a few minutes, then the tab crashes or the browser forcibly reclaims the context. It's a typical production bug, and hard to catch in quick local testing on a powerful desktop.

## When Pixi over plain Canvas 2D, and when it's overkill

**When Pixi is worth it:**

- Hundreds to thousands of sprites or particles at once. Batching solves what plain Canvas 2D hits a CPU (central processing unit) ceiling on, when every `drawImage` call is drawn individually.
- Compositions with several filters, blend modes, and complex interactivity across many objects.
- A project that will grow in complexity: many layers, nested object hierarchies, texture reuse.

**When it's overkill:**

- A handful of simple shapes or icons, or a one-off simple animation. The library's weight and API surface aren't justified relative to the task.
- Plain Canvas 2D (articles 01-03) is simpler and entirely sufficient for that.

## Pixi with React: an imperative core inside a declarative shell

```tsx
function PixiCanvas() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const app = new Application();
    let cancelled = false;

    (async () => {
      await app.init({ width: 800, height: 600 });
      if (cancelled) { app.destroy(true); return; } // unmounted while init() was running
      containerRef.current?.appendChild(app.canvas);
      // ...build the scene
    })();

    return () => {
      cancelled = true;
      app.destroy(true, { children: true, texture: true }); // required cleanup —
                                                                // without it, every
                                                                // remount (a route
                                                                // change, React
                                                                // StrictMode) leaks
                                                                // GPU resources
    };
  }, []);

  return <div ref={containerRef} />;
}
```

This is the same principle as "canvas as an escape hatch from React's render model", which article 08 covers in depth for plain canvas. A Pixi `Application` lives inside `useEffect`, outside React's render cycle, and must be explicitly destroyed in the cleanup function.

For a more declarative style there is `@pixi/react`. It's a wrapper that lets you describe a scene with JSX (a syntax extension for JavaScript) components like `<pixiSprite>`. It remains a thin layer over the same imperative Pixi model, not a replacement for it.

## Connection to other articles

- [WebGL and GPU Fundamentals](./04-webgl-and-gpu-fundamentals.md) — draw calls, batching, shaders and textures: the foundation Pixi's entire batch renderer is built on.
- [Canvas 2D Fundamentals](./01-canvas-2d-fundamentals.md) and [Canvas Animation and Game Loop](./02-canvas-animation-and-game-loop.md) — the immediate-mode model that retained-mode Pixi contrasts with. Article 02 also covers the hit detection that Pixi handles for you through the scene graph.
- [Architecture and Performance for Canvas Apps](./08-architecture-and-performance-for-canvas-apps.md) — the React integration and memory-management patterns from this article generalize to a whole application.

## Common interview traps

- **Being unable to explain how Pixi differs from plain canvas at a model level** — conflating "Pixi uses WebGL" with "Pixi is retained mode". Both are true, but they are two **different** facts. WebGL rendering stays immediate at the GPU level, while retained mode is about how **your** code is organized on top of it.

- **Confusing `Texture` and `BaseTexture`** — not knowing that many `Texture` objects can point to one `BaseTexture` without a re-upload to the GPU. That is exactly what makes sprite atlases a batching mechanism, not just convenient file packaging.

- **Not knowing what breaks batching** — being unable to name concrete causes: a texture swap, a filter mid-draw-order, a blend mode change. And being unable to propose architectural fixes: an atlas, grouping by texture, limiting the number of filters.

- **Assuming `Graphics` is as cheap as `Sprite` every frame** — not knowing that redrawing `Graphics` rebuilds its geometry. Moving a `Sprite` is just a transform-matrix change over data that already exists.

- **Not knowing the cost difference between `Text` and `BitmapText`** — proposing `Text` for a counter that updates every frame. That misses the canvas rasterization pass on every change.

- **Not calling `destroy()`** — creating new textures or render textures inside the render loop without releasing the old ones. The result is a GPU memory leak, especially noticeable on mobile devices.

- **Not cleaning up a Pixi `Application` on React unmount** — forgetting `app.destroy()` in a `useEffect` cleanup function. Leaks then accumulate on every remount: route changes, React StrictMode in development.
