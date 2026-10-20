---
name: batatis-ui-opus
description: Batatis UI/frontend/visual work. Always use Claude Opus 5.5 at the highest available Opus 5.5 tier for implementation AND review. Default look is the Linear-caliber system in batatis-ui-linear (no prompt needed). Use for any UI, UX, component, layout, PDF preview, applicant or SCO interface work.
---

# Batatis UI — Opus 5.5 required

## Model pin (mandatory)

For **all** UI / frontend / visual / UX **implementation and UI review** in this repo:

- Model family: **Claude Opus 5.5**
- Tier: **highest available** Opus 5.5 reasoning tier in the current session (prefer max → xhigh → high)
- Example slugs when available: `claude-opus-5-5-max`, `claude-opus-5-5-xhigh`, `claude-opus-5-5-high`
- Do **not** route UI work or UI review to non-Opus models for cost/speed unless the user explicitly overrides
- If Opus account usage is blocked, keep iterating with provisional (Composer) checks + `smoke.mjs` — **do not** claim a formal UI seal until Opus 5.5 can re-run

When spawning subagents for UI implement or UI review, set `model` to the Opus 5.5 slug above when available.

## Default look (mandatory)

Load and follow `../batatis-ui-linear/SKILL.md` + `docs/design/tokens.css` + `docs/design-system-linear.md`. Produce that system by default — the user should not need to name a reference product.

## Product UI surfaces (attribute UX rules correctly)

| Surface | Job | Surface-specific UX rules |
| --- | --- | --- |
| **Applicant** | Conversational intake, article confirmation, completeness issues, PDF preview/export | Signal confidence; **don’t silently fill** required fields; clarity for users **without** prior variance experience |
| **SCO reviewer** | Fast **administrative** review (citations, gaps, explanations) to save SCO time | Keep **retrieved code text visually distinct** from AI explanations; never present completeness as technical correctness |

### Not a surface UX rule — do not attach to Applicant or SCO

**Jurisdiction portability** is a **judging criterion / data-model** constraint (Usability & portability 10%): keep schema adaptable across **430+** Alberta jurisdictions; do **not** hard-wire one municipality’s form chrome into the core model. Portability is **not** an SCO-reviewer UX rule and must not be listed as one.

## Bug-free bar

- Every primary control does what its label says; no placeholder buttons in shipped surfaces.
- Required fields show confidence / emptiness; never silent fill.
- Retrieved code text ≠ AI explanation styling.
- Empty, error, and loading states when data can be missing.
- Alt-path process fields (risk / mitigations / assumptions) remain present — not dropped for “simplicity.”

## Design note

Application chrome uses the Linear-default system (dark charcoal tool UI). Marketing/landing pages may differ, but product surfaces (intake, ranking, Section C, SCO, export) stay on tokens.
