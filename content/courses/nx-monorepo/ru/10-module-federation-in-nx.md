# Module Federation в Nx: host, remotes и serve

## Теория

### Что Nx добавляет поверх голого Module Federation

Собрать федерацию на голом webpack — это руками написать ModuleFederationPlugin-конфиги обеих сторон, согласовать shared-списки, порты, урлы и оркестрацию dev-серверов. Nx оборачивает всё это в три вещи:

- **Генераторы** `@nx/react:host` и `@nx/react:remote`: создают приложения сразу с правильной проводкой — bootstrap-паттерном, конфигами, роутингом и записями друг о друге.
- **`module-federation.config.ts`** — декларативный слой над бандлером. Вы описываете *что*: имя, remotes, exposes. Плагин Nx разворачивает это в полный конфиг ModuleFederationPlugin, включая дефолтный shared: все зависимости из package.json шарятся автоматически, react — как singleton. Тонкая настройка — глава 11.
- **Оркестрация serve**: `nx serve shell` сам поднимает remotes — центральная тема ниже.

> **Версии.** Генераторы предлагают `--bundler=rspack` или `webpack`, конфиги идентичны по смыслу. Rspack — это Rust-реализация webpack-API, в разы быстрее, и дефолт в свежих Nx.

> **Под капотом.** Новые версии используют Module Federation 2.0 — коротко MF 2.0 — через `@module-federation/enhanced` и пакет `@nx/module-federation`. В старых репах стоит `withModuleFederation` из `@nx/react/module-federation` поверх webpack. Файлы выглядят иначе, роли те же.

### module-federation.config.ts: две стороны контракта

```ts
// apps/shell/module-federation.config.ts — HOST
const config = {
  name: 'shell',
  remotes: ['catalog', 'checkout'],   // кого умею загружать
};

// apps/catalog/module-federation.config.ts — REMOTE
const config = {
  name: 'catalog',
  exposes: { './Module': './src/remote-entry.ts' },  // что отдаю наружу
};
```

`remotes: ['catalog']` — это **static remote** в форме "имя без адреса". На dev-е Nx сам знает порт каталога. На проде адрес подставляется при сборке: кортежем `['catalog', 'https://cdn.../']` или через переменную окружения.

Альтернатива — **dynamic remotes**. Адреса не зашиваются в бандл, а читаются в рантайме из `module-federation.manifest.json`, и host генерируется с флагом `--dynamic`. Тогда переехавшая сеть доставки контента (CDN) или канареечный remote — это правка манифеста, без пересборки host.

Правило: начинайте со static, потому что так проще и ошибки видны раньше. Переходите на dynamic, когда адреса remotes реально меняются независимо от релизов host.

### Bootstrap-паттерн: зачем main.ts стал двухфайловым

Генератор создаёт вместо привычного main.tsx пару:

```ts
// apps/shell/src/main.ts — всё, что в нём есть:
import('./bootstrap');

// apps/shell/src/bootstrap.tsx — настоящий вход: createRoot().render(<App/>)
```

Это не украшение, а **async boundary** из главы 09. Динамический `import()` даёт бандлеру точку, где он может остановиться. Там он проводит shared negotiation — init контейнеров, выбор версий react — и только потом исполняет код, который эти shared потребляет.

Склейте эти файлы в один — получите классическую ошибку "Shared module is not available for eager consumption" (воспроизведём в главе 11).

### Что происходит при nx serve shell

Ключевой практический вопрос главы. Поднимать три полноценных dev-сервера с watch и горячей заменой модулей (HMR) — дорого. На реальной федерации из 10 remotes это гигабайты памяти и минуты старта. Поэтому Nx по умолчанию делает иначе:

```
                  nx serve shell

        ┌────────────────────────────────┐
        │ shell — полноценный dev-server │
        │ :4200 · watch · HMR            │
        └────────────────────────────────┘
        ждёт remotes на портах из конфига
                        ▼
┌─────────────────────┐    ┌─────────────────────┐
│ catalog :4201       │    │ checkout :4202      │
│ статика: собран     │    │ статика: собран     │
│ один раз, без watch │    │ один раз, без watch │
└─────────────────────┘    └─────────────────────┘

       nx serve shell --devRemotes=catalog
         → catalog тоже dev-server с HMR
```

