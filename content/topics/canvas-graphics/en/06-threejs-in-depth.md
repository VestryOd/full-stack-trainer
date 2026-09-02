# three.js in Depth

## From 2D to 3D: the same retained-mode model, plus a dimension of depth

three.js is a retained-mode scene on top of WebGL (Web Graphics Library), plus everything 3D needs that 2D doesn't. The architectural problem is the same one Pixi solves in article 05, and the WebGL layer underneath is article 04.

Three things are new:

- A camera that projects three-dimensional space onto a flat screen.
- Lighting that answers "what does this material look like under this light".
- A depth buffer, for correctly ordering objects that occlude each other in 3D.

## The mental model: `Scene`, `Camera`, `Renderer`

```javascript
// the scene tree — like Pixi's stage
const scene = new THREE.Scene();

// where and how we're looking
const camera = new THREE.PerspectiveCamera(75, aspect, 0.1, 1000);

// a wrapper over raw WebGL (article 04)
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

// on each call: walk the scene, issue draw calls for visible objects
renderer.render(scene, camera);
```

`Scene` is a tree of objects, conceptually identical to Pixi's `stage`/`Container`, just in three dimensions.

`Camera` isn't "an object in the scene". It's the definition of **how** three-dimensional coordinates turn into two-dimensional screen coordinates, that is the projection matrix.

`Renderer` is a thin wrapper over the raw WebGL context (article 04). On each `render()` call it generates the draw calls needed for every visible object.

## `PerspectiveCamera` vs. `OrthographicCamera`

```javascript
// Perspective: farther objects look visually smaller (like human vision)
const perspective = new THREE.PerspectiveCamera(
  75,              // fov — the vertical field of view, in degrees
  width / height,   // aspect — the viewport's aspect ratio
  0.1,              // near — the near clipping plane
  1000,             // far — the far clipping plane
);

// Orthographic: no size reduction with distance, parallel lines stay
// parallel — CAD (computer-aided design) views, isometric games,
// 2D overlays inside a 3D scene
const orthographic = new THREE.OrthographicCamera(
  -width / 2, width / 2, height / 2, -height / 2, 0.1, 1000,
);
```

**`near`/`far` and z-fighting** aren't a formality. They're a real source of a visible bug.

The depth buffer stores distance from the camera with precision distributed **non-linearly**: much more precision near `near`, considerably less near `far`.

Set `near` too small and `far` too large, and two surfaces at physically different but close depths can get almost identical depth-buffer values. The renderer then can't reliably decide which one is closer.

The result is the characteristic flicker of one surface poking through another at the slightest camera movement. That is z-fighting. The fix is setting `near`/`far` as tightly as possible around the scene's actual bounds, rather than "with margin just in case".

## The Geometry + Material + Mesh triad

```javascript
const geometry = new THREE.BoxGeometry(1, 1, 1);  // what shape (vertices)

// how it's shaded and lit
const material = new THREE.MeshStandardMaterial({ color: 0x3366ff });

// an object in the scene: geometry + material + transform
const cube = new THREE.Mesh(geometry, material);
scene.add(cube);

cube.position.set(0, 1, 0);
cube.rotation.y = Math.PI / 4;
```

`Geometry` is responsible for the shape. `Material` is responsible for how that shape reacts to light and textures. `Mesh` combines them and places them in the scene with its own transform.

Three different `Mesh` objects can reuse the **same** `Geometry` and `Material`, which ties directly into the draw-call optimizations below.

## `BufferGeometry`: the same buffers and attributes from article 04

```javascript
const geometry = new THREE.BufferGeometry();

const positions = new Float32Array([ /* x,y,z for each vertex */ ]);
// 3 — components per vertex
geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

// nx,ny,nz — the "outward" direction, used for lighting
const normals = new Float32Array([ /* ... */ ]);
geometry.setAttribute('normal', new THREE.BufferAttribute(normals, 3));

// u,v — texture-mapping coordinates
const uvs = new Float32Array([ /* ... */ ]);
geometry.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
```

`BufferGeometry` isn't a separate concept. It's a direct wrapper over the GPU (graphics processing unit) buffers and attributes from article 04:

- `position` is a required attribute — there is nothing to draw without it.
- `normal` is the surface direction at each vertex, critical for computing how light bounces off it. Without normals, a lit model looks "flat" or renders incorrectly.
- `uv` is the coordinates used to stretch a texture over the surface.

