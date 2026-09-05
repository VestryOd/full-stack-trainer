# Web Animations API

## Что такое WAAPI на самом деле — и почему это не "альтернатива CSS"

Частое заблуждение: Web Animations API (WAAPI) воспринимают как третий, отдельный способ анимировать элементы — наряду с CSS-переходами и `requestAnimationFrame` (rAF). На самом деле WAAPI — это **тот же самый движок**, который исполняет `transition` и `@keyframes` (см. [CSS Transitions и Keyframes](./02-css-transitions-and-keyframes.md)). Сверху добавлен только программный JS-интерфейс.

Когда вы пишете `element.animate(...)`, браузер создаёт ровно такой же внутренний `KeyframeEffect`, как если бы вы описали `@keyframes` в CSS. Свойства те же:

- интерполяция по типу значения;
- возможность работать на компоузитор-потоке для `transform`/`opacity` (см. [Rendering Pipeline и Frame Budget](./01-rendering-pipeline-and-frame-budget.md));
- та же timing model.

Разница не в производительности "CSS быстрее/JS медленнее" — а в том, **откуда берутся значения и кто ими управляет**. CSS хорош, когда keyframe-значения известны заранее, на этапе написания стилей. WAAPI нужен, когда:

- целевое значение вычисляется в рантайме (перетаскивание, физика, данные с сервера)
- анимацией нужно управлять программно: приостановить, развернуть, замедлить, дождаться завершения через промис
- нужно комбинировать несколько независимых анимаций на одном свойстве, не переписывая CSS-классы

Именно поэтому создание анимации через переключение CSS-классов "на каждое динамическое значение" — анти-паттерн, который решается напрямую через WAAPI, без потери производительности CSS-движка.

## `element.animate()`: синтаксис и форматы keyframes

```javascript
const animation = element.animate(keyframes, options);
```

Keyframes можно задать в двух эквивалентных форматах:

```javascript
// Формат 1: массив объектов-кадров (явные offset-позиции)
element.animate(
  [
    { transform: 'translateY(0)',   opacity: 1, offset: 0 },
    { transform: 'translateY(-8px)', opacity: 0.6, offset: 0.5 },
    { transform: 'translateY(0)',   opacity: 1, offset: 1 },
  ],
  { duration: 600, easing: 'ease-in-out' },
);

// Формат 2: объект с массивами значений по свойствам —
// браузер сам равномерно распределяет offset между значениями
element.animate(
  {
    transform: ['translateY(0)', 'translateY(-8px)', 'translateY(0)'],
    opacity: [1, 0.6, 1],
  },
  { duration: 600, easing: 'ease-in-out' },
);
```

Второй формат удобнее для динамически генерируемых keyframes (например, когда список промежуточных значений собирается в цикле из данных), потому что не нужно вручную считать `offset` для каждой точки.

`options` — тот же набор параметров, что и `animation-*` в CSS, но в виде camelCase-объекта:

```javascript
element.animate(keyframes, {
  duration: 300,        // ↔ animation-duration
  easing: 'ease-out',   // ↔ animation-timing-function
  delay: 100,           // ↔ animation-delay
  endDelay: 0,           // ждать после конца, прежде чем animation считается finished
  iterations: 3,          // ↔ animation-iteration-count (Infinity для infinite)
  direction: 'alternate', // ↔ animation-direction
  fill: 'forwards',       // ↔ animation-fill-mode
  iterationStart: 0,      // с какой точки цикла [0..iterations) начать
  composite: 'replace',   // как комбинируется с underlying-значением — см. ниже
});
```

## Жизненный цикл `Animation`: не «запустил и забыл»

`element.animate()` возвращает объект `Animation` — программный пульт управления запущенной анимацией, а не одноразовый вызов:

