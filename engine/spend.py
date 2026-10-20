"""Total spend cap, and the only OpenAI HTTP call in this repository.

Live calls require ``BATATIS_LIVE=1`` and ``OPENAI_API_KEY``. Live mode is
OpenAI only: ``BATATIS_LLM_PROVIDER=anthropic`` is refused when live is on.
The running total lives in Postgres (``DATABASE_URL``, or ``POSTGRES_URL``
when that is unset), in one table, ``spend_ledger``. There is no daily cap.
``BATATIS_DAILY_SPEND_CAP_USD`` is ignored.

``openai_chat_json`` is the only function that posts to the provider. It
estimates input tokens from the messages it was given, always sends
``max_completion_tokens``, and reserves the priced worst case: the model's
input rate times that estimate, plus its output rate times
``max_completion_tokens``. A model missing from the price table is refused
before any request. The ``model`` on the response must be the model that was
sent. The reservation inserts a row only when settled spend plus open
reservations plus this estimate is within ``BATATIS_TOTAL_BUDGET_USD``
(default 20). Postgres takes a transaction advisory lock in the statement
before that insert, and holds it until commit, so concurrent instances cannot
pass the check together. After the provider returns, the row is settled to the
cost of validated reported tokens. Ambiguous errors retain the full reservation;
no automatic refund, retry, or age-based release is permitted.

Only text messages and bounded JSON response formats are supported. Input is
bounded by the UTF-8 bytes of the complete serialized request, plus framing
allowance. Dated models and the standard service tier are pinned. Output is
bounded in the actual request, not merely declared by the caller.

No database, a database error, an unknown model, or a full cap refuses the
call and leaves the offline path to answer. Those refusals are not HTTP 5xx.
The API key is read from the environment inside the request and is not logged.
The code database is never opened here; a URL that points at ``codedb.sqlite``
is refused.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import urllib.error
import urllib.request
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel

log = logging.getLogger(__name__)

# USD per 1,000,000 tokens, standard rate (not batch, not fine-tune): input, output.
# Source: https://developers.openai.com/api/docs/pricing (Standard table) and the
# gpt-4.1 model page, checked 2026-10-20. The dated ids are that page's default
# snapshots of the same models, not fine-tunes, so they use the same rates.
# The reservation uses these full rates. Cached-input discounts are not applied,
# so the ledger does not under-count a call that hit the cache.
MODEL_PRICES: dict[str, tuple[Decimal, Decimal]] = {
    'gpt-4.1': (Decimal('2.00'), Decimal('8.00')),
    'gpt-4.1-2025-04-14': (Decimal('2.00'), Decimal('8.00')),
    'gpt-4.1-mini': (Decimal('0.40'), Decimal('1.60')),
    'gpt-4.1-mini-2025-04-14': (Decimal('0.40'), Decimal('1.60')),
}
_MODEL_SNAPSHOTS = {
    'gpt-4.1': 'gpt-4.1-2025-04-14',
    'gpt-4.1-mini': 'gpt-4.1-mini-2025-04-14',
}
_MAX_OUTPUT_TOKENS = 32_768
_CONTEXT_TOKENS = 1_047_576
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024

# Route names stored on ledger rows. Every live OpenAI call goes through
# openai_chat_json in this file.
ROUTE_IDENTIFY_RERANK = 'identify.rerank'
ROUTE_IDENTIFY_VERIFY = 'identify.verify'
ROUTE_IDENTIFY_SCREEN = 'identify.screen'
ROUTE_COMPLETENESS = 'completeness.judge'
ROUTE_SECTION_D = 'section_d'

CAP_NOTICE = (
    "Live AI is off: the demo's spending limit has been reached. Showing offline results."
)
LEDGER_NOTICE = (
    'Live AI is off: the spending limit could not be checked. Showing offline results.'
)
UNPRICED_NOTICE = (
    'Live AI is off: this model has no price on file, so the call was refused. '
    'Showing offline results.'
)

_SCALE = Decimal('1000000')
_PLACES = Decimal('0.000001')
_CENTS = Decimal('0.01')
_DEFAULT_CAP = Decimal('20')
# Arbitrary constant. Serializes reservation statements across connections.
_ADVISORY_LOCK = 82420020

_USED_MICRO = """
COALESCE(SUM(
  CASE
    WHEN status = 'settled' THEN CAST(REPLACE(actual_usd, '.', '') AS BIGINT)
    WHEN status = 'reserved' THEN CAST(REPLACE(est_usd, '.', '') AS BIGINT)
    ELSE 0
  END
), 0)"""

# One statement. The cap predicate is the WHERE clause. SQLite runs it inside
# BEGIN IMMEDIATE, which is what makes the check atomic on the test double.
SQLITE_RESERVE_SQL = f"""
INSERT INTO spend_ledger (ts, route, model, est_usd, actual_usd, status)
SELECT ?, ?, ?, ?, NULL, 'reserved'
WHERE (SELECT {_USED_MICRO} FROM spend_ledger) + ? <= ?
RETURNING id
"""

# The cap check is its own statement. The lock is the statement before it,
# in the same transaction. A join of pg_advisory_xact_lock onto the sum is
# not ordered: Postgres 16 planned the aggregate first and three $0.40
# reservations passed a $1 cap. Two statements on one connection are ordered,
# and the transaction lock is held until commit.
POSTGRES_LOCK_SQL = 'SELECT pg_advisory_xact_lock(%s)'
POSTGRES_RESERVE_SQL = f"""
INSERT INTO spend_ledger (ts, route, model, est_usd, actual_usd, status)
SELECT %s, %s, %s, %s, NULL, 'reserved'
WHERE (SELECT {_USED_MICRO} FROM spend_ledger) + %s <= %s
RETURNING id
"""

_SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS spend_ledger (
  id INTEGER PRIMARY KEY,
  ts TEXT NOT NULL,
  route TEXT NOT NULL,
  model TEXT NOT NULL,
  est_usd TEXT NOT NULL,
  actual_usd TEXT,
  status TEXT NOT NULL CHECK (status IN ('reserved', 'settled', 'released'))
)
"""

