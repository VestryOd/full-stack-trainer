# Архитектура библиотек и module boundaries

## Теория

Это глава про то, **почему** libs в рабочем Nx-проекте выглядят именно так: десятки мелких либ со странными именами вроде `catalog-data-access` вместо пары "утилок". За этим стоит не вкусовщина, а две оси классификации и линтер, который их защищает.

### Ось первая: тип либы

Nx-сообщество за годы сошлось на четырёх типах:

```
┌──────────────────┬───────────────────────────────────┬──────────────────────────────────┐
│ тип либы         │ может зависеть от                 │ что внутри                       │
├──────────────────┼───────────────────────────────────┼──────────────────────────────────┤
│ type:feature     │ feature · ui · data-access · util │ страницы, smart-компоненты, флоу │
├──────────────────┼───────────────────────────────────┼──────────────────────────────────┤
│ type:ui          │ ui · util                         │ глупые компоненты, без данных    │
├──────────────────┼───────────────────────────────────┼──────────────────────────────────┤
│ type:data-access │ data-access · util                │ API-клиенты, стейт, сервисы      │
├──────────────────┼───────────────────────────────────┼──────────────────────────────────┤
│ type:util        │ util                              │ чистые функции, типы, хелперы    │
└──────────────────┴───────────────────────────────────┴──────────────────────────────────┘
```

Читается матрица сверху вниз как "от умного к глупому": feature знает всё, util не знает никого. Ключевые запреты — снизу вверх: **ui не ходит за данными** (иначе компонент нельзя переиспользовать с другим источником), **data-access не знает про рендеринг** (иначе его нельзя дёрнуть из Node-скрипта или другого фреймворка), **util чист** (иначе он не util). Стрелка вниз по матрице — можно; вверх — нарушение.

### Ось вторая: scope (домен)

Тип отвечает "что это", scope — "чьё это": `catalog`, `checkout`, `shared`. В файловой системе scope — это grouping folder: `libs/<scope>/<type>`; сама папка scope проектом не является — это просто способ группировки:

```
libs/
├── catalog/
│   ├── feature/         # catalog-feature: страница каталога
│   └── data-access/     # catalog-data-access: продукты, API
├── checkout/            # появится в главе 10
└── shared/
    ├── ui/              # shared-ui: Button и прочие кирпичи
    └── util/            # shared-util: форматирование, типы
```

Правило по scope одно, но важнейшее: **домены не лезут друг к другу напрямую; общее живёт в shared**. `catalog` может зависеть от `catalog` и `shared`; от `checkout` — нет. Именно это правило делает будущие микрофронтенды (глава 10) реально независимыми: если catalog не импортирует ничего из checkout, их можно собирать и деплоить порознь.

### Теги: машиночитаемая версия обеих осей

Классификация бесполезна, пока она живёт в головах и вики. В Nx она записывается в `tags` в project.json — строки без встроенной семантики (конвенция `ось:значение`):

```json
{ "name": "catalog-feature", "tags": ["scope:catalog", "type:feature"] }
```

Теги мы уже видели пустыми в главе 01 — генератор создаёт `"tags": []` именно под это. Заполнять их лучше сразу при генерации (`--tags=scope:catalog,type:feature`), а в главе 07 наш кастомный генератор будет делать это автоматически.

### @nx/enforce-module-boundaries: линтер поверх графа

Правило ESLint из пакета `@nx/eslint-plugin`, которое превращает конвенции в ошибки сборки. Механика: линтер видит импорт → резолвит его в проект-цель через project graph (тот же, что в главе 02) → сверяет теги проекта-источника и проекта-цели с `depConstraints`. Конфиг живёт в корневом eslint-конфиге:

```js
'@nx/enforce-module-boundaries': ['error', {
  depConstraints: [
    { sourceTag: 'type:feature', onlyDependOnLibsWithTags: ['type:feature', 'type:ui', 'type:data-access', 'type:util'] },
    { sourceTag: 'type:ui', onlyDependOnLibsWithTags: ['type:ui', 'type:util'] },
    // ...
  ],
}],
```

Ограничения комбинируются по принципу И: импорт должен пройти **каждое** правило, чей sourceTag есть у источника. `catalog-feature` (scope:catalog + type:feature) может импортировать `shared-ui`, потому что проходит и по оси scope (shared разрешён для catalog), и по оси type (ui разрешён для feature). Бонусом это же правило запрещает relative-импорты через границы проектов и deep-imports мимо index.ts — те самые дырки из главы 02.

Важно понимать статус: свежесгенерированный конфиг содержит заглушку `{ sourceTag: '*', onlyDependOnLibsWithTags: ['*'] }` — правило формально включено, но **разрешает всё**. Boundaries в репе есть только тогда, когда кто-то заменил заглушку на реальные constraints и lint гоняется в CI.