```javascript
const anim = element.animate(
  { transform: ['scale(1)', 'scale(1.2)'] },
  { duration: 400, easing: 'ease-out', fill: 'forwards' },
);

anim.pause();                 // приостановить в текущей позиции
anim.play();                  // продолжить
anim.reverse();               // проиграть в обратную сторону от текущей позиции
anim.finish();                // мгновенно доскочить до конечного состояния
anim.cancel();                // остановить и откатить к состоянию до анимации
                               // (в отличие от finish — cancel убирает fill-эффект)

anim.playbackRate = 2;        // ускорить в 2 раза "на лету", без перезапуска
anim.playbackRate = -1;       // проиграть назад с той же скоростью

console.log(anim.currentTime);  // текущая позиция на временной шкале (мс)
anim.currentTime = 200;         // "перемотать" вручную — полезно для scrubbing
                                 // (например, синхронизация с drag-жестом
                                 // пользователя без пересоздания анимации)

console.log(anim.playState);    // 'idle' | 'running' | 'paused' | 'finished'
```

Практический пример: анимация, управляемая ползунком. Перетаскивание ползунка выполняет scrubbing — перемотку анимации в любую точку по времени. Через CSS `transition` это в принципе невозможно: там нет способа программно поставить прогресс на произвольную точку:

```javascript
const timeline = element.animate(
  { transform: ['translateX(0)', 'translateX(300px)'] },
  { duration: 1000, fill: 'both' },
);
timeline.pause(); // сразу ставим на паузу — управляем вручную

slider.addEventListener('input', (e) => {
  const progress = Number(e.target.value) / 100; // 0..1
  timeline.currentTime = progress * 1000;         // прогресс анимации = позиция слайдера
});
```

## `animation.finished`: промисы вместо `setTimeout`-гадания

До WAAPI было всего два способа узнать, что анимация точно закончилась. Первый — слушать событие `transitionend` или `animationend`, у которого есть известные подводные камни:

- может не сработать при `display: none`;
- может сработать несколько раз, если переходят несколько свойств;
- может не сработать вовсе, если элемент удалён из DOM раньше времени. DOM — это document object model, дерево объектов страницы в браузере.

Второй — `setTimeout` на предполагаемую длительность. Это хрупко: не учитываются изменения `playbackRate` и паузы.

`Animation.finished` — промис, который резолвится, когда анимация закончилась естественным путём, и **реджектится**, если её отменили через `cancel()`:

```javascript
async function animateOutAndRemove(element) {
  const anim = element.animate(
    { opacity: [1, 0], transform: ['scale(1)', 'scale(0.9)'] },
    { duration: 250, easing: 'ease-in', fill: 'forwards' },
  );

  try {
    await anim.finished;       // ждём именно завершения, без гадания по времени
    // удаляем DOM-узел только после того, как анимация реально доиграла
    element.remove();
  } catch {
    // анимация была отменена (например, элемент понадобился снова) — ничего не делаем
  }
}
```

Это решает классическую проблему exit-анимаций в компонентных фреймворках (см. также AnimatePresence в статье 05). React размонтирует DOM-узел синхронно в момент вызова `setState`, а любая CSS-анимация на нём обрывается вместе с узлом. Промис `animation.finished` даёт точку, в которой можно достоверно отложить фактическое удаление до конца анимации.

## Composite modes: `replace`, `add`, `accumulate`

Composite mode определяет, как значение анимации **комбинируется** с уже существующим (underlying) значением свойства — либо от предыдущей анимации, либо от обычного CSS.

```txt
replace     (по умолчанию) — значение анимации полностью
              заменяет underlying-значение. Как обычный
              CSS transition/animation.
add         — значение анимации складывается с
              underlying-значением (для transform матрицы
              перемножаются, а не заменяются)
accumulate  — похоже на add, но специфично для многократных итераций
              одной анимации: каждая следующая итерация продолжает
              накапливать значение с того места, где закончилась
              предыдущая (унаследовано из SMIL/SVG-анимации)
```

`composite: 'add'` решает конкретную практическую задачу: наложение **независимых** анимаций на одно и то же свойство без ручного пересчёта комбинированной матрицы трансформации:

```javascript
// Базовая "живая" анимация — лёгкое покачивание идущее постоянно
element.animate(
  { transform: ['translateY(0px)', 'translateY(-4px)', 'translateY(0px)'] },
  { duration: 2000, iterations: Infinity, easing: 'ease-in-out' },
);

// При клике добавляем поверх текущего покачивания короткий "bounce",
// не прерывая и не пересчитывая базовую анимацию вручную
button.addEventListener('click', () => {
  element.animate(
    { transform: ['scale(1)', 'scale(1.15)', 'scale(1)'] },
    { duration: 300, composite: 'add' },
  );
});
// Итоговый transform на каждый момент времени — комбинация обеих
// анимаций (браузер сам перемножает матрицы), а не подмена одной другой
```

