<!-- verified: 2026-06-19, corrections: 0 -->
# GitLab CI

## Что такое GitLab CI

**GitLab CI** (GitLab Continuous Integration) — встроенная платформа GitLab для CI/CD (непрерывная интеграция и непрерывная доставка). Как и GitHub Actions, она не требует внешнего сервиса. Вы коммитите файл `.gitlab-ci.yml` в корень репозитория. GitLab сам его подхватывает и запускает по нему пайплайны.

GitLab CI появился на несколько лет раньше GitHub Actions и остаётся главным CI/CD-решением во многих компаниях, которые размещают собственную Git-инфраструктуру. Если компания работает на собственном экземпляре GitLab (on-premises — на серверах организации), вы почти наверняка будете работать с GitLab CI.

## Структура `.gitlab-ci.yml`

Файл конфигурации находится в **корне репозитория** (не в папке `.gitlab/` — всегда именно `.gitlab-ci.yml` на верхнем уровне). Он написан на YAML (текстовый формат для конфигурации).

```yaml
# .gitlab-ci.yml

stages:           # определяет порядок этапов; джобы в одном stage выполняются параллельно
  - lint
  - test
  - build
  - deploy

variables:        # переменные уровня пайплайна (нечувствительный конфиг)
  NODE_VERSION: "20"
  NODE_ENV: "test"

# ── Определение джоба ─────────────────────────────────────────────
run-lint:                       # имя джоба (произвольное, уникальное в файле)
  stage: lint                   # к какому stage относится этот джоб
  image: node:20-alpine         # Docker-образ для запуска этого джоба
  before_script:                # команды перед script — выполняются в каждом джобе
    - npm ci
  script:                       # реальные команды — обязательный ключ
    - npm run lint
  cache:                        # настройка кэша
    key: "$CI_COMMIT_REF_SLUG"  # ключ кэша — здесь: имя ветки
    paths:
      - node_modules/

run-tests:
  stage: test
  image: node:20-alpine
  before_script:
    - npm ci
  script:
    - npm test -- --coverage
  artifacts:                    # файлы, сохраняемые после завершения джоба
    when: always                # сохранять даже если джоб упал
    paths:
      - coverage/
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage/cobertura-coverage.xml
    expire_in: 7 days

build-app:
  stage: build
  image: node:20-alpine
  before_script:
    - npm ci
  script:
    - npm run build
  artifacts:
    paths:
      - dist/
    expire_in: 1 hour           # короткоживущий: нужен только для джоба deploy

deploy-staging:
  stage: deploy
  image: alpine:latest
  script:
    - ./scripts/deploy.sh staging
  environment:                  # говорит GitLab, что этот джоб деплоит в окружение
    name: staging
    url: https://staging.example.com
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

### Ключ `stages`

`stages` определяет одновременно и **имена** этапов, и **порядок** их выполнения. Джобы, принадлежащие одному stage, выполняются параллельно; следующий stage начинается только когда все джобы текущего прошли успешно.

```txt
stages: [lint, test, build, deploy]

  Stage lint  → run-lint (один джоб, выполняется один)
       ↓ (прошёл)
  Stage test  → run-tests (один джоб, но могло быть больше)
       ↓ (прошёл)
  Stage build → build-app
       ↓ (прошёл)
  Stage deploy → deploy-staging
```

Если опустить `stages`, GitLab использует значения по умолчанию: `[.pre, build, test, deploy, .post]`. Два специальных stage — `.pre` всегда выполняется до всего остального, `.post` — после всего — независимо от того, что указано в `stages`.

### Ключ `script`

`script` — **единственный обязательный ключ** в джобе. Это список команд оболочки, которые выполняются последовательно внутри контейнера джоба. Если любая команда возвращает ненулевой код выхода — джоб падает.

```yaml
script:
  - echo "Starting build"
  - npm run build
  - echo "Build complete"
```

`before_script` выполняется перед `script` и обычно используется для подготовки (установка зависимостей). `after_script` выполняется после `script` независимо от успеха или падения — полезен для очистки.

```txt
Порядок выполнения джоба:
  before_script  (подготовка: npm ci, apt-get install, ...)
  script         (реальная работа)
  after_script   (очистка — выполняется даже при падении)
