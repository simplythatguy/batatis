# Canadian (non-Alberta) and product precedents for the code-identification benchmark

Prepared 2026-10-23 for the Elephant accuracy work. Companion file: `cases-canada.json` (62 cases). Every citation is mapped to NBC(AE) 2023, 2nd printing, Division B by reading the article text in the local code database. Validator: `.venv/bin/python -m evals_dev.identify_bench.validate_web_cases docs/research/2026-10-23-elephant/cases-canada.json` prints `62 cases, 0 problems`.

## 1. Summary

- 62 cases, 190 gold article slots over 151 distinct Division B articles (median 2 per case, largest 47).
- Source groups: BC Building Code Appeal Board 28; CCMC evaluation 25; BC Building Code Interpretation Committee 7; Saskatchewan 2.
- By `type`: appeal 28; product-evaluation 25; interpretation 9. No case uses `alternative-solution-example`: no public worked example of an alternative solution with article-level citations was found (see section 5.4). The BC appeals that concern an alternative solution (1852, 1911, 1930, 1976, 1985) are typed `appeal`.
- By applicant: manufacturer 25; homeowner 12; owner-developer 10; homebuilder 7; designer 7; contractor 1.
- By confidence: high 45; medium 17. Medium means the mapping needed a renumbering argument, the source wording differs in places from the 2023 text, or the source lists only subsection-level rows and I used the articles its body names.
- Parts touched by gold (cases with at least one gold article in the Part): Part 3: 11; Part 4: 4; Part 5: 3; Part 6: 1; Part 9: 52.

| Topic | Cases |
|---|---|
| Envelope: moisture, air, insulation, cladding, roofing | 18 |
| Fire protection and spatial separation (Part 9) | 12 |
| Structure and framing materials (Part 9 with Part 4 references) | 10 |
| Part 3 fire safety, egress and combustible construction | 9 |
| Egress, stairs, guards and windows (Part 9) | 6 |
| Foundations, drainage and soil gas | 4 |
| Ventilation, alarms and secondary suites (Part 9) | 3 |

Secondary-suite cases (cross-cutting): ca-bcab-1942, ca-bcab-1887, ca-bcab-1954, ca-sk-advisory-secondary-suite-checklist. BC secondary-suite provisions differ from NBC(AE) 2023 in several places, so only decisions whose cited text matches the 2023 text were kept (section 6).

## 2. How to read the JSON

- `gold` holds Division B articles that the source itself says the proposal varies from, is evaluated against, or must address. A cited sentence, clause or table maps to its article. Nothing was added from my own judgment.
- CCMC evaluations: each report has a compliance-opinion table that marks every provision `Acceptable` or `Alternative`. `Alternative` rows at article or sentence level are gold (the report says the product departs from that acceptable solution). `Acceptable` rows, and articles the report body cites in its conditions, are `context`. Rows at subsection or section level (for example "9.23.10. Wall Studs") were not turned into articles. One exception: the structural insulated panel report (13016-R) lists only subsections in its table but its scope text names the articles it is an alternative to, so those articles are gold with medium confidence.
- BC appeals and interpretations: gold is the Division B article list the decision cites as applicable ("Applicable Code requirements") or the interpretation cites and discusses ("Building Code Reference(s)" plus the answer). An article that only appears in an interpretation's reference list but is never discussed in its answer is `context` (24-0096, 24-0122, 24-0144), and related articles named only in the reasoning are `context` too. Division A and Division C citations (for example the alternative-solution compliance sentences) are not articles in the database and were dropped.
- `mapping.as_cited` keeps the source number and edition; `mapping.verification` quotes at most 20 words of the 2023 article text (the build asserted that each quote is a substring of the database text). Renumbered successors say so and give the evidence.
- `source.excerpt` is now a short locating anchor (at most 15 source words), abridged during parent integration. Earlier draft assertions of a continuous verbatim excerpt do not apply to spliced table/narrative anchors; consult the original source.
- `description` is written in the applicant voice from source facts only and contains no code numbers. For manufacturers the applicant is the product maker.
- Dates are the source publication or last-modified month (CCMC: last modified; first-issue month is in `notes` where relevant).
- The Saskatchewan secondary-suite case has 47 gold articles, one source checklist. Score it separately from small-gold cases.

## 3. Case index

