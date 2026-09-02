# Анимация на canvas и игровой цикл

## От статичного рисунка к живому canvas

Анимация на canvas — это **стереть предыдущий кадр и нарисовать новый с нуля**, много раз в секунду. Так работает immediate-mode модель из статьи 01: нарисованные пиксели ничего не помнят о себе.

Поэтому анимация на canvas не может быть "измени свойство — браузер сам перерисует". Так работают CSS и Web Animations API (WAAPI), и их разбирает статья rAF and JS-Driven Animation. Canvas так не умеет.

Петля здесь становится **игровым циклом**: она владеет целым состоянием мира, а не одним значением. Каноническая delta-time петля на `requestAnimationFrame` разобрана в статье rAF and JS-Driven Animation, где она двигает одно значение независимо от частоты дисплея. Здесь состояние — это позиции, скорости, счёт и столкновения. Вместо "анимировать переход" вы симулируете текущий момент и отрисовываете его.

```javascript
let previousTimestamp;
function loop(timestamp) {
  if (previousTimestamp === undefined) previousTimestamp = timestamp;
  const dt = (timestamp - previousTimestamp) / 1000; // секунды, как в статье rAF
  previousTimestamp = timestamp;

  update(dt);                                  // изменить состояние мира
  ctx.clearRect(0, 0, canvas.width, canvas.height); // стереть предыдущий кадр
  draw(ctx);                                    // нарисовать состояние мира заново

  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
```

Разделение `update` и `draw` — не стилистическая прихоть. Функция `update` — чистая логика: числа, физика, правила игры. Она не знает о существовании `ctx`, поэтому её можно проверить обычным модульным тестом, вообще без канваса (подробнее — в статье 08). Функция `draw` — единственное место, которое трогает `ctx`. Решений она не принимает и только отображает уже посчитанное состояние.

## Fixed timestep vs variable timestep

Обычная delta-time петля (как выше) — **variable timestep**: `dt` каждый кадр разный, зависит от реальной частоты кадров. Для визуальной анимации одного значения это нормально. Для **физики и игровой логики** — источник проблем:

- При скачке `dt` (лаг, смена вкладки, слабое устройство) быстро движущийся объект может проскочить сквозь препятствие за один большой шаг. Коллизия просто не будет замечена — это эффект "туннелирования".
- Один и тот же уровень игры физически ведёт себя **по-разному** на разных устройствах, даже если код идентичен. Шаг интегрирования скорости разный при разном `dt`, поэтому и ошибка численного интегрирования накапливается по-разному.
- Воспроизводимость (повторы, детерминированные тесты) становится невозможной. Результат симуляции зависит от того, **как** именно распределились кадры во времени.

Решение — **fixed timestep с аккумулятором**, то есть фиксированный шаг. Физика всегда шагает одинаковыми маленькими порциями времени, независимо от реальной частоты кадров. Накопленное "лишнее" время между физическими шагами идёт на интерполяцию визуальной позиции между двумя последними физическими состояниями:

```javascript
const FIXED_DT = 1 / 60; // физика всегда шагает по 1/60 секунды
let accumulator = 0;
let previousState = {};
let currentState = {};

function loop(timestamp) {
  if (previousTimestamp === undefined) previousTimestamp = timestamp;
  let frameTime = (timestamp - previousTimestamp) / 1000;
  previousTimestamp = timestamp;

  frameTime = Math.min(frameTime, 0.25); // защита от "спирали смерти" —
                                          // если кадр был аномально долгим
                                          // (вкладка была свёрнута), не пытаться
                                          // "нагнать" сотни физических шагов разом

  accumulator += frameTime;

  while (accumulator >= FIXED_DT) {
    previousState = { ...currentState };
    updatePhysics(currentState, FIXED_DT); // всегда одинаковый шаг
    accumulator -= FIXED_DT;
  }

  const alpha = accumulator / FIXED_DT; // сколько "осталось" между шагами, 0..1
  const renderState = interpolate(previousState, currentState, alpha);

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  draw(ctx, renderState); // рисуем промежуточное, сглаженное состояние

  requestAnimationFrame(loop);
}
```

Практический смысл: физика становится детерминированной и одинаковой на любом устройстве. Интерполяция (`alpha`) вдобавок убирает визуальную "ступенчатость". Без неё ступенчатость видна, когда рендер попадает ровно на шаги физики, а `FIXED_DT` может не совпадать с частотой дисплея.

