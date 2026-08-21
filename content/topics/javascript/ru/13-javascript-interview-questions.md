# JavaScript Advanced — Вопросы для интервью

## Группа 1: Контексты выполнения и область видимости

**Что такое Execution Context и из чего он состоит?**

Execution Context — абстрактный контейнер спецификации ECMAScript. Движок создаёт его при вызове функции или старте скрипта. Полей четыре:

```txt
LexicalEnvironment    — где ищутся let/const
VariableEnvironment   — где живут var и function-декларации
ThisBinding           — значение this
code evaluation state — позиция выполнения (важна для генераторов)
```

Стек контекстов = Call Stack. Наверху всегда текущий контекст (Running Execution Context).

---

**Что такое хойстинг и почему он происходит?**

Хойстинг — следствие двухфазной модели выполнения. В фазе создания (creation phase) движок сканирует код и создаёт привязки до того, как выполнится любая строка. `var` он инициализирует значением `undefined`, а `function`-декларацию — полным объектом функции. Привязки `let`/`const` создаются, но не инициализируются — это и есть Temporal Dead Zone (TDZ). Код не "перемещается", меняется только порядок операций.

---

**В чём разница между `LexicalEnvironment` и `VariableEnvironment`?**

Это два поля одного Execution Context, ссылающиеся на разные Environment Records:

```txt
VariableEnvironment — var и function-декларации; не меняется
                      в пределах функции
LexicalEnvironment  — let/const текущего блока; на каждый
                      блок {} создаётся новый Declarative ER
```

Именно это позволяет `let` быть block-scoped, а `var` — function-scoped внутри одной функции.

---

**Что такое TDZ и почему `let`/`const` в нём находятся?**

Temporal Dead Zone — состояние привязки "создана, но не инициализирована" в Environment Record. В фазе создания блока движок сканирует весь блок и создаёт привязки для `let`/`const` в TDZ с самого начала блока. Любое обращение к ним до строки объявления бросает `ReferenceError`. Следствие: внутри блока `let x` затеняет внешний `x` с самого начала блока, а не с момента объявления.

---

**Как работает scope chain и почему она лексическая, а не динамическая?**

Scope chain — цепочка ссылок `[[OuterEnv]]` между Environment Records. Каждый ER хранит поле `[[OuterEnv]]`, указывающее на ER лексически объемлющей области видимости. При создании функции `[[Environment]]` слот фиксируется на текущем ER — это происходит в момент определения функции, не вызова. Поэтому функция "видит" переменные места определения, а не места вызова — лексическая область видимости.

---

## Группа 2: this и привязка

**Назови четыре правила определения `this` и их приоритет.**

Правил четыре, приоритет — сверху вниз:

```txt
new Fn()           → this = новый объект
fn.call/apply/bind → this = первый аргумент
obj.fn()           → this = объект слева от точки
fn()               → this = globalThis (sloppy) / undefined (strict)
```

Если под вызов подходят сразу два правила, побеждает то, что выше.

---

**Почему у стрелочных функций нет своего `this`?**

Стрелочная функция не создаёт `ThisBinding` в своём Function Environment Record. Обращение к `this` внутри стрелки разрешается по Scope Chain — как обычный идентификатор, находя `this` лексически объемлющего контекста. Именно поэтому `call`/`apply`/`bind` не влияют на `this` стрелки — им просто нечего переопределять.

---

**Что возвращает `bind` и можно ли его переопределить?**

`bind` возвращает **bound function exotic object** с тремя внутренними слотами: `[[BoundTargetFunction]]`, `[[BoundThis]]`, `[[BoundArguments]]`. `[[BoundThis]]` нельзя переопределить через `call`/`apply` или повторный `bind` — он зафиксирован навсегда. Единственное исключение: `new BoundFn()` — при `new` алгоритм `[[Construct]]` игнорирует `[[BoundThis]]` и создаёт новый объект.

---

**Почему `obj.method` теряет `this` при передаче как callback?**

При `const fn = obj.method` извлекается только сама функция — implicit binding `this = obj` существовал только в синтаксисе `obj.method()`. Функция не хранит "память" о связи с объектом. При последующем вызове `fn()` применяется default binding: `this = undefined` (strict) или `globalThis` (sloppy). Решение: `fn.bind(obj)`, обёртка `() => obj.method()`, или class field с arrow function.

