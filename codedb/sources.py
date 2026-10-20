"""Source documents: which PDFs/page texts are citable, and how to read their pages.

The registry is the single place that knows edition status. Everything else asks it.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT_DIR = ROOT / "reference" / "text"
CODES_DIR = ROOT / "reference" / "codes"
BUILD_DIR = Path(__file__).resolve().parent / "build"


@dataclass(frozen=True)
class CodeDoc:
    key: str            # short key used in the DB ("NBC-AE")
    label: str          # citation label
    stem: str           # reference/text/<stem>.jsonl and reference/codes/<stem>.pdf
    kind: str           # "code" (citable acceptable solutions) | "intent" (explanatory supplement)
    citable: bool       # may be cited as Alberta law
    footer_marker: str = ""   # substring identifying running footers
    family: str = ""    # NBC | NFC

    @property
    def jsonl(self) -> Path:
        return TEXT_DIR / f"{self.stem}.jsonl"

    @property
    def pdf(self) -> Path:
        return CODES_DIR / f"{self.stem}.pdf"


DOCS = {
    d.key: d
    for d in [
        CodeDoc("NBC-AE", "NBC(AE) 2023 p2", "NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2", "code", True,
                "National Building Code – 2023 Alberta Edition", "NBC"),
        CodeDoc("NFC-AE", "NFC(AE) 2023 p2", "NFC-AE-2023-2nd-printing", "code", True,
                "National Fire Code – 2023 Alberta Edition", "NFC"),
        CodeDoc("NBC-2020-IS", "NBC 2020 Intent Statements", "NBC-2020-Intent-Statements", "intent", False, "", "NBC"),
        CodeDoc("NFC-2020-IS", "NFC 2020 Intent Statements", "NFC-Intent-Statements", "intent", False, "", "NFC"),
    ]
}

# Editions that must never be cited as Alberta law. Patterns are matched case-insensitively
# by the validator; the message explains what to cite instead.
SUPERSEDED_PATTERNS = [
    (r"\b(?:NBC|NFC)\s*\(?\s*AE\s*\)?\s*[-–]?\s*(?:2019|2014|2006)\b", "superseded Alberta Edition"),
    (r"\bAlberta\s+(?:Building|Fire)\s+Code\s*[-–]?\s*(?:2019|2014|2006)\b", "superseded Alberta Edition"),
    (r"\bABC\s*[-–]?\s*(?:2019|2014|2006)\b", "superseded Alberta Edition"),
    (r"\b(?:1st|first)\s+printing\b", "superseded 1st printing of the 2023 AE"),
    (r"\b(?:NBC|NFC)\s*\(?\s*AE\s*\)?\s*[-–]?\s*2023\s+p1\b", "superseded 1st printing of the 2023 AE"),
    (r"superseded-1st-printing", "superseded 1st printing of the 2023 AE"),
    (r"\b(?:NBC|NFC)\s*(?:of\s+Canada\s*)?[-–]?\s*(?:2015|2010|2005)\b", "superseded national edition"),
]
# National editions that may appear only as labelled explanatory context.
NATIONAL_CONTEXT_RE = r"\b(?:NBC|NFC|National\s+(?:Building|Fire)\s+Code(?:\s+of\s+Canada)?)\s*[-–]?\s*(?:2020|2025)\b"


@dataclass
class Page:
    page: int
    raw: str                      # text exactly as in reference/text
    lines: list[str] = field(default_factory=list)   # cleaned (no copyright/header/footer)


_HEADER_RE = re.compile(
    r"^(?:(?:A-|D-)?(?:T ?able )?[\dA-Z][\w.()\- ]{0,40}\s)?Division [ABC](?:\s[\w.()\- ]{0,40})?$|^Division [ABC]$"
    r"|^(?:Appendix [A-D]|Index|Fire and Sound Resistance T ?ables|Span T ?ables)(?: Division [ABC])?$"
)


@lru_cache(maxsize=None)
def load_pages(key: str) -> tuple[Page, ...]:
    doc = DOCS[key]
    out = []
    with doc.jsonl.open(encoding="utf8") as f:
        for line in f:
            rec = json.loads(line)
            out.append(Page(rec["page"], rec["text"], clean_lines(rec["text"], doc)))
    return tuple(out)


def clean_lines(text: str, doc: CodeDoc) -> list[str]:
    lines = [ln.rstrip() for ln in text.split("\n")]
    lines = [ln for ln in lines if ln.strip() and not ln.lstrip().startswith("©")]
    if doc.kind == "code":
        if lines and _HEADER_RE.match(lines[0].strip()):
            lines = lines[1:]
        if lines and doc.footer_marker and doc.footer_marker in lines[-1]:
            lines = lines[:-1]
    else:
        lines = [ln for ln in lines if not re.fullmatch(r"\s*Intent Statements: \w+ 20\d\d\s*", ln)]
        if lines and re.fullmatch(r"\s*\d{1,4}\s*", lines[-1]):
            lines = lines[:-1]
    return [ln.strip() for ln in lines]


def volume_of(key: str, page: int) -> int | None:
    if key == "NBC-AE":
        return 1 if page < 816 else 2
    return None
