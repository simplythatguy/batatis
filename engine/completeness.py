"""Administrative pre-flight: deterministic planted classes D01–D13 and D16.

D09/D10 cover empty fields only. Generic/unrelated narratives, attachment contradictions
(D14), relevance (D15), engineering adequacy and licence authenticity require human judgement.
Supporting-document metadata follows section_d.supporting_documents; no PDF is interpreted here.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from codedb import validate_text

from .codes import Codes
from .jurisdictions import notices_for
from .models import INTENT_LABEL, Case, Gap as CaseGap
from .not_applicable import not_applicable, problems as not_applicable_problems
from .process_fields import confirmed_value, latest_fact, process_fields
from .professional import (
    OFFICER_PROFESSIONAL_GAP, PRESCRIPTIVE_CONTRADICTION, ProfessionalResult,
    authentication_metadata_usable, professional_authentication_confirmed, professional_confirmed,
    professional_involvement, unresolved_item,
)
from .section_c import section_c_rows
from .section_d import SupportingDocument, section_d_plan, supporting_documents


class Gap(CaseGap):
    fix_hint: str
    citation: str | None = None


_PLACEHOLDERS = {'tbd', 'tobedetermined', 'tobeprovided', 'unknown', 'pending', 'na', 'notprovided', 'placeholder'}
_HISTORICAL = re.compile(r'\b(?:historical|history|superseded|not current|earlier edition)\b', re.I)
_PID = re.compile(r'\d+(?:\.\d+){3}\.(?:\(\d+\)(?:\([a-z]+\))?)?')


def _missing(value) -> bool:
    return (not isinstance(value, str) or not value.strip()
            or re.sub(r'\W', '', value.casefold()) in _PLACEHOLDERS)


def _pairs(row):
    return sorted((p.function, p.objective, p.bracket, tuple(p.clauses), p.application_note or '',
                   p.table, p.pdf_page, p.function_text or '', p.objective_text or '') for p in row.pairs)


@lru_cache(maxsize=1)
def _edition_crosswalks() -> tuple[dict, ...]:
    path = Path(__file__).resolve().parents[1] / 'research/precedents/index.json'
    if not path.exists():
        return ()
    rows = json.loads(path.read_text(encoding='utf-8'))
    return tuple(a for precedent in rows if re.search(r'\b(?:2014|2019)\b', precedent.get('code_edition', ''))
                 for a in precedent.get('articles_varied', [])
                 if a.get('original_division') == 'B' and a.get('ae2023_provision')
                 and 'successor' in a.get('status', ''))


def professional_involvement_gaps(case: Case, codes: Codes, process, *,
                                  professional: ProfessionalResult | None = None,
                                  documents: list[SupportingDocument] | None = None) -> list[Gap]:
    """Administrative professional gap. An alternative case does not clear by a prescriptive Yes."""
    gaps: list[Gap] = []

    def add(rule, section, field, missing, fix_hint, citation=None, severity='blocking'):
        gaps.append(Gap(id=f'{rule}:{field}', severity=severity, section=section, field=field,
                        message=f'Your application appears to be missing {missing}', fix_hint=fix_hint, citation=citation))

    professional = professional or professional_involvement(case, codes)
    if professional.prescriptive_contradiction:
        gaps.append(Gap(
            id='professional:prescriptive_route_confirmed', severity='warning', section='D',
            field='prescriptive_route_confirmed', message=PRESCRIPTIVE_CONTRADICTION,
            fix_hint='Leave the prescriptive answer unset. It does not close professional involvement.',
            citation=None, routed_to='officer'))
    # Source resolution is independent of whether a professional has been engaged.
    for reason in professional.reasons:
        if reason.source_unresolved:
            gaps.append(Gap(
                id=f'professional:source_lookup:{reason.code}', severity='blocking', section='D',
                field='professional_source', message=reason.message, fix_hint=reason.message,
                citation=None, routed_to='officer'))
    # Engagement is not a requirement determination. In particular, not_engaged
    # must never bypass a mandatory duty or let an officer accept an unresolved question.
    required = professional.required == 'yes' or confirmed_value(case, 'engineering_required') in ('yes', True)
    if required:
        citation = next((r.citation for r in professional.reasons if r.required == 'yes'), codes.citation('2.4.1.1.(3)', 'C'))
        if not professional_confirmed(case):
            gaps.append(Gap(
                id='D12:professional_confirmation', severity='blocking', section='D',
                field='professional_confirmation',
                message='Your application appears to be missing an applicant-confirmed registered professional for this scope.',
                fix_hint='Confirm their engineer or architect role and registration number or seal. File metadata alone does not confirm this.',
                citation=citation, routed_to='professional'))
        if _missing(confirmed_value(case, 'professional_name', 'responsible_professional', 'professional.name')):
            add('D12', 'D', 'responsible_professional', 'a named registered professional required for this work.',
                'Ask who takes responsibility, their discipline and scope, and obtain their own authenticated work.', citation)
        qualifications = next((item.answer for item in process if item.id == 'qualifications'), None)
        if qualifications is None and _missing(confirmed_value(case, 'professional.qualifications', 'professional_qualifications')):
            add('D12', 'D', 'professional_qualifications', 'the qualifications of the responsible professional.',
                'Request their qualifications, experience and background; do not draft them.', codes.citation('2.3.1.1.(4)', 'C'))
        docs = supporting_documents(case) if documents is None else documents
        if (not professional_authentication_confirmed(case)
                and not any(seal_is_professional_evidence(doc, quote=_file_quote(case, doc)) for doc in docs)):
            add('D12', 'D', 'professional_authentication', 'authentication information for the required professional work.',
                'Request the responsible professional’s authenticated document; authenticity and scope need human review.',
                codes.citation('2.4.1.1.(5)', 'C'))
    elif professional.involvement == 'professional_involved':
        pass
    elif professional.resolution is not None and not professional.resolution.required:
        pass
    elif professional.applicant_sourced or professional.not_sure_fields:
        gaps.append(Gap(
            id='professional:professional_requirement', severity='blocking', section='D',
            field='professional_requirement', message=OFFICER_PROFESSIONAL_GAP,
            fix_hint='The officer decides whether a registered professional is required. An applicant yes or no does not close this.',
            citation=next((r.citation for r in professional.reasons if r.required == 'depends'), None),
            routed_to='officer', submission_blocking=False))
    elif professional.required == 'depends' or professional.involvement == 'unresolved':
        line = next((reason.message for reason in professional.reasons if reason.required == 'depends'), '')
        if not line:
            what = professional.questions[0] if professional.questions else 'Whether a registered professional is required'
            line = unresolved_item(what, professional.routed_to)
        gaps.append(Gap(
            id='professional:professional_requirement', severity='blocking', section='D',
            field='professional_requirement',
            message=line,
            fix_hint=line,
            citation=next((r.citation for r in professional.reasons if r.required == 'depends'), None),
            routed_to=professional.routed_to, submission_blocking=professional.routed_to != 'officer'))
    return gaps


def _file_quote(case: Case, doc: SupportingDocument) -> str:
    fact = latest_fact(case, f'evidence.{doc.id}.file_ref')
    if fact is None or not isinstance(fact.source.quote, str):
        return ''
    return fact.source.quote


def seal_is_professional_evidence(doc: SupportingDocument, *, quote: str = '') -> bool:
    """A seal string on an unsigned vendor or sales email does not authenticate the work."""
    seal = doc.professional_seal.strip() if isinstance(doc.professional_seal, str) else ''
    if not seal:
        return False
    return authentication_metadata_usable(doc.responsible_party, doc.issuer, doc.title, quote, seal)


def _case_constraints(case: Case, codes: Codes, *,
                       professional: ProfessionalResult | None = None,
                       documents: list[SupportingDocument] | None = None) -> list[Gap]:
    """Return stable, located findings. An empty list is no technical or acceptance determination."""
    gaps: list[Gap] = []

    def add(rule, section, field, missing, fix_hint, citation=None, severity='blocking'):
        gaps.append(Gap(id=f'{rule}:{field}', severity=severity, section=section, field=field,
                        message=f'Your application appears to be missing {missing}', fix_hint=fix_hint, citation=citation))

    for field, missing, hint in not_applicable_problems(case):
        section = next((sec for token, sec in (('section_c', 'C'), ('section_d', 'D'), ('owner', 'A'),
                                                ('representative', 'A')) if token in field), 'B')
        add('not_applicable', section, field, missing, hint)
    if (case.jurisdiction is None or not case.jurisdiction.id.strip()
            or not case.jurisdiction.name.strip()):
        add('admin', 'B', 'jurisdiction', 'the reviewing jurisdiction.', 'Ask which authority will receive the application.')

    try:
        process = process_fields(case, codes)
    except (KeyError, ValueError, OSError):
        process = []
        gaps.append(Gap(id='source:process', section='process', field='process_source',
            message='The Division C documentation source could not be resolved; the source remains uncertain.',
            fix_hint='Restore the source and rerun the review.', routed_to='officer'))
    expected = {}
    for pid in dict.fromkeys(case.provisions):
        try:
            expected.update((row.provision_id, row) for row in section_c_rows([pid], codes))
        except (KeyError, ValueError):
            add('D05', 'C', f'provisions.{pid}', f'a verified benchmark: provision {pid} was not found in NBC(AE) 2023, 2nd printing.',
                'Confirm the Division B article or sentence using the code database.')
    if not case.provisions:
        add('benchmark', 'C', 'provisions', 'a confirmed Division B benchmark.',
            'Confirm the acceptable-solution provisions affected by the departure before preparing Section C.')
    actual = {row.provision_id for row in case.section_c}
    for pid, expected_row in expected.items():
        if pid not in actual:
            add('D16', 'C', f'section_c.{pid}', f'the Section C row for benchmark {pid} cited in Section B.',
                'Populate the row by deterministic lookup after the applicant confirms the benchmark.', expected_row.citation)

    for index, row in enumerate(case.section_c):
        field = f'section_c.{index}.{row.provision_id}'
        try:
            rec = codes.provision(row.provision_id, 'B')
            canonical = section_c_rows([row.provision_id], codes) if rec else []
        except ValueError:
            rec, canonical = None, []
        if rec is None:
            add('D05', 'C', field, f'a verified reference: provision {row.provision_id} was not found in NBC(AE) 2023, 2nd printing.',
                'Ask for the correct current Division B provision; do not guess a replacement.')
        elif len(canonical) != 1 or canonical[0].provision_id != row.provision_id:
            add('D07', 'C', field + '.pairs', 'sentence-level Section C attribution rows.',
                'Expand this article into its sentence rows using deterministic lookup.', rec['citation'])
        else:
            current = canonical[0]
            if row.citation != current.citation:
                add('citation_binding', 'C', field + '.citation', 'the database citation bound to this row’s actual provision.',
                    'Use the exact lookup citation for this provision; a valid citation to another article is not a match.',
                    current.citation)
            if (_pairs(row) != _pairs(current) or row.attribution_status != current.attribution_status
                    or row.attributed_via != current.attributed_via):
                pairs = ', '.join(dict.fromkeys(p.bracket for p in current.pairs)) or 'no row in the attribution table'
                add('D07', 'C', field + '.pairs', 'the exact objective/function attribution for this provision; '
                    'a supplied pair or attribution scope is not in its Division B table row.',
                    f'Restore the lookup result: {pairs}. Keep clause conditions and inherited scope.', current.citation)
            payload_fields = ('intents', 'intent_comparison', 'differs', 'only_in_intent', 'only_in_ae',
                              'related_root', 'related_root_method')
            supplied = row.model_dump(include=set(payload_fields))
            verified_payload = current.model_dump(include=set(payload_fields))
            if supplied != verified_payload:
                add('intent_payload', 'C', field + '.intent_payload', 'the complete canonical intent payload and comparison metadata.',
                    'Reload the intent text, labels, provision scope, pages, attribution brackets and comparison status from the database. '
                    'Do not present changed or generated intent text as sourced.', current.citation)
        if row.provision_id not in expected:
            add('confirmation', 'C', field + '.confirmation', 'confirmation of this benchmark provision.',
                'Ask the applicant to confirm the benchmark; do not silently add an article.')

        validation = validate_text(row.citation, db_path=codes.db_path)
        edition_error = any(e['code'] in ('superseded_edition', 'national_edition_as_law') for e in validation['errors'])
        mapped_citation = None
        if not _HISTORICAL.search(row.citation):
            for mapping in _edition_crosswalks():
                original = mapping['original_citation'].rstrip('.')
                if row.provision_id.rstrip('.').split('.(')[0] != original and not row.provision_id.startswith(original + '('):
                    continue
                heading = confirmed_value(case, f'section_c.{row.provision_id}.heading', f'benchmark.{row.provision_id}.heading')
                old_topic = mapping.get('ae2023_title', '')
                heading_mismatch = bool(rec and old_topic and old_topic.casefold() != rec['article_title'].casefold()
                    and (heading == old_topic or old_topic.casefold() in row.citation.casefold()))
                if rec is None or heading_mismatch or edition_error:
                    target = _PID.search(mapping['ae2023_provision'])
                    mapped_citation = codes.citation(target.group(), 'B') if target else None
                    edition_error = True
                    break
        if edition_error:
            hint = ('The precedent index points to ' + mapped_citation + '; confirm the current scope. Cross-edition equivalence is unverified.'
                    if mapped_citation else 'Confirm the current number and heading, or explicitly label this as historical context.')
            add('D06', 'C', field + '.edition', 'a current-edition citation; this reference cites a superseded edition as current '
                'or uses an earlier number with a mismatched heading.', hint, mapped_citation or (rec['citation'] if rec else None))
        other_errors = [e for e in validation['errors'] if e['code'] not in ('superseded_edition', 'national_edition_as_law')]
        if rec and other_errors and not edition_error:
            add('citation', 'C', field + '.citation', 'a source-consistent code citation.',
                'Restore the database citation. ' + ' '.join(e['message'] for e in other_errors), rec['citation'])
        if any(intent.label != INTENT_LABEL for intent in row.intents):
            add('D08', 'C', field + '.intent_label', 'the explanatory label for the national 2020 intent statement; it is not Alberta law.',
                f'Use the label: {INTENT_LABEL}. Keep the Alberta code benchmark separate.')

    gaps.extend(professional_involvement_gaps(case, codes, process, professional=professional, documents=documents))

    docs = supporting_documents(case) if documents is None else documents
    for doc in docs:
        if latest_fact(case, f'evidence.{doc.id}.title') is not None and _missing(confirmed_value(case, f'evidence.{doc.id}.title')):
            add('D13', 'D', f'evidence.{doc.id}.title', 'a confirmed title for a supporting document.',
                'Ask the applicant to confirm the current document title; do not reuse an older title.')
        if not doc.date or not doc.date.strip():
            add('D13', 'D', f'evidence.{doc.id}.date', f'the date/revision of supporting document “{doc.title}”.',
                'Request the issue/revision date so the reviewer can identify the version supplied.', severity='warning')
    if expected:
        # Use only verified provisions so a bad reference becomes a gap, not an exception/500.
        verified = case.model_copy(update={'provisions': list(expected)})
        for item in section_d_plan(verified, codes, docs).items:
            if item.objective is None:
                add('evidence_scope', 'D', f'evidence.{item.id}.scope', f'an identified performance benchmark for {item.provision_id}.',
                    'The table has no row; ask the responsible designer which substantive benchmark applies.', item.citation, 'warning')
            elif item.status == 'needed':
                add('evidence', 'D', f'evidence.{item.id}', f'supporting evidence for {item.provision_id}, {item.function}–{item.objective}.',
                    item.performance_issue + ' Select appropriate evidence types with the responsible designer; not every ladder rung is required.',
                    item.citation)
    # Information from the case's jurisdiction pack (for example a local form). Severity info never blocks.
    for notice in notices_for(case, 'gaps'):
        gaps.append(Gap(id=f'info:{notice.id}', severity='info', section=notice.section, field=notice.id,
                        message=notice.message, fix_hint=notice.fix_hint, submission_blocking=False))
    return gaps


def check_completeness(case: Case, codes: Codes, *, professional=None, documents=None, store=None) -> list[Gap]:
    """Compatibility projection of the one shared policy, never a second evaluator."""
    from .export.package import prepare_package
    return prepare_package(case, codes, store=store).policy.gaps
