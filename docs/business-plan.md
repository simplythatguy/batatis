# Batatis: Business Plan

*Building Codes Challenge, Submission 1 (Oct 29, 2026). Status is as of Oct 22, 2026. Every figure carries its kind. **Verified** means a primary source says it and the source is named. **Measured** means a run or a file produced it. **Estimate** means arithmetic on figures shown. **Assumption** means a number we chose, with its basis. Prices are hypotheses, and no buyer has seen one. Figures that no other research file holds are recorded in [`docs/research/2026-10-21-source-checks.md`](./research/2026-10-21-source-checks.md) ("source checks"). The market research is `docs/research/2026-10-20-vision/C-market-provinces-business.md`, and later mentions use its file name alone. What is built is defined in the Implementation Plan, §3.*

## 1. The company in one paragraph

Batatis helps builders, manufacturers and their consultants prepare a complete, code-referenced alternative-solution application on the Safety Codes Council's *Variance Form for Proposed Alternative Solution* (Part 1, Sections A to D, [form dated Oct 6, 2026](https://ebs.safetycodes.ab.ca/documents/webdocs/PI/Variance%20Template%20final.pdf)). It also helps safety codes officers (SCOs) see what an incoming application still lacks. It checks administrative completeness and never technical correctness. When an engineer's judgment is needed, it says so, lists what the evidence must address, and stops.

Live today at <https://batatis-vert.vercel.app>: sign-up for applicants and officers, a one-question-at-a-time flow for Sections A to D, Section C looked up from the code's tables, the Council's October 2026 form as a draft PDF, or as the app's "Official PDF" once no required item is missing (the Council's own form filled in, which the Council does not issue or approve), submission to Calgary or Edmonton, and an officer queue with claim, accept-as-complete and return-with-message. The intake reader and the code check over all 2,080 Division B articles are on screen in the same flow. The officer package review is merged as a backend, and its screens are in progress. Coded rules for the most-varied articles are merged as a backend, with no screen and no domain reviewer. The accuracy report page, a second province and any portal integration are roadmap.

Two terms are kept apart throughout. A *variance* is the officer's legal authorization under the Safety Codes Act, s.38. An *alternative solution* is the applicant's technical evidence, under NBC(AE) Division C, 2.3.1, that the design performs at least as well as the acceptable solution. An accepted variance needs both (Implementation Plan, §2.1). Batatis helps with both halves and decides neither.

Intake still differs by authority. Calgary asks for its own Request for Specific Variance form in addition to the Council's form, and Edmonton uses the Council's form (`engine/data/jurisdictions/packs/`).

## 2. Why us

- **Source-first by rule.** The repository's non-negotiables (`AGENTS.md`) say that an article number is never fabricated, that Section C is a deterministic lookup, that Section D professional evidence is never authored, and that the product never says a design complies or is safe. The code identification pipeline enforces the first with a quote check: a citation that does not quote the code word for word is dropped.
- **We caught the form change.** The Council replaced its variance form on Oct 6, 2026 and paired it with mandatory portal registration from Dec 1, 2026 ([IB-2026-10-01](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf)). The export is pinned to the form's SHA-256, so a changed form is detected instead of silently filled. The challenge brief's Appendix 1 differs from the new form in six places (Implementation Plan, §4.3).
- **We know where the volume is.** The Council's Data Hub report for Q1 and Q2 2026 counts 3,088 building-article entries. One Part 9 article, 9.10.15.5.(8), has 1,501 of them (49%). The three most-varied articles, 9.10.15.5.(8), 9.10.11.2. and 9.10.13.13., have 2,118 (69%, our arithmetic on the report's figures). Calgary reviewed and accepted 382 zero-lot-line alternative-solution requests between Jan 1 and Sep 1, 2017, and then created standing posted variances. Coded rules for these articles exist as a backend with no screen, and no domain reviewer has signed them.
- **We target the officer side.** No product in the competitor survey (`docs/research/2026-10-20-vision/C-market-provinces-business.md`, §1.2) prepares or reviews alternative-solution applications. That is an absence found by web search on Oct 20, 2026, not proof.