_POSTGRES_DDL = """
CREATE TABLE IF NOT EXISTS spend_ledger (
  id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  ts TEXT NOT NULL,
  route TEXT NOT NULL,
  model TEXT NOT NULL,
  est_usd TEXT NOT NULL,
  actual_usd TEXT,
  status TEXT NOT NULL CHECK (status IN ('reserved', 'settled', 'released'))
)
"""


class LedgerUnavailable(Exception):
    """The spend ledger could not be read or written. Carries no connection string."""


def _ddl_race(exc: BaseException) -> bool:
    """True for the errors concurrent CREATE TABLE IF NOT EXISTS raises."""
    state = getattr(exc, 'sqlstate', None)
    # 23505 unique_violation, 42P07 duplicate_table, 40P01 deadlock_detected.
    return state in {'23505', '42P07', '40P01'}


def _missing_ledger(exc: BaseException) -> bool:
    """True when the error is 'table not created yet'. The message is not logged."""
    try:
        import psycopg
        if isinstance(exc, psycopg.errors.UndefinedTable):
            return True
    except Exception:
        pass
    message = str(exc).lower()
    return 'spend_ledger' in message and ('does not exist' in message or 'undefined' in message)


class KeyedResult:
    """Outcome of one gated call. ``offline`` means the provider was not contacted."""

    def __init__(self, *, offline: bool, notice: str | None, value: Any = None):
        self.offline = offline
        self.notice = notice
        self.value = value

    def as_notice(self) -> dict[str, str] | None:
        if not self.notice:
            return None
        return {'notice': self.notice}


class BudgetStatus(BaseModel):
    live: bool
    cap_usd: float | None
    spent_usd: float | None
    remaining_usd: float | None


def live_enabled() -> bool:
    """True only when both the live flag and a non-empty key are set."""
    flag = os.environ.get('BATATIS_LIVE') == '1'
    key = (os.environ.get('OPENAI_API_KEY') or '').strip()
    return flag and bool(key)


def total_cap_usd() -> Decimal | None:
    """Total cap in USD. Unset means 20. A daily cap variable is not read.

    An unparseable or negative value is ``None``: callers refuse the model call.
    """
    raw = os.environ.get('BATATIS_TOTAL_BUDGET_USD')
    if raw is None:
        return _DEFAULT_CAP
    try:
        cap = Decimal(raw.strip())
    except InvalidOperation:
        return None
    if not cap.is_finite() or cap < 0 or cap > _DEFAULT_CAP:
        return None
    return cap


