# Generators: scaffolding as code

## Theory

### A generator is a function over a virtual file system

We've been using generators since chapter 01; time to open up the mechanics. A generator is a function of the form `(tree, options) => void`, where **Tree** is a virtual file system. Reads come from disk, but every write (`tree.write`, `generateFiles`) accumulates in memory. Only after the generator has finished does Nx flush the changes to disk:

```
┌───────────────────────────────────────────────────┐
│ nx g @mini-shop/workspace-plugin:feature-lib cart │
└───────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│ schema.json: option validation,                   │
│ x-prompt collects what is missing                 │
└───────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│ implementation(tree, options):                    │
│ every change goes to the virtual FS (Tree)        │
└───────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│ --dry-run: print the Tree diff and exit,          │
│ the disk is untouched                             │
└───────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│ without dry-run: flush the Tree to disk,          │
│ formatting, package installs                      │
└───────────────────────────────────────────────────┘
```

Two things follow from this architecture for free. First, `--dry-run` doesn't "emulate": it executes **the same code** and prints the virtual file system diff, just without the flush. A divergence between dry-run and a real run is impossible by construction. Second, generators are unit-testable without a disk: create a Tree in memory, run the function, assert on the contents.

The same mechanics powers `nx migrate` (chapter 13). Migrations are generators too, except the Nx team writes them, and they run codemods over your repo during version upgrades.

### Built-in generators: schema, options, defaults

The invocation syntax is `nx g <package>:<name>`. What a given generator can do is described by its **schema.json**. It lists option types, required flags, defaults, and `x-prompt` — the question asked interactively when an option is missing. To see it without reading JSON: `nx g @nx/react:lib --help`. The third layer of defaults is `generators` in nx.json (chapter 01): options recorded there are applied silently.

### How to read someone else's generator

The skill is the sibling of "find the executor's code" from chapter 03. The chain:

```bash
cat node_modules/@nx/react/generators.json | python3 -m json.tool | grep -A4 '"library"'
# "library": {
#   "factory": "./src/generators/library/library",
#   "schema": "./src/generators/library/schema.json", ...

cat node_modules/@nx/react/src/generators/library/schema.json   # WHAT it asks
less node_modules/@nx/react/src/generators/library/library.js   # WHAT it does
```

When a generator did something you didn't expect, the answer is always in those two files, not in the docs.

### Why teams write their own generators

Chapter 06 ended with conventions: the scope/type structure, tags, non-buildable, vitest, a templated importPath. A convention living in a wiki degrades with every new person. Someone forgets the tags, someone picks a different bundler, someone puts the lib in the wrong place.

**A local generator is a convention compiled into code.** The correct structure emerges not because everyone read the wiki, but because any other path is longer.

The key technique when writing one is **composition**. Don't create the project by hand via `tree.write`. Programmatically call the built-in generator (`libraryGenerator` from `@nx/react`) with pinned options, then post-process the result.

The built-in generator updates tsconfig.base.json, creates project.json, the eslint and vite configs — and keeps doing it correctly after every Nx upgrade. Your code is responsible only for the delta: domain templates, validations, naming conventions.

> **Versions.** Before Nx 17, local generators lived in `tools/generators` and ran via a separate `nx workspace-generator` command — that mechanism is gone. The modern way is a local plugin: a regular lib with a `generators.json`, which `nx g` finds by package name. If you see `tools/generators` with schema.json files in a work repo — it's an artifact of old versions; migrations move it to a plugin.

### Devkit: the minimal vocabulary

Everything you need is exported from `@nx/devkit`:

- `Tree` — read, write, exists, children, delete.
- `names()` — name canonicalization: `shoppingCart` gives fileName `shopping-cart` and className `ShoppingCart`.
- `generateFiles()` — renders a template folder, substituting `__fileName__` in paths and `<%= className %>` in contents.
- `formatFiles()` — prettier over what changed.
- `readProjectConfiguration` / `updateProjectConfiguration` — work with project.json as an object.

## In a real-world monorepo

- `npx nx list` — plugins with generators; `npx nx list @nx/react` — a package's generator list; `nx g <gen> --help` — the options without reading schema.json.
- Does the team have its own generators: `find . -name generators.json -not -path '*/node_modules/*'` — a local plugin reveals itself instantly. Found one — read it: it's the most honest documentation of the repo's conventions.
- `grep -B2 -A8 '"generators"' nx.json` — the silent defaults: why `nx g @nx/react:lib` in this repo creates what it creates.
- Don't move, rename or delete a project by hand. Use `nx g @nx/workspace:move --project=X --destination=...` and `@nx/workspace:remove`: they update tsconfig paths, imports and configs for you.
- A built-in generator is habitually invoked with the same five flags (visible in command history/docs)? That's an application for a local wrapper generator.

## What we're adding to the project

A local `workspace-plugin` with a `feature-lib` generator. One command creates a feature lib following chapter 06's conventions: the right directory, importPath, tags, and a stub page. We'll prove it by generating the `checkout` domain, which chapter 10 will need.

## Practical exercise

**Input:** the workspace after chapter 06 (layers, tags, boundaries enabled).

