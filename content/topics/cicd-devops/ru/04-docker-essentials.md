<!-- verified: 2026-06-19, corrections: 0 -->
# Docker Essentials

## Что такое Docker (и чем он не является)

**Docker** — платформа для сборки, доставки и запуска приложений в изолированных, воспроизводимых средах, называемых **контейнерами**. Ключевая проблема, которую он решает: "работает у меня на машине" — приложение ведёт себя по-разному в dev, CI, staging и production, потому что в каждом окружении своя версия ОС, runtime, установленные библиотеки и системная конфигурация.

Docker — **не** виртуальная машина (VM). Это различие важно:

```txt
Виртуальная машина (VM):
  ┌──────────────────────────────────────────────┐
  │              Host OS (Linux/Windows)          │
  │  ┌──────────────────────────────────────────┐│
  │  │     Гипервизор (VMware, VirtualBox)       ││
  │  │  ┌──────────────┐  ┌──────────────┐      ││
  │  │  │  Guest OS    │  │  Guest OS    │      ││
  │  │  │  (полный     │  │  (полный     │      ││
  │  │  │   Linux)     │  │   Linux)     │      ││
  │  │  │  App + libs  │  │  App + libs  │      ││
  │  │  └──────────────┘  └──────────────┘      ││
  │  └──────────────────────────────────────────┘│
  └──────────────────────────────────────────────┘
  У каждой VM — своё полное ядро ОС; тяжело, запуск занимает минуты

Docker Container (контейнер):
  ┌──────────────────────────────────────────────┐
  │              Host OS (ядро Linux)             │
  │  ┌───────────────────────────────────────┐   │
  │  │     Docker Engine (демон runtime)      │   │
  │  │  ┌──────────────┐ ┌──────────────┐   │   │
  │  │  │  Контейнер A  │ │  Контейнер B  │   │   │
  │  │  │  app + libs   │ │  app + libs   │   │   │
  │  │  │  (нет своего  │ │  (нет своего  │   │   │
  │  │  │  ядра ОС)    │ │  ядра ОС)    │   │   │
  │  │  └──────────────┘ └──────────────┘   │   │
  │  └───────────────────────────────────────┘   │
  └──────────────────────────────────────────────┘
  Контейнеры разделяют ядро хост-ОС — лёгкие, запуск за миллисекунды
```

Контейнеры используют функции ядра Linux — **namespaces** (изоляция процессов: у каждого контейнера своё дерево процессов, сетевой стек, видимость файловой системы) и **cgroups** (control groups — контрольные группы: ограничения использования CPU и памяти) — чтобы создать иллюзию отдельной машины без накладных расходов полной ОС.

## Image vs Container

Это самое фундаментальное различие в Docker:

```txt
Image (образ)     = схема — read-only (только для чтения) послойный снимок файловой системы
                    со всем необходимым для запуска приложения
                    (runtime, зависимости, конфигурационные файлы, скомпилированный код)

Container         = запущенный экземпляр образа
(контейнер)         = образ + записываемый слой сверху + изолированный процесс
```

Аналогия: образ — это определение класса в коде; контейнер — объект, созданный из этого класса. Из одного образа можно одновременно запустить множество контейнеров.

```bash
# Собрать образ из Dockerfile (рассмотрим ниже)
docker build -t my-app:1.0 .

# Запустить контейнер из этого образа
docker run my-app:1.0

# Запустить несколько контейнеров из одного образа
docker run -d --name app-1 my-app:1.0
docker run -d --name app-2 my-app:1.0
docker run -d --name app-3 my-app:1.0

# Список запущенных контейнеров
docker ps

# Список всех образов
docker images
```

Ключевые флаги для `docker run`:

```bash
docker run \
  -d \                          # detached: запустить в фоне
  -p 3000:3000 \                # маппинг порта: хост:контейнер
  -e NODE_ENV=production \      # переменная окружения
  -v ./data:/app/data \         # монтирование volume: путь-хоста:путь-контейнера
  --name my-container \         # дать контейнеру имя
  --rm \                        # удалить контейнер после остановки
  my-app:1.0
```

