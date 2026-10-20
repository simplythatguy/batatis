---
topic: occupancy-and-accessibility
scope: Major occupancy classification (Div B 3.1.2 groups A to F), mixed occupancies (3.1.3), special building types, the Part 9 vs Part 3 applicability line, and barrier-free accessibility (Section 3.8) under NBC(AE) 2023 2nd printing, and the points where a registered professional is required.
sources_checked:
  - Repository contracts and briefs (PREAMBLE, WAVE2-BRIEF, WAVE2-TOPICS occupancy-and-accessibility section, CONTRACTS, WAVES, reference/README-challenge)
  - Method files read (t3-workflow SKILL and references/routes, Matt Pocock engineering research SKILL, pstack unslop SKILL)
  - NBC(AE) 2023 2nd printing, reference/codes/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.pdf, pages listed in Sources, each checked with codedb lookup and codesearch page
  - NBC 2020 Intent Statements (explanatory only), reference/codes/NBC-2020-Intent-Statements.pdf, pages listed in Intent
  - Permit Regulation AR 204/2007, reference/text (farm building definition, source p.5)
  - STANDATA variances and interpretations in reference/text: 23-BCV-001, 23-BCV-005, 23-BCV-006, 23-BCV-011, 23-BCV-011R1, 23-BCV-013 (with 19-EDB-002), 23-BCV-014, 23-BCI-016R1, 23-BCI-019, 23-BCI-024, 23-BCI-032, 23-BCI-034
  - CWC Alternative Solutions Guide, reference/guides/CWC-Alternative-Solutions-Guide.pdf, source pp.6, 8, 9
  - research/precedents/index.json (titles and dates only)
  - https://alberta.ca/application-for-barrier-free-relaxation (fetched 2026-10-19)
last_verified: 2026-10-19
---
# Occupancy and accessibility

## Progress
- Done (2026-10-19): all template sections written. Code citations were checked with codedb lookup and page reads, and intent pages were checked by eye only where the Intent section says so.
- Validator: `codedb validate` reports 0 errors and 0 warnings. Unverified items are listed under Open questions and marked UNVERIFIED in the text.

## Plain-language summary
Every building, and every separate part of a building, has a major occupancy. The major occupancy is the principal use the building is used or intended for, and it includes subsidiary uses that are an integral part of that use [Div A, Article 1.4.1.2., PDF p.47]. Div B Table 3.1.2.1 sorts uses into groups: A (assembly, four divisions), B (detention, treatment and care, three divisions), C (residential), D (business and personal services), E (mercantile) and F (industrial, high, medium and low hazard divisions) [Div B, Sentence 3.1.2.1.(1), PDF p.129] [Div B, Table 3.1.2.1, PDF p.130].

The occupancy and the size of the building decide which Part applies. Part 3 covers post-disaster buildings, every building of Group A, Group B or Group F, Division 1, and every building of Group C, D, E, F-2 or F-3 that is over 600 m² in building area or over three storeys in building height [Div A, Sentence 1.3.3.2.(1), PDF pp.39-40]. Part 9 covers the smaller buildings of Group B, Division 4 (home-type care), C, D, E, F-2 and F-3 that are three storeys or less and 600 m² or less [Div A, Sentence 1.3.3.3.(1), PDF p.40].

A building with more than one use is classified under every major occupancy it contains [Div B, Sentence 3.1.2.1.(2), PDF p.129]. Where two occupancies share a building, Table 3.1.3.1 sets the fire-resistance rating of the separation between them [Div B, Sentence 3.1.3.1.(1), PDF p.130] [Div B, Table 3.1.3.1, PDF p.131]. A Group F, Division 1 occupancy may not share a building with Group A, B or C occupancies [Div B, Sentence 3.1.3.2.(1), PDF p.131].

Section 3.8 sets barrier-free design rules. Barrier-free means that a building and its facilities can be approached, entered and used by persons with physical or sensory disabilities [Div A, Article 1.4.1.2., PDF p.42]. Div B Section 3.8 does not apply to the house types listed in Div B Sentence 3.8.2.1.(1), to Group F, Division 1 buildings, to buildings not intended for daily or full-time occupancy, or to relocatable industrial accommodation [Div B, Sentence 3.8.2.1.(1), PDF p.301]. The Provincial Barrier-Free Administrator or the Provincial Building Administrator may relax Section 3.8 if the owner shows that a requirement is unnecessary or that extraordinary circumstances prevent conformance [Div C, Sentence 2.2.1.4.(1), PDF p.730].

Farm buildings have two separate rules. The Code does not apply to a low-human-occupancy building on a farm that houses livestock, stores or maintains equipment, or stores materials or produce [Div A, Sentence 1.1.1.1.(4), PDF pp.37-38]. A farm building not for public use is also one of the buildings that need no registered professional involvement [Div C, Sentence 2.4.1.1.(1), PDF pp.739-740]. Those are different tests, and a farm building can meet one without meeting the other.

## When this topic applies
Trigger signals. Any of these in a project description, drawing set or permit file routes the question here.
- A stated use that maps to a group in Table 3.1.2.1 [Div B, Table 3.1.2.1, PDF p.130]. The Note A-3.1.2.1.(1) examples show the intended reach of each group. Restaurants, places of worship, libraries and child care facilities are Group A, Division 2. Offices, banks and medical offices are Group D. Shops, stores and supermarkets are Group E. Storage garages are listed under Group F, Division 3, and warehouses appear under both Group F, Division 2 and Group F, Division 3 [Div B, Note A-3.1.2.1.(1), PDF pp.356-359].
- Two or more uses in one building, such as ground-floor retail with residential units above [Div B, Sentence 3.1.2.1.(2), PDF p.129].
- A building height or building area near 3 storeys or 600 m², which decides Part 3 or Part 9 [Div A, Sentence 1.3.3.2.(1), PDF pp.39-40] [Div A, Sentence 1.3.3.3.(1), PDF p.40].
- Special building types with their own sentences: an arena-type building used occasionally for trade shows [Div B, Sentence 3.1.2.3.(1), PDF p.130]; a police station with detention quarters that is one storey and 600 m² or less [Div B, Sentence 3.1.2.4.(1), PDF p.130]; convalescent or children's custodial homes for ambulatory occupants [Div B, Sentence 3.1.2.5.(1), PDF p.130]; baled combustible fibre storage [Div B, Sentence 3.1.2.6.(1), PDF p.130]; and a self-service storage building, which is Group F, Division 2 [Div B, Sentence 3.9.1.2.(1), PDF p.320] [Div B, Sentence 3.9.1.3.(1), PDF p.320].
- A Group F, Division 1 building that the owner wants treated as Group F, Division 2, such as an oil or gas processing building (STANDATA 23-BCV-005) or a natural gas regulating and metering building (STANDATA 23-BCV-006) [source p.2 of each].
- A greenhouse, including a greenhouse open to the public, where the owner proposes polyethylene film (STANDATA 23-BCV-011R1). Option 2 for public access requires Group F, Division 3 [source p.2].
- Accessibility features: an entrance, a path of travel, a washroom, a counter, a parking stall, fixed seating in an assembly room, or a physician clinic or office [Div B, Sentence 3.8.2.2.(1), PDF p.302] [Div B, Sentence 3.8.2.3.(1), PDF p.302] [Div B, Sentence 3.8.2.8.(1), PDF p.304] [Div B, Sentence 3.8.5.1.(1), PDF p.319].
- A passenger elevator proposed in place of a platform lift or limited-use/limited-application elevator (STANDATA 23-BCV-013, February 2026) [source p.2].
- A residential project of 10 or more dwelling units funded in whole or in part by the Government of Alberta, which must provide adaptable dwelling units at one per 10 dwelling units [Div B, Sentence 3.8.1.1.(3), PDF p.301].
- Temporary industrial accommodation for a workforce, which brings in Part 10 [Div A, Sentence 1.3.3.3.(2), PDF p.40]. A building within an airport vicinity protection area that is subject to acoustic insulation brings in Part 11 [Div A, Sentence 1.3.3.3.(5), PDF p.40] [Div B, Sentence 11.1.1.1.(1), PDF p.1517].
- A farm building, where the question is whether the Code applies at all [Div A, Sentence 1.1.1.1.(4), PDF pp.37-38], or whether a registered professional must authenticate drawings [Div C, Sentence 2.4.1.1.(1), PDF pp.739-740].

