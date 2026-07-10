# Agile & Scrum — Interview Questions

## Middle

**Name the four values of the Agile Manifesto. What does the last line of the Manifesto actually mean ("while there is value in the items on the right...")?**

The four values: individuals and interactions over processes and tools; working software over comprehensive documentation; customer collaboration over contract negotiation; responding to change over following a plan. The last line is the most overlooked part of the Manifesto: it clearly says the items on the right (process, documentation, contracts, plans) are not rejected — they just get lower priority when they conflict with the items on the left. The Manifesto is not about giving up on planning and documentation. It's about the fact that when there's a conflict between them and working software or the ability to adapt, the second one wins.

---

**What is the difference between the Product Owner and Scrum Master roles?**

The Product Owner is responsible for maximizing product value: managing the Product Backlog, setting the Product Goal, and deciding what to do and in what order. The Scrum Master is responsible for how effectively Scrum is used: facilitating events, removing impediments, and coaching the team and the organization. The PO does not tell people *how* to do the work — that's the Developers' decision. The Scrum Master is not the manager of the Developers, and does not decide what goes into the backlog — that's the PO's job. Both roles exist to serve the team, not to command it.

---

**How does Definition of Done differ from Definition of Ready?**

Definition of Done is an official part of the Scrum Guide: a formal quality standard that any Product Backlog Item must meet to count as part of the Increment (for example: code reviewed, has test coverage, deployed to staging). Definition of Ready is not part of the official Scrum Guide, but it's a very common practice: conditions a task must meet before it can even enter Sprint Planning (clear acceptance criteria, an estimate, dependencies identified). DoD is about the quality of the output; DoR is about the readiness of the input.

---

**Why is the Daily Scrum not a status report for a manager?**

The event belongs to the Developers and exists so they can adjust the Sprint Backlog for the next 24 hours — the team syncs on progress toward the Sprint Goal and finds blockers that they themselves solve. If the standup turns into each person reporting to a manager or tech lead in turn, the event loses its purpose: people talk "for the record," nobody really listens to the next person, and real blockers get pushed to "let's talk after" and forgotten there. A useful test: if you remove the manager from the room, does the standup still mean anything to the team?

---

**Why aren't story points just a stand-in for hours?**

Story points measure the complexity, size, and uncertainty of a task *relative to other already-estimated tasks*, not calendar time. The reasons: different people work at different speeds (a task that takes a senior developer 3 hours might take a mid-level developer 8), and a time-based estimate almost always turns into a promise or deadline in a manager's mind, no matter how much uncertainty it actually carried. Story points create some psychological distance from a literal time promise — as long as they don't get converted back into hours through velocity, which is a common failure mode covered separately below.

---

**What is the difference between Cycle Time and Lead Time?**

Cycle Time is the time from when work on a task actually starts to when it finishes — an internal metric that matters to the team for judging its own speed. Lead Time is the time from when a request arrives (a task is created or enters the backlog) to when it finishes — it includes all the waiting time before work starts, plus the Cycle Time itself. Lead Time is a customer-facing metric: it answers "how long from the moment I asked, to the moment I get it." Lead Time is always ≥ Cycle Time.

---

**What is a WIP limit, and why does going over it hurt more than it looks?**

A WIP limit (Work In Progress limit) caps how many tasks can be in progress at once at a given stage. Behind it is Little's Law: Cycle Time = WIP / Throughput — if WIP grows without a matching rise in throughput, cycle time for every individual task has to grow. There's a second reason too: the cost of context switching — holding several parallel tasks in mind at once costs real time and mental energy that doesn't add value to any single one of them. A WIP limit forces the team to focus, and naturally redirects effort to wherever the real bottleneck actually is.

---

**What is a Sprint Goal, and why does it matter more than just a list of tickets for the sprint?**

The Sprint Goal is one connected goal for the sprint that explains why the chosen set of tasks makes sense together, and it lets the team stay flexible about implementation details without losing focus on the outcome. A list of tickets without a goal is just a work queue; if something unexpected happens (a task turns out harder than expected), a team with a clear Sprint Goal can re-prioritize *within* the goal ("let's drop a minor feature but deliver the main one"), while a team without a goal just loses focus, unsure what on the list is actually critical.

---

**What is Backlog Refinement, and why is it not the same thing as Sprint Planning?**

Backlog Refinement is an ongoing activity during the sprint: adding detail, estimates, and order to upcoming Product Backlog Items, so they meet the Definition of Ready by the time they enter a sprint. Sprint Planning is a one-time event at the start of the sprint, where a specific amount of work is chosen from an already-prepared backlog. Good refinement makes planning fast and predictable; without it, planning turns into an improvised discussion of unclear tasks exactly when the team needs to commit to scope.

---

## Senior

**What is the difference between "being Agile" and "doing Agile ceremonies"? Give a concrete example of this difference in practice.**

