# A file reaches an app through four different doors

A file-picker button, drag and drop, pasting from the clipboard, and
the modern File System Access API — four different ways to get a
file from a person, and all four end up with the same kind of object.
The difference between them isn't the result; it's what action they
demand from a human, and what the app is then allowed to do with the
file.

## All four doors end at the same object — `File`

`File` extends `Blob` and adds a name, a modified date, and a size —
whether it arrived from a picker dialog, the clipboard, or a drag.

```ts
// The classic file picker — the entry point that's been around longest
fileInput.addEventListener('change', async (e) => {
  const file = (e.target as HTMLInputElement).files![0];
  const text = await file.text(); // the modern way, no FileReader needed
  attachToNote(currentNoteId, { name: file.name, size: file.size, text });
});
```

| `File` property | what it holds |
|---|---|
| `name` | the file name, with its extension |
| `size` | size in bytes |
| `type` | MIME (media type) — for example, `image/png` — or an empty string |
| `lastModified` | a number: the last-modified timestamp |

The methods `file.text()`, `file.arrayBuffer()`, and `file.stream()`
read content asynchronously and need no old-style `FileReader` with
its callbacks. For a large attachment, `file.stream()` is the next
article's topic, where a file is read in pieces instead of all at
once.

## An object URL lives until it's explicitly released

`URL.createObjectURL` gives a file an address the browser can display
— an attachment preview in a note, say — without reading its bytes
into the app's own memory.

```ts
// A note attachment's preview: the browser hands out the address
const objectUrl = URL.createObjectURL(file);
preview.src = objectUrl; // blob:http://localhost:8934/fffd41f1-...
// the address shape was captured on the same Playwright setup

// Once the preview is no longer needed — the note was deleted or closed
URL.revokeObjectURL(objectUrl);
```

Until the address is revoked, the browser keeps the file in memory,
even once the `<img>` that used it is long gone from the page.
`revokeObjectURL` isn't an optimization — it's a required step of
removing an attachment.

## File System Access gives lasting access, not a one-time pick

A plain `<input>` hands over a `File` once, and there's no way to
read that same file again without a new dialog. File System Access
works differently: it returns a handle — a `FileSystemFileHandle` —
that can be saved and reused in a later session.

```txt
A handle outlives the session; a plain File does not
┌───────────────────────────────────────────────────────┐
│ The user opens showOpenFilePicker()                   │
└───────────────────────────────────────────────────────┘
                             │
                             ▼
┌───────────────────────────────────────────────────────┐
│ The app gets a FileSystemFileHandle                   │
└───────────────────────────────────────────────────────┘
                             │
                             ▼
┌───────────────────────────────────────────────────────┐
│ The handle is saved in IndexedDB for later            │
└───────────────────────────────────────────────────────┘
                             │
                             ▼
┌───────────────────────────────────────────────────────┐
│ Next session: handle.queryPermission() before reading │
└───────────────────────────────────────────────────────┘
the app asks for access again, instead of picking the file again
```

```ts
// Opened the file once, saved the handle — access outlives the closed tab
const [handle] = await window.showOpenFilePicker();
await saveHandleForLater(currentNoteId, handle); // the handle goes to IndexedDB

// Next session: ask for permission again before touching the file
const status = await handle.queryPermission({ mode: 'read' });
if (status === 'granted') {
  const file = await handle.getFile();
}
```

As of this writing, `showOpenFilePicker`, `showSaveFilePicker`, and
`showDirectoryPicker` are supported only by `Chromium` — check
current browser support tables rather than this text. An app that
needs a handle everywhere must plan for a classic `<input>` as a
fallback path.

## Drag and drop delivers files through `DataTransfer`, not a click

A `drop` event keeps its files not on `event.target` but inside a
`DataTransfer` object, which can also carry text, links, and other
data.

```ts
// An attachment drop zone: skip preventDefault on dragover
// and the drop event never fires at all — the spec requires it
dropZone.addEventListener('dragover', (e) => e.preventDefault());

dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  const files = Array.from(e.dataTransfer!.files);
  files.forEach((file) => attachToNote(currentNoteId, file));
});
```

```ts
// What a DataTransfer with one dropped file actually holds —
// checked on a synthetic object on the same setup
console.log(Array.from(dataTransfer.types)); // ['Files']
console.log(dataTransfer.items[0].kind);     // 'file'
```

The `types` list doesn't enumerate each file's MIME type separately —
it only reports the category `'Files'` once at least one file was
dropped. The real type comes from the `File` object itself, once it's
pulled out of `dataTransfer.files`.

## The clipboard: reading asks permission, writing asks for a gesture

Writing to the clipboard and reading from it follow different rules:
a write only needs a real human action behind it, while a read also
needs the `clipboard-read` permission.

```ts
// Pasting an attachment from the clipboard — a screenshot, say
pasteZone.addEventListener('paste', async (e) => {
  const item = Array.from(e.clipboardData!.items)
    .find((i) => i.type.startsWith('image/'));
  if (item) attachToNote(currentNoteId, item.getAsFile()!);
});
```

```txt
With no gesture and no permission:
NotAllowedError: Failed to execute 'writeText' on 'Clipboard':
Write permission denied.

With read permission granted:
clipboard.read() → ClipboardItem, types: ['text/plain']
```

Both messages were captured on the same Playwright setup. The
`clipboard-read` permission starts in the `prompt` state by default —
the same state geolocation had in this topic's first article. An
automated environment is stricter about gestures than a regular
browser: in a real Chrome, a button click is almost always enough for
`writeText`, but that's worth confirming in your target browser
rather than assuming.

## Sending a file back out is just a link with a `download` attribute

Handing a file back to the person needs no separate API — a link is
enough, and the browser opens its own save dialog for it.

```ts
// Exporting a note as a plain-text file
function downloadNote(note: Note) {
  const blob = new Blob([note.body], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${note.title}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}
```

`showSaveFilePicker` from File System Access does the same job
differently: the person picks both a name and a folder up front, and
the app can then write to that same file several times in a row. A
`download` link can't do that — it creates a fresh file on every
download.

## What to pick for a note's attachment

| scenario | fitting door |
|---|---|
| An "Attach file" button | the classic `<input type="file">` |
| An area where an image gets dragged in | `DataTransfer` on the `drop` event |
| Pasting a screenshot with a key combo | `clipboardData` on the `paste` event |
| Editing the same file over and over | File System Access, with `<input>` as a fallback |
| Exporting a note back to the person | a `download` link, with no extra permission |

## Common mistakes

- **Skipping `preventDefault()` on `dragover`.** Symptom: the `drop`
  event never fires at all, and the browser opens the file in a new
  tab instead.
- **Forgetting `URL.revokeObjectURL` after removing an attachment.**
  Symptom: the app's memory grows with every preview opened and
  closed.
- **Expecting a clipboard-write permission dialog, like notifications.**
  Symptom: the code waits for a dialog that never shows up — a write
  is almost always settled by the gesture, not by a dialog.
- **Relying on File System Access with no support check.** Symptom:
  the "Open and keep editing" button silently does nothing in a
  browser where `showOpenFilePicker` doesn't exist.

## Related topics

- [Big data gets processed in chunks, and work can be cancelled](./08-streams-and-cancellation.md) —
  `file.stream()` for attachments that are never read whole.
- [A browser's storages each do a different job](./05-storage.md) —
  where to keep an attachment's own `Blob` between sessions,
  `IndexedDB`.
- React — the task bank with component-level clipboard practice.
