"""Pull building facts out of an applicant's description.

Two extractors are kept so the labelled comparison in
``evals_dev/description_facts/`` can be re-run. ``extract_description`` is the
winner (rules plus a normaliser). Extracted facts are unconfirmed and marked
with source type ``description``. Only the interrogative clause or sentence is
left out of the proposed-alternative text. Nothing here is a professional opinion.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

FT_TO_M = 0.3048
SQFT_TO_M2 = 0.09290304

_WORDS = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
    'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14,
    'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20,
}
_WORD_ALT = '|'.join(_WORDS)
_WH = re.compile(r'^(?:what|how|why|when|where|which|who)\b', re.I)
_STOREY_RE = re.compile(
    rf'\b(?P<n>\d+|{_WORD_ALT})[\s-]*stor(?:e)?ys?\b', re.I)
_AREA_METRIC_RE = re.compile(
    r'\b(?P<n>\d+(?:\.\d+)?)\s*(?:m²|m2|sq\.?\s*m(?:etres?)?|square\s+metres?)\b', re.I)
_SPAN_RE = re.compile(
    r'\bspan(?:s|ning)?\b(?:\s+\w+){0,5}\s+(?P<n>\d+(?:\.\d+)?)[\s-]*(?P<u>m|metres?|meters?|ft|feet|foot)\b'
    r'|\b(?P<n2>\d+(?:\.\d+)?)[\s-]*(?P<u2>m|metres?|meters?|ft|feet|foot)\b(?:\s+\w+){0,4}\s+span\b',
    re.I)
_OCCUPANCY = (
    ('relocatable_industrial_camp', re.compile(r'relocatable industrial camps?', re.I)),
    ('multi_family', re.compile(r'\b(?:multi[-\s]?family|duplex|triplex|fourplex|apartments?)\b', re.I)),
    ('single_family', re.compile(
        r'\b(?:single[-\s]?family|detached(?:\s+(?:house|home))?|garden suite|garage suite|laneway suite|secondary suite)\b',
        re.I)),
    ('hotel', re.compile(r'\b(?:hotel|motel)\b', re.I)),
    ('assembly', re.compile(r'\b(?:assembly occupancy|assembly hall|theatre|theater|church)\b', re.I)),
    ('care', re.compile(r'\b(?:care occupancy|nursing home|group home)\b', re.I)),
    ('treatment', re.compile(r'\b(?:treatment occupancy|hospital)\b', re.I)),
    ('detention', re.compile(r'\b(?:detention occupancy|detention|jail|prison)\b', re.I)),
    ('mercantile', re.compile(r'\b(?:mercantile|retail store|retail occupancy)\b', re.I)),
    ('business', re.compile(r'\b(?:business occupancy|office building)\b', re.I)),
    # Hyphenated modifiers (factory-bonded, warehouse-style) are product words, not a building.
    ('industrial', re.compile(
        r'(?<!-)\b(?:industrial occupancy|warehouse|factory)\b(?!-)', re.I)),
    ('farm', re.compile(r'\b(?:farm building|barn)\b', re.I)),
    ('mixed', re.compile(r'\b(?:mixed[-\s]?use)\b', re.I)),
)


@dataclass(frozen=True)
class ExtractedFact:
    field: str
    value: int | float | str
    quote: str
    source: str = 'description'


@dataclass(frozen=True)
class DescriptionExtract:
    alternative_description: str | None
    facts: tuple[ExtractedFact, ...]


_RESIDENTIAL = frozenset({'single_family', 'multi_family'})


def _protect(text: str) -> str:
    """Keep abbreviations such as ``sq. ft.`` from looking like sentence ends."""
    return re.sub(
        r'\b(?:sq|ft|m|no|fig)\.\s+(?=[a-z])',
        lambda match: match.group(0).replace('.', '\0'),
        text, flags=re.I)


def _restore(text: str) -> str:
    return text.replace('\0', '.')


def is_question(sentence: str) -> bool:
    """A question to the tool, not a statement that merely sits beside one."""
    stripped = sentence.strip()
    return '?' in stripped or bool(_WH.match(stripped))


def _without_question_clause(piece: str) -> str | None:
    """Drop a question sentence, or only the comma-clause that contains ``?``."""
    raw = _restore(piece)
    if not raw.strip():
        return None
    if '?' in raw:
        clauses = [clause for clause in raw.split(',') if clause.strip() and not is_question(clause)]
        if not clauses:
            return None
        return ','.join(clauses)
    if is_question(raw):
        return None
    return raw


def _filter_line(line: str) -> str:
    """Apply sentence and ``;`` / ``—`` splits inside one line, then drop questions."""
    tokens = re.split(r'((?<=[.!?])\s+|\s*;\s*|\s*—\s*)', _protect(line))
    kept: list[str] = []
    for index in range(0, len(tokens), 2):
        piece = _without_question_clause(tokens[index])
        if piece is None:
            continue
        if kept:
            kept.append(tokens[index - 1])
        kept.append(piece)
    return ''.join(kept).strip()


def _without_questions(text: str) -> str:
    """Drop interrogative lines and clauses. Leave every other line in place."""
    lines: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            lines.append('')
            continue
        filtered = _filter_line(line)
        if filtered:
            lines.append(filtered)
    return '\n'.join(lines).strip()


def sentences(text: str) -> list[str]:
    """Split on sentence and line boundaries and on ``;`` or ``—`` list separators.

    A comma is not a boundary. Abbreviations such as ``sq. ft.`` stay together.
    """
    pieces: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = re.split(r'(?<=[.!?])\s+|\s*;\s*|\s*—\s*', _protect(stripped))
        for part in parts:
            cleaned = _restore(part).strip()
            if cleaned:
                pieces.append(cleaned)
    return pieces


def narrative_sentences(text: str) -> list[str]:
    """Statements only. A ``?`` drops that clause, not the rest of the row."""
    return [sentence for sentence in sentences(_without_questions(text)) if sentence.strip()]


def alternative_text(text: str) -> str | None:
    """Non-question remainder. Line breaks stay unless they follow sentence punctuation."""
    filtered = _without_questions(text)
    if not filtered:
        return None
    parts = re.split(r'(?<=[.!?])\s+', _protect(filtered))
    kept = [_restore(part).strip() for part in parts if part.strip()]
    if not kept:
        return None
    return ' '.join(kept)


def _occupancy(text: str) -> str | None:
    """Building-use words only. One residential category wins; a conflict stays empty.

    A wrong occupancy is worse than none. Product or process adjectives never match.
    """
    found = [name for name, pattern in _OCCUPANCY if pattern.search(text)]
    residential = [name for name in found if name in _RESIDENTIAL]
    if len(residential) == 1:
        return residential[0]
    if residential:
        return None
    return found[0] if len(found) == 1 else None


def _storey_value(token: str) -> int | None:
    if token.isdigit():
        number = int(token)
    else:
        number = _WORDS.get(token.casefold())
    if number is None or not 1 <= number <= 40:
        return None
    return number


def _round(value: float) -> float:
    return round(value + 0.0, 2)


def extract_regex(text: str) -> DescriptionExtract:
    """Digit and hyphen rules on the original wording. Metric area and span only.

    Feet and number-words that are not in the storey list are left unextracted
    rather than stored as metres.
    """
    facts: list[ExtractedFact] = []
    narrative = narrative_sentences(text)
    body = ' '.join(narrative)
    for sentence in narrative:
        match = _STOREY_RE.search(sentence)
        if match and not any(fact.field == 'storeys' for fact in facts):
            value = _storey_value(match.group('n'))
            if value is not None:
                facts.append(ExtractedFact('storeys', value, sentence))
        match = _AREA_METRIC_RE.search(sentence)
        if match and not any(fact.field == 'building_area_m2' for fact in facts):
            facts.append(ExtractedFact('building_area_m2', _round(float(match.group('n'))), sentence))
        match = _SPAN_RE.search(sentence)
        if match and not any(fact.field == 'span_m' for fact in facts):
            number = match.group('n') or match.group('n2')
            unit = (match.group('u') or match.group('u2') or '').casefold()
            if number and unit in ('m', 'metre', 'metres', 'meter', 'meters'):
                facts.append(ExtractedFact('span_m', _round(float(number)), sentence))
    occupancy = _occupancy(body)
    if occupancy:
        quote = next((sentence for sentence in narrative if _occupancy(sentence) == occupancy), body)
        facts.append(ExtractedFact('occupancy', occupancy, quote))
    return DescriptionExtract(alternative_text(text), tuple(facts))


def _normalise_sentence(sentence: str) -> str:
    text = sentence.casefold().replace('²', '2').replace('’', "'")
    text = re.sub(r'(?<=\d),(?=\d)', '', text)
    text = re.sub(
        rf'\b({_WORD_ALT})\b(?=\s*-?\s*(?:stor|m|ft|feet|foot|sq|square))',
        lambda match: str(_WORDS[match.group(1).casefold()]), text, flags=re.I)
    text = re.sub(r'(\d)\s*-\s*(?=stor)', r'\1 ', text)
    text = re.sub(r'square\s+metres?', 'm2', text)
    text = re.sub(r'sq\.?\s*m(?:etres?)?', 'm2', text)
    text = re.sub(r'\bm\s*2\b', 'm2', text)
    text = re.sub(r'square\s+feet', 'sqft', text)
    text = re.sub(r'sq\.?\s*ft\.?', 'sqft', text)
    text = re.sub(r'\bft2\b', 'sqft', text)
    text = re.sub(r'\bmetres?\b', 'm', text)
    text = re.sub(r'\bmeters?\b', 'm', text)
    text = re.sub(r'\bfeet\b', 'ft', text)
    text = re.sub(r'\bfoot\b', 'ft', text)
    text = re.sub(r'(\d)\s*-\s*(?=(?:ft|m|sqft|m2)\b)', r'\1 ', text)
    return text


_N_STOREY = re.compile(r'\b(\d+)\s+stor(?:e)?ys?\b')
_N_AREA = re.compile(r'\b(\d+(?:\.\d+)?)\s*(m2|sqft)\b')
_N_SPAN = re.compile(
    r'\bspan(?:s|ning)?\b(?:\s+\w+){0,5}\s+(\d+(?:\.\d+)?)\s*(m|ft)\b'
    r'|(\d+(?:\.\d+)?)\s*(m|ft)\b(?:\s+\w+){0,4}\s+span\b')


def extract_normalised(text: str) -> DescriptionExtract:
    """Regex rules after number words, hyphens and unit names are folded together."""
    facts: list[ExtractedFact] = []
    narrative = narrative_sentences(text)
    for sentence in narrative:
        folded = _normalise_sentence(sentence)
        if not any(fact.field == 'storeys' for fact in facts):
            match = _N_STOREY.search(folded)
            if match:
                value = _storey_value(match.group(1))
                if value is not None:
                    facts.append(ExtractedFact('storeys', value, sentence))
        if not any(fact.field == 'building_area_m2' for fact in facts):
            match = _N_AREA.search(folded)
            if match:
                number = float(match.group(1))
                if match.group(2) == 'sqft':
                    number *= SQFT_TO_M2
                facts.append(ExtractedFact('building_area_m2', _round(number), sentence))
        if not any(fact.field == 'span_m' for fact in facts):
            match = _N_SPAN.search(folded)
            if match:
                number = float(match.group(1) or match.group(3))
                unit = match.group(2) or match.group(4)
                if unit == 'ft':
                    number *= FT_TO_M
                facts.append(ExtractedFact('span_m', _round(number), sentence))
    body = ' '.join(narrative)
    occupancy = _occupancy(body)
    if occupancy:
        quote = next((sentence for sentence in narrative if _occupancy(sentence) == occupancy), body)
        facts.append(ExtractedFact('occupancy', occupancy, quote))
    return DescriptionExtract(alternative_text(text), tuple(facts))


# Winner of evals_dev/description_facts/RESULTS.md (synthetic, in-sample).
EXTRACTORS = {'regex': extract_regex, 'normalised': extract_normalised}
WINNER = 'normalised'


def extract_description(text: str) -> DescriptionExtract:
    return EXTRACTORS[WINNER](text)


_SCORE_FIELDS = ('storeys', 'building_area_m2', 'span_m', 'occupancy', 'alternative_description')


def _same(field: str, gold, pred) -> bool:
    if field in ('building_area_m2', 'span_m'):
        return gold is not None and pred is not None and abs(float(gold) - float(pred)) <= 0.02
    if field == 'alternative_description':
        norm = lambda value: ' '.join(value.split()) if isinstance(value, str) else value  # noqa: E731
        return norm(gold) == norm(pred)
    return gold == pred


def score_variant(rows: list[dict], name: str) -> dict:
    """Field-level counts. A null gold and a null prediction are not a true positive."""
    counts = {field: {'tp': 0, 'fp': 0, 'fn': 0} for field in _SCORE_FIELDS}
    for row in rows:
        extracted = EXTRACTORS[name](row['text'])
        predicted = {fact.field: fact.value for fact in extracted.facts}
        predicted['alternative_description'] = extracted.alternative_description
        for field in _SCORE_FIELDS:
            gold, pred = row.get(field), predicted.get(field)
            if gold is None and pred is None:
                continue
            if _same(field, gold, pred):
                counts[field]['tp'] += 1
            else:
                if pred is not None:
                    counts[field]['fp'] += 1
                if gold is not None:
                    counts[field]['fn'] += 1
    report = {}
    totals = {'tp': 0, 'fp': 0, 'fn': 0}
    for field, count in counts.items():
        precision = count['tp'] / (count['tp'] + count['fp']) if count['tp'] + count['fp'] else 1.0
        recall = count['tp'] / (count['tp'] + count['fn']) if count['tp'] + count['fn'] else 1.0
        report[field] = {'precision': precision, 'recall': recall, **count}
        for key in totals:
            totals[key] += count[key]
    precision = totals['tp'] / (totals['tp'] + totals['fp']) if totals['tp'] + totals['fp'] else 1.0
    recall = totals['tp'] / (totals['tp'] + totals['fn']) if totals['tp'] + totals['fn'] else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    report['micro'] = {'precision': precision, 'recall': recall, 'f1': f1, **totals}
    return report
