<!-- verified: 2026-06-05, corrections: 0 -->
# CommonJS vs ES Modules

## История модулей в JavaScript

Когда JavaScript появился:

```txt
никаких модулей не существовало
```

---

В браузере использовали:

```html
<script src="a.js"></script>
<script src="b.js"></script>
```

---

Все попадало в:

```txt
Global Scope
```

---

Что приводило к конфликтам имен.

---

# Появление CommonJS

Node.js появился раньше,
чем официальный стандарт модулей JavaScript.

---

Поэтому Node придумал собственную систему:

```txt
CommonJS
```

---

# CommonJS синтаксис

Импорт:

```js
const express = require('express');
```

---

Экспорт:

```js
module.exports = {
  foo,
};
```

---

или

```js
exports.foo = foo;
```

---

# Как работает require()

Очень популярный вопрос.

---

Когда Node видит:

```js
require('./user');
```

он:

1. Находит файл.
2. Выполняет его.
3. Кэширует результат.
4. Возвращает exports.

---

# Module Cache

Важно понимать.

---

Первый вызов:

```js
require('./config');
```

---

Файл выполняется.

---

Второй вызов:

```js
require('./config');
```

---

Берется из кэша.

---

Повторного выполнения нет.

---

# Пример

```js
console.log('loaded');

module.exports = {};
```

---

```js
require('./config');
require('./config');
```

---

Выведет:

```txt
loaded
```

только один раз.

---

# Недостатки CommonJS

Главная проблема:

```txt
синхронная загрузка модулей
```

---

Модуль должен быть загружен
до продолжения выполнения.

---

# Появление ES Modules

Позже стандарт JavaScript получил:

```txt
ES Modules (ESM)
```

---

Это официальный стандарт ECMAScript.

---

# ESM синтаксис

Импорт:

```js
import express from 'express';
```

---

Экспорт:

```js
export function foo() {}
```

---

или

```js
export default foo;
```

---

# Named Export

```js
export const name = 'Max';
```

---

Импорт:

```js
import { name } from './user';
```

---

# Default Export

```js
export default UserService;
```

---

Импорт:

```js
import UserService from './user';
```

---

# Главное отличие

CommonJS:

```txt
module.exports
```

---

ESM:

```txt
export
```

---

# Статический анализ

Очень популярный вопрос.

---

ESM импортируется:

```txt
до выполнения кода
```

---

Поэтому:

```txt
Tree Shaking
Bundling
Static Analysis
```

работают лучше.

---

# Пример

Плохо для анализа:

```js
const moduleName = getName();

require(moduleName);
```

---

Невозможно понять заранее,
что будет загружено.

---

ESM:

```js
import user from './user';
```

---

Можно проанализировать заранее.

---

# Tree Shaking

Очень важная тема.

---

Если:

```js
import { foo } from './utils';
```

---

Bundler может удалить:

```txt
bar
baz
unused code
```

---

Это уменьшает размер bundle.

---

# Dynamic Import

ESM поддерживает:

```js
const module =
  await import('./module.js');
```

---

Это аналог lazy loading.

---

# Top-Level Await

Поддерживается только ESM.

---

```js
const users =
  await getUsers();
```

---

Без дополнительной функции.

---

# Как включить ESM в Node

package.json

```json
{
  "type": "module"
}
```

---

Либо:

```txt
.mjs
```

расширение файла.

---

# __dirname проблема

Очень любят спрашивать.

---

В CommonJS:

```js
__dirname
__filename
```

есть автоматически.

---

В ESM:

их нет.

---

Приходится использовать:

```js
import.meta.url
```

---

# Interop

Можно ли смешивать CommonJS и ESM?

---

Да.

---

Но возникают сложности.

---

Например:

```js
import pkg from 'cjs-package';
```

---

Иногда приходится использовать:

```js
createRequire()
```

---

# Что используется сегодня

В новых проектах:

```txt
ES Modules
```

---

В старых проектах:

```txt
CommonJS
```

---

Очень много legacy кода всё ещё использует require.

---

# Interview Answer

CommonJS — историческая система модулей Node.js, использующая require и module.exports. ES Modules — официальный стандарт ECMAScript, использующий import/export. ESM поддерживает статический анализ, tree shaking, dynamic imports и top-level await, поэтому является предпочтительным выбором для современных проектов.