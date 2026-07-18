# three.js в деталях

## От 2D к 3D: та же retained-mode модель, плюс измерение глубины

three.js решает ту же архитектурную задачу, что Pixi (статья 05) — retained-mode сцена поверх WebGL (статья 04), — но добавляет то, чего нет в 2D: камеру с проекцией трёхмерного пространства на плоский экран, освещение, отвечающее на вопрос "как этот материал выглядит при таком-то свете", и буфер глубины для правильного порядка отрисовки объектов, перекрывающих друг друга в 3D.

## Ментальная модель: `Scene`, `Camera`, `Renderer`

```javascript
const scene = new THREE.Scene();                                   // дерево сцены — как stage в Pixi
const camera = new THREE.PerspectiveCamera(75, aspect, 0.1, 1000);  // ГДЕ и КАК смотрим
const renderer = new THREE.WebGLRenderer({ antialias: true });      // обёртка над сырым WebGL (статья 04)
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

renderer.render(scene, camera); // на каждый вызов: пройти сцену, выполнить draw call'ы для видимых объектов
```

`Scene` — дерево объектов, концептуально идентичное `stage`/`Container` в Pixi, но в трёх измерениях. `Camera` — не "объект в сцене", а определение того, КАК трёхмерные координаты превращаются в двумерные координаты экрана (матрица проекции). `Renderer` — тонкая обёртка над сырым WebGL-контекстом (статья 04), которая на каждый `render()` генерирует необходимые draw call'ы для всех видимых объектов.

## `PerspectiveCamera` vs `OrthographicCamera`

```javascript
// Перспектива: объекты дальше — визуально меньше (как человеческое зрение)
const perspective = new THREE.PerspectiveCamera(
  75,              // fov — угол обзора по вертикали, в градусах
  width / height,   // aspect — соотношение сторон вьюпорта
  0.1,              // near — ближняя плоскость отсечения
  1000,             // far — дальняя плоскость отсечения
);

// Ортографическая: НЕТ уменьшения с расстоянием, параллельные линии
// остаются параллельными — CAD-виды, изометрические игры, 2D-оверлеи в 3D-сцене
const orthographic = new THREE.OrthographicCamera(
  -width / 2, width / 2, height / 2, -height / 2, 0.1, 1000,
);
```

**`near`/`far` и z-fighting** — не формальность, а источник реального визуального бага. Буфер глубины хранит расстояние до камеры с точностью, распределённой НЕЛИНЕЙНО: больше точности рядом с `near`, значительно меньше — рядом с `far`. Если задать `near` слишком маленьким, а `far` — слишком большим, две поверхности, физически расположенные на разной, но близкой глубине, могут получить ПОЧТИ ОДИНАКОВОЕ значение в буфере глубины — рендерер не может надёжно решить, какая из них ближе, и результат — характерное мерцание/пробивание одной поверхности сквозь другую при малейшем движении камеры (z-fighting). Фикс — задавать `near`/`far` максимально плотно вокруг реальных границ сцены, а не "с запасом на всякий случай".

## Триада Geometry + Material + Mesh

```javascript
const geometry = new THREE.BoxGeometry(1, 1, 1); // ЧТО за форма (вершины)
const material = new THREE.MeshStandardMaterial({ color: 0x3366ff }); // КАК это закрашено/освещено
const cube = new THREE.Mesh(geometry, material); // объект В СЦЕНЕ: geometry + material + трансформация
scene.add(cube);

cube.position.set(0, 1, 0);
cube.rotation.y = Math.PI / 4;
```

`Geometry` отвечает за форму, `Material` — за то, как эта форма реагирует на свет и текстуры, `Mesh` объединяет их и размещает в сцене с собственной трансформацией — три разных `Mesh` могут переиспользовать ОДНУ и ту же `Geometry`/`Material`, что напрямую связано с оптимизацией draw call'ов ниже.

## `BufferGeometry`: то же самое, что буферы и атрибуты из статьи 04

