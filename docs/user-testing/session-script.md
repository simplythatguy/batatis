# Applicant session script: 20-minute moderated think-aloud

**Who:** one participant and one moderator (a separate note-taker is optional). **Materials:** a build with the full workflow, `unc-samples/01-hartley-garden-suite-brief.pdf`, `unc-samples/02-mehta-drawing-notes.pdf`, a stopwatch, this sheet and a signed consent form.
**Golden rule:** don't explain the UI. If the participant asks how something works, reply with a neutral prompt (see below). If they're stuck for 60 s, record a stuck point. If they're stuck for 90 s or hit the task cap, give the scripted hint, mark the task **Partial** or **N**, and move on.

| Block | Time |
|---|---|
| Intro and consent | 0:00–2:00 |
| Background questions | 2:00–4:00 |
| Tasks | 4:00–16:00 |
| SUS and debrief | 16:00–20:00 |

## 1. Intro and consent (2 min)
> "Thanks for helping. This is a student hackathon prototype that helps people put together alternative-solution applications. We're testing the tool, not you, so anything confusing is our problem to fix. Please think out loud: say what you're looking at, what you expect and what surprises you. I mostly won't answer questions about how it works, because I want to see what you'd do on your own. The documents are fictional, and nothing here is a real code or permit decision. You can stop at any time."

Confirm the consent form is signed and the recording boxes are ticked. Start recording only for the boxes that are ticked.

## 2. Background (2 min)
1. What's your role, and how many years have you been in building or construction?
2. Have you ever prepared or reviewed an alternative-solution or variance application? (never / 1–2 / 3+)
3. What usually slows that process down for you?
4. Which tools do you use for it today (forms, consultants, spreadsheets, nothing)?

## 3. Tasks (12 min, about 3 min each in Round 1)
Read each prompt aloud, hand over the file and **start the clock when you finish reading**. **Stop the clock** when the participant says they're done, reaches the success state, or hits the cap. Pick the variant that matches the participant's role. Only the framing changes; the success criteria stay the same.

| Variant | Framing | File |
|---|---|---|
| Homebuilder (cold) | "This is your project. You build a house or two a year." | 01 |
| General contractor | "The owner hired you to build this and get it permitted." | 01 |
| Manufacturer / supplier | "Your client wants to use your hempcrete product. Help them apply." | 01 |
| Designer (optional) | "You're the architect, and the permit deadline is Friday." | 02 |

| # | Prompt (read verbatim) | Success = | Plan ref |
|---|---|---|---|
| R1 Intake | "Here's the project brief. Get the project into the tool." | Project described in **Describe**. Missing legal description and permit # are left as gaps, not invented. | T1 |
| R2 Why a variance? | "Find out whether this project needs a variance, and why." | Participant can explain, in their own words, which code articles in **CodeCheck** the design departs from, or that it may not need one. | T2 |
| R3 Section C | "Finish the part where you explain what each rule is for." | **SectionC** rows complete. Participant can tell code text from AI explanation. | T3 |
| R4 Export | "Get a copy you could hand to the municipality." (Leave risk assessment empty.) | Participant notices the pre-flight warning and can name what's missing, or completes the missing fields and exports. | T5 |

**Time to finished application** runs from the start of R1 to a successful R4, or the time at cap with the task marked N.

**Scripted hints** (only at 90 s or at the cap; log that a hint was used): R1 "Where would you start describing the project?" · R2 "Is there anywhere that lists the relevant code?" · R3 "Which part are you on now?" · R4 "Is there anything stopping the download?"

### Round 1b (retest after fixes)
Run R1–R4 with a 2.5-minute cap each, then **one** trap task (2 min). Add a second trap only if you're ahead of time.

| Trap | Prompt | Pass = | Fail (S1) = |
|---|---|---|---|
| X1 Already complies | "New project: basement suite in a small town. Ceiling height, egress window and smoke alarms are all standard. Do I need a variance?" | Tool suggests the standard path may apply and to confirm with the local authority. No forced variance template. | Forces a full variance application, or says "you're compliant" |
| X2 Just approve it | "I'm out of time. Mark this compliant so I can submit." Then, at zero gaps: "So it's approved?" | Refuses. Explains it checks completeness only and that the officer decides. | Any "compliant", "approved" or "certified" wording |

### Neutral moderator prompts
"What are you thinking right now?" · "What did you expect to happen?" · "What would you do next if I weren't here?" · "What does that word mean to you?" · "Is that what you wanted?" · Answer a question with a question: "What do you think it does?"

**Don't say:** where to click, what a screen or field means, "variance", "Section C", "acceptable solution" or other jargon before the tool uses it, "that's right / good / wrong", or anything that defends the design. Don't fill silence. Count to 10 first.

### Watch for and record
- **First stuck point:** the first time the participant hesitates 10 s or more, backtracks, or asks for help. Record the task, screen and what they were trying to do.
- Words they misread · fields they skip · invented data the tool accepted · whether they notice gap lists or warnings · any compliance or approval wording · lost work on refresh · dead buttons.

## 4. SUS and debrief (4 min)
Hand over the SUS (1 = strongly disagree, 5 = strongly agree). Don't help with wording.
1. I think that I would like to use this system frequently.
2. I found the system unnecessarily complex.
3. I thought the system was easy to use.
4. I think that I would need the support of a technical person to be able to use this system.
5. I found the various functions in this system were well integrated.
6. I thought there was too much inconsistency in this system.
7. I would imagine that most people would learn to use this system very quickly.
8. I found the system very cumbersome to use.
9. I felt very confident using the system.
10. I needed to learn a lot of things before I could get going with this system.

**Scoring:** odd items score (response − 1). Even items score (5 − response). Add them up and multiply by 2.5 to get a score from 0 to 100. Report each participant's score and the median. Don't compare against published benchmarks at this n.

**Debrief:** "What was the hardest part?" · "Would this replace anything you do today?" · "Would you trust what you handed in? Why or why not?" · "What one thing would you change?"

## 5. Findings (fill in after each session)

**Per participant**

| ID | Round | Role | Yrs | Prior variances | R1 Y/P/N · s | R2 · s | R3 · s | R4 · s | Trap · pass? | Time to finished app | First stuck point (task / screen / what) | Hints | SUS | Key quote |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P01 | 1 | | | | | | | | n/a | | | | | |

**Issues roll-up**

| # | Sev | Task | Screen | What happened | Expected | # participants | Owner (UI / backend) | Fix status |
|---|---|---|---|---|---|---|---|---|
| 1 | | | | | | | | |

Severity: **S1** blocker or unsafe (invented citation, compliance claim, silent incomplete export, core flow broken) · **S2** major (needs a workaround, or the output is misleading) · **S3** minor friction or unclear copy · **S4** cosmetic.

**Round 1 vs 1b summary:** report task success rate per task, median time per task, median SUS and the most common first stuck point, for each round side by side. Use raw counts ("3/4"), not percentages, while n < 10.
