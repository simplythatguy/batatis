# Requirement-set coverage evaluation

`evals_dev/requirement_bench` is a standard-library-only, offline evaluator for
**all known requirement references**, separately measured at retrieval,
identification, application inclusion, and applicant visibility. It does not run
the engine, import historical answer keys, tune identification, or call providers.
No expert-verified real requirement sets are supplied. The included examples and
regressions are synthetic harness evidence, never expert gold or product accuracy.

The separate `evals_dev.requirement_capture` adapter runs the actual deterministic
engine from an exported predictor-only bundle. It verifies the frozen source,
config, corpus and inline input hashes and retains observed input and raw result
artifacts. It supplies retrieval and confirmed-applicability layers separately.
It leaves application/export and applicant-visible layers `null`, since a local
engine invocation does not observe those surfaces. The scorer consequently
reports them as `not_supplied`, rather than inventing visibility or complete-flow
success.

Freeze its current configuration before sealing a real input plan:

```sh
python3 -c 'import json; from evals_dev.requirement_capture import frozen_config; print(json.dumps(frozen_config(), indent=2))' > /path/to/bundle/config.json
python3 -m evals_dev.requirement_capture --bundle /path/to/exported-inputs --out /path/to/new-capture --db /absolute/path/to/codedb/build/codedb.sqlite
```

The adapter requires the configured `requirements` profile and the exact recorded
source revision/hash. It makes zero provider calls. A source-verified but
unreviewed candidate is not silently counted as a confirmed identification.

## Run it

From the repository root, with Python 3.11 or later:

```sh
python3 -m unittest evals_dev.requirement_bench.test_requirement_bench -q
python3 -m evals_dev.requirement_bench synthetic-demo --out evals_dev/requirement_bench/runs/demo-001
python3 -m evals_dev.requirement_bench score \
  --manifest evals_dev/requirement_bench/runs/demo-001/manifest.json \
  --predictions evals_dev/requirement_bench/runs/demo-001/captured/predictions.jsonl \
  --split holdout --run-id synthetic-demo \
  --out evals_dev/requirement_bench/runs/demo-001/replayed-report.json
```

The demo plans three cases, reports zero expert-eligible cases and
`expert_metrics: null`, and makes zero provider calls. Replay reads the same
captured predictions. Scores and capture hashes reproduce; the scorer's own
runtime and current Git state can differ. New outputs are exclusive creations:
use a fresh directory/report name for each attempt. `runs/` is ignored by Git.

Exit status is **0** for structurally valid captures, **1** for missing, duplicate,
errored, malformed or unavailable captures, and **2** for an invalid dataset,
changed sealed artifact, or command failure. Exit 0 does not mean all requirements
were found, or that a key is exhaustive or expert-reviewed. JSON reports retain
the actual scores, denominators, per-case failures and missing requirement IDs.

## Grounding at the starting revision

At `661ab7e128b214dd0775d3e9b4aaf61f72e96e4d`, the inspected sources were:

- `engine/models_identify.py`: `IdentifyArticle.division` supports B; ranked
  `articles`, verifier picks, `committed`, `choices`, and A/C `process_refs` have
  different meanings. Identification does not write confirmed case provisions.
- `engine/models.py`: `Case.provisions` records confirmed Division B selections;
  `section_c` is a separate persisted artifact. Neither proves rendered visibility.
- `engine/identify/corpus.py`: production article retrieval reads Division B only.
- `codedb/store.py` and `codedb/sources.py`: source edition registry and compound
  `(doc, division, id)` identities. A read-only local database inspection found
  31 A articles, 2,080 B articles and 66 C articles, and 13,743 NBC-AE provisions
  across levels. These are corpus counts, not applicable-requirement counts.
- `Data Prompts/index.json`: 653 cases, declared source groups and outcome-leakage
  flags. `evals_dev/data_prompts/corpus.py` keeps shared default-input attachments
  together. Its loader also reads evaluation metadata, so this evaluator does
  **not** import that loader or any historical benchmark case/answer loader.

