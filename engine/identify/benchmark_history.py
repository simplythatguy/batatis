"""Retain the applicant's comparison while invalidating stale confirmation."""
from . import cards


def preserve(result, previous, codes):
    if previous is None or previous.benchmark.basis != 'applicant':
        return
    prior = previous.benchmark
    current = prior.model_copy(deep=True)
    same = (result.input_fingerprint == previous.input_fingerprint
            and result.requirement_coverage.source == previous.requirement_coverage.source
            and result.requirement_coverage.source is not None)
    row = None
    if result.requirement_coverage.source is not None:
        row = cards.provision(codes, prior.provision_id or prior.provision, 'B')
    if row is None or row.get('level') not in ('article', 'sentence'):
        current.provision = current.provision_id = current.citation = current.sentence = None
        current.objectives, current.functions, current.attribution_missing = [], [], True
        same = False
    elif not same:
        current.provision = row.get('article') or row['id']
        current.provision_id = row['id'] if row['level'] == 'sentence' else None
        current.citation, current.sentence = row.get('citation'), cards.flat(row.get('text')) or None
        current.objectives, current.functions, current.attribution_missing = cards.terms(codes, row['id'])
    if not same:
        current.identified, current.requirement = False, None
        current.departure_status = 'proposed' if current.departure else 'none'
        current.question = 'Project inputs or the code source changed. Review and confirm this comparison again.'
    result.benchmark = current
