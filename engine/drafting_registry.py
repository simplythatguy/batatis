"""Bounded lexical discovery of product names, with exact spans in actual supplied source snapshots."""
from __future__ import annotations

import re

from .models_drafting import DraftRegistryQuery, DraftSource

# A named/marketed product, marked product label, or distinctive brand/model spelling; no demo vocabulary.
_PATTERNS = (
    re.compile(r'(?im)\b(?:product|manufacturer|brand|trade name|product name)\s*:\s*(?P<name>[^\n;.!?]{2,80})'),
    re.compile(r'\*\*(?P<name>[^*\n]{2,80})\*\*'),
    re.compile(r'\b(?i:call|called|calling|name|named|naming|known as|marketed as|sold as)\s+'
               r'(?:(?i:our|the|this|a|proposed|new|wall|board|panel|product|system|it)\s+){0,8}'
               r'(?P<name>[A-Z][A-Za-z0-9-]{2,60})\b'),
    re.compile(r'\b(?P<name>(?:[A-Z][A-Za-z0-9-]*[ \t]+){1,3}(?:[A-Z]{1,6}-)?\d{1,5}(?:[.-]\d+)?)\b'),
    re.compile(r'\b(?P<name>(?:[A-Z]{2,}[a-z][A-Za-z0-9]*|[A-Z][a-z]+[A-Z][A-Za-z0-9]*))\b'),
)
_DISTINCTIVE = re.compile(r'[A-Z]{2,}[a-z]|[A-Z][a-z]+[A-Z]')
_AUTHORITY = re.compile(r'\b(?:NBC|CCMC|ISO|ASTM|CAN|CSA|ULC|SCC|STANDATA|Division|Section)\b', re.I)
_QUERY = re.compile(r"[A-Za-z0-9][A-Za-z0-9 '’()./-]{1,79}")


def product_queries(sources: list[DraftSource], limit: int = 3) -> list[DraftRegistryQuery]:
    out = []

    def covers(full, short):
        return re.search(r'(?<!\w)' + re.escape(short.casefold()) + r'(?!\w)', full.casefold()) is not None
    for source in sources:
        if source.kind not in {'description', 'document', 'fact'}:
            continue
        candidates = []
        if re.search(r'(?:^|\.)(?:product|manufacturer|brand|trade_name)(?:\.|$)',
                     str(source.metadata.get('field', ''))):
            candidates.append((0, len(source.text), True))
        for index, pattern in enumerate(_PATTERNS):
            candidates.extend((*m.span('name'), index in {0, 2}) for m in pattern.finditer(source.text))
        # Prefer a full marked/named/model phrase over a shorter brand token within it.
        kept = []
        for start, end, explicit in candidates:
            while start < end and source.text[start].isspace():
                start += 1
            while end > start and source.text[end - 1].isspace():
                end -= 1
            quote = source.text[start:end]
            query = ' '.join(quote.split())
            if (not _QUERY.fullmatch(query) or _AUTHORITY.search(query) or len(query.split()) > 6
                    or (not explicit and not _DISTINCTIVE.search(query))):
                continue
            if any(a <= start and end <= b for a, b, _ in kept):
                continue
            kept = [(a, b, e) for a, b, e in kept if not (start <= a and b <= end)]
            kept.append((start, end, explicit))
        for start, end, _ in sorted(kept):
            quote = source.text[start:end]
            query = ' '.join(quote.split())
            if any(covers(existing.query, query) for existing in out):
                continue
            candidate = DraftRegistryQuery(query=query, source_id=source.id, quote=quote, start=start, end=end)
            replaced = [index for index, existing in enumerate(out) if covers(query, existing.query)]
            if replaced:
                position = replaced[0]
                out = [existing for index, existing in enumerate(out) if index not in replaced]
                out.insert(position, candidate)
            elif len(out) < limit:
                out.append(candidate)
    return out
