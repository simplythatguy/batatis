"""Bind an officer determination to what it was about.

That is the applicant's professional answers, the proposed alternative and its code
references, and the authority. A resubmission that changes only other answers (an
address, a document, a building-area answer) keeps the determination; a mandatory
duty still overrides a carried "not required" (professional_involvement). Changed
professional answers, alternative, references or authority require a new
determination; the old record stays in the history. No public fact input can write
these records.
"""
from __future__ import annotations

import hashlib
import json

from .models import Case, ProfessionalRequirementResolution

_SCOPE_FIELDS = frozenset({'alternative_description', 'alternative', 'engineering_required',
                           'apega_number', 'aaa_number'})
# Describing the building is not a professional answer. A changed size or occupancy that makes a
# professional mandatory still overrides a carried "not required".
_BUILDING_FIELDS = frozenset({'occupancy', 'storeys', 'building_area_m2', 'principal_dwelling_units',
                              'gross_area_per_floor_m2', 'total_unit_count', 'gross_area_unsettled', 'farm_public_use'})


def _professional_answer(field: str) -> bool:
    from .professional import ProfessionalFacts, _ENGAGEMENT_FIELDS
    if field in _BUILDING_FIELDS:
        return False
    return (field.startswith(('professional', 'registered_professional')) or field in _SCOPE_FIELDS
            or field in ProfessionalFacts.model_fields or field in _ENGAGEMENT_FIELDS)


def requirement_fingerprint(case: Case) -> str:
    # The latest value of each answer, not its id or time: saving the same answer again changes nothing.
    answers = {fact.field: [fact.value, fact.status] for fact in case.facts
               if fact.kind != 'proposed' and _professional_answer(fact.field)}
    content = {'answers': answers, 'provisions': case.provisions,
               'jurisdiction': case.jurisdiction.model_dump() if case.jurisdiction else None,
               'authority': case.authority}
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def _whole_content_fingerprint(case: Case) -> str:
    """The earlier binding (every fact, document and reference), so a record made before it still counts unchanged."""
    content = case.model_dump(include={'facts', 'provisions', 'section_c', 'evidence', 'jurisdiction', 'authority'})
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def current_resolution(case: Case) -> ProfessionalRequirementResolution | None:
    if not case.professional_resolutions:
        return None
    resolution = case.professional_resolutions[-1]
    if resolution.content_fingerprint in (requirement_fingerprint(case), _whole_content_fingerprint(case)):
        return resolution
    return None
