# API contract

Merge note: PR #8 (`backend/section-d-issues`) is the canonical `docs/api-contract.md` when that branch lands. Keep its Section D issues section. Keep the section below beside it; do not replace it.

## Case API (backend/case-api)

Administrative completeness only. A response never certifies that a design complies or is safe. Citations are returned only when they come from the code database.

Dates are ISO-8601 strings. JSON bodies use `Content-Type: application/json`. Error bodies are FastAPI `detail`, a string unless a route below says otherwise.

### Reviewing jurisdiction

The completeness gap "missing the reviewing jurisdiction" reads one field: `case.jurisdiction`. It does not read a fact, the browser header, or a `jurisdiction_id` key.

`case.jurisdiction` is null until a request stores this object:

```json
{ "id": "edmonton", "name": "Edmonton", "authority": null }
```

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `id` | string | yes | Stable key. `calgary` or `edmonton` for those two authorities. This is the value the product header shows. |
| `name` | string | yes | Display name, such as `Edmonton`. |
| `authority` | string or null | no | Legal name of the authority having jurisdiction. Omit it or send null. |

A JSON string `"edmonton"` is rejected with 422. A body that only has `jurisdiction_id` does not set `case.jurisdiction`; the gap stays. Create and update both take the object above.

`POST /cases` stores it only when that object is in the create body. The first save often happens before the applicant picks an authority, and that create then stores null. `PUT /cases/{id}/jurisdiction` writes the same object later. Either write clears the gap. `GET /cases/{id}/gaps` is the list that shows it. The `gaps` array on the Case document is stored as sent and is not recomputed by these routes.

### Case

```json
{
  "id": "case_…",
  "title": "New house application",
  "created_at": "2026-10-20T18:00:00+00:00",
  "updated_at": "2026-10-20T18:00:00+00:00",
  "jurisdiction": { "id": "edmonton", "name": "Edmonton", "authority": null },
  "facts": [],
  "provisions": [],
  "section_c": [],
  "evidence": [],
  "gaps": []
}
```

Fact `kind` is `exact`, `pointed`, `computed`, or `proposed`. `status` is `confirmed` or `unconfirmed`. A `proposed` fact cannot be `confirmed` (422). `source.type` is `code`, `file`, `user_text`, `drawing`, or `user_click`.

`POST /cases` and `POST /cases/{id}/facts` and `PUT /cases/{id}/jurisdiction` serialize writes per case. A fact added while Section D is rebuilding is kept.

### `POST /cases`

Body, all fields optional:

```json
{ "title": "New house application", "jurisdiction": { "id": "edmonton", "name": "Edmonton", "authority": null } }
```

`201` returns the Case. `422` when `jurisdiction` is not the object above (a string is 422). Unknown keys such as `jurisdiction_id` are ignored, which leaves `jurisdiction` null.

### `GET /cases/{id}`

`200` the Case. `404` `{"detail": "case not found"}`.

### `PUT /cases/{id}/jurisdiction`

Body is the jurisdiction object, not wrapped:

```json
{ "id": "edmonton", "name": "Edmonton", "authority": null }
```

`200` the updated Case. The reviewing-jurisdiction gap is gone on the next `GET /cases/{id}/gaps`. `404` unknown case. `422` when the body is a string, is null, or omits `id` or `name`.

### `POST /cases/{id}/facts`

Body is one Fact. `200` the Case. `404` unknown case. `422` when the fact is invalid, including a proposed fact sent as confirmed.

### `POST /cases/{id}/files`

`multipart/form-data` with one field, `file`. PDF only. The check is the `%PDF-` magic bytes in the first 1024 bytes, then a page count. The file's text is not read and is not stored on the case.

| Env | Default | Meaning |
| --- | --- | --- |
| `BATATIS_FILE_MAX_BYTES` | `20971520` (20 MB) | Reject larger uploads. |
| `BATATIS_FILES` | `<repo>/.batatis-files` | Directory for the bytes. Git-ignored. Not returned to the client. |

`201`:

```json
{ "id": "file_…", "name": "plans.pdf", "pages": 1, "sha256": "<hex>", "read": true }
```

`name` is the base name of the upload. `pages` is the PDF page count. `sha256` is the hex digest of the stored bytes. `read` is always true.

The case gains one confirmed fact. Nothing else is extracted.

| Fact field | Value |
| --- | --- |
| `field` | `file.<id>.name` |
| `value` | the base name |
| `kind` | `exact` |
| `status` | `confirmed` |
| `source.type` | `file` |
| `source.ref` | the file id |
| `source.quote` | null |

