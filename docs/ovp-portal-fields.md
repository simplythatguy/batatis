# Orders and Variances Portal fields in the portal package

`engine/export/portal.py` prepares a package for the safety codes officer who registers a variance. Registration is not Council approval, and the applicant does not register.

The field list is **unofficial**. It was read from the OVP public front end at <https://ovp.safetycodes.ab.ca/> before login on 2026-10-20, together with IB-2026-10-01. There is no public field-list document. The list may change without notice, and it was not checked against the logged-in form. Variance status, discipline, AHJ, employer, and code-set options load after login, so the sidecar stores them as free text with a TODO.

The package writes `ovp-sidecar.json` plus named attachment files.

- Issuing SCO, Designation of Power, Employer, Variance status, and Issue Date stay blank for the registering officer. Permit # is optional and comes from `permit_number`.
- Discipline is the free-text value Building only when `Case.jurisdiction` is set and the confirmed code set is the National Building Code alone. AHJ is `Case.jurisdiction.authority` or `.name` only when those two do not disagree. Any other case leaves the field blank.
- Civic Address is parsed from `municipal_address` (aliases `civic_address` and `address`) into suite, house, street, municipality, and postal code. A string that does not parse is kept whole and flagged. Lot/block/plan or a complete ATS description (section 1–36, township 1–126, range 1–30, meridian 4, 5, or 6) is enough on its own.
- A code item is a Code Set / Standard plus a sentence-level id such as `3.5.2.1.(2)`. An article is mapped through codedb only when the case's own facts or quote name one sentence that codedb lists. Several possible sentences are candidates flagged `needs sentence-level reference`. One is never picked.
- Each file is tagged Variance Form or Supporting Document, and both are required. Allowed formats are PDF, TXT, JPG, JPEG, PNG, TIF, TIFF, and CSV, up to 25 MB, with file names of 100 characters or fewer and no special characters. A sanitized name is suggested.
- `POST /cases/{id}/files` on `backend/case-api` stores `file.<id>.name` on the case and keeps the bytes outside the case JSON. A supporting file that is only a name is a blocking portal gap: `supporting document file missing`.
- Owner, signature, and objectives stay in the variance form PDF. They are not OVP fields.
