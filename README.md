# Batatis

Agent-ready environment for the Alberta **Building Codes Challenge** (Built World Tech — Venture Pilots 2026).

We are building an AI tool that helps innovators prepare **complete alternative-solution (variance) applications** and helps Safety Codes Officers review them for **administrative completeness** — not technical correctness.

## Run it locally

Python 3.12 and Node.js 22, matching [`.github/workflows/ci.yml`](./.github/workflows/ci.yml). Commands are from the repository root unless the block says `cd web`. Checked with Python 3.12.3 and Node.js v22.23.3, with `OPENAI_API_KEY` unset. The engine starts with no OpenAI key.

On Ubuntu, install the venv package when `python3 -m venv` reports that ensurepip is not available:

```bash
sudo apt install python3.12-venv
```

### Backend

```bash
python3 -m venv .venv
.venv/bin/pip install -r engine/requirements.txt
.venv/bin/uvicorn engine.api:app --port 8000
```

Leave that terminal open. Uvicorn prints `Uvicorn running on http://127.0.0.1:8000`. The route list is at http://127.0.0.1:8000/docs.

Creating a case works before any code database exists:

```bash
curl -s -D - -o /dev/null -X POST http://127.0.0.1:8000/cases \
  -H 'content-type: application/json' -d '{}'
```

That returns `HTTP/1.1 201 Created`.

### Code database

Code search, Section C lookup, and PDF export read `codedb/build/codedb.sqlite`. That file is not in git.

Download the two source PDFs from the NRC Publications Archive. They are copyrighted. Save them on your machine under these exact names, and do not commit them. `codedb build` looks only at these paths:

- NBC(AE) 2023, **2nd printing** (Volumes 1 and 2 in one PDF): [NRC record](https://nrc-publications.canada.ca/eng/view/object/?id=0316d953-0d55-4311-af69-cad55efec499). Save the 2nd-printing download as `reference/codes/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.pdf`.
- Supplement to the NBC 2020: Intent Statements (national, explanatory, not Alberta law): [NRC record](https://nrc-publications.canada.ca/eng/view/object/?id=de0e0ec9-a452-4337-bc84-002a230c9d66). Save it as `reference/codes/NBC-2020-Intent-Statements.pdf`.

Then extract page text and build. `tools/extract_text.py` reads every PDF under `reference/` and writes `reference/text/<pdf name>.jsonl`. Run it after the PDFs are in place, and before `codedb build`.

```bash
mkdir -p reference/codes
.venv/bin/pip install -r codedb/requirements.txt
.venv/bin/python tools/extract_text.py
.venv/bin/python -m codedb build
```

`mkdir -p reference/codes` is required first. With no `reference/` directory, `tools/extract_text.py` exits 1 because it cannot create `reference/text`. After `reference/codes` exists and is empty, the same command exits 0 and writes no JSONL.

`codedb build` then checks these four files, in this order. The two `.jsonl` files are the extract output; the two `.pdf` files are the downloads above.

- `reference/text/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.jsonl`
- `reference/codes/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.pdf`
- `reference/text/NBC-2020-Intent-Statements.jsonl`
- `reference/codes/NBC-2020-Intent-Statements.pdf`

On a fresh clone, with the PDFs absent, `codedb build` stops at the first missing file, exits 2, and writes nothing under `codedb/build/`:

```text
codedb: Required source missing: <repo>/reference/text/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.jsonl; existing build was not replaced
```

With the database missing, code routes return HTTP 503:

```json
{"detail":"code database not found"}
```

Checked for `GET /code/search?q=egress`, `GET /code/9.9.10.1.(1)`, `POST /section-c`, `POST /cases/{id}/export`, and `GET /cases/{id}/gaps`. `POST /cases` still returns 201.

PDF export also reads the Safety Codes Council form at `reference/guides/SCC-Variance-Form.pdf` (not in git; override with `BATATIS_SCC_FORM`). While the database is missing, export returns the 503 above. Pytest skips the export tests that need that PDF.

### Web app

In a second terminal:

```bash
cd web
npm install
npm run dev
```

Open the URL Vite prints:

```text
Local:   http://localhost:5173/
```

On this machine `http://127.0.0.1:5173/` did not connect under the default `npm run dev`; `http://localhost:5173/` returned HTTP 200. The page title is Batatis and the Describe screen loads. Vite proxies `/api` to http://127.0.0.1:8000, so `http://localhost:5173/api/code/search?q=egress` returns the same 503 body.

On http://localhost:5173/#/section-c, with the database missing, the page shows **Offline sample** and this sentence: "The engine is not reachable, so these rows are a bundled offline sample, not a lookup for this case." The label tooltip reads `Engine not reachable: Engine 503: code database not found`.

### Tests

Engine, code database, and dev evals (the CI `engine` job). Live model tests skip when their keys are unset.

```bash
.venv/bin/pip install -r engine/requirements.txt -r codedb/requirements.txt -r research/precedents/requirements.txt
.venv/bin/python -m pytest -q engine/tests codedb/tests evals_dev -rs
```

With no code database and no API keys, that printed `118 passed, 201 skipped`.

Web (the CI `web` job), from `web/`:

```bash
npm ci
npm run typecheck
npm run build
```

Both `typecheck` and `build` exited 0. The production files go to `web/dist/` (gitignored).

CI then runs `evals/ui-artifacts/smoke.mjs` (Playwright against the static pages in `evals/ui-artifacts/`). From the repository root:

```bash
SMOKE_DIR="$(mktemp -d)"
npm init -y --prefix "$SMOKE_DIR"
npm install --prefix "$SMOKE_DIR" playwright-core@1.64.1
node "$SMOKE_DIR/node_modules/playwright-core/cli.js" install chromium
chrome="$(find "${HOME}/.cache/ms-playwright" -type f -name chrome -path '*chrome-linux*' | head -n 1)"
ln -sfn "$SMOKE_DIR/node_modules" node_modules
CHROME_PATH="$chrome" node evals/ui-artifacts/smoke.mjs
rm -f node_modules
```

That printed `ui-artifacts smoke: PASS (Opus P0 checks)`.

## Clone and start agents

```bash
git clone https://github.com/simplythatguy/batatis.git
cd batatis
# Optional: refresh Matt Pocock skills
npx skills@latest add mattpocock/skills -a cursor
```

Open the repo in **Cursor**. New agent threads should:

1. Read [`AGENTS.md`](./AGENTS.md) (entrypoint).
2. Follow always-on rules under [`.cursor/rules/`](./.cursor/rules/) (includes **pstack model map** + **review = Opus 5.5**).
3. Install **pstack** plugin once: `/add-plugin pstack` — see [`docs/pstack.md`](./docs/pstack.md).
4. Load skills as tasks demand:
   - `.cursor/skills/batatis-*` — challenge domain / variance / **UI Linear system** / UI Opus pin
   - `.agents/skills/` — Matt Pocock engineering skills (triage, tdd, grill-*, etc.)
5. Use [`evals/fixtures/`](./evals/fixtures/) and [`evals/battle-prompts/`](./evals/battle-prompts/) (incl. `ui-blind/`) to verify understanding.
6. **All quality reviews** of agent outputs use Claude Opus 5.5 (max/xhigh). UI review also Opus 5.5.

Human-oriented brief: [`docs/hackathon-problem-brief.md`](./docs/hackathon-problem-brief.md).  
NBC(AE) acceptable vs alternative process: [`docs/diagrams/nbc-ae-acceptable-vs-alternative-flow.png`](./docs/diagrams/nbc-ae-acceptable-vs-alternative-flow.png).  
Product UI system: [`docs/design-system-linear.md`](./docs/design-system-linear.md).  
User-testing protocol: [`docs/user-testing/README.md`](./docs/user-testing/README.md).

## Non-negotiables (short)

- Completeness review only — never certify safety/compliance.
- No fabricated code citations; Section C attributions are lookups.
- Do not invent Section D professional evidence.
- Prefer NBC(AE) 2023 **2nd printing**.
- UI → Opus 5.5 implement **and** review; default look = Linear-caliber tokens (no prompt required).

## Status

Engineer-needed flag (model-checked): rules_only 55/60 on the dev set (in-sample), 1 under-flag; shipped rules_plus_unknown: 50/60 in-sample, 0 under-flags, 27 unknowns sent to the applicant; held-out 7/8 blind (pre-fix), post-fix 4/8 (no longer blind).

Clone-ready **agent environment** (rules, skills, evals, docs). Application product code is not the focus of this PR.
