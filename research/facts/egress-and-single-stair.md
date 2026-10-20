---
topic: egress-and-single-stair
scope: Means of egress under NBC(AE) 2023 (Div B 3.3 and 3.4; Part 9 9.9), with depth on single-exit-stair buildings (Point Access Blocks) and on ordinary egress variances (travel distance, dead-end corridors, exit width).
sources_checked:
  - NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2
  - NFC-AE-2023-2nd-printing
  - "NBC-2020-Intent-Statements, explanatory only"
  - SCC-Variance-Form
  - Edmonton-Point-Access-Block-Guide
  - Edmonton-Alt-Solutions-Emergency-Services
  - STANDATA-23-BCI-026-23-FCI-014
  - STANDATA-23-BCV-001
  - Edmonton-B23-05
  - Edmonton-Point-Access-Block-Technical-Report
  - Edmonton-Point-Access-Block-Building-Code-Guide
  - Edmonton-Point-Access-Block-Design-Guide
  - BC-Ministerial-Order-BA-2024-03
  - Seattle-2021-Building-Code-Chapter-10
  - NYC-2022-Code-Index-and-current-published-1006.3.2
  - CBHCC-code-priorities-and-proposed-changes-tracking-database
  - NRC-Consultation-on-single-egress-2025
  - singlestair.ca-KHA
  - Alberta-Engineering-and-Geoscience-Professions-Act
  - APEGA-common-terminology
last_verified: 2026-10-18
---
# Egress and single exit stair

## Progress
- Done: existing skeleton and partial benchmark, attribution and intent sections recovered on 2026-10-18. Required contracts, briefs, workflow, Matt Pocock research and pstack unslop methods read. Base HEAD verified as 02fb483d3afeac77ceb46066443b63dbc63dfc5b. Working code DB CLI available.
- Done: all template sections, current Alberta SES interpretation, foreign context, sources and the four-storey twelve-unit Section C example are saved. The code audit covers 60 body articles and two attribution tables. All 79 explicit NBC sentence/clause openings match their source-page text. All 27 listed national intent identifiers were found. Fifty exact attribution rows are recorded.
- Validation complete: full scan checked 642 citation tokens and reports one unsupported NFC-AE document error, zero warnings. The supported-code scope checked 640 tokens with zero errors and warnings. The retained NFC clause is directly checked against second-printing PDF page 355. No placeholders remain. Fresh and existing SES interpretation PDFs are byte-identical.
- Next for integration: rerun the full scanner once the database owner adds NFC-AE support. No topic-content work remains pending. No predecessor downloads were present; replacement sources are in the owned reference folder. No commits or other agents' file changes were made by this researcher.
- Scope: only this file and reference/web/egress-and-single-stair/ may be written. No evals, variants, source solutions, commits, pushes or further delegation. Keep this Progress block for resumability and save after each section.

## Plain-language summary

An egress route is the route people use to leave during an emergency. An exit is the protected portion that leads outside or to another defined safe destination.
A Point Access Block is an apartment building with homes clustered around one exit stair rather than two.
The usual apartment benchmark requires two exits so people and firefighters retain another route if one becomes unusable.
The second route protects both people and the building. A comparison limited to evacuation time misses part of that benchmark.
Part 9 covers qualifying small buildings. A four-storey apartment falls under Part 3 even if its footprint is small.
One stair is allowed in some narrow code configurations. A shared stair in a three- or four-storey apartment is not justified merely by having few units or a short corridor.
An Alberta single-stair proposal outside the acceptable solutions needs a documented alternative solution with project-specific evidence and acceptance by the authority having jurisdiction, the permit authority.
Edmonton's Point Access Block guide describes that pathway and requires professional involvement. It is not a province-wide standing approval.
This sheet identifies benchmarks, evidence and missing information. It does not decide whether a design provides equivalent safety.

Code basis: NBC(AE) 2023 p2, Div A, Sentence 1.2.1.1.(1) [PDF p.38]; Div A, Sentences 1.3.3.2.(1) and 1.3.3.3.(1) [PDF p.39-40]; Div B, Sentence 3.4.2.1.(1) [PDF p.269]; Div B, Sentences 9.9.8.2.(1) and (2) [PDF p.871]; Div B, Sentence 9.9.9.3.(1) [PDF p.872-873]. Definitions are in Div A, Article 1.4.1.2., access to exit [PDF p.42], exit [PDF p.44] and means of egress [PDF p.48].

Edmonton's guide, issued 2025-02-28, PDF pages 2-4 and 8, explains its alternative-solution pathway.

## When this topic applies

Concrete intake signals include:

- A new apartment with a single shared interior or exterior stair, a Point Access Block, or a request to remove an existing second exit.
- A proposed three- to six-storey apartment that relies on sprinklers, a vestibule or smoke control to compensate for one stair.
- An upper unit whose only doorway leads to a stair used by several suites, or to a public corridor served by one exit.
- A corridor with a dead end longer than 6 m, two exit doors located close together, or two nominal routes that merge into one vulnerable route.
- A request to exceed travel distance or reduce exit or corridor width. Egress door count, exit count, route independence, width and protection are different tests.
- A route through a lobby, an occupied roof, a mezzanine, an exterior balcony, a locked door or a stair exposed to neighbouring openings.
- A bedroom escape window, especially where an applicant calls it a second exit without explaining the complete route beyond it.

The benchmarks behind those signals are NBC(AE) 2023 p2, Div B, Sentences 3.3.1.3.(8) and (9) [PDF p.246], 3.3.1.9.(5) [PDF p.249], 3.4.1.2.(1) [PDF p.268], 3.4.2.3.(1) [PDF p.271], 3.4.2.5.(1) [PDF p.271-272], 3.4.3.2.(8) [PDF p.273], 9.9.7.2.(2) [PDF p.870], 9.9.7.3.(1) [PDF p.870], 9.9.9.3.(1) [PDF p.872-873] and 9.9.10.1.(1) [PDF p.873]. Specific roof, lobby, exterior-stair and hardware rules appear below.

Classification comes before selecting an exit rule:

| Intake fact | Consequence and verified source |
|---|---|
| Group C apartment, no more than 3 storeys in building height and no more than 600 m2 in building area | Within the small-building size and occupancy limits of Part 9. Building area is not the sum of all floor areas. NBC(AE) 2023 p2, Div A, Sentence 1.3.3.3.(1) [PDF p.40]; Div A, Article 1.4.1.2., building area definition [PDF p.43]. |
| Group C apartment exceeding either 3 storeys or 600 m2 | Parts 3, 4, 5 and 6 apply. NBC(AE) 2023 p2, Div A, Sentence 1.3.3.2.(1) [PDF p.39-40]. |
| Assembly, institutional or other non-residential use mixed into the proposal | Reassess major occupancy and the applicable Part under the cited Division A rules. A Group C-only Point Access Block study does not establish performance for every mixed-use arrangement. Edmonton technical report, PDF page 7. |
| Basement, sloping site, mezzanine or roof enclosure | Confirm building height and first storey using defined terms and actual elevations. Do not substitute a marketing storey count. NBC(AE) 2023 p2, Div A, Article 1.4.1.2., building height [PDF p.43], first storey [PDF p.45] and grade [PDF p.46]. |

Near-misses and companion topics:

- A house with one secondary suite has special shared-egress provisions. Route the suite classification and limits to [housing-secondary-suites-part9](housing-secondary-suites-part9.md), then apply the relevant egress rules. Do not treat a twelve-unit apartment as a house with a secondary suite.
- An ordinary bedroom-window replacement primarily concerns [housing-secondary-suites-part9](housing-secondary-suites-part9.md) and [occupancy-and-accessibility](occupancy-and-accessibility.md) unless the proposal changes the route used to escape.
- A penetration or fire-rated wall change belongs to [fire-separations-and-spatial-separation](fire-separations-and-spatial-separation.md). It also belongs here when it compromises an exit enclosure or another route.
- A sprinkler substitution, standpipe or alarm issue belongs to [firefighting-alarms-sprinklers](firefighting-alarms-sprinklers.md). Sprinkler installation alone does not establish an allowable shared single exit.
- A stair's load-bearing design belongs to [structural-and-framing](structural-and-framing.md). Its usable width, geometry and emergency function also belong here.
- General variance paperwork belongs to [process-and-admin](process-and-admin.md). Attribution lookup belongs to [code-structure-and-attribution](code-structure-and-attribution.md). Neither establishes technical equivalence.

## Benchmark acceptable solutions

For ordinary occupied apartment floor areas, the default is two exits, subject to the code's specific exceptions. A shared single-stair design outside those exceptions needs an alternative solution. Major occupancy, building height and building area decide whether Part 3 or Part 9 governs. The classification provisions and their pages appear above.

### Part 3 (Division B, Sections 3.3 and 3.4)

Part 3 normally requires at least two exits for an occupied floor area: NBC(AE) 2023 p2, Div B, Sentence 3.4.2.1.(1) [PDF p.269]. Required exits from a floor must remain separate, subject to the stated convergence concession: NBC(AE) 2023 p2, Div B, Sentence 3.4.1.2.(1) [PDF p.268].

The general small-floor single-exit allowance applies to a building of not more than 2 storeys in building height. The total occupant load served by that exit must be 60 or less. The floor area must also meet one of two sets of limits: NBC(AE) 2023 p2, Div B, Sentence 3.4.2.1.(2) [PDF p.269]. These limits describe that allowance, rather than all dwelling-unit exceptions.

- Not sprinklered throughout: both area and travel distance must meet the table labelled 3.4.2.1.-A. For Group C, that is 100 m2 and 15 m. This is the table forming part of NBC(AE) 2023 p2, Div B, Sentence 3.4.2.1.(2) [PDF p.269].
- Sprinklered throughout: travel distance must be 25 m or less, and the floor area must meet the table labelled 3.4.2.1.-B. For Group C, that is 150 m2. The table forms part of NBC(AE) 2023 p2, Div B, Sentence 3.4.2.1.(2); the table itself is on [PDF p.270].

For a Group B or Group C floor area, the one exit must be an exterior doorway no more than 1.5 m above adjacent ground level: NBC(AE) 2023 p2, Div B, Sentence 3.4.2.1.(3) [PDF p.270].

Building height is the first test. The one-exit allowance stops at 2 storeys. Apart from the dwelling-unit waiver in Sentence (4) below, a 3- or 4-storey apartment floor therefore has no one-exit route in Part 3, whatever its floor area or travel distance: NBC(AE) 2023 p2, Div B, Sentence 3.4.2.1.(2) [PDF p.269].

Sentences 3.4.2.1.(1) and (2) do not apply to dwelling units whose access to exit conforms to Sentences 3.3.4.4.(1) to (4): NBC(AE) 2023 p2, Div B, Sentence 3.4.2.1.(4) [PDF p.270]. Sentence (4) names only Sentences 3.3.4.4.(1) to (4). It does not name (5) or (6), so those sentences are not waivers of the floor-area rule on their face. See Open questions.

Article 3.3.4.4. sets the unit-level egress rules. Its main points are these: NBC(AE) 2023 p2, Div B, Article 3.3.4.4. [PDF p.263-264].

- A dwelling unit of more than one storey needs an egress door into a public access to exit from its top storey and from its bottom storey, each within 1.5 m of that storey's floor level (Sentence (2)).
- A unit may have a single exit if that exit is an exterior doorway no more than 1.5 m above adjacent ground, and either no more than one storey of travel is needed to reach it, or the top storey opens to a balcony no more than 6 m above adjacent ground (Sentence (3)).
- In a residential building of not more than 3 storeys in building height, a unit door may open directly into an exit stairway, provided the unit has a second and separate means of egress (Sentence (5)).
- If a unit has a second and separate means of egress, one of those means may pass through an interior corridor served by a single exit, an exterior balcony served by a single exit stairway, or an exterior passageway served by a single exit stairway (Sentence (6)).

