# A pipeline run: what Playwright asks of the build machine

On a build server a test runs in a different environment: another operating
system, other fonts, another time zone and half the processor cores. That
automatic build-and-check setup is usually called CI (continuous integration).
The gap between machines is predictable, and it is closed by project settings
plus the right packaging of the run.

## Anything the config does not pin comes from the machine

A test does not live in a vacuum. The time zone, the language, the window size
and the fonts all come from the system unless you say otherwise.

```txt
                The same test on two machines
┌─────────────────────────┐  ┌───────────────────────────────┐
│ A developer laptop      │  │ A build machine               │
│                         │  │                               │
│ system: macOS           │  │ system: Linux in a container  │
│ fonts: the system ones  │  │ fonts: whatever was installed │
│ screen: retina, x2      │  │ screen: none at all           │
│ zone: Europe/Bratislava │  │ zone: UTC                     │
│ language: en-US         │  │ language: C or en-US          │
│ cores: 11               │  │ cores: 2                      │
└─────────────────────────┘  └───────────────────────────────┘
   anything the config does not pin comes from the machine:
   the date, number formats, window size, even font shapes
```

One run is enough to see it. Below are two tests that differ only in whether they
pin the environment.

```ts
// tests/env.spec.ts
test.describe('pinned environment', () => {
  test.use({ timezoneId: 'Europe/Kyiv', locale: 'uk-UA',
             viewport: { width: 1280, height: 720 } });

  test('pinned', async ({ page }) => {
    await page.goto('/tasks');
    const date = await page.evaluate(
      () => new Date('2026-09-18T21:30:00Z').toLocaleString());
    console.log(`  date: ${date}`);
  });
});
```

The same moment in time prints differently.

```txt
timeZone: Europe/Kiev
locale:   uk-UA
viewport: 1280x720
date:     19.09.2026, 00:30:00

timeZone: Europe/Bratislava
locale:   en-US
viewport: 1280x720
date:     9/18/2026, 11:30:00 PM
```

The gap is not only in the format: for the first test it is already the
nineteenth of September, for the second it is still the eighteenth. A test that
compares a date on the page against an expected one will fail at night until the
time zone is pinned. The language matters the same way, because `toLocaleString`
and string sorting both follow the locale.

```ts
// playwright.config.ts — the environment stated once, the same everywhere
export default defineConfig({
  use: {
    timezoneId: 'Europe/Kyiv',
    locale: 'uk-UA',
    viewport: { width: 1280, height: 720 },
    colorScheme: 'light',
  },
});
```

## A container removes the rest of the gap

The time zone and the language come from the config, but the browser build, the
font set and the system libraries do not. A ready-made image evens those out, and
one is published for every version of the package.

```yaml
# a build job fragment: the image version matches the package version
container:
  image: mcr.microsoft.com/playwright:v1.63.0-noble
```

Matching versions here is mandatory, not nice to have. The image carries the
browser builds inside, so a mismatch makes the package either download its own or
refuse to start. Without an image, the browsers and their system dependencies are
installed by hand.

```bash
# on a bare machine: browsers plus the system libraries they need
npx playwright install --with-deps chromium
```

How the pipeline itself is built — steps, caches, permissions, environments — is
the subject of the neighbouring topic on continuous delivery and operations,
called CI/CD & DevOps (development and operations). What matters here is only
what Playwright itself asks for: a container or an install with dependencies, a
worker count that matches the cores, and somewhere to put the artefacts.

## Sharding in a matrix, and one report out of many

Sharding splits the suite between machines, but each machine ends up with its own
piece of the report. To make it one report again, the shards write an
intermediate `blob` format that is merged afterwards.

```yaml
# a matrix fragment: four machines, each with its share of the suite
strategy:
  matrix:
    shard: [1, 2, 3, 4]
steps:
  - run: npx playwright test --shard=${{ matrix.shard }}/4 --reporter=blob
```

Every run drops its archive into the `blob-report` directory. Those archives are
gathered in one place and glued together by a single command.

```bash
npx playwright merge-reports --reporter=html ./all-blob-reports
```

Merging is a report pass, not a second run of the tests.

```txt
Running 4 tests using 2 workers

✓  1 [chromium] › tests/part1.spec.ts:3:5 › part 1: list (88ms)
✓  2 [chromium] › tests/part1.spec.ts:8:5 › part 1: pages (60ms)
✓  3 [chromium] › tests/part2.spec.ts:3:5 › part 2: list (72ms)
✓  4 [chromium] › tests/part2.spec.ts:8:5 › part 2: pages (53ms)

4 passed (1.6s)
```

