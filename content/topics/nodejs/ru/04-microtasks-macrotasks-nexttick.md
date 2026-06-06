<!-- verified: 2026-06-05, corrections: 0 -->
# Microtasks, Macrotasks и process.nextTick

## Самая любимая тема интервьюеров

Очень часто показывают такой код:

```js
setTimeout(() => {
  console.log('timeout');
}, 0);

Promise.resolve().then(() => {
  console.log('promise');
});

console.log('sync');
```

---

Что выведется?

---

Ответ:

```txt
sync
promise
timeout
```

---

Почему?

---

Потому что существуют разные очереди задач.

---

# Task Queues

В Node есть несколько очередей.

---

Упрощенно:

```txt
nextTick Queue
↓
Microtask Queue
↓
Macrotask Queue
```

---

# Macrotasks

Сюда попадают:

```txt
setTimeout
setInterval
setImmediate
I/O callbacks
```

---

# Microtasks

Сюда попадают:

```txt
Promise.then
Promise.catch
Promise.finally
queueMicrotask
```

---

# Главное правило

После завершения текущего кода:

```txt
Сначала выполняются все Microtasks
Потом Macrotasks
```

---

# Пример

```js
setTimeout(() => {
  console.log('timeout');
});

Promise.resolve().then(() => {
  console.log('promise');
});
```

---

Результат:

```txt
promise
timeout
```

---

# Почему Promise раньше

Promise находится в:

```txt
Microtask Queue
```

---

setTimeout находится в:

```txt
Macrotask Queue
```

---

Microtasks всегда имеют приоритет.

---

# queueMicrotask

Специальный API.

---

```js
queueMicrotask(() => {
  console.log('microtask');
});
```

---

Работает аналогично Promise.then.

---

# process.nextTick

Самая коварная тема.

---

Node имеет отдельную очередь:

```txt
nextTick Queue
```

---

У неё ещё более высокий приоритет.

---

# Пример

```js
process.nextTick(() => {
  console.log('tick');
});

Promise.resolve().then(() => {
  console.log('promise');
});
```

---

Результат:

```txt
tick
promise
```

---

# Почему?

Потому что порядок:

```txt
nextTick
↓
Microtasks
↓
Macrotasks
```

---

# Полный приоритет

```txt
Call Stack
↓
process.nextTick
↓
Promise Microtasks
↓
Timers
↓
I/O
↓
setImmediate
```

---

# Очень популярный вопрос

Что выведет код?

```js
console.log('1');

setTimeout(() => {
  console.log('2');
});

Promise.resolve().then(() => {
  console.log('3');
});

console.log('4');
```

---

Ответ:

```txt
1
4
3
2
```

---

Разбор:

```txt
1 -> sync
4 -> sync
3 -> microtask
2 -> macrotask
```

---

# Более сложный пример

```js
console.log('1');

process.nextTick(() => {
  console.log('2');
});

Promise.resolve().then(() => {
  console.log('3');
});

setTimeout(() => {
  console.log('4');
});

console.log('5');
```

---

Ответ:

```txt
1
5
2
3
4
```

---

Разбор:

```txt
1 sync
5 sync

2 nextTick

3 Promise

4 timeout
```

---

# process.nextTick опасность

Можно случайно заблокировать Event Loop.

---

Плохо:

```js
function loop() {
  process.nextTick(loop);
}

loop();
```

---

Что произойдет?

---

Event Loop никогда не дойдет до остальных очередей.

---

Получим starvation.

---

# setImmediate vs setTimeout

Очень популярный вопрос.

---

```js
setImmediate(...)
```

работает в фазе:

```txt
Check
```

---

```js
setTimeout(...)
```

работает в фазе:

```txt
Timers
```

---

В обычном коде порядок не гарантирован.

---

После I/O обычно первым будет:

```txt
setImmediate
```

---

# Senior Interview Answer

Node.js использует несколько очередей задач. Наивысший приоритет имеет process.nextTick, затем выполняются Promise-based microtasks, после чего Event Loop переходит к macrotasks, таким как setTimeout, setImmediate и I/O callbacks. Именно поэтому Promise.then выполняется раньше setTimeout(0), а process.nextTick раньше Promise.then.