## A tour of materials: unlit → lit → PBR

Materials differ in how they react to light. PBR below stands for physically based rendering.

| Material | How it reacts to light | Where it fits |
|---|---|---|
| `MeshBasicMaterial` | No reaction to light at all: a flat color or texture, ignoring every light source in the scene. The cheapest one. | 3D interface elements, wireframes, deliberately "flat" stylized looks. |
| `MeshLambertMaterial` | Lit, but only diffuse (matte) reflection, computed per vertex. Cheaper and less accurate. | Mostly legacy and simple cases. |
| `MeshPhongMaterial` | Lit, and adds specular highlights computed per pixel. More expensive than Lambert. | The classic "shiny plastic" look. |
| `MeshStandardMaterial` and `MeshPhysicalMaterial` | Physically based rendering. The material is described by roughness and metalness, from an approximation of real-world light physics. That replaces an arbitrary "highlight formula" like Phong's. | Visually more realistic results that stay consistent across different lighting setups. `Physical` adds clearcoat, transmission (glass) and other advanced real-world effects. |

The practical choice: `Standard` or `Physical` is the default for anything meant to look realistic, such as product viewers and architectural visualization. `Basic` is for a cheap, stylized, unlit look. `Phong` is for legacy code, or for a specific stylized "shine" at a lower cost than full physically based rendering.

## Lights and shadows

```javascript
// uniform light from every direction, no direction, no shadows —
// just a "floor" of illumination so shadows aren't pure black
scene.add(new THREE.AmbientLight(0xffffff, 0.4));

// parallel rays (like the sun)
const dirLight = new THREE.DirectionalLight(0xffffff, 1);
dirLight.position.set(5, 10, 5);
dirLight.castShadow = true;
scene.add(dirLight);

// radiates in all directions from a point (like a bulb),
// fades with distance
const pointLight = new THREE.PointLight(0xffaa00, 1, 50);

// a cone with an angle
const spotLight = new THREE.SpotLight(0xffffff, 1, 0, Math.PI / 6);
```

**How a shadow map works.** The scene gets rendered an extra time, from the light's point of view, into a depth texture. That is a second render pass, on top of the main one from the camera's viewpoint.

Then, in the main pass, each pixel's distance from the light is compared against the value stored in that texture. If the stored value is smaller, the pixel is in shadow: something closer to the light is blocking it.

```javascript
renderer.shadowMap.enabled = true;
mesh.castShadow = true;     // this object casts a shadow
mesh.receiveShadow = true;  // shadows fall onto this object

dirLight.shadow.mapSize.width = 2048;  // shadow map resolution: higher —
dirLight.shadow.mapSize.height = 2048; // crisper shadow edges, but more
                                          // expensive in memory and in the
                                          // time this extra pass takes
```

Shadow cost isn't an abstraction. Every light with `castShadow: true` needs its own extra render pass per frame.

And `mapSize` resolution is a direct trade-off between "sharp shadow edges" and "memory plus render time". On mobile devices this is one of the first things cut when performance runs short.

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
// but the projection matrix didn't
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  renderer.setSize(window.innerWidth, window.innerHeight);
});
```

```javascript
// ✅ camera.aspect (or any other camera property: fov, near, far)
// does not automatically recompute the projection matrix — that
// needs an explicit call after every such change
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix(); // required after changing aspect/fov/near/far
  renderer.setSize(window.innerWidth, window.innerHeight);
});
```

## `OrbitControls` and loading real assets with `GLTFLoader`

```javascript
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

const controls = new OrbitControls(camera, renderer.domElement);
// inertia while orbiting — requires calling .update() every frame
controls.enableDamping = true;

