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

The script prints the three cases as JSON. A second run prints the same JSON and puts the same documents back, including after a later edit. Case ids, fact ids, and timestamps are fixed.

| Id | Input directory | City on the brief |
| --- | --- | --- |
| `demo-a-manufacturer-nailbase` | `evals/demo-cases/a-manufacturer-nailbase-sheathing/input/` | Edmonton |
| `demo-b-gc-firestop` | `evals/demo-cases/b-contractor-firestop-nonconformance/input/` | Calgary |
| `demo-c-homebuilder-infill` | `evals/demo-cases/c-homebuilder-infill-house/input/` | Edmonton |

Facts come only from those `input/` files. `keys/`, `expected/`, and `presenter/` are not read. Each fact's `source.ref` is the repo path under `input/`, and its `source.quote` is a substring of that file. `confirmed` means the file states it. It does not mean the statement was verified, and it is not a professional opinion. Unsigned drafts stay labelled by the `DRAFT` or `EXAMPLE` line in the file. Manufacturer performance claims stay `unconfirmed`.

The seed does not copy PDF bytes and does not write `file.{id}.name`. The recorder still uploads a brief itself when this file is already on disk:

- `evals/demo-cases/a-manufacturer-nailbase-sheathing/input/project-brief.pdf`
- `evals/demo-cases/b-contractor-firestop-nonconformance/input/project-brief.pdf`
- `evals/demo-cases/c-homebuilder-infill-house/input/project-brief.pdf`

## Code ID cards

The seed does not create Code ID cards. `provisions` and `section_c` are empty on every seeded case.

`project.description` is an exact passage from that case's `input/project-brief.md`. Pasting that value into "What are you building?" is what grows the cards labelled **Your words**. Those cards are questions, not ranked articles. Answer **Not sure** on them.

A ranked card appears only after **Search Division B** returns a row from `GET /code/search`. Add that row only when its id is on the page. Do not type an article id the search did not return, and do not fill one in from `keys/` or `expected/`.
