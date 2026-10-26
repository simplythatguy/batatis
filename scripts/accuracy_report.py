#!/usr/bin/env python
"""Build the accuracy report: docs/accuracy/report.json (read by the #/accuracy page) and docs/accuracy/report.md.

    python scripts/accuracy_report.py                       # code identification from evals_dev/identify_bench if present
    python scripts/accuracy_report.py --bench-ref REF       # ... or from a git ref that holds the benchmark (draft PR #58)
    python scripts/accuracy_report.py --no-verify           # draft: skip running the tests behind the guaranteed claims

Two kinds of claim, kept apart:

* Guaranteed: true by construction and enforced by named tests. The builder fails when a claim names no test or a test
  that does not exist, then runs them and fails unless every one passes (skipped counts as not passed).
* Measured: a number with its dataset, sample size, date, interval and source (a file and commit, or a PR body and its
  merge commit). The builder fails when a figure has no source. Deterministic figures are recomputed from the stored
  datasets at the current commit; figures that cannot be recomputed (a first blind run, a gate run) are quoted from the
  PR body that recorded them.

Code identification is read from the benchmark's stored result rows with the benchmark's own report code and decision
rule (`scripts/accuracy_codeid_probe.py`). When the benchmark finishes, re-running this script updates that section with
no code change. No provider is called, no key is read, and the held-out and judge-only data are never opened.

Nothing user-visible may name an AI provider: the output is scanned before it is written.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / 'docs' / 'accuracy' / 'report.json'
OUT_MD = ROOT / 'docs' / 'accuracy' / 'report.md'
BENCH = 'evals_dev/identify_bench'
SCHEMA = 'batatis-accuracy/1'
EDITION = 'NBC(AE) 2023, 2nd printing'

# The same names the provider guard tests refuse (engine/tests/test_no_provider_names_exposed.py), plus model
# family names. Arm ids in the benchmark contain some of these, so they are mapped before anything is written.
PROVIDER_NAMES = re.compile(r'jev|typesafe|openai|anthropic|claude|\bgpt|\bluna\b|sonnet|opus|haiku|gemini', re.I)
HEX = re.compile(r'^[0-9a-f]{7,40}$')


class ReportError(ValueError):
    """The report would contain a figure without a source, a claim without a test, or a provider name."""


# ---------------------------------------------------------------------------------------------------------------
# Guaranteed claims. Each names the tests that enforce it. A test whose id names a provider is left out of the list
# (the id would be shown on the page); the claim still holds through the tests that are listed.

GUARANTEED = [
    {
        'id': 'citations-resolve',
        'claim': f'Every code reference Batatis shows is checked against the {EDITION} code database.',
        'detail': ('An article number that is not in the database is removed from code identification and from assistant '
                   'answers, or kept as the applicant’s own unchecked text. The exported form text passes the '
                   'citation validator with zero errors.'),
        'tests': [
            'engine/tests/test_identify_service.py::test_lying_model_never_shows_a_fabricated_citation',
            'engine/tests/test_assist.py::test_grounded_provision_lookup_citations_removal_and_spend_receipt',
            'engine/tests/test_intake_extract.py::test_article_numbers_resolve_in_codedb_or_stay_unresolved_text',
            'engine/tests/test_export_g3.py::test_codedb_validate_cli_reports_zero_errors',
            'codedb/tests/test_validator.py::test_detects_invalid_citations',
        ],
    },
    {
        'id': 'fabrications-filtered',
        'claim': 'A made-up citation or quote from an AI model never reaches the screen.',
        'detail': ('Tests replace the model with one that lies on purpose: invented article numbers, paraphrased or '
                   'invented quotes. A pick is kept only when its quote appears word for word in the article. Over 30 '
                   'random liars, nothing invented is shown.'),
        'tests': [
            'engine/tests/test_identify_service.py::test_lying_model_never_shows_a_fabricated_citation',
            'engine/tests/test_identify.py::test_quote_check_drops_paraphrase_and_unlisted_articles',
            'engine/tests/test_intake_extract.py::test_a_lying_model_can_only_point_at_real_words',
            'engine/tests/test_identify_service.py::test_verifier_failure_means_no_commit',
        ],
    },
    {
        'id': 'section-c-lookup',
        'claim': 'Section C objectives and functions come from a lookup in the code’s attribution tables, not from an AI model.',
        'detail': ('Once an article is identified, its objective and function rows are read from the tables. Where a '
                   'sentence has no row, Section C says so. Where the national intent differs, it is labelled.'),
        'tests': [
            'engine/tests/test_section_c.py::test_most_varied_part9_sentences',
            'engine/tests/test_section_c.py::test_article_without_table_row_says_so',
            'engine/tests/test_section_c.py::test_differs_flag_comes_from_intent_comparison',
            'engine/tests/test_export.py::test_section_c_cells_and_appendix_match_section_c_rows',
            'engine/tests/test_export_g3.py::test_section_c_rows_carry_identification_lookup_and_quoted_sentence',
        ],
    },
    {
        'id': 'no-filled-blanks',
        'claim': 'Batatis never fills a blank to make the form look complete.',
        'detail': ('A value reaches the form only with a source in the applicant’s own words or files; a guess, or '
                   'sources that disagree, wait for the applicant. A field '
                   'shows N/A only when the applicant said it does not apply and gave a reason. The official form stays '
                   'locked while a required field is empty.'),
        'tests': [
            'engine/tests/test_export_na.py::test_without_the_fact_the_field_stays_blank_and_is_never_shown_as_n_a',
            'engine/tests/test_export_na.py::test_only_the_applicant_can_mark_a_field_not_applicable',
            'engine/tests/test_export.py::test_blocks_on_unconfirmed_facts_and_blocking_gaps',
            'engine/tests/test_export.py::test_direct_export_cannot_bypass_authoritative_completeness',
            'engine/tests/test_intake_extract.py::test_no_value_without_a_source_on_dev_cases_and_stripped_copies',
            'engine/tests/test_intake_extract.py::test_values_read_from_the_applicants_own_words_are_used_without_asking',
            'engine/tests/test_intake_extract.py::test_a_guess_or_a_reading_against_the_applicants_answer_stays_to_check',
            'engine/tests/test_package_review_boundary.py::test_never_fills_a_blank_from_elsewhere_in_the_package',
        ],
    },
    {
        'id': 'applicant-writes-the-case',
        'claim': 'Batatis never writes the applicant’s case or the officer’s decision.',
        'detail': ('The rationale, risk assessment, mitigating measures, assumptions and limits are the applicant’s '
                   'words. Text an AI drafted, or altered applicant text, is refused at export.'),
        'tests': [
            'engine/tests/test_process_fields.py::test_applicant_passage_roundtrips_but_ai_cannot_fill_field',
            'engine/tests/test_export.py::test_generated_or_altered_process_content_never_exports',
            'engine/tests/test_package_review_boundary.py::test_never_writes_risk_mitigation_or_assumptions',
            'engine/tests/test_completeness.py::test_checker_does_not_claim_compliance_or_write_process_answers',
        ],
    },
    {
        'id': 'no-compliance-language',
        'claim': 'Batatis never says a design complies, is safe, approved or adequate.',
        'detail': ('The checker, the assistant, the coded rules, the checklists, the intake notes, the package review '
                   'and the exported form are each tested for those words. It reports what is missing, not whether the '
                   'design is right.'),
        'tests': [
            'engine/tests/test_completeness.py::test_checker_does_not_claim_compliance_or_write_process_answers',
            'engine/tests/test_assist.py::test_compliance_and_safety_verdicts_are_stopped',
            'engine/tests/test_rules_vectors.py::test_no_rule_text_or_output_says_complies_safe_approved_or_adequate',
            'engine/tests/test_checklists.py::test_copy_never_says_complies_safe_approved_or_adequate',
            'engine/tests/test_intake_plan.py::test_fork_wording_keeps_the_two_halves_distinct',
            'engine/tests/test_package_review_boundary.py::test_no_compliance_language_in_any_generated_text',
            'engine/tests/test_export_g3.py::test_wording_check_catches_a_banned_word',
        ],
    },
    {
        'id': 'personal-details-scrubbed',
        'claim': ('Before the intake reader, code identification or the assistant sends text to an AI model, Batatis '
                  'removes the names, contact details and addresses it recognizes.'),
        'detail': 'Known values from the application and the account are replaced too, including a name read from an uploaded file.',
        'tests': [
            'engine/tests/test_redact.py::test_known_personal_facts_are_replaced_case_insensitively',
            'engine/tests/test_intake_extract.py::test_model_text_is_scrubbed_before_it_leaves',
            'engine/tests/test_intake_pdf.py::test_a_name_read_from_a_file_is_scrubbed_from_the_description_sent_to_the_model',
            'engine/tests/test_identify_service.py::test_identify_redacts_personal_details_before_the_provider',
            'engine/tests/test_assist.py::test_personal_information_is_redacted_before_the_provider_sees_it',
        ],
    },
    {
        'id': 'no-provider-names',
        'claim': 'The web app, code identification answers, the exported form and this report name no AI provider.',
        'detail': ('Tests scan the web code that ships to the browser, the code identification responses, the exported '
                   'PDF, this report and this page for provider names.'),
        'tests': [
            'engine/tests/test_no_provider_names_exposed.py::test_web_source_that_ships_to_the_browser_names_no_provider',
            'engine/tests/test_no_provider_names_exposed.py::test_identify_responses_name_no_provider',
            'engine/tests/test_no_provider_names_exposed.py::test_the_export_headers_and_pdf_name_no_provider',
            'engine/tests/test_no_provider_names_exposed.py::test_the_accuracy_report_names_no_provider',
            'web/src/calm/no-provider-names.test.ts::the accuracy page and its report name no provider',
        ],
    },
    {
        'id': 'refused-run-writes-nothing',
        'claim': 'A refused or failed run leaves no partial write.',
        'detail': ('A run refused for a stale version, a rate limit or a concurrent edit changes nothing on the '
                   'application. A failed model call stores no model facts and commits no article.'),
        'tests': [
            'engine/tests/test_identify_service.py::test_answers_are_written_with_the_result_or_not_at_all',
            'engine/tests/test_identify_service.py::test_stale_expected_version_is_a_409_and_changes_nothing',
            'engine/tests/test_identify_service.py::test_identify_run_is_one_cas_and_a_write_during_it_is_a_409',
            'engine/tests/test_intake_plan.py::test_a_stale_version_is_refused_before_any_model_call',
            'engine/tests/test_intake_extract.py::test_gate_closed_and_failures_store_no_model_facts',
        ],
    },
    {
        'id': 'nothing-committed-uncalibrated',
        'claim': 'Code identification does not pick an article on its own while its commit rule is uncalibrated.',
        'detail': 'Until a calibration exists it offers at most three quoted choices, and the applicant decides.',
        'tests': [
            'engine/tests/test_identify_service.py::test_uncalibrated_default_commits_nothing_and_offers_three_quoted_choices',
        ],
    },
    {
        'id': 'rule-evaluators-agree',
        'claim': 'The coded rules give the same answer in the browser and on the server.',
        'detail': ('Two evaluators, one in Python and one in TypeScript, run the same hand-set vectors and must produce '
                   'identical output.'),
        'tests': [
            'engine/tests/test_rules_vectors.py::test_golden_outputs_are_current',
            'web/src/rules/rules.test.ts::cross-language agreement: every full output equals the Python evaluator\'s (outputs.json)',
        ],
    },
]

# Claims considered and left out because no test enforces them as worded. Shown in report.md only.
NOT_CLAIMED = [
    {'claim': 'Personal details are scrubbed before relevance scoring.',
     'why': 'The relevance route calls the scrubber, but no test asserts it, so the guarantee names only the three paths that are tested.'},
    {'claim': 'No compliance language anywhere.',
     'why': 'The tests cover the generated text of named components, not every string in the product, so the claim names those components.'},
]


# ---------------------------------------------------------------------------------------------------------------
# Figures that cannot be recomputed. Quoted from the PR body that recorded them, with its merge commit.

PR54 = {'kind': 'pr', 'pr': 54, 'commit': 'd13e2d6ce68040fb1b05c589c3f4407023635a77'}
PR60 = {'kind': 'pr', 'pr': 60, 'commit': '43e7c0938f2cbb17a09b92cc39f91159f5a4cb29'}
PR54_DATE = '2026-10-21'
PR60_DATE = '2026-10-21'

G3_RECORDED = {
    'cases': [
        ('Manufacturer, nail-base sheathing (demo)', 27, 23),
        ('Contractor, firestop (demo)', 37, 13),
        ('Homebuilder, infill house (demo)', 28, 22),
        ('BTRboard sample', 45, 5),
    ],
    'checks': ['N/A only from applicant facts', '50 applicant fields filled or N/A', 'Citation validator: 0 errors',
               'Render test', 'Section C and process rows', 'Precedent-example panel data', 'Offline registry snapshot and bundle',
               'Wording'],
    'quote': ('a-manufacturer-nailbase-sheathing: 27 filled + 23 N/A of 50 ... b-contractor-firestop-nonconformance: 37 filled + 13 N/A of 50 ... '
              'c-homebuilder-infill-house: 28 filled + 22 N/A of 50 ... sample-btrboard: 45 filled + 5 N/A of 50 ... G3 PASS'),
}


# ---------------------------------------------------------------------------------------------------------------
# helpers

def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def head_commit() -> tuple[str, bool]:
    sha = git('rev-parse', 'HEAD')
    dirty = bool(git('status', '--porcelain', '--', '.', ':(exclude)docs/accuracy/report.json',
                     ':(exclude)docs/accuracy/report.md'))
    return sha, dirty


def wilson(x: float, n: int) -> list[float] | None:
    from evals_dev.stats import wilson_interval
    if not n:
        return None
    return [round(v, 4) for v in wilson_interval(min(max(x, 0.0), float(n)), n)]


def count(x: float) -> str:
    return str(int(x)) if abs(x - round(x)) < 1e-9 else f'{x:.1f}'


def figure(fid: str, label: str, x: float, n: int, *, dataset: str, sample: str, date: str, source: dict,
           tags: list[str] | None = None, interval: bool = True, note: str | None = None) -> dict:
    lo_hi = wilson(x, n) if interval else None
    return {'id': fid, 'label': label, 'x': round(x, 4), 'n': n, 'rate': round(x / n, 4) if n else None,
            'value': f'{count(x)} of {n}', 'interval': lo_hi, 'interval_kind': 'Wilson 95%' if lo_hi else None,
            'dataset': dataset, 'sample': sample, 'date': date, 'tags': tags or [], 'note': note, 'source': source}


def file_source(paths: list[str], commit: str, command: str | None = None, **extra) -> dict:
    return {'kind': 'file', 'paths': paths, 'commit': commit, 'command': command, **extra}


def pr_source(base: dict, quote: str) -> dict:
    return {**base, 'quote': quote}


# ---------------------------------------------------------------------------------------------------------------
# measured sections recomputed from the stored datasets

def intake_section(commit: str, today: str) -> dict:
    from evals_dev.intake_facts import score
    r = score.score()
    src = file_source(['evals_dev/intake_facts/gold.json', 'evals_dev/cases/', 'evals_dev/intake_facts/score.py'], commit,
                      'python -m evals_dev.intake_facts.score', pr=54)
    tags = ['in-sample', 'model-checked']
    sample = '60 development cases (agent-written)'
    return {
        'id': 'intake',
        'title': 'Reading facts from a description',
        'plain': ('How often the facts Batatis reads from a project description are right (precision) and how many of '
                  'the stated facts it finds (recall).'),
        'status': 'measured',
        'caveats': ['In sample: the labels were written while the rules were written, so these numbers flatter the rules.',
                    'The cases are agent-written and model-checked. No label is human-verified.'],
        'figures': [
            figure('intake.precision', 'Facts read that are right', r['tp'], r['tp'] + r['fp'], dataset='Intake gold labels',
                   sample=sample, date=today, source=src, tags=tags),
            figure('intake.recall', 'Stated facts it found', r['tp'], r['tp'] + r['fn'], dataset='Intake gold labels',
                   sample=sample, date=today, source=src, tags=tags),
            figure('intake.recall_known', 'Stated facts it found, counting only labels from each case’s fact list',
                   r['known_hit'], r['known'], dataset='Intake gold labels', sample=sample, date=today, source=src, tags=tags),
        ],
    }


def engineer_section() -> dict:
    path = 'evals_dev/section_d_flag/metrics.json'
    m = json.loads((ROOT / path).read_text(encoding='utf-8'))
    shipped = m['dev']['rules_plus_unknown']
    commit = git('log', '-1', '--format=%H', '--', path)
    date = m['generated_at'][:10]
    src = file_source([path, 'evals_dev/section_d_flag/RESULTS.md'], commit, measured_at=m['source_commit'])
    tags = ['in-sample', 'model-checked']
    return {
        'id': 'engineer',
        'title': 'Saying when an engineer is needed',
        'plain': ('Whether Batatis’s flag for professional involvement agrees with the labels, and how often it '
                  'says no when the answer is yes (an under-flag).'),
        'status': 'measured',
        'caveats': [f'It never answers no on these text-only cases. It answers yes or asks, so zero under-flags holds by '
                    f'construction, and {shipped["unknown"]} of {shipped["scored"]} cases are sent to the applicant as a question.',
                    'Labels are model-written, not checked by an engineer.'],
        'figures': [
            figure('engineer.agreement', 'Agrees with the label', shipped['matched'], shipped['scored'],
                   dataset='Engineer-needed labels', sample='60 development cases', date=date, source=src, tags=tags),
            figure('engineer.under_flag', 'Said no when the label was yes', shipped['under_flag'], shipped['scored'],
                   dataset='Engineer-needed labels', sample='60 development cases', date=date, source=src, tags=tags),
        ],
    }


def _prompts(name: str) -> list[dict]:
    return json.loads((ROOT / 'evals_dev' / 'boundary' / name).read_text(encoding='utf-8'))['prompts']


def _dev_cases() -> list[dict]:
    return [json.loads(p.read_text(encoding='utf-8')) for p in sorted((ROOT / 'evals_dev' / 'cases').glob('dev-*.json'))]


DEV_REGIMES = {'dev-024': 'plumbing', 'dev-025': 'electrical', 'dev-059': 'gas', 'dev-060': 'private_sewage'}


def scope_section(commit: str, today: str) -> dict:
    from engine.intake.scope import classify
    cases = _dev_cases()
    redirects = [c for c in cases if c['gold']['intake_action'] == 'redirect']
    in_scope = [c for c in cases if c['gold']['intake_action'] != 'redirect']
    # The regime each development redirect belongs to, as in engine/tests/test_intake_plan.py (gold names the route, not the id).
    want = {c['id']: DEV_REGIMES.get(c['id']) for c in redirects}
    hits = 0
    for c in redirects:
        got = classify(c['description'])
        regime = got.regime.id if got.regime else None
        hits += regime is not None and (want[c['id']] is None or regime == want[c['id']])
    false_dev = sum(classify(c['description']).status == 'redirect' for c in in_scope)

    def counts(prompts):
        ok = tot = fal = ins = 0
        for p in prompts:
            got = classify(p['text'])
            regime = got.regime.id if got.regime else None
            if p['expect'] == 'redirect':
                tot += 1
                ok += regime == p['regime']
            else:
                ins += 1
                fal += regime is not None
        return ok, tot, fal, ins

    b_ok, b_tot, b_fal, b_in = counts(_prompts('scope.json'))
    s_ok, s_tot, s_fal, s_in = counts(_prompts('blind_scope.json'))
    dev_src = file_source(['evals_dev/cases/', 'engine/intake/scope.py'], commit, 'pytest engine/tests/test_intake_plan.py -k scope -s', pr=54)
    b_src = file_source(['evals_dev/boundary/scope.json', 'engine/intake/scope.py'], commit, pr=54)
    s_src = file_source(['evals_dev/boundary/blind_scope.json', 'engine/intake/scope.py'], commit, pr=54)
    first = pr_source(PR54, 'Blind set `blind_scope.json` (32 redirects, 32 in-scope; written by a subagent that never saw the code) | '
                            '**16/32 redirects, 2/32 false**')
    return {
        'id': 'scope',
        'title': 'Sending other codes elsewhere',
        'plain': ('Whether Batatis notices a question that belongs to another code (plumbing, fire, energy, electrical, '
                  'gas, private sewage) and redirects it, without redirecting building-code questions.'),
        'status': 'measured',
        'caveats': ['The first blind run is the only out-of-sample result. The rules were then generalised with the blind '
                    'prompts in view, so the later blind-set numbers are no longer blind.',
                    'A fresh blind set is needed for a real estimate. Prompts are agent-written, not human-verified.'],
        'figures': [
            figure('scope.dev_redirects', 'Development cases redirected correctly', hits, len(redirects),
                   dataset='Development cases', sample=f'{len(redirects)} out-of-scope cases', date=today, source=dev_src,
                   tags=['in-sample']),
            figure('scope.dev_false', 'Building-code cases redirected by mistake', false_dev, len(in_scope),
                   dataset='Development cases', sample=f'{len(in_scope)} in-scope cases', date=today, source=dev_src,
                   tags=['in-sample']),
            figure('scope.boundary', 'Boundary prompts redirected correctly', b_ok, b_tot, dataset='Scope boundary set',
                   sample=f'{b_tot} redirect prompts', date=today, source=b_src, tags=['in-sample'],
                   note=f'{b_fal} of {b_in} in-scope boundary prompts redirected by mistake.'),
            figure('scope.blind_first', 'Blind prompts redirected correctly, first contact', 16, 32,
                   dataset='Blind scope set', sample='32 redirect prompts', date=PR54_DATE,
                   source=first, tags=['blind', 'first run'], note='2 of 32 in-scope blind prompts redirected by mistake.'),
            figure('scope.blind_now', 'Blind prompts redirected correctly, after the fixes', s_ok, s_tot,
                   dataset='Blind scope set', sample=f'{s_tot} redirect prompts', date=today, source=s_src,
                   tags=['no longer blind'], note=f'{s_fal} of {s_in} in-scope blind prompts redirected by mistake.'),
        ],
    }


def fork_section(commit: str, today: str) -> dict:
    from engine.intake import service
    from engine.intake.fork import assess
    from engine.models import Case
    blind = [(p['text'], p['label']) for p in _prompts('blind_fork.json')]
    cases = _dev_cases()
    dev = [c['description'] for c in cases if c['gold']['intake_action'] == 'proceed_conditionally']

    def pr(rows, label):
        got = [(assess(t).variance_needed, lab) for t, lab in rows]
        tp = sum(g == label and lab == label for g, lab in got)
        return tp, sum(g == label for g, _ in got), sum(lab == label for _, lab in got)

    l_tp, l_pred, l_gold = pr(blind, 'likely')
    n_tp, n_pred, n_gold = pr(blind, 'not_indicated')
    dev_likely = sum(assess(t).variance_needed == 'likely' for t in dev)

    asked = total = 0
    for c in cases:
        if c['gold']['intake_action'] == 'redirect':
            continue
        sentences = re.split(r'(?<=[.?!])\s+', c['description'])
        variants = [' '.join(s for s in sentences if not re.search(r'\d|storey|area', s, re.I)) or 'We need a variance.']
        if c['gold']['intake_action'] == 'ask':
            variants.append(c['description'])
        for text in variants:
            case = Case()
            service.apply(case, text, service.run(text, []))
            plan = case.intake.plan
            total += 1
            asked += any(q.priority == 'critical' for q in plan.questions) or plan.fork.variance_needed == 'unknown'

    b_src = file_source(['evals_dev/boundary/blind_fork.json', 'engine/intake/fork.py'], commit, pr=54)
    d_src = file_source(['evals_dev/cases/', 'engine/intake/fork.py'], commit, pr=54)
    a_src = file_source(['evals_dev/cases/', 'engine/intake/plan.py', 'engine/intake/questions.py'], commit,
                        'pytest engine/tests/test_intake_plan.py -k asks_or_abstains -s', pr=54)
    first = pr_source(PR54, 'Fork, `blind_fork.json` (45 labelled) | **likely 4/4 precision, 4/15 recall; not_indicated 7/8, 7/15**')
    first_dev = pr_source(PR54, 'Fork, 38 dev `proceed_conditionally` cases (`likely`) | 20/38')
    nb = ['no longer blind']
    return {
        'id': 'fork',
        'title': 'Saying early whether a variance is likely needed',
        'plain': ('From the description alone, whether the project likely departs from an acceptable solution (so a '
                  'variance is likely needed), shows no departure, or is unclear and needs a question.'),
        'status': 'measured',
        'caveats': ['As with scope, only the first blind run is out of sample; the rules were generalised with those prompts in view.',
                    'Precision is how often the label Batatis gives is right; recall is how many cases with that label it finds.'],
        'figures': [
            figure('fork.blind_first_likely_recall', 'Blind prompts labelled likely that it found, first contact', 4, 15,
                   dataset='Blind fork set', sample='15 prompts labelled likely', date=PR54_DATE, source=first,
                   tags=['blind', 'first run'], note='Precision 4 of 4. Not indicated: precision 7 of 8, recall 7 of 15.'),
            figure('fork.blind_likely_precision', 'Likely, when Batatis says it', l_tp, l_pred, dataset='Blind fork set',
                   sample=f'{l_pred} prompts it labelled likely', date=today, source=b_src, tags=nb),
            figure('fork.blind_likely_recall', 'Blind prompts labelled likely that it found', l_tp, l_gold, dataset='Blind fork set',
                   sample=f'{l_gold} prompts labelled likely', date=today, source=b_src, tags=nb),
            figure('fork.blind_not_indicated_precision', 'Not indicated, when Batatis says it', n_tp, n_pred,
                   dataset='Blind fork set', sample=f'{n_pred} prompts it labelled not indicated', date=today, source=b_src, tags=nb),
            figure('fork.blind_not_indicated_recall', 'Blind prompts labelled not indicated that it found', n_tp, n_gold,
                   dataset='Blind fork set', sample=f'{n_gold} prompts labelled not indicated', date=today, source=b_src, tags=nb),
            figure('fork.dev_first', 'Development cases that need a variance, flagged likely, first run', 20, 38,
                   dataset='Development cases', sample='38 cases that proceed conditionally', date=PR54_DATE, source=first_dev,
                   tags=['first run']),
            figure('fork.dev_now', 'Development cases that need a variance, flagged likely', dev_likely, len(dev),
                   dataset='Development cases', sample=f'{len(dev)} cases that proceed conditionally', date=today, source=d_src,
                   tags=['in-sample']),
            figure('fork.asks', 'Descriptions missing key facts that get a critical question or an unclear answer', asked, total,
                   dataset='Development cases with facts removed, plus the cases whose answer is to ask', sample=f'{total} descriptions',
                   date=today, source=a_src, tags=['in-sample']),
        ],
    }


def rules_section(commit: str, today: str) -> dict:
    from engine.rules import evaluate, golden, load_rule
    vectors = json.loads((ROOT / 'evals_dev' / 'rules' / 'vectors.json').read_text(encoding='utf-8'))['vectors']
    ok = 0
    for v in vectors:
        r = evaluate(load_rule(v['rule']), v['inputs'])
        got = {'state': r['state'], 'outcome_id': r['outcome_id'], 'provision': r['provision']['id'],
               'missing': [m['field'] for m in r['missing']]}
        if 'assumptions' in v['expect']:
            got['assumptions'] = len(r['assumptions'])
        ok += got == v['expect']
    current = golden.OUTPUTS.read_text(encoding='utf-8') == golden.text()
    rule_files = sorted(p for p in (ROOT / 'engine' / 'data' / 'rules').glob('*.json') if p.name != 'index.json')
    unreviewed = sum(1 for p in rule_files if json.loads(p.read_text(encoding='utf-8')).get('reviewed') is not True)
    vec_unreviewed = sum(1 for v in vectors if v.get('reviewed') is not True)
    src = file_source(['evals_dev/rules/vectors.json', 'evals_dev/rules/outputs.json', 'engine/rules/'], commit,
                      'pytest engine/tests/test_rules_vectors.py; npm run test:rules', pr=63)
    return {
        'id': 'rules',
        'title': 'Coded rules',
        'plain': ('For five provisions applicants often vary, Batatis compares the applicant’s numbers with the '
                  'acceptable solution and says whether the design follows or departs from it. Each rule is checked '
                  'against vectors set by hand from the code text.'),
        'status': 'measured',
        'caveats': [f'Unreviewed: {unreviewed} of {len(rule_files)} rules and {vec_unreviewed} of {len(vectors)} vectors are not yet '
                    'signed by a domain reviewer (evals_dev/rules/REVIEW.md).',
                    'The vectors test the rules as coded. They do not show that a reading of the code is the right one.',
                    'The browser evaluator is checked against the server’s output for every vector'
                    + ('' if current else ' (the stored outputs are out of date at this commit)') + '.'],
        'figures': [
            figure('rules.vectors', 'Hand-set vectors where the server evaluator gives the expected result', ok, len(vectors),
                   dataset='Coded-rule vectors', sample=f'{len(vectors)} vectors over {len(rule_files)} rules', date=today,
                   source=src, tags=['unreviewed'], interval=False),
        ],
    }


G3_LABELS = {'a-manufacturer-nailbase-sheathing': 'Manufacturer, nail-base sheathing (demo)',
             'b-contractor-firestop-nonconformance': 'Contractor, firestop (demo)',
             'c-homebuilder-infill-house': 'Homebuilder, infill house (demo)',
             'sample-btrboard': 'BTRboard sample'}


def g3_section(run_gate: bool, commit: str, today: str) -> dict:
    lines, ran = None, False
    form = os.environ.get('BATATIS_SCC_FORM')
    if run_gate and form and Path(form).exists():
        run = subprocess.run([sys.executable, 'scripts/gate_g3.py'], cwd=ROOT, capture_output=True, text=True)
        lines, ran = run.stdout.splitlines(), True
    figures = []
    if ran and lines is not None:
        src = file_source(['scripts/gate_g3.py', 'evals/demo-cases/export/'], commit, 'python scripts/gate_g3.py', pr=60)
        date = today
        rows = [re.match(r'\s*(\S+): (\d+) filled \+ (\d+) N/A of 50', ln) for ln in lines]
        cases = [(m.group(1), int(m.group(2)), int(m.group(3))) for m in rows if m]
        checks = [ln for ln in lines if re.match(r'\s*\[(PASS|FAIL)\]', ln)]
        passed = sum('[PASS]' in ln for ln in checks)
        n_checks = len(checks)
    else:
        src = pr_source(PR60, G3_RECORDED['quote'])
        date = PR60_DATE
        cases = G3_RECORDED['cases']
        passed = n_checks = len(G3_RECORDED['checks'])
    figures.append(figure('g3.checks', 'Gate checks passed', passed, n_checks, dataset='Export gate G3',
                          sample=f'{len(cases)} example applications', date=date, source=src, interval=False,
                          tags=['example data']))
    for name, filled, na in cases:
        label = G3_LABELS.get(name, name.replace('-', ' '))
        figures.append(figure(f'g3.case.{len(figures)}', f'{label}: fields filled or marked N/A by the applicant', filled + na, 50,
                              dataset='Export gate G3', sample='50 applicant fields', date=date, source=src, interval=False,
                              tags=['example data'], note=f'{filled} filled, {na} N/A with the applicant’s reason.'))
    return {
        'id': 'export',
        'title': 'The official form export',
        'plain': ('Whether the three demo applications and one sample export cleanly to the official SCC form: every '
                  'applicant field filled or marked N/A by the applicant, zero citation errors, and no compliance wording.'),
        'status': 'measured',
        'caveats': ['These are fictional example applications. They show the export works end to end, not that a real '
                    'application is accurate.'],
        'figures': figures,
    }


# ---------------------------------------------------------------------------------------------------------------
# code identification, from the benchmark rows

ARMS = {
    'R0-bm25': ('keyword', 'Keyword search (the floor)'),
    'R1-searchrank-v3': ('keyword-structured', 'Keyword search with code-structure ranking'),
    'R2-precedent-lofo': ('precedent', 'Precedent matcher'),
    'R4-jev-screen': ('screen', 'The relevance model screens all 2,080 articles'),
    'R5-jev-screen-rerank60': ('screen-rerank', 'Screen, then the relevance model re-ranks the top 60'),
    'R6-bm25-jev-rerank60': ('keyword-rerank', 'Keyword search, then the relevance model re-ranks the top 60'),
    'F1-rrf-R5-R1-R2': ('fusion', 'A blend of the screen-and-re-rank, structured keyword and precedent rankings'),
    'A9-bm25-luna-rerank60': ('keyword-verifier-rerank', 'Keyword search, then the verification model re-ranks the top 60'),
    'V15f-R5': ('product', 'Screen and re-rank, then the verification model reads the top 15 in full and quotes'),
    'V40f-R5': ('product-40', 'As the product pipeline, but the verification model reads the top 40'),
    'V15c-R5': ('product-short', 'As the product pipeline, but the verification model reads the first 700 characters'),
    'V15f-R6': ('keyword-rerank-verify', 'Keyword search and re-rank, then the verification model reads the top 15'),
    'V15f-F1': ('fusion-verify', 'The blend, then the verification model reads the top 15'),
    'V15f-R5-ool': ('product-open', 'As the product pipeline, but the verification model may name an article outside the list'),
}
PRODUCT = 'V15f-R5'
SCREEN_RERANK = 'R5-jev-screen-rerank60'
FLOOR = 'R0-bm25'
GROUP_LABEL = {'part9': 'Part 9', 'other': 'Other Parts', 'mixed': 'Mixed'}


def note_text(row: dict) -> str:
    """The decision rule's notes for a pipeline, in plain words."""
    out = []
    for n in row.get('notes') or []:
        if n.startswith('incomplete'):
            out.append('rows missing')
        elif 'H2_errors' in n:
            out.append('too many failed runs (limit 2%)')
        elif 'H1_no_fabricated' in n:
            out.append('showed a fabricated citation')
        elif 'H2_p95' in n:
            out.append('too slow (limit 20 s)')
    if not out and row.get('p_worse') is not None:
        out.append('tied with the best; the rule prefers a cheaper one' if row.get('tied') else 'not tied with the best')
    return '; '.join(dict.fromkeys(out)) or '-'


