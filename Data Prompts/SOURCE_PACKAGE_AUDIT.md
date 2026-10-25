# Supplied package audit

The audit describes the completed local collection. Links to saved PDFs, HTML and worker files refer to that collection; Git contains the URL/hash receipts and reconstructed prompts. See [restoration instructions](README.md#restore-local-attachments).

The DOCX contains 38 external hyperlink relationships pointing to 37 unique targets, with no embedded files. Every unique target was retrieved and its outgoing document links were inventoried. Original DOCX bytes, hyperlink IDs, display labels, source paragraphs and retrieval metadata are preserved under `_source_package/`.

## Download coverage

- Direct package targets: 37 / 37 retrieved (PDFs and landing pages are distinguished below).
- Document URLs exposed by those target landing pages: 273 attempted; 273 downloaded. The obsolete HTTP SCC FAQ link was recovered from its official HTTPS equivalent, with the failed attempt retained.
- CCMC registry: all 462 linked assessment pages and their 462 PDF viewer targets were downloaded. All 462 PDFs passed SHA-256 and page-tree checks (4,904 pages). These are product assessments, not individual building applications.
- Supplemental package audit: H19 retained 66 records, including archive continuations, legislation PDFs, newer printings, rights pages and training/video metadata. See the [38-link detail table](_research/workers/H19/package-audit.md) and [audit report](_research/workers/H19/report.md).
- YouTube webinar: watch/oEmbed metadata and availability checked; video bytes were not downloaded. CSA training requires registration and returned 403; no registered training video was retrieved. Account portals were not accessed.

This is a bounded audit of the supplied links, directly exposed document resources, and the complete registry-linked assessment set. The NRC Publications Archive is a large research repository; the case researchers searched relevant families, and this audit does not claim to have downloaded its entire corpus or every external reference cited inside code books.

## Every unique package target

| ID | Package label | Original target / saved target | Linked file URLs downloaded | Supplemental PDFs |
| --- | --- | --- | ---: | --- |
| PKG-01 | City of Edmonton, Point Access Block Alternative Solution Guide | [original URL](https://www.edmonton.ca/sites/default/files/public-files/Point-Access-Block-Alternative-Solution-Guide.pdf) · [pdf](_source_package/downloads/PKG-01-1546fef63937.pdf) | 0 | — |
| PKG-02 | User’s Guide – NECB 2020 | [original URL](https://nrc-publications.canada.ca/eng/view/object/?id=c6504d98-2da4-43c5-a8f6-360d6e640f88) · [html](_source_package/downloads/PKG-02-f412bcfc1c44.html) | 1 | [H19-NRC-06](_research/workers/H19/files/PKG-02/users-guide-necb-2020-nrc-ft-137d9d31d801.pdf) |
| PKG-03 | NRC Publications Archive | [original URL](https://nrc-publications.canada.ca/) · [html](_source_package/downloads/PKG-03-7b2a728c8352.html) | 0 | — |
| PKG-04 | City of Edmonton, Application Requirements for House Permits | [original URL](https://www.edmonton.ca/residential_neighbourhoods/application-requirements-house-permits) · [html](_source_package/downloads/PKG-04-d8d4f640820b.html) | 65 | — |
| PKG-05 | Challenge Scope; Building Codes Challenge Scope | [original URL](https://edmontonunlimited.com/wp-content/uploads/2026/09/Building-Codes-Challenge-with-Appendix-.pdf) · [pdf](_source_package/downloads/PKG-05-761bf8d9d8e9.pdf) | 0 | [H19-CHAL-01](_research/workers/H19/files/PKG-05/building-codes-challenge-scope-with-appendix-761bf8d9d8e9.pdf) |
| PKG-06 | Safety Codes Council variance form | [original URL](https://ebs.safetycodes.ab.ca/documents/webdocs/PI/Variance%20Template%20final.pdf) · [pdf](_source_package/downloads/PKG-06-f44640ca005c.pdf) | 0 | [H19-SCC-01](_research/workers/H19/files/PKG-06/scc-variance-form-f44640ca005c.pdf) |
| PKG-07 | CCMC Registry of Product Assessments | [original URL](https://nrc.canada.ca/en/certifications-evaluations-standards/canadian-construction-materials-centre/ccmc-publications/registry.html) · [html](_source_package/downloads/PKG-07-0ae68ace736f.html) | 1 | — |
| PKG-08 | Building STANDATA index | [original URL](https://www.alberta.ca/building-standata) · [html](_source_package/downloads/PKG-08-9e6185603ae3.html) | 0 | — |
| PKG-09 | Guideline to the Variance Form | [original URL](https://www.safetycodes.ab.ca/permits-inspections/variances/) · [html](_source_package/downloads/PKG-09-d4e038aef9d2.html) | 5 | — |
| PKG-10 | Exemption Regulation (AR 351/2003) | [original URL](https://open.alberta.ca/publications/2003_351) · [html](_source_package/downloads/PKG-10-428ec8569b42.html) | 0 | [H19-AB-03](_research/workers/H19/files/PKG-10/exemption-regulation-AR351-2003-kings-printer-ab05a6d57f0e.pdf) |
| PKG-11 | Building code variances (2019) | [original URL](https://open.alberta.ca/publications/standata-building-code-variance-national-building-code-2019-alberta-edition) · [html](_source_package/downloads/PKG-11-5e97b02f898c.html) | 33 | — |
| PKG-12 | Building code variances (2023) | [original URL](https://open.alberta.ca/publications/standata-variance-building-national-building-code-2023-alberta-edition) · [html](_source_package/downloads/PKG-12-7def4008df5d.html) | 19 | — |
| PKG-13 | Building code interpretations (2023) | [original URL](https://open.alberta.ca/publications/standata-interpretation-building-national-building-code-2023-alberta-edition) · [html](_source_package/downloads/PKG-13-b2eb65af616c.html) | 40 | — |
| PKG-14 | Building code variances (2014) | [original URL](https://open.alberta.ca/publications/standata-building-code-variance-2014) · [html](_source_package/downloads/PKG-14-2d783dd0e72a.html) | 23 | — |
| PKG-15 | Building code bulletins (2023) | [original URL](https://open.alberta.ca/publications/standata-bulletin-building-national-building-code-2023-alberta-edition) · [html](_source_package/downloads/PKG-15-bbb54adf73cd.html) | 11 | — |
| PKG-16 | Safety Codes Act | [original URL](https://www.qp.alberta.ca/documents/Acts/S01.pdf) · [pdf](_source_package/downloads/PKG-16-3a1a442fc668.pdf) | 0 | [H19-AB-01](_research/workers/H19/files/PKG-16/safety-codes-act-S01-3a1a442fc668.pdf) |
| PKG-17 | Building Code Regulation (AR 5/2024) | [original URL](https://open.alberta.ca/publications/2024_005) · [html](_source_package/downloads/PKG-17-8a73c50fd515.html) | 0 | [H19-AB-02](_research/workers/H19/files/PKG-17/building-code-regulation-AR5-2024-kings-printer-ea2a1921c325.pdf) |
| PKG-18 | NECB 2020 navigation training | [original URL](https://sustainablewaterlooregion.ca/frameworks/resources/national-energy-code-of-canada-for-buildings-necb-2020-online-training-navigating-and-applying-the-code-2/) · [html](_source_package/downloads/PKG-18-9df315537218.html) | 0 | — |
| PKG-19 | Building code errata (2023) | [original URL](https://open.alberta.ca/publications/standata-errata-building-national-building-code-2023-alberta-edition) · [html](_source_package/downloads/PKG-19-939a368090f1.html) | 1 | — |
| PKG-20 | National Building Code – 2023 Alberta Edition, 2nd printing | [original URL](https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en) · [pdf](_source_package/downloads/PKG-20-3d45376d6c71.pdf) | 0 | [H19-AB-05](_research/workers/H19/files/PKG-20/nbc-2023-alberta-edition-2nd-printing-nrc-ft-3d45376d6c71.pdf) |
| PKG-21 | NRC, Canada's objective-based codes | [original URL](https://nrc-publications.canada.ca/eng/view/accepted/?id=ad81d6f2-e76c-4eff-a428-de7e001d3527) · [pdf](_source_package/downloads/PKG-21-9397834f3671.pdf) | 0 | [H19-NRC-07](_research/workers/H19/files/PKG-21/nrc-canadas-objective-based-codes-accepted-9397834f3671.pdf) |
| PKG-22 | Permit Regulation (AR 204/2007) | [original URL](https://open.alberta.ca/publications/2007_204) · [html](_source_package/downloads/PKG-22-10aed091b379.html) | 0 | [H19-AB-04](_research/workers/H19/files/PKG-22/permit-regulation-AR204-2007-kings-printer-b162b9a15dfc.pdf) |
| PKG-23 | FNNBOA webinar on navigating the National Building Code | [original URL](https://m.youtube.com/watch?v=jhN7isNfgoE) · [html](_source_package/downloads/PKG-23-26dc1e0af7e0.html) | 0 | — |
| PKG-24 | National Energy Code of Canada for Buildings 2020, 2nd printing | [original URL](https://nrc-publications.canada.ca/eng/view/ft/?id=af36747e-3eee-4024-a1b4-73833555c7fa&dp=2&dsl=en) · [pdf](_source_package/downloads/PKG-24-5f28b6f83f9a.pdf) | 0 | [H19-AB-11](_research/workers/H19/files/PKG-24/necb-2020-2nd-printing-nrc-ft-5f28b6f83f9a.pdf) |
| PKG-25 | Canadian Wood Council, Alternative Solutions Guide (2025) | [original URL](https://cwc.ca/wp-content/uploads/2025/04/CWC-ASG-April2-2.pdf) · [pdf](_source_package/downloads/PKG-25-38b185cc7923.pdf) | 0 | — |
| PKG-26 | Supplement to the NBC 2020: Intent Statements | [original URL](https://nrc-publications.canada.ca/eng/view/object/?id=de0e0ec9-a452-4337-bc84-002a230c9d66) · [html](_source_package/downloads/PKG-26-6b8611a2cf6d.html) | 1 | [H19-NRC-01](_research/workers/H19/files/PKG-26/nbc-2020-intent-statements-supplement-nrc-ft-a75ef52eff6f.pdf) |
| PKG-27 | NRC, Accepting alternate solutions under objective-based codes | [original URL](https://nrc-publications.canada.ca/eng/view/accepted/?id=e5e9e318-6e0f-4fd8-b2a4-0a7d502168bc) · [pdf](_source_package/downloads/PKG-27-fc5301df7095.pdf) | 0 | [H19-NRC-08](_research/workers/H19/files/PKG-27/nrc-accepting-alternate-solutions-objective-based-accepted-fc5301df7095.pdf) |
| PKG-28 | National Fire Code – 2023 Alberta Edition | [original URL](https://publications.gc.ca/collections/collection_2024/cnrc-nrc/NR24-27-2-2023-eng.pdf) · [html](_source_package/downloads/PKG-28-4dfe9798b366.html) | 0 | [H19-AB-07](_research/workers/H19/files/PKG-28/nfc-2023-alberta-edition-NR24-27-8d6333c4ed23.pdf) |
| PKG-29 | City of Calgary, Guide to Applying for an Alternative Solution (Variance) | [original URL](https://www.calgary.ca/content/dam/www/tools-and-resources/guide-to-applying-for-an-alternative-solution.pdf) · [pdf](_source_package/downloads/PKG-29-bbb0628b7b5f.pdf) | 0 | — |
| PKG-30 | Supplement to NEBC 2020: Intent Statements | [original URL](https://nrc-publications.canada.ca/eng/view/ft/?id=b31a0620-ee88-4e32-bf62-c40f0b6e8f73) · [pdf](_source_package/downloads/PKG-30-104d37f1a673.pdf) | 0 | [H19-NRC-02](_research/workers/H19/files/PKG-30/necb-2020-intent-supplement-nrc-ft-104d37f1a673.pdf) |
| PKG-31 | Single Stair Canada | [original URL](https://singlestair.ca/) · [html](_source_package/downloads/PKG-31-261faa03d7d5.html) | 0 | — |
| PKG-32 | National Plumbing Code of Canada (NPC) 2020 | [original URL](https://publications.gc.ca/collections/collection_2022/cnrc-nrc/NR24-29-2020-eng.pdf) · [html](_source_package/downloads/PKG-32-4e05ddd3e72d.html) | 0 | [H19-AB-09](_research/workers/H19/files/PKG-32/npc-2020-NR24-29-64180d9de6dd.pdf) |
| PKG-33 | City of Edmonton, Guideline for Alternative Solutions Affecting Emergency Services | [original URL](https://www.edmonton.ca/sites/default/files/public-files/COE-IM-GUIDE-0040-v01-20250415%20Guideline%20for%20Alternative%20Solutions%20Affecting%20Emergency%20Services.pdf) · [pdf](_source_package/downloads/PKG-33-1d57547972e4.pdf) | 0 | [H19-EDM-01](_research/workers/H19/files/PKG-33/edmonton-guideline-alt-solutions-emergency-services-1d57547972e4.pdf) |
| PKG-34 | Supplement to NFC: Intent Statements | [original URL](https://nrc-publications.canada.ca/eng/view/object/?id=c76b4965-74c1-4581-8fba-423aad79104e) · [html](_source_package/downloads/PKG-34-6f49ee12c3d7.html) | 1 | [H19-NRC-03](_research/workers/H19/files/PKG-34/nfc-2020-intent-statements-supplement-nrc-ft-79dcade3c2a7.pdf) |
| PKG-35 | City of Calgary, building advisories, bulletins and Standing Posted Variances | [original URL](https://www.calgary.ca/development/permits/building-regulation-advisories.html) · [html](_source_package/downloads/PKG-35-c291b5e601bf.html) | 71 | — |
| PKG-36 | Illustrated User's Guide, NBC 2020 Part 9 | [original URL](https://nrc-publications.canada.ca/eng/view/ft/?id=a7a505fa-519c-436b-a23b-6f418df87e6a) · [pdf](_source_package/downloads/PKG-36-eec6f3f394bf.pdf) | 0 | [H19-NRC-05](_research/workers/H19/files/PKG-36/illustrated-users-guide-nbc-2020-part9-nrc-ft-eec6f3f394bf.pdf) |
| PKG-37 | Supplement to NPC Intent Statements | [original URL](https://nrc-publications.canada.ca/eng/view/object/?id=17608c17-51a4-4c4f-8baa-b5b18ca60d2b) · [html](_source_package/downloads/PKG-37-6ce5351efc93.html) | 1 | [H19-NRC-04](_research/workers/H19/files/PKG-37/npc-2020-intent-statements-supplement-nrc-ft-2728f7cf0f8b.pdf) |

## Edition and source distinctions

The package's NBC(AE) 2023 and NECB 2020 downloads are second printings. The supplied NFC(AE) 2023 and NPC 2020 PDF URLs resolve through archive notices to first printings; both original first printings were recovered using the archive notice's own Continue link. Official second printings were also retained and separately labeled by H19. They were not silently substituted for the original package files.

The linked intent-statement supplements identify 2020 code editions. No matching 2023 Alberta supplement was located in the bounded search. Do not infer current-edition equivalence from a title or matching article number.

STANDATA, Calgary standing posted variances and Edmonton policy/design documents are regulator references or published illustrative designs. They are not confidential applicant files. The PAB overview is eight pages; its companion design guide supplies examples A–M. The three expanded studies correspond to existing catalogue examples and were not counted twice.

The SCC page linked as Guideline to the Variance Form did not expose a document with that exact title. The actual available form, documentation bulletins, refusal template, FAQs and notices were retained as general references.

## Access and reuse limits

Blocked and unvisited source attempts remain in [source_gaps.json](source_gaps.json) and individual worker reports. Search snippets, permit-register entries and empty/error responses were not substituted for original technical case attachments. Calgary and Edmonton agenda attachment hosts returned 403 in the attempted clients; the local reports record the strongest unverified leads. Calgary DMap reuse terms and property-record access restrictions are preserved in the A02 report.

The [NRC archive terms](https://nrc-publications.canada.ca/eng/copyright/) restrict the viewing licence to personal noncommercial use and state that systematic downloading is not permitted. Source downloads are retained locally for the requested research audit; permission for product use, redistribution, model training or benchmark redistribution has not been established. NRC archive attachments are marked `rights_review_required` in case metadata. This is not a blanket licensed training dataset. CCMC and other publishers' rights must be considered under their own terms; the archive terms are not automatically attributed to every Canadian government source.

## Machine-readable evidence

- `_source_package/links.json` and `link_audit.json`: exact unique targets, relationships, document labels and page/file receipts.
- `_source_package/resource_audit.json`: all 273 exposed document URL attempts and the SCC HTTPS recovery.
- `_source_package/ccmc_document_audit.json` and `ccmc_pdf_audit.json`: all registry assessment pages and actual PDF viewer URLs.
- `_source_package/file_validation.json` and `ccmc_file_validation.json`: original-byte hashes and PDF readability checks.
- `_research/workers/H19/candidates.json`: detailed edition, reference, rights and access records for the package audit slice.