---

**Что такое `[[Construct]]` алгоритм при `new Fn()`?**

При вызове `new Fn()` движок выполняет три шага:

```txt
1. obj = Object.create(Fn.prototype)
2. вызвать Fn с this = obj
3. если Fn вернул объект → вернуть его, иначе вернуть obj
```

Именно поэтому `new Fn()` с `return { x: 1 }` вернёт `{ x: 1 }`, а не `obj`. При `new BoundFn()` `[[BoundThis]]` игнорируется и `obj` создаётся как обычно.

---

## Группа 3: Замыкания

**Что такое замыкание на уровне движка?**

Замыкание = функция + ссылка на Environment Record, в котором она была создана (`[[Environment]]` внутренний слот). Это не копия переменных, а живая ссылка: изменение переменной в ER видно всем функциям, замкнутым на него. Каждая функция в JS является замыканием — даже функция верхнего уровня замыкается на Global ER.

---

**Почему `var` в цикле с `setTimeout` печатает одно значение?**

Все callbacks замкнуты на один и тот же ER (функции или глобальный), в котором `var i` — единственная переменная. К моменту выполнения callbacks, то есть после синхронного кода, цикл завершён и `i` равно финальному значению. Вариант с `let i` это исправляет. Спецификация предписывает создавать новый LexicalEnvironment на каждой итерации, со своей копией `i`, поэтому каждый callback замкнут на уникальный `i`.

---

**Что V8 реально удерживает в памяти через замыкание?**

V8 создаёт **Context object** для каждого ER, на который ссылается хотя бы одна живая функция. Если несколько функций замкнуты на один ER, V8 создаёт один общий Context — удерживающий все переменные, используемые хотя бы одной из них. Это значит: функция, использующая только `small`, может случайно удерживать `huge`, если они созданы в одном scope вместе с другой функцией, использующей `huge`.

---

**В чём главное преимущество фабричных функций перед классами для инкапсуляции?**

Фабричная функция создаёт настоящую приватность через замыкание: внутренние переменные физически недоступны снаружи модуля. Класс с `#`-полями (ES2022) тоже даёт true privacy на уровне движка, но каждый метод в фабричной функции — отдельный объект (нет prototype-цепочки). Для 1-2 экземпляров разница несущественна; для тысяч — класс эффективнее по памяти, т.к. методы в prototype.

---

## Группа 4: Прототипы и наследование

**Объясни разницу между `[[Prototype]]`, `__proto__` и `prototype`.**

Три разные вещи с обманчиво похожими именами:

```txt
[[Prototype]] — внутренний слот любого объекта → его прототип
__proto__     — устаревший аксессор на Object.prototype, читает
                и пишет [[Prototype]] (Annex B, только браузеры)
prototype     — обычное свойство Function-объектов; становится
                [[Prototype]] объектов, созданных через new Fn()
```

Правильный способ читать `[[Prototype]]` — `Object.getPrototypeOf(obj)`.

---

**Что делает `class` под капотом? Чем отличается от ручного конструктора?**

`class` — синтаксический сахар над прототипным механизмом. От ручного конструктора его отличают три вещи:

```txt
1. методы класса non-enumerable — как если бы их задали через
   Object.defineProperty с enumerable: false; ручные
   prototype.method = fn остаются enumerable
2. вызов без new бросает TypeError, тогда как функция-конструктор
   просто выполняется как обычный вызов
3. extends настраивает две цепочки, а не одну:
     Derived.prototype[[Prototype]] = Base.prototype  (экземпляры)
     Derived[[Prototype]] = Base                      (статика)
```

---

**Как работает `instanceof` и когда он даёт неверный результат?**

`instanceof` проверяет, есть ли `Fn.prototype` в `[[Prototype]]`-цепочке объекта (или вызывает `Symbol.hasInstance`). Неверный результат: если `Fn.prototype` заменить после создания объекта — `obj instanceof Fn` вернёт `false`, т.к. `obj[[Prototype]]` указывает на старый объект. Также ломается при объектах из разных realm (разные `Array` в iframe).

---

