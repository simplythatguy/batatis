# Batatis: Business Plan

*Building Codes Challenge, Submission 1 (Oct 29, 2026). Sources are cited inline and were retrieved Oct 20, 2026. Estimates are labelled and show their arithmetic. Prices are hypotheses to test, not results. Features are described as built only where they exist in the current build; everything else is marked as planned or in progress.*

## 1. The company in one paragraph
Batatis helps builders, manufacturers and their consultants prepare a **complete, code-referenced alternative-solution (variance) application** on the Safety Codes Council's *Variance Form for Proposed Alternative Solution*, Part 1, Sections A–D ([SCC form, Oct 6, 2026 version](https://ebs.safetycodes.ab.ca/documents/webdocs/PI/Variance%20Template%20final.pdf)). It is designed to also give Safety Codes Officers (SCOs) an **alternative-solution completeness review** for any incoming package, plus a package for the Council's mandatory registration portal. The officer review and the portal package are in development and not yet built. Batatis checks completeness, never technical correctness. Where engineering judgment is needed, it says who may provide it and what evidence is expected. It doesn't produce that evidence itself.

SCC policy requires its variance form for every variance application ([City of Calgary guide, approved Nov 23, 2023](https://www.calgary.ca/content/dam/www/tools-and-resources/guide-to-applying-for-an-alternative-solution.pdf)). Local processes and add-on requirements still vary by employer of SCOs ([challenge scope](https://edmontonunlimited.com/wp-content/uploads/2026/09/Building-Codes-Challenge-with-Appendix-.pdf)).

## 2. Why us
**Team approach.** We are a small team that built Batatis source-first: every value traces to the form, the code database or the applicant's own documents. That habit of reading the regulator's own data is where the points below came from.

- **Approach: every claim is source-traced.** Code citations must quote the code text word for word or they are dropped. Section C attributions are database lookups, not model output. Section D professional evidence is never invented. The product never states that a design is safe or compliant. These are the build's non-negotiables, written into the repository.
- **We caught the form change.** The SCC replaced its variance form on **Oct 6, 2026** (5 pages, 87 fields). It differs from the Appendix 1 template in the challenge pack: the Section B checkbox wording, the privacy notice (now the *Protection of Privacy Act* s.13(1)(b)) and the Part 2 decision wording all changed. Batatis's export field map is fingerprinted to that exact form file (SHA-256), so a changed form is detected rather than silently filled. The Council paired the new form with mandatory portal registration from Dec 1, 2026 ([SCC IB-2026-10-01](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf)).
- **We know where the volume is.** One Part 9 article, **9.10.15.5.(8)** (roof soffits on houses close to the property line), accounts for **1,501 of the 3,088 building-article entries** in the Council's public variance data ([SCC Variance Data Hub](https://www.safetycodes.ab.ca/data-hub/variance-data/)). Calgary turned the same article into a standing variance after reviewing 382 zero-lot-line alternative solutions between Jan 1 and Sep 1, 2017 ([Calgary advisory](https://www.calgary.ca/content/dam/www/pda/pd/documents/building/variances/advisory-new-standing-posted-variance-procedure.pdf)).
- **We target the officer side of alternative solutions.** None of the 10 code-AI products we reviewed (§7) advertises alternative-solution or variance review for officers.

## 3. The problem, in sourced numbers
- **Building variances registered in Alberta** ([SCC Annual Report 2023, p.31](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/Annual%20Report%202023.pdf)):

  | 2019 | 2020 | 2021 | 2022 | 2023 |
  |---|---|---|---|---|
  | 1,553 | 637 | 1,698 | 1,713 | 837* |

  \*The 2023 count is as of the end of March 2024, and the Council notes that "some 2023 variances have not yet been captured", so it is likely an under-count. In 2019 and 2021–2022 the count ran at about 1,550–1,710 a year. The Council also notes that jurisdiction-wide variances may reduce the number issued. No count has been published for 2024 or 2025 ([AR 2024](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/SCC%202024%20Annual%20Report.pdf), [AR 2025](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/Annual%20Report%202025%20Final.pdf)).
- **Where:** the City of Edmonton accounted for **67% of all variances in the province in 2023 (all disciplines, 909 total)**, Calgary for 9%, and other jurisdictions for 25% (AR 2023, p.31). The report doesn't break the shares out for the building discipline alone.
- **What gets varied** ([Data Hub](https://www.safetycodes.ab.ca/data-hub/variance-data/)). The page says publication begins with variances registered in Q1 and Q2 2026; the dataset is named for Q1 and has no date column, so the period is unconfirmed and we don't annualize it. Each entry is one varied article, not one application.
  - **3,088 building-article entries** (3,118 across all disciplines).
  - **1,846 distinct building variance IDs.**
  - **By variance type, on the all-disciplines base of 3,118 entries:** 1,601 jurisdiction, 1,514 site-specific, and 3 province- or jurisdiction-wide.

  The Data Hub's 1,846 IDs and the annual report's 837 for 2023 use different bases and periods. We don't compare them until the Council confirms the Data Hub's coverage.
- **New mandatory work from Dec 1, 2026.** SCOs must register every variance in the Orders and Variances Portal, individually and per location, *including those relying on jurisdictional alternative solutions*, with the supporting documentation they used. Only SCOs can register, and accredited organizations and SCOs are jointly responsible ([IB-2026-10-01](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf)). Division C §2.3.1 documentation of alternative solutions is mandatory, with a copy of each variance to the Council within 10 days ([SCC IB-2025-11-18](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2025-11-18%20Mandatory%20Documentation%20of%20Variances.pdf)).
- **No system-wide quality measure exists yet.** Until now the Council has not retained or published alternative solutions or supporting material ([Data Hub](https://www.safetycodes.ab.ca/data-hub/variance-data/)).
- **Time:** there is **no published service standard for variance review** from the SCC, Edmonton or Calgary. Variances are decided inside permit review. The nearest proxies are permit averages:
  - Edmonton commercial, mixed-use, industrial and multi-unit building permits: **60-day average against a 120-day target**, Q3 2026 ([Edmonton Q3 2026 report](https://www.edmonton.ca/sites/default/files/public-files/documents/q3-2026-upe-ds-quarterly-report.pdf)).
  - Calgary commercial new buildings and additions: **52–62 days**, Apr–Jun 2026; commercial improvements: 21–31 days ([Calgary](https://www.calgary.ca/development/safety-approval-timelines.html)).

## 4. Buyers, ranked
| Rank | Buyer | Why this rank (public data) | Who bears the cost today |
|---|---|---|---|
| **1** | **Production homebuilders in the Edmonton region** (permit and code-compliance leads) | **The applicant writes the alternative solution.** Division C §2.3.1 documentation is now mandatory (IB-2025-11-18), and the person proposing the solution supplies it. **Site-specific variances, the bespoke tail, are about half the entries** (1,514 of 3,118, all disciplines; Data Hub). The most-varied building articles are Part 9 house provisions (Data Hub), and Edmonton is about 67% of all 2023 variances (AR 2023). The challenge names production homebuilders first ([scope](https://edmontonunlimited.com/wp-content/uploads/2026/09/Building-Codes-Challenge-with-Appendix-.pdf)), and two sponsors (BILD Alberta, Jayman Homes) represent them | **The builder:** staff or consultant time, plus holding cost while an application goes back and forth. Neither Edmonton nor Calgary charges a building-code variance fee (§5) |
| 2 | **Authorities that employ SCOs**, starting with the City of Edmonton | **The new registration work falls on them.** From Dec 1, only SCOs can register, every variance is registered individually per location (including repeated jurisdictional ones), and the authority is jointly responsible for complete, accurate registrations (IB-2026-10-01). Building-relevant accredited bodies: 299 municipalities and 40 agencies (counts cover all disciplines; [AR 2025](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/Annual%20Report%202025%20Final.pdf)) | **The authority:** officer review and registration time, with no building-code variance fee to recover it in Edmonton or Calgary |
| 3 | **Manufacturers, and the designers and code consultants who specify their products** | Calgary routes innovative products through CCMC or recognized evaluators, and otherwise through a project-specific alternative solution in a permit application ([Calgary B23-014, Sep 17, 2026](https://www.calgary.ca/content/dam/www/pda/pd/documents/building/advisories/b23-014-new-products-materials-and-systems-in-building-construction.pdf)). A variance "is not intended for product or equipment approval" (Calgary guide, 2023), so Batatis serves the *assembly or design* application that uses a product | **The manufacturer or design team:** CCMC fees, consultant time |

The **Safety Codes Council / Build Forward Alberta** is a statutory council (accreditation, certification, variance registration) and runs the "front door for innovation" ([SCC, Oct 7, 2026](https://www.safetycodes.ab.ca/a-step-forward-for-alternative-solutions/)). We treat it as a channel and pilot sponsor, not a buyer.

**The tension we've named (and test in §9):** about half the entries are jurisdiction-type repeats. A repeat costs a builder little each time, so per-package pricing only works for the bespoke tail. For repeats, the value moves to the authority, which must still register each one.

## 5. Willingness to pay: public anchors and an untested price range
**What exists today (sourced):**
| Anchor | Amount | Source |
|---|---|---|
| SCC/ASCA fee for an alternative solution or variance (unaccredited areas) | **C$125/hour** | [SCC fee schedule](https://ebs.safetycodes.ab.ca/documents/webdocs/sr/council%20fee%20schedule%20asca%20v2.pdf) |
| Calgary / Edmonton building-code variance fee | **None.** Calgary bills "Additional Plans Review" at C$119/h for non-residential permits; it isn't confirmed to apply to variances. Edmonton's "Variance Request Fee" is a **zoning / development-permit** fee, not a building-code fee | [Calgary 2026](https://www.calgary.ca/content/dam/www/pda/pd/documents/fees/building-and-trade-permit-fee-schedule.pdf), [Edmonton 2026](https://www.edmonton.ca/sites/default/files/public-files/2026-planning-and-development-fee-schedules-consolidated.pdf) |
| Appeal of a refusal | C$500 | [Calgary guide 2023](https://www.calgary.ca/content/dam/www/tools-and-resources/guide-to-applying-for-an-alternative-solution.pdf) |
| Engineering time (proxy; no Alberta rate guide is published since CEA paused publishing its guide) | **C$160–375/hour** (Saskatchewan 2026 recommended minimums) | [ACEC-SK](https://www.acec-sk.ca/wp-content/uploads/2025/12/2026_Schedule_of_Fees_Summary.pdf); [CEA notice](https://cea.ca/advocacy-publications/rate-guide.html) |
| CCMC product evaluation | C$4,000 application; highly innovative products add C$10k–250k+ guide development (initial total C$14,000+), 8–18 months; fee structure changed Sept 1, 2026 | [CCMC PAS-001](https://nrc.canada.ca/en/certifications-evaluations-standards/canadian-construction-materials-centre/ccmc-publications/document.html?id=PAS-001&type=policy) |
| Ontario municipal alternative-solution fees (several cities) | Ottawa Tier I C$1,080 plus third-party evaluation costs, Tier II C$430; Kingston C$318.25/h, C$2,000 minimum | [Ottawa](https://documents.ottawa.ca/sites/default/files/bldg_fee_schedule_en_0.pdf), [Kingston](https://www.cityofkingston.ca/media/kwmpr0xh/building-permit-fee-summary-january-1-2026.pdf) |
| Code-AI seats | UpCodes US$39–59/user/month (annual); CodeComply.Ai US$3,000/seat/year (≈US$250/month); Lawtonica C$30/month (Canadian-dollar anchor) | [UpCodes](https://cms-v2.up.codes/pricing), [Refresh Miami](https://refreshmiami.com/news/with-2m-in-tow-ai-startup-codecomply-ai-aims-to-accelerate-construction-approvals-and-reshape-compliance-checks/), [Lawtonica](https://lawtonica.ca/pricing) |
| Per-check AI plan review | InspectMind: US$1 per drawing sheet with a US$50 minimum tier, plus US$0.25 per sheet per added code | [InspectMind](https://www.inspectmind.ai/pricing) |
| AI review for cities | CivCheck: "free to our City Partners, forever", with a small applicant prescreening fee. But Denver approved up to US$4.6M over 5 years with CivCheck's operator | [civcheck.com](https://civcheck.com/), [Colorado Politics](https://www.coloradopolitics.com/2026/03/09/denver-approves-4-6m-ai-powered-permit-review-contract/) |

**Price range to test (hypotheses, untested; no buyer has seen a price):**
- **Applicant, per bespoke package: C$125–750.** *Arithmetic:* the low end is 1 hour at the SCC's own C$125/h alternative-solution rate. The high end is 2 hours at the top of the C$160–375/h engineering proxy (2 × C$375). The test is whether a builder pays roughly one to two hours of review-equivalent time to arrive complete.
- **Applicant, seat plan for repeat filers: US$39–250 per user per month.** Bounded by UpCodes Essentials (US$39) at the low end and CodeComply.Ai (US$3,000/yr ÷ 12 = US$250) at the high end. Lawtonica's C$30/month shows a cheaper Canadian code-search tier exists.
- **Authority licence: no price stated.** Authority willingness to pay is untested. The program's Venture Pilots stream may fund a pilot of roughly $10k–50k to the team (a quote from the program lead to media, not an official figure, and not an authority budget; [Taproot, Sep 22, 2026](https://edmonton.taproot.news/briefs/2026/09/22/pilot-builds-on-foundation-with-new-challenge-ahead-of-startup-week)). For context, both Edmonton and Calgary apply the New West Partnership Trade Agreement's C$75,000 goods-and-services threshold ([Edmonton](https://www.edmonton.ca/sites/default/files/public-files/Procurement%20Standard.pdf), [Calgary](https://www.calgary.ca/buy-sell/supply-to-city/procurement-policy.html)).

**Facing the "free to cities" norm head-on.** The market norm for municipal AI pre-check is free to the city, with the applicant paying (CivCheck), so our primary model is the same: **the applicant pays, and officers use Batatis free**. Denver shows cities will also pay for review tools at scale, so an authority licence (for example, for the registration package across repeat variances) is a second line, not the base case. Clariti is already inside Calgary with a zoning and document-completeness pilot ([Clariti case study](https://www.claritisoftware.com/resources/case-studies/how-calgary-is-using-ai-to-bring-consistency-to-one-of-canadas-most-complex-zoning-frameworks)), so we position Batatis as the alternative-solution layer an authority adds, not as a replacement for its permit pre-check.

## 6. Cost per application
> **Measured cost and latency per application (unmeasured):** *[slot: median and 90th-percentile cost (C$) and latency (seconds) per case across 20 or more dev cases, with provider, model ids, case count and run date. Shown alongside it: measured cost ÷ C$125 (the low end of the per-package price range) as the share of the floor price that model cost consumes.]*

**How a run is built.** In the current build, code identification runs in four steps:
1. A hosted screening model (Jev, from TypeSafe) scores every Division B article in batches.
2. The top candidates are re-ranked together in one request.
3. An optional verifier (Anthropic Claude in the current build) picks the governing articles with word-for-word quotes.
4. BM25 keyword search is kept as a keyless baseline and fallback.

**In progress** on `backend/identify-api` (draft [PR #12](https://github.com/simplythatguy/batatis/pull/12), not yet merged): a provider switch for the verifier and rerank (`BATATIS_LLM_PROVIDER=openai|anthropic`; the OpenAI verifier defaults to `gpt-4.1`, overridable), with Jev optional. The Oct 29 demo is planned to run on OpenAI, which is the key the team holds, once the switch merges. The production provider will be chosen by the keyed benchmark. Section C attribution and the completeness rules are database lookups and rules, with no model cost.

**Formula** (list prices of the pinned models at run time):

cost per case = Σ over model calls (input tokens × input price + output tokens × output price) ÷ 1,000,000

- **Provider-switched build (draft PR #12):** BM25 first stage (no model cost), then an OpenAI rerank (`gpt-4.1-mini` by default) and an OpenAI verifier (`gpt-4.1` by default), or Anthropic if chosen. Jev is only an optional reranker, and its calls are added only if it is turned on.
- **Keyless fallback** (BM25 plus rules plus deterministic Section C): model cost is zero. The only cost is hosting, at lower identification quality.

## 7. Competitive landscape
| Product | What it does | Price (public) | Alternative-solution / variance prep or review? |
|---|---|---|---|
| **CodesWise** (Canada) | Cited AI search of NBC(AE) 2023, NFC(AE) and national codes; reranker; Canadian hosting | Not read | Not mentioned; says it is "a reference tool" that doesn't replace a code consultant ([codeswise.com](https://www.codeswise.com/), [Alberta page](https://www.codeswise.com/codes/alberta)) |
| **Lawtonica** (Canada) | Code library, AI Q&A, compliance checks; Ontario and Alberta codes | C$30/month | Not mentioned ([features](https://lawtonica.ca/features), [pricing](https://lawtonica.ca/pricing)) |
| **CodeReady** (Toronto) | Drawing/spec compliance pre-check for municipalities and designers | Not published | Not mentioned ([codeready.ai](https://www.codeready.ai/)) |
| **UptoCode** | Drawing/BIM checks against uploaded NBC/provincial codes, cited | Not read | Not mentioned ([Canada page](https://uptocode.ai/plan-review-canada)) |
| **InspectMind** (YC W24) | AI plan check of drawings and specs; lists NBC, Ontario, BC, Alberta | US$1/sheet, US$50 minimum tier | Not mentioned ([Canada page](https://www.inspectmind.ai/locations/canada-plan-check), [pricing](https://www.inspectmind.ai/pricing)) |
| **Clariti CivCheck** | Guided completeness and code checks for permits; **Calgary pilot** (residential zoning and document completeness) | Tiered for cities, or free to cities with an applicant fee | Not mentioned ([product](https://www.claritisoftware.com/products/civcheck-ai-plan-review-software), [Calgary case study](https://www.claritisoftware.com/resources/case-studies/how-calgary-is-using-ai-to-bring-consistency-to-one-of-canadas-most-complex-zoning-frameworks)) |
| **Archistar AI PreCheck** | AI plan review for 30-plus cities | By demo | Not mentioned ([archistar.ai](https://www.archistar.ai/aiprecheck/)) |
| **UpCodes** | US code research and Copilot | US$39–59/user/month (annual) | Not mentioned ([pricing](https://cms-v2.up.codes/pricing)) |
| **CodeComply.Ai** | Design, precheck and plan review against ICC/NFPA/ADA/FHA | US$3,000/seat/year (2025) | Not mentioned ([codecomply.ai](https://codecomply.ai/)) |
| **PermitFlow** | AI agents for US permit expediting | Not published | Not mentioned ([permitflow.com](https://www.permitflow.com/)) |
| Code consultants (e.g. TAIREC, Calgary) | Hand-prepare alternative solutions | Not published | **Yes: the status quo** ([listing](https://linkedin.com/company/tairec-fire-consulting-ltd)) |
| NRC CCMC | Product evaluations along the alternative-solution path | C$4,000 + guide development | Product-level ([PAS-001](https://nrc.canada.ca/en/certifications-evaluations-standards/canadian-construction-materials-centre/ccmc-publications/document.html?id=PAS-001&type=policy)) |
| SSRIA + Build Forward Alberta | Official template and written guide, in development | Free resource (expected) | **Yes, as a document** ([SCC](https://www.safetycodes.ab.ca/a-step-forward-for-alternative-solutions/)) |

**Our claim:** we found no software product that prepares or reviews alternative-solution applications. Every tool above searches codes or checks ordinary permit drawings against prescriptive rules. This is based on public product pages as of Oct 20, 2026, so it is absence of evidence, not proof. **We don't claim** to be the only completeness checker (CivCheck checks completeness for ordinary permits) or the only cited NBC(AE) search (CodesWise does that).

## 8. Defensibility as models improve
A better model makes anyone's code search and drafting better, including ours. It doesn't give a competitor these things:
1. **Officer-side alternative-solution review as a workflow** (in development). It is designed to let an SCO run Batatis on *any* incoming package, including ones not made with Batatis. The officer would get every gap tied to a form section and to Division C §2.3.1, a drafted information request they edit and send themselves, and a registration package for the mandatory portal. Being in the SCO's workflow and earning their trust is earned per authority. It isn't a model capability.
2. **Form-version tracking per jurisdiction** (built for the Oct 6, 2026 form). Forms and registration rules change, and they differ by employer of SCOs. A fingerprinted field map per version catches each change, and each new jurisdiction pack adds to the library.
3. **The Section C attribution layer,** which supports both of the above. Each article maps to its objectives, functional statements and intent statements, and a validator drops any citation that doesn't match the code text. This is specific to alternative solutions. Cited code search alone (CodesWise, Lawtonica) doesn't produce it.
4. **Corrections from pilots** (planned). Officer corrections to alternative-solution reviews would be collected under a data-sharing agreement with each authority, which owns its records.

**Risks:**
- The official SSRIA/SCC template could commoditize the form, so we fill it rather than compete with it.
- An incumbent already in Alberta (Clariti in Calgary) could add an alternative-solution module.
- Code-text use for commercial purposes needs written terms from NRC.

## 9. What we haven't validated yet
- **No buyer has seen a price.** Every price in §5 is a hypothesis built from public anchors, and the authority's willingness to pay has no figure at all.
- **Whether builders pay per package** when about half of variance entries are jurisdiction-type repeats (§4 tension).
- **Measured cost and latency per case** are pending the benchmark runs (§6 slot).
- **The officer review and portal package are not built yet,** and no officer has used Batatis. Time saved for an SCO is a target, not a result (see the Implementation Plan's testing protocol).
- **No pilot partner has agreed.** We have not contacted anyone; this is a hackathon prototype.
- **The Data Hub's period and bases** are unconfirmed (§3).
- **Consultant preparation fees in Alberta** are not public; we use proxies.