Sentence (6) permits one of the unit's means of egress to use the listed single-exit arrangements only if another, separate means of egress exists. It cannot justify the worked example's single route with no separate alternative. A project relying on a more complex combination needs a documented interpretation from the permit authority. Do not extend the waiver in Sentence 3.4.2.1.(4) beyond the dwelling-unit configurations it names.

Distance between exits. Subject to the alternative configuration in Sentence (2), the minimum separation is half the maximum floor-area diagonal. For a floor area with a public corridor, that minimum need not exceed 9 m. For other floor areas, it must be at least 9 m. The first statement is a cap on the required minimum, not a prohibition on exits being farther apart. Measure the shortest path smoke could take while respecting intervening fire separations: NBC(AE) 2023 p2, Div B, Sentences 3.4.2.3.(1) to (3) [PDF p.271].

Travel distance to an exit. Where more than one exit is required, the usual residential limits are 45 m in a floor area sprinklered throughout and 30 m otherwise: NBC(AE) 2023 p2, Div B, Sentence 3.4.2.5.(1), Clauses (c) and (f) [PDF p.271-272]. The 105 m configuration in Clause (d) has extensive conditions, including unseparated rooms or suites and a public corridor at least 9 m wide. It is not the ordinary apartment benchmark. Residential suite separations are normally at least 1 h, with a limited 45 min allowance tied to the construction requirements: NBC(AE) 2023 p2, Div B, Sentences 3.3.4.2.(1) and (2) [PDF p.262].

Travel follows the actual walking route rather than a straight line on the plan. It may start at the suite door only if the suite separation and protected route satisfy the measurement concession: NBC(AE) 2023 p2, Div B, Sentences 3.4.2.4.(1) and (2) [PDF p.271].

Public corridors ordinarily need 1100 mm width and may have a dead end no longer than 6 m, subject to the stated exceptions: NBC(AE) 2023 p2, Div B, Sentences 3.3.1.9.(1) and (5) [PDF p.249]. A 5 m dead end does not by itself eliminate the floor area's two-exit requirement. Suite doorways normally open onto a public corridor, an exterior passageway or the exterior, with access in opposite directions to separate exits, subject to the stated dwelling-unit exceptions: NBC(AE) 2023 p2, Div B, Sentences 3.3.1.3.(8) and (9) [PDF p.246].

Exit width. The minimum aggregate width for residential occupancy is the occupant load times 6.1 mm for doorways, corridors and ramps no steeper than 1 in 8, 8 mm for stairs with a rise of 180 mm or less and a run of 280 mm or more, and 9.2 mm for other stairs and ramps: NBC(AE) 2023 p2, Div B, Sentence 3.4.3.2.(1) [PDF p.272]. Where more than one exit is required, each exit counts for not more than one-half of the required width: NBC(AE) 2023 p2, Div B, Sentence 3.4.3.2.(7) [PDF p.273].

Minimum clear widths for Group C appear in the table labelled 3.4.3.2.-A, including its Notes (1) and (2), forming part of NBC(AE) 2023 p2, Div B, Sentence 3.4.3.2.(8) [PDF p.273].

- Exit stairs: 900 mm where the stair serves not more than 2 storeys above the lowest exit level or not more than 1 storey below it. 1100 mm where it serves more than that.
- Doorways: 850 mm.
- Corridors, passageways and ramps: 1100 mm.

A stair serving a 4-storey building from the ground floor serves more than 2 storeys above the lowest exit level. The 1100 mm column therefore applies to that stair.

Width based on load and the tabulated physical minimum both apply. Ordinary stacked floor areas do not automatically require the sum of every floor's occupant load to determine stair width. Sentence 3.4.3.2.(4) generally permits non-cumulative widths for stacked floors, subject to its exceptions: NBC(AE) 2023 p2, Div B, Sentence 3.4.3.2.(4) [PDF p.273]. For apartments, determine occupant load using two persons per sleeping room rather than two persons per unit: NBC(AE) 2023 p2, Div B, Sentence 3.1.17.1.(1), Clause (b) [PDF p.171].

Exit protection remains part of the benchmark. Exit fire separation is tied to the construction article's floor rating, with a 45 min floor and a 2 h ceiling on the rating required by this article: NBC(AE) 2023 p2, Div B, Sentences 3.4.4.1.(1) and (2) [PDF p.274]. Openings, services and activities in exits are restricted. An exit cannot become an HVAC plenum, an ancillary storage room or general occupied space: NBC(AE) 2023 p2, Div B, Article 3.4.4.4. [PDF p.275].

An exit through a lobby is a conditional concession, not an unrestricted discharge arrangement. The Part 3 concession includes the 4.5 m lobby elevation and 15 m travel limits, restrictions on adjacent uses and continued separation of the stair from the lobby: NBC(AE) 2023 p2, Div B, Sentences 3.4.4.2.(1) and (2) [PDF p.274-275].

For stairs, check flights, landings and doors as well as width. Flights normally rise no more than 3.7 m between landings, and landings are required at specified stair, ramp and door transitions: NBC(AE) 2023 p2, Div B, Sentences 3.4.6.3.(1) to (3) [PDF p.277]. Exit door release generally requires no key, special device or specialized knowledge and no more than one releasing operation, with specific exceptions for permitted locking systems: NBC(AE) 2023 p2, Div B, Sentence 3.4.6.16.(1) [PDF p.282]. This is not permission to install any electromagnetic lock.

Convergence. If more than 2 exits serve a floor area, exits may converge under Sentence 3.4.3.1.(2), provided the converging exits contribute no more than 50% of the total required exit width for the floor area: NBC(AE) 2023 p2, Div B, Sentence 3.4.1.2.(2) [PDF p.268].

### Part 9, Division B Section 9.9

The following rules describe the small-building benchmark. They do not apply to a four-storey apartment merely because it has a small footprint.

| Issue | Acceptable-solution requirement, paraphrased | Verified citation |
|---|---|---|
| Suite access | In a multi-suite floor area, provide an exterior exit door, public corridor door or exterior passageway door. Ordinarily, a corridor or passageway must offer travel in opposite directions to separate exits. | NBC(AE) 2023 p2, Div B, Sentences 9.9.7.2.(1) and (2) [PDF p.869-870]. |
| Dead ends | Usually no more than 6 m, with the express suite and dwelling-unit provisions considered together. | NBC(AE) 2023 p2, Div B, Sentence 9.9.7.3.(1) [PDF p.870]. |
| Room egress doors | Rooms and suites other than dwelling units need two egress doors when the table's area or internal-distance limits are exceeded. For Group C other than dwelling units, the table lists 100 m2 and 15 m. | NBC(AE) 2023 p2, Div B, Sentences 9.9.7.4.(1) and (2), Table 9.9.7.4. [PDF p.870]. |
| Independent access | Required suite access cannot pass through another dwelling unit, service room or other occupancy. | NBC(AE) 2023 p2, Div B, Sentence 9.9.7.5.(1) [PDF p.870]. |
| Measurement | Measure along the route from any point. Starting at the room or suite door requires the separation conditions in Sentence (2). | NBC(AE) 2023 p2, Div B, Sentences 9.9.8.1.(1) and (2) [PDF p.870]. |
| Floor exits | Ordinarily two exits. Travel to the nearest exit is limited to 40 m for business and personal services, 45 m for sprinklered floor areas, and 30 m otherwise. | NBC(AE) 2023 p2, Div B, Sentence 9.9.8.2.(1) [PDF p.871]. |
| General single exit | Buildings of one or two storeys may have one exit from each storey if the referenced area and distance conditions and the total 60-person facility limit are met. The dwelling-unit subsection still applies. | NBC(AE) 2023 p2, Div B, Sentence 9.9.8.2.(2) [PDF p.871]. |
| Capacity distribution | Where several exits are required, each contributes at most half the required width. | NBC(AE) 2023 p2, Div B, Sentence 9.9.8.3.(1) [PDF p.871]. |
| Exit independence | At least two required exits must be independent and remote along the travel route. Part 9 states this qualitatively rather than importing Part 3's diagonal formula. | NBC(AE) 2023 p2, Div B, Sentence 9.9.8.4.(1) [PDF p.871]. |
| Lobby discharge | At most one exit may pass through the lobby. The 4.5 m elevation and 15 m travel limits and other protective conditions apply. | NBC(AE) 2023 p2, Div B, Article 9.9.8.5. [PDF p.871]. |
| Mezzanine | Ordinarily provide exits accessible at that level. Limited low-load, small-area configurations can use the space below, subject to every listed condition. | NBC(AE) 2023 p2, Div B, Article 9.9.8.6. [PDF p.871-872]. |

Dwelling units need a separate check. A multi-level unit normally must reach an egress-door level by travelling no more than one storey up or down. The specified large window or balcony configurations provide exceptions: NBC(AE) 2023 p2, Div B, Sentences 9.9.9.1.(1) to (3) [PDF p.872]. The large-window exception is limited to a unit not above or below another suite. Its 1 m by 0.55 m opening and sill-height conditions differ from the ordinary bedroom-window dimensions.

The doorway of an apartment onto a public corridor or exterior passageway ordinarily needs opposite-direction access to two exits unless the unit has another separate means of egress, with the listed exceptions: NBC(AE) 2023 p2, Div B, Sentence 9.9.9.2.(1) [PDF p.872]. A unit using a shared exit stair or the specified shared corridor, balcony or passageway served by one exit needs a second and separate means of egress: NBC(AE) 2023 p2, Div B, Sentence 9.9.9.3.(1) [PDF p.872-873]. The distinct rule for an upper dwelling in a house with a secondary suite is Sentence 9.9.9.3.(2) [PDF p.873].

Bedroom escape. Unless the suite is sprinklered, each bedroom or combination bedroom needs the specified outside window or exterior door. The window must open without keys, tools, special knowledge or removal of hardware. Its unobstructed opening must be at least 0.35 m2, with no dimension under 380 mm, and stay open without extra support. Window wells require at least 760 mm clearance in front, with opening-sash, enclosure and security-bar conditions: NBC(AE) 2023 p2, Div B, Sentences 9.9.10.1.(1) to (6) [PDF p.873]. This is a bedroom-escape requirement, not a general grant of a second exit for a shared-stair apartment. Removing the bedroom-window requirement by sprinklers does not remove the shared-egress requirements above.

Part 9 geometry and protection also matter:

- The common exit-facility minimum is 900 mm, excluding doors and corridors. Public and exit corridors require 1100 mm. The subsection excludes specified single-dwelling and house-with-secondary-suite routes. Door and stair rules must be checked separately: NBC(AE) 2023 p2, Div B, Articles 9.9.3.1. to 9.9.3.3. [PDF p.864].
- Required clear height is normally 2.1 m, with stated exceptions and separate stair and doorway rules: NBC(AE) 2023 p2, Div B, Sentence 9.9.3.4.(1) [PDF p.864].
- Exit separations depend on the adjacent floor assembly rating and the listed exceptions. A separation common to two exits must be smoke-tight and cannot have openings that compromise continuity: NBC(AE) 2023 p2, Div B, Sentences 9.9.4.2.(1), (3) and (4) [PDF p.864-865]. The gypsum smoke-barrier provision in Sentence (2) is specific to a house with a secondary suite.
- An exterior stair that is the only route from a suite may need protection from nearby unprotected openings. Calling the stair outdoors does not settle the exposure problem: NBC(AE) 2023 p2, Div B, Sentence 9.9.4.4.(1) [PDF p.865].
- Corridor activities cannot reduce required clear width. Obstructions and door operation remain separate checks: NBC(AE) 2023 p2, Div B, Sentence 9.9.5.2.(1) [PDF p.866]; Article 9.9.6.7. [PDF p.869].
- An occupied roof requires egress, and more than 60 occupants requires two remote means leading to exit-standard stairs: NBC(AE) 2023 p2, Div B, Sentences 9.9.7.1.(1) and (2) [PDF p.869]. The Part 3 counterpart is Article 3.3.1.3. [PDF p.245-246]. A roof patio cannot be added to a single-stair proposal without reassessing its egress.

