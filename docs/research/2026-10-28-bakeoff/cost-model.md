# Batatis cost model

Written 2026-10-28 for the 2026-10-29 demo. All amounts are Canadian dollars (C$) unless they say US$. Every parameter, with its low, base and high values, unit, source, date read and kind, is in [`cost-params.json`](./cost-params.json). The computed results are in the same file under `derived`.

Each figure has one of three kinds:

- **Published** means an official page or document states it. The source is linked.
- **Measured** means a run in the Batatis repository produced it.
- **Assumed** means we chose it. The basis is given.

## Bottom line

1. **The AI is cheap, and it does not decide the case.** One application costs about **US$0.28 (C$0.39)** in model fees at list prices (range US$0.11 to US$2.05). Hosting at pilot volume adds about **C$0.62**. Our marginal cost is about **C$1 per application**. Paying half a person to keep the jurisdiction packs current and to give support adds about **C$60** (assumed).
2. **Today's process is expensive, and most of the cost lands on the applicant who waits.** A bespoke application costs about **C$14,200** across preparation, review and rework. Each extra "more information" round costs about **C$3,600**, and 59% of that is carrying cost while the project waits. For a repeat house variance the total is about **C$770**. For a complex Part 3 case it is about **C$104,000**. All three are estimates built from published wages, fees and rates plus our assumptions.
3. **Alberta-wide, rework and delay cost about C$3.6M a year (base).** The range is C$0.7M to C$26M. Officer time is a small part of this, about 2.75 full-time officers. The rest falls on applicants.
4. **Batatis is cheaper than the current process if it removes one extra round in every 60 bespoke applications.** That covers the C$61 loaded cost. Counting only marginal cost, it needs one round in every 3,600. If it removes 35% of extra rounds, as comparable AI pre-checks report for ordinary permits, it saves about C$2,000 on a bespoke application. No one has measured that for Batatis.
5. **A rival that is 5 points less accurate and 99% cheaper loses on cost.** On a bespoke application it saves the applicant under C$1 of Batatis's marginal cost. It adds about C$240 to C$840 of expected rework (it would save C$60 against our loaded cost). **On repeat house variances the gap shrinks to about C$30 to C$120, so a cheap rival can win there on price.** We should price repeat filings low and earn on the hard cases.

## What changed from the repo's older figures

- `docs/business-plan.md` §6 and `docs/judge-qa.md` Q4 say "about US$0.02 per identification run" and "US$0.05 per application". **Those figures are stale.** They priced the Oct 21 pipeline, which screened all 2,080 articles with a paid model. The current pipeline (`engine/identify/pipeline.json`, Oct 26) screens articles deterministically, so identification now costs about US$0.002 per run. Applicant drafting was added on Oct 26. It makes two GPT-6.1 Sol calls (draft and audit), and **those two calls are about 90% of the AI cost**.
- The brief says Claude Haiku 5.5 at medium effort is the default model. In the code, Haiku 5.5 runs only the assistant (`engine/routes_assist.py`). The identify verifier, intake reader and document review use GPT-6 Luna, and drafting uses GPT-6.1 Sol. **Luna and Haiku 5.5 have the same list price** (US$0.10 in, US$0.50 out per million tokens), so moving those steps to Haiku changes nothing. Moving drafting to Haiku would cut the base AI cost from US$0.28 to about **US$0.04**.
- Haiku 5.5's price in `engine/llm_gate.py` (US$0.10 / US$0.50) matches Anthropic's pricing page, read today. Prompts over 100,000 tokens cost US$0.50 / US$2.50. A long document review on Haiku would cross that threshold, and the gate does not price the over-100K tier.
- The README counts **3,088 building articles varied** in January to June 2026. That number counts article entries, not applications, because one variance can cite several articles.

## Parameters

Case-type parameters use three columns. **Low** is a repeat Part 9 house variance, such as roof soffits near the property line (9.10.15.5.(8), 49% of 2026 entries). **Base** is a bespoke Part 9 or small-building case. **High** is a complex Part 3 case that needs a fire engineer.