### Buildable и publishable: почему НЕ всё

По умолчанию либа non-buildable (`--bundler=none`, как наша shared-ui): у неё нет своего build, потребитель компилирует её исходники сам через алиас. **Buildable** либа имеет собственный target `build` и артефакт в dist — она нужна ровно в двух случаях: инкрементальная сборка гигантской репы (собирать либы отдельно и переиспользовать из кеша) и техническая необходимость (глава 12: у Node-приложения свой компилятор, которому нужен готовый артефакт соседа — увидим на практике). **Publishable** — buildable + оформление npm-пакета (`--publishable --importPath=...`): только для кода, который реально публикуется наружу.

Рефлекс "сделаю все либы buildable, как npm-пакеты" — дорогая ошибка: каждая либа обрастает конфигом сборки, пайплайн — оркестрацией `^build`, холодный старт репы замедляется в разы, а выгоды при обычных размерах нет: vite и так прекрасно собирает приложение из исходников либ. Правило: **non-buildable, пока не доказана необходимость обратного**.

## В рабочем монорепо

- `grep -h '"tags"' $(find libs apps -name project.json -not -path '*/node_modules/*') | sort | uniq -c` — вся таксономия репы одной командой: какие оси приняты, есть ли проекты без тегов.
- Найдите `enforce-module-boundaries` в корневом eslint-конфиге: если там заглушка `'*' → '*'` — boundaries в репе декоративные, полагаться на слоистость нельзя.
- `nx graph` → сгруппируйте взглядом по папкам scope: у здоровой репы рёбра между доменами идут только через shared; прямое ребро catalog → checkout — находка для ревью.
- Проверьте, что lint с этим правилом реально гоняется в CI (grep по CI-конфигу): правило, которое не запускается, не существует.
- `for p in $(ls libs/*/*/project.json); do grep -l '"build"' $p; done` + `nx show project <либа>` — какие либы buildable; у каждой должно быть объяснение (инкрементальность? публикация? техническая необходимость?).

## Что добавляем в проект

Рефакторим mini-shop из "приложение + одна либа" в слоистую структуру: `catalog-feature` (страница каталога), `catalog-data-access` (продукты, пока на моках — реальный API в главе 12), `shared-util` (форматирование цены). Вешаем теги, включаем боевые depConstraints — и ломаем правило, чтобы увидеть ошибку.

## Практическое задание

**Вход:** workspace после главы 05.

**Задача:**

1. Сгенерировать три либы (все non-buildable, vitest, теги — сразу флагом `--tags`):
   - `shared-util` в `libs/shared/util` (`scope:shared`, `type:util`) — обычная TS-либа (`@nx/js:lib`), функция `formatPrice(cents: number): string`;
   - `catalog-data-access` в `libs/catalog/data-access` (`scope:catalog`, `type:data-access`) — тип `Product` и `getProducts(): Promise<Product[]>` на моках;
   - `catalog-feature` в `libs/catalog/feature` (`scope:catalog`, `type:feature`) — компонент `CatalogPage`: грузит продукты, рендерит карточки с `Button` из shared-ui и ценой через `formatPrice`.
2. Проставить теги существующим проектам: `shell` (`scope:shell`, `type:app`), `shared-ui` (`scope:shared`, `type:ui`).
3. Заменить в корневом eslint-конфиге заглушку `'*' → '*'` на матрицу: обе оси, включая `type:app → type:feature|ui|util` (приложение не должно ходить в data-access напрямую — данные приносит feature).
4. Подключить `CatalogPage` в shell вместо прежнего содержимого App.
5. Сломать правило дважды и прочитать обе ошибки: импорт `CatalogPage` внутри `shared-ui` (нарушение по type) и импорт из `catalog-data-access` внутри `shell` (нарушение по вашей матрице для app). Откатить.

**Требования:** `nx run-many -t lint` зелёный после рефакторинга; `nx graph` показывает слои: shell → catalog-feature → {catalog-data-access, shared-ui}; shared-util внизу.

**Edge cases на подумать:**

- Команда вводит boundaries в репу с сотней существующих нарушений. Включать error сразу?
- Куда класть код, нужный и catalog, и checkout, но состоящий из React-компонентов с данными?
- Почему `scope:shared → scope:shared` (shared не видит доменов) — самое важное правило матрицы?

## Разбор решения

Шаг 1 — генерация (обратите внимание: теги задаются при создании, а не "потом когда-нибудь"):