| # | id | Source | Type | Applicant | Gold | Conf. |
|---|---|---|---|---|---|---|
| 1 | ca-ccmc-dimpled-foundation-dampproofing | CCMC 12266-R: Platon Foundation Wrap; NBC 2020 | product-evaluation | manufacturer | 9.13.2.2. | high |
| 2 | ca-ccmc-rigid-board-radon-barrier | CCMC 14349-R: FOAMULAR NGX RadonBARRIER Radon Abatement System; NBC 2020 | product-evaluation | manufacturer | 9.13.4.2., 9.25.3.6. | high |
| 3 | ca-ccmc-xps-air-barrier-system | CCMC 12935-R: FOAMULAR NGX CodeBord Air Barrier System; NBC 2020 | product-evaluation | manufacturer | 9.25.3.2. | high |
| 4 | ca-ccmc-sheathing-tape-joints | CCMC 11362-R: 3M Construction Sheathing Tape 8088; NBC 2020 (also NBC 2015) | product-evaluation | manufacturer | 9.27.3.3. | high |
| 5 | ca-ccmc-eps-sheathing-integral-membrane | CCMC 13488-R: AiRclad (Sheathing Membrane / Insulation Board); NBC 2020 (also NBC 2015) | product-evaluation | manufacturer | 9.27.3.2. | high |
| 6 | ca-ccmc-intumescent-thermal-barrier-over-spf | CCMC 14036-R: DC315; NBC 2020 (also NBC 2015) | product-evaluation | manufacturer | 3.1.4.2., 3.1.5.15., 9.10.17.10., 9.25.2.3., 9.29.5.2. | high |
| 7 | ca-ccmc-pmdi-binder-osb-panels | CCMC 14072-R: WANNATE PM-200 (pMDI binder for OSB); NBC 2020 (also NBC 2015) | product-evaluation | manufacturer | 9.23.15.2., 9.23.16.2., 9.23.17.2., 9.27.10.1., 9.29.9.1., 9.30.2.2. | high |
| 8 | ca-ccmc-open-cell-spf-insulation | CCMC 14138-R: Duka Open Cell SPF; NBC 2020 (also NBC 2015) | product-evaluation | manufacturer | 9.25.2.2. | high |
| 9 | ca-ccmc-closed-cell-spf-single-pass | CCMC 14230-R: WALLTITE XL01; NBC 2020 (also NBC 2015) | product-evaluation | manufacturer | 5.9.1.1., 9.25.2.5. | high |
| 10 | ca-ccmc-reflective-eps-board-foundation-wall | CCMC 13459-R: EZfoil (EPS board with low-E facer); NBC 2020 (also NBC 2015) | product-evaluation | manufacturer | 9.25.2.2., 9.25.4.2., 9.36.2.2., 9.36.2.8. | medium |
| 11 | ca-ccmc-insulated-polymer-cladding | CCMC 14182-R: ALIGN Composite Cladding 7 in. Plank; NBC 2020 | product-evaluation | manufacturer | 9.27.12.1. | high |
| 12 | ca-ccmc-clip-fastened-composite-siding | CCMC 14734-R: UH61 Fluted Wall Panels; NBC 2020 | product-evaluation | manufacturer | 9.27.5.4., 9.27.12.1. | medium |
| 13 | ca-ccmc-pvc-footing-form-and-drain | CCMC 13492-R: Form-A-Drain; NBC 2020 | product-evaluation | manufacturer | 4.1.1.3., 9.14.3.1., 9.14.3.2., 9.14.3.3. | high |
| 14 | ca-ccmc-vented-plastic-sill-plate | CCMC 14229-R: Vented sill plate (TEK-BASE); NBC 2020 (also NBC 2015) | product-evaluation | manufacturer | 9.23.2.3., 9.30.1.3. | high |
| 15 | ca-ccmc-composite-decking-and-stair-treads | CCMC 13125-R: Trex wood-plastic composite decking; NBC 2020 (also NBC 2015) | product-evaluation | manufacturer | 9.3.2.9., 9.4.2.3., 9.4.3.1., 9.8.9.1., 9.23.15.5. | high |
| 16 | ca-ccmc-laminated-strand-lumber | CCMC 12627-R: TimberStrand LSL; NBC 2015 | product-evaluation | manufacturer | 9.23.2.2., 9.23.4.2., 9.23.10.1. | high |
| 17 | ca-ccmc-wood-i-joist-floors-houses | CCMC 13032-R: Nordic I-Joist Series; NBC 2020 (also NBC 2015) | product-evaluation | manufacturer | 9.10.8.10., 9.23.4.2. | high |
| 18 | ca-ccmc-steel-joist-hangers | CCMC 13287-R: Face-mount joist hangers (Credit Valley Steel Products); NBC 2015 | product-evaluation | manufacturer | 4.3.1.1., 9.23.3.4., 9.23.9.2. | medium |
| 19 | ca-ccmc-self-tapping-structural-screws | CCMC 13677-R: SWG ASSY self-tapping wood screws; NBC 2015 | product-evaluation | manufacturer | 4.3.1.1., 9.23.3.1. | high |
| 20 | ca-ccmc-helical-steel-piles-small-buildings | CCMC 14027-R: Roterra auger-installed steel piles; NBC 2015 | product-evaluation | manufacturer | 4.2.3.8. | medium |
| 21 | ca-ccmc-cement-free-concrete-block | CCMC 14346-R: CarbiCrete Concrete Masonry Unit; NBC 2015 | product-evaluation | manufacturer | 5.8.1.4., 9.15.2.2., 9.20.2.1. | medium |
| 22 | ca-ccmc-structural-insulated-panels | CCMC 13016-R: Insulspan Structural Insulated Panel (SIP) System; NBC 2015 (also NBC 2010) | product-evaluation | manufacturer | 9.4.1.1., 9.23.10.1., 9.23.4.2. | medium |
| 23 | ca-ccmc-pex-piping-noncombustible-buildings | CCMC 13529-R: AquaPEX cross-linked polyethylene piping (Uponor); NBC 2015 | product-evaluation | manufacturer | 3.1.5.19., 3.1.9.1., 3.1.9.4., 3.1.12.1., 3.2.5.13., 3.6.4.3. | medium |
| 24 | ca-ccmc-ductwrap-fire-rated-grease-duct | CCMC 14382-R: CL4FIRE Code-96 Grease Duct Insulation System; NBC 2020 (also NBC 2015) | product-evaluation | manufacturer | 3.1.7.1. | medium |
| 25 | ca-ccmc-liquid-applied-deck-membrane | CCMC 13473-R: FlexStone cold liquid-applied polyurethane deck membrane; NBC 2015 | product-evaluation | manufacturer | 9.26.2.1. | medium |
| 26 | ca-bcab-1976-sip-fire-rating-alt-solution | BCAB 1976: Alternative solution regarding the fire-resistance rating of structural insulated panels; BCBC 2024 | appeal | owner-developer | 9.10.3.1. | high |
| 27 | ca-bcab-1945-open-cell-foam-insulation | BCAB 1945: Insulation material, acceptable or alternative solution; BCBC 2024 | appeal | homebuilder | 9.25.2.2. | high |
| 28 | ca-bcab-1852-mezzanine-enclosed-second-level | BCAB 1852: Alternative solution to Sentences 3.2.1.1.(3) and (4); BCBC 2018 | appeal | owner-developer | 3.2.1.1. | medium |
| 29 | ca-bcab-1911-spatial-separation-combined-buildings | BCAB 1911: Alternative solution to address spatial separation requirements; BCBC 2018 | appeal | owner-developer | 3.2.3.1., 3.2.3.7., 3.2.3.14. | high |
| 30 | ca-bcab-1930-combustible-high-building-alt-solution | BCAB 1930: Alternative solution to address combustible construction and high building measures; BCBC 2024 | appeal | owner-developer | 3.2.2.47., 3.2.6.1. | high |
| 31 | ca-bcab-1985-fire-block-metal-cladding-cavity | BCAB 1985: Requirement for fire blocks in an exterior wall assembly; BCBC 2024 | appeal | homebuilder | 9.10.16.2. | high |
| 32 | ca-bcab-1965-membrane-tape-flashing-detail | BCAB 1965: Requirements for the installation of flashing; BCBC 2024 | appeal | homebuilder | 9.27.3.8., 5.6.1.2., 9.27.1.1. | high |
| 33 | ca-bcab-1990-landing-headroom-variance-request | BCAB 1990: Clear height over landing, step from landing to floor; BCBC 2024 | appeal | homeowner | 9.8.6.4., 9.8.6.2., 9.8.4.1., 9.8.3.2. | high |
| 34 | ca-bcab-1942-limiting-distance-window-secondary-suite | BCAB 1942: Actual and effective limiting distances, and fire department response; BCBC 2024 | appeal | homeowner | 9.10.15.3., 9.10.15.4., 3.2.3.1. | high |
| 35 | ca-bcab-1869-garden-cottage-next-to-garage | BCAB 1869: Applicable Code requirements for spatial separation, subsections 9.10.14. and 9.10.15.; BCBC 2018 | appeal | homeowner | 9.10.14.1., 9.10.15.1. | medium |
| 36 | ca-bcab-1948-detached-multi-suite-garage | BCAB 1948: Spatial separation requirements for a detached multi-suite garage; BCBC 2024 | appeal | owner-developer | 9.10.2.1., 9.10.14.1., 9.10.15.1. | high |
| 37 | ca-bcab-1999-combustible-roof-overhang-townhouse | BCAB 1999: Roof overhangs above a wall of a townhouse facing a property line; BCBC 2024 | appeal | owner-developer | 9.10.15.5. | high |
| 38 | ca-bcab-1981-open-rv-shelter-spatial-separation | BCAB 1981: Spatial separation requirements for an RV shelter; BCBC 2024 | appeal | owner-developer | 9.10.14.2., 9.10.14.4., 9.10.14.5. | high |
| 39 | ca-bcab-1887-secondary-suite-separation-attic | BCAB 1887: Continuity of required fire separation for a secondary suite; BCBC 2018 | appeal | homebuilder | 9.10.9.12., 9.10.5.1. | medium |
| 40 | ca-bcab-2006-rooftop-deck-privacy-screen-rowhouse | BCAB 2006: Fire separation of residential roof-top decks; BCBC 2024 | appeal | owner-developer | 9.10.9.1., 9.10.9.16., 9.10.11.2. | high |
| 41 | ca-bcab-1954-egress-balcony-secondary-suite-alteration | BCAB 1954: Means of egress from a house with a secondary suite; BCBC 2024 | appeal | homeowner | 9.9.9.1., 9.9.9.2. | medium |
| 42 | ca-bcab-1940-window-opening-control-device-egress | BCAB 1940: Restrictions on window openings and requirements for egress windows; BCBC 2018 | appeal | homeowner | 9.8.8.1., 9.9.10.1. | medium |
| 43 | ca-bcab-1936-stair-width-inset-wall | BCAB 1936: Required width of stair below handrails; BCBC 2018 | appeal | homeowner | 9.8.2.1., 9.8.7.6. | high |
| 44 | ca-bcab-1859-climbable-guard-return-privacy-screen | BCAB 1859: Climbability of guards; BCBC 2018 | appeal | designer | 9.8.8.6. | high |
| 45 | ca-bcab-2002-loft-in-vaulted-unit | BCAB 2002: Loft access and ceiling height, and definition of storey; BCBC 2024 | appeal | homeowner | 9.5.3.1., 9.8.2.1. | high |
| 46 | ca-bcab-1849-vapour-barrier-paint-over-spray-foam | BCAB 1849: Vapour barrier paint applied to spray applied polyurethane insulation; BCBC 2018 | appeal | homebuilder | 9.25.4.2. | high |
| 47 | ca-bcab-1950-attic-rec-room-foam-walls-unfinished | BCAB 1950: Protection of foamed plastic insulation and protection from mechanical damage; BCBC 2024 | appeal | homebuilder | 9.10.17.10., 9.25.2.3. | high |
| 48 | ca-bcab-2000-interior-foundation-drain-stepped-slab | BCAB 2000: Foundation wall drainage at interior locations; BCBC 2024 | appeal | homebuilder | 9.14.2.1., 9.14.3.3., 9.16.3.1. | high |
| 49 | ca-bcab-1854-deck-membrane-treated-as-roofing | BCAB 1854: Deck surface material; BCBC 2018 | appeal | homeowner | 9.26.1.1., 9.26.1.2. | high |
| 50 | ca-bcab-1855-vaulted-ceiling-roof-venting-baffles | BCAB 1855: Roof space ventilation; BCBC 2018 | appeal | homeowner | 9.19.1.1., 9.19.1.3. | high |
| 51 | ca-bcab-1920-recirculating-kitchen-hood-airtight-home | BCAB 1920: Kitchen ventilation in a home with high energy efficiency; BCBC 2018 | appeal | homeowner | 9.32.3.7., 9.32.3.11. | medium |
| 52 | ca-bcab-1897-exterior-passageway-alcove-suite-door | BCAB 1897: Egress from residential suite to exterior passageway; BCBC 2018 | appeal | owner-developer | 3.3.1.3., 3.3.1.9. | high |
| 53 | ca-bcab-1929-concealed-combustible-pipe-noncombustible-building | BCAB 1929: Concealment of combustible water piping in a building of noncombustible construction; BCBC 2018 | appeal | contractor | 3.1.5.19. | high |
| 54 | ca-bcic-24-0096-detached-garage-and-carport-spacing | BC Building Code Interpretation 24-0096: Spatial separation for accessory buildings; BCBC 2024 | interpretation | homeowner | 9.10.14.1., 9.10.14.4., 9.10.14.5., 9.10.15.1., 9.10.15.4., 9.10.15.5. | high |
| 55 | ca-bcic-24-0080-crawl-space-insulation-protection | BC Building Code Interpretation 24-0080: Protection of insulation in crawl spaces; BCBC 2024 | interpretation | designer | 9.10.8.9., 9.25.2.3. | high |
| 56 | ca-bcic-24-0181-furring-fasteners-through-exterior-insulation | BC Building Code Interpretation 24-0181: Furring fasteners through exterior insulation; BCBC 2024 | interpretation | designer | 9.27.2.2., 9.27.5.3., 9.27.5.4., 9.27.5.7. | high |
| 57 | ca-bcic-24-0122-foam-plastic-inside-concrete-wall | BC Building Code Interpretation 24-0122: Foamed plastic insulation on the inside face of a concrete wall; BCBC 2024 | interpretation | designer | 3.2.3.8., 3.1.5.5. | high |
| 58 | ca-bcic-24-0123-combustible-ceiling-finish-test-method | BC Building Code Interpretation 24-0123: Ceiling products tested to CAN/ULC S102.2; BCBC 2024 | interpretation | designer | 3.1.5.12., 3.1.12.1. | high |
| 59 | ca-bcic-24-0120-heated-crawlspace-ground-cover-joints | BC Building Code Interpretation 24-0120: Heated crawlspace vapour barrier; BCBC 2024 | interpretation | designer | 9.18.6.2., 9.25.3.3., 9.25.3.6. | high |
| 60 | ca-bcic-24-0144-vertical-cladding-horizontal-furring | BC Building Code Interpretation 24-0144: Vertical exterior cladding with horizontal furring; BCBC 2024 | interpretation | designer | 9.27.2.2., 9.27.2.3. | high |
| 61 | ca-sk-ministerial-interpretation-co-detectors-in-lieu-of-alarms | Ministerial Interpretation NBC 2020-004: Carbon Monoxide (CO) Detectors Installed in Lieu of CO Alarms; NBC 2020 (with Saskatchewan amendments) | interpretation | owner-developer | 9.32.3.9., 6.9.3.1. | medium |
| 62 | ca-sk-advisory-secondary-suite-checklist | Construction Codes Advisory: Secondary Suites (how the NBC 2020 applies to secondary suites); NBC 2020 | interpretation | homeowner | 47 articles (checklist) | medium |

