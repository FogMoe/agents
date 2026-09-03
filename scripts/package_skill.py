#!/usr/bin/env python3
"""Package one repository skill as an upload-ready ZIP archive."""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path


SKILL_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
EXCLUDED_DIRS = {".git", "__pycache__", "node_modules"}
ROOT_EXCLUDED_DIRS = {"evals"}
EXCLUDED_FILES = {".DS_Store", "Thumbs.db"}
EXCLUDED_GLOBS = {"*.pyc", "*.pyo"}
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


class PackageError(ValueError):
    """Raised when a skill cannot be packaged safely."""


def _should_exclude(relative_path: Path) -> bool:
    if relative_path.parts and relative_path.parts[0] in ROOT_EXCLUDED_DIRS:
        return True
    if any(part in EXCLUDED_DIRS for part in relative_path.parts):
        return True
    if relative_path.name in EXCLUDED_FILES:
        return True
    return any(fnmatch.fnmatch(relative_path.name, pattern) for pattern in EXCLUDED_GLOBS)


def _skill_files(skill_path: Path) -> list[tuple[Path, Path]]:
    files: list[tuple[Path, Path]] = []
    for path in skill_path.rglob("*"):
        relative_path = path.relative_to(skill_path)
        if _should_exclude(relative_path):
            continue
        if path.is_symlink():
            raise PackageError(f"{path}: symbolic links are not supported")
        if path.is_file():
            files.append((relative_path, path))
    return sorted(files, key=lambda item: item[0].as_posix())


def _write_file(archive: zipfile.ZipFile, relative_path: Path, source: Path) -> None:
    info = zipfile.ZipInfo(relative_path.as_posix(), ZIP_TIMESTAMP)
    info.create_system = 3
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    with source.open("rb") as input_file, archive.open(info, "w") as output_file:
        shutil.copyfileobj(input_file, output_file)


def package_skill(repo_root: Path, skill_name: str, output_dir: Path) -> Path:
    """Package ``skills/<skill_name>`` with its contents at the archive root."""
    if SKILL_NAME.fullmatch(skill_name) is None:
        raise PackageError(
            "skill name must contain only lowercase letters, numbers, and single hyphens"
        )

    repo_root = repo_root.resolve()
    skill_path = (repo_root / "skills" / skill_name).resolve()
    skills_root = (repo_root / "skills").resolve()
    if skill_path.parent != skills_root:
        raise PackageError(f"{skill_name!r}: skill must be a direct child of {skills_root}")
    if not skill_path.is_dir():
        raise PackageError(f"{skill_path}: skill directory does not exist")
    if not (skill_path / "SKILL.md").is_file():
        raise PackageError(f"{skill_path}: SKILL.md is missing")

    output_dir = output_dir.resolve()
    if output_dir == skill_path or skill_path in output_dir.parents:
        raise PackageError(f"{output_dir}: output directory must be outside the skill")

    files = _skill_files(skill_path)
    if Path("SKILL.md") not in {relative_path for relative_path, _ in files}:
        raise PackageError(f"{skill_path}: SKILL.md cannot be packaged")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{skill_name}.zip"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=output_dir, prefix=f".{skill_name}-", suffix=".zip", delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
        with zipfile.ZipFile(temporary_path, "w") as archive:
            for relative_path, source in files:
                _write_file(archive, relative_path, source)
        os.replace(temporary_path, output_path)
    except (OSError, zipfile.BadZipFile) as exc:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise PackageError(f"could not create {output_path}: {exc}") from exc
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill", help="name of a directory under skills/")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="archive destination (default: dist/ in the repository)",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent
    output_dir = args.output_dir or repo_root / "dist"
    try:
        output_path = package_skill(repo_root, args.skill, output_dir)
    except (PackageError, OSError) as exc:
        parser.error(str(exc))
    print(f"Packaged {args.skill} to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
