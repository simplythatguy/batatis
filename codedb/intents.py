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

from .attributions import parse_bracket
from .textnorm import SourceText, source_text
from .sources import load_pages

_BRACKET = re.compile(r"\[[^\]]*\]")


def parse_attribution_bracket(raw: str):
    """Parse one intent-supplement attribution bracket, tolerating PDF letter spacing.

    The supplement's justified lines are often letter-spaced on extraction, e.g.
    "[ F 1 0 ,F 1 2 ,F 0 5 ,F 0 6 - O S 3 . 7 ]" or "[F20, F80-OH 4]" or "[F6 3-OS2.3]".
    An attribution bracket contains only F/O codes, digits, dots, commas and one hyphen, so
    whitespace inside it carries no meaning: drop it all before matching. Non-attribution
    brackets (quoted Code words such as "[noncombustible]") still fail and return None.
    """
    return parse_bracket(re.sub(r"\s+", "", raw))


@dataclass
class Block:
    objective: str | None
    attribution_lines: list[str] = field(default_factory=list)  # raw "[..] note" lines
    intent_lines: list[str] = field(default_factory=list)
    page: int = 0
    source: str | None = None
    page_end: int = 0

    @property
    def brackets(self):
        found = (parse_attribution_bracket(m.group(0)) for ln in self.attribution_lines for m in _BRACKET.finditer(ln))
        return [b for b in found if b]

    @property
    def attribution_notes(self) -> list[str]:
        """Attribution text other than parsed brackets (clause scopes, "Applies to ..." notes).

        Bracketed words that are not attributions (e.g. "[noncombustible]" quoted from Code text) stay in the note.
        """
        notes = []

        def remove(text):
            return _BRACKET.sub(lambda m: "" if parse_attribution_bracket(m.group(0)) else m.group(0), text).strip()

        for ln in self.attribution_lines:
            rest = remove(ln)
            if rest:
                # Removing a bracket first would make the remaining text a
                # discontinuous span that cannot align with the PDF any more.
                value = source_text(ln, self.source, self.page, self.page_end)
                notes.append(SourceText(rest, remove(value.readable), value.unmatched, self.source, value.uncertain_lines)
                             if isinstance(value, SourceText) else rest)
        return notes

    def intents(self, repair) -> list[str]:
        raw = "\n".join(self.intent_lines)
        text = repair(source_text(raw, self.source, self.page, self.page_end))
        parts = re.split(r"(?m)^Intent \d+\.\s*", text)
        out = [" ".join(p.split()).strip() for p in parts if p.strip()]
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
                block.source, block.page_end = key, p.page
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
                        block.source = key
                        cur.blocks.append(block)
                mode = "intent"
                continue
            if mode == "attr" and block is not None:
                block.page_end = p.page
                if line.startswith("[") or not block.attribution_lines:
                    block.attribution_lines.append(line)
                else:
                    block.attribution_lines[-1] += " " + line
            elif mode == "intent" and block is not None:
                block.page_end = p.page
                block.intent_lines.append(line)
    return entries
