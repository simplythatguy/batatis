#!/usr/bin/env python3
"""Check the delivered corpus against the saved bytes, manifests and numbered folders."""
import hashlib
import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from pypdf import PdfReader
from PIL import Image

BASE = Path(__file__).resolve().parents[1]
logging.getLogger("pypdf").setLevel(logging.ERROR)


def main():
    errors, warnings = [], []
    index = json.loads((BASE / "index.json").read_text())
    cache_path = BASE / "_research" / "pdf_readability_cache.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    file_cache, pdfs = {}, {}
    def inspect(path, expected_hash=None):
        if not path.is_file():
            errors.append({"path": str(path.relative_to(BASE)), "error": "missing file"})
            return
        data = path.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if expected_hash and actual != expected_hash:
            errors.append({"path": str(path.relative_to(BASE)), "error": "SHA-256 mismatch"})
        if actual in file_cache:
            return
        file_cache[actual] = {"path": str(path.relative_to(BASE)), "bytes": len(data)}
        if path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"):
            try:
                with Image.open(path) as picture:
                    picture.verify()
            except Exception as exc:
                errors.append({"path": str(path.relative_to(BASE)), "error": "image decoder failed", "detail": str(exc)})
        if path.suffix.lower() == ".pdf":
            if not data.startswith(b"%PDF-"):
                errors.append({"path": str(path.relative_to(BASE)), "error": "non-PDF content in .pdf"})
                return
            if actual in cache:
                record = cache[actual]
                pdfs[actual] = {"path": str(path.relative_to(BASE)), "pages": record["pages"],
                                "first_three_pages_text_characters": record["first_three_pages_text_characters"],
                                "verification": "current bytes match SHA-256 of the previously parsed original"}
                if record["first_three_pages_text_characters"] < 80:
                    warnings.append({"path": str(path.relative_to(BASE)), "warning": "little extractable text; visual/OCR evaluation needed"})
                if record.get("parser_limit"):
                    pdfs[actual]["parser"] = record.get("parser")
                    warnings.append({"path": str(path.relative_to(BASE)), "warning": "pypdf reader limitation; original opens with PDFium", "detail": record["parser_limit"]})
                return
            try:
                reader = PdfReader(path, strict=False)
                count = len(reader.pages)
                if not count:
                    raise ValueError("zero pages")
                text = "\n".join((reader.pages[n].extract_text() or "") for n in range(min(3, count)))
                pdfs[actual] = {"path": str(path.relative_to(BASE)), "pages": count, "first_three_pages_text_characters": len(text)}
                if len(text.strip()) < 80:
                    warnings.append({"path": str(path.relative_to(BASE)), "warning": "little extractable text; visual/OCR evaluation needed"})
            except Exception as exc:
                errors.append({"path": str(path.relative_to(BASE)), "error": "PDF parser failed", "detail": str(exc)})
    for number, row in enumerate(index, 1):
        folder = BASE / row["folder"]
        if row["prompt"] != number or folder.name != f"Prompt {number}":
            errors.append({"case_id": row.get("case_id"), "error": "non-contiguous prompt numbering"})
        if row["worker"] in {f"H{n:02d}" for n in range(1, 19)} and row["priority_tier"] != 4:
            errors.append({"case_id": row["case_id"], "error": "outside-Alberta source incorrectly classified as local"})
        for filename in ("prompt.txt", "source.json", "evaluation.json"):
            if not (folder / filename).is_file():
                errors.append({"folder": folder.name, "error": "missing " + filename})
        source = json.loads((folder / "source.json").read_text())
        prompt = (folder / "prompt.txt").read_text()
        if len(prompt.strip()) < 150:
            errors.append({"folder": folder.name, "error": "empty/underspecified prompt"})
        if not source.get("facts"):
            errors.append({"folder": folder.name, "error": "no source-supported case facts"})
        for fact in source.get("facts", []):
            if not isinstance(fact, dict) or not fact.get("text") or not fact.get("locator"):
                errors.append({"folder": folder.name, "error": "source fact missing text or locator", "fact": fact})
        default_inputs = [a for a in source["attachments"] if a.get("included_in_default_input", True)]
        if not default_inputs:
            errors.append({"folder": folder.name, "error": "no default input attachment"})
        attachment_list = prompt.rsplit("\nAttachments:\n", 1)[-1].split("\n\nThis test question", 1)[0]
        if "_evaluation/" in attachment_list:
            errors.append({"folder": folder.name, "error": "held-back outcome reference is listed as default input"})
        for attachment in source["attachments"]:
            inspect(folder / attachment["filename"], attachment["sha256"])
            derived = attachment.get("derived_text")
            if derived:
                inspect(folder / derived["filename"], derived["sha256"])
            if not attachment.get("url"):
                errors.append({"folder": folder.name, "error": "missing original source URL"})
        eval_data = json.loads((folder / "evaluation.json").read_text())
        if source["case_type"] in ("issued_variance", "appeal_decision") and not eval_data.get("outcome_leakage"):
            warnings.append({"folder": folder.name, "warning": "published decision requires an outcome leakage review"})
    actual_folders = {p.name for p in BASE.glob("Prompt *") if p.is_dir()}
    expected_folders = {r["folder"] for r in index}
    if actual_folders != expected_folders:
        errors.append({"error": "extra/missing numbered folders", "extra": sorted(actual_folders - expected_folders), "missing": sorted(expected_folders - actual_folders)})
    package = json.loads((BASE / "_source_package" / "link_audit.json").read_text())
    if len(package) != 37 or len({r["url"] for r in package}) != 37:
        errors.append({"error": "source-package link inventory is not 37 unique audited targets"})
    for item in package:
        if item.get("status") == "downloaded":
            inspect(BASE / item["path"], item["sha256"])
    resources_path = BASE / "_source_package" / "resource_audit.json"
    resources = json.loads(resources_path.read_text()) if resources_path.exists() else []
    for item in resources:
        if item.get("status") == "downloaded":
            inspect(BASE / item["path"], item["sha256"])
    registry_path = BASE / "_source_package" / "ccmc_pdf_audit.json"
    registry = json.loads(registry_path.read_text()) if registry_path.exists() else []
    for item in registry:
        if item.get("status") == "downloaded":
            inspect(BASE / item["path"], item["sha256"])
    report = {"validated_at": datetime.now(timezone.utc).isoformat(), "prompt_count": len(index),
              "case_types": dict(Counter(r["case_type"] for r in index)), "jurisdictions": dict(Counter(r["jurisdiction"] for r in index)),
              "unique_attachment_and_reference_hashes_checked": len(file_cache), "unique_pdfs_parsed": len(pdfs),
              "pdf_pages": sum(r["pages"] for r in pdfs.values()), "package_links_audited": len(package),
              "linked_resources_attempted": len(resources), "resource_download_failures": sum(r["status"] != "downloaded" for r in resources),
              "ccmc_linked_pdfs": len(registry),
              "errors": errors, "warnings": warnings, "pdf_inventory": list(pdfs.values()),
              "scope": "Byte hashes, source paths, PDF readability, case metadata and numbering. Source facts require the accompanying case/worker review; this is not expert technical adjudication."}
    (BASE / "validation.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("pdf_inventory", "jurisdictions")}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