def neutral(arm: str) -> tuple[str, str]:
    if arm in ARMS:
        return ARMS[arm]
    key = PROVIDER_NAMES.sub('model', arm).lower()
    return key, f'Pipeline {key}'


def bench_tree(ref: str | None) -> tuple[Path | None, str | None, str | None, tempfile.TemporaryDirectory | None]:
    """The benchmark tree, its commit, and how it was found. A git ref is extracted to a temporary directory."""
    if ref:
        commit = git('rev-parse', f'{ref}^{{commit}}')
        tmp = tempfile.TemporaryDirectory(prefix='batatis-bench-')
        data = subprocess.run(['git', 'archive', commit], cwd=ROOT, capture_output=True, check=True).stdout
        with tarfile.open(fileobj=BytesIO(data)) as tar:
            tar.extractall(tmp.name, filter='data')
        build = ROOT / 'codedb' / 'build'
        if build.exists() and not (Path(tmp.name) / 'codedb' / 'build').exists():
            (Path(tmp.name) / 'codedb' / 'build').symlink_to(build.resolve())
        remote = subprocess.run(['git', 'show-ref', '--verify', '--quiet', f'refs/remotes/{ref}'], cwd=ROOT).returncode == 0
        label = f'branch {ref.split("/", 1)[1]}' if remote and '/' in ref else ref
        return Path(tmp.name), commit, label, tmp
    if (ROOT / BENCH / 'results').is_dir():
        return ROOT, git('log', '-1', '--format=%H', '--', f'{BENCH}/results'), 'this checkout', None
    return None, None, None, None