The isolated worktree lacked a built code database. Inspection and the catalog
CLI smoke used the existing database in the project checkout in read-only mode.
No heldout answer contents were inspected or transferred into production.

`catalog` exports source identities without copyrighted code prose:

```sh
python3 -m evals_dev.requirement_bench catalog \
  --db /absolute/path/to/codedb/build/codedb.sqlite --out /path/to/bundle/catalog.json
python3 -m evals_dev.requirement_bench key-template \
  --case-id case-001 --out /path/to/bundle/case-001.answer.json
```

The catalog command checks the live schema and `NBC(AE) 2023 p2` source label,
retains the source-text SHA and database/WAL hashes, and rejects corpus drift
during the snapshot. It supports NBC-AE 2023, 2nd printing; other codes and
standards remain explicitly unsupported unless a separately audited catalog is
provided. A source identity match verifies existence and edition, not applicability.

## Seal the dataset before prediction

Keep a private bundle directory containing a plan, catalog, frozen predictor
config, input documents, attachments and separately authored answer files.
All paths in a plan, input or manifest are relative to that bundle root. Paths
cannot escape the root, including through symlinks. A minimal plan is:

```json
{
  "schema_version": 1,
  "dataset_id": "reviewed-dataset-version",
  "catalog": "catalog.json",
  "config": "config.json",
  "cases": [{
    "case_id": "case-001",
    "split": "holdout",
    "groups": ["source-family-001", "rewrite-family-001"],
    "input": "case-001.input.json",
    "answer": "case-001.answer.json",
    "leakage_review": {
      "status": "unreviewed", "reviewer": null, "evidence": []
    }
  }]
}
```

This example deliberately cannot seal as a holdout until input leakage review
is cleared with reviewer identity and evidence. Other statuses are `cleared`
and `contains_outcome`; unreviewed/outcome-bearing inputs may be kept in train/dev
diagnostics. Declare **every** shared source, rewrite, application, attachment
family and related lineage group. A holdout is not clean merely because its ID
differs. Input review must address source decisions/outcomes inside supplied PDFs
and derived text, not only metadata fields.

An input document contains exactly these fields:

```json
{
  "schema_version": 1, "case_id": "case-001",
  "narrative": "The complete applicant-supplied description.",
  "facts": [{"field": "project.location", "value": "Applicant-supplied value"}],
  "attachments": [{"path": "attachments/input.pdf", "sha256": "64-lowercase-hex-characters", "media_type": "application/pdf"}]
}
```

Use empty arrays when no facts/attachments were supplied. No truncation occurs.
Input fields are allowlisted; obvious answer/outcome fact fields are rejected.
The predictor config has exactly `predictor` and `settings`: `predictor` contains
`name`, full `git_commit`, `dirty`, and `source_sha256`; unknown provenance values
are null. `settings` freezes the full model/prompt/retrieval configuration and any
seed, extraction version, timeout and cache policy. Do not put secrets or labels
in config. A config hash identifies the supplied settings, not independent proof
that an adapter used them.

```sh
python3 -m evals_dev.requirement_bench seal --plan /path/to/bundle/plan.json --out /path/to/bundle/manifest.json
python3 -m evals_dev.requirement_bench export \
  --manifest /path/to/bundle/manifest.json --split holdout --run-id run-001 \
  --out /path/to/predictor-inputs-run-001
```

Sealing hashes answer files as opaque bytes. Export does not deserialize keys.
Export contains only `requests.jsonl`, `predictor-config.json`,
`source-catalog.json` and declared input attachments. Requests contain the
full input plus case/run identifiers and input/config/catalog/opaque manifest
hash bindings. They contain no answers, answer paths, splits, groups, coverage
labels, review metadata or expected requirement IDs. The opaque manifest digest
binds the answer version without disclosing its contents.

