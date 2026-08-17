# The Webpack Core Model

## Why understand Webpack even if you write Vite

Webpack set the vocabulary the whole industry uses: *module*, *chunk*, *loader*, *plugin*, *code splitting*, *hot module replacement*. Vite, Rspack and Turbopack describe themselves in those same terms — sometimes reusing them, sometimes deliberately rejecting them. So the Webpack model is not "how to configure one tool" but the base language for talking about builds, interviews included.

The practical side has not gone anywhere either: Webpack 5 is actively developed, an enormous number of live projects build on it, and the published roadmap is preparing a sixth major version. "Webpack is legacy" is a debatable claim at best.

## The vocabulary: module → chunk → asset

These three words get conflated more than anything else, and the confusion makes it impossible even to state the problem you have.

```txt
     The Webpack vocabulary: module → chunk → asset
┌──────────────────────────────────────────────────────┐
│ MODULE — one file after the loaders ran              │
│ Button.tsx, Button.css, logo.svg, react/index.js     │
│                          ↓                           │
│ grouping: entry points plus every import()           │
│                          ↓                           │
│ CHUNK — a group of modules chosen to ship together   │
│ main, analytics, vendors, runtime                    │
│                          ↓                           │
│ file generation, contenthash substitution            │
│                          ↓                           │
│ ASSET — a file on disk                               │
│ main.a1b2c3.js, analytics.9f8e7d.js, main.4c5d6e.css │
└──────────────────────────────────────────────────────┘
   one chunk yields several assets (js + css + map);
    one module can end up in several chunks at once
```

- **Module** — a node of the graph from [The Module Graph and Resolution], but after transformation. Note that a module is not only JS: `Button.css` and `logo.svg` are modules too, because a loader turned them into something importable.
- **Chunk** — a unit of the **bundler's decision**: "these modules ship together". Chunks arise from entry points, from every `import()`, and from `splitChunks` rules. A chunk exists inside the build; it has a name and an id, but it may not exist on disk as a single file.
- **Asset** — what is actually written into `dist/`. One chunk usually produces several assets: JS, extracted CSS, a source map.

The practical value of the distinction is in how you phrase questions. "My bundle is big" is useless. Useful: **"why did `chart-lib` end up in the `main` chunk rather than in `analytics`?"** That question has an answer; the first one does not. The analysis tools that show exactly this relationship are covered in [Tree Shaking and Optimization].

Worth memorizing separately: the same module can land in **several chunks at once**. If `lib/api.ts` is imported from two lazy routes, without a shared group it is duplicated into both chunks — one of the main themes of [Code Splitting and Long-Term Caching].

## The config: what it is made of

```js
// webpack.config.js — the minimum that covers shop-admin
const path = require('path');
const HtmlWebpackPlugin = require('html-webpack-plugin');

module.exports = {
  mode: 'production',

  // 1. the roots of the graph
  entry: './src/main.tsx',

  // 2. where to write the result and under what names
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: '[name].[contenthash].js',
    clean: true,                        // wipe dist before each build
  },

  // 3. how to find modules — covered in the resolution article
  resolve: {
    extensions: ['.tsx', '.ts', '.js'],
    alias: { '@': path.resolve(__dirname, 'src') },
  },

  // 4. what transforms the files that were found
  module: {
    rules: [
      { test: /\.tsx?$/, exclude: /node_modules/, use: 'ts-loader' },
      { test: /\.s?css$/, use: ['style-loader', 'css-loader', 'sass-loader'] },
      { test: /\.(png|svg|woff2)$/, type: 'asset/resource' },
    ],
  },

  // 5. who intervenes in the build as a whole
  plugins: [new HtmlWebpackPlugin({ template: './index.html' })],
};
```

Five sections, five distinct questions: **where** to start walking, **where** to write, **how** to search, **what** to transform with, **who** intervenes. Everything else in a config is `optimization` (the subject of [Code Splitting and Long-Term Caching] and [Tree Shaking and Optimization]) and `devServer` (the subject of [Dev Server and HMR]).

### mode: one line that changes a dozen defaults

