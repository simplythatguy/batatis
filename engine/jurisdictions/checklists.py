"""Standing-package checklists: load, cross-check against the packs, and read a case's answers.

    engine/data/jurisdictions/checklists/<id>.json   one checklist per standing package (StandingChecklist)

Each checklist names its pack (`jurisdiction`) and package (`package`); the package names the checklist back.
A historical package never has a checklist. Nothing here names a particular city.

Answers are case facts, one per condition and one for its reason:

    checklist.<checklist id>.<condition id>          'confirmed' | 'not_yet' | 'does_not_apply'
    checklist.<checklist id>.<condition id>.reason   free text

Only applicant facts count (`user_click` or `user_text`, never `proposed`). An answer is the applicant's
declaration; it is never a determination.
"""
from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING

from ..models import Case, Fact
from ..models_checklists import (ANSWER_STATES, AnswerCounts, CaseChecklist, CaseCondition, ConditionAnswer,
                                 HistoricalPackage, JurisdictionChecklist, StandingChecklist, historical)

if TYPE_CHECKING:
    from . import Registry
    from ..models_jurisdictions import JurisdictionPack

NOTICE = ('A checklist is never a determination. Confirming a condition is your own declaration that the '
          'project follows the published package; it is not an acceptance of the design. The safety codes '
          'officer decides whether the package can be used and whether its conditions are met.')
NONE_NO_JURISDICTION = 'The case does not name a jurisdiction yet, so no standing package can be offered.'
NONE_IN_PACK = ('This office has no current standing package with a checklist. Where none fits, the route is a '
                'site-specific variance (the full application).')
APPLICANT_SOURCES = {'user_click', 'user_text'}
FIELD_PREFIX = 'checklist.'


def field(checklist_id: str, condition_id: str, reason: bool = False) -> str:
    return f'{FIELD_PREFIX}{checklist_id}.{condition_id}' + ('.reason' if reason else '')


# Quote verification. The same normalisation is applied to the quote and to the reference text, so a quote
# matches when it is the source's words with PDF spacing, ligatures and typographic quotes evened out.

_TRANSLATE = str.maketrans({'‘': "'", '’': "'", '“': '"', '”': '"',
                            '–': '-', '—': '-', '‐': '-', '‑': '-', '­': ''})


def normalise(text: str) -> str:
    text = unicodedata.normalize('NFKC', text).translate(_TRANSLATE)
    text = ' '.join(text.split())
    text = re.sub(r'\s*-\s*', '-', text)
    return re.sub(r'\s+([,.;:)])', r'\1', text)


def load_dir(reg: 'Registry') -> None:
    """Load `<root>/checklists/*.json` into `reg.checklists` and cross-check with the packs.

    A checklist whose pack is absent is skipped, so removing a pack file removes its checklists too."""
    from . import PackError, _read
    folder = reg.root / 'checklists'
    for path in sorted(folder.glob('*.json')) if folder.is_dir() else []:
        checklist = _read(path, StandingChecklist)
        if path.stem != checklist.id:
            raise PackError(f'{path.name}: file name must be the checklist id {checklist.id}')
        pack = reg.packs.get(checklist.jurisdiction)
        if pack is None:
            continue
        where = f'checklists/{path.name}'
        pkg = next((p for p in pack.standing_packages if p.id == checklist.package), None)
        if pkg is None:
            raise PackError(f'{where}: pack {pack.id} has no standing package {checklist.package}')
        if pkg.status != 'current':
            raise PackError(f'{where}: package {pkg.code} is {pkg.status}; a historical package never has a checklist')
        if pkg.checklist != checklist.id:
            raise PackError(f'{where}: package {pkg.code} must name this checklist (checklist: "{checklist.id}")')
        if pkg.code != checklist.code or pkg.issued != checklist.issued or pkg.source.sha256 != checklist.source.sha256:
            raise PackError(f'{where}: code, issued date and source hash must match package {pkg.code}')
        reg.checklists[checklist.id] = checklist
    for pack in reg.packs.values():
        for pkg in pack.standing_packages:
            if pkg.checklist and pkg.checklist not in reg.checklists:
                raise PackError(f'packs/{pack.id}.json: package {pkg.code} names missing checklist {pkg.checklist}')
            if pkg.checklist and pkg.status != 'current':
                raise PackError(f'packs/{pack.id}.json: historical package {pkg.code} cannot name a checklist')


def for_pack(reg: 'Registry', pack: 'JurisdictionPack') -> list[StandingChecklist]:
    return [reg.checklists[p.checklist] for p in pack.standing_packages
            if p.status == 'current' and p.checklist in reg.checklists]


def historical_for(pack: 'JurisdictionPack') -> list[HistoricalPackage]:
    return [historical(p) for p in pack.standing_packages if p.status == 'historical']


def _view(checklist: StandingChecklist) -> dict:
    data = checklist.model_dump(exclude={'schema_version', 'reviewed_by', 'reviewed_on', 'reference_text',
                                         'conditions'})
    return {**data, 'notice': NOTICE}


def jurisdiction_view(checklist: StandingChecklist) -> JurisdictionChecklist:
    return JurisdictionChecklist(**_view(checklist), conditions=checklist.conditions)


def answers(case: Case, checklist: StandingChecklist) -> dict[str, ConditionAnswer]:
    """The latest applicant answer per condition. Facts are in write order; later facts win."""
    latest: dict[str, Fact] = {}
    for fact in case.facts:
        if (fact.field.startswith(FIELD_PREFIX) and fact.kind != 'proposed' and fact.status == 'confirmed'
                and fact.source.type in APPLICANT_SOURCES):
            latest[fact.field] = fact
    found = {}
    for condition in checklist.conditions:
        state = latest.get(field(checklist.id, condition.id))
        if state is None or state.value not in ANSWER_STATES:
            continue
        reason = latest.get(field(checklist.id, condition.id, reason=True))
        found[condition.id] = ConditionAnswer(state=state.value, fact_id=state.id,
                                              reason=str(reason.value) if reason and reason.value else None)
    return found


def case_view(case: Case, checklist: StandingChecklist, provisions: list[str]) -> CaseChecklist:
    given = answers(case, checklist)
    rows = [CaseCondition(**c.model_dump(), answer=given.get(c.id)) for c in checklist.conditions]
    states = [r.answer.state for r in rows if r.answer]
    counts = AnswerCounts(total=len(rows), confirmed=states.count('confirmed'), not_yet=states.count('not_yet'),
                          does_not_apply=states.count('does_not_apply'), unanswered=len(rows) - len(states))
    mine = {_bare(p) for p in case.provisions}
    return CaseChecklist(**_view(checklist), conditions=rows, counts=counts, provisions=provisions,
                         matches_case_provisions=any(_bare(p) in mine for p in provisions))


def _bare(provision: str) -> str:
    """'B:9.10.11.2.(2)' and '9.10.11.2.(2)' compare equal."""
    return provision.split(':')[-1].strip()
