# Паттерны архитектуры CSS

## Базовая проблема, которую решают все CSS-архитектуры

У CSS есть два свойства, делающих его сложным в масштабе:

1. **Глобальная область видимости** — каждый селектор конкурирует со всеми остальными в документе. Встроенных границ модулей нет.
2. **Эскалация специфичности** — когда стиль не применяется, инстинктивное решение — сделать селектор более специфичным. Это создаёт храповик: специфичность только растёт, переопределения становятся всё сложнее.

Каждая CSS-архитектура — BEM, CSS Modules, CSS-in-JS, Tailwind — это разный ответ на один вопрос: **как не дать глобальной области видимости и эскалации специфичности сделать CSS неподдерживаемым?**

## BEM — Block Element Modifier

### Соглашение об именовании

BEM — соглашение об именовании, кодирующее иерархию компонентов в именах классов:

```
блок              → .card
блок__элемент     → .card__header
блок__элемент     → .card__body
блок__элемент     → .card__footer
блок--модификатор → .card--featured
элемент--мод.     → .card__header--large
```

```html
<article class="card card--featured">
  <header class="card__header card__header--large">
    <h2 class="card__title">Заголовок</h2>
    <span class="card__tag">Новое</span>
  </header>
  <div class="card__body">
    <p class="card__description">...</p>
  </div>
  <footer class="card__footer">
    <button class="card__action card__action--primary">Читать далее</button>
  </footer>
</article>
```

```css
.card { background: white; border-radius: 8px; }
.card--featured { border: 2px solid #0066cc; }
.card__header { padding: 16px 16px 0; }
.card__header--large { padding: 24px 24px 0; }
.card__title { font-size: 1.25rem; font-weight: 700; }
.card__body { padding: 16px; }
.card__footer { padding: 0 16px 16px; }
.card__action { display: inline-flex; padding: 8px 16px; }
.card__action--primary { background: #0066cc; color: white; }
```

### Почему BEM работает — логика, а не только конвенция

Сила BEM не в двойном подчёркивании — а в ограничении: **каждый селектор является единственным классом со специфичностью `(0, 1, 0)`**.

Без BEM:
```css
.card .header { }           /* (0, 2, 0) */
.card .header .title { }    /* (0, 3, 0) */
.featured .card .title { }  /* (0, 3, 0) — одинаковая специфичность, побеждает порядок */
```

Каждое новое правило может создать конфликт специфичности. Переопределение чего угодно требует совпадения или превышения существующей специфичности.

С BEM:
```css
.card__header { }   /* (0, 1, 0) */
.card__title { }    /* (0, 1, 0) */
.card--featured { } /* (0, 1, 0) */
```

Всё — `(0, 1, 0)`. **Конфликтов специфичности нет** — побеждает последнее правило (порядок в источнике). Переопределение тривиально: любой селектор выше `(0, 1, 0)` победит.

Имя кодирует отношение: `.card__title` говорит, что это заголовок внутри карточки — без вложенности в селекторе. Можно переместить HTML, изменить DOM-структуру, и стили по-прежнему работают — связанность в имени, а не в иерархии селекторов.

### Ловушки BEM

**Не зеркалить DOM-вложенность в именах BEM:**

```html
<!-- Неправильно: глубина BEM следует глубине DOM -->
<div class="card">
  <div class="card__body">
    <div class="card__body__content">  <!-- card__body__content — неправильно -->
      <p class="card__body__content__text">  <!-- ещё хуже -->

<!-- Правильно: плоский BEM, независимо от DOM-вложенности -->
<div class="card">
  <div class="card__body">
    <div class="card__content">  <!-- элемент card, а не card__body -->
      <p class="card__text">
```

Элементы принадлежат Блоку, а не другим Элементам. BEM не поддерживает вложенность элементов — выравнивайте: `card__content`.

**Модификаторы дополняют, а не заменяют:**

```html
<!-- Неправильно: модификатор заменяет базовый класс -->
<button class="card__action--primary">

<!-- Правильно: модификатор дополняет базовый класс -->
<button class="card__action card__action--primary">
```

Без базового класса пришлось бы дублировать все базовые стили в модификаторе.

**Когда создавать новый Блок vs использовать Элемент:**

