# Batatis: Implementation Plan

*Building Codes Challenge, Submission 1 (Oct 29, 2026). Sources are cited inline and were retrieved Oct 20, 2026. "Built" means it is in the current build; anything else is marked planned, in progress or a target. Results are reported only where they exist, and are labelled.*

## 1. Summary
Batatis fits into Alberta's current process and doesn't replace any of it. The applicant still submits the SCC variance form (Calgary and Edmonton call the request a "Request for Specific Variance"), the SCO still decides, and from Dec 1, 2026 the SCO still registers the variance in the Council's portal. What is designed to change:
- the application arrives complete and code-referenced;
- the officer can run a completeness review on any package;
- the officer gets a registration-ready bundle.

The officer review and the bundle are not built yet (§6).

**Path:**
- Oct 29: demo build.
- Nov 10: semi-finals, with the agent-run testing evidence.
- Nov 26: pilot build hosted in a Canadian region.
- Dec 1: **target** of a pilot agreement in principle with one accredited organization (the authority having jurisdiction, per §3).
- Dec 2 – Mar 2: pilot, if agreed, in the program's implementation window, which the program says is "not guaranteed" ([onboarding guide](https://edmontonunlimited.com/wp-content/uploads/2026/09/Built-World-Challenge-Onboarding-Guide.docx.pdf)).

**Real-user rounds begin only if a sponsor engages; none are scheduled, and we have contacted no one.** What *is* scheduled is agent-run evidence: scripted AI-agent walkthroughs before and after each fix (§7) and keyed benchmark runs (§6).

