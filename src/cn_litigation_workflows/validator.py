"""Deterministic validation for the public plugin and Skill bundle."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import struct
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


PROJECT_NAME = "cn-litigation-workflows"
PROJECT_VERSION = "0.1.1"
EXPECTED_SKILLS = {
    "draft-cn-element-complaints",
    "prepare-cn-evidence-damages",
}
EXPECTED_WORKBOOK_SHEETS = [
    "00_使用说明",
    "01_案件参数",
    "02_赔偿项目",
    "03_被扶养人",
    "04_保险分配",
    "05_已付款",
    "06_证据映射",
    "07_法源参数",
    "08_核对报警",
    "09_边界测试",
]
TEXT_SUFFIXES = {
    ".cff",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
IGNORED_PARTS = {".git", "__pycache__", "dist", "build"}
FORBIDDEN_BUNDLED_MARKERS = {
    "ponziwang",
    "yaosushi",
    "yaosushi-suzhuang",
}


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _issue(
    severity: str, code: str, path: Path | str, message: str
) -> ValidationIssue:
    return ValidationIssue(severity, code, str(path), message)


def _load_json(path: Path, issues: list[ValidationIssue]) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        issues.append(_issue("ERROR", "FILE_MISSING", path, "Required file is missing."))
        return {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        issues.append(_issue("ERROR", "JSON_INVALID", path, str(exc)))
        return {}
    if not isinstance(value, dict):
        issues.append(_issue("ERROR", "JSON_ROOT", path, "JSON root must be an object."))
        return {}
    return value


def _parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        return {}, raw
    end = raw.find("\n---\n", 4)
    if end < 0:
        return {}, raw
    block = raw[4:end]
    data: dict[str, str] = {}
    current_key: str | None = None
    for line in block.splitlines():
        match = re.match(r"^([a-zA-Z0-9_-]+):\s*(.*)$", line)
        if match:
            current_key = match.group(1)
            value = match.group(2).strip().strip("\"'")
            data[current_key] = "" if value in {"|", ">"} else value
        elif current_key and line.startswith((" ", "\t")):
            data[current_key] = (data[current_key] + " " + line.strip()).strip()
    return data, raw[end + 5 :]


def _relative_links(markdown: str) -> Iterable[str]:
    for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", markdown):
        target = match.group(1).strip()
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        yield target.split("#", 1)[0]


def _validate_plugin(root: Path, issues: list[ValidationIssue]) -> None:
    path = root / ".codex-plugin" / "plugin.json"
    manifest = _load_json(path, issues)
    if not manifest:
        return

    required = ["name", "version", "description", "author", "skills", "interface"]
    for field in required:
        if not manifest.get(field):
            issues.append(_issue("ERROR", "PLUGIN_FIELD", path, f"Missing {field!r}."))

    if manifest.get("name") != PROJECT_NAME:
        issues.append(
            _issue(
                "ERROR",
                "PLUGIN_NAME",
                path,
                f"Manifest name must be {PROJECT_NAME!r}.",
            )
        )
    version = str(manifest.get("version", ""))
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", version):
        issues.append(_issue("ERROR", "PLUGIN_VERSION", path, "Use strict SemVer."))
    if version != PROJECT_VERSION:
        issues.append(
            _issue("ERROR", "VERSION_SYNC", path, f"Expected {PROJECT_VERSION}, got {version}.")
        )
    if manifest.get("license") != "Apache-2.0":
        issues.append(_issue("ERROR", "PLUGIN_LICENSE", path, "Expected Apache-2.0."))
    if manifest.get("skills") != "./skills/":
        issues.append(_issue("ERROR", "PLUGIN_SKILLS_PATH", path, "Expected ./skills/."))

    author = manifest.get("author")
    if not isinstance(author, dict) or not author.get("name"):
        issues.append(_issue("ERROR", "PLUGIN_AUTHOR", path, "author.name is required."))

    for field in ("homepage", "repository"):
        value = manifest.get(field)
        if not isinstance(value, str) or not value.startswith("https://"):
            issues.append(_issue("ERROR", "PLUGIN_URL", path, f"{field} must be HTTPS."))

    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        issues.append(_issue("ERROR", "PLUGIN_INTERFACE", path, "interface must be an object."))
        return
    for field in (
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
        "defaultPrompt",
    ):
        if not interface.get(field):
            issues.append(_issue("ERROR", "PLUGIN_INTERFACE_FIELD", path, f"Missing {field}."))
    prompts = interface.get("defaultPrompt", [])
    if not isinstance(prompts, list) or not 1 <= len(prompts) <= 3:
        issues.append(
            _issue("ERROR", "PLUGIN_PROMPTS", path, "defaultPrompt must contain 1-3 strings.")
        )
    elif any(not isinstance(prompt, str) or len(prompt) > 128 for prompt in prompts):
        issues.append(
            _issue("ERROR", "PLUGIN_PROMPT_LENGTH", path, "Prompts must be <=128 characters.")
        )
    for field in ("composerIcon", "logo"):
        value = interface.get(field)
        if not isinstance(value, str) or not value.startswith("./"):
            issues.append(
                _issue(
                    "ERROR",
                    "PLUGIN_IMAGE_PATH",
                    path,
                    f"{field} must be a ./-prefixed relative path.",
                )
            )
            continue
        candidate = (root / value[2:]).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            issues.append(
                _issue("ERROR", "PLUGIN_IMAGE_ESCAPE", path, f"{field} escapes the plugin.")
            )
            continue
        if not candidate.is_file():
            issues.append(
                _issue("ERROR", "PLUGIN_IMAGE_MISSING", candidate, f"{field} is missing.")
            )
            continue
        if candidate.stat().st_size > 5 * 1024 * 1024:
            issues.append(
                _issue("ERROR", "PLUGIN_IMAGE_SIZE", candidate, "Image exceeds 5 MiB.")
            )
            continue
        try:
            header = candidate.read_bytes()[:24]
            if header[:8] != b"\x89PNG\r\n\x1a\n" or len(header) < 24:
                raise ValueError("Expected a PNG image.")
            width, height = struct.unpack(">II", header[16:24])
        except (OSError, ValueError, struct.error) as exc:
            issues.append(_issue("ERROR", "PLUGIN_IMAGE_INVALID", candidate, str(exc)))
            continue
        if width != height or width < 48 or width > 4096:
            issues.append(
                _issue(
                    "ERROR",
                    "PLUGIN_IMAGE_DIMENSIONS",
                    candidate,
                    f"Expected a 48-4096 px square image; got {width}x{height}.",
                )
            )


def _validate_marketplace(root: Path, issues: list[ValidationIssue]) -> None:
    path = root / ".agents" / "plugins" / "marketplace.json"
    market = _load_json(path, issues)
    if not market:
        return
    if market.get("name") != PROJECT_NAME:
        issues.append(_issue("ERROR", "MARKET_NAME", path, "Marketplace name mismatch."))
    plugins = market.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1:
        issues.append(_issue("ERROR", "MARKET_PLUGINS", path, "Expected one plugin entry."))
        return
    entry = plugins[0]
    if entry.get("name") != PROJECT_NAME:
        issues.append(_issue("ERROR", "MARKET_PLUGIN_NAME", path, "Plugin name mismatch."))
    source = entry.get("source", {})
    if source.get("source") != "url":
        issues.append(_issue("ERROR", "MARKET_SOURCE", path, "Expected a Git URL source."))
    url = source.get("url", "")
    if not isinstance(url, str) or not url.startswith("https://github.com/"):
        issues.append(_issue("ERROR", "MARKET_URL", path, "Expected a public GitHub HTTPS URL."))
    policy = entry.get("policy", {})
    if policy.get("installation") != "AVAILABLE":
        issues.append(_issue("ERROR", "MARKET_INSTALL", path, "Plugin must be AVAILABLE."))
    if policy.get("authentication") != "ON_INSTALL":
        issues.append(_issue("ERROR", "MARKET_AUTH", path, "Expected ON_INSTALL."))


def _validate_skills(root: Path, issues: list[ValidationIssue]) -> None:
    skills_root = root / "skills"
    if not skills_root.is_dir():
        issues.append(_issue("ERROR", "SKILLS_MISSING", skills_root, "skills/ is missing."))
        return
    actual = {path.name for path in skills_root.iterdir() if path.is_dir()}
    if actual != EXPECTED_SKILLS:
        issues.append(
            _issue(
                "ERROR",
                "SKILL_SET",
                skills_root,
                f"Expected {sorted(EXPECTED_SKILLS)}, got {sorted(actual)}.",
            )
        )

    for skill_name in sorted(actual):
        skill_dir = skills_root / skill_name
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            issues.append(_issue("ERROR", "SKILL_MD", skill_md, "SKILL.md is missing."))
            continue
        try:
            frontmatter, body = _parse_frontmatter(skill_md)
        except UnicodeDecodeError as exc:
            issues.append(_issue("ERROR", "SKILL_UTF8", skill_md, str(exc)))
            continue
        if frontmatter.get("name") != skill_name:
            issues.append(
                _issue("ERROR", "SKILL_NAME", skill_md, "Frontmatter name must match directory.")
            )
        if not frontmatter.get("description"):
            issues.append(
                _issue("ERROR", "SKILL_DESCRIPTION", skill_md, "Description is required.")
            )
        if set(frontmatter) - {"name", "description"}:
            issues.append(
                _issue("ERROR", "SKILL_FRONTMATTER", skill_md, "Only name and description are allowed.")
            )
        if len(skill_md.read_text(encoding="utf-8").splitlines()) > 500:
            issues.append(
                _issue("ERROR", "SKILL_LENGTH", skill_md, "SKILL.md must be <=500 lines.")
            )

        for target in _relative_links(body):
            candidate = (skill_dir / target).resolve()
            try:
                candidate.relative_to(skill_dir.resolve())
            except ValueError:
                issues.append(
                    _issue("ERROR", "LINK_ESCAPE", skill_md, f"Link escapes Skill: {target}")
                )
                continue
            if not candidate.exists():
                issues.append(
                    _issue("ERROR", "LINK_MISSING", skill_md, f"Missing linked file: {target}")
                )

        agent_yaml = skill_dir / "agents" / "openai.yaml"
        if not agent_yaml.is_file():
            issues.append(_issue("ERROR", "AGENT_YAML", agent_yaml, "openai.yaml is missing."))
        else:
            text = agent_yaml.read_text(encoding="utf-8")
            if f"${skill_name}" not in text:
                issues.append(
                    _issue(
                        "ERROR",
                        "AGENT_PROMPT",
                        agent_yaml,
                        "default_prompt must explicitly mention the Skill.",
                    )
                )


def _strip_urls(text: str) -> str:
    return re.sub(r"https?://[^\s)>]+", "<URL>", text)


def _scan_text(path: Path, text: str, issues: list[ValidationIssue]) -> None:
    scrubbed = _strip_urls(text)
    checks = [
        (
            "CHINESE_ID",
            re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
            "Possible Chinese identity number.",
        ),
        (
            "PHONE_CN",
            re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
            "Possible mainland mobile number.",
        ),
        (
            "PRIVATE_KEY",
            re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
            "Private key material.",
        ),
        (
            "TOKEN",
            re.compile(r"\b(?:ghp|github_pat|sk)-[A-Za-z0-9_-]{16,}\b"),
            "Possible access token.",
        ),
        (
            "ABSOLUTE_PATH",
            re.compile(
                r"(?:/"
                + r"root/|/"
                + r"workspace/|file"
                + r"://|[A-Za-z]:\\\\Users\\\\)"
            ),
            "Local absolute path.",
        ),
    ]
    for code, pattern, message in checks:
        if pattern.search(scrubbed):
            issues.append(_issue("ERROR", f"SENSITIVE_{code}", path, message))


def _scan_repository(root: Path, issues: list[ValidationIssue]) -> None:
    forbidden_suffixes = {".env", ".key", ".p12", ".pfx", ".pem"}
    for path in sorted(root.rglob("*")):
        if any(part in IGNORED_PARTS for part in path.relative_to(root).parts):
            continue
        if path.is_symlink():
            issues.append(_issue("ERROR", "SYMLINK", path, "Symlinks are not allowed."))
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() in forbidden_suffixes or path.name == ".env":
            issues.append(_issue("ERROR", "FORBIDDEN_FILE", path, "Credential-like file."))
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {
            "LICENSE",
            "NOTICE",
            ".gitignore",
            ".gitattributes",
        }:
            try:
                _scan_text(path, path.read_text(encoding="utf-8"), issues)
            except UnicodeDecodeError:
                issues.append(_issue("ERROR", "UTF8", path, "Text file is not UTF-8."))


def _validate_originality_boundary(root: Path, issues: list[ValidationIssue]) -> None:
    """Keep known third-party Skill/template sources out of the public bundle."""

    for base in (root / "skills", root / "assets"):
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_symlink() or not path.is_file():
                continue
            relative = path.relative_to(root)
            folded_path = relative.as_posix().casefold()
            if any(marker in folded_path for marker in FORBIDDEN_BUNDLED_MARKERS):
                issues.append(
                    _issue(
                        "ERROR",
                        "THIRD_PARTY_PATH",
                        path,
                        "Known third-party Skill/template marker in bundled path.",
                    )
                )
            if path.suffix.casefold() == ".docx":
                issues.append(
                    _issue(
                        "ERROR",
                        "COURT_TEMPLATE_BUNDLED",
                        path,
                        "DOCX court/template files require a separate rights review.",
                    )
                )
            if path.suffix.casefold() not in TEXT_SUFFIXES:
                continue
            try:
                folded_text = path.read_text(encoding="utf-8").casefold()
            except UnicodeDecodeError:
                continue
            if any(marker in folded_text for marker in FORBIDDEN_BUNDLED_MARKERS):
                issues.append(
                    _issue(
                        "ERROR",
                        "THIRD_PARTY_CONTENT",
                        path,
                        "Known third-party Skill/template marker in bundled content.",
                    )
                )


def _validate_office_metadata(root: Path, issues: list[ValidationIssue]) -> None:
    relationship_ns = {
        "r": "http://schemas.openxmlformats.org/package/2006/relationships"
    }
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in {".docx", ".xlsx"}:
            continue
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                for member in ("docProps/core.xml", "docProps/custom.xml"):
                    if member not in names:
                        continue
                    value = archive.read(member).decode("utf-8", errors="replace")
                    lowered = value.lower()
                    if any(
                        marker in lowered
                        for marker in (
                            "<dc:creator>",
                            "<cp:lastmodifiedby>",
                            "userid",
                            "userId".lower(),
                            "ksotemplatedocersaverecord",
                        )
                    ):
                        issues.append(
                            _issue(
                                "ERROR",
                                "OFFICE_METADATA",
                                path,
                                f"Potential author/account metadata in {member}.",
                            )
                        )
                for member in sorted(
                    name for name in names if name.endswith(".rels")
                ):
                    try:
                        relationships = ET.fromstring(archive.read(member))
                    except ET.ParseError:
                        issues.append(
                            _issue(
                                "ERROR",
                                "OFFICE_RELS_XML",
                                path,
                                f"Invalid OOXML relationships file: {member}.",
                            )
                        )
                        continue
                    for relationship in relationships.findall(
                        "r:Relationship", relationship_ns
                    ):
                        target = relationship.attrib.get("Target", "")
                        target_mode = relationship.attrib.get("TargetMode", "")
                        has_uri_scheme = bool(
                            re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target)
                        )
                        has_external_path = target.startswith(
                            ("\\\\", "//")
                        ) or bool(re.match(r"^[A-Za-z]:[\\/]", target))
                        if (
                            target_mode.casefold() == "external"
                            or has_uri_scheme
                            or has_external_path
                        ):
                            issues.append(
                                _issue(
                                    "ERROR",
                                    "OFFICE_EXTERNAL_REL",
                                    path,
                                    (
                                        "Unexpected external OOXML relationship "
                                        f"in {member}; target value withheld."
                                    ),
                                )
                            )
                external = [
                    name
                    for name in names
                    if name.startswith(("xl/externalLinks/", "word/embeddings/"))
                ]
                if external:
                    issues.append(
                        _issue(
                            "ERROR",
                            "OFFICE_EXTERNAL",
                            path,
                            f"Unexpected embedded/external parts: {external}",
                        )
                    )
        except zipfile.BadZipFile:
            issues.append(_issue("ERROR", "OFFICE_ZIP", path, "Invalid Office ZIP package."))


def _validate_workbook(root: Path, issues: list[ValidationIssue]) -> None:
    path = (
        root
        / "skills"
        / "prepare-cn-evidence-damages"
        / "assets"
        / "traffic-accident-compensation-template.xlsx"
    )
    if not path.is_file():
        issues.append(_issue("ERROR", "WORKBOOK_MISSING", path, "Workbook is missing."))
        return
    ns = {
        "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "o": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "r": "http://schemas.openxmlformats.org/package/2006/relationships",
    }
    try:
        with zipfile.ZipFile(path) as archive:
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            sheet_nodes = workbook.findall(".//m:sheet", ns)
            names = [item.attrib["name"] for item in sheet_nodes]
            workbook_relationships = ET.fromstring(
                archive.read("xl/_rels/workbook.xml.rels")
            )
            targets = {}
            for item in workbook_relationships.findall("r:Relationship", ns):
                target = item.attrib.get("Target", "").lstrip("/")
                if target and not target.startswith("xl/"):
                    target = f"xl/{target}"
                targets[item.attrib["Id"]] = target
            sheet_targets = {
                item.attrib["name"]: targets.get(
                    item.attrib.get(
                        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id",
                        "",
                    ),
                    "",
                )
                for item in sheet_nodes
            }
            formulas = 0
            for member in archive.namelist():
                if member.startswith("xl/worksheets/sheet") and member.endswith(".xml"):
                    sheet = ET.fromstring(archive.read(member))
                    formulas += len(sheet.findall(".//m:f", ns))
            gate_formulas: dict[str, str] = {}
            for sheet_name, cell_refs in {
                "08_核对报警": {"B10", "B12", "B19"},
                "04_保险分配": {"B24", "B28"},
            }.items():
                member = sheet_targets.get(sheet_name, "")
                if not member:
                    continue
                sheet = ET.fromstring(archive.read(member))
                for cell in sheet.findall(".//m:c", ns):
                    cell_ref = cell.attrib.get("r", "")
                    if cell_ref in cell_refs:
                        gate_formulas[f"{sheet_name}!{cell_ref}"] = cell.findtext(
                            "m:f", default="", namespaces=ns
                        )
    except (KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
        issues.append(_issue("ERROR", "WORKBOOK_INVALID", path, str(exc)))
        return
    if names != EXPECTED_WORKBOOK_SHEETS:
        issues.append(
            _issue("ERROR", "WORKBOOK_SHEETS", path, f"Unexpected sheets: {names}")
        )
    if formulas < 500:
        issues.append(
            _issue(
                "ERROR",
                "WORKBOOK_FORMULAS",
                path,
                f"Expected at least 500 formula cells; found {formulas}.",
            )
        )
    formula_requirements = {
        "08_核对报警!B10": (
            "'07_法源参数'!H12",
            "'07_法源参数'!I12",
            '"已核验"',
        ),
        "08_核对报警!B12": ("'07_法源参数'!E18",),
        "08_核对报警!B19": (
            "SUMPRODUCT",
            "'02_赔偿项目'!A5:A26",
            "'06_证据映射'!D5:D34",
        ),
        "04_保险分配!B24": ("IF(",),
        "04_保险分配!B28": ("IF(",),
    }
    formula_failures = []
    for cell, fragments in formula_requirements.items():
        formula = gate_formulas.get(cell, "")
        if any(fragment not in formula for fragment in fragments):
            formula_failures.append(cell)
    if "DATE(2020,9,19)" in gate_formulas.get("08_核对报警!B12", ""):
        formula_failures.append("08_核对报警!B12:magic-date")
    if formula_failures:
        issues.append(
            _issue(
                "ERROR",
                "WORKBOOK_RELEASE_GATES",
                path,
                f"Missing fail-closed release-gate formulas: {sorted(formula_failures)}.",
            )
        )


def _parse_registry_value(text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*[\"']?([^\"'\n]+)", text)
    return match.group(1).strip() if match else None


def _validate_source_freshness(
    root: Path, issues: list[ValidationIssue], today: dt.date
) -> None:
    for path in sorted(root.glob("skills/*/references/source-registry.yml")):
        text = path.read_text(encoding="utf-8")
        verified = _parse_registry_value(text, "verified_on")
        refresh = _parse_registry_value(text, "refresh_after_days")
        if not verified or not refresh:
            issues.append(
                _issue("ERROR", "SOURCE_REGISTRY", path, "Missing verification metadata.")
            )
            continue
        try:
            age = (today - dt.date.fromisoformat(verified)).days
            threshold = int(refresh)
        except ValueError as exc:
            issues.append(_issue("ERROR", "SOURCE_REGISTRY_VALUE", path, str(exc)))
            continue
        if age > threshold:
            issues.append(
                _issue(
                    "WARNING",
                    "SOURCE_STALE",
                    path,
                    f"Registry is {age} days old; refresh threshold is {threshold}.",
                )
            )


def _validate_version_files(root: Path, issues: list[ValidationIssue]) -> None:
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    citation = (root / "CITATION.cff").read_text(encoding="utf-8")
    pyproject_path = root / "pyproject.toml"
    pyproject = pyproject_path.read_text(encoding="utf-8")
    if f"## [{PROJECT_VERSION}]" not in changelog:
        issues.append(
            _issue("ERROR", "CHANGELOG_VERSION", root / "CHANGELOG.md", "Version missing.")
        )
    if f'version: "{PROJECT_VERSION}"' not in citation:
        issues.append(
            _issue("ERROR", "CITATION_VERSION", root / "CITATION.cff", "Version mismatch.")
        )
    project_block = re.search(
        r"(?ms)^\[project\]\s*(.*?)(?=^\[[^\n]+\]|\Z)",
        pyproject,
    )
    version_match = (
        re.search(r'(?m)^version\s*=\s*["\']([^"\']+)["\']\s*$', project_block.group(1))
        if project_block
        else None
    )
    pyproject_version = version_match.group(1) if version_match else None
    if pyproject_version != PROJECT_VERSION:
        issues.append(
            _issue(
                "ERROR",
                "PYPROJECT_VERSION",
                pyproject_path,
                f"Expected {PROJECT_VERSION}, got {pyproject_version or 'missing'}.",
            )
        )


def _validate_markdown_links(root: Path, issues: list[ValidationIssue]) -> None:
    paths = sorted(root.glob("*.md")) + sorted((root / "docs").glob("*.md"))
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for target in _relative_links(text):
            candidate = (path.parent / target).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                issues.append(
                    _issue("ERROR", "ROOT_LINK_ESCAPE", path, f"Link escapes repository: {target}")
                )
                continue
            if not candidate.exists():
                issues.append(
                    _issue("ERROR", "ROOT_LINK_MISSING", path, f"Missing linked file: {target}")
                )


def validate_project(
    root: Path,
    *,
    today: dt.date | None = None,
) -> list[ValidationIssue]:
    """Validate the repository without modifying it."""

    root = root.resolve()
    issues: list[ValidationIssue] = []
    required = [
        "LICENSE",
        "NOTICE",
        "README.md",
        "README.zh-CN.md",
        "PRIVACY.md",
        "TERMS.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "GOVERNANCE.md",
        "SUPPORT.md",
        "CODE_OF_CONDUCT.md",
        "ROADMAP.md",
        "ADOPTERS.md",
        "CHANGELOG.md",
        "THIRD_PARTY_NOTICES.md",
        "CITATION.cff",
        "AGENTS.md",
        "pyproject.toml",
        "docs/architecture.md",
        "docs/compatibility.md",
        "docs/evals.md",
        "docs/legal-source-policy.md",
        "docs/privacy.md",
        "docs/provenance.md",
        "docs/release-process.md",
        "docs/routing-contract.md",
        "docs/scope-disclaimer.md",
        "docs/testing.md",
        ".github/workflows/ci.yml",
        ".github/workflows/codex-pr-review.yml",
        ".github/workflows/release.yml",
        ".github/workflows/source-freshness.yml",
    ]
    for name in required:
        if not (root / name).is_file():
            issues.append(_issue("ERROR", "ROOT_FILE", root / name, "Required file missing."))

    _validate_plugin(root, issues)
    _validate_marketplace(root, issues)
    _validate_skills(root, issues)
    _scan_repository(root, issues)
    _validate_originality_boundary(root, issues)
    _validate_office_metadata(root, issues)
    _validate_workbook(root, issues)
    _validate_source_freshness(root, issues, today or dt.date.today())
    _validate_markdown_links(root, issues)
    if all(
        (root / name).is_file()
        for name in ("CHANGELOG.md", "CITATION.cff", "pyproject.toml")
    ):
        _validate_version_files(root, issues)
    return sorted(issues, key=lambda item: (item.severity, item.code, item.path))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
