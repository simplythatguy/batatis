"""Question planner: at most five questions, each with why it is asked and what an answer unblocks.

Seeds: PR #12 `engine/identify/questions.py` probes (article families, the "why" lines and the split
score). Ranking: a conflict in the applicant's own words first, then how evenly the fact splits the
current code-identification candidates, then critical facts that decide the route (Part 9 or Part 3,
the departure itself), then the administrative Section A and B fields. A fact the applicant already
stated (confirmed or not) is not asked again; the confirm card handles it. "Not sure" never blocks:
the question is dropped from later plans and stays visible to the officer as an open item.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable

from ..models import Fact
from ..models_intake import FieldConflict, IntakePlan, Question

CAP = 5


@dataclass(frozen=True)
class Probe:
    field: str
    text: str
    why: str
    unblocks: tuple[str, ...]
    prefixes: tuple[str, ...] = ()            # Division B families the fact separates
    prose: tuple[str, ...] = ()               # words in the description that make it relevant
    priority: str = 'critical'
    base: int = 0                             # weight before any candidate is known


PROBES = (
    Probe('alternative_description',
          'In a sentence or two, what does your design do differently from the usual code requirement?',
          'Code identification looks for the requirement your design departs from. Without the departure there '
          'is nothing to compare.', ('the departure', 'code identification'), base=40),
    Probe('storeys', 'How many storeys does the building have?',
          'Storey count decides between Part 9 and Part 3 and changes which exit, fire-separation and construction '
          'requirements are candidates.', ('Part 9 or Part 3', 'exit and fire-separation requirements'),
          ('9.9.8.', '9.9.9.', '9.10.4.', '9.10.8.', '3.4.2.', '3.2.2.', '3.2.1.'),
          ('storey', 'stair', 'exit', 'floor'), base=20),
    Probe('building_area_m2', 'What is the building area (the footprint) in square metres?',
          'Building area, with storeys and occupancy, decides whether Part 9 or Part 3 applies.',
          ('Part 9 or Part 3',), ('9.10.8.', '3.2.2.'), ('area', 'footprint', 'm2', 'm²'), base=15),
    Probe('occupancy', 'What is the building used for (for example a house, apartments, an office or a care home)?',
          'Occupancy moves a design between Part 9 housing requirements and Part 3 requirements for other uses.',
          ('Part 9 or Part 3', 'occupancy-specific requirements'),
          ('3.1.2.', '9.10.2.', '3.4.2.', '3.1.17.', '3.3.'), ('use', 'occupan', 'tenant'), base=18),
    Probe('sprinklered', 'Is the building sprinklered?',
          'Sprinkler status changes which fire-separation, exit and spatial-separation requirements are candidates.',
          ('fire-separation and exit requirements',), ('3.2.2.', '3.2.5.', '9.10.8.', '3.4.2.', '3.2.3.', '9.10.15.'),
          ('sprinkler', 'fire'), base=6),
    Probe('limiting_distance_m',
          'How far is that wall from the property line?',
          'The distance to the property line decides which spatial-separation requirements and opening limits apply.',
          ('spatial-separation requirements',), ('9.10.14.', '9.10.15.', '3.2.3.'),
          ('property line', 'lot line', 'neighbour', 'side yard', 'eave', 'soffit', 'lane', 'fence')),
    Probe('faces_public_way', 'What is on the other side of that wall?',
          'Whether the wall faces a public way changes which soffit projection requirements apply.',
          ('soffit projection requirements',), ('9.10.14.', '9.10.15.', '3.2.3.'),
          ('property line', 'lot line', 'neighbour', 'side yard', 'eave', 'soffit', 'lane', 'street', 'fence')),
    Probe('dwelling_units', 'How many dwelling units (homes or suites) are in the building?',
          'The number of dwellings changes which separation, smoke-alarm and exit requirements apply.',
          ('suite and dwelling requirements',), ('9.10.9.', '9.10.19.', '3.3.4.', '9.9.9.'),
          ('suite', 'unit', 'apartment', 'dwelling', 'rental')),
    Probe('part4_design', 'Is a registered engineer designing the structure under Part 4?',
          'Part 4 design changes which structural requirements are the benchmark and when an engineer is required.',
          ('structural requirements', 'professional involvement'), ('4.', '9.4.', '9.23.'),
          ('load', 'beam', 'span', 'structur', 'snow', 'wind', 'foundation')),
    Probe('assembly.description', 'What is the wall, floor or roof assembly made of, layer by layer?',
          'The materials and their fire or thermal properties decide which assembly, insulation and fire-resistance '
          'requirements apply.', ('assembly requirements',),
          ('9.10.3.', '9.25.', '9.23.', '9.27.', '9.36.', '3.1.5.', '3.1.7.'),
          ('wall', 'assembly', 'sheathing', 'insulation', 'cladding', 'siding', 'board', 'panel')),
    Probe('product_scope', 'One building, or across Alberta?',
          'A variance is a decision for one building or site. Acceptance everywhere is a product-evaluation route.',
          ('the application route',), (), ('product', 'manufactur', 'sell', 'market', 'across alberta'), base=0),
    Probe('owner_name', "What is the owner's name?", 'Section A of the variance form names the owner.',
          ('Section A',), priority='administrative'),
    Probe('municipal_address', 'What is the municipal address of the site?',
          'Section B of the variance form identifies the property.', ('Section B',), priority='administrative'),
    Probe('legal_description', 'What is the legal description (lot, block and plan, or ATS)?',
          'Section B of the variance form identifies the property.', ('Section B',), priority='administrative'),
    Probe('mailing_address', 'What mailing address should the officer use?',
          'Section A of the variance form needs a mailing address.', ('Section A',), priority='administrative'),
)
PROBE_BY_FIELD = {probe.field: probe for probe in PROBES}
# The value already on the case answers these too.
ALIASES = {'building_area_m2': ('building_area_m2', 'floor_area_m2', 'building_area_ft2'),
           'legal_description': ('legal_description', 'lot', 'plan', 'ats_sec'),
           'assembly.description': ('assembly.description',)}


def question_id(field: str) -> str:
    return 'intake.' + field


def issued_questions(facts: Iterable[Fact], previous: IntakePlan | None) -> list[Question]:
    """Recover only probes whose issuance this case's saved answer or uncertainty already proves."""
    answered = {'storeys' if f.field == 'building.storeys' else f.field for f in facts
                if f.source.ref == 'intake answer' and f.status == 'confirmed'}
    not_sure = set(previous.not_sure) if previous else set()
    recovered = [Question(id=question_id(p.field), field=p.field, text=p.text, why=p.why,
                          priority=p.priority, unblocks=list(p.unblocks)) for p in PROBES
                 if p.field in answered or question_id(p.field) in not_sure]
    stored = [*previous.asked, *previous.questions] if previous else []
    return list({q.id: q for q in [*recovered, *stored]}.values())