```javascript
const geometry = new THREE.BufferGeometry();

const positions = new Float32Array([ /* x,y,z для каждой вершины */ ]);
geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3)); // 3 — компонент на вершину

const normals = new Float32Array([ /* nx,ny,nz — направление "наружу" для расчёта освещения */ ]);
geometry.setAttribute('normal', new THREE.BufferAttribute(normals, 3));

const uvs = new Float32Array([ /* u,v — координаты для наложения текстуры */ ]);
geometry.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
```

`BufferGeometry` — не отдельная концепция, а прямая обёртка над GPU-буферами и атрибутами из статьи 04: `position` — обязательный атрибут (без него нечего рисовать), `normal` — направление поверхности в каждой вершине, критичное для расчёта того, как свет отражается (без нормалей освещённая модель выглядит "плоской" или рендерится неправильно), `uv` — координаты для натягивания текстуры на поверхность.

## Тур по материалам: unlit → lit → PBR

```txt
MeshBasicMaterial      — БЕЗ реакции на свет вообще: просто плоский
                           цвет/текстура, полностью игнорирует все
                           источники света в сцене. Самый дешёвый.
                           Годится для UI-элементов в 3D, wireframe,
                           намеренно "плоского" стилизованного вида

MeshLambertMaterial     — освещённый, но только диффузное (матовое)
                           отражение, посчитанное ПО ВЕРШИНАМ (дешевле,
                           менее точно) — в основном legacy/простые случаи

MeshPhongMaterial       — освещённый, добавляет бликовые (specular)
                           отражения, расчёт ПО ПИКСЕЛЯМ — классический
                           вид "глянцевого пластика", дороже Lambert

MeshStandardMaterial /
MeshPhysicalMaterial     — PBR (Physically Based Rendering) — модель
                           материала через параметры roughness
                           (шероховатость) и metalness (металличность),
                           основанная на приближении реальной физики
                           света, а не на произвольной "формуле блика"
                           как в Phong. Даёт визуально более реалистичный
                           и, что важно, ПОСЛЕДОВАТЕЛЬНЫЙ результат при
                           разных условиях освещения. Physical
                           дополнительно даёт clearcoat, transmission
                           (стекло) и другие продвинутые эффекты
                           реальных материалов
```

Практический выбор: `Standard`/`Physical` — дефолт для всего, что должно выглядеть реалистично (продуктовые вьюеры, архитектурная визуализация); `Basic` — для дешёвого/стилизованного/безосветного вида; `Phong` — только для legacy-кода или специфического стилизованного "глянца" по более низкой цене, чем полноценный PBR.

## Свет и тени

```javascript
scene.add(new THREE.AmbientLight(0xffffff, 0.4));  // равномерный свет со ВСЕХ сторон,
                                                     // без направления и без теней —
                                                     // просто "пол" освещённости,
                                                     // чтобы тени не были чисто чёрными

const dirLight = new THREE.DirectionalLight(0xffffff, 1); // параллельные лучи (как солнце)
dirLight.position.set(5, 10, 5);
dirLight.castShadow = true;
scene.add(dirLight);

const pointLight = new THREE.PointLight(0xffaa00, 1, 50); // излучает во все стороны из точки
                                                            // (как лампочка), затухает с расстоянием

const spotLight = new THREE.SpotLight(0xffffff, 1, 0, Math.PI / 6); // конус с углом
```

**Механика shadow map:** сцена дополнительно рендерится ОДИН РАЗ С ТОЧКИ ЗРЕНИЯ ИСТОЧНИКА СВЕТА в текстуру глубины (это уже второй render pass, помимо основного, с точки зрения камеры) — затем в основном проходе для каждого пикселя сравнивается его расстояние до источника света с сохранённым в этой текстуре значением: если сохранённое значение меньше — пиксель в тени (что-то ближе к свету загораживает его).

```javascript
renderer.shadowMap.enabled = true;
mesh.castShadow = true;     // этот объект отбрасывает тень
mesh.receiveShadow = true;  // на этот объект тени падают

dirLight.shadow.mapSize.width = 2048;  // разрешение shadow map: выше —
dirLight.shadow.mapSize.height = 2048; // чётче края тени, но дороже
                                          // по памяти и по времени рендера
                                          // этого дополнительного прохода
```

