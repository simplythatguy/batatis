"""Repair PDF extraction artifacts in code text.

The registered JSONL preserves extraction provenance. SourceText attaches a reading
form from the paired PDF's character geometry, without changing the raw string.
Only whitespace-equivalent spans are aligned; font matrices and baseline offsets
recover Unicode scripts. Unalignable or ambiguous spans stay verbatim. Plain strings
retain the legacy corpus segmentation used by attribution parsing. Rebuilding needs
pypdfium2 (also an engine dependency); database queries do not.
"""
from __future__ import annotations

import ctypes
import math
import re
import unicodedata
from collections import Counter
from functools import lru_cache

_WORD = re.compile(r"[A-Za-z]+")
# A run of >=3 tokens (all short except possibly the last), at least half single letters.
_TOK = r"(?:[a-z]{1,2}|[a-z][A-Z]|[A-Z][a-z])[,.;:]? "
_RUN = re.compile(r"(?<![\w-])[A-Za-z]{1,2}[,.;:]? (?:" + _TOK + r"){1,}[A-Za-z]?[a-z]{0,25}(?![\w])[,.;:]?")


class Segmenter:
    def __init__(self, texts):
        c = Counter()
        self.hyphenated = set()
        for t in texts:
            self.hyphenated.update(m[0].lower() for m in re.finditer(r"\b[A-Za-z]+-[A-Za-z]+\b", t))
            for w in _WORD.findall(t):
                if len(w) > 1 or w.lower() in ("a", "i"):
                    c[w.lower()] += 1
        # drop rare 1-2 letter fragments that are themselves artifacts of letter spacing
        for w in list(c):
            if len(w) <= 2 and c[w] < 50 and w not in _SHORT_OK:
                del c[w]
        total = sum(c.values()) or 1
        self.cost = {w: -math.log(n / total) for w, n in c.items()}
        self.maxlen = max((len(w) for w in c), default=1)
        self.unknown = -math.log(1 / (total * 10))

    def split(self, s: str) -> list[str]:
        n = len(s)
        best = [0.0] + [math.inf] * n
        back = [0] * (n + 1)
        for i in range(1, n + 1):
            for j in range(max(0, i - self.maxlen), i):
                w = s[j:i]
                c = self.cost.get(w.lower())
                if c is None:
                    c = self.unknown * (i - j)
                if best[j] + c < best[i]:
                    best[i], back[i] = best[j] + c, j
        words, i = [], n
        while i > 0:
            words.append(s[back[i]:i])
            i = back[i]
        return words[::-1]


_SHORT_OK = {"a", "i", "an", "as", "at", "be", "by", "do", "if", "in", "is", "it", "no", "of", "on", "or", "to",
             "up", "we", "so", "m", "mm", "kg", "kpa", "id"}


def _fix_run(m: re.Match, seg: Segmenter) -> str:
    run = m.group(0)
    toks = run.split()
    singles = sum(1 for t in toks if len(t.strip(",.;:")) == 1)
    if singles * 2 < len(toks):
        return run
    trail = ""
    joined = "".join(toks)
    # keep punctuation attached to the token it followed
    pieces, buf = [], ""
    for ch in joined:
        if ch in ",.;:":
            if buf:
                pieces.append((buf, ch)); buf = ""
            else:
                trail += ch
        else:
            buf += ch
    if buf:
        pieces.append((buf, ""))
    out = []
    for letters, punct in pieces:
        out.append(" ".join(seg.split(letters)) + punct)
    return " ".join(out) + trail


