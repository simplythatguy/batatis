# Calgary/Edmonton development input-reference audit

**Scope:** 25 existing Calgary/Edmonton development cases across **11 unique source groups**. The selection was `corpus.select('dev')` followed by the city filter. The prescribed selector derives split membership from the corpus catalog; only returned dev cases were inspected further. No holdout item-level facts/errors were queried, serialized, or audited. No model outputs were generated, prompts tuned, model-generation APIs called, or external files downloaded.

The support classifications below were produced by a Codex Luna agent and checked against saved sources; they are not human or professional review.

## Denominator and evidence handling

The unmodified `evals_dev.data_prompts.gold.gold` builder produced **259 original checks**: 109 source facts (F), 121 review-focus items (R), 13 boundary items (B), and 16 article references (A). All 259 are preserved verbatim as rows in [input-reference-audit.json](./input-reference-audit.json). These counts describe reference/input support, not Luna correctness or observed model accuracy. The audit does not claim 95% accuracy and does not remove or reweight checks.

The 25 cases contain **154 source facts**; 109 entered the original F denominator. The other 45 remain visible in JSON with their original text-overlap scores and independent availability judgments. A score below the frozen text-overlap threshold is not proof that content is absent: the PAB guide uses graphics for its matrix and example metrics. Conversely, high lexical overlap does not establish every conjunct, including a revision date or acceptance condition.

Every default-input attachment was read as bytes and its SHA-256 matched the corpus descriptor. There are **21 unique default attachments** (3 jpg, 18 pdf). The **five excluded records** below were read only from `source.json` metadata; their bytes were not opened. The read-only NBC(AE) code database used for article resolution has SHA-256 `672f2c44d4ca3568630bb6046c7bfece5837bbab33b01a57a35da9a5b46fc03f`.

## Material input/reference mismatches

### L04-001 — SPV-001 Revision 5 is named, but only Revision 4 is supplied

The prompt asks for “Revision 5 as an issued reference” and separately lists the attached Revision 4. The only default SPV file is `calgary-spv-001-r4-2024-7a528dc00a59.pdf`, SHA-256 `7a528dc00a5979299f7b4b8f5a3027f420df3a0c929490b6c807cab0a4cc1c36`. Its p.1 says “October 1, 2017 (Revision 4 – June 17, 2024)”; p.4 says “0.3 m allowable footing projection into the easement”; p.5 says the MARW agreement can allow a “0.6m footing projection across the property line” and keeps buildings at least 0.9 m apart. The prompt itself also states the 0.3 m / 0.6 m discrepancy, so that conflict is answerable as a prompt-plus-R4 fact. It cannot establish that the same wording is in the current R5 or that R5 was accepted on March 5, 2026.

The R5 file appears in metadata as `_evaluation/calgary-spv-001-r5-2026-bbe2767cfbeb.pdf`, role `outcome_reference`, `included_in_default_input=false`, 810,908 bytes, SHA-256 `bbe2767cfbebab533b1afa971afc9393ef56547337bd95f7996aa5d981b649de`. Its bytes were not opened. Affected scored items: `F1`, `F2`, `F4`, `F5`, and `R5`; unscored source fact `F3` is also partly version-bound. Fair repair: provide R5 as a real default input if exact current-revision extraction is intended, or make a new version expect a missing-revision request. Keep the old checks visible.

### L04-002 — prompt says SPV-002 is attached; metadata excludes it

The prompt says “Review the attached Calgary SPV-002.” The default input has B23-014 and the City guide, but SPV-002 is recorded as `_evaluation/calgary-spv-002-blazemaster-2018-dc80a2c63927.pdf`, role `outcome_reference`, `included_in_default_input=false`, 104,608 bytes, SHA-256 `dc80a2c63927fba8cb134de950b9a3cc599a2b636c1ce75588b082f82552b95f`. Without that attachment, the exact NPC 2015 clauses, BlazeMaster/partial-flow-through/DuCF scope, conditional DCVAF fallback, and permit-address condition cannot be read. The attached B23-014 (SHA-256 `eab7e795172816bc47744288e5bad17a4867c2b79cf4ba37b87cd9eee9a02017`) supports general product acceptance and project-specific alternative-solution guidance; the attached City guide says variances are not general product/equipment approvals. The affected scored checks are `R1–R3`; source facts `F1–F4` are also unsupported by default input but were not in the original F denominator.

### L04-005 — prompt says SPV-006 is attached; metadata excludes it

The prompt says “Use the attached Calgary SPV-006.” The default inputs contain B23-006, B23-005, B23-010 and the City guide. SPV-006 is recorded as `_evaluation/calgary-spv-006-2025-8df85aa592ab.pdf`, role `outcome_reference`, `included_in_default_input=false`, 450,927 bytes, SHA-256 `8df85aa592abc0272806687daf7de01c14fdc9433b97c6641192e438889e9437`. The included B23 documents support emergency-access completeness and possible professional involvement, but not the excluded SPV body/Figure 1 edition wording, SPV scope, fire/egress/sprinkler/HVAC conditions, or article `9.10.13.13.`. Affected scored checks: `R1–R3` and article check `A:9.10.13.13.`. Six SPV source facts are also outside the original F denominator. The other article `9.10.11.2.` is supported by included B23-006 p.1.