Remotes собираются **один раз** — со всеми выгодами кеша из главы 04, где "не менялись" означает "мгновенно", — и раздаются как статика на своих портах. В watch-режиме — только host. Следствие, на котором спотыкается каждый новичок: **вы правите код каталога при запущенном `nx serve shell` — и ничего не происходит**. Это не баг: каталог задеплоен как статика.

Работаете над каталогом — скажите об этом: `nx serve shell --devRemotes=catalog`. Каталог поднимется полноценным dev-сервером с HMR, а checkout останется статикой. Оркестрацию таких долгоживущих задач в новых версиях обеспечивают continuous tasks из главы 03.

### Роутинг: host владеет маршрутами

Решение из главы 09 становится кодом: react-router живёт в host, remote-модули подключаются лениво:

```tsx
const CatalogPage = React.lazy(() => import('catalog/Module'));
```

`'catalog/Module'` — не путь в файловой системе и не алиас tsconfig. Это федеративный запрос: "у контейнера catalog возьми exposes './Module'". TypeScript о таком модуле ничего не знает. Его типизирует файл `remotes.d.ts` (`declare module 'catalog/Module'`), сгенерированный Nx.

Помните из главы 09: это декларация, а не гарантия. Реальный контракт проверяется только в рантайме, а MF 2.0 умеет генерировать типы из remote (глава 11).

## В рабочем монорепо

- `cat apps/*/module-federation.config.*` — карта федерации за минуту: кто host (remotes), кто remote (exposes), какая гранулярность экспонирования.
- `nx show project shell --web` → target serve: какой executor/команда, какие порты, есть ли `devRemotes` в опциях по умолчанию.
- Как прод узнаёт адреса remotes: grep по `manifest` (dynamic) и по кортежам/env в module-federation.config (static). Это ответ на "что нужно передеплоить, если каталог переехал на другой CDN".
- Ваша команда владеет одним remote? Локальный запуск — `nx serve shell --devRemotes=<ваш>`: host и чужие remotes статикой, ваш — с HMR. Порты заняты после аварийного завершения — `lsof -i :4200-4210` и почистить.
- `cat apps/shell/src/remotes.d.ts` плюс поиск сгенерированных `@mf-types`. Так видно, как в репе типизированы федеративные импорты: голый declare module или типы из MF 2.0.

## Что добавляем в проект

Кульминация курса: mini-shop становится федерацией. Vite-shell уходит — весь смысл тонких приложений в том, что их не жалко пересоздать. На его месте host и два remote на rspack, а страницы остаются в либах и просто переподключаются.

## Практическое задание

**Вход:** workspace после главы 08 (+ прочитанная глава 09). Весь интерфейс живёт в либах: catalog-feature (CatalogPage), checkout-feature-cart (CartPage), shared-ui, shared-util.

**Задача:**

1. Удалить приложение shell штатным генератором (`@nx/workspace:remove`). Перед этим выписать, что мы теряем. И убедиться, что почти ничего: баннер из главы 04 и target deploy переедут в новый shell.
2. Сгенерировать федерацию: host `shell` c remotes `catalog` и `checkout` (одной командой генератора host), bundler — rspack, тесты vitest, без сквозных (e2e) тестов.
3. Подключить контент из либ: `./Module` каталога реэкспортирует `CatalogPage` из `@mini-shop/catalog-feature`; checkout — `CartPage` из `@mini-shop/checkout-feature-cart`. Приложения-remotes должны остаться тонкими (импорт + экспорт).
4. Роутинг в host: `/` (заглушка-витрина), `/catalog`, `/checkout`; ленивые импорты + Suspense fallback + error boundary на случай недоступного remote (решение из главы 09).
5. Изучить serve: запустить `nx serve shell`, зафиксировать порты и процессы. Поправить текст в CatalogPage и убедиться, что **без** `--devRemotes` изменение не подхватывается. Затем перезапустить с `--devRemotes=catalog` и убедиться, что подхватывается.
6. Привести хозяйство в порядок: теги новым проектам (`scope:catalog,type:app` и так далее), `typecheck`-таргеты и deploy-таргет из главы 08 на оба remote. Тогда `nx deploy catalog` публикует независимый артефакт — ради этого всё и затевалось.

**Edge cases на подумать:**

- Что будет, если удалить `import('./bootstrap')` и вернуть обычный main.tsx?
- `nx build shell` — попадут ли туда бандлы каталога? Что тогда деплоится при "деплое shell"?
- Как shell узнает прод-адреса remotes, если на CDN они живут на разных доменах?