Для казуальных браузерных игр и большинства демо-эффектов честный variable timestep вполне достаточен. Fixed timestep оправдан, когда есть настоящая физика столкновений, соревновательная логика или жёсткое требование воспроизводимости.

## Паттерн "сущность" (entity): минимальная архитектура

Самая простая работающая архитектура для canvas-анимации с множеством объектов — плоский массив сущностей, каждая со своими `update`/`draw`:

```javascript
class Ball {
  constructor(x, y, vx, vy, radius) {
    Object.assign(this, { x, y, vx, vy, radius });
  }

  update(dt) {
    this.x += this.vx * dt;
    this.y += this.vy * dt;
    if (this.x - this.radius < 0 || this.x + this.radius > canvas.width) this.vx *= -1;
    if (this.y - this.radius < 0 || this.y + this.radius > canvas.height) this.vy *= -1;
  }

  draw(ctx) {
    ctx.beginPath();
    ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
    ctx.fill();
  }
}

const entities = [new Ball(100, 100, 150, 200, 12), new Ball(300, 200, -100, 180, 8)];

function update(dt) { entities.forEach((e) => e.update(dt)); }
function draw(ctx) { entities.forEach((e) => e.draw(ctx)); }
```

Это **не** retained-mode сцена, как в Pixi или three.js (статьи 05-06). Массив сущностей — не самостоятельная структура, которую canvas "знает" и умеет перерисовывать выборочно. Это обычные JS-объекты, которые вы сами каждый кадр перебираете и рисуете заново, целиком опираясь на immediate-mode модель статьи 01.

## Многослойные canvas: самая дешёвая крупная оптимизация

Если часть сцены статична и не меняется каждый кадр, перерисовывать её вместе с динамическим содержимым — чистая трата CPU (central processing unit, центральный процессор). Статична — это фон, декоративные элементы или рамка UI (user interface, пользовательский интерфейс). Решение — несколько `<canvas>`-элементов, наложенных друг на друга через CSS:

```html
<div style="position: relative; width: 800px; height: 600px;">
  <canvas id="background" style="position: absolute; inset: 0;"></canvas>
  <canvas id="foreground" style="position: absolute; inset: 0;"></canvas>
</div>
```

```javascript
// Фон рисуется один раз, не в игровом цикле
const bgCtx = document.getElementById('background').getContext('2d');
drawStaticBackground(bgCtx); // градиент, звёзды, декор — посчитано один раз

// В игровом цикле трогается только foreground
const fgCanvas = document.getElementById('foreground');
const fgCtx = fgCanvas.getContext('2d');
function loop(timestamp) {
  // ...
  fgCtx.clearRect(0, 0, fgCanvas.width, fgCanvas.height);
  draw(fgCtx); // только динамические сущности
  requestAnimationFrame(loop);
}
```

Эффект особенно заметен, когда статичный фон сам по себе дорог для рисования: сложный градиент, сотни декоративных элементов. Без разделения на слои эта стоимость платится **каждый** кадр впустую, хотя посчитать её достаточно один раз.

## Спрайт-листы и 9-аргументная форма `drawImage`

Спрайт-лист (sprite sheet) — одно изображение с несколькими кадрами анимации, расположенными в сетке. Полная форма `drawImage` вырезает произвольный прямоугольник из исходного изображения. Дальше она вставляет вырезанное на canvas в произвольное место и произвольного размера:

```javascript
ctx.drawImage(
  image,
  sx, sy, sWidth, sHeight, // откуда вырезать в исходном изображении
  dx, dy, dWidth, dHeight, // куда вставить на canvas и какого размера
);
```

```javascript
// Покадровая анимация персонажа из спрайт-листа 8 кадров по 64×64px в ряд
const FRAME_WIDTH = 64;
const FRAME_HEIGHT = 64;
let currentFrame = 0;
let frameTimer = 0;
const FRAME_DURATION = 0.1; // секунд на кадр

function update(dt) {
  frameTimer += dt;
  if (frameTimer >= FRAME_DURATION) {
    frameTimer -= FRAME_DURATION;
    currentFrame = (currentFrame + 1) % 8;
  }
}

function draw(ctx) {
  ctx.drawImage(
    spriteSheet,
    currentFrame * FRAME_WIDTH, 0, FRAME_WIDTH, FRAME_HEIGHT, // вырезать i-й кадр
    playerX, playerY, FRAME_WIDTH, FRAME_HEIGHT, // вставить на позицию игрока
  );
}
```

