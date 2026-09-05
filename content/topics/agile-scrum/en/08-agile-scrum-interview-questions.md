# Agile & Scrum — Interview Questions

## Middle

**Name the four values of the Agile Manifesto. What does the last line of the Manifesto actually mean ("while there is value in the items on the right...")?**

The four values each put one thing above another:

- Individuals and interactions over processes and tools.
- Working software over comprehensive documentation.
- Customer collaboration over contract negotiation.
- Responding to change over following a plan.

The last line is the most overlooked part of the Manifesto. It says plainly that the items on the right — process, documentation, contracts, plans — are not rejected. They just get lower priority when they conflict with the items on the left.

So the Manifesto is not about giving up planning and documentation. It says that when those conflict with working software or the ability to adapt, the second one wins.

---

**What is the difference between the Product Owner and Scrum Master roles?**

The Product Owner (PO) is responsible for maximizing product value. That means managing the Product Backlog, setting the Product Goal, and deciding what to do and in what order.

The Scrum Master is responsible for how effectively Scrum is used: facilitating events, removing impediments, and coaching the team and the organization.

Where the line between them runs:

- The PO does not tell people *how* to do the work. That is the Developers' decision.
- The Scrum Master is not the manager of the Developers.
- The Scrum Master does not decide what goes into the backlog. That is the PO's job.

Both roles exist to serve the team, not to command it.

---

**How does Definition of Done differ from Definition of Ready?**

Definition of Done is an official part of the Scrum Guide. It is a formal quality standard that any Product Backlog Item must meet to count as part of the Increment. For example: code reviewed, has test coverage, deployed to staging.

Definition of Ready is not part of the official Scrum Guide, but it is a very common practice. It lists what a task must satisfy before it can even enter Sprint Planning: clear acceptance criteria, an estimate, dependencies identified.

Short version: DoD (Definition of Done) is about the quality of the output, DoR (Definition of Ready) about the readiness of the input.

---

**Why is the Daily Scrum not a status report for a manager?**

The event belongs to the Developers. It exists so they can adjust the Sprint Backlog for the next 24 hours. The team syncs on progress toward the Sprint Goal and finds blockers that they themselves solve.

If the standup turns into each person reporting to a manager or tech lead in turn, the event loses its purpose:

- People talk "for the record."
- Nobody really listens to the next person.
- Real blockers get pushed to "let's talk after" and are forgotten there.

A useful test: remove the manager from the room. Does the standup still mean anything to the team?

---

**Why aren't story points just another name for hours?**

Story points measure the complexity, size, and uncertainty of a task *relative to other already-estimated tasks*, not calendar time.

There are two reasons for that:

- Different people work at different speeds. A task that takes a senior developer 3 hours might take a mid-level developer 8.
- A time-based estimate almost always turns into a promise or a deadline in a manager's mind, no matter how much uncertainty it actually carried.

Story points create some psychological distance from a literal time promise. That holds only while they are not converted back into hours through velocity, which is a common failure mode covered separately below.

---

**What is the difference between Cycle Time and Lead Time?**

Cycle Time is the time from the moment work on a task actually starts to the moment it finishes. It is an internal metric: the team uses it to judge its own speed.

Lead Time is the time from the moment a request arrives — the task is created or enters the backlog — to the moment it finishes. It includes all the waiting time before work starts, plus the Cycle Time itself.

| Metric | Clock starts | Whose question it answers |
|---|---|---|
| Cycle Time | work actually starts | the team's own speed |
| Lead Time | the request arrives | how long the customer waits |

Lead Time answers a customer question: how long from the moment I asked, to the moment I get it. Lead Time is always ≥ Cycle Time.

---

**What is a WIP limit, and why does going over it hurt more than it looks?**

A WIP limit (Work In Progress limit) caps how many tasks can be in progress at once at a given stage.

Behind it is Little's Law: Cycle Time = WIP / Throughput. If WIP grows without a matching rise in throughput, the cycle time of every individual task has to grow.

There is a second reason as well: the cost of context switching. Holding several parallel tasks in mind at once costs real time and mental energy, and that cost adds value to none of them.

A WIP limit forces the team to focus. It also redirects effort to wherever the real bottleneck actually is.

