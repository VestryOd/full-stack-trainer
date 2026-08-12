# Executors: от run-commands до собственного

## Теория

### Лестница выбора

Из главы 03 мы знаем, что executor — это функция, которой Nx отдаёт задачу, а `nx:run-commands` с сахаром `"command"` — самый частый из них. Прежде чем писать свой, честно пройдите лестницу:

```
┌─────────────────────────────────────┬───────────────────────────────────────────┐
│ хватит nx:run-commands              │ нужен кастомный executor                  │
├─────────────────────────────────────┼───────────────────────────────────────────┤
│ обернуть готовый CLI одной командой │ логика: условия, ретраи, вызовы API       │
├─────────────────────────────────────┼───────────────────────────────────────────┤
│ несколько команд подряд/параллельно │ типизированные опции со schema-валидацией │
├─────────────────────────────────────┼───────────────────────────────────────────┤
│ разовый скрипт конкретной репы      │ переиспользование в десятках проектов     │
├─────────────────────────────────────┼───────────────────────────────────────────┤
│ вывод и exit code — достаточно      │ нужен context: граф, root, configuration  │
└─────────────────────────────────────┴───────────────────────────────────────────┘
```

Между колонками есть промежуточная ступень, о которой часто забывают: **скрипт, запущенный через run-commands** (`"command": "tsx tools/scripts/deploy.ts"`). Логика уже в нормальном типизированном файле, но без плагинной обвязки. Для многих задач это оптимум; кастомный executor побеждает его, когда нужны валидируемые опции на каждый проект и доступ к контексту Nx.

### run-commands глубже, чем "command"

Полная форма умеет заметно больше сахара из главы 03:

```json
{
  "executor": "nx:run-commands",
  "options": {
    "commands": [
      "node tools/scripts/prepare.js {projectName}",
      "vite build"
    ],
    "parallel": false,
    "cwd": "{projectRoot}",
    "envFile": ".env.build",
    "forwardAllArgs": true
  }
}
```

- `commands` + `parallel: false` — последовательная цепочка (по умолчанию команды из списка идут параллельно!);
- интерполяция: `{projectRoot}`, `{projectName}`, `{args.имя}` — значения из контекста и CLI-аргументов подставляются в строки;
- `envFile` подгружает переменные (помним из главы 04: если они влияют на артефакт — им место и в inputs);
- `forwardAllArgs` пробрасывает `nx run x:y --флаги` внутрь команды.

Exit code ≠ 0 у любой команды → задача провалена. Для многих сценариев этого контракта достаточно.

### Анатомия кастомного executor-а

Три файла, зеркально генераторам из главы 07: запись в **executors.json** (реестр плагина), **schema.json** (типы и валидация опций) и **impl** — асинхронная функция:

```ts
export default async function myExecutor(
  options: MyExecutorSchema,        // уже провалидированы схемой
  context: ExecutorContext,         // кто я и где я
): Promise<{ success: boolean }> { ... }
```

Контракт результата — объект `{ success }`, а не исключение и не exit code: executor выполняется внутри процесса Nx, и `success: false` — штатный способ сказать "задача провалена" (упавшее исключение тоже провалит задачу, но с некрасивым стектрейсом вместо вашего сообщения).

**ExecutorContext** — то, чего нет у shell-команды: `projectName` (для кого запущена задача), `root` (корень workspace), `projectsConfigurations` (конфигурация всех проектов — фактически project graph), `targetName`/`configurationName`, `isVerbose`. Один executor, повешенный на десять проектов, ведёт себя по-разному, потому что читает контекст, — в этом его сила против захардкоженного скрипта.

Для долгоживущих задач (dev-серверы) существует вторая форма контракта — async iterable, который yield-ит события вместо одного результата; так устроены serve-executors, и так Nx понимает, что задача "работает", а не "зависла".