```txt
                  What a single mode line actually switches
┌───────────────────────┬─────────────────────┬──────────────────────────────┐
│ option                │ mode: 'development' │ mode: 'production'           │
├───────────────────────┼─────────────────────┼──────────────────────────────┤
│ devtool               │ 'eval'              │ false                        │
├───────────────────────┼─────────────────────┼──────────────────────────────┤
│ cache                 │ { type: 'memory' }  │ false — filesystem is opt-in │
├───────────────────────┼─────────────────────┼──────────────────────────────┤
│ output.pathinfo       │ true                │ false                        │
├───────────────────────┼─────────────────────┼──────────────────────────────┤
│ optimization.minimize │ false               │ true                         │
├───────────────────────┼─────────────────────┼──────────────────────────────┤
│ moduleIds / chunkIds  │ 'named'             │ 'deterministic'              │
├───────────────────────┼─────────────────────┼──────────────────────────────┤
│ usedExports           │ false               │ true                         │
├───────────────────────┼─────────────────────┼──────────────────────────────┤
│ concatenateModules    │ false               │ true                         │
├───────────────────────┼─────────────────────┼──────────────────────────────┤
│ realContentHash       │ false               │ true                         │
├───────────────────────┼─────────────────────┼──────────────────────────────┤
│ nodeEnv               │ 'development'       │ 'production'                 │
└───────────────────────┴─────────────────────┴──────────────────────────────┘
        mode is not a "speed switch" but a bundle of a dozen defaults,
        half of which directly affect bundle size and cache stability
```

Three consequences worth understanding:

- **`moduleIds: 'named'` versus `'deterministic'`.** In dev a module gets a readable id (its file path), which helps while debugging. In prod it gets a short deterministic one that depends only on the module itself. This is exactly what decides whether your vendor chunk hash changes after you add one file to the application; details in [Code Splitting and Long-Term Caching].
- **`nodeEnv` substitutes `process.env.NODE_ENV` through `DefinePlugin`.** Libraries write `if (process.env.NODE_ENV !== 'production') { warnAboutSomething() }`, the value is inlined as a literal, and the minifier drops the dead branch entirely. That is how React gets noticeably smaller in production. The mechanics are in [Tree Shaking and Optimization].
- **`cache` is off by default in production.** The filesystem cache is opt-in:

```js
// webpack.config.js — persistent caching, built into Webpack 5
module.exports = {
  cache: {
    type: 'filesystem',
    buildDependencies: { config: [__filename] },  // rebuild everything when the config changes
  },
};
```

This is what replaced the old way of speeding up rebuilds — `cache-loader` and `hard-source-webpack-plugin`. Both are unnecessary and unmaintained today: the built-in filesystem cache solves the same problem more reliably because it tracks the build's own dependencies, not just file contents. Seeing `cache-loader` in a 2026 config is a reliable sign that the config has not been revisited in years.

## Loaders: a pipeline over one file

A loader is a function "file contents → file contents", applied to every file matching `test`. It knows nothing about other modules or about the resulting chunks: its work is local.

```txt
           A loader chain: a pipeline over ONE file
┌───────────────────────────────────────────────────────────────────┐
│ use: ['style-loader', 'css-loader', 'sass-loader']                │
│                                 ↓                                 │
│ the file ui/Button.scss is read — plain text                      │
│                                 ↓                                 │
│ sass-loader    SCSS → CSS                                         │
│                                 ↓                                 │
│ css-loader     CSS → a JS module, @import and url() → imports     │
│                                 ↓                                 │
│ style-loader   a JS module → code injecting <style> into the page │
│                                 ↓                                 │
│ the output is a valid JS module — a graph node                    │
└───────────────────────────────────────────────────────────────────┘
    the order is the reverse of how it is written: it is function
  composition — style(css(sass(file))), so the last entry runs first
```

**Why the order is reversed.** Not a quirk, but a direct consequence of a chain being function composition. `use: [a, b, c]` reads as `a(b(c(file)))`: the innermost call first, the outermost last. The same principle as in mathematics and in `compose()` from functional programming. That is why in a CSS chain `sass-loader` — which turns SCSS into CSS — must be last in the array: it runs first.

A key requirement on the end of the chain: **the last loader applied must return valid JavaScript**. The module graph is made of JS nodes, so an image, a stylesheet or an SVG ultimately becomes a JS module too — one that either exports a URL or injects styles into the document.

The order can be shifted with `enforce`: rules split into three groups — `pre`, normal and `post` — and within each group the same right-to-left rule applies. The classic use of `pre` is a linter that must see the source before any transformation.

### Deprecated: file-loader, url-loader, raw-loader

Webpack 5 introduced Asset Modules — built-in handling of binary and text assets with no loaders at all:

```js
module: {
  rules: [
    { test: /\.svg$/,  type: 'asset/resource' },   // a separate file + URL  (was file-loader)
    { test: /\.png$/,  type: 'asset/inline' },     // a data URI             (was url-loader)
    { test: /\.txt$/,  type: 'asset/source' },     // contents as a string   (was raw-loader)
    { test: /\.jpg$/,  type: 'asset' },            // chosen by size, 8 KB threshold
  ],
}
```

