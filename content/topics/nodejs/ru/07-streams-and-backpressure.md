<!-- verified: 2026-06-05, corrections: 0 -->
# Streams и Backpressure

## Проблема, которую решают Streams

```ts
// ❌ Загружает ВЕСЬ файл в память одним куском
const data = await fs.promises.readFile('movie.mp4'); // 5 GB → 5 GB в heap
res.end(data);
```

```txt
Проблемы такого подхода:
  - Out Of Memory при файлах больше доступной памяти
  - даже если памяти хватает — пиковое потребление 5 GB
    на КАЖДЫЙ параллельный запрос (100 запросов = 500 GB)
  - клиент не получает НИЧЕГО, пока весь файл не прочитан
    с диска — задержка перед первым байтом ответа равна
    времени чтения всего файла
```

```ts
// ✅ Передаёт данные частями (по умолчанию чанк ~64KB)
fs.createReadStream('movie.mp4').pipe(res);
```

Идея Stream — не "читать файл по частям" сама по себе (это можно сделать и без stream API), а **связать producer и consumer так, чтобы скорость producer автоматически подстраивалась под скорость consumer** — это и есть backpressure, и именно она делает streams нетривиальной темой.

## Внутренний буфер и highWaterMark — то, что определяет ВСЁ остальное

```txt
Каждый Readable и Writable stream имеет ВНУТРЕННИЙ буфер
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
  highWaterMark: 1024 * 1024, // 1 MB чанки
});
```

`highWaterMark` — это не "жёсткий лимит памяти", а ПОРОГ для сигналов backpressure. Реальное потребление памяти может временно превышать его (внутренний буфер может принять чанк целиком, даже если это превысит порог), но именно этот порог запускает механизм сигнализации "притормози".

## Backpressure механически: что РЕАЛЬНО происходит при `.write()`

```ts
// Без backpressure — наивное копирование
readStream.on('data', (chunk) => {
  writeStream.write(chunk); // ❌ игнорируем возвращаемое значение
});
```

```txt
Если источник (диск, сеть) быстрее, чем получатель
(медленный диск, медленная сеть, медленный клиент):

  writeStream.write(chunk) добавляет chunk во внутренний
  буфер Writable И ВОЗВРАЩАЕТ false, когда буфер превысил
  highWaterMark — НО ДАННЫЕ ВСЁ РАВНО ЗАПИСЫВАЮТСЯ В БУФЕР.

  Если игнорировать false и продолжать писать — буфер
  растёт неограниченно → классическая утечка памяти
  "growing buffer", которая видна в production как
  постепенный рост RSS процесса под нагрузкой.
```

```ts
// ✅ Корректная ручная реализация backpressure
function copy(readStream: Readable, writeStream: Writable) {
  readStream.on('data', (chunk) => {
    const canContinue = writeStream.write(chunk);
    if (!canContinue) {
      readStream.pause(); // остановить ЧТЕНИЕ источника
    }
  });

  writeStream.on('drain', () => {
    // буфер Writable опустел ниже highWaterMark —
    // можно продолжать читать
    readStream.resume();
  });
}
```

`.pipe()` делает РОВНО это — `pause()`/`resume()` на основе возвращаемого значения `write()` и события `'drain'`. Поэтому "pipe реализует backpressure автоматически" — это не магия, а инкапсуляция приведённого выше кода.

## `.pipe()` vs `pipeline()` — почему `pipe()` опасен в production

```ts
// ❌ pipe() НЕ останавливает downstream-потоки при ошибке
// в одном из них — это источник утечек файловых дескрипторов
fs.createReadStream('source.txt')
  .pipe(zlib.createGzip())
  .pipe(fs.createWriteStream('out.gz'));
// если createWriteStream выбросит ошибку (например, ENOSPC —
// диск заполнен), readStream и gzip-поток ОСТАНУТСЯ ОТКРЫТЫМИ
```

```ts
// ✅ pipeline() — корректно очищает ВСЕ потоки при ошибке
// в ЛЮБОМ из них, и поддерживает async/await
import { pipeline } from 'node:stream/promises';

await pipeline(
  fs.createReadStream('source.txt'),
  zlib.createGzip(),
  fs.createWriteStream('out.gz'),
); // бросает исключение, если что-то пошло не так,
   // и destroy()-ит ВСЕ потоки в цепочке
```

