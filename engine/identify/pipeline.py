"""Identification used by POST /cases/{id}/identify: screen -> rerank -> verify -> commit or quoted choices.

Ported from PR #12 (engine/identify/pipeline.py) and rebuilt around one IdentifyConfig:
  screen   Decisions (temporary default) or Jev judges every Division B article (2,080), or a lexical arm
  rerank   the top `rerank_n` re-judged by the configured provider, or a structured rerank, or none
  verify   OpenAI (default, GPT Luna) or Anthropic reads the full text of the top `verify_n` and picks
           with word-for-word quotes; a quote that is not in the article drops the pick
  commit   Part 9 only, calibrated threshold for this config, verifier picked, at most 3 (commit.py)
  choices  the top three uncommitted articles as quoted choices, any Part
If the model path fails, the run is ranked by keyword search (BM25), labelled, and commits nothing.

Every displayed article id is a codedb Division B article and every displayed quote is codedb text:
the verifier output is checked in verify.check_quotes and again here before anything is shown.
Nothing here writes the case; the route persists the result.
"""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from engine.codes import Codes
from engine.models_identify import (BenchmarkRecord, DroppedPick, IdentifyArticle, IdentifyResult, IdentifyTrace,
                                    OpenQuestion, QuotedChoice, StageRecord)
from engine.process_refs import process_refs
from engine.public_names import UNAVAILABLE, public_stage_model, public_text

from . import cards
from .commit import CommitPolicy, decide, load_policy
from .config import DIVISION_B_ARTICLES, IdentifyConfig, load_config
from .corpus import articles, bm25_rank, card
from .llm import OpenAIVerifier, score_candidates
from .providers import Transports, scoring_ask, transports as default_transports
from .requirement import benchmark as requirement_benchmark
from .screen import Judge
from .search_rank import rank_articles
from .verify import Pick, check_quotes, normalize

logger = logging.getLogger(__name__)
OnStage = Callable[[str, dict], None]
CHOICE_WHY = 'Your answer tells us whether this is the requirement your design departs from.'
NOT_NARROWED = ('I could not narrow this down. These are the closest articles; none is committed. '
                'Answer a question below, or choose the article your design departs from.')


class ScreenIncomplete(RuntimeError):
    pass


class StageUnavailable(RuntimeError):
    pass


@dataclass
class RunOutput:
    result: IdentifyResult
    screen: dict[str, float] | None        # every article's screen estimate (exhaustive model screens only)
    rerank: dict[str, float] | None


def description_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class _Stages:
    def __init__(self, on_stage: OnStage | None, log):
        self.on_stage, self.log, self.records = on_stage, log, []
        self.emitted: set[str] = set()

    def run(self, stage: str, method: str, model: str | None, fn):
        start, before = time.monotonic(), len(self.log.calls)
        record = StageRecord(stage=stage, method=method, model=model)
        try:
            return fn(record)
        finally:
            calls = self.log.calls[before:]
            record.seconds = round(time.monotonic() - start, 3)
            record.requests = max(record.requests, len(calls))
            record.input_tokens = sum(c['input_tokens'] for c in calls)
            record.output_tokens = sum(c['output_tokens'] for c in calls)
            self.records.append(record)

    def emit(self, stage: str, **payload):
        """One event per stage, in pipeline order. Payloads carry counts only, never prose or code text."""
        if stage in self.emitted:
            return
        self.emitted.add(stage)
        if self.on_stage:
            self.on_stage(stage, {'stage': stage, **payload})


def _lexical(method: str, prose: str, db: Path, arts: dict) -> list[str]:
    ranked = rank_articles(prose, db) if method == 'bm25_v3' else bm25_rank(prose, db)
    return [a for a in ranked if a in arts]


def _verifier(config: IdentifyConfig, tp: Transports, arts: dict, db: Path):
    if config.verifier == 'openai':
        if tp.openai is None:
            raise StageUnavailable(tp.unavailable.get('openai', 'OpenAI unavailable'))
        return OpenAIVerifier(tp.openai, arts, model=config.verifier_model, effort=config.verifier_effort)
    if tp.anthropic is None:
        raise StageUnavailable(tp.unavailable.get('anthropic', 'Anthropic unavailable'))
    from .verify import ClaudeVerifier
    return ClaudeVerifier(db, client=tp.anthropic, model=config.verifier_model, effort=config.verifier_effort)


