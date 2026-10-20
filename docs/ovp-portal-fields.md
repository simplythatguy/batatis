# Orders and Variances Portal checks

`engine/export/portal.py` flags the unofficial OVP rules that would reject an upload. The field list was read from the public front end at <https://ovp.safetycodes.ab.ca/> before login on 2026-10-20, with IB-2026-10-01. It is not SCC documentation. It may change, and it was not checked against the logged-in form.

What the module does now:

- Article-only code ids are flagged `needs sentence-level reference`. The id is left as written. A sentence is never picked or invented, including when the case text names one.
- Location is ready when any one of a civic address, lot/block/plan, or an ATS description is present. `municipal_address` is not required. The civic string is stored whole.
- A Variance Form and a Supporting Document are both required. Allowed formats are PDF, TXT, JPG, PNG, TIF, and CSV, up to 25 MB. File names must be 100 characters or fewer and have no special characters. A sanitized name is suggested. The file is not renamed.
- Issuing SCO, Designation of Power, Employer, Discipline, AHJ, Variance status, and Issue Date are manifest lines marked `filled by the registering SCO`. They are left blank and are never auto-filled. Permit # is optional. Owner, signature, and objectives stay in the variance form PDF and are not OVP fields.

## Post-submission

Not built. Do this after the submission package, not in the current portal module.

- **JSON sidecar and named attachment bundle.** A sidecar of OVP fields next to the variance-form PDF and the supporting files, with document-type tags and sanitized names. The case store does not hold file bytes. `POST /cases/{id}/files` on `backend/case-api` records `file.<id>.name` and keeps the PDF outside the case JSON.
- **Derived discipline and AHJ.** Fill these from `Case.jurisdiction` only when the mapping is unambiguous, and leave them blank for the registering officer otherwise. Employer stays with the officer. Do not copy an applicant fact into an OVP list field.
- **Civic address split.** Parse `municipal_address` into suite, house, street, municipality, and postal code. If the string does not parse, keep it whole and flag it. Do not invent the missing parts. Lot/block/plan and ATS range checks (section 1–36, township 1–126, range 1–30, meridian 4, 5, or 6) belong with that parser.
- **Lists that load after login.** Variance status, discipline, AHJ, employer, and code-set options are server lists. Until those values are known, store free text and a TODO. Do not treat a Batatis string as the OVP list id.
