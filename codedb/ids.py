"""Provision identifiers: one parsed, canonical shape used everywhere.

Canonical text form follows the code's own convention:
  section "9.9."  subsection "9.9.10."  article "9.9.10.1."
  sentence "9.9.10.1.(1)"  clause "9.9.10.1.(1)(a)"  subclause "9.9.10.1.(1)(a)(i)"
"""
from __future__ import annotations

import re
from dataclasses import dataclass

LEVELS = ("part", "section", "subsection", "article", "sentence", "clause", "subclause")
NUM_LEVEL = {1: "part", 2: "section", 3: "subsection", 4: "article"}
ROMAN = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii", "xiii", "xiv", "xv"]

# Accepts the canonical form and the common sloppy variants (missing final dot before "(",
# spaces between groups). Normalisation happens in parse().
PID_RE = re.compile(
    r"(?P<nums>\d{1,2}(?:\.\d{1,3}){0,3})\.?\s?"
    r"(?P<sent>\(\d{1,2}\))?(?P<cl>\([a-z]{1,2}\))?(?P<sub>\((?:i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii)\))?"
)


@dataclass(frozen=True, order=True)
class Pid:
    nums: tuple[int, ...]
    sentence: int | None = None
    clause: str | None = None
    subclause: str | None = None

    @property
    def level(self) -> str:
        if self.subclause:
            return "subclause"
        if self.clause:
            return "clause"
        if self.sentence is not None:
            return "sentence"
        return NUM_LEVEL[len(self.nums)]

    @property
    def part(self) -> int:
        return self.nums[0]

    @property
    def article(self) -> "Pid | None":
        return Pid(self.nums) if len(self.nums) == 4 else None

    def parent(self) -> "Pid | None":
        if self.subclause:
            return Pid(self.nums, self.sentence, self.clause)
        if self.clause:
            return Pid(self.nums, self.sentence)
        if self.sentence is not None:
            return Pid(self.nums)
        if len(self.nums) > 1:
            return Pid(self.nums[:-1])
        return None

    def ancestors(self):
        p = self.parent()
        while p is not None:
            yield p
            p = p.parent()

    def sentence_id(self) -> "Pid | None":
        return Pid(self.nums, self.sentence) if self.sentence is not None else None

    def __str__(self) -> str:
        s = ".".join(str(n) for n in self.nums) + "."
        if self.sentence is not None:
            s += f"({self.sentence})"
        if self.clause:
            s += f"({self.clause})"
        if self.subclause:
            s += f"({self.subclause})"
        return s

    def sort_key(self):
        return (self.nums, self.sentence or 0, clause_index(self.clause), roman_index(self.subclause))


def clause_index(c: str | None) -> int:
    if not c:
        return 0
    if len(c) == 1:
        return ord(c) - 96
    return 26 + ord(c[-1]) - 96  # (aa), (bb) style


def roman_index(r: str | None) -> int:
    return ROMAN.index(r) + 1 if r in ROMAN else 0


def next_clause(c: str | None) -> str:
    return "a" if c is None else chr(ord(c) + 1)


def next_roman(r: str | None) -> str | None:
    i = roman_index(r)
    return ROMAN[i] if i < len(ROMAN) else None


def parse(s: str) -> Pid:
    """Parse a provision id (tolerant of a missing dot before '(' and stray spaces)."""
    s = re.sub(r"\s+", "", s.strip())
    m = PID_RE.fullmatch(s)
    if not m:
        raise ValueError(f"not a provision id: {s!r}")
    nums = tuple(int(x) for x in m.group("nums").split("."))
    sent = int(m.group("sent")[1:-1]) if m.group("sent") else None
    cl = m.group("cl")[1:-1] if m.group("cl") else None
    sub = m.group("sub")[1:-1] if m.group("sub") else None
    if any(n < 1 for n in nums) or (sent is not None and (len(nums) != 4 or sent < 1)):
        raise ValueError(f"invalid provision hierarchy: {s!r}")
    if cl and sent is None:
        raise ValueError(f"clause without sentence: {s!r}")
    return Pid(nums, sent, cl, sub)


def canon(s: str) -> str:
    return str(parse(s))
