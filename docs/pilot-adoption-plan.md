# Batatis: Pilot and Adoption Plan

*Building Codes Challenge, Submission 1 (Oct 29, 2026). Status is as of Oct 22, 2026. Status words follow the Implementation Plan, §3: **built**, **backend** (the API is merged and its screen is not finished) and **roadmap**. Source notes: `docs/research/2026-10-21-source-checks.md`.*

> **No pilot partner has agreed to anything.** No applicant, officer or organization has used Batatis or seen a price. Every date, segment and metric below is a **target**, not a result and not a commitment from anyone else.

## 1. Phases after Demo Day (all targets)

| Phase | When (target) | What happens | Exit condition (target) |
|---|---|---|---|
| 0. Ready to pilot | Nov 26 build, pilot-ready by Dec 1, 2026 | Screens for the officer package review and the close-out record finished. Hosting in a Canadian cloud region. A pack and reviewer access code for the pilot authority. Monitoring of ask rate, override rate and dropped-quote rate | The build passes the automated checks and a planted-gap package with no compliance claims and no invented citations |
| 1. Parallel pilot with one accredited organization | Dec 2, 2026 to Mar 2, 2027, the program's implementation window, which the guide calls "not guaranteed" ([onboarding guide](https://edmontonunlimited.com/wp-content/uploads/2026/09/Built-World-Challenge-Onboarding-Guide.docx.pdf)) | Applicants prepare packages with Batatis. Officers run the completeness review alongside today's process. Officers make every decision and register in the Council's portal themselves | The success metrics in §3 are met and the organization asks to continue |
| 2. Applicant self-serve | After a successful pilot | Repeat filers (production homebuilders, manufacturers) use Batatis to arrive complete in any participating jurisdiction | Paying applicant accounts at a price tested in the pilot |
| 3. More organizations, then a portal interface | After phase 2 | Add a pack for each organization that joins. Build an interface into the portal only on the Council's terms | The Council publishes integration requirements and approves the path |

## 2. Target segments (in order)

| # | Segment | Why this order | Source |
|---|---|---|---|
| 1 | **Accredited organizations with high variance volume** (municipal building groups) as the pilot host | The authority having jurisdiction is the accredited organization, not the individual officer, so a pilot is agreed with the organization. The City of Edmonton accounted for 67% of all variances in 2023 (all disciplines) | [IB-2026-10-16](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-16_AHJ_Clarification.pdf); [Annual Report 2023](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/Annual%20Report%202023.pdf), p.32 |
| 2 | **Production homebuilders** as the first paying applicants | The person requesting the alternative solution supplies the Division C documentation, now mandatory. The five most-varied building articles are all Part 9 house provisions and make up 2,503 of the 3,088 entries in Q1 to Q2 2026 (81%). One article, 9.10.15.5.(8), has 1,501 | [IB-2025-11-18](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2025-11-18%20Mandatory%20Documentation%20of%20Variances.pdf); `docs/research/2026-10-20-vision/C-market-provinces-business.md` §2.0 |
| 3 | **Product manufacturers** using the alternative-solution path | An evaluation report from the Canadian Construction Materials Centre or another recognized body may be used in determining compliance (Division A, 1.2.2.1.(2)), and the project-specific alternative solution covers the project that uses the product. Batatis helps assemble the application on the Council's form and shows what the evidence must address. The applicant's licensed professional provides the technical content and judgment, and the authority reviews the submission | `docs/research/2026-10-21-source-checks.md` §7 |
| 4 | **Smaller accredited organizations** | Alberta has 433 accredited organizations, 299 of them municipalities. They are reached by adding a pack once one pilot works, and the fallback pack serves them until then | `docs/research/2026-10-20-vision/C-market-provinces-business.md` §2.0; `docs/api/jurisdictions.md` |

## 3. Success metrics (targets, not results)

