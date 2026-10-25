#!/usr/bin/env python3
"""Restore selected originals from a local collection or explicit public URLs."""

import argparse
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

from assemble import html_text
from corpus import BASE, attachment_files, cases, check_file, child, select_numbers


def derive(original, destination):
    if original.suffix.lower() in (".html", ".htm"):
        destination.write_text(html_text(original) + "\n")
    elif original.suffix.lower() == ".docx":
        paragraphs = []
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        with zipfile.ZipFile(original) as archive:
            members = [name for name in archive.namelist() if name in
                       ("word/document.xml", "word/footnotes.xml", "word/endnotes.xml")]
            for member in members:
                tree = ElementTree.fromstring(archive.read(member))
                for paragraph in tree.iter(namespace + "p"):
                    text = "".join(node.text or "" for node in paragraph.iter(namespace + "t"))
                    if text:
                        paragraphs.append(text)
        destination.write_text("\n".join(paragraphs) + "\n")
    else:
        shutil.copyfile(original, destination)


def download(attachment, destination):
    url = (attachment.get("archive_url") or
           attachment.get("download_receipt", {}).get("final_url") or
           attachment.get("final_url") or attachment["url"])
    if urlsplit(url).scheme not in ("https", "http"):
        raise ValueError("download URL must use HTTP(S)")
    if attachment.get("reuse_status") == "rights_review_required" or any(
            urlsplit(value).hostname == "nrc-publications.canada.ca"
            for value in (url, attachment["url"])):
        raise ValueError("publisher rights review required; use a permitted local copy")
    # Use the same system trust store and transport as the original collector.
    result = subprocess.run([
        "curl", "--location", "--fail", "--silent", "--show-error",
        "--proto", "=https,http", "--proto-redir", "=https,http",
        "--connect-timeout", "20", "--max-time", "60",
        "--max-filesize", str(attachment["bytes"]),
        "--user-agent", "Batatis-corpus-restore/1.0",
        "--output", str(destination), "--url", url,
    ], capture_output=True, text=True)
    if result.returncode:
        raise ValueError(f"download failed ({result.returncode}): {result.stderr.strip()}")


def restore(base, source_root=None, numbers=None, network=False, include_evaluation=False):
    if network and not numbers:
        raise ValueError("network restoration requires explicit --case IDs or --prompt numbers")
    report = {"restored": 0, "already_verified": 0, "errors": []}
    for row, folder, source in cases(base, numbers):
        for item, original, derived in attachment_files(source, include_evaluation):
            name = item["filename"]
            temporary = None
            try:
                target = child(folder, name)
                if target.exists():
                    check_file(target, item)
                    report["already_verified"] += 1
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
                    temporary = Path(handle.name)
                local = child(source_root, f"{row['folder']}/{name}") if source_root else None
                if local and local.is_file():
                    shutil.copyfile(local, temporary)
                elif derived:
                    derive(child(folder, original["filename"]), temporary)
                elif source_root:
                    candidate = child(source_root, original["original_collection_path"])
                    shutil.copyfile(candidate, temporary)
                elif network:
                    download(original, temporary)
                else:
                    raise ValueError("supply --from or --download")
                check_file(temporary, item)
                temporary.replace(target)
                report["restored"] += 1
            except (OSError, ValueError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
                report["errors"].append({"prompt": row["prompt"], "file": name,
                                         "error": str(exc)})
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--from", dest="source_root", type=Path, help="existing local Data Prompts folder")
    mode.add_argument("--download", action="store_true", help="fetch explicitly selected prompts; publisher terms apply")
    parser.add_argument("--prompt", action="append", type=int, help="prompt number; repeat to select several")
    parser.add_argument("--case", dest="case_ids", action="append", help="case ID; repeat to select several")
    parser.add_argument("--include-evaluation", action="store_true", help="also restore held-back evaluator references")
    args = parser.parse_args()
    try:
        numbers = select_numbers(BASE, args.prompt, args.case_ids)
        report = restore(BASE, args.source_root, numbers, args.download, args.include_evaluation)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2))
    return bool(report["errors"])


if __name__ == "__main__":
    raise SystemExit(main())
