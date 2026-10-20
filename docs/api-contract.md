# Frontend to engine contract

The product UI is the Vite app in `web/`. Screens call `web/src/api/client.ts`. In `vite dev`, `/api` is proxied to `http://127.0.0.1:8000`. A production preview has no proxy, so the build sets `VITE_ENGINE_URL` to that origin. Requests time out after 8 seconds (export after 20). A timeout is treated as the engine not answering.

`apps/web` is frozen. It is not this client.

Dates are ISO-8601 strings. The client sends JSON with `Content-Type: application/json`. Unknown response fields are ignored.

## Error body

FastAPI `detail`, a string or an object. Export uses an object:

```json
{
  "detail": {
    "message": "export blocked; resolve these or export a draft",
    "reasons": ["Section C has no provisions"]
  }
}
```

Status 0 in the client means the engine was not reached or did not answer in time. The screen shows that text, a Retry control, and the three cached examples.

## Case and fact

`POST /cases` body:

```json
{ "title": "Hempcrete garden suite", "jurisdiction": { "id": "edmonton", "name": "Edmonton", "authority": null } }
```

`jurisdiction` is null until the applicant picks Calgary or Edmonton. It is sent only on create. There is no route to change it later.

`201` returns a Case (`engine/models.py`): `id`, `title`, `created_at`, `updated_at`, `jurisdiction`, `facts`, `provisions`, `section_c`, `evidence`, `gaps`.

`POST /cases/{id}/facts` body is a Fact. `kind` is `exact`, `pointed`, `computed`, or `proposed`. `status` is `confirmed` or `unconfirmed`. A `proposed` fact must stay `unconfirmed`. Confirmation is a new fact whose `source.type` is `user_click`. `source.quote` equals `value` for process answers. `422` when a proposed fact is sent as confirmed.

The description is posted as a confirmed pointed fact:

```json
{
  "field": "project.description",
  "value": "Hempcrete walls for a garden suite.",
  "kind": "pointed",
  "status": "confirmed",
  "source": { "type": "user_text", "ref": "Your description", "quote": "Hempcrete walls for a garden suite." }
}
```

The same words are also posted on `alternative` unless the applicant typed Section B themselves. Process answers use `process.rationale`, `process.risk`, `process.mitigation`, `process.assumptions`, `process.maintenance_operation`, and `process.qualifications`. The checker also accepts the aliases in `engine/completeness.py` and `engine/process_fields.py` (`owner` for `owner_name`, `date` for `application_date`, and so on).

## Routes the UI calls

| Method and path | When |
| --- | --- |
| `POST /cases` | First save, or the first description or file, once per browser session |
| `POST /cases/{id}/facts` | Each fact the engine has not seen |
| `GET /cases/{id}/gaps` | After facts are posted. Administrative gaps only |
| `GET /code/search?q&division&limit` | Code check search. Hits are shown as returned |
| `GET /code/{id}?division` | Section C code text when the lookup is live |
| `POST /section-c` `{ "provisions": ["9.10.15.5.(8)"] }` | After the applicant confirms a departure that has an article id |
| `POST /cases/{id}/section-d` `{ "provisions": ["…"] }` | Section D recommendations |
| `GET /cases/{id}/professional` | Practice-of-engineering flag |
| `GET /cases/{id}/process-fields` | Process prompts and stored answers |
| `POST /cases/{id}/export` `{ "draft": false }` | Check completeness, once blocking gaps are closed |
| `POST /cases/{id}/files` `{ "name": "plans.pdf" }` | Upload attempt. No such route exists today |

`GET /cases/{id}/gaps` returns `completeness.Gap`: `id`, `section` (`A` `B` `C` `D` `process`), `field`, `message`, `severity`, `fix_hint`, `citation`. The message is the plain-language line the Describe page shows.

`POST /cases/{id}/section-d` returns `{ "items": […], "notices": […] }`. Each item has `provision_id`, `citation`, `status`, `performance_issue`, and `recommended_types`. Those types are recommendations, not results.

`GET /cases/{id}/professional` returns `required` and `general_required` as `yes`, `no`, or `depends`, plus `reasons`, `questions`, and `scope_note`.

`POST /cases/{id}/export` returns `application/pdf` on 200. `409` lists `reasons`. `503` means the blank SCC form file is missing. Gaps, Section C, Section D, professional, and export also fail when `BATATIS_CODEDB` is missing. The screen says so and does not invent article text.

## What is not called

Identify stays in `engine/cli_sut.py`. Code-check cards that come from the typed description are labelled as the applicant's words and carry no article id. Search hits are whatever `GET /code/search` returns.

There is no file-upload route. The POST still goes out so a down or slow engine fails in the open, with Retry and the cached examples.

Cached examples are local (`web/src/examples.ts`): NorthCore sheathing, the corridor-duct contractor case (`evals_dev` dev-003), and the infill-soffit homebuilder case (dev-001). They are opened only from "Try an example". A new visitor starts on "Who are you?" with an empty case.
