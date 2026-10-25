#!/usr/bin/env python3
"""Assemble researched records into portable, provenance-backed attachment tests."""
import csv
import hashlib
import json
import re
import shutil
import zipfile
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

BASE = Path(__file__).resolve().parents[1]
TYPES = {"actual_application", "issued_variance", "appeal_decision", "documented_design_study",
         "published_worked_example", "product_evidence", "research_evidence", "documented_case_summary", "regulatory_guidance"}
RANK = {kind: i for i, kind in enumerate(["actual_application", "documented_design_study",
        "issued_variance", "appeal_decision", "documented_case_summary", "published_worked_example", "regulatory_guidance", "product_evidence", "research_evidence"])}


class SourceText(HTMLParser):
    def __init__(self, main_only=False):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip, self.main = [], 0, 0
        self.main_only = main_only
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg", "nav", "header", "footer"):
            self.skip += 1
        if tag == "main":
            self.main += 1
        if not self.skip and tag in ("p", "div", "li", "br", "h1", "h2", "h3", "h4", "tr", "section"):
            self.parts.append("\n")
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg", "nav", "header", "footer") and self.skip:
            self.skip -= 1
        if tag == "main" and self.main:
            self.main -= 1
        if tag in ("p", "div", "li", "h1", "h2", "h3", "h4", "tr", "section"):
            self.parts.append("\n")
    def handle_data(self, data):
        if not self.skip and (not self.main_only or self.main):
            self.parts.append(data)
    def text(self):
        return "\n".join(line for s in "".join(self.parts).splitlines() if (line := re.sub(r"\s+", " ", s).strip()))


def html_text(path):
    raw = path.read_text(errors="replace")
    parser = SourceText(main_only="<main" in raw.lower())
    parser.feed(raw)
    return parser.text()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def priority(record):
    jurisdiction = record["jurisdiction"].lower()
    # These completed source lanes are explicitly outside Alberta, even where a disclaimer names it.
    worker = record.get("worker", "")
    if re.fullmatch(r"H(?:0[1-9]|1[0-8])", worker):
        return 4, "Outside Alberta - attachment comparison only"
    # Negative/comparative qualifications often mention the target cities; they are not locations.
    if record.get("worker") in ("L15", "L16", "L17", "L18"):
        return 3, "Canadian supporting evidence"
    geography = re.split(r"[;(]|\s+[—–]\s+", jurisdiction, maxsplit=1)[0].strip()
    if any(city in geography for city in ("calgary", "edmonton")) and not geography.startswith(("not ", "non-", "no ")):
        return 1, "Calgary / Edmonton"
    if "alberta" in geography and not geography.startswith(("not ", "non-", "no ")) or geography == "ab":
        return 2, "Other Alberta / province-wide"
    if record["case_type"] in ("product_evidence", "research_evidence") and (geography.startswith("canada") or "nrc" in geography):
        return 3, "Canadian supporting evidence"
    return 4, "Outside Alberta - attachment comparison only"


