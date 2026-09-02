# Пиксели, изображения и эффекты

## Уровень ниже примитивов

Эта статья работает на уровень ниже примитивов рисования. Здесь вы не рисуете фигуры, а напрямую читаете и пишете значения RGBA (red, green, blue, alpha) каждого отдельного пикселя буфера. Статьи 01-02 оставались на уровне "нарисуй прямоугольник" и "нарисуй путь".

Это открывает три класса задач, недостижимых через `fillRect` и `drawImage`. Первый — попиксельные фильтры изображений. Второй — трюки композитинга вроде эффекта стирающегося слоя (scratch-card). Третий, в конце статьи, — полный вынос рендеринга с главного потока.

## `ImageData`: чтение и запись буфера напрямую

```javascript
const imageData = ctx.getImageData(x, y, width, height); // читает область буфера
console.log(imageData.width, imageData.height);
console.log(imageData.data); // Uint8ClampedArray — сырые байты RGBA

ctx.putImageData(imageData, x, y); // пишет буфер обратно
```

**`getImageData` стоит дорого.** Canvas 2D может рендериться с ускорением на GPU (graphics processing unit, графический процессор). Запрос сырых пикселей на стороне CPU (central processing unit, центральный процессор) вынуждает синхронизацию. Браузер обязан дождаться, пока GPU закончит текущую работу. Затем он копирует содержимое буфера из памяти GPU в обычную память процесса.

Эта точка синхронизации может стоить заметного времени, особенно в цикле на каждом кадре. Вызов `getImageData` на каждый кадр анимации — частая причина внезапного проседания FPS (frames per second, кадров в секунду).

Подсказка `willReadFrequently: true` при получении контекста заставляет браузер с самого начала держать буфер в памяти, доступной CPU. Так браузер избегает повторных копий GPU→CPU:

```javascript
const ctx = canvas.getContext('2d', { willReadFrequently: true });
```

`putImageData`, в отличие от `fillRect` и `drawImage`, **игнорирует** текущую трансформацию, `globalCompositeOperation` и область отсечения. Это прямая побайтовая запись в буфер. Это не "рисование" в обычном смысле контекста как машины состояний (статья 01).

## `Uint8ClampedArray`: раскладка RGBA и разница с `Uint8Array`

`imageData.data` — плоский массив байт, по 4 значения на пиксель, построчно:

```txt
data[0] = R пикселя (0,0)   data[4] = R пикселя (1,0)
data[1] = G пикселя (0,0)   data[5] = G пикселя (1,0)
data[2] = B пикселя (0,0)   data[6] = B пикселя (1,0)
data[3] = A пикселя (0,0)   data[7] = A пикселя (1,0)
```

`Clamped` в имени типа — не формальность. При записи значения вне диапазона `[0, 255]` оно **обрезается** до границы: 255 при переполнении, 0 при отрицательном. Обычный `Uint8Array` вместо этого обернул бы значение по модулю 256.

Для арифметики фильтров это критично. Пусть `pixel + 50` даёт 280. Обычный `Uint8Array` вернёт `280 % 256 = 24` — визуально случайный тёмный пиксель вместо ожидаемого яркого. `Uint8ClampedArray` корректно даёт `255`.

**Рабочий пример: обесцвечивание (grayscale) и пороговый фильтр (threshold)**

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

Если на canvas нарисовано изображение с **другого** origin без корректных CORS-заголовков, canvas помечается как **tainted**, испорченный. CORS расшифровывается как cross-origin resource sharing. Браузер после этого намеренно блокирует любое чтение его пиксельных данных — `getImageData`, `toDataURL`, `toBlob` — и бросает `SecurityError`.

Это не баг и не строгость ради строгости. Это защита от использования canvas как "оракула" для кражи содержимого приватных cross-origin изображений. Атакующий мог бы определить, залогинен ли пользователь на другом сайте: загрузить его приватную аватарку и прочитать её пиксели.

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
// ✅ Явно запросить CORS-режим — работает только если сервер
// изображения отдаёт заголовок Access-Control-Allow-Origin
const img = new Image();
img.crossOrigin = 'anonymous';
img.src = 'https://other-domain.com/photo.jpg';
img.onload = () => {
  ctx.drawImage(img, 0, 0);
  canvas.toDataURL(); // ✅ работает, если сервер разрешил CORS
};
```

Частый практический сценарий: пользователь загружает фото, мы применяем фильтр на canvas, а экспорт в файл падает с непонятной ошибкой. Причина почти всегда именно эта. Клиентский `crossOrigin` без соответствующего заголовка на сервере **не** помогает. Оба условия обязательны одновременно.

## `globalCompositeOperation`: как рисование смешивается с уже нарисованным

Важно правильно понять масштаб этого свойства. Это не одно смешивание, применяемое ко всей сцене в конце. Это режим, применяющийся к **каждому вызову рисования** и определяющий, как новые пиксели комбинируются с уже существующими в буфере под ними.

### `destination-out`: полный scratch-card эффект

Новая фигура **стирает** существующее содержимое там, где она рисуется: режим работает как ластик, а не как краска. Именно на этом построены эффекты "сотри и узнай приз":

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

  ctx.globalCompositeOperation = 'destination-out'; // ключевая строка:
  // всё, что рисуется дальше, стирает существующие пиксели вместо
  // того, чтобы рисоваться поверх них
  ctx.beginPath();
  ctx.arc(e.offsetX, e.offsetY, 20, 0, Math.PI * 2);
  ctx.fill(); // "дырка" в слое фольги — под ней виден базовый слой
});
```