```bash
npx nx g @nx/js:lib shared-util --directory=libs/shared/util \
  --bundler=none --unitTestRunner=vitest --linter=eslint \
  --importPath=@mini-shop/shared-util --tags=scope:shared,type:util

npx nx g @nx/js:lib catalog-data-access --directory=libs/catalog/data-access \
  --bundler=none --unitTestRunner=vitest --linter=eslint \
  --importPath=@mini-shop/catalog-data-access --tags=scope:catalog,type:data-access

npx nx g @nx/react:lib catalog-feature --directory=libs/catalog/feature \
  --bundler=none --unitTestRunner=vitest --linter=eslint \
  --importPath=@mini-shop/catalog-feature --tags=scope:catalog,type:feature
```

Код по слоям (каждая либа реэкспортирует публичное через свой index.ts):

```ts
// libs/shared/util/src/lib/format-price.ts
export function formatPrice(cents: number, currency = 'USD'): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(cents / 100);
}
```

```ts
// libs/catalog/data-access/src/lib/products.ts
export interface Product {
  id: string;
  title: string;
  priceCents: number;
}

const MOCK_PRODUCTS: Product[] = [
  { id: 'p1', title: 'Mechanical keyboard', priceCents: 12900 },
  { id: 'p2', title: 'USB-C dock', priceCents: 8900 },
  { id: 'p3', title: '4K monitor', priceCents: 41900 },
];

// Контракт уже асинхронный: в главе 12 моки заменит реальный HTTP-клиент,
// и ни один потребитель не изменится.
export async function getProducts(): Promise<Product[]> {
  return MOCK_PRODUCTS;
}
```

```tsx
// libs/catalog/feature/src/lib/catalog-page.tsx
import { useEffect, useState } from 'react';
import { Button } from '@mini-shop/shared-ui';
import { formatPrice } from '@mini-shop/shared-util';
import { getProducts, type Product } from '@mini-shop/catalog-data-access';

export function CatalogPage() {
  const [products, setProducts] = useState<Product[]>([]);

  useEffect(() => {
    getProducts().then(setProducts);
  }, []);

  return (
    <section>
      <h2>Catalog</h2>
      {products.map((p) => (
        <article key={p.id}>
          <h3>{p.title}</h3>
          <span>{formatPrice(p.priceCents)}</span>
          <Button onClick={() => console.log('add', p.id)}>Add to cart</Button>
        </article>
      ))}
    </section>
  );
}
```

Шаги 2–3 — теги и матрица. В project.json shell и shared-ui дописываются `tags`, а в корневом eslint-конфиге заглушка заменяется:

```js
// eslint.config.mjs (фрагмент правила)
'@nx/enforce-module-boundaries': ['error', {
  enforceBuildableLibDependency: true,
  allow: [],
  depConstraints: [
    // ось scope: домены изолированы, общее — в shared
    { sourceTag: 'scope:catalog', onlyDependOnLibsWithTags: ['scope:catalog', 'scope:shared'] },
    { sourceTag: 'scope:shared', onlyDependOnLibsWithTags: ['scope:shared'] },
    { sourceTag: 'scope:shell', onlyDependOnLibsWithTags: ['scope:catalog', 'scope:shared'] },
    // ось type: от умного к глупому
    { sourceTag: 'type:app', onlyDependOnLibsWithTags: ['type:feature', 'type:ui', 'type:util'] },
    { sourceTag: 'type:feature', onlyDependOnLibsWithTags: ['type:feature', 'type:ui', 'type:data-access', 'type:util'] },
    { sourceTag: 'type:ui', onlyDependOnLibsWithTags: ['type:ui', 'type:util'] },
    { sourceTag: 'type:data-access', onlyDependOnLibsWithTags: ['type:data-access', 'type:util'] },
    { sourceTag: 'type:util', onlyDependOnLibsWithTags: ['type:util'] },
  ],
}],
```

Ключевые решения:

- `type:app` не имеет права на data-access: приложение — тонкая обёртка (глава 01), данные ему приносит feature. Если завтра захочется "быстренько дёрнуть API из App" — линтер напомнит, где этому место.
- `scope:shell` видит catalog (подключает страницы), но сам никому не виден — на app нельзя ссылаться в принципе (у либ нет тега scope:shell в onlyDependOn).
- Обе оси проверяются одновременно: катим импорт через scope-правило И через type-правило.

Шаг 5 — ломаем. Импорт `catalog-feature` внутри shared-ui:

```bash
npx nx lint shared-ui
# error  A project tagged with "type:ui" can only depend on libs
#        tagged with "type:ui", "type:util"   @nx/enforce-module-boundaries
```

Импорт `catalog-data-access` в shell даст симметричную ошибку для `type:app`. Текст ошибки называет теги, а не имена проектов, — правило масштабируется на любые будущие либы без единой правки конфига.

Ответы на edge cases:

- В репе с сотней нарушений включать error сразу — заблокировать всем работу. Рабочий паттерн: включить как `warn`, выписать нарушения в бэклог, гасить пачками, переключить в `error` по достижении нуля. Альтернатива для точечных легаси-исключений — поле `allow` (белый список), но каждый элемент в нём должен иметь тикет на выпил.
- Компоненты с данными, нужные обоим доменам, — это `shared/feature` (тип feature, scope shared): матрица это разрешает (shared-feature зависит от shared-data-access). Если такого кода становится много — возможно, "общий" домен на самом деле полноценный третий scope.
- `scope:shared → scope:shared` гарантирует, что shared не знает о доменах: иначе через shared-либу образуется скрытый мост catalog ↔ checkout, и независимость доменов (а с ней и независимый деплой микрофронтендов) закончится, формально не нарушив ни одного другого правила.

## Проверь себя

1. Почему ui-либе запрещено зависеть от data-access? Приведи конкретный сценарий, который ломается при нарушении.
2. Опиши механику enforce-module-boundaries: откуда линтер знает, какому проекту принадлежит импортируемый модуль и какие у него теги?
3. Правил в depConstraints два массива — по scope и по type. Как они комбинируются для конкретного импорта и почему двух осей обычно достаточно?
4. Чем non-buildable либа отличается от buildable на уровне того, что происходит при `nx build shell`? Назови ситуации, когда buildable оправдана.
5. В репе есть теги и боевой depConstraints, но нарушения всё равно просачиваются в main. Какое звено, скорее всего, отсутствует?

<details>
<summary>Ответы</summary>

1. ui-компонент, который сам ходит за данными, нельзя переиспользовать: карточка товара, дёргающая `getProducts()` изнутри, жёстко привязана к источнику данных каталога — её не вставишь в checkout со списком уже купленного и не отрендеришь в сторибуке без моков сети. Зависимость ui → util-only гарантирует: компонент получает всё через props, а "откуда данные" решает feature-слой. Бонус: тесты ui-либы не требуют ни моков API, ни провайдеров стейта.
2. Линтер использует project graph: импорт-спецификатор резолвится через paths/workspaces в файл, файл принадлежит какому-то projectRoot — это проект-цель; его project.json содержит tags. Дальше механическая сверка: для каждого правила, чей sourceTag есть у проекта-источника, проверяется, что теги цели входят в onlyDependOnLibsWithTags. Не входят — ошибка линта с перечислением тегов.
3. По принципу И: импорт легален, только если проходит каждое применимое правило. `catalog-feature → shared-ui`: scope-правило (catalog может shared — ок) И type-правило (feature может ui — ок). Достаточно двух осей потому, что они ортогональны и отвечают на два независимых вопроса: "чьё" (владение, независимость деплоя) и "что" (слой, направление зависимостей). Третья ось (например, platform:web/node) добавляется тем же механизмом, когда появляется третий независимый вопрос.
4. Non-buildable: у либы нет задачи build вообще; vite, собирая shell, компилирует её исходники напрямую через алиас — в task graph одна сборка. Buildable: у либы свой build с артефактом в dist, `^build` выстраивает порядок, потребитель линкуется с артефактом. Оправдана при инкрементальной сборке очень крупной репы (переиспользование готовых артефактов либ из кеша), при публикации наружу (publishable) и при технической необходимости готового артефакта (глава 12).
5. Запуск в CI. Правило существует, только когда выполняется: если `nx affected -t lint` не входит в обязательные проверки PR (или lint позволено падать), boundaries остаются документацией. Проверить просто: найти в CI-конфиге lint и убедиться, что он блокирует мерж.

</details>

## Частая ошибка

Разработчик из single-app мира заводит одну либу `shared/common` — "ну а куда ещё класть общее?" — и она начинает пухнуть: сегодня туда падает форматтер, завтра React-хук с запросом к API, послезавтра константы двух несвязанных доменов. Через полгода от неё зависит вся репа, любая правка в ней делает affected ≈ всё (глава 05), а распутывание превращается в квартальный проект. Классификация type/scope — это прививка именно от этого: у каждой вещи есть ровно одно правильное место, и "не знаю куда — значит в common" перестаёт быть вариантом. Если затрудняетесь выбрать тип для куска кода — это обычно значит, что кусок надо разрезать.

Вторая ошибка тише и коварнее: теги проставлены, правило в конфиге есть — но там заглушка `'*' → '*'` из генератора, или lint не блокирует мерж в CI. Возникает **иллюзия границ**: команда верит в слоистость, произносит её на собеседованиях, а граф тем временем зарастает перекрёстными импортами — ведь ни одна машина их не останавливает. Первое, что стоит сделать после этой главы в рабочей репе, — открыть корневой eslint-конфиг и честно ответить: наши boundaries — правило или декорация?
