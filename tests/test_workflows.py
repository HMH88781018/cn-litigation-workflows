from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


class WorkflowSecurityTests(unittest.TestCase):
    def test_all_actions_are_pinned_to_full_commit_shas(self) -> None:
        uses_pattern = re.compile(r"(?m)^\s*uses:\s+[^@\s]+@([^\s#]+)")
        for path in sorted(WORKFLOWS.glob("*.yml")):
            with self.subTest(workflow=path.name):
                refs = uses_pattern.findall(path.read_text(encoding="utf-8"))
                self.assertTrue(refs)
                self.assertTrue(
                    all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in refs),
                    refs,
                )

    def test_codex_review_isolates_untrusted_pull_request_data(self) -> None:
        text = (WORKFLOWS / "codex-pr-review.yml").read_text(encoding="utf-8")
        self.assertNotIn("actions/checkout@", text)
        self.assertNotIn("refs/pull/", text)
        self.assertNotIn("prompt-file:", text)
        self.assertNotIn("output-file:", text)
        self.assertIn("application/vnd.github.v3.diff", text)
        self.assertIn("--max-filesize 2097152", text)
        self.assertIn(
            "working-directory: ${{ runner.temp }}/codex-review-context",
            text,
        )
        self.assertIn('permission-profile: ":read-only"', text)
        self.assertIn("safety-strategy: drop-sudo", text)
        self.assertEqual(1, text.count("secrets.OPENAI_API_KEY"))
        self.assertLess(text.index("Run read-only Codex review"), text.index("publish:"))


if __name__ == "__main__":
    unittest.main()