## 3. The problem, in sourced numbers

**Building variances registered in Alberta** ([Council Annual Report 2023](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/Annual%20Report%202023.pdf), printed page 32; source checks §1). Verified.

| 2019 | 2020 | 2021 | 2022 | 2023 |
|---:|---:|---:|---:|---:|
| 1,553 | 637 | 1,698 | 1,713 | 837 |

The 2023 count was taken at the end of March 2024, and the Council says "some 2023 variances have not yet been captured", so it is probably low. The Council also notes that a single jurisdiction-wide variance can replace many. The 2023 report gives 909 variances across all disciplines, and the City of Edmonton accounted for 67% of them, the City of Calgary 9% and other jurisdictions 25% (shares as published, rounded). The report does not split those shares by discipline.

**What gets varied** (Council Data Hub, report *Variances Registered Q1-Q2 2026*, read Oct 20, 2026; `C-market-provinces-business.md`, §2.0). Verified. The Data Hub counts varied articles, not applications.

| Discipline | Article entries, Q1 to Q2 2026 |
|---|---:|
| Building | 3,088 |
| Plumbing | 22 |
| Electrical | 3 |
| Pressure equipment | 3 |
| Fire | 1 |
| Gas | 1 |

The five most-varied building articles are 9.10.15.5.(8) with 1,501, 9.10.11.2. with 366, 9.10.13.13. with 251, 9.10.14.2. with 218 and 9.10.14.5. with 167. All five sit in Section 9.10 (fire protection) of Part 9. The research doubles the half-year to about 6,200 entries a year, and that assumes the half-year is typical (estimate).

**Nobody measures quality.** The Council says it is not collecting or retaining supporting materials or alternative solutions, so no public figure shows how often applications are returned. The Council's 2025 annual report records 9 notices of appeal and none on a variance refusal. We read that as a sign that the friction sits upstream, in the back-and-forth with the officer, but it is an inference (`C-market-provinces-business.md`, §2.0).

**Scale of the system.** 433 accredited organizations (299 municipalities, 93 corporations, 40 agencies and 1 regional services commission), 2,317 certified SCOs in all disciplines, and for the building discipline 520 certifications and 438 designations of powers (Council Annual Report 2025, p.7 and p.10; `C-market-provinces-business.md`, §2.0). Verified.

**Time and cost of delay.**

- The organizers describe the cost of rework and delay as "a few hundred dollars to tens of thousands of dollars", and call the evidence anecdotal (Challenge Scope, p.2). It is a framing, not a survey.
- A practitioner guide on alternative solutions advises allowing "one to two months" for correspondence and "two to four months to receive comments" (CWC and WoodWorks BC *Alternative Solutions Guide*, pp.4 to 6; `C-market-provinces-business.md`, §2.4). It is guidance, not a measurement.
- **Estimate.** A month of carrying cost on one house waiting for a variance decision is about C$2,333, if C$400,000 of land and construction financing is outstanding at 7% (C$400,000 x 0.07 / 12). Both inputs are our assumptions. A two-month back-and-forth is then about C$4,700.
- No service standard for variance review has been published by the Council, Edmonton or Calgary (`C-market-provinces-business.md`, §2.4).

**New mandatory work from Dec 1, 2026** ([IB-2026-10-01](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf), [IB-2025-11-18](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2025-11-18%20Mandatory%20Documentation%20of%20Variances.pdf)). Verified. SCOs must register every variance individually, for a specific location, in the Orders and Variances Portal, with the documentation they used. Only SCOs can register, and accredited organizations and SCOs are jointly responsible for complete and accurate registrations. Variances must be registered at the time of issuance or as soon as reasonably practicable thereafter, and the legacy email method ends. Before Dec 1, IB-2025-11-18 asks for a copy of each variance within 10 days of issuance. It also requires alternative solutions to be documented under Division C, 2.3.1.

## 4. Buyers, ranked

