# Motion Design Patterns and Accessibility

## From technique to product judgment

Everything in articles 01-06 was about WHAT tool to animate with and HOW not to break performance. This article is about WHEN and WHY, and that's exactly what separates a developer who "knows GSAP" from one who makes product decisions about motion on screen. An experienced engineer knows not to slap `will-change` on static elements (article 01); a *professional* knows that in half the cases where animation gets added at all, it shouldn't have been added in the first place.

Accessibility (`prefers-reduced-motion`) isn't a "bonus" subsection tacked onto the end of this article — it's a requirement on the same level of importance as performance. A user with a vestibular disorder who gets physically nauseated by a large parallax animation isn't a hypothetical edge case — it's a real percentage of the audience on any product with meaningful reach.

## Micro-interactions: duration and easing conventions

Industry design systems (Material Design, the Human Interface Guidelines) converge on a similar duration scale for a reason — it reflects how people actually perceive a system's response to their own action:

```txt
~100 ms or less     — press/active state (button press, tap).
                       Should feel almost instant — any delay here
                       reads as "the interface isn't responding,"
                       not as "a nice animation"
150-250 ms           — hover states, small UI transitions
                       (a tooltip revealing, an icon switching)
250-400 ms           — standard state transitions (modal,
                       dropdown, panel)
400 ms+              — emphasis animations (onboarding, a large
                       hero element) — use sparingly, not as the
                       default for the whole interface
```

**Enter reaches the screen faster than exit leaves it** — this isn't an arbitrary convention, it follows from the psychology of waiting: the user initiated the element's appearance and expects an immediate response (fast-out, a sharp start via `ease-out`), whereas an element the user has already "mentally dismissed" disappearing is tolerated fine at a slightly faster pace and doesn't need the same sharp responsiveness:

```css
.modal {
  transition: opacity 0.25s ease-out, transform 0.25s ease-out; /* enter: fast response */
}
.modal.is-closing {
  transition: opacity 0.15s ease-in, transform 0.15s ease-in; /* exit: shorter than enter */
}
```

