#!/usr/bin/env python3
"""Download public source bytes without modifying them; workers own separate folders."""
import argparse
import hashlib
import json
import io
import re
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlparse


def fetch(url, directory, name=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    record = {"url": url, "retrieved_at": stamp}
    if urlparse(url).scheme not in ("https", "http"):
        return {**record, "status": "unsupported_scheme"}
    with tempfile.TemporaryDirectory() as tmp:
        body, headers = Path(tmp) / "body", Path(tmp) / "headers"
        retrieval_url = quote(url, safe="/:?=&%#@+;,")
        record["retrieval_url"] = retrieval_url
        command = ["curl", "--location", "--silent", "--show-error", "--retry", "1",
                   "--connect-timeout", "20", "--max-time", "150", "--max-filesize", "150000000",
                   "--proto", "=https,http", "--proto-redir", "=https,http",
                   "--user-agent", "Mozilla/5.0 (public-building-research)",
                   "--dump-header", str(headers), "--output", str(body),
                   "--write-out", "%{http_code}\n%{url_effective}\n%{content_type}", retrieval_url]
        result = subprocess.run(command, capture_output=True, text=True)
        info = result.stdout.splitlines()
        record.update(http_status=info[0] if info else None,
                      final_url=info[1] if len(info) > 1 else url,
                      content_type=info[2] if len(info) > 2 else "",
                      error=result.stderr[-1500:] or None)
        if result.returncode or not body.exists() or not record["http_status"].startswith("2"):
            return {**record, "status": "download_failed"}
        data = body.read_bytes()
        ctype = record["content_type"].lower()
        pdf_start = data.find(b"%PDF-", 0, 4096)
        if "application/pdf" in ctype and pdf_start > 0:
            raw_hash = hashlib.sha256(data).hexdigest()
            raw_target = directory / ("transport-capture-" + raw_hash[:16] + ".bin")
            raw_target.write_bytes(data)
            record.update(raw_capture_path=str(raw_target.resolve()), raw_capture_sha256=raw_hash,
                          entity_extraction=f"Copied unchanged PDF entity from byte {pdf_start}; original transport capture retained.")
            data = data[pdf_start:]
        digest = hashlib.sha256(data).hexdigest()
        original = unquote(Path(urlparse(record["final_url"]).path).name) or "source"
        ext = Path(original).suffix.lower()
        if data.startswith(b"%PDF-"):
            ext, kind = ".pdf", "pdf"
        elif data.startswith(b"PK\x03\x04"):
            kind = "zip_container"
            ext = ext if ext in (".docx", ".xlsx", ".pptx", ".zip") else ".zip"
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    members = archive.namelist()
                    if "word/document.xml" in members:
                        ext = ".docx"
                    elif "xl/workbook.xml" in members:
                        ext = ".xlsx"
                    elif "ppt/presentation.xml" in members:
                        ext = ".pptx"
            except zipfile.BadZipFile:
                kind = "invalid_zip"
        elif data.startswith(b"\x89PNG"):
            ext, kind = ".png", "image"
        elif data.startswith(b"\xff\xd8\xff"):
            ext, kind = ".jpg", "image"
        elif "html" in ctype or b"<html" in data[:5000].lower() or b"<!doctype html" in data[:5000].lower():
            ext, kind = ".html", "html"
        else:
            ext, kind = ext or ".bin", "other"
            if "json" in ctype or data.lstrip().startswith((b"{", b"[")):
                try:
                    json.loads(data)
                    ext, kind = ".json", "json"
                except (ValueError, UnicodeDecodeError):
                    pass
        stem = name or Path(original).stem
        stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-.")[:110] or "source"
        target = directory / (stem + "-" + digest[:12] + ext)
        target.write_bytes(data)
        record.update(status="downloaded", path=str(target.resolve()), filename=target.name,
                      sha256=digest, bytes=len(data), kind=kind)
        if kind == "html":
            text = data[:100000].decode("utf-8", errors="replace").lower()
            markers = ["just a moment...", "access denied", "captcha", "enable javascript and cookies", "request blocked"]
            record["possible_block_page"] = any(s in text for s in markers)
        (directory / (target.name + ".source.json")).write_text(json.dumps(record, indent=2) + "\n")
        return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("directory")
    parser.add_argument("--name")
    args = parser.parse_args()
    print(json.dumps(fetch(args.url, args.directory, args.name), indent=2))


if __name__ == "__main__":
    main()
