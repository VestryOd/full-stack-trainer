# Пиксели, изображения и эффекты

## Уровень ниже примитивов

Статьи 01-02 работают с canvas через высокоуровневые примитивы: "нарисуй прямоугольник", "нарисуй путь". Эта статья — про уровень ниже, где вы не рисуете фигуры, а напрямую читаете и пишете значения RGBA каждого отдельного пикселя буфера. Это открывает три класса задач, недостижимых через `fillRect`/`drawImage`: попиксельные фильтры изображений, композитинг-трюки вроде scratch-card эффекта, и, в конце статьи, полный вынос рендеринга с главного потока.

## `ImageData`: чтение и запись буфера напрямую

```javascript
const imageData = ctx.getImageData(x, y, width, height); // читает область буфера
console.log(imageData.width, imageData.height);
console.log(imageData.data); // Uint8ClampedArray — сырые байты RGBA

ctx.putImageData(imageData, x, y); // пишет буфер обратно
```

**Стоимость `getImageData` — не мелочь.** Canvas 2D может рендериться с использованием GPU-ускорения, и запрос сырых пикселей ЦП вынуждает синхронизацию: браузер обязан дождаться, пока GPU закончит текущую работу, скопировать содержимое буфера из GPU-памяти в обычную память процесса — это точка синхронизации, которая может стоить заметного времени, особенно в горячем цикле (вызов на каждый кадр анимации — частая причина внезапного проседания FPS). Подсказка `willReadFrequently: true` при получении контекста заставляет браузер с самого начала держать буфер в CPU-доступной памяти, избегая повторных GPU→CPU копий:

```javascript
const ctx = canvas.getContext('2d', { willReadFrequently: true });
```

`putImageData`, в отличие от `fillRect`/`drawImage`, **игнорирует** текущую трансформацию, `globalCompositeOperation` и clip-регион — это прямая побайтовая запись в буфер, а не "рисование" в обычном смысле контекста как машины состояний (статья 01).

## `Uint8ClampedArray`: раскладка RGBA и разница с `Uint8Array`

`imageData.data` — плоский массив байт, по 4 значения на пиксель, построчно:

```txt
data[0] = R пикселя (0,0)   data[4] = R пикселя (1,0)
data[1] = G пикселя (0,0)   data[5] = G пикселя (1,0)
data[2] = B пикселя (0,0)   data[6] = B пикселя (1,0)
data[3] = A пикселя (0,0)   data[7] = A пикселя (1,0)
```

`Clamped` в имени типа — не формальность: при записи значения вне диапазона `[0, 255]` оно **обрезается** до границы (255 при переполнении, 0 при отрицательном), а не оборачивается по модулю 256, как в обычном `Uint8Array`. Это критично для арифметики фильтров — `pixel + 50`, дающее 280, обычным `Uint8Array` дало бы `280 % 256 = 24` (визуально — случайный тёмный пиксель вместо ожидаемого яркого), а `Uint8ClampedArray` корректно даёт `255`.

**Рабочий пример: grayscale и threshold-фильтр**

```javascript
function applyGrayscale(ctx, width, height) {
  const imageData = ctx.getImageData(0, 0, width, height);
  const data = imageData.data;

  for (let i = 0; i < data.length; i += 4) {
    // Формула яркости (luminance) — глаз чувствительнее к зелёному,
    // менее — к синему, поэтому не просто (r+g+b)/3
    const luminance = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
    data[i] = data[i + 1] = data[i + 2] = luminance; // R=G=B=яркость → серый
    // data[i + 3] (alpha) не трогаем
  }

  ctx.putImageData(imageData, 0, 0);
}

function applyThreshold(ctx, width, height, cutoff = 128) {
  const imageData = ctx.getImageData(0, 0, width, height);
  const data = imageData.data;

  for (let i = 0; i < data.length; i += 4) {
    const luminance = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
    const value = luminance >= cutoff ? 255 : 0; // строго чёрный/белый
    data[i] = data[i + 1] = data[i + 2] = value;
  }

  ctx.putImageData(imageData, 0, 0);
}
```

## Безопасность: tainted canvas и `crossOrigin`

