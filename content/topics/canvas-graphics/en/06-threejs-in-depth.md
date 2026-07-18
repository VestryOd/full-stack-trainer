# three.js in Depth

## From 2D to 3D: the same retained-mode model, plus a dimension of depth

three.js solves the same architectural problem as Pixi (article 05) — a retained-mode scene on top of WebGL (article 04) — but adds what 2D doesn't need: a camera that projects three-dimensional space onto a flat screen, lighting that answers "what does this material look like under this light," and a depth buffer for correctly ordering objects that occlude each other in 3D.

## The mental model: `Scene`, `Camera`, `Renderer`

```javascript
const scene = new THREE.Scene();                                   // the scene tree — like Pixi's stage
const camera = new THREE.PerspectiveCamera(75, aspect, 0.1, 1000);  // WHERE and HOW we're looking
const renderer = new THREE.WebGLRenderer({ antialias: true });      // a wrapper over raw WebGL (article 04)
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

renderer.render(scene, camera); // on each call: walk the scene, issue draw calls for visible objects
```

`Scene` is a tree of objects, conceptually identical to Pixi's `stage`/`Container`, just in three dimensions. `Camera` isn't "an object in the scene" — it's the definition of HOW three-dimensional coordinates turn into two-dimensional screen coordinates (the projection matrix). `Renderer` is a thin wrapper over the raw WebGL context (article 04) that generates the necessary draw calls for every visible object on each `render()` call.

## `PerspectiveCamera` vs. `OrthographicCamera`

```javascript
// Perspective: farther objects look visually smaller (like human vision)
const perspective = new THREE.PerspectiveCamera(
  75,              // fov — the vertical field of view, in degrees
  width / height,   // aspect — the viewport's aspect ratio
  0.1,              // near — the near clipping plane
  1000,             // far — the far clipping plane
);

// Orthographic: NO size reduction with distance, parallel lines stay
// parallel — CAD views, isometric games, 2D overlays inside a 3D scene
const orthographic = new THREE.OrthographicCamera(
  -width / 2, width / 2, height / 2, -height / 2, 0.1, 1000,
);
```

**`near`/`far` and z-fighting** aren't a formality — they're a real source of a visible bug. The depth buffer stores distance from the camera with precision distributed NON-LINEARLY: much more precision near `near`, considerably less near `far`. If `near` is set too small and `far` too large, two surfaces physically located at different, but close, depths can end up with ALMOST IDENTICAL values in the depth buffer — the renderer can't reliably decide which one is closer, and the result is the characteristic flicker of one surface poking through another with the slightest camera movement (z-fighting). The fix is setting `near`/`far` as tightly as possible around the scene's actual bounds, rather than "with margin just in case."

## The Geometry + Material + Mesh triad

```javascript
const geometry = new THREE.BoxGeometry(1, 1, 1); // WHAT shape (vertices)
const material = new THREE.MeshStandardMaterial({ color: 0x3366ff }); // HOW it's shaded/lit
const cube = new THREE.Mesh(geometry, material); // an object IN THE SCENE: geometry + material + transform
scene.add(cube);

cube.position.set(0, 1, 0);
cube.rotation.y = Math.PI / 4;
```

`Geometry` is responsible for the shape, `Material` for how that shape reacts to light and textures, and `Mesh` combines them and places them in the scene with its own transform — three different `Mesh` objects can reuse the SAME `Geometry`/`Material`, which ties directly into the draw-call optimizations below.

## `BufferGeometry`: the same buffers and attributes from article 04

```javascript
const geometry = new THREE.BufferGeometry();

const positions = new Float32Array([ /* x,y,z for each vertex */ ]);
geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3)); // 3 — components per vertex

const normals = new Float32Array([ /* nx,ny,nz — the "outward" direction, used for lighting */ ]);
geometry.setAttribute('normal', new THREE.BufferAttribute(normals, 3));

const uvs = new Float32Array([ /* u,v — texture-mapping coordinates */ ]);
geometry.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
```

`BufferGeometry` isn't a separate concept — it's a direct wrapper over the GPU buffers and attributes from article 04: `position` is a required attribute (nothing to draw without it), `normal` is the surface direction at each vertex, critical for computing how light bounces off it (without normals, a lit model looks "flat" or renders incorrectly), `uv` is the coordinates used to stretch a texture over the surface.

## A tour of materials: unlit → lit → PBR