def token_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """USD for these token counts. Raises KeyError when ``model`` is not priced."""
    inn, out = _prices(model)
    if any(type(n) is not int or n < 0 for n in (input_tokens, output_tokens)):
        raise ValueError('invalid token count')
    usd = (Decimal(input_tokens) * inn + Decimal(output_tokens) * out) / _SCALE
    return usd.quantize(_PLACES, rounding=ROUND_CEILING)


def _prices(model: str) -> tuple[Decimal, Decimal]:
    """Refuse unknown or corrupt prices, including alias/snapshot disagreement."""
    if model not in {*_MODEL_SNAPSHOTS, *_MODEL_SNAPSHOTS.values()}:
        raise KeyError(model)
    rates = MODEL_PRICES[model]
    if (not isinstance(rates, tuple) or len(rates) != 2 or
            any(not isinstance(n, Decimal) or not n.is_finite() or n <= 0 for n in rates)):
        raise ValueError('invalid pricing')
    snapshot = _MODEL_SNAPSHOTS.get(model, model)
    if rates != MODEL_PRICES.get(snapshot):
        raise ValueError('inconsistent pricing')
    return rates


def sqlite_database_url(path: Path | str) -> str:
    """sqlite URL for a test double. ``sqlite://`` plus an absolute path."""
    return 'sqlite://' + Path(path).resolve().as_posix()


def database_url() -> str | None:
    """Neon/Postgres URL, else an explicit sqlite URL for tests.

    ``DATABASE_URL`` wins. ``POSTGRES_URL`` is the fallback. Matches the deploy
    branch: a ``postgres://`` scheme is rewritten, and ``sslmode=require`` is
    added when the Postgres URL does not set it. Sqlite URLs are left alone.
    """
    raw = (os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL') or '').strip()
    if not raw:
        return None
    if raw.startswith('sqlite:'):
        return raw
    if raw.startswith('postgres://'):
        raw = 'postgresql://' + raw[len('postgres://'):]
    if raw.startswith('postgresql://') and 'sslmode=' not in raw:
        parts = urlsplit(raw)
        query = parts.query + ('&' if parts.query else '') + 'sslmode=require'
        raw = urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))
    return raw


def _usd_text(amount: Decimal) -> str:
    if not amount.is_finite() or amount < 0:
        raise LedgerUnavailable
    return format(amount.quantize(_PLACES, rounding=ROUND_CEILING), '.6f')


def _micro(amount: Decimal) -> int:
    return int(Decimal(_usd_text(amount)) * _SCALE)


def _cap_micro(cap: Decimal) -> int:
    if not cap.is_finite() or not 0 <= cap <= _DEFAULT_CAP:
        raise LedgerUnavailable
    # Costs round up; the available cap must round down.
    return int((cap * _SCALE).to_integral_value(rounding=ROUND_FLOOR))


def _checked_totals(rows) -> tuple[Decimal, Decimal]:
    """Validate legacy TEXT amounts before SQL can coerce bad data to zero.

    Run under the reservation lock. A recorded overrun freezes further calls
    instead of concealing an amount above its reservation.
    """
    settled = reserved = Decimal('0')
    for estimate, actual, status in rows:
        for amount in (estimate, actual):
            if amount is not None and (not isinstance(amount, str) or
                    re.fullmatch(r'(0|[1-9][0-9]{0,8})\.[0-9]{6}', amount) is None):
                raise LedgerUnavailable
        if estimate is None or status not in {'reserved', 'settled', 'released'}:
            raise LedgerUnavailable
        if status == 'settled':
            if actual is None or Decimal(actual) > Decimal(estimate):
                raise LedgerUnavailable
            settled += Decimal(actual)
        elif actual is not None:
            raise LedgerUnavailable
        elif status == 'reserved':
            reserved += Decimal(estimate)
    return settled, reserved


def _validate_ledger(con) -> tuple[Decimal, Decimal]:
    return _checked_totals(con.execute('SELECT est_usd, actual_usd, status FROM spend_ledger').fetchall())