Один спрайт-лист плюс вычисляемый по индексу кадра `sx` — стандартный паттерн 2D-игр. Он избавляет от отдельного `<img>` и отдельной загрузки на каждый кадр анимации.

## Определение попадания: три подхода

**Математический (AABB или окружность)** — самый дешёвый и самый частый в реальном коде. AABB расшифровывается как axis-aligned bounding box: прямоугольник, стороны которого параллельны осям.

```javascript
function pointInRect(px, py, rect) {
  return px >= rect.x && px <= rect.x + rect.width &&
         py >= rect.y && py <= rect.y + rect.height;
}

function pointInCircle(px, py, circle) {
  const dx = px - circle.x, dy = py - circle.y;
  return dx * dx + dy * dy <= circle.radius * circle.radius; // без sqrt — дешевле
}
```

**`isPointInPath()`/`isPointInStroke()`** — спросить у самого контекста, попадает ли точка в накопленный путь, без ручной геометрии:

```javascript
ctx.beginPath();
ctx.arc(150, 100, 50, 0, Math.PI * 2);
// не вызывая fill()/stroke() — просто проверка попадания в путь
const isHit = ctx.isPointInPath(clickX, clickY);
```

Удобно для неправильных/сложных форм, которые уже описаны как canvas-путь и которые лень (или невыгодно) дублировать отдельной математической моделью.

**Подбор по цвету (color-picking) на скрытом canvas** — решает определение попадания точно для сложных, перекрывающихся, произвольно неправильных фигур, вообще без математики. Каждый интерактивный объект рисуется на невидимом внеэкранном canvas сплошным уникальным цветом, со сглаживанием выключенным. По клику читается цвет пикселя под курсором:

```javascript
const hitCanvas = document.createElement('canvas');
hitCanvas.width = canvas.width; hitCanvas.height = canvas.height;
const hitCtx = hitCanvas.getContext('2d', { willReadFrequently: true });
hitCtx.imageSmoothingEnabled = false; // обязательно: сглаживание размажет цвета на границах

const colorToEntity = new Map();
entities.forEach((entity, i) => {
  const color = `rgb(${(i + 1) & 255}, 0, 0)`; // уникальный "id-цвет" на объект
  colorToEntity.set(color, entity);
  hitCtx.fillStyle = color;
  entity.drawHitShape(hitCtx); // та же геометрия, что при отрисовке, но одним цветом
});

canvas.addEventListener('click', (e) => {
  const pixel = hitCtx.getImageData(e.offsetX, e.offsetY, 1, 1).data;
  const color = `rgb(${pixel[0]}, ${pixel[1]}, ${pixel[2]})`;
  const clickedEntity = colorToEntity.get(color);
});
```

Это работает точно для любой формы: звёзды, произвольные полигоны, наложенные друг на друга объекты. Цена — дополнительный внеэкранный проход отрисовки на каждое изменение сцены. Детали работы с пикселями, включая `getImageData` и его стоимость, разобраны в статье 03.

## Пауза при уходе со вкладки

Браузер сам замедляет и приостанавливает `requestAnimationFrame` в фоновых вкладках, об этом говорит статья rAF and JS-Driven Animation. Для игровой логики этого недостаточно. Может остановиться только рендер, а физический аккумулятор продолжит копить `dt` или читать `Date.now()` напрямую. Тогда при возврате на вкладку `frameTime` окажется огромным.

Без ограничения сверху симуляция попытается нагнать часы или даже дни пропущенного времени за один кадр. Это ограничение — `Math.min(frameTime, 0.25)` из примера fixed timestep выше.

```javascript
let isPaused = false;
document.addEventListener('visibilitychange', () => {
  isPaused = document.hidden;
  if (!isPaused) previousTimestamp = undefined; // сбросить точку отсчёта dt,
                                                  // чтобы не получить огромный
                                                  // первый dt после возврата
});

function loop(timestamp) {
  if (isPaused) { requestAnimationFrame(loop); return; }
  // ...обычная логика update/draw
  requestAnimationFrame(loop);
}
```

## Собираем всё вместе: минимальный Pong

