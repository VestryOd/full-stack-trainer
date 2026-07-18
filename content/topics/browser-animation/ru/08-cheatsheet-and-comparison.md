# Шпаргалка и сравнение технологий

Справочный материал по статьям 01-07 — без нового объяснения концепций, только компактные таблицы и сниппеты для быстрого использования. Если формулировка непонятна — она разобрана подробно в соответствующей статье, указанной в заголовке раздела.

## Часть 1: Шпаргалка

### CSS: свойства анимации/перехода — что дёшево, что дорого (статья 01)

| Свойство | Стадии конвейера | Стоимость |
|---|---|---|
| `transform`, `opacity` | Composite | Дёшево — компоузитор, GPU |
| `filter` (в поддерживающих браузерах может быть compositor-only) | Composite / Paint | Условно дёшево — зависит от движка и типа фильтра |
| `background-color`, `box-shadow`, `border-color` | Style → Paint → Composite | Средне — repaint без reflow |
| `width`, `height`, `top`, `left`, `margin`, `padding` | Style → Layout → Paint → Composite | Дорого — reflow, возможно каскадный |

### `transition` — синтаксис (статья 02)

```css
.el {
  transition-property: transform, opacity;
  transition-duration: 0.3s, 0.2s;
  transition-timing-function: ease-out, linear;
  transition-delay: 0s;
  transition-behavior: allow-discrete; /* разрешить переход дискретных свойств (display) */
}
```

### `@keyframes` / `animation-*` — лонгхенды (статья 02)

| Свойство | Значения | Частая ошибка |
|---|---|---|
| `animation-fill-mode` | `none` \| `forwards` \| `backwards` \| `both` | Забыть `forwards` → элемент "прыгает" обратно после анимации |
| `animation-direction` | `normal` \| `reverse` \| `alternate` \| `alternate-reverse` | Забыть про `alternate` для пульсации без "телепорта" |
| `animation-iteration-count` | число \| `infinite` | — |
| `animation-play-state` | `running` \| `paused` | Единственный способ поставить CSS-анимацию на паузу без JS-класса |

### Cubic-bezier пресеты, которые стоит помнить (статья 02)

```txt
ease          = cubic-bezier(0.25, 0.1, 0.25, 1.0)   — дефолт transition
ease-in       = cubic-bezier(0.42, 0.0, 1.0, 1.0)    — для уходящих элементов
ease-out      = cubic-bezier(0.0, 0.0, 0.58, 1.0)    — для появляющихся элементов
ease-in-out   = cubic-bezier(0.42, 0.0, 0.58, 1.0)   — переход между стабильными состояниями
Material fast-out-slow-in = cubic-bezier(0.05, 0.7, 0.1, 1)
Spring-подобный overshoot = cubic-bezier(0.34, 1.56, 0.64, 1)  — y > 1 даёт "bounce"
```

```css
/* steps() — не easing, а покадровая спрайт-анимация */
animation: walk 0.8s steps(8, jump-end) infinite;

/* linear() — piecewise-линейная кривая для многократного bounce/spring */
transition: transform 0.8s linear(0, 0.5 15%, 0.9 30%, 1.1 45%, 1 100%);
```

### `@property` — типизированные custom properties (статья 02)

```css
@property --angle {
  syntax: '<angle>';
  inherits: false;
  initial-value: 0deg;
}
```

### WAAPI — методы и свойства `Animation` (статья 03)

| Метод/свойство | Назначение |
|---|---|
| `element.animate(keyframes, options)` | Запуск, возвращает `Animation` |
| `.play()` / `.pause()` / `.reverse()` | Управление воспроизведением |
| `.finish()` | Доиграть мгновенно, сохраняя fill-эффект |
| `.cancel()` | Остановить и откатить к состоянию ДО анимации |
| `.playbackRate` | Скорость воспроизведения (может быть отрицательной) |
| `.currentTime` | Ручной scrubbing позиции |
| `.playState` | `idle` \| `running` \| `paused` \| `finished` |
| `.finished` | Promise, резолвится по завершении, реджектится по `cancel()` |
| `composite: 'add'` | Наложение независимых анимаций на одно свойство |
| `element.getAnimations()` / `document.getAnimations()` | Оркестрация набора анимаций |

```javascript
// Scroll-driven анимация через WAAPI (статья 03)
const timeline = new ViewTimeline({ subject: el, axis: 'block' });
el.animate({ opacity: [0, 1] }, { fill: 'both', timeline });
```

### Канонический rAF-цикл с delta time (статья 04)

```javascript
let previousTimestamp;
function tick(timestamp) {
  if (previousTimestamp === undefined) previousTimestamp = timestamp;
  const deltaMs = timestamp - previousTimestamp;
  previousTimestamp = timestamp;

  update(deltaMs / 1000); // передаём секунды, скорость — в единицах/сек

  requestAnimationFrame(tick);
}
requestAnimationFrame(tick);
```

### Минимальный FLIP-сниппет (статья 04)

```javascript
function flip(el, mutateFn) {
  const first = el.getBoundingClientRect();
  mutateFn();
  const last = el.getBoundingClientRect();
  const dx = first.left - last.left;
  const dy = first.top - last.top;

  el.style.transition = 'none';
  el.style.transform = `translate(${dx}px, ${dy}px)`;
  el.getBoundingClientRect(); // форсируем layout один раз
  el.style.transition = 'transform 0.3s ease';
  el.style.transform = '';
}
```

### GSAP — базовое API (статья 05)

