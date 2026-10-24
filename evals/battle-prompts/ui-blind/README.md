# Blind UI battle prompts

Prompts describe **product features only** for Building Codes Challenge variance-tool screens.

## Hard rules for prompt authors

Do **not** mention: Linear, dark mode, Inter, spacing tokens, charcoal, pills, status dots, or color values. The env skills/rules must supply the look.

## Agent procedure

1. Read `AGENTS.md`, `batatis-ui-linear`, `batatis-ui-opus`, domain skills as needed.
2. Implement a real surface under `evals/ui-artifacts/` (HTML or React sandbox) using `docs/design/tokens.css`.
3. Screenshot → store media `media/ui-battle/` (Project Context) and optionally copy into review notes.
4. Use the current calm design contract and pass bar below; the historical Linear references supply interaction examples. Review on the model profile in `.cursor/rules/pstack-models.mdc`.

## Pass bar (UI-blind)

| # | Criterion | Fail if |
| --- | --- | --- |
| 1 | Linear-caliber structure (charcoal layers, thin borders, Inter-like sans, 8px, sidebar+main) **without** indigo filled CTAs | Purple/indigo filled primaries, marketing card grid, purple-glow AI skin |
| 2 | All prompt capabilities present | Feature dropped “for simplicity” |
| 3 | Bug-free bar | Dead buttons, silent fills, code blended into AI prose, missing empty/error |
| 4 | Domain safety | Completeness only; no “complies/safe”; alt-path process fields present |
| 5 | UI P0 chrome | Neutral grey primary CTA; active nav faint fill only; shared gaps; gating; no demo leakage; styled controls; nowrap |
| 6 | Interaction smoke | `node evals/ui-artifacts/smoke.mjs` PASS |

**Formal review uses a fresh independent reviewer** on the final revision under `.cursor/rules/pstack-models.mdc` (GPT-6.1-Sol at max). Overall: each surface **PASS/FAIL**. Round fails if any FAIL.

## Suite

| ID | File | Surface |
| --- | --- | --- |
| UI-B01 | `01-intake.md` | Applicant intake |
| UI-B02 | `02-article-ranking.md` | Article ranking |
| UI-B03 | `03-section-c.md` | Section C table |
| UI-B04 | `04-sco-review.md` | SCO review |
| UI-B05 | `05-export.md` | Export / PDF preview |