## Dockerfile

**Dockerfile** — текстовый файл с последовательностью инструкций, которые Docker выполняет для сборки образа. Каждая инструкция создаёт новый **слой** (layer) в образе (подробнее о слоях ниже).

```dockerfile
# syntax=docker/dockerfile:1
FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./

RUN npm ci --only=production

COPY . .

RUN npm run build

EXPOSE 3000

CMD ["node", "dist/server.js"]
```

### `FROM` — базовый образ

```dockerfile
FROM node:20-alpine
```

Каждый Dockerfile начинается с `FROM`, указывающего **базовый образ** — отправную точку, поверх которой строится ваш образ. Распространённые варианты для Node.js:

```txt
node:20          — полный образ на базе Debian (~350 МБ)
node:20-alpine   — образ на базе Alpine Linux (~50 МБ)
                   меньше и быстрее загружается, но использует musl libc вместо glibc
                   (может вызывать проблемы с нативными аддонами, рассчитанными на glibc)
node:20-slim     — на базе Debian, но со многими инструментами удалёнными (~80 МБ)
                   золотая середина между полным и alpine
```

`FROM scratch` означает начало с пустого образа — используется для минималистичных приложений с единственным бинарником (Go-бинарники и т.д.).

### `WORKDIR` — рабочая директория

```dockerfile
WORKDIR /app
```

Устанавливает рабочую директорию внутри контейнера для всех последующих инструкций (`RUN`, `COPY`, `CMD` и т.д.). Создаёт директорию, если её нет. Эквивалент `mkdir -p /app && cd /app`.

### `COPY` — копирование файлов с хоста в образ

```dockerfile
COPY package.json package-lock.json ./
COPY . .
```

`COPY <src> <dest>` копирует файлы из **build context** (директории, переданной в `docker build`) в файловую систему образа. Назначение `./` означает текущий `WORKDIR`.

`COPY . .` копирует всё из build context в `WORKDIR` — но только то, что не исключено `.dockerignore` (рассмотрим ниже).

`ADD` похожа на `COPY`, но также поддерживает URL и автоматически распаковывает `.tar`-архивы. **Предпочитайте `COPY`** — она явная и предсказуемая. Используйте `ADD` только когда специально нужна авто-распаковка.

### `RUN` — выполнить команду при сборке

```dockerfile
RUN npm ci --only=production
```

`RUN` выполняет команду оболочки **во время сборки** и сохраняет результат как новый слой образа. Используется для установки зависимостей, компиляции, генерации файлов и т.д.

**Лучшая практика — объединять команды для уменьшения числа слоёв:**

```dockerfile
# ❌ Создаёт 3 отдельных слоя — лишние накладные расходы
RUN apt-get update
RUN apt-get install -y curl
RUN rm -rf /var/lib/apt/lists/*

# ✅ Создаёт 1 слой — объединяет связанные команды
RUN apt-get update && \
    apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/*
```

Финальный `rm -rf /var/lib/apt/lists/*` удаляет кэш пакетного менеджера — если бы он был в отдельном `RUN`, кэш всё равно остался бы запечённым в предыдущем слое, делая образ больше.

### `EXPOSE` — документировать порт

```dockerfile
EXPOSE 3000
```

`EXPOSE` — **только документация** — не публикует порт фактически. Говорит тому, кто читает Dockerfile, какой порт слушает контейнеризованное приложение. Реальный маппинг порта происходит при `docker run` с флагом `-p`.

### `ENV` — установить переменные окружения

```dockerfile
ENV NODE_ENV=production
ENV PORT=3000
```

Устанавливает переменные окружения в образе. В отличие от `-e` при запуске (что применяется только к этому запуску контейнера), `ENV` запекается в образ и влияет на все контейнеры, созданные из него.

## `CMD` vs `ENTRYPOINT` — критически важное различие

Это одна из наиболее часто неправильно понимаемых частей синтаксиса Dockerfile. Оба определяют, что запускается при старте контейнера — но они играют разные роли.