```

### Ключ `image`

Каждый джоб выполняется внутри **Docker-контейнера**. Ключ `image` указывает, какой Docker-образ использовать:

```yaml
image: node:20-alpine    # Node.js 20 на Alpine Linux (маленький образ)
```

Можно установить образ по умолчанию для всех джобов на верхнем уровне и переопределить его для конкретного джоба:

```yaml
default:
  image: node:20-alpine  # используется всеми джобами, у которых нет своего image

build-go-service:
  image: golang:1.22     # переопределяет дефолт для этого конкретного джоба
  script:
    - go build ./...
```

Это ключевое отличие от GitHub Actions: в GitLab CI каждый джоб по умолчанию выполняется в Docker-контейнере (при Docker executor). В GitHub Actions раннер имеет предустановленные инструменты на хост-VM (виртуальной машине), и вы используете `uses: actions/setup-node@v4` для их настройки.

## GitLab Runner

**GitLab Runner** — отдельное open-source приложение (написано на Go), которое регистрируется у экземпляра GitLab и выполняет джобы из ваших пайплайнов. Отношения:

```txt
  Сервер GitLab               GitLab Runner (отдельная машина)
  ┌─────────────────┐         ┌───────────────────────────────────┐
  │ Читает          │         │                                   │
  │ .gitlab-ci.yml  │──джоб──→│ Забирает джоб                     │
  │ при каждом пуше │         │ Выполняет его в Docker-контейнере │
  │                 │←─итог───│ (или shell, VM, K8s-под...)       │
  └─────────────────┘         └───────────────────────────────────┘
```

### Исполнители раннера (executors)

**Executor** (исполнитель) определяет, как именно раннер запускает каждый джоб:

```txt
docker      → каждый джоб выполняется в чистом Docker-контейнере
              (самый распространённый вариант)
              требует Docker на машине с раннером

shell       → каждый джоб выполняется в оболочке машины раннера
              нет изоляции — джобы разделяют окружение машины

kubernetes  → каждый джоб выполняется как pod в Kubernetes-кластере
              (K8s — это Kubernetes, платформа оркестрации)
              хорошо для крупных, cloud-native пайплайнов

docker+machine → выделяет новую облачную VM для каждого джоба
                 (GitLab-эквивалент GitHub-hosted runners)
```

### Типы раннеров

```txt
Shared runners  → предоставляются GitLab.com для всех проектов;
                  на бесплатных тарифах — лимит минут в месяц

Group runners   → зарегистрированы на GitLab-группу; доступны
                  всем проектам этой группы

Project runners → зарегистрированы на один проект; доступны
                  только ему

Self-hosted     → раннер, который вы сами ставите и обслуживаете,
(любой тип)       в любом месте
```

Для GitLab.com (SaaS-версия, software as a service) shared runners доступны предварительно настроенными. Для self-hosted экземпляра GitLab (распространено в корпоративной среде) вы должны самостоятельно установить и зарегистрировать раннеры.

**Регистрация self-hosted раннера:**

```bash
# Установка бинарника раннера (пример для Linux)
repo=https://packages.gitlab.com/install/repositories/runner/gitlab-runner
curl -L "$repo/script.deb.sh" | sudo bash
sudo apt-get install gitlab-runner

# Регистрация у вашего экземпляра GitLab
sudo gitlab-runner register \
  --url https://gitlab.example.com \
  --token <your-registration-token> \
  --executor docker \
  --docker-image node:20-alpine \
  --description "my-docker-runner"
```

## Переменные пайплайна

Переменные в GitLab CI поступают из нескольких источников с определённым приоритетом:

```txt
Приоритет (высший → низший):
  1. Переменные триггера (передаются при запуске через API)
  2. Переменные запланированного пайплайна
  3. Ручные переменные (заданы при нажатии "Run pipeline")
  4. Переменные уровня проекта (Settings → CI/CD → Variables)
  5. Переменные уровня группы
  6. Переменные уровня экземпляра (только admin, для self-hosted)
  7. Переменные из .gitlab-ci.yml (ключ `variables:`)