def plan_questions(*, known: set[str], prose: str, candidates: list[dict], conflicts: list[FieldConflict],
                   not_sure: set[str], role: str | None, departure_known: bool, cap: int = CAP) -> list[Question]:
    """`known`: fields with a value on the case. `candidates`: identify articles still open
    ({'provision', 'title'}), most likely first. Deterministic."""
    low = (prose or '').lower()
    scored: list[tuple[int, int, Question]] = []
    for order, conflict in enumerate(conflicts):
        probe = PROBE_BY_FIELD.get(conflict.field)
        if probe is None or question_id(conflict.field) in not_sure:
            continue
        if any(name in known for name in ALIASES.get(conflict.field, (conflict.field,))):
            continue                                 # answered since: the applicant's value settles it
        said = ', '.join(f'"{q}"' for q in dict.fromkeys(conflict.quotes))
        scored.append((1000, -order, Question(
            id=question_id(conflict.field), field=conflict.field, kind='conflict', priority=probe.priority,
            text=f'You wrote {said}. {probe.text}', why='Two different values were written, so neither is used yet. '
            + probe.why, unblocks=list(probe.unblocks))))
    conflicted = {c.field for c in conflicts}
    for order, probe in enumerate(PROBES):
        qid = question_id(probe.field)
        if probe.field in conflicted or qid in not_sure:
            continue
        if any(name in known for name in ALIASES.get(probe.field, (probe.field,))):
            continue
        if probe.field == 'alternative_description' and departure_known:
            continue
        if probe.field == 'product_scope' and role != 'manufacturer' and not any(word in low for word in probe.prose):
            continue
        hits = [c['provision'] for c in candidates if any(str(c.get('provision', '')).startswith(p) for p in probe.prefixes)]
        mentioned = any(word in low for word in probe.prose)
        split = min(len(hits), max(0, len(candidates) - len(hits)))
        if probe.priority == 'administrative':
            score = 1
        else:
            score = split * 10 + len(hits) * 2 + probe.base + (8 if mentioned else 0) + (50 if probe.field == 'product_scope' else 0)
            if score == 0:
                continue                         # nothing in the words or the candidates makes it matter
        scored.append((score, -order, Question(id=qid, field=probe.field, text=probe.text, why=probe.why,
                                               unblocks=list(probe.unblocks), splits=hits[:10], priority=probe.priority)))
    scored.sort(key=lambda item: (-item[0], -item[1]))
    return [question for _, _, question in scored[:cap]]