def code_id_section(ref: str | None) -> dict:
    base = {
        'id': 'code-id',
        'title': 'Finding the code articles that apply',
        'plain': ('Whether the article an applicant needs is the one Batatis shows first (Part 9), or among the three '
                  'quoted choices it offers (other Parts and mixed cases).'),
    }
    root, commit, where, tmp = bench_tree(ref)
    if root is None:
        return {**base, 'status': 'not_run', 'figures': [], 'detail': [],
                'caveats': ['The benchmark result rows are not on this branch (draft PR #58). Run the builder with '
                            '--bench-ref to read them, or after the benchmark merges.']}
    try:
        run = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'accuracy_codeid_probe.py'), str(root)], cwd=root,
                             capture_output=True, text=True, env={**os.environ, 'PYTHONPATH': str(root)})
        if run.returncode != 0:
            raise ReportError('the benchmark probe failed:\n' + run.stderr[-3000:])
        p = json.loads(run.stdout)
    finally:
        if tmp is not None:
            tmp.cleanup()
    return {**base, **code_id_from_probe(p, commit, where)}


def code_id_from_probe(p: dict, commit: str, where: str) -> dict:
    sel, dev, pub = p['selection'], p['development'], p['public53']
    if PRODUCT not in sel:
        return {'status': 'not_run', 'figures': [], 'detail': [], 'caveats': ['The product pipeline has no stored rows yet.']}
    first, last = (p['rows']['first'] or '')[:10], (p['rows']['last'] or '')[:10]
    date = first if first == last else f'{first} to {last}'
    pr = 58 if where != 'this checkout' else None

    digests = {f['arm']: f['sha256'] for f in p['row_files']}

    def src(arms: list[str]) -> dict:
        # Row files are named after internal arm ids, some of which name a provider; cite the folder and the files'
        # digests under their neutral names instead.
        files = [{'pipeline': neutral(a)[0], 'sha256_16': digests.get(a)} for a in arms]
        return file_source([f'{BENCH}/results/'], commit, 'python -m evals_dev.identify_bench decision', pr=pr,
                           ref=where if where != 'this checkout' else None, row_files=files)

    c = p['cases']
    n_sel = c['selection_gold']
    groups = c['selection_by_group']
    sel_sample = (f'{n_sel} cases with known answers ({groups.get("part9", 0)} Part 9, {groups.get("other", 0)} other Parts, '
                  f'{groups.get("mixed", 0)} mixed)')
    sel_dataset = 'Public Alberta precedents (53) and interpretation requests (26), the selection folds'
    d = p['decision'] or {}
    winner, provisional = d.get('winner'), d.get('provisional')
    prod = sel[PRODUCT]
    screen_draws = sel.get(SCREEN_RERANK, {}).get('repeats', 0)
    g1 = {g['id']: g['status'] for g in p['g1']}
    latency_run = g1.get('G1.5') == 'PASS'
    status = 'measured' if winner and latency_run and screen_draws >= 3 else 'provisional'

    def draws(e: dict, arm: str) -> str:
        if p['kinds'].get(arm) == 'verify':
            return f'{e["repeats"]} verifier runs over {screen_draws} relevance draws'
        return f'{e["repeats"]} draw{"s" if e["repeats"] != 1 else ""}'

    def short_runs(e: dict, arm: str) -> str:
        if p['kinds'].get(arm) == 'verify':
            return f'{e["repeats"]} runs, {screen_draws} draws'
        return f'{e["repeats"]} run{"s" if e["repeats"] != 1 else ""}'

    def fig(fid, label, arm, e, *, dataset, sample, tags, note=None):
        s = e['success']
        return figure(fid, label, s['x'], s['n'], dataset=dataset, sample=sample, date=date, source=src(chain(arm)),
                      tags=tags, note=note)

    def chain(arm: str) -> list[str]:
        return list(reversed(p.get('chains', {}).get(arm) or [arm]))

    tags = ['provisional'] if status == 'provisional' else []
    figures = [
        fig('codeid.product', 'Right article shown (product pipeline)', PRODUCT, prod, dataset=sel_dataset, sample=sel_sample,
            tags=tags + ['selection folds'], note=f'{draws(prod, PRODUCT)}. A case that succeeded in some runs only counts as a fraction.'),
    ]
    if FLOOR in sel:
        figures.append(fig('codeid.floor', 'Right article shown (keyword search, for comparison)', FLOOR, sel[FLOOR],
                           dataset=sel_dataset, sample=sel_sample, tags=['selection folds'], note='Deterministic: one run.'))
    if PRODUCT in dev:
        e = dev[PRODUCT]
        figures.append(fig('codeid.product_dev', 'Right article shown on development cases (not used to choose)', PRODUCT, e,
                           dataset='Development cases with known answers (calibration and validation folds)',
                           sample=f'{e["cases"]} cases', tags=tags + ['development folds'],
                           note=f'{draws(e, PRODUCT)}. Agent-written cases.'))
    if SCREEN_RERANK in pub and FLOOR in pub:
        r5, r0 = pub[SCREEN_RERANK]['ranking'], pub[FLOOR]['ranking']
        n = pub[SCREEN_RERANK]['cases']
        figures.append(figure('codeid.public_top1', 'Relevance stage puts a cited article first', r5['hit@1']['mean'] * n, n,
                              dataset='Public Alberta precedents', sample=f'{n} cases', date=date, source=src([SCREEN_RERANK, FLOOR]),
                              tags=tags + ['relevance stage only'],
                              note=f'Mean of {pub[SCREEN_RERANK]["repeats"]} draws. Keyword search: {r0["hit@1"]["mean"] * 100:.1f}%.'))
        figures.append(figure('codeid.public_top5', 'Relevance stage puts a cited article in the first five', r5['hit@5']['mean'] * n, n,
                              dataset='Public Alberta precedents', sample=f'{n} cases', date=date, source=src([SCREEN_RERANK, FLOOR]),
                              tags=tags + ['relevance stage only'],
                              note=f'Mean of {pub[SCREEN_RERANK]["repeats"]} draws. Keyword search: {r0["hit@5"]["mean"] * 100:.1f}%.'))
    fab = prod.get('fabricated_citations_shown') if p.get('integrity_rechecked') else None
    if fab is not None:
        shown = prod['errors']['rows']
        figures.append(figure('codeid.fabricated', 'Stored product runs that would show a citation not in the code database', fab, shown,
                              dataset=sel_dataset, sample=f'{shown} stored runs, rechecked against the code database', date=date,
                              source=src([PRODUCT]), tags=['selection folds']))

    # pipeline table, in the decision rule's order
    order = [r['arm'] for r in d.get('rows', [])] or list(sel)
    by_arm = {r['arm']: r for r in d.get('rows', [])}
    table = []
    for arm in order:
        e = sel[arm]
        s = e['success']
        key, label = neutral(arm)
        r = by_arm.get(arm, {})
        lo, hi = s['wilson_95']
        table.append([label, f'{count(s["x"])} of {s["n"]}', f'{s["rate"] * 100:.1f}% ({lo * 100:.1f}–{hi * 100:.1f})',
                      short_runs(e, arm), '-' if e['usd_per_case_run'] is None else f'US${e["usd_per_case_run"]:.4f}',
                      'chosen' if arm == winner else ('carried as provisional' if arm == provisional else note_text(r))])
    by_group = []
    for arm in [PRODUCT, SCREEN_RERANK, FLOOR]:
        if arm in sel:
            e = sel[arm]
            by_group.append([neutral(arm)[1]] + [
                (lambda g: '-' if not g else f'{count(g["x"])} of {g["n"]}')(e['by_group'].get(k)) for k in ('part9', 'other', 'mixed')])
    g1_rows = []
    mrr = p.get('rerank_mrr_public53') or []
    if mrr:
        g1_rows.append(['Re-rank mean reciprocal rank on 53 public precedents, at least 0.70',
                        f'{sum(mrr) / len(mrr):.3f} over {len(mrr)} draws (lowest {min(mrr):.3f})', g1.get('G1.1', 'not run').lower()])
    g1_rows.append(['Verification model top-1 by Part, with intervals, over at least 5 runs', f'{prod["repeats"]} runs', g1.get('G1.2', 'not run').lower()])
    g1_rows.append(['Cost per case run, all stages',
                    '-' if prod['usd_per_case_run'] is None else f'US${prod["usd_per_case_run"]:.4f}', g1.get('G1.3', 'not run').lower()])
    g1_rows.append(['Verification stage latency, one request at a time', 'not measured', g1.get('G1.4', 'not run').lower()])
    g1_rows.append(['End-to-end latency, one case at a time', 'not measured', g1.get('G1.5', 'not run').lower()])
    g1_rows.append(['Fabricated citations shown', 'not rechecked' if fab is None else str(fab), g1.get('G1.6', 'not run').lower()])
    parts = []
    for label, v in sorted((p.get('top1_by_part') or {}).get(PRODUCT, {}).items()):
        lo, hi = v['rate']['wilson_95']
        parts.append([label[:1].upper() + label[1:], f'{v["rate"]["label"]}', f'{lo * 100:.1f}–{hi * 100:.1f}%'])

    rob = (by_arm.get(provisional or winner or '', {}) or {}).get('robust') or {}
    if winner:
        verdict = (f'The decision rule chose the product pipeline ({neutral(winner)[1].lower()}).' if winner == PRODUCT
                   else f'The decision rule chose {neutral(winner)[1].lower()}, not the product pipeline.')
    elif provisional:
        why = ''
        if rob.get('agreement_ok') is False and rob.get('top1_agreement') is not None:
            why = (f' It fails one robustness condition: two runs on the same case agree on the first article '
                   f'{rob["top1_agreement"] * 100:.1f}% of the time, under the required {d.get("agreement_min", 0.9) * 100:.0f}%.')
        carried = 'the product pipeline' if provisional == PRODUCT else neutral(provisional)[1].lower()
        verdict = (f'The decision rule carries {carried} as provisional, not as a winner: it is tied with the best '
                   f'and the cheapest of those tied.{why} The choice needs a person.')
    else:
        verdict = 'No pipeline met the decision rule yet.'

    caveats = []
    if status == 'provisional':
        caveats.append(f'Provisional: {screen_draws} complete relevance draws per case on {c["total"]} cases; the plan asks for '
                       'more draws, and the latency pass has not run.')
    caveats += [verdict,
                'The selection folds were used to choose the pipeline, so its number there is the best of several and flatters it. '
                'The development folds were not used to choose.',
                'No committed-pick precision exists: the commit rule is uncalibrated, so Batatis commits nothing on its own.',
                'The held-out test split has not been run. It runs once, after the commit rule is fitted.',
                'Answer lists for public precedents can be incomplete, so a right answer can be scored as a miss.']

    detail = [
        {'title': 'Every pipeline the benchmark compared (selection folds)',
         'header': ['Pipeline', 'Right article', 'Rate (Wilson 95%)', 'Runs', 'Cost per case run', 'Decision'],
         'rows': table},
        {'title': 'By Part group (selection folds)', 'header': ['Pipeline', 'Part 9', 'Other Parts', 'Mixed'], 'rows': by_group},
        {'title': 'Verification model: first article right, by Part (all cases with known answers)',
         'header': ['Part', 'Right', 'Wilson 95%'], 'rows': parts},
        {'title': 'Gate G1 checks', 'header': ['Check', 'Value', 'Status'], 'rows': g1_rows},
    ]
    return {'status': status, 'figures': figures, 'detail': detail, 'caveats': caveats,
            'definition': ('A Part 9 case succeeds when the first article shown is a right one; any other case when a right '
                           'article is among the three quoted choices. Each case scores the share of its runs that succeed.'),
            'rows': {'live_rows': p['rows']['live'], 'first': p['rows']['first'], 'last': p['rows']['last'],
                     'files': [{'pipeline': neutral(f['arm'])[0], 'rows': f['rows'], 'sha256_16': f['sha256']}
                               for f in p['row_files'] if f['arm'] in ARMS]},
            'updates_when': ('The benchmark finishes: more relevance draws, the latency pass, then the decision memo. '
                             'Re-run python scripts/accuracy_report.py and this section updates with no code change.')}