"Being Agile" means actually working according to the Manifesto's values: short feedback loops with real users, willingness to change the plan when reality changes, a self-organizing team, and a retro that genuinely changes behavior. "Doing the ceremonies" means performing the outer shape (sprints, standups, a board, a retro) without the function these things were built for. A concrete example: a Sprint Review attended only by a manager who already knows what's coming, versus a Sprint Review with real users or stakeholders whose feedback actually reorders the Product Backlog. From the outside, both look the same — "we held a demo" — but in substance, one produces feedback from reality and the other doesn't.

---

**What is Zombie Scrum / Cargo Cult Agile, and how would you diagnose it on a team you've just joined?**

Cargo Cult Agile is when a team copies the visible parts of Scrum without reproducing the mechanism they were built for: a short feedback loop with reality. Zombie Scrum is a more specific term for the same situation applied to Scrum: the events happen formally, but the team is "dead inside" — no real inspection, no real adaptation. To diagnose it without asking the team directly: look at the retro's action items over the last 4–6 sprints and see if the same items keep repeating; check who actually attends the Sprint Review and whether their feedback ever changes backlog priorities; compare the scope committed at Sprint Planning against what actually got delivered over several sprints.

---

**Explain why Planning Poker actually works — what does the technique surface, beyond an averaged number?**

The real value isn't in mathematically averaging guesses — it's that a gap between estimates is a signal, not noise. If one person says "2" and another says "13" for the same task, that means the two people have a fundamentally different understanding of the scope or hidden complexity, and the right response is a discussion ("why did you say 13?"), not an average. Revealing cards privately and simultaneously removes anchoring bias: if estimates were spoken aloud one at a time, the first number would inevitably shape how everyone else thinks about the task. The real output of planning poker is hidden misunderstandings uncovered before the sprint starts, when they're cheap to fix.

---

**A team keeps missing its sprint commitments, and management wants the team to "estimate more accurately." What's actually wrong here, and what do you say?**

The problem is probably not estimation accuracy — it's a misunderstanding of what an estimate even is: it's being treated as a promise instead of a probability-based forecast. The first step is collecting data: how much of the Sprint Backlog, on average, gets displaced by unplanned work, and how many Sprint Goals are actually met. If the misses are explained by constant unplanned insertions, not bad estimation, the real problem is a structural mismatch (maybe Scrumban is needed instead of hard-locked Scrum — see article 04). The conversation with management should be grounded in these numbers: "estimates can't get more accurate while 50% of the work gets added after the estimate is already made."

---

**Given Team X (a support queue, unpredictable flow) and Team Y (planned feature roadmap work), which structure fits which team, and why?**

Team X (support) fits Kanban: work arrives continuously and unpredictably, the SLA demands a response right now, not "after the next Sprint Planning"; WIP limits and flow metrics (cycle time, throughput) give a probability-based SLA forecast without artificially forcing work into sprints. Team Y (planned features) fits Scrum: work can be batched over a 1–2 week horizon, there are outside stakeholders who benefit from a predictable sync point (a demo every two weeks), and a fixed Sprint Goal gives useful focus. The real decision axis is how predictable and "batchable" the incoming work is — not the team's label ("we're a product team," "we're a support team").

---

**What is a watermelon status report, and how do you catch one before it becomes a crisis?**

A watermelon status report ("green outside, red inside") is a status report that shows "on track" at the surface, while the real work underneath is in serious trouble. It happens because of structural incentives: reporting rewards optimistic rounding, and an "at risk" label quietly gets downgraded to avoid an uncomfortable conversation. You catch it not by trusting the words ("in progress"), but by watching objective signals: comparing committed scope to actual delivered scope over several sprints, tracking tasks stuck in a status far longer than the team's normal cycle time without anyone escalating, and asking direct follow-up questions in standup instead of accepting a vague "everything's fine."

---

**How would you negotiate getting technical debt into the backlog, if the PO keeps deprioritizing it?**

Write tech debt as a full backlog item with the same rigor as a feature — not a vague "we should really refactor this," but a concrete cost of inaction: "this shortcut adds about 2 hours to every related feature, and we've already paid that cost N times this quarter," ideally backed by data (rising cycle time on related tickets, incident frequency). Negotiate a standing capacity allocation (say, a fixed 15–20%), instead of begging for time one sprint at a time. The core idea: make the cost of inaction visible and measurable, because the PO physically cannot prioritize something they can't see in a structured form in the backlog.

---

**What is Goodhart's Law, and how does it apply to using velocity as a KPI?**

Goodhart's Law: "when a measure becomes a target, it stops being a good measure." Applied to velocity: as long as it's an internal forecasting tool a team uses for itself, it's useful. The moment velocity turns into a KPI with consequences ("velocity must go up every sprint," comparing velocity across teams), the team gets a rational reason to optimize the number itself — inflating estimates (what used to be a "5" becomes an "8") — instead of actually delivering more value. Velocity formally goes up. Real delivery speed does not.

---

**A stakeholder, under deadline pressure, demands a single number from you for an uncertain task. Walk through how you respond.**

