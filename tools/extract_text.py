"""Extract per-page text from every PDF under reference/ into reference/text/<name>.jsonl.
Each line: {"doc": name, "page": 1-based PDF page, "text": ...}. Idempotent: skips up-to-date outputs."""
import json, sys, pathlib
from pypdf import PdfReader

ROOT = pathlib.Path(__file__).resolve().parent.parent / "reference"
OUT = ROOT / "text"

def main():
    OUT.mkdir(exist_ok=True)
    for pdf in sorted(ROOT.rglob("*.pdf")):
        if any("superseded" in p for p in pdf.parts):
            continue
        out = OUT / (pdf.stem + ".jsonl")
        if out.exists() and out.stat().st_mtime > pdf.stat().st_mtime:
            continue
        reader = PdfReader(str(pdf))
        with out.open("w", encoding="utf8") as f:
            for i, page in enumerate(reader.pages, 1):
                f.write(json.dumps({"doc": pdf.stem, "page": i, "text": page.extract_text() or ""}) + "\n")
        print(f"{pdf.stem}: {len(reader.pages)} pages", file=sys.stderr)

if __name__ == "__main__":
    main()
