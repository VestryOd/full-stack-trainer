<!-- verified: 2026-06-19, corrections: 0 -->
# GitHub Actions

## Что такое GitHub Actions

**GitHub Actions** — встроенная CI/CD (Continuous Integration / Continuous Delivery — непрерывная интеграция и доставка) платформа GitHub. Вместо подключения внешнего сервиса (Jenkins, CircleCI, Travis CI) вы описываете автоматизацию прямо в репозитории в виде YAML-файлов. Эти файлы — **workflows** (рабочие процессы) — хранятся в папке `.github/workflows/` и версионируются вместе с кодом приложения.

Ключевая идея: описать *что делать* (последовательность шагов) и *когда делать* (событие-триггер). Инфраструктура GitHub берёт на себя всё остальное.

```txt
Ваш репозиторий
└── .github/
    └── workflows/
        ├── ci.yml          ← запускается на каждый push / pull request
        ├── deploy.yml      ← запускается при мёрже в main
        └── release.yml     ← запускается при пуше git-тега
```

## Структура workflow YAML

Каждый файл workflow имеет одинаковую структуру верхнего уровня:

```yaml
name: CI                          # отображаемое имя в интерфейсе GitHub Actions

on:                               # ТРИГГЕР — когда запускается этот workflow
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:                              # переменные окружения уровня всего workflow
  NODE_VERSION: '20'

jobs:                             # работа — один или несколько джобов
  test:                           # ID джоба (используется для зависимостей между джобами)
    name: Run tests               # отображаемое имя в интерфейсе
    runs-on: ubuntu-latest        # тип раннера

    steps:                        # упорядоченный список действий/команд в этом джобе
      - name: Checkout code
        uses: actions/checkout@v4  # готовое действие из маркетплейса

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'

      - name: Install dependencies
        run: npm ci                # команда оболочки

      - name: Run tests
        run: npm test
```

Четыре ключа верхнего уровня, которые нужно знать:

```txt
name    — отображаемое имя (необязательно, но рекомендуется)
on      — триггер(ы): какие события запускают этот workflow
env     — переменные окружения, доступные всем джобам workflow
jobs    — реальная работа: словарь ID джобов и их определений
```

## Триггеры (`on`)

Ключ `on` определяет, когда запускается workflow. GitHub Actions поддерживает десятки событий; вот те, что покрывают 90% случаев:

### `push`

```yaml
on:
  push:
    branches: [main, develop]       # только при пушах в эти ветки
    paths:                          # необязательно: только если изменились эти пути
      - 'src/**'
      - 'package.json'
```

Запускается при каждом пуше коммитов в указанные ветки. Фильтр `paths` полезен для монорепозиториев — пропустить фронтенд CI, если изменились только файлы бэкенда.

### `pull_request`

```yaml
on:
  pull_request:
    branches: [main]               # только для PR, нацеленных на main
    types: [opened, synchronize]   # по умолчанию: opened + synchronize (новые коммиты в PR)
```

Запускается при событиях pull request. Самые важные типы: `opened` (PR создан), `synchronize` (в ветку PR добавлен новый коммит), `closed` (PR закрыт или смёржен).

### `schedule`

```yaml
on:
  schedule:
    - cron: '0 6 * * 1'           # каждый понедельник в 06:00 UTC
```

Запускается по расписанию cron — полезно для ночных сборок, еженедельных аудитов зависимостей (`npm audit`) или E2E-тестов по расписанию против продакшна. Формат стандартный Unix cron: `минута час день-месяца месяц день-недели`.

### `workflow_dispatch`

```yaml
on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Target environment'
        required: true
        default: 'staging'
        type: choice
        options: [staging, production]
```

Позволяет запустить workflow вручную из интерфейса GitHub или через API. Блок `inputs` добавляет форму с полями — полезно для deploy-workflow, где человек должен выбрать целевое окружение.

### `workflow_call`

```yaml
on:
  workflow_call:                   # делает этот workflow переиспользуемым другими
    inputs:
      node-version:
        type: string
        required: true
    secrets:
      NPM_TOKEN:
        required: true
```

Используется для создания **переиспользуемых workflows** — подробнее ниже.

## Джобы: параллелизм и зависимости