**Focus states are a separate zone where animation should be restrained, not decorated.** The focus ring (`:focus-visible`) should appear almost instantly: for a keyboard user, a delayed or slowly-fading focus indicator reads as an interface lag, not as polish. Fine details (the outline's color) can be animated, but the indicator's actual appearance shouldn't be deferred by hundreds of milliseconds for the sake of a smooth transition.

## Stagger: why 20-50 ms "feels organic," and this isn't just a technical detail

Article 05 covered the stagger syntax in GSAP/Motion; here's why those specific numbers work and others don't.

```txt
0 ms (all elements at once) — reads as "robotic," unnatural:
  in the real world, synchronous events almost always have a
  small time spread between them; perfect synchrony subconsciously
  reads as "artificial"

20-50 ms between elements   — reads as an organic, "alive"
  sequence — enough for the eye to register a wave of motion,
  not enough for the list to feel slow

100+ ms between elements    — for a short list (5-10 items), this
  already feels drawn out: the user is waiting for the LAST
  element to appear before considering the interface "settled"
```

The direction of the stagger matters just as much as the delay's magnitude: a wave radiating out from the point of user interaction (a button click → elements fly outward from it) or moving in the natural reading direction (left-to-right, top-to-bottom) reinforces the "organic" feel far more than an arbitrary DOM order — GSAP's `stagger: { from: 'center' }` (article 05) exists specifically to control this direction, not just the delay amount.

## Page/state transitions: the shared-element illusion

The "magic" transition where a card in a list smoothly morphs into a hero image on a detail page runs on a single psychological trick: the viewer interprets continuous motion of an object as "this is the same object, just somewhere else" — even though technically it's two different DOM nodes in two different documents/states. The View Transitions API (article 03) and FLIP (article 04) are exactly the mechanics that produce this illusion.

Practical boundaries for using it:

```txt
- Route transition duration — 200-350 ms. Longer, and the user
  is physically waiting on the interface, which reads as slow
  navigation, not as "nice"
- Do NOT block user input while a transition is playing — if
  the user hits "back" mid-animation, the interface should
  respond, not ignore input until the transition finishes
- Do NOT overuse shared-element transitions for UNRELATED
  objects — if card A visually "morphs" into content B that
  isn't actually the same object, the illusion works AGAINST
  the user: it creates a false mental link between unrelated
  entities
```

## Scroll storytelling: pinning, cheap parallax, progress-linked sequences

Brand landing pages (flagship product pages, portfolios, promo sites) often use pinned sections with multi-step animation synced to scroll (article 05, GSAP ScrollTrigger), including frame-by-frame sequences where scroll drives playback of a pre-rendered frame sequence (the signature technique behind Apple-style product pages).

**Parallax "done cheaply" specifically means `transform`, not `background-position`:**

```css
/* ❌ background-position — layout/paint on every scroll frame */
.parallax-layer {
  background-position: center calc(50% + var(--scroll-offset));
}
```

```css
/* ✅ transform — Composite only (article 01) */
.parallax-layer {
  transform: translateY(calc(var(--scroll-offset) * 0.5px));
  will-change: transform; /* targeted, for the duration of active scroll — article 01 */
}
```

**Cost/benefit — stated honestly, not as marketing copy:**

```txt
Cost:
  - High production cost: requires frame-by-frame design work,
    not reusable across pages
  - High risk of jank on weaker devices — this exact pattern is
    behind most of the "it lags on Android" bug reports
    (article 06)
  - Risk of disorientation: "scroll-jacking" (hijacking native
    scroll for custom logic) breaks the user's familiar mental
    model ("I scroll down — the page moves down") and can
    physically make users with vestibular disorders sick
    (see below)

Justified:
  - Marketing/brand pages, where the GOAL is impression and
    engagement, not task completion speed
  - NOT justified in a utility-focused interface (dashboard,
    admin panel, data table) — there the user wants
    predictability and speed, not "a story," and scroll
    storytelling there is a pure anti-pattern that adds friction
    to an ordinary task
```

## Skeleton screens vs. spinners: perceived performance through motion

A spinner only communicates "something is loading, duration unknown" — the user's brain gets no structure to anticipate the result, and the wait subjectively feels longer. A skeleton screen (gray placeholders echoing the shape of the coming content) provides that structure up front — the user sees "a heading goes here, three lines of text here, an image there" before the data even arrives, and that reduces perceived latency, even though the actual load time hasn't changed by a single millisecond.

An important detail that often gets missed: **a skeleton screen shown for a very fast load becomes a source of visual noise itself, not a benefit**:

```javascript
// ✅ Only show a skeleton if loading ACTUALLY takes a noticeable
// amount of time — otherwise, on fast responses the user sees a
// 50 ms flash of skeleton right before the real content, which is
// more distracting than having no loading indicator at all
function useDelayedSkeleton(isLoading, delayMs = 300) {
  const [showSkeleton, setShowSkeleton] = useState(false);
  useEffect(() => {
    if (!isLoading) { setShowSkeleton(false); return; }
    const timer = setTimeout(() => setShowSkeleton(true), delayMs);
    return () => clearTimeout(timer);
  }, [isLoading, delayMs]);
  return showSkeleton;
}
```

The rule: a skeleton screen earns its place for requests that OFTEN take a noticeable amount of time (hundreds of milliseconds or more) — for near-instant responses (a cache hit, local data), any loading indicator at all is wasted visual work the user sees for nothing.

## When NOT to animate: motion as noise

Every animation should carry a specific communicative purpose: draw attention to a change, show a relationship between states, give feedback on an action. If it does none of those three, it's noise, not polish:

```txt
- A table/dashboard with frequently updating data (live quotes,
  real-time metrics) — animating EVERY cell change (numbers
  "bouncing" on every tick) distracts from reading and gets in
  the way of actually parsing the data — a brief highlight on the
  changed cell serves better here than a full value animation

- A form validation error that "shakes" on every retry — beyond
  the first warning, this annoys rather than informs; the user
  already knows the field is invalid

- Animation "because we can" — decorative motion added with no
  purpose ("everything flies in and spins as it enters the
  viewport") — competes for the user's attention against the
  actual task on the page instead of supporting it
```

The professional discipline here is asking "what does this animation COMMUNICATE to the user" every time one gets added — not "does it look cool in isolation."

## `prefers-reduced-motion` — a hard professional requirement, not an option

### What it actually means

`prefers-reduced-motion` isn't an aesthetic preference for "I don't like animations" — it's an OS-level setting that users turn on for a medical reason: **vestibular disorders**. For some people, large-amplitude motion (parallax, big zoom/pan transitions, rotation) physically causes dizziness, nausea, disorientation — the same mechanism as motion sickness in a vehicle. Ignoring this media query in production isn't "unfinished polish" — it's an accessibility barrier with real physical consequences for a portion of the user base.

### Global implementation — systemic, not a per-component afterthought

```css
/* A blunt kill switch — neutralizes animation everywhere
   developers forgot to explicitly account for reduced-motion.
   Useful as a safety net for a legacy codebase, but should NOT
   be the only mechanism (see why below) */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

### Reduced motion does not mean no motion

Bluntly zeroing out every duration (the example above) is a workable safety net, but it isn't the best solution where the animation itself carries meaning — for instance, showing a relationship between an old and a new state. The right pattern is to **replace movement with an opacity cross-fade**, preserving the fact that a transition happened while removing specifically the large-amplitude motion that triggers symptoms:

```css
:root {
  --enter-transform: translateY(20px);
  --enter-duration: 0.3s;
}

@media (prefers-reduced-motion: reduce) {
  :root {
    --enter-transform: none;      /* remove the MOVEMENT */
    --enter-duration: 0.15s;       /* but keep the transition itself */
  }
}

.modal {
  transition: opacity var(--enter-duration), transform var(--enter-duration);
}
.modal.entering {
  opacity: 0;
  transform: var(--enter-transform); /* none under reduced-motion — only
                                         opacity animates, but the state
                                         change is still communicated */
}
```

In JS, the same branching applies to which type of animation you choose (say, dropping a spring with a visible overshoot in favor of a plain linear fade):

```javascript
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const transitionConfig = prefersReducedMotion
  ? { duration: 0.15, ease: 'linear' }               // fade only, no movement/overshoot
  : { type: 'spring', stiffness: 300, damping: 24 }; // full physics

element.animate(
  { opacity: [0, 1] },
  transitionConfig,
);
```

Worth listening for changes, not just checking on load — a user can flip this setting mid-session, in the OS preferences, while your page is open:

```javascript
const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
mediaQuery.addEventListener('change', (e) => {
  applyMotionPreference(e.matches);
});
```

Libraries at the level of Motion offer this as a built-in, app-wide configuration, instead of leaving every component responsible for checking `matchMedia` on its own:

```tsx
import { MotionConfig } from 'motion/react';

<MotionConfig reducedMotion="user">
  <App />
</MotionConfig>
// Every child motion component automatically respects the
// system setting, with no manual checks needed anywhere
```

### Focus management during animated transitions

A separate, often-overlooked piece of animation accessibility: **don't tie focus movement to an animation's completion**. The classic mistake: a modal opens with a 300 ms transition, and focus only moves to the modal's heading on `transitionend`/`animation.finished` — a user working via keyboard or screen reader is forced to wait out a decorative animation before the interface even acknowledges they're "inside" the modal:

```javascript
// ❌ Focus waits for the animation to finish — an unnecessary delay
// for users who don't need or see the animation itself (a screen
// reader, for instance), but the delay entering the modal is very
// much felt
modalElement.animate({ opacity: [0, 1] }, { duration: 300 })
  .finished.then(() => modalTitle.focus());
```

```javascript
// ✅ Focus moves IMMEDIATELY on open — the animation plays in
// parallel, visually, without blocking accessibility
function openModal() {
  modalElement.classList.add('is-open');
  modalTitle.focus();                       // right away
  modalElement.animate({ opacity: [0, 1] }, { duration: 300 }); // the visual layer runs separately
}
```

The same holds symmetrically on close — focus returns to whatever triggered the modal at the moment the close is initiated, not once the exit animation visually finishes. This can feel "premature" to a developer (the content is still visually disappearing), but from an accessibility standpoint the application's state changes at the moment of the user's action — the animation is just a visual illustration of that, and it shouldn't be a bottleneck for interaction speed for users who don't experience the animation the same way a sighted user without vestibular issues does.

## Connection to other articles

```txt
[CSS Transitions and Keyframes] / [Web
 Animations API]                       — the mechanics for implementing
                                          this article's duration/easing
                                          conventions
[rAF and JS-Driven Animation]          — springs (article 04) — the
                                          physical basis for "alive"
                                          micro-interactions, which
                                          reduced-motion swaps out for
                                          a linear fade
[Animation Libraries and Ecosystem]    — MotionConfig and similar
                                          library-level mechanisms
                                          for app-wide reduced-motion
                                          handling
[Performance Debugging and Jank
 Hunting]                               — jank diagnosed on a scroll
                                          storytelling section is a
                                          signal to reconsider the
                                          pattern's cost/benefit, not
                                          just to optimize it technically
```

## Common interview traps

- **Not knowing the duration conventions** — being unable to explain WHY a hover state is shorter than a modal transition, or why exit is usually faster than enter — these aren't arbitrary numbers, they're grounded UX conventions.

- **Treating `prefers-reduced-motion` as "optional polish"** — not knowing it's tied to a real medical condition (vestibular disorders) rather than user aesthetic preference, and treating it as a nice-to-have instead of a hard requirement.

- **Assuming reduced motion means "remove all animation"** — not knowing the pattern of replacing movement with an opacity cross-fade, which preserves the transition's communicative function while removing the symptom-triggering displacement.

- **Tying focus management to an animation's completion** — not understanding that delaying focus until `transitionend`/`animation.finished` creates a real barrier for keyboard/screen-reader users, even if it's invisible to a sighted user with no accessibility needs.

- **Proposing scroll storytelling (pinning, frame-by-frame sequences) for a utility interface** — not distinguishing context: what's justified on a brand landing page is an anti-pattern on a dashboard, where the user values predictability and speed over spectacle.

- **Not knowing about delaying the skeleton screen's appearance** — suggesting a skeleton be shown immediately for any load, unaware that on fast responses this creates an extra visual flash rather than improving perceived performance.

- **Animating frequently-updating data indiscriminately** — not seeing the difference between animation that helps register a change (a soft highlight) and animation that gets in the way of reading the data itself (a full bounce on every update of a real-time table).
