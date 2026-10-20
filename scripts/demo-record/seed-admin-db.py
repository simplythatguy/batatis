"""Write a code database the completeness check can read.

The rows are Division C provisions already cited in this repo, with the PDF pages
from those citations. Sentence text is left empty. This is used only when the
NBC source PDF is not in the checkout, so the engine can answer gaps.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from codedb import ids, store

# id, division, pdf page. Pages are the ones already cited in research/facts.
ROWS = (
    ("2.3.1.1.(2)(a)", "C", 739),
    ("2.3.1.1.(2)(b)", "C", 739),
    ("2.3.1.1.(3)", "C", 739),
    ("2.3.1.1.(4)", "C", 739),
    ("2.4.1.1.(1)", "C", 739),
    ("2.4.1.1.(2)", "C", 740),
    ("2.4.1.1.(3)", "C", 740),
    ("2.4.1.1.(4)", "C", 740),
    ("2.4.1.1.(5)", "C", 740),
    ("2.4.1.2.(1)", "C", 740),
    ("2.4.1.2.(2)", "C", 740),
    ("2.4.1.3.(1)", "C", 740),
    ("2.4.1.4.(1)", "C", 740),
)


def main(path: Path) -> None:
    if path.exists():
        path.unlink()
    con = store.create(path)
    con.execute(
        "INSERT INTO docs VALUES (?,?,?,?,?,?,?)",
        ("NBC-AE", "NBC(AE) 2023 p2", "code", 1, "", "", None),
    )
    for raw, division, page in ROWS:
        pid = ids.parse(raw)
        con.execute(
            "INSERT INTO provisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "NBC-AE",
                division,
                str(pid),
                pid.level,
                pid.part,
                None,
                None,
                str(pid.article) if pid.article else None,
                pid.sentence,
                pid.clause,
                pid.subclause,
                str(pid.parent()) if pid.parent() else None,
                "",
                "",
                "",
                "",
                "[]",
                page,
                page,
                1,
                ".".join(f"{part:04d}" for part in pid.sort_key()[0])
                + f".{pid.sort_key()[1]:04d}.{pid.sort_key()[2]:04d}",
            ),
        )
    store.finalize(con, path)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