### Ordinary egress variances

A longer travel route, longer dead end or narrower passage is a departure from its own benchmark even when two stairs remain. Describe the exact length or width, measurement endpoints, occupant load, protection and affected population. Compare the same building before and after the proposed change. Evidence for one departure does not prove another. The benchmark articles above and the documentation requirements of NBC(AE) 2023 p2, Div C, Sentences 2.3.1.1.(2), (3) and (5) [PDF p.739] support that comparison.

## Attributions

Attributions are exact functional-statement and objective pairings from the Alberta second-printing tables, not tags chosen by the researcher. Each bracket keeps the table's grouping. The first page in each row locates the provision; the page after the brackets locates its attribution. Code text and table rows were checked separately using the CLI and layout-preserving PDF extraction.

The relevant tables are NBC(AE) 2023 p2, Div B, Table 3.10.1.1. [PDF p.342-347] and Div B, Table 9.38.1.1. [PDF p.1125-1126]. These citations identify the continued table pages, not the location of its first page.

Objective meanings, paraphrased from NBC(AE) 2023 p2, Div A, Article 2.2.1.1., PDF pages 68-72:

- OS1.2 concerns injury when fire or explosion affects areas beyond its origin.
- OS1.5 concerns delayed or impeded escape during a fire emergency.
- OS3.1 concerns injury such as falls, collisions or contact.
- OS3.6 concerns people trapped in confined spaces.
- OS3.7 concerns delayed or impeded movement to safety in any emergency.
- OP1.2 concerns damage to the building when fire or explosion affects areas beyond its origin. It is a property-protection objective, not an operational statement.

Functional meanings, paraphrased from NBC(AE) 2023 p2, Div A, Article 3.2.1.1., PDF pages 79-80:

- F03 concerns limiting fire effects outside the area of origin.
- F05 concerns limiting fire effects on emergency egress.
- F06 concerns limiting fire effects on notification, suppression and response facilities.
- F10 concerns timely movement to safety in an emergency.
- F12 concerns supporting emergency response.
- F30 concerns reducing injury through falling, collision, contact and related hazards.
- F36 concerns preventing entrapment in confined spaces.

### Part 3 verified rows

| Provision and body page | Exact table brackets | Attribution source |
|---|---|---|
| NBC(AE) 2023 p2, Div B, Sentence 3.3.1.3.(8) [PDF p.246] | [F05-OS1.5] | Div B Table attribution, PDF p.342 |
| NBC(AE) 2023 p2, Div B, Sentence 3.3.1.3.(9) [PDF p.246] | [F10,F12,F05,F06-OS3.7] | Div B Table attribution, PDF p.342 |
| NBC(AE) 2023 p2, Div B, Sentence 3.3.1.9.(1) [PDF p.249] | [F10,F12-OS3.7] | Div B Table attribution, PDF p.342 |
| NBC(AE) 2023 p2, Div B, Sentence 3.3.4.4.(2) [PDF p.263] | [F10,F05-OS3.7] | Div B Table attribution, PDF p.345 |
| NBC(AE) 2023 p2, Div B, Sentence 3.3.4.4.(3) [PDF p.263] | [F10-OS3.7] | Div B Table attribution, PDF p.345 |
| NBC(AE) 2023 p2, Div B, Sentence 3.3.4.4.(4) [PDF p.263] | [F05-OS1.2,OS1.5] | Div B Table attribution, PDF p.345 |
| NBC(AE) 2023 p2, Div B, Sentence 3.3.4.4.(5) [PDF p.263] | [F10,F05-OS3.7] | Div B Table attribution, PDF p.345 |
| NBC(AE) 2023 p2, Div B, Sentence 3.3.4.4.(6) [PDF p.263-264] | [F10,F05-OS3.7] | Div B Table attribution, PDF p.345 |
| NBC(AE) 2023 p2, Div B, Sentence 3.4.1.2.(1) [PDF p.268] | [F10,F12,F05,F06-OS3.7] [F12,F06-OP1.2] [F12,F06-OS1.5,OS1.2] | Div B Table attribution, PDF p.346 |
| NBC(AE) 2023 p2, Div B, Sentence 3.4.1.2.(2) [PDF p.268] | [F10-OS3.7] | Div B Table attribution, PDF p.346 |
| NBC(AE) 2023 p2, Div B, Sentence 3.4.2.1.(1) [PDF p.269] | [F10,F12,F05,F06-OS3.7] [F12,F06-OS1.2] [F12,F06-OP1.2] | Div B Table attribution, PDF p.346 |
| NBC(AE) 2023 p2, Div B, Sentence 3.4.2.1.(3) [PDF p.270] | [F10-OS3.7] | Div B Table attribution, PDF p.346 |
| NBC(AE) 2023 p2, Div B, Sentence 3.4.2.3.(1) [PDF p.271] | [F10,F05-OS1.5] | Div B Table attribution, PDF p.346 |
| NBC(AE) 2023 p2, Div B, Sentence 3.4.2.3.(4) [PDF p.271] | [F10-OS3.7] | Div B Table attribution, PDF p.346 |
| NBC(AE) 2023 p2, Div B, Sentence 3.4.2.5.(1) [PDF p.271-272] | [F10-OS3.7] | Div B Table attribution, PDF p.346 |
| NBC(AE) 2023 p2, Div B, Sentence 3.4.3.2.(1) [PDF p.272] | [F10-OS3.7] | Div B Table attribution, PDF p.346 |
| NBC(AE) 2023 p2, Div B, Sentence 3.4.3.2.(7) [PDF p.273] | [F10-OS3.7] | Div B Table attribution, PDF p.346 |
| NBC(AE) 2023 p2, Div B, Sentence 3.4.3.2.(8) [PDF p.273] | [F12,F10-OS3.7] [F30-OS3.1] [F12-OP1.2] [F12-OS1.2] | Div B Table attribution, PDF p.346 |
| NBC(AE) 2023 p2, Div B, Sentence 3.4.4.1.(1) [PDF p.274] | [F05-OS1.5] [F06-OS1.5,OS1.2] [F03-OS1.2] [F06,F03-OP1.2] | Div B Table attribution, PDF p.347 |
| NBC(AE) 2023 p2, Div B, Sentence 3.4.4.4.(1) [PDF p.275] | [F05-OS1.5] [F06-OS1.5,OS1.2] [F03-OS1.2] [F06,F03-OP1.2] | Div B Table attribution, PDF p.347 |

### Part 9 verified rows

| Provision and body page | Exact table brackets | Attribution source |
|---|---|---|
| NBC(AE) 2023 p2, Div B, Sentence 9.9.3.2.(1) [PDF p.864] | [F10-OS3.7] | Div B Table attribution, PDF p.1125 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.3.3.(1) [PDF p.864] | [F30-OS3.1] [F10-OS3.7] | Div B Table attribution, PDF p.1125 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.3.4.(1) [PDF p.864] | [F30-OS3.1] [F10-OS3.7] | Div B Table attribution, PDF p.1125 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.4.2.(1) [PDF p.864] | [F05-OS1.5] [F03-OS1.2] [F03-OP1.2] | Div B Table attribution, PDF p.1125 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.4.2.(3) [PDF p.865] | [F05-OS1.5] | Div B Table attribution, PDF p.1125 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.4.2.(4) [PDF p.865] | [F05-OS1.5] [F03-OS1.2] [F03-OP1.2] | Div B Table attribution, PDF p.1125 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.4.4.(1) [PDF p.865] | [F05-OS1.5] | Div B Table attribution, PDF p.1125 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.5.2.(1) [PDF p.866] | [F10-OS3.7] | Div B Table attribution, PDF p.1125 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.7.1.(1) [PDF p.869] | [F10-OS3.7] | Div B Table attribution, PDF p.1125 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.7.2.(1) [PDF p.869-870] | [F10-OS1.5] | Div B Table attribution, PDF p.1125 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.7.2.(2) [PDF p.870] | [F10-OS3.7] | Div B Table attribution, PDF p.1126 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.7.3.(1) [PDF p.870] | [F10-OS3.7] | Div B Table attribution, PDF p.1126 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.7.4.(1) [PDF p.870] | [F10-OS3.7] | Div B Table attribution, PDF p.1126 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.7.4.(2) [PDF p.870] | [F10-OS1.5] | Div B Table attribution, PDF p.1126 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.7.5.(1) [PDF p.870] | [F10-OS3.7] | Div B Table attribution, PDF p.1126 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.8.2.(1) [PDF p.871] | [F10-OS3.7] | Div B Table attribution, PDF p.1126 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.8.3.(1) [PDF p.871] | [F10-OS3.7] | Div B Table attribution, PDF p.1126 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.8.4.(1) [PDF p.871] | [F10-OS1.5] | Div B Table attribution, PDF p.1126 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.8.5.(1) [PDF p.871] | [F10-OS1.5] | Div B Table attribution, PDF p.1126 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.8.5.(5) [PDF p.871] | [F05-OS1.5] | Div B Table attribution, PDF p.1126 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.8.6.(1) [PDF p.871] | [F05-OS1.5] | Div B Table attribution, PDF p.1126 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.8.6.(4) [PDF p.872] | [F05-OS1.5] | Div B Table attribution, PDF p.1126 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.9.1.(1) [PDF p.872] | [F10-OS3.7] | Div B Table attribution, PDF p.1126 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.9.1.(2) [PDF p.872] | [F10-OS3.7] | Div B Table attribution, PDF p.1126 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.9.1.(3) [PDF p.872] | [F10-OS3.7] | Div B Table attribution, PDF p.1126 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.9.2.(1) [PDF p.872] | [F10-OS3.7] | Div B Table attribution, PDF p.1126 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.9.3.(1) [PDF p.872] | [F10-OS3.7] | Div B Table attribution, PDF p.1126 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.9.3.(2) [PDF p.872-873] | [F10-OS3.7] | Div B Table attribution, PDF p.1126 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.10.1.(1) [PDF p.873] | [F10-OS3.7] | Div B Table attribution, PDF p.1126 |
| NBC(AE) 2023 p2, Div B, Sentence 9.9.10.1.(6) [PDF p.873] | [F10,F12,F36-OS1.5] [F10,F12,F36-OS3.6] | Div B Table attribution, PDF p.1126 |

### Exceptions and sentences with no direct row

Some conditions, definitions and exceptions have no separately printed attribution. For example, the Part 3 single-floor and dwelling-unit exceptions in Sentences 3.4.2.1.(2) and (4) have no direct row. Evaluate them against the attributed two-exit root in Sentence 3.4.2.1.(1). The equivalent distinction applies between the Part 9 single-exit exception in Sentence 9.9.8.2.(2) and its attributed root in Sentence 9.9.8.2.(1). This does not create new attributions for the exception sentences.

The Part 3 dead-end limit in Sentence 3.3.1.9.(5), and the general measurement Sentences 3.4.2.4.(1) and (2), also have no separately printed rows in the relevant table. Record that absence. A departure analysis must identify the applicable attributed root or related acceptable solutions and explain the connection, rather than attach F10 to an unlisted sentence by guesswork.

Part 9 gives no separate row to Article 9.9.8.1.'s measurement sentences or to the exceptions in Sentences 9.9.8.6.(2) and (3). Do not infer that the missing rows waive their conditions. Other sentences of the same article, or the requirement they qualify, retain their own printed pairings.

