# three.js в деталях

## От 2D к 3D: та же retained-mode модель, плюс измерение глубины

three.js — это retained-mode сцена поверх WebGL (Web Graphics Library) плюс всё то, что нужно в 3D и не нужно в 2D. Retained-mode здесь — режим с запоминанием. Архитектурную задачу three.js решает ту же, что Pixi в статье 05, а слой WebGL под ним — это статья 04.

Нового здесь три вещи:

- Камера с проекцией трёхмерного пространства на плоский экран.
- Освещение, отвечающее на вопрос "как этот материал выглядит при таком-то свете".
- Буфер глубины — для правильного порядка отрисовки объектов, перекрывающих друг друга в 3D.

## Ментальная модель: `Scene`, `Camera`, `Renderer`

```javascript
// дерево сцены — как stage в Pixi
const scene = new THREE.Scene();

// где и как смотрим
const camera = new THREE.PerspectiveCamera(75, aspect, 0.1, 1000);

// обёртка над сырым WebGL (статья 04)
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

// на каждый вызов: пройти сцену, выполнить
// вызовы отрисовки для видимых объектов
renderer.render(scene, camera);
```

`Scene` — дерево объектов, концептуально идентичное `stage`/`Container` в Pixi, но в трёх измерениях.

`Camera` — не "объект в сцене", а определение того, **как** трёхмерные координаты превращаются в двумерные координаты экрана. Это матрица проекции.

`Renderer` — тонкая обёртка над сырым WebGL-контекстом (статья 04). На каждый `render()` он генерирует нужные вызовы отрисовки (draw call) для всех видимых объектов.

## `PerspectiveCamera` vs `OrthographicCamera`

```javascript
// Перспектива: объекты дальше — визуально меньше (как человеческое зрение)
const perspective = new THREE.PerspectiveCamera(
  75,              // fov — угол обзора по вертикали, в градусах
  width / height,   // aspect — соотношение сторон вьюпорта
  0.1,              // near — ближняя плоскость отсечения
  1000,             // far — дальняя плоскость отсечения
);

// Ортографическая: нет уменьшения с расстоянием, параллельные линии
// остаются параллельными — виды CAD (computer-aided design,
// системы автоматизированного проектирования), изометрические
// игры, 2D-оверлеи в 3D-сцене
const orthographic = new THREE.OrthographicCamera(
  -width / 2, width / 2, height / 2, -height / 2, 0.1, 1000,
);
```

**`near`/`far` и z-fighting** — не формальность, а источник реального визуального бага.

Буфер глубины хранит расстояние до камеры с точностью, распределённой **нелинейно**: больше точности рядом с `near`, значительно меньше — рядом с `far`.

Задайте `near` слишком маленьким, а `far` слишком большим — и две поверхности на разной, но близкой глубине получат почти одинаковое значение в буфере глубины. Рендерер тогда не может надёжно решить, какая из них ближе.

Результат — характерное мерцание одной поверхности сквозь другую при малейшем движении камеры. Это и есть z-fighting. Фикс — задавать `near`/`far` максимально плотно вокруг реальных границ сцены, а не "с запасом на всякий случай".

## Триада Geometry + Material + Mesh

```javascript
const geometry = new THREE.BoxGeometry(1, 1, 1);  // что за форма (вершины)

// как это закрашено и освещено
const material = new THREE.MeshStandardMaterial({ color: 0x3366ff });

// объект в сцене: geometry + material + трансформация
const cube = new THREE.Mesh(geometry, material);
scene.add(cube);

cube.position.set(0, 1, 0);
cube.rotation.y = Math.PI / 4;
```

`Geometry` отвечает за форму. `Material` отвечает за то, как эта форма реагирует на свет и текстуры. `Mesh` объединяет их и размещает в сцене с собственной трансформацией.

Три разных `Mesh` могут переиспользовать **одну и ту же** `Geometry` и `Material`, что напрямую связано с оптимизацией вызовов отрисовки ниже.

## `BufferGeometry`: то же самое, что буферы и атрибуты из статьи 04

