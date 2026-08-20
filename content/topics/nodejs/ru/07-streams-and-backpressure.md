<!-- verified: 2026-06-05, corrections: 0 -->
# Streams и Backpressure

## Проблема, которую решают Streams

```ts
// ❌ Загружает весь файл в память одним куском
const data = await fs.promises.readFile('movie.mp4'); // 5 GB → 5 GB в heap
res.end(data);
```

```txt
Проблемы такого подхода:
  - Out Of Memory при файлах больше доступной памяти
  - даже если памяти хватает — пиковое потребление 5 GB
    на каждый параллельный запрос (100 запросов = 500 GB)
  - клиент не получает ничего, пока весь файл не прочитан
    с диска — задержка перед первым байтом ответа равна
    времени чтения всего файла
```

```ts
// ✅ Передаёт данные частями (по умолчанию чанк ~64KB)
fs.createReadStream('movie.mp4').pipe(res);
```

Streams — это не просто "читать файл по частям": так можно сделать и без stream API. Главная идея — **связать producer и consumer так, чтобы скорость producer автоматически подстраивалась под скорость consumer**. Это и есть backpressure, и именно она делает streams нетривиальной темой.

## Внутренний буфер и highWaterMark — то, что определяет всё остальное

```txt
Каждый Readable и Writable stream имеет внутренний буфер
(объект Buffer/массив объектов в object mode).

highWaterMark — порог размера этого буфера:
  - для Readable: сколько байт держать в буфере "наготове"
    до того, как Node перестанет запрашивать у источника
    новые данные
  - для Writable: сколько байт можно держать в буфере
    "на запись" до того, как .write() начнёт возвращать false

По умолчанию: 64 KB для бинарных потоков (16 для object mode —
в штуках объектов, а не байтах)
```

```ts
// Кастомный highWaterMark — например, для стриминга
// больших чанков (видео) выгоднее буфер побольше
const readStream = fs.createReadStream('movie.mp4', {
  highWaterMark: 1024 * 1024, // чанки по 1 MB
});
```

`highWaterMark` — это не "жёсткий лимит памяти". Это **порог** для сигналов backpressure. Реальное потребление памяти может временно превышать его: внутренний буфер принимает чанк целиком, даже если это выводит его за порог. Но именно переход через этот порог запускает механизм сигнализации "притормози".

## Backpressure механически: что реально происходит при `.write()`

```ts
// Без backpressure — наивное копирование
readStream.on('data', (chunk) => {
  writeStream.write(chunk); // ❌ игнорируем возвращаемое значение
});
```

```txt
Если источник (диск, сеть) быстрее, чем получатель
(медленный диск, медленная сеть, медленный клиент):

  writeStream.write(chunk) добавляет чанк во внутренний
  буфер Writable и возвращает false, когда буфер превысил
  highWaterMark — но данные всё равно записываются в буфер.

  Если игнорировать false и продолжать писать — буфер
  растёт неограниченно → классическая утечка памяти
  "growing buffer". В production она видна как постепенный
  рост RSS процесса (resident set size — вся память
  процесса) под нагрузкой.
```

```ts
// ✅ Корректная ручная реализация backpressure
function copy(readStream: Readable, writeStream: Writable) {
  readStream.on('data', (chunk) => {
    const canContinue = writeStream.write(chunk);
    if (!canContinue) {
      readStream.pause(); // остановить чтение источника
    }
  });

  writeStream.on('drain', () => {
    // буфер Writable опустел ниже highWaterMark —
    // можно продолжать читать
    readStream.resume();
  });
}
```

`.pipe()` делает ровно это: `pause()`/`resume()` на основе возвращаемого значения `write()` и события `'drain'`. Поэтому "pipe реализует backpressure автоматически" — это не магия, а инкапсуляция приведённого выше кода.

## `.pipe()` vs `pipeline()` — почему `pipe()` опасен в production

```ts
// ❌ pipe() не останавливает downstream-потоки при ошибке
// в одном из них — это источник утечек файловых дескрипторов
fs.createReadStream('source.txt')
  .pipe(zlib.createGzip())
  .pipe(fs.createWriteStream('out.gz'));
// если createWriteStream выбросит ошибку (например, ENOSPC —
// диск заполнен), readStream и gzip-поток останутся открытыми
```

```ts
// ✅ pipeline() — корректно очищает все потоки при ошибке
// в любом из них, и поддерживает async/await
import { pipeline } from 'node:stream/promises';

await pipeline(
  fs.createReadStream('source.txt'),
  zlib.createGzip(),
  fs.createWriteStream('out.gz'),
); // бросает исключение, если что-то пошло не так,
   // и вызывает destroy() на всех потоках цепочки
```

```txt
Это типичный "trick question" на senior-собеседовании:
"чем плох .pipe() в реальном коде?" Ответ не про
backpressure — с ней всё в порядке. Ответ про обработку
ошибок и очистку ресурсов при частичном сбое цепочки.
```

## Async iteration — современная альтернатива событиям `'data'`/`'end'`

```ts
// ✅ for-await-of — Readable-потоки реализуют AsyncIterable
async function processLines(filePath: string) {
  const stream = fs.createReadStream(filePath, { encoding: 'utf-8' });

  for await (const chunk of stream) {
    process(chunk);
  }
  // backpressure обрабатывается автоматически: цикл не
  // запрашивает следующий чанк, пока не завершит обработку
  // текущего — это естественный pull-based backpressure
}
```

