# Анимация на canvas и игровой цикл

## От статичного рисунка к живому canvas

В статье 01 разобрано, что canvas — immediate-mode: нарисованные пиксели ничего не помнят о себе. Отсюда прямое следствие: анимация на canvas не может быть "измени свойство — браузер сам перерисует" (как в CSS/WAAPI, см. [rAF and JS-Driven Animation]) — единственный способ показать движение — **стереть предыдущий кадр и нарисовать новый с нуля**, много раз в секунду.

Каноническая delta-time петля на `requestAnimationFrame` уже разобрана в [rAF and JS-Driven Animation] — там она нужна, чтобы двигать ОДНО значение независимо от частоты дисплея. Здесь та же петля становится **игровым циклом**: вместо одного значения — целое состояние мира (позиции, скорости, счёт, столкновения), и вместо "анимировать переход" — "симулировать и отрисовать текущий момент этой симуляции".

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

Разделение `update` и `draw` — не стилистическая прихоть: `update` — чистая логика (числа, физика, правила игры), которая не знает о существовании `ctx` и может быть протестирована обычным unit-тестом без канваса вообще (статья 08 разбирает это подробнее); `draw` — единственное место, которое трогает `ctx`, и не содержит логики принятия решений, только отображение уже посчитанного состояния.

## Fixed timestep vs variable timestep

Обычная delta-time петля (как выше) — **variable timestep**: `dt` каждый кадр разный, зависит от реальной частоты кадров. Для визуальной анимации одного значения это нормально. Для **физики и игровой логики** — источник проблем:

```txt
Проблема variable timestep для физики:
  - При скачке dt (лаг, смена вкладки, слабое устройство) быстро движущийся
    объект может "проскочить" сквозь препятствие за один большой шаг —
    коллизия просто не будет замечена (эффект "туннелирования")
  - Один и тот же уровень игры физически ведёт себя ПО-РАЗНОМУ на разных
    устройствах, даже если код идентичен — потому что шаг интегрирования
    скорости разный при разном dt (накопление ошибок численного
    интегрирования зависит от размера шага)
  - Воспроизводимость (replay, детерминированные тесты) невозможна —
    результат симуляции зависит от того, КАК именно распределились
    кадры во времени
```

Решение — **fixed timestep с аккумулятором**: физика всегда шагает одинаковыми маленькими порциями времени, независимо от реальной частоты кадров; накопленное "лишнее" время между физическими шагами используется для интерполяции визуальной позиции между двумя последними физическими состояниями:

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
                                          // если кадр был АНОМАЛЬНО долгим
                                          // (вкладка была свёрнута), не пытаться
                                          // "нагнать" сотни физических шагов разом

  accumulator += frameTime;

  while (accumulator >= FIXED_DT) {
    previousState = { ...currentState };
    updatePhysics(currentState, FIXED_DT); // ВСЕГДА одинаковый шаг
    accumulator -= FIXED_DT;
  }

  const alpha = accumulator / FIXED_DT; // сколько "осталось" между шагами, 0..1
  const renderState = interpolate(previousState, currentState, alpha);

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  draw(ctx, renderState); // рисуем ПРОМЕЖУТОЧНОЕ, сглаженное состояние

  requestAnimationFrame(loop);
}
```

Практический смысл: физика становится детерминированной и одинаковой на любом устройстве, а интерполяция (`alpha`) убирает визуальную "ступенчатость", которая иначе возникла бы при рендере ровно на шагах физики (`FIXED_DT` может не совпадать с частотой дисплея). Для казуальных браузерных игр и большинства демо-эффектов честный variable timestep вполне достаточен — fixed timestep оправдан, когда есть настоящая физика столкновений, соревновательная логика или воспроизводимость критична.

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

Это НЕ retained-mode сцена, как в Pixi/three.js (статьи 05-06) — массив сущностей не самостоятельная структура, которую canvas "знает" и умеет перерисовывать выборочно; это просто обычные JS-объекты, которые вы сами каждый кадр перебираете и рисуете заново, целиком опираясь на immediate-mode модель статьи 01.

## Многослойные canvas: самая дешёвая крупная оптимизация

Если часть сцены статична (фон, декоративные элементы, UI-рамка) и не меняется каждый кадр, перерисовывать её вместе с динамическим содержимым — чистая трата CPU. Решение — несколько `<canvas>`-элементов, наложенных друг на друга через CSS:

```html
<div style="position: relative; width: 800px; height: 600px;">
  <canvas id="background" style="position: absolute; inset: 0;"></canvas>
  <canvas id="foreground" style="position: absolute; inset: 0;"></canvas>
</div>
```

```javascript
// Фон рисуется ОДИН РАЗ, не в игровом цикле
const bgCtx = document.getElementById('background').getContext('2d');
drawStaticBackground(bgCtx); // градиент, звёзды, декор — посчитано один раз

