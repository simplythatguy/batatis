"""Relevance orchestration over the existing exhaustive Jev screen and top-60 rerank."""
from __future__ import annotations

import hashlib
import os
import threading
from contextlib import contextmanager
from pathlib import Path

from .identify import Identification, Judge
from .identify.jevkit import keystore
from .identify.screen import JEV_PROVIDER
from .models import Case
from .public_names import MODEL_VERSIONS as PUBLIC_MODEL_VERSIONS
from .relevance_models import RelevanceBands, RelevanceRecord

BANDS_FILE = Path(__file__).with_name('identify') / 'relevance_bands.json'


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
    # Jev has its own credentials; an unrelated OpenAI key must not enable/disable it.
    if os.environ.get('BATATIS_LIVE') != '1':
        raise RelevanceUnavailable('BATATIS_LIVE is disabled')
    if not keystore.resolve(JEV_PROVIDER):
        raise RelevanceUnavailable('TypeSafe credential is absent')
    return Judge()


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
    return RelevanceRecord(
        model=public_model(result.model), scored_at=scored_at, description_sha256=description_hash(text),
        scores=result.screen, rerank=rerank, display=display_probabilities(result.screen, rerank),
        bands=RelevanceBands.model_validate_json(BANDS_FILE.read_text()))
