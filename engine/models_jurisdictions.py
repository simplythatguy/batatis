"""Jurisdiction pack wire records. A pack is data in `engine/data/jurisdictions/`, never code.

Every record forbids unknown keys, so a typo in a pack fails validation instead of being ignored.
`engine/data/jurisdictions/pack.schema.json` is generated from these models (see
`engine.jurisdictions.schema`) and a test keeps it in step.

A pack describes where an application goes and what that office has published. It never says a
design complies, and a standing package or checklist is never a determination.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DATE = r'^\d{4}-\d{2}-\d{2}$'
SHA256 = r'^[0-9a-f]{64}$'
SLUG = r'^[a-z0-9][a-z0-9-]*$'

Coverage = Literal['full', 'code_only', 'preview']
SourceStatus = Literal['verified', 'unverified']


class _Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class PackSource(_Strict):
    """Where a claim comes from. `retrieved` is the date the URL was fetched or checked."""
    title: str = Field(min_length=1)
    url: str = Field(pattern=r'^https://')
    retrieved: str = Field(pattern=DATE, description='Date the URL was fetched or checked (YYYY-MM-DD).')
    pages: str | None = Field(default=None, description='PDF pages that carry the claim, as printed by the reader, e.g. "pp.2-3".')
    sha256: str | None = Field(default=None, pattern=SHA256, description='SHA-256 of the file fetched on `retrieved`.')
    status: SourceStatus = Field(default='verified', description='`unverified` when the claim could not be checked against the source.')
    note: str | None = None


class ProcessNote(_Strict):
    """One administrative process claim. Never a technical or acceptance statement."""
    id: str = Field(pattern=SLUG)
    topic: Literal['entry_point', 'submission', 'permit_link', 'scope', 'documents',
                   'professional', 'review', 'decision', 'appeal', 'registration', 'authority']
    text: str = Field(min_length=1)
    sources: list[PackSource] = Field(min_length=1)


AuthorityKind = Literal['accredited_municipality', 'alberta_safety_codes_authority', 'accredited_organisation',
                        'first_nation', 'federal', 'outside_alberta', 'unconfirmed']


class Authority(_Strict):
    """The authority having jurisdiction is an organisation, not an officer (SCC IB-2026-10-16).

    `first_nation`, `federal`, `outside_alberta` and `unconfirmed` name who decides where the Safety Codes Act
    variance does not, or where Batatis has not confirmed it; those packs are never `full` coverage."""
    name: str = Field(min_length=1)
    kind: AuthorityKind
    reviewer_code: str | None = Field(
        default=None, description='The account `Authority` code when Batatis has reviewer accounts for this office; else null.')
    contact: str | None = None
    sources: list[PackSource] = Field(min_length=1)


class FormEntry(_Strict):
    """A form the office expects. `role` says whether it is the province form or an additional local one."""
    id: str = Field(pattern=SLUG)
    title: str
    issuer: str
    role: Literal['primary', 'additional']
    version: str
    status: Literal['current', 'confirm_with_office', 'historical']
    export: Literal['supported', 'not_yet'] = Field(description='Whether Batatis fills this form today.')
    sha256: str = Field(pattern=SHA256)
    page_count: int = Field(ge=1)
    field_count: int = Field(ge=0)
    pdf_last_modified: str | None = Field(default=None, pattern=DATE)
    field_map: str | None = Field(default=None, description='Repository path of the field map, when export is supported.')
    local_path: str | None = Field(default=None, description='Git-excluded local copy under reference/.')
    note: str = ''
    source: PackSource


class StandingPackage(_Strict):
    """A published local route (standing posted variance or policy). Its conditions live in a checklist file."""
    id: str = Field(pattern=SLUG)
    code: str = Field(description='The identifier the issuer prints, e.g. SPV-001 or B23-01.')
    kind: Literal['standing_posted_variance', 'policy']
    title: str
    revision: str | None = None
    issued: str = Field(pattern=DATE)
    edition: str = Field(description='Code edition the document cites, as printed.')
    status: Literal['current', 'historical']
    historical_reason: str | None = None
    provisions: list[str] = Field(default_factory=list, description='Provisions the source names, as printed. Not a code analysis.')
    applies_to: str
    note: str = ''
    checklist: str | None = Field(default=None, description='Id of the checklist in checklists/<id>.json; null when none is built. Never set on a historical package. A checklist is never a determination.')
    source: PackSource


class Guide(_Strict):
    """A published guide for a design category or process. Guidance, not a variance or an approval."""
    id: str = Field(pattern=SLUG)
    title: str
    issued: str | None = Field(default=None, pattern=DATE)
    topic: str
    summary: str
    requires_professional: bool | None = None
    source: PackSource
    companions: list[PackSource] = Field(default_factory=list)


class Bulletin(_Strict):
    """A Safety Codes Council information bulletin. Title, date and link; paragraphs are not copied."""
    id: str = Field(pattern=r'^IB-\d{4}-\d{2}-\d{2}$')
    title: str
    issued: str = Field(pattern=DATE)
    effective: str | None = Field(default=None, pattern=DATE)
    summary: str
    source: PackSource


class PackNotice(_Strict):
    """Information shown on the gaps list and the export. Severity is always info; it never blocks."""
    id: str = Field(pattern=r'^[a-z0-9_]+$')
    surfaces: list[Literal['gaps', 'export_header', 'export_appendix']] = Field(min_length=1)
    section: Literal['A', 'B', 'C', 'D', 'process']
    heading: str = Field(description='Appendix heading for the notice.')
    message: str = Field(min_length=1, pattern=r'^[\x20-\x7e]+$', description='ASCII, because it is also sent as an HTTP header.')
    fix_hint: str
    sources: list[PackSource] = Field(min_length=1)


class Match(_Strict):
    """How a case's jurisdiction resolves to this pack. Compared case-insensitively."""
    ids: list[str] = Field(default_factory=list)
    names: list[str] = Field(default_factory=list)