Стоимость теней — не абстракция: КАЖДЫЙ источник света с `castShadow: true` требует своего ДОПОЛНИТЕЛЬНОГО render pass на кадр, и разрешение `mapSize` — прямой компромисс "чёткость краёв тени" против "память + время рендера" — на мобильных устройствах это одна из первых вещей, которую урезают при нехватке производительности.

## Игровой цикл и обработка resize

```javascript
function animate() {
  requestAnimationFrame(animate);
  renderer.render(scene, camera);
}
animate();
```

```javascript
// ❌ Растянутое/искажённое изображение после resize —
// aspect поменялся, а МАТРИЦА ПРОЕКЦИИ — нет
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  renderer.setSize(window.innerWidth, window.innerHeight);
});
```

```javascript
// ✅ camera.aspect (и любое другое свойство камеры: fov, near, far)
// НЕ пересчитывает матрицу проекции автоматически — это нужно
// сделать явным вызовом после каждого такого изменения
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix(); // ОБЯЗАТЕЛЬНО после смены aspect/fov/near/far
  renderer.setSize(window.innerWidth, window.innerHeight);
});
```

## `OrbitControls` и загрузка реальных ассетов через `GLTFLoader`

```javascript
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; // инерция при вращении — требует .update() каждый кадр

function animate() {
  requestAnimationFrame(animate);
  controls.update(); // обязателен при enableDamping: true
  renderer.render(scene, camera);
}
```

**Почему glTF — стандартный формат:** glTF спроектирован именно как "формат для рантайма", а не для редактирования — компактный, с нативной поддержкой PBR-материалов, скелетной анимации и morph targets, широкой поддержкой инструментов экспорта (Blender и практически весь остальной 3D-тулинг). Более старые форматы (`.obj` без анимации и PBR, `.fbx` — тяжелее и менее открыт) не дают этого набора "из коробки".

```javascript
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';

const dracoLoader = new DRACOLoader();
dracoLoader.setDecoderPath('/draco/'); // путь к decoder-файлам Draco

const loader = new GLTFLoader();
loader.setDRACOLoader(dracoLoader);

loader.load('/model.glb', (gltf) => {
  scene.add(gltf.scene);
});
```

**Draco** — расширение сжатия геометрии для glTF: заметно уменьшает размер файла для сложных мешей ценой необходимости декодирования на клиенте (`DRACOLoader`) — оправдано для продакшен-сцен со сложной геометрией, распространяемых по сети, особенно на мобильном трафике.

## Текстуры и цветовые пространства: причина "модель выглядит блёклой"

Изображения-текстуры обычно хранятся в sRGB-цветовом пространстве (гамма-кодировка, оптимизированная под восприятие экрана человеком), но математика освещения в рендерере корректно работает в ЛИНЕЙНОМ пространстве. three.js должен знать, в каком пространстве закодирована каждая текстура, и в каком пространстве нужно выдать финальный цвет на экран:

```javascript
const texture = new THREE.TextureLoader().load('/albedo.jpg');
texture.colorSpace = THREE.SRGBColorSpace; // ОБЯЗАТЕЛЬНО для цветных
                                              // (albedo/diffuse) текстур —
                                              // без этого либо двойное,
                                              // либо отсутствующее
                                              // sRGB-декодирование

renderer.outputColorSpace = THREE.SRGBColorSpace; // корректный вывод
                                                     // финального цвета на экран
```

Симптом неправильной настройки — классический "модель выглядит блёклой/плоской" или, наоборот, неестественно контрастной: это не проблема с самой моделью или освещением, а рассинхронизация цветовых пространств на входе (текстура) и на выходе (рендерер). `GLTFLoader` для собственных текстур модели настраивает это автоматически корректно; при РУЧНОЙ загрузке текстур через `TextureLoader` (например, кастомная canvas-текстура) — это нужно выставлять явно самому.

## Raycasting: попадание курсора в 3D-объект

```javascript
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();

window.addEventListener('click', (event) => {
  // Нормализованные координаты устройства: -1..1 по обеим осям
  mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
  mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

  raycaster.setFromCamera(mouse, camera); // луч ОТ камеры ЧЕРЕЗ эту точку экрана
  const hits = raycaster.intersectObjects(scene.children, true); // true — рекурсивно

  if (hits.length > 0) {
    console.log('Clicked:', hits[0].object); // hits[0] — БЛИЖАЙШЕЕ пересечение
  }
});
```

