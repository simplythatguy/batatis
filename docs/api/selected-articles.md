# Saved code-check selections

`GET /cases/{id}` (also `/api/cases/{id}`) returns `selected_articles`, independently of
`provisions`, the confirmed Division B benchmarks. Selecting an article does not confirm
that the design departs from it, create a citation fact, or prepare Section C/D.

`selected_articles` has three useful states:

- `null`: a legacy application has never saved a code-check list. A client can reconstruct
  its existing confirmed references and description cards using its legacy fallback.
- `[]`: the applicant explicitly saved an empty list. Do not restore removed selections
  from an older confirmed-reference list.
- An ordered list: restore these selected articles and their answer state, including
  unanswered cards. Retrieve any displayed code wording and attributions separately.

## Replace the saved list

`PUT /cases/{id}/selected-articles` (also under `/api`) accepts:

```json
{
  "expected_version": 7,
  "selected_articles": [
    {
      "id": "search-9.27.3.4.",
      "provision": "9.27.3.4.",
      "answer": null,
      "pending": false
    }
  ]
}
```

Both top-level fields are required; an empty list clears the saved snapshot. The response
is the complete saved `Case`, including the new acknowledged `version`. Use that version
for the next versioned write. Serialize this write with fact, jurisdiction and reference
writes; do not treat an unacknowledged selection request as saved.

Each card needs a stable nonblank `id` (up to 200 characters) and `provision` (up to 80).
An article or descendant is canonicalized using CodeDB's identifier parser and verified
against Division B. Card ids and canonical provisions must each be unique; order is kept.
The list accepts at most 500 cards. Overlapping article and sentence selections are not
silently merged or answered by the server.

`answer` is `"yes"`, `"no"`, `"not-sure"`, or `null` (default). `pending` is a strict boolean,
default `false`: an answer still awaiting its existing confirmation request stays pending
when reopened. These fields preserve the card's state; even `"yes"` does not promote it
to `provisions`. Existing explicit benchmark/identify confirmation and withdrawal routes
remain responsible for confirmed references. No client quote, benchmark flag, Section C
attribution, evidence, or professional conclusion is accepted by this endpoint.

The route changes only `selected_articles` and the case's write timestamps/version. It
preserves title, facts, confirmed references, Section C/D, messages and account list
preferences. Persist only actual code-reference cards here; description-only questions
continue to use their existing fact/description restoration path.

## Errors and access

- `422`: missing/invalid/extra fields, ambiguous duplicates, or an invalid identifier.
- `404`: the case is missing, expired or inaccessible, or a selected Division B provision
  does not exist. A failed list is never partially stored; deleted cases are not recreated.
- `409`: `expected_version` is stale, another write wins, or the owner's case is read-only.
  Read and reconcile explicitly before retrying; never overwrite a newer application.
- `503`: the code corpus is unavailable. The saved snapshot stays intact. Clearing an empty
  list requires no corpus access.

The existing case policy applies: owners can edit drafts and returned applications;
reviewers can read authorized cases but cannot change applicant selections. Existing
anonymous legacy behavior is retained. Storage rechecks current ownership and status under
its write lock. Responses carry `Cache-Control: no-store`.

Frontend save/reopen wiring is a separate implementation step. Backend persistence tests
do not establish that application switching is fixed in the browser or deployed product.