| Rank | Buyer | Why this rank | Who bears the cost today |
|---|---|---|---|
| 1 | **Production homebuilders, and the consultants who prepare their files**, starting in the Edmonton and Calgary regions | The applicant writes the alternative solution and its Division C documentation, now mandatory. The most-varied building articles are Part 9 house provisions. Edmonton had 67% of 2023 variances in all disciplines. The Challenge Scope lists production homebuilders first among its target customers | The builder, in staff or consultant time and carrying cost. Calgary and Edmonton charge no variance fee (`C-market-provinces-business.md`, §2.4). The Council's schedule for areas served by the Alberta Safety Codes Authority lists a discretionary charge of C$125 per hour for an alternative solution or variance (source checks §1) |
| 2 | **Authorities that employ SCOs**, starting with Edmonton and Calgary | From Dec 1 the registration work falls on them: individual registration per location, supporting documentation included, joint responsibility. 433 accredited organizations exist | The authority, in officer and registration time, with no variance fee to recover it |
| 3 | **Manufacturers, and the designers who specify their products** | A product can reach acceptance through an evaluation report from the Canadian Construction Materials Centre (CCMC) or another recognized body (Division A, 1.2.2.1.(2)), and a project-specific alternative solution covers the project that uses it. The research expects product-level demand to be codified away over time (finding 8 in `C-market-provinces-business.md`), so this segment is third | The manufacturer or design team |

The **Safety Codes Council and Build Forward Alberta** run the Council's "front door for innovation" and are developing an official template and guide with SSRIA (announced Oct 7, 2026, no date or price given). We treat the Council as a channel, a pilot sponsor and the main competitive risk, not as a buyer.

**The tension we have named.** Some variances are repeats. Calgary's standing posted variances replace one-off requests with a posted package, and the Data Hub does not show variance type. The research assumes that only 5% to 15% of entries are bespoke (assumption, `C-market-provinces-business.md`, §2.5). Per-package pricing therefore works for the bespoke tail. For repeats, the value moves to the authority, which must still register each variance. The sizing in §7 shows what each case is worth.

## 5. Willingness to pay

### 5.1 What exists today

| Anchor | Amount | Kind and source |
|---|---|---|
| Council fee for an alternative solution or variance in areas served by the Alberta Safety Codes Authority | C$125 per hour, a "discretionary charge by issuing Agency" (schedule effective Jan 1, 2022) | Verified, source checks §1 |
| Calgary, Edmonton | No variance fee. Appeal of a refusal costs C$500 | Verified, `C-market-provinces-business.md`, §2.4 |
| Ontario municipal alternative-solution fees, 2026 | Toronto C$2,368.32. Ottawa Tier I C$1,080 plus third-party evaluation costs, Tier II C$430. Kingston C$318.25 per hour, minimum C$2,000 | Verified, §2.4 and §5.1 |
| Consultant fees to prepare an alternative solution in Alberta | Not published | Verified negative. We assume C$3,000 to C$15,000 per bespoke package of consultant, designer and internal time (assumption, §2.5) |
| AI code-check seats | UpCodes US$39 to US$68 per user per month. CodeComply.Ai US$3,000 per seat per year | Verified as reported, §1.2 and §5.1 |
| AI plan review sold to authorities | Denver: up to US$4.6M over five years for about 12,000 applications a year, about US$77 per application per year | Verified as reported, with our ratio (estimate), §1.4 |
| Free pre-check for applicants | Markham and Burlington give applicants an AI pre-check at no charge. The municipality or vendor pays | Verified, §1.3. It limits what a pure applicant-side pre-check can charge in Ontario |
| Cost of delay | About C$2,333 per month of carrying cost on one house | Estimate, §3 above |

### 5.2 Price hypotheses to test (assumptions, untested)