Near-misses that belong to another topic or to no topic in this sheet.
- Detached and semi-detached houses, houses with a secondary suite, duplexes, triplexes, townhouses, row houses, and boarding houses not used in social programs are outside Section 3.8 [Div B, Sentence 3.8.2.1.(1), PDF p.301]. Their Part 9 questions go to housing-secondary-suites-part9. Functional statements F73 and F74 exclude the same house types, but that sentence has no social-program qualifier [Div A, Sentence 3.1.1.2.(3), PDF p.79].
- Number of exits, travel distance, and exit width. These belong to egress-and-single-stair.
- The fire-resistance rating of walls, floors and assemblies inside one occupancy. The rating between two different occupancies, from Div B Table 3.1.3.1, stays in this topic.
- Height and area limits for combustible or noncombustible construction. Those depend on major occupancy, but the limits belong to combustible-construction-and-mass-timber [source p.8 of the CWC guide].
- Window guards and window opening control devices in dwellings (Div B Sentence 9.8.8.1 and STANDATA 23-BCV-001). This sheet covers only that STANDATA's exclusion for adaptable and barrier-free dwelling units [source p.3].
- Part 4 structural design, which must be done by a registered professional [Div C, Sentence 2.4.1.2.(1), PDF p.740]. That belongs to structural-and-framing and professional-involvement.
- Plumbing fixture counts and ventilation rates. Those belong to hvac-ventilation-plumbing, even though the occupancy group sets part of the answer.
- Multi-level storage racking treated as a special and unusual structure under Div B Article 3.2.2.2 (STANDATA 23-BCV-014). The occupancy question is secondary to the structural and construction question. This sheet mentions it only as a novel-use example [source p.1].

## Benchmark acceptable solutions
These articles set the recipe for occupancy and accessibility. Each row is paraphrased, and each citation was checked against the extracted NBC(AE) 2023 text or the named source page.

Classification (Part 3)
- Every building or part is classified by major occupancy from Table 3.1.2.1 [Div B, Sentence 3.1.2.1.(1), PDF p.129] [Div B, Table 3.1.2.1, PDF p.130]. Note A-3.1.2.1.(1) lists example uses under each group [Div B, Note A-3.1.2.1.(1), PDF pp.356-359].
- A building with more than one major occupancy is classified under every one of them [Div B, Sentence 3.1.2.1.(2), PDF p.129]. A building counts as one occupancy only when all of its uses fall in the same group, or the same division where the group has divisions [Div B, Sentence 3.1.2.2.(1), PDF p.130].
- An arena-type building used occasionally for trade shows is Group A, Division 3 [Div B, Sentence 3.1.2.3.(1), PDF p.130].
- A police station with detention quarters is Group B, Division 2 if it is one storey and 600 m² or less in building area [Div B, Sentence 3.1.2.4.(1), PDF p.130].
- Convalescent and children's custodial homes are residential within Part 3 if occupants are ambulatory, they live as one housekeeping unit in a suite, and sleeping accommodation is for 10 persons or fewer [Div B, Sentence 3.1.2.5.(1), PDF p.130].
- Buildings used to store baled combustible fibres are Group F, Division 2 [Div B, Sentence 3.1.2.6.(1), PDF p.130].
- Section 3.9 applies to self-service storage buildings that are one storey, have no basement or mezzanine, have only external access to their storage units, are used for storage only, and hold no other major occupancy, subject to the exceptions in Sentences 3.9.3.1.(2) and (4) [Div B, Sentence 3.9.1.2.(1), PDF p.320]. Those buildings are classified as Group F, Division 2 [Div B, Sentence 3.9.1.3.(1), PDF p.320].

Part 9 applicability and classification
- Part 9 applies to buildings of three storeys or less, with building area of 600 m² or less, used for Group B, Division 4, C, D, E, F-2 or F-3 [Div A, Sentence 1.3.3.3.(1), PDF p.40].
- Part 3 applies to post-disaster buildings, to Group A, Group B and Group F, Division 1 buildings at any size, and to Group C, D, E, F-2 and F-3 buildings over 600 m² or over three storeys [Div A, Sentence 1.3.3.2.(1), PDF pp.39-40].
- The Part 9 occupancy table lists B-4 (home-type care), C, D, E, F-2 and F-3. Its F-3 entry excludes storage garages that serve individual dwelling units [Div B, Sentence 9.10.2.1.(1), PDF p.876] [Div B, Table 9.10.2.1, PDF p.876].
- Children's custodial and convalescent homes for ambulatory occupants living as a single housekeeping unit in a dwelling unit, with sleeping accommodation for 10 persons or fewer, are Group C in Part 9 [Div B, Sentence 9.10.2.2.(1), PDF p.876]. The Part 3 version says "suite" where Part 9 says "dwelling unit" [Div B, Sentence 3.1.2.5.(1), PDF p.130].

Separation between major occupancies (Part 3 Section 3.1.3)
- Major occupancies must be separated by fire separations rated per Table 3.1.3.1 [Div B, Sentence 3.1.3.1.(1), PDF p.130] [Div B, Table 3.1.3.1, PDF p.131]. The Group C to Group E cell is 2 h, with note (5) pointing to the reduction below [Div B, Table 3.1.3.1, PDF p.131].
- The rating may drop to 1 h in a building of three storeys or less that holds not more than two dwelling units together with a Group E occupancy [Div B, Sentence 3.1.3.1.(2), PDF p.131].
- No separation is needed at the vertical plane around an opening through a horizontal separation when Articles 3.2.8.2 to 3.2.8.8 are met [Div B, Sentence 3.1.3.1.(3), PDF p.131].
- A Group F, Division 1 occupancy may not share a building with Group A, B or C occupancies [Div B, Sentence 3.1.3.2.(1), PDF p.131]. A Group F, Division 2 building may hold no more than one residential suite [Div B, Sentence 3.1.3.2.(2), PDF p.131].