The input_sha256 field is the private original input file's byte hash.
The separate input_payload_sha256 field is computed over the inline parsed input
using UTF-8 JSON with sorted keys, ensure_ascii=False, and separators (',', ':').
The public protocol.validate_request(packet) function recomputes that digest and
checks the request schema without key access. A predictor must call it **before**
reading the narrative or starting the engine. The payload digest preserves case,
whitespace, complete facts and attachment metadata; the normalized content_sha256
in the private manifest is used only for leakage grouping. Config and catalog
are exported as their exact original bytes, so their public file hashes are
directly verifiable by a predictor.

Seal/export/score all recheck hashes and split controls. Shared declared groups,
normalized narratives (case/whitespace insensitive), normalized full inputs or
attachment bytes cannot cross train/dev/holdout splits. Answer files or copies
of their bytes cannot be inputs, attachments, catalog or config. A change to an
input, answer, attachment, config or catalog requires a new seal and run;
previous prediction/evidence bindings fail rather than silently resuming a cache.

These are integrity checks, **not an access-control sandbox or semantic leakage
detector**. Run prediction in a separate process/account/container with only the
exported directory mounted. Do not expose the private bundle or scoring reports.
Hashes cannot detect undeclared paraphrase/source relationships, a mislabeled
review, an outcome hidden in prose, or intentional adapter misconduct. There is
no automatic ingestion of real cases until these checks and human input review
can be supplied.

## Author and review keys separately

`key-template` creates an empty real key with unknown coverage and unreviewed
status. It makes no requirement assertions. A key contains:

- `origin`: `real` or `synthetic`.
- `coverage`: `status` (`unknown`, `minimum`, `exhaustive`), `dimensions` with
  A/B/C/other each `reviewed` or `unreviewed`, and explicit `limitations`.
  Exhaustive declarations require all four dimensions reviewed.
- `review`: `status` (`unreviewed`, `provisional`, `expert_verified`), `reviewer`,
  `qualifications`, timezone-bearing `reviewed_at`, and `evidence`.
  Expert status requires these fields and hashed review evidence. Synthetic
  keys cannot claim expert status. Review evidence is supplied, not authenticated
  by this tool; no verified expert keys currently ship here.
- `requirements`: unique `id`, `role` (`primary`, `supporting`, `administrative`,
  `scope`), `reference`, `support` (`catalogued`, `unsupported`) and `provenance`.
  Provenance entries have `source`, `locator`, `sha256` (null allowed only for
  unverified sources). Expert-reviewed requirements require known source hashes.

Each reference includes **document, edition, printing, division, provision**.
Division is A/B/C or null for an external/unknown source. Edition/printing can
be null only for unsupported references. Catalogued keys must match the sealed
catalog exactly. Other-code/standard dependencies use `support: unsupported`
with a source scope/locator and remain unresolved; do not invent an article.

Use sentence/clause identifiers where distinct duties would otherwise collapse
into one article. Duplicate references are rejected. The evaluator measures
coverage of distinct annotated source references; an article match cannot prove
every duty within that article was understood. Exhaustiveness, applicability,
professional evidence and alternative-solution reasoning require expert review.
No automatic article/sentence expansion, fuzzy edition matching or model judging
fills that gap. Additional requirements outside a minimum/unknown key remain
unadjudicated, rather than being called false positives.

## Supply separate captured layers

`protocol.py` provides the input-only `Predictor` interface. Bind an adapter's
config/catalog/output dependencies before calling it with a request. The harness
never invokes an arbitrary executable or a provider. `example_predictor.py` is
only a synthetic marker reader and refuses real catalogs/configurations.

For each request, write one JSONL prediction record. Copy the request's fields
except `input`, and add exactly:

```json
{
  "status": "ok", "error": null, "elapsed_ms": 125.0, "requests": [],
  "observed_inputs": {
    "request": {"path": "observed-request.json", "sha256": "64-hex"},
    "config": {"path": "predictor-config.json", "sha256": "64-hex"},
    "catalog": {"path": "source-catalog.json", "sha256": "64-hex"},
    "attachments": []
  },
  "layers": {
    "retrieval_candidates": {"path": "capture.json", "sha256": "64-hex"},
    "identified_requirements": {"path": "capture.json", "sha256": "64-hex"},
    "application_included": null,
    "applicant_visible": null
  }
}
```

All four layer names must be present; null means not observed, which earns no
coverage credit. Evidence paths are relative to the predictions file's directory.
Every successful prediction also requires observed_inputs: retain the actual
input-only request packet (all bindings plus input) as JSON, exact config/catalog
files, and all supplied attachments as file references. Paths may be relocated
within the capture directory; attachment hash multiplicities must match the
request. The scorer opens and hashes these files, recomputes the inline payload
digest, and compares bindings to the sealed manifest. Merely copying claimed
hash strings is insufficient. Rehashing a tampered observed request while keeping
old bindings still fails. observed_inputs may be null for an error before input
loading; error records receive no hits.

An evidence JSON repeats **all** request bindings except `input`, adds `kind`
(`captured` or `synthetic`) and a `layers` object. Each supplied layer has exactly
`items` and `raw_artifacts`. An item is:

```json
{
  "reference": {"document": "SYNTHETIC-TEST-CODE", "edition": "fixture-v1", "printing": "test-only", "division": "C", "provision": "admin"},
  "resolution": "resolved", "reason": null
}
```

These example symbols are intentionally not real citations. `unresolved` items
need a nonempty reason and the same structured source scope as the key. Resolved
items must exist in the sealed catalog. Wrong edition/printing, invented citations,
duplicate references, stale bindings or changed evidence hashes invalidate that
layer and award zero hits. A top-level error/malformed/duplicate prediction awards
zero hits at all layers, even if it references a previously successful capture.

For real captures, `raw_artifacts` must be a nonempty list of `{path, sha256}` file
references for **each** supplied layer. Use the actual retrieval trace, complete
identification result, persisted application snapshot/export, and applicant
DOM/accessibility capture plus saved screen evidence, respectively. The adapter
must extract references from that layer's observed artifact. A/C process refs
must not automatically be treated as selected application requirements. An API
list, committed list, or saved selection does not establish applicant visibility.
There is no assumed three-item limit: the scorer uses the supplied visible list's
actual length. Hash checks bind the adapter's assertions to retained artifacts;
they cannot authenticate that a DOM list was visible or interpret screenshots.
Inspect browser evidence separately before claiming real applicant coverage.
Retained input artifacts establish what the adapter logged as observed inputs;
they are not execution attestation that the engine used them. A real adapter
must validate before dispatch, pass those validated values to the engine, and
retain its raw engine traces. This generic scorer does not execute or certify an
adapter, infer its internal behavior, or replace independent adapter review.

Each provider request, including retries and failed dispatches, records
`request_id`, `provider`, `model`, `status`, `input_tokens`, `output_tokens`,
`cost_usd`, `latency_ms`, `error`. IDs must be unique. Status is `ok` or `error`;
error text must agree with status. Unknown model/usage/latency/cost values are
null, never guessed zero. Use an empty request list only when no provider
dispatch occurred. Captured end-to-end attempt latency is separate from request
latency and the evaluator's own runtime.

## Read the metrics honestly

