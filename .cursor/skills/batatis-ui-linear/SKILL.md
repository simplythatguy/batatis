---
name: batatis-ui-linear
description: Batatis UI interaction safeguards for applicant, SCO, intake, ranking, Section C, export, and product chrome work. Use the calm design document for visual rules and batatis-ui-opus for model policy and independent review.
---

# Batatis UI interaction safeguards

Read [the calm design system](../../../docs/design-system-calm.md) before product UI work. It is the single design authority for tokens, primary buttons, stage navigation, the icon rail and sidebar. This skill keeps interaction and data safeguards; its historical name does not select a separate visual system.

## Scope

Simplify without losing supported capabilities. Pair with [minimalist content guidance](../batatis-ui-minimalist/SKILL.md) and [model and quality policy](../batatis-ui-opus/SKILL.md). Formal UI review uses a fresh independent Claude Opus 5.5 reviewer (user decision 2026-10-26; see `../batatis-ui-opus/SKILL.md`).

## UI P0 (must not fail)

| # | Rule |
| --- | --- |
| 1 | Use the calm primary-button tokens and keep at most one primary action per card or panel. |
| 2 | Follow the calm stage and shell navigation contract. Every icon has an accessible name, a hover or focus label, and visible keyboard focus. |
| 3 | Derive the deck, applicant Review, SCO gaps and export gate from one shared gap source. |
| 4 | Block official export and administrative-complete decisions while blocking gaps remain or checks are stale. Show the reason inline. Draft exports retain explicit missing values. |
| 5 | Show real values or an explicit missing value with its gap. Demo rows, bracket placeholders and status words such as `present` never stand in for applicant data. |
| 6 | Use styled, accessible controls from the calm system. Keep checkboxes square and outside text-input padding rules, and use `resize: none` on textareas. |
| 7 | Keep button labels on one line and let button rows wrap. Every action stays visible in narrow panes. |
| 8 | Derive fields, article status, Section C, Section D, counts, summaries and previews from the same application state. Preview text equals the stored table values. Gates name unconfirmed articles. |
| 9 | Every control works. Navigation uses links; actions visibly change state. Use styled dialogs. Disabled controls explain why. No inert controls, `href="#"` or native `alert()`. |
| 10 | Start unanswered choices empty. Inferred or defaulted values carry provenance and a way to confirm them. |
| 11 | Keep scrolling inside the shell's list, detail and preview panes. |
| 12 | A Required or Missing label corresponds to the shared gap list and clears when satisfied. Provenance such as "Not authored by this tool" remains distinct from status. Status also has a text equivalent. |

Retrieved code text stays visually distinct from AI explanations. Completeness indicators, including a composer "PASS", never imply design approval, safety or technical correctness. Section C is deterministic lookup after article identification. Section D professional evidence stays human-authored. The alternative-path rationale, risk assessment, mitigating measures, assumptions, maintenance and qualifications remain reachable.

## Implementation checklist

1. Read the calm contract and use the current `web/src/calm/` components and tokens.
2. Check that displayed values, gaps and export gates agree with the same application state, including empty, loading, error and unconfirmed states.
3. Exercise each changed control with keyboard and pointer input. Check narrow panes, labels, focus, disabled reasons and source-versus-AI styling.
4. Run `node evals/ui-artifacts/smoke.mjs` for product UI work. Capture and inspect screenshots and a working demo through the supported workflow; the capture helper is `evals/ui-artifacts/screenshots.mjs`.
5. Review the final revision independently using the current model profile and `evals/battle-prompts/ui-blind/README.md`. For skill or rule edits, audit `evals/fixtures/understanding-checklist.md`.
