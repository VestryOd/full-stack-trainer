# Motion Design Patterns and Accessibility

## From technique to product judgment

Everything in articles 01-06 was about **what** tool to animate with and **how** not to break performance. This article is about **when** and **why**. That is exactly what separates a developer who knows GSAP (the GreenSock Animation Platform) from one who makes product decisions about motion on screen.

An experienced engineer knows not to put `will-change` on static elements (article 01). A *professional* knows something else: in half the cases where animation gets added at all, it should not have been added.

Accessibility (`prefers-reduced-motion`) isn't a "bonus" subsection added at the end of this article. It's a requirement as important as performance. Some users have a vestibular disorder, and a large parallax animation makes them physically nauseated. That isn't a hypothetical edge case. On any product with meaningful reach it's a real percentage of the audience.

## Micro-interactions: duration and easing conventions

Industry design systems (Material Design, the Human Interface Guidelines) converge on a similar duration scale. That isn't a coincidence: the scale reflects how people actually perceive a system's response to their own action:

```txt
~100 ms or less     — press/active state (button press, tap).
                       Should feel almost instant — any delay here
                       feels like "the interface isn't responding,"
                       not as "a nice animation"
150-250 ms           — hover states, small UI transitions
                       (a tooltip revealing, an icon switching)
250-400 ms           — standard state transitions (modal,
                       dropdown, panel)
400 ms+              — emphasis animations (onboarding, a large
                       hero element) — use sparingly, not as the
                       default for the whole interface
```

**Exit leaves the screen faster than enter arrives.** This isn't an arbitrary convention. It follows from the psychology of waiting: the user started the element's appearance and expects an immediate response.

So enter gets a sharp start (`ease-out`) and the full standard duration. Exit is the other case, because the user has already "mentally dismissed" the element. A shorter duration there feels tidy rather than abrupt, and it needs none of that sharp responsiveness:

```css
.modal {
  transition: opacity 0.25s ease-out, transform 0.25s ease-out; /* enter: fast response */
}
.modal.is-closing {
  transition: opacity 0.15s ease-in, transform 0.15s ease-in; /* exit: shorter than enter */
}
```

**Focus states are a separate zone where animation should be restrained, not decorated.** The focus ring (`:focus-visible`) should appear almost instantly. For a keyboard user, a delayed or slowly-fading focus indicator looks like interface lag, not like polish.

Fine details such as the outline's color can be animated. The indicator's actual appearance, though, shouldn't be deferred by hundreds of milliseconds for the sake of a smooth transition.

## Stagger: why 20-50 ms "feels organic," and this isn't just a technical detail

Article 05 covered the stagger syntax in GSAP/Motion; here's why those specific numbers work and others don't.

```txt
0 ms (all elements at once) — looks "robotic," unnatural:
  in the real world, synchronous events almost always have a
  small time spread between them; perfect synchrony subconsciously
  feels "artificial"

20-50 ms between elements   — looks like an organic, "alive"
  sequence — enough for the eye to register a wave of motion,
  not enough for the list to feel slow

100+ ms between elements    — for a short list (5-10 items), this
  already feels drawn out: the user is waiting for the last
  element to appear before considering the interface "settled"
```

The direction of the stagger matters just as much as the size of the delay. Two directions reinforce the "organic" feel:

| Direction | What it looks like |
|---|---|
| Radiating out from the point of interaction | A button click, and elements fly outward from it. |
| Following the natural reading order | Left-to-right, top-to-bottom. |

Either one beats an arbitrary order in the DOM (document object model — the tree of page elements). GSAP's `stagger: { from: 'center' }` (article 05) exists specifically to control this direction, not just the delay amount.

## Page/state transitions: the shared-element illusion

The "magic" transition where a card in a list smoothly morphs into a hero image on a detail page runs on one psychological trick. The viewer interprets continuous motion of an object as "this is the same object, just somewhere else". Technically it's two different DOM nodes in two different documents or states.

The View Transitions API (article 03) and FLIP — First, Last, Invert, Play (article 04) — are exactly the mechanics that produce this illusion.

