# Backend integration checkpoint — 20 October 2026

Verified implementation revision: `c7fd734c049dad40a9239b03cc03e6807f28ee7c`.
This records the integrated case-building, export, extraction and development-fixture work.
It is a backend checkpoint, not completion of the full [build plan](2-week-build.md).
Implementation and delegated review roles used GPT-6.1-Sol at max effort under the user's temporary model override.

## Integrated behavior

- Section D evidence requests follow the confirmed Section C objective/function rows.
  Professional-involvement rules, CCMC search, applicant-written process fields and completeness
  checks are available through the case API.
- Final PDF export recomputes completeness from the current case. Calling export directly cannot
  bypass the checks by supplying an empty gap list. Citations, attribution pairs and the full
  explanatory-intent payload must match their canonical database rows.
- Later unconfirmed or blank facts invalidate earlier answers. Drafts omit these answers, rebuild
  Section C from verified confirmed provisions, and show the unresolved items. Applicant-authored
  process answers and linked supporting-document metadata appear in the appendix.
- PDF glyph geometry repairs word spacing and supported superscripts/subscripts. A homogeneous
  script run is converted together; conflicting or unsupported runs preserve the entire raw line.
  The original extraction remains available. Standalone CodeDB requirements now declare PDFium.
- The development set contains 60 cases: 18 ask, 38 proceed conditionally and four redirect.
  All 25 originals were source-checked; 35 were added and independently model-reviewed.
  The impossible area/diagonal combination in `dev-027` was corrected. The set is model-checked,
  not human/professional-reviewed. Details are in [the review ledger](../../../evals_dev/REVIEW.md).
- Committed JSON is the sole fixture-authoring source. `author_cases.py` defaults to a read-only
  check; explicit `--write` refreshes only deterministic Section C values after batch validation,
  preserving narratives, semantic labels and authoring receipts.

## Verification on the integrated checkout

Run from the repository root unless otherwise stated:

```sh
.venv/bin/python -m codedb build
.venv/bin/python -m pytest -q engine/tests codedb/tests evals_dev -rs
.venv/bin/python -m codedb.audit
.venv/bin/python evals_dev/author_cases.py --check
.venv/bin/python evals_dev/validate_cases.py
.venv/bin/python -m engine.schema_export --check
git diff --check
# From web/:
npm run build
```

- Combined pytest: **254 passed, two skipped**. One identification test requires
  `ANTHROPIC_API_KEY`; the other requires the explicit live-call flag `BATATIS_LIVE_JEV=1`.
  Neither skip proves provider behavior or live accuracy.
- Source spot audit: **30 checks, zero mismatches**.
- Fixture validator: **60 cases, 249 citations, 39 Section C rows, 68 attribution
  brackets/conditions, zero errors**. Refresher check found zero drift.
- Schema generation, TypeScript/Vite build and whitespace checks passed.
- Numerical-content checks preserved digit sequences in **24,639** provision, note and intent
  records, after decoding intent JSON and excluding source list-heading numbers.
  This is an inventory check, not proof of formula interpretation.
- The final text audit scanned 44,782 fields and reported 567 split-word, three glued-term,
  eight unit and six hyphen warnings, with zero mixed-digit-script warnings. These are heuristic
  flags, not confirmed error counts. It retained 369 unreconstructed line occurrences, including
  74 with uncertain scripts, for source inspection.

The parent compared the rebuilt database with the preserved pre-integration database.
All 13,743 provision identities/metadata/raw text, 774 note records apart from reading text,
10,122 intent metadata rows, 11,501 attribution rows, attribution statuses, intent comparisons,
code-table records and definitions remained identical. Derived note links changed from 1,658 to
1,667: ten full references were recovered from split text, and one truncated `A-3.8.` link was
removed. Each recovered reference matches the original raw text after removing whitespace and
points to an existing note.

## Export evidence

Fresh samples were generated on the integrated checkout and rebuilt database:

```sh
.venv/bin/python -m engine.export.sample /tmp/batatis-verification-20261020/final
```

- [Synthetic final PDF](/tmp/batatis-verification-20261020/final/sample.pdf)
- [Incomplete draft PDF](/tmp/batatis-verification-20261020/final/sample-draft.pdf)
- [Inspected form](/tmp/batatis-verification-20261020/final/sample-page1.png)
- [Inspected applicant process appendix](/tmp/batatis-verification-20261020/final/sample-appendix1.png)
- [Inspected source text and units](/tmp/batatis-verification-20261020/final/sample-page-07.png)
- [Inspected draft omissions](/tmp/batatis-verification-20261020/final/sample-draft-appendix1.png)

Both PDFs have five form pages and ten appendix pages. The final PDF is flattened.
The fixtures explicitly label all purported evidence and professional identities as synthetic.
Signatures and officer decisions remain blank. Saved page images were opened and inspected;
this is PDF evidence, not a recorded browser journey.

T3 preview open/navigation/snapshot attempts failed, including:
`No preview automation host is available for snapshot in environment 224cc28a-dc1b-41dd-a30a-04624c99df16. The server-owned browser may be starting or reconnecting.`
Browser recording was unavailable. No new frontend surface was implemented in this checkpoint.

## Remaining limits and next work

The checker verifies administrative presence and source consistency. It does not authenticate
attachments, inspect their bytes, establish professional competence, judge evidence adequacy,
or automatically resolve contradictory/irrelevant evidence and generic risk narratives.
Image-rendered mathematical symbols absent from the PDF text layer remain missing; formula
recovery is partial. The uncertainty report retains lines requiring source inspection.

The frontend still needs the new evidence, process, preflight and export API flow connected and
tested in the browser. Live identification benchmark gates, latency/cost measurements and
human/professional fixture checks remain outstanding. These results establish neither 100%
accuracy nor technical compliance or safety.

## Methods used

- [T3 workflow and routing](~/.codex/skills/t3-workflow/SKILL.md)
- [pstack feature workflow](~/.agents/skill-libraries/pstack/skills/poteto-mode/playbooks/feature.md)
- [Matt Pocock code review](~/.agents/skill-libraries/mattpocock/skills/engineering/code-review/SKILL.md)
- [Matt Pocock diagnosis](~/.agents/skill-libraries/mattpocock/skills/engineering/diagnosing-bugs/SKILL.md)
- [PDF rendering and inspection](~/.codex/plugins/cache/openai-primary-runtime/pdf/26.1017.11052/skills/pdf/SKILL.md)

Worker-specific research, TDD and adversarial-review receipts appear in the task results and
development-case review ledger. No held-out judge cases were opened.