Это **полная** рабочая механика scratch-card эффекта. Трёх составляющих достаточно для реального продакшен-компонента без дополнительных библиотек: базовый слой, слой фольги и кисть-ластик через `destination-out`.

### Остальные практически важные режимы

- `source-atop` — новый рисунок виден только **там**, где под ним уже есть непрозрачное содержимое. Он обрезается силуэтом существующего содержимого. Это удобно, чтобы перекрашивать или тонировать внутри уже нарисованного силуэта, не выходя за его границы.
- `multiply` — каналы цвета перемножаются, поэтому результат всегда темнее исходных цветов. Классический режим для наложения тени и затемнения поверх существующей сцены.
- `screen` — визуально противоположность `multiply`: результат всегда светлее. Используется для эффектов засветки и бликов.
- `lighter` — значения каналов складываются, это аддитивное смешивание. Классический приём для свечения и частиц. Перекрывающиеся яркие частицы (искры, огонь, свет) в местах перекрытия становятся ярче, а не просто рисуются друг поверх друга.

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
// создавая естественный эффект скопления света, а не плоского наложения
```

Как и любое состояние контекста (статья 01), `globalCompositeOperation` нужно явно возвращать к `'source-over'` или оборачивать в `save()`/`restore()`. Иначе следующий кусок кода, ничего не знающий об этой смене, начнёт рисоваться в неожиданном режиме смешивания.

## Тени и `filter`: те же CSS-эффекты, но с реальной стоимостью на каждый кадр

```javascript
ctx.shadowColor = 'rgba(0,0,0,0.4)';
ctx.shadowBlur = 12;
ctx.shadowOffsetX = 4;
ctx.shadowOffsetY = 4;
// тень рисуется автоматически при любом fill, stroke или drawImage
ctx.fillRect(50, 50, 100, 100);

ctx.filter = 'blur(4px) brightness(1.2)'; // тот же синтаксис CSS filter (статья
                                            // browser-animation, где filter уже
                                            // разбирался как CSS-свойство)
ctx.drawImage(image, 0, 0);
```

Стоимость реальная. `shadowBlur` и `filter: blur()` — это фактически программный проход размытия по растеризованным пикселям, на **каждый** вызов рисования. В immediate-mode модели всё перерисовывается каждый кадр (статья 02). Поэтому стоимость платится заново 60 раз в секунду, для каждого затронутого объекта. На большом количестве анимируемых объектов с тенью или размытием это частый источник резкого падения FPS.

**Практическое решение — один раз закэшировать дорогой эффект во внеэкранном canvas**, а в игровом цикле только `drawImage` уже готового результата:

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
// ✅ Эффект посчитан один раз во внеэкранном canvas, дальше — дешёвый drawImage
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

Это тот же принцип "посчитать статику один раз", что и многослойные canvas в статье 02. Здесь он применён к дорогим визуальным эффектам вместо целых сцен.

## Экспорт: `toDataURL` vs `toBlob`

```javascript
const dataUrl = canvas.toDataURL('image/png'); // синхронно, блокирует главный поток
// Base64-строка раздувает размер данных примерно на треть по сравнению
// с бинарным представлением — дороже по памяти и по времени кодирования

canvas.toBlob((blob) => {
  // асинхронно — кодирование происходит без блокировки главного потока
  const formData = new FormData();
  formData.append('image', blob);
  fetch('/upload', { method: 'POST', body: formData });
}, 'image/png');
```

Правило: `toBlob` — предпочтительный выбор почти всегда, особенно для больших canvas и для отправки на сервер. `Blob` идёт в `FormData` и `fetch` напрямую, без раздувания в base64 и без синхронной блокировки. Используйте `toDataURL` только для мелких изображений или там, где действительно нужна именно строка: встраивание в `<img src>` или в CSS напрямую.

`createImageBitmap(source)` — отдельный инструмент для декодирования изображений вне главного потока:

```javascript
const response = await fetch('/large-photo.jpg');
const blob = await response.blob();
const bitmap = await createImageBitmap(blob); // декодирование в фоне,
                                                // не блокирует главный поток