```javascript
const geometry = new THREE.BufferGeometry();

const positions = new Float32Array([ /* x,y,z для каждой вершины */ ]);
// 3 — компонент на вершину
geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

// nx,ny,nz — направление "наружу" для расчёта освещения
const normals = new Float32Array([ /* ... */ ]);
geometry.setAttribute('normal', new THREE.BufferAttribute(normals, 3));

// u,v — координаты для наложения текстуры
const uvs = new Float32Array([ /* ... */ ]);
geometry.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
```

`BufferGeometry` — не отдельная концепция, а прямая обёртка над буферами и атрибутами GPU (graphics processing unit — графический процессор) из статьи 04:

- `position` — обязательный атрибут, без него нечего рисовать.
- `normal` — направление поверхности в каждой вершине, критичное для расчёта того, как отражается свет. Без нормалей освещённая модель выглядит "плоской" или рендерится неправильно.
- `uv` — координаты для натягивания текстуры на поверхность.

## Тур по материалам: unlit → lit → PBR

Материалы отличаются тем, как они реагируют на свет. PBR ниже — это physically based rendering, физически корректный рендеринг.

| Материал | Как реагирует на свет | Где уместен |
|---|---|---|
| `MeshBasicMaterial` | Без реакции на свет вообще: просто плоский цвет или текстура, все источники света в сцене игнорируются. Самый дешёвый. | Элементы интерфейса в 3D, wireframe, намеренно "плоский" стилизованный вид. |
| `MeshLambertMaterial` | Освещённый, но только диффузное (матовое) отражение, посчитанное по вершинам. Дешевле и менее точно. | В основном legacy и простые случаи. |
| `MeshPhongMaterial` | Освещённый, добавляет бликовые (specular) отражения с расчётом по пикселям. Дороже Lambert. | Классический вид "глянцевого пластика". |
| `MeshStandardMaterial` и `MeshPhysicalMaterial` | Физически корректный рендеринг. Материал описан параметрами roughness (шероховатость) и metalness (металличность), на приближении реальной физики света. Это заменяет произвольную "формулу блика", как в Phong. | Визуально более реалистичный результат, устойчивый при разных условиях освещения. `Physical` дополнительно даёт clearcoat, transmission (стекло) и другие продвинутые эффекты реальных материалов. |

Практический выбор: `Standard` или `Physical` — дефолт для всего, что должно выглядеть реалистично, например для продуктовых вьюеров и архитектурной визуализации. `Basic` — для дешёвого стилизованного вида без освещения. `Phong` — только для legacy-кода или специфического стилизованного "глянца" по более низкой цене, чем полноценный физически корректный рендеринг.

## Свет и тени

```javascript
// равномерный свет со всех сторон, без направления и без теней —
// просто "пол" освещённости, чтобы тени не были чисто чёрными
scene.add(new THREE.AmbientLight(0xffffff, 0.4));

// параллельные лучи (как солнце)
const dirLight = new THREE.DirectionalLight(0xffffff, 1);
dirLight.position.set(5, 10, 5);
dirLight.castShadow = true;
scene.add(dirLight);

// излучает во все стороны из точки (как лампочка),
// затухает с расстоянием
const pointLight = new THREE.PointLight(0xffaa00, 1, 50);

// конус с углом
const spotLight = new THREE.SpotLight(0xffffff, 1, 0, Math.PI / 6);
```

**Механика shadow map.** Сцена дополнительно рендерится ещё один раз, с точки зрения источника света, в текстуру глубины. Это уже второй проход рендеринга, помимо основного, с точки зрения камеры.

Затем в основном проходе для каждого пикселя его расстояние до источника света сравнивается с сохранённым в этой текстуре значением. Если сохранённое значение меньше, пиксель в тени: что-то ближе к свету загораживает его.

```javascript
renderer.shadowMap.enabled = true;
mesh.castShadow = true;     // этот объект отбрасывает тень
mesh.receiveShadow = true;  // на этот объект тени падают

dirLight.shadow.mapSize.width = 2048;  // разрешение shadow map: выше —
dirLight.shadow.mapSize.height = 2048; // чётче края тени, но дороже
                                          // по памяти и по времени рендера
                                          // этого дополнительного прохода
```