## 4. Sources consulted

All fetched 2026-10-23.

CCMC, National Research Council Canada (primary):
- Registry JSON, 462 entries (250 evaluation reports `-R`, 212 listings `-L`): https://nrc.canada.ca/en/certifications-evaluations-standards/canadian-construction-materials-centre/ccmc-publications/published_evaluations.html
- Report pages (all 462 downloaded; the 250 `-R` reports parsed for their compliance tables): https://nrc.canada.ca/en/certifications-evaluations-standards/canadian-construction-materials-centre/ccmc-publications/document.html?id=NNNNN-R&type=cert
- BTRboard, the example named in the brief, is not in the live registry (no entry with that name); a web search found no CCMC number for it.

British Columbia (code editions BCBC 2018 and 2024):
- Building Code Appeal Board decisions index: https://www2.gov.bc.ca/gov/content/industry/construction-industry/building-codes-standards/building-code-appeal-board/building-code-appeal-board-decisions (266 decision pages from 1700 to 2007 downloaded: `.../building-code-appeal-board-decisions/bcab-NNNN`).
- BC Building Code Interpretation Committee, 2024 interpretation index (141 entries) hosted by the Building Officials' Association of BC: https://boabc.org/building-and-plumbing-code-interpretations-2024/ (PDFs under https://boabc.org/wp-content/uploads/). Entry point: https://www2.gov.bc.ca/gov/content/industry/construction-industry/building-codes-standards/bc-codes/code-interpretations
- Municipal alternative-solution guides, read for worked examples (none found): Burnaby https://www.burnaby.ca/sites/default/files/acquiadam/2021-08/Alternative-Solutions-Informational-Guide.pdf ; Coquitlam https://coquitlam.ca/DocumentCenter/View/4122/Alternative-Solutions-Guide-PDF ; Saanich https://www.saanich.ca/assets/Local~Government/Documents/Inspections/Alternative%20Solutions%20-%20Bulletin.pdf