Barrier-free design (Section 3.8)
- Section 3.8 deals with the barrier-free design of buildings [Div B, Sentence 3.8.1.1.(1), PDF p.301]. Buildings required to be barrier-free under Subsection 3.8.2 are designed under Subsection 3.8.3 [Div B, Sentence 3.8.1.1.(2), PDF p.301].
- Section 3.8 does not apply to the house types listed in Sentence 3.8.2.1.(1), to Group F, Division 1 buildings, to buildings not intended for daily or full-time occupancy, or to relocatable industrial accommodation [Div B, Sentence 3.8.2.1.(1), PDF p.301]. Note A-3.8.2.1 says the requirements are to be applied with discretion in Group F, Division 2 and 3 buildings, where construction or processes can make compliance impracticable, and that accessibility can reasonably be required where an industrial building has subsidiary offices or showrooms [Div B, Note A-3.8.2.1, PDF p.398].
- Except for service entrances and some suite entrances, every pedestrian entrance to a barrier-free storey is barrier-free and connects to a barrier-free exterior path [Div B, Sentence 3.8.2.2.(1), PDF p.302]. A barrier-free entrance is designed under Subsection 3.8.3 [Div B, Sentence 3.8.2.2.(2), PDF p.302].
- A barrier-free path of travel runs from the barrier-free entrances through the entrance storey and the other normally occupied floor areas [Div B, Sentence 3.8.2.3.(1), PDF p.302].
- The path is not required to service rooms, elevator machine rooms, janitors' rooms, service spaces, crawl spaces, attic or roof spaces, parking levels with no barrier-free stalls, or suite floors that are not at the suite's entry level. It is also not required for the floor above or below the entry level in buildings of two storeys or less, subject to the conditions in Clause 3.8.2.3.(2)(g) [Div B, Sentence 3.8.2.3.(2), PDF p.302].
- In an assembly occupancy, the number of wheelchair spaces in rooms or areas with fixed seats follows Table 3.8.2.3 [Div B, Sentence 3.8.2.3.(3), PDF p.302].
- A barrier-free path runs from a barrier-free entrance to designated barrier-free parking that is not in a storage garage, and to the other exterior points listed in the same sentence [Div B, Sentence 3.8.2.5.(1), PDF p.303].
- Except as Sentence (3) permits, where washrooms are provided on a storey with a barrier-free path, at least one universal washroom that meets Subsection 3.8.3 is required [Div B, Sentence 3.8.2.8.(1), PDF p.304]. Sentence (3) exempts washrooms inside residential suites that are not designated accessible under Sentence 3.8.1.1.(3), and washrooms in care-occupancy suites [Div B, Sentence 3.8.2.8.(3), PDF p.304].
- A barrier-free path is at least 1 000 mm clear, except where another provision or the doorway article governs [Div B, Sentence 3.8.3.2.(1), PDF p.306].
- Where a passenger elevator is used on a barrier-free path, the features in Appendix E of ASME A17.1/CSA B44 apply [Div B, Sentence 3.8.3.7.(1), PDF p.309]. A platform-equipped device needs a floor space of at least 1 500 mm by 1 000 mm and entry doors that are at least 850 mm clear on a short side, or 1 000 mm clear at either end of a long side [Div B, Sentence 3.8.3.7.(2), PDF p.310].
- A residential project of 10 or more dwelling units funded in whole or in part by the Government of Alberta must provide one adaptable dwelling unit per 10 units [Div B, Sentence 3.8.1.1.(3), PDF p.301]. Adaptable units are designed under Subsection 3.8.4 [Div B, Sentence 3.8.4.1.(1), PDF p.317].
- Physician clinics and offices have their own rules. Doorways on the barrier-free path are at least 915 mm clear, doors have power operators, the main waiting area allows a 1 700 mm turning circle, and one in five examination rooms and one in five treatment rooms meet the same standard [Div B, Sentence 3.8.5.2.(1), PDF p.319] [Div B, Sentence 3.8.5.2.(2), PDF p.319] [Div B, Sentence 3.8.5.2.(3), PDF p.319] [Div B, Sentence 3.8.5.3.(1), PDF p.319] [Div B, Sentence 3.8.5.3.(2), PDF p.319].

Fire protection on barrier-free floors
- Sentence 3.3.1.7.(1) sets clauses (a) to (e) for a floor area above or below the first storey that is not sprinklered throughout and has a barrier-free path [Div B, Sentence 3.3.1.7.(1), PDF p.248]. Clause (a) requires an elevator that meets fire and smoke conditions. Clause (b) requires at least two fire zones in which persons with physical disabilities can be accommodated. Clause (c) requires balconies in residential occupancies, except on the storey with the barrier-free entrance. Clause (d) or (e) requires an exterior exit at ground level or a ramp to ground level. The printed text has "or" only between clauses (d) and (e). Whether (a) and (b) are alternatives is UNVERIFIED. The explanatory note describes the elevator as a firefighter-used means of evacuating persons with disabilities [Div B, Note A-3.3.1.7.(1), PDF p.387].

Part 9 buildings and Section 3.8
- Part 9 buildings must conform to Section 3.8 unless Article 9.5.2.3 or Sentence 3.8.2.1.(1) applies [Div B, Sentence 9.5.2.1.(1), PDF p.840]. This is the main point where Part 9 and Part 3 differ for accessibility. A Part 9 mercantile or business building that is not a house is still subject to Section 3.8.
- Where a barrier-free path is provided above the first storey, Article 3.3.1.7 applies [Div B, Sentence 9.5.2.2.(1), PDF p.840].
- In an apartment building without an elevator, the barrier-free path is needed only on the entrance level. It is not needed where the floor difference between the entrance level and every dwelling unit exceeds 600 mm [Div B, Sentence 9.5.2.3.(1), PDF p.840] [Div B, Sentence 9.5.2.3.(2), PDF p.840].
- The Part 9 ramp rules do not apply to ramps in a barrier-free path of travel, and the Part 9 landing rules do not apply to landings for those ramps [Div B, Sentence 9.8.5.1.(1), PDF p.855] [Div B, Sentence 9.8.6.1.(1), PDF p.856].

## Attributions
Table 3.10.1.1, "Objectives and Functional Statements Attributed to the Acceptable Solutions in Part 3," starts at the separation rows of Part 3 [Div B, Table 3.10.1.1, PDF p.321]. It has no rows for Articles 3.1.2.1 to 3.1.2.6, because the classification articles carry no attributions. The codedb status for each classification sentence is "none" [Div B, Sentence 3.1.2.1.(1), PDF p.129] [Div B, Sentence 3.1.2.5.(1), PDF p.130]. The CWC guide notes that many Division B requirements have no attributed objectives or functional statements, which makes alternative solutions harder to prepare [source p.6].

Each row below is one provision and its attribution pairs. The objective and functional statement wording is paraphrased, with the source page for each.