All three old loaders are legacy today. The same process continues: per the project roadmap, CSS (`experiments.css`, an experiment since version 5), HTML handling and TypeScript compilation are all moving into core. In other words, Webpack's direction of travel is to reduce the number of loaders and plugins a typical project needs.

### The same job in Vite

Vite has no "loader" concept at all. The typical transformations are built in: TypeScript, JSX, CSS, PostCSS, preprocessors and static assets are handled without configuration. Anything non-typical is done by a plugin with a `transform` hook.

```ts
// vite.config.ts — the equivalent of the config above
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  css: {
    preprocessorOptions: {
      scss: { additionalData: '@use "@/styles/vars" as *;' },
    },
  },
});
```

Read this comparison carefully. The Vite config is shorter **not because Vite is "better designed"**, but because its policy differs: typical cases are baked into the tool rather than expressed as configuration. The price is less control in atypical cases, and the moment you need that control you are writing a plugin. The other side of the same coin is in [The Vite Model].

## Plugins: hooking into the build lifecycle

A plugin operates on a different level: it does not transform files, it intervenes in the **process**. The model is simple:

- **compiler** — the object representing the whole Webpack run. It lives from start to finish (and in watch mode, for the entire session).
- **compilation** — the object of one specific build. In watch mode there will be many: one per rebuild.

Both expose sets of hooks — points you can attach to: "the graph is built", "chunks are assigned", "files are about to be written". A plugin is an object with an `apply(compiler)` method that subscribes to the hooks it needs. The internal mechanics of subscribing (the `tapable` library, sync and async hook flavours) are not needed for practical work — the model "there are stages, you can attach to them" is enough.

A minimal plugin in full:

```js
// adds a file with the build timestamp to dist
class BuildStampPlugin {
  apply(compiler) {
    compiler.hooks.thisCompilation.tap('BuildStampPlugin', (compilation) => {
      compilation.hooks.processAssets.tap(
        {
          name: 'BuildStampPlugin',
          stage: compiler.webpack.Compilation.PROCESS_ASSETS_STAGE_ADDITIONAL,
        },
        () => {
          const { RawSource } = compiler.webpack.sources;
          compilation.emitAsset('build-stamp.txt', new RawSource(`built at ${Date.now()}`));
        },
      );
    });
  }
}
```

Notice what is missing: there is no "file contents" input. A plugin gets access to the build as a whole and decides for itself what to do with it — add an asset, modify an existing one, fail the build, write to the stats.

```txt
                     Loader versus plugin: different units of work
┌────────────────────┬──────────────────────────────┬─────────────────────────────────┐
│                    │ loader                       │ plugin                          │
├────────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ unit of work       │ a single file                │ the whole build                 │
├────────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ when it runs       │ when a file enters the graph │ on lifecycle hooks              │
├────────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ what it receives   │ the file contents            │ compiler and compilation        │
├────────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ what it returns    │ transformed contents         │ nothing — it mutates the build  │
├────────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ sees other modules │ no                           │ yes, the entire graph           │
├────────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ typical examples   │ ts-loader, sass-loader       │ HtmlWebpackPlugin, DefinePlugin │
├────────────────────┼──────────────────────────────┼─────────────────────────────────┤
│ the Vite analogue  │ a plugin's transform hook    │ the other hooks of that plugin  │
└────────────────────┴──────────────────────────────┴─────────────────────────────────┘
              Vite has no separate "loader" concept: both are hooks of one
                  plugin, which makes its vocabulary one term shorter
```

A test that separates the two cleanly: **if the job can be done by looking at one file, it is a loader; if it needs to know something about the build as a whole, it is a plugin.** Transpiling TypeScript is a loader. Generating an `index.html` that links to the final hashed assets is a plugin, because asset names are only known at the end of the build.

### A plugin in Vite

The same plugin in Vite terms (in fact, in Rollup/Rolldown terms, whose interface Vite adopts):

```ts
import type { Plugin } from 'vite';

export function buildStamp(): Plugin {
  return {
    name: 'build-stamp',
    apply: 'build',                  // production build only, not the dev server
    generateBundle() {
      this.emitFile({
        type: 'asset',
        fileName: 'build-stamp.txt',
        source: `built at ${Date.now()}`,
      });
    },
  };
}
```

The differences are immediately visible: one concept instead of two, `enforce: 'pre' | 'post'` to control ordering relative to the built-in plugins, and `apply: 'build' | 'serve'` to pick a mode. Plus Vite-specific hooks layered on the Rollup interface: `config`, `configResolved`, `configureServer`, `transformIndexHtml`. The ecosystem consequence — compatibility with Rollup plugins — is covered in [The Vite Model].