Если на canvas нарисовано изображение с ДРУГОГО origin без корректных CORS-заголовков, canvas помечается как **tainted** (испорченный) — браузер намеренно блокирует любое последующее чтение его пиксельных данных (`getImageData`, `toDataURL`, `toBlob`), бросая `SecurityError`. Это не баг и не излишняя строгость — это защита от использования canvas как "оракула" для кражи содержимого приватных cross-origin изображений (например, определить, залогинен ли пользователь на другом сайте, через доступность его приватной аватарки, читая её пиксели байт за байтом).

```javascript
// ❌ Без crossOrigin — canvas окажется "испорчен" для чужого origin,
// и попытка экспорта упадёт с SecurityError в консоли
const img = new Image();
img.src = 'https://other-domain.com/photo.jpg';
img.onload = () => {
  ctx.drawImage(img, 0, 0);
  canvas.toDataURL(); // 💥 SecurityError: tainted canvas
};
```

```javascript
// ✅ Явно запросить CORS-режим — РАБОТАЕТ только если сервер
// изображения отдаёт заголовок Access-Control-Allow-Origin
const img = new Image();
img.crossOrigin = 'anonymous';
img.src = 'https://other-domain.com/photo.jpg';
img.onload = () => {
  ctx.drawImage(img, 0, 0);
  canvas.toDataURL(); // ✅ работает, если сервер разрешил CORS
};
```

Частый практический сценарий: "пользователь загружает фото, мы применяем фильтр на canvas, экспорт в файл падает с непонятной ошибкой" — почти всегда причина именно в этом: `crossOrigin` на клиенте без соответствующего заголовка на сервере НЕ помогает, оба условия обязательны одновременно.

## `globalCompositeOperation`: как рисование смешивается с уже нарисованным

Важно понимать масштаб этого свойства правильно: это не "финальный блендинг всей сцены", а режим, применяющийся к **каждому вызову рисования**, определяя, как новые пиксели комбинируются с уже существующими в буфере под ними.

### `destination-out`: полный scratch-card эффект

Новая фигура СТИРАЕТ существующее содержимое там, где она рисуется (работает как ластик, а не как краска) — именно на этом построены scratch-card эффекты ("сотри и узнай приз"):

```javascript
// 1. Базовый слой — то, что скрыто под "фольгой" (текст приза, картинка)
ctx.fillStyle = '#222';
ctx.fillRect(0, 0, canvas.width, canvas.height);
ctx.fillStyle = 'gold';
ctx.font = 'bold 32px sans-serif';
ctx.fillText('You won 500!', 60, 150);

// 2. Слой "фольги" поверх — то, что пользователь будет стирать
ctx.globalCompositeOperation = 'source-over'; // обычное рисование (дефолт)
ctx.fillStyle = '#999';
ctx.fillRect(0, 0, canvas.width, canvas.height);

// 3. Стирание кистью при движении курсора
canvas.addEventListener('pointermove', (e) => {
  if (e.buttons !== 1) return; // стираем только при зажатой кнопке

  ctx.globalCompositeOperation = 'destination-out'; // КЛЮЧЕВАЯ строка:
  // всё, что рисуется дальше, СТИРАЕТ существующие пиксели вместо
  // того, чтобы рисоваться поверх них
  ctx.beginPath();
  ctx.arc(e.offsetX, e.offsetY, 20, 0, Math.PI * 2);
  ctx.fill(); // "дырка" в слое фольги — под ней виден базовый слой
});
```

Это ПОЛНАЯ рабочая механика scratch-card эффекта — три составляющие (базовый слой, слой фольги, кисть-ластик через `destination-out`) достаточны для реального продакшен-компонента без дополнительных библиотек.

### Остальные практически важные режимы

```txt
source-atop  — новый рисунок виден ТОЛЬКО там, где уже есть непрозрачный
                контент под ним (обрезается силуэтом существующего
                содержимого) — удобно для перекрашивания/тонирования
                внутри уже нарисованного силуэта, не выходя за его границы

multiply     — каналы цвета ПЕРЕМНОЖАЮТСЯ — результат всегда темнее
                исходных цветов — классический режим для наложения тени/
                затемнения поверх существующей сцены

screen       — визуально противоположность multiply — результат всегда
                светлее — используется для эффектов засветки/бликов

lighter      — значения каналов СКЛАДЫВАЮТСЯ (аддитивное смешивание) —
                классический приём для свечения и частиц: перекрывающиеся
                яркие частицы (искры, огонь, свет) становятся ЯРЧЕ в
                местах перекрытия, а не просто рисуются друг поверх друга
```