def _rank(prose, db, arts, ids, config, tp, stages) -> tuple[list[tuple[str, float | None]], dict | None, dict | None, int]:
    """Model path: (ranked, screen scores, rerank scores, articles scored). Raises on any failure."""
    screen: dict[str, float] | None = None
    judge = None
    if config.exhaustive:
        judge = Judge(scoring_ask(tp, config.screen), chars=config.card_chars, attempts=2,
                      model=config.screen_model, method=config.screen)

        def do_screen(record):
            scores = judge.judge(prose, arts, ids)
            record.errors = judge.usage.errors
            missing = [a for a in ids if a not in scores]
            if len(ids) != DIVISION_B_ARTICLES or len(scores) != DIVISION_B_ARTICLES or missing:
                raise ScreenIncomplete(f'screen scored {len(scores)} of {DIVISION_B_ARTICLES} Division B articles')
            return scores
        screen = stages.run('screen', config.screen, config.screen_model, do_screen)
        pool = sorted(ids, key=lambda a: -screen[a])[:config.rerank_n]
        scored = len(screen)
    else:
        pool = stages.run('screen', config.screen, None, lambda r: _lexical(config.screen, prose, db, arts))[:config.rerank_n]
        if not pool:
            raise StageUnavailable('keyword screen found no article')
        scored = len(pool)
    stages.emit('screen', status='done', method=config.screen, articles=scored)

    rerank: dict[str, float] | None = None
    if config.rerank in ('decisions', 'jev'):
        if judge is None or judge.method != config.rerank:
            judge = Judge(scoring_ask(tp, config.rerank), chars=config.card_chars, attempts=2,
                          model=config.rerank_model, method=config.rerank)

        def do_rerank(record):
            before = judge.usage.requests
            out = judge.judge(prose, arts, pool)
            record.requests = judge.usage.requests - before
            record.detail = 'one request' if record.requests == 1 else f'{record.requests} requests'
            return out
        rerank = stages.run('rerank', config.rerank, config.rerank_model, do_rerank)
        ranked = sorted(((a, rerank[a]) for a in pool), key=lambda x: -x[1])
    elif config.rerank == 'openai':
        if tp.openai is None:
            raise StageUnavailable(tp.unavailable.get('openai', 'OpenAI unavailable'))
        scores, _ = stages.run('rerank', 'openai', config.rerank_model, lambda r: score_candidates(
            tp.openai, prose, arts, pool, model=config.rerank_model, chars=config.card_chars,
            effort=config.verifier_effort))
        rerank = dict(scores)
        ranked = sorted(scores, key=lambda x: -x[1]) + [(a, None) for a in pool if a not in rerank]
    else:
        ranked = [(a, screen[a] if screen else None) for a in pool]
    stages.emit('rerank', status='done' if config.rerank != 'none' else 'skipped', method=config.rerank,
                articles=len(ranked))
    return ranked, screen, rerank, scored


def _guard(picks: list[Pick], candidates: list[str], arts: dict) -> tuple[list[Pick], list]:
    """Second, independent quote check at the display boundary (the verifier adapters already ran one)."""
    return check_quotes(list(picks), candidates, arts)


def _in_article(quote: str | None, art: dict) -> bool:
    return bool(quote) and normalize(quote) in normalize(card(art, None))