---

**What is a Sprint Goal, and why does it matter more than just a list of tickets for the sprint?**

The Sprint Goal is one connected goal for the sprint. It explains why the chosen set of tasks makes sense together. It also lets the team stay flexible about implementation details without losing focus on the outcome.

A list of tickets without a goal is just a work queue. The difference shows the moment something unexpected happens — say, a task turns out harder than expected:

- A team with a clear Sprint Goal can re-prioritize *within* the goal, dropping a minor feature to deliver the main one.
- A team without a goal just loses focus, unsure what on the list is actually critical.

---

**What is Backlog Refinement, and why is it not the same thing as Sprint Planning?**

Backlog Refinement is an ongoing activity during the sprint. The team adds detail, estimates and order to upcoming Product Backlog Items. The aim is that they meet the Definition of Ready by the time they enter a sprint.

Sprint Planning is a one-time event at the start of the sprint. There the team picks a specific amount of work from an already-prepared backlog.

Good refinement makes planning fast and predictable. Without it, planning turns into an improvised discussion of unclear tasks — exactly when the team has to commit to scope.

---

## Senior

**What is the difference between "being Agile" and "doing Agile ceremonies"? Give a concrete example of this difference in practice.**

"Being Agile" means actually working according to the Manifesto's values:

- Short feedback loops with real users.
- Willingness to change the plan when reality changes.
- A self-organizing team.
- A retro that genuinely changes behavior.

"Doing the ceremonies" means performing the outer shape — sprints, standups, a board, a retro — without the function these things were built for.

A concrete example, two Sprint Reviews that look identical from outside:

- One is attended only by a manager who already knows what is coming.
- The other has real users or stakeholders, and their feedback actually reorders the Product Backlog.

Both get reported as "we held a demo." In substance, one produces feedback from reality and the other does not.

---

**What is Zombie Scrum / Cargo Cult Agile, and how would you diagnose it on a team you've just joined?**

Cargo Cult Agile is when a team copies the visible parts of Scrum without reproducing the mechanism they were built for. That mechanism is a short feedback loop with reality.

Zombie Scrum is a more specific term for the same situation applied to Scrum. The events happen formally, but the team is "dead inside": no real inspection, no real adaptation.

You can diagnose it without asking the team directly. Three checks:

- Look at the retro's action items over the last 4–6 sprints. Do the same items keep repeating?
- Check who actually attends the Sprint Review, and whether their feedback ever changes backlog priorities.
- Compare the scope committed at Sprint Planning against what actually got delivered, over several sprints.

---

**Explain why Planning Poker actually works — what does the technique surface, beyond an averaged number?**

The real value is not in mathematically averaging guesses. It is that a gap between estimates is a signal, not noise.

If one person says "2" and another says "13" for the same task, they understand the scope or hidden complexity very differently. The right response is a discussion — "why did you say 13?" — not an average.

Revealing cards privately and simultaneously removes anchoring bias. If estimates were spoken aloud one at a time, the first number would inevitably shape how everyone else thinks about the task.

So the real output of planning poker is hidden misunderstandings, uncovered before the sprint starts, while they are still cheap to fix.

---

**A team keeps missing its sprint commitments. Management wants the team to "estimate more accurately." What is actually wrong here, and what do you say?**

The problem is probably not estimation accuracy. It is a misunderstanding of what an estimate even is: it gets treated as a promise instead of a probability-based forecast.

The first step is collecting data:

- How much of the Sprint Backlog, on average, gets displaced by unplanned work.
- How many Sprint Goals the team actually meets.

If the misses come from constant unplanned insertions rather than bad estimation, the real problem is structural. The team may need Scrumban instead of Scrum with a sprint whose scope is frozen up front — see [article 04](./04-scrum-vs-kanban-vs-scrumban.md).

Ground the conversation with management in these numbers. The line that lands: "estimates can't get more accurate while 50% of the work gets added after the estimate is already made."

---

**Given Team X (a support queue, unpredictable flow) and Team Y (planned feature roadmap work), which structure fits which team, and why?**

Team X (support) fits Kanban:

- Work arrives continuously and unpredictably.
- The SLA (service level agreement — the response time promised to the customer) demands a reaction right now, not after the next Sprint Planning.
- WIP limits (work in progress) and flow metrics — cycle time, throughput — give a probability-based forecast against that SLA, without artificially forcing work into sprints.

Team Y (planned features) fits Scrum:

- Work can be batched over a 1–2 week horizon.
- Outside stakeholders benefit from a predictable sync point, such as a demo every two weeks.
- A fixed Sprint Goal gives the team useful focus.

The real decision axis is how predictable and "batchable" the incoming work is. It is not the team's label: "we're a product team," "we're a support team."

---

**What is a watermelon status report, and how do you catch one before it becomes a crisis?**

A watermelon status report ("green outside, red inside") shows "on track" at the surface, while the real work underneath is in serious trouble.

It happens because of structural incentives. Reporting rewards optimistic rounding, and an "at risk" label quietly gets downgraded to avoid an uncomfortable conversation.

You catch it by watching objective signals instead of trusting the words:

- Compare committed scope to actually delivered scope over several sprints.
- Track tasks stuck in one status far longer than the team's normal cycle time, with nobody escalating.
- Ask direct follow-up questions in standup instead of accepting a vague "everything's fine."

---

**How would you negotiate getting technical debt into the backlog, if the Product Owner keeps deprioritizing it?**

Write tech debt as a full backlog item, with the same rigor as a feature. Not a vague "we should really refactor this," but a concrete cost of inaction:

> "This shortcut adds about 2 hours to every related feature, and we've already paid that cost N times this quarter."

Back the claim with data where you can: rising cycle time on related tickets, incident frequency.

Then negotiate a fixed share of every sprint for it — say 15–20% of the team's capacity — instead of asking for time sprint by sprint.

The core idea is to make the cost of inaction visible and measurable. The Product Owner physically cannot prioritize something they cannot see in a structured form in the backlog.

---

**What is Goodhart's Law, and how does it apply to using velocity as a KPI (key performance indicator)?**

Goodhart's Law says: "when a measure becomes a target, it stops being a good measure."

Applied to velocity: while it stays an internal forecasting tool a team uses for itself, it is useful. The moment velocity turns into a KPI with consequences, the picture flips. Typical consequences: "velocity must go up every sprint," or velocity compared across teams.

Now the team has a rational reason to optimize the number itself instead of delivering more value. The cheapest way is to inflate estimates: what used to be a "5" becomes an "8." Velocity formally goes up. Real delivery speed does not.

---

**A stakeholder, under deadline pressure, demands a single number from you for an uncertain task. Walk through how you respond.**

I don't give a flat estimate. First I break the task into known and unknown parts, out loud:

- "Part A is clear: 3 days, high confidence."
- "Part B is integration with an unfamiliar API. That's where the uncertainty is."

Then I propose a time-boxed spike: a short investigation with a hard limit — say one day — whose only output is information. It resolves the key unknown before anyone commits to a number.

After the spike I give a range or a confidence interval, not a single figure. Where possible I back it with historical flow data. Flow data here means how long comparable tasks actually took. A typical answer: "5–7 days in the simple case, up to 12 in the complex one."

If the stakeholder insists on a number right now, I state the consequences directly. Either we cut scope, or the risk of breaking a public promise to the client becomes visible right now. The alternative is that it shows up quietly in three weeks.

---

## Lead

**What is the "Spotify model," and why is citing it as a scaling framework a warning sign in an interview?**

The "Spotify model" (Squad / Tribe / Chapter / Guild) is not an official framework. It is a snapshot of Spotify's organizational culture as of 2012, described in a white paper by Henrik Kniberg and Anders Ivarsson. Both authors said explicitly that this was an imperfect, still-evolving state, not a recipe to copy.

Spotify itself later changed its structure many times and moved away from much of what was described.

So citing it as a ready-made, prescriptive framework is a sign that the candidate is repeating a diagram without knowing the nuance.

Worse, many companies copied only the terminology. Renaming teams to "squads" is easy; bringing over the culture of autonomy and trust that actually made the structure work is not. That is Cargo Cult Agile applied to organizational design.

---

