"""Compatibility names. A and B now project one policy; C remains unavailable."""
from .completeness_rules import ElementVerdict, QuoteSpan, VariantResult, format_export_reason

SELECTED_VARIANT = 'B'


class VariantUnavailable(RuntimeError):
    pass


def run_variant(variant, doc, codes=None, llm=None):
    if variant not in ('A', 'B', 'C'):
        raise ValueError(f'unknown variant {variant}')
    if variant == 'C':
        raise VariantUnavailable('provider-assisted completeness is unavailable')
    from .completeness_policy import evaluate
    from .completeness_snapshot import Snapshot, from_case
    if doc.case:
        from .export.package import prepare_package
        return prepare_package(doc.case, codes).policy.variant_result(variant, doc.submission_id or doc.ref)
    return evaluate(Snapshot(doc), codes).variant_result(variant, doc.submission_id or doc.ref)
