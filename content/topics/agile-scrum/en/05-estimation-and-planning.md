# Estimation and Planning

## Why estimate at all

Estimation exists to support a useful planning conversation. Two typical questions: how much can we realistically take into the next sprint, and when will a backlog of 40 items roughly be done. It does not exist to create a promise that later gets used against the team as a broken contract.

The moment an estimate turns into a promise instead of a probability-based forecast, everything built on top of it starts working against the team. That includes story points, planning poker and velocity. Every section below comes back to this idea.

## Story points vs time-based estimates

**Story points** are a relative unit of measurement, and they are deliberately disconnected from calendar time. The number usually comes from a near-Fibonacci sequence: 1, 2, 3, 5, 8, 13, 21.

It reflects a combination of complexity, effort and uncertainty, compared to tasks the team has already estimated. The team says "this task is about three times bigger than that other one we scored a 2," not "this task will take 6 hours."

| Dimension | Story points | Estimate in hours or days |
|---|---|---|
| What it measures | Complexity, effort and uncertainty, relative to other tasks. | Calendar time for one specific person. |
| Depends on who takes the task | No. | Yes: a senior and a mid-level developer differ. |
| How a manager hears it | An abstract number. | A promise with a date attached. |
| Scale | Non-linear: 1, 2, 3, 5, 8, 13, 21. | Linear: any number of hours. |

### Why disconnect the estimate from time at all

There are two reasons, and neither is about convenience — both are about the fact that time-based estimates are systematically wrong:

1. **Different people work at different speeds.** A task that takes a senior developer 3 hours might take a mid-level developer 8. That is not because the mid-level developer is "worse": experience directly affects calendar time. Story points measure the complexity and size of the work relative to other tasks, not the time of one specific person. So you don't need to know in advance who will pick up the task.
2. **A time-based estimate almost always gets treated as a promise.** A developer says "this will take 2 days," and that number turns into a deadline in the manager's mind. It does so no matter how much uncertainty was actually behind it. A story point is an abstract number with no direct unit of time, so it creates some psychological distance from a literal time promise. At least in theory: see below for why this often breaks down in practice.

The non-linear scale (1, 2, 3, 5, 8, 13, not 1, 2, 3, 4, 5…) is not random. It reflects an honest fact: the bigger and more complex a task is, the less real precision the team actually has when estimating it.

The team can accurately tell a 1 from a 2. It cannot accurately tell a 13 from a 21. The scale deliberately avoids a false sense of precision at that level. That pushes the team either to break the large task down, or to admit high uncertainty openly.

### The common failure: points get converted back to time anyway

This is where the theory breaks down in almost every real team. Once a team has enough history — "we usually close about 30 points per sprint" — someone asks how many days a 5-point task takes. The question comes from management, and sometimes from the team itself.

If the team answers "about 2 days," the implicit conversion is set. From that point on, a story point stops being what it was meant to be. It becomes a unit of time again, with an extra layer of opacity that *hides* the conversion instead of removing it.

The result: the team spends effort on relative-sizing discussions during planning poker, and ends up with exactly the thing it was trying to avoid. That thing is a time estimate, now wrapped in "points" jargon. The wrapper makes it harder to notice that the conversion is happening at all. It is harder still to challenge the conversion when it turns out to be wrong.

## Planning Poker and why it actually works

**Planning Poker** is an estimation technique. Every team member privately picks a card with a number, usually from that same near-Fibonacci sequence. Everyone picks at the same time, and then all the cards get revealed together.

A common misunderstanding is thinking the point of the technique is to "average out everyone's guesses." That's not it. The real value is somewhere else:

**A gap between estimates is a signal, not noise.** If one person says "2" and another says "13" for the same task, that's not a reason to take the average and move on. It's a direct sign that two people understand the task's scope or hidden complexity very differently.

The right response isn't averaging, it's a discussion. "Why did you say 13?" — "I didn't know we still need to migrate the old data. That's why I said 2, not 13."

**Revealing estimates privately and at the same time removes anchoring bias.** Suppose people announced their estimates out loud, one at a time. The first number spoken would "anchor" how everyone else thinks about the task. Even experienced engineers unconsciously drift toward a number they just heard.

A private, simultaneous reveal is the only way to get independent, unbiased estimates from every person before the discussion starts.

### Scenario: divergence as a discovery tool

The team is estimating a task: add report export to PDF (portable document format). Developer A gives a 3. Developer B gives a 13.

> **A:** We already have a library for generating PDFs, we're using it somewhere else. This is just a new template.

> **B:** I didn't know about that library. I thought we'd have to build PDF generation from scratch. I also assumed the report needs custom date filters, which the current data model doesn't support.

> **A:** Custom filters are a separate task, that's not in the current scope.

> **B:** Then I'll revise. If the library already exists and filters are out of scope, I'd say 3 or 5 too.

A five-minute conversation uncovered two hidden misunderstandings: nobody knew about the existing library, and one person silently expanded the scope. Otherwise both would have surfaced mid-sprint, where fixing them costs the most. That, not the average number, is the real output of planning poker.

## Velocity: forecasting tool vs management weapon

**Velocity** is the number of story points a team closes on average per sprint, calculated from the history of past sprints.

### The legitimate use

Velocity is a useful internal forecasting tool *for one team, looking at itself*. A team that consistently closes 25–30 points per sprint can answer two questions honestly, from data. How much can we take into the next sprint? Roughly when will a 150-point backlog be finished — about 5–6 sprints, with some spread.

This works because the comparison is against the team's own history, at its own scale calibration.

### The anti-pattern: velocity as a pressure tool

