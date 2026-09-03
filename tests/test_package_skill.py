from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.package_skill import PackageError, package_skill


class PackageSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.skill = self.root / "skills" / "example-skill"
        self.skill.mkdir(parents=True)
        (self.skill / "SKILL.md").write_text(
            "---\nname: example-skill\n---\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_packages_skill_contents_at_archive_root(self) -> None:
        (self.skill / "references").mkdir()
        (self.skill / "references" / "guide.md").write_text(
            "Guide", encoding="utf-8"
        )

        output = package_skill(self.root, "example-skill", self.root / "dist")

        with zipfile.ZipFile(output) as archive:
            self.assertEqual(archive.namelist(), ["SKILL.md", "references/guide.md"])
            self.assertEqual(archive.read("references/guide.md"), b"Guide")
            self.assertNotIn("example-skill/SKILL.md", archive.namelist())

    def test_excludes_development_artifacts(self) -> None:
        (self.skill / "evals").mkdir()
        (self.skill / "evals" / "evals.json").write_text("{}", encoding="utf-8")
        (self.skill / "scripts" / "__pycache__").mkdir(parents=True)
        (self.skill / "scripts" / "__pycache__" / "helper.pyc").write_bytes(b"cache")
        (self.skill / "Thumbs.db").write_bytes(b"cache")

        output = package_skill(self.root, "example-skill", self.root / "dist")

        with zipfile.ZipFile(output) as archive:
            self.assertEqual(archive.namelist(), ["SKILL.md"])

    def test_repeated_packages_are_identical(self) -> None:
        output = package_skill(self.root, "example-skill", self.root / "dist")
        first = output.read_bytes()

        output = package_skill(self.root, "example-skill", self.root / "dist")

        self.assertEqual(output.read_bytes(), first)

    def test_rejects_invalid_skill_name(self) -> None:
        with self.assertRaisesRegex(PackageError, "skill name must contain"):
            package_skill(self.root, "../example-skill", self.root / "dist")

    def test_rejects_missing_skill_directory(self) -> None:
        with self.assertRaisesRegex(PackageError, "skill directory does not exist"):
            package_skill(self.root, "missing", self.root / "dist")

    def test_rejects_missing_skill_file(self) -> None:
        (self.skill / "SKILL.md").unlink()

        with self.assertRaisesRegex(PackageError, "SKILL.md is missing"):
            package_skill(self.root, "example-skill", self.root / "dist")

    def test_rejects_output_inside_skill(self) -> None:
        with self.assertRaisesRegex(PackageError, "must be outside the skill"):
            package_skill(self.root, "example-skill", self.skill / "dist")


if __name__ == "__main__":
    unittest.main()