| Article | Attribution pair (Div B Table 3.10.1.1.) | Objective (Div A) | Functional statement (Div A) |
|---|---|---|---|
| Div B 3.1.3.1.(1) | [F03-OS1.2] (PDF p.321) | OS1.2, fire or explosion impacting areas beyond its point of origin [Div A, Sentence 2.2.1.1.(1), PDF pp.68-73] | F03, retard the effects of fire on areas beyond its point of origin [Div A, Sentence 3.2.1.1.(1), PDF p.79] |
| Div B 3.1.3.1.(1) | [F03-OP1.2] (PDF p.321) | OP1.2, fire or explosion impacting areas beyond its point of origin, for property [Div A, Sentence 2.2.1.1.(1), PDF p.72] | F03, as above [Div A, Sentence 3.2.1.1.(1), PDF p.79] |
| Div B 3.1.3.1.(2) | [F03-OS1.2] (PDF p.321) | OS1.2, as above [Div A, Sentence 2.2.1.1.(1), PDF pp.68-73] | F03, as above [Div A, Sentence 3.2.1.1.(1), PDF p.79] |
| Div B 3.1.3.1.(3) | [F02,F03,F06-OS1.2] and [F10,F05-OS1.5] and [F02,F03,F06-OP1.2] (PDF p.321) | OS1.2; OS1.5, persons delayed in or impeded from moving to a safe place during a fire emergency [Div A, Sentence 2.2.1.1.(1), PDF pp.68-73]; OP1.2 | F02, limit the severity and effects of fire or explosions [Div A, Sentence 3.2.1.1.(1), PDF p.79]; F06, retard the effects of fire on facilities for notification, suppression and emergency response [Div A, Sentence 3.2.1.1.(1), PDF p.80]; F10, facilitate the timely movement of persons to a safe place in an emergency [Div A, Sentence 3.2.1.1.(1), PDF p.80]; F05, retard the effects of fire on emergency egress facilities [Div A, Sentence 3.2.1.1.(1), PDF p.80] |
| Div B 3.1.3.2.(1) | [F02,F03-OS1.2] and [F10-OS1.5] (PDF p.321) | OS1.2; OS1.5 [Div A, Sentence 2.2.1.1.(1), PDF pp.68-73] | F02, F03, F10 [Div A, Sentence 3.2.1.1.(1), PDF pp.79-80] |
| Div B 3.1.3.2.(2) | [F02,F03-OS1.2] (PDF p.321) | OS1.2 [Div A, Sentence 2.2.1.1.(1), PDF pp.68-73] | F02, F03 [Div A, Sentence 3.2.1.1.(1), PDF pp.79-80] |
| Div B 3.3.1.7.(1) | [F06-OS1.5] and [F10,F05-OS1.5] (Div B Table attribution, PDF p.342) | OS1.5 [Div A, Sentence 2.2.1.1.(1), PDF pp.68-73] | F06, F10, F05 [Div A, Sentence 3.2.1.1.(1), PDF pp.79-80] |
| Div B 3.8.2.2.(1) | [F73-OA1] (PDF p.352) | OA1, barrier-free path of travel: limit the probability that a person with a physical or sensory limitation is unacceptably impeded from accessing the building or circulating within it [Div A, Sentence 2.2.1.1.(1), PDF p.71] | F73, facilitate access to and circulation in the building and its facilities by persons with physical or sensory limitations [Div A, Sentence 3.2.1.1.(1), PDF p.81] |
| Div B 3.8.2.2.(4) | [F73-OA1] (PDF p.352) | OA1 [Div A, Sentence 2.2.1.1.(1), PDF p.71] | F73 [Div A, Sentence 3.2.1.1.(1), PDF p.81] |
| Div B 3.8.2.3.(1) | [F73-OA1] (PDF p.352) | OA1 [Div A, Sentence 2.2.1.1.(1), PDF p.71] | F73 [Div A, Sentence 3.2.1.1.(1), PDF p.81] |
| Div B 3.8.2.3.(3) | [F74-OA2] (PDF p.352) | OA2, barrier-free facilities: limit the probability that a person with a physical or sensory limitation is unacceptably impeded from using the building's facilities [Div A, Sentence 2.2.1.1.(1), PDF p.71] | F74, facilitate the use of the building's facilities by persons with physical or sensory limitations [Div A, Sentence 3.2.1.1.(1), PDF p.81] |
| Div B 3.8.2.5.(1) | [F73-OA1] (PDF p.352) | OA1 [Div A, Sentence 2.2.1.1.(1), PDF p.71] | F73 [Div A, Sentence 3.2.1.1.(1), PDF p.81] |
| Div B 3.8.2.8.(1) | [F74-OA2], [F72-OH2.1], [F71-OH2.3] (PDF p.352) | OA2 [Div A, Sentence 2.2.1.1.(1), PDF p.71]; OH2.1, exposure to human or domestic waste; OH2.3, inadequate facilities for personal hygiene [Div A, Sentence 2.2.1.1.(1), PDF p.70] | F74 [Div A, Sentence 3.2.1.1.(1), PDF p.81]; F72, provide facilities for the sanitary disposal of human and domestic wastes [Div A, Sentence 3.2.1.1.(1), PDF p.81]; F71, provide facilities for personal hygiene [Div A, Sentence 3.2.1.1.(1), PDF p.81] |
| Div B 3.8.3.2.(1) | [F73-OA1] (PDF p.352) | OA1 [Div A, Sentence 2.2.1.1.(1), PDF p.71] | F73 [Div A, Sentence 3.2.1.1.(1), PDF p.81] |
| Div B 3.8.3.7.(2) | [F10-OS3.7], [F30-OS3.1], [F73-OA1], [F74-OA2] (Div B Table attribution, PDF p.353) | OS3.7, persons delayed in or impeded from moving to a safe place during an emergency; OS3.1, injury from tripping or slipping [Div A, Sentence 2.2.1.1.(1), PDF p.69]; OA1; OA2 | F10 [Div A, Sentence 3.2.1.1.(1), PDF p.80]; F30, minimize the risk of injury from tripping, slipping, falling, contact, drowning or collision [Div A, Sentence 3.2.1.1.(1), PDF p.80]; F73; F74 |

Application limits on the accessibility pairs
- Objective OA (and so OA1 and OA2) does not apply to the house types listed, to Group F, Division 1 buildings, or to buildings not intended for daily or full-time occupancy [Div A, Sentence 2.1.1.2.(5), PDF p.67].
- Functional statements F73 and F74 have the same three exclusions [Div A, Sentence 3.1.1.2.(3), PDF p.79]. Their own wording points to that exclusion [Div A, Sentence 3.2.1.1.(1), PDF p.81].
- The objective OS3.7 and the function F10 both appear in the Div B 3.8.3.7.(2) row. The text of OS3.7 is read from [Div A, Sentence 2.2.1.1.(1), PDF p.69]. Its wording beyond that line is UNVERIFIED, because the extracted text is cut at "during an emer".

## Intent
The entries below paraphrase the NBC 2020 Intent Statements. That supplement is explanatory only. It is not Alberta law, and it does not replace the NBC(AE) 2023 text. The label comes before each citation.

Classification and separation (Part 3)
- NBC 2020 Intent Statements, 3.1.2.1.(1) [PDF p.54]: classify buildings or parts of buildings by use and occupancy, so that the right requirements apply.
- NBC 2020 Intent Statements, 3.1.2.1.(2) [PDF p.55]: classify a building by all of its major uses and occupancies.
- NBC 2020 Intent Statements, 3.1.2.2.(1) [PDF p.55]: treat a building as a single major occupancy only when all its uses fall in one group, or one division of a group.
- NBC 2020 Intent Statements, 3.1.2.3.(1) [PDF p.55]: classify occasional-use arena buildings as Group A, Division 3, and exempt them from the Group E classification in 3.1.2.1.(1).
- NBC 2020 Intent Statements, 3.1.2.4.(1) [PDF p.55]: classify small police stations with detention as Group B, Division 2, and exempt them from Group B, Division 1.
- NBC 2020 Intent Statements, 3.1.2.5.(1) [PDF p.55]: classify convalescent and children's custodial homes as residential when they meet the size and occupant limits.
- NBC 2020 Intent Statements, 3.1.2.6.(1) [PDF p.55]: classify storage of baled combustible fibres as medium-hazard industrial.
- NBC 2020 Intent Statements, 3.1.3.1.(1) [PDF p.56]: limit the chance that fire spreads from one major occupancy into an adjacent one with a different fire risk, which could harm persons (OS1) or damage the building (OP1).
- NBC 2020 Intent Statements, 3.1.3.1.(2) [PDF p.56]: allow a 1 h separation between a dwelling unit and a mercantile occupancy in a building of three storeys or less, because the limited number of units and the height restriction address evacuation times.
- NBC 2020 Intent Statements, 3.1.3.1.(3) [PDF pp.56-57]: exclude the plane around an open space between storeys from separation, where design conditions and the open-space measures it cross-references are met, so that evacuation times, fuel load and fire spread, and tenable conditions along exits are controlled.
- NBC 2020 Intent Statements, 3.1.3.2.(1) [PDF p.57]: limit the chance that an explosion or fast fire in a Group F, Division 1 occupancy harms people in an assembly, residential, or care or detention occupancy.
- NBC 2020 Intent Statements, 3.1.3.2.(2) [PDF p.57]: limit the chance that a fire in a medium-hazard Group F, Division 2 building harms people in a residential suite.

Accessibility (Section 3.8 and related)
- NBC 2020 Intent Statements, 3.8.1.1.(1) [PDF p.726]: state the scope of barrier-free design.
- NBC 2020 Intent Statements, 3.8.2.1.(1) [PDF p.726]: state the application of barrier-free design.
- NBC 2020 Intent Statements, 3.8.2.2.(1) [PDF p.726]: limit the chance that a person using a wheelchair or other assistive device cannot readily and conveniently enter a building (OA1).
- NBC 2020 Intent Statements, 3.8.2.3.(1) [PDF p.727]: limit the chance that such a person cannot move about in a building, or use its facilities, without another person's help (OA1).
- NBC 2020 Intent Statements, 3.8.2.5.(1) [PDF p.729]: limit the chance that such a person cannot travel between a building entrance and the exterior (OA1).
- NBC 2020 Intent Statements, 3.8.2.8.(1) [PDF p.730]: state when universal washrooms apply under the barrier-free design rules, and limit the chance that such a person cannot use a universal washroom independently (OA2 and OH2).
- NBC 2020 Intent Statements, 3.8.3.2.(1) [PDF p.736]: limit the chance that such a person cannot circulate within a building without help (OA1).
- NBC 2020 Intent Statements, 3.8.3.7.(1) [PDF p.748]: limit the chance that such a person cannot approach, use and maneuver into or out of a passenger-elevating device (OA1), and that the device does not meet proper standards (OS3).
- NBC 2020 Intent Statements, 3.3.1.7.(1) [PDF p.526]: limit the chance that persons with physical disabilities are not protected or are delayed in evacuating, and that emergency responders are delayed in a fire response (OS1).

