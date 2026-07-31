from __future__ import annotations

import sys
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cn_litigation_workflows.validator import (  # noqa: E402
    EXPECTED_WORKBOOK_SHEETS,
)


class WorkbookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = (
            ROOT
            / "skills"
            / "prepare-cn-evidence-damages"
            / "assets"
            / "traffic-accident-compensation-template.xlsx"
        )

    def test_workbook_structure_and_formula_density(self) -> None:
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        with zipfile.ZipFile(self.path) as archive:
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            sheet_names = [
                item.attrib["name"]
                for item in workbook.findall(".//m:sheet", ns)
            ]
            formulas = 0
            for member in archive.namelist():
                if member.startswith("xl/worksheets/sheet") and member.endswith(".xml"):
                    sheet = ET.fromstring(archive.read(member))
                    formulas += len(sheet.findall(".//m:f", ns))
        self.assertEqual(EXPECTED_WORKBOOK_SHEETS, sheet_names)
        self.assertGreaterEqual(formulas, 500)

    def test_workbook_has_no_author_or_external_link_parts(self) -> None:
        rel_ns = {
            "r": "http://schemas.openxmlformats.org/package/2006/relationships"
        }
        with zipfile.ZipFile(self.path) as archive:
            names = set(archive.namelist())
            external_relationships = []
            for member in names:
                if not member.endswith(".rels"):
                    continue
                relationships = ET.fromstring(archive.read(member))
                for relationship in relationships.findall("r:Relationship", rel_ns):
                    target = relationship.attrib.get("Target", "")
                    target_mode = relationship.attrib.get("TargetMode", "")
                    if target_mode.lower() == "external" or target.lower().startswith(
                        ("file:", "http:", "https:", "\\\\")
                    ):
                        external_relationships.append(member)
        self.assertNotIn("docProps/core.xml", names)
        self.assertFalse(any(name.startswith("xl/externalLinks/") for name in names))
        self.assertEqual([], external_relationships)

    def test_release_gate_formulas_fail_closed(self) -> None:
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        with zipfile.ZipFile(self.path) as archive:
            alarm_sheet = ET.fromstring(
                archive.read("xl/worksheets/sheet9.xml")
            )
            formulas = {
                cell.attrib["r"]: cell.findtext("m:f", default="", namespaces=ns)
                for cell in alarm_sheet.findall(".//m:c", ns)
            }
            insurance_sheet = ET.fromstring(
                archive.read("xl/worksheets/sheet5.xml")
            )
            insurance_formulas = {
                cell.attrib["r"]: cell.findtext("m:f", default="", namespaces=ns)
                for cell in insurance_sheet.findall(".//m:c", ns)
            }

        self.assertIn("'07_法源参数'!H12", formulas["B10"])
        self.assertIn("'07_法源参数'!I12<>\"已核验\"", formulas["B10"])
        self.assertIn("'07_法源参数'!E18", formulas["B12"])
        self.assertNotIn("DATE(2020,9,19)", formulas["B12"])
        self.assertIn("SUMPRODUCT", formulas["B19"])
        self.assertIn("'02_赔偿项目'!A5:A26", formulas["B19"])
        self.assertIn("'06_证据映射'!D5:D34", formulas["B19"])
        self.assertTrue(insurance_formulas["B24"].startswith("IF("))
        self.assertTrue(insurance_formulas["B28"].startswith("IF("))


if __name__ == "__main__":
    unittest.main()
