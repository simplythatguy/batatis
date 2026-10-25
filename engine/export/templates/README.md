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

`prepare_form(hash_checked_bytes, field_map, row_count)` returns editable blank
bytes plus the runtime field map. It retains at least one attribution row,
copies the original continuation-row vector operators for more rows, and
moves the intact original Section D/disclosure/signature block. It closes
table-only pages with the source's bottom rule. Each selected canonical row
has its own native cells. An intent cell shows the deterministic passages, or
their start and `(full text: Appendix C-k)`; Appendix C-k prints each passage
once. A long applicant value keeps a labelled reference and its complete text
in the generated appendix. No spare rows are added.

The source's printed row "Legal description of property that this variance
will apply to:" has no widget. Export alone draws a typed legal description
there through a temporary widget that flattening removes; `prepare_form`, the
field map and the re-upload reader keep the source's own 74 widgets. The
combined Section D box lists as many whole entries as it holds, then
`D-k to D-n: continued in Appendix D`.

The new source has one combined supporting-document box. It has no separate
owner-print fields, and its jurisdiction checkbox is driven by confirmed
`scope=jurisdiction`, rather than the older form's `submitted_to_scc` fact.
Consent, signatures and their dates are not automatically filled.

`export_case` preserves the flattened public response: zero widgets and no
AcroForm tree. Drafts still bypass official completeness blocking, exclude
unconfirmed values and retain open items, result/API metadata and the draft
filename. They have no added visible draft stamp or label on any PDF page.

The legacy `scc_2026-10` map remains available explicitly, with its original
five-page bytes and SHA-256
`f44640ca005c957c11a2387d2768fffc35ef93c97125dcca37436fcc0b9afc1d`.
It is not equivalent to the supplied seven-page source. `BATATIS_SCC_FORM`
overrides only this legacy version. The supplied default always uses its
tracked asset; an explicit `export_case(form=...)` is still hash-checked
against the requested version.

## Re-upload reader

The upload reader uses `form_path(version=...)` for each known map and
reconstructs the dynamic blank through `prepare_form`. Exported
metadata includes `/BatatisFormVersion`, `/BatatisAttributionRows`, and
`/BatatisFormPages`; this is a layout hint, not proof of uploaded content.
Source hashes, page boxes, source glyph geometry, vector borders and editable
widget identities/rectangles must match before fields are read. New layouts
require all five consistent version/row/page/source hints; row reconstruction
is bounded to 256 rows and checked against observed pages. Missing hints,
conflicts or scanned dynamic geometry produce uncertainty, with file pointers
instead of invented field locations. Legacy forms retain fixed-five rows and
overflow even when their selected-row metadata is larger.

The verified runtime map supplies all attribution rectangles/page indices and
the combined `supporting_document_field`. Only pages after runtime `form_pages`
are applicant appendix pages. Printed reviewer/appeal/Part 4 pages never enter
applicant narrative extraction. An unverified layout exposes no narrative
pages. Combined Section D text is preserved as supplied; it does not establish
separate document titles, responsible people or professional approval.
