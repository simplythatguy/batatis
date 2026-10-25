# Accuracy95 Calgary/Edmonton procurement and owner-design search r3

**Search date:** 2026-10-25  
**Workspace branch:** work/luna-accuracy-95-20261025  
**Research ledger snapshot:** 2026-10-25 20:03:21 UTC (per-source retrieval timestamps were not exposed by the web tool)  
**Scope:** Up to five new independent Calgary or Edmonton project groups from public owner or procurement technical design records. The admission bar was a project-specific building code analysis, alternative-solution evidence, design drawings, or technical completeness evidence. Searches were limited to first-party public records and public procurement surfaces.

## Result

This pass found **0 eligible new Calgary/Edmonton project groups, 0 distinct new local projects, and 0 qualifying original attachments**. No new source group was added to the corpus. Nothing here demonstrates an approval, permit decision, technical correctness, or safety.

I ran the full 20-query budget, focused on CanadaBuys, University of Alberta, University of Calgary, and local facility procurement. This is zero additional groups beyond the earlier quarantined Edmonton ECSD report, which covers two named school projects in one shared source group; that prior group was not reopened or recounted here. The exact query strings and lead dispositions are in [procurement-candidates-r3.json](./procurement-candidates-r3.json). Search results provided a few useful near-misses, but no newly surfaced project attachment met both the locality and evidence requirements.

## Disposition of the strongest leads

- **Coronation ECO Station Expansion — municipal RFP notice only.** The [CanadaBuys notice](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/ab-2026-00800) describes an expansion and renovation at Coronation Yard and gives the site between 114 and 115 Avenue, east of 143 Street. The opened text does not explicitly name the project-site city, so I did not infer Edmonton from the City of Edmonton contracting organization or its reference to Edmontonians. The notice sends bidders to an external purchasing site and exposes no design attachment. The CanadaBuys leave-site request returned a web-reader 403, and the linked destination was not accessible through the web reader. No sign-in, account, or workaround was attempted.

- **University of Alberta Telus Gallery — construction-management RFP notice only.** The [CanadaBuys notice](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/ab-2025-00595) asks for construction-management services for Telus Gallery. It does not give a project-site address or establish the city of the project. Full details are on an external procurement site; the same web-reader 403 and destination-access limitation applied. No design attachment was exposed.

- **Bowness High School Theatre Upgrade — architectural-consultant RFP notice only.** The [CanadaBuys notice](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/ab-2025-06170) identifies a school-board RFP for an architectural consultant. Its body provides the board’s Calgary address, not a project site address, and its full details are on a third-party site that may require an account. I did not enter that site. No technical attachment was available on the opened public notice. This is not a drawing-index sheet, but the notice itself does not supply the design evidence requested.