**Что произойдёт при присваивании свойства, если в прототипе есть setter?**

Если в `[[Prototype]]`-цепочке есть setter для свойства `x`, то `obj.x = val` вызывает setter с `this = obj` — собственное свойство `obj.x` не создаётся. Это неочевидно: многие ожидают, что присваивание всегда создаёт собственное свойство. `Object.defineProperty(obj, 'x', { value: val })` обходит setter и создаёт собственное свойство.

---

**Зачем восстанавливать `constructor` при ручной настройке прототипной цепочки?**

`Derived.prototype = Object.create(Base.prototype)` заменяет весь объект `prototype`, затирая исходный `Derived.prototype.constructor = Derived`. После этого `new Derived().constructor === Base` — что ломает рефлексию и паттерны, зависящие от `.constructor` (например, `obj.constructor()` для создания новых экземпляров того же типа). Восстановление: `Derived.prototype.constructor = Derived`.

---

## Группа 5: Event Loop

**Опиши полный алгоритм браузерного Event Loop.**

Одна итерация Event Loop:

```txt
1. взять одну задачу из Task Queue
2. выполнить её до конца (run-to-completion)
3. полностью дренировать Microtask Queue, включая
   микрозадачи, добавленные по ходу
4. rendering opportunity (rAF → style → layout → paint)
5. вернуться к шагу 1
```

Критично: Microtask Queue дренируется полностью — не одна микрозадача, а все до последней.

---

**Почему `Promise.then` всегда асинхронный, даже для уже resolved Promise?**

Спецификация требует: реакция на Promise (`.then` callback) всегда помещается в Microtask Queue, никогда не вызывается синхронно. Это гарантирует предсказуемый порядок: синхронный код после `.then()` всегда выполняется раньше callback, независимо от состояния Promise. Без этой гарантии порядок был бы непредсказуем в зависимости от времени resolve.

---

**В чём разница между `process.nextTick`, `queueMicrotask` и `Promise.then` в Node.js?**

В Node.js Microtask Queue двухуровневая. Сначала полностью дренируется `nextTick Queue` (`process.nextTick`), затем — Microtask Queue (`Promise.then`, `queueMicrotask`). Среди микрозадач наивысший приоритет у `process.nextTick`: исторически это API предшествовало Promise. Остальные две попадают в одну очередь, в порядке FIFO (first in, first out). Рекурсивный `process.nextTick` блокирует Event Loop.

---

**Как рендеринг соотносится с Event Loop в браузере?**

Рендеринг (layout, paint) происходит между задачами, **после** полного дренирования Microtask Queue. С точки зрения рендеринга, задача + все её микрозадачи — атомарный блок. Промежуточные визуальные состояния, создаваемые через Promise.then, пользователь не увидит — рендер произойдёт только после дренирования всей очереди. `requestAnimationFrame` выполняется непосредственно перед рендером, после последней микрозадачи.

---

**Что произойдёт, если внутри `.then` создавать бесконечную цепочку Promise?**

Бесконечная цепочка микрозадач заблокирует Event Loop навсегда: Microtask Queue дренируется до пуста, а каждая новая микрозадача добавляет следующую — цикл никогда не завершается. Task Queue никогда не получит управление. В браузере страница зависнет (нет рендера, нет обработки событий), в Node.js — процесс заблокируется. `Promise.resolve().then(function loop() { return Promise.resolve().then(loop); })` — демонстрация.

---

**Чем `setTimeout(fn, 0)` отличается от `queueMicrotask(fn)`?**

`setTimeout(fn, 0)` помещает `fn` в Task Queue как макрозадачу. Она выполнится в следующей итерации Event Loop, после всех текущих микрозадач. Вызов `queueMicrotask(fn)` помещает `fn` в Microtask Queue. Такая задача выполнится в конце текущей задачи, до следующей макрозадачи и до рендера. Разница критична: микрозадача выполняется раньше и "видит" состояние до рендера.

---

## Группа 6: Асинхронные паттерны

**В чём структурная (не синтаксическая) проблема callback-подхода?**