### `CMD` — команда по умолчанию, легко переопределяется

```dockerfile
CMD ["node", "dist/server.js"]
```

`CMD` устанавливает **команду по умолчанию** при старте контейнера. Она легко заменяется при запуске — всё, что передаётся после имени образа в `docker run`, полностью заменяет `CMD`:

```bash
docker run my-app:1.0                           # выполняет: node dist/server.js
docker run my-app:1.0 node dist/migrate.js      # CMD заменён — выполняет: node dist/migrate.js
docker run my-app:1.0 /bin/sh                   # CMD заменён — открывает shell
```

### `ENTRYPOINT` — фиксированный исполняемый файл, аргументы добавляются

```dockerfile
ENTRYPOINT ["node"]
CMD ["dist/server.js"]
```

`ENTRYPOINT` устанавливает **фиксированный исполняемый файл**, который всегда запускается. Аргументы, переданные в `docker run`, **добавляются** к `ENTRYPOINT`, а не заменяют его:

```bash
docker run my-app:1.0                    # выполняет: node dist/server.js
docker run my-app:1.0 dist/migrate.js   # выполняет: node dist/migrate.js
                                          # (аргумент добавлен к ENTRYPOINT)
```

Чтобы заменить `ENTRYPOINT` при запуске, нужен флаг `--entrypoint`:

```bash
docker run --entrypoint /bin/sh my-app:1.0   # открывает shell
```

### Практический паттерн комбинирования

Наиболее распространённый паттерн для образов приложений:

```dockerfile
# ENTRYPOINT = фиксированный исполняемый файл
# CMD        = аргумент по умолчанию (легко переопределяется)

ENTRYPOINT ["node"]
CMD ["dist/server.js"]       # по умолчанию: запустить сервер

# Тогда в CI или скриптах:
# docker run my-app:1.0 dist/migrate.js   → запускает миграцию
# docker run my-app:1.0                   → запускает сервер
```

### Exec form vs shell form

И `CMD`, и `ENTRYPOINT` имеют два синтаксиса:

```dockerfile
# Exec form (JSON-массив) — ПРЕДПОЧТИТЕЛЬНО
CMD ["node", "dist/server.js"]

# Shell form (строка) — ИЗБЕГАТЬ для CMD/ENTRYPOINT
CMD node dist/server.js
```

**Всегда используйте exec form для `CMD` и `ENTRYPOINT`.** Shell form оборачивает команду в `/bin/sh -c "..."`, что означает: ваше приложение запускается как дочерний процесс `sh`. Это создаёт две проблемы:
1. Процесс не получает сигналы ОС (`SIGTERM`) напрямую — `sh` получает их, и может не передавать дальше. Это ломает graceful shutdown (корректное завершение).
2. Проблема PID 1: в контейнере у процесса с PID 1 есть особые обязанности (поглощение зомби-процессов). Если ваше приложение работает как дочерний процесс `sh`, `sh` является PID 1 — и он не обрабатывает зомби-процессы корректно.

## Слои образа и кэш сборки

Каждая инструкция `RUN`, `COPY`, `ADD` и `FROM` в Dockerfile создаёт новый **слой** (layer) в образе. Слои стекируются — каждый записывает только diff (изменения) относительно слоя под ним.

```txt
Образ "my-app:1.0"
  Слой 5: COPY . .  +  RUN npm run build        ← меняется часто
  Слой 4: RUN npm ci --only=production           ← меняется при изменении package-lock.json
  Слой 3: COPY package.json package-lock.json ./ ← меняется при изменении зависимостей
  Слой 2: WORKDIR /app                           ← стабильный
  Слой 1: FROM node:20-alpine                    ← стабильный
```

**Кэш сборки** — Docker кэширует каждый слой. При пересборке образа Docker повторно использует кэшированные слои сверху вниз, останавливаясь на первом изменившемся слое (или слое, входные данные которого изменились):