Part 9
- NBC 2020 Intent Statements, 9.10.2.1.(1) [PDF p.1343]: classify buildings by use and occupancy to determine the requirements that apply.
- NBC 2020 Intent Statements, 9.10.2.2.(1) [PDF p.1343]: classify certain convalescent and children's custodial homes as residential when they are limited in size and number of occupants.

Page check. The intent PDF was read or searched for the entries listed above, and pages 54-57, 726, 729 and 748 were checked that way. The other page numbers come from the codedb intent parse and are not checked by eye. Where the 2020 intent text and the 2023 text differ, the 2023 text governs. The note on discretion for Group F, Division 2 and 3 buildings is an explanatory note, not an intent statement. It is cited in the Benchmark section.

## Typical alternative solutions
The proposals below are the ones the sources describe. Each was written as a STANDATA or interpretation with conditions, or it is an open proposal with no decision recorded. None is a template for a new application.

- Reclassify a Group F, Division 1 oil or gas processing building as F-2. The STANDATA allows this for a building of 150 m² or less, that is low human occupancy, outside urban areas, and houses oil or gas processing equipment. It requires a risk assessment by an Alberta-licensed registered engineering professional, with ventilation, gas detection, emergency shutdown stations and listed fire detection [23-BCV-005, source p.2]. The STANDATA excludes offices, warehousing and other buildings on the same site [23-BCV-005, source p.2].
- Reclassify a Group F, Division 1 natural gas regulating or metering building as F-2. The STANDATA allows this for a building that does not exceed 55 m² in building area or one storey in building height, that is low human occupancy, with ventilation meeting the sentence it cites [23-BCV-006, source p.2].
- Put a restaurant or beverage establishment in an F-1 building, such as a flour mill, distillery or cereal mill. Sentence 3.1.3.2.(1) bars F-1 with Group A, B or C occupancies [Div B, Sentence 3.1.3.2.(1), PDF p.131]. A restaurant is a Group A, Division 2 example [Div B, Note A-3.1.2.1.(1), PDF p.357]. The variance route is described in 23-BCI-024, which also covers treating an F-1 occupancy as presenting a risk similar to F-2 [23-BCI-024/23-FCI-008, source p.1].
- Run a greenhouse with public access. The later 23-BCV-011R1 has two options. Option 2 requires a one-storey building classed as Group F, Division 3, with public access limited to plant retail, aisles at least 1.1 m wide, exit doors widened by 40% (not less than 1 190 mm), and an occupant load based on 4.6 m² per person for the areas the clause covers (the full clause was not read) [23-BCV-011R1, source p.2].
- Treat multi-level storage racking as a special and unusual structure under Article 3.2.2.2, designed by good fire protection engineering practice, because the code has no specific rule for it. The STANDATA notes that some SCOs have read these racks as storeys, mezzanines or interconnected floor spaces [23-BCV-014, source p.1].
- Use a passenger elevator instead of a platform lift or limited-use/limited-application elevator for barrier-free access. The conditions include vertical travel of 7 620 mm or less, car dimensions at least the minimum in Sentence 3.8.3.7.(2), no firefighter emergency operation elements for a lift replacement, and permit documents supplied to the authority having jurisdiction [23-BCV-013, source pp.2-3].
- Design a supportive living building as Group B, Division 3 care occupancy. Some authorities having jurisdiction have required Group B, Division 2 treatment occupancy instead, citing occupant self-evacuation and the design of the building [23-BCI-019, source p.1]. Its stated purpose is to clarify how occupancy classification applies to these facilities [23-BCI-019, source p.1]. Its remaining pages were not read.

## Usual mitigations and evidence
The mitigations are the conditions written into each alternative. Reviewers in this topic rely on the STANDATA conditions and on the evidence they require. The list below names what each source asks for.

- Area and occupancy limits. 23-BCV-005 limits the building to 150 m² and low human occupancy, and 23-BCV-006 limits it to a building that does not exceed 55 m² in building area or one storey in building height [source p.2 of each].
- Ventilation and detection. 23-BCV-005 requires ventilation rates tied to electrical area classification under API RP500, at least six air changes per hour, combustible or toxic gas detection, emergency shutdown stations with remote activators, and listed fire detection that shuts down and depressurizes the facility [source p.2].
- Flame performance. For greenhouse film, 23-BCV-011R1 accepts a flame spread rating of 25 or less in place of CAN/ULC-S109 [source p.2]. CAN/ULC-S109 is the flame test named in Article 3.1.18.5 [23-BCV-011, source p.1].
- Barrier-free devices. 23-BCV-013 relies on ASME A17.1/CSA B44 and on CSA B355 for platform lifts [source pp.2-3]. The features of Appendix E of ASME A17.1/CSA B44 apply to passenger elevators on a barrier-free path [Div B, Sentence 3.8.3.7.(1), PDF p.309].
- Engineering evidence. 23-BCV-005 requires a registered engineering professional's risk assessment [source p.2]. 23-BCI-024 says it is not a design or evaluation guide for the engineering analysis that a variance requires [source p.1].
- Administrative evidence. A barrier-free relaxation requires a demonstration to the administrator that a requirement is unnecessary or that extraordinary circumstances prevent conformance [Div C, Sentence 2.2.1.4.(1), PDF p.730]. Relaxations are not issued to lower costs, to correct a missed code requirement, to fix construction errors, or to avoid harder design alternatives [23-BCI-016R1, source p.1].

Evidence ranking used in this sheet. The ranking below is this sheet's own ordering of sources. The code does not rank them.
1. The NBC(AE) 2023 2nd printing text, as printed and as checked in the extracted pages. This is the only citable building code.
2. STANDATA variances and interpretations issued by the Provincial Building Administrator or the Provincial Barrier-Free Administrator. Each states its scope, such as "applicable throughout the Province of Alberta" for a variance, and each has conditions.
3. Individual relaxations under Sentence 2.2.1.4.(1), which are decided case by case.
4. Explanatory notes in the NBC(AE) 2023 and the NBC 2020 Intent Statements. The intent statements are explanatory only.
5. Guides and industry texts. The CWC guide is written around BC Building Code examples [source p.9], so it is not Alberta authority. The SCC barrier-free guide's edition is UNVERIFIED (see Open questions).

## Engineering / professional triggers
- A registered professional is not required for the building types listed in Sentence 2.4.1.1.(1). Those include a farm building not for public use and a relocatable industrial camp building [Div C, Sentence 2.4.1.1.(1), PDF pp.739-740]. The business, mercantile and industrial rows are limited by storeys and building area, for example one storey and 500 m² or less [Div C, Sentence 2.4.1.1.(1), PDF pp.739-740].
- For any other building, drawings and specifications must be authenticated by one or more registered professionals [Div C, Sentence 2.4.1.1.(3), PDF p.740]. Each professional authenticates under the Architects Act or the Engineering and Geoscience Professions Act [Div C, Sentence 2.4.1.1.(5), PDF p.740].
- The authority having jurisdiction may require registered professionals to authenticate drawings and perform field reviews where size or complexity raises special safety concerns [Div C, Sentence 2.4.1.1.(4), PDF p.740].
- Part 4 structural design must be done by a registered professional skilled in the work [Div C, Sentence 2.4.1.2.(1), PDF p.740]. The occupancy sets the importance category for loads [Div B, Sentence 4.1.2.1.(3), PDF p.424].
- An F-1 to F-2 reclassification under 23-BCV-005 needs a risk assessment by an Alberta-licensed registered engineering professional [source p.2].
- A barrier-free relaxation is granted or refused by the Provincial Barrier-Free Administrator or the Provincial Building Administrator, not by a professional stamp. The owner must make the demonstration to the administrator [Div C, Sentence 2.2.1.4.(1), PDF p.730].
- Whether classifying an occupancy needs a professional's judgment is UNVERIFIED. None of the sentences read for this sheet says so.

