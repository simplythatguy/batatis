# Coded rules: what the domain reviewer must check (WP-31, AC5.1)

The coded rules are not trusted until a person who knows Part 9 of NBC(AE) 2023 signs the vectors. Until then every rule file (`engine/data/rules/*.json`) and every vector (`vectors.json`) carries `reviewed: false`, and every result says so. Batatis never presents a rule result as a finding about the whole design; the reviewer checks that each flag reads the code correctly.

Source of truth: NBC(AE) 2023, 2nd printing (`reference/codes/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.pdf`). PDF page numbers below are the file's pages. Code citations and pages are already checked by machine against the code database (`engine/tests/test_rules_vectors.py`); the table numbers and the readings below are not, and need a person.

Time needed: about 2 hours. A readable form of every vector with its full output: `evals_dev/rules/outputs.json` (search for the vector id).

## 1. Tables (transcribed by hand from the PDF)

- [ ] **Table 9.10.15.4.** (PDF p.902), in `glazed-openings-houses.json` → `tables[0]`: the 12 limiting-distance columns and 5 rows. `null` stands for the printed dash.
- [ ] **Table 9.10.14.4.-A** (PDF p.895), in `unprotected-openings.json` → `tables`: both occupancy groups (residential, business and personal services, low-hazard industrial; mercantile and medium-hazard industrial).
- [ ] A dash is read as 100% (no limit). Every dash follows a 100 entry in the printed table.
- [ ] Row choice: the first row whose "Maximum Total Area of Exposing Building Face" is not less than the actual area (a 30.5 m² face uses the 40 row; 100.5 m² uses "Over 100"). Vectors G20, G21.

## 2. Readings the vectors depend on

Each of these is a choice made in the rule data. Mark it agreed, or write the correct reading and the vectors that change.

**Openings, houses: 9.10.15.4.(1) (`glazed-openings-houses`)**
- [ ] Column choice: the column for the lesser limiting distance nearest to the actual one, and, for limiting distances greater than 1.2 m only, linear interpolation between columns, because the Notes to Figures A-9.10.15.4.(2)-B and -C (PDF p.1380, note 4) call interpolation "also acceptable". A result that only fits by interpolation says so in its message (`follows_interpolated`, vectors G08, G09, G18). Is it right to show these as "follows"?
- [ ] The permitted area under Sentence (1) is the larger of Clause (a) (Table) and Clause (c) (limiting distance squared, only where the limiting distance is not less than 1.2 m). Clause (b) (Subsection 3.2.3.) is not evaluated; it is listed under `not_checked`. Vectors G06, G07, G22.
- [ ] Sentence (7): "up to twice the area determined in accordance with Sentence (1)" is twice that larger value, for glass blocks, or for a sprinklered building where every room behind the face with glazed openings is sprinklered. Vector G10.
- [ ] Sentence (6) (faces its own detached garage) is shown as "follows" with Sentence (6) cited, not as "not applicable". Vector G11.
- [ ] Below 1.2 m the table is 0%, so any glazing departs (G04), and no glazing follows (G05).

**Openings, other Part 9 buildings: 9.10.14.4.(1) (`unprotected-openings`)**
- [ ] No interpolation is used for Table 9.10.14.4.-A (no Note permits it for this table). Lesser column only.
- [ ] Occupancy to row: business, hotel, multi-unit residential with a unit above another, and low-hazard industrial use the residential row; mercantile and medium-hazard industrial use the mercantile row; high-hazard industrial is outside Part 9 (U06); assembly, care, treatment, detention, farm, camps and mixed use are "not applicable" (U17). Is "not applicable" right for a Group B, Division 4 home-type care occupancy, which Part 9 covers but Table 9.10.14.4.-A does not list?
- [ ] Clause (c)(ii): half the limiting distance squared for mercantile and medium-hazard industrial (U03, U04).
- [ ] Sentences (8) (open-air storage garage, limiting distance not less than 3 m) and (9) (storey facing a street at street level, not less than 9 m) use the **actual** limiting distance, as Sentence 9.10.14.3.(1) excludes them from halving (U16). Sentence (8) is offered only for industrial occupancy (a storage garage is Group F, Division 3).
- [ ] Sentences (10) and (11) (detached garages serving one dwelling unit) are not coded; listed under `not_checked`.

**Half the limiting distance (9.10.15.3.(1) and 9.10.14.3.(1))**
- [ ] Applied where the fire department response exceeds 10 minutes in 10% or more of calls and any storey is not sprinklered. `sprinklered: "partial"` is treated as "some storey is not sprinklered". Vectors G12, G13, S07, S08, S09.
- [ ] Applied to the soffit rule too: 9.10.15.3.(1) halves the limiting distance for all of Subsection 9.10.15. except 9.10.15.2.(2), 9.10.15.4.(3) and 9.10.15.5.(13), so the 0.45 m test in Sentences 9.10.15.5.(8) and (9) uses the halved value. The soffit-to-property-line distance in Sentence (9) is not halved.

