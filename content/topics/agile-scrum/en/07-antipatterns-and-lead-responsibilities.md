# Antipatterns and Lead Responsibilities

> This is the most practical article in the series. Its question is not what X is, but what an experienced engineer or lead actually does when the process starts breaking down. It builds on ideas from every earlier article: Zombie Scrum and "being vs doing Agile" (01) and the real purpose of Scrum events (02). It also uses flow metrics (03) and estimating under pressure (05).

## Recognizing and naming process theater

### Watermelon status reports (green outside, red inside)

A **watermelon status report** is a status report or dashboard that looks "green" (on track) on the surface. Underneath, the real work is "red" (in serious trouble). The name captures it exactly: green outside, red inside.

This usually isn't malicious. It comes from structural reasons:

- Reporting rewards optimistic rounding — "95% done" for weeks in a row.
- Individual ticket statuses get rolled up without an honest summary.
- An "at risk" label quietly gets downgraded to "on track", to avoid an uncomfortable conversation with leadership.

**How a lead spots this:**

- Compares the scope committed at Sprint Planning to what actually got delivered over several recent sprints, instead of trusting this week's number as reported.
- Asks specific questions in standup: "what exactly is blocking this ticket," not just "in progress."
- Watches for tickets that stay "in progress" far longer than the team's normal cycle time, with nobody raising a flag. Cycle time is the time from the moment work on a ticket actually starts to the moment it is done ([article 03](./03-kanban-and-flow.md)).

The last one is a direct sign of a hidden problem.

**What a lead does about it:**

- Normalizes saying "this is at risk" with no negative consequence for the person who says it. Psychological safety is a precondition here: without it, nobody will tell the truth.
- Replaces subjective status labels like "mostly fine" with objective signals — real cycle time percentiles and actual progress against plan, instead of a gut feeling.

### Sprint commitments treated as deadlines instead of forecasts

The difference between "being Agile" and "doing the ceremonies" is covered in article 01. Article 05 covered why an estimate is a probability-based forecast, not a promise.

Here is the same logic at the level of a whole sprint. The Sprint Backlog commitment is the team's best forecast given current information. It is not a signed contract with penalties for missing it.

Part of a lead's job is to keep reinforcing this in conversations with leadership. Management sometimes starts treating "we committed to 30 points" as a hard deadline with consequences.

Then the lead has to bring the conversation back to the right frame explicitly. The alternative is letting the team quietly drown under pressure that comes from a misunderstanding of what the commitment means.

### Retros that produce no actual change

Article 02 covered this symptom at the level of one event. Here is what a lead specifically does about it.

The sign is the same complaints repeating in retro action items, sprint after sprint. A lead's direct responsibility here is a real, checkable log of action items: owner, due date, and a follow-up check at the next retro. Not just a wish list nobody opens again.

A lead also has to be willing to name the problem out loud. In the example below, CI (continuous integration) is the automated pipeline that builds the code and runs the tests:

> "We've raised the slow-CI issue four sprints in a row. Let's actually block time to fix it this sprint, instead of raising it a fifth time."

## Negotiating technical debt into the backlog as visible, prioritized work

**The anti-pattern:** technical debt gets handled as "extra" work squeezed into gaps between real tasks. Or, worse, senior engineers quietly do it in unrecorded time, with no accounting for the hours spent.

This creates an unsustainable pace, which directly violates the Manifesto's 8th principle of sustainable development ([article 01](./01-agile-fundamentals.md)). It also makes technical debt invisible to the prioritization done by the Product Owner (PO). If the work is not in the backlog, the PO physically cannot weigh it against everything else.

**What a lead does:**

- Writes technical debt items into the backlog with the same rigor as feature items. Not "we should really refactor this sometime," but a concrete description of *the cost of not doing it*.
- Backs that cost with data wherever possible: rising cycle time on related tickets, incident frequency in that part of the system ([article 03](./03-kanban-and-flow.md)).
- Negotiates a fixed share of every sprint for tech debt — say 15–20% of team capacity. The alternative is asking for time one sprint at a time, re-justifying it from scratch every single time.