| Parameter | Low | Base | High | Unit | Kind | Source |
|---|---:|---:|---:|---|---|---|
| Building variance applications a year | 837 | 1,700 | 6,176 | per year | Published | Council Annual Report 2023 (837 in 2023, incomplete; 1,698 and 1,713 in 2021 and 2022). High = Data Hub article entries x 2, a ceiling |
| Mix: repeat / bespoke / complex | 95 / 4.5 / 0.5% | 88 / 10 / 2% | 80 / 15 / 5% | share | Assumed | The Council does not record variance type. The top five articles are 81% of entries |
| Officer wage, Safety Codes Officer II, Edmonton | 43.92 | 50.23 | 56.53 | C$/hour | Published | City of Edmonton posting, Apr 14, 2026. ALIS gives C$46.50 for construction inspectors (2023 survey) |
| Benefits and overhead multiplier | 1.25 | 1.35 | 1.50 | x wage | Assumed | Not published. Ceiling check: the Council allows C$125/h for an alternative solution in areas the Alberta Safety Codes Authority serves |
| Loaded officer cost | 54.90 | 67.81 | 84.80 | C$/hour | Estimate | Wage x multiplier. The model uses the base value for all case types |
| Engineer billing rate | 160 | 225 | 265 | C$/hour | Published | ACEC Saskatchewan 2026 minimum rates (E1, E3 project engineer, E4 specialist). Saskatchewan, not Alberta |
| Builder or designer time, repeat filings | 75 | 100 | 120 | C$/hour | Assumed | Repo research assumption |
| Carrying-cost interest rate | 5.7 | 7.0 | 9.0 | %/year | Assumed | The Bank of Canada raised its policy rate to 2.5% on Oct 28, 2026 (published). Prime plus a loan spread is our assumption |
| Money tied up while waiting | 250,000 | 400,000 | 2,000,000 | C$ | Assumed | One house; the repo's figure for one house; a small multi-unit project |
| Carrying cost per month | 1,188 | 2,333 | 15,000 | C$/month | Estimate | Money tied up x rate / 12. BILD/Altus put GTA approval delay at C$2,600 per apartment per month (Ontario, 2022) |
| First-submission preparation | 400 | 8,000 | 40,000 | C$ | Assumed | No Alberta consultant fee is published. 4 h x C$100; about 35 h x C$225; 150 h x C$265. An Australian 2026 memo prices performance-based fire engineering at 15,000 to 40,000+ (AUD) |
| Officer hours, first review | 1 | 6 | 16 | hours | Assumed | Not published. Kingston, ON charges C$318.25/h with a C$2,000 minimum (6.3 h). Toronto C$2,368.32, Ottawa C$430 to C$1,080 |
| Extra rounds per application today | 0.6 | 1.6 | 2.4 | rounds | Published (other places) | Surrey 1.6 resubmissions; Denver 37% first-pass acceptance (implies 1.7); Honolulu 3.4 cycles. Ordinary permits, not Alberta variances. Low is assumed |
| Officer hours per extra round | 0.5 | 2 | 6 | hours | Assumed | |
| Applicant hours per extra round | 2 | 6 | 20 | hours | Assumed | At C$100, C$225, C$265 |
| Delay per extra round | 1 | 4 | 6 | weeks | Published (guidance) | CWC/WoodWorks BC guide: allow 1 to 2 months for correspondence. Low is assumed |
| Extra rounds Batatis removes | 20 | 35 | 60 | % | Assumed | Not measured for Batatis. Seattle 35% fewer correction cycles; Honolulu 3.4 to 1.4 cycles (city-reported) |
| Haiku 5.5 price | 0.10 / 0.50 | 0.10 / 0.50 | 0.50 / 2.50 | US$ per 1M tokens | Published | Anthropic pricing page. High = prompts over 100K tokens |
| GPT-6 Luna price | 0.10 / 0.50 | 0.10 / 0.50 | 0.20 / 0.75 | US$ per 1M tokens | Published | OpenAI pricing page. High = over 272K tokens |
| GPT-6.1 Sol price | 2 / 10 | 2 / 10 | 4 / 15 | US$ per 1M tokens | Published | OpenAI pricing page |
| Jev reranker price | 0.042 | 0.042 | 0.042 | US$ per 1M input tokens | Measured | Repo benchmark; output free |
| Exchange rate | 1.4057 | 1.4057 | 1.4057 | C$ per US$ | Published | Bank of Canada, Oct 21, 2026 |
| Vercel Pro seats | 20 | 40 | 60 | US$/month | Published | US$20 per seat, 1 to 3 seats assumed |
| Neon database | 0 | 4 | 36 | US$/month | Published | US$0.106 per CU-hour, US$0.35 per GB-month; usage assumed |
| Applications per month, pilot | 300 | 100 | 20 | per month | Assumed | Low column is the cheapest per application |
| Staff for packs and support | 0.25 FTE / 3,000 apps | 0.5 FTE / 1,000 apps | 1 FTE / 300 apps | | Assumed | C$120,000 loaded salary assumed |

