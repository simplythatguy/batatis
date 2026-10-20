"""Required Part 1 elements, mapped to the SCC variance template field names.

Process fields (risk, mitigating measures, assumptions and limits) are applicant-written.
They are not evidence types. The SCC AcroForm has no box for them; they stay on the
case record and are grouped with Section B, the proposal.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .models import INTENT_LABEL

_MAP = json.loads((Path(__file__).resolve().parent / 'export/field_maps/scc_2026-10.json').read_text())


@dataclass(frozen=True)
class ElementSpec:
    field: str
    template_section: str
    export_section: str
    export_field: str
    form_fields: tuple[str, ...]
    label: str
    question: str
    source: str
    group: str = ''
    requires_codedb: bool = False


def _widgets(*facts: str) -> tuple[str, ...]:
    names = []
    for block in (_MAP['text_fields'],):
        for name, spec in block.items():
            if spec['fact'] in facts:
                names.append(name)
    for index, row in enumerate(_MAP['section_c_rows']):
        # Only the first row is the default single-benchmark slot. Extra rows are addressed by index.
        if index:
            break
        for key, fact in (('article', 'section_c.article'), ('objective', 'objective'),
                          ('function', 'function'), ('intent', 'section_c.intent')):
            if fact in facts:
                names.append(row[key])
    for index, row in enumerate(_MAP['section_d_rows']):
        if index:
            break
        for key, fact in (('document', 'supporting_doc'), ('responsible', 'responsible_party')):
            if fact in facts:
                names.append(row[key])
    return tuple(dict.fromkeys(names))


ELEMENTS: tuple[ElementSpec, ...] = (
    ElementSpec('owner_name', 'A', 'A', 'owner_name', _widgets('owner_name'), 'owner name',
                "What is the owner's name?", 'applicant'),
    ElementSpec('application_date', 'A', 'A', 'application_date', _widgets('request_date'), 'application date',
                'What is the application date?', 'applicant'),
    ElementSpec('representative', 'A', 'A', 'representative', _widgets('owner_rep_name'), 'applicant representative',
                "Who is the owner's representative, if there is one?", 'applicant'),
    ElementSpec('mailing_address', 'A', 'A', 'mailing_address', _widgets('mailing_address'), 'mailing address',
                'What is the mailing address for this application?', 'applicant'),
    ElementSpec('signature', 'A', 'A', 'signature', (), 'signature',
                'Who signed the application, and was it signed?', 'applicant'),
    ElementSpec('owner_rep_signature_date', 'A', 'A', 'owner_rep_signature_date', ('Date2',),
                'representative signature date', 'What is the date next to the signature?', 'applicant'),
    ElementSpec('civic_address', 'B', 'B', 'civic_address', _widgets('municipal_address'), 'civic address',
                'What is the municipal address of the project?', 'applicant'),
    ElementSpec('legal_description', 'B', 'B', 'legal_description', ('Lot', 'Block', 'Plan', 'QTR', 'SEC', 'TWP', 'RGE', 'MER'),
                'legal description', 'What is the legal description (lot, block and plan, or ATS)? A placeholder such as TBD does not supply it.',
                'applicant'),
    ElementSpec('alternative_description', 'B', 'B', 'alternative_description', (), 'description of the proposed alternative',
                'Describe the proposed alternative in your own words, including the acceptable solution you want to depart from.',
                'applicant'),
    ElementSpec('risk_assessment', 'B', 'process', 'risk_assessment', (), 'risk assessment',
                'What risks arise from this specific departure? Name who or what is affected. A line such as "low risk" is not enough. Write this yourself; the tool will not draft it.',
                'applicant', 'Alternative-path process field. Applicant-written. Not an evidence type.'),
    ElementSpec('mitigating_measures', 'B', 'process', 'mitigating_measures', (), 'mitigating measures',
                'What measures address each risk and the objective of the cited provision? Write them yourself; the tool will not draft them.',
                'applicant', 'Alternative-path process field. Applicant-written. Not an evidence type.'),
    ElementSpec('assumptions_and_limits', 'B', 'process', 'assumptions_and_limits', (), 'assumptions and limits',
                'What assumptions and limits does your analysis rely on? Label them as assumptions. Do not state an unverified guess as a known fact. The tool will not draft this.',
                'applicant', 'Alternative-path process field. Applicant-written. Not an evidence type.'),
    ElementSpec('section_b.consistency', 'B', 'B', 'section_b.consistency', (), 'Section B consistency with attachments',
                'Section B and an attachment give different values. Which value should the application use? The review will not pick one.',
                'applicant'),
    ElementSpec('code_or_standard', 'C', 'C', 'code_or_standard', _widgets('code_or_standard'), 'code or standard',
                'Which code and edition are you citing?', 'applicant'),
    ElementSpec('section_c.article', 'C', 'C', 'section_c.article', _widgets('section_c.article'), 'Section C article',
                'Which Division B provision is the benchmark for this departure?', 'applicant'),
    ElementSpec('section_c.intent', 'C', 'C', 'section_c.intent', _widgets('section_c.intent'), 'intent statement label',
                f'If you include a national intent statement, label it "{INTENT_LABEL}". It is explanatory material, not Alberta law.',
                'applicant'),
    ElementSpec('section_c.edition', 'C', 'C', 'section_c.edition', (), 'edition of the citation',
                'This citation appears to use a superseded edition as if it were current. What is the NBC(AE) 2023 provision, or is this historical context?',
                'applicant'),
    ElementSpec('section_c.relevance', 'C', 'C', 'section_c.relevance', (), 'relevance of the cited provision',
                'The cited provision does not appear to address the departure you described. Which benchmark are you varying?',
                'applicant'),
    ElementSpec('section_c.pair_match', 'C', 'C', 'section_c.pair_match', _widgets('objective', 'function'),
                'objective and function',
                'The objective and function on this row do not match the Division B attribution table for this provision. Confirm the row from the code database; do not type a remembered pair.',
                'applicant', requires_codedb=True),
    ElementSpec('section_c.provision_found', 'C', 'C', 'section_c.provision_found', _widgets('section_c.article'),
                'provision in NBC(AE) 2023',
                'This provision id was not found in NBC(AE) 2023, 2nd printing. What is the correct current provision?',
                'applicant', requires_codedb=True),
    ElementSpec('supporting_doc', 'D', 'D', 'supporting_doc', _widgets('supporting_doc'), 'supporting document',
                'What supporting document are you relying on, and who is responsible for it?', 'applicant'),
    ElementSpec('responsible_professional', 'D', 'D', 'responsible_professional', _widgets('responsible_party'),
                'responsible professional',
                'Which registered professional will take responsibility for this work? Enter the name they will sign. Do not invent a name.',
                'applicant'),
    ElementSpec('professional_qualifications', 'D', 'D', 'professional_qualifications', (),
                'qualifications of the responsible professional',
                'Ask the registered professional for their qualifications, experience and the scope they will seal. Do not draft this.',
                'registered_professional'),
    # IB-2025-11-18: Division C Section 2.3.1 documentation is mandatory for a building variance.
    ElementSpec('division_c_2_3_1', 'B', 'B', 'division_c_2_3_1', (),
                'Division C Section 2.3.1 documentation',
                'Is the Division C Section 2.3.1 documentation for this alternative solution included? IB-2025-11-18 requires that documentation. The tool will not draft it.',
                'applicant', 'IB-2025-11-18'),
    # IB-2026-10-01: each variance is registered individually, for one specific location.
    ElementSpec('single_location', 'B', 'B', 'single_location', (),
                'single location',
                'This application lists more than one location. Which single location should this registration cover? IB-2026-10-01 requires one registration per location. The review will not pick one.',
                'applicant', 'IB-2026-10-01'),
)

BY_FIELD = {spec.field: spec for spec in ELEMENTS}

WIDGET_TO_FIELD = {}
for spec in ELEMENTS:
    for widget in spec.form_fields:
        WIDGET_TO_FIELD.setdefault(widget, spec.field)

SECTION_TITLES = {
    'A': 'Part 1 Section A — Applicant',
    'B': 'Part 1 Section B — Project and proposal',
    'C': 'Part 1 Section C — Code provisions',
    'D': 'Part 1 Section D — Supporting documents',
}

NOTICE = (
    'This review lists administrative gaps only. It is not a finding that the design is safe, '
    'that it complies with the code, or that a variance is granted.'
)
