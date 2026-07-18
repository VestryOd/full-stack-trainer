# Шпаргалка и сравнение технологий

Справочный материал по статьям 01-08 — без новых объяснений концепций, только компактные таблицы и сниппеты для быстрого использования. Если формулировка непонятна — она разобрана подробно в статье, указанной в заголовке раздела.

## Часть 1: Шпаргалка

### Canvas 2D: методы контекста по назначению (статьи 01-03)

| Группа | Методы/свойства |
|---|---|
| Рисование (без пути) | `fillRect`, `strokeRect`, `clearRect` |
| Пути | `beginPath`, `moveTo`, `lineTo`, `arc`, `quadraticCurveTo`, `bezierCurveTo`, `closePath`, `fill`, `stroke` |
| Стили | `fillStyle`, `strokeStyle`, `lineWidth`, `lineCap`, `lineJoin`, `setLineDash`, `createLinearGradient`, `createRadialGradient`, `createPattern` |
| Трансформации | `translate`, `rotate`, `scale`, `setTransform`, `resetTransform` |
| Состояние | `save`, `restore` |
| Текст | `fillText`, `strokeText`, `font`, `textAlign`, `textBaseline`, `measureText` |
| Пиксели | `getImageData`, `putImageData`, `createImageData` |
| Композитинг | `globalCompositeOperation`, `globalAlpha` |
| Экспорт | `toDataURL`, `toBlob`, `createImageBitmap` |

### Каноническая retina-настройка canvas (статья 01)

```javascript
function setupCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  canvas.style.width = `${rect.width}px`;
  canvas.style.height = `${rect.height}px`;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  return ctx;
}
```

### Минимальный игровой цикл (статья 02)

```javascript
let previousTimestamp;
function loop(timestamp) {
  if (previousTimestamp === undefined) previousTimestamp = timestamp;
  const dt = (timestamp - previousTimestamp) / 1000;
  previousTimestamp = timestamp;

  update(dt);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  draw(ctx);

  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
```

### `drawImage`: три формы вызова (статья 02)

```javascript
ctx.drawImage(image, dx, dy);                             // 1. как есть, в позицию
ctx.drawImage(image, dx, dy, dWidth, dHeight);             // 2. + масштабирование
ctx.drawImage(                                             // 3. + вырезка из источника (спрайты)
  image,
  sx, sy, sWidth, sHeight, // откуда вырезать в исходнике
  dx, dy, dWidth, dHeight, // куда вставить и какого размера
);
```

### `globalCompositeOperation` — быстрая таблица (статья 03)

| Режим | Эффект |
|---|---|
| `source-over` (дефолт) | Обычное рисование поверх |
| `destination-out` | Новая фигура СТИРАЕТ существующее — основа scratch-card |
| `source-atop` | Новое видно только там, где уже есть непрозрачный контент |
| `multiply` | Каналы перемножаются — темнее |
| `screen` | Визуально противоположно multiply — светлее |
| `lighter` | Каналы складываются (аддитивно) — свечение/частицы |

### Pixi.js — быстрый старт (статья 05)

| API | Назначение |
|---|---|
| `new Application()` + `await app.init(...)` | Создать приложение/рендерер |
| `app.stage.addChild(container)` | Корень дерева сцены |
| `new Sprite(texture)` | Отрисовать текстуру в позиции/повороте/масштабе |
| `Texture` vs `BaseTexture` | Окно в область изображения vs фактическая GPU-текстура |
| `app.ticker.add((t) => ...)` | Встроенный цикл обновления, `t.deltaTime`/`t.deltaMS` |
| `await Assets.load(url)` | Загрузка с кэшированием/дедупликацией |
| `sprite.destroy()` / `texture.destroy(true)` | Освобождение GPU-ресурсов |

### three.js — быстрый старт (статья 06)

| API | Назначение |
|---|---|
| `new THREE.Scene()` | Дерево сцены |
| `new THREE.PerspectiveCamera(fov, aspect, near, far)` | Камера с перспективной проекцией |
| `new THREE.WebGLRenderer()` | Обёртка над WebGL-контекстом |
| `new THREE.Mesh(geometry, material)` | Geometry (форма) + Material (шейдинг) в сцене |
| `AmbientLight` / `DirectionalLight` / `PointLight` / `SpotLight` | Типы источников света |
| `camera.aspect = ...; camera.updateProjectionMatrix()` | ОБЯЗАТЕЛЬНАЯ пара при ресайзе |
| `OrbitControls` / `GLTFLoader` | Управление камерой мышью / загрузка моделей |
| `geometry.dispose()`, `material.dispose()`, `texture.dispose()` | Освобождение GPU-ресурсов |

### d3.js — ядро (статья 07)