Saskatchewan (NBC 2020 adopted 2024-01-01):
- Ministerial interpretations list: https://www.saskatchewan.ca/business/housing-development-construction-and-property-management/building-and-technical-standards/national-building-and-fire-code-information (NBC 2020-003, NBC 2020-004 and NPC 2020-001 downloaded).
- Publications Centre advisories (24 listed; 7 downloaded): https://publications.saskatchewan.ca/#/categories/746
- Appeal Board scope page (alternative solutions are not appealable; no published decisions): https://saskatchewan.ca/business/housing-development-construction-and-property-management/building-and-technical-standards/saskatchewan-building-and-accessibility-standards-appeal-board

Other jurisdictions checked:
- Manitoba permit dispute decisions (one decision): https://gov.mb.ca/labour/its/building_codes/decisions.html and https://www.gov.mb.ca/asset_library/en/labour/docs/its/180-provencher-blvd.pdf
- Ontario BMEC authorizations (list only): https://www.ontario.ca/page/building-materials-evaluation-commission-decisions ; Building Code Commission decisions are on CanLII, which blocks automated access: https://www.canlii.org/en/on/onbcc/
- Nova Scotia, New Brunswick, Prince Edward Island, Newfoundland and Labrador, Yukon, Northwest Territories, Nunavut: web searches only; no public decision or interpretation database found (details in section 5.4).

## 5. Excluded candidates and reasons

### 5.1 CCMC (250 evaluation reports, 212 listings)

Used: 25 reports, one case each. Everything else, with reasons:

- Listings (`-L`, 212): a listing records that a product meets a standard; it has no compliance-opinion table against NBC provisions, so there is no gold. Not used.
- Evaluation reports with no compliance-opinion table (older page format, 15): 12718-R, 12788-R, 12878-R, 13098-R, 13182-R, 13209-R, 13212-R, 13315-R, 13323-R, 13387-R, 13579-R, 13634-R, 13674-R, 14053-R, 14410-R. Not used.
- Reports whose table has only `Acceptable` rows (37): 06292-R, 12307-R, 12344-R, 12416-R, 12419-R, 12420-R, 12835-R, 12913-R, 12969-R, 13059-R, 13092-R, 13102-R, 13103-R, 13232-R, 13240-R, 13268-R, 13272-R, 13310-R, 13353-R, 13354-R, 13422-R, 13475-R, 13608-R, 13640-R, 13675-R, 13687-R, 13691-R, 14005-R, 14006-R, 14065-R, 14098-R, 14122-R, 14123-R, 14129-R, 14390-R, 14791-R, 14827-R. These are conformity evaluations without a departure, so they are not variance situations. Not used.
- Reports whose `Alternative` rows are all at subsection or section level (29): 10241-R, 10475-R, 12678-R, 12839-R, 13134-R, 13309-R, 13380-R, 13420-R, 13429-R, 13534-R, 13544-R, 13551-R, 13606-R, 13628-R, 13635-R, 13645-R, 14030-R, 14043-R, 14045-R, 14094-R, 14112-R, 14113-R, 14145-R, 14171-R, 14173-R, 14174-R, 14307-R, 14366-R, 14783-R. Reducing a subsection to articles would be my judgment, so they are not used (13016-R is used because its body names the articles; 13134-R, a vinyl deck membrane, was replaced by 13473-R, whose table names the roofing-material table).
- Reports with article- or sentence-level `Alternative` rows that are not used because another report with the same departure is already a case (same article set):

| Same-departure group | Reports not used | Represented by |
|---|---|---|
| 9.27.3.2. (sheathing membrane standard) | 12264-R, 12808-R, 12892-R, 13119-R, 13230-R, 13280-R, 13286-R, 13292-R, 13294-R, 13424-R, 13426-R, 13510-R, 13549-R, 13647-R, 14071-R, 14106-R, 14117-R, 14124-R, 14148-R, 14201-R, 14411-R, 14510-R, 14575-R, 14584-R, 14982-R | ca-ccmc-eps-sheathing-integral-membrane (13488-R) |
| 9.25.3.2. (air barrier materials) | 12857-R, 12884-R, 13231-R, 13253-R, 13289-R, 13298-R, 13329-R, 13490-R, 13519-R, 13565-R, 13617-R, 14096-R, 14099-R, 14143-R, 14241-R, 14461-R, 14524-R, 14820-R | ca-ccmc-xps-air-barrier-system (12935-R) |
| 9.23.4.2. only (LVL, PSL, LSL spans) | 08675-R, 11161-R, 11518-R, 12472-R, 12904-R, 13006-R, 13474-R, 13485-R, 13507-R, 13543-R, 14476-R, 14935-R | ca-ccmc-laminated-strand-lumber (12627-R, richest set) |
| 9.10.8.10. and 9.23.4.2. (I-joists, trusses) | 12412-R, 12691-R, 12787-R, 13053-R, 13132-R, 13300-R, 13487-R, 14001-R, 14146-R, 14508-R | ca-ccmc-wood-i-joist-floors-houses (13032-R) |
| 5.9.1.1. and 9.25.2.5. (spray foam) | 12070-R, 13655-R, 14128-R, 14367-R, 14444-R | ca-ccmc-closed-cell-spf-single-pass (14230-R) |
| 9.13.2.2. (dampproofing materials) | 12658-R, 13099-R, 13169-R, 13673-R, 14472-R | ca-ccmc-dimpled-foundation-dampproofing (12266-R) |
| Deck and stair loads set (9.3.2.9., 9.4.2.3., 9.4.3.1., 9.8.9.1., 9.23.15.5. and variants) | 13191-R, 13569-R, 14086-R, 14150-R, 15042-R, 13690-R, 14092-R, 14101-R, 14744-R, 13500-R, 14089-R, 14114-R, 13378-R, 14154-R, 14121-R, 14342-R | ca-ccmc-composite-decking-and-stair-treads (13125-R) |
| Binders for wood panels (six material-standard articles) | 12009-R, 13421-R, 13486-R, 14125-R | ca-ccmc-pmdi-binder-osb-panels (14072-R) |
| 9.25.2.2. only (insulation materials) | 12764-R, 14067-R, 14130-R, 14272-R (hemp fibre batt, a case was built and then dropped as a near duplicate of the spray foam case) | ca-ccmc-open-cell-spf-insulation (14138-R) |
| 9.27.12.1. (vinyl and insulated siding) | 14047-R, 14323-R, 14719-R, 14769-R | ca-ccmc-insulated-polymer-cladding (14182-R) |
| 9.27.3.3. (sheathing tape) | 11955-R, 14190-R | ca-ccmc-sheathing-tape-joints (11362-R) |
| 9.13.3.x waterproofing materials | 13297-R, 13560-R, 13562-R, 13630-R, 14095-R, 14144-R, 14841-R, 13452-R | none (waterproofing membranes are not represented; 13297-R is NBC 2005 and its numbers do not map) |
| 9.29.5.x gypsum board finish (vinyl-laminated) | 13637-R, 14119-R, 14184-R | none (interior finish not represented) |
| 9.25.2.2., 9.25.4.2., 9.36.2.8. | 14205-R | ca-ccmc-reflective-eps-board-foundation-wall (13459-R) |
| 9.14.3.x foundation drain pipe | 14520-R | ca-ccmc-pvc-footing-form-and-drain (13492-R) |
| 9.13.2.2.-9.13.2.4. (dimpled membranes, NBC 2015) | 14080-R, 14093-R | ca-ccmc-dimpled-foundation-dampproofing (12266-R) |
| 9.27.3.2.-9.27.3.4. and 9.27.3.2.-9.27.3.3. (sheathing with tape) | 06666-R, 14019-R, 13584-R, 14049-R | ca-ccmc-eps-sheathing-integral-membrane (13488-R) |
| Single reports on other topics, mappable but not selected to keep the set near the target size | 12525-R (underlayment), 13216-R (glulam, NBC 2010 table only), 13302-R, 14008-R, 14204-R (masonry and stone veneer products), 13356-R, 14032-R (air barrier, Part 5 title differs), 13494-R, 13508-R, 13517-R, 14003-R, 14018-R, 14075-R, 14083-R, 14088-R, 14091-R, 14136-R, 14445-R, 14450-R, 14928-R | none (candidates for a later pass: masonry veneer, glulam, roof venting, flashing tape, interior boards) |