| Who | Hypothesis | Basis |
|---|---|---|
| Applicant, per completed package | C$150 to C$750 | Low end: the research's per-package assumption (`C-market-provinces-business.md`, §5.4, model 2). High end: about one third of one month's estimated carrying cost for a house (C$2,333). The Council's own rate is C$125 per hour, so the low end is about one hour of that time |
| Applicant, seat for repeat filers | About C$2,400 per user per year | The research's assumption, set between UpCodes Professional (US$59 per month, US$708 per year) and CodeComply.Ai (US$3,000 per seat per year) |
| Authority | No price. Pilots sized under C$75,000 | Calgary requires open competitive procurement at C$75,000 or more for goods and services (Calgary procurement policy; `C-market-provinces-business.md`, §5.2). The program guide names a possible paid pilot through Venture Pilots but gives no amount |

**Who pays.** The applicant pays, and the officer's tier is free in Alberta. Calgary and Edmonton charge no variance fee, so they have no fee income that a tool could be paid from. The market evidence points the same way: where authorities buy AI review, the buyer is a city with a budget line (Denver), and Canadian pre-checks are free to the applicant (Markham, Burlington). An authority licence is a second line and not the base case.

**Arithmetic on what per-package fees can support in Alberta alone (estimate).** With 310 to 930 bespoke packages a year (5% to 15% of about 6,200 entries) and a price of C$150 to C$750, the ceiling is C$46,500 to C$697,500 a year if every bespoke package paid. That is a small business. Seat and authority revenue, and other provinces, are what make this a company (§7).

## 6. Cost per application

The model cost of one application is small, and it is an estimate. The token use per call comes from the code's caps and the usage assumptions in the [cost model](research/2026-10-28-bakeoff/cost-model.md); no application has run with metering on. Prices are US$ per million tokens at list, from `engine/llm_gate.py`: Claude Sonnet 5.5 at US$2 in and US$10 out, Claude Haiku 5.5 at US$0.10 and US$0.50. Canadian dollars use the Bank of Canada rate of 1.4057 CAD per USD on Oct 21, 2026. This section replaces the Oct 21 figures, which priced a pipeline that screened all 2,080 articles with a paid model.

| Step, with assumed use per application | Model | Base cost (US$) | Kind |
|---|---|---:|---|
| Reading the description, two reads | Claude Sonnet 5.5 | 0.08 | Estimate |
| Document review, one run | Claude Sonnet 5.5 | 0.22 | Estimate |
| Drafting the statements, one run | Claude Sonnet 5.5 | 0.14 | Estimate |
| Independent audit of the drafts, one run | Claude Sonnet 5.5 | 0.11 | Estimate |
| Finding and ranking code articles, two searches (table of contents, then the leading 72) | Claude Haiku 5.5 | 0.016 | Estimate |
| Assistant, five answers | Claude Haiku 5.5 | 0.006 | Estimate |
| Section C lookup, completeness checks, officer package review, form export | None | 0 | By construction |
| **One application** | | **about 0.57** (C$0.80) | Estimate |

**What else it costs.** Hosting adds about C$0.62 an application at pilot volume. Half a person for jurisdiction packs, support and domain review adds about C$60, for a loaded cost of about C$61. If every step ran on Claude Haiku 5.5, the model cost would be about US$0.05. Even the base case is about 0.5% of the low end of the price hypothesis (C$150).

**What this means.** Model cost does not decide whether Batatis is a business. Upkeep of jurisdiction packs, domain review, support, officer onboarding and Canadian-region hosting do. One extra "more information" round on a custom application costs about C$3,600, mostly the builder's cost of waiting, so Batatis pays for itself if it saves one such round in every 60 custom applications. The cost model also prices a rival that is 99% cheaper and 5 points less accurate: it saves a builder under C$1 on a custom application and adds about C$240 to C$840 of expected rework.

**Spend controls (built).** Each model call reserves its worst-case cost first and settles with the reported tokens afterward. A daily cap (default US$5) is kept in a shared database ledger. Per-IP limits apply, and when the gate is shut the code search keeps its deterministic order (`docs/deploy.md`, `engine/llm_gate.py`). These are estimates until applications run with metering on.

## 7. How big, and how it grows

All figures here are estimates from `C-market-provinces-business.md` (§2.5 and §5.4) and `docs/research/2026-10-20-vision/README.md` (§8). The assumptions are in those files and are summarized in the table.

