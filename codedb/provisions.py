"""Parse the code body into a provision tree (section > subsection > article > sentence > clause > subclause)
and the "Notes to Part N" into notes.

The parser is a hierarchy-checked state machine over cleaned page lines: a line is only accepted as a
heading or label when it fits the current position in the tree (right parent, increasing number). Anything
else is text of the current node. This is what keeps cross-references that happen to start a wrapped line
("9.5.1.2. and Note ...") from creating phantom provisions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import ids, textnorm
from .ids import Pid
from .sources import load_pages

# ---------------------------------------------------------------- document segments


@dataclass
class Segment:
    division: str
    part: int | None
    kind: str          # body | notes | appendix | index | front
    first: int
    last: int


_DIV = re.compile(r"^Division ([ABC])$")


def segments(key: str) -> list[Segment]:
    pages = load_pages(key)
    segs: list[Segment] = []
    cur = Segment("", None, "front", pages[0].page, pages[0].page)
    for p in pages:
        raw = [ln.strip() for ln in p.raw.split("\n") if ln.strip() and not ln.lstrip().startswith("©")]
        new = None
        if raw and raw[0] == "Index":
            new = Segment("", None, "index", p.page, p.page)
        elif len(raw) > 1 and (m := _DIV.match(raw[0])):
            d = m.group(1)
            if (mp := re.fullmatch(r"Part (\d+)", raw[1])):
                part = int(mp.group(1))
                if not (cur.kind == "body" and cur.division == d and cur.part == part):
                    new = Segment(d, part, "body", p.page, p.page)
            elif (mn := re.match(r"Notes to Part (\d+)$", raw[1])):
                part = int(mn.group(1))
                if not (cur.kind == "notes" and cur.division == d and cur.part == part):
                    new = Segment(d, part, "notes", p.page, p.page)
            elif re.match(r"Notes to Part \d+ \.{3}", raw[1]):
                pass  # table-of-contents page inside a part
            elif re.fullmatch(r"Appendix [A-Z]", raw[1]):
                new = Segment(d, None, "appendix", p.page, p.page)
            elif len(raw) <= 6:
                new = Segment(d, None, "front", p.page, p.page)
        if new is not None:
            segs.append(cur)
            cur = new
        cur.last = p.page
    segs.append(cur)
    return [s for s in segs if s.kind != "front" or s.first != s.last or s.division]


# ---------------------------------------------------------------- provision tree


@dataclass
class Node:
    division: str
    pid: Pid
    title: str = ""
    page: int = 0
    page_end: int = 0
    lines: list[tuple[int, str]] = field(default_factory=list)   # own text lines (incl. children for sentences)
    source: str | None = None

    def add(self, page: int, text: str):
        self.lines.append((page, text))
        self.page_end = max(self.page_end, page)

    @property
    def text(self) -> str:
        raw = "\n".join(t for _, t in self.lines)
        return textnorm.source_text(raw, self.source, self.page, self.page_end)


_SECTION = re.compile(r"^Section (\d+)\.(\d+)\.\s+([A-Z].*)$")
_SUBSECTION = re.compile(r"^(\d+)\.(\d+)\.(\d+)\.\s+([A-Z(].*)$")
_ARTICLE = re.compile(r"^(\d+)\.(\d+)\.(\d+)\.(\d+)\.\s+([A-Z(].*)$")
_SENT = re.compile(r"^(\d{1,2})\)\s+(.*)$")
_LABEL = re.compile(r"^([a-z]{1,4})\)\s+(.*)$")
_LEADER = re.compile(r"\.{5,}|\. \. \. \.")
_TABLE_CAPTION = re.compile(r"^Table (\d+(?:\.\d+)+\.(?:-[A-Z0-9]+)?)(?: \(Continued\))?$")
_FIGURE_CAPTION = re.compile(r"^Figure \d+(?:\.\d+)+\.(?:-[A-Z0-9]+)?(?: \(Continued\))?$")


def prenormalize(stream: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Undo extraction splits that hide labels: "b ) text" -> "b) text"; "3.6.4." + "4. Title" -> one line."""
    out: list[tuple[int, str]] = []
    for page, line in stream:
        line = re.sub(r"^([a-z]{1,4}|\d{1,2}) \)\s", r"\1) ", line)
        if out and re.fullmatch(r"\d+\.\d+\.\d+\.", out[-1][1]) and re.match(r"^\d+\.\s+[A-Z]", line):
            out[-1] = (out[-1][0], out[-1][1] + line)
            continue
        out.append((page, line))
    return out