Без `composite: 'add'` вторая анимация использует `composite: 'replace'` — это дефолт. Она просто перебила бы первую на время своего выполнения. После её окончания элемент "прыгнул" бы обратно к состоянию первой анимации.

Это визуально дёрганый скачок. Многие пытаются лечить его руками, вычисляя комбинированный transform в JS. Режим `composite: 'add'` снимает эту задачу с разработчика полностью.

## `getAnimations()`: оркестрация набора анимаций

`Element.prototype.getAnimations()` и `Document.prototype.getAnimations()` возвращают список всех активных (и недавно завершённых, до сборки мусора) `Animation`-объектов на элементе или во всём документе:

```javascript
// Отменить все текущие анимации элемента перед запуском новой —
// частый паттерн для избежания "накопления" анимаций при быстром
// повторном взаимодействии пользователя (например, спам-клики)
function animateExclusive(element, keyframes, options) {
  element.getAnimations().forEach((anim) => anim.cancel());
  return element.animate(keyframes, options);
}
```

```javascript
// Дождаться завершения всех анимаций на странице перед,
// например, снятием скриншота или переходом к следующему шагу теста
async function waitForAllAnimations() {
  const animations = document.getAnimations();
  await Promise.all(animations.map((a) => a.finished));
}
```

Это то, чего в принципе не было в чисто CSS-модели. Чтобы узнать, что где-то на странице что-то анимируется, раньше было два пути. Либо вручную отслеживать состояние в JS, либо заранее расставлять обработчики `transitionend` на каждый элемент.

## Почему WAAPI лучше ручного переключения CSS-классов для динамических значений

```javascript
// ❌ Переключение классов для динамического значения —
// требует генерировать CSS на лету или заводить класс на каждый
// возможный случай, и ломается при повторном триггере без
// принудительного reflow
function highlightProgress(bar, percent) {
  bar.className = `progress progress--${percent}`; // класса progress--73 не существует
  // Альтернатива — inline style, но тогда для повторного запуска
  // transition на то же значение нужен трюк с forced reflow:
  bar.style.transition = 'none';
  bar.style.width = '0%';
  void bar.offsetWidth; // форсированный synchronous layout — см. статью 01
  bar.style.transition = 'width 0.3s ease';
  bar.style.width = `${percent}%`;
}
```

```javascript
// ✅ WAAPI — прямое значение из переменной, без генерации CSS
// и без reflow-хаков; каждый вызов создаёт чистый, независимый Animation
function highlightProgress(bar, percent) {
  bar.animate(
    { width: [`${bar.getBoundingClientRect().width}px`, `${percent}%`] },
    { duration: 300, easing: 'ease', fill: 'forwards' },
  );
}
```

Второй пример неидеален с точки зрения производительности: `width` — layout-triggering свойство, дороже, чем `transform` (см. статью 01). Но он иллюстрирует главное. WAAPI принимает произвольное JS-значение напрямую, без промежуточного шага "сначала сформировать CSS".

Речь про перетаскивание, drag-and-drop списки, анимацию на основе физики курсора. Для `transform`/`opacity`-анимаций с динамическими значениями это единственный чистый способ не городить генерацию классов или инлайн-стилей вручную.

## Производительность: тот же движок, что и CSS — а не rAF-цикл

Важное разграничение, которое часто путают на собеседованиях: WAAPI — это **не** то же самое, что "написать `requestAnimationFrame`-цикл на JS" (статья 04). Хотя обе техники управляются из JS, у них принципиально разная модель исполнения:

```txt
rAF-цикл (ручной):
  Каждый кадр → JS-колбэк выполняется на главном потоке →
  вычисляет новое значение → пишет style →
  браузер пересчитывает Style/(Layout)/Paint/Composite
  Если главный поток занят, колбэк опаздывает
  и кадр может быть пропущен

WAAPI (element.animate):
  Браузер получает полное описание анимации один раз →
  дальнейшее воспроизведение для transform/opacity/filter
  может идти на компоузиторе, без обращения к главному потоку
  каждый кадр — как и в случае с CSS-переходами
```