NOT_MEASURED = [
    {'title': 'A held-out result', 'why': 'The held-out test split runs once, after the commit rule is fitted. It has not run.'},
    {'title': 'How often a committed article is right', 'why': 'The commit rule is uncalibrated, so Batatis commits nothing on its own and there is nothing to count.'},
    {'title': 'Latency of code identification', 'why': 'The one-case-at-a-time timing pass needs account credit and has not run.'},
    {'title': 'Whether the officer review catches planted gaps', 'why': 'The 20-application planted-gap evaluation with a blind author has not run.'},
    {'title': 'Labels a person has checked', 'why': 'Every label above is model-checked. No human-verified subset exists yet.'},
]


# ---------------------------------------------------------------------------------------------------------------
# guaranteed claims: the tests must exist (and pass, with --verify)

def _py_test_exists(path: Path, name: str) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except (OSError, SyntaxError):
        return False
    return any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name for n in ast.walk(tree))


def _ts_test_exists(path: Path, name: str) -> bool:
    try:
        text = path.read_text(encoding='utf-8')
    except OSError:
        return False
    return any(m.group(2) == name for m in re.finditer(r'\btest\((["\'`])(.*?)\1', text))


def test_ref(test_id: str) -> dict:
    path, _, name = test_id.partition('::')
    runner = 'node' if path.endswith('.ts') else 'pytest'
    return {'id': test_id, 'file': path, 'name': name, 'runner': runner}


