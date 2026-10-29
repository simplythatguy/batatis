# Measured AI cost per application

**Measured on 3 complete applications (2026-10-29): the AI cost US$0.88 (C$1.23) per application on average, and C$0.97 to C$1.69 per run.** Drafting the case is almost 90% of it. The officer side costs nothing, because the package review is rule-based.

Every number in the first three tables is measured. Each paid model call appended its reported tokens to a log (`BATATIS_SPEND_LOG`, see `engine/llm_gate.py`). US$ is the token count times the list prices in `engine/llm_gate.py`. C$ uses 1.4057 CAD per USD, the same rate as [the business plan](../business-plan.md#6-cost-per-application).

## Per application

| Run | US$ | C$ | Paid calls |
|---|---:|---:|---:|
| 1 | 0.69 | 0.97 | 13 |
| 2 | 1.20 | 1.69 | 17 |
| 3 | 0.74 | 1.04 | 13 |
| **Average** | **0.88** | **1.23** | 14.3 |

## By stage (average of the 3 runs)

| Stage | Calls | US$ | C$ | Business-plan estimate (US$) |
|---|---:|---:|---:|---:|
| Reading the description | 1 | 0.011 | 0.016 | 0.08 |
| File review (the attached PDF) | 1 | 0.064 | 0.090 | 0.22 |
| Code identification (rank, then verify, twice) | 4 | 0.029 | 0.040 | 0.016 |
| Drafting the case and the application wording | 7.3 | 0.771 | 1.083 | 0.25 (drafting 0.14 + audit 0.11) |
| Assistant (one question) | 1 | 0.002 | 0.002 | 0.006 (five answers) |
| Officer side: claim, package review, decision | 0 | 0 | 0 | 0 |
| **Total** | 14.3 | **0.876** | **1.232** | **0.57** |

## By stage, per run (US$)

| Stage | Run 1 | Run 2 | Run 3 |
|---|---:|---:|---:|
| Reading the description | 0.011 | 0.011 | 0.011 |
| File review | 0.060 | 0.065 | 0.067 |
| Code identification | 0.028 | 0.029 | 0.029 |
| Drafting | 0.588 (6 calls) | 1.096 (10 calls) | 0.629 (6 calls) |
| Assistant | 0.002 | 0.002 | 0.002 |
| Officer side | 0 | 0 | 0 |

## Why it is higher than the US$0.57 estimate

- **Drafting runs more than once.** The estimate assumed one drafting run and one audit. A real applicant drafts the case, then drafts the application wording, and drafts again when later answers make a draft stale. That makes 2 to 3 drafting rounds of 2 to 5 calls each. Each call reads about 30,000 to 40,000 tokens of sources and case, and writes 2,000 to 6,600, so it costs about US$0.09 to US$0.12.
- **Run 2 is the outlier.** Its first case draft (3 calls, US$0.32) was never accepted: the test driver missed the Accept button, so the case was drafted again. Without that round, run 2 is US$0.88 and the 3-run average is US$0.77 (C$1.08).
- **Reading and file review cost less than estimated.** The estimate allowed two reads of the description and a larger document review. Each run made one read call (about 1,350 tokens in) and one review call (about 8,500 in, 4,300 out).
- **Code identification costs more than estimated.** Each of the two ranking calls reads about 100,000 tokens, but at the small model's price the stage is still about US$0.03.

## How it was measured

- **App.** A clean copy of this branch's `HEAD` with the spend log switched on: engine on port 8100, web on port 3100, AI on, and a fresh case store. The rate limits and daily cap were raised for this process only, so no call was refused and retried.
- **Case.** The Edmonton row-house case: the v2 description plus `incomplete.pdf` from the studio case.
- **Applicant steps.** Describe and attach, read, rules, questions, Draft my case and Accept all, proof, paperwork, Check my application, then Draft my application and Accept. The applicant then wrote the upkeep text, answered the last rule question, and attached a supporting report as evidence. Last came consent, both signatures, and Submit to Edmonton.
- **Assistant.** The applicant asked one question, with the application open.
- **Officer.** A new Edmonton reviewer account opened the application, which claimed it and ran the package review, then returned it with the information request.
- **Supporting report.** It is a 2-page test PDF made for these runs. Attaching it made no AI call.
- **Run 1 extras.** One more assistant call (US$0.0004) was asked with no application open, and it is left out. Run 1's final submit was the same API request as the Submit button.
- **Logs.** Kept outside the repo in `/tmp/spend/run1.jsonl`, `run2.jsonl` and `run3.jsonl`.

## Appendix: tokens per model (average per application, measured)

| Model | Used for | Calls | Input tokens | Output tokens | List price, US$ per 1M in / out | US$ |
|---|---|---:|---:|---:|---|---:|
| Claude Sonnet 5.5 | Reading, file review, drafting | 9.3 | 247,098 | 35,165 | 2 / 10 | 0.846 |
| Claude Haiku 5.5 | Code identification, assistant | 5 | 260,812 | 8,671 | 0.10 / 0.50 | 0.030 |

Input tokens include any cache reads and writes, priced as normal input. If caching took place, the true bill is a little lower.