| Pool | Size | Main assumptions |
|---|---|---|
| Alberta bespoke-preparation work | C$0.9M to C$14M a year before capture. C$0.3M to C$7M at a 30% to 50% capture | About 6,200 entries a year. 5% to 15% bespoke. C$3,000 to C$15,000 of time per package |
| Alberta templated paperwork | C$0.19M to C$1.4M a year of labour | 5,000 to 5,900 entries, 0.5 to 2 hours each, C$75 to C$120 an hour |
| Canadian authority-side pre-check | US$23M to US$50M a year if every application were covered. US$7M to US$15M at 30% | 300,000 to 650,000 applications a year at Denver's US$77 per application |
| Canadian seats | About C$42M a year | 25% of 25,700 inspectors at C$3,000, plus 10% of 330,639 engineers at C$700 |

The honest reading is the research's: **the Alberta pool is C$0.9M to C$14M a year before capture, and what Batatis could capture of it, C$0.3M to C$7M a year, is at most a single-digit-million-dollar business.** A very large outcome would need other provinces, then all permits, then other countries. The research's own arithmetic says US$100M of annual revenue takes about 875 authorities, or about 12,000 Canadian seats plus international revenue, over 8 to 10 years on a top-decile growth curve. We treat that as an outer bound, not a plan.

**How it grows, in stages.**

| Stage | Product | Who pays | Proof point |
|---|---|---|---|
| 1. Alberta wedge | Variance preparation for the most-varied articles, a bespoke-case workspace, a free officer view | Production builders and consultants. 3 to 5 authority pilots under C$75,000 | Cycle time and first-pass acceptance on real files |
| 2. Canada | Completeness pre-flight for more permit types. Packs for Saskatchewan, Manitoba, British Columbia and Ontario | Applicant subscriptions and authority licences | Review minutes saved on real files. Licensed code text |
| 3. Other countries | Performance-based markets such as England, Australia and New Zealand | The same two sides | A second-country pack shipped |

A reviewed province pack takes roughly 3 to 6 months with one jurisdiction expert, if code-text licences allow (estimate, `docs/research/2026-10-20-vision/README.md`, §7). The Alberta packs are data (`docs/api/jurisdictions.md`), and every other province is a labelled "preview" and nothing more.

## 8. Competitive landscape

From `C-market-provinces-business.md`, §1 (read Oct 20, 2026). Prices are as reported there.

| Company | What it does | Public price | Prepares or reviews alternative-solution applications? |
|---|---|---|---|
| UpCodes | Code search and an assistant, US codes | US$39 per user per month (annual) to US$59 | Not addressed |
| CodeComply.Ai | AI plan review for building departments and architects, US codes | US$3,000 per seat per year | Not mentioned on its site |
| Archistar | AI pre-check for cities. Customers include Surrey, Burlington, Ottawa, Kingston and Markham | By demo | Not stated. Checks are rule-based zoning, Part 9 and completeness |
| Clariti, including CivCheck | Permit platform with AI plan review. Toronto pilot. Denver contract up to US$4.6M | Not published | Not stated |
| GreenLite | Third-party plan review using AI | Not published | Not stated |
| PermitFlow | Permit expediting software for builders | Subscription, amounts not disclosed | No |
| Cloudpermit | Permitting platform for local governments. The seller claims about 850 municipalities | Not published | Not stated |
| Trax Codes | AI codes platform for Canada | Not published | Not stated |
| Code consultants | Prepare alternative solutions by hand | Not published | **Yes. This is the status quo** |
| Council template and guide (SSRIA, Build Forward Alberta) | An official alternative-solution template and written guide in development | No date or price announced | **Yes, as a document** |

**What we claim.** We found no software product that prepares or reviews alternative-solution applications. That rests on web search and vendor pages on Oct 20, 2026, so it is absence of evidence. **What we do not claim.** We are not the only completeness checker (CivCheck checks completeness for ordinary permits) and not the only code search. At least six Canadian municipalities launched AI pre-check tools between March and September 2026, and all of them cover zoning, completeness and Part 9, so well-funded vendors already hold the relationships (`C-market-provinces-business.md`, §1.1).

