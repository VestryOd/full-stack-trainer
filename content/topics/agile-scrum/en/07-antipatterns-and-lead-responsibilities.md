# Antipatterns and Lead Responsibilities

> This is the most practical article in the series — not "what is X," but "what does an experienced engineer or lead actually do when the process starts breaking down." It builds on ideas from every earlier article: Zombie Scrum and "being vs doing Agile" (01), the real purpose of Scrum events (02), flow metrics (03), estimating under pressure (05).

## Recognizing and naming process theater

### Watermelon status reports (green outside, red inside)

A **watermelon status report** is a status report or dashboard that looks "green" (on track) on the surface, while the real work underneath is "red" (in serious trouble). The name captures it exactly: green outside, red inside. This usually isn't malicious — it comes from structural reasons: reporting rewards optimistic rounding ("95% done" for weeks in a row), individual ticket statuses get rolled up without an honest summary, or an "at risk" label quietly gets downgraded to "on track" to avoid an uncomfortable conversation with leadership.

**How a lead spots this:** compares the scope committed at Sprint Planning to what actually got delivered over several recent sprints, instead of trusting this week's number at face value; asks specific questions in standup ("what exactly is blocking this ticket, not just 'in progress'"); watches for tickets that stay "in progress" far longer than the team's normal cycle time (see the flow metrics in article 03) without anyone raising a flag — that's a direct sign of a hidden problem.

**What a lead does about it:** normalizes saying "this is at risk" without any negative consequence for the person who says it (psychological safety is a precondition here — without it, nobody will tell the truth); replaces subjective status labels ("mostly fine") with objective signals — real cycle time percentiles, actual progress against plan, instead of a gut feeling.

### Sprint commitments treated as deadlines instead of forecasts

Article 01 already covered the difference between "being Agile" and "doing the ceremonies"; article 05 covered why an estimate is a probability-based forecast, not a promise. Here's the same logic applied at the level of a whole sprint: the Sprint Backlog commitment is the team's best forecast given current information — not a signed contract with penalties for missing it. Part of a lead's job is to keep reinforcing this understanding in conversations with leadership. When management starts treating "we committed to 30 points" as a hard deadline with consequences, the lead needs to explicitly bring the conversation back to the right frame, instead of quietly letting the team drown under pressure caused by a misunderstanding of what the commitment actually means.

### Retros that produce no actual change

Article 02 covered this symptom at the level of one event; here's what a lead specifically does about it. The sign is the same complaints repeating in retro action items, sprint after sprint. A lead's direct responsibility here: keep a real, checkable log of action items (owner, due date, a follow-up check at the next retro — not just a wish list nobody opens again), and be willing to say out loud: "we've raised the slow-CI issue four sprints in a row — let's actually block time to fix it this sprint, instead of raising it a fifth time."

## Negotiating technical debt into the backlog as visible, prioritized work

