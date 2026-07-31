#!/usr/bin/env python3
"""Deterministic structural audit for legal-template DOCX files.

The script is intentionally read-only.  It inspects the OOXML package, builds a
privacy-preserving fingerprint, and reports structural risks.  It does not
decide whether a legal document is substantively correct and never repairs the
input file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from xml.etree import ElementTree as ET


VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"

HASH_CHUNK_SIZE = 1024 * 1024
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 2048
MAX_MEMBER_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
MAX_XML_BYTES = 32 * 1024 * 1024
XML_FORBIDDEN_MARKERS = (b"<!doctype", b"<!entity")
URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
XML = "http://www.w3.org/XML/1998/namespace"

NS = {"w": W, "r": R, "rel": REL, "wp": WP, "w14": W14}


def q(namespace: str, local: str) -> str:
    return f"{{{namespace}}}{local}"


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256_bytes(payload)


def int_attr(element: ET.Element | None, namespace: str, name: str) -> int | None:
    if element is None:
        return None
    raw = element.get(q(namespace, name))
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def str_attr(
    element: ET.Element | None, namespace: str, name: str, default: str | None = None
) -> str | None:
    if element is None:
        return default
    return element.get(q(namespace, name), default)


def text_content(element: ET.Element) -> str:
    return "".join(node.text or "" for node in element.findall(".//w:t", NS))


VOLATILE_ATTRS = {
    "rsidR",
    "rsidRPr",
    "rsidDel",
    "rsidP",
    "rsidSect",
    "paraId",
    "textId",
}


def canonical_node(element: ET.Element, *, strip_text: bool = True) -> Any:
    """Return a stable, compact XML representation suitable for hashing."""

    attrs = []
    for key, value in sorted(element.attrib.items()):
        if local_name(key) in VOLATILE_ATTRS:
            continue
        attrs.append((local_name(key), value))

    if element.tag in {q(W, "t"), q(W, "instrText"), q(W, "delText")}:
        node_text = "<TEXT>" if strip_text else (element.text or "")
    else:
        raw = (element.text or "").strip()
        node_text = raw if raw else None

    children = [
        canonical_node(child, strip_text=strip_text)
        for child in list(element)
        if child.tag != q(W, "proofErr")
    ]
    return [local_name(element.tag), attrs, node_text, children]


def find_child(parent: ET.Element | None, path: str) -> ET.Element | None:
    if parent is None:
        return None
    return parent.find(path, NS)


def relation_target(
    relationship_map: dict[str, dict[str, str]], relationship_id: str | None
) -> str | None:
    if not relationship_id:
        return None
    item = relationship_map.get(relationship_id)
    if not item:
        return None
    return item.get("report_target")


def external_target_reasons(
    mode: str,
    target: str,
    package_names: set[str],
) -> list[str]:
    """Classify targets that must never be treated as internal package paths."""

    decoded = unquote(target).strip()
    reasons: list[str] = []
    if mode.strip().casefold() == "external":
        reasons.append("declared_external")
    if URI_SCHEME_RE.match(decoded):
        reasons.append("absolute_uri")
    if decoded.casefold().startswith("file:"):
        reasons.append("file_uri")
    if decoded.startswith(("\\\\", "//")):
        reasons.append("unc_or_network_path")
    if WINDOWS_ABSOLUTE_PATH_RE.match(decoded):
        reasons.append("absolute_file_path")
    if (
        decoded.startswith("/")
        and not decoded.startswith("//")
        and decoded.lstrip("/") not in package_names
    ):
        reasons.append("absolute_file_path")
    return reasons


def parse_relationships(
    archive: zipfile.ZipFile,
    findings: list[dict[str, Any]],
    *,
    include_sensitive_metadata: bool = False,
) -> tuple[dict[str, dict[str, str]], list[dict[str, Any]]]:
    main_rel_path = "word/_rels/document.xml.rels"
    names = set(archive.namelist())
    if main_rel_path not in names:
        findings.append(
            finding("PKG003_MISSING_DOCUMENT_RELS", "P0", "package", "缺少主文档关系文件")
        )

    rel_map: dict[str, dict[str, str]] = {}
    normalized: list[dict[str, Any]] = []
    rel_paths = sorted(name for name in names if name.lower().endswith(".rels"))
    for rel_path in rel_paths:
        rel_path_hash = sha256_bytes(rel_path.encode("utf-8"))
        try:
            root = ET.fromstring(archive.read(rel_path))
        except ET.ParseError as exc:
            code = (
                "PKG004_INVALID_DOCUMENT_RELS"
                if rel_path == main_rel_path
                else "PKG017_INVALID_RELATIONSHIP_PART"
            )
            findings.append(
                finding(
                    code,
                    "P0",
                    "package/relationship-part",
                    "关系文件无法解析",
                    evidence={
                        "relationship_part_sha256": rel_path_hash,
                        "error_type": type(exc).__name__,
                    },
                )
            )
            continue
        if root.tag != q(REL, "Relationships"):
            code = (
                "PKG004_INVALID_DOCUMENT_RELS"
                if rel_path == main_rel_path
                else "PKG017_INVALID_RELATIONSHIP_PART"
            )
            findings.append(
                finding(
                    code,
                    "P0",
                    "package/relationship-part",
                    "关系文件根元素或命名空间无效",
                    {"relationship_part_sha256": rel_path_hash},
                )
            )
            continue

        for node in root.findall(f"./{{{REL}}}Relationship"):
            rel_id = node.get("Id", "")
            target = node.get("Target", "")
            mode = node.get("TargetMode", "Internal")
            rel_type = node.get("Type", "")
            target_hash = sha256_bytes(target.encode("utf-8"))
            relationship_type_hash = sha256_bytes(rel_type.encode("utf-8"))
            external_reasons = external_target_reasons(mode, target, names)

            if rel_path == main_rel_path:
                rel_map[rel_id] = {
                    "target": target,
                    "report_target": (
                        target
                        if include_sensitive_metadata
                        else f"<redacted:{target_hash}>"
                    ),
                    "mode": mode,
                    "type": rel_type,
                }

            normalized_item = {
                "relationship_part_sha256": rel_path_hash,
                "relationship_id_sha256": sha256_bytes(rel_id.encode("utf-8")),
                "type_sha256": relationship_type_hash,
                "target_sha256": target_hash,
                "target_redacted": not include_sensitive_metadata,
                "mode": mode,
            }
            if include_sensitive_metadata:
                normalized_item["target"] = target
            if external_reasons:
                normalized_item["external_reasons"] = external_reasons
                findings.append(
                    finding(
                        code="REL003_EXTERNAL_TARGET",
                        severity="P1",
                        path="package/relationship",
                        message="检测到外部、URI、UNC 或文件关系目标；默认隐藏原值，交付前须核验并移除非必要链接",
                        evidence={
                            "relationship_part_sha256": rel_path_hash,
                            "relationship_id_sha256": sha256_bytes(
                                rel_id.encode("utf-8")
                            ),
                            "relationship_type_sha256": relationship_type_hash,
                            "target_sha256": target_hash,
                            "reasons": external_reasons,
                        },
                    )
                )
            else:
                if rel_path == main_rel_path:
                    resolved = posixpath.normpath(
                        posixpath.join("word", target)
                    ).lstrip("/")
                    if resolved not in names:
                        evidence: dict[str, Any] = {
                            "target_sha256": target_hash,
                            "resolved_sha256": sha256_bytes(
                                resolved.encode("utf-8")
                            ),
                        }
                        if include_sensitive_metadata:
                            evidence.update({"target": target, "resolved": resolved})
                        findings.append(
                            finding(
                                "REL002_MISSING_TARGET",
                                "P0",
                                "package/relationship",
                                "关系目标不存在",
                                evidence,
                            )
                        )
            normalized.append(normalized_item)

    normalized.sort(
        key=lambda item: (
            item["relationship_part_sha256"],
            item["type_sha256"],
            item["target_sha256"],
            item["mode"],
        )
    )
    return rel_map, normalized


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


def member_evidence(info: zipfile.ZipInfo) -> dict[str, Any]:
    return {
        "member_name_sha256": sha256_bytes(info.filename.encode("utf-8")),
        "compressed_bytes": info.compress_size,
        "uncompressed_bytes": info.file_size,
    }


def scan_xml_safety(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    findings: list[dict[str, Any]],
) -> bool:
    tail = b""
    try:
        with archive.open(info, "r") as source:
            while chunk := source.read(HASH_CHUNK_SIZE):
                lowered = (tail + chunk).lower()
                marker = next(
                    (item for item in XML_FORBIDDEN_MARKERS if item in lowered),
                    None,
                )
                if marker is not None:
                    findings.append(
                        finding(
                            code="PKG013_UNSAFE_XML_DECLARATION",
                            severity="P0",
                            path="package/xml-member",
                            message="XML 包含被禁止的 DOCTYPE 或 ENTITY 声明",
                            evidence={
                                **member_evidence(info),
                                "marker": marker.decode("ascii"),
                            },
                        )
                    )
                    return False
                tail = lowered[-32:]
    except (OSError, RuntimeError, zipfile.BadZipFile, NotImplementedError) as exc:
        findings.append(
            finding(
                code="PKG014_XML_PREFLIGHT_FAILED",
                severity="P0",
                path="package/xml-member",
                message=f"XML 安全预检失败：{exc}",
                evidence=member_evidence(info),
            )
        )
        return False
    return True


def preflight_archive(
    archive: zipfile.ZipFile,
    archive_size: int,
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    infos = archive.infolist()
    total_uncompressed = sum(info.file_size for info in infos)
    package = {
        "archive_size_bytes": archive_size,
        "entry_count": len(infos),
        "total_uncompressed_bytes": total_uncompressed,
        "limits": {
            "archive_bytes": MAX_ARCHIVE_BYTES,
            "members": MAX_ARCHIVE_MEMBERS,
            "member_uncompressed_bytes": MAX_MEMBER_UNCOMPRESSED_BYTES,
            "total_uncompressed_bytes": MAX_TOTAL_UNCOMPRESSED_BYTES,
            "compression_ratio": MAX_COMPRESSION_RATIO,
            "xml_bytes": MAX_XML_BYTES,
        },
    }

    if archive_size > MAX_ARCHIVE_BYTES:
        findings.append(
            finding(
                "PKG007_ARCHIVE_TOO_LARGE",
                "P0",
                "package",
                "DOCX 压缩包超过允许大小",
                {"actual": archive_size, "limit": MAX_ARCHIVE_BYTES},
            )
        )
    if len(infos) > MAX_ARCHIVE_MEMBERS:
        findings.append(
            finding(
                "PKG008_TOO_MANY_MEMBERS",
                "P0",
                "package",
                "DOCX 包内成员数量超过限制",
                {"actual": len(infos), "limit": MAX_ARCHIVE_MEMBERS},
            )
        )
    if total_uncompressed > MAX_TOTAL_UNCOMPRESSED_BYTES:
        findings.append(
            finding(
                "PKG009_TOTAL_UNCOMPRESSED_TOO_LARGE",
                "P0",
                "package",
                "DOCX 总解压大小超过限制",
                {
                    "actual": total_uncompressed,
                    "limit": MAX_TOTAL_UNCOMPRESSED_BYTES,
                },
            )
        )

    duplicate_names = [
        name for name, count in Counter(info.filename for info in infos).items() if count > 1
    ]
    if duplicate_names:
        findings.append(
            finding(
                "PKG010_DUPLICATE_MEMBERS",
                "P0",
                "package",
                "DOCX 包含重名成员，解析结果可能不确定",
                {
                    "member_name_hashes": sorted(
                        sha256_bytes(name.encode("utf-8")) for name in duplicate_names
                    )
                },
            )
        )

    for info in infos:
        evidence = member_evidence(info)
        if info.flag_bits & 0x1:
            findings.append(
                finding(
                    "PKG011_ENCRYPTED_MEMBER",
                    "P0",
                    "package/member",
                    "DOCX 包含加密成员，无法安全审计",
                    evidence,
                )
            )
        if info.file_size > MAX_MEMBER_UNCOMPRESSED_BYTES:
            findings.append(
                finding(
                    "PKG012_MEMBER_TOO_LARGE",
                    "P0",
                    "package/member",
                    "DOCX 单个成员解压大小超过限制",
                    {**evidence, "limit": MAX_MEMBER_UNCOMPRESSED_BYTES},
                )
            )
        if info.file_size:
            ratio = info.file_size / max(1, info.compress_size)
            if ratio > MAX_COMPRESSION_RATIO:
                findings.append(
                    finding(
                        "PKG015_COMPRESSION_RATIO_TOO_HIGH",
                        "P0",
                        "package/member",
                        "DOCX 成员压缩比超过限制",
                        {
                            **evidence,
                            "ratio": round(ratio, 3),
                            "limit": MAX_COMPRESSION_RATIO,
                        },
                    )
                )
        if info.filename.lower().endswith((".xml", ".rels")):
            if info.file_size > MAX_XML_BYTES:
                findings.append(
                    finding(
                        "PKG016_XML_TOO_LARGE",
                        "P0",
                        "package/xml-member",
                        "XML 成员超过允许大小",
                        {**evidence, "limit": MAX_XML_BYTES},
                    )
                )

    if any(item["severity"] == "P0" for item in findings):
        return package

    for info in infos:
        if info.filename.lower().endswith((".xml", ".rels")):
            if not scan_xml_safety(archive, info, findings):
                break
    return package


def parse_section(
    sect_pr: ET.Element,
    section_id: str,
    table_ids: list[str],
    relationship_map: dict[str, dict[str, str]],
) -> dict[str, Any]:
    page_size = find_child(sect_pr, "w:pgSz")
    margins = find_child(sect_pr, "w:pgMar")
    section_type = find_child(sect_pr, "w:type")
    columns = find_child(sect_pr, "w:cols")
    page_number = find_child(sect_pr, "w:pgNumType")

    headers = []
    for node in sect_pr.findall("w:headerReference", NS):
        rel_id = node.get(q(R, "id"))
        headers.append(
            {
                "type": node.get(q(W, "type"), "default"),
                "target": relation_target(relationship_map, rel_id),
            }
        )
    footers = []
    for node in sect_pr.findall("w:footerReference", NS):
        rel_id = node.get(q(R, "id"))
        footers.append(
            {
                "type": node.get(q(W, "type"), "default"),
                "target": relation_target(relationship_map, rel_id),
            }
        )

    result = {
        "id": section_id,
        "page": {
            "width_dxa": int_attr(page_size, W, "w"),
            "height_dxa": int_attr(page_size, W, "h"),
            "orientation": str_attr(page_size, W, "orient", "portrait"),
        },
        "margins": {
            "top_dxa": int_attr(margins, W, "top"),
            "right_dxa": int_attr(margins, W, "right"),
            "bottom_dxa": int_attr(margins, W, "bottom"),
            "left_dxa": int_attr(margins, W, "left"),
            "gutter_dxa": int_attr(margins, W, "gutter") or 0,
            "header_dxa": int_attr(margins, W, "header"),
            "footer_dxa": int_attr(margins, W, "footer"),
        },
        "section_type": str_attr(section_type, W, "val", "nextPage(default)"),
        "columns": {
            "count": int_attr(columns, W, "num") or 1,
            "space_dxa": int_attr(columns, W, "space"),
        },
        "title_page": sect_pr.find("w:titlePg", NS) is not None,
        "page_number": {
            "start": int_attr(page_number, W, "start"),
            "format": str_attr(page_number, W, "fmt"),
        },
        "headers": sorted(headers, key=lambda item: (item["type"], item["target"] or "")),
        "footers": sorted(footers, key=lambda item: (item["type"], item["target"] or "")),
        "table_ids": table_ids,
        "properties_hash": stable_hash(canonical_node(sect_pr, strip_text=True)),
    }
    width = result["page"]["width_dxa"]
    left = result["margins"]["left_dxa"]
    right = result["margins"]["right_dxa"]
    gutter = result["margins"]["gutter_dxa"]
    result["usable_width_dxa"] = (
        width - left - right - gutter
        if None not in (width, left, right, gutter)
        else None
    )
    return result


def table_depth(element: ET.Element, parent_map: dict[ET.Element, ET.Element]) -> int:
    depth = 0
    current = parent_map.get(element)
    while current is not None:
        if current.tag == q(W, "tbl"):
            depth += 1
        current = parent_map.get(current)
    return depth


def analyze_table(
    table: ET.Element,
    table_id: str,
    depth: int,
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    table_pr = find_child(table, "w:tblPr")
    table_width = find_child(table_pr, "w:tblW")
    table_indent = find_child(table_pr, "w:tblInd")
    table_layout = find_child(table_pr, "w:tblLayout")
    table_justification = find_child(table_pr, "w:jc")
    floating = find_child(table_pr, "w:tblpPr") is not None
    grid_columns = [
        int_attr(node, W, "w") or 0
        for node in table.findall("./w:tblGrid/w:gridCol", NS)
    ]
    grid_count = len(grid_columns)

    rows: list[dict[str, Any]] = []
    active_merges: dict[tuple[int, int], int] = {}
    merge_cells: list[dict[str, Any]] = []
    cant_split_count = 0
    header_indices: list[int] = []

    for row_index, row in enumerate(table.findall("./w:tr", NS)):
        row_pr = find_child(row, "w:trPr")
        row_height = find_child(row_pr, "w:trHeight")
        grid_before = int_attr(find_child(row_pr, "w:gridBefore"), W, "val") or 0
        grid_after = int_attr(find_child(row_pr, "w:gridAfter"), W, "val") or 0
        cant_split = find_child(row_pr, "w:cantSplit") is not None
        repeat_header = find_child(row_pr, "w:tblHeader") is not None
        if cant_split:
            cant_split_count += 1
        if repeat_header:
            header_indices.append(row_index)

        cursor = grid_before
        cells = []
        merge_keys_this_row: set[tuple[int, int]] = set()
        for cell_index, cell in enumerate(row.findall("./w:tc", NS)):
            cell_pr = find_child(cell, "w:tcPr")
            span = int_attr(find_child(cell_pr, "w:gridSpan"), W, "val") or 1
            cell_width_node = find_child(cell_pr, "w:tcW")
            vertical_merge = find_child(cell_pr, "w:vMerge")
            if vertical_merge is None:
                merge_value = None
            else:
                merge_value = str_attr(vertical_merge, W, "val", "continue") or "continue"
            key = (cursor, span)
            if merge_value == "restart":
                active_merges[key] = row_index
                merge_keys_this_row.add(key)
            elif merge_value == "continue":
                merge_keys_this_row.add(key)
                if key not in active_merges:
                    findings.append(
                        finding(
                            "MRG001_CONTINUE_WITHOUT_RESTART",
                            "P0",
                            f"{table_id}/R{row_index:03d}/C{cursor:03d}",
                            "纵向合并 continue 缺少匹配的 restart",
                            {"span": span},
                        )
                    )

            cell_text = text_content(cell)
            cells.append(
                {
                    "physical_index": cell_index,
                    "start_col": cursor,
                    "span": span,
                    "width": {
                        "type": str_attr(cell_width_node, W, "type"),
                        "value": int_attr(cell_width_node, W, "w"),
                    },
                    "vmerge": merge_value,
                    "nested_table_count": len(cell.findall(".//w:tbl", NS)),
                    "text_chars": len(cell_text),
                    "text_hash": sha256_bytes(cell_text.encode("utf-8")),
                    "properties_hash": stable_hash(
                        canonical_node(cell_pr, strip_text=True) if cell_pr is not None else None
                    ),
                }
            )
            if merge_value:
                merge_cells.append(
                    {
                        "row": row_index,
                        "start_col": cursor,
                        "span": span,
                        "value": merge_value,
                    }
                )
            cursor += span

        for key in list(active_merges):
            if key not in merge_keys_this_row:
                active_merges.pop(key, None)

        coverage = cursor + grid_after
        if grid_count and coverage != grid_count:
            findings.append(
                finding(
                    "TBL003_ROW_GRID_MISMATCH",
                    "P1",
                    f"{table_id}/R{row_index:03d}",
                    "该行逻辑列覆盖与 tblGrid 不一致",
                    {
                        "grid_columns": grid_count,
                        "row_coverage": coverage,
                        "grid_before": grid_before,
                        "grid_after": grid_after,
                    },
                )
            )

        rows.append(
            {
                "index": row_index,
                "grid_before": grid_before,
                "grid_after": grid_after,
                "height": {
                    "value_dxa": int_attr(row_height, W, "val"),
                    "rule": str_attr(row_height, W, "hRule"),
                },
                "cant_split": cant_split,
                "repeat_header": repeat_header,
                "cells": cells,
                "properties_hash": stable_hash(
                    canonical_node(row_pr, strip_text=True) if row_pr is not None else None
                ),
            }
        )

    if header_indices:
        expected = list(range(0, max(header_indices) + 1))
        if header_indices != expected:
            findings.append(
                finding(
                    "PAG003_NONCONTIGUOUS_TABLE_HEADER",
                    "P1",
                    table_id,
                    "重复表头行不是从表格顶部开始的连续行",
                    {"header_rows": header_indices},
                )
            )

    data_row_count = max(0, len(rows) - len(header_indices))
    data_cant_split = max(0, cant_split_count - len(header_indices))
    ratio = data_cant_split / data_row_count if data_row_count else 0.0
    risky_cant_split_rows = []
    for row in rows:
        if row["repeat_header"] or not row["cant_split"]:
            continue
        row_total = sum(cell["text_chars"] for cell in row["cells"])
        row_max_cell = max((cell["text_chars"] for cell in row["cells"]), default=0)
        if row_total > 100 or row_max_cell > 60:
            risky_cant_split_rows.append(row["index"])
    if ratio > 0.80 and (
        risky_cant_split_rows or (data_row_count >= 30 and ratio > 0.95)
    ):
        findings.append(
            finding(
                "PAG001_EXCESSIVE_CANTSPLIT",
                "P1",
                table_id,
                "较长内容行或大型表格中禁止跨页比例过高，可能造成巨幅留白或溢出",
                {
                    "data_rows": data_row_count,
                    "cant_split_rows": data_cant_split,
                    "ratio": round(ratio, 4),
                    "risky_row_indices": risky_cant_split_rows,
                },
            )
        )

    if floating:
        findings.append(
            finding(
                "TBL005_FLOATING_TABLE",
                "P1",
                table_id,
                "检测到浮动表格；普通版心公式不能可靠判断其位置",
            )
        )
    if not grid_columns:
        findings.append(
            finding("TBL004_MISSING_GRID", "P1", table_id, "表格缺少 tblGrid")
        )

    table_text = text_content(table)
    return {
        "id": table_id,
        "depth": depth,
        "section_id": None,
        "width": {
            "type": str_attr(table_width, W, "type"),
            "value": int_attr(table_width, W, "w"),
        },
        "indent": {
            "type": str_attr(table_indent, W, "type"),
            "value": int_attr(table_indent, W, "w") or 0,
        },
        "layout": str_attr(table_layout, W, "type"),
        "justification": str_attr(table_justification, W, "val", "left"),
        "floating": floating,
        "grid_columns_dxa": grid_columns,
        "grid_width_dxa": sum(grid_columns),
        "row_count": len(rows),
        "rows": rows,
        "merge_cells": merge_cells,
        "text_chars": len(table_text),
        "text_hash": sha256_bytes(table_text.encode("utf-8")),
        "properties_hash": stable_hash(
            canonical_node(table_pr, strip_text=True) if table_pr is not None else None
        ),
    }


def topology_view(report: dict[str, Any]) -> dict[str, Any]:
    sections = []
    for section in report["document"]["sections"]:
        sections.append(
            {
                "page": section["page"],
                "margins": section["margins"],
                "section_type": section["section_type"],
                "columns": section["columns"],
                "title_page": section["title_page"],
                "page_number": section["page_number"],
                "headers": section["headers"],
                "footers": section["footers"],
                "table_ids": section["table_ids"],
            }
        )
    tables = []
    for table in report["document"]["tables"]:
        tables.append(
            {
                "id": table["id"],
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
    return {"sections": sections, "tables": tables}


def format_view(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "section_properties": [
            item["properties_hash"] for item in report["document"]["sections"]
        ],
        "tables": [
            {
                "properties_hash": table["properties_hash"],
                "width": table["width"],
                "indent": table["indent"],
                "layout": table["layout"],
                "justification": table["justification"],
                "floating": table["floating"],
                "rows": [
                    {
                        "properties_hash": row["properties_hash"],
                        "height": row["height"],
                        "cells": [cell["properties_hash"] for cell in row["cells"]],
                    }
                    for row in table["rows"]
                ],
            }
            for table in report["document"]["tables"]
        ],
        "property_inventory": report["document"].get("property_inventory", {}),
    }


def audit_docx(
    path: Path,
    *,
    include_text: bool = False,
    include_sensitive_metadata: bool = False,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    try:
        source_size = path.stat().st_size
    except OSError as exc:
        findings.append(
            finding(
                "PKG001_INVALID_ZIP",
                "P0",
                "package",
                "无法读取 DOCX 文件",
                {"error_type": type(exc).__name__},
            )
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "tool": {"name": "docx_audit", "version": VERSION},
            "source": {"filename": "<redacted>", "filename_redacted": True},
            "document": {},
            "findings": findings,
            "summary": summarize(findings),
        }

    filename_hash = sha256_bytes(path.name.encode("utf-8"))
    source_metadata = {
        "filename": path.name if include_sensitive_metadata else "<redacted>",
        "filename_sha256": filename_hash,
        "filename_redacted": not include_sensitive_metadata,
        "size_bytes": source_size,
    }
    if source_size > MAX_ARCHIVE_BYTES:
        findings.append(
            finding(
                "PKG007_ARCHIVE_TOO_LARGE",
                "P0",
                "package",
                "DOCX 压缩包超过允许大小",
                {"actual": source_size, "limit": MAX_ARCHIVE_BYTES},
            )
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "tool": {"name": "docx_audit", "version": VERSION},
            "source": source_metadata,
            "package": {
                "archive_size_bytes": source_size,
                "limits": {"archive_bytes": MAX_ARCHIVE_BYTES},
            },
            "document": {},
            "findings": findings,
            "summary": summarize(findings),
        }

    try:
        source_sha256 = sha256_file(path)
    except OSError as exc:
        findings.append(
            finding(
                "PKG001_INVALID_ZIP",
                "P0",
                "package",
                "无法读取 DOCX 文件",
                {"error_type": type(exc).__name__},
            )
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "tool": {"name": "docx_audit", "version": VERSION},
            "source": source_metadata,
            "document": {},
            "findings": findings,
            "summary": summarize(findings),
        }

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "tool": {"name": "docx_audit", "version": VERSION},
        "source": {
            **source_metadata,
            "sha256": source_sha256,
        },
    }

    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        findings.append(finding("PKG001_INVALID_ZIP", "P0", "package", str(exc)))
        report["document"] = {}
        report["findings"] = findings
        report["summary"] = summarize(findings)
        return report

    with archive:
        package_preflight = preflight_archive(archive, source_size, findings)
        if any(item["severity"] == "P0" for item in findings):
            report["package"] = package_preflight
            report["document"] = {}
            report["findings"] = findings
            report["summary"] = summarize(findings)
            return report

        bad_member = archive.testzip()
        if bad_member:
            findings.append(
                finding(
                    "PKG002_CORRUPT_MEMBER",
                    "P0",
                    bad_member,
                    "DOCX 包内文件校验失败",
                )
            )
        names = sorted(archive.namelist())
        if "word/document.xml" not in names:
            findings.append(
                finding("PKG005_MISSING_DOCUMENT_XML", "P0", "package", "缺少 word/document.xml")
            )
            report["package"] = {
                **package_preflight,
                "entries_hash": stable_hash(names),
            }
            report["document"] = {}
            report["findings"] = findings
            report["summary"] = summarize(findings)
            return report

        relationship_map, normalized_relationships = parse_relationships(
            archive,
            findings,
            include_sensitive_metadata=include_sensitive_metadata,
        )
        try:
            root = ET.fromstring(archive.read("word/document.xml"))
        except ET.ParseError as exc:
            findings.append(
                finding("PKG006_INVALID_DOCUMENT_XML", "P0", "word/document.xml", str(exc))
            )
            report["document"] = {}
            report["findings"] = findings
            report["summary"] = summarize(findings)
            return report

        report["package"] = {
            **package_preflight,
            "entries_hash": stable_hash(names),
            "relationships": normalized_relationships,
            "relationships_hash": stable_hash(
                [
                    {
                        key: value
                        for key, value in item.items()
                        if key not in {"target", "target_redacted"}
                    }
                    for item in normalized_relationships
                ]
            ),
        }

        parent_map = {child: parent for parent in root.iter() for child in parent}
        all_tables = root.findall(".//w:tbl", NS)
        table_id_map = {id(table): f"T{index:03d}" for index, table in enumerate(all_tables, 1)}
        tables = [
            analyze_table(
                table,
                table_id_map[id(table)],
                table_depth(table, parent_map),
                findings,
            )
            for table in all_tables
        ]
        table_report_map = {item["id"]: item for item in tables}

        body = root.find("w:body", NS)
        sections: list[dict[str, Any]] = []
        pending_table_ids: list[str] = []
        if body is None:
            findings.append(finding("DOC001_MISSING_BODY", "P0", "document", "缺少 w:body"))
        else:
            section_counter = 0
            for child in list(body):
                if child.tag == q(W, "tbl"):
                    pending_table_ids.append(table_id_map[id(child)])
                    for nested in child.findall(".//w:tbl", NS):
                        pending_table_ids.append(table_id_map[id(nested)])
                elif child.tag == q(W, "p"):
                    sect_pr = child.find("./w:pPr/w:sectPr", NS)
                    if sect_pr is not None:
                        section_counter += 1
                        section_id = f"SEC-{section_counter:02d}"
                        sections.append(
                            parse_section(
                                sect_pr,
                                section_id,
                                list(pending_table_ids),
                                relationship_map,
                            )
                        )
                        pending_table_ids.clear()
                elif child.tag == q(W, "sectPr"):
                    section_counter += 1
                    section_id = f"SEC-{section_counter:02d}"
                    sections.append(
                        parse_section(
                            child,
                            section_id,
                            list(pending_table_ids),
                            relationship_map,
                        )
                    )
                    pending_table_ids.clear()

            if pending_table_ids:
                findings.append(
                    finding(
                        "SEC001_UNASSIGNED_CONTENT",
                        "P1",
                        "document",
                        "部分表格未能映射到分节",
                        {"table_ids": pending_table_ids},
                    )
                )
            if not sections:
                findings.append(
                    finding("SEC002_MISSING_SECTION_PROPERTIES", "P1", "document", "未发现分节属性")
                )

        section_map = {section["id"]: section for section in sections}
        for section in sections:
            for table_id in section["table_ids"]:
                if table_id in table_report_map:
                    table_report_map[table_id]["section_id"] = section["id"]

        for table in tables:
            if table["depth"] > 0:
                findings.append(
                    finding(
                        "TBL006_NESTED_TABLE_REVIEW",
                        "P2",
                        table["id"],
                        "嵌套表格需按父单元格可用宽度另行复核",
                    )
                )
                continue
            section = section_map.get(table["section_id"])
            if not section or section["usable_width_dxa"] is None:
                findings.append(
                    finding(
                        "TBL007_UNKNOWN_USABLE_WIDTH",
                        "P1",
                        table["id"],
                        "无法确定所属分节的正文可用宽度",
                    )
                )
                continue
            body_width = section["usable_width_dxa"]
            width_type = table["width"]["type"]
            width_value = table["width"]["value"]
            grid_width = table["grid_width_dxa"]
            if width_type == "dxa" and width_value and width_value > 0:
                effective_width = float(width_value)
            elif width_type == "pct" and width_value is not None:
                effective_width = body_width * width_value / 5000.0
            else:
                effective_width = float(grid_width)
            indent = float(table["indent"]["value"] or 0)
            justification = table["justification"] or "left"
            if justification == "center":
                left_edge = (body_width - effective_width) / 2.0
            elif justification == "right":
                left_edge = body_width - effective_width
            else:
                left_edge = indent
            right_edge = left_edge + effective_width
            tolerance = max(20.0, effective_width * 0.0025)
            overflow = max(0.0, right_edge - body_width, -left_edge)
            table["geometry"] = {
                "usable_width_dxa": body_width,
                "effective_width_dxa": round(effective_width, 3),
                "left_edge_dxa": round(left_edge, 3),
                "right_edge_dxa": round(right_edge, 3),
                "overflow_dxa": round(overflow, 3),
                "tolerance_dxa": round(tolerance, 3),
            }
            if overflow > tolerance:
                findings.append(
                    finding(
                        "TBL001_WIDTH_OVERFLOW",
                        "P0",
                        table["id"],
                        "表格超出所属分节正文可用宽度",
                        table["geometry"],
                    )
                )
            elif overflow > 0:
                findings.append(
                    finding(
                        "TBL002_WIDTH_NEAR_EDGE",
                        "P1",
                        table["id"],
                        "表格轻微越过版心或存在取整风险",
                        table["geometry"],
                    )
                )
            if width_type == "dxa" and width_value and grid_width:
                difference = abs(width_value - grid_width)
                if difference > tolerance:
                    findings.append(
                        finding(
                            "TBL008_WIDTH_GRID_DIFFERENCE",
                            "P1",
                            table["id"],
                            "tblW 与 tblGrid 总宽差异超出容差",
                            {
                                "tblW_dxa": width_value,
                                "grid_width_dxa": grid_width,
                                "difference_dxa": difference,
                                "tolerance_dxa": round(tolerance, 3),
                            },
                        )
                    )

        relationship_ids = set(relationship_map)
        referenced_ids: set[str] = set()
        for element in root.iter():
            for attribute, value in element.attrib.items():
                if attribute in {q(R, "id"), q(R, "embed"), q(R, "link")}:
                    referenced_ids.add(value)
        for missing_id in sorted(referenced_ids - relationship_ids):
            findings.append(
                finding(
                    "REL001_UNRESOLVED_ID",
                    "P0",
                    f"relationship/{missing_id}",
                    "主文档引用了不存在的关系 ID",
                )
            )

        docpr_ids = [node.get("id") for node in root.findall(".//wp:docPr", NS)]
        duplicate_docpr = sorted(
            value for value, count in Counter(docpr_ids).items() if value is not None and count > 1
        )
        if duplicate_docpr:
            findings.append(
                finding(
                    "OBJ001_DUPLICATE_DOCPR_ID",
                    "P0",
                    "document/drawings",
                    "绘图 docPr ID 重复",
                    {"ids": duplicate_docpr},
                )
            )

        text = text_content(root)
        checkbox_chars = {
            char: text.count(char) for char in ("□", "☐", "☑", "☒", "√", "■", "▣")
        }
        inline_count = len(root.findall(".//wp:inline", NS))
        anchor_count = len(root.findall(".//wp:anchor", NS))
        if anchor_count:
            findings.append(
                finding(
                    "OBJ002_FLOATING_DRAWINGS",
                    "P1",
                    "document/drawings",
                    "检测到浮动绘图；勾选或表格覆盖对象可能跨软件漂移",
                    {"anchor_count": anchor_count},
                )
            )
        solid_marks = checkbox_chars["■"] + checkbox_chars["▣"] + checkbox_chars["☒"]
        if solid_marks:
            findings.append(
                finding(
                    "CHK001_SOLID_OR_X_MARK",
                    "P1",
                    "document/checkboxes",
                    "检测到实心或叉号方框字符；需逐项确认是否违反框内√标准",
                    {"count": solid_marks},
                )
            )

        revision_count = len(root.findall(".//w:ins", NS)) + len(root.findall(".//w:del", NS))
        comment_range_count = len(root.findall(".//w:commentRangeStart", NS))
        hidden_count = len(root.findall(".//w:vanish", NS))
        if revision_count:
            findings.append(
                finding(
                    code="DOC002_UNRESOLVED_REVISIONS",
                    severity="P1",
                    path="document/revisions",
                    message="存在未处理的修订标记",
                    evidence={"count": revision_count},
                )
            )
        if comment_range_count or "word/comments.xml" in names:
            findings.append(
                finding(
                    "DOC003_COMMENTS_PRESENT",
                    "P1",
                    "document",
                    "存在批注或批注范围",
                    {"range_count": comment_range_count},
                )
            )
        if hidden_count:
            findings.append(
                finding(
                    "DOC004_HIDDEN_TEXT_PRESENT",
                    "P2",
                    "document",
                    "检测到隐藏文字属性，交付前需确认",
                    {"count": hidden_count},
                )
            )

        pagination = {
            "manual_page_breaks": len(
                [
                    node
                    for node in root.findall(".//w:br", NS)
                    if node.get(q(W, "type")) == "page"
                ]
            ),
            "page_break_before": len(root.findall(".//w:pageBreakBefore", NS)),
            "keep_next": len(root.findall(".//w:keepNext", NS)),
            "keep_lines": len(root.findall(".//w:keepLines", NS)),
            "cant_split_rows": len(root.findall(".//w:trPr/w:cantSplit", NS)),
            "repeat_header_rows": len(root.findall(".//w:trPr/w:tblHeader", NS)),
        }

        paragraph_property_hashes = sorted(
            stable_hash(canonical_node(node, strip_text=True))
            for node in root.findall(".//w:pPr", NS)
        )
        run_property_hashes = sorted(
            stable_hash(canonical_node(node, strip_text=True))
            for node in root.findall(".//w:rPr", NS)
        )
        property_inventory = {
            "paragraph_properties": paragraph_property_hashes,
            "run_properties": run_property_hashes,
            "text_direction": len(root.findall(".//w:textDirection", NS)),
            "fit_text": len(root.findall(".//w:fitText", NS)),
            "rtl": len(root.findall(".//w:rtl", NS)),
            "bidi": len(root.findall(".//w:bidi", NS)),
            "vertical_alignment": len(root.findall(".//w:vertAlign", NS)),
        }
        if property_inventory["fit_text"]:
            findings.append(
                finding(
                    "FMT001_FITTEXT_PRESENT",
                    "P2",
                    "document/format",
                    "检测到 fitText；需确认是否为母版固有属性",
                    {"count": property_inventory["fit_text"]},
                )
            )

        objects = {
            "drawings": len(root.findall(".//w:drawing", NS)),
            "inline_drawings": inline_count,
            "floating_drawings": anchor_count,
            "content_controls": len(root.findall(".//w:sdt", NS)),
            "w14_checkboxes": len(root.findall(".//w14:checkbox", NS)),
            "legacy_checkboxes": len(root.findall(".//w:ffData/w:checkBox", NS)),
            "docpr_ids": len(docpr_ids),
            "unique_docpr_ids": len(set(value for value in docpr_ids if value is not None)),
            "checkbox_characters": checkbox_chars,
        }

        report["document"] = {
            "sections": sections,
            "tables": tables,
            "objects": objects,
            "pagination": pagination,
            "property_inventory": property_inventory,
            "text": {
                "characters": len(text),
                "sha256": sha256_bytes(text.encode("utf-8")),
            },
        }
        if include_text:
            report["document"]["text"]["value"] = text

        report["hashes"] = {
            "topology": stable_hash(topology_view(report)),
            "format": stable_hash(format_view(report)),
            "content": report["document"]["text"]["sha256"],
            "pagination": stable_hash(
                {
                    "sections": [
                        {
                            "type": section["section_type"],
                            "page_number": section["page_number"],
                        }
                        for section in sections
                    ],
                    "pagination": pagination,
                    "rows": [
                        [
                            {
                                "cant_split": row["cant_split"],
                                "repeat_header": row["repeat_header"],
                            }
                            for row in table["rows"]
                        ]
                        for table in tables
                    ],
                }
            ),
            "checkbox_inventory": stable_hash(objects),
        }

    severity_order = {"P0": 0, "P1": 1, "P2": 2}
    findings.sort(
        key=lambda item: (
            severity_order.get(item["severity"], 9),
            item["code"],
            item["path"],
        )
    )
    report["findings"] = findings
    report["summary"] = summarize(findings)
    return report


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


def should_fail(report: dict[str, Any], threshold: str) -> bool:
    if threshold == "none":
        return False
    rank = {"P0": 0, "P1": 1, "P2": 2}
    limit = rank[threshold]
    return any(rank.get(item["severity"], 99) <= limit for item in report["findings"])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only structural audit for a DOCX legal template or complaint"
    )
    parser.add_argument("input", type=Path, help="DOCX file to inspect")
    parser.add_argument("--json", type=Path, dest="json_path", help="write JSON report")
    parser.add_argument("--include-text", action="store_true", help="include full extracted text")
    parser.add_argument(
        "--include-sensitive-metadata",
        action="store_true",
        help="include the input filename and raw external relationship targets",
    )
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON")
    parser.add_argument(
        "--fail-on",
        choices=("P0", "P1", "P2", "none"),
        default="P0",
        help="return exit code 2 when this severity or higher is present",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.input.is_file():
        if args.include_sensitive_metadata:
            diagnostic = f"Input file not found: {args.input}"
        else:
            path_hash = sha256_bytes(str(args.input).encode("utf-8"))
            diagnostic = f"Input file not found (input_path_sha256={path_hash})"
        print(diagnostic, file=sys.stderr)
        return 3
    try:
        report = audit_docx(
            args.input,
            include_text=args.include_text,
            include_sensitive_metadata=args.include_sensitive_metadata,
        )
    except Exception as exc:  # fail closed with a concise diagnostic
        print(f"Audit failed: {exc}", file=sys.stderr)
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