| API | Назначение |
|---|---|
| `d3.select(el).selectAll(sel)` | Выборка DOM-узлов |
| `.data(array, keyFn).join(enter, update, exit)` | Привязка данных + реконсиляция DOM |
| `d3.scaleLinear().domain([...]).range([...])` | Чистая функция: данные → пиксели |
| `d3.line().x(fn).y(fn)` | Генератор геометрии линии из массива данных |
| `d3.line().context(ctx)` | Перенаправить генератор формы рисовать на canvas вместо SVG |

## Часть 2: Сравнение технологий

| Технология | Для чего лучше всего | Что умеет | Типичное реальное применение | Комфортный диапазон элементов | Производительность | Ограничения |
|---|---|---|---|---|---|---|
| **DOM + CSS** *(см. топик [Browser Animation])* | Обычный UI, доступный из коробки | Layout, стилизация, CSS-анимация | Любой стандартный интерфейс | Сотни-тысячи узлов | Compositor для transform/opacity, main thread для layout | Не годится для попиксельной/GPU-интенсивной графики |
| **SVG** | Интерактивные дашборды, иконки, диаграммы | Векторный retained-mode DOM, CSS-стилизация, доступность | Графики с богатой интерактивностью, иллюстрации, иконки | До ~1-2 тыс. элементов | DOM-based, тот же оверхед на узел, что у обычного DOM | Деградирует на больших количествах узлов |
| **Canvas 2D** | Попиксельная работа, кастомная 2D-графика | Immediate-mode рисование, пиксельные фильтры, композитинг | Графики/дашборды с 10k+ точек, простые игры, эффекты (scratch-card) | 10 000+ простых объектов | CPU-растеризация, один DOM-узел независимо от контента | Нет retained-mode сцены "из коробки", ручной hit detection |
| **WebGL (сырой)** | Полный контроль над GPU-конвейером | Шейдеры, буферы, произвольный рендеринг | Движки поверх него (Pixi, three.js), нишевые кастомные рендереры | Ограничено драйверным оверхедом на draw call, не сырым числом объектов | GPU-параллелизм, компоузитор-независимый рендеринг | Крайне многословный API, высокий порог входа |
| **WebGPU** | Современный низкоуровневый доступ к GPU | Явный pipeline-объект, compute shaders, меньший CPU-оверхед на кадр | Тяжёлые вычисления на GPU, следующее поколение движков | Выше, чем WebGL, за счёт меньшего оверхеда на draw call | Ниже CPU-оверхед на вызов, чем у WebGL | Поддержка в браузерах ещё не универсальна — проверять перед продакшеном |
| **Pixi.js** | 2D-сцены с сотнями-тысячами спрайтов | Retained-mode сцена, батчинг, фильтры, спрайт-атласы | Промо-страницы с частицами, 2D-игры, слот/казино-игры | Тысячи-десятки тысяч спрайтов (с атласами/батчингом) | GPU-батчинг через WebGL | Избыточен для горстки простых фигур |
| **three.js** | 3D-сцены и объекты | Камеры, освещение, PBR-материалы, загрузка glTF-моделей | Продуктовые 3D-конфигураторы, брендовые 3D-сцены, визуализации | Тысячи мешей (больше — через instancing) | GPU-рендеринг с полным 3D-конвейером | Требует понимания 3D-математики/освещения для нетривиальных сцен |
| **d3.js** | Математика шкал/форм + привязка данных | Scales, shape-генераторы, data join, рендерер-независимость (SVG или canvas) | Кастомная, нестандартная визуализация данных | Зависит от целевого рендерера (SVG-лимиты или canvas-лимиты) | Зависит от того, во что рендерится (SVG DOM или canvas) | Не "чарт-библиотека из коробки" — требует сборки визуализации вручную |
| **Чарт-библиотеки (ECharts/Chart.js)** | Стандартные графики за минимум кода | Готовые bar/line/pie/scatter с легендами, тултипами, адаптивностью | 90% продуктовых дашбордов и отчётов | Обычно тысячи точек, зависит от библиотеки | Обычно SVG/canvas под капотом, оптимизировано авторами библиотеки | Меньше свободы для нестандартных/уникальных визуализаций |
| **Lottie** *(см. топик [Browser Animation])* | Воспроизведение сложной анимации из After Effects | Точное 1-в-1 воспроизведение векторной motion-графики | Onboarding-иллюстрации, брендированные лоадеры | Не про количество элементов — про сложность одной анимации | Зависит от рендерера (svg/canvas/html) | Требует пайплайна bodymovin-экспорта, не для интерактивной графики |

**Как использовать эту таблицу на практике:** начинать с верхних строк (DOM/CSS, SVG) и спускаться вниз только тогда, когда конкретная задача (объём данных, интерактивность, попиксельный контроль, 3D) упирается в реальное ограничение текущего уровня — так же, как в сравнительной таблице browser-animation, выбор инструмента должен следовать за задачей, а не за "мощностью" технологии в отрыве от контекста.
