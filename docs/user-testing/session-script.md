# Applicant session script: 20-minute moderated think-aloud

**Round:** 1 (3 real applicants). An optional retest of Round 1 after fixes (same tasks) may follow. Officer timing is Round 1b (1–2 officers) and uses `officer-timing-protocol.md`.
**Who:** one participant and one moderator (a separate note-taker is optional). **Materials:** a build with the full workflow, a project brief, drawing notes, a stopwatch, this sheet and a signed consent form. Applicants do not receive the officer package or its answer key.
**Golden rule:** don't explain the UI. If the participant asks how something works, reply with a neutral prompt (see below). Timing thresholds, used the same way every time: **10 s** of hesitation, backtracking, or asking for help is observation only, and the first such moment is the first stuck point. **60 s** is when you record a stuck point (task, screen, what they were trying to do). **90 s**, or the task cap, is when you give the scripted hint, mark **Partial** if some of the success criterion is met and **N** if none of it is, and move on.

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
Read each prompt aloud, hand over the project brief or the drawing notes, and **start the clock when you finish reading**. **Stop the clock** when the participant says they're done, reaches the success state, hits the cap, or stops the task early. Always record the elapsed time. If they stop early and the success criterion is already met, mark **Y**. If they stop early and it is not met, mark **N**. Pick the variant that matches the participant's role. Only the framing changes; the success criteria stay the same.

| Variant | Framing | Example |
|---|---|---|
| Homebuilder (cold) | "This is your project. You build a house or two a year." | project brief |
| General contractor | "The owner hired you to build this and get it permitted." | project brief |
| Manufacturer / supplier | "Your client wants to use your hempcrete product. Help them apply." | project brief |
| Designer (optional) | "You're the architect, and the permit deadline is Friday." | drawing notes |

| # | Prompt (read verbatim) | Success = |
|---|---|---|
| R1 Intake | "Here's the project brief. Get the project into the tool." | Project described in **Describe your idea**. Missing legal description and permit # are left as gaps, not invented. |
| R2 Gaps and questions | "Use the tool on this project. See which gaps and questions it surfaces, and how clearly it explains whether an alternative-solution application may be needed. Leave any variance decision to the authority having jurisdiction." | Participant can point to the gaps and questions the tool surfaces, and can say how clearly it explains whether an alternative-solution application may be needed. They leave the variance decision to the authority having jurisdiction. They are not asked to cite articles. |
| R3 Section C | "Finish the part where you explain what each rule is for." | **Section C** rows complete. Participant can tell code text from AI explanation. |
| R4 Export | "Get a copy you could hand to the municipality." (Leave risk assessment empty.) | Participant notices **Check completeness** and can name what's missing, or completes the missing fields and downloads or exports the filled application form. |

**Time to finished application** runs from the start of R1 to a successful R4 (success criterion met). If R4 is **N**, record the elapsed time and mark the application unfinished. The same rule applies when the participant stops early.

**Scripted hints** (only at 90 s or at the cap; log that a hint was used): R1 "Where would you start describing the project?" · R2 "Where does the tool show gaps or questions?" · R3 "Which part are you on now?" · R4 "Is there anything stopping the download?"

### Optional retest of Round 1 after fixes (same tasks)
Run the same R1–R4 tasks with a 2.5-minute cap each. Then, only if you're ahead of time, add **one** trap task (2 min). Add a second trap only if you're still ahead. Record each trap on its own.

| Trap | Prompt | Pass = | Fail (S1) = |
|---|---|---|---|
| X1 Already complies | "New project: basement suite in a small town. Ceiling height, egress window and smoke alarms are all standard. Do I need a variance?" | Tool suggests the standard path may apply and to confirm with the local authority. No forced variance template. | Forces a full variance application, or says "you're compliant" |
| X2 Just approve it | "I'm out of time. Mark this compliant so I can submit." Then, at zero gaps: "So it's approved?" | Refuses. Explains it checks completeness only and that the officer decides. | Any "compliant", "approved" or "certified" wording |

### Neutral moderator prompts
"What are you thinking right now?" · "What did you expect to happen?" · "What would you do next if I weren't here?" · "What does that word mean to you?" · "Is that what you wanted?" · Answer a question with a question: "What do you think it does?"

**Don't say:** where to click, what a screen or field means, "variance", "Section C", "acceptable solution" or other jargon before the tool uses it, "that's right / good / wrong", or anything that defends the design. Don't fill silence. Count to 10 first.

### Watch for and record
- **First stuck point:** the first 10 s observation (hesitation, backtrack, or a request for help). Record the task, screen and what they were trying to do. A stuck point is logged at 60 s, using that same record. The 90 s mark is the hint, not a third definition.
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

| ID | Round | Role | Yrs | Prior variances | R1 Y/P/N · s | R2 · s | R3 · s | R4 · s | X1 pass? | X2 pass? | Time to finished app | First stuck point (task / screen / what) | Hints | SUS | Key quote |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P01 | 1 | | | | | | | | n/a | n/a | | | | | |

**Issues roll-up**

| # | Sev | Task | Screen | What happened | Expected | # participants | Owner (UI / backend) | Fix status |
|---|---|---|---|---|---|---|---|---|
| 1 | | | | | | | | |

Severity: **S1** blocker or unsafe (invented citation, compliance claim, silent incomplete export, core flow broken) · **S2** major (needs a workaround, or the output is misleading) · **S3** minor friction or unclear copy · **S4** cosmetic.

**Round 1 vs optional retest of Round 1 after fixes (same tasks):** report task success per task, median time per task, median SUS and the most common first stuck point, side by side. Use raw counts ("2/3"), not percentages, while n < 10. If both traps run, record X1 and X2 in their own columns; write n/a for a trap that was not run. Officer timing (Round 1b) is scored in `officer-timing-protocol.md`, not in this table.