Главная проблема — инверсия управления: при передаче callback вы отдаёте контроль вызываемой функции. Нет гарантий: callback вызовется ровно один раз, не синхронно, не с err и data одновременно, не проглотит exception. Кроме IoC: нельзя вернуть значение из callback, параллельные операции требуют ручных счётчиков, обработка ошибок дублируется на каждом уровне, код читается снаружи внутрь.

---

**Что происходит с Promise при `resolve(anotherPromise)`?**

Если в `resolve(value)` передать thenable (объект с `.then`), запускается Promise Resolution Procedure: новый Promise "следует" за переданным thenable, подписываясь на его `.then`. Это позволяет chaining работать с любым thenable, не только с нативным Promise. Если передать уже resolved Promise — новый Promise принимает его значение асинхронно (через микрозадачу).

---

**Во что `async/await` концептуально компилируется?**

`async function` всегда возвращает Promise. Каждый `await expr` концептуально = `expr.then(continuation)` — всё, что после `await`, становится callback. `try/catch` вокруг `await` = `.catch()`. Каждый `await` добавляет минимум одну микрозадачу, поэтому несколько sequential `await` в одной async-функции перемежаются с микрозадачами других функций.

---

**Чем отличается `Promise.race` от `Promise.any`?**

`Promise.race` завершается, как только **первый** Promise settled (fulfilled или rejected). `Promise.any` завершается, как только **первый** Promise fulfilled, а реджектится только если все rejected — с `AggregateError`, содержащим все reasons. Вариант `race` с немедленно rejecting Promise реджектится сразу, а `any` продолжает ждать остальных.

---

**Что такое `Promise.allSettled` и когда использовать вместо `Promise.all`?**

`Promise.allSettled` всегда resolves (никогда не rejects) — возвращает массив `{ status: 'fulfilled', value } | { status: 'rejected', reason }` для каждого входного Promise. Использовать когда нужны все результаты независимо от частичных ошибок (например, загрузить несколько секций дашборда — показать что успело). `Promise.all` — когда нужны все или ничего.

---

**Классическая ошибка `await` в цикле — что происходит и как исправить?**

`for (const id of ids) { await fetchItem(id); }` — каждый запрос ждёт предыдущего, операции выполняются последовательно: общее время = сумма всех времён. Исправление: `Promise.all(ids.map(id => fetchItem(id)))` — все запросы запускаются одновременно, общее время ≈ максимальному. Когда нужна последовательность (например, rate limiting) — намеренно оставляем `await` в цикле.

---

## Группа 7: Генераторы и итераторы

**Что такое Iterator Protocol? Реализуй вручную.**

Iterable — объект с `[Symbol.iterator]()` методом, возвращающим Iterator. Iterator — объект с `next()` методом, возвращающим `{ value, done }`. `done: false` — есть значение, `done: true` — итерация завершена. Пример: `{ [Symbol.iterator]() { return this; }, next() { return done ? { value: undefined, done: true } : { value: current++, done: false }; } }`.

---

**Чем генераторная функция отличается от обычной при вызове?**

Вызов `gen()` не выполняет код — создаёт объект-генератор в состоянии `suspendedStart` и возвращает его. Код выполняется только при первом `gen.next()`. Это принципиальное отличие: `function* g() { console.log('hi'); }; g();` — ничего не выводит. Генератор одновременно Iterator и Iterable: `gen[Symbol.iterator]() === gen` — true.

---

**Что передаётся в первый `next(value)` генератора?**

Значение первого `next(value)` **игнорируется**. Ему некуда попасть: нет предшествующего `yield`, который мог бы его принять. Первый `next()` только запускает генератор до первого `yield`. Со второго `next(value)` значение `value` становится результатом предыдущего `yield`. В `const x = yield 'prompt';` переменная `x` получит то, что передали в следующий `next()`.

---

**Что делает `yield*` и что возвращает?**

`yield*` делегирует итерацию другому iterable: поочерёдно выдаёт все его значения. Значение выражения `yield* inner()` = значение `return` внутреннего генератора (финальный `IteratorResult.value` при `done: true`). Отметим, что `yield*` работает с любым iterable (массив, строка, Set), не только с генераторами.

---

**Для чего нужны async generators и как их потреблять?**

