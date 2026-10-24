"""Conservative connected duplicate groups, independent of ordering and model outputs.

Edges join equal gold sets, normalized descriptions, source documents, explicit rewrites and revision
families. Gold equality intentionally over-groups distinct situations. Folds stay fixed; clean_test
rejects any component touching tune and keeps one deterministic representative per remaining group.
Supply the whole universe, including kinds/sources outside the requested report slice.
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .cases import Case


def _source_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith('utm_')
             and k.lower() not in ('fbclid', 'gclid')]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, urlencode(sorted(query)), ''))


def duplicate_groups(cases: list[Case]) -> dict[str, str]:
    """case id -> smallest member id of its connected duplicate component."""
    parents = {c.id: c.id for c in cases}
    if len(parents) != len(cases):
        raise ValueError('duplicate case ids')

    def root(cid):
        while parents[cid] != cid:
            parents[cid] = parents[parents[cid]]
            cid = parents[cid]
        return cid

    def join(a, b):
        ra, rb = root(a), root(b)
        parents[max(ra, rb)] = min(ra, rb)

    seen: dict[tuple, str] = {}
    for c in cases:
        meta = c.meta or {}
        text = re.sub(r'\W+', ' ', unicodedata.normalize('NFKC', c.description).casefold()).strip()
        keys = []
        if c.gold:
            keys.append(('gold', tuple(sorted(set(c.gold)))))
        if text:
            keys.append(('text', text))
        if meta.get('source_url'):
            keys.append(('source', _source_url(meta['source_url'])))
        if meta.get('family'):
            keys.append(('family', meta['family']))
        for key in keys:
            if key in seen:
                join(c.id, seen[key])
            else:
                seen[key] = c.id
        original = meta.get('rewrite_of')
        if original in parents:
            join(c.id, original)
    return {cid: root(cid) for cid in parents}


def clean_test(cases: list[Case]) -> list[Case]:
    """Unique test representatives whose full duplicate component contains no tune case."""
    groups = duplicate_groups(cases)
    tuned = {groups[c.id] for c in cases if c.fold == 'tune'}
    kept, seen = [], set()
    # Prefer a positive case over a diagnostic twin, using only immutable case metadata.
    for c in sorted(cases, key=lambda c: (c.kind != 'benchmark', c.id)):
        group = groups[c.id]
        if c.fold == 'test' and group not in tuned and group not in seen:
            kept.append(c)
            seen.add(group)
    return kept
