#!/usr/bin/env python3
"""Cache actual PDF readability by content hash while closed research lanes are curated."""
import hashlib
import json
import logging
from pathlib import Path
from pypdf import PdfReader
import pypdfium2 as pdfium

BASE = Path(__file__).resolve().parents[1]
logging.getLogger("pypdf").setLevel(logging.ERROR)


def main():
    completed = json.loads((BASE / "_research" / "preassembly_complete_workers.json").read_text())["completed_workers"]
    target = BASE / "_research" / "pdf_readability_cache.json"
    cache = json.loads(target.read_text()) if target.exists() else {}
    checked, errors = 0, []
    for worker in completed:
        manifest = BASE / "_research" / "workers" / worker / "candidates.json"
        data = json.loads(manifest.read_text())
        for case in data.get("cases", []):
            for attachment in case.get("attachments", []):
                path = Path(attachment["path"])
                if path.suffix.lower() != ".pdf" or not path.is_file():
                    continue
                raw = path.read_bytes()
                value = hashlib.sha256(raw).hexdigest()
                if value in cache:
                    continue
                try:
                    if not raw.startswith(b"%PDF-"):
                        raise ValueError("not PDF bytes")
                    reader = PdfReader(path, strict=False)
                    pages = len(reader.pages)
                    text = "\n".join(reader.pages[n].extract_text() or "" for n in range(min(3, pages)))
                    if not pages:
                        raise ValueError("zero pages")
                    cache[value] = {"pages": pages, "first_three_pages_text_characters": len(text),
                                    "checked_path": str(path.relative_to(BASE)), "result": "readable PDF; semantic/visual accuracy not established by this check"}
                    checked += 1
                except Exception as exc:
                    try:
                        document = pdfium.PdfDocument(path)
                        text = "\n".join(document[n].get_textpage().get_text_range() for n in range(min(3, len(document))))
                        if not len(document):
                            raise ValueError("zero pages in PDFium")
                        cache[value] = {"pages": len(document), "first_three_pages_text_characters": len(text),
                                        "checked_path": str(path.relative_to(BASE)), "parser": "PDFium",
                                        "parser_limit": str(exc), "result": "PDFium-readable original; pypdf limitation recorded"}
                        checked += 1
                    except Exception as fallback:
                        errors.append({"case_id": case.get("id"), "path": str(path), "error": str(exc), "pdfium_error": str(fallback)})
    target.write_text(json.dumps(cache, indent=2) + "\n")
    (BASE / "_research" / "candidate_pdf_errors.json").write_text(json.dumps(errors, indent=2) + "\n")
    print(json.dumps({"new_pdf_hashes_checked": checked, "cached_hashes": len(cache), "errors": errors}, indent=2))


if __name__ == "__main__":
    main()
