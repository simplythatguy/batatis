"""The system under test: what the engine does when someone pastes a case's prompt and attaches its files.

The route order is reproduced in process, with the engine's own functions and no shortcuts:
intake (rules, forms, then the model pass), identification (configured screen, rerank and verifier,
or the keyword fallback when a stage is unavailable), the plan refresh, and the completeness gaps.
Only `Case.prompt` and the default-input attachments reach the engine. The output is what the API
returns for that case, so the report can only use what an applicant or officer could be shown.

Two deliberate differences from the hosted app, both recorded on every result: the 4 MB upload limit
is not applied (it is a hosting limit, counted separately), and there is no signed-in account, so no
account names are scrubbed (the cases contain no applicant account).
"""
from __future__ import annotations

import os
import time
import traceback
from pathlib import Path

from . import ledger
from .corpus import Case

UPLOAD_LIMIT = 4 * 1024 * 1024


class _Skipped(Exception):
    pass


def load_env(path: str | None = None) -> None:
    """Read provider keys from a private .env into this process only. Values are never printed."""
    path = path or os.environ.get('DPE_ENV_FILE')
    if not path:
        return
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        name, value = line.split('=', 1)
        name = name.strip()
        if name in ('OPENAI_API_KEY', 'OPENROUTER_API_KEY', 'JEV_API_KEY', 'TYPESAFE_API_KEY'):
            os.environ.setdefault(name, value.strip().strip('"').strip("'"))


def configure(*, live: bool, elephant: bool) -> None:
    """Engine switches for an unattended run: live OpenAI, Elephant on or off, local caps out of the way."""
    os.environ['BATATIS_LIVE'] = '1' if live else '0'
    os.environ['BATATIS_LIVE_ELEPHANT'] = '1' if (live and elephant) else '0'
    os.environ.pop('BATATIS_PROVIDER', None)
    os.environ['BATATIS_DAILY_SPEND_CAP_USD'] = os.environ.get('DPE_SPEND_CAP_USD', '500')
    os.environ['BATATIS_LLM_RATE_LIMIT'] = '1000000'
    os.environ['BATATIS_LLM_RATE_WINDOW_SECONDS'] = '1'
    os.environ.setdefault('BATATIS_STORE', 'file')
    os.environ['BATATIS_JEV_UNCAPPED'] = '1'          # the engine's own switch: Jev is outside the dollar ledger
    ledger.install(read=os.environ.get('DPE_HTTP_CACHE', 'read') != 'refresh')


def init_worker(live: bool, elephant: bool) -> None:
    load_env()
    configure(live=live, elephant=elephant)


def run_case(case: Case) -> dict:
    """One case through the engine. Never raises: failures are recorded in the result."""
    from engine.codes import Codes, default_db
    from engine.completeness import check_completeness
    from engine.identify.config import load_config
    from engine.identify.pipeline import description_hash, run as identify_run
    from engine.intake import model as model_pass
    from engine.intake import review as review_pass
    from engine.intake import service
    from engine.intake.extract import scrubbed
    from engine.intake.plan import description
    from engine.models import Case as EngineCase
    from engine.redact import known_values, scrub

    book = ledger.Ledger()
    token = ledger.CURRENT.set(book)
    started = time.monotonic()
    stages: dict[str, float] = {}
    result: dict = {'case_id': case.id, 'errors': []}
    try:
        codes = Codes(default_db())
        files = [(f'file{i + 1}', a.filename, case.read(a)) for i, a in enumerate(case.attachments)]
        result['over_upload_limit'] = [name for _, name, data in files if len(data) > UPLOAD_LIMIT]
        engine_case = EngineCase()
        transport, status = model_pass.default_transport('dpe')
        review_transport, review_status = review_pass.default_transport('dpe') if files else (None, 'off')
        if files and os.environ.get('DPE_REVIEW_TRANSPORT') == 'opencode':    # comparison runs only
            from .opencode_review import transport as opencode_transport
            review_transport, review_status = opencode_transport, 'live'
        t = time.monotonic()
        known = known_values(engine_case, [])
        extraction = service.run(case.prompt, files, codes=codes, transport=transport, status=status,
                                 outbound=lambda text, personal: scrubbed(text, [*known, *personal]),
                                 review_transport=review_transport, review_status=review_status)
        service.apply(engine_case, case.prompt, extraction)
        stages['intake'] = time.monotonic() - t

        t = time.monotonic()
        text = description(engine_case)
        outbound = scrub(text, known_values(engine_case, []))
        plan = engine_case.intake.plan if engine_case.intake else None
        redirected = bool(plan and plan.scope.status == 'redirect')    # the web skips identification then
        result['identify_skipped'] = redirected
        try:
            if redirected:
                raise _Skipped()
            output = identify_run(outbound, codes=codes, config=load_config(), facts=engine_case.facts,
                                  description_sha256=description_hash(text), client_ip='dpe')
            engine_case.identify = output.result
            trace = output.result.trace
            result['identify_spend'] = {'usd': trace.usd, 'by_provider': trace.spend}
            # Every article's screen and rerank score, kept for the hand-off threshold study (never judged).
            result['identify_scores'] = {'screen': output.screen, 'rerank': output.rerank}
        except _Skipped:
            pass
        except Exception as error:                     # the route answers 503; the case keeps its intake
            result['errors'].append(f'identify: {type(error).__name__}: {error}'[:300])
        stages['identify'] = time.monotonic() - t

        service.refresh(engine_case)
        gaps = check_completeness(engine_case, codes)
        result['case'] = engine_case.model_dump(mode='json')
        result['gaps'] = [g.model_dump(mode='json') for g in gaps]
    except Exception as error:
        result['errors'].append(f'run: {type(error).__name__}: {error}'[:300])
        result['traceback'] = traceback.format_exc()[-2000:]
    finally:
        ledger.CURRENT.reset(token)
    result['seconds'] = round(time.monotonic() - started, 3)
    result['stage_seconds'] = {k: round(v, 3) for k, v in stages.items()}
    result['cost'] = ledger.as_dict(book)
    return result