A concrete cost of inaction sounds like this:

> "This shortcut adds about 2 hours to every related feature going forward. We've already paid that cost 6 times this quarter."

### Scenario: negotiating tech debt time with a product manager

> **Lead:** I want to talk about refactoring the payment processing module. Over the last quarter we rolled back releases three times because of bugs specifically in that module. Cycle time on tickets that touch it runs about 2.5x higher than similarly sized tickets elsewhere.

> **PM:** But client X's features are the priority right now.

> **Lead:** Understood. I'm not asking to stop feature work. I'm proposing we allocate a fixed 20% of team capacity to tech debt every sprint, starting with this module. Without that we'll keep losing roughly a week per quarter to rollbacks and hotfixes right here. That's not a hypothesis: it has already happened three times.

Here the tech debt request is not a vague ask. It is backed by a concrete cost of inaction, expressed in data the PO can actually use in their own prioritization.

## Mentoring junior engineers on realistic estimation

A common failure mode among junior engineers is giving overly optimistic, single-number estimates, with no range at all.

The reason is usually not a lack of knowledge about estimation technique. It is psychological:

- A junior engineer does not yet know how to spot *their own* unknowns — they don't know what they don't know.
- They feel pressure to look competent and fast.
- They are afraid of looking slow compared to more experienced teammates.

**What a lead does:**

- Teaches the breakdown / spike / range technique explicitly, in 1:1s (one-on-one meetings). Do not assume a junior will pick it up on their own over time. Break the task into known and unknown parts, run a spike on the unknown, then give a range instead of one number ([article 05](./05-estimation-and-planning.md)).
- Reviews estimates together with the junior engineer before Sprint Planning, for a while. Not only after the estimate has already been said out loud in front of the whole team.
- Normalizes the phrase "I don't know, let me run a spike." A spike is a short, time-boxed investigation whose only output is information. Saying that is a sign of professional maturity, not weakness.
- Shares their own past estimation mistakes: a plain "I once underestimated a similar integration by a week" works. That removes the stigma of admitting uncertainty far better than a generic "it's fine to be wrong."

## Leading without formal authority

Here's the core idea: a senior engineer (an individual contributor, or IC) influences the team's process and priorities without being anyone's formal manager. This works through a few concrete mechanisms:

- **Earned trust from consistent technical judgment** — if an engineer's past recommendations have regularly turned out right, their word carries more weight, regardless of title.
- **Framing suggestions around team or business outcomes, not personal preference.** Say "this approach will lower incident frequency, based on last quarter's data." Do not say "I don't like how this was done."
- **Using the retro as the legitimate channel for raising concerns.** The retro formally exists for exactly this purpose — the Manifesto's 12th principle ([article 01](./01-agile-fundamentals.md)). A senior engineer who uses this channel consistently is working inside a recognized structure, not going around it.
- **Understanding the limits of this influence.** A senior IC cannot force a PO to make a decision. But they can make the cost of ignoring the feedback visible, backed by data. The actual decision stays with whoever holds the formal authority.

One important observation. Informal authority, when genuinely earned and not just loudness, often affects daily team behavior more than a formal title. The team is acting out of respect for judgment, not just out of obedience to a hierarchy.

## When and how to challenge a Scrum Master or Product Owner

**When to challenge:** not every disagreement is worth open pushback. A few specific patterns are worth raising directly:

- A Scrum Master rigidly enforcing the form of a ritual against what the team actually needs — theater instead of substance ([article 02](./02-scrum-framework.md)).
- A PO who systematically changes priorities mid-sprint without acknowledging the cost of that switch. Switching context costs real time and focus ([article 03](./03-kanban-and-flow.md)).
- Decisions made without consulting the team, even though they directly affect the team's ability to work at a sustainable pace.

**How to challenge productively:**

