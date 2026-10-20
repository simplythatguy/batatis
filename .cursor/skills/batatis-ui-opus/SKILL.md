---
name: batatis-ui-opus
description: Batatis UI/frontend/visual work. Always use Claude Opus 5.5 at the highest available Opus 5.5 tier. Use for any UI, UX, component, layout, PDF preview, applicant or SCO interface work.
---

# Batatis UI — Opus 5.5 required

## Model pin (mandatory)

For **all** UI / frontend / visual / UX implementation or design review in this repo:

- Model family: **Claude Opus 5.5**
- Tier: **highest available** Opus 5.5 reasoning tier in the current session (prefer max → xhigh → high)
- Example slugs when available: `claude-opus-5-5-max`, `claude-opus-5-5-xhigh`, `claude-opus-5-5-high`
- Do **not** route UI work to non-Opus models for cost/speed unless the user explicitly overrides

When spawning subagents for UI, set `model` to the Opus 5.5 slug above.

## Product UI surfaces

1. **Applicant** — conversational intake, article confirmation, completeness issues, PDF preview/export.
2. **SCO reviewer** — fast administrative review: citations, gaps, explanations; save SCO time (judging criterion).

## UX constraints from the brief

- Signal confidence; don’t silently fill required fields.
- Keep retrieved code text visually distinct from AI explanations.
- Portability: avoid hard-wiring one municipality’s chrome into the data model.
- Accessibility and clarity for users **without** prior variance experience (general applicability).

## Design note

Prefer purposeful, non-generic marketing aesthetics only if building a landing/marketing surface; for the application itself, prioritize clarity of legal/admin workflow over decoration.