Стоимость теней — не абстракция. Каждый источник света с `castShadow: true` требует своего дополнительного прохода рендеринга на кадр.

А разрешение `mapSize` — прямой компромисс между "чёткостью краёв тени" и "памятью плюс временем рендера". На мобильных устройствах это одна из первых вещей, которую урезают при нехватке производительности.

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
// aspect поменялся, а матрица проекции — нет
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  renderer.setSize(window.innerWidth, window.innerHeight);
});
```

```javascript
// ✅ camera.aspect (и любое другое свойство камеры: fov, near, far)
// не пересчитывает матрицу проекции автоматически — это нужно
// сделать явным вызовом после каждого такого изменения
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix(); // обязательно после смены aspect/fov/near/far
  renderer.setSize(window.innerWidth, window.innerHeight);
});
```

## `OrbitControls` и загрузка реальных ассетов через `GLTFLoader`

```javascript
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

const controls = new OrbitControls(camera, renderer.domElement);
// инерция при вращении — требует .update() каждый кадр
controls.enableDamping = true;

function animate() {
  requestAnimationFrame(animate);
  controls.update(); // обязателен при enableDamping: true
  renderer.render(scene, camera);
}
```

**Почему glTF — стандартный формат.** glTF спроектирован именно как "формат для рантайма", а не для редактирования. Он компактный, с нативной поддержкой физически корректных материалов, скелетной анимации и morph targets. Поддержка инструментов экспорта тоже широкая: Blender и практически весь остальной 3D-тулинг.

Более старые форматы не дают этого набора "из коробки". Формат `.obj` — без анимации и без физически корректных материалов. Формат `.fbx` тяжелее и менее открыт.

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

**Draco** — расширение сжатия геометрии для glTF. Оно заметно уменьшает размер файла для сложных мешей ценой необходимости декодирования в браузере через `DRACOLoader`. Это оправдано для продакшен-сцен со сложной геометрией, раздаваемых по сети, особенно на мобильном трафике.

## Текстуры и цветовые пространства: причина "модель выглядит блёклой"

Изображения-текстуры обычно хранятся в цветовом пространстве sRGB. Это гамма-кодировка, оптимизированная под восприятие экрана человеком. Математика же освещения в рендерере корректно работает только в линейном пространстве.

Поэтому three.js должен знать две вещи. В каком пространстве закодирована каждая текстура и в каком пространстве нужно выдать финальный цвет на экран:

```javascript
const texture = new THREE.TextureLoader().load('/albedo.jpg');
texture.colorSpace = THREE.SRGBColorSpace; // обязательно для цветных
                                              // (albedo/diffuse) текстур —
                                              // без этого либо двойное,
                                              // либо отсутствующее
                                              // sRGB-декодирование

renderer.outputColorSpace = THREE.SRGBColorSpace; // корректный вывод
                                                     // финального цвета на экран
```

Симптом неправильной настройки — классический "модель выглядит блёклой и плоской". В обратном случае она выглядит неестественно контрастной.

Ни то ни другое не проблема самой модели или освещения. Это рассинхронизация цветовых пространств на входе, то есть в текстуре, и на выходе, то есть в рендерере.

Для собственных текстур модели `GLTFLoader` настраивает это автоматически и корректно. При ручной загрузке текстур через `TextureLoader` — например, для кастомной canvas-текстуры — выставлять всё нужно явно самому.

## Raycasting: попадание курсора в 3D-объект

```javascript
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();

window.addEventListener('click', (event) => {
  // Нормализованные координаты устройства: -1..1 по обеим осям
  mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
  mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

  // луч от камеры через эту точку экрана
  raycaster.setFromCamera(mouse, camera);

  // true — рекурсивно
  const hits = raycaster.intersectObjects(scene.children, true);

  if (hits.length > 0) {
    console.log('Clicked:', hits[0].object); // hits[0] — ближайшее пересечение
  }
});
```

Это 3D-аналог определения попадания (hit detection) из статьи 02, где на canvas шли математические проверки, и `hitArea` в Pixi (статья 05). Вместо 2D-геометрии здесь считается пересечение луча с треугольниками мешей в трёхмерном пространстве, и результат отсортирован по расстоянию от камеры.

## Анимация: `AnimationMixer` vs ручная трансформация в цикле

```javascript
// Для авторских анимаций (скелетная анимация, morph targets),
// экспортированных из Blender/Maya вместе с моделью
const mixer = new THREE.AnimationMixer(gltf.scene);
const action = mixer.clipAction(gltf.animations[0]);
action.play();

