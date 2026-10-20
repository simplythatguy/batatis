# Batatis: product vision, tools and accuracy plan

Date: 2026-10-20. Status: research-backed proposal. Labels: **measured** (run by us today), **verified** (primary source read), **estimate** (arithmetic or judgement, assumptions shown). Code citations are NBC(AE) 2023, 2nd printing only; NBC 2025 appears only as the next national model edition, not adopted in Alberta.

Supporting files in this folder:

- [Models, Jev and S1MB](A-models-jev-s1mb.md): Jev facts and pricing, S1MB open models, frontier model prices and drawing benchmarks, accuracy-guarantee techniques.
- [Drawings to interactive plan](B-drawings-interactive-acc.md): file formats, floor-plan recognition, automated compliance checking, editor stack, 25 computable NBC(AE) 2023 checks, pipeline.
- [Market, provinces, business](C-market-provinces-business.md): competitors, Alberta variance data, market size, province table, licensing, revenue models.
- [Jev benchmark](jev-benchmark/README.md): our measured code-identification test, scripts and raw judgments.
- [Concept page](concept.html): interactive mock of the main screen, pipeline and evidence charts.
- [Drawing probe](D-drawing-probe.md): what 11 real Alberta applicant plan sets contain, and how to read them without generating numbers.
- [Build plan to 29 October](2-week-build.md): what we build by the 29 October 2026 deadline, what waits for later, accuracy targets and the day-by-day schedule. It narrows the build, not this vision.

---

## 1. The idea

**Batatis turns the drawings people already have into a living, code-aware model of the building, and assembles the compliance proof automatically.**

Drop anything: a PDF permit set, CAD, IFC, a scan, a phone photo. Type almost nothing. Batatis builds a *Plan Twin*: an interactive 2D plan overlaid on the original sheets, where every room, wall, window, door and stair carries its measured values, where each value came from, and the requirements that apply to it. It runs the check a Safety Codes Officer would run, before the officer sees it. For every problem it offers the cheapest way out: a design fix, another route inside the same article, a standing alternative the jurisdiction already accepts, or a full alternative-solution (variance) case with Section C filled by exact lookup and the evidence still needed spelled out. The officer receives the same case as a structured, source-linked proof they can verify in minutes.

The design principle is **"never confidently wrong"**: everything that can be exact is deterministic software (code text, citations, attributions, editions, geometry, arithmetic, forms); models are used where they were measured to help, with every uncertainty shown as a question or a flag instead of a guess; people sign what the law says people sign.

The thesis for judges and investors: building codes are objective-based in law (alternative solutions are allowed) but prescriptive in practice, because proving equivalent performance is slow and expensive. Make the proof cheap and you speed up housing and let innovation (modular, mass timber, new materials) into construction.

## 2. Why this wins

