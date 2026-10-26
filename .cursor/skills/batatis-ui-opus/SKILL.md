---
name: batatis-ui-opus
description: Batatis UI implementation and review with the current model policy, calm design contract, and applicant/officer quality boundaries. Use for components, layout, PDF previews, and other visible surfaces.
---

# Batatis UI — model and quality policy

## Model

Use **GPT-6.1-Sol at max** for UI implementation and independent UI review (user override, 2026-10-23). Read `.cursor/rules/pstack-models.mdc` for the shared role map. In T3 set the exact supported model/options through the task tool and verify the returned selection. User instructions govern subsequent model changes.

## Default look

Read [the calm design system](../../../docs/design-system-calm.md), the single design authority for product UI, and use `web/src/calm/` for implementation. Follow `../batatis-ui-linear/SKILL.md` for P0 interaction safeguards and `../batatis-ui-minimalist/SKILL.md` for content density. Resolve visual differences in favour of the calm contract.

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