По умолчанию все джобы в workflow выполняются параллельно. Используйте `needs` для объявления зависимостей:

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps: [...]

  test:
    runs-on: ubuntu-latest
    steps: [...]

  build:
    runs-on: ubuntu-latest
    needs: [lint, test]          # ждёт, пока ОБА lint и test завершатся успешно
    steps: [...]

  deploy:
    runs-on: ubuntu-latest
    needs: build                 # ждёт build
    if: github.ref == 'refs/heads/main'   # запускается только в ветке main
    steps: [...]
```

```txt
Временная шкала:
  t=0s   lint ──────→ pass (30с)
         test ──────────────────→ pass (90с)
                                          ↓
  t=90с                              build (60с)
                                          ↓
  t=150с                           deploy (только в main)
```

Условие `if` на джобе (или шаге) управляет тем, запускается ли он. Распространённые паттерны:

```yaml
if: github.ref == 'refs/heads/main'          # только в ветке main
if: github.event_name == 'pull_request'      # только для PR
if: failure()                                # только если предыдущий шаг упал
if: always()                                 # всегда, даже если предыдущие джобы упали
```

## Matrix builds

**Matrix** позволяет запустить один и тот же джоб несколько раз с разными комбинациями параметров — без дублирования определения джоба.

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        node-version: [18, 20, 22]
        os: [ubuntu-latest, windows-latest]

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node-version }}
      - run: npm ci && npm test
```

Это создаёт 6 параллельных джобов: `{node-18, ubuntu}`, `{node-18, windows}`, `{node-20, ubuntu}`, `{node-20, windows}`, `{node-22, ubuntu}`, `{node-22, windows}`.

Полезные опции:

```yaml
strategy:
  fail-fast: false    # не отменять остальные matrix-джобы при падении одного (по умолч.: true)
  max-parallel: 3     # ограничить число одновременных джобов (полезно при rate limit'ах)

  matrix:
    include:          # добавить конкретные комбинации, которых нет в декартовом произведении
      - node-version: 20
        os: macos-latest
    exclude:          # убрать конкретные комбинации из декартового произведения
      - node-version: 18
        os: windows-latest
```

## Секреты и переменные окружения

Здесь три уровня конфигурационных значений, и выбор неверного — риск безопасности:

```txt
Переменные окружения (env)  → нечувствительный конфиг (NODE_ENV, PORT, API_URL)
Секреты (secrets)           → чувствительные значения (пароли, токены, приватные ключи)
GitHub Environments         → секреты, привязанные к конкретной цели деплоя (staging, prod)
```

**Определение и использование секретов:**

```yaml
# В интерфейсе GitHub: Settings → Secrets and variables → Actions → New repository secret
# Затем в workflow:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Vercel
        env:
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}     # подставляется из GitHub Secrets
          VERCEL_ORG_ID: ${{ secrets.VERCEL_ORG_ID }}
        run: npx vercel --prod --token $VERCEL_TOKEN
```

**GitHub Environments** добавляют слой защиты — можно потребовать ручного подтверждения перед тем, как джоб, нацеленный на окружение `production`, запустится:

```yaml
jobs:
  deploy-prod:
    runs-on: ubuntu-latest
    environment: production        # ссылается на GitHub Environment, созданный в Settings
    steps:
      - run: ./deploy.sh
        env:
          DB_URL: ${{ secrets.DB_URL }}   # этот секрет привязан к окружению "production"
```

### Старший нюанс #1: секреты маскируются, но не шифруются в логах

GitHub Actions маскирует значения секретов в логах (заменяет на `***`). Однако:
- Если вы выводите секрет по частям (`echo ${SECRET:0:3}`), маска это не поймает
- Если зависимость выводит секрет в stdout во время установки (атака на цепочку поставок), маска GitHub поймает его *после факта* только если секрет появляется дословно
- **Никогда не передавайте секреты как аргументы командной строки** (`run: ./deploy.sh --token $SECRET`) — они попадут в листинг процессов на раннере. Передавайте их через переменные окружения.

## Артефакты и кэширование

Это два разных понятия, которые часто путают:

```txt
Кэш (cache)     → ускоряет пайплайн за счёт хранения файлов между ЗАПУСКАМИ одного workflow
                  (node_modules, pip-пакеты, Maven .m2 — то, что меняется редко)

Артефакт        → хранит РЕЗУЛЬТАТ джоба для скачивания или использования СЛЕДУЮЩИМ ДЖОБОМ
(artifact)        в том же запуске (скомпилированный бандл, отчёт о тестах, слой Docker-образа)
```

