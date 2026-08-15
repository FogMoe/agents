#!/usr/bin/env python3
"""Generate the README skill catalog from SKILL.md metadata."""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


START_MARKER = "<!-- skills:start -->"
END_MARKER = "<!-- skills:end -->"
SUMMARY_KEY = "fogmoe-summary"


class CatalogError(ValueError):
    """Raised when the skill catalog source is invalid."""


@dataclass(frozen=True)
class Skill:
    name: str
    summary: str
    readme_path: str


def _parse_scalar(value: str, *, path: Path, field: str) -> str:
    value = value.strip()
    if not value:
        raise CatalogError(f"{path}: {field} must not be empty")
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise CatalogError(f"{path}: invalid quoted {field}: {exc.msg}") from exc
        if not isinstance(parsed, str) or not parsed:
            raise CatalogError(f"{path}: {field} must be a non-empty string")
        return parsed
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise CatalogError(f"{path}: invalid quoted {field}")
        return value[1:-1].replace("''", "'")
    return value


def _frontmatter_lines(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise CatalogError(f"{path}: missing opening frontmatter delimiter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise CatalogError(f"{path}: missing closing frontmatter delimiter") from exc
    return lines[1:end]


def _read_skill(path: Path, repo_root: Path) -> Skill:
    name: str | None = None
    summary: str | None = None
    in_metadata = False

    for line in _frontmatter_lines(path):
        top_level = re.fullmatch(r"([a-zA-Z0-9_-]+):(?:\s*(.*))?", line)
        if top_level:
            key, value = top_level.groups()
            in_metadata = key == "metadata"
            if key == "name":
                name = _parse_scalar(value or "", path=path, field="name")
            continue

        if in_metadata:
            metadata_item = re.fullmatch(r"\s{2}([a-zA-Z0-9_-]+):\s*(.*)", line)
            if metadata_item and metadata_item.group(1) == SUMMARY_KEY:
                summary = _parse_scalar(
                    metadata_item.group(2), path=path, field=f"metadata.{SUMMARY_KEY}"
                )

    if name is None:
        raise CatalogError(f"{path}: missing name")
    if summary is None:
        raise CatalogError(f"{path}: missing metadata.{SUMMARY_KEY}")
    if name != path.parent.name:
        raise CatalogError(
            f"{path}: skill name {name!r} does not match directory {path.parent.name!r}"
        )

    readme_path = path.relative_to(repo_root).as_posix()
    return Skill(name=name, summary=summary, readme_path=readme_path)


def load_skills(repo_root: Path) -> list[Skill]:
    skill_paths = sorted((repo_root / "skills").rglob("SKILL.md"))
    if not skill_paths:
        raise CatalogError(f"{repo_root / 'skills'}: no SKILL.md files found")

    skills = [_read_skill(path, repo_root) for path in skill_paths]
    names = [skill.name for skill in skills]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise CatalogError(f"duplicate skill names: {', '.join(duplicates)}")
    return sorted(skills, key=lambda skill: skill.name)


def _escape_table_cell(value: str) -> str:
    return value.replace("|", r"\|").replace("\r", " ").replace("\n", " ")


def render_catalog(skills: list[Skill], newline: str = "\n") -> str:
    lines = [
        START_MARKER,
        "| Skill | Summary |",
        "|-------|---------|",
    ]
    lines.extend(
        f"| [{skill.name}]({skill.readme_path}) | {_escape_table_cell(skill.summary)} |"
        for skill in skills
    )
    lines.append(END_MARKER)
    return newline.join(lines)


def updated_readme(repo_root: Path) -> tuple[str, str]:
    readme_path = repo_root / "README.md"
    current = readme_path.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in current else "\n"
    pattern = re.compile(
        rf"{re.escape(START_MARKER)}.*?{re.escape(END_MARKER)}", re.DOTALL
    )
    if len(pattern.findall(current)) != 1:
        raise CatalogError(
            f"{readme_path}: expected exactly one skill catalog marker pair"
        )
    generated = pattern.sub(render_catalog(load_skills(repo_root), newline), current)
    return current, generated


def update_readme(repo_root: Path, *, check: bool) -> bool:
    current, generated = updated_readme(repo_root)
    if current.replace("\r\n", "\n") == generated.replace("\r\n", "\n"):
        return False
    if check:
        diff = difflib.unified_diff(
            current.splitlines(),
            generated.splitlines(),
            fromfile="README.md",
            tofile="README.md (generated)",
            lineterm="",
        )
        print("\n".join(diff), file=sys.stderr)
        print(
            "README skill catalog is stale; run "
            "`python scripts/update_readme_skills.py`.",
            file=sys.stderr,
        )
        return True

    (repo_root / "README.md").write_bytes(generated.encode("utf-8"))
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="fail instead of updating a stale catalog"
    )
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parent.parent
    try:
        changed = update_readme(repo_root, check=args.check)
    except (CatalogError, OSError, UnicodeError) as exc:
        print(exc, file=sys.stderr)
        return 2
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