```txt
Если вы изменили исходный файл (src/server.ts):
  Слой 1 (FROM)             — cache HIT (не изменился)
  Слой 2 (WORKDIR)          — cache HIT
  Слой 3 (COPY package.json)— cache HIT (package.json не менялся)
  Слой 4 (RUN npm ci)       — cache HIT (package-lock.json не менялся)
  Слой 5 (COPY . .)         — cache MISS (исходники изменились) → пересборка отсюда
```

Вот почему **порядок имеет значение в Dockerfile**: кладите то, что меняется реже всего, наверх, а то, что меняется чаще всего — вниз.

```dockerfile
# ✅ Правильный порядок — установка зависимостей кэшируется, пока не меняется package-lock.json
FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json ./    # сначала копируем только lockfile
RUN npm ci                                 # кэшируется, пока lockfile не изменился
COPY . .                                   # исходники (меняются часто) — копируем после
RUN npm run build

# ❌ Неправильный порядок — npm ci перезапускается при каждом изменении исходников
FROM node:20-alpine
WORKDIR /app
COPY . .          # исходники и package.json скопированы вместе
RUN npm ci        # кэш сбрасывается при любом изменении исходных файлов
RUN npm run build
```

## Multi-stage builds (многоэтапная сборка)

**Multi-stage build** использует несколько инструкций `FROM` в одном Dockerfile. Каждый `FROM` начинает новый этап сборки. Вы можете копировать файлы из одного этапа в другой — оставляя инструменты сборки позади.

Это основная техника для уменьшения размера production-образов:

```dockerfile
# syntax=docker/dockerfile:1

# ── Этап 1: builder (сборщик) ─────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci                              # устанавливает ВСЕ зависимости (включая devDependencies)

COPY . .
RUN npm run build                       # создаёт dist/

# ── Этап 2: production-образ ──────────────────────────────────────
FROM node:20-alpine AS production

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev                   # устанавливает ТОЛЬКО production-зависимости

COPY --from=builder /app/dist ./dist    # копируем только скомпилированный вывод из builder

EXPOSE 3000
CMD ["node", "dist/server.js"]
```

Что остаётся в этапе `builder` (не попадает в финальный образ):
- TypeScript-компилятор (`tsc`)
- Все dev-зависимости (тестовые фреймворки, инструменты сборки)
- Исходные TypeScript-файлы
- Инструменты сборки (webpack, vite, esbuild)

Финальный образ содержит только: Node.js runtime + production npm-пакеты + скомпилированный JS-вывод.

```txt
Без multi-stage:    ~400 МБ (все инструменты + devDeps + исходники)
С multi-stage:       ~80 МБ (только runtime + prodDeps + скомпилированный вывод)
```

Multi-stage builds можно также использовать для запуска тестов в CI без загрязнения production-образа:

```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM deps AS test
COPY . .
RUN npm test          # если упадёт — вся сборка упадёт; тесты — часть build-процесса

FROM deps AS builder
COPY . .
RUN npm run build

FROM node:20-alpine AS production
# ... (как выше)
```

## `.dockerignore`

`.dockerignore` работает точно так же, как `.gitignore`, но для build context Docker. Он говорит Docker, какие файлы исключить из build context (директории, отправляемой демону Docker при выполнении `docker build`).

```txt
# .dockerignore
node_modules/          # никогда не копировать node_modules — всегда устанавливать заново внутри образа
.git/                  # история git не нужна в образе
.env                   # НИКОГДА не включать .env — может содержать секреты
dist/                  # будет пересобрано внутри образа
coverage/
*.log
.DS_Store
README.md
```

Почему это важно:
1. **Скорость**: без `.dockerignore` вся директория `node_modules/` (потенциально сотни МБ) передаётся демону Docker при каждом `docker build`. Это медленно и тратит трафик в CI.
2. **Безопасность**: файлы `.env`, локальные учётные данные и приватные ключи никогда не должны попадать в Docker-образ. Даже если за `COPY . .` следует `RUN rm .env`, файл `.env` существует в промежуточном слое и может быть извлечён из образа с помощью `docker history`.
3. **Корректность**: `COPY . .` без `.dockerignore` копирует `node_modules/` с хоста в образ, а они могут быть собраны под другую ОС (macOS-нативные аддоны не запустятся на Linux).