Это значит, что WAAPI-анимация на `transform` продолжит идти гладко, даже если главный поток занят тяжёлым JS. Тем же свойством обладают CSS-transitions и keyframes, потому что это буквально тот же движок. rAF-цикл такого свойства не имеет по определению: он и **есть** работа главного потока.

## Scroll-driven animations: `ScrollTimeline` и `ViewTimeline`

До появления этой возможности анимация "прогресс зависит от скролла" всегда требовала JS-обработчика события `scroll`. Такой обработчик на каждый скролл-евент вручную вычисляет прогресс и обновляет стиль, а событий бывают десятки в секунду. Отсюда риск layout thrashing, и всё это на главном потоке.

Scroll-driven animations выносят эту связь в декларативную модель, независимую от главного потока.

Ключевое разграничение, которое стоит чётко проговаривать на интервью:

```txt
Scroll-linked (это то, что делают ScrollTimeline/ViewTimeline):
  Прогресс анимации напрямую равен позиции скролла.
  Нет своих "часов" — currentTime анимации это функция
  от scrollTop/viewport-пересечения. Прокрутили назад —
  анимация тоже пошла назад, синхронно, без интерполяции по времени.

Scroll-triggered (то, что обычно делает GSAP ScrollTrigger
  в "play once" режиме, или IntersectionObserver + CSS-класс):
  Скролл лишь запускает обычную time-based анимацию
  (со своей длительностью и easing), дальше она идёт
  независимо от скролла, по собственным часам.
```

CSS-форма — `animation-timeline`:

```css
/* Scroll-linked: прогресс-бар вверху страницы, привязанный
   напрямую к прокрутке всего документа */
@keyframes grow-progress {
  from { transform: scaleX(0); }
  to   { transform: scaleX(1); }
}
.reading-progress-bar {
  animation: grow-progress linear;
  animation-timeline: scroll(root); /* источник — скролл root-элемента */
  transform-origin: left;
}
```

```css
/* Scroll-linked через ViewTimeline: элемент проявляется по мере
   входа в viewport и уходит по мере выхода, без IntersectionObserver */
@keyframes reveal {
  from { opacity: 0; transform: translateY(24px); }
  to   { opacity: 1; transform: translateY(0); }
}
.reveal-card {
  animation: reveal linear both;
  animation-timeline: view();       /* таймлайн = видимость элемента во вьюпорте */
  animation-range: entry 0% cover 40%; /* с момента входа до 40% покрытия */
}
```

WAAPI-форма — те же таймлайны как объекты, передаваемые в `animate()`:

```javascript
const timeline = new ViewTimeline({
  subject: document.querySelector('.reveal-card'),
  axis: 'block',
});

document.querySelector('.reveal-card').animate(
  { opacity: [0, 1], transform: ['translateY(24px)', 'translateY(0)'] },
  { fill: 'both', timeline },
);
```

Практическая ценность для продакшена — знакомый список эффектов: параллакс, прогресс-бары чтения, reveal-on-scroll-карточки. Раньше все они требовали `scroll`-листенера с throttle- или rAF-обёрткой. Статья 06 разбирает, почему наивный scroll-хендлер — источник jank. Теперь они исполняются на компоузиторе декларативно, без единой строчки JS на путь скролла.

## View Transitions API: снимок "было/стало" без ручного кроссфейда

Классическая задача возникает при переходе между состояниями: открыли модалку, переключили вкладку, изменили layout списка. Хочется красивого перехода: "старое состояние плавно превращается в новое".

Но старое и новое DOM-состояния физически не существуют одновременно. Раньше это делали вручную: клонировали старый узел, накладывали поверх нового, кроссфейдили через `opacity`. Клон потом чистили руками.

`document.startViewTransition()` делает это встроенно:

```javascript
function switchToGridLayout() {
  if (!document.startViewTransition) {
    applyGridLayout(); // фолбэк для браузеров без поддержки — просто применяем без анимации
    return;
  }

  document.startViewTransition(() => {
    applyGridLayout(); // любая синхронная мутация DOM/классов внутри колбэка
  });
}
```

Механика по шагам:

