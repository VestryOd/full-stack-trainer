# Pixi.js in Depth

## Pixi: a retained-mode scene on top of WebGL

Articles 01-03 covered immediate-mode Canvas 2D: you draw pixels, nothing about them is remembered, and next frame you redraw from scratch (article 01). Pixi flips this model: you create scene objects ONCE, and from then on just **mutate their properties** (`sprite.x = 150`, `sprite.rotation += 0.02`) — Pixi figures out what and how to redraw, and assembles those changes into the smallest possible number of WebGL draw calls (article 04) through its built-in batch renderer.

```txt
Canvas 2D (immediate mode, articles 01-03):   Pixi (retained mode):
  every frame:                                  once:
    ctx.clearRect(...)                            const sprite = new Sprite(texture);
    ctx.drawImage(sprite, x, y)                   stage.addChild(sprite);
    // you're responsible for EVERY frame          every frame:
                                                     sprite.x += 1; // just a mutation
                                                     // Pixi knows what to redraw
```

This isn't "Pixi eliminates immediate mode as a concept" — under the hood, Pixi still draws through WebGL draw calls every frame (fully immediate-mode rendering at the GPU level, article 04); but from the perspective of YOUR code, the model becomes retained: you work with a tree of long-lived objects instead of one-shot drawing commands.

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
                       // to ALL its children — plain canvas has no
                       // equivalent to this without manual
                       // save()/translate()/rotate() around every
                       // child draw call (article 01)
```

`app.stage` is the scene's root `Container`. Any `Container` is a tree node holding both a list of children and its own transform (position, rotation, scale, alpha); a parent's transform automatically composes with its descendants' transforms at render time — something plain Canvas 2D would require you to manage by hand via `save()`/`translate()`/`rotate()` around every single draw (article 01), but which is built directly into the scene structure here.

## `Sprite`, `Texture`, and `BaseTexture`

```txt
BaseTexture — the actual pixels UPLOADED TO GPU MEMORY (one GPU
               texture); the "heaviest" unit — this is what actually
               costs graphics memory

Texture      — a "window" into a region of a BaseTexture (an x, y,
               width, height rectangle inside it); MANY Textures can
               point to ONE BaseTexture without re-uploading it

Sprite       — a display object that draws a specific Texture at a
               given position/rotation/scale
```

```javascript
const sprite = new Sprite(texture);
sprite.anchor.set(0.5); // anchor point (0.5, 0.5) = center —
                          // rotation/scale happen around the center
                          // instead of the default (0,0) corner
```

The Texture/BaseTexture split is exactly what makes sprite atlases possible: one large PNG (one `BaseTexture`, one GPU upload) gets sliced into dozens of `Texture` objects, each pointing to its own rectangle inside the shared image — with no extra GPU upload per sprite.

## Sprite atlases: why they enable batching

Pixi's batch renderer can combine drawing many sprites into ONE draw call, as long as all the sprites involved share a common `BaseTexture` — the GPU doesn't need to swap "texture units" between drawing neighboring sprites if they're reading pixels from the same uploaded image (article 04: a draw call's cost is mostly state-change overhead, including texture swaps).

```txt
❌ 200 separate PNG files, each its own BaseTexture:
   drawing 200 sprites ≈ up to 200 draw calls (or groups by adjacent
   matching textures) — driver overhead grows linearly

✅ One 2048×2048px atlas, 200 sprites — 200 Textures, each pointing
   into a different rectangle of the SAME BaseTexture:
   the same 200 sprites render in JUST A FEW (ideally one) draw
   calls, regardless of the count
