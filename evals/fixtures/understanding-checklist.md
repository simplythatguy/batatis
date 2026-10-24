# Understanding checklist (golden)

Agents (or humans editing skills) should answer all items correctly. Expected answers:

1. **Completeness** (not technical correctness).
2. Intake → Code identification → Supplemental case-building.
3. Sections **A–C** for guided fill; **D** recommendations (not solo completion); full A–D in scope for review/export.
4. **Deterministic lookup** of objective, function, intent (after article ID).
5. Must **not** invent professional evidence / practice engineering; recommend + flag only.
6. **Over 430** Alberta jurisdictions.
7. **NBC – 2023 Alberta Edition, 2nd printing**.
8. Division C holds **administrative** requirements for documenting alternative solutions / variances (esp. §2.3).
9. **Intake** or **Code Identification** (both 20%).
10. **False** — wrong citations are worse than uncertainty.
11. **Safety Codes Officer (SCO)** / AHJ reviewer.
12. **GPT-6.1-Sol at max**, for UI implementation and independent review (user override, 2026-10-23).
13. After “complies with applicable acceptable solution(s)?”: **Yes** = evidence ladder → permit; **No** = SSRIA variance path.
14. On alternative path, must include **risk assessment, mitigating measures, assumptions/limits** (never skip).
15. Evidence ladder (low→high): manufacturer lit → STANDATA → ISO 17025 test → evaluation → eval+testing → qualification → ISO 17065 certification (plus CCMC / ICC-ES / professional opinion / engineering review on alt path). Never invent these.

## Fixture prompt (for manual or CI agent evals)

> Using only this repository’s agent docs (AGENTS.md, .cursor/rules, .cursor/skills, docs/), answer the quiz items in `evals/fixtures/quiz-prompt.md` as JSON `{"answers":[...],"notes":"..."}`.