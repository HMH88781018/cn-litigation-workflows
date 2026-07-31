"""Build a deterministic, path-safe plugin release archive."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path


EXCLUDED_DIR_NAMES = {
    ".git",
    ".idea",
    ".pytest_cache",
    ".ruff_cache",
    ".vscode",
    "__pycache__",
    "build",
    "dist",
    "outputs",
}
EXCLUDED_FILE_NAMES = {
    ".coverage",
    ".DS_Store",
}
EXCLUDED_SUFFIXES = {".bak", ".log", ".pyc", ".pyo", ".tmp"}
SUBMISSION_ROOT_FILES = {
    "LICENSE",
    "NOTICE",
    "THIRD_PARTY_NOTICES.md",
}
SUBMISSION_ROOT_DIRS = {
    ".codex-plugin",
    "assets",
    "skills",
}


def _is_generated(relative: Path) -> bool:
    if any(
        part in EXCLUDED_DIR_NAMES or part.endswith(".egg-info")
        for part in relative.parts
    ):
        return True
    if relative.name in EXCLUDED_FILE_NAMES:
        return True
    if relative.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    return relative.name.endswith(".docx.audit.json")


def _members(root: Path, *, excluded_paths: set[Path] | None = None) -> list[Path]:
    excluded = {path.resolve() for path in (excluded_paths or set())}
    result: list[Path] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if _is_generated(relative):
            continue
        if path.is_symlink() or not path.is_file() or path.resolve() in excluded:
            continue
        result.append(path)
    return sorted(result, key=lambda item: item.relative_to(root).as_posix())


def build_archive(root: Path, output: Path) -> tuple[Path, Path]:
    root = root.resolve()
    output = output.resolve()
    checksum = output.with_suffix(output.suffix + ".sha256")
    output.parent.mkdir(parents=True, exist_ok=True)
    files = _members(root, excluded_paths={output, checksum})
    manifest = root / ".codex-plugin" / "plugin.json"
    if manifest not in files:
        raise ValueError("Plugin manifest is not in the release set.")

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            relative = path.relative_to(root)
            if ".." in relative.parts or relative.is_absolute():
                raise ValueError(f"Unsafe archive path: {relative}")
            info = zipfile.ZipInfo(relative.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, path.read_bytes())

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return output, checksum


def _submission_members(root: Path) -> list[Path]:
    """Return the minimal, allowlisted Skills-only portal payload."""

    files: list[Path] = []
    for name in sorted(SUBMISSION_ROOT_FILES):
        path = root / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Required submission file is missing: {name}")
        files.append(path)
    for name in sorted(SUBMISSION_ROOT_DIRS):
        base = root / name
        if not base.is_dir() or base.is_symlink():
            raise ValueError(f"Required submission directory is missing: {name}")
        for path in base.rglob("*"):
            relative = path.relative_to(root)
            if _is_generated(relative) or path.is_symlink() or not path.is_file():
                continue
            files.append(path)
    return sorted(set(files), key=lambda item: item.relative_to(root).as_posix())


def build_submission_archive(root: Path, output: Path) -> tuple[Path, Path]:
    """Build a deterministic ZIP accepted by the Skills-only submission flow."""

    root = root.resolve()
    output = output.resolve()
    checksum = output.with_suffix(output.suffix + ".sha256")
    output.parent.mkdir(parents=True, exist_ok=True)
    files = _submission_members(root)
    required = {
        ".codex-plugin/plugin.json",
        "assets/composer-icon.png",
        "assets/logo.png",
        "skills/draft-cn-element-complaints/SKILL.md",
        "skills/prepare-cn-evidence-damages/SKILL.md",
    }
    names = {path.relative_to(root).as_posix() for path in files}
    missing = sorted(required - names)
    if missing:
        raise ValueError(f"Submission archive is incomplete: {missing}")

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            relative = path.relative_to(root)
            if ".." in relative.parts or relative.is_absolute():
                raise ValueError(f"Unsafe archive path: {relative}")
            info = zipfile.ZipInfo(relative.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, path.read_bytes())

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return output, checksum