## Interactions with other topics
- combustible-construction-and-mass-timber. The construction limits in Subsection 3.2.2 depend on major occupancy, building height and building area [source p.8 of the CWC guide].
- egress-and-single-stair. Travel distance is set in Clause 3.4.2.5.(1) [Div B, Sentence 3.3.1.6.(1), PDF p.248]. Protection of barrier-free floor areas in Sentence 3.3.1.7.(1) also meets egress and fire protection [Div B, Sentence 3.3.1.7.(1), PDF p.248].
- fire-separations-and-spatial-separation. Table 3.1.3.1 sets occupancy separations in this sheet. The construction of the separations and the zone fire separations in Sentence 3.3.1.7.(1) belong to the fire separation topic.
- structural-and-framing. The importance category for loads depends on intended use and occupancy [Div B, Sentence 4.1.2.1.(3), PDF p.424].
- professional-involvement. The thresholds for registered professional involvement in Div C Sentence 2.4.1.1.(1) are owned by that topic [Div C, Sentence 2.4.1.1.(1), PDF pp.739-740].
- process-and-admin and evidence-and-conformity. Variance and relaxation routes are in Division C. The barrier-free relaxation sentence is in Sentence 2.2.1.4.(1) [Div C, Sentence 2.2.1.4.(1), PDF p.730].
- hvac-ventilation-plumbing. The ventilation conditions in 23-BCV-005 and 23-BCV-006 belong to that topic. This sheet covers only the universal washroom rule [Div B, Sentence 3.8.2.8.(1), PDF p.304].
- firefighting-alarms-sprinklers. Whether a floor area is sprinklered throughout changes the answer under Sentence 3.3.1.7.(1) [Div B, Sentence 3.3.1.7.(1), PDF p.248]. In a Part 9 building, a fire alarm system is required where the building has more than three storeys, the total occupant load exceeds 300, or the occupant load for a major occupancy exceeds Table 9.10.18.2 [Div B, Sentence 9.10.18.2.(2), PDF p.908].
- housing-secondary-suites-part9. Part 9 buildings that are not houses must conform to Section 3.8, subject to Article 9.5.2.3 [Div B, Sentence 9.5.2.1.(1), PDF p.840]. The houses are excluded [Div B, Sentence 3.8.2.1.(1), PDF p.301]. The window control device variance excludes adaptable and barrier-free dwelling units [23-BCV-001, source p.3].
- building-envelope-insulation-cladding. Part 11 applies to buildings in an airport vicinity protection area that are subject to acoustic insulation requirements [Div B, Sentence 11.1.1.1.(1), PDF p.1517].
- code-structure-and-attribution. The Table 3.10.1.1 pairs in Section 4 use the attribution format that topic owns.

## Common refusal / "more info" causes
Each cause below is either written in a source or follows from a cited sentence. Where a source does not say that the cause is common in practice, the item is marked.

- Treating the examples in Note A-3.1.2.1.(1) as the whole test. The CWC guide reports that authorities often read these examples as definitions and not as guidance for further evaluation [source p.8].
- Classifying only the main use of a mixed building. A building is classified under every major occupancy it contains [Div B, Sentence 3.1.2.1.(2), PDF p.129].
- Leaving out the building area and building height that decide between Part 3 and Part 9 [Div A, Sentence 1.3.3.2.(1), PDF pp.39-40] [Div A, Sentence 1.3.3.3.(1), PDF p.40].
- Proposing a Group B, Division 3 care classification for a supportive living building. Some authorities have required Group B, Division 2 instead, for reasons that include self-evacuation and the design of the building [23-BCI-019, source p.1].
- Putting a Group A occupancy, such as a restaurant, in a Group F, Division 1 building without a variance. Div B Sentence 3.1.3.2.(1) bars that combination [Div B, Sentence 3.1.3.2.(1), PDF p.131] [23-BCI-024/23-FCI-008, source p.1].
- Asking for an F-1 to F-2 reclassification without the STANDATA conditions, such as the 150 m² limit and the engineer's risk assessment in 23-BCV-005 [source p.2].
- Asking for a barrier-free relaxation to lower construction costs, to correct a missed requirement, to fix construction errors, or to avoid a harder design. These are not issued [23-BCI-016R1, source p.1]. The same STANDATA says that requests lacking the required AHJ review at the building permit stage are being received [23-BCI-016R1, source p.1].
- Claiming the farm building exclusion without the low-human-occupancy and listed-use facts [Div A, Sentence 1.1.1.1.(4), PDF pp.37-38] [Div A, Note A-1.1.1.1.(4)(a), PDF pp.55-56]. Claiming the professional exemption for a farm building needs facts showing that the building is not for public use [Div C, Sentence 2.4.1.1.(1), PDF p.740].
- Missing barrier-free entrance, path and washroom detail on the drawings. Which of these an SCO treats as a refusal ground is UNVERIFIED. The sentences that require them are cited in the Benchmark section.
- Citing 2019 or British Columbia code numbers. The 2023 Alberta edition governs. The CWC guide is built on BC Building Code examples [source p.9]. The 23-BCV-005 STANDATA quotes an egress table, Table 3.3.1.5.A, that I could not find in the extracted 2023 text (see Open questions).

## Precedents
Current STANDATA, interpretation and bulletin entries are listed by number, date and the page read. Historical 14-BCV and 19-BCV entries exist in the precedent index for the same topics, and they are not citable as current law.

- STANDATA 23-BCV-001, Window opening control devices, April 2024. It excludes window control devices from adaptable and barrier-free dwelling units [source p.3].
- STANDATA 23-BCV-005, Occupancy classification of oil and gas processing buildings, May 2024. It allows Group F, Division 2 under the conditions in Typical alternative solutions [source pp.1-2].
- STANDATA 23-BCV-006, Occupancy classification of natural gas regulating and metering buildings, May 2024. It allows Group F, Division 2 under the conditions in Alternatives [source pp.1-2].
- STANDATA 23-BCV-011, Polyethylene film for greenhouse enclosures, February 2025. Its purpose covers greenhouses occupied only by staff. The later 23-BCV-011R1 extends the purpose to greenhouses with public access [source p.1 of each]. Whether 23-BCV-011R1 formally supersedes it is UNVERIFIED.
- STANDATA 23-BCV-011R1, same subject, October 2026. Option 1 covers greenhouses not open to the public. Option 2 covers public-access greenhouses classed as Group F, Division 3 [source p.2].
- STANDATA 23-BCV-013/19-EDB-002, Elevator and passenger-elevating devices, February 2026. It allows a passenger elevator in place of a lift or limited-use/limited-application elevator under conditions [source pp.2-3].
- STANDATA 23-BCV-014, Multi-level storage racking systems, March 2025. It allows the racks to be considered special and unusual structures under Article 3.2.2.2 [source p.1].
- STANDATA interpretation 23-BCI-016R1, Barrier-free design requirements: relaxations, November 2025. It sets out when a relaxation is appropriate [source p.1]. The index also lists an earlier 23-BCI-016 from March 2025, which was not read.
- STANDATA interpretation 23-BCI-019, Occupancy classification for supportive living accommodations, December 2025 [source p.1]. Pages 2 to 4 were not read.
- STANDATA interpretation 23-BCI-024/23-FCI-008, Variance process for industrial occupancy, August 2026. It covers F-1 to F-2 variances and restaurants in F-1 buildings [source p.1].
- STANDATA interpretation 23-BCI-032/23-FCI-005, Occupancy classification for buildings used for tank vehicles, July 2025 [source p.1]. Pages 2 and 3 were not read.
- STANDATA interpretation 23-BCI-034, Elevator operation and accessibility for residential buildings, March 2025 [source p.1]. Pages 2 to 4 were not read.
- STANDATA interpretation 23-BCB-004, Occupancy of buildings under construction, January 2025. The precedent index lists it, and it was not read.
- Edmonton policy B19-04, Small Building Access. The precedent index lists it, and it was not read. Its title does not indicate a Section 3.8 or occupancy topic.
- Calgary and Edmonton policies on occupancy or barrier-free design. None appeared in the precedent index's title search. This is UNVERIFIED beyond titles.
- The SCC barrier-free guide. Its edition is UNVERIFIED (see Open questions).

