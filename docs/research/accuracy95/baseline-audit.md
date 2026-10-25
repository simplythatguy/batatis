# Accuracy baseline audit — 2026-10-25

## Finding

The quoted **Edmonton 17 / 70%** and **Calgary 8 / 69%** figures are check-level micro-accuracy from the saved `it1-review` **development** run. They are not whole-case correctness, and they are not a result for the currently selected Luna + Jev profile. Recalculation from the saved development score rows gives:

| City | Dev cases | F: source facts | R: review points | B: boundaries | A: named articles | All checks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Edmonton | 17 | 55/73 (75.3%) | 52/86 (60.5%) | 3/3 (100%) | 13/13 (100%) | **123/175 (70.3%)** |
| Calgary | 8 | 20/36 (55.6%) | 27/35 (77.1%) | 9/10 (90.0%) | 2/3 (66.7%) | **58/84 (69.0%)** |
| Combined Calgary / Edmonton tier | 25 | 75/109 (68.8%) | 79/121 (65.3%) | 12/13 (92.3%) | 15/16 (93.8%) | **181/259 (69.9%)** |

The 17 and 8 are case counts. The percentage denominator is **175 and 84 reference checks**, respectively. F/R/B/A checks are weighted equally in the micro-average, so cases with more checks carry more weight. The main recorded misses in this local slice are source facts and review points, not article checks.

## Which run produced the figures

The authoritative saved development row file is:

`/Users/aamia/.t3/worktrees/batatis/data-prompts-eval/.dpe-cache/runs/it1-review/score-dev-gpt-6.1-sol-low.jsonl`

Its aggregate is:

`/Users/aamia/.t3/worktrees/batatis/data-prompts-eval/.dpe-cache/runs/it1-review/score-dev-gpt-6.1-sol-low.summary.json`

The paired run metadata is:

`/Users/aamia/.t3/worktrees/batatis/data-prompts-eval/.dpe-cache/runs/it1-review/meta.json`

The metadata says `split=dev`, `intake_model=gpt-6-luna`, `intake_effort=medium`, engine commit `437e0f553e8faef6a9b8525a56bbd1d4a7616f4b`, engine tree `23c1524a767bd4465119363eb35d2c20ab38884e`, and identify config hash `464590da27f5cbf1`. The decision record identifies the document-review prompt as the original prompt, SHA-256 `4a29a9bd45488d5d531b9cfaa6c5d37cab285c3576b6fb63a27743611b3054d0`, matching commit `437e0f55`.

**The `gpt-6.1-sol-low` part of the score filename is the judge, not the generator.** The saved summary records judge `gpt-6.1-sol:low`; Luna medium generated intake and document review. The historical metadata configured Elephant screening/reranking but also records `elephant=false`. Inspection of the 334 development outputs found `identify.mode=bm25_fallback` in **334/334** cases. Therefore the article check is not evidence for the selected Jev identification path. The configured verifier model was not reached in those fallback outputs.

This run is also not the selected combined profile. The locked profile in the decision record is Luna medium for extraction, review and full-text verification, with Jev 1.13.0 screening all 2,080 Division B articles and reranking the top 60, then Luna medium verifying the top 15; config hash `5f1c92331550984a`. The record explicitly says combined-profile accuracy was not verified. Do not label the 70/69 figures as current-product or 95% accuracy.

## Saved baselines and accounting

| Saved result | Split | Cases | Checks passed / expected | Accuracy | Generator / judge | Key limitation |
| --- | --- | ---: | ---: | ---: | --- | --- |
| `baseline` | dev | 334 | 597 / 2,981 | 20.03% | Luna medium / Sol low | No live document review (`review_status=none`) |
| `baseline` | holdout, aggregate only | 319 | 589 / 2,851 | 20.66% | Luna medium / Sol low | Aggregate summary only; no item-level holdout errors or outputs inspected |
| `it1-review` | dev | 334 | 2,308 / 2,981 | 77.42% | Luna medium + original review prompt / Sol low | Historical checkpoint; not the locked Luna + Jev profile |