**Task:**

1. Install `@nx/plugin` and generate a local plugin `workspace-plugin` in `tools/workspace-plugin`.
2. Generate a `feature-lib` generator stub inside it and implement the contract:
   - **Input:** `name` (positional, e.g. `cart`), `scope` (e.g. `checkout`);
   - **Validation:** scope must be an existing folder in `libs/` — otherwise a clear error listing the available ones;
   - **Output:** a lib in `libs/<scope>/feature-<name>` with importPath `@mini-shop/<scope>-feature-<name>`, tags `scope:<scope>,type:feature`, bundler none and vitest. Plus a `<Name>Page` component from a template and a re-export in index.ts;
   - **Implementation:** composition with `libraryGenerator` from `@nx/react`; your own files via `generateFiles`.
3. Run with `--dry-run`, then create a real lib: `feature-cart` in the `checkout` scope. Create the scope folder beforehand — or decide how the generator should behave with a brand-new scope, and justify your choice.
4. Verify: `nx lint checkout-feature-cart` is green (the tags fit the boundaries matrix), `nx graph` shows the new lib in the right layer.
5. Write a unit test for the generator: the name `shoppingCart` yields the file `shopping-cart-page.tsx` and the class `ShoppingCartPage`.

**Edge cases to think about:**

- Re-running with the same name — what should happen, and what will happen?
- Why do template files carry a suffix like `.template` and `__fileName__` variables in paths?
- The generator broke after `nx migrate` to a new major — which part is the likely culprit: your templates or the `libraryGenerator` call?

## Worked solution

Steps 1–2 — the plugin and the stub:

```bash
npx nx add @nx/plugin
npx nx g @nx/plugin:plugin workspace-plugin --directory=tools/workspace-plugin \
  --importPath=@mini-shop/workspace-plugin --linter=eslint --unitTestRunner=vitest

npx nx g @nx/plugin:generator feature-lib \
  --path=tools/workspace-plugin/src/generators/feature-lib
```

> **Versions.** The signatures of the `@nx/plugin` generators themselves changed between majors: name and path may be positional or a flag. Check `nx g @nx/plugin:generator --help` for your version. The essence is stable: you get a `generators.json` at the plugin root and a generator folder with four files.

`schema.json` — the contract with the user:

```json
{
  "$schema": "https://json-schema.org/schema",
  "$id": "FeatureLib",
  "title": "A mini-shop feature lib following chapter 06 conventions",
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "description": "The feature name, e.g. cart",
      "$default": { "$source": "argv", "index": 0 },
      "x-prompt": "What is the feature called?"
    },
    "scope": {
      "type": "string",
      "description": "The domain (an existing folder in libs/)",
      "x-prompt": "Which domain (scope) does the feature belong to?"
    }
  },
  "required": ["name", "scope"]
}
```

`generator.ts` — composition + the delta:

```ts
import { formatFiles, generateFiles, names, Tree } from '@nx/devkit';
import { libraryGenerator } from '@nx/react';
import * as path from 'path';
import { FeatureLibGeneratorSchema } from './schema';

export async function featureLibGenerator(tree: Tree, options: FeatureLibGeneratorSchema) {
  const { fileName, className } = names(options.name);

  // Validate scope against reality, not a wiki: the domain list = folders in libs/
  const scopes = tree.children('libs');
  if (!scopes.includes(options.scope)) {
    const known = scopes.join(', ');
    throw new Error(`Unknown scope "${options.scope}". Existing: ${known}`);
  }

  const projectRoot = `libs/${options.scope}/feature-${fileName}`;

  // Composition: the built-in generator does all the heavy lifting —
  // project.json, vite/eslint configs, the alias in tsconfig.base.json
  await libraryGenerator(tree, {
    name: `${options.scope}-feature-${fileName}`,
    directory: projectRoot,
    importPath: `@mini-shop/${options.scope}-feature-${fileName}`,
    tags: `scope:${options.scope},type:feature`,
    style: 'css',
    linter: 'eslint',
    unitTestRunner: 'vitest',
    bundler: 'none',
    component: false,
  });

  // Our delta: the domain page template + the public API
  generateFiles(tree, path.join(__dirname, 'files'), projectRoot, {
    className,
    fileName,
    scope: options.scope,
    tmpl: '',
  });
  tree.write(
    `${projectRoot}/src/index.ts`,
    `export { ${className}Page } from './lib/${fileName}-page';\n`,
  );

  await formatFiles(tree);
}

export default featureLibGenerator;
```

The template `files/src/lib/__fileName__-page.tsx.template`:

```tsx
export function <%= className %>Page() {
  return (
    <section>
      <h2><%= className %></h2>
      {/* TODO: filled in by the feature */}
    </section>
  );
}
```

Both `__fileName__` in the file name and `<%= className %>` in the contents are substitutions from the object passed to `generateFiles`. The `.template` suffix is stripped on generation, and it protects the file from being compiled or linted as part of the plugin itself.