Practical boundaries for using it:

```txt
- Route transition duration — 200-350 ms. Longer, and the user
  is physically waiting on the interface, which feels like slow
  navigation, not as "nice"
- Do not block user input while a transition is playing — if
  the user hits "back" mid-animation, the interface should
  respond, not ignore input until the transition finishes
- Do not overuse shared-element transitions for unrelated
  objects — if card A visually "morphs" into content B that
  isn't actually the same object, the illusion works against
  the user: it creates a false mental link between unrelated
  entities
```

## Scroll storytelling: pinning, cheap parallax, progress-linked sequences

Brand landing pages — flagship product pages, portfolios, promo sites — often use pinned sections with multi-step animation synced to scroll (article 05, GSAP ScrollTrigger). That includes frame-by-frame sequences, where scroll drives playback of a pre-rendered frame sequence. This is the signature technique behind Apple-style product pages.

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
  - Marketing/brand pages, where the goal is impression and
    engagement, not task completion speed
  - Not justified in a utility-focused interface (dashboard,
    admin panel, data table) — there the user wants
    predictability and speed, not "a story," and scroll
    storytelling there is a pure anti-pattern that adds friction
    to an ordinary task
```

## Skeleton screens vs. spinners: perceived performance through motion

A spinner only communicates "something is loading, duration unknown". The user's brain gets no structure to anticipate the result, so the wait subjectively feels longer.

A skeleton screen is a set of gray placeholders echoing the shape of the coming content, and it provides that structure in advance. The user sees "a heading goes here, three lines of text here, an image there" before the data even arrives.

That reduces perceived latency, even though the actual load time hasn't changed by a single millisecond.

One detail often gets missed: **a skeleton screen shown for a very fast load becomes visual noise itself, not a benefit**:

```javascript
// ✅ Only show a skeleton if loading actually takes a noticeable
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

The rule: show a skeleton screen for requests that **often** take a noticeable amount of time, meaning hundreds of milliseconds or more. For near-instant responses — a cache hit, local data — any loading indicator at all is wasted visual work that the user sees for nothing.

## When *not* to animate: motion as noise

Every animation should carry a specific communicative purpose: draw attention to a change, show a relationship between states, give feedback on an action. If it does none of those three, it's noise, not polish:

```txt
- A table/dashboard with frequently updating data (live quotes,
  real-time metrics) — animating every cell change (numbers
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

The professional discipline here is one question, asked every time an animation gets added: "what does this animation communicate to the user"? Not "does it look cool in isolation".

## `prefers-reduced-motion` — a hard professional requirement, not an option

### What it actually means

`prefers-reduced-motion` isn't an aesthetic preference for "I don't like animations". It's a setting in the operating system, and users turn it on for a medical reason: **vestibular disorders**. For some people, large-amplitude motion — parallax, big zoom or pan transitions, rotation — physically causes dizziness, nausea and disorientation. It's the same mechanism as motion sickness in a vehicle.

Ignoring this media query in production isn't "unfinished polish". It's an accessibility barrier with real physical consequences for a portion of the user base.

### Global implementation — systemic, not a per-component afterthought

```css
/* A blunt global override — neutralizes animation everywhere
   developers forgot to explicitly account for reduced-motion.
   Useful as a safety net for a legacy codebase, but it should
   not be the only mechanism (see why below) */
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

Bluntly zeroing out every duration, as the example above does, is a workable safety net. It isn't the best solution where the animation itself carries meaning — showing a relationship between an old and a new state, for instance.

The right pattern is to **replace movement with an opacity cross-fade**. That preserves the fact that a transition happened, and removes specifically the large-amplitude motion that triggers symptoms:

```css
:root {
  --enter-transform: translateY(20px);
  --enter-duration: 0.3s;
}

@media (prefers-reduced-motion: reduce) {
  :root {
    --enter-transform: none;      /* remove the movement */
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

In JS, the same branching applies to which type of animation you choose. For example, a spring with a visible overshoot gives way to a plain linear fade:

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

Worth listening for changes, not just checking on load. A user can switch this setting mid-session, in the system preferences, while your page is open:

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

A separate, often-overlooked piece of animation accessibility: **don't tie focus movement to an animation's completion**.

The classic mistake looks like this. A modal opens with a 300 ms transition, and focus moves to the modal's heading only on `transitionend`/`animation.finished`. A user working via keyboard or screen reader then has to wait for a decorative animation to finish. Only after that does the interface acknowledge they're "inside" the modal:

```javascript
// ❌ Focus waits for the animation to finish — an unnecessary delay
// for users who don't need or see the animation itself (a screen
// reader, for instance), but the delay entering the modal is very
// much felt
modalElement.animate({ opacity: [0, 1] }, { duration: 300 })
  .finished.then(() => modalTitle.focus());
```

```javascript
// ✅ Focus moves immediately on open — the animation plays in
// parallel, visually, without blocking accessibility
function openModal() {
  modalElement.classList.add('is-open');
  modalTitle.focus();                       // right away
  // the visual layer runs separately
  modalElement.animate({ opacity: [0, 1] }, { duration: 300 });
}
```

The same holds symmetrically on close. Focus returns to whatever triggered the modal at the moment the close is initiated, not once the exit animation visually finishes.

To a developer this can feel "premature", because the content is still visually disappearing. From an accessibility standpoint, though, the application's state changes at the moment of the user's action.

The animation is only a visual illustration of that change. It shouldn't be a bottleneck for interaction speed. Some users don't experience the animation the way a sighted user without vestibular issues does.

## Connection to other articles

| Article | What it gives this one |
|---|---|
| [CSS Transitions and Keyframes](./02-css-transitions-and-keyframes.md) and [Web Animations API](./03-web-animations-api.md) | The mechanics for implementing the duration and easing conventions above. |
| [requestAnimationFrame and JS-Driven Animation](./04-raf-and-js-driven-animation.md) | Springs (article 04) — the physical basis for "alive" micro-interactions, which reduced motion swaps for a linear fade. |
| [Animation Libraries and the Ecosystem](./05-animation-libraries-and-ecosystem.md) | `MotionConfig` and similar library-level mechanisms for app-wide reduced-motion handling. |
| [Performance Debugging and Jank Hunting](./06-performance-debugging-and-jank-hunting.md) | Jank diagnosed on a scroll storytelling section is a signal. Reconsider the pattern's cost and benefit, not just optimize it technically. |

## Common interview traps

- **Not knowing the duration conventions.** Being unable to explain **why** a hover state is shorter than a modal transition. Or why exit is usually faster than enter. These aren't arbitrary numbers, they're grounded conventions of UX (user experience).

- **Treating `prefers-reduced-motion` as "optional polish".** Not knowing that it's tied to a real medical condition — vestibular disorders — rather than to a user's aesthetic preference. Treating it as a nice-to-have instead of a hard requirement.

- **Assuming reduced motion means "remove all animation".** Not knowing the pattern of replacing movement with an opacity cross-fade. That pattern keeps the transition's communicative function and removes the displacement that triggers symptoms.

- **Tying focus management to an animation's completion.** Not understanding that a delay until `transitionend`/`animation.finished` creates a real barrier for keyboard and screen-reader users. It's invisible to a sighted user with no accessibility needs, and it's still a barrier.

- **Proposing scroll storytelling (pinning, frame-by-frame sequences) for a utility interface.** Not distinguishing context: what's justified on a brand landing page is an anti-pattern on a dashboard. There the user values predictability and speed over spectacle.

- **Not knowing about delaying the skeleton screen's appearance.** Suggesting that a skeleton be shown immediately for any load. On fast responses that creates an extra visual flash instead of improving perceived performance.

- **Animating frequently-updating data indiscriminately.** Not seeing the difference between two kinds of animation. One helps register a change: a soft highlight. The other gets in the way of reading the data, like a full bounce on every update of a real-time table.