**The anti-pattern:** technical debt gets handled as "extra" work squeezed into gaps between real tasks, or — worse — quietly done by senior engineers off the books, with no accounting for the time spent. This creates an unsustainable pace (a direct violation of the Manifesto's 8th principle — sustainable development, see article 01), and it makes technical debt invisible to the PO's prioritization: if the work isn't in the backlog, the PO physically cannot weigh it against everything else.

**What a lead does:** writes technical debt items into the backlog with the same rigor as feature items — not "we should really refactor this sometime," but a concrete description of *the cost of not doing it*: "this shortcut adds about 2 hours to every related feature going forward — we've already paid that cost 6 times this quarter." Wherever possible, this gets backed by data (rising cycle time on related tickets, incident frequency in that part of the system — see the flow metrics in article 03). Negotiates a standing capacity allocation for tech debt (say, a fixed 15–20% every sprint), instead of begging for time one sprint at a time, re-justifying it from scratch every single time.

### Scenario: negotiating tech debt time with a product manager

> **Lead:** I want to talk about refactoring the payment processing module. Over the last quarter, we rolled back releases three times because of bugs specifically in that module, and cycle time on tickets that touch it runs about 2.5x higher than similarly sized tickets elsewhere.
> **PM:** But client X's features are the priority right now.
> **Lead:** Understood. I'm not asking to stop feature work — I'm proposing we allocate a fixed 20% of team capacity to tech debt every sprint, starting with this module. Without that, we'll keep losing roughly a week per quarter to rollbacks and hotfixes right here — that's not a hypothesis, it's already happened three times.

Here, the tech debt request isn't a vague ask — it's backed by a concrete cost of inaction, expressed in data the PO can actually use in their own prioritization.

## Mentoring junior engineers on realistic estimation

A common failure mode among junior engineers is giving overly optimistic, single-number estimates (no range at all). The reason is usually not a lack of knowledge about estimation technique — it's psychological: a junior engineer doesn't yet know how to spot *their own* unknowns (they don't know what they don't know), or they feel pressure to look competent and fast, or they're afraid of looking slow compared to more experienced teammates.

**What a lead does:** explicitly teaches the breakdown/spike/range technique from article 05 in 1:1s, rather than assuming a junior will pick it up on their own over time; reviews estimates together with the junior engineer before Sprint Planning for a while, rather than only after the estimate has already been said out loud in front of the whole team; normalizes the phrase "I don't know, let me run a spike" as a sign of professional maturity, not weakness; shares their own past estimation mistakes ("I once underestimated a similar integration by a week") — this removes the stigma of admitting uncertainty far better than any generic reassurance that "it's fine to be wrong."

## Leading without formal authority

Here's the core idea: a senior engineer (an individual contributor, or IC) influences the team's process and priorities without being anyone's formal manager. This works through a few concrete mechanisms:

- **Earned trust from consistent technical judgment** — if an engineer's past recommendations have regularly turned out right, their word carries more weight, regardless of title.
- **Framing suggestions around team/business outcomes, not personal preference** — "this approach will lower incident frequency, based on last quarter's data," not "I don't like how this was done."
- **Using the retro as the legitimate channel for raising concerns** — the retro formally exists for exactly this purpose (the Manifesto's 12th principle, article 01), and a senior engineer who uses this channel consistently is working inside a recognized structure, not going around it.
- **Understanding the limits of this influence** — a senior IC cannot force a PO to make a decision; but they can make the cost of ignoring the feedback visible, backed by data, and leave the actual decision to whoever holds the formal authority.

One important observation: informal authority, when it's genuinely earned (not just loudness), often has a bigger real effect on a team's day-to-day behavior than a formal title — because the team is acting out of respect for judgment, not just out of obedience to a hierarchy.

## When and how to challenge a Scrum Master or Product Owner

**When to challenge:** not every disagreement is worth open pushback, but a few specific patterns are worth raising directly: a Scrum Master rigidly enforcing the form of a ritual against what the team actually needs (theater instead of substance, article 02); a PO who systematically changes priorities mid-sprint without acknowledging the cost of that switch (context-switching cost, article 03); decisions made without consulting the team, even though they directly affect the team's ability to work at a sustainable pace.

**How to challenge productively:**
- **A private conversation first, not public confrontation.** A personal conflict (unlike a general process issue, which is fine to raise at a retro in front of the whole team) is almost always better started one-on-one — this lowers defensiveness and gives the other person a chance to hear the feedback without an audience.
- **Data, not vibes.** "Over the last 4 sprints, 55% of the Sprint Backlog got displaced by unplanned work" lands completely differently than "it feels chaotic lately."
- **Framing around impact, not blame.** "Here's the effect I'm seeing" — not "you're doing this wrong."
- **Proposing a concrete alternative or experiment**, not just criticizing the current situation.

### Scenario: talking to a PO who keeps injecting unplanned work mid-sprint

> **Lead:** I want to raise a pattern with you one-on-one, before bringing it to the whole team's retro. Over the last three sprints, on average 4 out of 5 tasks got added to the sprint after Sprint Planning, without any discussion with the team. Because of this, we've consistently missed the Sprint Goal — not because we're working badly, but because the plan actually changes every week.
> **PO:** A lot of those are real, urgent client requests.
> **Lead:** I believe they're real. Here's what I'd propose: either we explicitly reserve a small percentage of capacity for exactly this kind of urgent request right at Sprint Planning, so it isn't a surprise, or, if urgency is this frequent, maybe it's worth discussing moving part of our work to a Kanban flow instead of a hard-locked sprint (see article 04) — because right now we're paying the cost of both Scrum's rigid structure and constant urgent insertions at the same time, which is the worst of both worlds.

Notice the lead doesn't say "you're hurting the team." They show a specific, measurable pattern and offer two concrete paths forward, leaving the choice to the PO — but grounded in data, not a vague complaint.

## Balancing stakeholder pressure against sustainable pace

The Manifesto's 8th principle (article 01) states this directly: a sustainable pace should hold up indefinitely, not be treated as an exception. The trap is that agreeing to "just one crunch sprint, just this once" sets a precedent — one-off exceptions turn into the norm precisely because nobody formally cancels them. After the first "just one more time, this one's really important," it gets much harder to say no the second time.

**What a lead does:** makes the trade-off explicit and visible, instead of silently absorbing the pressure and passing it on to the team as overtime. Instead of a quiet "okay, let's push," the lead states the choice directly: "we can hit this date if we cut scope Y, add resources Z, or accept the risk of building up technical debt in area W — which do you want?" This is a direct extension of the pushback technique from article 05 (the "flat estimate under pressure" trap), just applied at the scale of the whole team and the whole planning process, instead of a single task.

## Common interview traps

- **"A senior engineer without a manager title has no real way to influence a bad process"** — false. Informal leadership is a real, expected senior-level skill: through earned trust, data-backed argument, and using legitimate channels like the retro. Lacking formal authority is not the same as having no influence.

- **"You should challenge a PO or Scrum Master's decisions at the retro, in front of the whole team"** — this oversimplification hides an important nuance: general process issues are fine to raise publicly at the retro, but a personal conflict or disagreement with a specific person is almost always better started as a private conversation — going public on the first attempt is more likely to trigger defensiveness than lead to real change.

- **"Technical debt should be quietly cleaned up by senior engineers in their spare time"** — false. This hides the real cost of technical debt from the business, and it makes the PO's prioritization incomplete by definition (you can't prioritize what isn't visible in the backlog) — and it creates an unsustainable pace specifically for the people quietly paying down that debt.

- **"If leadership demands a crunch, the lead should just refuse outright"** — oversimplified. A lead's real job isn't to unilaterally block a business decision — it's to make the trade-off (scope / resources / risk) explicit and visible, letting the business make an informed choice, instead of either silently sabotaging the request or silently agreeing to overtime.

- **"A sprint commitment should always be met, no matter what"** — this directly contradicts the actual nature of a sprint commitment as a forecast, not a contract (see above and article 01). If a lead reinforces this misconception instead of challenging it, they're strengthening exactly the dynamic that turns Scrum into a source of chronic pressure, instead of a tool for adapting to change.
