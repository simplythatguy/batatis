# MVP acceptance test: three personas, cold run to the SCC Variance form PDF

Label: **model-checked, not human-verified**. Written 2026-10-20, about 2:45 PM MDT (UTC-6), by Data Nerd. Read-only: the GitHub repo (simplythatguy/batatis), local research files, and public sources. Nobody was contacted and nothing was posted.

Code text: National Building Code – 2023 Alberta Edition (NBC(AE) 2023), 2nd printing, © National Research Council of Canada. Excerpts quoted with attribution for research. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499

**Scope:** IP and BP are docs, out of scope; X Factor recorded as observations only (no pass/fail).

**Where each fact comes from**
- **Repo, branch `dev` @ `adb7f88`:**
  - `evals/demo-cases/{a,b,c}-*/input/*`
  - `engine/export/field_maps/scc_2026-10.json`
  - PR descriptions #11, #12, #16, #21, #23–#26, #30–#34
- **Unc session notes (not in this repo):**
  - session 4 (Dana, #16 @579cd2c)
  - session 5 (Mira, #16 @579cd2c)
  - session 3 (Carlos, #16 @579cd2c, plus BAT-55 at @27bec3e)
- **Our research files:**
  - `identify-regression.json`
  - `carlos-s1-backing.json`
  - `human-review-triggers.json`
  - `heldout-v2-sealed/README.md` (README only; the gold is sealed and was not opened)
- **Code text:** codedb (NBC(AE) 2023 2nd printing).
- **Not used as evidence:** `keys/`, `expected/` and README answer keys (Karen's guardrail).

---

## 0. Ground rules for the tester

1. **Start state.** Use a fresh browser window with no saved case. Session 5 found that the landing page reopened the previous user's case; BAT-55 on @27bec3e reports this fixed. Start the clock when the landing page loads. Stop it when the PDF has downloaded and opens.
2. **Input.** Use only the case's `input/` files. Paste the project brief into Describe and attach the other files if upload works. If a field has to be typed by hand, type only values that are in `input/`. Never invent a value, for example a registration number.
3. **"Not sure".** Whenever the persona would not know an answer, choose **Not sure**.
4. **Record everything.** Note the blocking-gap count after each step, the wall-clock time, and every sentence that breaks the overclaim rule (section 5).
5. **Two environments.**
   - **Live:** https://batatis-vert.vercel.app. Live per aamia's 14:53 decision (OpenAI on, hard cap US$20, codedb bundled). Engine steps are testable on live once deployed; record the live commit.
   - **Dev:** branch `dev` run with the engine, the codedb and the SCC form configured. Which dev URL to use is TBD (section 7).

## 1. Pass criteria (each persona)

| # | Criterion | How to check | Source |
|---|---|---|---|
| P1 | Finished in **≤ 15 min** wall clock, landing to an opened PDF. Internal target (Unc session cap), not a rubric figure. | stopwatch | session 3 ("Run 14:00-14:16 (15-min cap)") |
| P2 | **0 blocking gaps wrongly closed** (a gap closed without the evidence, or the confirmation, the case lacks) | compare the gap list with the "must stay open" list for the case | #23 (`evidence_listed` is not a sufficiency check), #26 (a professional is confirmed only by the applicant's role plus seal or registration number) |
| P3 | **0 blocking gaps wrongly left open** (a gap whose answer is in `input/` and was given, but which stays open) | compare with the case's "answerable from input" list | sessions 3 and 4 (narrative saved only on blur; answers didn't refresh) |
| P4 | **No overclaims** (section 5 list) anywhere in the UI, the text record or the PDF | read every screen; then `pdftotext` the PDF and grep it | Karen's guardrails; #27 grep list (`complies`, `compliant`) |
| P5 | **Every citation resolves** in the 2nd-printing codedb, at the right Div and page | look up each cited id with `codedb lookup`, or by hand against the case's gold list | codedb snapshot |
| P6 | The gold citations for the case appear: as Code check cards, as Section C rows, or as an explicit open question naming them | case gold table | §2–4 |
| P7 | **Export opens and its fields match** `scc_2026-10.json`. The permit number sits in field **`Permit`** (Section B, label "Permit Number (if applicable)", fact `permit_number`) when the case has one, and that field is **blank** when the case has none | open the PDF; read the AcroForm values (command below); otherwise `pdftotext` | field map on `dev` |
| P8 | Mandatory human-review triggers that apply to the case show up as a route to a person, never as a ruling | Section D and the officer list | `human-review-triggers.json` |
| P9 | **Public URL (live only).** (a) The privacy notice names OpenAI (US) as a processor, in both the web app and the API. (b) `GET <live>/codedb.sqlite` and any static codedb path return 404. (c) Every response has at most 25 words per snippet and at most 75 in total. (d) When the cap is spent, a labelled BM25 fallback ('keyword search, no AI') shows. (e) `/identify` and `/ccmc/search` are rate-limited. (f) Live identify results are labelled as model output. | browser plus `curl -s -o /dev/null -w '%{http_code}' <live>/codedb.sqlite`; read the privacy notice and API docs; count snippet words | Karen review; aamia 14:53 decision |
| P10 | **Eval strings.** Any number shown in the UI, the text record or the PDF is an approved string, verbatim, labelled 'model-checked, not human-verified', and dev-set only. None of the §5 item 12 strings appears. | grep the UI text, the .txt record and `pdftotext` of the PDF | Karen review |

**How to read the export fields** (no network needed):

```sh
python3 -c "from pypdf import PdfReader as R; f=R('APP.pdf').get_fields() or {}; [print(k,'=',(f.get(k) or {}).get('/V')) for k in ['Owner','Owner Rep','Mailing Address','Date of Reqeuest','Permit','Municipal Address','Lot','Block','Plan','Code or Standard','Article(s)','Supporting Doc','Name Responsible']]"
```

- The field names are the form's own `/T` values, including the typo `Date of Reqeuest` (field map note).
- If `get_fields()` comes back empty, the PDF may be flattened. Use `pdftotext -layout APP.pdf -` and check by label. Whether the export is flattened is TBD.
- **What the field map defines:**
  - **Required facts** (`required_facts`): `owner_name`, `mailing_address`, `request_date`, `municipal_address`.
  - **`Code or Standard` default:** "National Building Code - 2023 Alberta Edition (2nd printing), Division B". Per #25, "2nd printing" is written only when the codedb label is NBC(AE) 2023 p2.
  - **Officer and signature fields** (`skipped.officer`, `skipped.signature`) must be **blank**.
- **Why the form matters:** SCC IB-2026-10-01, page 4 of the IB PDF: "The revised variance form must be completed and included when the variance is registered through OVP."
- **Form facts:** the form has 87 AcroForm fields, sha256 `f44640ca005c957c11a2387d2768fffc35ef93c97125dcca37436fcc0b9afc1d`. It is git-excluded and configured with `BATATIS_SCC_FORM` (#24, #25).

## Cold-run steps (shared screen flow)

Screen names come from #16, the live page and the Unc reports.

- **S1 Landing / role picker:** pick the role.
- **S2 Describe:** paste and upload.
- **S3 Applicant and site details:** Sections A and B.
- **S4 Code check:** article cards, each with Yes / No / Not sure.
- **S5 Section C:** objectives, functions and intent.
- **S6 Section D:** professional involvement and the issues screen.
- **S7 Alternative path:** rationale, risk assessment, mitigating measures, assumptions and limits.
- **S8 Check completeness.**
- **S9 Application PDF export.** A draft is allowed while a gap is legitimately open; per #21, a draft is stamped `DRAFT, open gaps`.
- **S10 Officer review (mandatory, on the scoring sheet for every persona; not inside the 15-min clock):**
  - The officer opens the same case id the applicant used.
  - Every Not sure from S1–S9 appears as an officer item marked 'SCO decides'.
  - The deficiency list equals that case's must-stay-open list (A4, B4, C4).
  - Attachments show as 'evidence listed (not reviewed)'.
  - An information request can be drafted.
  - Record time-to-first-request as observed, with no threshold.
  - Contradictions are labelled as the safety codes officer's (SCO) judgement.

**Required in every persona (Karen):**
- **S2 upload check:** attach the case's other `input/` files. They are listed, and their facts are proposed with the file as source. If upload isn't deployed, record N/A (environment).
- **S3/S4 scope:** the app *proposes* the Part (B: Part 3, citing Div A 1.3.3.2.(1)(c), PDF p.39; A and C: Part 9, citing Div A 1.3.3.3.(1), PDF p.40). Fail if the scope is stated as a ruling rather than proposed.
- **S4 benchmark:** the per-case benchmark below is offered. Record the rank of the primary gold as observed, with no threshold.
- **S5 rows:** each row's objectives and functions equal the codedb attributions for that Sentence (no inherited or fabricated pairs; see #23), and each article has an explainer paragraph (brief 1.c.iii).
- **S7:** the answered gap closes.

---

## 2. Persona A: manufacturer (Mira Okafor), case A, NailBase insulated sheathing

**Inputs used** (`evals/demo-cases/a-manufacturer-nailbase-sheathing/input/`):
- `project-brief.md`
- `product-data-sheet.md`
- `wall-section-note.md`
- `test-summary-EXAMPLE.md`
- `engineer-letter-draft-EXAMPLE.md`

**Baseline:** session 5 on #16 @579cd2c did not finish (27 blocking at about 9.5 min).

| Step | Expected outcome (pass) | Fail if | Depends on |
|---|---|---|---|
| S1 | The manufacturer role is offered, and the case starts empty | the previous case loads | [#16](https://github.com/simplythatguy/batatis/pull/16), [#31](https://github.com/simplythatguy/batatis/pull/31) |
| S2 | The brief is pasted. The facts in table A1 are **proposed** (not confirmed) with their source. The question sentences ("housewrap? (*maybe not needed*)") are not turned into facts. **Upload (required):** the other `input/` files are attached, listed, and their facts proposed with the file as source; N/A (environment) if upload isn't deployed. | the whole paste lands in "Proposed alternative"; a fact appears that isn't in `input/` | fact extraction: **BAT-65 PR (TBD, not found)**; description facts [#23](https://github.com/simplythatguy/batatis/pull/23); uploads [#24](https://github.com/simplythatguy/batatis/pull/24) and [#21](https://github.com/simplythatguy/batatis/pull/21) |
| S3 | Sections A and B match table A1. The app asks whether this is a one-site or jurisdiction-wide variance (`not_site_specific`), because the brief asks for "approval to sell it across Alberta" and also names a pilot house. Scope proposed as Part 9 (Div A 1.3.3.3.(1), PDF p.40). | the app picks one of the two silently; scope stated as a ruling | [#25](https://github.com/simplythatguy/batatis/pull/25), [#21](https://github.com/simplythatguy/batatis/pull/21) |
| S4 | Cards are offered for the gold in table A2, each waiting for a Yes. No card is accepted by the app on its own. Div B 9.29.9.3. is not offered as relevant. **Benchmark:** Div B 9.27.5.1.(1) plus Div B 9.27.5.3.(3)(b). Record the rank of the primary gold (observed, no threshold). | a card answers yes/no for the user; 9.29.9.3.(2) is suggested as relevant (session 5 regression) | [#12](https://github.com/simplythatguy/batatis/pull/12) (draft), [#33](https://github.com/simplythatguy/batatis/pull/33) (draft) |
| S5 | One row per confirmed gold Sentence. For Div B 9.23.17.3.(1), the row shows "not attributed": codedb `attribution_status` is `none`. Each row's objectives and functions equal the codedb attributions for that Sentence (no inherited or fabricated pairs, #23); each article has an explainer paragraph (brief 1.c.iii). | objectives or functions are copied from a sibling Sentence; an inherited or fabricated objective/function pair; no explainer | [#30](https://github.com/simplythatguy/batatis/pull/30), [#25](https://github.com/simplythatguy/batatis/pull/25) |
| S6 | The question "Do we need an engineer to stamp anything?" is routed to a person (table A3), never answered yes or no. The unsigned engineer letter does **not** confirm a professional. | `needs_professional` closes on the draft letter; the screen shows "depends. depends." | [#26](https://github.com/simplythatguy/batatis/pull/26), [#16](https://github.com/simplythatguy/batatis/pull/16) |
| S7 | Narrative answers save on input (not only on blur), and the answered gap closes | the first answer is lost (BAT-55 S2) | [#16](https://github.com/simplythatguy/batatis/pull/16) |
| S8 | Every gap in table A4 "must stay open" is still open. Every "answerable" gap is closed. | P2 or P3 is broken | [#11](https://github.com/simplythatguy/batatis/pull/11) (draft), [#23](https://github.com/simplythatguy/batatis/pull/23), [#30](https://github.com/simplythatguy/batatis/pull/30) |
| S9 | The PDF opens. **`Permit` is blank**: the brief says `*Not applied yet*`. The other fields follow table A1. The officer and signature fields are blank. | `Permit` contains anything; the export is blocked with no reason given | [#25](https://github.com/simplythatguy/batatis/pull/25), [#24](https://github.com/simplythatguy/batatis/pull/24) (form configured), [#31](https://github.com/simplythatguy/batatis/pull/31) |
| S10 | Officer opens the same case id. Every Not sure from S1–S9 is an officer item marked 'SCO decides'. The deficiency list equals A4 must-stay-open. Attachments read 'evidence listed (not reviewed)'. An information request can be drafted. Time-to-first-request recorded (observed, no threshold). | a different or empty case opens; a Not sure is missing; the deficiency list differs from A4 | [#16](https://github.com/simplythatguy/batatis/pull/16), [#31](https://github.com/simplythatguy/batatis/pull/31), [#23](https://github.com/simplythatguy/batatis/pull/23) |

**A1. Expected facts.** Field-map keys; values come from `input/` only.

| Fact | Expected | Status |
|---|---|---|
| owner_name | Birchfield Example Homes ("Builder-owned spec home until sale") | proposed, must be confirmed. **Fail** if Example Panel Works is filled in as Owner without confirmation. |
| owner_rep_name | Blank until the applicant's role is confirmed. Mira is the manufacturer's Technical Director (#25: filled only after `applicant_role=owner_representative`). | open gap |
| mailing_address | Not in input | open gap |
| request_date | Date of the run | auto |
| permit_number → `Permit` | **Blank** (brief: "*Not applied yet*") | n/a |
| municipal_address | 0000 Example Way NW, Edmonton, AB | proposed; depends on the one-site / jurisdiction-wide answer |
| lot / block / plan | Blank (brief: "*Don't have it*") | open gap |
| Building | 2 storeys, about 190 m², single-family, unsprinklered, HRV planned (per #23, this sentence yields "storeys 2, area 190, and occupancy `single_family`") | proposed |
| Product | 50 mm foam core plus 6 mm fibre-cement facer; no wood; shiplap edges with EPW tape; replaces 11 mm OSB; vinyl siding nailed into the facer, no furring; housewrap TBD; bracing "by sheathing"; limiting distance not shown; "CCMC pending" | proposed, applicant-stated claims |

**A2. Gold citations.** All codedb-checked against the 2nd printing. They come from `identify-regression.json` idr-001/002/003; 9.23.17.3.(1) was confirmed by Unc.

| Provision | PDF page | Quote (≤25 words) |
|---|---|---|
| Div B 9.23.17.3.(1) | p.990 | "Gypsum sheathing, rigid insulation and fibreboard shall not be used for the attachment of cladding materials." — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499 |
| Div B 9.27.5.1.(1) | p.1017 | "cladding shall be fastened to the framing members or furring members, or to blocking between the framing members." — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499 |
| Div B 9.27.5.1.(2) | p.1018 | "vertically applied vinyl siding … attached to sheathing only where the sheathing consists of not less than … 11 mm OSB." — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499 |
| Div B 9.27.5.3.(3)(b) | p.1018 | "spaced not more than 600 mm o.c." (furring, the benchmark alternative the applicant skipped) — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499 |

**Must not be offered as relevant:** Div B 9.29.9.3. (the session 5 failure: OSB/particleboard nails used as an interior finish).

**A3. Routes** (the app routes; a person decides).
- **(a) "Approved for all of Alberta".** Two routes, and the app must present them as routes, not as an approval:
  - product evaluation by CCMC or a Provincial Building Administrator (PBA)-approved evaluator (`identify-regression.json` product_approval_vs_variance, claims 1–2)
  - a province-wide variance request to the PBA, Div C 2.2.1.2.(1), PDF p.729: "A written request for a variance may be submitted to the Provincial Building Administrator." — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499 (HR-31)
- **(b) Pilot house on a variance.** A site-specific variance is the SCO's decision: SCA s.38(1) and HR-30 (mandatory routing).
- **(c) "Engineer stamp?"**
  - Route this through Section D: HR-21 (practice of engineering) and HR-03 if anything is designed under Part 4.
  - HR-05: Div B 9.23.3.5.(4), PDF p.967: "Fastening of sheathing shall conform to Part 4, a) where the 1-in-50 hourly wind pressure is equal to or greater than 1.2 kPa" — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499. The app may state the threshold and the location values as facts and must leave the conclusion to the officer.
  - Edmonton 1-in-50 hourly wind pressure 0.45 kPa and Sa(0.2) 0.103: from no-ground-truth-cases.json, not codedb-checkable.
- **(d) Bracing "by sheathing".** This is an open question; the app must not state the bracing design.

**A4. Gaps.**
- **Must stay open:**
  - evaluation report (only "Enquiry email only" exists)
  - engineer letter unsigned, so no confirmed professional
  - sheathing membrane / housewrap "TBD"
  - bracing design
  - air-leakage test ("Not tested")
  - flame-spread / foam-protection argument ("No report referenced")
  - mailing address
  - legal description
  - one-site vs jurisdiction-wide (until it is answered)
- **Answerable from input (must close once answered):** storeys, building area, occupancy, sprinklered = no, product description, the facer/no-furring attachment method.

---

## 3. Persona B: general contractor (Carlos Mendes), case B, firestop nonconformance

**Inputs used** (`evals/demo-cases/b-contractor-firestop-nonconformance/input/`):
- `project-brief.md`
- `ncr-firestop-EXAMPLE.md`
- `manufacturer-ej-draft-EXAMPLE.md`
- `architect-email-EXAMPLE.md`
- `penetration-schedule.md`

**Baselines:**
- **#16 @579cd2c:** did not finish in 15 min (1 blocking gap, no PDF).
- **BAT-55 @27bec3e:**
  - Draft 8-page PDF at about 6 min.
  - The permit number was blank on the form "even though BP-0000-00000 was entered".
  - The professional blocker couldn't be cleared honestly.

| Step | Expected outcome (pass) | Fail if | Depends on |
|---|---|---|---|
| S1 | The GC role is offered; empty case | state leak | [#16](https://github.com/simplythatguy/batatis/pull/16) |
| S2 | The facts in table B1 are proposed with their source (cfx-001..005 in `carlos-s1-backing.json`) **Upload (required):** the other `input/` files are attached, listed, and their facts proposed with the file as source; N/A (environment) if upload isn't deployed. | the paste lands in "Proposed alternative"; owner, address, legal or permit is "not found" (sessions 3 and BAT-55) | **BAT-65 PR (TBD)**, [#23](https://github.com/simplythatguy/batatis/pull/23), [#24](https://github.com/simplythatguy/batatis/pull/24)/[#21](https://github.com/simplythatguy/batatis/pull/21) for attachments |
| S3 | Jurisdiction proposed as Calgary from the address and confirmed by the user. Decided: export the SCC form, show a notice, don't block. Required notice (app copy as specified by Karen, not a source quote): *Calgary's guide (2023) asks for its own Request for Specific Variance form, filed with your Calgary SCO. This PDF is the Council's form with the same facts; confirm with the SCO which form to file.* Scope proposed as Part 3 (Div A 1.3.3.2.(1)(c), PDF p.39). | Calgary is set without confirmation; the notice is missing; the app claims Calgary accepts the SCC form; export blocked for Calgary; scope stated as a ruling | [#21](https://github.com/simplythatguy/batatis/pull/21) |
| S4 | Cards for the table B2 gold. The sprinkler "exempt" claim is linked to Div B 3.1.9.1.(4) as a **needs-evidence question** (cfx-005). The card quotes the firestop sentence, not just the first sentence. **Benchmark:** Div B 3.1.9.1.(1)(a), with a CAN/ULC-S115 listed firestop. Record the rank of the primary gold (observed, no threshold). | 3.1.9.1 is missing; the cards are blank or "(See Note A-3.1.9.)" (BAT-55 S2) | [#12](https://github.com/simplythatguy/batatis/pull/12), [#33](https://github.com/simplythatguy/batatis/pull/33) |
| S5 | One row per confirmed Sentence. Div B 3.1.9.4.(4) is not copied from sibling (3) (#30). Each row's objectives and functions equal the codedb attributions for that Sentence (no inherited or fabricated pairs, #23); each article has an explainer paragraph (brief 1.c.iii). | "No row in table" with no state shown; an inherited or fabricated objective/function pair; no explainer | [#30](https://github.com/simplythatguy/batatis/pull/30) |
| S6 | Mandatory triggers routed (table B3). The sales-rep email is listed as evidence, not reviewed (cfx-004). A GC can answer "not engaged / ask the coordinating registered professional (CRP)" without inventing a number. | the rep email is treated as an engineering judgement (EJ); the professional gap closes on a document; the only way forward is a fake registration number | [#26](https://github.com/simplythatguy/batatis/pull/26), [#23](https://github.com/simplythatguy/batatis/pull/23); "Not sure" for professional fields: **TBD** (no PR found) |
| S7 | The answer to "variance or fix?" is the verbatim two-route text in `carlos-s1-backing.json` `app_answer` ("Two routes; the officer decides. …") The answered gap closes. | promises a variance; says "rip it out" or "keep it" as a ruling | [#16](https://github.com/simplythatguy/batatis/pull/16); content in carlos-s1-backing |
| S8 | Table B4 gaps are correct | P2/P3 broken | [#11](https://github.com/simplythatguy/batatis/pull/11), [#23](https://github.com/simplythatguy/batatis/pull/23), [#30](https://github.com/simplythatguy/batatis/pull/30) |
| S9 | The PDF opens. **`Permit` = `BP-0000-00000`.** `Municipal Address` = 0000 Example Avenue SW, Calgary, AB. `Lot`/`Block`/`Plan` = 0 / 0 / 0000000. `Owner` = Example Commons Holdings Inc. Section D lists the supporting documents. Section D names the technical issues: F rating at the actual annular spaces; PVC/PEX against the metal-only listing EX-FS-1234; escutcheon evidence. | `Permit` is blank (the BAT-55 data-loss bug); Section D is blank with "No supporting documents listed"; Section D omits any of these three issues | [#25](https://github.com/simplythatguy/batatis/pull/25), [#24](https://github.com/simplythatguy/batatis/pull/24); permit-bug fix PR: **TBD** |
| S10 | Officer opens the same case id. Every Not sure from S1–S9 is an officer item marked 'SCO decides'. The deficiency list equals B4 must-stay-open. Attachments read 'evidence listed (not reviewed)'. An information request can be drafted. Time-to-first-request recorded (observed, no threshold). | a different or empty case opens; a Not sure is missing; the deficiency list differs from B4 | [#16](https://github.com/simplythatguy/batatis/pull/16), [#31](https://github.com/simplythatguy/batatis/pull/31), [#23](https://github.com/simplythatguy/batatis/pull/23) |

**B1. Expected facts** (from cfx-001..005, built from `input/`):
- **Project:** project_name Example Commons; address 0000 Example Avenue SW, Calgary, AB; legal Lot 0, Block 0, Plan 0000000; owner Example Commons Holdings Inc.
- **Permit:** building_permit `BP-0000-00000`, status issued.
- **Building:**
  - 5 storeys; sprinklered (applicant-stated); retail at grade with 64 dwelling units above
  - floor rating "1 h" (stated from the architect's code analysis)
  - CRP Example Architecture Inc. (applicant-stated)
- **Firestop facts:** L3/L4; sealant Example FireSeal 200; listing EX-FS-1234 ("metal pipes only", per the third-party inspector); penetrants PVC drain pipe and PEX bundles; some holes bigger than the listing allows; L2 copper passed.
- **Sprinkler and schedule:** the sprinkler branch lines were sealed with the same sealant, and the sub's claim "exempt" is unverified; close-in date 2026-10-24.
- **owner_rep_name:** blank until the GC's role is confirmed (#25).
- **mailing_address:** not in input → open gap.

**B2. Gold citations** (codedb, 2nd printing):

| Provision | PDF page | Quote (≤25 words) |
|---|---|---|
| Div B 3.1.9.1.(1) | p.159 | "sealed by a firestop that … CAN/ULC-S115 … has an F rating not less than the required fire-resistance rating of the fire separation" — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499 |
| Div B 3.1.9.4.(2) | p.160 | "Combustible water distribution piping is permitted to penetrate a fire separation" (PEX) — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499 |
| Div B 3.1.9.4.(4) | p.160 | "Combustible drain, waste and vent piping is permitted to penetrate a fire separation" (PVC DWV) — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499 |
| Div B 3.1.9.1.(4) | p.159 | "Sprinklers are permitted to penetrate … without having to meet the firestop requirements … provided … covered by a metal escutcheon plate" — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499 |
| Div A 1.2.1.1.(1) | p.38 | the acceptable-solution route (a) vs the alternative-solution route (b) |
| Div C 2.3.1.1.(1) | p.739 | alternative-solution documentation |
| SCA s.38(1) | page 31 of the Act PDF | the SCO may issue a written variance |

**B3. Mandatory human-review triggers** (`human-review-triggers.json`):
- **HR-01** (outside every Div C 2.4.1.1.(1) exception: 5 storeys, 64 units)
- **HR-11** (sprinkler system in a 2.4.1.1.(3) building)
- **HR-04** (not Part 9 scope; strongly-indicated)
- **HR-30** (any variance → SCO)
- **HR-17** (alternative-solution documentation names the responsible person)

The app routes each of these to a person and states none of them as satisfied.

**B4. Gaps.**
- **Must stay open:**
  - a tested/listed firestop system for PVC and PEX at the actual annular spaces
  - EJ from a qualified issuer: the rep email lacks a signature/authorization, the tested system referenced, job name/location and issuer qualifications (cfx-004)
  - escutcheon evidence for the sprinkler "exempt" claim
  - confirmed professional (CRP named, no seal or registration number given)
  - mailing address
- **Answerable from input:** owner, address, legal description, permit number, storeys, sprinklered (as applicant-stated), uses.

---

## 4. Persona C: homebuilder (Priya Natarajan), case C, infill house (`c-homebuilder-infill-house`)

**Inputs used** (`evals/demo-cases/c-homebuilder-infill-house/input/`):
- `project-brief.md`
- `drawing-notes.md`
- `window-supplier-note-EXAMPLE.md`

**Gold status:** CONFIRMED by Karen: codedb-verified by Karen, model-checked. Proposed by Data Nerd from `input/` and codedb (not from `keys/`).

| Step | Expected outcome (pass) | Fail if | Depends on |
|---|---|---|---|
| S1 | Homebuilder role; empty case | state leak | [#16](https://github.com/simplythatguy/batatis/pull/16) |
| S2 | The facts in table C1 are proposed with their source **Upload (required):** the other `input/` files are attached, listed, and their facts proposed with the file as source; N/A (environment) if upload isn't deployed. | the paste lands in "Proposed alternative"; the computed area is not shown as derived | **BAT-65 PR (TBD)**, [#23](https://github.com/simplythatguy/batatis/pull/23) |
| S3 | Edmonton proposed from the address and confirmed; `Permit` left empty Scope proposed as Part 9 (Div A 1.3.3.3.(1), PDF p.40). | the permit is filled with any value; scope stated as a ruling | [#21](https://github.com/simplythatguy/batatis/pull/21) |
| S4 | Cards for the table C2 gold. For W-07, the app shows the comparison of the fact with the figure: 0.312 m² (400 mm × 780 mm, from the supplier) against 0.35 m². PR #12 reports this comparison as `below` on Div B 9.9.10.1.(2), citing `fact_w07_area`. **Benchmark:** Div B 9.9.10.1.(2). Record the rank of the primary gold (observed, no threshold). | the app says the window "fails" or "complies"; the comparison is missing | [#12](https://github.com/simplythatguy/batatis/pull/12) |
| S5 | Section C rows for the confirmed Sentences Each row's objectives and functions equal the codedb attributions for that Sentence (no inherited or fabricated pairs, #23); each article has an explainer paragraph (brief 1.c.iii). | rows copied across Sentences; an inherited or fabricated objective/function pair; no explainer | [#30](https://github.com/simplythatguy/batatis/pull/30) |
| S6 | Section D: no mandatory professional trigger fires on the stated facts (single-family, 2 storeys, Part 9; Edmonton HWP 1/50 0.45 kPa, Sa(0.2) 0.103). The screen still says the officer decides, and the truss/spray-foam suppliers are "to be confirmed". | "no engineer needed" stated as a ruling | [#26](https://github.com/simplythatguy/batatis/pull/26), [#16](https://github.com/simplythatguy/batatis/pull/16) |
| S7 | Narrative saved; the "What needs a variance" answer is routed per table C3 The answered gap closes. | "no variance needed" for the slab or the roof | [#16](https://github.com/simplythatguy/batatis/pull/16) |
| S8 | Table C4 gaps are correct | P2/P3 broken | [#11](https://github.com/simplythatguy/batatis/pull/11), [#23](https://github.com/simplythatguy/batatis/pull/23), [#30](https://github.com/simplythatguy/batatis/pull/30) |
| S9 | The PDF opens. **`Permit` is blank** (brief: "Not yet applied for"). `Owner` = J. & R. Example. `Municipal Address` = 0000 Example Crescent NW, Edmonton, AB. `Lot`/`Block`/`Plan` = 0 / 0 / 0000000. | `Permit` is non-blank; blocked with no reason | [#25](https://github.com/simplythatguy/batatis/pull/25), [#24](https://github.com/simplythatguy/batatis/pull/24) |
| S10 | Officer opens the same case id. Every Not sure from S1–S9 is an officer item marked 'SCO decides'. The deficiency list equals C4 must-stay-open. Attachments read 'evidence listed (not reviewed)'. An information request can be drafted. Time-to-first-request recorded (observed, no threshold). | a different or empty case opens; a Not sure is missing; the deficiency list differs from C4 | [#16](https://github.com/simplythatguy/batatis/pull/16), [#31](https://github.com/simplythatguy/batatis/pull/31), [#23](https://github.com/simplythatguy/batatis/pull/23) |

**C1. Expected facts:**
- **Owner and site:** owner J. & R. Example; applicant Larkspur Example Homes (Priya Natarajan); address 0000 Example Crescent NW, Edmonton, AB; legal Lot 0, Block 0, Plan 0000000; permit not yet applied for.
- **Building:** detached single-family, 2 storeys, about 210 m², no suite, no sprinklers; in-house drafting with no architect or engineer of record.
- **Slab:** 100 mm slab on 50 mm XPS "R-7.5 (RSI 1.32) per STANDATA"; PEX hydronic loops; edge insulation *not shown*.
- **Roof:** low slope at 2%; closed-cell spray foam, thickness "TBD"; "Unvented per STANDATA 23-BCV-017"; the RDH report is not referenced or attached.
- **Window W-07:** Bedroom 3 casement; clear opening 400×780 (supplier); sill 450 mm; it is the only window in that bedroom.
- **Smoke alarms:** locations not yet shown.
- **owner_rep_name / mailing_address:** open.

**C2. Gold citations (confirmed by Karen).** Code text is from codedb (2nd printing). The STANDATA quotes below are from the published Alberta STANDATA. Those PDFs are not in this repo.

| Provision | PDF page | Quote (≤25 words) |
|---|---|---|
| Div B 9.9.10.1.(2) | p.873 | "provide an unobstructed opening of not less than 0.35 m² in area with no dimension less than 380 mm" — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499 |
| Div B 9.9.10.1.(1) | p.873 | "each bedroom or combination bedroom shall have at least one outside window or exterior door openable from the inside" — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499 |
| Div B 9.36.2.8.(5) | p.1077 | "floors-on-ground with embedded heating ducts, cables or pipes shall be insulated … under their full bottom surface including the edges." — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499 |
| STANDATA 23-BCV-003 | page 3 of the STANDATA PDF | "A minimum RSI 1.32 (R 7.5) under slab insulation complies when installed for a heated floor in contact with the ground." |
| Div B 9.19.1.1.(1) | p.939 | "vents shall be installed to permit the transfer of moisture from the space to the exterior." — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499 |
| STANDATA 23-BCV-017 | page 2 of the STANDATA PDF | "design requirements from the following documents which are to be provided with the permit application" (RDH report 32139.000) |
| Div B 9.10.19.1.(1) | p.909 | "smoke alarms conforming to CAN/ULC-S531, “Standard for Smoke Alarms,” shall be installed in a) each dwelling unit" — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499 |
| Div B 9.10.19.3.(1) | p.909 | "Within dwelling units, sufficient smoke alarms shall be installed so that a) there is at least one smoke alarm installed on each storey" (smoke-alarm locations gap) — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499 |

The 23-BCV-003 quote is the STANDATA's own wording. The app may quote it with attribution and must not restate it as its own verdict (section 5).

**C3. Routes:**
- **W-07:** redesign (a larger opening) or a site-specific variance; the SCO decides (HR-30).
- **Slab:** the province-wide STANDATA 23-BCV-003 exists. The app names it and its condition, and the officer accepts the application. Edge insulation stays an open question.
- **Roof:** STANDATA 23-BCV-017 requires the RDH design documents "to be provided with the permit application". The app asks for the report and the spray-foam thickness.

**C4. Gaps.**
- **Must stay open:**
  - RDH report not provided
  - spray-foam thickness TBD
  - slab edge insulation not shown
  - smoke alarm locations
  - W-07 opening below the figure (until redesign or an officer decision)
  - mailing address
- **Answerable from input:** owner, address, legal description, storeys, area, occupancy, sprinklered = no, window size.

---

## 5. Global fail list (any persona, any screen, the text record or the PDF)

1. **Banned verdict wording.** The app states, as its own verdict, "complies", "compliant", "not exempt", "exempt", "approved", "accepted", "no variance needed", or "variance granted". Quoting a source with attribution is allowed (for example the 23-BCV-003 text).
2. **Officer rulings.** Any yes/no ruling that belongs to the officer: whether a variance will be granted, whether a document is an engineering judgement, whether a professional is required (as a final answer), or whether the work must be removed.
3. **Invented values.** A value that isn't in `input/` and wasn't typed by the tester (owner, permit, registration number, seal, legal description).
4. **Wrongly closed gaps.** A blocking gap closed by an attachment or a claim alone: for example, `needs_professional` closed by a document or an unsigned letter (#26), or evidence counted as "sufficient" rather than "evidence listed (not reviewed)" (#23).
5. **Bad citations.**
   - a citation that does not resolve in the 2nd-printing codedb
   - a superseded edition used without a "historical context" label
   - a page that doesn't match codedb
6. **Clipped text shown as full.** Code text over 25 words shown without the clip marker. #24 clips provision text to 25 words. Backy's UI contract: "… [clipped, see NBC p.N]".
7. **Field placement.** The permit number is in any field other than `Permit`; `Permit` is blank when the case has a permit (B), or non-blank when it has none (A, C).
8. **Officer and signature fields** (`skipped.officer` / `skipped.signature`) are filled.
9. **State leak.** A previous case's data shows up (session 5), including browser autofill of earlier names (session 3, S3).
10. **Time.** Over 15 min wall clock (internal target, Unc session cap; not a rubric figure).
11. **Export.** The PDF does not open, or it is blocked with no listed reason. A 503 "PDF export is unavailable on this deployment" counts as **N/A (environment)**, not as an app fail, if it is shown plainly (#24 contract).
12. **Unapproved eval strings or phantom citations (grep the UI, text record and PDF):** `60/60`; a bare `0.818`; `17 committed errors`; `3 repeats` used as an accuracy figure; the phantom Div A ids, as grep patterns `Div A 1\.2\.1\.1\.\(3\)`, `Div A 1\.2\.1\.2\.\(1\)`, `Div A 1\.2\.1\.3\.\(1\)` (match the Div A form only; Div C 2.2.1.2.(1) is real, PDF p.729); `Table 2.4.2.1.A/B`; `verifies every reference`.
13. **Public URL (live):** any P9 item fails.

## 6. Scoring sheet (Unc fills in)

| Persona | Step | Criterion | Live: pass/fail/N/A, time, gaps | Dev: pass/fail/N/A, time, gaps | Notes / screenshot |
|---|---|---|---|---|---|
| A | S1 | empty case, role offered | | | |
| A | S2 | A1 facts proposed with source; upload listed + facts sourced to file (or N/A env) | | | |
| A | S3 | one-site vs jurisdiction-wide asked; Part 9 proposed, not ruled | | | |
| A | S4 | A2 gold offered; 9.29.9.3. not offered; benchmark offered; rank of primary gold: ___ | | | |
| A | S5 | 9.23.17.3.(1) row "not attributed"; pairs = codedb attributions; explainer per article | | | |
| A | S6 | engineer question routed; letter doesn't confirm | | | |
| A | S7 | narrative saves | | | |
| A | S8 | A4 gaps correct (P2/P3) | | | |
| A | S9 | PDF opens; `Permit` blank; fields per A1 | | | |
| A | S10 | officer: same case id; Not sure items 'SCO decides'; deficiencies = A4; 'evidence listed (not reviewed)'; request drafted; time-to-first-request (observed) | | | |
| A | all | P1 ≤15 min · P4 no overclaim · P5 citations resolve · P8 triggers · P9 public URL (live) · P10 eval strings | | | |
| B | S1 | empty case, GC role | | | |
| B | S2 | B1 facts proposed (cfx-001..005); upload listed + facts sourced to file (or N/A env) | | | |
| B | S3 | Calgary confirmed; required Calgary notice shown; no claim Calgary accepts the SCC form; export not blocked; Part 3 proposed, not ruled | | | |
| B | S4 | B2 gold; "exempt" → 3.1.9.1.(4) question; benchmark offered; rank of primary gold: ___ | | | |
| B | S5 | 3.1.9.4.(4) row not copied; pairs = codedb attributions; explainer per article | | | |
| B | S6 | HR-01/HR-11/HR-04/HR-30 routed; rep email "evidence listed (not reviewed)" | | | |
| B | S7 | two-route answer, verbatim | | | |
| B | S8 | B4 gaps correct | | | |
| B | S9 | `Permit` = BP-0000-00000; Section D lists documents; Section D names annular-space F rating, PVC/PEX vs EX-FS-1234, escutcheon evidence | | | |
| B | S10 | officer: same case id; Not sure items 'SCO decides'; deficiencies = B4; 'evidence listed (not reviewed)'; request drafted; time-to-first-request (observed) | | | |
| B | all | P1 · P4 · P5 · P8 · P9 (live) · P10 | | | |
| C | S1 | empty case, homebuilder | | | |
| C | S2 | C1 facts proposed; upload listed + facts sourced to file (or N/A env) | | | |
| C | S3 | Edmonton confirmed; `Permit` empty; Part 9 proposed, not ruled | | | |
| C | S4 | W-07 0.312 vs 0.35 m² comparison, no verdict; benchmark offered; rank of primary gold: ___ | | | |
| C | S5 | rows per Sentence; pairs = codedb attributions; explainer per article | | | |
| C | S6 | no ruling on the engineer question | | | |
| C | S7 | STANDATA routes named, no "no variance needed" | | | |
| C | S8 | C4 gaps correct | | | |
| C | S9 | PDF opens; `Permit` blank; fields per C1 | | | |
| C | S10 | officer: same case id; Not sure items 'SCO decides'; deficiencies = C4; 'evidence listed (not reviewed)'; request drafted; time-to-first-request (observed) | | | |
| C | all | P1 · P4 · P5 · P8 · P9 (live) · P10 | | | |

**Overall:** a persona passes only if every row passes (N/A rows excluded) **and** P1–P8 hold.

| Persona | Live | Dev | Tester | Date / time (MDT) | Commit |
|---|---|---|---|---|---|
| A | | | | | |
| B | | | | | |
| C | | | | | |

## 7. Dependency map

| Area | PR | State on Oct 20, about 2:45 PM MDT |
|---|---|---|
| Web flow, cold case, officer review | [#16](https://github.com/simplythatguy/batatis/pull/16) | open (head `f66a461`) |
| UI fixes on #16 (officer box, export state in the text record) | [#31](https://github.com/simplythatguy/batatis/pull/31) | open (base: #16's branch) |
| Identify cards, decision route, codedb `section_c_row` | [#12](https://github.com/simplythatguy/batatis/pull/12) | draft |
| Search ranking so case A articles surface | [#33](https://github.com/simplythatguy/batatis/pull/33) | draft |
| Completeness pipeline | [#11](https://github.com/simplythatguy/batatis/pull/11) | draft |
| Answerable gaps, description facts | [#23](https://github.com/simplythatguy/batatis/pull/23) | open |
| Gap scoping, Section C attribution states | [#30](https://github.com/simplythatguy/batatis/pull/30) | open |
| Confirmed professional before evidence | [#26](https://github.com/simplythatguy/batatis/pull/26) | open |
| Case jurisdiction, export reasons, demo seed, `inspect_upload` | [#21](https://github.com/simplythatguy/batatis/pull/21) | open |
| Export appendix, `not_site_specific`, `applicant_role` gaps, code-field label | [#25](https://github.com/simplythatguy/batatis/pull/25) | draft |
| Deploy (Vercel, Postgres, uploads with a 4 MB limit, clipping to 25 words) | [#24](https://github.com/simplythatguy/batatis/pull/24) | open ("Nothing was deployed") |
| Run-locally docs (dev environment) | [#34](https://github.com/simplythatguy/batatis/pull/34) | open |
| Section D issues list (base) | [#8](https://github.com/simplythatguy/batatis/pull/8) | merged |
| Demo cases (`input/`) | [#14](https://github.com/simplythatguy/batatis/pull/14), [#27](https://github.com/simplythatguy/batatis/pull/27) | merged |
| Fact extraction from the paste (BAT-65) | **TBD: no PR found** by search of PRs, branches and titles | n/a |

## 8. Couldn't source (marked TBD, not invented)

- **BAT-65 fact-extraction PR.** No PR, branch or title mentions it. GitHub search for "BAT-65" hits only #32, #27 and #16, none of them a fact-extraction PR. Every S2 extraction step depends on it, so they are **TBD**. #23 covers only description facts (storeys, area, occupancy).
- **Fix for the BAT-55 permit-number data loss** (permit entered, blank in the PDF): no PR identified.
- **"Not sure" / "not engaged yet" for professional fields** (BAT-55 S2): no PR identified.
- **Dev URL** for the "Dev" column: not given in any source read. It is the local run of `dev` (#34 is still open) or a deploy once #24 merges.
- **Live deployment's commit:** record it at test time (aamia's 14:53 decision puts the engine on live once deployed).
- **Whether the exported PDF is flattened**, which decides whether AcroForm values can be read: unknown.
- **SCC form file:** not in the repo (git-excluded). Only its sha256 is sourced.
- **Case C gold:** codedb-verified by Karen, model-checked (confirmed).
- **Expected numbers:** no expected blocking-gap counts or per-step times are sourced, so the criteria name specific gaps rather than counts.