class TreeParser:
    """Feeds cleaned lines of one body segment and builds nodes."""

    def __init__(self, division: str, part: int, skip_tables: set[str]):
        self.division, self.part = division, part
        self.nodes: dict[Pid, Node] = {}
        self.section = self.subsection = self.article = None   # Pid
        self.sentence = self.clause = self.subclause = None     # Node
        self.skip_tables = skip_tables
        self.skipping = False
        self.in_table = False
        self.anomalies: list[str] = []
        self.tables: dict[str, int] = {}

    # -- helpers
    def _new(self, pid: Pid, page: int, title: str = "") -> Node:
        n = Node(self.division, pid, title, page, page)
        self.nodes[pid] = n
        return n

    def _close_from(self, level: str):
        order = ["section", "subsection", "article", "sentence", "clause", "subclause"]
        for name in order[order.index(level):]:
            setattr(self, name, None)

    def feed(self, stream: list[tuple[int, str]]):
        stream = prenormalize(stream)
        i = 0
        while i < len(stream):
            page, line = stream[i]
            i += self._line(stream, i, page, line)

    def _lookahead(self, stream, i, rx_ok, n=8, stop=None):
        for _, ln in stream[i + 1:i + 1 + n]:
            if rx_ok(ln):
                return True
            if stop and stop(ln):
                return False
        return False

    def _line(self, stream, i, page, line) -> int:
        if _LEADER.search(line):
            return 1
        if _FIGURE_CAPTION.match(line):
            self.in_table = True
            return 1
        if (m := _TABLE_CAPTION.match(line)):
            tid = m.group(1)
            self.tables.setdefault(tid, page)
            if tid in self.skip_tables:
                self.skipping = True
                return 1
            self.in_table = True
            return 1
        if self.skipping:
            # the attribution table runs until its own notes; the next structural heading ends it
            if not (_SECTION.match(line) or line.startswith("Notes to Part")):
                return 1
            self.skipping = False
        if self.in_table:
            # Cell values and table footnotes are not body sentences. Resume only
            # at a body heading or the next expected body label.
            sent = _SENT.match(line)
            label = _LABEL.match(line)
            next_sent = sent and int(sent.group(1)) == (self.sentence.pid.sentence + 1 if self.sentence else 1)
            next_clause = label and self.sentence and label.group(1) == ids.next_clause(
                self.clause.pid.clause if self.clause else None)
            if not (_SECTION.match(line) or _SUBSECTION.match(line) or _ARTICLE.match(line) or next_sent or next_clause):
                return 1
            self.in_table = False

        m = _SECTION.match(line)
        if m and int(m.group(1)) == self.part:
            pid = Pid((int(m.group(1)), int(m.group(2))))
            prefix = f"{pid.nums[0]}.{pid.nums[1]}."
            if (self.section is None or pid.nums > self.section.nums) and self._lookahead(
                    stream, i, lambda ln: ln.startswith(prefix) and bool(_SUBSECTION.match(ln) or _ARTICLE.match(ln)), n=6):
                self._close_from("section")
                self.section = pid
                self._new(pid, page, m.group(3).strip())
                return 1
        m = _SUBSECTION.match(line)
        if m and self.section and (int(m.group(1)), int(m.group(2))) == self.section.nums:
            pid = Pid(tuple(int(x) for x in m.groups()[:3]))
            prefix = ".".join(m.groups()[:3]) + "."
            if (self.subsection is None or pid.nums > self.subsection.nums) and self._lookahead(
                    stream, i, lambda ln: ln.startswith(prefix) and bool(_ARTICLE.match(ln)), n=6):
                self._close_from("subsection")
                self.subsection = pid
                self._new(pid, page, m.group(4).strip())
                return 1
        m = _ARTICLE.match(line)
        if m and self.subsection and tuple(int(x) for x in m.groups()[:3]) == self.subsection.nums:
            pid = Pid(tuple(int(x) for x in m.groups()[:4]))
            reserved = m.group(5).strip() == "Reserved"
            if (self.article is None or pid.nums > self.article.nums) and (reserved or self._lookahead(
                    stream, i, lambda ln: bool(re.match(r"^1\)\s", ln)), n=8,
                    stop=lambda ln: bool(_ARTICLE.match(ln) or _SUBSECTION.match(ln)))):
                self._close_from("article")
                self.article = pid
                node = self._new(pid, page, m.group(5).strip())
                # wrapped title: following short lines before "1)" that are not "(See ...)" notes
                k = 1
                while not reserved and i + k < len(stream):
                    nxt = stream[i + k][1]
                    if _SENT.match(nxt) or nxt.startswith("(") or _LEADER.search(nxt):
                        break
                    node.title += " " + nxt
                    k += 1
                return k
        if self.article is None:
            return 1  # text outside any article (part/section intro) is not a provision
        art = self.nodes[self.article]

        m = _SENT.match(line)
        if m:
            n = int(m.group(1))
            expected = 1 if self.sentence is None else self.sentence.pid.sentence + 1
            if n == expected:
                self._close_from("sentence")
                self.sentence = self._new(Pid(self.article.nums, n), page)
                self.sentence.add(page, line)
                return 1
            if self.sentence is not None and expected < n <= expected + 2:
                self.anomalies.append(f"{self.article}: sentence {n} after {expected - 1} (p.{page})")
                self._close_from("sentence")
                self.sentence = self._new(Pid(self.article.nums, n), page)
                self.sentence.add(page, line)
                return 1
        if self.sentence is None:
            art.add(page, line)   # article preamble, e.g. "(See Note A-...)"
            return 1

        m = _LABEL.match(line)
        if m:
            lab = m.group(1)
            as_clause = lab == ids.next_clause(self.clause.pid.clause if self.clause else None)
            as_sub = self.clause is not None and lab == ids.next_roman(
                self.subclause.pid.subclause if self.subclause else None)
            if as_clause and as_sub:
                # "i)" after clause h): look ahead for "ii)" (subclauses) vs "j)" (clauses)
                for _, ln in stream[i + 1:i + 30]:
                    if ln.startswith("ii) "):
                        as_clause = False
                        break
                    if ln.startswith("j) ") or _SENT.match(ln):
                        as_sub = False
                        break
                else:
                    as_sub = False
            if as_sub:
                c = self.clause.pid
                self.subclause = self._new(Pid(c.nums, c.sentence, c.clause, lab), page)
                for nd in (self.sentence, self.clause, self.subclause):
                    nd.add(page, line)
                return 1
            if as_clause:
                self.subclause = None
                self.clause = self._new(Pid(self.article.nums, self.sentence.pid.sentence, lab), page)
                self.sentence.add(page, line)
                self.clause.add(page, line)
                return 1
        # plain text: belongs to the open sentence and to the innermost open clause/subclause. A line that
        # starts like "(See Note ...)" right after the clause list closes the clause list.
        self.sentence.add(page, line)
        if self.clause is not None and not line.startswith("(See"):
            self.clause.add(page, line)
            if self.subclause is not None:
                self.subclause.add(page, line)
        return 1


