# Batatis: Pilot and Adoption Plan

*Building Codes Challenge, Submission 1 (Oct 29, 2026). Sources read Oct 20, 2026.*

> **We have contacted no one.** No pilot partner, applicant, officer or organization has agreed to anything, seen a price, or tested Batatis. Every date, segment and metric below is a **target**, not a result or a commitment from anyone else.

## 1. Phases after Demo Day (all targets)
| Phase | When (target) | What happens | Exit condition (target) |
|---|---|---|---|
| 0. Ready to pilot | Nov 26 build, pilot-ready by Dec 1, 2026 | Hosting in a Canadian cloud region; applicant and officer sign-in; officer completeness view; portal registration package (form, attachment manifest, redaction flags); monitoring of ask, override and dropped-quote rates | Build passes the agent-run walkthroughs and the planted-gap package with no compliance claims and no invented citations |
| 1. Parallel pilot with one accredited organization | Dec 2, 2026 – Mar 2, 2027 (the program's implementation window, which it calls "not guaranteed", [onboarding guide](https://edmontonunlimited.com/wp-content/uploads/2026/09/Built-World-Challenge-Onboarding-Guide.docx.pdf)) | Applicants prepare packages with Batatis; officers run the completeness review alongside today's process. Officers make every decision and register in the Council's portal themselves | Success metrics in §3 met, and the organization asks to continue |
| 2. Applicant self-serve | After a successful pilot | Repeat filers (production homebuilders, manufacturers) use Batatis to arrive complete in any participating jurisdiction | Paying applicant accounts at a price tested in the pilot |
| 3. More organizations, then an OVP integration | After phase 2 | Configure per-organization checklists; build an approved interface into the portal only on the Council's terms | The Council publishes integration requirements and approves the path |

## 2. Target segments (in order)
| # | Segment | Why this order | Source |
|---|---|---|---|
| 1 | **Accredited organizations with high variance volume** (municipal building groups) as the pilot host | The authority having jurisdiction is the accredited organization, not the individual officer, so a pilot is agreed with the organization. Edmonton accounted for about 67% of 2023 variances (all disciplines) | [SCC IB-2026-10-16](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-16_AHJ_Clarification.pdf); [SCC Annual Report 2023](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/Annual%20Report%202023.pdf) |
| 2 | **Production homebuilders** as the first paying applicants | The person requesting the alternative solution supplies the Division C 2.3.1 documentation, now mandatory. The most-varied building articles are Part 9 house provisions (1,501 of 3,088 building article entries are soffit article 9.10.15.5.(8)) | [SCC IB-2025-11-18](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2025-11-18%20Mandatory%20Documentation%20of%20Variances.pdf); [SCC Data Hub](https://www.safetycodes.ab.ca/data-hub/variance-data/) |
| 3 | **Product manufacturers** using the alternative-solution path | A CCMC assessment or recognized evaluation is voluntary evidence for the authority, which decides, while the alternative solution is project-specific and submitted with a permit; Batatis prepares the project-specific package | [Calgary B23-014](https://www.calgary.ca/content/dam/www/pda/pd/documents/building/advisories/b23-014-new-products-materials-and-systems-in-building-construction.pdf) |
| 4 | **Smaller accredited organizations** | Alberta has 433 accredited organizations, 299 of them municipalities; reached through per-organization configuration once one pilot works | [SCC Annual Report 2025](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/Annual%20Report%202025%20Final.pdf) |

## 3. Success metrics (targets, not results)
| Metric | Target | How measured |
|---|---|---|
| Returns for more information | Fewer than the organization's own baseline for comparable applications | Organization's records, compared in parallel |
| Officer completeness-review time | Below the manual baseline on the same planted-gap package | Timed planted-gap protocol (Implementation Plan §7); no timing data exists today |
| Planted gaps caught by officers using the report | At least Y of Z, fixed before the session | Same protocol |
| Compliance claims or invented citations in output | 0 | Automated checks plus officer override log |
| First-time applicants completing Part 1 A–D unaided | At least 2 of 3 per round | Think-aloud sessions, only if a partner engages |
| Continuation | At least 1 organization asks to continue after Mar 2, 2027 | Written request |
| Cost per case vs. price floor | Identification measured (pinned models, mean of 3 repeats): C$0.027 per case on dev cases, about 0.02% of the C$125 floor (Implementation Plan §4); full pipeline to be measured | Keyed benchmark, reported in US$ and C$ with a dated rate |

## 4. Gating conditions
| Gate | What it requires | Our response | Source |
|---|---|---|---|
| **Procurement** | Edmonton and Calgary run open competitive procurement for goods and services at or above C$75,000 (the New West Partnership Trade Agreement threshold). In Edmonton, a sole source at that level needs documented proof that only one supplier can meet the need | Keep the pilot scope under C$75,000. The program's Venture Pilots stream may fund pilots (the program lead told media "around $10,000 to $50,000"; not an official figure). A paid contract above the threshold would go through the organization's competitive process | [Edmonton Procurement Standard](https://www.edmonton.ca/sites/default/files/public-files/Procurement%20Standard.pdf); [Calgary procurement policy](https://www.calgary.ca/buy-sell/supply-to-city/procurement-policy.html); [Taproot, Sep 22, 2026](https://edmonton.taproot.news/briefs/2026/09/22/pilot-builds-on-foundation-with-new-challenge-ahead-of-startup-week) |
| **Privacy: private applicants (PIPA)** | Alberta's PIPA applies to private organizations within Alberta; PIPEDA still applies to cross-border transfers, such as calls to a model API outside Canada | Personal information stays in the case record and out of prompts; Canadian-region hosting; Zero Data Retention to be requested from the model provider (not yet requested); keyless in-region fallback available | [OIPC: PIPA](https://oipc.ab.ca/legislation/pipa/); [OPC](https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/r_o_p/prov-pipeda/) |
| **Privacy: municipalities (POPA)** | Alberta's Protection of Privacy Act has been in force since June 11, 2025; its privacy-management-program duties apply from June 11, 2026 | The organization's POPA obligations flow to us by contract, and pilot records belong to the organization | [OIPC: POPA](https://oipc.ab.ca/legislation/popa/) |
| **The SCC portal (OVP)** | From Dec 1, 2026, only SCOs register variances, only through OVP, one location per registration, with supporting documentation and the revised variance form; unnecessary personal information is removed or redacted. Integration options and technical requirements are still to come | Batatis never registers anything; it prepares a package the SCO uploads. Any automated interface is built only with the Council's approval | [SCC IB-2026-10-01](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf) |
| **Program window** | The Dec 2 – Mar 2 implementation window is not guaranteed | Phase 1 slips to whenever an organization engages; nothing in phases 2–3 depends on program funding | Onboarding guide (above) |
| **Code text terms** | NRC code text is linked or quoted minimally | Written NRC terms before any commercial use | Implementation Plan §10 |

## 5. What would stop the pilot
- An officer finds a compliance claim or an invented citation in output: pause and fix before continuing.
- The organization's privacy review doesn't approve the data flow: run the keyless in-region path or stop.
- The Council's portal requirements conflict with the package format: change the package, not the officer's process.