def _cents(amount: Decimal) -> Decimal:
    return amount.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _json_money(amount: Decimal) -> float:
    return float(_cents(amount))


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def _sqlite_path(url: str) -> Path:
    # sqlite:///abs/file -> /abs/file. sqlite://relative is rejected.
    if not url.startswith('sqlite:///'):
        raise LedgerUnavailable
    path = Path(url[len('sqlite://'):])
    if not path.is_absolute():
        raise LedgerUnavailable
    if path.name == 'codedb.sqlite':
        raise LedgerUnavailable
    return path


class _SqliteLedger:
    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        if self.path.name == 'codedb.sqlite':
            raise LedgerUnavailable
        try:
            con = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        except sqlite3.Error as exc:
            raise LedgerUnavailable from exc
        con.execute('PRAGMA busy_timeout=30000')
        return con

    def _ensure(self, con: sqlite3.Connection) -> None:
        con.execute(_SQLITE_DDL)

    def reserve(self, route: str, model: str, estimate: Decimal, cap: Decimal) -> int | None:
        est = _usd_text(estimate)
        try:
            with closing(self._connect()) as con:
                self._ensure(con)
                con.execute('BEGIN IMMEDIATE')
                try:
                    _validate_ledger(con)
                    row = con.execute(
                        SQLITE_RESERVE_SQL,
                        (_stamp(), route, model, est, _micro(estimate), _cap_micro(cap)),
                    ).fetchone()
                    con.execute('COMMIT')
                except Exception:
                    try:
                        con.execute('ROLLBACK')
                    except sqlite3.Error:
                        pass
                    raise
        except sqlite3.Error as exc:
            raise LedgerUnavailable from exc
        return None if row is None else int(row[0])

    def settle(self, row_id: int, actual: Decimal) -> None:
        self._update(row_id, 'settled', _usd_text(actual))

    def release(self, row_id: int) -> None:
        self._update(row_id, 'released', None)

    def _update(self, row_id: int, status: str, actual: str | None) -> None:
        try:
            with closing(self._connect()) as con:
                con.execute('BEGIN IMMEDIATE')
                try:
                    con.execute(
                        "UPDATE spend_ledger SET status=?, actual_usd=? WHERE id=? AND status='reserved'",
                        (status, actual, row_id),
                    )
                    con.execute('COMMIT')
                except Exception:
                    try:
                        con.execute('ROLLBACK')
                    except sqlite3.Error:
                        pass
                    raise
        except sqlite3.Error as exc:
            raise LedgerUnavailable from exc

    def totals(self) -> tuple[Decimal, Decimal] | None:
        try:
            with closing(self._connect()) as con:
                return _validate_ledger(con)
        except sqlite3.OperationalError as exc:
            if 'no such table' in str(exc).lower():
                return Decimal('0'), Decimal('0')
            raise LedgerUnavailable from exc
        except sqlite3.Error as exc:
            raise LedgerUnavailable from exc