```

**Определение переменных в `.gitlab-ci.yml`:**

```yaml
variables:
  NODE_ENV: "production"          # доступна всем джобам
  DOCKER_REGISTRY: "registry.example.com"

deploy:
  variables:
    DEPLOY_TARGET: "us-east-1"   # доступна только в этом джобе
  script:
    - echo "Deploying to $DEPLOY_TARGET"
```

**Предопределённые CI/CD-переменные** — GitLab сам подставляет в каждый пайплайн множество полезных переменных:

```txt
$CI_COMMIT_SHA        — полный SHA коммита, запустившего пайплайн
$CI_COMMIT_SHORT_SHA  — первые 8 символов SHA коммита
$CI_COMMIT_BRANCH     — имя ветки (пусто для пайплайнов тегов)
$CI_COMMIT_TAG        — имя тега (пусто для пайплайнов веток)
$CI_COMMIT_REF_SLUG   — имя ветки или тега, спецсимволы → -
                        (годится как тег образа или ключ кэша)
$CI_PIPELINE_ID       — уникальный числовой ID пайплайна
$CI_JOB_ID            — уникальный числовой ID джоба
$CI_PROJECT_PATH      — namespace/project-name ("myorg/myapp")
$CI_REGISTRY          — адрес встроенного Container Registry GitLab
$CI_REGISTRY_IMAGE    — полный путь образа для этого проекта
$CI_REGISTRY_USER     — имя пользователя для входа в реестр
$CI_REGISTRY_PASSWORD — пароль для входа в реестр (job token)
```

Реальный пример — тегирование и пуш Docker-образа тегом SHA (хеш, который однозначно определяет коммит):

```yaml
build-docker:
  stage: build
  image: docker:24
  services:
    - docker:24-dind               # dind = Docker-in-Docker: демон Docker,
                                   # запущенный внутри контейнера джоба; нужен
                                   # для выполнения команд docker внутри контейнера
  script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA
```

## `rules` vs `only`/`except`

Они управляют **когда запускается джоб**. `only`/`except` — старый синтаксис; `rules` — современная замена, которую следует использовать в новых пайплайнах.

### `only` / `except` (устаревший синтаксис — избегать в новых пайплайнах)

```yaml
deploy:
  script: ./deploy.sh
  only:
    - main                  # только когда ветка — "main"
    - tags                  # или когда запушен git-тег
  except:
    - schedules             # но не для запланированных пайплайнов
```

Ограничения: `only`/`except` работает как плоский список условий (имена веток, источники пайплайна) и плохо поддерживает сложную логику или выражения с переменными.

### `rules` (современный подход — предпочтительный)

`rules` вычисляет условия последовательно и останавливается на первом совпадении:

```yaml
deploy-production:
  script: ./deploy.sh production
  rules:
    - if: $CI_COMMIT_TAG                          # если запушен git-тег → запустить
      when: on_success
    - if: $CI_COMMIT_BRANCH == "main"             # иначе в main → вручную
      when: manual
    - when: never                                  # иначе → не запускать никогда
```

Доступные значения `when`:

```txt
on_success   → запустить, если все джобы прошлых stage прошли
               (по умолчанию)
on_failure   → запустить, только если предыдущий джоб упал
               (очистка и уведомления)
always       → запускать всегда, что бы ни было с прошлыми джобами
manual       → добавить джоб, но ждать нажатия "Run" человеком
never        → не добавлять джоб в пайплайн вообще
delayed      → запустить с задержкой (start_in: '10 minutes')
```

`rules` также поддерживает `changes` (запустить только если изменились определённые файлы) и `exists` (запустить только если файл существует):

```yaml
run-frontend-tests:
  script: npm test
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      changes:
        - frontend/**/*
        - package.json
```

## Кэширование и артефакты

Концепции те же, что в GitHub Actions, но синтаксис отличается:

**Кэш** — сохранять файлы между запусками пайплайна:

```yaml
run-tests:
  cache:
    key:
      files:
        - package-lock.json      # кэш инвалидируется при изменении этого файла
    paths:
      - node_modules/
    policy: pull-push            # pull — загрузить кэш в начале, push — сохранить в конце
                                 # также: pull (только чтение), push (только запись)
