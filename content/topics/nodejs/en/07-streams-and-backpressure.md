# Streams and Backpressure

## The Problem Streams Solve

```ts
// ❌ Loads the ENTIRE file into memory in one shot
const data = await fs.promises.readFile('movie.mp4'); // 5 GB → 5 GB on the heap
res.end(data);
```

```txt
Problems with this approach:
  - Out Of Memory for files larger than available memory
  - even if memory is sufficient — peak usage of 5 GB for
    EVERY concurrent request (100 requests = 500 GB)
  - the client gets NOTHING until the whole file has been
    read from disk — time to first byte equals the time to
    read the entire file
```

```ts
// ✅ Sends data in chunks (default chunk size ~64KB)
fs.createReadStream('movie.mp4').pipe(res);
```

The idea behind streams isn't just "read a file in pieces" (you could do that without the stream API too) — it's **connecting a producer and a consumer so the producer's speed automatically adapts to the consumer's speed**. That's backpressure, and it's what makes streams a non-trivial topic.

## The internal buffer and highWaterMark — what determines everything else

```txt
Every Readable and Writable stream has an INTERNAL buffer
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

`highWaterMark` is not a "hard memory limit" — it's a THRESHOLD for backpressure signals. Actual memory usage can temporarily exceed it (the internal buffer can accept a whole chunk even if that pushes it past the threshold), but this threshold is what triggers the "slow down" signaling mechanism.

## Backpressure mechanically: what REALLY happens on `.write()`

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
  internal buffer AND RETURNS false once the buffer exceeds
  highWaterMark — BUT THE DATA IS STILL WRITTEN TO THE BUFFER.

  If you ignore the false and keep writing — the buffer grows
  without bound → the classic "growing buffer" memory leak,
  visible in production as a steady rise in process RSS
  under load.
```

```ts
// ✅ Correct manual backpressure implementation
function copy(readStream: Readable, writeStream: Writable) {
  readStream.on('data', (chunk) => {
    const canContinue = writeStream.write(chunk);
    if (!canContinue) {
      readStream.pause(); // stop READING from the source
    }
  });

  writeStream.on('drain', () => {
    // the Writable's buffer dropped below highWaterMark —
    // safe to resume reading
    readStream.resume();
  });
}
```

`.pipe()` does EXACTLY this — `pause()`/`resume()` based on `write()`'s return value and the `'drain'` event. So "pipe implements backpressure automatically" isn't magic — it's an encapsulation of the code above.

## `.pipe()` vs `pipeline()` — why `.pipe()` is dangerous in production

```ts
// ❌ pipe() does NOT stop downstream streams on an error in
// one of them — a source of file descriptor leaks
fs.createReadStream('source.txt')
  .pipe(zlib.createGzip())
  .pipe(fs.createWriteStream('out.gz'));
// if createWriteStream throws (e.g., ENOSPC — disk full),
// readStream and the gzip stream stay OPEN
```

```ts
// ✅ pipeline() — properly cleans up ALL streams on an error
// in ANY of them, and supports async/await
import { pipeline } from 'node:stream/promises';

await pipeline(
  fs.createReadStream('source.txt'),
  zlib.createGzip(),
  fs.createWriteStream('out.gz'),
); // throws if anything goes wrong, and calls destroy()
   // on EVERY stream in the chain
```

```txt
This is a typical senior interview "trick question":
"what's wrong with .pipe() in real code?" — the answer isn't
about backpressure (that part is fine), it's about ERROR
HANDLING and RESOURCE CLEANUP on a partial failure of the chain.
```

## Async iteration — a modern alternative to `'data'`/`'end'` events

```ts
// ✅ for-await-of — Readable streams implement AsyncIterable
async function processLines(filePath: string) {
  const stream = fs.createReadStream(filePath, { encoding: 'utf-8' });

  for await (const chunk of stream) {
    process(chunk);
  }
  // backpressure is handled AUTOMATICALLY: the loop doesn't
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
    callback(); // signals "ready for the next chunk" — THIS is backpressure
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
    transform(record, enc, cb) {
      saveToDatabase(record);
      cb();
    },
  }),
);
```

Key point: `callback()` in `_transform` should only be called once processing of the current chunk is done. If `_transform` performs an async operation (a database write), `callback()` must be called AFTER it completes. Otherwise backpressure breaks: the Transform stream keeps accepting new chunks faster than the current ones are processed, and async operations pile up without bound.

```ts
// ❌ callback() called immediately — backpressure is broken,
// potentially thousands of pending DB writes accumulate in memory
_transform(record, enc, callback) {
  saveToDatabase(record); // async, but NOT awaited
  callback(); // called IMMEDIATELY — Transform thinks it's ready for more
}

// ✅ callback() waits for the async operation to finish
async _transform(record, enc, callback) {
  await saveToDatabase(record);
  callback(); // only now does Transform request the next chunk
}
```

## A practical example: streaming an HTTP response without buffering everything in memory

```ts
// Export a large table as CSV — without loading all rows
// into memory at once
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

Senior nuance: if the client disconnects (`res` becomes `destroyed`), `pipeline()` automatically aborts the ENTIRE chain, including `dbStream` — i.e., it cancels the database query. Without `pipeline()` (using manual `.pipe()`), the database query would keep running and pulling data "into nowhere," holding onto a connection from the DB pool.

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

- **"Streams are just reading a file in chunks"** — missing that the core idea is AUTOMATICALLY synchronizing producer and consumer speed (backpressure), not just saving memory.

- **Ignoring the return value of `.write()`** — not knowing that `write()` returns `false` once the Writable's internal buffer exceeds `highWaterMark`, and that ignoring this signal leads to unbounded buffer growth in memory.

- **Not knowing the difference between `.pipe()` and `pipeline()`** — not mentioning that `.pipe()` doesn't release resources (file descriptors, connections) when an error occurs mid-chain, while `pipeline()` properly calls `destroy()` on every stream.

- **Calling `callback()` in `_transform` before an async operation completes** — this breaks backpressure, letting the Transform stream accept new chunks faster than current ones are processed, causing unbounded accumulation of pending operations (e.g., DB writes).

- **Using streams where they aren't needed** — adding the complexity of stream-based code for small data volumes, where `readFile`/`JSON.parse` is simpler and carries no leak risk from mishandled events.