The strongest saved completed Luna development result is 2,308/2,981, **77.42%**, not 95%. In the `it1-review` development summary the check counts are F 891/1,255, R 1,071/1,311, B 289/352 and A 57/63. This suggests that document review accounts for a large measured change over the no-review baseline, while facts and review points remain the largest sources of non-passes.

The baseline counts and hashes are preserved in [`workflow-accuracy-evidence-20261025.json`](../../evaluations/workflow-accuracy-evidence-20261025.json), and the interpretation/limits are in [`workflow-decision-20261025.md`](../../evaluations/workflow-decision-20261025.md). The summary artifact hashes recorded and verified against the saved files are:

- `baseline` dev summary: `9662cab1272a0ed395fa219d2c83fad322a0961b6872da13a11520c680b9152e`
- `baseline` holdout aggregate summary: `51ae0e1205b7b7c265da2e5a5fb42e29243df3fcebd00e0a7b2c937f0d4f65c1`
- `it1-review` dev summary: `cea74539c65350a8e96664bb481bed3cd68f4a1ab90f4e08abda4076946d9bd2`

These are historical, pre-integrity-repair artifacts. The old run folders have `meta.json` but no frozen `manifest.json`; the per-case score rows do not record validator version or provenance, and most failed checks have blank note/evidence. The judge model/effort is recoverable, but the exact validator build for these scores is not. The later evidence record says these results lack fully verified frozen-run provenance.

## Operational errors and guardrails

For `it1-review` dev, the aggregate records 334/334 live document reviews, zero missing case outputs and zero judge request failures. The saved case outputs have no top-level run errors. This does **not** mean the configured article model ran: all 334 identification outputs used BM25 fallback while the operational `ran` guard still passed.

Guardrails are separate from the F/R/B/A accuracy denominator. In `it1-review` dev:

- `citations_resolve`: 334/334 pass.
- `no_alberta_commit_outside_alberta`: 334/334 pass.
- `ran`: 334/334 pass.
- `no_claims`: 305/334 pass (**29 failures**); all 25 Edmonton/Calgary cases pass this guard.
- Judge notes include 10 `unverified` and 9 `violation` outcomes; the aggregate records zero judge-call failures.

The 29 `no_claims` failures are not all proof of an unqualified product claim. One development example, `H02-002`, is flagged on the sentence “Stated in the request: the consent plans say the stair must comply with D1/AS1 …”; other examples report attributed findings from an assessment manager or published ruling. The lexical guard scans Batatis-authored review text and can confuse attributed source positions with Batatis's own conclusion. The decision record also reports a synthetic false negative where unqualified assertions such as “Structural safety is assured” passed the production and independent lexical filters. Keep this guard hard; improve attribution-aware detection and evaluate both false positives and false negatives.

## First failing layers and concrete development examples

1. **Judge credit and measurement provenance need review before prompt tuning.** In development case `L05-001`, the score rows mark F3 and R1 as misses. The rendered report says the guide's designs are inspirational and incomplete, says they are not for development/building-permit approval or construction, says site-specific information is not accounted for, calls the source a guide rather than an application, and asks whether Example A is only a guide reference or a real proposal. That looks like substantial or complete coverage of the cited checks, yet the legacy score row has no note/evidence explaining its non-pass. Treat this as an evaluator-credit disagreement to adjudicate, not as proof that the prompt needs more boilerplate. The old judge validator version is not recorded.

2. **Source-fact and review-point coverage are the main measurable content misses.** The full dev `it1-review` counts are F 891/1,255 (71.0%) and R 1,071/1,311 (81.7%). In Calgary case `A03-004`, the review records the 1967 planetarium, owner/developer, project cost and attributed life-safety statements, but the scorer marks F1/F3/F4 missed around the conversion/heritage description and complete service-core and systems details. In Calgary case `L04-002`, the review preserves the general product-advisory boundary and asks for the permit address, but its score rows miss R1-R3 on the NPC 2015 versus NBC(AE) distinction, the specific product/partial-flow-through/DuCF scope, and the conditional DCVAF fallback. These are precise extraction and review targets; preserve their source, edition, status and conditions as atomic facts with page quotes.