```txt
Это типичный "trick question" на senior-собеседовании:
"чем плох .pipe() в реальном коде?" — ответ не про
backpressure (с ней всё в порядке), а про ОБРАБОТКУ ОШИБОК
и ОЧИСТКУ РЕСУРСОВ при частичном сбое цепочки.
```

## Async iteration — современная альтернатива событиям `'data'`/`'end'`

```ts
// ✅ for-await-of — Readable стримы реализуют AsyncIterable
async function processLines(filePath: string) {
  const stream = fs.createReadStream(filePath, { encoding: 'utf-8' });

  for await (const chunk of stream) {
    process(chunk);
  }
  // backpressure обрабатывается АВТОМАТИЧЕСКИ: цикл не
  // запрашивает следующий chunk, пока не завершит обработку
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
    callback(); // сигнал "готов к следующему chunk" — ЭТО и есть backpressure
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
    transform(record, enc, cb) {
      saveToDatabase(record);
      cb();
    },
  }),
);
```

Ключевой момент: `callback()` в `_transform` вызывается ТОЛЬКО когда обработка текущего chunk'а завершена. Если внутри `_transform` есть асинхронная операция (запись в БД) — `callback()` нужно вызывать ПОСЛЕ её завершения. Иначе backpressure не работает: Transform будет продолжать принимать новые chunk'и, не дождавшись завершения обработки предыдущих, и асинхронные операции накопятся неограниченно.

```ts
// ❌ callback() вызван немедленно — backpressure сломан,
// в памяти может скопиться тысячи pending DB-запросов
_transform(record, enc, callback) {
  saveToDatabase(record); // async, но НЕ await
  callback(); // вызван СРАЗУ — Transform думает, что готов к следующему
}

// ✅ callback() ждёт завершения async-операции
async _transform(record, enc, callback) {
  await saveToDatabase(record);
  callback(); // только теперь Transform запросит следующий chunk
}
```

## Практический пример: streaming HTTP response без накопления в памяти

```ts
// Экспорт большой таблицы как CSV — без загрузки всех
// строк в память одновременно
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
  // pipeline() прервёт dbStream и освободит соединение с БД
});
```

Senior-нюанс: если клиент прерывает соединение (`res` становится `destroyed`), `pipeline()` автоматически прерывает ВСЮ цепочку, включая `dbStream` — то есть отменяет запрос к БД. Без `pipeline()` (через ручной `.pipe()`) запрос к БД продолжал бы выполняться и тянуть данные "в никуда", удерживая соединение с пулом БД.

## Когда Streams НЕ нужны

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
[The Event Loop]            — Stream'ы построены на событиях
                               ('data', 'drain', 'end') — это
                               EventEmitter-based API, работающий
                               через Event Loop
[libuv and the Thread Pool]  — fs.createReadStream читает чанки
                               через Thread Pool (как и обычный
                               fs.readFile, но порциями)
```

## Типичные ошибки на интервью

- **"Streams — это просто чтение файла по частям"** — упускать, что главная идея — это АВТОМАТИЧЕСКАЯ синхронизация скорости producer и consumer (backpressure), а не просто экономия памяти.

- **Игнорировать возвращаемое значение `.write()`** — не понимать, что `write()` возвращает `false`, когда внутренний буфер Writable превысил `highWaterMark`, и что игнорирование этого сигнала ведёт к неограниченному росту буфера в памяти.

- **Не знать разницу `.pipe()` vs `pipeline()`** — не упоминать, что `.pipe()` не освобождает ресурсы (файловые дескрипторы, соединения) при ошибке в середине цепочки, а `pipeline()` корректно вызывает `destroy()` на всех потоках.

- **Вызывать `callback()` в `_transform` до завершения асинхронной операции** — это ломает backpressure, позволяя Transform-потоку принимать новые chunk'и быстрее, чем обрабатываются текущие, что приводит к неограниченному накоплению pending-операций (например, запросов к БД).

- **Использовать Streams там, где они не нужны** — добавлять сложность stream-based кода для небольших объёмов данных, где `readFile`/`JSON.parse` проще и не несут рисков утечек при неправильной обработке событий.
