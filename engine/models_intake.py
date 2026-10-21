"""Intake records: where each extracted fact came from, and what was read from each file.

Stored on `Case.intake`. The facts themselves live in the case ledger (`Case.facts`). This record
adds the pointer the ledger has no room for: which pass found the fact (rules, form or model), the
character span in the text it was read from, and a per-file report that says "not read" with a
reason instead of guessing. Nothing here confirms a fact; the applicant does that.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

Method = Literal['rules', 'form', 'model']
FileStatus = Literal['read', 'partly_read', 'not_read']
FormKind = Literal['scc_variance', 'acroform']
ModelStatus = Literal['off', 'fake', 'live', 'gate_closed', 'failed', 'not_needed']


class FactPointer(BaseModel):
    """One extracted fact and where it sits. `start`/`end` index the source text: the description,
    or the page text of `page` (text layer order). Form values have no span."""
    fact_id: str
    field: str
    method: Method
    source_ref: str                         # 'description' or a case file id
    page: int | None = None                 # 1-based
    start: int | None = None
    end: int | None = None
    verified: bool = True                   # false for a model value the rules could not re-derive (proposed)


class FileReport(BaseModel):
    file_id: str
    name: str
    status: FileStatus
    reason: str | None = None               # always set when status is not 'read'
    pages: int | None = None
    pages_read: list[int] = []
    pages_not_read: list[int] = []
    form: FormKind | None = None
    form_fields_read: int = 0
    form_fields_skipped: list[str] = []     # officer, signature and unmapped fields, by name
    facts: int = 0


class ModelPass(BaseModel):
    status: ModelStatus
    model: str | None = None
    reason: str | None = None
    pointed: int = 0                        # quote found and the value re-derived from it by the rules
    proposed: int = 0                       # quote found, value not re-derived: stored as `proposed`
    dropped: int = 0                        # quote not in the source: never stored
    input_tokens: int = 0
    output_tokens: int = 0


class FieldConflict(BaseModel):
    """The text gives two different values for one field, so neither was stored. The planner asks."""
    field: str
    values: list[str | int | float | bool] = []
    quotes: list[str] = []
    source_ref: str
    page: int | None = None


class UnresolvedCitation(BaseModel):
    """An article number the applicant typed that is not in NBC(AE) 2023, 2nd printing."""
    entered: str
    source_ref: str
    page: int | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


class IntakeRecord(BaseModel):
    ran_at: str = Field(default_factory=_now)
    text_sha256: str | None = None
    pointers: list[FactPointer] = []
    files: list[FileReport] = []
    model: ModelPass = Field(default_factory=lambda: ModelPass(status='off'))
    conflicts: list[FieldConflict] = []
    unresolved_citations: list[UnresolvedCitation] = []