Вопрос: "Может ли этот компонент существовать независимо?" Если да — новый Блок. Если имеет смысл только внутри другого компонента — Элемент.

```css
/* .card__action — элемент, существует только внутри карточек */
/* .button — блок, может существовать где угодно */
```

### BEM не решает проблему глобальной области видимости

BEM по-прежнему помещает классы в глобальную CSS-область. Два разработчика могут создать `.card__title` с разными намерениями. В небольших командах работает (конвенции + ревью). В крупных командах или при интеграции сторонних компонентов — проблема.

## CSS Modules

CSS Modules решают проблему глобальной области, **автоматически привязывая имена классов к файлу, в котором они определены**. При сборке каждое имя класса преобразуется в уникальный идентификатор:

```css
/* card.module.css */
.card { background: white; border-radius: 8px; }
.header { padding: 16px; }
.title { font-size: 1.25rem; }
.action { padding: 8px 16px; }
.actionPrimary { background: #0066cc; color: white; }
```

```javascript
// Card.tsx
import styles from './card.module.css';

function Card() {
  return (
    <article className={styles.card}>
      <header className={styles.header}>
        <h2 className={styles.title}>Заголовок</h2>
      </header>
      <footer>
        <button className={`${styles.action} ${styles.actionPrimary}`}>
          Читать далее
        </button>
      </footer>
    </article>
  );
}
```

Итоговый HTML:
```html
<article class="card_card__3xK9p">
  <header class="card_header__7mP2a">
    <h2 class="card_title__1vRq8">Заголовок</h2>
  </header>
  <footer>
    <button class="card_action__2nJ4k card_actionPrimary__8cD3m">
      Читать далее
    </button>
  </footer>
</article>
```

Сгенерированные имена классов уникальны — конфликты между файлами исключены.

### Возможности CSS Modules

**`:global` — выход из области видимости:**

```css
/* Этот класс применяется глобально, без scoping */
:global(.third-party-class) { color: red; }

/* Смешанный подход */
:global(.theme-dark) .card { background: #1a1a2e; }
```

**`composes` — наследование стилей:**

```css
/* base.module.css */
.button {
  display: inline-flex;
  padding: 8px 16px;
  border-radius: 4px;
  font-weight: 600;
}

/* card.module.css */
.action {
  composes: button from './base.module.css';
  /* Добавляет класс 'button' к элементу — без дублирования стилей */
  background: #0066cc;
  color: white;
}
```

`composes` добавляет составной класс к элементу в runtime — элемент получает оба имени в HTML, стили не копируются.

### Что CSS Modules не решают

- Нет динамических стилей на основе состояния JavaScript — нужно переключать классы, а не менять значения свойств
- Нет совместного размещения стилей и логики (отдельные файлы)
- Многословный синтаксис для условных классов
- Scoping — это конвенция этапа сборки: сгенерированный CSS по-прежнему глобален в production, просто с уникальными именами

## CSS-in-JS

CSS-in-JS пишет стили как JavaScript, рядом с компонентом. Два доминирующих подхода: **runtime** (Styled Components, Emotion) и **zero-runtime** (Linaria, vanilla-extract, StyleX).

### Runtime CSS-in-JS (Styled Components, Emotion)

```typescript
// Styled Components
import styled from 'styled-components';

const Card = styled.article<{ featured?: boolean }>`
  background: white;
  border-radius: 8px;
  border: ${({ featured }) => featured ? '2px solid #0066cc' : 'none'};
`;

const CardTitle = styled.h2`
  font-size: 1.25rem;
  font-weight: 700;
`;

const ActionButton = styled.button<{ variant?: 'primary' | 'secondary' }>`
  display: inline-flex;
  padding: 8px 16px;
  background: ${({ variant }) => variant === 'primary' ? '#0066cc' : 'transparent'};
  color: ${({ variant }) => variant === 'primary' ? 'white' : '#0066cc'};
`;

// Использование:
<Card featured>
  <CardTitle>Заголовок</CardTitle>
  <ActionButton variant="primary">Читать далее</ActionButton>
</Card>
```

**Как runtime CSS-in-JS работает под капотом:**

