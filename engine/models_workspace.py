"""Applicant signatures and edit history, separate from the append-only fact ledger."""
from __future__ import annotations

import base64
import binascii
import io
from typing import Literal

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, field_validator

SignerRole = Literal['owner', 'owner_rep']
SIGNATURE_MAX_BYTES = 200 * 1024


class SignatureInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=500, strict=True)
    method: Literal['drawn', 'typed']
    image: str = Field(max_length=4 * ((SIGNATURE_MAX_BYTES + 2) // 3) + 22, strict=True)

    @field_validator('name')
    @classmethod
    def _name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Enter the signer name.')
        return value

    @field_validator('image')
    @classmethod
    def _png(cls, value):
        if not value.startswith('data:image/png;base64,'):
            raise ValueError('Use a PNG signature image.')
        try:
            data = base64.b64decode(value.split(',', 1)[1], validate=True)
            if len(data) > SIGNATURE_MAX_BYTES:
                raise ValueError('Signature images must be at most 200 KB.')
            with Image.open(io.BytesIO(data)) as image:
                if image.format != 'PNG' or image.width * image.height > 4_000_000:
                    raise ValueError('Use a PNG signature image of at most four million pixels.')
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                image.load()
        except (binascii.Error, OSError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError) as error:
            raise ValueError('Use a valid PNG signature image.') from error
        return value


class WorkspaceSignature(BaseModel):
    """A saved signature. Its image was checked once on the way in (SignatureInput); loading a case never decodes it."""
    name: str
    method: Literal['drawn', 'typed']
    image: str
    role: SignerRole
    signed_on: str
    content_hash: str


class SignatureView(WorkspaceSignature):
    current: bool


class WorkspaceConsent(BaseModel):
    agreed: bool = Field(strict=True)
    at: str


class HistoryEntry(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=200, strict=True)
    at: str = Field(min_length=1, max_length=100, strict=True)
    block: str = Field(min_length=1, max_length=200, strict=True)
    label: str = Field(max_length=500, strict=True)
    before: str = Field(max_length=60000, strict=True)
    after: str = Field(max_length=60000, strict=True)
    by: Literal['you', 'ai', 'restore']


HISTORY_MAX_ENTRIES = 300
HISTORY_MAX_CHARS = 1_000_000   # every case read carries the history, so it stays small


def trim_history(entries: list[HistoryEntry]) -> list[HistoryEntry]:
    """The newest entries, one per id (a retried batch is not stored twice), within both limits."""
    unique = list({entry.id: entry for entry in entries}.values())[-HISTORY_MAX_ENTRIES:]
    kept, size = [], 0
    for entry in reversed(unique):
        size += len(entry.before) + len(entry.after)
        if size > HISTORY_MAX_CHARS and kept:
            break
        kept.append(entry)
    return list(reversed(kept))


class Workspace(BaseModel):
    signatures: list[WorkspaceSignature] = Field(default_factory=list)
    consent: WorkspaceConsent | None = None
    history: list[HistoryEntry] = Field(default_factory=list)


class WorkspaceSigner(BaseModel):
    role: SignerRole
    name: str
    required: bool = True


class WorkspaceView(BaseModel):
    content_hash: str
    signers: list[WorkspaceSigner]
    signatures: list[SignatureView]
    consent: WorkspaceConsent | None
    history: list[HistoryEntry]