function animate() {
  requestAnimationFrame(animate);
  controls.update(); // required when enableDamping: true
  renderer.render(scene, camera);
}
```

**Why glTF is the standard format.** glTF is designed specifically as a "runtime format", not an editing one. It is compact, with native support for physically based materials, skeletal animation and morph targets. Export tooling support is broad too: Blender and essentially the rest of the 3D toolchain.

Older formats don't offer this set of features out of the box. The `.obj` format has no animation and no physically based rendering support. And `.fbx` is heavier and less open.

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

**Draco** is a geometry compression extension for glTF. It noticeably shrinks file size for complex meshes, at the cost of needing decoding in the browser through `DRACOLoader`. It is worth doing for production scenes with complex geometry sent over the network, especially on mobile connections.

## Textures and color space: why "the model looks washed out"

Texture images are typically stored in sRGB color space. That means gamma-encoded, optimized for how displays render for human perception. A renderer's lighting math, though, is only correct in linear space.

So three.js needs to know two things. Which color space each texture is encoded in, and which space the final color must be output in for the screen:

```javascript
const texture = new THREE.TextureLoader().load('/albedo.jpg');
texture.colorSpace = THREE.SRGBColorSpace; // required for color (albedo/diffuse)
                                              // textures — without it, you get
                                              // either double sRGB decoding, or none at all

renderer.outputColorSpace = THREE.SRGBColorSpace; // correctly outputs the
                                                     // final color to the screen
```

The symptom of getting this wrong is the classic "the model looks washed out and flat". In the opposite case it looks unnaturally high in contrast.

Neither is a problem with the model or the lighting itself. It's a mismatch between the color spaces on the input side, the texture, and the output side, the renderer.

`GLTFLoader` sets this up correctly and automatically for a model's own textures. With manual texture loading via `TextureLoader` — say, a custom canvas texture — you have to set it explicitly yourself.

## Raycasting: hit-testing 3D objects with the cursor

```javascript
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();

window.addEventListener('click', (event) => {
  // Normalized device coordinates: -1..1 on both axes
  mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
  mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

  // a ray from the camera through this screen point
  raycaster.setFromCamera(mouse, camera);

  // true — recurse into children
  const hits = raycaster.intersectObjects(scene.children, true);

  if (hits.length > 0) {
    console.log('Clicked:', hits[0].object); // hits[0] — the closest hit
  }
});
```

This is the 3D analog of hit detection from article 02, the math checks on canvas, and of `hitArea` in Pixi (article 05). Instead of 2D geometry, it computes a ray's intersection with a mesh's triangles in three-dimensional space, with results sorted by distance from the camera.

## Animation: `AnimationMixer` vs. manually transforming in the loop

```javascript
// For authored animation (skeletal animation, morph targets),
// exported from Blender/Maya along with the model
const mixer = new THREE.AnimationMixer(gltf.scene);
const action = mixer.clipAction(gltf.animations[0]);
action.play();

// deltaTime here is seconds since the previous frame. A bare
// requestAnimationFrame callback receives a timestamp, not a delta —
// derive it yourself, or take it from THREE.Clock().getDelta()
function animate(deltaTime) {
  mixer.update(deltaTime); // must be called every frame with the real dt
  renderer.render(scene, camera);
}
```

```javascript
// For simple procedural motion (a spinning product in a viewer) —
// AnimationMixer is overkill; an ordinary transform mutation in the
// loop is simpler
function animate(deltaTime) { // deltaTime in seconds, as above
  productMesh.rotation.y += deltaTime * 0.5;
  renderer.render(scene, camera);
}
```

The rule: `AnimationMixer` is for playing back real animation clips, created by an animator and exported with the model.

For your own procedural animation written in code — rotation, bobbing, following the cursor — mutate `position`/`rotation`/`scale` directly in the render loop. That is entirely sufficient, and needs no `AnimationMixer` at all.

## Performance: reducing draw call count

Article 04 established that real-world GPU rendering cost in most scenes is driven by the **number** of draw calls, not raw triangle count. There are two direct tools for this in three.js:

```javascript
// InstancedMesh — thousands of copies of one geometry+material in one draw call
const instancedMesh = new THREE.InstancedMesh(treeGeometry, treeMaterial, 5000);
const matrix = new THREE.Matrix4();

for (let i = 0; i < 5000; i++) {
  matrix.setPosition(Math.random() * 100 - 50, 0, Math.random() * 100 - 50);
  instancedMesh.setMatrixAt(i, matrix); // its own transform per instance
}
scene.add(instancedMesh); // a "forest" of 5000 trees — one draw call instead of 5000
```

```javascript
// Merging geometries for different static objects sharing a material
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

Just like Pixi (article 05), three.js GPU resources — geometry, materials, textures — aren't released automatically by JS garbage collection. The wrapper JS object can be collected while the GPU memory allocated for it stays held:

```javascript
// ❌ The classic leak: loading a new model on a route change
// without releasing the previous scene's resources
function loadNewModel(url) {
  // removes objects from the scene, but does not release their GPU resources
  scene.clear();
  loader.load(url, (gltf) => scene.add(gltf.scene));
}
```

```javascript
// ✅ Explicitly walk the scene and dispose() geometry/material/textures before replacing it
function disposeSceneContents(scene) {
  scene.traverse((object) => {
    if (object.geometry) object.geometry.dispose();
    if (object.material) {
      const materials = Array.isArray(object.material)
        ? object.material
        : [object.material];
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

This is an especially common bug in product configurators and viewers, where a user switches models or variants many times per session. Without an explicit `dispose()`, GPU memory grows with every switch until the tab crashes.

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

`react-three-fiber` is a declarative React renderer for a three.js scene. JSX (a syntax extension for JavaScript) components such as `<mesh>` and `<ambientLight>` map directly onto three.js objects. Mounting, unmounting and cleanup are handled by React's lifecycle automatically.

What article 05 (Pixi + React) and article 08 (canvas + React) do by hand via `useEffect` is abstracted here at the library level.

`drei` is a collection of ready-made helpers on top of this: an `OrbitControls` wrapper, a `useGLTF` hook with caching, ready-made lighting and environment presets.

Prefer this pairing for React apps where component composition matters more than manual micro-control over every scene detail. Product configurators and interactive 3D interfaces are the typical case. Use raw three.js when you need very fine-grained control, or integration entirely outside React.

## The shader escape hatch: `ShaderMaterial`

When built-in materials can't express the effect you need, `ShaderMaterial` gives direct access to the GLSL (OpenGL Shading Language) model from article 04:

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

function animate(deltaTime) { // deltaTime in seconds, as above
  material.uniforms.uTime.value += deltaTime; // the uniform is updated manually from JS
  renderer.render(scene, camera);
}
```

This is a direct application of `attribute`/`uniform`/`varying` from article 04. The built-in variables are supplied automatically — `position`, `uv`, `projectionMatrix`, `modelViewMatrix` — leaving you to write only the meaningful part of the shader.

## Connection to other articles

- [WebGL and GPU Fundamentals](./04-webgl-and-gpu-fundamentals.md) — buffer, attribute, uniform and draw call: the foundation that `BufferGeometry`, `Material` and `InstancedMesh` wrap.
- [Pixi.js in Depth](./05-pixijs-in-depth.md) — the same retained-mode model and the same draw-call economics, just in 2D.
- [Architecture and Performance for Canvas Apps](./08-architecture-and-performance-for-canvas-apps.md) — the `dispose()` discipline and React integration from this article generalize to a whole application.

## Common interview traps

- **Forgetting `updateProjectionMatrix()` after a resize** — knowing you need to change `camera.aspect`, but not knowing that this alone doesn't recompute the projection matrix. The result is a stretched image.

- **Being unable to explain z-fighting** — not connecting flickering overlapping surfaces to the depth buffer's non-linear precision distribution and a too-wide `near`/`far` range.

- **Confusing materials by purpose** — being unable to explain the difference between unlit (`Basic`), lit but not physically based (`Lambert`/`Phong`), and physically based (`Standard`/`Physical`). And not knowing when each is justified.

- **Not knowing shadows' cost** — not understanding that every shadow-casting light is an extra render pass. Shadow map resolution is a direct quality-versus-performance trade-off.

- **Not knowing about sRGB and color spaces** — blaming "the model looks washed out" on bad lighting or a bad model. What goes unchecked is `texture.colorSpace` and `renderer.outputColorSpace`.

- **Not calling `dispose()` when swapping scenes or models** — not knowing that geometry, materials and textures aren't collected automatically by the JS garbage collector. GPU memory then grows on repeated model loads.

- **Not knowing about `InstancedMesh`** — trying to draw thousands of identical objects as ordinary `Mesh` instances. That is thousands of separate draw calls instead of one.

- **Having no opinion on react-three-fiber versus raw three.js** — being unable to explain what `react-three-fiber` abstracts, namely lifecycle and declarativeness. And not knowing when direct control through the raw API is the better call.