```txt
MeshBasicMaterial      — NO reaction to light at all: just a flat
                           color/texture, entirely ignoring every
                           light source in the scene. The cheapest.
                           Good for 3D UI elements, wireframes,
                           deliberately "flat" stylized looks

MeshLambertMaterial     — lit, but only diffuse (matte) reflection,
                           computed PER VERTEX (cheaper, less
                           accurate) — mostly legacy/simple cases

MeshPhongMaterial       — lit, adds specular highlights, computed
                           PER PIXEL — the classic "shiny plastic"
                           look, more expensive than Lambert

MeshStandardMaterial /
MeshPhysicalMaterial     — PBR (Physically Based Rendering) — models
                           a material via roughness and metalness
                           parameters, based on an approximation of
                           real-world light physics, rather than an
                           arbitrary "highlight formula" like Phong's.
                           Produces a visually more realistic and,
                           importantly, CONSISTENT result across
                           different lighting setups. Physical adds
                           clearcoat, transmission (glass), and other
                           advanced real-world material effects
```

The practical choice: `Standard`/`Physical` is the default for anything meant to look realistic (product viewers, architectural visualization); `Basic` for a cheap/stylized/unlit look; `Phong` only for legacy code or a specific stylized "shine" at a lower cost than full PBR.

## Lights and shadows

```javascript
scene.add(new THREE.AmbientLight(0xffffff, 0.4));  // uniform light from EVERY direction,
                                                     // no direction, no shadows — just a
                                                     // "floor" of illumination so shadows
                                                     // aren't pure black

const dirLight = new THREE.DirectionalLight(0xffffff, 1); // parallel rays (like the sun)
dirLight.position.set(5, 10, 5);
dirLight.castShadow = true;
scene.add(dirLight);

const pointLight = new THREE.PointLight(0xffaa00, 1, 50); // radiates in all directions from
                                                            // a point (like a bulb), fades with distance

const spotLight = new THREE.SpotLight(0xffffff, 1, 0, Math.PI / 6); // a cone with an angle
```

**How a shadow map works:** the scene gets rendered an EXTRA TIME, FROM THE LIGHT'S POINT OF VIEW, into a depth texture (that's a second render pass, on top of the main one from the camera's viewpoint) — then in the main pass, each pixel's distance from the light is compared against the value stored in that texture: if the stored value is smaller, the pixel is in shadow (something closer to the light is blocking it).

```javascript
renderer.shadowMap.enabled = true;
mesh.castShadow = true;     // this object casts a shadow
mesh.receiveShadow = true;  // shadows fall onto this object

dirLight.shadow.mapSize.width = 2048;  // shadow map resolution: higher —
dirLight.shadow.mapSize.height = 2048; // crisper shadow edges, but more
                                          // expensive in memory and in the
                                          // time this extra pass takes
```

Shadow cost isn't an abstraction: EVERY light with `castShadow: true` needs its own EXTRA render pass per frame, and `mapSize` resolution is a direct trade-off between "sharp shadow edges" and "memory + render time" — on mobile devices, this is one of the first things cut when performance runs short.

## The render loop and resize handling

```javascript
function animate() {
  requestAnimationFrame(animate);
  renderer.render(scene, camera);
}
animate();
```

```javascript
// ❌ A stretched/distorted image after resize — aspect changed,
// but the PROJECTION MATRIX didn't
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  renderer.setSize(window.innerWidth, window.innerHeight);
});
```

```javascript
// ✅ camera.aspect (or any other camera property: fov, near, far)
// does NOT automatically recompute the projection matrix — that
// needs an explicit call after every such change
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix(); // REQUIRED after changing aspect/fov/near/far
  renderer.setSize(window.innerWidth, window.innerHeight);
});
```

## `OrbitControls` and loading real assets with `GLTFLoader`

```javascript
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; // inertia while orbiting — requires calling .update() every frame

function animate() {
  requestAnimationFrame(animate);
  controls.update(); // required when enableDamping: true
  renderer.render(scene, camera);
}
```

**Why glTF is the standard format:** glTF is designed specifically as a "runtime format," not an editing one — compact, with native support for PBR materials, skeletal animation, and morph targets, and broad export tooling support (Blender and essentially the rest of the 3D toolchain). Older formats (`.obj`, with no animation or PBR support; `.fbx`, heavier and less open) don't offer this set of features out of the box.

```javascript
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';

const dracoLoader = new DRACOLoader();
dracoLoader.setDecoderPath('/draco/'); // path to the Draco decoder files

const loader = new GLTFLoader();
loader.setDRACOLoader(dracoLoader);

loader.load('/model.glb', (gltf) => {
  scene.add(gltf.scene);
});
```

**Draco** is a geometry compression extension for glTF: it noticeably shrinks file size for complex meshes, at the cost of needing client-side decoding (`DRACOLoader`) — worth it for production scenes with complex geometry distributed over the network, especially on mobile connections.

## Textures and color space: why "the model looks washed out"

Texture images are typically stored in sRGB color space (gamma-encoded, optimized for how displays render for human perception), but a renderer's lighting math is only correct in LINEAR space. three.js needs to know which space each texture is encoded in, and which space the final color needs to be output in for the screen:

```javascript
const texture = new THREE.TextureLoader().load('/albedo.jpg');
texture.colorSpace = THREE.SRGBColorSpace; // REQUIRED for color (albedo/diffuse)
                                              // textures — without it, you get
                                              // either double sRGB decoding, or none at all

renderer.outputColorSpace = THREE.SRGBColorSpace; // correctly outputs the
                                                     // final color to the screen
```

The symptom of getting this wrong is the classic "the model looks washed out/flat," or, in the opposite case, unnaturally contrasty — this isn't a problem with the model or the lighting itself, it's a mismatch between the color spaces on the input side (the texture) and the output side (the renderer). `GLTFLoader` sets this up correctly and automatically for a model's own textures; with MANUAL texture loading via `TextureLoader` (say, a custom canvas texture), you have to set it explicitly yourself.

## Raycasting: hit-testing 3D objects with the cursor

```javascript
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();

window.addEventListener('click', (event) => {
  // Normalized device coordinates: -1..1 on both axes
  mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
  mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

  raycaster.setFromCamera(mouse, camera); // a ray FROM the camera THROUGH this screen point
  const hits = raycaster.intersectObjects(scene.children, true); // true — recurse into children

  if (hits.length > 0) {
    console.log('Clicked:', hits[0].object); // hits[0] — the CLOSEST intersection
  }
});
```

This is the 3D analog of hit detection from article 02 (math checks on canvas) and `hitArea` in Pixi (article 05) — instead of 2D geometry, this computes a ray's intersection with a mesh's triangles in three-dimensional space, with results sorted by distance from the camera.

## Animation: `AnimationMixer` vs. manually transforming in the loop

```javascript
// For AUTHORED animation (skeletal animation, morph targets),
// exported from Blender/Maya along with the model
const mixer = new THREE.AnimationMixer(gltf.scene);
const action = mixer.clipAction(gltf.animations[0]);
action.play();

function animate(deltaTime) {
  mixer.update(deltaTime); // MUST be called every frame with the real dt
  renderer.render(scene, camera);
}
```

```javascript
// For simple procedural motion (a spinning product in a viewer) —
// AnimationMixer is overkill; an ordinary transform mutation in the
// loop is simpler
function animate(deltaTime) {
  productMesh.rotation.y += deltaTime * 0.5;
  renderer.render(scene, camera);
}
```

The rule: `AnimationMixer` is for playing back REAL animation clips created by an animator and exported with the model; for your own, code-written procedural animation (rotation, bobbing, following the cursor), directly mutating `position`/`rotation`/`scale` in the render loop is entirely sufficient and needs no `AnimationMixer` at all.

## Performance: reducing draw call count

Article 04: real-world GPU rendering cost in most scenes is driven by the NUMBER of draw calls, not raw triangle count. three.js gives you two direct tools for this:

```javascript
// InstancedMesh — thousands of copies of ONE geometry+material in ONE draw call
const instancedMesh = new THREE.InstancedMesh(treeGeometry, treeMaterial, 5000);
const matrix = new THREE.Matrix4();

for (let i = 0; i < 5000; i++) {
  matrix.setPosition(Math.random() * 100 - 50, 0, Math.random() * 100 - 50);
  instancedMesh.setMatrixAt(i, matrix); // its own transform PER INSTANCE
}
scene.add(instancedMesh); // a "forest" of 5000 trees — ONE draw call instead of 5000
```

```javascript
// Merging geometries for DIFFERENT static objects sharing a material
// that don't need an independent runtime transform
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
const merged = mergeGeometries([rockGeometry1, rockGeometry2, rockGeometry3]);
const rocksMesh = new THREE.Mesh(merged, rockMaterial); // one Mesh instead of three
```

```javascript
// Capping pixelRatio — critical on mobile: retina displays with
// devicePixelRatio 3 would otherwise render at triple the internal
// resolution per side, with no perceptible benefit past ~2x
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
```

## `dispose()`: the leak almost everyone ships to production

Just like Pixi (article 05), three.js's GPU resources (geometry, materials, textures) aren't released automatically by JS garbage collection — the wrapper JS object can be collected while the GPU memory allocated for it stays held:

```javascript
// ❌ The classic leak: loading a new model on a route change
// WITHOUT releasing the previous scene's resources
function loadNewModel(url) {
  scene.clear(); // removes objects from the scene, but does NOT release their GPU resources
  loader.load(url, (gltf) => scene.add(gltf.scene));
}
```