## Non-root пользователь и rootless-контейнеры

По умолчанию процессы внутри Docker-контейнера работают от имени `root` (UID 0). Это риск безопасности: если злоумышленник использует уязвимость в приложении и выходит за пределы контейнера, он делает это с правами root — получая максимальные привилегии на хосте.

**Non-root user** означает явное создание пользователя внутри контейнера и переключение на него:

```dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY --from=builder /app/dist ./dist

# Создать non-root пользователя и группу
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

# Изменить владельца директории приложения на нового пользователя
RUN chown -R appuser:appgroup /app

# Переключиться на non-root пользователя
USER appuser

EXPOSE 3000
CMD ["node", "dist/server.js"]
```

В базовом образе `node:20-alpine` уже есть пользователь `node` (UID 1000). Его можно просто использовать:

```dockerfile
# Более простой подход с использованием встроенного пользователя node
FROM node:20-alpine
WORKDIR /app
COPY --chown=node:node package.json package-lock.json ./
RUN npm ci --omit=dev
COPY --chown=node:node --from=builder /app/dist ./dist
USER node                   # переключиться на встроенного пользователя node
CMD ["node", "dist/server.js"]
```

**Rootless containers** (бескорневые контейнеры) — более широкая концепция: запуск всего демона Docker от имени непривилегированного пользователя на хосте — так что даже если контейнер выйдет за свои пределы, он выйдет в пространство пользователя непривилегированного демона, а не root. Это отдельная конфигурация установки Docker, не Dockerfile.

```txt
На практике для fullstack-разработчика:
  → Добавляйте USER <non-root> во все production Dockerfile
  → Используйте --chown в COPY для установки правильного владельца файлов
  → Не используйте --privileged в docker run (даёт полный доступ к хосту)
  → Не монтируйте /var/run/docker.sock без крайней необходимости
     (доступ к Docker socket = root-эквивалентный доступ к хосту)
```

## Основы Docker Compose

**Docker Compose** — инструмент для определения и запуска многоконтейнерных приложений. Вместо нескольких команд `docker run` с десятками флагов вы описываете весь стек приложения в файле `docker-compose.yml` и запускаете его одной командой.

```yaml
# docker-compose.yml
version: '3.9'

services:
  app:
    build: .                          # собрать образ из Dockerfile в текущей директории
    ports:
      - '3000:3000'
    environment:
      NODE_ENV: development
      DATABASE_URL: postgres://postgres:password@db:5432/myapp
    depends_on:
      db:
        condition: service_healthy    # ждать пока db пройдёт health check
    volumes:
      - ./src:/app/src               # монтировать исходники для hot-reload в development

  db:
    image: postgres:16-alpine         # использовать официальный образ, сборка не нужна
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
      POSTGRES_DB: myapp
    volumes:
      - postgres-data:/var/lib/postgresql/data   # named volume: сохраняется между перезапусками
    healthcheck:
      test: ['CMD-SHELL', 'pg_isready -U postgres']
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - '6379:6379'

volumes:
  postgres-data:     # объявить named volumes здесь
```

```bash
# Запустить все сервисы (собрать образы при необходимости)
docker compose up --build

# Запустить в detached mode (фоне)
docker compose up -d

# Остановить все сервисы и удалить контейнеры
docker compose down

# Остановить и также удалить volumes (ВНИМАНИЕ: уничтожает данные БД)
docker compose down -v

# Просмотреть логи
docker compose logs -f app

# Запустить одноразовую команду в сервисе
docker compose exec app sh
docker compose run --rm app node dist/migrate.js
```

Ключевые концепции Compose:

```txt
services    → каждый ключ — именованный контейнер с его конфигурацией
build       → путь к Dockerfile или объект конфигурации сборки
image       → использовать готовый образ вместо сборки
ports       → маппинг портов хост:контейнер
environment → переменные окружения для контейнера
volumes     → монтировать пути хоста или named volumes
depends_on  → определить порядок запуска зависимостей между сервисами
networks    → по умолчанию Compose создаёт одну сеть и все сервисы к ней подключаются,
              поэтому "db" в DATABASE_URL разрешается в IP контейнера сервиса db
```

### Старший нюанс: `depends_on` не означает "готово"

`depends_on: db` ждёт только *запуска контейнера* db — не того, что PostgreSQL *внутри контейнера* готов принимать соединения. Ваше приложение может попытаться подключиться до того, как база данных слушает.

Решения:
- Используйте `condition: service_healthy` с `healthcheck` (показано выше)
- Напишите логику retry в коде запуска приложения
- Используйте wait-скрипт (`wait-for-it.sh` или аналогичный)

## Полный пример production Dockerfile

```dockerfile
# syntax=docker/dockerfile:1

# ── Этап 1: Установка зависимостей ───────────────────────────────
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ── Этап 2: Сборка ───────────────────────────────────────────────
FROM deps AS builder
COPY . .
RUN npm run build

# ── Этап 3: Production-образ ─────────────────────────────────────
FROM node:20-alpine AS production

# Установить production-окружение
ENV NODE_ENV=production

WORKDIR /app

# Установить только production-зависимости
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && \
    npm cache clean --force        # удалить кэш npm для уменьшения размера слоя

# Скопировать скомпилированный вывод из builder
COPY --from=builder /app/dist ./dist

# Использовать встроенного non-root пользователя node
RUN chown -R node:node /app
USER node

EXPOSE 3000

# Exec form — гарантирует, что SIGTERM приходит напрямую к процессу node
CMD ["node", "dist/server.js"]
```

## Типичные ошибки на интервью

- **"Image и container — одно и то же"** — образ это read-only схема; контейнер — запущенный экземпляр этого образа с записываемым слоем. Из одного образа одновременно могут работать много контейнеров.

- **Использование shell form для `CMD`** — `CMD node server.js` оборачивает команду в `/bin/sh -c`, делая `sh` процессом, получающим `SIGTERM` при `docker stop`. Node никогда не видит сигнал и принудительно завершается после grace period. Всегда используйте exec form: `CMD ["node", "server.js"]`.

- **Не понимать разницу между `CMD` и `ENTRYPOINT`** — очень распространённый вопрос на собеседованиях. `CMD` предоставляет значения по умолчанию, которые *заменяются* при передаче аргументов в `docker run`; `ENTRYPOINT` — фиксированный исполняемый файл, который *получает* эти аргументы. Они созданы для совместной работы.

- **Копирование `node_modules` в образ** — если `.dockerignore` не исключает `node_modules/`, `COPY . .` копирует их с машины сборки в образ. Нативные аддоны, собранные под macOS, упадут на Linux. Всегда устанавливайте заново внутри контейнера.

- **Не использовать multi-stage builds для production-образов** — production-образ с TypeScript-компилятором, тестовыми фреймворками и исходными `.ts`-файлами — красный флаг на собеседовании. Multi-stage builds — ожидаемая практика.

- **Помещать секреты в `ENV` в Dockerfile** — `ENV DATABASE_URL=postgres://admin:secret@...` навсегда запекает секрет во все слои образа. Даже если потом перезаписать его командой `RUN`, он восстановим из более ранних слоёв через `docker history`. Секреты должны передаваться во время выполнения (`docker run -e`) или через secrets manager, а не запекаться в образ.

- **Считать, что `depends_on` означает готовность сервиса** — `depends_on` ждёт только запуска процесса контейнера, но не того, что сервис внутри принимает соединения. PostgreSQL, Redis или любой другой сервис требует health check для корректной работы `condition: service_healthy`.

- **Запускать production-контейнеры от root** — отсутствие `USER` в Dockerfile означает запуск процесса от root внутри контейнера. Интервьюер, знакомый с Docker, заметит это немедленно. Всегда добавляйте инструкцию `USER` в production-образы.