| Вызов | Назначение |
|---|---|
| `gsap.to(target, vars)` | От текущего значения к заданному |
| `gsap.from(target, vars)` | От заданного значения к текущему |
| `gsap.fromTo(target, fromVars, toVars)` | Обе точки явно |
| `gsap.timeline()` | Оркестрация, `.to()`/`.from()` в цепочке с позиционными параметрами (`'-=0.2'`, метки) |
| `stagger: { each, from, grid }` | Волновое распределение задержек |
| `ScrollTrigger: { trigger, pin, scrub, start, end }` | Scroll-хореография с закреплением секции |

```javascript
gsap.timeline()
  .to('.a', { opacity: 1, duration: 0.4 })
  .to('.b', { opacity: 1, duration: 0.4 }, '-=0.2'); // на 0.2с раньше конца предыдущего
```

### Motion (Framer Motion) — базовые пропсы (статья 05)

| Проп | Назначение |
|---|---|
| `initial` / `animate` | Начальное и целевое состояние (декларативно, как функция стейта) |
| `exit` (внутри `AnimatePresence`) | Анимация при размонтировании — без этого React убирает узел мгновенно |
| `whileHover` / `whileTap` | Состояния на взаимодействие |
| `layout` | Автоматический FLIP при изменении геометрии между рендерами |
| `variants` + `staggerChildren` | Именованные состояния, оркестрация по дереву компонентов |
| `transition={{ type: 'spring', stiffness, damping }}` | Физическая, интеррупт-способная анимация (статья 04) |

```tsx
<AnimatePresence>
  {isOpen && (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    />
  )}
</AnimatePresence>
```

### `prefers-reduced-motion` — обязательный boilerplate (статья 07)

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

```javascript
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
window.matchMedia('(prefers-reduced-motion: reduce)')
  .addEventListener('change', (e) => applyMotionPreference(e.matches));
```

## Часть 2: Сравнение технологий

| Технология | Для чего лучше всего | Что умеет | Типичное реальное применение | Производительность | Ограничения |
|---|---|---|---|---|---|
| **CSS transitions** | Простой переход между двумя состояниями по триггеру | Interpolate одного изменения свойства | Hover/focus-состояния, открытие/закрытие панели | Compositor (для transform/opacity) | Нет произвольных промежуточных точек, нет программного контроля прогресса |
| **CSS `@keyframes`** | Самозапускающаяся, повторяющаяся анимация | Произвольные промежуточные точки, повтор, направление | Спиннеры, pulse-индикаторы, покадровые спрайты (`steps()`) | Compositor (для transform/opacity) | Нет динамических значений из JS без пересборки CSS |
| **WAAPI** | Программная анимация с тем же движком, что CSS | play/pause/reverse/scrub, промисы, composite modes, scroll-driven таймлайны | Динамические значения из данных, exit-анимации с `finished`, scrubbing | Compositor (для transform/opacity/filter) | Более многословный синтаксис, чем CSS для простых случаев |
| **rAF + ручной JS** | Полный контроль: физика, спринги, интерруптибельность | Всё, что можно выразить в коде | Drag-инерция, кастомные springs, курсор-фолловеры, canvas-анимация | Главный поток — всегда main-thread работа | Требует ручного delta time, склонность к джанку при тяжёлом JS |
| **GSAP** | Сложная timeline-оркестрация и scroll-хореография | Timeline с точным позиционированием, stagger-паттерны, `ScrollTrigger` pin/scrub | Брендовые лендинги, "сайты-истории", сложные onboarding-последовательности | В основном compositor-friendly свойства, но библиотека сама — JS на главном потоке | Дополнительный вес бандла, оверхед на простых задачах |
| **Motion (Framer Motion)** | React-интеграция: layout-анимации, exit-анимации, декларативная оркестрация | `layout` (авто-FLIP), `AnimatePresence`, variants, spring-физика по умолчанию | UI-анимации в React-приложениях, реордер списков, модалки с exit-переходом | Compositor там, где возможно, плюс JS-оркестрация | Смысл только в React-контексте; полный пакет тяжелее, чем "мини"-ядро |
| **Lottie** | Воспроизведение сложной векторной анимации из After Effects | Точное 1-в-1 воспроизведение дизайна аниматора, программный контроль сегментов | Onboarding-иллюстрации, брендированные лоадеры, персонажная анимация | Зависит от рендерера (`svg`/`canvas`/`html`), может быть тяжёлым для сложных сцен | Требует пайплайна bodymovin-экспорта, любое изменение — правка в AE и реэкспорт |
| **Scroll-driven animations (нативные)** | Простой scroll-linked прогресс без JS в пути скролла | `animation-timeline: scroll()`/`view()`, привязка прогресса к скроллу/видимости | Progress-бар чтения, reveal-on-scroll карточки, простой parallax | Compositor, полностью вне главного потока | Не умеет закреплять (pin) элемент — для сложной хореографии всё ещё нужен GSAP |
| **Canvas/WebGL** *(см. топик [Canvas & Graphics])* | Тысячи независимо анимируемых объектов, кастомный рендеринг | Полный контроль растеризации, произвольная графика вне DOM | Частицы, игры, сложные визуализации данных, генеративная графика | Отдельный рендер-контекст, может уйти в Worker через `OffscreenCanvas` | Нет DOM-доступности "из коробки", нет CSS-каскада, больше низкоуровневого кода |

**Как использовать эту таблицу на практике:** начинать с верхних строк (CSS transitions/keyframes/WAAPI) и спускаться вниз только тогда, когда конкретная задача упирается в реальное ограничение текущего уровня — а не выбирать инструмент "потому что он мощнее" в отрыве от того, что вообще требуется сделать.
