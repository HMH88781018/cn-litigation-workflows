#!/usr/bin/env python3
"""Compare the structural fingerprints of a DOCX baseline and candidate.

The default policy is conservative: text may change, but topology, formatting,
pagination controls, checkbox inventory, and embedded objects require explicit
approval.  Approval flags document that a category is expected; they do not
prove the change is legally or visually correct.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from docx_audit import VERSION as AUDIT_VERSION
from docx_audit import audit_docx, stable_hash


VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"


def finding(
    code: str,
    severity: str,
    path: str,
    message: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "path": path,
        "message": message,
    }
    if evidence:
        item["evidence"] = evidence
    return item


def summarize(findings: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(item["severity"] for item in findings)
    if counts["P0"]:
        status = "FAIL"
    elif counts["P1"] or counts["P2"]:
        status = "WARN"
    else:
        status = "PASS"
    return {
        "status": status,
        "P0": counts["P0"],
        "P1": counts["P1"],
        "P2": counts["P2"],
    }


def section_core(report: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for section in report["document"].get("sections", []):
        result.append(
            {
                "page": section["page"],
                "margins": section["margins"],
                "section_type": section["section_type"],
                "columns": section["columns"],
                "title_page": section["title_page"],
                "page_number": section["page_number"],
                "headers": section["headers"],
                "footers": section["footers"],
            }
        )
    return result


def table_topology_core(report: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for table in report["document"].get("tables", []):
        result.append(
            {
                "depth": table["depth"],
                "section_id": table["section_id"],
                "grid_columns_dxa": table["grid_columns_dxa"],
                "row_count": table["row_count"],
                "rows": [
                    {
                        "grid_before": row["grid_before"],
                        "grid_after": row["grid_after"],
                        "cells": [
                            {
                                "start_col": cell["start_col"],
                                "span": cell["span"],
                                "vmerge": cell["vmerge"],
                                "nested_table_count": cell["nested_table_count"],
                            }
                            for cell in row["cells"]
                        ],
                    }
                    for row in table["rows"]
                ],
            }
        )
    return result


def table_format_core(report: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for table in report["document"].get("tables", []):
        result.append(
            {
                "width": table["width"],
                "indent": table["indent"],
                "layout": table["layout"],
                "justification": table["justification"],
                "floating": table["floating"],
                "properties_hash": table["properties_hash"],
                "rows": [
                    {
                        "height": row["height"],
                        "cant_split": row["cant_split"],
                        "repeat_header": row["repeat_header"],
                        "properties_hash": row["properties_hash"],
                        "cell_properties": [cell["properties_hash"] for cell in row["cells"]],
                    }
                    for row in table["rows"]
                ],
            }
        )
    return result


def compare_reports(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    allow_topology: bool = False,
    allow_format: bool = False,
    allow_pagination: bool = False,
    allow_checkbox: bool = False,
    allow_objects: bool = False,
    allow_relationships: bool = False,
    report_text_change: bool = False,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    allowed: list[dict[str, str]] = []

    base_sections = section_core(baseline)
    cand_sections = section_core(candidate)
    if base_sections != cand_sections:
        evidence = {
            "baseline_sections": len(base_sections),
            "candidate_sections": len(cand_sections),
            "baseline_hash": stable_hash(base_sections),
            "candidate_hash": stable_hash(cand_sections),
        }
        if allow_topology:
            allowed.append({"category": "sections", "status": "explicitly_allowed"})
        else:
            findings.append(
                finding(
                    "DIF001_SECTION_STRUCTURE_CHANGED",
                    "P0",
                    "document/sections",
                    "页面、分节、页眉页脚或页码结构发生变化",
                    evidence,
                )
            )

    base_tables = table_topology_core(baseline)
    cand_tables = table_topology_core(candidate)
    if base_tables != cand_tables:
        evidence = {
            "baseline_tables": len(base_tables),
            "candidate_tables": len(cand_tables),
            "baseline_hash": stable_hash(base_tables),
            "candidate_hash": stable_hash(cand_tables),
        }
        if allow_topology:
            allowed.append({"category": "table_topology", "status": "explicitly_allowed"})
        else:
            findings.append(
                finding(
                    "DIF002_TABLE_TOPOLOGY_CHANGED",
                    "P0",
                    "document/tables",
                    "表数、网格、行列或合并关系发生变化",
                    evidence,
                )
            )

    base_format = {
        "tables": table_format_core(baseline),
        "properties": baseline["document"].get("property_inventory", {}),
    }
    cand_format = {
        "tables": table_format_core(candidate),
        "properties": candidate["document"].get("property_inventory", {}),
    }
    if base_format != cand_format:
        evidence = {
            "baseline_hash": stable_hash(base_format),
            "candidate_hash": stable_hash(cand_format),
        }
        if allow_format:
            allowed.append({"category": "format", "status": "explicitly_allowed"})
        else:
            findings.append(
                finding(
                    "DIF003_FORMAT_CHANGED",
                    "P1",
                    "document/format",
                    "表格、行、单元格、段落或文字属性发生变化",
                    evidence,
                )
            )

    base_pagination = baseline.get("hashes", {}).get("pagination")
    cand_pagination = candidate.get("hashes", {}).get("pagination")
    if base_pagination != cand_pagination:
        evidence = {"baseline_hash": base_pagination, "candidate_hash": cand_pagination}
        if allow_pagination:
            allowed.append({"category": "pagination", "status": "explicitly_allowed"})
        else:
            findings.append(
                finding(
                    "DIF004_PAGINATION_CONTROLS_CHANGED",
                    "P1",
                    "document/pagination",
                    "分页、禁止跨页、重复表头或相关控制属性发生变化",
                    evidence,
                )
            )

    base_objects = baseline["document"].get("objects", {})
    cand_objects = candidate["document"].get("objects", {})
    object_keys = (
        "drawings",
        "inline_drawings",
        "floating_drawings",
        "content_controls",
        "w14_checkboxes",
        "legacy_checkboxes",
        "docpr_ids",
        "unique_docpr_ids",
    )
    base_object_core = {key: base_objects.get(key) for key in object_keys}
    cand_object_core = {key: cand_objects.get(key) for key in object_keys}
    if base_object_core != cand_object_core:
        evidence = {"baseline": base_object_core, "candidate": cand_object_core}
        if allow_objects:
            allowed.append({"category": "objects", "status": "explicitly_allowed"})
        else:
            findings.append(
                finding(
                    "DIF005_OBJECT_INVENTORY_CHANGED",
                    "P1",
                    "document/objects",
                    "绘图、控件或相关对象数量发生变化",
                    evidence,
                )
            )

    base_checkbox = baseline.get("hashes", {}).get("checkbox_inventory")
    cand_checkbox = candidate.get("hashes", {}).get("checkbox_inventory")
    if base_checkbox != cand_checkbox:
        evidence = {
            "baseline_hash": base_checkbox,
            "candidate_hash": cand_checkbox,
            "baseline_characters": base_objects.get("checkbox_characters", {}),
            "candidate_characters": cand_objects.get("checkbox_characters", {}),
        }
        if allow_checkbox:
            allowed.append({"category": "checkbox", "status": "explicitly_allowed"})
        else:
            findings.append(
                finding(
                    "DIF006_CHECKBOX_INVENTORY_CHANGED",
                    "P1",
                    "document/checkboxes",
                    "勾选对象或方框字符盘点发生变化，须与真值表核对",
                    evidence,
                )
            )

    base_relationships = baseline.get("package", {}).get("relationships_hash")
    cand_relationships = candidate.get("package", {}).get("relationships_hash")
    if base_relationships != cand_relationships:
        evidence = {
            "baseline_hash": base_relationships,
            "candidate_hash": cand_relationships,
        }
        if allow_relationships:
            allowed.append({"category": "relationships", "status": "explicitly_allowed"})
        else:
            findings.append(
                finding(
                    "DIF007_RELATIONSHIPS_CHANGED",
                    "P1",
                    "package/relationships",
                    "图片、页眉页脚、超链接或其他关系目标发生变化",
                    evidence,
                )
            )

    base_content = baseline.get("hashes", {}).get("content")
    cand_content = candidate.get("hashes", {}).get("content")
    content_changed = base_content != cand_content
    if content_changed and report_text_change:
        findings.append(
            finding(
                "DIF008_TEXT_CHANGED",
                "P2",
                "document/text",
                "正文文字发生变化；请与字段或点改白名单核对",
                {
                    "baseline_hash": base_content,
                    "candidate_hash": cand_content,
                    "baseline_characters": baseline["document"].get("text", {}).get("characters"),
                    "candidate_characters": candidate["document"].get("text", {}).get("characters"),
                },
            )
        )

    severity_order = {"P0": 0, "P1": 1, "P2": 2}
    findings.sort(
        key=lambda item: (
            severity_order.get(item["severity"], 9),
            item["code"],
            item["path"],
        )
    )
    allowed.sort(key=lambda item: item["category"])

    report = {
        "schema_version": SCHEMA_VERSION,
        "tool": {
            "name": "docx_diff",
            "version": VERSION,
            "audit_version": AUDIT_VERSION,
        },
        "baseline": {
            "filename": baseline["source"]["filename"],
            "sha256": baseline["source"]["sha256"],
            "audit_summary": baseline.get("summary", {}),
            "hashes": baseline.get("hashes", {}),
        },
        "candidate": {
            "filename": candidate["source"]["filename"],
            "sha256": candidate["source"]["sha256"],
            "audit_summary": candidate.get("summary", {}),
            "hashes": candidate.get("hashes", {}),
        },
        "content_changed": content_changed,
        "allowed_categories": allowed,
        "findings": findings,
        "summary": summarize(findings),
    }
    return report


def should_fail(report: dict[str, Any], threshold: str) -> bool:
    if threshold == "none":
        return False
    rank = {"P0": 0, "P1": 1, "P2": 2}
    limit = rank[threshold]
    return any(rank.get(item["severity"], 99) <= limit for item in report["findings"])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare DOCX structure, format, pagination, checkboxes, and relationships"
    )
    parser.add_argument("baseline", type=Path, help="locked mother template or point-edit baseline")
    parser.add_argument("candidate", type=Path, help="candidate DOCX")
    parser.add_argument("--json", type=Path, dest="json_path", help="write JSON report")
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON")
    parser.add_argument("--allow-topology-change", action="store_true")
    parser.add_argument("--allow-format-change", action="store_true")
    parser.add_argument("--allow-pagination-change", action="store_true")
    parser.add_argument("--allow-checkbox-change", action="store_true")
    parser.add_argument("--allow-object-change", action="store_true")
    parser.add_argument("--allow-relationship-change", action="store_true")
    parser.add_argument(
        "--report-text-change",
        action="store_true",
        help="add a P2 finding when extracted text differs",
    )
    parser.add_argument(
        "--fail-on",
        choices=("P0", "P1", "P2", "none"),
        default="P1",
        help="return exit code 2 when this severity or higher is present",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    for path in (args.baseline, args.candidate):
        if not path.is_file():
            print(f"Input file not found: {path}", file=sys.stderr)
            return 3
    try:
        baseline = audit_docx(args.baseline)
        candidate = audit_docx(args.candidate)
        if not baseline.get("document") or not candidate.get("document"):
            print("Unable to compare: one input could not be audited", file=sys.stderr)
            return 4
        report = compare_reports(
            baseline,
            candidate,
            allow_topology=args.allow_topology_change,
            allow_format=args.allow_format_change,
            allow_pagination=args.allow_pagination_change,
            allow_checkbox=args.allow_checkbox_change,
            allow_objects=args.allow_object_change,
            allow_relationships=args.allow_relationship_change,
            report_text_change=args.report_text_change,
        )
    except Exception as exc:
        print(f"Comparison failed: {exc}", file=sys.stderr)
        return 4

    indent = 2 if args.pretty else None
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=indent)
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 2 if should_fail(report, args.fail_on) else 0


if __name__ == "__main__":
    raise SystemExit(main())