// В игровом цикле трогается ТОЛЬКО foreground
const fgCtx = document.getElementById('foreground').getContext('2d');
function loop(timestamp) {
  // ...
  fgCtx.clearRect(0, 0, canvas.width, canvas.height);
  draw(fgCtx); // только динамические сущности
  requestAnimationFrame(loop);
}
```

Эффект особенно заметен, когда статичный фон сам по себе дорог для рисования (сложный градиент, сотни декоративных элементов) — без разделения на слои эта стоимость платится КАЖДЫЙ кадр впустую, хотя реально требуется посчитать её один раз.

## Sprite sheets и 9-аргументная форма `drawImage`

Спрайт-лист — одно изображение с несколькими кадрами анимации, расположенными в сетке. `drawImage` в полной форме позволяет вырезать произвольный прямоугольник ИЗ исходного изображения и вставить его в произвольное место И размер на canvas:

```javascript
ctx.drawImage(
  image,
  sx, sy, sWidth, sHeight, // откуда вырезать В ИСХОДНОМ изображении
  dx, dy, dWidth, dHeight, // куда вставить и какого размера НА CANVAS
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
    playerX, playerY, FRAME_WIDTH, FRAME_HEIGHT,               // вставить на позицию игрока
  );
}
```

Один спрайт-лист + вычисляемый `sx` по индексу кадра — стандартный паттерн 2D-игр, избегающий отдельного `<img>`/загрузки на каждый кадр анимации.

## Hit detection: три подхода

**Математический (AABB/окружность)** — самый дешёвый и самый частый в реальном коде:

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
// НЕ вызывая fill()/stroke() — просто проверка попадания в путь
const isHit = ctx.isPointInPath(clickX, clickY);
```

Удобно для неправильных/сложных форм, которые уже описаны как canvas-путь и которые лень (или невыгодно) дублировать отдельной математической моделью.

**Color-picking на скрытом canvas** — решает hit-testing для СЛОЖНЫХ, перекрывающихся, произвольно неправильных фигур точно, без математики вообще: каждый интерактивный объект рисуется на невидимом offscreen-canvas сплошным уникальным цветом (без сглаживания!), и по клику читается цвет пикселя под курсором:

```javascript
const hitCanvas = document.createElement('canvas');
hitCanvas.width = canvas.width; hitCanvas.height = canvas.height;
const hitCtx = hitCanvas.getContext('2d', { willReadFrequently: true });
hitCtx.imageSmoothingEnabled = false; // ОБЯЗАТЕЛЬНО: сглаживание "размажет" цвета на границах

const colorToEntity = new Map();
entities.forEach((entity, i) => {
  const color = `rgb(${(i + 1) & 255}, 0, 0)`; // уникальный "id-цвет" на объект
  colorToEntity.set(color, entity);
  hitCtx.fillStyle = color;
  entity.drawHitShape(hitCtx); // та же геометрия, что и в drawing, но одним цветом
});

canvas.addEventListener('click', (e) => {
  const pixel = hitCtx.getImageData(e.offsetX, e.offsetY, 1, 1).data;
  const color = `rgb(${pixel[0]}, ${pixel[1]}, ${pixel[2]})`;
  const clickedEntity = colorToEntity.get(color);
});
```

Это работает точно для любой формы (звёзды, произвольные полигоны, наложенные друг на друга объекты), ценой дополнительного offscreen-рендер-прохода на каждое изменение сцены — детали работы с пикселями (`getImageData`, стоимость) разобраны в статье 03.

## Пауза при уходе со вкладки

Браузер сам троттлит/приостанавливает `requestAnimationFrame` в фоновых вкладках (см. [rAF and JS-Driven Animation]), но для игровой логики этого недостаточно самого по себе: если приостановить ТОЛЬКО рендер, а физический аккумулятор продолжает копить `dt` (или использует `Date.now()` напрямую), при возврате на вкладку `frameTime` окажется огромным — без клампа (`Math.min(frameTime, 0.25)` из примера fixed timestep выше) симуляция попытается "нагнать" часы или даже дни пропущенного времени за один кадр.

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

Этот пример намеренно небольшой, но собирает вместе все компоненты статьи: разделение `update`/`draw`, delta-time петлю, entity-подобную структуру данных (`ball`, `paddle` как обычные объекты), математический hit detection (AABB для ракетки) — то, с чего реально начинается любая браузерная игра или интерактивная canvas-фича.

## Связь с другими статьями

```txt
[Canvas 2D Fundamentals]                — immediate-mode модель, которая
                                           делает explicit-цикл clear→
                                           update→draw обязательным
[rAF and JS-Driven Animation]           — базовая delta-time rAF-петля,
                                           расширенная здесь до полноценного
                                           игрового цикла с состоянием
[Pixels, Images, and Effects]           — работа с пикселями color-picking
                                           подхода к hit detection
[Architecture and Performance for
 Canvas Apps]                            — object pooling, dirty rectangles
                                           и другие оптимизации, которые
                                           надстраиваются над этим циклом
                                           в реальном продакшен-приложении
```

## Типичные ошибки на интервью

- **Не разделять `update` и `draw`** — писать одну функцию, которая одновременно мутирует состояние и рисует, что делает логику непроверяемой без canvas и затрудняет добавление fixed timestep позже.

- **Не знать разницы fixed vs variable timestep** — не суметь объяснить, почему физика при variable timestep может вести себя по-разному на разных устройствах, и что такое "туннелирование" при скачке `dt`.

- **Не клампить `dt` после лага/фоновой вкладки** — не предвидеть "спираль смерти": если реальный `frameTime` не ограничен сверху, симуляция после возврата на вкладку пытается досчитать огромный промежуток времени за один кадр, что делает лаг ещё хуже.

- **Перерисовывать статичный фон каждый кадр** — не знать про многослойные canvas как самую дешёвую оптимизацию, вместо этого пытаться "оптимизировать" сам рисующий код статичного фона.

- **Использовать только математический hit detection там, где формы сложные и перекрывающиеся** — не знать про color-picking на скрытом canvas как точную альтернативу написанию геометрии пересечения произвольных полигонов вручную.

- **Полагаться только на браузерное троттлинг rAF в фоне** — не осознавать, что паузу для ИГРОВОЙ логики (таймеры, физика) нужно реализовывать явно через `visibilitychange`, а не полагаться исключительно на то, что браузер сам замедлит рендер.