Token counts per call are assumptions bounded by the code's caps. They are listed in `cost-params.json` as `tokens_*` and `calls_*`. No applicant has run the full flow with metering on, so **none of the per-application token counts is measured**. The verifier's 4,500 tokens in and 1,100 out were measured on the Oct 21 pipeline.

## Formulas

```
Officer loaded rate     O = wage x multiplier
Carrying cost / month   M = money tied up x interest rate / 12
Cost of one extra round C_round = O x officer hours per round
                                + applicant hours per round x applicant rate
                                + (delay weeks / 4.345) x M
Cost today              C_today = preparation + O x first-review hours + R x C_round
                                  (R = expected extra rounds)
Saving with Batatis     S = R x r x C_round        (r = share of rounds removed)
Batatis cost            B = AI fees + hosting per application (+ staff per application, loaded)
Batatis pays off when   S > B, so r > B / (R x C_round)
```

The model assumes Batatis saves no preparation time. That is conservative. Each 10% of preparation saved is worth C$40, C$800 and C$4,000 in the three cases.

## Batatis cost per application

AI fees, US$ at list prices (base usage: 2 identification runs, 2 intake reads, 1 document review, 1 drafting generation, 5 assistant answers):

| Step | Model | Low | Base | High |
|---|---|---:|---:|---:|
| Rerank 60 articles | Jev | 0.0003 | 0.0009 | 0.011 |
| Verify top 15, quote check | Luna, medium | 0.001 | 0.004 | 0.018 |
| Intake read | Luna, medium | 0.001 | 0.004 | 0.015 |
| Document review | Luna, medium | 0.003 | 0.011 | 0.093 |
| Draft (write) | Sol 6.1, medium | 0.060 | 0.140 | 0.900 |
| Draft (independent audit) | Sol 6.1, medium | 0.044 | 0.110 | 0.960 |
| Assistant answers | Haiku 5.5, medium | 0 | 0.006 | 0.052 |
| **AI total** | | **0.11** | **0.28** | **2.05** |

Example arithmetic for the base draft call: 25,000 input tokens x US$2 per million = US$0.05, plus 9,000 output tokens x US$10 per million = US$0.09, for US$0.14.

| Per application | Low | Base | High |
|---|---:|---:|---:|
| AI fees | C$0.15 | C$0.39 | C$2.88 |
| Hosting (Vercel seats and Neon, divided by pilot volume) | C$0.09 | C$0.62 | C$6.75 |
| **Marginal cost** | **C$0.25** | **C$1.01** | **C$9.63** |
| Staff for packs, support and domain review (assumed) | C$10 | C$60 | C$400 |
| **Loaded cost** | **C$10** | **C$61** | **C$410** |

The limiter is people. At pilot volume, staff cost is 60 times the AI and hosting cost combined. Hosting costs more than the AI at under about 150 applications a month. The high column assumes one full-time person serving 300 applications a year. That is the true cost of an early pilot, and it falls with volume.

## Cost of the problem today

Per application (estimates from the formulas above, base officer rate C$67.81/h):

| | Repeat house | Bespoke | Complex Part 3 |
|---|---:|---:|---:|
| First submission (preparation + officer review) | C$468 | C$8,407 | C$41,085 |
| One extra round: officer | C$34 | C$136 | C$407 |
| One extra round: applicant rework | C$200 | C$1,350 | C$5,300 |
| One extra round: carrying cost of delay | C$273 | C$2,148 | C$20,713 |
| **One extra round, total** | **C$507** | **C$3,634** | **C$26,420** |
| Expected extra rounds | 0.6 | 1.6 | 2.4 |
| Rework and delay | C$304 | C$5,814 | C$63,409 |
| **Total today** | **C$772** | **C$14,221** | **C$104,494** |
| Officer hours | 1.3 | 9.2 | 30.4 |

