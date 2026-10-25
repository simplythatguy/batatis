# Calgary school/facility and adaptive-reuse source search

**Search date:** 2026-10-25 UTC  
**Scope:** Independent pass for Calgary school-board/facility preplanning or building-code-analysis attachments, plus City of Calgary building-specific adaptive-reuse technical reports. This did not repeat broad SPV/SCC/PAB harvesting.

## Result

No candidate met the attachment-backed admission bar in this pass. I found **0 new eligible Calgary projects and 0 new independent source groups**. No original project document was downloaded, so this pass records **0 original-byte hashes and 0 locally verified PDF pages**. The artifact is a search and access handoff, not a new corpus prompt.

The starting corpus snapshot remains **17 Calgary prompts across 12 source groups**. The prior 26-query accuracy95 sweep already recorded that same Calgary count and one new Edmonton group for Griesbach/Chambery; that Edmonton report was not counted here. The full prompt index and source catalogue were checked before disposition. No near-miss project name or URL/path string matched an indexed Calgary case or the source catalogue. A SHA-256 comparison was not possible because no original bytes were retrieved.

## First-party leads and dispositions

### Springbank Hill School: drawing index only, current URL returns 404

The CBE-hosted, web-indexed one-page PDF names Springbank Hill School at **7652 26 Ave SW, Calgary**, CBE as owner, project 2015-001, and “Issued for Tender” dated March 11, 2016. Its drawing list includes sheet A0.01, “Building Code Analysis, Legends and Assembly Schedules.” The PDF itself is only a one-page title/index sheet; it does not contain that analysis. The current direct GET returned **404 HTML** (108,205 response bytes), so there are no original drawing bytes or hash to retain. [CBE PDF](https://www.cbe.ab.ca/schools/building-and-modernizing-schools/Documents/Springbank-Hill-School-Elevation.pdf)

### Foothills Athletic Centre and Fieldhouse: potential City facility code appendix, blocked

A City of Calgary eScribe attachment indexed as “FRA2019-0628 Program Overview and Update ATT 3” identifies the Foothills Athletic Centre and Fieldhouse. The search-indexed contents list “Building Code Analysis” at Appendix K, printed page 319, among project diagrams, systems descriptions, a soils report, space programme, risks, and outline specifications. These are index-only observations; the project report’s original bytes are needed to establish contents, explicit project locality, and project scope. The City publisher context was not used to infer locality. Direct GET to the official eScribe filestream returned **403 Cloudflare challenge HTML** (307,665 response bytes), not the PDF. I did not retry through alternate access paths. The visible project naming does not establish adaptive reuse, so this remains an unverified facility-code-analysis lead and is not counted as an eligible group. [City attachment](https://pub-calgary.escribemeetings.com/filestream.ashx?DocumentId=93287)

### John G. Diefenbaker School: pre-design report lead, report not attached

The official CBE construction status report’s indexed text says a pre-design report for John G. Diefenbaker School modernization was completed in December 2023 and that Alberta Infrastructure manages the project. The status report does not supply the underlying pre-design report or its technical/code analysis. The inspected search-index text also does not establish the project street address or explicit city; locality is not inferred from the board publisher. This is a follow-up lead only. [CBE Construction Projects Status Report](https://www.cbe.ab.ca/schools/building-and-modernizing-schools/Documents/Construction-Projects-Status-Report-June-24-2025.pdf)

## Adaptive-reuse search results excluded

- A City of Calgary downtown incentive-program report discusses office conversions and adaptive reuse at the program level; no building-specific technical report surfaced. [City report](https://pub-calgary.escribemeetings.com/filestream.ashx?DocumentId=298938)
- Calgary Arts Development’s cultural-spaces report discusses city-owned facilities and adaptive reuse at a sector level, but is not a City project report and does not provide a building-level technical package. [Strategic report](https://calgaryartsdevelopment.com/wp-content/uploads/2025/06/20250602-Final-Strategic-Update-Full-Report.pdf)

These were excluded as policy/sector material rather than project evidence. Existing Calgary Fire Hall No. 1/North-West Travellers, Planetarium, YWCA/Beltline Pool, school/SPV and SCC groups were not counted again.

## Search and verification record

I ran **20 focused search queries** across CBE, Calgary Catholic School District, Alberta Infrastructure/Alberta Government, City of Calgary, and the City’s public meeting attachment domain. Query text, candidate metadata, direct-fetch URLs/statuses, dedupe fields, and source limits are in [candidates.json](./calgary-search-candidates.json).

Direct GET outcomes for the two first-party attachment leads were:

- CBE Springbank Hill index PDF: HTTP 404; only an HTML error response was returned.
- City eScribe Foothills attachment: HTTP 403; only a Cloudflare challenge page was returned.

The prior accuracy95 source file reports aggregate Calgary eScribe 403 counts but does not retain the URL-level blocked list. Therefore the Foothills 403 is **one URL observed as blocked in this pass**, but whether it is novel relative to all earlier Calgary 403 attempts cannot be established from the saved record. The exact URL is absent from the current `source_catalogue.jsonl`.

No source bytes were retained under `originals/`, because none of the leads yielded an eligible, retrievable original project document. No redistribution permission was verified. No facts, application prompts, or attachments were synthesized.

## Parent browser follow-up

At 2026-10-25 20:29:43 UTC, an ordinary Chromium session opened the same public Foothills attachment URL. It returned HTTP 403, `text/html; charset=UTF-8`, with page title `Just a moment...`. No PDF was downloaded or counted. The check used no credentials, proxy, stealth settings, CAPTCHA interaction or other access-control workaround. The raw access record remains at `Data Prompts/_research/accuracy95-browser-source-check/access.json` (ignored local artifact). This is one additional access observation, not a new source group or a retry of all 24 prior gaps.

## Methods used

- Matt Pocock, **research**: primary-source search, direct-source verification, and a source-backed handoff.
- T3 workflow **research route**: bounded research scope, use of the assigned output directory, and honest access/verification limits.
- Batatis corpus provenance rules: preserve source class, explicit locality, original bytes/hashes/locators when available, and do not infer approvals or technical acceptance.
