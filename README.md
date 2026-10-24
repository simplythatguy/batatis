# Batatis

A guided workspace for building-code variance applications in Alberta.

[Development](https://batatis-git-dev-abdelwaly-projects.vercel.app) · [Production](https://batatis-vert.vercel.app)

## Inspiration

A new building product or construction method can require an alternative solution to a prescriptive code requirement. Preparing that application means finding the right code references, explaining the proposal, and gathering supporting evidence. Missing information can send the application back for another round of review.

Batatis brings that work into one place for applicants and Safety Codes Officers.

## What it does

- Guides applicants through Sections A–D of the variance application.
- Helps applicants find code provisions and retrieves Section C objectives, functions, and intent through deterministic lookups.
- Keeps answers, supporting documents, and PDF drafts with the application.
- Identifies missing administrative information and questions that need professional input.
- Gives officers a review queue, notices, decisions, and a resubmission history.

Batatis checks administrative completeness. Decisions about technical correctness, equivalent performance, and safety remain with qualified professionals and the reviewing authority.

## How we built it

React, TypeScript, and Vite power the web app. Python and FastAPI handle applications, administrative checks, and PDF export. CodeDB searches pinned official publications, starting with NBC – 2023 Alberta Edition, second printing.

Local storage uses SQLite; hosted storage uses PostgreSQL. Elephant 1 through OpenRouter supplies code-relevance estimates when enabled. These estimates are uncalibrated and require review.

## Challenges

The application must submit the revision the applicant actually saved, keep uploaded evidence tied to the right application, and preserve officer decisions across resubmissions. PDF reading also needs to preserve uncertainty so an unclear reading never becomes an invented applicant answer.

## Run locally

Use Python 3.12 and Node.js 22.12 or newer.

```bash
git clone --branch dev https://github.com/simplythatguy/batatis.git
cd batatis
python3.12 -m venv .venv
.venv/bin/pip install -r engine/requirements.txt -r codedb/requirements.txt
npm ci --prefix web
BATATIS_LIVE=0 BATATIS_LIVE_ELEPHANT=0 scripts/local-app.sh start
```

Open http://localhost:3000. The engine uses port 8000. Stop both with `scripts/local-app.sh stop`.

The offline path needs no API key. Code search and PDF export need the official source files and a built CodeDB; follow the [local setup guide](docs/local-development.md).

## What's next

Test the full workflow with applicants and officers, calibrate the new relevance model, and validate results against independently reviewed applications. Batatis remains a prototype for Alberta's [Building Codes Challenge](docs/hackathon-problem-brief.md).

## Project docs

[Setup](docs/local-development.md) · [API](docs/api-contract.md) · [Verification](docs/user-testing/README.md) · [Deployment](docs/deploy.md) · [Contributing with agents](AGENTS.md)

<details>
<summary>Historical evaluation and limitations</summary>

Historical engineer-needed measurement: At measured source `d479e82`, the shipped facts-only `rules_plus_unknown` agreed with model gold on 50/60 text-only dev cases (0 no outputs, 27 unknowns) and 8/11 model-constructed cases without ground truth. Unshipped `rules_only` had 55/60 dev agreement and 1 under-flag. These were in-sample, model-checked labels, not expert validation or a measurement of the current build. Zero under-flags on the dev set was partly by design because it never answered no. See the [API contract](docs/api-contract.md) for the receipt and limitations.

</details>
