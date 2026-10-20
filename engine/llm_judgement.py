"""Provider-backed judgement for completeness classes that rules do not decide.

Quote verification lives here and does not depend on which provider produced the
quotes. A finding whose quote is not in the applicant document is dropped.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field

import httpx

from .ingest import Ingested, quote_matches_bytes

# Pinned model ids. Prices are USD per 1M tokens, standard (not batch), checked 2026-10-20.
# OpenAI: https://developers.openai.com/api/docs/pricing — gpt-4.1-mini $0.40 in / $1.60 out.
# Anthropic: https://platform.claude.com/docs/en/about-claude/pricing — claude-sonnet-5-5 $2 in / $10 out.
OPENAI_MODEL = 'gpt-4.1-mini'
ANTHROPIC_MODEL = 'claude-sonnet-5-5'
PRICES_PER_MILLION = {
    OPENAI_MODEL: {'input': 0.40, 'output': 1.60},
    ANTHROPIC_MODEL: {'input': 2.00, 'output': 10.00},
}

JUDGEMENT_FIELDS = (
    'risk_assessment', 'mitigating_measures', 'assumptions_and_limits',
    'section_b.consistency', 'section_c.relevance', 'supporting_doc', 'section_c.intent',
)

_SYSTEM = """You review administrative completeness of an Alberta alternative-solution (variance) application.
You do not decide whether the design is safe, code-compliant, or approved.
Look only for these problems, and only when the applicant's own words show them:
- D09 generic risk assessment (for example "low risk") that is not about the departure
- D10 mitigating measures that are missing, generic, or unrelated to the departure
- D11 assumptions stated as verified facts, or left blank
- D14 a Section B fact that contradicts an attachment — quote BOTH spans and do not pick which is correct
- D15 a cited provision that does not address the described departure
- D13 a supporting document with no responsible person, or a placeholder such as "to follow" or a brochure only
Quote the applicant's words verbatim. Do not invent article numbers, STANDATA numbers, test results, or professional opinions.
Do not draft the missing risk assessment, mitigations, or assumptions.
Return JSON: {"findings":[{"field":"...","defect_class":"D09","problem":"generic","verdict":"unclear","reason":"...","quotes":["..."]}]}
verdict is only "unclear" or "missing". If nothing applies, return {"findings":[]}.
"""


@dataclass
class LLMUsage:
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    dropped: int = 0

    @property
    def usd(self) -> float:
        price = PRICES_PER_MILLION.get(self.model)
        if not price:
            return 0.0
        return (self.input_tokens * price['input'] + self.output_tokens * price['output']) / 1_000_000


@dataclass
class LLMResult:
    text: str
    usage: LLMUsage


class LLMClient:
    def complete(self, system: str, user: str) -> LLMResult:  # pragma: no cover - interface
        raise NotImplementedError


def resolve_provider(explicit: str | None = None) -> str | None:
    """OpenAI is primary when its key is present. BATATIS_LLM_PROVIDER overrides the choice."""
    choice = (explicit if explicit is not None else os.environ.get('BATATIS_LLM_PROVIDER') or '').strip().lower()
    if choice:
        if choice not in ('openai', 'anthropic'):
            raise ValueError('BATATIS_LLM_PROVIDER must be openai or anthropic')
        return choice
    if os.environ.get('OPENAI_API_KEY'):
        return 'openai'
    if os.environ.get('ANTHROPIC_API_KEY'):
        return 'anthropic'
    return None


def provider_has_key(name: str | None) -> bool:
    if name == 'openai':
        return bool(os.environ.get('OPENAI_API_KEY'))
    if name == 'anthropic':
        return bool(os.environ.get('ANTHROPIC_API_KEY'))
    return False


def build_client(explicit: str | None = None) -> LLMClient | None:
    name = resolve_provider(explicit)
    if not provider_has_key(name):
        return None
    if name == 'openai':
        return OpenAIClient()
    return AnthropicClient()


def estimate_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    return LLMUsage(provider='', model=model, input_tokens=input_tokens, output_tokens=output_tokens).usd


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str | None = None, model: str = OPENAI_MODEL, timeout: float = 60):
        self.api_key = api_key or os.environ['OPENAI_API_KEY']
        self.model = model
        self.timeout = timeout

    def complete(self, system: str, user: str) -> LLMResult:
        started = time.perf_counter()
        response = httpx.post(
            'https://api.openai.com/v1/chat/completions',
            headers={'Authorization': f'Bearer {self.api_key}'},
            json={
                'model': self.model,
                'temperature': 0,
                'response_format': {'type': 'json_object'},
                'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        body = response.json()
        usage = body.get('usage') or {}
        return LLMResult(
            body['choices'][0]['message']['content'],
            LLMUsage('openai', self.model, int(usage.get('prompt_tokens') or 0),
                     int(usage.get('completion_tokens') or 0), time.perf_counter() - started),
        )


class AnthropicClient(LLMClient):
    def __init__(self, api_key: str | None = None, model: str = ANTHROPIC_MODEL, timeout: float = 90):
        self.api_key = api_key or os.environ['ANTHROPIC_API_KEY']
        self.model = model
        self.timeout = timeout

    def complete(self, system: str, user: str) -> LLMResult:
        started = time.perf_counter()
        response = httpx.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': self.api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            json={
                'model': self.model,
                'max_tokens': 4096,
                'system': system,
                'messages': [{'role': 'user', 'content': user}],
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        body = response.json()
        text = ''.join(block.get('text', '') for block in body.get('content') or [] if block.get('type') == 'text')
        usage = body.get('usage') or {}
        return LLMResult(
            text,
            LLMUsage('anthropic', self.model, int(usage.get('input_tokens') or 0),
                     int(usage.get('output_tokens') or 0), time.perf_counter() - started),
        )


class ScriptedClient(LLMClient):
    """Recorded or hand-written JSON. Wiring tests only. The harness never uses this."""

    def __init__(self, payload: dict):
        self.payload = payload

    def complete(self, system: str, user: str) -> LLMResult:
        return LLMResult(json.dumps(self.payload), LLMUsage('scripted', 'scripted', 12, 24, 0.001))


def _parse_findings(text: str) -> list[dict]:
    cleaned = text.strip()
    cleaned = re.sub(r'^```(?:json)?\s*|\s*```$', '', cleaned)
    try:
        body = json.loads(cleaned)
    except json.JSONDecodeError:
        return []
    findings = body.get('findings') if isinstance(body, dict) else None
    return [item for item in findings or [] if isinstance(item, dict)]


def quotes_verify(quotes: list[str], doc: Ingested, *, need: int) -> bool:
    if len(quotes) < need:
        return False
    return all(quote_matches_bytes(quote, doc.data, doc.text, ledger=doc.ledger) for quote in quotes if quote.strip())


def filter_findings(doc: Ingested, findings: list[dict]) -> tuple[list[dict], int]:
    """Drop any finding whose quotes do not verify. Provider-independent."""
    kept, dropped = [], 0
    for finding in findings:
        field_name = finding.get('field')
        if field_name not in JUDGEMENT_FIELDS:
            dropped += 1
            continue
        if finding.get('verdict') not in ('missing', 'unclear'):
            dropped += 1
            continue
        quotes = [quote for quote in finding.get('quotes') or [] if isinstance(quote, str)]
        need = 2 if field_name == 'section_b.consistency' or finding.get('defect_class') == 'D14' else 1
        if not quotes_verify(quotes, doc, need=need):
            dropped += 1
            continue
        finding = dict(finding)
        finding['quotes'] = quotes
        kept.append(finding)
    return kept, dropped


def judge_document(doc: Ingested, client: LLMClient) -> tuple[list[dict], LLMUsage]:
    user = 'Applicant document:\n' + doc.text[:120000]
    result = client.complete(_SYSTEM, user)
    kept, dropped = filter_findings(doc, _parse_findings(result.text))
    result.usage.dropped = dropped
    return kept, result.usage
