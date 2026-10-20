"""Repair PDF extraction artifacts in code text.

The registered JSONL preserves extraction provenance. SourceText attaches a reading
form from the paired PDF's character geometry, without changing the raw string.
Only whitespace-equivalent spans are aligned; font matrices and baseline offsets
recover Unicode scripts. Unalignable or ambiguous spans stay verbatim. Plain strings
retain the legacy corpus segmentation used by attribution parsing. Rebuilding needs
pypdfium2; database queries do not.
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
    def __new__(cls, raw, readable, unmatched=(), source=None, uncertain_lines=()):
        obj = super().__new__(cls, raw)
        obj.readable = readable
        obj.unmatched = tuple(unmatched)
        obj.source = source
        obj.uncertain_lines = tuple(uncertain_lines)
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
        raise RuntimeError('Text rebuild requires pypdfium2; install codedb/requirements.txt') from exc
    from .sources import DOCS
    return pypdfium2.PdfDocument(DOCS[key].pdf)


class PageText:
    def __init__(self, original, readable, uncertain=()):
        self.original = original
        compact_parts = []
        self.offsets = []
        self.readable = tuple(readable)
        self.uncertain = tuple(uncertain)
        for i, c in enumerate(original):
            compact = _alignment(c)
            compact_parts.append(compact)
            self.offsets.extend([i] * len(compact))
        self.key = ''.join(compact_parts)

    def _candidates(self, raw):
        key = _alignment(raw)
        if not key:
            return {raw}, False
        matches = set()
        uncertain = False
        at = self.key.find(key)
        while at >= 0:
            begin, end = self.offsets[at], self.offsets[at + len(key) - 1] + 1
            if _alignment(self.original[begin:end]) == key:
                # Never take only half of a multi-letter ligature.
                matches.add(re.sub(r'\s+', ' ', ''.join(self.readable[begin:end])).strip())
                uncertain |= any(first < end and last > begin for first, last in self.uncertain)
            at = self.key.find(key, at + 1)
        return matches, uncertain

    def candidates(self, raw):
        matches, uncertain = self._candidates(raw)
        return set() if uncertain else matches


def _restore_scripts(chars, geom, generated):
    """Project a homogeneous glyph run together, or keep the entire run flat.

    A per-character context window gives digits at opposite ends of a run
    different evidence. Use the run's external context once. Unsupported letters
    and conflicting baselines prevent conversion of the whole run; a missing
    image-rendered base symbol is never synthesized.
    """
    readable, uncertain = chars.copy(), []
    script_chars = '0123456789+-()'
    raised = str.maketrans(script_chars, '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁽⁾')
    lowered = str.maketrans(script_chars, '₀₁₂₃₄₅₆₇₈₉₊₋₍₎')

    def same_style(a, b):
        _, ay, size, horizontal = a
        _, by, other, bh = b
        return (horizontal and bh and size > 0 and
                abs(size-other) <= 0.01*size and abs(ay-by) <= 0.03*size)

    for token in re.finditer(r'\S+', ''.join(chars)):
        if not any(c in script_chars for c in token[0]):
            continue
        start = token.start()
        runs = []
        for i in range(start + 1, token.end()):
            if not same_style(geom(start), geom(i)):
                runs.append((start, i))
                start = i
        runs.append((start, token.end()))
        for start, end in runs:
            if not any(c in script_chars for c in chars[start:end]):
                continue  # Pure letter runs are outside this digit/operator projection.
            x, y, size, horizontal = geom(start)
            if not horizontal:
                continue
            last_x = geom(end - 1)[0]
            neighbours = []
            for j in (*range(max(0, start-4), start), *range(end, min(len(chars), end+4))):
                if not chars[j].isalnum():
                    continue
                bx, by, base, bh = geom(j)
                distance = max(min(x, last_x)-bx, 0, bx-max(x, last_x))
                if bh and base > 0 and distance < 4*base and abs(by-y) < 0.65*base:
                    neighbours.append((base, by))
            if not neighbours:
                continue
            base = max(n[0] for n in neighbours)
            if not 0 < size < 0.82*base:
                continue
            modes = set()
            for reference_size, baseline in neighbours:
                if abs(reference_size-base) <= 0.01*base:
                    delta = y - baseline
                    modes.add((1 if delta > 0 else -1) if 0.15*base < abs(delta) < 0.65*base else 0)
            if modes not in ({1}, {-1}):
                if modes & {-1, 1}:
                    uncertain.append((start, end))
                continue
            if not all(c in script_chars for c in chars[start:end]):
                # This digit/operator mapping does not cover decimal points,
                # fraction slashes or letters. Preserve and audit the whole raw
                # line instead of projecting only part of the script run.
                uncertain.append((start, end))
                continue
            translation = raised if modes == {1} else lowered
            for i in range(start, end):
                readable[i] = chars[i].translate(translation)
            # Only synthetic spaces before a script run are attached to its
            # base. Encoded spaces remain part of the source reading.
            j = start - 1
            while j >= 0 and chars[j] in ' \t' and generated(j):
                readable[j] = ''
                j -= 1
    return readable, uncertain


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

        readable, uncertain = _restore_scripts(chars, geom, lambda i: pdfium.FPDFText_IsGenerated(tp.raw, i) == 1)
        for i in discretionary:
            readable[i] = '\u00ad'
        return PageText(''.join(chars), readable, uncertain)
    finally:
        tp.close()
        page.close()


def source_text(raw, key, first, last=None):
    """Align lines without changing any non-whitespace source character.

    Reordered formula/table fragments and unrepresentable/ambiguous script runs
    keep their entire raw line and are exposed through unmatched. This never
    invents words, digits or operators, including image-rendered base symbols.
    """
    if key is None:
        return raw
    sources = [page_text(key, p) for p in range(first, (last or first) + 1)]
    lines, unmatched, uncertain_lines = [], [], []
    for line in raw.split('\n'):
        candidates, uncertain = set(), False
        for source in sources:
            found, blocked = source._candidates(line)
            candidates.update(found)
            uncertain |= blocked
        if len(candidates) == 1 and not uncertain:
            lines.append(candidates.pop())
        else:
            lines.append(line)
            if line.strip():
                unmatched.append(line)
                if uncertain:
                    uncertain_lines.append(line)
    return SourceText(raw, '\n'.join(lines), unmatched, key, uncertain_lines)