> **Версии.** В старых репах executors называются **builders** — наследие Angular devkit (`"builder": "@angular-devkit/build-angular:browser"` в angular.json). Контракт тот же, слово другое. А `nx:run-commands` до ребрендинга жил как `@nrwl/workspace:run-commands` — встретите в непромигрированных конфигах.

### Навык: что вообще запускается

Полная цепочка дебага любого target-а (собираем главы 01, 03 и эту):

1. `nx show project X` — итоговая конфигурация: executor или command, опции после всех слоёв (inferred → targetDefaults → project.json).
2. Если executor кастомный: `node_modules/<пакет>/executors.json` (для локального плагина — `tools/workspace-plugin/executors.json`) → путь к impl → читать код.
3. `nx run X:target --verbose` — полный стектрейс вместо краткой ошибки.

Это закрывает вопрос "почему деплой в нашей репе делает *это*" за минуты — без археологии по вики и опросов старожилов.

## В рабочем монорепо

- `find . -name executors.json -not -path '*/node_modules/*'` — есть ли в репе кастомные executors; их impl — фактическая документация того, как у команды устроены деплой, кодоген, миграции БД.
- `grep -rn '"executor"' --include=project.json apps libs | grep -v 'nx:run-commands' | grep -v '@nx/'` — какие проекты используют самописные executors (и старые `@nrwl/`-алиасы заодно).
- В выводе `nx show project X` посмотрите на опции с фигурными скобками: `{projectRoot}`, `{args.*}` — интерполяция объясняет, откуда в командах "магические" значения.
- Задача падает непонятно — `nx run X:y --verbose` до чтения кода: часто хватает полного стектрейса.
- Ищете, где живёт логика деплоя: сначала `nx show project <app>` (target deploy), потом impl по цепочке из теории — а не поиском "deploy" по всей репе.

## Что добавляем в проект

Кастомный executor `deploy` в нашем workspace-plugin: деплой-заглушка, публикующая собранный артефакт в локальную "CDN"-папку. В главах 10–11 именно так мы будем изображать независимый деплой каждого remote-микрофронтенда.

## Практическое задание

**Вход:** workspace после главы 07 (локальный плагин с генератором feature-lib).

**Задача:**

1. Сгенерировать заготовку executor-а `deploy` в workspace-plugin.
2. Реализовать контракт:
   - **Опции (schema):** `destination` (строка, default `".deploy"`), `clean` (boolean, default `true`);
   - **Логика:** найти артефакт проекта (`dist/<projectRoot>` — путь вычислить из context, не хардкодить), при отсутствии — `success: false` с внятной подсказкой "сначала nx build"; при `clean` — очистить целевую папку; скопировать артефакт в `<destination>/<projectName>`; напечатать псевдо-URL вида `https://cdn.mini-shop.local/<projectName>/`;
   - **Результат:** `{ success: true }` только если копирование состоялось.
3. Повесить target `deploy` на shell: executor из плагина, `dependsOn: ["build"]`, без кеша.
4. Проверить сценарии: деплой без сборки (артефакта нет → success:false); `nx deploy shell` (build подтянулся по dependsOn, из кеша — если не менялся); повторный deploy (build hit, deploy выполнился заново).
5. Добавить `.deploy/` в .gitignore.

**Edge cases на подумать:**

- Почему `dependsOn: ["build"]` (без `^`), а не `["^build"]`?
- Что случится при `nx run-many -t deploy` на несколько проектов с общей `destination` без подпапок по имени проекта?
- Почему executor возвращает `success: false`, а не бросает `throw new Error(...)`?

## Разбор решения

Шаги 1–2 — заготовка и реализация:

```bash
npx nx g @nx/plugin:executor deploy \
  --path=tools/workspace-plugin/src/executors/deploy
```

`schema.json`:

```json
{
  "$schema": "https://json-schema.org/schema",
  "$id": "Deploy",
  "title": "Деплой-заглушка: публикует dist проекта в локальную CDN-папку",
  "type": "object",
  "properties": {
    "destination": {
      "type": "string",
      "description": "Корень локальной 'CDN'",
      "default": ".deploy"
    },
    "clean": {
      "type": "boolean",
      "description": "Очищать целевую папку перед копированием",
      "default": true
    }
  },
  "required": []
}
```

`executor.ts`:

```ts
import { ExecutorContext, logger } from '@nx/devkit';
import { cpSync, existsSync, rmSync } from 'fs';
import * as path from 'path';
import { DeployExecutorSchema } from './schema';

export default async function deployExecutor(
  options: DeployExecutorSchema,
  context: ExecutorContext,
): Promise<{ success: boolean }> {
  const projectName = context.projectName!;
  // Контекст вместо хардкода: executor работает для ЛЮБОГО проекта репы
  const projectRoot = context.projectsConfigurations.projects[projectName].root;
  const distPath = path.join(context.root, 'dist', projectRoot);
  const targetPath = path.join(context.root, options.destination, projectName);

  if (!existsSync(distPath)) {
    logger.error(`Артефакт не найден: ${distPath}`);
    logger.error(`Сначала соберите проект: nx build ${projectName}`);
    return { success: false };
  }

  if (options.clean && existsSync(targetPath)) {
    rmSync(targetPath, { recursive: true });
  }
  cpSync(distPath, targetPath, { recursive: true });

  logger.info(`✅ ${projectName} задеплоен → ${targetPath}`);
  logger.info(`   https://cdn.mini-shop.local/${projectName}/`);
  return { success: true };
}
```

Шаг 3 — target на shell (`apps/shell/project.json`, фрагмент):

```json
{
  "targets": {
    "deploy": {
      "executor": "@mini-shop/workspace-plugin:deploy",
      "dependsOn": ["build"],
      "cache": false
    }
  }
}
```

Ключевые решения:

- `dependsOn: ["build"]` без `^` — деплою нужен собранный **сам проект**, а не его зависимости (их соберёт `^build` самого build). Деплоится всегда свежий артефакт: если исходники не менялись, build закроется кешем за миллисекунды — это ровно та связка "чистые функции кешируем, side effects выполняем", которую мы построили в главе 04.
- `cache: false` у deploy формально избыточен (кеш включается только явным `cache: true`), но задокументированное намерение дешевле часа дебага, если однажды кто-то включит кеш этому имени target-а через targetDefaults.
- Путь артефакта вычисляется из `context.projectsConfigurations` — повесьте этот же target на catalog или checkout-remote (глава 10), и он заработает без единой правки.

Шаг 4 — сценарии:

```bash
rm -rf dist && npx nx run shell:deploy --exclude-task-dependencies 2>/dev/null \
  || npx nx run shell:deploy   # с dependsOn build подтянется сам; без dist вручную:
# >  NX   Артефакт не найден: dist/apps/shell — Сначала соберите проект: nx build shell

npx nx deploy shell
# ✔ nx run shell:build          ← предпосылка из dependsOn
# ✅ shell задеплоен → .deploy/shell
#    https://cdn.mini-shop.local/shell/

