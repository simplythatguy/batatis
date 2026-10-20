# Blind UI battle prompts

Prompts describe **product features only** for Building Codes Challenge variance-tool screens.

## Hard rules for prompt authors

Do **not** mention: Linear, dark mode, Inter, spacing tokens, charcoal, pills, status dots, or color values. The env skills/rules must supply the look.

## Agent procedure

1. Read `AGENTS.md`, `batatis-ui-linear`, `batatis-ui-opus`, domain skills as needed.
2. Implement a real surface under `evals/ui-artifacts/` (HTML or React sandbox) using `docs/design/tokens.css`.
3. Screenshot → store media `media/ui-battle/` (Project Context) and optionally copy into review notes.
4. Review against `docs/design/linear-reference/` + pass bar below (Opus 5.5 preferred for formal UI seal).

## Pass bar (UI-blind)

| # | Criterion | Fail if |
| --- | --- | --- |
| 1 | Looks like the in-repo design system (charcoal layers, thin borders, Inter-like sans, 8px rhythm, sparse functional color, sidebar+main / list+detail) | Generic light dashboard, purple-glow AI skin, marketing card grid |
| 2 | All prompt capabilities present | Feature dropped “for simplicity” |
| 3 | Bug-free bar | Dead buttons, silent required fills, code text blended into AI prose, missing empty/error for missing data |
| 4 | Domain safety | Completeness language only; no “complies/safe”; alt-path process fields not removed |

Overall: each surface **PASS/FAIL**. Round fails if any surface FAIL. Fix skills → re-run.

## Suite

| ID | File | Surface |
| --- | --- | --- |
| UI-B01 | `01-intake.md` | Applicant intake |
| UI-B02 | `02-article-ranking.md` | Article ranking |
| UI-B03 | `03-section-c.md` | Section C table |
| UI-B04 | `04-sco-review.md` | SCO review |
| UI-B05 | `05-export.md` | Export / PDF preview |
