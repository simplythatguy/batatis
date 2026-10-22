"""Read-only CCMC discovery with a complete-registry cache and labelled offline fallback.

The public registry's JSON link (verified 2026-10-20) moved from the old corp.nrc.gc.ca
host to published_evaluations.html on nrc.canada.ca. The JSON index has no report dates:
dates are read from matched report headers, or explicitly reported as unavailable.
"""
from __future__ import annotations

import json
import os
import re
import ssl
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from threading import RLock
from typing import Callable, Literal
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel

REGISTRY_URL = ('https://nrc.canada.ca/en/certifications-evaluations-standards/'
                'canadian-construction-materials-centre/ccmc-publications/registry.html')
API_URL = REGISTRY_URL.rsplit('/', 1)[0] + '/published_evaluations.html'
REPORT_URL = REGISTRY_URL.rsplit('/', 1)[0] + '/document.html'
# One search may match up to 50 listings. Report dates are cached on this instance.
# A single search opens at most this many new report requests to nrc.canada.ca.
REPORT_FETCH_CAP = 8
_ROOT = Path(__file__).resolve().parents[1]


# The offline fallback shipped with the engine (vercel.json bundles engine/data/**/*.json) and its access date.
BUNDLED_SNAPSHOT = _ROOT / 'engine/data/ccmc/ccmc-registry.json'
BUNDLED_META = _ROOT / 'engine/data/ccmc/snapshot.json'


def bundled_snapshot_date(path: Path) -> str:
    """The access date recorded for a known snapshot file, or 'unknown'. The date is attached only when the
    file's SHA-256 matches the one recorded with it, so a replaced file is never shown with the old date."""
    import hashlib
    for meta_path in (BUNDLED_META, _ROOT / 'research/precedents/ccmc-summary.json'):
        try:
            meta = json.loads(meta_path.read_text())
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except (OSError, ValueError):
            continue
        if digest == (meta.get('sha256') or meta.get('source_sha256')):
            return meta['accessed']
    return 'unknown'


class RegistryUnavailable(RuntimeError):
    pass


class Assessment(BaseModel):
    number: str
    title: str
    manufacturer: str
    assessment_kind: Literal['evaluation', 'listing']
    date: str | None = None
    date_kind: Literal['modified', 'issued'] | None = None
    date_source_url: str | None = None
    report_url: str
    message: str = ''


class RegistrySearch(BaseModel):
    query: str
    searched_date: str
    registry_date: str
    source: Literal['live', 'snapshot']
    source_url: str = API_URL
    snapshot_path: str | None = None
    cached: bool
    total_matches: int
    results: list[Assessment]
    message: str
    notice: str


def _download(url: str) -> bytes:
    cafile = os.environ.get('SSL_CERT_FILE')
    if not cafile and Path('/etc/ssl/cert.pem').exists():
        cafile = '/etc/ssl/cert.pem'
    request = Request(url, headers={'User-Agent': 'Batatis/0.1 (CCMC registry discovery)'})
    with urlopen(request, timeout=8, context=ssl.create_default_context(cafile=cafile)) as response:
        data = response.read(5_000_001)
    if len(data) > 5_000_000:
        raise ValueError('registry response exceeds size limit')
    return data


def _fetch_json(url: str) -> dict:
    return json.loads(_download(url))


def _fetch_text(url: str) -> str:
    return _download(url).decode('utf-8')


