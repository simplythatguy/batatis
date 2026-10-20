# Engine HTTP contract

Administrative completeness only. A response never certifies that a design complies or is safe.
Citations are returned only when they are in the code database.

## Cases

`POST /cases` creates an empty case. Facts start empty. Nothing from a fixture or another case is copied in.

`POST /cases/{id}/facts` appends one fact on that case.

`GET /cases/{id}` returns the case as stored.

## Identify

`POST /cases/{id}/identify` is the primary call. Body:

```json
{"prose": "applicant description", "answers": [{"field": "building.storeys", "answer": "not sure"}]}
```

`GET /cases/{id}/identify/stream?prose=` and `POST` with `Accept: text/event-stream` emit stage events in order: `screen`, `rerank`, `verify`, `questions`, `done`. They are stage markers, not tokens.

The same function serves `engine/cli_sut.py`. Identify does not write `provisions`. An answer of "not sure" or unknown is stored as a fact with status `unknown` and is returned in `open_questions`. Identification continues.

`open_questions` has at most about five targeted questions, plus any unknown answer that did not already appear. Each question has `field`, `text`, `why`, `status` (`open` or `unknown`), and `disambiguates` (candidate article ids). An unconfirmed value is asked back as a confirmation.

`variance_needed` is `not_indicated`, `likely`, or `unknown`. When nothing has confirmed a departure, the explanation is:

> No departure from the acceptable solution has been identified; if the design follows the cited acceptable solution, a variance may not be needed. Confirm with your Safety Codes Officer.

That sentence is not a compliance finding. `intake_action` is `redirect` for a request that belongs to the plumbing, electrical, gas, or private-sewage regime, which is where the development-case gold schema uses `redirect`. `redirect_to` names that regime.

`benchmark` is one Division B article the proposal is measured against, or `identified: false` plus a question. `commit_policy.status` is `placeholder_uncalibrated` for the 0.75 threshold and the cap of 3 until `evals_dev/human_key/calibration.json` says `calibrated`.

`POST /cases/{id}/identify/confirm` with `{"provisions": ["9.10.15.5.(8)"]}` checks each id in the code database, then writes `provisions` and Section C. An unknown id returns 404 and leaves the case unchanged.

With no provider key, the runner uses BM25, commits nothing, and sets `mode` to `bm25_fallback`. A cached demo, when one is shipped, is served for an exact description match when there is no key or no code database, with `cached: true`.

## Export

`POST /cases/{id}/export` reads the blank form from `engine/export/forms.json`, keyed by jurisdiction and form id. The default is `alberta` / `scc-variance`, version `scc_2026-10`, PDF last-modified `2026-10-06`, 5 pages, 87 fields. The file SHA-256 must match the registry and `engine/export/field_maps/scc_2026-10.json`. A mismatch is HTTP 422.

The response is the PDF. Headers `X-Batatis-Form-Version`, `X-Batatis-Form-Date`, `X-Batatis-Form-Id`, and `X-Batatis-Jurisdiction` repeat the registry entry. The same values are in the PDF info dictionary.

The October 2026 Safety Codes Council form differs in wording from the challenge brief's Appendix 1 (Section B checkbox label, privacy text, and the officer line "approximately equivalent or greater safety performance"). Appendix 1 is not the export target.

Optional body fields `jurisdiction` and `form_id` select another registry entry. `BATATIS_SCC_FORM` overrides only the default entry's path. The SHA check still applies.

## Keyed benchmark

```sh
BATATIS_LLM_PROVIDER=openai .venv/bin/python -m engine.identify.benchmark \
  --repeats 3 --cases 20 --source evals_dev \
  --fx-usd-cad 1.4097 --fx-date 2026-10-19
```

The process exits 2 when `OPENAI_API_KEY` is missing. It does not print the key. `--fx-usd-cad` (CAD per 1 USD) and `--fx-date` are required and are printed on every variant line. The rate above is Bank of Canada series FXUSDCAD for 2026-10-19; pass a different pair when you have a newer one. Each variant line includes pinned model ids, input and output tokens per case, p50 and p95 latency, USD and CAD per case, top-1, recall@5, MRR, ask rate, and committed-pick errors, then a line comparing CAD per case with the C$125 price floor. The command fetches official sources and builds the code database first.
