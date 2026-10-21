"""Jurisdiction packs: load, validate and resolve. All jurisdiction facts live in data files.

    engine/data/jurisdictions/packs/<id>.json      one pack per office (JurisdictionPack)
    engine/data/jurisdictions/provinces/<XX>.json  items every pack in a province shares
    engine/data/jurisdictions/coverage.json        coverage labels for every province and territory

`BATATIS_JURISDICTIONS_DIR` points the loader at another directory with the same layout, so a new
pack is a new file and no code changes. Nothing here names a particular city.

A pack never says a design complies; a standing package or checklist is never a determination.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, get_args

from pydantic import ValidationError

from ..account_models import Authority as ReviewerAuthority
from ..models import Case, Jurisdiction
from ..models_jurisdictions import (CoverageFile, JurisdictionDetail, JurisdictionPack, JurisdictionSummary,
                                    JurisdictionsResult, PackNotice, ProvinceShared, ResolvedForm, ResolvedNote)

DATA_DIR = Path(__file__).resolve().parent.parent / 'data' / 'jurisdictions'
ENV_DIR = 'BATATIS_JURISDICTIONS_DIR'

DISCLAIMER = ('Process notes say where an application goes and what the office has published, with the source '
              'and the date it was checked. They are not legal advice and not a determination: Batatis never '
              'says a design complies, and a standing package or checklist is never an approval. The safety '
              'codes officer decides.')

MatchedBy = Literal['id', 'name', 'reviewer_code', 'fallback']


class PackError(ValueError):
    """A pack directory that does not validate. The message names the file."""


@dataclass(frozen=True)
class Resolution:
    pack: JurisdictionPack
    matched_by: MatchedBy


def _key(value: str | None) -> str:
    return ' '.join((value or '').split()).casefold()


def _read(path: Path, model):
    try:
        return model.model_validate(json.loads(path.read_text()))
    except (ValidationError, json.JSONDecodeError) as exc:
        raise PackError(f'{path.name}: {exc}') from None


@dataclass
class Registry:
    root: Path
    packs: dict[str, JurisdictionPack] = field(default_factory=dict)
    provinces: dict[str, ProvinceShared] = field(default_factory=dict)
    coverage: CoverageFile | None = None
    _ids: dict[str, str] = field(default_factory=dict)
    _names: dict[str, str] = field(default_factory=dict)
    fallbacks: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path | str | None = None) -> 'Registry':
        root = Path(root or os.environ.get(ENV_DIR) or DATA_DIR)
        reg = cls(root=root)
        coverage = root / 'coverage.json'
        if not coverage.is_file():
            raise PackError(f'coverage.json not found in {root}')
        reg.coverage = _read(coverage, CoverageFile)
        for path in sorted((root / 'provinces').glob('*.json')):
            shared = _read(path, ProvinceShared)
            if path.stem != shared.province:
                raise PackError(f'{path.name}: file name must be the province code {shared.province}')
            reg.provinces[shared.province] = shared
        for path in sorted((root / 'packs').glob('*.json')):
            reg._add(path, _read(path, JurisdictionPack))
        reg._check()
        return reg

    def _add(self, path: Path, pack: JurisdictionPack):
        if path.stem != pack.id:
            raise PackError(f'{path.name}: file name must be the pack id {pack.id}')
        if pack.id in self.packs:
            raise PackError(f'{path.name}: duplicate pack id {pack.id}')
        self.packs[pack.id] = pack
        for raw, index in [*((i, self._ids) for i in [pack.id, *pack.match.ids]),
                           *((n, self._names) for n in [pack.name, *pack.match.names])]:
            key = _key(raw)
            if index.get(key, pack.id) != pack.id:
                raise PackError(f'{path.name}: "{raw}" also matches pack {index[key]}')
            index[key] = pack.id

    def _check(self):
        regions = {r.id for r in self.coverage.regions}
        reviewer_codes = set(get_args(ReviewerAuthority))
        fallbacks = self.fallbacks
        for pack in self.packs.values():
            where = f'packs/{pack.id}.json'
            if pack.province not in regions:
                raise PackError(f'{where}: province {pack.province} has no coverage entry')
            if pack.fallback:
                if pack.province in fallbacks:
                    raise PackError(f'{where}: {pack.province} already has fallback pack {fallbacks[pack.province]}')
                fallbacks[pack.province] = pack.id
            code = pack.authority.reviewer_code
            if code is not None and code not in reviewer_codes:
                raise PackError(f'{where}: reviewer_code {code!r} is not an account Authority')
            forms = [f.id for f in self.forms(pack)]
            if len(forms) != len(set(forms)):
                raise PackError(f'{where}: a form id repeats a province form id')

    # Lookups

    def get(self, pack_id: str) -> JurisdictionPack | None:
        return self.packs.get(pack_id)

    def by_reviewer_code(self, code: str | None) -> JurisdictionPack | None:
        return next((p for p in self.packs.values() if code and p.authority.reviewer_code == code), None)

    def reviewing_packs(self) -> list[JurisdictionPack]:
        """Packs whose office has reviewer accounts, in reviewer-code order."""
        order = list(get_args(ReviewerAuthority))
        found = [p for p in self.packs.values() if p.authority.reviewer_code in order]
        return sorted(found, key=lambda p: order.index(p.authority.reviewer_code))

    def resolve(self, jurisdiction: Jurisdiction | None, authority: str | None = None) -> Resolution | None:
        """A case's jurisdiction (id, then name or authority name) or reviewer authority, then the fallback."""
        if jurisdiction is not None:
            hit = self._ids.get(_key(jurisdiction.id))
            if hit:
                return Resolution(self.packs[hit], 'id')
            for raw in (jurisdiction.name, jurisdiction.authority):
                hit = self._names.get(_key(raw))
                if hit:
                    return Resolution(self.packs[hit], 'name')
        pack = self.by_reviewer_code(authority)
        if pack:
            return Resolution(pack, 'reviewer_code')
        if jurisdiction is not None and _key(jurisdiction.id):
            fallback = self.fallbacks.get(self.coverage.default_province)
            if fallback:
                return Resolution(self.packs[fallback], 'fallback')
        return None

    def resolve_case(self, case: Case) -> Resolution | None:
        return self.resolve(case.jurisdiction, case.authority)

    # Views

    def forms(self, pack: JurisdictionPack) -> list[ResolvedForm]:
        shared = self.provinces.get(pack.province)
        return ([ResolvedForm(**f.model_dump(), scope='province') for f in (shared.forms if shared else [])]
                + [ResolvedForm(**f.model_dump(), scope='local') for f in pack.forms])

    def detail(self, pack: JurisdictionPack) -> JurisdictionDetail:
        shared = self.provinces.get(pack.province)
        notes = ([ResolvedNote(**n.model_dump(), scope='province') for n in (shared.process_notes if shared else [])]
                 + [ResolvedNote(**n.model_dump(), scope='local') for n in pack.process_notes])
        return JurisdictionDetail(
            id=pack.id, name=pack.name, province=pack.province, coverage=pack.coverage, fallback=pack.fallback,
            code_edition=pack.code_edition, summary=pack.summary, authority=pack.authority,
            process_notes=notes, forms=self.forms(pack), standing_packages=pack.standing_packages,
            guides=pack.guides, bulletins=[*(shared.bulletins if shared else []), *pack.bulletins],
            notices=pack.notices, disclaimer=DISCLAIMER)

    def listing(self) -> JurisdictionsResult:
        rows = [JurisdictionSummary(
            id=p.id, name=p.name, province=p.province, coverage=p.coverage, fallback=p.fallback,
            authority=p.authority.name, reviewer_code=p.authority.reviewer_code,
            standing_packages=len(p.standing_packages), forms=len(self.forms(p)))
            for p in sorted(self.packs.values(), key=lambda p: (p.province, p.fallback, p.name))]
        return JurisdictionsResult(jurisdictions=rows, coverage=self.coverage.regions,
                                   levels=self.coverage.levels, disclaimer=DISCLAIMER)

    def notices(self, case: Case, surface: str) -> list[PackNotice]:
        found = self.resolve_case(case)
        return [n for n in found.pack.notices if surface in n.surfaces] if found else []


_CACHE: dict[str, Registry] = {}


def registry() -> Registry:
    """The registry for the current directory setting, loaded once per directory."""
    root = str(Path(os.environ.get(ENV_DIR) or DATA_DIR).resolve())
    if root not in _CACHE:
        _CACHE[root] = Registry.load(root)
    return _CACHE[root]


def clear_cache():
    _CACHE.clear()


def notices_for(case: Case, surface: str) -> list[PackNotice]:
    return registry().notices(case, surface)


def export_notice(case: Case) -> str | None:
    """The `X-Batatis-Notice` text for an export, or None when the pack has no export notice."""
    found = notices_for(case, 'export_header')
    return ' '.join(n.message for n in found) or None


def reviewing_authority_names() -> str:
    """'A or B' over the offices that have reviewer accounts, for user-facing messages."""
    names = [p.name for p in registry().reviewing_packs()]
    return ' or '.join([', '.join(names[:-1]), names[-1]] if len(names) > 1 else names) or 'a reviewing authority'