```

The practical takeaway: for scenes with hundreds or thousands of similar sprites (particles, UI icons, map tiles), packing images into an atlas isn't a micro-optimization — it's an architectural decision determining whether the scene hits a performance ceiling at real-world object counts.

## The batch renderer: what breaks it

```txt
What breaks a batch (forces a separate draw call):
  - A BaseTexture change between sprites adjacent in draw order
    (if they aren't from the same atlas)
  - A Filter on ANY object in the middle of the draw order — a
    filter requires rendering into a TEMPORARY render texture and
    back, which fundamentally interrupts batching before and after it
  - A blend mode change between adjacent objects
  - A custom shader on a single object, different from the rest of
    the batch
```

The practical architectural consequences: group sprites sharing a texture next to each other in draw order wherever visual z-order allows it; limit the number of DISTINCT filters in a scene (not "a filter on every tenth sprite, mixed with plain ones," but either applied to a whole visual layer or not at all); for truly massive counts of uniform, simple sprites (thousands of particles), use `ParticleContainer` — a specialized container that trades away some flexibility (a simplified transform model, limited per-child filter support) for maximum batching throughput in exactly this scenario.

## `Graphics`: vector shapes — but not free every frame

`Graphics` is the API for drawing vector shapes (the analog of `fillRect`/`arc`/paths from article 01), but the result is WebGL geometry, not canvas pixels:

```javascript
const graphics = new Graphics();
graphics.rect(0, 0, 100, 100).fill(0xff3366);
graphics.circle(150, 50, 40).fill(0x33ccff);
stage.addChild(graphics);
```

The key difference from `Sprite`: moving/rotating/scaling a `Sprite` every frame is cheap — it's just changing the transform matrix over geometry and a texture that already exist. `Graphics`, when you call `clear()` and draw again, **rebuilds its geometry** (regenerates the vertex buffer) — an operation noticeably more expensive than a plain transform change.

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

The rule: use `Graphics` for static or infrequently-changing vector shapes; for shapes that genuinely need to redraw every frame in large numbers, use either a `Sprite` with a pre-baked texture, or cache the `Graphics` result into a `RenderTexture`/`cacheAsTexture` once, instead of rebuilding geometry every tick.

## `Text` vs. `BitmapText`

```javascript
const text = new Text({ text: 'Score: 0', style: { fontSize: 24, fill: 0xffffff } });
// Internally, Text renders the string via canvas 2D (measuring,
// rasterizing glyphs) and uploads the result as an ORDINARY
// texture — expensive on EVERY text/style change, fine as a static label

const bitmapText = new BitmapText({ text: 'Score: 0', style: { fontFamily: 'game-font' } });
// BitmapText assembles a string from PRE-BUILT glyph sprites of a
// pre-generated bitmap font (a character sprite atlas) — updating
// the text does NOT require re-rasterizing via canvas, cheap every frame
```

The practical choice: a score counter that updates once a second or less — `Text` is fine; an FPS counter or timer updating every frame — `BitmapText`, because canvas rasterization on every frame for `Text` creates real, noticeable overhead that `BitmapText` avoids entirely, at the cost of needing a pre-built bitmap font.

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

Conceptually, this is the same problem as hit detection on plain canvas (article 02: math checks/`isPointInPath`/color-picking), but Pixi handles it for you through the scene graph: hit testing runs automatically across the `Container` hierarchy, accounting for parent transforms, with no manual coordinate math needed.

## Filters: built-in, and a custom fragment shader

```javascript
import { BlurFilter, ColorMatrixFilter } from 'pixi.js';

sprite.filters = [new BlurFilter({ strength: 8 })];

const colorMatrix = new ColorMatrixFilter();
colorMatrix.grayscale(0.8);
sprite.filters = [colorMatrix];
```

A filter is applied by rendering the object (and sometimes some area around it) into a temporary render texture, running a fragment shader (article 04) over it, and inserting the result back into the scene — exactly why filters "break batching" (see above): it's an extra, isolated render pass, not part of the ordinary drawing flow.

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

This is a direct application of article 04's GLSL model — Pixi supplies `vTextureCoord` (a rasterization-interpolated varying) and `uTexture` (a uniform sampler), sparing you from manually setting up buffers/attributes for a full-screen pass.

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

Pixi already runs its own rAF render loop inside `Application` — you don't need (and shouldn't add) a separate `requestAnimationFrame` alongside it; your own game logic hooks in via `app.ticker.add()`, getting `deltaTime` (in "frames at a target 60fps") or `deltaMS` (in milliseconds) for its own calculations.

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

GPU resources (textures, buffers) aren't released by JS's automatic garbage collection the same way ordinary objects are — the JS wrapper object can be collected, but the GPU memory allocated for it stays occupied until `destroy()` is explicitly called.

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

This leak pattern is especially dangerous on mobile devices with limited GPU memory: the app runs fine for a few minutes, then the tab crashes or the browser forcibly reclaims the context — a typical production bug that's hard to catch in quick local testing on a powerful desktop.

## When Pixi over plain Canvas 2D, and when it's overkill

```txt
Pixi earns its place:
  - Hundreds to thousands of sprites/particles at once (batching
    solves what plain Canvas 2D hits a CPU ceiling on when drawing
    every drawImage call individually)
  - Compositions with several filters, blend modes, complex
    interactivity across many objects
  - A project that will grow in complexity (many layers, nested
    object hierarchies, texture reuse)

Overkill:
  - A handful of simple shapes/icons, a one-off simple animation —
    the library's weight and API surface aren't justified relative
    to the task; plain Canvas 2D (articles 01-03) is simpler and
    entirely sufficient
```

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
      app.destroy(true, { children: true, texture: true }); // REQUIRED cleanup —
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

This is the same "canvas as an escape hatch from React's render model" principle (article 08 covers it in depth for plain canvas) — a Pixi `Application` lives inside `useEffect`, outside React's render cycle, and must be explicitly destroyed in the cleanup function. For a more declarative style, `@pixi/react` exists (a wrapper letting you describe a scene with JSX components like `<pixiSprite>`), but it remains a thin layer over the same imperative Pixi model, not a replacement for it.

## Connection to other articles

```txt
[WebGL and GPU Fundamentals]          — draw calls, batching, shaders,
                                         textures — the foundation Pixi's
                                         entire batch renderer is built on
[Canvas 2D Fundamentals] /
[Canvas Animation and Game Loop]      — the immediate-mode model that
                                         retained-mode Pixi contrasts
                                         with; the hit detection from
                                         article 02 that Pixi handles
                                         for you through the scene graph
[Architecture and Performance for
 Canvas Apps]                          — the React integration and
                                         memory-management patterns from
                                         this article generalize to a
                                         whole application
```

## Common interview traps

- **Being unable to explain how Pixi differs from plain canvas at a model level** — conflating "Pixi uses WebGL" with "Pixi is retained mode" — both are true, but they're two DIFFERENT facts: WebGL rendering stays immediate at the GPU level; retained mode is about how YOUR code is organized on top of it.

- **Confusing Texture and BaseTexture** — not knowing that many Textures can point to one BaseTexture without a re-upload to the GPU, and that this is exactly what makes sprite atlases a batching mechanism, not just "convenient file packaging."

- **Not knowing what breaks batching** — being unable to name concrete causes (a texture swap, a filter mid-draw-order, a blend mode change) and propose architectural fixes (an atlas, grouping by texture, limiting the number of filters).

- **Assuming `Graphics` is as cheap as `Sprite` every frame** — not knowing that redrawing `Graphics` rebuilds its geometry, whereas moving a `Sprite` is just a transform-matrix change over data that already exists.

- **Not knowing the cost difference between `Text` and `BitmapText`** — proposing `Text` for a counter that updates every frame, unaware of the canvas rasterization pass on every change.

- **Not calling `destroy()`** — creating new textures/render textures inside the render loop without releasing the old ones, leading to a GPU memory leak, especially noticeable on mobile devices.

- **Not cleaning up a Pixi `Application` on React unmount** — forgetting `app.destroy()` in a `useEffect` cleanup function, accumulating leaks on every remount (route changes, React StrictMode in development).
