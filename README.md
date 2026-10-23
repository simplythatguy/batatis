# Batatis

Prepare a code-referenced variance application for Alberta.

Batatis guides applicants through the Safety Codes Variance Template and helps Safety Codes Officers find missing administrative information. It is a prototype for Alberta's [Building Codes Challenge](docs/hackathon-problem-brief.md).

> Batatis checks administrative completeness. It does not certify that a design complies, is safe, or achieves equivalent performance.

## Why we are building it

A new building product or construction method may need an alternative solution to a prescriptive code requirement. The applicant must explain the proposal, identify the relevant code provisions, and provide supporting evidence.

That information is spread across code books, forms, and technical documents. Batatis brings the application into one guided workspace so missing information is visible before the next review.

## Who it is for

- Contractors, manufacturers, and design teams preparing an alternative-solution application.
- Safety Codes Officers reviewing applications sent to their authority.

## How it works

1. **Describe the proposal.** Add the building and location details, then choose the reviewing authority.
2. **Review the code.** Search candidate provisions, read their source text, and confirm the provisions for the application. Section C objectives, functional statements, and intent come from database lookups.
3. **Build the case.** Add the rationale, risks, mitigating measures, assumptions, and supporting documents. Batatis identifies missing items and when professional input is needed. Applicants and their professionals supply the evidence.
4. **Review and export.** Check the missing-information list, view the actual draft PDF, and export the application with code references.
5. **Work through officer review.** The officer sends notices and records a decision. The applicant corrects a returned application and resubmits it.

The workspace saves application titles, pins, and archive choices. Archived applications are available in Settings. The code library can use a selected application's context or let you browse without one.

## What comes out

- A saved application organized around Sections A–D of the variance template.
- A list of missing administrative information and supporting-evidence questions.
- A PDF draft with code references for the applicant to check and complete.

Code lookup starts with **NBC – 2023 Alberta Edition, second printing**. Source references stay separate from AI explanations and professional judgments.

## Run it locally

Use Python 3.12 and Node.js 22.12 or newer. No model API key is needed for the offline path.

Clone the current prototype and start the engine:

```bash
git clone --branch work/mvp-improvement-20261022 \
  https://github.com/simplythatguy/batatis.git
cd batatis
python3.12 -m venv .venv
.venv/bin/pip install -r engine/requirements.txt -r codedb/requirements.txt
BATATIS_LIVE=0 BATATIS_STORE=file BATATIS_CASES=./.data/cases.sqlite \
  .venv/bin/uvicorn engine.api:app --port 8000
```

In a second terminal, start the web app:

```bash
cd batatis/web
npm ci
npm run dev
```

Open the URL Vite prints, usually **http://localhost:5173**. The engine's route documentation is at **http://127.0.0.1:8000/docs**.

Code search, Section C lookups, and PDF export also need the source documents and a built code database. Follow the [local setup guide](docs/local-development.md#build-code-lookup-and-pdf-export) to enable them. The guide also covers ports, configuration, and checks. Optional settings are listed in [`.env.example`](.env.example).

## How it is built

| Part | Responsibility |
| --- | --- |
| [React, TypeScript, and Vite](web/) | Guided applicant workspace and officer review. |
| [Python and FastAPI](engine/) | Application storage, administrative checks, and PDF export. |
| [CodeDB](codedb/) | Search and deterministic attribution lookups from pinned official publications. |

Local development uses SQLite for case storage. Hosted runs require PostgreSQL. AI can assist code identification and application questions when enabled; source lookup and professional approval remain separate.

## Project status

Batatis is under active development. Independent UI review and the complete hosted applicant-to-officer journey are still under verification. The [hosted prototype](https://batatis-vert.vercel.app) currently runs an earlier build; run this source locally to explore the current integration.

For more detail, see the [challenge brief](docs/hackathon-problem-brief.md), [API contract](docs/api-contract.md), [verification guide](docs/user-testing/README.md), and [deployment guide](docs/deploy.md). Contributors using coding agents can start with [AGENTS.md](AGENTS.md).
