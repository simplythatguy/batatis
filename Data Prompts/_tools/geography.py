"""Explicit source geography and stable descriptive case directory names."""

import json
import re
import unicodedata
from pathlib import Path


def load_geography(base):
    return json.loads((base / "geography.json").read_text())


def component(value):
    if not isinstance(value, str) or not value.strip() or value in (".", ".."):
        raise ValueError("empty or invalid geography component")
    if re.search(r'[\\/:*?"<>|\x00-\x1f]', value) or value != value.strip():
        raise ValueError(f"invalid geography component: {value}")
    return value


def case_folder(record, geography):
    slug = unicodedata.normalize("NFKD", record["title"]).encode("ascii", "ignore").decode().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")[:72].rstrip("-") or "case"
    case_id = component(record.get("case_id") or record["id"])
    return Path(*(component(geography[key]) for key in
                  ("country", "province_or_state", "city_or_town")), "Prompts", f"{case_id}-{slug}").as_posix()