- Mapping drops inside used reports: 13529-R lists the service-penetration article 3.1.9.2. as Alternative; that number now has a different title and topic in the 2023 text, so it is dropped. The 2015 article 3.1.9.5. (Combustible Piping Penetrations) is kept as its 2023 successor 3.1.9.4. with the evidence stated in the mapping. 13529-R also lists National Plumbing Code rows (support for horizontal piping, potable water systems); those are outside Division B and dropped. EIFS was Subsection 9.27.13. in NBC 2015 and is 9.27.14. in NBC 2020 (CCMC 13103-R and 13232-R list both); the EIFS reports only have Acceptable rows, so none is used.

### 5.2 BC Building Code Appeal Board (266 decision pages 1700 to 2007 downloaded)

Used: 28 decisions. Every other decision was reviewed by title and by its extracted "Applicable Code requirements"; I read about 40 of them in detail and did not read the rest in full. Reason codes:

- `DIVAC` cites only Division A or Division C provisions (definitions, application, alternative-solution documentation), so no Division B gold can be formed.
- `PLUMB` plumbing code (BCPC, Book II) or a mix with plumbing; outside the building code.
- `EDITION` decided under BCBC 2012 or older; numbering and wording are not comparable with NBC(AE) 2023, so not mapped.
- `BCSPEC` depends on a BC-specific provision or amendment with no NBC(AE) 2023 counterpart (energy step code, letters of assurance, BC secondary-suite and cooling additions).
- `ACCESS` accessible design (Section 3.8); BC wording is likely to differ; not examined, candidates for a later pass.
- `RENUM` the cited BCBC 2018 numbers or wording differ from the 2023 text and need sentence-by-sentence work; not selected.
- `DUP` mappable, but a selected case already covers the same articles or situation (named).
- `PART3` mappable Part 3 topic that was not selected (Part 3 topics are already covered by several selected cases).
- `LATER` mappable Part 9 topic of narrow scope, not selected; candidates for a later pass.
- `NOTEXT` listed as withdrawn, cancelled, dismissed or not available; no decision text.

| Code | Decisions (id: title) |
|---|---|
| DIVAC (28) | 1841: Dwelling unit/suite definition; 1842: Alternative solution for determination of grade; 1846: Determination of grade; 1856: Application of defined term dwelling unit; 1857: Applicable edition of BC Building Code; 1865: Permitted use of a storage garage; 1885: Application of Building Code for fabric cover yurts; 1898: Application of intent statements to exit requirements; 1909: Buildings designated post-disaster; 1913: Building height, change of occupancy; 1914: Spatial separations for a park model trailer; 1921: Storeys in building height, rooftop structures; 1924: Localized depression and storeys in building height, single ; 1925: Configuration of required egress and exits, two-storey suite; 1928: Applicability of the Building Code to an accessory building; 1933: Determination of grade and building height for an alteration; 1935: Determination of subsidiary or major occupancy; 1943: Determination of major occupancies in an existing building; 1944: Building Code application to an addition to an existing buil; 1946: Registered professional responsibility for an alternative so; 1970: Application of defined terms dwelling unit and suite; 1973: Requirement to retain building features originally required ; 1974: Application of code requirements to the change in occupancy ; 1982: Alternative solution for the alteration of an existing house; 1992: Applicability of the Building Code to a carport; 1993: Application of defined term suite related to a dwelling unit; 2003: Definition of Building, Commercial Kitchen Trailer; 2007: Addressing Code deficiencies in a change of occupancy in an  |
| PLUMB (7) | 1860: Size of trap and trap arm in relation to fixture outlet pipe; 1895: Use of long sweep 90 degree elbows in a sanitary drainage sy; 1926: Accessible location for shut-off valves, residential suites; 1951: Vacuum-relief valve requirement; 1961: Roof drain requirement for covered roof deck; 1983: Connection of wet vent to nominally horizontal sanitary drai; 1994: Check valve requirement for a plastic water service pipe sup |
| EDITION (1) | 1963: Protection for suspended garage floors over basements in tow (BCBC 2012) |
| BCSPEC (4) | 1932: Application of Part 9, energy efficiency requirement; 1956: Protection from overheating in an alteration to include a se; 1977: Letters of assurance for a Part 9 building; 1991: Energy efficiency requirements for windows and doors in a ho |
| ACCESS (9) | 1899: Application of building requirements for persons with disabi; 1910: Application of requirements for accessibility in existing bu; 1939: Accessibility requirement for exterior entrance to live-work; 1958: Alteration of an existing school to replace a lift with a ra; 1962: Requirement for power door operators in accessible floor are; 1964: Accessibility requirements for a fruit processing, retail, a; 1979: Access requirements in a public nature-viewing building; 1995: Access requirement for raised platform in a church; 1997: Movable or removable armrest for an adaptable seat in an ass |
| RENUM (5) | 1874: Use of combustible DWV plumbing piping in high rise building; 1906: Required kitchen ventilation utilizing a heat recovery unit; 1966: Fire separation and fire-resistance rating requirements for ; 1971: Firestopping of noncombustible outlet boxes in a horizontal ; 1980: Heat-recovery ventilators in a mechanical ventilation system |
| DUP (13) | 1845: Spatial separation calculations for houses (spatial separation glazing: see 1942 and BCIC 24-0096); 1853: Limiting distance, fire department response time (limiting distance and response time: see 1942); 1862: Spatial separation, NFPA 13D, “Installation of sprinkler sys (limiting distance with sprinklers: see 1942); 1863: Spatial separation, NFPA 13D, “Installation of sprinkler sys (limiting distance with sprinklers: see 1942); 1871: Egress from dwelling units (egress travel limit: see 1954); 1880: Required guard protection at intersection of deck and sloped (guards: covered by 1859 and 1940); 1893: Required fire blocking (fire blocking: see 1985); 1896: Required fire blocking (fire blocking: see 1985); 1905: Basement interior protection of insulated concrete forms (foamed plastic protection: see 1950 and the DC315 case); 1916: Glazed openings in exposing building face of a single family (limiting distance and response time: see 1942); 1938: Required exterior guards (guards: covered by 1859 and 1940); 1941: Required exterior guards (guards: covered by 1859 and 1940); 1952: Required exterior guards (guards: covered by 1859 and 1940) |
| PART3 (27) | 1840: Occupancy classification of a flour mill; 1843: Dead-end corridor, elevator lobby; 1844: Doors in exit shafts for high buildings; 1847: Protection of electrical conductors for emergency equipment; 1848: Establishing finished ground for the determination of grade ; 1864: Required manual stations for fire alarm systems; 1866: Required egress for a mercantile Group E suite; 1867: Required smoke dampers; 1868: Occupancy classification of amenities area; 1876: Means of egress for fourth storey suites; 1878: Exposure protection for required egress door exterior path o; 1892: Fire extinguishing systems for a distillery; 1894: Source of water supply for NFPA 13 sprinkler requirements; 1901: Vertical HVAC shaft; 1902: Corridor within an interconnected floor space; 1912: Egress from mezzanine; 1915: Smoke control at vestibules in a high building; 1931: Means of egress in an alteration to an existing building; 1957: Construction of an exterior exit facility; 1959: Vertical HVAC shaft servicing a single suite; 1960: Integrity of an exit at service equipment penetrations into ; 1967: Standpipe system requirements for a house; 1968: Roof access requirements for a house; 1975: Requirement for kitchen ventilation in a daycare facility; 1986: Flame test requirements for upholstered, fixed, theatre seat; 1996: Requirement for a mezzanine to be a visually open area; 2005: Provision of water supply for firefighting |
| LATER (12) | 1872: Fire department access roadway to buildings; 1882: Minimum room size for a water-closet room (powder room); 1883: Minimum doorway size for water-closet room (powder room); 1884: Reduction of required doorway width and obstruction of acces; 1886: Location of required water closets; 1890: Attic access for self-storage units; 1903: Access stair requirements for an elevated floor storage area; 1918: Identification of potential intruders, entrance to dwelling; 1937: Ergonomic design of handrails; 1953: Protection from precipitation in an alteration to an existin; 1987: Ventilation requirements in the renovation of a guest suite ; 1988: Change of use in a garage attached to a single-family dwelli |
| NOTEXT | Withdrawn: 2004 1978 1923 1888 1879 1858 1851 1850 1839 1838 1832; Cancelled: 2001 1998 1972 1955 1949 1947 1934 1927 1919 1917 1904 1881 1875 1873 1861 1827; Not available: 1989 1984 1969 1922 1908 1907 1891 1889 1870; Dismissed: 1900 |
| EDITION (older pages) | 132 downloaded decisions numbered 1700 to 1839 (decided under BCBC 2006 or 2012, older page template): not examined individually and not mapped. Decisions below 1700 (about 700 more, on the index page) were not downloaded for the same reason. |

