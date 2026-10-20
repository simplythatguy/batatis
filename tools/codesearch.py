r"""Search the extracted reference texts.

  .venv/bin/python -I tools/codesearch.py find "3\.4\.2\.1\." [--doc NBC-AE] [--max 20]
  .venv/bin/python -I tools/codesearch.py page NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2 830
  .venv/bin/python -I tools/codesearch.py docs

`find` takes a Python regex (case-insensitive) and prints doc, PDF page, and a snippet.
`--doc` filters by substring of the document name. Page numbers are 1-based PDF pages:
cite them as "PDF p.N" alongside the article number."""
import argparse, json, pathlib, re, sys

TEXT = pathlib.Path(__file__).resolve().parent.parent / "reference" / "text"

def pages(doc_filter=None):
    for f in sorted(TEXT.glob("*.jsonl")):
        if doc_filter and doc_filter.lower() not in f.stem.lower():
            continue
        for line in f.open(encoding="utf8"):
            yield json.loads(line)

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    fp = sub.add_parser("find"); fp.add_argument("pattern"); fp.add_argument("--doc"); fp.add_argument("--max", type=int, default=20); fp.add_argument("--context", type=int, default=160)
    pp = sub.add_parser("page"); pp.add_argument("doc"); pp.add_argument("page", type=int)
    sub.add_parser("docs")
    a = ap.parse_args()
    if a.cmd == "docs":
        for f in sorted(TEXT.glob("*.jsonl")):
            print(f.stem)
        return
    if a.cmd == "page":
        for p in pages(a.doc):
            if p["page"] == a.page:
                print(f"== {p['doc']} PDF p.{p['page']}\n{p['text']}")
                return
        sys.exit("page not found")
    rx = re.compile(a.pattern, re.I)
    n = 0
    for p in pages(a.doc):
        flat = " ".join(p["text"].split())
        for m in rx.finditer(flat):
            s = max(0, m.start() - a.context); e = min(len(flat), m.end() + a.context)
            print(f"[{p['doc']} PDF p.{p['page']}] ...{flat[s:e]}...\n")
            n += 1
            if n >= a.max:
                return
            break
    if n == 0:
        print("no matches")

if __name__ == "__main__":
    main()