## Intent

Intent entries come from the NBC 2020 Intent Statements, national explanatory material rather than Alberta law. The listed entries were matched by sentence identifier to the Alberta second-printing body text and checked in the intent supplement. That mapping does not mean every Alberta amendment, attribution or exception is identical to the national edition. Alberta's attribution tables govern the Section C pairings. Intent wording below is paraphrased.

- Sentence 3.4.2.1.(1), two exits per floor area. The intent is to avoid a single blocked exit leaving occupants without another route. It also gives responders another way to reach the floor. Its OS1 branch addresses injury through fire spread when access is delayed; its OP1 branch addresses damage to the building through that same failure. NBC 2020 Intent Statements, 3.4.2.1.(1) [PDF p.608-609]. The property branch matters even when a proposed evacuation-time calculation is favourable.
- Sentence 3.4.2.1.(2), one exit allowed. The intent is to exempt certain floor areas from the two-exit rule. The stated basis is a limited occupant load served by the exit, with a restricted floor area and travel distance. NBC 2020 Intent Statements, 3.4.2.1.(2) [PDF p.609].
- Sentence 3.4.2.1.(4), dwelling-unit waiver. The intent exempts dwelling unit access from the two-exit or one-exit rule, on two conditions: occupants know their routes, and the unit design is limited by Sentences 3.3.4.4.(1) to (4), which caps the number of occupants. NBC 2020 Intent Statements, 3.4.2.1.(4) [PDF p.610]. The waiver names only Sentences (1) to (4). The 2020 intent does not extend it to Sentences (5) or (6).
- Sentence 3.3.4.4.(1), direct access to a corridor not required. Certain unit egress facilities are exempt from the direct-access rule for a public corridor or exterior passageway on the same storey. The basis is that occupants know the routes and the time to reach safety is short. NBC 2020 Intent Statements, 3.3.4.4.(1) [PDF p.582].
- Sentence 3.3.4.4.(2), doors serving the uppermost and lowest dwelling-unit storeys. The intent limits excessive travel and preserves another egress route if one is blocked. NBC 2020 Intent Statements, 3.3.4.4.(2) [PDF p.582-583].
- Sentence 3.3.4.4.(3), multi-level unit. The intent exempts a multi-level unit from the each-storey egress door rule. The basis is that travel to the exit door does not pass more than one storey up or down, or an outside balcony serves as the upper-level exit. NBC 2020 Intent Statements, 3.3.4.4.(3) [PDF p.583].
- Sentence 3.3.4.4.(4), separated private stair. An uppermost- or lowest-storey doorway can be omitted under the specified configuration because a stair separated from the other unit storeys provides the route to public access to exit. The intent limits fire spread into that stair and resulting harm or evacuation delay. NBC 2020 Intent Statements, 3.3.4.4.(4) [PDF p.583].
- Sentence 3.3.4.4.(5), unit doorway into an exit stair. A unit door may open directly into an exit stair in a building not more than 3 storeys, if the unit has a second means of egress. NBC 2020 Intent Statements, 3.3.4.4.(5) [PDF p.583-584].
- Sentence 3.3.4.4.(6), pass-through means of egress. A unit with a second means of egress may use one route through a corridor served by a single exit. The intent exempts those egress facilities from the exterior-doorway, public-corridor and 6 m dead-end limits, on the basis that a second means of egress is available if one route is blocked. NBC 2020 Intent Statements, 3.3.4.4.(6) [PDF p.584]. The intent names the rule being relaxed. It does not say that Sentence (6) also relaxes the floor-area rule in Sentence 3.4.2.1.(1).
- Sentence 3.4.2.3.(1), spacing of exits. Exits must not sit too close together, so that a fire does not block both routes. NBC 2020 Intent Statements, 3.4.2.3.(1) [PDF p.611].
- Sentence 3.4.2.4.(2), suite travel distance. Travel distance may be measured from the suite egress door when the suite is separated and the route beyond it is protected. NBC 2020 Intent Statements, 3.4.2.4.(2) [PDF p.612].
- Sentence 3.4.2.5.(1), travel to an exit. The intent limits travel distance to an exit. NBC 2020 Intent Statements, 3.4.2.5.(1) [PDF p.612].
- Sentence 3.4.3.2.(1), exit width. Exits must be wide enough to allow efficient egress. NBC 2020 Intent Statements, 3.4.3.2.(1) [PDF p.614].
- Sentence 3.4.3.2.(8), physical minimum width. The intent also addresses responder access, congestion and collision injury, and fire spread causing injury or building damage when responders are delayed. NBC 2020 Intent Statements, 3.4.3.2.(8) [PDF p.616-617]. A width based only on the occupant-load multiplier misses these purposes.
- Sentence 3.4.4.1.(1), protected exits. The intent limits fire entering an exit, spreading between floors through it, delaying evacuation or obstructing responders. It includes the resulting injury and building-damage consequences. NBC 2020 Intent Statements, 3.4.4.1.(1) [PDF p.623-624].
- Sentence 3.3.1.3.(9), opposite-direction routes. The intent preserves a useful route for occupants and responders when the other route becomes inaccessible. NBC 2020 Intent Statements, 3.3.1.3.(9) [PDF p.521].
- Sentence 3.3.1.9.(5), dead ends. The intent addresses people entering a dead end and being unable to retrace their path because of crowd pressure or untenable conditions. The within-suite exception relies on familiarity. NBC 2020 Intent Statements, 3.3.1.9.(5) [PDF p.529].
- Sentence 9.9.7.3.(1), dead-end corridors. A dead-end corridor longer than 6 m is restricted, so that people do not enter an excessively long dead end and become trapped. The rule is relaxed for dead ends within a suite, because occupants know the suite. NBC 2020 Intent Statements, 9.9.7.3.(1) [PDF p.1325].
- Sentence 9.9.7.4.(1), number of egress doors. The intent provides enough doors for efficient escape from large rooms or suites. Its exceptions address lower occupant loads and occupants' familiarity with the routes. NBC 2020 Intent Statements, 9.9.7.4.(1) [PDF p.1325].
- Sentence 9.9.8.2.(1), exit count and travel distance. The intent limits travel distance to exits and requires an alternative exit if one is blocked. NBC 2020 Intent Statements, 9.9.8.2.(1) [PDF p.1327].
- Sentence 9.9.8.2.(2), single exit in one- and two-storey buildings. This sentence overrides the two-exit rule for low buildings with a low occupant load, limited floor areas and limited travel distance. NBC 2020 Intent Statements, 9.9.8.2.(2) [PDF p.1327].
- Sentence 9.9.8.3.(1), capacity at one exit. The intent stops too much required exit capacity from concentrating at one exit. NBC 2020 Intent Statements, 9.9.8.3.(1) [PDF p.1327].
- Sentence 9.9.9.1.(1) to (3), dwelling-unit travel to a level. These sentences supersede the Part 9 exit-count and travel rules for units with more than one storey, on the stated basis of limited travel to a route out. NBC 2020 Intent Statements, 9.9.9.1.(1) to (3) [PDF p.1330-1331].
- Sentence 9.9.9.2.(1), two separate exits from a unit. The intent ensures an alternative route when one is blocked. NBC 2020 Intent Statements, 9.9.9.2.(1) [PDF p.1332].
- Sentence 9.9.9.3.(1) and (2), shared egress. These sentences supersede the single-exit or single-doorway allowance for a suite and require a second means of egress from the unit in listed cases. The intent again is to provide an alternative route. NBC 2020 Intent Statements, 9.9.9.3.(1) and (2) [PDF p.1332].
- Sentence 9.9.10.1.(1), bedroom escape. The intent limits people being trapped in a bedroom if their other means of egress is blocked. NBC 2020 Intent Statements, 9.9.10.1.(1) [PDF p.1333]. Its limited purpose does not convert every bedroom window into a shared apartment exit.

Sentence 3.4.2.1.(3) does have an intent entry. It relates the doorway-to-ground elevation limit to travel distance and delayed movement to safety: NBC 2020 Intent Statements, 3.4.2.1.(3) [PDF p.609-610]. The inherited draft's claim that this rationale was absent was incorrect.

The supplement explains the limited-load, limited-area and limited-distance basis of the general single-exit allowance. It does not establish a numerical proof that any selected height, load, sprinkler package or vestibule gives equivalent performance in a new design. That proof belongs in the project-specific professional analysis.

## Typical alternative solutions

### A shared single stair with additional protection

Applicants propose a small apartment floor plate with few suites and short corridors, then seek to replace the second stair's redundancy with a defined fire and life-safety strategy. The benchmark remains the relevant two-exit acceptable solution, including the effects on responders and property. A low occupant count is one input, not a demonstration that the remaining route survives a fire.

Edmonton's guide identifies compartmentation, vestibules, exterior passageways and smoke management as potential measures, to be selected through the project's analysis. The guide requires a qualified fire-protection or life-safety code consultant and professional involvement. It does not prescribe one universal package. Edmonton Point Access Block guide, PDF pages 4-5 and 8; accompanying Building Code Guide, PDF pages 6-7.

The downloaded technical report is an example analysis, revision 4 dated 2025-02-28. It examines failure of the sole route using event trees, fault trees and reliability diagrams. Its worked design is a four-storey, sixteen-unit building with an intervening vestibule. The report's scope is the number of exits; other departures need additional analysis. Its results cannot be copied as a numerical safety finding for the different twelve-unit case below. Source: [Edmonton technical report](https://www.edmonton.ca/sites/default/files/public-files/Point-Access-Block-Technical-Report.pdf), accessed 2026-10-18, PDF pages 6-7, 16-26.

