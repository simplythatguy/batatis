"""Parse the NRC "Supplement to the NBC/NFC 2020: Intent Statements".

Entry shape (one per provision; a provision may have several objective blocks):
  Provision: 2.2.5.1.(3)
  Objective / OS3 / Attributions / [F30-OS3.1] [F10-OS3.7] / Intent(s) / Intent 1. ... Intent 2. ...
  Objective / OS1 / Attributions / [F10-OS1.5] / Intent(s) / Intent 1. ...
Provisions with no attribution have only "Intent(s)".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .attributions import PAIR_RE, parse_bracket
from .sources import load_pages


@dataclass
class Block:
    objective: str | None
    attribution_lines: list[str] = field(default_factory=list)  # raw "[..] note" lines
    intent_lines: list[str] = field(default_factory=list)
    page: int = 0

    @property
    def brackets(self):
        out = []
        for ln in self.attribution_lines:
            for m in re.finditer(r"\[[^\]]*\]", ln):
                b = parse_bracket(m.group(0))
                if b:
                    out.append(b)
        return out

    @property
    def attribution_notes(self) -> list[str]:
        notes = []
        for ln in self.attribution_lines:
            rest = re.sub(r"\[[^\]]*\]", "", ln).strip()
            if rest:
                notes.append(rest)
        return notes

    def intents(self, repair) -> list[str]:
        text = "\n".join(self.intent_lines)
        parts = re.split(r"(?m)^Intent \d+\.\s*", text)
        out = [repair(" ".join(p.split())).strip() for p in parts if p.strip()]
        return out


@dataclass
class Entry:
    provision: str
    page: int
    page_end: int
    blocks: list[Block] = field(default_factory=list)


def parse_intents(key: str) -> list[Entry]:
    entries: list[Entry] = []
    cur: Entry | None = None
    block: Block | None = None
    mode = None
    pending_objective = False
    for p in load_pages(key):
        for line in p.lines:
            if (m := re.match(r"^Provision:\s*(.+)$", line)):
                cur = Entry(m.group(1).strip(), p.page, p.page)
                entries.append(cur)
                block, mode, pending_objective = None, None, False
                continue
            if cur is None:
                continue
            cur.page_end = p.page
            if line == "Objective":
                pending_objective = True
                continue
            if pending_objective:
                block = Block(line.strip(), page=p.page)
                cur.blocks.append(block)
                pending_objective, mode = False, None
                continue
            if line == "Attributions":
                mode = "attr"
                continue
            if line == "Intent(s)":
                if block is None or block.intent_lines or mode == "intent":
                    if block is None or mode != "attr":
                        block = Block(None, page=p.page)
                        cur.blocks.append(block)
                mode = "intent"
                continue
            if mode == "attr" and block is not None:
                if line.startswith("[") or not block.attribution_lines:
                    block.attribution_lines.append(line)
                else:
                    block.attribution_lines[-1] += " " + line
            elif mode == "intent" and block is not None:
                block.intent_lines.append(line)
    return entries
