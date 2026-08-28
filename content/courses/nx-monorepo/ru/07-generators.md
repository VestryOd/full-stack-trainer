# Генераторы: скаффолдинг как код

## Теория

### Генератор — функция над виртуальной файловой системой

Мы пользуемся генераторами с главы 01, пора разобрать механику. Генератор — это функция вида `(tree, options) => void`, где **Tree** — виртуальная файловая система: чтение идёт с диска, но каждая запись (`tree.write`, `generateFiles`) копится в памяти. Только когда генератор отработал целиком, Nx делает flush изменений на диск:

```
┌───────────────────────────────────────────────────┐
│ nx g @mini-shop/workspace-plugin:feature-lib cart │
└───────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│ schema.json: валидация опций,                     │
│ x-prompt дособирает недостающие                   │
└───────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│ implementation(tree, options):                    │
│ все изменения — в виртуальной ФС (Tree)           │
└───────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│ --dry-run: напечатать diff Tree и выйти,          │
│ диск не тронут                                    │
└───────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│ без dry-run: flush Tree на диск,                  │
│ форматирование, установка пакетов                 │
└───────────────────────────────────────────────────┘
```

Из этой архитектуры бесплатно следуют две вещи. Во-первых, `--dry-run` не "эмулирует": он выполняет **тот же код** и печатает diff виртуальной файловой системы, просто без flush. Расхождение между dry-run и реальным запуском невозможно по построению. Во-вторых, генераторы тестируются юнитами без диска: создали Tree в памяти, прогнали функцию, проверили содержимое.

На этой же механике работает `nx migrate` (глава 13): миграции — те же генераторы, только их пишет команда Nx, а запускают они кодмоды над вашей репой при обновлении версий.

### Встроенные генераторы: schema, опции, дефолты

Синтаксис вызова — `nx g <пакет>:<имя>`. Что умеет конкретный генератор, описано в его **schema.json**. Там перечислены типы опций, обязательность, дефолты и `x-prompt` — вопрос, который зададут интерактивно, если опция не передана. Посмотреть без чтения JSON: `nx g @nx/react:lib --help`. Третий слой дефолтов — `generators` в nx.json (глава 01): записанные там опции подставляются молча.

### Как читать чужой генератор

Навык — брат "найти код executor-а" из главы 03. Цепочка:

```bash
cat node_modules/@nx/react/generators.json | python3 -m json.tool | grep -A4 '"library"'
# "library": {
#   "factory": "./src/generators/library/library",
#   "schema": "./src/generators/library/schema.json", ...

cat node_modules/@nx/react/src/generators/library/schema.json   # ЧТО спрашивает
less node_modules/@nx/react/src/generators/library/library.js   # ЧТО делает
```

Когда генератор сделал не то, что вы ожидали, — ответ всегда в этих двух файлах, а не в документации.

### Зачем командам свои генераторы

Глава 06 закончилась конвенциями: scope/type-структура, теги, non-buildable, vitest, importPath по шаблону. Конвенция, живущая в вики, деградирует с каждым новым человеком. Кто-то забудет теги, кто-то выберет другой bundler, кто-то положит либу не туда.

**Локальный генератор — это конвенция, скомпилированная в код.** Правильная структура получается не потому, что все прочитали вики, а потому что другой путь длиннее.

Ключевой приём при написании — **композиция**. Не создавайте проект руками через `tree.write`. Программно вызовите встроенный генератор (`libraryGenerator` из `@nx/react`) с зафиксированными опциями и доработайте результат.

Встроенный генератор обновит tsconfig.base.json, создаст project.json, eslint- и vite-конфиги — и продолжит это делать правильно после каждого обновления Nx. Ваш код отвечает только за прибавку: доменные шаблоны, валидации, конвенции имён.

> **Версии.** До Nx 17 локальные генераторы жили в `tools/generators` и запускались отдельной командой `nx workspace-generator` — этот механизм выпилен. Современный способ — локальный плагин: обычная либа с `generators.json`, которую `nx g` находит по имени пакета. Если в рабочей репе видите `tools/generators` со schema.json внутри — это артефакт старых версий, при миграции его переводят на плагин.

### Devkit: минимальный словарь

Всё нужное экспортируется из `@nx/devkit`:

- `Tree` — read, write, exists, children, delete.
- `names()` — каноникализация имени: `shoppingCart` даёт fileName `shopping-cart` и className `ShoppingCart`.
- `generateFiles()` — рендер папки шаблонов с подстановками `__fileName__` в путях и `<%= className %>` в содержимом.
- `formatFiles()` — prettier по изменённому.
- `readProjectConfiguration` / `updateProjectConfiguration` — работа с project.json как с объектом.

## В рабочем монорепо

- `npx nx list` — плагины с генераторами; `npx nx list @nx/react` — список генераторов пакета; `nx g <ген> --help` — опции без чтения schema.json.
- Есть ли у команды свои генераторы: `find . -name generators.json -not -path '*/node_modules/*'` — локальный плагин выдаст себя сразу. Нашли — прочитайте: это самая честная документация конвенций репы.
- `grep -B2 -A8 '"generators"' nx.json` — молчаливые дефолты: почему `nx g @nx/react:lib` в этой репе создаёт то, что создаёт.
- Не двигайте, не переименовывайте и не удаляйте проект руками. Возьмите `nx g @nx/workspace:move --project=X --destination=...` и `@nx/workspace:remove`: они обновят tsconfig paths, импорты и конфиги за вас.
- Чужой генератор постоянно вызывают с одними и теми же пятью флагами (видно по истории команд/доке)? Это заявка на локальный генератор-обёртку.

## Что добавляем в проект

Локальный плагин `workspace-plugin` с генератором `feature-lib`. Одна команда создаёт feature-либу по конвенциям главы 06: правильные каталог, importPath, теги, страница-заглушка. Проверим его, сгенерировав `checkout`-домен, который понадобится в главе 10.

## Практическое задание

**Вход:** workspace после главы 06 (слои, теги, boundaries включены).

**Задача:**

1. Установить `@nx/plugin` и сгенерировать локальный плагин `workspace-plugin` в `tools/workspace-plugin`.
2. Сгенерировать в нём заготовку генератора `feature-lib` и реализовать контракт:
   - **Вход:** `name` (позиционный, например `cart`), `scope` (например `checkout`);
   - **Валидация:** scope должен быть существующей папкой в `libs/` — иначе понятная ошибка со списком доступных;
   - **Выход:** либа в `libs/<scope>/feature-<name>` с importPath `@mini-shop/<scope>-feature-<name>`, тегами `scope:<scope>,type:feature`, bundler none и vitest. Плюс компонент `<Name>Page` из шаблона и реэкспорт в index.ts;
   - **Реализация:** композиция с `libraryGenerator` из `@nx/react`, свои файлы — через `generateFiles`.
3. Прогнать `--dry-run`, затем создать боевую либу: `feature-cart` в scope `checkout`. Папку scope создать заранее — или решить, как генератор должен себя вести с новым scope, и обосновать выбор.
4. Убедиться: `nx lint checkout-feature-cart` зелёный (теги легли в матрицу boundaries), `nx graph` показывает новую либу в правильном слое.
5. Написать юнит-тест генератора: имя `shoppingCart` даёт файл `shopping-cart-page.tsx` и класс `ShoppingCartPage`.

**Edge cases на подумать:**

- Повторный запуск с тем же именем — что должно произойти и что произойдёт?
- Почему шаблонные файлы имеют суффикс вроде `.template` / переменные `__fileName__` в путях?
- Генератор сломался после `nx migrate` на новую мажорную версию — какая часть скорее всего: ваши шаблоны или вызов `libraryGenerator`?

## Разбор решения

Шаги 1–2 — плагин и заготовка:

```bash
npx nx add @nx/plugin
npx nx g @nx/plugin:plugin workspace-plugin --directory=tools/workspace-plugin \
  --importPath=@mini-shop/workspace-plugin --linter=eslint --unitTestRunner=vitest

npx nx g @nx/plugin:generator feature-lib \
  --path=tools/workspace-plugin/src/generators/feature-lib
```

> **Версии.** Сигнатуры самих `@nx/plugin`-генераторов менялись между мажорами: имя и путь бывают позиционными или флагом. Сверьтесь с `nx g @nx/plugin:generator --help` своей версии. Суть неизменна: получаем `generators.json` в корне плагина и папку генератора с четырьмя файлами.

`schema.json` — контракт с пользователем:

```json
{
  "$schema": "https://json-schema.org/schema",
  "$id": "FeatureLib",
  "title": "Feature-либа mini-shop по конвенциям главы 06",
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "description": "Имя фичи, например cart",
      "$default": { "$source": "argv", "index": 0 },
      "x-prompt": "Как называется фича?"
    },
    "scope": {
      "type": "string",
      "description": "Домен (существующая папка в libs/)",
      "x-prompt": "К какому домену (scope) относится фича?"
    }
  },
  "required": ["name", "scope"]
}
```

`generator.ts` — композиция + доводка:

```ts
import { formatFiles, generateFiles, names, Tree } from '@nx/devkit';
import { libraryGenerator } from '@nx/react';
import * as path from 'path';
import { FeatureLibGeneratorSchema } from './schema';

export async function featureLibGenerator(tree: Tree, options: FeatureLibGeneratorSchema) {
  const { fileName, className } = names(options.name);

  // Валидация scope по факту, а не по вики: список доменов = папки в libs/
  const scopes = tree.children('libs');
  if (!scopes.includes(options.scope)) {
    const known = scopes.join(', ');
    throw new Error(`Неизвестный scope "${options.scope}". Существующие: ${known}`);
  }

  const projectRoot = `libs/${options.scope}/feature-${fileName}`;

  // Композиция: всю "тяжёлую" работу делает штатный генератор —
  // project.json, vite/eslint-конфиги, алиас в tsconfig.base.json
  await libraryGenerator(tree, {
    name: `${options.scope}-feature-${fileName}`,
    directory: projectRoot,
    importPath: `@mini-shop/${options.scope}-feature-${fileName}`,
    tags: `scope:${options.scope},type:feature`,
    style: 'css',
    linter: 'eslint',
    unitTestRunner: 'vitest',
    bundler: 'none',
    component: false,
  });

  // Наша прибавка: доменный шаблон страницы + публичный API
  generateFiles(tree, path.join(__dirname, 'files'), projectRoot, {
    className,
    fileName,
    scope: options.scope,
    tmpl: '',
  });
  tree.write(
    `${projectRoot}/src/index.ts`,
    `export { ${className}Page } from './lib/${fileName}-page';\n`,
  );

  await formatFiles(tree);
}

export default featureLibGenerator;
```

Шаблон `files/src/lib/__fileName__-page.tsx.template`:

```tsx
export function <%= className %>Page() {
  return (
    <section>
      <h2><%= className %></h2>
      {/* TODO: наполняется фичей */}
    </section>
  );
}
```

И `__fileName__` в имени файла, и `<%= className %>` в содержимом — подстановки из объекта, переданного в `generateFiles`. Суффикс `.template` отрезается при генерации и защищает файл от компиляции и линта в составе самого плагина.

Шаги 3–4 — запуск. Решение по новому scope: **генератор не создаёт домены молча**. Новый домен означает новые правила в boundaries-матрице (глава 06), и это осознанное архитектурное действие, а не побочный эффект скаффолдинга. Поэтому сначала `mkdir libs/checkout` (и строка в depConstraints), потом:

```bash
npx nx g @mini-shop/workspace-plugin:feature-lib cart --scope=checkout --dry-run
# CREATE libs/checkout/feature-cart/project.json
# CREATE libs/checkout/feature-cart/src/lib/cart-page.tsx
# UPDATE tsconfig.base.json
# ...

npx nx g @mini-shop/workspace-plugin:feature-lib cart --scope=checkout
npx nx lint checkout-feature-cart   # зелёный: теги легли в матрицу сразу
```

Шаг 5 — тест без диска (та же Tree-механика):

```ts
import { createTreeWithEmptyWorkspace } from '@nx/devkit/testing';
import { featureLibGenerator } from './generator';

it('каноникализирует имя фичи', async () => {
  const tree = createTreeWithEmptyWorkspace();
  tree.write('libs/catalog/.gitkeep', '');

  await featureLibGenerator(tree, { name: 'shoppingCart', scope: 'catalog' });

  const root = 'libs/catalog/feature-shopping-cart';
  expect(tree.exists(`${root}/src/lib/shopping-cart-page.tsx`)).toBe(true);
  expect(tree.read(`${root}/src/index.ts`, 'utf-8')).toContain('ShoppingCartPage');
});
```

Ответы на оставшиеся edge cases:

- Повторный запуск упадёт внутри `libraryGenerator` на конфликте имени проекта, и это правильное поведение. Идемпотентность генераторам не обещана (глава 01), а "обновление" существующей либы — задача рефакторинга, не скаффолдинга.
- После `nx migrate` ломается обычно вызов `libraryGenerator` (его опции — внутренний API соседнего мажора), а не ваши шаблоны. Это цена композиции, и она ниже альтернативы: без композиции вы бы вручную догоняли все изменения структуры, которые новый Nx делает сам. Юнит-тест генератора падает первым и показывает, что чинить, — поэтому он обязателен, а не опционален.

## Проверь себя

1. Почему `--dry-run` гарантированно показывает ровно то, что сделает реальный запуск? Какая архитектурная особенность генераторов это обеспечивает?
2. Наш генератор вызывает `libraryGenerator` вместо создания файлов руками. Перечисли, что конкретно мы получаем от этой композиции и какую цену платим.
3. Генератор из плагина сделал не то, что вы ожидали. Опиши цепочку файлов в node_modules, по которой вы найдёте причину.
4. Зачем `names()` и почему генератор не должен использовать введённое пользователем имя как есть?
5. Команда обсуждает: записать конвенции создания либ в вики или в генератор. Приведи три аргумента за генератор и один честный аргумент за вики.

<details>
<summary>Ответы</summary>

1. Dry-run и реальный запуск исполняют один и тот же код implementation. Все записи идут в виртуальную файловую систему (Tree), и различие только в последнем шаге: печатать diff или делать flush на диск. Расхождение невозможно по построению: нет отдельной "эмуляции", которая могла бы отстать от реальности.
2. Получаем project.json с правильной структурой, алиас в tsconfig.base.json, eslint/vite/vitest-конфиги и корректную регистрацию проекта. Всё это продолжает соответствовать текущей версии Nx после каждого обновления, потому что поддерживается командой Nx. Платим зависимостью от сигнатуры `libraryGenerator`, которая может меняться между мажорами. После `nx migrate` наш генератор нужно прогнать тестом и, возможно, поправить опции.
3. Начните с `node_modules/<пакет>/generators.json`: найти имя генератора, взять пути `schema` и `factory`. Затем открыть `schema.json` и сверить опции и их дефолты — часто "не то" оказывается молчаливым дефолтом или дефолтом из nx.json. Затем прочитать файл из `factory` и увидеть фактическую логику. Та же цепочка, что для executors в главе 03, только реестр называется generators.json.
4. Пользователь введёт что угодно: `shoppingCart`, `Shopping-Cart`, `shopping cart`. Функция `names()` даёт канонические формы: fileName `shopping-cart`, className `ShoppingCart`, propertyName `shoppingCart`. Структура файлов и имена классов остаются единообразными независимо от того, кто и как вызвал генератор. Без этого конвенция имён умирает на втором пользователе.
5. Три аргумента за генератор. Он выполняется, а не читается, поэтому конвенцию нельзя "забыть". Валидации — наш scope-чек — ловят ошибку в момент создания, а не на ревью. Обновление конвенции означает правку кода в одном месте плюс тест, а не рассылку "перечитайте вики". Честный аргумент за вики: генератор — это код, который надо поддерживать, особенно после мажорных обновлений Nx. Для конвенции, применяемой дважды в год, эта цена может не окупиться.

</details>

## Частая ошибка

Разработчик, впервые взявшийся за кастомный генератор, пишет его "с нуля". Руками через `tree.write` он создаёт project.json и vite-конфиг, правит tsconfig.base.json. Фактически это копия того, что делает `@nx/react:lib`, в собственном коде.

Первые месяцы работает. Потом `nx migrate` меняет структуру конфигов: скажем, репа переезжает на inferred targets или новый формат eslint. Штатный генератор Nx обновляется сам, а самодельный продолжает генерить прошлогоднюю структуру.

Правильный инстинкт: ваш генератор — тонкая обёртка вокруг штатного, то есть валидации, шаблоны и фиксированные опции. Вся "инфраструктурная" генерация идёт только композицией.

Вторая ошибка — генератор-сирота. Его написали на энтузиазме и три месяца им пользовались. Потом структура репы уехала — новая ось тегов, другой test-runner, — а генератор не обновили. Теперь он создаёт либы, которые тут же падают на lint, люди делают вывод "генераторы не работают" и возвращаются к копипасте.

Лечение дисциплинарное. У генератора есть юнит-тест: он падает в CI (continuous integration — сервер, который прогоняет проверки), когда отстал. А любой PR (pull request — запрос на слияние ветки), меняющий конвенции репы, обязан менять и генератор: это такой же контракт, как типы в API.