// deltaTime здесь — секунды с предыдущего кадра. Голый колбэк
// requestAnimationFrame получает таймстемп, а не дельту: посчитайте
// её сами либо возьмите из THREE.Clock().getDelta()
function animate(deltaTime) {
  mixer.update(deltaTime); // обязан вызываться каждый кадр с реальным dt
  renderer.render(scene, camera);
}
```

```javascript
// Для простого процедурного движения (вращающийся продукт в вьюере) —
// AnimationMixer избыточен, обычная мутация трансформации в цикле проще
function animate(deltaTime) { // deltaTime в секундах, как выше
  productMesh.rotation.y += deltaTime * 0.5;
  renderer.render(scene, camera);
}
```

Правило: `AnimationMixer` — для проигрывания реальных анимационных клипов, созданных аниматором и экспортированных вместе с моделью.

Для собственной процедурной анимации, написанной в коде — вращение, покачивание, следование за курсором, — меняйте `position`/`rotation`/`scale` прямо в цикле рендера. Этого полностью достаточно, и `AnimationMixer` тут не нужен вообще.

## Производительность: снижение числа вызовов отрисовки

В статье 04 показано, что реальная стоимость GPU-рендеринга в большинстве сцен определяется **количеством** вызовов отрисовки, а не сырым числом треугольников. Прямых инструментов для этой задачи в three.js два:

```javascript
// InstancedMesh — тысячи копий одной geometry+material одним вызовом
const instancedMesh = new THREE.InstancedMesh(treeGeometry, treeMaterial, 5000);
const matrix = new THREE.Matrix4();

