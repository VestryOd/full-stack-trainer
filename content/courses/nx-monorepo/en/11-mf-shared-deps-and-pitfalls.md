# Shared dependencies and federation pitfalls

## Theory

This is the most "painful" chapter of the course. Everything described here is a real incident, and it happens regularly in projects built on Module Federation (MF). The good news: the list is finite, and almost everything is diagnosable in minutes once you know the mechanics.

### What Nx shares by default

We wrote nothing about shared in `module-federation.config.ts` — yet the negotiation from chapter 09 works. That's because the Nx plugin does the sharing **by itself**. It shares every npm package from package.json, takes `requiredVersion` from there, and marks react and its family as singletons.

An important Nx specialty: **workspace libs are shared too**. The libs `shared-ui`, `shared-util` and the rest land in the shared scope as singleton modules. The tuning knob is the `shared` function in the config:

```ts
const config: ModuleFederationConfig = {
  name: 'catalog',
  exposes: { './Module': './src/remote-entry.ts' },
  // for each candidate: false = don't share, undefined = the Nx default,
  // an object = your own singleton/strictVersion/requiredVersion
  shared: (name, defaults) => {
    if (name === 'react') return { ...defaults, strictVersion: true };
    return undefined;
  },
};
```

### Two reacts: why it's the hooks that break

From chapter 09 we know react is always `singleton: true`. Here's the failure mechanics when that's violated. React keeps state *at the module-instance level*: each react copy has its own internal hooks dispatcher (the very reference `useState` dereferences when called).

The host's react renders a component → the dispatcher is set on **its** copy. But the catalog component was compiled against **its own** copy of react — its `useState` looks at the second copy's dispatcher, which is `null`. The result is the famous **"Invalid hook call"**, whose official cause list literally includes "more than one copy of React".

Same story with Context. A `createContext` in copy A and a `useContext` in copy B operate on different objects. The host's theme provider is then invisible to the remote's components. The symptom is sneakier than hooks: nothing crashes, the remote just "didn't get the theme", or `useContext` returned the default.

Diagnosing duplicate reacts takes 30 seconds. In the console, read `__REACT_DEVTOOLS_GLOBAL_HOOK__.renderers.size`: more than 1 means both copies are live. Then open the Network tab and look for react chunks inside a remote's bundle, where react should have come from shared.

### Versions: the warning you must not ignore

Suppose the singleton is in place, but versions drift: the host was built with react 18.3, and a remote requires ^19. The console then shows a warning like `Unsatisfied version 19.0.0 ... of shared singleton module react (required ^18.3.0)`. And **the first one to load wins**.

The app keeps running on the "wrong" version. Maybe it's fine. Maybe the remote calls an API that isn't there. `strictVersion: true` turns this into a remote-load error. That is harsh, but the failure lands at the boundary — where our chapter 10 RemoteBoundary catches it — instead of deep inside a render.

Pragmatics: for react, the router and state libraries, take strictVersion plus upgrade discipline. Production console warnings are not noise, they are drift telemetry.

### Workspace libs under federation: the subtlest part

Since Nx shares `shared-ui` as a singleton, there's one Button instance per page. Sounds great — until you remember MF's superpower, **independent deploys**:

- on Monday, catalog is deployed — its artifact contains *yesterday's* shared-ui;
- on Wednesday, Button is changed and only checkout is deployed — its artifact carries the *new* shared-ui;
- a user opens the page: the shared scope picks **one** shared-ui instance — whose? Both sides declare the same "version" (a workspace lib has no npm version), so the first to load wins. If catalog loaded first, checkout runs with *yesterday's* Button — one that no longer exists in its own sources.

That's the last row of the table below — a remote showing a stale, foreign interface. A monorepo *does not protect* you from version skew when deploys are unsynchronized. You *build* from one commit, but you *live* in production with artifacts from different commits. Three working strategies:

1. **Backward compatibility of shared libs** as the norm. Change Button by addition, not by reshaping. A breaking change goes through a new component or prop, and the old one is marked deprecated.
2. **Coordinated deployment** of the affected parts: shared-ui changed → `nx affected` knows every consumer (chapter 05) → deploy them together. The honest price: the thicker the shared layer, the less independent the deploys.
3. **Don't share** a specific lib (`shared: (n) => n === '@mini-shop/shared-ui' ? false : undefined`): each remote ships its own copy. The price — bundle size and a ban on Context/state inside the lib (there are two copies now); the payoff — full version independence.

Choosing among 1–3 is a team-level architectural decision, not a config line "to taste".

### Typing between host and remote

The `remotes.d.ts` from chapter 10 is a manual promise. Module Federation 2.0 does better. Building a remote generates a types package for its exposes (`@mf-types`), and the host pulls that package in. Your editor and tsc then see the real signature of `catalog/Module`.

Be sober about the guarantee: the types match the remote **at generation time**. A production remote deployed later may have changed, and compiling the host against fresh types won't catch that. So MF types are a *development* tool. The *production* contract is guarded by process: contract tests and end-to-end (e2e) tests of the pair, plus canary deploys of remotes.

### The incident table

```
                federation incidents
┌─────────────────────────────────────────────────┐
│ eager consumption error                         │
│   typical cause: missing async boundary         │
│   first check: main.ts = import("./bootstrap")? │
├─────────────────────────────────────────────────┤
│ Invalid hook call                               │
│   typical cause: two react instances            │
│   first check: devtools: renderers.size > 1?    │
├─────────────────────────────────────────────────┤
│ warning: unsatisfied version                    │
│   typical cause: shared versions drifted        │
│   first check: what each remoteEntry declares   │
├─────────────────────────────────────────────────┤
│ 404 or CORS (cross-origin) on remoteEntry.js    │
│   typical cause: remote's address or deploy     │
│   first check: curl the config/manifest URL     │
├─────────────────────────────────────────────────┤
│ remote shows a stale, foreign interface         │
│   typical cause: workspace lib: first wins      │
│   first check: when each remote was deployed    │
└─────────────────────────────────────────────────┘
```

On "eager consumption", the mechanics come from chapters 09–10. Code that synchronously consumes a shared module ran before negotiation managed to put that module into the shared scope. The cure is to restore the async boundary, `import('./bootstrap')`.

For the host's truly startup-critical dependencies there is a second cure, `eager: true`. The module then ships in the initial bundle and doesn't wait for negotiation.

## In a real-world monorepo

- Production, browser console: filter for "Unsatisfied" and "shared" — any warnings? That's your federation's version-drift map, free telemetry.
- `__REACT_DEVTOOLS_GLOBAL_HOOK__.renderers.size` in production — the quick duplicate-react test. While you are there, check the design system in Network: is it arriving in several remotes' chunks?
- In every app's module-federation.config: is there a `shared` function with overrides, and why (git blame those lines — an incident usually stands behind every `false`).
- Find out the team's strategy for shared workspace libs: compatibility / coordinated deploys / no sharing? If nobody can answer, the strategy is "whatever happens", and the first-wins incident is ahead of you.
- Is MF type generation in place (`@mf-types` in artifacts, dts options in the config)? And does continuous integration (CI) build the host against the remotes' fresh types? That pair is the contract check.

## What we're adding to the project

The mini-shop code is unchanged at the end of this chapter. Along the way, though, we break it twice. We reproduce the eager error and the duplicate-react conflict, diagnose both incidents with standard tools, and fix them. Plus we prove that shared-ui really exists in a single instance.

## Practical exercise

**Input:** the federation from chapter 10 (host + catalog + checkout).

**Task:**

1. **Prove shared-ui sharing.** Add a temporary side effect to the Button module: `console.log('[shared-ui] module loaded')`. Visit `/catalog` and `/checkout`. How many times did the log fire? Explain, then remove the log.
2. **Reproduce the eager error.** Inline the contents of bootstrap.tsx straight into main.ts (removing `import('./bootstrap')`). Record the exact error text, explain the mechanics, revert.
3. **Reproduce two reacts.** In the catalog's module-federation.config, exclude react from shared (`shared: (name) => name === 'react' ? false : undefined`). Open `/catalog`, record the error. Diagnose: `renderers.size` in the console, the react chunk in Network inside the catalog bundle. Revert.
4. **Tighten the contract.** In the host, declare `strictVersion: true` for react (with requiredVersion from package.json). Verify the federation works as before. Then answer two questions in writing. What happens now instead of the "quiet warning" on version drift? Where will that error be caught?
5. **Dissect first-wins.** Walk this scenario in writing, step by step: catalog deployed Monday, Button changed Tuesday, checkout deployed Wednesday. Which Button does the user see on `/checkout`, and why? Pick a strategy for mini-shop (compatibility / coordinated deploys / no sharing) and justify it.