def check_tests(claims: list[dict]) -> list[str]:
    problems = []
    for c in claims:
        if not c.get('tests'):
            problems.append(f'guaranteed claim {c["id"]} names no test')
        for t in c.get('tests', []):
            ref = test_ref(t if isinstance(t, str) else t['id'])
            path = ROOT / ref['file']
            ok = _ts_test_exists(path, ref['name']) if ref['runner'] == 'node' else _py_test_exists(path, ref['name'])
            if not ok:
                problems.append(f'guaranteed claim {c["id"]}: test not found: {ref["id"]}')
    return problems


def verify_tests(claims: list[dict]) -> dict:
    """Run every named test. pytest results come from its junit file; node tests run per file with a name pattern."""
    ids = sorted({t for c in claims for t in c['tests']})
    py = [t for t in ids if not t.split('::')[0].endswith('.ts')]
    ts = [t for t in ids if t.split('::')[0].endswith('.ts')]
    results: dict[str, str] = {}
    with tempfile.TemporaryDirectory() as tmp:
        junit = Path(tmp) / 'junit.xml'
        subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', f'--junitxml={junit}', *py],
                       cwd=ROOT, capture_output=True, text=True)
        import xml.etree.ElementTree as ET
        for case in ET.parse(junit).getroot().iter('testcase'):
            name = case.get('name', '').split('[')[0]
            cls = case.get('classname', '')
            path = cls.replace('.', '/') + '.py'
            key = f'{path}::{name}'
            state = 'failed' if case.find('failure') is not None or case.find('error') is not None else (
                'skipped' if case.find('skipped') is not None else 'passed')
            prev = results.get(key)
            if prev != 'failed':
                results[key] = 'failed' if state == 'failed' else (prev if prev == 'passed' and state == 'skipped' else state)
    for t in ts:
        file, name = t.split('::', 1)
        run = subprocess.run(['node', '--experimental-strip-types', '--no-warnings', '--import', './scripts/register-ts.mjs',
                              '--test', f'--test-name-pattern={re.escape(name)}', file.removeprefix('web/')],
                             cwd=ROOT / 'web', capture_output=True, text=True)
        results[t] = 'passed' if run.returncode == 0 and re.search(r'(?:#|ℹ) pass [1-9]', run.stdout) else 'failed'
    missing = [t for t in ids if t not in results]
    for t in missing:
        results[t] = 'not collected'
    return results