**Your organization has 6 teams building one product, with constant mutual blocking. Walk through how you'd choose between Scrum of Scrums, LeSS (Large-Scale Scrum) and SAFe (Scaled Agile Framework).**

First I diagnose the real nature of the problem. Is this lightweight coordination — a few dependencies that a regular sync between team representatives could solve? Or is it a deeper issue of shared product and architecture ownership?

The answer picks the framework:

- **The dependencies are mostly about information** ("what is the other team doing"). Start with a lightweight Scrum of Scrums: a short regular sync of one representative per team. It is cheaper to adopt and requires no reorganization.
- **The teams genuinely need one shared Product Backlog and one shared Definition of Done** for coordinated prioritization. Then look at LeSS. It is deliberately minimalist and solves coordination through self-management, rather than by adding a management layer.
- **The organization is large, sits in a regulated industry, and needs enterprise governance and synchronized releases** beyond what the other two cover. Only then consider SAFe.

Enterprise governance here means company-wide rules for audit, compliance and reporting. The weight of SAFe is justified by that level of complexity, never by default.

---

**You are a senior individual contributor (IC) with no formal authority. How do you get a Scrum Master to stop rigidly running ceremonies that no longer serve the team?**

I start with a private conversation, not a public confrontation at the retro.

The argument is built on data, not feelings. Over the last 4 sprints:

- Only one manager has attended our Sprint Review.
- No real users have ever been there.
- Not a single review has changed backlog priorities.

That is a specific, checkable pattern, not a general complaint that "retros feel boring."

Saying "here's what I'm seeing" instead of "you're doing this wrong" frames it around impact, not blame. I also propose a concrete experiment instead of just criticizing the current format. For example: "let's invite a real user to the next Review and see if anything changes."

If that doesn't help, I use the retro as the legitimate channel to raise it with the whole team, backed by the same data.

---

**Leadership asks for "just one crunch sprint" — one sprint of overtime — to hit a deadline. How do you handle this as a lead?**

I don't refuse unilaterally, and I don't quietly agree and pass the pressure on to the team as overtime. I make the trade-off explicit and visible instead.

I state a concrete choice for leadership: we can hit this date, but only in one of three ways.

- Cut scope Y.
- Add resources Z.
- Accept the risk of building up technical debt in area W.

Which one do you want? This is the same pushback technique used against estimation pressure, now applied to the whole team. Its rule: never refuse the date outright, always answer with the price of it ([article 05](./05-estimation-and-planning.md)).

I also name the cost of a precedent. Agreeing to "just this once" without saying out loud that it is an exception, not a new norm, almost always makes it the new norm. I make that cost visible to leadership ahead of time, not after the fact.

---

**A team's retro has raised the same three issues for the last five sprints with no resolution. What do you do differently as the person responsible for the team's health?**

First, I stop letting the team "raise an issue" without a real commitment to solving it. I introduce a mandatory, checkable action-item log: owner, due date, and a follow-up check at the next retro. Not a wish list nobody opens again.

Second, I name the pattern out loud. Slow CI (continuous integration — the automated build-and-test pipeline) is the usual example: "we've talked about slow CI five sprints in a row. Let's actually block time to fix it this sprint, instead of raising it a sixth time."

Third, the issue may be outside the team's own authority — say, it depends on another department. Then escalating it beyond the team is my job as the lead. Leaving it as an unsolved retro item forever, inside a team that cannot fix it on its own, is not an option.

---

**How do you tell whether a team is doing real Scrum or performing "Scrum theater," using only observable signals, without asking the team directly?**

I look at specific, checkable signals, not the team's self-description.

- **Sprint Review.** Do real users or stakeholders show up? Does their feedback actually change the backlog afterward, or is it a demo for the same manager every time?
- **Retrospective.** Do the same action items keep repeating sprint after sprint, with no traceable resolution?
- **Daily Scrum.** Remove the manager from the room: does the format of the meeting change? If yes, it was already a report, not the team adapting its own plan.
- **Sprint Planning.** Does the team actually discuss and push back on scope, or silently listen to an already-finished ticket list?

Several of these signals lining up gives a confident diagnosis. And it never requires asking "are you doing real Scrum?" — a question the team will almost always answer "yes" to, regardless of reality.