## Worked example
This is a hypothetical case for illustration. It is not an application and not a decision.

A developer proposes a new four-storey building of 1 200 m² building area. The ground floor is a shop of 300 m² (Group E). Floors 2 to 4 hold nine apartment units (Group C). The building is not sprinklered throughout. No government funding is involved.

Step 1, classify the uses. The building holds two major occupancies, Group E and Group C, so it is classified under both [Div B, Sentence 3.1.2.1.(2), PDF p.129]. Shops are Group E examples, and apartments are Group C examples [Div B, Note A-3.1.2.1.(1), PDF pp.356-359].

Step 2, choose the Part. Part 3 applies because the building is over three storeys and over 600 m² [Div A, Sentence 1.3.3.2.(1), PDF pp.39-40]. Part 9 does not apply, because it covers buildings of three storeys or less and 600 m² or less [Div A, Sentence 1.3.3.3.(1), PDF p.40].

Step 3, set the separation between the shop and the apartments. Table 3.1.3.1 gives 2 h for the Group C to Group E pair [Div B, Table 3.1.3.1, PDF p.131]. The 1 h relief in Sentence 3.1.3.1.(2) needs three storeys or less and not more than two dwelling units [Div B, Sentence 3.1.3.1.(2), PDF p.131]. This building has four storeys and nine units, so the relief does not apply. The attribution pairs for the separation are in the Section C table below.

Step 4, barrier-free design. Section 3.8 applies, because the building is not a house [Div B, Sentence 3.8.2.1.(1), PDF p.301]. The entrances to the shop and to the residential lobby must be barrier-free and connect to a barrier-free exterior path [Div B, Sentence 3.8.2.2.(1), PDF p.302]. A barrier-free path must run through the entrance storey and the other normally occupied floor areas [Div B, Sentence 3.8.2.3.(1), PDF p.302]. Whether the upper-floor corridors are normally occupied areas for this building, and so need the path, is a fact the applicant must establish. This sheet does not decide it. The residential suites are outside the path where they are not at the entry level of the suite [Div B, Sentence 3.8.2.3.(2), PDF p.302]. The adaptable dwelling unit rule does not apply, because the project is not government funded and has fewer than 10 units [Div B, Sentence 3.8.1.1.(3), PDF p.301]. Washrooms in the shop on the entrance storey need at least one universal washroom [Div B, Sentence 3.8.2.8.(1), PDF p.304]. Washrooms inside residential suites that are not designated accessible are exempt [Div B, Sentence 3.8.2.8.(3), PDF p.304].

Step 5, protect the barrier-free floors. The building is not sprinklered throughout, so Sentence 3.3.1.7.(1) applies to each floor above or below the first storey that has a barrier-free path [Div B, Sentence 3.3.1.7.(1), PDF p.248]. The clauses cover an elevator (a), two fire zones (b), residential balconies (c) on floors other than the entrance storey, and an exterior exit or ground-level ramp (d or e). The printed text puts "or" only between (d) and (e). Whether (a) and (b) are alternatives is UNVERIFIED, so the applicant has to read the printed page and the explanatory note before choosing.

Section C, attributions for this case. Each row is one provision and its attribution pair. The Section C table uses the pairs from Table 3.10.1.1 and the 2020 intent text, which is explanatory only.

| Article (Div B) | Attribution pair | Objective (Div A) | Function (Div A) | Intent (NBC 2020 Intent Statements, explanatory only) |
|---|---|---|---|---|
| Div B 3.1.3.1.(1), [Div B Sentence 3.1.3.1.(1), PDF p.130] | [F03-OS1.2] (Div B Table attribution, PDF p.321) | OS1.2, fire or explosion impacting areas beyond its point of origin [Div A, Sentence 2.2.1.1.(1), PDF pp.68-73] | F03, retard the effects of fire on areas beyond its point of origin [Div A, Sentence 3.2.1.1.(1), PDF p.79] | NBC 2020 Intent Statements, 3.1.3.1.(1) [PDF p.56] |
| Div B 3.1.3.1.(1), [Div B Sentence 3.1.3.1.(1), PDF p.130] | [F03-OP1.2] (Div B Table attribution, PDF p.321) | OP1.2, fire or explosion impacting areas beyond its point of origin, under the property-protection objective [Div A, Sentence 2.2.1.1.(1), PDF p.72] | F03, as above [Div A, Sentence 3.2.1.1.(1), PDF p.79] | NBC 2020 Intent Statements, 3.1.3.1.(1) [PDF p.56] |
| Div B 3.8.2.2.(1), [Div B Sentence 3.8.2.2.(1), PDF p.302] | [F73-OA1] (Div B Table attribution, PDF p.352) | OA1, barrier-free path of travel [Div A, Sentence 2.2.1.1.(1), PDF p.71] | F73, facilitate access to and circulation in the building and its facilities [Div A, Sentence 3.2.1.1.(1), PDF p.81] | NBC 2020 Intent Statements, 3.8.2.2.(1) [PDF p.726] |
| Div B 3.8.2.3.(1), [Div B Sentence 3.8.2.3.(1), PDF p.302] | [F73-OA1] (Div B Table attribution, PDF p.352) | OA1, barrier-free path of travel [Div A, Sentence 2.2.1.1.(1), PDF p.71] | F73, as above [Div A, Sentence 3.2.1.1.(1), PDF p.81] | NBC 2020 Intent Statements, 3.8.2.3.(1) [PDF p.727] |
| Div B 3.8.2.8.(1), [Div B Sentence 3.8.2.8.(1), PDF p.304] | [F74-OA2] (Div B Table attribution, PDF p.352) | OA2, barrier-free facilities [Div A, Sentence 2.2.1.1.(1), PDF p.71] | F74, facilitate the use of the building's facilities by persons with physical or sensory limitations [Div A, Sentence 3.2.1.1.(1), PDF p.81] | NBC 2020 Intent Statements, 3.8.2.8.(1) [PDF p.730] |
| Div B 3.3.1.7.(1), [Div B Sentence 3.3.1.7.(1), PDF p.248] (only if the floor area is not sprinklered throughout) | [F06-OS1.5] and [F10,F05-OS1.5] (Div B Table attribution, PDF p.342) | OS1.5, persons delayed in or impeded from moving to a safe place during a fire emergency [Div A, Sentence 2.2.1.1.(1), PDF pp.68-73] | F06, retard the effects of fire on facilities for notification, suppression and emergency response [Div A, Sentence 3.2.1.1.(1), PDF p.80]; F10, facilitate the timely movement of persons to a safe place in an emergency [Div A, Sentence 3.2.1.1.(1), PDF p.80]; F05, retard the effects of fire on emergency egress facilities [Div A, Sentence 3.2.1.1.(1), PDF p.80] | NBC 2020 Intent Statements, 3.3.1.7.(1) [PDF p.526] |

Explainer for each article in the table. 3.1.3.1.(1) sets the separation rule that the shop and apartment pair triggers, and the attribution pairs tie it to the fire spread objectives. 3.8.2.2.(1) and 3.8.2.3.(1) are the entrance and path rules, and both attribute to OA1 through F73. 3.8.2.8.(1) is the universal washroom rule, attributed to OA2 through F74. 3.3.1.7.(1) applies only when the floor area is not sprinklered throughout, and the attribution pairs are the fire-related ones in Table 3.10.1.1.

Two limits on this example. First, a Section C table shows what the code attributes to a provision, not whether a design meets the objective. Second, the intent text is from the 2020 national supplement. It explains the purpose and is not Alberta law.

