from __future__ import annotations

import datetime as dt
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cn_litigation_workflows.validator import (  # noqa: E402
    _scan_text,
    _validate_office_metadata,
    _validate_version_files,
    validate_project,
)


class ProjectValidationTests(unittest.TestCase):
    def test_repository_has_no_validation_errors(self) -> None:
        issues = validate_project(ROOT, today=dt.date(2026, 7, 29))
        errors = [item for item in issues if item.severity == "ERROR"]
        self.assertEqual([], errors, "\n".join(str(item) for item in errors))

    def test_source_registry_becomes_stale(self) -> None:
        issues = validate_project(ROOT, today=dt.date(2026, 9, 1))
        codes = {item.code for item in issues}
        self.assertIn("SOURCE_STALE", codes)

    def test_sensitive_number_detection(self) -> None:
        issues = []
        path = Path("synthetic-leak.txt")
        synthetic_number = "138" + "0013" + "8000"
        _scan_text(path, f"当事人手机：{synthetic_number}", issues)
        self.assertIn("SENSITIVE_PHONE_CN", {item.code for item in issues})

    def test_official_url_digits_are_not_phone_data(self) -> None:
        issues = []
        path = Path("source.md")
        _scan_text(
            path,
            "https://example.invalid/archive/2021/01/18163755568.html",
            issues,
        )
        self.assertNotIn("SENSITIVE_PHONE_CN", {item.code for item in issues})

    def test_validator_does_not_modify_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            marker = Path(temp_dir) / "marker"
            marker.write_text("unchanged", encoding="utf-8")
            validate_project(ROOT, today=dt.date(2026, 7, 29))
            self.assertEqual("unchanged", marker.read_text(encoding="utf-8"))

    def test_pyproject_version_must_match_project_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "CHANGELOG.md").write_text(
                "## [0.1.1]\n",
                encoding="utf-8",
            )
            (root / "CITATION.cff").write_text(
                'version: "0.1.1"\n',
                encoding="utf-8",
            )
            (root / "pyproject.toml").write_text(
                '[project]\nname = "example"\nversion = "9.9.9"\n',
                encoding="utf-8",
            )
            issues = []
            _validate_version_files(root, issues)
            self.assertIn("PYPROJECT_VERSION", {item.code for item in issues})

    def test_external_office_relationship_is_blocked_without_target_leak(self) -> None:
        relationship_target = (
            "https://example.invalid/client?token=SYNTHETIC-REL-SECRET"
        )
        relationships = f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
    Target="{relationship_target}" TargetMode="External"/>
</Relationships>
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workbook = root / "synthetic.xlsx"
            with zipfile.ZipFile(workbook, "w") as archive:
                archive.writestr(
                    "xl/worksheets/_rels/sheet1.xml.rels",
                    relationships,
                )
            issues = []
            _validate_office_metadata(root, issues)

        self.assertIn("OFFICE_EXTERNAL_REL", {item.code for item in issues})
        serialized = "\n".join(str(item) for item in issues)
        self.assertNotIn(relationship_target, serialized)
        self.assertNotIn("SYNTHETIC-REL-SECRET", serialized)


if __name__ == "__main__":
    unittest.main()
