"""Keep a case small enough to save.

A requirement profile names every review candidate. The shared passage graph, discovery
walks and the full article dump are what make that profile too large to send back with
the case. Candidates stay, in the same order, with the fields an answer needs.
"""
from __future__ import annotations

from engine.models_identify import IdentifyResult

# A stored requirement profile whose passage graph was removed. The running server treats
# it as a requirement run and compacts again after a refresh. An older server leaves it
# alone, so answering a question does not write the graph back.
COMPACTED = 'compacted'
REQUIREMENT_SCREENS = frozenset({'requirements', COMPACTED})


def requirement_screen(result: IdentifyResult | None) -> bool:
    if result is None:
        return False
    return result.trace.config.get('screen') in REQUIREMENT_SCREENS


def compact_identify(result: IdentifyResult) -> IdentifyResult:
    """Drop the passage graph. Review candidates and their answers stay."""
    requirements = [
        item.model_copy(update={'discoveries': [], 'evidence': []})
        for item in result.requirements
    ]
    update: dict = {
        'requirements': requirements,
        'requirement_evidence': [],
        'requirement_links': [],
    }
    # Other modes use the article list as the candidate list. A requirement profile does not.
    if requirement_screen(result) and not result.committed and not result.choices:
        update['articles'] = []
    return result.model_copy(update=update)