The problem starts the moment velocity is used outside this narrow, internal purpose:

**Comparing velocity between different teams** is meaningless, and methodologically wrong. Story points aren't standardized across teams. Team A might call something a "5" that Team B would call a "13," simply because each team calibrated its own scale differently over time.

Take the claim that Team A does 40 points per sprint while Team B does only 25, so Team B must be slower. It compares two units that aren't comparable. It is like comparing meters on one ruler with feet on another, without converting between them.

**Using velocity as a pressure metric on a team or on individuals** breaks it in a second way. Management starts demanding that velocity go up every sprint, or uses low velocity as a reason for a disciplinary conversation.

The team then adapts quickly, and rationally. It does not get more productive; it inflates estimates. What used to be called a 5 is now called an 8. Velocity formally goes up. The real speed of delivering value does not.

This is a concrete example of **Goodhart's Law**: when a measure becomes a target, it stops being a good measure. It was originally stated about economic indicators, but the principle applies everywhere.

Velocity can turn from an internal diagnostic tool into a KPI (key performance indicator) with real consequences attached. At that moment people get a rational reason to optimize the number itself, instead of the thing it was supposed to measure.

## The "flat estimate under pressure" trap

Here is a classic scenario. A manager or stakeholder is under their own pressure, say a promise already made to a client. They come to the team and ask for one number, right now.

The request ignores the fact that the task carries real uncertainty. That uncertainty can be an unfamiliar part of the system, an external dependency with an unclear API, or no data about similar past tasks.

Under pressure, it's easy to give a **flat estimate**. That is a single number with no range and no stated confidence level: "this will take 2 weeks," and nothing more. The number then gets locked in as a hard deadline in the stakeholder's mind, no matter how much uncertainty was behind it.

### What a senior engineer does instead

**Explicitly breaks the task down into known and unknown parts.** Not "two months for the whole feature," but part by part. Part A, the form and validation, is well understood: estimate 3 days, high confidence. Part B, integration with an external payment API, is uncertain, because we've never worked with this provider before.

**Proposes a spike task to resolve the key unknown before committing to a number.** A spike is a time-boxed research task, for example one day. Its goal isn't to ship the feature. It is to answer one specific question: does this API support webhooks for payment status, or will we need to poll? After the spike the estimate is much more accurate, because the unknown is now known.

**Gives a range or a confidence interval instead of a single number.** For example: with high confidence, 5–7 days, if the API works the way the docs describe. If we need a workaround for a missing webhook, up to 12 days. A range like that is more honest and more useful for planning than one flat "7 days," which creates a false sense of precision.

**Relies on historical data, not just gut feeling.** Flow metrics measure the work stream itself: how long tasks take and how many finish per week (article 03 covers them in detail). One such metric is the cycle time distribution for similar tasks over the last six months.

With that data the estimate can rest on real percentiles of the past, instead of one developer's subjective feeling in the moment. An example: "tasks like this finish within 8 days, 85% of the time."

### Scenario: pushing back on an unrealistic deadline

> **Stakeholder:** The client wants the new payment provider integration in 3 weeks. Just give me a number.

> **Senior engineer:** I'll give you an honest answer, not just a number that sounds convenient. The form and internal logic — 4 days, I'm confident about that. The API integration is the unknown part: we've never worked with this provider, and their docs don't say whether they support webhooks for payment status.

> I'd like to run a one-day spike this week to find out. After that I can give you a range with real confidence behind it, instead of a guess. If the API turns out to be simple, 3 weeks is realistic. If we end up needing polling instead of webhooks, plan for 4–5 weeks.

> **Stakeholder:** What if I tell the client 3 weeks right now?

> **Senior engineer:** Then we either cut part of the scope, or we risk breaking a public promise to the client. Catching the problem quietly inside the team first is better. I'd rather give you an accurate number in a day than a nice-sounding one that isn't backed by anything.

Notice the senior engineer doesn't answer with a vague "it depends" and nothing else. They give a structured breakdown, a concrete next step (the spike), and an honest set of outcomes. The decision stays with the stakeholder, but it now rests on real data instead of an empty excuse.

## Common interview traps

- **"Story points measure how many hours or days a task will take"** — no, this is a direct misunderstanding of what relative estimation is for. Story points measure complexity, size and uncertainty *relative to other already-estimated tasks*. They are deliberately disconnected from calendar time, so that they don't create the illusion of a precise time promise.

- **"Velocity should go up every sprint — that means we're improving"** — rising velocity proves nothing on its own. It can reflect a real increase in the team's productivity. It can also be simple estimate inflation: what used to be called a 5 is now called an 8. An independent check is needed — real flow throughput, or the quality of what got shipped. Without it, rising velocity is an uninformative metric, and one especially exposed to Goodhart's Law.

- **"Planning poker is just a way to average everyone's guesses"** — the real value of the technique isn't the math of averaging. It's that a gap between estimates surfaces hidden assumptions and misunderstandings before the sprint starts, when they're cheap to fix. Mid-sprint they are expensive.

- **"Comparing team velocities shows which team is more productive"** — methodologically wrong: story points aren't standardized across teams, and each team calibrates its own scale differently. Comparing raw numbers between teams compares units that aren't actually comparable.

- **"A senior engineer should always respond to pressure with 'it depends'"** — a vague answer with no real content doesn't help negotiate anything. It doesn't look professional either. The right senior-level response isn't dodging the question. It is a structured breakdown of what's known and unknown, a concrete proposal (a spike), and an honest range with reasoning behind it. General phrases with nothing specific in them are not an answer.
