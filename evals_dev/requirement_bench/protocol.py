"""Input-only predictor interface; deliberately independent of manifests and answer keys.

Adapters consume exported JSONL requests and return captured prediction records. They must
run outside the scoring process. This protocol is a data seam, not an OS access sandbox.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Protocol, TypedDict

VERSION = 1
LAYERS = ('retrieval_candidates', 'identified_requirements', 'application_included', 'applicant_visible')
REFERENCE_FIELDS = {'document', 'edition', 'printing', 'division', 'provision'}
BINDING_FIELDS = {'schema_version', 'run_id', 'case_id', 'manifest_sha256', 'input_sha256',
                  'input_payload_sha256', 'config_sha256', 'catalog_sha256'}


class Invalid(ValueError):
    """An artifact violates the evaluation contract."""


class PredictorRequest(TypedDict):
    schema_version: int
    run_id: str
    case_id: str
    manifest_sha256: str
    input_sha256: str
    input_payload_sha256: str
    config_sha256: str
    catalog_sha256: str
    input: dict


class Predictor(Protocol):
    def __call__(self, request: PredictorRequest, /) -> dict:
        """Return one prediction with the request's bindings and four evidence layers."""
        ...


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Invalid(message)


def shape(value, fields: set[str], where: str) -> dict:
    require(isinstance(value, dict) and set(value) == fields, f'{where}: expected fields {sorted(fields)}')
    return value


def nonempty(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def fingerprint(value) -> str:
    return digest_bytes(canonical(value))


def hash_file(path: Path) -> str:
    with path.open('rb') as stream:
        h = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
        return h.hexdigest()


def is_hash(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def _pairs(pairs):
    out = {}
    for key, value in pairs:
        require(key not in out, f'duplicate JSON key: {key}')
        out[key] = value
    return out


def loads(text: str):
    def bad_constant(value):
        raise Invalid(f'non-finite JSON number: {value}')
    def finite_float(token):
        value = float(token)
        require(math.isfinite(value), 'non-finite JSON number')
        return value
    try:
        return json.loads(text, object_pairs_hook=_pairs, parse_constant=bad_constant, parse_float=finite_float)
    except Invalid:
        raise
    except (ValueError, UnicodeError, RecursionError) as error:
        raise Invalid('malformed JSON') from error


def read_json(path: Path):
    try:
        return loads(path.read_text(encoding='utf-8'))
    except UnicodeError as error:
        raise Invalid('invalid UTF-8 JSON') from error


def write_json(path: Path, value) -> None:
    """Refuse accidental overwrite of sealed inputs, keys, and past run artifacts."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def child(root: Path, relative: str) -> Path:
    require(nonempty(relative), 'empty artifact path')
    try:
        rel = Path(relative)
        path = (root / rel).resolve()
    except (OSError, ValueError, RuntimeError) as error:
        raise Invalid('invalid artifact path') from error
    require(not rel.is_absolute() and path.is_relative_to(root.resolve()), 'artifact path escapes bundle')
    require(path.is_file(), f'artifact missing: {relative}')
    return path


def file_ref(root: Path, relative: str) -> dict:
    return {'path': relative, 'sha256': hash_file(child(root, relative))}


def checked_ref(root: Path, ref: dict) -> Path:
    shape(ref, {'path', 'sha256'}, 'file reference')
    require(is_hash(ref['sha256']), 'invalid file hash')
    path = child(root, ref['path'])
    require(hash_file(path) == ref['sha256'], f'artifact hash changed: {ref["path"]}')
    return path


def number(value, *, integer=False, nullable=True) -> bool:
    if value is None:
        return nullable
    if type(value) not in ((int,) if integer else (int, float)) or value < 0:
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def reference(value) -> tuple:
    shape(value, REFERENCE_FIELDS, 'reference')
    require(nonempty(value['document']) and nonempty(value['provision']), 'reference needs document and provision')
    require(all(v is None or nonempty(v) for v in (value['edition'], value['printing'])), 'invalid edition/printing')
    require(value['division'] in ('A', 'B', 'C', None), 'invalid division')
    return tuple(value[k] for k in sorted(REFERENCE_FIELDS))


def validate_input(value: dict, case_id: str) -> None:
    shape(value, {'schema_version', 'case_id', 'narrative', 'facts', 'attachments'}, 'predictor input')
    require(type(value['schema_version']) is int and value['schema_version'] == VERSION, 'input version')
    require(value['case_id'] == case_id and nonempty(case_id), 'input case id')
    require(nonempty(value['narrative']), 'input narrative is empty')
    require(isinstance(value['facts'], list), 'input facts must be a list')
    for fact in value['facts']:
        shape(fact, {'field', 'value'}, 'input fact')
        require(nonempty(fact['field']) and isinstance(fact['value'], str), 'invalid input fact')
        require(fact['field'].casefold() not in {
            'gold', 'answer', 'expected', 'review_focus', 'known_outcome', 'requirements', 'evaluation',
        }, 'answer-like fact field is forbidden')
    require(isinstance(value['attachments'], list), 'input attachments must be a list')
    for attachment in value['attachments']:
        shape(attachment, {'path', 'sha256', 'media_type'}, 'input attachment')
        require(nonempty(attachment['media_type']) and is_hash(attachment['sha256']), 'invalid attachment metadata')


def validate_request(packet: dict) -> None:
    """Predictors can verify inline input integrity without seeing a manifest or key."""
    shape(packet, BINDING_FIELDS | {'input'}, 'predictor request')
    require(type(packet['schema_version']) is int and packet['schema_version'] == VERSION, 'request version')
    require(nonempty(packet['run_id']) and nonempty(packet['case_id']), 'request run/case id missing')
    for field in BINDING_FIELDS - {'schema_version', 'run_id', 'case_id'}:
        require(is_hash(packet[field]), f'invalid request {field}')
    validate_input(packet['input'], packet['case_id'])
    require(fingerprint(packet['input']) == packet['input_payload_sha256'], 'inline input payload hash changed')