Эквивалентно `'data'`/`'end'`, но без риска "забыть про backpressure" — async iterator сам контролирует темп чтения через внутренний pull-механизм.

## Transform stream — кастомная обработка "на лету"

```ts
import { Transform } from 'node:stream';

// Пример: построчный парсер NDJSON (newline-delimited JSON)
// — типичный паттерн для обработки больших логов/экспортов
class NdjsonParser extends Transform {
  private buffer = '';

  constructor() {
    super({ readableObjectMode: true }); // выход — объекты, не Buffer
  }

  _transform(chunk: Buffer, encoding: string, callback: TransformCallback) {
    this.buffer += chunk.toString();
    const lines = this.buffer.split('\n');
    this.buffer = lines.pop() ?? ''; // последняя строка может быть неполной

    for (const line of lines) {
      if (line.trim()) this.push(JSON.parse(line)); // push → readable-сторона
    }
    callback(); // сигнал "готов к следующему чанку" — это и есть backpressure
  }

  _flush(callback: TransformCallback) {
    if (this.buffer.trim()) this.push(JSON.parse(this.buffer));
    callback();
  }
}

// Использование:
await pipeline(
  fs.createReadStream('export.ndjson'),
  new NdjsonParser(),
  new Transform({
    objectMode: true,
    async transform(record, enc, cb) {
      await saveToDatabase(record); // cb — только после записи, иначе backpressure сломан
      cb();
    },
  }),
);
```

Ключевой момент: `callback()` в `_transform` вызывается только тогда, когда обработка текущего чанка завершена. Если внутри `_transform` есть асинхронная операция — например, запись в базу данных — `callback()` нужно вызывать **после** её завершения.

Иначе backpressure не работает. Transform продолжает принимать новые чанки, не дождавшись обработки предыдущих, и асинхронные операции накапливаются неограниченно.

```ts
// ❌ callback() вызван немедленно — backpressure сломан,
// в памяти может скопиться тысячи незавершённых запросов к базе
_transform(record, enc, callback) {
  saveToDatabase(record); // асинхронно, но без await
  callback(); // вызван сразу — Transform думает, что готов к следующему
}

// ✅ callback() ждёт завершения асинхронной операции
async _transform(record, enc, callback) {
  await saveToDatabase(record);
  callback(); // только теперь Transform запросит следующий чанк
}
```

## Практический пример: streaming HTTP response без накопления в памяти

```ts
// Экспорт большой таблицы как CSV (comma-separated values)
// — без загрузки всех строк в память одновременно
app.get('/export.csv', async (req, res) => {
  res.setHeader('Content-Type', 'text/csv');

  const dbStream = db.query('SELECT * FROM orders').stream(); // Readable

  const csvTransform = new Transform({
    objectMode: true,
    transform(row, enc, callback) {
      callback(null, `${row.id},${row.amount},${row.createdAt}\n`);
    },
  });

  await pipeline(dbStream, csvTransform, res);
  // если клиент закроет соединение посреди скачивания —
  // pipeline() прервёт dbStream и освободит соединение с базой
});
```

Senior-нюанс: если клиент прерывает соединение, `res` становится `destroyed`, и `pipeline()` автоматически прерывает **всю** цепочку, включая `dbStream`. То есть отменяет запрос к базе данных.

Без `pipeline()` — на ручном `.pipe()` — запрос к базе продолжал бы выполняться и тянуть данные "в никуда". Заодно он удерживал бы соединение из пула базы данных.

## Когда Streams не нужны

```txt
Streams добавляют сложность (управление состоянием,
обработка ошибок на каждом этапе цепочки). Они оправданы,
когда:
  - объём данных значительно больше доступной памяти
    (видео, большие экспорты, логи)
  - нужен "time to first byte" — начать отдавать данные
    клиенту, не дожидаясь полной готовности

Для файлов в десятки КБ (конфиги, маленькие JSON-ответы)
readFile/обычный JSON.stringify проще, понятнее и не
создают рисков "забытого callback()" или "забытого
pause()/resume()".
```

## Связь с другими темами

```txt
[The Event Loop]            — потоки построены на событиях
                               ('data', 'drain', 'end') — это
                               EventEmitter-based API, работающий
                               через Event Loop
[libuv and the Thread Pool]  — fs.createReadStream читает чанки
                               через Thread Pool (как и обычный
                               fs.readFile, но порциями)
```

## Типичные ошибки на интервью

- **"Streams — это просто чтение файла по частям"** — упускать, что главная идея — автоматическая синхронизация скорости producer и consumer (backpressure), а не просто экономия памяти.

- **Игнорировать возвращаемое значение `.write()`** — `write()` возвращает `false`, когда внутренний буфер Writable превысил `highWaterMark`. Игнорирование этого сигнала ведёт к неограниченному росту буфера в памяти.

- **Не знать разницу `.pipe()` vs `pipeline()`** — `.pipe()` не освобождает ресурсы (файловые дескрипторы, соединения) при ошибке в середине цепочки. `pipeline()` корректно вызывает `destroy()` на всех потоках.

- **Вызывать `callback()` в `_transform` до завершения асинхронной операции** — это ломает backpressure. Transform начинает принимать новые чанки быстрее, чем обрабатываются текущие, и незавершённые операции (например, запросы к базе данных) накапливаются неограниченно.

- **Использовать Streams там, где они не нужны** — брать сложность stream-based кода для небольших объёмов данных. Там `readFile`/`JSON.parse` проще и не несёт рисков утечек при неправильной обработке событий.
