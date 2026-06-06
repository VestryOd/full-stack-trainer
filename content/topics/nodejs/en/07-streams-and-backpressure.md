# Streams and Backpressure

## The Problem with Large Data

Imagine a file:

```txt
movie.mp4
5 GB
```

---

The naive solution:

```js
const data = await fs.promises.readFile('movie.mp4');
```

---

What will happen?

---

Node will try to load:

```txt
ALL 5 GB
into memory
```

---

If there is not enough memory:

```txt
Out Of Memory
```

---

Even if memory is sufficient:

```txt
enormous GC pressure
```

---

# The Solution

Streams.

---

# What is a Stream

A stream is a flow of data that transfers information in chunks.

---

Instead of:

```txt
5 GB at once
```

---

We get:

```txt
Chunk 1
Chunk 2
Chunk 3
...
```

---

For example:

```txt
64 KB
64 KB
64 KB
```

---

# The Core Idea

Do not hold the entire file in memory.

---

Process the data gradually.

---

# Types of Streams

Node provides four types.

---

# Readable

A data source.

---

For example:

```txt
File
HTTP Request
Socket
```

---

Example:

```js
const stream = fs.createReadStream('file.txt');
```

---

# Writable

A data destination.

---

For example:

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

Can both read and write.

---

Example:

```txt
TCP Socket
```

---

# Transform

Receives data and transforms it.

---

Example:

```txt
Compression
Encryption
CSV Parser
```

---

# How a Readable Stream Works

```js
const stream = fs.createReadStream('file.txt');
```

---

Node starts reading the file in chunks.

---

We receive events:

```js
stream.on('data', chunk => {
  console.log(chunk);
});
```

---

Each chunk is a:

```txt
Buffer
```

---

# End Event

When the data is exhausted:

```js
stream.on('end', () => {
  console.log('done');
});
```

---

# Pipe

The most popular operation.

---

Without pipe:

```js
read.on('data', chunk => {
  write.write(chunk);
});
```

---

With pipe:

```js
read.pipe(write);
```

---

What happens:

```txt
Readable
    ↓
Writable
```

---

Very efficient.

---

# A Real Example

Copying a file.

---

```js
fs.createReadStream('source.txt')
  .pipe(
    fs.createWriteStream('copy.txt')
  );
```

---

# Why Streams Are Faster

Imagine:

```txt
5 GB file
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

The difference is enormous.

---

# Stream Pipeline

A very popular API.

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

Automatically:

```txt
handles errors
closes streams
```

---

# What is Backpressure

One of the most loved topics in senior interviews.

---

# Imagine

Producer:

```txt
100 MB/s
```

---

Consumer:

```txt
10 MB/s
```

---

We have a problem.

---

The producer generates data faster than the consumer can process it.

---

# What Happens Without Control

The buffer starts to grow.

---

```txt
100 MB
500 MB
2 GB
```

---

Memory runs out.

---

# The Solution

Backpressure.

---

# The Idea

If the consumer cannot keep up:

```txt
pause the producer
```

---

# How It Works in Node

The method:

```js
stream.write()
```

returns:

```txt
true
or
false
```

---

false means:

```txt
buffer is full
```

---

Need to wait.

---

```js
writeStream.once('drain', () => {
  continueWriting();
});
```

---

# Why pipe Is So Great

It automatically implements:

```txt
Backpressure
```

---

Therefore:

```js
read.pipe(write);
```

is much better than manual copying.

---

# A Common Question

Why are Streams more efficient than readFile?

---

Answer:

Because a Stream processes data in chunks, without loading the entire file into memory.

---

# Senior Interview Answer

Streams allow processing large volumes of data in chunks without loading them entirely into memory. Node supports Readable, Writable, Duplex, and Transform streams. The backpressure mechanism prevents memory overflow by automatically regulating the data transfer speed between producer and consumer.