| Metric | Numerator / denominator and limit |
| --- | --- |
| Known requirement recall | Resolved, catalogued key matches / **all known requirement occurrences**, including unsupported dependencies. Unsupported items cannot receive resolved credit. |
| Supported requirement recall | Same matches / catalogued key occurrences only. This narrower score cannot establish full coverage. |
| All-known requirements recalled | Nonempty cases with every known requirement resolved / **all planned cases**. Empty/unknown keys never win by vacuous set inclusion. |
| Any-hit diagnostic | Cases with at least one resolved key match / all planned cases. Finding the primary article alone is insufficient. |
| All-known accounted-for diagnostic | Every known requirement either resolved or correctly marked unsupported/unresolved / all planned cases. This is not full identification. |
| Unsupported explicitly unresolved | Correct unresolved scope matches / known unsupported requirements. |
| Declared-exhaustive exact set match | Exact nonempty set matches / planned cases whose keys declare exhaustive coverage and have no unsupported requirements. Synthetic/provisional versions remain diagnostics. |
| Precision on declared-exhaustive keys | Key matches / observed predictions on those eligible keys; absent predictions do not establish precision. |

All layers also report division and role recall. Missing, malformed, duplicate,
errored, invalid and unsupplied predictions stay in their preplanned case and
requirement denominators. No conditional-success headline replaces them. A zero
requirement denominator produces null recall/exact accuracy, never 100%.
Unknown/minimum keys cannot establish exhaustive accuracy even if every known
reference was returned. An entirely unsupported/unknown corpus cannot establish
product accuracy through the supported-only score.

`expert_headline.metrics` is null unless real, nonempty, expert-verified,
exhaustive, fully catalogued keys with cleared input leakage reviews exist.
Synthetic and provisional cohorts are always separate. `whole_planned_set_eligible`
also requires every selected case to qualify. Capture-level unassignable errors
or duplicate request IDs withhold the expert headline; planned diagnostics still
retain failures. The reported split distinguishes development from heldout
results; do not claim a blind holdout if you trained on it or its diagnostics.

Accounting retains failed requests and valid ledger entries even when another
entry is malformed. Unknown/missing usage propagates null aggregate cost/tokens
and request totals as appropriate; known subtotals remain labeled as reported
subtotals. Repeated request IDs make totals uncertain rather than double-charging
a claimed exact total. Latency samples include failures, with sample/unknown
counts, median, nearest-rank p95 and range. These are captured observations, not
an authenticated invoice or a performance comparison. Offline replay preserves
original capture usage while recording zero fresh provider requests and spend.

Reports retain manifest/input/answer/config/catalog/prediction/evidence hashes,
source database and WAL provenance, declared source groups, review coverage,
predictor Git/source identity, sealing/scoring Git state and harness source
hashes. The original captures and private key bundle are required for replay.
The seal is a reproducibility checksum, not a signature or proof of expert review.

Regression tests exercise the real CLI/scorer and split checks: late deciding
text, A/B/C supporting and administrative requirements, unsupported standards,
wrong editions/invented citations, unknown/empty keys, omitted/duplicate/malformed
records, stale input/config/answer/evidence, fresh reruns, group/narrative/attachment
leakage, request failures/retries, null costs and failed latency. This CLI has no
product visual surface; executable output and tests are its verification evidence.
The regressions also mutate inline narratives while preserving all old bindings,
rehash substituted observed artifacts, and check attachment bytes and exact
config/catalog exports.

## Implementation verification

The local focused suite passed with 62 unittest tests and, in the project's
Python environment, 62 pytest tests plus 12 subtests. The synthetic CLI and an
independent replay produced identical scores, denominators, cohorts, evidence
references and original usage accounting. Expert metrics remained null and fresh
provider requests/spend stayed zero. The catalog command exported 13,743 identities
from the existing read-only code database. Compilation and diff checks passed.

The broader engine gate was attempted: 2,431 passed, 1,923 skipped, 12 failed and
37 setup errors. This isolated worktree has no built codedb at its required local
path; failures report missing/unopenable code database and dependent route/probe
failures. That gate is not a pass. No database was copied or source changed outside
the assigned paths to conceal this prerequisite.

Methods applied: the T3 workflow router and visual-evidence guidance (CLI output
is the observable surface); pstack's tracked feature playbook and
benchmark-checklist; Matt Pocock codebase-design and code-review; and the
Batatis hackathon/variance-workflow domain methods. Review was local under the
explicit no-subagents instruction.
