# Full-Stack Trainer — Инструкция по запуску

## Порядок запуска промптов

Каждый промпт — отдельная сессия Claude CLI. Запускай в директории `full-stack-trainer/`.

---

### PROMPT 1 — Scaffold
```bash
cd full-stack-trainer/
claude < PROMPT_1_SCAFFOLD.md
```
**Что получишь:** Next.js проект с конфигом, структурой, пустыми JSON файлами, рабочим `npm run dev`.
**Проверка:** `npm run dev` → localhost:3000 открывается без ошибок.

---

### PROMPT 2 — Content
```bash
claude < PROMPT_2_CONTENT.md
```
**Что получишь:** Все вопросы, задачи, квиз-вопросы в JSON. Проверка и фикс существующих RU статей. EN переводы.
**Проверка:** `node -e "require('./content/questions/javascript.json').length"` → число > 40

⚠️ **Этот промпт самый долгий** — много контента. Если Claude CLI упрётся в лимит, запускай повторно с уточнением: `"Continue from Task C, topicId: nestjs onwards"`

---

### PROMPT 3 — UI
```bash
claude < PROMPT_3_PAGES.md
```
**Что получишь:** Все страницы с полным UI, компоненты, прогресс-трекинг, темизация, локализация.
**Проверка:** `npm run build` → no errors

---

### PROMPT 4 — Deploy
```bash
claude < PROMPT_4_DEPLOY.md
```
**Что получишь:** Netlify конфиг, GitHub Actions, SEO мета-теги, README, финальная проверка.
**Проверка:** Build report без ошибок.

---

## Если что-то пошло не так

### Claude CLI обрезал на середине
Запусти продолжение:
```
Continue the previous task. You were generating content/questions/[topicId].json. Resume from where you stopped.
```

### JSON невалидный
```bash
node -e "JSON.parse(require('fs').readFileSync('content/questions/javascript.json', 'utf8'))"
```
Ошибка покажет строку. Попроси Claude: `Fix the JSON syntax error in content/questions/javascript.json at line N`.

### TypeScript ошибки после Prompt 3
```bash
npx tsc --noEmit 2>&1 | head -50
```
Скопируй вывод и попроси: `Fix these TypeScript errors: [paste]`

### Забыл `generateStaticParams`
```bash
grep -r "generateStaticParams" src/app/ | wc -l
```
Должно быть равно количеству dynamic routes (папок с `[param]`).

---

## Деплой на Netlify

После успешного `npm run build`:

```bash
# 1. Инициализируй git если ещё нет
git init
git add .
git commit -m "feat: full-stack interview trainer"

# 2. Создай репо на GitHub и запуши
git remote add origin https://github.com/VestryOd/full-stack-trainer.git
git push -u origin main

# 3. Netlify:
#    - netlify.com → Add new site → Import from GitHub
#    - Build command: npm run build
#    - Publish directory: out
#    - Deploy!
```

---

## Добавление нового контента в будущем

### Новые вопросы
Открой `content/questions/{topicId}.json`, добавь объект по схеме из `src/types/index.ts`.

### Новая тема теории
1. Создай папку `content/topics/{topicId}/ru/` и `content/topics/{topicId}/en/`
2. Добавь `.md` файлы
3. Добавь топик в `src/constants/topics.ts`
4. Создай `content/questions/{topicId}.json`

### Попросить Claude CLI добавить вопросы
```
Add 10 more senior-level questions about [TOPIC] to content/questions/[topicId].json. 
Follow the existing schema. Include both en and ru fields. 
Append to the existing array, don't overwrite it.
```