def run(prose: str, *, codes: Codes, config: IdentifyConfig | None = None, transports: Transports | None = None,
        verifier=None, on_stage: OnStage | None = None, facts=(), policy: CommitPolicy | None = None,
        description_sha256: str | None = None, client_ip: str | None = None) -> RunOutput:
    """`prose` is the outbound (already redacted) description. `verifier` overrides the configured one (tests)."""
    config = config or load_config()
    tp = transports or default_transports(client_ip, scoring={config.screen, config.rerank},
                                          anthropic=config.verifier == 'anthropic')
    policy = policy or load_policy(config.config_hash)
    if policy.status == 'calibrated' and policy.config_hash != config.config_hash:
        policy = CommitPolicy('uncalibrated', 'calibration was fitted for a different pipeline config')
    db = Path(codes.db_path)
    arts = articles(db)
    ids = list(arts)
    t0 = time.monotonic()
    stages = _Stages(on_stage, tp.log)
    mode = 'fake' if tp.kind == 'fake' else 'live'
    fallback_reason = None
    screen = rerank = None
    try:
        ranked, screen, rerank, scored = _rank(prose, db, arts, ids, config, tp, stages)
        ranker = f'{config.screen} screen + {config.rerank} rerank'
    except Exception as error:
        fallback_reason = _reason(error)
        # The response says only that scoring was unavailable (engine/public_names.py); the cause is logged here.
        logger.warning('Identify model path unavailable, keyword fallback: %s', fallback_reason)
        mode = 'bm25_fallback'
        ranked = [(a, None) for a in stages.run('fallback', config.fallback, None,
                                                lambda r: _lexical(config.fallback, prose, db, arts))[:config.rerank_n]]
        scored, ranker = len(ranked), f'{config.fallback} fallback'
        stages.emit('screen', status='failed', method=config.screen, fallback=config.fallback)
        stages.emit('rerank', status='fallback', method=config.fallback, articles=len(ranked))
    fallback = mode == 'bm25_fallback'

    # Verify
    picks: list[Pick] = []
    dropped: list[DroppedPick] = []
    verifier_state = 'not run: keyword fallback' if fallback else 'not run: verifier off'
    verifier_ran = False
    candidates = [a for a, _ in ranked[:config.verify_n]]
    if not fallback and (verifier is not None or config.verifier != 'none'):
        def do_verify(record):
            v = verifier or _verifier(config, tp, arts, db)
            return v.verify(prose, candidates)
        try:
            checked = stages.run('verify', config.verifier, config.verifier_model, do_verify)
            keep, again = _guard(checked.picks, candidates, arts)
            picks = keep
            dropped = [DroppedPick(article=p.article, reason=why) for p, why in [*checked.dropped, *again]]
            verifier_ran = checked.stop_reason != 'refusal'
            verifier_state = (f'{len(picks)} picked, {len(dropped)} dropped' if verifier_ran
                              else 'refused: no picks')
        except Exception as error:
            verifier_state = f'failed: {_reason(error)}'
    stages.emit('verify', status='done' if verifier_ran else 'skipped', picks=len(picks), dropped=len(dropped))

    # Order: verifier picks lead, then rerank order
    prob = dict(ranked)
    by_pick = {p.article: p for p in picks}
    order = [p.article for p in picks] + [a for a, _ in ranked if a not in by_pick]
    order = [a for a in order if a in arts][:config.top_k]

    shown: list[IdentifyArticle] = []
    committed: list[str] = []
    for rank, article_id in enumerate(order, start=1):
        art = arts[article_id]
        pick = by_pick.get(article_id)
        if pick is not None and _in_article(pick.quote, art):
            quote, source = cards.flat(pick.quote), 'verifier'
            sentence_id, _ = cards.sentence_for_quote(codes, article_id, quote)
        else:
            sentence_id, text = cards.first_sentence(codes, article_id)
            quote, source = cards.short(text), ('codedb' if text else None)
        commit, why = decide(part=art['part'], probability=prob.get(article_id), fallback=fallback,
                             verifier_ran=verifier_ran, verifier_picked=pick is not None,
                             committed_so_far=len(committed), policy=policy)
        if commit:
            committed.append(article_id)
        objectives, functions, missing = cards.terms(codes, sentence_id or article_id)
        shown.append(IdentifyArticle(
            rank=rank, provision=article_id, provision_id=sentence_id, title=art['title'], part=art['part'],
            citation=cards.citation(codes, sentence_id or article_id), link=f'/code/{article_id}?division=B',
            quote=quote, quote_source=source, reason=cards.model_reason(pick.reason) if pick else None,
            probability=None if prob.get(article_id) is None else round(prob[article_id], 4),
            screen_probability=None if not screen else round(screen.get(article_id, 0.0), 4),
            verifier='picked' if pick else ('not_picked' if verifier_ran else 'not_run'),
            status='committed' if commit else ('fallback' if fallback else 'candidate'), commit_reason=why,
            objectives=objectives, functions=functions, attribution_missing=missing))

    choices: list[QuotedChoice] = []
    for item in shown:
        if len(choices) >= config.choices_k:
            break
        if item.status == 'committed' or not item.quote:
            continue
        if not fallback:
            item.status = 'choice'
        choices.append(QuotedChoice(
            id=f'choice_{item.provision}', provision=item.provision, provision_id=item.provision_id,
            title=item.title, part=item.part, citation=item.citation, quote=item.quote,
            question=f'The code says: "{item.quote}" Does your design do something different from this?'))
    questions = [OpenQuestion(id=c.id, field=f'identify.choice.{c.provision}', text=c.question, why=CHOICE_WHY,
                              provision=c.provision) for c in choices]
    stages.emit('questions', status='done', choices=len(choices), committed=len(committed))

    narrowed = bool(picks) and not fallback
    benchmark = _benchmark(shown, committed, narrowed, by_pick, codes, facts)
    log = tp.log
    trace = IdentifyTrace(
        config=config.as_dict(), config_hash=config.config_hash, exhaustive=config.exhaustive and not fallback,
        articles_expected=DIVISION_B_ARTICLES, articles_scored=scored, ranker=ranker, fallback_reason=fallback_reason,
        verifier=verifier_state, picks=[p.article for p in picks], dropped=dropped, stages=stages.records,
        spend=log.by_provider(), usd=round(log.usd(), 6), seconds=round(time.monotonic() - t0, 3))
    model_ids = {stage: public_stage_model(getattr(config, stage), pin)
                 for stage, pin in config.model_ids().items()}
    if fallback:
        model_ids = {'screen': None, 'rerank': None, 'verifier': None}
    # Models, providers and spend are named only here and in the log. The result reads them as neutral words.
    logger.info('Identify run detail: ranker=%s verifier=%s models=%s spend=%s', ranker, verifier_state, model_ids,
                log.by_provider())
    result = IdentifyResult(
        mode=mode, source={'live': 'live', 'fake': 'fake', 'bm25_fallback': 'bm25 fallback'}[mode],
        label=_label(mode, config, scored, public_text(fallback_reason, UNAVAILABLE)), narrowed=narrowed,
        message=None if narrowed else NOT_NARROWED, articles=shown, committed=committed, choices=choices,
        questions=[q.text for q in questions], open_questions=questions, benchmark=benchmark,
        process_refs=process_refs(codes), model_ids=model_ids, commit_policy=policy.view(), scored_at=_now(),
        description_sha256=description_sha256 or description_hash(prose), trace=trace)
    return RunOutput(result, screen if not fallback else None, rerank if not fallback else None)


