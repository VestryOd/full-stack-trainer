# Streams and Backpressure

## The Problem Streams Solve

```ts
// ❌ Loads the whole file into memory in one shot
const data = await fs.promises.readFile('movie.mp4'); // 5 GB → 5 GB on the heap
res.end(data);
```

```txt
Problems with this approach:
  - Out Of Memory for files larger than available memory
  - even if memory is sufficient — peak usage of 5 GB for
    every concurrent request (100 requests = 500 GB)
  - the client gets nothing until the whole file has been
    read from disk — time to first byte equals the time to
    read the entire file
```

```ts
// ✅ Sends data in chunks (default chunk size ~64KB)
fs.createReadStream('movie.mp4').pipe(res);
```

Streams are not just "read a file in pieces" — you could do that without the stream API too. The real idea is **connecting a producer and a consumer so the producer's speed automatically adapts to the consumer's speed**. That is backpressure, and it is what makes streams a non-trivial topic.

## The internal buffer and highWaterMark — what determines everything else

```txt
Every Readable and Writable stream has an internal buffer
(a Buffer / array of objects in object mode).

highWaterMark — the threshold size for this buffer:
  - for Readable: how much data to keep "ready" in the
    buffer before Node stops requesting new data from the
    source
  - for Writable: how much data can sit in the "pending
    write" buffer before .write() starts returning false

Default: 64 KB for binary streams (16 for object mode —
counted in objects, not bytes)
```

```ts
// Custom highWaterMark — e.g., for streaming large chunks
// (video) a bigger buffer is more efficient
const readStream = fs.createReadStream('movie.mp4', {
  highWaterMark: 1024 * 1024, // 1 MB chunks
});
```

`highWaterMark` is not a "hard memory limit". It is a **threshold** for backpressure signals. Actual memory usage can temporarily exceed it: the internal buffer accepts a whole chunk even if that pushes it past the threshold. But crossing this threshold is what starts the "slow down" signaling mechanism.

## Backpressure mechanically: what really happens on `.write()`

```ts
// Without backpressure — naive copying
readStream.on('data', (chunk) => {
  writeStream.write(chunk); // ❌ ignoring the return value
});
```

```txt
If the source (disk, network) is faster than the destination
(slow disk, slow network, slow client):

  writeStream.write(chunk) appends chunk to the Writable's
  internal buffer and returns false once the buffer exceeds
  highWaterMark — but the data is still written to the buffer.

  If you ignore the false and keep writing — the buffer grows
  without bound → the classic "growing buffer" memory leak.
  In production it shows up as a steady rise in the process's
  resident set size (RSS) under load.
```

```ts
// ✅ Correct manual backpressure implementation
function copy(readStream: Readable, writeStream: Writable) {
  readStream.on('data', (chunk) => {
    const canContinue = writeStream.write(chunk);
    if (!canContinue) {
      readStream.pause(); // stop reading from the source
    }
  });

  writeStream.on('drain', () => {
    // the Writable's buffer dropped below highWaterMark —
    // safe to resume reading
    readStream.resume();
  });
}
```

`.pipe()` does exactly this: `pause()`/`resume()` based on `write()`'s return value and the `'drain'` event. So "pipe implements backpressure automatically" isn't magic — it's an encapsulation of the code above.

## `.pipe()` vs `pipeline()` — why `.pipe()` is dangerous in production

```ts
// ❌ pipe() does not stop downstream streams on an error in
// one of them — a source of file descriptor leaks
fs.createReadStream('source.txt')
  .pipe(zlib.createGzip())
  .pipe(fs.createWriteStream('out.gz'));
// if createWriteStream throws (e.g., ENOSPC — disk full),
// readStream and the gzip stream stay open
```

```ts
// ✅ pipeline() — properly cleans up every stream on an error
// in any of them, and supports async/await
import { pipeline } from 'node:stream/promises';

await pipeline(
  fs.createReadStream('source.txt'),
  zlib.createGzip(),
  fs.createWriteStream('out.gz'),
); // throws if anything goes wrong, and calls destroy()
   // on every stream in the chain
```

```txt
This is a typical senior interview "trick question":
"what's wrong with .pipe() in real code?" The answer isn't
about backpressure — that part is fine. It is about error
handling and resource cleanup when part of the chain fails.
```

## Async iteration — a modern alternative to `'data'`/`'end'` events

```ts
// ✅ for-await-of — Readable streams implement AsyncIterable
async function processLines(filePath: string) {
  const stream = fs.createReadStream(filePath, { encoding: 'utf-8' });

  for await (const chunk of stream) {
    process(chunk);
  }
  // backpressure is handled automatically: the loop doesn't
  // request the next chunk until it finishes processing the
  // current one — natural pull-based backpressure
}
```