- **A private conversation first, not public confrontation.** A personal conflict is almost always better started one-on-one. That lowers defensiveness and gives the other person a chance to hear the feedback without an audience. A general process issue is different: that one is fine to raise at a retro in front of the whole team.
- **Data, not impressions.** "Over the last 4 sprints, 55% of the Sprint Backlog got displaced by unplanned work" lands completely differently than "it feels chaotic lately."
- **Framing around impact, not blame.** Say "here's the effect I'm seeing," not "you're doing this wrong."
- **Proposing a concrete alternative or experiment**, not just criticizing the current situation.

### Scenario: talking to a PO who keeps injecting unplanned work mid-sprint

> **Lead:** I want to raise a pattern with you one-on-one, before bringing it to the whole team's retro. Over the last three sprints, on average 4 out of 5 tasks got added after Sprint Planning. Nobody discussed them with the team. Because of this we've consistently missed the Sprint Goal — not because we're working badly, but because the plan actually changes every week.

> **PO:** A lot of those are real, urgent client requests.

> **Lead:** I believe they're real. Here's what I'd propose — two options.

> **Option 1.** We explicitly reserve a small percentage of capacity for exactly this kind of urgent request, right at Sprint Planning, so it isn't a surprise.

> **Option 2.** If urgency is this frequent, we move part of our work to a Kanban flow. That means giving up a sprint whose scope is locked up front (see [article 04](./04-scrum-vs-kanban-vs-scrumban.md)). Right now we're paying the cost of both at the same time: Scrum's rigid structure and constant urgent insertions. That is the worst of both worlds.

Notice what the lead does not say: there is no "you're hurting the team" here. Instead they show a specific, measurable pattern and offer two concrete paths forward. The choice stays with the PO, but it is grounded in data, not a vague complaint.

## Balancing stakeholder pressure against sustainable pace

The Manifesto's 8th principle ([article 01](./01-agile-fundamentals.md)) states this directly: a sustainable pace should hold up indefinitely, not be treated as an exception.

The trap is that agreeing to "just one crunch sprint, just this once" sets a precedent. One-off exceptions turn into the norm precisely because nobody formally cancels them. After the first "just one more time, this one's really important," it gets much harder to say no the second time.

**What a lead does:** makes the trade-off explicit and visible. The alternative is silently absorbing the pressure and passing it to the team as overtime. Instead of a quiet "okay, let's push," the lead states the choice directly:

> "We can hit this date, but only in one of three ways. Cut scope Y. Add resources Z. Or accept the risk of building up technical debt in area W. Which do you want?"

This is a direct extension of the pushback technique from [article 05](./05-estimation-and-planning.md), the "flat estimate under pressure" trap. Its rule: never refuse the date outright, always answer with its price. Here it is applied to the whole team and the whole planning process, not to a single task.

## Common interview traps

- **"A senior engineer without a manager title has no real way to influence a bad process"** — false. Informal leadership is a real, expected senior-level skill: through earned trust, data-backed argument, and using legitimate channels like the retro. Lacking formal authority is not the same as having no influence.

- **"You should challenge a PO or Scrum Master's decisions at the retro, in front of the whole team"** — this oversimplification hides an important nuance. General process issues are fine to raise publicly at the retro. But a personal conflict, or disagreement with a specific person, is almost always better started as a private conversation. Going public on the first attempt is more likely to trigger defensiveness than to lead to real change.

- **"Technical debt should be quietly cleaned up by senior engineers in their spare time"** — false. This hides the real cost of technical debt from the business. It also makes the PO's prioritization incomplete by definition: you can't prioritize what isn't visible in the backlog. And it creates an unsustainable pace specifically for the people quietly paying that debt down.

- **"If leadership demands a crunch, the lead should just refuse outright"** — oversimplified. A lead's real job isn't to unilaterally block a business decision. It is to make the trade-off — scope, resources, risk — explicit and visible, so the business can make an informed choice. Silently sabotaging the request and silently agreeing to overtime are both worse.

- **"A sprint commitment should always be met, no matter what"** — this directly contradicts the nature of a sprint commitment. It is a forecast, not a contract (see above and [article 01](./01-agile-fundamentals.md)). A lead who reinforces this misconception strengthens exactly the wrong dynamic. It is the dynamic that turns Scrum into a source of chronic pressure, instead of a tool for adapting to change.
