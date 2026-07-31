from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RoutingContractTests(unittest.TestCase):
    def test_cross_skill_source_of_truth_is_documented(self) -> None:
        draft = (
            ROOT / "skills" / "draft-cn-element-complaints" / "SKILL.md"
        ).read_text(encoding="utf-8")
        evidence = (
            ROOT / "skills" / "prepare-cn-evidence-damages" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("prepare-cn-evidence-damages", draft)
        self.assertIn("draft-cn-element-complaints", evidence)
        self.assertIn("唯一真源", evidence)

    def test_public_evals_use_only_synthetic_inputs(self) -> None:
        cases = json.loads((ROOT / "evals" / "cases.json").read_text(encoding="utf-8"))
        self.assertEqual(10, len(cases))
        for case in cases:
            self.assertTrue(case["id"].startswith("SYN-"))
            self.assertIn(case["expected_skill"], {
                "draft-cn-element-complaints",
                "prepare-cn-evidence-damages",
                None,
            })
            self.assertNotIn("身份证号：", case["prompt"])

    def test_release_guardrails_distinguish_instruction_and_review_evidence(self) -> None:
        draft = (
            ROOT / "skills" / "draft-cn-element-complaints" / "SKILL.md"
        ).read_text(encoding="utf-8")
        evidence = (
            ROOT / "skills" / "prepare-cn-evidence-damages" / "SKILL.md"
        ).read_text(encoding="utf-8")
        release = (
            ROOT
            / "skills"
            / "prepare-cn-evidence-damages"
            / "references"
            / "release-gates.md"
        ).read_text(encoding="utf-8")
        self.assertIn("指令/诉请意向", draft)
        self.assertIn("证据支持值", draft)
        self.assertIn("不可信案件数据", draft)
        self.assertIn("不可信材料内容", evidence)
        self.assertIn("即使不要求用户在多个方案中选择", evidence)
        self.assertIn("不构成", release)
        self.assertIn("独立人工复核", release)


if __name__ == "__main__":
    unittest.main()