| Metric | Target | How measured |
|---|---|---|
| Returns for more information | Fewer than the organization's own baseline for comparable applications | The organization's records, compared in parallel |
| Officer completeness-review time | Below the manual baseline on the same planted-gap package | The timed protocol in `docs/user-testing/officer-timing-protocol.md`. No timing data exists today |
| Planted gaps caught by officers using the report | At least Y of Z, fixed before the session | The same protocol |
| Compliance claims or invented citations in output | 0 | Automated checks plus the officer override log |
| First-time applicants completing Part 1 A to D unaided | At least 2 of 3 per round | Think-aloud sessions, only if a partner engages |
| Continuation | At least 1 organization asks to continue after Mar 2, 2027 | A written request |
| Model cost against price | One identification run costs about US$0.019 to US$0.020 (C$0.027 to C$0.028), measured. A generous application costs about C$0.17, which is about 0.1% of the low end of the price hypothesis (C$150) | `docs/business-plan.md` §6. Other costs are not priced |

## 4. Gating conditions

| Gate | What it requires | Our response | Source |
|---|---|---|---|
| **Procurement** | Calgary requires open competitive procurement at C$75,000 or more for goods and services. The research did not find Edmonton's internal threshold. A paid pilot would go through the program's Venture Pilots review, which the guide describes without an amount | Keep the pilot scope under C$75,000. A paid contract above the threshold would go through the organization's competitive process | `docs/research/2026-10-20-vision/C-market-provinces-business.md` §5.2; onboarding guide |
| **Privacy: private applicants** | Alberta's PIPA applies, and the federal Privacy Commissioner says PIPEDA can still apply to a disclosure across provincial or national borders, case by case | Personal details are removed before AI calls (with a stated limit). Applications follow the inactivity and workflow retention policy. Canadian-region hosting for the pilot. The organization's own review decides whether the model path is allowed. Without it, Batatis runs on its labelled keyword search | `docs/research/2026-10-21-source-checks.md` §2b; `docs/implementation-plan.md` §5 |
| **Privacy: municipalities** | Alberta's Protection of Privacy Act has been in force since June 11, 2025. It requires a privacy management program, privacy impact assessments in defined cases, breach notification, and notice when personal information is used in an automated system | The pilot contract would set who is responsible for what and who owns the pilot records, subject to the organization's privacy review. We would prepare an impact assessment pack for that review | `docs/research/2026-10-20-vision/C-market-provinces-business.md` §5.2 |
| **The Council's portal** | From Dec 1, 2026 only SCOs register variances, only through the portal, one location per registration, with supporting documentation and the revised variance form. Unnecessary personal information is removed or redacted. Integration requirements are still to come | Batatis never registers anything. The close-out record lists what to send and keep, and the SCO does the registering. Any interface is built only with the Council's approval | [IB-2026-10-01](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf) |
| **Program window** | The Dec 2 to Mar 2 window is not guaranteed | Phase 1 slips to whenever an organization engages. Nothing in phases 2 and 3 depends on program funding | Onboarding guide |
| **Code text terms** | The app shows code text in full, with its citation, PDF page and a credit and link to the NRC publication, and the code library lets a user read any article. NBC(AE) 2023 says commercial reproduction of NRC material needs written consent | Written NRC terms before any public commercial launch. For a private pilot with an authority, confirm with the authority whether the display is acceptable | `docs/business-plan.md` §9 |
| **Reviewer accounts** | Reviewer accounts exist only for Calgary and Edmonton | Open the account type to a pilot authority from its pack when a pilot is agreed | `docs/api/jurisdictions.md` |

## 5. What we would ask of a partner

These are requests, not agreements.

- Two officers for about two hours each, for the timed planted-gap review.
- A named contact for the organization's privacy review.
- The organization's current intake steps and forms, so that its pack is accurate and cites its own documents.
- Permission to compare returns for more information against the organization's own baseline.

## 6. What would stop the pilot

- An officer finds a compliance claim or an invented citation in output: pause and fix before continuing.
- The organization's privacy review does not approve the data flow: run without the model path or stop.
- The Council's portal requirements conflict with the close-out package: change the package, not the officer's process.