3. **Review findings do not reach the article scorer in this historical run.** The engine call passes `engine_case.facts` into `identify_run`; the review remains separately under `case.intake.review`. For `A10-001`, review output contains many source facts and cited provisions, but identification still records BM25 fallback. Before tuning article prompts or thresholds, ensure the current profile forwards only verified, source-backed reviewed facts and cited provisions into its Jev screen/rerank. The separate h6 experiment tried this seam but its saved Jev runs were incomplete and unscored.

4. **Article checks are too small and too incomplete to support an article-quality claim here.** The city slice has only 16 A checks. The full `it1-review` dev run also used BM25 fallback, and the decision record says named article references are incomplete positives; the check does not score false-positive articles or establish precision. Measure article retrieval under the actual Jev profile before making an article accuracy claim.

## Ranked fix candidates

1. **Repair measurement credit first.** Adjudicate cases like `L05-001` against the rendered report and gold, record the validator version, and retain reasons/evidence for every failed check. Otherwise a prompt can be changed to satisfy a judge miss rather than a product omission.
2. **Improve source-backed fact and review coverage.** Preserve complete, atomic table/schedule values, source/page, edition, status, and conditions through extraction and review. Use `A03-004` and `L04-002` as concrete coverage cases; evaluate whether each listed fact is truly absent before changing prompts. h2 tried whole-entry/example-status instructions, but has no full-score evidence.
3. **Verify the review-to-identification handoff on the locked profile.** Pass only verified, cited review facts/provisions to Jev and prove screening, reranking and verification actually ran. h6 tried reviewed-prose input, but its Jev studies were incomplete; the historical 334-case run used BM25 fallback throughout.
4. **Make claim guardrails attribution-aware while preserving both sides of the guard.** Reduce false positives for clearly attributed external positions such as `H02-002`, and close the recorded false-negative pattern (“Structural safety is assured”). Keep these guardrail outcomes separate from F/R/B/A scores.
5. **Only then tune article retrieval or review prompting against verified misses.** The saved city slice has just 16 A checks, incomplete positives, and no false-positive scoring, so it cannot rank article matcher changes or substantiate 95% accuracy.

## What the `dpe-h*` branches already tried

The local branch inventory contains h2, h3, h5, h6, h7, h8 and h9; no h1 or h4 branch was present. Relative to this task worktree's `HEAD=e5e794b6ab828afdfc52858cf3ed75d39e62a73c`, h7 and the h8 parent commit `259b6b1c` are ancestors; the listed h2/h3/h5/h6/h8/h9 branch tips are not.

| Branch / commit | Attempt | Evidence and status |
| --- | --- | --- |
| h2 `dbda0c14` | Review prompt asks for whole table/schedule entries as one fact, complete values and excerpts; guide/study values are explicitly not facts about an actual applicant/site. Raised excerpt limit to 600 characters. | Targeted prompt change only; not an ancestor of this worktree. No completed full accuracy score attributable to it. |
| h3 `b667f37b` | Redaction keeps short numeric legal-description values and replaces known values only at whole-word boundaries. | Focused redaction change/tests; not an ancestor. No accuracy result. |
| h5 `de6e16de` | Skips the duplicate first-pages model pass over files when full document review runs; retains rules/forms extraction. The branch also adds redirect/scoring harness safeguards. | Cost/workflow change; not an ancestor. No completed accuracy score. |
| h6 `57c147bd`, `6a8b3e9e` | Adds up to 4,000 characters of reviewed facts and resolved cited provisions to identification prose; adds a Jev study comparing request-only with request-plus-review across all 2,080 articles, top-60 rerank and no verifier. | The decision record says `it5-jev` and `it6-prose-jev` outputs are incomplete with no completed score. Not an ancestor. This is an already-tried handoff hypothesis, not evidence of improvement. |
| h7 `b1d7fe05` | Retries transient dropped connections, rate limits and server errors, and permits rerunning failed network cases. | Reliability change; it is in this task worktree's history. It does not improve content coverage by itself. |
| h8 parent `259b6b1c` | Judge/guardrail distinguishes attributed source reports from Batatis's own verdicts. | This attribution update is in the current worktree history. |
| h8 `e0979bfc` | Prevents a foreign-jurisdiction provision with a matching number from being presented as an NBC(AE) provision. | Not an ancestor of this worktree. Safety boundary fix; no accuracy score. |
| h9 `e2c74b2d` | Prompt v3 adds who decides, historical status, separate matters, product scope, code editions and unattached references. | Not an ancestor. The saved paired 14-component dev comparison used DeepSeek Flash max as both review model and judge with `judge-v7-strict`: original 89/130 (68.46%), v3 91/130 (70.00%). The source-group interval was −13.33 to +15.17 points; one review failed in each arm and v3 had two invalid/unverified judge outcomes. It did not establish a prompt gain. These figures are separate from the Edmonton/Calgary city figures. |

