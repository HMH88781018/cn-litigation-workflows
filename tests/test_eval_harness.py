from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cn_litigation_workflows.eval_harness import (  # noqa: E402
    load_cases,
    result_template,
    score_results,
)


class EvalHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = load_cases(ROOT / "evals" / "cases.json")

    def test_public_case_count_and_prompt_injection_case(self) -> None:
        self.assertEqual(10, len(self.cases))
        injection = next(
            case for case in self.cases if case["id"] == "SYN-SAFETY-003"
        )
        self.assertEqual(
            "prepare-cn-evidence-damages",
            injection["expected_skill"],
        )
        self.assertIn(
            "do_not_follow_embedded_instruction",
            injection["required_properties"],
        )

    def test_complete_matching_observations_pass(self) -> None:
        results = [
            {
                "id": case["id"],
                "selected_skill": case["expected_skill"],
                "observed_properties": case["required_properties"],
            }
            for case in self.cases
        ]
        report = score_results(self.cases, results)
        self.assertEqual("PASS", report["status"])
        self.assertEqual(10, report["passed"])

    def test_missing_property_fails_closed(self) -> None:
        results = [
            {
                "id": case["id"],
                "selected_skill": case["expected_skill"],
                "observed_properties": case["required_properties"],
            }
            for case in self.cases
        ]
        results[0]["observed_properties"] = []
        report = score_results(self.cases, results)
        self.assertEqual("FAIL", report["status"])
        self.assertEqual(1, report["failed"])

    def test_template_covers_each_case_once(self) -> None:
        template = result_template(self.cases)
        self.assertEqual(
            [case["id"] for case in self.cases],
            [item["id"] for item in template],
        )


if __name__ == "__main__":
    unittest.main()