## Open questions / uncertainty
- SCC barrier-free guide edition. Search results describe a fifth edition (June 2017, built on the 2014 code) and a 2024 sixth edition titled "Accessibility Design Guide". I tried to fetch the open.alberta.ca page for the fifth edition, and the server returned HTTP 520. The edition and the guide's content are UNVERIFIED, and this sheet cites no guide content.
- Barrier-free relaxation fee. A search summary reports $100 plus GST. The alberta.ca application page, fetched 2026-10-19, does not mention a fee. The fee is UNVERIFIED and is not stated here.
- Alberta amendments to barrier-free design. The national NBC 2020 text, which is explanatory context only, is not in the repo, so the 2023 sentences that differ from it cannot be listed here. That comparison is UNVERIFIED.
- Clauses (a) and (b) of Sentence 3.3.1.7.(1). The printed text puts "or" only between (d) and (e). Whether (a) and (b) are alternatives is UNVERIFIED. The explanatory note [Div B, Note A-3.3.1.7.(1), PDF p.387] was read in part only.
- Table 3.3.1.5.A. STANDATA 23-BCV-005 quotes this egress table for Group F, Division 2 (150 m², 10 m). I could not find the table in the extracted NBC(AE) 2023 text. It may come from an earlier edition or from the STANDATA itself. Resolve this before reusing the quote.
- 23-BCV-011R1 and 23-BCV-011. Whether the later revision formally supersedes the earlier STANDATA is UNVERIFIED. The text read says the scope is extended.
- Classification of data centres and vertical farms. Neither appears in the Div B Note A-3.1.2.1.(1) examples. Classification by an authority having jurisdiction is UNVERIFIED. The nearest checked analogues are the farm building exclusion in Div A Sentence 1.1.1.1.(4) and the greenhouse options in 23-BCV-011R1.
- Farm building definition. Permit Regulation AR 204/2007 defines "farm building" by reference to agricultural land and an agricultural operation [source p.5]. Its relationship to the farm exclusion in Div A Sentence 1.1.1.1.(4) is UNVERIFIED. Div A Note A-1.1.1.1.(4)(a) refers to the National Farm Building Code of Canada 1995, a historical reference. Whether Alberta uses it now is UNVERIFIED.
- Partly read STANDATA interpretations. 23-BCI-019 (pages 2 to 4), 23-BCI-032 (pages 2 and 3), 23-BCI-034 (pages 2 to 4) and 23-BCI-016 (the March 2025 version) were not fully read. Their conclusions are UNVERIFIED. 23-BCB-004 and the Edmonton B19-04 policy appear only as index entries.
- Calgary and Edmonton policies. The precedent index title search found no occupancy or barrier-free policy from Calgary or Edmonton. This is UNVERIFIED beyond titles.
- Part 10 and Part 11 design. Only the scope sentences were read: [Div A, Sentence 1.3.3.3.(2), PDF p.40], [Div B, Sentence 10.1.1.1.(1), PDF p.1499], and [Div B, Sentence 11.1.1.1.(1), PDF p.1517]. Their design requirements are UNVERIFIED.
- Adaptable dwelling units. Only Sentences 3.8.1.1.(3) and 3.8.4.1.(1) were read. The design requirements in Subsection 3.8.4 are UNVERIFIED.
- Part 9 separation of Group C and Group E. The 1 h relief in Sentence 3.1.3.1.(2) is cited from Part 3. The Part 9 rule for the same pair (Section 9.10) was not read in this sheet.
- Professional judgment for classification. Whether classifying an occupancy needs a professional's judgment is UNVERIFIED. None of the sentences read says so.
- Intent page numbers. For most intent citations, the page was checked by reading or searching the intent PDF. The rest come from the codedb intent parse and are not checked by eye (listed in the Intent section).
- Greenhouse Option 2 occupant load. The clause was not read in full (source p.2 of 23-BCV-011R1).
- Sentence 3.8.2.5.(1). Only the parking clause was read in full. The other exterior points it lists are UNVERIFIED.
- Validator. The result of `codedb validate` is reported in the final message, not here.

## Sources
Code (NBC(AE) 2023 2nd printing, reference/codes/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.pdf). Provisions cited with their pages: [Div A, Sentence 1.1.1.1.(4), PDF pp.37-38]; [Div B, Sentence 3.1.2.1.(1), PDF p.129]; [Div B, Sentence 3.1.3.1.(1), PDF pp.130-131]; [Div C, Sentence 2.2.1.4.(1), PDF p.730].

Other provisions read, with their pages: [Div A, Sentence 1.3.3.2.(1), PDF pp.39-40]; [Div A, Sentence 1.3.3.3.(1), PDF p.40]; [Div A, Sentence 2.1.1.2.(5), PDF p.67]; [Div A, Sentence 2.2.1.1.(1), PDF pp.68-73]; [Div A, Sentence 3.1.1.2.(3), PDF p.79]; [Div A, Sentence 3.2.1.1.(1), PDF pp.79-81]; [Div B, Sentence 3.3.1.6.(1), PDF p.248]; [Div B, Sentence 3.8.1.1.(1), PDF p.301]; [Div B, Sentence 3.8.5.3.(1), PDF p.319]; [Div B, Sentence 3.9.1.3.(1), PDF p.320]; [Div B, Table 3.10.1.1, PDF p.342]; [Div B, Table 3.10.1.1, PDF p.352]; [Div B, Note A-3.1.2.1.(1), PDF pp.356-359]; [Div B, Note A-3.3.1.7.(1), PDF p.387]; [Div B, Note A-3.8.2.1, PDF p.398]; [Div B, Sentence 4.1.2.1.(3), PDF p.424]; [Div B, Sentence 9.5.2.1.(1), PDF p.840]; [Div B, Sentence 9.8.5.1.(1), PDF p.855]; [Div B, Sentence 9.10.2.1.(1), PDF p.876]; [Div B, Sentence 9.10.18.2.(2), PDF p.908]; [Div B, Sentence 10.1.1.1.(1), PDF p.1499]; [Div B, Sentence 11.1.1.1.(1), PDF p.1517]; [Div C, Sentence 2.4.1.1.(5), PDF p.740].

Intent (NBC 2020 Intent Statements, explanatory only, reference/codes/NBC-2020-Intent-Statements.pdf, PDF pages): 54, 55, 56, 57, 526, 726, 727, 729, 730, 736, 748, 1343.

Alberta regulations: Permit Regulation AR 204/2007, reference/text/Permit-Regulation-AR-204-2007, source p.5.

STANDATA and interpretations (reference/text/, source pages): 23-BCV-001 (April 2024), p.3; 23-BCV-005 (May 2024), pp.1-2; 23-BCV-006 (May 2024), pp.1-2; 23-BCV-011 (February 2025), p.1; 23-BCV-011R1 (October 2026), pp.1-2; 23-BCV-013/19-EDB-002 (February 2026), pp.1-3; 23-BCV-014 (March 2025), p.1; 23-BCI-016R1 (November 2025), p.1; 23-BCI-019 (December 2025), p.1; 23-BCI-024/23-FCI-008 (August 2026), p.1; 23-BCI-032/23-FCI-005 (July 2025), p.1; 23-BCI-034 (March 2025), p.1.

Guide: CWC Alternative Solutions Guide (reference/guides/CWC-Alternative-Solutions-Guide.pdf), source pp.6, 8, 9. The guide is built on BC Building Code examples.

Precedent index: research/precedents/index.json (titles and dates only, used to find STANDATA entries; no claims taken from index fields).

Web (accessed 2026-10-19): https://alberta.ca/application-for-barrier-free-relaxation (fetched). The page names the Provincial Barrier-Free Administrator or Provincial Building Administrator as deciders, quotes the Sentence 2.2.1.4.(1) test, refers to NBC(AE) 2023, and has no fee. The SCC barrier-free guide search (WebSearch, standard) returned results but no fetched page; its edition is UNVERIFIED.
