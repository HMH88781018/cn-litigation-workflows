"""Console entry points."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .release import build_archive, build_submission_archive
from .validator import validate_project


def validate_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate CN Litigation Workflows.")
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--fail-on-warning", action="store_true")
    args = parser.parse_args(argv)

    issues = validate_project(Path(args.root))
    if args.as_json:
        print(
            json.dumps(
                {
                    "status": "FAIL" if any(i.severity == "ERROR" for i in issues) else "PASS",
                    "issues": [item.to_dict() for item in issues],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif not issues:
        print("PASS: project validation found no issues.")
    else:
        for item in issues:
            print(f"{item.severity} {item.code} {item.path}: {item.message}")

    if any(item.severity == "ERROR" for item in issues):
        return 1
    if args.fail_on_warning and any(item.severity == "WARNING" for item in issues):
        return 2
    return 0


def package_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic plugin archive.")
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--submission",
        action="store_true",
        help="Build the minimal Skills-only OpenAI submission ZIP.",
    )
    args = parser.parse_args(argv)

    issues = validate_project(Path(args.root))
    errors = [item for item in issues if item.severity == "ERROR"]
    if errors:
        for item in errors:
            print(f"ERROR {item.code} {item.path}: {item.message}", file=sys.stderr)
        return 1
    builder = build_submission_archive if args.submission else build_archive
    archive, checksum = builder(Path(args.root), Path(args.output))
    print(archive)
    print(checksum)
    return 0