class _PostgresLedger:
    def __init__(self, url: str):
        self.url = url

    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:
            raise LedgerUnavailable from exc
        try:
            return psycopg.connect(self.url, autocommit=False, connect_timeout=10)
        except Exception as exc:
            raise LedgerUnavailable from exc

    def _run(self, fn):
        con = self._connect()
        try:
            return fn(con)
        except LedgerUnavailable:
            raise
        except Exception as exc:
            try:
                con.rollback()
            except Exception:
                pass
            raise LedgerUnavailable from exc
        finally:
            con.close()

    def _ensure_table(self) -> None:
        """Create the ledger outside the reservation transaction.

        Concurrent ``CREATE TABLE IF NOT EXISTS`` on Postgres raises
        UniqueViolation (pg_type) or DuplicateTable. That must not become a
        failed spend check. Commit the table first, then reserve.
        """
        last: BaseException | None = None
        for _ in range(4):
            con = self._connect()
            try:
                con.execute(_POSTGRES_DDL)
                con.commit()
                return
            except Exception as exc:
                last = exc
                try:
                    con.rollback()
                except Exception:
                    pass
                if not _ddl_race(exc):
                    raise LedgerUnavailable from exc
            finally:
                con.close()
        raise LedgerUnavailable from last

    def reserve(self, route: str, model: str, estimate: Decimal, cap: Decimal) -> int | None:
        est = _usd_text(estimate)
        self._ensure_table()

        def fn(con):
            # A pool/server default of REPEATABLE READ would make the cap's
            # snapshot stale while waiting for the advisory lock.
            con.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED')
            con.execute(POSTGRES_LOCK_SQL, (_ADVISORY_LOCK,))
            _validate_ledger(con)
            row = con.execute(
                POSTGRES_RESERVE_SQL,
                (_stamp(), route, model, est, _micro(estimate), _cap_micro(cap)),
            ).fetchone()
            con.commit()
            return None if row is None else int(row[0])

        return self._run(fn)

    def settle(self, row_id: int, actual: Decimal) -> None:
        self._update(row_id, 'settled', _usd_text(actual))

    def release(self, row_id: int) -> None:
        self._update(row_id, 'released', None)

    def _update(self, row_id: int, status: str, actual: str | None) -> None:
        def fn(con):
            con.execute(POSTGRES_LOCK_SQL, (_ADVISORY_LOCK,))
            con.execute(
                "UPDATE spend_ledger SET status=%s, actual_usd=%s WHERE id=%s AND status='reserved'",
                (status, actual, row_id),
            )
            con.commit()

        self._run(fn)

    def totals(self) -> tuple[Decimal, Decimal] | None:
        def fn(con):
            try:
                totals = _validate_ledger(con)
            except Exception as exc:
                con.rollback()
                if _missing_ledger(exc):
                    return Decimal('0'), Decimal('0')
                raise
            con.rollback()
            return totals

        return self._run(fn)


def open_ledger():
    """Open the configured ledger. Raises LedgerUnavailable with no URL in the message."""
    url = database_url()
    if not url:
        raise LedgerUnavailable
    if url.startswith('sqlite:'):
        if os.environ.get('VERCEL'):
            raise LedgerUnavailable
        return _SqliteLedger(_sqlite_path(url))
    if url.startswith('postgresql://'):
        return _PostgresLedger(url)
    raise LedgerUnavailable


def _usage_tokens(value: Any) -> tuple[int, int] | None:
    """Only coherent Chat Completions accounting can reduce a reservation."""
    usage = value.get('usage') if isinstance(value, Mapping) else None
    if not isinstance(usage, Mapping):
        return None
    inn = usage.get('prompt_tokens')
    out = usage.get('completion_tokens')
    total = usage.get('total_tokens')
    if any(type(n) is not int or n < 0 for n in (inn, out, total)):
        return None
    if total != inn + out:
        return None
    return inn, out


class SpendError(Exception):
    """The provider call failed, or live mode refused a non-OpenAI provider.

    The message has no API key and no request body.
    """


def live_provider_is_anthropic() -> bool:
    """Compatibility predicate: any non-OpenAI provider is refused in live/hosted mode."""
    if os.environ.get('BATATIS_LIVE') != '1' and not os.environ.get('VERCEL'):
        return False
    return (os.environ.get('BATATIS_LLM_PROVIDER') or 'openai').strip().lower() != 'openai'


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def estimate_input_tokens(messages: Any, response_format: dict | None = None, *,
                          model: str = 'gpt-4.1-mini', max_completion_tokens: int = 8) -> int:
    """Conservative text-only bound from the complete request, including schema.

    A byte-level tokenizer cannot emit more tokens than source UTF-8 bytes.
    Count all JSON fields, including schema, and add 4096 framing tokens plus
    64 per message. No network tokenizer, character heuristic, or tools. The
    request validator limits the accepted schema/message shape.
    """
    payload = _payload(messages, model, max_completion_tokens, response_format)
    return len(_json_bytes(payload)) + 4096 + 64 * len(messages)