1. При рендеринге JavaScript вычисляет template literal с текущими props
2. Генерируется уникальное имя класса (обычно хеш от содержимого стилей)
3. В `<head>` вставляется тег `<style>` с CSS для этого имени класса
4. Сгенерированное имя класса применяется к элементу

Динамические стили (на основе props) генерируют новые имена классов — каждая уникальная комбинация значений props может создать новое CSS-правило.

**Преимущества runtime CSS-in-JS:**
- Полная мощь JavaScript в стилях — условия, циклы, переменные темы
- Совместное размещение: стили и компонент в одном файле
- Автоматический scoping — конфликты имён невозможны
- Типизированные props в styled components
- Удаление мёртвого кода: неиспользуемые компоненты = неиспользуемые стили

**Недостатки runtime CSS-in-JS:**
- **Стоимость runtime**: вставка стилей происходит в JavaScript на основном потоке — добавляет к TTI
- **Несовместимость с React Server Components**: runtime-вставка стилей требует браузерного окружения JS — в RSC его нет
- **Стоимость гидратации**: при SSR стили должны быть сериализованы и повторно вставлены на клиенте
- Больший JS-бандл

### Zero-runtime CSS-in-JS (vanilla-extract, StyleX, Linaria)

Zero-runtime-подходы переносят генерацию стилей на этап сборки:

```typescript
// vanilla-extract — styles.css.ts
import { style, styleVariants } from '@vanilla-extract/css';

export const card = style({
  background: 'white',
  borderRadius: '8px',
});

export const cardVariants = styleVariants({
  default: { border: 'none' },
  featured: { border: '2px solid #0066cc' },
});

export const title = style({
  fontSize: '1.25rem',
  fontWeight: 700,
});

// Component.tsx
import { card, cardVariants, title } from './styles.css';

function Card({ featured }: { featured?: boolean }) {
  return (
    <article className={`${card} ${featured ? cardVariants.featured : cardVariants.default}`}>
      <h2 className={title}>Заголовок</h2>
    </article>
  );
}
```

При сборке vanilla-extract генерирует настоящие `.css`-файлы с хешированными именами классов. Нулевая стоимость runtime — просто статические CSS-файлы.

**Компромисс**: нет по-настоящему динамических стилей в runtime. Варианты должны быть перечислены при сборке. Для реально динамических значений (цвета пользователя, произвольные пиксели) нужны инлайновые стили или CSS-кастомные свойства.

### CSS-кастомные свойства как мост для динамических стилей

```typescript
// Zero-runtime CSS-in-JS + динамические значения через кастомные свойства
// styles.css.ts (vanilla-extract)
import { style, createVar } from '@vanilla-extract/css';

export const accentColor = createVar();

export const card = style({
  vars: { [accentColor]: '#0066cc' }, // значение по умолчанию
  borderColor: accentColor,
});

// Component.tsx — динамическое значение через inline style на переменной
function Card({ color }: { color: string }) {
  return (
    <article
      className={card}
      style={{ [accentColor]: color }} // переопределить кастомное свойство
    >
```

Кастомное свойство задаётся инлайново (динамически, без генерации классов), остальные стили — в статическом CSS.

## Utility-first CSS (Tailwind)

Tailwind предоставляет большой набор однозадачных utility-классов, напрямую отображающихся в CSS-свойства:

```html
<!-- BEM-эквивалент: -->
<article class="card card--featured">
  <header class="card__header">
    <h2 class="card__title">Заголовок</h2>
  </header>
</article>

<!-- Tailwind-эквивалент: -->
<article class="bg-white rounded-lg border-2 border-blue-600 shadow-md">
  <header class="px-4 pt-4">
    <h2 class="text-xl font-bold text-gray-900">Заголовок</h2>
  </header>
</article>
```

### Как Tailwind работает на самом деле

Tailwind сканирует исходные файлы на имена классов и генерирует CSS только для реально используемых классов (tree-shaking). Результат — статический файл с однозначными классами:

```css
/* Сгенерировано Tailwind — только классы из ваших файлов */
.bg-white { background-color: rgb(255 255 255); }
.rounded-lg { border-radius: 0.5rem; }
.border-2 { border-width: 2px; }
.border-blue-600 { border-color: rgb(37 99 235); }
.text-xl { font-size: 1.25rem; line-height: 1.75rem; }
.font-bold { font-weight: 700; }
.px-4 { padding-left: 1rem; padding-right: 1rem; }
.pt-4 { padding-top: 1rem; }
```

Каждый класс имеет специфичность `(0, 1, 0)` и объявляет единственное свойство. Конфликты разрешаются порядком в источнике — побеждает класс, появляющийся позже в сгенерированном CSS.

### Преимущества Tailwind

**Нет решений об именовании**: сложнейшая часть CSS в масштабе — именование. Tailwind устраняет её — компоненты и иерархии классов называть не нужно.

**Совместное размещение**: стили находятся в HTML (или JSX). Для изменения стиля не нужно переключать файлы.

**Предсказуемая специфичность**: каждый класс — `(0, 1, 0)`. Войны специфичности невозможны.

**Согласованная дизайн-система**: шкала Tailwind (`text-sm`, `text-base`, `text-lg`) навязывает дизайн-систему. Произвольные значения (`text-[17px]`) существуют, но не поощряются.

**Производительность**: сгенерированный CSS крошечный (5–20 КБ типично для большого приложения, gzip) из-за purge неиспользуемых классов.

### Недостатки Tailwind

**Многословность HTML**: длинные списки классов на сложных компонентах трудно читать.

**Давление на компонентную абстракцию**: без именования нужны компоненты (React/Vue) для избегания дублирования списков классов. Чистый HTML + Tailwind становится громоздким.

**Трение при кастомизации**: нестандартные значения требуют расширения конфига или произвольных значений (`text-[17px]`, `bg-[#1a1a2e]`).

**Когнитивная нагрузка для новичков**: нужно знать Tailwind API (имена классов неочевидны — `py-4` vs `padding-block: 1rem`).

**Динамические стили**: имена классов Tailwind должны быть полными строками в источнике — конкатенация строк ломает сканер:

```javascript
// Неправильно — сканер Tailwind не найдёт 'bg-blue-600'
const color = 'blue';
<div className={`bg-${color}-600`}>  // не сработает

// Правильно — полные имена классов в источнике
const classMap = { blue: 'bg-blue-600', red: 'bg-red-600' };
<div className={classMap[color]}>
```

### Escape hatch `@apply`

Для повторяющихся комбинаций utility-классов, которым нужно имя, Tailwind предоставляет `@apply`:

```css
/* В вашем CSS — извлечь повторяющиеся паттерны в класс */
@layer components {
  .btn {
    @apply inline-flex items-center justify-center px-4 py-2 font-semibold rounded-md;
  }
  .btn-primary {
    @apply btn bg-blue-600 text-white hover:bg-blue-700;
  }
}
```

`@apply` спорен — он возвращает проблему именования, от которой Tailwind был призван избавить. Используйте редко, только для shared-паттернов.

## Сравнение — когда подходит каждый подход

### Масштаб и размер команды

| Подход | Малая команда / прототип | Средняя / продукт | Крупная / дизайн-система |
|---|---|---|---|
| Plain CSS + BEM | ✓ Отлично | ✓ Хорошо | ⚠ Нужна строгая дисциплина |
| CSS Modules | ✓ Хорошо | ✓ Отлично | ✓ Хорошо |
| CSS-in-JS (runtime) | ✓ Хорошо | ✓ Хорошо | ⚠ Проблемы производительности |
| CSS-in-JS (zero-runtime) | ⚠ Накладные расходы на настройку | ✓ Хорошо | ✓ Отлично |
| Tailwind | ✓ Отлично | ✓ Отлично | ⚠ Нужна компонентная система |

### Технические ограничения

**Используйте BEM когда:**
- Проект не привязан к фреймворку или использует несколько
- Стили должны работать без инструментов сборки
- Команда хорошо знает CSS, но не глубоко JavaScript

**Используйте CSS Modules когда:**
- Используете компонентный фреймворк (React, Vue, Svelte)
- Нужны преимущества scoping без отказа от "обычного" синтаксиса CSS
- Нужно делиться стилями между компонентами без сложного инструментария

