# UI-B04 — SCO administrative review

Build the Safety Codes Officer reviewer screen.

## Required capabilities (do not omit)

- Fast administrative review of a submitted variance draft: citations present?, Section C complete?, gaps list, explanations.
- Show citation / retrieved code text distinctly from AI-written explanations.
- List administrative deficiencies (e.g. missing risk assessment, empty mitigations, unlabeled assumptions, incomplete A/B, **unconfirmed inferred owner**).
- Gaps come from the **same shared source** as intake / export — counts and labels must agree.
- Optimize for SCO time — scan citations, gaps, and explanations quickly.
- Must **not** offer a control that certifies technical correctness or marks the design “code-compliant” / “safe.”
- Admin-complete stays disabled while blocking gaps remain; show the reason inline.
- Actions appropriate to admin review (e.g. Request applicant fixes, Mark admin-complete) without implying AHJ approval of the variance.
- Navigation consistent with the product shell.