def _payload(messages, model: str, max_completion_tokens: int, response_format) -> dict:
    if (type(max_completion_tokens) is not int or
            not 1 <= max_completion_tokens <= _MAX_OUTPUT_TOKENS):
        raise ValueError('invalid output bound')
    if not isinstance(messages, list) or not 1 <= len(messages) <= 64:
        raise ValueError('invalid messages')
    for message in messages:
        if (not isinstance(message, dict) or set(message) != {'role', 'content'} or
                message['role'] not in {'system', 'developer', 'user', 'assistant'} or
                not isinstance(message['content'], str)):
            raise ValueError('text messages only')
    payload = {
        'model': _MODEL_SNAPSHOTS.get(model, model),
        'messages': messages,
        'max_completion_tokens': max_completion_tokens,
        'service_tier': 'default',
        'n': 1,
        'store': False,
    }
    if response_format is not None:
        if not isinstance(response_format, dict):
            raise ValueError('invalid response format')
        if response_format != {'type': 'json_object'}:
            if (set(response_format) != {'type', 'json_schema'} or
                    response_format['type'] != 'json_schema'):
                raise ValueError('unsupported response format')
            fmt = response_format['json_schema']
            if (not isinstance(fmt, dict) or set(fmt) != {'name', 'strict', 'schema'} or
                    not isinstance(fmt['name'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', fmt['name']) or
                    fmt['strict'] is not True or not isinstance(fmt['schema'], dict)):
                raise ValueError('invalid response schema')
            # No remote/recursive refs or expansions outside the serialized bound.
            def check_schema(node, depth=0):
                if depth > 16:
                    raise ValueError('schema too deep')
                if isinstance(node, dict):
                    if any(str(key).startswith('$') for key in node):
                        raise ValueError('schema refs are unsupported')
                    for value in node.values():
                        check_schema(value, depth + 1)
                elif isinstance(node, list):
                    for value in node:
                        check_schema(value, depth + 1)
            check_schema(fmt['schema'])
            if len(_json_bytes(response_format)) > 32_768:
                raise ValueError('schema too large')
        payload['response_format'] = response_format
    # Serialize before reserving. This also isolates caller mutations from the
    # request that was counted (including nested schema dictionaries).
    return json.loads(_json_bytes(payload))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _post_chat(payload: dict, api_key: str) -> dict:
    """POST one chat completion. ``api_key`` is a header only and is not logged."""
    data = _json_bytes(payload)
    request = urllib.request.Request(
        'https://api.openai.com/v1/chat/completions',
        data=data,
        method='POST',
        headers={
            'Authorization': 'Bearer ' + api_key,
            'Content-Type': 'application/json',
        },
    )
    try:
        # urllib performs no HTTP retries. Refuse redirects so this single
        # reservation cannot turn into another request or leak authorization.
        opener = urllib.request.build_opener(_NoRedirect())
        with opener.open(request, timeout=60) as response:
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
            if len(raw) > _MAX_RESPONSE_BYTES:
                raise SpendError('openai response too large')
    except urllib.error.HTTPError as exc:
        raise SpendError('openai http ' + str(exc.code)) from None
    except Exception:
        raise SpendError('openai request failed') from None
    try:
        parsed = json.loads(raw.decode('utf-8'))
    except Exception:
        raise SpendError('openai response was not json') from None
    if not isinstance(parsed, dict):
        raise SpendError('openai response was not an object')
    if parsed.get('error'):
        raise SpendError('openai refused')
    return parsed


# #12 engine/identify/llm.py `_openai_json` posts on its own today. That call
# has to come through this function. The guard test fails CI otherwise.
def openai_chat_json(messages, *, model: str, max_completion_tokens: int,
                     response_format: dict | None = None,
                     route: str = ROUTE_IDENTIFY_RERANK) -> KeyedResult:
    """One bounded, priced attempt. Unknown outcomes retain their full reservation.

    Preflight refusals do not contact the provider. After sending begins every
    exception, cancellation, timeout, refusal, malformed response, and failed
    settlement stays charged at the reservation until billing reconciliation.
    There are no hidden transport or SDK retries.
    """
    if live_provider_is_anthropic():
        raise SpendError('Live mode is OpenAI only.')
    if not live_enabled():
        return KeyedResult(offline=True, notice=None)
    try:
        _prices(model)
    except (KeyError, ValueError, TypeError):
        return KeyedResult(offline=True, notice=UNPRICED_NOTICE)
    cap = total_cap_usd()
    if cap is None:
        return KeyedResult(offline=True, notice=LEDGER_NOTICE)
    try:
        payload = _payload(messages, model, max_completion_tokens, response_format)
        input_est = len(_json_bytes(payload)) + 4096 + 64 * len(payload['messages'])
        if input_est + max_completion_tokens > _CONTEXT_TOKENS:
            raise ValueError('request exceeds context bound')
        estimate = token_cost(model, input_est, max_completion_tokens)
    except (ValueError, TypeError, OverflowError, RecursionError, InvalidOperation):
        return KeyedResult(offline=True, notice=LEDGER_NOTICE)
    try:
        ledger = open_ledger()
        row_id = ledger.reserve(route, model, estimate, cap)
    except LedgerUnavailable:
        log.warning('spend ledger unavailable')
        return KeyedResult(offline=True, notice=LEDGER_NOTICE)
    if row_id is None:
        return KeyedResult(offline=True, notice=CAP_NOTICE)

    # The reservation is durable before this point. Do not refund on exceptions:
    # even a connection/read/parse error can follow billable provider processing.
    api_key = (os.environ.get('OPENAI_API_KEY') or '').strip()
    value = _post_chat(payload, api_key)
    if not isinstance(value, dict):
        raise SpendError('invalid openai response')
    if value.get('model') != payload['model']:
        raise SpendError('openai model mismatch')
    if value.get('service_tier') != 'default':
        raise SpendError('openai service tier mismatch')
    choices = value.get('choices') or []
    if (not isinstance(choices, list) or len(choices) != 1 or
            not isinstance(choices[0], dict) or
            not isinstance(choices[0].get('message'), dict)):
        raise SpendError('invalid openai choices')
    spent = _usage_tokens(value)
    actual = estimate
    if spent is not None:
        actual = token_cost(model, *spent)
        if spent[0] > input_est or spent[1] > max_completion_tokens:
            # Never clamp reported spend to hide an overrun. An over-reservation
            # amount in the ledger freezes future calls for manual investigation.
            try:
                ledger.settle(row_id, max(actual, estimate))
            except LedgerUnavailable:
                log.warning('spend ledger unavailable')
            raise SpendError('openai usage exceeded request bounds')
    if choices[0].get('finish_reason') == 'refusal' or choices[0]['message'].get('refusal'):
        raise SpendError('openai refused')
    try:
        ledger.settle(row_id, actual)
    except LedgerUnavailable:
        # A failed/ambiguously committed settlement leaves at most the full
        # reservation consumed. Returning the response cannot free that budget.
        log.warning('spend ledger unavailable')
    return KeyedResult(offline=False, notice=None, value=value)


def budget_status() -> BudgetStatus:
    """Cap and settled spend. No key, no per-request rows. Ledger errors stay HTTP 200."""
    try:
        return _budget_status()
    except Exception:
        log.warning('spend ledger unavailable')
        return BudgetStatus(live=live_enabled(), cap_usd=None, spent_usd=None, remaining_usd=None)


def _budget_status() -> BudgetStatus:
    cap = total_cap_usd()
    cap_json = None if cap is None else _json_money(cap)
    try:
        url = database_url()
        if not url:
            totals = None
        elif url.startswith('sqlite:'):
            path = _sqlite_path(url)
            if not path.exists():
                totals = (Decimal('0'), Decimal('0'))
            else:
                totals = open_ledger().totals()
        else:
            totals = open_ledger().totals()
    except LedgerUnavailable:
        log.warning('spend ledger unavailable')
        totals = None
    if totals is None or cap is None:
        return BudgetStatus(live=live_enabled(), cap_usd=cap_json, spent_usd=None, remaining_usd=None)
    settled, reserved = totals
    if os.environ.get('VERCEL') and url and url.startswith('sqlite:'):
        return BudgetStatus(live=live_enabled(), cap_usd=cap_json, spent_usd=None, remaining_usd=None)
    remaining = (cap - settled - reserved).quantize(_CENTS, rounding=ROUND_FLOOR)
    if remaining < 0:
        remaining = Decimal('0.00')
    return BudgetStatus(
        live=live_enabled(),
        cap_usd=cap_json,
        spent_usd=_json_money(settled),
        remaining_usd=float(remaining),
    )