## Разбор решения

Шаги 1–2 — пересоздание:

```bash
npx nx g @nx/workspace:remove shell
npx nx g @nx/react:host shell --directory=apps/shell \
  --remotes=catalog,checkout --bundler=rspack \
  --style=css --unitTestRunner=vitest --e2eTestRunner=none
```

Одна команда создала три приложения и всю проводку. Существенное из сгенерированного:

```
apps/
├── shell/
│   ├── module-federation.config.ts  # name + список remotes
│   ├── rspack.config.ts             # оборачивает MF-конфиг
│   └── src/
│       ├── main.ts                  # import('./bootstrap')
│       ├── bootstrap.tsx            # настоящий вход
│       ├── remotes.d.ts             # объявляет 'catalog/Module'
│       └── app/app.tsx              # роуты с React.lazy
├── catalog/
│   ├── module-federation.config.ts  # name + exposes './Module'
│   └── src/remote-entry.ts          # уедет наружу как './Module'
└── checkout/                        # аналогично
```

Шаг 3 — remotes остаются тонкими (главы 01 и 06 окупаются здесь):

```ts
// apps/catalog/src/remote-entry.ts
export { CatalogPage as default } from '@mini-shop/catalog-feature';

// apps/checkout/src/remote-entry.ts
export { CartPage as default } from '@mini-shop/checkout-feature-cart';
```

Шаг 4 — host владеет маршрутами и деградацией:

```tsx
// apps/shell/src/app/app.tsx
import { lazy, Suspense } from 'react';
import { Link, Route, Routes } from 'react-router-dom';
import { RemoteBoundary } from './remote-boundary';

const CatalogPage = lazy(() => import('catalog/Module'));
const CheckoutPage = lazy(() => import('checkout/Module'));

export function App() {
  return (
    <>
      <nav>
        <Link to="/">mini-shop</Link> · <Link to="/catalog">Catalog</Link> ·{' '}
        <Link to="/checkout">Checkout</Link>
      </nav>
      <Suspense fallback={<p>Загрузка…</p>}>
        <Routes>
          <Route path="/" element={<h2>Витрина</h2>} />
          <Route
            path="/catalog"
            element={
              <RemoteBoundary fallback={<p>Каталог временно недоступен</p>}>
                <CatalogPage />
              </RemoteBoundary>
            }
          />
          <Route
            path="/checkout"
            element={
              <RemoteBoundary fallback={<p>Оформление временно недоступно</p>}>
                <CheckoutPage />
              </RemoteBoundary>
            }
          />
        </Routes>
      </Suspense>
    </>
  );
}

export default App;
```

`RemoteBoundary` — обычный класс-ErrorBoundary с fallback-пропом. Падение загрузки remote — шаг 2 схемы из главы 09 — деградирует до сообщения на одном роуте, а не роняет приложение.

Шаг 5 — serve и его логика:

```bash
npx nx serve shell
# > catalog:  собран и раздаётся статикой на :4201
# > checkout: собран и раздаётся статикой на :4202
# > shell:    dev-server на :4200 (watch + HMR)
```

Правка CatalogPage при таком запуске не видна: каталог "задеплоен" статикой. И это честная модель прода — чужие remotes вы тоже не пересобираете. Работа над каталогом:

```bash
npx nx serve shell --devRemotes=catalog
```

Шаг 6 — deploy remote-а: `nx deploy catalog` → build каталога (или кеш) → `.deploy/catalog` с его чанками и remoteEntry.json/js. Вот он, независимый деплой из главы 09, в миниатюре: артефакт каталога публикуется отдельно от shell.

Ответы на edge cases:

- Без `import('./bootstrap')` бандлер теряет async boundary. Код, потребляющий shared react, оказывается в синхронном стартовом чанке раньше, чем negotiation успевает отработать. Результат — "Shared module is not available for eager consumption"; подробный разбор в главе 11.
- `nx build shell` собирает **только shell**: в dist/apps/shell бандлов каталога нет — там лишь адреса, по которым host будет их искать. "Деплой shell" публикует host; remotes деплоятся своими пайплайнами — в этом и был смысл.
- Прод-адреса зависят от режима. Для static remotes это кортеж `['catalog', 'https://cdn.mini-shop.example/catalog/']` в module-federation.config прод-сборки или env-подстановка. Для по-настоящему независимой инфраструктуры это dynamic remotes с манифестом, который правится без пересборки host.