## Prompt/gold separation and holdout boundary

The SUT source path is cleanly separated at the code level: `sut.run_case` passes `case.prompt` and the default-input attachment bytes to the engine; it does not pass `Case.facts`, `Case.focus` or `known_outcome`. `gold.gold(...)` is constructed in the scoring path after the result exists. The split code groups cases sharing a source group or attachment hash and assigns the whole component to dev or holdout.

The saved 14-case prompt-comparison context audit also records 28 intended inputs, 14 equal request/schema pairs and 32 captured requests, with no extra agent or evaluation context found. That audit is scoped to that experiment, not all 334 historical calls. No item-level holdout errors or outputs were opened for this audit; holdout evidence above is limited to its saved aggregate summary.

## Exact read-only reproduction commands

Run the following from the old evidence checkout. These read local saved development scores and corpus metadata only; they do not run the engine, judge or any provider.

```sh
git -C /Users/aamia/.t3/worktrees/batatis/data-prompts-eval rev-parse HEAD
shasum -a 256 \
  /Users/aamia/.t3/worktrees/batatis/data-prompts-eval/.dpe-cache/runs/baseline/score-dev-gpt-6.1-sol-low.summary.json \
  /Users/aamia/.t3/worktrees/batatis/data-prompts-eval/.dpe-cache/runs/baseline/score-holdout-gpt-6.1-sol-low.summary.json \
  /Users/aamia/.t3/worktrees/batatis/data-prompts-eval/.dpe-cache/runs/it1-review/score-dev-gpt-6.1-sol-low.summary.json
cd /Users/aamia/.t3/worktrees/batatis/data-prompts-eval
PYTHONPATH=. python3 - <<'PY'
import json
from collections import Counter
from pathlib import Path
from evals_dev.data_prompts import corpus

cases = {c.id: c for c in corpus.select('dev')}
path = Path('.dpe-cache/runs/it1-review/score-dev-gpt-6.1-sol-low.jsonl')
by_city = {city: Counter() for city in ('Edmonton', 'Calgary')}
for line in path.read_text().splitlines():
    row = json.loads(line)
    city = cases[row['case_id']].city
    if city not in by_city:
        continue
    acc = by_city[city]
    acc['cases'] += 1
    for check in row['checks']:
        acc['checks'] += 1
        acc['passed'] += bool(check['passed'])
        acc[check['kind'] + '_n'] += 1
        acc[check['kind'] + '_passed'] += bool(check['passed'])
for city, acc in by_city.items():
    print(city, dict(acc), f"{acc['passed'] / acc['checks']:.4%}")
PY
```

The repository commands documented for a new run are `python -m evals_dev.data_prompts run ...` and `score ...`, but they can invoke providers if caches miss. They were **not** run for this audit.

## Methods used

- T3 workflow routing and direct-research route: `/Users/aamia/.codex/skills/t3-workflow/SKILL.md` and `references/routes.md`.
- pstack `benchmark-checklist`: `/Users/aamia/.agents/skill-libraries/pstack/skills/benchmark-checklist/SKILL.md`, applied proportionately to accuracy denominators, output/error accounting, provenance and whether the active workflow actually ran.
