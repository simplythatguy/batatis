# Blind UI battle prompts

Prompts describe **product features only** for Building Codes Challenge variance-tool screens.

## Hard rules for prompt authors

Do **not** mention: Linear, dark mode, Inter, spacing tokens, charcoal, pills, status dots, or color values. The env skills/rules must supply the look.

## Agent procedure

1. Read `AGENTS.md`, `batatis-ui-linear`, `batatis-ui-opus`, domain skills as needed.
2. Implement a real surface under `evals/ui-artifacts/` (HTML or React sandbox) using `docs/design/tokens.css`.
3. Screenshot → store media `media/ui-battle/` (Project Context) and optionally copy into review notes.
4. Review against `docs/design/linear-reference/` + pass bar below. Prefer **Opus 5.5** for formal UI seal when account usage allows.

## Pass bar (UI-blind)

| # | Criterion | Fail if |
| --- | --- | --- |
| 1 | Linear-caliber structure (charcoal layers, thin borders, Inter-like sans, 8px, sidebar+main) **without** indigo filled CTAs | Purple/indigo filled primaries, marketing card grid, purple-glow AI skin |
| 2 | All prompt capabilities present | Feature dropped “for simplicity” |
| 3 | Bug-free bar | Dead buttons, silent fills, code blended into AI prose, missing empty/error |
| 4 | Domain safety | Completeness only; no “complies/safe”; alt-path process fields present |
| 5 | Opus P0 chrome + gate honesty | Neutral grey primary CTA; active nav faint fill only; **neutral focus rings** (never indigo); shared gaps incl. inferred owner; unified resolve continue; gating; no demo leakage; styled controls; nowrap |
| 6 | Interaction smoke | `node evals/ui-artifacts/smoke.mjs` PASS |

**Formal seal = Opus 5.5 when available.** Composer / cheaper reviews are provisional only — never treat them as a shipped seal. Overall: each surface **PASS/FAIL**. Round fails if any FAIL.

## Suite

| ID | File | Surface |
| --- | --- | --- |
| UI-B01 | `01-intake.md` | Applicant intake (incl. inferred-owner gap) |
| UI-B02 | `02-article-ranking.md` | Article ranking (unified resolve gate) |
| UI-B03 | `03-section-c.md` | Section C table (same resolve gate as B02) |
| UI-B04 | `04-sco-review.md` | SCO review (shared gaps) |
| UI-B05 | `05-export.md` | Export / PDF preview (inferred honesty) |
| UI-B06 | `06-evidence-plan.md` | Section D evidence plan |
| UI-B07 | `07-adversarial-gates.md` | Cross-screen gate honesty |