The rework and delay range, C$304 to C$63,409, matches the organizers' framing of "a few hundred dollars to tens of thousands of dollars" (Challenge Scope, p.2). That framing is anecdotal, and so are our inputs.

Alberta per year:

| | Low | Base | High |
|---|---:|---:|---:|
| Applications | 837 | 1,700 | 6,176 |
| Whole process (preparation, review, rework) | C$1.6M | C$7.1M | C$49M |
| Rework and delay | C$0.7M | C$3.6M | C$26M |
| Officer hours (full-time equivalents at 1,650 h) | 1,507 (0.9) | 4,542 (2.75) | 24,333 (14.7) |
| Officer cost | C$0.10M | C$0.31M | C$1.65M |
| Saved if Batatis removes 35% of extra rounds | C$0.25M | C$1.26M | C$9.3M |

The low and high columns move every input together, so they are wider than any single real year. The high column uses article entries as applications, which overstates volume.

**Nobody publishes how often Alberta variances go back for more information.** The Council says it does not collect the supporting documents. The 1.6 rounds come from Surrey's residential permits and match Denver's 37% first-pass rate. A pilot should measure the real Alberta rate first.

## Is Batatis cheaper than the current process?

Batatis adds a cost and removes rounds. The net per application, with 35% of rounds removed and no preparation time saved:

| | Repeat house | Bespoke | Complex |
|---|---:|---:|---:|
| Saving from fewer rounds | C$107 | C$2,035 | C$22,193 |
| Minus marginal cost (C$1.01) | C$106 | C$2,034 | C$22,192 |
| Minus loaded cost (C$61) | C$46 | C$1,974 | C$22,132 |
| Share of rounds Batatis must remove to break even, loaded | 20% | 1.0% | 0.1% |
| The same, marginal only | 0.3% | 0.02% | 0.002% |

On a bespoke case, Batatis breaks even on loaded cost if it saves one extra round in every 60 applications (C$61 / C$3,634). On marginal cost it breaks even at one round in every 3,600. On repeat house variances the margin is thin. Calgary's standing variances already handle many of those, and a pre-approved package may beat any tool.

## The competitor question

A rival is 5 percentage points less accurate and 99% cheaper. Who wins?

We read "accuracy" as **first-pass completeness**: the chance a submission needs no extra round. If each submission is complete with probability *a*, the expected extra rounds are (1 − *a*) / *a*. The rival's extra cost per application is:

```
Extra cost to the rival's user = (1/a_rival − 1/a_batatis) x C_round
Rival is cheaper overall only if  0.99 x Batatis price > that extra cost
```

