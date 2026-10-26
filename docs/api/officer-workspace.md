# Officer workspace and the request-and-resubmit loop

How a Safety Codes Officer reads, decides and sends a request back, and what the server guarantees about
each step. It builds on the [package review API](package-review.md). Completeness is administrative only:
nothing here judges the design, and nothing claims compliance.

Wire types: `engine/models_review.py` (`Workspace`, `FindingState`, `ReviewTally`, `AcceptGate`,
`RulebookGap`, `RequestLimits`, `RequestTarget`, `Disposition`, `InformationRequestEdit`, `DispositionEdit`,
`ReturnWithRequest`, `VarianceIssued`, `CloseOut`), `DecisionRequest.review_version` and the extra
`DecisionItem` fields in `engine/routes_review.py` and `engine/account_models.py`. The web reads them from
`web/src/api/types.gen.ts`.

## One workspace, no steps

The officer works on one screen: the application itself, with each finding shown under the field it is
about, and a side rail with the counts, the exact request text and the decision. There are no review steps,
so nothing is marked done because it was passed.

## The officer's call on a finding

Every finding except the peer-review signal has one officer state (`FindingState.state`):

| State | Meaning | Counts against acceptance when the finding is blocking |
| --- | --- | --- |
| `ask` | In the request. Its item is `included`. | Yes |
| `verify` | Not established yet (`not_found`, or routed to the officer): look first, then ask or dismiss. | Yes |
| `dismissed` | The officer's call, with a `reason` (`checked`, `not_needed`, `does_not_fit`) and, for a blocking finding, a note. Kept in the record; the applicant never sees it. | No |

Defaults when the officer has not chosen: `ask` for an applicant finding the review established, `verify`
for a `not_found` or officer-routed one. A finding never stops counting by becoming unreadable: only a
dismissal stops it. A finding whose field the shared completeness rules still require on the saved
application is `locked`: it can't be dismissed, only asked for.

Dispositions are stored on the session (`ReviewSession.dispositions`) and changed in the same write as the
request draft: `PUT …/{version}/information-request` with `findings: [{key, state, reason?, note?}]`
(changes only). The server owns `included` for finding-linked items: it is true exactly when the state is
`ask`. The PUT answers with the whole `PackageReviewIndex`, so the counts, the gate and the rendered
`information_request.text` on screen always come from the save that just happened.

## One set of counts

`Workspace.tally` is the only definition of every count. The client never recounts.

- `required`: blocking findings not dismissed, plus rulebook blocking gaps that no finding covers.
- `to_check`: warnings not dismissed. `verify`: findings still to look at. `dismissed`. `asked`: items in the
  request text. `rulebook`: the uncovered rulebook gaps (listed in `Workspace.rulebook`).

`SessionSummary.required` is the same number for older versions.

## Deciding on the version on screen

`GET /review/{case_id}/package-review` returns `workspace` for the latest version: `version`,
`case_version`, `current` (it read the saved application as it is now), the states, the tally and
`gate` (`can_accept`, `reason`). The server rechecks the same gate on every decision:

- An acceptance sends `expected_version` (the saved application on screen) and `review_version` (the
  package-review version on screen). It is refused (409, with the reason) unless the case is at
  `expected_version`, `review_version` is the latest session, that session read this case version, its
  `tally.required` is 0, and the shared completeness rules report no blocking gap. Without any package
  review the acceptance is refused unless the code database is missing on this server, in which case the
  completeness rules alone decide (as before).
- A refusal pins `expected_version` as before.

## One way to send a request back

`POST /review/{case_id}/package-review/{version}/return` with `{expected_version, text}` sends the saved
request and returns the application **in one write**: the case gets one decision message (the request text)
whose items carry their targets, the status becomes `returned`, and the request is frozen. Either all of it
happens or none of it does; the response is the saved `Case`. `text` must equal the server's rendering of the saved draft, so the applicant
receives exactly what the officer previewed (409 when it differs: the draft changed, review it again).
Before writing, the server checks the claim, the case version, that `version` is the latest session, that at
least one item is included, and every limit in `Workspace.limits` (items, intro, item text, whole text). The
legacy `…/information-request/send` route and a plain `return` decision stay for older callers; the
workspace uses only this route.

A sent request is frozen and readable as the applicant sees it (`GET /cases/{case_id}/information-request`).

## Where the applicant answers

Every item that is sent has a `RequestTarget` (`section`, optional `field`, `label`), and the decision
item carries it (`DecisionItem.section`, `field`, `label`, `request_item_id`, `finding_key`). The applicant
answers by fixing the application and sending it again; there are no replies.

Shared with the workspace thread (the applicant's document and editor). What the request needs from the
applicant side:

| Target `field` | Place to answer |
| --- | --- |
| A Section A/B detail field (`owner_name`, `representative`, `civic_address`, `mailing_address`, `legal_description`, `application_date`, `alternative_description`, …) | That field's control. |
| An alternative-path field (`rationale`, `risk_assessment`, `mitigating_measures`, `assumptions_and_limits`, `maintenance_operation`, `qualifications`, with or without `process.`) | That passage. |
| `evidence.<id>.<attribute>`, `document.*`, `section_d.*`, `professional_*` | The Section D document (or the professional card) it names. |
| `section_c.<provision>`, `citation.*` | That Section C reference. |
| `clarification.<question_id>` | The clarification answer card (as today). |
| No field, or one the applicant side does not know (`div_c.*`, `demonstrate.*`, officer items without a field) | A short answer box for that item in its `section`, saved as the fact `request_answer.<request_item_id>`. |

Requirements on the applicant side: show every item of the latest request with its `label` and a way to
reach its place; never mark an item resolved by itself (the officer confirms on the next review); and save
`request_answer.*` facts like other answers, so they appear in the officer's "changed since" view.

An application that was returned can't be sent again unchanged: `POST /cases/{case_id}/submit` answers 409
`Nothing changed since it was returned` when no stored answer, evidence listing or request answer differs
from the return.

## Close-out

Accepting as administratively complete is not issuing a variance. After an acceptance the close-out shows
"Administratively complete · technical review next" and nothing is due. When the officer issues the
variance (outside Batatis) they record the date: `POST /review/{case_id}/close-out/issued`
`{issued_on: "YYYY-MM-DD"}`. Only then is the copy to the Safety Codes Council due, 10 days after
`issued_on` (IB-2025-11-18), and "Mark as sent" becomes available. A refusal has no Council copy; its
record package lists what to keep on file.

## Sources

Findings carry every pointer they were read from, each with its full quote. A PDF uploaded to a case's
package review is kept with the case (`InputFile.file_id`), so "Open page N" opens it; it follows the case's
retention. Standalone third-party uploads are not kept.
