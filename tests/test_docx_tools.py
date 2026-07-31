from __future__ import annotations

import io
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr
from hashlib import sha256
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
DOCX_TOOLS = ROOT / "skills" / "draft-cn-element-complaints" / "scripts"
sys.path.insert(0, str(DOCX_TOOLS))

import docx_audit  # noqa: E402
from docx_audit import audit_docx  # noqa: E402
from docx_diff import compare_reports  # noqa: E402


DOCUMENT_TEMPLATE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
    <w:tbl>
      <w:tblPr><w:tblW w:w="9000" w:type="dxa"/></w:tblPr>
      <w:tblGrid><w:gridCol w:w="4500"/><w:gridCol w:w="4500"/></w:tblGrid>
      <w:tr>
        <w:tc><w:tcPr><w:tcW w:w="4500" w:type="dxa"/></w:tcPr><w:p><w:r><w:t>字段</w:t></w:r></w:p></w:tc>
        <w:tc><w:tcPr><w:tcW w:w="4500" w:type="dxa"/></w:tcPr><w:p><w:r><w:t>值</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>
    </w:sectPr>
  </w:body>
</w:document>
"""

EMPTY_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>
"""

EXTERNAL_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId9"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
    Target="{target}" TargetMode="External"/>
</Relationships>
"""


def make_docx(
    path: Path,
    text: str,
    *,
    relationships: str = EMPTY_RELS,
    extra_relationship_parts: dict[str, str] | None = None,
    document_xml: str | None = None,
) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "word/document.xml",
            document_xml if document_xml is not None else DOCUMENT_TEMPLATE.format(text=text),
        )
        archive.writestr("word/_rels/document.xml.rels", relationships)
        for rel_path, rel_xml in (extra_relationship_parts or {}).items():
            archive.writestr(rel_path, rel_xml)


def compare(baseline: dict, candidate: dict, *, report_text: bool) -> dict:
    return compare_reports(
        baseline,
        candidate,
        allow_topology=False,
        allow_format=False,
        allow_pagination=False,
        allow_checkbox=False,
        allow_objects=False,
        allow_relationships=False,
        report_text_change=report_text,
    )


class DocxToolTests(unittest.TestCase):
    def test_audit_is_privacy_preserving_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.docx"
            make_docx(path, "SYNTHETIC-SECRET")
            report = audit_docx(path)
            self.assertNotIn("SYNTHETIC-SECRET", str(report))
            self.assertNotIn("sample.docx", str(report))
            self.assertEqual("<redacted>", report["source"]["filename"])
            self.assertEqual(
                sha256(b"sample.docx").hexdigest(),
                report["source"]["filename_sha256"],
            )
            self.assertNotEqual("FAIL", report["summary"]["status"])

    def test_sensitive_metadata_requires_explicit_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "client-name.docx"
            target = "https://example.invalid/download?token=SYNTHETIC-TOKEN"
            make_docx(
                path,
                "正文",
                relationships=EXTERNAL_RELS.format(target=target),
            )

            report = audit_docx(path)
            serialized = str(report)
            self.assertNotIn("client-name.docx", serialized)
            self.assertNotIn(target, serialized)
            self.assertNotIn("SYNTHETIC-TOKEN", serialized)
            relationship = report["package"]["relationships"][0]
            self.assertEqual(sha256(target.encode()).hexdigest(), relationship["target_sha256"])
            self.assertNotIn("target", relationship)
            self.assertEqual(
                {"REL003_EXTERNAL_TARGET"},
                {item["code"] for item in report["findings"]},
            )
            self.assertEqual(
                1,
                sum(
                    item["code"] == "REL003_EXTERNAL_TARGET"
                    for item in report["findings"]
                ),
            )
            self.assertEqual("WARN", report["summary"]["status"])

            opted_in = audit_docx(path, include_sensitive_metadata=True)
            self.assertEqual("client-name.docx", opted_in["source"]["filename"])
            self.assertEqual(
                target,
                opted_in["package"]["relationships"][0]["target"],
            )
            self.assertEqual(
                report["package"]["relationships_hash"],
                opted_in["package"]["relationships_hash"],
            )

    def test_internal_relationship_targets_are_hashed_and_affect_diff_hash(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = Path(temp_dir) / "first.docx"
            second_path = Path(temp_dir) / "second.docx"
            first_rels = EXTERNAL_RELS.format(target="document.xml").replace(
                'TargetMode="External"',
                'TargetMode="Internal"',
            )
            second_rels = EXTERNAL_RELS.format(target="./document.xml").replace(
                'TargetMode="External"',
                'TargetMode="Internal"',
            )
            make_docx(first_path, "正文", relationships=first_rels)
            make_docx(second_path, "正文", relationships=second_rels)

            first = audit_docx(first_path)
            second = audit_docx(second_path)
            first_relationship = first["package"]["relationships"][0]
            second_relationship = second["package"]["relationships"][0]

            self.assertNotIn("target", first_relationship)
            self.assertNotIn("target", second_relationship)
            self.assertEqual(
                sha256(b"document.xml").hexdigest(),
                first_relationship["target_sha256"],
            )
            self.assertEqual(
                sha256(b"./document.xml").hexdigest(),
                second_relationship["target_sha256"],
            )
            self.assertNotEqual(
                first["package"]["relationships_hash"],
                second["package"]["relationships_hash"],
            )
            self.assertEqual("PASS", first["summary"]["status"])
            self.assertEqual("PASS", second["summary"]["status"])

    def test_external_targets_in_all_relationship_parts_are_detected_and_redacted(
        self,
    ) -> None:
        cases = {
            "package": ("_rels/.rels", "relative-target", "External"),
            "header": ("word/_rels/header1.xml.rels", "https://example.invalid/SYNTHETIC-HEADER-TOKEN", "Internal"),
            "footer": ("word/_rels/footer1.xml.rels", r"\\server\share\SYNTHETIC-FOOTER-TOKEN", "Internal"),
            "footnotes": ("word/_rels/footnotes.xml.rels", "file:synthetic/SYNTHETIC-FOOTNOTE-TOKEN", "Internal"),
            "comments": ("word/_rels/comments.xml.rels", r"C:\cases\SYNTHETIC-COMMENT-TOKEN", "Internal"),
            "embedded-object": (
                "word/embeddings/_rels/oleObject1.bin.rels",
                "mailto:SYNTHETIC-EMBEDDED-TOKEN@example.invalid",
                "Internal",
            ),
            "absolute-file": (
                "word/_rels/settings.xml.rels",
                "/" + "srv/SYNTHETIC-ABSOLUTE-FILE-TOKEN",
                "Internal",
            ),
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            for name, (rel_path, target, mode) in cases.items():
                with self.subTest(name=name):
                    path = Path(temp_dir) / f"{name}.docx"
                    relationships = EXTERNAL_RELS.format(target=target).replace(
                        'TargetMode="External"',
                        f'TargetMode="{mode}"',
                    )
                    make_docx(
                        path,
                        "正文",
                        extra_relationship_parts={rel_path: relationships},
                    )
                    report = audit_docx(path)
                    serialized = str(report)
                    external_findings = [
                        item
                        for item in report["findings"]
                        if item["code"] == "REL003_EXTERNAL_TARGET"
                    ]
                    self.assertEqual(1, len(external_findings))
                    self.assertEqual("WARN", report["summary"]["status"])
                    self.assertNotIn(target, serialized)
                    self.assertNotIn("SYNTHETIC-", serialized)
                    self.assertNotIn(rel_path, serialized)
                    self.assertEqual(
                        sha256(target.encode()).hexdigest(),
                        external_findings[0]["evidence"]["target_sha256"],
                    )
                    self.assertIn(
                        sha256(rel_path.encode()).hexdigest(),
                        serialized,
                    )

    def test_missing_input_path_is_redacted_without_explicit_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "SYNTHETIC-CLIENT-NAME.docx"
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                exit_code = docx_audit.main([str(path)])
            diagnostic = stderr.getvalue()
            self.assertEqual(3, exit_code)
            self.assertNotIn(str(path), diagnostic)
            self.assertNotIn("SYNTHETIC-CLIENT-NAME", diagnostic)
            self.assertIn(
                sha256(str(path).encode()).hexdigest(),
                diagnostic,
            )

            stderr = io.StringIO()
            with redirect_stderr(stderr):
                exit_code = docx_audit.main(
                    [str(path), "--include-sensitive-metadata"]
                )
            self.assertEqual(3, exit_code)
            self.assertIn(str(path), stderr.getvalue())

    def test_archive_resource_limits_fail_closed(self) -> None:
        cases = (
            ("MAX_ARCHIVE_BYTES", 1, "PKG007_ARCHIVE_TOO_LARGE"),
            ("MAX_ARCHIVE_MEMBERS", 1, "PKG008_TOO_MANY_MEMBERS"),
            ("MAX_TOTAL_UNCOMPRESSED_BYTES", 1, "PKG009_TOTAL_UNCOMPRESSED_TOO_LARGE"),
            ("MAX_MEMBER_UNCOMPRESSED_BYTES", 1, "PKG012_MEMBER_TOO_LARGE"),
            ("MAX_COMPRESSION_RATIO", 1, "PKG015_COMPRESSION_RATIO_TOO_HIGH"),
            ("MAX_XML_BYTES", 1, "PKG016_XML_TOO_LARGE"),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "limits.docx"
            make_docx(path, "重复内容" * 100)
            for constant, limit, expected_code in cases:
                with self.subTest(constant=constant):
                    with mock.patch.object(docx_audit, constant, limit):
                        report = audit_docx(path)
                    self.assertEqual("FAIL", report["summary"]["status"])
                    self.assertIn(
                        expected_code,
                        {item["code"] for item in report["findings"]},
                    )

    def test_unsafe_xml_declarations_fail_closed(self) -> None:
        samples = {
            "doctype": "<!DOCTYPE w:document>" + DOCUMENT_TEMPLATE.format(text="正文"),
            "entity": "<!-- <!ENTITY synthetic 'value'> -->"
            + DOCUMENT_TEMPLATE.format(text="正文"),
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            for name, document_xml in samples.items():
                with self.subTest(name=name):
                    path = Path(temp_dir) / f"{name}.docx"
                    make_docx(path, "unused", document_xml=document_xml)
                    report = audit_docx(path)
                    self.assertEqual("FAIL", report["summary"]["status"])
                    self.assertIn(
                        "PKG013_UNSAFE_XML_DECLARATION",
                        {item["code"] for item in report["findings"]},
                    )

    def test_source_hashing_does_not_read_entire_file_at_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "streamed.docx"
            make_docx(path, "正文")
            with mock.patch.object(
                Path,
                "read_bytes",
                side_effect=AssertionError("whole-file read is forbidden"),
            ):
                report = audit_docx(path)
            self.assertNotEqual("FAIL", report["summary"]["status"])

    def test_revision_finding_has_one_well_formed_entry(self) -> None:
        revision = (
            '<w:ins w:id="1" w:author="Synthetic">'
            "<w:r><w:t>修订文字</w:t></w:r>"
            "</w:ins>"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "revision.docx"
            make_docx(path, "unused", document_xml=DOCUMENT_TEMPLATE.format(text=revision))
            report = audit_docx(path)
            revision_findings = [
                item
                for item in report["findings"]
                if item["code"] == "DOC002_UNRESOLVED_REVISIONS"
            ]
            self.assertEqual(1, len(revision_findings))
            self.assertEqual("document/revisions", revision_findings[0]["path"])
            self.assertEqual({"count": 1}, revision_findings[0]["evidence"])

    def test_identical_docx_has_no_diff(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.docx"
            make_docx(path, "相同文字")
            report = audit_docx(path)
            diff = compare(report, report, report_text=True)
            self.assertFalse(diff["content_changed"])
            self.assertEqual("PASS", diff["summary"]["status"])

    def test_text_only_change_does_not_become_topology_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            baseline_path = Path(temp_dir) / "baseline.docx"
            candidate_path = Path(temp_dir) / "candidate.docx"
            make_docx(baseline_path, "修改前")
            make_docx(candidate_path, "修改后")
            diff = compare(
                audit_docx(baseline_path),
                audit_docx(candidate_path),
                report_text=True,
            )
            self.assertTrue(diff["content_changed"])
            self.assertEqual(
                {"DIF008_TEXT_CHANGED"},
                {item["code"] for item in diff["findings"]},
            )

    def test_invalid_package_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "broken.docx"
            path.write_text("not a zip", encoding="utf-8")
            report = audit_docx(path)
            self.assertEqual("FAIL", report["summary"]["status"])
            self.assertIn(
                "PKG001_INVALID_ZIP",
                {item["code"] for item in report["findings"]},
            )


if __name__ == "__main__":
    unittest.main()
