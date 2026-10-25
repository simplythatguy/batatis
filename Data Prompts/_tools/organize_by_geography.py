#!/usr/bin/env python3
"""Move complete case folders into their documented geographic hierarchy."""

import json
from pathlib import Path

from corpus import BASE, child, write_indexes
from geography import case_folder, load_geography
from write_readme import write_navigation


def relocate_paths(value, previous):
    if isinstance(value, dict):
        return {key: relocate_paths(item, previous) for key, item in value.items()}
    if isinstance(value, list):
        return [relocate_paths(item, previous) for item in value]
    if isinstance(value, str):
        for old, new in previous.items():
            if value == old or value.startswith(old + "/"):
                return new + value[len(old):]
    return value


def organize(base=BASE):
    index = json.loads((base / "index.json").read_text())
    geography = load_geography(base)
    if set(geography) != {row["case_id"] for row in index}:
        raise ValueError("geography must contain exactly one entry for every indexed case")
    moves = []
    destinations = set()
    for row in index:
        relative = case_folder(row, geography[row["case_id"]])
        source, target = child(base, row["folder"]), child(base, relative)
        if relative in destinations:
            raise ValueError(f"duplicate destination: {relative}")
        destinations.add(relative)
        if not source.is_dir():
            # Resume a prior move interrupted before the index was written.
            manifest = target / "source.json"
            if not manifest.is_file() or json.loads(manifest.read_text())["id"] != row["case_id"]:
                raise ValueError(f"missing source: {row['case_id']}")
            source = target
        elif source != target and target.exists():
            raise ValueError(f"occupied destination: {row['case_id']}")
        moves.append((row, source, target, relative))
    previous = {row["folder"]: relative for row, _, _, relative in moves}
    for row, source, target, relative in moves:
        if source != target:
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)
        location = geography[row["case_id"]]
        source_path = target / "source.json"
        metadata = json.loads(source_path.read_text())
        metadata["geography"] = location
        source_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
        row.update(folder=relative, **{key: location[key] for key in
                                      ("country", "province_or_state", "city_or_town")})
    write_indexes(base, index)
    # Preserve the original verification record while updating its file pointers.
    path = base / "validation.json"
    if path.exists():
        report = relocate_paths(json.loads(path.read_text()), previous)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    write_navigation(base, index)
    return {"cases": len(index), "country_folders": len({r["country"] for r in index}),
            "locality_folders": len({(r["country"], r["province_or_state"], r["city_or_town"]) for r in index})}


if __name__ == "__main__":
    print(json.dumps(organize(), indent=2))