## 9. Defensibility as models improve

A better model makes anyone's code search and drafting better, including ours. It also lowers our screen cost. It does not supply the following.

1. **Jurisdiction packs, kept current.** A pack holds an office's process, forms, standing packages and notices with sources, as data. The research argues that the jurisdiction pack, not the model, should be the product. A pack has to be researched from the office's own documents and kept current when the office changes its forms.
2. **A place in the officer's workflow.** The officer queue is built, and the package review and the drafted information request are merged as a backend. Trust in the officer's workflow is earned per authority and is not a model feature.
3. **An exact core.** The code database, the Section C tables and the validators make citations checkable. A model that writes fluent text does not make it checkable. Models sit behind pinned versions, and the benchmark harness in draft PR #58 is meant to let us swap one for another and compare them on the same cases.
4. **Form-version tracking.** The Council changed the form on Oct 6, 2026. A pinned field map detects each change.
5. **Corrections from pilots (roadmap).** Officer corrections to reviews could be collected under a data agreement with each authority, which owns its records.

**Risks.**

- An official template could commoditize the form. We fill the Council's form, and we would add the new template as a form version.
- An incumbent could add an alternative-solution module. Archistar and Clariti already hold Canadian municipal relationships.
- **Code-text licensing.** NBC(AE) 2023 says commercial reproduction of National Research Council (NRC) material needs written consent. The research ranks this the highest-priority risk. The app shows code text in full, with its citation, PDF page and a credit and link to the NRC publication, and the code library lets a user read any article. We have not asked NRC for terms, and written terms are needed before a public commercial launch. If terms are refused, the fallback is a link-out and user-supplied-text design (`C-market-provinces-business.md`, §3.2 and (c)).
- **Reviewer adoption is not assured.** A staff survey of more than 150 employees in Honolulu gave "almost universally negative feedback" on an AI plan-review pilot, as reported by Stateline (`C-market-provinces-business.md`, §1.2, verified as reported).

## 10. The first 18 months, and what must be true

This is a plan, not a commitment from anyone.

1. Ask NRC for written terms before a public launch, and offer Build Forward Alberta an integration or pilot.
2. Sign 3 to 5 Alberta authorities under C$75,000 a year each, and 2 to 3 production builders.
3. Apply to Innovative Solutions Canada for non-dilutive funding. Its Challenge Stream funds Phase 1 proofs of feasibility of up to C$150,000, but the page we read lists no open housing or permitting challenge (`C-market-provinces-business.md`, §5.2).
4. Prepare a privacy impact assessment pack and the notice that Alberta's Protection of Privacy Act expects when personal information is used in an automated system.

**What must be true, from the research.**

- NRC grants workable written terms within about six months. Otherwise we switch to the link-out design.
- Council or municipal data show at least 300 bespoke variances a year in Alberta. Otherwise we pivot to a standing-variance workflow and all-permit completeness.
- One municipality signs a paid contract above C$50,000 within 12 months.
- If the Council's template ships first, we integrate it and do not compete with it.

## 11. What we have not validated

- **No buyer has seen a price.** Every price in §5.2 is a hypothesis. The authority side has no price at all.
- **Whether builders pay per package.** Some variances are repeats, and the share that is bespoke is unknown. The Council does not collect it.
- **Cost covers model calls only.** Hosting, support, pack upkeep and Canadian-region hosting are not priced. Usage numbers for the assistant are illustrative.
- **Code identification accuracy on the final pipeline is not measured.** The benchmark is unfinished (draft PR #58) and the commit rule is uncalibrated, so nothing is committed automatically.
- **No pilot partner has agreed to anything,** and no officer has used Batatis. Time saved for an officer is a target, not a result.
- **Market sizes are estimates** with the assumptions shown. They rest on a half-year of Data Hub counts and on consultant fees that nobody publishes.
- **The competitor claim is absence of evidence.**
