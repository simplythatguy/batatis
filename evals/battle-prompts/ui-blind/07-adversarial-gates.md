# UI-B07 — Adversarial gates (cross-screen)

Stress-test that completeness gates stay honest across the workflow. Implement against the existing artifact suite (or a thin harness that drives them).

## Required capabilities (do not omit)

- **Inferred owner:** If owner was filled from an upload and not yet confirmed, it is an administrative gap on intake, SCO, and export. Export must not print the owner as an unmarked fact until Confirm. Confirm clears the gap everywhere.
- **One continue rule:** When two articles (e.g. `9.25.2.1.` and `9.25.3.1.`) must be resolved, ranking **and** Section C share the same gate: Continue stays disabled until **each** is confirmed **or** rejected. Footer names the unresolved articles with “confirm or reject” — not “confirm at least one.”
- **Shared gap source:** Gap chips / lists / counts on intake, ranking, Section C, SCO, export, and evidence plan must agree for the same project state.
- **Override honesty:** Any “download with gaps” path still lists the open gaps (including inferred owner) before proceeding.

## Out of scope

Do not change product look tokens in this prompt — behavior only.