## A visual baseline belongs to one browser and one system

Image comparison compares pixels, and pixels depend on who drew them. Playwright
knows that and writes the browser and system names into the baseline file name.

```ts
test('the list matches the baseline', async ({ page }) => {
  await page.goto('/tasks');
  await expect(page.getByRole('listitem')).toHaveCount(20);

  await expect(page).toHaveScreenshot('tasks.png');
});
```

On the first run there is no baseline yet, so the test fails and stores the shot.

```txt
Error: A snapshot doesn't exist at
  tests/vis.spec.ts-snapshots/tasks-chromium-darwin.png,
  writing actual.
```

The `chromium-darwin` suffix answers the question "why does it not match for my
colleague". A baseline taken on macOS in Chromium fits neither another browser
nor Linux in a container. Hence the practice: record baselines in the same image
that later checks them.

When the images diverge, the report says by how much.

```txt
Error: expect(page).toHaveScreenshot(expected) failed

  3984 pixels (ratio 0.01 of all image pixels) are different.
  Snapshot: tasks.png

Call log:
  - Expect "toHaveScreenshot(tasks.png)" with timeout 5000ms
  - taking page screenshot
    - disabled all CSS animations
    - waiting for fonts to load...
    - fonts loaded
  - 3984 pixels (ratio 0.01 of all image pixels) are different.
  - waiting 100ms before taking screenshot
  - captured a stable screenshot
```

The log also shows the tool fighting for repeatability on its own: it switches
animations off, waits for fonts, and takes the shot twice until it stops
changing. Three files are left next to the report: expected, actual and the
difference between them.

| option | what it is for |
|---|---|
| `maxDiffPixels` | a pixel allowance for small anti-aliasing differences |
| `maxDiffPixelRatio` | the same allowance as a share of the image area |
| `threshold` | how different a pixel must be to count as different |
| `mask` | cover the volatile parts: a date, an avatar, an advert |
| `stylePath` | attach styles that hide animation and moving content |
| `animations` | animations are disabled during the shot by default |

## Updating baselines is a separate operation

Baselines never update themselves: until you say so, a difference counts as a
defect.

```bash
# redraw only the baselines that changed
npx playwright test --update-snapshots=changed
```

There are four modes, and the help output lists them: `all` rewrites every
baseline, `changed` only the differing ones, `missing` only the absent ones,
`none` writes nothing. Without the flag the mode is `missing`; the flag with no
value means `changed`.

Redraw baselines where they are checked. Updating on a laptop and then checking
in a container is the most common way to get a permanently red test.

## Artefacts and caches: what to upload, what not to store

Artefacts are needed after the run, so the pipeline uploads them as files. Three
things are usually worth it: the report, traces of failed tests, and the images
of mismatched screenshots.

```yaml
# a job fragment: keep the report even when tests failed
- uses: actions/upload-artifact@v4
  if: always()
  with:
    name: playwright-report
    path: playwright-report/
    retention-days: 7
```

Caching goes the other way. Browser builds live in a system directory and take
hundreds of megabytes: on my machine it is 557 megabytes for three components.
The official advice is not to cache browsers, because restoring the cache takes
about as long as downloading them, and the system dependencies cannot be cached
at all. Cache what caches cheaply: the `npm` dependencies.

## Common mistakes

- **Recording baselines on a laptop and checking them in a container.** The
  symptom: the test is red for everyone except the author of the baseline.
- **Letting the image version and the package version drift apart.** The symptom:
  the containerised run downloads browsers or fails to start.
- **Using the same worker count as locally.** The symptom: on two cores the tests
  start failing on timeouts, because they fight over the processor.
- **Forgetting `if: always()` on the upload step.** The symptom: the report
  exists only for green runs, exactly when nobody needs it.

## Related topics

- [A flaky test is worse than no test](./08-flakiness-and-parallelism.md) — how
  to split a suite between machines and why a retry is not an investigation.
- [A failing test should explain itself](./07-debugging.md) — what sits in the
  trace you upload from the pipeline.
- [The Playwright model: browser, context, page](./01-playwright-model.md) — why
  the browser version is tied to the package version.
- Continuous delivery and operations, the CI/CD & DevOps topic — the pipelines
  themselves: steps, environments, permissions and release strategies.