Equivalent to `'data'`/`'end'`, but without the risk of "forgetting backpressure" — the async iterator controls the read rate itself via an internal pull mechanism.

## Transform streams — custom on-the-fly processing

```ts
import { Transform } from 'node:stream';

// Example: a line-by-line NDJSON (newline-delimited JSON)
// parser — a typical pattern for processing large
// logs/exports
class NdjsonParser extends Transform {
  private buffer = '';

  constructor() {
    super({ readableObjectMode: true }); // output is objects, not Buffers
  }

  _transform(chunk: Buffer, encoding: string, callback: TransformCallback) {
    this.buffer += chunk.toString();
    const lines = this.buffer.split('\n');
    this.buffer = lines.pop() ?? ''; // the last line may be incomplete

    for (const line of lines) {
      if (line.trim()) this.push(JSON.parse(line)); // push → the readable side
    }
    callback(); // signals "ready for the next chunk" — this is backpressure
  }

  _flush(callback: TransformCallback) {
    if (this.buffer.trim()) this.push(JSON.parse(this.buffer));
    callback();
  }
}

// Usage:
await pipeline(
  fs.createReadStream('export.ndjson'),
  new NdjsonParser(),
  new Transform({
    objectMode: true,
    async transform(record, enc, cb) {
      await saveToDatabase(record); // cb only after the write, or backpressure breaks
      cb();
    },
  }),
);
```

Key point: `callback()` in `_transform` should only be called once processing of the current chunk is done. If `_transform` performs an async operation, such as a database write, `callback()` must be called **after** it completes.

Otherwise backpressure breaks. The Transform stream keeps accepting new chunks faster than the current ones are processed, and async operations pile up without bound.

```ts
// ❌ callback() called immediately — backpressure is broken,
// potentially thousands of pending database writes accumulate
_transform(record, enc, callback) {
  saveToDatabase(record); // async, but not awaited
  callback(); // called at once — Transform thinks it's ready for more
}

// ✅ callback() waits for the async operation to finish
async _transform(record, enc, callback) {
  await saveToDatabase(record);
  callback(); // only now does Transform request the next chunk
}
```

## A practical example: streaming an HTTP response without buffering everything in memory

```ts
// Export a large table as CSV (comma-separated values) —
// without loading all rows into memory at once
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
  // if the client disconnects mid-download, pipeline() aborts
  // dbStream and frees the database connection
});
```

Senior nuance: if the client disconnects, `res` becomes `destroyed`, and `pipeline()` automatically aborts the **entire** chain, including `dbStream`. That is, it cancels the database query.

Without `pipeline()` — with a manual `.pipe()` — the database query would keep running and pulling data "into nowhere". It would also keep holding a connection from the database pool.

## When Streams aren't worth it

```txt
Streams add complexity (state management, error handling at
every stage of the chain). They're worth it when:
  - the data volume significantly exceeds available memory
    (video, large exports, logs)
  - "time to first byte" matters — start sending data to the
    client before everything is ready

For files in the tens of KB (configs, small JSON responses),
readFile/plain JSON.stringify is simpler, easier to reason
about, and doesn't risk a "forgotten callback()" or
"forgotten pause()/resume()".
```

## Connection to other topics

```txt
[The Event Loop]            — streams are built on events
                               ('data', 'drain', 'end') — an
                               EventEmitter-based API running
                               through the Event Loop
[libuv and the Thread Pool]  — fs.createReadStream reads chunks
                               via the Thread Pool (same as
                               regular fs.readFile, but in pieces)
```

## Common interview mistakes

- **"Streams are just reading a file in chunks"** — missing that the core idea is automatically synchronizing producer and consumer speed (backpressure), not just saving memory.

- **Ignoring the return value of `.write()`** — `write()` returns `false` once the Writable's internal buffer exceeds `highWaterMark`. Ignoring that signal leads to unbounded buffer growth in memory.

- **Not knowing the difference between `.pipe()` and `pipeline()`** — on an error in the middle of the chain, `.pipe()` doesn't release file descriptors or connections. The `pipeline()` helper properly calls `destroy()` on every stream.

- **Calling `callback()` in `_transform` before an async operation completes** — this breaks backpressure. The Transform stream then accepts new chunks faster than current ones are processed, so pending operations (database writes, for example) accumulate without bound.

- **Using streams where they aren't needed** — taking on the complexity of stream-based code for small data volumes. There `readFile`/`JSON.parse` is simpler and carries no leak risk from mishandled events.