```javascript
// ✅ Explicitly walk the scene and dispose() geometry/material/textures before replacing it
function disposeSceneContents(scene) {
  scene.traverse((object) => {
    if (object.geometry) object.geometry.dispose();
    if (object.material) {
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      materials.forEach((material) => {
        Object.values(material).forEach((value) => {
          if (value?.isTexture) value.dispose(); // textures embedded in the material
        });
        material.dispose();
      });
    }
  });
}

function loadNewModel(url) {
  disposeSceneContents(scene);
  scene.clear();
  loader.load(url, (gltf) => scene.add(gltf.scene));
}
```

This is an especially common bug in product configurators and viewers, where a user switches models/variants many times per session — without explicit `dispose()`, GPU memory grows with every switch until the tab crashes.

## Ecosystem: react-three-fiber + drei

```tsx
import { Canvas } from '@react-three/fiber';
import { OrbitControls, useGLTF } from '@react-three/drei';

function Model() {
  const { scene } = useGLTF('/model.glb'); // a hook with load caching built in
  return <primitive object={scene} />;
}

function ProductViewer() {
  return (
    <Canvas camera={{ position: [0, 1, 5], fov: 50 }}>
      <ambientLight intensity={0.4} />
      <directionalLight position={[5, 10, 5]} castShadow />
      <Model />
      <OrbitControls />
    </Canvas>
  );
}
```

`react-three-fiber` is a declarative React renderer for a three.js scene: JSX components (`<mesh>`, `<ambientLight>`) map directly onto three.js objects, and mounting/unmounting/cleanup are handled by React's lifecycle automatically — what article 05 (Pixi + React) and article 08 (canvas + React) do by hand via `useEffect`, here is abstracted at the library level. `drei` is a collection of ready-made helpers on top of this (an `OrbitControls` wrapper, a `useGLTF` hook with caching, ready-made lighting/environment presets). Prefer this pairing for React apps where component composition matters more than manual micro-control over every scene detail (product configurators, interactive 3D UI); drop down to raw three.js when you need very fine-grained control, or integration entirely outside React.

## The shader escape hatch: `ShaderMaterial`

When built-in materials can't express the effect you need, `ShaderMaterial` gives direct access to article 04's GLSL model:

```javascript
const material = new THREE.ShaderMaterial({
  uniforms: { uTime: { value: 0 } },
  vertexShader: `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: `
    uniform float uTime;
    varying vec2 vUv;
    void main() {
      gl_FragColor = vec4(vUv.x, vUv.y, sin(uTime) * 0.5 + 0.5, 1.0);
    }
  `,
});

function animate(deltaTime) {
  material.uniforms.uTime.value += deltaTime; // the uniform is updated manually from JS
  renderer.render(scene, camera);
}
```

This is a direct application of `attribute`/`uniform`/`varying` from article 04 — three.js supplies the built-in variables (`position`, `uv`, `projectionMatrix`, `modelViewMatrix`) automatically, leaving you to write only the meaningful part of the shader.

## Connection to other articles

```txt
[WebGL and GPU Fundamentals]          — buffer/attribute/uniform/draw
                                         call — the foundation that
                                         BufferGeometry, Material, and
                                         InstancedMesh wrap
[Pixi.js in Depth]                    — the same retained-mode model
                                         and the same draw-call economics,
                                         just in 2D
[Architecture and Performance for
 Canvas Apps]                          — the dispose() discipline and
                                         React integration from this
                                         article generalize to a whole application
```

## Common interview traps

- **Forgetting `updateProjectionMatrix()` after a resize** — knowing you need to change `camera.aspect`, but not knowing that alone doesn't recompute the projection matrix, producing a stretched image.

- **Being unable to explain z-fighting** — not connecting flickering overlapping surfaces to the depth buffer's non-linear precision distribution and a too-wide `near`/`far` range.

- **Confusing materials by purpose** — being unable to explain the difference between unlit (`Basic`), lit non-PBR (`Lambert`/`Phong`), and PBR (`Standard`/`Physical`), and when each is justified.

- **Not knowing shadows' cost** — not understanding that every shadow-casting light is an extra render pass, and that shadow map resolution is a direct quality/performance trade-off.

- **Not knowing about sRGB/color spaces** — blaming "the model looks washed out" on "bad lighting" or "a bad model," without checking `texture.colorSpace`/`renderer.outputColorSpace`.

- **Not calling `dispose()` when swapping scenes/models** — not knowing that geometry/materials/textures aren't automatically collected by the JS garbage collector, leading to growing GPU memory on repeated model loads.

- **Not knowing about `InstancedMesh`** — trying to draw thousands of identical objects as ordinary `Mesh` instances, unaware that's thousands of separate draw calls instead of one.

- **Having no opinion on react-three-fiber vs. raw three.js** — being unable to explain what `react-three-fiber` abstracts (lifecycle, declarativeness) and when direct control through the raw API is the better call.