npx nx deploy shell
# ✔ nx run shell:build  [local cache]   ← сборка из кеша
# ✅ shell задеплоен → .deploy/shell    ← деплой выполнился заново
```

Ответы на оставшиеся edge cases:

- `run-many -t deploy` с общей папкой без подпапок по проекту — гонка параллельных задач за одни пути: артефакты перезатирают друг друга недетерминированно. Наша схема `<destination>/<projectName>` делает деплои независимыми по построению — тот же принцип изоляции, что и у outputs в кеше.
- `throw` тоже провалит задачу, но пользователь получит стектрейс executor-а вместо диагноза. `success: false` + `logger.error` — это управляемый отказ: вы сами формулируете, что случилось и что делать. Исключения оставьте для действительно неожиданного (баг в самом executor-е).

## Проверь себя

1. Сформулируй контракт executor-а: сигнатура, что означает возврат `{ success: false }`, чем это отличается от ненулевого exit code у run-commands.
2. Что именно даёт `ExecutorContext`, чего принципиально нет у shell-команды? Покажи на примере нашего deploy.
3. Почему у deploy `dependsOn: ["build"]` без `^`, и почему связка "deploy зависит от build + build кешируется" — правильная архитектура, а не лишний запуск?
4. Команда просит "добавить ретраи и Slack-уведомление в деплой". Сейчас это run-commands с bash-строкой на 200 символов. По каким признакам понять, что пора переходить на кастомный executor (или хотя бы на скрипт)?
5. Незнакомая репа, `nx run api:migrate-db` делает что-то страшное. Опиши цепочку файлов, по которой ты за пять минут выяснишь, что именно запускается.

<details>
<summary>Ответы</summary>

1. `async (options, context) => Promise<{ success: boolean }>` (для long-running — async iterable). `success: false` — штатный, управляемый провал: executor сам залогировал причину и вернул вердикт, Nx пометит задачу проваленной (и уронит зависимые). У run-commands аналогичную роль играет exit code процесса — но там диагностика ограничена тем, что напечатала команда; executor формулирует ошибку программно и типизированно.
2. Контекст самосознания задачи: `projectName`, root проекта из `projectsConfigurations` (фактически граф), имя target-а и configuration, verbose-флаг. Shell-команда знает только свой cwd и env. В deploy это позволило вычислить `dist/<projectRoot>` и `<destination>/<projectName>` из контекста — один executor обслуживает любой проект репы без параметров-хардкодов.
3. Без `^`: деплою нужен артефакт самого проекта; зависимости соберёт `^build` этого build. Связка правильная, потому что каждый слой делает своё: dependsOn гарантирует свежесть артефакта (деплой никогда не публикует устаревший dist), кеш гарантирует, что "свежесть" бесплатна при неизменённых исходниках, а `cache: false` на самом deploy гарантирует, что публикация выполняется всегда. Ни один сценарий (изменили код / не меняли / удалили dist) не ломается.
4. Признаки перехода: в строке появились условия и обработка ошибок (`&&`, `||`, `if`); опции передаются позиционно и без валидации; ту же строку копируют во второй-третий проект; при падении никто не может понять, на каком шаге. Первая ступень — вынести в типизированный скрипт (`tsx tools/scripts/deploy.ts`) и звать через run-commands; executor оправдан, когда нужны schema-валидация опций на проект и context (разные проекты — разное поведение).
5. `nx show project api` → target `migrate-db`: executor и итоговые опции. Если executor кастомный — `executors.json` соответствующего пакета/плагина (для локального — в tools/) → поле implementation → открыть файл и прочитать. При запуске — `--verbose` для полного стектрейса. Пять минут, ноль опросов старожилов.

</details>

## Частая ошибка

Разработчик из single-app мира решает задачи "как в package.json": в `commands` у run-commands вырастает bash-простыня — `mkdir -p ... && cp -r ... && curl ... || echo 'failed' && exit 1` — на десять команд с условиями. Она не типизирована, не тестируется, по-разному ведёт себя в bash и zsh, а падение в середине оставляет полудеплой без отката. Порог простой: **как только в команде появилось `&&` с условием или обработка ошибки — это уже программа**, и ей место в файле (скрипт через run-commands) или в executor-е, где отказ — это осмысленный `success: false` с диагнозом, а не обрывок stdout.

Противоположная крайность — executor-мания: кастомный executor на каждую мелочь, где хватило бы `"command": "rimraf dist"`. Каждый executor — это schema, impl, тесты и поддержка при обновлениях Nx; плагин распухает, и через год половина executors дублирует существующие CLI хуже оригинала. Лестница из начала главы — рабочий фильтр: команда → команды → скрипт → executor, и на каждую ступень поднимаются только те задачи, которым тесно на текущей.