**Используйте runtime CSS-in-JS когда:**
- Стили сильно зависят от runtime JS-состояния (переключение темы, пользовательская кастомизация)
- Нужна глубокая TypeScript-интеграция (prop-типизированные styled components)
- **Не** когда: используются React Server Components, критична производительность (TTI), SSR — ключевое требование

**Используйте zero-runtime CSS-in-JS (vanilla-extract, StyleX) когда:**
- Нужны типизированные стили без runtime-стоимости
- Создаёте дизайн-систему для нескольких фреймворков
- Важна производительность RSC или SSR

**Используйте Tailwind когда:**
- Быстрое прототипирование или стартап-среда
- Компонентный фреймворк абстрагирует списки классов
- Команда ценит конвенцию над конфигурацией
- Нужна встроенная дизайн-система без её проектирования

### "Правильный" ответ в 2025

Нет единственно верного ответа — но разумный дефолт для React/Next.js-приложения в production:

1. **Tailwind** для utility-стилизации (отступы, цвета, типографика) — конвенционально, без накладных расходов на именование
2. **CSS-кастомные свойства** для динамических/тематических значений
3. **CSS Modules** для сложных стилей компонентов, трудно выражаемых в utility
4. **`@layer`** для организации каскада между слоями

Гибридный подход использует каждый инструмент там, где он лучший. Чистый Tailwind для всего создаёт шум в HTML; чистые CSS Modules — накладные расходы на именование; чистый CSS-in-JS — runtime-стоимость.

## Типичные ошибки на интервью

**"Почему BEM использует единственные классы вместо селекторов-потомков?"**

Единственные классы имеют единообразную специфичность `(0, 1, 0)`. Селекторы-потомки (`.card .title`) имеют более высокую специфичность `(0, 2, 0)` и создают связанность между родителем и потомком в селекторе — при перемещении `.title` за пределы `.card` в DOM стиль ломается. С BEM-классом `.card__title` связь в имени, а не в иерархии. Переопределение тривиально — любой селектор выше `(0, 1, 0)` победит.

---

**"В чём разница между CSS Modules и CSS-in-JS?"**

CSS Modules: трансформация на этапе сборки, генерирующая уникальные имена классов из CSS-файлов. Сам CSS — стандартный, никакого JavaScript в runtime. CSS-in-JS (runtime): JavaScript генерирует CSS в runtime, вставляя теги `<style>`. Позволяет динамические стили. Runtime-стоимость, несовместимость с RSC. CSS-in-JS (zero-runtime): как CSS Modules, но с JavaScript/TypeScript-синтаксисом для авторинга — стили генерируются при сборке, нет runtime-стоимости.

---

**"Какова основная проблема производительности у runtime CSS-in-JS вроде Styled Components?"**

Две проблемы: (1) **размер JS-бандла** — определения стилей являются JavaScript, добавляя к бандлу. (2) **Runtime-вставка стилей** — на каждом рендере JavaScript вычисляет стили и вставляет/обновляет теги `<style>` на основном потоке. Это добавляет к Time to Interactive. При SSR стили должны быть сериализованы (обычно как тег `<style>` в HTML) и клиент должен согласовать свои сгенерированные стили с серверными, что добавляет к стоимости гидратации.

---

**"Какую проблему Tailwind решает, которую BEM не решает?"**

Проблему именования. С BEM всё равно нужно решать, как называть блок, какие у него элементы и модификаторы. Это значительная когнитивная нагрузка в масштабе. Tailwind устраняет именование полностью — utility-классы применяются напрямую. Кроме того, Tailwind навязывает ограничения дизайн-системы (предопределённые значения шкалы) и предотвращает рост CSS-файла — неиспользуемые utility удаляются.

---

**"Когда вы выбрали бы CSS Modules вместо Tailwind?"**

Для сложных стилей компонентов, трудно выражаемых как комбинации utility — сложные дизайны псевдоэлементов, сложные @keyframes анимации, глубоко условная стилевая логика, или стили, которые имеют больший смысл как связный блок, чем как 20 отдельных utility. Также: когда команда имеет сильную CSS-экспертизу и ценит явный авторинг стилей; или когда дизайн-система выражает стили через CSS-переменные, а не через маппинги utility-классов.