```

**Артефакты** — передавать файлы между джобами в одном пайплайне:

```yaml
build-app:
  artifacts:
    paths:
      - dist/
    expire_in: 1 hour

deploy:
  needs:
    - job: build-app
      artifacts: true            # явно загрузить артефакты из build-app
  script:
    - ls dist/                   # файлы доступны здесь
```

По умолчанию джоб автоматически загружает артефакты из всех джобов **предыдущих stages**. Использование `needs:` с `artifacts: true` делает зависимость явной и позволяет загрузить из конкретного джоба без ожидания всего его stage.

## `needs` — DAG-пайплайны

GitLab CI поддерживает **DAG** (Directed Acyclic Graph — ориентированный ациклический граф; структура графа, где зависимости текут в одном направлении без циклов) для выполнения пайплайна. С `needs:` джоб может стартовать сразу после готовности своих конкретных зависимостей — без ожидания всего предыдущего stage.

```txt
Без needs (по stage): весь stage "test" должен завершиться
до старта любого джоба "build".

  lint ─────────────────────────╮
  unit-tests ───────────────────┤─→ build (стартует здесь)
  integration-tests (10 мин) ───╯

С needs (DAG): build стартует сразу после lint.

  lint ─────────────────────────────→ build (сразу после lint)
  unit-tests ───────────────────────→
  integration-tests (10 мин) ───────→ (не блокирует build)
```

```yaml
build-fast:
  stage: build
  needs:
    - lint          # стартовать как только lint прошёл, не ждать тестов
  script:
    - npm run build
```

## GitLab CI vs GitHub Actions — переключение между ними

Это наиболее практически полезное сравнение для fullstack-разработчика, работающего с обеими платформами:

```txt
Тема                  GitHub Actions         GitLab CI
──────────────────────────────────────────────────────────────────
Где лежит конфиг      .github/workflows/     .gitlab-ci.yml
                      *.yml, много файлов    в корне репозитория,
                                             по умолчанию один

Имя конфига           любое имя, любое       всегда .gitlab-ci.yml
                      количество

Концепция stages      явных stages нет,      явный ключ `stages:`:
                      порядок — через        имена и порядок
                      `needs:`               в одном месте

Параллельные джобы    по умолчанию, если     по умолчанию внутри
                      нет `needs:`           одного stage

Образ для джоба       на шаг, через          на джоб, через
                      `actions/setup-*`      `image:` (Docker-first)
                      на хост-VM

Ключ триггера         `on:`                  `rules:` / `only:`

Слово для PR/MR       pull_request           merge_request_event

Доступ к секретам     ${{ secrets.NAME }}    $VARIABLE_NAME, как
                                             любая переменная

Ручной триггер        `workflow_dispatch`    `when: manual` на джобе

Кэширование           actions/cache@v4       ключ `cache:` в джобе

Передача файлов       upload-artifact и      `artifacts:` в джобе
между джобами         download-artifact

Переиспользование     reusable workflows,    `include:` подключает
пайплайнов            composite actions      другие YAML-файлы;
                                             `extends:` наследует
                                             от шаблонов джобов

Встроенный реестр     GitHub Container       GitLab Container
контейнеров           Registry (ghcr.io)     Registry ($CI_REGISTRY)

Self-hosted runners   GitHub Actions runner  GitLab Runner: свой
                      (тот же бинарник,      бинарник, несколько
                      другой конфиг)         исполнителей
```

### Ключевые различия, которые нужно усвоить

**1. Stages vs граф зависимостей**

В GitHub Actions нет концепции `stages`. Порядок выполнения задаётся исключительно через `needs:`. В GitLab CI `stages:` определяет порядок на уровне stage; внутри одного stage джобы параллельны.

```yaml
# GitHub Actions — порядок через needs
jobs:
  lint:
    ...
  test:
    needs: [lint]
  build:
    needs: [test]

# GitLab CI — порядок через stages
stages: [lint, test, build]
lint-job:
  stage: lint