def _reason(error: Exception) -> str:
    """Technical category only: never a provider body, a credential, or applicant prose."""
    from .providers import DecisionsProtocolError, GateClosed, ScoringUnavailable
    if isinstance(error, GateClosed):
        return f'{error.provider} gate: {error.source}'
    if isinstance(error, DecisionsProtocolError):
        return 'scoring response was refused or invalid'
    if isinstance(error, (ScreenIncomplete, StageUnavailable, ScoringUnavailable)):
        return str(error)
    cause = error.__cause__ or error
    return f'{type(error).__name__}/{type(cause).__name__}'


def _label(mode: str, config: IdentifyConfig, scored: int, fallback_reason: str | None) -> str:
    if mode == 'bm25_fallback':
        return (f'Ranked by keyword search ({config.fallback.upper()}) because the model path was unavailable '
                f'({fallback_reason}). Nothing is committed.')
    screen = (f'All {scored} Division B articles were scored' if config.exhaustive
              else f'Keyword search ({config.screen}) shortlisted {scored} articles')
    rerank = {'jev': f'; the top {config.rerank_n} were re-checked',
              'decisions': f'; the top {config.rerank_n} were re-checked',
              'openai': f'; the top {config.rerank_n} were re-checked', 'none': ''}[config.rerank]
    verify = '' if config.verifier == 'none' else f'; the top {config.verify_n} were read in full'
    fake = ' Offline fake providers: for testing only, not a measurement.' if mode == 'fake' else ''
    return f'{screen}{rerank}{verify}.{fake}'


def _benchmark(shown, committed, narrowed, by_pick, codes, facts) -> BenchmarkRecord:
    target = next((a for a in shown if a.provision in committed), None)
    basis = 'committed'
    if target is None and narrowed:
        target, basis = next((a for a in shown if a.verifier == 'picked'), None), 'top_choice'
    if target is None:
        return BenchmarkRecord(identified=False, question='Which of these requirements does your design depart from?')
    sentence = None
    if target.provision_id:
        sentence = cards.flat((cards.provision(codes, target.provision_id) or {}).get('text')) or None
    pick = by_pick.get(target.provision)
    departure = cards.model_reason(pick.reason) if pick else None
    objectives, functions, missing = cards.terms(codes, target.provision_id or target.provision)
    return BenchmarkRecord(
        identified=True, basis=basis, provision=target.provision, provision_id=target.provision_id,
        citation=target.citation, sentence=sentence or target.quote, departure=departure,
        departure_status='proposed' if departure else 'none', objectives=objectives, functions=functions,
        attribution_missing=missing,
        requirement=requirement_benchmark(target.provision_id, sentence, facts) if sentence else None,
        question='Is this the requirement your design departs from? Describe the departure in one line.')