**Кэширование `node_modules`:**

```yaml
- uses: actions/setup-node@v4
  with:
    node-version: '20'
    cache: 'npm'          # встроенный кэш — кэширует ~/.npm с ключом по хешу package-lock.json
```

Или явно:

```yaml
- uses: actions/cache@v4
  with:
    path: ~/.npm
    key: ${{ runner.os }}-npm-${{ hashFiles('**/package-lock.json') }}
    restore-keys: |
      ${{ runner.os }}-npm-
```

`key` — условие попадания в кэш: если хеш `package-lock.json` изменился (новая/обновлённая зависимость), старый кэш не используется (cache miss) и `npm ci` выполняется полностью, создавая новую запись кэша. При cache hit `npm ci` всё равно запускается, но работает намного быстрее (проверяет, не скачивает).

**Передача результатов сборки между джобами:**

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci && npm run build
      - uses: actions/upload-artifact@v4
        with:
          name: dist-bundle             # имя артефакта
          path: dist/                   # какие файлы загрузить
          retention-days: 7             # сколько хранить

  deploy:
    runs-on: ubuntu-latest
    needs: build
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist-bundle
          path: dist/
      - run: ./scripts/deploy.sh
```

## Переиспользуемые workflows

Когда несколько репозиториев (или несколько workflow в одном репо) выполняют одну и ту же логику, **reusable workflows** устраняют дублирование. Переиспользуемый workflow — это обычный workflow-файл с `on: workflow_call`.

```yaml
# .github/workflows/shared-test.yml
name: Shared Test Suite

on:
  workflow_call:
    inputs:
      node-version:
        type: string
        default: '20'
    secrets:
      NPM_TOKEN:
        required: false

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ inputs.node-version }}
      - run: npm ci && npm test
```

```yaml
# .github/workflows/ci.yml — вызывает общий workflow
name: CI

on:
  push:
    branches: [main]

jobs:
  run-tests:
    uses: ./.github/workflows/shared-test.yml     # путь в том же репозитории
    with:
      node-version: '20'
    secrets:
      NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
```

Для переиспользования из другого репозитория путь принимает вид `owner/repo/.github/workflows/file.yml@ref`.

## Composite actions (составные действия)

**Composite action** — переиспользуемая *часть джоба* — группа шагов, упакованных в одну вызов через `uses:`. В отличие от reusable workflow (который является полным джобом), composite action встраивается в джоб рядом с другими шагами.

```yaml
# .github/actions/setup-and-install/action.yml
name: Setup Node and install dependencies
description: Checks out code, sets up Node.js, and runs npm ci with caching

inputs:
  node-version:
    description: Node.js version
    default: '20'

runs:
  using: composite
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: ${{ inputs.node-version }}
        cache: npm
    - run: npm ci
      shell: bash
```

```yaml
# Любой workflow теперь может делать так:
steps:
  - uses: ./.github/actions/setup-and-install
    with:
      node-version: '20'
  - run: npm test
  - run: npm run build
```

```txt
Composite action vs Reusable workflow — когда что использовать:

  Composite action    → переиспользовать ГРУППУ ШАГОВ внутри джоба
                        (setup, установка, сборка — затем вызывающий добавляет свои шаги)

  Reusable workflow   → переиспользовать ЦЕЛЫЙ ДЖОБ (или набор джобов)
                        (полный тест-сьют, полная последовательность деплоя)