def normalize_case(case, worker, errors):
    record = dict(case)
    record["worker"] = worker
    record.setdefault("id", worker + "-" + hashlib.sha256(str(record).encode()).hexdigest()[:8])
    for required in ("title", "jurisdiction", "case_type", "source_url", "prompt", "facts"):
        if not record.get(required):
            errors.append({"case_id": record["id"], "error": "missing " + required})
            return None
    if record["case_type"] not in TYPES:
        errors.append({"case_id": record["id"], "error": "unrecognized case type", "value": record["case_type"]})
        return None
    attachments = []
    for item in record.get("attachments", []):
        if not isinstance(item, dict):
            errors.append({"case_id": record["id"], "error": "attachment is not a metadata object"})
            continue
        path = Path(item.get("path", ""))
        if not path.is_absolute():
            candidates = [BASE.parent / path, BASE / "_research" / "workers" / worker / path]
            path = next((p for p in candidates if p.is_file()), path)
        if not path.is_file() or not item.get("url"):
            errors.append({"case_id": record["id"], "error": "missing attachment or original URL", "attachment": item})
            continue
        actual_hash = digest(path)
        if item.get("sha256") and item["sha256"] != actual_hash:
            errors.append({"case_id": record["id"], "error": "attachment hash mismatch", "path": str(path)})
            continue
        data = path.read_bytes()[:1000]
        if path.suffix.lower() == ".pdf" and not data.startswith(b"%PDF-"):
            errors.append({"case_id": record["id"], "error": "PDF extension has non-PDF bytes", "path": str(path)})
            continue
        if path.suffix.lower() in (".html", ".htm"):
            text = html_text(path)
            if len(text) < 250 or re.search(r"^(Access Denied|Just a moment|403 Forbidden|404 Not Found)", text, re.I):
                errors.append({"case_id": record["id"], "error": "HTML is empty, blocked or not a usable document", "path": str(path)})
                continue
        attachments.append({**item, "path": str(path.resolve()), "sha256": actual_hash, "bytes": path.stat().st_size})
    if not attachments:
        errors.append({"case_id": record["id"], "error": "no valid attachment"})
        return None
    record["attachments"] = attachments
    return record