**Soffits: 9.10.15.5.(8) to (10) (`soffits-houses`)**
- [ ] A limiting distance of exactly 0.45 m falls under Sentence (8) ("not more than 0.45 m"): no projecting soffit (S01).
- [ ] A soffit face exactly 0.45 m from the property line follows Sentence (9) ("shall not project to less than 0.45 m") (S02); 0.44 m departs (S03).
- [ ] Sentence (10) (faces a public way) is an exception to both (8) and (9) (S04, S05).
- [ ] Sentence (11) protection and the cladding Sentences are not checked; listed under `not_checked`.

**Firewalls: 9.10.11.2.(2) (`firewall-suite-rowhouses`)** — the reading most in need of a decision
- [ ] Reading used: Sentence (2) applies when a building of residential occupancy contains more than 2 houses and at least 2 of them have a secondary suite, and it is met when no part of the building between firewalls contains more than 2 adjacent houses with a secondary suite. This follows the purpose clause ("to create separate buildings each containing no more than 2 adjacent houses with a secondary suite") and how the City of Calgary (SPV-006) and the City of Edmonton (Policy B23-01) describe the Sentence.
- [ ] Consequence to confirm: a building of 3 or more houses where only 2 have a secondary suite "follows" with no firewall (F06). A stricter literal reading ("a party wall that separates any 2 adjacent houses with a secondary suite from the rest of the building shall be constructed as a firewall") would make F06 depart, and would change the `follows` outcome.
- [ ] Fewer than 2 houses with a secondary suite is "not applicable"; party walls then follow Sentence (1) (F05).
- [ ] The input "largest number of adjacent houses with a secondary suite in one part between firewalls" is the right question for an applicant to answer.

**Fire dampers: 9.10.13.13.(1) (`fire-dampers`)**
- [ ] Boundaries: Sentences (2) and (3) need a melting point "not below 760°C" (760 passes, D06); Sentence (4) needs "above 760°C" (760 fails, D10; 761 passes, D11). Sentence (2) area "less than 130 cm²" (130 fails, D05; 129.9 passes, D04); discharge "not more than 1.2 m" (1.2 passes). Sentence (3) "not less than 500 mm" (500 passes, D08; 499 fails, D09).
- [ ] Sentence (3)'s "exhaust duct riser in which the airflow is upward" is part of the duct category the applicant picks, not asked separately.
- [ ] 9.10.9.9.(5), which Sentence (1) also names, is read as permitting a fire damper without the firestop of 9.10.9.6.(1); it is not treated as removing the need for a damper. Listed under `not_checked`.
- [ ] 9.10.5.1.(3) (openings in a rated membrane ceiling, conforming to Appendix D) is treated as an exception (D12, D13).

**Every rule**
- [ ] Part 9 scope: more than 3 storeys, or a building area over 600 m², is "not applicable" (Div A 1.3.3.3.(1)); 600 m² exactly stays in Part 9 (D19, D20). When storeys or area are not stated, the rule assumes Part 9 and says so (G17, S14).
- [ ] Subsection 9.10.15. applies to houses (`single_family`) and to `multi_family` buildings with no dwelling unit above another (9.10.15.1.(1)); otherwise 9.10.14.

## 3. Wording

- [ ] Every `message` in the five rule files, `notice`, `needs_info_message` and `departs_next_step` in `index.json`. None may say or imply that the design complies, is safe, approved or adequate (a test enforces the words; the reviewer checks the meaning).
- [ ] `departs_next_step` describes the alternative solution (Div C 2.3.1) and the request for variance (Safety Codes Act s.38) as what the applicant does, and the officer as the one who decides.
- [ ] Every `question` and `why` in `index.json` → `inputs` is answerable by an applicant without a professional, or says who can answer it (fire response time).

## 4. The vectors

- [ ] For each of the 88 vectors in `vectors.json`: the `inputs` and `description` make sense, and `expect` (state, outcome, deciding Sentence, questions asked) is what you would conclude from the code text. The expected values were set by hand from the code text, not from either evaluator.

## Sign-off

When every box is ticked (or the disagreement is written down and the data fixed): set `reviewed: true` on each vector and each rule file you signed, run `python -m engine.rules.golden`, and add a row here.

| Reviewer | Role or qualification | Date | Rules and vectors signed | Notes |
|---|---|---|---|---|
| | | | | |
