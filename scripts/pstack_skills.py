#!/usr/bin/env python3
"""Generate or check Batatis's regular-file pstack skill entrypoints.

--write creates the initial hash manifest and repairs generated wrappers. An
existing manifest pins the source bytes: --write refuses to bless source drift.
A reviewed upstream update must update the provenance below and replace the
manifest. This script never runs vendored code or installs plugin hooks.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = Path(".agents/pstack")
SOURCE = BUNDLE / "upstream"
MANIFEST = BUNDLE / "manifest.json"
SURFACES = (".agents/skills", ".claude/skills", ".cursor/skills")
NOTICES = (
    "LICENSE", "LICENSE-cursor-team-kit", "LICENSE-superpowers", "NOTICE.md", "UPSTREAM.md",
)
PROVENANCE = {
    "repository": "https://github.com/ericlitman/open-pstack",
    "version": "1.16.0",
    "commit": "b4c5e3d63318308b7e11f26b2bc156e7793d834a",
    "source_subdirectory": "plugins/pstack",
    "root_notice_files": list(NOTICES),
}
SOURCE_FILE_COUNT = 273 + len(NOTICES)
SKILL_COUNT = 63
REFERENCE_NOTES = [{
    "source": "skills/why/references/synthesizer-prompt.md",
    "target": "url",
    "reason": "Citation-template placeholder, not a local file reference.",
}]


def tree_files(directory: Path) -> list[Path]:
    """Reject links before reading or writing through a bundled path."""
    for part in (directory, *directory.parents):
        if part == ROOT:
            break
        if part.is_symlink():
            raise ValueError(f"symlink is not portable: {part.relative_to(ROOT)}")
    files = []
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"symlink is not portable: {path.relative_to(ROOT)}")
        if path.is_file():
            files.append(path)
        elif not path.is_dir():
            raise ValueError(f"not a regular file or directory: {path.relative_to(ROOT)}")
    return files


def scalar(value: str) -> str:
    # The pinned frontmatter uses single-line plain or quoted strings only.
    if value.startswith('"'):
        value = json.loads(value)
    elif value.startswith("'") and value.endswith("'"):
        value = value[1:-1].replace("''", "'")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("expected a nonempty frontmatter string")
    return value


def wrappers(source_files: list[Path]) -> dict[Path, bytes]:
    generated = {}
    names = set()
    skills = [path for path in source_files if path.name == "SKILL.md"]
    if len(skills) != SKILL_COUNT:
        raise ValueError(f"expected {SKILL_COUNT} source skills, found {len(skills)}")
    for path in skills:
        if path.parent.parent != ROOT / SOURCE / "skills":
            raise ValueError(f"uncovered nested skill: {path.relative_to(ROOT)}")
        match = re.match(r"\A---\n(.*?)\n---(?:\n|$)", path.read_bytes().decode("utf-8"), re.S)
        if not match:
            raise ValueError(f"missing frontmatter: {path.relative_to(ROOT)}")
        header = match[1]
        fields = {}
        for line in header.splitlines():
            field = re.fullmatch(r"([a-z][a-z-]*):\s*(.+)", line)
            if not field or field[1] in fields:
                raise ValueError(f"unsupported or duplicate frontmatter: {path.relative_to(ROOT)}")
            fields[field[1]] = field[2]
        name = scalar(fields.get("name", ""))
        local_name = "pstack-" + name
        if name != path.parent.name or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", local_name):
            raise ValueError(f"invalid skill name: {path.relative_to(ROOT)}")
        if len(local_name) > 64 or local_name in names:
            raise ValueError(f"duplicate or overlong skill name: {local_name}")
        names.add(local_name)
        if len(scalar(fields.get("description", ""))) > 1024:
            raise ValueError(f"overlong description: {path.relative_to(ROOT)}")
        for flag in ("disable-model-invocation", "user-invocable"):
            if flag in fields and fields[flag] not in ("true", "false"):
                raise ValueError(f"invalid {flag}: {path.relative_to(ROOT)}")
        # Preserve description, invocation flags, paths, and any other metadata.
        header = re.sub(r"^name:.*$", "name: " + local_name, header, flags=re.M)
        content = (
            f"---\n{header}\n---\n\n# {local_name}\n\n"
            "Read `.agents/pstack/ADAPTER.md` from the repository root, then\n"
            f"`.agents/pstack/upstream/skills/{name}/SKILL.md`.\n\n"
            "Apply the adapter to the upstream method. Resolve its relative links and file\n"
            "references from the upstream source file's directory, not this wrapper.\n"
        ).encode("utf-8")
        for surface in SURFACES:
            generated[Path(surface) / local_name / "SKILL.md"] = content
    return generated


def markdown_prose(text: str) -> str:
    """Keep line numbers while excluding YAML and fenced code examples."""
    lines, fence = [], ""
    source_lines = text.splitlines()
    frontmatter = bool(source_lines and source_lines[0] == "---")
    for index, line in enumerate(source_lines):
        if frontmatter:
            if index and line == "---":
                frontmatter = False
            lines.append("")
            continue
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                fence = ""
            lines.append("")
        elif marker:
            fence = marker[1]
            lines.append("")
        else:
            lines.append(line)
    return "\n".join(lines)


def anchors(path: Path) -> set[str]:
    text = markdown_prose(path.read_text(encoding="utf-8"))
    result = set(re.findall(r'<a\s+[^>]*(?:id|name)=[\'"]([^\'"]+)[\'"]', text, re.I))
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^\s{0,3}#{1,6}\s+(.*?)(?:\s+#+)?\s*$", line)
        heading = match[1] if match else ""
        if (
            not match and index + 1 < len(lines) and line.strip()
            and re.fullmatch(r" {0,3}(?:=+|-+)\s*", lines[index + 1])
        ):
            heading = line.strip()
        if not heading:
            continue
        heading = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", heading)
        heading = html.unescape(re.sub(r"<[^>]*>", "", heading)).lower()
        slug = "".join(
            c for c in heading if c in "-_" or unicodedata.category(c)[0] not in "PS"
        ).replace(" ", "-")
        candidate, number = slug, 0
        while candidate in result:
            number += 1
            candidate = f"{slug}-{number}"
        result.add(candidate)
    return result


def link_issues(source_files: list[Path]) -> dict[tuple[str, str, str], int]:
    issues = {}
    source_root = (ROOT / SOURCE).resolve()
    notes = {(note["source"], note["target"]) for note in REFERENCE_NOTES}
    # Inline/image links and reference definitions; code spans are examples.
    link_pattern = re.compile(
        r"!?\[[^\]\n]*\]\(\s*(<[^>\n]*>|(?:\\.|[^\s()\\]|\([^()\n]*\))+)"
        r"(?:\s+[\'\"][^\n]*?[\'\"])?\s*\)"
        r"|^ {0,3}\[[^]\n]+\]:\s*(<[^>\n]*>|\S+)", re.M,
    )
    for path in source_files:
        if path.suffix.lower() != ".md":
            continue
        text = markdown_prose(path.read_text(encoding="utf-8"))
        text = re.sub(
            r"(?<!`)(`+)(?!`)(.*?)(?<!`)\1(?!`)",
            lambda m: re.sub(r"[^\n]", " ", m[0]), text, flags=re.S,
        )
        source = path.relative_to(source_root).as_posix()
        for match in link_pattern.finditer(text):
            target = (match[1] or match[2]).strip("<>")
            if (source, target) in notes:
                continue
            url = urlsplit(html.unescape(target))
            if url.scheme and url.scheme != "file" or url.netloc:
                continue
            destination = (path.parent / unquote(url.path)).resolve() if url.path else path
            problem = ""
            if url.scheme == "file":
                problem = "nonportable file URL"
            elif not destination.is_relative_to(source_root):
                problem = "target is outside the vendored bundle"
            elif not destination.exists():
                problem = "missing local target"
            elif (
                url.fragment and destination.suffix.lower() == ".md" and destination.is_file()
                and unquote(url.fragment) not in anchors(destination)
            ):
                problem = "missing Markdown fragment"
            if problem:
                issues.setdefault((source, target, problem), text.count("\n", 0, match.start()) + 1)
    return issues


def check_links(source_files: list[Path], acknowledged: list) -> list[str]:
    issues = link_issues(source_files)
    errors, known = [], set()
    for item in acknowledged:
        if (
            not isinstance(item, dict) or set(item) != {"source", "target", "problem", "reason"}
            or not all(isinstance(value, str) and value.strip() for value in item.values())
        ):
            raise ValueError("invalid known_upstream_link_issues entry")
        key = (item["source"], item["target"], item["problem"])
        if key in known or key not in issues:
            raise ValueError(f"duplicate or stale upstream link acknowledgement: {key}")
        known.add(key)
        print(f"known upstream reference: {item['source']} -> {item['target']}: {item['reason']}")
    for (source, target, problem), line in issues.items():
        if (source, target, problem) not in known:
            errors.append(f"{SOURCE / source}:{line}: {problem}: {target}")
    return errors


def run(write: bool) -> int:
    tree_files(ROOT / BUNDLE)
    actual_wrappers, actual_directories = set(), set()
    for surface in SURFACES:
        directory = ROOT / surface
        for part in (directory, directory.parent):
            if part.is_symlink():
                raise ValueError(f"symlink is not portable: {part.relative_to(ROOT)}")
        for entry in sorted(directory.glob("pstack-*")):
            if not entry.is_dir() or entry.is_symlink():
                raise ValueError(f"entrypoint must be a regular directory: {entry.relative_to(ROOT)}")
            actual_directories.add(entry.relative_to(ROOT))
            actual_wrappers.update(path.relative_to(ROOT) for path in tree_files(entry))
            if any(path.is_dir() for path in entry.iterdir()):
                raise ValueError(f"unexpected entrypoint subdirectory: {entry.relative_to(ROOT)}")
    files = tree_files(ROOT / SOURCE)
    for name in NOTICES:
        if ROOT / SOURCE / name not in files:
            raise ValueError(f"missing required root notice: {SOURCE / name}")
    if len(files) != SOURCE_FILE_COUNT:
        raise ValueError(f"expected {SOURCE_FILE_COUNT} vendored files, found {len(files)}")
    for name in (".claude-plugin", ".codex-plugin"):
        plugin = json.loads((ROOT / SOURCE / name / "plugin.json").read_text(encoding="utf-8"))
        if plugin.get("name") != "pstack" or plugin.get("version") != PROVENANCE["version"]:
            raise ValueError(f"unexpected {name} plugin name/version")
    generated = wrappers(files)
    manifest_path = ROOT / MANIFEST
    saved = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else None
    if manifest_path.exists() and not isinstance(saved, dict):
        raise ValueError("manifest must be a JSON object")
    acknowledged = saved.get("known_upstream_link_issues", []) if saved else []
    if not isinstance(acknowledged, list):
        raise ValueError("known_upstream_link_issues must be a list")
    manifest = {
        "schema_version": 1,
        "upstream": PROVENANCE,
        "vendored_files": {
            path.relative_to(ROOT / SOURCE).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in files
        },
        "skill_names": sorted(path.parent.name for path in generated if path.parts[0] == ".agents"),
        "entrypoint_surfaces": list(SURFACES),
        "reference_notes": REFERENCE_NOTES,
        "known_upstream_link_issues": acknowledged,
    }
    errors = []
    if saved is None and not write:
        errors.append(f"missing manifest: {MANIFEST}; run with --write")
    elif saved is not None:
        if set(saved) != set(manifest):
            errors.append("manifest fields differ from the generator")
        for key in manifest.keys() - {"vendored_files"}:
            if saved.get(key) != manifest[key]:
                errors.append(f"manifest {key} differs from the generator")
        recorded = saved.get("vendored_files", {})
        if not isinstance(recorded, dict):
            raise ValueError("manifest vendored_files must be an object")
        for name in sorted(recorded.keys() - manifest["vendored_files"].keys()):
            errors.append(f"missing vendored file: {SOURCE / name}")
        for name, digest in manifest["vendored_files"].items():
            if name not in recorded:
                errors.append(f"unrecorded vendored file: {SOURCE / name}")
            elif recorded[name] != digest:
                errors.append(f"source SHA256 drift: {SOURCE / name}")
    if errors:
        raise ValueError("\n".join(errors) + "\nRestore the pinned source/manifest before generating wrappers.")
    unexpected = actual_wrappers - generated.keys()
    if unexpected:
        raise ValueError("unexpected entrypoint files: " + ", ".join(str(path) for path in sorted(unexpected)))
    unexpected_dirs = actual_directories - {path.parent for path in generated}
    if unexpected_dirs:
        raise ValueError("unexpected entrypoint directories: " + ", ".join(str(path) for path in sorted(unexpected_dirs)))
    if not (ROOT / BUNDLE / "ADAPTER.md").is_file():
        errors.append(f"missing local required reference: {BUNDLE / 'ADAPTER.md'}")
    if write:
        if saved is None:
            manifest_path.write_bytes((json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
        for relative, content in generated.items():
            path = ROOT / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    for relative, content in generated.items():
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing wrapper: {relative}")
        elif path.read_bytes() != content:
            errors.append(f"generated wrapper drift: {relative}; run with --write")
    errors.extend(check_links(files, acknowledged))
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    print(f"pstack skills: {len(files)} vendored hashes, {SKILL_COUNT} skills, {len(generated)} regular-file entrypoints; {'FAILED' if errors else 'OK'}")
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="create the initial manifest and regenerate wrappers")
    mode.add_argument("--check", action="store_true", help="validate without writing (default)")
    args = parser.parse_args()
    try:
        return run(args.write)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
