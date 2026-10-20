"""Parse the "Objectives and Functional Statements Attributed to the Acceptable Solutions" tables.

Plain text extraction interleaves the two table columns' cells unpredictably, so this module reads text
fragments with their PDF coordinates (pypdf visitor). In the PDF the row label "(n)" is top-aligned with the
first line of its cell, so every content line belongs to the most recent label at or above it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pypdf

from .sources import DOCS, load_pages

PAIR_RE = re.compile(r"\[\s*(F\d+(?:\s*,\s*F\d+)*)\s*-\s*(O[SHAPE]\d*(?:\.\d+)?(?:\s*,\s*O[SHAPE]\d*(?:\.\d+)?)*)\s*\]")
_ART = re.compile(r"^(\d+\.\d+\.\d+\.\d+\.)\s*(.*)$")
_SENT = re.compile(r"^\((\d+)\)\s*(.*)$")
_CLAUSE = re.compile(r"^((?:\([a-z]{1,2}\))(?:\((?:i|ii|iii|iv|v|vi|vii|viii|ix|x)\))?(?:(?:\s*,\s*and\s+|\s*,\s*|\s+and\s+|\s+to\s+|\s+or\s+)(?:\([a-z]{1,2}\))(?:\((?:i|ii|iii|iv|v|vi|vii|viii|ix|x)\))?)*)\s*(.*)$")


@dataclass
class Bracket:
    fs: list[str]
    objectives: list[str]
    raw: str

    @property
    def pairs(self):
        return [(f, o) for f in self.fs for o in self.objectives]


@dataclass
class Row:
    table: str
    article: str
    article_title: str
    sentence: int | None
    clauses: list[str]           # [] = whole sentence; ["a"], ["a","b"], ["b(i)"]
    brackets: list[Bracket]
    note: str
    page: int
    raw: str = ""

    @property
    def provision(self) -> str:
        s = self.article + (f"({self.sentence})" if self.sentence is not None else "")
        if len(self.clauses) == 1:
            c = self.clauses[0]
            s += "".join(f"({x})" for x in re.findall(r"[a-z]+", c))
        return s


def _expand_clauses(label: str) -> list[str]:
    """'(b),(d)' -> ['b','d'];  '(a) to (c)' -> ['a','b','c'];  '(b)(i)' -> ['b(i)']"""
    found = re.findall(r"\(([a-z]{1,2})\)(?:\((i|ii|iii|iv|v|vi|vii|viii|ix|x)\))?", label)
    out = [c + (f"({sub})" if sub else "") for c, sub in found]
    if " to " in label and len(found) == 2 and not found[0][1] and len(found[0][0]) == len(found[1][0]) == 1:
        out = [chr(x) for x in range(ord(found[0][0]), ord(found[1][0]) + 1)]
    return out


def parse_bracket(raw: str) -> Bracket | None:
    m = PAIR_RE.fullmatch(raw.strip())
    if not m:
        return None
    fs = [x.strip() for x in m.group(1).split(",")]
    obs = [x.strip() for x in m.group(2).split(",")]
    return Bracket(fs, obs, "[" + ",".join(fs) + "-" + ",".join(obs) + "]")


def find_tables(key: str) -> list[tuple[str, int, int]]:
    """[(table_id, first_page, last_page)] for each attribution table, located from page text."""
    pages = load_pages(key)
    out, open_ = [], None
    for p in pages:
        flat = " ".join(p.lines)
        m = re.search(r"Table (\d+\.\d+\.1\.1\.)\s+Objectives and Functional Statements Attributed to the", flat)
        if m and open_ is None:
            open_ = (m.group(1), p.page)
        if open_ and re.search(r"Notes to Table " + re.escape(open_[0]), flat):
            out.append((open_[0], open_[1], p.page))
            open_ = None
    return out


@dataclass
class _Line:
    y: float
    x: float
    text: str


def _page_columns(reader: pypdf.PdfReader, pageno: int) -> list[list[_Line]]:
    frags = []

    def visit(text, cm, tm, fd, fs):
        if not text.strip():
            return
        x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
        y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
        frags.append((x, y, text.replace("\n", " ")))

    reader.pages[pageno - 1].extract_text(visitor_text=visit)
    width = float(reader.pages[pageno - 1].mediabox.width)
    cols: list[list[_Line]] = [[], []]
    for col in (0, 1):
        fr = [f for f in frags if 30 < f[1] < 735 and ((f[0] < width / 2) == (col == 0))]
        fr.sort(key=lambda f: (-f[1], f[0]))
        lines: list[_Line] = []
        for x, y, t in fr:
            if lines and abs(lines[-1].y - y) < 3:
                ln = lines[-1]
                if x < ln.x:
                    ln.text, ln.x = t + " " + ln.text, x
                else:
                    ln.text += ("" if t.startswith(" ") or ln.text.endswith(" ") else " ") + t
            else:
                lines.append(_Line(y, x, t))
        for ln in lines:
            ln.text = re.sub(r"\s+", " ", ln.text).strip()
        cols[col] = lines
    return cols


def parse_table(key: str, table: str, first: int, last: int, reader: pypdf.PdfReader) -> tuple[list[Row], list[str]]:
    rows: list[Row] = []
    problems: list[str] = []
    article = title = None
    sentence: int | None = None
    done = False
    for pg in range(first, last + 1):
        for lines in _page_columns(reader, pg):
            started = False
            label_x = None
            pending = ""
            for ln in lines:
                t = ln.text
                if not started:
                    if t.startswith("Provision Functional Statements"):
                        started, label_x = True, ln.x
                    continue
                if t.startswith("Notes to Table"):
                    done = True
                    break
                if t.startswith("Table ") and "(Continued)" in t:
                    continue
                if pending:  # bracket wrapped onto this line
                    t = pending + " " + t
                    pending = ""
                if t.count("[") > t.count("]"):
                    pending = t
                    continue
                in_label = ln.x < label_x + 25
                clauses: list[str] = []
                if in_label:
                    if (m := _ART.match(t)) and not t.startswith("("):
                        article, title, sentence = m.group(1), m.group(2), None
                        continue
                    if (m := _SENT.match(t)):
                        sentence, t = int(m.group(1)), m.group(2)
                        if not t:
                            continue
                    elif not t.startswith("["):
                        if rows and rows[-1].article == article and rows[-1].sentence == sentence and not t[0].isupper():
                            rows[-1].note += " " + t
                        else:
                            title = f"{title} {t}"
                        continue
                if (m := _CLAUSE.match(t)) and not t.startswith("[") :
                    clauses = _expand_clauses(m.group(1))
                    t = m.group(2)
                if t.startswith("["):
                    brs, pos = [], 0
                    for bm in re.finditer(r"\[[^\]]*\]", t):
                        if t[pos:bm.start()].strip():
                            break
                        b = parse_bracket(bm.group(0))
                        if b is None:
                            problems.append(f"p.{pg} unparsed bracket {bm.group(0)!r} in {article}")
                            break
                        brs.append(b)
                        pos = bm.end()
                    note = t[pos:].strip()
                    if article is None:
                        problems.append(f"p.{pg} row before any article: {t!r}")
                        continue
                    rows.append(Row(table, article, title or "", sentence, clauses, brs, note, pg, ln.text))
                elif rows:
                    rows[-1].note = (rows[-1].note + " " + t).strip()   # application-note continuation
                else:
                    problems.append(f"p.{pg} stray text {t!r}")
            if done:
                break
        if done:
            break
    for r in rows:
        r.note = re.sub(r"\s+", " ", r.note).strip()
        # Editorial square brackets inside quoted application text are valid;
        # warn only when an attribution bracket was left in the note stream.
        if re.search(r"\[\s*F\d+", r.note):
            problems.append(f"p.{r.page} bracket inside application note of {r.provision}: {r.note[:80]!r}")
    return rows, problems


def parse_all(key: str = "NBC-AE") -> tuple[list[Row], list[str], list[tuple[str, int, int]]]:
    reader = pypdf.PdfReader(str(DOCS[key].pdf))
    rows, problems = [], []
    tables = find_tables(key)
    for table, first, last in tables:
        r, p = parse_table(key, table, first, last, reader)
        rows += r
        problems += p
    return rows, problems, tables
