"""The JSON Schema for pack files, generated from `engine.models_jurisdictions`.

    python -m engine.jurisdictions.schema          # write engine/data/jurisdictions/pack.schema.json
    python -m engine.jurisdictions.schema --check  # exit 1 when the committed schema is stale

Every object has `additionalProperties: false`, so unknown keys are rejected.
"""
from __future__ import annotations

import argparse
import json
import sys

from pydantic.json_schema import models_json_schema

from ..models_jurisdictions import CoverageFile, JurisdictionPack, ProvinceShared
from . import DATA_DIR

OUT = DATA_DIR / 'pack.schema.json'
FILES = {'packs/*.json': JurisdictionPack, 'provinces/*.json': ProvinceShared, 'coverage.json': CoverageFile}


def schema() -> dict:
    _, defs = models_json_schema([(m, 'validation') for m in FILES.values()], ref_template='#/$defs/{model}',
                                 title='Batatis jurisdiction pack files')
    defs['$schema'] = 'https://json-schema.org/draft/2020-12/schema'
    defs['description'] = ('Generated from engine/models_jurisdictions.py. Files: '
                           + '; '.join(f'{glob} is {model.__name__}' for glob, model in FILES.items()) + '.')
    return defs


def render() -> str:
    return json.dumps(schema(), indent=2, sort_keys=True) + '\n'


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    text = render()
    if args.check:
        if not OUT.is_file() or OUT.read_text() != text:
            print(f'{OUT} is stale; run python -m engine.jurisdictions.schema', file=sys.stderr)
            return 1
        return 0
    OUT.write_text(text)
    print(f'wrote {OUT}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