ctx.drawImage(bitmap, 0, 0); // рисуется как обычное изображение
```

`new Image()` вместе с `.onload` декодирует файл на главном потоке. Решающая работа здесь — декодирование JPEG (joint photographic experts group) или PNG (portable network graphics) в растровые данные. Для больших изображений это создаёт заметные подвисания. `createImageBitmap` явно выносит декодирование за пределы главного потока.

## `OffscreenCanvas` + Worker: рендеринг полностью вне главного потока

`OffscreenCanvas` переносит рендеринг в поток-воркер, и здесь разобрана полная механика. Топик browser-animation уже упоминал его в статье Performance Debugging and Jank Hunting как "мост" к этой теме. Там он появился как сигнал, что анимация через DOM (document object model, дерево объектов страницы в браузере) физически упёрлась в потолок.

`canvas.transferControlToOffscreen()` передаёт управление рендерингом элемента в поток-воркер. **Вся** последующая работа с контекстом идёт там, а не на главном потоке: `getContext`, вызовы рисования, всё остальное.

```javascript
// main.js — главный поток
const canvas = document.querySelector('canvas');
const offscreen = canvas.transferControlToOffscreen();
const worker = new Worker('render-worker.js');
worker.postMessage({ canvas: offscreen }, [offscreen]); // передаём с transfer —
                                                          // владение переходит воркеру,
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
    ctx = e.data.canvas.getContext('2d'); // getContext доступен и в воркере
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

**Когда воркер оправдывает сложность:** тяжёлая, по-настоящему CPU-затратная попиксельная работа на каждый кадр. Большое количество частиц, сложная симуляция, обработка изображений в реальном времени.

Там рендеринг реально конкурирует за главный поток с обработкой пользовательского ввода, React-рендерами и другой работой UI (user interface, пользовательский интерфейс). Это измеримо бьёт по отзывчивости, которую меряют метрикой INP (Interaction to Next Paint); см. статью browser-animation/06.

**Когда не оправдывает:** при лёгком рисовании архитектурная сложность перевешивает выгоду. Эта сложность — передача состояния через `postMessage`, синхронизация состояния интерфейса с воркером, дублирование части логики. Большинство canvas-фич прекрасно работают на главном потоке без такого уровня инженерии.

## Связь с другими статьями

- [Canvas 2D: фундамент](./01-canvas-2d-fundamentals.md) — примитивы рисования, поверх которых работает пиксельный уровень этой статьи.
- [Анимация на canvas и игровой цикл](./02-canvas-animation-and-game-loop.md) — цикл update/draw, в который встраивается кэширование дорогих эффектов и вынос в воркер.
- Performance Debugging and Jank Hunting (browser-animation) — где `OffscreenCanvas` впервые упомянут как сигнал архитектурного потолка анимации через DOM.
- [Архитектура и производительность canvas-приложений](./08-architecture-and-performance-for-canvas-apps.md) — систематизация кэширования эффектов, пулов и бюджетов памяти на уровне всего приложения.

## Типичные ошибки на интервью

- **Не знать о стоимости `getImageData`.** Вызывать его на каждый кадр анимации, не осознавая, что это точка синхронизации GPU→CPU. И не знать про `willReadFrequently` как способ снизить эту стоимость для частых чтений.

- **Путать `Uint8ClampedArray` с обычным `Uint8Array`.** Не знать, что значения вне `[0, 255]` обрезаются, а не оборачиваются по модулю. Симптом — необъяснимые артефакты в собственных пиксельных фильтрах при переполнении.

- **Не суметь объяснить tainted canvas.** Рисование cross-origin изображения без корректных CORS-заголовков блокирует **любое** последующее чтение пикселей (`getImageData`, `toDataURL`, `toBlob`) с `SecurityError`. Клиентский `crossOrigin` без серверных заголовков не помогает.

- **Считать `globalCompositeOperation` финальным эффектом наложения.** Это режим смешивания, применяющийся к **каждому** вызову рисования. Следом обычно не удаётся объяснить механику scratch-card эффекта через `destination-out`.

- **Не знать про `lighter` для аддитивного свечения.** Пытаться получить эффект «яркие частицы становятся ярче при перекрытии» через полупрозрачность и `source-over`. Результат выходит визуально другим: более тусклым и плоским.

- **Не различать `toDataURL` и `toBlob` по производительности.** Использовать синхронный `toDataURL` для отправки больших изображений на сервер. При этом `toBlob` асинхронен и не раздувает данные в base64.

- **Не знать про `OffscreenCanvas` с воркером.** Предлагать «просто оптимизировать код рисования» там, где реальная проблема — конкуренция рендеринга с работой интерфейса за главный поток. Это решает архитектурный вынос в воркер, а не точечная оптимизация.