```javascript
const canvas = document.querySelector('canvas');
const ctx = canvas.getContext('2d');

const ball = { x: 400, y: 300, vx: 240, vy: 180, radius: 8 };
const paddle = { x: 20, y: 250, width: 12, height: 100, vy: 0 };
let score = 0;

function update(dt) {
  ball.x += ball.vx * dt;
  ball.y += ball.vy * dt;

  if (ball.y - ball.radius < 0 || ball.y + ball.radius > canvas.height) ball.vy *= -1;
  if (ball.x + ball.radius > canvas.width) ball.vx *= -1; // отскок от правой стены

  paddle.y += paddle.vy * dt;

  // AABB-проверка столкновения мяча с ракеткой (математический hit detection)
  const hitsPaddle =
    ball.x - ball.radius < paddle.x + paddle.width &&
    ball.x + ball.radius > paddle.x &&
    ball.y > paddle.y && ball.y < paddle.y + paddle.height;

  if (hitsPaddle && ball.vx < 0) {
    ball.vx *= -1;
    score += 1;
  } else if (ball.x - ball.radius < 0) {
    ball.x = 400; ball.y = 300; score = 0; // мимо ракетки — сброс
  }
}

function draw(ctx) {
  ctx.fillStyle = '#111';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.fillStyle = 'white';
  ctx.fillRect(paddle.x, paddle.y, paddle.width, paddle.height);

  ctx.beginPath();
  ctx.arc(ball.x, ball.y, ball.radius, 0, Math.PI * 2);
  ctx.fill();

  ctx.font = '20px monospace';
  ctx.fillText(`Score: ${score}`, canvas.width - 140, 30);
}

let previousTimestamp;
function loop(timestamp) {
  if (previousTimestamp === undefined) previousTimestamp = timestamp;
  const dt = (timestamp - previousTimestamp) / 1000;
  previousTimestamp = timestamp;

  update(dt);
  draw(ctx); // fillRect фона заменяет clearRect — заодно и фон, и очистка
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
```

Этот пример намеренно небольшой, но собирает вместе все компоненты статьи. В нём разделены `update` и `draw`, работает delta-time петля, а данные лежат в структуре из сущностей: `ball` и `paddle` как обычные объекты. Попадание определяется математически, проверкой AABB для ракетки. Ровно с этого реально начинается любая браузерная игра или интерактивная canvas-фича.

## Связь с другими статьями

- [Canvas 2D: фундамент](./01-canvas-2d-fundamentals.md) — immediate-mode модель, из-за которой явный цикл «очистить → обновить → нарисовать» обязателен.
- rAF and JS-Driven Animation — базовая delta-time петля на `requestAnimationFrame`, расширенная здесь до полноценного игрового цикла с состоянием.
- [Пиксели, изображения и эффекты](./03-pixels-images-and-effects.md) — работа с пикселями, на которой стоит подбор по цвету.
- [Архитектура и производительность canvas-приложений](./08-architecture-and-performance-for-canvas-apps.md) — пул объектов, «грязные» прямоугольники и другие оптимизации поверх этого цикла.

## Типичные ошибки на интервью

- **Не разделять `update` и `draw`.** Писать одну функцию, которая одновременно мутирует состояние и рисует. Логика становится непроверяемой без canvas, а добавить fixed timestep позже труднее.

- **Не знать разницы fixed vs variable timestep.** Не суметь объяснить, почему физика при variable timestep ведёт себя по-разному на разных устройствах. И не знать, что такое "туннелирование" при скачке `dt`.

- **Не ограничивать `dt` сверху после лага или фоновой вкладки.** Это сценарий "спирали смерти". Если реальный `frameTime` не ограничен, после возврата на вкладку симуляция досчитывает огромный промежуток времени за один кадр. Лаг от этого только хуже.

- **Перерисовывать статичный фон каждый кадр.** Не знать про многослойные canvas как самую дешёвую оптимизацию и вместо этого пытаться "оптимизировать" сам рисующий код фона.

- **Использовать только математику там, где формы сложные и перекрывающиеся.** Не знать про подбор по цвету на скрытом canvas как точную альтернативу. Иначе остаётся писать геометрию пересечения произвольных полигонов вручную.

- **Полагаться только на то, что браузер замедлит `requestAnimationFrame` в фоне.** Паузу для **игровой** логики (таймеры, физика) нужно реализовывать явно, через `visibilitychange`. Одного замедления рендера браузером недостаточно.
