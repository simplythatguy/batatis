# Supplied challenge form

The default `challenge_2026-09-15.pdf` is mechanically extracted from physical
pages 5-11 of the user's **Building Codes Challenge Scope Sept 15 2026.pdf**.
The original eleven-page source SHA-256 is
`761bf8d9d8e93445a49ce58c443a1a8928fa08a45a031a0adc371d45fd5a7d55`.
Its versioned field map pins the extracted asset hash. The supplied default is tracked and hash-checked during the build. The legacy
five-page SCC form is still fetched at build time into `codedb/build/`; never
commit that legacy PDF. Both forms are included in the engine bundle.

To reproduce with pypdf 6.21.1:

```sh
python -m engine.export.build_challenge_template /path/to/original.pdf --check
```

The asset preserves all seven source pages, page boxes, vector operators,
fonts, logo and printed wording. Its 74 widgets are independent canonical
terminal fields: the original source's four shared attribution parents, each
with five Kids, are split into `Article(s)`, `Article(s)1`, etc. Blank text
fields have actual appearances. Signature/consent/reviewer fields remain
blank; source helper text remains hidden; executable field actions are removed.
The source's printed Part 4 Appendix is preserved source content, never a
verified CodeDB source or generated citation narrative.

`prepare_form(hash_checked_bytes, field_map, layout)` returns editable blank
bytes plus the runtime field map. `layout` accepts a row count or measured
line counts from `form_growth.Layout`. It retains at least one attribution row
and gives each selected canonical row its own cells. The default blank remains
byte-compatible with earlier exports.

The supplied form makes room for full values at 10 pt in Sections A, B and D,
and 9 pt in Section C. Its own blue borders stretch as cells grow. A value that
crosses a page continues in matching boxes, with repeated labels or a
continuation heading. Later rows move down or onto another page. The source
Section D, disclosure and signature blocks stay intact. Intent cells show the
complete deterministic passages. Appendix C-k keeps their citation and lookup
record. No spare attribution rows are added. Inputs beyond the layout work
bounds fail explicitly instead of losing text.

The source's printed row "Legal description of property that this variance
will apply to:" has no source widget. Export draws a typed legal description
there through a temporary widget that flattening removes. The row grows or
continues beside any separately supplied lot, block and plan. Flattened
readback verifies that printed row and its continuations. The combined Section
D box grows or continues to carry every listed document and responsible party.

The new source has one combined supporting-document box. It has no separate
owner-print fields, and its jurisdiction checkbox is driven by confirmed
`scope=jurisdiction`, rather than the older form's `submitted_to_scc` fact.
Consent, signatures and their dates are not automatically filled.

`export_case` preserves the flattened public response: zero widgets and no
AcroForm tree. Drafts still bypass official completeness blocking, exclude
unconfirmed values and retain open items (`ExportResult.open_items`), result/API
metadata and the draft filename. They have no added visible draft stamp or
label on any PDF page, and no printed to-do list: the open items, their fix
hints and placeholders for unanswered passages belong to the questions and
Review. The appendix prints only real content (notices, continued values,
N/A reasons, confirmed answers and passages, Section C, listed documents), and
a draft with none of it has no appendix pages.

The legacy `scc_2026-10` map remains available explicitly, with its original
five-page bytes and SHA-256
`f44640ca005c957c11a2387d2768fffc35ef93c97125dcca37436fcc0b9afc1d`.
It retains its fixed cells and labelled appendix references for long values.
It is not equivalent to the supplied seven-page source. `BATATIS_SCC_FORM`
overrides only this legacy version. The supplied default always uses its
tracked asset; an explicit `export_case(form=...)` is still hash-checked
against the requested version.

## Re-upload reader

The upload reader uses `form_path(version=...)` for each known map and
reconstructs the dynamic blank through `prepare_form`. Exported
metadata includes `/BatatisFormVersion`, `/BatatisAttributionRows`, and
`/BatatisFormPages`. Grown cells also carry a canonical `/BatatisLayout` value.
These are reconstruction hints, never proof of uploaded content.
Source hashes, page boxes, source glyph geometry, vector borders and editable
widget identities/rectangles must match before fields are read. New layouts
require consistent version, row, page and source hints. Row reconstruction is
bounded to 256 rows. Grown-layout hints allow at most 2,000 lines per applicant
cell or attribution row, 5,000 Section D lines and 60,000 total lines. Their
minimum page requirement must fit the declared form-page prefix before
reconstruction. Appended attachment pages cannot satisfy that bound. Missing hints,
conflicts or scanned dynamic geometry produce uncertainty, with file pointers
instead of invented field locations. Legacy forms retain fixed-five rows and
overflow even when their selected-row metadata is larger. Continuation boxes
read as one field in order. An uncertain segment, or text after an empty
segment, leaves the whole field `not_found` with a pointer for officer review.

The verified runtime map supplies all attribution rectangles/page indices and
the combined `supporting_document_field`. Only pages after runtime `form_pages`
are applicant appendix pages. Printed reviewer/appeal/Part 4 pages never enter
applicant narrative extraction. An unverified layout exposes no narrative
pages. Combined Section D text is preserved as supplied; it does not establish
separate document titles, responsible people or professional approval.
