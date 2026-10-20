"""Objectives (Div A 2.2.1.1.(1)) and functional statements (Div A 3.2.1.1.(1)) as a code -> definition table."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .ids import parse


@dataclass
class Definition:
    code: str           # OS, OS1, OS1.1, F10
    kind: str           # objective | functional_statement
    title: str          # "Fire Safety" for OS1; the statement itself for sub-objectives and F-codes
    text: str           # full definition text
    parent: str | None
    page: int
    lines: list[str] = field(default_factory=list)


_TOP = re.compile(r"^(O[SHAPE])\s+([A-Z].*)$")
_OBJ = re.compile(r"^(O[SHAPE]\d+)\s+([A-Z].*)$")
_SUB = re.compile(r"^(O[SHAPE]\d+)\s?\.\s?(\d+)\s*[–-]\s*(.*)$")
_FS = re.compile(r"^F(\d)\s?(\d{1,2})\s+(To\b.*)$|^F(\d{2,3})\s+(To\b.*)$")


def parse_definitions(nodes, repair) -> list[Definition]:
    out: list[Definition] = []
    cur: Definition | None = None
    obj = nodes[("A", parse("2.2.1.1.(1)"))]
    for page, line in obj.lines[1:]:
        if (m := _SUB.match(line)):
            code = f"{m.group(1)}.{m.group(2)}"
            cur = Definition(code, "objective", "", "", m.group(1), page, [m.group(3)])
        elif (m := _OBJ.match(line)):
            cur = Definition(m.group(1), "objective", m.group(2), "", m.group(1)[:2], page, [])
        elif (m := _TOP.match(line)):
            cur = Definition(m.group(1), "objective", m.group(2), "", None, page, [])
        elif cur is not None:
            cur.lines.append(line)
            continue
        else:
            continue
        out.append(cur)
    cur = None
    fs = nodes[("A", parse("3.2.1.1.(1)"))]
    for page, line in fs.lines[1:]:
        if (m := _FS.match(line)):
            code = "F" + (m.group(1) + m.group(2) if m.group(1) else m.group(4))
            cur = Definition(code, "functional_statement", "", "", None, page, [m.group(3) or m.group(5)])
            out.append(cur)
        elif cur is not None:
            cur.lines.append(line)
    for d in out:
        d.text = repair(" ".join(d.lines)).strip()
        if not d.title:
            d.title = d.text
    return out