def repair(text: str, seg: Segmenter | None) -> str:
    if isinstance(text, SourceText):
        # Geometry, rather than unigram guesses, supplies the word boundaries.
        # A discretionary hyphen is removed only with corpus support. A real
        # compound (or an unknown word) keeps its hyphen.
        seg = _source_segmenter(text.source) if text.source else seg

        def hyphen(m):
            a, b = m[1], m[2]
            joined = (a + b).lower()
            compound = (a + '-' + b).lower()
            if seg and joined in seg.cost and compound not in seg.hyphenated:
                return a + b
            return a + '-' + b
        t = re.sub(r"([A-Za-z]+)\u00ad\s*([A-Za-z]+)", hyphen, text.readable)
        return t.replace('\u00ad', '-')
    t = text
    t = re.sub(r"\b(O[SHAPE]\d+) \.(\d)", r"\1.\2", t)          # "OS1 .1" -> "OS1.1"
    t = re.sub(r"\bF(\d) (\d)\b", r"F\1\2", t)                   # "F1 1" -> "F11"
    t = re.sub(r",(a n d|o r)\b", lambda m: ", " + m.group(1).replace(" ", ""), t)
    if seg is not None:
        t = _RUN.sub(lambda m: _fix_run(m, seg), t)
    t = re.sub(r"(\w) ([,;:])(?=\s|$)", r"\1\2", t)               # "sprinklered , each"
    t = re.sub(r"(\w)\s+\.(\s|$)", r"\1.\2", t)
    t = re.sub(r"(\S)- \n?(?=[a-z])", r"\1-", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t


def flat(text: str) -> str:
    """Whitespace-insensitive form for comparing against page text."""
    return re.sub(r"\s+", "", text)


class SourceText(str):
    """Raw text with a separately aligned reading form; SQLite stores the raw str.

    Keeping the original string value preserves text_raw, parser labels, source
    audits and citations. Only repair() consumes the reading form.
    """
    def __new__(cls, raw, readable, unmatched=(), source=None):
        obj = super().__new__(cls, raw)
        obj.readable = readable
        obj.unmatched = tuple(unmatched)
        obj.source = source
        return obj


def _alignment(text):
    # Ligatures and native superscripts can have different Unicode encodings
    # in independent extractors. This key is never emitted as the reading text.
    return ''.join(unicodedata.normalize('NFKC', c) for c in text if not c.isspace())


@lru_cache(maxsize=4)
def _source_segmenter(key):
    from .sources import load_pages
    return Segmenter(' '.join(p.lines) for p in load_pages(key))


@lru_cache(maxsize=4)
def _pdf(key):
    # Already used by the application; needed only for rebuilding text, not queries.
    try:
        import pypdfium2
    except ImportError as exc:
        raise RuntimeError('Text rebuild requires pypdfium2; install engine/requirements.txt') from exc
    from .sources import DOCS
    return pypdfium2.PdfDocument(DOCS[key].pdf)


class PageText:
    def __init__(self, original, readable):
        self.original = original
        compact_parts = []
        self.offsets = []
        self.readable = tuple(readable)
        for i, c in enumerate(original):
            compact = _alignment(c)
            compact_parts.append(compact)
            self.offsets.extend([i] * len(compact))
        self.key = ''.join(compact_parts)

    def candidates(self, raw):
        key = _alignment(raw)
        if not key:
            return {raw}
        matches = set()
        at = self.key.find(key)
        while at >= 0:
            begin, end = self.offsets[at], self.offsets[at + len(key) - 1] + 1
            if _alignment(self.original[begin:end]) == key:
                # Never take only half of a multi-letter ligature.
                matches.add(re.sub(r'\s+', ' ', ''.join(self.readable[begin:end])).strip())
            at = self.key.find(key, at + 1)
        return matches


@lru_cache(maxsize=128)
def page_text(key, page_number):
    """Recover PDFium's positioned boundaries and raised/lowered glyphs.

    The JSONL registry has page/text only, so geometry comes from its paired PDF.
    Character identity must match before a reconstructed line can be used.
    """
    doc = _pdf(key)
    import pypdfium2.raw as pdfium
    page = doc[page_number - 1]
    tp = page.get_textpage()
    try:
        chars = []
        discretionary = set()
        for i in range(tp.count_chars()):
            cp = pdfium.FPDFText_GetUnicode(tp.raw, i)
            if pdfium.FPDFText_IsHyphen(tp.raw, i) == 1:
                chars.append('-')
                discretionary.add(i)
            else:
                chars.append(chr(cp) if cp else '\x00')
        readable = chars.copy()
        for i in discretionary:
            readable[i] = '\u00ad'
        geometry = {}

        def geom(i):
            if i not in geometry:
                matrix = pdfium.FS_MATRIX()
                pdfium.FPDFText_GetMatrix(tp.raw, i, matrix)
                x, y = ctypes.c_double(), ctypes.c_double()
                pdfium.FPDFText_GetCharOrigin(tp.raw, i, x, y)
                size = pdfium.FPDFText_GetFontSize(tp.raw, i) * math.hypot(matrix.a, matrix.b)
                geometry[i] = (x.value, y.value, size, abs(matrix.b) + abs(matrix.c) < 0.01)
            return geometry[i]

        raised = str.maketrans('0123456789+-()', '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁽⁾')
        lowered = str.maketrans('0123456789+-()', '₀₁₂₃₄₅₆₇₈₉₊₋₍₎')
        for i, c in enumerate(chars):
            if c not in '0123456789+-()':
                continue
            x, y, size, horizontal = geom(i)
            if not horizontal:
                continue
            neighbours = []
            for j in range(max(0, i-4), min(len(chars), i+5)):
                if j == i or not chars[j].isalnum():
                    continue
                bx, by, base, bh = geom(j)
                if bh and base > 0 and abs(bx-x) < 4*base and abs(by-y) < 0.65*base:
                    neighbours.append((base, by))
            if neighbours:
                base, baseline = max(neighbours)
                delta = y - baseline
                if 0 < size < 0.82*base and 0.15*base < abs(delta) < 0.65*base:
                    readable[i] = c.translate(raised if delta > 0 else lowered)
                    # PDFium sometimes inserts a synthetic word space before a
                    # raised unit exponent. Keep encoded spaces; attach only the
                    # generated spaces to the script's base glyph.
                    j = i - 1
                    while j >= 0 and chars[j] in ' \t' and pdfium.FPDFText_IsGenerated(tp.raw, j) == 1:
                        readable[j] = ''
                        j -= 1
        return PageText(''.join(chars), readable)
    finally:
        tp.close()
        page.close()


def source_text(raw, key, first, last=None):
    """Align lines without changing any non-whitespace source character.

    Reordered formula/table fragments that cannot be aligned remain verbatim and
    are exposed through unmatched. This never invents words, digits or operators.
    """
    if key is None:
        return raw
    sources = [page_text(key, p) for p in range(first, (last or first) + 1)]
    lines, unmatched = [], []
    for line in raw.split('\n'):
        candidates = {t for source in sources for t in source.candidates(line)}
        if len(candidates) == 1:
            lines.append(candidates.pop())
        else:
            lines.append(line)
            if line.strip():
                unmatched.append(line)
    return SourceText(raw, '\n'.join(lines), unmatched, key)