class JurisdictionPack(_Strict):
    schema_version: Literal[1] = 1
    id: str = Field(pattern=SLUG)
    name: str
    province: str = Field(pattern=r'^[A-Z]{2}$')
    coverage: Coverage
    fallback: bool = Field(default=False, description='The province pack used when no local pack matches.')
    code_edition: str
    summary: str
    authority: Authority
    match: Match = Field(default_factory=Match)
    process_notes: list[ProcessNote] = Field(default_factory=list)
    forms: list[FormEntry] = Field(default_factory=list)
    standing_packages: list[StandingPackage] = Field(default_factory=list)
    guides: list[Guide] = Field(default_factory=list)
    bulletins: list[Bulletin] = Field(default_factory=list)
    notices: list[PackNotice] = Field(default_factory=list)


class ProvinceShared(_Strict):
    """Items that apply in every pack of a province (the SCC form, Council bulletins, province-wide notes)."""
    schema_version: Literal[1] = 1
    province: str = Field(pattern=r'^[A-Z]{2}$')
    name: str
    process_notes: list[ProcessNote] = Field(default_factory=list)
    forms: list[FormEntry] = Field(default_factory=list)
    bulletins: list[Bulletin] = Field(default_factory=list)


class CoverageEntry(_Strict):
    id: str = Field(pattern=r'^[A-Z]{2}$')
    name: str
    coverage: Coverage
    note: str
    roadmap: str | None = None


class CoverageFile(_Strict):
    schema_version: Literal[1] = 1
    default_province: str = Field(pattern=r'^[A-Z]{2}$', description='Province whose fallback pack takes unmatched cases.')
    levels: dict[Coverage, str]
    regions: list[CoverageEntry]


# Wire records. `scope` says whether an item comes from the province file or the local pack.

class ResolvedForm(FormEntry):
    scope: Literal['province', 'local']


class ResolvedNote(ProcessNote):
    scope: Literal['province', 'local']


class JurisdictionSummary(_Strict):
    id: str
    name: str
    province: str
    coverage: Coverage
    fallback: bool
    authority: str
    reviewer_code: str | None
    standing_packages: int
    forms: int


class JurisdictionsResult(_Strict):
    jurisdictions: list[JurisdictionSummary]
    coverage: list[CoverageEntry]
    levels: dict[Coverage, str]
    disclaimer: str


class JurisdictionDetail(_Strict):
    id: str
    name: str
    province: str
    coverage: Coverage
    fallback: bool
    code_edition: str
    summary: str
    authority: Authority
    process_notes: list[ResolvedNote]
    forms: list[ResolvedForm]
    standing_packages: list[StandingPackage]
    guides: list[Guide]
    bulletins: list[Bulletin]
    notices: list[PackNotice]
    disclaimer: str


class Place(_Strict):
    """A place an applicant can name, and who reviews building work there. Generated by
    `python -m engine.jurisdictions.places_build`; one place becomes one pack unless a hand-written pack
    already names it."""
    id: str = Field(pattern=SLUG, description='Pack id: the slug of the short name, e.g. red-deer.')
    name: str = Field(min_length=1, description='Legal name, e.g. City of Red Deer.')
    aliases: list[str] = Field(default_factory=list, description='Other names an applicant types, e.g. Red Deer.')
    province: str = Field(pattern=r'^[A-Z]{2}$')
    lg_code: str | None = Field(default=None, pattern=r'^\d{4}$', description='Municipal Affairs code, Alberta only.')
    type: str = Field(min_length=1, description='City, Town, First Nation, Airport lands, ...')
    kind: AuthorityKind
    office: str = Field(min_length=1, description='Who reviews building work here.')
    accreditation: list[str] = Field(default_factory=list, description='Safety Codes Council accreditation numbers held under this name.')
    covered: bool = Field(description='True when Batatis prepares the application here; false means not covered.')
    code_edition: str = Field(min_length=1)
    note: str = Field(min_length=1, description='One plain sentence the applicant sees about who decides here.')
    ask: str = Field(min_length=1, description='Who to ask, shown as the fix for a place that is not covered.')
    climate_location: str | None = Field(default=None, description='Exact NBC(AE) Table C-2 location name, if any.')
    sources: list[PackSource] = Field(min_length=1)


class PlacesFile(_Strict):
    """`places/<group>.json`: generated places for a province or for outside Alberta."""
    schema_version: Literal[1] = 1
    group: str = Field(pattern=SLUG)
    generated_by: str
    inputs: dict[str, str] = Field(description='Input file name to SHA-256 of the file the places were built from.')
    places: list[Place] = Field(min_length=1)
