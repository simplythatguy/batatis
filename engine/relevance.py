"""Relevance orchestration over configured exhaustive article scoring and rerank."""
from __future__ import annotations

import hashlib
import os
import threading
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from .identify import Identification, Judge
from .identify.screen import DECISIONS_MODEL, ELEPHANT_MODEL, JEV_MODEL
from .models import Case
from .public_names import public_stage_model
from .relevance_models import DECISIONS_PUBLIC_MODEL, ELEPHANT_PUBLIC_MODEL, PUBLIC_MODEL, RelevanceBands, RelevanceRecord

BANDS_FILE = Path(__file__).with_name('identify') / 'relevance_bands.json'
PUBLIC_MODEL_VERSIONS = {JEV_MODEL: PUBLIC_MODEL, DECISIONS_MODEL: DECISIONS_PUBLIC_MODEL,
                         ELEPHANT_MODEL: ELEPHANT_PUBLIC_MODEL}


def public_model(pin: str) -> str:
    """The version clients see for a scoring model pin. An unmapped pin raises; it is never passed through."""
    try:
        return PUBLIC_MODEL_VERSIONS[pin]
    except KeyError:
        raise ValueError('the scoring model has no public version') from None


class RelevanceUnavailable(RuntimeError):
    pass


class RelevanceInProgress(RuntimeError):
    pass


class CaseScorings:
    """Reject duplicate work while a case is scoring; finished case ids are removed."""

    def __init__(self):
        self._active: set[str] = set()
        self._lock = threading.Lock()

    @contextmanager
    def claim(self, case_id: str):
        with self._lock:
            if case_id in self._active:
                raise RelevanceInProgress()
            self._active.add(case_id)
        try:
            yield
        finally:
            with self._lock:
                self._active.remove(case_id)


def live_judge() -> Judge:
    from . import llm_gate, provider_routing
    from .identify.config import load_config
    from .identify.providers import scoring_ask, transports
    config = load_config()
    if config.screen == 'requirements':
        # Requirement discovery is deterministic; the Code Library keeps the historical Jev relevance arm.
        config = replace(config, screen='jev', screen_model=JEV_MODEL)
    if not provider_routing.local_active() and not llm_gate.fake_providers() and os.environ.get('BATATIS_LIVE') != '1' \
            and not (config.screen == 'elephant' and llm_gate.provider_enabled('elephant')):
        raise RelevanceUnavailable('BATATIS_LIVE is disabled')
    if not config.exhaustive:
        raise RelevanceUnavailable('relevance requires exhaustive scoring')
    tp = transports(scoring={config.screen, config.rerank})
    try:
        judge = Judge(scoring_ask(tp, config.screen), chars=config.card_chars,
                      model=config.screen_model, method=config.screen,
                      question_style=config.question_style if config.screen == 'elephant' else 'shared')
    except RuntimeError:
        raise RelevanceUnavailable('configured scoring credential is absent or disabled') from None
    judge.config = config
    judge.transports = tp
    return judge


def description(case: Case) -> str:
    """The latest description fact wins, including an explicit empty replacement.

    identify() accepts caller prose and has no existing intake-answer composer. Do not
    silently send administrative facts or evidence descriptions to the scoring provider.
    """
    fact = next((fact for fact in reversed(case.facts) if fact.field == 'project.description'), None)
    return fact.value if fact is not None and isinstance(fact.value, str) else ''


def description_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def current_record(record: RelevanceRecord, case: Case) -> RelevanceRecord:
    return record.model_copy(update={'stale': record.description_sha256 != description_hash(description(case))})


def display_probabilities(scores: dict[str, float], rerank: dict[str, float]) -> dict[str, float]:
    """The single display policy: rerank when present (including zero), otherwise screen."""
    return {article: rerank.get(article, probability) for article, probability in scores.items()}


def relevance_record(result: Identification, text: str, scored_at: str) -> RelevanceRecord:
    rerank = dict(result.ranked)
    models = {stage: public_stage_model(result.methods.get(stage, 'jev'), model)
              for stage, model in result.model_ids.items()}
    return RelevanceRecord(
        model=public_model(result.model), scored_at=scored_at, description_sha256=description_hash(text),
        config_hash=result.config_hash, model_ids=models,
        scores=result.screen, rerank=rerank, display=display_probabilities(result.screen, rerank),
        bands=scoring_bands(public_model(result.model), models, result.config_hash))


def scoring_bands(model: str, model_ids: dict, config_hash: str | None) -> RelevanceBands:
    """Historical Jev bands stay historical; other configurations have no fitted relevance thresholds."""
    from .identify.config import IdentifyConfig
    historical_config = IdentifyConfig(screen='jev', screen_model=JEV_MODEL, rerank='jev', rerank_model=JEV_MODEL)
    if model == PUBLIC_MODEL and config_hash == historical_config.config_hash \
            and all(pin in (JEV_MODEL, PUBLIC_MODEL) for pin in model_ids.values()):
        return RelevanceBands.model_validate_json(BANDS_FILE.read_text(encoding='utf-8'))
    return RelevanceBands(x=0.0, y=1.0, status='uncalibrated; display range only')