Это 3D-аналог hit detection из статьи 02 (математические проверки на canvas) и `hitArea` в Pixi (статья 05) — вместо 2D-геометрии здесь считается пересечение луча с треугольниками мешей в трёхмерном пространстве, и результат отсортирован по расстоянию от камеры.

## Анимация: `AnimationMixer` vs ручная трансформация в цикле

```javascript
// Для АВТОРСКИХ анимаций (скелетная анимация, morph targets),
// экспортированных из Blender/Maya вместе с моделью
const mixer = new THREE.AnimationMixer(gltf.scene);
const action = mixer.clipAction(gltf.animations[0]);
action.play();

function animate(deltaTime) {
  mixer.update(deltaTime); // ОБЯЗАН вызываться каждый кадр с реальным dt
  renderer.render(scene, camera);
}
```

```javascript
// Для простого процедурного движения (вращающийся продукт в вьюере) —
// AnimationMixer избыточен, обычная мутация трансформации в цикле проще
function animate(deltaTime) {
  productMesh.rotation.y += deltaTime * 0.5;
  renderer.render(scene, camera);
}
```

Правило: `AnimationMixer` — для проигрывания РЕАЛЬНЫХ анимационных клипов, созданных аниматором и экспортированных вместе с моделью; для собственной, написанной в коде процедурной анимации (вращение, покачивание, следование за курсором) — прямая мутация `position`/`rotation`/`scale` в цикле рендера полностью достаточна и не требует `AnimationMixer` вообще.

## Производительность: снижение числа draw call'ов

Статья 04: реальная стоимость GPU-рендеринга в большинстве сцен определяется КОЛИЧЕСТВОМ draw call'ов, а не сырым числом треугольников. three.js даёт два прямых инструмента для этой задачи:

```javascript
// InstancedMesh — тысячи копий ОДНОЙ geometry+material ОДНИМ draw call'ом
const instancedMesh = new THREE.InstancedMesh(treeGeometry, treeMaterial, 5000);
const matrix = new THREE.Matrix4();

for (let i = 0; i < 5000; i++) {
  matrix.setPosition(Math.random() * 100 - 50, 0, Math.random() * 100 - 50);
  instancedMesh.setMatrixAt(i, matrix); // своя трансформация НА КАЖДЫЙ экземпляр
}
scene.add(instancedMesh); // "лес" из 5000 деревьев — ОДИН draw call вместо 5000
```

```javascript
// Слияние геометрий для РАЗНЫХ статичных объектов с общим материалом,
// которым не нужна независимая трансформация в рантайме
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
const merged = mergeGeometries([rockGeometry1, rockGeometry2, rockGeometry3]);
const rocksMesh = new THREE.Mesh(merged, rockMaterial); // один Mesh вместо трёх
```

```javascript
// Ограничение pixelRatio — критично для мобильных: retina-дисплеи
// с devicePixelRatio 3 иначе рендерят ВНУТРЕННЕЕ разрешение втрое
// больше по каждой стороне без заметной пользы после ~2x
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
```

## `dispose()`: утечка, которую отгружает в продакшен почти каждый

Как и в Pixi (статья 05), GPU-ресурсы three.js (геометрия, материалы, текстуры) НЕ освобождаются JS-сборщиком мусора автоматически — обёрточный JS-объект может быть собран, а выделенная GPU-память останется занятой:

```javascript
// ❌ Классическая утечка: загрузка новой модели при смене маршрута
// БЕЗ освобождения ресурсов старой сцены
function loadNewModel(url) {
  scene.clear(); // убирает объекты из сцены, НО НЕ освобождает их GPU-ресурсы
  loader.load(url, (gltf) => scene.add(gltf.scene));
}
```