```

## Полный реальный пример: test → build → deploy на Vercel

```yaml
# .github/workflows/ci-deploy.yml
name: CI + Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  # ── 1. Lint + Type-check ──────────────────────────────────────
  lint:
    name: Lint & Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: npm
      - run: npm ci
      - run: npm run lint
      - run: npm run type-check

  # ── 2. Тесты ──────────────────────────────────────────────────
  test:
    name: Unit & Integration Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: npm
      - run: npm ci
      - run: npm test -- --coverage
      - uses: actions/upload-artifact@v4
        if: always()                      # загружать coverage даже если тесты упали
        with:
          name: coverage-report
          path: coverage/
          retention-days: 7

  # ── 3. Сборка ─────────────────────────────────────────────────
  build:
    name: Build
    runs-on: ubuntu-latest
    needs: [lint, test]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: npm
      - run: npm ci
      - run: npm run build
      - uses: actions/upload-artifact@v4
        with:
          name: next-build
          path: .next/

  # ── 4. Деплой (только ветка main) ─────────────────────────────
  deploy:
    name: Deploy to Vercel
    runs-on: ubuntu-latest
    needs: build
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    environment: production
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          name: next-build
          path: .next/
      - name: Deploy
        run: npx vercel --prod --token ${{ secrets.VERCEL_TOKEN }}
        env:
          VERCEL_ORG_ID: ${{ secrets.VERCEL_ORG_ID }}
          VERCEL_PROJECT_ID: ${{ secrets.VERCEL_PROJECT_ID }}
```

## GitHub-hosted vs self-hosted runners

```txt
                    GitHub-hosted         Self-hosted
─────────────────────────────────────────────────────────────────────
Настройка           Нулевая               Установить ПО раннера,
                                          зарегистрировать в GitHub
Обслуживание        Никакого (GitHub)     Ваша ответственность
                                          (обновления ОС, патчи)
Доступ к сети       Только публичный      Может достигать приватных
                    интернет              VPC, БД
Железо              Стандартные VM        Любое — GPU, конкретный CPU, ARM
Модель оплаты       Поминутная            Ваши расходы на инфраструктуру
Изоляция            Чистая VM каждый раз  Может быть постоянным
                                          (риск общего состояния)
Варианты ОС         ubuntu, windows,      Всё, где можно запустить
                    macos                 ПО раннера
```

### Старший нюанс #2: безопасность self-hosted runner

Self-hosted раннеры на **публичных репозиториях** — серьёзный риск безопасности: вредоносный PR может изменить workflow для запуска произвольного кода на вашем раннере — получив доступ к приватным ключам, внутренним БД и другим секретам на машине.

Меры защиты:
- **Требовать подтверждения для первичных контрибьюторов** (настройка GitHub: "Require approval for all outside collaborators")
- **Запускать self-hosted раннеры в изолированных окружениях** (эфемерные VM, контейнеры) — не на машинах с постоянным доступом к чувствительным системам
- **Оставить self-hosted раннеры только для приватных репозиториев**, если они имеют доступ к внутренним ресурсам

## Типичные ошибки на интервью

- **Путать `env` на уровне workflow, джоба и шага** — переменные окружения каскадируют: `env` уровня workflow доступен везде; уровня джоба — всем шагам этого джоба; уровня шага — только этому шагу. Секрет, установленный не на том уровне, может просто не быть виден там, где он нужен.

- **Использовать `npm install` вместо `npm ci` в пайплайнах** — `npm install` может модифицировать `package-lock.json` при несоответствиях; `npm ci` всегда устанавливает точные версии из lockfile и падает, если lockfile устарел. В CI всегда используйте `npm ci`.

- **Не кэшировать зависимости** — запуск `npm ci` без кэша добавляет 1–3 минуты на установку зависимостей в каждом джобе. `actions/setup-node@v4` с `cache: npm` решает это одной строкой.

- **Хранить секреты в `env` уровня workflow** — значения `env` уровня workflow видны в интерфейсе GitHub и логах; секреты, доступные через `${{ secrets.NAME }}`, маскируются. Никогда не храните чувствительные значения в обычном `env`.

- **Не понимать, что `needs` создаёт жёсткую зависимость, а не просто порядок** — если джоб из `needs` падает, зависящий джоб не запускается вообще (если не установлено `if: always()`). Это означает, что упавший джоб test *заблокирует* джоб deploy — что именно то, что нужно, но важно это понимать, а не считать "просто сортировкой".

- **Путать reusable workflow и composite action** — reusable workflow вызывается через `uses:` в секции `jobs:` и является полным джобом; composite action вызывается через `uses:` в секции `steps:` и является группой шагов. Они не взаимозаменяемы.

- **Забыть `if: github.event_name == 'push'` на джобе deploy** — workflow, запускаемый и на `push`, и на `pull_request`, будет пытаться задеплоить при создании PR, если нет фильтра. PR из форка также не имеет доступа к секретам — джоб deploy упадёт или выполнится с пустыми значениями.