# ---------------------------------------------------------------------------------------------------------------
# build, validate, render

def build(*, bench_ref: str | None, verify: bool, run_gate: bool, today: str | None = None) -> dict:
    sys.path.insert(0, str(ROOT))
    commit, dirty = head_commit()
    today = today or dt.date.today().isoformat()
    problems = check_tests(GUARANTEED)
    if problems:
        raise ReportError('\n'.join(problems))
    results = verify_tests(GUARANTEED) if verify else None
    guaranteed = []
    for c in GUARANTEED:
        tests = [test_ref(t) for t in c['tests']]
        if results:
            for t in tests:
                t['result'] = results.get(t['id'], 'not collected')
        guaranteed.append({'id': c['id'], 'claim': c['claim'], 'detail': c['detail'], 'tests': tests})
    if results:
        bad = [f'{t} ({r})' for t, r in sorted(results.items()) if r != 'passed']
        if bad:   # a skipped or uncollected test enforces nothing
            raise ReportError('a test behind a guaranteed claim did not pass: ' + ', '.join(bad))
    measured = [
        intake_section(commit, today),
        code_id_section(bench_ref),
        scope_section(commit, today),
        fork_section(commit, today),
        engineer_section(),
        rules_section(commit, today),
        g3_section(run_gate, commit, today),
    ]
    report = {
        'schema': SCHEMA,
        'generated_on': today,
        'built_from': {'commit': commit, 'dirty': dirty},
        'edition': EDITION,
        'intro': ('Batatis checks whether a variance application is complete and cites the code. It does not judge '
                  'whether a design is right. This page separates what Batatis guarantees by construction from what we '
                  'measured, with how sure we are.'),
        'guaranteed': guaranteed,
        'verified': None if not results else {
            'date': today, 'commit': commit, 'passed': sum(r == 'passed' for r in results.values()),
            'skipped': sum(r == 'skipped' for r in results.values()), 'total': len(results)},
        'measured': measured,
        'not_measured': NOT_MEASURED,
        'not_claimed': NOT_CLAIMED,
    }
    validate(report)
    return report


