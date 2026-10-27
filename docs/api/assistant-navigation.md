# Assistant navigation

`POST /assist` still requires a signed-in user and authorizes `case_id` before reading it.
The normal grounded answer, source validation, redaction, one-way officer notices and
professional-authorship limits are unchanged.

The request may include `destinations`, an array of enabled destination ids from
`engine/assist_navigation.py` (at most 64). The client offers only destinations it can
actually open in the current role, application and view. This is an allowlist of
local actions, never URLs or permission to edit an application.

For an unambiguous explicit request, such as “Open the code library”, the response is:

```json
{
  "answer": "",
  "cited": [],
  "removed_citations": [],
  "notice": "",
  "navigation": {"destination": "code-library"}
}
```

The server intersects the offered ids with its current role/case policy. It does
not call a model, spend tokens or change saved application data for this path.
Negated, quoted, hypothetical, mixed, ambiguous and unrecognized commands continue
through ordinary grounded help, with `navigation: null`. Model prose never creates
an action. Unknown ids and oversized arrays are rejected with 422.

The browser must recheck its current enabled registry, application identity and view
generation before applying the result. A newer user navigation or case switch
invalidates an older plan. It acknowledges success only after the actual route or
panel has opened, retaining unsaved input and ordinary permission/confirmation
gates. Sending a request is not proof that navigation succeeded. This contract
serves typed chat and contextual Help.

The registry includes the applicant stages, sidebar, code library/search, selected
references, download options, settings, notifications and named form
questions. Reviewer destinations include the queue, PDF-package review, current
review steps and panels. Current-file reviewer destinations also require an
authorized, reviewable case from the reviewer's authority, owned by someone else.
The server supplies human destination names as product-help context, replacing
internal screen-name guesses. Older clients that omit `destinations` receive normal
help with `navigation: null`.

The `references` destination opens the current Application stage. Historical
`#/references` and `#/section-c` links also resolve to Application; the Code
library's existing references link remains a backward alias. Historical
`#/officer` resolves to the current Review stage. These aliases do not expose
standalone legacy screens. Accuracy evidence remains offline in
`docs/accuracy/report.md` and `docs/accuracy/report.json`; there is no accuracy
destination, product UI or public authentication exemption.

`comments` opens the existing officer-comments page for the applicant's captured
current application. The browser offers it only while that native destination is
available, rejects stale plans after account, application or view changes, and
acknowledges opening only after the page renders the captured application id.
Question and help-context changes also retire pending navigation, including a
move away and back while the route stays the same.
Reading and read receipts remain the comments page's responsibility. Requests
about another named application are not inferred or retargeted.

This backend contract is not evidence that the browser has implemented every
destination or that a hosted deployment supports it.
