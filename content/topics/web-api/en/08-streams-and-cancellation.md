# Big data gets processed in chunks, and work can be cancelled

Waiting for a file with thousands of notes to load and parse in one
go is a bad idea: the app stays silent until the very end, holds the
whole text in memory twice, and can't stop halfway if the person
changes their mind. A stream, `ReadableStream` and its companions,
hands out data in pieces as they become ready, and `AbortController`
lets processing stop without waiting for the last piece.

## Waiting for the whole file isn't always the sensible choice

Importing a notes archive is this article's running example, and with
a large archive the naive approach shows its cost right away.

```ts
// Importing an archive: the whole file is read before the app
// can show the person anything at all
const text = await file.text();       // the entire file, as a string
const notes = JSON.parse(text);       // and again, as an array of objects
notes.forEach((n) => saveNote(n));
```

On a two-megabyte archive this works fine, but it gives no progress,
keeps the file in memory in two representations at once, and can't
stop any sooner than `JSON.parse` finishing the very last comma.

## `ReadableStream` hands out chunks of an arbitrary size

`file.stream()` returns a stream instead of the whole content at
once — you read it piece by piece, and the browser picks each
piece's size on its own.

```ts
// Reading the archive in pieces instead of file.text()
const reader = file.stream().getReader();
let chunk;
while (!(chunk = await reader.read()).done) {
  console.log(chunk.value.byteLength); // chunk size isn't guaranteed
}
```

A chunk boundary never lines up with a line or record boundary — a
chunk can cut a JSON record right in half. Below, one archived note's
record is split across two byte chunks, and reassembling them in a
buffer still recovers it correctly.

```ts
// Measured on the same setup: the string "id":2 is cut exactly in
// half, but a line buffer still reassembles it whole
let buffer = '';
const results: Note[] = [];
for (const piece of ['{"id":1,"na', 'me":"a"}\n{"id":2,"name":"b"}\n']) {
  buffer += piece;
  const lines = buffer.split('\n');
  buffer = lines.pop()!;
  for (const line of lines) if (line) results.push(JSON.parse(line));
}
console.log(results.length); // 2 — both records parsed correctly
```

## `TransformStream` turns bytes into notes while staying a pipeline

A `TransformStream` sits between reading and writing and changes data
on the fly — in the archive import, it cuts text into individual
notes, line by line.

```ts
// The whole pipeline: bytes -> text -> individual Note objects
let buffer = '';
const lineSplitter = new TransformStream<string, Note>({
  transform(text, controller) {
    buffer += text;
    const lines = buffer.split('\n');
    buffer = lines.pop()!;
    for (const line of lines) if (line) controller.enqueue(JSON.parse(line));
  },
  flush(controller) {
    if (buffer) controller.enqueue(JSON.parse(buffer)); // the last, \n-less line
  },
});

const reader = file.stream()
  .pipeThrough(new TextDecoderStream())
  .pipeThrough(lineSplitter)
  .getReader();
```

No step ever runs ahead of the rest: on a pipeline of three synthetic
numbers, measured on the same setup, the transform step processed one
value, waited for the reader to take the result, and only then picked
up the next. That mutual waiting is called backpressure — it keeps a
fast source from flooding a slow consumer with unprocessed data.

## An `AbortSignal` cuts the pipeline without waiting for its end

A "Cancel import" button should stop the whole pipeline at once, not
just its last step — that's what passing `signal` into `pipeTo` does.

```txt
Importing the archive runs as a pipeline, not one chunk
┌─────────────────────────────────────────────┐
│ The archive: file.stream() hands out bytes  │
└─────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│ TextDecoderStream: bytes become text        │
└─────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│ TransformStream: text is cut into notes     │
└─────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│ Each note is written to IndexedDB right away│
└─────────────────────────────────────────────┘
an AbortSignal can cut the pipeline at any of these steps
```

```ts
// Cancel by hand or by timeout — whichever signal fires first
const manualCancel = new AbortController();
cancelButton.onclick = () => manualCancel.abort('user cancelled import');

const signal = AbortSignal.any([
  manualCancel.signal,
  AbortSignal.timeout(60_000), // a guard against a stuck import
]);

await readableNotes.pipeTo(writableNotes, { signal });
```

`AbortSignal.any` merges several signals into one: the pipeline stops
at whichever fires first, a manual cancel or the timeout. This isn't
the same example reused from a neighboring topic: there,
`AbortController` cancels a single `fetch`; here, one signal holds a
whole pipeline's source, transform, and write step together.

## Already-processed notes stay put; only the remainder is cancelled

The source gets a `cancel()` call with the abort reason, but notes
that already made it to the write step aren't going anywhere.

```ts
// Progress and an honest stop in the middle of the pipeline
let imported = 0;
const writableNotes = new WritableStream({
  write(note) {
    saveNote(note);
    imported++;
    progressLabel.textContent = `Imported ${imported} notes`;
  },
});

try {
  await readableNotes.pipeTo(writableNotes, { signal });
} catch (reason) {
  // reason === 'user cancelled import' — exactly what was passed to abort()
  progressLabel.textContent = `Stopped at ${imported} notes`;
}
```

With six notes already written, cancelling the pipeline leaves them
saved — measured on the same Playwright setup: `pipeTo` rejected with
the reason `'user cancelled import'`, and the `WritableStream` had
already received and written everything that reached it before the
abort. Pass `abort()` a string instead of calling it empty, and that
reason arrives at the source as is, never wrapped in an `AbortError`.

## Common mistakes

- **Reading the archive with `file.text()` instead of a stream.**
  Symptom: the interface shows no progress until the whole file
  parses, and cancelling stops nothing because it's already too late.
- **Assuming a stream chunk ends on a record boundary.** Symptom:
  `JSON.parse` crashes on a partial line, because a byte chunk cut
  off in the middle of it.
- **Cancelling the source without passing `signal` into `pipeTo`.**
  Symptom: `reader.cancel()` runs, but the `WritableStream` keeps
  writing whatever already made it into its queue.
- **Rolling back already-saved records on cancellation.** Symptom:
  a person cancels a long import and gets an empty list instead of
  the part that had already been saved.

## Related topics

- [Heavy work leaves the main thread](./03-workers.md) — where to
  move the JSON parsing itself, if it slows the interface down more
  than reading the stream does.
- [A file reaches an app through four different doors](./07-files-and-clipboard.md) —
  `file.stream()` and the other ways to read a `File`.
- Browser / JS Runtime — the question bank with `AbortController` for
  cancelling a stale `fetch` request, a different job for the same
  tool.
- JavaScript — covers `AbortController` as a language feature and its
  built-in objects, not as part of the platform's streams.
