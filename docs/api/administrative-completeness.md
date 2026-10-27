# Administrative completeness: one result for both sides

Batatis checks a variance application for **administrative completeness** only: is each item the SCC
template and NBC(AE) Division C 2.3.1.1 ask for present, readable and confirmed? It never decides whether the
design complies, is safe, or is technically adequate. An empty list of findings is not an approval.

The applicant workspace and the officer workspace show the **same result**. The rules live in one place
(`engine/completeness_policy.py`), run once per request, and every route projects that one result.

## How the result is computed

1. **Prepare the package.** `engine/export/package.py` `prepare_package()` renders the exact PDF that would
   leave Batatis: the SCC form, the Batatis appendix, then visible record pages and the supporting documents.
2. **Read it back.** `engine/completeness_snapshot.py` `from_uploads()` reads that PDF the same way it reads an
   officer upload.
3. **Evaluate once.** `engine/completeness_policy.py` `evaluate()` returns one `AdministrativeReport`.

An officer who uploads the exported file gets steps 2 and 3 on the same bytes, so the result is the same.
Saved data that the form has no field for travels as visible pages in the PDF, never as hidden metadata:

| Page heading | What it carries |
| --- | --- |
| `Batatis administrative source record v1`, `Record type: professional declaration` | Whether a registered professional is involved, required, or unresolved, with the owner and location it is bound to. |
| `Batatis administrative source record v1`, `Record type: unresolved input` | A saved item that is still open: an unconfirmed answer, a required passage left unanswered (reason code `blank`), a jurisdiction notice, or a source that could not be read. |
| `Applicant supplemental statement` | A confirmed statement with no template field: code analysis, testing procedures, coordinator, failure conditions, lapsed maintenance, emergency response. |
| `Batatis supporting source v1` | A header followed by the actual pages of a named attachment. Citation and contradiction checks read these pages, not a saved extraction quote. |

A saved record can add an open item. It can never clear a problem found in the visible pages.

## Where to read it

| Route | Who | Field |
| --- | --- | --- |
| `POST /cases/{case_id}/completeness` | Applicant (owner, edit mode) | `CompletenessResponse.policy` |
| `POST /review/{case_id}/package-review` (saved case or uploaded PDFs) | Officer | `ReviewSession.policy` |
| `POST /package-review`, `POST /package-review/{package_id}` | Officer, standalone package | `ReviewSession.policy` |
| `POST /cases/{case_id}/export` (official) | Applicant | `409` `detail.reasons` equals `policy.export_reasons` |

`GET /cases/{case_id}/gaps`, submit, and the older `reviews[]` and `findings[]` lists are projections of the
same result. Build new screens on `policy`. Wire types: `AdministrativeReport` and `AdministrativeItem` in
`web/src/api/types.gen.ts`; models in `engine/models_completeness.py`.

## `AdministrativeReport`

| Field | Meaning |
| --- | --- |
| `schema_version` | `batatis.administrative_completeness.v1` |
| `policy_version` | Date of the rule set, currently `2026-10-26`. |
| `stage` | `preparation`. Batatis prepares pages for signing outside the app (see Signatures). |
| `administrative_only`, `not_a_compliance_determination` | Always `true`. Show this framing on both screens. |
| `items` | One `AdministrativeItem` per requirement checked, including the ones that passed. |
| `export_reasons` | One line per item that blocks an official export. Empty means the official PDF can be produced. |
| `ready_for_export` | `export_reasons` is empty. |

## `AdministrativeItem`

| Field | Meaning |
| --- | --- |
| `key` | Stable requirement id, for example `rationale:presence`, `div_c.testing_procedures:presence`, `citation:10:9.9.10.1.(1):nonexistent_provision`. Unique within a report. Use it as the React key and to match items across versions. |
| `field`, `section`, `label` | What the item is about. `section` is `A`, `B`, `C`, `D` or `process` (Division C 2.3.1.1 documentation). |
| `verdict` | `present`: the item is there. `missing`: it is not there, or it is a placeholder or a generic answer. `unclear`: Batatis could not establish it either way. |
| `reason_code` | Why. See the table below. |
| `reason` | One plain sentence for the screen. |
| `value` | The actual confirmed value when there is one. Never a source quote, and always `null` for an unconfirmed answer. |
| `certainty` | How the value was read: `present`, `blank` (read, and empty), `not_found` (could not be read or confirmed), `not_applicable` (a check with no single value, or a field that does not apply, such as no representative). |
| `severity` | `blocking`, `warning` or `info`. `info` never blocks anything. |
| `routed_to` | Who acts next: `applicant` (supply or fix it), `officer` (the officer must look at the source), `professional` (a registered engineer or architect must address it). |
| `export_blocking` | This item stops the official PDF. A draft is always available. |
| `submission_blocking` | This item stops submission. `false` for `info`. |
| `fix_hint` | What to do, worded for the person in `routed_to`. |
| `citations` | Code references for the requirement, from the code database only. |
| `sources`, `pointers` | Where the value came from: saved source records and file, page, form field and box. A pointer of an unread value has no quote. |

