"""Hard constraints from the completeness battle prompts, checked on variant output."""
from __future__ import annotations

import re

from engine.completeness_variants import VariantResult

_AFFIRMATIVE = re.compile(
    r'\b(this design complies|code-compliant|technically correct|variance is granted|mark the application as code-compliant)\b',
    re.I)
_STANDATA = re.compile(r'\b\d{2}-BC[A-Z]-\d+\b')
_EVIDENCE_SLUR = re.compile(
    r'(risk assessment|mitigating measures|assumptions and limits).{0,48}(evidence type|ladder rung)',
    re.I)


def _blob(result: VariantResult) -> str:
    parts = []
    for element in result.elements:
        parts.append(element.reason)
        if element.prompt:
            parts.append(element.prompt['question'])
    return '\n'.join(parts)


def constraint_failures(result: VariantResult, source_text: str) -> list[str]:
    """Return failed constraint ids. The fixed notice is not scanned for negated compliance words."""
    text = _blob(result)
    failed = []
    if _AFFIRMATIVE.search(text):
        failed.append('no_compliance_claim')
    if _EVIDENCE_SLUR.search(text):
        failed.append('process_not_evidence_type')
    for token in _STANDATA.findall(text):
        if token not in source_text:
            failed.append('no_fabricated_standata')
            break
    for element in result.elements:
        if element.verdict in ('missing', 'unclear'):
            prompt = element.prompt or {}
            if not prompt.get('question') or not prompt.get('field') or prompt.get('source') not in (
                    'applicant', 'registered_professional'):
                failed.append('prompt_on_gap')
                break
            if element.field in ('risk_assessment', 'mitigating_measures', 'assumptions_and_limits'):
                if prompt.get('source') != 'applicant':
                    failed.append('process_prompt_is_applicant')
                    break
            if element.field == 'professional_qualifications' and prompt.get('source') != 'registered_professional':
                failed.append('qualifications_from_professional')
                break
    if result.invented_values:
        failed.append('no_invented_values')
    return failed
