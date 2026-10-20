# Orders and Variances Portal fields in the portal package

`engine/export/portal.py` prepares a package for the safety codes officer who registers a variance. Registration is not Council approval, and the applicant does not register.

The field list is **unofficial**. It was read from the OVP public front end at <https://ovp.safetycodes.ab.ca/> before login on 2026-10-20. There is no public field-list document. The list may change without notice, and it was not checked against the logged-in form. Variance status options and code-set names are loaded after login and are not known here.

What the package does with that list:

- Issuing SCO, Designation of Power, Employer, Discipline, AHJ, Variance status, and Issue Date are manifest lines marked `filled by the registering SCO`. They are left blank and are never auto-filled. Permit # is optional.
- Location accepts any one of a Civic Address (street and postal code split from the civic string), lot/block/plan, or a complete ATS description. The civic label is Civic Address. `municipal_address` is not required.
- A code item is a Code Set / Standard plus a sentence-level id such as `3.5.2.1.(2)`. An article-only id is flagged `needs sentence-level reference before OVP`. The sentence is never invented.
- Each file is tagged Variance Form or Supporting Document, and both are required. Allowed formats are PDF, TXT, JPG, PNG, TIF, and CSV, up to 25 MB, with file names of 100 characters or fewer and no special characters. A sanitized name is suggested; the file is not renamed.
- Owner, signature, and objectives stay in the variance form PDF. They are not OVP fields.
