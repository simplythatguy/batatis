# Batatis glossary

Domain terms for the Alberta Building Codes Challenge. Prefer these spellings in tickets, specs, and agent output. See also `docs/hackathon-problem-brief.md` and `docs/agents/domain.md`.

| Term | Meaning |
| --- | --- |
| **NBC(AE)** | National Building Code – 2023 Alberta Edition (prefer 2nd printing) |
| **Acceptable solution** | Prescriptive Division B “recipe” that is deemed to satisfy the Code |
| **Alternative solution / variance** | Non-prescriptive path that must achieve ≥ performance of attributed objectives/functional statements; Alberta SCO may issue a variance |
| **SCO** | Safety Codes Officer (reviewer / AHJ side) |
| **AHJ** | Authority Having Jurisdiction |
| **Section A–D** | Part 1 of the Safety Codes Variance Template (applicant): identity, proposal, attributions, supporting docs |
| **Section C attributions** | Article ↔ objective / functional statement / intent; **deterministic lookup**, not LLM memory |
| **Section D** | Supporting documentation plan; tool recommends and flags professionals — does **not** invent professional judgment |
| **Division C §2.3** | Administrative requirements for documenting alternative solutions |
| **STANDATA** | Alberta regulator interpretations / variances / bulletins / errata (OGL-Alberta) |
| **SSRIA variance template** | Extended Request for Specific Variance form used on the alternative path |
| **Evidence ladder** | Confidence order for compliance **evidence types** (manufacturer lit → STANDATA → ISO 17025 → evaluation → eval+testing → qualification → ISO 17065). Alt-path **extra evidence types**: CCMC, ICC-ES, professional opinion, engineering review. **Not** the same as alt-path process fields (risk / mitigations / assumptions) |
| **Alt-path process requirements** | Risk assessment, mitigating measures, assumptions/limits — required workflow fields on the No/variance fork; **not** evidence-ladder rungs |
| **Jurisdiction portability** | Judging / data-model constraint (Usability & portability): adaptable schema across 430+ AHJs — **not** an SCO-surface UX rule |
| **Completeness review** | Administrative gap check — **not** a finding of technical correctness or safety |
| **CCMC** | Canadian Construction Materials Centre product assessments |
| **Batatis** | This project / product name for the challenge team’s AI variance assistant |
