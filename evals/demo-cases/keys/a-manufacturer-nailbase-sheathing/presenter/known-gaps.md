# Known gaps in the input bundle (presenter key, don't upload)
1. **Owner** for Section A is undecided. The manufacturer isn't the owner.
2. Legal description and permit number are missing.
3. Permeance was tested at 25 mm, but 50 mm is installed. Permeance is inversely proportional to thickness (Note A-9.25.5.1.(1)), so 50 mm could be <30. Lab accreditation scope isn't stated, and the ASTM E96 edition isn't stated.
4. No air-leakage test, which is needed to apply 9.25.5.1.(1)(a)(i). The code names no method (confirmed gap).
5. The thermal resistance claim has no named insulation standard or certificate (9.25.2.2.(1)).
6. Bracing says "by sheathing", but the panel isn't a listed bracing sheathing.
7. The engineer letter is a **draft**, unsigned, and its scope excludes bracing, joints and fire.
8. There's no evaluation report. "CCMC pending" is only an enquiry.
9. No limiting distance or exposing-face data, so it can't be ruled out that 9.10.14.5/9.10.15.5 apply.
10. No operation, maintenance or inspection plan for the fastening (Div C 2.3.1.1.(2)(b)).

## Planted in inputs
Notes taken out of the client bundle. The gaps stay in the files by omission.

- `input/engineer-letter-draft-EXAMPLE.md`: no seal, no permit-to-practice number, no date of authentication.
- `input/test-summary-EXAMPLE.md`: accreditation body and scope not stated; ASTM E96 edition not stated; specimen is 25 mm (the installed product is 50 mm); not tested: air leakage, thermal resistance, 50 mm thickness, taped joints.
- `input/project-brief.md` (same text in the html and pdf): "selling in two other provinces" — claim not checked.
