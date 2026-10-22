# Source checks, 21 October 2026

The plans and the pitch cite figures that no other file in `docs/research/` holds. This note records where each one comes from, what was read, and the value. Each source was downloaded or run on Oct 21, 2026. Downloaded files are not committed. Each entry gives the SHA-256 of the file read (first 16 hex digits), so a reader can repeat the check. Anything not listed here is either in another research file (named in the plan that uses it) or is labelled an estimate or an assumption there.

Labels follow `C-market-provinces-business.md`: **verified** means the figure is on the primary source named, **measured** means a run or a file produced it, **estimate** means arithmetic on the figures shown.

## 1. Safety Codes Council documents

| Source | SHA-256 | Value read | Label |
|---|---|---|---|
| [Annual Report 2023](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/Annual%20Report%202023.pdf), printed page 32, table "Variances" | 477b961d152658ab | Building variances registered: 2019 1,553; 2020 637; 2021 1,698; 2022 1,713; 2023 837. All disciplines in 2023: 909, "as of the end of March 2024", and "some 2023 variances have not yet been captured". Shares of all variances in 2023: City of Edmonton 67%, City of Calgary 9%, other jurisdictions 25% (as published, rounded). "Jurisdiction-wide variances may decrease the number of variances being issued." | Verified |
| [Council fee schedule, ASCA permit fees](https://ebs.safetycodes.ab.ca/documents/webdocs/sr/council%20fee%20schedule%20asca%20v2.pdf), version 2, effective Jan 1, 2022, page 6 | 6e404d386179343f | "Alternative solution/variance* $125/hour". The footnote reads "* Discretionary charge by issuing Agency". The schedule applies to the Alberta Safety Codes Authority, which serves unaccredited areas. It also states the Council levy: 4% of the permit fee, minimum $4.50, maximum $560 | Verified |
| [IB-2025-11-18](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2025-11-18%20Mandatory%20Documentation%20of%20Variances.pdf), Mandatory Documentation of Variances | 3ca39cbf4d1c0797 | "Building, fire, and plumbing: Document alternative solutions as required by Division C of the applicable code." "Submit a copy of each variance to the Safety Codes Council within 10 days of issuance." "Retain all supporting documentation and make it available upon request by an Administrator." | Verified |
| [IB-2026-10-01](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf), Orders and Variances Registration Changes | ac3217ac4603f490 | Effective Dec 1, 2026 the Orders and Variances Portal "will be the sole acceptable method for registering orders and variances". "Only SCOs will have access to register variances and orders in OVP." "All variances must be registered individually, for a specific location, including those relying on jurisdictional alternative solutions." Supporting documentation "must be included at the time of registration". "The revised variance form must be completed and included when the variance is registered through OVP." Registration "does not constitute Council approval of that order or variance and does not transfer responsibility for the decision from the individual authorized under the Safety Codes Act to issue it." Organizations with high volumes "may work with the Council to develop automated interfaces, integrations, or other approved solutions" | Verified |
| [IB-2026-10-16](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-16_AHJ_Clarification.pdf), Clarifying Authority Having Jurisdiction | dbd3a61b53f5ad4e | "Authority Having Jurisdiction rests with accredited organizations and the Alberta Safety Codes Authority." "SCOs do not supersede or replace the AHJ established under the Act." Undue influence is "a person directing an SCO to issue a variance based on anything other than an administratively compliant alternative solution." | Verified |
| Variance form dated Oct 6, 2026 (`engine/data/jurisdictions/provinces/AB.json`, entry `scc-variance`) | f44640ca005c957c | 5 pages, 87 fields. The SHA-256 of the file read matches the field map `engine/export/field_maps/scc_2026-10.json` | Verified |

## 2. Built World Challenge documents

| Source | SHA-256 | Value read | Label |
|---|---|---|---|
| [Innovator Onboarding Guide, Fall 2026](https://edmontonunlimited.com/wp-content/uploads/2026/09/Built-World-Challenge-Onboarding-Guide.docx.pdf), page 2 | f21a701467385f42 | Oct 29 Submission 1, the semi-final package, "Top ~10 teams selected for semi-finals". Nov 10 semi-final presentations, "Up to 5 teams selected for finals". Nov 10 to 26 build and refine with coaches. Nov 26 Submission 2, the final package. Dec 1 Demo Day. Dec 2 to Mar 2 "Implementation of the prototype into a customer environment (not guaranteed but this is indeed the point, so let's make it happen!)". Building Codes Challenge sponsors: Safety Codes Council, BILD Alberta, Jayman Homes, City of Edmonton. Prizes for the Building Codes stream: $3,000, $1,000, $1,000. "Exact submission deadlines, templates and instructions to be posted in Discord." The team owns what it builds | Verified |
| Challenge Scope (local copy `reference/guides/Challenge-Scope.pdf`, git-excluded; public at edmontonunlimited.com), pages 1 to 4 | 761bf8d9d8e93445 | "There are over 430 jurisdictions in Alberta." "Financial cost in labour, errors, and delay ranges from a few hundred dollars to tens of thousands of dollars, depending on complexity and how much rework is required." The framing is described in the scope as anecdotal. The rubric on page 4 matches `docs/judging-rubric.md` | Verified as the organizers' framing, not a survey |
| Council presentation "Alternative Solutions Under Alberta's Objective-Based Codes" (Adam Salkeld, Compliance and Technical Advisor, Building; local copy `reference/guides/SCC-hackathon-presentation-alternative-solutions.pdf`, git-excluded), 14 slides | e2ee8ab52ac74e9b | Slide 6 table: a variance is a "legal authorization to deviate" under Safety Codes Act s.38, tested for "approx. equivalent or greater safety", issued by an Administrator or SCO who may set conditions, refusal appealable within 30 days. An alternative solution is "technical evidence behind the decision" under NBC(AE) Div. C, 2.3.1, tested against "at least Division B minimum performance", prepared by the proponent. "Compliance with a variance is deemed to be compliance with this Act. (Safety Codes Act, s. 40(2))". Slide 8: request for variance plus alternative solution equals accepted variance. Slide 11: Recognize, Pre-apply, Submit, Review, Decide, Close out ("Copy to the Council within 10 days"). The file must contain: code analysis and attributions; assumptions, limits and testing; qualifications, coordinator, maintenance needs. Slide 12: worked example Sentence 9.10.15.4.(1), function F03, objective OP3.1 | Verified |

## 3. The Council's form compared with the challenge brief's Appendix 1

Read from the two PDFs on Oct 21 (Appendix 1 on pages 5 to 9 of the Challenge Scope; the current form is the file in §1).

| Place on the form | Appendix 1 | Form dated Oct 6, 2026 |
|---|---|---|
| Section B checkbox | "Check this box if the Proposed Alternative Solution is for a Jurisdiction and is not site-specific." | "Check this box if the Proposed Alternative Solution has been submitted to the Safety Codes Council for review for jurisdictional use." |
| Section D | One field: "Name of Supporting Documentation and Name of the Individual/Professional and/or Professional Organization Responsible" | Two columns: "Name of Supporting Documentation" and "Name of Individual/Professional/Professional Organization Responsible" |
| Signatures and disclosures | Collection under section 4(c) of the Protection of Privacy Act. A list of fields the Council may publish. A checkbox: "By checking this box, I acknowledge and agree to the described use of the information provided." A declaration above the signatures: the alternative "will provide an alternative that provides equal or better performance" | Collection still under section 4(c). Sharing with the Council "in accordance with the municipality's Quality Management System agreement and section 13(1)(b) of the Protection of Privacy Act". "Some of the non-personal information provided in this form may be published on the SCC website." No checkbox and no performance declaration in Part 1 |
| Part 2(a) | "equal or better performance to the provisions of the Code, Standard, and/or regulation" | "approximately equivalent or greater safety performance to the provisions of the Code and/or Standard" |
| Part 2(b), third reason | "will NOT provide equal or better performance" | "will NOT provide approximately equivalent or greater safety performance". Adds a line: "This written refusal has been served to the applicant on in this format" |
| Part 3 | Appeal "within 30 days of the date the Written Notice was served in person" | Appeal "within 30 days of the date the Refusal was served" |

## 4. Exchange rate

Bank of Canada Valet API, series FXUSDCAD (daily average): 2026-10-19 1.4097, 2026-10-20 1.4054, 2026-10-21 1.4057. Verified by request on Oct 21. Costs in the plans use 1.4057.

## 5. Model cost per case

Code identification was measured by the benchmark harness in draft PR #58 (`feat/wp10-11-evals`, branch tip 6a42795, Oct 21). The harness keeps a hash-chained ledger of every model request in `evals_dev/identify_bench/ledger/` (one file per provider). The ledger bills the relevance stage at US$0.042 per million tokens, input and output alike, which is the price `engine/llm_gate.py` uses. It bills the verifier at the short-context list price (US$0.10 in and US$0.50 out per million tokens). The product's gate reserves and settles the verifier at the long-context price (US$0.20 and US$0.75), an over-estimate. The ledger bills cached input at the full price.

Settled requests, summarized on Oct 21 with the script below. The branch is a draft and is not on `dev`.

| Stage | Settled calls | Mean cost (US$) | Mean tokens in and out | Notes |
|---|---:|---:|---|---|
| Relevance screen of all 2,080 Division B articles | 291 draws | 0.0173 | 375,089 and 36,903 | About 20 requests per draw. Median 0.0176 |
| Relevance re-rank of the top 60 | 284 | 0.00056 | 12,152 and 1,070 | One request |
| Verifier reading the full text of the top 15 | 636 | 0.00099 | 4,499 and 1,083 | Ledger price. At the gate's long-context price: 4,499 x 0.20 / 1,000,000 + 1,083 x 0.75 / 1,000,000 = 0.0017 |

Sum for one identification run, at ledger prices: 0.0173 + 0.00056 + 0.00099 = US$0.0189. With the verifier at the gate's price: US$0.0196. In Canadian dollars at 1.4057: C$0.0265 and C$0.0275.

The 2026-10-20 research (`docs/research/2026-10-20-vision/README.md`, §6, and the benchmark README in its subfolder for the relevance benchmark) reports the same screen cost from an earlier run: about 0.38 million input tokens per case, about US$0.016 at US$0.042 per million input tokens, 20 requests, about 1.6 seconds with 8 parallel requests.

The intake model pass was measured in PR #54: 19 live calls cost about US$0.012 in total, about US$0.0006 per call.

```python
import json, collections, statistics
# run from a checkout that has both ledger files from branch feat/wp10-11-evals at 6a42795
for path in LEDGER_FILES:
    rows = [json.loads(l) for l in open(path)]
    by = collections.defaultdict(list)
    for r in rows:
        if r['op'] == 'settle':
            by[r['arm']].append(r)
    for arm, rs in by.items():
        usd = [float(r['usd']) for r in rs]
        print(arm, len(rs), statistics.mean(usd),
              statistics.mean(r['input_tokens'] for r in rs),
              statistics.mean(r['output_tokens'] for r in rs))
```

## 6. Internal runs

| Run | Command | Result | Limits |
|---|---|---|---|
| Intake rules on the 60 development cases, Oct 21, `dev` at 054c632, no model, no network | `python -m evals_dev.intake_facts.score` | Precision 159/159 = 1.000 (95% Wilson 0.976 to 1.000). Recall 159/162 = 0.981 (0.947 to 0.994). Recall on labels taken from the cases' known facts: 134/137. Three misses: dev-014, dev-047, dev-051 | In sample: the labels were written while the rules were written (`evals_dev/intake_facts/gold.json`). Cases are agent-authored and model-checked |
| Continuous integration on `dev` at 054c632 | GitHub Actions run 39720990321 | Engine job: 1,698 passed, 5 skipped. Web job and secret scan passed | The skipped tests need provider access |
| Live deployment, read-only requests, Oct 21 | `GET /api/jurisdictions`, `GET /api/code/search`, `GET /api/openapi.json` on https://batatis-vert.vercel.app | Three packs (calgary, edmonton, alberta-other) with coverage "full", and 13 coverage rows in total (12 labelled "preview"). Code search for "glazed openings exposing building face" returns 9.10.15.4. and 9.10.15.4.(1) among the first three rows. The OpenAPI document lists 64 paths | Shows the deployed build serves these routes. It does not show live provider access |

## 7. Code citations checked in the code database

Looked up with `python -m codedb lookup` on Oct 21 in the NBC(AE) 2023, 2nd printing database (`codedb/README.md`). PDF pages are 1-based.

| Id | Title or topic | PDF page |
|---|---|---:|
| Division A, 1.2.1.1.(1)(b) | Alternative solutions achieve "at least the minimum level of performance required by Division B" | 38 |
| Division A, 1.2.2.1.(2) | Evaluation reports issued by the Canadian Construction Materials Centre may be used in determining compliance | 38 |
| Division A, 1.4.1.1.(4) | Where alternative solutions are referred to, they are those in Clause 1.2.1.1.(1)(b) | 41 |
| Division C, 2.3.1.1.(2)(b), (3), (4), (6) | Documentation of alternative solutions, including the co-ordinator | 739 |
| Division C, 2.4.1.1.(3), 2.4.1.2.(1) | Registered professionals | 740 |
| 9.10.15.4.(1) | Glazed Openings in Exposing Building Face. Attribution [F03-OP3.1] in Table 9.38.1.1., PDF p.1130 | 901 |
| 9.10.15.5.(8), (9), (10) | Construction of Exposing Building Face of Houses | 904 |
| 9.10.11.2.(2) | Firewalls Not Required | 889 |
| 9.10.13.13.(1) | Fire Dampers | 893 |