def validate(report: dict) -> None:
    """Every figure has a source with a commit; every claim names tests; nothing names a provider."""
    problems = []
    if report.get('schema') != SCHEMA:
        problems.append('wrong schema')
    for c in report.get('guaranteed', []):
        if not c.get('tests'):
            problems.append(f'guaranteed claim {c.get("id")} names no test')
    for s in report.get('measured', []):
        if s.get('status') not in ('measured', 'provisional', 'not_run'):
            problems.append(f'section {s.get("id")}: unknown status {s.get("status")}')
        if s.get('status') != 'not_run' and not s.get('figures'):
            problems.append(f'section {s.get("id")}: measured but has no figures')
        for f in s.get('figures', []):
            where = f'figure {f.get("id")}'
            src = f.get('source') or {}
            if src.get('kind') == 'file':
                if not src.get('paths'):
                    problems.append(f'{where}: file source without a path')
            elif src.get('kind') == 'pr':
                if not isinstance(src.get('pr'), int) or not src.get('quote'):
                    problems.append(f'{where}: PR source without a PR number or the quoted text')
            else:
                problems.append(f'{where}: no source')
            if not HEX.match(str(src.get('commit') or '')):
                problems.append(f'{where}: source without a commit')
            for k in ('dataset', 'sample', 'date', 'label'):
                if not f.get(k):
                    problems.append(f'{where}: no {k}')
            if not isinstance(f.get('n'), int) or f['n'] <= 0:
                problems.append(f'{where}: no sample size')
            if f.get('interval') is not None and not (0 <= f['interval'][0] <= f['interval'][1] <= 1):
                problems.append(f'{where}: bad interval')
    try:
        text = json.dumps(report, ensure_ascii=False, allow_nan=False)
    except ValueError:
        raise ReportError('the report holds a non-finite number (NaN or infinity)') from None
    for m in list(PROVIDER_NAMES.finditer(text))[:5]:
        problems.append(f'provider name in the report: ...{text[max(0, m.start() - 40):m.end() + 40]}...')
    if problems:
        raise ReportError('\n'.join(problems))