## Проверь себя

1. Перечисли, что генератор `@nx/react:host` создаёт помимо самого React-приложения, и зачем каждая часть.
2. Почему при `nx serve shell` remotes поднимаются статикой, а не dev-серверами? Какую проблему это решает и какое неудобство создаёт?
3. В чём разница между static и dynamic remotes? Приведи сценарий, где dynamic оправдан.
4. `import('catalog/Module')` — как этот спецификатор разрешается на этапе сборки host и в рантайме? Откуда TypeScript знает такой модуль?
5. Наши remote-приложения — по три строчки: реэкспорт страницы из либы. Какие выгоды архитектуры прошлых глав здесь сработали?

<details>
<summary>Ответы</summary>

1. Он создаёт `module-federation.config.ts` — декларацию имени и remotes, которую плагин разворачивает в полный конфиг бандлера. Создаёт bootstrap-пару `main.ts` → `bootstrap.tsx`, то есть async boundary для shared negotiation. Создаёт `remotes.d.ts` с TS-декларациями федеративных модулей. Создаёт каркас роутинга с `React.lazy` по remote-ам и порт serve каждому приложению. И создаёт сами приложения remotes с `remote-entry.ts` и exposes.
2. N полноценных dev-серверов — это память, минуты старта и watch над кодом, который вы не трогаете. Статика решает масштаб: remotes собираются один раз (обычно из кеша) и просто раздаются, а watch остаётся только у host. Неудобство: правки в remote не подхватываются, пока его не объявишь `--devRemotes`. Отсюда классическое недоумение "правлю — не меняется".
3. Static означает, что список remotes и их адреса фиксируются при сборке host: на dev — порты, на прод — урлы кортежем или через env. Смена адреса = пересборка host. Dynamic означает, что host читает адреса в рантайме из манифеста, и сборка host от адресов не зависит. Dynamic оправдан, когда адреса remotes меняются независимо от релизов host. Примеры: канарейки и постепенные выкатки remote-ов, разные окружения с разными сетями доставки контента, миграция доменов без релиза host.
4. На этапе сборки бандлер видит в конфиге, что `catalog` — федеративный remote. Резолвить модуль в файлы он не пытается: на его месте остаётся runtime-запрос. В рантайме это шаги из главы 09: загрузить remoteEntry каталога, `init` с общим shared scope, `container.get('./Module')`, догрузить чанки. TypeScript знает модуль только из `remotes.d.ts` (или сгенерированных MF 2.0 типов) — это обещание разработчика, рантайм его не проверяет.
5. Тонкие приложения (глава 01): весь интерфейс в либах, поэтому пересоздание shell стоило почти ничего, а remotes свелись к реэкспорту. Границы и scope (глава 06): catalog-фича не тянет checkout, значит remote каталога не увозит чужой код. Кеш (глава 04): статичные remotes при serve пересобираются мгновенно, если не менялись. Deploy-executor (глава 08) лёг на remotes без единой правки — контекст вместо хардкода.

</details>

## Частая ошибка

Первый день с федерацией почти всегда выглядит так: разработчик запускает `nx serve shell`, открывает каталог, правит `catalog-page.tsx` — ничего. Сохраняет ещё раз, перезагружает страницу, грешит на кеш браузера, на Nx, на rspack. А это дизайн: при обычном serve каталог — статический артефакт, как в проде.

Рефлекс, который надо выработать: **запуская dev-режим, объявляй, над чем работаешь** — `--devRemotes=catalog`. Полезно закрепить это в `README` или в target-е (`serve-dev` с преднастроенными devRemotes), чтобы новые люди не проходили этот квест заново.

Вторая ошибка — тащить код в приложение-remote. Кажется естественным: "страница каталога — значит, пишу в apps/catalog/src". Но код, запертый в приложении, невозможно ни переиспользовать, ни покрыть boundary-правилами (глава 06). Сам remote при этом перестаёт быть тонким переходником и обрастает логикой. Однажды эту логику захочется дёрнуть из другого места, и её придётся выковыривать.

Правило не меняется от появления федерации: **весь смысловой код — в либах; приложение (хоть host, хоть remote) — конфигурация, роутинг и реэкспорт**. Наши remote-entry по три строки — это не упрощение учебника, а целевое состояние.