## 2. Why us / approach
**Team approach.** We are a small team that built Batatis source-first: every value traces to the form, the code database or the applicant's own documents. Reading the regulator's own data and bulletins is how we found the Oct 6 form change and the soffit-article concentration in variances ([SCC Variance Data Hub](https://www.safetycodes.ab.ca/data-hub/variance-data/)). The pattern isn't new: the City of Calgary accepted 382 zero-lot-line alternative solutions from 26 builders in the first eight months of 2017 ([Calgary advisory, Sep 6, 2017](https://www.calgary.ca/content/dam/www/pda/pd/documents/building/variances/advisory-new-standing-posted-variance-procedure.pdf)).

- **Source-traced by design.** A citation must quote the code text word for word or it is dropped. Section C attributions are lookups. Section D professional evidence is never invented. The product never states compliance.
- **We caught the Oct 6, 2026 SCC form change.** The export field map is fingerprinted to that exact file (§3).
- **Officer-side alternative-solution review** is the part of the workflow none of the code-AI products we reviewed advertises (Business Plan, §7). It is our next build focus.

## 3. How it fits current workflows
**Today:**
- **Calgary:** the applicant discusses the need with an SCO, then submits the variance form and supporting documents (digital preferred). The City reviews, may ask for more information, then accepts or rejects. The variance is tied to a building permit ([Calgary guide, approved Nov 23, 2023](https://www.calgary.ca/content/dam/www/tools-and-resources/guide-to-applying-for-an-alternative-solution.pdf)).
- **Edmonton:** the applicant submits a Request for Specific Variance with an alternative-solution report documented per Division C, Section 2.3; Edmonton's bulletin B23-05 refers to it as Division B ([Edmonton B23-05](https://www.edmonton.ca/sites/default/files/public-files/documents/coe-scpi-pol-int-0001-b23-05-application-of-9944.pdf)). More than 95% of Edmonton applications are submitted online ([City of Edmonton](https://www.edmonton.ca/business_economy/development-permitting-improvements)). Alternative solutions that affect emergency response are peer-reviewed with Fire Rescue Services ([Edmonton guideline](https://www.edmonton.ca/sites/default/files/public-files/COE-IM-GUIDE-0040-v01-20250415%20Guideline%20for%20Alternative%20Solutions%20Affecting%20Emergency%20Services.pdf)).
- **From Dec 1, 2026, everywhere in Alberta:** variances are registered only through the Council's **Orders and Variances Portal** (OVP), by the SCO. Three recent Council bulletins set the rules Batatis is designed around (all read Oct 20, 2026 from the Council's own PDFs):

**Regulatory fit: what each bulletin requires and how Batatis responds**
| Bulletin | What it requires | How Batatis responds | Status |
|---|---|---|---|
| [**IB-2025-11-18**](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2025-11-18%20Mandatory%20Documentation%20of%20Variances.pdf), Mandatory Documentation of Variances | Building, fire and plumbing variances must be documented as alternative solutions per **Division C, 2.3.1**. A copy of each variance goes to the Council within 10 days of issuance; supporting documents are retained and made available to the Administrator on request. Non-compliance can lead to suspension or cancellation of accreditation | Intake and the completeness review check that the Div C 2.3.1 documentation is present before export. Export is blocked (HTTP 409, with reasons) while blocking gaps remain, unless the user exports a labelled draft. The 10-day copy appears as a reminder, never as a gap or a verdict | Export gate and A–D gap check **built**; the 2.3.1 gate and 10-day reminder are in draft PR #11 (not merged) |
| [**IB-2026-10-01**](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf), Orders and Variances Registration Changes | From Dec 1, 2026, OVP is the **sole** registration method and the legacy submission method ends. Only SCOs register. Each variance is registered individually, for one location, at or soon after issuance, with the supporting documentation the SCO used **and the revised variance form**. Organizations should remove or redact unnecessary personal information; OVP is run under POPA | Export fills the **revised SCC form** (Oct 6, 2026), fingerprinted to that exact file. The planned registration package is the filled form, an attachment manifest and redaction flags on attachments, with a one-location-per-registration gate. Batatis never registers anything: the SCO uploads the package | Form export **built**; package and location gate in draft PR #11 (not merged) |
| [**IB-2026-10-16**](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-16_AHJ_Clarification.pdf), Clarifying Authority Having Jurisdiction | The **AHJ is the accredited organization** (or the Alberta Safety Codes Authority). SCOs exercise delegated powers on its behalf, within their designation and terms of employment, and must apply its administrative policies. The NBC(AE) Div A 1.4.1.2 definition is read as the person *through whom* the AHJ acts | Each case records the receiving **authority** (organization), and the completeness check asks for it when it is missing. Export leaves the officer's Part 2 fields (jurisdiction, agency, SCO) for the officer to complete. The officer-side review is designed to be licensed to and configured by the accredited organization (its checklist, retention and accounts), with SCOs as users acting for it. A pilot agreement would be with the organization, not an individual officer | Authority field and Part 2 skip **built**; organization-level configuration planned |

**Form version (built).** The export targets the **SCC Variance Form dated Oct 6, 2026** (5 pages, 87 fields). Its field map, `engine/export/field_maps/scc_2026-10.json`, carries the SHA-256 of that exact form file ([SCC form](https://ebs.safetycodes.ab.ca/documents/webdocs/PI/Variance%20Template%20final.pdf)). That form differs from the challenge's Appendix 1 template: the Section B checkbox wording, the privacy notice and the Part 2 decision wording all changed. A second field map for the Appendix 1 version is planned so that both can be exported.

**Integration, in three phases:**
1. **Pilot, with nothing to install (in development).** The deliverable is designed to be:
   - the **filled SCC form**;
   - a **portal registration package**: an attachment manifest and a redaction check, so that the registering SCO can upload the form and its supporting documents per location (in progress);
   - an **officer completeness report** with a **drafted information request** that the officer edits and sends.

   The officer will be able to run the review on *any* incoming package, including ones not made with Batatis. A report generated on the applicant side is advisory only.
2. **Next: a planned API.** A documented REST API with webhooks, so a municipal permitting system can push applications and pull completeness results.
3. **Later: a sanctioned OVP integration path.** The Council's bulletin says organizations with high volumes "may work with the Council to develop automated interfaces, integrations, or other approved solutions that facilitate the transfer of required information into OVP while maintaining compliance with Council reporting requirements", with details on integration options and technical requirements to follow ([IB-2026-10-01](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf); [ovp.safetycodes.ab.ca](https://ovp.safetycodes.ab.ca/)). Batatis would build that interface together with a partner authority, under the Council's requirements. After that come connectors to permitting platforms and a jurisdiction-portable schema (each case already carries a jurisdiction id and authority) for local form add-ons and other provinces.

## 4. Architecture, models, hosting and residency
- **Built today:** a FastAPI engine; a read-only SQLite code database built from official NBC(AE) 2023 sources (2nd printing, in force per [Alberta.ca](https://www.alberta.ca/building-codes-and-standards)); cases in a SQLite JSON store; a React + Vite front end, currently running on fixture data with the engine not yet connected. **Nothing is hosted yet.**
- **Models in the Oct 29 demo build (OpenAI end to end; the switch is in draft [PR #12](https://github.com/simplythatguy/batatis/pull/12), not yet merged):**
  - **code identification:** BM25 keyword search first (local, no model cost), then an OpenAI rerank, then an OpenAI verifier that keeps a citation only if it quotes the code text word for word;
  - **completeness:** rules only, unless the model-assisted judge in draft PR #11 (variant C) ships;
  - **optional, switchable paths the demo build doesn't use:** Jev screening (TypeSafe, at `api.typesafe.ai`; hosting location not published) and an Anthropic verifier. The current `dev` branch still calls these two until PR #12 merges.

  The exact model snapshot ids are pinned and reported by the keyed benchmark, and each case records the model ids it used. Cost and latency per case: **to be measured; keyed benchmark pending.**
- **Pilot:** cases move to managed Postgres, with encrypted file storage in the same region. Everything runs in one container plus a database, in a Canadian cloud region (e.g. AWS Calgary or Montreal, or Azure Canada Central). The front end is served from the same provider.
- **Residency.** Model calls don't stay in Canada by default.
  - **OpenAI:** its Canada region (`ca.api.openai.com`) offers *storage at rest* in Canada but *not processing* in Canada, and requires approval for Modified Abuse Monitoring or Zero Data Retention ([OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data)).
  - **Jev:** called at `api.typesafe.ai`; TypeSafe doesn't publish the hosting location or data residency.
  - **Anthropic:** we have not confirmed a Canadian processing option.

  For the pilot we therefore send only code text and non-personal facts to any model, or run the **keyless fallback** (BM25, rule-based completeness, deterministic Section C) fully in-region, with lower identification quality.

## 5. Data handling and privacy
- **Stored today:** document metadata only. PDF ingestion with page-linked quotes is being added for the Nov 26 build.
- **Planned per case:** applicant-entered facts, uploaded documents, extracted values (each either exact from a form field or a verified quote with a page reference), and verdict history for re-upload comparisons.
- **Personal information:** owner and applicant names, contact details, site address, and the professional's name and registration. It is designed to stay in the case record and out of prompts, be encrypted at rest, and have role-based access for applicants and officers.
- **Retention (proposed, to be agreed with each authority):** the life of the application plus a period matching the authority's records schedule, with deletion on request.
- **Model providers:**
  - By default, OpenAI doesn't train on API data and keeps abuse-monitoring logs for up to 30 days. Zero Data Retention requires OpenAI's prior approval ([OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data)). **We will request Zero Data Retention** for the provider the pilot build uses.
  - Retention terms for the optional providers (Anthropic, Jev) will be confirmed before either is used with pilot data.
- **Law** (designing for compliance, not certifying it):
  - **Private applicants:** Alberta's **PIPA**, which applies instead of PIPEDA within Alberta. **PIPEDA** still applies to cross-border transfers, such as calls to a model API outside Canada ([OPC](https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/r_o_p/prov-pipeda/), [OIPC: PIPA](https://oipc.ab.ca/legislation/pipa/)).
  - **Municipalities:** Alberta's **Protection of Privacy Act (POPA)**, in force June 11, 2025, which replaced FOIP's privacy part ([OIPC: POPA](https://oipc.ab.ca/legislation/popa/)). Its privacy-management-program duties apply from June 11, 2026. When we serve a municipality, its POPA obligations flow to us by contract, and pilot records belong to the public body.

## 6. Timeline and milestones
| When | Engineering milestone (planned unless marked) | Evidence milestone (targets) | Program |
|---|---|---|---|
| **Oct 29** | Demo build: intake; code identification over HTTP; Section C table; Section D issues list with the engineering screen (in review); completeness for Part 1 A–D with intake prompts; export of the Oct 6 form with pre-flight warnings (field map built); reproducible code-database build (built); first accuracy report on dev cases, labelled model-checked. **Dependency:** a human-verified subset needs about 2–3 hours of a person writing answer keys. If no reviewer is available, the report ships without it and says so. | AI-agent walkthrough 3 (re-run of session 2's script after fixes) | Submission 1 |
| **Nov 10** | Cost and latency per case on 20 or more dev cases. **To be measured: keyed benchmark pending** (no figure yet) | Before/after walkthrough results; benchmark results | Semi-finals |
| **Nov 26** | Pilot hosting in a Canadian region; Postgres plus encrypted storage; applicant and officer sign-in; PDF ingestion with page-linked quotes; officer review view and re-upload comparison; portal registration package; commit thresholds calibrated on the human-verified subset (if it exists) | Target: first real-user sessions, only if a partner engages | Submission 2 |
| **Dec 1** | Pilot-ready build; monitoring (ask rate, override rate, dropped-quote rate); runbook for code-database, form and bulletin updates | **Target:** pilot agreement in principle with one accredited organization | Demo Day; portal registration becomes mandatory |
| **Dec 2 – Mar 2** | Pilot support; weekly override review; threshold re-calibration | Pilot success criteria (§8) | Implementation window (not guaranteed) |

## 7. User-testing protocol: how testing changes the design
The protocol files (session script, consent form, officer-timing protocol) are in the repository under [`docs/user-testing/`](https://github.com/simplythatguy/batatis/tree/cursor/docs-user-testing-kit-3078/docs/user-testing) (currently in pull request #6, pending merge into dev).

**AI-agent simulated sessions so far.** These were scripted walkthroughs run by an AI agent playing a fictional first-time applicant (an Edmonton small builder with a hempcrete garden suite). They were not run by people, and we report their findings, not ratings.
| Session (Oct 20, 2026) | Front end | Outcome | Findings | Design change it drives | Status |
|---|---|---|---|---|---|
| 1 | Earlier front end (now frozen) | Could not start an application | Scaffold landing page; no entry point or upload; export was a placeholder | Plain-language "What are you building?" entry; one end-to-end path; label every field | Front end replaced by the current React + Vite app. **The specific fixes haven't been re-tested** |
| 2 | Current React + Vite front end, fixture data, engine not connected | Partial: never reached a finished application | Opens prefilled with someone else's example case, and "Reset case" does nothing visible; the typed description isn't read into facts; no export, and pre-flight stays disabled; upload says "Waiting for the engine" with no explanation; "Not sure" blocks Continue; code-check questions are generic, not about the project; "you may not need a variance" appears next to blocking gaps; Review and Report are unbuilt placeholders in the navigation | (1) Start from an empty case, with "Load example" as an option, and make Reset work. (2) Make "Not sure" a non-blocking answer that becomes an open question. (3) Give a reachable end state: export with a pre-flight warning list, and hide the placeholders | Open; walkthrough 3 re-runs the same script after the fixes, reported as "before → after" (e.g. "reached export: no → yes") |

What worked in session 2: provenance chips on every fact, plain-language "Why we ask" hints, a live blocking-gap count, and no compliance or approval claims.

**Protocol for each round:**
| Round (when) | Recruit criteria | Tasks | Success metric (targets, not results) | Design decision it changes |
|---|---|---|---|---|
| S (AI-agent walkthroughs; before Oct 29, repeated after each fix) | Scripted personas: production-builder coordinator, manufacturer product manager, GC project manager, SCO. None has variance experience, apart from the SCO persona | The three demo cases (§9), plus traps: "just mark it compliant", invented test data, fake citation, "zero gaps = approved?" | Each persona completes Part 1 A–D unaided; 0 compliance claims; 0 invented citations or evidence; every unverified fact is asked about, not filled | Wording and order of intake questions; when to ask instead of auto-commit; refusal copy |
| 1 (target: Nov 10 – Nov 26, only if a partner engages) | 3 first-time applicants (one each: homebuilder, manufacturer, GC) who have never filed a variance | One demo case each, think-aloud | **Target: ≥2 of 3 complete Part 1 without help in ≤X minutes** (X set from the agent walkthroughs); ≤1 question per session that the tool should have asked but didn't | Intake flow and plain-language explainers (General Applicability) |
| 1b (target: Nov 10 – Nov 26, only if a partner engages) | 1–2 building-discipline SCOs or plan examiners at a partner accredited organization | Review a planted-gap package (3 applications, known gaps) **with** the Batatis report vs. **without** it (manual checklist walkthrough) | **Target: officer completes the planted-gap review in under X minutes with Batatis against the manual baseline, and catches ≥Y of Z planted gaps** (X, Y and Z fixed before the session) | Layout of the officer view; which gaps show first; information-request wording |
| 1-retest (optional; target: within 1 week of the Round 1 fixes, before Nov 26) | The same 3 Round 1 participants, or new first-time applicants matching the same criteria | The same demo cases and script as Round 1, run after the fixes | **Target: every Round 1 failure point is passed; completion time drops against Round 1**, reported as before → after | Confirms the Round 1 fixes worked before the final design is locked for Demo Day |
| 2 (target: Dec 2 – Mar 2) | Pilot authority staff and their applicants | Live applications, run in parallel with today's process | Returns for more information vs. the authority's baseline; override rate; dropped-quote rate; "would you open it twice" | Commit thresholds per Part; jurisdiction-pack fields; go/no-go on a paid contract |

**Officer timing.** No timing data exists yet, from officers or internally. The planted-gap comparison above is a protocol. Any internal dry-run timing will be labelled as an internal estimate, not officer data.

## 8. Pilot targets
We have contacted no one, and no pilot partner, user session or officer timing exists. Everything below is a target.
| Target | When (target) | Success criteria (targets) | Gate |
|---|---|---|---|
| Agreement in principle with one accredited organization (a municipality's building group is the natural fit: Edmonton accounted for about 67% of 2023 variances, all disciplines, [SCC AR 2023](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/Annual%20Report%202023.pdf)) | By Dec 1 | A written, no-commitment pilot scope for Dec 2 – Mar 2 | A partner organization engages through the program first |
| Pilot, run in parallel with the current process | Dec 2 – Mar 2 | Fewer returns for more information than the organization's baseline; officer review time below the manual baseline (§7 protocol); ≥1 organization asks to continue | Program window (not guaranteed); hosting in a Canadian region; privacy terms agreed (§5) |
| Registration package accepted for OVP upload | During the pilot | SCOs upload Batatis packages without rework | The Council's OVP integration and technical requirements, which it says will follow (IB-2026-10-01) |

## 9. Demo cases (General Applicability)
All people, companies and products are fictional, and only code and STANDATA citations are real. Article text is confirmed against the code database build before the demo.
1. **Homebuilder:** a 2-storey Edmonton infill house.
   - The heated slab **is covered by province-wide variance STANDATA 23-BCV-003 if its conditions are met** ([STANDATA](https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/3915ba54-96dd-4c54-a9c1-63df5c917836/download/ma-standata-variance-building-23-bcv-003-2024-05.pdf)).
   - The unvented low-slope roof is **conditional on 23-BCV-017** and its referenced design report ([STANDATA](https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/2aa7678c-c476-4523-b0c3-36e71256e11b/download/ma-standata-variance-building-23-bcv-017-2025-09.pdf)).
   - Only the narrow bedroom window needs an alternative solution: Sentence 9.9.10.1.(2) sets a minimum unobstructed opening of 0.35 m² with no dimension under 380 mm (verified against our code database).

   This shows the "you may not need a variance" check. The same check applies Edmonton's B23-05 interpretation: Article 9.9.4.4 ("Openings Near Unenclosed Exterior Exit Stairs and Ramps", verified against our code database) need not apply where the stair is not more than 1.5 m above, or not more than 600 mm below, adjacent ground ([B23-05](https://www.edmonton.ca/sites/default/files/public-files/documents/coe-scpi-pol-int-0001-b23-05-application-of-9944.pdf)).
2. **Manufacturer:** a nail-base sheathing panel used in an Edmonton house, measured against Sentence 9.27.5.1.(2), which allows cladding to be fastened to sheathing only when the sheathing meets minimum thicknesses (verified against our code database; the Code does not name nail-base panels). The tool routes product acceptance to CCMC or a recognized evaluator, and the *project-specific* alternative solution to the permit application, as Calgary describes ([Calgary B23-014](https://www.calgary.ca/content/dam/www/pda/pd/documents/building/advisories/b23-014-new-products-materials-and-systems-in-building-construction.pdf)). It does not treat the variance as product approval, which Calgary rules out ([Calgary guide 2023](https://www.calgary.ca/content/dam/www/tools-and-resources/guide-to-applying-for-an-alternative-solution.pdf)).
3. **General contractor (Part 3):** a 5-storey mixed-use building in Calgary where 46 pipe penetrations were firestopped with a system outside its tested scope. Sentence 3.1.9.1.(1) requires firestops tested to CAN/ULC-S115 (verified against our code database). The tool first points to remediation with tested systems; the industry guideline says engineering judgments should not be used in place of tested systems when those are available. Where no tested system exists, it flags that **an engineering judgment is required**: issued by the firestop manufacturer's qualified technical staff, or by a registered professional engineer working with the manufacturer ([IFC engineering-judgment guidelines](https://firestop.org/wp-content/uploads/2024/03/Guidelines_Firestop_Engineering_Judgments_Rev2024-02.pdf)). That judgment is then accepted by the registered professional responsible for the Part 3 design. The tool lists the evidence the judgment must contain, without generating any engineering content.

## 10. Risks and mitigations
| Risk | Mitigation |
|---|---|
| Hallucinated citations | Every citation must quote code-database text and is dropped if the quote doesn't match (built in the verifier). Extracted values will be required to match the source bytes once PDF ingestion lands. The tool never states compliance or safety. |
| Model outage, deprecation or provider change | Model ids are pinned (built) and recorded with each case. The keyless BM25 fallback auto-commits nothing, and the UI says so. The provider switch (in progress, draft PR #12) lets us swap providers after re-running evals. |
| Wrong confident identification outside Part 9 | Auto-commit only in Part 9 with p≥0.75 and at most 3 articles, otherwise ask. **Both values are placeholders, uncalibrated, to be calibrated on the human-verified subset.** Widen to other Parts only when evals clear the error bar. |
| NBC reprints or amendments | The code database is rebuilt by script from official sources, with fingerprint checks and a 30-page spot audit, and versioned by printing. Each case records the version it used. |
| Form or registration-rule changes | Form version Oct 2026 is handled with a fingerprinted field map. The three bulletins in §3 are encoded as named gates, so a new bulletin is a rule change, not a rewrite. The portal registration package is in progress. |
| Eval validity | The 60 dev cases are model-checked. The human-verified subset is a dependency, and a held-out set is run once. |
| Code-text copyright | NRC code text is linked or quoted minimally and never redistributed. Written NRC terms are needed before commercial use. |
| Model residency | Prompts without personal data, or the in-region keyless fallback (§4). |
| Official template substitutes for us | Build Forward Alberta and SSRIA are producing a template and guide ([SCC](https://www.safetycodes.ab.ca/a-step-forward-for-alternative-solutions/)). We fill it as a form version rather than compete. |
| Officer adoption | Officers stay the decision-maker and edit every information request. Time saved is measured (§7) before we claim it. |

## 11. What we haven't validated yet
- **No real user has tested Batatis.** Two AI-agent walkthroughs ran. One failed on the earlier front end; the other reached partway on the current one, with no export.
- **The officer review, Report, export flow and portal package are not built yet.**
- **No officer timing exists.** "Saves an SCO time" is a target with a protocol.
- **No pilot partner has agreed.** We have not contacted anyone.
- **Cost and latency per case: to be measured; keyed benchmark pending.** No figure is reported until the run exists.
- **The OpenAI demo build** (BM25 → OpenAI rerank → OpenAI verifier) is in draft PR #12 and not merged; `dev` still calls Jev and Anthropic, and we hold neither key. **If PR #12 isn't merged by Oct 29, the demo runs on the keyless path:** BM25 retrieval, rule-based completeness and deterministic Section C, with no automatic code commits, and the UI says so.
- **Commit thresholds are uncalibrated,** and the human-verified eval subset depends on a person being available.
- **Residency and retention:** model processing is outside Canada; Zero Data Retention has not been requested or granted yet.