The PDF bytes are stored at `{BATATIS_FILES}/{case_id}/{file_id}.pdf`. The case JSON keeps the base name and the file id. It does not keep the bytes. There is no route that returns the file. A portal package in this process can read those bytes back from that path by case id and file id. The directory is git-ignored. Uploaded files are never committed.

`404` unknown case. `413` `{"detail": "file too large"}`. `415` `{"detail": "not a PDF"}` when the magic bytes fail or the PDF cannot be opened for a page count. `422` when the `file` field is missing. Error bodies do not include a filesystem path.

### `POST /cases/{id}/export`

Body optional: `{ "draft": false }`. `200` is `application/pdf` with `Content-Disposition: attachment; filename="<id>-scc-variance.pdf"` (`-DRAFT` when `draft` is true). `404` unknown case. `409`:

```json
{ "detail": { "message": "export blocked; resolve these or export a draft", "reasons": ["…"] } }
```

`503` `{"detail": "SCC variance form not found"}` when the blank form file is missing. The path is logged on the server and is not in the body. `503` `{"detail": "code database not found"}` when the code database is missing. `500` for another export failure.

### `GET /cases/{id}/gaps`

`200` is the administrative gap list from `check_completeness`. Each item has `id`, `section` (`A`, `B`, `C`, `D`, or `process`), `field`, `message`, `severity` (`blocking` or `warning`), `fix_hint`, and `citation`. An empty list is not a finding that the design complies or is safe.

The reviewing-jurisdiction item has `field` `jurisdiction`, `section` `B`, and message `Your application appears to be missing the reviewing jurisdiction.` It is present only when `case.jurisdiction` is null.

`404` unknown case. `503` when the code database is missing.

### `POST /cases/{id}/section-d`

Body optional. Extra keys are rejected.

```json
{ "provisions": ["9.25.5.2.(1)"] }
```

`200` is `{ "items": […], "notices": […] }`. Confirmed provisions and the Section C rows looked up for them are saved on the case. The route does not author evidence. `404` unknown case, or a provision id that is not in the code database (the case is left unchanged). `400` invalid provision id. `422` extra keys. `503` when the code database is missing.

### `GET /cases/{id}/professional`

`200` is `required` and `general_required` (`yes`, `no`, or `depends`), plus `reasons`, `questions`, and `scope_note`. This screens documented duties. It does not decide competence or safety. `404` unknown case. `503` when the code database is missing.

### `GET /cases/{id}/process-fields`

`200` is the alternative-path prompts. Risk assessment, mitigating measures, and assumptions/limits are process fields, not evidence-ladder rungs. `404` unknown case. `503` when the code database is missing.

### `GET /ccmc/search?q&limit`

`q` is required, 1 to 200 characters. `limit` is 1 to 50, default 20. `200` is a registry search. `422` when the query is invalid. `503` when the registry snapshot is unavailable.

### `GET /code/search?q&division&limit`

`division` is `A`, `B`, or `C` (default `B`). `limit` is 1 to 100, default 20. `200` is a list of hits with `id`, `division`, `level`, `article_title`, `title`, `text`, and `citation`. `422` when a query parameter is invalid. `503` when the code database is missing.

### `GET /code/{provision_id}?division`

`200` is the code-database record. `400` when the id is invalid or the division is ambiguous. `404` `{"detail": "provision not found"}`. `503` when the code database is missing.

### `POST /section-c`

```json
{ "provisions": ["9.10.15.5.(8)"] }
```

`200` is the Section C rows from deterministic lookup, in input order. `400` invalid provision id. `404` when a provision is not in the code database. `503` when the code database is missing.

### Code database

`BATATIS_CODEDB` overrides the path. The default is `<repo>/codedb/build/codedb.sqlite`. When that file is absent, `Codes` raises `CodeDbMissing`. The exception message is `code database not found` and contains no path.

The handler is the one at the bottom of `create_app` in `engine/api.py`, the same handler as PR #8 (`backend/section-d-issues` at `b2f8ae26`): HTTP 503 `{"detail": "code database not found"}`. The resolved path is written to the server log only. There is no `FileNotFoundError` handler.

### CORS

Origins matching `http://localhost` or `http://127.0.0.1` with an optional port are allowed, including `http://localhost:5173`.

Responses expose `Content-Disposition`, `X-Batatis-Form-Version`, `X-Batatis-Form-Date`, `X-Batatis-Form-Id`, `X-Batatis-Jurisdiction`, and any other response header whose name starts with `X-Batatis-`.
