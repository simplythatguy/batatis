"""Targeted identify questions.

Each question names a fact that would change which of the current candidates applies,
lists those candidates, and stays under a cap of five. A value already on the case but
not confirmed is asked back as a confirmation. An unknown answer stays open.
"""
from __future__ import annotations

from engine.identify.storeys import parse_storeys

QUESTION_CAP = 5

# Prefixes are families already in NBC(AE) Division B. A question is emitted only when a
# candidate the ranker returned actually sits in that family, or the applicant's words
# name the fact and the top candidates are what it would split.
PROBES = (
    {
        'field': 'assembly.material',
        'label': 'wall assembly',
        'ask': 'What is the wall assembly made of, and what are its fire-resistance and thermal properties?',
        'why': 'The material and its fire or thermal properties decide which wall, insulation, and fire-resistance articles apply.',
        'prefixes': ('9.10.3.', '9.10.8.', '9.23.', '9.25.', '3.1.5.', '3.1.7.'),
        'prose': ('hemp', 'hempcrete', 'straw bale', 'wall assembly', 'assembly', 'insulation'),
        'boost': ('hemp', 'hempcrete'),
    },
    {
        'field': 'assembly.sheathing_membrane',
        'label': 'sheathing membrane',
        'ask': 'Is a sheathing membrane part of this wall?',
        'why': 'A sheathing membrane is a different layer from a structural nail-base panel.',
        'prefixes': ('9.27.3.',),
        'prose': ('sheathing membrane',),
        'topic': ('sheathing membrane',),
    },
    {
        'field': 'building.storeys',
        'label': 'number of storeys',
        'ask': 'How many storeys does the building have?',
        'why': 'Storey count changes which exit, fire-separation, and spatial-separation articles are in the set.',
        'prefixes': ('9.9.8.', '9.9.9.', '9.10.4.', '3.4.2.', '3.2.2.'),
        'prose': ('storey', 'storeys', 'story', 'stories', 'stair', 'single exit'),
    },
    {
        'field': 'building.height',
        'label': 'building height',
        'ask': 'What is the building height in storeys and metres?',
        'why': 'Height decides whether Part 9 or Part 3 exit and construction articles govern.',
        'prefixes': ('3.2.1.', '3.2.2.', '9.10.8.', '3.2.6.'),
        'prose': ('building height', 'metres high', 'high building'),
    },
    {
        'field': 'building.occupancy',
        'label': 'occupancy',
        'ask': 'What is the occupancy (and, if you have it, the occupant load)?',
        'why': 'Occupancy and occupant load move a design between Part 9 housing articles and Part 3 assembly or care articles.',
        'prefixes': ('3.1.2.', '9.10.2.', '3.4.2.', '3.1.17.'),
        'prose': ('occupancy', 'occupant', 'dwelling', 'suite', 'assembly', 'care'),
    },
    {
        'field': 'site.limiting_distance',
        'label': 'limiting distance',
        'ask': 'What is the limiting distance from the exposing building face to the property line?',
        'why': 'Limiting distance decides which spatial-separation articles, and which unprotected-opening limits, stay in the set.',
        'prefixes': ('9.10.14.', '9.10.15.', '3.2.3.'),
        'prose': ('limiting distance', 'property line', 'exposing', 'setback', 'side yard'),
    },
    {
        'field': 'building.area',
        'label': 'building area',
        'ask': 'What is the building area of each storey?',
        'why': 'Building area changes the Part 9 / Part 3 boundary and several construction articles.',
        'prefixes': ('9.10.8.', '3.2.2.', '1.3.3.'),
        'prose': ('building area', 'floor area', 'm2', 'm²'),
    },
    {
        'field': 'building.sprinklered',
        'label': 'sprinkler status',
        'ask': 'Is the building sprinklered?',
        'why': 'Sprinkler status changes which exit and fire-separation relaxations are candidates.',
        'prefixes': ('3.2.2.', '3.2.5.', '9.10.8.', '3.4.2.'),
        'prose': ('sprinkler',),
    },
    {
        'field': 'egress.window',
        'label': 'bedroom egress window',
        'ask': 'Is the opening a bedroom egress window, and what clear opening does it provide?',
        'why': 'That fact distinguishes bedroom egress-window articles from other opening and exit articles.',
        'prefixes': ('9.9.10.', '9.7.1.', '9.9.9.'),
        'prose': ('egress', 'bedroom window', 'window opening'),
    },
)


def _view(facts) -> list[dict]:
    out = []
    for fact in facts or []:
        if hasattr(fact, 'model_dump'):
            out.append(fact.model_dump())
        else:
            out.append(dict(fact))
    return out


def _terms(probe: dict) -> tuple[str, ...]:
    return tuple(probe.get('topic') or probe['prose'])


def _topic_in(probe: dict, prose: str) -> bool:
    low = (prose or '').lower()
    return any(term in low for term in _terms(probe))


def _provision_hits(probe: dict, candidates: list[dict], provisions) -> list[dict]:
    """Candidates or confirmed provisions in this question's provision family."""
    hits = []
    seen = set()
    for cand in candidates:
        pid = str(cand.get('provision') or '')
        if any(pid.startswith(prefix) for prefix in probe['prefixes']) and pid not in seen:
            hits.append(cand)
            seen.add(pid)
    for pid in provisions or []:
        pid = str(pid)
        if any(pid.startswith(prefix) for prefix in probe['prefixes']) and pid not in seen:
            hits.append({'provision': pid, 'title': '', 'text': ''})
            seen.add(pid)
    return hits