# ---------------------------------------------------------------- notes

_NOTE = re.compile(
    r"^A-(?P<id>(?:T ?able |Figure )?\d+(?:\.\d+)*\.?(?:-[A-Z0-9]+)?(?:\(\d+\))*(?:\([a-z]{1,2}\))*(?:\((?:i|ii|iii|iv|v|vi)\))?"
    r"(?:(?:,| and| to|, and) \(\d+\)(?:\([a-z]\))?)*)\s+(?P<title>[A-Z].*)$"
)


@dataclass
class Note:
    division: str
    note_id: str          # "A-9.9.10.1.(1)"
    title: str
    page: int
    page_end: int
    lines: list[str] = field(default_factory=list)
    source: str | None = None

    @property
    def text(self):
        return textnorm.source_text("\n".join(self.lines), self.source, self.page, self.page_end)


def note_targets(note_id: str) -> list[str]:
    """'A-3.8.3.9.(1) and (2)' -> ['3.8.3.9.(1)', '3.8.3.9.(2)'];  'A-9.11.' -> ['9.11.']"""
    body = note_id[2:].replace("T able", "Table")
    if body.startswith(("Table", "Figure")):
        return []
    m = re.match(r"(\d+(?:\.\d+)*\.?)((?:\(\d+\))?(?:\([a-z]{1,2}\))*(?:\([ivx]+\))?)(.*)$", body)
    if not m:
        return []
    nums = m.group(1) if m.group(1).endswith(".") else m.group(1) + "."
    first = nums + m.group(2)
    out = [first]
    for extra in re.findall(r"\((\d+)\)(\([a-z]\))?", m.group(3)):
        out.append(f"{nums}({extra[0]}){extra[1]}")
    return out