```txt
1. Браузер делает "снимок" (screenshot) текущего состояния DOM
2. Выполняется переданный колбэк — здесь происходит реальное
   изменение DOM/классов/состояния (может быть синхронным
   или возвращать промис для асинхронных обновлений)
3. Браузер делает снимок нового состояния DOM
4. Между двумя снимками браузер по умолчанию проигрывает
   плавный cross-fade — управляемый через псевдоэлементы
   ::view-transition-old(root) и ::view-transition-new(root)
```

Кастомизация перехода — обычный CSS на псевдоэлементы:

```css
::view-transition-old(root) {
  animation: fade-out 0.25s ease-out;
}
::view-transition-new(root) {
  animation: fade-in 0.25s ease-in;
}
```

Некоторым отдельным элементам нужен эффект "shared element". Карточка в списке плавно превращается в hero-изображение на детальной странице. Раньше этот "магический" переход требовал FLIP-техники (First / Last / Invert / Play) вручную, см. статью 04. Теперь достаточно присвоить именованный `view-transition-name`:

```css
.product-card__image {
  view-transition-name: product-hero; /* браузер сам анимирует
    переход между старой и новой геометрией элемента с этим именем */
}
```

Важное ограничение для этой темы. Здесь разобрана same-document форма: переходы внутри одностраничного приложения (SPA), где документ остаётся тем же и меняется только его состояние.

Cross-document View Transitions расширяют ту же идею на навигацию в многостраничном приложении (MPA), где каждая навигация — это загрузка отдельной HTML-страницы. У них свои нюансы конфигурации, задаваемые через `@view-transition` в CSS. В контексте этой темы важно знать об их существовании, но детали — за рамками DOM-, CSS- и JS-анимации одного документа.

## Связь с другими статьями

- [CSS Transitions и Keyframes](./02-css-transitions-and-keyframes.md) — тот же движок keyframes и timing, что WAAPI использует под капотом.
- [requestAnimationFrame и JS-driven анимация](./04-raf-and-js-driven-animation.md) — FLIP-техника, которую View Transitions во многом заменяют для shared-element переходов.
- [Диагностика производительности и охота за джанком](./06-performance-debugging-and-jank-hunting.md) — почему наивный scroll-листенер был проблемой, которую решают scroll-driven animations.
- [Библиотеки анимации и экосистема](./05-animation-libraries-and-ecosystem.md) — Motion (Framer Motion) использует WAAPI под капотом там, где это возможно.

## Типичные ошибки на интервью

- **"WAAPI — это как rAF, только с другим синтаксисом"** — фундаментально неверно. WAAPI использует тот же движок, что CSS transitions/keyframes, и может исполняться на компоузиторе; rAF-цикл — это всегда JS-код на главном потоке, исполняющийся заново каждый кадр.

- **Путать `cancel()` и `finish()`** — `finish()` мгновенно доигрывает анимацию до конца и оставляет fill-эффект, если задан. А `cancel()` останавливает анимацию и **полностью** откатывает элемент к состоянию до её начала, игнорируя fill-mode.

- **Не знать, что `animation.finished` реджектится при `cancel()`** — код с `await anim.finished` без `try/catch` может привести к необработанному promise rejection. Так бывает, если анимация была отменена: например, пользователь быстро кликнул дважды.

- **Не понимать composite modes** — пытаться вручную вычислять "комбинированный" transform в JS для двух одновременных анимаций на одном элементе, не зная про `composite: 'add'`, который решает эту задачу нативно.

- **Путать scroll-linked и scroll-triggered** — не суметь объяснить разницу. У ScrollTimeline и ViewTimeline прогресс — функция скролла, своих часов нет. А у GSAP (GreenSock Animation Platform) ScrollTrigger в play-once режиме скролл лишь запускает независимую time-based анимацию.

- **Не знать про View Transitions API** — предлагать вручную клонировать DOM-узлы и кроссфейдить через `opacity` там, где `document.startViewTransition()` решает ту же задачу декларативно и с меньшим количеством кода.

- **Не проверять поддержку `startViewTransition` перед вызовом** — вызывать API без фолбэка, что ломает приложение в браузерах без поддержки вместо того, чтобы просто применить изменение без анимации.
