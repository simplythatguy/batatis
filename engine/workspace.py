"""The content a signer attests to; workspace metadata cannot invalidate itself."""
from __future__ import annotations

import hashlib
import json

from .models import Case
from .models_workspace import SignatureView, WorkspaceSigner, WorkspaceView
from .not_applicable import not_applicable
from .process_fields import confirmed_value

_SIGNING_FACTS = frozenset({'date', 'request_date', 'application_date', 'section_a.date',
                           'owner_signature', 'owner_signature_date', 'owner_rep_signature',
                           'owner_rep_signature_date', 'consent'})


def content_hash(case: Case) -> str:
    latest = {fact.field: fact for fact in case.facts}
    facts = {key: fact.value for key, fact in latest.items()
             if fact.export()['status'] == 'confirmed' and key not in _SIGNING_FACTS
             and not key.startswith(('signature.', 'signatures.', 'consent.', 'workspace.'))}
    content = {'facts': facts, 'provisions': case.provisions,
               'section_c': [row.model_dump() for row in case.section_c],
               'documents': [item.model_dump() for item in case.evidence],
               'jurisdiction': case.jurisdiction.model_dump() if case.jurisdiction else None}
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def signers(case: Case) -> list[WorkspaceSigner]:
    owner = confirmed_value(case, 'owner_name', 'owner', 'section_a.owner_name')
    representative = confirmed_value(case, 'owner_rep_name', 'representative', 'applicant_name')
    result = [WorkspaceSigner(role='owner', name=str(owner or ''))]
    if representative and str(representative).strip() and 'owner_rep_name' not in not_applicable(case):
        result.append(WorkspaceSigner(role='owner_rep', name=str(representative)))
    return result


def workspace_view(case: Case) -> WorkspaceView:
    digest = content_hash(case)
    return WorkspaceView(content_hash=digest, signers=signers(case),
                         signatures=[SignatureView(**signature.model_dump(), current=signature.content_hash == digest)
                                     for signature in case.workspace.signatures],
                         consent=case.workspace.consent, history=list(reversed(case.workspace.history)))
