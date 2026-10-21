"""JSON Schema for the engine's wire types, the single source for the web's TypeScript types.

    python -m engine.schema_export            # write web/src/api/engine.schema.json
    python -m engine.schema_export --check    # exit 1 when the committed schema is stale

The web turns this file into `web/src/api/types.gen.ts` (`npm run gen:types`; `npm run build` checks it).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from pydantic.json_schema import GenerateJsonSchema, models_json_schema

from .api import NewCase, SectionCRequest
from .code_library import CodeTOC, ProvisionContext
from .models import Case, Fact, SectionCRow
from .account_models import UserResult, MessagesResult
from .routes_auth import SignupRequest, LoginRequest, OnboardingRequest
from .routes_review import (NotificationsResult, ApplicationsResult, QueueResult, ClaimResult, ClaimRequest,
                            DecisionRequest, MessageRequest)
from .routes_assist import AssistRequest, AssistResult
from .identify.http_models import (BenchmarkConfirmRequest, IdentifyConfirmRequest, IdentifyDecisionRequest,
                                   IdentifyDecisionResponse, IdentifyRequest)
from .models_review import InformationRequestEdit, PackageReviewIndex, ReviewSession, SentInformationRequests
from .models_jurisdictions import JurisdictionDetail, JurisdictionsResult
from .routes_jurisdictions import CaseJurisdictionPack

OUT = Path(__file__).resolve().parent.parent / 'web' / 'src' / 'api' / 'engine.schema.json'
RESPONSES = (Case, SectionCRow, CodeTOC, ProvisionContext, UserResult, MessagesResult, ApplicationsResult,
             QueueResult, ClaimResult, AssistResult, NotificationsResult, IdentifyDecisionResponse,
             ReviewSession, PackageReviewIndex, SentInformationRequests,
             JurisdictionsResult, JurisdictionDetail, CaseJurisdictionPack)  # responses carry every field
REQUESTS = (Fact, NewCase, SectionCRequest, SignupRequest, LoginRequest, OnboardingRequest,
            ClaimRequest, DecisionRequest, MessageRequest, AssistRequest, InformationRequestEdit,
            IdentifyRequest, IdentifyDecisionRequest, IdentifyConfirmRequest, BenchmarkConfirmRequest)  # defaulted fields optional


class _ResponsesCarryDefaults(GenerateJsonSchema):
    """In serialization mode every field is required, because the engine always serializes it."""

    def field_is_required(self, field, total):
        return True if self.mode == 'serialization' else super().field_is_required(field, total)


def schema() -> dict:
    """Response models as `Name`; a request model whose input shape differs is `NameInput`."""
    _, defs = models_json_schema([(m, 'serialization') for m in RESPONSES] + [(m, 'validation') for m in REQUESTS],
                                 ref_template='#/$defs/{model}', schema_generator=_ResponsesCarryDefaults,
                                 title='Batatis engine wire types')
    rename = lambda n: re.sub(r'-Output$', '', re.sub(r'-Input$', 'Input', n))   # noqa: E731
    text = re.sub(r'"#/\$defs/([\w-]+)"', lambda m: f'"#/$defs/{rename(m.group(1))}"', json.dumps(defs))
    out = json.loads(text)
    out['$defs'] = {rename(k): v for k, v in out['$defs'].items()}
    return out


def render() -> str:
    return json.dumps(schema(), indent=2, sort_keys=True) + '\n'


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true', help='fail if the committed schema differs')
    ap.add_argument('--out', type=Path, default=OUT)
    a = ap.parse_args(argv)
    text = render()
    if a.check:
        if not a.out.exists() or a.out.read_text() != text:
            print(f'{a.out} is stale: run python -m engine.schema_export', file=sys.stderr)
            return 1
        return 0
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(text)
    print(f'wrote {a.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
