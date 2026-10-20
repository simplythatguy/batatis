"""Repair PDF extraction artifacts in code text.

The NRC PDFs letter-space some justified lines, so plain extraction yields
"w o u l dr e s t r i c te s c a p e" and "OS1 .1". We keep the raw text for page
verification and store a repaired text for reading and search. Repair = collapse a
run of letter-spaced tokens and re-segment it with a word list learned from the same
document (dynamic programming over unigram costs).
"""
from __future__ import annotations

import math
import re
from collections import Counter

_WORD = re.compile(r"[A-Za-z]+")
# A run of >=3 tokens (all short except possibly the last), at least half single letters.
_TOK = r"(?:[a-z]{1,2}|[a-z][A-Z]|[A-Z][a-z])[,.;:]? "
_RUN = re.compile(r"(?<![\w-])[A-Za-z]{1,2}[,.;:]? (?:" + _TOK + r"){1,}[A-Za-z]?[a-z]{0,25}(?![\w])[,.;:]?")


class Segmenter:
    def __init__(self, texts):
        c = Counter()
        for t in texts:
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
