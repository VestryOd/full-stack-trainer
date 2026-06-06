# CommonJS vs ES Modules

## The History of Modules in JavaScript

When JavaScript first appeared:

```txt
no modules existed at all
```

---

In the browser, people used:

```html
<script src="a.js"></script>
<script src="b.js"></script>
```

---

Everything ended up in:

```txt
Global Scope
```

---

Which led to name conflicts.

---

# The Emergence of CommonJS

Node.js appeared before the official JavaScript module standard existed.

---

So Node invented its own system:

```txt
CommonJS
```

---

# CommonJS Syntax

Import:

```js
const express = require('express');
```

---

Export:

```js
module.exports = {
  foo,
};
```

---

or

```js
exports.foo = foo;
```

---

# How require() Works

A very popular interview question.

---

When Node sees:

```js
require('./user');
```

it:

1. Finds the file.
2. Executes it.
3. Caches the result.
4. Returns exports.

---

# Module Cache

Important to understand.

---

First call:

```js
require('./config');
```

---

The file is executed.

---

Second call:

```js
require('./config');
```

---

Taken from cache.

---

No re-execution.

---

# Example

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

Will print:

```txt
loaded
```

only once.

---

# Drawbacks of CommonJS

The main problem:

```txt
synchronous module loading
```

---

The module must be loaded before execution continues.

---

# The Emergence of ES Modules

Later, the JavaScript standard gained:

```txt
ES Modules (ESM)
```

---

This is the official ECMAScript standard.

---

# ESM Syntax

Import:

```js
import express from 'express';
```

---

Export:

```js
export function foo() {}
```

---

or

```js
export default foo;
```

---

# Named Export

```js
export const name = 'Max';
```

---

Import:

```js
import { name } from './user';
```

---

# Default Export

```js
export default UserService;
```

---

Import:

```js
import UserService from './user';
```

---

# The Main Difference

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

# Static Analysis

A very popular interview question.

---

ESM imports are resolved:

```txt
before code execution
```

---

Therefore:

```txt
Tree Shaking
Bundling
Static Analysis
```

work better.

---

# Example

Bad for analysis:

```js
const moduleName = getName();

require(moduleName);
```

---

Impossible to know in advance what will be loaded.

---

ESM:

```js
import user from './user';
```

---

Can be analyzed in advance.

---

# Tree Shaking

A very important topic.

---

If:

```js
import { foo } from './utils';
```

---

The bundler can remove:

```txt
bar
baz
unused code
```

---

This reduces the bundle size.

---

# Dynamic Import

ESM supports:

```js
const module =
  await import('./module.js');
```

---

This is the equivalent of lazy loading.

---

# Top-Level Await

Only supported in ESM.

---

```js
const users =
  await getUsers();
```

---

Without an additional wrapper function.

---

# How to Enable ESM in Node

package.json:

```json
{
  "type": "module"
}
```

---

Or use the:

```txt
.mjs
```

file extension.

---

# The __dirname Problem

A popular interview question.

---

In CommonJS:

```js
__dirname
__filename
```

are available automatically.

---

In ESM:

they are not.

---

You have to use:

```js
import.meta.url
```

---

# Interop

Can you mix CommonJS and ESM?

---

Yes.

---

But complications arise.

---

For example:

```js
import pkg from 'cjs-package';
```

---

Sometimes you need to use:

```js
createRequire()
```

---

# What Is Used Today

In new projects:

```txt
ES Modules
```

---

In older projects:

```txt
CommonJS
```

---

A lot of legacy code still uses require.

---

# Interview Answer

CommonJS is Node.js's historical module system, using require and module.exports. ES Modules is the official ECMAScript standard, using import/export. ESM supports static analysis, tree shaking, dynamic imports, and top-level await, making it the preferred choice for modern projects.
