from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from scripts.update_readme_skills import CatalogError, update_readme


README_TEMPLATE = """# Skills

<!-- skills:start -->
stale
<!-- skills:end -->
"""


def write_skill(
    root: Path,
    name: str,
    summary: str | None,
    *,
    author: str | None = "scarletkc",
    source: str | None = "https://github.com/scarletkc/agents",
) -> None:
    metadata_lines = ["metadata:"]
    if author is not None:
        metadata_lines.append(f"  author: {author}")
    if source is not None:
        metadata_lines.append(f"  source: {source}")
    if summary is not None:
        metadata_lines.append(f'  summary: "{summary}"')
    metadata = "\n".join(metadata_lines)
    path = root / "skills" / name / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        f"---\nname: {name}\ndescription: Test skill.\n{metadata}\n---\n",
        encoding="utf-8",
    )


class UpdateReadmeSkillsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "README.md").write_text(README_TEMPLATE, encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_updates_catalog_from_metadata_in_name_order(self) -> None:
        write_skill(self.root, "zulu", "Last skill.")
        write_skill(self.root, "alpha", "First skill.")

        self.assertTrue(update_readme(self.root, check=False))

        readme = (self.root / "README.md").read_text(encoding="utf-8")
        self.assertLess(readme.index("[alpha]"), readme.index("[zulu]"))
        self.assertIn("| [alpha](skills/alpha/SKILL.md) | First skill. |", readme)
        self.assertFalse(update_readme(self.root, check=True))

    def test_check_reports_stale_catalog_without_writing(self) -> None:
        write_skill(self.root, "alpha", "First skill.")

        with redirect_stderr(io.StringIO()):
            self.assertTrue(update_readme(self.root, check=True))
        self.assertEqual(
            (self.root / "README.md").read_text(encoding="utf-8"), README_TEMPLATE
        )

    def test_check_ignores_line_ending_differences(self) -> None:
        write_skill(self.root, "alpha", "First skill.")
        update_readme(self.root, check=False)
        readme_path = self.root / "README.md"
        content = readme_path.read_bytes().replace(b"\r\n", b"\n")
        readme_path.write_bytes(content.replace(b"\n", b"\r\n"))

        self.assertFalse(update_readme(self.root, check=True))

    def test_rejects_skill_without_summary(self) -> None:
        write_skill(self.root, "alpha", None)

        with self.assertRaisesRegex(CatalogError, "missing metadata.summary"):
            update_readme(self.root, check=False)

    def test_rejects_skill_without_canonical_source(self) -> None:
        write_skill(self.root, "alpha", "First skill.", source=None)

        with self.assertRaisesRegex(CatalogError, "missing metadata.source"):
            update_readme(self.root, check=False)

    def test_rejects_skill_without_author(self) -> None:
        write_skill(self.root, "alpha", "First skill.", author=None)

        with self.assertRaisesRegex(CatalogError, "missing metadata.author"):
            update_readme(self.root, check=False)


if __name__ == "__main__":
    unittest.main()