def main():
    errors, cases, duplicates, excluded = [], [], [], []
    override_path = BASE / "_research" / "curation_overrides.json"
    overrides = json.loads(override_path.read_text()) if override_path.exists() else {}
    for manifest in sorted((BASE / "_research" / "workers").glob("*/candidates.json")):
        try:
            data = json.loads(manifest.read_text())
            for case in data.get("cases", []):
                override = overrides.get("case_overrides", {}).get(case.get("id")) or overrides.get("worker_case_type_overrides", {}).get(manifest.parent.name)
                if override:
                    if override.get("exclude"):
                        excluded.append({"case_id": case.get("id"), "worker": manifest.parent.name, "reason": override["reason"]})
                        continue
                    case = {**case, "original_worker_case_type": case.get("case_type"), "case_type": override.get("case_type", case.get("case_type")), "parent_curation_note": override["reason"]}
                    if override.get("additional_limitations"):
                        case["limitations"] = list(case.get("limitations", [])) + override["additional_limitations"]
                    if override.get("additional_attachments"):
                        case["attachments"] = list(case.get("attachments", [])) + override["additional_attachments"]
                    if override.get("replace_attachments"):
                        case["attachments"] = override["replace_attachments"]
                    if override.get("prompt_override"):
                        case["prompt"] = override["prompt_override"]
                    if override.get("prompt_append"):
                        case["prompt"] = case.get("prompt", "").rstrip() + "\n\n" + override["prompt_append"]
                    if override.get("additional_review_focus"):
                        evaluation = dict(case.get("evaluation", {}))
                        focus = evaluation.get("review_focus", [])
                        evaluation["review_focus"] = (focus if isinstance(focus, list) else [focus]) + override["additional_review_focus"]
                        case["evaluation"] = evaluation
                    if override.get("evaluation_override"):
                        case["evaluation"] = {**case.get("evaluation", {}), **override["evaluation_override"]}
                record = normalize_case(case, manifest.parent.name, errors)
                if record:
                    cases.append(record)
        except Exception as exc:
            errors.append({"manifest": str(manifest), "error": str(exc)})
    cases.sort(key=lambda r: (priority(r)[0], RANK[r["case_type"]], r["worker"], r["id"]))
    seen, accepted = {}, []
    for case in cases:
        hashes = tuple(sorted(a["sha256"] for a in case["attachments"]))
        # Distinct studies within a shared report require explicit study/page facts.
        locators = tuple(sorted(str(f.get("locator", "")) for f in case["facts"] if isinstance(f, dict)))
        key = (hashes, locators if case["case_type"] in ("documented_design_study", "published_worked_example", "documented_case_summary") else ())
        if key in seen:
            duplicates.append({"duplicate_id": case["id"], "kept_id": seen[key], "reason": "same original source set and case location"})
            continue
        seen[key] = case["id"]
        accepted.append(case)
    # Keep records sharing an original input report together when selecting evaluation sets.
    parents = list(range(len(accepted)))
    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    owner = {}
    for i, case in enumerate(accepted):
        primary = [a for a in case["attachments"] if a.get("role") == "input"] or case["attachments"]
        for attachment in primary:
            value = attachment["sha256"]
            if value in owner:
                parents[root(i)] = root(owner[value])
            else:
                owner[value] = i
    group_members = {}
    for i, case in enumerate(accepted):
        group_members.setdefault(root(i), []).append(case["id"])
    group_ids = {r: hashlib.sha256("|".join(sorted(members)).encode()).hexdigest()[:16] for r, members in group_members.items()}
    index = []
    for number, case in enumerate(accepted, 1):
        folder = BASE / f"Prompt {number}"
        folder.mkdir(exist_ok=True)
        attachment_rows, usable = [], []
        has_non_outcome = any(a.get("role") != "outcome_reference" for a in case["attachments"])
        for i, item in enumerate(case["attachments"], 1):
            source = Path(item["path"])
            default_input = item.get("role") != "outcome_reference" or not has_non_outcome
            target_dir = folder if default_input else folder / "_evaluation"
            target_dir.mkdir(exist_ok=True)
            target = target_dir / source.name
            if target.exists() and digest(target) != item["sha256"]:
                target = target_dir / (f"attachment-{i}-" + source.name)
            shutil.copy2(source, target)
            row = {k: v for k, v in item.items() if k != "path"}
            row.update(filename=str(target.relative_to(folder)), included_in_default_input=default_input,
                       original_collection_path=str(source.relative_to(BASE)) if source.is_relative_to(BASE) else str(source))
            if "nrc-publications.canada.ca" in item.get("url", ""):
                row["reuse_status"] = "rights_review_required"
                row["rights_source"] = "https://nrc-publications.canada.ca/eng/copyright/"
            receipt = source.with_name(source.name + ".source.json")
            if receipt.is_file():
                download = json.loads(receipt.read_text())
                row["download_receipt"] = {key: download.get(key) for key in ("retrieved_at", "http_status", "final_url", "content_type", "kind", "status", "entity_extraction", "raw_capture_sha256", "raw_capture_path") if download.get(key) is not None}
            else:
                row["download_receipt"] = {"retrieved_at": "not recorded in a collect.py sidecar; consult worker report", "kind": source.suffix.lstrip(".")}
            if source.suffix.lower() in (".html", ".htm"):
                derived = target_dir / f"attachment-{i}-source-text.txt"
                derived.write_text(html_text(source) + "\n")
                row["derived_text"] = {"filename": str(derived.relative_to(folder)), "sha256": digest(derived), "operation": "HTML text extraction; no facts authored"}
                if default_input:
                    usable.append(str(derived.relative_to(folder)))
            elif source.suffix.lower() in (".json", ".csv", ".tsv"):
                derived = target_dir / f"attachment-{i}-source-data.txt"
                shutil.copy2(source, derived)
                row["derived_text"] = {"filename": str(derived.relative_to(folder)), "sha256": digest(derived), "operation": "Byte-identical text copy using .txt extension; original data file retained"}
                if default_input:
                    usable.append(str(derived.relative_to(folder)))
            elif source.suffix.lower() == ".docx":
                paragraphs = []
                with zipfile.ZipFile(source) as archive:
                    members = [n for n in archive.namelist() if n == "word/document.xml" or n in ("word/footnotes.xml", "word/endnotes.xml")]
                    for member in members:
                        tree = ElementTree.fromstring(archive.read(member))
                        for paragraph in tree.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
                            text = "".join(node.text or "" for node in paragraph.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"))
                            if text:
                                paragraphs.append(text)
                derived = target_dir / f"attachment-{i}-source-text.txt"
                derived.write_text("\n".join(paragraphs) + "\n")
                row["derived_text"] = {"filename": str(derived.relative_to(folder)), "sha256": digest(derived), "operation": "DOCX body/footnote/endnote paragraph text extraction; layout and list numbering not reproduced; original retained"}
                if default_input:
                    usable.append(str(derived.relative_to(folder)))
            else:
                if default_input:
                    usable.append(str(target.relative_to(folder)))
            attachment_rows.append(row)
        tier, tier_label = priority(case)
        text = case["prompt"].strip()
        if tier == 4:
            text = "Comparative attachment exercise: this source is from " + case["jurisdiction"] + ". It is not an Alberta application.\n\n" + text
        text += "\n\nAttachments:\n" + "\n".join("- " + name for name in usable)
        text += "\n\nThis test question is reconstructed from published source material. Use the source jurisdiction and code edition. Identify missing administrative information and evidence; professional technical conclusions remain with the responsible reviewer.\n"
        (folder / "prompt.txt").write_text(text)
        source_meta = {k: v for k, v in case.items() if k not in ("prompt", "evaluation", "attachments")}
        source_meta.update(prompt_number=number, priority_tier=tier, priority=tier_label, attachments=attachment_rows,
                           prompt_origin="reconstructed source-derived evaluation question; not an original applicant message")
        source_meta["reuse_status"] = "rights_review_required" if any(a.get("reuse_status") == "rights_review_required" for a in attachment_rows) else "publisher_terms_apply; no blanket dataset licence asserted"
        write_json(folder / "source.json", source_meta)
        evaluation = dict(case.get("evaluation", {}))
        evaluation.setdefault("known_outcome", "unknown; no expert assessment supplied")
        evaluation.setdefault("outcome_leakage", case["case_type"] in ("issued_variance", "appeal_decision", "product_evidence"))
        if case["case_type"] in ("issued_variance", "appeal_decision", "product_evidence"):
            evaluation["outcome_leakage"] = True
        evaluation.update(case_id=case["id"], evaluator_only=True,
                          jurisdiction_priority=tier_label,
                          alberta_evaluation_use="comparative attachment format/content only" if tier == 4 else "source extraction and administrative evidence exercise; not technical approval",
                          instruction="Do not upload this file with the test prompt. Published outcome is not a new technical approval or a complete scored ground truth.")
        write_json(folder / "evaluation.json", evaluation)
        source_group = group_ids[root(number - 1)]
        row = {"prompt": number, "folder": folder.name, "priority_tier": tier, "priority": tier_label, "case_id": case["id"], "title": case["title"],
               "case_type": case["case_type"], "jurisdiction": case["jurisdiction"], "code_edition": case.get("code_edition", "unknown"),
               "source_url": case["source_url"], "attachments": len(attachment_rows), "source_group": source_group,
               "outcome_leakage": evaluation["outcome_leakage"], "reuse_status": source_meta["reuse_status"], "worker": case["worker"]}
        index.append(row)
    if index:
        with (BASE / "index.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(index[0]))
            writer.writeheader()
            writer.writerows(index)
    write_json(BASE / "index.json", index)
    write_json(BASE / "_research" / "assembly_report.json", {"created_at": datetime.now(timezone.utc).isoformat(),
               "candidate_count": len(cases), "prompt_count": len(index), "case_types": dict(Counter(r["case_type"] for r in index)),
               "errors": errors, "duplicates": duplicates, "excluded_candidates": excluded,
               "distinct_source_groups": len({r["source_group"] for r in index})})
    print(json.dumps({"prompts": len(index), "errors": len(errors), "duplicates": len(duplicates), "types": dict(Counter(r["case_type"] for r in index))}, indent=2))


if __name__ == "__main__":
    main()