```javascript
// ✅ Явный обход и dispose() геометрии/материала/текстур перед заменой
function disposeSceneContents(scene) {
  scene.traverse((object) => {
    if (object.geometry) object.geometry.dispose();
    if (object.material) {
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      materials.forEach((material) => {
        Object.values(material).forEach((value) => {
          if (value?.isTexture) value.dispose(); // текстуры внутри материала
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

Это особенно частый баг в продуктовых конфигураторах и вьюерах, где пользователь переключает модели/варианты много раз за сессию — без явного `dispose()` GPU-память растёт с каждым переключением, пока вкладка не рухнет.

## Экосистема: react-three-fiber + drei

```tsx
import { Canvas } from '@react-three/fiber';
import { OrbitControls, useGLTF } from '@react-three/drei';

function Model() {
  const { scene } = useGLTF('/model.glb'); // хук с кэшированием загрузки
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

`react-three-fiber` — декларативный React-рендерер для сцены three.js: JSX-компоненты (`<mesh>`, `<ambientLight>`) отображаются напрямую в объекты three.js, монтирование/размонтирование и cleanup управляются React-жизненным циклом автоматически — то, что в статье 05 (Pixi + React) и статье 08 (canvas + React) делается вручную через `useEffect`, здесь абстрагировано на уровне библиотеки. `drei` — набор готовых хелперов поверх этого (обёртка `OrbitControls`, хук `useGLTF` с кэшированием, готовые пресеты освещения/окружения). Предпочитать эту связку — для React-приложений, где композиция компонентов важнее ручного микроконтроля над каждой деталью сцены (продуктовые конфигураторы, интерактивные 3D-UI); переходить на "чистый" three.js — когда нужен очень тонкий контроль или интеграция вне React вообще.

## Шейдерный "запасной выход": `ShaderMaterial`

Когда встроенные материалы не могут выразить нужный эффект, `ShaderMaterial` даёт прямой доступ к GLSL-модели статьи 04:

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
  material.uniforms.uTime.value += deltaTime; // uniform обновляется вручную из JS
  renderer.render(scene, camera);
}
```

Это прямое использование `attribute`/`uniform`/`varying` из статьи 04 — three.js подставляет встроенные переменные (`position`, `uv`, `projectionMatrix`, `modelViewMatrix`) автоматически, оставляя вам писать только содержательную часть шейдера.

## Связь с другими статьями

```txt
[WebGL and GPU Fundamentals]          — buffer/attribute/uniform/draw call —
                                         фундамент, который BufferGeometry,
                                         Material и InstancedMesh оборачивают
[Pixi.js in Depth]                    — та же retained-mode модель и та же
                                         draw-call-экономика, но в 2D
[Architecture and Performance for
 Canvas Apps]                          — dispose()-дисциплина и React-
                                         интеграция из этой статьи обобщаются
                                         на уровень всего приложения
```

## Типичные ошибки на интервью

- **Забыть `updateProjectionMatrix()` после resize** — знать, что нужно поменять `camera.aspect`, но не знать, что это само по себе не пересчитывает матрицу проекции, что даёт растянутое изображение.

- **Не суметь объяснить z-fighting** — не связывать мерцание перекрывающихся поверхностей с нелинейным распределением точности в буфере глубины и слишком широким диапазоном `near`/`far`.

- **Путать материалы по назначению** — не суметь объяснить разницу unlit (`Basic`) / lit non-PBR (`Lambert`/`Phong`) / PBR (`Standard`/`Physical`), и когда каждый оправдан.

- **Не знать стоимости теней** — не понимать, что каждый источник света с тенью — это дополнительный render pass, и что разрешение shadow map — прямой компромисс качество/производительность.

- **Не знать про sRGB/цветовые пространства** — списывать "модель выглядит блёклой" на "плохое освещение" или "плохую модель", не проверяя `texture.colorSpace`/`renderer.outputColorSpace`.

- **Не вызывать `dispose()` при смене сцены/модели** — не знать, что геометрия/материалы/текстуры не собираются JS garbage collector'ом автоматически, что приводит к росту GPU-памяти при повторной загрузке моделей.

- **Не знать про `InstancedMesh`** — пытаться нарисовать тысячи одинаковых объектов обычными `Mesh` без осознания, что это тысячи отдельных draw call'ов вместо одного.

- **Не иметь мнения о react-three-fiber vs "чистый" three.js** — не суметь объяснить, что абстрагирует `react-three-fiber` (жизненный цикл, декларативность) и когда прямой контроль через чистый API оправданнее.