- **INNISFAIL PDSTC Lunchroom Expansion — strong nonlocal attachment lead.** The official CanadaBuys search index surfaced a drawing set whose title block names the project as “INNISFAIL PDSTC / LUNCHROOM EXPANSION” and whose sheet A01-00-01 is titled “Building Code Review & Life Safety Plan.” The indexed extraction describes a 2015 NBC Part 3 review with occupancy, area, height, access, egress, and life-safety items. The drawing set is marked issued for tender. The [official drawing-set URL](https://canadabuys.canada.ca/documents/pub/att/2018/05/24/35e6ef55c32770672b659eaa2cce3981/drawings_final.pdf) was not downloaded or page-rendered because the named project is outside Calgary and Edmonton. Calgary in the title block is the architect’s office address, not project locality. Treat the indexed text as a lead, not byte-verified evidence.

- **Waiparous Creek Hydrometric Cableway Rebuild — federal tender drawings, outside the city and building scope.** The [official 10-page drawing package](https://canadabuys.canada.ca/sites/default/files/webform/tender_notice/24327/5000076429---annex-b---drawings_dessins_engineering-design-services_en.pdf) identifies the Waiparous Creek cableway, includes structural/site drawings, and is marked issued for tender. It is not a Calgary/Edmonton building project and contains no project-specific building-code analysis.

- **Transport Canada Canada Place workspace — Edmonton RFB, wrong evidence type.** The [public RFB](https://canadabuys.canada.ca/sites/default/files/webform/tender_notice/24914/t8080-230317---rfb.pdf) explicitly locates work at 9700 Jasper Avenue, Canada Place, Edmonton, but its scope is workstation supply, delivery, assembly, and installation. It does not expose building-code analysis or building-design completeness evidence. Its reference to detailed furniture plans does not make this a building design record.

- **University of Calgary design standards — generic records.** The [drawing standard](https://www.ucalgary.ca/live-uc-ucalgary-site/sites/default/files/teams/223/Design%20Standards/8.1%20Drawing%20Standard.pdf) and [CAD layer convention](https://www.ucalgary.ca/sites/default/files/teams/223/Design%20Standards/8.4.2%20Layer%20Naming%20Convention.pdf) mention code-analysis and fire-safety sheet types, but neither identifies a project or provides project drawings. Both were excluded as generic standards.

## Counts and deduplication

| Measure | Count | Evidence boundary |
| --- | ---: | --- |
| Targeted search queries | 20 | Exact query text is in the JSON artifact |
| Records dispositioned | 8 | Three procurement notices, two nonlocal drawing packages, one Edmonton furniture RFB, and two generic university standards |
| New eligible local source groups | 0 | No attachment met both locality and evidence requirements |
| Distinct new local projects | 0 | No project admitted |
| Qualifying original attachments / retained original bytes | 0 / 0 | No source-original bytes were downloaded or retained because no attachment first met the admission bar |
| Exact source URL matches in index | 0 | Normalized exact URL comparison |
| Exact source URL/final URL matches in source catalogue | 0 | Normalized exact URL comparison |
| Exact project-title substring matches in index | 0 | Compared the named project leads |
| SHA-256 comparisons possible | No | No qualifying original bytes were retrieved |
| Procurement records with observed web-reader access errors | 4 | Two external detail routes and two truncated City of Edmonton tender notices |
| Web-reader error observations | 6 | Two errors on each external detail route, plus one 403 for each City notice |
| Additional third-party detail route not accessed | 1 | Bowness notice says an account may be required |
| Existing eScribe 403 URLs retried | 0 | The prior 24 known gaps (18 Calgary, 6 Edmonton) were left untouched |

The URL comparison used both index source URLs and source-catalogue URL/final-URL fields, normalizing away query strings, fragments, and trailing slashes. Project-name checks were exact-title substring checks; they are not fuzzy identity resolution. Since no candidate originals were downloaded, there are no new hashes to compare. The candidate JSON records per-lead URL and title checks and leaves hash comparison unavailable where bytes were not obtained.

The four observed web-reader access-error records were the Coronation ECO Station and Telus Gallery external detail routes, plus two City of Edmonton tender notices whose titles were truncated in result lists. These failures describe the web-reader path only; they do not establish that the source host’s attachment is absent or blocked. No access control was bypassed. The existing 24 eScribe 403 URLs were not retried.

CanadaBuys states on the opened notices that related tender attachments are copyright-protected. No blanket redistribution permission is asserted. No source was copied into the prompt corpus or used for tuning or evaluation.

## Limits and next usable evidence

This sweep did not find an openly downloadable local owner/procurement attachment with a project-specific code analysis or alternative-solution record. The strongest practical lead is the Innisfail drawing package, but it is outside the target cities. The local procurement notices that could lead to design packages route to a third-party portal or do not expose attachments in the public notice. No further access attempt was made where the tool reported a 403, a destination was unavailable, or an account might be required.

No application facts, applicant prompts, or outcomes were synthesized. No fees were paid, access-to-information request was filed, person was contacted, or material published. The search was read-only with respect to the corpus: index, gold labels, prompts, source metadata, and engine files were not edited.

## Methods used

- Matt Pocock, research: primary-source search and claim-level evidence limits. The method’s usual background-agent step was omitted because the task explicitly prohibited further delegation.
- T3 workflow, research route: kept the scope bounded to the assigned artifact paths.
- Batatis hackathon domain guidance: treated code/design records as administrative evidence only; no claim of technical correctness, compliance, approval, or safety.
- The parent’s previously completed T3 maintenance check was reused as directed in the task brief. The PDF rendering method was not loaded because no eligible original was downloaded or rendered.