def pct(x: float | None) -> str:
    return '-' if x is None else f'{x * 100:.1f}%'


def source_text(src: dict) -> str:
    if src['kind'] == 'pr':
        return f'PR #{src["pr"]} body (merge commit {src["commit"][:7]})'
    where = ', '.join(f'`{p}`' for p in src['paths'])
    extra = f' on {src["ref"]}' if src.get('ref') else ''
    pr = f', PR #{src["pr"]}' if src.get('pr') else ''
    return f'{where} at {src["commit"][:7]}{extra}{pr}'


def render_md(r: dict) -> str:
    out = ['# Batatis accuracy report', '',
           f'Generated by `python scripts/accuracy_report.py` on {r["generated_on"]} from commit `{r["built_from"]["commit"][:7]}`'
           + (' (uncommitted changes)' if r['built_from']['dirty'] else '') + '. Do not edit by hand. '
           'The page at `#/accuracy` reads `report.json` next to this file.', '', r['intro'], '',
           '## What Batatis guarantees', '',
           'True by construction and enforced by tests. The report is built only when every one of these tests passes.', '']
    if r.get('verified'):
        v = r['verified']
        out += [f'Last run of these tests: {v["passed"]} passed, {v["skipped"]} skipped, of {v["total"]}, on {v["date"]} at `{v["commit"][:7]}`.', '']
    for c in r['guaranteed']:
        out += [f'### {c["claim"]}', '', c['detail'], '', 'Enforced by:', '']
        out += [f'- `{t["id"]}`' + (f' ({t["result"]})' if t.get('result') else '') for t in c['tests']] + ['']
    out += ['## What we measured, and how sure we are', '',
            'Each figure is x of n with a 95% Wilson interval where one applies, the dataset, the date and the source.', '']
    for s in r['measured']:
        badge = {'provisional': ' (provisional)', 'not_run': ' (not run)'}.get(s['status'], '')
        out += [f'### {s["title"]}{badge}', '', s['plain'], '']
        if s.get('definition'):
            out += [f'Success: {s["definition"]}', '']
        if s['figures']:
            out += ['| Figure | Value | 95% interval | Dataset and sample | Date | Labels | Source |', '|---|---|---|---|---|---|---|']
            for f in s['figures']:
                iv = '-' if not f['interval'] else f'{pct(f["interval"][0])}–{pct(f["interval"][1])}'
                label = f['label'] + (f'. {f["note"]}' if f.get('note') else '')
                out.append(f'| {label} | {f["value"]} ({pct(f["rate"])}) | {iv} | {f["dataset"]}; {f["sample"]} | {f["date"]} | '
                           f'{", ".join(f["tags"]) or "-"} | {source_text(f["source"])} |')
            out.append('')
        out += [f'- {c}' for c in s.get('caveats', [])] + ['']
        for t in s.get('detail', []):
            if not t['rows']:
                continue
            out += [f'#### {t["title"]}', '', '| ' + ' | '.join(t['header']) + ' |', '|' + '---|' * len(t['header'])]
            out += ['| ' + ' | '.join(row) + ' |' for row in t['rows']] + ['']
        if s.get('updates_when'):
            out += [f'Updates when: {s["updates_when"]}', '']
    out += ['## Not measured yet', ''] + [f'- **{n["title"]}.** {n["why"]}' for n in r['not_measured']] + ['']
    out += ['## Claims left out', '', 'Considered for the guaranteed list and left out because no test enforces them as worded.', '']
    out += [f'- {n["claim"]} {n["why"]}' for n in r['not_claimed']] + ['']
    return '\n'.join(out)


def dump(report: dict) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False, sort_keys=False, allow_nan=False) + '\n'


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--bench-ref', help='git ref holding evals_dev/identify_bench (for example the fetched PR #58 branch)')
    ap.add_argument('--no-verify', dest='verify', action='store_false',
                    help='skip running the tests a guaranteed claim names (drafts only; the committed report is verified)')
    ap.add_argument('--run-gate', action='store_true', help='re-run gate G3 (needs BATATIS_SCC_FORM)')
    ap.add_argument('--date', help='measurement date to record (default today)')
    args = ap.parse_args(argv)
    try:
        report = build(bench_ref=args.bench_ref, verify=args.verify, run_gate=args.run_gate, today=args.date)
    except ReportError as e:
        print(f'accuracy report: {e}', file=sys.stderr)
        return 1
    # Only a verified build replaces the published report; a --no-verify draft goes to a temp folder.
    out_json, out_md = (OUT_JSON, OUT_MD) if args.verify else _draft_paths()
    out_json.parent.mkdir(parents=True, exist_ok=True)
    _publish({out_json: dump(report), out_md: render_md(report)})
    shown = (lambda p: p.relative_to(ROOT)) if args.verify else (lambda p: p)
    print(f'wrote {"" if args.verify else "draft (unverified) "}{shown(out_json)} and {shown(out_md)}')
    return 0


def _publish(files: dict) -> None:
    """Publish the files together. Everything is rendered and written to unique temp files first; if a replacement
    fails, files already replaced are restored from their backups. A crash between two replacements can still leave
    a mismatched pair until the next run, which is why `--verify` rebuilds both every time."""
    import shutil
    import tempfile
    staged, backups, replaced = {}, {}, []
    try:
        for path, text in files.items():
            fd, tmp = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent)
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                handle.write(text)
            staged[path] = Path(tmp)
            if path.exists():
                fd, bak = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.bak', dir=path.parent)
                os.close(fd)
                shutil.copy2(path, bak)
                backups[path] = Path(bak)
        try:
            for path, tmp in staged.items():
                os.replace(tmp, path)
                replaced.append(path)
        except BaseException:
            for path in replaced:                     # roll back what was already published
                if path in backups:
                    os.replace(backups.pop(path), path)
                else:
                    path.unlink(missing_ok=True)
            raise
    finally:
        for leftover in [*staged.values(), *backups.values()]:
            if leftover.exists():
                leftover.unlink()


def _draft_paths() -> tuple[Path, Path]:
    """A new private folder per run (mkdtemp: unique name, mode 0700), never a fixed path another user could pre-plant."""
    import tempfile
    folder = Path(tempfile.mkdtemp(prefix='batatis-accuracy-draft-'))
    return folder / 'report.json', folder / 'report.md'


if __name__ == '__main__':
    raise SystemExit(main())