### L05-003 — technical-report conclusion is expected from an excluded report

The prompt requests review of attached Design Guide Example C. Source fact `F7` and review-focus check `R1` depend on the Point Access Block Technical Report, metadata path `_evaluation/pab-technical-report-d2d1dcfb9feb.pdf`, role `outcome_reference`, `included_in_default_input=false`, 4,010,121 bytes, SHA-256 `d2d1dcfb9feb131d537170b256780beac4a155a60d8856486afca72ba514d693`. The report bytes were not opened. The expected technical conclusion is not supported by the three attached guides. Repair by supplying the report if it is intended evidence, or making the new check ask for the missing report.

### L14-003 — drawing-only task includes profile-only and evaluator-path checks

The prompt restricts analysis to three drawing images and says not to infer storey count from an unlabelled section. The excluded `_evaluation/singlestair-kha-9d648e601877.html` record (role `outcome_reference`, `included_in_default_input=false`, 169,974 bytes, SHA-256 `9d648e601877ce7b38f25cbe1baebb56ee7981ff0cfcec517425830e2f20c79f`) supplies the profile quantities; its bytes were not opened. The typical-floor image supports the stair/hallway observation (`F3`), but not the profile’s storey, dwelling, occupant, or exit-width values. Scored `R4` asks for independent confirmation of profile-reported acceptance; `R6` scores whether the model knows the profile’s evaluator-side `_evaluation` path. `R1` is partly answerable: the visible plan supports a stair arrangement, but not the exact unit/level scope. A future drawing-only check should score visible evidence boundaries and requests for missing records, not hidden file-path knowledge.

## Answerable facts missed by text-only overlap

The Edmonton PAB cases share Design Guide SHA-256 `fd29e2084bca5467bce576a13ee65e4c2dee84615a0127699b09a6cb9ab0c79a`. The p.6 catalogue matrix and pp.17–26 Example A–M panels are graphic-heavy. In-memory OCR and visual page review confirmed the lot/zone matrix and scenario metrics. For example, Example B p.17 shows 8 units, 22 bedrooms, and 10 cars; Example L p.25 shows 18 units / 42 bedrooms in both height variants. The expanded-study discrepancies are also visible: L05-002 F7 contrasts one car per unit on p.9 with 10 cars for Example B on p.17; L05-012 F7 contrasts “up to 16” units on pp.12–13 with 18 catalogue units on p.25. Both source facts are answerable, but below the original lexical threshold. L05-003 F7 is different: it depends on the excluded technical report.

Across the 45 source facts outside the F denominator, the Luna source audit provisionally classifies 31 as supported by included evidence, 1 as partly supplied, and 13 as excluded-source-only; see every row in JSON. Across all 154 facts, the status counts are 136 supported, 5 partly supplied, and 13 excluded-source-only. A06-001 F2/F6 and L14-003 F3 are also source-supported despite not being counted. This shows both directions of error: text-only overlap can omit visible/supportable facts, while a high score can conceal a missing revision-specific conjunct.

## Fair repair choices

- Preserve the original 259 checks as the fixed historic denominator.
- Correct the three Calgary SPV input/reference pairs: provide the authentic referenced issue when it belongs in the user input, or score an explicit request for the missing issue in a new version.
- Remove hidden evaluator-path knowledge from L14-003 and align its scored claims to the drawing-only prompt.
- Include the PAB technical report only when its conclusion is an intended input; otherwise expect abstention/request for it.
- Add documented visual/OCR availability review for graphics-heavy local sources in a future version. Do not count a reduced subset as 95%.

## Method receipt

Loaded and applied Matt Pocock **research** (`/Users/aamia/.agents/skill-libraries/mattpocock/skills/engineering/research/SKILL.md`) and pstack **benchmark-checklist** (`/Users/aamia/.agents/skill-libraries/pstack/skills/benchmark-checklist/SKILL.md`) proportionately. Also followed workspace [`AGENTS.md`](../../../AGENTS.md), `/Users/aamia/.codex/skills/t3-workflow/SKILL.md`, and `/Users/aamia/.codex/skills/t3-workflow/references/routes.md`. Library roots were `/Users/aamia/.agents/skill-libraries/mattpocock/skills/` and `/Users/aamia/.agents/skill-libraries/pstack/skills/`. Evidence was restricted to selected dev-case prompt/source/evaluation metadata, actual hash-verified default input bytes, permitted extracted-text cache, and read-only local code database. The full per-case input inventory, all 259 check rows, all 154 facts, all 121 review-focus rows, and issue-level source locators/hashes are in the JSON companion.

Selected case IDs: A03-003, L05-001, L05-002, L05-003, L05-004, L05-005, L05-006, L05-007, L05-008, L05-009, L05-010, L05-011, L05-012, L05-013, L14-003, L04-001, L04-002, L04-005, A06-001, A10-001, A15-001, L06-014, L06-018, A03-004, A15-003.
