# Offline demo seed

For the Playwright recorder (`scripts/record-demo.sh`, cloud agent `bc-6b7a9d41`) and the Code ID cards.

The recorder does not start the engine and does not need an API key. When an engine is already listening on `127.0.0.1:8000`, it can load the three fictional cases first. The seed itself makes no network call and reads no key.

```sh
export BATATIS_DEMO=1
python scripts/seed_demo.py
# or, with the engine already running under that same variable:
curl -X POST http://127.0.0.1:8000/demo/seed
```

`BATATIS_DEMO` must be the character `1`. Any other value, including an unset variable, leaves the seed off. The script exits 2 and writes nothing. `POST /demo/seed` returns 404 `{"detail":"not found"}`. Leave the variable unset in production.

The script prints the cases as JSON. A second run prints the same JSON and puts the same documents back, including after a later edit. Case ids and fact ids are fixed. `seeded_at` is the seed time (`2026-10-20T00:00:00+00:00`), not a submission time. Each case has `provenance` `example`, `example_id` equal to its id, and `version` 1. Titles start with `EXAMPLE DATA: `. `identify.ranked`, `package.story`, and the other values the seed writes itself use `source.type` `demo_seed`. Quote-checked facts from the input files use `source.type` `file`. No seeded fact uses `user_text` or `user_click`. A `demo_seed` fact does not satisfy a gap and is not professional evidence.

| Id | Input directory | City on the brief |
| --- | --- | --- |
| `demo-a-manufacturer-nailbase` | `evals/demo-cases/a-manufacturer-nailbase-sheathing/input/` | Edmonton |
| `demo-b-gc-firestop` | `evals/demo-cases/b-contractor-firestop-nonconformance/input/` | Calgary |
| `demo-c-homebuilder-infill` | `evals/demo-cases/c-homebuilder-infill-house/input/` | Edmonton |
| `demo-officer-after-fixes` | `evals/demo-cases/tester-samples/03-sco-submission-bundle.html` and `01-hartley-garden-suite-brief.html` | County of Example |

The first three are the applicant cases. The fourth is the officer package after the stated fixes. Its `package.story` is `blocking gaps drop to only what a professional must supply`. Jurisdiction and authority are the County of Example named on the bundle. Section D professional facts stay the unconfirmed label `needs professional`. The Division B benchmark is `identify.ranked` on the case: a JSON list of provision ids. The seed stores `[]`, and `apply_identify_benchmark` keeps only ids the code database resolves in Division B. It does not substitute an article, and it does not fill Section C. `keys/` is not read.

Facts for the first three cases come only from those `input/` files. `keys/`, `expected/`, and `presenter/` are not read. Each of those facts' `source.ref` is the repo path under `input/`, and its `source.quote` is a substring of that file. `confirmed` means the file states it. It does not mean the statement was verified, and it is not a professional opinion. Unsigned drafts stay labelled by the `DRAFT` or `EXAMPLE` line in the file. Manufacturer performance claims stay `unconfirmed`.

The seed does not copy PDF bytes and does not write file.{id}.name. This branch has no upload route. The recorder does not upload a brief.

## Code ID cards

The seed does not create Code ID cards. `provisions` and `section_c` are empty on every seeded case.

`project.description` is an exact passage from that case's `input/project-brief.md`. Pasting that value into "What are you building?" is what grows the cards labelled **Your words**. Those cards are questions, not ranked articles. Answer **Not sure** on them.

A ranked card appears only after **Search Division B** returns a row from `GET /code/search`. Add that row only when its id is on the page. Do not type an article id the search did not return, and do not fill one in from `keys/` or `expected/`.
