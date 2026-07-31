from __future__ import annotations

import datetime as dt
import posixpath
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cn_litigation_workflows.release import (  # noqa: E402
    _is_generated,
    build_archive,
    build_submission_archive,
)
from cn_litigation_workflows.validator import (  # noqa: E402
    _relative_links,
    validate_project,
)


class ReleaseArchiveTests(unittest.TestCase):
    def test_generated_and_private_paths_are_excluded(self) -> None:
        for value in (
            ".git/config",
            "build/package.bin",
            "dist/release.zip",
            "outputs/report.json",
            "tests/__pycache__/test_release.pyc",
            "src/example.egg-info/PKG-INFO",
            "draft.docx.audit.json",
        ):
            with self.subTest(value=value):
                self.assertTrue(_is_generated(Path(value)))
        self.assertFalse(_is_generated(Path(".github/workflows/ci.yml")))

    def test_archive_is_deterministic_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first.zip"
            second = Path(temp_dir) / "second.zip"
            build_archive(ROOT, first)
            build_archive(ROOT, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                names = archive.namelist()
            self.assertIn(".codex-plugin/plugin.json", names)
            self.assertIn(".agents/plugins/marketplace.json", names)
            self.assertIn(".github/workflows/ci.yml", names)
            self.assertIn("AGENTS.md", names)
            self.assertIn("CONTRIBUTING.md", names)
            self.assertIn("GOVERNANCE.md", names)
            self.assertIn("evals/cases.json", names)
            self.assertIn("examples/synthetic-damages-input.json", names)
            self.assertIn("pyproject.toml", names)
            self.assertIn("scripts/run_evals.py", names)
            self.assertIn("src/cn_litigation_workflows/eval_harness.py", names)
            self.assertIn("tests/test_eval_harness.py", names)
            self.assertIn("skills/draft-cn-element-complaints/SKILL.md", names)
            self.assertIn("skills/prepare-cn-evidence-damages/SKILL.md", names)
            self.assertIn("PRIVACY.md", names)
            self.assertIn("README.zh-CN.md", names)
            self.assertIn("docs/legal-source-policy.md", names)
            self.assertFalse(any(name.startswith("../") for name in names))
            self.assertFalse(any(".git/" in name or name.startswith(".git/") for name in names))
            self.assertFalse(any("__pycache__" in name for name in names))
            self.assertFalse(any(name.startswith(("build/", "dist/", "outputs/")) for name in names))

            with zipfile.ZipFile(first) as archive:
                archive_names = set(archive.namelist())
                for name in sorted(item for item in archive_names if item.endswith(".md")):
                    markdown = archive.read(name).decode("utf-8")
                    for target in _relative_links(markdown):
                        candidate = posixpath.normpath(
                            posixpath.join(posixpath.dirname(name), target)
                        )
                        self.assertIn(
                            candidate,
                            archive_names,
                            f"{name} links to missing archive member {target}",
                        )

                extract_root = Path(temp_dir) / "arbitrary-extraction-folder"
                archive.extractall(extract_root)
            errors = [
                item
                for item in validate_project(
                    extract_root,
                    today=dt.date(2026, 7, 29),
                )
                if item.severity == "ERROR"
            ]
            self.assertEqual([], errors, "\n".join(str(item) for item in errors))

    def test_submission_archive_is_minimal_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "submission-first.zip"
            second = Path(temp_dir) / "submission-second.zip"
            build_submission_archive(ROOT, first)
            build_submission_archive(ROOT, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())

            with zipfile.ZipFile(first) as archive:
                names = set(archive.namelist())
            for required in (
                ".codex-plugin/plugin.json",
                "LICENSE",
                "NOTICE",
                "THIRD_PARTY_NOTICES.md",
                "assets/composer-icon.png",
                "assets/logo.png",
                "skills/draft-cn-element-complaints/SKILL.md",
                "skills/prepare-cn-evidence-damages/SKILL.md",
            ):
                self.assertIn(required, names)
            self.assertFalse(
                any(
                    name.startswith(
                        (
                            ".agents/",
                            ".github/",
                            "docs/",
                            "evals/",
                            "examples/",
                            "scripts/",
                            "src/",
                            "submission/",
                            "tests/",
                        )
                    )
                    for name in names
                )
            )
            self.assertNotIn("pyproject.toml", names)
            self.assertFalse(any("__pycache__" in name for name in names))
            self.assertFalse(any(name.endswith((".pyc", ".docx")) for name in names))


if __name__ == "__main__":
    unittest.main()
