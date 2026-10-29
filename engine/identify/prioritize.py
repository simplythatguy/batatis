"""Order discoveries by their input evidence without removing any candidate."""
from __future__ import annotations

import math
import re
from collections import Counter

from .requirement_corpus import words


def order(result, prose):
    query = set(words(prose))
    index = {e.id: e for e in result.requirement_evidence}
    tokens = {}
    for item in result.requirements:
        evidence = [index[eid] for eid in item.evidence_ids if eid in index]
        own = [e.quote for e in evidence if e.division == item.division and (
            e.provision_id == item.provision_id or e.provision_id.startswith((item.provision_id or '') + '('))]
        tokens[item.id] = set(words(item.title + ' ' + ' '.join(own))) & query
    frequency = Counter(word for found in tokens.values() for word in found)
    total = len(result.requirements)
    priority = {'human': 0, 'previous': 0, 'explicit': 1, 'lexical': 2, 'administrative': 3,
                'reference': 4, 'reverse_reference': 5, 'model_search': 6}

    def rank(item):
        kind = min((priority[d.kind] for d in item.discoveries), default=7)
        weight = sum(math.log(1 + total / frequency[w]) for w in tokens[item.id])
        # A deterministic lexical ordering is not a calibrated applicability score.
        return kind, -weight, item.division or '', tuple(int(x) for x in re.findall(r'\d+', item.provision_id or ''))

    result.requirements.sort(key=rank)
    position = {item.provision_id: i for i, item in enumerate(result.requirements) if item.division == 'B'}
    result.articles.sort(key=lambda article: position.get(article.provision, total))
    for rank_number, article in enumerate(result.articles, 1):
        article.rank = rank_number
    return result