`async function*` — асинхронный генератор, умеющий и `await`, и `yield`. Потребляется через `for await...of`. Идеален для paginated API — следующая страница запрашивается только когда потребитель готов — а также для стриминга данных и lazy async pipeline. Отметим, что `for await...of` работает и с синхронными iterables, оборачивая значения в Promise.resolve, но не наоборот.

---

## Группа 8: Proxy, Reflect и Symbol

**В чём разница между `Reflect.get(target, prop, receiver)` и `target[prop]`?**

`target[prop]` при наличии getter в прототипе вызывает getter с `this = target` (объект, где найдено свойство). `Reflect.get(target, prop, receiver)` передаёт `receiver` как `this` в getter. Внутри Proxy-ловушки `get(target, prop, receiver)`, `receiver` = сам proxy — что корректно при наследовании. Использование `target[prop]` вместо `Reflect.get` ломает inherited getters.

---

**Что такое инварианты Proxy и почему они существуют?**

Инварианты — ограничения, которые ловушки Proxy не могут нарушить. Пример: `get` ловушка для non-configurable, non-writable свойства обязана вернуть его реальное значение (TypeError иначе). Цель: гарантировать, что Proxy не может "солгать" об иммутабельных свойствах и сломать основные предположения языка о data integrity. 

---

**Как Vue 3 использует Proxy для реактивности?**

`reactive(obj)` оборачивает объект в Proxy с двумя ловушками:

```txt
get-ловушка → вызывает track(target, prop) при чтении
set-ловушка → вызывает trigger(target, prop) при записи
```

Вызов `track` запоминает, что текущий `activeEffect` зависит от этого свойства. Вызов `trigger` при изменении перезапускает все зависимые effects. Это позволяет автоматически обновлять UI (user interface) при мутации состояния, без явной подписки.

---

**Чем `Symbol.for('key')` отличается от `Symbol('key')`?**

`Symbol('key')` создаёт уникальный символ каждый раз — `Symbol('key') !== Symbol('key')`. `Symbol.for('key')` ищет в глобальном реестре: если символ с таким ключом уже есть — возвращает его, иначе создаёт и регистрирует. `Symbol.for('key') === Symbol.for('key')` — true. Глобальный реестр работает между модулями и realm (iframe, Worker).

---

**Что такое well-known symbols? Приведи три примера с практическим смыслом.**

Well-known symbols — предопределённые символы, через которые можно изменить поведение объекта в стандартных операциях. `Symbol.iterator` — делает объект iterable (for...of, spread). `Symbol.toPrimitive` — управляет приведением типов (hint: 'number'/'string'/'default'). `Symbol.hasInstance` — кастомная логика `instanceof`. `Symbol.toStringTag` — кастомный тег `Object.prototype.toString.call()`.

---

## Группа 9: Управление памятью

**Объясни поколенческий GC в V8 (достаточно для интервью).**

V8 делит кучу на два поколения:

```txt
Young Generation — новые объекты, ~1-8 MB
Old Generation   — долгоживущие объекты
```