```javascript
// Аддитивное свечение для частиц — характерный приём "огня"/"искр"
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
// Там, где частицы перекрываются — суммарная яркость выше,
// создавая естественный эффект скопления света, а НЕ плоского наложения
```

Как и с любым состоянием контекста (статья 01), `globalCompositeOperation` нужно возвращать к `'source-over'` явно (или оборачивать в `save()`/`restore()`) — иначе следующая, ничего не подозревающая часть кода начнёт рисоваться в неожиданном режиме смешивания.

## Тени и `filter`: те же CSS-эффекты, но с реальной стоимостью на каждый кадр

```javascript
ctx.shadowColor = 'rgba(0,0,0,0.4)';
ctx.shadowBlur = 12;
ctx.shadowOffsetX = 4;
ctx.shadowOffsetY = 4;
ctx.fillRect(50, 50, 100, 100); // тень рисуется автоматически при любом fill/stroke/drawImage

ctx.filter = 'blur(4px) brightness(1.2)'; // тот же синтаксис CSS filter (статья
                                            // browser-animation, где filter уже
                                            // разбирался как CSS-свойство)
ctx.drawImage(image, 0, 0);
```

Стоимость — не мелочь: `shadowBlur` и `filter: blur()` — это фактически программный проход блюра по растеризованным пикселям на КАЖДЫЙ вызов рисования, и в immediate-mode модели (где всё перерисовывается каждый кадр, статья 02) эта стоимость платится заново 60 раз в секунду для каждого затронутого объекта. На большом количестве анимируемых объектов с тенью/блюром это — частый источник резкого падения FPS.

**Практическое решение — кэшировать дорогой эффект в offscreen-canvas один раз**, а в игровом цикле только `drawImage` уже готового результата:

```javascript
// ❌ Тень пересчитывается на каждый кадр для каждой частицы
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
// ✅ Эффект посчитан ОДИН РАЗ в offscreen-canvas, дальше — дешёвый drawImage
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
    ctx.drawImage(glowSprite, p.x - 20, p.y - 20); // просто копирование готовых пикселей
  });
}
```

Это тот же принцип "посчитать статику один раз", что и многослойные canvas в статье 02, применённый к дорогим визуальным эффектам вместо целых сцен.

## Экспорт: `toDataURL` vs `toBlob`

```javascript
const dataUrl = canvas.toDataURL('image/png'); // СИНХРОННО, блокирует главный поток
// Base64-строка раздувает размер данных примерно на треть по сравнению
// с бинарным представлением — дороже по памяти и по времени кодирования

canvas.toBlob((blob) => {
  // АСИНХРОННО — кодирование происходит без блокировки главного потока
  const formData = new FormData();
  formData.append('image', blob);
  fetch('/upload', { method: 'POST', body: formData });
}, 'image/png');
```

Правило: `toBlob` — предпочтительный выбор почти всегда, особенно для больших canvas и/или для отправки на сервер — `Blob` идёт в `FormData`/`fetch` напрямую, без раздувания в base64 и без синхронной блокировки. `toDataURL` оправдан только для мелких изображений или там, где действительно нужна именно строка (встраивание в `<img src>`/CSS напрямую).

`createImageBitmap(source)` — отдельный инструмент для декодирования изображений ВНЕ главного потока:

```javascript
const response = await fetch('/large-photo.jpg');
const blob = await response.blob();
const bitmap = await createImageBitmap(blob); // декодирование в фоне,
                                                // не блокирует главный поток
ctx.drawImage(bitmap, 0, 0); // рисуется как обычное изображение
```

В отличие от `new Image()` + `.onload` (где решающая часть работы — декодирование JPEG/PNG в растровые данные — может создавать заметный джанк на главном потоке для больших изображений), `createImageBitmap` явно выносит это декодирование за пределы главного потока.

## `OffscreenCanvas` + Worker: рендеринг полностью вне главного потока

В [Performance Debugging and Jank Hunting] (topic browser-animation) `OffscreenCanvas` упоминался как "мост" к этой теме — сигнал, что DOM-анимация физически упёрлась в потолок. Здесь — полная механика.

`canvas.transferControlToOffscreen()` передаёт управление рендерингом элемента в Worker-поток — ВСЯ последующая работа с контекстом (`getContext`, вызовы рисования) происходит там, а не на главном потоке:

```javascript
// main.js — главный поток
const canvas = document.querySelector('canvas');
const offscreen = canvas.transferControlToOffscreen();
const worker = new Worker('render-worker.js');
worker.postMessage({ canvas: offscreen }, [offscreen]); // передаём с transfer —
                                                          // owner переходит воркеру,
                                                          // главный поток больше
                                                          // не может рисовать в canvas

worker.postMessage({ type: 'input', x: mouseX, y: mouseY }); // ввод — единственное,
                                                               // что идёт через postMessage
```

```javascript
// render-worker.js — воркер-поток
let ctx;
self.onmessage = (e) => {
  if (e.data.canvas) {
    ctx = e.data.canvas.getContext('2d'); // getContext доступен и в Worker для OffscreenCanvas
    startLoop();
  }
  if (e.data.type === 'input') { /* обновить состояние на основе ввода */ }
};

function startLoop() {
  function loop(timestamp) {
    update();
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    draw(ctx); // весь игровой цикл статьи 02 — целиком в воркере
    requestAnimationFrame(loop); // rAF доступен и в Worker-контексте OffscreenCanvas
  }
  requestAnimationFrame(loop);
}
```

**Когда это оправдывает сложность:** тяжёлая, по-настоящему CPU-затратная попиксельная работа на каждый кадр — большое количество частиц, сложная симуляция, обработка изображений в реальном времени — где рендеринг реально конкурирует за главный поток с обработкой пользовательского ввода, React-рендерами и другой UI-работой, и это измеримо бьёт по отзывчивости (INP, статья browser-animation/06). **Когда НЕ оправдывает:** для лёгкого рисования архитектурная сложность (передача состояния через `postMessage`, синхронизация UI-состояния с воркером, дублирование части логики) перевешивает выгоду — большинство canvas-фич прекрасно работают на главном потоке без этого уровня инженерии.

## Связь с другими статьями

```txt
[Canvas 2D Fundamentals]              — примитивы рисования, поверх
                                         которых работает пиксельный
                                         уровень этой статьи
[Canvas Animation and Game Loop]      — цикл update/draw, в который
                                         встраивается кэширование
                                         дорогих эффектов и вынос в Worker
[Performance Debugging and Jank
 Hunting] (browser-animation)          — где OffscreenCanvas впервые
                                         упомянут как сигнал архитектурного
                                         потолка DOM-анимации
[Architecture and Performance for
 Canvas Apps]                          — систематизация кэширования
                                         эффектов, пулов и бюджетов памяти
                                         на уровне всего приложения
```

## Типичные ошибки на интервью

- **Не знать о стоимости `getImageData`** — вызывать его на каждый кадр анимации без осознания, что это точка синхронизации GPU→CPU, и не знать про `willReadFrequently` как способ снизить эту стоимость для частых чтений.

- **Путать `Uint8ClampedArray` с обычным `Uint8Array`** — не знать, что значения вне `[0, 255]` обрезаются (clamped), а не оборачиваются по модулю, и получать необъяснимые артефакты в собственных пиксельных фильтрах при переполнении.

- **Не суметь объяснить tainted canvas** — не знать, что рисование cross-origin изображения без корректных CORS-заголовков блокирует ЛЮБОЕ последующее чтение пикселей (`getImageData`/`toDataURL`/`toBlob`) с `SecurityError`, и что клиентский `crossOrigin` без серверных заголовков не помогает.

- **Считать `globalCompositeOperation` "финальным эффектом наложения"** — не понимать, что это режим смешивания, применяющийся к КАЖДОМУ вызову рисования, и не суметь объяснить механику scratch-card эффекта через `destination-out`.

- **Не знать про `lighter` для аддитивного свечения** — пытаться реализовать эффект "яркие частицы становятся ярче при перекрытии" через полупрозрачность и `source-over`, что даёт визуально другой (более тусклый, "плоский") результат.

- **Не различать `toDataURL` и `toBlob` по производительности** — использовать синхронный `toDataURL` для отправки больших изображений на сервер, не зная, что `toBlob` асинхронен и не раздувает данные в base64.

- **Не знать про `OffscreenCanvas` + Worker** — предлагать "просто оптимизировать код рисования" там, где реальная проблема — конкуренция рендеринга с UI-работой за главный поток, которую решает архитектурный вынос в Worker, а не точечная оптимизация.
