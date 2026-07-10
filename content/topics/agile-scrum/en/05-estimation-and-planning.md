# Estimation and Planning

## Why estimate at all

Before we look at techniques, let's be clear about the goal. Estimation exists to support a useful planning conversation — "how much can we realistically take into the next sprint," "when will a backlog of 40 items roughly be done" — not to create a promise that later gets used against the team as a broken contract. The moment an estimate turns into a promise instead of a probability-based forecast, everything built on top of it (story points, planning poker, velocity) starts working against the team instead of for it. Keep this idea in mind — every section below comes back to it.

## Story points vs time-based estimates

**Story points** are a relative unit of measurement, and they are deliberately disconnected from calendar time. The number (usually from a near-Fibonacci sequence: 1, 2, 3, 5, 8, 13, 21) reflects a combination of complexity, effort, and uncertainty, compared to tasks the team has already estimated — "this task is about three times bigger than that other one we scored a 2" — not "this task will take 6 hours."

### Why disconnect the estimate from time at all

There are two reasons, and neither is about convenience — both are about the fact that time-based estimates are systematically wrong:

1. **Different people work at different speeds.** A task that takes a senior developer 3 hours might take a mid-level developer 8 — not because the mid-level developer is "worse," but because experience directly affects calendar time. Story points measure the complexity and size of the work relative to other tasks, not the time of one specific person, so you don't need to know in advance who will pick up the task.
2. **A time-based estimate almost always gets treated as a promise.** The moment a developer says "this will take 2 days," that number nearly always turns into a deadline in the manager's mind — no matter how much uncertainty was actually behind it. Story points, being an abstract number with no direct unit of time, create some psychological distance from a literal "time promise" — at least in theory (see below for why this often breaks down in practice).

The non-linear scale (1, 2, 3, 5, 8, 13, not 1, 2, 3, 4, 5…) is not random. It reflects an honest fact: the bigger and more complex a task is, the less real precision the team actually has when estimating it. The team can accurately tell the difference between a "1" and a "2." It cannot accurately tell the difference between a "13" and a "21," and the scale deliberately avoids giving a false sense of precision at that level — pushing the team to either break the large task down, or openly admit high uncertainty.

### The common failure: points get converted back to time anyway

This is where the theory breaks down in almost every real team. Once a team has enough history ("we usually close about 30 points per sprint"), it becomes tempting — for management, and sometimes for the team itself — to ask: "how many days is a 5-point task?" If the team answers ("about 2 days"), the implicit conversion is now set — and from that point on, a story point stops being what it was meant to be. It becomes a unit of time again, just with an extra layer of opacity that *hides* the conversion instead of removing it.

The result: the team spends effort on relative-sizing discussions during planning poker, but ends up with exactly the thing it was trying to avoid — a time estimate, just wrapped in "points" jargon, which makes it harder to notice that the conversion is even happening, and even harder to challenge it when it turns out to be wrong.

## Planning Poker and why it actually works

**Planning Poker** is an estimation technique where every team member privately and simultaneously picks a card with a number (usually from that same near-Fibonacci sequence), and then all the cards get revealed at the same time.

A common misunderstanding is thinking the point of the technique is to "average out everyone's guesses." That's not it. The real value is somewhere else:

**A gap between estimates is a signal, not noise.** If one person says "2" and another says "13" for the same task, that's not a reason to just take the average and move on. It's a direct sign that two people have a fundamentally different understanding of the task's scope or hidden complexity. The right response isn't averaging — it's a discussion: "why did you say 13?" / "I didn't know we still need to migrate the old data — that's why I said 2, not 13."

**Revealing estimates privately and at the same time removes anchoring bias.** If people announced their estimates out loud one at a time, the first number spoken would inevitably "anchor" how everyone else thinks about the task — even experienced engineers unconsciously drift toward a number they just heard. Revealing cards privately and simultaneously is the only way to get independent, unbiased estimates from every person before the discussion starts.

### Scenario: divergence as a discovery tool

The team is estimating "add PDF export for reports." Developer A gives a "3." Developer B gives a "13."

> **A:** We already have a library for generating PDFs, we're using it somewhere else. This is just a new template.
> **B:** I didn't know about that library. I thought we'd have to build PDF generation from scratch, and I also assumed the report needs custom date filters, which the current data model doesn't support.
> **A:** Custom filters are a separate task, that's not in the current scope.
> **B:** Then I'll revise — if the library already exists and filters are out of scope, I'd say "3" or "5" too.

A five-minute conversation just uncovered two hidden misunderstandings (not knowing about an existing library, an unspoken scope expansion) that would otherwise have surfaced mid-sprint, at the point where fixing them costs the most. That — not "the average number" — is the real output of planning poker.

## Velocity: forecasting tool vs management weapon

**Velocity** is the number of story points a team closes on average per sprint, calculated from the history of past sprints.

### The legitimate use

Velocity is a useful internal forecasting tool *for one team, looking at itself*. If a team consistently closes 25–30 points per sprint, that lets it give an honest, data-based answer to questions like "how much can we take into next sprint" and "roughly when will a 150-point backlog be finished" (roughly, 5–6 sprints, with some spread). This works because the comparison is against the team's own history, at its own scale calibration.

### The anti-pattern: velocity as a pressure tool

The problem starts the moment velocity is used outside this narrow, internal purpose:

**Comparing velocity between different teams** is meaningless, and methodologically wrong. Story points aren't standardized across teams: Team A might call something a "5" that Team B would call a "13," simply because each team calibrated its own scale differently over time. The claim "Team A does 40 points per sprint, Team B only does 25, so Team B must be slower" compares two units that aren't comparable — like comparing meters on one ruler with feet on another, without converting between them.

**Using velocity as a pressure metric on a team or on individuals** — if management starts demanding "velocity must go up every sprint," or uses low velocity as a reason for a disciplinary conversation, the team adapts quickly (and rationally) — not by getting more productive, but by inflating estimates: what used to be called a "5" is now called an "8." Velocity formally goes up. The real speed of delivering value does not.

This is a concrete example of **Goodhart's Law**: "when a measure becomes a target, it stops being a good measure" (originally stated about economic indicators, but the principle applies everywhere). The moment velocity turns from an internal diagnostic tool into a KPI with real consequences attached, people get a rational reason to optimize the number itself, instead of the thing it was supposed to measure.

## The "flat estimate under pressure" trap

Here is a classic scenario: a manager or stakeholder, under their own pressure (say, a promise already made to a client), comes to the team and asks to "just give me a number" — without accounting for the fact that the task carries real uncertainty (an unfamiliar part of the system, an external dependency with an unclear API, no data about similar past tasks).

Under pressure, it's easy to fall into giving a **flat estimate** — a single number with no range and no stated confidence level ("this will take 2 weeks"). That number then inevitably gets locked in as a hard deadline in the stakeholder's mind, no matter how much uncertainty was actually behind it.

### What a senior engineer does instead

**Explicitly breaks the task down into known and unknown parts.** Not "two months for the whole feature," but "part A (the form and validation) is well understood, estimate 3 days, high confidence; part B (integration with an external payment API) is uncertain — we've never worked with this provider before."

**Proposes a spike task to resolve the key unknown before committing to a number.** A spike is a time-boxed research task (for example, one day), and its goal isn't to ship the feature — it's to get a specific answer to a specific question ("does this API support webhooks for payment status, or will we need to poll?"). After the spike, the estimate becomes much more accurate, because the unknown is now known.

**Gives a range or a confidence interval instead of a single number.** "With high confidence, 5–7 days, if the API works the way the docs describe. If we need a workaround for a missing webhook, up to 12 days" — this is more honest and more useful for planning than one flat number like "7 days," which creates a false sense of precision.

**Relies on historical data, not just gut feeling.** If the team has flow metrics (see article 03) — for example, the cycle time distribution for similar tasks over the last six months — the estimate can rest on real percentiles of past data ("tasks like this finish within 8 days, 85% of the time"), instead of just one developer's subjective feeling in the moment.

### Scenario: pushing back on an unrealistic deadline

> **Stakeholder:** The client wants the new payment provider integration in 3 weeks. Just give me a number.
> **Senior engineer:** I'll give you an honest answer, not just a number that sounds convenient. The form and internal logic — 4 days, I'm confident about that. The API integration is the unknown part: we've never worked with this provider, and their docs don't say whether they support webhooks for payment status. I'd like to run a one-day spike this week to find out. After that, I can give you a range with real confidence behind it, instead of a guess. If the API turns out to be simple, 3 weeks is realistic. If we end up needing polling instead of webhooks, plan for 4–5 weeks.
> **Stakeholder:** What if I tell the client 3 weeks right now?
> **Senior engineer:** Then we either cut part of the scope, or we risk breaking a public promise to the client, instead of catching the problem quietly inside the team first. I'd rather give you an accurate number in a day than a nice-sounding one that isn't backed by anything right now.

Notice the senior engineer doesn't answer with a vague "it depends" and nothing else. They give a structured breakdown, a concrete next step (the spike), and an honest set of outcomes — leaving the decision to the stakeholder, but grounded in real data instead of an empty excuse.

## Common interview traps

- **"Story points measure how many hours or days a task will take"** — no, this is a direct misunderstanding of what relative estimation is for. Story points measure complexity, size, and uncertainty *relative to other already-estimated tasks*, deliberately disconnected from calendar time — specifically so they don't create the illusion of a precise time promise.

- **"Velocity should go up every sprint — that means we're improving"** — rising velocity proves nothing on its own. It can reflect a real increase in the team's productivity, or it can be simple estimate inflation (what used to be called a "5" is now called an "8"). Without an independent check (real flow throughput, or the quality of what got shipped), rising velocity is an uninformative metric — and one that's especially exposed to Goodhart's Law.

- **"Planning poker is just a way to average everyone's guesses"** — the real value of the technique isn't the math of averaging. It's that a gap between estimates surfaces hidden assumptions and misunderstandings before the sprint starts, when they're cheap to fix, instead of mid-sprint, when they're expensive.

- **"Comparing team velocities shows which team is more productive"** — methodologically wrong: story points aren't standardized across teams, and each team calibrates its own scale differently. Comparing raw numbers between teams compares units that aren't actually comparable.

- **"A senior engineer should always respond to pressure with 'it depends'"** — a vague answer with no real content doesn't help negotiate anything, and it doesn't look professional either. The right senior-level response isn't dodging the question — it's a structured breakdown of what's known and unknown, a concrete proposal (a spike), and an honest range with reasoning behind it, instead of general phrases with nothing specific in them.
