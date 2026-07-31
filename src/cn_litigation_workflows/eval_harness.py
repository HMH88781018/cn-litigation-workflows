"""Validate and score synthetic Skill evaluation observations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ALLOWED_SKILLS = {
    "draft-cn-element-complaints",
    "prepare-cn-evidence-damages",
    None,
}


def load_cases(path: Path) -> list[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read eval cases from {path}: {exc}") from exc
    if not isinstance(value, list) or not value:
        raise ValueError("Eval cases must be a non-empty JSON array.")

    seen: set[str] = set()
    for index, case in enumerate(value):
        location = f"case[{index}]"
        if not isinstance(case, dict):
            raise ValueError(f"{location} must be an object.")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.startswith("SYN-"):
            raise ValueError(f"{location}.id must be a SYN-* string.")
        if case_id in seen:
            raise ValueError(f"Duplicate eval id: {case_id}")
        seen.add(case_id)
        if not isinstance(case.get("prompt"), str) or not case["prompt"].strip():
            raise ValueError(f"{case_id}.prompt must be a non-empty string.")
        if case.get("expected_skill") not in ALLOWED_SKILLS:
            raise ValueError(f"{case_id}.expected_skill is not recognized.")
        properties = case.get("required_properties")
        if (
            not isinstance(properties, list)
            or not properties
            or any(not isinstance(item, str) or not item for item in properties)
            or len(set(properties)) != len(properties)
        ):
            raise ValueError(
                f"{case_id}.required_properties must be unique non-empty strings."
            )
    return value


def result_template(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": case["id"],
            "selected_skill": None,
            "observed_properties": [],
            "notes": "",
        }
        for case in cases
    ]


def load_results(path: Path) -> list[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read eval results from {path}: {exc}") from exc
    if not isinstance(value, list):
        raise ValueError("Eval results must be a JSON array.")
    return value


def score_results(
    cases: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    expected = {case["id"]: case for case in cases}
    observed: dict[str, dict[str, Any]] = {}
    malformed: list[str] = []

    for index, result in enumerate(results):
        if not isinstance(result, dict):
            malformed.append(f"result[{index}] is not an object")
            continue
        result_id = result.get("id")
        if not isinstance(result_id, str):
            malformed.append(f"result[{index}].id is not a string")
            continue
        if result_id in observed:
            malformed.append(f"duplicate result id: {result_id}")
            continue
        properties = result.get("observed_properties")
        if not isinstance(properties, list) or any(
            not isinstance(item, str) for item in properties
        ):
            malformed.append(f"{result_id}.observed_properties is not a string array")
            continue
        selected_skill = result.get("selected_skill")
        if selected_skill not in ALLOWED_SKILLS:
            malformed.append(f"{result_id}.selected_skill is not recognized")
            continue
        observed[result_id] = result

    case_reports: list[dict[str, Any]] = []
    for case_id, case in expected.items():
        result = observed.get(case_id)
        if result is None:
            case_reports.append(
                {
                    "id": case_id,
                    "passed": False,
                    "skill_match": False,
                    "missing_properties": case["required_properties"],
                    "reason": "missing_result",
                }
            )
            continue
        observed_properties = set(result["observed_properties"])
        missing_properties = [
            item
            for item in case["required_properties"]
            if item not in observed_properties
        ]
        skill_match = result["selected_skill"] == case["expected_skill"]
        case_reports.append(
            {
                "id": case_id,
                "passed": skill_match and not missing_properties,
                "skill_match": skill_match,
                "missing_properties": missing_properties,
                "reason": None,
            }
        )

    unexpected = sorted(set(observed) - set(expected))
    passed = sum(1 for item in case_reports if item["passed"])
    failed = len(case_reports) - passed
    status = "PASS" if not malformed and not unexpected and failed == 0 else "FAIL"
    return {
        "status": status,
        "total": len(case_reports),
        "passed": passed,
        "failed": failed,
        "malformed": malformed,
        "unexpected_result_ids": unexpected,
        "cases": case_reports,
    }


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="Validate synthetic cases or score recorded Skill observations."
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=root / "evals" / "cases.json",
        help="eval case JSON path",
    )
    parser.add_argument("--results", type=Path, help="recorded observation JSON path")
    parser.add_argument(
        "--template",
        action="store_true",
        help="print a result-recording template as JSON",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    try:
        cases = load_cases(args.cases)
        if args.template:
            print(json.dumps(result_template(cases), ensure_ascii=False, indent=2))
            return 0
        if args.results:
            report = score_results(cases, load_results(args.results))
            if args.as_json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                print(
                    f"{report['status']}: {report['passed']}/{report['total']} "
                    "synthetic eval cases passed."
                )
                for item in report["cases"]:
                    if not item["passed"]:
                        missing = ", ".join(item["missing_properties"]) or "none"
                        print(
                            f"FAIL {item['id']}: skill_match={item['skill_match']}; "
                            f"missing_properties={missing}"
                        )
                for message in report["malformed"]:
                    print(f"FAIL malformed result: {message}")
                for result_id in report["unexpected_result_ids"]:
                    print(f"FAIL unexpected result id: {result_id}")
            return 0 if report["status"] == "PASS" else 1
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.as_json:
        print(json.dumps({"status": "PASS", "cases": len(cases)}, indent=2))
    else:
        print(f"PASS: {len(cases)} synthetic eval cases are structurally valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