1. **The problem is concentrated and machine-readable (verified, rendered from the Safety Codes Council's public report, 2026-10-20).** Alberta's registered variances in Q1–Q2 2026 cite 3,088 building-code article entries. Five Part 9 fire-protection articles account for 81% of those entries:

   | Div B article | Topic | Entries | Share | Existing standing alternative |
   |---|---|---|---|---|
   | 9.10.15.5.(8) | projecting roof soffits where limiting distance ≤ 0.45 m | 1,501 | 48.6% | Calgary SPV-001 Zero Lot Line (Rev 5, 2026-03-05) |
   | 9.10.11.2. | firewalls not required (party walls) | 366 | 11.9% | Calgary SPV-006 (2025-06-19) |
   | 9.10.13.13. | fire dampers | 251 | 8.1% | Calgary SPV-006 |
   | 9.10.14.2. | area and location of exposing building face | 218 | 7.1% | Calgary SPV-003 (2025-02-12) |
   | 9.10.14.5. | construction of exposing building face | 167 | 5.4% | Calgary SPV-003; STANDATA 23-BCV-018 (soffit protection) |

   All five turn on things drawings show (limiting distance, exposing faces, soffits, party walls, ducts crossing rated assemblies). Most of the volume is "detect the need, choose the right accepted package, prove every condition, document it": work software can do from drawings.

2. **Nobody does alternative solutions.** Every AI plan-review product found (Archistar, Clariti/CivCheck, CodeComply.Ai, UpCodes, Symbium, PermitFlow, GreenLite) checks prescriptive rules, zoning or completeness. Canada's 2026 municipal AI pre-check wave (Surrey, Burlington, Ottawa, Kingston, Toronto, Markham, Cambridge) is prescriptive, low-rise, and outside Alberta. Edmonton automates zoning only; no Calgary pilot was found.
3. **The national regulator has written the spec.** NRC's Innovative Solutions Canada challenge (July–August 2026), "Deterministic AI-assisted compliance checking for building permit applications", asks for PDF/CAD/IFC input, Parts 3 and 9, deterministic rules plus human-in-the-loop, four outcomes (Meets / Does not meet / Information not available / Uncertain) and at least 90% accuracy on simple rules. That is this architecture.
4. **The economics are lopsided (measured).** Screening every one of the 2,080 Division B articles against a project costs about $0.016 and 1.6 seconds; total model cost for a 20-sheet case is about $1–4 (estimate). One month of carrying cost on a house waiting for a variance is about C$2,300 (estimate).

## 3. The experience

1. **Drop.** One drop zone. Pages are sorted (floor plan, elevation, section, site plan, schedule, spec sheet, test report, photo); the title block is read; the address resolves to the authority, code edition and local process ("Calgary, AB · NBC(AE) 2023, 2nd printing · City of Calgary process").
2. **See.** The Plan Twin appears over the original sheet. Rooms have uses and areas; walls have types and ratings; windows have clear openings; exits have paths. Every value says where it came from (sheet and region) and whether it was read, computed, confirmed by you, or unknown.
3. **Flags, the way a reviewer would raise them.** Pins in the four NRC states. Clicking one shows the exact code text with its citation, the measured value and its source, and the ways out.
4. **What-if, live.** Widen a window and the egress flag clears; change a wall type and separation flags update; move the house on its lot and limiting-distance, exposing-face and soffit checks re-run.
5. **Variance in about a minute.** Sections A and B from the title block and plan; Section C by deterministic lookup (objectives, functional statements; intent shown separately as "NBC 2020 Intent Statements, explanatory only"); Section D as an evidence plan ordered by the confidence ladder with professional-involvement triggers; risk assessment, mitigating measures and assumptions drafted for the applicant to confirm. When a standing package applies, its conditions become a checklist that must be satisfied.
6. **Pre-flight.** The completeness gate the officer would apply. Export stays disabled while anything blocking remains, and says why.
7. **The officer's view.** Claims linked to evidence and code text, machine-verified citations, AI-written text marked, standing-package conditions ticked or open, a diff since last submission, a drafted information request.
8. **Anywhere in Canada.** Change the address: authority, code, process and forms change; coverage is labelled honestly (full, code-only, preview); flags are recomputed against that code.

The [concept page](concept.html) is a working mock of steps 2–6 on a synthetic Calgary rowhouse with secondary suites; its code quotes and Section C rows are real lookups (for example Sentence 9.10.11.2.(2) → [F03-OS1.2] and [F03-OP3.1], Table 9.38.1.1. [PDF p.1128]).

## 4. How it stays trustworthy

"100% accuracy" is achievable for the parts that are exact by construction. For the parts that need judgement, the honest and strongest promise is: *every item the system answers on its own is covered by a measured error bound; every item it is unsure about goes to a person; an audit sample watches for drift.*

| Layer | Job | Why it can be trusted |
|---|---|---|
| Exact core | Code text, citations, Section C attributions, edition and jurisdiction rules, arithmetic, geometry, forms | Deterministic software over a versioned code database (13,743 provisions of NBC(AE) 2023, 2nd printing, already built); the citation validator rejects any article, page or attribution that does not exist |
| Deterministic scope | Part 3 vs Part 9, division, edition, building class | Computed from confirmed facts before any model runs |
| Exhaustive screen | A decision model judges every provision in scope | Removes the retrieval ceiling: 96.5% of governing articles kept while passing 15% of the code (measured) |
| Comparative rerank | The shortlist judged side by side in one request | Top-1 doubles over keyword search (measured 32% → 66%) |
| Rules for multi-step logic | Counts, thresholds, conditions computed in code and stated explicitly | Measured: stating "more than 2 houses with a secondary suite; party walls are not firewalls" moved that issue from #84 to #30 for the decision model; a coded rule makes it certain |
| Frontier verifier | Reads the shortlist in full, must quote; quotes matched word for word; claims checked as supports / contradicts / says nothing | Fabricated quotes are caught by string matching, not by the model's opinion of itself |
| Two readings of every drawing value | Vector geometry vs schedule text, or parser vs vision model; agreement auto-accepts, disagreement becomes a one-click confirmation on the sheet | Vision models are good readers of text (up to 0.95) and poor counters of symbols (0.16–0.39 door counting), so geometry never comes from a vision model alone |
| Calibrated abstention | Thresholds set on labelled cases with a stated error budget | To claim ≤1% error at 95% confidence with no observed errors needs about 299 labelled auto-accepted items per stratum (jurisdiction, document type) |
| People decide | Professionals sign engineering judgements; the officer decides acceptance | The product prepares and checks; it never says a design is safe or compliant |

## 5. Tools: what each does, how good, what it costs

| Job | Choice | Evidence | Cost (estimate unless measured) |
|---|---|---|---|
| Sort pages | Title-block text rules, then a decision model with images (Jev 1.14 leads S1MB vision at 0.746; vllm-sr/d3-flash for Canadian hosting) | S1MB vision board; document-type tasks 0.68–0.73 for decision models, so measure per class | ≈ $0.0002 per sheet |
| Plan geometry | Vector PDF paths and text (PyMuPDF to prototype; pdfium/pdf.js/pikepdf or an Artifex licence before shipping, because PyMuPDF is AGPL); DXF via ezdxf; DWG via ODA (File Converter, or SDK at $7,500 then $4,500 a year); IFC via IfcOpenShell / web-ifc; RVT via Autodesk APS | Alberta and Ontario authorities require vector PDFs for permit drawings; layers are often flattened, so walls are inferred geometrically | Cents per sheet; ≤ $3 per RVT translation |
| Raster and photos | Deskew, OCR, an MIT/Apache floor-plan model (RoomFormer, Raster2Seq) trained on licensed data, SAM 2 for click-assist; mandatory scale confirmation | Best raster model: corner F1 59.4, door/window F1 77.8; so raster gives an assisted draft, not facts | < $0.03 per page |
| Text on drawings | Native PDF text or OCR, then a cheap vision model (Gemini 3.8 Flash or GPT-6-Luna) returning a source span per field, then a decision-model "is this field wrong?" check | Text reading is the strongest vision-model skill | ≈ $0.007 per sheet |
| Second reading on disputes | A different vendor (Gemini 4 Argon, Claude Sonnet 5.5 or Opus 5.5) only where two readings disagree | Errors correlate across models (they agree 60% of the time when both are wrong); use different lineages and different evidence | $0.05–0.25 per disputed sheet |
| Scale | Triangulate page size × printed scale, a dimension string vs its measured length, and objects of known size; confirm with the user | Exporters rarely write the PDF Measure dictionary reliably | ≈ $0 |
| Code knowledge | The existing code database plus reviewed jurisdiction packs (amendments, processes, forms, standing variances) | Exact | Licensing (section 9) |
| Code identification and applicability | Deterministic scope → decision model screens every provision → one-request rerank of the top 60 → frontier verifier | Measured on 53 Alberta precedents (section 6) | ≈ $0.02 per project for the screen |
| Rule checks (25 computable articles first) | TypeScript rules engine running in a Web Worker (live what-if) and Node (authoritative run); JSTS geometry in integer millimetres; a visibility-graph path module for travel distance | Same code on both sides gives reproducible flags; five geometric primitives cover the 25 checks | $0 |
| Claim verification | Exact quote match, then an entailment judgement (decision model), then a second-vendor model near the threshold | TypeSafe citation-check pattern; MiniCheck-class checkers | ≈ $0.00005 per claim plus escalations |
| Drafting narratives | Claude Sonnet 5.5 or GPT-6.1-Sol ($2 / $10 per million tokens), grounded on retrieved text; Opus 5.5 ($4 / $20) for hard comparisons | Closed-book code answers read well and are often wrong (57–66% expert-rated accuracy in a fire-code study), so drafting is always grounded and verified | ≈ $0.09–0.18 per application |
| Reviewer simulation | Opus 5.5 plus Gemini 4 Argon as an independent second reviewer; disagreements become "check this" items | Hypotheses until calibrated against real officer comments | ≈ $0.3–0.6 per run |
| Interface | React + TypeScript, PDF.js underlay, SVG semantic overlay (Konva fallback), the team's Linear-style design system | Clean licences; measured edit cost < 0.5 ms at 20,000 SVG elements | $0 |
| Hosting | PostgreSQL and object storage in Canada; self-hosted decision and vision models on Calgary GPUs (Denvr A100 80 GB) for residency customers | No hosted frontier model processes data in Canada today; Jev is US-hosted | GPU hours, not tokens |

Typical variable model cost for a 20-sheet case: about **$1.2** (cheap first tier), **$3.1** (Gemini 4 Argon reading, Opus reviewer), **$4.3** (Sonnet reads every tile; Opus verifies, drafts and reviews). Batch pricing cuts non-interactive stages in half. A minute of reviewer time costs more than the whole model bill.

## 6. Jev and the S1MB models: what to use, how

**Measured on our domain** (53 public Alberta precedents, 2,080 Division B articles, about $0.96 in total, 0 failed requests; [details](jev-benchmark/README.md)):

| Pipeline | Top-1 | Top-5 | Recall@50 | Recall@200 |
|---|---|---|---|---|
| Keyword search (BM25) | 32% | 66% | 77% | 83% |
| BM25 top 60 → Jev rerank | 66% | 81% | 77% | 83% |
| Jev screens all 2,080 | 53% | 77% | 88% | 91% |
| Jev screens all → top 60 reranked together | 64% | 81% | 88% | 91% |

**Adding a frontier verifier (measured, blind):** on the 20 variance and SPV cases, Claude Sonnet 5.5 read Jev's top 40 (randomly ordered, no scores shown, no other files or web) and ranked the governing articles. Top-1 rose from 65% (Jev alone) to **85%**, top-3 from 85% to 90%, recall within 5 from 69% to 83%. Its confident picks were reliable: 14 of 15 correct at p ≥ 0.8, 4 of 4 at p ≥ 0.9. Where the shortlist missed the gold article (greenhouse film), it named the right one from its own knowledge (3.1.18.5.), which the citation gate would then check. Cost about $0.03 per case. This is the cascade to build: deterministic scope → decision-model screen of every provision → one-request rerank → frontier verifier → abstain below a calibrated threshold (here, 5 of 20 cases would go to a person).

**How to use Jev (or any decision model) well:**

1. Fix scope in code first (Part 9 vs Part 3, division, edition).
2. Screen every provision in scope; do not let top-k retrieval decide what can be found.
3. Rerank the shortlist in one request so candidates are judged side by side.
4. Ask the job's real question. "Directly governs or departs from" for code identification; "a reviewer would raise an issue" for pre-flight. Not "applies" (647 of 2,080 articles score ≥ 0.5 for a house).
5. Compute derived facts (counts, thresholds, multi-step conditions, dates) in code and state them; the decision model's documented weaknesses are arithmetic and multi-hop reasoning.
6. Use its probabilities to order and to route, not as proof: the top pick was right in 7 of 8 cases at p ≥ 0.9 but only 18 of 25 at p ≥ 0.8.
7. Pin the model version (`jev-latest` moves from 1.13 to 1.14 this month) and set thresholds on our own labelled cases.

**Which decision model.** On S1MB English text, open Apache-2.0 models beat Jev: vllm-sr/d3 0.739 and Perplexity Decider v1.2 0.728 vs Jev 1.14 0.642, and the gap is largest on rule/entailment (+0.15) and numeric/spatial (+0.25) tasks. Perplexity Decider is $0.02 per million input tokens on OpenRouter, half of Jev's $0.042. On S1MB vision, Jev 1.14 leads (0.746) by 0.001. S1MB contains no building codes or drawings, so our harness is the deciding test: rerun it with Perplexity Decider v1.2 and vllm-sr/d3 (an OpenRouter key or the free d3 API key is all that is needed) and keep whichever wins on our cases. For Canadian data residency, self-host vllm-sr/d3 (27B, about 62–65 GiB) or d3-flash (8B) on Calgary GPUs; Jev is US-hosted with no documented Canadian or private option.

**Fix first:** the python.org Python 3.14 on this Mac has no CA bundle, so every `jev` call failed with "network" (that is why earlier research logs say "Jev unavailable"). Run "Install Certificates.command" from the Python 3.14 folder, or prefix calls with `SSL_CERT_FILE=/etc/ssl/cert.pem`.

## 7. Anywhere in Canada

One engine, one plan model, one rule language; reviewed **jurisdiction packs** carry the differences.

- **Common core (other provinces' adopted national editions, not Alberta law):** every province except Nunavut (NBC 2015) and Newfoundland and Labrador (NBC 2025) builds on NBC 2020, and the alternative-solution logic (Division A 1.2.1.1 and Division C section 2.3) is the same everywhere.
- **What a pack holds:** adopted text and amendments with effective dates and transition rules; who may prepare a submission (Manitoba and Vancouver require registered professionals, Alberta any owner or agent); the form (Alberta's single provincial template, Quebec's RBQ form, municipal forms elsewhere); the receiving authority; standing variances and local policies; licence terms.
- **Order (by fit and licensing):** Alberta (done) → Saskatchewan and Manitoba (their adopted NBC 2020 with light amendments; not Alberta law) → British Columbia (clearest licensing path; Vancouver separate) → Ontario (largest volume, active competitors) → Atlantic provinces → Quebec (French, strictest copyright) → territories. Roughly 3–6 months per reviewed pack with one jurisdiction expert, licences permitting (estimate).
- **Code churn is a feature:** the 2025 national model codes (released 2025-12-22) are expected to be adopted from about mid-2027. A change-impact view ("which of your projects and standing packages does this amendment touch") is valuable to applicants and regulators alike.
- **Honest coverage labels** in the product: full (rules, forms, packages), code-only (search and Section C, no rule pack yet), preview.

## 8. From wedge to a billion-dollar company

The market research is blunt: the Alberta variance wedge alone is a single-digit-million-dollar market, and Canada's authority-side pre-check pool is roughly US$23–50M a year. A billion-dollar outcome requires becoming **the compliance layer for building permits in several countries**, as the large outcomes in this space are platforms: Procore (US$1.32B revenue, FY2025), OpenGov (US$1.8B valuation, 2024), Autodesk's US$875M purchase of PlanGrid. The plan below is built so each stage funds and de-risks the next.

| Stage | Product | Who pays | Proof point |
|---|---|---|---|
| 1. Alberta wedge (0–18 months) | Variance autopilot for the five articles that make up 81% of volume; bespoke alternative-solution workspace; free officer view | Production builders (enterprise about C$40,000 a year), designers and consultants (about C$2,400 per seat), per-package fees; 3–5 authority pilots under C$75,000 each | Cycle time and first-pass acceptance on real files; integrate the Safety Codes Council / Build Forward Alberta template rather than compete with it |
| 2. Canada, all permits (18–36 months) | Pre-flight for every Part 9 permit and the review copilot for authorities; packs for SK, MB, BC, ON | Applicant subscriptions and per-project fees; authority licences (Denver's AI plan-review contract implies about US$77 per application per year) | Measured review minutes saved; licensed code text |
| 3. International (3–6 years) | Performance-based markets: England (Building Safety Regulator: Gateway 2 approval rose from 39% to 92% in a year once application quality improved), Australia and New Zealand (performance solutions), then the US (about 19,900 permit-issuing authorities; federal grants for automated permitting) | Same two-sided model | Second-country pack shipped |
| 4. Platform | Structured submissions as the standard between applicants and authorities; the building's compliance record reused for renovations, sales, lending and insurance; a marketplace for professional sign-offs and peer reviews; product-acceptance passports for manufacturers | Take rates and data products | Network effects: outcomes improve predictions |

To reach US$100M ARR (the usual threshold for a billion-dollar valuation) takes, for example, about 875 authorities, or about 12,000 Canadian seats plus international revenue; at top-decile growth that is 8–10 years (estimate). That is the honest size of the ambition.

**Moats:** reviewed, licensed jurisdiction packs with change tracking; a labelled corpus of real permit sheets and outcomes (the scarce asset no public dataset provides); an executable rule library with provenance that maps to NRC's coming machine-readable formats; the two-sided workflow position; Canadian data residency and audit trail.

## 9. Risks and what retires them

| Risk | Mitigation |
|---|---|
| **Code-text licensing.** NBC(AE) 2023 states that commercial reproduction of NRC material needs NRC's written consent; NRC's licence for machine-readable codes is "under development" | Write to Codes@nrc-cnrc.gc.ca now; use BC's formal licence process; architecture fallback of link-out and user-supplied text |
| **Official tools** (SSRIA research, supported by Build Forward Alberta, toward an alternative-solution template and written guide; announced 2026-10-07 with no date or price) | Be the best companion: implement the official template when it ships, and offer Batatis to SSRIA and the Council as the tool behind it |
| **Incumbents** (Archistar, Clariti/CivCheck, Cloudpermit) | Compete where they are absent: performance-based work, Plan Twin, Alberta |
| **Drawing extraction reliability** | Vector first; two readings per value; one-click confirmation; collect a licensed corpus from day one |
| **Trust and liability** | Four-state outputs; never "compliant"; calibration with ≥300 labelled items per stratum; audit sample |
| **Data residency** | Canada-resident mode with self-hosted models; cloud mode only with customer consent |
| **Alternatives being codified away** (CCMC reports as acceptable solutions, standing variances) | The same Plan Twin serves all-permit pre-flight; codification makes packages easier to automate |

## 10. What to build and show the judges

Two real Alberta patterns, both in the top five:

- **The 49% case:** a narrow-lot house whose site plan puts a side wall within 0.45 m limiting distance under a projecting soffit. Batatis measures limiting distance from the site plan, sees the soffit on the elevation, flags Sentence 9.10.15.5.(8), and offers: cut the soffit, or apply the jurisdiction's standing package where one exists (Calgary SPV-001 for zero-lot-line homes), producing the package and its conditions checklist.
- **The rowhouse case:** four houses adding basement suites. Batatis flags the firewall requirement in Sentence 9.10.11.2.(2) (#2 in Alberta) and duct dampers in 9.10.13.13. (#3), finds Calgary SPV-006, drafts the variance with Section C by lookup, and also catches ordinary deficiencies (bedroom egress window opening under Sentence 9.9.10.1.(2), smoke alarm locations and interconnection under 9.10.19.3. and 9.10.19.5., sound rating under 9.11.1.1.).

| Criterion (weight) | What the demo proves |
|---|---|
| Intake (20%) | Drop a drawing set; get the Plan Twin and a fact ledger with sources; at most a few explained questions |
| Code identification (20%) | Every provision screened, ranked, verified, quoted; measured recall on 53 public precedents |
| Recommendations (10%) | Fix options, standing packages, evidence ladder, professional triggers |
| Review (10%) | Officer view with verified citations, condition checklists, revision diff |
| Applicability (5%) | Two building types; any Part 9 project |
| Implementation (10%) | Working vertical slice plus the accuracy harness and its numbers |
| Business (10%) | Verified volume, clear buyers, expansion path, licensing plan |
| Usability/portability (10%) | No-forms intake; plain language; honest coverage labels per province |
| X factor (5%) | Live what-if on the plan; a variance drafted in about a minute |

Build order, by judging weight: (1) vector-PDF site plan and elevation reader for limiting distance, exposing face and soffits, with the 25-check rule engine starting from the top-five articles; (2) the Plan Twin overlay with provenance and four-state flags; (3) the screen-rerank-verify code-identification pipeline over the existing database; (4) variance composer with Section C lookup and standing-package checklists; (5) officer view and PDF export; (6) jurisdiction switcher with coverage labels.

## 11. Next steps this week

1. Ask NRC (Codes@nrc-cnrc.gc.ca) for written commercial terms; submit BC's copyright permission form.
2. Contact the Safety Codes Council / Build Forward Alberta about the template and a pilot, and ask how many variances are bespoke.
3. Get real Alberta permit sets (Calgary's sample suite drawings, builder partners); measure the vector/raster mix and extraction accuracy.
4. Rerun the decision-model harness with Perplexity Decider v1.2 and vllm-sr/d3; pick the winner.
5. Install the Python CA certificates so Jev works everywhere.
6. Build slice (1) above on a real narrow-lot house set.
