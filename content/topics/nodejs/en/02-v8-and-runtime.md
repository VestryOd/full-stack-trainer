# V8 and Node.js Runtime

## What is V8

V8 is a JavaScript Engine developed by Google.

---

Used in:

```txt
Chrome
Node.js
Deno
```

---

# What V8 Does

Takes JavaScript code:

```js
const x = 5 + 10;
```

---

And executes it.

---

# Core Responsibilities of V8

- Parsing
- Compilation
- Optimization
- Execution
- Garbage Collection

---

# Parsing

First, V8 reads the source code.

---

From:

```js
const x = 5;
```

it builds:

```txt
AST
(Abstract Syntax Tree)
```

---

Simplified:

```txt
VariableDeclaration
 ├── Identifier(x)
 └── Literal(5)
```

---

# Compilation

Old engines:

```txt
code
↓
interpretation
```

---

Modern V8:

```txt
code
↓
compilation
↓
machine code
```

---

# JIT

Just-In-Time Compilation.

---

Code is compiled during execution.

---

# Ignition

The first execution tier.

---

Simplified:

```txt
JS
↓
Bytecode
```

---

# TurboFan

The optimizing compiler.

---

When V8 sees that a function is called many times:

```js
function add(a,b) {
  return a+b;
}
```

---

It optimizes it.

---

Result:

```txt
Very fast machine code
```

---

# Hidden Classes

A very popular senior interview question.

---

V8 tries to optimize objects.

---

For example:

```js
const user = {
  name: 'Max',
  age: 30
};
```

---

An internal structure is created:

```txt
Hidden Class
```

---

If objects have the same shape:

```js
{name, age}
{name, age}
{name, age}
```

---

V8 works faster.

---

# Why Dynamically Changing Objects Is Bad

Bad:

```js
user.address = 'London';
```

---

The Hidden Class changes.

---

Optimization can break.

---

# Inline Cache

The next level of optimization.

---

V8 remembers:

```txt
where an object's field is located
```

---

And accesses it faster.

---

# What is a Runtime

A very important question.

---

V8 can:

```txt
execute JavaScript
```

---

But V8 cannot:

```txt
read files
open sockets
work with the network
work with the OS
```

---

# What Node Adds

Node adds:

```txt
libuv
fs
http
crypto
timers
streams
process
```

---

Therefore:

```txt
V8
+
Node APIs
+
Libuv
=
Node Runtime
```

---

# Heap and Stack

V8 stores data in memory.

---

Stack:

```txt
Function Calls
Primitive Values
References
```

---

Heap:

```txt
Objects
Arrays
Closures
Functions
```

---

# Garbage Collection

V8 automatically manages memory.

---

The core idea:

```txt
Unreachable objects are removed
```

---

Example:

```js
let user = {
  name: 'Max'
};

user = null;
```

---

The old object becomes unreachable.

GC can now remove it.

---

# A Common Problem

Memory Leak.

---

For example:

```js
const cache = [];

setInterval(() => {
  cache.push(largeObject);
}, 1000);
```

---

Objects are never freed.

Memory keeps growing.

---

# Why V8 Is So Fast

Reasons:

- JIT Compilation
- TurboFan
- Hidden Classes
- Inline Cache
- Optimized GC

---

# Interview Answer

V8 is the JavaScript Engine responsible for parsing, compiling, and executing JavaScript code. It uses JIT compilation, TurboFan optimizations, Hidden Classes, and Inline Cache to achieve high performance. Node.js uses V8 as its execution engine and adds libuv and system APIs on top for working with files, the network, and the operating system.
