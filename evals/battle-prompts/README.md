# Battle prompt suite

Prompts for proving the cloneable agent env. Run with repo context only (AGENTS.md, `.cursor/rules`, `.cursor/skills/batatis-*`, `docs/`, `GLOSSARY.md`).

Pass bar (documented in store `docs/battle-test-report.md`):

1. Automated checklist score ≥ 80% of hard constraints for that prompt.
2. **Opus 5.5** reviewer (`claude-opus-5-5-max` or `xhigh`) overall ≥ **4.0 / 5** with **no material gaps** (wrong completeness/correctness, fabricated citations encouraged, Section D as engineer, skipped risk on alt path, wrong UI model).
3. Fail → fix skills/rules → re-run until pass.

| ID | File | Category |
| --- | --- | --- |
| BT01–BT05 | `01-problem-understanding.md` | Problem understanding |
| BT06–BT10 | `02-variance-workflow.md` | Variance workflow |
| BT11–BT14 | `03-ui-constraints.md` | UI / Opus pin |
| BT15–BT18 | `04-nbc-ae-fork.md` | NBC(AE) fork |
| BT19–BT22 | `05-evidence-ladder.md` | Evidence ladder |
| BT23–BT26 | `06-section-c-d.md` | Section C vs D |
| BT27–BT30 | `07-sco-completeness.md` | SCO completeness |
| BT31–BT35 | `08-pitfalls.md` | Pitfalls / traps |
| BT36–BT47 | `09-adversarial-edges.md` | Adversarial edges (D invent, skip risk, wrong UI model, fabricated STANDATA, SCO correctness, BT12/BT20 traps) |
| UI-B01+ | `ui-blind/` | Blind product-UI prompts (no look keywords); artifacts in `evals/ui-artifacts/` |