Steps 3–4 — running it. The new-scope decision: **the generator does not create domains silently**. A new domain means new rules in the boundaries matrix (chapter 06), and that's a deliberate architectural act, not a scaffolding side effect. So first `mkdir libs/checkout` (and a line in depConstraints), then:

```bash
npx nx g @mini-shop/workspace-plugin:feature-lib cart --scope=checkout --dry-run
# CREATE libs/checkout/feature-cart/project.json
# CREATE libs/checkout/feature-cart/src/lib/cart-page.tsx
# UPDATE tsconfig.base.json
# ...

npx nx g @mini-shop/workspace-plugin:feature-lib cart --scope=checkout
npx nx lint checkout-feature-cart   # green: the tags fit the matrix immediately
```

Step 5 — a diskless test (the same Tree mechanics):

```ts
import { createTreeWithEmptyWorkspace } from '@nx/devkit/testing';
import { featureLibGenerator } from './generator';

it('canonicalizes the feature name', async () => {
  const tree = createTreeWithEmptyWorkspace();
  tree.write('libs/catalog/.gitkeep', '');

  await featureLibGenerator(tree, { name: 'shoppingCart', scope: 'catalog' });

  const root = 'libs/catalog/feature-shopping-cart';
  expect(tree.exists(`${root}/src/lib/shopping-cart-page.tsx`)).toBe(true);
  expect(tree.read(`${root}/src/index.ts`, 'utf-8')).toContain('ShoppingCartPage');
});
```

Answers to the remaining edge cases:

- A re-run fails inside `libraryGenerator` on the project-name conflict, and that is correct behaviour. Generators promise no idempotency (chapter 01), and "updating" an existing lib is a refactoring task, not scaffolding.
- After `nx migrate` the usual casualty is the `libraryGenerator` call (its options are effectively the neighbouring major's internal API), not your templates. That's the price of composition, and it's lower than the alternative. Without composition you'd be manually chasing every structural change that new Nx makes on its own. The generator's unit test fails first and shows what to fix — which is why it's mandatory, not optional.

## Check yourself

1. Why is `--dry-run` guaranteed to show exactly what a real run would do? Which architectural property of generators ensures it?
2. Our generator calls `libraryGenerator` instead of creating files by hand. List what exactly this composition buys us and what price we pay.
3. A plugin's generator did something you didn't expect. Describe the chain of files in node_modules that leads you to the cause.
4. What is `names()` for, and why must a generator not use the user-typed name as is?
5. The team is debating: record the lib-creation conventions in a wiki or in a generator. Give three arguments for the generator and one honest argument for the wiki.

<details>
<summary>Answers</summary>

1. Dry-run and the real run execute the same implementation code. All writes go to the virtual file system (Tree), and the only difference is the final step: print the diff, or flush to disk. Divergence is impossible by construction: there's no separate "emulation" that could fall behind reality.
2. We get a correctly structured project.json, the alias in tsconfig.base.json, eslint/vite/vitest configs and proper project registration. All of it keeps matching the current Nx version after every upgrade, because the Nx team maintains it. We pay with a dependency on the `libraryGenerator` signature, which can change between majors. After `nx migrate` our generator needs its test run, and possibly its options adjusted.
3. Start with `node_modules/<package>/generators.json`: find the generator's name and take its `schema` and `factory` paths. Then open `schema.json` and check the options and their defaults — often "the unexpected" is a silent default, or one from nx.json. Then read the `factory` file and see the actual logic. It is the same chain as for executors in chapter 03, only the registry is called generators.json.
4. The user will type anything: `shoppingCart`, `Shopping-Cart`, `shopping cart`. The `names()` helper produces canonical forms: fileName `shopping-cart`, className `ShoppingCart`, propertyName `shoppingCart`. So the file structure and class names stay uniform regardless of who invoked the generator and how. Without it, the naming convention dies with the second user.
5. Three arguments for the generator. It executes rather than gets read, so a convention can't be "forgotten". Validations — our scope check — catch mistakes at creation time, not in review. Updating the convention means updating code in one place plus a test, not a "please re-read the wiki" broadcast. The honest argument for the wiki: a generator is code that must be maintained, especially across major Nx upgrades. For a convention applied twice a year, that price may not pay off.

</details>

## Common mistake

A developer writing their first custom generator builds it "from scratch". They hand-create project.json and the vite config via `tree.write`, and they edit tsconfig.base.json. That effectively copies what `@nx/react:lib` does into their own code.

It works for a few months. Then `nx migrate` changes the config structure: say, the repo moves to inferred targets or a new eslint format. The built-in Nx generator updates itself, while the homemade one keeps generating last year's structure.

The right instinct: your generator is a thin wrapper around the built-in one — validations, templates and pinned options. All "infrastructure" generation happens only through composition.

The second mistake is the orphaned generator. It was written with enthusiasm and used for three months. Then the repo's structure moves on — a new tag axis, a different test runner — and the generator isn't updated. Now it creates libs that immediately fail lint, people conclude "generators don't work" and go back to copy-paste.

The cure is disciplinary. The generator has a unit test, so it fails in CI — continuous integration — when it falls behind. And any PR (pull request) that changes the repo's conventions must change the generator too: it's a contract, same as types in an API.