## Why a Webpack config grows

Three reasons, all structural rather than "bad tool":

1. **Every file type needs an explicit rule.** Nothing works by default — that is the price of flexibility.
2. **Dev and prod need different values for the same options.** `devtool`, `output.filename`, `optimization`, `devServer` — almost everything differs.
3. **Optimizations are declared explicitly.** `splitChunks`, `runtimeChunk`, minimizers — all of it is config lines.

The standard answer is composing configs per environment:

```txt
config/
├─ webpack.common.js    entry, resolve, loader rules — the shared part
├─ webpack.dev.js       devServer, devtool, mode: development
└─ webpack.prod.js      contenthash, splitChunks, mode: production
```

```js
// config/webpack.prod.js
const { merge } = require('webpack-merge');
const common = require('./webpack.common.js');

module.exports = merge(common, {
  mode: 'production',
  devtool: 'source-map',
  output: { filename: '[name].[contenthash].js' },
  optimization: {
    splitChunks: { chunks: 'all' },
    runtimeChunk: 'single',
  },
});
```

The alternative is a config function that receives the environment:

```js
// webpack.config.js
module.exports = (env, argv) => ({
  mode: argv.mode,
  devtool: argv.mode === 'production' ? 'source-map' : 'eval-cheap-module-source-map',
  // ...
});
```

The criterion is simple: if the environments differ by two or three lines, the function reads better; if whole sections differ, `webpack-merge` is more honest, because it does not turn a config into a tree of ternaries.

A separate case is monorepos and frameworks with their own CLI. There the config is usually generated by the tool and must not be edited by hand: you extend the generated one instead. How that works is covered in the NX course (executors and build configuration) and in the Angular course (the build and deploy chapter).

## Relation to other topics

```txt
[The Module Graph and Resolution]   — where a module comes from: the graph
                                       walk and the resolution algorithm
[Code Splitting and Long-Term
 Caching]                            — where a chunk comes from: splitChunks,
                                       runtimeChunk, contenthash in an asset
[Tree Shaking and Optimization]     — what usedExports, concatenateModules
                                       and the minifier actually do
[Dev Server and HMR]                — the devServer section and how hot
                                       reloading is built on the same model
[The Vite Model]                    — a different answer to the same problems:
                                       built-in transforms and one kind of
                                       extension instead of two
[Ecosystem and Choosing a Tool]     — Rspack as a Webpack replacement that
                                       does not require rewriting the config
NX course                            — building inside a monorepo
Angular course                       — building an Angular application
```

## Common interview traps

- **Conflating module, chunk and asset.** The most common and most visible mistake. Someone who says "chunk" for a file in `dist/` and "bundle" for everything at once cannot explain module duplication across two chunks, nor why CSS is extracted into its own asset. A good answer separates three levels: the file after transformation, the bundler's grouping decision, the result on disk.

- **"A loader and a plugin are roughly the same, just wired differently"** — they are fundamentally different units of work. The interviewer's probe usually sounds like: *"you need to generate an `index.html` linking to hashed files — loader or plugin, and why?"* Answering "a plugin, because asset names are only known at the end of the build, while a loader only sees one file" shows model-level understanding rather than a memorized list.

- **Not knowing why loaders apply right to left.** "Historical reasons" is a weak answer. "Because a chain is function composition: `use: [a, b, c]` means `a(b(c(file)))`" is a strong one, and it sticks forever.

- **"`mode: 'production'` just turns on minification"** — that is about a tenth of the truth. Behind one line sits a dozen defaults, including `moduleIds: 'deterministic'` (which affects cache stability), `usedExports` and `concatenateModules` (tree shaking and module merging), and the `NODE_ENV` substitution through `DefinePlugin`.

- **Suggesting `cache-loader` or `hard-source-webpack-plugin` to speed up builds** — a marker of Webpack 4-era knowledge. Since version 5 the built-in `cache: { type: 'filesystem' }` covers that job and does it more reliably, because `buildDependencies` makes it aware of the build's own inputs. `file-loader`/`url-loader`/`raw-loader` instead of Asset Modules is the same tell.

- **"The Vite config is shorter, therefore Vite is better"** — comparing the wrong things. A short config means the typical transformations are baked into the tool, not that there is less work to do. A strong answer frames it as a choice between "everything explicit and configurable" and "typical works by itself, atypical needs a plugin" — and names which projects justify which choice.
