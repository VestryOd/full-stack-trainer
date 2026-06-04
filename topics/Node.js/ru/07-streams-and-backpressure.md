# Streams и Backpressure

## Проблема больших данных

Представим файл:

```txt
movie.mp4
5 GB
```

---

Наивное решение:

```js
const data = await fs.promises.readFile('movie.mp4');
```

---

Что произойдет?

---

Node попытается загрузить:

```txt
ВСЕ 5 GB
в память
```

---

Если памяти меньше:

```txt
Out Of Memory
```

---

Даже если памяти хватает:

```txt
огромная нагрузка на GC
```

---

# Решение

Streams.

---

# Что такое Stream

Stream — это поток данных,
который передает информацию частями.

---

Вместо:

```txt
5 GB сразу
```

---

Получаем:

```txt
Chunk 1
Chunk 2
Chunk 3
...
```

---

Например:

```txt
64 KB
64 KB
64 KB
```

---

# Главная идея

Не хранить весь файл в памяти.

---

Обрабатывать данные постепенно.

---

# Типы Streams

Node предоставляет четыре типа.

---

# Readable

Источник данных.

---

Например:

```txt
File
HTTP Request
Socket
```

---

Пример:

```js
const stream = fs.createReadStream('file.txt');
```

---

# Writable

Получатель данных.

---

Например:

```txt
File
HTTP Response
Socket
```

---

```js
const stream = fs.createWriteStream('copy.txt');
```

---

# Duplex

Можно читать и писать.

---

Пример:

```txt
TCP Socket
```

---

# Transform

Получает данные и преобразует их.

---

Пример:

```txt
Compression
Encryption
CSV Parser
```

---

# Как работает Readable Stream

```js
const stream = fs.createReadStream('file.txt');
```

---

Node начинает читать файл частями.

---

Получаем события:

```js
stream.on('data', chunk => {
  console.log(chunk);
});
```

---

Каждый chunk:

```txt
Buffer
```

---

# End Event

Когда данные закончились:

```js
stream.on('end', () => {
  console.log('done');
});
```

---

# Pipe

Самая популярная операция.

---

Без pipe:

```js
read.on('data', chunk => {
  write.write(chunk);
});
```

---

С pipe:

```js
read.pipe(write);
```

---

Что происходит:

```txt
Readable
    ↓
Writable
```

---

Очень эффективно.

---

# Реальный пример

Копирование файла.

---

```js
fs.createReadStream('source.txt')
  .pipe(
    fs.createWriteStream('copy.txt')
  );
```

---

# Почему Streams быстрее

Представим:

```txt
5 GB файл
```

---

readFile():

```txt
5 GB RAM
```

---

Stream:

```txt
64 KB RAM
```

---

Разница огромная.

---

# Stream Pipeline

Очень популярный API.

---

```js
pipeline(
  readStream,
  gzip,
  writeStream,
  callback
);
```

---

Автоматически:

```txt
обрабатывает ошибки
закрывает потоки
```

---

# Что такое Backpressure

Одна из самых любимых тем senior интервью.

---

# Представим

Источник:

```txt
100 MB/s
```

---

Получатель:

```txt
10 MB/s
```

---

Получаем проблему.

---

Источник генерирует данные быстрее,
чем потребитель успевает их обрабатывать.

---

# Что произойдет без контроля

Буфер начнет расти.

---

```txt
100 MB
500 MB
2 GB
```

---

Память закончится.

---

# Решение

Backpressure.

---

# Идея

Если потребитель не успевает:

```txt
приостановить producer
```

---

# Как работает в Node

Метод:

```js
stream.write()
```

возвращает:

```txt
true
или
false
```

---

false означает:

```txt
буфер переполнен
```

---

Нужно подождать.

---

```js
writeStream.once('drain', () => {
  continueWriting();
});
```

---

# Почему pipe такой крутой

Он автоматически реализует:

```txt
Backpressure
```

---

Поэтому:

```js
read.pipe(write);
```

намного лучше ручного копирования.

---

# Частый вопрос

Почему Streams эффективнее readFile?

---

Ответ:

Потому что Stream обрабатывает данные частями,
не загружая весь файл в память.

---

# Senior Interview Answer

Streams позволяют обрабатывать большие объемы данных по частям, не загружая их полностью в память. Node поддерживает Readable, Writable, Duplex и Transform streams. Механизм backpressure предотвращает переполнение памяти, автоматически регулируя скорость передачи данных между producer и consumer.