I don't give a flat estimate — I explicitly break the task into known and unknown parts ("part A is clear, 3 days, high confidence; part B is integration with an unfamiliar API, that's where the uncertainty is"). I propose a time-boxed spike (say, one day) to resolve the key unknown before committing to a number. After the spike, I give a range or confidence interval instead of a single figure ("5–7 days in the simple case, up to 12 in the complex one"), backed by historical flow data on similar tasks where possible. If the stakeholder insists on a number right now, I state the consequences directly: either we cut scope, or the risk of breaking a public promise to the client becomes visible now, instead of quietly showing up in three weeks.

---

## Lead

**What is the "Spotify model," and why is citing it as a scaling framework a red flag in an interview?**

The "Spotify model" (Squad / Tribe / Chapter / Guild) is not an official framework — it's a snapshot of Spotify's organizational culture as of 2012, described in a white paper by Henrik Kniberg and Anders Ivarsson, who explicitly said it was an imperfect, still-evolving state, not a recipe to copy. Spotify itself later changed its structure many times and moved away from much of what was described. Citing it as a ready-made, prescriptive framework is a sign the candidate is repeating a diagram without knowing the nuance. Worse, many companies copied only the terminology (renaming teams "squads") without bringing over the culture of autonomy and trust that actually made the structure work — this is Cargo Cult Agile applied to organizational design.

---

**Your organization has 6 teams building one product, with constant mutual blocking. Walk through how you'd choose between Scrum of Scrums, LeSS, and SAFe.**

First, I'd diagnose the real nature of the problem: is this lightweight coordination (a few dependencies that a regular sync between team representatives could solve), or is it a deeper issue of shared product and architecture ownership? If the dependencies are mostly about information ("what is the other team doing") — I'd start with a lightweight Scrum of Scrums, since it's cheaper to adopt and doesn't require reorganizing anything. If the problem runs deeper — the teams genuinely need one shared Product Backlog and a shared Definition of Done for coordinated prioritization — I'd look at LeSS, which is deliberately minimalist and solves coordination through self-management instead of adding a management layer. I'd only consider SAFe if the organization is large, operates in a regulated industry, and genuinely needs enterprise governance and synchronized releases at a scale that Scrum of Scrums or LeSS don't cover — SAFe's weight is only justified by that level of complexity, not by default.

---

**As a senior IC with no formal authority, how do you get a Scrum Master to stop rigidly running ceremonies that no longer serve the team?**

I start with a private conversation, not a public confrontation at the retro. The argument is built on data, not feelings: "over the last 4 sprints, only one manager has attended our Sprint Review, no real users have ever been there, and not a single review has changed backlog priorities" — that's a specific, checkable pattern, not a general complaint that "retros feel boring." I frame it around impact, not blame: "here's what I'm seeing," not "you're doing this wrong." I propose a concrete experiment ("let's invite a real user to the next Review and see if anything changes") instead of just criticizing the current format. If that doesn't help, I use the retro as the legitimate channel to raise it with the whole team, backed by the same data.

---

**Leadership asks for "just one crunch sprint" to hit a deadline. How do you handle this as a lead?**

I don't unilaterally refuse, and I don't quietly agree and pass the pressure on to the team as overtime — I make the trade-off explicit and visible. I state a concrete choice for leadership: "we can hit this date if we cut scope Y, add resources Z, or accept the risk of building up technical debt in area W — which do you want?" This is a direct extension of the pushback technique used for estimation pressure, applied at the scale of the whole team. I also name the cost of a precedent directly: agreeing to "just this once" without an explicit statement that it's an exception, not a new norm, almost always becomes the new norm — and I make that cost visible to leadership ahead of time, not after the fact.

---

**A team's retro has raised the same three issues for the last five sprints with no resolution. What do you do differently as the person responsible for the team's health?**

First, I stop letting the team "raise an issue" without a real commitment to solving it — I introduce a mandatory, checkable action-item log (owner, due date, a follow-up check at the next retro), not a wish list nobody opens again. Second, I name the pattern out loud: "we've talked about slow CI five sprints in a row — let's actually block time to fix it this sprint, instead of raising it a sixth time." Third, if the issue is outside the team's own authority (say, it depends on another department), it's my job as the lead to escalate it beyond the team, instead of letting it stay an unsolved retro item forever, inside a team that has no authority to fix it on its own.

---

**How do you tell whether a team is doing real Scrum or performing "Scrum theater," using only observable signals, without asking the team directly?**

I look at specific, checkable signals, not the team's self-description. Sprint Review: do real users or stakeholders show up, and does their feedback actually change the backlog afterward, or is it a demo for the same manager every time? Retrospective: do the same action items keep repeating sprint after sprint with no traceable resolution? Daily Scrum: if you remove the manager from the room, does the format of the meeting change — if yes, it was already a report, not the team adapting its own plan. Sprint Planning: does the team actually discuss and push back on scope, or silently listen to an already-finished ticket list? Several of these signals lining up gives a confident diagnosis without ever asking "are you doing real Scrum?" — a question the team will almost always answer "yes" to, regardless of reality.
