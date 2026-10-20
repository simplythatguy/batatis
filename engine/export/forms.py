"""Jurisdiction and form-version registry for variance export.

`engine/export/forms.json` is keyed by jurisdiction, then form id. Export resolves an entry,
checks the PDF SHA-256, and stamps the version label and PDF last-modified date.
`BATATIS_SCC_FORM` overrides only the default entry's file path. The SHA check still applies.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = Path(__file__).resolve().parent / 'forms.json'


class FormRegistryError(Exception):
    pass


@dataclass(frozen=True)
class FormSpec:
    jurisdiction: str
    form_id: str
    version: str
    source_url: str
    pdf_last_modified: str
    page_count: int
    field_count: int
    sha256: str
    field_map_path: Path
    local_path: Path
    note: str

    @property
    def label(self) -> str:
        return f'{self.jurisdiction}/{self.form_id} ({self.version})'


def load_registry(path: Path | str | None = None) -> dict:
    src = Path(path) if path else REGISTRY_PATH
    if not src.is_file():
        raise FormRegistryError(f'form registry not found at {src}')
    data = json.loads(src.read_text())
    if 'forms' not in data or 'default' not in data:
        raise FormRegistryError(f'{src} must contain "default" and "forms"')
    return data


def resolve_form(jurisdiction: str | None = None, form_id: str | None = None, *,
                 registry: Path | str | None = None) -> FormSpec:
    """Pick one registered form. An explicit registry path ignores `BATATIS_SCC_FORM`."""
    reg = load_registry(registry)
    default = reg['default']
    jurisdiction = jurisdiction or os.environ.get('BATATIS_JURISDICTION') or default['jurisdiction']
    form_id = form_id or os.environ.get('BATATIS_FORM_ID') or default['form_id']
    try:
        raw = reg['forms'][jurisdiction][form_id]
    except KeyError:
        known = [f'{j}/{fid}' for j, forms in reg['forms'].items() for fid in forms]
        raise FormRegistryError(
            f'No form registered for jurisdiction {jurisdiction!r} form_id {form_id!r}. Known: {", ".join(known)}')
    field_map = Path(raw['field_map'])
    local = Path(raw['local_path'])
    if not field_map.is_absolute():
        field_map = ROOT / field_map
    if not local.is_absolute():
        local = ROOT / local
    is_default = jurisdiction == default['jurisdiction'] and form_id == default['form_id']
    if is_default and registry is None and os.environ.get('BATATIS_SCC_FORM'):
        local = Path(os.environ['BATATIS_SCC_FORM'])
    required = ('version', 'source_url', 'pdf_last_modified', 'page_count', 'field_count', 'sha256')
    missing = [k for k in required if raw.get(k) in (None, '')]
    if missing:
        raise FormRegistryError(f'{jurisdiction}/{form_id} is missing {", ".join(missing)}')
    return FormSpec(
        jurisdiction=jurisdiction, form_id=form_id, version=str(raw['version']),
        source_url=str(raw['source_url']), pdf_last_modified=str(raw['pdf_last_modified']),
        page_count=int(raw['page_count']), field_count=int(raw['field_count']),
        sha256=str(raw['sha256']), field_map_path=field_map, local_path=local,
        note=str(raw.get('note') or ''))