test-job:
  stage: test      # автоматически после stage lint
build-job:
  stage: build     # автоматически после stage test
```

**2. Ключ `include` для разбивки больших пайплайнов**

GitLab CI поддерживает разбивку пайплайна на несколько файлов через `include:`:

```yaml
# .gitlab-ci.yml
include:
  - local: '.gitlab/ci/test.yml'
  - local: '.gitlab/ci/build.yml'
  - project: 'my-org/shared-pipelines'   # подключить из другого GitLab-проекта
    ref: main
    file: '/templates/deploy.yml'
```

GitHub Actions достигает этого иначе — через reusable workflows, вызываемые из секции `jobs:`.

**3. `extends:` для шаблонов джобов**

GitLab CI имеет встроенную систему шаблонов и наследования:

```yaml
.node-defaults:          # джобы, начинающиеся с . — скрытые (шаблоны, не запускаются)
  image: node:20-alpine
  before_script:
    - npm ci
  cache:
    key: "$CI_COMMIT_REF_SLUG"
    paths: [node_modules/]

lint:
  extends: .node-defaults    # наследует image, before_script, cache
  stage: lint
  script:
    - npm run lint

test:
  extends: .node-defaults    # то же наследование
  stage: test
  script:
    - npm test
```

В GitHub Actions это достигается через composite actions и reusable workflows — прямого эквивалента `extends:` нет.

**4. Merge Request-пайплайны**

В GitLab есть концепция **Merge Request (MR) пайплайнов** первого класса. Они выполняются в контексте MR и получают MR-специфичные переменные, например `$CI_MERGE_REQUEST_ID` и `$CI_MERGE_REQUEST_SOURCE_BRANCH_NAME`:

```yaml
test:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"   # только для MR
```

В GitHub Actions используется событие `pull_request`, которое концептуально идентично, но переменные называются иначе (`github.event.pull_request.number` и т.д.).

## Типичные ошибки на интервью

- **"GitLab CI использует YAML так же, как GitHub Actions"** — структура похожа, но семантика отличается. Наибольшее концептуальное различие: в GitLab CI `stages:` — это механизм упорядочивания первого класса; в GitHub Actions используется только `needs:`.

- **Забывать, что джобы в одном stage выполняются параллельно** — распространённый источник багов. Если два джоба в одном stage оба пишут по одному и тому же пути артефакта или с одним и тем же ключом кэша, между ними будет гонка. Выносите конфликтующие джобы в разные stages или используйте `needs:` для явной последовательности.

- **Использовать `only`/`except` в новых пайплайнах** — этот синтаксис устарел в пользу `rules:`. Осведомлённость об этой эволюции на собеседовании сигнализирует, что вы работали с GitLab CI недавно, а не несколько лет назад.

- **Путать `artifacts` и `cache`** — артефакты передают файлы между джобами внутри одного запуска пайплайна, а кэш сохраняет файлы между несколькими запусками. Артефакты хранятся у GitLab, их можно скачать из веб-интерфейса (UI). Кэш хранится на раннере.

- **Не знать, что такое `dind`** — это сокращение от Docker-in-Docker. Сервис `docker:dind` нужен, чтобы выполнить `docker build` внутри джоба GitLab CI, который сам работает в Docker-контейнере. Без него у команды `docker` (CLI — интерфейс командной строки) нет демона, с которым работать. Интервьюеры, работающие с GitLab CI, спрашивают об этом, потому что это реальная операционная проблема.

- **Считать, что синтаксис `${{ secrets.NAME }}` работает в GitLab CI** — в GitLab CI любая переменная доступна как обычная shell-переменная `$VARIABLE_NAME`. Это касается и секретов из Settings → CI/CD → Variables. Синтаксис `${{ }}` специфичен для GitHub Actions.

- **Не знать о `.pre` и `.post`** — это специальные имена stage в GitLab CI. Stage `.pre` всегда выполняется до всех остальных, а `.post` — после них, независимо от списка `stages:`. Они полезны для глобальной подготовки и очистки, и о них часто спрашивают на собеседовании.