Minor GC (Scavenge) работает только с Young. Он копирует живые объекты в новое полупространство (Cheney's algorithm), а мёртвые теряются автоматически. Объекты, пережившие 2 Minor GC, переезжают в Old Generation. Major GC (Mark-Sweep-Compact) обходит весь граф от GC Roots и удаляет недостижимые. Orinoco добавляет инкрементальную и конкурентную маркировку, что снижает stop-the-world паузы.

---

**Что является GC Roots в JavaScript?**

GC Roots — начальные точки маркировки, всегда считающиеся живыми:

```txt
1. глобальные переменные (window, globalThis)
2. стек вызовов — локальные переменные активных функций
3. живые замыкания — Environment Records, на которые
   ссылаются живые функции
4. внутренние ссылки V8
```

Объект достижим, если существует путь от любого GC Root до него.

---

**Зачем нужен `WeakMap` и когда он предпочтителен перед `Map`?**

`WeakMap` держит ключи слабо: если на объект-ключ нет других ссылок, GC может собрать его и автоматически удалит запись из WeakMap. Это предотвращает утечки при кешировании данных, привязанных к объектам: узлам DOM (document object model) или request-объектам. `Map` удерживал бы такие ключи вечно. `WeakMap` не итерируется и не имеет `.size`: спецификация не может гарантировать консистентный снимок слабых ключей.

---

**Что гарантирует `WeakRef` и что нет?**

`WeakRef` хранит слабую ссылку и не препятствует GC. Вызов `.deref()` возвращает объект или `undefined`, если тот уже собран. Три вещи **не гарантированы**:

```txt
- когда объект будет собран
- будет ли он собран вообще (спецификация допускает
  бессмертный объект за WeakRef)
- что deref() вернёт undefined сразу после obj = null
  (GC не детерминирован)
```

Использовать только для оппортунистических кешей, где потеря значения допустима.

---

## Группа 10: Приведение типов и равенство

**Опиши алгоритм Abstract Equality Comparison (`==`) по шагам.**

Алгоритм `x == y`:

```txt
1. одинаковые типы   → Strict Equality
2. null == undefined → true, и наоборот;
                       любой из них с другим → false
3. Number vs String  → ToNumber(String)
4. Boolean           → ToNumber, повторить
5. Object vs String/Number/Symbol
                     → ToPrimitive(Object), повторить
6. иначе             → false
```

Ключевое: `null` равен только `null` и `undefined` — шаг 2 перехватывает до всех остальных.

---

**Почему `typeof null === 'object'` — это признанный баг?**

В оригинальной реализации JS (1995) значения хранились как 32-битные слова, младшие 3 бита — тег типа. Значение `null` представлялось нулевым указателем (0x000), а тег `000` означает object. Это баг, который хотели исправить в ECMAScript 2015, но отклонили из-за обратной совместимости. Корректная проверка на `null`: только `x === null`.

---

**В чём разница между `Object.is`, `===` и `==`?**

`==` — Abstract Equality с приведением типов. `===` — Strict Equality без приведения, но с двумя исключениями: `NaN !== NaN` и `+0 === -0`. `Object.is` — SameValue алгоритм: `NaN === NaN` (true), `+0 !== -0` (false). `Object.is` используется в React для сравнения зависимостей и в Map/Set как SameValueZero (вариант, где `+0 === -0`).

---

**Почему `isNaN('hello') === true`, но `Number.isNaN('hello') === false`?**

Глобальный `isNaN(x)` сначала применяет `ToNumber(x)`: `ToNumber('hello') = NaN`, затем проверяет NaN (not a number) → true. `Number.isNaN(x)` — строгая проверка: возвращает `true` только если `typeof x === 'number' && x !== x`. Строка никогда не пройдёт первую проверку → false. Правило: всегда использовать `Number.isNaN` для проверки реального NaN.

---

**Почему `[] == false` равно `true`, но `if ([])` выполняется?**

Это разные алгоритмы. `if ([])` использует `ToBoolean([])`, а объект всегда truthy. Сравнение `[] == false` использует Abstract Equality:

```txt
шаг 4: false → 0         → [] == 0
шаг 5: [] → ToPrimitive  → '' == 0
шаг 3: '' → 0            → 0 == 0 → true
```

С Boolean оператор `==` сначала конвертирует Boolean в Number. ToBoolean он не использует.

---

## Группа 11: Модули

**Что происходит при `exports = { ... }` в CommonJS-модуле?**

`exports` — локальная переменная, изначально указывающая на `module.exports`. Переприсваивание `exports = { ... }` создаёт новый объект, но `module.exports` остаётся исходным пустым объектом. `require()` возвращает `module.exports`, не `exports`. Изменения потеряны. Правильно: `module.exports = { ... }` или добавление свойств через `exports.key = value`.

---

**Что такое live bindings в ESM и как они отличаются от CJS?**

ESM (ECMAScript Modules) экспортирует **привязку** (binding), а CJS (CommonJS) — значение. Привязка — это живая ссылка на переменную в экспортирующем модуле: когда переменная в модуле меняется, импортирующая сторона видит новое значение. Экспорт CJS фиксируется в момент `module.exports`, и для примитивов это копия.

Возьмём `export let count = 0; export function inc() { count++; }`. В ESM `import { count }; inc(); count;` даст 1. В CJS после destructuring `count` остался бы 0.

---

**Как ведут себя циклические зависимости в CJS и ESM — в чём ключевое различие?**

CJS: при цикле B получает **текущий** `module.exports` A в момент circular require — частично заполненный объект (только то, что уже было присвоено). ESM: фаза Linking создаёт все привязки до выполнения (live bindings существуют), но они могут быть в TDZ до инициализации. Решение для ESM-циклов: использовать функции-акцессоры вместо прямых значений — функции обращаются к binding позже.

---

**Может ли `require()` загрузить ESM-модуль?**

С Node.js 22.12 (и 20.19) может, при одном условии: в графе модуля не должно быть top-level `await`. Иначе Node.js бросит `ERR_REQUIRE_ASYNC_MODULE`. Причина в том, что `require()` синхронный и не умеет ждать асинхронный модуль.

На более старых версиях любой `require()` от ESM бросает `ERR_REQUIRE_ESM`. Универсальное решение работает везде: динамический `await import('./esm-module.mjs')` из CJS-контекста возвращает Promise с namespace object.

---

**Что такое top-level await и как он влияет на зависимые модули?**

Top-level await доступен только в ESM. Модуль с `export const data = await fetch(...)` считается "готовым" только после завершения `await`. Все модули, импортирующие этот модуль, ждут его завершения — они не начнут выполнение пока top-level await не разрешится. Это делает весь граф зависимостей асинхронным. Параллельная загрузка: независимые модули с top-level await могут загружаться параллельно.

---

## Группа 12: Современный JavaScript

**Чем `??` принципиально отличается от `||` — покажи случай, где выбор важен.**

`||` срабатывает на любое falsy (0, `''`, `false`, `null`, `undefined`, `NaN`). `??` — только на `null`/`undefined`. Критичный случай: `config.retries ?? 3` — если `retries = 0`, вернёт 0 (корректно). `config.retries || 3` — вернёт 3 (баг: заменяет допустимое 0 на default). Аналогично для пустой строки как валидного значения.

---

**Что `structuredClone` умеет, а `JSON.parse(JSON.stringify())` — нет?**

`structuredClone` корректно клонирует: `Date` (остаётся Date, не строка), `RegExp`, `Map`, `Set`, `ArrayBuffer`, `undefined` (не удаляется), циклические ссылки (не бросает). JSON теряет функции, `undefined`, превращает `Date` в строку, бросает при циклах, заменяет `NaN`/`Infinity` на `null`. Ограничение `structuredClone`: не клонирует функции, DOM-узлы, теряет прототип class instances.

---

**Как AbortController отменяет `fetch` и что происходит на стороне сервера?**

`controller.abort()` устанавливает `signal.aborted = true` и диспатчит `abort` событие. `fetch` подписан на `signal` и при abort отменяет HTTP-запрос на клиенте (браузер закрывает соединение). `fetch` отклоняется с `AbortError`. На стороне **сервера**: сервер может не знать об отмене — продолжает обрабатывать запрос. Для серверной отмены нужен явный механизм (cancellation token в теле запроса).

---

**Что такое tagged template literal и что получает tag-функция?**

Тег — функция, вызываемая с синтаксисом `` tag`template ${expr}` ``. Она получает две вещи:

```txt
strings   — замороженный массив строковых частей, плюс
            strings.raw с сырыми escape-последовательностями
...values — вычисленные выражения
```

Функция может вернуть что угодно, не обязательно строку. Применения: query builder для SQL (structured query language) с параметрами вместо склейки строк, HTML sanitizer, `styled-components`, `gql`.

---

## Группа 13: Predict the Output

**Вопрос 1 — Event Loop + async/await**

```js
async function a() {
  console.log(1);
  await Promise.resolve();
  console.log(2);
}

console.log(3);
a();
console.log(4);
```

Что выведет код? Объясни порядок.

<details>
<summary>Ответ</summary>

`3, 1, 4, 2`. Синхронно: `3` → `a()` запускается → `1` → `await` приостанавливает `a()`, управление возвращается → `4`. Стек пуст → дренируем Microtask Queue: `2`.

</details>

---

**Вопрос 2 — Microtask Queue + вложенные Promise**

```js
Promise.resolve()
  .then(() => {
    console.log('A');
    Promise.resolve().then(() => console.log('B'));
  })
  .then(() => console.log('C'));

Promise.resolve().then(() => console.log('D'));
```

<details>
<summary>Ответ</summary>

`A, D, B, C`. После синхронного кода в очереди `[mA, mD]`. Выполняем `mA`: 'A', добавляем `mB`, `mA` завершена → добавляем `mC`. Очередь: `[mD, mB, mC]`. D → B → C.

</details>

---

**Вопрос 3 — Замыкание + var в цикле**

```js
const fns = [];
for (var i = 0; i < 3; i++) {
  fns.push(() => i);
}
console.log(fns[0](), fns[1](), fns[2]());
```

<details>
<summary>Ответ</summary>

`3 3 3`. Все три стрелки замкнуты на один ER (глобальный/функции) с одной переменной `var i`. К моменту вызова цикл завершён, `i = 3`.

</details>

---

**Вопрос 4 — Прототипы + this**

```js
function Animal(name) { this.name = name; }
Animal.prototype.speak = function() { return this.name; };

const dog = new Animal('Rex');
const speak = dog.speak;

console.log(dog.speak());  // ?
console.log(speak());      // ?
```

<details>
<summary>Ответ</summary>

`'Rex'`, `undefined` (strict) или `''` (sloppy/globalThis.name). `dog.speak()` — implicit binding, `this = dog`. `speak()` — default binding, `this = globalThis` или `undefined`.

</details>

---

**Вопрос 5 — Coercion**

```js
console.log([] + []);    // ?
console.log([] + {});    // ?
console.log(+[]);        // ?
console.log(+{});        // ?
console.log('' == false); // ?
console.log(null == false); // ?
```

<details>
<summary>Ответ</summary>

`''`, `'[object Object]'`, `0`, `NaN`, `true`, `false`.

```txt
[] → '' и {} → '[object Object]'     через ToPrimitive
+[]  = ToNumber('') = 0
+{}  = ToNumber('[object Object]') = NaN
'' == false    → false→0, ''→0, 0==0 → true
null == false  → null равен только null/undefined → false
```

</details>

---

**Вопрос 6 — ESM live bindings**

```js
// counter.mjs
export let x = 1;
export const inc = () => x++;

// main.mjs
import { x, inc } from './counter.mjs';
console.log(x); // ?
inc();
inc();
console.log(x); // ?
const snap = x;
inc();
console.log(snap === x); // ?
```

<details>
<summary>Ответ</summary>

`1`, `3`, `false`. `x` — live binding, обновляется при каждом `inc()`. `snap = x` копирует значение примитива (3) в локальную переменную, не сам binding. После ещё одного `inc()`: `x = 4`, `snap = 3` → `3 !== 4` → false.

</details>

---

**Вопрос 7 — Proxy + Symbol.toPrimitive**

```js
const p = new Proxy({ val: 10 }, {
  get(t, prop, r) {
    if (prop === Symbol.toPrimitive) return hint => t.val * (hint === 'string' ? -1 : 2);
    return Reflect.get(t, prop, r);
  }
});

console.log(+p);     // ?
console.log(`${p}`); // ?
console.log(p + 1);  // ?
```

<details>
<summary>Ответ</summary>

`20`, `'-10'`, `21`.

```txt
+p       → hint 'number'  → 10*2 = 20
`${p}`   → hint 'string'  → 10*-1 = -10 → шаблон даёт '-10'
p + 1    → hint 'default' → 10*2 = 20 → 20+1 = 21
```

</details>

---

**Вопрос 8 — Generator + двунаправленная передача**

```js
function* gen() {
  const a = yield 1;
  const b = yield 2;
  return a + b;
}
const g = gen();
console.log(g.next('x').value); // ?
console.log(g.next(10).value);  // ?
console.log(g.next(20).value);  // ?
```

<details>
<summary>Ответ</summary>

`1`, `2`, `30`. Первый `next('x')` — 'x' игнорируется, выполняется до `yield 1` → возвращает `{ value: 1 }`. Второй `next(10)` — 10 = значение `yield 1`, `a = 10`, выполняется до `yield 2` → `{ value: 2 }`. Третий `next(20)` — 20 = значение `yield 2`, `b = 20`, `return a + b = 30` → `{ value: 30, done: true }`.

</details>