**Edge cases to think about:**

- Why is `shared: () => false` for *all* workspace libs a bad default, even though it "removes" first-wins?
- The design system keeps the current theme in a React Context. What happens if you stop sharing it?
- Can strictVersion help against first-wins for workspace libs?

## Worked solution

**Step 1.** The log fires **once**, on the first visit to either remote. The shared-ui lib entered the shared scope as a singleton, and the second remote received the already-initialized module. That's the Nx default for workspace libs in action.

**Step 2.** After inlining bootstrap:

```
Uncaught Error: Shared module is not available for
  eager consumption: webpack/sharing/consume/default/react/react
```

The mechanics: `createRoot` and JSX (the markup syntax React compiles into calls) execute in the synchronous startup chunk. The shared react hasn't been negotiated yet, because negotiation is async. The `import('./bootstrap')` call gives the bundler the break point: container init and the shared scope first, application code second. The revert = restore the two-file pair.

**Step 3.** The experiment config:

```ts
// apps/catalog/module-federation.config.ts — an EXPERIMENT, do not merge
const config: ModuleFederationConfig = {
  name: 'catalog',
  exposes: { './Module': './src/remote-entry.ts' },
  shared: (name) => (name === 'react' ? false : undefined),
};
```

Now catalog bundles its own react. The host renders CatalogPage with the host's react, but the page's own code calls `useState` from the catalog's copy — a foreign dispatcher:

```
Uncaught Error: Invalid hook call. Hooks can only be called
inside of the body of a function component.
```

The diagnostics confirm it: `__REACT_DEVTOOLS_GLOBAL_HOOK__.renderers.size === 2`, and in Network a react chunk arrives with the catalog bundle. Note: the error was caught by chapter 10's RemoteBoundary — the catalog route failed, not the whole app. Reverting the config restores the singleton.

**Step 4.** The tightening:

```ts
// apps/shell/module-federation.config.ts
const config: ModuleFederationConfig = {
  name: 'shell',
  remotes: ['catalog', 'checkout'],
  shared: (name, defaults) =>
    name === 'react' || name === 'react-dom'
      ? { ...defaults, singleton: true, strictVersion: true }
      : undefined,
};
```

On a future drift — say, a remote built against react 19 — there will be no warning and no first-wins. There will be an error **at remote load time**, that is, at the boundary, where RemoteBoundary shows the fallback. A deliberate trade-off: an unavailable catalog with a clear error in monitoring versus "works, but unpredictably".

**Step 5.** The user on `/checkout` sees **yesterday's** Button if catalog initialized first — say, the user entered through `/catalog`. The catalog's shared-ui claimed the singleton slot, and checkout, deployed with the new version, received someone else's old module. Worse, the behaviour depends on navigation order: straight to `/checkout` gives the new button, via the catalog the old one.

For mini-shop we choose strategy 1+2. The shared-ui lib evolves backward-compatibly. On a breaking change, `nx affected` tells us whom to deploy together, and chapters 05 and 13 turn that into CI automation.

Answers to the edge cases:

- A blanket `false` for workspace libs cures first-wins at the cost of everything sharing exists for. Every remote ships its own copies of the ui and util libs, which costs bundle size. Worse, any Context or state in those libs stops being common. Duplication-by-default is microfrontends without the monorepo benefits, while a *targeted* `false` for one problematic lib is a legitimate tool.
- A theme in Context plus an unshared design system is exactly the "two createContexts" case. The ThemeProvider from the host copy is invisible to the remote copies, so remotes get the default theme. Libs with Context or state must be shared as singletons — or the state must move out of them.
- No. The strictVersion flag compares versions, and workspace libs have no version at all (or everyone's is the same, "0.0.0"). Drift in *content* under an identical version is invisible to strictVersion. Against first-wins only the theory's strategies work: compatibility, coordinated deploys, or not sharing.

## Check yourself

1. Describe the chain by which two react instances produce "Invalid hook call" — where exactly does the state that diverges live?
2. Why doesn't a monorepo protect a federation from shared-lib version skew even though everyone builds from one repository? What are the three defence strategies and the price of each?
3. An "Unsatisfied version of shared singleton module" warning in production: what actually happened, what's the risk, and what does strictVersion change?
4. What does MF 2.0 type generation between host and remote guarantee, and what does it **not** guarantee? What complements the contract for production?
5. A developer hit "Invalid hook call" and, following internet advice, deleted node_modules, ran `npm dedupe` and added resolutions. It didn't help. Why were those actions off-target in an MF project, and what's the correct diagnostic sequence?

<details>
<summary>Answers</summary>

1. The react module internally keeps a reference to the current hooks dispatcher, which the renderer sets before invoking a component. The host's react renders the component and sets the dispatcher on **its** copy. The component's code was compiled importing **another** copy, so its `useState` reads the dispatcher of the copy where it was never set. Context objects and the scheduler diverge the same way. The "which dispatcher is current" state is per-module, so two module copies = two disconnected worlds.
2. Build and deploy live on different time axes. Everything builds from one commit, but the artifacts in production come from different commits, because each remote was deployed at its own moment. A workspace lib in the shared scope is a singleton without a meaningful version. The first to load wins, and its content may be older than everyone else's. Strategy (a) is backward compatibility of shared libs; its price is discipline in how their API evolves. Strategy (b) is coordinated deployment of everything affected, via affected; its price is less independent deploys. Strategy (c) is not sharing a given lib; its price is bundle duplication and no common Context or state inside it.
3. Negotiation found that one participant's declared range isn't satisfied by the version that landed in the shared scope. But because of singleton it took what was there and moved on. The risk is runtime behaviour of the "wrong" version, from harmless to calling a nonexistent API deep inside a render. The strictVersion flag moves the failure to remote load time. You get an error at the boundary — caught by the error boundary, visible in monitoring as a load failure — instead of unpredictability inside.
4. It guarantees this much: at type *generation* time, the exposes signatures match the remote's real code. You get editor autocomplete, and tsc fails on incompatibility when the host builds. It does not guarantee that the remote running in production is the same one: it may have been deployed later with a different contract. The complement is process. CI builds the host against all remotes' fresh types (the contract check), e2e tests cover the pair, and remotes go out as canary deploys.
5. All three actions cure "two react versions in node_modules", a disease of the single-app npm world. In a federation the second react arrives not from the host's node_modules but **over the network in a remote's bundle**. Deduplicating local dependencies can't touch it. The correct sequence has four steps. First, `renderers.size` in the console, to confirm the duplicate. Second, the Network tab, to see whose bundle shipped the second react. Third, that app's module-federation.config, to find out why react isn't shared — excluded, or singleton broken. Fourth, fix the shared config.

</details>

## Common mistake

"Invalid hook call" trails an enormous internet legacy from the single-app world, where its cause is two react versions in node_modules. A developer coming from there habitually treats it with `npm dedupe`, resolutions and lock-file regeneration. It doesn't help.

In a federation the second react arrives **over the network from a neighbouring app's bundle**, somewhere npm tooling never looks. The first reflex in an MF project is different: `renderers.size` → Network → the shared config. The diagnostic direction is "what loaded into the browser", not "what's in node_modules".

The second mistake is strategic: the team believes the monorepo automatically protects the federation from drift ("we build everything from one commit"). Build — yes. But you *live* in production with artifacts from different commits, because deploys are independent, and that is the entire point of MF.

While shared workspace libs change backward-compatibly, the illusion holds. The first breaking Button refactor plus unsynchronized remote deploys produces a floating bug that depends on the user's navigation order. The shared-libs strategy (compatibility / coordinated deploys / no sharing) must be chosen and written down before the first incident, not after.