def _normal(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', text).casefold() if not unicodedata.combining(c))


def _names(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        if value.lstrip().startswith('['):
            value = json.loads(value)
        else:
            value = value.split('|')
    if not isinstance(value, list) or any(not isinstance(s, str) for s in value):
        raise ValueError('malformed product names in registry')
    return [s.strip() for s in value if s.strip()]


class _ReportText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data):
        self.parts.append(data)


class CCMCRegistry:
    def _public_snapshot_path(self) -> str:
        """Repo-relative for a bundled or local snapshot, so no server path reaches a response."""
        try:
            return self.snapshot_path.resolve().relative_to(_ROOT).as_posix()
        except ValueError:
            return self.snapshot_path.name

    def __init__(self, snapshot_path: Path | str | None = None, snapshot_date: str | None = None,
                 *, fetch_json: Callable[[str], dict] = _fetch_json,
                 fetch_text: Callable[[str], str] = _fetch_text, ttl_seconds: float = 3600,
                 clock: Callable[[], float] = time.monotonic, today: Callable[[], date] = date.today,
                 offline: bool = False):
        candidates = [BUNDLED_SNAPSHOT, _ROOT / 'reference/data/ccmc-registry.json']
        configured = snapshot_path or os.environ.get('BATATIS_CCMC_SNAPSHOT')
        self.snapshot_path = Path(configured) if configured else next((p for p in candidates if p.exists()), candidates[0])
        if snapshot_date is None:
            # A custom snapshot must bring its own access date; never attach the bundled date to it.
            snapshot_date = 'unknown' if configured else bundled_snapshot_date(self.snapshot_path)
        self.snapshot_date = snapshot_date
        self.fetch_json, self.fetch_text = fetch_json, fetch_text
        self.ttl_seconds, self.clock, self.today, self.offline = ttl_seconds, clock, today, offline
        self._lock = RLock()
        self._items: list[tuple[Assessment, str]] | None = None
        self._loaded_at = float('-inf')
        self._source: Literal['live', 'snapshot'] = 'snapshot'
        self._registry_date = snapshot_date
        self._notice = ''
        self._dates: dict[str, tuple[str | None, str | None]] = {}

    @staticmethod
    def _parse(data: dict) -> list[tuple[Assessment, str]]:
        if not isinstance(data, dict) or not isinstance(data.get('items'), list) or data.get('hasMore') is not False:
            raise ValueError('registry data is malformed or incomplete; cannot report a negative search')
        out = []
        seen = set()
        for item in data['items']:
            if not isinstance(item, dict) or not isinstance(item.get('status_eng'), str) or item.get('ispublished') not in ('Y', 'N'):
                raise ValueError('malformed assessment status in registry')
            number = item.get('ccmcno')
            manufacturer = item.get('organization_eng')
            products = _names(item.get('products_eng', item.get('product_eng')))
            if (not isinstance(number, str) or not re.fullmatch(r'\d{5}-[RL]', number)
                    or not isinstance(manufacturer, str) or not manufacturer.strip() or not products):
                raise ValueError('malformed assessment in registry')
            if number in seen:
                raise ValueError('duplicate assessment number in registry')
            seen.add(number)
            if item.get('ispublished') != 'Y' or item.get('status_eng') != 'Active':
                continue
            assessment = Assessment(number=number, title='; '.join(products), manufacturer=manufacturer.strip(),
                assessment_kind='listing' if number.endswith('-L') else 'evaluation',
                report_url=REPORT_URL + '?' + urlencode({'id': number, 'type': 'cert'}))
            searchable = ' '.join([number, manufacturer, item.get('organization_fre') or '', *products,
                                  *_names(item.get('products_fre', item.get('product_fre')))])
            out.append((assessment, _normal(searchable)))
        return out

    def _live(self) -> dict:
        url = API_URL
        visited = set()
        items = []
        while url not in visited and len(visited) < 50:
            visited.add(url)
            page = self.fetch_json(url)
            if not isinstance(page, dict) or not isinstance(page.get('items'), list):
                raise ValueError('invalid registry page')
            items.extend(page['items'])
            if page.get('hasMore') is False:
                return {'items': items, 'hasMore': False}
            if page.get('hasMore') is not True:
                raise ValueError('registry pagination status is absent')
            next_link = next((link.get('href') for link in page.get('links', []) if link.get('rel') == 'next'), None)
            if not next_link:
                raise ValueError('registry pagination is incomplete')
            url = urljoin(url, next_link)
            parsed, api = urlparse(url), urlparse(API_URL)
            if (parsed.scheme, parsed.netloc, parsed.path) != (api.scheme, api.netloc, api.path):
                raise ValueError('registry next page leaves the official endpoint')
        raise ValueError('registry pagination loop or limit reached')

    def _load(self) -> bool:
        if self._items is not None and self.clock() - self._loaded_at < self.ttl_seconds:
            return True
        try:
            if self.offline:
                raise OSError('offline mode')
            parsed = self._parse(self._live())
            self._source, self._registry_date = 'live', self.today().isoformat()
            self._notice = 'Searched the public CCMC JSON registry. Report applicability needs review.'
        except (OSError, ValueError, TypeError, KeyError) as error:
            try:
                parsed = self._parse(json.loads(self.snapshot_path.read_text()))
            except (OSError, ValueError, TypeError, KeyError) as fallback:
                raise RegistryUnavailable('Live CCMC registry and a complete offline snapshot are unavailable; '
                                          'no negative search conclusion can be made.') from fallback
            self._source, self._registry_date = 'snapshot', self.snapshot_date
            self._notice = (f'Using offline snapshot dated {self.snapshot_date}; live registry unavailable '
                            f'({type(error).__name__}). Current status and report dates are unverified.')
        self._items = parsed
        self._dates.clear()
        self._loaded_at = self.clock()
        return False

    def _report_date(self, assessment: Assessment) -> tuple[str | None, str | None]:
        try:
            parser = _ReportText()
            parser.feed(self.fetch_text(assessment.report_url))
            text = ' '.join(parser.parts)
            if not re.search(r'CCMC\s+number:\s*' + re.escape(assessment.number), text):
                return None, None
            for label, kind in (('Modified date', 'modified'), ('Issue date', 'issued')):
                match = re.search(label + r':\s*(\d{4}-\d{2}-\d{2})', text)
                if match:
                    return date.fromisoformat(match.group(1)).isoformat(), kind
        except (OSError, ValueError, UnicodeError):
            pass
        return None, None

    def search(self, query: str, limit: int = 20) -> RegistrySearch:
        tokens = re.findall(r'\w+', _normal(query))
        if not tokens or len(query) > 200 or not 1 <= limit <= 50:
            raise ValueError('Enter a product or manufacturer name (1–200 characters); limit must be 1–50.')
        with self._lock:
            cached = self._load()
            matches = [a for a, text in self._items if all(token in text for token in tokens)]
            selected = matches[:limit]
            pending = [a for a in selected if a.number not in self._dates] if self._source == 'live' else []
            pending = pending[:REPORT_FETCH_CAP]
            if pending:
                with ThreadPoolExecutor(max_workers=4) as pool:
                    for a, result in zip(pending, pool.map(self._report_date, pending)):
                        self._dates[a.number] = result
            results = []
            for assessment in selected:
                modified, kind = self._dates.get(assessment.number, (None, None))
                display_date = f'{kind} {modified}' if modified else 'date not available from registry index'
                results.append(assessment.model_copy(update={'date': modified, 'date_kind': kind,
                    'date_source_url': assessment.report_url if modified else None,
                    'message': f'found a listing: {assessment.number}, {assessment.title}, {display_date}'
                    if assessment.assessment_kind == 'listing' else
                    f'found an evaluation: {assessment.number}, {assessment.title}, {display_date}'}))
            searched = self.today().isoformat()
            message = (f'Found {len(matches)} registry assessment(s).' if matches else
                       f'no evaluation found in the registry (searched {searched})')
            if self._source == 'snapshot':
                message += f' Offline snapshot dated {self._registry_date}; current registry not verified.'
            return RegistrySearch(query=query.strip(), searched_date=searched, registry_date=self._registry_date,
                source=self._source, snapshot_path=self._public_snapshot_path() if self._source == 'snapshot' else None,
                cached=cached, total_matches=len(matches), results=results, message=message, notice=self._notice)