| Batatis first-pass rate | Rival | Extra rounds | Repeat house | Bespoke | Complex |
|---|---|---:|---:|---:|---:|
| 90% | 85% | 0.065 | C$33 | C$238 | C$1,727 |
| 75% | 70% | 0.095 | C$48 | C$346 | C$2,516 |
| 60% | 55% | 0.152 | C$77 | C$551 | C$4,003 |
| 49% (today's 1.6 rounds, minus 35%) | 44% | 0.232 | C$118 | C$843 | C$6,127 |

What the rival saves is 99% of the Batatis price.

- **At cost (C$1 marginal):** the rival saves C$1 and loses C$33 to C$6,127. Batatis wins every case by a factor of 30 or more.
- **At loaded cost (C$61):** the rival saves C$60. Batatis wins every bespoke and complex case. On repeat houses at a 90% first-pass rate the rival wins by about C$27, and Batatis wins only once first-pass completeness is below about 68%.
- **At a price:** Batatis wins while its price stays below the extra cost in the table. For bespoke cases that is about C$240 to C$840. For repeat houses it is about C$30 to C$120. The repo's price hypothesis of C$150 to C$750 per package is about at break-even for bespoke cases and too high for repeat houses.

Two limits apply. If "accuracy" means article identification and the applicant or officer catches half of the rival's errors before they cost a round, halve the table. The table also leaves out the cost of a wrong code citation that nobody catches. That is a safety and legal risk, not a rework cost, and we do not price it.

**The honest answer:** the AI is already cents per application, so being 99% cheaper on AI saves almost nothing. What decides the case is the rework avoided, which is worth hundreds to thousands of dollars per bespoke application. The cost that matters is people, and a cheaper rival still needs people to keep its rules current.

## Who pays, and what they might pay

The anchors below come from the repo's market research (`docs/research/2026-10-20-vision/C-market-provinces-business.md`, read 2026-10-20) unless marked. No buyer has seen a Batatis price.

| Anchor | Amount | Kind |
|---|---|---|
| Calgary, Edmonton variance fee | None. Appeal of a refusal C$500 | Published |
| Alberta Safety Codes Authority, alternative solution or variance | C$125/hour, discretionary | Published (Council fee schedule, 2022) |
| Ontario municipal alternative-solution fees, 2026 | Toronto C$2,368.32; Ottawa C$430 to C$1,080; Kingston C$318.25/h, C$2,000 minimum | Published |
| Consultant fee for an alternative solution in Alberta | Not published anywhere we found | Gap |
| UpCodes | US$39 to US$68 per user per month | Published (vendor page, Oct 19) |
| CodeComply.Ai | US$3,000 per seat per year | Published, as reported by Refresh Miami (Jan 2025) |
| Denver AI plan review (Clariti CivCheck) | Up to US$4.6M over 5 years for about 12,000 applications a year, about US$77 per application | Published contract; per-application figure is our arithmetic |
| Archistar AI PreCheck | Sold to cities by demo. Free to applicants in Markham and Burlington | Published (no price) |
| Clariti, Symbium, PermitFlow | Not published | Gap |
| Cloudpermit | About US$6,000 per user per year | Unverified third-party listing |

**Who pays.** Applicants bear nearly all the cost (C$5,600 of the C$5,800 rework on a bespoke case), so the builder or their consultant is the first buyer. Authorities carry only about 2.75 officer full-time equivalents of variance rework in the base case, which is too little to buy a tool for that alone. From Dec 1, 2026, officers must also register every variance with its documents (IB-2026-10-01). That new work is the authority's reason to buy. Manufacturers pay when one product drives many variances.

**Willingness to pay (assumed).** Price below one third of the rework a case avoids, so the buyer keeps two thirds:

- Repeat house filings: a seat for repeat filers, or C$25 to C$50 a package.
- Bespoke cases: C$250 to C$750 a package.
- Complex cases: C$1,500 to C$5,000 a package, still far below the engineer's fee.
- Authorities: a pilot licence under C$75,000, the level at which Calgary requires open competitive procurement.

## Pitch lines

1. "One application costs about forty cents in AI fees at list prices. With hosting it's about a dollar." *(Estimate: published model prices, assumed token counts.)*
2. "The cost that matters is people. Paying someone to keep the rules current is about sixty dollars an application at pilot scale." *(Assumption.)*
3. "One extra round on a bespoke variance costs about thirty-six hundred dollars. Most of that is the builder's interest while the project waits." *(Estimate. Bank of Canada rate published; loan size and spread assumed.)*
4. "Batatis pays for itself if it saves one extra round in sixty bespoke applications." *(Arithmetic on the line above.)*
5. "Officer time is the smaller cost. Variance rework across Alberta is about three officers' worth of hours. The applicants carry the millions." *(Estimate. Edmonton's April 2026 posting: C$44 to C$57 an hour.)*
6. "A rival that's five points less accurate and ninety-nine percent cheaper saves you under a dollar and costs you two hundred to eight hundred dollars in extra rounds on a bespoke file." *(Estimate, competitor table.)*
7. "On repeat house variances the gap is small, so we'd price those low and charge for the hard cases." *(Pricing assumption.)*
8. "Nobody publishes how often Alberta variances go back for more information. We used Surrey's 1.6 resubmissions and Denver's 37% first-pass rate, and the first thing a pilot measures is the real number." *(Published elsewhere; the Alberta figure is a gap.)*

## Sources

Read on 2026-10-28 unless a date is given.

- Anthropic pricing, Claude Haiku 5.5: https://platform.claude.com/docs/en/about-claude/pricing
- OpenAI pricing, GPT-6.1 Sol and GPT-6 Luna: https://developers.openai.com/api/docs/pricing
- Vercel pricing: https://vercel.com/pricing
- Neon pricing: https://neon.com/pricing
- Bank of Canada key interest rates (policy rate raised to 2.5% on Oct 28, 2026): https://www.bankofcanada.ca/core-functions/monetary-policy/key-interest-rates/
- City of Edmonton, Building Safety Codes Officer II posting, Apr 14, 2026 (via job board copy): https://safety.kardow.com/companies/city-of-edmonton/jobs/building-safety-code-officer-ii-480e01d3868e45a6a5691bfb84cca42b
- ALIS, Construction inspectors (NOC 22233), 2023 Alberta Wage and Salary Survey: https://alis.alberta.ca/occinfo/wages-and-salaries-in-alberta/construction-inspectors/22233/
- ACEC Saskatchewan, 2026 Fee Schedule Guideline Summary: https://files.constantcontact.com/9bb518af501/05afdab0-eaaf-4475-99c6-0913c26c358c.pdf
- CCC Engineering design memo, Feb 26, 2026 (Australia, order of magnitude only): https://ccc-engineering-website.pages.dev/design-memos/fire-protection-design-cost/
- Safety Codes Council Data Hub (page re-read today; no quarter after Q1-Q2 2026 is described in the page text): https://www.safetycodes.ab.ca/data-hub/variance-data/
- Safety Codes Council Annual Report 2023, p.32 (read 2026-10-21): https://ebs.safetycodes.ab.ca/documents/webdocs/SR/Annual%20Report%202023.pdf
- Safety Codes Council Annual Report 2025 (read 2026-10-20): https://ebs.safetycodes.ab.ca/documents/webdocs/SR/Annual%20Report%202025%20Final.pdf
- Council fee schedule, ASCA, effective 2022 (read 2026-10-21): https://ebs.safetycodes.ab.ca/documents/webdocs/sr/council%20fee%20schedule%20asca%20v2.pdf
- IB-2026-10-01, Orders and Variances registration: https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf
- Kingston fee summary 2026 (read 2026-10-20): https://www.cityofkingston.ca/media/kwmpr0xh/building-permit-fee-summary-january-1-2026.pdf
- Ottawa fee schedule 2026 (read 2026-10-20): https://documents.ottawa.ca/sites/default/files/bldg_fee_schedule_en_0.pdf
- Surrey AI pre-check, vendor blog with the city baseline (read 2026-10-20): https://www.archistar.ai/blog/city-of-surrey/
- Denver CivCheck contract, Colorado Politics, Mar 9, 2026 (read 2026-10-20): https://www.coloradopolitics.com/2026/03/09/denver-approves-4-6m-ai-powered-permit-review-contract/
- Stateline on Seattle and Honolulu, Aug 21, 2026 (read 2026-10-20): https://www.newstribune.com/news/2026/aug/21/cities-turn-to-ai-to-speed-up-housing-permitting/
- BILD/Altus cost of delay, 2022 (read 2026-10-20): https://www.bildgta.ca/?p=8770
- CodeComply.Ai price, Refresh Miami (read 2026-10-20): https://refreshmiami.com/news/with-2m-in-tow-ai-startup-codecomply-ai-aims-to-accelerate-construction-approvals-and-reshape-compliance-checks/
- CWC and WoodWorks BC, *Alternative Solutions Guide*, pp.4-6: repo copy `reference/text/CWC-Alternative-Solutions-Guide.jsonl`
- Building Codes Challenge scope, p.2 and rubric item 7 (Business Plan, 10%): `/tmp/bcc-scope/scope.txt`
- Repo code read today: `engine/llm_gate.py`, `engine/identify/pipeline.json`, `engine/identify/config.py`, `engine/identify/jev_runtime.py`, `engine/drafting_provider.py`, `engine/drafting_generation.py`, `engine/intake/model.py`, `engine/intake/review.py`, `engine/routes_assist.py`
- Repo documents read today: `docs/business-plan.md`, `docs/judge-qa.md`, `docs/pitch-slides.md`, `docs/pitch-narration.md`, `docs/research/2026-10-20-vision/C-market-provinces-business.md`, `docs/research/2026-10-21-source-checks.md`, `README.md`

The Calgary figure (382 zero-lot-line requests from 26 builders in eight months of 2017) is in the organizers' Building Codes Challenge Data Package (October 2026), in the City of Calgary standing posted variances entry, and in `docs/business-plan.md` §2. The model does not use it.
