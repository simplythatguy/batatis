# UI-B02 — Article ranking

Build the code identification / article ranking screen.

## Required capabilities (do not omit)

- List candidate NBC(AE) articles ranked by relevance to the proposed alternative.
- For each candidate show: article id, short title, rank/score or order, and whether it is confirmed / rejected / pending.
- Highlight the recommended **benchmark acceptable solution** with a short explanation.
- Allow the user to confirm or reject articles; asking clarifying questions must be obvious when interpretation is ambiguous.
- **Continue gate:** when multiple articles must be resolved, Continue stays disabled until **each** is confirmed **or** rejected. Footer names the unresolved articles (e.g. “Resolve 9.25.2.1., 9.25.3.1. (confirm or reject) to continue”) — do not enable after confirming only one if others remain open. This rule must match Section C.
- Retrieved article identifiers must be visually clear; do not invent article numbers in the sample data beyond clearly labeled placeholder demo rows marked as demo.
- Actions: Confirm / Reject per article, Back to intake, Continue to Section C.
- Keep navigation to other workflow steps.