for (let i = 0; i < 5000; i++) {
  matrix.setPosition(Math.random() * 100 - 50, 0, Math.random() * 100 - 50);
  instancedMesh.setMatrixAt(i, matrix); // своя трансформация на каждый экземпляр
}
scene.add(instancedMesh); // "лес" из 5000 деревьев — один вызов вместо 5000
```

```javascript
// Слияние геометрий для разных статичных объектов с общим материалом,
// которым не нужна независимая трансформация в рантайме
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
const merged = mergeGeometries([rockGeometry1, rockGeometry2, rockGeometry3]);
const rocksMesh = new THREE.Mesh(merged, rockMaterial); // один Mesh вместо трёх
```

```javascript
// Ограничение pixelRatio — критично для мобильных: retina-дисплеи
// с devicePixelRatio 3 иначе рендерят внутреннее разрешение втрое
// больше по каждой стороне без заметной пользы после ~2x
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
```

## `dispose()`: утечка, которую отгружает в продакшен почти каждый

Как и в Pixi (статья 05), GPU-ресурсы three.js — геометрия, материалы, текстуры — не освобождаются JS-сборщиком мусора автоматически. Обёрточный JS-объект может быть собран, а выделенная GPU-память останется занятой:

```javascript
// ❌ Классическая утечка: загрузка новой модели при смене маршрута
// без освобождения ресурсов старой сцены
function loadNewModel(url) {
  // убирает объекты из сцены, но не освобождает их GPU-ресурсы
  scene.clear();
  loader.load(url, (gltf) => scene.add(gltf.scene));
}
```

```javascript
// ✅ Явный обход и dispose() геометрии/материала/текстур перед заменой
function disposeSceneContents(scene) {
  scene.traverse((object) => {
    if (object.geometry) object.geometry.dispose();
    if (object.material) {
      const materials = Array.isArray(object.material)
        ? object.material
        : [object.material];
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

Это особенно частый баг в продуктовых конфигураторах и вьюерах, где пользователь переключает модели и варианты много раз за сессию. Без явного `dispose()` GPU-память растёт с каждым переключением, пока вкладка не рухнет.

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

`react-three-fiber` — декларативный React-рендерер для сцены three.js. Компоненты JSX (синтаксическое расширение JavaScript) вроде `<mesh>` и `<ambientLight>` отображаются напрямую в объекты three.js. Монтирование, размонтирование и очистка управляются жизненным циклом React автоматически.

То, что в статье 05 (Pixi + React) и статье 08 (canvas + React) делается вручную через `useEffect`, здесь абстрагировано на уровне библиотеки.

`drei` — набор готовых хелперов поверх этого: обёртка `OrbitControls`, хук `useGLTF` с кэшированием, готовые пресеты освещения и окружения.

Эту связку стоит предпочитать в React-приложениях, где композиция компонентов важнее ручного микроконтроля над каждой деталью сцены. Типичный случай — продуктовые конфигураторы и интерактивные 3D-интерфейсы. На "чистый" three.js стоит переходить, когда нужен очень тонкий контроль или интеграция вне React вообще.

## Шейдерный "запасной выход": `ShaderMaterial`

Когда встроенные материалы не могут выразить нужный эффект, `ShaderMaterial` даёт прямой доступ к модели GLSL (OpenGL Shading Language) из статьи 04:

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

function animate(deltaTime) { // deltaTime в секундах, как выше
  material.uniforms.uTime.value += deltaTime; // uniform обновляется вручную из JS
  renderer.render(scene, camera);
}
```

Это прямое использование `attribute`/`uniform`/`varying` из статьи 04. Встроенные переменные — `position`, `uv`, `projectionMatrix`, `modelViewMatrix` — подставляются автоматически, и писать вам остаётся только содержательную часть шейдера.

## Связь с другими статьями

- [WebGL и основы GPU](./04-webgl-and-gpu-fundamentals.md) — buffer, attribute, uniform и вызов отрисовки: фундамент, который оборачивают `BufferGeometry`, `Material` и `InstancedMesh`.
- [Pixi.js в деталях](./05-pixijs-in-depth.md) — та же retained-mode модель и та же экономика вызовов отрисовки, но в 2D.
- [Архитектура и производительность canvas-приложений](./08-architecture-and-performance-for-canvas-apps.md) — дисциплина `dispose()` и React-интеграция из этой статьи обобщаются на уровень всего приложения.

## Типичные ошибки на интервью

- **Забыть `updateProjectionMatrix()` после resize** — знать, что нужно поменять `camera.aspect`, но не знать, что само по себе это не пересчитывает матрицу проекции. Результат — растянутое изображение.

- **Не суметь объяснить z-fighting** — не связывать мерцание перекрывающихся поверхностей с нелинейным распределением точности в буфере глубины и слишком широким диапазоном `near`/`far`.

- **Путать материалы по назначению** — не суметь объяснить разницу между неосвещённым (`Basic`), освещённым, но не физически корректным (`Lambert`/`Phong`), и физически корректным (`Standard`/`Physical`). И не знать, когда каждый из них оправдан.

- **Не знать стоимости теней** — не понимать, что каждый источник света с тенью — это дополнительный проход рендеринга. Разрешение shadow map — прямой компромисс между качеством и производительностью.

- **Не знать про sRGB и цветовые пространства** — списывать "модель выглядит блёклой" на плохое освещение или плохую модель. Непроверенными остаются `texture.colorSpace` и `renderer.outputColorSpace`.

- **Не вызывать `dispose()` при смене сцены или модели** — не знать, что геометрия, материалы и текстуры не собираются JS-сборщиком мусора автоматически. GPU-память тогда растёт при повторной загрузке моделей.

- **Не знать про `InstancedMesh`** — пытаться нарисовать тысячи одинаковых объектов обычными `Mesh`. Это тысячи отдельных вызовов отрисовки вместо одного.

- **Не иметь мнения о react-three-fiber против "чистого" three.js** — не суметь объяснить, что абстрагирует `react-three-fiber`, а именно жизненный цикл и декларативность. И не знать, когда прямой контроль через чистый API оправданнее.