The Design Guide illustrates planning options rather than permit-ready designs. Its examples are limited to six storeys and four dwellings per storey, but those illustration limits are not Alberta code permissions. Source: [Edmonton Design Guide](https://www.edmonton.ca/sites/default/files/public-files/Point-Access-Block-Design-Guide.pdf), accessed 2026-10-18, PDF pages 6-7 and 10-12.

### Longer routes, dead ends or reduced width

An ordinary variance may retain two stairs but extend a corridor, create a longer dead end or reduce a clear dimension. The proposed evidence should address the changed failure mechanism. For example, early detection can affect response time, but it does not itself remove a pinch point, smoke exposure or the risk that people must reverse direction in a dead end. This is a research interpretation of the cited intent entries, not a predetermined approval criterion.

The relevant benchmarks are NBC(AE) 2023 p2, Div B, Sentences 3.3.1.9.(5) [PDF p.249], 3.4.2.5.(1) [PDF p.271-272], 3.4.3.2.(8) [PDF p.273], 9.9.7.3.(1) [PDF p.870], 9.9.8.2.(1) [PDF p.871] and 9.9.3.3.(1) [PDF p.864]. A submission must identify each departure separately and explain the combined proposal under Div C, Article 2.3.1.1. [PDF p.739].

### Exterior or direct-entry arrangements

Applicants sometimes replace a second interior route with an exterior stair, balcony, passageway or direct ground-level unit entrance. Check the complete path to safety, exposure from windows and other suites, and the specific dwelling-unit exceptions. A ladder or bedroom window is not automatically a second acceptable exit. Fire escapes are permitted as exits only on existing buildings under NBC(AE) 2023 p2, Div B, Sentence 9.9.2.1.(2) [PDF p.863]. New construction cannot simply borrow that existing-building allowance.

### Existing buildings

An existing stair, former approval or familiar local arrangement is evidence of what was built, not proof that the present alteration complies. Obtain the approved drawings, variance and conditions, then compare the proposed occupancy and physical changes with them. The need to document and preserve operational limits follows from NBC(AE) 2023 p2, Div C, Article 2.3.1.1. [PDF p.739]. The October 2026 SES STANDATA also requires ongoing availability of the issued variance on the premises, as discussed under Precedents.

## Usual mitigations and evidence

### The evidence addresses failure of the remaining route

For single-stair work, the professional's comparison must address the continued availability of the stair, rather than merely its ability to carry a small crowd. Relevant project questions include smoke entering the corridor, open or failed doors, smoke transfer to the stair, water or power failure, and firefighter operations while occupants descend. These questions follow from the attributed exit purposes, the national intent entries and Edmonton's emergency-services guide. They are not assumed failure probabilities.

| Proposed measure | Evidence needed to assess the claim |
|---|---|
| Sprinklers | Governing design standard, coverage, water demand and available supply, supervision, outages, inspection and maintenance. State which protection is already required for the benchmark building. |
| Better suite and corridor compartmentation | Rated assembly details, continuity, penetrations, doors, closers and the route by which smoke could still reach the stair. A wall rating alone does not establish a smoke barrier. |
| An intervening vestibule | Plans, door arrangement, ratings, self-closing and release functions, clear dimensions, leakage assumptions and operation when doors are held open by occupants or hose lines. |
| Stair pressurization or ventilation | A professional smoke-control design, leakage paths, wind and stack effects, door-opening forces, power, controls, commissioning and failure behaviour. |
| Exterior passageway | Exposure from adjacent openings, wind-driven smoke and fire, winter conditions and a continuous route to an acceptable discharge. |
| Wider stair or fewer occupants | Actual clear width, landings, door swings, bedroom-based load, mobility needs, and responder counterflow. More width does not replace lost route independence by arithmetic alone. |
| Earlier warning | Detector locations, alarm sequence, audibility, verification and reasonable notification and pre-movement assumptions. |
| Additional response or rescue provisions | Site access and staging, water supply, hose routing, operations, equipment limits and confirmation of any unusual assumptions with the local fire service. |
| Maintenance or management controls | A named owner, enforceable procedures, test intervals, records, staff training and a handover process. Do not assume every door stays closed forever. |

These are topics for supporting evidence, not requirements for every building or a recipe for acceptance. Legal documentation requirements are NBC(AE) 2023 p2, Div C, Sentences 2.3.1.1.(2) to (6) [PDF p.739].

Edmonton's Point Access Block guide, PDF pages 4-6 and 8, and its emergency-services guide, PDF pages 8-9 and 20-22, explain the local analysis and documentation expectations.

### Comparative analysis and uncertainty

The code's documentation requirements call for a defined comparison, with its assumptions and limits. An ASET/RSET study compares available safe egress time, how long the route remains usable, with required safe egress time. Required time includes detection, alarm, pre-movement and travel. It needs project-specific occupant assumptions and safety margins. This sheet sets no universal margin.

A probability model needs supported failure rates, dependency assumptions and sensitivity checks. Treat the Edmonton example's inputs as study assumptions. The professional and permit authority assess their applicability. Edmonton technical report, PDF pages 14 and 16-26; Edmonton emergency-services guide, PDF pages 20-21.

### Edmonton emergency-service assumptions

Edmonton's emergency-services guide identifies F06, F12 and F13 as signals that a proposal may affect responders. It also asks whether the proposal changes prescribed firefighting measures, relies on timely intervention, introduces unfamiliar technology or changes occupant procedures. A single-stair proposal implicates those questions because the main exit-count attribution includes F06 and F12. Source: Edmonton emergency-services guide, PDF pages 8-9; the exact Part 3 exit-count pairing is in Attributions above.

The guide gives service targets, not an assurance of arrival at a particular fire. It describes first-pump arrival within seven minutes and a first-alarm assignment within eleven minutes from receipt of an emergency call, at the stated 90% benchmarks. It identifies locations outside the ten-minute boundary and asks designers to account for them. These times do not start at ignition. Project-specific response and water assumptions require confirmation. Source: Edmonton emergency-services guide, PDF pages 14-15.

Ladder rescue also requires usable access and setup space. The guide describes aerial apparatus reach and outrigger requirements, as well as ground ladders and hose resources. A height label such as "four storeys" does not establish that every dwelling is reachable. Source: Edmonton emergency-services guide, PDF pages 16-18. Its operational data are dated 2025-04-15 and should be confirmed for a live project.

### Standards and verification records

The following standards are verified in the second-printing code. The relevant edition must be checked against the code's referenced-documents table and the accepted design. This list does not claim that the full standards were read.

| Evidence or system | Verified standard reference and limit |
|---|---|
| Fire endurance of assemblies | CAN/ULC-S101 is a test basis for fire-resistance ratings, with the stated code exceptions and Appendix D alternative. NBC(AE) 2023 p2, Div B, Article 3.1.7.1. [PDF p.151]. |
| Fire doors and other closures | NFPA 80 is the installation reference for the listed closures. NFPA 105 applies to the listed smoke-damper and leakage-rated-door installations. NBC(AE) 2023 p2, Div B, Article 3.1.8.5. [PDF p.153-154]. |
| Surface-burning characteristics | CAN/ULC-S102 and, for the specified materials and configurations, CAN/ULC-S102.2. A flame-spread rating is not a fire-resistance rating. NBC(AE) 2023 p2, Div B, Article 3.1.12.1. [PDF p.165-166]. |
| Sprinkler design | NFPA 13 is the general reference; NFPA 13R and 13D have specific permissions and Alberta additions. Do not infer that any four-storey residential building may use NFPA 13R without checking all conditions. NBC(AE) 2023 p2, Div B, Article 3.2.5.12. [PDF p.233-234]. |
| Fire alarm installation and verification | CAN/ULC-S524 and CAN/ULC-S537 respectively. NBC(AE) 2023 p2, Div B, Sentences 3.2.4.5.(1) and (2) [PDF p.220]. |
| Integrated fire and life-safety systems | CAN/ULC-S1001 testing where systems are integrated, under NBC(AE) 2023 p2, Div B, Sentence 3.2.9.1.(1) [PDF p.245] and the Part 9 counterpart, Sentence 9.10.1.2.(1) [PDF p.875]. |

A test or listing is useful only within its tested configuration and scope. A product evaluation does not by itself demonstrate whole-building single-stair performance. No CCMC number establishing that performance was verified in this research.

### Evidence confidence ladder

This ladder describes what a source can establish. It is a research aid, not a statutory ranking.

1. The adopted code, applicable provincial interpretation and a signed site-specific variance establish the applicable rules or actual acceptance and its conditions.
2. Authenticated project analysis, drawings and relevant test or listing reports support the technical case within stated assumptions. They still require review.
3. Commissioning, integrated testing, field reviews and operating records show whether the accepted design was implemented and maintained. They do not replace design analysis.
4. Municipal technical examples and foreign regulations show approaches that may inform the analysis. They do not approve a different Alberta project.
5. A designer's published account of acceptance is useful evidence of that designer's report. Without the issued variance, its precise conditions remain unverified.
6. Advocacy, renders and unsupported claims of international safety do not establish equivalence for a particular building.

## Engineering / professional triggers

### Provincial building-code requirements

Professional involvement and the choice of an alternative solution are separate questions. The October 2026 SES interpretation expressly says that an alternative-solution author's qualifications may include registered professional status, but that status is not automatically prescribed solely by use of that compliance path. The building's characteristics and the work being done still determine the applicable requirements. Source: STANDATA 23-BCI-026/23-FCI-014, PDF pages 1-2 and 7, listed with its full URL in Sources.

The controlling building-code provisions are:

- NBC(AE) 2023 p2, Div C, Sentence 2.4.1.1.(1) [PDF p.739-740] lists the buildings normally exempt from registered-professional involvement. Its residential allowance includes a single-family dwelling or a multiple-family dwelling with four or fewer dwelling units. Part 9 is not itself an exemption.
- For buildings outside that exemption, drawings and specifications need authentication by registered professionals qualified in the applicable combination of architecture and engineering: NBC(AE) 2023 p2, Div C, Sentence 2.4.1.1.(3) [PDF p.740].
- The permit authority may require authentication and field reviews when size or complexity raises special safety concerns, even for a building otherwise exempt: NBC(AE) 2023 p2, Div C, Sentence 2.4.1.1.(4) [PDF p.740].
- Authentication must conform to the relevant professional legislation: NBC(AE) 2023 p2, Div C, Sentence 2.4.1.1.(5) [PDF p.740].
- For a project within the stated professional-involvement scope, the owner must retain the coordinating registered professional and registered professionals of record before applying for the permit, and submit the required schedules: NBC(AE) 2023 p2, Div C, Articles 2.4.2.1. and 2.4.2.2. [PDF p.741].
- Regardless of who authors it, an alternative-solution analysis must identify that person's qualifications, experience and background, and identify one coordinator where several people are responsible for different aspects: NBC(AE) 2023 p2, Div C, Sentences 2.3.1.1.(4) and (6) [PDF p.739].

The worked example has twelve dwellings. It is outside the four-dwelling residential exemption. It needs the appropriate registered professionals even before the design's single-stair complexity is considered. Do not infer that every Part 3 building requires identical disciplines or that an architect can authenticate every engineering analysis.

### Engineering work within the submission

Alberta's Engineering and Geoscience Professions Act, section 1(q), covers specified design, evaluation and related work requiring professional application of mathematics, physics or other applied subjects. Its section 2 restricts engineering practice, with the stated authorizations and exceptions. The King's Printer consolidation was accessed 2026-10-18; the definition is at PDF page 10 and the scope provisions begin at PDF page 12. [Official Act](https://kings-printer.alberta.ca/documents/Acts/E11.pdf).

Applying that definition to this topic is a research inference. A design-specific smoke-control calculation, fire/smoke simulation, tenability assessment, structural fire analysis, sprinkler hydraulic design or quantified stair-failure comparison can involve engineering practice. Those tasks require assessment by an appropriately authorized professional. A generic consultant label or software-generated calculation does not establish competence or authorization. APEGA's [terminology and legal definition](https://www.apega.ca/dictionary/common-terminology), accessed 2026-10-18, supports the distinction between an engineering degree and Alberta professional registration.

### Edmonton submission requirements

Edmonton's Point Access Block guide requires professional involvement in design, field review and preparation of the alternative solution, with properly authenticated and validated plans. It also requires a qualified fire-protection or life-safety code consultant. It recommends an early pre-application meeting and describes coordination between permit reviewers and Edmonton Fire Rescue Services. These are Edmonton's published application requirements, not a statement that every Alberta alternative solution requires the same consultant arrangement. Source: Edmonton Point Access Block guide, PDF pages 4 and 6-8.

The emergency-services guide says affected proposals are subject to professional peer review by the City's permit and fire-service teams. It calls for competent design and accurate operational assumptions. Source: Edmonton emergency-services guide, PDF pages 3, 8-9 and 20-22. [professional-involvement](professional-involvement.md) contains the companion topic; its claims must be checked against the same current sources.

## Interactions with other topics

| Companion topic | What a change to egress can affect |
|---|---|
| [fire-separations-and-spatial-separation](fire-separations-and-spatial-separation.md) | Suite and corridor separations, stair enclosures, penetrations, exterior openings and safe exit discharge. A single exit needs protection from a fire elsewhere in the building. |
| [firefighting-alarms-sprinklers](firefighting-alarms-sprinklers.md) | Sprinkler standard and coverage, water supply, alarm and smoke-control integration, firefighter access, hoses and commissioning. |
| [occupancy-and-accessibility](occupancy-and-accessibility.md) | Bedroom-based occupant load, mobility and sensory limitations, care versus residential use, common paths and practical evacuation assistance. An elevator is not automatically an evacuation solution. |
| [housing-secondary-suites-part9](housing-secondary-suites-part9.md) | The special house-with-secondary-suite exceptions, escape windows, upper-unit arrangements and smoke barriers. These exceptions do not extend to all multi-suite apartments. |
| [combustible-construction-and-mass-timber](combustible-construction-and-mass-timber.md) | Permitted height and area, floor ratings, exposed or concealed combustibles and required sprinklers. One-stair acceptance does not resolve the construction classification. |
| [hvac-ventilation-plumbing](hvac-ventilation-plumbing.md) | Pressure differences, air transfer and ducts that affect smoke movement or enclosure integrity. Ordinary comfort ventilation does not establish a smoke-control system. |
| [building-envelope-insulation-cladding](building-envelope-insulation-cladding.md) | Exterior fire spread and smoke exposure near an outside stair or discharge, plus the wind and leakage assumptions of pressurization. |
| [structural-and-framing](structural-and-framing.md) | Stair, landing and barrier support, rated assemblies and required field review. |
| [process-and-admin](process-and-admin.md) and [evidence-and-conformity](evidence-and-conformity.md) | Variance scope, source editions, acceptance conditions, commissioning, owner responsibilities and retention of the accepted report. |
| [code-structure-and-attribution](code-structure-and-attribution.md) | Exact sentence-level attribution, exceptions with no direct row, and the difference between Alberta law and national explanatory intent. |

These are interaction signals, not findings that the proposed changes satisfy those companion requirements. The protective and documentation rules cited in Benchmark acceptable solutions and Usual mitigations and evidence remain the source basis.

## Common refusal / "more info" causes

The provincial SES interpretation identifies incomplete information, incorrect assumptions or inputs, failure to demonstrate the required performance, and unclear or impractical recommendations as refusal grounds. A variance is a decision about the documented project; an applicant has no automatic entitlement to acceptance. Source: STANDATA 23-BCI-026/23-FCI-014, PDF pages 1-3 and 7.

For egress submissions, those problems commonly take the following forms. This list applies the published documentation and benchmark requirements to the topic; it is not a statistical claim about application outcomes.

- The code edition, major occupancy, building area, building height or number of dwellings is missing. The wrong Part or an inapplicable house-with-secondary-suite exception is then used.
- The application treats one stair as a permitted design because the floor is small, the corridor is shorter than 6 m, or a foreign code allows a similar building.
- Section C lists F10 and OS3.7 but omits F05, F06, F12, OS1.2 or OP1.2 where the Part 3 exit-count row requires them.
- A table exception is assigned a guessed attribution, or national explanatory intent is used to overwrite the Alberta attribution table.
- The baseline is not a lawful two-exit design for the actual project. Features required in both baseline and proposal are presented as extra compensation.
- Only nominal widths are shown. Door leaves, hardware, landings, projections, smoke-control door force and responder counterflow are omitted.
- A travel-distance drawing starts at the suite door without satisfying the measurement concession, or uses a straight-line distance through walls.
- A proposed second route joins the first before safety, passes through another suite, or depends on an unsupported ladder-rescue assumption.
- Fire and smoke analysis assumes doors always close, fans and water never fail, or everyone's mobility and response time are identical.
- The analysis considers occupants but not the emergency access and property-protection purposes attributed to the benchmark.
- Extra departures, such as longer dead ends, lobby discharge or reduced fire separation, are not declared or evaluated together.
- Qualifications, professional responsibility, commissioning, maintenance or owner handover records are absent.
- A published pilot is cited without its issued variance, scope, site limitations or acceptance conditions.

The source requirements for that information are NBC(AE) 2023 p2, Div C, Article 2.3.1.1. [PDF p.739]. The exact egress and attribution rules are cited above. Edmonton's emergency-services guide, PDF pages 8-9 and 20-22, gives the local review context.

## Precedents

### Alberta SES interpretation, October 2026

STANDATA 23-BCI-026/23-FCI-014, "Single-Egress-Stairs for buildings of residential occupancy," applies throughout Alberta. It confirms that a residential building needing multiple stairs under the acceptable solutions may instead use an accepted alternative solution with the required documentation and performance demonstration. It does not add a prescriptive six-storey allowance or give every single-stair design standing approval. It distinguishes the author's qualifications from the building's professional-involvement triggers and requires issued variance documentation to remain available on the premises after occupancy. Relevant source pages are 1-2 and 7; pages 4-6 reproduce the supporting code framework.

[Official interpretation PDF](https://open.alberta.ca/dataset/cb3d1662-1354-45c8-aab8-29b91f2a6c35/resource/e47b8923-5a81-43eb-b2ff-90106b1e688d/download/ma-standata-interpretation-joint-23bci026-23fci014-2026-10.pdf), accessed 2026-10-18. The downloaded PDF was checked against the existing extracted copy. This is an interpretation of the pathway, not an issued project variance.

Ongoing retention is also stated directly in NFC(AE) 2023 p2, Div C, Clause 2.3.1.2.(1)(b) [PDF p.355]. It covers accepted building-code alternatives attributed to the listed fire, safety-in-use and property objectives. This clause was checked with codesearch because the current structured DB lookup did not return its Division C entry.

### Edmonton guidance and a reported local pilot

The municipal guide and its companion technical and design guides are first-party guidance, not a variance instrument. They provide the application pathway, mandatory professional criteria, a method of comparison and illustrative designs. Sources: Edmonton Point Access Block guide, PDF pages 2-8; the downloaded companion guides listed in Sources. The [City's resource page](https://www.edmonton.ca/business_economy/new-commercial-building), accessed 2026-10-18, links all three companion documents. The code text takes priority over that page's simplified storey-count description.

The project team's [KHA pilot account](https://singlestair.ca/KHA), accessed 2026-10-18, reports that Edmonton accepted its three-storey, ten-unit Part 9 apartment alternative solution in September 2025 after an August resubmission. It describes three units on each upper floor, a 1200 mm exit facility, sprinklers, stronger compartmentation, short travel and a fire safety plan. It says the solution is site-specific. This verifies the team's published account. The signed variance, permit and precise acceptance conditions were not obtained, so the account is not proof that another project may copy the package.

### British Columbia ministerial order, foreign context

Ministerial Order BA 2024 03, dated 2024-08-27, created a BC pathway for residential single-exit buildings up to six storeys and 18 m, with at most four dwellings and 24 persons per floor. Travel limits are 25 m from any point and 6 m from a dwelling to the exit. The package includes NFPA 13 sprinklers, including balconies and decks, a 2 h exit enclosure, a 1500 mm exit facility and direct outdoor discharge. Additional smoke-movement provisions apply above four storeys, with the specified vestibule alternative. Fire-service capability, water and maintenance assumptions are part of the context. The order routes these designs through Part 3 rather than Part 9. It is BC law, not Alberta law or an Alberta variance.

[Official order](https://www2.gov.bc.ca/assets/gov/farming-natural-resources-and-industry/construction-industry/building-codes-and-standards/revisions-and-mo/bcbc-revision-3/2024_bcbc_mo_ba_2024_03.pdf), accessed 2026-10-18, PDF pages 1-9. This account describes that dated order, not every later BC amendment.

### Seattle, foreign context

The downloaded 2021 Seattle Building Code, Chapter 10, Section 1006.3.4, item 7, permits a single-exit condition serving no more than five storeys of Group R-2 within a building of no more than six storeys above grade plane, subject to its full conditions. These include at most four dwellings on a floor, rated construction, sprinklers, stair pressurization for an interior stair, intervening corridors, short travel, elevator protection and restrictions on communicating occupancies. A statement that Seattle permits every six-storey apartment with one stair would omit material limits. This is foreign regulatory context, not an Alberta benchmark.

[Seattle's official chapter](https://www.seattle.gov/documents/Departments/SDCI/Codes/SeattleBuildingCode/2021SBCChapter10.pdf), accessed 2026-10-18, PDF pages 9-10, printed pages 10-9 and 10-10. The download was read with macOS PDFKit because pypdf lacked its AES dependency. No project approval or safety-outcome study was inferred from the regulation.

### New York City, foreign context

The 2022 NYC Building Code's Section 1006.3.2 contains several distinct single-exit routes. Item 6 concerns buildings up to four storeys, with up to three dwellings per storey, Type I or II construction, area and access limits, protected stairs and sprinklers. Item 7 concerns Type I or II Group R-2 buildings up to six storeys and 2000 square feet per storey. These are conditional foreign provisions. They do not establish an Alberta allowance for six-storey light wood construction, or compliance with every other NYC requirement.

The [City's 2022 code page](https://www.nyc.gov/site/buildings/codes/2022-construction-codes.page) links the official chapter viewer. Its underlying PDF could not be downloaded in this run. The [current City code publication, Section 1006.3.2](https://codelibrary.amlegal.com/codes/newyorkcity/latest/NYCadmin/0-0-0-173087), accessed 2026-10-18, supplied the verified text above. The hosted publication warns that recent changes or textual errors may not yet be reflected.

### National code development, not adoption

CBHCC's [2030 priorities](https://cbhcc-cchcc.ca/en/code-priorities/), accessed 2026-10-18, include consideration of single egress within housing supply. Its [proposed-changes tracking database](https://cbhcc-cchcc.ca/en/proposed-changes-tracking-database/), accessed the same day, lists proposal 2271, "Single egress for multi-unit residential buildings," as a draft under the National Model Codes Committee on Fire and Life Safety, dated 2026-05-13. The description concerns residential buildings up to 18 m. A tracking entry is not an adopted provision. The original request's full submission and author were not verified.

The NRC's March 15, 2025 [consultation report](https://publications.gc.ca/collections/collection_2025/cnrc-nrc/NR24-129-2025-eng.pdf), PDF pages 4-8, records stakeholder feedback and plans for subsequent research. It expressly distinguishes received comments from NRC conclusions. It is not a finding that all single-stair proposals have equivalent safety. The catalogue and report were accessed 2026-10-18 through the web reader; direct local downloads returned HTML rather than a PDF.

### Related Alberta and municipal documents

- STANDATA 23-BCV-001 addresses window-opening control devices. Its province-wide allowance uses ASTM F2090 mechanisms and excludes adaptable or barrier-free dwellings. It addresses the conflict between window fall protection and bedroom escape, not the removal of an apartment's second exit. [Official variance](https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/01b622f0-f4a1-426d-b15f-ffc25e725949/download/ma-standata-variance-building-23-bcv-001-2024-04.pdf), accessed 2026-10-18, PDF pages 1-3.
- Edmonton policy interpretation B23-05 addresses openings near unenclosed exterior stairs and ramps. Its stated low-height conditions are no more than 1.5 m above ground or no more than 600 mm below ground. It is not a single-stair apartment authorization. [Official policy](https://www.edmonton.ca/sites/default/files/public-files/documents/coe-scpi-pol-int-0001-b23-05-application-of-9944.pdf?cb=1781105565), accessed 2026-10-18, PDF page 1. Its benchmark is NBC(AE) 2023 p2, Div B, Article 9.9.4.4. [PDF p.865].
- No Calgary standing posted variance or CCMC evaluation establishing general acceptance of Point Access Blocks was verified. Absence of a verified document is not a claim that no project-specific approval exists. A product report, a different city's policy or an older-edition variance needs its own scope check.

## Worked example

### Intake and classification

This is an invented application example, not an approved project or professional design.

The applicant proposes a four-storey, twelve-dwelling apartment in Edmonton. Each floor has three two-bedroom dwellings. The building area is 280 m2. There is no basement, occupied roof or commercial occupancy. The first storey is at the ground-level entrance. Upper dwellings open onto a short public corridor leading through a vestibule to one enclosed interior stair. The stair discharges directly outside. The proposed corridor has no dead-end portion over 6 m. Actual plans would need to prove every assumed dimension.

Four storeys puts this Group C building under Part 3 regardless of its small building area: NBC(AE) 2023 p2, Div A, Sentence 1.3.3.2.(1) [PDF p.39-40]. The twelve dwellings also put it outside the four-dwelling professional exemption in Div C, Sentence 2.4.1.1.(1) [PDF p.739-740].

For a concrete construction baseline, assume the building meets the sprinklered four-storey Group C construction article, including its 1800 m2 building-area ceiling, rated floors and supporting construction. This article permits combustible or noncombustible construction: NBC(AE) 2023 p2, Div B, Article 3.2.2.52. [PDF p.189-190]. This example does not seek a construction-rating variance. Select and document the sprinkler design under Article 3.2.5.12. [PDF p.233-234]. The proposed design uses NFPA 13; sprinklers already required in the baseline cannot be counted as wholly additional compensation.

The bedroom-based occupant load is 3 dwellings times 2 sleeping rooms times 2 persons, or 12 persons per floor and 48 for the building. This calculation uses NBC(AE) 2023 p2, Div B, Sentence 3.1.17.1.(1), Clause (b) [PDF p.171]. It is not a lease restriction to two residents per dwelling.

### Define the requested departure

The acceptable solution provides two exits from each occupied floor, and normally opposite-direction routes from the public corridor at each suite door. The proposal provides one shared exit instead. It therefore departs from the exit-count and opposite-direction requirements: NBC(AE) 2023 p2, Div B, Sentence 3.4.2.1.(1) [PDF p.269] and Sentence 3.3.1.3.(9) [PDF p.246]. The small-building single-exit allowance is limited to two storeys, and the stated unit arrangements do not use the private or separate alternative routes needed for the dwelling-unit exceptions.

The proposed vestibule and its protection are candidate compensation. Their effectiveness is not established by this example. The applicant must provide the professional analysis, drawings, emergency-services assessment and operating conditions. A longer dead end, unprotected direct suite-to-stair door, smaller exit or less protected discharge would be an additional design issue requiring its own analysis.

### Section C, applicable code and attributions

Applicable code: NBC(AE) 2023 p2. National 2020 intent is explanatory only. The table distinguishes the requested departures from retained or proposed protective measures. Its inclusion of a provision does not claim that every provision is being varied.

| Article or sentence and role | Objective | Function | Intent and verified source |
|---|---|---|---|
| NBC(AE) 2023 p2, Div B, Sentence 3.4.2.1.(1) [PDF p.269]. Main departure, two floor exits replaced by one. | OS3.7 | F10, F12, F05, F06 | Preserve an alternative route for occupants and responders when one route is blocked. NBC 2020 Intent Statements, 3.4.2.1.(1) [PDF p.608-609]. |
| NBC(AE) 2023 p2, Div B, Sentence 3.4.2.1.(1) [PDF p.269]. Same departure, fire injury branch. | OS1.2 | F12, F06 | Avoid delayed responder access allowing fire spread and injury. NBC 2020 Intent Statements, 3.4.2.1.(1) [PDF p.609]. |
| NBC(AE) 2023 p2, Div B, Sentence 3.4.2.1.(1) [PDF p.269]. Same departure, building protection branch. | OP1.2 | F12, F06 | Avoid delayed responder access allowing fire spread and damage to the building. NBC 2020 Intent Statements, 3.4.2.1.(1) [PDF p.609]. |
| NBC(AE) 2023 p2, Div B, Sentence 3.3.1.3.(9) [PDF p.246]. Companion departure, corridor has no second direction to another exit. | OS3.7 | F10, F12, F05, F06 | Preserve an available route and effective responder access when one egress route cannot be used. NBC 2020 Intent Statements, 3.3.1.3.(9) [PDF p.521]. |
| NBC(AE) 2023 p2, Div B, Sentence 3.4.2.5.(1) [PDF p.271-272]. Retained travel-distance benchmark. | OS3.7 | F10 | Limit delay caused by excessive travel. NBC 2020 Intent Statements, 3.4.2.5.(1) [PDF p.612]. |
| NBC(AE) 2023 p2, Div B, Sentence 3.4.3.2.(8) [PDF p.273]. Retained minimum-width benchmark. | OS3.7; OS3.1; OS1.2; OP1.2 | OS3.7 has F12 and F10; OS3.1 has F30; OS1.2 and OP1.2 each have F12. | Provide usable egress and responder access, reduce collision injury, and avoid resulting fire spread. NBC 2020 Intent Statements, 3.4.3.2.(8) [PDF p.616-617]. |
| NBC(AE) 2023 p2, Div B, Sentence 3.4.4.1.(1) [PDF p.274]. Exit protection retained and potentially strengthened. | OS1.5; OS1.2; OP1.2 | OS1.5 has F05 and F06; OS1.2 has F06 and F03; OP1.2 has F06 and F03. | Limit fire entering an exit, delaying occupants or responders, and spreading through the exit to other areas. NBC 2020 Intent Statements, 3.4.4.1.(1) [PDF p.623-624]. |

Exact Alberta attribution verification for the two requested departures:

- NBC(AE) 2023 p2, Div B, Sentence 3.4.2.1.(1): [F10,F12,F05,F06-OS3.7] [F12,F06-OS1.2] [F12,F06-OP1.2] (Div B Table attribution, PDF p.346).
- NBC(AE) 2023 p2, Div B, Sentence 3.3.1.3.(9): [F10,F12,F05,F06-OS3.7] (Div B Table attribution, PDF p.342).

The retained-measure rows are checked against the exact brackets in Attributions. A real application may need additional rows for proposed changes to corridor or suite separations, doors, alarms, sprinklers, smoke management or discharge. It should not imply those rows have been resolved before the proposed system is defined.

### Supporting calculation and evidence request

The 12-person floor load gives 73.2 mm when multiplied by the 6.1 mm doorway factor and 96 mm for a stair that qualifies for the 8 mm factor. These are capacity calculations under NBC(AE) 2023 p2, Div B, Sentence 3.4.3.2.(1) [PDF p.272]. They do not override physical minima. A stair serving the three upper storeys needs the 1100 mm minimum, and the listed doorway minimum is 850 mm, under Sentence 3.4.3.2.(8) [PDF p.273]. The fact that one stair has enough arithmetic capacity does not waive the second exit.

A reviewer needs the following Section D supporting records before evaluating the proposal:

1. Dimensioned site, floor, stair, vestibule and discharge drawings, including routes, clear widths, ratings and door operation.
2. A code analysis that explicitly compares the lawful two-exit baseline with the proposal against every applicable Section C objective and function.
3. A professional fire and life-safety assessment of the sole route's availability, credible smoke and door scenarios, assumptions, dependencies, uncertainty and limits.
4. Sprinkler, alarm and any smoke-control design and integration documents, with commissioning and maintenance requirements.
5. An emergency-services assessment addressing simultaneous access and egress, site access, water, hose routing and any rescue assumptions.
6. Professional responsibilities, authenticated documents, field review, schedules, a coordinator and the owner's operating and handover obligations.

The legal documentation basis is NBC(AE) 2023 p2, Div C, Article 2.3.1.1. [PDF p.739]. Edmonton's Point Access Block guide and emergency-services guide supply the local submission context. The example ends with the application requirements. It makes no finding that a vestibule, sprinkler standard or calculated evacuation time achieves equivalence, and it does not issue a variance.

## Open questions / uncertainty

- Project-specific equivalence remains undecided. This research does not calculate stair reliability, select a smoke-control design, assign a safety margin or authenticate any proposal.
- UNVERIFIED: the issued variance and permit conditions for the KHA pilot. The project's published account was read; no signed approval instrument was obtained.
- UNVERIFIED: the original national single-egress code-change request's full content and author. The current tracker was read and verifies proposal 2271's draft status, but the detailed submission was not retrieved.
- The Edmonton technical report's generic failure probabilities and four-storey sixteen-unit example were not independently validated. They must not be presented as measured performance of a twelve-unit project.
- A particular complex dwelling-unit arrangement may require an interpretation of how its private and shared routes interact. The sentences requiring a second, separate route cannot justify a proposal with no such route. This sheet does not claim a universal exemption for every low-rise apartment.
- UNVERIFIED: the complete current amendment histories of the dated BC order and Seattle chapter, and the applicability of those documents or the current NYC hosted text to a future project. The cited provisions were read as foreign context only.
- No Calgary standing variance or CCMC evaluation approving a generic single-stair apartment was verified. There may be site-specific decisions that are not publicly accessible.
- Full copies of the referenced testing standards were not read. Their numbers and uses were checked in the adopted code; their edition-specific scope and test reports remain project inputs.
- Operational data in Edmonton's April 2025 emergency-services guide should be confirmed for a live site. Target response times do not guarantee arrival from the instant a fire begins.
- The existing validator database currently omits NFC-AE. The retention-of-documentation clause is verified in the actual second-printing text, but its lookup cannot be certified by this database. Final validation results are recorded below rather than described as an unconditional pass.

### Access and extraction limits

The required local code, intent, form and guide files were accessible. No first-printing code, held-out evaluations, knowledge variants or source-solutions folder was read. Direct Python HTTPS downloads failed certificate verification; system curl retrieved the Edmonton, BC, Seattle and Alberta documents with normal certificate checks. Some web-reader requests returned 502 or 403 even where curl worked.

The CBHCC pages and NRC report were readable through the web reader. Direct CBHCC downloads timed out. The attempted NRC PDF downloads returned an HTML response; that file is retained with a `.response.html` extension, not represented as a successful PDF. The NYC chapter viewer was accessible, but attempted underlying PDF downloads returned 404 and the ICC-hosted chapter returned 403. The current City code publication supplied the cited NYC single-exit text. These failures do not affect the direct Alberta code checks.

### Cited provision register

The code register contains 60 distinct body articles, 59 from NBC(AE) and one from NFC(AE), plus two attribution tables. The 80 explicit sentence or clause identifiers include 79 NBC identifiers and the directly verified NFC clause. Ranges and whole-article citations are additional context, rather than a claim that every sentence is separately listed below.

NBC(AE) 2023 p2, Div A: 1.2.1.1., 1.3.3.2., 1.3.3.3., 1.4.1.2., 2.2.1.1., 3.2.1.1.

NBC(AE) 2023 p2, Div B: 3.1.7.1., 3.1.8.5., 3.1.12.1., 3.1.17.1., 3.2.2.52., 3.2.4.5., 3.2.5.12., 3.2.9.1., 3.3.1.3., 3.3.1.9., 3.3.4.2., 3.3.4.4., 3.4.1.2., 3.4.2.1., 3.4.2.3., 3.4.2.4., 3.4.2.5., 3.4.3.1., 3.4.3.2., 3.4.4.1., 3.4.4.2., 3.4.4.4., 3.4.6.3., 3.4.6.16., 9.9.2.1., 9.9.3.1., 9.9.3.2., 9.9.3.3., 9.9.3.4., 9.9.4.2., 9.9.4.4., 9.9.5.2., 9.9.6.7., 9.9.7.1., 9.9.7.2., 9.9.7.3., 9.9.7.4., 9.9.7.5., 9.9.8.1., 9.9.8.2., 9.9.8.3., 9.9.8.4., 9.9.8.5., 9.9.8.6., 9.9.9.1., 9.9.9.2., 9.9.9.3., 9.9.10.1., 9.10.1.2.

NBC(AE) 2023 p2, Div C: 2.3.1.1., 2.4.1.1., 2.4.2.1., 2.4.2.2.

The sole NFC(AE) 2023 p2 body article is the Division C retention-of-documentation provision cited under Precedents. The attribution-table identifiers and exact continued pages appear under Attributions. Foreign regulations are listed separately under Precedents and are not part of this adopted-code article count.

### Verification receipt

Verified on 2026-10-18 against base HEAD 02fb483d3afeac77ceb46066443b63dbc63dfc5b, with concurrent uncommitted work preserved:

- The working `python -m codedb` CLI was used for body text, exact attributions and intent mappings. No database rebuild or source edits were made.
- `tools/codesearch.py find` was rerun for all 62 distinct body-article or attribution-table identifiers. Every identifier had source hits in the intended code.
- All 80 explicit sentence/clause identifiers were page-checked. The 79 NBC identifiers' text openings matched the direct codesearch output from their mapped source pages, with zero mismatches. The NFC retention clause was checked directly on its actual page because it is absent from the DB.
- All 27 intent identifiers explicitly introduced by the national intent citations were re-searched in the supplement with source hits. The remaining sentences covered by ranges were read with their surrounding article entries.
- Fifty Alberta attribution rows are transcribed as exact bracket groupings. Their table pages were checked with layout-preserving PDF extraction, including the two-column continuation pages. The Section C departure rows preserve every printed attribution branch.
- The downloaded October 2026 SES interpretation was read alongside the existing source. Their SHA-256 hashes both equal `bec257a3d632abe184f4d27d3d128230d64554a58d586ff40d4ef2c373e1e65b`. The source hierarchy, foreign-law limits and designer-reported pilot status are stated explicitly.

Full-file validator command:

```text
.venv/bin/python -m codedb validate research/facts/egress-and-single-stair.md
1 files; 642 citation tokens; 1 errors; 0 warnings
unsupported_document: NFC-AE is not built; no citation check can be certified for this document
```

The command returned exit 1. This is an unsupported-document limitation, not an unverified or fabricated retention clause. It remains in the deliverable because the actual adopted fire-code text verifies it. Changing the shared database is outside this topic's ownership.

A separately scoped call to the existing validator's `validate_text` API omitted only that one NFC citation line from the input string. The file itself was not altered for this check. That run checked 640 citation tokens with zero errors and zero warnings. The full-file result above must not be reported as a clean pass.

The validator checks recognized citation syntax and source mappings. It does not validate fire engineering, decide acceptance or prove that a list of code articles is complete for an actual building. Numbered Part 3 table labels with letter suffixes were also checked directly on their source pages because the current scanner does not resolve those suffixes as table identifiers.

## Sources

All sources below were actually read in the portions identified. Web access date is 2026-10-18 unless a different document issue date is stated. Issue dates describe the source, not a claim that its contents were created on the access date.

### Adopted code, explanatory intent and application form

| Source | Exact source and portions used | Claim supported |
|---|---|---|
| NBC(AE) 2023, second printing | `reference/codes/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.pdf`; searchable copy `reference/text/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.jsonl`. Division A definitions, applicability, objectives and functions; Division B construction and egress provisions and attribution tables; Division C documentation and professional involvement. Exact PDF pages accompany each claim above. | Alberta acceptable solutions, classification, exact attribution, supporting-system references and professional requirements. |
| NFC(AE) 2023, second printing | `reference/codes/NFC-AE-2023-2nd-printing.pdf`, Division C retention of documentation, PDF page 355. | Retention on the premises of accepted alternatives attributed to the specified objectives. Verified by codesearch; outside the current DB's supported document set. |
| NBC 2020 Intent Statements, explanatory only | `reference/codes/NBC-2020-Intent-Statements.pdf`; searchable copy `reference/text/NBC-2020-Intent-Statements.jsonl`. The listed egress entries and pages are cited in Intent and the worked example. | Explanatory reasons for the corresponding benchmark sentences. Does not replace Alberta attribution. |
| Safety Codes Council variance form | `reference/guides/SCC-Variance-Form.pdf`, PDF pages 1-2. | Section C fields for article, objective, function and intent, and Section D supporting documentation. |

### Alberta and Edmonton guidance

| Source | Source location and portions read | Claim supported |
|---|---|---|
| SES STANDATA | [23-BCI-026/23-FCI-014, October 2026](https://open.alberta.ca/dataset/cb3d1662-1354-45c8-aab8-29b91f2a6c35/resource/e47b8923-5a81-43eb-b2ff-90106b1e688d/download/ma-standata-interpretation-joint-23bci026-23fci014-2026-10.pdf), all 7 pages. Existing file `reference/precedents/alberta-standata/standata-nbc2023-interpretation-23-bci-026.pdf`; fresh copy in this topic's reference folder. | Province-wide interpretation of the alternative-solution route, refusal grounds, professional distinction and ongoing retention. |
| Window-opening controls | [23-BCV-001, April 2024](https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/01b622f0-f4a1-426d-b15f-ffc25e725949/download/ma-standata-variance-building-23-bcv-001-2024-04.pdf), PDF pages 1-3; existing `reference/precedents/alberta-standata/standata-nbc2023-variance-23-bcv-001.pdf`. | Narrow ASTM F2090 window-control allowance and excluded dwellings. |
| Exterior-stair interpretation | [Edmonton B23-05](https://www.edmonton.ca/sites/default/files/public-files/documents/coe-scpi-pol-int-0001-b23-05-application-of-9944.pdf?cb=1781105565), PDF page 1; existing `reference/precedents/edmonton/edmonton-policy-interpretation-b23-05-application-of-9944.pdf`. | Local low-height application criteria for openings near exterior stairs, not blanket PAB approval. |
| Point Access Block alternative-solution guide | `reference/guides/Edmonton-Point-Access-Block-Guide.pdf`, all 8 pages, issued 2025-02-28. [City-hosted guide](https://www.edmonton.ca/sites/default/files/public-files/Point-Access-Block-Alternative-Solution-Guide.pdf). | Local application pathway, professionals, early meetings, review and illustrative character of the analysis. |
| Edmonton emergency services | `reference/guides/Edmonton-Alt-Solutions-Emergency-Services.pdf`, COE-IM-GUIDE-0040 v01, 2025-04-15, relevant PDF pages 3-9 and 14-22. | Operational-impact screening, response and equipment context, professional analysis, maintenance and commissioning. |
| Edmonton resource page | [New commercial building](https://www.edmonton.ca/business_economy/new-commercial-building), Point Access Block resource section; saved as `edmonton-new-commercial-building.html`. | Official links and publication context for the PAB guides. |
| Edmonton Building Code Guide | [Official PDF](https://www.edmonton.ca/sites/default/files/public-files/Point-Access-Block-Building-Code-Guide.pdf), all 7 pages, issued 2025-02-28; saved as `edmonton-building-code-guide.pdf`. | Companion framework, risk-mitigation options and limitations. |
| Edmonton Technical Report | [Official PDF](https://www.edmonton.ca/sites/default/files/public-files/Point-Access-Block-Technical-Report.pdf), revision 4, issued 2025-02-28; relevant PDF pages 6-10, 14-26 and 28; saved as `edmonton-technical-report.pdf`, 30 pages. | Example comparative-risk method, limited scope and four-storey sixteen-unit example. |
| Edmonton Design Guide | [Official PDF](https://www.edmonton.ca/sites/default/files/public-files/Point-Access-Block-Design-Guide.pdf), relevant PDF pages 2-12 and 27, issued 2025-02-28; saved as `edmonton-design-guide.pdf`, 27 pages. | Planning illustrations, study limits and explicit warning that the designs are not permit-ready. |

### Foreign regulations, development work and professional context

| Source | Full source URL and portion used | Claim supported |
|---|---|---|
| BC ministerial order | [BA 2024 03](https://www2.gov.bc.ca/assets/gov/farming-natural-resources-and-industry/construction-industry/building-codes-and-standards/revisions-and-mo/bcbc-revision-3/2024_bcbc_mo_ba_2024_03.pdf), dated 2024-08-27, all 9 pages; saved as `bc-ministerial-order-BA-2024-03.pdf`. | Dated BC single-exit package and conditions. Foreign context only. |
| Seattle Building Code | [2021 chapter 10](https://www.seattle.gov/documents/Departments/SDCI/Codes/SeattleBuildingCode/2021SBCChapter10.pdf), PDF pages 9-10; saved as `seattle-2021-chapter10.pdf`, 66 pages. | Conditional single-exit allowance and exact distinction between five R-2 storeys served and six storeys above grade. Foreign context only. |
| NYC code index | [2022 construction codes](https://www.nyc.gov/site/buildings/codes/2022-construction-codes.page) and [chapter viewer](https://www.nyc.gov/assets/buildings/apps/pdf_viewer/viewer.html?file=2022BC_Chapter10_EgressWBwm.pdf&section=conscode_2022). | Official chapter location. Viewer shell saved as `nyc-2022-viewer.html`; no successful chapter-PDF download claimed. |
| NYC published code text | [Section 1006.3.2](https://codelibrary.amlegal.com/codes/newyorkcity/latest/NYCadmin/0-0-0-173087), items 6-7, accessed in the web reader. | Conditional four- and six-storey routes and Type I/II restrictions. Foreign context only. |
| CBHCC priorities | [Code priorities](https://cbhcc-cchcc.ca/en/code-priorities/), 2030 housing-supply paragraph, web reader. | Single egress is an area of national development work. |
| CBHCC tracker | [Proposed-changes tracking database](https://cbhcc-cchcc.ca/en/proposed-changes-tracking-database/), proposal 2271 and status dated 2026-05-13, web reader. | Current listed draft status and description. Not an adopted Alberta allowance. |
| NRC consultation | [Report PDF](https://publications.gc.ca/collections/collection_2025/cnrc-nrc/NR24-129-2025-eng.pdf), relevant PDF pages 4-8, and [official catalogue](https://www.publications.gc.ca/site/eng/9.948976/publication.html), March 15, 2025. | Scope and limits of the stakeholder consultation. Read through the web tool; local attempted PDF response was HTML. |
| Local pilot account | [KHA on singlestair.ca](https://singlestair.ca/KHA), project status, dimensions and described compensation; saved as `singlestair-kha.html`. | Designer-reported Edmonton acceptance in September 2025, with site-specific limitation. Not a signed variance. |
| Engineering legislation | [Engineering and Geoscience Professions Act](https://kings-printer.alberta.ca/documents/Acts/E11.pdf), section 1(q), PDF page 10, and section 2 beginning at PDF page 12; saved as `engineering-geoscience-professions-act.pdf`. | Legal definition and restriction of engineering practice, subject to stated authorizations and exceptions. |
| APEGA definition | [Common terminology](https://www.apega.ca/dictionary/common-terminology), engineering and professional engineer entries. | Regulator's explanation of the definition and Alberta registration. |

Fresh downloads are under `reference/web/egress-and-single-stair/`. Existing reference documents were reused. The precedent index was used only to locate primary documents and their URLs; the claims were checked against those documents.

### Methods used

- T3 workflow router and routes: `~/.codex/skills/t3-workflow/SKILL.md` and `~/.codex/skills/t3-workflow/references/routes.md`. Applied scoped research, preservation of concurrent changes and checkpointing. The parent's maintenance receipt was reused as instructed.
- Matt Pocock research: `~/.agents/skill-libraries/mattpocock/skills/engineering/research/SKILL.md`. Followed technical claims to primary sources and saved findings in this file. No further delegation, per this task's explicit limit.
- pstack unslop: `~/.agents/skill-libraries/pstack/skills/unslop/SKILL.md`. Applied plain prose and explicit source attribution.
- PDF reading: `~/.codex/plugins/cache/openai-primary-runtime/pdf/26.1017.11052/skills/pdf/SKILL.md`. Used page-specific extraction, layout-preserving attribution-table reads and PDFKit for the encrypted Seattle source. This is a sourced text deliverable; no product UI was implemented and no product screenshot or demo was required.