### 5.3 BC Building Code Interpretation Committee, 2024 index (141 entries)

Used: 7 (24-0080, 24-0096, 24-0120, 24-0122, 24-0123, 24-0144, 24-0181). Excluded, with reasons:

Codes as in section 5.2, assigned from the Part numbers in each interpretation's reference list (not read one by one except where a note is given). `BCSPEC` here means the BC text differs from the 2023 text on the point asked; `PLUMB` also covers entries that mix building and plumbing references.

| Code | Interpretations |
|---|---|
| BCSPEC (6) | 24-0007: Cooling System in a Dwelling Unit (cooling system in a dwelling unit: BC cooling requirement; the 2023 text has no cooling sentence); 24-0037: Fire Dampers in Houses with Secondary Suites (secondary-suite duct dampers: the cited sentence 9.10.9.9.(6) and the smoke-circulation wording of 9.32.3.2.(4) do not exist in the 2023 text); 24-0038: Separation of Suites in a House having a Suite without  (suite separation: BC grades the fire-resistance of the secondary-suite separation, the 2023 sentence is a flat smoke-tight barrier); 24-0065: Radon Rough-In Vent Termination (radon rough-in: BC amended the national figure so the vent must end outside; the 2023 text keeps the capped rough-in); 24-0068: Residential Air Conditioners (residential air conditioners: BC cooling requirement); 24-0115: Heating and Cooling Systems in Houses with Secondary Su (heating and cooling for secondary suites: BC allows one system with a smoke detector; the 2023 sentence forbids direct interconnection) |
| RENUM (1) | 24-0031: Sprinkler and Fire Alarm Systems in Row Housing (row-house fire alarm: the 2023 text of the first fire-alarm article differs from the BC text) |
| DUP (6) | 24-0046: Opening Restrictor on Bedroom Window (bedroom window restrictor: same articles as BCAB 1940); 24-0066: Separate dwelling unit exposing building face (exposing building face of an addition: see BCAB 1942); 24-0075: Area of Glazed Openings (area of glazed openings: same articles as BCAB 1942); 24-0105: Application of Part 3 Spatial Separation Requirements t (Part 3 tables for Part 9 townhouse glazing: same articles as BCAB 1942); 24-0159: Minimum Construction Requirements of Exposing Building  (construction of exposing faces: see BCIC 24-0096); 24-0161: Application of 9.10.14 or 9.10.15 to Multi-Unit Buildin (which spacing subsection applies to multi-unit buildings: see BCAB 1948 and 1869) |
| PLUMB (14) | 24-0019: Installation Requirements for Condensate Drains; 24-0043: Venting Requirements for Floor Drains NPS 3 and Larger; 24-0052: Sizing a Vent Stack; 24-0054: Bathroom Exhaust Fans; 24-0062: Wet Venting a Water Closet With a Symmetrical Fitting; 24-0107: Emergency Roof Overflows; 24-0109: Venting of Manufactured Oil Interceptors; 24-0116: Press-Connect Fittings – Stainless Steel and Copper Pip; 24-0139: Floor Drain in a High Voltage Room; 24-0146: Pin Bolt Anchors for Water Closet Floor Flange; 24-0153: Private Water Supply Water Service Shut-off Valve Requi; 24-0157: Restricted Location of Sanitary Drainage Pipes; 24-0163: Horizontal Dry Vent; 24-0170: Cleanouts in Health Care Facilities |
| ACCESS (28) | 24-0001: Power door operators for entry doors; 24-0005: Encroachment of clear transfer space for the change roo; 24-0013: Accessible ramp, landing and walkway curb protection; 24-0015: Measurement of Clear Floor Space Width at a Door; 24-0017: Doorway Width for One Bathroom in a Dwelling Unit; 24-0021: Adaptable Bedrooms; 24-0022: Adaptable Bathrooms; 24-0023: Future Conversion of Adaptable Suites; 24-0024: Plumbing Systems for Showers in Adaptable Suites; 24-0025: Lever Handles for Faucets in Adaptable Suites; 24-0029: Limited Mobility Stalls; 24-0030: Illumination of Exterior Path of Travel; 24-0034: Balcony Access in Adaptable Suites; 24-0039: Access for Part 9 Apartment Buildings; 24-0047: Separate water closets for genders; 24-0049: Adaptable water closet encroachments; 24-0055: Curtains for Accessible Showers; 24-0057: Accessible Counters; 24-0067: Private vs Public Showers; 24-0072: Width of Accessible Exterior Walk; 24-0081: Wave Action Power Door Operator; 24-0084: Power Door Operator Exemptions; 24-0085: Adaptable Dwellings Served by Exterior Doors only; 24-0098: Accessible Clearance Between Doors in an Elevator Vesti; 24-0111: Accessible clearance for sliding door without power doo; 24-0121: Combined universal washroom and universal dressing and ; 24-0126: Location of push-button controls for power door operato; 24-0142: Where universal washrooms are required |
| PART3 (42) | 24-0003: Dead End Corridors; 24-0009: Landing at Top of Mezzanine Stair; 24-0010: Climbable Objects and Steps near Guards; 24-0012: Future Visible Signal Devices in Ensuite Bathrooms; 24-0018: Open mezzanine; 24-0032: Tactile Walking Surface Indicators; 24-0033: Spatial Interpolation with LD < 1.2m; 24-0041: Handrail Projections; 24-0045: Industrial Mineral Stockpile Cover; 24-0048: Sprinklers on top floor residential balconies; 24-0050: Group A Division 2 Occupancy in an Article 3.2.2.60 Bui; 24-0056: Open area beneath mezzanine; 24-0060: Fire-Resistance Rating of Balcony Structure and Roof Ov; 24-0069: Townhouse roof fire-resistance rating; 24-0070: Protection of steel columns within a fire-rated wall; 24-0071: Heavy Timber Roof Assembly and Sprinklers; 24-0074: Sloped parking garage floor; 24-0077: Manual signal silencing of audible signal devices; 24-0078: Definition of Street; 24-0082: Firestopping Between Fire-Rated Sill and Exterior Curta; 24-0087: Sprinklers in Care Facilities for Residential Use; 24-0093: Exterior door that is not a required exit door; 24-0095: Exterior amenity roof deck; 24-0101: Visible signal devices within dwelling unit; 24-0102: Canadian Wood Council – The Span Book; 24-0104: Concrete Columns for Part 9 Buildings; 24-0113: Fire Dampers at Floor Level Instead of Fire-Separated V; 24-0124: Low Frequency Fire Alarm Audible Signal Devices; 24-0140: Fire-Resistance Rating (FRR) of the first-floor assembl; 24-0141: Firestopping of Exterior Electrical Outlet Box; 24-0143: Fire separation of elevator control room with no elevat; 24-0145: Labelling of Exit Stairs per BCBC and CSA; 24-0147: Egress doors from roof decks or contained open space; 24-0148: Egress from Elevator Lobbies; 24-0149: Fire Blocks between concealed vertical and horizontal s; 24-0151: Visual Signal in Bathrooms of Residential Suites; 24-0155: Supervision of Sprinkler Control Valves; 24-0167: Exit exposure for a principal entrance; 24-0168: Unlimited Unprotected Openings in an Open-Air Storage (; 24-0171: Latching of Fire-rated door; 24-0173: Outlet boxes in staggered-stud walls; 24-0176: Washroom for Storage Garages |
| LATER (33) | 24-0004: Spatial Separation between dwelling units with storage; 24-0006: Application of Tables in 9.36.2.6, 9.36.2.7 and 9.36.2.; 24-0008: Unsupported height of foundation wall; 24-0011: Part 9 guards for windows; 24-0016: Accessory Building; 24-0020: Double Header Joist around Floor Opening; 24-0028: Egress from Multi-Level Dwelling Units; 24-0035: Exhaust Air Inlet as a Return Air Inlet in Dwelling Uni; 24-0040: Footing Area Proportional to Column Spacing; 24-0042: Camera as a door viewer; 24-0051: Small Residential Care Home; 24-0064: Attachment of a Porch Roof; 24-0083: Resistance to Forced Entry for Doors Between Dwelling; 24-0086: Location of Principal Exhaust Fan in Single Family Dwel; 24-0088: Building Plan Dimension for Braced Wall Panels; 24-0091: Radon System Pipe Standard and Air Barrier Material; 24-0092: Requirements for Gas-Permeable Layer and Location of Be; 24-0094: Slip-resistance of exterior stair; 24-0099: Braced Wall Panels for Detached Garage; 24-0100: Direct passage in combination rooms; 24-0103: Attachment of Cladding; 24-0106: Vehicle Guards for Garage Serving a Single Dwelling Uni; 24-0108: Exit from a second storey dwelling unit; 24-0110: Twenty-minute Wood Door Frame; 24-0112: ICF Reinforcement; 24-0117: DWV Piping in Gas-Permeable Layer; 24-0131: Laterally Unsupported Foundation Walls Below Openings; 24-0135: Height of a Window in a Townhouse; 24-0154: Minimum Slope for a Ramp; 24-0164: Combining Parts 4 & 9 for Seismic Design of Houses; 24-0174: Windows in Vehicular Access Doors; 24-0177: Wood blocking in braced wall panels; 24-0180: Thickness Variations in Solid Core Wood Doors |
| DIVAC (4) | 24-0061: Seismic Restraint, Friction Forces and Playground Equip (definition, edition or non-article reference); 24-0114: Roof Soffit - Withdrawn (definition, edition or non-article reference); 24-0125: Exterior Exit Route to a Public Thoroughfare (definition, edition or non-article reference); 24-0158: Variations from Tables D-2.3.4.-A to G (definition, edition or non-article reference) |

Only the 2024 index (BCBC 2024) was used. BC interpretations for BCBC 2018, 2012 and 2006 (boabc.org index pages) were not opened.

### 5.4 Other provinces, territories and sources

- Saskatchewan Appeal Board: hears owner appeals of building official orders and interpretation requests, but the Chief Codes Administrator does not refer matters that are alternative solutions, and no decisions are published. Nothing to harvest.
- Saskatchewan ministerial interpretations: NBC 2020-004 (CO detectors in lieu of CO alarms) is used. NBC 2020-003 (tiered prescriptive path for Section 9.36) is excluded: it fills a gap in the national text (Tiers 3 to 5 reserved) by replacing the compliance article, and the Alberta edition already has a different compliance article (9.36.8.2. gives points for Tiers 2 to 5), so the situation does not carry over. NPC 2020-001 (backflow) is plumbing code.
- Saskatchewan advisories: the Secondary Suites advisory is used. Bedroom Egress Windows and Clearance Above Cooktops were read; they restate articles already covered by BCAB 1940 and by the NBC text (descriptive guidance, no departure). Electrical Equipment Installation, Radon, Fire Alarm Monitoring, Five Principles and the others were downloaded or listed but not read in detail.
- Manitoba: the permit dispute decisions page lists one decision (180 Provencher Blvd, December 2025); it is a scanned letter about snow-drift loading under a Winnipeg by-law and cites no NBC article. The ITS bulletins index could not be fetched; bulletins found by search (factory-constructed buildings, manufactured homes) are scope notes.
- Ontario: the Building Material Evaluation Commission publishes only a table of authorizations (copies by email); Building Code Commission decisions are on CanLII, which returns a bot-protection page to automated requests, so they were not read. A Ministry ruling approving a laminated strand lumber product (Ruling 05-19-143) appeared in search results; it concerns the same product and articles as CCMC 12627-R and was not read. OBC numbering was not used for any case.
- Nova Scotia, New Brunswick, Prince Edward Island: statutes and municipal guidance only. A Halifax guide describes the alternative-solution form but its sample was not retrievable as a document. PEI IRAC orders surfaced by search concern permits, not code articles.
- Newfoundland and Labrador: the Buildings Accessibility Appeal Tribunal annual reports (2020-21, 2021-22) record no appeals.
- Yukon, Northwest Territories, Nunavut: searches found no interpretation bulletins or decision lists.
- Quebec: not attempted (separate Construction Code, French-language sources).
- NRC and CCBFC: no public database of published code interpretations or alternative-solution worked examples was found. The Illustrated User's Guides were not opened.
- Municipal alternative-solution guides (Burnaby, Coquitlam, Saanich, Halifax, Manitoba ITS form): procedural only; none gives an article-level worked example.

## 6. Mapping caveats

Editions. NBC(AE) 2023 is based on NBC 2020. BCBC 2024 is based on NBC 2020 (the BC interpretation committee says the 2024 BCBC was harmonized with NBC 2020, interpretation 24-0096), BCBC 2018 on NBC 2015, and CCMC reports cite NBC 2010, 2015 or 2020. Edition alone was never accepted as proof: each gold article was matched by reading the 2023 text, and the build refused any quote that is not in the database.

Renumbered successors found (kept, medium confidence, evidence in the mapping):
- BCBC 2018 9.10.9.10. (Concealed Spaces above Fire Separations) is 2023 9.10.9.12.; the sentences are word for word identical, and 2023 9.10.9.10. is now Collapse of Combustible Construction (ca-bcab-1887).
- BCBC 2018 9.32.3.6. and 9.32.3.8. (kitchen exhaust fan, air ducts) correspond to 2023 9.32.3.7. (Supplemental Exhaust) and 9.32.3.11. (Ducts); 2023 9.32.3.6. is Reserved (ca-bcab-1920).
- NBC 2015 3.1.9.5. (Combustible Piping Penetrations), cited by CCMC 13529-R, is 2023 3.1.9.4.; 2023 3.1.9.5. is a different topic (ca-ccmc-pex-piping-noncombustible-buildings). The same renumbering explains why BCAB 1874 (BCBC 2018 3.1.9.5.) was not used.
- 2023 9.27.14. replaced the EIFS articles numbered 9.27.13. in NBC 2015.

Same article, different wording (kept with a note):
- 9.8.8.1.(4): the 2023 text says the opening-limiting mechanism "can only be released with the use of tools or special knowledge"; BCBC 2018 did not. That is the conflict behind BCAB 1940 and Alberta's window-opening-control-device variance (ca-bcab-1940).
- 3.2.1.1.(3) mezzanine exception: the 2023 text uses an aggregate-area limit of 40 percent; BCBC 2018 used an open-plane test. Sentence (4) is identical (ca-bcab-1852).
- 9.10.15.1.(1): BCBC 2018 had a third clause for accessory buildings that serve a house; the 2023 text does not (ca-bcab-1869).
- 9.9.9.2.: the 2023 text builds the secondary-suite exception into the first sentence; BCBC 2024 has it in a separate sentence (ca-bcab-1954).
- Sentence numbers inside articles often differ (for example BCBC 3.3.1.3.(11),(12) are 2023 3.3.1.3.(8),(9)); gold is at article level, and the sentence number as cited stays in `as_cited`.

Alberta-specific points found while reading the 2023 text:
- No article 9.1.2.1.: NBC 2020 limits a secondary suite's floor area; the Alberta edition has only one article in Section 9.1. The Saskatchewan checklist case drops it.
- The secondary-suite smoke-tight barrier rules (9.9.4.2., 9.10.8.3., 9.10.9.1.-9.10.9.4., 9.10.9.16.-9.10.9.17., 9.10.10.4., 9.10.11.2., 9.10.12.3., 9.10.15.1., 9.10.19.5., 9.32.3.9., 9.33.1.1., 9.33.4.3.) match the Saskatchewan checklist descriptions. BC amendments to the same area (graded fire-resistance, duct dampers, one system with a smoke detector, a cooling sentence) are not in the 2023 text, which is why several BC interpretations (24-0007, 24-0037, 24-0038, 24-0068, 24-0115) and BCAB 1956 were excluded.
- Energy articles 9.36.2.2. and 9.36.2.8. (used in ca-ccmc-reflective-eps-board-foundation-wall): the requirement text was read and matches; table values were not compared, so Alberta table differences are not ruled out.
- CCMC opinions and BC decisions are not Alberta variances. They show which articles the applicant had to address, not whether an Alberta SCO would accept the proposal.

Other limits:
- Standards editions referenced inside articles (CSA, ASTM, CAN/ULC) were not compared.
- CCMC reports that only list NBC 2015 (12627-R, 13016-R, 13287-R, 13473-R, 13529-R, 13677-R, 14027-R, 14346-R) were mapped by the article text, but the product evaluation may be updated to NBC 2020 later with different rows.
- Applicant labels for appeals and interpretations are inferred from the project; the decisions do not state who appealed.
- The Saskatchewan CO interpretation substitutes Saskatchewan wording (a province-wide CO alarm requirement, Henry's Law); the substituted articles are the 2023 articles, but the detector permission itself is not in the 2023 text.

## 7. Gaps and suggested follow-ups

- No alternative-solution worked examples with article-level citations were found outside BC appeals and CCMC; Ontario BCC decisions (CanLII) and BMEC authorizations (on request) would add real alternative-solution files if obtained by hand.
- Mass timber and cross-laminated timber, windows and doors, masonry veneer, glulam, waterproofing membranes, firestopping products and roof ventilation products are not represented; CCMC has candidates for most of them (section 5.1 last row).
- BC decisions before 1840 and BCBC 2018 interpretations could be mapped with per-sentence checks if more cases are needed.
- Most of the 24 Saskatchewan advisories (radon, fire alarm monitoring, electrical equipment rooms, cooktop clearance) were not read in detail; they are descriptive and could give single-topic interpretation cases.

## 8. Reproduction notes

- CCMC: `published_evaluations.html` returns the full registry; each report page carries a "Compliance opinion" table with the columns ID, Code provision and Solution type.
- BC appeals: decision pages are plain HTML with sections Project description, Applicable Code requirements, Local Authority's position, Appellant's position and the Board decision.
- Verification used read-only SQLite queries against `codedb/build/codedb.sqlite` (doc NBC-AE, division B), the database behind `evals_dev.identify_bench.codedb_lookup`.

Parent integration disposition: the Saskatchewan CO-substitution case is now marked `evaluation_scope: foreign_topic` and excluded from primary current-Alberta recall. Its mapping wording identifies related topics only, not the same Alberta requirement. All gold identifiers are retained for source audit.