def _hits(probe: dict, prose: str, candidates: list[dict], provisions=()) -> list[dict]:
    """Provision family, or a topic the description actually names. Not the top ranked cards."""
    hits = _provision_hits(probe, candidates, provisions)
    described = _topic_in(probe, prose)
    # A sheathing-membrane card follows that topic or that provision. A ranked
    # article with the words in its title is not enough for a nail-base panel.
    if 'sheathing membrane' in _terms(probe):
        case_has = any(str(pid).startswith('9.27.3.') for pid in provisions or [])
        if not described and not case_has:
            return []
        return [hit for hit in hits if str(hit.get('provision') or '').startswith('9.27.3.')]
    if hits:
        return hits
    if described:
        return []
    return []


def question_matches(question: dict, *, description: str, provisions=(), candidates=()) -> bool:
    """A question card is shown only when its provision or its topic matches this case.

    ``provisions`` are the case's provisions. Ranked candidates are not a match by themselves.
    """
    description = (description or '').lower()
    provision_ids = [str(pid) for pid in provisions or []]
    disambiguates = [str(pid) for pid in question.get('disambiguates') or []]
    parts = [str(question.get('text') or ''), str(question.get('why') or '')]
    linked = {pid for pid in disambiguates}
    for cand in candidates or []:
        if str(cand.get('provision') or '') in linked:
            parts.append(str(cand.get('title') or ''))
            parts.append(str(cand.get('text') or ''))
    blob = ' '.join(parts).lower()
    if 'sheathing membrane' in blob:
        if 'sheathing membrane' in description:
            return True
        return any(pid.startswith('9.27.3.') for pid in provision_ids)
    if provision_ids and disambiguates:
        return any(
            left.startswith(right) or right.startswith(left)
            for left in disambiguates for right in provision_ids
        )
    if disambiguates and not provision_ids:
        return True
    return True


def _known(facts: list[dict], field: str) -> dict | None:
    found = None
    for fact in facts:
        if fact.get('field') == field:
            found = fact
    return found


def _text(probe: dict, fact: dict | None) -> tuple[str, str]:
    """Question text and status. Unconfirmed values are asked back; unknown stays open."""
    label = probe['label']
    if fact is None or fact.get('value') in (None, ''):
        status = fact.get('status') if fact and fact.get('status') in ('open', 'unknown') else 'open'
        if status == 'unknown':
            return (f'{label[:1].upper()}{label[1:]} is still unknown, so no value is being assumed. {probe["ask"]}',
                    'unknown')
        return probe['ask'], 'open'
    status = fact.get('status') or 'unconfirmed'
    if status == 'confirmed':
        return '', 'confirmed'
    if status in ('open', 'unknown'):
        return (f'{label[:1].upper()}{label[1:]} was answered "{fact.get("value")}" and is still {status}. '
                f'It is not being assumed. {probe["ask"]}'), status
    return (f'Confirm {label} is "{fact.get("value")}". It is recorded but not confirmed, so it is not being assumed.',
            'unconfirmed')


def _with_storeys(prose: str, facts: list[dict]) -> list[dict]:
    """A storey count written in the description is already known. Do not ask for it again."""
    if any(fact.get('field') == 'building.storeys' for fact in facts):
        return facts
    parsed = parse_storeys(prose)
    if parsed is None:
        return facts
    count, quote = parsed
    return facts + [{
        'field': 'building.storeys', 'value': count, 'status': 'confirmed',
        'source': {'type': 'user_text', 'ref': 'description', 'quote': quote},
    }]


def generate_questions(prose: str, candidates: list[dict], facts=None, *, cap: int = QUESTION_CAP,
                       provisions=None) -> list[dict]:
    """Ranked questions, at most `cap`. Each names the candidates it disambiguates."""
    facts = _with_storeys(prose, _view(facts))
    prose = prose or ''
    provisions = list(provisions or [])
    scored = []
    for probe in PROBES:
        hits = _hits(probe, prose, candidates, provisions)
        described = _topic_in(probe, prose)
        if not hits and not described:
            continue
        fact = _known(facts, probe['field'])
        if fact and fact.get('status') == 'confirmed' and fact.get('value') not in (None, ''):
            continue
        text, status = _text(probe, fact)
        if not text:
            continue
        split = min(len(hits), max(0, len(candidates) - len(hits)))
        score = split * 10 + len(hits)
        if any(k in prose.lower() for k in probe.get('boost', ())):
            score += 50
        scored.append((score, {
            'id': probe['field'],
            'field': probe['field'],
            'text': text,
            'why': probe['why'],
            'status': status if status in ('open', 'unknown') else 'open',
            'disambiguates': [h['provision'] for h in hits],
            'answer': None if not fact or fact.get('status') not in ('open', 'unknown') else fact.get('value'),
        }))
    scored.sort(key=lambda item: -item[0])
    chosen = []
    seen = set()
    for _, question in scored:
        if question['field'] in seen:
            continue
        seen.add(question['field'])
        chosen.append(question)
        if len(chosen) >= cap:
            break
    for fact in facts:
        field = str(fact.get('field') or '')
        if fact.get('status') not in ('open', 'unknown') or field in seen:
            continue
        chosen.append({
            'id': field,
            'field': field,
            'text': f'{field} is still {fact.get("status")}. Identify continues without assuming a value.',
            'why': 'The applicant answered that this fact is unknown.',
            'status': fact.get('status'),
            'disambiguates': [],
            'answer': fact.get('value'),
        })
    return [question for question in chosen
            if question_matches(question, description=prose, provisions=provisions, candidates=candidates)]