def parse_notes(division: str, part: int, stream: list[tuple[int, str]]) -> list[Note]:
    notes: list[Note] = []
    cur: Note | None = None
    for page, line in stream:
        m = _NOTE.match(line)
        if m:
            nid = "A-" + m.group("id").replace("T able", "Table")
            tg = note_targets(nid)
            okpart = (not tg) or tg[0].split(".")[0] == str(part)
            if okpart:
                title = m.group("title")
                # "A-9.9.10.1.(2) Bedroom Window Opening Areas and Dimensions. Although ..." -> title, text
                tm = re.match(r"(.{3,160}?[a-z0-9)”'])\.\s+(.*)$", title)
                if tm:
                    title, rest = tm.group(1), [tm.group(2)]
                else:
                    title, rest = title.rstrip("."), []
                cur = Note(division, nid, title, page, page, rest)
                notes.append(cur)
                continue
        if cur is not None:
            cur.lines.append(line)
            cur.page_end = page
    return notes


# ---------------------------------------------------------------- driver


@dataclass
class ParsedCode:
    nodes: dict[tuple[str, Pid], Node]
    notes: list[Note]
    tables: dict[tuple[str, str], int]
    segments: list[Segment]
    anomalies: list[str]


def parse_code(key: str, skip_tables: set[str]) -> ParsedCode:
    pages = {p.page: p for p in load_pages(key)}
    nodes: dict[tuple[str, Pid], Node] = {}
    notes: list[Note] = []
    tables: dict[tuple[str, str], int] = {}
    anomalies: list[str] = []
    segs = segments(key)
    for s in segs:
        stream = [(pg, ln) for pg in range(s.first, s.last + 1) for ln in pages[pg].lines]
        if s.kind == "body":
            tp = TreeParser(s.division, s.part, skip_tables)
            tp.feed(stream)
            for pid, n in tp.nodes.items():
                n.source = key
                nodes[(s.division, pid)] = n
            for t, pg in tp.tables.items():
                tables.setdefault((s.division, t), pg)
            anomalies += [f"Div {s.division} {a}" for a in tp.anomalies]
        elif s.kind == "notes":
            notes += parse_notes(s.division, s.part, stream)
    for note in notes:
        note.source = key
    return ParsedCode(nodes, notes, tables, segs, anomalies)
