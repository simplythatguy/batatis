"""Bind an officer determination to the applicant content actually reviewed.

Communication, claims and decisions do not change this basis. Changed applicant
facts, evidence, references or jurisdiction require a new determination; the old
record stays in the history. No public fact input can write these records.
"""
from __future__ import annotations

import hashlib
import json

from .models import Case, ProfessionalRequirementResolution


def requirement_fingerprint(case: Case) -> str:
    content = case.model_dump(include={'facts', 'provisions', 'section_c', 'evidence', 'jurisdiction', 'authority'})
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def current_resolution(case: Case) -> ProfessionalRequirementResolution | None:
    if not case.professional_resolutions:
        return None
    resolution = case.professional_resolutions[-1]
    return resolution if resolution.content_fingerprint == requirement_fingerprint(case) else None