Common `reason_code` values:

| Code | Meaning |
| --- | --- |
| `supplied` | Present, nothing to do. |
| `blank`, `absent`, `placeholder` | Missing. The applicant supplies it. |
| `unconfirmed` | An answer exists but is not confirmed. The applicant confirms or withdraws it. |
| `not_found`, `unreadable`, `source_unresolved`, `signature_unread` | Uncertain. The source could not be read or resolved. The pointers show where to look. |
| `lookup_skipped` | The code database was unavailable, so the check did not run. Not a finding about the application. |
| `generic`, `thin`, `unrelated`, `stated_as_fact` | The risk, mitigation or assumptions passage is generic, a single phrase, unrelated to the proposal, or states an assumption as fact. |
| `contradiction` | A value in an attachment disagrees with the form. Both places are in `pointers`. |
| `multiple_locations` | More than one location for one variance (IB-2026-10-01). |
| `nonexistent_provision`, `superseded_edition`, `pair_mismatch`, `attribution_not_in_table` | A cited provision is not in NBC(AE) 2023 2nd printing in the division written, the edition is old, or the objective and function do not match the attribution table. A partial attribution is never reported as a match. |
| `requirement_unresolved` | Whether a registered professional is required is not settled. Routed to the officer, or to the professional when one is known to be required. |

## What the screens should show

- Group by `section`. Show `missing` and `unclear` differently: missing is "add this", unclear is "check
  this" with the pointer.
- Show `value`, never a quote, as the answer. Show a quote only as evidence next to its pointer.
- When `routed_to` is `professional`, say that a registered engineer or architect is required for this item.
- Do not word any state as compliant, safe, approved or acceptable.

## Rules shared by both sides

These used to differ between the applicant and officer checks. Each now has one definition:

- **Division C 2.3.1.1 file items.** Code analysis, testing procedures, qualifications, maintenance, and a
  single coordinator when several people or firms take responsibility are required on both sides. A
  negative statement ("No testing procedures have been provided") does not count as naming them.
- **Risk, mitigation, assumptions.** Generic, unrelated, and stated-as-fact answers are flagged on both sides.
  A real narrative that contains the word "unknown" is not a placeholder; only a whole-answer placeholder is.
- **"Demonstrate, don't assert" prompts.** Failure conditions, lapsed maintenance and emergency-response
  assumptions are warnings on both sides.
- **Owner without a representative** is valid on both sides (`certainty: not_applicable`).
- **Legal description** as lot, block and plan (or ATS) is valid on both sides.
- **One location** per variance on both sides.
- **Supporting documents.** A named attachment whose file is missing is a gap on every path.
- **Citations** are looked up in the division written next to them. A Note reference (`Note A-9.9.10.1.(1)`) is
  an explanatory note, not Division A, and is accepted if the provision exists in any division. If the
  code database is unavailable the result is `lookup_skipped`, never "does not exist".
- **Jurisdiction notices** (for example Calgary's own form) are `info` items. They never block and never crash
  the review.

## Signatures

The stage is `preparation`: Batatis produces pages for signing outside the app, so an unsigned export is
allowed. A started signature without its date is a gap. A wet or image signature cannot be read from text, so
`signature:presence` stays an officer check (`unclear`, `warning`).

## Professional involvement

The report says when a registered engineer or architect is required and the requirement is known
(`routed_to: professional`). If the requirement is not settled, `professional_requirement` is `unclear` and
routed to the officer. Batatis never writes the professional's evidence (Section D) and never judges
credentials or technical scope.

## Proof of parity

`tools/verify_completeness_parity.py` runs the three repository demo applications through nine scenarios
each (baseline, vague risk, unrelated mitigations, assumption stated as fact, second site, missing
attachment, unconfirmed owner, bad citation inside an attachment, attachment contradicting the form). For
every package it compares the applicant result, the saved-case officer result and an officer upload of the
exported bytes, field by field (pointers excluded). It needs the code database:

```bash
BATATIS_CODEDB=codedb/build/codedb.sqlite .venv/bin/python tools/verify_completeness_parity.py --out /tmp/parity
```

It exits non-zero on any mismatch and writes each PDF and both results under `--out`.
